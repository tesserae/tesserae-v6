"""Book-level restriction: part ids kept by resolve_restriction, accepted by
the ranking filter, and `books=` on the Theme Search route."""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend import passage_index as pi  # noqa: E402


def _rec(i, work, ref):
    return {'id': f'w{i}', 'work': work, 'language': 'la', 'scale': 'fine',
            'ref_start': ref, 'ref_end': ref, 'desc': {'gist': f'g{i}'}}


RECORDS = (
    [_rec(i, f'la/tacitus.annales.part.{n}.tess', f'tac. ann. {n}.{i}')
     for n in (1, 2, 3) for i in (1, 2)]
    + [_rec(20, 'la/tacitus.historiae.tess', 'tac. hist. 1.1')]
)


@pytest.fixture(autouse=True)
def index(monkeypatch, tmp_path):
    monkeypatch.setattr(pi, '_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(pi, '_works_by_language_cache', {})
    monkeypatch.setattr(pi, '_sidecar_written', False)
    monkeypatch.setitem(pi._state, 'loaded', True)
    monkeypatch.setitem(pi._state, 'ok', True)
    monkeypatch.setitem(pi._state, 'error', None)
    monkeypatch.setitem(pi._state, 'languages', None)
    monkeypatch.setattr(pi, '_records', RECORDS)
    by_work = {}
    for i, r in enumerate(RECORDS):
        by_work.setdefault(pi._norm_work(r['work']), []).append(i)
    monkeypatch.setattr(pi, '_by_work', by_work)
    monkeypatch.setattr(pi, '_ids', [r['id'] for r in RECORDS])


def test_resolve_restriction_keeps_part_ids():
    works, note = pi.resolve_restriction(
        works=['tacitus.annales.part.1', 'tacitus.annales.part.2'])
    assert works == {'tacitus.annales.part.1', 'tacitus.annales.part.2'}
    assert note is None


def test_base_id_still_means_the_whole_work():
    works, _ = pi.resolve_restriction(works=['tacitus.annales'])
    assert works == {'tacitus.annales'}


def test_a_part_the_index_lacks_is_not_kept():
    works, note = pi.resolve_restriction(works=['tacitus.annales.part.9'])
    assert works == set() and note


def _stub_scores(monkeypatch):
    scores = np.linspace(0.9, 0.8, len(RECORDS)).astype(np.float32)
    monkeypatch.setattr(pi, 'embed_query', lambda text: np.zeros(3))
    monkeypatch.setattr(pi, '_score_all', lambda q: scores.copy())
    monkeypatch.setattr(pi, '_mask_undescribed', lambda s: s)
    monkeypatch.setattr(pi, '_lexical_boost', lambda q, s: 0)
    monkeypatch.setattr(pi, '_cluster_coherence', lambda s: 0.5)
    monkeypatch.setattr(pi, 'held_languages', lambda: set())
    monkeypatch.setattr(pi, 'BASELINE_MARGIN', -1.0)


def test_filter_accepts_a_part_level_set(monkeypatch):
    _stub_scores(monkeypatch)
    out = pi.find_by_text('storm', limit=25,
                          only_works={'tacitus.annales.part.1', 'tacitus.annales.part.3'})
    parts = {pi.work_id(r['work']) for r in out['results']}
    assert parts and parts <= {'tacitus.annales.part.1', 'tacitus.annales.part.3'}
    assert len(out['results']) == 4          # one base work: no per-work cap


def test_route_reports_books_searched(monkeypatch):
    seen = []

    def fake(query, **kw):
        seen.append(kw)
        return {'query': query, 'results': [], 'confidence': {'level': 'restricted'}}

    monkeypatch.setattr(pi, 'find_by_text', fake)
    monkeypatch.setattr(pi, 'index_version', lambda: 'v')
    monkeypatch.delenv('THEME_READER_URL', raising=False)
    r = app.test_client().get(
        '/api/passages/theme-search?q=storm&works=tacitus.annales&books=1-2,9')
    out = json.loads(r.get_data())
    assert out['books_searched'] == [1, 2]
    assert seen[0]['only_works'] == {'tacitus.annales.part.1', 'tacitus.annales.part.2'}


def test_route_with_no_held_book_answers_with_a_note(monkeypatch):
    r = app.test_client().get(
        '/api/passages/theme-search?q=storm&works=tacitus.annales&books=8')
    out = json.loads(r.get_data())
    assert out['results'] == [] and out['books_searched'] == [] and out['note']
