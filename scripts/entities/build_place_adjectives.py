"""Build data/entity_index/place_adjectives.json: for each place, the corpus names that are its Latin adjectives.

    venv/bin/python scripts/entities/build_place_adjectives.py --tsv territory_adjectives.tsv --texts window_texts.db [--write]
    venv/bin/python scripts/entities/build_place_adjectives.py --check

The TSV is the list of corpus-name entities whose forms are Latin adjectives of a place in the store (columns
corpus_name_eid, corpus_name_label, place_eid, place_label, ...). Numeric eids change at a store rebuild, so the
script resolves each to its entity_id through the store and writes only entity_ids. A row whose label in the store
differs from the label in the TSV stops the run (the eids are from another store).

Left out: Gordianus (the emperor, not Gordion) and Phradates (a Persian name, not Phra). For Tusculanum, a line
group is excluded when every occurrence of its form is followed within two words by disputatio or a form of it
(Cicero's Tusculanae disputationes is a book title). A line group is the unit the page counts: the line reference
and the form key. Rows with no line reference are never excluded.

Without --write nothing is written and the counts are printed. --check reads the JSON and the store and exits 1 if
an entity_id in the JSON is not in the store or its place is not a place. The page ignores an id it cannot find.
"""
import argparse
import csv
import json
import os
import re
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_STORE = os.path.join(ROOT, 'data', 'entity_index', 'entities.sqlite')
DEFAULT_OUT = os.path.join(ROOT, 'data', 'entity_index', 'place_adjectives.json')

LEAVE_OUT = {'Gordianus': 'the emperor, not Gordion', 'Phradates': 'a Persian name, not Phra'}
# label of the adjective entity -> stem that must follow within two words for the line to be a book title
BOOK_TITLE = {'Tusculanum': 'disput'}
LINE_GROUP = "coalesce(m.line_ref, '#' || m.wid) || '|' || coalesce(m.form_key, lower(m.form))"


def _ro(path):
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


def followed_by(text, form, stem):
    """[bool] one per occurrence of the form in the text: a word starting with stem within the next two words."""
    out = []
    for m in re.finditer(r'(?<!\w)' + re.escape(form) + r'(?!\w)', text or '', re.I):
        nxt = re.findall(r'\w+', text[m.end():m.end() + 80])[:2]
        out.append(any(w.lower().startswith(stem) for w in nxt))
    return out


def book_title_groups(db, texts, eid, stem):
    """{(work, group key)} of the line groups of entity eid whose every row is a book title, and the count of rows."""
    groups = {}
    for form, lr, wid, window_id, work, key in db.execute(
            f'select m.form, m.line_ref, m.wid, w.window_id, w.work, {LINE_GROUP} from mention_rows m '  # nosec B608
            'join windows w on w.wid = m.wid where m.eid = ?', (eid,)):
        row = texts.execute('select text from window_texts where id = ?', (window_id,)).fetchone()
        flags = followed_by(row[0] if row else '', form, stem)
        title = bool(flags) and all(flags) and lr is not None
        g = groups.setdefault((work, key), [])
        g.append(title)
    excluded = {k for k, v in groups.items() if all(v)}
    rows = sum(len(groups[k]) for k in excluded)
    return excluded, rows


def build(tsv, store, texts_path):
    db = _ro(store)
    texts = _ro(texts_path)
    places = {}
    report = {'left_out': [], 'tusculanae_rows_removed': 0, 'tusculanae_lines_removed': 0}

    def entity(eid):
        r = db.execute('select entity_id, label, type, source from entities where eid = ?', (eid,)).fetchone()
        if r is None:
            sys.exit(f'eid {eid} is not in the store {store}')
        return r

    with open(tsv, encoding='utf-8') as f:
        for row in csv.DictReader(f, delimiter='\t'):
            label = row['corpus_name_label']
            if label in LEAVE_OUT:
                report['left_out'].append((label, LEAVE_OUT[label]))
                continue
            adj_id, adj_label, _t, adj_src = entity(int(row['corpus_name_eid']))
            place_id, place_label, place_type, _s = entity(int(row['place_eid']))
            if adj_label != label or adj_src != 'names':
                sys.exit(f'eid {row["corpus_name_eid"]} is {adj_label!r} ({adj_src}) in the store, {label!r} in the TSV')
            if place_label != row['place_label'] or place_type != 'place':
                sys.exit(f'eid {row["place_eid"]} is {place_label!r} ({place_type}) in the store, {row["place_label"]!r} in the TSV')
            adj = {'entity_id': adj_id, 'label': adj_label, 'exclude_lines': []}
            eid = int(row['corpus_name_eid'])
            if label in BOOK_TITLE:
                excluded, nrows = book_title_groups(db, texts, eid, BOOK_TITLE[label])
                adj['exclude_lines'] = [{'work': w, 'key': k} for w, k in sorted(excluded)]
                report['tusculanae_rows_removed'] += nrows
                report['tusculanae_lines_removed'] += len(excluded)
            place = places.setdefault(place_id, {'label': place_label, 'adjectives': []})
            place['adjectives'].append(adj)
            adj['_eid'] = eid
    # rows and lines after the exclusions
    n_rows = n_lines = 0
    for place in places.values():
        for adj in place['adjectives']:
            eid = adj.pop('_eid')
            ex = {(x['work'], x['key']) for x in adj['exclude_lines']}
            seen = set()
            for work, key in db.execute(
                    f'select w.work, {LINE_GROUP} from mention_rows m join windows w on w.wid = m.wid '  # nosec B608
                    'where m.eid = ?', (eid,)):
                if (work, key) in ex:
                    continue
                n_rows += 1
                seen.add((work, key))
            n_lines += len(seen)
    report.update(places=len(places), adjectives=sum(len(p['adjectives']) for p in places.values()),
                  rows=n_rows, lines=n_lines)
    return {'version': 1, 'places': places}, report


def check(path, store):
    """The ids of the JSON that the store does not hold, as messages."""
    with open(path, encoding='utf-8') as f:
        places = json.load(f).get('places') or {}
    db = _ro(store)
    bad = []
    for pid, p in places.items():
        r = db.execute('select type from entities where entity_id = ?', (pid,)).fetchone()
        if r is None or r[0] != 'place':
            bad.append(f'place {pid} ({p.get("label")}) is not a place entity in the store')
        for a in p.get('adjectives', []):
            r = db.execute('select source from entities where entity_id = ?', (a['entity_id'],)).fetchone()
            if r is None or r[0] != 'names':
                bad.append(f'adjective {a["entity_id"]} ({a.get("label")}) is not a corpus name (source names) in the store')
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--tsv')
    ap.add_argument('--texts', help='window_texts.db, to find the book-title lines')
    ap.add_argument('--store', default=DEFAULT_STORE)
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.check:
        bad = check(a.out, a.store)
        for b in bad:
            print(b)
        print('OK: every id in the file is in the store' if not bad else f'{len(bad)} ids missing')
        return 1 if bad else 0
    if not (a.tsv and a.texts):
        ap.error('--tsv and --texts are required to build')
    data, rep = build(a.tsv, a.store, a.texts)
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    if a.write:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write('\n')
        print('wrote', a.out)
        bad = check(a.out, a.store)
        for b in bad:
            print(b)
        return 1 if bad else 0
    print('dry run, nothing written')
    return 0


if __name__ == '__main__':
    sys.exit(main())
