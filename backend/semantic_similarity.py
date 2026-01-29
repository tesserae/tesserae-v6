"""
Tesserae V6 - Semantic Similarity Module

Uses Heidelberg NLP's SPhilBERTa model for cross-lingual semantic matching
between Latin and Ancient Greek texts.

Model: bowphs/SPhilBerta (Sentence Transformer)
Paper: "Graecia capta ferum victorem cepit: Detecting Latin Allusions to 
       Ancient Greek Literature" (Riemenschneider & Frank, ACL 2023)

This module provides:
- Sentence/unit embeddings for Latin and Greek text
- Cosine similarity between text units
- Semantic matching as a primary match type or score boost

The SPhilBERTa model is trained on parallel Latin-Greek texts and can:
- Find semantically similar passages within the same language
- Find cross-lingual allusions between Latin and Greek (future feature)

Citation:
@inproceedings{riemenschneider-frank-2023-graecia,
    title = "{Graecia capta ferum victorem cepit.} Detecting Latin Allusions 
             to Ancient Greek Literature",
    author = "Riemenschneider, Frederick and Frank, Anette",
    booktitle = "Proceedings of the 1st Workshop on Ancient Language Processing",
    year = "2023",
    publisher = "Association for Computational Linguistics",
}
"""

import os
import numpy as np
from typing import List, Dict, Tuple, Optional
import json

LATIN_GREEK_MODEL = "bowphs/SPhilBerta"
ENGLISH_MODEL = "all-MiniLM-L6-v2"
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'semantic_cache')
EMBEDDINGS_CACHE_FILE = os.path.join(CACHE_DIR, 'embeddings_cache.json')
LEMMA_CACHE_FILE = os.path.join(CACHE_DIR, 'lemma_embeddings.json')

_models = {}
_embeddings_cache = {}
_lemma_embeddings_cache = {}

def get_model(language: str = 'la'):
    """
    Lazily load the appropriate sentence transformer model based on language.
    - Latin/Greek: SPhilBERTa (trained on classical texts)
    - English: all-MiniLM-L6-v2 (general-purpose, fast)
    
    Args:
        language: Language code ('la', 'grc', or 'en')
    
    Returns:
        SentenceTransformer model or None if loading fails
    """
    global _models
    
    model_name = ENGLISH_MODEL if language == 'en' else LATIN_GREEK_MODEL
    
    if model_name not in _models:
        try:
            from sentence_transformers import SentenceTransformer
            print(f"Loading semantic model for {language}: {model_name}...")
            _models[model_name] = SentenceTransformer(model_name)
            print(f"Semantic model {model_name} loaded successfully")
        except Exception as e:
            print(f"Error loading semantic model {model_name}: {e}")
            print(f"Semantic matching will be unavailable for {language}")
            return None
    return _models[model_name]

def encode_texts(texts: List[str], show_progress: bool = False, language: str = 'la') -> Optional[np.ndarray]:
    """
    Encode a list of texts into semantic embeddings.
    
    Args:
        texts: List of text strings to encode
        show_progress: Whether to show progress bar
        language: Language code for model selection
        
    Returns:
        NumPy array of shape (len(texts), embedding_dim) or None if model unavailable
    """
    model = get_model(language)
    if model is None:
        return None
    
    try:
        embeddings = model.encode(texts, show_progress_bar=show_progress)
        return embeddings
    except Exception as e:
        print(f"Error encoding texts: {e}")
        return None

