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
from backend.assistant import model  # noqa: E402

# THESE ARE INTEGRATION TESTS and they say so rather than failing obscurely.
#
# Every one of them asks Tessa a real question: the searches hit the live index
# and the answers come from the model server on port 8081. A CI runner has
# neither, so without this the whole module fails for want of a service and the
# failures look like broken conversation handling.
#
# Skipped, not faked. A stub model would make these pass while testing nothing,
# which is the failure mode this file's own docstring is about.
if not model.is_available():
    pytest.skip('assistant model server not reachable; these are integration '
                'tests against a live model and index',
                allow_module_level=True)


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


def test_lists_the_actual_lines_when_asked_for_instances(client, route):
    """The listing request, and the fabrication it once produced.

    Asked "can you give the Eobanus instances?", the assistant returned twelve
    citations that each quoted the Aeneid's opening line as though it were
    Eobanus. The 21 real lines had been retrieved correctly and then discarded by
    a character cap on the fact block before the model saw them, so it
    reconstructed what it expected. Inventing primary text under a citation is
    the worst output this tool can produce.
    """
    ask(client, route, 'Where does the phrase arma virumque appear?')
    answer, _ = ask(client, route, 'Can you give the Eobanus instances?')

    # A real Eobanus line, from the corpus, not from Vergil.
    assert 'trahit arma' in answer or 'arma virosque' in answer or 'in arma viros' in answer, (
        'the answer lists no genuine Eobanus line')
    # The Aeneid incipit is NOT in Eobanus. Quoting it here is the fabrication.
    assert 'Troiae qui primus ab oris' not in answer, (
        "the answer quotes the Aeneid's opening line as though it were Eobanus")


def test_guardrails_clean_on_a_listing_answer(client, route):
    """A guard that fails on a TRUE answer is worse than no guard.

    The citation check collected legitimate references from 'examples' only,
    while the lines arrive under 'lines', so twelve correct citations were all
    reported unsupported and a good answer was marked unclean.
    """
    ask(client, route, 'Where does the phrase arma virumque appear?')
    resp = client.post(route, json={'question': 'Can you give the Eobanus instances?'})
    done = {}
    for line in resp.get_data(as_text=True).split('\n'):
        if line.startswith('data: '):
            try:
                payload = json.loads(line[6:])
            except ValueError:
                continue
            if 'searches_run' in payload:
                done = payload
    g = done.get('guardrails') or {}
    assert g.get('fabricated_quotes') == [], f'fabricated quotes: {g.get("fabricated_quotes")}'
    assert g.get('references_removed') == [], f'citations wrongly rejected: {g.get("references_removed")}'
    assert g.get('clean') is True, f'guardrails: {g}'


def test_a_question_about_the_site_does_not_inherit_the_last_phrase(client, route):
    """NC asked Tessa to describe the site and got a search for arma virumque.

    The carry-over guard tested `_is_about_the_tool`, a bare substring list that
    named connectors and CSV but never the site itself, so "tell me about the
    site's search capabilities" was not recognised as a question about the tool.
    It inherited the phrase from the previous turn and ran a corpus search for
    it, and the reader watched "searching for 'arma virumque'..." appear under a
    question that had nothing to do with the Aeneid.

    Guarding on `_is_about_the_site` instead was the obvious fix and the wrong
    one: it ends in a Help-page relevance fallback loose enough to match almost
    anything, which stopped the genuine follow-ups from carrying their subject
    too. Hence the narrow list, and hence this test on both sides of it.
    """
    q1 = 'Where does the phrase arma virumque appear?'
    a1, ran1 = ask(client, route, q1)
    assert any('line_search' in r for r in ran1), f'turn 1 ran {ran1}'

    history = [{'role': 'user', 'text': q1}, {'role': 'assistant', 'text': a1}]
    for question in ("tell me about the site's search capabilities",
                     'what search types are there?',
                     'what can this site search for?'):
        answer, ran = ask(client, route, question, history=history)
        assert not ran, f'{question!r} ran {ran}; it should search nothing'
        assert 'arma virumque' not in answer.lower(), \
            f'{question!r} answered about the carried phrase: {answer[:160]}'
        assert answer.strip(), f'{question!r} answered nothing at all'


def test_the_narrow_guard_still_lets_a_real_followup_carry_its_subject(client, route):
    """The other side of the same guard.

    A guard that discards context silently is worse than the bug it fixes, so
    the follow-up path is asserted here rather than left to be noticed later.
    """
    q1 = 'Where does the phrase arma virumque appear?'
    a1, _ = ask(client, route, q1)
    history = [{'role': 'user', 'text': q1}, {'role': 'assistant', 'text': a1}]
    _, ran = ask(client, route, 'how about in post-classical authors?',
                 history=history)
    assert any('line_search' in r for r in ran), \
        f'the follow-up stopped searching for the carried phrase; ran {ran}'
