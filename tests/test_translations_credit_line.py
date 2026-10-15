"""The work-level translation credit names the translator (2026-10-15)."""
from backend.translations import credit_line


def test_translator_put_in_front_of_a_site_name():
    data = {'attribution': 'Perseus Digital Library, Tufts University',
            'sources': [{'translator': 'Theodore C. Williams', 'year': 1910}]}
    assert credit_line(data) == 'Theodore C. Williams (1910), via Perseus Digital Library, Tufts University'


def test_attribution_that_already_names_the_translator_is_kept():
    data = {'attribution': 'H. A. Bellows (1922), via Project Gutenberg',
            'sources': [{'translator': 'H. A. Bellows', 'year': 1922}]}
    assert credit_line(data) == 'H. A. Bellows (1922), via Project Gutenberg'


def test_no_sources_keeps_the_attribution_and_no_attribution_uses_the_translator():
    assert credit_line({'attribution': 'Someone'}) == 'Someone'
    assert credit_line({'sources': [{'translator': 'A. Translator'}]}) == 'A. Translator'
