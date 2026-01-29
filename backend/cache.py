"""
Tesserae V6 - Result Cache
Caches search results for instant repeated queries
"""
import os
import json
import hashlib
from datetime import datetime

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')

def ensure_cache_dir():
    """Ensure cache directory exists"""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

def get_cache_key(source_id, target_id, language, settings):
    """Generate a unique cache key for a search configuration"""
    key_parts = {
        'source': source_id,
        'target': target_id,
        'language': language,
        'source_language': settings.get('source_language', language),
        'target_language': settings.get('target_language', language),
        'match_type': settings.get('match_type', 'lemma'),
        'min_matches': settings.get('min_matches', 2),
        'stoplist_mode': settings.get('stoplist_mode', 'auto'),
        'stoplist_size': settings.get('stoplist_size', 0),
        'max_distance': settings.get('max_distance', 999),
        'use_meter': settings.get('use_meter', False),
        'use_sound': settings.get('use_sound', False),
        'use_edit_distance': settings.get('use_edit_distance', False),
        'use_pos': settings.get('use_pos', False),
        'use_syntax': settings.get('use_syntax', False),
        'source_unit_type': settings.get('source_unit_type', 'line'),
        'target_unit_type': settings.get('target_unit_type', 'line'),
        'stoplist_basis': settings.get('stoplist_basis', 'source_target'),
        'bigram_boost': settings.get('bigram_boost', False),
        'custom_stopwords': settings.get('custom_stopwords', ''),
    }
    key_str = json.dumps(key_parts, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()

def get_cached_results(source_id, target_id, language, settings):
    """Retrieve cached results if they exist"""
    ensure_cache_dir()
    cache_key = get_cache_key(source_id, target_id, language, settings)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)
                return cached.get('results'), cached.get('metadata')
        except (json.JSONDecodeError, IOError):
            return None, None
    return None, None

def save_cached_results(source_id, target_id, language, settings, results, metadata):
    """Save search results to cache"""
    ensure_cache_dir()
    cache_key = get_cache_key(source_id, target_id, language, settings)
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    cache_data = {
        'results': results,
        'metadata': metadata,
        'cached_at': datetime.now().isoformat(),
        'source': source_id,
        'target': target_id,
        'language': language,
        'settings': settings
    }
    
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)
        return True
    except IOError:
        return False

def clear_cache():
    """Clear all cached results"""
    ensure_cache_dir()
    count = 0
    for f in os.listdir(CACHE_DIR):
        if f.endswith('.json'):
            os.remove(os.path.join(CACHE_DIR, f))
            count += 1
    return count

def clear_cache_for_language(language):
    """Clear cached results for a specific language"""
    ensure_cache_dir()
    count = 0
    for f in os.listdir(CACHE_DIR):
        if f.endswith('.json'):
            cache_file = os.path.join(CACHE_DIR, f)
            try:
                with open(cache_file, 'r', encoding='utf-8') as cf:
                    cached = json.load(cf)
                    if cached.get('language') == language:
                        os.remove(cache_file)
                        count += 1
            except (json.JSONDecodeError, IOError):
                pass
    return count

def get_cache_stats():
    """Get cache statistics"""
    ensure_cache_dir()
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith('.json')]
    total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files)
    return {
        'cached_searches': len(files),
        'total_size_mb': round(total_size / (1024 * 1024), 2)
    }
