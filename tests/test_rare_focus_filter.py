"""rare_focus_filter: Reader verbal matches must be anchored by a
distinctive word, or share three or more words."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _rows(*lemma_sets):
    return [{'text': 't', 'matched_lemmas': sorted(s)} for s in lemma_sets]


def test_filter_against_real_latin_table():
    from backend.app import rare_focus_filter
    results = _rows(
        {'quis', 'uarius'},                 # the Catullus commonplace: hide
        {'quis', 'adfatibus'},              # anchored by a rare word: keep
        {'arma', 'uir', 'cano'},            # three common words together: keep
        {'quis', 'ipse'},                   # two commonplaces: hide
    )
    kept, hidden, commons = rare_focus_filter(results, 'la')
    kept_sets = [set(r['matched_lemmas']) for r in kept]
    assert {'quis', 'adfatibus'} in kept_sets
    assert {'arma', 'cano', 'uir'} in kept_sets
    assert hidden == 2
    assert 'quis' in commons and 'uarius' in commons


def test_unknown_language_passes_through():
    from backend.app import rare_focus_filter
    results = _rows({'quis', 'uarius'})
    kept, hidden, commons = rare_focus_filter(results, 'zz')
    assert kept == results and hidden == 0 and commons == []


def test_rows_without_lemmas_are_kept():
    from backend.app import rare_focus_filter
    kept, hidden, _ = rare_focus_filter([{'text': 'x'}], 'la')
    assert len(kept) == 1 and hidden == 0
