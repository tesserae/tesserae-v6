"""A Hebrew query typed without vowel points matches every homograph reading
of its consonants (#483 follow-up): אל typed bare must find אל "to", אל² "not"
and אל³ "God", through the index's fallback forms."""
from backend.hebrew.processor import homograph_readings, is_unpointed, base_lemma


def test_readings_cover_the_group():
    readings = homograph_readings('אל')
    assert 'אל' in readings and 'אל²' in readings and 'אל³' in readings
    assert all(base_lemma(r) == 'אל' for r in readings)


def test_a_numbered_lemma_lists_the_same_group():
    assert set(homograph_readings('מלך²')) == set(homograph_readings('מלך'))
    assert 'מלך' in homograph_readings('מלך²')


def test_unknown_lemma_is_its_own_reading():
    assert homograph_readings('זזזז') == ['זזזז']


def test_pointed_and_unpointed_tokens():
    assert is_unpointed('אל')
    assert is_unpointed('מלך')
    assert not is_unpointed('אֵל')
    assert not is_unpointed('מִזְמ֥וֹר')


def test_line_search_fallbacks_expand_a_bare_word():
    from backend.app import _hebrew_unpointed_fallbacks
    fallbacks, lemmas = _hebrew_unpointed_fallbacks('אל', {'אל'}, set())
    assert lemmas == {'אל'}
    assert {'אל²', 'אל³'} <= fallbacks['אל']


def test_line_search_fallbacks_skip_a_stopped_reading_in_favour_of_content():
    from backend.app import _hebrew_unpointed_fallbacks
    fallbacks, lemmas = _hebrew_unpointed_fallbacks('אל אלהים', {'אל', 'אלהים'}, {'אל'})
    assert 'אל' not in lemmas and 'אלהים' in lemmas
    canonical = next(iter(fallbacks))
    assert base_lemma(canonical) == 'אל' and canonical != 'אל'


def test_pointed_query_gets_no_fallbacks():
    from backend.app import _hebrew_unpointed_fallbacks
    fallbacks, lemmas = _hebrew_unpointed_fallbacks('אֵל', {'אל³'}, set())
    assert fallbacks is None and lemmas == {'אל³'}
