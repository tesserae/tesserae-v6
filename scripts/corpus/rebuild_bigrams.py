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
live = B.get_cache_path(lang)
new = live + '.new'
if os.path.exists(live):
    bak = f'{live}.pre-rebuild-{time.strftime("%Y%m%d-%H%M")}.bak'
    shutil.copy2(live, bak); print('backup', bak, flush=True)
B.get_cache_path = lambda l, _n=new: _n   # save_bigram_cache writes to the .new path
t0 = time.time()
data = B.calculate_bigram_frequencies(lang, TextProcessor(), progress_callback=lambda i, n: print(f'  {i}/{n}', flush=True))
os.replace(new, live)
print(f'DONE {lang}: docs {data.get("total_docs")}, bigrams {data.get("total_bigrams")}, keys {len(data.get("frequencies", {}))}, {time.time()-t0:.0f}s', flush=True)
