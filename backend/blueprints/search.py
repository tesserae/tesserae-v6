"""
Tesserae V6 - Search Blueprint

This module handles the core intertextual search functionality, finding parallel
passages between a source text and a target text using various matching algorithms.

Key Features:
    - Streaming search with real-time progress updates (SSE)
    - Multiple match types: lemma, exact, sound, edit distance, semantic
    - Cross-lingual matching (Latin-Greek, Latin-English, Greek-English)
    - Configurable stoplist generation (Zipf-based)
    - V3-style scoring with IDF and distance metrics
    - Result caching for performance

Search Flow:
    1. Validate source/target texts exist
    2. Check cache for previous results
    3. Process texts into units (lines or phrases)
    4. Generate stoplists based on frequency
    5. Find matching lemmas/words between texts
    6. Score matches using V3 algorithm
    7. Filter and sort results
    8. Return formatted results with highlighting
"""

# =============================================================================
# IMPORTS
# =============================================================================
from flask import Blueprint, jsonify, request, Response
from flask_login import current_user
import os
import json
import time
from backend.utils import resolve_text_path, format_short_locus

from backend.logging_config import get_logger
from backend.services import get_user_location, log_search
from backend.cache import get_cached_results, save_cached_results, clear_cache
from backend.concurrency_gate import SearchSlot, get_cancellation_message

from backend.matcher import get_curated_stoplists
from backend.search_cancellation import (
    SearchCancellation, SearchCancelled, request_cancellation,
)

logger = get_logger('search')


# =============================================================================
# BLUEPRINT SETUP
# =============================================================================
search_bp = Blueprint('search', __name__)

# Valid cross-lingual language pairs (order-independent; both directions supported)
VALID_CROSSLINGUAL_PAIRS = {
    frozenset(('grc', 'la')),
    frozenset(('la', 'en')),
    frozenset(('grc', 'en')),
}
# Coptic-Greek pair added unconditionally -- the corpus/text checks at search
# time handle the case where Coptic texts are not installed.
VALID_CROSSLINGUAL_PAIRS.add(frozenset(('cop', 'grc')))
# Hebrew cross-lingual pairs (Hebrew Bible -> Greek Septuagint, Hebrew Bible ->
# Latin Vulgate). Corpus/text checks at search time handle absence gracefully.
VALID_CROSSLINGUAL_PAIRS.add(frozenset(('he', 'grc')))
VALID_CROSSLINGUAL_PAIRS.add(frozenset(('he', 'la')))

# Module-level references to shared components (injected via init_search_blueprint)
_matcher = None       # Matcher: Finds parallel passages between texts
_scorer = None        # Scorer: Calculates V3-style similarity scores
_text_processor = None # TextProcessor: Tokenization and lemmatization
_texts_dir = None     # Path to corpus directory
_get_processed_units = None      # Function to get cached/processed text units
_get_corpus_frequencies = None   # Function to get word frequency data


def init_search_blueprint(matcher, scorer, text_processor, texts_dir, 
                          get_processed_units_fn, get_corpus_frequencies_fn):
    """
    Initialize blueprint with required dependencies.
    
    Called from app.py during startup to inject shared components.
    This pattern avoids circular imports while sharing state.
    """
    global _matcher, _scorer, _text_processor, _texts_dir
    global _get_processed_units, _get_corpus_frequencies
    _matcher = matcher
    _scorer = scorer
    _text_processor = text_processor
    _texts_dir = texts_dir
    _get_processed_units = get_processed_units_fn
    _get_corpus_frequencies = get_corpus_frequencies_fn


# =============================================================================
# SHARED SEARCH HELPERS
# =============================================================================

def _resolve_with_fallback(texts_dir, language, text_id):
    """Try resolving text path in the requested language first, then
    fall back to scanning all language directories dynamically.

    Returns (resolved_path, actual_language) or (None, None).
    """
    # Primary: try the requested language
    path = resolve_text_path(texts_dir, language, text_id)
    if path:
        return path, language

    # Fallback: scan all language directories dynamically
    try:
        available_langs = [
            d for d in os.listdir(texts_dir)
            if os.path.isdir(os.path.join(texts_dir, d)) and not d.startswith('.')
        ]
    except OSError:
        available_langs = ['la', 'grc', 'en']

    for alt_lang in available_langs:
        if alt_lang == language:
            continue
        path = resolve_text_path(texts_dir, alt_lang, text_id)
        if path:
            logger.warning(
                "Smart fallback: resolved '%s' from '%s' → '%s'",
                text_id, language, alt_lang
            )
            return path, alt_lang

    return None, None

def _parse_search_request(data):
    """Parse and validate a search request from either endpoint.

    Returns dict with source_id, target_id, language, source_language,
    target_language, settings, source_path, target_path, is_crosslingual.
    Raises ValueError for missing fields, FileNotFoundError for missing texts.
    """
    source_id = data.get('source')
    target_id = data.get('target')
    language = data.get('language', 'la')
    source_language = data.get('source_language', language)
    target_language = data.get('target_language', language)

    settings = data.get('settings', {})
    for key in ['match_type', 'min_matches', 'max_results', 'max_distance',
                'stoplist_basis', 'stoplist_size', 'source_unit_type', 'target_unit_type',
                'use_meter', 'use_pos', 'use_syntax', 'use_sound', 'use_edit_distance',
                'bigram_boost', 'custom_stopwords']:
        if key in data and key not in settings:
            settings[key] = data[key]

    if not source_id or not target_id:
        raise ValueError('Please select both source and target texts')

    # Language/Path resolution
    match_type = settings.get('match_type', 'lemma')
    is_crosslingual = match_type in ('semantic_cross', 'dictionary_cross', 'crosslingual_fusion')

    if is_crosslingual:
        source_language = data.get('source_language', 'la')
        target_language = data.get('target_language', 'la')
        source_path, source_language = _resolve_with_fallback(_texts_dir, source_language, source_id)
        target_path, target_language = _resolve_with_fallback(_texts_dir, target_language, target_id)
    else:
        source_path, resolved_src_lang = _resolve_with_fallback(_texts_dir, language, source_id)
        target_path, resolved_tgt_lang = _resolve_with_fallback(_texts_dir, language, target_id)
        if resolved_src_lang and resolved_tgt_lang:
            if resolved_src_lang == resolved_tgt_lang:
                source_language = resolved_src_lang
                target_language = resolved_tgt_lang
                language = resolved_src_lang
            else:
                raise ValueError(
                    f"Selected texts belong to different languages ('{resolved_src_lang}' and '{resolved_tgt_lang}'). "
                    f"Please select Cross-Language mode."
                )

    if not source_path or not target_path:
        raise FileNotFoundError('Text files not found')

    settings['language'] = language
    settings['source_language'] = source_language
    settings['target_language'] = target_language
    settings['source_text_path'] = source_path
    settings['target_text_path'] = target_path

    return {
        'source_id': source_id, 'target_id': target_id,
        'language': language, 'source_language': source_language,
        'target_language': target_language, 'settings': settings,
        'source_path': source_path, 'target_path': target_path,
        'is_crosslingual': is_crosslingual,
    }


def _load_units(params):
    """Load processed text units for source and target texts."""
    settings = params['settings']
    source_unit_type = settings.get('source_unit_type', 'line')
    target_unit_type = settings.get('target_unit_type', 'line')

    if params['is_crosslingual']:
        source_units = _get_processed_units(params['source_id'], params['source_language'], source_unit_type, _text_processor)
        target_units = _get_processed_units(params['target_id'], params['target_language'], target_unit_type, _text_processor)
    else:
        source_units = _get_processed_units(params['source_id'], params['language'], source_unit_type, _text_processor)
        target_units = _get_processed_units(params['target_id'], params['language'], target_unit_type, _text_processor)

    return source_units, target_units


def _load_corpus_frequencies(language, settings):
    """Load corpus frequencies if stoplist basis requires them."""
    stoplist_basis = settings.get('stoplist_basis', 'source_target')
    if stoplist_basis == 'corpus':
        freq_data = _get_corpus_frequencies(language, _text_processor)
        if freq_data:
            return freq_data.get('frequencies', {})
    return None


def _run_matcher(match_type, source_units, target_units, settings,
                 corpus_frequencies=None, cancellation=None):
    """Dispatch to the appropriate matcher based on match_type.

    Returns (matches, stoplist_size).
    Raises ValueError for cross-lingual types that need special handling.
    """
    if match_type == 'sound':
        return _matcher.find_sound_matches(source_units, target_units, settings,
                                           cancellation=cancellation)
    elif match_type == 'edit_distance':
        return _matcher.find_edit_distance_matches(source_units, target_units, settings,
                                                   cancellation=cancellation)
    elif match_type == 'semantic':
        from backend.semantic_similarity import find_semantic_matches
        return find_semantic_matches(source_units, target_units, settings, cancellation)
    elif match_type == 'dictionary':
        from backend.semantic_similarity import find_dictionary_matches
        return find_dictionary_matches(source_units, target_units, settings, cancellation)
    elif match_type in ('semantic_cross', 'dictionary_cross', 'crosslingual_fusion'):
        raise ValueError(f'Cross-lingual match type {match_type} requires special handling')
    else:
        return _matcher.find_matches(source_units, target_units, settings,
                                     corpus_frequencies, cancellation)


def _run_matcher_with_heartbeats(match_type, source_units, target_units,
                                 settings, corpus_frequencies, cancellation):
    """Run matching in a thread while making cancellation observable to SSE."""
    from concurrent.futures import ThreadPoolExecutor, TimeoutError

    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            future = pool.submit(
                _run_matcher, match_type, source_units, target_units,
                settings, corpus_frequencies, cancellation,
            )
            while True:
                try:
                    result = future.result(timeout=1)
                    yield ('result', result)
                    return
                except TimeoutError:
                    cancellation.check()
                    yield ('heartbeat', None)
        except GeneratorExit:
            # This runs before the executor context manager waits for its
            # worker, giving the matcher a chance to terminate child pools.
            cancellation.cancel()
            raise


