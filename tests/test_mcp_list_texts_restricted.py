"""list_texts (the MCP connector's wrapper over /api/texts) must pass the
restricted flag and credit line through, since a connector client quotes
passages the same way the site does and is bound by the same licence terms.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.blueprints import mcp_http  # noqa: E402


def test_list_texts_passes_through_restricted_and_credit(monkeypatch):
    monkeypatch.setattr(mcp_http, '_get', lambda path, params=None: [
        {'id': 'heldwork.history.tess', 'author': 'Held Author', 'work': 'History',
         'title': 'History', 'restricted': True,
         'credit': 'Source: Test Licence Holder (example.invalid)'},
        {'id': 'ordinary.poem.tess', 'author': 'Ordinary Poet', 'work': 'Poem',
         'title': 'Poem'},
    ])
    out = mcp_http._t_list_texts({'language': 'la'})
    by_id = {t['id']: t for t in out}
    assert by_id['heldwork.history.tess']['restricted'] is True
    assert by_id['heldwork.history.tess']['credit'] == (
        'Source: Test Licence Holder (example.invalid)')
    assert 'restricted' not in by_id['ordinary.poem.tess']
