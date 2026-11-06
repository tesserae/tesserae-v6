#!/usr/bin/env python3
"""Martial: English for every epigram of the complete corpus text, Bohn's prose
(1860, epigram-exact) with Ker's Loeb (1919, 1920) where Bohn has none.

WHY THIS EXISTS. The installed alignment (align_martial.py, August 2026) was built
against a 6,399-line selection. The corpus text was replaced on 2026-09-18 by a
complete edition of 9,375 lines (14 books), and the installed file now covers 6,319
of them, 67 percent, because the added lines belong to epigrams the selection never
held. Bohn, keyed to the same epigram numbers (checked book by book), covers all
but fifteen.

WHAT THE FIFTEEN ARE. Bohn prints Graglia's Italian or nothing for the grossest
epigrams. The plan was to supply them from Ker's Loeb, which was described as
complete. It is not: Ker prints the Latin of those epigrams and no English for them
(4.48 is a plain example, English page "BOOK IV. XLVI-XLIX" runs from 46 to 49
without it). So of the fifteen, Ker supplies the ones where Bohn is silent but Ker
translated (1.58, 11.45, 11.58) and twelve remain without English in either book,
which this script prints. They are left blank rather than served in Italian or
guessed.

TWO SOURCES, ONE FILE. `sources` lists Bohn (one entry), then Ker, and
`unit_sources` gives, for each unit, the index of the source that wrote it.

KER'S PAGES. The archive.org text is a facing-page Loeb: a Latin page headed
"THE EPIGRAMS OF MARTIAL" and an English page headed "BOOK I. vi-ix", each epigram
opening with its roman numeral alone on a line. OCR loses numerals and damages
others (HI for III), so the numerals of one book's English pages are read as a
whole: each numeral has a set of possible readings, and the longest strictly
increasing run of numbers through those sets is kept (best_increasing). Ker's
English is used only for an epigram Bohn lacks, and only after the name check on
the pair.

Usage:
    python align_martial_ker.py --bohn-dir DIR --ker-files vol1.txt vol2.txt \
        --tess texts/la/martial.epigrams.tess --out OUT.json
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proper_names as V  # noqa: E402
import align_martial as AM  # noqa: E402

ROMAN_VAL = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}


def to_int(s):
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN_VAL.get(ch)
        if v is None:
            return None
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total


def int_to_roman(n):
    out = ''
    for v, r in ((1000, 'M'), (500, 'D'), (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                 (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        while n >= v:
            out += r
            n -= v
    return out


# characters this OCR reads where a roman numeral stood
FIX = {'l': 'I', '1': 'I', 'i': 'I', 'v': 'V', 'x': 'X', 'H': 'II', 'h': 'II', 'm': 'III',
       'U': 'II', 'u': 'II', 'T': 'I', 'J': 'I', '!': 'I', '|': 'I', 'O': 'X', 'N': 'II'}
NUM_LINE = re.compile(r'^\s*([IVXLHlhUuiTJ1Oxv!|mN]{1,9})\s*[.,]?\s*$')


def numeral_candidates(tok):
    """Possible integer readings of an OCR'd roman numeral."""
    out = set()
    plain = tok.upper().replace('1', 'I').replace('L', 'L')
    if re.fullmatch(r'[IVXLC]+', plain):
        v = to_int(plain)
        if v:
            out.add(v)
    mapped = ''.join(FIX.get(c, c.upper()) for c in tok)
    if re.fullmatch(r'[IVXLC]+', mapped):
        v = to_int(mapped)
        if v:
            out.add(v)
    # H read as II or as one I or as V
    for rep in ('II', 'I', 'V'):
        m2 = ''.join((rep if c in 'Hh' else FIX.get(c, c.upper()) if c not in 'IVXLC' else c) for c in tok)
        if re.fullmatch(r'[IVXLC]+', m2):
            v = to_int(m2)
            if v:
                out.add(v)
    return out


ENGL = AM.ENGLISH
LATIN_HINT = set(('et est non quid qui quod in ad cum sed nec si me te se tibi mihi quae '
                  'nam ut sic iam hoc haec ille ipse sum es sunt esse tu ego nunc per pro '
                  'de ex ab quam quis tamen dum aut atque nil nihil cui quem').split())


def english_ratio(text):
    words = re.findall(r"[A-Za-z']+", text.lower())
    if not words:
        return 0.0, 0.0
    return (sum(1 for w in words if w in ENGL) / len(words),
            sum(1 for w in words if w in LATIN_HINT) / len(words))


HEAD_EN = re.compile(r'^\s*BOOK\s+([IVXLH]{1,6})\s*[.,]?\s+(\S.{0,22}[-\u2014\u2013]\s*\S{1,10})\s*$')
HEAD_LAT = re.compile(r'^\s*THE\s+EPIGRAMS\s+OF\s+MARTIAL\s*$', re.I)
PAGENO = re.compile(r'^\s*\d{1,3}\s*$')


def clean(s):
    return re.sub(r'\s+', ' ', s).strip()


