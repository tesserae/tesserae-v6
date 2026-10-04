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
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
import json

from backend.logging_config import get_logger
# Arabic root channel: above this many line pairs a match needs two shared roots.
_ARABIC_SINGLE_ROOT_MAX_PAIRS = 2_000_000

logger = get_logger('semantic_similarity')

LATIN_GREEK_MODEL = "bowphs/SPhilBerta"
ENGLISH_MODEL = "all-MiniLM-L6-v2"
# Hebrew has its own within-language model: MiqraBERT (Biblical-Hebrew Sentence-BERT),
# fine-tuned in-house on OpenBible cross-references. The he corpus embeddings are computed
# with it. Falls back to base MiqraBERT if the fine-tuned dir is absent.
_HE_FINETUNED = os.path.join(os.path.dirname(__file__), 'models', 'miqrabert-hebrew-thematic')
HEBREW_MODEL = _HE_FINETUNED if os.path.isdir(_HE_FINETUNED) else "davidmsmiley/MiqraBERT"
# Persian, Urdu and Arabic (2026-09-05): multilingual-e5-large, the model the
# Coptic corpus was embedded with (it has no Coptic vocabulary, but covers all
# three of these). Stored embeddings carry the "passage: " prefix the model
# expects (scripts/precompute_e5_multilang.py); the real-time fallback applies
# the same prefix. e5 cosines are compressed (unrelated lines score about 0.75
# to 0.8), so these languages get their own similarity floor and top-n, see
# E5_SEMANTIC_SETTINGS. Coptic keeps its historical path so that the deployed
# system stays the one the Coptic article evaluated.
E5_MODEL = "intfloat/multilingual-e5-large"
E5_LANGUAGES = ('fa', 'ur', 'ar')
E5_PREFIX = "passage: "
# Measured 2026-09-05 on Hafez x Zabur-e Ajam (9,502 x 1,252 lines): mean cosine
# 0.847, 99th percentile 0.893, 99.9th 0.907. The floor sits at the 99.9th
# percentile; scores fed to fusion are rescaled from the compressed band so
# the channel discriminates inside it: 0.90 -> 0.33, 0.925 -> 0.5, 1.0 -> 1.0.
E5_SEMANTIC_SETTINGS = {'min_semantic_score': 0.90, 'semantic_top_n': 10}
E5_RESCALE_FLOOR, E5_RESCALE_SPAN = 0.85, 0.15
# The band differs by language (Burda x Qur'an: mean 0.878, p99.9 0.941), so
# the floor is set per search at this percentile of the pair's own similarity
# matrix (never below the fixed floor), and scores are rescaled above it.
E5_FLOOR_PERCENTILE = 99.9



# The full similarity matrix of a large pair does not fit in memory: Hafez's
# Diwan against Saeb's (9,502 x 157,780 lines, Persian, 2026-10-03) is a
# 6 GB float32 table, built twice over by the division that normalised it,
# and it killed this demo server at a 20 GB cap three times in an hour. The
# matrix is only ever read a row at a time for its top entries, so it is
# computed in blocks of rows against pre-normalised vectors and never held
# whole. The e5 per-search floor, a percentile of the whole matrix until
# now, is taken from a sample of up to 512 evenly spaced source rows.
SIMILARITY_BLOCK_ROWS = 512


def _unit_rows(m):
    m = np.asarray(m, dtype=np.float32)
    return m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-8)


def iter_similarity_blocks(source_embeddings, target_embeddings, cancellation=None,
                           block_rows=SIMILARITY_BLOCK_ROWS):
    src = _unit_rows(source_embeddings)
    tgt_t = _unit_rows(target_embeddings).T
    for start in range(0, src.shape[0], block_rows):
        if cancellation:
            cancellation.check()
        yield start, src[start:start + block_rows] @ tgt_t


def sampled_percentile(source_embeddings, target_embeddings, percentile, rows=SIMILARITY_BLOCK_ROWS):
    """The percentile of the cosine matrix, from up to `rows` evenly spaced source rows (exact below that)."""
    src = np.asarray(source_embeddings, dtype=np.float32)
    if src.shape[0] > rows:
        src = src[np.linspace(0, src.shape[0] - 1, rows).astype(int)]
    block = _unit_rows(src) @ _unit_rows(target_embeddings).T
    return float(np.percentile(block, percentile))


