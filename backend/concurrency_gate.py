"""Concurrency gate for heavy search operations.

Prevents out-of-memory crashes when multiple users run expensive searches
simultaneously. Uses file-based locking (fcntl.flock) to coordinate across
Apache mod_wsgi worker processes, which share no Python state.

How it works:
    Each active heavy search creates a "slot file" in a lock directory and
    holds an exclusive flock on it for the search's duration. Before starting,
    a new search counts how many slot files are currently locked (i.e., held
    by live processes). If the count exceeds MAX_HEAVY_SEARCHES, the search
    waits and yields "queued" SSE events so the frontend can show a message.

    A memory safety valve also prevents new searches from starting when
    available RAM is below MEMORY_THRESHOLD_GB, regardless of slot count.

Crash safety:
    When a process dies, the OS releases its flock automatically, so stale
    slot files are detectable (they can be locked by the counting routine)
    and are cleaned up on the next acquisition attempt.

Configuration (environment variables):
    TESSERAE_MAX_HEAVY_SEARCHES  -- max concurrent heavy searches (default: 2)
    TESSERAE_MEMORY_THRESHOLD_GB -- min available GB to start a search (default: 8)
    TESSERAE_QUEUE_TIMEOUT       -- max seconds to wait in queue (default: 300)
    TESSERAE_QUEUE_POLL_INTERVAL -- seconds between retry attempts (default: 2.0)

Runtime configuration:
    Use ConcurrencyConfig class methods to adjust settings at runtime
    without restarting the server (e.g., from admin API endpoints).

Usage in an SSE generator:
    slot = SearchSlot()
    for queued_event in slot.acquire():
        yield format_sse_event("queued", queued_event)
    try:
        ... run heavy search ...
    finally:
        slot.release()

Usage in a synchronous endpoint:
    with SearchSlot() as slot:
        ... run heavy search ...
    # slot is released automatically on exit (or on exception)
"""

import fcntl
import os
import time
import threading
import logging

from backend.memory_util import get_available_memory_gb

logger = logging.getLogger(__name__)

# Use a project-local directory instead of /tmp so lock files are visible
# and cleanable even when Apache runs with PrivateTmp=yes.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCK_DIR = os.environ.get(
    'TESSERAE_LOCK_DIR', os.path.join(_PROJECT_ROOT, 'tmp', 'search_slots'))


def _ensure_lock_dir():
    """Create the lock directory if it doesn't exist."""
    os.makedirs(LOCK_DIR, exist_ok=True)


def _count_active_slots():
    """Count how many slot files are currently held by live processes.

    Tries to acquire an exclusive lock on each .lock file. If the lock
    fails (EWOULDBLOCK), the file is held by a live process. If it
    succeeds, the file is stale (the holding process died) and is
    cleaned up.

    Returns the number of actively held slots.
    """
    _ensure_lock_dir()
    active = 0
    for name in os.listdir(LOCK_DIR):
        if not name.endswith('.lock'):
            continue
        path = os.path.join(LOCK_DIR, name)
        try:
            fd = os.open(path, os.O_RDWR)
            try:
                # Try to lock it -- if we can, the original holder is dead
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Stale file: unlock and delete
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
                try:
                    os.unlink(path)
                    logger.info("Cleaned up stale slot file: %s", name)
                except OSError:
                    pass
            except BlockingIOError:
                # File is held by a live process
                os.close(fd)
                active += 1
        except OSError:
            pass
    return active


class ConcurrencyConfig:
    """Thread-safe runtime-configurable concurrency settings."""
    _lock = threading.Lock()

    # Defaults (captured at import time from env vars)
    _default_max = int(os.environ.get('TESSERAE_MAX_HEAVY_SEARCHES', '2'))
    _default_mem = float(os.environ.get('TESSERAE_MEMORY_THRESHOLD_GB', '8'))
    _default_timeout = float(os.environ.get('TESSERAE_QUEUE_TIMEOUT', '300'))
    _default_poll = float(os.environ.get('TESSERAE_QUEUE_POLL_INTERVAL', '2.0'))

    # Current values (mutable)
    _max_heavy_searches = _default_max
    _memory_threshold_gb = _default_mem
    _queue_timeout = _default_timeout
    _queue_poll_interval = _default_poll
    _stress_test_mode = False

    @classmethod
    def get_max_searches(cls):
        with cls._lock:
            return cls._max_heavy_searches

    @classmethod
    def set_max_searches(cls, value):
        value = int(value)
        if not (1 <= value <= 50):
            raise ValueError(f"max_searches must be between 1 and 50, got {value}")
        with cls._lock:
            cls._max_heavy_searches = value

    @classmethod
    def get_memory_threshold(cls):
        with cls._lock:
            return cls._memory_threshold_gb

    @classmethod
    def set_memory_threshold(cls, value):
        value = float(value)
        if not (0.5 <= value <= 128):
            raise ValueError(f"memory_threshold_gb must be between 0.5 and 128, got {value}")
        with cls._lock:
            cls._memory_threshold_gb = value

    @classmethod
    def get_queue_timeout(cls):
        with cls._lock:
            return cls._queue_timeout

    @classmethod
    def set_queue_timeout(cls, value):
        value = float(value)
        if not (30 <= value <= 3600):
            raise ValueError(f"queue_timeout must be between 30 and 3600, got {value}")
        with cls._lock:
            cls._queue_timeout = value

    @classmethod
    def get_queue_poll_interval(cls):
        with cls._lock:
            return cls._queue_poll_interval

    @classmethod
    def set_queue_poll_interval(cls, value):
        value = float(value)
        if not (0.5 <= value <= 10):
            raise ValueError(f"queue_poll_interval must be between 0.5 and 10, got {value}")
        with cls._lock:
            cls._queue_poll_interval = value

    @classmethod
    def is_stress_test_mode(cls):
        with cls._lock:
            return cls._stress_test_mode

    @classmethod
    def set_stress_test_mode(cls, enabled: bool):
        with cls._lock:
            cls._stress_test_mode = bool(enabled)

    @classmethod
    def reset_to_defaults(cls):
        with cls._lock:
            cls._max_heavy_searches = cls._default_max
            cls._memory_threshold_gb = cls._default_mem
            cls._queue_timeout = cls._default_timeout
            cls._queue_poll_interval = cls._default_poll
            cls._stress_test_mode = False

    @classmethod
    def get_status(cls):
        """Return config values plus live system data."""
        with cls._lock:
            config = {
                'max_searches': cls._max_heavy_searches,
                'memory_threshold_gb': cls._memory_threshold_gb,
                'queue_timeout': cls._queue_timeout,
                'queue_poll_interval': cls._queue_poll_interval,
                'stress_test_mode': cls._stress_test_mode,
                'active_searches': _count_active_slots(),
                'available_memory_gb': round(get_available_memory_gb(), 1),
                'defaults': {
                    'max_searches': cls._default_max,
                    'memory_threshold_gb': cls._default_mem,
                    'queue_timeout': cls._default_timeout,
                    'queue_poll_interval': cls._default_poll,
                },
            }
        return config

    @classmethod
    def to_dict(cls):
        """Return just the config values (no live data)."""
        with cls._lock:
            return {
                'max_searches': cls._max_heavy_searches,
                'memory_threshold_gb': cls._memory_threshold_gb,
                'queue_timeout': cls._queue_timeout,
                'queue_poll_interval': cls._queue_poll_interval,
                'stress_test_mode': cls._stress_test_mode,
            }


