"""
Generic start-and-poll wrapper for light search endpoints.

Many consumer AI assistants can only fetch a URL and give up after ~30 seconds,
so a search that runs longer (e.g. rare-words over two large texts) can never
complete synchronously for them. This helper exposes any synchronous compute as
a poll-able GET, mirroring the fusion GET-poll pattern in ``fusion.py``:

  * the first GET starts the work in a background thread and returns
    ``{"status": "running"}``;
  * subsequent GETs to the same URL return ``{"status": "complete", ...}`` once
    the result is cached, or ``{"status": "error", ...}`` once (then retry).

Cross-worker de-duplication uses a ``.running`` marker file in the shared,
file-based cache dir, so concurrent mod_wsgi workers don't start the same job
twice. Results are cached to disk keyed on the job parameters.
"""
import os
import json
import time
import hashlib
import threading
import logging

from flask import jsonify

from backend.cache import CACHE_DIR, ensure_cache_dir

logger = logging.getLogger(__name__)

# A 'running' marker older than this is treated as stale (the worker died), so
# the next poll restarts the job rather than reporting 'running' forever.
POLL_MARKER_TTL = 1800  # 30 min


class SearchInputError(Exception):
    """A user/input error in a search (bad params, text not found, index
    missing). The synchronous route maps ``status`` to an HTTP code; the poll
    runner stores the message as the job error."""

    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def make_job_key(name, *parts):
    """Stable job key from the endpoint name and its parameters."""
    raw = name + '|' + '|'.join('' if p is None else str(p) for p in parts)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]


def _paths(name, key):
    stem = os.path.join(CACHE_DIR, f"asyncjob_{name}_{key}")
    return stem + '.json', stem + '.running', stem + '.error'


def _run(name, key, compute):
    """Run ``compute()`` in a background thread and persist its result/err."""
    result_path, run_path, err_path = _paths(name, key)
    try:
        data = compute()
        tmp = result_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        os.replace(tmp, result_path)
    except Exception as e:  # noqa: BLE001 — surface any failure to the poller
        logger.error("async job %s failed: %s", name, e, exc_info=True)
        try:
            with open(err_path, 'w', encoding='utf-8') as f:
                f.write(str(e)[:500])
        except IOError:
            pass
    finally:
        try:
            os.remove(run_path)
        except OSError:
            pass


def poll(name, key, compute, transform=None, poll_seconds=25):
    """Return a Flask JSON response implementing the start-and-poll protocol.

    Args:
        name: short endpoint name (e.g. 'hapax') — namespaces the cache files.
        key: job key from :func:`make_job_key`.
        compute: zero-arg callable returning a JSON-serializable dict. It runs in
            a background thread and MUST NOT touch ``flask.request`` or the DB.
        transform: optional ``fn(result_dict) -> dict`` to slim/cap what the poll
            returns to the caller (the full result is still cached).
        poll_seconds: hint told to the caller for how long to wait between polls.
    """
    ensure_cache_dir()
    result_path, run_path, err_path = _paths(name, key)

    # Complete?
    if os.path.exists(result_path):
        try:
            with open(result_path, encoding='utf-8') as f:
                data = json.load(f)
            for p in (run_path, err_path):
                try:
                    os.remove(p)
                except OSError:
                    pass
            out = dict(transform(data) if transform else data)
            out['status'] = 'complete'
            out['cached'] = True
            return jsonify(out)
        except (IOError, ValueError):
            pass  # unreadable cache — fall through and recompute

    # Prior failure? Surface it once, then clear so the next call retries.
    if os.path.exists(err_path):
        try:
            with open(err_path, encoding='utf-8') as f:
                err = f.read()
        except IOError:
            err = 'unknown error'
        try:
            os.remove(err_path)
        except OSError:
            pass
        return jsonify({'status': 'error', 'error': err,
                        'message': 'The search failed; call the same URL again to retry.'}), 500

    # Already running (fresh marker)?
    if os.path.exists(run_path) and (time.time() - os.path.getmtime(run_path)) < POLL_MARKER_TTL:
        return jsonify({'status': 'running',
                        'message': f'Working. Poll this same URL again in ~{poll_seconds}s '
                                   'until status is "complete".'})

    # Start a new background run.
    try:
        with open(run_path, 'w', encoding='utf-8') as f:
            f.write('')
    except IOError:
        pass
    threading.Thread(target=_run, args=(name, key, compute), daemon=True).start()
    return jsonify({'status': 'running',
                    'message': f'Search started. Poll this same URL again in ~{poll_seconds}s '
                               'until status is "complete".'})
