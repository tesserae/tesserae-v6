import sqlite3, json, os, sys, mmap, time
sys.path.insert(0, '/home/ncoffee/tesserae-v6-dev')
from backend.work_names import base_work
S = os.path.expanduser('~/tesserae-backups/public_data_2026-10-25_withheld')
db = sys.argv[1]
ids = {e['id'] for e in json.load(open(S + '/withheld_ids.json'))}
samples = json.load(open(S + '/work/samples.json'))
c = sqlite3.connect(db)
r = {}
r['integrity'] = c.execute('pragma integrity_check').fetchone()[0]
r['texts_with_listed_id'] = sum(1 for (f,) in c.execute('select filename from texts') if f.endswith('.tess') and base_work(f[:-5]) in ids)
r['orphan_lines'] = c.execute('select count(*) from lines where text_id not in (select text_id from texts)').fetchone()[0]
r['orphan_postings'] = c.execute('select count(*) from postings where text_id not in (select text_id from texts)').fetchone()[0]
r['lemma_doc_freq_mismatch'] = c.execute('select count(*) from (select lemma, count(distinct text_id) n from postings group by lemma) a left join lemma_doc_freq b using(lemma) where b.df is null or b.df != a.n').fetchone()[0] + c.execute('select count(*) from lemma_doc_freq where lemma not in (select lemma from postings)').fetchone()[0]
c.close()
t = time.time()
with open(db, 'rb') as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
    r['raw_byte_occurrences'] = {k: m.find(v.encode('utf-8')) for k, v in samples.items()}
    r['raw_sahidica'] = m.find(b'sahidica')
# full dump scan
c = sqlite3.connect(db)
hits = {k: 0 for k in samples}
n = 0
for line in c.iterdump():
    n += 1
    for k, v in samples.items():
        if v in line: hits[k] += 1
r['dump_statements'] = n
r['dump_occurrences'] = hits
r['dump_seconds'] = round(time.time() - t, 1)
c.close()
# searches
from backend import inverted_index as ii
ii.INDEX_DIR = os.path.dirname(os.path.dirname(db)) + '/' + os.path.basename(os.path.dirname(db)) if False else os.path.dirname(db)
# the module looks for <lang>_index.db in INDEX_DIR; db is named la_index.db
searches = {}
for q in (['arma', 'uir'], ['cano', 'troia'], ['gallia', 'diuido']):
    res = ii.lookup_lemmas(q, 'la', min_matches=2)
    searches[' '.join(q)] = len(res) if hasattr(res, '__len__') else str(type(res))
r['searches_lookup_lemmas_min2'] = searches
cn = ii.get_connection('la')
r['search_uses_copy'] = cn.execute('pragma database_list').fetchall()[0][2]
r['stats_texts'] = cn.execute('select count(*) from texts').fetchone()[0]
print(json.dumps(r, indent=1))
