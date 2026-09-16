"""Fixture test for scripts/corpus/apply_prelude_books.py.

The real passage index (data/passage_index/) is multi-gigabyte, not in git,
and not available in this checkout, so this builds a tiny synthetic stand-in
with the same shapes (window_texts.db tables, ids.json, descriptions.jsonl,
a cache/*.json fusion result, and the three current post-split .tess files)
and runs the script against it with --apply. This is the acceptance check
for the script: nothing here ever touches a real passage index.
"""
import json
import os
import sqlite3
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, 'scripts', 'corpus', 'apply_prelude_books.py')


def _tess_lines(book, start, end):
    return ''.join(
        f'<wordsworth prelude {book}.{i}>\tline{book}-{i}\n' for i in range(start, end + 1)
    )


def build_fixture(root):
    os.makedirs(os.path.join(root, 'texts', 'en'), exist_ok=True)
    os.makedirs(os.path.join(root, 'data', 'passage_index'), exist_ok=True)
    os.makedirs(os.path.join(root, 'cache'), exist_ok=True)

    part12 = _tess_lines(12, 1, 336)
    part13 = _tess_lines(13, 1, 378)
    part14 = _tess_lines(14, 1, 456)
    with open(os.path.join(root, 'texts', 'en', 'wordsworth.prelude.part.12.tess'), 'w', encoding='utf-8') as f:
        f.write(part12)
    with open(os.path.join(root, 'texts', 'en', 'wordsworth.prelude.part.13.tess'), 'w', encoding='utf-8') as f:
        f.write(part13)
    with open(os.path.join(root, 'texts', 'en', 'wordsworth.prelude.part.14.tess'), 'w', encoding='utf-8') as f:
        f.write(part14)
    with open(os.path.join(root, 'texts', 'en', 'wordsworth.prelude.tess'), 'w', encoding='utf-8') as f:
        f.write(part12 + part13 + part14)

    # window_texts.db
    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    c = sqlite3.connect(wdb)
    c.execute('CREATE TABLE window_texts (id TEXT, language TEXT, work TEXT, '
              'ref_start TEXT, ref_end TEXT, text TEXT)')
    c.execute('CREATE TABLE lines (work TEXT, ord INTEGER, ref TEXT, text TEXT)')

    window_rows = [
        # whole-work windows
        ('wordsworth.prelude:fine:1', 'en', 'wordsworth.prelude',
         'wordsworth prelude 12.5', 'wordsworth prelude 12.15', 'w1'),
        ('wordsworth.prelude:fine:2', 'en', 'wordsworth.prelude',
         'wordsworth prelude 12.330', 'wordsworth prelude 12.340', 'w2 straddle 12/13'),
        ('wordsworth.prelude:fine:3', 'en', 'wordsworth.prelude',
         'wordsworth prelude 12.710', 'wordsworth prelude 12.720', 'w3 straddle 13/14'),
        # part.12 windows
        ('wordsworth.prelude.part.12:fine:1', 'en', 'wordsworth.prelude.part.12',
         'wordsworth prelude 12.5', 'wordsworth prelude 12.15', 'p1 stays 12'),
        ('wordsworth.prelude.part.12:fine:400', 'en', 'wordsworth.prelude.part.12',
         'wordsworth prelude 12.400', 'wordsworth prelude 12.410', 'p2 moves to 13'),
        ('wordsworth.prelude.part.12:fine:900', 'en', 'wordsworth.prelude.part.12',
         'wordsworth prelude 12.900', 'wordsworth prelude 12.910', 'p3 moves to 14 (undescribed)'),
        ('wordsworth.prelude.part.12:fine:330', 'en', 'wordsworth.prelude.part.12',
         'wordsworth prelude 12.330', 'wordsworth prelude 12.340', 'p4 straddle 12/13 stays 12'),
        ('wordsworth.prelude.part.12:fine:710', 'en', 'wordsworth.prelude.part.12',
         'wordsworth prelude 12.710', 'wordsworth prelude 12.720', 'p5 straddle 13/14 moves to 13'),
        # unrelated work
        ('vergil.aeneid:fine:1', 'la', 'vergil.aeneid',
         'verg. aen. 1.1', 'verg. aen. 1.5', 'arma virumque cano'),
    ]
    c.executemany('INSERT INTO window_texts VALUES (?,?,?,?,?,?)', window_rows)

    line_rows = [
        ('wordsworth.prelude', 0, 'wordsworth prelude 12.334', 'lineA'),
        ('wordsworth.prelude', 1, 'wordsworth prelude 12.338', 'lineB'),
        ('wordsworth.prelude', 2, 'wordsworth prelude 12.716', 'lineC'),
        ('wordsworth.prelude.part.12', 0, 'wordsworth prelude 12.1', 'stale'),
        ('wordsworth.prelude.part.12', 1, 'wordsworth prelude 12.500', 'stale'),
        ('wordsworth.prelude.part.12', 2, 'wordsworth prelude 12.1170', 'stale'),
        ('vergil.aeneid', 0, 'verg. aen. 1.1', 'arma virumque cano'),
    ]
    c.executemany('INSERT INTO lines VALUES (?,?,?,?)', line_rows)
    c.commit(); c.close()

    # descriptions.jsonl: mirrors most window_texts rows, plus one fallback-only
    # row (id 'p2b') that is NOT in window_texts.db at all, and deliberately
    # omits 'p3' (the undescribed-window case, present only in window_texts.db
    # and ids.json).
    desc_rows = [
        {'id': 'wordsworth.prelude:fine:1', 'work': 'wordsworth.prelude', 'scale': 'fine',
         'ref_start': 'wordsworth prelude 12.5', 'ref_end': 'wordsworth prelude 12.15',
         'desc': {'gist': 'd1'}},
        {'id': 'wordsworth.prelude:fine:2', 'work': 'wordsworth.prelude', 'scale': 'fine',
         'ref_start': 'wordsworth prelude 12.330', 'ref_end': 'wordsworth prelude 12.340',
         'desc': {'gist': 'd2'}},
        {'id': 'wordsworth.prelude:fine:3', 'work': 'wordsworth.prelude', 'scale': 'fine',
         'ref_start': 'wordsworth prelude 12.710', 'ref_end': 'wordsworth prelude 12.720',
         'desc': {'gist': 'd3'}},
        {'id': 'wordsworth.prelude.part.12:fine:1', 'work': 'wordsworth.prelude.part.12', 'scale': 'fine',
         'ref_start': 'wordsworth prelude 12.5', 'ref_end': 'wordsworth prelude 12.15',
         'desc': {'gist': 'p1'}},
        {'id': 'wordsworth.prelude.part.12:fine:400', 'work': 'wordsworth.prelude.part.12', 'scale': 'fine',
         'ref_start': 'wordsworth prelude 12.400', 'ref_end': 'wordsworth prelude 12.410',
         'desc': {'gist': 'p2'}},
        {'id': 'wordsworth.prelude.part.12:fine:330', 'work': 'wordsworth.prelude.part.12', 'scale': 'fine',
         'ref_start': 'wordsworth prelude 12.330', 'ref_end': 'wordsworth prelude 12.340',
         'desc': {'gist': 'p4'}},
        {'id': 'wordsworth.prelude.part.12:fine:710', 'work': 'wordsworth.prelude.part.12', 'scale': 'fine',
         'ref_start': 'wordsworth prelude 12.710', 'ref_end': 'wordsworth prelude 12.720',
         'desc': {'gist': 'p5'}},
        {'id': 'wordsworth.prelude.part.12:fine:950', 'work': 'wordsworth.prelude.part.12', 'scale': 'fine',
         'ref_start': 'wordsworth prelude 12.950', 'ref_end': 'wordsworth prelude 12.960',
         'desc': {'gist': 'p2b fallback-only, moves to 14'}},
        {'id': 'vergil.aeneid:fine:1', 'work': 'vergil.aeneid', 'scale': 'fine',
         'ref_start': 'verg. aen. 1.1', 'ref_end': 'verg. aen. 1.5',
         'desc': {'gist': 'unrelated'}},
    ]
    dpath = os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl')
    with open(dpath, 'w', encoding='utf-8') as f:
        for r in desc_rows:
            f.write(json.dumps(r) + '\n')

    # ids.json: embedding-row order. Includes the fallback-only id 'p2b' and
    # the undescribed id 'p3', both of which must still get renamed correctly.
    ids = [
        'wordsworth.prelude:fine:1', 'wordsworth.prelude:fine:2', 'wordsworth.prelude:fine:3',
        'wordsworth.prelude.part.12:fine:1', 'wordsworth.prelude.part.12:fine:400',
        'wordsworth.prelude.part.12:fine:900', 'wordsworth.prelude.part.12:fine:330',
        'wordsworth.prelude.part.12:fine:710', 'vergil.aeneid:fine:1',
        'wordsworth.prelude.part.12:fine:950',
    ]
    with open(os.path.join(root, 'data', 'passage_index', 'ids.json'), 'w', encoding='utf-8') as f:
        json.dump(ids, f)

    # a cached fusion result naming one of the Prelude works, plus one that
    # doesn't, to check selective deletion.
    with open(os.path.join(root, 'cache', 'hit.json'), 'w', encoding='utf-8') as f:
        json.dump({'source': 'wordsworth.prelude.part.12', 'target': 'someone.else'}, f)
    with open(os.path.join(root, 'cache', 'miss.json'), 'w', encoding='utf-8') as f:
        json.dump({'source': 'foo', 'target': 'bar'}, f)

    return ids


