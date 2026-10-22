"""Put Lavinium back together in the People & Places store (2026-10-21).

The stage 4 build filed the town of Lavinium under the river Labinios (Pleiades 393444), because the
river's Latin spelling Lavinius has the same stem. The corpus name Lavinium (Lavinia, Lavini, Lavinio),
its Greek spellings (Λαουίνιον) and a third corpus name wrongly headed "Lavinarium" (Laviniaque,
Laviniam) were merged into the river and so hidden from the search: typing Lavinium, Lavinia or
Laviniaque found nothing. The river kept the inscriptions of the Laurentes Lavinates as well.

This script, run on a copy of the store, makes one entry headed Lavinium out of the three corpus names,
takes it out of the river, gives it the documents that name Lavinium or its people, drops the spelling
Lavinius from the river (so the catalog does not attach Lavinium to it again), and rebuilds the stored
catalog. The river keeps its five Greek mentions (Λαβίνιος). The entry also holds the name Lavinia,
whose forms the corpus scan cannot tell from the adjective Lavinian or from the town.

    python scripts/entities/correct_lavinium.py STORE_COPY
"""
import sqlite3
import sys

from backend import entity_extras as extras
from backend import entity_index as ei
from backend import entity_mergeback as mb
from backend import entity_promote as pr

RIVER = 'pl:393444'
TOWN = 'nm:lauin:main'
INTO_TOWN = ('nm:lauin', 'nm:λαουιν:main')
RIVER_SPELLING = 'lauinius'
SEARCH_NAMES = ('Lavinium', 'Lavinia', 'Lavinian')
LABELS = ('Lavinium', 'Lavinium', 'Λαουίνιον',
          'Latin town south of Rome, in legend founded by Aeneas and named for Lavinia. '
          'The entry also holds the name Lavinia and the adjective Lavinian.')


def eid_of(db, entity_id):
    row = db.execute('select eid from entities where entity_id = ?', (entity_id,)).fetchone()
    if row is None:
        sys.exit(f'REFUSING: {entity_id} is not in the store')
    return row[0]


def correct(db):
    river, town = eid_of(db, RIVER), eid_of(db, TOWN)
    out = {}
    for entity_id in INTO_TOWN:
        out[entity_id] = mb.apply_merge(db, eid_of(db, entity_id), town, 'lavinium_correction_2026_10_21')
    db.execute('delete from entity_merges where eid = ?', (town,))
    db.execute("update entity_aliases set eid = ? where eid = ? and alias_id in ('pn:lauin', 'pn:λαουιν')",
               (town, river))
    db.execute('delete from variants where eid = ? and form = ?', (river, RIVER_SPELLING))
    db.execute('delete from search_names where eid = ? and lower(name) = ?', (river, RIVER_SPELLING))
    have = {(d, f) for d, f in db.execute('select doc_id, form from document_mentions where eid = ?', (town,))}
    docs = db.execute("select rowid, doc_id, form from document_mentions where eid = ? and form like 'lauin%'",
                      (river,)).fetchall()
    for rowid, doc_id, form in docs:
        if (doc_id, form) in have:
            db.execute('delete from document_mentions where rowid = ?', (rowid,))
        else:
            db.execute('update document_mentions set eid = ? where rowid = ?', (town, rowid))
    out['documents_moved'] = len(docs)
    names = {n.lower() for (n,) in db.execute('select name from search_names where eid = ?', (town,))}
    for n in SEARCH_NAMES:
        if n.lower() not in names:
            db.execute("insert into search_names values (?, ?, 'model')", (town, n))
    db.execute('delete from entity_labels where eid = ?', (town,))
    db.execute('insert into entity_labels values (?, ?, ?, ?, ?)', (town,) + LABELS)
    pr._refresh_windows(db, [town, river])
    out['town_windows'], = db.execute('select n_windows from entities where eid = ?', (town,)).fetchone()
    out['river_windows'], = db.execute('select n_windows from entities where eid = ?', (river,)).fetchone()
    return out


def main(path):
    db = sqlite3.connect(path)
    out = correct(db)
    db.commit()
    db.close()
    extras.write_catalog(path)
    print(out)
    print('folded check:', ei.fold('Lavinium'))


if __name__ == '__main__':
    main(sys.argv[1])
