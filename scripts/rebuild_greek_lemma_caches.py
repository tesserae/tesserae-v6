#!/usr/bin/env python3
"""
Rebuild all Greek lemma caches and inverted index with the improved pipeline.

Uses the full lemmatization stack:
  1. 690K-entry lookup table (PTNK + MorphGNT + Rahlfs LXX)
  2. Stanza grc_proiel fallback (97% accuracy on Koine)
  3. CLTK GreekBackoffLemmatizer fallback

Processes all 660+ Greek texts, writes:
  - cache/lemmas/grc/<filename>.json (per-file lemma cache)
  - Updates data/inverted_index/grc_index.db (postings + lines tables)

Run in tmux overnight -- takes 3-4 hours.
"""

import json
import os
import sys
import time
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

TEXTS_DIR = os.path.join(PROJECT_ROOT, 'texts', 'grc')
CACHE_DIR = os.path.join(PROJECT_ROOT, 'cache', 'lemmas', 'grc')
INDEX_DB = os.path.join(PROJECT_ROOT, 'data', 'inverted_index', 'grc_index.db')

def main():
    os.makedirs(CACHE_DIR, exist_ok=True)

    print(f"Loading text processor with full pipeline...")
    from backend.text_processor import TextProcessor
    tp = TextProcessor()
    # Ensure Stanza is NOT skipped for this rebuild
    tp._skip_stanza = False

    all_files = sorted(f for f in os.listdir(TEXTS_DIR) if f.endswith('.tess'))
    print(f"Greek texts to process: {len(all_files)}")
    print(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    conn = sqlite3.connect(INDEX_DB)
    c = conn.cursor()

    start = time.time()
    total_lines = 0
    total_postings = 0
    errors = []

    for i, filename in enumerate(all_files):
        filepath = os.path.join(TEXTS_DIR, filename)
        t0 = time.time()

        try:
            units = tp.process_file(filepath, 'grc', 'line')
        except Exception as e:
            errors.append((filename, str(e)))
            print(f"  [{i+1}/{len(all_files)}] {filename}: ERROR - {e}")
            continue

        # Write lemma cache
        base = filename.replace('.tess', '')
        cache_data = {
            'units_line': units,
        }
        cache_path = os.path.join(CACHE_DIR, f'{filename.replace(".tess", ".json")}')
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False)

        # Update inverted index
        c.execute('SELECT text_id FROM texts WHERE filename = ?', (filename,))
        row = c.fetchone()
        if row:
            text_id = row[0]
            c.execute('DELETE FROM postings WHERE text_id = ?', (text_id,))
            c.execute('DELETE FROM lines WHERE text_id = ?', (text_id,))
        else:
            c.execute('INSERT INTO texts (filename) VALUES (?)', (filename,))
            text_id = c.lastrowid

        posting_count = 0
        for unit in units:
            ref = unit.get('ref', '')
            lemmas = unit.get('lemmas', [])
            tokens = unit.get('tokens', [])
            lemmas_str = json.dumps(lemmas, ensure_ascii=False) if lemmas else ''
            tokens_str = json.dumps(tokens, ensure_ascii=False) if tokens else ''
            c.execute('INSERT OR REPLACE INTO lines (text_id, ref, content, lemmas, tokens) VALUES (?, ?, ?, ?, ?)',
                      (text_id, ref, unit.get('text', ''), lemmas_str, tokens_str))
            seen = set()
            for pos, lemma in enumerate(lemmas):
                if lemma and lemma not in seen:
                    c.execute('INSERT INTO postings (lemma, text_id, ref, positions) VALUES (?, ?, ?, ?)',
                              (lemma, text_id, ref, str(pos)))
                    posting_count += 1
                    seen.add(lemma)

        c.execute('UPDATE texts SET line_count = ? WHERE text_id = ?', (len(units), text_id))

        # Commit every 10 texts to avoid huge transactions
        if (i + 1) % 10 == 0:
            conn.commit()

        elapsed = time.time() - start
        dt = time.time() - t0
        total_lines += len(units)
        total_postings += posting_count
        remaining = (elapsed / (i + 1)) * (len(all_files) - i - 1) / 60

        print(f"  [{i+1}/{len(all_files)}] {filename}: {len(units)} lines, {posting_count} postings ({dt:.1f}s) | {elapsed/60:.1f}m elapsed, ~{remaining:.0f}m remaining")
        sys.stdout.flush()

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Completed: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Texts: {len(all_files)}, Lines: {total_lines}, Postings: {total_postings}")
    print(f"Total time: {(time.time()-start)/60:.1f} minutes")
    if errors:
        print(f"Errors ({len(errors)}):")
        for fn, err in errors:
            print(f"  {fn}: {err}")
    print(f"\nLemma caches written to: {CACHE_DIR}")
    print(f"Index updated: {INDEX_DB}")


if __name__ == '__main__':
    main()
