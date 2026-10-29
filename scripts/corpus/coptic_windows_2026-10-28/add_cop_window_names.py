# ruff: noqa: E402, E741  (a run-once script: imports follow its path setup)
"""Add window_names rows for the new Coptic windows to a COPY of window_names.db, using build_window_names.py's own
Coptic pass (name set from syntax_coptic.db, tokenizer, names_in_window) unchanged.
usage: add_cop_window_names.py WINDOW_TEXTS_DB LIVE_WINDOW_NAMES_DB OUT_DB WORKS_FILE"""

import os
import sys
import shutil
import sqlite3
import collections
import time

ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, ROOT)
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "corpus"))
import build_window_names as b

b.SYNTAX_COPTIC_DB = "/var/www/tesseraev6_flask/data/inverted_index/syntax_coptic.db"  # the live parse store
wt, live, out_path, works_file = sys.argv[1:5]
works = set(open(works_file).read().split())
t0 = time.time()
cop_names = b.propn_purity_set(
    b.syntax_coptic_pairs(b.SYNTAX_COPTIC_DB, b.normalize_coptic),
    min_total=2,
    min_rate=0.85,
)
print("cop names", len(cop_names), f"{time.time() - t0:.0f}s", flush=True)
con = sqlite3.connect(f"file:{wt}?mode=ro", uri=True)
pairs = {}
for wid, w, text in con.execute(
    "select id, work, text from window_texts where language='cop'"
):
    if w in works:
        orig, norm = b.tokenize_coptic(text)
        pairs[wid] = set(b.names_in_window(orig, norm, cop_names).items())
shutil.copyfile(live, out_path)
out = sqlite3.connect(out_path)
have = {r[0] for r in out.execute("select distinct id from window_names")}
assert not (set(pairs) & have), "a new window already has name rows"
df = collections.Counter()
batch = []
for w, ps in pairs.items():
    for k, form in ps:
        batch.append((w, k, form))
        df[k] += 1
out.executemany("insert into window_names values (?,?,?)", batch)
for k, n in df.items():
    out.execute(
        "insert into name_df values (?,?) on conflict(k) do update set df = df + excluded.df",
        (k, n),
    )
out.execute(
    "update meta set value = ? where key = ?",
    (
        str(
            int(
                out.execute(
                    "select value from meta where key='windows_cop'"
                ).fetchone()[0]
            )
            + len(pairs)
        ),
        "windows_cop",
    ),
)
out.commit()
print(
    "windows",
    len(pairs),
    "rows added",
    len(batch),
    "windows with names",
    len({r[0] for r in batch}),
    "keys",
    len(df),
)
print(collections.Counter(r[0].rsplit(":", 2)[0] for r in batch))
print("integrity", out.execute("pragma integrity_check").fetchone())
