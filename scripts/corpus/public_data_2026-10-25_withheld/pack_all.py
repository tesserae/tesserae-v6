# ruff: noqa: E401, E402, E701, E702, E731, E741, F401
# One-off script of 2026-10-25, kept as it ran (see README.md beside it).
import os
import sys
import json
import tarfile
import hashlib
import time
S = os.path.expanduser('~/tesserae-backups/public_data_2026-10-25_withheld')
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()
def tarinfo(t, path, arc):
    ti = t.gettarinfo(path, arcname=arc); ti.uid = ti.gid = 0; ti.uname = ti.gname = ''; ti.mode = 0o644
    return ti
def pack(name, folder, files, top=None):
    out = os.path.join(S, name); t0 = time.time(); inner = {}
    with tarfile.open(out, 'w:gz', compresslevel=9) as t:
        if top:
            ti = tarfile.TarInfo(top + '/'); ti.type = tarfile.DIRTYPE; ti.mode = 0o755; ti.mtime = int(time.time()); t.addfile(ti)
        for n in files:
            p = os.path.join(folder, n); arc = f'{top}/{n}' if top else n
            inner[arc] = {'bytes': os.path.getsize(p), 'sha256': sha(p)}
            with open(p, 'rb') as f:
                t.addfile(tarinfo(t, p, arc), f)
    r = {'archive_bytes': os.path.getsize(out), 'archive_sha256': sha(out), 'files': inner, 'seconds': round(time.time() - t0, 1)}
    print(name, json.dumps(r, indent=1))
    return r
which = sys.argv[1]
if which == 'pi':
    d = S + '/work/pack_pi'
    m = json.load(open(d + '/MANIFEST.json'))
    m['windows'] = 226480
    m['restricted_windows_withheld'] = 341
    for n in ('ids.json', 'embeddings.npy', 'descriptions.jsonl'):
        m['files'][n] = {'bytes': os.path.getsize(f'{d}/{n}'), 'sha256': sha(f'{d}/{n}')}
    json.dump(m, open(d + '/MANIFEST.json', 'w'), indent=1, ensure_ascii=False)
    r = pack('passage_index_la.tar.gz', d, ['LICENCE.txt', 'README.txt', 'descriptions.jsonl', 'ids.json', 'MANIFEST.json', 'embeddings.npy'], top='la')
elif which == 'la':
    r = pack('la_index.db.tar.gz', S + '/work/pack_la', ['la_index.db', 'LICENSE.txt', 'README.txt'])
else:
    r = pack('window_texts.db.tar.gz', S + '/work/pack_wt', ['window_texts.db', 'LICENSE.txt', 'README.txt'])
json.dump(r, open(f'{S}/work/pack_{which}.json', 'w'), indent=1)
