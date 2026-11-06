"""Tests for scripts/syntax: the ref rule, part-file slicing, and the plan and build steps.

The real syntax databases are 1 to 2 GB, so these build tiny stand-ins with the
production table shapes and run the scripts against them.
"""
import json
import os
import sqlite3
import subprocess
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYN = os.path.join(REPO_ROOT, 'scripts', 'syntax')
sys.path.insert(0, SYN)
sys.path.insert(0, REPO_ROOT)

from syntax_gap_lib import align, norm_key, read_tess  # noqa: E402

SCHEMA = [
    "CREATE TABLE syntax_source (parser TEXT, model TEXT, build_date TEXT, total_texts INTEGER, total_lines INTEGER)",
    "CREATE TABLE texts (text_id INTEGER PRIMARY KEY, filename TEXT UNIQUE NOT NULL)",
    "CREATE TABLE syntax (text_id INTEGER NOT NULL, ref TEXT NOT NULL, tokens TEXT, lemmas TEXT, upos TEXT, "
    "heads TEXT, deprels TEXT, feats TEXT, PRIMARY KEY (text_id, ref))",
]


def row(words):
    n = len(words)
    return (json.dumps(words), json.dumps([w.lower() for w in words]), json.dumps(['X'] * n),
            json.dumps([0] + [1] * (n - 1)), json.dumps(['root'] + ['dep'] * (n - 1)), json.dumps(['_'] * n))


