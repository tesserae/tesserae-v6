#!/usr/bin/env python3
"""Repair malformed line tags in .tess files and in every store that copied them.

Fifty-four corpus files carry tags like "<sal.  Cat..58.15>" (a double space,
and a doubled period standing in for the space before the locus) or
"<pl. poen.  1>" (a double space). The rule is backend.utils.normalize_ref,
the same one the connector applies on output:

    "sal.  Cat..58.15" -> "sal. Cat. 58.15"     "pl. poen.  1" -> "pl. poen. 1"

Stores that hold the raw tag and are rewritten here, each behind its own flag:
  --texts          the .tess files (only the tag between < and > changes)
  --lemma-cache    cache/lemmas/<lang>/<stem>*.json: unit refs, and file_hash
                   set to the md5 of the repaired file so the cache stays valid
  --index          data/inverted_index/<lang>_index.db: lines.ref and
                   postings.ref for the affected texts (copy, update, swap)
  --passage-index  data/passage_index/descriptions.jsonl (ref_start/ref_end)
                   and window_texts.db (window_texts.ref_start/ref_end,
                   lines.ref) for the affected works
  --translations   data/translations/<lang>__<work>.json ref_to_unit keys
  --fusion-cache   delete cache/<hash>.json results whose source or target is
                   an affected text (they are recomputed on demand)

Default is a dry run that reports counts; --apply writes. Every rewritten
file or database gets a .bak-reftags-<date> copy first. --root points at the
checkout whose data is to be repaired (default: this repo).

    python scripts/corpus/repair_ref_tags.py --texts [--apply]
    python scripts/corpus/repair_ref_tags.py --root /var/www/tesseraev6_flask \
        --lemma-cache --index --passage-index --translations --fusion-cache --apply
"""
import glob
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
if '--root' in sys.argv and sys.argv.index('--root') + 1 >= len(sys.argv):
    raise SystemExit('--root needs a path')
ROOT = sys.argv[sys.argv.index('--root') + 1] if '--root' in sys.argv else REPO
APPLY = '--apply' in sys.argv
STAMP = time.strftime('%Y%m%d')
sys.path.insert(0, REPO)
from backend.utils import normalize_ref  # noqa: E402

def bad(tag):
    return '  ' in tag or '..' in tag


