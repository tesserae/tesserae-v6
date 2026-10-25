import sqlite3, json, os, sys, mmap
sys.path.insert(0, '/home/ncoffee/tesserae-v6-dev')
from backend.work_names import base_work
S = os.path.expanduser('~/tesserae-backups/public_data_2026-10-25_withheld')
db = sys.argv[1]
ids = {e['id'] for e in json.load(open(S + '/withheld_ids.json'))}
samples = json.load(open(S + '/work/samples.json'))
c = sqlite3.connect(db)
def cnt():
    return {'window_texts': c.execute('select count(*) from window_texts').fetchone()[0],
            'lines': c.execute('select count(*) from lines').fetchone()[0],
            'works_window_texts': c.execute('select count(distinct work) from window_texts').fetchone()[0],
            'works_lines': c.execute('select count(distinct work) from lines').fetchone()[0],
            'by_language': dict(c.execute('select language,count(*) from window_texts group by 1').fetchall())}
rep = {'before': cnt()}
works = {w for (w,) in c.execute('select distinct work from window_texts')} | {w for (w,) in c.execute('select distinct work from lines')}
drop = sorted(w for w in works if base_work(w) in ids)
rep['works_dropped'] = len(drop)
rep['base_ids_hit'] = len({base_work(w) for w in drop})
rep['base_ids_not_present'] = sorted(ids - {base_work(w) for w in drop})
c.execute('create temp table dropw(work text primary key)')
c.executemany('insert into dropw values (?)', [(w,) for w in drop])
rep['windows_removed'] = c.execute('select count(*) from window_texts where work in (select work from dropw)').fetchone()[0]
rep['lines_removed'] = c.execute('select count(*) from lines where work in (select work from dropw)').fetchone()[0]
c.execute('delete from window_texts where work in (select work from dropw)')
c.execute('delete from lines where work in (select work from dropw)')
c.commit()
c.execute('VACUUM')
rep['after'] = cnt()
rep['integrity'] = c.execute('pragma integrity_check').fetchone()[0]
rep['rows_with_listed_id'] = {
  'window_texts_work': sum(1 for (w,) in c.execute('select distinct work from window_texts') if base_work(w) in ids),
  'window_texts_id_prefix': sum(1 for (i,) in c.execute('select id from window_texts') if base_work(i.split(':')[0]) in ids),
  'lines': sum(1 for (w,) in c.execute('select distinct work from lines') if base_work(w) in ids)}
rep['lines_orphan_work'] = c.execute('select count(*) from lines where work not in (select work from window_texts)').fetchone()[0]
rep['windows_without_lines'] = c.execute('select count(*) from window_texts where work not in (select distinct work from lines)').fetchone()[0]
rep['like_sahidica'] = c.execute("select count(*) from window_texts where id like 'sahidica%' or work like 'sahidica%'").fetchone()[0] + c.execute("select count(*) from lines where work like 'sahidica%'").fetchone()[0]
c.close()
with open(db, 'rb') as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as m:
    rep['raw_byte_occurrences'] = {k: m.find(v.encode('utf-8')) for k, v in samples.items()}
    rep['raw_sahidica_string'] = m.find(b'sahidica')
c = sqlite3.connect(db)
hits = {k: 0 for k in samples}; n = 0
for line in c.iterdump():
    n += 1
    for k, v in samples.items():
        if v in line: hits[k] += 1
rep['dump_statements'] = n; rep['dump_occurrences'] = hits
print(json.dumps(rep, indent=1))
