"""Entity mentions: "where else is this place, person or god named?" (stage 2, trial).

Read-only routes over the entity store built by scripts/entity_model_pass.py (backend/
entity_index.py holds the schema). The store path comes from TESSERAE_ENTITY_STORE and
defaults to data/entity_index/entities.sqlite. Without the file every route answers 503
with a JSON error, so the page can say so.

    GET /api/entities/search?q=                   up to 50 entities whose label or a name form
                                                  starts with or contains q
    GET /api/entities/<id>                        one entity with its mention counts by work
    GET /api/entities/<id>/mentions?work=&lang=&offset=&limit=
                                                  the mentions as rows (one row per matched line),
                                                  with the window text
    GET /api/entities/<id>/documents?lang=&offset=&limit=
                                                  inscriptions and papyri that name the entity
                                                  (503 unless the documents collection is on)

Stage 2b: the search also lists the corpus's own capitalized names (source 'names'), an entity
view lists the corpus names that belong to it, a search with no match offers near spellings, and
counts are counts of lines, not windows (two overlapping windows that hold one line are one).

The page behind these routes is a trial (?entities=1). The connector tools stay off: the routes
are listed as site only in backend/blueprints/mcp_manifest.py.
"""
import json
import os
import sqlite3
import threading

from flask import Blueprint, jsonify, request

from backend import entity_extras as extras
from backend import entity_index as ei
from backend import entity_promote as extras_promote
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

_local = threading.local()
_cache = {}
_cache_lock = threading.Lock()


def store_path():
    return os.environ.get('TESSERAE_ENTITY_STORE') or DEFAULT_STORE


def _conn(path):
    """A read-only connection for this thread (an sqlite3 connection cannot be shared).
    Keyed by the file's identity as well as its path, so a store swapped in by a rename is
    reopened on the next request instead of being read through the old file handle."""
    st = os.stat(path)
    key = (path, st.st_ino, st.st_mtime_ns, st.st_size)
    c = getattr(_local, 'conn', None)
    if c is None or getattr(_local, 'key', None) != key:
        if c is not None:
            try:
                c.close()
            except sqlite3.Error:
                pass
        c = sqlite3.connect(f'file:{path}?mode=ro', uri=True, check_same_thread=False)
        _local.conn, _local.key = c, key
    return c


def _unavailable():
    resp = jsonify({'error': 'The mentions store is not installed on this server.', 'available': False})
    resp.status_code = 503
    return resp


def _catalog(path):
    """Every list entity and every corpus name, cached until the store file changes: id, label,
    type, identifiers, name forms, mention counts by language (lines), shared-name facts, and the
    corpus names that belong to each list entity. Read from the table entity_catalog (one select)
    when the store has it, else built in memory from the whole store (several seconds)."""
    st = os.stat(path)
    key = (path, st.st_mtime_ns, st.st_size)
    with _cache_lock:
        hit = _cache.get('catalog')
        if hit and hit[0] == key:
            return hit[1]
    c = _conn(path)
    has_table = c.execute("select 1 from sqlite_master where name = 'entity_catalog'").fetchone() is not None
    if has_table:
        rows = [json.loads(d) for (d,) in c.execute('select data from entity_catalog')]
    else:
        rows = extras.build_catalog(c)
    ents = {r['eid']: r for r in rows if r['source'] in ('list', 'promoted')}
    names = {r['eid']: r for r in rows if r['source'] == 'corpus'}
    name_index = extras.NameIndex([(n['eid'], {n['folded_label']} | set(n['forms'])) for n in names.values()])
    labels = [(e, {e['folded_label'], e['label_key']} | set(e['label_key'].split())) for e in ents.values()]
    try:
        has_docs = c.execute("select 1 from sqlite_master where name = 'document_mentions'").fetchone() is not None
    except sqlite3.Error:
        has_docs = False
    out = {'by_eid': ents, 'names': names, 'name_index': name_index, 'labels': labels,
           'has_documents_table': has_docs, 'stored_catalog': has_table,
           'has_lines': 'line_ref' in {r[1] for r in c.execute('pragma table_info(mention_rows)')},
           'by_id': {e['id']: e for e in ents.values()}}
    for n in names.values():
        out['by_id'].setdefault(n['id'], n)
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
    label = e.get('display_label') or e['label']
    out = {'id': e['id'], 'label': label, 'type': e['type'], 'source': e['source'],
           'display_label': label, 'display_label_la': e.get('display_label_la'),
           'display_label_grc': e.get('display_label_grc'), 'description': e.get('description'),
           'identifiers': ids, 'mention_unit': 'lines',
           'mention_counts': counts, 'mentions_total': e['total'],
           'label_shared': bool(e['shared_label_with']) or e['homonym_mentions'] > 0,
           'label_shared_with': e['shared_label_with'][:5],
           'shared_name_mentions': e['homonym_mentions']}
    if e['source'] == 'promoted':
        out['provenance'] = extras_promote.PROVENANCE
    return out


