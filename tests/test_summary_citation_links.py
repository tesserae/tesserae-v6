"""The Search One Text summary links each passage it cites (backend/blueprints/passages.py)."""
from backend.blueprints.passages import _cite_full_refs, _locus


def test_locus_reads_roman_and_arabic_numbers():
    assert _locus('hamlet IV.5.165') == 'IV.5.165'
    assert _locus('verg. aen. 4.61') == '4.61'
    assert _locus('tac. ann. 1.73') == '1.73'


def test_roman_numbered_play_references_are_linked():
    """Hamlet is cited by act, scene and line with a Roman act number (2026-10-20)."""
    text, cites = _cite_full_refs('fear gives pause (III.1.66) and grief (I.2.135, IV.5.165).',
                                  ['hamlet III.1.66', 'hamlet I.2.135', 'hamlet IV.5.165'])
    assert cites == ['hamlet III.1.66', 'hamlet I.2.135', 'hamlet IV.5.165']
    assert '(hamlet I.2.135, hamlet IV.5.165)' in text


def test_a_bare_roman_numeral_with_no_passage_is_left_alone():
    assert _cite_full_refs('a word (I) and (IV)', ['hamlet I.1.1']) == ('a word (I) and (IV)', [])


def test_arabic_references_still_link():
    text, cites = _cite_full_refs('as Vergil says (4.61).', ['verg. aen. 4.61'])
    assert cites == ['verg. aen. 4.61'] and '(verg. aen. 4.61)' in text
