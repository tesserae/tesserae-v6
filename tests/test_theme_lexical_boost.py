"""Theme Search lexical boost (2026-09-20): a word index over the
descriptions adds LEXICAL_BETA x normalised BM25 to matching windows; it is
skipped when the index is missing or built for a different set of windows."""
import json
import os
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend import passage_index as PI  # noqa: E402

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    'build_desc_fts', os.path.join(PROJECT_ROOT, 'scripts', 'build_desc_fts.py'))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
build, description_text = _mod.build, _mod.description_text

RECORDS = [
    {'id': 'a:fine:0', 'desc': {'gist': 'A woman recognizes her husband by a scar', 'themes': ['recognition']}},
    {'id': 'b:fine:0', 'desc': {'gist': 'Warriors arm for battle', 'themes': ['war'], 'action_steps': ['puts on greaves']}},
    {'id': 'c:fine:0', 'desc': {'gist': 'A storm at sea batters the ships'}},
    {'id': 'd:fine:0'},  # undescribed
]


@pytest.fixture
def fake_index(tmp_path, monkeypatch):
    src = tmp_path / 'descriptions.jsonl'
    with open(src, 'w', encoding='utf-8') as fh:
        for r in RECORDS[:3]:
            fh.write(json.dumps(r) + '\n')
    out = tmp_path / 'desc_fts.sqlite'
    n, _ = build(str(src), str(out))
    assert n == 3
    monkeypatch.setattr(PI, '_LEX_PATH', str(out))
    monkeypatch.setattr(PI, '_DATA_DIR', str(tmp_path))   # the index's source file lives here
    monkeypatch.setattr(PI, '_records', RECORDS)
    monkeypatch.setattr(PI, '_lex_state', {'checked': False, 'ok': False, 'row_by_id': None})
    monkeypatch.delenv('THEME_LEXICAL', raising=False)
    return out


def test_description_text_joins_the_fields():
    t = description_text(RECORDS[1])
    assert 'Warriors arm' in t and 'war' in t and 'greaves' in t


def test_boost_goes_to_the_matching_window_only(fake_index):
    scores = np.array([0.80, 0.80, 0.80, -1.0])
    n = PI._lexical_boost('a wife recognizes her husband', scores)
    assert n == 1
    assert scores[0] == pytest.approx(0.80 + PI.LEXICAL_BETA)
    assert scores[1] == 0.80 and scores[2] == 0.80 and scores[3] == -1.0


def test_function_words_alone_give_no_boost(fake_index):
    scores = np.array([0.5, 0.5, 0.5, -1.0])
    assert PI._lexical_boost('the and of', scores) == 0
    assert list(scores) == [0.5, 0.5, 0.5, -1.0]


def test_missing_index_means_no_boost(tmp_path, monkeypatch):
    monkeypatch.setattr(PI, '_LEX_PATH', str(tmp_path / 'absent.sqlite'))
    monkeypatch.setattr(PI, '_records', RECORDS)
    monkeypatch.setattr(PI, '_lex_state', {'checked': False, 'ok': False, 'row_by_id': None})
    scores = np.array([0.5, 0.5, 0.5, -1.0])
    assert PI._lexical_boost('storm at sea', scores) == 0


def test_stale_index_is_refused(fake_index, monkeypatch):
    # the index describes 3 windows; pretend the passage index now has 400 described
    big = [{'id': f'x{i}:fine:0', 'desc': {'gist': 'filler'}} for i in range(400)]
    monkeypatch.setattr(PI, '_records', big)
    monkeypatch.setattr(PI, '_lex_state', {'checked': False, 'ok': False, 'row_by_id': None})
    scores = np.full(400, 0.5)
    assert PI._lexical_boost('storm at sea', scores) == 0


def test_env_switch_turns_it_off(fake_index, monkeypatch):
    monkeypatch.setenv('THEME_LEXICAL', '0')
    monkeypatch.setattr(PI, '_lex_state', {'checked': False, 'ok': False, 'row_by_id': None})
    scores = np.array([0.5, 0.5, 0.5, -1.0])
    assert PI._lexical_boost('storm at sea', scores) == 0


def test_lexical_words_drop_function_words():
    assert PI._lexical_words('a wife or child recognizes someone long thought dead or lost') == \
        ['wife', 'child', 'recognizes', 'someone', 'long', 'thought', 'dead', 'lost']


def test_best_word_match_gets_the_largest_boost(fake_index):
    # 'storm sea ships' matches window c fully, window a and b not at all
    scores = np.array([0.5, 0.5, 0.5, -1.0])
    n = PI._lexical_boost('a storm at sea batters the ships', scores)
    assert n >= 1
    assert scores[2] == pytest.approx(0.5 + PI.LEXICAL_BETA)   # the best match gets the full beta
    assert scores[2] > scores[0] and scores[2] > scores[1]


def test_edited_source_file_makes_the_index_stale(fake_index, tmp_path, monkeypatch):
    # the fixture built the index from tmp_path/descriptions.jsonl; rewrite that file
    src = tmp_path / 'descriptions.jsonl'
    with open(src, 'a', encoding='utf-8') as fh:
        fh.write(' ' * 10)
    monkeypatch.setattr(PI, '_lex_state', {'checked': False, 'ok': False, 'row_by_id': None})
    scores = np.array([0.5, 0.5, 0.5, -1.0])
    assert PI._lexical_boost('storm at sea', scores) == 0
