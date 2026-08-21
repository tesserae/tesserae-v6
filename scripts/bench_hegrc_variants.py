#!/usr/bin/env python3
"""Hebrew->Greek benchmark comparing dictionary variants, from cached lemmas.

Baseline: the CATSS Hebrew-Greek dictionary (hebrew_greek.csv).
Enriched: CATSS UNION a co-occurrence dictionary derived from the aligned Masoretic-
Septuagint text, built LEAVE-ONE-BOOK-OUT (for each test book, the co-occurrence dict
comes from every OTHER book), so the gain is honest generalization, not memorization.

Task: for each Hebrew verse, rank all LXX verses of its book by corpus-IDF-weighted
shared-dictionary score; report R@1 / R@5 (true same-reference verse retrieved).
"""
import os, sys, math, pickle, unicodedata
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.synonym_dict import CROSSLINGUAL_STOPLIST_GREEK

MIN_CO = 3        # a Hebrew-Greek pair must co-occur in >= this many aligned verses
MIN_COND = 0.08   # and the Greek must appear in >= this fraction of the Hebrew word's verses
TOP_PARTNERS = 6  # keep at most this many Greek partners per Hebrew word

def norm_gr(s):
    s = unicodedata.normalize('NFD', str(s).strip().lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.replace('ς', 'σ')

def load_catss():
    d = defaultdict(set)
    with open(os.path.join(ROOT, 'backend/synonymy/v6_additions/hebrew_greek.csv'), encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'): continue
            p = line.split(',')
            if len(p) < 2: continue
            g = norm_gr(p[1])
            if len(g) >= 3 and g not in CROSSLINGUAL_STOPLIST_GREEK:
                d[p[0].strip()].add(g)
    return d

def build_cooc(data, books):
    co = defaultdict(Counter); he_occ = Counter()
    for b in books:
        d = data[b]
        lxx_by = defaultdict(set)
        for chv, gs in d['lxx']: lxx_by[chv].update(gs)
        for chv, hls in d['he']:
            gs = lxx_by.get(chv)
            if not gs: continue
            for h in set(hls):
                he_occ[h] += 1
                for g in gs: co[h][g] += 1
    out = defaultdict(set)
    for h, cnt in co.items():
        for g, c in cnt.most_common(TOP_PARTNERS):
            if c >= MIN_CO and c / he_occ[h] >= MIN_COND:
                out[h].add(g)
    return out

def bench(d, hedict, idf):
    lxx = [(chv, set(gs)) for chv, gs in d['lxx']]
    lxx_ref = {}
    for i, (chv, _) in enumerate(lxx):
        lxx_ref.setdefault(chv, i)
    r1 = r5 = n = 0
    for chv, hls in d['he']:
        if chv not in lxx_ref: continue
        true_i = lxx_ref[chv]
        heg = set()
        for h in hls: heg |= hedict.get(h, set())
        if not heg: continue
        scored = []
        for i, (_, gs) in enumerate(lxx):
            sh = heg & gs
            if sh: scored.append((sum(idf.get(g, 0.0) for g in sh), i))
        if not scored: continue
        scored.sort(reverse=True); n += 1
        if scored[0][1] == true_i: r1 += 1
        if any(i == true_i for _, i in scored[:5]): r5 += 1
    return r1, r5, n

def main():
    data = pickle.load(open(os.path.join(ROOT, 'research/languages/hebrew/hegrc_lemmas.pkl'), 'rb'))
    books = list(data.keys())
    catss = load_catss()
    # corpus-wide Greek IDF across all cached LXX verses
    Ntot = 0; df = Counter()
    for b in books:
        for chv, gs in data[b]['lxx']:
            Ntot += 1
            for g in set(gs): df[g] += 1
    idf = {g: math.log(Ntot / c) for g, c in df.items()}
    print(f'books: {len(books)} | CATSS Hebrew words: {len(catss)} | LXX verses: {Ntot}\n', flush=True)

    hdr = f'{"book":<13}{"base R@1":>9}{"base R@5":>9}{"  ":>3}{"enr R@1":>9}{"enr R@5":>9}{"verses":>8}'
    print(hdr, flush=True); print('-' * len(hdr), flush=True)
    agg = {'b1': 0, 'b5': 0, 'e1': 0, 'e5': 0, 'n': 0}
    for tb in books:
        cooc = build_cooc(data, [b for b in books if b != tb])   # leave-one-book-out
        enriched = defaultdict(set)
        for h in set(catss) | set(cooc):
            enriched[h] = catss.get(h, set()) | cooc.get(h, set())
        b1, b5, bn = bench(data[tb], catss, idf)
        e1, e5, en = bench(data[tb], enriched, idf)
        n = bn  # same verse set
        agg['b1'] += b1; agg['b5'] += b5; agg['e1'] += e1; agg['e5'] += e5; agg['n'] += n
        print(f'{tb:<13}{(b1/n if n else 0):>9.2f}{(b5/n if n else 0):>9.2f}{"":>3}'
              f'{(e1/n if n else 0):>9.2f}{(e5/n if n else 0):>9.2f}{n:>8}', flush=True)
    N = agg['n'] or 1
    print('-' * len(hdr), flush=True)
    print(f'{"OVERALL":<13}{agg["b1"]/N:>9.2f}{agg["b5"]/N:>9.2f}{"":>3}'
          f'{agg["e1"]/N:>9.2f}{agg["e5"]/N:>9.2f}{agg["n"]:>8}', flush=True)
    print(f'\nbase = CATSS dictionary; enr = CATSS + leave-one-book-out corpus co-occurrence.', flush=True)
    print('BENCH DONE', flush=True)

if __name__ == '__main__':
    main()
