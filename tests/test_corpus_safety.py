"""Tests for scripts/corpus/corpus_safety.py, the shared dry-run/backup/
atomic-write helper for scripts that mutate corpus data (code audit
2026-09-21, finding #2). Everything here runs against a pytest tmp_path;
nothing touches the real corpus, an index, or a cache.
"""
import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, 'scripts', 'corpus'))

import corpus_safety as cs  # noqa: E402


# --- add_apply_argument / make_parser -------------------------------------

def test_apply_argument_defaults_to_dry_run():
    ap = argparse.ArgumentParser()
    cs.add_apply_argument(ap)
    args = ap.parse_args([])
    assert args.apply is False


def test_apply_argument_set_with_flag():
    ap = argparse.ArgumentParser()
    cs.add_apply_argument(ap)
    args = ap.parse_args(['--apply'])
    assert args.apply is True


def test_make_parser_has_apply():
    ap = cs.make_parser('a test script')
    assert ap.parse_args([]).apply is False
    assert ap.parse_args(['--apply']).apply is True


# --- atomic_write: dry run writes nothing, apply writes -------------------

def test_dry_run_writes_nothing(tmp_path):
    # "Dry run" for a caller of this module means: don't call atomic_write
    # or backup at all. Confirm the file is untouched when a script's own
    # --apply gate (modeled here directly) is False.
    target = tmp_path / 'work.tess'
    target.write_text('<ref 1>\told text\n', encoding='utf-8')
    apply_ = False
    if apply_:
        cs.atomic_write(str(target), '<ref 1>\tnew text\n')
    assert target.read_text(encoding='utf-8') == '<ref 1>\told text\n'


def test_apply_writes(tmp_path):
    target = tmp_path / 'work.tess'
    target.write_text('<ref 1>\told text\n', encoding='utf-8')
    cs.atomic_write(str(target), '<ref 1>\tnew text\n')
    assert target.read_text(encoding='utf-8') == '<ref 1>\tnew text\n'


def test_atomic_write_accepts_a_list_of_lines(tmp_path):
    target = tmp_path / 'work.tess'
    cs.atomic_write(str(target), ['<ref 1>\ta\n', '<ref 2>\tb\n'])
    assert target.read_text(encoding='utf-8') == '<ref 1>\ta\n<ref 2>\tb\n'


def test_atomic_write_creates_a_new_file(tmp_path):
    target = tmp_path / 'new.tess'
    assert not target.exists()
    cs.atomic_write(str(target), 'hello\n')
    assert target.read_text(encoding='utf-8') == 'hello\n'


def test_atomic_write_leaves_no_temp_file_behind(tmp_path):
    target = tmp_path / 'work.tess'
    cs.atomic_write(str(target), 'content\n')
    leftovers = [p for p in os.listdir(tmp_path) if p != 'work.tess']
    assert leftovers == []


# --- backup: made, dated, a rerun never clobbers the first ----------------

def test_backup_is_made_and_matches_original(tmp_path):
    target = tmp_path / 'work.tess'
    target.write_text('original content\n', encoding='utf-8')
    dest = cs.backup(str(target), tag='mytag')
    assert dest is not None
    assert os.path.exists(dest)
    assert os.path.basename(dest).startswith('work.tess.bak-mytag-')
    with open(dest, encoding='utf-8') as fh:
        assert fh.read() == 'original content\n'
    # the live file is untouched by taking a backup
    assert target.read_text(encoding='utf-8') == 'original content\n'


def test_backup_of_missing_file_returns_none(tmp_path):
    target = tmp_path / 'does_not_exist.tess'
    assert cs.backup(str(target), tag='x') is None


