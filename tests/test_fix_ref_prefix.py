"""Fixture tests for scripts/corpus/fix_ref_prefix.py.

Builds tiny stand-ins with the shapes of the real stores (checked read-only
against production, 2026-10-16) and runs the script on them by subprocess.
Covers: a dry run writes nothing; an apply rewrites every string-ref store and
leaves other rows alone; the derived stores (inverted index, lemma cache) are
counted but never written; the prefix boundary; a second apply changes nothing.
"""
import json
import os
import sqlite3
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, 'scripts', 'corpus', 'fix_ref_prefix.py')

OLD = 'libanius. orations_1-11.'
NEW = 'libanius. orations.'
WORK = 'libanius.orations.part.1'
ARGS = ['--fix', WORK, OLD, NEW]


def build_fixture(root):
    pi = os.path.join(root, 'data', 'passage_index')
    for d in (pi, os.path.join(root, 'data', 'inverted_index'),
              os.path.join(root, 'data', 'events'), os.path.join(root, 'cache', 'reuse_pairs'),
              os.path.join(root, 'cache', 'lemmas', 'grc'),
              os.path.join(root, 'backend', 'embeddings', 'grc')):
        os.makedirs(d, exist_ok=True)

    c = sqlite3.connect(os.path.join(pi, 'window_texts.db'))
    c.execute('CREATE TABLE window_texts (id TEXT PRIMARY KEY, language TEXT, work TEXT, '
              'ref_start TEXT, ref_end TEXT, text TEXT)')
    c.execute('CREATE TABLE lines (work TEXT, ord INTEGER, ref TEXT, text TEXT)')
    c.executemany('INSERT INTO window_texts VALUES (?,?,?,?,?,?)', [
        (WORK + ':fine:0', 'grc', WORK, OLD + ' 1.1', OLD + ' 1.12', 't'),
        ('libanius.orations:fine:0', 'grc', 'libanius.orations', NEW + ' 1.1', NEW + ' 1.12', 't'),
        ('other.work:fine:0', 'grc', 'other.work', 'x. 1', 'x. 2', 't'),
    ])
    c.executemany('INSERT INTO lines VALUES (?,?,?,?)', [
        (WORK, 0, OLD + ' 1.1', 'a'), (WORK, 1, OLD + ' 1.2', 'b'),
        ('libanius.orations', 0, NEW + ' 1.1', 'a'), ('other.work', 0, 'x. 1', 'c'),
    ])
    c.commit()
    c.close()

    with open(os.path.join(pi, 'descriptions.jsonl'), 'w', encoding='utf-8') as fh:
        for rec in (
            {'id': WORK + ':fine:0', 'work': WORK, 'ref_start': OLD + ' 1.1', 'ref_end': OLD + ' 1.12'},
            {'id': 'other.work:fine:0', 'work': 'other.work', 'ref_start': 'x. 1', 'ref_end': 'x. 2'},
        ):
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')

    c = sqlite3.connect(os.path.join(root, 'cache', 'reuse_pairs', 'grc.db'))
    c.execute('CREATE TABLE pairs (work_a TEXT, line_a_ref TEXT, work_b TEXT, line_b_ref TEXT, '
              'shared INTEGER, jaccard REAL, span_len INTEGER)')
    c.execute('CREATE TABLE line_counts (work TEXT, line_ref TEXT, n_works INTEGER)')
    c.executemany('INSERT INTO pairs VALUES (?,?,?,?,?,?,?)', [
        ('libanius.orations_1-11.part.1', OLD + ' 1.1', 'other.work', 'x. 1', 3, .5, 4),
        ('other.work', 'x. 1', WORK, OLD + ' 1.2', 3, .5, 4),
        ('other.work', 'x. 1', 'other.work', 'x. 2', 3, .5, 4),
    ])
    c.executemany('INSERT INTO line_counts VALUES (?,?,?)', [
        (WORK, OLD + ' 1.1', 2), ('other.work', 'x. 1', 2),
        # a longer range must not match the shorter one's prefix
        ('libanius.orations_1-11', 'libanius. orations_1-110. 5.1', 1),
    ])
    c.commit()
    c.close()

    c = sqlite3.connect(os.path.join(root, 'data', 'events', 'event_dossiers.sqlite'))
    c.execute('CREATE TABLE passages (event_id TEXT, rank INTEGER, work TEXT, ref_start TEXT, '
              'ref_end TEXT, score REAL, llm_label TEXT, names_matched TEXT, snippet TEXT, '
              'window_id TEXT, language TEXT)')
    c.execute('CREATE TABLE scholarship (event_id TEXT, kind TEXT, title TEXT, page_ref TEXT, '
              'url TEXT, passage_rank INTEGER, passage_ref TEXT)')
    c.execute("INSERT INTO passages (event_id, work, ref_start, ref_end, window_id) VALUES "
              "('e1','libanius.orations_1-11', ?, ?, 'old:fine:1')", (OLD + ' 5.15', OLD + ' 5.26'))
    c.execute("INSERT INTO passages (event_id, work, ref_start, ref_end, window_id) VALUES "
              "('e2','other.work','x. 1','x. 2','o:fine:1')")
    c.commit()
    c.close()

    c = sqlite3.connect(os.path.join(root, 'data', 'inverted_index', 'grc_index.db'))
    c.execute('CREATE TABLE texts (text_id INTEGER PRIMARY KEY, filename TEXT UNIQUE, author TEXT, '
              'title TEXT, line_count INTEGER)')
    c.execute('CREATE TABLE lines (text_id INTEGER, ref TEXT, content TEXT, lemmas TEXT, tokens TEXT, '
              'PRIMARY KEY (text_id, ref))')
    c.execute('CREATE TABLE postings (lemma TEXT, text_id INTEGER, ref TEXT, positions TEXT)')
    c.execute("INSERT INTO texts (text_id, filename) VALUES (1, ?)", (WORK + '.tess',))
    c.execute("INSERT INTO lines (text_id, ref) VALUES (1, ?)", (OLD + ' 1.1',))
    c.executemany("INSERT INTO postings VALUES (?,?,?,?)",
                  [('a', 1, OLD + ' 1.1', '0'), ('b', 1, OLD + ' 1.1', '1')])
    c.commit()
    c.close()

    with open(os.path.join(root, 'cache', 'lemmas', 'grc', WORK + '-abc.json'), 'w') as fh:
        json.dump({'text_id': WORK + '.tess', 'file_hash': 'h',
                   'units_line': [{'ref': OLD + ' 1.1'}], 'units_phrase': [{'ref': OLD + ' 1.1'}]}, fh)
    with open(os.path.join(root, 'backend', 'embeddings', 'grc', WORK + '.meta.json'), 'w') as fh:
        json.dump({'n_lines': 2, 'line_refs': [OLD + ' 1.1', OLD + ' 1.2']}, fh)


