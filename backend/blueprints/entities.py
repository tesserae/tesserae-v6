"""Entity mentions: "where else is this place, person or god named?" (stage 2, trial).

Read-only routes over the entity store built by scripts/entity_model_pass.py (backend/
entity_index.py holds the schema). The store path comes from TESSERAE_ENTITY_STORE and
defaults to data/entity_index/entities.sqlite. Without the file every route answers 503
with a JSON error, so the page can say so.

    GET /api/entities/search?q=                   up to 50 entities whose label or a name form
                                                  starts with or contains q
    GET /api/entities/<id>                        one entity with its mention counts by work
    GET /api/entities/<id>/mentions?work=&lang=&offset=&limit=
                                                  the mentions as rows, with the window text

The page behind these routes is a trial (?entities=1). The connector tools stay off: the routes
are listed as site only in backend/blueprints/mcp_manifest.py.
"""
import collections
import json
import os
import sqlite3
import threading

from flask import Blueprint, jsonify, request

from backend import entity_index as ei
from backend import passage_index
from backend import window_texts
from backend.logging_config import get_logger

logger = get_logger('blueprints.entities')
entities_bp = Blueprint('entities', __name__)

DEFAULT_STORE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             'data', 'entity_index', 'entities.sqlite')
SEARCH_LIMIT = 50
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
LANG_ORDER = ('la', 'grc', 'en')
_TYPE_OUT = {'place': 'place', 'person': 'person', 'deity': 'deity'}

_local = threading.local()
_cache = {}
_cache_lock = threading.Lock()


def store_path():
    return os.environ.get('TESSERAE_ENTITY_STORE') or DEFAULT_STORE


def _conn(path):
    """A read-only connection for this thread (an sqlite3 connection cannot be shared)."""
    c = getattr(_local, 'conn', None)
    if c is None or getattr(_local, 'path', None) != path:
        c = sqlite3.connect(f'file:{path}?mode=ro', uri=True, check_same_thread=False)
        _local.conn, _local.path = c, path
    return c


def _unavailable():
    resp = jsonify({'error': 'The mentions store is not installed on this server.', 'available': False})
    resp.status_code = 503
    return resp


def _type_out(t):
    return _TYPE_OUT.get(t, 'other')


def _catalog(path):
    """Every list entity, cached until the store file changes: id, label, type, identifiers,
    name forms, mention counts by language, shared-name facts."""
    st = os.stat(path)
    key = (path, st.st_mtime_ns, st.st_size)
    with _cache_lock:
        hit = _cache.get('catalog')
        if hit and hit[0] == key:
            return hit[1]
    c = _conn(path)
    ents = {}
    for eid, entity_id, typ, label, pid, cands, group in c.execute(
            "select eid, entity_id, type, label, pleiades_id, pleiades_candidates, homonym_group "
            "from entities where source = 'list'"):
        try:
            pl = json.loads(cands) if cands else ([pid] if pid else [])
        except ValueError:
            pl = [pid] if pid else []
        ents[eid] = {'eid': eid, 'id': entity_id, 'label': label, 'type': _type_out(typ), 'list_type': typ,
                     'pleiades': [str(x) for x in pl], 'forms': [], 'merged_ids': [],
                     'counts': {}, 'label_key': ei.label_key(label), 'homonym_mentions': 0}
    for eid, form in c.execute("select eid, form from variants where source = 'list'"):
        if eid in ents:
            ents[eid]['forms'].append(form)
    for eid, alias in c.execute("select eid, alias_id from entity_aliases"):
        if eid in ents:
            ents[eid]['merged_ids'].append(alias)
    for eid, lang, n, hom in c.execute(
            "select m.eid, w.language, count(*), sum(m.homonym) from mention_rows m "
            "join windows w on w.wid = m.wid group by m.eid, w.language"):
        if eid in ents:
            ents[eid]['counts'][lang] = n
            ents[eid]['homonym_mentions'] += hom or 0
    by_key = collections.defaultdict(list)
    for e in ents.values():
        if e['label_key']:
            by_key[e['label_key']].append(e)
    for e in ents.values():
        others = [o['label'] for o in by_key.get(e['label_key'], ()) if o is not e]
        e['shared_label_with'] = others
        e['total'] = sum(e['counts'].values())
        e['folded_label'] = ei.fold(e['label'])
    out = {'by_eid': ents, 'by_id': {e['id']: e for e in ents.values()}}
    for e in ents.values():
        for a in e['merged_ids']:
            out['by_id'].setdefault(a, e)
    with _cache_lock:
        _cache['catalog'] = (key, out)
    return out


def _public(e):
    counts = {lg: e['counts'][lg] for lg in LANG_ORDER if lg in e['counts']}
    counts.update({lg: n for lg, n in e['counts'].items() if lg not in counts})
    ids = {}
    if e['pleiades']:
        ids['pleiades'] = e['pleiades']
    if e['merged_ids']:
        ids['also_listed_as'] = e['merged_ids']
    return {'id': e['id'], 'label': e['label'], 'type': e['type'], 'identifiers': ids,
            'mention_counts': counts, 'mentions_total': e['total'],
            'label_shared': bool(e['shared_label_with']) or e['homonym_mentions'] > 0,
            'label_shared_with': e['shared_label_with'][:5],
            'shared_name_mentions': e['homonym_mentions']}


def _rank(e, f, raw):
    """Lower is better. None when the entity does not match."""
    label = e['folded_label']
    key = e['label_key']
    if label == f or key == f:
        return 0
    if label.startswith(f) or key.startswith(f):
        return 1
    if any(x == f for x in e['forms']):
        return 2
    if any(x.startswith(f) for x in e['forms']):
        return 3
    if f in label or f in key:
        return 4
    if any(f in x for x in e['forms']):
        return 5
    return None


