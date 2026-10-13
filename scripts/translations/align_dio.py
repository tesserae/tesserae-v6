#!/usr/bin/env python3
"""Cassius Dio, Roman History 36 to 55: Earnest Cary's Loeb translation
(1914 to 1927) aligned to texts/grc/cassius_dio.roman_history.tess.

Source: Bill Thayer's LacusCurtius transcription of the Loeb volumes
(penelope.uchicago.edu/Thayer/E/Roman/Texts/Cassius_Dio/<book>*.html), one
page per book. The pages mark every chapter and section in the text
(`<A CLASS="chapter" NAME="18">`, `<A CLASS="sec" NAME="18.2">`), using the
Boissevain numbering that Perseus's Greek (Cary's Greek text) also uses, so
the alignment is by exact citation. Cary's English also carries fragments
that the Greek file does not (chapters 1a, 1b and the like, and book 36
chapters 1 to 17): their English is dropped, not guessed at. Footnotes,
Thayer's notes, page numbers and the page furniture are removed.

    align_dio.py HTML_DIR TESS OUT_DIR

The script reports which Greek references have no English and which English
sections have no Greek, and runs the proper-name and length checks the other
aligners use. Rights: Thayer's page states the Loeb volumes are now in the
public domain (earlier volumes lapsed, later ones not renewed).
"""
import json
import os
import re
import sys
from collections import OrderedDict

from lxml import html as LH

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V                       # noqa: E402
from align_perseus import length_correlation   # noqa: E402
from write_aligned import tess_refs, write_aligned   # noqa: E402

html_dir, tess_path, out_dir = sys.argv[1:4]


def book_sections(path, book):
    """-> OrderedDict 'book.chapter.section' -> English (digit chapters only)."""
    raw = open(path, encoding='utf-8').read()
    doc = LH.fromstring(raw)
    first = doc.xpath('//a[@class="chapter"]')
    assert first, f'{path}: no chapter markers'
    para = first[0]
    while para.tag != 'p':
        para = para.getparent()
    out = OrderedDict()
    chap = sec = None
    buf = []

    def flush():
        if chap is not None and sec is not None and buf:
            t = re.sub(r'\s+', ' ', ''.join(buf).replace('\xad', '')).strip()
            if t:
                key = f'{book}.{chap}.{sec}'
                out[key] = (out[key] + ' ' + t) if key in out else t
        buf.clear()

    def go(node):
        nonlocal chap, sec
        cls = node.get('class')
        if node.tag == 'a' and cls in ('chapter', 'sec'):
            flush()
            name = node.get('name', '')
            if cls == 'chapter':
                chap = name if name.isdigit() else None
                sec = '1' if chap else None
            else:
                m = re.fullmatch(r'(\d+)\.(\d+)', name)
                if m:
                    # a chapter whose own marker the page omits (47.43) is
                    # taken from its first section marker
                    chap, sec = m.group(1), m.group(2)
                else:
                    chap = sec = None
            return
        if node.tag == 'a' and cls in ('ref', 'note'):
            return
        if node.tag == 'span' and cls == 'pagenum':
            return
        if node.text:
            buf.append(node.text)
        for c in node:
            go(c)
            if c.tail:
                buf.append(c.tail)

    # the body runs from the first chapter marker to the first footnote
    # paragraph (one that opens with <a class="note">)
    for el in [para] + list(para.itersiblings()):
        if el.tag in ('hr', 'h2', 'table'):
            break
        if el.tag != 'p' or (el.get('class') or '') == 'ivy':
            continue
        if el.xpath('./a[@class="note"]'):
            break
        go(el)
        flush()
    return out


by_ref = OrderedDict()
for b in range(36, 56):
    secs = book_sections(os.path.join(html_dir, f'{b}.html'), b)
    print(f'book {b}: {len(secs)} English sections')
    by_ref.update(secs)

