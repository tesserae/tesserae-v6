#!/usr/bin/env python3
"""Statius: Thebaid, Silvae and Achilleid, from Mozley's Loeb of 1928.

THE LAST BIG GAP IN LATIN

14,783 lines with no English at all, and the poet at the centre of the Flavian
intertextual work this project exists to support. Perseus carries a translation
of none of the three. Project Gutenberg has none either.

WHERE THE ALIGNMENT DATA COMES FROM, WHICH IS THE WHOLE TRICK

The plan for this was "an OCR-and-margin-number extraction": read the marginal
line numbers off a page scan. That is slow and unreliable, because marginal
digits sit alone in white space and are the first thing OCR loses.

It is also unnecessary. The Loeb prints a RUNNING HEADER on every page giving the
exact line range that page contains -- "THEBAID, I. 18-41" -- and a running
header is ordinary text in ordinary type, which is what OCR reads best. The
Internet Archive scan preserves it. So every page of English can be attached to a
known range of Latin lines without reading one marginal number.

The Silvae headers carry book, poem and line ("SILVAE, I. I. 42-65"), which is
exactly the book.poem.line our own references already use.

Two volumes, both US public domain by date of publication:
  statiusstat01statuoft       Silvae, and Thebaid I-IV
  statiuswithengli02statuoft  Thebaid V-XII, and Achilleid

WHAT THE OCR GETS WRONG, AND HOW IT IS CAUGHT

Digits are where OCR fails, and a page header is mostly digits: "66-93" comes
back as "06-93", "42-65" as "42-05". Left alone, one misread number silently
attaches a page of English to the wrong lines, and nothing downstream would
notice.

The repair does not guess. Within a book the pages are CONTIGUOUS, so each page
begins where the last one ended plus one. Where the scan disagrees with
contiguity, contiguity is believed. A page that cannot be reconciled is dropped
rather than forced. Every repair is counted and printed, because a pipeline that
silently fixes things is one that silently breaks them.

Then the two tests the rest of this pipeline uses, for the same reason: wrong
English beside right Latin is invisible to the reader who needs the English.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

SRC = os.environ.get('TESSERAE_STATIUS_SRC', '/home/ncoffee/perseus_trans/statius_src')
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/la'
OUT = os.environ.get('TESSERAE_STATIUS_OUT',
                     '/home/ncoffee/perseus_trans/translations_statius')

VOLUMES = ['statiusstat01statuoft', 'statiuswithengli02statuoft']

NAME_FLOOR = 0.25
CORR_FLOOR = 0.45

# A Loeb page of Statius holds twenty-odd lines. These bound what a header is
# allowed to claim before we stop believing it. They are the whole basis of the
# repair below, so they are measured from the scan rather than guessed: the
# printed ranges cluster between 19 and 33 lines, and the bounds sit outside
# that with room for the short page at the end of a book.
MIN_SPAN = 10
MAX_SPAN = 48

# Mozley prefaces some poems with a note of his own, and the note sits on the
# page under the same running header as the verse, so it is picked up as though
# it were the translation. It is rare -- one page of the Silvae's eighty-eight,
# none of the Thebaid's two hundred and eighty-nine -- but a reader given an
# editor's remarks in place of the poem has no way to tell. Such a page is
# dropped and counted.
EDITORIAL = re.compile(r'(Statius (?:shows|here|is)|Epicedia|\bcf\.|\bibid\b'
                       r'|see Introduction)', re.I)

ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7,
         'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11, 'XII': 12}

# Letters OCR substitutes for digits. Applied ONLY inside a header's number
# fields, never to the English, so no real word is ever mangled.
OCR_DIGIT = str.maketrans({'O': '0', 'o': '0', 'l': '1', 'I': '1',
                           'S': '5', 'B': '8', 'Z': '2', 'q': '9'})

NUM = r'[0-9OolISBZq]{1,4}'
EPIC = re.compile(r'^\s*(THEBAID|ACHILLEID)[.,]?\s+([IVXL]+)[.,]\s+(' + NUM +
                  r')\s*[-–—]\s*(' + NUM + r')\s*$')
SILVA = re.compile(r'^\s*SILVAE[.,]?\s+([IVXL]+)[.,]\s+([IVXL]+)[.,]\s+(' + NUM +
                   r')\s*[-–—]\s*(' + NUM + r')\s*$')


def digits(s):
    s = s.translate(OCR_DIGIT)
    return int(s) if s.isdigit() else None


def clean(lines):
    """One Loeb page of English, out of a column of OCR."""
    out = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        s = re.sub(r'[*^~]+', '', s)        # footnote markers the scan mangles
        s = re.sub(r'\s+', ' ', s)
        out.append(s)
    text = ' '.join(out)
    text = text.replace('- ', '')            # words broken across scan lines
    text = re.sub(r'\s+([,.;:?!])', r'\1', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


def parse_volume(path):
    """[(work, book, poem, start, end, english)] in printed order."""
    pages, cur = [], None
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            k = None
            m = EPIC.match(line)
            if m:
                k = (m.group(1).lower(), ROMAN.get(m.group(2)), None,
                     digits(m.group(3)), digits(m.group(4)))
            else:
                m = SILVA.match(line)
                if m:
                    k = ('silvae', ROMAN.get(m.group(1)), ROMAN.get(m.group(2)),
                         digits(m.group(3)), digits(m.group(4)))
            if k and k[1] and k[3] is not None and k[4] is not None:
                if cur:
                    pages.append(cur[:5] + (clean(cur[5]),))
                cur = (k[0], k[1], k[2], k[3], k[4], [])
                continue
            if cur:
                cur[5].append(line)
    if cur:
        pages.append(cur[:5] + (clean(cur[5]),))
    return pages


def repair(pages):
    """Fix OCR'd page numbers, and count every repair.

    THE RULE IS THE PAGE'S OWN LENGTH, NOT CONTIGUITY. That is the correction
    that matters, and the first version of this got it backwards.

    A header is judged first on whether it is internally plausible: a Loeb page
    of Statius holds twenty-odd lines. A header that claims a sane span is
    believed AS PRINTED, even when it does not follow the previous page, because
    the usual reason for a jump is that the scan lost the header of the page in
    between. Believing contiguity there would stretch one page of English across
    the lines of a page we do not have.

    Only when the span is impossible do we conclude a digit was misread, and then
    contiguity supplies the missing one. "6-93" following a page that ended at 65
    claims 88 lines, which no page holds; contiguity says 66, and 66-93 is 28
    lines, which is exactly a page. That is a repair with two independent reasons
    to believe it.

    A header that cannot be made plausible either way is DROPPED. Sixty lines of
    the wrong English is worse than sixty lines of none.
    """
    fixed = dropped = editorial = 0
    out, prev_key, prev_end = [], None, None
    for work, book, poem, start, end, text in pages:
        key = (work, book, poem)
        if key != prev_key:
            prev_key, prev_end = key, None
        span = end - start + 1
        if not (MIN_SPAN <= span <= MAX_SPAN) and prev_end is not None:
            # The span is impossible, so a digit is wrong. Try contiguity for the
            # start, and only accept it if the result is a plausible page.
            cand = prev_end + 1
            if MIN_SPAN <= end - cand + 1 <= MAX_SPAN:
                start, span = cand, end - cand + 1
                fixed += 1
        if not (MIN_SPAN <= span <= MAX_SPAN):
            dropped += 1
            continue
        if EDITORIAL.search(text[:400]):
            editorial += 1
            continue
        out.append((work, book, poem, start, end, text))
        prev_end = end
    return out, fixed, dropped, editorial


def load_refs(path, depth):
    """{(book[, poem], line): full ref} for one .tess file."""
    refs = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'^<([^>]*)>', line)
            if not m:
                continue
            ref = m.group(1).strip()
            nums = re.findall(r'(\d+)', ref)
            if len(nums) < depth:
                continue
            refs.setdefault(tuple(int(x) for x in nums[-depth:]), ref)
    return refs


def latin_for(path):
    out = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'^<([^>]*)>\s*(.*)$', line)
            if m:
                out.setdefault(m.group(1).strip(), m.group(2).strip())
    return out


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


WORKS = [('thebaid', 'statius.thebaid', 2),
         ('achilleid', 'statius.achilleid', 2),
         ('silvae', 'statius.silvae', 3)]


def main():
    pages = []
    for vol in VOLUMES:
        p = f'{SRC}/{vol}.txt'
        if not os.path.exists(p):
            print(f'missing volume: {p}')
            continue
        pages += parse_volume(p)
    print(f'page headers parsed: {len(pages)}')
    pages, fixed, dropped, editorial = repair(pages)
    print(f'  repaired by contiguity: {fixed}   dropped as unreconcilable: {dropped}'
          f'   dropped as editorial matter: {editorial}')

    os.makedirs(OUT, exist_ok=True)
    print(f"\n{'work':20s} {'refs':>6s} {'paired':>7s} {'cov':>6s} {'names':>6s} "
          f"{'len r':>6s} {'lines/page':>10s}  verdict")
    report, total, written = [], 0, 0
    for work, tessname, depth in WORKS:
        path = f'{TESS}/{tessname}.tess'
        if not os.path.exists(path):
            print(f'{tessname:20s} -- no .tess file')
            continue
        refs, lat = load_refs(path, depth), latin_for(path)
        mine = [p for p in pages if p[0] == work]

        mapping, pairs = {}, []
        for _, book, poem, start, end, text in mine:
            if not text:
                continue
            for ln in range(start, end + 1):
                key = (book, poem, ln) if depth == 3 else (book, ln)
                ref = refs.get(key)
                if ref and ref not in mapping:
                    mapping[ref] = text
                    pairs.append((lat.get(ref, ''), text))

        cov = len(mapping) / len(refs) if refs else 0
        hit, n = V.score(pairs, 'la', sample=300)
        r = corr(pairs)
        units = len(set(mapping.values()))
        per = round(len(mapping) / units, 1) if units else 0.0
        ok = (hit is not None and hit >= NAME_FLOOR) or (r is not None and r >= CORR_FLOOR)
        hs = f'{hit:6.3f}' if hit is not None else '   n/a'
        rs = f'{r:6.3f}' if r is not None else '   n/a'
        print(f'{tessname:20s} {len(refs):6d} {len(mapping):7d} {cov:6.3f} {hs} {rs} '
              f'{per:10.1f}  ' + ('ok' if ok else 'REJECTED'))
        report.append({'work': tessname, 'refs': len(refs), 'paired': len(mapping),
                       'coverage': round(cov, 4), 'pages': len(mine),
                       'name_hit': (round(hit, 3) if hit is not None else None),
                       'length_corr': (round(r, 3) if r is not None else None),
                       'lines_per_page': per, 'status': 'ok' if ok else 'rejected'})
        if not ok:
            continue

        ulist, idx, ref2u = [], {}, {}
        for ref, txt in mapping.items():
            if txt not in idx:
                idx[txt] = len(ulist)
                ulist.append(txt)
            ref2u[ref] = idx[txt]
        json.dump({
            'tess_work': f'la/{tessname}', 'language': 'la',
            'n_tess_refs': len(refs), 'n_translated': len(mapping),
            'coverage': round(cov, 4),
            'mean_source_lines_per_translation_unit': per,
            'alignment_confidence': 'medium',
            'name_check_hit_rate': (round(hit, 3) if hit is not None else None),
            'name_check_n': n,
            'length_correlation': (round(r, 3) if r is not None else None),
            'verified_by': 'names' if (hit is not None and hit >= NAME_FLOOR) else 'page length',
            'sources': [{'translator': 'J. H. Mozley', 'year': 1928,
                         'title': 'Statius, with an English translation (Loeb)',
                         'publisher': 'William Heinemann / G. P. Putnam',
                         'mode': 'page', 'ref_composition': ['loeb page'],
                         'source_url': 'https://archive.org/details/statiusstat01statuoft'}],
            'license': ('Public domain in the United States: published 1928. '
                        'Text from the Internet Archive scan.'),
            'attribution': 'J. H. Mozley (1928), via the Internet Archive',
            'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
        }, open(f'{OUT}/la__{tessname}.json', 'w'), ensure_ascii=False)
        written += 1
        total += len(mapping)

    print(f'\nworks written: {written}   lines translated: {total:,}')
    json.dump(report, open(f'{OUT}/report.json', 'w'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
