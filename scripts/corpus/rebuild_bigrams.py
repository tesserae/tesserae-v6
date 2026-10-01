#!/usr/bin/env python3
"""Full rebuild of a language's rare-bigram cache from the corpus (whole works
plus orphan parts, as backend.bigram_frequency counts them). The cache is
written beside the live file and renamed over it: the live file belongs to
the web app's account and cannot be opened for writing, and the rename is
atomic for any reader. A backup copy is taken first.
    cd /var/www/tesseraev6_flask && venv/bin/python rebuild_bigrams.py grc
"""
import os, shutil, sys, time
sys.path.insert(0, os.getcwd())
lang = sys.argv[1]
import backend.bigram_frequency as B
from backend.text_processor import TextProcessor

# A script that imports the processor directly gets an empty language
# handler table: a plugin language (Coptic, Hebrew) then falls through to the
# Latin tokenizer, which strips its letters, and the table comes out EMPTY.
# On 2026-10-01 this script wrote a Hebrew table of 0 bigrams over the live
# one (restored from the backup it takes). Register the plugins first, as
# scripts/batch_lemma_cache.py does, and refuse to swap in an empty table.
for _module in ('backend.coptic', 'backend.hebrew', 'backend.persian', 'backend.urdu', 'backend.arabic'):
    try:
        __import__(_module, fromlist=['register']).register()
    except ImportError:
        continue
live = B.get_cache_path(lang)
new = live + '.new'
if os.path.exists(live):
    bak = f'{live}.pre-rebuild-{time.strftime("%Y%m%d-%H%M")}.bak'
    shutil.copy2(live, bak); print('backup', bak, flush=True)
B.get_cache_path = lambda l, _n=new: _n   # save_bigram_cache writes to the .new path
t0 = time.time()
data = B.calculate_bigram_frequencies(lang, TextProcessor(), progress_callback=lambda i, n: print(f'  {i}/{n}', flush=True))
if not data.get('total_bigrams'):
    os.remove(new)
    sys.exit(f'REFUSED: the rebuilt {lang} table holds no bigrams; the live file is untouched')
os.replace(new, live)
print(f'DONE {lang}: docs {data.get("total_docs")}, bigrams {data.get("total_bigrams")}, keys {len(data.get("frequencies", {}))}, {time.time()-t0:.0f}s', flush=True)
