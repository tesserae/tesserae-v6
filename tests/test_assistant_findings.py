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
