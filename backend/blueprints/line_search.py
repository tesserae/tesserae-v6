"""Line Search routes: /line-search, /line-search-parallel, /corpus-search and their helpers.

Moved out of backend/app.py unchanged (application-factory job, 2026-10-12).
"""
import os
import re
import math
import unicodedata

from flask import Blueprint, jsonify, request
from flask_login import current_user

from backend.services import get_user_location, log_search
from backend import fspaths
from backend.utils import get_text_metadata, clean_cts_reference, resolve_text_path, exact_phrase_pattern, strip_hebrew_pointing, exact_search_text, format_short_locus
from backend.frequency_cache import get_corpus_frequencies
from backend.distance_filter import is_prose_text as is_prose_text_unified
from backend.distance_filter import get_max_distance as _get_max_distance
from backend.runtime import (
    TEXTS_DIR, AUTHOR_DATES,
    app_logger, text_processor, get_processed_units, api_route_for,
)
from flask import current_app as app
from backend.line_search_support import _normalize_lemma, _normalize_latin_lemma
from backend.blueprints.documents import (
    _DOCUMENT_SORT_MODES, _search_documents_collection, _line_search_documents_only,
)

line_search_bp = Blueprint('line_search', __name__)
api_route = api_route_for(line_search_bp)



# =============================================================================
# PROSE DETECTION HELPERS
# =============================================================================
# Prose detection delegated to unified detect_text_type() in utils.py via
# distance_filter.is_prose_text (imported as is_prose_text_unified at top).
# POETRY_MAX_DISTANCE / PROSE_MAX_DISTANCE kept here for app.py's own use.

POETRY_MAX_DISTANCE = 20
PROSE_MAX_DISTANCE = 4


def _hebrew_unpointed_fallbacks(query, query_lemmas, stopwords):
    """For a Hebrew query, the index fallback forms that let a word typed
    without vowel points match every homograph reading of its consonants.
    Returns (fallback_forms or None, query_lemmas), where a lemma the
    stoplist would drop is replaced by its first content reading so that a
    bare אל in a longer query still finds אל³ "God"."""
    from backend.hebrew.processor import homograph_readings, is_unpointed, lemmatize_hebrew
    fallbacks = {}
    lemmas = set(query_lemmas)
    for token in query.split():
        if not is_unpointed(token):
            continue
        for lemma in lemmatize_hebrew([token]):
            readings = [r for r in homograph_readings(lemma) if r not in stopwords] or [lemma]
            canonical = lemma if lemma in readings else readings[0]
            others = set(readings) - {canonical}
            if canonical != lemma and lemma in lemmas:
                lemmas.discard(lemma)
                lemmas.add(canonical)
            if others:
                fallbacks[canonical] = others
    return (fallbacks or None), lemmas


def _line_lemmas_matching_query(line_lemmas, query_lemmas, fallback_forms=None):
    """The lemmas of an indexed line that answer the query: the query lemmas
    themselves and their fallback readings. The index lookup counts a hit on
    מלך² as a hit on מלך, so a line must be judged the same way here; testing
    the line against the query lemmas alone dropped every line that held only
    another reading (bare מלך found "king" but never "he reigned"). The line's
    own readings are returned, so each result names the word it has."""
    accepted = set(query_lemmas)
    for lemma in query_lemmas:
        accepted.update((fallback_forms or {}).get(lemma, ()))
    return set(line_lemmas) & accepted


def _univerbation_lemmatize(word):
    """The folded Latin lemmas of a word, for backend.univerbation."""
    return {l for l in (_normalize_lemma(x, 'la') for x in text_processor.lemmatize_word(word, 'la')) if l}


def _score_v3_idf(shared_lemmas, corpus_frequencies, total_corpus_words,
                   distance, phrase_match_bonus=1.0):
    """V3-style scoring: sum(IDF) * distance_factor * phrase_bonus.

    Args:
        shared_lemmas: Set of shared lemma strings.
        corpus_frequencies: Dict mapping lemma → corpus frequency count.
        total_corpus_words: Total word count across corpus.
        distance: Span between first and last matched word positions.
        phrase_match_bonus: Multiplier for phrase matches (default 1.0).

    Returns:
        float score.
    """
    idf_sum = 0
    for lemma in shared_lemmas:
        freq = corpus_frequencies.get(lemma, 1)
        idf = math.log(total_corpus_words / (freq + 1)) + 1
        idf_sum += idf
    distance_factor = 1.0 / (1 + math.log(distance + 1))
    return idf_sum * distance_factor * phrase_match_bonus


def _deduplicate_and_normalize(results):
    """Deduplicate results by text content (keep highest score) and normalize scores to 0-10."""
    import re as _re
    seen_texts = {}
    deduplicated = []
    for r in results:
        text_key = _re.sub(r'[^\w\s]', '', r['text'].lower()).strip()
        if text_key not in seen_texts:
            seen_texts[text_key] = r
            deduplicated.append(r)

    if deduplicated:
        max_score = max(r['score'] for r in deduplicated) or 1
        for r in deduplicated:
            r['raw_score'] = r['score']
            r['score'] = round((r['score'] / max_score) * 10, 2)

    return deduplicated


def _resolve_line_text(source_text_id, line_ref, language):
    """Look up a line's text from its .tess file using the reference tag."""
    source_path = resolve_text_path(TEXTS_DIR, language, source_text_id)
    if source_path:
        with open(source_path, 'r', encoding='utf-8') as f:
            for file_line in f:
                file_line = file_line.strip()
                if file_line.startswith('<') and '>' in file_line:
                    end_tag = file_line.index('>')
                    ref = file_line[1:end_tag].strip()
                    if ref == line_ref:
                        return file_line[end_tag+1:].strip()
    return None


def _build_line_search_stopwords(language, corpus_frequencies):
    """Build stopwords set for line search: default language stops + Zipf elbow detection."""
    from backend.matcher import DEFAULT_LATIN_STOP_WORDS, DEFAULT_GREEK_STOP_WORDS, DEFAULT_ENGLISH_STOP_WORDS
    from backend.zipf import find_zipf_elbow
    from collections import Counter

    if language == 'la':
        stopwords = set(DEFAULT_LATIN_STOP_WORDS)
    elif language == 'grc':
        stopwords = set(DEFAULT_GREEK_STOP_WORDS)
    else:
        stopwords = set(DEFAULT_ENGLISH_STOP_WORDS)

    if corpus_frequencies:
        freq_counter = Counter(corpus_frequencies)
        zipf_stops = find_zipf_elbow(freq_counter, min_stopwords=10, max_stopwords=50)
        stopwords = stopwords.union(zipf_stops)

    return stopwords


def _evaluate_line_candidate(unit, ref, filename, filtered_source_lemmas, query_text_lower,
                              source_text_id, line_ref, key_phrases, corpus_frequencies,
                              total_corpus_words, lang_dates, seen_results, min_matches=2,
                              index_matching_lemmas=None):
    """Evaluate a single candidate line against the source line.

    Used by both the index fast path and the fallback scan path in line_search_parallel().
    Returns a result dict if the candidate passes all filters, or None.

    For the index path, pass index_matching_lemmas (the lemmas the index found).
    For the fallback path, leave it None to compute shared lemmas directly.
    """
    import re as _re

    if not unit:
        return None

    unit_ref = ref or unit.get('ref', '')
    result_key = (filename, unit_ref)
    if result_key in seen_results:
        return None
    seen_results.add(result_key)

    target_text = unit.get('text', '').lower().strip()

    # Exclude the exact source line and lines with identical text
    if filename == source_text_id and unit_ref == line_ref:
        return None
    if target_text == query_text_lower:
        return None

    # Compute shared lemmas (index path verifies against actual lemmas with normalization)
    target_lemmas_list = unit.get('lemmas', [])

    if index_matching_lemmas is not None:
        target_lemmas_normalized = {_normalize_latin_lemma(l) for l in target_lemmas_list}
        source_lemmas_normalized = {_normalize_latin_lemma(l) for l in filtered_source_lemmas}
        matching_normalized = {_normalize_latin_lemma(l) for l in index_matching_lemmas}
        shared = matching_normalized & target_lemmas_normalized & source_lemmas_normalized
    else:
        target_lemmas = set(target_lemmas_list)
        shared = filtered_source_lemmas & target_lemmas

    if len(shared) < min_matches:
        return None

    # Phrase matching — quotation detection
    target_normalized = _re.sub(r'[^\w\s]', '', target_text)
    phrase_match_bonus = 1.0
    for phrase in key_phrases:
        if phrase in target_normalized:
            phrase_match_bonus = 1000.0 + len(phrase) * 100
            break

    # Calculate match positions and distance
    if index_matching_lemmas is not None:
        match_positions = [i for i, lem in enumerate(target_lemmas_list)
                          if _normalize_latin_lemma(lem) in shared]
    else:
        match_positions = [i for i, lem in enumerate(target_lemmas_list) if lem in shared]

    if len(match_positions) >= 2:
        distance = match_positions[-1] - match_positions[0] + 1
    else:
        distance = 1

    max_dist = PROSE_MAX_DISTANCE if is_prose_text_unified(filename) else POETRY_MAX_DISTANCE
    if distance > max_dist:
        return None

    score = _score_v3_idf(shared, corpus_frequencies, total_corpus_words,
                           distance, phrase_match_bonus)

    # Build result
    parts = filename.replace('.tess', '').split('.')
    author_key = filename.split('.')[0].lower()
    author_info = lang_dates.get(author_key, {})

    return {
        'text_id': filename,
        'author': parts[0] if parts else '',
        'work': '.'.join(parts[1:]) if len(parts) > 1 else '',
        'ref': unit_ref,
        'text': unit.get('text', ''),
        'tokens': unit.get('tokens', []),
        'highlight_indices': match_positions,
        'matched_lemmas': list(shared),
        'match_count': len(shared),
        'score': round(score, 3),
        'year': author_info.get('year'),
        'era': author_info.get('era', 'Unknown')
    }


