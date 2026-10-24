#!/usr/bin/env python3
"""Lysias, the speeches, from W. R. M. Lamb's Loeb of 1930 as distributed by Perseus.

Pipeline 1 of the README (Perseus TEI), done directly for one author. Perseus
holds Lamb's translation as one TEI file per speech
(canonical-greekLit/data/tlg0540/tlgNNN/tlg0540.tlgNNN.perseus-eng2.xml), with the
speech sections as `<div type="textpart" subtype="section" n="K">`. Our references
are speech.section ("lys. speeches 12.47"), so the alignment is one section to one
section with nothing to search for.

Which Perseus file is which speech is not assumed from its number. For every speech
the count of Perseus sections is compared with the count of our sections and printed,
and the name check and length correlation judge the file as a whole.

Date: Lamb's Loeb was first published in 1930, inside the project's cutoff (1930 or
earlier, which entered the US public domain on 1 January 2026).
"""
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_common as C

PERSEUS = os.environ.get('TESSERAE_PERSEUS_WORK',
                         os.path.expanduser('~/perseus_trans/work')) + '/canonical-greekLit/data/tlg0540'
NS = '{http://www.tei-c.org/ns/1.0}'


def text_of(el):
    parts = []

    def walk(e):
        tag = e.tag.replace(NS, '')
        if tag in ('note', 'milestone'):
            if e.tail:
                parts.append(e.tail)
            return
        if e.text:
            parts.append(e.text)
        for c in e:
            walk(c)
        if e.tail:
            parts.append(e.tail)

    if el.text:
        parts.append(el.text)
    for c in el:
        walk(c)
    return re.sub(r'\s+', ' ', ''.join(parts)).strip()


def speech_sections(n):
    p = f'{PERSEUS}/tlg{n:03d}/tlg0540.tlg{n:03d}.perseus-eng2.xml'
    if not os.path.exists(p):
        return None
    root = ET.parse(p).getroot()
    out = {}
    for d in root.iter(NS + 'div'):
        if d.get('subtype') == 'section' and d.get('n', '').isdigit():
            t = text_of(d)
            if t:
                out[int(d.get('n'))] = t
    return out


def main():
    tl = C.load_tess(os.path.join(C.TEXTS, 'grc', 'lysias.speeches.tess'))
    ours = {}
    for ref, _ in tl:
        m = re.search(r'(\d+)\.(\d+)\s*$', ref)
        if m:
            ours.setdefault(int(m.group(1)), {})[int(m.group(2))] = ref
    mapping = {}
    print('speech  our sections  Perseus sections  paired')
    for sp in sorted(ours):
        secs = speech_sections(sp)
        if not secs:
            print(f'{sp:6d}  {len(ours[sp]):13d}  -- no file')
            continue
        paired = 0
        for k, ref in ours[sp].items():
            if k in secs:
                mapping[ref] = secs[k]
                paired += 1
        print(f'{sp:6d}  {len(ours[sp]):13d}  {len(secs):16d}  {paired:6d}')
    source = {'translator': 'W. R. M. Lamb', 'year': 1930, 'place': 'London and Cambridge, MA',
              'publisher': 'William Heinemann / Harvard University Press',
              'title': 'Lysias (Loeb Classical Library 244)', 'license': 'public domain',
              'mode': 'section', 'ref_composition': ['speech', 'section'],
              'url': 'https://archive.org/details/lysiaslamb00lysiuoft',
              'source_url': 'https://github.com/PerseusDL/canonical-greekLit/tree/master/data/tlg0540',
              'cts_urn': 'urn:cts:greekLit:tlg0540.*.perseus-eng2'}
    row = C.finish('lysias.speeches', 'grc', tl, mapping, source,
                   'CC BY-SA 4.0 (Perseus Digital Library TEI); underlying translation is US public domain '
                   '(published 1930, inside the project cutoff)',
                   'Perseus Digital Library, Tufts University',
                   confidence='high')
    C.save_report('lysias', [row])


if __name__ == '__main__':
    main()
