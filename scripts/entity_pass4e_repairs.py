"""Entity mentions, pass 4e contents (2026-10-20): repair six faults in what single entities hold.

    venv/bin/python scripts/entity_pass4e_repairs.py --store IN.sqlite [--out OUT.sqlite] [--apply] [--report FILE.json]

Without --apply nothing is written. The run counts what each repair would move and prints the table. With
--apply the store IN is copied to OUT (never written in place), the repairs run, the search names made from the
spellings and the catalog are rebuilt, and the integrity check is printed.

The six repairs, each found by reading the entity (the faults named in the stage 4 report):
    1 cypris     Κύπρις and its case forms leave the Cypriots (people) for the Cypris epithet entity. The store keeps an
                 epithet apart from the god unless the model named the epithet by the god's name (the rule of
                 promote_store, merge_target), and Latin Cypridis already sits in the entity Cypris.
    2 caresus    The Caresus river leaves the Carii (people) for a new place entity. The English word caresses is
                 not a name and its rows are dropped.
    3 geshur     Γεδσούρ leaves Gershom (person) for the existing place Geshur.
    4 terracina  Ταρρακίνα leaves Tarquinia (place) for the existing place Tarracina (the town of Anxur).
    5 nicopolis  The people headed Nicaeans is headed Nicopolitans (every row spells Nicopolis).
The sixth fault, the Greek -es veto, is code (backend/entity_mergeback.py) and not an operation on the store.
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend import entity_extras as extras  # noqa: E402
from backend import entity_index as ei  # noqa: E402
from backend import entity_promote as pr  # noqa: E402

# (key, source entity id, destination entity id, predicate on the folded spelling, drop predicate, label notes)
MOVES = [
    {'name': 'cypris', 'src': 'pn:κυπρ2', 'dst': 'pn:cyprid',
     'folds': {'κυπρισ', 'κυπριδοσ', 'κυπριδα', 'κυπριν', 'κυπρι'}, 'grc': 'Κύπρις'},
    {'name': 'caresus', 'src': 'pn:kares', 'dst': 'new:caresus',
     'folds': {'καρησοσ', 'καρησον', 'καρησηνησ', 'caresi'}, 'drop': {'caresses'}},
    {'name': 'geshur', 'src': 'pn:גרשון', 'dst': 'pn:geshu', 'folds': {'γεδσουρ'}, 'grc': 'Γεδσούρ'},
    {'name': 'terracina', 'src': 'pn:ταρκυν', 'dst': 'pn:tarracin', 'prefix': 'ταρρακιν', 'grc': 'Ταρρακίνη',
     'alias': 'pn:ταρρακιν',
     'description': 'Volscian town on the coast of Latium, called Anxur by the Volsci and Tarracina by the Romans.'},
]
NEW = {'caresus': {'entity_id': 'pn:caresus', 'type': 'place', 'label': 'Caresus', 'grc': 'Κάρησος', 'name_key': 'karesos',
                   'description': 'River of the Troad named in the Iliad (12.20) and described by Strabo (13.1).'}}
RENAME = {'entity_id': 'pn:νικοπολιτ', 'old': 'Nicaeans', 'new': 'Nicopolitans', 'old_names': ('Nicaeans', 'Nicaea'),
          'new_names': ('Nicopolitans', 'Nicopolis')}
WATCH = ['pn:κυπρ2', 'pn:cyprid', 'pn:kares', 'pn:caresus', 'pn:גרשון', 'pn:geshu', 'pn:ταρκυν', 'pn:tarracin', 'pn:νικοπολιτ']


def eid_of(db, entity_id):
    r = db.execute('select eid from entities where entity_id = ?', (entity_id,)).fetchone()
    return r[0] if r else None


def counts(db, entity_id):
    """{'eid', 'label', 'type', 'rows', 'windows', 'forms': {(spelling, language): rows}} of an entity, or None."""
    row = db.execute('select eid, label, type from entities where entity_id = ?', (entity_id,)).fetchone()
    if not row:
        return None
    forms = {}
    for f, lang, n in db.execute('select m.form, w.language, count(*) from mention_rows m join windows w using (wid) '
                                 'where m.eid = ? group by 1, 2', (row[0],)):
        forms[f'{f} [{lang}]'] = n
    return {'eid': row[0], 'label': row[1], 'type': row[2], 'rows': sum(forms.values()),
            'windows': db.execute('select count(distinct wid) from mention_rows where eid = ?', (row[0],)).fetchone()[0],
            'forms': forms}


def selected(db, eid, m):
    """The distinct spellings of entity eid that a repair moves."""
    out = set()
    for (f,) in db.execute('select distinct form from mention_rows where eid = ?', (eid,)):
        k = ei.fold(f)
        if k in m.get('folds', ()) or (m.get('prefix') and k.startswith(m['prefix'])):
            out.add(f)
    return out


def apply_all(db, log=print):
    done = {}
    next_eid = db.execute('select max(eid) from entities').fetchone()[0] + 1
    for m in MOVES:
        src = eid_of(db, m['src'])
        if src is None:
            raise SystemExit(f"repair {m['name']}: source {m['src']} not in the store")
        if m['dst'].startswith('new:'):
            spec = NEW[m['dst'][4:]]
            dst = next_eid
            next_eid += 1
            db.execute('insert into entities(eid, entity_id, type, label, source, name_key, distinctive, n_windows) '
                       "values (?,?,?,?,'promoted',?,0,0)", (dst, spec['entity_id'], spec['type'], spec['label'], spec['name_key']))
            db.execute('insert into entity_labels values (?,?,?,?,?)', (dst, spec['label'], spec['label'], spec['grc'], spec['description']))
            db.execute('insert into variants values (?,?,?,?,?)', (dst, ei.fold(spec['label']), '', 'form', 'promoted'))
            db.execute('insert into entity_aliases values (?,?,?,?,?)', (dst, spec['entity_id'], spec['label'], spec['type'], 'pass4e'))
        else:
            dst = eid_of(db, m['dst'])
            if dst is None:
                raise SystemExit(f"repair {m['name']}: destination {m['dst']} not in the store")
        forms = selected(db, src, m)
        folds = {ei.fold(f) for f in forms}
        moved, dropped = pr._move_rows(db, src, dst, folds)
        have = {f for (f,) in db.execute('select form from variants where eid = ?', (dst,))}
        var = db.execute('select rowid, form, language, role, source from variants where eid = ?', (src,)).fetchall()
        mv = [r for r in var if ei.fold(r[1]) in folds or (m.get('prefix') and ei.fold(r[1]).startswith(m['prefix']))]
        for rowid, f, lang, role, source in mv:
            if f in have:
                db.execute('delete from variants where rowid = ?', (rowid,))
            else:
                db.execute('update variants set eid = ? where rowid = ?', (dst, rowid))
                have.add(f)
        removed = 0
        for d in m.get('drop', ()):
            removed += db.execute('select count(*) from mention_rows where eid = ? and lower(form) = ?', (src, d)).fetchone()[0]
            db.execute('delete from mention_rows where eid = ? and lower(form) = ?', (src, d))
            db.execute('delete from variants where eid = ? and form = ?', (src, d))
        if m.get('alias'):
            db.execute('update entity_aliases set eid = ? where eid = ? and alias_id = ?', (dst, src, m['alias']))
        lab = db.execute('select display_label_grc, description from entity_labels where eid = ?', (dst,)).fetchone()
        if lab is not None and m.get('grc') and not lab[0]:
            db.execute('update entity_labels set display_label_grc = ? where eid = ?', (m['grc'], dst))
        if lab is not None and m.get('description') and not lab[1]:
            db.execute('update entity_labels set description = ? where eid = ?', (m['description'], dst))
        pr._refresh_windows(db, [src, dst])
        done[m['name']] = {'src': m['src'], 'dst': m['dst'] if not m['dst'].startswith('new:') else NEW[m['dst'][4:]]['entity_id'],
                           'spellings': sorted(forms), 'moved': moved, 'dropped_duplicates': dropped, 'dropped_not_a_name': removed,
                           'variants_moved': len(mv)}
    # the heading of the Nicopolitans
    e = eid_of(db, RENAME['entity_id'])
    db.execute('update entities set label = ? where eid = ?', (RENAME['new'], e))
    db.execute('update entity_labels set display_label = ?, display_label_la = ? where eid = ?', (RENAME['new'], RENAME['new'], e))
    db.execute('update variants set form = ? where eid = ? and form = ?', (RENAME['new'].lower(), e, RENAME['old'].lower()))
    for old, new in zip(RENAME['old_names'], RENAME['new_names']):
        db.execute("update search_names set name = ? where eid = ? and name = ? and source = 'model'", (new, e, old))
    done['nicopolis'] = {'entity': RENAME['entity_id'], 'from': RENAME['old'], 'to': RENAME['new']}
    return done


def tot(db):
    return (db.execute('select count(*) from entities').fetchone()[0], db.execute('select count(*) from mention_rows').fetchone()[0])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--store', required=True, help='the store to repair (read only)')
    ap.add_argument('--out', help='the repaired store to write (with --apply)')
    ap.add_argument('--apply', action='store_true', help='write the store; without it the run only counts')
    ap.add_argument('--report', help='write the before and after counts as JSON')
    a = ap.parse_args()
    ro = sqlite3.connect(f'file:{a.store}?mode=ro', uri=True)
    before = {k: counts(ro, k) for k in WATCH}
    print('entities, mention rows before', tot(ro))
    for m in MOVES:
        src = eid_of(ro, m['src'])
        forms = selected(ro, src, m)
        n = sum(before[m['src']]['forms'].get(f'{f} [{lang}]', 0) for f in forms for lang in ('la', 'grc', 'en', 'he'))
        print(f"{m['name']}: would move {n} rows of {len(forms)} spellings {sorted(forms)} from {m['src']} to {m['dst']}")
    if not a.apply:
        print('dry run, nothing written')
        return 0
    if not a.out or os.path.abspath(a.out) == os.path.abspath(a.store):
        raise SystemExit('--apply needs --out, a path other than --store')
    ro.close()
    if os.path.exists(a.out):
        os.remove(a.out)
    shutil.copyfile(a.store, a.out)
    db = sqlite3.connect(a.out)
    done = apply_all(db)
    extras.add_form_search_names(db)
    db.execute("delete from meta where key = 'pass4e_contents'")
    db.execute("insert into meta values ('pass4e_contents', ?)", (json.dumps(done, ensure_ascii=False),))
    db.commit()
    after_tot = tot(db)
    check = db.execute('pragma integrity_check').fetchone()[0]
    db.close()
    extras.write_catalog(a.out)
    db = sqlite3.connect(f'file:{a.out}?mode=ro', uri=True)
    after = {k: counts(db, k) for k in WATCH}
    print('entities, mention rows after', after_tot, 'integrity', check)
    if a.report:
        json.dump({'before': before, 'after': after, 'done': done, 'totals_after': after_tot, 'integrity': check},
                  open(a.report, 'w'), ensure_ascii=False, indent=1)
    return 0 if check == 'ok' else 1


if __name__ == '__main__':
    sys.exit(main())
