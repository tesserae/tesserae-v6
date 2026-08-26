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
import subprocess
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
        if not name.endswith('.lock') or name.startswith('reaper_'):
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


def get_process_memory_mb(pid):
    """Get Resident Set Size (RSS) RAM usage in MB for a process ID."""
    if not pid:
        return None
    try:
        res = subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True, timeout=2)
        kb = int(res.stdout.strip())
        return round(kb / 1024.0, 1)
    except Exception:
        return None


def get_active_searches():
    """Inspect all active search slots and return their metadata.

    Returns a list of dicts, each containing:
        - slot_id: str
        - pid: int
        - source_id: str
        - target_id: str
        - language: str
        - match_type: str
        - start_time: float (timestamp)
        - runtime_seconds: float
        - memory_mb: float or None
        - is_cancelling: bool
    """
    _ensure_lock_dir()
    now = time.time()
    results = []

    for name in os.listdir(LOCK_DIR):
        if not name.endswith('.lock') or name.startswith('reaper_'):
            continue
        path = os.path.join(LOCK_DIR, name)
        slot_id = name[:-5]  # strip '.lock'
        try:
            fd = os.open(path, os.O_RDWR)
            try:
                # Try non-blocking flock — if it succeeds, file is stale
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
                # Safety: this cleanup is race-free because (1) flock is atomic —
                # if we acquired the lock, no live process holds it; (2) new
                # SearchSlot.acquire() always creates a fresh file with a unique
                # slot_id (PID + timestamp), never reusing stale filenames; and
                # (3) os.unlink of a file that was already removed by another
                # reader is harmless (caught by the OSError handler).
                try:
                    os.unlink(path)
                    cancel_path = os.path.join(LOCK_DIR, f"{slot_id}.cancel")
                    if os.path.exists(cancel_path):
                        os.unlink(cancel_path)
                except OSError:
                    pass
            except BlockingIOError:
                # Slot is actively held by a running process! Read metadata.
                metadata = {}
                try:
                    with open(path, 'r') as f:
                        content = f.read().strip()
                        if content:
                            metadata = json.loads(content)
                except (OSError, ValueError, json.JSONDecodeError):
                    pass

                os.close(fd)

                parts = slot_id.split('_')
                pid = metadata.get('pid') or (int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else None)
                start_time = metadata.get('start_time')
                if not start_time:
                    try:
                        start_time = os.path.getmtime(path)
                    except OSError:
                        start_time = now
                runtime = round(max(0.0, now - start_time), 1)

                results.append({
                    'slot_id': slot_id,
                    'pid': pid,
                    'source_id': metadata.get('source_id', 'Unknown'),
                    'target_id': metadata.get('target_id', 'Unknown'),
                    'language': metadata.get('language', 'Unknown'),
                    'match_type': metadata.get('match_type', 'Unknown'),
                    'start_time': start_time,
                    'runtime_seconds': runtime,
                    'memory_mb': get_process_memory_mb(pid),
                    'is_cancelling': os.path.exists(os.path.join(LOCK_DIR, f"{slot_id}.cancel"))
                })
        except OSError:
            pass

    results.sort(key=lambda x: x['start_time'])
    return results


