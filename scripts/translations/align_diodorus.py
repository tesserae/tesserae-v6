#!/usr/bin/env python3
"""Diodorus Siculus, Bibliotheca Historica, books 1 to 5 and 18 to 20: the Loeb
translation (Oldfather, vols. I to III; Geer, vols. IX and X) aligned to
texts/grc/diodorus_siculus.bibliotheca_historica.tess.

Source: Bill Thayer's LacusCurtius transcription of the Loeb volumes
(penelope.uchicago.edu/Thayer/E/Roman/Texts/Diodorus_Siculus/<book><letter>*.html),
each book split over several pages (1A to 1D, 2A, 2B, and so on). The pages
mark every chapter and section in the text (`<A CLASS="chapter" NAME="18">`,
`<A CLASS="sec" NAME="18.2">`), numbered chapter.section within the book, as
Perseus's Teubner Greek is, so the alignment is by exact citation: the book
comes from the page name. Footnotes, Thayer's notes, page numbers and the page
furniture are removed. Where the Greek has a section the English runs
together with the one before, the Greek section shares that English; where
the English has fragments with no Greek (and the reverse) the script reports
them rather than guessing.

    align_diodorus.py HTML_DIR TESS OUT_DIR [--dry]

Rights: Thayer's home page for Diodorus states that Loeb volumes I to XI are
in the public domain because the copyright was not renewed (volume XII is not).
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
PAGES = {1: "ABCD", 2: "AB", 3: "ABCDE", 4: "ABCD", 5: "ABCD", 18: "ABC", 19: "ABCDEF", 20: "ABCDE"}


def book_sections(path, book):
    """-> OrderedDict 'book.chapter.section' -> English (digit chapters only)."""
    raw = open(path, encoding='utf-8').read()
    doc = LH.fromstring(raw)
    # the body starts at the first chapter marker or the first plain
    # chapter.section anchor (book 1 opens with <A NAME="1.1"> and no
    # chapter marker)
    first = doc.xpath('//a[@class="chapter" or (not(@class) and @name="1.1")]')
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
        plain = (node.tag == 'a' and not cls
                 and re.fullmatch(r'\d+\.\d+', node.get('name', '')))
        if node.tag == 'a' and (cls in ('chapter', 'sec') or plain):
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
for b, letters in PAGES.items():
    n_b = 0
    for L in letters:
        secs = book_sections(os.path.join(html_dir, f'{b}{L}.html'), b)
        n_b += len(secs)
        for k, v in secs.items():
            by_ref[k] = (by_ref[k] + ' ' + v) if k in by_ref else v
    print(f'book {b}: {n_b} English sections')

refs = tess_refs(tess_path)
tails = {r: r.split()[-1] for r in refs}
units, ref_to_unit, pairs = [], {}, []
src = {}
for line in open(tess_path, encoding='utf-8'):
    ref, text = line.rstrip('\n').split('\t', 1)
    src[ref[1:-1]] = text
missing = [r for r in refs if tails[r] not in by_ref]
extra = [k for k in by_ref if k not in set(tails.values())]
# A Greek section whose number Thayer's page does not mark (the translator ran two or
# more of the Greek editor's sections together) shares the English of the nearest
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
print(f'English sections without Greek: {len(extra)} ')
print('uncovered:', [r.split()[-1] for r in refs if r not in ref_to_unit])
print(f'name check {hit} on {n}; length correlation {corr}')
if len(sys.argv) > 4 and sys.argv[4] == '--dry':
    sys.exit(0)
write_aligned(
    out_dir, 'grc', 'diodorus_siculus.bibliotheca_historica', units, ref_to_unit,
    attribution='C. H. Oldfather (vols. I to III) and Russel M. Geer (vols. IX and X), '
                'Loeb Classical Library; transcription by Bill Thayer, LacusCurtius',
    license='Public domain in the United States: the Loeb volumes (1933 to 1954) '
            'were not renewed, per LacusCurtius.',
    sources=[{
        'translator': 'C. H. Oldfather (books 1 to 5), Russel M. Geer (books 18 to 20)',
        'year': 1954,
        'publisher': 'Harvard University Press / William Heinemann',
        'title': 'Diodorus of Sicily (Loeb Classical Library), vols. I to III, IX and X',
        'mode': 'exact', 'ref_composition': ['book', 'chapter', 'section'],
        'source_url': 'https://penelope.uchicago.edu/Thayer/E/Roman/Texts/'
                      'Diodorus_Siculus/home.html',
        'pd_reason': 'copyright of Loeb vols. I, II, III, IX and X not renewed '
                     '(LacusCurtius, Diodorus Siculus home page)',
        'short_attribution': 'C. H. Oldfather (1933-1939), R. M. Geer (1947-1954)'}],
    confidence='high' if (hit or 0) >= 0.70 else 'medium',
    approximate=False, tess_refs=refs,
    notes=f'{len(merged)} sections whose number Thayer does not mark share the English of the preceding section of the same chapter; the {sum(1 for r in refs if r not in ref_to_unit)} uncovered references are the book tables of contents.',
    name_check={'name_check_hit_rate': hit, 'name_check_n': n},
    verified_by='exact citation match; proper names; length correlation '
                f'{corr:.3f}' if corr is not None else 'exact citation match')
