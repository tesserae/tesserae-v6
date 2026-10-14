"""Coins: the read-only API behind the Coins page.

    GET /api/coins?q=&authority=&mint=&denomination=&material=&source=
                  &date_from=&date_to=&sort=relevance|date&page=&per_page=
        coin types (Roman and Greek), searchable over legends and descriptions,
        filterable, paged, with facet counts for the filters in force.
    GET /api/coins/facets
        every value of each filter with its count, the date span, and the
        count per source.
    GET /api/coins/<id>
        one coin type.
    GET /api/coins/for-passage?work=&lang=&ref=&ref_end=
        the Reader's Coins tab: related imagery (the five coin descriptions
        nearest the gist of the passage window) and name links (a person named
        on a coin and in the passage). See backend/coins_passage.py.
    GET /api/coins/theme?q=
        the coin descriptions nearest a free-text query, for Theme Search.

`person=<name>` on the list route keeps the types that name that person as
authority or obverse portrait (the target of a name link).

The data is a SQLite file written offline by scripts/coins/build_coins_db.py;
the routes only read it. The path comes from TESSERAE_COINS_DB, default
data/coins/coins.sqlite. With no file the list route answers available=false
and the detail route 404, as the Events routes do.

Dates are signed years (-25 is 25 BCE). The type records come from OCRE and
CRRO (Roman) and seven Greek catalogues (Corpus Nummorum, Seleucid, PELLA,
Ptolemaic, BIGR, IRIS, Levantine), published through nomisma.org under
ODbL or a Creative Commons non-commercial licence (CREDITS below). Images live
on museum specimen records, so the page links to the type's own page and stores
none.
"""
import os
import re
import sqlite3
import unicodedata
from urllib.parse import quote

from flask import Blueprint, jsonify, request

from backend import coins_passage
from backend.logging_config import get_logger

