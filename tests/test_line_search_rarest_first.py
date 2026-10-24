"""The rarest-first lemma lookup returns what the plain fetch returns.

A query holding a very common lemma (sum, et) used to read every posting of
that lemma. Now the locations are found from the other lemmas and the common
lemma is looked up on those lines only. These tests hold that to the plain
fetch (the same function on a caller-supplied connection, which never takes
the new route) on a small index built in the real schema, including the
order of the locations, the lemmas of each and every position list.
"""
import json
import os
import random
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import inverted_index as II  # noqa: E402

COMMON = {'sum': 0.55, 'svm': 0.06, 'et': 0.5, 'in': 0.4}
RARE = {'amor': 0.05, 'bellum': 0.05, 'cano': 0.06, 'dux': 0.04, 'uir': 0.05, 'vir': 0.03, 'zeta': 0.04}


def build_index(seed=3, texts=5, lines_per_text=120):
    rng = random.Random(seed)
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    conn.execute('CREATE TABLE texts (text_id INTEGER PRIMARY KEY, filename TEXT UNIQUE, author TEXT, title TEXT, line_count INTEGER)')
    conn.execute('CREATE TABLE postings (lemma TEXT, text_id INTEGER, ref TEXT, positions TEXT)')
    conn.execute('CREATE TABLE lines (text_id INTEGER, ref TEXT, content TEXT, lemmas TEXT, tokens TEXT, PRIMARY KEY (text_id, ref))')
    conn.execute('CREATE INDEX idx_lemma ON postings(lemma)')
    conn.execute('CREATE INDEX idx_text ON postings(text_id)')
    for t in range(1, texts + 1):
        conn.execute('INSERT INTO texts VALUES (?, ?, ?, ?, ?)', (t, f'a.w{t}.tess', 'a', f'w{t}', lines_per_text))
        for r in range(lines_per_text):
            ref = f'w{t} {r + 1}'
            lemmas = []
            for table in (COMMON, RARE):
                for lemma, p in table.items():
                    for _ in range(2):          # a word may occur twice in a line
                        if rng.random() < p / 1.5:
                            lemmas.append(lemma)
            rng.shuffle(lemmas)
            positions = {}
            for pos, lemma in enumerate(lemmas):
                positions.setdefault(lemma, []).append(pos)
            for lemma, plist in positions.items():
                conn.execute('INSERT INTO postings VALUES (?, ?, ?, ?)', (lemma, t, ref, json.dumps(plist)))
            conn.execute('INSERT INTO lines VALUES (?, ?, ?, ?, ?)', (t, ref, ' '.join(lemmas), json.dumps(lemmas), json.dumps(lemmas)))
    conn.commit()
    return conn


@pytest.fixture
def index(monkeypatch):
    conn = build_index()
    monkeypatch.setattr(II, 'COMMON_LEMMA_POSTINGS', 30)
    monkeypatch.setattr(II, 'COMMON_LEMMA_RATIO', 2)
    monkeypatch.setattr(II, "get_connection", lambda language: conn)
    II._DUP_REF_CACHE.clear()
    return conn


def plain(conn, lemmas, language, min_matches, fallback_forms=None):
    return II.lookup_lemmas(lemmas, language, fallback_forms=fallback_forms, conn=conn, min_matches=min_matches)


def fast(lemmas, language, min_matches, fallback_forms=None):
    return II.lookup_lemmas(lemmas, language, fallback_forms=fallback_forms, min_matches=min_matches, rarest_first=True)


def same(a, b):
    assert list(a) == list(b)                     # the same locations in the same order
    for key in a:
        assert a[key]['lemmas'] == b[key]['lemmas'], key
        assert a[key]['positions'] == b[key]['positions'], key
        assert list(a[key]['positions']) == list(b[key]['positions']), key


