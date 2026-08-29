#!/usr/bin/env python3
"""Silius Italicus, Punica I-VIII, from Duff's Loeb volume I of 1927.

THE LARGEST WHOLLY UNTRANSLATED LATIN WORK LEFT

12,198 lines, none with English. The Loeb is the only complete modern
English prose version. Volume I (books 1-8) was first printed 1927 and is
US public domain; volume II (books 9-17) was first printed 1934 and is NOT
public domain until 2030, so books 9-17 stay honestly uncovered. (The 1661
Thomas Ross verse translation covers the rest but its scan is early-modern
typography that OCR cannot read reliably, and the version paraphrases too
loosely to pair line ranges; checked and rejected.)

METHOD: the Statius running-header alignment (align_statius.py), with three
repairs that scan taught us since:

1. ENGLISH PAGES ARE CUT AT THE FACING LATIN PAGE'S OWN HEADER. The June
   Statius aligner collected everything between two English headers, which
   glued the intervening Latin page and its apparatus into the served
   English (found and retrimmed 2026-08-29). Here the Latin pages carry
   their own running headers -- "SILIUS ITALICUS", or "PUNICORUM" /
   "LIBER <ORDINAL>" at a book opening -- and the English page's buffer
   stops at the first of them.

2. BOOK OPENINGS ARE REAL PAGES. The first English page of each book is
   headed "PUNICA / BOOK <ROMAN>" with no line range (the range-bearing
   headers start with the second page), which is why every Loeb-aligned
   book used to begin at ~line 20. Here that header opens a synthetic page
   for lines 1..(next header's start - 1).

3. DUFF'S ARGUMENTS ARE STRIPPED, NOT SERVED. Each book opens with an
   italic ARGUMENT (plot summary with parenthesised line ranges), split
   across the first Latin and first English page. Serving a summary as if
   it were the translation is the Medicamina failure. Scan lines from an
   'ARGUMENT' heading through the last summary line (recognised by its
   trailing "(...)" line-range parenthesis) are dropped; the eight opening
   pages were then read by eye against the Latin.

Everything else is the Statius rule set: a header claiming a plausible page
span (10-40 lines) is believed as printed; an impossible span is repaired by
contiguity or dropped; overlapping claims are trimmed; the name check and
length correlation gate the write.

Source scan: https://archive.org/details/punicasi01siliuoft (djvu text).

Usage:
    python scripts/translations/align_silius.py \
        --src   <punicasi01siliuoft_djvu.txt> \
        --tess  texts/la/silius_italicus.punica.tess \
        --out   la__silius_italicus.punica.json
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

NAME_FLOOR = 0.25
CORR_FLOOR = 0.45
MIN_SPAN, MAX_SPAN = 10, 40   # measured from the printed ranges, as in Statius

OCR_DIGIT = str.maketrans({'O': '0', 'o': '0', 'l': '1', 'I': '1', 'r': '1',
                           'S': '5', 'B': '8', 'Z': '2', 'q': '9'})
NUM = r'[0-9OolIrSBZq]{1,4}'
HEADER = re.compile(r'^\s*PUNICA[.,]?\s+([IVXLT1l]+)[.,]?\s+(' + NUM +
                    r')\s*[-–—]+\s*(' + NUM + r')\s*$')
OPENING = re.compile(r'^\s*PUNICA\s*$')
BOOK = re.compile(r'^\s*BOOK\s+([IVXLT1l]+)\s*$')
LATIN_PAGE = re.compile(r'^\s*(SILIUS\s+ITALICUS|PUNICORUM|LIBER\s+[A-Z]+)\s*$')
ARG_RANGE = re.compile(r'\(\s*\d+[^)]*\)\s*\.?\s*$')


def roman(s):
    s = s.upper().replace('T', 'I').replace('1', 'I').replace('L', 'I')
    vals = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6,
            'VII': 7, 'VIII': 8}
    return vals.get(s)


def digits(s):
    s = s.translate(OCR_DIGIT)
    return int(s) if s.isdigit() else None


def strip_argument(lines):
    """Drop an ARGUMENT block: from its heading to the last line that ends
    with a parenthesised line range, searched within the block's reach."""
    out, i = [], 0
    while i < len(lines):
        if re.match(r'^\s*ARGUMENT', lines[i]):
            last = i
            for j in range(i + 1, min(i + 30, len(lines))):
                if ARG_RANGE.search(lines[j]):
                    last = j
            i = last + 1
            continue
        out.append(lines[i])
        i += 1
    return out


