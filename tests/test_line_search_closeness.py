"""Closeness fields on Line Search hits (owner's review 2026-10-10: a
four-word query put lines sharing one word on top; the default should be a
near quotation). Tightened the same day after the first live form marked 23
of 36 hits for "sit tibi terra levis" as quotations: the common words sit
and tibi are dropped by the lemma search, so a line is a quotation only when
it also carries the query's own words in surface form."""
from backend.app import _is_near_quotation, _surface_hits, _span

Q = 'sit tibi terra levis'
LEMMAS = {'terra', 'levis'}


def test_martial_is_a_quotation():
    tokens = 'Sit tibi terra leuis mollique tegaris harena'.split()
    hits = _surface_hits(Q, tokens, 'la')
    assert hits == 4
    assert _is_near_quotation(LEMMAS, LEMMAS, [2, 3], Q, surface_hits=hits)


def test_caesar_with_only_the_key_words_is_not():
    tokens = 'haec levibus cratibus terraque inaequat'.split()
    hits = _surface_hits(Q, tokens, 'la')
    assert hits == 1  # terraque -> terra; levibus is not levis
    assert not _is_near_quotation(LEMMAS, LEMMAS, [1, 3], Q, surface_hits=hits)


def test_one_inflected_word_still_counts():
    # "terra tibi sit leuis": every word present, in another order
    tokens = 'terra tibi sit leuis'.split()
    assert _surface_hits(Q, tokens, 'la') == 4
    # "sit tibi terra leuior": one word inflected, still a quotation
    tokens = 'sit tibi terra leuior'.split()
    hits = _surface_hits(Q, tokens, 'la')
    assert hits == 3
    assert _is_near_quotation(LEMMAS, LEMMAS, [2, 3], Q, surface_hits=hits)


def test_two_of_four_words_is_not_a_quotation():
    tokens = 'Ut cum terra levis mediam virgultaque molem'.split()
    hits = _surface_hits(Q, tokens, 'la')
    assert hits == 2
    assert not _is_near_quotation(LEMMAS, LEMMAS, [2, 3], Q, surface_hits=hits)


def test_all_words_scattered_is_not():
    assert not _is_near_quotation(LEMMAS, LEMMAS, [0, 9], 'terra levis', surface_hits=2)


def test_missing_a_lemma_is_not():
    assert not _is_near_quotation({'terra'}, LEMMAS, [0], 'terra levis', surface_hits=1)


def test_one_word_query_is_never_a_quotation():
    assert not _is_near_quotation({'terra'}, {'terra'}, [0], 'terra', surface_hits=1)


def test_no_positions_is_not():
    assert not _is_near_quotation(LEMMAS, LEMMAS, [], 'terra levis', surface_hits=2)


def test_without_surface_information_the_window_rule_alone_applies():
    assert _is_near_quotation(LEMMAS, LEMMAS, [2, 5], 'terra levis')  # width 4 <= 2 + 2


def test_surface_norm_strips_greek_accents_and_punctuation():
    assert _surface_hits('μῆνιν ἄειδε', ['Μῆνιν', 'ἄειδε,', 'θεά'], 'grc') == 2
    assert _surface_hits('arma virumque', ['Arma', 'uirumque', 'cano'], 'la') == 2


def test_words_scattered_through_a_long_sentence_do_not_count_within_the_window():
    tokens = ('terra inquam cuius modi sit refert et ad quam rem bona aut non bona sit '
              'ea tibi fundum colere oportet').split()
    assert _surface_hits(Q, tokens, 'la') == 3
    assert _surface_hits(Q, tokens, 'la', window=6) == 2
    assert not _is_near_quotation(LEMMAS, LEMMAS, [0, 3], Q,
                                  surface_hits=_surface_hits(Q, tokens, 'la', window=6))


def test_tibullus_reworking_within_the_window_counts():
    tokens = 'terraque securae sit super ossa leuis'.split()
    assert _surface_hits(Q, tokens, 'la', window=6) == 3


def test_span():
    assert _span([3, 4, 5, 6]) == 4
    assert _span([]) is None
