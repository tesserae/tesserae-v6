"""
Tesserae V6 - Feature Request Blueprint

POST /api/feature-request — intake for structured feature / language / text /
bug requests submitted by a user's AI assistant following the Tesserae
AI-assistant guide.

Flow for each submission:
    1. Validate + rate-limit (per IP).
    2. Store privately in the `feedback` table (includes contact, if given).
    3. Email the team privately (includes contact).
    4. For actionable types (feature / language / bug), ALSO auto-file a public
       GitHub issue — with the submitter's contact/email STRIPPED — so it lands
       in the dev triage workflow. Gated: no token configured => this step is
       skipped and the request still lands via DB + email.

The AI is instructed (in the guide) to obtain explicit user sign-off before
calling this endpoint and to warn the user that the description becomes a public
GitHub issue; contact info is kept private by this endpoint regardless.
"""
import os
import time
import logging
import threading

from flask import Blueprint, jsonify, request

from backend.db_utils import get_db_cursor
from backend.email_notifications import send_notification
from backend.github_feedback import github_feedback_enabled, create_feedback_issue

logger = logging.getLogger(__name__)

feature_request_bp = Blueprint('feature_request', __name__)

VALID_TYPES = {'feature', 'language', 'text', 'bug', 'other'}
GITHUB_TYPES = {'feature', 'language', 'bug'}   # 'text' -> curatorial flow; 'other' -> no issue
MAX_FIELD = 4000
MAX_TOTAL = 12000

# --- simple per-IP rate limit (mirrors the admin-login limiter) ---
_RL_MAX = int(os.environ.get('FEATURE_REQUEST_MAX_PER_HOUR', '6'))
_RL_WINDOW = 3600
_rl_attempts = {}
_rl_lock = threading.Lock()


def _client_ip():
    fwd = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    return fwd or request.remote_addr or 'unknown'


def _rate_limited():
    now = time.time()
    ip = _client_ip()
    cutoff = now - _RL_WINDOW
    with _rl_lock:
        # prune all buckets
        for k in list(_rl_attempts):
            kept = [t for t in _rl_attempts[k] if t >= cutoff]
            if kept:
                _rl_attempts[k] = kept
            else:
                _rl_attempts.pop(k, None)
        recent = _rl_attempts.get(ip, [])
        if len(recent) >= _RL_MAX:
            return True
        recent.append(now)
        _rl_attempts[ip] = recent
        return False


def _field(data, name):
    v = data.get(name)
    return str(v).strip()[:MAX_FIELD] if v else ''


@feature_request_bp.route('/feature-request', methods=['POST'])
def feature_request():
    data = request.get_json(silent=True) or {}

    req_type = (data.get('type') or 'feature').strip().lower()
    if req_type not in VALID_TYPES:
        req_type = 'other'

    title = _field(data, 'title')
    problem = _field(data, 'problem')
    desired = _field(data, 'desired')
    example = _field(data, 'example')
    tried = _field(data, 'tried')
    context = _field(data, 'context')
    contact = _field(data, 'contact')          # email — kept PRIVATE (DB + email only)

    if not (title or problem or desired):
        return jsonify({'error': 'Please include at least a title or a description '
                                 'of what you want.'}), 400

    if _rate_limited():
        return jsonify({'error': 'Too many requests from this address. '
                                 'Please try again later.'}), 429, {'Retry-After': str(_RL_WINDOW)}

    # --- public-safe body (NO contact) — shared by the DB record, email, and GitHub issue ---
    parts = []
    if title:
        parts.append(f"**Title:** {title}")
    parts.append(f"**Type:** {req_type}")
    if problem:
        parts.append(f"**Problem / need:**\n{problem}")
    if desired:
        parts.append(f"**Desired Tesserae behaviour:**\n{desired}")
    if example:
        parts.append(f"**Example:**\n{example}")
    if tried:
        parts.append(f"**Current workaround / what they tried:**\n{tried}")
    if context:
        parts.append(f"**Search context (auto-captured):**\n{context}")
    public_body = "\n\n".join(parts)[:MAX_TOTAL]
    public_body += "\n\n---\n_Filed via the Tesserae AI-assistant protocol._"

    feedback_id = None
    issue_url = None

    # --- (2) private DB record (feedback table), contact included ---
    try:
        with get_db_cursor() as cur:
            cur.execute(
                '''INSERT INTO feedback (name, email, feedback_type, message)
                   VALUES (%s, %s, %s, %s) RETURNING id''',
                (None, contact or None, f'ai:{req_type}',
                 public_body + (f"\n\n[contact: {contact}]" if contact else '')),
            )
            row = cur.fetchone()
            feedback_id = row[0] if row else None
    except Exception as e:
        logger.warning("feature_request DB insert failed: %s", e)

    # --- (3) private email to the team, contact included ---
    try:
        subject = f"New AI-protocol {req_type} request" + (f": {title}" if title else "")
        email_body = public_body + (
            f"\n\nContact (private): {contact}" if contact else "\n\nContact: not provided")
        send_notification(subject, email_body, 'feature_request')
    except Exception as e:
        logger.warning("feature_request email notify failed: %s", e)

    # --- (4) public GitHub issue for actionable types, email STRIPPED ---
    if req_type in GITHUB_TYPES and github_feedback_enabled():
        gh_title = f"[{req_type}] " + (title or f"{req_type} request")
        issue_url = create_feedback_issue(gh_title, public_body,
                                          ['from-ai-protocol', req_type])

    return jsonify({
        'success': True,
        'id': feedback_id,
        'type': req_type,
        'github_filed': bool(issue_url),
        'issue_url': issue_url,
    })