def affected_files(root):
    """(lang, filename) for every .tess whose tags need the rule, in every
    language directory (the same sweep as tests/test_tess_tags_clean.py)."""
    out = []
    for lang in sorted(os.listdir(os.path.join(root, 'texts'))):
        for path in sorted(glob.glob(os.path.join(root, 'texts', lang, '*.tess'))):
            with open(path, encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    if line.startswith('<'):
                        e = line.find('>')
                        if e > 0 and bad(line[1:e]):
                            out.append((lang, os.path.basename(path)))
                            break
    return out


def backup(path):
    if APPLY and os.path.exists(path):
        shutil.copy2(path, f'{path}.bak-reftags-{STAMP}')


def fix_texts(root, files):
    total = 0
    for lang, fn in files:
        path = os.path.join(root, 'texts', lang, fn)
        lines = open(path, encoding='utf-8').read().split('\n')
        n = 0
        out = []
        for line in lines:
            if line.startswith('<') and '>' in line:
                e = line.index('>')
                tag = line[1:e]
                new = normalize_ref(tag)
                if new != tag:
                    n += 1
                line = '<' + new + line[e:]
            out.append(line)
        assert len(out) == len(lines)
        assert [l.split('>', 1)[-1] if l.startswith('<') else l for l in out] == \
               [l.split('>', 1)[-1] if l.startswith('<') else l for l in lines], fn
        total += n
        print(f'  texts  {lang}/{fn}: {n} tags')
        if APPLY:
            backup(path)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write('\n'.join(out))
    print(f'texts: {total} tags in {len(files)} files')


def fix_lemma_cache(root, files):
    total = 0
    for lang, fn in files:
        stem = fn[:-5]
        text_path = os.path.join(root, 'texts', lang, fn)
        new_hash = hashlib.md5(open(text_path, 'rb').read()).hexdigest()  # nosec B324
        for cpath in glob.glob(os.path.join(root, 'cache', 'lemmas', lang, stem + '.json')) + \
                glob.glob(os.path.join(root, 'cache', 'lemmas', lang, stem + '-*.json')):
            d = json.load(open(cpath, encoding='utf-8'))
            n = 0
            for key in ('units_line', 'units_phrase'):
                for u in d.get(key) or []:
                    if isinstance(u, dict) and u.get('ref'):
                        new = normalize_ref(u['ref'])
                        if new != u['ref']:
                            u['ref'] = new
                            n += 1
            hash_changed = d.get('file_hash') != new_hash
            d['file_hash'] = new_hash
            total += n
            print(f'  lemma-cache {os.path.basename(cpath)}: {n} refs, hash {"updated" if hash_changed else "same"}')
            if APPLY:
                backup(cpath)
                json.dump(d, open(cpath, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'lemma-cache: {total} refs')


def fix_index(root, files):
    for lang in sorted({l for l, _ in files}):
        db = os.path.join(root, 'data', 'inverted_index', f'{lang}_index.db')
        if not os.path.exists(db):
            print(f'  index {lang}: no database'); continue
        fns = [fn for l, fn in files if l == lang]
        src = sqlite3.connect(db)
        ids = [r[0] for r in src.execute(
            'select text_id from texts where filename in (%s)' % ','.join('?' * len(fns)), fns)]
        n_lines = n_post = 0
        for t in ('lines', 'postings'):
            for rowid, ref in src.execute(f'select rowid, ref from {t} where text_id in (%s)' % ','.join('?' * len(ids)), ids):
                if normalize_ref(ref) != ref:
                    if t == 'lines': n_lines += 1
                    else: n_post += 1
        src.close()
        print(f'  index {lang}: {len(ids)} texts, {n_lines} line refs, {n_post} posting refs to rewrite')
        if not APPLY:
            continue
        new = db + '.new'
        shutil.copy2(db, new)
        c = sqlite3.connect(new)
        for t in ('lines', 'postings'):
            rows = c.execute(f'select rowid, ref from {t} where text_id in (%s)' % ','.join('?' * len(ids)), ids).fetchall()
            c.executemany(f'update {t} set ref=? where rowid=?',
                          [(normalize_ref(ref), rid) for rid, ref in rows if normalize_ref(ref) != ref])
        c.commit(); c.close()
        os.replace(db, f'{db}.bak-reftags-{STAMP}')
        os.replace(new, db)
        print(f'  index {lang}: swapped in (backup {os.path.basename(db)}.bak-reftags-{STAMP})')


def fix_passage_index(root, files):
    works = {fn[:-5] for _, fn in files}
    dpath = os.path.join(root, 'data', 'passage_index', 'descriptions.jsonl')
    n = 0
    if os.path.exists(dpath):
        out_path = dpath + '.new'
        with open(dpath, encoding='utf-8') as fh, open(out_path, 'w', encoding='utf-8') as out:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:
                    out.write(line); continue
                if r.get('work') in works:
                    changed = False
                    for k in ('ref_start', 'ref_end'):
                        if r.get(k):
                            v = normalize_ref(r[k])
                            if v != r[k]:
                                r[k] = v; changed = True
                    if changed:
                        n += 1
                        out.write(json.dumps(r, ensure_ascii=False) + '\n'); continue
                out.write(line)
        print(f'  passage-index descriptions.jsonl: {n} rows')
        if APPLY:
            backup(dpath); os.replace(out_path, dpath)
        else:
            os.remove(out_path)
    wdb = os.path.join(root, 'data', 'passage_index', 'window_texts.db')
    if os.path.exists(wdb):
        c = sqlite3.connect(wdb)
        q = ','.join('?' * len(works)); w = sorted(works)
        wt = c.execute(f'select rowid, ref_start, ref_end from window_texts where work in ({q})', w).fetchall()
        ln = c.execute(f'select rowid, ref from lines where work in ({q})', w).fetchall()
        wt_upd = [(normalize_ref(a), normalize_ref(b), rid) for rid, a, b in wt if normalize_ref(a) != a or normalize_ref(b) != b]
        ln_upd = [(normalize_ref(r), rid) for rid, r in ln if normalize_ref(r) != r]
        print(f'  passage-index window_texts.db: {len(wt_upd)} windows, {len(ln_upd)} lines')
        c.close()
        if APPLY:
            # Copy, update, swap, as for the inverted indexes: the live app's
            # read-only handles keep the old file until the WSGI reload.
            new = wdb + '.new'
            shutil.copy2(wdb, new)
            c = sqlite3.connect(new)
            c.executemany('update window_texts set ref_start=?, ref_end=? where rowid=?', wt_upd)
            c.executemany('update lines set ref=? where rowid=?', ln_upd)
            c.commit(); c.close()
            os.replace(wdb, f'{wdb}.bak-reftags-{STAMP}')
            os.replace(new, wdb)


def fix_translations(root, files):
    total = 0
    for lang, fn in files:
        path = os.path.join(root, 'data', 'translations', f'{lang}__{fn[:-5]}.json')
        if not os.path.exists(path):
            continue
        d = json.load(open(path, encoding='utf-8'))
        r2u = d.get('ref_to_unit') or {}
        new = {}
        n = 0
        for k, v in r2u.items():
            nk = normalize_ref(k)
            if nk != k: n += 1
            new.setdefault(nk, v)
        assert len(new) == len(r2u), f'{fn}: keys collide after cleaning'
        d['ref_to_unit'] = new
        total += n
        print(f'  translations {os.path.basename(path)}: {n} keys')
        if APPLY:
            backup(path)
            json.dump(d, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'translations: {total} keys')


def fix_fusion_cache(root, files):
    names = {fn for _, fn in files} | {fn[:-5] for _, fn in files}
    hit = []
    for path in glob.glob(os.path.join(root, 'cache', '*.json')):
        try:
            d = json.load(open(path, encoding='utf-8'))
        except Exception:
            continue
        if isinstance(d, dict) and (d.get('source') in names or d.get('target') in names):
            hit.append(path)
    print(f'  fusion-cache: {len(hit)} cached results involve affected texts')
    if APPLY:
        for p in hit:
            os.remove(p)


def preflight(root, files, data_modes):
    """Refuse to touch the data stores unless the repaired texts are in place
    (the lemma-cache hash is taken from the file on disk), and refuse to start
    any store if a translation map would have two keys collapse into one."""
    still_bad = [f'{l}/{fn}' for l, fn in files
                 if any(bad(line[1:line.find('>')]) for line in open(os.path.join(root, 'texts', l, fn), encoding='utf-8', errors='replace')
                        if line.startswith('<') and '>' in line)]
    if data_modes and still_bad:
        raise SystemExit(f'texts still carry malformed tags; repair or pull them first: {still_bad[:5]}')
    for lang, fn in files:
        path = os.path.join(root, 'data', 'translations', f'{lang}__{fn[:-5]}.json')
        if os.path.exists(path):
            r2u = json.load(open(path, encoding='utf-8')).get('ref_to_unit') or {}
            if len({normalize_ref(k) for k in r2u}) != len(r2u):
                raise SystemExit(f'translation keys would collide after cleaning: {path}')


if __name__ == '__main__':
    if '--list' in sys.argv:
        # "lang/filename" per line: the affected set is fixed by the list, not
        # by scanning, so the data stores can be repaired after the texts are.
        files = [tuple(l.strip().split('/', 1)) for l in open(sys.argv[sys.argv.index('--list') + 1])
                 if l.strip() and not l.startswith('#')]
    else:
        files = affected_files(ROOT)
    data_modes = any(f in sys.argv for f in ('--lemma-cache', '--index', '--passage-index', '--translations', '--fusion-cache'))
    print(f'{"APPLY" if APPLY else "DRY RUN"} on {ROOT}: {len(files)} files')
    if APPLY:
        preflight(ROOT, files, data_modes)
    if '--texts' in sys.argv: fix_texts(ROOT, files)
    if '--lemma-cache' in sys.argv: fix_lemma_cache(ROOT, files)
    if '--index' in sys.argv: fix_index(ROOT, files)
    if '--passage-index' in sys.argv: fix_passage_index(ROOT, files)
    if '--translations' in sys.argv: fix_translations(ROOT, files)
    if '--fusion-cache' in sys.argv: fix_fusion_cache(ROOT, files)
