"""Unit tests for scripts/translations/align_rumi_masnavi_nicholson.py.

The real alignment is trivial by design (eighteen Persian lines, eighteen
numbered English couplets, one to one), so what needs testing is that the
script actually REFUSES rather than guesses when the inputs do not agree:
a gap or duplicate in the source numbering, or a ref count that does not
match the couplet count. Everything here runs against small fixture files
written to tmp_path, never against the real corpus or the real Nicholson
text.
"""
import importlib.util
import json
import os
import sys

import pytest

SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'scripts', 'translations')
sys.path.insert(0, SCRIPT_DIR)

spec = importlib.util.spec_from_file_location(
    'align_rumi_masnavi_nicholson', os.path.join(SCRIPT_DIR, 'align_rumi_masnavi_nicholson.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def write_tess(path, n):
    with open(path, 'w', encoding='utf-8') as f:
        for i in range(1, n + 1):
            f.write(f'<rumi.masnavi.1.{i}>\tPersian line {i}\n')


def write_src(path, lines):
    with open(path, 'w', encoding='utf-8') as f:
        for n, text in lines:
            f.write(f'{n}. {text}\n')


def test_read_couplets_parses_numbered_lines(tmp_path):
    src = tmp_path / 'src.txt'
    write_src(src, [(1, 'First couplet.'), (2, 'Second couplet.'), (3, 'Third couplet.')])
    couplets = mod.read_couplets(str(src))
    assert couplets == [(1, 'First couplet.'), (2, 'Second couplet.'), (3, 'Third couplet.')]


def test_read_couplets_rejects_unrecognized_line(tmp_path):
    src = tmp_path / 'src.txt'
    src.write_text('not a numbered line\n', encoding='utf-8')
    with pytest.raises(ValueError):
        mod.read_couplets(str(src))


def test_main_builds_one_to_one_alignment(tmp_path, monkeypatch, capsys):
    tess = tmp_path / 'rumi.masnavi.part.1.tess'
    write_tess(tess, 3)
    src = tmp_path / 'src.txt'
    write_src(src, [(1, 'First couplet.'), (2, 'Second couplet.'), (3, 'Third couplet.')])
    out_dir = tmp_path / 'out'

    monkeypatch.setattr(sys, 'argv', [
        'align_rumi_masnavi_nicholson.py',
        '--src', str(src), '--tess', str(tess), '--out-dir', str(out_dir),
    ])
    mod.main()

    out_file = out_dir / 'fa__rumi.masnavi.part.1.json'
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding='utf-8'))
    assert data['n_tess_refs'] == 3
    assert data['n_translated'] == 3
    assert data['coverage'] == 1.0
    assert data['alignment_confidence'] == 'exact'
    assert data['approximate'] is False
    assert data['units'] == ['First couplet.', 'Second couplet.', 'Third couplet.']
    assert data['ref_to_unit']['rumi.masnavi.1.1'] == 0
    assert data['ref_to_unit']['rumi.masnavi.1.2'] == 1
    assert data['ref_to_unit']['rumi.masnavi.1.3'] == 2
    assert data['sources'][0]['translator'] == 'Reynold A. Nicholson'


def test_main_refuses_gap_in_numbering(tmp_path, monkeypatch):
    tess = tmp_path / 'rumi.masnavi.part.1.tess'
    write_tess(tess, 3)
    src = tmp_path / 'src.txt'
    # Line 2 is missing: 1, 3, 4 instead of 1, 2, 3.
    write_src(src, [(1, 'First couplet.'), (3, 'Third couplet.'), (4, 'Fourth couplet.')])
    out_dir = tmp_path / 'out'

    monkeypatch.setattr(sys, 'argv', [
        'align_rumi_masnavi_nicholson.py',
        '--src', str(src), '--tess', str(tess), '--out-dir', str(out_dir),
    ])
    with pytest.raises(SystemExit):
        mod.main()
    assert not out_dir.exists() or not list(out_dir.glob('*.json'))


def test_main_refuses_mismatched_ref_count(tmp_path, monkeypatch):
    tess = tmp_path / 'rumi.masnavi.part.1.tess'
    write_tess(tess, 4)  # four refs, only three couplets below
    src = tmp_path / 'src.txt'
    write_src(src, [(1, 'First couplet.'), (2, 'Second couplet.'), (3, 'Third couplet.')])
    out_dir = tmp_path / 'out'

    monkeypatch.setattr(sys, 'argv', [
        'align_rumi_masnavi_nicholson.py',
        '--src', str(src), '--tess', str(tess), '--out-dir', str(out_dir),
    ])
    with pytest.raises(SystemExit):
        mod.main()
    assert not out_dir.exists() or not list(out_dir.glob('*.json'))
