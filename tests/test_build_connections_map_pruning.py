"""Tests for scripts/build_connections_map.py's cache retention (NC,
2026-09-19): a build keeps the cache it just wrote plus exactly one older
one (the fallback backend.connections_map._resolve() serves when a corpus
edit changes index_fingerprint() before the next ~40-minute rebuild lands),
and deletes anything older than that.

Loaded via importlib rather than a package import: scripts/ is not a
package, and the module's own heavy imports (numpy, backend.scripture_id
etc.) only run at import time, never at collection time for anything else,
so this is the same cost any other test importing backend.connections_map
already pays.
"""
import importlib.util
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SPEC = importlib.util.spec_from_file_location(
    'build_connections_map',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'scripts', 'build_connections_map.py'))
build_connections_map = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_connections_map)


def _write_cache(path, built_at):
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)')
    conn.execute('INSERT INTO meta VALUES (?, ?)', ('built_at', json.dumps(built_at)))
    conn.commit()
    conn.close()


def test_prune_keeps_the_new_cache_and_exactly_one_older_one(tmp_path, monkeypatch):
    monkeypatch.setattr(build_connections_map, 'CACHE_DIR', str(tmp_path))
    new_path = str(tmp_path / 'new.db')
    keep_path = str(tmp_path / 'keep.db')
    old_path1 = str(tmp_path / 'old1.db')
    old_path2 = str(tmp_path / 'old2.db')
    _write_cache(new_path, '2026-09-19T12:00:00')
    _write_cache(keep_path, '2026-09-18T12:00:00')     # the most recent OTHER one
    _write_cache(old_path1, '2026-09-10T00:00:00')
    _write_cache(old_path2, '2026-08-01T00:00:00')

    build_connections_map.prune_old_caches(new_path)

    remaining = set(os.listdir(tmp_path))
    assert remaining == {'new.db', 'keep.db'}


def test_prune_does_nothing_when_at_most_one_older_cache_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(build_connections_map, 'CACHE_DIR', str(tmp_path))
    new_path = str(tmp_path / 'new.db')
    keep_path = str(tmp_path / 'keep.db')
    _write_cache(new_path, '2026-09-19T12:00:00')
    _write_cache(keep_path, '2026-09-18T12:00:00')

    build_connections_map.prune_old_caches(new_path)

    assert set(os.listdir(tmp_path)) == {'new.db', 'keep.db'}


def test_prune_with_only_the_new_cache_present_removes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(build_connections_map, 'CACHE_DIR', str(tmp_path))
    new_path = str(tmp_path / 'new.db')
    _write_cache(new_path, '2026-09-19T12:00:00')

    build_connections_map.prune_old_caches(new_path)

    assert set(os.listdir(tmp_path)) == {'new.db'}


def test_prune_survives_an_unreadable_cache_file(tmp_path, monkeypatch):
    # A corrupt or half-written file should sort last (empty built_at), not
    # crash the prune.
    monkeypatch.setattr(build_connections_map, 'CACHE_DIR', str(tmp_path))
    new_path = str(tmp_path / 'new.db')
    keep_path = str(tmp_path / 'keep.db')
    junk_path = str(tmp_path / 'junk.db')
    _write_cache(new_path, '2026-09-19T12:00:00')
    _write_cache(keep_path, '2026-09-18T12:00:00')
    with open(junk_path, 'wb') as fh:
        fh.write(b'not a sqlite file')

    build_connections_map.prune_old_caches(new_path)

    remaining = set(os.listdir(tmp_path))
    assert 'new.db' in remaining
    assert 'keep.db' in remaining
    assert 'junk.db' not in remaining
