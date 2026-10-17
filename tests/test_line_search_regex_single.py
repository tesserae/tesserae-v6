"""A regex Line Search with one pattern lists its lines (2026-10-17).

The co-occurrence rule (two distinct matched words) used to drop every line of a
one-token regex, so a search for one name by pattern returned nothing. A pattern
without whitespace is a listing search as a single exact word is (issue #502). A
pattern with whitespace still asks for two matched words, and exact mode is untouched.
Runs the corpus scan over a small fixture folder."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.app  # noqa: E402,F401  (the application must be built first)
from backend.blueprints import line_search as A  # noqa: E402
from backend.line_search_params import _read_params  # noqa: E402

TEXT = """<livy.fixture 10.4.5> Rusellanum agrum Etrusci populabantur.
<livy.fixture 10.37.3> ad Rusellas Samnites ierunt, Rusellani fugerunt.
<livy.fixture 10.37.4> Samnites ad Perusiam ierunt.
"""


def _scan(tmp_path, monkeypatch, query, search_type):
    (tmp_path / 'livy.fixture.tess').write_text(TEXT, encoding='utf-8')
    monkeypatch.setattr(A, 'get_text_metadata', lambda p: {'author': 'Livy', 'title': 'Fixture'})
    monkeypatch.setattr('backend.distance_filter.passes_distance_filter', lambda *a, **k: True)
    with backend.app.app.test_request_context():
        params = _read_params({'query': query, 'language': 'la', 'search_type': search_type,
                               'max_results': 50})
        results, _ = A._scanned_candidates(params, str(tmp_path), {}, set(), set(), {}, {}, False)
    return results


def test_one_pattern_lists_every_line_it_matches(tmp_path, monkeypatch):
    out = _scan(tmp_path, monkeypatch, 'rusell(an|as)', 'regex')
    assert [r['locus'] for r in out] == ['10.4.5', '10.37.3']
    assert out[0]['matched_words'] == ['rusellan']
    assert out[1]['matched_words'] == ['rusellas', 'rusellan']


def test_a_pattern_with_a_space_still_wants_two_matched_words(tmp_path, monkeypatch):
    out = _scan(tmp_path, monkeypatch, 'rusellanum agrum', 'regex')
    assert [r['locus'] for r in out] == ['10.4.5']
    assert _scan(tmp_path, monkeypatch, 'rusellanum samnites', 'regex') == []


def test_exact_single_word_is_unchanged(tmp_path, monkeypatch):
    out = _scan(tmp_path, monkeypatch, 'Perusiam', 'exact')
    assert [r['locus'] for r in out] == ['10.37.4']