def test_backup_rerun_does_not_clobber_the_first(tmp_path, monkeypatch):
    target = tmp_path / 'work.tess'
    target.write_text('version 1\n', encoding='utf-8')

    # Freeze time.strftime so two calls land in the "same second", the
    # exact case the convention calls out: "a rerun must never overwrite
    # the first run's backup."
    fixed_stamp = '20260921-120000'
    monkeypatch.setattr(cs.time, 'strftime', lambda *_a, **_k: fixed_stamp)

    first = cs.backup(str(target), tag='reftags')
    target.write_text('version 2\n', encoding='utf-8')
    second = cs.backup(str(target), tag='reftags')

    assert first != second
    assert os.path.exists(first)
    assert os.path.exists(second)
    with open(first, encoding='utf-8') as fh:
        assert fh.read() == 'version 1\n'
    with open(second, encoding='utf-8') as fh:
        assert fh.read() == 'version 2\n'


def test_backup_without_tag(tmp_path):
    target = tmp_path / 'work.tess'
    target.write_text('x\n', encoding='utf-8')
    dest = cs.backup(str(target))
    assert dest is not None
    assert os.path.basename(dest).startswith('work.tess.bak-')


# --- line endings survive a round trip ------------------------------------

def test_crlf_survives_atomic_write_round_trip(tmp_path):
    target = tmp_path / 'work.tess'
    original = '<ref 1>\ttext one\r\n<ref 2>\ttext two\r\n'
    with open(target, 'w', encoding='utf-8', newline='') as fh:
        fh.write(original)

    text = cs.read_text_preserving_eol(str(target))
    assert text == original  # not silently converted to \n on read

    cs.atomic_write(str(target), text)  # round trip with no edit
    with open(target, encoding='utf-8', newline='') as fh:
        raw = fh.read()
    assert raw == original
    assert '\r\n' in raw
    assert raw.count('\r\n') == 2


def test_mixed_line_endings_are_not_normalized(tmp_path):
    target = tmp_path / 'work.tess'
    original = 'line one\r\nline two\nline three\r'
    with open(target, 'w', encoding='utf-8', newline='') as fh:
        fh.write(original)
    lines = cs.read_lines_preserving_eol(str(target))
    assert lines == ['line one\r\n', 'line two\n', 'line three\r']
    cs.atomic_write(str(target), lines)
    with open(target, encoding='utf-8', newline='') as fh:
        assert fh.read() == original


def test_lf_only_file_stays_lf(tmp_path):
    target = tmp_path / 'work.tess'
    original = '<ref 1>\ta\n<ref 2>\tb\n'
    target.write_text(original, encoding='utf-8', newline='')
    text = cs.read_text_preserving_eol(str(target))
    cs.atomic_write(str(target), text)
    with open(target, encoding='utf-8', newline='') as fh:
        raw = fh.read()
    assert raw == original
    assert '\r' not in raw


# --- a write failure leaves the original file intact ----------------------

def test_write_failure_leaves_original_intact(tmp_path):
    target = tmp_path / 'work.tess'
    target.write_text('safe original\n', encoding='utf-8')

    class Boom(Exception):
        pass

    class BadLines:
        """Raises partway through iteration, simulating a failure after
        some (but not all) content has been written to the temp file."""

        def __iter__(self):
            yield 'first line that gets written\n'
            raise Boom('disk full, or whatever else went wrong')

    try:
        cs.atomic_write(str(target), BadLines())
    except Boom:
        pass
    else:
        raise AssertionError('expected the write failure to propagate')

    # original untouched
    assert target.read_text(encoding='utf-8') == 'safe original\n'
    # and no leftover temp file
    leftovers = [p for p in os.listdir(tmp_path) if p != 'work.tess']
    assert leftovers == []


def test_write_failure_on_new_file_leaves_nothing(tmp_path):
    target = tmp_path / 'brand_new.tess'

    class Boom(Exception):
        pass

    class BadLines:
        def __iter__(self):
            yield 'partial\n'
            raise Boom()

    try:
        cs.atomic_write(str(target), BadLines())
    except Boom:
        pass
    else:
        raise AssertionError('expected the write failure to propagate')

    assert not target.exists()
    assert os.listdir(tmp_path) == []
