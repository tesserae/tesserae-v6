#!/usr/bin/env python3
"""Write stories.json and old_to_new_refs.json for the restructured Shahnameh.

stories.json: one entry per Ganjoor story in the source's order: number, Persian title, English
title (Warner's heading when one Persian story matches one Warner section, otherwise a plain
translation of the Persian title, kept in titles_en_*.json), the reign it sits under, the new
reference of its first and last line, the old running numbers it covers, and how it was matched.

Usage: build_stories_json.py WORKDIR OUTDIR
"""

import json
import sys
import glob
import collections

base, out = sys.argv[1], sys.argv[2]
st = json.load(open(base + "/stories_raw.json"))
W = json.load(open(base + "/warner_stories.json"))
T = json.load(open(base + "/match_table.json"))
prep = json.load(open(base + "/titles_prep.json"))
man = {}
import os  # noqa: E402

for f in sorted(
    glob.glob(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "titles_en", "titles_en_*.json"
        )
    )
):
    man.update(json.load(open(f)))
o2n = json.load(open(base + "/old_to_new_refs.json"))
first = {}
last = {}
for old, new in o2n.items():
    s = int(new.split(".")[2])
    n = int(old)
    first[s] = min(first.get(s, n), n)
    last[s] = max(last.get(s, n), n)
grp = {}
for g in T:
    for s in g["stories"]:
        grp[s] = g
rows = []
for s in st:
    n = s["number"]
    g = grp.get(n)
    if str(n) in prep["ok"]:
        en, src = prep["ok"][str(n)], "Warner heading"
    else:
        en, src = man[str(n)], "translated from the Persian title"
    status = g["status"] if g else "unmatched"
    rows.append(
        {
            "number": n,
            "title_fa": s["title_fa"],
            "title_en": en,
            "title_en_source": src,
            "reign_fa": s["reign_title_fa"],
            "n_couplets": s["n_couplets"],
            "first_ref": f"ferdowsi.shahnameh.{n}.1.1",
            "last_ref": f"ferdowsi.shahnameh.{n}.{s['n_couplets']}.2",
            "first_couplet": 1,
            "last_couplet": s["n_couplets"],
            "old_first": first[n],
            "old_last": last[n],
            "ganjoor_poem_id": s["poem_id"],
            "warner_match": status,
            "warner_sections": [
                {"volume": W[i - 1]["vol"], "heading": W[i - 1]["title"][:90]}
                for i in (g["warner"] if g else [])
            ],
        }
    )
json.dump(rows, open(out + "/stories.json", "w"), ensure_ascii=False, indent=1)
json.dump(
    o2n,
    open(out + "/old_to_new_refs.json", "w"),
    ensure_ascii=False,
    separators=(",", ":"),
)
print(len(rows), "stories", collections.Counter(r["title_en_source"] for r in rows))
