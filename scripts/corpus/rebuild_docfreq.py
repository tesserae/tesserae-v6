#!/usr/bin/env python3
"""
Rebuild lemma_doc_freq in a working copy of a language's inverted index,
applying the one-document-per-work rule (mirrors backend/bigram_frequency.py
calculate_bigram_frequencies and backend/frequency_cache.py
deduplicate_text_files): a .part. file counts only if the whole-work file
(name before ".part." + ".tess") does NOT exist on disk in texts/<lang>/.

Never touches production. Reads production only via read-only sqlite URIs
and os.path.exists() on the production texts/ directory tree; writes only to
the working-directory copy passed on the command line.
"""
import argparse
import json
import os
import sqlite3
import sys

PROD_ROOT = '/var/www/tesseraev6_flask'
TEXTS_DIR = os.path.join(PROD_ROOT, 'texts')


def counted_text_ids(conn, language):
    """Return (all_text_ids_info, counted_ids_set, skipped_rows) applying the
    one-document-per-work rule to the texts table's filenames, checking whole-
    work existence against the actual texts/<lang>/ directory on disk."""
    lang_dir = os.path.join(TEXTS_DIR, language)
    cur = conn.cursor()
    rows = cur.execute('SELECT text_id, filename FROM texts').fetchall()

    counted = set()
    skipped = []
    for text_id, filename in rows:
        if '.part.' not in filename:
            counted.add(text_id)
            continue
        base = filename.split('.part.')[0]
        whole_path = os.path.join(lang_dir, base + '.tess')
        if os.path.exists(whole_path):
            skipped.append((text_id, filename, base + '.tess'))
        else:
            counted.add(text_id)
    return rows, counted, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('language', choices=['la', 'grc'])
    ap.add_argument('db_path', help='path to the .new working copy to modify')
    ap.add_argument('--out-json', required=True, help='where to write stats JSON')
    args = ap.parse_args()

    language = args.language
    db_path = args.db_path

    if not os.path.exists(db_path):
        print(f"ERROR: {db_path} does not exist", file=sys.stderr)
        sys.exit(1)

    # Read-only connection first, to compute counted ids and before-stats,
    # without touching the file.
    ro = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    rows, counted, skipped = counted_text_ids(ro, language)
    total_texts = len(rows)
    n_counted = len(counted)

    before_count = ro.execute('SELECT COUNT(*) FROM lemma_doc_freq').fetchone()[0]

    # Snapshot ALL before-df values so we can diff after rebuilding (needed to
    # find lemmas that vanish, and to answer the before/after table).
    before_df = dict(ro.execute('SELECT lemma, df FROM lemma_doc_freq').fetchall())
    ro.close()

    # Now open read-write on the working copy and rebuild.
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL')
    cur = conn.cursor()

    placeholders = ','.join(['?'] * len(counted)) if counted else None
    cur.execute('DELETE FROM lemma_doc_freq')
    if counted:
        cur.execute(
            f'INSERT INTO lemma_doc_freq (lemma, df) '
            f'SELECT lemma, COUNT(DISTINCT text_id) FROM postings '
            f'WHERE text_id IN ({placeholders}) GROUP BY lemma',
            list(counted)
        )
    conn.commit()

    after_count = cur.execute('SELECT COUNT(*) FROM lemma_doc_freq').fetchone()[0]
    after_df = dict(cur.execute('SELECT lemma, df FROM lemma_doc_freq').fetchall())

    print(f"[{language}] VACUUM...")
    conn.execute('VACUUM')
    conn.commit()

    integrity = conn.execute('PRAGMA integrity_check').fetchone()[0]
    conn.close()

    # Lemmas that vanished (were in before, not in after): occur only in
    # skipped (uncounted book-part) text_ids.
    vanished_lemmas = sorted(set(before_df) - set(after_df))

    # For up to 10 examples, find one file each lemma came from among the
    # skipped rows (a part file whose whole exists).
    examples = []
    if vanished_lemmas and skipped:
        skipped_ids = [tid for tid, _, _ in skipped]
        skipped_id_to_name = {tid: fn for tid, fn, _ in skipped}
        ro2 = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        cur2 = ro2.cursor()
        for lemma in vanished_lemmas[:10]:
            ph = ','.join(['?'] * len(skipped_ids))
            row = cur2.execute(
                f'SELECT text_id FROM postings WHERE lemma = ? AND text_id IN ({ph}) LIMIT 1',
                [lemma] + skipped_ids
            ).fetchone()
            if row:
                examples.append({'lemma': lemma, 'file': skipped_id_to_name.get(row[0], '?')})
        ro2.close()

    # Also check: are any vanished lemmas NOT explained by skipped rows (i.e.
    # a bug)? Should be zero if postings/texts are consistent.
    unexplained = []
    if vanished_lemmas:
        ro3 = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
        cur3 = ro3.cursor()
        counted_ph = ','.join(['?'] * len(counted)) if counted else None
        for lemma in vanished_lemmas:
            if counted:
                row = cur3.execute(
                    f'SELECT COUNT(*) FROM postings WHERE lemma = ? AND text_id IN ({counted_ph})',
                    [lemma] + list(counted)
                ).fetchone()
                if row[0] > 0:
                    unexplained.append(lemma)
        ro3.close()

    stats = {
        'language': language,
        'total_texts_rows': total_texts,
        'counted_texts': n_counted,
        'skipped_texts': len(skipped),
        'skipped_examples': [{'text_id': t, 'filename': fn, 'whole': w} for t, fn, w in skipped[:20]],
        'lemma_doc_freq_before': before_count,
        'lemma_doc_freq_after': after_count,
        'vanished_lemma_count': len(vanished_lemmas),
        'vanished_examples': examples,
        'unexplained_vanished': unexplained[:20],
        'integrity_check': integrity,
    }
    with open(args.out_json, 'w') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
