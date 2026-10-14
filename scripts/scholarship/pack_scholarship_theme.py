"""Pack the scholarship Theme Search index for the site.

Reads the index built by build_scholarship_theme_index.py (embeddings.npy,
ids.json, descriptions.jsonl) and writes the four files the route
backend/scholarship_theme.py opens, into --out:

    embeddings.npy   float16, rows in ids.json order, each row unit length
    ids.json         the window ids, row order
    windows.jsonl    one line per window, in row order, reduced to what the
                     route needs: id, source, language, work, work_language,
                     ref_start, ref_end, commentator, journal, title, authors,
                     year, url, text
    windows_fts.db   SQLite, FTS5 table `f` (body, id UNINDEXED), rowid = row.
                     The body is the text of the prototype's keyword search
                     (commentator, work, reference, then the note), so the
                     ranking measured in the evaluation is the ranking served.
    manifest.json    row count and file sizes

Article windows (source `ejc`, ids ejc:<citation id>:<piece>) take journal,
title, authors, year and link from the citation index. The language of each
work (the language folder holding its text) is looked up in the texts folder, so
the route can build a Reader link without searching at request time. Both are
only read.

    python scripts/scholarship/pack_scholarship_theme.py --index DIR --out DIR2
"""
import argparse
import json
import os
import sqlite3
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
PROD = '/var/www/tesseraev6_flask'


def work_languages(texts_dir):
    """{work or base work: language folder} from the .tess files under texts/<lang>/."""
    from backend.work_names import base_work
    full, base = {}, {}
    for lang in sorted(os.listdir(texts_dir)):
        d = os.path.join(texts_dir, lang)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith('.tess'):
                stem = f[:-5]
                full.setdefault(stem, lang)
                base.setdefault(base_work(stem), lang)
    return full, base


def language_of(work, full, base):
    return full.get(work) or base.get(work)


def article_meta(citations_db, cids):
    """{citation id: (journal, title, authors, year, link)} for the ids asked."""
    out = {}
    if not citations_db or not os.path.exists(citations_db) or not cids:
        return out
    con = sqlite3.connect(f'file:{citations_db}?mode=ro', uri=True)
    try:
        ids = sorted(cids)
        for i in range(0, len(ids), 500):
            part = ids[i:i + 500]
            q = ('SELECT c.id, a.journal, a.title, a.authors, a.year, a.url_jstor, a.url_ia '
                 'FROM citations c JOIN articles a ON a.id = c.article_id '
                 f'WHERE c.id IN ({",".join("?" * len(part))})')  # nosec B608 -- placeholders only
            for cid, journal, title, authors, year, jstor, ia in con.execute(q, part):
                out[cid] = (journal, title, authors, year, jstor or ia)
    finally:
        con.close()
    return out


def cid_of(wid):
    """The citation id in an article window id (ejc:<cid>:<piece>), else None."""
    parts = str(wid).split(':')
    if len(parts) == 3 and parts[0] == 'ejc' and parts[1].isdigit():
        return int(parts[1])
    return None


def fts_body(rec):
    work = (rec.get('work') or '').replace('.', ' ').replace('_', ' ')
    return f"{rec.get('commentator') or ''} {work} {rec.get('ref_start') or ''} {rec['text']}"


def read_descriptions(path):
    recs = {}
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            r = json.loads(line)
            recs[r['id']] = r
    return recs


