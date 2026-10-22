"""The experimental Tessa: the model chooses the searches (backend/assistant/agent_tools.py)."""
import json

from backend.assistant import agent_tools


def test_a_sentence_citing_a_reference_no_search_returned_is_dropped():
    text = 'Pallas dies at 10.487. Evander mourns at 11.151. Turnus boasts at 10.999.'
    out, dropped = agent_tools.check_citations(text, ['... 10.487 ... 11.151 ...'])
    assert '10.999' not in out and '11.151' in out and len(dropped) == 1


def test_the_model_calls_a_search_then_answers(monkeypatch):
    replies = iter([
        {'content': '', 'tool_calls': [{'id': 'c1', 'function': {'name': 'people_places', 'arguments': json.dumps({'name': 'Sarpedon'})}}]},
        {'content': 'Sarpedon is named in 169 lines.'},
    ])
    monkeypatch.setattr(agent_tools, '_chat', lambda messages, tools=None: next(replies))
    monkeypatch.setattr(agent_tools.searches, 'run', lambda name, args: {'total_lines': 169, 'name': args['name']})
    events = list(agent_tools.answer_stream('Where is Sarpedon mentioned?', history=[]))
    kinds = [k for k, _ in events]
    assert kinds == ['step', 'chunk', 'done']
    assert events[1][1] == 'Sarpedon is named in 169 lines.'
    assert events[2][1]['searches_run'] == ['people_places']


def test_history_reaches_the_model(monkeypatch):
    seen = {}

    def chat(messages, tools=None):
        seen['messages'] = messages
        return {'content': 'ok'}
    monkeypatch.setattr(agent_tools, '_chat', chat)
    list(agent_tools.answer_stream('analysis of those results?', history=[
        {'role': 'user', 'text': 'compare Aeneid 1 to Lucan 1'}, {'role': 'assistant', 'text': 'Here is the link.'}]))
    roles = [m['role'] for m in seen['messages']]
    assert roles == ['system', 'user', 'assistant', 'user']
