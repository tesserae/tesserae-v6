"""Similar Passages' per-language sections (find_similar_to_window(by_language=True),
2026-10-07): a language with few results in the main list gets its own best matches,
so an Urdu passage among Persian-dominated results still shows Urdu."""
import numpy as np

from backend import passage_index as pi
from test_passage_same_names import _install, _rec, _reset_names_state  # noqa: F401 (fixture)


def _unit(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_a_crowded_out_language_gets_its_own_section(monkeypatch, _reset_names_state):
    monkeypatch.setattr(pi, '_undescribed', set())
    monkeypatch.setitem(pi._state, 'languages', None)
    # Source (Urdu), six close Persian windows, two slightly less close Urdu ones,
    # and twenty far filler windows so the median sits well below.
    recs = [_rec('mir:fine:0', 'mir.kulliyat', 'ur')]
    emb = [_unit([1, 0, 0])]
    for i in range(6):
        recs.append(_rec(f'fa{i}:fine:0', f'poet{i}.diwan', 'fa')); emb.append(_unit([1, 0.05 + 0.01 * i, 0]))
    for i in range(2):
        recs.append(_rec(f'ur{i}:fine:0', f'urdu{i}.diwan', 'ur')); emb.append(_unit([1, 0.2 + 0.05 * i, 0]))
    for i in range(20):
        recs.append(_rec(f'x{i}:fine:0', f'far{i}.text', 'la')); emb.append(_unit([0, 0, 1]))
    _install(monkeypatch, recs, emb)
    monkeypatch.setattr(pi, '_score_all', lambda q: np.asarray(pi._emb) @ q)
    monkeypatch.setattr(pi, 'scripture_id', type('S', (), {
        'span': staticmethod(lambda *a, **k: None), 'overlaps': staticmethod(lambda a, b: False)}))

    out = pi.find_similar_to_window('mir:fine:0', limit=5, by_language=True)
    main_langs = [r['language'] for r in out['results']]
    assert main_langs == ['fa'] * 5                       # Persian fills the main list
    assert [r['work'] for r in out['by_language']['ur']] == ['urdu0.diwan', 'urdu1.diwan']
    assert 'fa' not in out['by_language']                 # already has five above
    shown = {r['id'] for r in out['results']}
    assert not shown & {r['id'] for rows in out['by_language'].values() for r in rows}


def test_without_the_flag_the_response_is_unchanged(monkeypatch, _reset_names_state):
    monkeypatch.setitem(pi._state, 'languages', None)
    recs = [_rec('a:fine:0', 'a.text', 'la'), _rec('b:fine:0', 'b.text', 'grc')]
    _install(monkeypatch, recs, [_unit([1, 0]), _unit([1, 0.1])])
    monkeypatch.setattr(pi, '_score_all', lambda q: np.asarray(pi._emb) @ q)
    out = pi.find_similar_to_window('a:fine:0', limit=5)
    assert 'by_language' not in out
