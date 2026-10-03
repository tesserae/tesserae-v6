"""Job uploads: a GPU job on the campus cluster sends its result file back.

The cluster can fetch our inputs from the public jobs directory but had no
way to return anything larger than a log line (2026-10-03: a 1 GB vector
file). This route receives a file for a named job when the request carries
that job's token.

The token is a file on the server, data/job_uploads/<job>/.token, written
by scripts/jobs/new_upload_token.py before the job is submitted and read on
every request. It never lives in the environment or the code. A job name and
a file name are plain tokens (letters, digits, dot, dash, underscore), the
body streams to disk in pieces, and one upload may not exceed MAX_BYTES, so
a result is sent in parts. The reply carries the size and the SHA-256 so the
job can check what landed.
"""
import hashlib
import hmac
import os
import re

from flask import Blueprint, jsonify, request

job_uploads_bp = Blueprint('job_uploads', __name__)

UPLOAD_ROOT = os.environ.get('TESSERAE_JOB_UPLOADS', os.path.join('data', 'job_uploads'))
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$')
MAX_BYTES = 512 * 1024 * 1024
CHUNK = 4 * 1024 * 1024


def _token_for(job):
    path = os.path.join(UPLOAD_ROOT, job, '.token')
    try:
        with open(path, encoding='utf-8') as fh:
            return fh.read().strip()
    except OSError:
        return None


@job_uploads_bp.route('/jobs/upload/<job>/<name>', methods=['PUT', 'POST'])
def upload(job, name):
    if not NAME.match(job) or not NAME.match(name) or name.startswith('.'):
        return jsonify({'error': 'bad job or file name'}), 400
    expected = _token_for(job)
    given = request.headers.get('X-Job-Token', '')
    if not expected or not given or not hmac.compare_digest(expected, given):
        return jsonify({'error': 'no such job, or wrong token'}), 403
    declared = request.content_length
    if declared is not None and declared > MAX_BYTES:
        return jsonify({'error': f'too large; send parts of at most {MAX_BYTES} bytes'}), 413
    folder = os.path.join(UPLOAD_ROOT, job)
    os.makedirs(folder, exist_ok=True)
    final = os.path.join(folder, name)
    partial = final + '.part'
    digest = hashlib.sha256()
    size = 0
    with open(partial, 'wb') as out:
        while True:
            piece = request.stream.read(CHUNK)
            if not piece:
                break
            size += len(piece)
            if size > MAX_BYTES:
                out.close()
                os.unlink(partial)
                return jsonify({'error': f'too large; send parts of at most {MAX_BYTES} bytes'}), 413
            digest.update(piece)
            out.write(piece)
    os.replace(partial, final)
    return jsonify({'ok': True, 'job': job, 'name': name, 'bytes': size, 'sha256': digest.hexdigest()})
