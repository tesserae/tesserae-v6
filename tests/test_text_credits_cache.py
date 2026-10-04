"""/api/text-credits parses text_sources.json once per file version, not per request."""
import json
import os
import threading
import time
from unittest import mock

import pytest
from flask import Flask

import backend.blueprints.corpus as corpus

REAL_LOAD = json.load

ENTRIES = [
    {'author': 'Virgil', 'work': 'Aeneid'},
    {'author': 'Homer', 'work': 'Iliad'},
    {'author': 'Virgil', 'work': 'Eclogues'},
]


def write(path, data, bump_ns=0):
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding='utf-8')
    if bump_ns:  # deterministic "file changed" without sleeping
        st = path.stat()
        os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + bump_ns))


@pytest.fixture
def sources(tmp_path, monkeypatch):
    (tmp_path / 'texts').mkdir()
    corpus.init_corpus_blueprint(str(tmp_path / 'texts'), None, None)
    path = tmp_path / 'text_sources.json'
    write(path, ENTRIES)
    monkeypatch.setattr(corpus, 'TEXT_SOURCES_FILE', path)
    return path


@pytest.fixture
def client(sources):
    app = Flask(__name__)
    app.register_blueprint(corpus.corpus_bp, url_prefix='/api')
    with app.test_client() as c:
        yield c


@pytest.fixture
def loads():
    with mock.patch.object(corpus.json, 'load', wraps=REAL_LOAD) as m:
        yield m


def parses(m):
    """json.load calls on text_sources.json (the restricted-texts registry has its own)."""
    return sum(c.args[0].name == str(corpus.TEXT_SOURCES_FILE) for c in m.call_args_list)


def works(resp):
    return [e['work'] for e in resp.get_json()['entries']]


def test_unchanged_file_parsed_once(client, loads):
    for _ in range(5):
        assert works(client.get('/api/text-credits?limit=25')) == ['Aeneid', 'Iliad', 'Eclogues']
    assert parses(loads) == 1


def test_modified_file_reloaded(client, sources, loads):
    client.get('/api/text-credits')
    write(sources, ENTRIES + [{'author': 'Ovid', 'work': 'Metamorphoses'}], bump_ns=10**9)
    assert client.get('/api/text-credits').get_json()['total'] == 4
    assert works(client.get('/api/text-credits?query=ovid')) == ['Metamorphoses']
    assert parses(loads) == 2


def test_filter_and_pagination_unchanged(client):
    page = client.get('/api/text-credits?query=VIRG&offset=1&limit=25').get_json()
    assert page == {'entries': [ENTRIES[2]], 'total': 2, 'offset': 1, 'limit': 25}
    assert client.get('/api/text-credits?limit=10').status_code == 400
    assert client.get('/api/text-credits?offset=-1').status_code == 400


def test_requests_do_not_mutate_cached_entries(client):
    client.get('/api/text-credits?query=homer')
    client.get('/api/text-credits?offset=2&limit=25')
    assert corpus.get_text_sources() == ENTRIES
    assert works(client.get('/api/text-credits')) == ['Aeneid', 'Iliad', 'Eclogues']


def test_missing_file_is_empty(client, sources):
    sources.unlink()
    assert client.get('/api/text-credits').get_json()['total'] == 0


def test_malformed_change_errors_instead_of_serving_stale(client, sources):
    assert client.get('/api/text-credits').status_code == 200
    write(sources, '[{"author": ', bump_ns=10**9)
    assert client.get('/api/text-credits').status_code == 500
    assert client.get('/api/text-credits').status_code == 500  # no stale fallback
    write(sources, ENTRIES[:1], bump_ns=2 * 10**9)
    assert client.get('/api/text-credits').get_json()['total'] == 1


def test_concurrent_cold_requests_parse_once(sources):
    def slow_load(f):
        time.sleep(0.05)  # widen the race window so an unlocked refresh would double-parse
        return REAL_LOAD(f)

    barrier = threading.Barrier(8)

    def hit():
        barrier.wait()
        corpus.get_text_sources()

    with mock.patch.object(corpus.json, 'load', side_effect=slow_load) as m:
        threads = [threading.Thread(target=hit) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert parses(m) == 1
