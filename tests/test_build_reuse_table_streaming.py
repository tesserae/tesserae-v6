"""scripts/reuse/build_reuse_table.py reads one lemma cache at a time and
accepts --root (2026-10-18).

The Greek build held every lemma cache in one dictionary (5.7 GB of JSON on
disk) and sat at 12.2 GB resident on 2026-10-17. These tests build a small
corpus of tiny texts with caches under a temporary root and check that the
streamed build gives the same lines, postings, commonplace set and pairs as
the old all-at-once path, which is rebuilt here by hand, and that --root
reads from the root it is given.
"""
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'reuse'))

import build_reuse_table as brt  # noqa: E402
from backend import lemma_cache  # noqa: E402

WORKS = {
    'vergil.aeneid': [
        ('aen. 1.1', ['arma', 'uirumque', 'cano', 'troiae', 'qui', 'primus', 'ab', 'oris'],
         ['arma', 'uirumque', 'cano', 'troia', 'qui', 'primus', 'ab', 'ora']),
        ('aen. 1.2', ['italiam', 'fato', 'profugus', 'laviniaque', 'venit', 'litora'], None),
    ],
    'ovid.tristia': [
        ('trist. 2.1', ['arma', 'uirumque', 'cano', 'troiae', 'qui', 'primus', 'ab', 'oris'], None),
        ('trist. 2.2', ['nihil', 'hic', 'simile', 'omnino', 'est', 'ceterum'], None),
    ],
    'cicero.brutus': [
        ('brut. 1', ['et', 'in', 'ista', 'res', 'alia'], None),
        ('brut. 2', ['et', 'in', 'ista', 'res', 'alia'], None),
        ('brut. 3', ['ab'], None),
    ],
    'lucan.bellum_civile.part.1': [
        ('luc. 1.1', ['italiam', 'fato', 'profugus', 'laviniaque', 'venit', 'litora'], None),
    ],
    'lucan.bellum_civile': [
        ('luc. 1.1', ['italiam', 'fato', 'profugus', 'laviniaque', 'venit', 'litora'], None),
    ],
    'nocache.work': [
        ('nc. 1', ['quae', 'cumque', 'scribit', 'nemo', 'legit'], None),
    ],
}


def _make_root(root, with_cache=True):
    texts = os.path.join(root, 'texts', 'la')
    os.makedirs(texts)
    os.makedirs(os.path.join(root, 'cache', 'lemmas', 'la'))
    for work, lines in WORKS.items():
        with open(os.path.join(texts, work + '.tess'), 'w', encoding='utf-8') as f:
            for ref, toks, _ in lines:
                f.write(f'<{ref}>\t{" ".join(toks)}\n')


def _fill_caches(root, skip=('nocache.work',)):
    for work, lines in WORKS.items():
        if work in skip:
            continue
        path = os.path.join(root, 'texts', 'la', work + '.tess')
        units = []
        for ref, toks, lems in lines:
            u = {'ref': ref, 'tokens': toks, 'text': ' '.join(toks)}
            if lems:
                u['lemmas'] = lems
            units.append(u)
        assert lemma_cache.save_cached_units(work + '.tess', 'la', units, [], lemma_cache.get_file_hash(path))


@pytest.fixture
def root(tmp_path, monkeypatch):
    # restore the module-level directories after set_root() changes them
    for mod, names in ((brt, ('TEXTS_DIR', 'CACHE_DIR', 'INDEX_DIR')),
                       (lemma_cache, ('TEXTS_DIR', 'CACHE_DIR'))):
        for n in names:
            monkeypatch.setattr(mod, n, getattr(mod, n))
    r = str(tmp_path / 'checkout')
    os.makedirs(r)
    _make_root(r)
    brt.set_root(r)
    _fill_caches(r)
    return r


def _old_all_at_once(root):
    """The old loader, in the test only: every cache in one dict."""
    kept = {}
    surviving, _ = brt.list_corpus_files('la')
    for fname in surviving:
        c = lemma_cache.get_cached_units(fname, 'la')
        if c is not None:
            kept[fname] = c
    return kept


def _old_commonplace(cache_data, ratio=0.08, language='la'):
    """The old in-memory second pass of build_index, copied as it was."""
    from collections import defaultdict
    lemma_df = defaultdict(int)
    for data in cache_data.values():
        for unit in data.get('units_line', []):
            for lem in set(brt._line_lemmas(unit)):
                lemma_df[lem] += 1
    thr = (max(lemma_df.values()) if lemma_df else 0) * ratio
    stop = brt._stopset_for(language)
    out = set()
    for data in cache_data.values():
        for unit in data.get('units_line', []):
            tokens = unit.get('tokens') or []
            if len(tokens) < 3:
                continue
            lemmas = brt._line_lemmas(unit)
            for idxs in brt.gen_ngram_indices(len(tokens)):
                lg = tuple(lemmas[i] for i in idxs)
                tg = tuple(tokens[i] for i in idxs)
                if all(lemma_df.get(lm, 0) >= thr or brt._fold(lm) in stop or brt._fold(t) in stop
                       for lm, t in zip(lg, tg)):
                    out.add(brt.hash_ngram(tg))
    return out


