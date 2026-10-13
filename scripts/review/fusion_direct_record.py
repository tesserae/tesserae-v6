#!/usr/bin/env python3
"""Record and check the output of fuse_results() from the function itself.

The golden API check compares the two fusion requests loosely (they are long
and cached). A refactor of backend/fusion.py::fuse_results needs an exact
comparison, so this script runs real fusion searches in-process (no server)
and records EVERY output row of EVERY fuse_results call, scores as the repr of
the float.

    TESSERAE_USE_DIRECT_SEARCH=1 PYTHONHASHSEED=0 \
        python scripts/review/fusion_direct_record.py record --out DIR
    TESSERAE_USE_DIRECT_SEARCH=1 PYTHONHASHSEED=0 \
        python scripts/review/fusion_direct_record.py check --against DIR
    TESSERAE_USE_DIRECT_SEARCH=1 PYTHONHASHSEED=0 \
        python scripts/review/fusion_direct_record.py replay --against DIR
    python scripts/review/fusion_direct_record.py time --against DIR [--runs 5]

record  runs the searches in SEARCHES and writes NAME.jsonl.gz per search (one
        header line per fuse_results call, then one line per output row) and
        NAME.inputs/callK.pkl (the arguments of each call, for `time`).
check   reruns the same searches and compares every row of every call with the
        recording. Any changed field, row order or row count is a difference.
        Exit status 1 if anything differs.
replay  feeds the pickled inputs of every recorded call back through
        fuse_results alone and compares the rows. The inputs are fixed, so the
        comparison is exact; this is the proof for a change inside fuse_results.
time    replays the largest recorded call of each of the first Latin and first
        Greek searches directly through fuse_results (inputs unpickled each
        run) and prints the times and the median.

Run it under ~/bin/tess-job (it loads the lemma caches and the embeddings).
"""
import argparse
import gzip
import json
import os
import pickle
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("TESSERAE_USE_DIRECT_SEARCH", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# name, language, source file, target file, extra options
SEARCHES = [
    ("la_aeneid1_met1", "la", "vergil.aeneid.part.1", "ovid.metamorphoses.part.1", {}),
    ("la_lucan1_aeneid2", "la", "lucan.bellum_civile.part.1", "vergil.aeneid.part.2", {}),
    ("la_catullus_propertius1", "la", "catullus.carmina", "propertius.elegies.part.1", {}),
    ("grc_iliad1_argonautica1", "grc", "homer.iliad.part.1", "apollonius_rhodius.argonautica.part.1", {}),
    ("grc_theogony_odyssey1", "grc", "hesiod.theogony", "homer.odyssey.part.1", {}),
    ("cop_bohairic_matthew_sahidic_matthew", "cop", "bohairic.matthew", "sahidica.matthew", {}),
    ("fa_asrar_rumuz", "fa", "iqbal.asrar_e_khudi", "iqbal.rumuz_e_bekhudi", {}),
    ("la_aeneid1_met1_meter", "la", "vergil.aeneid.part.1", "ovid.metamorphoses.part.1",
     {"freq_basis": "meter"}),
    ("la_aeneid1_met1_noctx", "la", "vergil.aeneid.part.1", "ovid.metamorphoses.part.1",
     {"confirm_context": False}),
]
TIMED = ("la_aeneid1_met1", "grc_iliad1_argonautica1")


def canon(obj):
    """Canonical JSON text of a row: sorted keys, sets sorted, floats as repr."""
    def default(o):
        if isinstance(o, (set, frozenset)):
            return sorted(o, key=repr)
        return repr(o)
    return json.dumps(obj, sort_keys=True, default=default, ensure_ascii=True)


def compare_call(k, rec_lines, now_lines):
    """Differences between the recorded and the new rows of one call (list of messages).

    A row-by-row difference where the two sides hold the same set of rows and
    the fused_score at every differing position is equal is reported as
    'tie order only': rows of equal score swapped places. That comes from the
    channels upstream (they return equal-score rows in a different order from
    one process to the next), not from fuse_results, which the replay command
    proves separately.
    """
    msgs = []
    n = max(len(rec_lines), len(now_lines))
    diff_idx = [i for i in range(n)
                if (rec_lines[i] if i < len(rec_lines) else None) != (now_lines[i] if i < len(now_lines) else None)]
    if not diff_idx:
        return msgs
    tie_only = len(rec_lines) == len(now_lines) and sorted(rec_lines) == sorted(now_lines)
    if tie_only:
        for i in diff_idx:
            if json.loads(rec_lines[i]).get("fused_score") != json.loads(now_lines[i]).get("fused_score"):
                tie_only = False
                break
    kind = "TIE ORDER ONLY (same rows, equal scores swapped)" if tie_only else "REAL DIFFERENCE"
    msgs.append(f"call {k}: {len(diff_idx)} differing positions of {n}: {kind}")
    if not tie_only:
        for i in diff_idx[:3]:
            msgs.append(f"call {k} row {i}: recorded {str(rec_lines[i] if i < len(rec_lines) else None)[:300]}"
                        f" / now {str(now_lines[i] if i < len(now_lines) else None)[:300]}")
    return msgs


class Recorder:
    """Wraps backend.fusion.fuse_results; one call = one numbered group of rows."""

    def __init__(self, fusion, mode, rec_path, inputs_dir, force_no_ctx):
        self.fusion = fusion
        self.orig = fusion.fuse_results
        self.mode = mode
        self.rec_path = rec_path
        self.inputs_dir = inputs_dir
        self.force_no_ctx = force_no_ctx
        self.calls = 0
        self.diffs = []
        self.rows_total = 0
        if mode == "record":
            self.fh = gzip.open(rec_path, "wt", encoding="utf-8", compresslevel=3)
        else:
            self.fh = gzip.open(rec_path, "rt", encoding="utf-8")

    def __call__(self, channel_results, *args, **kwargs):
        if self.force_no_ctx:
            kwargs["confirm_context"] = False
        k = self.calls
        self.calls += 1
        if self.mode == "record" and self.inputs_dir is not None:
            self.inputs_dir.mkdir(parents=True, exist_ok=True)
            with open(self.inputs_dir / f"call{k}.pkl", "wb") as f:
                pickle.dump((channel_results, args, kwargs), f, protocol=4)
        rows = self.orig(channel_results, *args, **kwargs)
        header = {"call": k, "n_rows": len(rows),
                  "kwargs": {a: (v if isinstance(v, (str, int, float, bool, type(None))) else "<obj>")
                             for a, v in kwargs.items()},
                  "channels": sorted(channel_results.keys())}
        self.rows_total += len(rows)
        if self.mode == "record":
            self.fh.write(canon(header) + "\n")
            for r in rows:
                self.fh.write(canon(r) + "\n")
        else:
            hl = self.fh.readline().rstrip("\n")
            if hl != canon(header):
                self.diffs.append(f"call {k}: header differs: recorded {hl[:200]} / now {canon(header)[:200]}")
                try:
                    n_rec = json.loads(hl)["n_rows"]
                except Exception:
                    n_rec = len(rows)
            else:
                n_rec = len(rows)
            rec_lines = [self.fh.readline().rstrip("\n") for _ in range(n_rec)]
            self.diffs.extend(compare_call(k, rec_lines, [canon(r) for r in rows]))
        return rows

    def close(self):
        self.fh.close()


def run_one(language, src, tgt, opts, tp, matcher, scorer, fusion):
    src_path = str(ROOT / "texts" / language / f"{src}.tess")
    tgt_path = str(ROOT / "texts" / language / f"{tgt}.tess")
    su = tp.process_file(src_path, language, "line")
    tu = tp.process_file(tgt_path, language, "line")
    t0 = time.time()
    res = []
    # The path the site takes (streaming and poll endpoints): iter_fusion_search.
    for event_type, data in fusion.iter_fusion_search(
            source_units=su, target_units=tu, matcher=matcher, scorer=scorer,
            source_id=f"{src}.tess", target_id=f"{tgt}.tess", language=language,
            mode="merged", max_results=5000,
            source_path=src_path, target_path=tgt_path,
            user_settings={"use_meter": False},
            freq_basis=opts.get("freq_basis", "corpus"),
            channel_weights=None, enabled_channels=None):
        if event_type == "complete":
            res = data["results"]
    return len(su), len(tu), len(res), time.time() - t0


def reset_state(fusion):
    """Empty the module caches whose content depends on which lemmas earlier searches asked for.

    fuse_results is not a pure function of its inputs: _get_corpus_doc_freqs
    caches document frequencies lemma by lemma, and the u/v variant and
    headword adjustments it applies make a lemma's cached value depend on
    which other lemmas were fetched first. The same pair then scores slightly
    differently after other searches in the same process (seen 2026-10-13:
    one Latin row 2.815 vs 3.1177). A recording is therefore only repeatable
    from a defined starting state, so each search starts from empty caches.
    """
    for name in ("_corpus_doc_freq_cache", "_total_texts_cache", "_headword_map_cache",
                 "_meter_doc_freq_cache", "_meter_total_texts_cache", "_meter_text_ids_cache",
                 "_text_pair_doc_freq_cache", "_text_pair_total_tokens_cache"):
        obj = getattr(fusion, name, None)
        if isinstance(obj, dict):
            obj.clear()
    if hasattr(fusion, "_text_genre_cache"):
        fusion._text_genre_cache = None
    try:
        from backend import formula_filter, context_channel
        formula_filter._lemma_doc_freq_cache.clear()
        context_channel._baseline_cache.clear()
    except Exception:
        pass


def register_language_plugins():
    """Register the language handlers the way backend/app.py does at start-up."""
    for mod in ("coptic", "hebrew", "persian", "urdu"):
        try:
            __import__(f"backend.{mod}", fromlist=["register"]).register()
        except ImportError as e:
            print(f"language plugin {mod} not registered: {e}", file=sys.stderr)


def cmd_record_or_check(args, mode):
    from backend.text_processor import TextProcessor
    from backend.matcher import Matcher
    from backend.scorer import Scorer
    from backend import fusion
    register_language_plugins()
    # Load the passage index so the context-confirmation pass really runs
    # (without it that pass fails quietly and the rows come back unconfirmed).
    from backend import passage_index
    passage_index._ensure_loaded()
    out = Path(args.out if mode == "record" else args.against)
    out.mkdir(parents=True, exist_ok=True)
    tp, matcher, scorer = TextProcessor(), Matcher(), Scorer()
    orig = fusion.fuse_results
    bad = 0
    summary = []
    try:
        for name, language, src, tgt, opts in SEARCHES:
            if args.only and name not in args.only:
                continue
            path = out / f"{name}.jsonl.gz"
            reset_state(fusion)
            rec = Recorder(fusion, mode, path, out / f"{name}.inputs" if mode == "record" else None,
                           force_no_ctx=(opts.get("confirm_context") is False))
            fusion.fuse_results = rec
            try:
                ns, nt, nres, secs = run_one(language, src, tgt, opts, tp, matcher, scorer, fusion)
            finally:
                fusion.fuse_results = orig
                rec.close()
            line = (f"{name}: {language} {src} x {tgt} {opts or ''} lines {ns}x{nt}, "
                    f"{rec.calls} fuse_results calls, {rec.rows_total} rows, {nres} results, {secs:.0f}s")
            if mode == "check":
                if rec.diffs and all("TIE ORDER ONLY" in d for d in rec.diffs):
                    line += "  same except tie order (" + "; ".join(rec.diffs) + ")"
                elif rec.diffs:
                    bad += 1
                    line += "  DIFFERENT"
                    for d in rec.diffs[:12]:
                        line += "\n    " + d
                else:
                    line += "  same"
            print(line, flush=True)
            summary.append(line)
    finally:
        fusion.fuse_results = orig
    if mode == "record":
        (out / "manifest.json").write_text(json.dumps(
            {"searches": [list(s[:4]) + [s[4]] for s in SEARCHES], "recorded": time.strftime("%Y-%m-%d %H:%M:%S"),
             "summary": summary}, indent=1))
    else:
        print(f"{len(summary) - bad} same, {bad} different")
    return 1 if bad else 0


def cmd_replay(args):
    """Feed every recorded call's pickled inputs back through fuse_results and
    compare with the recorded rows: exact, because the inputs are fixed."""
    from backend import fusion
    register_language_plugins()
    from backend import passage_index
    passage_index._ensure_loaded()
    out = Path(args.against)
    bad = 0
    for name, language, src, tgt, opts in SEARCHES:
        if args.only and name not in args.only:
            continue
        reset_state(fusion)
        pk = sorted((out / f"{name}.inputs").glob("call*.pkl"), key=lambda p: int(p.stem[4:]))
        diffs = []
        rows_total = 0
        t0 = time.time()
        with gzip.open(out / f"{name}.jsonl.gz", "rt", encoding="utf-8") as fh:
            for k, path in enumerate(pk):
                header = json.loads(fh.readline())
                rec_lines = [fh.readline().rstrip("\n") for _ in range(header["n_rows"])]
                with open(path, "rb") as f:
                    channel_results, a, kw = pickle.load(f)
                rows = fusion.fuse_results(channel_results, *a, **kw)
                now_lines = [canon(r) for r in rows]
                rows_total += len(rows)
                if rec_lines != now_lines:
                    diffs.extend(compare_call(k, rec_lines, now_lines))
                    diffs.append(f"call {k}: replay differs (any difference here is real)")
        status = "  same" if not diffs else "  DIFFERENT\n    " + "\n    ".join(diffs[:10])
        bad += bool(diffs)
        print(f"{name}: replayed {len(pk)} calls, {rows_total} rows, {time.time() - t0:.0f}s{status}", flush=True)
    print(f"replay: {bad} searches different")
    return 1 if bad else 0


def cmd_time(args):
    from backend import fusion
    out = Path(args.against)
    for name in TIMED:
        d = out / f"{name}.inputs"
        biggest = max(d.glob("call*.pkl"), key=lambda p: p.stat().st_size)
        times = []
        for _ in range(args.runs):
            with open(biggest, "rb") as f:
                channel_results, a, kw = pickle.load(f)
            kw = dict(kw)
            if args.no_context:
                kw["confirm_context"] = False
            t0 = time.time()
            rows = fusion.fuse_results(channel_results, *a, **kw)
            times.append(time.time() - t0)
            del rows, channel_results
        print(f"{name} ({biggest.name}): runs {[round(t, 2) for t in times]} median {statistics.median(times):.2f}s",
              flush=True)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--out", required=True)
    r.add_argument("--only", nargs="*")
    c = sub.add_parser("check")
    c.add_argument("--against", required=True)
    c.add_argument("--only", nargs="*")
    rp = sub.add_parser("replay")
    rp.add_argument("--against", required=True)
    rp.add_argument("--only", nargs="*")
    t = sub.add_parser("time")
    t.add_argument("--against", required=True)
    t.add_argument("--runs", type=int, default=5)
    t.add_argument("--no-context", action="store_true")
    args = ap.parse_args()
    if args.cmd == "time":
        return cmd_time(args)
    if args.cmd == "replay":
        return cmd_replay(args)
    return cmd_record_or_check(args, args.cmd)


if __name__ == "__main__":
    sys.exit(main())
