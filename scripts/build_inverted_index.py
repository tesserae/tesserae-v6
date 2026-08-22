#!/usr/bin/env python3
"""
Build an inverted index for fast lemma-based searches.
Maps lemma → list of (text_id, line_ref, positions) for instant lookups.

For Latin, can optionally use LatinPipe syntax database (syntax_latin.db) to get
high-quality lemmatizations from the EvaLatin 2024 parser, falling back to the
text_processor for texts not covered by the syntax database.

Supports --fast mode for Greek builds: uses only the UD lemma table (58K entries)
instead of the slow CLTK lemmatizer, and skips POS tagging entirely.
"""
import os
import sys
import re
import json
import sqlite3
import argparse
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from backend.text_processor import TextProcessor
try:
    from backend.arabic import register as register_arabic
    register_arabic()
except ImportError:
    pass
try:
    from backend.persian import register as register_persian
    register_persian()
except ImportError:
    pass
try:
    from backend.hebrew import register as register_hebrew
    register_hebrew()
except ImportError:
    pass
try:
    from backend.coptic import register as register_coptic
    register_coptic()
except ImportError:
    pass
try:
    from backend.urdu import register as register_urdu
    register_urdu()
except ImportError:
    pass

TEXTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')
INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'inverted_index')
LEMMA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'lemma_tables')


def load_lemma_table(language):
    """Load UD lemma table for fast table-only lemmatization during builds."""
    if language == 'la':
        path = os.path.join(LEMMA_DIR, 'latin_lemmas.json')
    elif language == 'grc':
        path = os.path.join(LEMMA_DIR, 'greek_lemmas.json')
    else:
        return None
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        table = json.load(f)
    print(f"  Loaded {len(table)} lemma mappings from {os.path.basename(path)}", flush=True)
    return table


def normalize_greek_token(token):
    """Normalize Greek token: remove diacritics, final sigma -> sigma."""
    nfkd = unicodedata.normalize('NFKD', token)
    normalized = ''.join(c for c in nfkd if not unicodedata.combining(c))
    normalized = normalized.replace('ς', 'σ')
    return normalized


def tokenize_greek_fast(text):
    """Fast Greek tokenizer for index builds — no POS tagging needed."""
    text_lower = text.lower()
    text_clean = re.sub(r'[^\u0300-\u036f\u0370-\u03ff\u1f00-\u1fff\s]', '', text_lower)
    tokens = text_clean.split()
    return tokens


def tokenize_latin_fast(text):
    """Fast Latin tokenizer for index builds."""
    text_lower = text.lower()
    text_lower = text_lower.replace('j', 'i').replace('v', 'u')
    text_clean = re.sub(r'[^a-z\s]', '', text_lower)
    tokens = text_clean.split()
    return tokens


def lemmatize_fast(tokens, lemma_table, language):
    """Fast lemmatization using only the UD table — no CLTK calls.
    Unknown words get their normalized form as lemma."""
    lemmas = []
    for token in tokens:
        if language == 'grc':
            norm = normalize_greek_token(token)
        else:
            norm = token
        if lemma_table and norm in lemma_table:
            lemmas.append(lemma_table[norm])
        else:
            lemmas.append(norm)
    return lemmas


def parse_tess_file(filepath):
    """Parse a .tess file and return list of (ref, text) tuples."""
    lines = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            match = re.match(r'^<([^>]+)>\s*(.+)$', line)
            if match:
                lines.append((match.group(1), match.group(2)))
    return lines


def load_syntax_data(language):
    """Load LatinPipe syntax data for use during index build.
    Returns a dict mapping (filename, ref) -> (tokens, lemmas) or None.
    The filename key matches .tess filenames (e.g. 'vergil.aeneid.part.1.tess')."""
    if language != 'la':
        return None
    syntax_db = os.path.join(INDEX_DIR, 'syntax_latin.db')
    if not os.path.exists(syntax_db):
        return None
    try:
        conn = sqlite3.connect(syntax_db)
        cursor = conn.cursor()
        id_to_filename = {}
        cursor.execute('SELECT text_id, filename FROM texts')
        for row in cursor:
            id_to_filename[row[0]] = row[1]
        cursor.execute('SELECT text_id, ref, tokens, lemmas FROM syntax')
        data = {}
        count = 0
        for row in cursor:
            syn_text_id, ref, tokens_json, lemmas_json = row
            filename = id_to_filename.get(syn_text_id)
            if filename is None:
                continue
            toks = json.loads(tokens_json) if tokens_json.startswith('[') else tokens_json.split()
            lems = json.loads(lemmas_json) if lemmas_json.startswith('[') else lemmas_json.split()
            norm_lems = [l.lower().replace('j', 'i').replace('v', 'u') for l in lems]
            data[(filename, ref)] = (toks, norm_lems)
            count += 1
        conn.close()
        print(f"  Loaded {count} lines from LatinPipe syntax database ({len(id_to_filename)} texts)")
        return data
    except Exception as e:
        print(f"  Could not load syntax data: {e}")
        return None

