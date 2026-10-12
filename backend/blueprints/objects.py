"""Objects: the read-only API behind the Objects page.

    GET /api/objects?q=&museum=&object_type=&culture=&material=
                    &date_from=&date_to=&sort=relevance|date&page=&per_page=
        museum objects (Cleveland Museum of Art, Art Institute of Chicago,
        Smithsonian), searchable over title, catalogue description, label and
        inscription, filterable, paged, with facet counts for the filters in force.
    GET /api/objects/facets
        every value of each filter with its count, the date span, and the
        count per museum.
    GET /api/objects/<id>
        one object.
    GET /api/objects/image/<id>
        the object's museum picture, fetched once by this server and served
        from a disk cache (data/objects/images/), so a visitor's browser never
        depends on the museum's image server.
    GET /api/objects/theme?q=
        the object descriptions nearest a free-text query, for Theme Search.

The data is a SQLite file written offline by scripts/objects/build_objects_db.py;
the routes only read it. The path comes from TESSERAE_OBJECTS_DB, default
data/objects/objects.sqlite. With no file the list route answers available=false
and the detail route 404, as the Coins routes do.

Dates are signed years (-500 is 500 BCE). The descriptions are the museums' own
catalogue texts, each with its licence and credit line; an image address is
stored only where the museum gives a web image under CC0 and the page links to
the museum's own record for the rest.
"""
import hashlib
import os
import re
import sqlite3
import tempfile
import unicodedata
from urllib.parse import quote, urlparse

import requests
from flask import Blueprint, Response, jsonify, request

from backend import objects_theme
from backend.logging_config import get_logger

logger = get_logger('objects')
objects_bp = Blueprint('objects', __name__)

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(_ROOT, 'data', 'objects', 'objects.sqlite')
MAX_PER_PAGE = 100
FACET_FIELDS = ('museum', 'object_type', 'culture', 'material')
FACET_LIMIT = 60

MUSEUM_NAMES = {
    'cleveland': 'Cleveland Museum of Art',
    'chicago': 'Art Institute of Chicago',
    'smithsonian': 'Smithsonian Institution',
}
LIST_COLUMNS = ('id, museum, title, object_type, culture, date_text, date_start, date_end, material, '
                'place_text, description, short_text, inscription_text, image_url, object_url, '
                'licence, credit')


def db_path():
    return os.environ.get('TESSERAE_OBJECTS_DB') or DEFAULT_DB


def _conn():
    path = db_path()
    if not os.path.exists(path):
        return None
    c = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    c.row_factory = sqlite3.Row
    return c


def fold(text):
    """Lower-case and strip diacritics, as the database's search_text was."""
    d = unicodedata.normalize('NFD', str(text or ''))
    return ''.join(ch for ch in d if not unicodedata.combining(ch)).lower()


def fts_query(q):
    """A phrase-safe FTS5 query: every word must occur, words of three or
    more letters match as prefixes. None when the text holds no word."""
    words = re.findall(r'\w+', fold(q))
    if not words:
        return None
    return ' '.join(f'"{w}"*' if len(w) >= 3 else f'"{w}"' for w in words)


def _present(r):
    d = {k: r[k] for k in r.keys() if k not in ('search_text', 'n')}
    d['museum_name'] = MUSEUM_NAMES.get(r['museum'], r['museum'])
    d['object_page'] = f'/objects/{quote(str(r["id"]), safe="")}'
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
        sql = f'SELECT c.{f} AS v, COUNT(*) AS n FROM objects c'  # nosec B608 -- f comes from the fixed FACET_FIELDS tuple
        if match:
            sql += ' JOIN objects_fts ON objects_fts.rowid = c.n AND objects_fts MATCH ?'
            vals = [match] + vals
        sql += ' WHERE ' + ' AND '.join(where) + f' GROUP BY c.{f} ORDER BY n DESC, v LIMIT {FACET_LIMIT}'  # nosec B608 -- fixed names, bound values
        out[f] = [{'value': r['v'], 'count': r['n']} for r in c.execute(sql, vals)]
    return out


def _empty_facets():
    return {f: [] for f in FACET_FIELDS}


