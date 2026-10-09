#!/usr/bin/env python3
"""Stream the Pleiades places dump and write a TSV of id, lat, lon, title.

Usage: pleiades_points.py DUMP.json.gz OUT.tsv
Streams with ijson (a plain json.load peaks near 16 GB). Uses reprPoint where
present, else the centre of bbox.
"""
import gzip, sys
import ijson


def main(src, out):
    n = kept = 0
    with gzip.open(src, "rb") as f, open(out, "w", encoding="utf-8") as o:
        o.write("pleiades_id\tlat\tlon\ttitle\n")
        for p in ijson.items(f, "@graph.item"):
            n += 1
            pt = p.get("reprPoint")
            if not pt and p.get("bbox"):
                b = p["bbox"]
                pt = [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2]
            if not pt:
                continue
            kept += 1
            o.write(f"{p['id']}\t{float(pt[1]):.5f}\t{float(pt[0]):.5f}\t{(p.get('title') or '').replace(chr(9), ' ')}\n")
    print("places", n, "with point", kept)


if __name__ == "__main__":
    main(*sys.argv[1:3])
