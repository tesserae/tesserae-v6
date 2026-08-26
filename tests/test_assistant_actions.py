"""Tessa hands the reader a control, and the control has to be real.

A link is a promise that something exists. If the model composed these it would
eventually offer a search of a work that is not in the corpus, in a language the
page does not accept, and the reader would land on an empty page believing the
corpus had been consulted. So every action is built in code from arguments a
search has already run with, and these tests pin that.
"""
from backend.assistant import actions

EXACT_FACT = {
    'kind': 'phrase occurrences',
    'args': {'query': 'arma virumque', 'search_type': 'exact', 'language': 'la'},
}
VARIANT_FACT = {
    'kind': 'VARIANT FORMS of the same phrase, found by lemma search.',
    'phrase': 'arma virumque',
}


def test_the_search_that_ran_becomes_the_first_action():
    built = actions.build([EXACT_FACT])
    assert built, 'a search that ran produced no way to open it'
    first = built[0]
    assert first['url'] == '/line-search?q=arma+virumque&type=exact'
    assert 'arma virumque' in first['label']


def test_the_other_search_type_is_offered_too():
    """Exact and lemma answer different questions, and which one you want is the
    commonest thing a reader gets wrong. Both are offered."""
    urls = [a['url'] for a in actions.build([EXACT_FACT])]
    assert '/line-search?q=arma+virumque&type=lemma' in urls


def test_a_variant_offer_becomes_a_clickable_lemma_search():
    urls = [a['url'] for a in actions.build([VARIANT_FACT])]
    assert '/line-search?q=arma+virumque&type=lemma' in urls


def test_the_same_url_is_never_offered_twice():
    built = actions.build([EXACT_FACT, VARIANT_FACT])
    assert len(built) == len({a['url'] for a in built})


def test_no_more_than_a_handful():
    built = actions.build([EXACT_FACT, VARIANT_FACT] * 6)
    assert len(built) <= actions.MAX_ACTIONS


def test_a_language_the_page_cannot_search_is_refused():
    assert actions.for_suggestion('line_search', phrase='x y z',
                                  search_type='exact', language='klingon') is None


def test_an_unknown_search_type_is_refused():
    assert actions.for_suggestion('line_search', phrase='x y z',
                                  search_type='fuzzy', language='la') is None


def test_facts_with_no_arguments_contribute_nothing():
    """A fact that records no search arguments must produce no link, rather than
    a link built from a guess."""
    assert actions.build([{'kind': 'phrase occurrences'}]) == []
    assert actions.build([{'kind': 'corpus listing', 'works': 2100}]) == []
    assert actions.build([]) == []
    assert actions.build(None) == []


def test_every_action_carries_what_the_page_needs_to_render_it():
    for a in actions.build([EXACT_FACT, VARIANT_FACT]):
        assert a['url'].startswith('/'), 'actions must stay inside the site'
        assert a['label'] and a['kind']


def test_the_query_is_url_encoded():
    a = actions.for_suggestion('theme_search', query='a warrior arms himself')
    assert ' ' not in a['url']
    assert a['url'].startswith('/theme-search?query=')


def test_reader_action_selects_the_whole_span_with_a_translation():
    a = actions.for_suggestion('read', work='vergil.aeneid',
                               ref='6.258', ref_end='6.263')
    assert 'work=vergil.aeneid.tess' in a['url']
    assert 'refEnd=6.263' in a['url']
    assert 'tab=translation' in a['url']


def test_compare_needs_both_texts():
    assert actions.for_suggestion('compare', source='vergil.aeneid',
                                  target='', language='la') is None
    a = actions.for_suggestion('compare', source='vergil.aeneid',
                               target='ovid.metamorphoses', language='la')
    assert a['url'].startswith('/?source=')
