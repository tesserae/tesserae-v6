"""Fetching the actual lines at a reference.

From Claude desktop's first use of Theme Search: the feature returned a correct
set of battle exhortations across three languages, and then there was no way to
read one. theme_search tells the agent "the gist is a machine-written summary of
the passage, never the passage itself: fetch the lines before quoting", and no
tool could. The only way through was an exact-phrase search on wording the user
already knew by heart.

The acceptance test they wrote is the first one here: given only the output of a
theme_search result, an agent with no prior knowledge of the text can retrieve
and quote the passage with correct loci in one call.

These go through the HTTP endpoint rather than calling window_texts directly,
for the reason recorded in test_assistant_conversation.py: testing the other
door is how a broken feature ships green.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402


@pytest.fixture(scope='module')
def route():
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/passages/lines'))


@pytest.fixture(scope='module')
def theme_route():
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/passages/theme-search'))


@pytest.fixture
def client():
    return app.test_client()


def get(client, route, **params):
    qs = '&'.join(f'{k}={v}' for k, v in params.items() if v not in (None, ''))
    r = client.get(f'{route}?{qs}')
    assert r.status_code == 200, f'endpoint returned {r.status_code}'
    return json.loads(r.get_data())


def test_a_theme_result_can_be_read_in_one_call(client, route, theme_route):
    """THE ACCEPTANCE TEST, as written in the report."""
    found = get(client, theme_route, q='a%20military%20leader%20speaks%20to%20his%20troops',
                limit=3)
    assert found.get('results'), 'theme search returned nothing to fetch'
    r = found['results'][0]

    got = get(client, route, work=r['work'],
              ref_start=r['ref_start'].replace(' ', '%20'),
              ref_end=r['ref_end'].replace(' ', '%20'))
    assert not got.get('error'), got.get('error')
    assert got['lines'], 'no lines returned'
    # Every line carries its own locus, because the presentation contract
    # requires a reference on every quotation.
    for line in got['lines']:
        assert line.get('ref'), 'a line came back with no reference'
        assert line.get('text'), 'a line came back with no text'
    # Enough identity to build a citation without reconstructing it from an id.
    assert got.get('author') or got.get('display_name')
    assert got.get('language')
    assert got.get('corpus_version')
    assert got.get('web_url', '').startswith('/read?work=')


def test_persian_which_has_no_other_route_to_its_text(client, route):
    """Persian is not in texts/ in the dev checkout OR in production.

    It is the case the whole line store exists for: without it a third of the
    index could be searched and never read.
    """
    got = get(client, route, work='ferdowsi.diwan',
              ref_start='ferdowsi.diwan.1', ref_end='ferdowsi.diwan.4')
    assert not got.get('error'), got.get('error')
    assert len(got['lines']) == 4
    assert got['language'] == 'fa'
    assert any('؀' <= ch <= 'ۿ' for ch in got['lines'][0]['text']), \
        'the Persian line came back without Perso-Arabic script'


def test_verse_lines_are_separate_not_one_blob(client, route):
    """The window files join lines with spaces; the export printed the opening
    of the Aeneid as prose because of it. Lines must arrive as lines."""
    got = get(client, route, work='vergil.aeneid.part.1',
              ref_start='verg.%20aen.%201.1', ref_end='verg.%20aen.%201.3')
    assert len(got['lines']) == 3
    assert got['lines'][0]['text'].startswith('Arma virumque cano')
    # Line 2 is its own line, not run on from line 1.
    assert 'Italiam' in got['lines'][1]['text']
    assert 'Italiam' not in got['lines'][0]['text']


def test_the_cap_is_honest(client, route):
    """A request for a whole book returns a bounded window that SAYS it is
    bounded, rather than a truncated payload that looks whole."""
    got = get(client, route, work='vergil.aeneid.part.1',
              ref_start='verg.%20aen.%201.1', ref_end='verg.%20aen.%201.500')
    assert got['capped'] is True
    assert got['returned'] < got['total']
    assert got['returned'] == len(got['lines'])
    assert 'note' in got and str(got['total']) in got['note']


def test_context_widens_the_window(client, route):
    """A machine-chosen window often starts mid-sentence."""
    tight = get(client, route, work='vergil.aeneid.part.1',
                ref_start='verg.%20aen.%201.10', ref_end='verg.%20aen.%201.12')
    wide = get(client, route, work='vergil.aeneid.part.1',
               ref_start='verg.%20aen.%201.10', ref_end='verg.%20aen.%201.12',
               context=2)
    assert len(wide['lines']) == len(tight['lines']) + 4


def test_a_bad_reference_says_so_rather_than_guessing(client, route):
    """Falling back to the start of the work would hand back the wrong passage
    under the right-looking citation, which is worse than an error."""
    got = get(client, route, work='vergil.aeneid.part.1',
              ref_start='verg.%20aen.%2099.99')
    assert got.get('error')
    assert '99.99' in got['error']
    assert not got.get('lines')


def test_an_unknown_work_says_so(client, route):
    got = get(client, route, work='nobody.nothing')
    assert got.get('error')
    assert not got.get('lines')


def test_work_is_required(client, route):
    got = get(client, route, work='')
    assert got.get('error')
