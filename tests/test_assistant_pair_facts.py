"""Each listed pair in the facts block carries the engine's own figures on
how common its shared words are and in how many works the pairing recurs."""
from backend.assistant import findings


def test_pair_note_marks_rare_words_and_unique_pairing():
    row = {'matched_words': [{'lemma': 'infero', 'frequency': 5, 'idf': 8.3},
                             {'lemma': 'latium', 'frequency': 4, 'idf': 8.5}],
           'formula_count': 1}
    note = findings.pair_evidence_note(row)
    assert 'infero (rare, 5 occurrences in the corpus)' in note
    assert 'latium (rare, 4 occurrences in the corpus)' in note
    assert 'occurs in no other work' in note


def test_pair_note_marks_common_words_and_recurring_pairing():
    row = {'matched_words': [{'lemma': 'moenia', 'frequency': 350}], 'formula_count': 7}
    note = findings.pair_evidence_note(row)
    assert 'moenia (common, 350 occurrences in the corpus)' in note
    assert 'recurs in 7 works' in note and 'a common pairing' in note


def test_block_carries_the_note():
    facts = {'n_results': 1, 'verdict': 'verbatim', 'verdict_note': 'x'}
    passages = [{'source': {'ref': 'verg. aen. 1.6', 'text': 'inferretque deos Latio'},
                 'target': {'ref': 'sil. 1.42', 'text': 'Intulerit Latio'},
                 'matched_words': [{'lemma': 'latium', 'frequency': 4}], 'formula_count': 1}]
    block = findings.format_for_narration(facts, passages=passages)
    assert 'shared words: latium (rare, 4 occurrences in the corpus); this pairing of words occurs in no other work' in block