def get_text_files(language):
    """Get all .tess files for a language"""
    lang_dir = os.path.join(TEXTS_DIR, language)
    if not os.path.exists(lang_dir):
        return []
    return [f for f in os.listdir(lang_dir) if f.endswith('.tess')]

def build_index(language, text_processor, verbose=True, resume=True, force=False,
                use_syntax_db=False, fast_mode=False):
    """Build inverted index for a language.
    
    Args:
        language: 'la', 'grc', or 'en'
        text_processor: TextProcessor instance (not used in fast mode)
        verbose: Print progress
        resume: Skip files already in the index (default True)
        force: Drop existing index and rebuild from scratch (overrides resume)
        use_syntax_db: For Latin, use LatinPipe syntax database for higher-quality lemmas
        fast_mode: Use table-only lemmatization (skips CLTK and POS tagging)
    """
    os.makedirs(INDEX_DIR, exist_ok=True)
    db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
    
    syntax_data = None
    if use_syntax_db and language == 'la':
        if verbose:
            print("Loading LatinPipe syntax database for high-quality lemmatization...", flush=True)
        syntax_data = load_syntax_data(language)
        if syntax_data is None:
            print("  WARNING: Could not load syntax database, falling back to standard lemmatization", flush=True)
    
    lemma_table = None
    if fast_mode and language != 'grc':
        if verbose:
            print(f"  NOTE: --fast mode is only for Greek. Using standard mode for {language}.", flush=True)
        fast_mode = False
    if fast_mode:
        lemma_table = load_lemma_table(language)
        if lemma_table is None:
            print(f"  WARNING: Could not load lemma table for {language}, fast mode disabled", flush=True)
            fast_mode = False
    
    existing_files = set()
    
    if force and os.path.exists(db_path):
        if verbose:
            print(f"  --force: Removing existing index {db_path}", flush=True)
        os.remove(db_path)
    
    if os.path.exists(db_path) and resume and not force:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute('SELECT filename FROM texts')
            existing_files = {row[0] for row in cursor.fetchall()}
            if verbose and existing_files:
                print(f"  Resuming: {len(existing_files)} files already indexed", flush=True)
            conn.close()
        except:
            pass
    
    if not os.path.exists(db_path) or not existing_files:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS texts (
                text_id INTEGER PRIMARY KEY,
                filename TEXT UNIQUE,
                author TEXT,
                title TEXT,
                line_count INTEGER
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS postings (
                lemma TEXT,
                text_id INTEGER,
                ref TEXT,
                positions TEXT,
                FOREIGN KEY (text_id) REFERENCES texts(text_id)
            )
        ''')
        
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
        
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_lemma ON postings(lemma)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_text ON postings(text_id)')
        conn.commit()
        conn.close()
    else:
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
        conn.commit()
        conn.close()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    text_files = get_text_files(language)
    files_to_process = [f for f in text_files if f not in existing_files]
    total_files = len(text_files)
    remaining = len(files_to_process)
    total_postings = 0
    total_lines = 0
    syntax_hits = 0
    syntax_misses = 0
    table_hits = 0
    table_misses = 0
    
    mode_label = "FAST (table-only)" if fast_mode else "standard (CLTK)"
    if verbose:
        if existing_files:
            print(f"Building index for {language} [{mode_label}]: {remaining} remaining of {total_files} files", flush=True)
        else:
            print(f"Building index for {language} [{mode_label}]: {total_files} files", flush=True)
    
    build_start = time.time()
    
    for i, filename in enumerate(files_to_process):
        filepath = os.path.join(TEXTS_DIR, language, filename)
        file_start = time.time()
        
        if fast_mode:
            try:
                raw_lines = parse_tess_file(filepath)
            except Exception as e:
                if verbose:
                    print(f"  [{i+1}/{remaining}] ERROR {filename}: {e}", flush=True)
                continue
            
            units = []
            for ref, text in raw_lines:
                tokens = tokenize_greek_fast(text)
                lemmas = lemmatize_fast(tokens, lemma_table, language)
                units.append({'ref': ref, 'text': text, 'tokens': tokens, 'lemmas': lemmas})
        else:
            try:
                units = text_processor.process_file(filepath, language, unit_type='line')
            except Exception as e:
                if verbose:
                    print(f"  [{i+1}/{remaining}] ERROR {filename}: {e}", flush=True)
                continue
        
        file_lines = len(units)
        parts = filename.replace('.tess', '').split('.')
        author = parts[0] if parts else ''
        title = '.'.join(parts[1:]) if len(parts) > 1 else ''
        
        cursor.execute(
            'INSERT OR IGNORE INTO texts (filename, author, title, line_count) VALUES (?, ?, ?, ?)',
            (filename, author, title, file_lines)
        )
        if cursor.rowcount == 0:
            cursor.execute('SELECT text_id FROM texts WHERE filename = ?', (filename,))
            text_id = cursor.fetchone()[0]
            continue
        text_id = cursor.lastrowid
        
        file_postings = 0
        for unit in units:
            ref = unit.get('ref', '')
            lemmas = unit.get('lemmas', [])
            tokens = unit.get('tokens', [])
            text_content = unit.get('text', '')
            
            if syntax_data is not None:
                syntax_key = (filename, ref)
                if syntax_key in syntax_data:
                    syn_tokens, syn_lemmas = syntax_data[syntax_key]
                    lemmas = syn_lemmas
                    tokens = syn_tokens
                    syntax_hits += 1
                else:
                    syntax_misses += 1
            
            if fast_mode and lemma_table:
                for lemma in lemmas:
                    norm = normalize_greek_token(lemma) if language == 'grc' else lemma
                    if norm in lemma_table:
                        table_hits += 1
                    else:
                        table_misses += 1
            
            total_lines += 1
            
            lemma_positions = {}
            for pos, lemma in enumerate(lemmas):
                if lemma not in lemma_positions:
                    lemma_positions[lemma] = []
                lemma_positions[lemma].append(pos)

            # Variant lemmas (Hebrew qere/ketiv): post the ketiv lemma at the SAME
            # position as the qere, so a lemma search for a ketiv-only word (e.g.
            # לא, where the qere is לו) finds the verse. This adds no token
            # position, so word and bigram counts still treat the pair as one.
            for pos, variants in enumerate(unit.get('variant_lemmas') or []):
                for vlem in variants:
                    if not vlem:
                        continue
                    if vlem not in lemma_positions:
                        lemma_positions[vlem] = []
                    if pos not in lemma_positions[vlem]:
                        lemma_positions[vlem].append(pos)

            for lemma, positions in lemma_positions.items():
                cursor.execute(
                    'INSERT INTO postings (lemma, text_id, ref, positions) VALUES (?, ?, ?, ?)',
                    (lemma, text_id, ref, json.dumps(positions))
                )
                total_postings += 1
                file_postings += 1
            
            cursor.execute(
                'INSERT OR IGNORE INTO lines (text_id, ref, content, lemmas, tokens) VALUES (?, ?, ?, ?, ?)',
                (text_id, ref, text_content, json.dumps(lemmas), json.dumps(tokens))
            )
        
        conn.commit()
        
        file_elapsed = time.time() - file_start
        total_elapsed = time.time() - build_start
        if verbose:
            print(f"  [{i+1}/{remaining}] {filename} — {file_lines} lines, {file_postings} postings ({file_elapsed:.1f}s) | Total: {total_lines} lines, {total_elapsed:.0f}s elapsed", flush=True)
    
    conn.commit()
    
    cursor.execute('SELECT COUNT(DISTINCT lemma) FROM postings')
    unique_lemmas = cursor.fetchone()[0]
    
    conn.close()
    
    file_size = os.path.getsize(db_path) / (1024 * 1024)
    
    total_elapsed = time.time() - build_start
    if verbose:
        print(f"\n  Completed: {total_files} texts, {total_lines} lines, {unique_lemmas} unique lemmas, {total_postings} postings", flush=True)
        print(f"  Index size: {file_size:.1f} MB", flush=True)
        print(f"  Total time: {total_elapsed/60:.1f} minutes", flush=True)
        if syntax_data is not None:
            print(f"  LatinPipe syntax hits: {syntax_hits}, fallback to CLTK: {syntax_misses}", flush=True)
        if fast_mode and lemma_table:
            total_tokens = table_hits + table_misses
            pct = (table_hits / total_tokens * 100) if total_tokens > 0 else 0
            print(f"  UD table coverage: {table_hits}/{total_tokens} tokens ({pct:.1f}%)", flush=True)
        print(f"  Saved to: {db_path}", flush=True)
    
    return db_path

def main():
    parser = argparse.ArgumentParser(description='Build inverted index for Tesserae corpus')
    parser.add_argument('--language', '-l', choices=['la', 'grc', 'en', 'ar', 'fa', 'he', 'cop', 'ur', 'all'], default='all',
                        help='Language to index (default: all)')
    parser.add_argument('--quiet', '-q', action='store_true', help='Suppress output')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Force full rebuild: delete existing index and reprocess all files')
    parser.add_argument('--use-syntax-db', action='store_true',
                        help='For Latin: use LatinPipe syntax database for higher-quality lemmatization')
    parser.add_argument('--fast', action='store_true',
                        help='Fast mode (Greek only): use only UD lemma table, skip CLTK and '
                             'POS tagging. Makes Greek builds minutes instead of hours. '
                             'Ignored for Latin and English.')
    args = parser.parse_args()
    
    text_processor = TextProcessor()
    
    if args.language == 'all':
        languages = ['la', 'grc', 'en']
    else:
        languages = [args.language]
    
    for lang in languages:
        build_index(lang, text_processor, verbose=not args.quiet,
                    force=args.force, use_syntax_db=args.use_syntax_db,
                    fast_mode=args.fast)
        print()
    
    print("Done!")

if __name__ == '__main__':
    main()
