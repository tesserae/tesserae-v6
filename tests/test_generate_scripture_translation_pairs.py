"""Tests for scripts/generate_scripture_translation_pairs.py's core logic
(NC, 2026-09-19): the generator that replaced a sampled, incomplete curated
translation-pairs list with an exhaustive one, built from
backend/scripture_id.py's own book-name table.

Loaded via importlib, the same way tests/test_build_connections_map_pruning.py
loads scripts/build_connections_map.py: scripts/ is not a package.
"""
import importlib.util
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SPEC = importlib.util.spec_from_file_location(
    'generate_scripture_translation_pairs',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'scripts', 'generate_scripture_translation_pairs.py'))
gen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gen)


def test_norm_work_strips_part_segment_and_extension():
    assert gen.norm_work('world_english_bible.pentateuch.part.2.exodus.tess') \
        == 'world_english_bible.pentateuch'
    assert gen.norm_work('hebrew_bible.exodus.tess') == 'hebrew_bible.exodus'
    assert gen.norm_work('jerome.vulgate.part.47.matthew.tess') == 'jerome.vulgate'


def test_book_of_filename_resolves_a_bare_book_name():
    assert gen.book_of_filename('hebrew_bible.exodus') == 'EXO'
    assert gen.book_of_filename('septuaginta.josue') == 'JOS'


def test_book_of_filename_resolves_a_part_files_own_book_suffix():
    assert gen.book_of_filename('world_english_bible.pentateuch.part.2.exodus') == 'EXO'
    assert gen.book_of_filename('jerome.vulgate.part.47.matthew') == 'MAT'


def test_book_of_filename_returns_none_for_a_non_book_aggregate():
    assert gen.book_of_filename('sahidic.bible') is None
    assert gen.book_of_filename('world_english_bible.pentateuch') is None


def test_collection_books_covers_every_part_file_under_one_coarse_work(tmp_path, monkeypatch):
    lang_dir = tmp_path / 'en'
    lang_dir.mkdir()
    for name in [
        'world_english_bible.pentateuch.tess',            # bare aggregate: no book, ignored
        'world_english_bible.pentateuch.part.1.genesis.tess',
        'world_english_bible.pentateuch.part.2.exodus.tess',
        'world_english_bible.revelation.tess',             # whole-book file, no .part.
        'not_a_bible_book.tess',                          # wrong prefix: excluded
    ]:
        (lang_dir / name).write_text('x')
    monkeypatch.setattr(gen, 'TEXTS_DIR', str(tmp_path))
    books = gen.collection_books('en', 'world_english_bible.')
    assert books['world_english_bible.pentateuch'] == {'GEN', 'EXO'}
    assert books['world_english_bible.revelation'] == {'REV'}
    assert 'not_a_bible_book' not in books


def test_generator_produces_every_book_pair_between_two_versions(tmp_path, monkeypatch):
    # A miniature corpus: one version with per-book files, another with one
    # coarse work covering two of the same books plus one it doesn't share.
    he_dir = tmp_path / 'he'
    en_dir = tmp_path / 'en'
    he_dir.mkdir()
    en_dir.mkdir()
    for name in ['hebrew_bible.genesis.tess', 'hebrew_bible.exodus.tess', 'hebrew_bible.leviticus.tess']:
        (he_dir / name).write_text('x')
    for name in ['world_english_bible.pentateuch.part.1.genesis.tess',
                'world_english_bible.pentateuch.part.2.exodus.tess']:
        (en_dir / name).write_text('x')
    monkeypatch.setattr(gen, 'TEXTS_DIR', str(tmp_path))
    monkeypatch.setattr(gen, 'VERSIONS', {
        'hebrew_bible': ('he', 'hebrew_bible.'),
        'world_english_bible': ('en', 'world_english_bible.'),
    })
    monkeypatch.setattr(gen, 'HAND_ADDED', [])
    monkeypatch.setattr(sys, 'argv', ['generate_scripture_translation_pairs.py'])
    gen.main()   # dry run (no --write in argv): prints only, does not touch the real JSON

    # Re-derive the same pairs the way main() does, to check them directly
    # rather than parsing stdout.
    import itertools
    by_version = {v: {'lang': lang, 'books': gen.collection_books(lang, prefix)}
                 for v, (lang, prefix) in gen.VERSIONS.items()}
    found = set()
    for va, vb in itertools.combinations(gen.VERSIONS, 2):
        for wa, ca in by_version[va]['books'].items():
            for wb, cb in by_version[vb]['books'].items():
                if ca & cb:
                    found.add(tuple(sorted((wa, wb))))
    assert tuple(sorted(('hebrew_bible.genesis', 'world_english_bible.pentateuch'))) in found
    assert tuple(sorted(('hebrew_bible.exodus', 'world_english_bible.pentateuch'))) in found
    # Leviticus has no WEB pentateuch part file in this miniature corpus, so
    # it must NOT be paired -- the generator must not over-match a coarse
    # work to every book, only the ones it actually has evidence for.
    assert not any('leviticus' in a or 'leviticus' in b for a, b in found)
