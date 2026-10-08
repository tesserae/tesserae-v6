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

    # embeddings.npy: row i belongs to ids[i] (backend/passage_index.py's own
    # invariant). Distinct, recognisable values per row so a test can check
    # exactly which rows survived, not just how many.
    np.save(passage_dir / 'embeddings.npy',
            np.arange(len(ids) * 3, dtype=np.float16).reshape(len(ids), 3))

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
    assert 'rebuild in place' in text
    assert 'rebuild_bigrams.py fa' in text
    # Lemma cache is rebuilt by this script now, not left as a whole-
    # language follow-up command for the operator to run by hand.
    assert 'batch_lemma_cache.py fa --force' not in text


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


def test_apply_rebuilds_the_lemma_cache_instead_of_leaving_it_deleted(fixture_root):
    """The fixture's existing cache file lives under a made-up name (not
    the real hash of 'poem.tess'/'fa') -- exactly the "legacy, differently
    named" case rebuild_work_lemma_cache treats as superseded once the
    real canonical path has a fresh cache: backed up, then removed, never
    left as a permanent orphan and never left simply deleted for a lazy
    rebuild to maybe get around to."""
    plan = dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    report = dlw.apply_drop(plan, tag='test')
    assert not any(line.startswith(dlw.LEMMA_CACHE_BLOCKED_PREFIX) for line in report)

    lemma_dir = fixture_root / 'cache' / 'lemmas' / 'fa'
    canonical = dlw.get_cache_path('poem.tess', 'fa', cache_dir=str(fixture_root / 'cache' / 'lemmas'))
    remaining = sorted(p.name for p in lemma_dir.iterdir() if p.suffix == '.json')
    assert remaining == sorted(['other.json', os.path.basename(canonical)])

    # The old (fake-named) file is gone, but only after a backup.
    old_name = 'poem-' + 'a' * 32 + '.json'
    assert not (lemma_dir / old_name).exists()
    assert any(p.name.startswith(old_name + '.bak-test-') for p in lemma_dir.iterdir())

    # The freshly rebuilt cache, at the REAL hashed path, reflects the
    # file as it is AFTER the drop: the dropped refs are gone, everything
    # else survives, under its original ref label.
    cache = json.loads(open(canonical, encoding='utf-8').read())
    assert [u['ref'] for u in cache['units_line']] == ['poem.1', 'poem.2', 'poem.3', 'poem.4', 'poem.5']
    assert cache['file_hash'] == dlw.get_file_hash(str(fixture_root / 'texts' / 'fa' / 'poem.tess'))


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


def test_plan_reports_the_matching_embedding_rows(fixture_root):
    plan = dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    assert plan['windows']['emb_present'] is True
    assert plan['windows']['emb_old_rows'] == 5  # 4 windows + 'other:fine:0'


# ---------------------------------------------------------------------------
# Defect 1 (2026-10-08 production incident): embeddings.npy must drop the
# SAME rows as ids.json/descriptions.jsonl, or the passage index falls out
# of lockstep and refuses to load site-wide.
# ---------------------------------------------------------------------------
def test_apply_drops_the_matching_embeddings_rows_and_keeps_lockstep(fixture_root):
    orig_ids = json.loads((fixture_root / 'data' / 'passage_index' / 'ids.json').read_text())
    orig_emb = np.load(fixture_root / 'data' / 'passage_index' / 'embeddings.npy')

    plan = dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    dlw.apply_drop(plan, tag='test')

    ids = json.loads((fixture_root / 'data' / 'passage_index' / 'ids.json').read_text())
    emb = np.load(fixture_root / 'data' / 'passage_index' / 'embeddings.npy')
    descs = [json.loads(l) for l in
             (fixture_root / 'data' / 'passage_index' / 'descriptions.jsonl').read_text().splitlines()]

    # All three stores shrink together and stay aligned: embeddings.npy's
    # rows survive in the SAME order as ids.json, so row i still belongs
    # to ids[i] after the drop, not just before it.
    assert len(ids) == emb.shape[0] == len(descs) == 3
    keep_positions = [i for i, wid in enumerate(orig_ids) if wid in set(ids)]
    assert np.array_equal(emb, orig_emb[keep_positions])
    assert ids == [orig_ids[i] for i in keep_positions]

    backups = list((fixture_root / 'data' / 'passage_index').glob('embeddings.npy.bak-test-*'))
    assert len(backups) == 1
    assert np.array_equal(np.load(backups[0]), orig_emb)


