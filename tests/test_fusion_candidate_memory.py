"""The fusion channels' candidate lists must not grow with source units
times target units (2026-09-20). Two guards:

1. The fusion channels (stoplist_size -1 plus exclude_function_words)
   apply the language's function-word list instead of an empty set, so
   "the", "and", "qui", "sum" are not matching features. A plain -1, as a
   user may enter in the classic search, still means no stoplist.
2. candidate_cap bounds the matcher's candidate list to the same top set
   the channel runner's quick-IDF pre-filter would keep.
"""
import math
import os
import sys
from collections import Counter

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.matcher import Matcher, DEFAULT_LATIN_STOP_WORDS  # noqa: E402
from backend import fusion  # noqa: E402


def unit(ref, words):
    toks = words.split()
    return {'ref': ref, 'text': words, 'tokens': toks, 'lemmas': toks}


def test_minus_one_applies_function_words_not_an_empty_set():
    m = Matcher()
    assert 'qui' in DEFAULT_LATIN_STOP_WORDS and 'sum' in DEFAULT_LATIN_STOP_WORDS
    src = [unit('s1', 'qui sum arma')]
    tgt = [unit('t1', 'qui sum uir'), unit('t2', 'arma cano qui')]
    matches, _ = m.find_matches(src, tgt, {'match_type': 'lemma', 'min_matches': 1,
                                           'stoplist_size': -1, 'language': 'la',
                                           'exclude_function_words': True})
    pairs = {(x['source_idx'], x['target_idx']): sorted(x['matched_lemmas']) for x in matches}
    # t1 shares only function words: no candidate. t2 shares "arma" (and "qui", excluded).
    assert pairs == {(0, 1): ['arma']}


def test_minus_one_english_function_words():
    m = Matcher()
    src = [unit('s1', 'the summer day began')]
    tgt = [unit('t1', 'the and with that'), unit('t2', 'summer began the')]
    matches, _ = m.find_matches(src, tgt, {'match_type': 'lemma', 'min_matches': 1,
                                           'stoplist_size': -1, 'language': 'en',
                                           'exclude_function_words': True})
    pairs = {(x['source_idx'], x['target_idx']): sorted(x['matched_lemmas']) for x in matches}
    # common content words ("summer", "day", "began") stay matchable
    assert pairs == {(0, 1): ['began', 'summer']}


def test_unknown_language_minus_one_is_still_no_stoplist():
    m = Matcher()
    src = [unit('s1', 'alpha beta')]
    tgt = [unit('t1', 'alpha gamma')]
    matches, _ = m.find_matches(src, tgt, {'match_type': 'lemma', 'min_matches': 1,
                                           'stoplist_size': -1, 'language': 'xx',
                                           'exclude_function_words': True})
    assert [(x['source_idx'], x['target_idx']) for x in matches] == [(0, 0)]


def test_plain_minus_one_without_the_flag_keeps_its_old_meaning():
    """A user who enters -1 in the classic search gets no stoplist at all."""
    m = Matcher()
    src = [unit('s1', 'qui sum arma')]
    tgt = [unit('t1', 'qui sum uir')]
    matches, _ = m.find_matches(src, tgt, {'match_type': 'lemma', 'min_matches': 2,
                                           'stoplist_size': -1, 'language': 'la'})
    assert [(x['source_idx'], x['target_idx']) for x in matches] == [(0, 0)]


def test_fusion_lemma_channels_exclude_function_words():
    for name in ('lemma', 'lemma_min1', 'exact'):
        assert fusion.CHANNEL_CONFIGS[name].get('exclude_function_words') is True, name


def _quick_scores(src, tgt, matches):
    freq = Counter()
    for u in src + tgt:
        for l in set(u['lemmas']):
            freq[l] += 1
    n = len(src) + len(tgt)
    return [sum(math.log((n + 1) / (freq.get(l, 1) + 1)) + 1 for l in m['matched_lemmas'])
            for m in matches]


def test_candidate_cap_keeps_the_pre_filter_top_set():
    m = Matcher()
    words = ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta', 'eta', 'theta']
    # source i shares word i with every target that has it; rarer words score higher
    src = [unit(f's{i}', f'{words[i]} filler{i}') for i in range(8)]
    tgt = []
    for j in range(12):
        # word k appears in k+1 targets: alpha once, theta eight times
        tgt.append(unit(f't{j}', ' '.join(w for k, w in enumerate(words) if j <= k)))
    settings = {'match_type': 'lemma', 'min_matches': 1, 'stoplist_size': -1, 'language': 'xx'}
    full, _ = m.find_matches(src, tgt, dict(settings))
    scores = _quick_scores(src, tgt, full)
    cap = 5
    top_scores = sorted(scores, reverse=True)[:cap]
    capped, _ = m.find_matches(src, tgt, dict(settings, candidate_cap=cap))
    assert len(capped) == cap
    assert [round(x['_quick_score'], 9) for x in capped] == [round(x, 9) for x in top_scores]
    # sorted best first, and every kept pair is a real match from the full run
    full_pairs = {(x['source_idx'], x['target_idx']) for x in full}
    assert all((x['source_idx'], x['target_idx']) in full_pairs for x in capped)


def test_candidate_cap_larger_than_matches_changes_nothing_but_order():
    m = Matcher()
    src = [unit('s1', 'alpha beta'), unit('s2', 'gamma')]
    tgt = [unit('t1', 'alpha'), unit('t2', 'gamma beta')]
    settings = {'match_type': 'lemma', 'min_matches': 1, 'stoplist_size': -1, 'language': 'xx'}
    full, _ = m.find_matches(src, tgt, dict(settings))
    capped, _ = m.find_matches(src, tgt, dict(settings, candidate_cap=1000))
    key = lambda x: (x['source_idx'], x['target_idx'])  # noqa: E731
    assert sorted(map(key, full)) == sorted(map(key, capped))


def test_every_lemma_channel_has_a_result_cap():
    for name in ('lemma', 'lemma_min1', 'exact'):
        assert fusion.CHANNEL_CONFIGS[name].get('max_results', 0) > 0, name


def test_run_channel_passes_the_candidate_cap(monkeypatch):
    seen = {}

    class FakeMatcher:
        def find_matches(self, s, t, settings, corpus, cancellation):
            seen.update(settings)
            return [], 0

    cfg = dict(fusion.CHANNEL_CONFIGS['lemma_min1'])
    out = fusion.run_channel('lemma_min1', cfg, [unit('a', 'x')], [unit('b', 'y')],
                             FakeMatcher(), None, 'src', 'tgt')
    assert out == []
    assert seen['candidate_cap'] == cfg['max_results'] * 4
