#!/usr/bin/env python3
"""Add a Wikipedia summary to each event of the dossier database.

  add_summaries.py INPUT.sqlite INTROS.json OUTPUT.sqlite

INTROS.json maps a Wikidata id to {"title", "description", "paragraph"}: the
opening paragraph of the event's English Wikipedia article. The copy gets four
new columns on `events`: summary (the paragraph, at most 600 characters, cut at
a sentence end), summary_source ('Wikipedia'), summary_url and summary_licence
('CC BY-SA 4.0'). An event without an article keeps its Wikidata description.
The input file is never changed.
"""
import json
import re
import shutil
import sqlite3
import sys
from urllib.parse import quote

MAX_CHARS = 600
LICENCE = 'CC BY-SA 4.0'
ABBREVIATIONS = {'c', 'ca', 'st', 'mr', 'mrs', 'dr', 'vs', 'cf', 'no', 'fl', 'b', 'd', 'r', 'e', 'ed', 'eds',
                 'gen', 'cos', 'sr', 'jr', 'lit', 'approx', 'esp', 'ie', 'eg'}
_BREAK = re.compile(r'([.!?]["\')\]]*)\s+(?=["\'(\[]?[A-Z0-9])')


def _is_sentence_end(text, end):
    """True when the full stop that closes text[:end] ends a sentence rather than an abbreviation or initial."""
    stem = re.search(r'(\w+)\W*$', text[:end - 1])
    word = stem.group(1) if stem else ''
    if text[end - 1:end] != '.':
        return True
    if word.lower() in ABBREVIATIONS:
        return False
    return not (len(word) == 1 and word.isupper())


def summarise(paragraph, limit=MAX_CHARS):
    """The paragraph cut after the last whole sentence that fits in `limit` characters."""
    text = ' '.join((paragraph or '').split())
    text = re.sub(r'\[\d+\]', '', text)
    if len(text) <= limit:
        return text
    cut = 0
    for m in _BREAK.finditer(text):
        end = m.end(1)
        if end > limit:
            break
        if _is_sentence_end(text, end):
            cut = end
    if cut:
        return text[:cut]
    # One sentence longer than the limit: stop at a word and say so.
    return text[:limit - 1].rsplit(' ', 1)[0].rstrip(' ,;:') + '…'


def wikipedia_url(title):
    return 'https://en.wikipedia.org/wiki/' + quote(title.replace(' ', '_'), safe='_(),:\'')


def main(argv):
    if len(argv) != 4:
        print(__doc__)
        return 2
    src, intros_path, out = argv[1:]
    shutil.copyfile(src, out)
    intros = json.load(open(intros_path, encoding='utf-8'))
    c = sqlite3.connect(out)
    have = {r[1] for r in c.execute('PRAGMA table_info(events)')}
    for col in ('summary', 'summary_source', 'summary_url', 'summary_licence'):
        if col not in have:
            c.execute(f'ALTER TABLE events ADD COLUMN {col} TEXT')
    total = c.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    filled = 0
    for (eid,) in c.execute('SELECT id FROM events').fetchall():
        it = intros.get(eid)
        text = summarise((it or {}).get('paragraph'))
        if not it or not text or not it.get('title'):
            continue
        c.execute('UPDATE events SET summary=?, summary_source=?, summary_url=?, summary_licence=? WHERE id=?',
                  (text, 'Wikipedia', wikipedia_url(it['title']), LICENCE, eid))
        filled += 1
    c.commit()
    c.execute('VACUUM')
    c.close()
    print(f'{filled} of {total} events have a Wikipedia summary; written to {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