def test_apply_drops_ids_and_descriptions_when_embeddings_npy_is_simply_absent(fixture_root):
    """A checkout with ids.json/descriptions.jsonl but no embeddings.npy at
    all (a partial fixture, or a build predating that store) must still
    drop the windows normally -- there is nothing to assert lockstep
    against, not a mismatch to refuse over."""
    os.remove(fixture_root / 'data' / 'passage_index' / 'embeddings.npy')

    plan = dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    assert plan['windows']['emb_present'] is False
    dlw.apply_drop(plan, tag='test')  # must not raise LockstepError

    ids = json.loads((fixture_root / 'data' / 'passage_index' / 'ids.json').read_text())
    assert set(ids) == {'poem:fine:0', 'poem:fine:3', 'other:fine:0'}
    assert not (fixture_root / 'data' / 'passage_index' / 'embeddings.npy').exists()


def test_apply_forced_embeddings_mismatch_aborts_and_restores_everything(fixture_root):
    """A pre-existing mismatch between embeddings.npy and ids.json (the
    exact shape of the 2026-10-08 incident, one step removed: here it is
    already wrong before the script runs) must stop the whole windows step
    cold, not write a single file -- including window_texts.db, which is
    otherwise edited first."""
    passage_dir = fixture_root / 'data' / 'passage_index'
    LIVE = ('window_texts.db', 'ids.json', 'descriptions.jsonl', 'embeddings.npy')
    before = {name: (passage_dir / name).read_bytes() for name in LIVE}

    # Corrupt embeddings.npy: one extra row no id names.
    bad = np.vstack([np.load(passage_dir / 'embeddings.npy'),
                      np.zeros((1, 3), dtype=np.float16)])
    np.save(passage_dir / 'embeddings.npy', bad)
    before['embeddings.npy'] = (passage_dir / 'embeddings.npy').read_bytes()

    plan = dlw.plan_drop('fa', 'poem.tess', DROP, root=str(fixture_root))
    with pytest.raises(dlw.LockstepError, match='out of lockstep'):
        dlw.apply_drop(plan, tag='test')

    # Every one of the four LIVE window stores is exactly as it was just
    # before apply_drop was called -- nothing was left half-changed (a
    # backup file appearing beside each is correct and expected; it is the
    # live files that must not move), and no stray .new/.tmp files remain.
    after = {name: (passage_dir / name).read_bytes() for name in LIVE}
    assert after == before
    assert not list(passage_dir.glob('*.new'))
    assert not list(passage_dir.glob('*.tmp-*'))


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


# ---------------------------------------------------------------------------
# Defect 2 (2026-10-08, caught before --apply on production's Ghalib
# footnotes): two SCATTERED refs (e.g. two footnotes far apart in the file)
# must drop only the windows that touch one of them, never every window
# between the first and the last dropped position -- that previously
# planned ~193 windows for two one-line footnotes.
# ---------------------------------------------------------------------------
SCATTERED_REFS = [f's.{n}' for n in range(1, 8)]  # s.1 .. s.7
SCATTERED_DROP = ['s.1', 's.7']  # far apart in file order (positions 0 and 6)


