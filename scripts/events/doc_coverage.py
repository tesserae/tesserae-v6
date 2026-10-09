#!/usr/bin/env python3
"""How many Wikidata events reach at least one document (+-10 years, within 100 km), by era.

Usage: doc_coverage.py EVENTS COUNTRIES PLEIADES_POINTS OUT.json
"""
import json, sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_event_dossier as b  # noqa: E402


def main(events, countries, pleiades, out):
    ev, co = b.load_jsonl(events), b.load_jsonl(countries)
    points, cw = b.load_points(pleiades), b.load_crosswalk()
    prod = b.Prod()
    eras = [(-800, -301, "800-301 BC"), (-300, -31, "300-31 BC"), (-30, 300, "30 BC-AD 300"), (301, 600, "AD 301-600")]
    stat = collections.defaultdict(lambda: collections.Counter())
    for rec in ev.values():
        span = b.event_span(rec)
        if not span:
            continue
        era = next(l for lo, hi, l in eras if lo <= span[0] <= hi) if any(lo <= span[0] <= hi for lo, hi, _ in eras) else "other"
        locs = b.specific_locations(rec, co)
        centres = []
        for l in locs:
            if l.get("pleiades") and l["pleiades"] in points:
                centres.append(points[l["pleiades"]][:2])
            elif l.get("coord") and b.parse_point(l["coord"]):
                centres.append(b.parse_point(l["coord"]))
        s = stat[era]
        s["events"] += 1
        s["with_centre"] += bool(centres)
        if centres:
            d = b.documents(prod, span, centres, points, cw, sample_cap=0)
            s["with_1plus_doc_100km"] += d["n"] > 0
            s["with_10plus_doc_100km"] += d["n"] >= 10
            s["with_1plus_narrow_dated"] += d["n_dated_within_50_years"] > 0
    json.dump(stat, open(out, "w"), indent=1)
    for k, v in stat.items():
        print(k, dict(v))


if __name__ == "__main__":
    main(*sys.argv[1:5])
