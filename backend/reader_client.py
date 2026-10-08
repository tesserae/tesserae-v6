"""Client for the reader-at-top service (services/reader_server.py).

Theme Search wants a re-rank of its top results by a trained free model
instead of the raw index score. That model runs as its own small service
(port 8091 by default), the same shape as the query encoder in
services/embed_server.py, so the web application never loads torch or the
checkpoint itself.

THEME_READER_URL is empty by default, which means the reader is disabled:
`score` returns None immediately and Theme Search falls back to the plain
index order. This also covers the request path if the service is down,
slow, or returns something unexpected -- `score` never raises, so a broken
reader degrades Theme Search back to what it already was rather than
breaking the page.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.request

from backend.logging_config import get_logger

logger = get_logger('reader_client')

_WARN_INTERVAL = 60.0  # seconds between "reader unreachable" log lines
_last_warn = 0.0
_warn_lock = threading.Lock()


def _warn_rate_limited(message, *args):
    global _last_warn
    now = time.time()
    with _warn_lock:
        if now - _last_warn < _WARN_INTERVAL:
            return
        _last_warn = now
    logger.warning(message, *args)


def score(query, passages, timeout=6.0):
    """Ask the reader service to score `passages` against `query`.

    `passages` is a list of {"id": str, "text": str}. Returns {id: float} on
    success, or None on any failure: the service disabled (THEME_READER_URL
    unset), unreachable, slow past `timeout`, a non-200 response, or a body
    that is not the JSON shape expected. Never raises.
    """
    url = (os.environ.get('THEME_READER_URL') or '').strip()
    if not url or not passages:
        return None

    endpoint = url.rstrip('/') + '/score'
    body = json.dumps({'query': query, 'passages': passages}).encode('utf-8')
    req = urllib.request.Request(
        endpoint, data=body, method='POST',
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                _warn_rate_limited(
                    '[READER] %s returned status %s', endpoint, resp.status)
                return None
            payload = json.loads(resp.read().decode('utf-8'))
    except Exception as e:  # noqa: BLE001 - disabled/timeout/network/bad JSON, all the same to the caller
        _warn_rate_limited('[READER] call to %s failed: %s', endpoint, e)
        return None

    scores = payload.get('scores')
    if not isinstance(scores, dict):
        _warn_rate_limited('[READER] %s returned no scores field', endpoint)
        return None
    try:
        return {k: float(v) for k, v in scores.items()}
    except (TypeError, ValueError) as e:
        _warn_rate_limited('[READER] %s returned unscorable values: %s', endpoint, e)
        return None
