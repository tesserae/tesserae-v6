"""/api/scope/capabilities: twelve capabilities for every served language, cached."""
import pytest

from backend import language_capabilities as lc
from backend.blueprints import scope

KEYS = [k for k, _s, _n in lc.CAPABILITIES]
LANGS = [{'code': 'la', 'label': 'Latin'}, {'code': 'cop', 'label': 'Coptic'}]


@pytest.fixture(autouse=True)
def fresh_cache():
    scope.reset_capabilities_cache()
    yield
    scope.reset_capabilities_cache()


def _patched(monkeypatch, calls):
    def reader(state, count):
        def read(lang, ctx):
            calls.append(lang)
            return {'state': state, 'count': count, 'note': 'stand-in'}
        return read
    fake = {k: reader('full' if i % 3 == 0 else 'partial' if i % 3 == 1 else 'none', None if i % 2 else i)
            for i, k in enumerate(KEYS)}
    monkeypatch.setattr(lc, 'READERS', fake)
    monkeypatch.setattr(lc, 'make_context', lambda languages, pairs, held: {'pairs': [], 'held': []})
    monkeypatch.setattr(scope, '_capabilities_inputs', lambda: (LANGS, [], []))


def test_every_language_has_every_capability(monkeypatch):
    from backend.app import app
    app.config['TESTING'] = True
    _patched(monkeypatch, [])
    body = app.test_client().get('/api/scope/capabilities').get_json()
    assert [c['key'] for c in body['capabilities']] == KEYS
    assert [r['code'] for r in body['languages']] == ['la', 'cop']
    for row in body['languages']:
        assert set(row['capabilities']) == set(KEYS)
        for cell in row['capabilities'].values():
            assert cell['state'] in ('full', 'partial', 'none')
            assert cell['count'] is None or isinstance(cell['count'], int)
            assert isinstance(cell['note'], str)
    assert len(body['computed_at']) == 10


def test_answer_is_cached(monkeypatch):
    from backend.app import app
    app.config['TESTING'] = True
    calls = []
    _patched(monkeypatch, calls)
    client = app.test_client()
    client.get('/api/scope/capabilities')
    n = len(calls)
    assert n == len(KEYS) * len(LANGS)
    client.get('/api/scope/capabilities')
    assert len(calls) == n


def test_a_failing_reader_gives_none_not_read(monkeypatch):
    def boom(lang, ctx):
        raise RuntimeError('x')
    monkeypatch.setattr(lc, 'make_context', lambda languages, pairs, held: {'pairs': [], 'held': []})
    readers = dict(lc.READERS, meter=boom)
    out = lc.build(LANGS, [], [], readers=readers)
    cell = out['languages'][0]['capabilities']['meter']
    assert cell == {'state': 'none', 'count': None, 'note': 'not read'}


def test_real_readers_return_valid_cells():
    ctx = lc.make_context(LANGS, [], [])
    for key in KEYS:
        cell = lc.READERS[key]('la', ctx)
        assert cell['state'] in ('full', 'partial', 'none')
