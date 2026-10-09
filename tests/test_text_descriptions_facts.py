"""The Reader's About panel facts (author/date/era/kind/edition), added
additively to /api/text-descriptions' single-work response.

Isolated against a throwaway texts/ directory and throwaway author-dates
and text-sources files, the same way test_restricted_texts_credit.py is,
so this does not depend on (or disturb) the real corpus data or on test
collection order.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from flask import Flask  # noqa: E402

from backend.blueprints import corpus as corpus_mod  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    lang_dir = tmp_path / 'texts' / 'la'
    lang_dir.mkdir(parents=True)
    (lang_dir / 'seneca.thyestes.tess').write_text(
        '<seneca.thyestes 1> some line </seneca.thyestes 1>\n'
        '<seneca.thyestes 2> another line </seneca.thyestes 2>\n')
    (lang_dir / 'ordinary.poem.tess').write_text(
        '<ordinary.poem 1> a line </ordinary.poem 1>\n')

    corpus_mod.init_corpus_blueprint(str(tmp_path / 'texts'), None, None)

    author_dates_file = tmp_path / 'author_dates.json'
    author_dates_file.write_text(json.dumps({
        'la': {'seneca': {'year': 65, 'era': 'Neronian', 'note': 'd. 65 CE'}},
    }))
    monkeypatch.setattr(corpus_mod, 'AUTHOR_DATES_FILE', author_dates_file)
    monkeypatch.setattr(corpus_mod, '_author_dates_cache', None)
    monkeypatch.setattr(corpus_mod, '_author_dates_mtime', None)

    sources_file = tmp_path / 'text_sources.json'
    sources_file.write_text(json.dumps([
        {'author': 'Seneca', 'work': 'Thyestes', 'e_source': 'Perseus',
         'e_source_url': 'https://perseus.example/thyestes',
         'print_source': 'Teubner, 1900.', 'added_by': 'Test'},
    ]))
    monkeypatch.setattr(corpus_mod, 'TEXT_SOURCES_FILE', sources_file)
    monkeypatch.setattr(corpus_mod, '_text_sources_cache', (None, []))

    app = Flask(__name__)
    app.register_blueprint(corpus_mod.corpus_bp, url_prefix='/api')
    with app.test_client() as c:
        yield c


def test_facts_cover_author_date_era_kind_and_edition(client):
    d = client.get('/api/text-descriptions?language=la&work=seneca.thyestes.tess').get_json()
    facts = d['facts']
    assert facts['author'] == 'Seneca'
    assert facts['work'] == 'Thyestes'
    assert facts['year'] == 65
    assert facts['era'] == 'Neronian'
    assert facts['date_note'] == 'd. 65 CE'
    assert facts['kind'] in ('poetry', 'prose')
    assert facts['edition'] == {
        'print_source': 'Teubner, 1900.',
        'e_source': 'Perseus',
        'e_source_url': 'https://perseus.example/thyestes',
    }


def test_facts_omit_edition_when_no_source_entry_matches(client):
    d = client.get('/api/text-descriptions?language=la&work=ordinary.poem.tess').get_json()
    facts = d['facts']
    assert facts['author'] == 'Ordinary'
    assert 'edition' not in facts


def test_no_facts_key_for_a_work_that_does_not_exist(client):
    d = client.get('/api/text-descriptions?language=la&work=nope.tess').get_json()
    assert d == {'description': None}


def test_restricted_work_gets_no_edition_lookup(client, tmp_path, monkeypatch):
    import backend.restricted_texts as restricted_texts
    registry_path = tmp_path / 'restricted_texts.json'
    registry_path.write_text(json.dumps({'texts': {
        'seneca.thyestes': {
            'holder': 'Test Licence Holder',
            'credit': 'Source: Test Licence Holder (example.invalid)',
            'license': 'indexing and search only; no redistribution',
            'added': '2026-10-01', 'ends': None,
        },
    }}))
    monkeypatch.setattr(restricted_texts, 'REGISTRY_PATH', registry_path)
    restricted_texts._cache['mtime'] = None
    restricted_texts._cache['texts'] = {}

    d = client.get('/api/text-descriptions?language=la&work=seneca.thyestes.tess').get_json()
    assert d['restricted'] is True
    assert d['credit'] == 'Source: Test Licence Holder (example.invalid)'
    # The print/e-text sourcing in text_sources.json is not this work's
    # credit line (a restricted work's provenance is not public), so it is
    # left out of facts even though an entry happens to match by name.
    assert 'edition' not in d['facts']

    restricted_texts._cache['mtime'] = None
    restricted_texts._cache['texts'] = {}
