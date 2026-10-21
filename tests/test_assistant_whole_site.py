"""Tessa's instructions name the whole site, not only the searches she can run (2026-10-21)."""
from backend.assistant import front_door, prompts


def test_the_guide_names_every_page_of_the_site():
    g = prompts.guide_system()
    for name in ('Search One Text', 'Theme Search', 'Reader', 'People & Places', 'Events', 'Similarity Map',
                 'Inscriptions & Papyri', 'Coins', 'Objects', 'Cross-Language', 'Browse Corpus'):
        assert name in g, name
    for label, _, _ in front_door.FRONT_DOOR_CHOICES:
        assert label in g


def test_the_guide_no_longer_says_only_the_tools_exist():
    g = prompts.guide_system()
    assert 'cover the whole site' in g
    assert 'Never recommend a search that is not in the list above' not in g


def test_search_type_questions_get_the_whole_site():
    from backend.assistant import front_door
    for q in ('what about search types', 'what kinds of search are there', 'where do i start',
              'what features does the site have'):
        assert front_door.matches_overview(q), q
    assert not front_door.matches_overview('what does the theme search find in ovid about storms at sea and shipwreck')
    text = front_door.overview()
    for name in ('Search One Text', 'People & Places', 'Events', 'Similarity Map', 'Coins', 'Objects', 'Collections'):
        assert name in text, name
    assert '](/events)' in text


def test_the_panel_route_answers_an_overview_question_without_the_model(monkeypatch):
    from backend.app import app
    from backend.blueprints import assistant as bp

    def boom(*a, **k):
        raise AssertionError('the model path must not run')
    monkeypatch.setattr(bp.agent, 'answer_stream', boom)
    r = app.test_client().post('/api/assistant/ask-stream', json={'question': 'what about search types?', 'history': []})
    body = r.get_data(as_text=True)
    assert 'Similarity Map' in body and 'People & Places' in body
