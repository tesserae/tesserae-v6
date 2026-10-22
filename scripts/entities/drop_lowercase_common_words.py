"""People & Places: remove lower-case Pliny rows that are plant, stone and other common words (2026-10-22).

scan_lowercase_work.py linked a lower-case form of the Natural History to an entry when its stem matched
a name's stem (the case-form rule for forms of six letters or more). Pliny's plant, stone and animal names
share stems with persons and places, so raphanus (radish) was filed under Raphania, lapathum (sorrel)
under Lapathus, gentiana (gentian) under Gentianus and galena (lead ore) under Galenus. A reading of the
lower-case forms rare outside Pliny gave the list below. Forms that may be the name itself (chironis,
memnonis, memnonia, melitis) are left.

    drop_lowercase_common_words.py STORE
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from backend import entity_extras as extras  # noqa: E402

# Folded forms (form_key), each a common word in the Natural History.
COMMON = {
    'raphani', 'raphanis', 'raphano', 'raphanus',            # radish
    'lapatho', 'lapathum',                                   # sorrel
    'gentiana', 'gentianam',                                 # gentian
    'galena', 'galenam', 'galenes',                          # lead ore
    'fullonia', 'fulloniae', 'fullonium',                    # of fullers
    'carduo',                                                # thistle
    'cyperis', 'cypero', 'cyperos',                          # galingale
    'baccaris',                                              # a plant
    'erythini', 'erythinis', 'erythinum', 'erythinus',       # a fish
    'hortensiis',                                            # garden plants
    'pelagia', 'pelagiae', 'pelagii',                        # of the sea
    'gorgonia',                                              # coral
    'chironia', 'chironiae', 'chironiam', 'chironii', 'chironium',  # plants named after Chiron
    'papulis',                                               # pimples
    'serapias',                                              # an orchid
    'hephaestitis',                                          # a stone
    'mercuriali', 'mercurialem',                             # the herb mercury
    'syagri', 'syagro', 'syagrorum',                         # a palm
    'prasio', 'prasiorum',                                   # a green stone
    'fulgentius',                                            # more brightly
    'melaena', 'melaenae',                                   # black
    'strategias',                                            # districts
    'nundinarium',                                           # of market days
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('store')
    a = ap.parse_args()
    import sqlite3
    db = sqlite3.connect(a.store)
    marks = ','.join('?' * len(COMMON))
    hit = db.execute(f"select rowid, eid from mention_rows where matcher = 'lowercase' and form_key in ({marks})",
                     sorted(COMMON)).fetchall()
    db.executemany('delete from mention_rows where rowid = ?', [(r,) for r, _ in hit])
    for eid in {e for _, e in hit}:
        n = db.execute('select count(distinct wid) from mention_rows where eid = ?', (eid,)).fetchone()[0]
        db.execute('update entities set n_windows = ? where eid = ?', (n, eid))
    db.commit()
    out = {'rows_removed': len(hit), 'entities_touched': len({e for _, e in hit}),
           'lowercase_rows_left': db.execute("select count(*) from mention_rows where matcher = 'lowercase'").fetchone()[0],
           'integrity': db.execute('pragma integrity_check').fetchone()[0]}
    db.close()
    extras.write_catalog(a.store)
    extras.write_form_index(a.store)
    print(json.dumps(out))


if __name__ == '__main__':
    sys.exit(main())
