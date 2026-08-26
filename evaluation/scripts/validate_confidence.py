"""Both probe sets through the NEW rule. Fixing short queries must not break long ones."""
import json, os, sys
import numpy as np
sys.path.insert(0, '/home/ncoffee/tesserae-scene')
from backend import passage_index as pi

def measure(query):
    pi._ensure_loaded()
    q = pi.embed_query(pi._E5_PREFIX + query.strip()[:1500])
    sc = pi._score_all(q)
    med = float(np.median(sc)); k = min(10, len(sc))
    return float(np.sort(sc)[-k:].mean()) - med, pi._cluster_coherence(sc)

def run(name, rows):
    ok = 0
    misses = []
    for r in rows:
        h, c = measure(r['query'])
        lvl = pi._confidence_level(h, c)
        got = lvl != 'low'
        if got == r['present']: ok += 1
        else: misses.append((r['query'][:46], lvl, r['present']))
    print(f'{name}: {ok}/{len(rows)} ({100*ok/len(rows):.0f}%)')
    for q, lvl, want in misses:
        print(f'    miss: {q:48s} -> {lvl:9s} (present={want})')

short = json.load(open('/home/ncoffee/tesserae-scene/evaluation/probe_sets/short_query_stats.json'))
run('short-query set (1-10 words)', short)
main = json.load(open('/home/ncoffee/tesserae-scene/evaluation/probe_sets/tesserae_2026-08.json'))
run('original 32-query set', main)
