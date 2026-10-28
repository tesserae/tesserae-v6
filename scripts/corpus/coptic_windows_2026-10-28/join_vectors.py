"""Join the GPU vectors and the CPU vectors in sidecar order; spot-check 16 GPU rows against a local CPU encode. usage: join_vectors.py DIR"""
import json, sys, random
import numpy as np
D = sys.argv[1]
side = [json.loads(l)['id'] for l in open(f'{D}/sidecar.jsonl', encoding='utf-8')]
gi = json.load(open(f'{D}/gpu/ids-000.json')); gv = np.load(f'{D}/gpu/vectors-000.npy')
ci = json.load(open(f'{D}/cpu_ids.json')); cv = np.load(f'{D}/cpu_vectors.npy')
assert gv.shape[0] == len(gi) and gv.shape[1] == cv.shape[1] == 1024
m = {i: v for i, v in zip(gi, gv)}; m.update({i: v for i, v in zip(ci, cv)})
assert set(m) == set(side) and len(m) == len(side)
V = np.stack([m[i] for i in side]).astype('float32')
np.save(f'{D}/vectors.npy', V); json.dump(side, open(f'{D}/vector_ids.json', 'w'))
print('joined', V.shape, 'norm range', float(np.linalg.norm(V, axis=1).min()), float(np.linalg.norm(V, axis=1).max()))
from sentence_transformers import SentenceTransformer
sys.path.insert(0, '/home/ncoffee/wt-copticwin/scripts/corpus'); import apply_passage_rows as APR
rows = {json.loads(l)['id']: json.loads(l) for l in open(f'{D}/sidecar.jsonl', encoding='utf-8')}
random.seed(3); pick = random.sample(gi, 16)
model = SentenceTransformer('intfloat/multilingual-e5-large', device='cpu')
loc = model.encode([APR.blob_for(rows[i]['desc']) for i in pick], batch_size=4, normalize_embeddings=True)
cos = [float(np.dot(loc[k], m[i])) for k, i in enumerate(pick)]
print('cosine GPU vs CPU, 16 rows: min', min(cos), 'mean', sum(cos) / 16)
