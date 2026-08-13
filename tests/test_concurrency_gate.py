"""Tests for backend.concurrency_gate — ConcurrencyConfig and SearchSlot.

Covers:
  - Cross-worker config sync via shared JSON file
  - Validation bounds for setters
  - Stress-test auto-expiry (1-hour TTL)
  - Stale lock file cleanup
  - Write failure propagation
"""

import fcntl
import json
import os
import tempfile
import time

import pytest

from backend.concurrency_gate import ConcurrencyConfig, _count_active_slots, LOCK_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _ConfigPatch:
    """Context manager that redirects ConcurrencyConfig to a temp file."""

    def __init__(self):
        self._old_path = None
        self._old_cache = None
        self._old_cache_ts = None
        self._tmpfile = None

    def __enter__(self):
        self._old_path = ConcurrencyConfig._CONFIG_FILE
        self._old_cache = ConcurrencyConfig._cache
        self._old_cache_ts = ConcurrencyConfig._cache_ts

        self._tmpfile = tempfile.NamedTemporaryFile(suffix='.json', delete=False)
        self._tmpfile.close()
        ConcurrencyConfig._CONFIG_FILE = self._tmpfile.name
        ConcurrencyConfig._cache = None
        ConcurrencyConfig._cache_ts = 0
        return self._tmpfile.name

    def __exit__(self, *exc):
        ConcurrencyConfig._CONFIG_FILE = self._old_path
        ConcurrencyConfig._cache = self._old_cache
        ConcurrencyConfig._cache_ts = self._old_cache_ts
        try:
            os.unlink(self._tmpfile.name)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 1. Cross-worker config sync via shared JSON file
# ---------------------------------------------------------------------------

def test_cross_worker_sync_reads_updated_file():
    """Simulates another Apache worker writing a config change to the JSON file.
    After expiring the TTL cache, this worker should pick up the new values."""
    with _ConfigPatch() as path:
        # Should start with defaults
        assert ConcurrencyConfig.get_max_searches() == ConcurrencyConfig._default_max

        # Another worker writes new values directly to the file
        new_config = {
            'max_searches': 42,
            'memory_threshold_gb': 16.5,
            'queue_timeout': 999,
            'queue_poll_interval': 1.5,
            'stress_test_mode': True,
            'stress_test_enabled_at': time.time(),
        }
        with open(path, 'w') as f:
            json.dump(new_config, f)

        # Expire the in-process cache
        ConcurrencyConfig._cache_ts = time.monotonic() - 10

        assert ConcurrencyConfig.get_max_searches() == 42
        assert ConcurrencyConfig.get_memory_threshold() == 16.5
        assert ConcurrencyConfig.get_queue_timeout() == 999
        assert ConcurrencyConfig.get_queue_poll_interval() == 1.5
        assert ConcurrencyConfig.is_stress_test_mode() is True


def test_ttl_cache_does_not_reread_within_window():
    """Within the 5-second TTL window, config should come from the cache, not the file."""
    with _ConfigPatch() as path:
        # Write a value and let the config read it
        cfg = {'max_searches': 7}
        with open(path, 'w') as f:
            json.dump(cfg, f)
        ConcurrencyConfig._cache_ts = 0  # force read
        assert ConcurrencyConfig.get_max_searches() == 7

        # Overwrite the file with a different value
        with open(path, 'w') as f:
            json.dump({'max_searches': 99}, f)

        # Cache is still fresh — should still return 7
        assert ConcurrencyConfig.get_max_searches() == 7


# ---------------------------------------------------------------------------
# 2. Validation bounds
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [0, -1, 51, 100])
def test_set_max_searches_rejects_out_of_range(value):
    with _ConfigPatch():
        with pytest.raises(ValueError):
            ConcurrencyConfig.set_max_searches(value)


