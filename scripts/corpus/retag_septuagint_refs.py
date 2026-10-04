#!/usr/bin/env python3
"""Rewrite the stored references of a corpus file whose line tags carried
a CTS URN instead of the plain form the rest of the corpus uses.

Two retaggings use this script, selected with --work (default 'septuagint',
so an existing call with no --work still does exactly what it always did):

- septuagint (#564, #578): 21 Septuagint files, retagged in the repository
    <septuaginta.tlg001 urn:cts:greekLit:tlg0527.tlg001.1st1K-grc1.1.1>  ->  <septuaginta.genesis 1.1>
    <septuaginta.daniel_theodotionis urn:cts:...tlg057.1st1K-grc1.1.1>  ->  <septuaginta.daniel_theodotionis 1.1>
- herodian: the 26 lines of aelius_herodianus.on_enclitics.tess, retagged
  by scripts/corpus/retag_herodian_refs.py
    <aelius_herodianus. urn:cts:greekLit:tlg0087.tlg002.1st1K-grc1.1>  ->  <aelius_herodianus.on_enclitics 1>

Every store that keeps the reference string must follow: the passage
index's window_texts.db (lines.ref, window_texts.ref_start, ref_end), its
descriptions.jsonl (ref_start, ref_end) and the connections-map caches
(windows.ref_start, ref_end). For the Septuagint retag the search index is
also rebuilt for the 21 files by scripts/corpus/add_texts_to_index.py
--replace, and the lemma caches by scripts/batch_lemma_cache.py, both keyed
on file contents; the single Herodian file needs the same two steps.

Usage (from the production checkout, inside a tess-job scope):
  python scripts/corpus/retag_septuagint_refs.py                      # dry run, Septuagint, counts only
  python scripts/corpus/retag_septuagint_refs.py --apply              # rewrite, Septuagint, with .bak copies
  python scripts/corpus/retag_septuagint_refs.py --work herodian --apply   # rewrite, Herodian, with .bak copies
"""
import argparse
import glob
import json
import os
import re
import shutil
import sqlite3
import sys
import time

TLG_TO_BOOK = {
    'tlg001': 'genesis', 'tlg002': 'exodus', 'tlg003': 'levitikon', 'tlg004': 'arithmoi',
    'tlg005': 'deuteronomion', 'tlg006': 'josue', 'tlg008': 'kritai', 'tlg010': 'ruth',
    'tlg011': 'basileion_a', 'tlg012': 'basileion_b', 'tlg013': 'basileion_g', 'tlg014': 'basileion_d',
    'tlg016': 'paralipomenon_b', 'tlg018': 'esdras_b', 'tlg024': 'machabaeorum_b',
    'tlg025': 'machabaeorum_g', 'tlg026': 'machabaeorum_d', 'tlg035': 'psalmi_salomonis',
    'tlg059': 'bel_et_draco_theodotionis',
}
_URN_SEPTUAGINT = re.compile(r'septuaginta\.(tlg\d{3}|[a-z_]+) urn:cts:greekLit:tlg0527\.tlg\d{3}\.1st1K-grc1\.(\S+)')
_URN_HERODIAN = re.compile(r'aelius_herodianus\. urn:cts:greekLit:tlg0087\.tlg002\.1st1K-grc1\.(\d+)')


def septuagint_new_ref(ref):
    """The plain reference for an old Septuagint one, or the input unchanged."""
    m = _URN_SEPTUAGINT.fullmatch(ref.strip())
    if not m:
        return ref
    head, rest = m.group(1), m.group(2)
    book = TLG_TO_BOOK.get(head, head if not head.startswith('tlg') else None)
    if book is None:
        raise SystemExit(f'no book for {ref!r}')
    return f'septuaginta.{book} {rest}'


def herodian_new_ref(ref):
    """The plain reference for an old Herodian one, or the input unchanged."""
    m = _URN_HERODIAN.fullmatch(ref.strip())
    if not m:
        return ref
    return f'aelius_herodianus.on_enclitics {m.group(1)}'


WORKS = {
    'septuagint': {
        'like_pattern': '%urn:cts:greekLit:tlg0527%',
        'new_ref': septuagint_new_ref,
        'backup_tag': 'lxxrefs',
    },
    'herodian': {
        'like_pattern': '%urn:cts:greekLit:tlg0087%',
        'new_ref': herodian_new_ref,
        'backup_tag': 'herodianrefs',
    },
}


def rewrite_sqlite(path, table_cols, apply, like_pattern, new_ref):
    con = sqlite3.connect(path)
    total = 0
    for table, cols in table_cols:
        for col in cols:
            rows = con.execute(f'SELECT rowid, "{col}" FROM "{table}" WHERE "{col}" LIKE ?',  # nosec B608
                               (like_pattern,)).fetchall()
            total += len(rows)
            if apply:
                con.executemany(f'UPDATE "{table}" SET "{col}"=? WHERE rowid=?',  # nosec B608
                                [(new_ref(v), rid) for rid, v in rows])
    if apply:
        con.commit()
    con.close()
    return total


def rewrite_jsonl(path, fields, apply, needle, new_ref):
    rows = [json.loads(l) for l in open(path, encoding='utf-8') if l.strip()]
    n = 0
    for r in rows:
        for f in fields:
            v = r.get(f)
            if isinstance(v, str) and needle in v:
                r[f] = new_ref(v); n += 1
    if apply:
        with open(path, 'w', encoding='utf-8') as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default='.')
    ap.add_argument('--work', choices=sorted(WORKS), default='septuagint')
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    os.chdir(a.root)
    cfg = WORKS[a.work]
    like_pattern, new_ref, backup_tag = cfg['like_pattern'], cfg['new_ref'], cfg['backup_tag']
    needle = like_pattern.strip('%')
    stamp = time.strftime('%Y%m%d-%H%M%S')
    stores = [('data/passage_index/window_texts.db', [('lines', ['ref']), ('window_texts', ['ref_start', 'ref_end'])])]
    stores += [(p, [('windows', ['ref_start', 'ref_end'])]) for p in sorted(glob.glob('cache/connections_map/*.db'))]
    for path, table_cols in stores:
        if not os.path.exists(path):
            print(f'  missing: {path}'); continue
        if a.apply:
            shutil.copy2(path, f'{path}.bak-{backup_tag}-{stamp}')
        n = rewrite_sqlite(path, table_cols, a.apply, like_pattern, new_ref)
        print(f'  {path}: {n} values' + (' rewritten' if a.apply else ' to rewrite'))
    p = 'data/passage_index/descriptions.jsonl'
    if os.path.exists(p):
        if a.apply:
            shutil.copy2(p, f'{p}.bak-{backup_tag}-{stamp}')
        n = rewrite_jsonl(p, ['ref_start', 'ref_end'], a.apply, needle, new_ref)
        print(f'  {p}: {n} values' + (' rewritten' if a.apply else ' to rewrite'))
    print('done' if a.apply else 'dry run; add --apply to rewrite (backups are made first)')


if __name__ == '__main__':
    main()
