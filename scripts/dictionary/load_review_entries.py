#!/usr/bin/env python3
"""Load Greek-Latin pairs into the dictionary_review table under one source name.

The live dictionary reads every row of dictionary_review whose status is
'accepted' at startup (backend/synonym_dict.py, load_accepted_review_entries).
Loading a judged set under one source name means one command removes it again
(--unload SOURCE).

Without --apply this is a dry run: it prints the counts and ten sample rows and
writes nothing. DATABASE_URL comes from the environment only.

Examples (run inside one bash -c that sources the production environment):
  python scripts/dictionary/load_review_entries.py --csv PAIRS.csv \
      --source harvest_2026-10-19_set_a --notes-from VERDICTS.csv
  python scripts/dictionary/load_review_entries.py --csv PAIRS.csv \
      --source harvest_2026-10-19_set_a --notes-from VERDICTS.csv --apply
  python scripts/dictionary/load_review_entries.py --unload harvest_2026-10-19_set_a --apply
"""
import argparse
import csv
import os
import sys
import unicodedata
from datetime import datetime

REVIEWER = 'the project lead (judged harvest)'
NOTES_LIMIT = 500
BATCH_SIZE = 500

INSERT_SQL = (
    "INSERT INTO dictionary_review "
    "(greek_lemma, latin_lemma, source, status, reviewed_by, reviewed_at, notes) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s) "
    "ON CONFLICT (greek_lemma, latin_lemma, source) DO NOTHING"
)
COUNT_SOURCE_SQL = "SELECT COUNT(*) FROM dictionary_review WHERE source = %s"
COUNT_ACCEPTED_SQL = "SELECT COUNT(*) FROM dictionary_review WHERE status = 'accepted'"
UNLOAD_SQL = "DELETE FROM dictionary_review WHERE source = %s"


def normalize_greek(text):
    """The key the live dictionary uses: no accents, lowercase, final sigma as sigma.

    Same two steps as backend/synonym_dict.py (_normalize_greek, then
    replace of final sigma). Idempotent, so the judged CSV (already in key form)
    passes through unchanged.
    """
    nfkd = unicodedata.normalize('NFKD', text.lower())
    stripped = ''.join(c for c in nfkd if not unicodedata.combining(c))
    return stripped.replace('ς', 'σ')


def normalize_latin(text):
    """Latin side as the live dictionary compares it: lowercase, v as u."""
    return text.strip().lower().replace('v', 'u')


def pair_key(greek, latin):
    return normalize_greek(greek.strip()), normalize_latin(latin)


def read_pairs(path):
    """Read greek_lemma and latin_lemma from a CSV, ignoring other columns.

    Returns (rows, duplicates): rows keep file order with within-file
    duplicates (same normalized pair) dropped.
    """
    rows = []
    seen = set()
    duplicates = 0
    with open(path, encoding='utf-8', newline='') as handle:
        for rec in csv.DictReader(handle):
            greek = (rec.get('greek_lemma') or '').strip()
            latin = (rec.get('latin_lemma') or '').strip()
            if not greek or not latin:
                continue
            key = pair_key(greek, latin)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            rows.append((key[0], latin.strip().lower()))
    return rows, duplicates


def read_exclusions(path):
    if not path:
        return set()
    keys = set()
    with open(path, encoding='utf-8', newline='') as handle:
        for rec in csv.DictReader(handle):
            greek = (rec.get('greek_lemma') or '').strip()
            latin = (rec.get('latin_lemma') or '').strip()
            if greek and latin:
                keys.add(pair_key(greek, latin))
    return keys


def build_notes(path):
    """Map normalized pair to 'qwen: V, reason | gpt-oss: V, reason' (500 characters)."""
    notes = {}
    if not path:
        return notes
    with open(path, encoding='utf-8', newline='') as handle:
        for rec in csv.DictReader(handle):
            greek = (rec.get('greek_lemma') or '').strip()
            latin = (rec.get('latin_lemma') or '').strip()
            if not greek or not latin:
                continue
            text = 'qwen: {}, {} | gpt-oss: {}, {}'.format(
                (rec.get('verdict_qwen') or '').strip().lower(),
                (rec.get('reason_qwen') or '').strip(),
                (rec.get('verdict_gptoss') or '').strip().lower(),
                (rec.get('reason_gptoss') or '').strip(),
            )
            notes[pair_key(greek, latin)] = text[:NOTES_LIMIT]
    return notes


def load_curated():
    """The curated Greek-Latin dictionary exactly as the app builds it."""
    from backend.synonym_dict import CURATED_GREEK_LATIN
    return CURATED_GREEK_LATIN


