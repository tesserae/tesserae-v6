"""
Tesserae V6 - Scene Blueprint

Passage-level content retrieval for the Reader: "Similar Passages" (what else in
the corpus is like this stretch of text) and "Theme Search" (find passages about
a described subject), plus the connection densities the Reader draws in its
gutter. Backed by backend/scene_index.py.

Endpoints (all GET, all under the app's API prefix):
    /scene/status                 index availability and size
    /scene/theme-search           ?q=...&limit=&languages=&scale=
    /scene/similar                ?work=&ref_start=&ref_end=  (or ?window=)
    /scene/density                ?work=&scale=

Every route answers 200 with an `error` field rather than raising, so a missing
or half-built index degrades the Reader's panel instead of breaking the page.
"""
from flask import Blueprint, jsonify, request

from backend.logging_config import get_logger
from backend import scene_index
from backend import lexical_density
from backend import translations

logger = get_logger('blueprints.scene')

scene_bp = Blueprint('scene', __name__)

_MAX_LIMIT = 100


def _int_arg(name, default, lo=1, hi=_MAX_LIMIT):
    try:
        return max(lo, min(int(request.args.get(name, default)), hi))
    except (TypeError, ValueError):
        return default


def _languages():
    raw = (request.args.get('languages') or '').strip()
    if not raw:
        return None
    langs = [x.strip() for x in raw.split(',') if x.strip()]
    return langs or None


def _scale():
    s = (request.args.get('scale') or '').strip().lower()
    return s if s in ('fine', 'coarse') else None


@scene_bp.route('/scene/status')
def scene_status():
    return jsonify(scene_index.status())


@scene_bp.route('/scene/theme-search')
def theme_search():
    """Free-text content query across every indexed language at once."""
    q = (request.args.get('q') or request.args.get('query') or '').strip()
    if not q:
        return jsonify({'error': 'q is required', 'results': []})
    out = scene_index.find_by_text(
        q, limit=_int_arg('limit', 25), languages=_languages(), scale=_scale())
    out['presentation'] = (
        'Each result is a passage whose CONTENT matches the description, not its '
        'wording, so results in different languages usually share no words with '
        'the query. Lead with the work and the gist; treat a result marked '
        'strong:false as a weak neighbour rather than a finding.')
    return jsonify(out)


@scene_bp.route('/scene/similar')
def similar_passages():
    """Passages whose content resembles a given passage.

    Accepts either an index window id (?window=) or a reader selection
    (?work= plus optional ?ref_start= and ?ref_end=).
    """
    window = (request.args.get('window') or '').strip()
    work = (request.args.get('work') or '').strip()
    limit = _int_arg('limit', 15)
    langs = _languages()
    include_same = (request.args.get('include_same_work') or '').lower() in ('1', 'true', 'yes')
    # By default the same Bible passage in the corpus's other versions is not
    # reported back: a reader in Coptic Genesis knows it is also in Hebrew and
    # Latin. A scholar comparing versions can ask for them with
    # ?include_other_versions=1.
    include_versions = (request.args.get('include_other_versions') or '').lower() in ('1', 'true', 'yes')
    if window:
        out = scene_index.find_similar_to_window(
            window, limit=limit, languages=langs, include_same_work=include_same,
            suppress_other_versions=not include_versions)
    elif work:
        out = scene_index.find_similar_to_passage(
            work, request.args.get('ref_start'), request.args.get('ref_end'),
            limit=limit, languages=langs, scale=_scale() or 'fine',
            suppress_other_versions=not include_versions)
    else:
        return jsonify({'error': 'work or window is required', 'results': []})
    out['presentation'] = (
        'These passages resemble the selection in CONTENT (scene type, theme, '
        'situation) rather than in wording. Say what kind of resemblance each '
        'shows, and note that a cross-language match shares no vocabulary. '
        'A result carrying `also_in` is one scriptural passage present in several '
        'of the corpus versions, collapsed into a single entry.')
    return jsonify(out)


@scene_bp.route('/lexical-density')
def lexical_density_route():
    """Per-line lexical connection counts, for the Reader's red gutter marks.

    Answers the older question ("what else uses these words?") beside the scene
    index's newer one ("what else is about this?"). Read off the precomputed
    lemma_doc_freq table and cached per work, so it costs a file read after the
    first call.
    """
    work = (request.args.get('work') or '').strip()
    if not work:
        return jsonify({'error': 'work is required', 'lines': []})
    language = (request.args.get('language') or 'la').strip()
    return jsonify(lexical_density.line_density(work, language=language))


@scene_bp.route('/translation')
def translation_route():
    """Aligned public-domain English for a selected passage.

    Pass the work and the selected refs (comma-separated, or repeated `ref`).
    Answers with available:false and a plain reason when no aligned translation
    covers the passage, which is a normal outcome given partial coverage.
    """
    work = (request.args.get('work') or '').strip()
    if not work:
        return jsonify({'available': False, 'reason': 'work is required'})
    refs = request.args.getlist('ref')
    if not refs:
        raw = request.args.get('refs') or ''
        refs = [r for r in (x.strip() for x in raw.split('|')) if r]
    return jsonify(translations.for_passage(work, refs))


@scene_bp.route('/scene/density')
def density():
    """Per-window connection counts for the Reader's gutter."""
    work = (request.args.get('work') or '').strip()
    if not work:
        return jsonify({'error': 'work is required', 'windows': []})
    return jsonify(scene_index.connection_density(work, scale=_scale() or 'fine'))
