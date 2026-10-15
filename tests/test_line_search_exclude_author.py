"""exclude_author drops every work of one author from Line Search.

Integration test against the live Latin index (skipped where absent), like
test_line_search_passage_cap.py.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.lexical_density import _index_path

if not os.path.exists(_index_path('la')):
    pytest.skip('Latin inverted index not present; integration test',
                allow_module_level=True)

import backend.app  # noqa: E402,F401
import backend.blueprints.line_search as _appmod  # noqa: E402
from backend.app import app  # noqa: E402
from backend.blueprints.line_search import _is_excluded_author  # noqa: E402
from backend.line_search_params import _read_params  # noqa: E402

_appmod.get_corpus_frequencies = lambda *a, **k: {'frequencies': {}}


def _route():
    return next(str(r) for r in app.url_map.iter_rules()
                if str(r).endswith('/line-search'))


def _post(**extra):
    body = {'query': 'arma virumque cano', 'language': 'la',
            'search_type': 'lemma', 'max_results': 500}
    body.update(extra)
    r = app.test_client().post(_route(), json=body)
    assert r.status_code == 200
    return r.get_json()


def test_off_by_default_and_empty_value_change_nothing():
    base = _post()
    for k in ('search_time',):
        base.pop(k, None)
    same = _post(exclude_author='')
    same.pop('search_time', None)
    assert base == same
    assert any(r['text_id'].startswith('vergil.') for r in base['results'])


def test_vergil_excluded_and_page_stays_full():
    off = _post()
    on = _post(exclude_author='vergil')
    assert not [r for r in on['results'] if r['text_id'].split('.')[0].lower() == 'vergil']
    assert {r['text_id'].split('.')[0] for r in on['results']} - {'vergil'}
    assert on['total'] >= off['total'] - 40  # other authors fill the places Vergil held
    assert not [w for w in on.get('by_work_all', []) if w['work_id'].split('.')[0] == 'vergil']


def test_excluded_author_matches_whole_and_part_files_only():
    assert _is_excluded_author('vergil.aeneid.tess', 'vergil')
    assert _is_excluded_author('vergil.aeneid.part.1.tess', 'vergil')
    assert _is_excluded_author('Vergil.georgics.tess', 'vergil')
    assert not _is_excluded_author('vergil_pseudo.culex.tess', 'vergil')


def test_parameter_is_read_and_trimmed():
    assert _read_params({'query': 'x', 'exclude_author': ' Vergil '}).exclude_author == 'vergil'
    assert _read_params({'query': 'x'}).exclude_author == ''
