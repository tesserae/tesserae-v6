"""Documents collection (inscriptions and papyri): routes and search helpers.

Moved out of backend/app.py unchanged (application-factory job, 2026-10-12).
"""
import json
import re
import itertools

from flask import Blueprint, jsonify, request

from backend.utils import exact_phrase_pattern, exact_search_text
from backend.distance_filter import passes_distance_filter
from backend.runtime import (
    text_processor, api_route_for,
)
from backend.line_search_support import _normalize_lemma

documents_bp = Blueprint('documents', __name__)
api_route = api_route_for(documents_bp)



# =============================================================================
# DOCUMENTS COLLECTION (stage 3b-2/3b-3, behind TESSERAE_DOCUMENTS=1)
# =============================================================================
# Lets /api/line-search search the documentary corpus (inscriptions, papyri;
# PR #678) alongside or instead of literature. See backend/documents.py for
# the index/metadata/sidecar access this reuses. Everything below is reached
# only when `collection` is 'documents' or 'both' AND backend.documents.enabled()
# -- with the switch off, or collection omitted, line_search()'s literary
# path above is completely untouched by any of this.
#
# Stage 3b-3 added restoration marking/exclusion, a stock-formula count and
# filter, and the GET /api/documents/<doc_id> Reader route (further down).

import unicodedata as _documents_ud

# Default threshold for `hide_formulas` (spec item 5): drop a document hit
# whose matched lemmas/phrase co-occur in MORE than this many documents in
# the same index. Measured directly against the real dev documents indexes
# (2026-10-08, la_documents_index.db/grc_documents_index.db), counting
# DISTINCT documents sharing the matched lemma set via
# backend.documents.find_co_occurring_lemmas + doc_for (the same postings
# lookup _documents_formula_count uses):
#   dis manibus                   35,231 documents  (a true formula)
#   bene merenti                  11,903 documents  (a true formula)
#   votum solvit libens merito     3,990 documents  (a true formula)
#   hic situs est                  3,535 documents  (a true formula)
#   arma virumque                     19 documents  (a genuine parallel)
#   arma virumque cano                 8 documents  (a genuine parallel)
# The gap between the smallest formula (3,535) and the largest genuine
# parallel (19) spans three orders of magnitude, so 100 cleanly separates
# them with wide margin on both sides.
DOCUMENTS_FORMULA_DEFAULT_N = 100

# Fewest candidate hits for which `hide_formulas` drops formula hits before
# looking up their metadata, restored words and ranking keys. Measured on
# the Latin documents index (median of three warm runs, 2026-10-19): the
# early drop saves about 15 microseconds per hidden hit (dis manibus,
# 35,607 hits: 1.57 s down to 1.02 s; bene merenti, 12,010: 0.43 s down to
# 0.23 s) and costs a dictionary lookup per hit. Below 2,000 candidates the
# saving (under 30 ms) is inside the run-to-run noise of one request, so
# those queries keep the single code path. Results and the hidden count are
# identical on both paths (checked on 14 queries).
_FORMULA_PREHIDE_MIN = 2000

# A plain `None` default for `_document_hit`'s `meta_override` would be
# indistinguishable from "looked this id up and it is genuinely
# uncredited" (a real, meaningful value); this sentinel means "the caller
# passed nothing, look it up yourself".
_UNSET = object()


# Stage 4 (the owner's review of the live documents trial, 2026-10-08):
# document results no longer come back in storage order. 'relevance'
# (default) ranks an exact adjacent phrase ahead of one whose matched words
# are scattered across the line, a match resting on surviving text ahead of
# one resting on editorially restored text, then fewer restorations
# elsewhere on the same line, then earliest date. 'oldest'/'newest' sort on
# date alone; 'region' alphabetically. See _document_sort_key.
_DOCUMENT_SORT_MODES = ('relevance', 'oldest', 'newest', 'region')


def _min_adjacent_span_rank(positions_dict, lemmas):
    """0 when the matched lemmas' best-case token positions on this line
    form one unbroken run (an "exact adjacent phrase" per the stage 4
    ranking spec), 1 when they are scattered, or when position data is not
    available for one of them. `positions_dict` is find_co_occurring_
    lemmas' own per-lemma position list for this line (backend.
    inverted_index's `data['positions']`) -- this never fetches or
    re-splits the line's text; a documentary phrase query is short (2-4
    words), and each lemma's own occurrence list on one short epigraphic or
    papyrus line is almost always length 1, so brute-forcing every
    combination of "which occurrence of each lemma" is a handful of
    tuples, never a performance concern even run across tens of thousands
    of candidates."""
    lists = [sorted(set(positions_dict.get(l) or [])) for l in lemmas]
    if not lists:
        return 1
    if len(lists) == 1:
        return 0 if lists[0] else 1
    if any(not lst for lst in lists):
        return 1
    best_span = None
    for combo in itertools.product(*lists):
        span = max(combo) - min(combo)
        if best_span is None or span < best_span:
            best_span = span
    return 0 if best_span == len(lists) - 1 else 1


def _restored_rank_and_extra(all_positions, restored_set):
    """(restored_rank, extra_restorations) for the 'relevance' sort.
    restored_rank: 0 every matched position is on surviving text, 1 some
    are restored, 2 every matched position is restored (mirrors
    _restoration_flags' own matched_restored/partly_restored, as a single
    ordered rank rather than two booleans). extra_restorations: how many
    OTHER token positions on the same line are restored but are not part
    of this match -- the spec's "fewer extra restorations" tiebreak,
    ascending. Both computed from token positions alone (never text)."""
    if not all_positions:
        return 0, len(restored_set)
    restored_matched = sum(1 for p in all_positions if p in restored_set)
    total = len(all_positions)
    if restored_matched == 0:
        rank = 0
    elif restored_matched == total:
        rank = 2
    else:
        rank = 1
    return rank, max(0, len(restored_set) - restored_matched)


def _date_sort_value(m):
    """A document hit's own best single year for sorting/century-bucketing:
    date_not_before, falling back to date_not_after, None when metadata.db
    has neither (an uncredited or undated hit) -- sorted last by
    _document_sort_key, never guessed at as "year zero"."""
    if not m:
        return None
    v = m.get('date_not_before')
    if v is None:
        v = m.get('date_not_after')
    return v


_formula_lemma_cache = {}


