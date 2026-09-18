"""GET /passages/works: which works of a language have passage windows.

Feeds the Browse Corpus "Theme Search" badge -- a work absent from the
passage index never shows up in Theme Search or Similar Passages, and
nothing on the site said so before this route existed. Stubs the passage
index's module state directly (the pattern tests/test_density_cache.py
uses) rather than loading the real, multi-gigabyte index, so this runs in
CI with no built index present.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend import passage_index  # noqa: E402


def _stub_index(monkeypatch, records):
    """Install a fake, already-loaded passage index with the given records."""
    monkeypatch.setitem(passage_index._state, 'loaded', True)
    monkeypatch.setitem(passage_index._state, 'ok', True)
    monkeypatch.setitem(passage_index._state, 'error', None)
    monkeypatch.setattr(passage_index, '_records', records)
    by_work = {}
    for i, r in enumerate(records):
        by_work.setdefault(passage_index._norm_work(r.get('work')), []).append(i)
    monkeypatch.setattr(passage_index, '_by_work', by_work)
    monkeypatch.setattr(passage_index, '_ids', [r['id'] for r in records])
    monkeypatch.setattr(passage_index, '_works_by_language_cache', {})


RECORDS = [
    {'id': 'w1', 'work': 'la/vergil.aeneid.part.1.tess', 'language': 'la'},
    {'id': 'w2', 'work': 'la/vergil.aeneid.part.2.tess', 'language': 'la'},
    {'id': 'w3', 'work': 'la/cicero.orator.tess', 'language': 'la'},
    {'id': 'w4', 'work': 'grc/homer.iliad.tess', 'language': 'grc'},
]


def _route():
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/passages/works'))


def _get(client, route, **params):
    qs = '&'.join(f'{k}={v}' for k, v in params.items() if v not in (None, ''))
    r = client.get(f'{route}?{qs}')
    assert r.status_code == 200, f'endpoint returned {r.status_code}'
    return json.loads(r.get_data())


def test_returns_the_base_ids_for_the_requested_language(monkeypatch):
    _stub_index(monkeypatch, RECORDS)
    client = app.test_client()
    out = _get(client, _route(), language='la')
    assert out['language'] == 'la'
    assert set(out['works']) == {'vergil.aeneid', 'cicero.orator'}
    assert 'homer.iliad' not in out['works']


def test_multi_part_work_collapses_to_one_base_id(monkeypatch):
    """vergil.aeneid.part.1 and .part.2 are two records, one work."""
    _stub_index(monkeypatch, RECORDS)
    client = app.test_client()
    out = _get(client, _route(), language='la')
    assert out['works'].count('vergil.aeneid') == 1


def test_a_language_with_no_records_returns_an_empty_list(monkeypatch):
    _stub_index(monkeypatch, RECORDS)
    client = app.test_client()
    out = _get(client, _route(), language='cop')
    assert out['works'] == []


def test_response_carries_an_index_version(monkeypatch):
    _stub_index(monkeypatch, RECORDS)
    monkeypatch.setattr(passage_index, 'index_version', lambda: '2026-09-18')
    client = app.test_client()
    out = _get(client, _route(), language='la')
    assert out['index_version'] == '2026-09-18'