QUERIES = [
    (['amor', 'sum'], 2),
    (['sum', 'amor'], 2),
    (['sum', 'amor', 'bellum'], 2),
    (['sum', 'amor', 'bellum'], 3),
    (['sum', 'et', 'cano'], 2),
    (['sum', 'et', 'cano'], 3),
    (['et', 'bellum'], 2),
    (['sum', 'uir'], 2),
    (['sum', 'vir', 'dux'], 2),
    (['amor', 'bellum'], 2),
    (['amor', 'sum'], 1),
    (['sum', 'amor', 'bellum'], 1),
    (['sum'], 1),
    (['zeta', 'et'], 2),          # the common lemma sorts before the rare one: plain fetch
    (['in', 'sum', 'dux', 'zeta'], 3),
]


@pytest.mark.parametrize('lemmas,min_matches', QUERIES)
@pytest.mark.parametrize('language', ['la', 'grc'])
def test_rarest_first_equals_the_plain_fetch(index, lemmas, min_matches, language):
    same(fast(lemmas, language, min_matches), plain(index, lemmas, language, min_matches))


def test_the_new_route_is_taken_when_it_applies(index):
    canon = ['amor', 'sum']
    mapping = {}
    for orig in canon:
        mapping.setdefault(orig, [orig])
    for orig in canon:
        for v in (orig.replace('u', 'v'), orig.replace('v', 'u'), orig.replace('i', 'j'), orig.replace('j', 'i')):
            owners = mapping.setdefault(v, [])
            if orig not in owners:
                owners.append(orig)
    assert II._lookup_rarest_first(index, canon, mapping, 2) is not None
    # min_matches 1 is a plain listing and never takes it.
    assert II._lookup_rarest_first(index, canon, mapping, 1) is None


def test_two_spellings_of_the_common_lemma_keep_the_last_ones_positions(index):
    # A line holding both sum and svm: the plain fetch keeps svm's positions for the lemma sum.
    index.execute("UPDATE lines SET lemmas = ? WHERE text_id = 1 AND ref = 'w1 1'",
                  (json.dumps(['amor', 'sum', 'svm', 'sum']),))
    index.execute("DELETE FROM postings WHERE text_id = 1 AND ref = 'w1 1'")
    for lemma, plist in (('amor', [0]), ('sum', [1, 3]), ('svm', [2])):
        index.execute('INSERT INTO postings VALUES (?, 1, ?, ?)', (lemma, 'w1 1', json.dumps(plist)))
    got = fast(['amor', 'sum'], 'la', 2)
    same(got, plain(index, ['amor', 'sum'], 'la', 2))
    assert got[('a.w1.tess', 'w1 1')]['positions']['sum'] == [2]


