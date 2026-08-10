"""
GitHub issue filing for AI-protocol feature/language/bug requests.

A user's AI assistant (following the Tesserae AI-assistant guide) can submit a
structured request via POST /api/feature-request. For actionable types this
module files a labelled GitHub issue in the team's repo so it lands directly in
the dev triage workflow.

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
import logging

import requests

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
_TIMEOUT = 10


def github_feedback_enabled():
    """True only when a token + repo are configured and the kill-switch is on."""
    token = os.environ.get('GITHUB_FEEDBACK_TOKEN', '').strip()
    repo = os.environ.get('GITHUB_FEEDBACK_REPO', '').strip()
    enabled = os.environ.get('FEEDBACK_GITHUB_ENABLED', 'true').strip().lower()
    return bool(token and repo and enabled in ('1', 'true', 'yes', 'on'))


def create_feedback_issue(title, body, labels):
    """Create a GitHub issue and return its html_url, or None on failure/disabled.

    `title` and `body` must ALREADY have any submitter contact info removed —
    this becomes a public issue.
    """
    if not github_feedback_enabled():
        return None
    token = os.environ.get('GITHUB_FEEDBACK_TOKEN', '').strip()
    repo = os.environ.get('GITHUB_FEEDBACK_REPO', '').strip()
    try:
        resp = requests.post(
            f"{GITHUB_API}/repos/{repo}/issues",
            headers={
                'Authorization': f'Bearer {token}',
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
            },
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
