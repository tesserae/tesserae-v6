"""
Tesserae V6 - Search Blueprint

This module handles the core intertextual search functionality, finding parallel
passages between a source text and a target text using various matching algorithms.

Key Features:
    - Streaming search with real-time progress updates (SSE)
    - Multiple match types: lemma, exact, sound, edit distance, semantic
    - Cross-lingual matching (Latin-Greek)
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

from backend.logging_config import get_logger
from backend.services import get_user_location, log_search
from backend.cache import get_cached_results, save_cached_results, clear_cache

logger = get_logger('search')


# =============================================================================
# BLUEPRINT SETUP
# =============================================================================
search_bp = Blueprint('search', __name__, url_prefix='/api')

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
# STREAMING SEARCH ENDPOINT
# =============================================================================

@search_bp.route('/search-stream', methods=['POST'])
def search_stream():
    """Main text comparison search with SSE progress streaming"""
    data = request.get_json()
    
    def generate():
        try:
            start_time = time.time()
            
            def send_progress(step, detail=""):
                elapsed = round(time.time() - start_time, 1)
                msg = {"type": "progress", "step": step, "detail": detail, "elapsed": elapsed}
                return f"data: {json.dumps(msg)}\n\n"
            
            yield send_progress("Initializing search")
            
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
                yield f"data: {json.dumps({'type': 'error', 'message': 'Please select both source and target texts'})}\n\n"
                return
            
            match_type = settings.get('match_type', 'lemma')
            is_crosslingual = match_type in ('semantic_cross', 'dictionary_cross')
            
            if is_crosslingual:
                source_lang_dir = os.path.join(_texts_dir, source_language)
                target_lang_dir = os.path.join(_texts_dir, target_language)
                source_path = os.path.join(source_lang_dir, source_id)
                target_path = os.path.join(target_lang_dir, target_id)
            else:
                lang_dir = os.path.join(_texts_dir, language)
                source_path = os.path.join(lang_dir, source_id)
                target_path = os.path.join(lang_dir, target_id)
            
            if not os.path.exists(source_path) or not os.path.exists(target_path):
                yield f"data: {json.dumps({'type': 'error', 'message': 'Text files not found'})}\n\n"
                return
            
            settings['language'] = language
            settings['source_language'] = source_language
            settings['target_language'] = target_language
            settings['source_text_path'] = source_path
            settings['target_text_path'] = target_path
            
            cached_results, cached_meta = get_cached_results(source_id, target_id, language, settings)
            
            if cached_results is not None:
                yield send_progress("Loading cached results")
                max_results = settings.get('max_results', 0)
                display_results = cached_results[:max_results] if max_results > 0 else cached_results
                meta = cached_meta or {}
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
            
            source_unit_type = settings.get('source_unit_type', 'line')
            target_unit_type = settings.get('target_unit_type', 'line')
            
            yield send_progress("Loading source text", source_id.replace('.tess', ''))
            if is_crosslingual:
                source_units = _get_processed_units(source_id, source_language, source_unit_type, _text_processor)
            else:
                source_units = _get_processed_units(source_id, language, source_unit_type, _text_processor)
            
            yield send_progress("Loading target text", target_id.replace('.tess', ''))
            if is_crosslingual:
                target_units = _get_processed_units(target_id, target_language, target_unit_type, _text_processor)
            else:
                target_units = _get_processed_units(target_id, language, target_unit_type, _text_processor)
            
            corpus_frequencies = None
            stoplist_basis = settings.get('stoplist_basis', 'source_target')
            if stoplist_basis == 'corpus':
                yield send_progress("Loading corpus frequencies")
                freq_data = _get_corpus_frequencies(language, _text_processor)
                if freq_data:
                    corpus_frequencies = freq_data.get('frequencies', {})
            
            yield send_progress("Finding matches", f"{len(source_units)} × {len(target_units)} units")
            
            if match_type == 'sound':
                matches, stoplist_size = _matcher.find_sound_matches(source_units, target_units, settings)
            elif match_type == 'edit_distance':
                matches, stoplist_size = _matcher.find_edit_distance_matches(source_units, target_units, settings)
            elif match_type == 'semantic':
                from backend.semantic_similarity import find_semantic_matches
                matches, stoplist_size = find_semantic_matches(source_units, target_units, settings)
            elif match_type in ('semantic_cross', 'dictionary_cross'):
                yield f"data: {json.dumps({'type': 'error', 'message': 'Use regular search endpoint for cross-lingual'})}\n\n"
                return
            else:
                matches, stoplist_size = _matcher.find_matches(source_units, target_units, settings, corpus_frequencies)
            
            if not matches:
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
            
            yield send_progress("Scoring matches", f"{len(matches)} candidates")
            scored_results = _scorer.score_matches(matches, source_units, target_units, settings, source_id, target_id)
            scored_results.sort(key=lambda x: x['overall_score'], reverse=True)
            
            yield send_progress("Saving to cache")
            metadata = {
                'source_lines': len(source_units),
                'target_lines': len(target_units),
                'stoplist_size': stoplist_size
            }
            save_cached_results(source_id, target_id, language, settings, scored_results, metadata)
            
            max_results = settings.get('max_results', 0)
            display_results = scored_results[:max_results] if max_results > 0 else scored_results
            
            user_id = current_user.id if current_user and current_user.is_authenticated else None
            city, country = get_user_location()
            log_search('text_comparison', language, source_id, target_id, None,
                      settings.get('match_type', 'lemma'), len(scored_results), False, user_id,
                      city, country)
            
            elapsed_time = round(time.time() - start_time, 2)
            result = {
                "type": "complete",
                "results": display_results,
                "total_matches": len(scored_results),
                "source_lines": len(source_units),
                "target_lines": len(target_units),
                "stoplist_size": stoplist_size,
                "elapsed_time": elapsed_time
            }
            yield f"data: {json.dumps(result)}\n\n"
            
        except Exception as e:
            logger.error(f"Search stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'
    })


@search_bp.route('/search', methods=['POST'])
def search():
    """Main text comparison search"""
    try:
        data = request.get_json()
        source_id = data.get('source')
        target_id = data.get('target')
        language = data.get('language', 'la')
        source_language = data.get('source_language', language)
        target_language = data.get('target_language', language)
        
        # Build settings from nested 'settings' object OR top-level properties
        settings = data.get('settings', {})
        # Also check for settings spread at top level (frontend sends them this way)
        for key in ['match_type', 'min_matches', 'max_results', 'max_distance', 
                    'stoplist_basis', 'stoplist_size', 'source_unit_type', 'target_unit_type',
                    'use_meter', 'use_pos', 'use_syntax', 'use_sound', 'use_edit_distance',
                    'bigram_boost', 'custom_stopwords']:
            if key in data and key not in settings:
                settings[key] = data[key]
        
        if not source_id or not target_id:
            return jsonify({"error": "Please select both source and target texts"})
        
        match_type = settings.get('match_type', 'lemma')
        is_crosslingual = match_type in ('semantic_cross', 'dictionary_cross')
        
        if is_crosslingual:
            source_lang_dir = os.path.join(_texts_dir, source_language)
            target_lang_dir = os.path.join(_texts_dir, target_language)
            source_path = os.path.join(source_lang_dir, source_id)
            target_path = os.path.join(target_lang_dir, target_id)
        else:
            lang_dir = os.path.join(_texts_dir, language)
            source_path = os.path.join(lang_dir, source_id)
            target_path = os.path.join(lang_dir, target_id)
        
        if not os.path.exists(source_path) or not os.path.exists(target_path):
            return jsonify({"error": "Text files not found"})
        
        settings['language'] = language
        settings['source_language'] = source_language
        settings['target_language'] = target_language
        settings['source_text_path'] = source_path
        settings['target_text_path'] = target_path
        
        cached_results, cached_meta = get_cached_results(
            source_id, target_id, language, settings
        )
        
        if cached_results is not None:
            max_results = settings.get('max_results', 0)
            display_results = cached_results[:max_results] if max_results > 0 else cached_results
            user_id = current_user.id if current_user and current_user.is_authenticated else None
            city, country = get_user_location()
            log_search('text_comparison', language, source_id, target_id, None, 
                      settings.get('match_type', 'lemma'), len(cached_results), True, user_id,
                      city, country)
            meta = cached_meta or {}
            return jsonify({
                "results": display_results,
                "total_matches": len(cached_results),
                "source_lines": meta.get('source_lines', 0),
                "target_lines": meta.get('target_lines', 0),
                "stoplist_size": meta.get('stoplist_size', 0),
                "cached": True
            })
        
        source_unit_type = settings.get('source_unit_type', 'line')
        target_unit_type = settings.get('target_unit_type', 'line')
        
        if is_crosslingual:
            source_units = _get_processed_units(source_id, source_language, source_unit_type, _text_processor)
            target_units = _get_processed_units(target_id, target_language, target_unit_type, _text_processor)
        else:
            source_units = _get_processed_units(source_id, language, source_unit_type, _text_processor)
            target_units = _get_processed_units(target_id, language, target_unit_type, _text_processor)
        
        corpus_frequencies = None
        stoplist_basis = settings.get('stoplist_basis', 'source_target')
        if stoplist_basis == 'corpus':
            freq_data = _get_corpus_frequencies(language, _text_processor)
            if freq_data:
                corpus_frequencies = freq_data.get('frequencies', {})
        
        match_type = settings.get('match_type', 'lemma')
        
        if match_type == 'sound':
            matches, stoplist_size = _matcher.find_sound_matches(
                source_units, target_units, settings
            )
        elif match_type == 'edit_distance':
            matches, stoplist_size = _matcher.find_edit_distance_matches(
                source_units, target_units, settings
            )
        elif match_type == 'semantic':
            from backend.semantic_similarity import find_semantic_matches
            matches, stoplist_size = find_semantic_matches(
                source_units, target_units, settings
            )
        elif match_type == 'semantic_cross':
            from backend.semantic_similarity import find_crosslingual_matches
            matches, stoplist_size = find_crosslingual_matches(
                source_units, target_units, source_language, target_language, settings
            )
        elif match_type == 'dictionary_cross':
            from backend.semantic_similarity import find_dictionary_crosslingual_matches
            # Load frequency data for IDF scoring (uses cached data from app init)
            greek_freq_data = _get_corpus_frequencies('grc', _text_processor)
            latin_freq_data = _get_corpus_frequencies('la', _text_processor)
            greek_frequencies = greek_freq_data.get('frequencies', {}) if greek_freq_data else {}
            latin_frequencies = latin_freq_data.get('frequencies', {}) if latin_freq_data else {}
            matches, stoplist_size = find_dictionary_crosslingual_matches(
                source_units, target_units, source_language, target_language, settings,
                greek_frequencies=greek_frequencies, latin_frequencies=latin_frequencies
            )
            # For dictionary matches, use IDF score directly instead of re-scoring
            # Build results directly from matches (already sorted by IDF)
            scored_results = []
            for m in matches:
                src_unit = source_units[m['source_idx']]
                tgt_unit = target_units[m['target_idx']]
                src_tokens = src_unit.get('tokens', [])
                tgt_tokens = tgt_unit.get('tokens', [])
                # Use original_tokens for display (preserves capitalization and diacritics)
                src_original = src_unit.get('original_tokens', src_tokens)
                tgt_original = tgt_unit.get('original_tokens', tgt_tokens)
                
                # Map matched lemmas back to original tokens (with diacritics and capitalization)
                # Use the first matched index to get the original token
                matched_words_with_original = []
                for wm in m.get('word_matches', []):
                    grc_indices = wm.get('greek_indices', [])
                    lat_indices = wm.get('latin_indices', [])
                    # Get original token with diacritics and capitalization
                    grc_original = src_original[grc_indices[0]] if grc_indices and grc_indices[0] < len(src_original) else wm['greek_lemma']
                    lat_original_word = tgt_original[lat_indices[0]] if lat_indices and lat_indices[0] < len(tgt_original) else wm['latin_lemma']
                    matched_words_with_original.append({
                        'greek_word': grc_original,
                        'latin_word': lat_original_word,
                        'greek_lemma': wm.get('greek_lemma', ''),
                        'latin_lemma': wm.get('latin_lemma', ''),
                        'display': f"{grc_original}→{lat_original_word}",
                        'type': 'cross_lingual',
                        'idf': wm.get('idf_score', 0)
                    })
                
                scored_results.append({
                    'source': {
                        'ref': src_unit.get('ref', ''),
                        'text': src_unit.get('text', ''),
                        'tokens': src_original,  # Use original tokens with capitalization/diacritics
                        'highlight_indices': [idx for wm in m.get('word_matches', []) for idx in wm.get('greek_indices', [])]
                    },
                    'target': {
                        'ref': tgt_unit.get('ref', ''),
                        'text': tgt_unit.get('text', ''),
                        'tokens': tgt_original,  # Use original tokens with capitalization
                        'highlight_indices': [idx for wm in m.get('word_matches', []) for idx in wm.get('latin_indices', [])]
                    },
                    'matched_words': matched_words_with_original,
                    'match_count': m.get('match_count', 0),
                    'distance': m.get('distance', 0),
                    'idf_score': m.get('idf_score', 0),
                    'overall_score': m.get('overall_score', 0),  # Combined IDF + distance score
                    'match_basis': 'dictionary_cross'
                })
            # Skip scorer and go directly to results
            metadata = {
                'source_lines': len(source_units),
                'target_lines': len(target_units),
                'stoplist_size': stoplist_size
            }
            save_cached_results(source_id, target_id, language, settings, 
                              scored_results, metadata)
            max_results = settings.get('max_results', 0)
            display_results = scored_results[:max_results] if max_results > 0 else scored_results
            user_id = current_user.id if current_user and current_user.is_authenticated else None
            city, country = get_user_location()
            log_search('text_comparison', language, source_id, target_id, None,
                      'dictionary_cross', len(scored_results), False, user_id, city, country)
            return jsonify({
                "results": display_results,
                "total_matches": len(scored_results),
                "source_lines": len(source_units),
                "target_lines": len(target_units),
                "stoplist_size": stoplist_size,
                "cached": False
            })
        else:
            matches, stoplist_size = _matcher.find_matches(
                source_units, target_units, settings, 
                corpus_frequencies=corpus_frequencies
            )
        
        scored_results = _scorer.score_matches(matches, source_units, target_units, settings, source_id, target_id)
        scored_results.sort(key=lambda x: x['overall_score'], reverse=True)
        
        metadata = {
            'source_lines': len(source_units),
            'target_lines': len(target_units),
            'stoplist_size': stoplist_size
        }
        
        save_cached_results(source_id, target_id, language, settings, 
                          scored_results, metadata)
        
        max_results = settings.get('max_results', 0)
        display_results = scored_results[:max_results] if max_results > 0 else scored_results
        
        user_id = current_user.id if current_user and current_user.is_authenticated else None
        city, country = get_user_location()
        log_search('text_comparison', language, source_id, target_id, None,
                  settings.get('match_type', 'lemma'), len(scored_results), False, user_id,
                  city, country)
        
        return jsonify({
            "results": display_results,
            "total_matches": len(scored_results),
            "source_lines": len(source_units),
            "target_lines": len(target_units),
            "stoplist_size": stoplist_size,
            "cached": False
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)})


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


@search_bp.route('/wildcard-search', methods=['POST'])
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
        
        data = request.get_json()
        query = data.get('query', '').strip()
        language = data.get('language', 'la')
        target_text = data.get('target_text')
        case_sensitive = data.get('case_sensitive', False)
        max_results = data.get('max_results', 500)
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
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Wildcard search error: {e}")
        return jsonify({'error': str(e), 'results': []}), 500
