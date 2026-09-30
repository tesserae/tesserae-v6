"""When a guide question names an author the corpus holds, the model is handed
that author's works and blurbs, so it names real titles."""
from backend.blueprints import assistant as bp


def test_author_holdings_lists_real_works_with_blurbs(monkeypatch):
    from backend.assistant import corpus_lookup
    from backend.blueprints import corpus
    monkeypatch.setattr(corpus_lookup, 'named_texts', lambda q, language=None, limit=2: [
        {'id': 'dracontius.romulea.tess', 'author': 'Dracontius', 'matched': 'author'}])
    monkeypatch.setattr(corpus_lookup, '_all_texts', lambda language=None: [
        {'id': 'dracontius.romulea.tess', 'author': 'Dracontius', 'title': 'Romulea', 'language': 'la'},
        {'id': 'dracontius.romulea.part.1.tess', 'author': 'Dracontius', 'title': 'Romulea', 'language': 'la'},
        {'id': 'dracontius.orestes.tess', 'author': 'Dracontius', 'title': 'Orestes', 'language': 'la'},
        {'id': 'vergil.aeneid.tess', 'author': 'Vergil', 'title': 'Aeneid', 'language': 'la'}])
    monkeypatch.setattr(corpus, 'load_descriptions', lambda: {'la': {'dracontius.orestes': 'A tragedy in hexameters.'}})
    block = bp._author_holdings('Who was Dracontius?')
    assert 'WHAT THIS SITE HOLDS BY DRACONTIUS' in block
    assert block.count('- Romulea') == 1          # book files collapse to the work
    assert '- Orestes: A tragedy in hexameters.' in block
    assert 'Aeneid' not in block


def test_no_named_author_means_no_block(monkeypatch):
    from backend.assistant import corpus_lookup
    monkeypatch.setattr(corpus_lookup, 'named_texts', lambda q, language=None, limit=2: [])
    assert bp._author_holdings('What does the score mean?') == ''
