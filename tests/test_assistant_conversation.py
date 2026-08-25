"""Tessa's follow-up handling, tested THROUGH THE HTTP ENDPOINT.

WHY THROUGH THE ENDPOINT

Because testing the other door is what let this ship broken. The conversation
fix was verified by calling agent.answer() directly, which threads history
correctly. The browser uses agent.answer_stream(), which did not thread it at
all. Every test passed and the feature was dead in the page: asked "What about
Eobanus?" right after a question about arma virumque, Tessa answered with a
general description of Eobanus's works and never searched for the phrase.

That is the same shape as the quotation-channel outage found the same day: two
paths, the tested one working and the shipped one not. So these tests go in by
the same door the browser uses.

The searches are real and hit the live index, so this is slower than a unit test
and is a regression suite rather than something to run on every save.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402


@pytest.fixture(scope='module')
def route():
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/ask-stream'))


@pytest.fixture
def client():
    """A client that keeps cookies across requests, as a browser does."""
    return app.test_client()


def ask(client, route, question, history=None):
    body = {'question': question}
    if history is not None:
        body['history'] = history
    resp = client.post(route, json=body)
    assert resp.status_code == 200, f'endpoint returned {resp.status_code}'
    answer, ran = '', []
    for line in resp.get_data(as_text=True).split('\n'):
        if not line.startswith('data: '):
            continue
        try:
            payload = json.loads(line[6:])
        except ValueError:
            continue
        if 'searches_run' in payload:
            ran = payload['searches_run']
        elif payload.get('text'):
            answer += payload['text']
    return answer, ran


def test_followup_carries_the_phrase_from_the_client(client, route):
    """The normal case: the page sends the conversation."""
    q1 = 'Where does the phrase arma virumque appear?'
    a1, ran1 = ask(client, route, q1)
    assert any('line_search' in r for r in ran1), f'turn 1 ran {ran1}'

    history = [{'role': 'user', 'text': q1}, {'role': 'assistant', 'text': a1}]
    _, ran2 = ask(client, route, 'What about Eobanus?', history=history)
    assert any('line_search' in r for r in ran2), (
        f'the follow-up ran {ran2}: it did not carry the phrase and answered '
        f'without searching for it')


def test_followup_works_when_the_client_sends_nothing(client, route):
    """The stale-browser case, carried by the session cookie.

    A browser holding an older bundle sends no history, which looks exactly like
    a first question. The cookie travels regardless of how old the loaded
    JavaScript is, so the thread survives.
    """
    ask(client, route, 'Where does the phrase arma virumque appear?')
    _, ran = ask(client, route, 'What about Eobanus?')
    assert any('line_search' in r for r in ran), (
        f'the follow-up ran {ran}: the server did not remember the previous '
        f'question, so a stale client loses the thread')


def test_never_tells_the_user_to_run_a_search(client, route):
    """The behaviour the whole search loop exists to remove.

    Tessa has the tools. Asked a corpus question she must use them, not name
    them. She replied "use string_search with the exact phrase... run
    fusion_search between your text and Eobanus's work".
    """
    answer, _ = ask(client, route, 'are you sure it is not in Eobanus?',
                    history=[{'role': 'user',
                              'text': 'Where does the phrase arma virumque appear?'}])
    low = answer.lower()
    for tool in ('string_search', 'fusion_search', 'line_search', 'rare_words'):
        assert tool not in low, f'answer names the tool {tool} instead of using it'


def test_exact_search_reports_variant_forms(client, route):
    """An exact search alone is true and useless.

    "arma virumque" is not in Eobanus as written; he has it 21 times inflected.
    Reporting only the exact hits hides the more interesting answer.
    """
    _, ran = ask(client, route, 'Where does the phrase arma virumque appear?')
    assert any('variant' in r for r in ran), (
        f'ran {ran}: no variant pass, so inflected forms went unreported')
