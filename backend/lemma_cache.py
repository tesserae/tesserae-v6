"""
Tesserae V6 - Lemma Cache
Pre-computes and caches lemmatized text units for faster searches
"""
import logging
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

def get_cache_path(text_id, language, cache_dir=None):
    """Get an ASCII-safe path to a cached lemma file.

    The cache filename must stay ASCII-only because some production WSGI
    environments expose an ASCII filesystem locale. Hashing the normalized
    text ID keeps filenames stable across NFC/NFD variants and avoids Unicode
    encode errors for Greek work IDs.

    `cache_dir` defaults to this module's own CACHE_DIR; backend/reuse_table.py
    passes its own (test-patchable) lemma cache directory so it can compute
    the SAME hashed filename production's own cache uses without adopting
    this module's CACHE_DIR (and, with it, get_cached_units's requirement
    that a live .tess file exist and hash-match -- reuse_table only wants a
    line's text, not a freshness guarantee, and the requirement would also
    defeat the fixture directories the reuse-route tests use).
    """
    cache_dir = cache_dir if cache_dir is not None else CACHE_DIR
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
    return os.path.join(cache_dir, language, filename)

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
    
    # Write beside the file and rename over it. Cache files are created by
    # whichever account first needed them (the web app at request time, or
    # the deploy account in a batch), so a later writer may not be allowed to
    # open the existing file; the directory allows a rename, and the swap is
    # atomic for a concurrent reader. A failure is logged, not swallowed: on
    # 2026-09-13 a batch rebuild reported eight caches built while two had
    # silently failed here, and stale rows reached the index.
    tmp_path = f'{cache_path}.{os.getpid()}.tmp'
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f)
        os.replace(tmp_path, cache_path)
        return True
    except OSError as e:
        logging.getLogger(__name__).warning('lemma cache not saved for %s: %s', text_id, e)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return False


def load_units_cached(filepath, language, text_processor, unit_type='line'):
    """Return processed units for a text, reusing the on-disk lemma cache when it
    is present and hash-valid; on a miss, compute with the text_processor and save
    both line and phrase units so subsequent calls hit the cache.

    This is the same disk-cache path the fusion loader uses. Callers that used to
    call text_processor.process_file directly (rare-word / rare-pair searches) can
    route through this to avoid re-lemmatizing on every request.
    """
    resolved_id = os.path.basename(filepath)
    cached = get_cached_units(resolved_id, language)
    if cached:
        key = 'units_phrase' if unit_type == 'phrase' else 'units_line'
        units = cached.get(key)
        if units is not None:
            return units
    units = text_processor.process_file(filepath, language, unit_type)
    try:
        file_hash = get_file_hash(filepath)
        line_units = units if unit_type == 'line' else text_processor.process_file(filepath, language, 'line')
        phrase_units = units if unit_type == 'phrase' else text_processor.process_file(filepath, language, 'phrase')
        save_cached_units(resolved_id, language, line_units, phrase_units, file_hash)
    except Exception:
        pass
    return units

def _ends_sentence_grc_fast(text):
    """Same check `TextProcessor._ends_sentence` uses for 'grc', without
    needing a TextProcessor instance (the fast path below never loads
    one)."""
    text = text.rstrip()
    return bool(text) and text[-1] in '.;·?!'


