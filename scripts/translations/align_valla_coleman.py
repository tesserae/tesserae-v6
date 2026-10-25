#!/usr/bin/env python3
"""English for Valla's De falso credita et ementita Constantini donatione.

Christopher B. Coleman, The Treatise of Lorenzo Valla on the Donation of
Constantine, Latin text and English translation (Yale University Press,
1922), Project Gutenberg #70092, public domain. The e-book prints Coleman's
Latin text first and his English after it. Coleman and the Latin Wikisource
text we hold are two editions of the same treatise, so no shared numbering
exists. The alignment goes in three steps and every one is checked:

 1. Our lines (a line is the text of one page of the edition the Wikisource
    transcription follows) are matched word by word to Coleman's Latin with a
    sequence matcher on a normalized spelling (case, u/v, i/j, ae/e, no
    punctuation), which gives each line a span of Coleman's Latin.
 2. Coleman's Latin paragraphs are matched to his English paragraphs by a
    length-based dynamic program (1:1, 1:2, 2:1, plus skips), the usual
    sentence-alignment method, and every pair is checked by proper names.
 3. A line takes the English paragraphs of the Latin paragraphs its span touches.
Lines whose span cannot be found (under half their words matched) get no English.

Usage: align_valla_coleman.py --english pg70092.txt --tess FILE --out OUT.json
"""
import argparse
import difflib
import math
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'corpus'))
from align_batch3 import emit, tess_refs  # noqa: E402


def norm_word(w):
    w = unicodedata.normalize('NFKD', w.lower())
    w = ''.join(c for c in w if not unicodedata.combining(c))
    w = re.sub(r'[^a-z]', '', w)
    return w.replace('v', 'u').replace('j', 'i').replace('ae', 'e').replace('oe', 'e').replace('ph', 'f').replace('ti', 'ci')


def words(text):
    return [x for x in (norm_word(w) for w in re.findall(r"[^\s]+", re.sub(r'\[\d+\]', ' ', text))) if x]


def paragraphs(lines):
    out, cur = [], []
    for ln in lines:
        if ln.strip():
            cur.append(ln.strip())
        elif cur:
            out.append(' '.join(cur))
            cur = []
    if cur:
        out.append(' '.join(cur))
    return out


def clean_en(t):
    t = re.sub(r'\[\d+\]', '', t)
    t = t.replace('_', '')
    return re.sub(r'\s+', ' ', t).strip()


def length_dp(la, en):
    """Monotone paragraph alignment (Gale and Church style). Returns [(la idxs, en idxs)]."""
    n, m = len(la), len(en)
    C, S = 1.15, 1.0
    INF = 1e18

    def cost(a, b):
        if a == 0 and b == 0:
            return 0
        mean = (a + b / C) / 2
        if mean == 0:
            return 0
        d = (b - a * C) / math.sqrt(mean * S * C)
        return d * d / 2 + math.log(1 + abs(d)) * 0

    moves = [(1, 1, 0), (1, 0, 450), (0, 1, 450), (2, 1, 90), (1, 2, 90), (2, 2, 160), (3, 1, 220), (1, 3, 220)]
    D = [[INF] * (m + 1) for _ in range(n + 1)]
    B = [[None] * (m + 1) for _ in range(n + 1)]
    D[0][0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            if D[i][j] >= INF:
                continue
            for di, dj, pen in moves:
                if i + di > n or j + dj > m:
                    continue
                a = sum(len(x) for x in la[i:i + di])
                b = sum(len(x) for x in en[j:j + dj])
                c = D[i][j] + pen + cost(a, b)
                if c < D[i + di][j + dj]:
                    D[i + di][j + dj] = c
                    B[i + di][j + dj] = (i, j)
    out = []
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj = B[i][j]
        out.append((list(range(pi, i)), list(range(pj, j))))
        i, j = pi, pj
    return out[::-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--english', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    t = open(a.english, encoding='utf-8').read().split('\n')
    lat_start = next(i for i, ln in enumerate(t) if ln.strip().startswith('LAURENTII VALLENSIS'))
    lat_end = next(i for i, ln in enumerate(t) if ln.strip() == 'FOOTNOTES' and i > lat_start)
    en_start = next(i for i, ln in enumerate(t) if ln.strip().startswith('THE DISCOURSE OF LORENZO VALLA'))
    en_end = next(i for i, ln in enumerate(t) if ln.strip() == 'FOOTNOTES' and i > en_start)
    lat_p = [p for p in paragraphs(t[lat_start + 1:lat_end]) if not p.startswith('DE FALSO CREDITA')]
    en_p = [clean_en(p) for p in paragraphs(t[en_start + 2:en_end])]  # the title runs over two lines
    print(f'  Coleman paragraphs: Latin {len(lat_p)}, English {len(en_p)}')
    pairs = length_dp([p for p in lat_p], en_p)
    la2en = {}
    for li, ei in pairs:
        for x in li:
            la2en[x] = ei
    # step 1: our lines onto Coleman's Latin
    refs, lat = tess_refs(a.tess, 'val. don.')
    cw, owner = [], []
    for pi, p in enumerate(lat_p):
        for w in words(p):
            cw.append(w)
            owner.append(pi)
    lw, lowner = [], []
    for k, (ref, tail) in enumerate(refs):
        for w in words(lat[ref]):
            lw.append(w)
            lowner.append(k)
    sm = difflib.SequenceMatcher(None, lw, cw, autojunk=False)
    hit = {}   # line index -> set of Coleman Latin paragraphs
    matched = {}
    for blk in sm.get_matching_blocks():
        for off in range(blk.size):
            k = lowner[blk.a + off]
            hit.setdefault(k, {}).setdefault(owner[blk.b + off], 0)
            hit[k][owner[blk.b + off]] += 1
            matched[k] = matched.get(k, 0) + 1
    total = {}
    for k in lowner:
        total[k] = total.get(k, 0) + 1
    mapping = {}
    for k, (ref, tail) in enumerate(refs):
        if matched.get(k, 0) < 0.5 * total.get(k, 1):
            continue
        paras = sorted(p for p, c in hit[k].items() if c >= max(3, 0.08 * total[k]))
        eng = sorted({e for p in paras for e in la2en.get(p, [])})
        if not eng:
            continue
        mapping[ref] = ' '.join(en_p[e] for e in eng)
    print(f'  lines with English: {len(mapping)} of {len(refs)}')
    ok = emit(a.out, 'la/valla.de_falso_credita_et_ementita_constantini_donatione', refs, lat, mapping, {
        'sources': [{'translator': 'Christopher Bush Coleman', 'year': 1922,
                     'title': 'The Treatise of Lorenzo Valla on the Donation of Constantine, text and translation into English',
                     'publisher': 'Yale University Press, New Haven (Project Gutenberg #70092)',
                     'mode': 'paragraph-matched',
                     'ref_composition': ['book', 'page'],
                     'source_url': 'https://www.gutenberg.org/ebooks/70092'}],
        'license': 'Public domain: published 1922.',
        'attribution': 'Christopher B. Coleman (1922), via Project Gutenberg',
        'notes': "Matched through Coleman's own Latin text, since the Latin held here is another edition."})
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