def top_pairs_by_block(source_embeddings, target_embeddings, top_n_per_source, min_score,
                       cancellation=None, block_rows=SIMILARITY_BLOCK_ROWS):
    out = []
    want = max(1, top_n_per_source * 2)
    for start, block in iter_similarity_blocks(source_embeddings, target_embeddings, cancellation, block_rows):
        k = min(want, block.shape[1])
        for r in range(block.shape[0]):
            row = block[r]
            cand = np.argpartition(-row, k - 1)[:k] if k < row.shape[0] else np.arange(row.shape[0])
            cand = cand[np.argsort(-row[cand], kind='stable')]
            count = 0
            for tgt_idx in cand:
                sim = float(row[tgt_idx])
                if sim >= min_score:
                    out.append((start + r, int(tgt_idx), sim))
                    count += 1
                    if count >= top_n_per_source:
                        break
    return out

def _rows_for_units(text_path, language, units):
    """Row indices into a text's stored embeddings for these units, matched by
    ref through the .meta.json line_refs, so a subset or a chunk of a text
    (a benchmark run over 2,500-line slices, say) reads the right rows. None
    when the metadata is missing or any ref is absent (caller then slices
    from the top, the historical behavior for whole-text searches)."""
    try:
        import json
        from backend.embedding_storage import get_metadata_path
        mp = get_metadata_path(text_path, language)
        if not os.path.exists(mp):
            return None
        refs = _META_REFS_CACHE.get(mp)
        if refs is None:
            with open(mp, encoding='utf-8') as f:
                refs = json.load(f).get('line_refs') or []
            _META_REFS_CACHE[mp] = refs
        pos = {r: i for i, r in enumerate(refs)}
        rows = [pos.get(u.get('ref')) for u in units]
        if any(r is None for r in rows):
            return None
        return rows
    except Exception as e:  # pragma: no cover
        logger.warning(f"ref-based embedding alignment failed for {text_path}: {e}")
        return None


_META_REFS_CACHE = {}
_GATHER_CACHE = {}


def _gather_by_ref(units, language):
    """Embeddings for units drawn from SEVERAL texts (a target of all 114
    suras, say), each line read from its own text's stored vectors, the
    file found from the ref (components before the trailing numbers:
    'quran.al_waqia.56.23' -> texts/<lang>/quran.al_waqia.tess). None if any
    unit's file or ref is missing."""
    import re as _re
    import numpy as np
    from backend.embedding_storage import load_embeddings, get_metadata_path, EMBEDDINGS_DIR
    rows = []
    for u in units:
        ref = u.get('ref') or ''
        parts = ref.split('.')
        while parts and _re.fullmatch(r'\d+', parts[-1]):
            parts.pop()
        stem = '.'.join(parts)
        if not stem:
            return None
        key = (stem, language)
        ent = _GATHER_CACHE.get(key)
        if ent is None:
            fake_path = os.path.join('texts', language, stem + '.tess')
            arr = load_embeddings(fake_path, language)
            mp = get_metadata_path(fake_path, language)
            if arr is None or not os.path.exists(mp):
                return None
            import json
            with open(mp, encoding='utf-8') as f:
                refs = json.load(f).get('line_refs') or []
            ent = (arr, {r: i for i, r in enumerate(refs)})
            _GATHER_CACHE[key] = ent
        arr, pos = ent
        i = pos.get(ref)
        if i is None:
            return None
        rows.append(arr[i])
    return np.vstack(rows) if rows else None


def model_name_for(language: str) -> str:
    """Which sentence-transformer serves a language's semantic channel."""
    if language == 'he':
        return HEBREW_MODEL
    if language in E5_LANGUAGES:
        return E5_MODEL
    return LATIN_GREEK_MODEL
CACHE_DIR = os.path.join(os.path.dirname(__file__), 'semantic_cache')
EMBEDDINGS_CACHE_FILE = os.path.join(CACHE_DIR, 'embeddings_cache.json')
LEMMA_CACHE_FILE = os.path.join(CACHE_DIR, 'lemma_embeddings.json')

_models = {}
_embeddings_cache = {}
_lemma_embeddings_cache = {}


# The full similarity matrix of a large pair does not fit in memory: Hafez's
# Diwan against Saeb's (9,502 x 157,780 lines, Persian, 2026-10-03) is a
# 6 GB float32 table, built twice over by the division that normalised it,
# and it killed the demo server at a 20 GB cap three times in an hour. The
# matrix is only ever read a row at a time for its top entries, so it is
# computed in blocks of rows against pre-normalised vectors and never held
# whole. A block of 512 rows against 157,780 columns is 323 MB.
SIMILARITY_BLOCK_ROWS = 512


