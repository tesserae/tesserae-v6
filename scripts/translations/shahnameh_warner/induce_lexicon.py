#!/usr/bin/env python3
"""Induce a small Persian-to-English word list from a first alignment (hunalign style):
words that keep appearing in the same units. Used only to guide the second alignment pass.

Usage: induce_lexicon.py --tess FILE --translation JSON --out lexicon.json
"""
import argparse, collections, json, math, re, sys, unicodedata

STOP_EN = set('''the and of to a in that is was he his her she it they them their with for as on at by from this but not
 be are had have has him who whom which when what then there thus so all one two three these those thou thee thy thine
 shall will would should may might can could did do done been were an or if my me our we you your i us no nor out up
 down upon unto into than more most such now how yet each every both its also while what where why'''.split())

def norm_fa(t):
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if unicodedata.category(c) not in ('Mn', 'Po', 'Cf', 'Pd', 'Ps', 'Pe', 'Zs'))
    return t.replace('ي', 'ی').replace('ك', 'ک')

def en_words(text):
    out = []
    for w in re.findall(r"[a-z]+", text.lower()):
        if len(w) >= 3 and w not in STOP_EN:
            w = re.sub(r"(ing|ed|es|s)$", "", w) if len(w) > 4 else w
            out.append(w)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tess', required=True); ap.add_argument('--translation', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--min-count', type=int, default=6)
    a = ap.parse_args()
    d = json.load(open(a.translation))
    lines = {t.strip('<>'): x for t, x in (l.rstrip('\n').split('\t', 1) for l in open(a.tess, encoding='utf-8'))}
    u2 = collections.defaultdict(list)
    for r, u in d['ref_to_unit'].items(): u2[u].append(r)
    fa_docs = []; en_docs = []
    for u, rs in u2.items():
        if len(rs) > 120: continue   # very long units are the badly matched ones
        ft = set(norm_fa(t) for r in rs for t in lines[r].split())
        et = set(en_words(d['units'][u]))
        fa_docs.append(ft); en_docs.append(et)
    N = len(fa_docs)
    nf = collections.Counter(t for s in fa_docs for t in s); ne = collections.Counter(t for s in en_docs for t in s)
    co = collections.Counter()
    cf = [t for t in nf if nf[t] >= a.min_count and nf[t] < N * 0.2 and len(t) >= 2]
    cfs = set(cf); ces = set(t for t in ne if ne[t] >= a.min_count and ne[t] < N * 0.2)
    for fs, es in zip(fa_docs, en_docs):
        fl = [t for t in fs if t in cfs]; el = [t for t in es if t in ces]
        for f in fl:
            for e in el: co[(f, e)] += 1
    best = {}
    for (f, e), c in co.items():
        if c < a.min_count: continue
        dice = 2 * c / (nf[f] + ne[e]); pef = c / nf[f]
        # association: log-likelihood-ish via PMI
        pmi = math.log(c * N / (nf[f] * ne[e]))
        if dice >= 0.12 and pef >= 0.25 and pmi >= 1.5:
            if f not in best or dice > best[f][1]: best[f] = (e, dice, c, pmi)
    lex = {f: v[0] for f, v in best.items()}
    json.dump({'lexicon': lex, 'n_units': N, 'details': {f: list(v) for f, v in list(best.items())[:2000]}}, open(a.out, 'w'), ensure_ascii=False)
    print('units', N, 'persian words with an English partner', len(lex), 'English words', len(set(lex.values())))
    for f, v in sorted(best.items(), key=lambda kv: -kv[1][2])[:40]: print(f, v[0], v[2], round(v[1], 2))

if __name__ == '__main__':
    main()
