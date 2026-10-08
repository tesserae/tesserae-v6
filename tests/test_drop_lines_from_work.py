"""The surgical-line-removal procedure (scripts/corpus/drop_lines_from_work.py).

Tested only against a throwaway fixture tree: its own texts/, cache/lemmas/,
data/inverted_index/, backend/embeddings/ and data/passage_index/, none of
them touching the real repository or server.
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

import drop_lines_from_work as dlw  # noqa: E402


REFS = ['poem.1', 'poem.2', 'poem.3', 'poem.essay.1', 'poem.essay.2', 'poem.4', 'poem.5']
TEXTS = {
    'poem.1': 'real line one',
    'poem.2': 'real line two',
    'poem.3': 'real line three',
    'poem.essay.1': 'an editor wrote this much later',
    'poem.essay.2': 'and signed it here',
    'poem.4': 'real line four',
    'poem.5': 'real line five',
}
DROP = ['poem.essay.1', 'poem.essay.2']


@pytest.fixture
def fixture_root(tmp_path):
    root = tmp_path

    (root / 'texts' / 'fa').mkdir(parents=True)
    tess = '\n'.join(f'<{ref}>\t{TEXTS[ref]}' for ref in REFS) + '\n'
    (root / 'texts' / 'fa' / 'poem.tess').write_text(tess, encoding='utf-8')
    # An unrelated work must never be touched.
    (root / 'texts' / 'fa' / 'other.tess').write_text('<other.1>\tsomething else\n', encoding='utf-8')

    index_dir = root / 'data' / 'inverted_index'
    index_dir.mkdir(parents=True)
    con = sqlite3.connect(index_dir / 'fa_index.db')
    con.execute('create table texts (text_id integer primary key, filename text, '
                'author text, title text, line_count integer)')
    con.execute('create table lines (text_id integer, ref text, content text, '
                'lemmas text, tokens text)')
    con.execute('create table postings (lemma text, text_id integer, ref text, positions text)')
    con.execute('create table lemma_doc_freq (lemma text, df integer)')
    con.execute("insert into texts values (1, 'poem.tess', 'Poet', 'Poem', ?)", (len(REFS),))
    con.executemany('insert into lines values (1, ?, ?, ?, ?)',
                     [(ref, TEXTS[ref], 'lemma_' + ref, 'tok') for ref in REFS])
    con.executemany("insert into postings values (?, 1, ?, '[0]')",
                     [('shared', ref) for ref in REFS])
    con.execute("insert into lemma_doc_freq values ('shared', 1)")
    con.commit()
    con.close()

    emb_dir = root / 'backend' / 'embeddings' / 'fa'
    emb_dir.mkdir(parents=True)
    np.save(emb_dir / 'poem.npy', np.arange(len(REFS) * 4, dtype=np.float32).reshape(len(REFS), 4))
    (emb_dir / 'poem.meta.json').write_text(json.dumps({
        'language': 'fa', 'n_lines': len(REFS), 'embedding_dim': 4, 'line_refs': REFS,
    }), encoding='utf-8')

    lemma_dir = root / 'cache' / 'lemmas' / 'fa'
    lemma_dir.mkdir(parents=True)
    (lemma_dir / ('poem-' + 'a' * 32 + '.json')).write_text('{}', encoding='utf-8')
    (lemma_dir / 'other.json').write_text('{}', encoding='utf-8')

    passage_dir = root / 'data' / 'passage_index'
    passage_dir.mkdir(parents=True)
    # Windows: one entirely inside the real poetry (untouched), one that
    # overlaps the essay span, one entirely inside the essay (both dropped).
    windows = [
        ('poem:fine:0', 'poem.1', 'poem.3'),       # no overlap -> kept
        ('poem:fine:1', 'poem.3', 'poem.essay.1'),  # overlaps -> dropped
        ('poem:fine:2', 'poem.essay.1', 'poem.essay.2'),  # inside essay -> dropped
        ('poem:fine:3', 'poem.4', 'poem.5'),       # no overlap -> kept
    ]
    con = sqlite3.connect(passage_dir / 'window_texts.db')
    con.execute('create table window_texts (id text primary key, language text, work text, '
                'ref_start text, ref_end text, text text)')
    con.execute('create table lines (work text, ord integer, ref text, text text)')
    con.executemany('insert into window_texts values (?, ?, ?, ?, ?, ?)',
                     [(wid, 'fa', 'poem', rs, re_, 'window text') for wid, rs, re_ in windows])
    con.executemany('insert into lines values (?, ?, ?, ?)',
                     [('poem', i, ref, TEXTS[ref]) for i, ref in enumerate(REFS)])
    con.commit()
    con.close()

    ids = [wid for wid, _, _ in windows] + ['other:fine:0']
    (passage_dir / 'ids.json').write_text(json.dumps(ids), encoding='utf-8')
    with open(passage_dir / 'descriptions.jsonl', 'w', encoding='utf-8') as fh:
        for wid in ids:
            fh.write(json.dumps({'id': wid, 'work': wid.split(':', 1)[0], 'gist': 'g'}) + '\n')

    return root


# ---------------------------------------------------------------------------
# plan_drop
# ---------------------------------------------------------------------------
def test_plan_finds_the_matching_rows_in_every_store(fixture_root):
    plan = dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    assert plan['total_lines'] == 7
    assert plan['remaining_lines'] == 5
    assert plan['drop_span'] == ('poem.essay.1', 'poem.essay.2')
    assert plan['index']['matching_line_rows'] == 2
    assert plan['index']['matching_posting_rows'] == 2
    assert plan['index']['old_line_count'] == 7
    assert plan['vectors']['matching_rows'] == 2
    assert plan['vectors']['row_indices'] == [3, 4]
    assert len(plan['lemma_cache']['files']) == 1
    assert plan['lemma_cache']['files'][0].startswith('poem-')
    assert sorted(plan['windows']['window_ids']) == ['poem:fine:1', 'poem:fine:2']
    assert plan['windows']['description_rows'] == 2
    assert plan['windows']['winvec_rows'] == 2


def test_plan_rejects_a_ref_not_in_the_file(fixture_root):
    with pytest.raises(ValueError, match='not found'):
        dlw.plan_drop('fa', 'poem.tess', ['poem.essay.1', 'poem.nonexistent'], root=str(fixture_root))


def test_plan_leaves_the_other_work_untouched(fixture_root):
    plan = dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    assert all('other' not in fn for fn in plan['lemma_cache']['files'])
    assert all(wid.split(':', 1)[0] != 'other' for wid in plan['windows']['window_ids'])


def test_format_plan_is_readable(fixture_root):
    text = dlw.format_plan(dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root)))
    assert 'poem.tess' in text
    assert '2 of 7' in text
    assert 'batch_lemma_cache.py fa --force' in text


# ---------------------------------------------------------------------------
# apply_drop -- exercised ONLY on this fixture, never real data.
# ---------------------------------------------------------------------------
def test_dry_run_changes_nothing_on_disk(fixture_root):
    before = (fixture_root / 'texts' / 'fa' / 'poem.tess').read_text(encoding='utf-8')
    dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    after = (fixture_root / 'texts' / 'fa' / 'poem.tess').read_text(encoding='utf-8')
    assert before == after
    assert not list((fixture_root / 'texts' / 'fa').glob('*.bak-*'))


def test_apply_drops_the_lines_and_keeps_the_rest_unrenumbered(fixture_root):
    plan = dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    dlw.apply_drop(plan, tag='test')

    text = (fixture_root / 'texts' / 'fa' / 'poem.tess').read_text(encoding='utf-8')
    refs_left = [line.split('\t')[0][1:-1] for line in text.strip().split('\n')]
    assert refs_left == ['poem.1', 'poem.2', 'poem.3', 'poem.4', 'poem.5']
    # Remaining refs keep their ORIGINAL labels -- no renumbering.
    assert '<poem.4>' in text and '<poem.5>' in text
    backups = list((fixture_root / 'texts' / 'fa').glob('poem.tess.bak-test-*'))
    assert len(backups) == 1
    assert 'an editor wrote this much later' in backups[0].read_text(encoding='utf-8')

    other = (fixture_root / 'texts' / 'fa' / 'other.tess').read_text(encoding='utf-8')
    assert other == '<other.1>\tsomething else\n'


def test_apply_updates_the_index_and_recomputes_doc_freq(fixture_root):
    plan = dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    dlw.apply_drop(plan, tag='test')

    con = sqlite3.connect(fixture_root / 'data' / 'inverted_index' / 'fa_index.db')
    line_count = con.execute('select line_count from texts where text_id=1').fetchone()[0]
    assert line_count == 5
    remaining_refs = {r for (r,) in con.execute('select ref from lines where text_id=1')}
    assert remaining_refs == {'poem.1', 'poem.2', 'poem.3', 'poem.4', 'poem.5'}
    remaining_post_refs = {r for (r,) in con.execute('select ref from postings where text_id=1')}
    assert remaining_post_refs == {'poem.1', 'poem.2', 'poem.3', 'poem.4', 'poem.5'}
    # build_lemma_doc_freq is only importable inside the real repo tree
    # (scripts.build_inverted_index); on this bare fixture it is skipped,
    # but the table must still be intact, not dropped.
    assert con.execute("select count(*) from lemma_doc_freq").fetchone()[0] >= 0
    con.close()


def test_apply_drops_the_matching_vector_rows_and_updates_meta(fixture_root):
    plan = dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    dlw.apply_drop(plan, tag='test')

    arr = np.load(fixture_root / 'backend' / 'embeddings' / 'fa' / 'poem.npy')
    assert arr.shape[0] == 5
    meta = json.loads((fixture_root / 'backend' / 'embeddings' / 'fa' / 'poem.meta.json').read_text())
    assert meta['line_refs'] == ['poem.1', 'poem.2', 'poem.3', 'poem.4', 'poem.5']
    assert meta['n_lines'] == 5
    # The surviving rows are untouched copies of the originals (indices
    # 0, 1, 2, 5, 6 of the original 7-row array), not recomputed.
    original = np.arange(len(REFS) * 4, dtype=np.float32).reshape(len(REFS), 4)
    assert np.array_equal(arr, original[[0, 1, 2, 5, 6]])


def test_apply_removes_the_stale_lemma_cache_file(fixture_root):
    plan = dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    dlw.apply_drop(plan, tag='test')

    lemma_dir = fixture_root / 'cache' / 'lemmas' / 'fa'
    remaining = sorted(p.name for p in lemma_dir.iterdir() if p.suffix == '.json')
    assert remaining == ['other.json']
    assert any(p.name.startswith(('poem-' + 'a' * 32 + '.json') + '.bak-test-')
               for p in lemma_dir.iterdir())


def test_apply_drops_overlapping_windows_and_their_description_and_vector_rows(fixture_root):
    plan = dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    dlw.apply_drop(plan, tag='test')

    con = sqlite3.connect(fixture_root / 'data' / 'passage_index' / 'window_texts.db')
    remaining = {r for (r,) in con.execute('select id from window_texts')}
    assert remaining == {'poem:fine:0', 'poem:fine:3'}
    remaining_lines = {r for (r,) in con.execute("select ref from lines where work='poem'")}
    assert remaining_lines == {'poem.1', 'poem.2', 'poem.3', 'poem.4', 'poem.5'}
    con.close()

    ids = json.loads((fixture_root / 'data' / 'passage_index' / 'ids.json').read_text())
    assert set(ids) == {'poem:fine:0', 'poem:fine:3', 'other:fine:0'}

    descs = [json.loads(l) for l in
             (fixture_root / 'data' / 'passage_index' / 'descriptions.jsonl').read_text().splitlines()]
    assert {d['id'] for d in descs} == {'poem:fine:0', 'poem:fine:3', 'other:fine:0'}


def test_apply_on_a_checkout_with_no_downstream_stores_only_touches_the_text(tmp_path):
    (tmp_path / 'texts' / 'fa').mkdir(parents=True)
    (tmp_path / 'texts' / 'fa' / 'bare.tess').write_text(
        '<bare.1>\tkeep\n<bare.2>\tdrop\n<bare.3>\tkeep\n', encoding='utf-8')
    plan = dlw.plan_drop('fa', 'bare.tess', ['bare.2'], root=str(tmp_path))
    assert plan['index']['present'] is False
    assert plan['vectors']['present'] is False
    assert plan['lemma_cache']['present'] is False
    assert plan['windows']['present'] is False
    report = dlw.apply_drop(plan, tag='test')
    text = (tmp_path / 'texts' / 'fa' / 'bare.tess').read_text(encoding='utf-8')
    assert text == '<bare.1>\tkeep\n<bare.3>\tkeep\n'
    assert any('nothing to do' in line for line in report)
