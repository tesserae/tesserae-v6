# ruff: noqa: E401, E402, E701, E702, E731, E741, F401
# One-off script of 2026-10-25, kept as it ran (see README.md beside it).
import sys
import os
import json
import csv
import collections
sys.path.insert(0, '/home/ncoffee/tesserae-v6-dev')
from backend import fspaths, utils
from backend.work_names import base_work
from scripts.corpus import build_text_archives as b
S = os.path.expanduser('~/tesserae-backups/public_data_2026-10-25_withheld')
root = '/var/www/tesseraev6_flask/texts/la'
idx = b.SourceIndex(b.load_sources('/var/www/tesseraev6_flask'))
files = sorted(f for f in fspaths.listdir_text(root) if f.endswith('.tess'))
withheld = {}   # file -> (reason, author, work)
nrow = collections.Counter()
for f in files:
    md = utils.get_text_metadata(os.path.join(root, f))
    src = idx.find(md.get('author', ''), md.get('work', ''))
    why = b.withheld_reason(src)
    if why:
        withheld[f] = (why, md.get('author', ''), md.get('work', ''))
man = {r['file'] for r in csv.DictReader(open('/var/www/tesseraev6_flask/public_data/texts_la_manifest.tsv', encoding='utf-8'), delimiter='\t')}
notinman = sorted(set(files) - man)
extra_man = sorted(man - set(files))
reg = json.loads(os.popen("git -C /home/ncoffee/tesserae-v6-dev show origin/restrict-augustinus-it:data/restricted_texts.json").read())['texts']
restricted_files = sorted(f for f in files if base_work(f[:-5]) in reg)
print('files', len(files), 'manifest rows', len(man), 'withheld files', len(withheld), 'not in manifest', len(notinman), 'in manifest not on disk', len(extra_man))
print('restricted files (branch registry):', restricted_files)
print('withheld not in manifest?', sorted(set(withheld) - set(notinman))[:20])
print('not in manifest, not withheld:', [f for f in notinman if f not in withheld])
# credit rows
rows = b.load_sources('/var/www/tesseraev6_flask')
wr = [r for r in rows if b.withheld_reason(r)]
bysrc_rows = collections.Counter(b.withheld_reason(r).split(' (')[0] for r in wr)
print('credit rows withheld', len(wr), dict(bysrc_rows))
ids = {}
for f, (why, a, w) in withheld.items():
    i = base_work(f[:-5]); name = why.split(' (')[0]
    e = ids.setdefault(i, {'id': i, 'source': name, 'reason': why[len(name)+2:-1], 'files': []})
    e['files'].append(f)
for f in restricted_files:
    i = base_work(f[:-5])
    e = ids.setdefault(i, {'id': i, 'source': 'registry', 'reason': 'restricted work', 'files': []})
    if e['source'] != 'registry':
        e['also_registry'] = True
    e['files'].append(f)
for i in reg:
    if i.startswith('augustine.') and i in ids:
        ids[i]['source'] = ids[i]['source']; ids[i]['also_registry'] = True
out = sorted(ids.values(), key=lambda e: e['id'])
json.dump(out, open(S + '/withheld_ids.json', 'w'), indent=1, ensure_ascii=False)
json.dump({'texts': {e['id']: {'holder': e['source'], 'reason': e['reason']} for e in out}}, open(S + '/withheld_ids_registry_shape.json', 'w'), indent=1, ensure_ascii=False)
print('base ids', len(out), dict(collections.Counter(e['source'] for e in out)))
print('files by source', dict(collections.Counter(v[0].split(' (')[0] for v in withheld.values())))
json.dump({'notinman': notinman, 'withheld_files': sorted(withheld)}, open(S+'/work/idlist_debug.json','w'), indent=1, ensure_ascii=False)
