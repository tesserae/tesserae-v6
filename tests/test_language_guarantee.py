"""Multi-language page composition by per-language round-robin (2026-08-31)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.passage_index import _interleave_languages


def h(work, lang, score):
    return {'work': work, 'language': lang, 'score': score}


def test_round_robin_across_languages():
    pool = [h('la.a', 'la', 0.9), h('la.b', 'la', 0.89), h('la.c', 'la', 0.88),
            h('he.a', 'he', 0.85), h('he.b', 'he', 0.84),
            h('grc.a', 'grc', 0.83)]
    heads = pool[:4]
    out = _interleave_languages(heads, [dict(p) for p in pool])
    assert [r['work'] for r in out] == ['la.a', 'he.a', 'grc.a', 'la.b']


def test_page_opens_with_global_best():
    pool = [h('grc.a', 'grc', 0.95), h('la.a', 'la', 0.90)]
    out = _interleave_languages(pool, [dict(p) for p in pool])
    assert out[0]['work'] == 'grc.a'


def test_absent_language_gets_nothing():
    pool = [h('la.a', 'la', 0.9), h('la.b', 'la', 0.89)]
    out = _interleave_languages(pool, [dict(p) for p in pool])
    assert [r['language'] for r in out] == ['la', 'la']


def test_exhausted_language_yields_to_others():
    pool = [h('la.a', 'la', 0.9), h('he.a', 'he', 0.8),
            h('la.b', 'la', 0.7), h('la.c', 'la', 0.6)]
    heads = pool[:4]
    out = _interleave_languages(heads, [dict(p) for p in pool])
    assert len(out) == 4 and [r['work'] for r in out] == ['la.a', 'he.a', 'la.b', 'la.c']