@objects_bp.route('/objects')
def list_objects():
    c = _conn()
    if c is None:
        return jsonify({'available': False, 'objects': [], 'total': 0, 'page': 1,
                        'per_page': 0, 'facets': _empty_facets()})
    try:
        match = fts_query(request.args.get('q'))
        page = max(request.args.get('page', 1, type=int) or 1, 1)
        per_page = min(max(request.args.get('per_page', 24, type=int) or 24, 1), MAX_PER_PAGE)
        sort = request.args.get('sort') or ('relevance' if match else 'date')

        where, vals = _filters(request.args)
        frm = 'objects c'
        params = list(vals)
        if match:
            frm += ' JOIN objects_fts ON objects_fts.rowid = c.n AND objects_fts MATCH ?'
            params = [match] + params
        clause = (' WHERE ' + ' AND '.join(where)) if where else ''
        total = c.execute(f'SELECT COUNT(*) FROM {frm}{clause}', params).fetchone()[0]  # nosec B608 -- fixed fragments, values bound

        if sort == 'relevance' and match:
            order = 'ORDER BY bm25(objects_fts), c.n'
        else:
            order = 'ORDER BY c.date_start IS NULL, c.date_start, c.id'
        cols = ', '.join(f'c.{x.strip()}' for x in LIST_COLUMNS.split(','))
        rows = c.execute(f'SELECT {cols} FROM {frm}{clause} {order} LIMIT ? OFFSET ?',  # nosec B608 -- fixed fragments, values bound
                         params + [per_page, (page - 1) * per_page]).fetchall()
        return jsonify({'available': True, 'objects': [_present(r) for r in rows], 'total': total,
                        'page': page, 'per_page': per_page, 'sort': sort,
                        'facets': _facets(c, request.args, match)})
    except sqlite3.OperationalError as e:  # a malformed FTS query is the visitor's, not a crash
        logger.warning('objects query failed: %s', e)
        return jsonify({'available': True, 'objects': [], 'total': 0, 'page': 1,
                        'per_page': 0, 'facets': _empty_facets()})
    finally:
        c.close()


@objects_bp.route('/objects/facets')
def object_facets():
    c = _conn()
    if c is None:
        return jsonify({'available': False, 'facets': _empty_facets(),
                        'museums': {}, 'total': 0, 'date_min': None, 'date_max': None})
    try:
        facets = {}
        for f in FACET_FIELDS:
            facets[f] = [{'value': r['v'], 'count': r['n']} for r in c.execute(
                f'SELECT {f} AS v, COUNT(*) AS n FROM objects WHERE {f} IS NOT NULL '  # nosec B608 -- f from the fixed FACET_FIELDS tuple
                'GROUP BY 1 ORDER BY n DESC, v')]
        span = c.execute('SELECT MIN(date_start), MAX(COALESCE(date_end, date_start)), COUNT(*) '
                         'FROM objects').fetchone()
        return jsonify({'available': True, 'facets': facets,
                        'museums': {x['value']: x['count'] for x in facets['museum']},
                        'total': span[2], 'date_min': span[0], 'date_max': span[1]})
    finally:
        c.close()


def _unavailable(message, status=200):
    return jsonify({'available': True, 'unavailable': True, 'error': message,
                    'results': []}), status


@objects_bp.route('/objects/theme')
def objects_theme_route():
    q = (request.args.get('q') or request.args.get('query') or '').strip()
    if not q:
        return jsonify({'error': 'q is required', 'results': []})
    c = _conn()
    if c is None:
        return jsonify({'available': False, 'results': []})
    try:
        limit = min(max(request.args.get('limit', 10, type=int) or 10, 1), 25)
        return jsonify(objects_theme.theme(c, db_path(), q, limit))
    except objects_theme.EncoderUnavailable as e:
        logger.warning('objects theme: encoder unavailable: %s', e)
        return _unavailable('The query encoder service is not running, so the object search is '
                            'unavailable just now.')
    finally:
        c.close()


# ---- Pictures served from our own cache ------------------------------------
# Hosts present in image_url in the production database (2026-10-12), with the
# number of objects each carries. Any other host is refused.
IMAGE_HOSTS = {
    'www.artic.edu': 390,                      # Art Institute of Chicago (IIIF)
    'openaccess-cdn.clevelandart.org': 304,    # Cleveland Museum of Art open access
}
IMAGE_MAX_BYTES = 8 * 1024 * 1024
IMAGE_TIMEOUT = 15
IMAGE_MAX_REDIRECTS = 3
IMAGE_USER_AGENT = ('Mozilla/5.0 (compatible; Tesserae/6; +https://tesserae.caset.buffalo.edu) '
                    'object-image-cache')
_EXT = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/gif': 'gif', 'image/webp': 'webp',
        'image/tiff': 'tif', 'image/svg+xml': 'svg'}


def image_dir():
    return os.environ.get('TESSERAE_OBJECT_IMAGES') or os.path.join(os.path.dirname(db_path()), 'images')


