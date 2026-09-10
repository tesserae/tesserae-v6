"""The facts block handed to the results assistant.

Three things went wrong on production (NC, 2026-09-10, Vergil Aeneid 1 against
Lucan 1): the prose said "EVIDENCE VERDICT confirms this as VERBATIM", copying
a label from the facts; it reported "all 25 of the top-ranked parallels landing
in Lucan", which in a two-text comparison cannot be otherwise; and it asked for
"historical context for Lucan's access to Vergil's text". The first two are
fixed in the facts block, the third in the prompt. These tests pin the block.
"""
from backend.assistant import findings, model, prompts


def _pair(src, tgt, channels, words=None):
    return {
        'source': {'ref': src, 'text': 'et vastas aperit syrtis'},
        'target': {'ref': tgt, 'text': 'Repulit a Libycis immensum Syrtibus aequor'},
        'channels': channels,
        'matched_words': [{'idf_score': w} for w in (words or [])],
    }


TWO_TEXT = [
    _pair('verg. aen. 1.146', 'luc. 1.499', ['quotation', 'lemma', 'semantic'], [6.1, 7.2]),
    _pair('verg. aen. 1.200', 'luc. 1.510', ['lemma', 'semantic', 'dictionary'], [4.0]),
    _pair('verg. aen. 1.300', 'luc. 1.600', ['lemma', 'lemma_min1', 'edit_distance']),
]


def test_verdict_is_plain_words_not_a_capitalised_code():
    facts = findings.summarize_results(TWO_TEXT, 'vergil.aeneid.part.1', 'lucan.bellum_civile.part.1')
    block = findings.format_for_narration(facts, passages=TWO_TEXT)
    assert 'VERDICT' not in block
    assert 'VERBATIM' not in block
    assert 'verbatim reuse' in block


def test_block_uses_plain_channel_words_and_no_passage_numbers():
    facts = findings.summarize_results(TWO_TEXT, 'vergil.aeneid.part.1', 'lucan.bellum_civile.part.1')
    block = findings.format_for_narration(facts, passages=TWO_TEXT)
    assert 'edit_distance' not in block and 'lemma_min1' not in block
    assert 'spelling' in block and 'shared words' in block
    assert '[1]' not in block
    assert '- verg. aen. 1.146:' in block
    assert 'passage [1]' in prompts.ANALYZE_SYSTEM


def test_two_text_comparison_reports_no_concentration():
    facts = findings.summarize_results(TWO_TEXT, 'vergil.aeneid.part.1', 'lucan.bellum_civile.part.1')
    assert facts['target_concentration'] == []
    assert facts['source_concentration'] == []
    block = findings.format_for_narration(facts, passages=TWO_TEXT)
    assert 'Where the matches land' not in block


def test_corpus_search_still_reports_where_matches_land():
    spread = TWO_TEXT + [_pair('verg. aen. 1.400', 'stat. theb. 2.1', ['lemma', 'semantic'])]
    facts = findings.summarize_results(spread, 'vergil.aeneid.part.1', None)
    works = dict(facts['target_concentration'])
    assert works == {'luc': 3, 'stat': 1}


def test_comparison_line_names_which_text_is_earlier():
    facts = findings.summarize_results(TWO_TEXT, 'vergil.aeneid.part.1', 'lucan.bellum_civile.part.1')
    block = findings.format_for_narration(facts, passages=TWO_TEXT)
    assert 'the earlier text' in block and 'the later text' in block


def test_prompt_no_longer_names_the_verdict_label():
    assert 'EVIDENCE VERDICT' not in prompts.ANALYZE_SYSTEM
    assert 'historical context' in prompts.ANALYZE_SYSTEM


# The prompt asks the model not to raise the access question. The guard is what
# makes sure of it: these two sentences are the ones production wrote.
def test_guard_removes_the_access_hedge():
    text = ('The match is strong. This case would be strengthened by a clear causal '
            'link or historical context for Lucan’s access to Vergil’s text, but '
            'weakened if the phrase were common. As it stands, the evidence supports reuse.')
    cleaned, removed = model.strip_access_talk(text)
    assert cleaned == 'The match is strong. As it stands, the evidence supports reuse.'
    assert len(removed) == 1


def test_guard_removes_whether_the_later_author_knew():
    text = ('The evidence does not settle the question of whether Lucan knew the '
            'Aeneid, but it does not support borrowing. The shared words are common.')
    cleaned, removed = model.strip_access_talk(text)
    assert cleaned == 'The shared words are common.'
    assert len(removed) == 1


def test_full_work_name_citations_are_allowed():
    from backend.blueprints.assistant import _allowed_refs
    allowed = _allowed_refs(TWO_TEXT, 'vergil.aeneid.part.1.tess', 'lucan.bellum_civile.part.1.tess')
    text = ('The run appears in Vergil’s Aeneid 1.146 and Lucan’s Bellum Civile 1.499. '
            'Nothing links it to Thebaid 6.98.')
    cleaned, removed = model.strip_unsupported_references(text, allowed)
    assert 'Bellum Civile 1.499' in cleaned
    assert 'Aeneid 1.146' in cleaned
    assert removed == ['Thebaid 6.98']


