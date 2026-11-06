#!/usr/bin/env python3
"""Florus, Epitome of Roman History: E. S. Forster's Loeb translation (1929)
aligned to texts/la/florus.epitome_bellorum_omnium_annorum at CHAPTER level.

Source: Bill Thayer's LacusCurtius transcription of the Loeb volume
(penelope.uchicago.edu/Thayer/E/Roman/Texts/Florus/Epitome/1A*.html to 2I*.html,
fetched at one request a second), where each chapter has an `<H3>` heading with its
roman numeral and a title. Our references are book.chapter.paragraph.sentence, and the
first two numbers are the book and the chapter (book 1 has 47 chapters, book 2 has
34), so every reference takes the English of its chapter. Thayer's footnote marks,
section and chapter numerals and his bracketed notes are removed.

Rights: published 1929 (US public domain). LacusCurtius states that the Loeb Florus
is in the public domain.

    align_florus_forster.py SRC_DIR OUT_DIR [--dry]
SRC_DIR holds the fetched pages (1A_.html ... 2I_.html).
"""
import glob
import os
import re
import sys

from lxml import html as LH

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, clean, roman_to_int   # noqa: E402

src_dir, out_dir = sys.argv[1:3]
dry = '--dry' in sys.argv
english = {}
for path in sorted(glob.glob(os.path.join(src_dir, '[12][A-Z]_.html'))):
    book = int(os.path.basename(path)[0])
    doc = LH.fromstring(open(path, encoding='utf-8', errors='replace').read())
    for bad in doc.xpath('//a[@class="comment"]|//a[@class="chapter"]|//a[@class="sec"]|//script|//span[@class="smallest"]'):
        bad.drop_tree()
    cur, buf = None, []
    for el in doc.iter():
        if el.tag == 'h3':
            m = re.match(r'\s*(?:p\d+\s+)?([IVXL]+)\.\s', el.text_content())
            if m:
                if cur:
                    english[cur] = clean(' '.join(buf))
                cur, buf = (book, roman_to_int(m.group(1))), []
        elif el.tag == 'p' and cur and (el.get('class') or '') == 'justify':
            buf.append(el.text_content())
    if cur:
        english[cur] = clean(' '.join(buf))
refs, src, _ = load_work('la', 'florus.epitome_bellorum_omnium_annorum')
units, idx, ref_to_unit = [], {}, {}
for r in refs:
    b, c = (int(x) for x in re.match(r'(\d+)\.(\d+)', tail(r)).groups())
    t = english.get((b, c))
    if not t:
        continue
    if (b, c) not in idx:
        idx[(b, c)] = len(units)
        units.append(t)
    ref_to_unit[r] = idx[(b, c)]
ours = {tuple(int(x) for x in re.match(r'(\d+)\.(\d+)', tail(r)).groups()) for r in refs}
print(f'English chapters {len(english)}, our chapters {len(ours)}, ours without English {sorted(ours - set(english))[:10]}, English without ours {sorted(set(english) - ours)[:10]}')
finish('la', 'florus.epitome_bellorum_omnium_annorum', units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='chapter',
       attribution='E. S. Forster, Florus: Epitome of Roman History, Loeb Classical Library (1929); transcription by Bill Thayer, LacusCurtius',
       license='Public domain in the United States (published 1929)',
       sources=[{'translator': 'Edward Seymour Forster', 'year': 1929, 'place': 'London and New York',
                 'publisher': 'William Heinemann / G. P. Putnam\'s Sons',
                 'title': 'Florus: Epitome of Roman History (Loeb Classical Library)',
                 'mode': 'chapter', 'ref_composition': ['book', 'chapter'],
                 'url': 'https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Florus/Epitome/home.html',
                 'pd_reason': 'published 1929'}],
       notes='Chapter-level units: every Latin sentence of a chapter shows the English of its whole chapter.')