def _formula_lemmas(language):
    """The lemmas of the language's stock-formula words
    (backend.documents.formula_words), so a hit's matched LEMMAS can be
    tested against a list that was written in surface forms ("manibus",
    "dis"). Each word contributes every lemma the lemmatizer offers for it.
    Cached per process, rebuilt when the word list is reloaded."""
    import backend.documents as docs
    words = docs.formula_words(language)
    cached = _formula_lemma_cache.get(language)
    if cached is not None and cached[0] is words:
        return cached[1]
    lemmas = set()
    if words:
        from backend.runtime import text_processor
        for w in words:
            for lem in text_processor.lemmatize_word(w, language):
                lemmas.add(_normalize_lemma(lem, language))
    lemmas = frozenset(lemmas)
    _formula_lemma_cache[language] = (words, lemmas)
    return lemmas


def _is_formula_only(matched_lemmas, formula_lemmas):
    """True when every lemma a hit matched on belongs to the stock-formula
    list: the match rests on "dis manibus", "vixit annis" and the like and
    carries nothing distinctive. False for an empty set (no information)."""
    return bool(matched_lemmas) and set(matched_lemmas) <= formula_lemmas


def _document_sort_key(sort, rank):
    """The tuple to sort a document hit's own `rank` dict (built in
    _search_documents_collection: adjacency/restored_rank/
    extra_restorations/date/region/doc_id) ascending on, for `sort` (one of
    _DOCUMENT_SORT_MODES; an unrecognized value is treated as
    'relevance')."""
    date = rank.get('date')
    date_known = date is not None
    if sort == 'oldest':
        return (date_known is False, date if date_known else 0, rank['doc_id'])
    if sort == 'newest':
        return (date_known is False, -date if date_known else 0, rank['doc_id'])
    if sort == 'region':
        region = (rank.get('region') or '').lower()
        return (region == '', region, rank['doc_id'])
    # A hit whose matched words are all stock-formula words (the lists in
    # data/documents/formula_words_*.txt) goes behind every hit that matched
    # something distinctive. It is a soft penalty: the hit stays in the
    # results, ordered among its own kind by the same keys as before.
    return (bool(rank.get('formula_only')), rank['adjacency'], rank['restored_rank'],
            rank['extra_restorations'], date_known is False, date if date_known else 0,
            rank['doc_id'])


def _century_label(year):
    """A document's own date_not_before/after (see _date_sort_value) as a
    century bucket for the distribution chart: classicists' convention, no
    year 0 (year 1 AD is the 1st century AD; year -1, i.e. 1 BC, is the 1st
    century BC). 'Unknown' for an undated hit -- shown as its own bar
    rather than silently dropped."""
    if year is None:
        return 'Unknown'
    if year == 0:
        # No year 0 in this convention (never a real EDH/EDCS/Trismegistos
        # date); a stray 0 is folded into 1st c. AD rather than producing
        # a nonsensical "0th century".
        n, era = 1, 'AD'
    elif year >= 1:
        n, era = (year - 1) // 100 + 1, 'AD'
    else:
        n, era = (-year - 1) // 100 + 1, 'BC'
    if n % 100 in (11, 12, 13):
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix} c. {era}'


def _century_sort_key(label):
    """Chronological order for _century_label's own output: BC centuries
    descending (furthest past first), then AD ascending, 'Unknown' last."""
    if label == 'Unknown':
        return (1, 0)
    n = int(''.join(ch for ch in label.split(' ', 1)[0] if ch.isdigit()))
    era = label.rsplit(' ', 1)[-1]
    return (0, -n if era == 'BC' else n + 10000)


def _tally_source_region(kept):
    """[{source, region, count}] sorted by count descending, over every
    kept candidate's own metadata (not just the page) -- the documents
    analogue of _count_candidates_by_work's by_work_all. `kept` is a list
    of the per-candidate dicts _search_documents_collection builds, each
    carrying a 'meta' key (a backend.documents.meta()-shaped dict, or
    None). `region` is translated (backend.documents.translate_label) the
    same way a result row's own 'region' field is, so a chart or table
    built from this never prints a raw German value either."""
    import backend.documents as docs
    tally = {}
    for k in kept:
        m = k.get('meta') or {}
        region = docs.translate_label(m.get('region')) or 'unknown'
        key = (m.get('source') or 'unknown', region)
        tally[key] = tally.get(key, 0) + 1
    out = [{'source': k[0], 'region': k[1], 'count': v} for k, v in tally.items()]
    out.sort(key=lambda x: -x['count'])
    return out


def _tally_century(kept):
    """[{century, count}] in chronological order, over every kept
    candidate (not just the page) -- the distribution-by-century chart the
    stage 4 spec asks for, computed once per request from metadata already
    fetched for ranking (see _search_documents_collection), not a second
    pass over the index."""
    tally = {}
    for k in kept:
        m = k.get('meta') or {}
        label = _century_label(_date_sort_value(m))
        tally[label] = tally.get(label, 0) + 1
    out = [{'century': label, 'count': v} for label, v in tally.items()]
    out.sort(key=lambda x: _century_sort_key(x['century']))
    return out


def _restoration_flags(matched_positions, restored_set):
    """(matched_restored, partly_restored) for one document hit: whether
    EVERY matched token position is one write_document_tess.py's own
    sidecar marked restored, or only SOME are. Both False when
    `matched_positions` is empty/None (no position information for this
    hit -- never a reason to claim restoration either way) or when none
    of the matched positions are restored."""
    if not matched_positions:
        return False, False
    restored_matched = sum(1 for p in matched_positions if p in restored_set)
    total = len(matched_positions)
    return restored_matched == total, 0 < restored_matched < total


def _normalize_token_for_phrase_match(tok):
    """NFC + lowercase + strip leading/trailing punctuation, so a token
    list built at index time (write_document_tess.py) can be compared
    against an exact-search query's own words without the two text layers
    (editorial brackets, stray punctuation) causing a false miss."""
    tok = _documents_ud.normalize('NFC', tok or '').lower()
    return re.sub(r'^\W+|\W+$', '', tok)


def _find_exact_phrase_positions(tokens, query):
    """Token-index span of an *exact*-search query inside one document
    line's own `tokens` list, best-effort: the first contiguous run whose
    normalized form matches the query word-for-word, with
    exact_phrase_pattern's own asymmetric rule carried over (no trailing
    boundary on the LAST word, so "virum" still matches a line's
    "virumque" -- see backend/utils.py). Returns [] when the query has no
    words, `tokens` is empty, or no such run is found (an exact hit whose
    positions this cannot pin down -- a scan-based SLOW PATH match, not an
    index-driven one, see _search_documents_collection -- simply carries
    no restoration marking, rather than guessing)."""
    words = [_normalize_token_for_phrase_match(w) for w in (query or '').split()]
    if not words or not tokens:
        return []
    norm_tokens = [_normalize_token_for_phrase_match(t) for t in tokens]
    n = len(words)
    for i in range(len(norm_tokens) - n + 1):
        ok = True
        for j in range(n):
            if j == n - 1:
                if not norm_tokens[i + j].startswith(words[j]):
                    ok = False
                    break
            elif norm_tokens[i + j] != words[j]:
                ok = False
                break
        if ok:
            return list(range(i, i + n))
    return []


