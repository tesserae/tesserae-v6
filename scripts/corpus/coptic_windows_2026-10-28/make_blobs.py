#!/usr/bin/env python3
"""From the describer's output make: sidecar.jsonl (one described row per window, in windows order, desc rows only),
gpu_blobs.jsonl.gz (non-restricted works, {id, text} with the e5 'query: ' blob) and cpu_blobs.jsonl (restricted works,
encoded on this server, never sent out). usage: make_blobs.py DIR"""
import gzip, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
import apply_passage_rows as APR
D = sys.argv[1]
restricted = set(json.load(open('/home/ncoffee/wt-copticwin/data/restricted_texts.json'))['texts'])
want = [json.loads(l)['id'] for l in open(f'{D}/windows.jsonl', encoding='utf-8')]
rows = {}
for l in open(f'{D}/descriptions.jsonl', encoding='utf-8'):
    r = json.loads(l)
    if 'desc' in r: rows.setdefault(r['id'], r)
miss = [i for i in want if i not in rows]
assert not miss, f'{len(miss)} windows without description, e.g. {miss[:3]}'
side = [rows[i] for i in want]
with open(f'{D}/sidecar.jsonl', 'w', encoding='utf-8') as fh:
    for r in side: fh.write(json.dumps(r, ensure_ascii=False) + '\n')
g = c = 0
with gzip.open(f'{D}/gpu_blobs.jsonl.gz', 'wt', encoding='utf-8') as gh, open(f'{D}/cpu_blobs.jsonl', 'w', encoding='utf-8') as ch:
    for r in side:
        rec = json.dumps({'id': r['id'], 'text': APR.blob_for(r['desc'])}, ensure_ascii=False) + '\n'
        if r['work'] in restricted: ch.write(rec); c += 1
        else: gh.write(rec); g += 1
print('sidecar', len(side), 'gpu', g, 'cpu (restricted)', c)
