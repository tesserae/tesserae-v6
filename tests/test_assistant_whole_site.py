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