@pytest.fixture
def scattered_fixture_root(tmp_path):
    root = tmp_path
    (root / 'texts' / 'fa').mkdir(parents=True)
    tess = '\n'.join(f'<{ref}>\tline {ref}' for ref in SCATTERED_REFS) + '\n'
    (root / 'texts' / 'fa' / 'scattered.tess').write_text(tess, encoding='utf-8')

    passage_dir = root / 'data' / 'passage_index'
    passage_dir.mkdir(parents=True)
    windows = [
        ('scattered:fine:A', 's.1', 's.1'),  # touches the FIRST dropped ref -> dropped
        ('scattered:fine:B', 's.2', 's.6'),  # the whole middle, touches NEITHER -> kept
        ('scattered:fine:C', 's.7', 's.7'),  # touches the SECOND dropped ref -> dropped
    ]
    con = sqlite3.connect(passage_dir / 'window_texts.db')
    con.execute('create table window_texts (id text primary key, language text, work text, '
                'ref_start text, ref_end text, text text)')
    con.execute('create table lines (work text, ord integer, ref text, text text)')
    con.executemany('insert into window_texts values (?, ?, ?, ?, ?, ?)',
                     [(wid, 'fa', 'scattered', rs, re_, 'window text') for wid, rs, re_ in windows])
    con.commit()
    con.close()

    ids = [wid for wid, _, _ in windows]
    (passage_dir / 'ids.json').write_text(json.dumps(ids), encoding='utf-8')
    with open(passage_dir / 'descriptions.jsonl', 'w', encoding='utf-8') as fh:
        for wid in ids:
            fh.write(json.dumps({'id': wid, 'work': 'scattered', 'gist': 'g'}) + '\n')
    np.save(passage_dir / 'embeddings.npy',
            np.arange(len(ids) * 2, dtype=np.float16).reshape(len(ids), 2))

    return root


def test_plan_drops_only_windows_touching_scattered_refs_not_the_whole_span(scattered_fixture_root):
    plan = dlw.plan_drop('fa', 'scattered.tess', SCATTERED_DROP, root=str(scattered_fixture_root))
    # The buggy version used the span from the first dropped position (0)
    # to the last (6), which overlaps window B (positions 1..5) too, and
    # would have planned to drop all three windows instead of two.
    assert sorted(plan['windows']['window_ids']) == ['scattered:fine:A', 'scattered:fine:C']
    assert plan['windows']['description_rows'] == 2
    assert plan['windows']['winvec_rows'] == 2


def test_apply_drops_only_the_scattered_windows_that_touch_a_dropped_ref(scattered_fixture_root):
    plan = dlw.plan_drop('fa', 'scattered.tess', SCATTERED_DROP, root=str(scattered_fixture_root))
    dlw.apply_drop(plan, tag='test')

    ids = json.loads((scattered_fixture_root / 'data' / 'passage_index' / 'ids.json').read_text())
    assert ids == ['scattered:fine:B']
    emb = np.load(scattered_fixture_root / 'data' / 'passage_index' / 'embeddings.npy')
    assert emb.shape[0] == 1
    descs = [json.loads(l) for l in
             (scattered_fixture_root / 'data' / 'passage_index' / 'descriptions.jsonl')
             .read_text().splitlines()]
    assert [d['id'] for d in descs] == ['scattered:fine:B']

    con = sqlite3.connect(scattered_fixture_root / 'data' / 'passage_index' / 'window_texts.db')
    remaining = {r for (r,) in con.execute('select id from window_texts')}
    con.close()
    assert remaining == {'scattered:fine:B'}


def test_contiguous_runs_groups_adjacent_positions_and_splits_gaps():
    assert dlw._contiguous_runs([]) == []
    assert dlw._contiguous_runs([5]) == [(5, 5)]
    assert dlw._contiguous_runs([1, 2, 3]) == [(1, 3)]
    assert dlw._contiguous_runs([0, 6]) == [(0, 0), (6, 6)]
    assert dlw._contiguous_runs([1, 2, 5, 6, 9]) == [(1, 2), (5, 6), (9, 9)]


