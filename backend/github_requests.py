"""
Public mirror of the requests workflow's GitHub issues.

GitHub issues are the single store of requests (feature, language, bug,
text correction, result problem, general suggestion): every one filed by
POST /api/feature-request carries the "request" label plus a "request:<type>"
label. This module reads that label back out for the public Requests page
(GET /api/requests), so a scholar can see what has been asked for and what
happened to it without ever touching GitHub.

Only a short, explicitly public summary ever leaves this module: the first
line of an issue's body after a "Summary:" marker, if the filer's submission
produced one, or nothing. The rest of the body (contact info is never there,
but free-text context can be long or stray) never crosses this boundary.

Cached in process for CACHE_TTL_SECONDS, and mirrored to disk under cache/ so
a worker that restarts (Apache recycles workers) does not refetch on its
first request after a restart.
"""
import os
import json
import time
import logging
import threading
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
_TIMEOUT = 10

CACHE_TTL_SECONDS = 600  # 10 minutes
# "recently closed": closed issues older than this are dropped from the
# public listing so it stays a current picture, not a full archive.
RECENT_CLOSED_DAYS = 90
_MAX_PAGES = 5  # 500 issues at 100/page; a sane ceiling for one repo's label

_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'cache', 'github_requests_cache.json',
)

_lock = threading.Lock()
_mem_cache = {'ts': 0.0, 'items': None}


def _headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }


def _label_names(issue):
    return [(l.get('name') if isinstance(l, dict) else l) or '' for l in issue.get('labels', [])]


def _type_label(issue):
    for name in _label_names(issue):
        if name.startswith('request:'):
            return name.split(':', 1)[1]
    return 'other'


def _status_for(issue):
    if issue.get('state') == 'open':
        if any(n.lower() == 'in progress' for n in _label_names(issue)):
            return 'in progress'
        return 'open'
    # Closed: GitHub's own state_reason distinguishes "we did it" from
    # "we're not doing it", so no extra label is needed for this half.
    return 'declined' if issue.get('state_reason') == 'not_planned' else 'done'


def _public_summary(body):
    """The text after a 'Summary:' marker on its own line, if the filer's
    submission produced one. Never any other part of the body."""
    for line in (body or '').splitlines():
        line = line.strip()
        if line.lower().startswith('summary:'):
            return line.split(':', 1)[1].strip()[:200]
    return ''


def _closed_recently(issue):
    closed_at = issue.get('closed_at')
    if not closed_at:
        return True
    try:
        dt = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
    except ValueError:
        return True
    return (datetime.now(timezone.utc) - dt).days <= RECENT_CLOSED_DAYS


def _merged_pr_url(repo, token, issue_number):
    """The merged pull request that closed this issue, if any. Costs one
    extra call per closed/done issue, which the cache keeps infrequent."""
    try:
        resp = requests.get(
            f"{GITHUB_API}/repos/{repo}/issues/{issue_number}/timeline",
            headers=_headers(token), timeout=_TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        for event in resp.json():
            if event.get('event') != 'cross-referenced':
                continue
            source_issue = (event.get('source') or {}).get('issue') or {}
            pr = source_issue.get('pull_request')
            if pr and pr.get('merged_at'):
                return source_issue.get('html_url')
    except Exception as e:
        logger.warning("github_requests timeline lookup failed for #%s: %s", issue_number, e)
    return None


def _fetch_from_github():
    token = os.environ.get('GITHUB_FEEDBACK_TOKEN', '').strip()
    repo = os.environ.get('GITHUB_FEEDBACK_REPO', '').strip()
    if not (token and repo):
        return []

    items = []
    url = f"{GITHUB_API}/repos/{repo}/issues"
    params = {'labels': 'request', 'state': 'all', 'per_page': 100,
              'sort': 'created', 'direction': 'desc'}
    page = 0
    while url and page < _MAX_PAGES:
        page += 1
        try:
            resp = requests.get(url, headers=_headers(token),
                                params=params if page == 1 else None, timeout=_TIMEOUT)
        except Exception as e:
            logger.warning("github_requests list error: %s", e)
            break
        if resp.status_code != 200:
            logger.warning("github_requests list failed: %s %s", resp.status_code, resp.text[:200])
            break
        for issue in resp.json():
            if issue.get('pull_request'):
                continue  # issues endpoint also returns PRs; skip those
            status = _status_for(issue)
            if status in ('done', 'declined') and not _closed_recently(issue):
                continue
            entry = {
                'number': issue.get('number'),
                'title': issue.get('title') or '',
                'type': _type_label(issue),
                'status': status,
                'created_at': issue.get('created_at'),
                'closed_at': issue.get('closed_at'),
                'summary': _public_summary(issue.get('body')),
                'url': issue.get('html_url'),
            }
            if status == 'done':
                pr_url = _merged_pr_url(repo, token, issue.get('number'))
                if pr_url:
                    entry['pr_url'] = pr_url
            items.append(entry)
        next_url = None
        for part in resp.headers.get('Link', '').split(','):
            if 'rel="next"' in part:
                next_url = part.split(';')[0].strip().strip('<>')
        url = next_url
    return items


def _load_disk_cache():
    try:
        with open(_CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return None


def _save_disk_cache(items, ts):
    try:
        os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
        with open(_CACHE_PATH, 'w') as f:
            json.dump({'ts': ts, 'items': items}, f)
    except Exception as e:
        logger.warning("github_requests disk cache write failed: %s", e)


def fetch_requests_listing(force_refresh=False):
    """Open + recently-closed issues labelled 'request', newest first.
    Cached in process for CACHE_TTL_SECONDS; falls back to a disk cache
    (fresh within the same window) so a freshly-restarted worker does not
    hit GitHub on its very first request."""
    now = time.time()
    with _lock:
        if not force_refresh and _mem_cache['items'] is not None \
                and now - _mem_cache['ts'] < CACHE_TTL_SECONDS:
            return _mem_cache['items']

    if not force_refresh:
        disk = _load_disk_cache()
        if disk and now - disk.get('ts', 0) < CACHE_TTL_SECONDS:
            with _lock:
                _mem_cache['items'] = disk['items']
                _mem_cache['ts'] = disk['ts']
            return disk['items']

    items = _fetch_from_github()
    with _lock:
        _mem_cache['items'] = items
        _mem_cache['ts'] = now
    _save_disk_cache(items, now)
    return items
