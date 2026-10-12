"""window_for_passage picks the prose piece holding a selected sentence (2026-10-11)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import passage_index as pi  # noqa: E402

TAC = 'tacitus.annales.part.1'
REF = 'Tac. Ann. 1.3'


def _rec(n, a, b, ref=REF, **extra):
    return dict({'id': f'{TAC}:prose:{n}', 'work': TAC, 'scale': 'prose', 'ref_start': ref,
                 'ref_end': ref, 'sub': n + 1, 'char_start': a, 'char_end': b}, **extra)


# One unit (1.3) cut into three pieces, then the next unit's one piece.
RECS = [
    _rec(0, 0, 600),
    _rec(1, 601, 1200),
    _rec(2, 1201, 1745),
    _rec(3, 0, 800, ref='Tac. Ann. 1.4'),
]


def _install(monkeypatch, records):
    monkeypatch.setattr(pi, '_records', records)
    monkeypatch.setattr(pi, '_by_work', {pi._norm_work(TAC): list(range(len(records)))})
    monkeypatch.setattr(pi, '_prose_works', {TAC})
    monkeypatch.setattr(pi, '_ensure_loaded', lambda: None)
    monkeypatch.setitem(pi._state, 'ok', True)


def test_no_offsets_gives_the_first_piece_as_before(monkeypatch):
    _install(monkeypatch, RECS)
    assert pi.window_for_passage(TAC, REF, REF) == f'{TAC}:prose:0'


def test_a_sentence_in_the_second_piece_gets_the_second_piece(monkeypatch):
    _install(monkeypatch, RECS)
    assert pi.window_for_passage(TAC, REF, REF, char_start=640, char_end=900) == f'{TAC}:prose:1'


def test_a_sentence_in_the_third_piece_gets_the_third_piece(monkeypatch):
    _install(monkeypatch, RECS)
    assert pi.window_for_passage(TAC, REF, REF, char_start=1500, char_end=1740) == f'{TAC}:prose:2'


def test_a_sentence_in_the_first_piece_gets_the_first_piece(monkeypatch):
    _install(monkeypatch, RECS)
    assert pi.window_for_passage(TAC, REF, REF, char_start=0, char_end=120) == f'{TAC}:prose:0'


def test_an_offset_beyond_every_piece_falls_back_to_the_first(monkeypatch):
    _install(monkeypatch, RECS)
    assert pi.window_for_passage(TAC, REF, REF, char_start=9000, char_end=9100) == f'{TAC}:prose:0'


def test_offsets_never_leave_the_unit(monkeypatch):
    _install(monkeypatch, RECS)
    # 1.4's single piece holds offset 100 too, but the selection is in 1.3
    assert pi.window_for_passage(TAC, REF, REF, char_start=100, char_end=200) == f'{TAC}:prose:0'
    assert pi.window_for_passage(TAC, 'Tac. Ann. 1.4', 'Tac. Ann. 1.4',
                                 char_start=100, char_end=200) == f'{TAC}:prose:3'


def test_a_merged_window_without_offsets_still_answers(monkeypatch):
    recs = [{'id': f'{TAC}:prosem:0', 'work': TAC, 'scale': 'prose', 'ref_start': REF,
             'ref_end': 'Tac. Ann. 1.4', 'units': 2}]
    _install(monkeypatch, recs)
    assert pi.window_for_passage(TAC, REF, REF, char_start=50, char_end=90) == f'{TAC}:prosem:0'
