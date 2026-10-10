"""Tessa describes what the server holds from the server's own state, never
from a fixed list in the prompt (owner's review 2026-10-10: her answer named
only Latin, Greek, Hebrew, English and Coptic after Persian, Urdu, the
inscriptions, the scholarship and the events had been added)."""
import os
import sqlite3

import pytest

from backend.assistant import site_facts


@pytest.fixture(autouse=True)
def fresh_cache():
    site_facts.reset_cache()
    yield
    site_facts.reset_cache()


def test_languages_agree_with_the_languages_route():
    """The helper and /api/languages make the same decision, so the two
    cannot drift apart silently."""
    from backend.app import app
    app.config['TESTING'] = True
    served = [l['code'] for l in app.test_client().get('/api/languages').get_json()['languages']]
    assert [c for c, _ in site_facts.languages()] == served


def test_sentence_names_every_served_language():
    text = site_facts.holdings_sentence()
    for _, label in site_facts.languages():
        assert label in text
    assert 'intertextual parallels' in text


def test_sentence_follows_the_collections_present(monkeypatch, tmp_path):
    """With no collection data the sentence stops at the literature; with an
    events database present it names the events."""
    monkeypatch.setenv('TESSERAE_DOCUMENTS', '0')
    monkeypatch.setenv('TESSERAE_EVENTS_DB', str(tmp_path / 'none.sqlite'))
    monkeypatch.setenv('TESSERAE_COINS_DB', str(tmp_path / 'none2.sqlite'))
    monkeypatch.setattr(site_facts, 'collections', lambda: [])
    assert 'also holds' not in site_facts.build_holdings_sentence()

    monkeypatch.undo()
    site_facts.reset_cache()
    db = tmp_path / 'events.sqlite'
    sqlite3.connect(db).close()
    monkeypatch.setenv('TESSERAE_EVENTS_DB', str(db))
    keys = [k for k, _ in site_facts.collections()]
    assert 'events' in keys
    assert 'historical events' in site_facts.build_holdings_sentence()


def test_prompt_and_canned_answer_use_the_live_sentence():
    from backend.assistant import prompts, router
    text = site_facts.holdings_sentence()
    assert text in prompts.guide_system()
    assert 'Hebrew, English and Coptic literature' not in prompts.guide_system()
    answer = router.route('What languages does Tesserae support?')
    assert answer and text.split('.')[0] in answer


def test_cache_refreshes_after_ttl(monkeypatch):
    first = site_facts.holdings_sentence()
    monkeypatch.setattr(site_facts, 'build_holdings_sentence', lambda: 'changed')
    assert site_facts.holdings_sentence() == first
    site_facts._cache['at'] -= site_facts._TTL + 1
    assert site_facts.holdings_sentence() == 'changed'


def test_prompt_module_builds_nothing_at_import():
    """The holdings sentence is built per request, never when prompts.py is
    imported (that happens before the language plugins register)."""
    from backend.assistant import prompts
    assert not hasattr(prompts, 'GUIDE_SYSTEM')


def test_a_three_language_sentence_is_not_cached(monkeypatch):
    from backend.assistant import site_facts
    site_facts.reset_cache()
    monkeypatch.setattr(site_facts, 'languages', lambda: [('la', 'Latin'), ('grc', 'Greek'), ('en', 'English')])
    first = site_facts.holdings_sentence()
    assert 'Latin, Greek and English' in first
    assert site_facts._cache['text'] is None
    monkeypatch.setattr(site_facts, 'languages', lambda: [('la', 'Latin'), ('grc', 'Greek'), ('en', 'English'), ('ur', 'Urdu')])
    second = site_facts.holdings_sentence()
    assert 'Urdu' in second
    assert site_facts._cache['text'] == second
    site_facts.reset_cache()