def cancel_search(slot_id):
    """Signal an active search slot to terminate cleanly at its next checkpoint.

    Returns True if signal was recorded, False if slot wasn't found or not active.
    """
    _ensure_lock_dir()
    if not slot_id or '/' in slot_id or '\\' in slot_id or '..' in slot_id:
        return False

    lock_path = os.path.join(LOCK_DIR, f"{slot_id}.lock")
    if not os.path.exists(lock_path):
        return False

    try:
        fd = os.open(lock_path, os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
            return False
        except BlockingIOError:
            os.close(fd)
            cancel_path = os.path.join(LOCK_DIR, f"{slot_id}.cancel")
            try:
                with open(cancel_path, 'w') as f:
                    f.write(json.dumps({'cancelled_at': time.time()}))
                logger.info("Created cancellation marker for slot %s", slot_id)
                return True
            except OSError as e:
                logger.error("Failed to write cancel marker for %s: %s", slot_id, e)
                return False
    except OSError:
        return False


def cancel_all_searches():
    """Cancel all currently running search slots.

    Returns list of cancelled slot IDs.
    """
    active = get_active_searches()
    cancelled = []
    for item in active:
        if cancel_search(item['slot_id']):
            cancelled.append(item['slot_id'])
    return cancelled


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
    _default_emergency_floor = float(os.environ.get('TESSERAE_EMERGENCY_RAM_FLOOR_GB', '3.0'))

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
            'emergency_ram_floor_gb': cls._default_emergency_floor,
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

    @classmethod
    def get_emergency_ram_floor(cls):
        with cls._lock:
            return cls._get_cached_config().get(
                'emergency_ram_floor_gb', cls._default_emergency_floor)

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
    def set_emergency_ram_floor(cls, value):
        value = float(value)
        if not (1.0 <= value <= 16.0):
            raise ValueError(
                f"emergency_ram_floor_gb must be between 1.0 and 16.0, got {value}")
        with cls._lock:
            cls._update_and_persist('emergency_ram_floor_gb', value)

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
            raw_mem = get_available_memory_gb()
            avail_mem = round(raw_mem, 1)
            floor = cfg.get('emergency_ram_floor_gb', cls._default_emergency_floor)
            return {
                'max_searches': cfg.get('max_searches', cls._default_max),
                'memory_threshold_gb': cfg.get('memory_threshold_gb', cls._default_mem),
                'queue_timeout': cfg.get('queue_timeout', cls._default_timeout),
                'queue_poll_interval': cfg.get('queue_poll_interval', cls._default_poll),
                'emergency_ram_floor_gb': floor,
                'stress_test_mode': cls._is_stress_test_active(cfg),
                'active_searches': _count_active_slots(),
                'available_memory_gb': avail_mem,
                'emergency_active': raw_mem < floor,
                'reaper_status': MemoryReaper.get_status(),
                'defaults': {
                    'max_searches': cls._default_max,
                    'memory_threshold_gb': cls._default_mem,
                    'queue_timeout': cls._default_timeout,
                    'queue_poll_interval': cls._default_poll,
                    'emergency_ram_floor_gb': cls._default_emergency_floor,
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
                'emergency_ram_floor_gb': cfg.get(
                    'emergency_ram_floor_gb', cls._default_emergency_floor),
                'stress_test_mode': cls._is_stress_test_active(cfg),
            }

class MemoryReaper:
    """Background daemon thread that monitors system RAM and cancels the newest
    running search when available memory drops below the emergency RAM floor.

    Singleton per process — calling ``start()`` more than once is harmless.
    Cross-worker coordination: Uses file locking (flock) and a shared state file
    in LOCK_DIR to prevent multiple mod_wsgi worker processes from reaping
    simultaneously (thundering herd prevention) and to synchronize cooldowns.

    Why the **newest** search?  It has completed the least work, so killing it
    wastes the fewest resources and lets older (closer-to-done) searches finish.
    """

    _thread = None          # type: threading.Thread | None
    _stop_event = threading.Event()
    _lock = threading.Lock()

    # In-memory fallbacks / defaults
    _reap_count = 0
    _last_reap_at = 0.0     # timestamp
    _last_reap_slot = ''
    _last_reap_reason = ''

    POLL_INTERVAL = 5.0     # seconds between RAM checks
    COOLDOWN = 10.0         # seconds to wait after a reap before checking again

    # ------------------------------------------------------------------
    # Shared State Helpers (cross-worker synchronization via lock files)
    # ------------------------------------------------------------------

    @classmethod
    def _state_file_path(cls):
        return os.path.join(LOCK_DIR, 'reaper_state.json')

    @classmethod
    def _tick_lock_path(cls):
        return os.path.join(LOCK_DIR, 'reaper_tick.lock')

    @classmethod
    def _read_shared_state(cls):
        """Read shared reaper telemetry state across workers."""
        try:
            path = cls._state_file_path()
            if os.path.exists(path):
                with open(path, 'r') as f:
                    return json.load(f)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        return {
            'reap_count': cls._reap_count,
            'last_reap_at': cls._last_reap_at,
            'last_reap_slot': cls._last_reap_slot,
            'last_reap_reason': cls._last_reap_reason,
        }

    @classmethod
    def _write_shared_state(cls, state):
        """Persist shared reaper telemetry state atomically."""
        _ensure_lock_dir()
        cls._reap_count = state.get('reap_count', 0)
        cls._last_reap_at = state.get('last_reap_at', 0.0)
        cls._last_reap_slot = state.get('last_reap_slot', '')
        cls._last_reap_reason = state.get('last_reap_reason', '')

        tmp_path = cls._state_file_path() + '.tmp'
        try:
            with open(tmp_path, 'w') as f:
                json.dump(state, f, indent=2)
            os.replace(tmp_path, cls._state_file_path())
        except OSError as e:
            logger.warning("Failed to write shared reaper state: %s", e)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def start(cls):
        """Start the reaper thread (idempotent)."""
        with cls._lock:
            if cls._thread is not None and cls._thread.is_alive():
                return
            cls._stop_event.clear()
            cls._thread = threading.Thread(
                target=cls._run, name='MemoryReaper', daemon=True)
            cls._thread.start()
            logger.info("MemoryReaper started (poll=%.1fs, cooldown=%.1fs)",
                        cls.POLL_INTERVAL, cls.COOLDOWN)

    @classmethod
    def stop(cls):
        """Signal the reaper to stop (used in tests or graceful shutdown)."""
        cls._stop_event.set()
        with cls._lock:
            if cls._thread is not None:
                cls._thread.join(timeout=cls.POLL_INTERVAL + 2)
                cls._thread = None
        logger.info("MemoryReaper stopped")

    @classmethod
    def is_running(cls):
        with cls._lock:
            return cls._thread is not None and cls._thread.is_alive()

    # ------------------------------------------------------------------
    # Status (exposed via admin API — reads cross-worker state file)
    # ------------------------------------------------------------------

    @classmethod
    def get_status(cls):
        state = cls._read_shared_state()
        return {
            'active': cls.is_running(),
            'reap_count': state.get('reap_count', 0),
            'last_reap_at': state.get('last_reap_at', 0.0),
            'last_reap_slot': state.get('last_reap_slot', ''),
            'last_reap_reason': state.get('last_reap_reason', ''),
        }

    # ------------------------------------------------------------------
    # Main loop (runs in a daemon thread)
    # ------------------------------------------------------------------

    @classmethod
    def _run(cls):
        """Poll system RAM and reap searches when memory is critical."""
        while not cls._stop_event.is_set():
            try:
                cls._tick()
            except Exception:
                logger.exception("MemoryReaper tick failed")
            cls._stop_event.wait(cls.POLL_INTERVAL)

    @classmethod
    def _tick(cls):
        """One check-and-reap cycle with cross-worker synchronization."""
        mem_gb = get_available_memory_gb()
        floor = ConcurrencyConfig.get_emergency_ram_floor()

        if mem_gb >= floor:
            return  # plenty of RAM — nothing to do

        # Shared cross-worker cooldown check: if any worker reaped < COOLDOWN ago, wait
        state = cls._read_shared_state()
        last_reap_at = state.get('last_reap_at', 0.0)
        if (time.time() - last_reap_at) < cls.COOLDOWN:
            return

        # RAM is below emergency floor. Try to acquire cross-worker tick lock
        _ensure_lock_dir()
        lock_path = cls._tick_lock_path()
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                # Try non-blocking flock — if another worker process is reaping, yield
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    # Re-check cooldown inside lock
                    state = cls._read_shared_state()
                    last_reap_at = state.get('last_reap_at', 0.0)
                    if (time.time() - last_reap_at) < cls.COOLDOWN:
                        return

                    active = get_active_searches()
                    if not active:
                        return

                    # Target the newest search (most recently started → least work lost)
                    newest = max(active, key=lambda s: s.get('start_time', 0.0))
                    slot_id = newest.get('slot_id')
                    if not slot_id:
                        return

                    reason = (
                        f"RAM {mem_gb:.1f} GB < emergency floor {floor:.1f} GB; "
                        f"reaping newest search {slot_id} "
                        f"(source={newest.get('source_id')}, target={newest.get('target_id')}, "
                        f"runtime={newest.get('runtime_seconds', 0):.0f}s)"
                    )
                    logger.warning("MemoryReaper: %s", reason)

                    if cancel_search(slot_id):
                        new_state = {
                            'reap_count': state.get('reap_count', 0) + 1,
                            'last_reap_at': time.time(),
                            'last_reap_slot': slot_id,
                            'last_reap_reason': reason,
                        }
                        cls._write_shared_state(new_state)
                        logger.warning("MemoryReaper: cancelled slot %s (total reaps: %d)",
                                       slot_id, new_state['reap_count'])
                        if cls.COOLDOWN > 0:
                            cls._stop_event.wait(cls.COOLDOWN)
                    else:
                        logger.warning("MemoryReaper: cancel_search(%s) returned False", slot_id)
                finally:
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    except OSError:
                        pass
            except BlockingIOError:
                # Another worker process is currently executing a reap tick
                pass
            finally:
                try:
                    os.close(fd)
                except OSError:
                    pass
        except OSError as e:
            logger.warning("MemoryReaper: failed to open tick lock file: %s", e)


def start_memory_reaper():
    """Convenience entry point to start the MemoryReaper.

    Call this from app startup (e.g. create_app) to ensure the reaper is
    running.  Safe to call multiple times — the reaper is a singleton.
    """
    MemoryReaper.start()


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

    def __init__(self, cancellation=None):
        self._fd = None
        self._path = None
        self._acquired = False
        self._cancellation = cancellation
        self.slot_id = None
        self._start_time = None

    def _create_slot_file(self):
        """Create a unique slot file and lock it."""
        _ensure_lock_dir()
        self.slot_id = f"slot_{os.getpid()}_{id(self)}_{time.monotonic_ns()}"
        self._start_time = time.time()
        name = f"{self.slot_id}.lock"
        self._path = os.path.join(LOCK_DIR, name)
        self._fd = os.open(self._path, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(self._fd, fcntl.LOCK_EX)
        payload = {
            'slot_id': self.slot_id,
            'pid': os.getpid(),
            'start_time': self._start_time,
            'source_id': 'Initializing...',
            'target_id': 'Initializing...',
            'language': '—',
            'match_type': 'Initializing...',
        }
        try:
            os.write(self._fd, json.dumps(payload).encode('utf-8'))
            os.fsync(self._fd)
        except OSError:
            pass

    def set_metadata(self, metadata: dict):
        """Write search parameters metadata into the slot file."""
        if not self._acquired or self._fd is None:
            return
        payload = {
            'slot_id': self.slot_id,
            'pid': os.getpid(),
            'start_time': self._start_time or time.time(),
            'source_id': metadata.get('source_id', 'Unknown'),
            'target_id': metadata.get('target_id', 'Unknown'),
            'language': metadata.get('language', 'Unknown'),
            'match_type': metadata.get('match_type', 'Unknown'),
        }
        try:
            os.lseek(self._fd, 0, os.SEEK_SET)
            os.ftruncate(self._fd, 0)
            os.write(self._fd, json.dumps(payload).encode('utf-8'))
            os.fsync(self._fd)
        except OSError as e:
            logger.warning("Failed to write metadata for slot %s: %s", self.slot_id, e)

    def is_cancelled(self):
        """Check whether an admin has issued a cancellation signal for this slot."""
        if not self.slot_id:
            return False
        cancel_path = os.path.join(LOCK_DIR, f"{self.slot_id}.cancel")
        return os.path.exists(cancel_path)

    def _remove_slot_file(self):
        """Release the lock and delete the slot file and any cancel marker."""
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
        if self.slot_id is not None:
            cancel_path = os.path.join(LOCK_DIR, f"{self.slot_id}.cancel")
            try:
                if os.path.exists(cancel_path):
                    os.unlink(cancel_path)
            except OSError:
                pass
            self.slot_id = None
        self._acquired = False

    def _can_proceed(self):
        """Check whether a slot is available and memory is sufficient.

        Returns (ok, reason) where reason explains why we're blocked.
        """
        mem_gb = get_available_memory_gb()

        # UNCONDITIONAL: Emergency RAM floor cannot be bypassed, even in
        # stress test mode.  This is the last-resort OOM guard.
        emergency_floor = ConcurrencyConfig.get_emergency_ram_floor()
        if mem_gb < emergency_floor:
            return False, (
                f"EMERGENCY: RAM critically low ({mem_gb:.1f} GB available, "
                f"emergency floor is {emergency_floor:.1f} GB)")

        # Normal memory threshold (skipped in stress test mode)
        if not ConcurrencyConfig.is_stress_test_mode():
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
        MemoryReaper.start()

        while True:
            if self._cancellation is not None:
                self._cancellation.check()
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
            if self._cancellation is not None:
                self._cancellation.check()
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
