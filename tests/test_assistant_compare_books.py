"""Tessa scopes "book 1 of each" to the two books, and says when a comparison
is still running (2 Oct 2026: whole Aeneid against whole Punica outlasted her
wait and she answered with a stock sentence)."""
from backend.assistant import corpus_lookup, agent


def test_shared_book_number():
    assert corpus_lookup.shared_book_number("compare book 1 of each Vergil's Aeneid and Silius' Punica") == 1
    assert corpus_lookup.shared_book_number('book 6 of both the Aeneid and the Thebaid') == 6
    assert corpus_lookup.shared_book_number('compare book 2 of the Aeneid with the Punica') == 2
    assert corpus_lookup.shared_book_number('compare the Aeneid and the Punica') is None
    assert corpus_lookup.shared_book_number('Thebaid 12 and Aeneid 6') is None


def test_book_of_finds_the_part_file(monkeypatch):
    rows = [{'id': 'vergil.aeneid.tess', 'language': 'la'},
            {'id': 'vergil.aeneid.part.1.tess', 'language': 'la'},
            {'id': 'vergil.aeneid.part.2.tess', 'language': 'la'}]
    monkeypatch.setattr(corpus_lookup, '_all_texts', lambda language=None: rows)
    book = corpus_lookup.book_of(rows[0], 1)
    assert book and book['id'] == 'vergil.aeneid.part.1.tess'
    assert corpus_lookup.book_of(rows[0], 9) is None


def test_still_running_sentence():
    facts = [{'kind': 'THE COMPARISON IS STILL RUNNING on the server. Say so.', 'source': 'Vergil, Aeneid',
              'target': 'Silius Italicus, Punica', 'still_running': True}]
    s = agent._handoff_sentence(facts)
    assert 'still running' in s and 'Vergil, Aeneid' in s and 'Open it below' in s
