#!/usr/bin/env python3
"""Incrementally add or replace texts in an inverted-index COPY.

Written for Latin corpus batch 2 (2026-08-30), replacing the ad-hoc driver
batch 1 ran from a scratchpad that no longer exists. The pattern is the
batch-1 one:

  - never touch the live index: work on a copy, atomic-swap afterwards
    (cp live -> copy; run this; mv live live.bak; mv copy live)
  - rows come FROM the lemma cache (cache/lemmas/<lang>/<work>.json),
    the same lemmatization the server uses, not a re-lemmatization
  - lemma_doc_freq is rebuilt at the end via build_inverted_index's own
    builder, so doc-freq stays in step with the postings

Usage:
  python add_texts_to_index.py --db /path/la_index.db.new --language la \
      --cache-dir /var/www/tesseraev6_flask/cache/lemmas \
      --add justin.epitome.tess --replace lactantius_placidus.x.tess ...

--add fails if the filename is already in texts; --replace requires it,
keeps the text_id, and swaps the postings/lines rows in one transaction.
"""
import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load_units(cache_dir, language, filename):
    import hashlib
    import unicodedata
    base = filename[:-5] if filename.endswith('.tess') else filename
    # the cache's canonical name is ASCII-hint + md5(text_id) (see
    # backend/lemma_cache.get_cache_path); the bare-stem name is legacy
    norm = unicodedata.normalize('NFC', filename)
    digest = hashlib.md5(norm.encode('utf-8')).hexdigest()  # nosec B324
    hint = ''.join(c if c.isalnum() or c in '._-' else '_'
                   for c in base if ord(c) < 128).strip('._-') or 'text'
    path = os.path.join(cache_dir, language, f'{hint[:64]}-{digest}.json')
    if not os.path.exists(path):
        path = os.path.join(cache_dir, language, base + '.json')
    if not os.path.exists(path):
        raise SystemExit(f'no lemma cache entry for {filename} in '
                         f'{cache_dir}/{language}')
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    units = data['units_line']
    if not units:
        raise SystemExit(f'empty units_line in {path}')
    return units


def insert_rows(cur, text_id, units):
    n_postings = 0
    for unit in units:
        ref = unit.get('ref', '')
        lemmas = unit.get('lemmas', [])
        tokens = unit.get('tokens', [])
        positions = {}
        for pos, lemma in enumerate(lemmas):
            positions.setdefault(lemma, []).append(pos)
        for lemma, plist in positions.items():
            cur.execute('INSERT INTO postings (lemma, text_id, ref, positions) '
                        'VALUES (?, ?, ?, ?)',
                        (lemma, text_id, ref, json.dumps(plist)))
            n_postings += 1
        cur.execute('INSERT OR IGNORE INTO lines '
                    '(text_id, ref, content, lemmas, tokens) VALUES (?, ?, ?, ?, ?)',
                    (text_id, ref, unit.get('text', ''),
                     json.dumps(lemmas), json.dumps(tokens)))
    return n_postings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', required=True, help='index COPY to modify')
    ap.add_argument('--language', required=True)
    ap.add_argument('--cache-dir', required=True)
    ap.add_argument('--add', nargs='*', default=[])
    ap.add_argument('--replace', nargs='*', default=[])
    args = ap.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f'no such db: {args.db} (copy the live index first)')
    conn = sqlite3.connect(args.db)
    cur = conn.cursor()

    for filename in args.add:
        row = cur.execute('SELECT text_id FROM texts WHERE filename = ?',
                          (filename,)).fetchone()
        if row:
            raise SystemExit(f'{filename} already indexed (text_id {row[0]}); '
                             'use --replace')
        units = load_units(args.cache_dir, args.language, filename)
        parts = filename.replace('.tess', '').split('.')
        cur.execute('INSERT INTO texts (filename, author, title, line_count) '
                    'VALUES (?, ?, ?, ?)',
                    (filename, parts[0], '.'.join(parts[1:]), len(units)))
        text_id = cur.lastrowid
        n = insert_rows(cur, text_id, units)
        conn.commit()
        print(f'added {filename}: text_id {text_id}, {len(units)} lines, {n} postings')

    for filename in args.replace:
        row = cur.execute('SELECT text_id FROM texts WHERE filename = ?',
                          (filename,)).fetchone()
        if not row:
            raise SystemExit(f'{filename} not indexed; use --add')
        text_id = row[0]
        units = load_units(args.cache_dir, args.language, filename)
        old_p = cur.execute('SELECT COUNT(*) FROM postings WHERE text_id = ?',
                            (text_id,)).fetchone()[0]
        cur.execute('DELETE FROM postings WHERE text_id = ?', (text_id,))
        cur.execute('DELETE FROM lines WHERE text_id = ?', (text_id,))
        cur.execute('UPDATE texts SET line_count = ? WHERE text_id = ?',
                    (len(units), text_id))
        n = insert_rows(cur, text_id, units)
        conn.commit()
        print(f'replaced {filename}: text_id {text_id}, {len(units)} lines, '
              f'{n} postings (was {old_p})')

    from scripts.build_inverted_index import build_lemma_doc_freq
    build_lemma_doc_freq(conn)
    conn.commit()
    n_texts, n_lines = cur.execute(
        'SELECT COUNT(*), (SELECT COUNT(*) FROM lines) FROM texts').fetchone()
    print(f'done: {n_texts} texts, {n_lines} lines, lemma_doc_freq rebuilt')
    conn.close()


if __name__ == '__main__':
    main()
