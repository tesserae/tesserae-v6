"""Rare Words leaves the corpus-occurrence list out unless the request asks."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import hapax  # noqa: E402


@pytest.fixture
def client():
    return app.test_client()


@pytest.fixture
def seen(monkeypatch):
    calls = []

    def fake(*args, **kwargs):
        calls.append(kwargs)
        return {'shared_rare_count': 0, 'results': []}

    monkeypatch.setattr(hapax, '_compute_rare_words', fake)
    return calls


@pytest.mark.parametrize('body,expected', [
    ({}, False),
    ({'include_corpus_locations': True}, True),
    ({'include_corpus_locations': 'true'}, True),
    ({'include_corpus_locations': False}, False),
])
def test_post_flag(client, seen, body, expected):
    r = client.post(API_PREFIX + '/hapax-search', json={'source': 'a', 'target': 'b', **body})
    assert r.status_code == 200
    assert seen[-1]['include_corpus_locations'] is expected


def test_query_string_flag(client, seen):
    r = client.get(API_PREFIX + '/hapax-search?source=a&target=b&include_corpus_locations=true')
    assert r.status_code == 200
    assert seen[-1]['include_corpus_locations'] is True


def test_nothing_in_the_connector_or_assistant_reads_the_field():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for rel in ('backend/blueprints/mcp_http.py', 'backend/assistant/agent.py',
                'backend/assistant/searches.py', 'integrations/mcp/tesserae_mcp.py'):
        with open(os.path.join(root, rel), encoding='utf-8') as f:
            assert 'all_corpus_locations' not in f.read(), rel
