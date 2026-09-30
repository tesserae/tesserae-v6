"""Asked to compare two texts, the assistant runs the comparison when it can
and reads the first page, instead of only handing over a control."""
from backend.assistant import agent, searches


RESULTS = [
    {'source': {'ref': 'stat. theb. 1.473', 'text': 'forsan et haec olim meminisse iuvet'},
     'target': {'ref': 'verg. aen. 1.203', 'text': 'forsan et haec olim meminisse iuvabit'},
     'overall_score': 8.1, 'matched_words': ['meminisse', 'iuvet'], 'features': {}},
    {'source': {'ref': 'stat. theb. 1.359', 'text': 'stagna refusa'},
     'target': {'ref': 'verg. aen. 1.126', 'text': 'stagna refusa'},
     'overall_score': 6.2, 'matched_words': ['stagna', 'refusa'], 'features': {}},
]
SRC = {'id': 'statius.thebaid.part.1.tess', 'display_name': 'Statius, Thebaid, Book 1', 'language': 'la'}
TGT = {'id': 'vergil.aeneid.part.1.tess', 'display_name': 'Vergil, Aeneid, Book 1', 'language': 'la'}


def _drain(gen):
    events = []
    result = None
    try:
        while True:
            events.append(next(gen))
    except StopIteration as stop:
        result = stop.value
    return events, result


def test_fusion_results_returns_a_cached_page_at_once(monkeypatch):
    monkeypatch.setattr(searches, 'fusion_page', lambda s, t, l, n: RESULTS)
    events, page = _drain(agent._fusion_results(SRC['id'], TGT['id'], 'la', 'A', 'B'))
    assert page == RESULTS and events == []


def test_fusion_results_waits_then_gives_up(monkeypatch):
    calls = []
    monkeypatch.setattr(searches, 'fusion_page', lambda s, t, l, n: calls.append(1) or None)
    monkeypatch.setattr(agent, 'FUSION_WAIT_SECONDS', 40)
    monkeypatch.setattr(agent, 'FUSION_POLL_SECONDS', 20)
    import time
    monkeypatch.setattr(time, 'sleep', lambda s: None)
    events, page = _drain(agent._fusion_results(SRC['id'], TGT['id'], 'la', 'A', 'B'))
    assert page is None
    assert events[0][0] == 'step' and 'first run' in events[0][1]
    assert len(calls) == 3


def test_read_results_streams_a_reading_and_hands_over_the_control(monkeypatch):
    monkeypatch.setattr(agent.model, 'stream', lambda *a, **k: iter([
        'The strongest parallel is Thebaid 1.473 against Aeneid 1.203, ',
        'meminisse iuvet against meminisse iuvabit. The rest is epic stock.']))
    monkeypatch.setattr(agent.actions, 'build', lambda facts, q: [{'kind': 'open', 'label': 'Compare'}])
    ran, facts = ['resolved both texts'], []
    events, _ = _drain(agent._read_results(RESULTS, SRC, TGT, 'compare them', facts, ran))
    kinds = [e[0] for e in events]
    assert kinds[0] == 'step' and 'chunk' in kinds and kinds[-1] == 'done'
    done = events[-1][1]
    assert done['searches_run'] == ['resolved both texts', 'fusion_search']
    assert done['read_results'] == {'source': SRC['id'], 'target': TGT['id'], 'n': 2}
    assert done['guardrails']['clean'] is True
    assert done['actions'][0]['label'] == 'Compare'
    assert facts[-1]['search'] == 'fusion_search'


def test_read_results_strips_a_citation_the_page_does_not_hold(monkeypatch):
    monkeypatch.setattr(agent.model, 'stream', lambda *a, **k: iter([
        'Thebaid 1.473 echoes Aeneid 1.203. Compare also Aeneid 6.851, which is not here.']))
    monkeypatch.setattr(agent.actions, 'build', lambda facts, q: [])
    monkeypatch.setattr(agent.actions, 'suggest', lambda q: [])
    events, _ = _drain(agent._read_results(RESULTS, SRC, TGT, '', [], []))
    done = events[-1][1]
    assert done['guardrails']['references_removed']
    assert 'Aeneid 6.851' not in done.get('text', '')
