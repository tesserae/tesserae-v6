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
import json
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


import signal

EMERGENCY_MEMORY_FLOOR_GB = 3.0


def _ensure_lock_dir():
    """Create the lock directory if it doesn't exist."""
    os.makedirs(LOCK_DIR, exist_ok=True)


def get_active_searches_list():
    """Return a list of dicts describing currently active searches.

    Each dict contains: pid, slot_file, source_id, target_id, match_type, start_time, runtime.
    """
    _ensure_lock_dir()
    searches = []
    now = time.time()
    for name in os.listdir(LOCK_DIR):
        if not name.endswith('.lock'):
            continue
        path = os.path.join(LOCK_DIR, name)
        try:
            fd = os.open(path, os.O_RDWR)
            try:
                # Try non-blocking lock -- if it succeeds, file is stale
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
                try:
                    os.unlink(path)
                except OSError:
                    pass
            except BlockingIOError:
                # File is actively held -- read metadata
                meta = {}
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    content = os.read(fd, 4096).decode('utf-8', errors='ignore').strip()
                    if content:
                        meta = json.loads(content)
                except (OSError, json.JSONDecodeError):
                    pass
                finally:
                    os.close(fd)

                pid = meta.get('pid')
                if not pid:
                    parts = name.split('_')
                    if len(parts) >= 2 and parts[1].isdigit():
                        pid = int(parts[1])

                start_ts = meta.get('start_time', now)
                runtime = round(now - start_ts, 1)

                searches.append({
                    'pid': pid,
                    'slot_file': name,
                    'source_id': meta.get('source_id', 'Unknown'),
                    'target_id': meta.get('target_id', 'Unknown'),
                    'match_type': meta.get('match_type', 'Unknown'),
                    'start_time': start_ts,
                    'runtime': runtime
                })
        except OSError:
            pass
    return searches


def _count_active_slots():
    """Count how many slot files are currently held by live processes."""
    return len(get_active_searches_list())


def kill_active_search(pid):
    """Terminate an active search process by PID and clean up its slot file.

    Returns True if killed/cleaned up, False if not found.
    """
    _ensure_lock_dir()
    found = False
    for name in os.listdir(LOCK_DIR):
        if not name.endswith('.lock'):
            continue
        if f"_{pid}_" in name:
            path = os.path.join(LOCK_DIR, name)
            try:
                os.unlink(path)
            except OSError:
                pass
            found = True

    if pid and pid != os.getpid():
        try:
            os.kill(pid, signal.SIGTERM)
            logger.info("Sent SIGTERM to active search PID %d", pid)
            found = True
        except ProcessLookupError:
            pass
        except OSError as e:
            logger.error("Failed to kill search PID %d: %s", pid, e)

    return found


def _reap_newest_active_slot():
    """Emergency reaper: aborts the newest active search when RAM hits critical floor (<3 GB)."""
    searches = get_active_searches_list()
    # Filter out current process
    other_searches = [s for s in searches if s.get('pid') != os.getpid()]
    if not other_searches:
        return False
    # Sort newest first
    other_searches.sort(key=lambda s: s.get('start_time', 0), reverse=True)
    newest = other_searches[0]
    pid = newest.get('pid')
    logger.warning("Emergency RAM Reaper terminating PID %d (%s vs %s) due to critical memory",
                   pid, newest.get('source_id'), newest.get('target_id'))
    return kill_active_search(pid)