def _dump(db_path):
    conn = sqlite3.connect(db_path)
    lines = conn.execute("SELECT line_id, work, line_ref, token_count, seq_in_work FROM lines "
                         "ORDER BY line_id").fetchall()
    post = conn.execute("SELECT ngram_hash, line_id FROM postings ORDER BY ngram_hash, line_id").fetchall()
    conn.close()
    return lines, post


def test_streamed_index_matches_the_all_at_once_path(root, tmp_path):
    surviving, skipped, loader = brt.stream_corpus('la')
    assert 'lucan.bellum_civile.part.1.tess' in skipped
    streamed_db = str(tmp_path / 's.db')
    s_stats, s_common = brt.build_index(loader, streamed_db, 200, language='la')
    assert loader.missing_cache == ['nocache.work.tess']

    old = _old_all_at_once(root)
    old_db = str(tmp_path / 'o.db')
    o_stats, o_common = brt.build_index(old, old_db, 200, language='la')

    assert _dump(streamed_db) == _dump(old_db)
    assert s_common == o_common == _old_commonplace(old)
    for k in ('works_indexed', 'lines_indexed', 'lines_under_3_tokens', 'distinct_ngrams_total',
              'ngrams_kept', 'postings_written', 'distinct_lemmas', 'commonplace_ngrams'):
        assert s_stats[k] == o_stats[k], k
    # the temporary token table must not survive into the index
    conn = sqlite3.connect(streamed_db)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert 'line_tok' not in names


def test_streamed_pairs_match_the_all_at_once_path(root, tmp_path):
    surviving, _, loader = brt.stream_corpus('la')
    s_db = str(tmp_path / 's.db')
    _, s_common = brt.build_index(loader, s_db, 200, language='la')
    s_pairs, s_other, _ = brt.find_pairs(s_db, 2, 0.15, 4, 0.5, 20, 0.06, s_common, drop_all_commonplace=False)

    old = _old_all_at_once(root)
    o_db = str(tmp_path / 'o.db')
    _, o_common = brt.build_index(old, o_db, 200, language='la')
    o_pairs, o_other, _ = brt.find_pairs(o_db, 2, 0.15, 4, 0.5, 20, 0.06, o_common, drop_all_commonplace=False)

    assert s_pairs == o_pairs
    assert s_pairs, "the fixture must produce at least one pair"
    works = {(p[0], p[3]) for p in s_pairs}
    assert ('ovid.tristia', 'vergil.aeneid') in works
    # a part file whose base exists is not read, so Lucan appears once
    assert not any('part' in w for pair in works for w in pair)
    assert dict(s_other) == dict(o_other)


def test_main_with_root_reads_the_given_root_and_writes_where_told(root, tmp_path, monkeypatch, capsys):
    out_db = str(tmp_path / 'out' / 'la.db')
    stats_out = str(tmp_path / 'out' / 'la_stats.json')
    os.makedirs(os.path.dirname(out_db))
    monkeypatch.setattr(sys, 'argv', ['build_reuse_table.py', '--language', 'la', '--root', root,
                                      '--out-db', out_db, '--stats-out', stats_out])
    brt.main()
    printed = capsys.readouterr().out
    assert 'RSS at' in printed
    assert 'nocache.work.tess' in printed

    stats = json.load(open(stats_out))
    assert stats['works_indexed'] == 4          # vergil, ovid, cicero, lucan (base)
    assert stats['skipped_missing_cache'] == 1
    assert stats['skipped_part_files'] == 1
    conn = sqlite3.connect(out_db)
    works = {r[0] for r in conn.execute("SELECT work_a FROM pairs UNION SELECT work_b FROM pairs")}
    meta = dict(conn.execute("SELECT key, value FROM meta"))
    conn.close()
    assert {'vergil.aeneid', 'ovid.tristia'} <= works
    assert meta['corpus_file_count'] == '4'
    # the script's own checkout was not written to
    assert brt.TEXTS_DIR == os.path.join(root, 'texts')
    assert brt.CACHE_DIR == os.path.join(root, 'cache', 'lemmas')
    assert lemma_cache.CACHE_DIR == os.path.join(root, 'cache', 'lemmas')


def test_root_with_a_stale_cache_counts_it_as_missing(root, tmp_path, monkeypatch):
    path = os.path.join(root, 'texts', 'la', 'cicero.brutus.tess')
    with open(path, 'a', encoding='utf-8') as f:
        f.write('<brut. 4>\tchanged after the cache was built\n')
    _, _, loader = brt.stream_corpus('la')
    brt.build_index(loader, str(tmp_path / 'x.db'), 200, language='la')
    assert 'cicero.brutus.tess' in loader.missing_cache
