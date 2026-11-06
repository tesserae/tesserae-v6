"""A work with one part under the four-line window minimum is not reported as missing windows.

scripts/corpus/verify_text_coverage.py exempted a short whole file but flagged a whole work whose
short part has no windows (hermas.pastor parts 6 and 20 have 2 and 3 lines). The fixture work here
has three parts, one of them two lines long.
"""
import importlib.util
import os

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'scripts', 'corpus', 'verify_text_coverage.py')
spec = importlib.util.spec_from_file_location('verify_text_coverage', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _write(path, n):
    with open(path, 'w', encoding='utf-8') as fh:
        for i in range(n):
            fh.write(f'<fix.work {i + 1}>\tline {i + 1}\n')


def test_count_lines_reads_reference_lines(tmp_path):
    p = tmp_path / 'w.part.2.tess'
    _write(p, 2)
    assert mod.count_lines(str(p)) == 2


def _flags(part_lines, win, desc=None, vec=None):
    desc = win if desc is None else desc
    vec = win if vec is None else vec
    return mod.window_flags('fix.work', 'fix.work', False, sum(part_lines.values()), part_lines, win, desc, vec)


PARTS = {'fix.work.part.1': 40, 'fix.work.part.2': 2, 'fix.work.part.3': 55}


def test_whole_with_one_short_part_is_covered_when_long_parts_have_windows():
    win = {'fix.work.part.1': 3, 'fix.work.part.3': 5}
    assert _flags(PARTS, win) == {'windows': True, 'described': True, 'winvec': True}


def test_a_long_part_without_windows_is_still_reported():
    win = {'fix.work.part.1': 3}
    r = _flags(PARTS, win)
    assert r['windows'] is False and r['described'] is False and r['winvec'] is False


def test_long_part_missing_descriptions_is_still_reported():
    win = {'fix.work.part.1': 3, 'fix.work.part.3': 5}
    r = _flags(PARTS, win, desc={'fix.work.part.1': 3, 'fix.work.part.3': 1})
    assert r['windows'] is True and r['described'] is False


def test_the_short_part_itself_is_exempt():
    r = mod.window_flags('fix.work.part.2', 'fix.work', True, 2, {}, {}, {}, {})
    assert r == {'windows': True, 'described': True, 'winvec': True}


def test_part_without_windows_but_long_enough_is_reported():
    r = mod.window_flags('fix.work.part.1', 'fix.work', True, 40, {}, {}, {}, {})
    assert r['windows'] is False