def _documents_formula_count(language, matched_lemmas, cache):
    """How many documents in this SAME documents index (for `language`)
    share every one of `matched_lemmas` -- the in-N-documents count stage
    3b-3 asks for, computed from postings the same way line search counts
    co-occurrence candidates (backend.documents.find_co_occurring_lemmas,
    which wraps backend.inverted_index's own index-driven lookup), never
    a corpus scan. `cache` is a plain dict the CALLER owns for the life of
    one request (keyed on frozenset(matched_lemmas)): a 2-3 word
    documentary query typically produces the same matched-lemma set
    across most of its hits, so this is usually computed once per query,
    not once per hit, satisfying the "cached per query" requirement
    without a module-level cache that could go stale across requests or
    leak between languages/queries.

    Returns None (never 0-as-a-guess) for an empty lemma set -- a hit
    whose matched_lemmas is empty (the exact/regex SLOW PATH never
    populates matched_lemmas -- see _search_documents_collection) has no
    well-defined "documents sharing this lemma pair" count, and formula
    hiding/display must treat that as unknown, not as "unique"."""
    if not matched_lemmas:
        return None
    key = frozenset(matched_lemmas)
    if key in cache:
        return cache[key]
    import backend.documents as docs
    candidates = docs.find_co_occurring_lemmas(list(key), language, min_matches=len(key))
    distinct_docs = set()
    for filename, ref, _matching_lemmas, _positions in candidates:
        d = docs.doc_for(language, filename, ref)
        if d:
            distinct_docs.add(d)
    count = len(distinct_docs)
    cache[key] = count
    return count


def _lemmatize_query_simple(query, language, text_processor):
    """Query lemmas for a documents-collection search. Documents are Latin
    or Greek only (backend.documents.SUPPORTED_LANGUAGES), so this is the
    plain lemmatizer path line_search()'s own literary branch uses for every
    language except Persian/Urdu/Arabic/Hebrew -- those branches never apply
    here and are not reproduced."""
    query_lemmas = set()
    for token in query.lower().split():
        lemmas = text_processor.lemmatize_word(token, language)
        query_lemmas.update(_normalize_lemma(l, language) for l in lemmas)
    if not query_lemmas:
        query_lemmas = set(_normalize_lemma(t, language) for t in query.lower().split())
    return query_lemmas


def _document_passes_filters(m, date_from, date_to, region, text_type, material, source, kind=None,
                              place=None):
    """True if a document hit's metadata (backend.documents.meta's return,
    or None) satisfies every filter the caller actually set. A filter the
    request left unset is skipped. When NO filter is active this always
    returns True, even with m=None (an uncredited hit is still shown). When
    at least one filter IS active and m is None, the hit cannot be
    confirmed and is excluded -- safer than showing an unfiltered row inside
    a filtered search."""
    if not any([date_from is not None, date_to is not None, region, text_type, material, source, kind,
                place]):
        return True
    if m is None:
        return False
    if kind:
        # 'inscriptions' or 'papyri': the same split the browse tree uses.
        from backend.documents_browse import _kind_for_source
        if _kind_for_source(m.get('source')) != kind:
            return False
    if date_from is not None:
        if m.get('date_not_after') is None or m['date_not_after'] < date_from:
            return False
    if date_to is not None:
        if m.get('date_not_before') is None or m['date_not_before'] > date_to:
            return False
    if region:
        # The Region drop-down offers the browse tree's normalized labels
        # (backend.documents_browse.normalize_region: spelling variants of a
        # region merged, a papyrus's nome taken from its ancient place, I.Sicily
        # all "Sicilia"), which differ from the raw `region` column. A
        # document passes when the raw column contains the text (what free
        # typing always did) or its normalized label equals it.
        if not (m.get('region') and region.lower() in m['region'].lower()):
            from backend.documents_browse import _kind_for_source, normalize_region
            _k = _kind_for_source(m.get('source'))
            label = normalize_region(_k, m.get('source'), m.get('region'), m.get('ancient_place'))[0] if _k else None
            if not label or label.lower() != region.lower():
                return False
    if place:
        from backend.documents import place_matches
        if not place_matches(place, m.get('ancient_place'), m.get('modern_place')):
            return False
    if text_type:
        if not m.get('text_type_label') or text_type.lower() not in m['text_type_label'].lower():
            return False
    if material:
        if not m.get('material_label') or material.lower() not in m['material_label'].lower():
            return False
    if source:
        cred = m.get('credit') or {}
        haystack = ' '.join(str(v) for v in (
            m.get('source'), m.get('collection'),
            cred.get('source_name'), cred.get('source_name_secondary'),
        ) if v).lower()
        if source.lower() not in haystack:
            return False
    return True


