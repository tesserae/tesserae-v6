#!/usr/bin/env python3
"""Write a copy of the passage index, the names index and the connections map
that holds only the languages a public bundle may carry.

The production passage index covers every language the site serves, including
Persian and Urdu, in one set of files whose rows line up (row i of
embeddings.npy is ids.json[i]). Leaving files out of an archive cannot remove
those rows, so this script rebuilds each file with only the allowed rows:

    ids.json, embeddings.npy        rows of allowed windows, in the original order
    descriptions.jsonl              records of allowed windows
    desc_fts.sqlite                 rebuilt from the filtered descriptions
    window_texts.db                 rows of allowed languages (and their lines)
    window_names.db                 rows of allowed windows, document counts recomputed
    works_by_language.json          allowed languages only
    connections map database        windows, edges and work tables of allowed
                                    works, pair tables recomputed, file renamed
                                    for the filtered index so the app finds it

    python3 scripts/ops/filter_passage_index.py --prod /var/www/tesseraev6_flask \
        --out OUTDIR --languages la,grc,en,cop,he --dry-run

`--dry-run` reads only ids.json and descriptions.jsonl and prints how many
windows each language would keep or lose. Nothing in --prod is ever written.
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from backend.work_names import base_work  # noqa: E402
import public_bundle_lib as lib  # noqa: E402


def log(msg):
    print(f'{time.strftime("%H:%M:%S")} {msg}', flush=True)


def scan_descriptions(path, allowed, restricted):
    """Return (keep_ids set, counts) from descriptions.jsonl."""
    keep = set()
    counts = {}
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            lang = r.get('language')
            ok = lang in allowed and base_work(r.get('work') or '') not in restricted
            c = counts.setdefault(lang, [0, 0])
            c[0 if ok else 1] += 1
            if ok:
                keep.add(r['id'])
    return keep, counts


def filter_jsonl(src, dst, keep):
    n = 0
    with open(src, encoding='utf-8') as fi, open(dst, 'w', encoding='utf-8') as fo:
        for line in fi:
            if not line.strip():
                continue
            if json.loads(line)['id'] in keep:
                fo.write(line if line.endswith('\n') else line + '\n')
                n += 1
    return n


def filter_sqlite_copy(src, dst, statements, vacuum=True):
    """Copy src to dst with the SQLite backup call (consistent), then run the
    deleting statements on the copy."""
    s = sqlite3.connect(f'file:{src}?mode=ro', uri=True)
    d = sqlite3.connect(dst)
    s.backup(d)
    s.close()
    for st in statements:
        d.execute(st) if isinstance(st, str) else d.execute(*st)
    d.commit()
    if vacuum:
        d.execute('VACUUM')
    d.close()


def filter_map(src, dst, allowed_langs, restricted, fingerprint):
    """Copy the connections map keeping allowed works and windows, recompute
    the aggregate tables the same way scripts/build_connections_map.py does."""
    from scripts.build_connections_map import century_label
    s = sqlite3.connect(f'file:{src}?mode=ro', uri=True)
    d = sqlite3.connect(dst)
    s.backup(d)
    s.close()
    langs = tuple(sorted(allowed_langs))
    q = ','.join('?' * len(langs))
    bad_works = [w for (w,) in d.execute(f'SELECT work FROM works WHERE language NOT IN ({q})', langs)]
    bad_works += [w for (w,) in d.execute('SELECT work FROM works') if base_work(w) in restricted]
    d.execute('CREATE TEMP TABLE bad_works (work TEXT PRIMARY KEY)')
    d.executemany('INSERT OR IGNORE INTO bad_works VALUES (?)', [(w,) for w in bad_works])
    d.execute('DELETE FROM edges WHERE work_a IN (SELECT work FROM bad_works) OR work_b IN (SELECT work FROM bad_works)')
    d.execute('DELETE FROM windows WHERE work IN (SELECT work FROM bad_works)')
    d.execute('DELETE FROM work_pairs WHERE work_a IN (SELECT work FROM bad_works) OR work_b IN (SELECT work FROM bad_works)')
    d.execute('DELETE FROM works WHERE work IN (SELECT work FROM bad_works)')
    # total_links / links_per_window from the remaining work pairs
    deg = {}
    for wa, wb, c in d.execute('SELECT work_a, work_b, count FROM work_pairs'):
        deg[wa] = deg.get(wa, 0) + c
        deg[wb] = deg.get(wb, 0) + c
    for w, wc in d.execute('SELECT work, window_count FROM works').fetchall():
        t = deg.get(w, 0)
        d.execute('UPDATE works SET total_links=?, links_per_window=? WHERE work=?',
                  (t, round(t / wc, 4) if wc else 0, w))
    meta = {w: dict(zip(('author_display', 'century', 'genre'), (a, c, g)))
            for w, a, c, g in d.execute('SELECT work, author_display, century, genre FROM works')}
    author_acc, century_acc, genre_acc = {}, {}, {}
    for wa, wb, la, lb, c, c_nt in d.execute('SELECT work_a, work_b, lang_a, lang_b, count, count_notrans FROM work_pairs'):
        ma, mb = meta[wa], meta[wb]
        aa, ab = f"{ma['author_display']} ({la})", f"{mb['author_display']} ({lb})"
        a_key = tuple(sorted((aa, ab)))
        akey = (a_key[0], a_key[1], la if a_key[0] == aa else lb, lb if a_key[0] == aa else la)
        p = author_acc.get(akey, (0, 0))
        author_acc[akey] = (p[0] + c, p[1] + c_nt)
        if ma['century'] is not None and mb['century'] is not None:
            lang_key = f'{la}-{lb}' if la <= lb else f'{lb}-{la}'
            pair = tuple(sorted((ma['century'], mb['century'])))
            key = (lang_key, pair[0], pair[1])
            p = century_acc.get(key, (0, 0))
            century_acc[key] = (p[0] + c, p[1] + c_nt)
        if ma['genre'] and mb['genre']:
            gp = tuple(sorted((ma['genre'], mb['genre'])))
            p = genre_acc.get(gp, (0, 0))
            genre_acc[gp] = (p[0] + c, p[1] + c_nt)
    for t in ('author_pairs', 'century_pairs', 'genre_pairs'):
        d.execute(f'DELETE FROM {t}')
    d.executemany('INSERT INTO author_pairs VALUES (?,?,?,?,?,?)',
                  [(k[0], k[1], k[2], k[3], v[0], v[1]) for k, v in author_acc.items()])
    d.executemany('INSERT INTO century_pairs VALUES (?,?,?,?,?,?,?)',
                  [(k[0], k[1], k[2], century_label(k[1]), century_label(k[2]), v[0], v[1]) for k, v in century_acc.items()])
    d.executemany('INSERT INTO genre_pairs VALUES (?,?,?,?)', [(k[0], k[1], v[0], v[1]) for k, v in genre_acc.items()])
    d.execute("UPDATE meta SET value=? WHERE key='index_fingerprint'", (json.dumps(fingerprint),))
    d.commit()
    d.execute('VACUUM')
    d.close()


def fingerprint_of(out_dir):
    parts = []
    for name in ('ids.json', 'embeddings.npy'):
        st = os.stat(os.path.join(out_dir, name))
        parts.append(f'{st.st_size}-{int(st.st_mtime)}')
    return '.'.join(parts)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--prod', default=lib.DEFAULT_PROD)
    ap.add_argument('--out', required=True, help='stage folder; files go under data/passage_index and cache/connections_map')
    ap.add_argument('--languages', default=None, help='comma list; default: core_languages of the exclusion file')
    ap.add_argument('--registry', default=None, help='restricted registry JSON (default: the one in --prod)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--skip-map', action='store_true')
    args = ap.parse_args(argv)

    excl = lib.load_exclusions()
    allowed = set((args.languages or ','.join(excl['core_languages'])).split(','))
    restricted = lib.load_registry_ids(args.registry or lib._registry_path(args.prod, excl))
    src = lib.passage_index_sources(args.prod)

    log('scanning descriptions.jsonl')
    keep_ids, counts = scan_descriptions(src['descriptions.jsonl'], allowed, restricted)
    for lang, (k, dropped) in sorted(counts.items(), key=lambda kv: str(kv[0])):
        log(f'  language {lang}: keep {k}, drop {dropped}')
    with open(src['ids.json'], encoding='utf-8') as f:
        ids = json.load(f)
    rows = [i for i, w in enumerate(ids) if w in keep_ids]
    log(f'ids.json {len(ids)} windows, keeping {len(rows)}')
    if args.dry_run:
        return 0

    pdir = os.path.join(args.out, 'data/passage_index')
    os.makedirs(pdir, exist_ok=True)

    import numpy as np
    emb = np.load(src['embeddings.npy'], mmap_mode='r')
    if emb.shape[0] != len(ids):
        log(f'REFUSING: embeddings rows {emb.shape[0]} differ from ids {len(ids)}')
        return 2
    np.save(os.path.join(pdir, 'embeddings.npy'), np.ascontiguousarray(emb[rows]))
    with open(os.path.join(pdir, 'ids.json'), 'w', encoding='utf-8') as f:
        json.dump([ids[i] for i in rows], f, ensure_ascii=False)
    del emb
    log('embeddings.npy and ids.json written')

    n = filter_jsonl(src['descriptions.jsonl'], os.path.join(pdir, 'descriptions.jsonl'), keep_ids)
    log(f'descriptions.jsonl: {n} records')

    # keyword index rebuilt from the filtered descriptions
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    import build_desc_fts
    nrows, secs = build_desc_fts.build(os.path.join(pdir, 'descriptions.jsonl'), os.path.join(pdir, 'desc_fts.sqlite'))
    log(f'desc_fts.sqlite: {nrows} rows')

    q = ','.join('?' * len(allowed))
    langs = tuple(sorted(allowed))
    filter_sqlite_copy(src['window_texts.db'], os.path.join(pdir, 'window_texts.db'), [
        ('DELETE FROM window_texts WHERE language NOT IN (%s)' % q, langs),
        'DELETE FROM lines WHERE work NOT IN (SELECT DISTINCT work FROM window_texts)',
    ])
    if restricted:
        c = sqlite3.connect(os.path.join(pdir, 'window_texts.db'))
        for (w,) in c.execute('SELECT DISTINCT work FROM window_texts').fetchall():
            if base_work(w) in restricted:
                c.execute('DELETE FROM window_texts WHERE work=?', (w,))
                c.execute('DELETE FROM lines WHERE work=?', (w,))
        c.commit(); c.close()
    log('window_texts.db filtered')

    # names: keep rows whose id is a kept window; recompute document counts
    names_out = os.path.join(pdir, 'window_names.db')
    filter_sqlite_copy(src['window_names.db'], names_out, [], vacuum=False)
    c = sqlite3.connect(names_out)
    c.execute('CREATE TEMP TABLE keep (id TEXT PRIMARY KEY)')
    c.executemany('INSERT INTO keep VALUES (?)', ((i,) for i in keep_ids))
    c.execute('DELETE FROM window_names WHERE id NOT IN (SELECT id FROM keep)')
    c.execute('DELETE FROM name_df')
    c.execute('INSERT INTO name_df SELECT k, COUNT(*) FROM window_names GROUP BY k')
    c.execute("DELETE FROM meta WHERE key LIKE 'windows!_%' ESCAPE '!' AND substr(key, 9) NOT IN (" + q + ")", langs)
    c.commit(); c.execute('VACUUM'); c.close()
    log('window_names.db filtered')

    with open(src['works_by_language.json'], encoding='utf-8') as f:
        wbl = json.load(f)
    wbl['languages'] = {k: [w for w in v if base_work(w) not in restricted]
                        for k, v in wbl.get('languages', {}).items() if k in allowed}
    with open(os.path.join(pdir, 'works_by_language.json'), 'w', encoding='utf-8') as f:
        json.dump(wbl, f, ensure_ascii=False)

    if not args.skip_map:
        msrc = lib.connections_map_source(args.prod)
        if msrc:
            mdir = os.path.join(args.out, 'cache/connections_map')
            os.makedirs(mdir, exist_ok=True)
            fp = fingerprint_of(pdir)
            mdst = os.path.join(mdir, f'{fp}.db')
            filter_map(msrc, mdst, allowed, restricted, fp)
            log(f'connections map written as {os.path.basename(mdst)}')
        else:
            log('no connections map found; skipped')
    log('done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
