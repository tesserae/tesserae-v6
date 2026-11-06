#!/usr/bin/env python3
"""Aratus, Callimachus' Hymns, Lycophron, Bion's Lament and Theocritus' Idylls,
from the Loeb translations as transcribed by the Theoi Classical Texts Library.

Translators and Loeb volumes (all published before 1931, US public domain):
- Aratus, Phaenomena: G. R. Mair, Loeb 1921 (with Callimachus and Lycophron)
- Callimachus, Hymns: A. W. Mair, Loeb 1921
- Lycophron, Alexandra: A. W. Mair, Loeb 1921
- Theocritus and Bion: J. M. Edmonds, Loeb 1912 (The Greek Bucolic Poets)

Theoi prints each paragraph with a bracketed number, "[19] I have yet...", and
for these five works that number is the GREEK line number. This is not assumed:
the largest marker in each section is compared with our own line count and
printed, and a section whose last marker falls far short is flagged (the same
trap README pipeline 7 describes for Way's Quintus, where the markers counted
the translator's own English lines).

A paragraph covers the Greek lines from its marker to the line before the next
marker. A marker out of order (a typing slip on Theoi's side) is dropped and
counted, never guessed at. Sources are cached in the staging folder.
"""
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import loeb_common as C

ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50}


def roman(s):
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN[ch]
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total


def sections(path, heading_re):
    """[(section id, [(marker, text)])] in page order."""
    raw = open(path, encoding='utf-8', errors='replace').read()
    raw = raw[raw.find('<body'):]
    raw = re.sub(r'<script.*?</script>', '', raw, flags=re.S)
    raw = re.sub(r'<sup>.*?</sup>', '', raw, flags=re.S)
    out, cur, dropped = [], None, 0
    last = 0
    for m in re.finditer(r'<(p|h\d)[^>]*>(.*?)</\1>', raw, flags=re.S):
        txt = html.unescape(re.sub(r'<[^>]+>', ' ', m.group(2)))
        txt = re.sub(r'\s+', ' ', txt).strip()
        if not txt:
            continue
        h = heading_re.match(txt)
        if h:
            cur = [h.group(1), []]
            out.append(cur)
            last = 0
            rest = txt[h.end():].strip()
            mm = re.match(r'\[(\d+)\]\s*(.*)$', rest)
            if mm:
                cur[1].append((int(mm.group(1)), mm.group(2)))
                last = int(mm.group(1))
            continue
        if cur is None:
            continue
        mm = re.match(r'(?:[A-Z][A-Z .\'-]{2,40}\s)?\[(\d+)\]\s*(.*)$', txt)
        if mm:
            n = int(mm.group(1))
            if n <= last:
                dropped += 1
                continue
            cur[1].append((n, mm.group(2)))
            last = n
        elif cur[1] and not re.match(r'^\d+\.', txt) and len(txt) > 40 and 'Theoi' not in txt:
            # an unmarked continuation of the paragraph before it
            cur[1][-1] = (cur[1][-1][0], cur[1][-1][1] + ' ' + txt)
    if dropped:
        print(f'    {os.path.basename(path)}: dropped {dropped} out-of-order marker(s)')
    return out


def spans(pars, last_line):
    out = []
    for i, (n, text) in enumerate(pars):
        end = (pars[i + 1][0] - 1) if i + 1 < len(pars) else last_line
        if end >= n:
            out.append((n, end, text))
    return out


def tess_index(path, key):
    """{(section, line): ref} using key(ref) -> (section, line) or None."""
    idx = {}
    tl = C.load_tess(path)
    for ref, _ in tl:
        k = key(ref)
        if k and k not in idx:
            idx[k] = ref
    return tl, idx


def last_line(idx, sec):
    return max((ln for (s, ln) in idx if s == sec), default=0)


def last_two(ref):
    m = re.search(r'(\d+)\.(\d+)\s*$', ref)
    return (int(m.group(1)), int(m.group(2))) if m else None


def single(ref):
    m = re.search(r'(\d+)\s*$', ref)
    return (1, int(m.group(1))) if m else None


MAIR_A = {'year': 1921, 'place': 'London and New York', 'publisher': "William Heinemann / G. P. Putnam's Sons",
          'license': 'public domain', 'mode': 'paragraph', 'ref_composition': ['line range']}
EDMONDS = {'translator': 'J. M. Edmonds', 'year': 1912, 'place': 'London and New York',
           'publisher': "William Heinemann / G. P. Putnam's Sons",
           'title': 'The Greek Bucolic Poets (Loeb Classical Library 28)',
           'license': 'public domain', 'mode': 'paragraph', 'ref_composition': ['idyll', 'line range']}


