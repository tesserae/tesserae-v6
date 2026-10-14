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


def _tables(monkeypatch):
    tables = {'la': ({'altus': 505, 'latium': 75, 'saturnius': 9}, 1655),
              'grc': ({'logos': 900}, 1000), 'en': ({'king': 300}, 500)}
    monkeypatch.setattr(findings, '_corpus_doc_freq', lambda language: tables.get(language, ({}, 0)))


def _row(*lemmas, fc=None):
    row = {'matched_words': [{'lemma': lem} for lem in lemmas]}
    if fc is not None:
        row['formula_count'] = fc
    return row


def test_language_is_inferred_from_the_shared_lemmas(monkeypatch):
    _tables(monkeypatch)
    assert findings.infer_language([_row('altus', 'latium'), _row('saturnius')]) == 'la'
    assert findings.infer_language([_row('logos')]) == 'grc'
    assert findings.infer_language([_row('unknownword')]) is None
    assert findings.infer_language([]) is None


def test_inferred_language_labels_a_rare_word_rare_and_a_common_one_common(monkeypatch):
    _tables(monkeypatch)
    rows = [_row('altus', fc=7), _row('saturnius', fc=1), _row('altus', 'saturnius')]
    lang = findings.infer_language(rows)
    block = findings.format_for_narration({'n_results': 3, 'verdict': 'weak', 'verdict_note': 'x'},
                                          passages=rows, language=lang)
    assert 'altus (common: in 505 of 1655 Latin texts); this pairing of words recurs in 7 works' in block
    assert 'saturnius (rare: in 9 of 1655 Latin texts); this pairing of words occurs in no other work' in block
    # a row with no recurrence figure shows none
    assert block.count('recurs in') == 1 and block.count('occurs in no other work') == 1


def test_ask_tessa_route_sends_the_labels_though_the_page_names_no_language(monkeypatch):
    """The results page posts rows and two display names, no language code."""
    import json
    from backend.app import app
    from backend.assistant import model
    _tables(monkeypatch)
    seen = {}
    monkeypatch.setattr(model, 'is_available', lambda: True)
    monkeypatch.setattr(model, 'complete', lambda system, user, **k: seen.setdefault('user', user) and 'ok')
    rows = [dict(_row('altus', fc=7), source={'ref': 'a 1', 'text': 'x'}, target={'ref': 'b 2', 'text': 'y'})]
    r = app.test_client().post('/api/assistant/analyze', json={'results': rows, 'source': 'A', 'target': 'B'})
    assert r.status_code == 200 and json.loads(r.get_data())
    assert 'altus (common: in 505 of 1655 Latin texts); this pairing of words recurs in 7 works' in seen['user']