def clean(lines):
    lines = strip_argument(lines)
    out = []
    for line in lines:
        s = line.strip()
        if not s or re.match(r'^\d+\s*$', s):     # page numbers
            continue
        s = re.sub(r'[*^~°]+', '', s)
        out.append(re.sub(r'\s+', ' ', s))
    text = ' '.join(out)
    text = text.replace('- ', '')
    text = re.sub(r'\s+([,.;:?!])', r'\1', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


def parse(path):
    """[(book, start, end, english)] in printed order; end=None on an
    opening page until the next page names its own start."""
    pages, cur, buf, in_latin = [], None, [], True
    lines = open(path, encoding='utf-8', errors='replace').read().split('\n')

    def flush():
        nonlocal cur, buf
        if cur:
            pages.append((cur[0], cur[1], cur[2], clean(buf)))
        cur, buf = None, []

    for i, line in enumerate(lines):
        m = HEADER.match(line)
        if m:
            b, s, e = roman(m.group(1)), digits(m.group(2)), digits(m.group(3))
            flush()
            if b and s is not None:
                cur, in_latin = (b, s, e), False
            continue
        bm = BOOK.match(line)
        if bm and roman(bm.group(1)):
            # a bare 'BOOK <n>' line opens the book's first English page
            # (book 1 prints 'PUNICA' above it; books 2-8 print it alone)
            flush()
            cur, in_latin = (roman(bm.group(1)), 1, None), False
            continue
        if OPENING.match(line):
            continue
        if LATIN_PAGE.match(line):
            flush()
            in_latin = True
            continue
        if cur and not in_latin:
            buf.append(line)
    flush()
    return pages


def repair(pages):
    """Statius rules: believe a plausible printed span; repair an impossible
    one by contiguity; give an opening page its end from the next header;
    trim overlaps; drop what cannot be reconciled."""
    fixed = dropped = overlaps = 0
    out, prev_book, prev_end = [], None, None
    for idx, (book, start, end, text) in enumerate(pages):
        if book != prev_book:
            prev_book, prev_end = book, None
        if end is None:                       # opening page
            nxt = pages[idx + 1] if idx + 1 < len(pages) else None
            if nxt and nxt[0] == book and nxt[1] and nxt[1] > start:
                end = nxt[1] - 1
            else:
                dropped += 1
                continue
            lo = 1                            # openings are legitimately short
        else:
            lo = MIN_SPAN
        span = end - start + 1
        if not (lo <= span <= MAX_SPAN) and prev_end is not None:
            cand = prev_end + 1
            if MIN_SPAN <= end - cand + 1 <= MAX_SPAN:
                start, span = cand, end - cand + 1
                fixed += 1
        if not (lo <= span <= MAX_SPAN):
            dropped += 1
            continue
        if prev_end is not None and start <= prev_end:
            overlaps += 1
            start = prev_end + 1
            if start > end:
                dropped += 1
                continue
        if not text:
            dropped += 1
            continue
        out.append((book, start, end, text))
        prev_end = end
    return out, fixed, dropped, overlaps


def corr(pairs):
    xs = [len(a) for a, b in pairs if a and b]
    ys = [len(b) for a, b in pairs if a and b]
    n = len(xs)
    if n < 10:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    pages = parse(args.src)
    pages, fixed, dropped, overlaps = repair(pages)
    print(f'pages kept: {len(pages)}  repaired: {fixed}  dropped: {dropped}'
          f'  overlaps trimmed: {overlaps}')

    refs, lat = {}, {}
    for line in open(args.tess, encoding='utf-8', errors='replace'):
        m = re.match(r'^<([^>]*)>\s*(.*)$', line)
        if not m:
            continue
        ref = m.group(1).strip()
        nums = re.findall(r'\d+', ref)
        if len(nums) >= 2:
            refs[(int(nums[-2]), int(nums[-1]))] = ref
            lat[ref] = m.group(2).strip()

    mapping, pairs = {}, []
    for book, start, end, text in pages:
        for ln in range(start, end + 1):
            ref = refs.get((book, ln))
            if ref and ref not in mapping:
                mapping[ref] = text
                pairs.append((lat.get(ref, ''), text))

    n_book_refs = {b: sum(1 for (bb, _) in refs if bb == b) for b in range(1, 18)}
    covered_refs = sum(n_book_refs[b] for b in range(1, 9))
    cov_all = len(mapping) / len(refs)
    cov_pd = len(mapping) / covered_refs if covered_refs else 0
    hit, n = V.score(pairs, 'la', sample=800)
    r = corr(pairs)
    units = sorted(set(mapping.values()), key=len)
    print(f'coverage {cov_all:.4f} of all 17 books '
          f'({cov_pd:.4f} of the PD books 1-8); names {hit} / {n}; len r {r}')
    ok = (hit is not None and hit >= NAME_FLOOR) or (r is not None and r >= CORR_FLOOR)
    if not ok:
        print('REJECTED: neither validation passed; nothing written')
        return

    ulist, idx, ref2u = [], {}, {}
    for ref, txt in mapping.items():
        if txt not in idx:
            idx[txt] = len(ulist)
            ulist.append(txt)
        ref2u[ref] = idx[txt]
    json.dump({
        'tess_work': 'la/silius_italicus.punica', 'language': 'la',
        'n_tess_refs': len(refs), 'n_translated': len(mapping),
        'coverage': round(cov_all, 4),
        'coverage_of_public_domain_books_1_8': round(cov_pd, 4),
        'mean_source_lines_per_translation_unit':
            round(len(mapping) / max(1, len(ulist)), 1),
        'alignment_confidence': 'high' if (hit or 0) >= 0.5 else 'medium',
        'name_check_hit_rate': hit, 'name_check_n': n,
        'length_correlation': (round(r, 3) if r is not None else None),
        'verified_by': 'names' if (hit or 0) >= NAME_FLOOR else 'page length',
        'sources': [{'translator': 'J. D. Duff', 'year': 1927,
                     'title': 'Silius Italicus, Punica, vol. I (Loeb)',
                     'publisher': 'William Heinemann / G. P. Putnam',
                     'mode': 'page', 'ref_composition': ['loeb page'],
                     'source_url': 'https://archive.org/details/punicasi01siliuoft'}],
        'license': 'Public domain in the United States: published 1927. '
                   'Books 9-17 (Loeb vol. II, 1934) are still in copyright '
                   'and are not included. Text from the Internet Archive scan.',
        'attribution': 'J. D. Duff (1927), via the Internet Archive',
        'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
    }, open(args.out, 'w'), ensure_ascii=False)
    print(f'wrote {args.out}: {len(mapping)} refs, {len(ulist)} units')


if __name__ == '__main__':
    main()
