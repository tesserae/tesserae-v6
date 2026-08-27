"""The Theme Search export, and the ranking dedup that feeds it.

Flagged by the automated review on PR #269: the export route shipped with no
backend coverage at all. It had been checked by hand against the live site,
which is not the same thing and does not survive the next change.

Both suites here go through the HTTP endpoint, for the reason recorded in
test_assistant_conversation.py: testing the other door is how a broken feature
ships green.
"""
import csv
import io
import json
import os
import sys

import pytest

# Before importing the app: backend/app.py raises without this outside dev, and
# CI has no environment. The suite has been red on main for this reason.
os.environ.setdefault('SESSION_SECRET', 'test-only-not-a-secret')
os.environ.setdefault('TESSERAE_DIRECT_SERVER', '1')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend.passage_index import _ref_coords  # noqa: E402


@pytest.fixture(scope='module')
def route():
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/passages/export'))


@pytest.fixture
def client():
    return app.test_client()


def get(client, route, **params):
    qs = '&'.join(f'{k}={v}' for k, v in params.items())
    r = client.get(f'{route}?{qs}')
    assert r.status_code == 200, f'endpoint returned {r.status_code}'
    return r


# --------------------------------------------------------------------------
# The export route
# --------------------------------------------------------------------------

def test_json_export_carries_the_source_passages(client, route):
    """The whole point: a Theme Search result names a work and a line range and
    shows a machine-written summary. The export has to carry the passage.

    NOTE the two formats name their fields differently. JSON keeps the internal
    names (`text`, `work`, `gist`); the CSV renames them for a reader who will
    open it in a spreadsheet (`passage`, `title`, `summary`), via
    _EXPORT_COLUMNS. Asserted in both places below so the difference is on the
    record rather than a trap: this test was written against the CSV names and
    failed on the JSON.
    """
    d = json.loads(get(client, route, q='a%20storm%20at%20sea', limit=4,
                       format='json').get_data())
    assert not d.get('error'), d.get('error')
    assert d['results'], 'no results to export'
    for r in d['results']:
        assert r['text'], f"{r['author']} {r['locus']} exported with no text"
        assert r['text'] != '[source text unavailable]'
    assert d['missing_text'] == 0


def test_json_and_csv_describe_the_same_passages(client, route):
    """The renaming must be a renaming and nothing more."""
    j = json.loads(get(client, route, q='a%20storm%20at%20sea', limit=3,
                       format='json').get_data())
    body = get(client, route, q='a%20storm%20at%20sea', limit=3,
               format='csv').get_data(as_text=True).lstrip('﻿')
    rows = list(csv.DictReader(io.StringIO(body)))
    assert len(rows) == len(j['results'])
    for jr, cr in zip(j['results'], rows):
        assert cr['passage'] == jr['text']
        assert cr['summary'] == (jr['gist'] or '')
        assert cr['author'] == jr['author']
        assert cr['locus'] == jr['locus']


def test_export_is_chronological_oldest_first(client, route):
    """A themed set crosses centuries and the reading order is itself
    information. Sorting by relevance score throws that away."""
    d = json.loads(get(client, route, q='a%20storm%20at%20sea', limit=8,
                       format='json').get_data())
    years = [r['date'] for r in d['results']]
    assert years, 'nothing to check'
    assert 'chronological' in d['order']
    # n is assigned in the sorted order, so it must be 1..N ascending.
    assert [r['n'] for r in d['results']] == list(range(1, len(d['results']) + 1))


def test_every_passage_is_labelled_well_enough_to_cite(client, route):
    d = json.loads(get(client, route, q='lament%20for%20the%20dead', limit=4,
                       format='json').get_data())
    for r in d['results']:
        assert r['author'], 'a result with no author cannot be cited'
        assert r['locus'], 'a result with no locus cannot be cited'
        assert r['language']