# ---------------------------------------------------------------------------
# rebuild_work_lemma_cache (2026-10-08 fix): the cache is rebuilt in place,
# not deleted -- its filename hashes the work's PATH-like text_id, not its
# content, so a plain delete left no way to tell, from the filesystem
# alone, whether the next request would ever rebuild it (it would -- but
# only lazily, and not at all for a language whose processor cannot even
# be imported where the delete happened, e.g. Urdu's Stanza pipeline,
# deliberately absent from production).
# ---------------------------------------------------------------------------
def test_rebuild_succeeds_and_the_cache_reflects_the_dropped_lines(tmp_path):
    (tmp_path / 'texts' / 'en').mkdir(parents=True)
    tess = ('<lemtest.1>\tone two three\n'
            '<lemtest.2>\tfour five six\n'
            '<lemtest.3>\tseven eight nine\n'
            '<lemtest.4>\tten eleven twelve\n')
    (tmp_path / 'texts' / 'en' / 'lemtest.tess').write_text(tess, encoding='utf-8')

    cache_lang_dir = tmp_path / 'cache' / 'lemmas' / 'en'
    cache_lang_dir.mkdir(parents=True)
    canonical = dlw.get_cache_path('lemtest.tess', 'en',
                                   cache_dir=str(tmp_path / 'cache' / 'lemmas'))
    # A stale cache already sitting at the REAL canonical path -- the
    # ordinary case, since that path never changes across the edit.
    with open(canonical, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps({'text_id': 'lemtest.tess', 'language': 'en',
                             'file_hash': 'stale-hash',
                             'units_line': [{'ref': 'STALE-UNIT'}], 'units_phrase': []}))
    # Plus a pre-hash-scheme legacy file under the old plain naming.
    legacy = cache_lang_dir / 'lemtest.json'
    legacy.write_text('{"legacy": true}', encoding='utf-8')

    plan = dlw.plan_drop('en', 'lemtest.tess', ['lemtest.2'], root=str(tmp_path))
    assert sorted(plan['lemma_cache']['files']) == sorted([os.path.basename(canonical), 'lemtest.json'])

    report = dlw.apply_drop(plan, tag='test')
    assert not any(line.startswith(dlw.LEMMA_CACHE_BLOCKED_PREFIX) for line in report)

    # The canonical file now holds a real rebuild: the dropped line is
    # gone, the other three keep their original ref labels, and the
    # stored file_hash matches the file AFTER the drop.
    new_cache = json.loads(open(canonical, encoding='utf-8').read())
    assert [u['ref'] for u in new_cache['units_line']] == ['lemtest.1', 'lemtest.3', 'lemtest.4']
    assert all(u['tokens'] for u in new_cache['units_line']), new_cache['units_line']
    assert new_cache['language'] == 'en'
    assert new_cache['file_hash'] == dlw.get_file_hash(str(tmp_path / 'texts' / 'en' / 'lemtest.tess'))

    # The canonical file's OWN prior (stale) content was backed up before
    # being overwritten -- it was overwritten in place, not renamed.
    canonical_backups = list(cache_lang_dir.glob(os.path.basename(canonical) + '.bak-test-*'))
    assert len(canonical_backups) == 1
    assert 'STALE-UNIT' in canonical_backups[0].read_text(encoding='utf-8')

    # The legacy file is superseded now that the canonical path has a
    # fresh cache: backed up, then removed, not left as permanent debris.
    assert not legacy.exists()
    legacy_backups = list(cache_lang_dir.glob('lemtest.json.bak-test-*'))
    assert len(legacy_backups) == 1
    assert '"legacy": true' in legacy_backups[0].read_text(encoding='utf-8')


