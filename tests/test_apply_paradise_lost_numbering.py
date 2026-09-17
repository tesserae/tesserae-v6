"""Fixture test for scripts/corpus/apply_paradise_lost_numbering.py.

The real passage index (data/passage_index/) is multi-gigabyte, not in git,
and not available in this checkout, so this builds a tiny synthetic
stand-in (window_texts.db tables, descriptions.jsonl, a cache/*.json fusion
result) and runs the script against it with --apply. This is the acceptance
check for the script: nothing here ever touches a real passage index.

Two paths are exercised, both using the script's own real per-book
constants (BOOK_LINE_COUNTS, OLD_SEGMENTS) rather than invented ones, since
those are hardcoded in the script for the real twelve books:

  - the primary, lines-table-based path, on milton.paradise_lost.part.1
    (book 1 really does have a duplicated old tag at "1.5": one row at old
    position 4, tagged "1.5" by the pre-fix bug, and the true "1.5" at
    position 5). A sparse `lines` table is given rows at a few positions,
    including both sides of that duplicate, and one window_texts row
    spans it (ref_start "1.5", ref_end "1.6"), to check the documented
    earliest-occurrence rule.
  - the OLD_SEGMENTS fallback, on milton.paradise_lost.part.7 (book 7's
    real segments are the simple single-duplicate case), by giving that
    work window_texts and descriptions rows but NO `lines` table rows at
    all, forcing resolve_ref() to fall back.

A third work, milton.paradise_lost.part.4, exercises the deleted
whitespace-only row (real, original position 393): one lines-table row
sits exactly on it (must be dropped, not remapped), one window's ref_start
touches it (moves forward to the next real line), one window's ref_end
touches it (moves back to the previous real line), and one window is
nothing but that row on both ends (a degenerate case the script warns
about but does not repair).
"""
import json
import os
import sqlite3
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, 'scripts', 'corpus', 'apply_paradise_lost_numbering.py')

PART1 = 'milton.paradise_lost.part.1'
PART4 = 'milton.paradise_lost.part.4'
PART7 = 'milton.paradise_lost.part.7'
WHOLE = 'milton.paradise_lost'


def build_fixture(root):
    os.makedirs(os.path.join(root, 'data', 'passage_index'), exist_ok=True)
    os.makedirs(os.path.join(root, 'cache'), exist_ok=True)

    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    c = sqlite3.connect(wdb)
    c.execute('CREATE TABLE window_texts (id TEXT, language TEXT, work TEXT, '
              'ref_start TEXT, ref_end TEXT, text TEXT)')
    c.execute('CREATE TABLE lines (work TEXT, ord INTEGER, ref TEXT, text TEXT)')

    # part.1: sparse lines table, including both sides of the real book-1
    # duplicate at old tag "1.5" (position 4, the erroneous pre-fix tag, and
    # position 5, the correct one).
    line_rows = [
        (PART1, 0, 'Milton P.L. 1.2', 'OF Mans First Disobedience'),
        (PART1, 3, 'Milton P.L. 1.5', 'With loss of Eden'),          # position 4 (old, wrong)
        (PART1, 4, 'Milton P.L. 1.5', 'Restore us, and regain'),      # position 5 (old, correct)
        (PART1, 5, 'Milton P.L. 1.6', "Sing Heav'nly Muse"),
        (PART1, 797, 'Milton P.L. 1.798', 'the great consult began'),
    ]
    c.executemany('INSERT INTO lines VALUES (?,?,?,?)', line_rows)

    # part.4: sparse lines table around the real deleted position (393),
    # including the blank row itself.
    line_rows_4 = [
        (PART4, 389, 'Milton P.L. 4.390', 'text390'),
        (PART4, 390, 'Milton P.L. 4.391', 'text391'),
        (PART4, 391, 'Milton P.L. 4.392', 'text392'),
        (PART4, 392, 'Milton P.L. 4.393', ' '),          # position 393: the deleted blank row
        (PART4, 393, 'Milton P.L. 4.394', 'text394'),
        (PART4, 395, 'Milton P.L. 4.396', 'text396'),
    ]
    c.executemany('INSERT INTO lines VALUES (?,?,?,?)', line_rows_4)

    window_rows = [
        # simple window, no ambiguity
        ('w1', 'en', PART1, 'Milton P.L. 1.2', 'Milton P.L. 1.2', 'w1 simple'),
        # spans the duplicate: ref_start hits the ambiguous "1.5"
        ('w2', 'en', PART1, 'Milton P.L. 1.5', 'Milton P.L. 1.6', 'w2 spans dup'),
        # part.7 rows: no lines table coverage at all, forces the
        # OLD_SEGMENTS fallback (book 7's real segments: (1,4,1),(5,640,0))
        ('w3', 'en', PART7, 'Milton P.L. 7.2', 'Milton P.L. 7.2', 'w3 fallback simple'),
        ('w4', 'en', PART7, 'Milton P.L. 7.4', 'Milton P.L. 7.6', 'w4 fallback straddles head/tail'),
        # unrelated work, must pass through untouched
        ('w5', 'la', 'vergil.aeneid', 'verg. aen. 1.1', 'verg. aen. 1.5', 'arma virumque cano'),
        # part.4: ref_start touches the deleted row, moves forward
        ('w6', 'en', PART4, 'Milton P.L. 4.393', 'Milton P.L. 4.396', 'w6 start touches deleted row'),
        # part.4: ref_end touches the deleted row, moves back
        ('w7', 'en', PART4, 'Milton P.L. 4.391', 'Milton P.L. 4.393', 'w7 end touches deleted row'),
        # part.4: window is nothing but the deleted row on both ends
        ('w8', 'en', PART4, 'Milton P.L. 4.393', 'Milton P.L. 4.393', 'w8 degenerate: only the deleted row'),
    ]
    c.executemany('INSERT INTO window_texts VALUES (?,?,?,?,?,?)', window_rows)
    c.commit(); c.close()

    desc_rows = [
        {'id': 'w1', 'work': PART1, 'scale': 'fine',
         'ref_start': 'Milton P.L. 1.2', 'ref_end': 'Milton P.L. 1.2', 'desc': {'gist': 'd1'}},
        {'id': 'w2', 'work': PART1, 'scale': 'fine',
         'ref_start': 'Milton P.L. 1.5', 'ref_end': 'Milton P.L. 1.6', 'desc': {'gist': 'd2'}},
        {'id': 'w3', 'work': PART7, 'scale': 'fine',
         'ref_start': 'Milton P.L. 7.2', 'ref_end': 'Milton P.L. 7.2', 'desc': {'gist': 'd3'}},
        {'id': 'w5', 'work': 'vergil.aeneid', 'scale': 'fine',
         'ref_start': 'verg. aen. 1.1', 'ref_end': 'verg. aen. 1.5', 'desc': {'gist': 'unrelated'}},
        {'id': 'w6', 'work': PART4, 'scale': 'fine',
         'ref_start': 'Milton P.L. 4.393', 'ref_end': 'Milton P.L. 4.396', 'desc': {'gist': 'd6'}},
    ]
    dpath = os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl')
    with open(dpath, 'w', encoding='utf-8') as f:
        for r in desc_rows:
            f.write(json.dumps(r) + '\n')

    with open(os.path.join(root, 'cache', 'hit.json'), 'w', encoding='utf-8') as f:
        json.dump({'source': PART1, 'target': 'someone.else'}, f)
    with open(os.path.join(root, 'cache', 'miss.json'), 'w', encoding='utf-8') as f:
        json.dump({'source': 'foo', 'target': 'bar'}, f)


