"""Tests for the fusion GET-poll honest-progress capture (backend.blueprints.fusion):
the background job records real coarse progress (phase, signals done/total,
candidates) to a status file that the poll reports. No fabricated time-percent.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import backend.blueprints.fusion as F


def _use_tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(F, "CACHE_DIR", str(tmp_path))


def test_channel_start_records_prior_signals_done(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    F._write_fusion_status("job1", "channel_start",
                           {"channel": "sound", "step": 7, "total": 10, "phase": "line"})
    st = F._read_fusion_status("job1")
    # a channel just STARTING means step-1 have finished
    assert st["signals_done"] == 6
    assert st["signals_total"] == 10
    assert st["current_signal"] == "sound"
    assert st["phase"] == "line"


def test_channel_done_counts_the_finished_signal(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    F._write_fusion_status("job2", "channel_done",
                           {"channel": "lemma", "step": 3, "total": 10, "phase": "line", "skipped": False})
    st = F._read_fusion_status("job2")
    assert st["signals_done"] == 3
    assert st["signals_total"] == 10


def test_intermediate_records_candidates(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    F._write_fusion_status("job3", "intermediate",
                           {"channels_done": 5, "channels_total": 10,
                            "total_results": 42, "phase": "window", "results": []})
    st = F._read_fusion_status("job3")
    assert st["signals_done"] == 5
    assert st["signals_total"] == 10
    assert st["candidates_so_far"] == 42
    assert st["phase"] == "window"


def test_non_progress_events_write_nothing(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    for ev in ("complete", "heartbeat", "error"):
        F._write_fusion_status("job4", ev, {"results": [1, 2]})
    assert F._read_fusion_status("job4") is None


def test_status_omits_missing_fields(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    # channel event with no phase/total present
    F._write_fusion_status("job5", "channel_start", {"channel": "sound", "step": 2})
    st = F._read_fusion_status("job5")
    assert "phase" not in st          # None values dropped
    assert "signals_total" not in st
    assert st["signals_done"] == 1
    assert st["current_signal"] == "sound"


def test_clear_removes_status(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    F._write_fusion_status("job6", "channel_done",
                           {"channel": "lemma", "step": 1, "total": 10, "phase": "line"})
    assert F._read_fusion_status("job6") is not None
    F._clear_fusion_status("job6")
    assert F._read_fusion_status("job6") is None
    # clearing a non-existent status is a no-op (no exception)
    F._clear_fusion_status("job6")


def test_status_path_is_under_cache_dir(tmp_path, monkeypatch):
    _use_tmp_cache(tmp_path, monkeypatch)
    p = F._fusion_status_path("abc")
    assert p.startswith(str(tmp_path))
    assert p.endswith("fusion_status_abc.json")
