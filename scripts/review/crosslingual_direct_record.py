#!/usr/bin/env python3
"""Record and check the output of the cross-language search from the function itself.

The golden API check compares the one cross-language request loosely (it goes
through a poll and a result cache). A refactor of
backend/blueprints/search.py::_direct_crosslingual_core needs an exact
comparison, so this script runs real cross-language searches in-process (no
server), by the route the site takes (_parse_search_request, _load_units,
_crosslingual_fusion_core), and records EVERY returned result row with every
field, scores as the repr of the float.

    TESSERAE_USE_DIRECT_SEARCH=1 PYTHONHASHSEED=0 \
        python scripts/review/crosslingual_direct_record.py record --out DIR
    TESSERAE_USE_DIRECT_SEARCH=1 PYTHONHASHSEED=0 \
        python scripts/review/crosslingual_direct_record.py check --against DIR
    TESSERAE_USE_DIRECT_SEARCH=1 PYTHONHASHSEED=0 \
        python scripts/review/crosslingual_direct_record.py replay --against DIR
    TESSERAE_USE_DIRECT_SEARCH=1 PYTHONHASHSEED=0 \
        python scripts/review/crosslingual_direct_record.py time --against DIR [--runs 5]

record  runs the searches in SEARCHES and writes NAME.jsonl.gz per search (one
        header line with every field of the answer except the result rows, then
        one line per result row) and NAME.inputs.pkl (the units and the
        settings, for replay).
check   reruns the same searches and compares the header and every row with the
        recording. Any changed field, row order or row count is a difference.
        Exit status 1 if anything differs.
replay  feeds the pickled units and settings back through the route and
        compares. The inputs are fixed, so the comparison is exact and leaves
        the loading of the texts out.
time    runs _direct_crosslingual_core directly on the pickled inputs of the
        timed searches and prints the times and the median.

Run it under ~/bin/tess-job (it loads the lemma caches and the embeddings).
"""
import argparse
import copy
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

# name, source language, target language, source file, target file, extra settings
SEARCHES = [
    ("grc_la_iliad1_aeneid1", "grc", "la", "homer.iliad.part.1", "vergil.aeneid.part.1", {}),
    ("la_grc_aeneid1_iliad1", "la", "grc", "vergil.aeneid.part.1", "homer.iliad.part.1", {}),
    # Every English text's precomputed embedding is 384-dimensional (MiniLM) and the
    # Latin and Greek ones 768 (SPhilBERTa), so on 2026-10-13 the live Latin-English
    # and Greek-English searches end in a matmul ValueError in the semantic channel.
    # The first two English searches below withhold the English precomputed
    # embeddings (the channel then encodes the English lines itself) so that the
    # rest of the function is exercised; the third records the error as the site
    # raises it. "_no_en_emb" and "_expect_error" are read here and not passed on.
    ("la_en_aeneid1_paradise1", "la", "en", "vergil.aeneid.part.1", "milton.paradise_lost.part.1",
     {"_no_en_emb": True}),
    ("grc_en_odyssey1_paradise1", "grc", "en", "homer.odyssey.part.1", "milton.paradise_lost.part.1",
     {"_no_en_emb": True}),
    ("la_en_aeneid1_paradise1_live_error", "la", "en", "vergil.aeneid.part.1", "milton.paradise_lost.part.1",
     {"_expect_error": True}),
    ("he_grc_genesis_direct", "he", "grc", "hebrew_bible.genesis", "septuaginta.genesis",
     {"hebrew_greek_route": "direct"}),
    ("cop_grc_genesis", "cop", "grc", "bohairic.genesis", "septuaginta.genesis", {}),
    ("fa_ur_hafez_ghalib", "fa", "ur", "hafez.diwan", "ghalib.diwan_wikisource", {}),
    ("grc_la_iliad1_aeneid1_penalty", "grc", "la", "homer.iliad.part.1", "vergil.aeneid.part.1",
     {"crosslingual_lemma_gate": "penalty"}),
    ("grc_la_iliad1_aeneid1_gateoff", "grc", "la", "homer.iliad.part.1", "vergil.aeneid.part.1",
     {"crosslingual_lemma_gate": "off"}),
]
TIMED = ("grc_la_iliad1_aeneid1", "la_en_aeneid1_paradise1")


