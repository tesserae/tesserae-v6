"""Shared helpers for filling the syntax parse gap (Latin and Greek).

THE REF RULE (found 2026-10-28 by reading backend/fusion.py find_syntax_matches
and backend/syntax_parser.py get_syntax_score_by_ref): a line of a .tess file is
read from the syntax database only when the row's `ref` is EXACTLY the text
inside the angle brackets of that line (`<lucr. 6.1189>` -> `lucr. 6.1189`), the
same string TextProcessor.process_file gives as the unit's `ref`. Nothing maps
one form to another. Rows keyed any other way (for example the CTS form
`adamnan.de_locis_santis urn:cts:...1.1`) are never read. Rows are looked up by
`texts.filename`, the exact file name.
"""
import json
import os
import re
import sqlite3
import unicodedata

TAG_LINE = re.compile(r'^<([^>]+)>\s*(.+)$')
PART_RE = re.compile(r'^(?P<base>.+?)\.part\.(?P<rest>.+)\.tess$')


def norm_key(text):
    """Comparable form of a line or of a parse's joined tokens: accents and
    punctuation gone, case folded, final sigma and j/v folded."""
    s = unicodedata.normalize('NFD', text or '')
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.casefold().replace('ς', 'σ').replace('j', 'i').replace('v', 'u')
    return ''.join(c for c in s if c.isalnum())


def read_tess(path):
    """[(tag, text)] exactly as TextProcessor.process_file reads a file."""
    out = []
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = TAG_LINE.match(line)
            if m:
                out.append((m.group(1), m.group(2)))
    return out


def tokens_key(tokens_json):
    try:
        return norm_key(''.join(json.loads(tokens_json)))
    except (TypeError, ValueError):
        return ''


def open_ro(path):
    return sqlite3.connect(f'file:{path}?mode=ro&immutable=1', uri=True)


def load_rows(conn):
    """{filename: [(ref, key)]} in stored order, for the whole database."""
    names = dict(conn.execute('SELECT text_id, filename FROM texts'))
    out = {n: [] for n in names.values()}
    cur = conn.execute('SELECT text_id, ref, tokens FROM syntax ORDER BY text_id, rowid')
    for tid, ref, toks in cur:
        out[names[tid]].append((ref, tokens_key(toks)))
    return out


def align(tess_lines, rows, prefer_same_ref=True):
    """Match the lines of a file to stored rows by normalized text.

    tess_lines: [(tag, text)]. rows: [(ref, key)].
    Returns (mapping tag -> ref, unmatched_tags). A line first takes the row
    whose ref already equals its tag when the text agrees, else the first
    unused row with the same key at or after the previous match, else the
    first unused row with that key anywhere. Never by position alone: a line
    whose text is in no row stays unmatched."""
    by_key = {}
    ref_idx = {}
    for i, (r, k) in enumerate(rows):
        by_key.setdefault(k, []).append(i)
        ref_idx.setdefault(r, i)
    used = set()
    mapping, unmatched, seen = {}, [], set()
    last = -1
    for tag, text in tess_lines:
        if tag in seen:
            continue  # a repeated tag in one file: the first line keeps it, as in the builds
        seen.add(tag)
        k = norm_key(text)
        i = None
        if prefer_same_ref:
            j = ref_idx.get(tag)
            if j is not None and j not in used and rows[j][1] == k:
                i = j
        if i is None:
            cands = [c for c in by_key.get(k, ()) if c not in used]
            if not k or not cands:
                unmatched.append(tag)
                continue
            after = [c for c in cands if c > last]
            i = after[0] if after else cands[0]
        used.add(i)
        last = i
        mapping[tag] = rows[i][0]
    return mapping, unmatched
