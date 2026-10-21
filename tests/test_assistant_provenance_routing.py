"""A question about where the site's material comes from is answered from the site pages."""
from backend.assistant import agent


def test_provenance_questions_go_to_the_guide():
    for q in ('Where do the Greek texts come from?',
              'Where do the inscriptions and papyri come from?',
              'Which edition of the Aeneid does Tesserae use?',
              'Where do the place coordinates come from?'):
        assert agent._is_about_the_tool(q), q


def test_a_phrase_or_a_holdings_question_still_goes_to_the_corpus():
    for q in ('Where does arma virumque come from?',
              'where does the phrase "tantae molis" come from?',
              'What Greek texts do you have?'):
        assert not agent._is_about_the_tool(q), q
