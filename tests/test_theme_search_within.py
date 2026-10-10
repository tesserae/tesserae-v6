"""Theme Search restricted to an author or to chosen works.

Runs with no built index: the passage index's module state is stubbed in the
way tests/test_passages_works_route.py does, and the embedding step is replaced
with fixed scores.
"""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend import passage_index  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(passage_index, '_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(passage_index, '_works_by_language_cache', {})
    monkeypatch.setattr(passage_index, '_sidecar_written', False)


def _rec(i, work, lang, ref):
    return {'id': f'w{i}', 'work': work, 'language': lang, 'scale': 'fine',
            'ref_start': ref, 'ref_end': ref, 'desc': {'gist': f'g{i}'}}


# lucan: one work. vergil: two works, the Aeneid with many windows.
RECORDS = (
    [_rec(i, 'la/lucan.bellum_civile.tess', 'la', f'luc. {i}.1') for i in range(0, 6)]
    + [_rec(10 + i, 'la/vergil.aeneid.part.1.tess', 'la', f'verg. aen. {i}.1') for i in range(1, 9)]
    + [_rec(30, 'la/vergil.georgics.tess', 'la', 'verg. geo. 1.1')]
    + [_rec(40, 'grc/homer.iliad.tess', 'grc', 'hom. il. 1.1')]
)


def _stub_index(monkeypatch):
    monkeypatch.setitem(passage_index._state, 'loaded', True)
    monkeypatch.setitem(passage_index._state, 'ok', True)
    monkeypatch.setitem(passage_index._state, 'error', None)
    monkeypatch.setattr(passage_index, '_records', RECORDS)
    by_work = {}
    for i, r in enumerate(RECORDS):
        by_work.setdefault(passage_index._norm_work(r['work']), []).append(i)
    monkeypatch.setattr(passage_index, '_by_work', by_work)
    monkeypatch.setattr(passage_index, '_ids', [r['id'] for r in RECORDS])
    monkeypatch.setitem(passage_index._state, 'languages', None)


@pytest.fixture
def index(monkeypatch):
    _stub_index(monkeypatch)


# --- resolve_restriction ----------------------------------------------------

def test_no_restriction_resolves_to_none(index):
    assert passage_index.resolve_restriction() == (None, None)
    assert passage_index.resolve_restriction(author='', works=[]) == (None, None)


def test_author_resolves_to_all_that_authors_works(index):
    works, note = passage_index.resolve_restriction(author='Vergil')
    assert works == {'vergil.aeneid', 'vergil.georgics'}
    assert note is None


def test_author_respects_the_chosen_languages(index):
    works, _ = passage_index.resolve_restriction(author='homer', languages=['la'])
    assert works == set()
    works, _ = passage_index.resolve_restriction(author='homer', languages=['grc'])
    assert works == {'homer.iliad'}


def test_works_resolve_and_parts_collapse(index):
    works, _ = passage_index.resolve_restriction(
        works=['vergil.aeneid.part.1', 'lucan.bellum_civile'])
    assert works == {'vergil.aeneid', 'lucan.bellum_civile'}


def test_unknown_author_gives_an_empty_set_and_a_note(index):
    works, note = passage_index.resolve_restriction(author='nobody')
    assert works == set()
    assert 'nobody' in note


def test_unknown_work_gives_an_empty_set_and_a_note(index):
    works, note = passage_index.resolve_restriction(works=['vergil.nonesuch'])
    assert works == set()
    assert note


def test_work_outside_the_named_author_is_not_resolved(index):
    works, note = passage_index.resolve_restriction(
        author='vergil', works=['lucan.bellum_civile'])
    assert works == set() and note


# --- ranking ----------------------------------------------------------------

def _stub_scores(monkeypatch):
    # Descending scores down the record list, all above the floor.
    scores = np.linspace(0.9, 0.8, len(RECORDS)).astype(np.float32)
    monkeypatch.setattr(passage_index, 'embed_query', lambda text: np.zeros(3))
    monkeypatch.setattr(passage_index, '_score_all', lambda q: scores.copy())
    monkeypatch.setattr(passage_index, '_mask_undescribed', lambda s: s)
    monkeypatch.setattr(passage_index, '_lexical_boost', lambda q, s: 0)
    monkeypatch.setattr(passage_index, '_cluster_coherence', lambda s: 0.5)
    monkeypatch.setattr(passage_index, 'held_languages', lambda: set())
    monkeypatch.setattr(passage_index, 'BASELINE_MARGIN', -1.0)   # every window clears the floor


def _works_of(out):
    return [passage_index._norm_work(r['work']) for r in out['results']]


def test_restricted_search_returns_only_the_chosen_works(index, monkeypatch):
    _stub_scores(monkeypatch)
    out = passage_index.find_by_text('storm', limit=25,
                                     only_works={'vergil.aeneid', 'vergil.georgics'})
    assert set(_works_of(out)) <= {'vergil.aeneid', 'vergil.georgics'}
    assert out['restricted'] is True


def test_restricted_search_withholds_confidence_and_strong_flags(index, monkeypatch):
    _stub_scores(monkeypatch)
    out = passage_index.find_by_text('storm', limit=25, only_works={'lucan.bellum_civile'})
    assert out['confidence'] == {'level': 'restricted'}
    assert out['strong_matches'] == 0
    assert not any(r['strong'] for r in out['results'])
    assert 'Confidence is not rated' in out['note']


def test_a_single_work_is_not_capped(index, monkeypatch):
    _stub_scores(monkeypatch)
    out = passage_index.find_by_text('storm', limit=25, only_works={'lucan.bellum_civile'})
    assert len(out['results']) == 6        # all six windows, past the 3-per-work cap


def test_several_works_share_the_restricted_cap(index, monkeypatch):
    _stub_scores(monkeypatch)
    monkeypatch.setattr(passage_index, 'RESTRICTED_PER_WORK', 4)
    out = passage_index.find_by_text('storm', limit=25,
                                     only_works={'vergil.aeneid', 'vergil.georgics'})
    counts = {}
    for w in _works_of(out):
        counts[w] = counts.get(w, 0) + 1
    assert counts['vergil.aeneid'] == 4
    assert counts['vergil.georgics'] == 1
    assert 'up to 4 passages' in out['note']


def test_restricted_paging_continues_the_same_ranking(index, monkeypatch):
    _stub_scores(monkeypatch)
    only = {'lucan.bellum_civile'}
    first = passage_index.find_by_text('storm', limit=4, only_works=only)
    second = passage_index.find_by_text('storm', limit=4, offset=4, only_works=only)
    ids = [r['id'] for r in first['results'] + second['results']]
    assert len(ids) == len(set(ids)) == 6


# --- the route --------------------------------------------------------------

def _get(client, **params):
    qs = '&'.join(f'{k}={v}' for k, v in params.items())
    r = client.get(f'/api/passages/theme-search?{qs}')
    assert r.status_code == 200
    return json.loads(r.get_data())


@pytest.fixture
def seen(index, monkeypatch):
    calls = []

    def fake(query, **kw):
        calls.append(kw)
        return {'query': query, 'results': [{'work': 'x'}], 'confidence': {'level': 'strong'}}

    monkeypatch.setattr(passage_index, 'find_by_text', fake)
    monkeypatch.setattr(passage_index, 'index_version', lambda: 'v')
    monkeypatch.delenv('THEME_READER_URL', raising=False)
    return calls


def test_route_without_restriction_passes_none(seen):
    _get(app.test_client(), q='storm')
    assert 'only_works' not in seen[0]


def test_route_resolves_author_to_a_work_set(seen):
    _get(app.test_client(), q='storm', author='vergil')
    assert seen[0]['only_works'] == {'vergil.aeneid', 'vergil.georgics'}


def test_route_resolves_works_list(seen):
    _get(app.test_client(), q='storm', works='lucan.bellum_civile,vergil.georgics')
    assert seen[0]['only_works'] == {'lucan.bellum_civile', 'vergil.georgics'}


def test_route_unknown_author_answers_empty_with_a_note_not_an_error(seen):
    out = _get(app.test_client(), q='storm', author='nobody')
    assert out['results'] == []
    assert 'nobody' in out['note']
    assert 'error' not in out
    assert seen == []        # the ranker was never asked


def test_route_unknown_work_answers_empty_with_a_note(seen):
    out = _get(app.test_client(), q='storm', works='vergil.nonesuch')
    assert out['results'] == [] and out['note'] and 'error' not in out
