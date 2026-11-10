"""People & Places: remove entries that are not names of people or places, listed in a JSON file (2026-11-10).

The group one build of 2026-11-10 (CLLG Freed Corpus, 1,025 Greek works) filed 10,193 new corpus names.
A reading of the new labels found 103 that are not names: 93 three-letter all-capital tokens that are
geometric point labels in the mathematical works (ΒΞΓ, ΘΝΞ), five edition or manuscript sigla from the
scholia (MoSCHOP, ΜαΜβ), and five all-capital words with iota adscript from inscription-style text.
Each is a whole entry, so the entry and every row that refers to it go, then the catalog and the form
index are rebuilt. A later build of new works infers the drop from the absence (backend/entity_new_works.py).

    drop_label_tokens.py STORE DROP.json        DROP.json: [{"entity_id": ..., "label": ..., "reason": ...}, ...]
"""
import argparse
import json
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
from backend import entity_extras as extras  # noqa: E402

# Every table with an eid column other than entities itself (entity_catalog and form_entities are rebuilt).
EID_TABLES = ('variants', 'mention_rows', 'search_names', 'entity_labels', 'entity_aliases', 'entity_merges',
              'entity_catalog')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('store')
    ap.add_argument('drop_json')
    a = ap.parse_args()
    wanted = json.load(open(a.drop_json, encoding='utf-8'))
    ids = [d['entity_id'] for d in wanted]
    db = sqlite3.connect(a.store)
    marks = ','.join('?' * len(ids))
    found = db.execute(f'select eid, entity_id, label from entities where entity_id in ({marks})', ids).fetchall()
    missing = sorted(set(ids) - {r[1] for r in found})
    eids = [r[0] for r in found]
    out = {'listed': len(ids), 'found': len(found), 'missing': missing, 'removed': {}}
    emarks = ','.join('?' * len(eids))
    for t in EID_TABLES:
        n = db.execute(f'select count(*) from {t} where eid in ({emarks})', eids).fetchone()[0]
        db.execute(f'delete from {t} where eid in ({emarks})', eids)
        out['removed'][t] = n
    # mention rows that still refer to a removed entity through its list twin, if any, are none by construction
    out['removed']['form_entities'] = db.execute(f'select count(*) from form_entities where eid in ({emarks})', eids).fetchone()[0]
    db.execute(f'delete from form_entities where eid in ({emarks})', eids)
    db.execute(f'delete from entities where eid in ({emarks})', eids)
    db.commit()
    out['entities_after'] = db.execute('select count(*) from entities').fetchone()[0]
    out['mention_rows_after'] = db.execute('select count(*) from mention_rows').fetchone()[0]
    out['integrity'] = db.execute('pragma integrity_check').fetchone()[0]
    db.close()
    extras.write_catalog(a.store)
    extras.write_form_index(a.store)
    print(json.dumps(out, ensure_ascii=False))
    return 0 if not missing else 1


if __name__ == '__main__':
    sys.exit(main())