def _unit_rows(m):
    m = np.asarray(m, dtype=np.float32)
    return m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-8)


def iter_similarity_blocks(source_embeddings, target_embeddings, cancellation=None,
                           block_rows=SIMILARITY_BLOCK_ROWS):
    """Yield (first_row_index, cosine block) for successive blocks of source rows."""
    src = _unit_rows(source_embeddings)
    tgt_t = _unit_rows(target_embeddings).T
    for start in range(0, src.shape[0], block_rows):
        if cancellation:
            cancellation.check()
        yield start, src[start:start + block_rows] @ tgt_t


def top_pairs_by_block(source_embeddings, target_embeddings, top_n_per_source, min_score,
                       cancellation=None, block_rows=SIMILARITY_BLOCK_ROWS):
    """(source_idx, target_idx, cosine) for each source row's best targets at or
    above min_score, at most top_n_per_source per row, computed block by block.
    Same pairs as the full-matrix version, in the same per-row order."""
    out = []
    want = max(1, top_n_per_source * 2)
    for start, block in iter_similarity_blocks(source_embeddings, target_embeddings, cancellation, block_rows):
        k = min(want, block.shape[1])
        for r in range(block.shape[0]):
            row = block[r]
            cand = np.argpartition(-row, k - 1)[:k] if k < row.shape[0] else np.arange(row.shape[0])
            cand = cand[np.argsort(-row[cand], kind='stable')]
            count = 0
            for tgt_idx in cand:
                sim = float(row[tgt_idx])
                if sim >= min_score:
                    out.append((start + r, int(tgt_idx), sim))
                    count += 1
                    if count >= top_n_per_source:
                        break
    return out