# Backward-compatible module-level accessors (read from ConcurrencyConfig)
MAX_HEAVY_SEARCHES = ConcurrencyConfig.get_max_searches()
MEMORY_THRESHOLD_GB = ConcurrencyConfig.get_memory_threshold()
QUEUE_POLL_INTERVAL = ConcurrencyConfig.get_queue_poll_interval()
QUEUE_TIMEOUT = ConcurrencyConfig.get_queue_timeout()


class SearchSlot:
    """Context manager / generator for acquiring a heavy-search slot.

    Can be used two ways:

    1. Generator (for SSE endpoints) -- yields queued status dicts:
        slot = SearchSlot()
        for event in slot.acquire():
            yield sse_format(event)
        try:
            ... heavy work ...
        finally:
            slot.release()

    2. Context manager (for synchronous endpoints) -- blocks until acquired:
        with SearchSlot() as slot:
            ... heavy work ...
    """

    def __init__(self):
        self._fd = None
        self._path = None
        self._acquired = False

    def _create_slot_file(self):
        """Create a unique slot file and lock it."""
        _ensure_lock_dir()
        name = f"slot_{os.getpid()}_{id(self)}_{time.monotonic_ns()}.lock"
        self._path = os.path.join(LOCK_DIR, name)
        self._fd = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(self._fd, fcntl.LOCK_EX)

    def _remove_slot_file(self):
        """Release the lock and delete the slot file."""
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        if self._path is not None:
            try:
                os.unlink(self._path)
            except OSError:
                pass
            self._path = None
        self._acquired = False

    def _can_proceed(self):
        """Check whether a slot is available and memory is sufficient.

        Returns (ok, reason) where reason explains why we're blocked.
        """
        # Memory check (skipped in stress test mode)
        if not ConcurrencyConfig.is_stress_test_mode():
            mem_gb = get_available_memory_gb()
            threshold = ConcurrencyConfig.get_memory_threshold()
            if mem_gb < threshold:
                return False, (
                    f"Server memory low ({mem_gb:.0f} GB available, "
                    f"need {threshold:.0f} GB)")

        max_searches = ConcurrencyConfig.get_max_searches()
        active = _count_active_slots()
        if active >= max_searches:
            return False, (
                f"Server is running {active} searches "
                f"(max {max_searches})")

        return True, ""

    def acquire(self):
        """Generator that yields queued-status dicts until a slot is acquired.

        Each yielded dict has the form:
            {"status": "queued", "reason": "...", "wait_time": seconds_waited}

        When the generator returns (StopIteration), the slot is held.
        Raises TimeoutError if queue_timeout is exceeded.
        """
        start = time.monotonic()

        while True:
            ok, reason = self._can_proceed()
            if ok:
                self._create_slot_file()
                self._acquired = True
                logger.info(
                    "Search slot acquired (pid=%d, waited=%.1fs)",
                    os.getpid(), time.monotonic() - start)
                return  # slot acquired, generator ends

            waited = time.monotonic() - start
            queue_timeout = ConcurrencyConfig.get_queue_timeout()
            if waited >= queue_timeout:
                raise TimeoutError(
                    f"Search queue timeout after {queue_timeout}s: {reason}")

            yield {
                "status": "queued",
                "reason": reason,
                "wait_time": round(waited, 1),
            }
            time.sleep(ConcurrencyConfig.get_queue_poll_interval())

    def release(self):
        """Explicitly release the slot. Safe to call multiple times."""
        if self._acquired:
            logger.info("Search slot released (pid=%d)", os.getpid())
            self._remove_slot_file()

    # Context manager interface (for synchronous endpoints)
    def __enter__(self):
        # Block until acquired (consume all queued events silently)
        for _ in self.acquire():
            pass
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False

    def __del__(self):
        # Safety net: release on garbage collection
        self._remove_slot_file()
