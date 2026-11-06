"""The prepared-window lookup answers exactly as the full scan over a work's windows did (2026-10-27)."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import passage_index as pi  # noqa: E402
from backend.work_names import is_part, work_id  # noqa: E402


def _reference(work, ref_start, ref_end, prefer='fine', char_start=None):
    """The scan window_for_passage made before the table (kept here as the specification)."""
    wid_work = work_id(work)
    group = pi._by_work.get(pi._norm_work(work)) or []
    exact = [row for row in group if pi._records[row].get('work') == wid_work]
    rows = exact if (is_part(wid_work) and exact) else group
    if not rows:
        return None
    want = pi._ref_coords_in(work, ref_start) or ()
    want_end = pi._ref_coords_in(work, ref_end) or want
    best, best_key = None, None
    for row in rows:
        r = pi._records[row]
        want_scale = 'prose' if (prefer == 'fine' and r.get('work') in pi._prose_works) else prefer
        if want_scale and r.get('scale') != want_scale:
            continue
        lo = pi._ref_coords_in(r.get('work'), r.get('ref_start'))
        hi = pi._ref_coords_in(r.get('work'), r.get('ref_end'))
        if not (lo and hi):
            continue
        if not want:
            return r.get('id')
        n = min(len(lo), len(hi), len(want), len(want_end))
        lo, hi, wn, we = lo[:n], hi[:n], want[:n], want_end[:n]
        covers = lo <= wn <= hi or (wn <= lo <= we)
        if not covers:
            continue
        key = (0, tuple(-x for x in lo)) if lo <= wn else (1, lo)
        if char_start is not None:
            a, b = r.get('char_start'), r.get('char_end')
            holds = a is not None and b is not None and a <= char_start < b
            key = (0 if holds else 1,) + key
        if best_key is None or key < best_key:
            best, best_key = r.get('id'), key
    if best is None and prefer:
        return _reference(work, ref_start, ref_end, prefer=None, char_start=char_start)
    return best


def _records(rng):
    recs = []
    works = ['aaa.epic', 'bbb.prose', 'ccc.long.part.1', 'ccc.long.part.2', 'ddd.deep']
    for work in works:
        for i in range(rng.randint(30, 90)):
            depth = 3 if work == 'ddd.deep' else 2
            book = rng.randint(1, 6)
            line = rng.randint(1, 60)
            lo = [book, line] if depth == 2 else [book, rng.randint(1, 5), line]
            hi_book = book if rng.random() > 0.1 else book + rng.randint(1, 3)
            hi = [hi_book, line + rng.randint(0, 12)] if depth == 2 else [hi_book, lo[1], line + rng.randint(0, 12)]
            if rng.random() < 0.05:
                hi = [hi[0]]                      # a window whose end reference is shallower
            if rng.random() < 0.03:
                lo, hi = hi, lo                   # a malformed window with its ends reversed
            rec = {
                'id': f'{work}:{i}', 'work': work,
                'scale': rng.choice(['fine', 'fine', 'coarse', 'prose']),
                'ref_start': f'{work} ' + '.'.join(map(str, lo)),
                'ref_end': f'{work} ' + '.'.join(map(str, hi)),
            }
            if rng.random() < 0.3:
                a = rng.randint(0, 500)
                rec['char_start'], rec['char_end'] = a, a + rng.randint(1, 200)
            if rng.random() < 0.02:
                rec['ref_start'] = ''
            recs.append(rec)
    return recs


def _install(monkeypatch, records, prose=()):
    by = {}
    for i, r in enumerate(records):
        by.setdefault(pi._norm_work(r['work']), []).append(i)
    monkeypatch.setattr(pi, '_records', records)
    monkeypatch.setattr(pi, '_by_work', by)
    monkeypatch.setattr(pi, '_prose_works', set(prose))
    monkeypatch.setattr(pi, '_ensure_loaded', lambda: None)
    monkeypatch.setitem(pi._state, 'ok', True)


def test_table_lookup_equals_the_full_scan(monkeypatch):
    rng = random.Random(20261027)
    records = _records(rng)
    _install(monkeypatch, records, prose=['bbb.prose'])
    asked = 0
    for work in ['aaa.epic', 'bbb.prose', 'ccc.long', 'ccc.long.part.1', 'ccc.long.part.2',
                 'ddd.deep', 'la/aaa.epic.tess', 'missing.work']:
        for _ in range(400):
            depth = 3 if work == 'ddd.deep' else 2
            start = [rng.randint(0, 8) for _ in range(depth - 1)] + [rng.randint(0, 80)]
            end = list(start)
            end[-1] += rng.randint(0, 5)
            if rng.random() < 0.1:
                end = [end[0] + rng.randint(0, 3)] + end[1:]
            if rng.random() < 0.05:
                end = end[:1]
            prefer = rng.choice(['fine', 'fine', 'coarse', 'prose', None])
            char = rng.choice([None, None, rng.randint(0, 600)])
            ref_s = work + ' ' + '.'.join(map(str, start))
            ref_e = work + ' ' + '.'.join(map(str, end))
            if rng.random() < 0.03:
                ref_s = None
            expected = _reference(work, ref_s, ref_e, prefer, char)
            assert pi.window_for_passage(work, ref_s, ref_e, prefer=prefer, char_start=char) == expected, \
                (work, ref_s, ref_e, prefer, char)
            asked += 1
    assert asked > 3000


def test_a_new_index_is_not_answered_from_the_old_tables(monkeypatch):
    first = [{'id': 'w:0', 'work': 'w', 'scale': 'fine', 'ref_start': 'w 1.1', 'ref_end': 'w 1.9'}]
    _install(monkeypatch, first)
    assert pi.window_for_passage('w', 'w 1.3', 'w 1.3') == 'w:0'
    second = [{'id': 'w:new', 'work': 'w', 'scale': 'fine', 'ref_start': 'w 1.1', 'ref_end': 'w 1.9'}]
    _install(monkeypatch, second)
    assert pi.window_for_passage('w', 'w 1.3', 'w 1.3') == 'w:new'


def test_row_of_first_is_the_first_index(monkeypatch):
    monkeypatch.setattr(pi, '_ids', ['a', 'b', 'a', 'c'])
    assert pi.row_of_first('a') == 0
    assert pi.row_of_first('c') == 3
    assert pi.row_of_first('zzz') is None
    monkeypatch.setattr(pi, '_ids', ['c', 'a'])
    assert pi.row_of_first('a') == 1