def _document_hit(language, filename, ref, matched_words, matched_lemmas, tokens=None,
                   matched_positions=None, formula_count=None, meta_override=_UNSET):
    """One documents-collection result row: credit, date, place, labels and
    restored-word positions from backend.documents, instead of the literary
    author/work/era/year shape. `tokens` (the line's own tokenized form, same
    one restored_indices' positions were computed against at write time) is
    passed through so the client can mark restored words by POSITION rather
    than re-splitting `text` on whitespace, which would drift out of step
    with restored_indices the moment punctuation or an elided editorial mark
    changes the split. Returns (row, meta_or_None) -- meta is handed back so
    the caller does not look metadata up twice for the filter check.

    `matched_positions` (stage 3b-3): the matched tokens' own index
    positions, when the caller could determine them (always true for the
    lemma FAST PATH; best-effort via _find_exact_phrase_positions for
    'exact'; never for 'regex' -- see _search_documents_collection), used
    only to set matched_restored/partly_restored against the sidecar's
    restored-token positions. `formula_count` (stage 3b-3): how many
    documents in this index share the matched lemma pair/phrase -- see
    _documents_formula_count; None when not computed (regex, or an exact
    hit whose matched_lemmas came back empty).

    `meta_override` (stage 4): the caller's own already-fetched metadata
    dict (or None, meaning "looked up and genuinely uncredited"), when it
    has one -- _search_documents_collection's lemma FAST PATH bulk-fetches
    metadata for every candidate up front (backend.documents.bulk_meta) so
    ranking thousands of matches never pays for one metadata.db round trip
    per row; passing the already-known value here avoids looking it up a
    second time. Left at its default (the `_UNSET` sentinel, not None --
    None is itself a valid, meaningful override) this calls
    backend.documents.meta(doc_id) itself, exactly as before stage 4.

    Place/region/material/object/text-type labels are passed through
    backend.documents.translate_label (a handful of EDH/EDCS/Trismegistos
    values are German) before going in the row; ancient_place/modern_place
    are set to None instead when backend.documents.is_unknown_place
    recognizes the raw value as a "place not known" placeholder (German
    'unbekannt', English 'unknown', Latin 'ignoratur') -- stage 4: hidden
    rather than shown translated as the word "unknown", which is no
    information for a reader. The metadata.db value itself is never
    modified by any of this."""
    import backend.documents as docs
    doc_id = docs.doc_for(language, filename, ref)
    if meta_override is not _UNSET:
        m = meta_override
    else:
        m = docs.meta(doc_id) if doc_id else None
    restored = docs.restored_indices(language, filename, ref)
    matched_restored, partly_restored = _restoration_flags(
        matched_positions, set(restored.get('restored') or []))

    def _place(value):
        return None if docs.is_unknown_place(value) else docs.translate_label(value)

    row = {
        'collection': 'documents',
        'doc_id': doc_id,
        'locus': ref,
        'text_id': filename,
        'language': language,
        'text': None,  # filled by the caller, which already has the line text
        'tokens': tokens or [],
        'matched_words': matched_words,
        'matched_lemmas': sorted(matched_lemmas) if matched_lemmas else [],
        'credit': (m or {}).get('credit'),
        'date_not_before': (m or {}).get('date_not_before'),
        'date_not_after': (m or {}).get('date_not_after'),
        'ancient_place': _place((m or {}).get('ancient_place')),
        'modern_place': _place((m or {}).get('modern_place')),
        'region': docs.translate_label((m or {}).get('region')),
        'pleiades_id': (m or {}).get('pleiades_id'),
        'text_type_label': docs.translate_label((m or {}).get('text_type_label')),
        'object_type_label': docs.translate_label((m or {}).get('object_type_label')),
        'material_label': docs.translate_label((m or {}).get('material_label')),
        'source': (m or {}).get('source'),
        'restored_indices': restored.get('restored'),
        'fragment_indices': restored.get('fragment'),
        'gap_before': docs.gap_positions(language, filename, ref),
        'matched_restored': matched_restored,
        'partly_restored': partly_restored,
        'formula_count': formula_count,
    }
    return row, m


def _lemma_candidates(language, filtered_query_lemmas, min_matched):
    """One index lookup for a lemma query, returned as (matches, everyone):
    `matches` is what _lemma_fast_path_matches always returned (the
    distance rule applied), `everyone` is the same lookup's list of
    (filename, ref, matched_lemmas) BEFORE the distance rule, which is
    exactly the population the formula count draws on (see
    _DocumentFormulaCounter)."""
    import backend.documents as docs
    from backend.distance_filter import get_max_distance
    out = []
    everyone = []
    if not filtered_query_lemmas:
        return out, everyone
    candidates = docs.find_co_occurring_lemmas(list(filtered_query_lemmas), language,
                                                 min_matches=min_matched)
    # The distance limit depends only on the bucket file, and a query's
    # candidates fall in a few hundred files at most: ask once per file.
    max_distance_by_file = {}
    for filename, ref, matching_lemmas, positions in candidates:
        matched_lemmas = set(matching_lemmas) & filtered_query_lemmas
        if len(matched_lemmas) < min_matched:
            continue
        everyone.append((filename, ref, matched_lemmas))
        lists = [positions.get(l) or [] for l in matched_lemmas]
        min_dist = 0
        if len(lists) >= 2:
            dists = [abs(pa - pb) for i in range(len(lists)) for j in range(i + 1, len(lists))
                     for pa in lists[i] for pb in lists[j]]
            if dists:
                min_dist = min(dists)
        if min_dist > 0:
            limit = max_distance_by_file.get(filename)
            if limit is None:
                limit = max_distance_by_file[filename] = get_max_distance(filename, language)
            if min_dist > limit:
                continue
        out.append({'filename': filename, 'ref': ref, 'matched_lemmas': matched_lemmas,
                    'positions': positions})
    return out, everyone


def _lemma_fast_path_matches(language, filtered_query_lemmas, min_matched):
    """Every (filename, ref, matched_lemmas, positions) the documents index
    has for `filtered_query_lemmas`, with the distance rule already applied
    -- the FULL, uncapped candidate set (stage 4: no 500-row ceiling).
    Cheap: nothing here touches metadata.db, a restored-word sidecar or a
    line's own text; the distance check reuses the index's own per-lemma
    position lists (the same ones find_co_occurring_lemmas returns),
    exactly the way _min_adjacent_span_rank reuses them for ranking,
    instead of re-fetching and re-splitting the line's text the way
    backend.distance_filter.calculate_match_distance does for the literary
    search path."""
    return _lemma_candidates(language, filtered_query_lemmas, min_matched)[0]


class _DocumentFormulaCounter:
    """The in-N-documents count for a set of matched lemmas, answered from
    the candidates the query's own index lookup already returned instead of
    one more index lookup per distinct lemma set (about 20 ms each, and 225
    of them for one sentence: 4.4 of 5.0 seconds).

    A document shares every lemma of S exactly when its candidate row
    (the rows with at least min_matched of the query's lemmas) holds S as a
    subset, so long as S itself has at least min_matched lemmas, which a
    hit's matched set always has. count() equals _documents_formula_count
    for those sets; any other set falls back to that function's lookup."""

    def __init__(self, language, everyone, doc_ids, min_matched, cache):
        self.language = language
        self.min_matched = min_matched
        self.cache = cache
        groups = {}
        for filename, ref, matched in everyone:
            d = doc_ids.get((filename, ref))
            if d:
                groups.setdefault(frozenset(matched), set()).add(d)
        self.groups = groups

    def count(self, matched_lemmas):
        if not matched_lemmas:
            return None
        key = frozenset(matched_lemmas)
        if key in self.cache:
            return self.cache[key]
        if len(key) < self.min_matched:
            return _documents_formula_count(self.language, matched_lemmas, self.cache)
        docs_with_all = set()
        for group_key, group_docs in self.groups.items():
            if key <= group_key:
                docs_with_all |= group_docs
        self.cache[key] = len(docs_with_all)
        return self.cache[key]


