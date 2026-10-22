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
    assert steps and out.startswith(agent_tools.RUNNING) and 'ask again' in out


def test_a_quotation_no_search_returned_is_caught_and_a_real_one_passes():
    out = ['{"lines": ["verg. aen. 1.154: sic cunctus pelagi cecidit fragor, aequora postquam"]}']
    text = ('It reads "Aeneas, cum iam fluctus et caelum aequora laesae". The line "sic cunctus pelagi cecidit '
            'fragor" ends the storm, as in *De rerum natura* and "the sea and the sky".')
    assert agent_tools.unverified_quotes(text, out) == ['Aeneas, cum iam fluctus et caelum aequora laesae']


def test_an_answer_citing_what_no_search_returned_is_sent_back_once(monkeypatch):
    replies = iter([
        {'content': 'Cato speaks at 1.237, in the Senate.'},
        {'content': '', 'tool_calls': [{'id': 'c1', 'function': {'name': 'read_passage', 'arguments': json.dumps(
            {'work': 'Lucan 1', 'ref': '1.237'})}}]},
        {'content': 'The narrator speaks at 1.237.'},
    ])
    seen = []

    def chat(messages, tools=None):
        seen.append([m['content'] for m in messages])
        return next(replies)
    monkeypatch.setattr(agent_tools, '_chat', chat)
    monkeypatch.setitem(agent_tools.TOOLS, 'read_passage',
                        (lambda a: '{"lines": ["luc. 1.237: signa fore"]}',) + agent_tools.TOOLS['read_passage'][1:])
    events = list(agent_tools.answer_stream('who is speaking there?', history=[
        {'role': 'user', 'text': 'compare Lucan 1 and Aeneid 2'}, {'role': 'assistant', 'text': 'Top: Aen. 2.313.'}]))
    assert 'Note from the site' in seen[1][-1] and 'Cato' not in seen[1][-1]
    assert events[-2] == ('chunk', 'The narrator speaks at 1.237.')


def test_an_answer_left_empty_by_the_checks_falls_back(monkeypatch):
    monkeypatch.setattr(agent_tools, '_chat', lambda messages, tools=None: {'content': 'It is at 9.999.'})
    try:
        list(agent_tools.answer_stream('where?', history=[]))
    except agent_tools.GaveUp:
        return
    raise AssertionError('expected GaveUp')


def test_misspelled_names_are_corrected_from_the_listing(monkeypatch):
    monkeypatch.setattr(agent_tools, '_VOCAB', {})
    monkeypatch.setattr(agent_tools.corpus_lookup, '_all_texts', lambda language=None: [
        {'author': 'Vergil', 'work': 'Aeneid', 'title': 'Aeneid', 'display_name': 'Vergil, Aeneid'},
        {'author': 'Servius', 'title': 'In Virgilii Georgicon libros commentarius'}])
    assert agent_tools._corrected('Vergils Aenied book 6') == 'Vergil Aeneid book 6'
    assert agent_tools._corrected('Virgil Aeneid 6') == 'Vergil Aeneid 6'


def test_one_work_prefers_a_title_match_with_its_book(monkeypatch):
    rows = {'claudian.de_raptu_proserpinae': {'id': 'claudian.de_raptu_proserpinae.tess', 'matched': 'work'}}
    monkeypatch.setattr(agent_tools, '_corrected', lambda name: name)
    monkeypatch.setattr(agent_tools.corpus_lookup, 'find_texts',
                        lambda name, limit=1: [rows['claudian.de_raptu_proserpinae']] if 'raptu' in name else [])
    monkeypatch.setattr(agent_tools.corpus_lookup, 'book_of',
                        lambda hit, num: {'id': f"claudian.de_raptu_proserpinae.part.{num}.tess"})
    assert agent_tools._one('Claudian De raptu Proserpinae 2')['id'] == 'claudian.de_raptu_proserpinae.part.2.tess'
    assert agent_tools._one('Claudian De raptu Proserpinae')['id'] == 'claudian.de_raptu_proserpinae.tess'


def test_tidy_removes_talk_about_the_check_and_renumbers():
    text = "You're right to check, and the re-run confirms it. Top:\n\n3. **a**\n4. **b**\n6. **c**"
    assert agent_tools._tidy(text) == 'Top:\n\n1. **a**\n2. **b**\n3. **c**'
    assert agent_tools._tidy('Cato is not the speaker.') == 'Cato is not the speaker.'
def test_list_texts_with_no_language_gives_counts_for_every_language(monkeypatch):
    from backend.assistant import agent as ordinary
    monkeypatch.setattr(ordinary, '_language_holdings_fact',
                        lambda code: {'language': code.upper(), 'works': 10, 'authors': 2})
    out = json.loads(agent_tools.t_list_texts({}))
    assert out['total_works'] == 10 * len(agent_tools.LANGUAGES)
    assert out['literary_works_by_language']['LA'] == {'works': 10, 'authors': 2}


def test_after_a_send_back_a_correction_of_the_unseen_draft_is_removed(monkeypatch):
    replies = iter([{'content': 'Lucan wrote it, at 1.1.'},
                    {'content': 'I need to correct my earlier answer: it was not Lucan. Statius wrote the Thebaid.'}])
    monkeypatch.setattr(agent_tools, '_chat', lambda messages, tools=None: next(replies))
    events = list(agent_tools.answer_stream('Who wrote the Thebaid?', history=[]))
    assert events[-2] == ('chunk', 'Statius wrote the Thebaid.')


def test_names_no_result_gives_are_caught():
    ctx = ['{"summary": "A mother laments her dead son Euryalus"}', 'Narrow it to Vergil']
    text = "In 9.481 the mother, Caillina, laments over Euryalus. Latin poets differ. Camilla's spear flies."
    assert agent_tools.unsupported_names(text, ctx) == ['Caillina', 'Camilla'] or \
        agent_tools.unsupported_names(text, ctx) == ['Caillina']


def test_several_comparisons_share_one_wait():
    ticks = iter(range(0, 10000, 100))
    clock = lambda: next(ticks)  # noqa: E731
    budget = {'left': 250}
    first = agent_tools._waiting(lambda: agent_tools.RUNNING + 'A with B.', clock=clock, sleep=lambda s: None, budget=budget)
    try:
        while True:
            next(first)
    except StopIteration:
        pass
    assert budget['left'] == 0
    second = agent_tools._waiting(lambda: agent_tools.RUNNING + 'C with D.', clock=clock, sleep=lambda s: None, budget=budget)
    assert list(second) == []
