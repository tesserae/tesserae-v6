"""Passages Theme Search finds for an event, judged by the original labeling instructions."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'events'))

import add_theme_passages as A  # noqa: E402

EV = {'label': 'Battle of Actium', 'ds': -31, 'de': -31, 'place': 'Aktio', 'place_ancient': 'Actium',
      'participants': ['Cleopatra', 'Augustus', 'Marcus Vipsanius Agrippa', 'Mark Antony', 'Gaius Sosius'],
      'summary': 'The Battle of Actium was a naval battle. It ended Antony. A third sentence.', 'description': ''}


def test_two_queries_one_from_the_description_one_from_names():
    qs = A.queries_for(EV)
    assert len(qs) == 2
    assert qs[0].startswith('Battle of Actium, 31 BCE. The Battle of Actium was a naval battle. It ended Antony')
    assert 'third sentence' not in qs[0]
    assert qs[1] == 'Battle of Actium, 31 BCE, at Actium: Cleopatra, Augustus, Marcus Vipsanius Agrippa, Mark Antony'


def test_the_part_suffix_is_dropped_from_a_work():
    assert A.base_work('cassius_dio.roman_history.part.50') == 'cassius_dio.roman_history'
    assert A.base_work('suetonius.de_vita_caesarum.part.2.augustus') == 'suetonius.de_vita_caesarum'
    assert A.base_work('plutarch.antony') == 'plutarch.antony'


def test_labels_are_read_from_the_json_list_in_order():
    reply = 'Thinking first.\n[{"n": 1, "label": "yes"}, {"n": "3", "label": "No"}]'
    assert A.parse_labels(reply, 3) == ['yes', None, 'no']


def test_the_instructions_are_those_of_the_original_judge():
    assert 'A passage with the same participants in a different year is \'no\'.' in A.SYSTEM
    assert A.BATCH == 4
