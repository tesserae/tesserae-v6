"""First-party page-view recording: which pages a visit opened, in order.

POST /api/usage/page always answers 204. Nothing here raises to the client.

The address lookup (services.get_user_location) sends the visitor's address to
ipinfo.io, with ip-api.com as fallback, exactly as the search log does. It runs
once per visit, on the visit's first page view. Later rows copy city and
country from the first row of the same visit.
"""
import re
from urllib.parse import urlsplit, parse_qsl, urlencode

from flask import Blueprint, request

from backend.db_utils import get_db_cursor
from backend.logging_config import get_logger
from backend.usage_bots import is_bot
from backend import services

logger = get_logger('usage')

usage_bp = Blueprint('usage', __name__)

OWN_HOST = 'tesserae.caset.buffalo.edu'
MAX_VIEWS_PER_VISIT = 200
_VISIT_RE = re.compile(r'^[0-9a-f]{16,32}$')
_DROPPED_PARAMS = ('token', 'key')


def clean_path(path):
    """Return the path with token= and key= parameters removed, or None if invalid."""
    if not isinstance(path, str) or not path.startswith('/') or len(path) > 300:
        return None
    parts = urlsplit(path)
    pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in _DROPPED_PARAMS]
    cleaned = parts.path
    if pairs:
        cleaned += '?' + urlencode(pairs)
    return cleaned[:300]


def referrer_host(referrer):
    """Host of an outside referrer, or None."""
    if not isinstance(referrer, str) or not referrer:
        return None
    try:
        host = (urlsplit(referrer).hostname or '').lower()
    except ValueError:
        return None
    if not host or host == OWN_HOST:
        return None
    return host[:200]


def _short(value, limit):
    return value[:limit] if isinstance(value, str) and value else None


@usage_bp.route('/usage/page', methods=['POST'])
def record_page_view():
    try:
        if is_bot(request.headers.get('User-Agent')):
            return '', 204
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return '', 204
        visit = body.get('visit')
        if not isinstance(visit, str) or not _VISIT_RE.match(visit):
            return '', 204
        path = clean_path(body.get('path'))
        page = body.get('page')
        if path is None or not isinstance(page, str) or not page or len(page) > 60:
            return '', 204
        language = _short(body.get('language'), 8)
        ref = referrer_host(body.get('referrer'))
        ip = services.get_client_ip()

        with get_db_cursor(commit=False) as cur:
            cur.execute(
                'SELECT count(*), max(city), max(country) FROM page_views WHERE visit_id = %s',
                (visit,))
            row = cur.fetchone()
        count = row[0] if row else 0
        if count >= MAX_VIEWS_PER_VISIT:
            return '', 204
        if count == 0:
            city, country, _ = services.get_user_location()
        else:
            city, country = row[1], row[2]
        with get_db_cursor() as cur:
            cur.execute(
                'INSERT INTO page_views (visit_id, path, page, language, referrer_host, '
                'client_ip, city, country) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)',
                (visit, path, page, language, ref, (ip or '')[:64] or None, city, country))
    except Exception as e:
        logger.debug(f'page view not recorded: {e}')
    return '', 204
