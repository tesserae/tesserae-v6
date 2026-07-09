"""
Tesserae V6 - Lemma Cache
Pre-computes and caches lemmatized text units for faster searches
"""
import os
import json
import hashlib
import unicodedata
from datetime import datetime
from backend.utils import resolve_text_path

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache', 'lemmas')
TEXTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')

def ensure_cache_dir():
    """Ensure the lemma cache directory exists"""
    os.makedirs(CACHE_DIR, exist_ok=True)

def get_file_hash(filepath):
    """Get MD5 hash of file content to detect changes"""
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()  # nosec B324

def _is_ascii(text):
    """Return True when text can be safely used in ASCII-only environments."""
    try:
        text.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False

def _legacy_cache_path(text_id, language):
    """Get the pre-v2 cache path that used the raw text ID in the filename."""
    safe_id = text_id.replace('/', '_').replace('.tess', '')
    return os.path.join(CACHE_DIR, language, f"{safe_id}.json")

def get_cache_path(text_id, language):
    """Get an ASCII-safe path to a cached lemma file.

    The cache filename must stay ASCII-only because some production WSGI
    environments expose an ASCII filesystem locale. Hashing the normalized
    text ID keeps filenames stable across NFC/NFD variants and avoids Unicode
    encode errors for Greek work IDs.
    """
    # Round-trip any surrogate escapes (from ASCII-locale fs decoding) back
    # to clean Unicode via UTF-8 so the hash is stable whether the caller
    # passes a JSON-decoded text_id or os.path.basename of a surrogate path.
    cleaned_id = text_id.encode('utf-8', errors='surrogateescape').decode('utf-8', errors='replace')
    normalized_id = unicodedata.normalize('NFC', cleaned_id)
    stem = normalized_id.replace('/', '_').replace('.tess', '')
    digest = hashlib.md5(normalized_id.encode('utf-8')).hexdigest()  # nosec B324

    ascii_hint = ''.join(
        c if c.isalnum() or c in '._-' else '_'
        for c in stem
        if ord(c) < 128
    ).strip('._-')
    if not ascii_hint:
        ascii_hint = 'text'

    filename = f"{ascii_hint[:64]}-{digest}.json"
    return os.path.join(CACHE_DIR, language, filename)

def get_cached_units(text_id, language):
    """Load pre-computed units from cache if available and valid"""
    cache_path = get_cache_path(text_id, language)
    if os.path.exists(cache_path):
        candidate_paths = [cache_path]
    elif _is_ascii(text_id):
        # Preserve existing cache hits for ASCII-only text IDs created before
        # the ASCII-safe hashed naming scheme.
        legacy_path = _legacy_cache_path(text_id, language)
        candidate_paths = [legacy_path] if os.path.exists(legacy_path) else []
    else:
        candidate_paths = []

    if not candidate_paths:
        return None
    
    text_path = resolve_text_path(TEXTS_DIR, language, text_id)
    if not text_path:
        return None
    
    try:
        current_hash = get_file_hash(text_path)
        for candidate_path in candidate_paths:
            with open(candidate_path, 'r', encoding='utf-8') as f:
                cached = json.load(f)
            if cached.get('file_hash') == current_hash:
                return cached
        return None
    except (json.JSONDecodeError, IOError):
        return None

def save_cached_units(text_id, language, units_line, units_phrase, file_hash):
    """Save pre-computed units to cache"""
    ensure_cache_dir()
    lang_dir = os.path.join(CACHE_DIR, language)
    os.makedirs(lang_dir, exist_ok=True)
    
    cache_path = get_cache_path(text_id, language)
    cache_data = {
        'text_id': text_id,
        'language': language,
        'file_hash': file_hash,
        'cached_at': datetime.now().isoformat(),
        'units_line': units_line,
        'units_phrase': units_phrase
    }
    
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)
        return True
    except IOError:
        return False

def rebuild_lemma_cache(language, text_processor, progress_callback=None):
    """Rebuild lemma cache for all texts in a language"""
    lang_dir = os.path.join(TEXTS_DIR, language)
    if not os.path.exists(lang_dir):
        return {'error': f'Language directory not found: {language}'}
    
    text_files = [f for f in os.listdir(lang_dir) if f.endswith('.tess')]
    total = len(text_files)
    processed = 0
    errors = []
    
    for text_file in text_files:
        try:
            filepath = os.path.join(lang_dir, text_file)
            file_hash = get_file_hash(filepath)
            
            units_line = text_processor.process_file(filepath, language, 'line')
            units_phrase = text_processor.process_file(filepath, language, 'phrase')
            
            save_cached_units(text_file, language, units_line, units_phrase, file_hash)
            processed += 1
            
            if progress_callback:
                progress_callback(processed, total, text_file)
                
        except Exception as e:
            errors.append(f"{text_file}: {str(e)}")
    
    return {
        'success': True,
        'language': language,
        'total': total,
        'processed': processed,
        'errors': errors
    }

def get_cache_stats():
    """Get statistics about the lemma cache"""
    stats = {}
    
    for lang in ['la', 'grc', 'en']:
        lang_cache_dir = os.path.join(CACHE_DIR, lang)
        lang_text_dir = os.path.join(TEXTS_DIR, lang)
        
        if os.path.exists(lang_cache_dir):
            cached_count = len([f for f in os.listdir(lang_cache_dir) if f.endswith('.json')])
        else:
            cached_count = 0
        
        if os.path.exists(lang_text_dir):
            total_count = len([f for f in os.listdir(lang_text_dir) if f.endswith('.tess')])
        else:
            total_count = 0
        
        stats[lang] = {
            'cached': cached_count,
            'total': total_count,
            'coverage': f"{(cached_count/total_count*100):.1f}%" if total_count > 0 else "0%"
        }
    
    return stats

def clear_lemma_cache(language=None):
    """Clear lemma cache for a language or all languages"""
    if language:
        lang_dir = os.path.join(CACHE_DIR, language)
        if os.path.exists(lang_dir):
            for f in os.listdir(lang_dir):
                os.remove(os.path.join(lang_dir, f))
            return {'cleared': language}
    else:
        for lang in ['la', 'grc', 'en']:
            lang_dir = os.path.join(CACHE_DIR, lang)
            if os.path.exists(lang_dir):
                for f in os.listdir(lang_dir):
                    os.remove(os.path.join(lang_dir, f))
        return {'cleared': 'all'}
