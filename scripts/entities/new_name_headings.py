"""Heading corrections for the names a build added (see backend/entity_heading_rules.py).

    python scripts/entities/new_name_headings.py STORE NEW_ENTITIES.csv --before STORE_BEFORE --out headings.tsv

Reads STORE and changes nothing in it. Covers the entities listed in the csv that still exist, plus any entity of
STORE that STORE_BEFORE does not have (names carved from them by the regroup). Writes a table: entity_id, old
heading, new heading, rule or model, evidence. Where the heading looks oblique and no nominative occurs among the
spellings, the gateway model is asked (the free campus model, address and key read by regroup_names.gateway()).
"""
import argparse
import csv
import os
import re
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend import entity_heading_rules as hr  # noqa: E402
from backend import entity_promote as pr  # noqa: E402
from backend import entity_regroup as rg  # noqa: E402

SYSTEM = (
    'You help catalog proper names in ancient Latin and Greek texts. You are given the spellings found for one '
    'name, with counts, and one line of text. The current heading may be an inflected form (an accusative, '
    'genitive, dative or ablative). Give the heading a reference index should carry: the nominative singular of '
    'the name, in the script and spelling pattern of the spellings (Childeberthi, Childeberthum give '
    'Childeberthus; Ἀβειβάλου gives Ἀβείβαλος). A name that is plural by nature, such as a people or a city like '
    'Athenae, keeps its nominative plural. If the current heading is already right, repeat it unchanged. Reply '
    'with one line only: HEADING: <the heading>')


def common_prefix(a, b):
    a, b = pr._plain(a), pr._plain(b)
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return a[:n]


def ask_heading(url, key, heading, forms, line):
    user = ('Current heading: %s\nSpellings: %s\nLine: %s' % (
        heading, ', '.join(f'{f} ({n})' for f, n in sorted(forms.items(), key=lambda x: -x[1])[:10]), line))
    reply = rg.ask(url, key, user, {}, system=SYSTEM, think=False, max_tokens=60)
    m = re.search(r'HEADING:\s*(\S+)', reply or '')
    return m.group(1).strip('.,;') if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('store')
    ap.add_argument('csv')
    ap.add_argument('--before', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--no-model', action='store_true')
    a = ap.parse_args()
    ids = {r['entity_id'] for r in csv.DictReader(open(a.csv, encoding='utf-8'))}
    db = sqlite3.connect(a.store)
    before = {r[0] for r in sqlite3.connect(a.before).execute('select entity_id from entities')}
    ids |= {r[0] for r in db.execute('select entity_id from entities') if r[0] not in before}
    out, asks, rejected = [], [], []
    n_scanned = 0
    for entity_id, eid, label in db.execute('select entity_id, eid, label from entities'):
        if entity_id not in ids:
            continue
        n_scanned += 1
        forms = dict(db.execute('select form, count(*) from mention_rows where eid = ? group by form', (eid,)))
        if not forms:
            continue
        r = hr.propose(label, forms)
        if r is None:
            continue
        rule, new, ev = r
        if rule == 'rule':
            out.append((entity_id, label, new, 'rule', '; '.join(ev)))
        else:
            asks.append((entity_id, eid, label, forms, ev))
    if asks and not a.no_model:
        import regroup_names as rn
        url, key = rn.gateway()
        lines = rg.Lines(rn.WINDOWS)

        work = [(x, rg.example_lines(db, lines, x[1], list(x[3]), n=1)) for x in asks]     # the store is read in this thread

        def one(item):
            x, ex = item
            return x, ask_heading(url, key, x[2], x[3], ex[0][:300] if ex else '')
        with ThreadPoolExecutor(4) as pool:
            for (entity_id, eid, label, forms, ev), new in pool.map(one, work):
                if not new or new == label:
                    continue
                if pr.script_of(new) != pr.script_of(label) or len(common_prefix(new, label)) < 3:
                    rejected.append((entity_id, label, new))
                    continue
                note = '' if new in forms else ' (not among the spellings)'
                out.append((entity_id, label, new, 'model', '; '.join(ev) + note))
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write('entity_id\told_heading\tnew_heading\trule_or_model\tevidence\n')
        for row in sorted(out):
            f.write('\t'.join(row) + '\n')
    print(f'scanned {n_scanned} entities, {len(out)} heading corrections ({sum(1 for r in out if r[3] == "rule")} by rule, '
          f'{sum(1 for r in out if r[3] == "model")} by model), {len(asks)} asked, {len(rejected)} model answers rejected (other script or no common start)')


if __name__ == '__main__':
    main()