def test_a_caller_supplied_connection_keeps_the_plain_fetch(index, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('the documents path must not take the rarest-first route')
    monkeypatch.setattr(II, '_lookup_rarest_first', refuse)
    assert plain(index, ['amor', 'sum'], 'la', 2)


def test_an_index_without_lines_falls_back_to_the_plain_fetch(index):
    index.execute('DROP TABLE lines')
    expected = plain(index, ['amor', 'sum'], 'la', 2)
    assert fast(['amor', 'sum'], 'la', 2) == expected


def test_find_co_occurring_lemmas_agrees(index):
    a = II.find_co_occurring_lemmas(['amor', 'bellum', 'sum'], 'la', min_matches=2, rarest_first=True)
    b = II.find_co_occurring_lemmas(['amor', 'bellum', 'sum'], 'la', min_matches=2, conn=index)
    assert [(f, r) for f, r, _, _ in a] == [(f, r) for f, r, _, _ in b]


def test_a_ref_held_by_two_lines_is_read_from_the_postings(index):
    # Text 2 holds the ref 'w2 5' on two lines. `lines` keeps the first; the postings of both
    # were written, and the plain fetch keeps the last row seen for each lemma.
    index.execute("UPDATE texts SET line_count = line_count + 1 WHERE text_id = 2")
    index.execute("UPDATE lines SET lemmas = ? WHERE text_id = 2 AND ref = 'w2 5'", (json.dumps(['dux', 'cano']),))
    index.execute("DELETE FROM postings WHERE text_id = 2 AND ref = 'w2 5'")
    for lemma, plist in (('dux', [0]), ('cano', [1])):                   # first line
        index.execute('INSERT INTO postings VALUES (?, 2, ?, ?)', (lemma, 'w2 5', json.dumps(plist)))
    for lemma, plist in (('amor', [0]), ('sum', [1, 2]), ('dux', [3])):  # second line, same ref
        index.execute('INSERT INTO postings VALUES (?, 2, ?, ?)', (lemma, 'w2 5', json.dumps(plist)))
    for lemmas, m in ((['amor', 'sum'], 2), (['dux', 'sum'], 2), (['sum', 'amor', 'dux'], 2),
                      (['sum', 'amor', 'cano'], 2), (['sum', 'amor', 'cano'], 3)):
        got = fast(lemmas, 'la', m)
        same(got, plain(index, lemmas, 'la', m))
    assert ('a.w2.tess', 'w2 5') in fast(['amor', 'sum'], 'la', 2)       # found only through the second line


def make_duplicate_ref(index):
    index.execute("UPDATE texts SET line_count = line_count + 1 WHERE text_id = 2")
    index.execute("UPDATE lines SET lemmas = ? WHERE text_id = 2 AND ref = 'w2 5'", (json.dumps(['dux']),))
    index.execute("DELETE FROM postings WHERE text_id = 2 AND ref = 'w2 5'")
    index.execute('INSERT INTO postings VALUES (?, 2, ?, ?)', ('dux', 'w2 5', json.dumps([0])))
    for lemma, plist in (('amor', [0]), ('sum', [1])):
        index.execute('INSERT INTO postings VALUES (?, 2, ?, ?)', (lemma, 'w2 5', json.dumps(plist)))


def test_the_postings_cost_guard_falls_back_to_the_plain_fetch(index, monkeypatch):
    make_duplicate_ref(index)
    canon = ['amor', 'sum']
    mapping = {'amor': ['amor'], 'sum': ['sum'], 'svm': ['sum']}
    monkeypatch.setattr(II, '_POSTINGS_PER_LINE', 1)
    assert II._lookup_rarest_first(index, canon, mapping, 2) is not None
    monkeypatch.setattr(II, '_POSTINGS_PER_LINE', 10 ** 6)
    assert II._lookup_rarest_first(index, canon, mapping, 2) is None
    same(fast(canon, 'la', 2), plain(index, canon, 'la', 2))


def test_duplicate_refs_are_named_from_the_postings(index):
    make_duplicate_ref(index)
    assert II._duplicate_refs(index, 2) == frozenset({'w2 5'})
    assert II._duplicate_refs(index, 1) == frozenset()


def test_a_candidate_line_missing_from_lines_falls_back_to_the_plain_fetch(index):
    first = index.execute("SELECT ref FROM postings WHERE lemma = 'amor' AND text_id = 3 LIMIT 1").fetchone()[0]
    index.execute("DELETE FROM lines WHERE text_id = 3 AND ref = ?", (first,))
    same(fast(['amor', 'sum'], 'la', 2), plain(index, ['amor', 'sum'], 'la', 2))


def test_the_route_is_opt_in(index, monkeypatch):
    def refuse(*a, **k):
        raise AssertionError('a caller that did not opt in must get the plain fetch')
    monkeypatch.setattr(II, '_lookup_rarest_first', refuse)
    got = II.lookup_lemmas(['amor', 'sum'], 'la', min_matches=2)
    same(got, plain(index, ['amor', 'sum'], 'la', 2))
    single = II.lookup_lemmas(['sum'], 'la', min_matches=1)
    assert not any(isinstance(v['positions'], II._LazyPositions) for v in single.values())
    assert II.find_co_occurring_lemmas(['amor', 'sum'], 'la', min_matches=2)
