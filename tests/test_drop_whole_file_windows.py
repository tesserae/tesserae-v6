"""A work indexed twice, whole file and book files, keeps only the books.

scripts/corpus/drop_whole_file_windows.py removes the whole file's windows
from the passage index when every book file of the work has windows of its
own. These tests build a four-work index in a temporary directory and check
what goes, what stays, and that the three index files still agree row for
row afterwards.
"""
import json
import os
import sqlite3
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.corpus import drop_whole_file_windows as tool  # noqa: E402

# Four works:
#   vergil.aeneid        whole file AND two book files, all indexed -> whole goes
#   catullus.carmina     whole file AND book files, but part.85 on disk has no
#                        windows -> whole stays
#   lucan.bellum_civile  whole file only -> stays
#   ovid.tristia.part.1  book file only, no whole -> stays
IDS = [
    'vergil.aeneid:fine:0',
    'vergil.aeneid.part.1:fine:0',
    'vergil.aeneid:coarse:0',
    'vergil.aeneid.part.2:fine:0',
    'catullus.carmina:fine:0',
    'catullus.carmina.part.1:fine:0',
    'lucan.bellum_civile:fine:0',
    'ovid.tristia.part.1:fine:0',
]


@pytest.fixture
def index(tmp_path):
    idx = tmp_path / 'passage_index'
    idx.mkdir()
    json.dump(IDS, open(idx / 'ids.json', 'w'))
    # Row i holds the value i, so alignment can be checked after the drop.
    emb = np.arange(len(IDS), dtype='float16').reshape(-1, 1).repeat(4, axis=1)
    np.save(idx / 'embeddings.npy', emb)
    with open(idx / 'descriptions.jsonl', 'w') as fh:
        for wid in IDS:
            work, scale, _ = wid.split(':')
            fh.write(json.dumps({'id': wid, 'work': work, 'scale': scale,
                                 'ref_start': 'x 1', 'ref_end': 'x 2'}) + '\n')
    con = sqlite3.connect(idx / 'window_texts.db')
    con.execute('CREATE TABLE window_texts (id TEXT PRIMARY KEY, language TEXT, '
                'work TEXT, ref_start TEXT, ref_end TEXT, text TEXT)')
    con.execute('CREATE TABLE lines (work TEXT, ord INTEGER, ref TEXT, text TEXT)')
    for wid in IDS:
        con.execute('INSERT INTO window_texts VALUES (?, ?, ?, ?, ?, ?)',
                    (wid, 'la', wid.split(':')[0], 'x 1', 'x 2', 'arma virumque'))
    con.execute("INSERT INTO lines VALUES ('vergil.aeneid', 0, 'verg. aen. 1.1', 'arma')")
    con.commit()
    con.close()

    texts = tmp_path / 'texts' / 'la'
    texts.mkdir(parents=True)
    for name in ('vergil.aeneid', 'vergil.aeneid.part.1', 'vergil.aeneid.part.2',
                 'catullus.carmina', 'catullus.carmina.part.1',
                 'catullus.carmina.part.85', 'lucan.bellum_civile',
                 'ovid.tristia.part.1'):
        (texts / f'{name}.tess').write_text('<x 1>\tarma\n')
    return idx, tmp_path / 'texts'


def test_the_plan_drops_only_a_whole_work_whose_books_are_all_indexed(index):
    idx, texts = index
    drop, skipped = tool.plan(IDS, str(texts))
    assert drop == ['vergil.aeneid']
    assert skipped == {'catullus.carmina': ['catullus.carmina.part.85']}


def test_without_a_texts_root_nothing_is_verified(index):
    drop, skipped = tool.plan(IDS, None)
    assert drop == []
    assert set(skipped) == {'vergil.aeneid', 'catullus.carmina'}


def test_a_dry_run_writes_nothing(index, capsys):
    idx, texts = index
    before = sorted(os.listdir(idx))
    assert tool.main(['--index', str(idx), '--texts', str(texts)]) == 0
    assert sorted(os.listdir(idx)) == before
    assert json.load(open(idx / 'ids.json')) == IDS
    out = capsys.readouterr().out
    assert 'drop  vergil.aeneid' in out
    assert 'keep  catullus.carmina: catullus.carmina.part.85' in out


def test_applying_without_texts_is_refused(index):
    idx, _ = index
    assert tool.main(['--index', str(idx), '--apply']) == 2
    assert json.load(open(idx / 'ids.json')) == IDS


def test_apply_keeps_ids_embeddings_and_descriptions_in_step(index):
    idx, texts = index
    assert tool.main(['--index', str(idx), '--texts', str(texts), '--apply',
                      '--tag', 'test']) == 0
    ids = json.load(open(idx / 'ids.json'))
    assert ids == [i for i in IDS if not i.startswith('vergil.aeneid:')]
    emb = np.load(idx / 'embeddings.npy')
    assert emb.shape[0] == len(ids)
    # Each surviving row still carries its original value.
    assert [int(v) for v in emb[:, 0]] == [IDS.index(i) for i in ids]
    desc = [json.loads(l) for l in open(idx / 'descriptions.jsonl')]
    assert [d['id'] for d in desc] == ids
    con = sqlite3.connect(idx / 'window_texts.db')
    left = {r[0] for r in con.execute('SELECT id FROM window_texts')}
    assert left == set(ids)
    # The whole work's line rows are text, not windows, and stay.
    assert con.execute("SELECT COUNT(*) FROM lines WHERE work = 'vergil.aeneid'"
                       ).fetchone()[0] == 1
    con.close()
    backups = [f for f in os.listdir(idx) if '.bak-test-' in f]
    assert len(backups) == 4, backups


def test_allow_incomplete_drops_the_covering_whole_too(index):
    idx, texts = index
    assert tool.main(['--index', str(idx), '--texts', str(texts), '--apply',
                      '--allow-incomplete']) == 0
    ids = json.load(open(idx / 'ids.json'))
    assert 'catullus.carmina:fine:0' not in ids
    assert 'catullus.carmina.part.1:fine:0' in ids
    assert 'lucan.bellum_civile:fine:0' in ids
