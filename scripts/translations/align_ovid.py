#!/usr/bin/env python3
"""Ovid's exile poetry and calendar: Tristia, Ex Ponto, Fasti.

The Metamorphoses, Amores, Ars and Heroides came in with the Perseus rebuild;
these three had nothing. Two sources, one script:

TRISTIA and EX PONTO: Wheeler's Loeb of 1924 (US public domain by date),
Internet Archive scan bwb_W9-CQC-386. The same running-header trick as
Statius and Aristophanes: every English page is headed "TRISTIA, I. v. 13-42"
or "EX PONTO, II. v. 15-42" - book in capitals, poem in lower-case romans,
then the line range. Tristia book II is a single poem and its headers carry
no poem numeral; our refs call it poem 1. The facing Latin pages are headed
"TRISTIUM LIBER PRIMUS" and never match the pattern.

FASTI: no public-domain Loeb exists (Frazer is 1931, out of reach until
2027), so Riley's Bohn prose of 1851 (Internet Archive scan
fastitristiapont00oviduoft, an 1876 printing). The scan is dirtier than the
Loebs and its headers alone are not enough: the verso header carries a line
range ("12 THE FASTI ; [b. I. 128-141") but OCR loses many, and the recto
running title is "OR, CALENDAR OF OVID." with the range often mangled. What
saves the alignment is Riley's own annotation: nearly every page carries
footnotes anchored "] - Ver. 141.", and those verse numbers date the page
directly. A page's range is taken from its header when the header is
plausible (sane span, contiguous with the previous page), otherwise from its
highest footnote anchor, otherwise the page is left unpaired. Common OCR
digit confusions (G for 6, l for 1, O for 0, S for 5) are repaired before a
number is read.

As everywhere in this directory: name check and length correlation decide
whether a work is written at all, and rejection is per work, not per page.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

SRC = os.environ.get('TESSERAE_OVID_SRC', '/home/ncoffee/perseus_trans/ovid_src')
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/la'
OUT = os.environ.get('TESSERAE_OVID_OUT', '/home/ncoffee/perseus_trans/translations_ovid')

WHEELER_FILE = 'wheeler_tristia_exponto.txt'   # bwb_W9-CQC-386_djvu.txt
RILEY_FILE = 'riley_fasti.txt'                 # fastitristiapont00oviduoft_djvu.txt

NAME_FLOOR = 0.20      # elegy names fewer heroes than epic; Fasti is myth-dense
CORR_FLOOR = 0.45
MIN_SPAN, MAX_SPAN = 5, 48

DIGIT_FIX = str.maketrans({'G': '6', 'l': '1', 'I': '1', 'O': '0', 'S': '5',
                           'o': '0', 'i': '1'})


def fix_int(s):
    s = s.translate(DIGIT_FIX)
    return int(s) if s.isdigit() else None


def corr(xs, ys):
    n = len(xs)
    if n < 10:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None


def clean(lines):
    out = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        s = re.sub(r'[*^~_|]+', '', s)
        out.append(re.sub(r'\s+', ' ', s))
    text = ' '.join(out)
    text = text.replace('- ', '')
    text = re.sub(r'\s+([,.;:?!])', r'\1', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


def load_tess(path, three_level):
    """three_level: refs end book.poem.line; else book.line.
    Returns {(book[,poem]): {line: (ref, latin)}}."""
    sections = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'^<([^>]*)>\s*(.*)$', line)
            if not m:
                continue
            ref = m.group(1).strip()
            if three_level:
                n = re.search(r'(\d+)\.(\d+)\.(\d+)\s*$', ref)
                if not n:
                    continue
                key = (int(n.group(1)), int(n.group(2)))
                ln = int(n.group(3))
            else:
                n = re.search(r'(\d+)\.(\d+)\s*$', ref)
                if not n:
                    continue
                key = (int(n.group(1)),)
                ln = int(n.group(2))
            sections.setdefault(key, {})[ln] = (ref, m.group(2).strip())
    return sections


# ---------------------------------------------------------------- Wheeler ---

# A candidate header: the work's name and a line range somewhere after it.
# OCR mauls the poem numerals beyond reliable reading ("m1", "vz", "rv"), so
# the walk below trusts numbers and contiguity, and uses the numeral token
# only to resync after a failure.
W_CAND = re.compile(r'(TRISTIA|EX\s*PONTO)[S]?\s*[,.;]?\s*'
                    r'([IVXTLJ1l]+)\s*[.,]\s*(.*\d.*)')
W_CROSS = re.compile(r'(\d{1,3})\s*[-—~]+\s*([a-z0-9]{1,5})\s*[.,]\s*(\d{1,3})')
W_SINGLE = re.compile(r'(\d{1,3})\s*[-—~]+\s*(\d{1,3})\s*[.,;]?\s*$')
# The Latin verso pages are headed a bare "OVID"; a Latin book heading opens
# each new book. Both end the English text of a page.
W_CUT = re.compile(r'^\s*(OVID|TRISTIUM\s+LIBER.*|LIBER\s+[A-Z]+.*|'
                   r'EPISTULAE\s+EX\s+PONTO.*|EX\s+PONTO\s+LIBER.*)\s*$')

BOOK_CHARS = {'I': 1, 'T': 1, 'L': 1, 'J': 1, '1': 1, 'l': 1, 'V': 5, 'X': 10}
ROMANS = ['', 'i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x',
          'xi', 'xii', 'xiii', 'xiv', 'xv', 'xvi']


def book_of(tok):
    vals = [BOOK_CHARS.get(c) for c in tok]
    if None in vals or not vals:
        return None
    total = 0
    for i, v in enumerate(vals):
        total += -v if i + 1 < len(vals) and vals[i + 1] > v else v
    return total if 1 <= total <= 5 else None


def poem_score(tok, q):
    """How much the OCR'd numeral token looks like poem number q."""
    import difflib
    t = tok.lower().strip('. ')
    t = ''.join({'1': 'i', 'l': 'i', 'j': 'i', 't': 'i', 'z': 'i',
                 'r': 'i'}.get(c, c) for c in t)
    if q >= len(ROMANS):
        return 0.0
    return difflib.SequenceMatcher(None, t, ROMANS[q]).ratio()


