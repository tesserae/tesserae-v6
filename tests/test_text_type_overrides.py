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


import pytest

# Works the name rules or the line-length rule typed wrongly (audit 2026-11-03).
VERSE_WORKS = [
    # caught by a prose name marker: 'fall', 'petrarch', 'gregory', 'galen'
    ('grc', 'quintus_smyrnaeus.fall_of_troy.tess'),
    ('grc', 'quintus_smyrnaeus.fall_of_troy.part.1.tess'),
    ('la', 'petrarch.africa.tess'),
    ('grc', 'gregory_of_nazianzus.christus_patiens.tess'),
    ('la', 'ausonius.commemoratio_professorum_burdigalensium.tess'),
    # a whole poem or book on one line reads as prose by length
    ('la', 'orientius_saint.commonitorium.tess'),
    ('la', 'paulinus_of_pella.eucharisticus.tess'),
    ('la', 'victor_claudius_marius.alethia.tess'),
    ('la', 'sedulius.hymnus_i.tess'),
    ('grc', 'babrius.fabulae_aesopeae.tess'),
    ('grc', 'pseudoscymnus.scymni_chii_ut_fertur_periegesis.tess'),
]
PROSE_WORKS = [
    # short entries read as verse by length
    ('la', 'obsequens.liber_de_prodigiis.tess'),
    ('grc', 'septuaginta.paralipomenon_i_sive_chronicon_i.tess'),
    ('grc', 'novum_testamentum.marcus.tess'),
    ('grc', 'novum_testamentum.ad_romanos.tess'),
    ('grc', 'anonymous.stadiasmus_magni_maris.tess'),
]


@pytest.mark.parametrize('lang,name', VERSE_WORKS)
def test_verse_works_are_poetry(lang, name):
    assert detect_text_type(name, language=lang) == 'poetry'


@pytest.mark.parametrize('lang,name', PROSE_WORKS)
def test_prose_works_are_prose(lang, name):
    assert detect_text_type(name, language=lang) == 'prose'


def test_every_greek_new_testament_book_is_prose():
    import os
    grc = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts', 'grc')
    books = [n for n in os.listdir(grc) if n.startswith('novum_testamentum.') and n.endswith('.tess')]
    assert books
    for name in books:
        assert detect_text_type(name, language='grc') == 'prose', name


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


def test_every_septuagint_book_is_prose():
    # The Septuagint is a prose translation: even Psalms, Job and the verse
    # prophets are prose in Greek, as the Vulgate is in Latin (#1288).
    import os
    grc = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts', 'grc')
    books = [n for n in os.listdir(grc) if n.startswith('septuaginta.') and n.endswith('.tess')]
    assert len(books) == 55
    for name in books:
        assert detect_text_type(name, language='grc') == 'prose', name
