#!/usr/bin/env python3
"""Zosimus, Historia Nova: the 1814 English (Green and Chaplin) aligned to
texts/grc/zosimus.historia_nova.tess in blocks.

Source: the Internet Archive scan `historyofcountzo00zosiuoft` ("The History
of Count Zosimus, sometime advocate and chancellor of the Roman Empire,
translated from the original Greek, with the notes of the Oxford edition",
London: J. Davis, Green and Chaplin, 1814), its OCR text file. Published in
1814, public domain everywhere.

The translation carries book headings and paragraphs but NO chapter or
section numbers, so the alignment cannot be exact. Method, per book:

1. clean the OCR: cut the preface before the first book and the notes and
   geography after "THE END", drop running heads and signature lines, rejoin
   words hyphenated at the end of a line, and rejoin a paragraph that a page
   break cut in two;
2. take each English paragraph as a unit;
3. map every Greek line to one paragraph by dynamic programming, the map
   being non-decreasing through the book. A pair scores for each proper name
   of the Greek line found among the paragraph's words and loses for the
   distance between the line's relative position in the book and the
   paragraph's (both measured in characters);
4. a paragraph no line chose is joined to the paragraph before it, so none
   of the English drops out.

The record is written approximate, confidence medium, one unit for several
lines (the Reader then says the translation covers the selection rather
than matching it line by line). It also prints the OCR vocabulary check
used to judge whether the scan is usable.

    align_zosimus.py OCR.txt TESS OUT_DIR ENGLISH_VOCAB_DIR [--dry]
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V                       # noqa: E402
from align_perseus import length_correlation   # noqa: E402
from write_aligned import tess_refs, write_aligned   # noqa: E402

ocr_path, tess_path, out_dir, vocab_dir = sys.argv[1:5]
dry = '--dry' in sys.argv

raw = open(ocr_path, encoding='utf-8', errors='replace').read().splitlines()
HEAD = re.compile(r'^\s*(BOOK\s+THE\s+FIRST|(SECOND|THIRD|FOURTH|FIFTH|SIXTH)\s+BOOK)\s*\.?\s*$')
start = next(i for i, l in enumerate(raw) if HEAD.match(l))
end = next(i for i, l in enumerate(raw) if re.search(r'THE\s+END\s+OF\s+THE\s+HISTORY', l))
body = raw[start:end]


def running_head(line):
    """A page head or foot: 'THE HISTORY BOOK ii.', 'BOOK ii. OF ZOSIMUS. 13',
    a signature such as 'VOL. I. NO. 1. B', or a bare page number."""
    s = line.strip()
    if re.fullmatch(r'[\d\W]*', s):
        return bool(s)
    if re.search(r'\bTHE\s+HISTORY\b', s) and re.search(r'BOOK', s, re.I) and len(s) < 60:
        return True
    if re.search(r'\bOF\s*ZOSIMUS', s, re.I) and re.search(r'BOOK|\*OOK|OOK', s, re.I) and len(s) < 60:
        return True
    if re.match(r'^VOL\.?\s', s) and len(s) < 40:
        return True
    return False


books, cur = [], None
for line in body:
    if HEAD.match(line):
        cur = []
        books.append(cur)
        continue
    if cur is None or running_head(line):
        continue
    cur.append(line.rstrip())
assert len(books) == 6, len(books)


def paragraphs(lines):
    paras, buf = [], []
    for l in lines + ['']:
        if l.strip():
            buf.append(l.strip())
            continue
        if buf:
            text = ''
            for piece in buf:
                if text.endswith('-') and piece[:1].islower():
                    text = text[:-1] + piece
                else:
                    text = (text + ' ' + piece) if text else piece
            paras.append(re.sub(r'\s+', ' ', text))
            buf = []
    merged = []
    for p in paras:
        # a page break cut this paragraph: the previous one has no stop
        if merged and not re.search(r'[.;:!?"”’\'*]\s*$', merged[-1]) and p[:1].islower():
            merged[-1] += ' ' + p
        else:
            merged.append(p)
    return merged


book_paras = [paragraphs(b) for b in books]

# OCR vocabulary check: the share of the translation's words that appear in
# the corpus's own English texts.
vocab = set()
for f in glob.glob(os.path.join(vocab_dir, '*.tess')):
    for line in open(f, encoding='utf-8', errors='replace'):
        vocab.update(w.lower() for w in re.findall(r"[A-Za-z]+", line.split('\t', 1)[-1]))
words = [w.lower() for ps in book_paras for p in ps for w in re.findall(r"[A-Za-z]+", p)]
oov = sum(1 for w in words if w not in vocab)
print(f'OCR check: {len(words)} words, {oov} not in the corpus English vocabulary '
      f'({oov / len(words):.4f}); {sum(len(p) for p in book_paras)} paragraphs')

refs = tess_refs(tess_path)
src = {}
for line in open(tess_path, encoding='utf-8'):
    ref, text = line.rstrip('\n').split('\t', 1)
    src[ref[1:-1]] = text
by_book = {}
for r in refs:
    by_book.setdefault(r.split()[-1].split('.')[0], []).append(r)


def name_hits(names, stems):
    n = 0
    for _, c in names:
        sc = V.skel(c)
        for e in stems:
            if e[:4] == c[:4] or (len(c) >= 5 and len(e) >= 5 and e[:5] == c[:5]) \
                    or (len(sc) >= 3 and len(V.skel(e)) >= 3 and V.skel(e)[:3] == sc[:3]):
                n += 1
                break
    return n


LAMBDA = 6.0
units, ref_to_unit, pairs = [], {}, []
for bi, paras in enumerate(book_paras, start=1):
    brefs = by_book[str(bi)]
    glines = [src[r] for r in brefs]
    n, m = len(glines), len(paras)
    gtot = sum(len(g) for g in glines)
    ptot = sum(len(p) for p in paras)
    gpos, c = [], 0
    for g in glines:
        gpos.append((c + len(g) / 2) / gtot)
        c += len(g)
    ppos, c = [], 0
    for p in paras:
        ppos.append((c + len(p) / 2) / ptot)
        c += len(p)
    gnames = [V.names_in(g, 'grc') for g in glines]
    pstems = [V.english_stems(p) for p in paras]
    NEG = -1e9
    best = [[NEG] * m for _ in range(n)]
    back = [[0] * m for _ in range(n)]
    for i in range(n):
        run_best, run_arg = NEG, 0
        for j in range(m):
            if i == 0:
                prev, arg = 0.0, 0
            else:
                if best[i - 1][j] > run_best:
                    run_best, run_arg = best[i - 1][j], j
                prev, arg = run_best, run_arg
            hit = name_hits(gnames[i], pstems[j]) / max(1, len(gnames[i])) if gnames[i] else 0.0
            best[i][j] = prev + hit - LAMBDA * abs(gpos[i] - ppos[j])
            back[i][j] = arg
    j = max(range(m), key=lambda k: best[n - 1][k])
    choice = [0] * n
    for i in range(n - 1, -1, -1):
        choice[i] = j
        j = back[i][j]
    chosen = sorted(set(choice))
    # a paragraph nobody chose joins the chosen one before it (or the first)
    owner, last = [], chosen[0]
    for j in range(m):
        if j in chosen:
            last = j
        owner.append(last)
    text_of = {}
    for j in range(m):
        text_of[owner[j]] = (text_of[owner[j]] + ' ' + paras[j]) if owner[j] in text_of else paras[j]
    unit_index = {}
    for j in chosen:
        unit_index[j] = len(units)
        units.append(text_of[j])
    for r, ch in zip(brefs, choice):
        ref_to_unit[r] = unit_index[ch]
        pairs.append((src[r], units[unit_index[ch]]))
    print(f'book {bi}: {n} Greek lines, {m} English paragraphs, {len(chosen)} units')

hit, nn = V.score(pairs, 'grc')
corr = length_correlation(pairs)
print(f'refs {len(refs)} translated {len(ref_to_unit)} units {len(units)} '
      f'(mean {len(ref_to_unit) / len(units):.2f} lines per unit)')
print(f'name check {hit} on {nn}; length correlation {corr}')
if dry:
    sys.exit(0)
path = write_aligned(
    out_dir, 'grc', 'zosimus.historia_nova', units, ref_to_unit,
    attribution='Green and Chaplin, London, 1814 (Internet Archive scan)',
    license='Public domain (published 1814).',
    sources=[{
        'translator': 'Anonymous (Green and Chaplin edition)', 'year': 1814,
        'publisher': 'J. Davis, London (printed by Green and Chaplin)',
        'title': 'The History of Count Zosimus, sometime advocate and chancellor '
                 'of the Roman Empire',
        'mode': 'paragraph blocks by dynamic programming (proper names and position)',
        'source_url': 'https://archive.org/details/historyofcountzo00zosiuoft',
        'pd_reason': 'published 1814',
        'short_attribution': 'Green and Chaplin (1814)'}],
    confidence='medium', approximate=True, tess_refs=refs,
    notes='The 1814 translation has book headings but no chapter numbers; each '
          'Greek line is mapped to an English paragraph by dynamic programming '
          '(proper names and relative position within the book). The scan is '
          'OCR text from the Internet Archive.',
    name_check={'name_check_hit_rate': hit, 'name_check_n': nn},
    verified_by='proper names; length correlation '
                f'{corr:.3f}' if corr is not None else 'proper names')
print('wrote', path)
