"""
Tesserae V6 - Reuse Blueprint

Corpus-wide verbatim/near-verbatim line reuse table, for the Reader's
"quoted in N works" marker and its Reuse tab. Backed by
backend/reuse_table.py, which reads cache/reuse_pairs/<lang>.db (built by
scripts/reuse/build_reuse_table.py -- see that script's docstring and
research/reuse_table/REPORT_2026-09-18.md for what the table measures).

Latin only as of 2026-09-19. A language with no table answers 404 with a
plain message rather than an empty 200, so the Reader can tell "not built
for this language" apart from "built, nothing repeats this line" (a normal
empty result).

DOCUMENTARY REUSE (2026-10-08): when TESSERAE_DOCUMENTS=1, both endpoints
also carry what backend/reuse_documents.py's cross-collection table
(cache/reuse_pairs/<lang>_documents.db) knows about the same line --
inscriptions and papyri that quote or near-quote it, built by
scripts/reuse/build_documents_reuse_table.py. This is additive and never
changes the existing literary 404 contract: a line with a literary table
but no documents table (or the switch off, or no documents hits) simply
carries an empty/omitted documents side, exactly as before this feature
existed. Behind the client's own `documents_trial` session flag
(?documents=1, the same trial LineSearch.jsx already uses) -- the server
sends the data whenever the env switch is on; the Reader decides whether
to show it.

Endpoints (both GET, under the app's API prefix):
    /reuse/line   ?work=&ref=&language=                  other works' lines
                  that repeat this line, both directions -- each carries a
                  `tier` ('strict' or 'possible', see reuse_table.line).
                  Also carries `documents: [...]` (same tier rule, see
                  reuse_documents.line) when TESSERAE_DOCUMENTS=1 and a
                  documents table exists for `language`; omitted otherwise.
    /reuse/marks  ?work=&ref_start=&ref_end=&language=    per-line reuse
                  counts for a range, for the marker -- `n_works` (strict)
                  and `n_possible_works` (possible), see reuse_table.marks.
                  Each line also carries `n_documents`/`n_possible_documents`
                  under the same TESSERAE_DOCUMENTS=1 gate.
"""
from flask import Blueprint, jsonify, request

from backend.logging_config import get_logger
from backend import reuse_table

logger = get_logger('blueprints.reuse')

reuse_bp = Blueprint('reuse', __name__)


def _language():
    return (request.args.get('language') or 'la').strip() or 'la'


def _not_built(language):
    return jsonify({
        'error': f"No reuse table has been built for language '{language}'.",
        'available': False,
    }), 404


def _documents_for_line(language, work, ref):
    """documents hits for one line, or None when the documents trial is
    off or no cross-collection table exists for this language -- callers
    treat None as "omit the field", never as an empty-but-present list
    (which would mean "checked, found nothing")."""
    import backend.documents as docs
    if not docs.enabled():
        return None
    from backend import reuse_documents
    if not reuse_documents.is_available(language):
        return None
    return reuse_documents.line(language, work, ref).get('documents', [])


def _documents_marks_for_work(language, work, ref_start, ref_end):
    """{ref: {'n_documents', 'n_possible_documents'}} for a work, or {}
    under the same gate as _documents_for_line (see its docstring) --
    here an empty dict is indistinguishable from "gated off", which is
    fine: reuse_marks merges it into each line's entry with .get(ref, {}),
    so a line simply carries no documents counts either way."""
    import backend.documents as docs
    if not docs.enabled():
        return {}
    from backend import reuse_documents
    if not reuse_documents.is_available(language):
        return {}
    result = reuse_documents.marks(language, work, ref_start, ref_end)
    if not result.get('available'):
        return {}
    return {l['ref']: l for l in result.get('lines', [])}


@reuse_bp.route('/reuse/line')
def reuse_line():
    work = (request.args.get('work') or '').strip()
    ref = (request.args.get('ref') or '').strip()
    if not work or not ref:
        return jsonify({'error': 'work and ref are required'}), 400
    language = _language()
    if not reuse_table.is_available(language):
        return _not_built(language)
    result = reuse_table.line(language, work, ref)
    documents = _documents_for_line(language, work, ref)
    if documents is not None:
        result['documents'] = documents
    return jsonify(result)


@reuse_bp.route('/reuse/marks')
def reuse_marks():
    work = (request.args.get('work') or '').strip()
    if not work:
        return jsonify({'error': 'work is required'}), 400
    language = _language()
    if not reuse_table.is_available(language):
        return _not_built(language)
    ref_start = (request.args.get('ref_start') or '').strip() or None
    ref_end = (request.args.get('ref_end') or '').strip() or None
    result = reuse_table.marks(language, work, ref_start, ref_end)
    doc_marks = _documents_marks_for_work(language, work, ref_start, ref_end)
    if doc_marks:
        seen_refs = set()
        for entry in result.get('lines', []):
            seen_refs.add(entry['ref'])
            dm = doc_marks.get(entry['ref'])
            if dm:
                entry['n_documents'] = dm['n_documents']
                entry['n_possible_documents'] = dm['n_possible_documents']
        # A line with ONLY document hits (no literary reuse at all) never
        # appears in result['lines'] from the literary query above -- add
        # it here, with n_works/n_possible_works at 0, so its documents
        # count is not silently dropped.
        for ref, dm in doc_marks.items():
            if ref not in seen_refs:
                result.setdefault('lines', []).append({
                    'ref': ref, 'n_works': 0, 'n_possible_works': 0,
                    'n_documents': dm['n_documents'],
                    'n_possible_documents': dm['n_possible_documents'],
                })
    return jsonify(result)