def wheeler_pages(path):
    """[(work, book, poem_token, tail, text)] in scan order."""
    pages, cur = [], None
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = W_CAND.search(line)
            if m and len(line) < 70:
                if cur:
                    pages.append(cur[:4] + (clean(cur[4]),))
                work = ('ovid.tristia' if m.group(1).startswith('TRISTIA')
                        else 'ovid.ex_ponto')
                cur = (work, book_of(m.group(2)), m.group(2), m.group(3), [])
                continue
            if cur:
                if W_CUT.match(line):
                    pages.append(cur[:4] + (clean(cur[4]),))
                    cur = None
                else:
                    cur[4].append(line)
    if cur:
        pages.append(cur[:4] + (clean(cur[4]),))
    return pages


def align_wheeler(pages, work, tess_path):
    """Walk the pages with a cursor (book, poem, line), trusting contiguity.

    A single-range header "53-82" continues the current poem up to 82. A
    cross header "127—11. 24" finishes the current poem and opens the next,
    up to line 24. Both are validated against the poem lengths in our own
    text, a failed page is dropped rather than guessed, and after a failure
    the numeral token (unreliable, but better than nothing) plus the poem
    lengths resync the cursor.
    """
    sections = load_tess(tess_path, three_level=True)
    plen = {}
    for (b, p), lines in sections.items():
        plen[(b, p)] = max(lines)
    npoems = {}
    for (b, p) in plen:
        npoems[b] = max(npoems.get(b, 0), p)

    mapping = {}
    book = poem = 0
    at = 0                       # last line assigned in (book, poem)
    crossed = dropped = resynced = 0
    stats = {}

    def assign(b, p, lo, hi, text):
        lines = sections.get((b, p), {})
        for ln in range(lo, hi + 1):
            if ln in lines and lines[ln][0] not in mapping:
                mapping[lines[ln][0]] = text

    for w, b, ptok, tail, text in pages:
        if w != work or not text or len(text) < 200:
            continue
        if b and b != book:
            book, poem, at = b, 1, 0
        if not book:
            continue
        cm, sm = W_CROSS.search(tail), W_SINGLE.search(tail)
        # Tristia II is one long poem; its headers carry no poem numeral and
        # a "cross" match there is a misread of the plain range.
        if npoems.get(book, 0) == 1:
            cm = None
        if cm and not (sm and sm.start() <= cm.start()):
            end = int(cm.group(3))
            nxt = None
            for q in (poem + 1, poem + 2):
                if (book, q) in plen and end <= plen[(book, q)] + 2:
                    nxt = q
                    break
            if nxt is None:
                dropped += 1
                continue
            assign(book, poem, at + 1, plen.get((book, poem), at), text)
            for q in range(poem + 1, nxt):        # a poem swallowed whole
                assign(book, q, 1, plen[(book, q)], text)
            assign(book, nxt, 1, min(end, plen[(book, nxt)]), text)
            poem, at = nxt, min(end, plen[(book, nxt)])
            crossed += 1
        elif sm:
            start, end = int(sm.group(1)), int(sm.group(2))
            pl = plen.get((book, poem), 0)
            if at == 0 and poem == 1 and 1 < start <= 60:
                # first headed page of a book: the opening lines sat under
                # the book-heading page, which has no running header
                at = start - 1
            if end > at and end <= pl + 2 and 0 < end - at <= 60:
                assign(book, poem, at + 1, min(end, pl), text)
                at = min(end, pl)
            else:
                # resync: which nearby poem does this page fit?
                best, bs = None, 0.35
                for q in range(poem, min(poem + 4, npoems.get(book, 0) + 1)):
                    if end <= plen.get((book, q), 0) + 2 and (q > poem or end > at):
                        s = poem_score(ptok, q)
                        if s > bs:
                            best, bs = q, s
                if best is None:
                    dropped += 1
                    continue
                lo = start if (0 < end - start <= 60) else max(1, end - 30)
                if best == poem:
                    lo = max(lo, at + 1)
                assign(book, best, lo, min(end, plen[(book, best)]), text)
                poem, at = best, min(end, plen[(book, best)])
                resynced += 1
        else:
            dropped += 1
    print(f'  {work}: crossed {crossed}, resynced {resynced}, dropped {dropped}')
    return sections, mapping