def run_script(root, extra_args=()):
    return subprocess.run(
        [sys.executable, SCRIPT, *extra_args], cwd=root,
        capture_output=True, text=True, check=True)


def test_dry_run_changes_nothing(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    ipath = os.path.join(root, 'data', 'passage_index', 'ids.json')
    dpath = os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl')
    before_wdb = open(wdb, 'rb').read()
    before_ids = open(ipath, encoding='utf-8').read()
    before_desc = open(dpath, encoding='utf-8').read()

    proc = run_script(root)
    assert 'DRY RUN' in proc.stdout

    assert open(wdb, 'rb').read() == before_wdb
    assert open(ipath, encoding='utf-8').read() == before_ids
    assert open(dpath, encoding='utf-8').read() == before_desc
    assert os.path.exists(os.path.join(root, 'cache', 'hit.json'))


def test_apply_remaps_and_splits(tmp_path):
    root = str(tmp_path)
    ids_before = build_fixture(root)

    proc = run_script(root, ['--apply'])
    assert 'APPLY' in proc.stdout

    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    c = sqlite3.connect(wdb)

    # --- window_texts table ---
    rows = {r[0]: r for r in c.execute(
        'SELECT id, work, ref_start, ref_end, text FROM window_texts')}

    # whole-work rows: refs remapped, work/id unchanged
    assert rows['wordsworth.prelude:fine:1'][1:4] == (
        'wordsworth.prelude', 'wordsworth prelude 12.5', 'wordsworth prelude 12.15')
    assert rows['wordsworth.prelude:fine:2'][1:4] == (
        'wordsworth.prelude', 'wordsworth prelude 12.330', 'wordsworth prelude 13.4')
    assert rows['wordsworth.prelude:fine:3'][1:4] == (
        'wordsworth.prelude', 'wordsworth prelude 13.374', 'wordsworth prelude 14.6')

    # part.12 rows that stay in part.12
    assert 'wordsworth.prelude.part.12:fine:1' in rows
    assert rows['wordsworth.prelude.part.12:fine:1'][1:4] == (
        'wordsworth.prelude.part.12', 'wordsworth prelude 12.5', 'wordsworth prelude 12.15')
    # straddling 12/13, decided by ref_start -> stays part.12
    assert 'wordsworth.prelude.part.12:fine:330' in rows
    assert rows['wordsworth.prelude.part.12:fine:330'][1:4] == (
        'wordsworth.prelude.part.12', 'wordsworth prelude 12.330', 'wordsworth prelude 13.4')

    # moved to part.13 (fully within book 13)
    assert 'wordsworth.prelude.part.12:fine:400' not in rows
    assert 'wordsworth.prelude.part.13:fine:400' in rows
    assert rows['wordsworth.prelude.part.13:fine:400'][1:4] == (
        'wordsworth.prelude.part.13', 'wordsworth prelude 13.64', 'wordsworth prelude 13.74')

    # moved to part.14 (fully within book 14)
    assert 'wordsworth.prelude.part.12:fine:900' not in rows
    assert 'wordsworth.prelude.part.14:fine:900' in rows
    assert rows['wordsworth.prelude.part.14:fine:900'][1:4] == (
        'wordsworth.prelude.part.14', 'wordsworth prelude 14.186', 'wordsworth prelude 14.196')

    # straddling 13/14, decided by ref_start -> moves to part.13
    assert 'wordsworth.prelude.part.12:fine:710' not in rows
    assert 'wordsworth.prelude.part.13:fine:710' in rows
    assert rows['wordsworth.prelude.part.13:fine:710'][1:4] == (
        'wordsworth.prelude.part.13', 'wordsworth prelude 13.374', 'wordsworth prelude 14.6')

    # unrelated work untouched
    assert rows['vergil.aeneid:fine:1'][1:4] == (
        'vergil.aeneid', 'verg. aen. 1.1', 'verg. aen. 1.5')

    # --- lines table ---
    whole_lines = dict(c.execute(
        "SELECT ref, text FROM lines WHERE work='wordsworth.prelude' ORDER BY ord"))
    assert list(whole_lines.items()) == [
        ('wordsworth prelude 12.334', 'lineA'),
        ('wordsworth prelude 13.2', 'lineB'),
        ('wordsworth prelude 14.2', 'lineC'),
    ]

    for work, n, first_ref, last_ref in (
        ('wordsworth.prelude.part.12', 336, 'wordsworth prelude 12.1', 'wordsworth prelude 12.336'),
        ('wordsworth.prelude.part.13', 378, 'wordsworth prelude 13.1', 'wordsworth prelude 13.378'),
        ('wordsworth.prelude.part.14', 456, 'wordsworth prelude 14.1', 'wordsworth prelude 14.456'),
    ):
        got = c.execute(
            'SELECT ord, ref FROM lines WHERE work=? ORDER BY ord', (work,)).fetchall()
        assert len(got) == n, (work, len(got))
        assert [o for o, _ in got] == list(range(n))
        assert got[0][1] == first_ref
        assert got[-1][1] == last_ref
    c.close()

    # --- descriptions.jsonl ---
    dpath = os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl')
    recs = {json.loads(l)['id']: json.loads(l) for l in open(dpath, encoding='utf-8')}
    assert recs['wordsworth.prelude.part.13:fine:400']['work'] == 'wordsworth.prelude.part.13'
    assert recs['wordsworth.prelude.part.13:fine:400']['ref_start'] == 'wordsworth prelude 13.64'
    # the fallback-only row: not in window_texts.db, decided from its own ref_start
    assert 'wordsworth.prelude.part.12:fine:950' not in recs
    moved = recs['wordsworth.prelude.part.14:fine:950']
    assert moved['work'] == 'wordsworth.prelude.part.14'
    assert moved['ref_start'] == 'wordsworth prelude 14.236'
    assert moved['ref_end'] == 'wordsworth prelude 14.246'
    assert moved['desc']['gist'] == 'p2b fallback-only, moves to 14'
    # unrelated row untouched
    assert recs['vergil.aeneid:fine:1']['work'] == 'vergil.aeneid'

    # --- ids.json: same order and count, renamed in place ---
    ipath = os.path.join(root, 'data', 'passage_index', 'ids.json')
    ids_after = json.load(open(ipath, encoding='utf-8'))
    assert len(ids_after) == len(ids_before)
    expected = list(ids_before)
    expected[expected.index('wordsworth.prelude.part.12:fine:400')] = 'wordsworth.prelude.part.13:fine:400'
    expected[expected.index('wordsworth.prelude.part.12:fine:900')] = 'wordsworth.prelude.part.14:fine:900'
    expected[expected.index('wordsworth.prelude.part.12:fine:710')] = 'wordsworth.prelude.part.13:fine:710'
    expected[expected.index('wordsworth.prelude.part.12:fine:950')] = 'wordsworth.prelude.part.14:fine:950'
    assert ids_after == expected
    # the undescribed id (:fine:900, only ever in window_texts.db) still renamed
    assert 'wordsworth.prelude.part.14:fine:900' in ids_after
    # untouched entries stay untouched, including the still-part.12 straddler
    assert 'wordsworth.prelude.part.12:fine:330' in ids_after

    # --- fusion cache ---
    assert not os.path.exists(os.path.join(root, 'cache', 'hit.json'))
    assert os.path.exists(os.path.join(root, 'cache', 'miss.json'))

    # --- backups were made ---
    backups = [f for f in os.listdir(os.path.join(root, 'data', 'passage_index'))
               if '.bak-prelude-' in f]
    assert len(backups) >= 3  # window_texts.db, descriptions.jsonl, ids.json