def pack(index, out, citations_db=None, texts_dir=None):
    ids = json.load(open(os.path.join(index, 'ids.json'), encoding='utf-8'))
    emb = np.load(os.path.join(index, 'embeddings.npy'), mmap_mode='r')
    if emb.shape[0] != len(ids):
        raise SystemExit(f'embeddings.npy has {emb.shape[0]} rows, ids.json has {len(ids)}')
    recs = read_descriptions(os.path.join(index, 'descriptions.jsonl'))
    missing = [i for i in ids if i not in recs]
    if missing:
        raise SystemExit(f'{len(missing)} ids have no description, first {missing[0]}')
    full, base = work_languages(texts_dir) if texts_dir and os.path.isdir(texts_dir) else ({}, {})
    meta = article_meta(citations_db, {c for c in (cid_of(i) for i in ids) if c is not None})

    os.makedirs(out, exist_ok=True)
    tmp = {n: os.path.join(out, n + '.tmp') for n in
           ('embeddings.npy', 'ids.json', 'windows.jsonl', 'windows_fts.db', 'manifest.json')}
    for p in tmp.values():
        if os.path.exists(p):
            os.remove(p)

    # Embeddings: unit rows in float16, written in chunks so memory stays small.
    dst = np.lib.format.open_memmap(tmp['embeddings.npy'], mode='w+', dtype=np.float16, shape=emb.shape)
    for i in range(0, emb.shape[0], 8192):
        blk = np.asarray(emb[i:i + 8192], dtype=np.float32)
        n = np.linalg.norm(blk, axis=1, keepdims=True)
        n[n == 0] = 1.0
        dst[i:i + 8192] = (blk / n).astype(np.float16)
    dst.flush()
    del dst
    with open(tmp['ids.json'], 'w', encoding='utf-8') as fh:
        json.dump(ids, fh)

    con = sqlite3.connect(tmp['windows_fts.db'])
    con.execute("CREATE VIRTUAL TABLE f USING fts5(body, id UNINDEXED, tokenize='porter unicode61')")
    batch, with_article, with_lang = [], 0, 0
    with open(tmp['windows.jsonl'], 'w', encoding='utf-8') as fh:
        for row, wid in enumerate(ids):
            r = recs[wid]
            cid = cid_of(wid)
            journal = title = authors = year = url = None
            if cid is not None and cid in meta:
                journal, title, authors, year, url = meta[cid]
                with_article += 1
            lang = language_of(r.get('work') or '', full, base)
            with_lang += 1 if lang else 0
            w = {'id': wid, 'source': r['source'], 'language': r.get('language'), 'work': r.get('work') or '',
                 'work_language': lang, 'ref_start': r.get('ref_start'), 'ref_end': r.get('ref_end'),
                 'commentator': r.get('commentator'), 'journal': journal, 'title': title, 'authors': authors,
                 'year': year, 'url': url, 'text': r['desc']['gist']}
            fh.write(json.dumps(w, ensure_ascii=False) + '\n')
            batch.append((row, fts_body(w), wid))
            if len(batch) >= 5000:
                con.executemany('INSERT INTO f(rowid, body, id) VALUES (?,?,?)', batch)
                batch = []
    if batch:
        con.executemany('INSERT INTO f(rowid, body, id) VALUES (?,?,?)', batch)
    con.commit()
    con.execute("INSERT INTO f(f) VALUES ('optimize')")
    con.commit()
    con.close()

    sizes = {n: os.path.getsize(os.path.join(out, n + '.tmp')) for n in
             ('embeddings.npy', 'ids.json', 'windows.jsonl', 'windows_fts.db')}
    manifest = {'rows': len(ids), 'dim': int(emb.shape[1]), 'dtype': 'float16', 'sizes': sizes,
                'article_windows_with_metadata': with_article, 'windows_with_work_language': with_lang}
    with open(tmp['manifest.json'], 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=1)
    for name, p in tmp.items():
        os.replace(p, os.path.join(out, name))
    return manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--index', required=True, help='the built index folder (read only)')
    ap.add_argument('--out', required=True, help='where the packed files go')
    ap.add_argument('--citations', default=os.path.join(PROD, 'data', 'citation_index', 'citations.db'))
    ap.add_argument('--texts', default=os.path.join(PROD, 'texts'))
    a = ap.parse_args()
    m = pack(a.index, a.out, a.citations, a.texts)
    print(json.dumps(m, indent=1))
    for n, s in m['sizes'].items():
        print(f'{n:18s} {s / 1e6:10.1f} MB')


if __name__ == '__main__':
    main()
