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
            gate.ConcurrencyConfig.set_emergency_ram_floor(1.0)
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
            gate.ConcurrencyConfig.set_emergency_ram_floor(1.0)
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


def test_slot_metadata_match_type_fusion_poll_label():
    """Slot metadata match_type should accept/report the 'fusion (poll)' label."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import backend.concurrency_gate as gate
        old_lock_dir = gate.LOCK_DIR
        gate.LOCK_DIR = tmpdir

        with _ConfigPatch():
            gate.ConcurrencyConfig.set_memory_threshold(0.5)
            gate.ConcurrencyConfig.set_emergency_ram_floor(1.0)
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


def test_cancel_search_releases_slot_and_cleans_up():
    """Cancellation should be detected by is_cancelled(), and slot.release()
    should clean up both the lock file and the .cancel marker."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import backend.concurrency_gate as gate
        old_lock_dir = gate.LOCK_DIR
        gate.LOCK_DIR = tmpdir

        with _ConfigPatch():
            gate.ConcurrencyConfig.set_memory_threshold(0.5)
            gate.ConcurrencyConfig.set_emergency_ram_floor(1.0)
            try:
                slot = gate.SearchSlot()
                for _ in slot.acquire():
                    pass

                slot.set_metadata({
                    'source_id': 'src.tess',
                    'target_id': 'tgt.tess',
                    'language': 'la',
                    'match_type': 'fusion (poll)',
                })

                # Before cancel: slot should not be cancelled
                assert not slot.is_cancelled()
                assert gate._count_active_slots() == 1

                # Simulate admin cancellation (create .cancel file)
                cancel_path = os.path.join(tmpdir, f"{slot.slot_id}.cancel")
                with open(cancel_path, 'w') as f:
                    f.write('')

                # After cancel: is_cancelled should return True
                assert slot.is_cancelled()

                # Slot is still active (hasn't been released yet)
                assert gate._count_active_slots() == 1

                # Release slot (as the finally block would do)
                slot.release()

                # After release: slot file and cancel marker should be gone
                assert gate._count_active_slots() == 0
                assert not os.path.exists(cancel_path), \
                    "Cancel marker should be cleaned up by slot.release()"
            finally:
                gate.LOCK_DIR = old_lock_dir


def test_emergency_floor_blocks_in_stress_mode(monkeypatch):
    """Emergency RAM floor must block new searches even when Stress Test Mode is ON."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import backend.concurrency_gate as gate
        old_lock_dir = gate.LOCK_DIR
        gate.LOCK_DIR = tmpdir

        with _ConfigPatch():
            try:
                gate.ConcurrencyConfig.set_emergency_ram_floor(5.0)
                gate.ConcurrencyConfig.set_stress_test_mode(True)
                assert gate.ConcurrencyConfig.is_stress_test_mode()

                # Mock memory below emergency floor (4.0 GB < 5.0 GB floor)
                monkeypatch.setattr(gate, 'get_available_memory_gb', lambda: 4.0)

                slot = gate.SearchSlot()
                ok, reason = slot._can_proceed()
                assert not ok
                assert "EMERGENCY" in reason
                assert "4.0 GB available" in reason
            finally:
                gate.LOCK_DIR = old_lock_dir


def test_emergency_floor_allows_when_above(monkeypatch):
    """Search proceeds when available memory is above the emergency RAM floor."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import backend.concurrency_gate as gate
        old_lock_dir = gate.LOCK_DIR
        gate.LOCK_DIR = tmpdir

        with _ConfigPatch():
            try:
                gate.ConcurrencyConfig.set_emergency_ram_floor(3.0)
                gate.ConcurrencyConfig.set_memory_threshold(4.0)
                gate.ConcurrencyConfig.set_stress_test_mode(True)

                # Mock memory above floor (3.5 GB > 3.0 GB floor, though < 4.0 GB threshold)
                monkeypatch.setattr(gate, 'get_available_memory_gb', lambda: 3.5)

                slot = gate.SearchSlot()
                ok, reason = slot._can_proceed()
                assert ok
                assert reason == ""
            finally:
                gate.LOCK_DIR = old_lock_dir


