# ruff: noqa: E402, E741  (a run-once script: imports follow its path setup)
"""Write the new windows (windows.jsonl) and the per-line rows of their works into a COPY of window_texts.db with
build_batch_windows.upsert. usage: upsert_texts.py WINDOWS_JSONL DB"""

import json
import sys
import os
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_batch_windows as BW
from works import GAPS

wins = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
db = sys.argv[2]
BW.upsert(db, wins, [f"/var/www/tesseraev6_flask/texts/cop/{w}.tess" for w in GAPS])
c = sqlite3.connect(db)
print(
    "after windows, lines:",
    c.execute("select count(*) from window_texts").fetchone()[0],
    c.execute("select count(*) from lines").fetchone()[0],
)
print("integrity", c.execute("pragma integrity_check").fetchone())
