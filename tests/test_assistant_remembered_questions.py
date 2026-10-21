"""The questions remembered in the session fill the conversation only for a page that sends none.

2026-10-21: the panel sent an empty conversation, the cookie supplied the day
before's "compare Lucretius book 1 with Ovid Met book 1", and "how does the theme
search work?" was answered with a theme comparison of the two.
"""


from backend.app import app  # noqa: E402
from backend.blueprints import assistant as bp  # noqa: E402


def _capture(monkeypatch):
    seen = []

    def fake(question, history=None, offered_phrase=None):
        seen.append(list(history or []))
        yield 'done', {'searches_run': []}

    monkeypatch.setattr(bp.agent, 'answer_stream', fake)
    return seen


def _ask(client, body):
    r = client.post('/api/assistant/ask-stream', json=body)
    r.get_data()
    return r


def test_an_empty_conversation_from_the_page_stays_empty(monkeypatch):
    seen = _capture(monkeypatch)
    client = app.test_client()
    with client.session_transaction() as s:
        s['tessa_qs'] = ['compare Lucretius book 1 with Ovid Met book 1']
    _ask(client, {'question': 'how does the theme search work?', 'history': []})
    assert seen == [[]]


def test_a_page_that_sends_no_conversation_gets_the_remembered_questions(monkeypatch):
    seen = _capture(monkeypatch)
    client = app.test_client()
    with client.session_transaction() as s:
        s['tessa_qs'] = ['compare Lucretius book 1 with Ovid Met book 1']
    _ask(client, {'question': 'and in book 2?'})
    assert seen and seen[0] == [{'role': 'user', 'text': 'compare Lucretius book 1 with Ovid Met book 1'}]