class ConcurrencyConfig:
    """Runtime-configurable concurrency settings shared across worker processes.

    Settings are persisted to a shared JSON file so that all Apache mod_wsgi
    worker processes read the same values.  A short in-process cache (5 s)
    avoids hitting the filesystem on every search check.
    """
    _lock = threading.Lock()

    # Defaults (captured at import time from env vars)
    _default_max = int(os.environ.get('TESSERAE_MAX_HEAVY_SEARCHES', '2'))
    _default_mem = float(os.environ.get('TESSERAE_MEMORY_THRESHOLD_GB', '8'))
    _default_timeout = float(os.environ.get('TESSERAE_QUEUE_TIMEOUT', '300'))
    _default_poll = float(os.environ.get('TESSERAE_QUEUE_POLL_INTERVAL', '2.0'))

    # Shared config file — lives next to lock files, accessible to all workers
    _CONFIG_FILE = os.path.join(_PROJECT_ROOT, 'data', 'concurrency_config.json')

    # In-process cache with TTL
    _cache = None           # dict or None
    _cache_ts = 0.0         # monotonic timestamp of last file read
    _CACHE_TTL = 5.0        # seconds before re-reading the file

    # ------------------------------------------------------------------
    # Internal: file I/O helpers
    # ------------------------------------------------------------------

    @classmethod
    def _read_file(cls):
        """Read config from shared JSON file; return dict or None."""
        try:
            with open(cls._CONFIG_FILE, 'r') as f:
                return json.load(f)
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    @classmethod
    def _write_file(cls, data):
        """Atomically write config to the shared JSON file."""
        os.makedirs(os.path.dirname(cls._CONFIG_FILE), exist_ok=True)
        tmp_path = cls._CONFIG_FILE + '.tmp'
        try:
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, cls._CONFIG_FILE)   # atomic on POSIX
        except OSError as e:
            logger.error("Failed to write concurrency config file: %s", e)
            raise

    @classmethod
    def _get_cached_config(cls):
        """Return current config, refreshing from file if cache is stale."""
        now = time.monotonic()
        if cls._cache is not None and (now - cls._cache_ts) < cls._CACHE_TTL:
            return cls._cache

        file_data = cls._read_file()
        if file_data is not None:
            cls._cache = file_data
            cls._cache_ts = now
            return cls._cache

        # No file yet — return env-var defaults
        defaults = cls._defaults_dict()
        cls._cache = defaults
        cls._cache_ts = now
        return defaults

    @classmethod
    def _defaults_dict(cls):
        return {
            'max_searches': cls._default_max,
            'memory_threshold_gb': cls._default_mem,
            'queue_timeout': cls._default_timeout,
            'queue_poll_interval': cls._default_poll,
            'stress_test_mode': False,
            'stress_test_enabled_at': 0,
        }

    @classmethod
    def _is_stress_test_active(cls, cfg):
        """Internal helper to check if stress test mode is active and not expired (1 hour TTL)."""
        if not cfg.get('stress_test_mode', False):
            return False
        # Auto-expire after 3600 seconds (1 hour)
        enabled_at = cfg.get('stress_test_enabled_at', 0)
        return (time.time() - enabled_at) < 3600

    @classmethod
    def _update_and_persist(cls, key, value):
        """Update one key, write to file, and bust the cache."""
        cfg = cls._get_cached_config().copy()
        cfg[key] = value
        cls._write_file(cfg)
        cls._cache = cfg
        cls._cache_ts = time.monotonic()

    # ------------------------------------------------------------------
    # Public getters (read through cache → shared file)
    # ------------------------------------------------------------------

    @classmethod
    def get_max_searches(cls):
        with cls._lock:
            return cls._get_cached_config().get('max_searches', cls._default_max)

    @classmethod
    def get_memory_threshold(cls):
        with cls._lock:
            return cls._get_cached_config().get('memory_threshold_gb', cls._default_mem)

    @classmethod
    def get_queue_timeout(cls):
        with cls._lock:
            return cls._get_cached_config().get('queue_timeout', cls._default_timeout)

    @classmethod
    def get_queue_poll_interval(cls):
        with cls._lock:
            return cls._get_cached_config().get('queue_poll_interval', cls._default_poll)

    @classmethod
    def is_stress_test_mode(cls):
        with cls._lock:
            return cls._is_stress_test_active(cls._get_cached_config())

    # ------------------------------------------------------------------
    # Public setters (validate, persist to file, bust cache)
    # ------------------------------------------------------------------

    @classmethod
    def set_max_searches(cls, value):
        value = int(value)
        if not (1 <= value <= 50):
            raise ValueError(f"max_searches must be between 1 and 50, got {value}")
        with cls._lock:
            cls._update_and_persist('max_searches', value)

    @classmethod
    def set_memory_threshold(cls, value):
        value = float(value)
        if not (0.5 <= value <= 128):
            raise ValueError(f"memory_threshold_gb must be between 0.5 and 128, got {value}")
        with cls._lock:
            cls._update_and_persist('memory_threshold_gb', value)

    @classmethod
    def set_queue_timeout(cls, value):
        value = float(value)
        if not (30 <= value <= 3600):
            raise ValueError(f"queue_timeout must be between 30 and 3600, got {value}")
        with cls._lock:
            cls._update_and_persist('queue_timeout', value)

    @classmethod
    def set_queue_poll_interval(cls, value):
        value = float(value)
        if not (0.5 <= value <= 10):
            raise ValueError(f"queue_poll_interval must be between 0.5 and 10, got {value}")
        with cls._lock:
            cls._update_and_persist('queue_poll_interval', value)

    @classmethod
    def set_stress_test_mode(cls, enabled: bool):
        with cls._lock:
            cfg = cls._get_cached_config().copy()
            cfg['stress_test_mode'] = bool(enabled)
            if enabled:
                cfg['stress_test_enabled_at'] = time.time()
            cls._write_file(cfg)
            cls._cache = cfg
            cls._cache_ts = time.monotonic()

    # ------------------------------------------------------------------
    # Reset / status
    # ------------------------------------------------------------------

    @classmethod
    def reset_to_defaults(cls):
        with cls._lock:
            defaults = cls._defaults_dict()
            cls._write_file(defaults)
            cls._cache = defaults
            cls._cache_ts = time.monotonic()

    @classmethod
    def get_status(cls):
        """Return config values plus live system data."""
        with cls._lock:
            cfg = cls._get_cached_config()
            return {
                'max_searches': cfg.get('max_searches', cls._default_max),
                'memory_threshold_gb': cfg.get('memory_threshold_gb', cls._default_mem),
                'queue_timeout': cfg.get('queue_timeout', cls._default_timeout),
                'queue_poll_interval': cfg.get('queue_poll_interval', cls._default_poll),
                'stress_test_mode': cls._is_stress_test_active(cfg),
                'active_searches': _count_active_slots(),
                'available_memory_gb': round(get_available_memory_gb(), 1),
                'defaults': {
                    'max_searches': cls._default_max,
                    'memory_threshold_gb': cls._default_mem,
                    'queue_timeout': cls._default_timeout,
                    'queue_poll_interval': cls._default_poll,
                },
            }

    @classmethod
    def to_dict(cls):
        """Return just the config values (no live data)."""
        with cls._lock:
            cfg = cls._get_cached_config()
            return {
                'max_searches': cfg.get('max_searches', cls._default_max),
                'memory_threshold_gb': cfg.get('memory_threshold_gb', cls._default_mem),
                'queue_timeout': cfg.get('queue_timeout', cls._default_timeout),
                'queue_poll_interval': cfg.get('queue_poll_interval', cls._default_poll),
                'stress_test_mode': cls._is_stress_test_active(cfg),
            }



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

    def __init__(self, source_id=None, target_id=None, match_type=None):
        self._fd = None
        self._path = None
        self._acquired = False
        self.source_id = source_id or 'Unknown'
        self.target_id = target_id or 'Unknown'
        self.match_type = match_type or 'Unknown'
        self.start_time = time.time()

    def _create_slot_file(self):
        """Create a unique slot file, write metadata JSON, and lock it."""
        if self._fd is not None:
            return  # Already created
        _ensure_lock_dir()
        name = f"slot_{os.getpid()}_{id(self)}_{time.monotonic_ns()}.lock"
        self._path = os.path.join(LOCK_DIR, name)
        self._fd = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        # Write metadata JSON into the slot file
        meta = {
            'pid': os.getpid(),
            'source_id': self.source_id,
            'target_id': self.target_id,
            'match_type': self.match_type,
            'start_time': self.start_time
        }
        try:
            os.ftruncate(self._fd, 0)
            os.lseek(self._fd, 0, os.SEEK_SET)
            os.write(self._fd, json.dumps(meta).encode('utf-8'))
            os.fsync(self._fd)
        except OSError:
            pass

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
        mem_gb = get_available_memory_gb()

        # 1. Unbypassable Emergency RAM Safety Floor (John's requirement)
        if mem_gb < EMERGENCY_MEMORY_FLOOR_GB and mem_gb != float('inf'):
            _reap_newest_active_slot()
            return False, (
                f"Emergency memory safety floor reached ({mem_gb:.1f} GB available, "
                f"minimum {EMERGENCY_MEMORY_FLOOR_GB:.1f} GB required)")

        # 2. Configured Memory Threshold (skipped in stress test mode)
        if not ConcurrencyConfig.is_stress_test_mode():
            threshold = ConcurrencyConfig.get_memory_threshold()
            if mem_gb < threshold:
                return False, (
                    f"Server memory low ({mem_gb:.1f} GB available, "
                    f"need {threshold:.1f} GB)")

        # 3. Concurrency Capacity (Note: our own slot is already created and counted)
        max_searches = ConcurrencyConfig.get_max_searches()
        active = _count_active_slots()
        if active > max_searches:
            return False, (
                f"Server capacity reached ({active - 1} running, "
                f"max {max_searches})")

        return True, ""

    def acquire(self):
        """Generator that yields queued-status dicts until a slot is acquired.

        Uses create-slot-then-verify ordering to prevent TOCTOU overcount races.
        """
        start = time.monotonic()

        while True:
            # Step 1: Optimistically reserve our slot file FIRST
            self._create_slot_file()

            # Step 2: Check if capacity and memory allow us to proceed
            ok, reason = self._can_proceed()
            if ok:
                self._acquired = True
                logger.info(
                    "Search slot acquired (pid=%d, waited=%.1fs, %s vs %s)",
                    os.getpid(), time.monotonic() - start, self.source_id, self.target_id)
                return  # slot acquired, generator ends

            # Step 3: Over limit or low RAM -- release our slot file while we wait
            self._remove_slot_file()

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