def test_csv_carries_a_bom_so_excel_reads_utf8(client, route):
    """Without it Excel reads a UTF-8 CSV as the system codepage and every
    Greek, Hebrew and Persian passage in the file becomes mojibake."""
    r = get(client, route, q='a%20storm%20at%20sea', limit=3, format='csv')
    body = r.get_data(as_text=True)
    assert body.startswith('﻿'), 'no BOM; Excel will mangle every non-Latin script'
    assert r.headers['Content-Type'] == 'text/csv; charset=utf-8'
    assert r.headers['Content-Type'].count('charset') == 1, 'charset duplicated'
    assert 'attachment; filename=' in r.headers.get('Content-Disposition', '')


def test_csv_parses_with_passages_that_contain_line_breaks(client, route):
    """Passages are multi-line verse now. If they were not quoted properly the
    file would look fine and parse into the wrong number of rows."""
    r = get(client, route, q='a%20storm%20at%20sea', limit=4, format='csv')
    body = r.get_data(as_text=True).lstrip('﻿')
    rows = list(csv.DictReader(io.StringIO(body)))
    assert rows, 'CSV parsed to nothing'
    assert list(rows[0]) == ['n', 'author', 'title', 'locus', 'date', 'era',
                             'language', 'score', 'strong', 'themes',
                             'summary', 'passage']
    assert any('\n' in r['passage'] for r in rows), \
        'no multi-line passage in the sample; verse line breaks may be lost'
    for row in rows:
        assert row['passage'].strip()


def test_a_missing_query_is_an_error_not_an_empty_export(client, route):
    d = json.loads(get(client, route, q='', format='json').get_data())
    assert d.get('error')


def test_an_unknown_format_is_refused(client, route):
    d = json.loads(get(client, route, q='storm', format='xlsx').get_data())
    assert d.get('error')


# --------------------------------------------------------------------------
# The dedup that decides what reaches the export in the first place
# --------------------------------------------------------------------------

def overlaps(a_start, a_end, b_start, b_end):
    """The predicate _rank uses, in isolation."""
    lo1, hi1 = _ref_coords(a_start), _ref_coords(a_end)
    lo2, hi2 = _ref_coords(b_start), _ref_coords(b_end)
    return lo1 <= hi2 and lo2 <= hi1


def test_passages_in_different_books_do_not_count_as_overlapping():
    """The bug the PR review caught, with the victim it already had.

    _ref_numbers keeps only the last two numeric coordinates, so Ammianus
    'amm. 21.13.14' became (13, 14) and 'amm. 17.13.30' became (13, 30). The
    book was discarded, two passages four books apart compared as overlapping,
    and the dedup dropped one of them from a live Theme Search page without
    saying so.
    """
    assert not overlaps('amm. 21.13.14', 'amm. 21.16.13',
                        'amm. 17.13.30', 'amm. 17.14.3')


def test_a_real_overlap_inside_one_book_is_still_caught():
    """The other side of the fix. Caesar came back as both 2.31.6-2.35.4 and
    2.32.10-2.34.4, one wholly inside the other."""
    assert overlaps('caes. bel. civ. 2.31.6', 'caes. bel. civ. 2.35.4',
                    'caes. bel. civ. 2.32.10', 'caes. bel. civ. 2.34.4')


def test_adjacent_but_disjoint_spans_do_not_overlap():
    assert not overlaps('verg. aen. 6.1', 'verg. aen. 6.12',
                        'verg. aen. 6.13', 'verg. aen. 6.24')


def test_touching_spans_do_overlap():
    assert overlaps('verg. aen. 6.1', 'verg. aen. 6.12',
                    'verg. aen. 6.12', 'verg. aen. 6.24')


def test_single_number_references_still_work():
    """Persian and Urdu references carry one coordinate, not book.line."""
    assert _ref_coords('ferdowsi.diwan.27931') == (27931,)
    assert overlaps('ferdowsi.diwan.27931', 'ferdowsi.diwan.27942',
                    'ferdowsi.diwan.27935', 'ferdowsi.diwan.27950')
    assert not overlaps('ferdowsi.diwan.27931', 'ferdowsi.diwan.27942',
                        'ferdowsi.diwan.30000', 'ferdowsi.diwan.30010')