# ------------------------------------------------------------------ Riley ---

# A page header, either side: "12 THE FASTI ; [b. I. 128—141" or
# "B. I. 141—166.] OR, CALENDAR OF OVID. 13". OCR mangles freely, so the
# separator is generous and the RANGE is validated separately.
R_SEP = re.compile(r'(THE\s+FAST|CALENDAR\s+OF|FASTI\s*[;.,]|^\s*\[?[Bb]\.\s*[IVXivxl1]+\.)')
R_RANGE = re.compile(r'[Bb8]\.\s*([IVXivxl1]+)\s*[.,;]?\s*([0-9GlIOSoi]{1,4})\s*[-—~]+\s*-?\s*([0-9GlIOSoi]{1,4})')
R_BOOK = re.compile(r'^\s*\.?\s*BOOK\s+THE\s+(\w+)', re.I)
BOOK_WORDS = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6}


def book_word(w):
    """OCR gives FIliST and SECONI; the six answers are known, so match by
    similarity the way align_aristophanes matches play titles."""
    import difflib
    hits = difflib.get_close_matches(w.lower(), list(BOOK_WORDS), n=1, cutoff=0.6)
    return BOOK_WORDS[hits[0]] if hits else None
R_FOOT = re.compile(r'\]\s*[-—]+\s*\^*\s*[VY]er[,.]\s*([0-9GlIOSoi]{1,4})')
R_FOOT_START = re.compile(r'\]\s*[-—]+\s*\^*\s*[VY]er[,.]\s*[0-9GlIOSoi]{1,4}')


