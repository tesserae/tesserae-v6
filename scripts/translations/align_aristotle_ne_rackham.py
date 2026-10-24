#!/usr/bin/env python3
"""Aristotle, Nicomachean Ethics: H. Rackham's Loeb translation (1926) aligned to
texts/grc/aristotle.nicomachean_ethics by Bekker position.

Our references are Bekker page, column and line (`1094a.5`, one every five lines).
Perseus's TEI of Rackham carries the Bekker line numbers as `line` anchors on about
a fifth of its paragraphs but never the page. The page is rebuilt by walking the
markers in order: a line number lower than the one before opens the next column
(a to b, then the next page). The rebuilt positions are checked against the
printed Bekker start of every book (I 1094a1, II 1103a14, III 1109b30, IV 1119b22,
V 1129a3, VI 1138b18, VII 1145a15, VIII 1155a3, IX 1163b32, X 1172a19) and the end
(1181b20); all eleven agree, so the script refuses to write if any does not.

Each unit is the English from one marker's paragraph through the paragraph of the
next marker (about twenty Bekker lines, so a paragraph shared with the next unit
appears in both), and each of our references takes the unit whose marker is the
last at or before its position.

    align_aristotle_ne_rackham.py OUT_DIR [--dry]
"""
import bisect
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work, tail, finish, clean, perseus_find   # noqa: E402

out_dir = sys.argv[1]
dry = '--dry' in sys.argv
recs = [r for r in perseus_find('Aristotle', 'Rackham', title_eq='Nicomachean Ethics')]
assert len(recs) == 1 and recs[0]['meta']['year'] <= 1930, len(recs)
meta = recs[0]['meta']
chunks = recs[0]['chunks']
page, col, last = 1094, 0, 0
markers = []                       # (position tuple, index of chunk)
book_first = {}
for i, c in enumerate(chunks):
    a = c['anchors']
    if 'line' not in a:
        continue
    L = int(a['line'])
    if L < last:
        if col == 0:
            col = 1
        else:
            col, page = 0, page + 1
    last = L
    pos = (page, col, L)
    markers.append((pos, i))
    book_first.setdefault(a['book'], pos)
KNOWN = {'1': (1094, 0, 1), '2': (1103, 0, 14), '3': (1109, 1, 30), '4': (1119, 1, 22), '5': (1129, 0, 3),
         '6': (1138, 1, 18), '7': (1145, 0, 15), '8': (1155, 0, 3), '9': (1163, 1, 32), '10': (1172, 0, 19)}
bad = {b: (book_first.get(b), k) for b, k in KNOWN.items() if book_first.get(b) != k}
end_ok = markers[-1][0] == (1181, 1, 20)
print(f'{len(markers)} Bekker markers; book starts agreeing {len(KNOWN) - len(bad)} of {len(KNOWN)}; end 1181b20 {"agrees" if end_ok else "DISAGREES"}')
if bad or not end_ok:
    sys.exit(f'refusing to write: rebuilt Bekker positions disagree with print: {bad}')

units, ref_to_unit = [], {}
for k, (pos, i) in enumerate(markers):
    j = markers[k + 1][1] if k + 1 < len(markers) else len(chunks) - 1
    units.append(clean(' '.join(c['text'] for c in chunks[i:j + 1])))
positions = [p for p, _ in markers]
refs, src, _ = load_work('grc', 'aristotle.nicomachean_ethics')
for r in refs:
    m = re.fullmatch(r'(\d+)([ab])\.(\d+)', tail(r))
    if not m:
        continue
    p = (int(m.group(1)), 0 if m.group(2) == 'a' else 1, int(m.group(3)))
    k = bisect.bisect_right(positions, p) - 1
    if k >= 0:
        ref_to_unit[r] = k
finish('grc', 'aristotle.nicomachean_ethics', units, ref_to_unit, refs, src, out_dir=out_dir, dry=dry, mode='bekker',
       attribution=f"{meta['translator']}, Aristotle: Nicomachean Ethics, Loeb Classical Library ({meta['year']}); Perseus Digital Library, Tufts University (TEI markup, CC BY-SA 4.0)",
       license='CC BY-SA 4.0 (Perseus Digital Library TEI); underlying translation is US public domain (published before 1931)',
       sources=[{'translator': meta['translator'], 'year': meta['year'], 'place': meta.get('pub_place'),
                 'publisher': meta.get('publisher'), 'title': meta.get('title'), 'mode': 'bekker',
                 'ref_composition': ['bekker page', 'column', 'line'], 'cts_urn': meta.get('cts_urn'),
                 'pd_reason': f"published {meta['year']}, US public domain"}],
       notes='Units run from one Bekker line marker of the English to the next (about twenty lines); a paragraph '
             'that contains a marker appears in the unit before it and the unit it opens.')
