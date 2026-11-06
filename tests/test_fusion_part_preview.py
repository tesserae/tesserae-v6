"""The preview shown while a large comparison runs in parts (2026-10-27).

A running list of the best rows must give the same top rows as merging every
kept row again after each part, which is what the code did before."""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend import fusion  # noqa: E402


def _line(src_line, tgt_line, score):
    return {'source': {'ref': f'a. 1.{src_line}'}, 'target': {'ref': f'b. 2.{tgt_line}'},
            'fused_score': score}


def _window(src_line, tgt_line, score):
    return {'source': {'ref': f'a. 1.{src_line}-a. 1.{src_line + 1}'},
            'target': {'ref': f'b. 2.{tgt_line}-b. 2.{tgt_line + 1}'},
            'fused_score': score,
            'matched_words': [{'lemma': f'w{src_line}'}]}


def _parts(seed, n_parts=6, size=40):
    """Rows per part: lines and windows that share line pairs inside the part."""
    rng = random.Random(seed)
    parts = []
    for p in range(n_parts):
        base = p * size
        lines, windows = [], []
        for _ in range(60):
            lines.append(_line(base + rng.randrange(size - 1), rng.randrange(80),
                               round(rng.random(), 6)))
        for _ in range(40):
            windows.append(_window(base + rng.randrange(size - 1), rng.randrange(79),
                                   round(rng.random(), 6)))
        parts.append((lines, windows))
    return parts


def _full_merge(parts_so_far, mode, cap):
    lines = [r for ls, _ in parts_so_far for r in ls]
    windows = [dict(r) for _, ws in parts_so_far for r in ws]
    return fusion._finish_levels(mode, fusion._by_score(lines),
                                 fusion._by_score(windows), ordered=True)[:cap]


def _ids(rows):
    return [(r['source']['ref'], r['target']['ref'], r['fused_score']) for r in rows]


def test_running_list_gives_the_top_rows_of_a_full_re_merge_after_every_part():
    for seed in range(5):
        parts = _parts(seed)
        preview = fusion._PartPreview('merged', 30, {})
        for i, (lines, windows) in enumerate(parts, 1):
            top, total = preview.add_part(lines, [dict(r) for r in windows])
            expected = _full_merge(parts[:i], 'merged', 30)
            assert _ids(top) == _ids(expected), (seed, i)
            assert len(top) <= 30


def test_the_running_list_never_grows_past_the_cap():
    preview = fusion._PartPreview('merged', 10, {})
    for lines, windows in _parts(9, n_parts=8):
        top, _total = preview.add_part(lines, windows)
        assert len(preview.best) <= 10 and len(top) <= 10


def test_line_mode_and_the_formula_filter():
    parts = _parts(3, n_parts=3)
    for lines, _w in parts:
        for i, r in enumerate(lines):
            r['formula_count'] = i % 4
    preview = fusion._PartPreview('line', 25, {'formula_max': 1})
    for lines, _w in parts:
        top, total = preview.add_part(lines, None)
    every = [r for ls, _ in parts for r in ls if r['formula_count'] <= 1]
    assert total == len(every)
    assert _ids(top) == _ids(fusion._by_score(every)[:25])


def test_part_rows_are_not_changed_by_the_preview():
    lines, windows = _parts(1, n_parts=1)[0]
    before = [dict(r) for r in windows]
    fusion._PartPreview('merged', 10, {}).add_part(lines, windows)
    assert windows == before


def test_a_finished_channel_is_collected_at_once_not_after_the_poll_interval(monkeypatch):
    import time
    monkeypatch.setattr(fusion, 'HEARTBEAT_INTERVAL', 5)
    monkeypatch.setattr(fusion, 'run_channel', lambda *a, **k: [{'score': 1}])
    t = time.perf_counter()
    events = list(fusion._run_channel_with_heartbeat(
        'lemma', {}, [], [], None, None, 's', 't', None, None, 'la', 'la', None))
    assert time.perf_counter() - t < 1
    assert events == [('result', [{'score': 1}])]


def test_a_slow_channel_still_sends_heartbeats(monkeypatch):
    import time
    monkeypatch.setattr(fusion, 'HEARTBEAT_INTERVAL', 0.05)

    def slow(*a, **k):
        time.sleep(0.3)
        return ['done']
    monkeypatch.setattr(fusion, 'run_channel', slow)
    events = list(fusion._run_channel_with_heartbeat(
        'lemma', {}, [], [], None, None, 's', 't', None, None, 'la', 'la', None))
    assert events[-1] == ('result', ['done'])
    assert sum(1 for e in events if e[0] == 'heartbeat') >= 3