@pytest.mark.parametrize("value", [0, 0.4, 129, 200])
def test_set_memory_threshold_rejects_out_of_range(value):
    with _ConfigPatch():
        with pytest.raises(ValueError):
            ConcurrencyConfig.set_memory_threshold(value)


@pytest.mark.parametrize("value", [0, 29, 3601, 10000])
def test_set_queue_timeout_rejects_out_of_range(value):
    with _ConfigPatch():
        with pytest.raises(ValueError):
            ConcurrencyConfig.set_queue_timeout(value)


@pytest.mark.parametrize("value", [0, 0.4, 11, 100])
def test_set_queue_poll_interval_rejects_out_of_range(value):
    with _ConfigPatch():
        with pytest.raises(ValueError):
            ConcurrencyConfig.set_queue_poll_interval(value)


def test_set_max_searches_accepts_valid_values():
    with _ConfigPatch():
        for val in [1, 2, 10, 50]:
            ConcurrencyConfig.set_max_searches(val)
            assert ConcurrencyConfig.get_max_searches() == val


# ---------------------------------------------------------------------------
# 3. Stress-test auto-expiry (1-hour TTL)
# ---------------------------------------------------------------------------

def test_stress_test_mode_active_within_one_hour():
    """Stress test mode should be active when enabled less than 1 hour ago."""
    with _ConfigPatch():
        ConcurrencyConfig.set_stress_test_mode(True)
        assert ConcurrencyConfig.is_stress_test_mode() is True


def test_stress_test_mode_expires_after_one_hour():
    """Stress test mode should auto-expire after 1 hour."""
    with _ConfigPatch() as path:
        # Write config with stress test enabled 2 hours ago
        cfg = {
            'stress_test_mode': True,
            'stress_test_enabled_at': time.time() - 7200,  # 2 hours ago
        }
        with open(path, 'w') as f:
            json.dump(cfg, f)
        ConcurrencyConfig._cache_ts = 0  # force re-read

        assert ConcurrencyConfig.is_stress_test_mode() is False


def test_stress_test_mode_disabled_is_not_active():
    """When stress_test_mode is False, is_stress_test_mode() returns False."""
    with _ConfigPatch():
        ConcurrencyConfig.set_stress_test_mode(False)
        assert ConcurrencyConfig.is_stress_test_mode() is False


# ---------------------------------------------------------------------------
# 4. Stale lock file cleanup
# ---------------------------------------------------------------------------

def test_stale_lock_file_cleanup():
    """A lock file not held by any process should be identified as stale and cleaned up."""
    # Create a temporary lock directory
    with tempfile.TemporaryDirectory() as tmpdir:
        import backend.concurrency_gate as gate
        old_lock_dir = gate.LOCK_DIR
        gate.LOCK_DIR = tmpdir

        try:
            # Create a fake stale lock file (no process holds a flock on it)
            stale_path = os.path.join(tmpdir, 'stale_99999.lock')
            with open(stale_path, 'w') as f:
                f.write('stale')

            # _count_active_slots should clean it up and return 0
            active = _count_active_slots()
            assert active == 0
            assert not os.path.exists(stale_path), "Stale lock file should have been removed"
        finally:
            gate.LOCK_DIR = old_lock_dir


