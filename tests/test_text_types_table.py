"""The prose/poetry table: lookup order, fill and check (never the real table)."""
import importlib.util
import json
import os

import pytest

from backend import utils

_spec = importlib.util.spec_from_file_location(
    'text_types_script',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'corpus', 'text_types.py'))
tt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tt)

LONG_LINES = ''.join(f'<x. {i}>\t' + 'word ' * 40 + '\n' for i in range(1, 10))
SHORT_LINES = ''.join(f'<x. {i}>\tarma virum que\n' for i in range(1, 10))


@pytest.fixture
def table_env(tmp_path, monkeypatch):
    table_path = tmp_path / 'text_types.json'
    monkeypatch.setattr(utils, 'TEXT_TYPES_PATH', str(table_path))
    monkeypatch.setattr(utils, '_text_types_cache', None)
    monkeypatch.setattr(utils, '_text_types_mtime', 0)
    monkeypatch.setattr(utils, 'get_override', lambda fn: {})
    texts = tmp_path / 'texts'
    (texts / 'la').mkdir(parents=True)

    def write_table(entries):
        table_path.write_text(json.dumps({'_description': 'x', 'la': entries}), encoding='utf-8')
        monkeypatch.setattr(utils, '_text_types_cache', None)
    return table_path, texts, write_table


def test_table_beats_markers_and_line_length(table_env):
    table_path, texts, write_table = table_env
    # 'vergil.aeneid' is a poetry marker and short lines say poetry; the table says prose.
    f = texts / 'la' / 'vergil.aeneid.tess'
    f.write_text(SHORT_LINES, encoding='utf-8')
    write_table({'vergil.aeneid.tess': {'text_type': 'prose', 'source': 'reviewed'}})
    assert utils.detect_text_type('vergil.aeneid.tess', filepath=str(f), language='la') == 'prose'
    # language None: found when exactly one language holds the name
    assert utils.detect_text_type('vergil.aeneid.tess') == 'prose'


def test_override_beats_table(table_env, monkeypatch):
    table_path, texts, write_table = table_env
    write_table({'some.work.tess': {'text_type': 'prose', 'source': 'marker'}})
    monkeypatch.setattr(utils, 'get_override', lambda fn: {'text_type': 'poetry'})
    assert utils.detect_text_type('some.work.tess', language='la') == 'poetry'


def test_absent_file_falls_back_to_cascade(table_env):
    table_path, texts, write_table = table_env
    write_table({'other.work.tess': {'text_type': 'prose', 'source': 'marker'}})
    f = texts / 'la' / 'newauthor.newwork.tess'
    f.write_text(LONG_LINES, encoding='utf-8')
    assert utils.detect_text_type(f.name, filepath=str(f), language='la') == 'prose'
    g = texts / 'la' / 'newauthor.shortwork.tess'
    g.write_text(SHORT_LINES, encoding='utf-8')
    assert utils.detect_text_type(g.name, filepath=str(g), language='la') == 'poetry'


def test_fill_adds_missing_and_keeps_existing(table_env, capsys):
    table_path, texts, write_table = table_env
    (texts / 'la' / 'a.kept.tess').write_text(LONG_LINES, encoding='utf-8')
    (texts / 'la' / 'a.new.tess').write_text(LONG_LINES, encoding='utf-8')
    write_table({'a.kept.tess': {'text_type': 'poetry', 'source': 'reviewed'}})
    assert tt.fill(str(table_path), str(texts)) == 0
    data = json.loads(table_path.read_text(encoding='utf-8'))
    assert data['la']['a.kept.tess'] == {'text_type': 'poetry', 'source': 'reviewed'}
    assert data['la']['a.new.tess'] == {'text_type': 'prose', 'source': 'line_length'}
    assert 'added la/a.new.tess' in capsys.readouterr().out
    # a second run adds nothing
    tt.fill(str(table_path), str(texts))
    assert 'added la/' not in capsys.readouterr().out


def test_check_exit_codes(table_env, capsys):
    table_path, texts, write_table = table_env
    (texts / 'la' / 'a.one.tess').write_text(LONG_LINES, encoding='utf-8')
    (texts / 'la' / 'a.two.tess').write_text(LONG_LINES, encoding='utf-8')
    write_table({'a.one.tess': {'text_type': 'prose', 'source': 'marker'}})
    assert tt.check(str(table_path), str(texts)) == 1
    assert 'no entry: la/a.two.tess' in capsys.readouterr().out
    write_table({'a.one.tess': {'text_type': 'prose', 'source': 'marker'},
                 'a.two.tess': {'text_type': 'prose', 'source': 'marker'}})
    assert tt.check(str(table_path), str(texts)) == 0
    write_table({'a.one.tess': {'text_type': 'prose', 'source': 'marker'},
                 'a.two.tess': {'text_type': 'prose', 'source': 'marker'},
                 'a.gone.tess': {'text_type': 'prose', 'source': 'marker'}})
    assert tt.check(str(table_path), str(texts)) == 1
