"""Ennius Annales fragments of uncertain book or work read plainly as loci."""
from backend.utils import build_citation, format_short_locus


def test_uncertain_book_keeps_skutsch_number_and_says_so():
    assert format_short_locus('ennius ann. sedinc.481') == '481 (book uncertain)'


def test_uncertain_work():
    assert format_short_locus('ennius ann. opinc.37') == 'uncertain work 37'
    assert format_short_locus('ennius ann. opinc.1a') == 'uncertain work 1a'


def test_ordinary_ennius_and_other_loci_unchanged():
    assert format_short_locus('ennius ann. 12.363') == '12.363'
    assert format_short_locus('hom. il. 1.1') == '1.1'
    assert format_short_locus('verg. aen. 1.94') == '1.94'


def test_citation_carries_the_readable_locus():
    assert build_citation('ennius.annales.tess', 'ennius ann. sedinc.481').endswith('481 (book uncertain)')
