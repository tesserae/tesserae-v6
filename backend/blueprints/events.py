"""Events: the read-only API behind the Events page.

    GET /api/events?q=&type=&century=&page=&per_page=
        the events in the dossier database, searchable by label, filterable
        by type and century (a signed number: -5 is the fifth century BCE,
        1 the first CE), paged. Also returns the types and centuries present
        so the page can offer them.
    GET /api/events/names
        every event once, compact, for the Events page's name suggestions.
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
import re
import sqlite3
from urllib.parse import quote

from flask import Blueprint, current_app, jsonify, request

from backend.logging_config import get_logger

logger = get_logger('events')
events_bp = Blueprint('events', __name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(_ROOT, 'data', 'events', 'event_dossiers.sqlite')
LABEL_ORDER = {'yes': 0, 'mention': 1}
MAX_PER_PAGE = 100
# A document whose dating span is wider than this says little about a short
# event ("450 to 401 BCE" loom weights for an event of 415 to 413).
MAX_DOCUMENT_SPAN = 50


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


DOCUMENT_TEXT_CHARS = 800


def _document_texts(documents):
    """{doc_id: text} for the documents the documents index holds, longest cut at
    DOCUMENT_TEXT_CHARS with an ellipsis (the record page has the whole text)."""
    by_lang = {}
    for d in documents:
        by_lang.setdefault(d.get('language') or 'la', []).append(d['doc_id'])
    out = {}
    try:
        from backend.documents import get_connection
    except Exception:  # noqa: BLE001
        return out
    for lang, ids in by_lang.items():
        conn = get_connection(lang)
        if conn is None:
            continue
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            try:
                rows = conn.execute(
                    f'SELECT ref, content FROM lines WHERE ref IN ({",".join("?" * len(chunk))})',  # nosec B608 -- placeholders only
                    chunk).fetchall()
            except sqlite3.Error:
                continue
            for ref, content in rows:
                t = ' '.join(str(content or '').split())
                if t:
                    out[ref] = t if len(t) <= DOCUMENT_TEXT_CHARS else t[:DOCUMENT_TEXT_CHARS].rsplit(' ', 1)[0] + ' …'
    return out


def document_url(doc_id, lang='la'):
    return f'/document?doc={quote(str(doc_id), safe="")}&lang={lang}&documents=1'


def _event_row(r):
    return {
        'id': r['id'], 'label': r['label'], 'type': r['type'],
        'date_start': r['date_start'], 'date_end': r['date_end'],
        'place': r['place'],
    }


def _scholarship(c, event_id, names=()):
    """The event's scholarship rows. A database that records the passage each
    article was found through (passage_rank, passage_ref) gives one row per
    article, with the first passage that brings it in (the lowest rank), ordered
    by that rank. Rows with scope 'span' are articles that cite within the span
    the leading passages cover but not a leading passage itself, and follow the
    others. An older database keeps its rows as they are. When the store holds
    scholarship_relevance (the gateway model's verdict on each article for this
    event), each article row carries relevance ('yes', 'partly' or 'no') and a
    one-line reason, and within each group the YES rows come first, then PARTLY,
    then NO."""
    cols = _columns(c, 'scholarship')
    verdicts = _relevance_verdicts(c, event_id)
    linked = 'passage_rank' in cols and 'passage_ref' in cols
    rows = c.execute('SELECT * FROM scholarship WHERE event_id = ? ORDER BY kind, rowid', (event_id,)).fetchall()
    out = []
    for s in rows:
        item = {'kind': s['kind'], 'title': s['title'], 'page_ref': s['page_ref'], 'url': s['url']}
        if s['kind'] == 'commentary':
            item.update(_commentary_cite_fields(s['title'], s['page_ref']))
        v = verdicts.get((s['url'] or '', s['title'] or '')) if s['kind'] == 'article' else None
        if v:
            item.update(relevance=v[0], relevance_reason=v[1])
        if linked:
            item.update(passage_rank=s['passage_rank'], passage_ref=s['passage_ref'])
            if 'scope' in cols:
                item['scope'] = s['scope'] or 'passage'
        out.append(item)
    if linked:
        out = _by_passage_rank(out, names)
    return out


_RELEVANCE_BAND = {'yes': 0, 'partly': 1, 'no': 2}


def _relevance_verdicts(c, event_id):
    """{(url, title): (verdict, reason)} from scholarship_relevance, lower-cased
    verdicts; empty when the store has no such table (an older store)."""
    if 'verdict' not in _columns(c, 'scholarship_relevance'):
        return {}
    out = {}
    for r in c.execute('SELECT url, title, verdict, reason FROM scholarship_relevance WHERE event_id = ?', (event_id,)):
        v = (r['verdict'] or '').lower()
        if v in _RELEVANCE_BAND:
            out[(r['url'] or '', r['title'] or '')] = (v, r['reason'] or '')
    return out


def _commentary_cite_fields(title, ref):
    """What the Cite control reads on a commentary note: commentator, work,
    the note's reference and the edition, taken from the held commentary the
    row's title ("W. W. How and J. Wells on herodotus.histories") names. Rows
    whose commentary is not held keep the commentator and work only."""
    who, sep, work = (title or '').rpartition(' on ')
    if not sep or not work or ' ' in work.strip():
        return {}
    from backend import scholarship
    fields = scholarship.commentary_edition_fields(commentator=who, work=work)
    out = {'commentator': who.strip(), 'work': work.strip(), 'ref_start': ref}
    out.update({k: v for k, v in fields.items() if k in ('edition', 'edition_title') and v})
    return out


# Journal apparatus the citation indexes carry as if it were an article
# (2026-10-18, the project lead on the Sicilian Expedition: "neither of
# which seems to closely pertain"). Rows with these titles are dropped.
_APPARATUS_TITLES = re.compile(
    r'^\s*(\[untitled\]|reports?\b|brief mention|volume information|front matter|back matter|'
    r'books? received|notes and news|proceedings of the|classical articles in non-classical|'
    r'summaries of (periodicals|dissertations)|index to volume|errata|corrigenda)', re.I)


def _event_words(label, place, participants):
    """Words of four letters or more from the event's label, place and
    participants, lower-cased and cut to six letters, so Syracuse matches
    Syracusan and Sicily matches Sicilian. Generic event words are left out."""
    words = set()
    for text in [label or '', place or ''] + list(participants or []):
        for w in re.findall(r"[A-Za-z\u00C0-\u024F]{4,}", str(text)):
            w = w.lower()
            if w in ('battle', 'siege', 'expedition', 'campaign', 'revolt', 'treaty', 'conspiracy'):
                continue
            words.add(w[:6])
    return words


def _title_names_event(title, words):
    low = (title or '').lower()
    return any(re.search(r'\b' + re.escape(w), low) for w in words)


def _by_passage_rank(items, names=()):
    """One row per article, ordered within its group (passage rows, then span
    rows) by three things in turn: whether the title names the event (its
    label, place or a participant), how many of the event's passages the
    article cites, and the rank of the first passage that brought it in.
    Journal apparatus titles are dropped. Commentary rows follow. Where the
    model's verdict is present it comes first within each group: YES, PARTLY, NO."""
    words = _event_words(*names) if names else set()
    best, cites = {}, {}
    for i in items:
        if i['kind'] == 'article':
            k = (i['url'] or '', i['title'] or '')
            cites[k] = cites.get(k, set()) | {i.get('passage_ref')}
            if k not in best or _rank(i) < _rank(best[k]):
                best[k] = i
    keep = []
    for i in items:
        if i['kind'] != 'article':
            keep.append(i)
            continue
        k = (i['url'] or '', i['title'] or '')
        if best[k] is not i or _APPARATUS_TITLES.match(i['title'] or ''):
            continue
        i['cites'] = len(cites[k])
        i['names_event'] = bool(words) and _title_names_event(i['title'], words)
        keep.append(i)
    order = {'article': 0, 'commentary': 1}
    # An article the model has not judged sits with PARTLY, between YES and NO.
    return sorted(keep, key=lambda i: (order.get(i['kind'], 2), i.get('scope') == 'span',
                                       _RELEVANCE_BAND.get(i.get('relevance'), 1),
                                       not i.get('names_event'), -i.get('cites', 0), _rank(i)))