def _rank(e, f, raw):
    """Lower is better. None when the entity does not match. A search name (stage 3b: the usual English
    name and other spellings a reader might type) ranks like a label, 0 for equality and 1 for a prefix.
    The first search name is the usual English name and ranks exactly like a label. The other search
    names rank half a step behind, so that Rhodes finds the island (usual name Rhodes) ahead of the
    Rhodians (who are also called Rhodes), however many more lines the Rhodians have."""
    label = e['folded_label']
    key = e['label_key']
    names = e.get('search_names') or ()
    usual = names[:1]
    if label == f or key == f or f in usual:
        return 0
    if f in names:
        return 0.5
    if label.startswith(f) or key.startswith(f) or any(x.startswith(f) for x in usual):
        return 1
    if any(x.startswith(f) for x in names):
        return 1.5
    if any(x == f for x in e['forms']):
        return 2
    if any(x.startswith(f) for x in e['forms']):
        return 3
    if f in label or f in key:
        return 4
    if any(f in x for x in e['forms']):
        return 5
    return None


def _edit_distance(a, b, limit=2):
    """Levenshtein distance, or limit + 1 when it exceeds `limit`."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def _suggestions(cat, f):
    """Up to five list labels within an edit distance of two of the folded query."""
    if len(f) < 3:
        return []
    found = {}
    for e, strings in cat['labels']:
        best = min((_edit_distance(f, s) for s in strings if s), default=3)
        if best <= 2:
            found[e['eid']] = (best, -e['total'], e['label'], e)
    top = sorted(found.values(), key=lambda x: x[:3])[:5]
    return [{'id': t[3]['id'], 'label': t[3]['label'], 'type': t[3]['type'], 'distance': t[0]} for t in top]


NEAR_LIMIT = 5
NEAR_MIN_LETTERS = 5      # a shorter query is too short for a near spelling to mean anything


def _near_spellings(cat, f, hits, name_hits):
    """List and promoted entities within an edit distance of the folded query, offered under
    "Near spellings" in two cases: the exact and prefix matches are only corpus names (or there are
    none), or the best exact or prefix match has fewer lines than the near entity. The search names
    count as spellings of the entity, so a reader who types Rhodes finds Rhodos. Fix pass: only for a
    query of five letters or more, at distance one for five or six letters and two for seven or more."""
    if len(f) < NEAR_MIN_LETTERS:
        return []
    limit = 1 if len(f) <= 6 else 2
    strong_ents = {h[3]['eid'] for h in hits if h[0] < 2}
    best_total = max([h[3]['total'] for h in hits if h[0] < 2] + [h[3]['total'] for h in name_hits if h[0] < 2],
                     default=-1)
    found = {}
    for e, strings in cat['labels']:
        if e['eid'] in strong_ents or e['total'] <= 0:
            continue
        if strong_ents and e['total'] <= best_total:
            continue
        cands = set(strings) | set(e.get('search_names') or ())
        best = min((_edit_distance(f, x, limit) for x in cands if x), default=limit + 1)
        if best <= limit:
            found[e['eid']] = (best, -e['total'], e['label'], e)
    top = sorted(found.values(), key=lambda x: x[:3])[:NEAR_LIMIT]
    out = []
    for dist, _t, _l, e in top:
        row = _public(e)
        row['distance'] = dist
        out.append(row)
    return out


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
    name_hits = []
    for n in cat['names'].values():
        if n['duplicate'] or n['total'] == 0:
            continue
        r = _rank(n, f, q)
        if r is not None:
            name_hits.append((r, -n['total'], n['label'], n))
    name_hits.sort(key=lambda x: x[:3])
    results = [_public(h[3]) for h in hits[:SEARCH_LIMIT]]
    results += [_public(h[3]) for h in name_hits[:max(0, SEARCH_LIMIT - len(results))]]
    out = {'q': q, 'available': True, 'total': len(hits) + len(name_hits), 'results': results,
           'list_total': len(hits), 'corpus_total': len(name_hits)}
    if not results:
        out['suggestions'] = _suggestions(cat, f)
    else:
        near = _near_spellings(cat, f, hits, name_hits)
        if near:
            out['near_spellings'] = near
    return jsonify(out)


def _naming(work):
    n = passage_index._naming(work) or {}
    return {'title': n.get('title') or '', 'author': n.get('author') or '',
            'display_name': n.get('display_name') or '',
            'restricted': bool(n.get('restricted')), 'credit': n.get('credit')}


def _group_key(cat):
    return extras.LINE_GROUP_SQL if cat['has_lines'] else "'#' || m.wid"


def _corpus_names_of(cat, e):
    """The corpus names that belong to a list entity, with their line counts."""
    return e.get('corpus_names', []) if e['source'] in ('list', 'promoted') else []


def _document_counts(path, e):
    import backend.documents as docs
    if not docs.enabled():
        return {}
    try:
        rows = _conn(path).execute(
            'select language, count(*) from document_mentions where eid = ? group by language', (e['eid'],)).fetchall()
    except sqlite3.Error:
        return {}
    return {lg: n for lg, n in rows}


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
            'select work, language, count(*) c from (select distinct w.work work, w.language language, '  # nosec B608
            f'{_group_key(cat)} k from mention_rows m join windows w on w.wid = m.wid where m.eid = ?) '
            'group by work, language order by c desc, work', (e['eid'],)).fetchall()
        corpus_names = _corpus_names_of(cat, e)
        doc_counts = _document_counts(path, e) if cat['has_documents_table'] else {}
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
    out['corpus_names'] = corpus_names
    out['document_counts'] = doc_counts
    out['available'] = True
    return jsonify(out)


def _int(name, default, lo, hi):
    try:
        return max(lo, min(int(request.args.get(name, default)), hi))
    except (TypeError, ValueError):
        return default


def _line_ords(work, refs):
    """{ref: order of that line in the work} from the passage text store, for the refs it knows."""
    c = window_texts._conn()
    out = {}
    if c is None:
        return out
    try:
        for ref in {r for r in refs if r}:
            row = c.execute('select ord from lines where work = ? and ref = ? limit 1', (work, ref)).fetchone()
            if row:
                out[ref] = row[0]
    except sqlite3.Error:
        return {}
    return out


def _best_window(work, members, line_ref):
    """Of the windows that hold one matched line, the one whose range centers best on the line.
    members: [(wid, window_id, ref_start, ref_end, form, homonym)]. The earliest window when the
    line orders are unknown."""
    if len(members) == 1 or not line_ref:
        return members[0]
    ords = _line_ords(work, [line_ref] + [m[2] for m in members] + [m[3] for m in members])
    if line_ref not in ords:
        return members[0]
    best, best_d = members[0], None
    for m in members:
        if m[2] in ords and m[3] in ords:
            d = abs((ords[m[2]] + ords[m[3]]) / 2.0 - ords[line_ref])
            if best_d is None or d < best_d:
                best, best_d = m, d
    return best


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
        key = _group_key(cat)
        where, args = 'm.eid = ?', [e['eid']]
        if work:
            where += ' and w.work = ?'
            args.append(work[:-5] if work.endswith('.tess') else work)
        if lang:
            where += ' and w.language = ?'
            args.append(lang)
        total = c.execute(f'select count(*) from (select 1 from mention_rows m join windows w on w.wid = m.wid '  # nosec B608
                          f'where {where} group by w.work, {key})', args).fetchone()[0]
        windows_total = c.execute(f'select count(*) from mention_rows m join windows w on w.wid = m.wid where {where}',  # nosec B608
                                  args).fetchone()[0]
        groups = c.execute(
            f'select w.work, {key} k, min(m.wid) from mention_rows m join windows w on w.wid = m.wid '  # nosec B608
            f'where {where} group by w.work, k order by w.work, min(m.wid) limit ? offset ?',
            args + [limit, offset]).fetchall()
        chosen = []
        for gwork, k, first in groups:
            members = c.execute(
                'select m.wid, w.window_id, w.ref_start, w.ref_end, m.form, m.homonym, m.wid, w.language, '  # nosec B608
                f'{"m.line_ref" if cat["has_lines"] else "null"} from mention_rows m join windows w on w.wid = m.wid '
                f'where m.eid = ? and w.work = ? and {key} = ? order by m.wid', (e['eid'], gwork, k)).fetchall()
            line_ref = members[0][8]
            pick = _best_window(gwork, [m[:6] for m in members], line_ref)
            language = next(m[7] for m in members if m[0] == pick[0])
            chosen.append((gwork, pick, language, line_ref, len(members)))
        shared = {}
        flagged = [r[1][0] for r in chosen if r[1][5]]
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
    texts = window_texts.texts_for([r[1][1] for r in chosen])
    names = {}
    out_rows = []
    for w, (wid, window_id, rs, re_, form, hom), language, line_ref, merged in chosen:
        if w not in names:
            names[w] = _naming(w)
        nm = names[w]
        others = []
        if hom:
            others = shared.get((wid, ei.fold(form))) or shared.get((wid, None)) or []
        wloc = passage_index._short_locus_fields(w, rs, re_)
        lloc = passage_index._short_locus_fields(w, line_ref, line_ref) if line_ref else wloc
        row = {'window_id': window_id, 'work': w, 'title': nm['title'], 'author': nm['author'],
               'language': language, 'ref_start': rs, 'ref_end': re_,
               'locus': lloc.get('locus', '') or wloc.get('locus', ''), 'window_locus': wloc.get('locus', ''),
               'line_ref': line_ref, 'windows_merged': merged,
               'text': texts.get(window_id), 'token': form,
               'shared_with': sorted(set(others))}
        if nm['restricted']:
            row['restricted'] = True
            row['credit'] = nm['credit']
        out_rows.append(row)
    return jsonify({'entity': _public(e), 'available': True, 'total': total, 'windows_total': windows_total,
                    'unit': 'lines', 'offset': offset, 'limit': limit,
                    'work': work or None, 'lang': lang or None, 'results': out_rows})


_UNKNOWN = ('unknown', 'unbekannt', '?', 'n/a', 'none')


def _doc_text_and_line(language, doc_id, form):
    """The first line of the document that holds the matched token (else its first line), as
    (line ref, line text). Read from the documents index for this response only."""
    import backend.documents as docs
    d = docs.get_document_lines(language, doc_id)
    if not d or not d['lines']:
        return None, None
    for ln in d['lines']:
        if form in {ei.fold(t) for t in ln.get('tokens') or []}:
            return ln['ref'], ln['text']
    return d['lines'][0]['ref'], d['lines'][0]['text']


@entities_bp.route('/entities/<entity_id>/documents')
def documents_of(entity_id):
    import backend.documents as docs
    path = store_path()
    if not os.path.exists(path):
        return _unavailable()
    if not docs.enabled():
        resp = jsonify({'error': 'The inscriptions and papyri are not available on this server.',
                        'available': False})
        resp.status_code = 503
        return resp
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
        if not cat['has_documents_table']:
            resp = jsonify({'error': 'The mentions store has no inscriptions and papyri table.', 'available': False})
            resp.status_code = 503
            return resp
        c = _conn(path)
        where, args = 'eid = ?', [e['eid']]
        if lang:
            where += ' and language = ?'
            args.append(lang)
        total = c.execute(f'select count(*) from document_mentions where {where}', args).fetchone()[0]  # nosec B608
        rows = c.execute(
            f'select doc_id, language, form, kind, adjective from document_mentions where {where} '  # nosec B608
            "order by case kind when 'form' then 0 when 'corpus_name' then 1 else 2 end, language, doc_id "
            'limit ? offset ?', args + [limit, offset]).fetchall()
    except sqlite3.Error as ex:
        logger.exception('[ENTITIES] store unreadable')
        return jsonify({'error': f'The mentions store could not be read: {ex}', 'available': False}), 503
    metas = docs.bulk_meta([r[0] for r in rows])

    def place(v):
        return None if docs.is_unknown_place(v) else docs.translate_label(v)

    out_rows = []
    for doc_id, language, form, kind, adj in rows:
        m = metas.get(doc_id) or {}
        ref, text = _doc_text_and_line(language, doc_id, form)
        labels = [docs.translate_label(m.get(k)) for k in ('text_type_label', 'object_type_label', 'material_label')]
        out_rows.append({
            'doc_id': doc_id, 'language': language, 'locus': ref, 'text': text, 'matched_form': form,
            'match_kind': kind, 'adjective': bool(adj), 'credit': m.get('credit'),
            'date_not_before': m.get('date_not_before'), 'date_not_after': m.get('date_not_after'),
            'ancient_place': place(m.get('ancient_place')), 'modern_place': place(m.get('modern_place')),
            'region': docs.translate_label(m.get('region')),
            'text_type_label': labels[0], 'object_type_label': labels[1], 'material_label': labels[2],
            'source': m.get('source')})
    return jsonify({'entity': _public(e), 'available': True, 'total': total, 'offset': offset, 'limit': limit,
                    'lang': lang or None, 'results': out_rows})
