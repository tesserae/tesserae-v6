"""
Tesserae V6 - Inverted Index

Pre-built SQLite index for fast corpus-wide lemma searches.
Enables O(1) lookup of any lemma to find all occurrences across the corpus.

Structure:
    lemma → [(text_id, line_reference, word_positions), ...]

Index Files:
    - data/inverted_index/la_index.db: Latin corpus
    - data/inverted_index/grc_index.db: Greek corpus
    - data/inverted_index/en_index.db: English corpus

Usage:
    from backend.inverted_index import lookup_lemmas
    
    results = lookup_lemmas(['amor', 'bellum'], 'la')
    # Returns dict: {(text_id, ref) -> {'lemmas': [...], 'positions': [...]}}
"""
import os
import sqlite3
import json
from functools import lru_cache

from backend.logging_config import get_logger

logger = get_logger('inverted_index')

INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'inverted_index')

_connections = {}

def get_connection(language):
    """Get SQLite connection for a language index (lazy loading)"""
    if language not in _connections:
        db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                _connections[language] = conn
            except Exception as e:
                logger.error(f"Failed to open {language} index: {e}")
                return None
        else:
            return None
    return _connections[language]

def is_index_available(language):
    """Check if inverted index is available for a language"""
    db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
    return os.path.exists(db_path)

def lookup_lemmas(lemmas, language, fallback_forms=None):
    """
    Look up multiple lemmas and return matching text locations.
    
    Args:
        lemmas: List of lemmas to search for
        language: 'la', 'grc', or 'en'
        fallback_forms: Optional dict mapping lemma -> set of inflected forms to also
                       search for. Matches on fallback forms count as matches for the
                       canonical lemma. This bridges the gap between properly lemmatized
                       queries and indexes built with older/incomplete lemma tables.
    
    Returns:
        Dict mapping (text_id, ref) to list of matching lemmas and positions
    """
    conn = get_connection(language)
    if not conn:
        return {}
    
    cursor = conn.cursor()
    results = {}
    
    # Map expanded variants back to original lemmas for consistent counting
    lemma_mapping = {}
    expanded_lemmas = set(lemmas)
    
    for orig in lemmas:
        lemma_mapping[orig] = orig
        if language == 'la':
            for variant in [orig.replace('u', 'v'), orig.replace('v', 'u'),
                           orig.replace('i', 'j'), orig.replace('j', 'i')]:
                expanded_lemmas.add(variant)
                lemma_mapping[variant] = orig
            if fallback_forms and orig in fallback_forms:
                fb_list = list(fallback_forms[orig])[:30]
                for fb in fb_list:
                    expanded_lemmas.add(fb)
                    lemma_mapping[fb] = orig
                    for variant in [fb.replace('u', 'v'), fb.replace('v', 'u'),
                                   fb.replace('i', 'j'), fb.replace('j', 'i')]:
                        expanded_lemmas.add(variant)
                        lemma_mapping[variant] = orig
    
    expanded_list = list(expanded_lemmas)
    placeholders = ','.join(['?' for _ in expanded_list])
    query = f'''
        SELECT p.lemma, t.filename, p.ref, p.positions
        FROM postings p
        JOIN texts t ON p.text_id = t.text_id
        WHERE p.lemma IN ({placeholders})
    '''  # nosec B608
    
    try:
        cursor.execute(query, expanded_list)  # nosec B608
        for row in cursor.fetchall():
            lemma, filename, ref, positions_json = row
            key = (filename, ref)
            if key not in results:
                results[key] = {'lemmas': set(), 'positions': {}}
            canonical = lemma_mapping.get(lemma, lemma)
            results[key]['lemmas'].add(canonical)
            results[key]['positions'][canonical] = json.loads(positions_json)
    except Exception as e:
        logger.error(f"Index lookup error: {e}")
    
    return results

def find_co_occurring_lemmas(lemmas, language, min_matches=2, max_distance=None, fallback_forms=None):
    """
    Find all text locations where at least min_matches of the given lemmas co-occur.
    
    Args:
        lemmas: List of query lemmas
        language: 'la', 'grc', or 'en'
        min_matches: Minimum number of lemmas that must appear together
        max_distance: Maximum token distance between any matching lemmas (None = no limit)
        fallback_forms: Optional dict mapping lemma -> set of inflected forms to also
                       search for. Matches on fallback forms count as matches for the
                       canonical lemma.
    
    Returns:
        List of (filename, ref, matching_lemmas, positions_dict) tuples
    """
    all_matches = lookup_lemmas(lemmas, language, fallback_forms=fallback_forms)
    
    results = []
    for (filename, ref), data in all_matches.items():
        matching_lemmas = data['lemmas']
        if len(matching_lemmas) >= min_matches:
            if max_distance is not None:
                positions = data['positions']
                all_positions = []
                for lemma in matching_lemmas:
                    if lemma in positions:
                        all_positions.extend(positions[lemma])
                if len(all_positions) >= 2:
                    all_positions.sort()
                    min_span = all_positions[-1] - all_positions[0]
                    if min_span > max_distance:
                        continue
            results.append((filename, ref, matching_lemmas, data['positions']))
    
    return results

def get_text_metadata(language):
    """Get list of all indexed texts with metadata"""
    conn = get_connection(language)
    if not conn:
        return []
    
    cursor = conn.cursor()
    cursor.execute('SELECT filename, author, title, line_count FROM texts')
    return [dict(row) for row in cursor.fetchall()]

