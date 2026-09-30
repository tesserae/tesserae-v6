"""Asked what two texts share in content, the assistant runs the Theme
Comparison and reads its pairs."""
from backend.assistant import agent

OUT = {'work_a': {'work': 'vergil.aeneid.part.1', 'author_display': 'Vergil', 'title': 'Aeneid, Book 1'},
       'work_b': {'work': 'lucan.bellum_civile.part.1', 'author_display': 'Lucan', 'title': 'Bellum Civile, Book 1'},
       'n_a': 125, 'n_b': 115,
       'confidence': {'top': 0.9246, 'baseline': 0.8466, 'head_lift': 0.0719, 'level': 'moderate'},
       'pairs': [{'score': 0.925, 'lift': 0.078, 'strong': False,
                  'a': {'id': 'x', 'work': 'vergil.aeneid.part.1', 'ref_start': 'verg. aen. 1.289', 'gist': 'A prophecy foretells peace.'},
                  'b': {'id': 'y', 'work': 'lucan.bellum_civile.part.1', 'ref_start': 'luc. 1.661', 'gist': 'A prophecy foretells chaos.'}}]}
A = {'id': 'vergil.aeneid.part.1.tess', 'display_name': 'Vergil, Aeneid, Book 1', 'matched': 'work'}
B = {'id': 'lucan.bellum_civile.part.1.tess', 'display_name': 'Lucan, Bellum Civile, Book 1', 'matched': 'work'}


def _drain(gen):
    events = []
    try:
        while True:
            events.append(next(gen))
    except StopIteration:
        pass
    return events


def test_intent_words():
    assert agent._theme_pair_intent('What does theme search show about these two books?')
    assert agent._theme_pair_intent('Do the Aeneid and the Thebaid share the same kind of scene?')
    assert not agent._theme_pair_intent('compare Aeneid 1 and Lucan BC 1')


def test_facts_block_carries_refs_and_confidence():
    block, refs = agent._theme_facts_block(OUT)
    assert 'moderate' in block and 'verg. aen. 1.289' in block and 'luc. 1.661' in block
    assert 'verg. aen. 1.289' in refs and 'lucan.bellum_civile.part.1' in refs


def test_reading_streams_and_offers_the_page(monkeypatch):
    monkeypatch.setattr(agent.model, 'stream', lambda *a, **k: iter([
        'Both books open with prophecy: verg. aen. 1.289 against luc. 1.661. ',
        'The reading is moderate.']))
    monkeypatch.setattr(agent.actions, 'build', lambda facts, q: [])
    events = _drain(agent._read_theme_comparison(OUT, A, B, 'what do they share?', [], ['x']))
    assert events[0][0] == 'step' and events[-1][0] == 'done'
    done = events[-1][1]
    assert done['theme_compare']['n_pairs'] == 1
    assert done['actions'][0]['url'] == '/theme-search?compare=vergil.aeneid.part.1&with=lucan.bellum_civile.part.1'
    assert done['guardrails']['clean'] is True


def test_reading_strips_a_pair_the_comparison_did_not_return(monkeypatch):
    monkeypatch.setattr(agent.model, 'stream', lambda *a, **k: iter([
        'verg. aen. 1.289 matches luc. 1.661. See also Aeneid 6.851 for the same idea.']))
    monkeypatch.setattr(agent.actions, 'build', lambda facts, q: [])
    done = _drain(agent._read_theme_comparison(OUT, A, B, '', [], []))[-1][1]
    assert done['guardrails']['references_removed'] and 'Aeneid 6.851' not in done.get('text', '')