def test_rebuild_blocked_by_import_error_leaves_the_old_cache_untouched(tmp_path, monkeypatch):
    (tmp_path / 'texts' / 'ur').mkdir(parents=True)
    tess = '<work.1>\tkeep one\n<work.2>\tdrop this\n<work.3>\tkeep two\n'
    (tmp_path / 'texts' / 'ur' / 'work.tess').write_text(tess, encoding='utf-8')

    cache_lang_dir = tmp_path / 'cache' / 'lemmas' / 'ur'
    cache_lang_dir.mkdir(parents=True)
    canonical = dlw.get_cache_path('work.tess', 'ur', cache_dir=str(tmp_path / 'cache' / 'lemmas'))
    old_content = json.dumps({'text_id': 'work.tess', 'language': 'ur',
                              'file_hash': 'old-hash', 'units_line': [], 'units_phrase': []})
    with open(canonical, 'w', encoding='utf-8') as fh:
        fh.write(old_content)

    class _NoStanzaProcessor:
        """Stands in for scripts.batch_lemma_cache.FastTextProcessor in an
        environment where Stanza (Urdu's analyser) is not installed --
        exactly backend/urdu/processor.py's `import stanza` failing deep
        inside tokenize_and_lemmatize, propagated unmodified."""
        def process_file(self, *a, **kw):
            raise ImportError("No module named 'stanza'")

    monkeypatch.setattr(dlw, '_get_lemma_rebuild_processor', lambda: _NoStanzaProcessor())

    plan = dlw.plan_drop('ur', 'work.tess', ['work.2'], root=str(tmp_path))
    report = dlw.apply_drop(plan, tag='test')

    blocked_lines = [line for line in report if line.startswith(dlw.LEMMA_CACHE_BLOCKED_PREFIX)]
    assert len(blocked_lines) == 1
    assert "No module named 'stanza'" in blocked_lines[0]
    assert 'scripts/batch_lemma_cache.py ur --force' in blocked_lines[0]

    # Nothing was deleted, backed up, or rewritten: the old cache is
    # bit-for-bit what it was before apply_drop ran.
    assert open(canonical, encoding='utf-8').read() == old_content
    assert not list(cache_lang_dir.glob('*.bak-*'))
    assert sorted(p.name for p in cache_lang_dir.iterdir()) == [os.path.basename(canonical)]

    # An unrelated store (the text itself) is not held hostage by the
    # lemma cache being blocked -- it has already been dropped.
    text = (tmp_path / 'texts' / 'ur' / 'work.tess').read_text(encoding='utf-8')
    assert text == '<work.1>\tkeep one\n<work.3>\tkeep two\n'


def test_main_exits_nonzero_when_the_lemma_cache_rebuild_is_blocked(tmp_path, monkeypatch, capsys):
    (tmp_path / 'texts' / 'ur').mkdir(parents=True)
    (tmp_path / 'texts' / 'ur' / 'work.tess').write_text(
        '<work.1>\tkeep\n<work.2>\tdrop\n<work.3>\tkeep\n', encoding='utf-8')
    (tmp_path / 'cache' / 'lemmas' / 'ur').mkdir(parents=True)
    canonical = dlw.get_cache_path('work.tess', 'ur', cache_dir=str(tmp_path / 'cache' / 'lemmas'))
    with open(canonical, 'w', encoding='utf-8') as fh:
        fh.write('{}')

    class _NoStanzaProcessor:
        def process_file(self, *a, **kw):
            raise ImportError("No module named 'stanza'")

    monkeypatch.setattr(dlw, '_get_lemma_rebuild_processor', lambda: _NoStanzaProcessor())
    monkeypatch.setattr(sys, 'argv', ['drop_lines_from_work.py', 'ur', 'work.tess',
                                      '--refs', 'work.2', '--apply', '--root', str(tmp_path)])

    with pytest.raises(SystemExit) as exc_info:
        dlw.main()
    assert exc_info.value.code != 0
    assert exc_info.value.code is not None

    out = capsys.readouterr().out
    assert dlw.LEMMA_CACHE_BLOCKED_PREFIX in out
    # Everything else still ran and was reported before the exit.
    assert 'text: rewrote' in out
