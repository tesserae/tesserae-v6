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


def test_keep_theme_additions_keeps_listed_events_only(tmp_path):
    import sqlite3
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location(
        'keep_theme_additions', os.path.join(os.path.dirname(__file__), '..', 'scripts', 'events', 'keep_theme_additions.py'))
    k = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(k)
    schema = 'CREATE TABLE passages (event_id TEXT, work TEXT, ref_start TEXT, found_by TEXT)'
    start, applied = tmp_path / 'start.sqlite', tmp_path / 'applied.sqlite'
    for p, rows in ((start, [('Q1', 'w', 'old', k.FOUND_BY), ('Q9', 'w', 'kept-before', k.FOUND_BY)]),
                    (applied, [('Q1', 'w', 'old', k.FOUND_BY), ('Q9', 'w', 'kept-before', k.FOUND_BY),
                               ('Q1', 'w', 'good', k.FOUND_BY), ('Q1', 'w', 'bad', k.FOUND_BY),
                               ('Q2', 'w', 'other', k.FOUND_BY), ('Q2', 'w', 'orig', None)])):
        db = sqlite3.connect(p)
        db.execute(schema)
        db.executemany('insert into passages values (?,?,?,?)', rows)
        db.commit()
        db.close()
    keep = tmp_path / 'keep.txt'
    keep.write_text('KEEP Q1\nDROP Q1 bad\n', encoding='utf-8')
    out = tmp_path / 'out.sqlite'
    k.main(str(start), str(applied), str(keep), str(out))
    got = sorted(r[0] for r in sqlite3.connect(out).execute('select ref_start from passages'))
    assert got == ['good', 'kept-before', 'old', 'orig']
