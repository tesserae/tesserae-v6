"""The Theme Search reader re-scores the whole composed list (300 rows),
not its first hundred (2026-09-20)."""
import importlib
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def test_default_depth_is_the_whole_composed_list(monkeypatch):
    monkeypatch.delenv('THEME_READER_K', raising=False)
    import backend.reader_rerank as rr
    importlib.reload(rr)
    assert rr.DEFAULT_K == 300


def test_env_can_still_set_the_depth(monkeypatch):
    monkeypatch.setenv('THEME_READER_K', '100')
    import backend.reader_rerank as rr
    importlib.reload(rr)
    assert rr.DEFAULT_K == 100
    monkeypatch.delenv('THEME_READER_K')
    importlib.reload(rr)


def test_route_fetches_a_hundred_works_for_the_reader():
    from backend.blueprints import passages
    assert passages.READER_HEADS == 100