def page_items(body):
    """Items of one English page, in order: ('cont', text) for words before the
    first numeral, ('mk', candidate_numbers, text) for each numeral and the
    English that follows it."""
    blocks, buf = [], []
    for ln in body + ['']:
        if ln.strip():
            buf.append(ln)
        elif buf:
            blocks.append(buf)
            buf = []
    items = []
    for blk in blocks:
        first = blk[0]
        txt = clean(' '.join(blk))
        mm = NUM_LINE.match(first)
        if mm and len(blk) == 1:
            cands = numeral_candidates(mm.group(1))
            if cands:
                items.append(['mk', cands, ''])
            continue
        if PAGENO.match(first) and len(blk) == 1:
            continue
        if re.match(r'^\d{1,2}\s', txt):
            continue   # a footnote
        m2 = re.match(r'^([IVXLH]{1,9})\s+(\S.*)$', first)
        if m2 and len(blk) >= 1 and numeral_candidates(m2.group(1)) and len(m2.group(1)) >= 2:
            items.append(['mk', numeral_candidates(m2.group(1)), ''])
            txt = clean(' '.join([m2.group(2)] + blk[1:]))
        er, lr = english_ratio(txt)
        if er < 0.12 or lr > er:
            continue   # Latin, Greek or junk
        if items:
            items[-1][2] = (items[-1][2] + ' ' + txt).strip()
        else:
            items.append(['cont', None, txt])
    return items


def best_increasing(entries):
    """entries: [(cands, text)] in page order. Choose one number per entry so
    the chosen numbers strictly increase, keeping as many entries as possible
    (longest increasing subsequence over the candidate sets). Returns
    [(number, text)] for the kept entries."""
    n = len(entries)
    best = [None] * n   # (length, number, prev_index)
    for i in range(n):
        cur = (1, None, None)
        pick = None
        for c in sorted(entries[i][0]):
            for j in range(i):
                if best[j] and best[j][1] < c and best[j][0] + 1 > (cur[0] if pick == c else 0) and best[j][0] + 1 >= cur[0]:
                    if best[j][0] + 1 > cur[0] or (best[j][0] + 1 == cur[0] and (pick is None or c < pick)):
                        cur = (best[j][0] + 1, c, j)
                        pick = c
        if cur[1] is None:
            c = min(entries[i][0])
            cur = (1, c, None)
        best[i] = cur
    # recover
    if not n:
        return []
    end = max(range(n), key=lambda i: (best[i][0], -best[i][1]))
    chain = []
    i = end
    while i is not None:
        chain.append((best[i][1], entries[i][1]))
        i = best[i][2]
    return list(reversed(chain))


def parse_ker(paths, log):
    """{(book, epigram_int): english} from the facing-page Loeb text."""
    per_book = defaultdict(list)    # book -> [(cands, text)]
    for path in paths:
        lines = open(path, encoding='utf-8', errors='ignore').read().split('\n')
        pages = []
        cur = None
        for ln in lines:
            m = HEAD_EN.match(ln)
            if m:
                bk = to_int(m.group(1).replace('H', 'II')) if re.fullmatch(r'[IVXLH]+', m.group(1)) else None
                cur = ['en', bk, []]
                pages.append(cur)
                continue
            if HEAD_LAT.match(ln):
                cur = ['lat', None, []]
                pages.append(cur)
                continue
            if cur is not None:
                cur[2].append(ln)
        for kind, bk, body in pages:
            if kind != 'en' or not bk or not 1 <= bk <= 14:
                continue
            for it in page_items(body):
                if it[0] == 'cont':
                    if per_book[bk]:
                        c, t = per_book[bk][-1]
                        per_book[bk][-1] = (c, (t + ' ' + it[2]).strip())
                else:
                    per_book[bk].append((it[1], it[2]))
    out = {}
    for bk, entries in per_book.items():
        entries = [(c, t) for c, t in entries if t]
        chain = best_increasing(entries)
        dropped = len(entries) - len(chain)
        if dropped:
            log['spurious'].append((bk, dropped))
        prev = 0
        for num, text in chain:
            if num != prev + 1:
                log['gaps'].append((bk, prev, num))
            prev = num
            out[(bk, num)] = text
    return out


EPISTLE_POEMS = {
    # the two epigrams printed inside a prefatory epistle (Books 1 and 9), which the
    # running-head page reader above never sees as numbered epigrams
    (1, 0): (r'You\s+knew\s+the\s+rites\s+to\s+jocund\s+Flora\s+dear', r'only\s+to\s+go\s+out\s*\?'),
    (9, 0): (r'Famed,\s+though\s+against\s+thy\s+will', r'to\s+thy\s+hands\s+return\s*\.'),
}