def run_script(root, extra_args=()):
    return subprocess.run(
        [sys.executable, SCRIPT, *extra_args], cwd=root,
        capture_output=True, text=True, check=True)


def test_dry_run_writes_nothing(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    before = open(wdb, 'rb').read()
    proc = run_script(root)
    assert 'DRY RUN' in proc.stdout
    after = open(wdb, 'rb').read()
    assert before == after
    assert os.path.exists(os.path.join(root, 'cache', 'hit.json'))


def test_apply_remaps_lines_table(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    run_script(root, ['--apply'])
    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    conn = sqlite3.connect(wdb)
    rows = dict(
        (ord_, ref) for ord_, ref in
        conn.execute('select ord, ref from lines where work=?', (PART1,)))
    conn.close()
    assert rows[0] == 'Milton P.L. 1.1'
    assert rows[3] == 'Milton P.L. 1.4'   # old-wrong duplicate row -> true position 4
    assert rows[4] == 'Milton P.L. 1.5'   # old-correct duplicate row -> true position 5
    assert rows[5] == 'Milton P.L. 1.6'   # already correct, unchanged
    assert rows[797] == 'Milton P.L. 1.798'  # already correct, unchanged


def test_apply_resolves_duplicate_to_earliest_position(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    run_script(root, ['--apply'])
    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    conn = sqlite3.connect(wdb)
    w1 = conn.execute('select ref_start, ref_end from window_texts where id=?', ('w1',)).fetchone()
    w2 = conn.execute('select ref_start, ref_end from window_texts where id=?', ('w2',)).fetchone()
    w5 = conn.execute('select ref_start, ref_end from window_texts where id=?', ('w5',)).fetchone()
    conn.close()
    assert w1 == ('Milton P.L. 1.1', 'Milton P.L. 1.1')
    # w2 spans the duplicate old tag "1.5": ref_start resolves to the
    # EARLIEST ord carrying that ref (position 4, the old-wrong row), so the
    # window's start moves to 1.4, not 1.5.
    assert w2 == ('Milton P.L. 1.4', 'Milton P.L. 1.6')
    assert w5 == ('verg. aen. 1.1', 'verg. aen. 1.5')  # unrelated work untouched


def test_apply_fallback_path_no_lines_table_coverage(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    run_script(root, ['--apply'])
    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    conn = sqlite3.connect(wdb)
    w3 = conn.execute('select ref_start, ref_end from window_texts where id=?', ('w3',)).fetchone()
    w4 = conn.execute('select ref_start, ref_end from window_texts where id=?', ('w4',)).fetchone()
    conn.close()
    # book 7's real OLD_SEGMENTS: (1,4,1) then (5,640,0); old "7.2" is
    # position 1 (offset 1) -> new "7.1"; old "7.4" is position 3 (offset 1)
    # -> new "7.3"; old "7.6" is position 6 (offset 0, past the head) -> new
    # "7.6" unchanged.
    assert w3 == ('Milton P.L. 7.1', 'Milton P.L. 7.1')
    assert w4 == ('Milton P.L. 7.3', 'Milton P.L. 7.6')


def test_apply_deletes_the_blank_row_from_lines_table(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    run_script(root, ['--apply'])
    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    conn = sqlite3.connect(wdb)
    rows = dict(
        (ord_, ref) for ord_, ref in
        conn.execute('select ord, ref from lines where work=?', (PART4,)))
    conn.close()
    assert 392 not in rows, 'the whitespace-only row (position 393) should be dropped, not remapped'
    assert rows[389] == 'Milton P.L. 4.390'   # position 390, before the deletion: unaffected
    assert rows[390] == 'Milton P.L. 4.391'   # position 391, before the deletion: unaffected
    assert rows[391] == 'Milton P.L. 4.392'   # position 392, before the deletion: unaffected
    assert rows[393] == 'Milton P.L. 4.393'   # position 394, after the deletion: shifts down by one
    assert rows[395] == 'Milton P.L. 4.395'   # position 396, after the deletion: shifts down by one


def test_apply_window_touching_deleted_row_moves_to_next_or_previous_line(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    run_script(root, ['--apply'])
    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    conn = sqlite3.connect(wdb)
    w6 = conn.execute('select ref_start, ref_end from window_texts where id=?', ('w6',)).fetchone()
    w7 = conn.execute('select ref_start, ref_end from window_texts where id=?', ('w7',)).fetchone()
    w8 = conn.execute('select ref_start, ref_end from window_texts where id=?', ('w8',)).fetchone()
    conn.close()
    # w6: ref_start pointed at the deleted row -> moves FORWARD to the next
    # real line (original position 394, which itself shifts down to 393);
    # ref_end (original position 396) shifts down to 395.
    assert w6 == ('Milton P.L. 4.393', 'Milton P.L. 4.395')
    # w7: ref_end pointed at the deleted row -> moves BACK to the previous
    # real line (original position 392, unaffected by the shift); ref_start
    # (original position 391) is also unaffected.
    assert w7 == ('Milton P.L. 4.391', 'Milton P.L. 4.392')
    # w8: nothing but the deleted row on both ends -- start moves forward,
    # end moves back, so the remapped window's start (393) lands after its
    # end (392). Left as-is (a warning is printed); not repaired here.
    assert w8 == ('Milton P.L. 4.393', 'Milton P.L. 4.392')


def test_apply_warns_about_degenerate_window(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    proc = run_script(root, ['--apply'])
    assert 'WARNING' in proc.stdout
    assert 'w8' in proc.stdout


def test_apply_remaps_descriptions_jsonl(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    run_script(root, ['--apply'])
    dpath = os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl')
    records = {}
    with open(dpath, encoding='utf-8') as f:
        for line in f:
            r = json.loads(line)
            records[r['id']] = r
    assert records['w1']['ref_start'] == 'Milton P.L. 1.1'
    assert records['w2']['ref_start'] == 'Milton P.L. 1.4'
    assert records['w2']['ref_end'] == 'Milton P.L. 1.6'
    assert records['w3']['ref_start'] == 'Milton P.L. 7.1'
    assert records['w5']['ref_start'] == 'verg. aen. 1.1'  # unrelated, untouched
    assert records['w6']['ref_start'] == 'Milton P.L. 4.393'  # moved forward off the deleted row
    assert records['w6']['ref_end'] == 'Milton P.L. 4.395'
    # id and work never change
    assert records['w2']['id'] == 'w2'
    assert records['w2']['work'] == PART1


def test_apply_deletes_matching_fusion_cache_only(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    run_script(root, ['--apply'])
    assert not os.path.exists(os.path.join(root, 'cache', 'hit.json'))
    assert os.path.exists(os.path.join(root, 'cache', 'miss.json'))


def test_apply_leaves_backup_files(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    run_script(root, ['--apply'])
    ppath = os.path.join(root, 'data', 'passage_index')
    backups = [f for f in os.listdir(ppath) if '.bak-milton-' in f]
    assert backups, 'expected at least one .bak-milton-<stamp> backup file'
