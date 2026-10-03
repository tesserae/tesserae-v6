"""Each listed pair in the facts block carries corpus-wide figures on how
common its shared words are (texts containing the lemma) and in how many
works the pairing recurs."""
from backend.assistant import findings


def _fake_index(monkeypatch):
    monkeypatch.setattr(findings, '_corpus_doc_freq',
                        lambda language: ({'altus': 505, 'latium': 75, 'infero': 394, 'saturnius': 9}, 1655))


def test_bands_come_from_corpus_document_frequency(monkeypatch):
    _fake_index(monkeypatch)
    row = {'matched_words': [{'lemma': 'infero', 'frequency': 5}, {'lemma': 'latium', 'frequency': 4},
                             {'lemma': 'saturnius', 'frequency': 3}], 'formula_count': 1}
    note = findings.pair_evidence_note(row, 'la')
    assert 'infero (common: in 394 of 1655 Latin texts)' in note
    assert 'latium (uncommon: in 75 of 1655 Latin texts)' in note
    assert 'saturnius (rare: in 9 of 1655 Latin texts)' in note
    assert 'occurs in no other work' in note


def test_recurring_pairing(monkeypatch):
    _fake_index(monkeypatch)
    note = findings.pair_evidence_note({'matched_words': [{'lemma': 'altus'}], 'formula_count': 7}, 'la')
    assert 'altus (common' in note and 'recurs in 7 works' in note and 'a common pairing' in note


def test_without_a_language_only_the_lemmas_are_named():
    note = findings.pair_evidence_note({'matched_words': [{'lemma': 'altus', 'frequency': 23}], 'formula_count': 2})
    assert note.startswith('shared words: altus;') and 'occurrences' not in note


def test_block_carries_the_note(monkeypatch):
    _fake_index(monkeypatch)
    facts = {'n_results': 1, 'verdict': 'verbatim', 'verdict_note': 'x'}
    passages = [{'source': {'ref': 'verg. aen. 1.6', 'text': 'inferretque deos Latio'},
                 'target': {'ref': 'sil. 1.42', 'text': 'Intulerit Latio'},
                 'matched_words': [{'lemma': 'latium'}], 'formula_count': 1}]
    block = findings.format_for_narration(facts, passages=passages, language='la')
    assert 'latium (uncommon: in 75 of 1655 Latin texts); this pairing of words occurs in no other work' in block