def get_model(language: str = 'la'):
    """
    Lazily load the appropriate sentence transformer model based on language.
    Uses SPhilBERTa for all languages (Latin, Greek, English) to enable
    cross-lingual search. SPhilBERTa's XLM-RoBERTa base handles English
    well (cosine 0.75+ for English-Latin translation pairs).

    Args:
        language: Language code ('la', 'grc', or 'en')

    Returns:
        SentenceTransformer model or None if loading fails
    """
    global _models

    # Use SPhilBERTa for all languages to share embedding space, except Hebrew,
    # which uses its own within-language fine-tuned MiqraBERT.
    model_name = model_name_for(language)
    
    if model_name not in _models:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading semantic model for {language}: {model_name}...")
            _models[model_name] = SentenceTransformer(model_name)
            logger.info(f"Semantic model {model_name} loaded successfully")
        except Exception as e:
            logger.error(f"Error loading semantic model {model_name}: {e}")
            logger.warning(f"Semantic matching will be unavailable for {language}")
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
        if language in E5_LANGUAGES:
            texts = [E5_PREFIX + t for t in texts]
        embeddings = model.encode(texts, show_progress_bar=show_progress)
        return embeddings
    except Exception as e:
        logger.error(f"Error encoding texts: {e}")
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
                          settings: Optional[Dict] = None,
                          cancellation=None) -> Tuple[List[Dict], int]:
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
    if cancellation:
        cancellation.check()
    language = settings.get('language', 'la')
    if language in E5_LANGUAGES:
        # The shared CHANNEL_CONFIGS floor (0.5) would accept every e5 pair.
        settings = {**settings, **{k: v for k, v in E5_SEMANTIC_SETTINGS.items()
                                   if k not in settings.get('_explicit', ())}}
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
            if language in E5_LANGUAGES:
                # A side made of several texts has no single file: gather.
                if source_all is None:
                    g = _gather_by_ref(source_units, language)
                    if g is not None:
                        source_all, source_indices = g, list(range(len(g)))
                if target_all is None:
                    g = _gather_by_ref(target_units, language)
                    if g is not None:
                        target_all, target_indices = g, list(range(len(g)))
            
            if source_all is not None and target_all is not None:
                if source_indices is None and len(source_units) != len(source_all):
                    source_indices = _rows_for_units(source_path, language, source_units)
                    if source_indices is None and language in E5_LANGUAGES:
                        g = _gather_by_ref(source_units, language)
                        if g is not None:
                            source_all, source_indices = g, list(range(len(g)))
                if target_indices is None and len(target_units) != len(target_all):
                    target_indices = _rows_for_units(target_path, language, target_units)
                    if target_indices is None and language in E5_LANGUAGES:
                        g = _gather_by_ref(target_units, language)
                        if g is not None:
                            target_all, target_indices = g, list(range(len(g)))
                if source_indices is not None:
                    source_embeddings = source_all[source_indices]
                else:
                    source_embeddings = source_all[:len(source_units)]
                
                if target_indices is not None:
                    target_embeddings = target_all[target_indices]
                else:
                    target_embeddings = target_all[:len(target_units)]
                
                used_precomputed = True
                logger.info(f"Using pre-computed embeddings: {len(source_embeddings)} source, {len(target_embeddings)} target")
        except Exception as e:
            logger.warning(f"Failed to load pre-computed embeddings: {e}")

    if source_embeddings is None or target_embeddings is None:
        if cancellation:
            cancellation.check()
        model = get_model(language)
        if model is None:
            logger.warning(f"Semantic model not available for {language}, returning empty results")
            return [], 0
        
        source_texts = [u.get('text', '') for u in source_units]
        target_texts = [u.get('text', '') for u in target_units]
        
        total_comparisons = len(source_texts) * len(target_texts)
        if total_comparisons > 10000000:
            logger.warning(f"{total_comparisons:,} comparisons - this may take a long time.")
            logger.warning(f"Consider pre-computing embeddings for faster search.")

        logger.info(f"Computing embeddings for {len(source_texts)} source and {len(target_texts)} target units...")
        
        try:
            source_embeddings = encode_texts(source_texts, show_progress=False, language=language)
            if cancellation:
                cancellation.check()
            target_embeddings = encode_texts(target_texts, show_progress=False, language=language)
            if source_embeddings is None or target_embeddings is None:
                logger.error(f"Failed to encode texts for {language}")
                return [], 0
        except Exception as e:
            logger.error(f"Error computing embeddings: {e}")
            return [], 0
    
    logger.info(f"Computing similarity in blocks ({len(source_embeddings)} x {len(target_embeddings)})...")

    matches = []

    e5_floor = None
    if language in E5_LANGUAGES:
        if len(source_embeddings) * len(target_embeddings) >= 10000:
            # Per-search floor at the 99.9th percentile of the pair's own
            # similarities, from a sample of rows, never below the fixed
            # floor. Small matrices keep the fixed band.
            e5_floor = float(max(min_score, sampled_percentile(source_embeddings, target_embeddings, E5_FLOOR_PERCENTILE)))
            min_score = e5_floor
            logger.info(f"e5 semantic floor for this search: {e5_floor:.3f} (p{E5_FLOOR_PERCENTILE}, sampled)")
        else:
            e5_floor = E5_RESCALE_FLOOR

    for src_idx, tgt_idx, sim in top_pairs_by_block(source_embeddings, target_embeddings, top_n_per_source, min_score, cancellation):
        score = sim
        if e5_floor is not None:
            # 0 at the floor, 1 at cosine 1.0, so the channel
            # discriminates inside the band it admits.
            score = max(0.0, min(1.0, (sim - e5_floor) / max(1e-6, 1.0 - e5_floor)))
        matches.append({
            'source_idx': src_idx,
            'target_idx': tgt_idx,
            'matched_lemmas': [],
            'match_basis': 'semantic',
            'semantic_score': score,
            'cosine': sim,
        })

    matches.sort(key=lambda x: x.get('semantic_score', 0), reverse=True)

    if max_results > 0:
        matches = matches[:max_results]

    mode = "pre-computed" if used_precomputed else "real-time"
    logger.info(f"Found {len(matches)} semantic matches ({mode})")
    return matches, 0


