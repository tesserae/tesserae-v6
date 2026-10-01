"""`_naming`, the one function Similar Passages, Theme Search and Theme
Comparison all build their result cards through (backend/passage_index.py),
must flag a restricted work and carry its credit line -- that is the single
integration point for all three of the content-search surfaces at once.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

import backend.restricted_texts as restricted_texts  # noqa: E402
from backend import passage_index as pi  # noqa: E402


@pytest.fixture
def fixture_registry(tmp_path, monkeypatch):
    registry_path = tmp_path / 'restricted_texts.json'
    registry_path.write_text(json.dumps({
        'texts': {
            'heldwork.history': {
                'holder': 'Test Licence Holder',
                'credit': 'Source: Test Licence Holder (example.invalid)',
                'license': 'indexing and search only; no redistribution',
                'added': '2026-10-01',
                'ends': None,
            }
        }
    }))
    monkeypatch.setattr(restricted_texts, 'REGISTRY_PATH', registry_path)
    restricted_texts._cache['mtime'] = None
    restricted_texts._cache['texts'] = {}
    yield
    restricted_texts._cache['mtime'] = None
    restricted_texts._cache['texts'] = {}


def test_naming_flags_restricted_work(fixture_registry):
    out = pi._naming('heldwork.history')
    assert out['restricted'] is True
    assert out['credit'] == 'Source: Test Licence Holder (example.invalid)'


def test_naming_flags_a_part_of_a_restricted_work(fixture_registry):
    out = pi._naming('heldwork.history.part.3')
    assert out['restricted'] is True


def test_naming_leaves_an_ordinary_work_unflagged(fixture_registry):
    out = pi._naming('ordinary.poem')
    assert 'restricted' not in out
    assert 'credit' not in out


def test_result_card_carries_the_flag_through(fixture_registry, monkeypatch):
    """_result (Similar Passages' and Theme Comparison's actual card builder)
    pulls in _naming's output, so the flag reaches both without either
    needing its own lookup."""
    monkeypatch.setattr(pi, '_records', [
        {'id': 'w1', 'work': 'heldwork.history', 'scale': 'fine', 'language': 'la',
         'ref_start': 'held. hist. 1', 'ref_end': 'held. hist. 1', 'desc': {}},
    ])
    card = pi._result(0, 0.9)
    assert card['restricted'] is True
    assert card['credit'] == 'Source: Test Licence Holder (example.invalid)'