def compute_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Compute cosine similarity between two embeddings.
    Sentence-transformer embeddings typically produce similarity in [0, 1] range
    for semantically related texts.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Cosine similarity score (typically 0 to 1 for related texts)
    """
    dot_product = np.dot(embedding1, embedding2)
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    return float(max(0, similarity))

def find_semantic_matches(source_units: List[Dict], target_units: List[Dict], 
                          settings: Optional[Dict] = None) -> Tuple[List[Dict], int]:
    """
    Find semantically similar passages between source and target texts.
    Uses pre-computed embeddings when available for fast search.
    Falls back to real-time computation for smaller texts.
    
    Args:
        source_units: List of source text units with 'text' field
        target_units: List of target text units with 'text' field  
        settings: Optional settings dict with:
            - language: Language code ('la', 'grc', 'en')
            - min_semantic_score: Minimum similarity threshold (default: 0.6)
            - max_results: Maximum number of results (default: 500)
            - semantic_top_n: Top N targets per source (default: 10)
            - source_text_path: Path to source .tess file (for pre-computed embeddings)
            - target_text_path: Path to target .tess file (for pre-computed embeddings)
            - source_line_indices: Subset of line indices to use from source
            - target_line_indices: Subset of line indices to use from target
            
    Returns:
        Tuple of (matches list, stoplist_size=0)
    """
    settings = settings or {}
    language = settings.get('language', 'la')
    min_score = settings.get('min_semantic_score', 0.6)
    max_results = settings.get('max_results', 500)
    top_n_per_source = settings.get('semantic_top_n', 10)
    source_path = settings.get('source_text_path')
    target_path = settings.get('target_text_path')
    source_indices = settings.get('source_line_indices')
    target_indices = settings.get('target_line_indices')
    
    source_embeddings = None
    target_embeddings = None
    used_precomputed = False
    
    if source_path and target_path:
        try:
            from backend.embedding_storage import load_embeddings
            
            source_all = load_embeddings(source_path, language)
            target_all = load_embeddings(target_path, language)
            
            if source_all is not None and target_all is not None:
                if source_indices is not None:
                    source_embeddings = source_all[source_indices]
                else:
                    source_embeddings = source_all[:len(source_units)]
                
                if target_indices is not None:
                    target_embeddings = target_all[target_indices]
                else:
                    target_embeddings = target_all[:len(target_units)]
                
                used_precomputed = True
                print(f"Using pre-computed embeddings: {len(source_embeddings)} source, {len(target_embeddings)} target")
        except Exception as e:
            print(f"Failed to load pre-computed embeddings: {e}")
    
    if source_embeddings is None or target_embeddings is None:
        model = get_model(language)
        if model is None:
            print(f"Semantic model not available for {language}, returning empty results")
            return [], 0
        
        source_texts = [u.get('text', '') for u in source_units]
        target_texts = [u.get('text', '') for u in target_units]
        
        total_comparisons = len(source_texts) * len(target_texts)
        if total_comparisons > 10000000:
            print(f"WARNING: {total_comparisons:,} comparisons - this may take a long time.")
            print(f"Consider pre-computing embeddings for faster search.")
        
        print(f"Computing embeddings for {len(source_texts)} source and {len(target_texts)} target units...")
        
        try:
            source_embeddings = encode_texts(source_texts, show_progress=False, language=language)
            target_embeddings = encode_texts(target_texts, show_progress=False, language=language)
            if source_embeddings is None or target_embeddings is None:
                print(f"Failed to encode texts for {language}")
                return [], 0
        except Exception as e:
            print(f"Error computing embeddings: {e}")
            return [], 0
    
    print(f"Computing similarity matrix ({len(source_embeddings)} x {len(target_embeddings)})...")
    
    similarity_matrix = np.dot(source_embeddings, target_embeddings.T)
    source_norms = np.linalg.norm(source_embeddings, axis=1, keepdims=True)
    target_norms = np.linalg.norm(target_embeddings, axis=1, keepdims=True)
    similarity_matrix = similarity_matrix / (source_norms @ target_norms.T + 1e-8)
    
    matches = []
    
    for src_idx in range(len(source_embeddings)):
        row = similarity_matrix[src_idx]
        top_indices = np.argsort(row)[::-1][:top_n_per_source * 2]
        
        count = 0
        for tgt_idx in top_indices:
            sim = float(row[tgt_idx])
            if sim >= min_score:
                matches.append({
                    'source_idx': int(src_idx),
                    'target_idx': int(tgt_idx),
                    'matched_lemmas': [],
                    'match_basis': 'semantic',
                    'semantic_score': sim
                })
                count += 1
                if count >= top_n_per_source:
                    break
    
    matches.sort(key=lambda x: x.get('semantic_score', 0), reverse=True)
    
    if max_results > 0:
        matches = matches[:max_results]
    
    mode = "pre-computed" if used_precomputed else "real-time"
    print(f"Found {len(matches)} semantic matches ({mode})")
    return matches, 0

def find_crosslingual_matches(source_units: List[Dict], target_units: List[Dict],
                               source_language: str, target_language: str,
                               settings: Optional[Dict] = None) -> Tuple[List[Dict], int]:
    """
    Find semantically similar passages between Greek and Latin texts using
    cross-lingual embeddings from SPhilBERTa.
    Uses pre-computed embeddings when available for fast search.
    
    Args:
        source_units: List of source text units with 'text' field
        target_units: List of target text units with 'text' field
        source_language: Language of source text ('la' or 'grc')
        target_language: Language of target text ('la' or 'grc')
        settings: Optional settings dict with:
            - min_semantic_score: Minimum similarity threshold (default: 0.5)
            - max_results: Maximum number of results (default: 500)
            - semantic_top_n: Top N targets per source (default: 10)
            - source_text_path: Path to source .tess file
            - target_text_path: Path to target .tess file
            - source_line_indices: Subset of line indices to use from source
            - target_line_indices: Subset of line indices to use from target
            
    Returns:
        Tuple of (matches list, stoplist_size=0)
    """
    settings = settings or {}
    min_score = settings.get('min_semantic_score', 0.5)
    max_results = settings.get('max_results', 500)
    top_n_per_source = settings.get('semantic_top_n', 10)
    source_path = settings.get('source_text_path')
    target_path = settings.get('target_text_path')
    source_indices = settings.get('source_line_indices')
    target_indices = settings.get('target_line_indices')
    
    if source_language not in ('la', 'grc') or target_language not in ('la', 'grc'):
        print(f"Cross-lingual matching only supports Latin (la) and Greek (grc)")
        return [], 0
    
    if source_language == target_language:
        print(f"For same-language matching, use find_semantic_matches instead")
        return find_semantic_matches(source_units, target_units, 
                                     {**settings, 'language': source_language})
    
    source_embeddings = None
    target_embeddings = None
    used_precomputed = False
    
    if source_path and target_path:
        try:
            from backend.embedding_storage import load_embeddings
            
            source_all = load_embeddings(source_path, source_language)
            target_all = load_embeddings(target_path, target_language)
            
            if source_all is not None and target_all is not None:
                if source_indices is not None:
                    source_embeddings = source_all[source_indices]
                else:
                    source_embeddings = source_all[:len(source_units)]
                
                if target_indices is not None:
                    target_embeddings = target_all[target_indices]
                else:
                    target_embeddings = target_all[:len(target_units)]
                
                used_precomputed = True
                print(f"Using pre-computed embeddings: {len(source_embeddings)} {source_language}, {len(target_embeddings)} {target_language}")
        except Exception as e:
            print(f"Failed to load pre-computed embeddings: {e}")
    
    if source_embeddings is None or target_embeddings is None:
        model = get_model('la')
        if model is None:
            print("SPhilBERTa model not available for cross-lingual matching")
            return [], 0
        
        source_texts = [u.get('text', '') for u in source_units]
        target_texts = [u.get('text', '') for u in target_units]
        
        total_comparisons = len(source_texts) * len(target_texts)
        if total_comparisons > 10000000:
            print(f"WARNING: {total_comparisons:,} comparisons - consider pre-computing embeddings")
        
        print(f"Computing cross-lingual embeddings: {len(source_texts)} {source_language} -> {len(target_texts)} {target_language}")
        
        try:
            source_embeddings = model.encode(source_texts, show_progress_bar=False)
            target_embeddings = model.encode(target_texts, show_progress_bar=False)
            if source_embeddings is None or target_embeddings is None:
                print("Failed to encode texts for cross-lingual matching")
                return [], 0
        except Exception as e:
            print(f"Error computing cross-lingual embeddings: {e}")
            return [], 0
    
    print(f"Computing similarity matrix ({len(source_embeddings)} x {len(target_embeddings)})...")
    
    similarity_matrix = np.dot(source_embeddings, target_embeddings.T)
    source_norms = np.linalg.norm(source_embeddings, axis=1, keepdims=True)
    target_norms = np.linalg.norm(target_embeddings, axis=1, keepdims=True)
    similarity_matrix = similarity_matrix / (source_norms @ target_norms.T + 1e-8)
    
    matches = []
    
    for src_idx in range(len(source_embeddings)):
        row = similarity_matrix[src_idx]
        top_indices = np.argsort(row)[::-1][:top_n_per_source * 2]
        
        count = 0
        for tgt_idx in top_indices:
            sim = float(row[tgt_idx])
            if sim >= min_score:
                matches.append({
                    'source_idx': int(src_idx),
                    'target_idx': int(tgt_idx),
                    'matched_lemmas': [],
                    'match_basis': 'semantic_cross',
                    'semantic_score': sim,
                    'source_language': source_language,
                    'target_language': target_language
                })
                count += 1
                if count >= top_n_per_source:
                    break
    
    matches.sort(key=lambda x: x.get('semantic_score', 0), reverse=True)
    
    if max_results > 0:
        matches = matches[:max_results]
    
    mode = "pre-computed" if used_precomputed else "real-time"
    print(f"Found {len(matches)} cross-lingual semantic matches ({source_language} -> {target_language}, {mode})")
    return matches, 0


def find_dictionary_crosslingual_matches(source_units: List[Dict], target_units: List[Dict],
                                          source_language: str, target_language: str,
                                          settings: Optional[Dict] = None,
                                          greek_frequencies: Optional[Dict] = None,
                                          latin_frequencies: Optional[Dict] = None) -> Tuple[List[Dict], int]:
    """
    Find Greek-Latin word matches using V3's curated dictionary.
    This provides word-level highlighting without requiring AI embeddings.
    Now with IDF scoring so rare word matches rank higher.
    
    Args:
        source_units: List of source text units with 'text' and 'lemmas' fields
        target_units: List of target text units with 'text' and 'lemmas' fields
        source_language: Language of source text ('grc')
        target_language: Language of target text ('la')
        settings: Optional settings dict with min_matches, max_results
        greek_frequencies: Optional dict of Greek lemma frequencies for IDF scoring
        latin_frequencies: Optional dict of Latin lemma frequencies for IDF scoring
        
    Returns:
        Tuple of (matches list, stoplist_size)
    """
    import math
    from backend.synonym_dict import find_greek_latin_matches
    
    settings = settings or {}
    min_matches = settings.get('min_matches', 2)  # Default to 2 (bigrams) like standard Tesserae
    max_results = settings.get('max_results', 500)
    
    if source_language not in ('la', 'grc') or target_language not in ('la', 'grc'):
        print(f"Dictionary matching only supports Latin (la) and Greek (grc)")
        return [], 0
    
    # Get frequency data for IDF calculation
    grc_freqs = greek_frequencies or {}
    lat_freqs = latin_frequencies or {}
    grc_total = sum(grc_freqs.values()) if grc_freqs else 100000
    lat_total = sum(lat_freqs.values()) if lat_freqs else 100000
    
    def normalize_for_freq_lookup(lemma: str, is_greek: bool = False) -> str:
        """Normalize lemma for frequency lookup - strip accents for Greek"""
        import unicodedata
        lemma_lower = lemma.lower()
        if is_greek:
            # Strip Greek diacritics/accents for frequency lookup
            normalized = unicodedata.normalize('NFD', lemma_lower)
            return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        return lemma_lower
    
    def calculate_idf(lemma: str, freqs: dict, total: int, is_greek: bool = False) -> float:
        """Calculate IDF score - higher for rare words"""
        lookup_key = normalize_for_freq_lookup(lemma, is_greek)
        freq = freqs.get(lookup_key, 1)
        return math.log((total + 1) / (freq + 1)) + 1
    
    matches = []
    
    for src_idx, src_unit in enumerate(source_units):
        src_lemmas = src_unit.get('lemmas', [])
        if not src_lemmas:
            continue
        
        for tgt_idx, tgt_unit in enumerate(target_units):
            tgt_lemmas = tgt_unit.get('lemmas', [])
            if not tgt_lemmas:
                continue
            
            if source_language == 'grc' and target_language == 'la':
                word_matches = find_greek_latin_matches(src_lemmas, tgt_lemmas)
            elif source_language == 'la' and target_language == 'grc':
                word_matches = find_greek_latin_matches(tgt_lemmas, src_lemmas)
                for m in word_matches:
                    m['greek_indices'], m['latin_indices'] = m['latin_indices'], m['greek_indices']
            else:
                continue
            
            # Count UNIQUE words on each side - a "2 word match" means 2 distinct words per language
            unique_greek = set(m['greek_lemma'].lower() for m in word_matches)
            unique_latin = set(m['latin_lemma'].lower() for m in word_matches)
            unique_word_count = min(len(unique_greek), len(unique_latin))
            
            if unique_word_count >= min_matches:
                # Calculate IDF score for each matched word pair
                total_idf = 0.0
                max_idf = 0.0  # Track highest IDF for rare word bonus
                for m in word_matches:
                    grc_idf = calculate_idf(m['greek_lemma'], grc_freqs, grc_total, is_greek=True)
                    lat_idf = calculate_idf(m['latin_lemma'], lat_freqs, lat_total, is_greek=False)
                    m['idf_score'] = (grc_idf + lat_idf) / 2  # Average IDF of the pair
                    total_idf += m['idf_score']
                    max_idf = max(max_idf, m['idf_score'])
                
                # Calculate distance penalty (V3-style)
                # Distance = span of matched words in source + span in target
                src_indices = [idx for m in word_matches for idx in m.get('greek_indices', [])]
                tgt_indices = [idx for m in word_matches for idx in m.get('latin_indices', [])]
                
                if src_indices and tgt_indices:
                    src_distance = max(src_indices) - min(src_indices) + 1
                    tgt_distance = max(tgt_indices) - min(tgt_indices) + 1
                    total_distance = src_distance + tgt_distance
                else:
                    total_distance = 2  # Minimum distance if indices not available
                
                # Scoring: Use AVERAGE IDF (not sum) so rare words beat many common words
                # Then apply distance penalty and small bonus for multiple matches
                avg_idf = total_idf / len(word_matches)
                distance_penalty = math.log(total_distance + 1)
                # Primary score is average IDF / distance, with small match count bonus
                match_bonus = 1 + (0.1 * (len(word_matches) - 1))  # 10% bonus per extra match
                final_score = (avg_idf / distance_penalty) * match_bonus if distance_penalty > 0 else avg_idf
                
                matches.append({
                    'source_idx': src_idx,
                    'target_idx': tgt_idx,
                    'matched_lemmas': [f"{m['greek_lemma']}→{m['latin_lemma']}" for m in word_matches],
                    'word_matches': word_matches,
                    'match_basis': 'dictionary_cross',
                    'semantic_score': len(word_matches) / max(len(src_lemmas), len(tgt_lemmas), 1),
                    'match_count': unique_word_count,  # Use unique word count, not pair count
                    'unique_greek': len(unique_greek),
                    'unique_latin': len(unique_latin),
                    'idf_score': total_idf,
                    'avg_idf': avg_idf,
                    'distance': total_distance,
                    'overall_score': final_score,  # Average IDF / distance with match bonus
                    'source_language': source_language,
                    'target_language': target_language
                })
    
    # Sort by overall_score (IDF / distance), then by match count as tiebreaker
    matches.sort(key=lambda x: (x.get('overall_score', 0), x.get('match_count', 0)), reverse=True)
    
    # Debug: Show top 5 matches with their IDF scores
    if matches:
        print(f"Top matches (showing first 5) - unique Greek/Latin words:")
        for m in matches[:5]:
            lemmas = m.get('matched_lemmas', [])
            score = m.get('overall_score', 0)
            avg_idf = m.get('avg_idf', 0)
            dist = m.get('distance', 0)
            u_grc = m.get('unique_greek', 0)
            u_lat = m.get('unique_latin', 0)
            print(f"  {lemmas} | grc={u_grc} lat={u_lat} avg_idf={avg_idf:.2f} score={score:.3f}")
    
    if max_results > 0:
        matches = matches[:max_results]
    
    print(f"Found {len(matches)} dictionary cross-lingual matches ({source_language} -> {target_language})")
    return matches, 0


def calculate_semantic_boost(source_text: str, target_text: str, language: str = 'la') -> float:
    """
    Calculate semantic similarity boost for a lemma/exact match.
    Used as a feature boost rather than primary matching.
    
    Args:
        source_text: Source passage text
        target_text: Target passage text
        language: Language code for model selection
        
    Returns:
        Semantic similarity score between 0 and 1
    """
    model = get_model(language)
    if model is None:
        return 0.0
    
    try:
        embeddings = model.encode([source_text, target_text])
        return compute_similarity(embeddings[0], embeddings[1])
    except Exception as e:
        print(f"Error computing semantic boost: {e}")
        return 0.0

def is_available(language: str = 'la') -> bool:
    """Check if semantic matching is available for a language."""
    try:
        model = get_model(language)
        return model is not None
    except:
        return False

def get_model_info(language: str = 'la') -> Dict:
    """Get information about the semantic model for a language."""
    model_name = ENGLISH_MODEL if language == 'en' else LATIN_GREEK_MODEL
    if language == 'en':
        capabilities = ['English semantic similarity']
    else:
        capabilities = [
            'Latin semantic similarity',
            'Greek semantic similarity', 
            'Cross-lingual Latin-Greek matching (future)'
        ]
    return {
        'model_name': model_name,
        'model_source': 'Hugging Face' if language == 'en' else 'Heidelberg NLP',
        'paper': 'Graecia capta ferum victorem cepit (ACL 2023)' if language != 'en' else 'N/A',
        'capabilities': capabilities,
        'available': is_available(language)
    }

def get_lemma_embedding(lemma: str, language: str = 'la') -> Optional[np.ndarray]:
    """
    Get embedding for a single lemma, with caching.
    Uses a template to provide context for the word.
    
    Args:
        lemma: The lemma to encode
        language: Language code for model selection
        
    Returns:
        Embedding vector or None if unavailable
    """
    global _lemma_embeddings_cache
    
    cache_key = f"{language}:{lemma}"
    if cache_key in _lemma_embeddings_cache:
        return np.array(_lemma_embeddings_cache[cache_key])
    
    model = get_model(language)
    if model is None:
        return None
    
    try:
        embedding = model.encode(lemma, show_progress_bar=False, convert_to_numpy=True)
        _lemma_embeddings_cache[cache_key] = embedding.tolist()
        return np.array(embedding)
    except Exception as e:
        print(f"Error encoding lemma '{lemma}': {e}")
        return None

def get_lemma_embeddings_batch(lemmas: List[str], language: str = 'la') -> Dict[str, np.ndarray]:
    """
    Get embeddings for multiple lemmas efficiently.
    
    Args:
        lemmas: List of lemmas to encode
        language: Language code for model selection
        
    Returns:
        Dictionary mapping lemma to embedding
    """
    global _lemma_embeddings_cache
    
    result = {}
    to_encode = []
    
    for lemma in lemmas:
        cache_key = f"{language}:{lemma}"
        if cache_key in _lemma_embeddings_cache:
            result[lemma] = np.array(_lemma_embeddings_cache[cache_key])
        else:
            to_encode.append(lemma)
    
    if to_encode:
        model = get_model(language)
        if model is not None:
            try:
                embeddings = model.encode(to_encode, show_progress_bar=False)
                for lemma, emb in zip(to_encode, embeddings):
                    cache_key = f"{language}:{lemma}"
                    _lemma_embeddings_cache[cache_key] = emb.tolist()
                    result[lemma] = emb
            except Exception as e:
                print(f"Error encoding lemmas batch: {e}")
    
    return result

def find_synonym_pairs(source_lemmas: List[str], target_lemmas: List[str], 
                       threshold: float = 0.85, language: str = 'la') -> List[Dict]:
    """
    Find synonym pairs between source and target lemmas using embedding similarity.
    
    Args:
        source_lemmas: Lemmas from source passage
        target_lemmas: Lemmas from target passage
        threshold: Minimum similarity to consider synonyms (default 0.65)
        language: Language code for model selection
        
    Returns:
        List of synonym pairs with similarity scores:
        [{'source_lemma': str, 'target_lemma': str, 'similarity': float, 
          'source_idx': int, 'target_idx': int}]
    """
    if not source_lemmas or not target_lemmas:
        return []
    
    unique_source = list(set(source_lemmas))
    unique_target = list(set(target_lemmas))
    
    all_lemmas = list(set(unique_source + unique_target))
    embeddings = get_lemma_embeddings_batch(all_lemmas, language)
    
    if not embeddings:
        return []
    
    synonym_pairs = []
    seen_pairs = set()
    
    for src_lemma in unique_source:
        if src_lemma not in embeddings:
            continue
        src_emb = embeddings[src_lemma]
        
        for tgt_lemma in unique_target:
            if tgt_lemma not in embeddings:
                continue
            
            if src_lemma.lower() == tgt_lemma.lower():
                continue
                
            pair_key = tuple(sorted([src_lemma, tgt_lemma]))
            if pair_key in seen_pairs:
                continue
            seen_pairs.add(pair_key)
            
            tgt_emb = embeddings[tgt_lemma]
            similarity = compute_similarity(src_emb, tgt_emb)
            
            if similarity >= threshold:
                src_indices = [i for i, l in enumerate(source_lemmas) if l == src_lemma]
                tgt_indices = [i for i, l in enumerate(target_lemmas) if l == tgt_lemma]
                
                synonym_pairs.append({
                    'source_lemma': src_lemma,
                    'target_lemma': tgt_lemma,
                    'similarity': float(similarity),
                    'source_indices': src_indices,
                    'target_indices': tgt_indices
                })
    
    synonym_pairs.sort(key=lambda x: x['similarity'], reverse=True)
    return synonym_pairs

def find_semantic_word_matches(source_tokens: List[str], target_tokens: List[str],
                                source_lemmas: List[str], target_lemmas: List[str],
                                threshold: float = 0.65, language: str = 'la') -> Tuple[List[Dict], List[int], List[int]]:
    """
    Find semantically related words between passages for highlighting.
    Returns exact matches (same lemma) and synonym pairs (similar embeddings).
    
    Args:
        source_tokens: Surface form tokens from source
        target_tokens: Surface form tokens from target
        source_lemmas: Lemmas from source
        target_lemmas: Lemmas from target
        threshold: Similarity threshold for synonyms
        language: Language code for model selection
        
    Returns:
        Tuple of:
        - matched_words: List of match info for display
        - source_highlight_indices: Token indices to highlight in source
        - target_highlight_indices: Token indices to highlight in target
    """
    matched_words = []
    source_highlights = set()
    target_highlights = set()
    
    source_lemma_lower = [l.lower() for l in source_lemmas]
    target_lemma_lower = [l.lower() for l in target_lemmas]
    
    for src_idx, src_lemma in enumerate(source_lemma_lower):
        if src_lemma in target_lemma_lower:
            tgt_idx = target_lemma_lower.index(src_lemma)
            source_highlights.add(src_idx)
            target_highlights.add(tgt_idx)
            
            src_token = source_tokens[src_idx] if src_idx < len(source_tokens) else src_lemma
            tgt_token = target_tokens[tgt_idx] if tgt_idx < len(target_tokens) else target_lemmas[tgt_idx]
            
            if not any(m.get('lemma') == source_lemmas[src_idx] for m in matched_words):
                matched_words.append({
                    'lemma': source_lemmas[src_idx],
                    'source_word': src_token,
                    'target_word': tgt_token,
                    'type': 'exact',
                    'similarity': 1.0
                })
    
    synonym_pairs = find_synonym_pairs(source_lemmas, target_lemmas, threshold, language)
    
    for pair in synonym_pairs:
        for src_idx in pair['source_indices']:
            source_highlights.add(src_idx)
        for tgt_idx in pair['target_indices']:
            target_highlights.add(tgt_idx)
        
        src_token = source_tokens[pair['source_indices'][0]] if pair['source_indices'] and pair['source_indices'][0] < len(source_tokens) else pair['source_lemma']
        tgt_token = target_tokens[pair['target_indices'][0]] if pair['target_indices'] and pair['target_indices'][0] < len(target_tokens) else pair['target_lemma']
        
        matched_words.append({
            'lemma': f"{pair['source_lemma']}~{pair['target_lemma']}",
            'source_word': src_token,
            'target_word': tgt_token,
            'type': 'synonym',
            'similarity': pair['similarity'],
            'display': f"{pair['source_lemma']}≈{pair['target_lemma']} ({int(pair['similarity']*100)}%)"
        })
    
    return matched_words, list(source_highlights), list(target_highlights)
