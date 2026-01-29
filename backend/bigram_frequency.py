"""
Bigram (word-pair) frequency calculation and IDF scoring.
Used for kakemphaton detection - finding rare word combinations
even when individual words are common.
"""
import os
import json
import math
from collections import Counter
from datetime import datetime

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache', 'bigrams')
TEXTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')

os.makedirs(CACHE_DIR, exist_ok=True)

_bigram_cache = {}

def make_bigram_key(lemma1, lemma2):
    """Create a canonical bigram key (alphabetically sorted for consistency)"""
    return f"{min(lemma1, lemma2)}|{max(lemma1, lemma2)}"

def extract_bigrams(lemmas):
    """Extract adjacent bigrams from a list of lemmas"""
    bigrams = []
    for i in range(len(lemmas) - 1):
        if lemmas[i] and lemmas[i+1]:
            bigrams.append(make_bigram_key(lemmas[i], lemmas[i+1]))
    return bigrams

def extract_word_pairs(lemmas, max_gap=3):
    """
    Extract word pairs within a window (up to max_gap intervening words).
    This is more relaxed than strict bigrams.
    
    Args:
        lemmas: List of lemmas
        max_gap: Maximum number of words between the pair (default 3)
    
    Returns:
        Set of word pair keys
    """
    pairs = set()
    window = max_gap + 1  # +1 because we count the distance between positions
    for i in range(len(lemmas)):
        if not lemmas[i]:
            continue
        for j in range(i + 1, min(i + window + 1, len(lemmas))):
            if lemmas[j]:
                pairs.add(make_bigram_key(lemmas[i], lemmas[j]))
    return pairs

def get_cache_path(language):
    """Get the path to the bigram cache file for a language"""
    return os.path.join(CACHE_DIR, f'{language}_bigrams.json')

def load_bigram_cache(language):
    """Load cached bigram frequencies for a language"""
    global _bigram_cache
    cache_path = get_cache_path(language)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _bigram_cache[language] = data
                return data
        except:
            pass
    return None

def get_bigram_cache(language):
    """Get the in-memory bigram cache for a language"""
    global _bigram_cache
    if language in _bigram_cache:
        return _bigram_cache[language]
    return load_bigram_cache(language)

def save_bigram_cache(language, frequencies, total_bigrams, doc_frequencies, total_docs):
    """Save bigram frequency data to cache file"""
    cache_path = get_cache_path(language)
    data = {
        'language': language,
        'frequencies': frequencies,
        'total_bigrams': total_bigrams,
        'doc_frequencies': doc_frequencies,
        'total_docs': total_docs,
        'last_updated': datetime.now().isoformat()
    }
    
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    
    _bigram_cache[language] = data
    return data

