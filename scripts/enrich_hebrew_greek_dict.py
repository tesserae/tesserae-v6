#!/usr/bin/env python3
"""Enrich hebrew_greek.csv with DISTINCTIVE rare/name anchors mined from the aligned
Masoretic-Septuagint text. Blanket co-occurrence enrichment hurt (it adds common-word
noise); adding only rare, strongly-corresponding Greek partners helped, held-out
(leave-one-book-out: R@1 0.348->0.398, R@5 0.600->0.652).

Filter: a Hebrew->Greek pair is added only if the Greek lemma is rare (corpus df <= 200,
i.e. distinctive), co-occurs with the Hebrew word in >= 3 aligned verses, and appears in
>= 15% of that Hebrew word's aligned verses (strong correspondence -- names, rare terms).
The shipped dict uses ALL books (the held-out benchmark proved it generalizes).
"""
import os, sys, pickle, unicodedata
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.synonym_dict import CROSSLINGUAL_STOPLIST_GREEK

RARE_DF = 200; MIN_COND = 0.15; MIN_CO = 3; TOP = 8
CSV = os.path.join(ROOT, 'backend/synonymy/v6_additions/hebrew_greek.csv')

def norm_gr(s):
    s = unicodedata.normalize('NFD', str(s).strip().lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.replace('ς', 'σ')

def main():
    data = pickle.load(open(os.path.join(ROOT, 'research/languages/hebrew/hegrc_lemmas.pkl'), 'rb'))
    books = list(data)
    # existing pairs (normalized) to avoid duplicates
    existing = set()
    lines = []
    with open(CSV, encoding='utf-8') as f:
        for line in f:
            lines.append(line.rstrip('\n'))
            s = line.strip()
            if s and not s.startswith('#'):
                p = s.split(',')
                if len(p) >= 2:
                    existing.add((p[0].strip(), norm_gr(p[1])))
    # corpus Greek df
    df = Counter()
    for b in books:
        for chv, gs in data[b]['lxx']:
            for g in set(gs): df[g] += 1
    # co-occurrence over all books
    co = defaultdict(Counter); occ = Counter()
    for b in books:
        lx = defaultdict(set)
        for chv, gs in data[b]['lxx']: lx[chv].update(gs)
        for chv, hls in data[b]['he']:
            gs = lx.get(chv)
            if not gs: continue
            for h in set(hls):
                occ[h] += 1
                for g in gs: co[h][g] += 1
    new = []
    for h, cnt in co.items():
        for g, c in cnt.most_common(TOP):
            if c >= MIN_CO and c / occ[h] >= MIN_COND and df.get(g, 0) <= RARE_DF:
                if (h, g) not in existing and len(g) >= 3 and g not in CROSSLINGUAL_STOPLIST_GREEK:
                    new.append((h, g)); existing.add((h, g))
    # append new pairs
    out = lines + ['# --- distinctive rare/name anchors mined from aligned MT-LXX (2026-08-21) ---']
    for h, g in sorted(new):
        out.append(f'{h},{g}')
    with open(CSV, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    print(f'existing pairs: {len(existing) - len(new)} | NEW rare-anchor pairs added: {len(new)}')
    print(f'wrote {CSV}')

if __name__ == '__main__':
    main()
