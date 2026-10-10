"""Tessa's answer to "where do I start?".

The same six choices as the "Start here" panel on the Search page
(client/src/components/search/frontDoor.js). The labels and paths here must
match that file, and tests/test_assistant_front_door.py checks that they do.
Change both together.

The Reader lives at /read and the Inscriptions & Papyri page at
/inscriptions-papyri (client/src/App.jsx, pathToPageType).
"""
import re

FRONT_DOOR_CHOICES = [
    ('Find where a phrase or a pair of words occurs', '/?tab=line'),
    ('Compare two works for shared language', '/?tab=parallel'),
    ('Find the rare words two works share', '/?tab=hapax'),
    ('Find passages about a subject, in any words', '/theme-search'),
    ('Read a text and see what each passage echoes', '/read'),
    ('Search inscriptions, papyri, events and coins', '/inscriptions-papyri?profile=everything'),
]

# Short questions that ask where to begin. Whole-phrase matches only, and only
# for a question of eight words or fewer, so "where do I start with Lucan's
# storms at sea" goes on to the model.
MARKERS = (
    'where do i start', 'where should i start', 'how do i use this',
    'how does this work', 'what can i do here', 'what does this site do',
    'what can i do', 'getting started', 'start here', 'how do i begin',
    'what is this',
)

MAX_WORDS = 8


def matches(normalised_question):
    """True when the (already normalised) question is a short request for a start."""
    words = normalised_question.split()
    if not words or len(words) > MAX_WORDS:
        return False
    q = ' '.join(words)
    return any(re.search(r'(?<![a-z0-9])' + re.escape(m) + r'(?![a-z0-9])', q) for m in MARKERS)


def answer():
    lines = ['This site does six kinds of thing.']
    lines += [f'- [{label}]({path})' for label, path in FRONT_DOOR_CHOICES]
    lines.append('Say which one and I will set it up.')
    return '\n'.join(lines)
