"""Capitalize the first letter of the label of carved People & Places entries (entity_id ending :r<number>).

The regroup (PR #1118) named each carved entry after its commonest spelling, and some spellings came from a
lower-case source (hecataeus, sextius, aegae). For those entries, when the first letter of `entities.label` is a
lower-case Latin letter, the label, the three display label columns of `entity_labels`, the `search_names` rows
that hold the old label exactly, and the label fields of the `entity_catalog` JSON (label, display_label,
display_label_la, display_label_grc) get a capital first letter. Greek, Hebrew and other scripts are left as they
are, and nothing else changes (not the forms, form_stems, label_key or folded_label).

    python scripts/entities/capitalize_carved_labels.py STORE_COPY            dry run, prints the count and examples
    python scripts/entities/capitalize_carved_labels.py STORE_COPY --apply    changes the copy

Refuses any path under /var/www: work on a copy, then install it.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import unicodedata

CARVED = re.compile(r':r\d+$')
LABEL_FIELDS = ('label', 'display_label', 'display_label_la', 'display_label_grc')


def cap(s):
    """`s` with its first letter in capitals when that letter is a lower-case Latin letter, else `s`."""
    if s and unicodedata.name(s[0], '').startswith('LATIN SMALL LETTER'):
        return s[0].upper() + s[1:]
    return s


def targets(db):
    """[(eid, entity_id, label)] of carved entries whose label starts with a lower-case Latin letter."""
    return [(eid, eid_s, label) for eid, eid_s, label in db.execute('select eid, entity_id, label from entities')
            if CARVED.search(eid_s or '') and cap(label or '') != (label or '')]


def apply(db, rows):
    """Change the rows of `targets` in the store. Returns the number of entries changed."""
    for eid, _entity_id, label in rows:
        new = cap(label)
        db.execute('update entities set label = ? where eid = ?', (new, eid))
        for col in ('display_label', 'display_label_la', 'display_label_grc'):
            v = db.execute(f'select {col} from entity_labels where eid = ?', (eid,)).fetchone()  # nosec B608 - fixed column names
            if v and v[0] and cap(v[0]) != v[0]:
                db.execute(f'update entity_labels set {col} = ? where eid = ?', (cap(v[0]), eid))  # nosec B608 - fixed column names
        db.execute('update search_names set name = ? where eid = ? and name = ?', (new, eid, label))
        r = db.execute('select data from entity_catalog where eid = ?', (eid,)).fetchone()
        if r and r[0]:
            d = json.loads(r[0])
            for k in LABEL_FIELDS:
                if isinstance(d.get(k), str):
                    d[k] = cap(d[k])
            db.execute('update entity_catalog set data = ? where eid = ?', (json.dumps(d, ensure_ascii=False), eid))
    db.commit()
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('store')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    if os.path.realpath(a.store).startswith('/var/www'):
        sys.exit('refusing a store under /var/www: copy it first')
    db = sqlite3.connect(a.store)
    rows = targets(db)
    print(f'{len(rows)} carved entries have a lower-case Latin first letter')
    for _eid, entity_id, label in rows[:5]:
        print(f'  {entity_id}: {label} -> {cap(label)}')
    if a.apply:
        print(f'changed {apply(db, rows)}; integrity_check {db.execute("pragma integrity_check").fetchone()[0]}')


if __name__ == '__main__':
    main()
