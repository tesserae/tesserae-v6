"""The faster Line Search pieces give the answers of the plain ones.

Each speed change in backend/blueprints/line_search.py, backend/inverted_index.py,
backend/univerbation.py, backend/utils.py and backend/metadata_cache.py leaves
the answer alone; these tests hold each one to a plain reference on inputs
built to be awkward. The recorded requests in scripts/review/line_search_requests.json
are the end-to-end proof (scripts/review/line_search_profile.py check).
"""
import json
import os
import random
import sqlite3
import time
import unicodedata

import pytest

from backend import inverted_index as II
from backend import metadata_cache
from backend import univerbation
from backend import utils
from backend.blueprints import line_search as LS


def brute_gap(lists):
    return min(abs(a - b) for i in range(len(lists)) for j in range(i + 1, len(lists))
               for a in lists[i] for b in lists[j])


def test_smallest_gap_between_lists_equals_comparing_every_pair():
    rng = random.Random(11)
    for _ in range(3000):
        k = rng.choice([2, 2, 2, 3, 4])
        lists = [sorted(rng.sample(range(0, 60), rng.randint(1, 8))) for _ in range(k)]
        assert LS._smallest_gap_between_lists(lists) == brute_gap(lists), lists
    assert LS._smallest_gap_between_lists([[5], [5]]) == 0
    assert LS._smallest_gap_between_lists([[1, 9], [5]]) == 4
    assert LS._smallest_gap_between_lists([[3, 3], [3]]) == 0


def test_candidate_within_distance_uses_the_text_limit_only_when_needed():
    calls = []
    limit = lambda: calls.append(1) or 4  # noqa: E731
    assert LS._candidate_within_distance('x.tess', {'a': [1], 'b': [1]}, 'la', limit) is True      # gap 0
    assert calls == []
    assert LS._candidate_within_distance('x.tess', {'a': [1], 'b': [30]}, 'la', lambda: 4) is False
    assert LS._candidate_within_distance('x.tess', {'a': [1], 'b': [4]}, 'la', lambda: 4) is True
    assert LS._candidate_within_distance('x.tess', {'a': [1]}, 'la') is True                      # one list


def make_index(rows):
    """An in-memory index: rows are (lemma, filename, ref, positions)."""
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE texts (text_id INTEGER PRIMARY KEY, filename TEXT)')
    conn.execute('CREATE TABLE postings (lemma TEXT, text_id INTEGER, ref TEXT, positions TEXT)')
    ids = {}
    for lemma, filename, ref, positions in rows:
        if filename not in ids:
            ids[filename] = len(ids) + 1
            conn.execute('INSERT INTO texts VALUES (?, ?)', (ids[filename], filename))
        conn.execute('INSERT INTO postings VALUES (?, ?, ?, ?)', (lemma, ids[filename], ref, json.dumps(positions)))
    conn.row_factory = sqlite3.Row
    return conn


def reference_lookup(conn, lemmas, language, fallback_forms=None):
    """lookup_lemmas as it stood: every location, positions read for each."""
    return II.lookup_lemmas(lemmas, language, fallback_forms=fallback_forms, conn=conn)


def test_lookup_with_min_matches_is_the_filtered_plain_lookup():
    rng = random.Random(5)
    rows = []
    for f in range(4):
        for ref in range(40):
            for lemma in ('arma', 'uir', 'cano', 'vir', 'et'):
                if rng.random() < 0.4:
                    rows.append((lemma, f'a.w{f}.tess', f'{f}.{ref}', sorted(rng.sample(range(30), rng.randint(1, 4)))))
    conn = make_index(rows)
    for lemmas, fb in ((['arma', 'uir'], None), (['arma', 'uir', 'cano'], None), (['uir'], None),
                       (['arma', 'uir', 'et'], {'uir': {'vir'}}), (['arma', 'cano'], {'arma': {'et'}})):
        plain = reference_lookup(conn, lemmas, 'la', fb)
        for m in (1, 2, 3):
            got = II.lookup_lemmas(lemmas, 'la', fallback_forms=fb, conn=conn, min_matches=m)
            want = {k: v for k, v in plain.items() if len(v['lemmas']) >= m}
            assert got == want
            assert list(got) == list(want)                                  # same order
            assert [sorted(v['positions']) for v in got.values()] == [sorted(v['positions']) for v in want.values()]
        found = II.find_co_occurring_lemmas(lemmas, 'la', min_matches=2, fallback_forms=fb, conn=conn)
        assert [(a, b, sorted(c), d) for a, b, c, d in found] == [
            (k[0], k[1], sorted(v['lemmas']), v['positions']) for k, v in plain.items() if len(v['lemmas']) >= 2]


def test_scan_json_equals_json_loads():
    for text in ('[]', '[1, 2, 3]', '[0,7]', ' [1]', '[1] ', '["a", "b\\u00e9"]', '{"a": [1.5, 2e3]}', '12', 'null',
                 '[1, 2', '[1,]'):
        try:
            want = json.loads(text)
        except ValueError:
            with pytest.raises(ValueError):
                II._scan_json(text)
            continue
        assert II._scan_json(text) == want
        assert type(II._scan_json(text)) is type(want)


def reference_exact_lines(raw, pattern):
    """The lines whose NFC text (after the tag) the pattern matches, found line by line."""
    out = []
    for i, line in enumerate(raw.split('\n')):
        line = line.strip()
        if not line or not line.startswith('<'):
            continue
        try:
            end_tag = line.index('>')
        except ValueError:
            continue
        text = line[end_tag + 1:].strip()
        if pattern.search(unicodedata.normalize('NFC', text)):
            out.append(i)
    return out