def _finalize_results(scored_results, source_units, target_units, stoplist_size,
                      settings, source_id, target_id, language, req_user_id, req_city, req_country, req_ip, cached=False):
    """Cache results, log the search, and build the response dict."""
    if not cached:
        metadata = {
            'source_lines': len(source_units),
            'target_lines': len(target_units),
            'stoplist_size': stoplist_size,
        }
        save_cached_results(source_id, target_id, language, settings, scored_results, metadata)

    max_results = settings.get('max_results', 0)
    display_results = scored_results[:max_results] if max_results > 0 else scored_results

    match_type_raw = settings.get('match_type', 'lemma')
    match_labels = {
        'lemma': 'Dictionary Form (Lemma)', 'exact': 'Exact Match',
        'semantic': 'AI Semantic', 'v3_synonyms': 'Dictionary (V3 Synonyms)',
        'synonyms': 'Dictionary (V3 Synonyms)', 'sound': 'Sound Matching',
        'edit_distance': 'Edit Distance'
    }
    log_search(match_labels.get(match_type_raw, 'Dictionary Form (Lemma)'), language, source_id, target_id, None,
               match_type_raw, len(scored_results), cached, req_user_id,
               req_city, req_country, req_ip)

    return {
        "results": display_results,
        "total_matches": len(scored_results),
        "source_lines": len(source_units),
        "target_lines": len(target_units),
        "stoplist_size": stoplist_size,
        "cached": cached,
    }


def _handle_dictionary_cross(params, source_units, target_units, settings,
                             cancellation=None):
    """Handle dictionary_cross match type with custom IDF-based result building.

    Unlike other match types, dictionary_cross builds results directly from
    matches (already sorted by IDF score) rather than going through the scorer.
    """
    from backend.semantic_similarity import find_dictionary_crosslingual_matches

    source_id = params['source_id']
    target_id = params['target_id']
    language = params['language']

    greek_freq_data = _get_corpus_frequencies('grc', _text_processor)
    latin_freq_data = _get_corpus_frequencies('la', _text_processor)
    greek_frequencies = greek_freq_data.get('frequencies', {}) if greek_freq_data else {}
    latin_frequencies = latin_freq_data.get('frequencies', {}) if latin_freq_data else {}

    matches, stoplist_size = find_dictionary_crosslingual_matches(
        source_units, target_units, params['source_language'],
        params['target_language'], settings,
        greek_frequencies=greek_frequencies, latin_frequencies=latin_frequencies,
        cancellation=cancellation,
    )

    scored_results = []
    for m in matches:
        if cancellation:
            cancellation.check()
        src_unit = source_units[m['source_idx']]
        tgt_unit = target_units[m['target_idx']]
        src_tokens = src_unit.get('tokens', [])
        tgt_tokens = tgt_unit.get('tokens', [])
        src_original = src_unit.get('original_tokens', src_tokens)
        tgt_original = tgt_unit.get('original_tokens', tgt_tokens)

        matched_words_with_original = []
        for wm in m.get('word_matches', []):
            grc_indices = wm.get('greek_indices', [])
            lat_indices = wm.get('latin_indices', [])
            grc_original = (src_original[grc_indices[0]]
                            if grc_indices and grc_indices[0] < len(src_original)
                            else wm['greek_lemma'])
            lat_original_word = (tgt_original[lat_indices[0]]
                                 if lat_indices and lat_indices[0] < len(tgt_original)
                                 else wm['latin_lemma'])
            matched_words_with_original.append({
                'greek_word': grc_original,
                'latin_word': lat_original_word,
                'greek_lemma': wm.get('greek_lemma', ''),
                'latin_lemma': wm.get('latin_lemma', ''),
                'display': f"{grc_original}\u2192{lat_original_word}",
                'type': 'cross_lingual',
                'idf': wm.get('idf_score', 0)
            })

        scored_results.append({
            'source': {
                'ref': format_short_locus(src_unit.get('ref', '')),
                'text': src_unit.get('text', ''),
                'tokens': src_original,
                'highlight_indices': [idx for wm in m.get('word_matches', [])
                                      for idx in wm.get('greek_indices', [])]
            },
            'target': {
                'ref': format_short_locus(tgt_unit.get('ref', '')),
                'text': tgt_unit.get('text', ''),
                'tokens': tgt_original,
                'highlight_indices': [idx for wm in m.get('word_matches', [])
                                      for idx in wm.get('latin_indices', [])]
            },
            'matched_words': matched_words_with_original,
            'match_count': m.get('match_count', 0),
            'distance': m.get('distance', 0),
            'idf_score': m.get('idf_score', 0),
            'overall_score': m.get('overall_score', 0),
            'match_basis': 'dictionary_cross'
        })

    req_user_id = current_user.id if current_user and current_user.is_authenticated else None
    req_city, req_country, req_ip = get_user_location()

    return jsonify(_finalize_results(scored_results, source_units, target_units,
                                      0, settings, source_id, target_id, language, req_user_id, req_city, req_country, req_ip))


def _find_dictionary_matches_fast(source_units, target_units, source_language,
                                  target_language, cancellation=None):
    """Fast inverted-index dictionary matching for cross-lingual fusion.

    Dispatches to the correct dictionary based on language pair:
    - Greek + Latin: inverted-index over get_greek_latin_dict() + CURATED_GREEK_LATIN
    - Latin + English: per-line find_latin_english_matches()
    - Greek + English: per-line find_greek_english_matches()

    Returns dict keyed by (src_idx, tgt_idx) with word_matches list.
    All word match dicts use unified keys: source_lemma, target_lemma,
    source_indices, target_indices.
    """
    lang_pair = frozenset((source_language, target_language))

    # --- English language pairs: use per-line matching functions ---
    if 'en' in lang_pair:
        return _find_english_dictionary_matches(source_units, target_units,
                                                source_language, target_language,
                                                cancellation)

    # --- Coptic-Greek and Hebrew (he-grc / he-la) pairs: CSV dictionary path ---
    if 'cop' in lang_pair or 'he' in lang_pair:
        return _find_csv_dictionary_matches(source_units, target_units,
                                            source_language, target_language,
                                            cancellation)

    # --- Greek-Latin pair: fast inverted-index path (unchanged) ---
    return _find_greek_latin_dictionary_matches_fast(source_units, target_units,
                                                     source_language, target_language,
                                                     cancellation)