def _rank(i):
    return i['passage_rank'] if i.get('passage_rank') is not None else 1e9


def _documents_naming(doc_ids, names):
    """Of `doc_ids`, those that the Mentions store records as naming any of
    `names` (the event's participants and place), by document_mentions, as
    {doc_id: set of the matched word forms}. The forms are the store's folded
    spelling (lower case, v written u), and the page uses them to highlight the
    words in the document's text (the project lead, 2026-10-20)."""
    from backend import entity_extras
    from backend.blueprints.entities import store_path
    path = store_path()
    if not doc_ids or not os.path.exists(path):
        return {}
    try:
        eids = {x for x in (entity_extras.resolve_name_to_eid(path, n) for n in names) if x is not None}
        if not eids:
            return {}
        c = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    except Exception:  # the dossier page must not depend on the Mentions store
        logger.exception('[EVENTS] the Mentions store could not be read')
        return {}
    found = {}
    try:
        wanted = list(doc_ids)
        marks = ','.join('?' * len(eids))
        for i in range(0, len(wanted), 400):
            chunk = wanted[i:i + 400]
            q = (f'SELECT DISTINCT doc_id, form FROM document_mentions WHERE eid IN ({marks}) '  # nosec B608
                 f'AND doc_id IN ({",".join("?" * len(chunk))})')  # placeholders only; values are bound
            for doc_id, form in c.execute(q, list(eids) + chunk):
                found.setdefault(doc_id, set()).add(form)
    except sqlite3.Error:
        return {}
    finally:
        c.close()
    return found