def run(root, *extra):
    return subprocess.run([sys.executable, SCRIPT, '--root', str(root), *ARGS, *extra],
                          capture_output=True, text=True, check=False)


def q(root, rel, sql):
    c = sqlite3.connect(os.path.join(root, rel))
    rows = c.execute(sql).fetchall()
    c.close()
    return rows


def snapshot(root):
    out = {}
    for d, _dn, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            with open(p, 'rb') as fh:
                out[p] = fh.read()
    return out


def test_dry_run_writes_nothing_and_counts(tmp_path):
    build_fixture(str(tmp_path))
    before = snapshot(str(tmp_path))
    r = run(tmp_path)
    assert r.returncode == 0, r.stderr
    assert snapshot(str(tmp_path)) == before
    assert 'DRY RUN' in r.stdout and 'nothing written' in r.stdout
    assert 'window_texts (windows)' in r.stdout
    assert 'postings (REBUILD)' in r.stdout
    assert 'older work id' in r.stdout


def test_apply_rewrites_string_stores_only(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    derived = {p: b for p, b in snapshot(root).items()
               if 'inverted_index' in p or os.sep + 'lemmas' + os.sep in p}
    r = run(tmp_path, '--apply')
    assert r.returncode == 0, r.stderr
    assert q(root, 'data/passage_index/window_texts.db',
             f"select ref_start, ref_end from window_texts where work='{WORK}'") == [
        (NEW + ' 1.1', NEW + ' 1.12')]
    assert sorted(x[0] for x in q(root, 'data/passage_index/window_texts.db',
                                  f"select ref from lines where work='{WORK}'")) == [
        NEW + ' 1.1', NEW + ' 1.2']
    assert q(root, 'data/passage_index/window_texts.db',
             "select ref from lines where work='other.work'") == [('x. 1',)]
    recs = [json.loads(line) for line in open(
        os.path.join(root, 'data/passage_index/descriptions.jsonl'), encoding='utf-8')]
    assert recs[0]['ref_start'] == NEW + ' 1.1' and recs[1]['ref_start'] == 'x. 1'
    assert q(root, 'cache/reuse_pairs/grc.db', 'select line_a_ref, line_b_ref from pairs') == [
        (NEW + ' 1.1', 'x. 1'), ('x. 1', NEW + ' 1.2'), ('x. 1', 'x. 2')]
    assert sorted(x[0] for x in q(root, 'cache/reuse_pairs/grc.db',
                                  'select line_ref from line_counts')) == sorted(
        ['libanius. orations_1-110. 5.1', 'x. 1', NEW + ' 1.1'])
    assert q(root, 'data/events/event_dossiers.sqlite',
             'select ref_start, ref_end, window_id from passages order by event_id') == [
        (NEW + ' 5.15', NEW + ' 5.26', 'old:fine:1'), ('x. 1', 'x. 2', 'o:fine:1')]
    meta = json.load(open(os.path.join(root, 'backend/embeddings/grc', WORK + '.meta.json')))
    assert meta['line_refs'] == [NEW + ' 1.1', NEW + ' 1.2']
    # derived stores are not touched
    now = snapshot(root)
    for p, b in derived.items():
        assert now[p] == b
    # a dated backup sits beside every store written
    names = os.listdir(os.path.join(root, 'data', 'passage_index'))
    assert any(n.startswith('window_texts.db.bak-fixrefs-') for n in names)
    assert any(n.startswith('descriptions.jsonl.bak-fixrefs-') for n in names)


def test_second_apply_changes_nothing(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    assert run(tmp_path, '--apply').returncode == 0
    after_first = {p: b for p, b in snapshot(root).items() if '.bak-' not in p}
    r = run(tmp_path, '--apply')
    assert r.returncode == 0, r.stderr
    assert {p: b for p, b in snapshot(root).items() if '.bak-' not in p} == after_first


def test_same_prefix_refused(tmp_path):
    r = subprocess.run([sys.executable, SCRIPT, '--root', str(tmp_path), '--fix', WORK, OLD, OLD],
                       capture_output=True, text=True, check=False)
    assert r.returncode == 2


def test_only_limits_the_stores_written(tmp_path):
    root = str(tmp_path)
    build_fixture(root)
    assert run(tmp_path, '--apply', '--only', 'events').returncode == 0
    assert q(root, 'data/events/event_dossiers.sqlite',
             'select ref_start from passages order by event_id')[0] == (NEW + ' 5.15',)
    assert q(root, 'data/passage_index/window_texts.db',
             f"select ref_start from window_texts where work='{WORK}'") == [(OLD + ' 1.1',)]
    assert run(tmp_path, '--only', 'nonsense').returncode == 2
