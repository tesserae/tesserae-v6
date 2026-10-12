"""Confidence for a Theme Search within ONE work (Search One Text).

No built index: module state is stubbed as tests/test_theme_search_within.py
does, with twenty windows of one work and fixed scores.
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import passage_index as pi  # noqa: E402

N = 20


def _records():
    return [{'id': f'w{i}', 'work': 'la/tacitus.annales.part.%d.tess' % (1 + i // 10), 'language': 'la',
             'scale': 'fine', 'ref_start': f'tac. ann. {1 + i // 10}.{i}', 'ref_end': f'tac. ann. {1 + i // 10}.{i}',
             'desc': {'gist': f'g{i}'}} for i in range(N)] + [
        {'id': 'other', 'work': 'la/lucan.bellum_civile.tess', 'language': 'la', 'scale': 'fine',
         'ref_start': 'luc. 1.1', 'ref_end': 'luc. 1.1', 'desc': {'gist': 'o'}}]


def _stub(monkeypatch, scores):
    recs = _records()
    monkeypatch.setattr(pi, '_DATA_DIR', '/nonexistent')
    monkeypatch.setitem(pi._state, 'loaded', True)
    monkeypatch.setitem(pi._state, 'ok', True)
    monkeypatch.setitem(pi._state, 'error', None)
    monkeypatch.setattr(pi, '_records', recs)
    by_work = {}
    for i, r in enumerate(recs):
        by_work.setdefault(pi._norm_work(r['work']), []).append(i)
    monkeypatch.setattr(pi, '_by_work', by_work)
    monkeypatch.setattr(pi, '_ids', [r['id'] for r in recs])
    monkeypatch.setitem(pi._state, 'languages', None)
    emb = np.eye(len(recs), 8, dtype=np.float32)
    emb[:, 0] += 1.0          # every row shares a component, so coherence is above zero
    monkeypatch.setattr(pi, '_emb', emb)
    sc = np.asarray(scores, dtype=np.float32)
    monkeypatch.setattr(pi, 'embed_query', lambda text: np.zeros(3))
    monkeypatch.setattr(pi, '_score_all', lambda q: sc.copy())
    monkeypatch.setattr(pi, '_mask_undescribed', lambda s: s)
    monkeypatch.setattr(pi, '_lexical_boost', lambda q, s: 0)
    monkeypatch.setattr(pi, 'held_languages', lambda: set())
    monkeypatch.setattr(pi, 'BASELINE_MARGIN', -1.0)


FLAT = [0.70 + 0.001 * (i % 5) for i in range(N)] + [0.95]            # narrow spread; Lucan row is outside
WIDE = [0.70 + 0.002 * (i % 3) for i in range(17)] + [0.80, 0.85, 0.95] + [0.50]


@pytest.fixture(autouse=True)
def _embeddings(monkeypatch):
    emb = np.eye(N + 1, 8, dtype=np.float32)
    emb[:, 0] += 1.0          # every row shares a component, so coherence is above zero
    monkeypatch.setattr(pi, '_emb', emb)


def test_signals_on_twenty_windows():
    sc = np.array(WIDE, dtype=np.float32)
    out = pi.within_work_signals(sc, list(range(N)))
    s = np.array(WIDE[:N], dtype=np.float64)
    assert out['n'] == N
    assert out['work_median'] == pytest.approx(float(np.median(s)))
    assert out['work_head_lift'] == pytest.approx(float(np.sort(s)[-10:].mean() - np.median(s)))
    assert out['top1_lift'] == pytest.approx(0.95 - float(np.median(s)))
    assert out['spread'] == pytest.approx(float(s.std()))
    assert 0.0 < out['work_coherence'] <= 1.0


def test_masked_windows_are_left_out_and_a_tiny_scope_is_not_rated():
    sc = np.array(WIDE, dtype=np.float32)
    sc[:5] = -1.0
    assert pi.within_work_signals(sc, list(range(N)))['n'] == 15
    assert pi.within_work_signals(sc, list(range(8))) is None


def test_the_band_thresholds():
    assert pi._within_level(pi.WITHIN_SPREAD_WEAK - 1e-6) == 'low'
    assert pi._within_level(pi.WITHIN_SPREAD_WEAK) == 'moderate'
    assert pi._within_level(pi.WITHIN_SPREAD_STRONG - 1e-6) == 'moderate'
    assert pi._within_level(pi.WITHIN_SPREAD_STRONG) == 'strong'


def test_a_flat_work_is_rated_low_and_nothing_is_strong(monkeypatch):
    _stub(monkeypatch, FLAT)
    out = pi.find_by_text('airplanes', limit=25, only_works={'tacitus.annales'})
    c = out['confidence']
    assert c['level'] == 'low' and c['fitted'] == pi.WITHIN_FITTED
    assert set(c) >= {'level', 'work_head_lift', 'work_coherence', 'spread', 'fitted', 'note'}
    assert out['strong_matches'] == 0 and not any(r['strong'] for r in out['results'])
    assert 'provisional' in c['note'] and out['note'] == c['note']


def test_a_wide_work_is_rated_and_strong_follows_z(monkeypatch):
    _stub(monkeypatch, WIDE)
    out = pi.find_by_text('a subject', limit=25, only_works={'tacitus.annales'})
    c = out['confidence']
    assert c['level'] in ('moderate', 'strong')
    sig = pi.within_work_signals(np.array(WIDE, dtype=np.float32), list(range(N)))
    assert c['work_head_lift'] == pytest.approx(sig['work_head_lift'], abs=1e-4)
    assert len(out['results']) == N              # the Lucan window is outside the scope
    for r in out['results']:
        z = (r['score'] - sig['work_median']) / sig['spread']
        assert r['z'] == pytest.approx(z, abs=0.01)
        assert r['lift'] == pytest.approx(r['score'] - sig['work_median'], abs=1e-4)
        assert r['strong'] == (z >= pi.WITHIN_STRONG_Z)
    assert out['strong_matches'] == sum(1 for r in out['results'] if r['strong'])
    assert out['strong_matches'] >= 1


def test_book_files_of_one_work_count_as_one_scope(monkeypatch):
    _stub(monkeypatch, WIDE)
    out = pi.find_by_text('a subject', limit=25, only_works={'tacitus.annales.part.1'})
    # ten windows are enough to rate; the scope is book 1 only
    assert out['confidence']['fitted'] == pi.WITHIN_FITTED
    assert len(out['results']) == 10


def test_several_works_are_not_rated(monkeypatch):
    _stub(monkeypatch, WIDE)
    out = pi.find_by_text('a subject', limit=25, only_works={'tacitus.annales', 'lucan.bellum_civile'})
    # The unknown-word check (2026-10-11) adds three fields to every
    # confidence block; a several-works search is still unrated.
    assert out['confidence']['level'] == 'restricted'
    assert set(out['confidence']) >= {'level', 'vocab_checked', 'unknown_words', 'no_known_words'}
    assert out['strong_matches'] == 0