def rank_documents(documents, naming):
    """Apply the Inscriptions & Papyri rule to the documents of one event:
    leave out any whose dating span is wider than MAX_DOCUMENT_SPAN years;
    put those in `naming` (doc ids that name a participant or the place)
    first, group "names"; the rest follow, group "dated". Inside each group
    the tighter dating comes first, then the nearer findspot. A document with
    no dating is unknown: it cannot fail the rule, and it follows every dated
    document of its group."""
    kept = []
    for d in documents:
        a, b = d['date_start'], d['date_end']
        span = (b - a) if (a is not None and b is not None) else None
        if span is not None and span > MAX_DOCUMENT_SPAN:
            continue
        d['date_span'] = span
        d['group'] = 'names' if d['doc_id'] in naming else 'dated'
        kept.append(d)
    far = 1e12
    kept.sort(key=lambda d: (d['group'] != 'names', d['date_span'] is None, d['date_span'] or 0,
                             d['distance_km'] if d['distance_km'] is not None else far, d['doc_id']))
    return kept


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
        # Ordering and the empty-event filter (owner's review 2026-10-10: a
        # list that opened on 801 BCE events with nothing attached was not
        # persuasive). The default order puts the events with the most
        # attached passages and nearby documents first; `sort=date` is the
        # old chronological order. Events with neither a passage nor a
        # document are left out unless `show=all`.
        # `sort=name` is alphabetical, the Events page's default since 2026-10-20
        # (the project lead: the list should open alphabetical, like the name box,
        # and be orderable by date). The route's own default stays `evidence`
        # for the connector and older links.
        sort = (request.args.get('sort') or 'evidence').strip().lower()
        if sort not in ('evidence', 'date', 'name'):
            sort = 'evidence'
        show_all = (request.args.get('show') or '').strip().lower() == 'all'

        # Four Wikidata items carry no English label, title or description,
        # only their Q-number: nothing a reader could recognise, so the
        # list leaves them out (the detail route still answers for them).
        where, args = ["NOT (label GLOB 'Q[0-9]*')"], []
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
        clause_all = ('WHERE ' + ' AND '.join(where)) if where else ''
        total_all = c.execute(f'SELECT COUNT(*) FROM events {clause_all}', args).fetchone()[0]  # nosec B608 -- clause is fixed fragments with ? placeholders; values are bound in args
        evidence = ("(EXISTS (SELECT 1 FROM passages p WHERE p.event_id = events.id "
                    "AND COALESCE(p.llm_label, '') IN ('yes', 'mention')) "
                    "OR EXISTS (SELECT 1 FROM documents d WHERE d.event_id = events.id))")
        where_shown = where if show_all else where + [evidence]
        clause = ('WHERE ' + ' AND '.join(where_shown)) if where_shown else ''
        total = total_all if show_all else c.execute(
            f'SELECT COUNT(*) FROM events {clause}', args).fetchone()[0]  # nosec B608 -- clause is fixed fragments with ? placeholders; values are bound in args
        counts = '''SELECT e.*,
                   (SELECT COUNT(*) FROM passages p WHERE p.event_id = e.id
                        AND COALESCE(p.llm_label, '') IN ('yes', 'mention')) AS n_passages,
                   (SELECT COUNT(*) FROM documents d WHERE d.event_id = e.id) AS n_documents,
                   (SELECT COUNT(*) FROM scholarship s WHERE s.event_id = e.id) AS n_scholarship
                FROM (SELECT * FROM events '''
        order = {'date': 'ORDER BY e.date_start, e.label COLLATE NOCASE',
                 'name': 'ORDER BY e.label COLLATE NOCASE, e.date_start'}.get(
            sort, 'ORDER BY (n_passages + n_documents) DESC, n_passages DESC, e.date_start, e.label')
        sql = counts + clause + ') e ' + order + ' LIMIT ? OFFSET ?'  # nosec B608 -- clause and order are fixed fragments with ? placeholders; values are bound
        rows = c.execute(sql, args + [per_page, (page - 1) * per_page]).fetchall()
        events = []
        for r in rows:
            d = _event_row(r)
            d.update(n_passages=r['n_passages'], n_documents=r['n_documents'],
                     n_scholarship=r['n_scholarship'])
            events.append(d)
        # Type counts follow the empty-event setting, not the other filters,
        # so the Type menu can say how many of each kind there are to see.
        type_clause = '' if show_all else 'WHERE ' + evidence
        type_rows = c.execute(
            f'SELECT type, COUNT(*) FROM events {type_clause} GROUP BY type ORDER BY type').fetchall()  # nosec B608 -- fixed fragment
        types = [r[0] for r in type_rows if r[0] is not None]
        type_counts = {r[0]: r[1] for r in type_rows if r[0] is not None}
        cents = sorted({century_of(r[0]) for r in c.execute(
            'SELECT date_start FROM events WHERE date_start IS NOT NULL')} - {None})
        return jsonify({'available': True, 'events': events, 'total': total, 'total_all': total_all,
                        'sort': sort, 'show': 'all' if show_all else 'evidence',
                        'page': page, 'per_page': per_page, 'types': types,
                        'type_counts': type_counts, 'centuries': cents})
    finally:
        c.close()