refs = tess_refs(tess_path)
tails = {r: r.split()[-1] for r in refs}
units, ref_to_unit, pairs = [], {}, []
src = {}
for line in open(tess_path, encoding='utf-8'):
    ref, text = line.rstrip('\n').split('\t', 1)
    src[ref[1:-1]] = text
missing = [r for r in refs if tails[r] not in by_ref]
extra = [k for k in by_ref if k not in set(tails.values())]
# A Greek section whose number Thayer's page does not mark (Cary ran two or
# three of Boissevain's sections together) shares the English of the nearest
# earlier section of the same chapter, whose text runs on through it. Book
# tables of contents (chapter 0) have no English and stay uncovered.
unit_of = {}
merged = []
for r in refs:
    t = tails[r]
    if t in by_ref:
        unit_of[t] = len(units)
        ref_to_unit[r] = len(units)
        units.append(by_ref[t])
        pairs.append((src[r], by_ref[t]))
    else:
        bk, ch, sc = t.split('.')
        prev = next((f'{bk}.{ch}.{k}' for k in range(int(sc) - 1, 0, -1)
                     if f'{bk}.{ch}.{k}' in unit_of), None)
        if prev is None and sc == '1' and ch != '0':
            # chapter opens with an unmarked first section (47.43.1): its
            # text is the tail of the section before the first marked one
            keys = list(by_ref)
            first = next((k for k in keys if k.startswith(f'{bk}.{ch}.')), None)
            if first and keys.index(first) > 0:
                prev = keys[keys.index(first) - 1]
        if ch != '0' and prev:
            ref_to_unit[r] = unit_of[prev]
            merged.append(r)
print(f'{len(merged)} sections share the English of the preceding section')
hit, n = V.score(pairs, 'grc')
corr = length_correlation(pairs)
print(f'refs {len(refs)} translated {len(ref_to_unit)} coverage {len(ref_to_unit)/len(refs):.4f}')
print(f'Greek refs with no English section of their own: {len(missing)} e.g. {missing[:8]}')
print(f'English sections without Greek: {len(extra)} (book 36 chapters 1 to 17 and book 55 from 9.5, which Perseus does not carry)')
print('uncovered:', [r.split()[-1] for r in refs if r not in ref_to_unit])
print(f'name check {hit} on {n}; length correlation {corr}')
if len(sys.argv) > 4 and sys.argv[4] == '--dry':
    sys.exit(0)
write_aligned(
    out_dir, 'grc', 'cassius_dio.roman_history', units, ref_to_unit,
    attribution='Earnest Cary (Loeb Classical Library, 1914 to 1927); '
                'transcription by Bill Thayer, LacusCurtius',
    license='Public domain in the United States (Loeb volumes of 1914 to 1927; '
            'copyright lapsed or was not renewed, per LacusCurtius).',
    sources=[{
        'translator': 'Earnest Cary', 'year': 1927,
        'publisher': 'Harvard University Press / William Heinemann',
        'title': "Dio's Roman History (Loeb Classical Library), vols. 3 to 6",
        'mode': 'exact', 'ref_composition': ['book', 'chapter', 'section'],
        'source_url': 'https://penelope.uchicago.edu/Thayer/E/Roman/Texts/'
                      'Cassius_Dio/home.html',
        'pd_reason': 'published 1914 to 1917 (vols. 3 to 6), US public domain',
        'short_attribution': 'E. Cary (1914-1917)'}],
    confidence='high' if (hit or 0) >= 0.70 else 'medium',
    approximate=False, tess_refs=refs,
    notes=f'{len(merged)} sections whose number Thayer does not mark share the English of the preceding section of the same chapter; the {sum(1 for r in refs if r not in ref_to_unit)} uncovered references are the book tables of contents.',
    name_check={'name_check_hit_rate': hit, 'name_check_n': n},
    verified_by='exact citation match; proper names; length correlation '
                f'{corr:.3f}' if corr is not None else 'exact citation match')
