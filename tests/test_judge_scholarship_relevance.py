"""The pure parts of scripts/events/judge_scholarship_relevance.py: reading the model's
answer, the prompt text and the event description."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'events'))

import judge_scholarship_relevance as J  # noqa: E402


def test_parse_takes_the_last_verdict_line_even_after_thinking_aloud():
    text = 'The article is about Libanius. So NO. NO<tab>Cites Thucydides 6.74 only to emend a reading.'
    assert J.parse(text) == ('NO', 'Cites Thucydides 6.74 only to emend a reading.')
    assert J.parse('PARTLY\tTouches the account.') == ('PARTLY', 'Touches the account.')
    assert J.parse('YES\tDiscusses the siege.')[0] == 'YES'


def test_parse_drops_a_repeated_verdict_inside_the_reason():
    v, reason = J.parse('PARTLY<tab>Uses Thucydides 6 for the Herms affair.PARTLY<tab>Uses Thucydides 6 for the Herms affair.')
    assert v == 'PARTLY' and reason == 'Uses Thucydides 6 for the Herms affair.'


def test_parse_returns_none_when_no_verdict_line_was_reached():
    assert J.parse('Let me think about 6.7. Hmm.')[0] is None
    assert J.parse('')[0] is None


def test_event_and_article_text():
    e = {'label': 'Sicilian Expedition', 'date_start': -415, 'date_end': -413, 'place': 'Syracuse',
         'participants': ['Nicias'], 'description': 'Athenian campaign.', 'summary': None}
    t = J.event_text(e)
    assert 'Dates: 415 BCE to 413 BCE' in t and 'Place: Syracuse' in t and 'Nicias' in t
    art = {'title': 'Zur Kritik', 'authors': ['Sintenis'], 'venue': 'Hermes', 'year': 1866,
           'snippets': [('Thuc. VI 74', 'a textual emendation')]}
    a = J.article_text(art, {'thuc. pele. 6.74'})
    assert 'no abstract held' in a and 'thuc. pele. 6.74' in a and '(Thuc. VI 74) a textual emendation' in a


def test_parse_accepts_a_written_backslash_t():
    import judge_scholarship_relevance as J
    assert J.parse('NO\\tCites the passage for a Greek word.')[0] == 'NO'


def test_default_provider_is_free():
    import judge_scholarship_relevance as J
    assert J.PROVIDER == 'gateway' and J.ANTHROPIC_MODEL.startswith('claude-')


def test_paid_provider_refuses_without_approval(tmp_path):
    import pytest
    import judge_scholarship_relevance as J
    with pytest.raises(SystemExit) as e:
        J.main([str(tmp_path / 'in.sqlite'), str(tmp_path / 'out.sqlite'), '--provider', 'anthropic'])
    assert 'REFUSING' in str(e.value)
