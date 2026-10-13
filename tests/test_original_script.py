"""The paragraph keeps quoted Greek in Greek letters: the checker and the retry."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend.assistant import model  # noqa: E402
from backend import original_script as osx  # noqa: E402
from backend import scholarship_theme  # noqa: E402
from backend import scholarship_recent  # noqa: E402
import pytest  # noqa: E402

# How and Wells on Herodotus 1.32.5
NOTE = ('ἄπηρος κτλ.: for some of these conditions (ὧν οὐκ ἄνευ) necessary to happiness cf. '
        'Arist. Eth. i. 8. 16; τὸ εὖ ζῆν combined for a Greek the two ideas of ‘good life’ '
        'and ‘good living’ (i. e. prosperity).')


@pytest.mark.parametrize('text', [
    'How and Wells say *euzen* joins two ideas.',
    'How and Wells say euzen joins two ideas.',
    'How and Wells say eu zēn joins two ideas.',
    'How and Wells say to eu zēn joins two ideas.',
])
def test_catches_transliteration_and_asterisks(text):
    assert osx.problems(text, [NOTE])


def test_does_not_flag_plain_english():
    text = 'How and Wells link happiness to Aristotle and to prosperity [1].'
    assert osx.problems(text, [NOTE]) == []


def test_clean_greek_passes():
    assert osx.problems('How and Wells take τὸ εὖ ζῆν (the good life) [1].', [NOTE]) == []


def test_problem_names_the_greek():
    msgs = osx.problems('They gloss euzen.', [NOTE])
    assert msgs and 'euzen' in msgs[0] and 'εὖ ζῆν' in msgs[0]


def test_fix_strips_asterisks():
    assert osx.fix('a *b* c **d**') == 'a b c d'


def test_settle_retries_once_then_accepts_good_answer():
    asked = []

    def ask(note):
        asked.append(note)
        return 'They gloss τὸ εὖ ζῆν (the good life) [1].'
    text, left = osx.settle('They gloss *euzen* [1].', [NOTE], ask)
    assert len(asked) == 1 and 'euzen' in asked[0] and 'εὖ ζῆν' in asked[0]
    assert left == [] and '*' not in text and 'εὖ ζῆν' in text


def test_settle_second_bad_answer_is_stripped_and_reported():
    text, left = osx.settle('They gloss *euzen* [1].', [NOTE], lambda note: 'They gloss *euzen* again [1].')
    assert '*' not in text and left


def test_settle_clean_answer_asks_nothing():
    def boom(note):
        raise AssertionError('should not ask')
    assert osx.settle('Plain answer [1].', [NOTE], boom) == ('Plain answer [1].', [])


# ---- through the route ----------------------------------------------------

@pytest.fixture
def scholarship(monkeypatch):
    monkeypatch.setattr(scholarship_recent, 'recent_safe',
                        lambda q, w, s: {'service': s, 'available': True, 'results': [], 'reason': ''})
    card = {'kind': 'commentary', 'work': 'herodotus.histories', 'commentator': 'How and Wells',
            'ref_start': 'hdt. 1.32.5', 'snippet': NOTE, 'link': {'kind': 'reader', 'url': '/read?x'},
            'title': None, 'year': None}
    monkeypatch.setattr(scholarship_theme, 'theme', lambda q, k=0, d=None: {'results': [card]})
    monkeypatch.setattr(model, 'is_available', lambda: True)


def _post(body):
    r = app.test_client().post('/api/passages/ask-scholarship', json=body)
    assert r.status_code == 200
    return json.loads(r.get_data())


BODY = {'question': 'What is happiness?', 'work': 'herodotus.histories'}


def test_route_retries_after_a_bad_answer(monkeypatch, scholarship):
    answers = ['How and Wells gloss *euzen* [1].', 'How and Wells gloss τὸ εὖ ζῆν (the good life) [1].']
    seen = []

    def fake(system, user, max_tokens=0, temperature=0):
        seen.append(user)
        return answers[len(seen) - 1]
    monkeypatch.setattr(model, 'complete', fake)
    out = _post(BODY)
    assert len(seen) == 2 and 'You wrote' in seen[1] and 'You wrote' not in seen[0]
    assert out['summary'] == answers[1] and out['script_problems'] == []


def test_route_twice_bad_strips_asterisks_and_reports(monkeypatch, scholarship):
    monkeypatch.setattr(model, 'complete', lambda *a, **k: 'How and Wells gloss *euzen* [1].')
    out = _post(BODY)
    assert '*' not in out['summary'] and out['script_problems']


def test_route_clean_answer_asks_once(monkeypatch, scholarship):
    calls = []

    def fake(system, user, max_tokens=0, temperature=0):
        calls.append(system)
        return 'How and Wells gloss τὸ εὖ ζῆν [1].'
    monkeypatch.setattr(model, 'complete', fake)
    out = _post(BODY)
    assert len(calls) == 1 and out['script_problems'] == []
    assert 'Never transliterate' in calls[0]


def test_summary_route_rule_and_field(monkeypatch):
    monkeypatch.setattr(model, 'is_available', lambda: True)
    seen = []

    def fake(system, user, max_tokens=0, temperature=0):
        seen.append(system)
        return 'The work speaks of happiness (hdt. 1.32.5).'
    monkeypatch.setattr(model, 'complete', fake)
    r = app.test_client().post('/api/passages/ask-summary', json={
        'question': 'happiness', 'work_label': 'Herodotus',
        'passages': [{'ref': 'hdt. 1.32.5', 'gist': 'Solon speaks of τὸ εὖ ζῆν.'}]})
    out = json.loads(r.get_data())
    assert out['script_problems'] == [] and 'Never transliterate' in seen[0]
