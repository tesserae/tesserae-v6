"""Tessa's "where do I start" answer: the same six choices as the Start here panel."""
import os
import re

from backend.assistant import front_door, router

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, 'client', 'src', 'components', 'search', 'frontDoor.js')


def test_fires_for_short_start_questions():
    for q in ('where do I start?', 'How does this work', 'What can I do here?', 'Getting started'):
        assert router.route(q) == front_door.answer(), q


def test_does_not_fire_for_a_question_about_a_topic():
    assert router.route("where do I start with Lucan's storms at sea") != front_door.answer()
    assert router.route('what is theme search') != front_door.answer()


def test_a_long_question_with_a_marker_does_not_fire():
    q = 'how does this work when I compare the Aeneid with the Thebaid in Latin'
    assert router.route(q) != front_door.answer()


def test_answer_names_all_six_labels_and_paths():
    text = front_door.answer()
    assert len(front_door.FRONT_DOOR_CHOICES) == 6
    for label, detail, path in front_door.FRONT_DOOR_CHOICES:
        assert f'[{label}]({path}): {detail}' in text
    assert text.startswith('This site does six kinds of thing.')
    assert text.endswith('Say which one and I will set it up.')


def test_backend_choices_match_the_frontend_file():
    source = open(FRONTEND, encoding='utf-8').read()
    for label, detail, path in front_door.FRONT_DOOR_CHOICES:
        assert f"label: '{label}'" in source
        assert f"detail: '{detail}'" in source
        assert f"href: '{path}'" in source
    assert len(re.findall(r"\bid: '", source)) == 6
