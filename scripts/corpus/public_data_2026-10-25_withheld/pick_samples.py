import sqlite3, json, os, sys, random
sys.path.insert(0, '/home/ncoffee/tesserae-v6-dev')
from backend.work_names import base_work
S = os.path.expanduser('~/tesserae-backups/public_data_2026-10-25_withheld')
ids = {e['id']: e for e in json.load(open(S + '/withheld_ids.json'))}
want = ['walahfrid_strabo.carmina', 'ennius.annales', 'aquinas.summa_theologiae_1', 'augustine.de_doctrina_christiana', 'petrus_riga.aurora']
c = sqlite3.connect(S + '/work/la_index/la_index.db')
tid = {}
for t, f in c.execute('select text_id, filename from texts'):
    tid.setdefault(base_work(f[:-5]), []).append(t)
random.seed(25)
wt = [t for w in ids for t in tid.get(w, [])]
out = {}
for w in want:
    rows = []
    for t in tid[w]:
        rows += [r[0] for r in c.execute('select content from lines where text_id=? and length(content) between 32 and 200', (t,))]
    random.shuffle(rows)
    for txt in rows:
        if c.execute('select count(*) from lines where content=? and text_id not in (%s)' % ','.join('?'*len(wt)), [txt]+wt).fetchone()[0] == 0:
            out[w] = txt; break
json.dump(out, open(S + '/work/samples.json', 'w'), indent=1, ensure_ascii=False)
for k, v in out.items(): print(k, ids[k]['source'], '|', v[:70])