def _search_documents_collection(language, search_type, query, filtered_query_lemmas,
                                  min_matched, offset, limit, date_from, date_to,
                                  region, text_type, material, source,
                                  exclude_restored=False, hide_formulas=None,
                                  sort='relevance', kind=None, place=None):
    """Document hits for the documents/both collection. Mirrors the FAST PATH
    of line_search()'s literary branch (same index-driven candidate lookup,
    same matched-word shape) against backend.documents's own documents-index
    connection, with document fields (credit/date/place/labels/restored
    positions) instead of author/work/era/year.

    Rarity note (spec item 3): a document hit's matched-lemma rarity belongs
    to the DOCUMENTS index's own lemma_doc_freq table, never the literary
    one. This function computes no score at all (same as the literary
    branch -- line_search results are filtered/deduped and sorted by era/
    year/author, never ranked by score) EXCEPT the stage 4 relevance rank
    added below, which is its own self-contained measure (adjacency/
    restoration/date, all read off this collection's own index and
    metadata.db) and never touches the literary lemma_doc_freq table either.

    Stage 3b-3, `exclude_restored`: drop a hit whose match rests ENTIRELY on
    restored tokens (restored_rank == 2, see _restored_rank_and_extra). A hit
    with no position information is never dropped by this (restored_rank is
    0 whenever there are no matched positions, by that function's own
    contract) -- "unknown" and "not restored" are deliberately the same safe
    outcome here.

    Stage 3b-3, `hide_formulas`: drop a hit whose `formula_count` (documents
    in this SAME index sharing its matched lemmas, see
    _documents_formula_count) exceeds this integer. A hit with
    formula_count None (regex; or exact, whose matched_lemmas is always
    empty -- see the SLOW PATH below) is never dropped: an unmeasured count
    is not evidence of a formula, and silently hiding regex/exact documents
    hits whenever this filter is on would be a much bigger behavior change
    than the spec asked for.

    Formula words (data/documents/formula_words_<language>.txt): they enter
    the 'relevance' sort as a soft penalty. A hit whose matched lemmas all
    belong to the lemmas of the list's words (_is_formula_only) sorts behind
    every hit that matched anything else (see _document_sort_key). The
    other sorts (oldest, newest, region) are unchanged.

    Speed of `hide_formulas`: the stock-formula count of a hit needs only
    the candidate lists, not the hit's metadata, restored words or ranking
    keys. When no other filter is active and exclude_restored is off, the
    hits to be hidden are therefore counted and dropped BEFORE those
    per-hit lookups run (measured, see _FORMULA_PREHIDE_MIN below), which
    gives the same results and the same formulas_hidden_count as before.

    Stage 4 (owner's review of the live trial, 2026-10-08): no 500-row
    ceiling. `offset`/`limit` page a SORTED, FULLY-FILTERED candidate list
    (`sort`, one of _DOCUMENT_SORT_MODES); the per-row cost of building a
    full result row (a line-text fetch, the restored-word sidecar, label
    translation) is paid only for the page actually requested, never for
    the whole candidate set -- see _lemma_fast_path_matches and
    backend.documents.bulk_meta's own docstrings for how ranking and
    filtering stay cheap at tens of thousands of candidates ("dis manibus"
    matches roughly 35,000 of them; measured end-to-end warm latency is in
    docs/DECISIONS.md).

    Returns (page_results, total, by_source_region, by_century, stats).
    `total` is the exact count of matches after EVERY filter (date/region/
    text_type/material/source/exclude_restored/hide_formulas); `by_
    source_region`/`by_century` ([{source,region,count}]/[{century,count}],
    the documents analogue of _count_candidates_by_work's by_work_all) are
    computed over that SAME total, not just the returned page.
    `page_results` is exactly `limit` rows (fewer on the last page) starting
    at `offset`. stats is {'restored_excluded_count',
    'formulas_hidden_count', 'formula_summary'} (formula_summary is None
    for a non-lemma search or an empty lemma set).
    """
    import backend.documents as docs
    stats = {'restored_excluded_count': 0, 'formulas_hidden_count': 0, 'formula_summary': None}
    if language not in docs.SUPPORTED_LANGUAGES or not docs.is_index_available(language):
        return [], 0, [], [], stats
    if search_type not in ('lemma', 'exact', 'regex'):
        search_type = 'lemma'
    if sort not in _DOCUMENT_SORT_MODES:
        sort = 'relevance'

    formula_cache = {}

    if search_type == 'lemma':
        if not filtered_query_lemmas:
            return [], 0, [], [], stats
        raw_candidates, everyone = _lemma_candidates(language, filtered_query_lemmas, min_matched)
        doc_ids = {}
        for filename, ref, _matched in everyone:
            doc_ids[(filename, ref)] = docs.doc_for(language, filename, ref)
        for c in raw_candidates:
            c['doc_id'] = doc_ids[(c['filename'], c['ref'])]
        formula_counter = _DocumentFormulaCounter(language, everyone, doc_ids, min_matched,
                                                  formula_cache)
        # The stock-formula count for the WHOLE query's lemma set is
        # exactly the distinct-document count this pass already computed,
        # whenever min_matched asked for every one of filtered_query_
        # lemmas (true for the common 2-word documentary phrase) --
        # seeding the cache here saves a second find_co_occurring_lemmas
        # pass purely to recompute the same number.
        if min_matched == len(filtered_query_lemmas):
            stats_doc_ids = {c['doc_id'] for c in raw_candidates if c['doc_id']}
            formula_cache[frozenset(filtered_query_lemmas)] = len(stats_doc_ids)

        # Early drop for hide_formulas (see the docstring): with no filter
        # and no restored-word exclusion, a hit's fate depends on its
        # formula count alone, so the hits to hide are counted and removed
        # before bulk_meta, the sidecar and the ranking keys run for them.
        no_filters = not any([date_from is not None, date_to is not None, region, text_type,
                              material, source, kind, place])
        counts_by_candidate = {}
        if (hide_formulas is not None and no_filters and not exclude_restored
                and len(raw_candidates) >= _FORMULA_PREHIDE_MIN):
            survivors = []
            for c in raw_candidates:
                fc = formula_counter.count(c['matched_lemmas'])
                if fc is not None and fc > hide_formulas:
                    stats['formulas_hidden_count'] += 1
                else:
                    counts_by_candidate[id(c)] = fc
                    survivors.append(c)
            raw_candidates = survivors
        meta_by_id = docs.bulk_meta([c['doc_id'] for c in raw_candidates if c['doc_id']])
        formula_lemmas = _formula_lemmas(language)

        kept = []
        for c in raw_candidates:
            m = meta_by_id.get(c['doc_id'])
            if not _document_passes_filters(m, date_from, date_to, region, text_type,
                                             material, source, kind, place):
                continue
            all_positions = sorted({p for l in c['matched_lemmas']
                                     for p in (c['positions'].get(l) or [])})
            restored = docs.restored_indices(language, c['filename'], c['ref'])
            restored_set = set(restored.get('restored') or [])
            restored_rank, extra_restorations = _restored_rank_and_extra(all_positions, restored_set)
            if exclude_restored and restored_rank == 2:
                stats['restored_excluded_count'] += 1
                continue
            if id(c) in counts_by_candidate:
                formula_count = counts_by_candidate[id(c)]
            else:
                formula_count = formula_counter.count(c['matched_lemmas'])
                if hide_formulas is not None and formula_count is not None and formula_count > hide_formulas:
                    stats['formulas_hidden_count'] += 1
                    continue
            adjacency = _min_adjacent_span_rank(c['positions'], c['matched_lemmas'])
            kept.append({
                'filename': c['filename'], 'ref': c['ref'], 'doc_id': c['doc_id'],
                'matched_lemmas': c['matched_lemmas'], 'all_positions': all_positions,
                'meta': m, 'formula_count': formula_count,
                'rank': {
                    'adjacency': adjacency, 'restored_rank': restored_rank,
                    'extra_restorations': extra_restorations,
                    'formula_only': _is_formula_only(c['matched_lemmas'], formula_lemmas),
                    'date': _date_sort_value(m), 'region': (m or {}).get('region'),
                    'doc_id': c['doc_id'] or '',
                },
            })

        total = len(kept)
        by_source_region = _tally_source_region(kept)
        by_century = _tally_century(kept)
        kept.sort(key=lambda k: _document_sort_key(sort, k['rank']))
        page = kept[offset:offset + limit]

        # Only the page's own rows pay for a line-text fetch, grouped by
        # filename exactly as the pre-stage-4 code did for every
        # candidate -- one batched get_lines_batch call per filename
        # touched by this page (almost always far fewer than `limit`
        # files), never one call per candidate.
        by_filename = {}
        for p in page:
            by_filename.setdefault(p['filename'], []).append(p['ref'])
        lines_by_filename = {filename: (docs.get_lines_batch(filename, refs, language) or {})
                              for filename, refs in by_filename.items()}

        page_results = []
        for p in page:
            line_info = lines_by_filename.get(p['filename'], {}).get(p['ref']) or {}
            text = line_info.get('text', '')
            tokens = line_info.get('tokens') or []
            matched_positions = sorted(pos for pos in p['all_positions'] if pos < len(tokens))
            matched_words = [tokens[i] for i in matched_positions]
            row, _m = _document_hit(language, p['filename'], p['ref'], matched_words,
                                     p['matched_lemmas'], tokens=tokens,
                                     matched_positions=matched_positions,
                                     formula_count=p['formula_count'], meta_override=p['meta'])
            row['text'] = text
            page_results.append(row)

        if filtered_query_lemmas:
            stats['formula_summary'] = {
                'query_lemmas': sorted(filtered_query_lemmas),
                'documents_sharing_all': formula_counter.count(filtered_query_lemmas),
            }
        return page_results, total, by_source_region, by_century, stats

    # exact/regex: no index path exists for these (same as the literary
    # SLOW PATH), so scan every line of every bucket file for `language`
    # through the documents index's own `lines` table -- reusing the SAME
    # connection the lemma path above uses. This already had no cheaper
    # path before stage 4; the only change here is removing the fixed
    # 500-row ceiling and running the full result set through the same
    # sort/paginate/distribution pass the lemma path above uses.
    conn = docs.get_connection(language)
    if conn is None:
        return [], 0, [], [], stats
    exact_pattern = exact_phrase_pattern(query, language) if search_type == 'exact' else None
    try:
        text_rows = conn.execute('SELECT text_id, filename FROM texts').fetchall()
    except Exception:                                               # noqa: BLE001
        return [], 0, [], [], stats

    seen = set()
    kept = []
    for trow in text_rows:
        filename = trow['filename']
        try:
            line_rows = conn.execute(
                'SELECT ref, content, tokens FROM lines WHERE text_id = ?', (trow['text_id'],)
            ).fetchall()
        except Exception:                                           # noqa: BLE001
            continue
        for lrow in line_rows:
            ref, text = lrow['ref'], (lrow['content'] or '')
            if (filename, ref) in seen:
                continue
            match_found = False
            if search_type == 'exact':
                if exact_pattern and exact_pattern.search(exact_search_text(text)):
                    match_found = True
            else:
                try:
                    if re.search(query, text, re.IGNORECASE):
                        match_found = True
                except re.error:
                    pass
            if not match_found:
                continue
            matched_words = query.split() if search_type == 'exact' else []
            try:
                row_tokens = json.loads(lrow['tokens']) if lrow['tokens'] else []
            except Exception:                                        # noqa: BLE001
                row_tokens = []
            # Best-effort token positions for 'exact' only (see
            # _find_exact_phrase_positions); 'regex' has no well-defined
            # phrase span to locate, so matched_positions stays [] and
            # matched_restored/partly_restored both come back False.
            matched_positions = (_find_exact_phrase_positions(row_tokens, query)
                                  if search_type == 'exact' else [])
            if not passes_distance_filter(text, matched_words, filename, language):
                continue
            doc_id = docs.doc_for(language, filename, ref)
            m = docs.meta(doc_id) if doc_id else None
            if not _document_passes_filters(m, date_from, date_to, region, text_type,
                                             material, source, kind, place):
                continue
            restored = docs.restored_indices(language, filename, ref)
            restored_set = set(restored.get('restored') or [])
            restored_rank, extra_restorations = _restored_rank_and_extra(matched_positions, restored_set)
            if exclude_restored and restored_rank == 2:
                stats['restored_excluded_count'] += 1
                continue
            seen.add((filename, ref))
            # No per-lemma position dict exists on this SLOW PATH (no
            # lemma match at all for 'regex'; 'exact' has no co-occurrence
            # concept to be "scattered" relative to) -- an exact/regex hit
            # is ranked as an exact adjacent phrase by construction.
            kept.append({
                'filename': filename, 'ref': ref, 'doc_id': doc_id, 'text': text,
                'tokens': row_tokens, 'matched_words': matched_words,
                'matched_positions': matched_positions, 'meta': m,
                'rank': {
                    'adjacency': 0, 'restored_rank': restored_rank,
                    'extra_restorations': extra_restorations,
                    'date': _date_sort_value(m), 'region': (m or {}).get('region'),
                    'doc_id': doc_id or '',
                },
            })

    total = len(kept)
    by_source_region = _tally_source_region(kept)
    by_century = _tally_century(kept)
    kept.sort(key=lambda k: _document_sort_key(sort, k['rank']))
    page = kept[offset:offset + limit]
    page_results = []
    for p in page:
        row, _m = _document_hit(language, p['filename'], p['ref'], p['matched_words'], set(),
                                 tokens=p['tokens'], matched_positions=p['matched_positions'],
                                 formula_count=None, meta_override=p['meta'])
        row['text'] = p['text']
        page_results.append(row)
    return page_results, total, by_source_region, by_century, stats