# =============================================================================
# LINE SEARCH (CORPUS-WIDE) API ROUTES
# =============================================================================
# These routes enable searching for words/phrases across the entire corpus
# using the pre-built inverted index for fast lookups.

def _dedup_same_passage(results):
    """Collapse the SAME passage duplicated across text_ids that vary only by
    author/work naming — e.g. cyprian.ad_demetrianum vs cyprian_saint.ad_demetrianum
    (both locus 23), or arnobius.adversus_nationes vs
    arnobius_of_sicca.adversus_nationes_libri_vii (both 2.59). The whole/part
    text_id dedup misses these because the ids differ.

    Key on (locus, normalized line text): two rows sharing BOTH the exact locus
    label and the exact line are the same passage under a variant spelling.
    Conservative by construction — a repeated refrain has one text but different
    loci (kept), and edition spelling variants differ in text (kept), so this only
    removes genuine duplicate-text inflation, never distinct loci. Rows with empty
    text are always kept (can't confirm they are duplicates). Order preserved.
    """
    seen = set()
    out = []
    for r in results:
        nt = ' '.join((r.get('text') or '').lower().split())
        key = (r.get('locus'), nt)
        if nt and key in seen:
            continue
        if nt:
            seen.add(key)
        out.append(r)
    return out


# A lemma this frequent (as a share of the table's most frequent lemma) is a
# commonplace: quis, ipse, uir and some three hundred friends. 0.45 keeps
# examen (151/767 in Latin) distinctive while catching uarius (481/767).
RARE_FOCUS_COMMON_RATIO = 0.45


def rare_focus_filter(results, language):
    """Drop lemma-search results whose shared words are ALL commonplaces.

    The Reader's Verbal Parallels tab asks this: a line's quid + uariis
    matching Catullus's quid + uarii is not an echo, it is Latin. A result
    survives when at least one shared lemma is distinctive (low document
    frequency), or when three or more distinct lemmas are shared, since the
    CO-OCCURRENCE of several common words is itself distinctive (arma +
    uir + cano). Returns (kept, hidden_count, common_lemmas_seen); on any
    failure (no doc-freq table for the language) returns results unfiltered.
    """
    try:
        import sqlite3 as _sq
        from backend.lexical_density import _index_path
        conn = _sq.connect(f'file:{_index_path(language)}?mode=ro', uri=True)
        max_df = conn.execute('SELECT MAX(df) FROM lemma_doc_freq').fetchone()[0]
        if not max_df:
            conn.close()
            return results, 0, []
        threshold = max_df * RARE_FOCUS_COMMON_RATIO
        df_cache = {}

        def df_of(lem):
            if lem not in df_cache:
                row = conn.execute(
                    'SELECT df FROM lemma_doc_freq WHERE lemma = ?',
                    (lem,)).fetchone()
                df_cache[lem] = row[0] if row else 0
            return df_cache[lem]

        kept, hidden, commons = [], 0, set()
        for r in results:
            distinct = set(r.get('matched_lemmas') or [])
            if not distinct:
                kept.append(r)
                continue
            if len(distinct) >= 3 or any(df_of(l) <= threshold for l in distinct):
                kept.append(r)
            else:
                hidden += 1
                commons.update(distinct)
        conn.close()
        return kept, hidden, sorted(commons)
    except Exception as e:
        # No doc-freq table for this language (or a broken one): filter
        # nothing, but say so — the silent form of this fallback is how the
        # missing Hebrew and Coptic tables went unnoticed last time.
        import logging
        logging.getLogger('tesserae').warning(
            '[RARE-FOCUS] filter unavailable for %s (%s); showing all matches',
            language, e)
        return results, 0, []


def _candidate_within_distance(filename, positions, language='la'):
    """The closeness rule line_search applies to each line through
    passes_distance_filter, decided here from the index's own per-lemma
    position lists so a candidate can be counted without loading its line:
    the smallest gap between an occurrence of one matched lemma and an
    occurrence of another must be within get_max_distance (4 tokens in prose,
    10 in verse). A candidate with positions for fewer than two lemmas (an
    older index, a one-word query) counts, as the filter passes such a line.

    Why this exists (2026-10-11): for the pair infero and latium the corpus
    chart counted one Tacitus line and the list under it showed none. The hit
    was Histories 3.55, a whole prose chapter in which the two words stand some
    forty words apart. The list dropped it under the closeness rule; the chart
    had counted it first. Counting after the same rule keeps the two in step.
    The filter groups by surface word where this groups by lemma, so two forms
    of one lemma standing together do not count as a close pair here."""
    lists = [lst for lst in (positions or {}).values() if lst]
    if len(lists) < 2:
        return True
    min_dist = min(abs(a - b)
                   for i in range(len(lists)) for j in range(i + 1, len(lists))
                   for a in lists[i] for b in lists[j])
    return min_dist == 0 or min_dist <= _get_max_distance(filename, language)


def _count_candidates_by_work(text_candidates, language, lang_dates):
    """[{work_id, author, work, year, era, count}] for every work holding a
    co-occurring line that also passes the closeness rule, newest-last by year
    (see line_search). A whole file wins over its book files; book files alone
    are summed. Each match is (ref, matching_lemmas, positions); a shorter
    tuple is counted without the distance check."""
    import re as _re_w
    groups = {}
    for filename, matches in text_candidates.items():
        kept = sum(1 for m in matches
                   if len(m) < 3 or _candidate_within_distance(filename, m[2], language))
        if not kept:
            continue
        base = _re_w.sub(r'\.part\.[^/]*$', '', filename[:-5] if filename.endswith('.tess') else filename)
        g = groups.setdefault(base, {'whole': None, 'parts': 0, 'file': filename})
        if '.part.' in filename:
            g['parts'] += kept
        else:
            g['whole'] = kept
            g['file'] = filename
    out = []
    for base, g in groups.items():
        count = g['whole'] if g['whole'] is not None else g['parts']
        filepath = resolve_text_path(TEXTS_DIR, language, g['file'])
        meta = get_text_metadata(filepath) if filepath else {}
        info = lang_dates.get(base.split('.')[0].lower(), {})
        out.append({'work_id': base, 'author': meta.get('author') or base.split('.')[0],
                    'work': meta.get('title') or base, 'year': info.get('year'),
                    'era': info.get('era', 'Unknown'), 'count': count})
    out.sort(key=lambda w: (w['year'] if w['year'] is not None else 9999, w['author'], w['work']))
    return out


_SURFACE_ENCLITICS = ('que', 'ue', 'ne')


def _surface_norm(token, language):
    """A token reduced for a surface comparison: lower case, no diacritics
    (Greek accents, Hebrew points), no punctuation, u for v and i for j in
    Latin and English."""
    t = unicodedata.normalize('NFD', str(token or '').lower())
    t = ''.join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r'[^\w]', '', t)
    if language in ('la', 'en'):
        t = t.replace('v', 'u').replace('j', 'i')
    return t


def _surface_hits(query, tokens, language, window=None):
    """How many distinct words of the query, common words included, the
    line carries in SURFACE form (an enclitic -que, -ue or -ne stripped from
    the line's word counts). With `window`, the most that fall inside any
    run of that many tokens, so a long prose sentence holding the words far
    apart does not pass as a quotation. The lemma search drops common words
    such as "sit" and "tibi", so this is the only place a quotation of "sit
    tibi terra levis" is told from a line that merely has terra and levis."""
    qwords = {_surface_norm(w, language) for w in str(query or '').split()}
    qwords.discard('')
    if not qwords:
        return 0
    forms = []  # per token, the set of query words it realises
    for tok in tokens or ():
        n = _surface_norm(tok, language)
        hit = set()
        if n:
            if n in qwords:
                hit.add(n)
            for enc in _SURFACE_ENCLITICS:
                if n.endswith(enc) and len(n) > len(enc) + 2 and n[:-len(enc)] in qwords:
                    hit.add(n[:-len(enc)])
        forms.append(hit)
    if language == 'la' and forms:
        # A joined word (quousque) realises the parts the query typed
        # (quo usque), and parts printed apart realise a joined query word.
        from backend.univerbation import surface_forms
        for hit, extra in zip(forms, surface_forms(
                [_surface_norm(t, language) for t in (tokens or ())], qwords,
                _univerbation_lemmatize)):
            hit.update(extra)
    if not window or window >= len(forms):
        return len(set().union(*forms)) if forms else 0
    best = 0
    for i in range(len(forms) - window + 1):
        best = max(best, len(set().union(*forms[i:i + window])))
    return best


def _is_near_quotation(matched_lemma_set, query_lemmas, positions, query, surface_hits=None):
    """True when a line quotes the phrase: it shares every content lemma of
    the query, the matched tokens sit within a window no longer than the
    query's own word count plus two, AND it carries the query's own words in
    surface form, common ones included, with at most one word inflected or
    missing. The last test was added after the first form marked 23 of 36
    hits for "sit tibi terra levis" as quotations (the common words sit and
    tibi had been dropped, so Caesar's "levibus cratibus terraque" passed).
    A one-word query is never a quotation in this sense: nothing to be near.
    `surface_hits` None skips the surface test (callers without tokens)."""
    if len(query_lemmas) < 2 or len(matched_lemma_set) < len(query_lemmas):
        return False
    if not positions:
        return False
    width = max(positions) - min(positions) + 1
    n_words = len(str(query or '').split())
    if width > n_words + 2:
        return False
    if surface_hits is None:
        return True
    return surface_hits >= n_words - 1


