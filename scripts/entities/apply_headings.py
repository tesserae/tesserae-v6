"""Set the heading of the entities listed in a headings table (see scripts/entities/new_name_headings.py).

    python scripts/entities/apply_headings.py STORE headings.tsv --dry
    python scripts/entities/apply_headings.py STORE headings.tsv --source rule

The table has the columns entity_id, old_heading, new_heading, rule_or_model, evidence. Only rows of the given
source are applied (default rule). A row is applied only when the entity still carries the old heading. The new
heading takes the capital of the old one. entities.label and entity_labels.display_label are set, and the Latin or
Greek display label too when it was the old heading. --dry prints what would change and writes nothing. After a real
run the catalog and the form index are rewritten.
"""
import argparse
import csv
import sqlite3
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


def capitalized_like(old, new):
    if old[:1].isupper() and new[:1].islower():
        return new[0].upper() + new[1:]
    return new


def apply_rows(db, rows, source='rule', dry=False):
    """rows: dicts of the table. Returns (changed [(entity_id, old, new)], skipped [(entity_id, why)])."""
    changed, skipped = [], []
    for r in rows:
        if r['rule_or_model'] != source:
            continue
        new = capitalized_like(r['old_heading'], r['new_heading'])
        e = db.execute('select eid, label from entities where entity_id = ?', (r['entity_id'],)).fetchone()
        if not e:
            skipped.append((r['entity_id'], 'no such entity'))
            continue
        if e[1] != r['old_heading']:
            skipped.append((r['entity_id'], f'heading is now {e[1]}'))
            continue
        changed.append((r['entity_id'], e[1], new))
        if dry:
            continue
        db.execute('update entities set label = ? where eid = ?', (new, e[0]))
        db.execute('update entity_labels set display_label = ? where eid = ? and display_label = ?', (new, e[0], e[1]))
        db.execute('update entity_labels set display_label_la = ? where eid = ? and display_label_la = ?', (new, e[0], e[1]))
        db.execute('update entity_labels set display_label_grc = ? where eid = ? and display_label_grc = ?', (new, e[0], e[1]))
    return changed, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('store')
    ap.add_argument('table')
    ap.add_argument('--source', default='rule', choices=('rule', 'model'))
    ap.add_argument('--dry', action='store_true')
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.table, encoding='utf-8'), delimiter='\t'))
    db = sqlite3.connect(a.store)
    changed, skipped = apply_rows(db, rows, a.source, a.dry)
    for c in changed:
        print('\t'.join(c))
    print(f'{len(changed)} headings {"would change" if a.dry else "changed"}, {len(skipped)} skipped {skipped[:5]}')
    if a.dry:
        return
    db.commit()
    db.close()
    from backend import entity_extras as ex
    ex.write_catalog(a.store)
    ex.write_form_index(a.store)
    db = sqlite3.connect(a.store)
    print('integrity', db.execute('pragma integrity_check').fetchone()[0])


if __name__ == '__main__':
    main()
