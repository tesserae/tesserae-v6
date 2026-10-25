import importlib.util
import os
import sqlite3

spec = importlib.util.spec_from_file_location(
    'apply_headings', os.path.join(os.path.dirname(__file__), '..', 'scripts', 'entities', 'apply_headings.py'))
ah = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ah)


def store():
    db = sqlite3.connect(':memory:')
    db.execute('create table entities (eid integer primary key, entity_id text, label text)')
    db.execute('create table entity_labels (eid integer, display_label text, display_label_la text, display_label_grc text)')
    db.executemany('insert into entities values (?,?,?)', [(1, 'nm:a', 'Childeberthum'), (2, 'nm:b', 'Euboicum'), (3, 'nm:c', 'Moved')])
    db.executemany('insert into entity_labels values (?,?,?,?)', [(1, 'Childeberthum', 'Childeberthum', None), (2, 'Euboicum', 'Euboicum', None)])
    return db


ROWS = [
    {'entity_id': 'nm:a', 'old_heading': 'Childeberthum', 'new_heading': 'Childeberthus', 'rule_or_model': 'rule'},
    {'entity_id': 'nm:b', 'old_heading': 'Euboicum', 'new_heading': 'euboicus', 'rule_or_model': 'rule'},
    {'entity_id': 'nm:c', 'old_heading': 'Other', 'new_heading': 'Z', 'rule_or_model': 'rule'},
    {'entity_id': 'nm:a', 'old_heading': 'Childeberthum', 'new_heading': 'Wrong', 'rule_or_model': 'model'},
]


def test_dry_run_changes_nothing():
    db = store()
    changed, skipped = ah.apply_rows(db, ROWS, dry=True)
    assert [c[2] for c in changed] == ['Childeberthus', 'Euboicus']
    assert skipped == [('nm:c', 'heading is now Moved')]
    assert db.execute('select label from entities where eid = 1').fetchone()[0] == 'Childeberthum'


def test_apply_sets_labels_with_the_old_capital_and_leaves_model_rows():
    db = store()
    ah.apply_rows(db, ROWS)
    assert db.execute('select label from entities where eid = 2').fetchone()[0] == 'Euboicus'
    assert db.execute('select display_label, display_label_la from entity_labels where eid = 1').fetchone() == ('Childeberthus', 'Childeberthus')
