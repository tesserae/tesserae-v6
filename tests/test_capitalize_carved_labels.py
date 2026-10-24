"""Capitalizing the labels of carved entries (scripts/entities/capitalize_carved_labels.py), on a fixture store."""
import importlib.util
import json
import os
import sqlite3

spec = importlib.util.spec_from_file_location(
    'ccl', os.path.join(os.path.dirname(__file__), '..', 'scripts', 'entities', 'capitalize_carved_labels.py'))
ccl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ccl)


def store():
    db = sqlite3.connect(':memory:')
    db.executescript('''create table entities (eid integer primary key, entity_id text, label text);
      create table entity_labels (eid integer primary key, display_label text, display_label_la text, display_label_grc text, description text);
      create table search_names (eid integer, name text, source text);
      create table entity_catalog (eid integer primary key, data text);''')
    rows = [(1, 'nm:hekat:r1', 'hecataeus'), (2, 'nm:ekata:r2', 'Ἑκαταῖος'),
            (3, 'nm:abc:r3', 'אדני'), (4, 'pn:rusell', 'rusellae'), (5, 'nm:sext:r1', 'Sextius'),
            (6, 'nm:aigai:r4', 'ægae')]
    for eid, ent, lab in rows:
        db.execute('insert into entities values (?,?,?)', (eid, ent, lab))
        db.execute('insert into entity_labels values (?,?,?,?,?)', (eid, lab, lab, None, 'd'))
        db.execute("insert into search_names values (?,?, 'model')", (eid, lab))
        db.execute("insert into search_names values (?,?, 'form')", (eid, 'hecat'))
        db.execute('insert into entity_catalog values (?,?)', (eid, json.dumps(
            {'label': lab, 'display_label': lab, 'forms': [lab], 'label_key': lab, 'form_stems': ['hecat']}, ensure_ascii=False)))
    return db


def test_only_carved_lower_case_latin_labels_are_targets():
    assert [t[1] for t in ccl.targets(store())] == ['nm:hekat:r1', 'nm:aigai:r4']


def test_apply_changes_the_label_fields_and_nothing_else():
    db = store()
    assert ccl.apply(db, ccl.targets(db)) == 2
    assert db.execute('select label from entities where eid = 1').fetchone()[0] == 'Hecataeus'
    assert db.execute('select display_label, display_label_la from entity_labels where eid = 1').fetchone() == ('Hecataeus', 'Hecataeus')
    assert db.execute("select name from search_names where eid = 1 and source = 'model'").fetchone()[0] == 'Hecataeus'
    assert db.execute("select name from search_names where eid = 1 and source = 'form'").fetchone()[0] == 'hecat'
    d = json.loads(db.execute('select data from entity_catalog where eid = 1').fetchone()[0])
    assert d['label'] == 'Hecataeus' and d['display_label'] == 'Hecataeus'
    assert d['forms'] == ['hecataeus'] and d['label_key'] == 'hecataeus' and d['form_stems'] == ['hecat']
    assert db.execute('select label from entities where eid = 6').fetchone()[0] == 'Ægae'
    # Greek, Hebrew, a non-carved id and an already capitalized label are untouched
    for eid in (2, 3, 4, 5):
        assert db.execute('select label from entities where eid = ?', (eid,)).fetchone()[0] == store().execute(
            'select label from entities where eid = ?', (eid,)).fetchone()[0]
    assert db.execute('select name from search_names where eid = 4 and source = "model"').fetchone()[0] == 'rusellae'
