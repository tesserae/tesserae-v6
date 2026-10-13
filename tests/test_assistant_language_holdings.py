"""A question about what the site holds in a language is answered from that
language's listing, and a work title that contains a language word is not."""
import pytest

from backend.assistant import actions, agent, corpus_lookup, searches

PERSIAN_ROWS = [
    {'id': 'hafez.divan.tess', 'author': 'Hafez', 'title': 'Divan', 'display_name': 'Hafez, Divan'},
    {'id': 'rumi.masnavi.part.1.tess', 'author': 'Rumi', 'title': 'Masnavi', 'display_name': 'Rumi, Masnavi 1'},
    {'id': 'rumi.masnavi.part.2.tess', 'author': 'Rumi', 'title': 'Masnavi', 'display_name': 'Rumi, Masnavi 2'},
]


@pytest.mark.parametrize('question,code', [
    ('What Persian works do you hold?', 'fa'),
    ('What do you have in Urdu?', 'ur'),
    ('Which Greek authors are in the corpus?', 'grc'),
    ('Do you have anything in Coptic?', 'cop'),
    ('What Latin works by Ovid do you hold?', 'la'),
])
def test_a_language_question_names_its_language(question, code):
    assert actions.holdings_language(question) == code


@pytest.mark.parametrize('question', [
    'Aeschylus Persians',
    'Do you hold Aeschylus Persians?',
    'Compare Greek and Latin works in the corpus',
    'How do I search?',
])
def test_a_title_or_a_comparison_is_not_a_language_question(question):
    assert actions.holdings_language(question) is None


@pytest.fixture
def prepared(monkeypatch):
    monkeypatch.setattr(agent.model, 'is_available', lambda: True)
    monkeypatch.setattr(agent, '_named_works', lambda q: {})
    monkeypatch.setattr(searches, 'corpus_census', lambda: {})

    def fake_run(name, args):
        assert name == 'list_texts'
        return PERSIAN_ROWS if args['language'] == 'fa' else []
    monkeypatch.setattr(searches, 'run', fake_run)

    def go(question, authors=()):
        monkeypatch.setattr(corpus_lookup, 'named_texts',
                            lambda q, language=None, limit=2: list(authors))
        steps = []
        out = agent._prepare(question, steps.append)
        return out, steps
    return go


def test_persian_works_are_listed_from_the_persian_listing(prepared):
    out, steps = prepared('What Persian works do you hold?')
    fact = next(f for f in out['facts'] if f.get('language') == 'Persian')
    assert fact['works'] == 2          # the two Masnavi files are one work
    assert fact['by_author'] == {'Hafez': ['Divan'], 'Rumi': ['Masnavi']}
    assert 'listing what the corpus holds in Persian' in steps


def test_arabic_is_reported_as_not_served(prepared):
    out, _ = prepared('What Arabic works do you hold?')
    fact = next(f for f in out['facts'] if f.get('language') == 'Arabic')
    assert fact['works'] == 0
    assert 'no served Arabic texts' in fact['note']
    assert 'by_author' not in fact


def test_a_named_author_keeps_the_author_path(prepared):
    out, _ = prepared('What Latin works by Ovid do you hold?',
                      authors=[{'id': 'ovid.met.tess', 'author': 'Ovid'}])
    assert not any(f.get('kind', '').startswith('HOLDINGS') for f in out['facts'])
