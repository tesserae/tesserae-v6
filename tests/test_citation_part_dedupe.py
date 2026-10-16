"""A citation on a book file names the book once, not twice."""
from backend.utils import build_citation


def test_book_label_matching_the_locus_cites_the_whole_work():
    assert (build_citation('thucydides.peleponnesian_war.part.2.tess', 'thuc. pele. 2.57.1')
            == 'Thucydides, Peloponnesian War 2.57.1')


def test_book_label_not_matching_the_locus_is_kept():
    out = build_citation('thucydides.peleponnesian_war.part.2.tess', 'thuc. pele. 57.1')
    assert 'Book 2' in out


def test_named_part_keeps_its_label():
    out = build_citation('livy.ab_urbe_condita.part.books_21-30.tess', 'liv. 21.1.1')
    assert 'Books 21-30' in out


def test_hebrew_bible_source_titles_use_arabic_numerals():
    import json
    from pathlib import Path
    from backend.utils import get_text_metadata
    rows = json.loads((Path(__file__).parent.parent / 'backend' / 'text_sources.json').read_text(encoding='utf-8'))
    hebrew = [r['work'] for r in rows if r.get('author') == 'Hebrew Bible']
    assert hebrew
    assert not [w for w in hebrew if w.split()[0] in ('I', 'II')]
    for stem, work in [('1_samuel', '1 Samuel'), ('2_kings', '2 Kings'), ('1_chronicles', '1 Chronicles')]:
        assert work in hebrew
        assert get_text_metadata('hebrew_bible.%s.tess' % stem)['work'] == work
