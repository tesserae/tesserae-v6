"""
GitHub issue filing for the requests workflow (feature/language/text/bug,
plus result-problem/text-correction/suggestion from the website).

A scholar's AI assistant, or the website's own suggestion dialog, can submit
a structured request via POST /api/feature-request. This module files a
labelled GitHub issue in the team's repo so it lands directly in the dev
triage workflow and in the public Requests page (backend/github_requests.py).

Gating & safety:
    - Fully OFF unless BOTH GITHUB_FEEDBACK_TOKEN and GITHUB_FEEDBACK_REPO are
      set (and FEEDBACK_GITHUB_ENABLED is not explicitly false). With the token
      absent, callers fall back to the private DB + email path only.
    - The public issue NEVER contains the submitter's contact/email — the caller
      is responsible for passing an already-stripped body. This module does not
      accept or embed contact info.
    - The token is read from the environment and never logged.
"""
import os
import time
import logging

import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
_TIMEOUT = 10

# A label this module has already confirmed exists in the repo (or just
# created), so a submission doesn't re-check on every call. Short TTL: this
# is a cheap convenience, not a source of truth -- a stale miss just means
# one extra GET.
_LABEL_CACHE_TTL = 3600
_label_cache = {'ts': 0.0, 'names': set()}


def github_feedback_enabled():
    """True only when a token + repo are configured and the kill-switch is on."""
    token = os.environ.get('GITHUB_FEEDBACK_TOKEN', '').strip()
    repo = os.environ.get('GITHUB_FEEDBACK_REPO', '').strip()
    enabled = os.environ.get('FEEDBACK_GITHUB_ENABLED', 'true').strip().lower()
    return bool(token and repo and enabled in ('1', 'true', 'yes', 'on'))


def _gh_headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
    }


def _ensure_labels(repo, token, labels):
    """Create any of `labels` that don't already exist in the repo (e.g. the
    first time a new request type is filed, "request:<type>" won't exist
    yet). GitHub silently drops an unknown label from `issues` creation
    rather than erroring, so this is filed proactively instead of assumed."""
    now = time.time()
    if now - _label_cache['ts'] > _LABEL_CACHE_TTL:
        try:
            resp = requests.get(f"{GITHUB_API}/repos/{repo}/labels",
                                headers=_gh_headers(token), params={'per_page': 100},
                                timeout=_TIMEOUT)
            if resp.status_code == 200:
                _label_cache['names'] = {l['name'] for l in resp.json()}
                _label_cache['ts'] = now
        except Exception as e:
            logger.warning("GitHub label list error: %s", e)

    for name in labels:
        if name in _label_cache['names']:
            continue
        try:
            resp = requests.post(f"{GITHUB_API}/repos/{repo}/labels",
                                 headers=_gh_headers(token),
                                 json={'name': name, 'color': 'ededed'}, timeout=_TIMEOUT)
            if resp.status_code in (201, 422):  # 422: another request just created it
                _label_cache['names'].add(name)
        except Exception as e:
            logger.warning("GitHub label create error (%s): %s", name, e)


def create_feedback_issue(title, body, labels):
    """Create a GitHub issue and return its html_url, or None on failure/disabled.

    `title` and `body` must ALREADY have any submitter contact info removed —
    this becomes a public issue.
    """
    if not github_feedback_enabled():
        return None
    token = os.environ.get('GITHUB_FEEDBACK_TOKEN', '').strip()
    repo = os.environ.get('GITHUB_FEEDBACK_REPO', '').strip()
    if labels:
        _ensure_labels(repo, token, labels)
    try:
        resp = requests.post(
            f"{GITHUB_API}/repos/{repo}/issues",
            headers=_gh_headers(token),
            json={'title': title[:250], 'body': body, 'labels': labels},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 201:
            return resp.json().get('html_url')
        # Never log the token; response text may include useful GitHub error detail.
        logger.warning("GitHub feedback issue failed: %s %s",
                       resp.status_code, resp.text[:300])
    except Exception as e:
        logger.warning("GitHub feedback issue error: %s", e)
    return None
