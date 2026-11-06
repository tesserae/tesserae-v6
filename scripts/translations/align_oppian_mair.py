#!/usr/bin/env python3
"""Oppian's Halieutica and Cynegetica, from A. W. Mair's Loeb of 1928.

Source: Internet Archive oppiancolluthust00oppiuoft (OCR text), US public domain
by publication date. Kept in the staging folder, never in the repository.

THE METHOD IS THE RUNNING HEAD (as in align_statius.py)

Each English page of the Loeb opens with a head that names the poem, book and the
Greek lines the page renders: "CYNEGETICA, I. 14-31". The Greek page that faces
it carries only the author's name. The English of a page is everything from its
head to the next head or to the next "OPPIAN" head of a Greek page, minus the
footnotes. Both poems number their lines exactly as our .tess files do (the
book lengths agree: Halieutica 797, 688, 648, 693, 680 and Cynegetica 538, 628,
525, 453, so no renumbering is applied).

Two things the OCR does that the walk has to survive:
- Digits in the head are the first thing lost. A head claiming an impossible span
  is repaired from its neighbours, and a head that cannot be made plausible is
  dropped, leaving its lines unpaired rather than paired wrongly.
- The first page of each book carries "or FISHING" or "or THE CHASE" in place of
  a range. Its lines are 1 up to the line before the next page's start.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_common as C

SRC_FILE = os.path.join(C.SRC, 'oppiancolluthust00oppiuoft.txt')
ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5}
OCR_DIGIT = str.maketrans({'O': '0', 'o': '0', 'l': '1', 'I': '1', 'S': '5', 'B': '8', 'Z': '2'})

HEAD = re.compile(r'^\W{0,3}(HALIEUT\w*|CYNEGET\w*)[.,]?\s+(?:bk\.?\s*|(?P<bk>[IVXLTY1]{1,4})[.,]\s*)?'
                  r'(?P<a>[0-9OolISBZ]{1,4})\s*(?:[-–—,]\s*|\s)?(?P<b>[0-9OolISBZ]{1,4})?\s*$')
OPENER = re.compile(r'^\W{0,3}(HALIEUT\w*|CYNEGET\w*)[.,]?\s+(?:or|on)\s+(FISHING|THE CHASE)', re.I)
GREEK_PAGE = re.compile(r'^\W{0,3}OPPIAN\W*$')

WORKS = {'halieutica': ('oppian.halieutica', 5), 'cynegetica': ('oppian_of_apamea.cynegetica', 4)}
MIN_SPAN, MAX_SPAN = 6, 45


def num(s):
    s = s.translate(OCR_DIGIT)
    return int(s) if s.isdigit() else None


def parse():
    raw = open(SRC_FILE, encoding='utf-8', errors='replace').read().split('\n')
    # the poems occupy the first part of the volume, before Colluthus
    heads = []
    for i, line in enumerate(raw):
        if OPENER.match(line):
            heads.append((i, line.strip()[:4].upper() == 'HALI' and 'halieutica' or 'cynegetica', None, None, None, True))
            continue
        m = HEAD.match(line)
        if m:
            work = 'halieutica' if m.group(1).upper().startswith('HAL') else 'cynegetica'
            bk = (m.group('bk') or '').replace('1', 'I').replace('T', 'I').replace('Y', 'V')
            book = ROMAN.get(bk)
            a, b = num(m.group('a')), num(m.group('b') or '')
            if a is None:
                continue
            if b is None:
                # "444465": two numbers run together
                s = m.group('a')
                if len(s) == 6:
                    a, b = int(s[:3]), int(s[3:])
            heads.append((i, work, book, a, b, False))
    return raw, heads


def page_text(raw, i, heads_idx, k):
    end = heads_idx[k + 1] if k + 1 < len(heads_idx) else len(raw)
    body = []
    for j in range(i + 1, end):
        if GREEK_PAGE.match(raw[j]):
            break
        body.append(raw[j])
    body = C.strip_footnotes(body)
    return C.clean_english(body)


def build():
    raw, heads = parse()
    idxs = [h[0] for h in heads]
    pages = []
    for k, (i, work, book, a, b, opener) in enumerate(heads):
        text = page_text(raw, i, idxs, k)
        pages.append([work, book, a, b, opener, text])
    # book for pages with a lost or garbled numeral, and openers: walk in order
    fixed = dropped = 0
    out = []
    cur_work, cur_book, prev_end = None, 0, None
    for k, (work, book, a, b, opener, text) in enumerate(pages):
        if work != cur_work:
            cur_work, cur_book, prev_end = work, 0, None
        if opener:
            cur_book += 1
            # lines 1 .. next page's start - 1
            nxt = next((p for p in pages[k + 1:] if p[0] == work and not p[4] and p[2]), None)
            end = (nxt[2] - 1) if nxt else None
            if end and 5 <= end <= MAX_SPAN:
                out.append((work, cur_book, 1, end, text))
                prev_end = end
            else:
                dropped += 1
            continue
        if book and book != cur_book and a is not None and a <= 40:
            cur_book = book                      # numeral read, and the page is near a book start
        elif book is None:
            book = cur_book
        if book is not None and book != cur_book:
            # a numeral that disagrees with the walk: trust the walk unless the lines restart
            if prev_end is not None and a < prev_end:
                cur_book = book
        book = cur_book
        if b is None or b < a:
            if prev_end is not None and b is not None:
                # start digit(s) lost: "6-93" read as end only
                pass
            dropped += 1
            continue
        span = b - a + 1
        if not (MIN_SPAN <= span <= MAX_SPAN) and prev_end is not None:
            cand = prev_end + 1
            if MIN_SPAN <= b - cand + 1 <= MAX_SPAN:
                a, span = cand, b - cand + 1
                fixed += 1
        if not (MIN_SPAN <= span <= MAX_SPAN) and not (span >= 3 and b is not None):
            dropped += 1
            continue
        if prev_end is not None and a <= prev_end and book == cur_book and out and out[-1][1] == book and out[-1][0] == work:
            a = prev_end + 1
            if a > b:
                dropped += 1
                continue
        out.append((work, book, a, b, text))
        prev_end = b
    return out, fixed, dropped, len(pages)


# ---------------------------------------------------------------------------
# Colluthus and Tryphiodorus: no ranges in the heads.
#
# These two short poems carry no line numbers in the running heads, only the
# poem's title on English pages and the poet's name on Greek pages. The Greek
# page that faces each English page is the one just before it, so an English
# page renders exactly the verse lines on the Greek page before it. The Greek
# lines of a page are counted in the scan (lines that carry no English function
# words, which drops the apparatus), the counts are scaled so the poem sums to
# our own line count, and a page's lines run from the running total.
# The scaling error is a line or two at a page edge, against units of about
# thirty lines. The name check and length correlation judge the result.
# ---------------------------------------------------------------------------
STOPW = set('of the and were to in is by for cf ed with on Hes Hom Th Il Od transposed omitted read conj '
            'Cf Paus Strabo Nonn ap Ovid Verg Ap'.split())
POEMS = {
    'colluthus': dict(work='colluthus.rape_of_helen', total=394, gname='COLLUTHUS',
                      ename='THE RAPE OF HELEN', lo=35880, hi=37480, title_first=35889),
    'tryphiodorus': dict(work='tryphiodorus.the_taking_of_ilios', total=691, gname='TRYPHIODORUS',
                         ename='THE TAKING OF ILIOS', lo=37740, hi=40585, title_first=37743),
}


def is_verse(line):
    if len(line.strip()) < 8:
        return False
    return not any(w in STOPW for w in re.findall(r'[A-Za-z]+', line))


def short_poem_pages(raw, cfg):
    pat = re.compile(r'^\W{0,3}(%s|%s)\b' % (cfg['ename'], cfg['gname']))
    heads = [i for i in range(cfg['lo'], cfg['hi']) if pat.match(raw[i])]
    segs = [(a, b) for a, b in zip(heads, heads[1:] + [cfg['hi']])]
    greek, english = [], []
    for a, b in segs:
        h = raw[a]
        body = raw[a + 1:b]
        if cfg['gname'] in h or a == cfg['title_first']:
            greek.append(sum(1 for ln in body if is_verse(ln)))
            continue
        # An English page whose successor lost its head (the Greek page that
        # follows it) arrives with that Greek page attached. Split where eight
        # verse-like lines run together.
        nz = [i for i, ln in enumerate(body) if ln.strip()]
        flags = [is_verse(body[i]) for i in nz]
        cut = None
        for k in range(len(nz) - 7):
            if all(flags[k:k + 8]):
                cut = nz[k]
                break
        if cut is not None and len(nz) > 55:
            greek_part = body[cut:]
            body = body[:cut]
            english.append(C.clean_english(C.strip_footnotes(body)))
            greek.append(sum(1 for ln in greek_part if is_verse(ln)))
        else:
            english.append(C.clean_english(C.strip_footnotes(body)))
    return greek, english


def short_poem(key):
    cfg = POEMS[key]
    raw = open(SRC_FILE, encoding='utf-8', errors='replace').read().split('\n')
    greek, english = short_poem_pages(raw, cfg)
    n = min(len(greek), len(english))
    counted = sum(greek[:n])
    scale = cfg['total'] / counted if counted else 1.0
    print(f"{key}: greek pages {len(greek)}, english pages {len(english)}, "
          f"counted {counted} against {cfg['total']} (scale {scale:.3f})")
    spans, pos = [], 0.0
    for i in range(n):
        a = int(round(pos)) + 1
        pos += greek[i] * scale
        b = min(int(round(pos)), cfg['total'])
        if b >= a and english[i]:
            spans.append((a, b, english[i]))
    return cfg, spans


def run_short(key, source, lic):
    cfg, spans = short_poem(key)
    tl = C.load_tess(os.path.join(C.TEXTS, 'grc', cfg['work'] + '.tess'))
    lines = {}
    for ref, _ in tl:
        m = re.search(r'(\d+)\.(\d+)\s*$', ref)
        if m:
            lines[(int(m.group(1)), int(m.group(2)))] = ref
    mapping = {}
    for a, b, text in spans:
        for ln in range(a, b + 1):
            ref = lines.get((1, ln))
            if ref and ref not in mapping:
                mapping[ref] = text
    return C.finish(cfg['work'], 'grc', tl, mapping, source, lic,
                    'Internet Archive', clean_notes=True)


def main():
    out, fixed, dropped, n = build()
    print(f'heads parsed: {n}   kept: {len(out)}   repaired: {fixed}   dropped: {dropped}')
    rows = []
    source = {'translator': 'A. W. Mair', 'year': 1928, 'place': 'London and New York',
              'publisher': 'William Heinemann / G. P. Putnam\'s Sons',
              'title': 'Oppian, Colluthus, Tryphiodorus, with an English translation (Loeb Classical Library 219)',
              'license': 'public domain', 'mode': 'page', 'ref_composition': ['book', 'line'],
              'url': 'https://archive.org/details/oppiancolluthust00oppiuoft',
              'source_url': 'https://archive.org/details/oppiancolluthust00oppiuoft'}
    lic = 'Public domain in the United States: published 1928 (A. W. Mair, Loeb Classical Library).'
    for key, (work, nb) in WORKS.items():
        tl = C.load_tess(os.path.join(C.TEXTS, 'grc', work + '.tess'))
        lines = {}
        for ref, _ in tl:
            m = re.search(r'(\d+)\.(\d+)\s*$', ref)
            if m:
                lines[(int(m.group(1)), int(m.group(2)))] = ref
        mapping = {}
        for w, book, a, b, text in out:
            if w != key or not text:
                continue
            for ln in range(a, b + 1):
                ref = lines.get((book, ln))
                if ref and ref not in mapping:
                    mapping[ref] = text
        rows.append(C.finish(work, 'grc', tl, mapping, source, lic, 'Internet Archive', clean_notes=True))
    for key in POEMS:
        rows.append(run_short(key, source, lic))
    C.save_report('oppian', rows)


if __name__ == '__main__':
    main()
