#!/usr/bin/env python3
"""Build the Theme Search word index: SQLite FTS5 (BM25) over every passage
description, keyed by the window id (the embedding row is looked up from
the id at query time, since descriptions.jsonl is not in embedding order).

Theme Search adds a small lexical boost from this index to the embedding
similarity (backend/passage_index.py, LEXICAL_BETA): measured 2026-09-20 on
the 16-query benchmark, first-ten precision 0.434 -> 0.506 (docs/DECISIONS.md).

REBUILD after every change to descriptions.jsonl (imports, retirements,
description rebuilds); the app checks the row count and refuses to use a
stale index. About three minutes, under 1 GB:

    ~/bin/tess-job --fg desc-fts 4 ./venv/bin/python3 scripts/build_desc_fts.py

Writes desc_fts.sqlite.tmp beside descriptions.jsonl and renames it over
desc_fts.sqlite when complete, so the live app never reads a half-written file.
"""
import argparse
import json
import os
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_SRC = os.path.join(ROOT, 'data', 'passage_index', 'descriptions.jsonl')


def flat(v):
    if isinstance(v, list):
        return ' '.join(str(x) for x in v if x)
    return str(v) if v else ''


def description_text(record):
    d = record.get('desc') or {}
    parts = [flat(d.get('gist')), flat(d.get('themes')), flat(d.get('action_steps')),
             flat(d.get('participants')), flat(d.get('setting'))]
    return ' '.join(p for p in parts if p)


def build(src, out):
    tmp = out + '.tmp'
    if os.path.exists(tmp):
        os.remove(tmp)
    conn = sqlite3.connect(tmp)
    conn.execute("CREATE VIRTUAL TABLE desc USING fts5(id UNINDEXED, text, tokenize='porter unicode61')")
    conn.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
    t0 = time.time()
    n = 0
    batch = []
    with open(src, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            batch.append((record.get('id'), description_text(record)))
            if len(batch) >= 20000:
                conn.executemany('INSERT INTO desc VALUES (?, ?)', batch)
                n += len(batch)
                batch = []
    if batch:
        conn.executemany('INSERT INTO desc VALUES (?, ?)', batch)
        n += len(batch)
    conn.execute("INSERT INTO meta VALUES ('rows', ?)", (str(n),))
    conn.execute("INSERT INTO meta VALUES ('source', ?)", (os.path.abspath(src),))
    conn.execute("INSERT INTO meta VALUES ('built_at', ?)", (time.strftime('%Y-%m-%dT%H:%M:%S'),))
    conn.commit()
    conn.execute("INSERT INTO desc(desc) VALUES('optimize')")
    conn.commit()
    conn.close()
    os.replace(tmp, out)
    return n, time.time() - t0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--source', default=DEFAULT_SRC)
    ap.add_argument('--out', default=None, help='default: desc_fts.sqlite beside the source')
    args = ap.parse_args()
    out = args.out or os.path.join(os.path.dirname(args.source), 'desc_fts.sqlite')
    n, secs = build(args.source, out)
    print(f'{n} descriptions indexed in {secs:.0f}s -> {out} ({os.path.getsize(out) / 1e6:.0f} MB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
