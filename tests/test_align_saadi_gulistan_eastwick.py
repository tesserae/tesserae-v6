"""Unit tests for scripts/translations/align_saadi_gulistan_eastwick.py.

This aligner deliberately builds a WHOLE-WORK, single-unit alignment (see
the module docstring for why a chapter-or-story split was not attempted),
so what needs testing is: the OCR cleanup (header/page-number stripping),
the ref-range slice between two named refs, and the refusal cases. Fixture
files only; never the real corpus or the real Eastwick scan.
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
    'align_saadi_gulistan_eastwick', os.path.join(SCRIPT_DIR, 'align_saadi_gulistan_eastwick.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


FAKE_SOURCE = """\
TRUBNER'S ORIENTAL SERIES.

Some preface material that should never be reached because the start
marker comes after it.

IN THE NAME OF GOD, THE MERCIFUL, THE COMPASSIONATE.

CHAPTER I.

Praise be to the glorious and almighty God, to whom
obedience is a cause of approach.

CHAPTER I. STORY V.

From the dust of the dead rose stems and leaves have

42

grown ten thousand times, and still each fresh spring day
new flowers bloom upon them.

CONCLUSION OF THE BOOK.

The book of the Gulistan is ended by the assistance of
God.

STEPHEN AUSTIN AND SONS, PRINTERS, HERTFORD.

This printer's colophon must never appear in the output.
"""


def write_tess(path, refs):
    with open(path, 'w', encoding='utf-8') as f:
        for ref in refs:
            f.write(f'<{ref}>\tPersian line {ref}\n')


def test_clean_english_strips_headers_and_page_numbers():
    cleaned = mod.clean_english(
        'CHAPTER I.\n\nReal paragraph text.\n\nCHAPTER I. STORY V.\n\n'
        '42\n\nMore real text continued\nacross two wrapped lines.\n\n'
        'CONCLUSION OF THE BOOK.\n\nFinal paragraph.'
    )
    assert 'CHAPTER' not in cleaned
    assert '42' not in cleaned.split('\n\n')[0]
    assert 'Real paragraph text.' in cleaned
    assert 'More real text continued across two wrapped lines.' in cleaned
    assert 'Final paragraph.' in cleaned


def test_extract_translation_finds_markers_and_strips_colophon(tmp_path):
    src = tmp_path / 'src.txt'
    src.write_text(FAKE_SOURCE, encoding='utf-8')
    text = mod.extract_translation(str(src))
    assert 'preface material' not in text
    assert 'colophon must never appear' not in text
    assert 'Praise be to the glorious' in text
    assert 'CONCLUSION OF THE BOOK' not in text  # header line itself stripped
    assert 'book of the Gulistan is ended' in text


def test_extract_translation_refuses_without_markers(tmp_path):
    src = tmp_path / 'src.txt'
    src.write_text('no markers here at all', encoding='utf-8')
    with pytest.raises(SystemExit):
        mod.extract_translation(str(src))


def padded_source():
    # Insert padding BEFORE the end marker, so extract_translation (which
    # cuts off at the end marker) actually sees it, clearing the script's
    # length sanity check.
    marker = 'CONCLUSION OF THE BOOK.'
    before, after = FAKE_SOURCE.split(marker, 1)
    return before + ('Extra padding text. ' * 600) + '\n\n' + marker + after


def test_main_builds_whole_work_unit(tmp_path, monkeypatch):
    tess = tmp_path / 'saadi.diwan.tess'
    refs = [f'saadi.diwan.{n}' for n in range(29806, 29812)]
    write_tess(tess, refs)
    src = tmp_path / 'src.txt'
    src.write_text(padded_source(), encoding='utf-8')
    out_dir = tmp_path / 'out'

    monkeypatch.setattr(sys, 'argv', [
        'align_saadi_gulistan_eastwick.py',
        '--src', str(src), '--tess', str(tess),
        '--first-ref', 'saadi.diwan.29808', '--last-ref', 'saadi.diwan.29810',
        '--out-dir', str(out_dir),
    ])
    mod.main()

    out_file = out_dir / 'fa__saadi.diwan.json'
    data = json.loads(out_file.read_text(encoding='utf-8'))
    assert data['n_units_stored'] == 1
    assert set(data['ref_to_unit']) == {'saadi.diwan.29808', 'saadi.diwan.29809', 'saadi.diwan.29810'}
    assert all(v == 0 for v in data['ref_to_unit'].values())
    assert data['n_tess_refs'] == 3
    assert data['coverage'] == 1.0
    assert 'Eastwick' in data['attribution']


def test_main_refuses_when_first_ref_missing(tmp_path, monkeypatch):
    tess = tmp_path / 'saadi.diwan.tess'
    write_tess(tess, [f'saadi.diwan.{n}' for n in range(29806, 29812)])
    src = tmp_path / 'src.txt'
    src.write_text(padded_source(), encoding='utf-8')
    out_dir = tmp_path / 'out'

    monkeypatch.setattr(sys, 'argv', [
        'align_saadi_gulistan_eastwick.py',
        '--src', str(src), '--tess', str(tess),
        '--first-ref', 'saadi.diwan.99999', '--last-ref', 'saadi.diwan.29810',
        '--out-dir', str(out_dir),
    ])
    with pytest.raises(SystemExit):
        mod.main()
    assert not out_dir.exists() or not list(out_dir.glob('*.json'))
