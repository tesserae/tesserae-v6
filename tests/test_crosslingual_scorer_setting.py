"""The cross-language scorer setting (2026-10-17): live by default, the evaluation scorer on request.

The identity test runs Aeneid 1 against Iliad 1 through both the live function (with the setting
on 'evaluation') and the evaluation scorer itself, and needs the texts, lemma caches and
embeddings. It skips where they are absent.
"""
import sys
from pathlib import Path

import pytest

from backend import cache
from backend.blueprints import search as sm

ROOT = Path(__file__).resolve().parents[1]


def _params(source_language, target_language):
    return {'source_id': 'a', 'target_id': 'b', 'language': 'grc',
            'source_language': source_language, 'target_language': target_language}


def test_default_scorer_is_live_and_gate_unchanged():
    cs = sm._cross_settings(_params('grc', 'la'), {})
    assert cs.crosslingual_scorer == 'live'
    assert cs.crosslingual_lemma_gate == 'exclude'


def test_evaluation_scorer_has_the_gate_off_unless_asked():
    cs = sm._cross_settings(_params('la', 'grc'), {'crosslingual_scorer': 'evaluation'})
    assert cs.crosslingual_scorer == 'evaluation'
    assert cs.crosslingual_lemma_gate == 'off'
    asked = sm._cross_settings(_params('grc', 'la'), {'crosslingual_scorer': 'evaluation',
                                                      'crosslingual_lemma_gate': 'penalty'})
    assert asked.crosslingual_lemma_gate == 'penalty'


def test_unknown_value_and_other_pairs_stay_live():
    assert sm._cross_settings(_params('grc', 'la'), {'crosslingual_scorer': 'bogus'}).crosslingual_scorer == 'live'
    en = sm._cross_settings(_params('la', 'en'), {'crosslingual_scorer': 'evaluation'})
    assert en.crosslingual_scorer == 'live'
    assert en.crosslingual_lemma_gate == sm.ENGLISH_CROSS_SETTINGS['lemma_gate']


def test_cache_key_is_unchanged_by_default_and_differs_for_evaluation():
    base = {'match_type': 'crosslingual_fusion', 'source_language': 'grc', 'target_language': 'la'}
    k0 = cache.get_cache_key('a', 'b', 'grc', dict(base))
    assert cache.get_cache_key('a', 'b', 'grc', {**base, 'crosslingual_scorer': 'live'}) == k0
    k1 = cache.get_cache_key('a', 'b', 'grc', {**base, 'crosslingual_scorer': 'evaluation'})
    k2 = cache.get_cache_key('a', 'b', 'grc', {**base, 'crosslingual_scorer': 'evaluation',
                                               'crosslingual_lemma_gate': 'exclude'})
    assert len({k0, k1, k2}) == 3


def test_parse_search_request_carries_the_scorer_from_the_top_level(monkeypatch):
    monkeypatch.setattr(sm, '_resolve_with_fallback', lambda d, lang, tid: (f'/x/{tid}', lang))
    params = sm._parse_search_request({
        'source': 'homer.iliad.part.1.tess', 'target': 'vergil.aeneid.part.1.tess',
        'source_language': 'grc', 'target_language': 'la',
        'match_type': 'crosslingual_fusion', 'crosslingual_scorer': 'evaluation'})
    assert params['settings']['crosslingual_scorer'] == 'evaluation'


def test_evaluation_scorer_function_default_is_unchanged(monkeypatch):
    """make_fused_scorer keeps the baseline rule unless v2 is asked for or set in the environment."""
    sys.path.insert(0, str(ROOT / 'evaluation' / 'scripts'))
    import crosslingual_common as cc
    monkeypatch.delenv('XL_RARITY_VARIANT', raising=False)
    with pytest.raises(ValueError):
        cc.make_fused_scorer('a.tess', 'b.tess', [], [], None, None, verbose=False, lone_pair_rule='v9')


GREEK = 'homer.iliad.part.1'
LATIN = 'vergil.aeneid.part.1'
HAVE_DATA = all([
    (ROOT / 'texts' / 'grc' / f'{GREEK}.tess').exists(),
    (ROOT / 'texts' / 'la' / f'{LATIN}.tess').exists(),
    (ROOT / 'backend' / 'embeddings' / 'grc' / f'{GREEK}.npy').exists(),
    (ROOT / 'backend' / 'embeddings' / 'la' / f'{LATIN}.npy').exists(),
])


@pytest.mark.skipif(not HAVE_DATA, reason='texts or embeddings absent')
def test_evaluation_path_equals_fused_score_on_aeneid1_iliad1(monkeypatch):
    monkeypatch.setenv('XL_RARITY_VARIANT', 'v2')
    monkeypatch.setenv('TESSERAE_USE_DIRECT_SEARCH', '1')
    sys.path.insert(0, str(ROOT / 'scripts' / 'review'))
    import crosslingual_evaluation_identity as ident
    R, search_module, su, tu = ident.site_units()
    ev_rows, _ = ident.evaluation_side(su, tu, 200)
    for sl in ('la', 'grc'):
        live_rows = ident.live_side(R, search_module, sl, 200)
        problems, _ = ident.compare(ev_rows, live_rows)
        assert not problems, problems[:5]


def test_evaluation_path_declines_texts_too_long_to_compare_line_by_line():
    from backend import crosslingual_evaluation_path as ev
    units = [{}] * 6000          # 36 million cells
    with pytest.raises(ev.EvaluationPathError):
        ev.score_pairs(units, units, 'la', 'a.tess', 'b.tess', object(), object(),
                       gate='off', penalty_factor=0.5, min_lemma_matches=2,
                       min_matches=1, max_results=500)


