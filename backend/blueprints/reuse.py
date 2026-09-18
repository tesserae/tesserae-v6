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

Endpoints (both GET, under the app's API prefix):
    /reuse/line   ?work=&ref=&language=                  other works' lines
                  that repeat this line, both directions
    /reuse/marks  ?work=&ref_start=&ref_end=&language=    per-line reuse
                  counts for a range, for the marker
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


@reuse_bp.route('/reuse/line')
def reuse_line():
    work = (request.args.get('work') or '').strip()
    ref = (request.args.get('ref') or '').strip()
    if not work or not ref:
        return jsonify({'error': 'work and ref are required'}), 400
    language = _language()
    if not reuse_table.is_available(language):
        return _not_built(language)
    return jsonify(reuse_table.line(language, work, ref))


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
    return jsonify(reuse_table.marks(language, work, ref_start, ref_end))
