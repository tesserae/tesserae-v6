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



def _row(id_, author, title, part=False):
    key = author.lower().replace(' ', '_')
    return {'id': id_, 'language': 'la', 'author': author, 'author_key': key, 'title': title,
            'work_key': title.lower().replace(' ', '_'), 'is_part': part}


ROWS = [
    _row('vergil.aeneid.tess', 'Vergil', 'Aeneid'),
    _row('vergil.aeneid.part.1.tess', 'Vergil', 'Aeneid', True),
    _row('vergil.aeneid.part.6.tess', 'Vergil', 'Aeneid', True),
    _row('silius_italicus.punica.tess', 'Silius Italicus', 'Punica'),
    _row('silius_italicus.punica.part.1.tess', 'Silius Italicus', 'Punica', True),
    _row('silius_italicus.punica.part.3.tess', 'Silius Italicus', 'Punica', True),
    _row('statius.thebaid.tess', 'Statius', 'Thebaid'),
    _row('statius.thebaid.part.12.tess', 'Statius', 'Thebaid', True),
    _row('statius.silvae.tess', 'Statius', 'Silvae'),
    _row('lucan.bellum_civile.tess', 'Lucan', 'Bellum Civile'),
    _row('ovid.metamorphoses.tess', 'Ovid', 'Metamorphoses'),
]


def test_author_name_then_title_with_book_number_narrows_to_the_book(monkeypatch):
    """"compare Aeneid 1 and Silius Italicus Punica 1" (3 Oct 2026): the
    author's name resolved first to the whole Punica, and the two-text limit
    stopped the scan before "Punica 1" could narrow it. Tessa then ran Aeneid 1
    against all seventeen books and outlasted her wait."""
    monkeypatch.setattr(corpus_lookup, '_all_texts', lambda language=None: ROWS)
    ids = lambda q: [h['id'] for h in corpus_lookup.named_texts(q, 'la')]
    assert ids('compare Aeneid 1 and Silius Italicus Punica 1') == ['vergil.aeneid.part.1.tess', 'silius_italicus.punica.part.1.tess']
    # The number on the first text instead.
    assert ids('Silius Italicus Punica 3 against Lucan') == ['silius_italicus.punica.part.3.tess', 'lucan.bellum_civile.tess']
    # More than two names: the first two in order of mention still win.
    assert ids('compare Vergil Aeneid 1 and Ovid Metamorphoses and Lucan') == ['vergil.aeneid.part.1.tess', 'ovid.metamorphoses.tess']
    # Unchanged: an author alone stays whole, a repeated name is not a second text.
    assert ids('echoes of Vergil in Statius') == ['vergil.aeneid.tess', 'statius.silvae.tess']
    assert len(ids('what about Statius Thebaid?')) == 1