# Both analyze routes used to raise NameError on `question` after the model had
# answered, so the non-streamed route returned 500 and the streamed one ended
# in an error event. The model is stubbed; the point is that the routes finish.
def _client(monkeypatch):
    from backend.app import app
    from backend.assistant import model as m
    monkeypatch.setattr(m, 'is_available', lambda: True)
    monkeypatch.setattr(m, 'complete', lambda *a, **k: 'The evidence supports verbatim reuse.')
    monkeypatch.setattr(m, 'stream', lambda *a, **k: iter(['The evidence ', 'supports verbatim reuse.']))
    app.testing = True
    return app, app.test_client()


def _path(app, endpoint):
    for rule in app.url_map.iter_rules():
        if rule.endpoint == endpoint:
            return rule.rule
    raise AssertionError(endpoint)


def test_analyze_route_finishes_with_and_without_a_question(monkeypatch):
    app, c = _client(monkeypatch)
    url = _path(app, 'assistant.analyze')
    for extra in ({}, {'question': 'Is Thebaid 6 relevant?'}):
        r = c.post(url, json={'results': TWO_TEXT, 'source': 'vergil.aeneid.part.1.tess',
                              'target': 'lucan.bellum_civile.part.1.tess', **extra})
        assert r.status_code == 200, r.get_data(as_text=True)[:200]
        body = r.get_json()
        assert body['model_used'] is True
        assert body['guardrails']['clean'] is True


def test_analyze_stream_route_ends_with_done(monkeypatch):
    import json as _json
    app, c = _client(monkeypatch)
    url = _path(app, 'assistant.analyze_stream')
    r = c.post(url, json={'results': TWO_TEXT, 'source': 'vergil.aeneid.part.1.tess',
                          'target': 'lucan.bellum_civile.part.1.tess', 'question': 'And so?'})
    assert r.status_code == 200
    events = [_json.loads(line[6:]) for line in r.get_data(as_text=True).splitlines()
              if line.startswith('data: ')]
    assert events[-1]['type'] == 'done', events[-1]
    assert events[-1]['guardrails']['clean'] is True


def test_truncated_answer_is_cut_back_to_a_full_sentence():
    text = 'The run is verbatim. The other parallels are thematic. The case for direct'
    assert model.trim_to_sentence(text) == 'The run is verbatim. The other parallels are thematic.'
    assert model.trim_to_sentence('Complete already.') == 'Complete already.'
    assert model.trim_to_sentence('No sentence end at all') == 'No sentence end at all'


def test_reference_guard_removes_a_range_citation_whole():
    # Production left "that passage–107" on the page: the guard matched
    # "Aeneid 1.1" and not the "–107" that followed it.
    from backend.blueprints.assistant import _allowed_refs
    allowed = _allowed_refs(TWO_TEXT, 'vergil.aeneid.part.1.tess', 'lucan.bellum_civile.part.1.tess')
    text = 'The construction in Aeneid 1.1–107 and Lucan 1.1–645 matches.'
    cleaned, removed = model.strip_unsupported_references(text, allowed)
    assert '–107' not in cleaned and '–645' not in cleaned
    assert cleaned == 'The construction in that passage and that passage matches.'
    assert len(removed) == 2


def test_reference_guard_keeps_a_valid_range_citation():
    from backend.blueprints.assistant import _allowed_refs
    allowed = _allowed_refs(TWO_TEXT, 'vergil.aeneid.part.1.tess', 'lucan.bellum_civile.part.1.tess')
    text = 'The storm at Aeneid 1.146–150 is echoed at Lucan 1.499.'
    cleaned, removed = model.strip_unsupported_references(text, allowed)
    assert cleaned == text and removed == []


def test_number_guard_accepts_the_parts_of_a_locus():
    block = '- verg. aen. 1.107: "..."\n  luc. 1.645: "..."'
    ok, invented = model.numbers_preserved(block, 'Line 107 of Aeneid 1 answers line 645 of Lucan 1.')
    assert ok and invented == []
    ok, invented = model.numbers_preserved(block, 'All 300 parallels agree.')
    assert not ok and invented == ['300']


def test_guard_leaves_ordinary_prose_alone():
    text = 'The shared phrase Syrtibus aequor is rare. The evidence supports direct reuse.'
    cleaned, removed = model.strip_access_talk(text)
    assert cleaned == text and removed == []


def test_guard_keeps_historical_context_when_it_is_not_a_hedge():
    text = ('The historical context is the civil war. The phrase recurs in Aen. 1.146 '
            'and Luc. 1.499. Both poets use it of the Syrtes.')
    cleaned, removed = model.strip_access_talk(text)
    assert cleaned == text and removed == []


def test_guard_does_not_split_on_abbreviations():
    text = ('The run appears at Aen. 1.146. This would be strengthened by historical '
            'context for the borrowing. The phrase is rare.')
    cleaned, removed = model.strip_access_talk(text)
    assert cleaned == 'The run appears at Aen. 1.146. The phrase is rare.'
    assert len(removed) == 1
