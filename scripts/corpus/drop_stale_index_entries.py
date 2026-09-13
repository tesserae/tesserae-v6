#!/usr/bin/env python3
"""Drop index entries whose text file no longer exists (copy, delete, recompute
lemma_doc_freq, VACUUM, atomic swap; the live app keeps its old handle until
the swap). Dry run unless --apply.
    python drop_stale_index_entries.py --root /var/www/tesseraev6_flask --language grc [--apply]
"""
import argparse, os, shutil, sqlite3, sys, time
ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--language', required=True); ap.add_argument('--apply', action='store_true')
a = ap.parse_args()
db = os.path.join(a.root, 'data', 'inverted_index', f'{a.language}_index.db')
con = sqlite3.connect(db)
rows = con.execute('select text_id, filename, line_count from texts').fetchall()
stale = [(t, f, n) for t, f, n in rows if not os.path.exists(os.path.join(a.root, 'texts', a.language, f))]
ids = [t for t, _, _ in stale]; marks = ','.join('?' * len(ids))
nl = con.execute(f'select count(*) from lines where text_id in ({marks})', ids).fetchone()[0] if ids else 0
npo = con.execute(f'select count(*) from postings where text_id in ({marks})', ids).fetchone()[0] if ids else 0
print(f'{a.language}: {len(rows)} entries, {len(stale)} stale ({nl} lines, {npo} postings)')
for t, f, n in stale: print(f'  {f} ({n} lines)')
con.close()
if not a.apply or not ids:
    print('dry run' if not a.apply else 'nothing to do'); raise SystemExit
tag = time.strftime('%Y%m%d-%H%M'); new = db + '.new'
shutil.copy2(db, new)
c = sqlite3.connect(new)
c.execute(f'delete from lines where text_id in ({marks})', ids)
c.execute(f'delete from postings where text_id in ({marks})', ids)
c.execute(f'delete from texts where text_id in ({marks})', ids)
# Document frequency counts one document per WORK (book files collapse to
# their base work); the canonical builder does that. A plain
# COUNT(DISTINCT text_id) here inflated every partitioned work on 2026-09-12.
sys.path.insert(0, a.root)
from scripts.build_inverted_index import build_lemma_doc_freq  # noqa: E402
build_lemma_doc_freq(c, verbose=False)
c.commit(); c.execute('VACUUM'); c.close()
os.replace(db, f'{db}.bak-stale-{tag}'); os.replace(new, db)
print(f'swapped; backup {os.path.basename(db)}.bak-stale-{tag}; texts now', sqlite3.connect(db).execute('select count(*) from texts').fetchone()[0])
