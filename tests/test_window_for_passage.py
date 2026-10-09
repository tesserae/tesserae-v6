"""window_for_passage compares every reference coordinate and stays in the named book (2026-10-06)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import passage_index as pi  # noqa: E402


def _install(monkeypatch, records):
    by = {}
    for i, r in enumerate(records):
        by.setdefault(pi._norm_work(r['work']), []).append(i)
    monkeypatch.setattr(pi, '_records', records)
    monkeypatch.setattr(pi, '_by_work', by)
    monkeypatch.setattr(pi, '_ensure_loaded', lambda: None)
    monkeypatch.setitem(pi._state, 'ok', True)


RECS = [
    {'id': 'c.part.10:fine:0', 'work': 'curtius_rufus.historiae_alexandri_magni.part.10', 'scale': 'fine',
     'ref_start': 'curt. hist. 10.1.1', 'ref_end': 'curt. hist. 10.1.12'},
    {'id': 'c.part.3:fine:0', 'work': 'curtius_rufus.historiae_alexandri_magni.part.3', 'scale': 'fine',
     'ref_start': 'curt. hist. 3.1.1', 'ref_end': 'curt. hist. 3.1.12'},
    {'id': 'c.part.3:fine:1', 'work': 'curtius_rufus.historiae_alexandri_magni.part.3', 'scale': 'fine',
     'ref_start': 'curt. hist. 3.1.7', 'ref_end': 'curt. hist. 3.1.18'},
]


def test_book_three_selection_gets_book_three_window(monkeypatch):
    _install(monkeypatch, RECS)
    assert pi.window_for_passage('curtius_rufus.historiae_alexandri_magni.part.3',
                                 'curt. hist. 3.1.1', 'curt. hist. 3.1.4') == 'c.part.3:fine:0'


def test_whole_work_name_still_finds_the_right_book(monkeypatch):
    _install(monkeypatch, RECS)
    assert pi.window_for_passage('curtius_rufus.historiae_alexandri_magni',
                                 'curt. hist. 3.1.1', 'curt. hist. 3.1.4') == 'c.part.3:fine:0'
    assert pi.window_for_passage('curtius_rufus.historiae_alexandri_magni',
                                 'curt. hist. 10.1.3', 'curt. hist. 10.1.5') == 'c.part.10:fine:0'


def test_prefers_the_window_starting_at_or_just_before_the_selection(monkeypatch):
    _install(monkeypatch, RECS)
    assert pi.window_for_passage('curtius_rufus.historiae_alexandri_magni.part.3',
                                 'curt. hist. 3.1.9', 'curt. hist. 3.1.10') == 'c.part.3:fine:1'
