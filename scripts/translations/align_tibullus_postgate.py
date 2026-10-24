#!/usr/bin/env python3
"""Tibullus, from J. P. Postgate's prose translation in the Loeb of 1912.

Source: Internet Archive catullustibullus0000catu (OCR text), US public domain
by publication date (London: Heinemann; New York: Macmillan, 1912).

METHOD: THE FACING LATIN PAGE IS THE KEY

Postgate's running heads name the book and poem ("TIBULLUS I. I.") but give no
line numbers, and the prose English cannot be counted against the verse. What the
scan does read well is the Latin on the facing page: ordinary type, one verse to
a line. So each English page is paired with the Latin page immediately before it,
the Latin lines of that page are located in OUR Latin text (the nearest line
ahead of the last one found, by letter similarity), and the English page is
assigned to the lines from the first to the last found.

Nothing here depends on the English at all, and nothing depends on counting. A
Latin page whose lines cannot be found leaves its lines unpaired.

Books III and IV in Postgate's Loeb are numbered differently from our Books 3
and its numbered poems, so this is checked, not assumed: the name check and the
length correlation judge the whole file, and the number of Latin lines found per
page is printed.
"""
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_common as C

SRC_FILE = os.path.join(C.SRC, 'catullustibullus0000catu.txt')
FIRST, LAST = 8461, 15125          # Tibullus through Sulpicia's Garland (1-based)
FOLIO = re.compile(r'^\s*(\d{2,3})\s*$')


def norm(s):
    s = s.lower().replace('v', 'u').replace('j', 'i')
    s = re.sub(r'[^a-z]', '', s)
    return s.replace('ae', 'e').replace('oe', 'e')


HEAD = re.compile(r'^\W{0,3}TIB[UV]LL[UV]S\b[ .\dIVXLivxlnr]{0,14}$')


def pages(raw):
    """Pages, cut at folio numbers AND at running heads. A folio the scan lost
    would otherwise fuse two pages into one, so every head also starts a page."""
    out, cur = [], []
    for line in raw[FIRST - 1:LAST]:
        t = re.sub(r'[ \t]+', ' ', line).strip()
        if FOLIO.match(line):
            out.append(cur)
            cur = []
        elif HEAD.match(t) and sum(1 for ln in cur if ln) > 6:
            out.append(cur)
            cur = [t]
        else:
            cur.append(t)
    out.append(cur)
    return [p for p in out if sum(1 for ln in p if ln) > 6]


def kind(page):
    """Latin pages carry the head TIBVLLVS, English pages TIBULLUS and the
    book and poem; the letter U against V is read reliably by the scan, so the
    head decides and English-word density settles the pages whose head is lost."""
    body = [ln for ln in page if ln]
    head = ' '.join(body[:4]).upper()
    if re.search(r'TIB[UV]LL[UV]S\s+[IVXL1]+\s*\.', head):
        return 'english'
    if 'TIBVLLVS' in head:
        return 'latin'
    if 'TIBULLUS' in head:
        return 'english'
    return 'english' if C.english_score(' '.join(body[:40])) >= 0.2 else 'latin'


def main():
    raw = open(SRC_FILE, encoding='utf-8', errors='replace').read().split('\n')
    pgs = pages(raw)
    tl = C.load_tess(os.path.join(C.TEXTS, 'la', 'tibullus.elegies.tess'))
    refs, texts = [], []
    for ref, t in tl:
        refs.append(ref)
        texts.append(norm(t))
    n = len(refs)
    print(f'pages: {len(pgs)}   our lines: {n}')

    last = -1
    spans = []        # (first idx, last idx, english)
    found_counts = []
    for k in range(len(pgs) - 1):
        if kind(pgs[k]) != 'latin' or kind(pgs[k + 1]) != 'english':
            continue
        lat = [re.sub(r'\s+\d+\s*$', '', ln) for ln in pgs[k]
               if ln and not re.match(r'^[\^\d*°]', ln) and 'TIBVLLVS' not in ln.upper().replace('U', 'V')]
        hits = []
        pos = last
        for ln in lat:
            key = norm(ln)
            if len(key) < 12:
                continue
            best, bi = 0.0, None
            for j in range(max(pos + 1, 0), min(pos + 90, n)):
                if abs(len(texts[j]) - len(key)) > 0.35 * max(len(key), 1):
                    continue
                r = difflib.SequenceMatcher(None, key, texts[j]).quick_ratio()
                if r >= 0.7:
                    r = difflib.SequenceMatcher(None, key, texts[j]).ratio()
                    if r > best:
                        best, bi = r, j
            if bi is not None and best >= 0.72:
                hits.append(bi)
                pos = bi
        found_counts.append(len(hits))
        if len(hits) < 4:
            continue
        a, b = hits[0], hits[-1]
        if last >= 0 and 0 < a - (last + 1) <= 3:
            a = last + 1
        body = [ln for ln in pgs[k + 1]]
        # the English page's own head and any trailing notes
        body = [ln for ln in body if not re.match(r'^TIBULLUS\b', ln)]
        text = C.clean_english(C.strip_footnotes(body))
        text = re.sub(r'(?:(?<=\s)|^)\d{1,3}\s+(?=[A-Z“‘\'"(])', '', text)   # margin line numbers
        # a running head the page cut left inside the text ("TIBULLUS] III. II.")
        text = re.sub(r'TIB[UV]LL[UV]S\]?\s*[IVXLHNUTivxlhnut1]{1,6}\.?\s*[IVXLHNUTivxlhnut1]{1,6}\.', '', text)
        text = re.sub(r'\s{2,}', ' ', text).strip()
        spans.append((a, b, text))
        last = b
    print(f'pairs used: {len(spans)}   latin lines found per page: '
          f'min {min(found_counts)}, median {sorted(found_counts)[len(found_counts) // 2]}, max {max(found_counts)}')

    mapping = {}
    for a, b, text in spans:
        for j in range(a, b + 1):
            mapping.setdefault(refs[j], text)
    source = {'translator': 'J. P. Postgate', 'year': 1912, 'place': 'London and New York',
              'publisher': 'William Heinemann / The Macmillan Co.',
              'title': 'Catullus, Tibullus and Pervigilium Veneris (Loeb Classical Library 6), Tibullus translated by J. P. Postgate',
              'license': 'public domain', 'mode': 'page', 'ref_composition': ['book', 'poem', 'line range'],
              'url': 'https://archive.org/details/catullustibullus0000catu',
              'source_url': 'https://archive.org/details/catullustibullus0000catu'}
    row = C.finish('tibullus.elegies', 'la', tl, mapping, source,
                   'Public domain in the United States: published 1912 (J. P. Postgate, Loeb Classical Library).',
                   'Internet Archive', clean_notes=True)
    C.save_report('tibullus', [row])


if __name__ == '__main__':
    main()
