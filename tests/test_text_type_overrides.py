"""Texts whose type the content rule gets wrong are fixed by an override."""

from backend.utils import detect_text_type

DIOGENIANUS = 'diogenianus_of_heraclea.paroemiae.tess'


def test_diogenianus_proverb_collection_is_prose_not_verse(tmp_path):
    # One short proverb per line: the median line length alone reads as verse.
    p = tmp_path / DIOGENIANUS
    p.write_text(''.join(f'<d. {i}>\tἈγαθὸν ἡ πενία\n' for i in range(1, 30)), encoding='utf-8')
    assert detect_text_type(DIOGENIANUS, filepath=str(p), language='grc') == 'prose'
    assert detect_text_type(DIOGENIANUS) == 'prose'
    # Without the override the same file is typed by its content, as poetry.
    other = tmp_path / 'zzunlisted.proverbs.tess'
    other.write_text(p.read_text(encoding='utf-8'), encoding='utf-8')
    assert detect_text_type(other.name, filepath=str(other), language='grc') == 'poetry'


# Hebrew Bible books set mostly as verse in the critical editions (BHS): the
# poetic books and the verse prophets. Every other book is prose. Without the
# per-book overrides the 'bible' prose marker typed every book as prose.
HEBREW_POETRY_BOOKS = {
    'psalms', 'proverbs', 'job', 'song_of_songs', 'lamentations',
    'isaiah', 'hosea', 'joel', 'amos', 'obadiah', 'micah', 'nahum',
    'habakkuk', 'zephaniah',
}


def test_hebrew_bible_books_are_typed_prose_or_poetry_by_book():
    import os
    he_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts', 'he')
    books = sorted(n for n in os.listdir(he_dir)
                   if n.startswith('hebrew_bible.') and n.endswith('.tess'))
    assert len(books) == 39
    named = {n[len('hebrew_bible.'):-len('.tess')] for n in books}
    assert HEBREW_POETRY_BOOKS <= named
    for name in books:
        book = name[len('hebrew_bible.'):-len('.tess')]
        expected = 'poetry' if book in HEBREW_POETRY_BOOKS else 'prose'
        assert detect_text_type(name, language='he') == expected, name
