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
import pytest
from backend import passage_index  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_data_dir(monkeypatch, tmp_path):
    """Every test here reads and writes the works-by-language sidecar under a
    temporary data dir, never the real one. On 2026-09-19 an unisolated run
    read production's sidecar (so the fixture works were not what came back)
    and, on a machine where it was missing, WROTE fixture data into
    production's data/passage_index/works_by_language.json through a worktree
    symlink."""
    monkeypatch.setattr(passage_index, '_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(passage_index, '_works_by_language_cache', {})
    monkeypatch.setattr(passage_index, '_sidecar_written', False)


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


# --- works_by_language.json sidecar ---------------------------------------
#
# Right after a deploy reload (touch tesseraev6_flask.wsgi), each of the
# three Apache workers loads the ~2GB passage index on its first request,
# which takes about 90 seconds. A request to this route during that window
# used to be slow or fail, and the client's silent fallback then rendered
# as "0 of 782 works are covered by Theme Search" -- indistinguishable from
# a real coverage gap. The sidecar lets the route answer from a small file
# instead of the loaded index, when that file is present and current.

def _reset_sidecar_state(monkeypatch):
    monkeypatch.setattr(passage_index, '_works_by_language_cache', {})
    monkeypatch.setattr(passage_index, '_sidecar_written', False)


def test_sidecar_hit_answers_without_loading_the_index(monkeypatch, tmp_path):
    """A current sidecar must answer the route without ever calling
    _ensure_loaded() -- that's the whole point of the fix."""
    monkeypatch.setattr(passage_index, '_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(passage_index, 'index_version', lambda: '2026-09-18')
    _reset_sidecar_state(monkeypatch)
    monkeypatch.setitem(passage_index._state, 'loaded', False)
    monkeypatch.setitem(passage_index._state, 'ok', False)
    monkeypatch.setattr(passage_index, '_records', None)
    monkeypatch.setattr(passage_index, '_by_work', None)
    sidecar = {'index_version': '2026-09-18',
               'languages': {'la': ['vergil.aeneid', 'cicero.orator'],
                             'grc': ['homer.iliad']}}
    (tmp_path / passage_index.WORKS_SIDECAR_FILENAME).write_text(json.dumps(sidecar))

    client = app.test_client()
    out = _get(client, _route(), language='la')

    assert set(out['works']) == {'vergil.aeneid', 'cicero.orator'}
    assert out['index_version'] == '2026-09-18'
    assert passage_index._state['loaded'] is False, \
        'a sidecar hit must not trigger _ensure_loaded()'


def test_stale_sidecar_falls_back_to_the_loaded_index(monkeypatch, tmp_path):
    """A sidecar stamped with a different index_version is a rebuild in
    progress, or leftover from a prior index, and must not be trusted."""
    monkeypatch.setattr(passage_index, '_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(passage_index, 'index_version', lambda: '2026-09-18')
    _reset_sidecar_state(monkeypatch)
    stale = {'index_version': '2020-01-01', 'languages': {'la': ['some.stale.work']}}
    (tmp_path / passage_index.WORKS_SIDECAR_FILENAME).write_text(json.dumps(stale))
    _stub_index(monkeypatch, RECORDS)

    client = app.test_client()
    out = _get(client, _route(), language='la')

    assert set(out['works']) == {'vergil.aeneid', 'cicero.orator'}
    assert 'some.stale.work' not in out['works']


def test_missing_sidecar_is_written_after_the_first_load(monkeypatch, tmp_path):
    """The request that has to load the index leaves the sidecar behind, so
    the next request (in this worker or another) does not have to."""
    monkeypatch.setattr(passage_index, '_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(passage_index, 'index_version', lambda: '2026-09-18')
    _reset_sidecar_state(monkeypatch)
    _stub_index(monkeypatch, RECORDS)

    client = app.test_client()
    out = _get(client, _route(), language='la')
    assert set(out['works']) == {'vergil.aeneid', 'cicero.orator'}

    sidecar_path = tmp_path / passage_index.WORKS_SIDECAR_FILENAME
    assert sidecar_path.exists(), 'a successful load must write the sidecar'
    payload = json.loads(sidecar_path.read_text())
    assert payload['index_version'] == '2026-09-18'
    assert set(payload['languages']['la']) == {'vergil.aeneid', 'cicero.orator'}
    assert set(payload['languages']['grc']) == {'homer.iliad'}


def test_sidecar_silent_on_a_language_falls_back_rather_than_guessing_empty(monkeypatch, tmp_path):
    """A current sidecar that never mentions a language (e.g. one added to
    the index after the sidecar was written) must not read as zero works."""
    monkeypatch.setattr(passage_index, '_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(passage_index, 'index_version', lambda: '2026-09-18')
    _reset_sidecar_state(monkeypatch)
    sidecar = {'index_version': '2026-09-18', 'languages': {'la': ['vergil.aeneid']}}
    (tmp_path / passage_index.WORKS_SIDECAR_FILENAME).write_text(json.dumps(sidecar))
    _stub_index(monkeypatch, RECORDS)

    client = app.test_client()
    out = _get(client, _route(), language='grc')

    assert out['works'] == ['homer.iliad']