def get_index_stats(language):
    """Get statistics about the index"""
    conn = get_connection(language)
    if not conn:
        return None
    
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM texts')
    texts = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(DISTINCT lemma) FROM postings')
    lemmas = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM postings')
    postings = cursor.fetchone()[0]
    
    # Check if lines table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lines'")
    has_lines = cursor.fetchone() is not None
    lines_count = 0
    if has_lines:
        cursor.execute('SELECT COUNT(*) FROM lines')
        lines_count = cursor.fetchone()[0]
    
    db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
    size_mb = os.path.getsize(db_path) / (1024 * 1024)
    
    return {
        'texts': texts,
        'unique_lemmas': lemmas,
        'total_postings': postings,
        'lines_cached': lines_count,
        'has_lines_table': has_lines,
        'size_mb': round(size_mb, 1)
    }

def ensure_lines_table(language):
    """Create lines table if it doesn't exist"""
    conn = get_connection(language)
    if not conn:
        return False
    
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
    return True

def get_line_data(filename, ref, language):
    """Get line content and lemmas directly from index"""
    conn = get_connection(language)
    if not conn:
        return None
    
    cursor = conn.cursor()
    cursor.execute('''
        SELECT l.content, l.lemmas, l.tokens
        FROM lines l
        JOIN texts t ON l.text_id = t.text_id
        WHERE t.filename = ? AND l.ref = ?
    ''', (filename, ref))
    
    row = cursor.fetchone()
    if row:
        return {
            'text': row[0],
            'lemmas': json.loads(row[1]) if row[1] else [],
            'tokens': json.loads(row[2]) if row[2] else []
        }
    return None

def get_lines_batch(filename, refs, language):
    """Get multiple lines at once for efficiency"""
    conn = get_connection(language)
    if not conn:
        return {}
    
    cursor = conn.cursor()
    placeholders = ','.join(['?' for _ in refs])
    cursor.execute(f'''
        SELECT l.ref, l.content, l.lemmas, l.tokens
        FROM lines l
        JOIN texts t ON l.text_id = t.text_id
        WHERE t.filename = ? AND l.ref IN ({placeholders})
    ''', [filename] + list(refs))  # nosec B608
    
    results = {}
    for row in cursor.fetchall():
        results[row[0]] = {
            'text': row[1],
            'lemmas': json.loads(row[2]) if row[2] else [],
            'tokens': json.loads(row[3]) if row[3] else []
        }
    return results

def has_lines_data(language):
    """Check if lines table exists and has data"""
    conn = get_connection(language)
    if not conn:
        return False
    
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lines'")
    if not cursor.fetchone():
        return False
    
    cursor.execute('SELECT COUNT(*) FROM lines LIMIT 1')
    return cursor.fetchone()[0] > 0

def index_single_text(filepath, language, text_processor):
    """
    Index a single text file and add it to the inverted index.
    Called when a new text is added to the corpus.
    
    Args:
        filepath: Full path to the .tess file
        language: 'la', 'grc', or 'en'
        text_processor: TextProcessor instance
    
    Returns:
        dict with indexing results or None on error
    """
    if not os.path.exists(filepath):
        return {'error': 'File not found'}
    
    filename = os.path.basename(filepath)
    db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
    
    if not os.path.exists(db_path):
        return {'error': 'Index not initialized for this language'}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT text_id FROM texts WHERE filename = ?', (filename,))
        if cursor.fetchone():
            conn.close()
            return {'status': 'already_indexed', 'filename': filename}
        
        units = text_processor.process_file(filepath, language, unit_type='line')
        
        parts = filename.replace('.tess', '').split('.')
        author = parts[0] if parts else ''
        title = '.'.join(parts[1:]) if len(parts) > 1 else ''
        
        cursor.execute(
            'INSERT INTO texts (filename, author, title, line_count) VALUES (?, ?, ?, ?)',
            (filename, author, title, len(units))
        )
        text_id = cursor.lastrowid
        
        postings_count = 0
        for unit in units:
            ref = unit.get('ref', '')
            lemmas = unit.get('lemmas', [])
            tokens = unit.get('tokens', [])
            text_content = unit.get('text', '')
            
            lemma_positions = {}
            for i, lemma in enumerate(lemmas):
                if lemma not in lemma_positions:
                    lemma_positions[lemma] = []
                lemma_positions[lemma].append(i)
            
            for lemma, positions in lemma_positions.items():
                cursor.execute(
                    'INSERT INTO postings (lemma, text_id, ref, positions) VALUES (?, ?, ?, ?)',
                    (lemma, text_id, ref, json.dumps(positions))
                )
                postings_count += 1
            
            cursor.execute(
                'INSERT OR IGNORE INTO lines (text_id, ref, content, lemmas, tokens) VALUES (?, ?, ?, ?, ?)',
                (text_id, ref, text_content, json.dumps(lemmas), json.dumps(tokens))
            )
        
        conn.commit()
        conn.close()
        
        if language in _connections:
            del _connections[language]
        
        return {
            'status': 'indexed',
            'filename': filename,
            'lines': len(units),
            'postings': postings_count
        }
        
    except Exception as e:
        return {'error': str(e)}

if __name__ == '__main__':
    for lang in ['la', 'grc']:
        if is_index_available(lang):
            stats = get_index_stats(lang)
            logger.info(f"{lang.upper()}: {stats}")
        else:
            logger.info(f"{lang.upper()}: No index available")