DOCUMENTS_LEMMA_CAP = 12


def _rarest_documents_lemmas(lemmas, language, cap, conn=None):
    """The `cap` rarest of `lemmas` by document frequency in the documents
    index (its `lemma_doc_freq` table), and the number reduced from; or the
    lemmas unchanged and None when no reduction is needed or no index is
    open. A lemma the index never saw (frequency 0) is dropped first, since it
    can match nothing."""
    import backend.documents as docs
    lemmas = set(lemmas)
    if len(lemmas) <= cap:
        return lemmas, None
    conn = conn or docs.get_connection(language)
    if conn is None:
        return lemmas, None
    df = {}
    for lem in lemmas:
        try:
            row = conn.execute('SELECT df FROM lemma_doc_freq WHERE lemma = ?', (lem,)).fetchone()
        except Exception:
            return lemmas, None
        df[lem] = row[0] if row else 0
    present = [l for l in lemmas if df[l] > 0]
    if len(present) <= cap:
        return set(present) or lemmas, (len(lemmas) if len(present) < len(lemmas) else None)
    return set(sorted(present, key=lambda l: (df[l], l))[:cap]), len(lemmas)


def _line_search_documents_only(query, language, search_type, offset, limit, sort, count_only,
                                 date_from, date_to, region, text_type, material, source,
                                 search_start_time, exclude_restored=False, hide_formulas=None,
                                 kind=None, place=None, rare_focus_filter=None):
    """Full /api/line-search response for collection='documents': the
    documentary corpus alone, no literary search run at all. Returns a Flask
    response directly (line_search() returns this immediately).

    Stage 4: `offset`/`limit` page the (now uncapped) result list 50 rows at
    a time by default, ranked by `sort`; the payload's 'total'/
    'distinct_loci' are the TRUE total after every filter, never a 500-row
    lower bound -- see _search_documents_collection's own docstring."""
    import time as time_module
    import backend.documents as docs

    filtered_query_lemmas = set()
    filtered_common_words = []
    if search_type == 'lemma' and language in docs.SUPPORTED_LANGUAGES:
        from backend.matcher import DEFAULT_LATIN_STOP_WORDS, DEFAULT_GREEK_STOP_WORDS
        stopwords = set(DEFAULT_LATIN_STOP_WORDS if language == 'la' else DEFAULT_GREEK_STOP_WORDS)
        query_lemmas = _lemmatize_query_simple(query, language, text_processor)
        content_lemmas = query_lemmas - stopwords
        filtered_query_lemmas = content_lemmas if len(content_lemmas) >= 2 else query_lemmas
        filtered_common_words = sorted(query_lemmas - content_lemmas)
    elif language in docs.SUPPORTED_LANGUAGES:
        filtered_query_lemmas = set(_normalize_lemma(t, language) for t in query.lower().split())

    # A passage-sized query searches on its rarest words here too. The
    # Reader's Documents tab sends a whole selection; a Tacitus chapter of 120
    # words took over four minutes against the documents index and a single
    # sentence eleven seconds (measured 2026-10-11), where the literary path
    # answers the same chapter in under a second because it caps the query
    # (see LEMMA_CAP in line_search). Same rule, same payload note.
    reduced_from = None
    if search_type == 'lemma' and len(filtered_query_lemmas) > DOCUMENTS_LEMMA_CAP:
        filtered_query_lemmas, reduced_from = _rarest_documents_lemmas(
            filtered_query_lemmas, language, DOCUMENTS_LEMMA_CAP)

    min_matched = max(1, min(2, len(filtered_query_lemmas))) if search_type == 'lemma' else 1

    results, total, by_source_region, by_century, doc_stats = _search_documents_collection(
        language, search_type, query, filtered_query_lemmas, min_matched, offset, limit,
        date_from, date_to, region, text_type, material, source,
        exclude_restored=exclude_restored, hide_formulas=hide_formulas, sort=sort,
        kind=kind, place=place)

    # rare_focus (the Reader): the same filter the literary path applies, passed
    # in by line_search so this module does not import it. A document sharing
    # only commonplaces is hidden and counted in payload['rare_focus'].
    rare_focus_report = None
    if rare_focus_filter is not None and search_type == 'lemma':
        results, hidden, commons = rare_focus_filter(results, language)
        if hidden:
            rare_focus_report = {'hidden': hidden, 'common_lemmas': commons}

    search_time = round(time_module.time() - search_start_time, 3)
    payload = {
        'collection': 'documents',
        'total': total,
        'distinct_loci': total,
        'query': query,
        'search_time': search_time,
        'capped': False,
        'sort': sort,
        'pagination': {'offset': offset, 'limit': limit, 'total': total},
        'corpus_version': docs.get_corpus_version(language),
    }
    if filtered_common_words:
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
    if by_source_region:
        payload['documents_by_source_region'] = by_source_region
        payload['lines_all'] = sum(w['count'] for w in by_source_region)
    if by_century:
        payload['documents_by_century'] = by_century
    if exclude_restored:
        payload['restored_excluded_count'] = doc_stats['restored_excluded_count']
    if hide_formulas is not None:
        payload['formulas_hidden_count'] = doc_stats['formulas_hidden_count']
    if doc_stats['formula_summary']:
        payload['formula_summary'] = doc_stats['formula_summary']
    if not count_only:
        payload['results'] = results
    return jsonify(payload)


