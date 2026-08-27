"""
Tesserae V6 - Scene Blueprint

Passage-level content retrieval for the Reader: "Similar Passages" (what else in
the corpus is like this stretch of text) and "Theme Search" (find passages about
a described subject), plus the connection densities the Reader draws in its
gutter. Backed by backend/passage_index.py.

Endpoints (all GET, all under the app's API prefix):
    /passages/status                 index availability and size
    /passages/theme-search           ?q=...&limit=&languages=&scale=
    /passages/similar                ?work=&ref_start=&ref_end=  (or ?window=)
    /passages/density                ?work=&scale=
    /passages/export                 ?q=...&format=json|csv  the same search,
                                     with the source passages, oldest first

Every route answers 200 with an `error` field rather than raising, so a missing
or half-built index degrades the Reader's panel instead of breaking the page.
"""
import csv
import io

from flask import Blueprint, Response, jsonify, request

from backend.logging_config import get_logger
from backend import passage_index
from backend import lexical_density
from backend import translations
from backend import window_texts

logger = get_logger('blueprints.passages')

passages_bp = Blueprint('passages', __name__)

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


@passages_bp.route('/passages/status')
def scene_status():
    return jsonify(passage_index.status())


@passages_bp.route('/passages/theme-search')
def theme_search():
    """Free-text content query across every indexed language at once."""
    q = (request.args.get('q') or request.args.get('query') or '').strip()
    if not q:
        return jsonify({'error': 'q is required', 'results': []})
    # The module contract is that these routes answer 200 with an error field
    # rather than raising, so a half-built index degrades the Reader's panel
    # instead of breaking the page. That was documented and not implemented:
    # on deployment this raised, Apache turned it into a bare 500, and the app
    # log was unreadable, so the cause could not be seen from the response at
    # all. An error the operator cannot read is an error they cannot fix.
    try:
        out = passage_index.find_by_text(
            q, limit=_int_arg('limit', 25), languages=_languages(), scale=_scale())
    except passage_index.EmbedUnavailable as e:
        # "cannot ask" is not "found nothing". Only one of those means the
        # corpus lacks the subject, and reporting the wrong one would be a
        # false negative dressed as a finding.
        logger.warning('[PASSAGES] encoder unavailable: %s', e)
        return jsonify({'error': 'theme search is unavailable: the query encoder '
                                 'service is not running', 'unavailable': True,
                        'results': []})
    except Exception as e:
        logger.exception('[PASSAGES] theme-search failed')
        return jsonify({'error': f'{type(e).__name__}: {e}', 'results': []})
    out['presentation'] = (
        'Each result is a passage whose CONTENT matches the description, not its '
        'wording, so results in different languages usually share no words with '
        'the query. Lead with the work and the gist; treat a result marked '
        'strong:false as a weak neighbour rather than a finding.')
    return jsonify(out)


def _chronological(results):
    """Oldest first, undated last.

    The same order the site shows results in, and the order the export has to
    keep: a themed set that crosses centuries is read as a line of descent, and
    a spreadsheet sorted by relevance score throws that away.
    """
    def key(r):
        y = r.get('year')
        return (0, y) if isinstance(y, (int, float)) else (1, 0)
    return sorted(results, key=key)


# The columns, in the order a reader wants to see them. Passage text last,
# because it is the long field and a spreadsheet is easier to scan when the
# labels come first.
_EXPORT_COLUMNS = [
    ('n', 'n'),
    ('author', 'author'),
    ('title', 'work'),
    ('locus', 'locus'),
    ('date', 'date'),
    ('era', 'era'),
    ('language', 'language'),
    ('score', 'score'),
    ('strong', 'strong'),
    ('themes', 'themes'),
    ('summary', 'gist'),
    ('passage', 'text'),
]

_LANG_NAME = {'la': 'Latin', 'grc': 'Greek', 'en': 'English', 'he': 'Hebrew',
              'cop': 'Coptic', 'fa': 'Persian', 'ur': 'Urdu', 'ar': 'Arabic'}


