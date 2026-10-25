#!/usr/bin/env python3
"""Church histories of the Greek tranche of 2026-10-24: the Nicene and
Post-Nicene Fathers translations (series 2, 1890) aligned by book and chapter.

    Socrates Scholasticus  NPNF 2.2  A. C. Zenos, 1890
    Sozomen                NPNF 2.2  Chester D. Hartranft, 1890
    Theodoret              NPNF 2.3  Blomfield Jackson, 1892

Source: the Christian Classics Ethereal Library's ThML files
(ccel.org/ccel/schaff/npnf202.xml, npnf203.xml). Each book is a div2 titled
"Book N" and each chapter a div3 whose first paragraph reads "Chapter N.-
title", so the English is keyed by book and chapter number as printed. The
Greek files are cited book.chapter (Socrates) or book.chapter.section (Sozomen,
Theodoret), so a Greek line takes the English of its chapter, and the sections
of a chapter share one unit. Footnotes are dropped.

    align_ccel_histories.py WORK_STEM THML TESS OUT_DIR [--dry]
"""
import os
import re
import sys

from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V                       # noqa: E402
from align_perseus import length_correlation   # noqa: E402
from write_aligned import tess_refs, write_aligned   # noqa: E402

INFO = {
    'socrates_scholasticus.historia_ecclesiastica': dict(
        match='Socrates Scholasticus', translator='A. C. Zenos', year=1890,
        title='The Ecclesiastical History of Socrates Scholasticus (Nicene and Post-Nicene Fathers, series 2, vol. 2)',
        url='https://ccel.org/ccel/schaff/npnf202.html', short='A. C. Zenos (1890)'),
    'sozomen.historia_ecclesiastica': dict(
        match='Sozomen', translator='Chester D. Hartranft', year=1890,
        title='The Ecclesiastical History of Sozomen (Nicene and Post-Nicene Fathers, series 2, vol. 2)',
        url='https://ccel.org/ccel/schaff/npnf202.html', short='C. D. Hartranft (1890)'),
    'theodoret.historia_ecclesiastica': dict(
        match='Ecclesiastical History, Dialogues', translator='Blomfield Jackson', year=1892,
        title='The Ecclesiastical History of Theodoret (Nicene and Post-Nicene Fathers, series 2, vol. 3)',
        url='https://ccel.org/ccel/schaff/npnf203.html', short='B. Jackson (1892)'),
}
ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}


def roman(s):
    s = s.upper()
    if not re.fullmatch(r'[IVXLC]+', s):
        return None
    total = 0
    for i, c in enumerate(s):
        v = ROMAN[c]
        total += -v if i + 1 < len(s) and ROMAN[s[i + 1]] > v else v
    return total


def text_of(el):
    out = []

    def go(e):
        if e.tag == 'note':
            return
        if e.text:
            out.append(e.text)
        for c in e:
            go(c)
            if c.tail:
                out.append(c.tail)
    go(el)
    return re.sub(r'\s+', ' ', ''.join(out)).strip()


def extract(path, match):
    root = etree.parse(path, etree.XMLParser(recover=True, huge_tree=True, load_dtd=False, resolve_entities=False)).getroot()
    d1 = next(d for d in root.iter('div1') if match in (d.get('title') or ''))
    out = {}
    # a book is a div2 titled "Book N" with chapters as div3 (Socrates, Sozomen),
    # or a div3 titled "Book N" with chapters as div4 (Theodoret)
    books = [(d, 'div3') for d in d1.findall('div2')] + [(d, 'div4') for d2 in d1.findall('div2') for d in d2.findall('div3')]
    for book_el, child in books:
        m = re.match(r'Book ([IVX]+)', book_el.get('title') or '')
        if not m or not book_el.findall(child):
            continue
        book = roman(m.group(1))
        order = 0
        for d3 in book_el.findall(child):
            order += 1
            t = text_of(d3)
            h = re.match(r'Chapter ([IVXLC]+|\d+)\s*\.?\s*[—-]?\s*', t)
            chap = (roman(h.group(1)) if not h.group(1).isdigit() else int(h.group(1))) if h else order
            body = t[h.end():] if h else t
            out[f'{book}.{chap}'] = (out.get(f'{book}.{chap}', '') + ' ' + body).strip()
    return out


def main():
    stem, thml, tess_path, out_dir = sys.argv[1:5]
    info = INFO[stem]
    by_ch = extract(thml, info['match'])
    src = {}
    for line in open(tess_path, encoding='utf-8'):
        ref, text = line.rstrip('\n').split('\t', 1)
        src[ref[1:-1]] = text
    refs = tess_refs(tess_path)
    units, ref_to_unit, unit_of, missing = [], {}, {}, []
    chap_greek = {}
    for r in refs:
        parts = r.split()[-1].split('.')
        key = '.'.join(parts[:2])
        if len(parts) < 2 or key not in by_ch:
            missing.append(r)
            continue
        if key not in unit_of:
            unit_of[key] = len(units)
            units.append(by_ch[key])
        ref_to_unit[r] = unit_of[key]
        chap_greek.setdefault(key, []).append(src[r])
    # length check per chapter: all Greek of the chapter against its English
    pairs = [(' '.join(g), by_ch[k]) for k, g in chap_greek.items()]
    hit, n = V.score(pairs, 'grc')
    corr = length_correlation(pairs)
    cov = len(ref_to_unit) / len(refs)
    extra = [k for k in by_ch if k not in chap_greek]
    print(f'{stem}: refs {len(refs)} translated {len(ref_to_unit)} ({cov:.4f}); English chapters {len(by_ch)}, with Greek {len(chap_greek)}')
    print(f'  Greek refs with no English {len(missing)} e.g. {[m.split()[-1] for m in missing[:8]]}')
    print(f'  English chapters with no Greek {len(extra)} e.g. {extra[:8]}')
    print(f'  name check {hit} on {n}; length correlation (per chapter) {corr}')
    if '--dry' in sys.argv:
        return
    if cov < 0.9:
        print('  REFUSE: coverage under 90 percent')
        return
    path = write_aligned(
        out_dir, 'grc', stem, units, ref_to_unit,
        attribution=f"{info['translator']} (Nicene and Post-Nicene Fathers, series 2); Christian Classics Ethereal Library",
        license='Public domain (published 1890 to 1892).',
        sources=[{'translator': info['translator'], 'year': info['year'], 'publisher': 'Christian Literature Publishing Co., Buffalo / Parker, Oxford',
                  'title': info['title'], 'mode': 'chapter', 'ref_composition': ['book', 'chapter'],
                  'source_url': info['url'], 'pd_reason': f"published {info['year']}, public domain",
                  'short_attribution': info['short']}],
        confidence='high' if (corr or 0) >= 0.5 else 'medium', approximate=False, tess_refs=refs,
        notes='Aligned by book and chapter as printed; the sections of a chapter share one English unit. '
              f'{len(missing)} Greek lines (prefaces and chapter lists) have no English.',
        name_check={'name_check_hit_rate': hit, 'name_check_n': n},
        verified_by='book and chapter number; proper names; length correlation per chapter '
                    f'{corr:.3f}' if corr is not None else 'book and chapter number')
    print('  wrote', path)


if __name__ == '__main__':
    main()