def test_emergency_floor_config_persistence():
    """Emergency RAM floor setting should validate range and persist across reads."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import backend.concurrency_gate as gate
        old_lock_dir = gate.LOCK_DIR
        gate.LOCK_DIR = tmpdir

        with _ConfigPatch():
            try:
                gate.ConcurrencyConfig.set_emergency_ram_floor(4.5)
                assert gate.ConcurrencyConfig.get_emergency_ram_floor() == 4.5
                assert gate.ConcurrencyConfig.get_status()['emergency_ram_floor_gb'] == 4.5

                # Out of range values should raise ValueError
                try:
                    gate.ConcurrencyConfig.set_emergency_ram_floor(0.5)
                    assert False, "Should have raised ValueError for floor < 1.0"
                except ValueError:
                    pass

                try:
                    gate.ConcurrencyConfig.set_emergency_ram_floor(20.0)
                    assert False, "Should have raised ValueError for floor > 16.0"
                except ValueError:
                    pass
            finally:
                gate.LOCK_DIR = old_lock_dir


def test_reaper_cancels_newest_search(monkeypatch):
    """MemoryReaper should identify and cancel the newest running search when memory is low."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import backend.concurrency_gate as gate
        old_lock_dir = gate.LOCK_DIR
        gate.LOCK_DIR = tmpdir

        with _ConfigPatch():
            try:
                gate.ConcurrencyConfig.set_emergency_ram_floor(5.0)

                # Mock sufficient RAM during initial acquisition
                monkeypatch.setattr(gate, 'get_available_memory_gb', lambda: 10.0)

                # Create two slots with distinct start times
                slot1 = gate.SearchSlot()
                for _ in slot1.acquire():
                    pass
                slot1._start_time = 1000.0

                slot2 = gate.SearchSlot()
                for _ in slot2.acquire():
                    pass
                slot2._start_time = 2000.0  # Newest search

                assert gate._count_active_slots() == 2

                # Mock low RAM (3.0 GB < 5.0 GB floor)
                monkeypatch.setattr(gate, 'get_available_memory_gb', lambda: 3.0)

                # Run one tick of the reaper manually
                gate.MemoryReaper._tick()

                # Newer search (slot2) should have a cancel marker, older one (slot1) should not
                assert slot2.is_cancelled(), "Newest search should be cancelled by reaper"
                assert not slot1.is_cancelled(), "Older search should remain uncancelled"

                # Telemetry check
                status = gate.MemoryReaper.get_status()
                assert status['reap_count'] >= 1
                assert slot2.slot_id in status['last_reap_slot']

                slot1.release()
                slot2.release()
            finally:
                gate.LOCK_DIR = old_lock_dir


def test_reaper_does_not_cancel_when_above_floor(monkeypatch):
    """MemoryReaper tick is a no-op when available memory is above the emergency floor."""
    with tempfile.TemporaryDirectory() as tmpdir:
        import backend.concurrency_gate as gate
        old_lock_dir = gate.LOCK_DIR
        gate.LOCK_DIR = tmpdir

        with _ConfigPatch():
            try:
                gate.ConcurrencyConfig.set_emergency_ram_floor(3.0)
                monkeypatch.setattr(gate, 'get_available_memory_gb', lambda: 6.0)

                slot = gate.SearchSlot()
                for _ in slot.acquire():
                    pass

                initial_reaps = gate.MemoryReaper._reap_count
                gate.MemoryReaper._tick()

                assert not slot.is_cancelled()
                assert gate.MemoryReaper._reap_count == initial_reaps

                slot.release()
            finally:
                gate.LOCK_DIR = old_lock_dir

