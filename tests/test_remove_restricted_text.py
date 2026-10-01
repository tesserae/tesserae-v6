"""The removal procedure for a text whose licence has ended
(scripts/corpus/remove_restricted_text.py).

This has never been run against real data -- no PHI text exists yet. Tested
here only against a throwaway fixture tree: its own texts/, cache/lemmas/,
data/inverted_index/, data/passage_index/ and data/restricted_texts.json,
none of them touching the real repository or server.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'scripts', 'corpus'))

import numpy as np
import pytest  # noqa: E402

import remove_restricted_text as rrt  # noqa: E402


@pytest.fixture
def fixture_root(tmp_path):
    root = tmp_path

    (root / 'data').mkdir()
    (root / 'data' / 'restricted_texts.json').write_text(json.dumps({
        '_comment': 'fixture',
        'texts': {
            'heldwork.history': {
                'holder': 'Test Licence Holder',
                'credit': 'Source: Test Licence Holder (example.invalid)',
                'license': 'indexing and search only; no redistribution',
                'added': '2026-10-01',
                'ends': None,
            }
        },
    }))

    (root / 'texts' / 'la').mkdir(parents=True)
    (root / 'texts' / 'la' / 'heldwork.history.part.1.tess').write_text(
        '<heldwork.history.part.1 1> line one </heldwork.history.part.1 1>\n')
    (root / 'texts' / 'la' / 'heldwork.history.part.2.tess').write_text(
        '<heldwork.history.part.2 1> line two </heldwork.history.part.2 1>\n')
    (root / 'texts' / 'la' / 'ordinary.poem.tess').write_text(
        '<ordinary.poem 1> a line </ordinary.poem 1>\n')

    (root / 'cache' / 'lemmas' / 'la').mkdir(parents=True)
    (root / 'cache' / 'lemmas' / 'la' / 'heldwork.history.part.1.json').write_text('{}')
    (root / 'cache' / 'lemmas' / 'la' / 'heldwork.history.part.2.json').write_text('{}')
    (root / 'cache' / 'lemmas' / 'la' / 'ordinary.poem.json').write_text('{}')

    index_dir = root / 'data' / 'inverted_index'
    index_dir.mkdir()
    db_path = index_dir / 'la_index.db'
    con = sqlite3.connect(db_path)
    con.execute('create table texts (text_id integer primary key, filename text, line_count integer)')
    con.execute('create table lines (text_id integer, line_num integer)')
    con.execute('create table postings (text_id integer, lemma text)')
    con.executemany('insert into texts values (?, ?, ?)', [
        (1, 'heldwork.history.part.1.tess', 1),
        (2, 'heldwork.history.part.2.tess', 1),
        (3, 'ordinary.poem.tess', 1),
    ])
    con.executemany('insert into lines values (?, ?)', [(1, 1), (2, 1), (3, 1)])
    con.executemany('insert into postings values (?, ?)', [(1, 'lemma1'), (2, 'lemma2'), (3, 'lemma3')])
    con.commit()
    con.close()

    passage_dir = root / 'data' / 'passage_index'
    passage_dir.mkdir()
    ids = ['heldwork.history.part.1:fine:0', 'heldwork.history.part.2:fine:0', 'ordinary.poem:fine:0']
    (passage_dir / 'ids.json').write_text(json.dumps(ids))
    np.save(passage_dir / 'embeddings.npy', np.arange(12, dtype=np.float32).reshape(3, 4))
    with open(passage_dir / 'descriptions.jsonl', 'w', encoding='utf-8') as fh:
        for i, wid in enumerate(ids):
            work = wid.split(':', 1)[0]
            fh.write(json.dumps({'id': wid, 'work': work, 'desc': {'gist': f'gist {i}'}}) + '\n')

    return root


def test_plan_finds_every_file_and_row_for_the_work(fixture_root):
    plan = rrt.plan_removal('heldwork.history', str(fixture_root))
    assert plan['registry_entry']['holder'] == 'Test Licence Holder'
    assert sorted(fn for _, fn in plan['text_files']) == [
        'heldwork.history.part.1.tess', 'heldwork.history.part.2.tess']
    assert sorted(fn for _, fn in plan['lemma_cache_files']) == [
        'heldwork.history.part.1.json', 'heldwork.history.part.2.json']
    assert plan['index']['la']['present'] is True
    assert plan['index']['la']['line_count'] == 2
    assert len(plan['index']['la']['matching_text_ids']) == 2
    assert plan['passage_windows']['present'] is True
    assert plan['passage_windows']['window_count'] == 2


def test_plan_leaves_the_ordinary_work_untouched(fixture_root):
    plan = rrt.plan_removal('heldwork.history', str(fixture_root))
    assert not any(fn == 'ordinary.poem.tess' for _, fn in plan['text_files'])
    assert not any(fn == 'ordinary.poem.json' for _, fn in plan['lemma_cache_files'])


def test_plan_on_a_checkout_with_no_index_reports_absence_not_an_error(tmp_path):
    (tmp_path / 'data').mkdir()
    (tmp_path / 'data' / 'restricted_texts.json').write_text(json.dumps({'texts': {}}))
    plan = rrt.plan_removal('nope.work', str(tmp_path))
    assert plan['registry_entry'] is None
    assert plan['text_files'] == []
    assert plan['passage_windows']['present'] is False


def test_format_plan_is_readable(fixture_root):
    text = rrt.format_plan(rrt.plan_removal('heldwork.history', str(fixture_root)))
    assert 'heldwork.history' in text
    assert 'text files (2)' in text
    assert '2 window(s)' in text


# ---------------------------------------------------------------------------
# apply_removal: exercised ONLY on this fixture, never real data.
# ---------------------------------------------------------------------------
def test_apply_removes_only_the_restricted_work_everywhere(fixture_root):
    plan = rrt.plan_removal('heldwork.history', str(fixture_root))
    report = rrt.apply_removal(plan, tag='test')

    # Text files gone, backed up, ordinary text untouched.
    la_dir = fixture_root / 'texts' / 'la'
    remaining = sorted(p.name for p in la_dir.iterdir() if p.suffix == '.tess')
    assert remaining == ['ordinary.poem.tess']
    assert any(p.name.startswith('heldwork.history.part.1.tess.bak-test-')
               for p in la_dir.iterdir())

    # Lemma cache gone, ordinary one untouched.
    lemma_dir = fixture_root / 'cache' / 'lemmas' / 'la'
    remaining_json = sorted(p.name for p in lemma_dir.iterdir() if p.suffix == '.json')
    assert remaining_json == ['ordinary.poem.json']

    # Index rows gone for the restricted text_ids, kept for the ordinary one.
    con = sqlite3.connect(fixture_root / 'data' / 'inverted_index' / 'la_index.db')
    remaining_rows = con.execute('select text_id, filename from texts').fetchall()
    con.close()
    assert remaining_rows == [(3, 'ordinary.poem.tess')]

    # Passage windows gone for the restricted work, kept for the ordinary one.
    ids = json.load(open(fixture_root / 'data' / 'passage_index' / 'ids.json'))
    assert ids == ['ordinary.poem:fine:0']
    descs = [json.loads(l) for l in open(
        fixture_root / 'data' / 'passage_index' / 'descriptions.jsonl')]
    assert [d['id'] for d in descs] == ['ordinary.poem:fine:0']
    emb = np.load(fixture_root / 'data' / 'passage_index' / 'embeddings.npy')
    assert emb.shape[0] == 1

    # Registry entry gone.
    registry, _ = rrt.load_registry(str(fixture_root))
    assert 'heldwork.history' not in registry

    assert any('la_index.db' in line for line in report)
    assert any('passage index' in line for line in report)


def test_data_operations_lines_name_the_work_and_date(fixture_root):
    plan = rrt.plan_removal('heldwork.history', str(fixture_root))
    report = rrt.apply_removal(plan, tag='test')
    text = rrt.data_operations_lines(plan, report)
    assert 'heldwork.history' in text
    assert 'data/restricted_texts.json' in text