def src(base, translator, title, url):
    d = dict(base)
    d.update({'translator': translator, 'title': title, 'url': url, 'source_url': url})
    return d


TARGETS = [
    dict(work='aratus.phaenomena', files=['theoi_AratusPhaenomena.html'],
         heading=re.compile(r'(PHAENOMENA), TRANSLATED BY G\. R\. MAIR'), secid=lambda h: 1, key=single,
         source=src(MAIR_A, 'G. R. Mair', 'Callimachus and Lycophron, with Aratus (Loeb Classical Library 129)',
                    'https://www.theoi.com/Text/AratusPhaenomena.html'),
         credit='Theoi Classical Texts Library (theoi.com)'),
    dict(work='callimachus.hymns', files=['theoi_CallimachusHymns1.html', 'theoi_CallimachusHymns2.html'],
         heading=re.compile(r'HYMN ([IVX]+)\.'), secid=roman, key=last_two,
         source=src(MAIR_A, 'A. W. Mair', 'Callimachus and Lycophron, with Aratus (Loeb Classical Library 129)',
                    'https://www.theoi.com/Text/CallimachusHymns1.html'),
         credit='Theoi Classical Texts Library (theoi.com)'),
    dict(work='lycophron.alexandra', files=['theoi_LycophronAlexandra.html'],
         heading=re.compile(r'(ALEXANDRA), TRANSLATED BY A\. W\. MAIR'), secid=lambda h: 1, key=single,
         source=src(MAIR_A, 'A. W. Mair', 'Callimachus and Lycophron, with Aratus (Loeb Classical Library 129)',
                    'https://www.theoi.com/Text/LycophronAlexandra.html'),
         credit='Theoi Classical Texts Library (theoi.com)'),
    dict(work='bion_of_phlossa.epitaphius', files=['theoi_Bion.html'],
         heading=re.compile(r'(I)\. THE LAMENT FOR ADONIS'),
         secid=lambda h: 1, key=single,
         source=src(EDMONDS, 'J. M. Edmonds', 'The Greek Bucolic Poets (Loeb Classical Library 28)',
                    'https://www.theoi.com/Text/Bion.html'),
         credit='Theoi Classical Texts Library (theoi.com)'),
    dict(work='theocritus.idylls', files=['theoi_TheocritusIdylls%d.html' % i for i in range(1, 6)],
         heading=re.compile(r'IDYLL ([IVXL]+)\.[^\[]{0,60}'), secid=roman, key=last_two,
         source=src(EDMONDS, 'J. M. Edmonds', 'The Greek Bucolic Poets (Loeb Classical Library 28)',
                    'https://www.theoi.com/Text/TheocritusIdylls1.html'),
         credit='Theoi Classical Texts Library (theoi.com)'),
]


def run(t):
    path = os.path.join(C.TEXTS, 'grc', t['work'] + '.tess')
    tl, idx = tess_index(path, t['key'])
    mapping = {}
    for fn in t['files']:
        for h, pars in sections(os.path.join(C.SRC, fn), t['heading']):
            sec = t['secid'](h)
            if not pars:
                continue
            ll = last_line(idx, sec)
            if ll == 0:
                print(f'    section {h}: not in our file, skipped')
                continue
            top = pars[-1][0]
            if top > ll:
                # A marker beyond our last line means the two numberings differ
                # for this poem. Pairing by number would drift, so it is skipped
                # and reported (the spec's rule for disagreeing numberings).
                print(f'    {t["work"]} section {sec}: SKIPPED, markers run to {top} but our text has '
                      f'{ll} lines (numberings differ)')
                continue
            note = '' if top >= 0.9 * ll else '   <-- last marker is far short of our line count'
            print(f'    {t["work"]} section {sec}: markers {len(pars)}, last {top}, our lines {ll}{note}')
            for a, b, text in spans(pars, ll):
                for ln in range(a, b + 1):
                    ref = idx.get((sec, ln))
                    if ref and ref not in mapping:
                        mapping[ref] = text
    return C.finish(t['work'], 'grc', tl, mapping, t['source'],
                    'Public domain in the United States: published %d. Text from the Theoi Classical '
                    'Texts Library transcription.' % t['source']['year'], t['credit'], confidence='high')


def main():
    only = sys.argv[1:]
    rows = []
    for t in TARGETS:
        if only and t['work'] not in only:
            continue
        rows.append(run(t))
    C.save_report('theoi_exact', rows)


if __name__ == '__main__':
    main()