def in_curated(curated, greek_key, latin_key):
    words = curated.get(greek_key)
    return bool(words) and latin_key in {w.replace('v', 'u') for w in words}


def plan(rows, exclusions, curated):
    """Split rows into those to insert, excluded and already curated."""
    to_insert, excluded, already = [], 0, 0
    for greek, latin in rows:
        key = pair_key(greek, latin)
        if key in exclusions:
            excluded += 1
        elif in_curated(curated, key[0], key[1]):
            already += 1
        else:
            to_insert.append((greek, latin))
    return to_insert, excluded, already


def _scalar(cur, sql, params=None):
    cur.execute(sql, params) if params is not None else cur.execute(sql)
    return cur.fetchone()[0]


def apply_load(conn, to_insert, source, notes, status, now=None, batch_size=BATCH_SIZE):
    """Insert in batches inside one transaction. Returns (inserted, skipped, before, after)."""
    now = now or datetime.now()
    cur = conn.cursor()
    try:
        before = _scalar(cur, COUNT_ACCEPTED_SQL)
        source_before = _scalar(cur, COUNT_SOURCE_SQL, (source,))
        for start in range(0, len(to_insert), batch_size):
            for greek, latin in to_insert[start:start + batch_size]:
                note = notes.get(pair_key(greek, latin))
                cur.execute(INSERT_SQL, (greek, latin, source, status, REVIEWER, now, note))
        source_after = _scalar(cur, COUNT_SOURCE_SQL, (source,))
        after = _scalar(cur, COUNT_ACCEPTED_SQL)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    inserted = source_after - source_before
    return inserted, len(to_insert) - inserted, before, after


def unload(conn, source):
    cur = conn.cursor()
    try:
        before = _scalar(cur, COUNT_ACCEPTED_SQL)
        cur.execute(UNLOAD_SQL, (source,))
        deleted = cur.rowcount
        after = _scalar(cur, COUNT_ACCEPTED_SQL)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return deleted, before, after


def connect():
    url = os.environ.get('DATABASE_URL')
    if not url:
        sys.exit('DATABASE_URL is not set. Source the production environment first.')
    import psycopg2
    return psycopg2.connect(url)


def main(argv=None, connect_fn=None, curated=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--csv', help='CSV with columns greek_lemma and latin_lemma (required unless --unload)')
    ap.add_argument('--source')
    ap.add_argument('--exclude')
    ap.add_argument('--notes-from')
    ap.add_argument('--status', default='accepted')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--unload', metavar='SOURCE')
    args = ap.parse_args(argv)
    connect_fn = connect_fn or connect

    if args.unload:
        if not os.environ.get('DATABASE_URL'):
            sys.exit('DATABASE_URL is not set. Source the production environment first.')
        if not args.apply:
            print('Dry run: --unload {} would delete every row of that source. Add --apply.'.format(args.unload))
            return 0
        conn = connect_fn()
        deleted, before, after = unload(conn, args.unload)
        print('Deleted {} rows of source {}. Accepted rows: {} before, {} after.'.format(
            deleted, args.unload, before, after))
        print('Next: delete cache/asyncjob_xlingual_*.json and touch the wsgi file.')
        return 0

    if not args.csv:
        ap.error('--csv is required')
    if not args.source:
        ap.error('--source is required')
    if not os.environ.get('DATABASE_URL'):
        sys.exit('DATABASE_URL is not set. Source the production environment first.')

    rows, duplicates = read_pairs(args.csv)
    exclusions = read_exclusions(args.exclude)
    notes = build_notes(args.notes_from)
    curated = curated if curated is not None else load_curated()
    to_insert, excluded, already = plan(rows, exclusions, curated)

    print('Rows in CSV after dropping {} duplicates within the file: {}'.format(duplicates, len(rows)))
    print('Excluded by --exclude: {}'.format(excluded))
    print('Already in the curated dictionary (skipped): {}'.format(already))
    print('To insert under source {} with status {}: {}'.format(args.source, args.status, len(to_insert)))

    if not args.apply:
        for greek, latin in to_insert[:10]:
            print('  {} -> {} | {}'.format(greek, latin, (notes.get(pair_key(greek, latin)) or '')[:100]))
        print('Dry run. Nothing written. Add --apply to load.')
        return 0

    conn = connect_fn()
    inserted, skipped, before, after = apply_load(conn, to_insert, args.source, notes, args.status)
    print('Inserted: {}'.format(inserted))
    print('Skipped as duplicates already in the table: {}'.format(skipped))
    print('Excluded: {}'.format(excluded))
    print('Accepted rows in the table: {} before, {} after.'.format(before, after))
    print('Next: delete cache/asyncjob_xlingual_*.json and touch the wsgi file.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