def epistle_poems(paths):
    out = {}
    for path in paths:
        t = open(path, encoding='utf-8', errors='ignore').read()
        for key, (a, b) in EPISTLE_POEMS.items():
            m = re.search(a + r'.{20,900}?' + b, t, flags=re.S)
            if m and key not in out:
                out[key] = clean(m.group(0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ker-files', nargs='+', required=True)
    ap.add_argument('--bohn-dir', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    log = {'gaps': [], 'spurious': []}
    ker = parse_ker(args.ker_files, log)
    ker.update(epistle_poems(args.ker_files))
    bohn = {}
    for b in range(1, 15):
        got = AM.parse_book(os.path.join(args.bohn_dir, f'book{b:02d}.htm'))
        for k, v in got.items():
            if k != 'epistula' and v and AM.is_english(v):
                bohn[(b, k)] = v

    refs = []
    for line in open(args.tess, encoding='utf-8', errors='ignore'):
        m = re.match(r'<(mart\. (\d+)\.([^.]+)\.(\d+))>\s*(.*)', line)
        if m:
            refs.append((m.group(1), int(m.group(2)), m.group(3), m.group(5)))

    units, unit_src, unit_of, ref_to_unit = [], [], {}, {}
    used_ker, blank = [], []
    for ref, b, ep, latin in refs:
        key = (b, int(ep)) if ep.isdigit() else None
        if key is None:
            continue
        if key not in unit_of:
            if key in bohn:
                text, src = bohn[key], 0
            elif key in ker and AM.is_english(ker[key]):
                text, src = ker[key], 1
                used_ker.append(key)
            else:
                if key not in blank:
                    blank.append(key)
                continue
            unit_of[key] = len(units)
            units.append(text)
            unit_src.append(src)
        ref_to_unit[ref] = unit_of[key]

    pairs = [(latin, units[ref_to_unit[ref]]) for ref, _, _, latin in refs if ref in ref_to_unit]
    score = V.score(pairs, 'la', sample=800)
    # per-epigram length correlation (lines vary in length, epigrams in size)
    per = defaultdict(lambda: [0, 0])
    for (r, b, e, lx) in refs:
        if r in ref_to_unit:
            per[(b, e)][0] += len(lx)
            per[(b, e)][1] = len(units[ref_to_unit[r]])
    xs = [v[0] for v in per.values()]
    ys = [v[1] for v in per.values()]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    corr = (sum((a - mx) * (c - my) for a, c in zip(xs, ys)) /
            ((sum((a - mx) ** 2 for a in xs) * sum((c - my) ** 2 for c in ys)) ** 0.5))
    # One entry for Bohn (the fourteen book pages are one translation; the Sources page and
    # the Reader's credit line would otherwise name it fourteen times) and one for Ker.
    sources = [{
        'title': 'The Epigrams of Martial translated into English prose (Bohn\'s Classical Library, 1897 printing)',
        'translator': 'anonymous (Bohn series)', 'year': 1897,
        'publisher': 'George Bell & Sons',
        'source_url': 'https://www.tertullian.org/fathers/martial_epigrams_book01.htm',
        'mode': 'exact', 'ref_composition': ['book', 'epigram'],
    }]
    sources.append({
        'title': 'Martial: Epigrams (Loeb Classical Library), 2 vols.',
        'translator': 'Walter C. A. Ker', 'year': 1920,
        'publisher': 'William Heinemann / G. P. Putnam\'s Sons',
        'source_url': 'https://archive.org/details/martialepigrams02martiala',
        'mode': 'exact', 'ref_composition': ['book', 'epigram'],
    })
    out = {
        'tess_work': 'la/martial.epigrams', 'language': 'la',
        'n_tess_refs': len(refs), 'n_translated': len(ref_to_unit),
        'coverage': round(len(ref_to_unit) / len(refs), 4),
        'mean_source_lines_per_translation_unit': round(len(ref_to_unit) / len(units), 1),
        'alignment_confidence': 'high',
        'name_check_hit_rate': score[0], 'name_check_n': score[1],
        'length_correlation': round(corr, 3),
        'verified_by': 'names',
        'sources': sources,
        'license': 'Public domain: Bohn prose translation, 1860 (1897 printing), transcription by '
                   'Roger Pearse (tertullian.org); Ker, Loeb Classical Library 1919 and 1920 '
                   '(US public domain by date of publication).',
        'attribution': 'The Epigrams of Martial translated into English prose (Bohn, Bell, 1897), '
                       'transcribed by Roger Pearse at tertullian.org; W. C. A. Ker (1919-1920), '
                       'Loeb Classical Library, via archive.org',
        'n_units_stored': len(units), 'units': units, 'unit_sources': unit_src,
        'ref_to_unit': ref_to_unit,
    }
    json.dump(out, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'refs {len(refs)} translated {len(ref_to_unit)} coverage {out["coverage"]:.4f} units {len(units)}')
    print(f'names {score}  length_r(per epigram) {corr:.3f}')
    print('from Ker:', [f'{b}.{e}' for b, e in used_ker])
    print('no English in Bohn or Ker:', [f'{b}.{e}' for b, e in blank])
    print('refs of epigram 0 (prefatory epigrams) and unnumbered:',
          sum(1 for r, b, e, lx in refs if not e.isdigit() or e == '0'))


if __name__ == '__main__':
    main()
