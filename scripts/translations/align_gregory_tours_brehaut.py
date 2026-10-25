#!/usr/bin/env python3
"""English for Gregory of Tours, Historiarum libri X (Latin Wikisource text).

Ernest Brehaut, History of the Franks by Gregory Bishop of Tours, selections
translated with notes (Columbia University Press, 1916; Project Gutenberg
#74955), public domain. Brehaut numbers the chapters as the Latin does, so a
Latin line book.chapter.paragraph takes the English of that book and chapter.
Where Brehaut summarized a passage he marks it with square brackets
("[7. Abraham ... 8. Isaac ...]"): those chapters are left without English
rather than served as a summary beside the full Latin. Brehaut's footnote
numbers and letters are removed.

Usage: align_gregory_tours_brehaut.py --english pg74955.txt --tess FILE --out OUT.json
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'corpus'))
from align_batch3 import emit, tess_refs  # noqa: E402

ORD = ['FIRST', 'SECOND', 'THIRD', 'FOURTH', 'FIFTH', 'SIXTH', 'SEVENTH', 'EIGHTH', 'NINTH', 'TENTH']


def clean(t):
    t = re.sub(r'\[\d+\]', '', t)
    t = re.sub(r'\[[A-Z]{1,2}\]', '', t)
    t = t.replace('_', '')
    return re.sub(r'\s+', ' ', t).strip()


def parse(path):
    raw = open(path, encoding='utf-8').read()
    lines = raw.split('\n')
    starts = {}
    ends = {}
    for i, ln in enumerate(lines):
        u = ln.strip()
        for n, o in enumerate(ORD, 1):
            if re.search(r'HERE BEGINS (THE )?' + o + r' BOOK', u) or (n == 8 and u.endswith('BEGINS BOOK EIGHT')) or (n == 9 and 'BEGINS BOOK NINE' in u):
                starts.setdefault(n, i)
            if re.search(r'HERE ENDS .*' + o + r' BOOK', u) or (n == 1 and u.startswith('HERE ENDS THE FIRST BOOK')):
                ends.setdefault(n, i)
    out = {}   # (book, chapter) -> text ; (book, 'pr') -> text
    for b in range(1, 11):
        seg = lines[starts[b] + 1: ends[b]]
        paras, cur = [], []
        for ln in seg:
            if ln.strip():
                cur.append(ln.strip())
            elif cur:
                paras.append(' '.join(cur))
                cur = []
        if cur:
            paras.append(' '.join(cur))
        chap = 'pr'
        buf = {}
        for p in paras:
            if re.match(r'^\*[\s*]*$', p):
                continue
            q = re.sub(r'^\[[A-Z]{1,2}\]\s*', '', p)
            m = re.match(r'^(\d+)\.\s+(.*)', q)
            if m and not q.startswith('['):
                chap = int(m.group(1))
                buf.setdefault(chap, []).append(m.group(2))
            elif q.startswith('['):
                # bracketed summary of one or more chapters: no English for them
                for mm in re.finditer(r'(?:^\[|\s)(\d+)\.\s', q):
                    pass
                chap = 'summary'
            else:
                if chap != 'summary':
                    buf.setdefault(chap, []).append(q)
        for c, ps in buf.items():
            out[(b, c)] = clean(' '.join(ps))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--english', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    eng = parse(a.english)
    print('  english chapters parsed:', len(eng))
    refs, lat = tess_refs(a.tess, 'greg. tur. hist.')
    mapping = {}
    for ref, tail in refs:
        b, c, _p = tail.split('.')
        if b == 'pr':
            continue
        key = (int(b), 'pr' if c == 'pr' else int(c))
        if key in eng and len(eng[key].split()) >= 3:
            mapping[ref] = eng[key]
    ok = emit(a.out, 'la/gregory_of_tours.historiarum_libri_x', refs, lat, mapping, {
        'sources': [{'translator': 'Ernest Brehaut', 'year': 1916,
                     'title': 'History of the Franks by Gregory Bishop of Tours, selections translated with notes',
                     'publisher': 'Columbia University Press, New York (Project Gutenberg #74955)',
                     'mode': 'chapter-exact',
                     'ref_composition': ['book', 'chapter', 'paragraph'],
                     'source_url': 'https://www.gutenberg.org/ebooks/74955'}],
        'license': 'Public domain: published 1916.',
        'attribution': 'Ernest Brehaut (1916), via Project Gutenberg',
        'notes': 'Chapters Brehaut summarized in square brackets have no English here.'})
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
