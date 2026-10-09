"""
Tesserae V6 - Requests workflow blueprint

POST /api/feature-request — intake for every structured request a scholar or
their AI assistant can file: a feature, a language, a text, a bug, plus the
three entry points added for the requests workflow (2026-10-08):
    - result-problem:    "Report a problem with this result" (search results)
    - text-correction:   "Suggest a correction" (the Reader)
    - suggestion:        "Suggest a change" (footer / Help, page URL only)

GET /api/requests — a public, read-only mirror of the GitHub issues this
route has filed, for the site's own Requests page. See backend/github_requests.py.

Flow for each POST:
    1. Validate + rate-limit (per IP).
    2. Store privately in the `feedback` table (includes contact, if given).
    3. Email the team privately (includes contact).
    4. File a public GitHub issue, labelled "request" + "request:<type>", with
       the submitter's contact STRIPPED. This is now unconditional across every
       type -- GitHub issues are the single store of requests (owner's decision,
       2026-10-08) -- gated only by whether GitHub filing is configured at all
       (no token => the request still lands via DB + email, see
       backend/github_feedback.py).

Contact info (name, email) is kept private by this endpoint regardless of
type: it goes into the DB record and the private email, never the public
issue body.
"""
import os
import re
import time
import logging
import threading

from flask import Blueprint, jsonify, request

from backend.db_utils import get_db_cursor
from backend.email_notifications import send_notification
from backend.github_feedback import github_feedback_enabled, create_feedback_issue
from backend.github_requests import fetch_requests_listing

logger = logging.getLogger(__name__)

feature_request_bp = Blueprint('feature_request', __name__)

# The connector's original types (feature/language/text/bug/other) plus the
# three entry points the requests workflow added on the website side.
VALID_TYPES = {'feature', 'language', 'text', 'bug', 'other',
               'result-problem', 'text-correction', 'suggestion'}
VALID_SOURCES = {'ai', 'site'}
MAX_FIELD = 4000
MAX_MESSAGE_RAW = 8000   # above this, reject rather than silently truncate
MAX_TOTAL = 12000

_TAG_RE = re.compile(r'<[^>]+>')

# --- simple per-IP rate limit (mirrors the admin-login limiter) ---
_RL_MAX = int(os.environ.get('FEATURE_REQUEST_MAX_PER_HOUR', '5'))
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


def _strip_html(s):
    """Public issue bodies render as GitHub markdown; a submitted <tag> is
    dropped rather than trusted to be harmless markup."""
    return _TAG_RE.sub('', s or '')


def _field(data, name, limit=MAX_FIELD):
    v = data.get(name)
    return _strip_html(str(v)).strip()[:limit] if v else ''


def _too_long(data, name, limit=MAX_MESSAGE_RAW):
    v = data.get(name)
    return bool(v) and len(str(v)) > limit


def _format_context(context):
    """A readable, public-safe context block from either the connector's
    legacy free-text string or the structured object the website dialog
    sends (page URL, language, source/target citations, line refs, search
    type and settings, score, channels; or work/refs/selected text from the
    Reader)."""
    if not context:
        return ''
    if isinstance(context, str):
        return _strip_html(context)[:MAX_FIELD]
    if not isinstance(context, dict):
        return ''
    order = [
        ('page_url', 'Page'),
        ('language', 'Language'),
        ('search_type', 'Search type'),
        ('settings', 'Settings'),
        ('source', 'Source'),
        ('target', 'Target'),
        ('refs', 'Line refs'),
        ('score', 'Score'),
        ('channels', 'Channels'),
        ('work', 'Work'),
        ('selected_text', 'Selected text'),
    ]
    lines = []
    for key, label in order:
        v = context.get(key)
        if v is None or v == '':
            continue
        v = _strip_html(str(v)).strip()[:500]
        if v:
            lines.append(f"{label}: {v}")
    return "\n".join(lines)[:MAX_FIELD]


def _summary_line(title, message, problem, desired):
    base = title or message or problem or desired or ''
    base = _strip_html(base).replace('\n', ' ').strip()
    return base[:140]


