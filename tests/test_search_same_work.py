"""A work searched against itself (owner 2026-10-10: "One work phrase:
exclude identical lines"): no line is paired with itself and each pair of
lines appears once, so the list shows where the work repeats its own
phrases rather than every line beside its twin."""
from backend.blueprints import search as search_mod


def test_drop_self_pairs_keeps_each_pair_once_with_the_earlier_line_first():
    matches = [
        {'source_idx': 0, 'target_idx': 0, 'matched_lemmas': ['a']},
        {'source_idx': 0, 'target_idx': 5, 'matched_lemmas': ['a', 'b']},
        {'source_idx': 5, 'target_idx': 0, 'matched_lemmas': ['a', 'b']},
        {'source_idx': 3, 'target_idx': 3, 'matched_lemmas': ['c']},
        {'source_idx': 2, 'target_idx': 7, 'matched_lemmas': ['d', 'e']},
    ]
    out = search_mod._drop_self_pairs(matches)
    assert [(m['source_idx'], m['target_idx']) for m in out] == [(0, 5), (2, 7)]


def test_drop_self_pairs_leaves_rows_without_indexes_alone():
    rows = [{'score': 1}]
    assert search_mod._drop_self_pairs(rows) == rows
    assert search_mod._drop_self_pairs([]) == []
    assert search_mod._drop_self_pairs(None) == []


def test_parse_marks_a_work_against_itself(monkeypatch):
    monkeypatch.setattr(search_mod, '_resolve_with_fallback',
                        lambda texts_dir, language, text_id: (f'/x/{text_id}.tess', 'la'))
    monkeypatch.setattr(search_mod, '_texts_dir', '/x', raising=False)
    same = search_mod._parse_search_request(
        {'source': 'catullus.carmina', 'target': 'catullus.carmina', 'language': 'la'})
    assert same['settings'].get('same_work') is True

    other = search_mod._parse_search_request(
        {'source': 'catullus.carmina', 'target': 'vergil.aeneid', 'language': 'la'})
    assert 'same_work' not in other['settings']

    # The same work in two different units (line against phrase) is a real
    # comparison of two cuttings, so it is left alone.
    units = search_mod._parse_search_request(
        {'source': 'catullus.carmina', 'target': 'catullus.carmina', 'language': 'la',
         'settings': {'source_unit_type': 'line', 'target_unit_type': 'phrase'}})
    assert 'same_work' not in units['settings']
