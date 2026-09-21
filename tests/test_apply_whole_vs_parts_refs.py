"""Fixture tests for scripts/corpus/apply_whole_vs_parts_refs.py.

The real inverted index and passage index are multi-gigabyte and not in
this checkout, so this builds tiny synthetic stand-ins with the same table
shapes (confirmed against production read-only, 2026-09-20 -- see the
script's module docstring and docs/DATA_OPERATIONS.md) and runs the script
against them with subprocess, the same pattern as
tests/test_apply_prelude_books.py. Covers: a dry run makes no changes; an
apply remaps every store correctly and leaves unrelated rows alone; a
collision (a target ref already present for the same file/work) refuses
the apply with no writes at all.
"""
import json
import os
import sqlite3
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, 'scripts', 'corpus', 'apply_whole_vs_parts_refs.py')


def build_fixture(root, extra_grc_lines_row=None, extra_grc_postings_row=None):
    os.makedirs(os.path.join(root, 'data', 'inverted_index'), exist_ok=True)
    os.makedirs(os.path.join(root, 'data', 'passage_index'), exist_ok=True)
    os.makedirs(os.path.join(root, 'cache', 'reuse_pairs'), exist_ok=True)

    # --- grc_index.db: isocrates.letters.part.2.tess (doubled bracket) and
    # hyperides.speeches.tess (whole, needs "speeches." inserted), plus an
    # untouched part file and an unrelated work for isolation checks.
    grc = sqlite3.connect(os.path.join(root, 'data', 'inverted_index', 'grc_index.db'))
    grc.execute('CREATE TABLE texts (text_id INTEGER PRIMARY KEY, filename TEXT UNIQUE, '
                'author TEXT, title TEXT, line_count INTEGER)')
    grc.execute('CREATE TABLE lines (text_id INTEGER, ref TEXT, content TEXT, lemmas TEXT, '
                'tokens TEXT, PRIMARY KEY (text_id, ref))')
    grc.execute('CREATE TABLE postings (lemma TEXT, text_id INTEGER, ref TEXT, positions TEXT)')
    grc.executemany('INSERT INTO texts (text_id, filename) VALUES (?, ?)', [
        (1, 'isocrates.letters.part.2.tess'),
        (2, 'isocrates.letters.part.1.tess'),   # untouched: single bracket already
        (3, 'hyperides.speeches.tess'),          # whole: needs remap
        (4, 'hyperides.speeches.part.1.tess'),   # part: already correct, untouched
    ])
    grc.executemany('INSERT INTO lines (text_id, ref, content) VALUES (?, ?, ?)', [
        (1, '<isoc. letters 2.1', 'text21'),
        (1, '<isoc. letters 2.2', 'text22'),
        (2, 'isoc. letters 1.1', 'text11'),
        (3, 'hyp. 1.1', 'htext1'),
        (3, 'hyp. 1.2', 'htext2'),
        (4, 'hyp. speeches. 1.1', 'hptext1'),
    ])
    if extra_grc_lines_row:
        grc.execute('INSERT INTO lines (text_id, ref, content) VALUES (?, ?, ?)',
                    extra_grc_lines_row)
    grc.executemany('INSERT INTO postings (lemma, text_id, ref, positions) VALUES (?, ?, ?, ?)', [
        ('oida', 1, '<isoc. letters 2.1', '0'),
        ('pas', 1, '<isoc. letters 2.1', '1'),
        ('men', 1, '<isoc. letters 2.2', '0'),
        ('kai', 3, 'hyp. 1.1', '0'),
        ('idia', 3, 'hyp. 1.1', '1'),
    ])
    if extra_grc_postings_row:
        grc.execute('INSERT INTO postings (lemma, text_id, ref, positions) VALUES (?, ?, ?, ?)',
                    extra_grc_postings_row)
    grc.commit()
    grc.close()

    # --- la_index.db: couplet part.1 (needs "et alii" inserted), plus an
    # already-correct part for isolation.
    la = sqlite3.connect(os.path.join(root, 'data', 'inverted_index', 'la_index.db'))
    la.execute('CREATE TABLE texts (text_id INTEGER PRIMARY KEY, filename TEXT UNIQUE, '
               'author TEXT, title TEXT, line_count INTEGER)')
    la.execute('CREATE TABLE lines (text_id INTEGER, ref TEXT, content TEXT, lemmas TEXT, '
               'tokens TEXT, PRIMARY KEY (text_id, ref))')
    la.execute('CREATE TABLE postings (lemma TEXT, text_id INTEGER, ref TEXT, positions TEXT)')
    la.executemany('INSERT INTO texts (text_id, filename) VALUES (?, ?)', [
        (10, 'couplet_et_alii.confucius_sinarum_philosophus.part.1.tess'),
        (11, 'couplet_et_alii.confucius_sinarum_philosophus.part.2.tess'),
    ])
    la.executemany('INSERT INTO lines (text_id, ref, content) VALUES (?, ?, ?)', [
        (10, 'Couplet. Confucius. epist.dedicatio', 'ded'),
        (10, 'Couplet. Confucius. epist.1.1', 'e11'),
        (11, 'Couplet et alii. Confucius. proem. decl. titulus', 'titulus'),
    ])
    la.executemany('INSERT INTO postings (lemma, text_id, ref, positions) VALUES (?, ?, ?, ?)', [
        ('ludovicus', 10, 'Couplet. Confucius. epist.dedicatio', '0'),
        ('postquam', 10, 'Couplet. Confucius. epist.1.1', '0'),
    ])
    la.commit()
    la.close()

    # --- window_texts.db
    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    w = sqlite3.connect(wdb)
    w.execute('CREATE TABLE window_texts (id TEXT PRIMARY KEY, language TEXT, work TEXT, '
              'ref_start TEXT, ref_end TEXT, text TEXT)')
    w.execute('CREATE TABLE lines (work TEXT, ord INTEGER, ref TEXT, text TEXT)')
    w.executemany('INSERT INTO window_texts VALUES (?,?,?,?,?,?)', [
        ('isocrates.letters.part.2:fine:0', 'grc', 'isocrates.letters.part.2',
         '<isoc. letters 2.1', '<isoc. letters 2.2', 'w1'),
        ('hyperides.speeches:fine:0', 'grc', 'hyperides.speeches',
         'hyp. 1.1', 'hyp. 1.2', 'w2'),
        ('hyperides.speeches.part.1:fine:0', 'grc', 'hyperides.speeches.part.1',
         'hyp. speeches. 1.1', 'hyp. speeches. 1.2', 'w3 untouched'),
        ('couplet_et_alii.confucius_sinarum_philosophus.part.1:fine:0', 'la',
         'couplet_et_alii.confucius_sinarum_philosophus.part.1',
         'Couplet. Confucius. epist.dedicatio', 'Couplet. Confucius. epist.1.1', 'w4'),
        ('vergil.aeneid:fine:0', 'la', 'vergil.aeneid', 'verg. aen. 1.1', 'verg. aen. 1.5', 'unrelated'),
    ])
    w.executemany('INSERT INTO lines VALUES (?,?,?,?)', [
        ('isocrates.letters.part.2', 0, '<isoc. letters 2.1', 'text21'),
        ('isocrates.letters.part.2', 1, '<isoc. letters 2.2', 'text22'),
        ('hyperides.speeches', 0, 'hyp. 1.1', 'htext1'),
        ('hyperides.speeches.part.1', 0, 'hyp. speeches. 1.1', 'hptext1'),
        ('couplet_et_alii.confucius_sinarum_philosophus.part.1', 0,
         'Couplet. Confucius. epist.dedicatio', 'ded'),
    ])
    w.commit()
    w.close()

    # --- descriptions.jsonl
    dpath = os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl')
    records = [
        {'id': 'isocrates.letters.part.2:fine:0', 'work': 'isocrates.letters.part.2',
         'ref_start': '<isoc. letters 2.1', 'ref_end': '<isoc. letters 2.2', 'desc': {}},
        {'id': 'hyperides.speeches:fine:0', 'work': 'hyperides.speeches',
         'ref_start': 'hyp. 1.1', 'ref_end': 'hyp. 1.2', 'desc': {}},
        {'id': 'hyperides.speeches.part.1:fine:0', 'work': 'hyperides.speeches.part.1',
         'ref_start': 'hyp. speeches. 1.1', 'ref_end': 'hyp. speeches. 1.2', 'desc': {}},
        {'id': 'vergil.aeneid:fine:0', 'work': 'vergil.aeneid',
         'ref_start': 'verg. aen. 1.1', 'ref_end': 'verg. aen. 1.5', 'desc': {}},
    ]
    with open(dpath, 'w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r) + '\n')

    # --- reuse tables
    grc_reuse = sqlite3.connect(os.path.join(root, 'cache', 'reuse_pairs', 'grc.db'))
    grc_reuse.execute('CREATE TABLE pairs (work_a TEXT, line_a_ref TEXT, work_b TEXT, '
                       'line_b_ref TEXT, shared INTEGER, jaccard REAL, span_len INTEGER)')
    grc_reuse.execute('CREATE TABLE line_counts (work TEXT, line_ref TEXT, n_works INTEGER)')
    grc_reuse.executemany('INSERT INTO pairs VALUES (?,?,?,?,?,?,?)', [
        ('hyperides.speeches', 'hyp. 1.1', 'demosthenes.orations', 'dem. 1.1', 5, 0.5, 5),
        ('demosthenes.orations', 'dem. 2.1', 'hyperides.speeches', 'hyp. 1.2', 5, 0.5, 5),
        ('hyperides.speeches.part.1', 'hyp. speeches. 1.1', 'x.y', 'x.1', 5, 0.5, 5),
    ])
    grc_reuse.executemany('INSERT INTO line_counts VALUES (?,?,?)', [
        ('hyperides.speeches', 'hyp. 1.1', 2),
        ('hyperides.speeches.part.1', 'hyp. speeches. 1.1', 2),
    ])
    grc_reuse.commit()
    grc_reuse.close()

    la_reuse = sqlite3.connect(os.path.join(root, 'cache', 'reuse_pairs', 'la.db'))
    la_reuse.execute('CREATE TABLE pairs (work_a TEXT, line_a_ref TEXT, work_b TEXT, '
                      'line_b_ref TEXT, shared INTEGER, jaccard REAL, span_len INTEGER)')
    la_reuse.execute('CREATE TABLE line_counts (work TEXT, line_ref TEXT, n_works INTEGER)')
    la_reuse.commit()
    la_reuse.close()

    # --- a cached fusion result naming one of the touched files, and one that doesn't
    os.makedirs(os.path.join(root, 'cache'), exist_ok=True)
    with open(os.path.join(root, 'cache', 'hit.json'), 'w') as f:
        json.dump({'source': 'hyperides.speeches.tess', 'target': 'x.tess', 'results': []}, f)
    with open(os.path.join(root, 'cache', 'miss.json'), 'w') as f:
        json.dump({'source': 'unrelated.tess', 'target': 'x.tess', 'results': []}, f)


def run_script(root, *args):
    return subprocess.run([sys.executable, SCRIPT, '--root', root, *args],
                           capture_output=True, text=True)


def test_dry_run_makes_no_changes(tmp_path):
    root = str(tmp_path)
    build_fixture(root)

    before = open(os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl')).read()
    result = run_script(root)
    assert result.returncode == 0, result.stderr
    assert '182 ref' not in result.stdout  # sanity: this is the tiny fixture, not prod scale
    after = open(os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl')).read()
    assert before == after
    assert not os.path.exists(os.path.join(root, 'cache', 'hit.json') + '.bak-x')
    # counts reported
    assert 'grc_index.db lines: 4 ref(s) to remap' in result.stdout
    assert 'la_index.db lines: 2 ref(s) to remap' in result.stdout
    assert 'isocrates.letters.part.3.tess not found in texts table' in result.stdout
    assert 'window_texts.db lines: 4 ref(s) to remap' in result.stdout
    assert 'window_texts.db window_texts: 3 of 3 row(s) to remap' in result.stdout
    assert 'descriptions.jsonl: 2 of 2 record(s) to remap' in result.stdout
    assert 'fusion cache: 1 cached result(s)' in result.stdout


def test_apply_remaps_every_store_and_spares_untouched_rows(tmp_path):
    root = str(tmp_path)
    build_fixture(root)

    result = run_script(root, '--apply', '--tag', 'unittest')
    assert result.returncode == 0, result.stderr

    # grc_index.db
    grc = sqlite3.connect(os.path.join(root, 'data', 'inverted_index', 'grc_index.db'))
    assert grc.execute("select ref from lines where text_id=1 order by ref").fetchall() == \
        [('isoc. letters 2.1',), ('isoc. letters 2.2',)]
    assert grc.execute("select ref from lines where text_id=2").fetchall() == \
        [('isoc. letters 1.1',)]  # untouched (already correct)
    assert set(grc.execute("select ref from lines where text_id=3").fetchall()) == \
        {('hyp. speeches. 1.1',), ('hyp. speeches. 1.2',)}
    assert grc.execute("select ref from lines where text_id=4").fetchall() == \
        [('hyp. speeches. 1.1',)]  # part file untouched
    postings_refs = {r for (r,) in grc.execute("select ref from postings where text_id=1")}
    assert postings_refs == {'isoc. letters 2.1', 'isoc. letters 2.2'}
    postings_refs_hyp = {r for (r,) in grc.execute("select ref from postings where text_id=3")}
    assert postings_refs_hyp == {'hyp. speeches. 1.1'}
    grc.close()
    assert os.path.exists(os.path.join(root, 'data', 'inverted_index',
                                        'grc_index.db.bak-unittest'))

    # la_index.db
    la = sqlite3.connect(os.path.join(root, 'data', 'inverted_index', 'la_index.db'))
    assert set(la.execute("select ref from lines where text_id=10").fetchall()) == {
        ('Couplet et alii. Confucius. epist.dedicatio',),
        ('Couplet et alii. Confucius. epist.1.1',),
    }
    assert la.execute("select ref from lines where text_id=11").fetchall() == \
        [('Couplet et alii. Confucius. proem. decl. titulus',)]  # untouched
    la.close()

    # window_texts.db
    w = sqlite3.connect(os.path.join(root, 'data', 'passage_index', 'window_texts.db'))
    row = w.execute("select ref_start, ref_end from window_texts where id=?",
                     ('isocrates.letters.part.2:fine:0',)).fetchone()
    assert row == ('isoc. letters 2.1', 'isoc. letters 2.2')
    row2 = w.execute("select ref_start, ref_end from window_texts where id=?",
                      ('hyperides.speeches:fine:0',)).fetchone()
    assert row2 == ('hyp. speeches. 1.1', 'hyp. speeches. 1.2')
    row3 = w.execute("select ref_start, ref_end from window_texts where id=?",
                      ('hyperides.speeches.part.1:fine:0',)).fetchone()
    assert row3 == ('hyp. speeches. 1.1', 'hyp. speeches. 1.2')  # already correct, untouched
    unrelated = w.execute("select ref_start, ref_end from window_texts where id=?",
                           ('vergil.aeneid:fine:0',)).fetchone()
    assert unrelated == ('verg. aen. 1.1', 'verg. aen. 1.5')  # untouched
    lines_refs = {r for (r,) in w.execute(
        "select ref from lines where work='isocrates.letters.part.2'")}
    assert lines_refs == {'isoc. letters 2.1', 'isoc. letters 2.2'}
    w.close()

    # descriptions.jsonl
    recs = {json.loads(l)['id']: json.loads(l) for l in
            open(os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl'))}
    assert recs['isocrates.letters.part.2:fine:0']['ref_start'] == 'isoc. letters 2.1'
    assert recs['hyperides.speeches:fine:0']['ref_start'] == 'hyp. speeches. 1.1'
    assert recs['hyperides.speeches.part.1:fine:0']['ref_start'] == 'hyp. speeches. 1.1'
    assert recs['vergil.aeneid:fine:0']['ref_start'] == 'verg. aen. 1.1'  # untouched

    # reuse tables
    rc = sqlite3.connect(os.path.join(root, 'cache', 'reuse_pairs', 'grc.db'))
    pairs = rc.execute("select work_a, line_a_ref, work_b, line_b_ref from pairs").fetchall()
    assert ('hyperides.speeches', 'hyp. speeches. 1.1', 'demosthenes.orations', 'dem. 1.1') in pairs
    assert ('demosthenes.orations', 'dem. 2.1', 'hyperides.speeches', 'hyp. speeches. 1.2') in pairs
    # the part-file row (already correct) is untouched
    assert ('hyperides.speeches.part.1', 'hyp. speeches. 1.1', 'x.y', 'x.1') in pairs
    lc = rc.execute("select work, line_ref, n_works from line_counts").fetchall()
    assert ('hyperides.speeches', 'hyp. speeches. 1.1', 2) in lc
    assert ('hyperides.speeches.part.1', 'hyp. speeches. 1.1', 2) in lc
    rc.close()

    # fusion cache
    assert not os.path.exists(os.path.join(root, 'cache', 'hit.json'))
    assert os.path.exists(os.path.join(root, 'cache', 'miss.json'))


def test_collision_refuses_apply(tmp_path):
    root = str(tmp_path)
    # text_id 1 (isocrates.letters.part.2) already has a row at the TARGET
    # ref "isoc. letters 2.1" under some other old ref -- an artificial
    # collision to exercise the refusal path.
    build_fixture(root, extra_grc_lines_row=(1, 'isoc. letters 2.1', 'pre-existing'))

    grc_path = os.path.join(root, 'data', 'inverted_index', 'grc_index.db')
    before = open(grc_path, 'rb').read()

    result = run_script(root, '--apply', '--tag', 'shouldnotwrite')
    assert result.returncode != 0
    assert 'COLLISION' in result.stdout or 'collision' in result.stderr.lower()

    after = open(grc_path, 'rb').read()
    assert before == after, 'a collision must refuse the apply with NO writes'
    assert not os.path.exists(grc_path + '.bak-shouldnotwrite')
