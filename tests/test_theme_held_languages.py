"""Held languages are kept out of Theme Search results (2026-10-06: Arabic)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.passage_index import held_languages  # noqa: E402


def test_arabic_held_by_default(monkeypatch):
    monkeypatch.delenv('TESSERAE_HELD_LANGUAGES', raising=False)
    monkeypatch.delenv('TESSERAE_LANGUAGES', raising=False)
    assert held_languages() == {'ar'}


def test_a_server_that_serves_arabic_shows_it(monkeypatch):
    monkeypatch.delenv('TESSERAE_HELD_LANGUAGES', raising=False)
    monkeypatch.setenv('TESSERAE_LANGUAGES', 'fa,ur,ar')
    assert held_languages() == set()


def test_override_and_empty(monkeypatch):
    monkeypatch.delenv('TESSERAE_LANGUAGES', raising=False)
    monkeypatch.setenv('TESSERAE_HELD_LANGUAGES', '')
    assert held_languages() == set()
    monkeypatch.setenv('TESSERAE_HELD_LANGUAGES', 'ar,he')
    assert held_languages() == {'ar', 'he'}
