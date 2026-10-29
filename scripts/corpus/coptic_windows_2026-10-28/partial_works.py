#!/usr/bin/env python3
"""List Coptic works already in the window store whose regenerated windows are not all present."""

import sqlite3
import sys

sys.path.insert(0, "/home/ncoffee/wt-copticwin/scripts/corpus")
import build_batch_windows as BW

P = "/var/www/tesseraev6_flask"
con = sqlite3.connect(f"file:{P}/data/passage_index/window_texts.db?mode=ro", uri=True)
live = {}
for i, w in con.execute("select id, work from window_texts where language='cop'"):
    live.setdefault(w, set()).add(i)
tot = 0
for w in sorted(live):
    new = BW.windows_for(f"{P}/texts/cop/{w}.tess", "cop", {}, {}, 0)
    ids = {x["id"] for x in new}
    miss, extra = ids - live[w], live[w] - ids
    if miss or extra:
        tot += len(miss)
        print(
            w,
            "regenerated",
            len(ids),
            "live",
            len(live[w]),
            "missing",
            len(miss),
            "live-only",
            len(extra),
        )
print("works partial; total missing", tot)
