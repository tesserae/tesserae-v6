"""The Greek and Hebrew letter tables against the one shared fixture."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from backend.transliterate import greek_to_latin, greek_to_betacode, hebrew_to_latin  # noqa: E402

with open(os.path.join(os.path.dirname(__file__), 'fixtures', 'transliteration_cases.json'), encoding='utf-8') as f:
    CASES = json.load(f)


def test_fixture_size():
    assert len(CASES) >= 40
    assert sum('hebrew' in c for c in CASES) >= 6
    assert sum('beta' in c for c in CASES) >= 6


@pytest.mark.parametrize('case', [c for c in CASES if 'greek' in c], ids=lambda c: c['greek'])
def test_greek_to_latin(case):
    assert greek_to_latin(case['greek']) == case['latin']


@pytest.mark.parametrize('case', [c for c in CASES if 'beta' in c], ids=lambda c: c['greek'])
def test_greek_to_betacode(case):
    assert greek_to_betacode(case['greek']) == case['beta']


@pytest.mark.parametrize('case', [c for c in CASES if 'hebrew' in c], ids=lambda c: c['hebrew'])
def test_hebrew_to_latin(case):
    assert hebrew_to_latin(case['hebrew']) == case['latin']


def test_other_text_passes_through():
    assert greek_to_latin('Plain, English; text 12.') == 'Plain, English; text 12.'
    assert hebrew_to_latin('abc 1') == 'abc 1'


def test_unpointed_hebrew_is_consonants_only():
    assert hebrew_to_latin('כפר') == 'kpr'