def calculate_bigram_frequencies(language, text_processor, progress_callback=None):
    """
    Calculate bigram frequencies for entire corpus.
    Tracks both raw frequency and document frequency for IDF calculation.
    """
    lang_dir = os.path.join(TEXTS_DIR, language)
    if not os.path.exists(lang_dir):
        return {}
    
    all_bigrams = []
    doc_bigrams = Counter()
    
    text_files = [f for f in os.listdir(lang_dir) if f.endswith('.tess')]
    if '.part.' in str(text_files):
        full_versions = set()
        for f in text_files:
            if '.part.' not in f:
                base = f.replace('.tess', '')
                full_versions.add(base)
        text_files = [f for f in text_files if '.part.' not in f or f.split('.part.')[0] not in full_versions]
    
    total_docs = len(text_files)
    print(f"Calculating bigram frequencies for {language}: {total_docs} texts...")
    
    for i, text_file in enumerate(text_files):
        text_path = os.path.join(lang_dir, text_file)
        try:
            units = text_processor.process_file(text_path, language)
            doc_unique_bigrams = set()
            
            for unit in units:
                lemmas = unit.get('lemmas', [])
                bigrams = extract_bigrams(lemmas)
                all_bigrams.extend(bigrams)
                doc_unique_bigrams.update(bigrams)
            
            for bg in doc_unique_bigrams:
                doc_bigrams[bg] += 1
                
        except Exception as e:
            print(f"  Error processing {text_file}: {e}")
        
        if progress_callback and (i + 1) % 50 == 0:
            progress_callback(i + 1, total_docs)
        elif (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{total_docs} texts...")
    
    freq = Counter(all_bigrams)
    frequencies = dict(freq.most_common())
    doc_freq_dict = dict(doc_bigrams.most_common())
    
    data = save_bigram_cache(language, frequencies, len(all_bigrams), doc_freq_dict, total_docs)
    
    print(f"  Done: {len(frequencies)} unique bigrams, {len(all_bigrams)} total occurrences")
    return data

def get_bigram_frequencies(language, text_processor=None, force_recalculate=False):
    """Get bigram frequencies, calculating if needed"""
    if language in _bigram_cache and not force_recalculate:
        return _bigram_cache[language]
    
    cached = load_bigram_cache(language)
    if cached and not force_recalculate:
        return cached
    
    if text_processor:
        return calculate_bigram_frequencies(language, text_processor)
    
    return None

def get_bigram_idf(bigram_key, language):
    """
    Get IDF score for a bigram.
    Higher score = rarer bigram = more significant.
    """
    cached = _bigram_cache.get(language)
    if not cached:
        cached = load_bigram_cache(language)
    
    if not cached:
        return 0.0
    
    doc_freqs = cached.get('doc_frequencies', {})
    total_docs = cached.get('total_docs', 1)
    
    doc_freq = doc_freqs.get(bigram_key, 0)
    
    if doc_freq == 0:
        return math.log(total_docs + 1)
    
    return math.log((total_docs + 1) / (doc_freq + 1))

def get_bigram_rarity_score(bigram_key, language):
    """
    Get a rarity score for a bigram (0-1 scale).
    1.0 = extremely rare (appears in very few documents)
    0.0 = very common
    """
    cached = _bigram_cache.get(language)
    if not cached:
        cached = load_bigram_cache(language)
    
    if not cached:
        return 0.5
    
    doc_freqs = cached.get('doc_frequencies', {})
    total_docs = cached.get('total_docs', 1)
    
    doc_freq = doc_freqs.get(bigram_key, 0)
    
    if doc_freq == 0:
        return 1.0
    
    ratio = doc_freq / total_docs
    rarity = 1.0 - ratio
    
    return min(1.0, max(0.0, rarity))

def find_shared_rare_bigrams(source_lemmas, target_lemmas, language, min_rarity=0.9, max_gap=3):
    """
    Find word pairs that appear in both source and target and are rare in the corpus.
    Uses a relaxed window-based approach allowing up to max_gap intervening words.
    
    Args:
        source_lemmas: List of lemmas from source line
        target_lemmas: List of lemmas from target line
        language: 'la', 'grc', or 'en'
        min_rarity: Minimum rarity score (0-1) to consider "rare"
        max_gap: Maximum intervening words between pair members (default 3)
    
    Returns:
        List of (bigram_key, rarity_score) tuples for shared rare word pairs
    """
    source_pairs = extract_word_pairs(source_lemmas, max_gap)
    target_pairs = extract_word_pairs(target_lemmas, max_gap)
    
    shared = source_pairs & target_pairs
    
    rare_shared = []
    for bg in shared:
        rarity = get_bigram_rarity_score(bg, language)
        if rarity >= min_rarity:
            rare_shared.append((bg, rarity))
    
    rare_shared.sort(key=lambda x: -x[1])
    return rare_shared

def calculate_bigram_boost(source_lemmas, target_lemmas, language, boost_weight=1.0):
    """
    Calculate a score boost based on shared rare bigrams.
    
    Args:
        source_lemmas: List of lemmas from source line
        target_lemmas: List of lemmas from target line
        language: 'la', 'grc', or 'en'
        boost_weight: Multiplier for the boost (from feature weights)
    
    Returns:
        Float boost value to add to the match score
    """
    rare_bigrams = find_shared_rare_bigrams(source_lemmas, target_lemmas, language, min_rarity=0.8)
    
    if not rare_bigrams:
        return 0.0
    
    total_boost = sum(rarity * boost_weight for _, rarity in rare_bigrams)
    
    return total_boost

def is_bigram_cache_available(language):
    """Check if bigram cache exists for a language"""
    cache_path = get_cache_path(language)
    return os.path.exists(cache_path)

def get_bigram_stats(language):
    """Get statistics about the bigram cache"""
    cached = _bigram_cache.get(language)
    if not cached:
        cached = load_bigram_cache(language)
    
    if not cached:
        return None
    
    return {
        'unique_bigrams': len(cached.get('frequencies', {})),
        'total_occurrences': cached.get('total_bigrams', 0),
        'total_docs': cached.get('total_docs', 0),
        'last_updated': cached.get('last_updated', 'Unknown')
    }

def initialize_bigram_caches(text_processor):
    """Initialize bigram caches for all languages at startup (if they exist)"""
    for lang in ['la', 'grc', 'en']:
        if is_bigram_cache_available(lang):
            load_bigram_cache(lang)
            print(f"Loaded bigram cache for {lang}")