@entities_bp.route('/entities/search')
def search():
    path = store_path()
    if not os.path.exists(path):
        return _unavailable()
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({'q': q, 'results': [], 'total': 0, 'available': True})
    f = ei.fold(q)
    try:
        cat = _catalog(path)
    except sqlite3.Error as e:
        logger.exception('[ENTITIES] store unreadable')
        return jsonify({'error': f'The mentions store could not be read: {e}', 'available': False}), 503
    hits = []
    for e in cat['by_eid'].values():
        r = _rank(e, f, q)
        if r is not None:
            hits.append((r, -e['total'], e['label'], e))
    hits.sort(key=lambda x: x[:3])
    return jsonify({'q': q, 'available': True, 'total': len(hits),
                    'results': [_public(h[3]) for h in hits[:SEARCH_LIMIT]]})


def _naming(work):
    n = passage_index._naming(work) or {}
    return {'title': n.get('title') or '', 'author': n.get('author') or '',
            'display_name': n.get('display_name') or '',
            'restricted': bool(n.get('restricted')), 'credit': n.get('credit')}


@entities_bp.route('/entities/<entity_id>')
def entity(entity_id):
    path = store_path()
    if not os.path.exists(path):
        return _unavailable()
    try:
        cat = _catalog(path)
        e = cat['by_id'].get(entity_id)
        if e is None:
            resp = jsonify({'error': f'No entity {entity_id}.', 'available': True})
            resp.status_code = 404
            return resp
        rows = _conn(path).execute(
            "select w.work, w.language, count(*) c from mention_rows m join windows w on w.wid = m.wid "
            "where m.eid = ? group by w.work, w.language order by c desc, w.work", (e['eid'],)).fetchall()
    except sqlite3.Error as ex:
        logger.exception('[ENTITIES] store unreadable')
        return jsonify({'error': f'The mentions store could not be read: {ex}', 'available': False}), 503
    works = []
    for work, lang, n in rows:
        nm = _naming(work)
        works.append({'work': work, 'title': nm['title'], 'author': nm['author'],
                      'display_name': nm['display_name'], 'language': lang, 'count': n})
    out = _public(e)
    out['works'] = works
    out['available'] = True
    return jsonify(out)


def _int(name, default, lo, hi):
    try:
        return max(lo, min(int(request.args.get(name, default)), hi))
    except (TypeError, ValueError):
        return default


@entities_bp.route('/entities/<entity_id>/mentions')
def mentions(entity_id):
    path = store_path()
    if not os.path.exists(path):
        return _unavailable()
    work = (request.args.get('work') or '').strip()
    lang = (request.args.get('lang') or '').strip()
    offset = _int('offset', 0, 0, 10 ** 7)
    limit = _int('limit', DEFAULT_LIMIT, 1, MAX_LIMIT)
    try:
        cat = _catalog(path)
        e = cat['by_id'].get(entity_id)
        if e is None:
            resp = jsonify({'error': f'No entity {entity_id}.', 'available': True})
            resp.status_code = 404
            return resp
        c = _conn(path)
        where, args = 'm.eid = ?', [e['eid']]
        if work:
            where += ' and w.work = ?'
            args.append(work[:-5] if work.endswith('.tess') else work)
        if lang:
            where += ' and w.language = ?'
            args.append(lang)
        total = c.execute(f'select count(*) from mention_rows m join windows w on w.wid = m.wid where {where}',  # nosec B608
                          args).fetchone()[0]
        rows = c.execute(
            'select m.wid, w.window_id, w.work, w.ref_start, w.ref_end, w.language, m.form, m.homonym '
            f'from mention_rows m join windows w on w.wid = m.wid where {where} '  # nosec B608
            'order by w.work, m.wid limit ? offset ?', args + [limit, offset]).fetchall()
        shared = {}
        flagged = [r[0] for r in rows if r[7]]
        for i in range(0, len(flagged), 400):
            part = flagged[i:i + 400]
            marks = ','.join('?' * len(part))
            for wid, form, label in c.execute(
                    'select m.wid, m.form, x.label from mention_rows m join entities x on x.eid = m.eid '
                    f'where m.homonym = 1 and m.eid != ? and m.wid in ({marks})', [e['eid']] + part):  # nosec B608
                shared.setdefault((wid, ei.fold(form)), []).append(label)
                shared.setdefault((wid, None), []).append(label)
    except sqlite3.Error as ex:
        logger.exception('[ENTITIES] store unreadable')
        return jsonify({'error': f'The mentions store could not be read: {ex}', 'available': False}), 503
    texts = window_texts.texts_for([r[1] for r in rows])
    names = {}
    out_rows = []
    for wid, window_id, w, rs, re_, language, form, hom in rows:
        if w not in names:
            names[w] = _naming(w)
        nm = names[w]
        others = []
        if hom:
            others = shared.get((wid, ei.fold(form))) or shared.get((wid, None)) or []
        loc = passage_index._short_locus_fields(w, rs, re_)
        row = {'window_id': window_id, 'work': w, 'title': nm['title'], 'author': nm['author'],
               'language': language, 'ref_start': rs, 'ref_end': re_, 'locus': loc.get('locus', ''),
               'text': texts.get(window_id), 'token': form,
               'shared_with': sorted(set(others))}
        if nm['restricted']:
            row['restricted'] = True
            row['credit'] = nm['credit']
        out_rows.append(row)
    return jsonify({'entity': _public(e), 'available': True, 'total': total, 'offset': offset, 'limit': limit,
                    'work': work or None, 'lang': lang or None, 'results': out_rows})