def find_dictionary_matches(source_units: List[Dict], target_units: List[Dict],
                             settings: Optional[Dict] = None,
                             cancellation=None) -> Tuple[List[Dict], int]:
    """
    Find intra-language dictionary-based matches using V3 synonym data.

    Uses an inverted-index approach: builds a target lemma index, then for
    each source lemma looks up which target lines contain a synonym of that
    lemma. This is O(S * L * avg_synonyms) instead of the brute-force
    O(S * T * L^2) pairwise comparison.

    Args:
        source_units: List of source text units with 'lemmas' field
        target_units: List of target text units with 'lemmas' field
        settings: Optional settings dict with:
            - language: Language code ('la', 'grc', or 'en')
            - min_matches: Minimum synonym pairs per unit pair (default: 2)
            - max_results: Maximum number of results (default: 0 = no limit)
            - include_lemma_matches: If True, count same-lemma pairs (default: False)

    Returns:
        Tuple of (matches list, stoplist_size)
    """
    from backend.synonym_dict import get_latin_lookup, get_greek_lookup, get_coptic_lookup
    from backend.matcher import DEFAULT_LATIN_STOP_WORDS, DEFAULT_GREEK_STOP_WORDS

    settings = settings or {}
    if cancellation:
        cancellation.check()
    language = settings.get('language', 'la')
    min_matches = settings.get('min_matches', 2)
    max_results = settings.get('max_results', 0)
    include_lemma_matches = settings.get('include_lemma_matches', False)

    if language == 'en':
        logger.warning("Dictionary matching not available for English (no synonym data in V3)")
        return [], 0

    if language == 'la':
        lookup = get_latin_lookup()
        stopwords = DEFAULT_LATIN_STOP_WORDS
    elif language == 'grc':
        lookup = get_greek_lookup()
        stopwords = DEFAULT_GREEK_STOP_WORDS
    elif language == 'cop':
        lookup = get_coptic_lookup()
        from backend.coptic.stopwords import COPTIC_STOP_WORDS
        stopwords = COPTIC_STOP_WORDS
    elif language == 'ar':
        # Root equivalence (backend/arabic/roots.py): words of one root are
        # this channel's "synonyms". A single shared root is the signal a
        # near-quotation leaves, so the default minimum is one pair here.
        from backend.arabic.roots import build_root_lookup
        from backend.fusion import _STOPLISTS
        stopwords = _STOPLISTS.get('ar', set())
        lookup = build_root_lookup(source_units, target_units, stopwords)
        # One shared root on a small comparison (a qasida against a sura, the
        # measured case); two on a large one. Whole diwans on both sides
        # (2026-09-06: Mutanabbi's 5,474 verses against Shawqi's 1,400) gave
        # 292,000 single-root pairs and took the app past its memory cap.
        n_pairs = len(source_units) * len(target_units)
        min_matches = 1 if n_pairs <= _ARABIC_SINGLE_ROOT_MAX_PAIRS else 2
        if min_matches == 2:
            logger.info(f"Arabic root channel: {n_pairs:,} line pairs, requiring two shared roots")
    else:
        return [], 0

    def is_content(lemma):
        return lemma not in stopwords and len(lemma) > 2

    # Phase 1: Build target lemma index — maps each lemma to the set of
    # target line indices where it appears.
    target_lemma_lines = defaultdict(set)
    for tgt_idx, tgt_unit in enumerate(target_units):
        if cancellation:
            cancellation.check()
        for lemma in tgt_unit.get('lemmas', []):
            low = lemma.lower()
            if is_content(low):
                target_lemma_lines[low].add(tgt_idx)

    # Phase 2: For each source line, find target lines that share synonym
    # pairs via the index.  A "synonym pair" is (src_lemma, tgt_lemma) where
    # tgt_lemma is in the synonym set of src_lemma (and they differ, unless
    # include_lemma_matches is True).
    # Bounded candidate list (2026-09-20): the fusion runner passes
    # candidate_cap; before, a whole-file prose source against the Aeneid
    # produced hundreds of thousands of window pairs here (360,126 for
    # Quintilian 9) and Seneca's Letters blew a 12 GB cap in this step.
    from backend.matcher import BoundedCandidates
    candidates = BoundedCandidates(settings.get('candidate_cap'), source_units, target_units)
    for src_idx, src_unit in enumerate(source_units):
        if cancellation:
            cancellation.check()
        # tgt_idx → set of (src_lemma, tgt_lemma) synonym pairs found
        pair_counts = defaultdict(set)
        for src_lemma in src_unit.get('lemmas', []):
            src_low = src_lemma.lower()
            if not is_content(src_low):
                continue
            synonyms = lookup.get(src_low, set())
            if not synonyms:
                continue
            for syn in synonyms:
                if not include_lemma_matches and syn == src_low:
                    continue
                if not is_content(syn):
                    continue
                if syn in target_lemma_lines:
                    for tgt_idx in target_lemma_lines[syn]:
                        pair_counts[tgt_idx].add((src_low, syn))

        for tgt_idx, pairs in pair_counts.items():
            if len(pairs) >= min_matches:
                matched = {p[0] for p in pairs} | {p[1] for p in pairs}
                candidates.add({
                    'source_idx': src_idx,
                    'target_idx': tgt_idx,
                    'matched_lemmas': list(matched),
                    'synonym_pairs': sorted(pairs),  # (source lemma, target lemma)
                    'match_basis': 'dictionary',
                })
    matches = candidates.result()

    if max_results > 0 and candidates.cap <= 0:
        matches = matches[:max_results]

    mode = "include_lemma" if include_lemma_matches else "synonym_only"
    logger.info(f"Found {len(matches)} dictionary matches (min_matches={min_matches}, {mode})")
    return matches, len(stopwords)