logger = get_logger('coins')
coins_bp = Blueprint('coins', __name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(_ROOT, 'data', 'coins', 'coins.sqlite')
MAX_PER_PAGE = 100
FACET_FIELDS = ('authority', 'mint', 'denomination', 'material', 'source')
FACET_LIMIT = 60

CREDITS = {
    'ocre': 'Type record: OCRE (American Numismatic Society), ODbL',
    'crro': 'Type record: CRRO (American Numismatic Society), ODbL',
    'cn': 'Type record: Corpus Nummorum, CC BY-NC-SA 3.0',
    'sco': 'Type record: SCO (American Numismatic Society), ODbL',
    'pella': 'Type record: PELLA (American Numismatic Society), ODbL',
    'pco': 'Type record: PCO (American Numismatic Society), ODbL',
    'bigr': 'Type record: BIGR (American Numismatic Society), ODbL',
    'iris': 'Type record: IRIS (University of Oxford), ODbL',
    'lco': 'Type record: LCO (American Numismatic Society), ODbL',
}
LIST_COLUMNS = ('id, source, uri, title, authority, issuer, portrait, mint, mint_pleiades_id, '
                'region, denomination, material, date_start, date_end, obverse_legend, '
                'reverse_legend, obverse_description, reverse_description')


def db_path():
    return os.environ.get('TESSERAE_COINS_DB') or DEFAULT_DB


def _conn():
    path = db_path()
    if not os.path.exists(path):
        return None
    c = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    return c


# Latin look-alike capitals inside a Greek word (a Latin B and A typed in
# BAΣΙΛΕΩΣ, as the catalogues themselves do) are read as Greek, the same rule
# scripts/coins/build_coins_db.py applies to the stored text, so the query
# and the index fold alike.
_LATIN_TO_GREEK = {'A': '\u0391', 'B': '\u0392', 'E': '\u0395', 'Z': '\u0396', 'H': '\u0397',
                   'I': '\u0399', 'K': '\u039a', 'M': '\u039c', 'N': '\u039d', 'O': '\u039f',
                   'P': '\u03a1', 'T': '\u03a4', 'Y': '\u03a5', 'X': '\u03a7'}


def unmix_scripts(text):
    def fix(m):
        w = m.group(0)
        if any(unicodedata.name(ch, '').startswith('GREEK') for ch in w):
            return ''.join(_LATIN_TO_GREEK.get(ch, ch) for ch in w)
        return w
    return re.sub(r'\S+', fix, str(text or ''))


def fold(text):
    """Lower-case and strip diacritics, as the database's search_text was."""
    d = unicodedata.normalize('NFD', unmix_scripts(text))
    d = ''.join(ch for ch in d if not unicodedata.combining(ch)).lower()
    # final and lunate sigma fold to the ordinary one, so a legend typed with
    # either is found
    return d.replace('\u03c2', '\u03c3').replace('\u03f2', '\u03c3')


def fts_query(q):
    """A phrase-safe FTS5 query: every word must occur, words of three or
    more letters match as prefixes. None when the text holds no word."""
    words = re.findall(r'\w+', fold(q))
    if not words:
        return None
    return ' '.join(f'"{w}"*' if len(w) >= 3 else f'"{w}"' for w in words)


def _present(r):
    d = {k: r[k] for k in r.keys() if k != 'search_text' and k != 'n'}
    d['type_url'] = d.get('uri')
    d['pleiades_url'] = (f'https://pleiades.stoa.org/places/{quote(str(r["mint_pleiades_id"]))}'
                         if r['mint_pleiades_id'] else None)
    d['credit'] = CREDITS.get(r['source'], 'Type record: American Numismatic Society, ODbL')
    d['coin_url'] = f'/coins/{quote(str(r["id"]), safe="")}'
    return d


def _filters(args, skip=None):
    """The WHERE fragments and bound values for the filters in `args`,
    leaving out the facet named in `skip`."""
    where, vals = [], []
    for f in FACET_FIELDS:
        v = (args.get(f) or '').strip()
        if v and f != skip:
            where.append(f'c.{f} = ?')
            vals.append(v)
    person = (args.get('person') or '').strip()
    if person:
        where.append("(instr('; ' || COALESCE(c.authority, '') || '; ', '; ' || ? || '; ') > 0 "
                     "OR instr('; ' || COALESCE(c.portrait, '') || '; ', '; ' || ? || '; ') > 0)")
        vals += [person, person]
    lo = args.get('date_from', type=int)
    hi = args.get('date_to', type=int)
    if lo is not None:
        where.append('COALESCE(c.date_end, c.date_start) >= ?')
        vals.append(lo)
    if hi is not None:
        where.append('c.date_start <= ?')
        vals.append(hi)
    return where, vals


def _facets(c, args, match):
    out = {}
    for f in FACET_FIELDS:
        where, vals = _filters(args, skip=f)
        where.append(f'c.{f} IS NOT NULL')
        sql = f'SELECT c.{f} AS v, COUNT(*) AS n FROM coins c'  # nosec B608 -- f comes from the fixed FACET_FIELDS tuple
        if match:
            sql += ' JOIN coins_fts ON coins_fts.rowid = c.n AND coins_fts MATCH ?'
            vals = [match] + vals
        sql += ' WHERE ' + ' AND '.join(where) + f' GROUP BY c.{f} ORDER BY n DESC, v LIMIT {FACET_LIMIT}'  # nosec B608 -- fixed names, bound values
        out[f] = [{'value': r['v'], 'count': r['n']} for r in c.execute(sql, vals)]
    return out


@coins_bp.route('/coins')
def list_coins():
    c = _conn()
    if c is None:
        return jsonify({'available': False, 'coins': [], 'total': 0, 'page': 1,
                        'per_page': 0, 'facets': {f: [] for f in FACET_FIELDS}})
    try:
        match = fts_query(request.args.get('q'))
        page = max(request.args.get('page', 1, type=int) or 1, 1)
        per_page = min(max(request.args.get('per_page', 24, type=int) or 24, 1), MAX_PER_PAGE)
        sort = request.args.get('sort') or ('relevance' if match else 'date')

        where, vals = _filters(request.args)
        frm = 'coins c'
        params = list(vals)
        if match:
            frm += ' JOIN coins_fts ON coins_fts.rowid = c.n AND coins_fts MATCH ?'
            params = [match] + params
        clause = (' WHERE ' + ' AND '.join(where)) if where else ''
        total = c.execute(f'SELECT COUNT(*) FROM {frm}{clause}', params).fetchone()[0]  # nosec B608 -- fixed fragments, values bound

        if sort == 'relevance' and match:
            order = 'ORDER BY bm25(coins_fts), c.n'
        else:
            order = 'ORDER BY c.date_start IS NULL, c.date_start, c.id'
        cols = ', '.join(f'c.{x.strip()}' for x in LIST_COLUMNS.split(','))
        rows = c.execute(f'SELECT {cols} FROM {frm}{clause} {order} LIMIT ? OFFSET ?',  # nosec B608 -- fixed fragments, values bound
                         params + [per_page, (page - 1) * per_page]).fetchall()
        return jsonify({'available': True, 'coins': [_present(r) for r in rows], 'total': total,
                        'page': page, 'per_page': per_page, 'sort': sort,
                        'facets': _facets(c, request.args, match)})
    except sqlite3.OperationalError as e:  # a malformed FTS query is the visitor's, not a crash
        logger.warning('coins query failed: %s', e)
        return jsonify({'available': True, 'coins': [], 'total': 0, 'page': 1,
                        'per_page': 0, 'facets': {f: [] for f in FACET_FIELDS}})
    finally:
        c.close()


@coins_bp.route('/coins/facets')
def coin_facets():
    c = _conn()
    if c is None:
        return jsonify({'available': False, 'facets': {f: [] for f in FACET_FIELDS},
                        'sources': {}, 'total': 0, 'date_min': None, 'date_max': None})
    try:
        facets = {}
        for f in FACET_FIELDS:
            facets[f] = [{'value': r['v'], 'count': r['n']} for r in c.execute(
                f'SELECT {f} AS v, COUNT(*) AS n FROM coins WHERE {f} IS NOT NULL '  # nosec B608 -- f from the fixed FACET_FIELDS tuple
                'GROUP BY 1 ORDER BY n DESC, v')]
        span = c.execute('SELECT MIN(date_start), MAX(COALESCE(date_end, date_start)), COUNT(*) '
                         'FROM coins').fetchone()
        return jsonify({'available': True, 'facets': facets,
                        'sources': {x['value']: x['count'] for x in facets['source']},
                        'total': span[2], 'date_min': span[0], 'date_max': span[1]})
    finally:
        c.close()


def _unavailable(message, status=200):
    return jsonify({'available': True, 'unavailable': True, 'error': message,
                    'related': [], 'name_links': [], 'results': []}), status


@coins_bp.route('/coins/for-passage')
def coins_for_passage():
    work = (request.args.get('work') or '').strip()
    ref = (request.args.get('ref') or request.args.get('ref_start') or '').strip()
    if not work or not ref:
        return jsonify({'error': 'work and ref are required', 'related': [], 'name_links': []})
    c = _conn()
    if c is None:
        return jsonify({'available': False, 'related': [], 'name_links': []})
    try:
        return jsonify(coins_passage.for_passage(
            c, db_path(), work, (request.args.get('lang') or request.args.get('language') or 'la').strip(),
            ref, (request.args.get('ref_end') or '').strip() or None))
    except coins_passage.EncoderUnavailable as e:
        logger.warning('coins for-passage: encoder unavailable: %s', e)
        return _unavailable('The query encoder service is not running, so related imagery cannot be '
                            'looked up just now.')
    finally:
        c.close()


@coins_bp.route('/coins/theme')
def coins_theme():
    q = (request.args.get('q') or request.args.get('query') or '').strip()
    if not q:
        return jsonify({'error': 'q is required', 'results': []})
    c = _conn()
    if c is None:
        return jsonify({'available': False, 'results': []})
    try:
        limit = min(max(request.args.get('limit', 10, type=int) or 10, 1), 25)
        return jsonify(coins_passage.theme(c, db_path(), q, limit))
    except coins_passage.EncoderUnavailable as e:
        logger.warning('coins theme: encoder unavailable: %s', e)
        return _unavailable('The query encoder service is not running, so the coin search is '
                            'unavailable just now.')
    finally:
        c.close()


@coins_bp.route('/coins/<path:coin_id>')
def get_coin(coin_id):
    c = _conn()
    if c is None:
        return jsonify({'error': 'The coins collection is not installed.'}), 404
    try:
        r = c.execute(f'SELECT {LIST_COLUMNS} FROM coins WHERE id = ?', (coin_id,)).fetchone()  # nosec B608 -- fixed column list
        if r is None:
            return jsonify({'error': 'No such coin type.'}), 404
        return jsonify({'coin': _present(r)})
    finally:
        c.close()
