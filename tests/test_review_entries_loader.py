"""The accepted dictionary_review entries load into CURATED_GREEK_LATIN (2026-10-18).

load_accepted_review_entries imported get_db_cursor from backend.db, a module that
does not exist, so the call always logged a warning and loaded nothing. The function
lives in backend.db_utils.
"""
import logging
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import backend.db_utils as db_utils
from backend import synonym_dict


class _Cursor:
    def __init__(self, rows):
        self._rows = rows
        self.sql = None

    def execute(self, sql, params=None):
        self.sql = sql

    def fetchall(self):
        return self._rows


def _fake_cursor_factory(cursor):
    @contextmanager
    def get_db_cursor(commit=True):
        yield cursor
    return get_db_cursor


def test_import_resolves():
    assert callable(db_utils.get_db_cursor)


def test_loader_adds_two_rows(monkeypatch):
    cursor = _Cursor([("ζῷον", "Animal"), ("τεστοσ", "Uorum")])
    monkeypatch.setattr(db_utils, "get_db_cursor", _fake_cursor_factory(cursor))
    saved = {k: list(v) for k, v in synonym_dict.CURATED_GREEK_LATIN.items()}
    try:
        n = synonym_dict.load_accepted_review_entries()
        assert n == 2
        assert "accepted" in cursor.sql
        assert "animal" in synonym_dict.CURATED_GREEK_LATIN[
            synonym_dict._normalize_greek("ζῷον").replace("ς", "σ")]
        assert synonym_dict.CURATED_GREEK_LATIN["τεστοσ"] == ["uorum"]
        # Loading again adds no duplicate.
        assert synonym_dict.load_accepted_review_entries() == 2
        assert synonym_dict.CURATED_GREEK_LATIN["τεστοσ"] == ["uorum"]
    finally:
        synonym_dict.CURATED_GREEK_LATIN.clear()
        synonym_dict.CURATED_GREEK_LATIN.update(saved)


def test_failing_import_only_warns(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "backend.db_utils", None)  # import raises ImportError
    with caplog.at_level(logging.WARNING):
        assert synonym_dict.load_accepted_review_entries() == 0
    assert "Could not load accepted review entries" in caplog.text