def canon(obj):
    """Canonical JSON text: sorted keys, sets sorted, floats as repr."""
    def default(o):
        if isinstance(o, (set, frozenset)):
            return sorted(o, key=repr)
        return repr(o)

    def fix(o):
        if isinstance(o, float):
            return {"__float__": repr(o)}
        if isinstance(o, dict):
            return {k: fix(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [fix(v) for v in o]
        return o
    return json.dumps(fix(obj), sort_keys=True, default=default, ensure_ascii=True)


def reset_state():
    """Empty the caches whose content depends on which lemmas earlier searches asked for."""
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


def load_search_module():
    """The search blueprint module, wired to the shared objects the way backend/app.py wires it."""
    from backend import runtime
    from backend.frequency_cache import get_corpus_frequencies
    from backend.blueprints import search as sm
    sm.init_search_blueprint(
        matcher=runtime.matcher, scorer=runtime.scorer, text_processor=runtime.text_processor,
        texts_dir=runtime.TEXTS_DIR, get_processed_units_fn=runtime.get_processed_units,
        get_corpus_frequencies_fn=get_corpus_frequencies)
    return sm


def build_inputs(sm, sl, tl, src, tgt, extra):
    """Parameters, units and settings, built the way the poll route builds them."""
    req = {"source": f"{src}.tess", "target": f"{tgt}.tess",
           "source_language": sl, "target_language": tl,
           "match_type": "crosslingual_fusion", "min_matches": 1, "max_results": 2000}
    # _parse_search_request copies only a fixed list of top-level keys into the
    # settings; the lemma-gate settings go in the settings object directly, as the
    # site's request body can carry them.
    settings = {k: v for k, v in extra.items() if k.startswith("crosslingual_")}
    req.update({k: v for k, v in extra.items() if not k.startswith("_") and k not in settings})
    req["settings"] = settings
    params = sm._parse_search_request(req)
    su, tu = sm._load_units(params)
    return params, su, tu


def answer_lines(core):
    """The answer as canonical lines: a header of every non-row field, then the rows."""
    head = {k: v for k, v in core.items() if k != "results"}
    # Timing and cache fields vary from run to run without the answer changing.
    for k in ("elapsed", "elapsed_seconds", "search_time", "time", "timing", "timings", "cached"):
        head.pop(k, None)
    rows = core.get("results") or []
    return [canon(head)] + [canon(r) for r in rows], len(rows)


def run_core(sm, params, su, tu, extra=None):
    extra = extra or {}
    reset_state()
    settings = params["settings"]
    from backend import embedding_storage
    real_load = embedding_storage.load_embeddings
    if extra.get("_no_en_emb"):
        embedding_storage.load_embeddings = (
            lambda path, language: None if language == "en" else real_load(path, language))
    t0 = time.time()
    try:
        core = sm._crosslingual_fusion_core(params, su, tu, settings, None)
    except Exception as e:
        if not extra.get("_expect_error"):
            raise
        core = {"__exception__": f"{type(e).__name__}: {e}"}
    finally:
        embedding_storage.load_embeddings = real_load
    return core, time.time() - t0


def cmd_record_or_check(args, mode):
    register_language_plugins()
    from backend import passage_index
    passage_index._ensure_loaded()
    sm = load_search_module()
    out = Path(args.out if mode == "record" else args.against)
    out.mkdir(parents=True, exist_ok=True)
    bad = 0
    summary = []
    for name, sl, tl, src, tgt, extra in SEARCHES:
        if args.only and name not in args.only:
            continue
        params, su, tu = build_inputs(sm, sl, tl, src, tgt, extra)
        if mode == "record":
            with open(out / f"{name}.inputs.pkl", "wb") as f:
                pickle.dump((copy.deepcopy(params), su, tu), f, protocol=4)
        core, secs = run_core(sm, params, su, tu, extra)
        lines, nrows = answer_lines(core)
        path = out / f"{name}.jsonl.gz"
        line = f"{name}: {sl}-{tl} {src} x {tgt} {extra or ''} lines {len(su)}x{len(tu)}, {nrows} rows, {secs:.0f}s"
        if mode == "record":
            with gzip.open(path, "wt", encoding="utf-8", compresslevel=3) as fh:
                for ln in lines:
                    fh.write(ln + "\n")
        else:
            with gzip.open(path, "rt", encoding="utf-8") as fh:
                rec = [ln.rstrip("\n") for ln in fh]
            diffs = compare(rec, lines)
            if diffs:
                bad += 1
                line += "  DIFFERENT\n    " + "\n    ".join(diffs[:12])
            else:
                line += "  same"
        print(line, flush=True)
        summary.append(line)
    if mode == "record":
        (out / "manifest.json").write_text(json.dumps(
            {"searches": [list(s[:5]) + [s[5]] for s in SEARCHES],
             "recorded": time.strftime("%Y-%m-%d %H:%M:%S"), "summary": summary}, indent=1))
    else:
        print(f"{len(summary) - bad} same, {bad} different")
    return 1 if bad else 0


def compare(rec, now):
    """Differences between recorded and new lines (header first, then rows)."""
    msgs = []
    if len(rec) != len(now):
        msgs.append(f"row count: recorded {len(rec) - 1}, now {len(now) - 1}")
    n = max(len(rec), len(now))
    diff_idx = [i for i in range(n)
                if (rec[i] if i < len(rec) else None) != (now[i] if i < len(now) else None)]
    if diff_idx:
        msgs.append(f"{len(diff_idx)} differing lines of {n} (line 0 is the header)")
        for i in diff_idx[:3]:
            msgs.append(f"line {i}: recorded {str(rec[i] if i < len(rec) else None)[:300]}"
                        f" / now {str(now[i] if i < len(now) else None)[:300]}")
    return msgs


def cmd_replay(args):
    register_language_plugins()
    from backend import passage_index
    passage_index._ensure_loaded()
    sm = load_search_module()
    out = Path(args.against)
    bad = 0
    for name, sl, tl, src, tgt, extra in SEARCHES:
        if args.only and name not in args.only:
            continue
        with open(out / f"{name}.inputs.pkl", "rb") as f:
            params, su, tu = pickle.load(f)
        core, secs = run_core(sm, params, su, tu, extra)
        lines, nrows = answer_lines(core)
        with gzip.open(out / f"{name}.jsonl.gz", "rt", encoding="utf-8") as fh:
            rec = [ln.rstrip("\n") for ln in fh]
        diffs = compare(rec, lines)
        bad += bool(diffs)
        status = "  same" if not diffs else "  DIFFERENT\n    " + "\n    ".join(diffs[:10])
        print(f"{name}: replayed {nrows} rows, {secs:.0f}s{status}", flush=True)
    print(f"replay: {bad} searches different")
    return 1 if bad else 0


def cmd_time(args):
    register_language_plugins()
    from backend import passage_index
    passage_index._ensure_loaded()
    sm = load_search_module()
    out = Path(args.against)
    from backend import embedding_storage
    real_load = embedding_storage.load_embeddings
    # As in the English searches of SEARCHES: the English precomputed embeddings are withheld.
    embedding_storage.load_embeddings = (
        lambda path, language: None if language == "en" else real_load(path, language))
    for name in TIMED:
        with open(out / f"{name}.inputs.pkl", "rb") as f:
            params, su, tu = pickle.load(f)
        times = []
        for _ in range(args.runs):
            p = copy.deepcopy(params)
            reset_state()
            t0 = time.time()
            core = sm._direct_crosslingual_core(p, su, tu, p["settings"], None, None)
            times.append(time.time() - t0)
            del core
        print(f"{name}: runs {[round(t, 2) for t in times]} median {statistics.median(times):.2f}s",
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
    args = ap.parse_args()
    if args.cmd == "time":
        return cmd_time(args)
    if args.cmd == "replay":
        return cmd_replay(args)
    return cmd_record_or_check(args, args.cmd)


if __name__ == "__main__":
    sys.exit(main())
