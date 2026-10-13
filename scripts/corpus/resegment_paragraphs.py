#!/usr/bin/env python3
"""Cut chapter-sized .tess units into paragraph-sized units of whole sentences.

Each unit '<ref>\\ttext' becomes '<ref>.1', '<ref>.2', ... : groups of whole
sentences of about --target words (never above --max unless one sentence is
longer, then it is cut at ';' or ':' and last at the comma nearest the
middle). Chapter references are kept as the prefix. Blank lines and the file's
line-ending style (CRLF or LF) are kept. The words are conserved: joining the
new units gives back the old unit's text, checked for every unit.

Usage: resegment_paragraphs.py FILE [--target 90] [--max 120] [--min 50] [--apply]
Dry run by default (prints counts before and after).
"""
import argparse
import re
import statistics

SENT_END = re.compile(r'(?<=[.?!])\s+(?=[A-Z"“(\[])')
ABBREV = re.compile(r'(?:^|\s)(?:[A-Za-z]{1,2}|Cap|Lib|Ps|Mt|Mc|Lc|Io|Ioh)\.$')


def sentences(text):
    parts, cur = [], ''
    for chunk in SENT_END.split(text):
        cur = (cur + ' ' + chunk).strip() if cur else chunk
        if ABBREV.search(cur):
            continue
        parts.append(cur)
        cur = ''
    if cur:
        parts.append(cur)
    return parts


def cut_long(sent, maxw):
    """Cut a sentence longer than maxw at ; or : then at the comma nearest the middle."""
    if len(sent.split()) <= maxw:
        return [sent]
    pieces = re.split(r'(?<=[;:])\s+', sent)
    if len(pieces) == 1:
        pieces = [sent]
    out = []
    for p in pieces:
        if len(p.split()) > maxw and ',' in p:
            words = p.split()
            mid = len(words) // 2
            idx = [i for i, w in enumerate(words[:-1]) if w.endswith(',')]
            if idx:
                k = min(idx, key=lambda i: abs(i - mid))
                out += cut_long(' '.join(words[:k + 1]), maxw) + cut_long(' '.join(words[k + 1:]), maxw)
                continue
        out.append(p)
    return out


def group(text, target, maxw, minw):
    units, cur, n = [], [], 0
    for s in (x for sent in sentences(text) for x in cut_long(sent, maxw)):
        w = len(s.split())
        if cur and (n >= target or n + w > maxw) and n >= minw:
            units.append(' '.join(cur))
            cur, n = [], 0
        cur.append(s)
        n += w
    if cur:
        if units and n < minw // 2:
            units[-1] += ' ' + ' '.join(cur)
        else:
            units.append(' '.join(cur))
    return units


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--target', type=int, default=90)
    ap.add_argument('--max', type=int, default=120)
    ap.add_argument('--min', type=int, default=50)
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    raw = open(a.file, encoding='utf-8', newline='').read()
    eol = '\r\n' if '\r\n' in raw else '\n'
    out, before, after = [], [], []
    for line in raw.split(eol):
        if '\t' not in line:
            out.append(line)
            continue
        ref, text = line.split('\t', 1)
        assert ref.startswith('<') and ref.endswith('>'), ref
        before.append(len(text.split()))
        units = group(text.strip(), a.target, a.max, a.min)
        assert ' '.join(units).split() == text.split(), f'words not conserved in {ref}'
        for i, u in enumerate(units, 1):
            out.append(f'{ref[:-1]}.{i}>\t{u}')
            after.append(len(u.split()))
    print(f'{a.file}: units {len(before)} -> {len(after)}; words {sum(before)} -> {sum(after)}')
    print(f'  median words/unit {statistics.median(before):.0f} -> {statistics.median(after):.0f}; '
          f'max {max(before)} -> {max(after)}; min {min(after)}; units over {a.max}: '
          f'{sum(1 for x in after if x > a.max)}; under 30: {sum(1 for x in after if x < 30)}')
    if a.apply:
        with open(a.file, 'w', encoding='utf-8', newline='') as fh:
            fh.write(eol.join(out))


if __name__ == '__main__':
    main()
