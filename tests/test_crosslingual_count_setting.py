"""The Greek-Latin counting and lone-pair settings of the evaluation scorer (2026-10-17).

crosslingual_dict_count  words (default since 2026-10-18) | pairs
crosslingual_lone_pair   keep (default)  | rare | drop

The scorer tests use a fixture of one Greek line and one Latin line with a crafted dictionary
(one Latin word matched to two Greek words, as Achilles to a patronymic and a name) and patched
document frequencies, so they need no texts, caches or index.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

from backend import cache
from backend.blueprints import search as sm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluation' / 'scripts'))
import crosslingual_common as cc  # noqa: E402


def _params(source_language='grc', target_language='la'):
    return {'source_id': 'a', 'target_id': 'b', 'language': 'grc',
            'source_language': source_language, 'target_language': target_language}


# --- The settings -------------------------------------------------------------------

def test_defaults_and_bad_values():
    cs = sm._cross_settings(_params(), {'crosslingual_scorer': 'evaluation'})
    assert (cs.crosslingual_dict_count, cs.crosslingual_lone_pair) == ('words', 'keep')
    bad = sm._cross_settings(_params(), {'crosslingual_scorer': 'evaluation',
                                         'crosslingual_dict_count': 'bogus',
                                         'crosslingual_lone_pair': 'bogus'})
    assert (bad.crosslingual_dict_count, bad.crosslingual_lone_pair) == ('words', 'keep')
    pairs = sm._cross_settings(_params(), {'crosslingual_scorer': 'evaluation',
                                           'crosslingual_dict_count': 'pairs'})
    assert pairs.crosslingual_dict_count == 'pairs'
    named = sm._cross_settings(_params('la', 'grc'), {'crosslingual_scorer': 'evaluation',
                                                      'crosslingual_dict_count': 'words',
                                                      'crosslingual_lone_pair': 'rare'})
    assert (named.crosslingual_dict_count, named.crosslingual_lone_pair) == ('words', 'rare')


def test_request_carries_the_settings_from_the_top_level(monkeypatch):
    monkeypatch.setattr(sm, '_resolve_with_fallback', lambda d, lang, tid: (f'/x/{tid}', lang))
    params = sm._parse_search_request({
        'source': 'homer.iliad.part.1.tess', 'target': 'vergil.aeneid.part.1.tess',
        'source_language': 'grc', 'target_language': 'la', 'match_type': 'crosslingual_fusion',
        'crosslingual_scorer': 'evaluation', 'crosslingual_dict_count': 'words',
        'crosslingual_lone_pair': 'drop'})
    assert params['settings']['crosslingual_dict_count'] == 'words'
    assert params['settings']['crosslingual_lone_pair'] == 'drop'


def test_cache_keys_by_default_and_by_setting():
    base = {'match_type': 'crosslingual_fusion', 'source_language': 'grc', 'target_language': 'la'}
    k_live = cache.get_cache_key('a', 'b', 'grc', dict(base))
    # (b) Under the live scorer the two settings change nothing, so they join no key.
    for extra in ({'crosslingual_dict_count': 'words', 'crosslingual_lone_pair': 'drop'},
                  {'crosslingual_dict_count': 'pairs'}):
        assert cache.get_cache_key('a', 'b', 'grc', {**base, **extra}) == k_live
    ev = {**base, 'crosslingual_scorer': 'evaluation'}
    k0 = cache.get_cache_key('a', 'b', 'grc', ev)
    # Naming the defaults is the same request as not naming them.
    assert cache.get_cache_key('a', 'b', 'grc', {**ev, 'crosslingual_dict_count': 'words',
                                                 'crosslingual_lone_pair': 'keep'}) == k0
    # (a) The default evaluation key differs from the key with 'pairs'.
    k_pairs = cache.get_cache_key('a', 'b', 'grc', {**ev, 'crosslingual_dict_count': 'pairs'})
    assert k_pairs != k0
    keys = {k0, k_pairs}
    for extra in ({'crosslingual_dict_count': 'words', 'crosslingual_lone_pair': 'rare'},
                  {'crosslingual_dict_count': 'words', 'crosslingual_lone_pair': 'drop'},
                  {'crosslingual_dict_count': 'pairs', 'crosslingual_lone_pair': 'rare'}):
        keys.add(cache.get_cache_key('a', 'b', 'grc', {**ev, **extra}))
    assert len(keys) == 5


def test_evaluation_key_differs_from_the_key_the_old_rule_produced():
    import hashlib
    import inspect
    import json
    base = {'match_type': 'crosslingual_fusion', 'source_language': 'grc', 'target_language': 'la'}
    ev = {**base, 'crosslingual_scorer': 'evaluation'}
    new_key = cache.get_cache_key('a', 'b', 'grc', ev)
    # (c) The count is always among the key parts under the evaluation scorer, so an entry
    # cached before 2026-10-18 (no count part, computed under 'pairs') is never reached.
    assert "key_parts['crosslingual_dict_count']" in inspect.getsource(cache.get_cache_key)
    captured = {}
    real = json.dumps

    def spy(obj, *a, **k):
        captured['parts'] = dict(obj) if isinstance(obj, dict) else obj
        return real(obj, *a, **k)
    import unittest.mock as mock
    with mock.patch.object(cache.json, 'dumps', spy):
        cache.get_cache_key('a', 'b', 'grc', ev)
    parts = captured['parts']
    assert parts['crosslingual_dict_count'] == 'words'
    old_parts = {k: v for k, v in parts.items() if k != 'crosslingual_dict_count'}
    old_key = hashlib.md5(real(old_parts, sort_keys=True).encode()).hexdigest()  # nosec B324
    assert old_key != new_key


def test_poll_job_key_has_the_count_under_evaluation_and_lone_pair_only_when_not_default(monkeypatch):
    from flask import Flask
    from backend.blueprints import async_poll
    seen = []
    monkeypatch.setattr(async_poll, 'poll', lambda name, key, compute, transform, **kw: seen.append(key) or {'ok': True})
    app = Flask(__name__)
    app.register_blueprint(sm.search_bp)
    client = app.test_client()
    q = '/crosslingual-search-poll?source=a.tess&target=b.tess&source_language=grc&target_language=la'
    for extra in ('', '&crosslingual_scorer=evaluation',
                  '&crosslingual_scorer=evaluation&crosslingual_dict_count=pairs&crosslingual_lone_pair=keep',
                  '&crosslingual_scorer=evaluation&crosslingual_dict_count=words',
                  '&crosslingual_scorer=evaluation&crosslingual_lone_pair=drop',
                  '&crosslingual_dict_count=words&crosslingual_lone_pair=drop'):
        client.get(q + extra)
    assert seen[0] == seen[5]                  # live ignores the options
    assert seen[1] == seen[3]                  # 'words' named is the default, same job
    assert seen[2] != seen[1]                  # 'pairs' has its own job
    assert len({seen[0], seen[1], seen[2], seen[4]}) == 4


# --- The scorer ---------------------------------------------------------------------

WORDS_TWO_TO_ONE = {('πηληιαδησ', 'achilles'), ('αχιλλευσ', 'achilles')}


@pytest.fixture
def fixture_scorer(monkeypatch):
    """make_fused_scorer on one Greek line and one Latin line with a crafted dictionary."""
    import backend.fusion as fusion
    import backend.blueprints.hapax as hapax
    state = {'matches': {(0, 0): set(WORDS_TWO_TO_ONE)},
             'grc_df': {'πηληιαδησ': 3, 'αχιλλευσ': 4, 'x': 500},
             'la_df': {'achilles': 2, 'y': 500}}
    monkeypatch.setattr(cc, 'build_dictionary_scores', lambda g, lt, lat_indices=None: state['matches'])
    monkeypatch.setattr(fusion, '_get_corpus_doc_freqs',
                        lambda lemmas, language='la': state['grc_df'] if language == 'grc' else state['la_df'])
    monkeypatch.setattr(fusion, '_get_total_texts', lambda language='la': 800)
    monkeypatch.setattr(fusion, '_get_text_meter', lambda f: None)
    monkeypatch.setattr(fusion, 'find_syntax_matches', lambda *a, **k: {})
    monkeypatch.setattr(hapax, 'rare_word_threshold', lambda language, share=0.12: 10)
    grc = [{'lemmas': ['πηληιαδησ', 'αχιλλευσ']}]
    lat = [{'lemmas': ['achilles']}]
    emb = np.array([[1.0, 0.0, 0.0, 0.0]])

    def make(**kw):
        scorer, _ = cc.make_fused_scorer('g.tess', 'l.tess', grc, lat, emb, emb, verbose=False,
                                         lone_pair_rule='v2', **kw)
        return scorer
    make.state = state
    return make


def test_one_to_two_match_counts_two_under_pairs_and_one_under_words(fixture_scorer):
    pairs = fixture_scorer(dict_count='pairs')
    words = fixture_scorer(dict_count='words')
    eff_matches, distinct, removed = words.parts['effective'](0, 0)
    assert distinct == 1 and not removed and len(eff_matches) == 2
    assert words.parts['distinct_words'](WORDS_TWO_TO_ONE) == 1
    # pairs: two matched pairs, so the lone-pair rule (one pair) does not apply and the
    # dictionary score is scaled by sqrt(2). words: one word, scaled by 1, rule applies.
    assert pairs(0, 0) > words(0, 0)
    # A genuine two-word match counts two under both values.
    fixture_scorer.state['matches'] = {(0, 0): {('πηληιαδησ', 'achilles'), ('αχιλλευσ', 'y')}}
    fixture_scorer.state['la_df']['y'] = 2
    two_pairs, two_words = fixture_scorer(dict_count='pairs'), fixture_scorer(dict_count='words')
    assert two_pairs(0, 0) == two_words(0, 0)


def test_defaults_equal_named_defaults_and_environment(fixture_scorer, monkeypatch):
    base = fixture_scorer()
    named = fixture_scorer(dict_count='words', lone_pair='keep')
    assert base(0, 0) == named(0, 0)
    monkeypatch.setenv('XL_DICT_COUNT', 'pairs')
    assert fixture_scorer()(0, 0) == fixture_scorer(dict_count='pairs')(0, 0)
    assert fixture_scorer()(0, 0) != base(0, 0)
    monkeypatch.setenv('XL_LONE_PAIR', 'bogus')
    with pytest.raises(ValueError):
        fixture_scorer()
    with pytest.raises(ValueError):
        fixture_scorer(dict_count='triples')


def test_lone_pair_keep_rare_drop(fixture_scorer):
    # Rare: every matched word under the threshold of 10 (df 3, 4 and 2). Nothing changes.
    rare_keep = fixture_scorer(dict_count='words', lone_pair='keep')(0, 0)
    assert fixture_scorer(dict_count='words', lone_pair='rare')(0, 0) == rare_keep
    assert fixture_scorer(dict_count='words', lone_pair='drop')(0, 0) == rare_keep
    # Common: one Greek word above the threshold. 'rare' removes the dictionary channel, so the
    # score is the semantic channel alone (1.2 x cosine 1.0), 'drop' removes the pair.
    fixture_scorer.state['grc_df']['αχιλλευσ'] = 500
    kept = fixture_scorer(dict_count='words', lone_pair='keep')(0, 0)
    assert kept > 1.2
    rare = fixture_scorer(dict_count='words', lone_pair='rare')
    assert rare(0, 0) == pytest.approx(1.2)
    assert rare.parts['effective'](0, 0)[0] is None
    dropped = fixture_scorer(dict_count='words', lone_pair='drop')
    assert dropped(0, 0) == float('-inf')
    assert dropped.parts['effective'](0, 0)[2] is True


def test_a_pair_with_two_distinct_words_is_never_treated_as_lone(fixture_scorer):
    fixture_scorer.state['matches'] = {(0, 0): {('x', 'achilles'), ('αχιλλευσ', 'y')}}
    fixture_scorer.state['la_df']['y'] = 500
    s_keep = fixture_scorer(dict_count='words', lone_pair='keep')(0, 0)
    assert fixture_scorer(dict_count='words', lone_pair='drop')(0, 0) == s_keep
    assert fixture_scorer(dict_count='words', lone_pair='rare')(0, 0) == s_keep


def test_score_pairs_lists_by_the_settings(fixture_scorer):
    from backend import crosslingual_evaluation_path as ev
    fixture_scorer.state['grc_df']['αχιλλευσ'] = 500          # the lone pair is common
    grc = [{'lemmas': ['πηληιαδησ', 'αχιλλευσ']}]
    lat = [{'lemmas': ['achilles']}]
    emb = np.array([[1.0, 0.0, 0.0, 0.0]])

    def run(**kw):
        return ev.score_pairs(grc, lat, 'grc', 'g.tess', 'l.tess', emb, emb, gate='off',
                              penalty_factor=0.5, min_lemma_matches=2, min_matches=1,
                              max_results=10, **kw)
    kept = run(dict_count='words', lone_pair='keep')
    assert len(kept) == 1 and kept[0]['has_dict'] and kept[0]['distinct'] == 1
    rare = run(dict_count='words', lone_pair='rare')
    assert len(rare) == 1 and not rare[0]['has_dict'] and rare[0]['distinct'] == 0 and rare[0]['pairs'] == []
    assert run(dict_count='words', lone_pair='drop') == []
    # The default listing is the words count with the pair kept.
    default = run()
    assert default[0]['has_dict'] and default[0]['distinct'] == 1
    # A request for a dictionary-confirmed list (min_matches 2) also loses the dropped-to-cosine row.
    assert ev.score_pairs(grc, lat, 'grc', 'g.tess', 'l.tess', emb, emb, gate='off', penalty_factor=0.5,
                          min_lemma_matches=2, min_matches=2, max_results=10,
                          dict_count='words', lone_pair='rare') == []


def test_make_fused_scorer_defaults_with_a_clean_environment(fixture_scorer, monkeypatch):
    """No arguments and no environment variables: words, keep and the v2 rarity rule."""
    for name in ('XL_DICT_COUNT', 'XL_LONE_PAIR', 'XL_RARITY_VARIANT'):
        monkeypatch.delenv(name, raising=False)
    fixture_scorer.state['matches'] = {(0, 0): {('x', 'achilles'), ('πηληιαδησ', 'achilles')}}
    fixture_scorer.state['grc_df']['x'] = 5
    grc = [{'lemmas': ['πηληιαδησ', 'x']}]
    lat = [{'lemmas': ['achilles']}]
    emb = np.array([[1.0, 0.0, 0.0, 0.0]])
    plain, _ = cc.make_fused_scorer('g.tess', 'l.tess', grc, lat, emb, emb, verbose=False)
    named, _ = cc.make_fused_scorer('g.tess', 'l.tess', grc, lat, emb, emb, verbose=False,
                                    dict_count='words', lone_pair='keep', lone_pair_rule='v2')
    old, _ = cc.make_fused_scorer('g.tess', 'l.tess', grc, lat, emb, emb, verbose=False,
                                  dict_count='pairs', lone_pair='keep', lone_pair_rule='baseline')
    assert plain(0, 0) == named(0, 0)
    assert plain(0, 0) != old(0, 0)
    assert plain.parts['effective'](0, 0) == named.parts['effective'](0, 0)