def image_open_licence(licence):
    """Open licence rule: the licence text names CC0, a CC BY licence or the
    public domain. The database holds two values, 'CC0' (Cleveland) and
    'Catalogue record CC0, description CC BY 4.0' (Chicago); both qualify.
    Anything else, or nothing, is not served."""
    t = (licence or '').lower()
    return 'cc0' in t or 'cc by' in t or 'public domain' in t


def image_host_allowed(url):
    try:
        u = urlparse(url or '')
    except ValueError:
        return False
    return u.scheme in ('http', 'https') and (u.hostname or '').lower() in IMAGE_HOSTS


def image_cache_key(url):
    return hashlib.sha1(url.encode('utf-8')).hexdigest()  # nosec B324 -- a file name, not security


def find_cached_image(url):
    """(path, content_type) of the cached file for `url`, or None."""
    d, key = image_dir(), image_cache_key(url)
    for ctype, ext in _EXT.items():
        p = os.path.join(d, f'{key}.{ext}')
        if os.path.exists(p):
            return p, ctype
    return None


def fetch_image(url):
    """Download `url` and return (bytes, content_type). Raises ValueError on
    anything unacceptable. Redirects are followed by hand, at most three, and
    each hop must stay on an allowed host."""
    cur = url
    for _ in range(IMAGE_MAX_REDIRECTS + 1):
        if not image_host_allowed(cur):
            raise ValueError('host not allowed')
        r = requests.get(cur, timeout=IMAGE_TIMEOUT, stream=True, allow_redirects=False,
                         headers={'User-Agent': IMAGE_USER_AGENT, 'Accept': 'image/*'})
        try:
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get('Location'):
                cur = requests.compat.urljoin(cur, r.headers['Location'])
                continue
            if r.status_code != 200:
                raise ValueError(f'upstream status {r.status_code}')
            ctype = (r.headers.get('Content-Type') or '').split(';')[0].strip().lower()
            if not ctype.startswith('image/'):
                raise ValueError('upstream is not an image')
            body = b''
            for chunk in r.iter_content(65536):
                body += chunk
                if len(body) > IMAGE_MAX_BYTES:
                    raise ValueError('image too large')
            if not body:
                raise ValueError('empty image')
            return body, ctype
        finally:
            r.close()
    raise ValueError('too many redirects')


def store_image(url, body, ctype):
    """Write atomically (temp file, then rename) and return the path."""
    d = image_dir()
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f'{image_cache_key(url)}.{_EXT.get(ctype, "bin")}')
    fd, tmp = tempfile.mkstemp(dir=d, suffix='.part')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(body)
        os.chmod(tmp, 0o664)  # nosec B103 -- group-writable on purpose: the tessdev group (Apache workers and the maintainer) shares data/
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return path


def _image_response(body, ctype, host):
    resp = Response(body, mimetype=ctype)
    resp.headers['Cache-Control'] = 'public, max-age=2592000'
    resp.headers['X-Image-Source'] = host
    return resp


@objects_bp.route('/objects/image/<path:object_id>')
def object_image(object_id):
    c = _conn()
    if c is None:
        return jsonify({'error': 'The objects collection is not installed.'}), 404
    try:
        r = c.execute('SELECT image_url, licence FROM objects WHERE id = ?', (object_id,)).fetchone()
    finally:
        c.close()
    if r is None or not r['image_url']:
        return jsonify({'error': 'No picture for this object.'}), 404
    url = r['image_url']
    if not image_open_licence(r['licence']) or not image_host_allowed(url):
        return jsonify({'error': 'No picture for this object.'}), 404
    host = urlparse(url).hostname.lower()
    hit = find_cached_image(url)
    if hit:
        with open(hit[0], 'rb') as f:
            return _image_response(f.read(), hit[1], host)
    try:
        body, ctype = fetch_image(url)
        store_image(url, body, ctype)
    except (ValueError, requests.RequestException, OSError) as e:
        logger.warning('object image %s: %s', object_id, e)
        return jsonify({'error': 'The museum picture could not be fetched just now.'}), 502
    return _image_response(body, ctype, host)


@objects_bp.route('/objects/<path:object_id>')
def get_object(object_id):
    c = _conn()
    if c is None:
        return jsonify({'error': 'The objects collection is not installed.'}), 404
    try:
        r = c.execute(f'SELECT {LIST_COLUMNS} FROM objects WHERE id = ?', (object_id,)).fetchone()  # nosec B608 -- fixed column list
        if r is None:
            return jsonify({'error': 'No such object.'}), 404
        return jsonify({'object': _present(r)})
    finally:
        c.close()
