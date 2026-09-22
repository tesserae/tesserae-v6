#!/usr/bin/env python3
"""Arrian's Anabasis from the Perseus canonical TEI into a .tess file.

Source: PerseusDL/canonical-greekLit, tlg0074.tlg001.perseus-grc2.xml, the
text of A. G. Roos (Teubner 1907), CC BY-SA 4.0. That is the same edition
our file already claims, but as the maintained canonical XML rather than a
scrape of the reading interface.

Citation: our corpus writes <arr. an. BOOK.CHAPTER.SECTION>, and Perseus
numbers each book's preface as chapter "pr", which our file writes as
chapter 0. That mapping is kept so existing references, links and the
quotation tables still resolve.
"""
import html
import re
import sys
import unicodedata

import argparse

ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('source', help='tlg0074.tlg001.perseus-grc2.xml')
ap.add_argument('out', help='the whole-work .tess file to write')
ap.add_argument('--parts-dir', help='also write one file per book into this directory')
args = ap.parse_args()
SRC, OUT = args.source, args.out
xml = open(SRC, encoding='utf-8').read()
body = xml[xml.index('<text'):]

# Drop apparatus, notes and page/line breaks: they are editorial furniture and
# the stray digits inside the Greek of our current book files come from
# exactly this kind of markup being flattened rather than removed.
body = re.sub(r'<note\b.*?</note>', ' ', body, flags=re.S)
body = re.sub(r'<app\b.*?</app>', ' ', body, flags=re.S)
body = re.sub(r'<(pb|lb|cb|milestone|gap)\b[^>]*/?>', ' ', body)

DIV = re.compile(r'<div\b[^>]*subtype="(?P<sub>book|chapter|section)"[^>]*\sn="(?P<n>[^"]+)"[^>]*>')
TAG = re.compile(r'<[^>]+>')

lines, book, chapter = [], None, None
pos = 0
for m in DIV.finditer(body):
    sub, n = m.group('sub'), m.group('n')
    if sub == 'book':
        book, chapter = n, None
    elif sub == 'chapter':
        chapter = '0' if n == 'pr' else n
    else:
        # a section: take everything up to the next div of any kind
        nxt = DIV.search(body, m.end())
        chunk = body[m.end(): nxt.start() if nxt else len(body)]
        chunk = chunk.split('</div>')[0]
        text = html.unescape(TAG.sub(' ', chunk))
        text = unicodedata.normalize('NFC', re.sub(r'\s+', ' ', text)).strip()
        # Match the punctuation the rest of the Greek corpus uses. Every other
        # Greek text here came through the older Perseus reading interface,
        # which renders the elision mark as a plain apostrophe and the raised
        # stop as a colon; the canonical XML writes U+02BC and U+00B7. The
        # lemma caches and the index were built on the first convention, and
        # an elision mark sits inside a word, so this is not only tidiness.
        text = (text.replace('\u02bc', "'").replace('\u2019', "'")
                    .replace('\u1fbd', "'").replace('\u00b7', ':'))
        if text and book and chapter is not None:
            lines.append((f'arr. an. {book}.{chapter}.{n}', text))

with open(OUT, 'w', encoding='utf-8', newline='') as fh:
    for ref, text in lines:
        fh.write(f'<{ref}>\t{text}\n')
print(f'{len(lines)} lines written to {OUT}')

if args.parts_dir:
    import collections
    import os
    by_book = collections.OrderedDict()
    for ref, text in lines:
        book = ref.split()[2].split('.')[0]
        by_book.setdefault(book, []).append((ref, text))
    base = os.path.basename(OUT)[:-5]
    for book, rows in by_book.items():
        path = os.path.join(args.parts_dir, f'{base}.part.{book}.tess')
        with open(path, 'w', encoding='utf-8', newline='') as fh:
            for ref, text in rows:
                fh.write(f'<{ref}>\t{text}\n')
        print(f'  book {book}: {len(rows)} lines -> {os.path.basename(path)}')
