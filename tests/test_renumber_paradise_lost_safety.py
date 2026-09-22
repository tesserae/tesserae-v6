"""The Paradise Lost renumbering script must not write unless asked.

Until 2026-09-22 it rewrote thirteen corpus files in place by DEFAULT, and
took no backup. `--dry-run` was the opt-out. Anyone who ran it to see what it
would do rewrote the corpus and had nothing to go back to. The convention
every other script under scripts/corpus/ follows is the opposite: a dry run
by default, `--apply` to write, a dated backup, and a rename rather than a
write in place.

These tests read the source rather than running it, because running it needs
the 10,565-line text and its twelve part files. What they pin is the shape:
the flag, the backup, and the atomic swap.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'scripts', 'corpus', 'renumber_paradise_lost.py')


def source():
    with open(SCRIPT, encoding='utf-8') as fh:
        return fh.read()


class TestWritingIsOptIn:
    def test_apply_is_what_authorises_a_write(self):
        assert "'--apply' in sys.argv" in source()

    def test_a_dry_run_is_the_default(self):
        """No flag at all must mean no write."""
        src = source()
        assert re.search(r'if not APPLY:', src), 'the guard must be on APPLY'
        assert 'dry run: nothing written' in src

    def test_dry_run_still_means_a_dry_run(self):
        """A command copied from the old docstring must still be safe."""
        assert "'--dry-run' not in sys.argv" in source()


class TestItCannotLoseTheOldFile:
    def test_every_file_is_backed_up_before_it_is_replaced(self):
        src = source()
        assert 'from scripts.corpus.corpus_safety import atomic_write, backup' in src
        # Both writers back up first.
        assert src.count('backup(path, BACKUP_TAG)') == 2

    def test_nothing_is_written_in_place(self):
        """A half-written .tess must never be visible to the running site."""
        src = source()
        assert "open(path, 'w'" not in src
        assert src.count('atomic_write(path,') == 2

    def test_the_line_total_guards_are_kept(self):
        """The hardcoded counts are the reason it refuses a file it does not
        recognise, so converting the flags must not have dropped them."""
        src = source()
        assert 'TOTAL_LINES = 10565' in src
        assert 'stopping, not touching anything' in src


class TestTheSurveyAgrees:
    def test_corpus_safety_no_longer_lists_it_as_backwards(self):
        helper = os.path.join(os.path.dirname(SCRIPT), 'corpus_safety.py')
        with open(helper, encoding='utf-8') as fh:
            table = fh.read()
        row = table[table.index('renumber_paradise_lost.py'):][:400]
        assert 'BACKWARDS' not in row
        assert 'CONVERTED' in row