def riley_pages(path, lo, hi):
    """Pages of the Fasti section: [(header_line, body_lines)]."""
    pages, cur = [], None
    with open(path, encoding='utf-8', errors='replace') as fh:
        for i, line in enumerate(fh):
            if not (lo <= i <= hi):
                continue
            s = line.strip()
            if len(s) < 90 and R_SEP.search(s) and not R_FOOT_START.search(s):
                if cur:
                    pages.append(cur)
                cur = (s, [])
                continue
            if cur:
                cur[1].append(line)
    if cur:
        pages.append(cur)
    return pages


def align_riley(path, lo, hi, tess_path):
    sections = load_tess(tess_path, three_level=False)
    book_max = {b[0]: max(l) for b, l in sections.items()}
    pages = riley_pages(path, lo, hi)
    mapping = {}
    book, prev_end = 1, 0
    in_contents = True          # the volume opens inside book I's contents
    from_header = from_anchor = merged = dropped = 0
    RANGEY = re.compile(r'\d+\s*[-—]+\s*\d+')
    for header, body in pages:
        # a BOOK heading inside the body advances the book and resets numbering
        body_text_lines, anchors, cut = [], [], False
        calm = 0
        for ln in body:
            bm = R_BOOK.match(ln.strip())
            if bm and book_word(bm.group(1)):
                nb = book_word(bm.group(1))
                if nb == book + 1:
                    book, prev_end = nb, 0
                    in_contents = True     # every book opens with a contents list
                    calm = 0
                continue
            if in_contents:
                if RANGEY.search(ln) or not ln.strip():
                    calm = 0
                    continue
                calm += 1
                if calm < 2:
                    continue
                in_contents = False
            for a in R_FOOT.finditer(ln):
                n = fix_int(a.group(1))
                if n:
                    anchors.append(n)
            if R_FOOT_START.search(ln):
                cut = True
            if not cut:
                body_text_lines.append(ln)
        text = clean(body_text_lines)
        if not text or len(text) < 80:
            continue
        start = prev_end + 1
        end = None
        hm = R_RANGE.search(header)
        if hm:
            s0, e0 = fix_int(hm.group(2)), fix_int(hm.group(3))
            if (s0 and e0 and MIN_SPAN <= e0 - s0 + 1 <= MAX_SPAN
                    and e0 > prev_end and prev_end - 10 <= s0 <= prev_end + 40):
                start, end = max(s0, prev_end + 1), e0
                from_header += 1
        if end is None:
            bmax = book_max.get(book, 900)
            good = [a for a in anchors if 1 <= a <= bmax]
            if good:
                lo = min(good)
                if lo > start + MAX_SPAN:
                    # pages were lost between; leave the gap unpaired and
                    # let the footnotes date this page directly
                    start = max(start, lo - 6)
                near = [a for a in good if a <= start + 45]
                far = [a for a in good if a > start + 45]
                if far:
                    # the next page's header was destroyed and its text is
                    # merged into this body: the footnotes run far past one
                    # page. Keep the WHOLE body (notes included) so the text
                    # really contains every verse the range claims, and let
                    # the anchors date the merged span.
                    end = max(good)
                    text = clean(ln for ln in body if not R_BOOK.match(ln.strip()))
                    merged += 1
                elif near and max(near) >= start:
                    end = max(near)
                    from_anchor += 1
        if end is None or end < start or end - start > 120:
            dropped += 1
            continue
        end = min(end, book_max.get(book, end))
        lines = sections.get((book,), {})
        for ln in range(start, end + 1):
            if ln in lines and lines[ln][0] not in mapping:
                mapping[lines[ln][0]] = text
        prev_end = end
    print(f'  fasti pages: {len(pages)}  ranged by header: {from_header}  '
          f'by footnote anchor: {from_anchor}  merged (notes kept): {merged}  '
          f'unplaceable: {dropped}')
    return sections, mapping


# ------------------------------------------------------------------ output --

