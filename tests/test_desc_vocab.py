"""The description vocabulary and the unknown-word check (Theme Search)."""
import importlib.util
import json
import os

import pytest

from backend import passage_index as pi

_spec = importlib.util.spec_from_file_location(
    'build_desc_vocab',
    os.path.join(os.path.dirname(__file__), '..', 'scripts', 'corpus', 'build_desc_vocab.py'))
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)

ROWS = [
    {'id': 'a', 'blob': 'Dido loves Aeneas. Legions march.', 'desc': {'gist': 'A queen mourns', 'themes': ['love', 'Grief']}},
    {'id': 'b', 'blob': 'The legion marches', 'desc': {'gist': 'A queen rules', 'props': ['sword']}},
    {'id': 'c', 'blob': 'Plague at Thebes', 'desc': {'gist': 'Plague strikes', 'themes': 'disease'}},
    {'id': 'd', 'blob': 'Plague again 42', 'desc': {}},
    {'id': 'e', 'blob': '', 'desc': {'gist': 'Sword and shield'}},
]


def test_builder_on_fixture(tmp_path):
    src = tmp_path / 'd.jsonl'
    src.write_text('\n'.join(json.dumps(r) for r in ROWS) + '\nnot json\n', encoding='utf-8')
    out = tmp_path / 'v.json'
    assert builder.main(['--descriptions', str(src), '--out', str(out)]) == 0
    data = json.loads(out.read_text())
    assert data['rows'] == 5 and data['min_count'] == 2
    w = data['words']
    assert w['queen'] == 2 and w['plague'] == 2 and w['sword'] == 2
    assert 'legion' not in w and 'legions' not in w   # one row each
    assert 'dido' not in w and 'thebes' not in w   # one row only
    assert '42' not in w
    assert w['a'] >= 2


VOCAB = {w: 5 for w in (
    'democracy establishment plague dido sejanus pannonian legion legions farmer lift '
    'launch rise airplane torpedo coffee potato establish').split()}


@pytest.mark.parametrize('query,expected', [
    ('xqzv plorf wibble', ['xqzv', 'plorf', 'wibble']),
    ('establishment of democracy', []),
    ('a farmer lifts potatoes', []),   # potato in this fake vocabulary
    ("Dido's plague", []),
    ('the legions', []),
    ('the launches', []),
    ('sun rises', ['sun']),
    ('airplanes', []),
    ('xqzv xqzv', ['xqzv']),
])
def test_unknown_query_words(query, expected):
    assert pi.unknown_query_words(query, vocab=VOCAB) == expected


def test_potatoes_only_unknown_when_absent():
    v = {k: n for k, n in VOCAB.items() if k != 'potato'}
    assert pi.unknown_query_words('a farmer lifts potatoes', vocab=v) == ['potatoes']


def test_stems():
    v = {'stop': 3, 'hope': 3, 'carry': 3, 'march': 3}
    for q in ('stopped', 'hoped', 'hoping', 'carries', 'marched', 'marches', 'stopping'):
        assert pi.unknown_query_words(q, vocab=v) == [], q


def test_check_off_without_vocabulary(monkeypatch):
    monkeypatch.setattr(pi, '_vocab', None)
    assert pi.unknown_query_words('xqzv') is None
    f = pi._vocab_fields('xqzv plorf')
    assert f == {'vocab_checked': False, 'unknown_words': [], 'no_known_words': False}
    assert pi._vocab_note('Original.', f) == 'Original.'


def test_fields_and_notes(monkeypatch):
    monkeypatch.setattr(pi, '_vocab', VOCAB)
    f = pi._vocab_fields('xqzv plorf wibble')
    assert f['vocab_checked'] and f['no_known_words'] and f['unknown_words'] == ['xqzv', 'plorf', 'wibble']
    assert pi._vocab_note('Low confidence.', f) == (
        'None of these words appears in any passage description: xqzv, plorf, wibble. '
        'There is nothing for Theme Search to match. Check the spelling, or describe '
        'the scene in other words.')
    f = pi._vocab_fields('a farmer lifts quux')
    assert f['unknown_words'] == ['quux'] and not f['no_known_words']
    assert pi._vocab_note('Moderate.', f) == (
        'Moderate. The word quux appears in no passage description, so it did not help the search.')
    f = pi._vocab_fields('a farmer lifts quux and zorp')
    assert pi._vocab_note('Moderate.', f).endswith(
        'The words quux and zorp appear in no passage description, so they did not help the search.')
    f = pi._vocab_fields('establishment of democracy')
    assert f['unknown_words'] == [] and not f['no_known_words']
    assert pi._vocab_note('Same.', f) == 'Same.'
    # nothing but stop words: no content word, so not "no known words"
    assert pi._vocab_fields('of the')['no_known_words'] is False


def test_long_list_is_capped(monkeypatch):
    monkeypatch.setattr(pi, '_vocab', VOCAB)
    q = ' '.join(f'zz{c}z' for c in 'abcdefghij')
    f = pi._vocab_fields(q)
    note = pi._vocab_note('x', f)
    assert note.startswith('None of these words')
    assert 'and 2 more.' in note


def test_load_vocab_from_file(tmp_path, monkeypatch):
    monkeypatch.setattr(pi, '_DATA_DIR', str(tmp_path))
    monkeypatch.setattr(pi, '_vocab', None)   # restored to None at teardown
    pi._load_vocab()
    assert pi._vocab is None
    (tmp_path / 'desc_vocab.json').write_text(json.dumps({'words': {'plague': 4}}))
    pi._load_vocab()
    assert pi._vocab == {'plague': 4}

