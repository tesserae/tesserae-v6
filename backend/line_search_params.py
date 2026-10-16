"""The request parameters of /api/line-search, read and coerced in one place.

Moved out of backend/blueprints/line_search.py unchanged (line-search steps job, 2026-10-13).
"""
from dataclasses import dataclass
from typing import Optional

from backend.blueprints.documents import _DOCUMENT_SORT_MODES


@dataclass
class LineSearchParams:
    """Everything /line-search reads from the request, with its defaults applied."""
    data: object
    query: str
    language: str
    search_type: str
    author_filter: str
    work_filter: str
    line_start: object
    line_end: object
    max_results: int
    count_only: bool
    rare_focus: bool
    collection: str
    documents_active: bool
    date_from: Optional[int]
    date_to: Optional[int]
    doc_region_filter: str
    doc_text_type_filter: str
    doc_material_filter: str
    doc_source_filter: str
    doc_kind_filter: str
    doc_place_filter: str
    doc_exclude_restored: bool
    doc_hide_formulas: Optional[int]
    doc_sort: str
    doc_offset: int
    doc_limit: int
    exclude_text_id: str
    exclude_locus: str
    line_text: str
    exclude_author: str = ''
    lemmas: tuple = ()


def _read_params(data) -> LineSearchParams:
    """Read and coerce every request parameter (POST body or GET query string)."""

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

    doc_place_filter = (data.get('doc_place') or '').strip() if documents_active else ''

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
    # Drop every work of one author (the work id's first segment, e.g. 'vergil').
    exclude_author = str(data.get('exclude_author', '') or '').strip().lower()

    # Dictionary forms the caller already has (the results page's corpus
    # panel sends a parallel's shared lemmas). With search_type 'lemma' they
    # are the query-lemma set as given and are not lemmatized again.
    _lemmas_raw = data.get('lemmas')
    if isinstance(_lemmas_raw, str):
        _lemmas_raw = _lemmas_raw.split()
    lemmas = tuple(str(x).strip() for x in _lemmas_raw if str(x).strip()) if isinstance(_lemmas_raw, (list, tuple)) else ()

    return LineSearchParams(
        data=data, query=query, language=language, search_type=search_type,
        author_filter=author_filter, work_filter=work_filter,
        line_start=line_start, line_end=line_end, max_results=max_results,
        count_only=count_only, rare_focus=rare_focus, collection=collection,
        documents_active=documents_active, date_from=date_from, date_to=date_to,
        doc_region_filter=doc_region_filter, doc_text_type_filter=doc_text_type_filter,
        doc_material_filter=doc_material_filter, doc_source_filter=doc_source_filter,
        doc_kind_filter=doc_kind_filter, doc_place_filter=doc_place_filter, doc_exclude_restored=doc_exclude_restored,
        doc_hide_formulas=doc_hide_formulas, doc_sort=doc_sort,
        doc_offset=doc_offset, doc_limit=doc_limit,
        exclude_text_id=exclude_text_id, exclude_locus=exclude_locus,
        line_text=line_text, exclude_author=exclude_author, lemmas=lemmas)