# --- Review points on pull request 991 (2026-10-17) ---------------------------------

def test_cross_settings_dataclass_holds_gate_off_for_evaluation_without_a_named_gate():
    """The branch that sets the gate to off reaches the CrossSettings the search reads."""
    for source, target in (('grc', 'la'), ('la', 'grc')):
        cs = sm._cross_settings(_params(source, target), {'crosslingual_scorer': 'evaluation'})
        assert type(cs).__name__ == 'CrossSettings'
        assert cs.crosslingual_scorer == 'evaluation'
        assert cs.crosslingual_lemma_gate == 'off'
    # Not named is the only trigger: a named gate, including exclude, is kept.
    for gate in ('exclude', 'penalty', 'off'):
        cs = sm._cross_settings(_params('grc', 'la'), {'crosslingual_scorer': 'evaluation',
                                                      'crosslingual_lemma_gate': gate})
        assert cs.crosslingual_lemma_gate == gate
    # The live scorer is untouched by the branch.
    assert sm._cross_settings(_params('grc', 'la'), {}).crosslingual_lemma_gate == 'exclude'


def test_cache_keys_differ_between_the_scorers_and_between_gate_variants():
    base = {'match_type': 'crosslingual_fusion', 'source_language': 'grc', 'target_language': 'la',
            'min_matches': 1, 'max_results': 0}
    variants = {
        'live': {},
        'evaluation': {'crosslingual_scorer': 'evaluation'},
        'evaluation_exclude': {'crosslingual_scorer': 'evaluation', 'crosslingual_lemma_gate': 'exclude'},
        'evaluation_penalty': {'crosslingual_scorer': 'evaluation', 'crosslingual_lemma_gate': 'penalty'},
        'evaluation_penalty_03': {'crosslingual_scorer': 'evaluation', 'crosslingual_lemma_gate': 'penalty',
                                  'crosslingual_penalty_factor': 0.3},
        'evaluation_off_named': {'crosslingual_scorer': 'evaluation', 'crosslingual_lemma_gate': 'off'},
    }
    keys = {n: cache.get_cache_key('a.tess', 'b.tess', 'grc', {**base, **v}) for n, v in variants.items()}
    # Naming the default gate explicitly is the same request as not naming it.
    assert keys.pop('evaluation_off_named') == keys['evaluation']
    assert len(set(keys.values())) == len(keys), keys
    # And a request under 'live' written out is the default request.
    assert cache.get_cache_key('a.tess', 'b.tess', 'grc', {**base, 'crosslingual_scorer': 'live'}) == keys['live']


def test_poll_job_key_differs_between_the_scorers(monkeypatch):
    from flask import Flask
    from backend.blueprints import async_poll
    seen = []

    def fake_poll(name, key, compute, transform, **kw):
        seen.append(key)
        return {'ok': True}
    monkeypatch.setattr(async_poll, 'poll', fake_poll)
    app = Flask(__name__)
    app.register_blueprint(sm.search_bp)
    client = app.test_client()
    q = '?source=a.tess&target=b.tess&source_language=grc&target_language=la'
    for extra in ('', '&crosslingual_scorer=live', '&crosslingual_scorer=evaluation',
                  '&crosslingual_scorer=bogus'):
        prefix = '/crosslingual-search-poll'
        client.get(prefix + q + extra)
    assert len(seen) == 4
    assert seen[0] == seen[1] == seen[3]       # live, written out, or unknown value
    assert seen[2] != seen[0]


def test_missing_evaluation_scorer_file_gives_a_readable_error_not_an_exception(monkeypatch, tmp_path):
    from backend import crosslingual_evaluation_path as ev
    monkeypatch.setattr(ev, 'COMMON_PATH', tmp_path / 'absent.py')
    monkeypatch.setattr(ev, '_common', None)
    params = {**_params('grc', 'la'), 'settings': {}}
    settings = {'crosslingual_scorer': 'evaluation', 'max_results': 500, 'min_matches': 1}
    units = [{'ref': 'x 1.1', 'text': 't', 'tokens': ['t'], 'lemmas': ['t']}]
    out = sm._direct_crosslingual_core(params, units, units, settings)
    assert isinstance(out, dict) and 'results' not in out
    assert 'not installed' in out['error']


def test_size_guard_fires_before_any_large_array_is_made(monkeypatch):
    """A pair just over the limit raises before the scorer (and its cosine matrix) is built."""
    from backend import crosslingual_evaluation_path as ev

    class Boom:
        def make_fused_scorer(self, *a, **k):
            raise AssertionError('allocation reached')
    monkeypatch.setattr(ev, '_load_common', lambda: Boom())
    n_src = 5000
    n_tgt = ev.MAX_MATRIX_CELLS // n_src + 1          # one line past the limit
    assert n_src * n_tgt > ev.MAX_MATRIX_CELLS
    with pytest.raises(ev.EvaluationPathError):
        ev.score_pairs([{}] * n_src, [{}] * n_tgt, 'la', 'a.tess', 'b.tess', object(), object(),
                       gate='off', penalty_factor=0.5, min_lemma_matches=2, min_matches=1, max_results=0)
    # At the limit exactly the guard lets the search through to the scorer.
    with pytest.raises(AssertionError, match='allocation reached'):
        ev.score_pairs([{}] * n_src, [{}] * (ev.MAX_MATRIX_CELLS // n_src), 'la', 'a.tess', 'b.tess',
                       object(), object(), gate='off', penalty_factor=0.5, min_lemma_matches=2,
                       min_matches=1, max_results=0)
