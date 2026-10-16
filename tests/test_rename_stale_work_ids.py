"""Fixture tests for scripts/corpus/rename_stale_work_ids.py (reuse table and events store)."""
import os
import sqlite3
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, 'scripts', 'corpus', 'rename_stale_work_ids.py')
OLD, NEW = 'libanius.orations_1-11.part.1', 'libanius.orations.part.1'


def build(root, new_rows=False):
    os.makedirs(os.path.join(root, 'cache', 'reuse_pairs'))
    os.makedirs(os.path.join(root, 'data', 'events'))
    c = sqlite3.connect(os.path.join(root, 'cache', 'reuse_pairs', 'grc.db'))
    c.execute('CREATE TABLE pairs (work_a TEXT, line_a_ref TEXT, work_b TEXT, line_b_ref TEXT, '
              'shared INTEGER, jaccard REAL, span_len INTEGER)')
    c.execute('CREATE TABLE line_counts (work TEXT, line_ref TEXT, n_works INTEGER)')
    c.executemany('INSERT INTO pairs VALUES (?,?,?,?,1,.5,3)', [
        (OLD, 'a 1', 'other.work', 'b 1'), ('other.work', 'b 1', OLD, 'a 2'),
        ('other.work', 'b 1', 'other.work2', 'b 2')])
    c.executemany('INSERT INTO line_counts VALUES (?,?,1)', [(OLD, 'a 1'), ('other.work', 'b 1')])
    if new_rows:
        c.execute('INSERT INTO line_counts VALUES (?,?,1)', (NEW, 'a 9'))
    c.commit()
    c.close()
    c = sqlite3.connect(os.path.join(root, 'data', 'events', 'event_dossiers.sqlite'))
    c.execute('CREATE TABLE passages (event_id TEXT, rank INTEGER, work TEXT, ref_start TEXT, '
              'ref_end TEXT, score REAL, llm_label TEXT, names_matched TEXT, snippet TEXT, '
              'window_id TEXT, language TEXT)')
    c.execute('CREATE TABLE judgements (model TEXT, event TEXT, window_id TEXT, prompt TEXT, '
              'label TEXT, ts REAL)')
    c.executemany('INSERT INTO passages (event_id, work, window_id) VALUES (?,?,?)', [
        ('e1', 'libanius.orations_1-11', OLD + ':fine:444'),
        ('e2', 'libanius.orations', 'libanius.orations:fine:2340'),
        ('e3', 'other.work', 'other.work:fine:1')])
    c.executemany('INSERT INTO judgements (model, event, window_id) VALUES (?,?,?)', [
        ('m', 'e1', OLD + ':fine:444'), ('m', 'e3', 'other.work:fine:1')])
    c.commit()
    c.close()


def run(root, *extra):
    return subprocess.run([sys.executable, SCRIPT, '--root', str(root), '--rename', OLD, NEW, *extra],
                          capture_output=True, text=True, check=False)


def q(root, rel, sql):
    c = sqlite3.connect(os.path.join(root, rel))
    out = c.execute(sql).fetchall()
    c.close()
    return out


def snap(root):
    out = {}
    for d, _x, fs in os.walk(root):
        for f in fs:
            with open(os.path.join(d, f), 'rb') as fh:
                out[os.path.join(d, f)] = fh.read()
    return out


def test_dry_run_writes_nothing(tmp_path):
    build(str(tmp_path))
    before = snap(str(tmp_path))
    r = run(tmp_path)
    assert r.returncode == 0, r.stderr
    assert snap(str(tmp_path)) == before
    assert 'nothing written' in r.stdout and 'judgements (window id)' in r.stdout


def test_apply_renames_both_stores(tmp_path):
    root = str(tmp_path)
    build(root)
    r = run(tmp_path, '--apply')
    assert r.returncode == 0, r.stderr
    ev = 'data/events/event_dossiers.sqlite'
    assert q(root, ev, 'select work, window_id from passages order by event_id') == [
        (NEW, NEW + ':fine:444'), ('libanius.orations', 'libanius.orations:fine:2340'),
        ('other.work', 'other.work:fine:1')]
    assert q(root, ev, 'select window_id from judgements order by event') == [
        (NEW + ':fine:444',), ('other.work:fine:1',)]
    ru = 'cache/reuse_pairs/grc.db'
    assert q(root, ru, 'select work_a, work_b from pairs') == [
        (NEW, 'other.work'), ('other.work', NEW), ('other.work', 'other.work2')]
    assert sorted(x[0] for x in q(root, ru, 'select work from line_counts')) == sorted(
        [NEW, 'other.work'])
    assert any('.bak-stalework-' in n for n in os.listdir(os.path.join(root, 'cache', 'reuse_pairs')))
    assert any('.bak-stalework-' in n for n in os.listdir(os.path.join(root, 'data', 'events')))
    # a second run finds the new id already in use and refuses
    assert run(tmp_path, '--apply').returncode == 2


def test_refuses_when_new_id_has_rows(tmp_path):
    build(str(tmp_path), new_rows=True)
    before = snap(str(tmp_path))
    r = run(tmp_path, '--apply')
    assert r.returncode == 2 and 'REFUSING' in r.stderr
    assert snap(str(tmp_path)) == before
