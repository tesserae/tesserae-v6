"""Refreshing the wording a passage window quotes, without re-describing it.

When a corpus file is corrected, the passage index keeps the old wording and
the site quotes it. Rebuilding the index properly means sending every window
through a language model again; this updates the stored words only, which is
right when the correction did not change what the passage says. On
2026-09-22 that was 353 windows of 5,980, and the differences were curly
quotation marks, elision marks and editorial brackets.
"""
import os
import sqlite3
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'scripts', 'corpus', 'refresh_window_text.py')


@pytest.fixture
def world(tmp_path):
    """A corpus file, and an index holding its previous wording."""
    texts = tmp_path / 'texts' / 'la'
    texts.mkdir(parents=True)
    (texts / 'ovid.met.tess').write_text(
        '<ov. met. 1.1>\tIn nova fert animus "mutatas" dicere formas\n'
        '<ov. met. 1.2>\tcorpora; di, coeptis nam vos mutastis et illas\n'
        '<ov. met. 1.3>\tadspirate meis primaque ab origine mundi\n', encoding='utf-8')
    index = tmp_path / 'data' / 'passage_index'
    index.mkdir(parents=True)
    db = sqlite3.connect(index / 'window_texts.db')
    db.execute('CREATE TABLE window_texts (id TEXT, language TEXT, work TEXT, '
               'ref_start TEXT, ref_end TEXT, text TEXT)')
    db.execute('CREATE TABLE lines (work TEXT, ord INTEGER, ref TEXT, text TEXT)')
    # the stored copy has the old curly quotation marks
    old_first = 'In nova fert animus “mutatas” dicere formas'
    db.execute('INSERT INTO window_texts VALUES (?,?,?,?,?,?)',
               ('ovid.met:fine:0', 'la', 'ovid.met', 'ov. met. 1.1', 'ov. met. 1.2',
                old_first + '\ncorpora; di, coeptis nam vos mutastis et illas'))
    for i, (ref, text) in enumerate([
            ('ov. met. 1.1', old_first),
            ('ov. met. 1.2', 'corpora; di, coeptis nam vos mutastis et illas'),
            ('ov. met. 1.3', 'adspirate meis primaque ab origine mundi')]):
        db.execute('INSERT INTO lines VALUES (?,?,?,?)', ('ovid.met', i, ref, text))
    db.commit()
    db.close()
    return tmp_path


def run(root, *args):
    return subprocess.run([sys.executable, SCRIPT, '--root', str(root),
                           '--works', 'la/ovid.met', *args],
                          capture_output=True, text=True, check=True).stdout


def stored(root):
    db = sqlite3.connect(root / 'data' / 'passage_index' / 'window_texts.db')
    win = db.execute('SELECT text FROM window_texts').fetchone()[0]
    line = db.execute("SELECT text FROM lines WHERE ref='ov. met. 1.1'").fetchone()[0]
    db.close()
    return win, line


def test_a_dry_run_changes_nothing(world):
    before = stored(world)
    out = run(world)
    assert 'DRY RUN' in out
    assert '1 window(s)' in out
    assert stored(world) == before


def test_apply_updates_the_window_and_its_lines(world):
    run(world, '--apply')
    win, line = stored(world)
    assert '"mutatas"' in line
    assert '“mutatas”' not in line
    assert '"mutatas"' in win
    assert 'corpora; di, coeptis' in win, 'the rest of the window must survive'


def test_it_keeps_a_backup_before_writing(world):
    run(world, '--apply')
    backups = list((world / 'data' / 'passage_index').glob('window_texts.db.bak-textrefresh-*'))
    assert len(backups) == 1


def test_running_twice_changes_nothing_the_second_time(world):
    run(world, '--apply')
    out = run(world)
    assert '0 window(s)' in out


def test_a_missing_file_is_skipped_not_fatal(world):
    out = subprocess.run([sys.executable, SCRIPT, '--root', str(world),
                          '--works', 'la/nobody.nothing'],
                         capture_output=True, text=True, check=True).stdout
    assert 'no such file' in out
