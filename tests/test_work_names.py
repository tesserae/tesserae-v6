"""One rule for collapsing a multi-part work to its base name.

Fourteen places worked this out for themselves, in three different ways, and
one of the three was wrong. These tests pin the rule, the distinction
between naming a file and naming a work, and the case that the wrong variant
missed.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.work_names import base_work, is_part, sql_base_work, work_id  # noqa: E402


class TestNamingAFile:
    @pytest.mark.parametrize('given,expected', [
        ('la/vergil.aeneid.part.1.tess', 'vergil.aeneid.part.1'),
        ('vergil.aeneid.part.1.tess', 'vergil.aeneid.part.1'),
        ('vergil.aeneid.part.1', 'vergil.aeneid.part.1'),
        ('shenoute.a22.tess', 'shenoute.a22'),
        ('', ''),
        (None, ''),
    ])
    def test_strips_the_directory_and_the_suffix_but_keeps_the_part(self, given, expected):
        assert work_id(given) == expected


class TestNamingAWork:
    @pytest.mark.parametrize('given,expected', [
        ('la/vergil.aeneid.part.1.tess', 'vergil.aeneid'),
        ('vergil.aeneid.tess', 'vergil.aeneid'),
        ('shenoute.a22.tess', 'shenoute.a22'),
    ])
    def test_collapses_the_part(self, given, expected):
        assert base_work(given) == expected

    @pytest.mark.parametrize('given,expected', [
        ('pindar.odes.part.2.nemeans.tess', 'pindar.odes'),
        ('nonnus_of_panopolis.dionysiaca.part.1.books_1-10.tess', 'nonnus_of_panopolis.dionysiaca'),
        ('jerome.vulgate.part.12.1_chronicles.tess', 'jerome.vulgate'),
        ('world_english_bible.pentateuch.part.1.genesis.tess', 'world_english_bible.pentateuch'),
    ])
    def test_collapses_a_part_that_carries_a_label(self, given, expected):
        """The case the old regex missed.

        `re.sub(r'\\.part\\.\\d+$', '', name)` needs the number to end the
        name. On 2026-09-21 the corpus held 215 files across 16 works with a
        label after the number, and for every one of them that variant
        returned the name unchanged, so the work was not recognised as
        itself: its description, its translation and its counts were looked
        up under a name nothing holds.
        """
        assert base_work(given) == expected

    def test_the_old_regex_really_did_miss_them(self):
        import re
        old = lambda n: re.sub(r'\.part\.\d+$', '', n.replace('.tess', ''))  # noqa: E731
        name = 'pindar.odes.part.2.nemeans.tess'
        assert old(name) == 'pindar.odes.part.2.nemeans'
        assert base_work(name) == 'pindar.odes'
        assert old(name) != base_work(name)


class TestTellingThemApart:
    def test_is_part(self):
        assert is_part('vergil.aeneid.part.3.tess')
        assert is_part('pindar.odes.part.2.nemeans.tess')
        assert not is_part('vergil.aeneid.tess')
        assert not is_part('shenoute.a22')

    def test_a_translation_keeps_its_part_but_falls_back_to_the_work(self):
        """The distinction that made a single rule impossible: a part has its
        own aligned translation, so naming the file must not collapse it."""
        assert work_id('vergil.aeneid.part.6.tess') == 'vergil.aeneid.part.6'
        assert base_work('vergil.aeneid.part.6.tess') == 'vergil.aeneid'


class TestTheSqlSaysTheSameThing:
    def test_matches_the_python_on_real_names(self):
        import sqlite3
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE t (filename TEXT)')
        names = ['vergil.aeneid.tess', 'vergil.aeneid.part.1.tess',
                 'pindar.odes.part.2.nemeans.tess', 'shenoute.a22.tess',
                 'jerome.vulgate.part.12.1_chronicles.tess']
        db.executemany('INSERT INTO t VALUES (?)', [(n,) for n in names])
        rows = db.execute(f'SELECT filename, {sql_base_work("filename")} FROM t').fetchall()
        for name, collapsed in rows:
            assert collapsed == base_work(name) + '.tess', name


class TestEveryCallerAgrees:
    def test_the_passage_index_uses_the_shared_rule(self):
        from backend import passage_index
        assert passage_index._norm_work('la/pindar.odes.part.2.nemeans.tess') == 'pindar.odes'

    def test_translations_keeps_the_part(self):
        from backend import translations
        assert translations._norm_work('la/vergil.aeneid.part.6.tess') == 'vergil.aeneid.part.6'

    def test_no_inline_copy_is_left_in_the_backend(self):
        """A new inline copy is the way this drifts back apart."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent / 'backend'
        offenders = []
        for path in root.rglob('*.py'):
            if path.name == 'work_names.py':
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
            if ".split('.part.')" in text or '.split(".part.")' in text:
                offenders.append(str(path.relative_to(root)))
        assert offenders == [], offenders
