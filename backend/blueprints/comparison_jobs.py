"""The download queue for comparisons above the live size limit (2026-10-24).

    POST /api/comparisons/jobs                  ask for the whole comparison as a file
    GET  /api/comparisons/jobs/<id>             status, place in the queue, file link
    GET  /api/comparisons/jobs/<id>/download    the CSV (gzip when over 20 MB)

A pair above COMPARE_MAX_LINE_PAIRS (backend/compare_limit.py) is not run live.
A visitor can queue it here instead. scripts/comparison_queue_runner.py, started
by a systemd user timer, takes the oldest queued job, one at a time, and writes
data/comparison_jobs/<id>.csv with the columns of the page's CSV export. Jobs and
files are removed after 14 days.

The visitor's own list is GET /api/comparisons/jobs (by the cookie).

Limits: two queued or running jobs per visitor (a cookie holds the token, only a
hash of it is stored) and twenty queued jobs in all.
"""
import hashlib
import json
import os
import re
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, send_file

from backend import compare_limit
from backend.logging_config import get_logger
from backend.models import db, ComparisonJob
from backend.utils import resolve_text_path

logger = get_logger('comparison_jobs')

comparison_jobs_bp = Blueprint('comparison_jobs', __name__)

_texts_dir = None

TOKEN_COOKIE = 'tess_compare_token'
MAX_PER_VISITOR = 2
MAX_QUEUED = 20
RETENTION_DAYS = 14
GZIP_OVER_BYTES = 20 * 1024 * 1024
JOBS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                        'data', 'comparison_jobs')

# The settings the page sends with a comparison that change its result or its
# cache entry (backend/blueprints/fusion.py _stream_params). Anything else is
# dropped, and every value is checked below.
_SETTING_KEYS = ('mode', 'max_results', 'source_unit_type', 'target_unit_type', 'use_meter',
                 'freq_basis', 'formula_max', 'formula_only', 'channel_weights', 'disabled_channels')
_EMAIL_RE = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,189}\.[^@\s]{2,}$')


def init_comparison_jobs_blueprint(texts_dir):
    global _texts_dir
    _texts_dir = texts_dir


