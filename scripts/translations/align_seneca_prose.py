#!/usr/bin/env python3
"""Seneca's prose (besides the epistles): De Beneficiis, the Dialogues,
De Clementia, and the Naturales Quaestiones, chapter-exact.

Sources, all US public domain:
  - De Beneficiis: Aubrey Stewart's Bohn (1887), Project Gutenberg 3794 —
    clean text, chapters as standalone roman-numeral lines under BOOK
    headings. Chapter-keyed EXACT.
  - Dialogues + De Clementia: Stewart's "Minor Dialogues with On
    Clemency" (Bohn 1889), Project Gutenberg 64576 — clean text. The
    twelve dialogues open with "THE <Nth> BOOK OF THE DIALOGUES..." title
    lines and Clemency's two books with "...BOOK OF THE DIALOGUE...";
    chapters are inline roman markers ("II. Next, if you choose...")
    read with the strict-successor chain, chapter I implicit. Chapter-
    keyed EXACT (our refs are book.chapter.section; every section of a
    chapter serves that chapter's English).
  - Naturales Quaestiones: John Clarke, "Physical Science in the Time of
    Nero" (1910), Project Gutenberg 76392 — clean text; per-book PREFACE
    blocks and standalone roman chapter lines. Chapter-keyed EXACT, with
    each book's preface serving the corpus praef refs.

REFUSALS. A work whose parsed chapter count differs from the corpus's by
more than one is refused and printed. De Otio is not attempted at all:
our refs number its four chapters 29-32 (the transmission's continuation
of De Vita Beata), Stewart numbers them 1-8, and with two moving
numbering systems and 36 lines at stake a wrong guess costs more than
the coverage is worth.

Usage:
    python scripts/translations/align_seneca_prose.py \
        --src-dir <dir with pg3794.txt stewart_dialogues.txt clarke_qnat.txt> \
        --tess-dir texts/la --out-dir <dir>
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50}


def roman_to_int(s):
    s = (s.upper().replace('T', 'I').replace('1', 'I').replace('!', 'I')
         .replace('Y', 'V'))
    s = re.sub(r'[^IVXL]', '', s)
    if not s:
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN[ch]
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total if total > 0 else None


def chapter_chain(lines, inline=False):
    """[(chapter, text)] read with the strict-successor chain.

    inline=False: a chapter is a standalone roman-numeral line (the clean
    Gutenberg shape). inline=True: the numeral opens the paragraph's first
    line (the Bohn scan shape), and chapter I is implicit at the start.
    """
    chapters, cur, buf = [], None, []

    def flush():
        if cur is not None and buf:
            text = ' '.join(buf)
            text = re.sub(r'\[\d+\]', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            chapters.append((cur, text))
    if inline:
        cur = 1
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if inline:
            m = re.match(r'^([IVXL]+)\.\s+(\S.*)$', s)
        else:
            # Gutenberg 3794 sets chapter I standalone but later chapters
            # inline, so both shapes are markers here
            m = re.match(r'^([IVXL]+)\.(?:\s+(\S.*))?$', s)
        n = roman_to_int(m.group(1)) if m else None
        expect = 1 if cur is None else cur + 1
        if n is not None and expect <= n <= expect + 2:
            flush()
            cur, buf = n, ([m.group(2)] if m.lastindex and m.group(2) else [])
            continue
        # scan page furniture: running headers and bare page numbers
        if re.match(r'^\d+\s*$', s) or 'MINOR' in s[:30] and s.isupper():
            continue
        if re.match(r'^CH\.\s', s) or re.match(r'^[A-Z\s.\]\[]{10,}\d*\s*$', s):
            continue
        # title-page lines ("THE THIRD BOOK OF THE DIALOGUES...", "OF
        # ANGER.", "Book I.") sit above the implicit first chapter and
        # must not be served as its opening words
        if not buf and (s.upper() == s or re.match(r'^Book [IVX]+\.$', s)):
            continue
        if cur is not None:
            buf.append(s)
    flush()
    return chapters


def write(out_dir, tessname, refs, lat, mapping, pairs, source, exact=True):
    cov = len(mapping) / len(refs) if refs else 0
    hit, n = V.score(pairs, 'la', sample=800)
    ulist, idx, ref2u = [], {}, {}
    for ref, txt in mapping.items():
        if txt not in idx:
            idx[txt] = len(ulist)
            ulist.append(txt)
        ref2u[ref] = idx[txt]
    ok = hit is not None and hit >= 0.25 and cov > 0.3
    print(f'{tessname:42s} cov {cov:.4f} ({len(mapping)}/{len(refs)}) '
          f'units {len(ulist)} names {hit}/{n} ' + ('ok' if ok else 'REJECTED'))
    if not ok:
        return
    json.dump({
        'tess_work': f'la/{tessname}', 'language': 'la',
        'n_tess_refs': len(refs), 'n_translated': len(mapping),
        'coverage': round(cov, 4),
        'mean_source_lines_per_translation_unit':
            round(len(mapping) / max(1, len(ulist)), 1),
        'alignment_confidence': 'high' if hit >= 0.5 else 'medium',
        'name_check_hit_rate': hit, 'name_check_n': n,
        'verified_by': 'names',
        'sources': [source], 'license': source['license'],
        'attribution': source['attribution'],
        'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
    }, open(os.path.join(out_dir, f'la__{tessname}.json'), 'w'),
        ensure_ascii=False)


STEWART_1889 = {
    'translator': 'Aubrey Stewart', 'year': 1889,
    'title': "Minor Dialogues, together with the Dialogue On Clemency (Bohn)",
    'publisher': 'George Bell and Sons', 'mode': 'exact',
    'ref_composition': ['dialogue', 'chapter'],
    'source_url': 'https://archive.org/details/minordialoguesto00seneuoft',
    'license': 'Public domain: published 1889. '
               'Text from the Internet Archive scan.',
    'attribution': 'Aubrey Stewart (Bohn, 1889), via the Internet Archive',
}

# printed sequence of the 1889 volume; (title regex on the scan,
# corpus file, corpus first-number) — None skips the stretch
DIALOGUES = [
    (r'OF\s+PROVIDENCE', 'seneca.de_providentia', r'sen\. prov\.'),
    (r'FIRMNESS\s+OF\s+THE\s+WISE', 'seneca.de_constantia', r'sen\. const\.'),
    (r'OF\s+ANGER', 'seneca.de_ira', r'sen\. ira\.'),
    (r'TO\s+MARCIA', 'seneca.de_consolatione_ad_marciam', r'sen\. cons\. marc\.'),
    (r'OF\s+A\s+HAPPY\s+LIFE', 'seneca.de_vita_beata', r'sen\. vit\. beat\.'),
    (r'OF\s+LEISURE', None, None),                     # De Otio: see header
    (r'(PEACE\s+OF\s+MIND|TRANQUILLITY)', 'seneca.de_tranquillitate_animi',
     r'sen\. tranq\.'),
    (r'SHORTNESS\s+OF\s+LIFE', 'seneca.de_brevitate_vitae',
     r'sen\. brev\. vit\.'),
    (r'TO\s+HELVIA', 'seneca.de_consolatione_ad_helviam',
     r'sen\. cons\. helv\.'),
    (r'TO\s+POLYBIUS', 'seneca.de_consolatione_ad_polybium',
     r'sen\. cons\. polyb\.'),
    (r'OF\s+CLEMENCY', 'seneca.de_clementia', r'sen\. cl\.'),
]


def load_tess(path, prefix_re):
    """refs[(book, chapter, section)] plus latin, from b.c.s refs."""
    refs, lat = {}, {}
    pat = re.compile(r'^<(' + prefix_re + r'\s+(\d+)\.(\d+)\.(\d+))>\s*(.*)')
    for line in open(path, encoding='utf-8', errors='replace'):
        m = pat.match(line)
        if m:
            refs[(int(m.group(2)), int(m.group(3)), int(m.group(4)))] = m.group(1)
            lat[m.group(1)] = m.group(5)
    return refs, lat


def do_benefits(src_dir, tess_dir, out_dir):
    lines = open(os.path.join(src_dir, 'pg3794.txt'),
                 encoding='utf-8', errors='replace').read().split('\n')
    # skip contents: books start at the second 'BOOK I.'
    starts = [i for i, l in enumerate(lines) if re.match(r'^BOOK [IVX]+\.$', l)]
    books, cur, buf = {}, None, []
    for i in range(starts[0], len(lines)):
        m = re.match(r'^BOOK ([IVX]+)\.$', lines[i])
        if m:
            if cur:
                books[cur] = buf
            cur, buf = roman_to_int(m.group(1)), []
            continue
        if re.match(r'^\*\*\* END', lines[i]):
            break
        buf.append(lines[i])
    if cur:
        books[cur] = buf

    refs, lat = load_tess(os.path.join(tess_dir, 'seneca.de_beneficiis.tess'),
                          r'sen\. ben\.')
    mapping, pairs = {}, []
    for b, blines in books.items():
        chapters = dict(chapter_chain(blines, inline=False))
        want = {c for (bb, c, s) in refs if bb == b}
        if want and abs(max(chapters, default=0) - max(want)) > 1:
            print(f'  de_beneficiis book {b} REFUSED '
                  f'({max(chapters, default=0)} vs {max(want)} chapters)')
            continue
        for (bb, c, s), ref in refs.items():
            if bb == b and c in chapters:
                mapping[ref] = chapters[c]
                pairs.append((lat[ref], chapters[c]))
    write(out_dir, 'seneca.de_beneficiis', refs, lat, mapping, pairs, {
        'translator': 'Aubrey Stewart', 'year': 1887,
        'title': 'L. Annaeus Seneca On Benefits (Bohn)',
        'publisher': 'George Bell and Sons (via Project Gutenberg)',
        'mode': 'exact', 'ref_composition': ['book', 'chapter'],
        'source_url': 'https://www.gutenberg.org/ebooks/3794',
        'license': 'Public domain: published 1887. '
                   'Text from Project Gutenberg.',
        'attribution': 'Aubrey Stewart (Bohn, 1887), via Project Gutenberg',
    })


# printed order of pg64576: dialogues I-XII, then Clemency I-II.
# (segment index, corpus file, corpus book number that segment answers for)
SEGMENTS = [
    ('seneca.de_providentia', r'sen\. prov\.', 1),
    ('seneca.de_constantia', r'sen\. const\.', 2),
    ('seneca.de_ira', r'sen\. ira\.', 1),
    ('seneca.de_ira', r'sen\. ira\.', 2),
    ('seneca.de_ira', r'sen\. ira\.', 3),
    ('seneca.de_consolatione_ad_marciam', r'sen\. cons\. marc\.', 6),
    ('seneca.de_vita_beata', r'sen\. vit\. beat\.', 7),
    (None, None, None),                      # De Otio: see the header
    ('seneca.de_tranquillitate_animi', r'sen\. tranq\.', 9),
    ('seneca.de_brevitate_vitae', r'sen\. brev\. vit\.', 10),
    ('seneca.de_consolatione_ad_helviam', r'sen\. cons\. helv\.', 11),
    ('seneca.de_consolatione_ad_polybium', r'sen\. cons\. polyb\.', 11),
    ('seneca.de_clementia', r'sen\. cl\.', 1),
    ('seneca.de_clementia', r'sen\. cl\.', 2),
]


def do_dialogues(src_dir, tess_dir, out_dir):
    lines = open(os.path.join(src_dir, 'pg64576.txt'),
                 encoding='utf-8', errors='replace').read().split('\n')
    lines = [re.sub(r'\{\d+\}', '', l) for l in lines]
    marks = [i for i, l in enumerate(lines)
             if re.match(r'^THE [A-Z]+ BOOK OF THE DIALOGUES? OF', l)]
    marks.append(next(i for i, l in enumerate(lines)
                      if re.match(r'^\*\*\* END', l)))
    if len(marks) - 1 != len(SEGMENTS):
        print(f'dialogue volume: expected {len(SEGMENTS)} segments, '
              f'found {len(marks) - 1}; refusing the whole volume')
        return

    per_work = {}
    for k, (tessname, prefix, book) in enumerate(SEGMENTS):
        if tessname is None:
            continue
        seg = lines[marks[k]:marks[k + 1]]
        chapters = dict(chapter_chain(seg, inline=True))
        per_work.setdefault((tessname, prefix), {})[book] = chapters

    for (tessname, prefix), by_book in per_work.items():
        refs, lat = load_tess(os.path.join(tess_dir, tessname + '.tess'),
                              prefix)
        mapping, pairs = {}, []
        for b, chapters in by_book.items():
            want = {c for (bb, c, s) in refs if bb == b}
            if not want:
                continue
            if abs(max(chapters, default=0) - max(want)) > 1:
                print(f'  {tessname} book {b} REFUSED (parsed '
                      f'{max(chapters, default=0)} vs corpus {max(want)})')
                continue
            for (bb, c, s), ref in refs.items():
                if bb == b and c in chapters:
                    mapping[ref] = chapters[c]
                    pairs.append((lat[ref], chapters[c]))
        write(out_dir, tessname, refs, lat, mapping, pairs, dict(
            STEWART_1889,
            source_url='https://www.gutenberg.org/ebooks/64576',
            publisher='George Bell and Sons (via Project Gutenberg)',
            attribution='Aubrey Stewart (Bohn, 1889), via Project Gutenberg',
            license='Public domain: published 1889. '
                    'Text from Project Gutenberg.'))


def do_qnat(src_dir, tess_dir, out_dir):
    lines = open(os.path.join(src_dir, 'pg76392.txt'),
                 encoding='utf-8', errors='replace').read().split('\n')
    # the body's BOOK I..VII (the later run of BOOK lines is the appendix
    # index); take the FIRST run, each followed within a few lines by
    # PREFACE or a bracketed subject line
    refs, lat = load_tess_qnat(os.path.join(
        tess_dir, 'seneca.quaestiones_naturales.tess'))
    # 'BOOK I' opens the table of contents, the text body, AND the
    # appendix index. The body is the run where BOOK II follows at
    # chapter-text distance, so parse only the BOOK I whose successor
    # BOOK II is farthest away, and stop at the next BOOK I after it.
    b1 = [i for i, l in enumerate(lines) if l.strip() == 'BOOK I']
    b2 = [i for i, l in enumerate(lines) if l.strip() == 'BOOK II']
    start = max(b1, key=lambda i: min((j for j in b2 if j > i),
                                      default=i) - i)
    stop = min((i for i in b1 if i > start), default=len(lines))
    lines = lines[start:stop]

    books, cur, curch, buf = {}, None, None, []

    def flush():
        if cur is not None and curch is not None and buf:
            text = ' '.join(buf)
            text = re.sub(r'\[\d+\]', '', text)
            text = re.sub(r'\s{2,}\d+$', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            if text:
                books.setdefault(cur, {})[curch] = text

    for ln in lines:
        s = ln.strip()
        m = re.match(r'^BOOK ([IVX]+)$', s)
        if m and roman_to_int(m.group(1)):
            flush()
            cur, curch, buf = roman_to_int(m.group(1)), None, []
            continue
        if cur is None:
            continue
        if re.match(r'^PREFACE$', s):
            flush()
            curch, buf = 'praef', []
            continue
        m = re.match(r'^([IVXL]+)$', s)
        n = roman_to_int(m.group(1)) if m else None
        if n is not None:
            expect = 2 if curch in (None, 'praef') else \
                (curch + 1 if isinstance(curch, int) else 2)
            if curch in (None, 'praef') and n in (1, 2):
                flush()
                if n == 2 and 1 not in books.get(cur, {}):
                    # chapter I opens unnumbered right after the preface;
                    # it was accumulating under 'praef' -- accept that and
                    # open II
                    pass
                curch, buf = n, []
                continue
            if isinstance(curch, int) and curch + 1 <= n <= curch + 2:
                flush()
                curch, buf = n, []
                continue
        # strip the marginal section numbers Clarke prints at line ends
        sclean = re.sub(r'\s{2,}\d+[a-z]?$', '', ln.rstrip())
        if curch is not None and sclean.strip():
            buf.append(sclean.strip())
    flush()

    mapping, pairs = {}, []
    for (b, c, sct), ref in refs.items():
        ch = books.get(b, {}).get(c)
        if ch is None and c == 1:
            ch = books.get(b, {}).get('praef')
        if ch:
            mapping[ref] = ch
            pairs.append((lat_qnat[ref], ch))
    write(out_dir, 'seneca.quaestiones_naturales', refs, lat_qnat,
          mapping, pairs, {
              'translator': 'John Clarke', 'year': 1910,
              'title': 'Physical Science in the Time of Nero',
              'publisher': 'Macmillan (via Project Gutenberg)',
              'mode': 'exact', 'ref_composition': ['book', 'chapter'],
              'source_url': 'https://www.gutenberg.org/ebooks/76392',
              'license': 'Public domain: published 1910. '
                         'Text from Project Gutenberg.',
              'attribution': 'John Clarke (1910), via Project Gutenberg',
          })


lat_qnat = {}


def load_tess_qnat(path):
    refs = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(
            r'^<(seneca\.quaest_nat\. (\d+)\.(praef|\d+)\.?(\d*))>\s*(.*)',
            line)
        if not m:
            continue
        c = 'praef' if m.group(3) == 'praef' else int(m.group(3))
        refs[(int(m.group(2)), c, m.group(4))] = m.group(1)
        lat_qnat[m.group(1)] = m.group(5)
    return refs, lat_qnat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    do_benefits(args.src_dir, args.tess_dir, args.out_dir)
    do_dialogues(args.src_dir, args.tess_dir, args.out_dir)
    do_qnat(args.src_dir, args.tess_dir, args.out_dir)


if __name__ == '__main__':
    main()