@api_route('/documents/<doc_id>', methods=['GET'])
def get_document(doc_id):
    """Stage 3b-3's document Reader view: one documentary text's own lines
    (from the documents index's `lines` table, via `doc_meta`), restored/
    fragment positions per line, credit, date/place/labels, and the stage
    3a display fields (museum, inventory, dimensions, translation,
    apparatus, commentary, image links) from metadata.db's `display`
    table. Behind TESSERAE_DOCUMENTS=1 (404 otherwise, same as the search
    side of this feature being entirely absent with the switch off); a
    live site additionally gates this at the client with the ?documents=1
    trial (see LineSearch.jsx), same as the search control itself.

    `doc_id` alone does not say which language's documents index it lives
    in (ids are source-prefixed, e.g. "edh:HD047322", not language-coded),
    so an explicit `?language=la|grc` is tried first; without one, every
    language in backend.documents.SUPPORTED_LANGUAGES is tried in turn
    and the first hit wins -- doc ids are unique across sources within a
    language by construction (stage 3a's merged corpus id), and no case
    of a document id colliding across la/grc has ever been seen in a real
    build, but a future dual-language corpus could reconsider this.
    """
    import backend.documents as docs
    if not docs.enabled():
        return jsonify({'error': 'not found'}), 404
    requested_language = (request.args.get('language') or '').strip().lower()
    languages_to_try = ([requested_language] if requested_language in docs.SUPPORTED_LANGUAGES
                         else list(docs.SUPPORTED_LANGUAGES))
    doc_data = None
    found_language = None
    for lang in languages_to_try:
        if not docs.is_index_available(lang):
            continue
        doc_data = docs.get_document_lines(lang, doc_id)
        if doc_data is not None:
            found_language = lang
            break
    if doc_data is None:
        return jsonify({'error': 'document not found'}), 404

    m = docs.meta(doc_id) or {}
    display = docs.display_fields(doc_id)
    edition_text = docs.leiden_texts([doc_id]).get(doc_id)
    payload = {
        'edition_text': edition_text,
        'doc_id': doc_id,
        'language': found_language,
        'text_id': doc_data['filename'],
        'lines': doc_data['lines'],
        'credit': m.get('credit'),
        'collection': m.get('collection'),
        'source': m.get('source'),
        'date_not_before': m.get('date_not_before'),
        'date_not_after': m.get('date_not_after'),
        'ancient_place': m.get('ancient_place'),
        'modern_place': m.get('modern_place'),
        'region': m.get('region'),
        'pleiades_id': m.get('pleiades_id'),
        'text_type_label': m.get('text_type_label'),
        'object_type_label': m.get('object_type_label'),
        'material_label': m.get('material_label'),
        'display': display or {},
        'image_hosts_down': docs.image_hosts_down_for((display or {}).get('image_url')),
    }
    indexing_only = docs.is_indexing_only(doc_id)
    if indexing_only:
        payload['indexing_only'] = True
    resp = jsonify(payload)
    if indexing_only:
        # Held for indexing and search only: the page may show the text, nothing may keep or pass it on.
        resp.headers['X-Robots-Tag'] = 'noindex, noarchive'
    return resp


