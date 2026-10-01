"""The credit line a restricted text's licence requires wherever a passage of
it is shown: /api/texts, the Reader's /api/text-descriptions lookup, and the
Sources (credits) page's /api/text-credits.

Tested against a throwaway registry entry and throwaway files in a temp
texts/ directory, since the real registry is empty (no PHI text exists yet)
and this guarantee has to hold before the first one arrives.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402
from flask import Flask  # noqa: E402

import backend.restricted_texts as restricted_texts  # noqa: E402
from backend.blueprints import corpus as corpus_mod  # noqa: E402


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


@pytest.fixture
def client(tmp_path, fixture_registry, monkeypatch):
    lang_dir = tmp_path / 'texts' / 'la'
    lang_dir.mkdir(parents=True)
    (lang_dir / 'heldwork.history.part.1.tess').write_text(
        '<heldwork.history.part.1 1> some line </heldwork.history.part.1 1>\n')
    (lang_dir / 'heldwork.history.part.2.tess').write_text(
        '<heldwork.history.part.2 1> another line </heldwork.history.part.2 1>\n')
    (lang_dir / 'ordinary.poem.tess').write_text(
        '<ordinary.poem 1> a line </ordinary.poem 1>\n')

    corpus_mod.init_corpus_blueprint(str(tmp_path / 'texts'), None, None)
    monkeypatch.setattr(corpus_mod, 'TEXT_SOURCES_FILE', tmp_path / 'no_such_file.json')

    app = Flask(__name__)
    app.register_blueprint(corpus_mod.corpus_bp, url_prefix='/api')
    with app.test_client() as c:
        yield c


def test_texts_listing_flags_restricted_work(client):
    texts = client.get('/api/texts?language=la').get_json()
    by_id = {t['id']: t for t in texts}
    assert by_id['heldwork.history.part.1.tess'].get('restricted') is True
    assert by_id['heldwork.history.part.1.tess']['credit'] == (
        'Source: Test Licence Holder (example.invalid)')
    assert by_id['heldwork.history.part.2.tess'].get('restricted') is True
    assert 'restricted' not in by_id['ordinary.poem.tess']


def test_text_descriptions_exposes_restricted_and_credit(client):
    restricted = client.get(
        '/api/text-descriptions?language=la&work=heldwork.history.part.1.tess'
    ).get_json()
    assert restricted['restricted'] is True
    assert restricted['credit'] == 'Source: Test Licence Holder (example.invalid)'

    ordinary = client.get(
        '/api/text-descriptions?language=la&work=ordinary.poem.tess'
    ).get_json()
    assert 'restricted' not in ordinary
    assert 'credit' not in ordinary


def test_text_credits_lists_restricted_work_once_with_licence(client):
    data = client.get('/api/text-credits?limit=500').get_json()
    restricted_entries = [e for e in data['entries'] if e.get('restricted')]
    assert len(restricted_entries) == 1  # one row for the work, not one per part
    entry = restricted_entries[0]
    assert entry['credit'] == 'Source: Test Licence Holder (example.invalid)'
    assert entry['license'] == 'indexing and search only; no redistribution'
    assert entry['e_source'] is None
    assert entry['print_source'] is None


def test_text_credits_query_matches_restricted_author(client):
    data = client.get('/api/text-credits?query=Heldwork').get_json()
    assert any(e.get('restricted') for e in data['entries'])