def find_crosslingual_matches(source_units: List[Dict], target_units: List[Dict],
                               source_language: str, target_language: str,
                               settings: Optional[Dict] = None,
                               cancellation=None) -> Tuple[List[Dict], int]:
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
    if cancellation:
        cancellation.check()
    min_score = settings.get('min_semantic_score', 0.5)
    max_results = settings.get('max_results', 500)
    top_n_per_source = settings.get('semantic_top_n', 10)
    source_path = settings.get('source_text_path')
    target_path = settings.get('target_text_path')
    source_indices = settings.get('source_line_indices')
    target_indices = settings.get('target_line_indices')
    
    classical = ('la', 'grc', 'en')
    shared_e5 = source_language in E5_LANGUAGES and target_language in E5_LANGUAGES
    if not shared_e5 and (source_language not in classical or target_language not in classical):
        logger.warning(f"Cross-lingual matching only supports Latin (la), Greek (grc), and English (en), "
                       f"or pairs among Persian, Urdu and Arabic")
        return [], 0
    
    if source_language == target_language:
        logger.warning(f"For same-language matching, use find_semantic_matches instead")
        return find_semantic_matches(source_units, target_units, 
                                     {**settings, 'language': source_language}, cancellation)
    
    source_embeddings = None
    target_embeddings = None
    used_precomputed = False
    
    if source_path and target_path:
        try:
            from backend.embedding_storage import load_embeddings
            
            source_all = load_embeddings(source_path, source_language)
            target_all = load_embeddings(target_path, target_language)
            # Persian/Urdu/Arabic sides made of several texts (all 114 suras),
            # or chunks of a text: gather rows by ref, as the same-language
            # channel does.
            if source_language in E5_LANGUAGES:
                if source_all is None or (source_indices is None and len(source_units) != len(source_all)):
                    g = _gather_by_ref(source_units, source_language)
                    if g is not None:
                        source_all, source_indices = g, list(range(len(g)))
            if target_language in E5_LANGUAGES:
                if target_all is None or (target_indices is None and len(target_units) != len(target_all)):
                    g = _gather_by_ref(target_units, target_language)
                    if g is not None:
                        target_all, target_indices = g, list(range(len(g)))
            
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
                logger.info(f"Using pre-computed embeddings: {len(source_embeddings)} {source_language}, {len(target_embeddings)} {target_language}")
        except Exception as e:
            logger.warning(f"Failed to load pre-computed embeddings: {e}")

    if source_embeddings is None or target_embeddings is None:
        if cancellation:
            cancellation.check()
        model = get_model(source_language if source_language in E5_LANGUAGES else 'la')
        if model is None:
            logger.warning("Cross-lingual embedding model not available")
            return [], 0
        
        source_texts = [u.get('text', '') for u in source_units]
        target_texts = [u.get('text', '') for u in target_units]
        
        total_comparisons = len(source_texts) * len(target_texts)
        if total_comparisons > 10000000:
            logger.warning(f"{total_comparisons:,} comparisons - consider pre-computing embeddings")

        logger.info(f"Computing cross-lingual embeddings: {len(source_texts)} {source_language} -> {len(target_texts)} {target_language}")
        
        try:
            source_embeddings = model.encode(source_texts, show_progress_bar=False)
            if cancellation:
                cancellation.check()
            target_embeddings = model.encode(target_texts, show_progress_bar=False)
            if source_embeddings is None or target_embeddings is None:
                logger.error("Failed to encode texts for cross-lingual matching")
                return [], 0
        except Exception as e:
            logger.error(f"Error computing cross-lingual embeddings: {e}")
            return [], 0
    
    logger.info(f"Computing similarity in blocks ({len(source_embeddings)} x {len(target_embeddings)})...")

    matches = []

    e5_floor = None
    if source_language in E5_LANGUAGES and target_language in E5_LANGUAGES:
        # Shared multilingual-e5 space: same per-search floor and rescaling
        # as the same-language channel, the percentile taken from a sample
        # of rows (see sampled_percentile).
        if len(source_embeddings) * len(target_embeddings) >= 10000:
            e5_floor = float(max(E5_SEMANTIC_SETTINGS['min_semantic_score'],
                                 sampled_percentile(source_embeddings, target_embeddings, E5_FLOOR_PERCENTILE)))
        else:
            e5_floor = E5_RESCALE_FLOOR
        min_score = max(min_score, e5_floor)
        logger.info(f"e5 cross-lingual floor: {e5_floor:.3f}")

    for src_idx, tgt_idx, sim in top_pairs_by_block(source_embeddings, target_embeddings, top_n_per_source, min_score, cancellation):
        score = sim
        if e5_floor is not None:
            score = max(0.0, min(1.0, (sim - e5_floor) / max(1e-6, 1.0 - e5_floor)))
        matches.append({
            'source_idx': src_idx,
            'target_idx': tgt_idx,
            'matched_lemmas': [],
            'match_basis': 'semantic_cross',
            'semantic_score': score,
            'cosine': sim,
            'source_language': source_language,
            'target_language': target_language
        })

    matches.sort(key=lambda x: x.get('semantic_score', 0), reverse=True)

    if max_results > 0:
        matches = matches[:max_results]

    mode = "pre-computed" if used_precomputed else "real-time"
    logger.info(f"Found {len(matches)} cross-lingual semantic matches ({source_language} -> {target_language}, {mode})")
    return matches, 0