@api_route('/documents/<doc_id>/scholarship', methods=['GET'])
def get_document_scholarship(doc_id):
    """Journal sentences and commentary notes that cite one document, from
    the offline document citation index: citation, one excerpt and a link,
    newest first, never summarised. Behind TESSERAE_DOCUMENTS=1 like the
    document view itself (404 otherwise); an absent index file gives an empty
    list."""
    import backend.documents as _docs_mod
    if not _docs_mod.enabled():
        return jsonify({'error': 'not found'}), 404
    from backend.document_scholarship import scholarship_for
    return jsonify(dict(scholarship_for(doc_id), doc_id=doc_id))


@api_route('/documents/places', methods=['GET'])
def document_places():
    """The findspots for the Place control of the Inscriptions & Papyri
    search: every distinct place (ancient name, with the commonest modern
    name after it) and how many documents it has, sorted by count, for one
    language when `language` is given (la, grc). `q` keeps the places whose
    name contains that text, `limit` the first N of those (`total` counts them all). See
    backend.documents.place_list. Behind TESSERAE_DOCUMENTS=1 like the rest."""
    import backend.documents as _docs_mod
    if not _docs_mod.enabled():
        return jsonify({'error': 'not found'}), 404
    language = (request.args.get('language') or '').strip() or None
    q = (request.args.get('q') or '').strip().lower()
    try:
        limit = int(request.args.get('limit', 0))
    except (TypeError, ValueError):
        limit = 0
    places = _docs_mod.place_list(language)
    if q:
        # Names that begin with the text come first, then names with a word
        # that begins with it, then the rest; by count within each group.
        def _rank(p):
            name = p['label'].lower()
            if name.startswith(q):
                return 0
            return 1 if re.search(r'(?<![^\W_])' + re.escape(q), name) else 2
        places = sorted((p for p in places if q in p['label'].lower()), key=_rank)
    total = len(places)
    if limit > 0:
        places = places[:limit]
    return jsonify({'language': language, 'places': places, 'total': total})


@api_route('/documents/browse', methods=['GET'])
def browse_documents():
    """The Documents section of Browse Corpus: a normalized facet tree
    (kind -> region -> century, each with counts; for papyri, region ->
    findspot -> century -- see `findspot_counts`) plus the flat filters
    (text type, material, object type, language) and one page of matching
    documents. Behind TESSERAE_DOCUMENTS=1 (404 otherwise, same as the rest
    of this feature); see backend/documents_browse.py for the normalization
    rules and the in-memory facet cache this reads.
    """
    import backend.documents as _docs_mod
    if not _docs_mod.enabled():
        return jsonify({'error': 'not found'}), 404
    import backend.documents_browse as browse_mod

    def _arg(name):
        v = (request.args.get(name) or '').strip()
        return v or None

    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.args.get('page_size', browse_mod.DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = browse_mod.DEFAULT_PAGE_SIZE

    result = browse_mod.browse(
        kind=_arg('kind'), region=_arg('region'), findspot=_arg('findspot'), century=_arg('century'),
        text_type=_arg('text_type'), material=_arg('material'),
        object_type=_arg('object'), language=_arg('language'), place=_arg('doc_place'),
        page=page, page_size=page_size)

    # First-line snippets are a per-document index lookup each; only done
    # for the one page actually being returned, and best-effort (see
    # first_line_for -- None on any miss, never an error for the request).
    for doc in result['documents']:
        doc['first_line'] = browse_mod.first_line_for(doc['doc_id'], doc.get('language'))

    return jsonify(result)
