#!/usr/bin/env python3
"""Blind reading material: the live and the evaluation scorer's top rows, mixed.

usage: crosslingual_scorer_blind.py OUT_DIR [--top 50] [--seed 20261017]

For three book pairs (Aeneid 1 against Iliad 1, Aeneid 2 against Iliad 2, Aeneid 6 against Odyssey 11)
runs the live Greek-Latin search twice through the route the site takes, with the live scorer
(two-lemma gate excluding, as today) and with the evaluation scorer (gate off), keeps the top rows of
each, and writes per book pair

  blind_<pair>.csv  the union of the rows in a random order. Columns: row_id, latin_locus,
                    latin_text, greek_locus, greek_text, dictionary_pairs. Nothing in it names
                    the scorer or a rank.
  key_<pair>.csv    row_id, live_rank, evaluation_rank (blank when the row is not in that
                    scorer's top rows), in_both.

The Latin text is the source of both searches. The dictionary pairs are the word-for-word pairs the
site's card shows for the row ("word->word", joined by " | "), without the phonetic echoes the live
scorer alone adds, so that the column does not tell the two apart.
"""
import argparse
import csv
import os
import random
import sys
from pathlib import Path

os.environ.setdefault("TESSERAE_USE_DIRECT_SEARCH", "1")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "review"))
import crosslingual_direct_record as R  # noqa: E402

PAIRS = [("aeneid1_iliad1", "vergil.aeneid.part.1", "homer.iliad.part.1"),
         ("aeneid2_iliad2", "vergil.aeneid.part.2", "homer.iliad.part.2"),
         ("aeneid6_odyssey11", "vergil.aeneid.part.6", "homer.odyssey.part.11")]


def top_rows(sm, latin, greek, scorer, top):
    """(rows, source units, target units) of one search; source is the Latin text."""
    extra = {}
    if scorer == "evaluation":
        extra = {"crosslingual_scorer": "evaluation", "crosslingual_lemma_gate": "off"}
    params, su, tu = R.build_inputs(sm, "la", "grc", latin, greek, extra)
    params["settings"]["max_results"] = top
    core, _ = R.run_core(sm, params, su, tu, {})
    if core.get("error"):
        raise SystemExit(core["error"])
    return core["results"], su, tu


def word_pairs(sm, src_unit, tgt_unit):
    """The word-for-word dictionary pairs of one pair of lines, one way for every row.

    The live search's own dictionary lookup (_find_dictionary_matches_fast) is run on the two lines,
    and each match is shown as the site's card shows it, "word->word" in the surface forms. Both
    scorers' rows are described by this one lookup, sorted, so the column carries no mark of the
    scorer that found the row.
    """
    found = sm._find_dictionary_matches_fast([src_unit], [tgt_unit], "la", "grc").get((0, 0)) or []
    src_tokens = src_unit.get("original_tokens", src_unit.get("tokens", []))
    tgt_tokens = tgt_unit.get("original_tokens", tgt_unit.get("tokens", []))
    shown = set()
    for wm in found:
        si, ti = wm.get("source_indices") or [], wm.get("target_indices") or []
        sw = src_tokens[si[0]] if si and si[0] < len(src_tokens) else wm.get("source_lemma", "")
        tw = tgt_tokens[ti[0]] if ti and ti[0] < len(tgt_tokens) else wm.get("target_lemma", "")
        shown.add(f"{sw}->{tw}")
    return " | ".join(sorted(shown))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir")
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20261017)
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    R.register_language_plugins()
    from backend import passage_index
    passage_index._ensure_loaded()
    sm = R.load_search_module()
    for n_pair, (name, latin, greek) in enumerate(PAIRS, 1):
        union = {}
        units = {}
        for scorer in ("live", "evaluation"):
            rows, su, tu = top_rows(sm, latin, greek, scorer, args.top)
            for u in su:
                units[("s", sm.format_short_locus(u.get("ref", "")))] = u
            for u in tu:
                units[("t", sm.format_short_locus(u.get("ref", "")))] = u
            for rank, row in enumerate(rows, 1):
                key = (row["source"]["ref"], row["target"]["ref"])
                entry = union.setdefault(key, {"row": row, "live": "", "evaluation": ""})
                entry[scorer] = rank
        keys = sorted(union)
        random.Random(args.seed).shuffle(keys)
        with open(out / f"blind_{name}.csv", "w", newline="", encoding="utf-8") as fb, \
                open(out / f"key_{name}.csv", "w", newline="", encoding="utf-8") as fk:
            wb, wk = csv.writer(fb), csv.writer(fk)
            wb.writerow(["row_id", "latin_locus", "latin_text", "greek_locus", "greek_text", "dictionary_pairs"])
            wk.writerow(["row_id", "live_rank", "evaluation_rank", "in_both"])
            for i, key in enumerate(keys, 1):
                e = union[key]
                row = e["row"]
                rid = f"P{n_pair}-{i:03d}"
                wb.writerow([rid, row["source"]["ref"], row["source"]["text"],
                             row["target"]["ref"], row["target"]["text"],
                             word_pairs(sm, units[("s", key[0])], units[("t", key[1])])])
                wk.writerow([rid, e["live"], e["evaluation"], bool(e["live"] and e["evaluation"])])
        n_live = sum(1 for k in keys if union[k]["live"])
        n_ev = sum(1 for k in keys if union[k]["evaluation"])
        n_both = sum(1 for k in keys if union[k]["live"] and union[k]["evaluation"])
        print(f"{name}: {len(keys)} rows in the union ({n_live} live, {n_ev} evaluation, {n_both} in both)", flush=True)


if __name__ == "__main__":
    main()