def make_db(path, texts):
    """texts: {filename: [(ref, [words])]}"""
    c = sqlite3.connect(path)
    for s in SCHEMA:
        c.execute(s)
    for i, (fn, rs) in enumerate(texts.items(), 1):
        c.execute('INSERT INTO texts VALUES (?, ?)', (i, fn))
        for ref, words in rs:
            c.execute('INSERT INTO syntax VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (i, ref) + row(words))
    c.commit()
    c.close()


def write_tess(path, lines):
    with open(path, 'w', encoding='utf-8') as fh:
        for tag, text in lines:
            fh.write(f'<{tag}>\t{text}\n')


def test_norm_key_folds_accents_case_punctuation_and_letter_variants():
    assert norm_key('Ἀρχὴ τοῦ, εὐαγγελίου.') == norm_key('αρχη του ευαγγελιου')
    assert norm_key('Vergilius, Iuppiter') == norm_key('uergilius iuppiter')
    assert norm_key('λόγος') == norm_key('λογοσ')
    assert norm_key('') == ''


def test_read_tess_returns_the_tag_text_inside_the_brackets(tmp_path):
    p = tmp_path / 'x.tess'
    write_tess(p, [('lucr. 6.1189', 'salsaque per fauces'), ('lucr. 6.1190', 'uix edita')])
    assert [t for t, _ in read_tess(str(p))] == ['lucr. 6.1189', 'lucr. 6.1190']


def test_ref_rule_row_is_read_only_under_the_tag(tmp_path):
    """The channel reads a row only when ref equals the .tess tag exactly."""
    from backend import fusion
    db = tmp_path / 'syntax_latin.db'
    make_db(str(db), {'w.tess': [('w 1', ['a', 'b']), ('w urn:cts:latinLit:x.1', ['c'])]})
    fusion._SYNTAX_PARSE_CACHE.clear()
    parses = fusion._load_syntax_for_text(str(db), 'w.tess')
    assert 'w 1' in parses and 'w urn:cts:latinLit:x.1' in parses
    units = [{'ref': 'w 1'}, {'ref': 'w 2'}]  # a unit's ref is the tag
    assert [u['ref'] in parses for u in units] == [True, False]
    fusion._SYNTAX_PARSE_CACHE.clear()


def test_align_slices_a_whole_work_for_a_part_by_text_not_position():
    whole = [('W urn:1', norm_key('Arma virumque cano')), ('W urn:2', norm_key('Troiae qui primus')),
             ('W urn:3', norm_key('ab oris Italiam')), ('W urn:4', norm_key('fato profugus'))]
    part = [('p 1', 'ab oris Italiam,'), ('p 2', 'fato profugus.'), ('p 3', 'a line the whole never had')]
    m, un = align(part, whole, prefer_same_ref=False)
    assert m == {'p 1': 'W urn:3', 'p 2': 'W urn:4'}
    assert un == ['p 3']


def test_align_repeated_text_uses_each_row_once_in_order():
    rows = [('r1', norm_key('amen')), ('r2', norm_key('amen')), ('r3', norm_key('other'))]
    m, un = align([('a', 'Amen'), ('b', 'Amen'), ('c', 'Amen')], rows, prefer_same_ref=False)
    assert m == {'a': 'r1', 'b': 'r2'} and un == ['c']


def test_align_repeated_tag_keeps_the_first_line_only():
    rows = [('r1', norm_key('one')), ('r2', norm_key('two'))]
    m, un = align([('t', 'one'), ('t', 'two')], rows, prefer_same_ref=False)
    assert m == {'t': 'r1'} and un == []


def test_align_prefers_the_row_already_under_the_tag():
    rows = [('x', norm_key('same')), ('t', norm_key('same'))]
    m, _ = align([('t', 'same')], rows)
    assert m == {'t': 't'}


def run(script, *args):
    r = subprocess.run([sys.executable, os.path.join(SYN, script), *args], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr + r.stdout
    return r.stdout


@pytest.fixture
def fixture(tmp_path):
    texts = tmp_path / 'texts'
    texts.mkdir()
    # whole work parsed under CTS-style refs (never read), a part file with no parse,
    # a renamed work (old name only in the database), a brand new work.
    write_tess(texts / 'zz_test.whole.tess', [('zz 1', 'arma virumque cano'), ('zz 2', 'troiae qui primus ab oris')])
    write_tess(texts / 'zz_test.whole.part.2.tess', [('zz. 2.1', 'Troiae qui primus ab oris.'), ('zz. 2.2', 'a new line')])
    write_tess(texts / 'zz_test.newname.tess', [('nn 1', 'fato profugus'), ('nn 2', 'laviniaque venit')])
    write_tess(texts / 'zz_test.brand_new.tess', [('bb 1', 'gallia est omnis divisa')])
    db = tmp_path / 'syntax_latin.db'
    make_db(str(db), {
        'zz_test.whole.tess': [('zz_test.whole urn:cts:x.1', ['arma', 'virumque', 'cano']),
                               ('zz_test.whole urn:cts:x.2', ['troiae', 'qui', 'primus', 'ab', 'oris'])],
        'zz_test.oldname.tess': [('o 1', ['fato', 'profugus']), ('o 2', ['laviniaque', 'venit'])],
    })
    return tmp_path, texts, db


def test_plan_and_build_cover_part_rename_rekey_and_parse(fixture):
    tmp, texts, db = fixture
    out = tmp / 'out'
    out.mkdir()
    run('gap_plan.py', '--lang', 'la', '--db', str(db), '--texts', str(texts), '--out-dir', str(out))
    plan = json.load(open(out / 'plan_la.json'))
    # the whole work's rows are rekeyed to the tags
    assert plan['rekey']['zz_test.whole.tess'] == {'zz 1': 'zz_test.whole urn:cts:x.1', 'zz 2': 'zz_test.whole urn:cts:x.2'}
    # the part file copies line 1 from the whole work and parses line 2
    assert plan['copy']['zz_test.whole.part.2.tess'] == {'zz. 2.1': ['zz_test.whole.tess', 'zz_test.whole urn:cts:x.2']}
    assert plan['parse']['zz_test.whole.part.2.tess'] == ['zz. 2.2']
    # the renamed work copies both lines from the old name
    assert set(plan['copy']['zz_test.newname.tess']) == {'nn 1', 'nn 2'}
    assert plan['parse']['zz_test.brand_new.tess'] == ['bb 1']
    todo = [json.loads(line) for line in open(out / 'todo_la.jsonl', encoding='utf-8')]
    assert sorted(t['text'] for t in todo) == ['a new line', 'gallia est omnis divisa']
    parsed = out / 'parsed.jsonl'
    with open(parsed, 'w', encoding='utf-8') as fh:
        for t in todo:
            w = t['text'].split()
            fh.write(json.dumps({'id': t['id'], 'tokens': w, 'lemmas': w, 'upos': ['X'] * len(w),
                                 'heads': [0] + [1] * (len(w) - 1), 'deprels': ['root'] + ['dep'] * (len(w) - 1),
                                 'feats': ['_'] * len(w)}) + '\n')
    new = out / 'new.db'
    stats = json.loads(run('gap_build.py', '--lang', 'la', '--live-db', str(db), '--texts', str(texts),
                           '--plan', str(out / 'plan_la.json'), '--todo', str(out / 'todo_la.jsonl'),
                           '--parsed', str(parsed), '--out', str(new)).strip().splitlines()[-1])
    assert stats['integrity'] == 'ok' and stats['rekeyed'] == 2 and stats['copied'] == 3 and stats['parsed_rows'] == 2
    c = sqlite3.connect(new)
    refs = lambda fn: sorted(r for (r,) in c.execute(  # noqa: E731
        'SELECT ref FROM syntax s JOIN texts t USING (text_id) WHERE t.filename=?', (fn,)))
    assert refs('zz_test.whole.tess') == ['zz 1', 'zz 2']
    assert refs('zz_test.whole.part.2.tess') == ['zz. 2.1', 'zz. 2.2']
    assert refs('zz_test.newname.tess') == ['nn 1', 'nn 2']
    assert refs('zz_test.brand_new.tess') == ['bb 1']
    assert refs('zz_test.oldname.tess') == ['o 1', 'o 2']  # the old row stays
    # the copied part row carries the whole work's parse of that very line
    tok = c.execute("SELECT tokens FROM syntax s JOIN texts t USING (text_id) WHERE t.filename='zz_test.whole.part.2.tess' AND ref='zz. 2.1'").fetchone()[0]
    assert json.loads(tok) == ['troiae', 'qui', 'primus', 'ab', 'oris']
    # the live file is untouched
    assert sqlite3.connect(db).execute('SELECT COUNT(*) FROM texts').fetchone()[0] == 2


def test_build_refuses_to_overwrite_the_live_database(fixture):
    tmp, texts, db = fixture
    r = subprocess.run([sys.executable, os.path.join(SYN, 'gap_build.py'), '--lang', 'la', '--live-db', str(db),
                        '--texts', str(texts), '--plan', 'x', '--todo', 'x', '--out', str(db)],
                       capture_output=True, text=True)
    assert r.returncode != 0 and 'live database' in r.stderr
