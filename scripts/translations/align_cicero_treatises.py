#!/usr/bin/env python3
"""Cicero's philosophical and rhetorical treatises, from Yonge's Bohn
translations on Project Gutenberg (clean transcriptions, no OCR).

~2,700 corpus lines across ten works. Three volumes cover them:

    pg14988  Tusculan Disputations; Nature of the Gods; Commonwealth
             (Yonge, Harper 1877 printing of the Bohn text)
    pg29247  Academic Questions I (Academica) and II (Lucullus); De Finibus
             (Yonge, Bohn 1853)
    pg11080  Orations vol. IV appendix: Rhetorical Invention; Orator;
             Topics; Oratorical Partitions; Best Style of Orators
             (Yonge, Bohn 1852)

TWO KINDS OF KEY, AND THE HONESTY LINE BETWEEN THEM

Yonge numbers CHAPTERS (the roman "I., II., III." of the old editions);
our corpus references SECTIONS (the modern "§" numbering), except for two
works. Where the corpus itself is chapter-keyed -- the Partitiones
(refs chapter.section, so the chapter is the first field) and De optimo
genere (refs 1-7 = its seven chapters) -- the alignment is EXACT.

Everywhere else there is no public concordance from chapter to section in
machine-readable form, so sections are allocated to chapters by CUMULATIVE
TEXT LENGTH within each book: chapter boundaries fall where the running
share of the Latin matches the running share of the English. Those works
are marked "approximate", the unit is one chapter (2-5 sections), and the
proper-name check gates every work. A book whose chapter numerals do not
chain 1,2,3... is refused outright rather than guessed at.

Fragmentary refs with no English counterpart (rep. fr.*, Acad. 2.0/3.0)
are skipped and stay uncovered.

Usage:
    python scripts/translations/align_cicero_treatises.py \
        --src-dir <dir with pg14988.txt pg29247.txt pg11080.txt> \
        --tess-dir texts/la --out-dir <dir>
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

ROMAN_RE = re.compile(r'^([IVXLC]+)\.\s+(\S.*)$')
ORDINAL_BOOKS = ['First', 'Second', 'Third', 'Fourth', 'Fifth']


def roman_to_int(s):
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}
    total, prev = 0, 0
    for ch in reversed(s):
        v = vals.get(ch)
        if v is None:
            return None
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total


# (source file, region start regex, region end regex, book heading template,
#  tessname, ref regex, mode)
#   book heading template: 'BOOK' -> '^BOOK <ROMAN>\.' ; 'ORDINAL:<text>' ->
#   '^<Ordinal> Book Of <text>' ; None -> single flat region
#   mode: 'sections' (proportional by length) | 'chapters' (exact)
WORKS = [
    ('pg14988.txt', r'^THE TUSCULAN DISPUTATIONS\.', r'^THE NATURE OF THE GODS\.',
     'BOOK', 'cicero.tusculanae_disputationes',
     r'^<(cic\. tusc\. (\d+)\.(\d+))>\s*(.*)', 'sections'),
    ('pg14988.txt', r'^THE NATURE OF THE GODS\.', r'^ON THE COMMONWEALTH\.',
     'BOOK', 'cicero.de_natura_deorum',
     r'^<(cic\. nat\. (\d+)\.(\d+))>\s*(.*)', 'sections'),
    ('pg14988.txt', r'^ON THE COMMONWEALTH\.', r'\*\*\* END',
     'BOOK', 'cicero.de_republica',
     r'^<(cic\. rep\. (\d+)\.(\d+))>\s*(.*)', 'sections'),
    ('pg29247.txt', r'^FIRST BOOK OF THE ACADEMIC QUESTIONS\.',
     r'^SECOND BOOK OF THE ACADEMIC QUESTIONS\.', None, 'cicero.academica',
     r'^<(Cic\. Acad\. (1)\.(\d+))>\s*(.*)', 'sections'),
    ('pg29247.txt', r'^SECOND BOOK OF THE ACADEMIC QUESTIONS\.',
     r'^A TREATISE ON THE CHIEF GOOD AND EVIL\.', None, 'cicero.lucullus',
     r'^<(cic\. luc\. ()(\d+))>\s*(.*)', 'sections'),
    ('pg29247.txt', r'^A TREATISE ON THE CHIEF GOOD AND EVIL\.',
     r'^THE TUSCULAN DISPUTATIONS\.',
     'ORDINAL:The Treatise', 'cicero.de_finibus_bonorum_et_malorum',
     r'^<(cic\. fin\. (\d+)\.(\d+))>\s*(.*)', 'sections'),
    ('pg11080.txt', r'^RHETORICAL INVENTION\.',
     r'^THE ORATOR OF M\.T\. CICERO\.', 'BOOK', 'cicero.de_inventione',
     r'^<(cic\. inv\. (\d+)\.(\d+))>\s*(.*)', 'sections'),
    ('pg11080.txt', r'^THE ORATOR OF M\.T\. CICERO\.',
     r'^THE TREATISE OF M\. T\. CICERO ON TOPICS,', None, 'cicero.orator',
     r'^<(cic\. orator\. ()(\d+))>\s*(.*)', 'sections'),
    ('pg11080.txt', r'^THE TREATISE OF M\. T\. CICERO ON TOPICS,',
     r'^A DIALOGUE CONCERNING ORATORICAL PARTITIONS\.', None, 'cicero.topica',
     r'^<(cic\. top\. ()(\d+))>\s*(.*)', 'sections'),
    ('pg11080.txt', r'^A DIALOGUE CONCERNING ORATORICAL PARTITIONS\.',
     r'^THE TREATISE OF M\. T\. CICERO ON THE BEST STYLE OF ORATORS\.', None,
     'cicero.de_partitione_oratoria',
     r'^<(cic\. part\. (\d+)\.(\d+))>\s*(.*)', 'chapters'),
    ('pg11080.txt', r'^THE TREATISE OF M\. T\. CICERO ON THE BEST STYLE OF ORATORS\.',
     r'\*\*\* END', None, 'cicero.de_optimo_genere_oratorum',
     r'^<(cic\. opt\. ()(\d+))>\s*(.*)', 'chapters'),
]


def slice_region(lines, start_re, end_re):
    start = end = None
    for i, ln in enumerate(lines):
        if start is None and re.match(start_re, ln.strip()):
            start = i + 1
        elif start is not None and re.search(end_re, ln.strip()):
            end = i
            break
    return lines[start:end] if start is not None else []


def book_heading(s):
    """The volumes write book headings three ways: 'BOOK II.',
    'Second Book Of The Treatise...', 'THE SECOND BOOK OF THE RHETORIC...'."""
    m = re.match(r'^BOOK ([IVX]+)\.?$', s)
    if m:
        return roman_to_int(m.group(1))
    # ordinal headings are set in capitals or Title Case; matching them
    # case-insensitively caught wrapped prose lines ("second book. At
    # present we have only dropped hints...") and split real books in two
    for k, o in enumerate(ORDINAL_BOOKS, 1):
        if re.match(rf'^(THE )?{o.upper()} BOOK\b', s) or \
                re.match(rf'^{o} Book Of [A-Z]', s):
            return k
    return None


def split_books(lines, template):
    """[(book_number, [lines])] — a single flat region is book ''. """
    if template is None:
        return [('', lines)]
    out, cur, buf = [], None, []
    for ln in lines:
        num = book_heading(ln.strip())
        if num:
            if cur is not None:
                out.append((cur, buf))
            cur, buf = num, []
            continue
        if cur is not None:
            buf.append(ln)
    if cur is not None:
        out.append((cur, buf))
    return out


def split_chapters(lines):
    """[(chapter_number, text)]; None if the numeral chain breaks."""
    chapters, cur, buf = [], None, []

    def flush():
        if cur is not None:
            text = ' '.join(buf)
            text = re.sub(r'\[\d+\]', '', text)
            text = re.sub(r'\s+', ' ', text).strip()
            chapters.append((cur, text))
    for ln in lines:
        s = ln.rstrip()
        m = ROMAN_RE.match(s)
        # some markers lack the period ("X Let us then return..."); a bare
        # numeral is believed only when it is 2+ characters (a wrapped
        # line starting with the pronoun 'I' must never open a chapter)
        # and lands on the expected next number
        if not m:
            m2 = re.match(r'^([IVXLC]{2,})\s+(\S.*)$', s)
            m = m2
        n = roman_to_int(m.group(1)) if m else None
        expect = 1 if cur is None else cur + 1
        # a marker the transcription lost merges its chapter into the
        # previous one (the text is still there, so cumulative-length
        # allocation stays honest); allow the chain to resync over up to
        # two lost markers
        if n is not None and expect <= n <= expect + 2:
            flush()
            cur, buf = n, [m.group(2)]
            continue
        if cur is not None and s and not s.startswith('['):
            buf.append(s)
    flush()
    nums = [n for n, _ in chapters]
    increasing = all(b > a for a, b in zip(nums, nums[1:]))
    complete = len(nums) >= 0.6 * (nums[-1] if nums else 1)
    return chapters, bool(nums) and increasing and complete


def allocate(chapters, sections):
    """sections: [(sec_num, latin_len)] -> {sec_num: chapter_index} by
    cumulative length matching."""
    if not chapters or not sections:
        return {}
    etot = sum(len(t) for _, t in chapters) or 1
    ltot = sum(l for _, l in sections) or 1
    bounds = []
    acc = 0.0
    for _, t in chapters:
        acc += len(t) / etot
        bounds.append(acc)              # cumulative share at chapter end
    out, acc_l, ci = {}, 0.0, 0
    for sec, l in sections:
        mid = (acc_l + l / 2) / ltot
        acc_l += l
        while ci < len(bounds) - 1 and mid > bounds[ci]:
            ci += 1
        out[sec] = ci
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    srcs = {}
    for fname, *_ in WORKS:
        if fname not in srcs:
            srcs[fname] = open(os.path.join(args.src_dir, fname),
                               encoding='utf-8', errors='replace').read().split('\n')

    for fname, start_re, end_re, template, tessname, pat, mode in WORKS:
        region = slice_region(srcs[fname], start_re, end_re)
        if not region:
            print(f'{tessname}: region not found, skipped')
            continue
        books = split_books(region, template)

        # corpus side, grouped by book
        tess_books, lat, order = {}, {}, []
        for line in open(os.path.join(args.tess_dir, tessname + '.tess'),
                         encoding='utf-8', errors='replace'):
            m = re.match(pat, line)
            if not m:
                continue
            ref, b, sec = m.group(1), m.group(2), int(m.group(3))
            b = int(b) if b else ''
            tess_books.setdefault(b, [])
            # one section can span several tess lines in letters; here each
            # section is one line, but guard against duplicates anyway
            if not any(s == sec for s, _ in tess_books[b]):
                tess_books[b].append((sec, len(m.group(4))))
            lat[ref] = m.group(4)
            order.append((ref, b, sec))

        # a flat source region answers for a single-book corpus work even
        # when the corpus numbers that book (Academica's refs are 1.n)
        if template is None and len(books) == 1:
            real = [b for b in tess_books if tess_books[b]]
            if len(real) == 1 and mode == 'sections':
                books = [(real[0], books[0][1])]

        mapping, pairs, refused = {}, [], []
        if mode == 'chapters':
            # the corpus is chapter-keyed here: Partitiones refs are
            # chapter.section (b is the chapter), De optimo's are the bare
            # chapter number (in sec)
            chapters, ok = split_chapters(books[0][1])
            if not ok:
                refused.append(('flat', len(chapters)))
            else:
                by_ch = {n: t for n, t in chapters}
                for ref, b, sec in order:
                    ch = b if isinstance(b, int) else sec
                    if ch in by_ch:
                        mapping[ref] = by_ch[ch]
                        pairs.append((lat[ref], by_ch[ch]))
        else:
            for bnum, blines in books:
                if bnum not in tess_books:
                    print(f'  {tessname}: source book {bnum} has no corpus '
                          f'counterpart, ignored')
                    continue
                chapters, ok = split_chapters(blines)
                if not ok or len(chapters) < 3:
                    refused.append((bnum, len(chapters)))
                    continue
                secs = sorted(tess_books[bnum])
                alloc = allocate(chapters, secs)
                for ref, b, sec in order:
                    if b != bnum or sec not in alloc:
                        continue
                    text = chapters[alloc[sec]][1]
                    mapping[ref] = text
                    pairs.append((lat[ref], text))
            got = {b for b, _ in books}
            for b in tess_books:
                if b not in got and tess_books[b]:
                    print(f'  {tessname}: corpus book {b} not found in the '
                          f'source, uncovered')

        n_refs = len(order)
        cov = len(mapping) / n_refs if n_refs else 0
        hit, n = V.score(pairs, 'la', sample=800)
        ulist, idx, ref2u = [], {}, {}
        for ref, txt in mapping.items():
            if txt not in idx:
                idx[txt] = len(ulist)
                ulist.append(txt)
            ref2u[ref] = idx[txt]
        ok = hit is not None and hit >= 0.25
        exact = mode == 'chapters'
        print(f'{tessname:40s} cov {cov:.4f} ({len(mapping)}/{n_refs}) '
              f'units {len(ulist)} names {hit}/{n} '
              + (f'REFUSED books {refused} ' if refused else '')
              + ('ok' if ok else 'REJECTED'))
        if not ok:
            continue
        json.dump({
            'tess_work': f'la/{tessname}', 'language': 'la',
            'n_tess_refs': n_refs, 'n_translated': len(mapping),
            'coverage': round(cov, 4),
            'mean_source_lines_per_translation_unit':
                round(len(mapping) / max(1, len(ulist)), 1),
            'alignment_confidence': ('high' if exact and hit >= 0.5
                                     else 'medium'),
            'approximate': not exact,
            'name_check_hit_rate': hit, 'name_check_n': n,
            'verified_by': 'names',
            'sources': [{'translator': 'C. D. Yonge', 'year': 1853,
                         'title': 'Bohn Classical Library translation',
                         'publisher': 'Henry G. Bohn (via Project Gutenberg)',
                         'mode': 'exact' if exact else 'proportional',
                         'ref_composition': ['book', 'chapter'],
                         'source_url': 'https://www.gutenberg.org/ebooks/' +
                                       fname[2:-4]}],
            'license': 'Public domain: Bohn translations, 1850s. '
                       'Text from Project Gutenberg.',
            'attribution': 'C. D. Yonge (Bohn), via Project Gutenberg',
            'n_units_stored': len(ulist), 'units': ulist,
            'ref_to_unit': ref2u,
        }, open(os.path.join(args.out_dir, f'la__{tessname}.json'), 'w'),
            ensure_ascii=False)


if __name__ == '__main__':
    main()
