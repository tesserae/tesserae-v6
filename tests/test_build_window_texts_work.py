"""build_window_texts.py --work rebuilds one work's rows and nothing else."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts'))
import build_window_texts as bwt  # noqa: E402


def _make(tmp_path):
    tree = tmp_path / 'texts' / 'fro'
    tree.mkdir(parents=True)
    (tree / 'w.a.tess').write_text(
        '<w.a.1.1>\tone\n<w.a.1.2>\ttwo\n<w.a.2.1>\tthree\n', encoding='utf-8')
    db = tmp_path / 'wt.db'
    c = sqlite3.connect(db)
    c.execute('CREATE TABLE window_texts (id TEXT PRIMARY KEY, language TEXT, work TEXT, '
              'ref_start TEXT, ref_end TEXT, text TEXT)')
    c.execute('CREATE TABLE lines (work TEXT, ord INTEGER, ref TEXT, text TEXT)')
    c.execute("INSERT INTO window_texts VALUES ('other:1','la','other','x.1','x.2','keep me')")
    c.execute("INSERT INTO lines VALUES ('other',0,'x.1','keep me')")
    c.commit()
    c.close()
    desc = tmp_path / 'descriptions.jsonl'
    rows = [{'id': 'w.a:fine:0', 'language': 'fro', 'work': 'w.a',
             'ref_start': 'w.a.1.1', 'ref_end': 'w.a.1.2'},
            {'id': 'w.a:fine:1', 'language': 'fro', 'work': 'w.a',
             'ref_start': 'w.a.1.3', 'ref_end': 'w.a.2.1'}]
    desc.write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
    return tree.parent, db, desc


def test_rebuild_one_work(tmp_path, monkeypatch):
    trees, db, desc = _make(tmp_path)
    monkeypatch.setattr(bwt, 'TEXT_TREES', [str(trees)])
    monkeypatch.setattr(bwt, 'WINDOW_FILES', [])
    assert bwt.rebuild_work(str(db), 'w.a', str(desc), apply=True) == 0
    c = sqlite3.connect(db)
    got = dict(c.execute("SELECT id, text FROM window_texts WHERE work='w.a'"))
    assert got['w.a:fine:0'] == 'one\ntwo'
    # start 1.3 is absent: clamped to the lines that exist in the range
    assert got['w.a:fine:1'] == 'three'
    assert c.execute("SELECT text FROM window_texts WHERE id='other:1'").fetchone() == ('keep me',)
    assert c.execute("SELECT COUNT(*) FROM lines WHERE work='w.a'").fetchone() == (3,)
    assert c.execute("SELECT COUNT(*) FROM lines WHERE work='other'").fetchone() == (1,)


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    trees, db, desc = _make(tmp_path)
    monkeypatch.setattr(bwt, 'TEXT_TREES', [str(trees)])
    monkeypatch.setattr(bwt, 'WINDOW_FILES', [])
    bwt.rebuild_work(str(db), 'w.a', str(desc), apply=False)
    c = sqlite3.connect(db)
    assert c.execute("SELECT COUNT(*) FROM window_texts WHERE work='w.a'").fetchone() == (0,)
