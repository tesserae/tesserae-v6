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


def test_a_list_item_with_an_unsupported_reference_is_removed_whole():
    text = ('The strongest are:\n\n1. **Aen. 1.146 / BC 1.499** - the Syrtis pair.\n'
            '2. **Aen. 1.999 / BC 1.888** - invented.\n\nAen. 1.103 echoes the storm. It is rare.')
    out, dropped = agent_tools.check_citations(text, ['1.146 1.499 1.103'])
    assert '1.999' not in out and '1.146' in out and 'It is rare.' in out
    assert dropped == ['2. **Aen. 1.999 / BC 1.888** - invented.']
    assert '**Aen.\n' not in out


def test_a_running_comparison_is_waited_for_with_progress(monkeypatch):
    pages = iter([None, None, [{'source_ref': 'od. 1.1', 'target_ref': 'aen. 1.1'}]])
    monkeypatch.setattr(agent_tools.searches, 'crosslingual_page', lambda *a, **k: next(pages))
    monkeypatch.setattr(agent_tools, '_pair', lambda a, b: [{'id': 'homer.odyssey.part.1', 'language': 'grc'},
                                                            {'id': 'vergil.aeneid.part.1', 'language': 'la'}])
    monkeypatch.setattr(agent_tools, '_fusion_compact', lambda rows: rows)
    monkeypatch.setattr(agent_tools, 'COMPARE_POLL', 0)
    replies = iter([
        {'content': '', 'tool_calls': [{'id': 'c1', 'function': {'name': 'compare_texts', 'arguments': json.dumps(
            {'text_a': 'Odyssey 1', 'text_b': 'Aeneid 1'})}}]},
        {'content': 'The comparison found od. 1.1 against aen. 1.1.'},
    ])
    seen = {}

    def chat(messages, tools=None):
        seen['messages'] = messages
        return next(replies)
    monkeypatch.setattr(agent_tools, '_chat', chat)
    events = list(agent_tools.answer_stream('compare Homer Odyssey 1 and Aeneid 1', history=[]))
    steps = [p for k, p in events if k == 'step']
    assert len(steps) == 3 and 'still running' in steps[1]
    tool_out = [m for m in seen['messages'] if m['role'] == 'tool'][0]['content']
    assert 'STILL RUNNING' not in tool_out and 'aen. 1.1' in tool_out


def test_a_comparison_running_past_the_wait_tells_the_model_what_to_do():
    ticks = iter(range(0, 1000, 100))
    gen = agent_tools._waiting(lambda: agent_tools.RUNNING + 'A with B.', clock=lambda: next(ticks), sleep=lambda s: None)
    steps = []
    try:
        while True:
            steps.append(next(gen))
    except StopIteration as stop:
        out = stop.value
    assert steps and out.startswith(agent_tools.RUNNING) and 'asking again' in out
