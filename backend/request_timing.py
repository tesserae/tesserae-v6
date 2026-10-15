"""Record how long each API request takes, one line per request.

The hook does nothing unless the environment variable TESSERAE_TIMING_DIR
names an existing, writable directory (checked once, at install). Each
request whose path starts with /api/ appends one line to
<dir>/<YYYY-MM-DD>.tsv:

    time  method  path  status  ms  bytes  worker  visitor

The path has no query string and the body is never read, so no text a
visitor searched for is recorded.

The visitor column tells one visitor's requests from another's without
recording who they are: it is the first ten hex digits of a keyed hash
(HMAC-SHA256) of the day, the visitor's address and browser name. The key
is the site's session secret, which never leaves the server, and the day is
part of the hash, so a code cannot be traced back to an address and the
same visitor gets an unrelated code the next day. No address is written.
Requests from the server itself (the site's own checks and tools) are
written as "local" instead of a code. There is no lock and no rotation: lines
are written with a single write in append mode (atomic for short lines on
Linux, so three workers can share a file), and one file per day is the
rotation.
"""
import hashlib
import hmac
import logging
import os
import socket
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
_key = [b""]
_local = set()


def _secret():
    """The site's session secret, shared by every worker so one visitor gets
    the same code from all three. Without it each worker draws its own
    random key: codes then still never reveal an address but differ between
    workers."""
    s = (os.environ.get("SESSION_SECRET") or os.environ.get("SECRET_KEY") or "").strip()
    return s.encode("utf-8") if s else os.urandom(32)


def _local_addresses():
    """Addresses that mean the request came from this server."""
    out = {"127.0.0.1", "::1"}
    try:
        out.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    try:
        out.update(socket.gethostbyname_ex("tesserae.caset.buffalo.edu")[2])
    except OSError:
        pass
    extra = os.environ.get("TESSERAE_TIMING_LOCAL_ADDRS", "")
    out.update(a.strip() for a in extra.split(",") if a.strip())
    return out


def _visitor(day):
    try:
        addr = request.remote_addr or ""
        if addr in _local:
            return "local"
        ua = request.headers.get("User-Agent", "")
        msg = ("%s|%s|%s" % (day, addr, ua)).encode("utf-8", "replace")
        return hmac.new(_key[0] or b"-", msg, hashlib.sha256).hexdigest()[:10]
    except Exception:
        return "-"  # timing must never break a request


def _write(directory, status, ms, nbytes):
    t = time.time()
    sec = int(t)
    if _cache[0] != sec:
        lt = time.localtime(sec)
        _cache[:] = [sec, time.strftime("%Y-%m-%dT%H:%M:%S.", lt), time.strftime("%Y-%m-%d", lt)]
    line = "%s%03d\t%s\t%s\t%d\t%.1f\t%d\t%d\t%s\n" % (
        _cache[1], int((t - sec) * 1000), request.method, _full_path(),
        status, ms, nbytes, os.getpid(), _visitor(_cache[2]),
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
    _key[0] = _secret()
    _local.clear()
    _local.update(_local_addresses())

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