def find_dictionary_crosslingual_matches(source_units: List[Dict], target_units: List[Dict],
                                          source_language: str, target_language: str,
                                          settings: Optional[Dict] = None,
                                          greek_frequencies: Optional[Dict] = None,
                                          latin_frequencies: Optional[Dict] = None,
                                          cancellation=None) -> Tuple[List[Dict], int]:
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
    
    if source_language not in ('la', 'grc', 'en') or target_language not in ('la', 'grc', 'en'):
        logger.warning(f"Dictionary matching only supports Latin (la), Greek (grc), and English (en)")
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
        if cancellation:
            cancellation.check()
        src_lemmas = src_unit.get('lemmas', [])
        if not src_lemmas:
            continue
        
        for tgt_idx, tgt_unit in enumerate(target_units):
            if cancellation:
                cancellation.check()
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
        logger.debug(f"Top matches (showing first 5) - unique Greek/Latin words:")
        for m in matches[:5]:
            lemmas = m.get('matched_lemmas', [])
            score = m.get('overall_score', 0)
            avg_idf = m.get('avg_idf', 0)
            dist = m.get('distance', 0)
            u_grc = m.get('unique_greek', 0)
            u_lat = m.get('unique_latin', 0)
            logger.debug(f"  {lemmas} | grc={u_grc} lat={u_lat} avg_idf={avg_idf:.2f} score={score:.3f}")
    
    if max_results > 0:
        matches = matches[:max_results]
    
    logger.info(f"Found {len(matches)} dictionary cross-lingual matches ({source_language} -> {target_language})")
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
        logger.error(f"Error computing semantic boost: {e}")
        return 0.0

def is_available(language: str = 'la') -> bool:
    """Check if semantic matching is available for a language."""
    try:
        model = get_model(language)
        return model is not None
    except Exception as e:
        logger.error(f"Error checking if semantic model is available: {e}")
        return False

def get_model_info(language: str = 'la') -> Dict:
    """Get information about the semantic model for a language."""
    model_name = LATIN_GREEK_MODEL
    capabilities = [
        'Latin semantic similarity',
        'Greek semantic similarity',
        'English semantic similarity',
        'Cross-lingual matching (Latin-Greek, Latin-English, Greek-English)',
    ]
    return {
        'model_name': model_name,
        'model_source': 'Heidelberg NLP',
        'paper': 'Graecia capta ferum victorem cepit (ACL 2023)',
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
        logger.error(f"Error encoding lemma '{lemma}': {e}")
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
                logger.error(f"Error encoding lemmas batch: {e}")
    
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