def _export_rows(results, texts):
    """Flatten results into labelled rows carrying their source passage."""
    rows = []
    for i, r in enumerate(_chronological(results), start=1):
        locus = r.get('ref_start') or ''
        if r.get('ref_end') and r['ref_end'] != locus:
            locus = f"{locus}-{r['ref_end']}"
        rows.append({
            'n': i,
            'author': r.get('author') or '',
            'work': r.get('title') or r.get('work') or '',
            'locus': locus,
            # The dating note ("d. c. 1020 CE") says more than the bare year and
            # is what a scholar would cite, so it leads where it exists.
            'date': r.get('date_note') or (str(r['year']) if isinstance(
                r.get('year'), (int, float)) else ''),
            'era': r.get('era') or '',
            'language': _LANG_NAME.get(r.get('language'), r.get('language') or ''),
            'score': round(r['score'], 4) if isinstance(
                r.get('score'), (int, float)) else '',
            'strong': 'yes' if r.get('strong') else 'no',
            'themes': '; '.join(str(t) for t in (r.get('themes') or [])),
            'gist': r.get('gist') or '',
            # Absent rather than empty when the lookup has no text, so a hole is
            # visible in the export instead of looking like a blank passage.
            'text': texts.get(r.get('id'), '[source text unavailable]'),
            'id': r.get('id') or '',
        })
    return rows


@passages_bp.route('/passages/export')
def export_theme_search():
    """The same Theme Search, with the source passages, oldest first.

    Theme Search results name a work and a line range and carry a machine-written
    summary, but never the passage itself, so what a reader could take away was a
    list of pointers. This returns the passages, labelled, in chronological
    order, as JSON for the printable view or CSV for a spreadsheet.
    """
    q = (request.args.get('q') or request.args.get('query') or '').strip()
    fmt = (request.args.get('format') or 'json').strip().lower()
    if not q:
        return jsonify({'error': 'q is required', 'results': []})
    if fmt not in ('json', 'csv'):
        return jsonify({'error': f'unknown format {fmt}', 'results': []})
    try:
        out = passage_index.find_by_text(
            q, limit=_int_arg('limit', 25), languages=_languages(), scale=_scale())
    except passage_index.EmbedUnavailable as e:
        logger.warning('[PASSAGES] encoder unavailable: %s', e)
        return jsonify({'error': 'theme search is unavailable: the query encoder '
                                 'service is not running', 'unavailable': True,
                        'results': []})
    except Exception as e:
        logger.exception('[PASSAGES] export failed')
        return jsonify({'error': f'{type(e).__name__}: {e}', 'results': []})

    results = out.get('results') or []
    texts = window_texts.texts_for([r.get('id') for r in results])
    rows = _export_rows(results, texts)
    missing = sum(1 for r in rows if r['text'] == '[source text unavailable]')
    if missing:
        logger.warning('[PASSAGES] export: %d of %d passages had no source text',
                       missing, len(rows))

    if fmt == 'csv':
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([label for label, _ in _EXPORT_COLUMNS])
        for row in rows:
            w.writerow([row[key] for _, key in _EXPORT_COLUMNS])
        # BOM: Excel reads a UTF-8 CSV as the system codepage without one, which
        # turns every Greek, Hebrew and Persian passage in the file into mojibake.
        body = '﻿' + buf.getvalue()
        stamp = ''.join(ch if ch.isalnum() else '_' for ch in q)[:40].strip('_')
        # content_type, not mimetype: Flask appends its own charset to a
        # mimetype, so passing one here produced "text/csv; charset=utf-8;
        # charset=utf-8".
        return Response(body, content_type='text/csv; charset=utf-8', headers={
            'Content-Disposition':
                f'attachment; filename="tesserae_theme_{stamp or "search"}.csv"'})

    return jsonify({
        'query': q,
        'count': len(rows),
        'missing_text': missing,
        'confidence': out.get('confidence'),
        'note': out.get('note'),
        'order': 'chronological, oldest first; undated last',
        'results': rows,
    })


@passages_bp.route('/passages/similar')
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
        out = passage_index.find_similar_to_window(
            window, limit=limit, languages=langs, include_same_work=include_same,
            suppress_other_versions=not include_versions)
    elif work:
        out = passage_index.find_similar_to_passage(
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


@passages_bp.route('/lexical-density')
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


@passages_bp.route('/translation')
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


@passages_bp.route('/passages/density')
def density():
    """Per-window connection counts for the Reader's gutter."""
    work = (request.args.get('work') or '').strip()
    if not work:
        return jsonify({'error': 'work is required', 'windows': []})
    return jsonify(passage_index.connection_density(work, scale=_scale() or 'fine'))
