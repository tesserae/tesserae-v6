#!/usr/bin/env python3
"""Identity check: the live search's evaluation path against the evaluation scorer itself.

The cross-language setting crosslingual_scorer = 'evaluation' (backend/crosslingual_evaluation_path.py)
claims to rank Greek-Latin pairs exactly as evaluation/scripts/crosslingual_common.py's fused_score
does, with the lone-pair rule of the 'v2' variant. This script tests the claim on Aeneid 1 against
Iliad 1, in both directions of search.

  Evaluation side: units from TextProcessor.process_file and embeddings from load_embeddings, as
  evaluation/scripts/benchmark_knauer_crosslingual.py loads them, then make_fused_scorer with
  XL_RARITY_VARIANT=v2 in the environment, scoring EVERY (Greek line, Latin line) pair.
  Live side: _crosslingual_fusion_core called in process (no web request) through the route the
  site takes, with settings crosslingual_scorer='evaluation' and max_results=TOP.

The top TOP pairs of the evaluation side must be the top TOP rows of the live side, in the same
order, with scores equal to 4 decimal places. Exit status 0 when they are, 1 when not.

    TESSERAE_USE_DIRECT_SEARCH=1 PYTHONHASHSEED=0 \
        ~/bin/tess-job --fg xlident 6 python scripts/review/crosslingual_evaluation_identity.py [--top 200]

Needs the texts, lemma caches and embeddings; the test in tests/ skips without them.
"""
import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("TESSERAE_USE_DIRECT_SEARCH", "1")
os.environ["XL_RARITY_VARIANT"] = "v2"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "review"))

GREEK = "homer.iliad.part.1"
LATIN = "vergil.aeneid.part.1"


def site_units():
    """The search module and the units of both texts as the site loads them (lemma caches)."""
    import crosslingual_direct_record as R
    R.register_language_plugins()
    sm = R.load_search_module()
    params, su, tu = R.build_inputs(sm, "grc", "la", GREEK, LATIN, {"crosslingual_scorer": "evaluation"})
    return R, sm, su, tu


def evaluation_side(su, tu, top):
    """The evaluation scorer's own top pairs, [(score, greek ref, latin ref)], best first.

    The units are the ones the site loads from its lemma caches, the same inputs the live
    path gets, so that only the scoring differs. (evaluation/scripts/benchmark_knauer_crosslingual.py
    lemmatizes afresh with TextProcessor.process_file; fresh_unit_differences below counts
    the lines where the two disagree.)
    """
    sys.path.insert(0, str(ROOT / "evaluation" / "scripts"))
    from crosslingual_common import TEXTS_DIR, make_fused_scorer
    from backend.embedding_storage import load_embeddings
    grc_path = TEXTS_DIR / "grc" / f"{GREEK}.tess"
    lat_path = TEXTS_DIR / "la" / f"{LATIN}.tess"
    grc_emb = load_embeddings(str(grc_path), "grc")
    lat_emb = load_embeddings(str(lat_path), "la")
    fused_score, _ = make_fused_scorer(grc_path, lat_path, su, tu, grc_emb, lat_emb, verbose=False)
    scored = []
    for g in range(len(su)):
        for lt in range(len(tu)):
            scored.append((fused_score(g, lt), g, lt))
    scored.sort(key=lambda t: (-t[0], t[1], t[2]))
    return [(s, su[g]["ref"], tu[lt]["ref"]) for s, g, lt in scored[:top]], len(scored)


def fresh_unit_differences(su, tu):
    """How many lines have other lemmas under a fresh TextProcessor run than in the site's caches."""
    sys.path.insert(0, str(ROOT / "evaluation" / "scripts"))
    from crosslingual_common import TEXTS_DIR
    from backend.text_processor import TextProcessor
    tp = TextProcessor()
    fresh_g = tp.process_file(str(TEXTS_DIR / "grc" / f"{GREEK}.tess"), "grc")
    fresh_l = tp.process_file(str(TEXTS_DIR / "la" / f"{LATIN}.tess"), "la")
    dg = sum(1 for a, b in zip(fresh_g, su) if a.get("lemmas") != b.get("lemmas"))
    dl = sum(1 for a, b in zip(fresh_l, tu) if a.get("lemmas") != b.get("lemmas"))
    return dg, len(su), dl, len(tu)


def live_side(R, sm, source_language, top):
    """The live function's rows under the evaluation scorer, [(score, greek ref, latin ref)]."""
    if source_language == "la":
        sl, tl, src, tgt = "la", "grc", LATIN, GREEK
    else:
        sl, tl, src, tgt = "grc", "la", GREEK, LATIN
    params, su, tu = R.build_inputs(sm, sl, tl, src, tgt, {"crosslingual_scorer": "evaluation"})
    params["settings"]["max_results"] = top
    core, _ = R.run_core(sm, params, su, tu, {})
    if core.get("error"):
        raise SystemExit(f"live path error: {core['error']}")
    rows = []
    for r in core["results"]:
        s_ref, t_ref = r["source"]["ref"], r["target"]["ref"]
        g_ref, l_ref = (s_ref, t_ref) if sl == "grc" else (t_ref, s_ref)
        rows.append((r["overall_score"], g_ref, l_ref))
    return rows


def short(ref):
    """Compare refs by their numbers (the live rows carry short loci)."""
    import re
    return tuple(int(n) for n in re.findall(r"\d+", ref)[-2:])


def compare(ev_rows, live_rows):
    problems = []
    if len(ev_rows) != len(live_rows):
        problems.append(f"row count: evaluation side {len(ev_rows)}, live {len(live_rows)}")
    worst = 0.0
    for i, (e, lt) in enumerate(zip(ev_rows, live_rows), 1):
        d = abs(e[0] - lt[0])
        worst = max(worst, d)
        if round(e[0], 4) != round(lt[0], 4):
            problems.append(f"rank {i}: score {e[0]!r} vs {lt[0]!r}")
        if (short(e[1]), short(e[2])) != (short(lt[1]), short(lt[2])):
            problems.append(f"rank {i}: pair {e[1]}/{e[2]} vs {lt[1]}/{lt[2]}")
    return problems, worst


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--top", type=int, default=200)
    args = ap.parse_args()
    R, sm, su, tu = site_units()
    ev_rows, n_pairs = evaluation_side(su, tu, args.top)
    print(f"evaluation side: {n_pairs} pairs scored, top {len(ev_rows)} kept, "
          f"best {ev_rows[0][0]:.4f}, rank {len(ev_rows)} {ev_rows[-1][0]:.4f}", flush=True)
    bad = 0
    for sl in ("la", "grc"):
        live_rows = live_side(R, sm, sl, args.top)
        problems, worst = compare(ev_rows, live_rows)
        print(f"search from {sl}: {len(live_rows)} rows, largest score difference {worst:.2e}, "
              f"{'IDENTICAL' if not problems else 'DIFFERENT'}", flush=True)
        for p in problems[:10]:
            print("   ", p)
        bad += bool(problems)
    dg, ng, dl, nl = fresh_unit_differences(su, tu)
    print(f"for information: lines whose lemmas differ between the site's caches and a fresh "
          f"TextProcessor run: Greek {dg} of {ng}, Latin {dl} of {nl}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
