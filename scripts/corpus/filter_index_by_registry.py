#!/usr/bin/env python3
"""Remove every restricted work from a COPY of an inverted index (for a public download).

Reads data/restricted_texts.json, finds each row of `texts` whose filename
belongs to a registered work (by backend.work_names.base_work, as
remove_restricted_text.py does), deletes its rows from `lines` and `postings`
and `texts`, recomputes `lemma_doc_freq` if the index has it, then VACUUMs.
It works in place on the path it is given, so always give it a copy, never
the live index. Prints a JSON report of the counts before and after.

    venv/bin/python scripts/corpus/filter_index_by_registry.py COPY.db [--ids a,b]
"""
import argparse
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from backend.work_names import base_work  # noqa: E402


def counts(con):
    out = {}
    for table in ('texts', 'lines', 'postings', 'lemma_doc_freq'):
        if con.execute("select 1 from sqlite_master where type='table' and name=?", (table,)).fetchone():
            out[table] = con.execute(f'select count(*) from {table}').fetchone()[0]  # nosec B608
    return out


def filter_index(db_path, ids):
    con = sqlite3.connect(db_path)
    before = counts(con)
    rows = con.execute('select text_id, filename from texts').fetchall()
    drop = [t for t, f in rows if f.endswith('.tess') and base_work(f[:-len('.tess')]) in ids]
    marks = ','.join('?' * len(drop))
    if drop:
        for table in ('lines', 'postings', 'texts'):
            con.execute(f'delete from {table} where text_id in ({marks})', drop)  # nosec B608
    if 'lemma_doc_freq' in before:
        con.execute('delete from lemma_doc_freq')
        con.execute('insert into lemma_doc_freq select lemma, count(distinct text_id) from postings group by lemma')
    con.commit()
    assert con.execute('pragma integrity_check').fetchone()[0] == 'ok'
    after_vacuum_free = con.execute('pragma freelist_count').fetchone()[0]
    con.execute('VACUUM')
    after = counts(con)
    con.close()
    return {'texts_removed': len(drop), 'before': before, 'after': after,
            'freelist_pages_before_vacuum': after_vacuum_free}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('db')
    ap.add_argument('--ids', help='comma list; default is every id in data/restricted_texts.json')
    args = ap.parse_args()
    if args.ids:
        ids = set(args.ids.split(','))
    else:
        with open(os.path.join(ROOT, 'data', 'restricted_texts.json'), encoding='utf-8') as f:
            ids = set(json.load(f)['texts'])
    print(json.dumps(filter_index(args.db, ids), indent=1))


if __name__ == '__main__':
    main()
