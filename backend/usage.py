"""One row per use of the site beyond the search page: a Theme Search
query, a text opened in the Reader, a Similar Passages request, a
Scholarship lookup, a connector tool call. Same country and city as the
search log, nothing more; never raises (NC, 2026-09-14: "Build it").
"""
import os

from flask import request

from backend.db_utils import get_db_cursor
from backend.logging_config import get_logger
from backend.services import get_user_location

logger = get_logger(__name__)

SOURCE = 'preview' if os.environ.get('TESSERAE_PREVIEW') else 'site'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS usage_events (
    id SERIAL PRIMARY KEY,
    kind VARCHAR(50) NOT NULL,
    source VARCHAR(20) DEFAULT 'site',
    language VARCHAR(10),
    work VARCHAR(255),
    ref_start VARCHAR(100),
    ref_end VARCHAR(100),
    query_text TEXT,
    results_count INTEGER,
    user_id VARCHAR(255),
    client_ip VARCHAR(50),
    city VARCHAR(100),
    country VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_usage_events_created_at ON usage_events(created_at);
CREATE INDEX IF NOT EXISTS idx_usage_events_kind ON usage_events(kind);
'''


def _user_id():
    try:
        from flask_login import current_user
        if current_user and current_user.is_authenticated:
            return str(current_user.id)
    except Exception:  # noqa: BLE001 - logging must never break a request
        pass
    return None


def log_event(kind, language=None, work=None, ref_start=None, ref_end=None, query_text=None,
              results_count=None, source=None):
    """Record one event. Called inside a request; safe to call anywhere."""
    try:
        city, country, ip = get_user_location()
    except Exception:  # noqa: BLE001
        city, country, ip = None, None, None
    try:
        with get_db_cursor() as cur:
            cur.execute(
                'INSERT INTO usage_events (kind, source, language, work, ref_start, ref_end, query_text, '
                'results_count, user_id, client_ip, city, country) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)',
                (kind, source or SOURCE, language, (work or '')[:255] or None, (ref_start or '')[:100] or None,
                 (ref_end or '')[:100] or None, (query_text or '')[:500] or None, results_count, _user_id(),
                 ip, city, country))
    except Exception as e:  # noqa: BLE001
        logger.warning('usage event not logged (%s): %s', kind, e)