def _span(positions):
    """Width of the window holding the matched tokens, or None."""
    if not positions:
        return None
    return max(positions) - min(positions) + 1


@api_route('/line-search', methods=['GET', 'POST'])
def line_search():
    """
    Search for words/phrases across the corpus with optional filters.
    Uses inverted index for fast lookups when available.
    """
    try:
        from backend.inverted_index import is_index_available, find_co_occurring_lemmas, has_lines_data, get_lines_batch, get_corpus_version
        from backend.distance_filter import passes_distance_filter, is_prose_text as is_prose_text_unified
        
        # Accept both POST JSON bodies and GET query-string params, so any
        # assistant that can only fetch a URL can still run this search.
        data = request.get_json(silent=True) or request.args

        query = data.get('query', '')
        language = data.get('language', 'la')
        search_type = data.get('search_type', 'lemma')
        author_filter = data.get('author', '')
        work_filter = data.get('work', '')
        line_start = data.get('line_start')
        line_end = data.get('line_end')
        # Coerce to int: on a GET request query-string params arrive as strings,
        # and max_results is compared with `len(results) >= max_results`.
        try:
            max_results = int(data.get('max_results', 500))
        except (TypeError, ValueError):
            max_results = 500
        if max_results <= 0:
            max_results = 500

        # count_only: return just the deduped corpus counts (total / distinct_loci
        # / capped) and skip the results payload. Quantifying a "commonplace" for
        # the per-entry corpus-context rule then costs a tiny response instead of
        # hundreds of passages. Accept truthy strings on GET.
        count_only = data.get('count_only', False)
        if isinstance(count_only, str):
            count_only = count_only.strip().lower() in ('1', 'true', 'yes', 'on')

        # rare_focus: opt-in (the Reader's Verbal Parallels tab sets it). Hide
        # results whose shared words are all commonplaces; see
        # rare_focus_filter. The Line Search page never sets it, so deliberate
        # common-word queries there behave exactly as before.
        rare_focus = data.get('rare_focus', False)
        if isinstance(rare_focus, str):
            rare_focus = rare_focus.strip().lower() in ('1', 'true', 'yes', 'on')

        # Documents collection (stage 3b-2, behind TESSERAE_DOCUMENTS=1): search
        # literature (default, today's exact behaviour), the documentary corpus
        # (inscriptions/papyri), or both. Omitting `collection` entirely, or the
        # switch being off, must leave every byte of the response unchanged —
        # so the literary code path below is never altered by this parameter;
        # it is only ever read at the two insertion points this stage added
        # (the early documents-only return, and the pre-return merge for
        # 'both'). See backend/documents.py.
        collection = (data.get('collection') or 'literature').strip().lower()
        if collection not in ('literature', 'documents', 'both'):
            collection = 'literature'
        import backend.documents as _docs_mod
        documents_active = collection in ('documents', 'both') and _docs_mod.enabled()

        def _coerce_year(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
        date_from = _coerce_year(data.get('date_from')) if documents_active else None
        date_to = _coerce_year(data.get('date_to')) if documents_active else None
        doc_region_filter = (data.get('region') or '').strip() if documents_active else ''
        doc_text_type_filter = (data.get('text_type') or '').strip() if documents_active else ''
        doc_material_filter = (data.get('material') or '').strip() if documents_active else ''
        doc_source_filter = (data.get('source') or '').strip() if documents_active else ''
        # 'inscriptions' or 'papyri'; anything else (or omitted) means both.
        doc_kind_filter = (data.get('kind') or '').strip().lower() if documents_active else ''
        if doc_kind_filter not in ('inscriptions', 'papyri'):
            doc_kind_filter = ''

        # Stage 3b-3: leave out a document hit whose match rests entirely on
        # restored text (documents/both only -- see _restoration_flags).
        doc_exclude_restored = False
        if documents_active:
            doc_exclude_restored = data.get('exclude_restored', False)
            if isinstance(doc_exclude_restored, str):
                doc_exclude_restored = doc_exclude_restored.strip().lower() in ('1', 'true', 'yes', 'on')

        # Stage 3b-3: hide a document hit whose matched lemmas/phrase co-occur
        # in more than N documents in this same index (a stock formula --
        # see _documents_formula_count and DOCUMENTS_FORMULA_DEFAULT_N).
        # Off by default; the caller passes an integer (any int, including 0)
        # to turn it on, so `0` is a valid, deliberately strict threshold, not
        # treated as falsy-and-ignored.
        doc_hide_formulas = None
        if documents_active:
            _hide_formulas_raw = data.get('hide_formulas')
            if _hide_formulas_raw not in (None, ''):
                try:
                    doc_hide_formulas = int(_hide_formulas_raw)
                except (TypeError, ValueError):
                    doc_hide_formulas = None

        # Stage 4 (owner's review of the live trial, 2026-10-08): document
        # hits no longer stop at a fixed 500-row ceiling (a stock phrase
        # like "dis manibus" is in roughly 35,000 of them) -- they are
        # paged server-side (`doc_offset`/`doc_limit`, 50 rows per page by
        # default, `doc_limit` clamped to that range so a request cannot
        # ask this endpoint to build an unbounded page) and ranked by
        # `doc_sort` (see _DOCUMENT_SORT_MODES/_document_sort_key): default
        # 'relevance' puts an exact adjacent phrase ahead of scattered
        # words, a match on surviving text ahead of one resting on restored
        # words, fewer extra restorations, then earliest date; 'oldest'/
        # 'newest' sort on date alone; 'region' sorts alphabetically.
        doc_sort = 'relevance'
        doc_offset = 0
        doc_limit = 50
        if documents_active:
            doc_sort = (data.get('sort') or 'relevance').strip().lower()
            if doc_sort not in _DOCUMENT_SORT_MODES:
                doc_sort = 'relevance'
            try:
                doc_offset = max(0, int(data.get('offset', 0)))
            except (TypeError, ValueError):
                doc_offset = 0
            try:
                doc_limit = int(data.get('limit', 50))
            except (TypeError, ValueError):
                doc_limit = 50
            doc_limit = max(1, min(50, doc_limit))

        # Source exclusion - don't include the source line in results
        exclude_text_id = data.get('exclude_text_id', '')
        exclude_locus = data.get('exclude_locus', '')
        
        line_text = data.get('line_text', '')
        
        if query:
            import time as time_module
            search_start_time = time_module.time()

            # collection='documents': the documentary corpus alone, no
            # literary search at all. Returns here; nothing below this
            # block runs, so it cannot affect the literary path (collection
            # omitted, or 'literature', or the switch off) in any way.
            if collection == 'documents' and documents_active:
                return _line_search_documents_only(
                    query, language, search_type, doc_offset, doc_limit, doc_sort, count_only,
                    date_from, date_to, doc_region_filter, doc_text_type_filter,
                    doc_material_filter, doc_source_filter, search_start_time,
                    exclude_restored=doc_exclude_restored, hide_formulas=doc_hide_formulas,
                    kind=doc_kind_filter)
            if collection == 'documents' and not documents_active:
                # Documents requested but the switch is off, or this
                # language has no documents index: literature's own
                # behaviour is the only sane fallback (never a silent
                # empty result), so fall through to it unchanged.
                collection = 'literature'

            try:
                from backend.metrical_scanner import is_prose_text
            except ImportError:
                from metrical_scanner import is_prose_text
            lang_dir = os.path.join(TEXTS_DIR, language)
            lang_dates = AUTHOR_DATES.get(language, {})
            
            if not fspaths.exists(lang_dir):
                return jsonify({'results': [], 'total': 0})
            
            # Build stoplist: ALWAYS include base stopwords (ab, et, in, etc.) 
            # plus optionally top N corpus-frequent lemmas
            from backend.matcher import DEFAULT_LATIN_STOP_WORDS, DEFAULT_GREEK_STOP_WORDS, DEFAULT_ENGLISH_STOP_WORDS
            
            # Start with base stopwords for the language
            if language == 'la':
                stopwords = set(DEFAULT_LATIN_STOP_WORDS)
            elif language == 'grc':
                stopwords = set(DEFAULT_GREEK_STOP_WORDS)
            elif language == 'en':
                stopwords = set(DEFAULT_ENGLISH_STOP_WORDS)
            else:
                # Persian, Urdu, Arabic, Coptic, Hebrew: the language's own
                # curated list. The English list applied here left every
                # Persian particle searchable, and one line of Hafez took
                # eleven minutes (2026-09-07).
                # Production's matcher has no language plugins yet (they come
                # with the Persian, Urdu and Arabic work), so fall back to the
                # list this branch always used.
                try:
                    from backend.matcher import _plugin_stoplist
                except ImportError:
                    _plugin_stoplist = None
                stopwords = set((_plugin_stoplist(language) if _plugin_stoplist else None)
                                or DEFAULT_ENGLISH_STOP_WORDS)
            
            # Optionally add top N corpus-frequent lemmas
            stoplist_size = data.get('stoplist_size', 10)
            corpus_freq_data = get_corpus_frequencies(language, text_processor)
            corpus_frequencies = corpus_freq_data.get('frequencies', {}) if corpus_freq_data else {}
            if stoplist_size > 0 and corpus_frequencies:
                sorted_lemmas = sorted(corpus_frequencies.items(), key=lambda x: x[1], reverse=True)
                stopwords.update(lemma for lemma, _ in sorted_lemmas[:stoplist_size])
            
            query_lemmas = set()
            # THE INDEX ALREADY KNOWS THE LEMMAS OF ITS OWN LINES. When the
            # Reader asks about lines of a work (it names them in `refs`, or
            # the first in exclude_text_id + exclude_locus), their lemmas are
            # read from the index's lines table instead of re-tagged. For
            # Persian, Urdu and Arabic re-tagging meant loading Stanza inside
            # the web process (gigabytes, minutes; the app grew to 10 GB).
            _stanza_langs = ('fa', 'ur', 'ar')
            _ref_list = [str(r) for r in (data.get('refs') or []) if r]
            if not _ref_list and data.get('exclude_text_id') and data.get('exclude_locus'):
                _stem = str(data['exclude_text_id']).replace('.tess', '')
                _ref_list = [f"{_stem}.{data['exclude_locus']}"]
            # Only for those three languages. On production the index path
            # changed Latin Reader results (Aeneid 1.33 came back empty on
            # 2026-09-11) because the index's lemma spellings differ from the
            # lemmatizer's; Latin, Greek and the rest keep the lemmatizer.
            if (search_type == 'lemma' and language in _stanza_langs and _ref_list
                    and data.get('exclude_text_id') and has_lines_data(language)):
                _stem = str(data['exclude_text_id']).replace('.tess', '')
                _rows = get_lines_batch(f'{_stem}.tess', _ref_list, language)
                for _row in _rows.values():
                    query_lemmas.update(_normalize_lemma(l, language) for l in (_row.get('lemmas') or []) if l)
            if search_type == 'lemma' and not query_lemmas:
                query_tokens = query.lower().split()
                try:
                    from backend.perso_arabic import _base_normalize
                except ImportError:
                    # The Persian, Urdu and Arabic normalizer lives on the
                    # preview branch; without it every language takes the
                    # lemmatizer path below.
                    _base_normalize = None
                if language in _stanza_langs and _base_normalize is not None:
                    # A typed query in these languages is searched by its
                    # normalized surface forms (the language's own normalizer,
                    # the one the index lemmas went through); nouns and most
                    # words are their own lemma, and no tagger runs here.
                    from backend.perso_arabic import _base_normalize
                    from backend.surface_lemmas import lemma_for
                    query_lemmas = set()
                    for t in query_tokens:
                        n = _base_normalize(t, language)
                        if not n:
                            continue
                        # The lemma the tagger gave this form when it built the
                        # index, from a table over the lemma caches. Without it
                        # an inflected form ("الديار") matched nothing, since
                        # the index is keyed by lemma ("دار"). The lemma
                        # replaces the form: the search wants every query
                        # lemma in the line, so a form that is not itself a
                        # lemma would rule every line out (2026-09-08).
                        lem = lemma_for(n, language)
                        query_lemmas.add(lem or n)
                else:
                    for token in query_tokens:
                        lemmas = text_processor.lemmatize_word(token, language)
                        query_lemmas.update(_normalize_lemma(l, language) for l in lemmas)
                if not query_lemmas:
                    query_lemmas = set(_normalize_lemma(t, language) for t in query_tokens)
            else:
                query_lemmas = set(_normalize_lemma(t, language) for t in query.lower().split())
            
            # A Hebrew query typed without vowel points: each lemma also
            # matches its other homograph readings (אל typed bare finds "to",
            # "not" and "God"), through the index's fallback forms.
            query_fallback_forms = None
            if language == 'he' and search_type == 'lemma':
                query_fallback_forms, query_lemmas = _hebrew_unpointed_fallbacks(query, query_lemmas, stopwords)

            # Filter out stopwords from query lemmas (like pairwise search)
            content_lemmas = query_lemmas - stopwords
            filtered_query_lemmas = content_lemmas
            if len(filtered_query_lemmas) < 2:
                # Restore the common words so the co-occurrence search can still
                # run — a two-word query whose second word is too common to index
                # on its own is still a PAIR query, not a single-word one.
                filtered_query_lemmas = query_lemmas

            # Words dropped as too-common, named in the response so a reduced
            # multi-word query is not silently answered as a different question.
            filtered_common_words = sorted(query_lemmas - content_lemmas)
            n_query_words = len([w for w in query.split() if w.strip()])

            # A PASSAGE-SIZED QUERY SEARCHES ON ITS RAREST WORDS. The Reader's
            # Verbal Parallels tab sends the whole selection as one query; six
            # Aeneid lines lemmatize to 40 lemmas, whose posting lists union to
            # 269,850 candidate lines and 97 seconds of search (measured
            # 2026-08-29). Two shared words out of 40
            # is also a commonplace, not a parallel. So above a cap the query
            # keeps only its rarest lemmas by corpus document frequency, which
            # is both the fast search and the Tesserae-shaped question: lines
            # sharing the passage's DISTINCTIVE vocabulary. The reduction is
            # named in the response, never silent.
            LEMMA_CAP = 12
            reduced_from = None
            if len(filtered_query_lemmas) > LEMMA_CAP:
                try:
                    import sqlite3 as _sq
                    from backend.lexical_density import _index_path
                    _conn = _sq.connect(f'file:{_index_path(language)}?mode=ro',
                                        uri=True)
                    _df = {}
                    for _lem in filtered_query_lemmas:
                        _r = _conn.execute(
                            'SELECT df FROM lemma_doc_freq WHERE lemma = ?',
                            (_lem,)).fetchone()
                        _df[_lem] = _r[0] if _r else 0
                    _conn.close()
                    _present = [l for l in filtered_query_lemmas if _df[l] > 0]
                    if len(_present) > LEMMA_CAP:
                        reduced_from = len(filtered_query_lemmas)
                        filtered_query_lemmas = set(
                            sorted(_present, key=lambda l: _df[l])[:LEMMA_CAP])
                except Exception as _e:
                    # No doc-freq table for this language: search as-is, but say
                    # so, because the silent form of this fallback is how the
                    # missing Hebrew and Coptic tables went unnoticed.
                    app.logger.warning(
                        '[LINE-SEARCH] passage-query reduction unavailable for '
                        '%s (%s); searching on all %d lemmas', language, _e,
                        len(filtered_query_lemmas))

            # WORDS PRINTED EITHER JOINED OR APART (Latin, lemma mode). A query
            # "quo usque tandem" finds a line printing "quousque tandem", and
            # a query "quousque" finds a line printing "quo usque", for the
            # short curated list in backend/univerbation.py. Query side only:
            # the joined forms count as fallback readings of the parts (and
            # the parts of the joined form) in the index lookup, and the
            # reverse direction is verified against the line's own lemma
            # sequence below, so "quousque tandem" does not match every line
            # with qui and tandem.
            univ_forward, univ_sequences = {}, {}
            if language == 'la' and search_type == 'lemma':
                try:
                    from backend import univerbation as _univ
                    _qtoks = query.lower().split()
                    univ_forward = _univ.expand_parts(_qtoks, _univerbation_lemmatize)
                    _rev_fb, univ_sequences = _univ.expand_joined(
                        _qtoks, _univerbation_lemmatize, stopwords)
                    univ_forward = {k: v for k, v in univ_forward.items() if k in filtered_query_lemmas}
                    univ_sequences = {k: v for k, v in univ_sequences.items() if k in filtered_query_lemmas}
                    _rev_fb = {k: v for k, v in _rev_fb.items() if k in univ_sequences}
                    query_fallback_forms = _univ.merge_fallbacks(query_fallback_forms, univ_forward, _rev_fb)
                except Exception:
                    app.logger.exception('[LINE-SEARCH] univerbation expansion failed; searching without it')
                    univ_forward, univ_sequences = {}, {}
            univ_active = bool(univ_forward or univ_sequences)

            # Single-word count_only: route here ONLY when the query LITERALLY has
            # one word. A multi-word query that common-word filtering reduces to a
            # single content word is still a co-occurrence (pair) query and must
            # run the pair search with the common word restored — reclassifying it
            # as single-word silently turned countable pairings like "bis nostra"
            # (22 places) into a work-count for "bis" (368 works). A one-word query
            # can't co-occur with anything, so answer how common the word is across
            # the corpus (document frequency) instead of a silent zero.
            if count_only and n_query_words <= 1:
                from backend.blueprints.hapax import get_document_frequencies_batch
                if content_lemmas:
                    dfs = get_document_frequencies_batch(content_lemmas, language)
                    df = max(dfs.values()) if dfs else 0
                    return jsonify({
                        'query': query,
                        'single_word': True,
                        'unit': 'works',
                        'corpus_document_frequency': df,
                        'total': df,
                        'corpus_version': get_corpus_version(language),
                        'note': ('single-word query: count is the number of works that contain '
                                 'this word, not co-occurring word pairs'),
                    })
                return jsonify({
                    'query': query, 'single_word': True, 'total': None, 'unquantified': True,
                    'corpus_version': get_corpus_version(language),
                    'note': 'query has no content words to count (all stopwords)',
                })

            results = []
            seen_results = set()
            by_work_all = None
            
            # FAST PATH: Use inverted index if available (O(1) lookup vs O(n) scan).
            # A single-word query (one content lemma) has nothing to co-occur with,
            # so it just lists the lines that contain the word (min_matches=1);
            # multi-word queries still require the pair to co-occur (min_matches=2).
            # 1 for a single-word query, 2 for multi-word; never 0 (an empty
            # lemma set would otherwise admit every line — it also can't reach the
            # fast-path guard below, but max(1,...) makes that safety explicit).
            min_matched = max(1, min(2, len(filtered_query_lemmas)))
            if search_type == 'lemma' and is_index_available(language) and len(filtered_query_lemmas) >= 1:
                candidates = find_co_occurring_lemmas(list(filtered_query_lemmas), language, min_matches=min_matched, fallback_forms=query_fallback_forms)
                use_indexed_lines = has_lines_data(language)
                
                # Group candidates by text
                text_candidates = {}
                for filename, ref, matching_lemmas, positions in candidates:
                    if filename not in text_candidates:
                        text_candidates[filename] = []
                    text_candidates[filename].append((ref, matching_lemmas, positions))

                # A joined query word found through its parts (reverse
                # direction) is kept only where the parts stand next to each
                # other in the line, in order. Done before the per-work counts
                # so they count the lines that will be listed.
                prefetched_lines = {}
                if univ_sequences and use_indexed_lines:
                    for _fn in list(text_candidates):
                        _ld = get_lines_batch(_fn, [r for r, _, _ in text_candidates[_fn]], language) or {}
                        prefetched_lines[_fn] = _ld
                        _kept = []
                        for _ref, _ml, _pos in text_candidates[_fn]:
                            _li = _ld.get(_ref)
                            if _li:
                                _toks = _li.get('tokens') or []
                                _mset, _, _ = _univ.match_line(
                                    [[_l] for _l in (_li.get('lemmas') or [])], _toks,
                                    filtered_query_lemmas, univ_forward, univ_sequences)
                                _ml = set(_ml) & _mset
                                if len(_ml) < min_matched:
                                    continue
                            _kept.append((_ref, _ml, _pos))
                        if _kept:
                            text_candidates[_fn] = _kept
                        else:
                            del text_candidates[_fn]

                # EVERY WORK'S COUNT, NOT JUST THE FIRST 500 LINES (2026-10-07).
                # The line list stops at max_results in index order, so for a
                # common pair (Persian "man ast") it held lines from two or three
                # poets and the corpus chart left out the very authors compared.
                # The index already returned every co-occurring line, so counting
                # them per work costs nothing. A work held both whole and in book
                # files is counted once: the whole file when present, else the sum
                # of its books. Counted AFTER the closeness rule (2026-10-11), from
                # the index's positions, so the chart counts the lines the list
                # would keep: it used to count every line containing the words
                # and then list none for a prose chapter with the words far apart.
                by_work_all = _count_candidates_by_work(text_candidates, language, lang_dates)
                
                for filename, matches in text_candidates.items():
                    filepath = resolve_text_path(TEXTS_DIR, language, filename)
                    if not filepath:
                        continue
                    
                    metadata = get_text_metadata(filepath)
                    if author_filter and metadata['author'] != author_filter:
                        continue
                    if work_filter and filename != work_filter and metadata['title'] != work_filter:
                        continue
                    
                    author_key = filename.split('.')[0].lower()
                    author_info = lang_dates.get(author_key, {})
                    era = author_info.get('era', 'Unknown')
                    # None (not the 9999 sentinel) for an unknown year, so it does
                    # not leak into output and plot as year 9999 on a timeline.
                    year = author_info.get('year')

                    # Get line data from index
                    refs_needed = [ref for ref, _, _ in matches]
                    lines_data = {}
                    if use_indexed_lines:
                        lines_data = (prefetched_lines.get(filename)
                                      or get_lines_batch(filename, refs_needed, language) or {})
                    
                    # Fallback: build a lookup from the actual file if lines_data is empty
                    file_lines_lookup = {}
                    if not lines_data:
                        try:
                            with fspaths.open_text(filepath, 'r', encoding='utf-8', errors='replace') as f:
                                for line in f:
                                    line = line.strip()
                                    if line.startswith('<') and '>' in line:
                                        tag_end = line.index('>')
                                        line_ref = line[1:tag_end]
                                        line_text = line[tag_end+1:].strip()
                                        file_lines_lookup[line_ref] = line_text
                        except Exception:
                            app_logger.exception(f"Error loading lines for {filename}")
                    
                    for ref, matching_lemmas, positions in matches:
                        result_key = (filename, ref)
                        if result_key in seen_results:
                            continue
                        
                        # Get text from index or fallback to file lookup
                        line_info = lines_data.get(ref)
                        if line_info:
                            text = line_info.get('text', '')
                        elif ref in file_lines_lookup:
                            text = file_lines_lookup[ref]
                            line_info = None  # Mark as file fallback
                        else:
                            continue  # Skip if no text available
                        
                        # Canonical short locus: strips CTS URNs and text-id
                        # prefixes (Hebrew "hebrew_bible.isaiah.34.11" -> "34.11").
                        locus = format_short_locus(ref)
                        
                        # Find matched words in text using pre-indexed lemmas
                        matched_words = []
                        matched_lemma_set = set()
                        matched_positions = []
                        indexed_lemmas = set(line_info.get('lemmas', [])) if line_info else set()
                        indexed_tokens = line_info.get('tokens', []) if line_info else []

                        # Use indexed data if available, otherwise fallback to quick token matching
                        if indexed_lemmas and univ_active:
                            # Joined words count as the parts they stand for,
                            # and parts printed apart as the joined word.
                            matched_lemma_set, matched_words, matched_positions = _univ.match_line(
                                [[_l] for _l in line_info.get('lemmas', [])], indexed_tokens,
                                filtered_query_lemmas, univ_forward, univ_sequences)
                        elif indexed_lemmas:
                            # Match query lemmas (and a bare Hebrew word's
                            # other readings) against indexed lemmas
                            matching_query_lemmas = _line_lemmas_matching_query(
                                indexed_lemmas, filtered_query_lemmas, query_fallback_forms)
                            if matching_query_lemmas:
                                matched_lemma_set = set(matching_query_lemmas)
                                # Find the actual words that correspond to matching lemmas
                                for i, lemma in enumerate(line_info.get('lemmas', [])):
                                    if lemma in matching_query_lemmas and i < len(indexed_tokens):
                                        matched_words.append(indexed_tokens[i])
                                        matched_positions.append(i)
                        else:
                            # Quick fallback: just check token overlap without full lemmatization
                            text_tokens = set(re.sub(r'[^\w\s]', '', text.lower()).split())
                            for token in text_tokens:
                                if token in filtered_query_lemmas:
                                    matched_words.append(token)
                                    matched_lemma_set.add(token)
                        
                        if univ_active and indexed_lemmas:
                            # one joined word can stand for two query words
                            if len(matched_lemma_set) < min_matched:
                                continue
                        elif len(set(matched_words)) < min_matched:
                            continue
                        
                        # Exclude source line if specified (normalize both sides for robust matching)
                        if exclude_text_id and exclude_locus:
                            # Normalize text_id comparison (handle with/without .tess, case-insensitive)
                            exclude_text_normalized = exclude_text_id.replace('.tess', '').lower()
                            filename_normalized = filename.replace('.tess', '').lower()
                            # Normalize locus comparison (clean CTS format on both sides)
                            exclude_locus_clean = clean_cts_reference(exclude_locus) if exclude_locus else ''
                            locus_clean = clean_cts_reference(locus) if locus else ''
                            if filename_normalized == exclude_text_normalized and locus_clean == exclude_locus_clean:
                                continue
                        
                        # Distance filter
                        if not passes_distance_filter(text, matched_words, filename, language):
                            continue
                        
                        seen_results.add(result_key)
                        _line_tokens = indexed_tokens or text.split()
                        _n_surface = _surface_hits(query, _line_tokens, language)
                        _n_surface_near = _surface_hits(
                            query, _line_tokens, language, window=n_query_words + 2)
                        results.append({
                            'text_id': filename,
                            'author': metadata['author'],
                            'work': metadata['title'],
                            'locus': locus,
                            'text': text,
                            'era': era,
                            'year': year,
                            'is_poetry': not is_prose_text_unified(filename, language),
                            'matched_words': matched_words,
                            # Distinct query lemmas this line shares, for
                            # rarity-aware filtering downstream (rare_focus).
                            # The scan path below sets the same field.
                            'matched_lemmas': sorted(matched_lemma_set),
                            # Closeness to the query (owner's review
                            # 2026-10-10: a four-word query put lines
                            # sharing one word on top). n_matched counts the
                            # query's content lemmas this line shares;
                            # `quotation` is true when it shares all of them
                            # within a window of two tokens more than the
                            # query's own length, which is a near quotation.
                            'n_matched': len(matched_lemma_set),
                            'n_surface': _n_surface,
                            'span': _span(matched_positions),
                            'quotation': _is_near_quotation(
                                matched_lemma_set, filtered_query_lemmas, matched_positions, query,
                                surface_hits=_n_surface_near),
                        })
                        
                        if len(results) >= max_results:
                            break
                    
                    if len(results) >= max_results:
                        break
            
            else:
                # SLOW PATH: Fallback to file scanning (for exact/regex search)
                # Compile the exact-phrase pattern once (whole-word-start matching).
                # Hebrew: users type unpointed queries, but the corpus text is
                # pointed (niqqud + cantillation). Strip pointing from the query
                # here and from each line before the regex runs, so an unpointed
                # exact search matches the pointed text (pointed text is kept for
                # display). See strip_hebrew_pointing.
                he_exact = (search_type == 'exact' and language == 'he')
                exact_query = strip_hebrew_pointing(query) if he_exact else query
                exact_pattern = exact_phrase_pattern(exact_query) if search_type == 'exact' else None
                text_files = [f for f in fspaths.listdir_text(lang_dir) if f.endswith('.tess')]
                
                for filename in text_files:
                    filepath = os.path.join(lang_dir, filename)
                    metadata = get_text_metadata(filepath)
                    
                    if author_filter and metadata['author'] != author_filter:
                        continue
                    if work_filter and filename != work_filter and metadata['title'] != work_filter:
                        continue
                    
                    author_key = filename.split('.')[0].lower()
                    author_info = lang_dates.get(author_key, {})
                    era = author_info.get('era', 'Unknown')
                    # None (not the 9999 sentinel) for an unknown year, so it does
                    # not leak into output and plot as year 9999 on a timeline.
                    year = author_info.get('year')

                    with fspaths.open_text(filepath, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if not line or not line.startswith('<'):
                                continue
                            
                            try:
                                end_tag = line.index('>')
                                full_locus = line[1:end_tag].strip()
                                text = line[end_tag+1:].strip()
                                locus = format_short_locus(full_locus)
                            except ValueError:
                                continue
                            
                            if line_start or line_end:
                                try:
                                    parts = locus.split()
                                    line_num = int(parts[-1]) if parts else 0
                                    if line_start and line_num < line_start:
                                        continue
                                    if line_end and line_num > line_end:
                                        continue
                                except (ValueError, IndexError):
                                    pass
                            
                            match_found = False
                            univ_line = None
                            if search_type == 'exact':
                                # Whole-word-start match (see _exact_phrase_pattern):
                                # excludes substring hits like "quot" inside "aliquot".
                                # Hebrew matches on the pointing-stripped layer; other
                                # languages are NFC-normalized so a precomposed Greek query
                                # matches text stored decomposed (Homer Il. 1.1 μῆνιν ἄειδε
                                # is NFD in the corpus). Both normalize the query side too.
                                match_text = strip_hebrew_pointing(text) if he_exact else exact_search_text(text)
                                if he_exact and ('[' in match_text or '(' in match_text):
                                    # Qere/ketiv, printed "[qere] (ketiv)" or
                                    # "(ketiv) [qere]": a phrase may run through
                                    # EITHER reading. Linearize both readings of the
                                    # line and match if either contains the phrase,
                                    # so exact search for the qere or the ketiv form
                                    # both find the verse.
                                    qere_line = re.sub(r'\[([^\[\]]+)\]\s*\(([^()]+)\)', r'\1', match_text)
                                    qere_line = re.sub(r'\(([^()]+)\)\s*\[([^\[\]]+)\]', r'\2', qere_line)
                                    ketiv_line = re.sub(r'\[([^\[\]]+)\]\s*\(([^()]+)\)', r'\2', match_text)
                                    ketiv_line = re.sub(r'\(([^()]+)\)\s*\[([^\[\]]+)\]', r'\1', ketiv_line)
                                    if exact_pattern and (exact_pattern.search(qere_line) or exact_pattern.search(ketiv_line)):
                                        match_found = True
                                elif exact_pattern and exact_pattern.search(match_text):
                                    match_found = True
                            elif search_type == 'regex':
                                try:
                                    if re.search(query, text, re.IGNORECASE):
                                        match_found = True
                                except re.error:
                                    pass
                            elif univ_active:
                                # Latin words joined or apart: judged on the
                                # line's own word sequence.
                                _uw = re.sub(r'[^\w\s]', '', text.lower()).split()
                                _usets = []
                                for _w in _uw:
                                    _ls = set(text_processor.lemmatize_word(_w, language))
                                    _ls.add(_w)
                                    _usets.append(_ls)
                                univ_line = _univ.match_line(
                                    _usets, _uw, filtered_query_lemmas, univ_forward, univ_sequences)
                                match_found = bool(univ_line[0])
                            else:
                                text_lower = text.lower()
                                text_words = set(re.sub(r'[^\w\s]', '', text_lower).split())
                                text_lemmas = set()
                                for word in text_words:
                                    lemmas = text_processor.lemmatize_word(word, language)
                                    text_lemmas.update(lemmas)
                                text_lemmas.update(text_words)
                                
                                # Use filtered query lemmas (without stopwords)
                                if filtered_query_lemmas & text_lemmas:
                                    match_found = True
                            
                            if match_found:
                                matched_words = []
                                matched_lemmas = set()  # Track unique lemmas matched (excluding stopwords)
                                if search_type == 'lemma' and univ_line is not None:
                                    matched_lemmas = set(univ_line[0])
                                    matched_words = list(univ_line[1])
                                elif search_type == 'lemma':
                                    for word in re.sub(r'[^\w\s]', '', text.lower()).split():
                                        word_lemmas = text_processor.lemmatize_word(word, language)
                                        word_lemmas.add(word)
                                        # Only count matches with filtered lemmas (no stopwords)
                                        shared_lemmas = word_lemmas & filtered_query_lemmas
                                        if shared_lemmas:
                                            matched_words.append(word)
                                            matched_lemmas.update(shared_lemmas)
                                elif search_type == 'exact':
                                    # The exact pattern already required the whole adjacent
                                    # phrase, so every query word is present. Count them ALL,
                                    # including stopwords — they are part of the phrase the user
                                    # asked for (e.g. "ad Scythiam"), not co-occurrence noise to
                                    # filter. Without this, a phrase containing a stopword falls
                                    # below the 2-word threshold and is silently dropped.
                                    for word in query.split():
                                        wl = word.lower()
                                        matched_words.append(wl)
                                        matched_lemmas.add(wl)
                                else:
                                    for word in query.lower().split():
                                        if word in text.lower() and word not in stopwords:
                                            matched_words.append(word)
                                            matched_lemmas.add(word)
                                
                                # Co-occurrence (lemma/regex) search needs at least 2 distinct
                                # lemmas — a single word in isolation is not a co-occurrence.
                                # Exact-phrase search is different: the user asked for that
                                # specific phrase, so a single-word query is a complete and
                                # valid match and must not be dropped here (issue #502: Coptic
                                # single-word exact queries returned nothing).
                                if search_type != 'exact' and len(matched_lemmas) < 2:
                                    continue
                                
                                # Exclude source line if specified (normalize both sides for robust matching)
                                if exclude_text_id and exclude_locus:
                                    exclude_text_normalized = exclude_text_id.replace('.tess', '').lower()
                                    filename_normalized = filename.replace('.tess', '').lower()
                                    exclude_locus_clean = clean_cts_reference(exclude_locus) if exclude_locus else ''
                                    locus_clean = clean_cts_reference(locus) if locus else ''
                                    if filename_normalized == exclude_text_normalized and locus_clean == exclude_locus_clean:
                                        continue
                                
                                # UNIFIED DISTANCE FILTERING (same logic as pairwise search)
                                if not passes_distance_filter(text, matched_words, filename, language):
                                    continue
                                
                                results.append({
                                    'text_id': filename,
                                    'author': metadata['author'],
                                    'work': metadata['title'],
                                    'locus': locus,
                                    'text': text,
                                    'era': era,
                                    'year': year,
                                    'is_poetry': not is_prose_text_unified(filename, language),
                                    'matched_words': matched_words,
                                    # The distinct query lemmas this line shares,
                                    # for rarity-aware filtering downstream.
                                    'matched_lemmas': sorted(matched_lemmas),
                                    # An exact or pattern hit carries the whole
                                    # query by construction (closeness ranking).
                                    'n_matched': len(matched_lemmas),
                                    'n_surface': (len(query.split()) if search_type == 'exact'
                                                  else _surface_hits(query, text.split(), language)),
                                    'span': None,
                                    'quotation': search_type == 'exact',
                                })
                                
                                if len(results) >= max_results:
                                    break
                    
                    if len(results) >= max_results:
                        break
            
            # Sort results: first by era (chronological), then by year, then alphabetically by author
            era_order = {
                'Biblical': -1,
                'Archaic': 0, 'Early Greek': 1, 'Classical': 2, 'Hellenistic': 3,
                'Republic': 4, 'Late Republican': 5, 'Late Republic': 5,
                'Augustan': 6, 'Early Imperial': 7, 'Imperial': 8, 
                'Later Imperial': 9, 'Late Antique': 10, 'Patristic': 10,
                'Carolingian': 11, 'Medieval': 12, 'Renaissance': 13, 
                'Early Modern': 14, 'Modern': 15, 'Unknown': 99
            }
            results.sort(key=lambda x: (
                era_order.get(x.get('era', 'Unknown'), 50),
                x.get('year') if x.get('year') is not None else 9999,
                x.get('author', '').lower()
            ))
            
            search_time = round(time_module.time() - search_start_time, 3)

            # Whether the corpus scan hit the result cap. When it did, `total`
            # is a floor, not an exact count — callers should report "N+" rather
            # than a false precise number. (The build loop breaks as soon as
            # len(results) reaches max_results.)
            capped = len(results) >= max_results

            # Collapse the corpus's whole-work vs .part.N duplication: e.g.
            # vergil.eclogues.tess and vergil.eclogues.part.1.tess both report
            # Eclogues 1.43, so an undeduped list double-counts the same line and
            # inflates the corpus-uniqueness signal (~2x for parted works). Key on
            # the .part.N-stripped text_id plus locus (whole and part normalize to
            # the same id; their `work` labels differ — "Eclogues" vs "Eclogues,
            # Book 1" — so we cannot key on work). Different works keep distinct
            # ids. Prefer the whole-work row as the canonical representative.
            import re as _re_dl

            def _base_tid(tid):
                return _re_dl.sub(r'\.part\.\d+.*\.tess$', '.tess', tid) if tid else tid

            _pos = {}
            _deduped = []
            for r in results:
                k = (_base_tid(r.get('text_id')) or r.get('author'), r.get('locus'))
                if k not in _pos:
                    _pos[k] = len(_deduped)
                    _deduped.append(r)
                else:
                    idx = _pos[k]
                    if '.part.' in (_deduped[idx].get('text_id') or '') and '.part.' not in (r.get('text_id') or ''):
                        _deduped[idx] = r
            results = _deduped

            # Second pass: collapse the SAME passage duplicated across text_ids
            # that vary only by author/work naming (see _dedup_same_passage).
            results = _dedup_same_passage(results)

            rare_focus_report = None
            if rare_focus and search_type == 'lemma':
                results, _hidden, _commons = rare_focus_filter(results, language)
                if _hidden:
                    rare_focus_report = {
                        'hidden': _hidden,
                        'common_lemmas': _commons,
                    }

            distinct_loci = len(results)
            payload = {
                'total': distinct_loci,
                'distinct_loci': distinct_loci,
                'query': query,
                # How many content lemmas the query had, so a page can show
                # "3 of 4 words" beside each line (closeness ranking).
                'query_lemma_count': len(filtered_query_lemmas),
                # And how many words it had as typed, so the page can say
                # "key words" when common words were dropped.
                'query_word_count': n_query_words,
                'search_time': search_time,
                'capped': capped,
                'corpus_version': get_corpus_version(language),
            }
            if capped:
                # `total`/`distinct_loci` are a lower bound under the cap.
                payload['total_at_least'] = distinct_loci
            if filtered_common_words:
                # A common word in the query was too frequent to index on its own;
                # it WAS still used for co-occurrence. Naming it lets the caller say
                # the pairing leans on the other word rather than mis-report rarity.
                payload['filtered_common_words'] = filtered_common_words
            if rare_focus_report:
                payload['rare_focus'] = rare_focus_report
            if reduced_from:
                payload['query_reduced'] = {
                    'from_lemmas': reduced_from,
                    'to_lemmas': sorted(filtered_query_lemmas),
                    'note': ('Passage-sized query: searched on its '
                             f'{len(filtered_query_lemmas)} rarest words'),
                }
            if by_work_all is not None:
                payload['by_work_all'] = by_work_all
                payload['lines_all'] = sum(w['count'] for w in by_work_all)

            # collection='both': append the documentary corpus's own hits
            # after the literary ones, reusing the SAME filtered_query_lemmas/
            # min_matched this literary search already computed above (for
            # la/grc, line_search's literary lemma extraction takes the same
            # plain-lemmatizer path _line_search_documents_only uses on its
            # own, so this is the identical query, not a re-derived one).
            # 'total'/'distinct_loci' above stay LITERATURE-ONLY (unchanged
            # meaning for every existing caller); the documents count is
            # reported separately rather than folded in, so a connector or
            # script already reading 'total' as "how many places in the
            # corpus" is not silently handed a different number depending on
            # a parameter it may not have sent.
            if collection == 'both' and documents_active:
                # min_matched is only ever assigned inside the FAST (index)
                # path above; the SLOW (exact/regex, or no-index) path never
                # sets it, so it is recomputed here with the same formula
                # rather than assumed to exist.
                _docs_min_matched = (max(1, min(2, len(filtered_query_lemmas)))
                                      if search_type == 'lemma' else 1)
                (doc_results, doc_total, doc_by_source_region, doc_by_century,
                 doc_stats) = _search_documents_collection(
                    language, search_type, query, filtered_query_lemmas, _docs_min_matched,
                    doc_offset, doc_limit, date_from, date_to, doc_region_filter,
                    doc_text_type_filter, doc_material_filter, doc_source_filter,
                    exclude_restored=doc_exclude_restored, hide_formulas=doc_hide_formulas,
                    sort=doc_sort, kind=doc_kind_filter)
                payload['collection'] = 'both'
                # Stage 4: 'documents_total' is now the TRUE total (every
                # match after filters), not a count of a 500-row-capped
                # list -- see _search_documents_collection's own docstring.
                payload['documents_total'] = doc_total
                payload['documents_sort'] = doc_sort
                payload['documents_pagination'] = {
                    'offset': doc_offset, 'limit': doc_limit, 'total': doc_total}
                if doc_by_source_region:
                    payload['documents_by_source_region'] = doc_by_source_region
                    payload['documents_lines_all'] = sum(w['count'] for w in doc_by_source_region)
                if doc_by_century:
                    payload['documents_by_century'] = doc_by_century
                if doc_exclude_restored:
                    payload['restored_excluded_count'] = doc_stats['restored_excluded_count']
                if doc_hide_formulas is not None:
                    payload['formulas_hidden_count'] = doc_stats['formulas_hidden_count']
                if doc_stats['formula_summary']:
                    payload['formula_summary'] = doc_stats['formula_summary']
                if not count_only:
                    results = results + doc_results

            if not count_only:
                payload['results'] = results
            return jsonify(payload)
        
        elif line_text or data.get('source_text_id'):
            pass
        else:
            return jsonify({'error': 'Provide query or line_text'}), 400
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@api_route('/line-search-parallel', methods=['POST'])
def line_search_parallel():
    """
    Search a single line against the entire corpus using inverted index for speed.
    
    Uses pre-built inverted index (lemma → locations) for O(1) candidate lookup,
    then scores only the matching lines instead of scanning all texts.
    """
    try:
        from backend.inverted_index import is_index_available, find_co_occurring_lemmas, has_lines_data, get_lines_batch
        
        data = request.get_json() or {}
        
        line_text = data.get('line_text', '')
        line_ref = data.get('line_ref', '')
        source_text_id = data.get('source_text_id', '')
        language = data.get('language', 'la')
        match_type = data.get('match_type', 'lemma')
        max_results = data.get('max_results', 100)
        max_per_text = data.get('max_per_text', 5)
        min_matches = data.get('min_matches', 2)
        exclude_source = data.get('exclude_source', True)
        use_index = data.get('use_index', True)
        stoplist_size = data.get('stoplist_size', 10)
        
        if not line_text and not (source_text_id and line_ref):
            return jsonify({'error': 'Provide line_text or source_text_id + line_ref'}), 400
        
        if source_text_id and line_ref and not line_text:
            line_text = _resolve_line_text(source_text_id, line_ref, language) or ''
        
        if not line_text:
            return jsonify({'error': 'Could not find the specified line'}), 404
        
        source_unit = text_processor.process_line(line_text, language)
        source_lemmas = set(source_unit.get('lemmas', []))
        
        if len(source_lemmas) < 1:
            return jsonify({'error': 'No lemmas found in the line'}), 400
        
        # Extract key phrases for exact phrase matching
        query_normalized = re.sub(r'[^\w\s]', '', line_text.lower())
        query_tokens = query_normalized.split()
        
        # Build phrase patterns: ONLY the first 2-3 word phrase (distinctive opening)
        # This ensures we find "arma virumque" quotations, not just any shared words
        key_phrases = []
        # Primary: first 3 words (most distinctive)
        if len(query_tokens) >= 3:
            key_phrases.append(' '.join(query_tokens[0:3]))
        # Secondary: first 2 words
        if len(query_tokens) >= 2:
            key_phrases.append(' '.join(query_tokens[0:2]))
        
        lang_dir = os.path.join(TEXTS_DIR, language)
        lang_dates = AUTHOR_DATES.get(language, {})
        
        if not fspaths.exists(lang_dir):
            return jsonify({'results': [], 'total': 0, 'texts_searched': 0})
        
        # Get corpus-wide frequencies for global IDF
        corpus_freq_data = get_corpus_frequencies(language, text_processor)
        corpus_frequencies = corpus_freq_data.get('frequencies', {}) if corpus_freq_data else {}
        total_corpus_words = sum(corpus_frequencies.values()) if corpus_frequencies else 1
        
        # Use same stoplist as pairwise search: default language stops + Zipf elbow detection
        stopwords = _build_line_search_stopwords(language, corpus_frequencies)
        
        # Filter source lemmas to exclude stopwords AND short words (same as Matcher)
        # Matcher uses len(lemma) > 2 filter
        # Normalize lemmas for index lookup (Greek diacritics, Latin u/v)
        source_lemmas = {_normalize_lemma(l, language) for l in source_lemmas}
        filtered_source_lemmas = {l for l in source_lemmas if l not in stopwords and len(l) > 2}
        if len(filtered_source_lemmas) < min_matches:
            # Fallback: include longer stopwords if too few content words
            filtered_source_lemmas = {l for l in source_lemmas if len(l) > 2}
        
        all_results = []
        texts_searched = 0
        seen_results = set()
        query_text_lower = line_text.lower().strip()

        # Try to use inverted index for fast lookup
        if use_index and is_index_available(language):
            # FAST PATH: Use inverted index
            candidates = find_co_occurring_lemmas(list(filtered_source_lemmas), language, min_matches)
            
            # Group candidates by text for efficient processing
            text_candidates = {}
            for filename, ref, matching_lemmas, positions in candidates:
                if exclude_source and filename == source_text_id:
                    continue
                if filename not in text_candidates:
                    text_candidates[filename] = []
                text_candidates[filename].append((ref, matching_lemmas, positions))
            
            texts_searched = len(text_candidates)
            
            # Check if we can use the fast path with indexed line data
            use_indexed_lines = has_lines_data(language)
            
            for filename, matches in text_candidates.items():
                filepath = os.path.join(lang_dir, filename)

                # Get line data - FAST: from index, SLOW: from file
                refs_needed = set(ref for ref, _, _ in matches)
                units_by_ref = {}
                
                if use_indexed_lines:
                    # Try fast path first: get lines from the index
                    lines_data = get_lines_batch(filename, list(refs_needed), language)
                    if lines_data:
                        units_by_ref = {ref: {'ref': ref, 'text': data['text'], 'lemmas': data['lemmas'], 'tokens': data['tokens']} 
                                        for ref, data in lines_data.items()}
                
                # Check for any missing refs and fall back to file for those
                missing_refs = refs_needed - set(units_by_ref.keys())
                if missing_refs:
                    if fspaths.exists(filepath):
                        file_units = get_processed_units(filename, language, 'line', text_processor)
                        file_units_by_ref = {u.get('ref', ''): u for u in file_units}
                        for ref in missing_refs:
                            if ref in file_units_by_ref:
                                units_by_ref[ref] = file_units_by_ref[ref]
                
                text_matches = []
                for ref, matching_lemmas, positions in matches:
                    unit = units_by_ref.get(ref)
                    result = _evaluate_line_candidate(
                        unit, ref, filename, filtered_source_lemmas, query_text_lower,
                        source_text_id, line_ref, key_phrases, corpus_frequencies,
                        total_corpus_words, lang_dates, seen_results, min_matches,
                        index_matching_lemmas=matching_lemmas)
                    if result:
                        text_matches.append(result)

                text_matches.sort(key=lambda x: x['score'], reverse=True)
                all_results.extend(text_matches[:max_per_text])
        else:
            # FALLBACK: Scan all texts (original behavior)
            text_files = [f for f in fspaths.listdir_text(lang_dir) if f.endswith('.tess')]
            if exclude_source and source_text_id:
                text_files = [f for f in text_files if f != source_text_id]
            
            for filename in text_files:
                texts_searched += 1
                units = get_processed_units(filename, language, 'line', text_processor)

                text_matches = []
                for unit in units:
                    result = _evaluate_line_candidate(
                        unit, unit.get('ref', ''), filename, filtered_source_lemmas,
                        query_text_lower, source_text_id, line_ref, key_phrases,
                        corpus_frequencies, total_corpus_words, lang_dates,
                        seen_results, min_matches)
                    if result:
                        text_matches.append(result)

                text_matches.sort(key=lambda x: x['score'], reverse=True)
                all_results.extend(text_matches[:max_per_text])
        
        all_results.sort(key=lambda x: x['score'], reverse=True)
        
        all_results = _deduplicate_and_normalize(all_results)
        
        final_results = all_results[:max_results] if max_results > 0 else all_results
        
        user_id = current_user.id if current_user and current_user.is_authenticated else None
        city, country, _ip = get_user_location()
        log_search('Line Search', language, source_text_id, None, line_text,
                  match_type, len(all_results), False, user_id, city, country, _ip)
        
        return jsonify({
            'results': final_results,
            'total': len(all_results),
            'displayed': len(final_results),
            'texts_searched': texts_searched,
            'query_line': line_text,
            'query_ref': line_ref if line_ref else 'Manual Query',
            'query_text_id': source_text_id if source_text_id else 'custom_query',
            'query_lemmas': list(filtered_source_lemmas),
            'all_lemmas': list(source_lemmas),
            'stopwords_filtered': list(stopwords & source_lemmas)
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@api_route('/corpus-search', methods=['POST'])
def corpus_search():
    """Search the entire corpus for lines containing specific lemmas using inverted index"""
    try:
        from backend.inverted_index import is_index_available, find_co_occurring_lemmas, has_lines_data, get_lines_batch
        
        data = request.get_json() or {}
        lemmas = data.get('lemmas', [])
        language = data.get('language', 'la')
        exclude_texts = data.get('exclude_texts', [])
        sort_by = data.get('sort_by', 'chronological')

        # Exclude the WHOLE work family of each excluded text, not just the exact
        # filename: the corpus carries a combined file AND per-book parts of the
        # same work (e.g. milton.paradise_lost.tess + .part.1.tess), so excluding
        # the compared text must also drop its duplicate variants, or a phrase
        # unique to the two compared texts leaks back through a part file.
        def _work_base(fn):
            return re.sub(r'\.part\.\d+.*$', '', re.sub(r'\.tess$', '', fn or ''))
        _excluded_bases = {_work_base(f) for f in exclude_texts}
        
        if not lemmas or len(lemmas) < 1:
            return jsonify({'error': 'At least 1 lemma required'}), 400
        
        lang_dates = AUTHOR_DATES.get(language, {})
        
        if not is_index_available(language):
            return jsonify({'error': 'Index not available for this language'}), 400

        # Normalize lemmas for index lookup (strip Greek diacritics, Latin u/v)
        normalized_lemmas = [_normalize_lemma(l, language) for l in lemmas]
        # Drop function words so corpus co-occurrence is driven by content words,
        # not grammatical particles. Critical for Coptic, whose lemmatizer emits
        # article/tense-marker morphemes (ⲡ "the", ⲁ past-marker, ...) that
        # co-occur in nearly every clause and otherwise flood the results.
        from backend.fusion import _STOPLISTS as _FUSION_STOPLISTS
        _stop = _FUSION_STOPLISTS.get(language, set())
        normalized_lemmas = [l for l in normalized_lemmas if l and l.lower() not in _stop]
        if not normalized_lemmas:
            return jsonify({'results': [], 'total': 0, 'lemmas': lemmas})
        matches = find_co_occurring_lemmas(normalized_lemmas, language, min_matches=min(2, len(normalized_lemmas)))
        
        results = []
        text_matches = {}
        text_genre_cache = {}
        
        for filename, ref, matching_lemmas, positions in matches:
            if _work_base(filename) in _excluded_bases:
                continue
            if filename not in text_genre_cache:
                text_genre_cache[filename] = not is_prose_text_unified(filename, language)

            is_poetry = text_genre_cache[filename]
            max_distance = POETRY_MAX_DISTANCE if is_poetry else PROSE_MAX_DISTANCE
            
            all_positions = []
            for lemma in matching_lemmas:
                if lemma in positions:
                    all_positions.extend(positions[lemma])
            if len(all_positions) >= 2:
                all_positions.sort()
                span = all_positions[-1] - all_positions[0]
                if span > max_distance:
                    continue
            
            if filename not in text_matches:
                text_matches[filename] = []
            text_matches[filename].append((ref, matching_lemmas, positions))
        
        for filename, refs_data in text_matches.items():
            filepath = resolve_text_path(TEXTS_DIR, language, filename)
            if not filepath:
                continue
            if not fspaths.exists(filepath):
                continue
            metadata = get_text_metadata(filepath)
            # Computed once per text, not once per row: a result page can
            # hold a couple thousand rows sharing the same handful of texts.
            display_name = metadata.get('display_name') or metadata.get('author') or filename
            author_key = filename.split('.')[0].lower()
            author_info = lang_dates.get(author_key, {})
            author_year = author_info.get('year')
            author_era = author_info.get('era', 'Unknown')
            author_note = author_info.get('note', '')
            is_poetry = text_genre_cache.get(filename, False)
            
            refs = [r[0] for r in refs_data]
            
            if has_lines_data(language):
                lines_data = get_lines_batch(filename, refs, language)
            else:
                lines_data = {}
                try:
                    with fspaths.open_text(filepath, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.startswith('<'):
                                end_tag = line.find('>')
                                if end_tag > 0:
                                    line_ref = line[1:end_tag]
                                    if line_ref in refs:
                                        line_text = line[end_tag+1:].strip()
                                        lines_data[line_ref] = {'text': line_text, 'tokens': [], 'lemmas': []}
                except Exception:
                    app_logger.exception(f"Error loading text snippet for {filename}")
            
            for ref, matching_lemmas, positions in refs_data:
                line_info = lines_data.get(ref, {})
                text = line_info.get('text', '')
                if not text:
                    continue
                tokens = line_info.get('tokens', [])
                token_lemmas = line_info.get('lemmas', [])
                
                matched_indices = []
                lemma_set = set(lemmas)
                for i, lemma in enumerate(token_lemmas):
                    if lemma in lemma_set:
                        matched_indices.append(i)

                # Clean locus + full citation, the same way Line Search builds
                # them (same formula as backend.utils.build_citation, inlined
                # here with the per-text display_name computed once above
                # rather than once per row). `locus` used to be the raw .tess
                # tag, which is what made the browser's tag-parsing fallback
                # necessary in the first place (issue #566); the server now
                # does the job here instead.
                clean_locus = format_short_locus(ref)
                citation = f"{display_name} {clean_locus}".strip() if clean_locus else display_name

                results.append({
                    'text_id': filename,
                    'author': metadata['author'],
                    'title': metadata['title'],
                    'locus': clean_locus,
                    'citation': citation,
                    'text': text,
                    'matched_lemmas': list(matching_lemmas),
                    'highlight_indices': matched_indices,
                    'tokens': tokens,
                    'year': author_year,
                    'era': author_era,
                    'date_note': author_note,
                    'is_poetry': is_poetry
                })
        
        if sort_by == 'chronological':
            results.sort(key=lambda x: (x['year'] if x['year'] is not None else 9999, x['author'], x['title'], x['locus']))
        else:
            results.sort(key=lambda x: (x['author'], x['title'], x['locus']))
        
        return jsonify({
            'results': results[:500],
            'total': len(results),
            'lemmas': lemmas
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
