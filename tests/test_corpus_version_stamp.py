"""The corpus version stamp follows the index file when piecemeal changes
leave the meta stamp behind, and the /corpus-version route returns it."""
import os, sqlite3, time
from datetime import date

from backend import inverted_index as ii


def _index(tmp_path, stamp):
    p = tmp_path / 'xx_index.db'
    c = sqlite3.connect(p)
    c.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)')
    if stamp:
        c.execute("INSERT INTO meta VALUES ('corpus_version', ?)", (stamp,))
    c.commit(); c.close()
    return p


def test_later_file_date_wins_over_old_stamp(tmp_path, monkeypatch):
    p = _index(tmp_path, '2026-08-16')
    monkeypatch.setattr(ii, 'INDEX_DIR', str(tmp_path))
    monkeypatch.setattr(ii, '_connections', {})
    monkeypatch.setattr(ii, '_corpus_version', {})
    monkeypatch.setattr(ii, 'get_connection', lambda lang: sqlite3.connect(p))
    assert ii.get_corpus_version('xx') == date.today().isoformat()


def test_stamp_kept_when_newer_than_file(tmp_path, monkeypatch):
    p = _index(tmp_path, '2999-01-01')
    monkeypatch.setattr(ii, 'INDEX_DIR', str(tmp_path))
    monkeypatch.setattr(ii, '_corpus_version', {})
    monkeypatch.setattr(ii, 'get_connection', lambda lang: sqlite3.connect(p))
    assert ii.get_corpus_version('xx') == '2999-01-01'