def validate_and_write(work, sections, mapping, source, license_, attribution):
    name_pairs, unit_len = [], {}
    for lines in sections.values():
        for ref, latin in lines.values():
            if ref in mapping:
                name_pairs.append((latin, mapping[ref]))
                u = mapping[ref]
                s, e = unit_len.get(id(u), (0, len(u)))
                unit_len[id(u)] = (s + len(latin), e)
    n_refs = sum(len(l) for l in sections.values())
    cov = len(mapping) / n_refs if n_refs else 0
    hit, n = V.score(name_pairs, 'la', sample=400)
    r = corr([a for a, _ in unit_len.values()], [b for _, b in unit_len.values()])
    units = len(set(mapping.values()))
    per = round(len(mapping) / units, 1) if units else 0.0
    ok = (hit is not None and hit >= NAME_FLOOR) or (r is not None and r >= CORR_FLOOR)
    hs = f'{hit:.3f}' if hit is not None else 'n/a'
    rs = f'{r:.3f}' if r is not None else 'n/a'
    print(f'{work:20s} refs={n_refs:5d} paired={len(mapping):5d} cov={cov:.3f} '
          f'names={hs} (n={n}) len_r={rs} lines/unit={per}  '
          + ('ok' if ok else 'REJECTED'))
    if not ok or not mapping:
        return
    ulist, idx, ref2u = [], {}, {}
    for ref, txt in mapping.items():
        if txt not in idx:
            idx[txt] = len(ulist)
            ulist.append(txt)
        ref2u[ref] = idx[txt]
    os.makedirs(OUT, exist_ok=True)
    json.dump({
        'tess_work': f'la/{work}', 'language': 'la',
        'n_tess_refs': n_refs, 'n_translated': len(mapping),
        'coverage': round(cov, 4),
        'mean_source_lines_per_translation_unit': per,
        'alignment_confidence': 'medium',
        'name_check_hit_rate': round(hit, 3) if hit is not None else None,
        'name_check_n': n,
        'length_correlation': round(r, 3) if r is not None else None,
        'verified_by': 'names' if (hit is not None and hit >= NAME_FLOOR) else 'length',
        'sources': [source], 'license': license_, 'attribution': attribution,
        'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
    }, open(os.path.join(OUT, f'la__{work}.json'), 'w'), ensure_ascii=False)


def main():
    wpath = os.path.join(SRC, WHEELER_FILE)
    pages = wheeler_pages(wpath)
    print(f'wheeler headers parsed: {len(pages)}')
    for work in ('ovid.tristia', 'ovid.ex_ponto'):
        sections, mapping = align_wheeler(
            pages, work, os.path.join(TESS, work + '.tess'))
        validate_and_write(
            work, sections, mapping,
            {'translator': 'A. L. Wheeler', 'year': 1924,
             'title': 'Ovid: Tristia, Ex Ponto (Loeb Classical Library 151)',
             'publisher': 'William Heinemann / G. P. Putnam',
             'mode': 'page', 'ref_composition': ['loeb page'],
             'source_url': 'https://archive.org/details/bwb_W9-CQC-386'},
            'Public domain in the United States: published 1924. '
            'Text from the Internet Archive scan.',
            'A. L. Wheeler (1924), via the Internet Archive')

    rpath = os.path.join(SRC, RILEY_FILE)
    # the Fasti section: from its first BOOK heading to "END OF THE FASTI"
    lo, hi = 0, None
    with open(rpath, encoding='utf-8', errors='replace') as fh:
        for i, line in enumerate(fh):
            if lo == 0 and R_BOOK.match(line.strip()):
                lo = i
            if 'END' in line and 'FASTI' in line:
                hi = i
                break
    if hi is None:
        print('riley: could not find the Fasti section')
        return
    sections, mapping = align_riley(rpath, lo, hi, os.path.join(TESS, 'ovid.fasti.tess'))
    validate_and_write(
        'ovid.fasti', sections, mapping,
        {'translator': 'H. T. Riley', 'year': 1851,
         'title': "The Fasti, Tristia, Pontic Epistles, Ibis, and Halieuticon "
                  "of Ovid, literally translated (Bohn's Classical Library)",
         'publisher': 'Henry G. Bohn / George Bell',
         'mode': 'page', 'ref_composition': ['page'],
         'source_url': 'https://archive.org/details/fastitristiapont00oviduoft'},
        'Public domain: published 1851 (1876 printing). '
        'Text from the Internet Archive scan.',
        'H. T. Riley (1851), via the Internet Archive')


if __name__ == '__main__':
    main()