@feature_request_bp.route('/feature-request', methods=['POST'])
def feature_request():
    data = request.get_json(silent=True) or {}

    req_type = (data.get('type') or 'feature').strip().lower()
    if req_type not in VALID_TYPES:
        req_type = 'other'

    source = (data.get('source') or 'ai').strip().lower()
    if source not in VALID_SOURCES:
        source = 'ai'

    for long_field in ('message', 'problem', 'desired', 'current_text', 'corrected_text'):
        if _too_long(data, long_field):
            return jsonify({'error': 'That message is too long. Please shorten it and '
                                     'try again.'}), 400

    title = _field(data, 'title')
    problem = _field(data, 'problem')
    desired = _field(data, 'desired')
    example = _field(data, 'example')
    tried = _field(data, 'tried')
    message = _field(data, 'message')
    current_text = _field(data, 'current_text')
    corrected_text = _field(data, 'corrected_text')
    context = data.get('context')
    name = _field(data, 'name', limit=200)
    contact = _field(data, 'contact', limit=200)   # email — kept PRIVATE (DB + email only)

    if not (title or problem or desired or message or current_text or corrected_text):
        return jsonify({'error': 'Please include at least a short description of '
                                 'what is wrong or what you would like to see.'}), 400

    if _rate_limited():
        return jsonify({'error': 'Too many requests from this address. '
                                 'Please try again later.'}), 429, {'Retry-After': str(_RL_WINDOW)}

    # --- public-safe body (NO contact) — shared by the DB record, email, and GitHub issue ---
    summary = _summary_line(title, message, problem, desired)
    ctx_block = _format_context(context)

    parts = []
    if summary:
        parts.append(f"Summary: {summary}")
    if title:
        parts.append(f"**Title:** {title}")
    parts.append(f"**Type:** {req_type}")
    if ctx_block:
        parts.append(f"**Context:**\n{ctx_block}")
    if message:
        parts.append(f"**Message:**\n{message}")
    if problem:
        parts.append(f"**Problem / need:**\n{problem}")
    if desired:
        parts.append(f"**Desired Tesserae behaviour:**\n{desired}")
    if example:
        parts.append(f"**Example:**\n{example}")
    if tried:
        parts.append(f"**Current workaround / what they tried:**\n{tried}")
    if current_text:
        parts.append(f"**Current text:**\n{current_text}")
    if corrected_text:
        parts.append(f"**Proposed text:**\n{corrected_text}")
    public_body = "\n\n".join(parts)[:MAX_TOTAL]
    public_body += "\n\n---\n_Filed via the Tesserae requests workflow._"

    feedback_id = None
    issue_url = None

    # --- (2) private DB record (feedback table), contact included ---
    try:
        with get_db_cursor() as cur:
            contact_note = ''
            if name:
                contact_note += f"\n\n[name: {name}]"
            if contact:
                contact_note += f"\n\n[contact: {contact}]"
            cur.execute(
                '''INSERT INTO feedback (name, email, feedback_type, message)
                   VALUES (%s, %s, %s, %s) RETURNING id''',
                (name or None, contact or None, f'{source}:{req_type}',
                 public_body + contact_note),
            )
            row = cur.fetchone()
            feedback_id = row[0] if row else None
    except Exception as e:
        logger.warning("feature_request DB insert failed: %s", e)

    # --- (3) private email to the team, contact included ---
    try:
        subject = f"New {req_type} request" + (f": {title}" if title else '')
        contact_line = ', '.join(x for x in (name, contact) if x)
        email_body = public_body + (
            f"\n\nContact (private): {contact_line}" if contact_line else "\n\nContact: not provided")
        send_notification(subject, email_body, 'feature_request')
    except Exception as e:
        logger.warning("feature_request email notify failed: %s", e)

    # --- (4) public GitHub issue, email STRIPPED. Every type now files one
    # (gated only by whether GitHub filing is configured; see
    # backend/github_feedback.py's kill switch). ---
    if github_feedback_enabled():
        gh_title = f"[{req_type}] " + (title or summary or f"{req_type} request")
        issue_url = create_feedback_issue(gh_title, public_body,
                                          ['request', f'request:{req_type}'])

    return jsonify({
        'success': True,
        'id': feedback_id,
        'type': req_type,
        'github_filed': bool(issue_url),
        'issue_url': issue_url,
    })


@feature_request_bp.route('/requests', methods=['GET'])
def requests_listing():
    """Public mirror of the GitHub issues this route files: grouped open vs.
    done for the site's Requests page. Never returns an issue body beyond
    its short public summary (see backend/github_requests.py)."""
    try:
        items = fetch_requests_listing()
    except Exception as e:
        logger.warning("requests_listing failed: %s", e)
        items = []

    open_items = sorted(
        (i for i in items if i['status'] in ('open', 'in progress')),
        key=lambda i: i.get('created_at') or '', reverse=True,
    )
    done_items = sorted(
        (i for i in items if i['status'] in ('done', 'declined')),
        key=lambda i: i.get('closed_at') or i.get('created_at') or '', reverse=True,
    )
    return jsonify({
        'open': open_items,
        'done': done_items,
        'github_enabled': github_feedback_enabled(),
    })
