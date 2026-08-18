"""Unit tests for the by-book distribution helper the agent charts use."""
from backend.blueprints.fusion import _by_book_counts


def test_by_book_counts_multi_and_single_book():
    results = [
        {'source': {'ref': 'verg. a. 11.22'}, 'target': {'ref': 'stat. theb. 12.808'}},
        {'source': {'ref': 'verg. a. 11.30'}, 'target': {'ref': 'stat. theb. 12.100'}},
        {'source': {'ref': 'verg. a. 2.5'},   'target': {'ref': 'stat. theb. 12.5'}},
        {'source': {'ref': 'sen. thy. 546'},  'target': {'ref': 'stat. theb. 12.9'}},
    ]
    bb = _by_book_counts(results)
    src = {d['book']: d['count'] for d in bb['source']}
    tgt = {d['book']: d['count'] for d in bb['target']}
    # book taken from the first ref number; a single-number ref falls in bucket 0
    assert src == {0: 1, 2: 1, 11: 2}
    assert tgt == {12: 4}
    # sorted by book ascending
    assert [d['book'] for d in bb['source']] == [0, 2, 11]


def test_by_book_counts_handles_missing_and_empty():
    assert _by_book_counts([]) == {'source': [], 'target': []}
    bb = _by_book_counts([{'source': None, 'target': {}}])
    assert bb == {'source': [{'book': 0, 'count': 1}],
                  'target': [{'book': 0, 'count': 1}]}