def _hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def clean_settings(raw):
    """The settings worth keeping, each checked; unknown keys and bad values are dropped."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    if raw.get('mode') in ('line', 'window', 'merged'):
        out['mode'] = raw['mode']
    mr = raw.get('max_results')
    if isinstance(mr, int) and not isinstance(mr, bool) and 0 < mr <= 100000:
        out['max_results'] = mr
    for k in ('source_unit_type', 'target_unit_type'):
        if raw.get(k) in ('line', 'phrase'):
            out[k] = raw[k]
    for k in ('use_meter', 'formula_only'):
        if isinstance(raw.get(k), bool):
            out[k] = raw[k]
    if raw.get('freq_basis') in ('corpus', 'meter', 'text_pair'):
        out['freq_basis'] = raw['freq_basis']
    fm = raw.get('formula_max')
    if isinstance(fm, int) and not isinstance(fm, bool) and fm >= 0:
        out['formula_max'] = fm
    cw = raw.get('channel_weights')
    if isinstance(cw, dict):
        out['channel_weights'] = {str(k): v for k, v in cw.items()
                                  if isinstance(v, (int, float)) and not isinstance(v, bool)}
    dc = raw.get('disabled_channels')
    if isinstance(dc, list):
        out['disabled_channels'] = [str(c) for c in dc][:30]
    return out


def queue_position(job):
    """1 for the job the runner takes next; None unless the job is queued."""
    if job.status != 'queued':
        return None
    ahead = ComparisonJob.query.filter(ComparisonJob.status == 'queued',
                                       ComparisonJob.created < job.created).count()
    return ahead + 1


def job_view(job):
    """The status answer for one job."""
    out = {
        'id': job.id,
        'status': job.status,
        'source': job.source,
        'target': job.target,
        'language': job.language,
        'created': job.created.isoformat() if job.created else None,
        'started': job.started.isoformat() if job.started else None,
        'finished': job.finished.isoformat() if job.finished else None,
        'line_pairs': job.line_pairs,
        'retention_days': RETENTION_DAYS,
        'email_notice': compare_limit.email_notice_available(),
    }
    if job.status == 'queued':
        out['position'] = queue_position(job)
        out['running_now'] = ComparisonJob.query.filter_by(status='running').count()
    if job.status == 'done':
        out['rows'] = job.rows
        out['download_url'] = f'/api/comparisons/jobs/{job.id}/download'
        out['expires'] = ((job.finished + timedelta(days=RETENTION_DAYS)).isoformat()
                          if job.finished else None)
    if job.status == 'failed':
        out['error'] = 'The comparison did not finish. Choose books to compare now, or ask again later.'
    return out


@comparison_jobs_bp.route('/comparisons/jobs', methods=['POST'])
def create_job():
    data = request.get_json(silent=True) or {}
    source = data.get('source')
    target = data.get('target')
    language = data.get('language') or 'la'
    if not isinstance(source, str) or not isinstance(target, str) or not source or not target \
            or not isinstance(language, str):
        return jsonify({'error': 'Please select both source and target texts.'}), 400
    if not resolve_text_path(_texts_dir, language, source) or \
            not resolve_text_path(_texts_dir, language, target):
        return jsonify({'error': 'Text files not found.'}), 404
    gate = compare_limit.check_size(_texts_dir, language, source, target)
    if not gate:
        return jsonify({'error': 'This pair is under the size limit and runs on the page, so no '
                                 'download is prepared for it.', 'runs_live': True}), 400
    email = data.get('email')
    if email in (None, ''):
        email = None
    elif not isinstance(email, str) or not _EMAIL_RE.match(email.strip()) or len(email.strip()) > 254:
        return jsonify({'error': 'That email address does not look right.'}), 400
    else:
        email = email.strip()

    token = request.cookies.get(TOKEN_COOKIE) or ''
    new_token = not re.match(r'^[A-Za-z0-9_-]{20,64}$', token)
    if new_token:
        token = secrets.token_urlsafe(24)
    owner = _hash(token)

    open_states = ('queued', 'running')
    mine = ComparisonJob.query.filter(ComparisonJob.owner_token == owner,
                                      ComparisonJob.status.in_(open_states)).count()
    if mine >= MAX_PER_VISITOR:
        return jsonify({'error': f'You already have {MAX_PER_VISITOR} comparisons waiting. '
                                 'Wait for one to finish before asking for another.'}), 429
    if ComparisonJob.query.filter_by(status='queued').count() >= MAX_QUEUED:
        return jsonify({'error': 'The download queue is full. Please try again later, '
                                 'or choose books to compare now.'}), 503

    job = ComparisonJob(
        id=secrets.token_urlsafe(12).replace('-', 'x').replace('_', 'y'),
        source=source, target=target, language=language,
        settings=json.dumps(clean_settings(data.get('settings'))),
        status='queued', email=email, owner_token=owner,
        line_pairs=gate['line_pairs'], created=datetime.now())
    db.session.add(job)
    db.session.commit()
    resp = jsonify(job_view(job))
    resp.status_code = 201
    if new_token:
        resp.set_cookie(TOKEN_COOKIE, token, max_age=RETENTION_DAYS * 86400, path='/',
                        httponly=True, samesite='Lax', secure=request.is_secure)
    return resp


def _get_job(job_id):
    if not re.match(r'^[A-Za-z0-9]{6,40}$', job_id or ''):
        return None
    return db.session.get(ComparisonJob, job_id)


@comparison_jobs_bp.route('/comparisons/jobs', methods=['GET'])
def my_jobs():
    """The visitor's own jobs of the last 14 days, newest first, found by the cookie token."""
    token = request.cookies.get(TOKEN_COOKIE) or ''
    if not re.match(r'^[A-Za-z0-9_-]{20,64}$', token):
        return jsonify({'jobs': []})
    since = datetime.now() - timedelta(days=RETENTION_DAYS)
    rows = (ComparisonJob.query.filter(ComparisonJob.owner_token == _hash(token),
                                       ComparisonJob.created >= since)
            .order_by(ComparisonJob.created.desc()).limit(20).all())
    return jsonify({'jobs': [job_view(j) for j in rows]})


@comparison_jobs_bp.route('/comparisons/jobs/<job_id>', methods=['GET'])
def job_status(job_id):
    job = _get_job(job_id)
    if job is None:
        return jsonify({'error': 'No such comparison. Files are kept '
                                 f'{RETENTION_DAYS} days.'}), 404
    return jsonify(job_view(job))


@comparison_jobs_bp.route('/comparisons/jobs/<job_id>/download', methods=['GET'])
def job_download(job_id):
    job = _get_job(job_id)
    if job is None:
        return jsonify({'error': 'No such comparison.'}), 404
    if job.status != 'done' or not job.file_path:
        return jsonify({'error': 'This comparison is not ready yet.', 'status': job.status}), 409
    path = os.path.realpath(job.file_path)
    if os.path.commonpath([os.path.realpath(JOBS_DIR), path]) != os.path.realpath(JOBS_DIR) \
            or not os.path.exists(path):
        return jsonify({'error': 'The file has been removed. Files are kept '
                                 f'{RETENTION_DAYS} days.'}), 410
    gz = path.endswith('.gz')
    name = f'tesserae_comparison_{job.id}.csv' + ('.gz' if gz else '')
    return send_file(path, mimetype='application/gzip' if gz else 'text/csv',
                     as_attachment=True, download_name=name)
