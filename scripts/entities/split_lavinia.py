"""Give Lavinia, daughter of Latinus, her own People & Places entry, apart from the town Lavinium (2026-10-21).

The corpus scan files every Lavinia, Lavinium and Lavinian under one name, and the 20:41 correction
(correct_lavinium.py) left them in one entry headed Lavinium. Each of its 185 mention rows was read by the
free gateway model (Qwen3.8 27B), with the passage around the word, as the person or as the town or its
adjective (Lavinia litora). The project lead's reading of the doubtful cases changed 13 of the model's
answers. The decisions are in lavinia_rows.csv (window id, spelling, refers_to, decided_by).

This script, run on a copy of the store, makes a promoted person entry pn:lauinia headed Lavinia, moves the
rows marked PERSON into it, makes the town a promoted place entry pn:lauinium (the old id nm:lauin:main kept
as an alias, so links keep working), and rebuilds the stored catalog and the spelling table.

    python scripts/entities/split_lavinia.py STORE_COPY
"""
import csv
import os
import sqlite3
import sys

from backend import entity_extras as extras
from backend import entity_promote as pr

ROWS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lavinia_rows.csv')
TOWN_OLD = 'nm:lauin:main'
TOWN, PERSON = 'pn:lauinium', 'pn:lauinia'
PERSON_FORMS = ('lauinia', 'lauiniae', 'lauiniam', 'lauinie', 'λαουινια', 'λαουινιαν')
PERSON_NAMES = ('Lavinia', 'Lavinia daughter of Latinus', 'Lavinia wife of Aeneas')
PERSON_LABELS = ('Lavinia', 'Lavinia', 'Λαουινία',
                 'Daughter of King Latinus, betrothed to Turnus and married to Aeneas.')
TOWN_LABELS = ('Lavinium', 'Lavinium', 'Λαουίνιον',
               'Latin town south of Rome, in legend founded by Aeneas and named for Lavinia. '
               'The entry also holds the adjective Lavinian.')


def decisions():
    out = {}
    with open(ROWS, newline='') as f:
        for r in csv.DictReader(f):
            key = (r['window_id'], r['form'])
            if out.get(key, r['refers_to']) != r['refers_to']:
                sys.exit(f'REFUSING: two decisions for {key}')
            out[key] = r['refers_to']
    return out


def split(db):
    row = db.execute('select eid from entities where entity_id = ?', (TOWN_OLD,)).fetchone()
    if row is None:
        sys.exit(f'REFUSING: {TOWN_OLD} is not in the store')
    town = row[0]
    if db.execute('select 1 from entities where entity_id = ?', (PERSON,)).fetchone():
        sys.exit(f'REFUSING: {PERSON} is already in the store')
    rows = db.execute('select m.rowid, w.window_id, m.form from mention_rows m join windows w on w.wid = m.wid '
                      'where m.eid = ?', (town,)).fetchall()
    want = decisions()
    missing = [(wid, form) for _r, wid, form in rows if (wid, form) not in want]
    if missing:
        sys.exit(f'REFUSING: {len(missing)} rows have no decision, first {missing[:3]}')
    person = db.execute('select max(eid) from entities').fetchone()[0] + 1
    db.execute("insert into entities (eid, entity_id, type, label, source, name_key, distinctive, n_windows) "
               "values (?, ?, 'person', 'Lavinia', 'promoted', 'lauin', 0, 0)", (person, PERSON))
    moved = [(person, rowid) for rowid, wid, form in rows if want[(wid, form)] == 'PERSON']
    db.executemany('update mention_rows set eid = ? where rowid = ?', moved)
    db.executemany("insert into variants values (?, ?, '', 'form', 'promoted')", [(person, f) for f in PERSON_FORMS])
    db.executemany("insert into search_names values (?, ?, 'model')", [(person, n) for n in PERSON_NAMES])
    db.execute('insert into entity_labels values (?, ?, ?, ?, ?)', (person,) + PERSON_LABELS)
    db.execute("update entities set entity_id = ?, type = 'place', source = 'promoted' where eid = ?", (TOWN, town))
    db.execute("insert into entity_aliases values (?, ?, 'Lavinium', 'name', 'lavinia_split_2026_10_21')",
               (town, TOWN_OLD))
    db.execute("update variants set source = 'promoted' where eid = ?", (town,))
    db.execute("delete from search_names where eid = ? and name = 'Lavinia'", (town,))
    db.execute('delete from entity_labels where eid = ?', (town,))
    db.execute('insert into entity_labels values (?, ?, ?, ?, ?)', (town,) + TOWN_LABELS)
    pr._refresh_windows(db, [town, person])
    n = dict(db.execute('select entity_id, n_windows from entities where eid in (?, ?)', (town, person)))
    return {'rows': len(rows), 'moved_to_person': len(moved), 'windows': n}


def main(path):
    db = sqlite3.connect(path)
    out = split(db)
    db.commit()
    db.close()
    extras.write_catalog(path)
    extras.write_form_index(path)
    print(out)


if __name__ == '__main__':
    main(sys.argv[1])
