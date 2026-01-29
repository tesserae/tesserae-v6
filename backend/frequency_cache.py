import os
import json
import hashlib
from collections import Counter
from datetime import datetime

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache', 'frequencies')
TEXTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')

os.makedirs(CACHE_DIR, exist_ok=True)

_frequency_cache = {}

def deduplicate_text_files(text_files):
    """
    Remove segmented versions when full version exists to avoid double-counting.
    Pattern: author.work.tess (full) vs author.work.part.N.tess (segment)
    If full version exists, exclude all corresponding .part.N files.
    """
    full_versions = set()
    for f in text_files:
        if '.part.' not in f:
            base = f.replace('.tess', '')
            full_versions.add(base)
    
    deduplicated = []
    for f in text_files:
        if '.part.' in f:
            parts = f.split('.part.')
            base = parts[0]
            if base in full_versions:
                continue
        deduplicated.append(f)
    
    return deduplicated

def get_corpus_checksum(language):
    """Get a checksum of all .tess files in a language directory"""
    lang_dir = os.path.join(TEXTS_DIR, language)
    if not os.path.exists(lang_dir):
        return None
    
    files = sorted([f for f in os.listdir(lang_dir) if f.endswith('.tess')])
    file_info = []
    for f in files:
        path = os.path.join(lang_dir, f)
        stat = os.stat(path)
        file_info.append(f"{f}:{stat.st_size}:{stat.st_mtime}")
    
    checksum = hashlib.md5('\n'.join(file_info).encode()).hexdigest()
    return checksum

def get_cache_path(language):
    """Get the path to the frequency cache file for a language"""
    return os.path.join(CACHE_DIR, f'{language}.json')

def load_frequency_cache(language):
    """Load cached frequencies for a language"""
    cache_path = get_cache_path(language)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _frequency_cache[language] = data
                return data
        except:
            pass
    return None

def save_frequency_cache(language, frequencies, total_lemmas, checksum):
    """Save frequency data to cache file"""
    cache_path = get_cache_path(language)
    data = {
        'language': language,
        'frequencies': frequencies,
        'total_lemmas': total_lemmas,
        'text_count': len([f for f in os.listdir(os.path.join(TEXTS_DIR, language)) if f.endswith('.tess')]) if os.path.exists(os.path.join(TEXTS_DIR, language)) else 0,
        'checksum': checksum,
        'last_updated': datetime.now().isoformat()
    }
    
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    
    _frequency_cache[language] = data
    return data

def calculate_corpus_frequencies(language, text_processor):
    """Calculate lemma frequencies for entire corpus (deduplicated)"""
    lang_dir = os.path.join(TEXTS_DIR, language)
    if not os.path.exists(lang_dir):
        return {}
    
    all_lemmas = []
    all_files = [f for f in os.listdir(lang_dir) if f.endswith('.tess')]
    text_files = deduplicate_text_files(all_files)
    
    print(f"Calculating corpus frequencies for {language}: {len(text_files)} texts (excluded {len(all_files) - len(text_files)} duplicate segments)...")
    
    for i, text_file in enumerate(text_files):
        text_path = os.path.join(lang_dir, text_file)
        try:
            units = text_processor.process_file(text_path, language)
            for unit in units:
                all_lemmas.extend(unit['lemmas'])
        except Exception as e:
            print(f"  Error processing {text_file}: {e}")
        
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(text_files)} texts...")
    
    freq = Counter(all_lemmas)
    frequencies = dict(freq.most_common())
    
    checksum = get_corpus_checksum(language)
    data = save_frequency_cache(language, frequencies, len(all_lemmas), checksum)
    
    print(f"  Done: {len(frequencies)} unique lemmas, {len(all_lemmas)} total tokens")
    return data

def get_corpus_frequencies(language, text_processor=None, force_recalculate=False):
    """Get corpus frequencies, calculating if needed"""
    if language in _frequency_cache and not force_recalculate:
        cached = _frequency_cache[language]
        current_checksum = get_corpus_checksum(language)
        if cached.get('checksum') == current_checksum:
            return cached
    
    cached = load_frequency_cache(language)
    if cached and not force_recalculate:
        current_checksum = get_corpus_checksum(language)
        if cached.get('checksum') == current_checksum:
            return cached
    
    if text_processor:
        return calculate_corpus_frequencies(language, text_processor)
    
    return None

def get_cached_stopwords(language, count=50):
    """Get top N most frequent lemmas as stopwords from cache"""
    cached = _frequency_cache.get(language)
    if not cached:
        cached = load_frequency_cache(language)
    
    if cached and 'frequencies' in cached:
        freq_items = list(cached['frequencies'].items())[:count]
        return set(lemma for lemma, _ in freq_items)
    
    return set()

def initialize_all_caches(text_processor):
    """Initialize frequency caches for all languages at startup"""
    for lang in ['la', 'grc', 'en']:
        lang_dir = os.path.join(TEXTS_DIR, lang)
        if os.path.exists(lang_dir):
            get_corpus_frequencies(lang, text_processor)

def recalculate_language_frequencies(language, text_processor):
    """Recalculate frequencies for a specific language (call after adding texts)"""
    return calculate_corpus_frequencies(language, text_processor)

def clear_frequency_cache(language=None):
    """Clear frequency cache for a language or all languages"""
    global _frequency_cache
    cleared_count = 0
    
    if language:
        cache_path = get_cache_path(language)
        if os.path.exists(cache_path):
            os.remove(cache_path)
            cleared_count = 1
        if language in _frequency_cache:
            del _frequency_cache[language]
        return {'cleared': cleared_count, 'language': language}
    else:
        for lang in ['la', 'grc', 'en']:
            cache_path = get_cache_path(lang)
            if os.path.exists(cache_path):
                os.remove(cache_path)
                cleared_count += 1
        _frequency_cache.clear()
        return {'cleared': cleared_count, 'all_languages': True}

def get_frequency_cache_stats():
    """Get frequency cache statistics"""
    stats = {}
    total_entries = 0
    for lang in ['la', 'grc', 'en']:
        cache_path = get_cache_path(lang)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    entries = len(data.get('frequencies', {}))
                    stats[lang] = entries
                    total_entries += entries
            except:
                stats[lang] = 0
        else:
            stats[lang] = 0
    return {'by_language': stats, 'total_entries': total_entries}
