"""The three functions named normalize_latin, pinned as they are today.

backend/matcher.py, backend/wildcard_search.py and backend/distance_filter.py
each export a function called normalize_latin. On 2026-09-21 they were three
different functions. Since then they have been reduced to two rules, both in
backend/latin_orthography.py, and this file records what each one does on the
same seven words so that anyone who changes or unifies them sees exactly what
moves.

  matcher.normalize_latin          fold_latin: lower case, v to u, j to i.
  distance_filter.normalize_latin  the same function (the very same object).
  wildcard_search.normalize_latin  fold_latin_surface: case KEPT, v to u,
                                   j to i, and a word-final -om becomes -um.

In plain words, the differences that remain: the search-box function keeps
capital letters and rewrites -om to -um ("servom" becomes "seruum", "VIRUM"
becomes "UIRUM"), while the other two lower-case everything and leave -om
alone ("servom" becomes "seruom", "VIRUM" becomes "uirum"). None of the three
touches Greek: "Ῥώμη" comes back unchanged, except that the two lower-casing
functions lower-case it too. The lemma tables hold keys such as "diuom", which
is why the -om rule must not be added to the lower-casing pair.
"""
import pytest

from backend import distance_filter, matcher, wildcard_search

WORDS = ['Iam', 'jam', 'servom', 'VIRUM', 'uirum', 'Juppiter', 'Ῥώμη']

EXPECTED = {
    # lower case, v to u, j to i; no -om rule
    'matcher': ['iam', 'iam', 'seruom', 'uirum', 'uirum', 'iuppiter', 'ῥώμη'],
    # the same function as matcher's
    'distance_filter': ['iam', 'iam', 'seruom', 'uirum', 'uirum', 'iuppiter', 'ῥώμη'],
    # case kept, v to u, j to i, final -om to -um
    'wildcard_search': ['Iam', 'iam', 'seruum', 'UIRUM', 'uirum', 'Iuppiter', 'Ῥώμη'],
}

FUNCTIONS = {
    'matcher': matcher.normalize_latin,
    'distance_filter': distance_filter.normalize_latin,
    'wildcard_search': wildcard_search.normalize_latin,
}


@pytest.mark.parametrize('module', sorted(FUNCTIONS))
def test_normalize_latin_on_the_shared_word_list(module):
    assert [FUNCTIONS[module](w) for w in WORDS] == EXPECTED[module]


def test_matcher_and_distance_filter_share_one_function():
    assert matcher.normalize_latin is distance_filter.normalize_latin


def test_wildcard_function_is_a_different_rule():
    assert wildcard_search.normalize_latin is not matcher.normalize_latin


@pytest.mark.parametrize('module', sorted(FUNCTIONS))
def test_each_is_idempotent_and_handles_empty(module):
    f = FUNCTIONS[module]
    assert [f(f(w)) for w in WORDS] == [f(w) for w in WORDS]     # folding twice changes nothing
    assert f('') == ''
