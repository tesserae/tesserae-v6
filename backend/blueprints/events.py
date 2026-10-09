"""Events: the read-only API behind the Events page.

    GET /api/events?q=&type=&century=&page=&per_page=
        the events in the dossier database, searchable by label, filterable
        by type and century (a signed number: -5 is the fifth century BCE,
        1 the first CE), paged. Also returns the types and centuries present
        so the page can offer them.
    GET /api/events/<id>
        one dossier: the event, its passages (Reader links, the offline
        relevance label "yes" first, then "mention"), nearby documents
        (links to the document view), scholarship and map points.

The data is a SQLite file written offline by scripts/events/ (see
load_dossiers_sqlite.py); the route only reads it. The path comes from
TESSERAE_EVENTS_DB, default data/events/event_dossiers.sqlite. With no file
the list route answers with available=false and the detail route with 404.
"""
import json
import os
import sqlite3
from urllib.parse import quote

from flask import Blueprint, jsonify, request

from backend.logging_config import get_logger

logger = get_logger('events')
events_bp = Blueprint('events', __name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(_ROOT, 'data', 'events', 'event_dossiers.sqlite')
LABEL_ORDER = {'yes': 0, 'mention': 1}
MAX_PER_PAGE = 100


def db_path():
    return os.environ.get('TESSERAE_EVENTS_DB') or DEFAULT_DB


def _conn():
    path = db_path()
    if not os.path.exists(path):
        return None
    c = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    return c


def _columns(c, table):
    return {r['name'] for r in c.execute(f'PRAGMA table_info({table})')}


def _json(value, default):
    if value in (None, ''):
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def century_of(year):
    """Signed century of a year: -490 is -5 (5th BCE), 9 is 1 (1st CE)."""
    if year is None:
        return None
    y = int(year)
    if y < 0:
        return -((-y - 1) // 100 + 1)
    return (y - 1) // 100 + 1 if y > 0 else -1


def century_range(c):
    """First and last year of a signed century."""
    if c < 0:
        return -(-c) * 100, -(-c - 1) * 100 - 1
    return (c - 1) * 100 + 1, c * 100


def _language_of(work, given=None):
    if given in ('la', 'grc'):
        return given
    try:
        from backend import window_texts
        lang = window_texts.language_of(work)
        if lang:
            return lang
    except Exception:  # the passage index may not be present (previews, tests)
        pass
    return 'la'


def reader_url(work, lang, ref):
    w = work if str(work).endswith('.tess') else f'{work}.tess'
    return f'/read?work={quote(w)}&lang={quote(lang)}&ref={quote(ref or "")}'


def document_url(doc_id, lang='la'):
    return f'/document?doc={quote(str(doc_id), safe="")}&lang={lang}&documents=1'


def _event_row(r):
    return {
        'id': r['id'], 'label': r['label'], 'type': r['type'],
        'date_start': r['date_start'], 'date_end': r['date_end'],
        'place': r['place'],
    }


@events_bp.route('/events')
def list_events():
    c = _conn()
    if c is None:
        return jsonify({'available': False, 'events': [], 'total': 0, 'page': 1,
                        'per_page': 0, 'types': [], 'centuries': []})
    try:
        q = (request.args.get('q') or '').strip()
        typ = (request.args.get('type') or '').strip()
        century = request.args.get('century', type=int)
        page = max(request.args.get('page', 1, type=int) or 1, 1)
        per_page = min(max(request.args.get('per_page', 25, type=int) or 25, 1), MAX_PER_PAGE)

        where, args = [], []
        if q:
            esc = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            where.append("(label LIKE ? ESCAPE '\\' OR place LIKE ? ESCAPE '\\')")
            args += [f'%{esc}%', f'%{esc}%']
        if typ:
            where.append('type = ?')
            args.append(typ)
        if century:
            lo, hi = century_range(century)
            where.append('date_start <= ? AND COALESCE(date_end, date_start) >= ?')
            args += [hi, lo]
        clause = ('WHERE ' + ' AND '.join(where)) if where else ''
        total = c.execute(f'SELECT COUNT(*) FROM events {clause}', args).fetchone()[0]
        rows = c.execute(
            f'''SELECT e.*,
                   (SELECT COUNT(*) FROM passages p WHERE p.event_id = e.id
                        AND COALESCE(p.llm_label, '') IN ('yes', 'mention')) AS n_passages,
                   (SELECT COUNT(*) FROM documents d WHERE d.event_id = e.id) AS n_documents,
                   (SELECT COUNT(*) FROM scholarship s WHERE s.event_id = e.id) AS n_scholarship
                FROM (SELECT * FROM events {clause}) e
                ORDER BY e.date_start, e.label LIMIT ? OFFSET ?''',
            args + [per_page, (page - 1) * per_page]).fetchall()
        events = []
        for r in rows:
            d = _event_row(r)
            d.update(n_passages=r['n_passages'], n_documents=r['n_documents'],
                     n_scholarship=r['n_scholarship'])
            events.append(d)
        types = [r[0] for r in c.execute(
            'SELECT DISTINCT type FROM events WHERE type IS NOT NULL ORDER BY type')]
        cents = sorted({century_of(r[0]) for r in c.execute(
            'SELECT date_start FROM events WHERE date_start IS NOT NULL')} - {None})
        return jsonify({'available': True, 'events': events, 'total': total, 'page': page,
                        'per_page': per_page, 'types': types, 'centuries': cents})
    finally:
        c.close()


@events_bp.route('/events/<event_id>')
def get_event(event_id):
    c = _conn()
    if c is None:
        return jsonify({'error': 'The event dossiers are not installed.'}), 404
    try:
        r = c.execute('SELECT * FROM events WHERE id = ?', (event_id,)).fetchone()
        if r is None:
            return jsonify({'error': 'No such event.'}), 404
        ev = _event_row(r)
        wt = r['wikipedia_title']
        ev.update(
            lat=r['lat'], lon=r['lon'], pleiades_id=r['pleiades_id'],
            participants=_json(r['participants'], []),
            wikipedia_title=wt, description=r['description'],
            wikipedia_url=('https://en.wikipedia.org/wiki/' + quote(wt.replace(' ', '_'))) if wt else None,
            pleiades_url=(f'https://pleiades.stoa.org/places/{quote(str(r["pleiades_id"]))}'
                          if r['pleiades_id'] else None))

        include_all = request.args.get('all') == '1'
        pcols = _columns(c, 'passages')
        rows = c.execute('SELECT * FROM passages WHERE event_id = ?', (r['id'],)).fetchall()
        passages, counts = [], {}
        for p in rows:
            label = p['llm_label'] or ''
            counts[label or 'unlabelled'] = counts.get(label or 'unlabelled', 0) + 1
            if label == 'no' and not include_all:
                continue
            given = p['language'] if 'language' in pcols else None
            lang = _language_of(p['work'], given)
            passages.append({
                'rank': p['rank'], 'work': p['work'], 'language': lang,
                'ref_start': p['ref_start'], 'ref_end': p['ref_end'], 'score': p['score'],
                'llm_label': label or None,
                'names_matched': _json(p['names_matched'], []),
                'snippet': p['snippet'],
                'reader_url': reader_url(p['work'], lang, p['ref_start']),
            })
        passages.sort(key=lambda p: (LABEL_ORDER.get(p['llm_label'], 2), p['rank'] if p['rank'] is not None else 1e9))

        dcols = _columns(c, 'documents')
        documents = []
        for d in c.execute('SELECT * FROM documents WHERE event_id = ? ORDER BY distance_km, doc_id',
                           (r['id'],)):
            lang = d['language'] if 'language' in dcols and d['language'] else 'la'
            documents.append({
                'doc_id': d['doc_id'], 'date_start': d['date_start'], 'date_end': d['date_end'],
                'place': d['place'], 'distance_km': d['distance_km'],
                'text_snippet': d['text_snippet'],
                'lat': d['lat'] if 'lat' in dcols else None,
                'lon': d['lon'] if 'lon' in dcols else None,
                'view_url': document_url(d['doc_id'], lang),
            })

        scholarship = [{'kind': s['kind'], 'title': s['title'], 'page_ref': s['page_ref'],
                        'url': s['url']}
                       for s in c.execute('SELECT * FROM scholarship WHERE event_id = ? ORDER BY kind, rowid',
                                          (r['id'],))]

        points = []
        if ev['lat'] is not None and ev['lon'] is not None:
            points.append({'kind': 'event', 'label': ev['place'] or ev['label'],
                           'lat': ev['lat'], 'lon': ev['lon'], 'n_documents': 0})
        spots = {}
        for d in documents:
            if d['lat'] is None or d['lon'] is None:
                continue
            s = spots.setdefault((d['place'], d['lat'], d['lon']),
                                 {'kind': 'findspot', 'label': d['place'], 'lat': d['lat'],
                                  'lon': d['lon'], 'n_documents': 0})
            s['n_documents'] += 1
        points += list(spots.values())

        return jsonify({'event': ev, 'passages': passages, 'passage_counts': counts,
                        'documents': documents, 'scholarship': scholarship, 'map': points})
    finally:
        c.close()