_NAMES_CACHE = {}


@events_bp.route('/events/names')
def event_names():
    """Every listed event once, in the list's own order (most passages and
    documents first), for the suggestion box under the Events name field.
    Events with no evidence are included (n_passages and n_documents are 0).
    Kept in the process after the first call: the store changes only at an
    install, which touches the WSGI file and restarts the workers."""
    path = db_path()
    body = _NAMES_CACHE.get(path)
    if body is None:
        c = _conn()
        if c is None:
            body = '[]'
        else:
            try:
                rows = c.execute(
                    """SELECT e.id, e.label, e.place, e.date_start, e.date_end, e.type,
                       (SELECT COUNT(*) FROM passages p WHERE p.event_id = e.id
                            AND COALESCE(p.llm_label, '') IN ('yes', 'mention')) AS n_passages,
                       (SELECT COUNT(*) FROM documents d WHERE d.event_id = e.id) AS n_documents
                       FROM events e WHERE NOT (e.label GLOB 'Q[0-9]*')
                       ORDER BY (n_passages + n_documents) DESC, n_passages DESC, e.date_start, e.label"""
                ).fetchall()
            finally:
                c.close()
            body = json.dumps([
                {'id': r['id'], 'label': r['label'], 'place': r['place'],
                 'year_start': r['date_start'], 'year_end': r['date_end'],
                 'type': r['type'], 'n_passages': r['n_passages'],
                 'n_documents': r['n_documents']} for r in rows], separators=(',', ':'))
            _NAMES_CACHE[path] = body
    resp = current_app.response_class(body, mimetype='application/json')
    resp.headers['Cache-Control'] = 'public, max-age=3600'
    return resp


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

        ecols = set(r.keys())
        if 'summary' in ecols and r['summary']:
            ev.update(summary=r['summary'], summary_source=r['summary_source'],
                      summary_url=r['summary_url'], summary_licence=r['summary_licence'])

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
                'language': lang,
                'lat': d['lat'] if 'lat' in dcols else None,
                'lon': d['lon'] if 'lon' in dcols else None,
                'view_url': document_url(d['doc_id'], lang),
            })

        n_stored = len(documents)
        naming = _documents_naming([d['doc_id'] for d in documents],
                                   list(ev['participants']) + ([ev['place']] if ev['place'] else []))
        documents = rank_documents(documents, naming)
        document_counts = {'names': sum(1 for d in documents if d['group'] == 'names'),
                           'dated': sum(1 for d in documents if d['group'] == 'dated'),
                           'left_out': n_stored - len(documents)}

        # The edition reference and the source names, so a card can lead with
        # "CIL 09, 03200" rather than the internal id (a "merged:" id marks a
        # stone both EDH and EDR record). Best effort: no metadata, no change.
        try:
            from backend.documents import bulk_meta
            metas = bulk_meta([d['doc_id'] for d in documents]) if documents else {}
        except Exception:  # the dossier page must not depend on metadata.db
            metas = {}
        for d in documents:
            m = metas.get(d['doc_id']) or {}
            credit = m.get('credit') or {}
            d['edition'] = credit.get('principal_edition')
            d['sources'] = [x for x in (credit.get('source_name'), credit.get('source_name_secondary')) if x]
            d['text_type'] = m.get('text_type_label')

        # The text of each document, from the documents index (the project lead,
        # 2026-10-20: "We get all the meta information about the inscription.
        # Everything but the text itself."). One row per document, keyed by its id.
        # Best effort: without the index the cards show their record line as before.
        texts = _document_texts(documents)
        for d in documents:
            d['text'] = texts.get(d['doc_id'])
            forms = naming.get(d['doc_id']) if isinstance(naming, dict) else None
            d['matched_forms'] = sorted(f for f in (forms or ()) if f)

        try:
            participants = json.loads(r['participants']) if 'participants' in r.keys() and r['participants'] else []
        except (TypeError, ValueError):
            participants = []
        scholarship = _scholarship(c, r['id'], (r['label'], r['place'], participants))

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
                        'documents': documents, 'document_counts': document_counts,
                        'scholarship': scholarship, 'map': points})
    finally:
        c.close()
