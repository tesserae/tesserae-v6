import json, os, sys, hashlib
import numpy as np
sys.path.insert(0, '/home/ncoffee/tesserae-v6-dev')
from backend.work_names import base_work
S = os.path.expanduser('~/tesserae-backups/public_data_2026-10-25_withheld')
IN, OUT = S + '/work/pi_la_in/la', S + '/work/pi_la_out/la'
os.makedirs(OUT, exist_ok=True)
DROP = {'augustine.de_doctrina_christiana'}
raw_ids = open(IN + '/ids.json', encoding='utf-8').read()
ids = json.loads(raw_ids)
emb = np.load(IN + '/embeddings.npy', mmap_mode='r')
descs = []
with open(IN + '/descriptions.jsonl', encoding='utf-8') as f:
    for line in f:
        if line.strip():
            descs.append(line)
rep = {'ids': len(ids), 'emb_rows': emb.shape[0], 'emb_shape': list(emb.shape), 'emb_dtype': str(emb.dtype), 'desc_lines': len(descs)}
assert len(ids) == emb.shape[0] == len(descs), rep
jd = [json.loads(l) for l in descs]
rep['desc_ids_align_with_ids'] = all(d['id'] == i for d, i in zip(jd, ids))
assert rep['desc_ids_align_with_ids']
rep['ids_json_compact'] = raw_ids == json.dumps(ids, ensure_ascii=False)
keep = [i for i, w in enumerate(ids) if base_work(w.split(':')[0]) not in DROP]
ks = set(keep); drop = [i for i in range(len(ids)) if i not in ks]
rep['dropped_windows'] = len(drop)
rep['dropped_desc_work_field'] = sum(1 for d in jd if base_work(d.get('work') or '') in DROP)
rep['dropped_ids_sample'] = [ids[i] for i in drop[:3]]
rep['kept'] = len(keep)
# also any window whose id or work names the dropped work in other ways
rep['kept_with_dropped_work_field'] = sum(1 for i in keep if base_work(jd[i].get('work') or '') in DROP)
# per-source counts of the windows left of withheld ids (for the README)
wid = {e['id']: e['source'] for e in json.load(open(S + '/withheld_ids.json'))}
cnt = {}
for i in keep:
    b = base_work(ids[i].split(':')[0])
    if b in wid: cnt[wid[b]] = cnt.get(wid[b], 0) + 1
rep['withheld_source_windows_left_in_slice'] = cnt
new_emb = np.ascontiguousarray(emb[keep])
np.save(OUT + '/embeddings.npy', new_emb)
with open(OUT + '/ids.json', 'w', encoding='utf-8') as f:
    f.write(json.dumps([ids[i] for i in keep], ensure_ascii=False))
with open(OUT + '/descriptions.jsonl', 'w', encoding='utf-8') as f:
    for i in keep:
        f.write(descs[i] if descs[i].endswith('\n') else descs[i] + '\n')
# verify
import random
random.seed(7)
nids = json.load(open(OUT + '/ids.json', encoding='utf-8'))
nemb = np.load(OUT + '/embeddings.npy', mmap_mode='r')
nd = [json.loads(l)['id'] for l in open(OUT + '/descriptions.jsonl', encoding='utf-8') if l.strip()]
rep['after'] = {'ids': len(nids), 'emb_rows': nemb.shape[0], 'desc': len(nd), 'aligned_desc': nd == nids}
pos_old = {w: i for i, w in enumerate(ids)}
samp = random.sample(nids, 10)
rep['sample_check'] = [{'id': s, 'old_row': pos_old[s], 'new_row': nids.index(s), 'same_vector': bool(np.array_equal(emb[pos_old[s]], nemb[nids.index(s)]))} for s in samp]
rep['all_vectors_equal_to_kept_rows'] = bool(np.array_equal(nemb, emb[keep]))
rep['dtype_same'] = nemb.dtype == emb.dtype
print(json.dumps(rep, indent=1))