def test_active_lock_file_counted():
    """A lock file held by a live process should be counted as active."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import backend.concurrency_gate as gate
        old_lock_dir = gate.LOCK_DIR
        gate.LOCK_DIR = tmpdir

        try:
            # Create a lock file and hold a flock on it (simulating an active search)
            active_path = os.path.join(tmpdir, 'active_search.lock')
            fd = os.open(active_path, os.O_CREAT | os.O_RDWR)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

            active = _count_active_slots()
            assert active == 1

            # Release the lock
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        finally:
            gate.LOCK_DIR = old_lock_dir


# ---------------------------------------------------------------------------
# 5. Write failure propagation
# ---------------------------------------------------------------------------

def test_write_failure_propagation():
    """Config file write to a non-existent path should raise OSError."""
    old = ConcurrencyConfig._CONFIG_FILE
    try:
        ConcurrencyConfig._CONFIG_FILE = '/nonexistent_dir_abc123/config.json'
        with pytest.raises(OSError):
            ConcurrencyConfig.set_max_searches(5)
    finally:
        ConcurrencyConfig._CONFIG_FILE = old


# ---------------------------------------------------------------------------
# 6. Metadata inspection and live cancellation
# ---------------------------------------------------------------------------

def test_slot_metadata_and_active_search_inspection():
    """Metadata written to a slot should be readable by get_active_searches()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import backend.concurrency_gate as gate
        old_lock_dir = gate.LOCK_DIR
        gate.LOCK_DIR = tmpdir

        with _ConfigPatch():
            gate.ConcurrencyConfig.set_memory_threshold(0.5)
            try:
                slot = gate.SearchSlot()
                # Acquire slot
                for _ in slot.acquire():
                    pass

                slot.set_metadata({
                    'source_id': 'vergil.aeneid.part.1.tess',
                    'target_id': 'lucan.bellum_civile.part.1.tess',
                    'language': 'la',
                    'match_type': 'sound'
                })

                active = gate.get_active_searches()
                assert len(active) == 1
                search = active[0]
                assert search['slot_id'] == slot.slot_id
                assert search['source_id'] == 'vergil.aeneid.part.1.tess'
                assert search['target_id'] == 'lucan.bellum_civile.part.1.tess'
                assert search['language'] == 'la'
                assert search['match_type'] == 'sound'
                assert search['pid'] == os.getpid()
                assert search['runtime_seconds'] >= 0.0
                assert search['is_cancelling'] is False

                slot.release()
                assert len(gate.get_active_searches()) == 0
            finally:
                gate.LOCK_DIR = old_lock_dir


def test_cancel_search_creates_marker_and_is_cancelled():
    """cancel_search() should create a .cancel file and cause slot.is_cancelled() to return True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import backend.concurrency_gate as gate
        old_lock_dir = gate.LOCK_DIR
        gate.LOCK_DIR = tmpdir

        with _ConfigPatch():
            gate.ConcurrencyConfig.set_memory_threshold(0.5)
            try:
                slot = gate.SearchSlot()
                for _ in slot.acquire():
                    pass

                assert slot.is_cancelled() is False

                # Signal cancellation
                success = gate.cancel_search(slot.slot_id)
                assert success is True
                assert slot.is_cancelled() is True

                # Active searches should show is_cancelling=True
                active = gate.get_active_searches()
                assert len(active) == 1
                assert active[0]['is_cancelling'] is True

                # Release slot should clean up slot file AND cancel file
                slot_id = slot.slot_id
                slot.release()
                cancel_file = os.path.join(tmpdir, f"{slot_id}.cancel")
                assert not os.path.exists(cancel_file)
            finally:
                gate.LOCK_DIR = old_lock_dir


def test_fusion_poll_job_metadata_match_type():
    """Fusion poll job metadata match_type should report as 'fusion (poll)'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import backend.concurrency_gate as gate
        old_lock_dir = gate.LOCK_DIR
        gate.LOCK_DIR = tmpdir

        with _ConfigPatch():
            gate.ConcurrencyConfig.set_memory_threshold(0.5)
            try:
                slot = gate.SearchSlot()
                for _ in slot.acquire():
                    pass

                slot.set_metadata({
                    'source_id': 'vergil.aeneid.part.1.tess',
                    'target_id': 'lucan.bellum_civile.part.1.tess',
                    'language': 'la',
                    'match_type': 'fusion (poll)',
                })

                active = gate.get_active_searches()
                assert len(active) == 1
                assert active[0]['match_type'] == 'fusion (poll)'
                slot.release()
            finally:
                gate.LOCK_DIR = old_lock_dir

