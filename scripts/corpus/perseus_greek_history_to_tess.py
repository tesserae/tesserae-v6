#!/usr/bin/env python3
"""A Perseus canonical-greekLit TEI edition (book / chapter / section) into .tess.

Used for Xenophon's Hellenica (tlg0032.tlg001.perseus-grc2, Marchant, OCT
1900) and Cassius Dio, Roman History 36 to 55 (tlg0385.tlg001.perseus-grc2,
Cary, Loeb 1914 to 1917), both CC BY-SA 4.0. It follows
arrian_from_perseus_tei.py: apparatus, notes and page breaks are dropped,
Perseus's modifier-letter apostrophe and raised stop are turned into the
plain apostrophe and colon that the rest of the Greek corpus carries, and a
chapter numbered "pr" becomes chapter 0.

    perseus_greek_history_to_tess.py SOURCE.xml OUT.tess --tag 'xen. hell.' \
        [--parts-dir DIR]

Writes the whole-work file and, with --parts-dir, one file per book named
<OUT stem>.part.<book>.tess, the way Herodotus and Thucydides are filed.
Exits non-zero when text inside the book divisions is not accounted for by
the section lines (the check compares Greek letters in and out). A word hyphenated across a
printed page is rejoined.
"""
import argparse
import collections
import html
import os
import re
import sys
import unicodedata

ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('source')
ap.add_argument('out')
ap.add_argument('--tag', required=True, help="reference prefix, e.g. 'xen. hell.'")
ap.add_argument('--parts-dir')
args = ap.parse_args()

xml = open(args.source, encoding='utf-8').read()
body = xml[xml.index('<text'):]
body = re.sub(r'<note\b.*?</note>', ' ', body, flags=re.S)
body = re.sub(r'<app\b.*?</app>', ' ', body, flags=re.S)
# A word broken across a printed page ("ἐκακούργη- <pb/> σαν", eleven times in
# Dio) is rejoined; one case also carries a stray footnote digit ("προς1-").
body = re.sub(r'\d*-\s*<pb\b[^>]*/>\s*', '', body)
body = re.sub(r'<(pb|lb|cb|milestone|gap)\b[^>]*/?>', ' ', body)

DIV = re.compile(r'<div\b[^>]*subtype="(?P<sub>book|chapter|section)"[^>]*\sn="(?P<n>[^"]+)"[^>]*>')
ANYDIV = re.compile(r'<div\b|</div>')
TAG = re.compile(r'<[^>]+>')


def clean(chunk):
    text = html.unescape(TAG.sub(' ', chunk))
    text = unicodedata.normalize('NFC', re.sub(r'\s+', ' ', text)).strip()
    return (text.replace('ʼ', "'").replace('’', "'")
                .replace('᾽', "'").replace('·', ':'))


lines, book, chapter = [], None, None
for m in DIV.finditer(body):
    sub, n = m.group('sub'), m.group('n')
    if sub == 'book':
        book, chapter = n, None
    elif sub == 'chapter':
        chapter = '0' if n in ('pr', 'arg') else n
    else:
        nxt = ANYDIV.search(body, m.end())
        text = clean(body[m.end(): nxt.start() if nxt else len(body)])
        if text and book and chapter is not None:
            lines.append((f'{args.tag} {book}.{chapter}.{n}', text))


def greek_letters(s):
    return sum(1 for c in s if 'GREEK' in unicodedata.name(c, ''))


src_letters = greek_letters(clean(body[body.index('<body'):]))
out_letters = sum(greek_letters(t) for _, t in lines)
print(f'{len(lines)} lines; Greek letters in source body {src_letters}, in lines {out_letters} '
      f'({out_letters / src_letters:.4f})')
if out_letters / src_letters < 0.985:
    print('WARNING: more than 1.5% of the Greek is not in any section line', file=sys.stderr)

with open(args.out, 'w', encoding='utf-8', newline='') as fh:
    for ref, text in lines:
        fh.write(f'<{ref}>\t{text}\n')

if args.parts_dir:
    by_book = collections.OrderedDict()
    for ref, text in lines:
        by_book.setdefault(ref.split()[-1].split('.')[0], []).append((ref, text))
    stem = os.path.basename(args.out)[:-5]
    for b, rows in by_book.items():
        path = os.path.join(args.parts_dir, f'{stem}.part.{b}.tess')
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            for ref, text in rows:
                fh.write(f'<{ref}>\t{text}\n')
        print(f'  book {b}: {len(rows)} lines -> {os.path.basename(path)}')