def test_exact_candidate_lines_keep_every_matching_line():
    files = [
        "<t. 1> Arma virumque cano\n<t. 2> arma\n\n<t. 3> virum arma virum\njunk virum line\n<t. 4> quo usque tandem\n",
        "<t. 1> arma\r\n<t. 2> virumque\r\n<t. 3>arma virumque\r\n",
        unicodedata.normalize('NFD', "<il. 1> μῆνιν ἄειδε θεὰ\n<il. 2> θεὰ θεὰ ἄνδρα\n<il. 3> Ἀχιλῆος θεὰ\n"),
        "<a. 1> ́arma virum\n<a. 2> x\n",
    ]
    queries = ['arma', 'arma virum', 'virum arma', 'quo usque', 'θεὰ', 'μῆνιν ἄειδε', 'ἄνδρα', 'zzz', 'θεὰ θεὰ',
               'Ἀχιλῆος θεὰ']
    for raw in files:
        for q in queries:
            pattern = utils.exact_phrase_pattern(q)
            wanted = LS._exact_candidate_lines(raw, LS._exact_prefilter_pattern(q))
            truth = reference_exact_lines(raw, pattern)
            if wanted is None:
                continue
            assert set(truth) <= set(wanted), (q, raw[:30])
            assert wanted == sorted(set(wanted))
    pattern = LS._exact_prefilter_pattern('a')
    assert LS._exact_prefilter_pattern('   ') is None
    assert LS._exact_candidate_lines('<t. 1> a\n', None) is None                       # no pattern: every line
    assert LS._exact_candidate_lines('<t. 1>\u0338 a\n<t. 2> b\n', pattern) is None     # tag joined to a mark: every line
    assert LS._exact_candidate_lines('<t. 1> a\n<t. 2> b\n', pattern) == [0]


def test_match_line_with_the_answers_worked_out_once_is_the_same():
    forward = {'quo': {'quousque'}, 'usque': {'quousque'}}
    sequences = {'quousque': ([{'quo', 'qui'}, {'usque'}], None)}
    query = {'quousque', 'tandem', 'quo', 'usque'}
    lines = [
        ([['quo'], ['usque'], ['tandem']], ['quo', 'usque', 'tandem']),
        ([['quousque'], ['tandem']], ['quousque', 'tandem']),
        ([['qui'], ['x'], ['usque']], ['qui', 'x', 'usque']),
        ([['tandem']], ['tandem']),
        ([], []),
    ]
    answers = univerbation.joined_answers(forward)
    for lemmas, tokens in lines:
        assert (univerbation.match_line(lemmas, tokens, query, forward, sequences)
                == univerbation.match_line(lemmas, tokens, query, forward, sequences, answers=answers))


def test_metadata_cache_follows_the_file_and_the_metadata_files(tmp_path, monkeypatch):
    f = tmp_path / 'ovid.metamorphoses.tess'
    f.write_text('<m. 1.1> in nova fert animus\n', encoding='utf-8')
    first = metadata_cache.get_text_metadata_cached(str(f))
    assert first == utils.get_text_metadata(str(f))
    first['title'] = 'changed by the caller'
    assert metadata_cache.get_text_metadata_cached(str(f))['title'] == utils.get_text_metadata(str(f))['title']
    # a replaced file is read again: a long-line text turns from poetry to prose
    f.write_text('<m. 1.1> ' + 'verbum ' * 60 + '\n', encoding='utf-8')
    os.utime(f, (time.time() + 5, time.time() + 5))
    assert (metadata_cache.get_text_metadata_cached(str(f))
            == utils.get_text_metadata(str(f)))
    # an edit to the overrides file changes the answer
    over = tmp_path / 'overrides.json'
    over.write_text(json.dumps({'ovid.metamorphoses.tess': {'display_work': 'First Name'}}), encoding='utf-8')
    monkeypatch.setattr(utils, 'OVERRIDES_PATH', str(over))
    monkeypatch.setattr(utils, '_overrides_cache', None)
    assert metadata_cache.get_text_metadata_cached(str(f))['work'] == 'First Name'
    over.write_text(json.dumps({'ovid.metamorphoses.tess': {'display_work': 'Second Name'}}), encoding='utf-8')
    os.utime(over, (time.time() + 9, time.time() + 9))
    assert metadata_cache.get_text_metadata_cached(str(f))['work'] == 'Second Name'
    assert metadata_cache.get_text_metadata_cached(str(tmp_path / 'missing.tess'))['author'] == utils.get_text_metadata(
        str(tmp_path / 'missing.tess'))['author']


def test_text_type_from_content_is_read_again_when_the_file_changes(tmp_path):
    f = tmp_path / 'x.y.tess'
    f.write_text('<a. 1> short line\n<a. 2> another short line\n', encoding='utf-8')
    assert utils._estimate_text_type_from_content(str(f)) == 'poetry'
    assert utils._estimate_text_type_from_content(str(f)) == 'poetry'
    f.write_text('<a. 1> ' + 'long ' * 60 + '\n<a. 2> ' + 'long ' * 60 + '\n', encoding='utf-8')
    os.utime(f, (time.time() + 5, time.time() + 5))
    assert utils._estimate_text_type_from_content(str(f)) == 'prose'
    assert utils._estimate_text_type_from_content_uncached(str(f)) == 'prose'
