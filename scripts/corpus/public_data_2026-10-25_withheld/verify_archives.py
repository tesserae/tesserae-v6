import tarfile, hashlib, json, os, sys, sqlite3, csv, mmap
import numpy as np
sys.path.insert(0, '/home/ncoffee/tesserae-v6-dev')
from backend.work_names import base_work
S = os.path.expanduser('~/tesserae-backups/public_data_2026-10-25_withheld'); V = S + '/work/verify'
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''): h.update(b)
    return h.hexdigest()
out = {}
for name, k, d in (('la_index.db.tar.gz', 'la', 'x_la'), ('window_texts.db.tar.gz', 'wt', 'x_wt'), ('passage_index_la.tar.gz', 'pi', 'x_pi')):
    led = json.load(open(f'{S}/work/pack_{k}.json'))
    with tarfile.open(f'{S}/{name}') as t:
        names = t.getnames(); t.extractall(f'{V}/{d}', filter='data')
    r = {'members': names, 'archive_sha256_matches_ledger': sha(f'{S}/{name}') == led['archive_sha256'], 'extracted': {}}
    for arc, v in led['files'].items():
        p = f'{V}/{d}/{arc}'
        r['extracted'][arc] = {'bytes': os.path.getsize(p), 'sha256': sha(p), 'matches_ledger': sha(p) == v['sha256']}
    out[name] = r
ids = {e['id'] for e in json.load(open(S + '/withheld_ids.json'))}
samples = json.load(open(S + '/work/samples.json'))
man = {r['file'] for r in csv.DictReader(open('/var/www/tesseraev6_flask/public_data/texts_la_manifest.tsv', encoding='utf-8'), delimiter='\t')}
c = sqlite3.connect(f'{V}/x_la/la_index.db')
files = {f for (f,) in c.execute('select filename from texts')}
out['la_index_files_equal_manifest'] = files == man
out['la_index_integrity'] = c.execute('pragma integrity_check').fetchone()[0]
out['la_index_counts'] = {t: c.execute(f'select count(*) from {t}').fetchone()[0] for t in ('texts', 'lines', 'postings', 'lemma_doc_freq')}
c = sqlite3.connect(f'{V}/x_wt/window_texts.db')
out['wt_integrity'] = c.execute('pragma integrity_check').fetchone()[0]
out['wt_counts'] = {t: c.execute(f'select count(*) from {t}').fetchone()[0] for t in ('window_texts', 'lines')}
out['wt_listed_ids_left'] = sum(1 for (w,) in c.execute('select distinct work from window_texts union select distinct work from lines') if base_work(w) in ids)
for p in (f'{V}/x_la/la_index.db', f'{V}/x_wt/window_texts.db'):
    with open(p, 'rb') as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
        out[os.path.basename(p) + '_raw_hits'] = {**{k: m.find(s.encode()) for k, s in samples.items()}, 'sahidica': m.find(b'sahidica')}
d = V + '/x_pi/la'
pids = json.load(open(d + '/ids.json', encoding='utf-8')); emb = np.load(d + '/embeddings.npy', mmap_mode='r')
dl = [json.loads(l)['id'] for l in open(d + '/descriptions.jsonl', encoding='utf-8') if l.strip()]
out['slice'] = {'ids': len(pids), 'emb': list(emb.shape), 'desc': len(dl), 'aligned': dl == pids,
                'dedoct_left': sum(1 for i in pids if base_work(i.split(':')[0]) == 'augustine.de_doctrina_christiana'),
                'manifest_windows': json.load(open(d + '/MANIFEST.json'))['windows'],
                'manifest_hashes_ok': all(sha(f'{d}/{n}') == v['sha256'] for n, v in json.load(open(d + '/MANIFEST.json'))['files'].items())}
print(json.dumps(out, indent=1))
