#!/usr/bin/env python3
"""Remove a Loeb volume's own headings from the start of a unit (Part F, 2026-10-24).

The Loeb volumes print matter of their own before a book or poem: Duff's prose
"ARGUMENT" of each book of the Punica, and the English title of a poem of the
Peristephanon ("A Hymn in Honour of Quirinus ..."). The page method pairs the page
with the lines on it, so such a heading arrives as the first words of a unit. A
heading is the editor's, not the translation of anything on our side, so it is cut.

    strip_book_summaries.py silius|prudentius FILE.json [FILE2.json ...]

Edits each file in place (the staged copies only) and prints what it removed.
The Argument of the Punica ends where its last parenthetical line range ("(278-x. 325).")
ends: the first range after the word ARGUMENT, then every range that follows within
600 characters of the one before.
"""
import json
import re
import sys

RANGE = re.compile(r'\(\d[0-9A-Za-z,\-–—. ?]{0,14}\)\s*\.')
TITLE_ENDS = [
    ('A Hymn in Honour of the Holy Martyrs Emeterius', 'Calagurris,'),
    ('A Hymn in Honour of Quirinus', "Siscia.'"),
    ('To Bishop Valerian on the Passion', 'Hippolytus."'),
]


def strip_argument(t):
    if not t.startswith('ARGUMENT'):
        return t
    end, prev = None, 0
    for m in RANGE.finditer(t[:4000]):
        if end is not None and m.start() - prev > 600:
            break
        end = prev = m.end()
    return t[end:].lstrip() if end else t


def strip_title(t):
    for start, last in TITLE_ENDS:
        if t.startswith(start):
            i = t.find(last, len(start))
            if 0 < i < 300:
                return t[i + len(last):].lstrip()
    return t


def main():
    kind, files = sys.argv[1], sys.argv[2:]
    fn = {'silius': strip_argument, 'prudentius': strip_title}[kind]
    for f in files:
        d = json.load(open(f))
        n = 0
        for i, u in enumerate(d['units']):
            v = fn(u)
            if v != u:
                n += 1
                print(f'  unit {i}: removed {len(u) - len(v)} characters, now begins: {v[:70]!r}')
                d['units'][i] = v
        json.dump(d, open(f, 'w'), ensure_ascii=False)
        print(f'{f.split("/")[-1]}: {n} units changed')


if __name__ == '__main__':
    main()
