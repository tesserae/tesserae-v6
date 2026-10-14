"""Record how long each API request takes, one line per request.

The hook does nothing unless the environment variable TESSERAE_TIMING_DIR
names an existing, writable directory (checked once, at install). Each
request whose path starts with /api/ appends one line to
<dir>/<YYYY-MM-DD>.tsv:

    time  method  path  status  ms  bytes  worker

The path has no query string and the body is never read, so no text a
visitor searched for is recorded. There is no lock and no rotation: lines
are written with a single write in append mode (atomic for short lines on
Linux, so three workers can share a file), and one file per day is the
rotation.
"""
import logging
import os
import time

from flask import g, request

logger = logging.getLogger(__name__)

ENV_VAR = "TESSERAE_TIMING_DIR"
PREFIX = "/api/"


def _full_path():
    """The path as the visitor sent it. On the live site Apache mounts the
    application under /api (WSGIScriptAlias), so inside Flask request.path is
    "/languages" and the mount point sits in request.script_root; the development
    server mounts at the root and request.path is already "/api/languages"."""
    return (request.script_root or "") + request.path


_cache = [0, "", ""]  # whole second, "YYYY-MM-DDTHH:MM:SS.", "YYYY-MM-DD"


def _write(directory, status, ms, nbytes):
    t = time.time()
    sec = int(t)
    if _cache[0] != sec:
        lt = time.localtime(sec)
        _cache[:] = [sec, time.strftime("%Y-%m-%dT%H:%M:%S.", lt), time.strftime("%Y-%m-%d", lt)]
    line = "%s%03d\t%s\t%s\t%d\t%.1f\t%d\t%d\n" % (
        _cache[1], int((t - sec) * 1000), request.method, _full_path(),
        status, ms, nbytes, os.getpid(),
    )
    try:
        fd = os.open(os.path.join(directory, _cache[2] + ".tsv"),
                     os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o664)
        try:
            os.write(fd, line.encode("utf-8")[:4000])
        finally:
            os.close(fd)
    except OSError:
        pass  # timing must never break a request


def install(app):
    """Register the timing hooks on app. Returns True when recording."""
    directory = os.environ.get(ENV_VAR, "").strip()
    if not directory or not os.path.isdir(directory) or not os.access(directory, os.W_OK):
        if directory:
            logger.info("Request timing off: %s=%s is not a writable directory", ENV_VAR, directory)
        return False
    logger.info("Request timing on: writing to %s", directory)

    @app.before_request
    def _timing_start():
        g._timing_t0 = time.perf_counter()
        g._timing_done = False

    @app.after_request
    def _timing_after(response):
        t0 = getattr(g, "_timing_t0", None)
        if t0 is not None and not g.get("_timing_done") and _full_path().startswith(PREFIX):
            g._timing_done = True
            # Only a response already held in memory is measured. Asking a
            # streamed response (the fusion search's progress events, the
            # downloads) for its length makes Werkzeug read the whole stream
            # first, so nothing reached the browser until the search was over
            # (2026-10-13, the morning after this hook went live). For a
            # stream the time recorded is the time to its first byte.
            nbytes = response.calculate_content_length() if response.is_sequence else None
            _write(directory, response.status_code, (time.perf_counter() - t0) * 1000.0,
                   -1 if nbytes is None else nbytes)
        return response

    @app.teardown_request
    def _timing_teardown(exc):
        t0 = getattr(g, "_timing_t0", None)
        if exc is not None and t0 is not None and not g.get("_timing_done") \
                and _full_path().startswith(PREFIX):
            g._timing_done = True
            _write(directory, 500, (time.perf_counter() - t0) * 1000.0, -1)

    return True
