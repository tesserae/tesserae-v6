"""Stage 3b-2's central safety claim, as a committed test rather than only
a manual capture: with `collection` omitted, or 'literature', or with
TESSERAE_DOCUMENTS=1 set but `collection` still omitted, `/api/line-search`
must return byte-identical results (search_time aside) to a request that
never heard of the documents collection at all.

Integration test against the live Latin index, like
test_line_search_passage_cap.py: skipped where the real index is absent, and
the corpus-frequency stoplist augmentation is monkeypatched to an empty
table (not under test here, and building it cold takes minutes-to-hours in
a fresh process — see research notes for the measured cost).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.lexical_density import _index_path

if not os.path.exists(_index_path('la')):
    pytest.skip('Latin inverted index not present; integration test',
                allow_module_level=True)

import backend.app as _appmod  # noqa: E402
import backend.documents as _docs_mod  # noqa: E402
from backend.app import app  # noqa: E402

_appmod.get_corpus_frequencies = lambda *a, **k: {'frequencies': {}}

QUERIES = [
    {'query': 'arma virumque', 'language': 'la'},
    {'query': 'arma virumque', 'language': 'la', 'search_type': 'exact'},
    {'query': 'arma virumque', 'language': 'la', 'author': 'vergil'},
]


def _route():
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/line-search'))


def _post(params):
    client = app.test_client()
    body = dict(params)
    body.setdefault('max_results', 50)
    r = client.post(_route(), json=body)
    assert r.status_code == 200
    d = r.get_json()
    d.pop('search_time', None)
    for row in d.get('results') or []:
        row.pop('search_time', None)
    return d


@pytest.fixture(autouse=True)
def _clean_documents_env(monkeypatch):
    # Start every test from a known-off state regardless of the real
    # process environment, and let backend.documents re-read it per call
    # (it never memoizes `enabled()`, so no reset needed after monkeypatch
    # restores the env var on teardown).
    monkeypatch.delenv('TESSERAE_DOCUMENTS', raising=False)
    yield


@pytest.mark.parametrize('params', QUERIES)
def test_collection_omitted_matches_collection_literature(params):
    baseline = _post(params)
    explicit = _post({**params, 'collection': 'literature'})
    assert baseline == explicit


@pytest.mark.parametrize('params', QUERIES)
def test_switch_on_but_collection_omitted_is_unchanged(params, monkeypatch):
    baseline = _post(params)
    monkeypatch.setenv('TESSERAE_DOCUMENTS', '1')
    assert _docs_mod.enabled() is True
    with_switch_on = _post(params)
    assert baseline == with_switch_on


@pytest.mark.parametrize('params', QUERIES)
def test_collection_documents_falls_back_to_literature_when_switch_is_off(params):
    # The switch is off (autouse fixture clears it) and collection=documents
    # is requested anyway: must behave exactly like a literature request,
    # never a silent empty result.
    baseline = _post(params)
    requested_documents = _post({**params, 'collection': 'documents'})
    assert baseline == requested_documents


def test_collection_both_adds_documents_fields_without_changing_literary_ones(monkeypatch):
    # This one needs a REAL documents index (not committed to the repo;
    # see backend/documents.py/DATA_OPERATIONS.md), unlike every other test
    # in this file, which only exercises the default/fallback paths.
    if not _docs_mod.is_index_available('la'):
        pytest.skip('la_documents_index.db not present; integration test')
    baseline = _post({'query': 'arma virumque'})
    monkeypatch.setenv('TESSERAE_DOCUMENTS', '1')
    both = _post({'query': 'arma virumque', 'collection': 'both'})
    # Every literary-only key baseline carries must still carry the SAME
    # value under 'both' (this is the scope assumption the auto-review
    # flagged: filtered_query_lemmas/min_matched must not have drifted).
    for key in ('total', 'distinct_loci', 'capped', 'corpus_version'):
        assert both.get(key) == baseline.get(key), key
    # The literary rows themselves (collection != 'documents') must be the
    # same set, in the same order, as the baseline's own results.
    lit_rows_in_both = [r for r in both.get('results') or [] if r.get('collection') != 'documents']
    assert lit_rows_in_both == (baseline.get('results') or [])
    # 'both' is additive: it may ALSO carry documents_total/by_source_region,
    # which the plain baseline never has.
    assert 'documents_total' in both
