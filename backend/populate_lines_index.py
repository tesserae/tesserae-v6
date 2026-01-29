#!/usr/bin/env python3
"""
Populate the lines table in the inverted index for faster line searches.
This stores text content and lemmas directly in the index, eliminating
the need to load files during search.

Run: python backend/populate_lines_index.py [language]
"""
import os
import sys
import json
import sqlite3
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.inverted_index import INDEX_DIR, ensure_lines_table
from backend.text_processor import TextProcessor

TEXTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')

def populate_lines(language='la', batch_size=100):
    """Populate the lines table for a language"""
    db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
    
    if not os.path.exists(db_path):
        print(f"Index not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lines (
            text_id INTEGER,
            ref TEXT,
            content TEXT,
            lemmas TEXT,
            tokens TEXT,
            PRIMARY KEY (text_id, ref),
            FOREIGN KEY (text_id) REFERENCES texts(text_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lines_text_ref ON lines(text_id, ref)')
    conn.commit()
    
    cursor.execute('SELECT COUNT(*) FROM lines')
    existing = cursor.fetchone()[0]
    if existing > 0:
        print(f"Lines table already has {existing:,} entries - clearing and rebuilding...")
        cursor.execute('DELETE FROM lines')
        conn.commit()
        print("Cleared existing entries")
    
    cursor.execute('SELECT text_id, filename FROM texts ORDER BY text_id')
    texts = cursor.fetchall()
    
    print(f"Processing {len(texts)} texts for {language}...")
    
    text_processor = TextProcessor()
    total_lines = 0
    start_time = time.time()
    
    for i, (text_id, filename) in enumerate(texts):
        filepath = os.path.join(TEXTS_DIR, language, filename)
        
        if not os.path.exists(filepath):
            print(f"  Skipping {filename} (file not found)")
            continue
        
        try:
            units = text_processor.process_file(filepath, language, 'line')
            
            batch = []
            for unit in units:
                ref = unit.get('ref', '')
                content = unit.get('text', '')
                lemmas = json.dumps(unit.get('lemmas', []))
                tokens = json.dumps(unit.get('tokens', []))
                batch.append((text_id, ref, content, lemmas, tokens))
            
            cursor.executemany(
                'INSERT OR REPLACE INTO lines (text_id, ref, content, lemmas, tokens) VALUES (?, ?, ?, ?, ?)',
                batch
            )
            
            total_lines += len(batch)
            
            if (i + 1) % 10 == 0:
                conn.commit()
                elapsed = time.time() - start_time
                rate = total_lines / elapsed if elapsed > 0 else 0
                print(f"  [{i+1}/{len(texts)}] {filename}: {len(batch)} lines ({total_lines:,} total, {rate:.0f} lines/sec)")
                
        except Exception as e:
            print(f"  Error processing {filename}: {e}")
    
    conn.commit()
    conn.close()
    
    elapsed = time.time() - start_time
    print(f"\nDone! Indexed {total_lines:,} lines from {len(texts)} texts in {elapsed:.1f}s")

if __name__ == '__main__':
    lang = sys.argv[1] if len(sys.argv) > 1 else 'la'
    
    if lang == 'all':
        for l in ['la', 'grc', 'en']:
            print(f"\n=== Processing {l.upper()} ===")
            populate_lines(l)
    else:
        populate_lines(lang)
