"""rare_focus_filter: Reader verbal matches must be anchored by a
distinctive word, or share three or more words.

The behavior tests run against a small doc-freq table built here (df values
copied from the real Latin table), so they prove the logic on CI where the
production index is absent. A final test runs against the real table when it
exists, and skips otherwise.
"""
import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Real Latin doc frequencies (2026-08-30): max 767; quis and uarius are
# commonplaces, adfatibus is rare, arma/uir/cano all common.
DF = {'maximus_placeholder': 767, 'quis': 699, 'uarius': 481, 'ipse': 721,
      'adfatibus': 4, 'arma': 456, 'uir': 640, 'cano': 368, 'examen': 151}


@pytest.fixture()
def fake_table(tmp_path, monkeypatch):
    db = tmp_path / 'fake_index.db'
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE lemma_doc_freq (lemma TEXT PRIMARY KEY, df INT)')
    conn.executemany('INSERT INTO lemma_doc_freq VALUES (?, ?)', DF.items())
    conn.commit()
    conn.close()
    import backend.lexical_density as ld
    monkeypatch.setattr(ld, '_index_path', lambda lang: str(db))


def _rows(*lemma_sets):
    return [{'text': 't', 'matched_lemmas': sorted(s)} for s in lemma_sets]


def test_filter_logic(fake_table):
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


def test_rows_without_lemmas_are_kept(fake_table):
    from backend.app import rare_focus_filter
    kept, hidden, _ = rare_focus_filter([{'text': 'x'}], 'la')
    assert len(kept) == 1 and hidden == 0


def test_unknown_language_passes_through():
    from backend.app import rare_focus_filter
    results = _rows({'quis', 'uarius'})
    kept, hidden, commons = rare_focus_filter(results, 'zz')
    assert kept == results and hidden == 0 and commons == []


def test_against_real_latin_table():
    """Calibration guard: on a machine with the production index, the real
    table must agree with the fixture's expectations."""
    from backend.lexical_density import _index_path
    from backend.app import rare_focus_filter
    if not os.path.exists(_index_path('la')):
        pytest.skip('production Latin index not present (CI)')
    kept, hidden, commons = rare_focus_filter(
        _rows({'quis', 'uarius'}, {'quis', 'adfatibus'}), 'la')
    assert hidden == 1 and 'uarius' in commons
    assert [set(r['matched_lemmas']) for r in kept] == [{'quis', 'adfatibus'}]