def _fast_greek_units(filepath, unit_type, lemma_table):
    """Line or phrase units for one Greek .tess file, lemmatized with the
    SAME table-only lookup `scripts/build_inverted_index.py`'s --fast mode
    uses for the index build (`tokenize_greek_fast` + `lemmatize_fast`): no
    CLTK, no POS tagging. Imported lazily so this function, and the import
    of `scripts.build_inverted_index` it needs, are only ever reached from
    `rebuild_lemma_cache`'s `fast_greek=True` path -- never for an
    existing, unmodified caller.

    Returns the same unit-dict shape `TextProcessor.process_file` returns
    (ref/text/tokens/original_tokens/lemmas/pos_tags/variant_lemmas/
    hemistich_breaks, plus line_refs for phrase units), with `pos_tags`,
    `variant_lemmas`, `hemistich_breaks` always empty (fast mode skips all
    three, matching the index build's own fast mode) and `original_tokens`
    set equal to `tokens` (the fast tokenizer does not keep a separate
    original-case form)."""
    from scripts.build_inverted_index import (  # local import: see docstring
        lemmatize_fast, parse_tess_file, tokenize_greek_fast)

    raw_lines = parse_tess_file(filepath)

    def _unit(ref, text, line_refs=None):
        tokens = tokenize_greek_fast(text)
        lemmas = lemmatize_fast(tokens, lemma_table, 'grc')
        unit = {
            'ref': ref, 'text': text, 'tokens': tokens,
            'original_tokens': tokens, 'lemmas': lemmas,
            'pos_tags': [], 'variant_lemmas': [], 'hemistich_breaks': [],
        }
        if line_refs is not None:
            unit['line_refs'] = line_refs
        return unit

    if unit_type == 'line':
        return [_unit(ref, text) for ref, text in raw_lines]

    units = []
    buf_refs, buf_texts = [], []
    for ref, text in raw_lines:
        buf_refs.append(ref)
        buf_texts.append(text)
        if _ends_sentence_grc_fast(text):
            combined_ref = buf_refs[0] if len(buf_refs) == 1 else f"{buf_refs[0]}-{buf_refs[-1]}"
            units.append(_unit(combined_ref, ' '.join(buf_texts), list(buf_refs)))
            buf_refs, buf_texts = [], []
    if buf_texts:
        combined_ref = buf_refs[0] if len(buf_refs) == 1 else f"{buf_refs[0]}-{buf_refs[-1]}"
        units.append(_unit(combined_ref, ' '.join(buf_texts), list(buf_refs)))
    return units


def rebuild_lemma_cache(language, text_processor, progress_callback=None,
                         file_filter=None, fast_greek=False,
                         build_phrase_units=True):
    """Rebuild lemma cache for all texts in a language.

    `build_phrase_units` (default True, unchanged behavior for every
    existing caller): when False, `units_phrase` is `[]` for every file
    and `text_processor.process_file(..., 'phrase')` is never called.
    Added for the documents build (stage 3b-1 follow-up), measured
    directly against the documentary corpus's own largest bucket file
    (`edr__roma__1_ad.tess`, 38,742 lines): that one file alone has a
    706-LINE run with no sentence-ending punctuation at all (common in
    epigraphic text, rare in literary text), so `process_file`'s phrase
    mode accumulates a single ~700-line "sentence" before it ever
    flushes, measured at 5.24 GB peak RSS for that one file alone (line
    mode alone on the same file: 1.45 GB). Nothing in this stage reads
    documents' phrase-mode cache entries (the index and
    `query_documents_index.py` both work off line-level postings), so
    skipping it here removes a measured, order-of-magnitude memory risk
    for zero loss of anything currently used. Literary callers never
    pass this and keep building phrase units exactly as before.

    `file_filter` (default None, unchanged behavior): an optional
    iterable of filenames to restrict the rebuild to (everything else in
    `TEXTS_DIR/language` is left untouched). For sharding a large rebuild
    across parallel processes, each given a disjoint subset of filenames.

    `fast_greek` (default False, unchanged behavior for every existing
    caller): when True AND `language == 'grc'`, lemmatizes with
    `_fast_greek_units` (the index build's own table-only fast-mode
    lookup) instead of `text_processor.process_file`, for both line and
    phrase units, so a fast-mode-built documents index and its lemma
    cache agree on every lemma. Ignored for any language other than
    'grc'; the import it needs is local to `_fast_greek_units` and is
    never reached unless this is explicitly True, so a caller that never
    passes it is byte-for-byte on the same code path as before."""
    lang_dir = os.path.join(TEXTS_DIR, language)
    if not os.path.exists(lang_dir):
        return {'error': f'Language directory not found: {language}'}

    text_files = [f for f in os.listdir(lang_dir) if f.endswith('.tess')]
    if file_filter is not None:
        allowed = set(file_filter)
        text_files = [f for f in text_files if f in allowed]
    total = len(text_files)
    processed = 0
    errors = []

    lemma_table = None
    if fast_greek and language == 'grc':
        from scripts.build_inverted_index import load_lemma_table
        lemma_table = load_lemma_table('grc')

    for text_file in text_files:
        try:
            filepath = os.path.join(lang_dir, text_file)
            file_hash = get_file_hash(filepath)

            if lemma_table is not None:
                units_line = _fast_greek_units(filepath, 'line', lemma_table)
                units_phrase = (_fast_greek_units(filepath, 'phrase', lemma_table)
                                if build_phrase_units else [])
            else:
                units_line = text_processor.process_file(filepath, language, 'line')
                units_phrase = (text_processor.process_file(filepath, language, 'phrase')
                                if build_phrase_units else [])

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
