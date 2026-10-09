#!/usr/bin/env python3
"""Leave-one-out recall of the co-citation boost.

Usage: eval_cocitation.py EVENTS LABELS COUNTRIES SAMPLE INTROS [matching] [lemma_dir]
For each hand-listed passage X of an event, the seeds are the OTHER hand-listed passages of that
event, the co-citation list is built from them, and the rank of X is read off the 'fused' ranking
(names + Theme Search) and the 'fused3' ranking (names + Theme Search + co-citation). Also prints,
per event, how many citation-index pages cite the seeds and how many co-cited loci result.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_event_dossier as b  # noqa: E402


def best_rank(ranked, work, lo, hi):
    return next((i for i, x in enumerate(ranked, 1) if x["work"] == work and b.loci_overlap(lo, hi, tuple(x["lo"]), tuple(x["hi"]))), None)


def main(events, labels, countries, sample, intros, matching="form", lemma_dir=None):
    b.MATCHING, b.LEMMA_DIR = matching, lemma_dir
    ev, lab, co = b.load_jsonl(events), b.load_jsonl(labels), b.load_jsonl(countries)
    intros = json.load(open(intros))
    prod, theme = b.Prod(), b.Theme()
    tot = {"fused": [0, 0, 0], "fused3": [0, 0, 0]}
    n_cov = 0
    for s in json.load(open(sample))["events"]:
        rec = ev[s["qid"]]
        span = b.event_span(rec)
        ents = b.build_entities(rec, lab, co, s.get("curated_names", []))
        theme.prepare(intros[s["key"]]["query"])
        hl = [(p["work"], p["lo"], p["hi"]) for p in b.hand_passages(s)]
        full = CoCite = b.CoCite(prod, hl)
        cov = len(full.pages)
        n_cov += cov > 0
        row = {}
        for mode in ("fused", "fused3"):
            r20 = r100 = ra = 0
            for i, (w, lo, hi) in enumerate(hl):
                seeds = hl[:i] + hl[i + 1:]
                lit = b.literary(prod, ents, span, limit=1, ranking=mode, theme=theme, seeds=seeds)
                k = best_rank(lit["all_ranked"], w, lo, hi)
                r20 += k is not None and k <= 20
                r100 += k is not None and k <= 100
                ra += k is not None
            row[mode] = (r20, r100, ra)
            for j in range(3):
                tot[mode][j] += (r20, r100, ra)[j]
        print(f"{s['key']:22s} passages {len(hl)} seed-pages(all) {cov:3d} co-cited loci {full.n_loci:4d}  fused {row['fused']}  fused3 {row['fused3']}", flush=True)
    print("events with citation pages for the seeds:", n_cov, "of 12")
    print("TOTAL leave-one-out (top20, top100, anywhere):", tot)


if __name__ == "__main__":
    main(*sys.argv[1:8])