def _find_csv_dictionary_matches(source_units, target_units, source_language,
                                 target_language, cancellation=None):
    """Dictionary matching for Coptic-Greek using a CSV-based dictionary.

    Builds an inverted index on the target side, then scans source lemmas.
    Returns dict keyed by (src_idx, tgt_idx) with word_matches list.
    """
    import csv
    import unicodedata
    from collections import defaultdict

    lang_pair = frozenset((source_language, target_language))

    # Load the appropriate dictionary
    synonymy_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'synonymy', 'v6_additions')

    if lang_pair == frozenset(('he', 'la')):
        dict_path = os.path.join(synonymy_dir, 'hebrew_latin.csv')
        new_lang = 'he'
    elif 'he' in lang_pair:
        dict_path = os.path.join(synonymy_dir, 'hebrew_greek.csv')
        new_lang = 'he'
    elif 'cop' in lang_pair:
        dict_path = os.path.join(synonymy_dir, 'coptic_greek.csv')
        new_lang = 'cop'
    else:
        return {}

    # The second CSV column is the "other" language (Greek for he/cop, Latin for
    # the he-la bridge). Latin needs u/v folding and no Greek min-length filter.
    col2_lang = next((l for l in lang_pair if l != new_lang), None)

    if not os.path.exists(dict_path):
        logger.warning(f"Dictionary not found: {dict_path}")
        return {}

    # Load dictionary as bidirectional mapping
    # CSV format: word1, word2 (the new-language word is first, Greek is second)
    new_to_greek = defaultdict(set)
    greek_to_new = defaultdict(set)
    with open(dict_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 2:
                continue
            w1 = row[0].strip()
            w2 = row[1].strip()
            if w1.startswith('#'):
                continue  # skip CSV comment/header lines (hebrew_latin.csv has them)
            if w1 and w2 and len(w1) >= 2 and len(w2) >= 2:
                if col2_lang == 'la':
                    # Latin: fold u/v and j/i to match the Latin index; no Greek
                    # betacode min-length filter, so 2-letter Latin (os, eo) survives.
                    w2_norm = w2.lower().replace('v', 'u').replace('j', 'i')
                    ok = len(w2_norm) >= 2
                else:
                    # Greek: strip accents for matching
                    # Require min length 3 for Greek to filter CATSS betacode artifacts
                    w2_norm = unicodedata.normalize('NFC', w2)
                    w2_norm = ''.join(c for c in unicodedata.normalize('NFD', w2_norm)
                                      if unicodedata.category(c) != 'Mn').lower()
                    # Normalize terminal sigma ς (U+03C2) to medial σ (U+03C3)
                    # to match the index which uses medial sigma throughout
                    w2_norm = w2_norm.replace('ς', 'σ')
                    ok = len(w2_norm) >= 3
                if ok:
                    new_to_greek[w1].add(w2_norm)
                    greek_to_new[w2_norm].add(w1)

    logger.info(f"Loaded {len(new_to_greek)} {new_lang} entries from {dict_path}")

    # Cross-lingual stoplist: remove only the highest-frequency function words
    # that produce thousands of vacuous matches. The IDF-based scoring in the
    # fusion handler handles the rest -- content words get higher IDF and rank
    # above function words naturally. We only need to remove words so common
    # that they create massive noise in the match set itself.
    from backend.synonym_dict import CROSSLINGUAL_STOPLIST_GREEK, CROSSLINGUAL_STOPLIST_LATIN
    _GREEK_STOP = CROSSLINGUAL_STOPLIST_GREEK

    from backend import fusion

    # Coptic: curated function words
    _COPTIC_STOP = fusion._STOPLISTS.get('cop', set())

    # Build combined stoplists: start with fusion registry, then override
    # Greek with the richer CROSSLINGUAL_STOPLIST_GREEK which includes
    # articles, pronouns, prepositions, particles
    lang_stops = dict(fusion._STOPLISTS)
    lang_stops['grc'] = _GREEK_STOP  # override with cross-lingual stoplist
    lang_stops['la'] = CROSSLINGUAL_STOPLIST_LATIN  # filter Latin function words (he-la bridge)

    if source_language == new_lang:
        src_dict = new_to_greek
    else:
        src_dict = greek_to_new

    src_stop = lang_stops.get(source_language, set())
    tgt_stop = lang_stops.get(target_language, set())

    # Build inverted index on target side
    target_index = defaultdict(list)
    for ti, unit in enumerate(target_units):
        if cancellation:
            cancellation.check()
        for pos, lemma in enumerate(unit.get('lemmas', [])):
            # Normalize sigma for consistent matching
            lemma_n = lemma.replace('ς', 'σ') if lemma else lemma
            if target_language == 'la' and lemma_n:
                lemma_n = lemma_n.lower().replace('v', 'u').replace('j', 'i')
            if lemma_n in tgt_stop or len(lemma_n) < 2:
                continue
            target_index[lemma_n].append((ti, pos))

    # Scan source units and find matches
    results = defaultdict(list)
    for si, unit in enumerate(source_units):
        if cancellation:
            cancellation.check()
        for src_pos, src_lemma in enumerate(unit.get('lemmas', [])):
            src_key = src_lemma
            if source_language == 'la' and src_key:
                src_key = src_key.lower().replace('v', 'u').replace('j', 'i')
            if src_key in src_stop or len(src_key) < 2:
                continue
            translations = src_dict.get(src_key, set())
            for translation in translations:
                if translation in tgt_stop:
                    continue
                if translation in target_index:
                    for ti, tgt_pos in target_index[translation]:
                        key = (si, ti)
                        results[key].append({
                            'source_lemma': src_lemma,
                            'target_lemma': translation,
                            'source_indices': [src_pos],
                            'target_indices': [tgt_pos],
                        })

    logger.info(f"Dictionary found {len(results)} pairs (minimal stoplist filtering)")
    return dict(results)


def _find_english_dictionary_matches(source_units, target_units, source_language,
                                     target_language, cancellation=None):
    """Fast inverted-index dictionary matching for English language pairs.

    Builds an inverted index on the English side's lemmas, then for each
    classical-language lemma looks up its English translations and finds
    which target/source lines contain them.  Returns dict keyed by
    (src_idx, tgt_idx) with word_matches list using unified keys.
    """
    import unicodedata
    from backend.synonym_dict import (get_latin_english_dict, get_greek_english_dict,
                                       CROSSLINGUAL_STOPLIST_ENGLISH,
                                       CROSSLINGUAL_STOPLIST_LATIN,
                                       CROSSLINGUAL_STOPLIST_GREEK, _normalize_greek)

    lang_pair = frozenset((source_language, target_language))

    # Determine which side is English vs classical
    if source_language == 'en':
        en_units, cl_units = source_units, target_units
        en_is_source = True
        cl_language = target_language
    else:
        en_units, cl_units = target_units, source_units
        en_is_source = False
        cl_language = source_language

    # Load the correct dictionary
    if cl_language == 'la':
        cl_dict = get_latin_english_dict()  # latin_lemma -> set of english words
        cl_stoplist = CROSSLINGUAL_STOPLIST_LATIN
    else:  # grc
        cl_dict = get_greek_english_dict()  # greek_norm -> set of english words
        cl_stoplist = CROSSLINGUAL_STOPLIST_GREEK

    # Build inverted index: english_lemma_lower -> [(unit_idx, token_position), ...]
    en_lemma_index = {}
    for en_idx, unit in enumerate(en_units):
        if cancellation:
            cancellation.check()
        for pos, lemma in enumerate(unit.get('lemmas', [])):
            ln = lemma.lower()
            if ln in CROSSLINGUAL_STOPLIST_ENGLISH:
                continue
            en_lemma_index.setdefault(ln, []).append((en_idx, pos))

    pair_matches = {}

    for cl_idx, cl_unit in enumerate(cl_units):
        if cancellation:
            cancellation.check()
        cl_lemmas = cl_unit.get('lemmas', [])
        for cl_pos, cl_lemma in enumerate(cl_lemmas):
            # Normalize the classical lemma for dictionary lookup
            if cl_language == 'la':
                cl_norm = cl_lemma.lower().replace('v', 'u')
                if cl_norm in cl_stoplist:
                    continue
                translations = cl_dict.get(cl_norm, set()) | cl_dict.get(cl_lemma.lower(), set())
            else:  # grc
                cl_norm = _normalize_greek(cl_lemma).replace('ς', 'σ')
                if cl_norm in cl_stoplist:
                    continue
                translations = cl_dict.get(cl_norm, set())

            if not translations:
                continue

            for en_word in translations:
                if en_word in CROSSLINGUAL_STOPLIST_ENGLISH:
                    continue
                hits = en_lemma_index.get(en_word)
                if not hits:
                    continue
                for en_idx, en_pos in hits:
                    if en_is_source:
                        key = (en_idx, cl_idx)
                        wm = {
                            'source_lemma': en_word,
                            'target_lemma': cl_norm,
                            'source_indices': [en_pos],
                            'target_indices': [cl_pos],
                        }
                    else:
                        key = (cl_idx, en_idx)
                        wm = {
                            'source_lemma': cl_norm,
                            'target_lemma': en_word,
                            'source_indices': [cl_pos],
                            'target_indices': [en_pos],
                        }
                    pair_matches.setdefault(key, []).append(wm)

    # Deduplicate: collapse multiple hits of same lemma pair per line pair
    for key in pair_matches:
        if cancellation:
            cancellation.check()
        seen = {}
        deduped = []
        for wm in pair_matches[key]:
            pair_key = (wm['source_lemma'], wm['target_lemma'])
            if pair_key not in seen:
                seen[pair_key] = wm
                deduped.append(wm)
            else:
                existing = seen[pair_key]
                for si in wm['source_indices']:
                    if si not in existing['source_indices']:
                        existing['source_indices'].append(si)
                for ti in wm['target_indices']:
                    if ti not in existing['target_indices']:
                        existing['target_indices'].append(ti)
        pair_matches[key] = deduped

    logger.info(f"English dictionary found {len(pair_matches)} pairs ({source_language}->{target_language})")
    return pair_matches


def _find_greek_latin_dictionary_matches_fast(source_units, target_units,
                                              source_language, target_language,
                                              cancellation=None):
    """Fast inverted-index dictionary matching for Greek-Latin pairs.

    Builds an inverted index of Latin lemmas, then for each Greek lemma looks
    up translations and finds which target lines contain them.  Returns dict
    keyed by (src_idx, tgt_idx) with word_matches list using unified keys
    (source_lemma, target_lemma, source_indices, target_indices).
    """
    import unicodedata
    from backend.synonym_dict import get_greek_latin_dict, CURATED_GREEK_LATIN, \
        CROSSLINGUAL_STOPLIST_GREEK, CROSSLINGUAL_STOPLIST_LATIN

    _, gl_dict_norm = get_greek_latin_dict()

    def strip_accents(s):
        nfd = unicodedata.normalize('NFD', s.lower())
        return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')

    # Determine which side is Greek, which is Latin
    if source_language == 'grc' and target_language == 'la':
        grc_units, lat_units = source_units, target_units
        grc_is_source = True
    else:
        grc_units, lat_units = target_units, source_units
        grc_is_source = False

    # Build inverted index: latin_lemma_norm -> set of (unit_idx, token_position)
    lat_lemma_index = {}
    for tgt_idx, unit in enumerate(lat_units):
        if cancellation:
            cancellation.check()
        for pos, lemma in enumerate(unit.get('lemmas', [])):
            ln = lemma.lower()
            if ln in CROSSLINGUAL_STOPLIST_LATIN:
                continue
            lat_lemma_index.setdefault(ln, []).append((tgt_idx, pos))

    # For each Greek unit, look up translations and find target hits
    pair_matches = {}  # (src_idx, tgt_idx) -> list of word match dicts

    for grc_idx, grc_unit in enumerate(grc_units):
        if cancellation:
            cancellation.check()
        grc_lemmas = grc_unit.get('lemmas', [])
        for grc_pos, grc_lemma in enumerate(grc_lemmas):
            grc_norm = strip_accents(grc_lemma)
            if grc_norm in CROSSLINGUAL_STOPLIST_GREEK:
                continue

            # Get all Latin translations for this Greek lemma
            # Normalize final sigma (ς→σ) to match CURATED_GREEK_LATIN key convention
            grc_lookup = grc_norm.replace('ς', 'σ')
            translations = set()
            curated = CURATED_GREEK_LATIN.get(grc_lookup, [])
            if curated:
                # Normalize v→u to match text processor's Latin lemmas (which use u)
                translations.update(w.lower().replace('v', 'u') for w in curated)
            dict_trans = gl_dict_norm.get(grc_norm, set()) or gl_dict_norm.get(grc_lookup, set()) if gl_dict_norm else set()
            if dict_trans:
                translations.update(w.lower().replace('v', 'u') for w in dict_trans)

            if not translations:
                continue

            # Look up which target lines contain these translations
            for lat_lemma in translations:
                if lat_lemma in CROSSLINGUAL_STOPLIST_LATIN:
                    continue
                hits = lat_lemma_index.get(lat_lemma)
                if not hits:
                    continue
                for lat_idx, lat_pos in hits:
                    if grc_is_source:
                        key = (grc_idx, lat_idx)
                    else:
                        key = (lat_idx, grc_idx)

                    wm = {
                        'source_lemma': grc_norm if grc_is_source else lat_lemma,
                        'target_lemma': lat_lemma if grc_is_source else grc_norm,
                        'source_indices': [grc_pos] if grc_is_source else [lat_pos],
                        'target_indices': [lat_pos] if grc_is_source else [grc_pos],
                        # Legacy keys for backward compatibility in Greek-Latin path
                        'greek_lemma': grc_norm,
                        'latin_lemma': lat_lemma,
                        'greek_indices': [grc_pos],
                        'latin_indices': [lat_pos],
                    }
                    pair_matches.setdefault(key, []).append(wm)

    # Deduplicate: collapse multiple hits of same lemma pair per line pair
    for key in pair_matches:
        if cancellation:
            cancellation.check()
        seen = {}
        deduped = []
        for wm in pair_matches[key]:
            pair_key = (wm['source_lemma'], wm['target_lemma'])
            if pair_key not in seen:
                seen[pair_key] = wm
                deduped.append(wm)
            else:
                # Merge indices
                existing = seen[pair_key]
                for si in wm['source_indices']:
                    if si not in existing['source_indices']:
                        existing['source_indices'].append(si)
                for ti in wm['target_indices']:
                    if ti not in existing['target_indices']:
                        existing['target_indices'].append(ti)
                if 'greek_indices' in wm:
                    for gi in wm['greek_indices']:
                        if gi not in existing.get('greek_indices', []):
                            existing.setdefault('greek_indices', []).append(gi)
                if 'latin_indices' in wm:
                    for li in wm['latin_indices']:
                        if li not in existing.get('latin_indices', []):
                            existing.setdefault('latin_indices', []).append(li)
        pair_matches[key] = deduped

    return pair_matches


def _longest_translated_run(word_matches):
    """Length of the longest 'translated run' in a pair's dictionary matches.

    A translated run is a diagonal run of matched positions -- consecutive on the
    SOURCE side and consecutive on the TARGET side -- i.e. a stretch of words whose
    translations appear in the same order in the target. It is the cross-lingual
    analog of the verbatim-quotation channel: a run of 3 translated-in-order words is
    intrinsically distinctive and, unlike bag-of-words overlap, is not inflated by a
    long candidate verse. This is fully language-agnostic: it reads only the matched
    positions the generic dictionary channel already records, so it serves every
    cross-lingual pair (he-grc, he-la, cop-grc, grc-la) with no per-language code.
    """
    pairs = set()
    for wm in word_matches or ():
        for sp in (wm.get('source_indices') or []):
            for tp in (wm.get('target_indices') or []):
                pairs.add((sp, tp))
    if not pairs:
        return 0
    best = 1
    for sp, tp in pairs:
        k = 1
        while (sp + k, tp + k) in pairs:
            k += 1
        if k > best:
            best = k
    return best


def _lxx_pivot_core(params, source_units, target_units, settings):
    """Answer a Hebrew-Greek search through the Septuagint. See backend/lxx_pivot.

    The New Testament quotes the SEPTUAGINT, not the Hebrew, so a biblical
    he-grc search is better answered Greek-to-Greek against the LXX and mapped
    back to the Hebrew verse by versification. Measured 2026-08-27 on the 22
    formula-marked Isaiah citations in Romans: direct route 0 of 22 in the top
    100, pivot with the biblical_greek profile 15 of 22, 8 in the top ten
    (backend/lxx_pivot.py carries the full account).

    Returns a plain dict (this runs inside the request-free core), or None to
    signal "no routed counterpart, use the direct route." Every result keeps
    the Septuagint line visible and carries the Hebrew reference and text it
    translates: a reader shown a match "in Hebrew" that was found in Greek
    must be able to see the Greek.
    """
    import re as _re
    from backend import lxx_pivot
    from backend.text_processor import TextProcessor
    from backend.matcher import Matcher
    from backend.scorer import Scorer
    from backend.fusion import iter_fusion_search

    source_language = params['source_language']
    he_side = 'source' if source_language == 'he' else 'target'
    he_id = params['source_id'] if he_side == 'source' else params['target_id']
    grc_id = params['target_id'] if he_side == 'source' else params['source_id']

    counterpart = lxx_pivot.lxx_counterpart(he_id)
    if not counterpart:
        return None
    lxx_path = os.path.join(_texts_dir, 'grc', counterpart + '.tess')
    if not os.path.exists(lxx_path):
        logger.info(f"[LXX_PIVOT] counterpart file missing, direct route: {lxx_path}")
        return None
    logger.info(f"[LXX_PIVOT] routing {he_id} x {grc_id} through {counterpart}")

    tp = TextProcessor()
    lxx_units = tp.process_file(lxx_path, language='grc')
    grc_units = target_units if he_side == 'source' else source_units

    if he_side == 'source':
        s_units, t_units = lxx_units, grc_units
        s_id, t_id = counterpart + '.tess', grc_id
        s_path, t_path = lxx_path, params['target_path']
    else:
        s_units, t_units = grc_units, lxx_units
        s_id, t_id = grc_id, counterpart + '.tess'
        s_path, t_path = params['source_path'], lxx_path

    results = []
    for evt, data in iter_fusion_search(
            source_units=s_units, target_units=t_units,
            matcher=Matcher(), scorer=Scorer(),
            source_id=s_id, target_id=t_id,
            language='grc', mode='merged',
            max_results=settings.get('max_results', 5000),
            source_path=s_path, target_path=t_path,
            user_settings={'weights_profile': 'biblical_greek'}):
        if evt == 'complete':
            results = data.get('results', [])

    lxx_pivot.annotate_results(results, he_id, he_side)

    # Attach the Hebrew line text beside each Hebrew reference, so the UI can
    # show the verse itself rather than only a pointer.
    he_path = params['source_path'] if he_side == 'source' else params['target_path']
    he_lines = {}
    try:
        with open(he_path, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                m = _re.match(r'^<([^>]*)>\t?(.*)$', line)
                if m:
                    he_lines.setdefault(m.group(1).strip(), m.group(2).strip())
    except OSError as e:
        logger.warning(f"[LXX_PIVOT] could not read Hebrew text: {e}")
    for r in results:
        half = r.get(he_side)
        if isinstance(half, dict) and half.get('hebrew_ref') in he_lines:
            half['hebrew_text'] = he_lines[half['hebrew_ref']]

    return {
        'results': results,
        'total_results': len(results),
        'via_septuagint': True,
        'septuagint_text': counterpart,
        'weights_profile': 'biblical_greek',
        'note': ('This Hebrew-Greek search was answered through the Septuagint: '
                 'the Greek side was searched against the Septuagint text of the '
                 'Hebrew book, and each result carries the Hebrew verse that '
                 'Septuagint line translates.'),
    }


def _handle_crosslingual_fusion(params, source_units, target_units, settings,
                                cancellation=None):
    """HTTP wrapper around :func:`_crosslingual_fusion_core`.

    Pulls the request-scoped user/location metadata (only available inside a
    Flask request) and hands it to the core, then jsonifies the plain dict the
    core returns. The core itself is request-free so the poll-able GET endpoint
    can run it in a background thread.
    """
    req_user_id = current_user.id if current_user and current_user.is_authenticated else None
    req_city, req_country, req_ip = get_user_location()
    core = _crosslingual_fusion_core(
        params, source_units, target_units, settings, cancellation,
        req_meta=(req_user_id, req_city, req_country, req_ip))
    return jsonify(core)


def _crosslingual_fusion_core(params, source_units, target_units, settings,
                              cancellation=None, req_meta=None):
    """Multi-channel cross-lingual fusion: semantic + dictionary + syntax + phonetic.

    Supports Greek-Latin, Latin-English, and Greek-English pairs.
    Phonetic channel (Greek-Latin only): transliterates Greek → Latin alphabet,
    then runs token-level edit distance to catch phonetic echoes (e.g. μῆνιν/mene).
    Runs all applicable channels, merges by (source_idx, target_idx), and
    applies a convergence bonus when multiple channels fire on the same pair.

    Request-free: returns a plain dict (never a Flask response), so it can run
    both inside an HTTP request (via :func:`_handle_crosslingual_fusion`) and in
    a background poll thread (via the crosslingual-search-poll endpoint).
    ``req_meta`` is an optional (user_id, city, country, ip) tuple for search
    logging; it defaults to all-None when no request context is available.
    """
    import math
    from backend.semantic_similarity import find_crosslingual_matches

    if cancellation:
        cancellation.check()

    source_id = params['source_id']
    target_id = params['target_id']
    language = params['language']
    source_language = params['source_language']
    target_language = params['target_language']
    min_matches = settings.get('min_matches', 1)

    # Two-lemma gate (Bernstein 2026-05-20). Scholar review of Iliad x Aeneid
    # output identified single-common-lemma matches (e.g. gerwn -> grandaevus,
    # koiranos -> rex) as noise at the top of the ranked list. The gate
    # excludes or penalises cross-lingual pairs whose distinct lemma-match
    # count is below a threshold (default 2). Three modes:
    #   'exclude' (default): drop below-threshold pairs entirely. Applied to
    #     both scholar-facing benchmark CSVs and user-facing search, since the
    #     scholar verdict is consistent: single-lemma matches are noise.
    #   'penalty': multiply the pair's fused score by a factor (default 0.5)
    #     so single-lemma pairs sink below multi-lemma pairs but stay visible
    #     to users who scroll. Available for callers who want softer filtering
    #     than the default.
    #   'off': no gate; preserves the pre-2026-05-20 behaviour.
    crosslingual_min_lemma_matches = settings.get('crosslingual_min_lemma_matches', 2)
    crosslingual_lemma_gate = settings.get('crosslingual_lemma_gate', 'exclude')
    crosslingual_penalty_factor = settings.get('crosslingual_penalty_factor', 0.5)
    if crosslingual_lemma_gate not in ('penalty', 'exclude', 'off'):
        crosslingual_lemma_gate = 'exclude'

    lang_pair = frozenset((source_language, target_language))
    if lang_pair not in VALID_CROSSLINGUAL_PAIRS:
        return {"error": f"Unsupported cross-lingual pair: {source_language} -> {target_language}. "
                f"Supported: grc-la, la-en, grc-en"}

    # --- Septuagint pivot for Hebrew-Greek biblical pairs ---
    # Falls through to the direct route when the Hebrew text has no routed
    # Septuagint counterpart, or when disabled (TESSERAE_LXX_PIVOT=0).
    if (lang_pair == frozenset(('he', 'grc'))
            and os.environ.get('TESSERAE_LXX_PIVOT', '1') not in ('0', 'false', 'no')):
        pivot_out = _lxx_pivot_core(params, source_units, target_units, settings)
        if pivot_out is not None:
            return pivot_out

    is_greek_latin = lang_pair == frozenset(('grc', 'la'))
    has_english = 'en' in lang_pair

    # --- Channel 1: Semantic (SPhilBERTa cosine) ---
    sem_settings = {**settings, 'max_results': 2000, 'semantic_top_n': 20}
    sem_matches, _ = find_crosslingual_matches(
        source_units, target_units,
        source_language, target_language, sem_settings, cancellation)

    # Index semantic results by pair key
    sem_by_pair = {}
    for m in sem_matches:
        if cancellation:
            cancellation.check()
        key = (m['source_idx'], m['target_idx'])
        sem_by_pair[key] = m.get('semantic_score', 0.0)

    # --- Channel 2: Dictionary (dispatched by language pair) ---
    logger.info("Running fast dictionary matching...")
    dict_by_pair = _find_dictionary_matches_fast(
        source_units, target_units,
        source_language, target_language, cancellation)
    logger.info(f"Dictionary found {len(dict_by_pair)} pairs with matches")

    # --- Semantic recovery for dictionary-only pairs ---
    # Dictionary pairs not found by the semantic channel (filtered by top-N cap)
    # get their actual cosine looked up from pre-computed embeddings.
    # Note: phonetic-only pairs are NOT recovered here — they're too numerous.
    # Phonetic acts only as a convergence booster on pairs already found by
    # semantic or dictionary.
    recovery_keys = set(dict_by_pair.keys()) - set(sem_by_pair.keys())
    if recovery_keys:
        try:
            from backend.embedding_storage import load_embeddings
            import numpy as np
            src_path = settings.get('source_text_path')
            tgt_path = settings.get('target_text_path')
            src_emb = load_embeddings(src_path, source_language) if src_path else None
            tgt_emb = load_embeddings(tgt_path, target_language) if tgt_path else None
            if src_emb is not None and tgt_emb is not None:
                src_emb = src_emb[:len(source_units)]
                tgt_emb = tgt_emb[:len(target_units)]
                # Normalise
                src_norms = np.linalg.norm(src_emb, axis=1, keepdims=True)
                tgt_norms = np.linalg.norm(tgt_emb, axis=1, keepdims=True)
                src_emb = src_emb / (src_norms + 1e-8)
                tgt_emb = tgt_emb / (tgt_norms + 1e-8)
                recovered = 0
                for key in recovery_keys:
                    if cancellation:
                        cancellation.check()
                    si, ti = key
                    if si < len(src_emb) and ti < len(tgt_emb):
                        cosine = float(np.dot(src_emb[si], tgt_emb[ti]))
                        if cosine > 0.4:
                            sem_by_pair[key] = cosine
                            recovered += 1
                logger.info(f"Semantic recovery: {recovered}/{len(recovery_keys)} dictionary-only pairs got cosine scores")
        except SearchCancelled:
            raise
        except Exception as e:
            logger.error(f"Semantic recovery failed: {e}")

    # --- Local IDF from source+target texts (avoids slow corpus freq lookup) ---
    import unicodedata
    def strip_accents(s):
        nfd = unicodedata.normalize('NFD', s.lower())
        return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')

    # Determine which side needs accent-stripping for IDF lookup
    source_needs_accent_strip = source_language == 'grc'
    target_needs_accent_strip = target_language == 'grc'

    # Count document frequency: how many lines contain each lemma
    doc_freq = {}
    for unit in source_units:
        if cancellation:
            cancellation.check()
        seen = set()
        for lemma in unit.get('lemmas', []):
            norm = strip_accents(lemma) if source_needs_accent_strip else lemma.lower()
            if norm not in seen:
                doc_freq[norm] = doc_freq.get(norm, 0) + 1
                seen.add(norm)
    for unit in target_units:
        if cancellation:
            cancellation.check()
        seen = set()
        for lemma in unit.get('lemmas', []):
            norm = strip_accents(lemma) if target_needs_accent_strip else lemma.lower()
            if norm not in seen:
                doc_freq[norm] = doc_freq.get(norm, 0) + 1
                seen.add(norm)
    total_docs = len(source_units) + len(target_units)

    def calc_idf(lemma, needs_accent_strip=False):
        key = strip_accents(lemma) if needs_accent_strip else lemma.lower()
        df = doc_freq.get(key, 1)
        return math.log((total_docs + 1) / (df + 1)) + 1

    # Build ref->index maps for syntax channel
    src_ref_to_idx = {u.get('ref', ''): i for i, u in enumerate(source_units)}
    tgt_ref_to_idx = {u.get('ref', ''): i for i, u in enumerate(target_units)}

    # --- Channel 3: Syntax (structural fingerprint matching) ---
    # UD dependency labels are language-independent, so cross-lingual matching
    # works directly between Greek and Latin syntax DBs.
    # English does not have a syntax DB yet, so skip for English pairs.
    syntax_by_pair = {}
    if not has_english:
        try:
            from backend.fusion import find_syntax_matches
            syntax_results = find_syntax_matches(
                source_units, target_units, source_id, target_id,
                min_score=0.1, max_results=50000,
                source_language=source_language,
                target_language=target_language,
                cancellation=cancellation,
            )
            # syntax_results is a dict: {"syntax": [...], "syntax_structural": [...]}
            if isinstance(syntax_results, dict):
                for sub_ch, sub_results in syntax_results.items():
                    if sub_results:
                        for r in sub_results:
                            src_ref = r.get('source', {}).get('ref', '')
                            tgt_ref = r.get('target', {}).get('ref', '')
                            score = r.get('score', r.get('overall_score', 0))
                            # Map refs back to unit indices
                            si = src_ref_to_idx.get(src_ref)
                            ti = tgt_ref_to_idx.get(tgt_ref)
                            if si is not None and ti is not None:
                                pair_key = (si, ti)
                                if score > syntax_by_pair.get(pair_key, 0):
                                    syntax_by_pair[pair_key] = score
                total_syntax = sum(len(v) for v in syntax_results.values() if v)
                logger.info(f"Syntax found {total_syntax} matches ({len(syntax_by_pair)} unique pairs)")
            else:
                logger.info("Syntax returned no results")
        except SearchCancelled:
            raise
        except Exception as e:
            logger.error(f"Syntax channel failed (may not have syntax DB): {e}")

    # --- Channel 4: Cross-lingual phonetic (transliteration + edit distance) ---
    # Greek-Latin: transliterate Greek → Latin alphabet, then compare tokens
    # by edit distance to catch phonetic echoes (e.g. μῆνιν / mene).
    # Coptic-Greek: transliterate Coptic → Greek alphabet, same idea — most
    # Coptic letters map identically to Greek, only 7 are Coptic-specific.
    phonetic_by_pair = {}
    is_coptic_greek = lang_pair == frozenset(('cop', 'grc'))
    if is_greek_latin:
        try:
            from backend.matcher import find_crosslingual_phonetic_matches
            phonetic_by_pair = find_crosslingual_phonetic_matches(
                source_units, target_units,
                source_language, target_language,
                min_similarity=0.60, min_token_len=3,
                cancellation=cancellation)
            logger.info(f"Phonetic found {len(phonetic_by_pair)} pairs with transliteration matches")
        except SearchCancelled:
            raise
        except Exception as e:
            logger.error(f"Phonetic channel failed: {e}")
    elif is_coptic_greek:
        try:
            from backend.matcher import find_crosslingual_phonetic_matches_cop_grc
            phonetic_by_pair = find_crosslingual_phonetic_matches_cop_grc(
                source_units, target_units,
                source_language, target_language,
                min_similarity=0.65, min_token_len=3)
            logger.info(f"Phonetic (cop-grc) found {len(phonetic_by_pair)} pairs with transliteration matches")
        except Exception as e:
            logger.error(f"Phonetic (cop-grc) channel failed: {e}")

    # --- Merge ---
    # Phonetic alone is too noisy (thousands of false positives from short-word
    # coincidences).  Only include phonetic pairs that also have semantic,
    # dictionary, or syntax support.  Semantic recovery above ensures phonetic
    # pairs with cosine > 0.4 get sem_by_pair entries, so they participate.
    all_keys = set(sem_by_pair.keys()) | set(dict_by_pair.keys()) | set(syntax_by_pair.keys())

    SEMANTIC_WEIGHT = 1.2
    DICTIONARY_WEIGHT = 2.0
    SYNTAX_WEIGHT = 0.5
    # Phonetic is a convergence booster only: phonetic-only pairs never enter the
    # fusion (all_keys is built from semantic/dict/syntax keys), so this weight only
    # ever nudges pairs that already have another channel. At the old 1.5 a phonetic
    # similarity of ~0.8-0.95 added ~1.2-1.4, rivaling DICTIONARY_WEIGHT (2.0) and
    # letting trivial echoes (ἅλα≈mari) outrank genuine dictionary calques. Dropped
    # to 0.5 (the syntax-booster tier) so phonetic breaks ties toward cross-script
    # echoes without dominating the dictionary/semantic signal.
    PHONETIC_WEIGHT = 0.5
    # Translated-run boost: a run of consecutive words whose translations appear in
    # order in the target is a near-certain alignment and is length-robust (see
    # _longest_translated_run). Additive: it only ever boosts a pair, so it cannot
    # regress recall. Tunable, like the weights above; generic across all pairs.
    RUN_WEIGHT = float(settings.get('crosslingual_run_weight', 3.0)) if settings else 3.0
    CONVERGENCE_BONUS = 0.5  # additive bonus when multiple channels fire

    fused = []
    for key in all_keys:
        if cancellation:
            cancellation.check()
        src_idx, tgt_idx = key
        cosine = sem_by_pair.get(key, 0.0)
        dict_wms = dict_by_pair.get(key)  # list of word match dicts or None

        has_semantic = cosine > 0
        has_dict = dict_wms is not None
        syntax_score = syntax_by_pair.get(key, 0.0)
        has_syntax = syntax_score > 0
        phonetic_matches = phonetic_by_pair.get(key)
        has_phonetic = phonetic_matches is not None and len(phonetic_matches) > 0

        # Count unique words per side for dict matches
        dict_word_count = 0
        avg_idf = 0.0
        if has_dict:
            unique_src = set(wm.get('source_lemma', wm.get('greek_lemma', '')) for wm in dict_wms)
            unique_tgt = set(wm.get('target_lemma', wm.get('latin_lemma', '')) for wm in dict_wms)
            dict_word_count = min(len(unique_src), len(unique_tgt))

            # Compute average IDF
            total_idf = 0.0
            for wm in dict_wms:
                src_lemma = wm.get('source_lemma', wm.get('greek_lemma', ''))
                tgt_lemma = wm.get('target_lemma', wm.get('latin_lemma', ''))
                si_idf = calc_idf(src_lemma, needs_accent_strip=source_needs_accent_strip)
                ti_idf = calc_idf(tgt_lemma, needs_accent_strip=target_needs_accent_strip)
                wm['idf_score'] = (si_idf + ti_idf) / 2
                total_idf += wm['idf_score']
            avg_idf = total_idf / len(dict_wms) if dict_wms else 0

        # Dictionary score: avg_idf scaled by match count (multiple rare matches >> 1 common)
        dict_score = (min(avg_idf / 10.0, 1.0) * math.sqrt(dict_word_count)) if has_dict else 0.0

        # Apply min_matches filter: pairs below the dictionary threshold are excluded
        if has_dict and dict_word_count < min_matches:
            has_dict = False
            dict_score = 0.0
            dict_word_count = 0
            dict_wms = None
        if not has_dict and min_matches > 1:
            continue  # User requires dictionary confirmation; skip semantic-only pairs

        # Two-lemma gate (see header comment). Record gate state before the
        # legacy min_matches filter has zeroed dict_word_count, so the gate
        # decision uses the original lemma count.
        gate_lemma_count = dict_word_count
        lemma_gate_triggered = gate_lemma_count < crosslingual_min_lemma_matches
        if lemma_gate_triggered and crosslingual_lemma_gate == 'exclude':
            continue

        # Phonetic score: average similarity of matched token pairs
        phonetic_score = 0.0
        if has_phonetic:
            phonetic_score = sum(m['similarity'] for m in phonetic_matches) / len(phonetic_matches)

        # Skip pairs with no channel
        if not has_semantic and not has_dict and not has_syntax and not has_phonetic:
            continue

        # Translated-run boost: longest run of in-order translated words in this pair
        # (cross-lingual quotation analog). A run of 2+ is distinctive; cap at 6.
        run_len = _longest_translated_run(dict_wms)
        run_score = (min(run_len, 6) / 6.0) if run_len >= 2 else 0.0

        # Fused score (additive, matching article formula)
        score = ((cosine * SEMANTIC_WEIGHT) + (dict_score * DICTIONARY_WEIGHT)
                 + (syntax_score * SYNTAX_WEIGHT) + (phonetic_score * PHONETIC_WEIGHT)
                 + (run_score * RUN_WEIGHT))
        n_channels = ((1 if has_semantic else 0) + (1 if has_dict else 0)
                      + (1 if has_syntax else 0) + (1 if has_phonetic else 0))
        if n_channels >= 2:
            score += CONVERGENCE_BONUS

        # Apply two-lemma gate penalty (soft-mode) after the score is composed.
        if lemma_gate_triggered and crosslingual_lemma_gate == 'penalty':
            score *= crosslingual_penalty_factor

        # Build result
        src_unit = source_units[src_idx]
        tgt_unit = target_units[tgt_idx]
        src_tokens = src_unit.get('tokens', [])
        tgt_tokens = tgt_unit.get('tokens', [])
        src_original = src_unit.get('original_tokens', src_tokens)
        tgt_original = tgt_unit.get('original_tokens', tgt_tokens)

        # Get word-level matches for highlighting
        matched_words = []
        source_highlights = []
        target_highlights = []

        if has_dict:
            for wm in dict_wms:
                # Use unified keys (source_indices/target_indices), fall back to
                # legacy greek_indices/latin_indices for Greek-Latin path
                s_indices = wm.get('source_indices')
                t_indices = wm.get('target_indices')
                if s_indices is None:
                    # Legacy Greek-Latin word match dicts
                    grc_indices = wm.get('greek_indices', [])
                    lat_indices = wm.get('latin_indices', [])
                    if source_language == 'grc':
                        s_indices, t_indices = grc_indices, lat_indices
                    else:
                        s_indices, t_indices = lat_indices, grc_indices

                src_lemma = wm.get('source_lemma', wm.get('greek_lemma', ''))
                tgt_lemma = wm.get('target_lemma', wm.get('latin_lemma', ''))

                src_word = (src_original[s_indices[0]]
                            if s_indices and s_indices[0] < len(src_original)
                            else src_lemma)
                tgt_word = (tgt_original[t_indices[0]]
                            if t_indices and t_indices[0] < len(tgt_original)
                            else tgt_lemma)
                mw_entry = {
                    'source_word': src_word,
                    'target_word': tgt_word,
                    'source_lemma': src_lemma,
                    'target_lemma': tgt_lemma,
                    'display': f"{src_word}\u2192{tgt_word}",
                    'type': 'cross_lingual',
                    'idf': wm.get('idf_score', 0)
                }
                # Preserve legacy keys for Greek-Latin frontend compatibility
                if is_greek_latin:
                    mw_entry['greek_word'] = src_word if source_language == 'grc' else tgt_word
                    mw_entry['latin_word'] = tgt_word if source_language == 'grc' else src_word
                    mw_entry['greek_lemma'] = wm.get('greek_lemma', src_lemma if source_language == 'grc' else tgt_lemma)
                    mw_entry['latin_lemma'] = wm.get('latin_lemma', tgt_lemma if source_language == 'grc' else src_lemma)
                matched_words.append(mw_entry)
                source_highlights.extend(s_indices)
                target_highlights.extend(t_indices)
        elif has_semantic:
            # Semantic-only: try dictionary lookup for highlights
            src_lemmas = src_unit.get('lemmas', [])
            tgt_lemmas = tgt_unit.get('lemmas', [])
            try:
                highlight_matches = _get_semantic_highlight_matches(
                    src_lemmas, tgt_lemmas, source_language, target_language)
                for g in highlight_matches:
                    s_idx_list = g.get('source_indices', [])
                    t_idx_list = g.get('target_indices', [])
                    source_highlights.extend(s_idx_list)
                    target_highlights.extend(t_idx_list)
                    src_w = src_tokens[s_idx_list[0]] if s_idx_list and s_idx_list[0] < len(src_tokens) else g.get('source_lemma', '')
                    tgt_w = tgt_tokens[t_idx_list[0]] if t_idx_list and t_idx_list[0] < len(tgt_tokens) else g.get('target_lemma', '')
                    mw_entry = {
                        'source_word': src_w, 'target_word': tgt_w,
                        'source_lemma': g.get('source_lemma', ''),
                        'target_lemma': g.get('target_lemma', ''),
                        'display': f"{src_w}\u2192{tgt_w}",
                        'type': 'cross_lingual'
                    }
                    if is_greek_latin:
                        mw_entry['greek_word'] = src_w if source_language == 'grc' else tgt_w
                        mw_entry['latin_word'] = tgt_w if source_language == 'grc' else src_w
                        mw_entry['greek_lemma'] = g.get('source_lemma', '') if source_language == 'grc' else g.get('target_lemma', '')
                        mw_entry['latin_lemma'] = g.get('target_lemma', '') if source_language == 'grc' else g.get('source_lemma', '')
                    matched_words.append(mw_entry)
            except Exception as e:
                logger.warning(f"Failed to process cross-lingual match entry: {e}")

        # Add phonetic match highlighting
        if has_phonetic:
            for pm in phonetic_matches:
                src_orig = pm['source_original']
                tgt_orig = pm['target_original']
                sim_pct = int(pm['similarity'] * 100)
                # Find token indices for highlighting
                src_idx_h = next((i for i, t in enumerate(src_tokens)
                                  if t.lower() == src_orig.lower() or t == src_orig), None)
                tgt_idx_h = next((i for i, t in enumerate(tgt_tokens)
                                  if t.lower() == tgt_orig.lower() or t == tgt_orig), None)
                if src_idx_h is not None:
                    source_highlights.append(src_idx_h)
                if tgt_idx_h is not None:
                    target_highlights.append(tgt_idx_h)
                mw_entry = {
                    'source_word': src_orig,
                    'target_word': tgt_orig,
                    'display': f"{src_orig}\u2248{tgt_orig} ({sim_pct}%)",
                    'type': 'phonetic',
                }
                if is_greek_latin:
                    if source_language == 'grc':
                        mw_entry['greek_word'] = src_orig
                        mw_entry['latin_word'] = tgt_orig
                    else:
                        mw_entry['greek_word'] = tgt_orig
                        mw_entry['latin_word'] = src_orig
                matched_words.append(mw_entry)

        if not matched_words:
            matched_words = [{
                'type': 'semantic_cross',
                'similarity': cosine,
                'display': f'Semantic similarity ({int(cosine*100)}%)',
                'lemma': 'semantic_cross'
            }]

        channels = []
        if has_semantic:
            channels.append(f'semantic ({int(cosine*100)}%)')
        if has_dict:
            channels.append(f'dictionary ({dict_word_count} words)')
        if has_syntax:
            channels.append(f'syntax ({syntax_score:.2f})')
        if has_phonetic:
            channels.append(f'phonetic ({len(phonetic_matches)} tokens)')

        fused.append({
            'source': {
                'ref': format_short_locus(src_unit.get('ref', '')),
                'text': src_unit.get('text', ''),
                'tokens': src_original,
                'highlight_indices': sorted(set(source_highlights))
            },
            'target': {
                'ref': format_short_locus(tgt_unit.get('ref', '')),
                'text': tgt_unit.get('text', ''),
                'tokens': tgt_original,
                'highlight_indices': sorted(set(target_highlights))
            },
            'matched_words': matched_words,
            'match_count': dict_word_count,
            'overall_score': score,
            'features': {
                'semantic_score': cosine,
                'dict_score': dict_score,
                'syntax_score': syntax_score,
                'phonetic_score': phonetic_score,
                'n_channels': n_channels,
                'lemma_gate_triggered': lemma_gate_triggered,
                'lemma_match_count': gate_lemma_count,
            },
            'channels': ', '.join(channels),
            'match_basis': 'crosslingual_fusion'
        })

    fused.sort(key=lambda x: x['overall_score'], reverse=True)

    max_results = settings.get('max_results', 500)
    if max_results > 0:
        fused = fused[:max_results]

    logger.info(f"Cross-lingual fusion: {len(fused)} results "
          f"({len(sem_by_pair)} semantic, {len(dict_by_pair)} dictionary, "
          f"{len(syntax_by_pair)} syntax, {len(phonetic_by_pair)} phonetic, "
          f"{len(set(sem_by_pair) & set(dict_by_pair))} sem+dict overlap)")

    req_user_id, req_city, req_country, req_ip = req_meta or (None, None, None, None)

    return _finalize_results(fused, source_units, target_units,
                             0, settings, source_id, target_id, language,
                             req_user_id, req_city, req_country, req_ip)


def _get_semantic_highlight_matches(src_lemmas, tgt_lemmas, source_language, target_language):
    """Get dictionary word matches for semantic-only pair highlighting.

    Dispatches to the correct dictionary function based on language pair.
    Returns a list of dicts with unified keys: source_lemma, target_lemma,
    source_indices, target_indices.
    """
    lang_pair = frozenset((source_language, target_language))

    if lang_pair == frozenset(('grc', 'la')):
        from backend.synonym_dict import find_greek_latin_matches
        if source_language == 'grc':
            gl = find_greek_latin_matches(src_lemmas, tgt_lemmas)
        else:
            gl = find_greek_latin_matches(tgt_lemmas, src_lemmas)
            for g in gl:
                g['greek_indices'], g['latin_indices'] = g['latin_indices'], g['greek_indices']
        # Normalize to unified keys
        result = []
        for g in gl:
            if source_language == 'grc':
                result.append({
                    'source_lemma': g['greek_lemma'],
                    'target_lemma': g['latin_lemma'],
                    'source_indices': g.get('greek_indices', []),
                    'target_indices': g.get('latin_indices', []),
                })
            else:
                result.append({
                    'source_lemma': g['latin_lemma'],
                    'target_lemma': g['greek_lemma'],
                    'source_indices': g.get('latin_indices', []),
                    'target_indices': g.get('greek_indices', []),
                })
        return result

    elif lang_pair == frozenset(('la', 'en')):
        from backend.synonym_dict import find_latin_english_matches
        if source_language == 'la':
            matches = find_latin_english_matches(src_lemmas, tgt_lemmas)
        else:
            matches = find_latin_english_matches(tgt_lemmas, src_lemmas)
            for m in matches:
                m['source_indices'], m['target_indices'] = m['target_indices'], m['source_indices']
                m['source_lemma'], m['target_lemma'] = m['target_lemma'], m['source_lemma']
        return matches

    elif lang_pair == frozenset(('grc', 'en')):
        from backend.synonym_dict import find_greek_english_matches
        if source_language == 'grc':
            matches = find_greek_english_matches(src_lemmas, tgt_lemmas)
        else:
            matches = find_greek_english_matches(tgt_lemmas, src_lemmas)
            for m in matches:
                m['source_indices'], m['target_indices'] = m['target_indices'], m['source_indices']
                m['source_lemma'], m['target_lemma'] = m['target_lemma'], m['source_lemma']
        return matches

    return []


# =============================================================================
# STREAMING SEARCH ENDPOINT
# =============================================================================

@search_bp.route('/search-stream', methods=['POST'])
def search_stream():
    """Main text comparison search with SSE progress streaming."""
    data = request.get_json()
    
    # Capture request context variables before entering the generator
    req_user_id = current_user.id if current_user and current_user.is_authenticated else None
    req_city, req_country, req_ip = get_user_location()

    def generate():
        slot = None
        cancellation = None
        try:
            cancellation = SearchCancellation(data.get('search_id'))
            start_time = time.time()

            def send_progress(step, detail=""):
                elapsed = round(time.time() - start_time, 1)
                msg = {"type": "progress", "step": step, "detail": detail, "elapsed": elapsed}
                return f"data: {json.dumps(msg)}\n\n"

            yield send_progress("Initializing search")

            try:
                params = _parse_search_request(data)
            except (ValueError, FileNotFoundError) as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                return

            settings = params['settings']
            source_id = params['source_id']
            target_id = params['target_id']
            language = params['language']
            match_type = settings.get('match_type', 'lemma')

            # Check cache (skip if user requested a fresh search)
            skip_cache = data.get('skip_cache', False)
            cached_results, cached_meta = (None, None) if skip_cache else \
                get_cached_results(source_id, target_id, language, settings)
            if cached_results is not None:
                yield send_progress("Loading cached results")
                max_results = settings.get('max_results', 0)
                display_results = cached_results[:max_results] if max_results > 0 else cached_results
                meta = cached_meta or {}
                
                # Log the cached search
                match_type_raw = settings.get('match_type', 'lemma')
                match_labels = {
                    'lemma': 'Dictionary Form (Lemma)', 'exact': 'Exact Match',
                    'semantic': 'AI Semantic', 'v3_synonyms': 'Dictionary (V3 Synonyms)',
                    'synonyms': 'Dictionary (V3 Synonyms)', 'sound': 'Sound Matching',
                    'edit_distance': 'Edit Distance'
                }
                log_search(match_labels.get(match_type_raw, 'Dictionary Form (Lemma)'), language, source_id, target_id, None,
                          match_type_raw, len(cached_results), True, req_user_id, req_city, req_country, req_ip)
                
                result = {
                    "type": "complete",
                    "results": display_results,
                    "total_matches": len(cached_results),
                    "source_lines": meta.get('source_lines', 0),
                    "target_lines": meta.get('target_lines', 0),
                    "stoplist_size": meta.get('stoplist_size', 0),
                    "elapsed_time": round(time.time() - start_time, 2),
                    "cached": True
                }
                yield f"data: {json.dumps(result)}\n\n"
                return

            # Concurrency gate: wait for a slot before starting heavy work
            slot = SearchSlot(cancellation=cancellation)
            try:
                for queued_event in slot.acquire():
                    cancellation.check()
                    yield f"data: {json.dumps({'type': 'queued', 'step': 'Search queued — server is busy', 'detail': queued_event.get('reason', ''), 'wait_time': queued_event.get('wait_time', 0), 'elapsed': round(time.time() - start_time, 1)})}\n\n"
            except TimeoutError as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
                return
            cancellation.check()

            # Write metadata for active search inspector
            slot.set_metadata({
                'source_id': source_id,
                'target_id': target_id,
                'language': language,
                'match_type': match_type,
            })

            # Load text units (with per-text progress messages)
            source_unit_type = settings.get('source_unit_type', 'line')
            target_unit_type = settings.get('target_unit_type', 'line')

            yield send_progress("Loading source text", source_id.replace('.tess', ''))
            cancellation.check()
            if params['is_crosslingual']:
                source_units = _get_processed_units(source_id, params['source_language'], source_unit_type, _text_processor)
            else:
                source_units = _get_processed_units(source_id, language, source_unit_type, _text_processor)

            yield send_progress("Loading target text", target_id.replace('.tess', ''))
            cancellation.check()
            if params['is_crosslingual']:
                target_units = _get_processed_units(target_id, params['target_language'], target_unit_type, _text_processor)
            else:
                target_units = _get_processed_units(target_id, language, target_unit_type, _text_processor)

            # Load corpus frequencies if needed
            if settings.get('stoplist_basis', 'source_target') == 'corpus':
                yield send_progress("Loading corpus frequencies")
            corpus_frequencies = _load_corpus_frequencies(language, settings)
            cancellation.check()

            # Find matches
            yield send_progress("Finding matches", f"{len(source_units)} \u00d7 {len(target_units)} units")
            try:
                for event_type, event_data in _run_matcher_with_heartbeats(
                        match_type, source_units, target_units, settings,
                        corpus_frequencies, cancellation):
                    if slot.is_cancelled():
                        cancellation.cancel()
                        yield f"data: {json.dumps({'type': 'cancelled', 'message': get_cancellation_message(slot)})}\n\n"
                        return
                    if event_type == 'heartbeat':
                        yield ": keep-alive\n\n"
                    else:
                        matches, stoplist_size = event_data
            except SearchCancelled:
                return
            except ValueError:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Use regular search endpoint for cross-lingual'})}\n\n"
                return

            if slot.is_cancelled():
                yield f"data: {json.dumps({'type': 'cancelled', 'message': get_cancellation_message(slot)})}\n\n"
                return


            if not matches:
                # Log the 0-match search before returning
                match_type_raw = settings.get('match_type', 'lemma')
                match_labels = {
                    'lemma': 'Dictionary Form (Lemma)', 'exact': 'Exact Match',
                    'semantic': 'AI Semantic', 'v3_synonyms': 'Dictionary (V3 Synonyms)',
                    'synonyms': 'Dictionary (V3 Synonyms)', 'sound': 'Sound Matching',
                    'edit_distance': 'Edit Distance'
                }
                log_search(match_labels.get(match_type_raw, 'Dictionary Form (Lemma)'), language, source_id, target_id, None,
                          match_type_raw, 0, False, req_user_id, req_city, req_country, req_ip)
                
                result = {
                    "type": "complete",
                    "results": [],
                    "total_matches": 0,
                    "source_lines": len(source_units),
                    "target_lines": len(target_units),
                    "stoplist_size": stoplist_size,
                    "elapsed_time": round(time.time() - start_time, 2)
                }
                yield f"data: {json.dumps(result)}\n\n"
                return

            # Score, cache, log, and return
            yield send_progress("Scoring matches", f"{len(matches)} candidates")
            cancellation.check()
            scored_results = _scorer.score_matches(matches, source_units, target_units, settings, source_id, target_id)
            cancellation.check()
            scored_results.sort(key=lambda x: x['overall_score'], reverse=True)

            yield send_progress("Saving to cache")
            response_data = _finalize_results(scored_results, source_units, target_units,
                                               stoplist_size, settings, source_id, target_id, language, req_user_id, req_city, req_country, req_ip)

            elapsed_time = round(time.time() - start_time, 2)
            result = {
                "type": "complete",
                "results": response_data["results"],
                "total_matches": response_data["total_matches"],
                "source_lines": response_data["source_lines"],
                "target_lines": response_data["target_lines"],
                "stoplist_size": response_data["stoplist_size"],
                "elapsed_time": elapsed_time
            }
            yield f"data: {json.dumps(result)}\n\n"

        except GeneratorExit:
            if cancellation is not None:
                cancellation.cancel()
            raise
        except SearchCancelled:
            return
        except Exception as e:
            logger.error(f"Search stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            if slot is not None:
                slot.release()
            if cancellation is not None:
                cancellation.close()

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    })


@search_bp.route('/search-cancel', methods=['POST'])
def cancel_search():
    """Record a cancellation request that can be observed by any web worker."""
    data = request.get_json(silent=True) or {}
    try:
        request_cancellation(data.get('search_id'))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        logger.error('Could not cancel search: %s', e)
        return jsonify({'error': str(e)}), 500
    return jsonify({'status': 'cancellation_requested'}), 202


@search_bp.route('/search', methods=['POST'])
def search():
    """Non-streaming text comparison search (POST /api/search).

    Matches source vs target text using the specified match_type (lemma, exact, sound,
    edit_distance, semantic, dictionary, or cross-lingual variants). Returns all results
    at once with matched_words, scores, and highlight indices.
    """
    cancellation = None
    try:
        data = request.get_json() or {}
        cancellation = SearchCancellation(data.get('search_id'))
        cancellation.check()
        params = _parse_search_request(data)
        settings = params['settings']
        source_id = params['source_id']
        target_id = params['target_id']
        language = params['language']
        match_type = settings.get('match_type', 'lemma')

        # Check cache (skip if user requested a fresh search)
        skip_cache = data.get('skip_cache', False)
        cached_results, cached_meta = (None, None) if skip_cache else \
            get_cached_results(source_id, target_id, language, settings)
        if cached_results is not None:
            max_results = settings.get('max_results', 0)
            display_results = cached_results[:max_results] if max_results > 0 else cached_results
            user_id = current_user.id if current_user and current_user.is_authenticated else None
            city, country, ip = get_user_location()
            match_type_raw = settings.get('match_type', 'lemma')
            match_labels = {
                'lemma': 'Dictionary Form (Lemma)', 'exact': 'Exact Match',
                'semantic': 'AI Semantic', 'v3_synonyms': 'Dictionary (V3 Synonyms)',
                'synonyms': 'Dictionary (V3 Synonyms)', 'sound': 'Sound Matching',
                'edit_distance': 'Edit Distance'
            }
            log_search(match_labels.get(match_type_raw, 'Dictionary Form (Lemma)'), language, source_id, target_id, None,
                      match_type_raw, len(cached_results), True, user_id, city, country, ip)
            meta = cached_meta or {}
            return jsonify({
                "results": display_results,
                "total_matches": len(cached_results),
                "source_lines": meta.get('source_lines', 0),
                "target_lines": meta.get('target_lines', 0),
                "stoplist_size": meta.get('stoplist_size', 0),
                "cached": True
            })

        # Concurrency gate: blocks until a slot is available
        with SearchSlot(cancellation=cancellation) as slot:
            cancellation.check()
            slot.set_metadata({
                'source_id': source_id,
                'target_id': target_id,
                'language': language,
                'match_type': match_type,
            })
            # Load text units and corpus frequencies
            source_units, target_units = _load_units(params)
            corpus_frequencies = _load_corpus_frequencies(language, settings)

            if slot.is_cancelled():
                return jsonify({'error': get_cancellation_message(slot)}), 410

            # Cross-lingual fusion (default for cross-lingual searches)
            if match_type == 'crosslingual_fusion':
                return _handle_crosslingual_fusion(
                    params, source_units, target_units, settings, cancellation)

            # Legacy single-channel cross-lingual paths
            if match_type == 'dictionary_cross':
                return _handle_dictionary_cross(
                    params, source_units, target_units, settings, cancellation)
            if match_type == 'semantic_cross':
                from backend.semantic_similarity import find_crosslingual_matches
                matches, stoplist_size = find_crosslingual_matches(
                    source_units, target_units, params['source_language'],
                    params['target_language'], settings, cancellation)
            else:
                matches, stoplist_size = _run_matcher(match_type, source_units, target_units,
                                                       settings, corpus_frequencies, cancellation)

            if slot.is_cancelled():
                return jsonify({'error': get_cancellation_message(slot)}), 410


            # Score, cache, log, and return
            cancellation.check()
            scored_results = _scorer.score_matches(matches, source_units, target_units, settings, source_id, target_id)
            scored_results.sort(key=lambda x: x['overall_score'], reverse=True)
            req_user_id = current_user.id if current_user and current_user.is_authenticated else None
            req_city, req_country, req_ip = get_user_location()
            return jsonify(_finalize_results(scored_results, source_units, target_units,
                                              stoplist_size, settings, source_id, target_id, language, req_user_id, req_city, req_country, req_ip))

    except SearchCancelled:
        return jsonify({'error': 'Search cancelled'}), 499
    except TimeoutError as e:
        return jsonify({"error": f"Server busy: {e}"}), 503
    except Exception as e:
        logger.exception(f"Search failed: {e}")
        return jsonify({"error": str(e)})
    finally:
        if cancellation is not None:
            cancellation.close()


@search_bp.route('/stoplists', methods=['GET'])
def get_curated_stoplists_endpoint():
    """Return the primary matcher stoplists used by the Help page.

    This intentionally differs from POST /stoplist, which computes a
    text-specific list using selected source and target texts.
    """
    response = jsonify({'stoplists': get_curated_stoplists()})
    response.headers['Cache-Control'] = 'no-store'
    return response


@search_bp.route('/stoplist', methods=['POST'])
def get_stoplist():
    """Get the computed stoplist for given texts and settings"""
    data = request.get_json() or {}
    source_id = data.get('source', '')
    target_id = data.get('target', '')
    language = data.get('language', 'la')
    stoplist_basis = data.get('stoplist_basis', 'source_target')
    stoplist_size = data.get('stoplist_size', 0)
    
    if stoplist_size == -1:
        return jsonify({'stopwords': [], 'count': 0})
    
    try:
        source_units = _get_processed_units(source_id, language, 'line', _text_processor)
        target_units = _get_processed_units(target_id, language, 'line', _text_processor)
        
        corpus_frequencies = None
        if stoplist_basis == 'corpus':
            freq_data = _get_corpus_frequencies(language, _text_processor)
            if freq_data:
                corpus_frequencies = freq_data.get('frequencies', {})
        
        if stoplist_size > 0:
            stopwords = _matcher.build_stoplist_manual(source_units + target_units, stoplist_size, language)
        else:
            stopwords = _matcher.build_stoplist(source_units, target_units, stoplist_basis, language, corpus_frequencies)
        
        return jsonify({
            'stopwords': sorted(list(stopwords)),
            'count': len(stopwords)
        })
    except Exception as e:
        return jsonify({'error': str(e), 'stopwords': []})


@search_bp.route('/cache/clear', methods=['POST'])
def clear_search_cache():
    """Clear all cached search results - available to all users"""
    try:
        count = clear_cache()
        logger.info(f"Search cache cleared: {count} cached searches removed")
        return jsonify({
            'success': True,
            'message': f'Cleared {count} cached searches',
            'count': count
        })
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@search_bp.route('/wildcard-search', methods=['GET', 'POST'])
def wildcard_search_endpoint():
    """
    PHI-style wildcard/boolean search.
    
    Supports:
    - Wildcards: am* (starts with), *or (ends with), ?or (single char)
    - Boolean: amor AND dolor, virtus OR honos, amor NOT bellum
    - Phrases: "arma virumque"
    """
    try:
        from backend.wildcard_search import wildcard_search
        
        # Accept both POST JSON bodies and GET query-string params.
        data = request.get_json(silent=True) or request.args
        query = data.get('query', '').strip()
        language = data.get('language', 'la')
        target_text = data.get('target_text')
        case_sensitive = data.get('case_sensitive', False)
        # Coerce to int: GET query-string params arrive as strings.
        try:
            max_results = int(data.get('max_results', 500))
        except (TypeError, ValueError):
            max_results = 500
        if max_results <= 0:
            max_results = 500
        era_filter = data.get('era_filter')
        
        if not query:
            return jsonify({'error': 'Query is required', 'results': []})
        
        results = wildcard_search(
            language=language,
            query=query,
            target_text=target_text,
            case_sensitive=case_sensitive,
            max_results=max_results,
            era_filter=era_filter
        )
        
        user_id = current_user.id if current_user.is_authenticated else None
        city, country, ip = get_user_location()
        log_search('String Search', language, None, None, query,
                   'wildcard', len(results.get('results', [])), False, user_id, city, country, ip)
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Wildcard search error: {e}")
        return jsonify({'error': str(e), 'results': []}), 500


@search_bp.route('/wildcard-search-poll', methods=['GET'])
def wildcard_search_poll():
    """Poll-able GET wildcard/string search for URL-only assistants.

    GET /api/wildcard-search-poll?query=sonipes&language=la

    A rare-word string search can run tens of seconds — longer than many
    URL-fetch tools wait. This returns {status:"running"} on the first call and
    {status:"complete", results:[...]} once ready; poll the same URL every ~25s.
    Mirrors /api/fusion-search. Results are capped (max_results / limit, default
    200) to stay context-window friendly."""
    from backend.wildcard_search import wildcard_search
    from backend.blueprints.async_poll import poll, make_job_key
    data = request.args
    query = (data.get('query') or '').strip()
    language = data.get('language', 'la')
    if not query:
        return jsonify({'status': 'error', 'error': 'Query is required'}), 200
    try:
        max_results = int(data.get('max_results', data.get('limit', 200)))
    except (TypeError, ValueError):
        max_results = 200
    if max_results <= 0:
        max_results = 200
    key = make_job_key('wildcard', language, query, max_results)

    def compute():
        return wildcard_search(language=language, query=query, max_results=max_results)

    def transform(d):
        res = (d.get('results') or [])[:max_results]
        return {'query': d.get('query'), 'parsed_type': d.get('parsed_type'),
                'total_matches': d.get('total_matches'), 'truncated': d.get('truncated'),
                'showing': len(res), 'results': res}

    return poll('wildcard', key, compute, transform)


@search_bp.route('/crosslingual-search-poll', methods=['GET'])
def crosslingual_search_poll():
    """Poll-able GET cross-lingual fusion for URL-only assistants.

    GET /api/crosslingual-search-poll?source=<id>&target=<id>
        &source_language=grc&target_language=la[&min_matches=2&offset=0&limit=30]

    A cross-lingual fusion run (semantic + dictionary + syntax + phonetic
    channels over every source x target line pair) can take minutes on a large
    pair — longer than the ~60s a remote MCP client waits. This mirrors
    /api/fusion-search: the first GET starts the run in a background thread and
    returns {status:"running"}; poll the same URL every ~25s until
    {status:"complete", parallels:[...]}. The full ranked list is cached, so
    offset/limit page through it without recomputing (and a matching POST
    /api/search hits the same results cache instantly).
    """
    from backend.blueprints.async_poll import poll, make_job_key, SearchInputError
    data = request.args
    source = data.get('source')
    target = data.get('target')
    source_language = data.get('source_language', 'grc')
    target_language = data.get('target_language', 'la')
    if not source or not target:
        return jsonify({'status': 'error',
                        'error': 'Provide source and target text ids (see /api/texts).'}), 200
    try:
        min_matches = int(data.get('min_matches', 2))
    except (TypeError, ValueError):
        min_matches = 2

    # Full ranked list cached once per (pair, languages, min_matches); pagination
    # slices this cached list per request, so offset/limit are NOT part of the key.
    RANKED_CAP = 2000
    key = make_job_key('xlingual', source, target,
                       source_language, target_language, min_matches, RANKED_CAP)

    def compute():
        req = {'source': source, 'target': target,
               'source_language': source_language, 'target_language': target_language,
               'match_type': 'crosslingual_fusion', 'min_matches': min_matches,
               'max_results': RANKED_CAP}
        params = _parse_search_request(req)
        settings = params['settings']
        su, tu = _load_units(params)
        core = _crosslingual_fusion_core(params, su, tu, settings, None)
        if isinstance(core, dict) and core.get('error'):
            raise SearchInputError(core['error'])
        results = core.get('results', []) if isinstance(core, dict) else []
        return {
            'source': source, 'target': target,
            'source_language': source_language, 'target_language': target_language,
            'total': len(results),
            # The ranked list is capped at RANKED_CAP, so a total equal to the cap
            # is a floor, not the true count. Flag it so it is not read as exact.
            'capped': len(results) >= RANKED_CAP,
            'source_lines': core.get('source_lines', len(su)),
            'target_lines': core.get('target_lines', len(tu)),
            'results': results,
        }

    try:
        offset = max(0, int(data.get('offset', 0)))
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = int(data.get('limit', 30))
    except (TypeError, ValueError):
        limit = 30
    limit = max(1, min(limit, 200))

    def transform(d):
        allres = d.get('results', [])
        page = allres[offset:offset + limit]
        return {
            'source': d.get('source'), 'target': d.get('target'),
            'source_language': d.get('source_language'),
            'target_language': d.get('target_language'),
            'count': len(allres), 'total': d.get('total', len(allres)),
            # Derived at serve time so results cached before the flag existed
            # still report honestly: a full ranked list AT the cap is a floor.
            'capped': bool(d.get('capped', False)) or len(allres) >= RANKED_CAP,
            'source_lines': d.get('source_lines'), 'target_lines': d.get('target_lines'),
            'offset': offset, 'limit': limit, 'showing': len(page),
            'parallels': page,
        }

    return poll('xlingual', key, compute, transform)
