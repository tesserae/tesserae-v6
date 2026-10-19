#!/usr/bin/env python3
"""Cicero, De Legibus: Francis Barham's translation aligned to the corpus
sections by speaker turn.

Source: 'Treatise on the Laws, by Francis Barham, Esq.' as reprinted in
The Treatises of M. T. Cicero (Bohn's Classical Library, ed. C. D. Yonge,
London, 1878 printing; Barham's translation first published 1841), OCR text
from archive.org item treatisesofcicer00ciceuoft. The translation numbers
the old chapters (I., II., ...) and not the modern sections, and no
public concordance between the two is machine-readable. Both texts are,
however, dialogues whose speakers are named at every turn, in the same order,
so the alignment runs on turns:

  1. The Latin turns are cut from texts/la/cicero.de_legibus.tess at the
     inline speaker labels ('Atticus:', 'Quintus:', 'Marcus:'); each turn
     knows which section refs it covers.
  2. The English turns are cut at the speaker names that open a paragraph
     ('Atticus.--', 'Marcus Cicero.--').
  3. Turns are matched one to one in order (a dynamic program on the
     speaker sequence with a small penalty for skipping a turn on either
     side), book by book.
  4. A section is linked to every English turn that overlaps it. Sections
     that share a turn are one unit, so a unit is the run of turns that
     touches a connected group of sections.

Run: align_de_legibus.py --src <OCR txt> --tess <tess> --out <json> [--report]
"""
import argparse
import json
import math
import os
import re
import sys

START = 'ON THE LAWS'
LABEL_RX = re.compile(r'(?<![\w])(Atticus|Quintus|Marcus):\s')
EN_TURN_RX = re.compile(
    r'^(?:[IVXLCivxl1]{1,7}[.,]\s+)?(Atticus|Quintus(?:\s+Cicero)?|Marcus(?:\s+Cicero)?)\s*[.,:]?\s*[—–-]{1,3}\s*(.*)$')
HEAD_RX = re.compile(r'^\s*[\dA-Za-z]{0,4}\s*(?:O[NXK]|0N)[.,*]?\s+THE\s+LAWS[.,]?\s*[\dA-Za-z]{0,4}\s*$', re.I)
BOOKHEAD_RX = re.compile(r'^\s*BOOK\s+[IVLJ1]{1,4}\.?\s*$')
SPEAKER = {'Atticus': 'A', 'Quintus': 'Q', 'Marcus': 'M'}


def latin_turns(tess):
    turns = []  # dict(book, speaker, refs, text)
    for line in open(tess, encoding='utf-8'):
        ref, text = line.rstrip('\n').split('\t', 1)
        m = re.search(r'(\d+)\.(\d+)>', ref)
        book, sec = int(m.group(1)), int(m.group(2))
        full = f'cic. leg. {book}.{sec}'
        pos = 0
        for lm in LABEL_RX.finditer(text):
            lead = text[pos:lm.start()].strip()
            if lead and turns:
                turns[-1]['refs'].add(full)
                turns[-1]['text'] += ' ' + lead
            turns.append({'book': book, 'sp': SPEAKER[lm.group(1)], 'refs': {full}, 'text': ''})
            pos = lm.end()
        tail = text[pos:].strip()
        if turns:
            turns[-1]['refs'].add(full)
            turns[-1]['text'] += ' ' + tail
    return turns


def english_book_lines(src):
    lines = open(src, encoding='utf-8', errors='replace').read().split('\n')
    start = None
    seen_treatise = False
    for i, ln in enumerate(lines):
        flat = re.sub(r'\s+', ' ', ln).strip()
        if flat == 'TREATISE ON THE LAWS.':
            seen_treatise = True
        if seen_treatise and flat.startswith('INTRODUCTION TO THE FIRST BOOK'):
            start = i
            break
    end = None
    for i in range(start, len(lines)):
        if re.sub(r'\s+', ' ', lines[i]).strip().startswith('[How many books of this treatise'):
            end = i
            break
    return lines[start:end]


def english_turns(src):
    lines = english_book_lines(src)
    books = []  # list of turn lists
    cur = None
    in_note = False
    in_intro = False
    para = None

    def close():
        nonlocal para
        if para is not None and cur is not None:
            cur.append(para)
        para = None

    for ln in lines:
        s = re.sub(r'\s+', ' ', ln).strip()
        if re.match(r'^INTRODUCTION TO THE (FIRST|SECOND|THIRD) BOOK', s):
            close()
            cur = []
            books.append(cur)
            in_intro = True
            in_note = False
            continue
        if BOOKHEAD_RX.match(ln):
            continue
        if len(s) <= 42 and not re.search(r'[a-z]{4,}', s) and re.search(r'LAWS|DE\s*[XN]AT|ETC\.|CONSULSH', s):
            in_note = False
            continue
        if HEAD_RX.match(ln) or re.fullmatch(r'\d*\s*[A-Z ]{0,6}', s) and not re.search(r'[a-z]', s):
            in_note = False
            continue
        if not s:
            in_note = False
            continue
        if re.match(r'^\d{1,2} ', s) and not re.match(r'^\d{1,2} (?:Atticus|Marcus|Quintus)', s):
            in_note = True
            continue
        if in_note:
            continue
        if s.startswith('[') and not para:
            in_note = True
            continue
        m = EN_TURN_RX.match(s)
        if m:
            close()
            in_intro = False
            para = {'sp': SPEAKER[m.group(1).split()[0]], 'name': m.group(1), 'text': m.group(2)}
            continue
        if in_intro or cur is None:
            continue
        if para is None:
            continue
        # a chapter numeral alone on a line, or a verse line, stays with the turn
        para['text'] += '\x01' + s
    close()
    return books


def vocabulary(src):
    text = open(src, encoding='utf-8', errors='replace').read()
    v = {}
    for w in re.findall(r"[a-z]+", text.lower()):
        v[w] = v.get(w, 0) + 1
    return v


SMALL = set('a an as at be by do go he if in is it me my no of on or so to up us we am i'.split())


def dehyphenate(text, vocab):
    """Line ends marked \\x01: the OCR dropped the hyphen of a word broken
    across lines. Join the two halves when the joined word occurs in the book
    as a whole word and at least one half is rare on its own."""
    def fix(m):
        w1, w2 = m.group(1), m.group(2)
        a, b = w1.lower(), w2.lower()
        joined = vocab.get(a + b, 0)
        if (a not in SMALL and joined >= 2 and a + b != a + b[:0]
                and (vocab.get(a, 0) < 8 or vocab.get(b, 0) < 8)):
            return w1 + w2
        return w1 + ' ' + w2
    def fix_hyphen(m):
        w1, w2 = m.group(1), m.group(2)
        if vocab.get((w1 + w2).lower(), 0) >= 1:
            return w1 + w2
        return w1 + '-' + w2
    text = re.sub(r'([A-Za-z]+)-\x01([a-z]+)', fix_hyphen, text)
    text = re.sub(r'([A-Za-z]+)\x01([a-z]+)', fix, text)
    text = text.replace('\x01', ' ')
    # chapter numerals of the old editions, lacuna rows and footnote marks
    text = re.sub(r'(?:(?<=[.?!;:"\u201d])|(?<=\s)|^)[IVXL]{1,6}\.\s+(?=[A-Z\[\u2014"\'])', ' ', text)
    text = re.sub(r'(?:\s*(?:\*|-x-|\u2022|\'\u2022))+', ' ', text)
    text = re.sub(r'(?<=[a-z.,;?!])\d{1,2}(?=\s|$)', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def match(lat, eng):
    """Order-preserving alignment of two turn sequences. A step takes one
    Latin turn and one English turn, or up to four turns on one side against
    one on the other (the Latin Library drops a speaker label here and there,
    and Barham splits or joins a few turns). Returns a list of
    (latin indices, english indices) groups and the total cost."""
    n, m = len(lat), len(eng)
    INF = 10.0 ** 9
    lw = [len(t['text'].split()) for t in lat]
    ew = [len(t['text'].split()) for t in eng]
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    steps = [(1, 1), (1, 2), (1, 3), (2, 1), (3, 1), (4, 1)]
    for i in range(n + 1):
        for j in range(m + 1):
            c = cost[i][j]
            if c >= INF:
                continue
            for di, dj in steps:
                if i + di > n or j + dj > m:
                    continue
                step = 0.0 if lat[i]['sp'] == eng[j]['sp'] else 3.0
                L = sum(lw[i:i + di])
                E = sum(ew[j:j + dj])
                step += min(3.0, 1.5 * abs(math.log((E + 6) / (1.25 * L + 6))))
                step += 1.5 * (di + dj - 2)
                if c + step < cost[i + di][j + dj]:
                    cost[i + di][j + dj] = c + step
                    back[i + di][j + dj] = (i, j)
            if i < n and c + 3 < cost[i + 1][j]:
                cost[i + 1][j] = c + 3
                back[i + 1][j] = (i, j)
            if j < m and c + 3 < cost[i][j + 1]:
                cost[i][j + 1] = c + 3
                back[i][j + 1] = (i, j)
    groups, i, j = [], n, m
    while (i, j) != (0, 0):
        pi, pj = back[i][j]
        if i > pi and j > pj:
            groups.append((list(range(pi, i)), list(range(pj, j))))
        i, j = pi, pj
    return list(reversed(groups)), cost[n][m]


def build(src, tess):
    ltur = latin_turns(tess)
    etur = english_turns(src)
    vocab = vocabulary(src)
    for book in etur:
        for t in book:
            t['text'] = dehyphenate(t['text'], vocab)
    out = {}
    report = []
    for b in (1, 2, 3):
        lat = [t for t in ltur if t['book'] == b]
        eng = etur[b - 1]
        pairs, cost = match(lat, eng)
        report.append((b, len(lat), len(eng), sum(len(g[0]) for g in pairs), sum(len(g[1]) for g in pairs), cost))
        out[b] = (lat, eng, pairs)
    return out, report


NAMES = {'A': 'Atticus', 'Q': 'Quintus', 'M': 'Marcus'}


def units_from(out, tess):
    """Link sections to English turns and group sections that share a turn."""
    refs = []
    latin_by_ref = {}
    for line in open(tess, encoding='utf-8'):
        ref, text = line.rstrip('\n').split('\t', 1)
        m = re.search(r'(\d+)\.(\d+)>', ref)
        key = f'cic. leg. {m.group(1)}.{m.group(2)}'
        refs.append(key)
        latin_by_ref[key] = text
    turns_of = {r: set() for r in refs}
    for b, (lat, eng, pairs) in out.items():
        for li, ej in pairs:
            for i in li:
                for r in lat[i]['refs']:
                    for j in ej:
                        turns_of[r].add((b, j))
    parent = {r: r for r in refs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    owner = {}
    for r in refs:
        for t in turns_of[r]:
            if t in owner:
                parent[find(r)] = find(owner[t])
            else:
                owner[t] = r
    groups = {}
    for r in refs:
        if turns_of[r]:
            groups.setdefault(find(r), []).append(r)
    units, ref_to_unit = [], {}
    for r in refs:  # unit numbers follow the order of the first section
        if not turns_of[r]:
            continue
        g = find(r)
        if g in {u for u in ()}:
            continue
    seen = {}
    for r in refs:
        if not turns_of[r]:
            continue
        g = find(r)
        if g not in seen:
            members = groups[g]
            ts = sorted({t for m in members for t in turns_of[m]})
            text = ' '.join(
                f"{NAMES[out[b][1][j]['sp']]}: {out[b][1][j]['text']}" for b, j in ts)
            seen[g] = len(units)
            units.append(text)
        ref_to_unit[r] = seen[g]
    uncovered = [r for r in refs if r not in ref_to_unit]
    return refs, latin_by_ref, units, ref_to_unit, uncovered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out, report = build(a.src, a.tess)
    for r in report:
        print('book %d: latin turns %d, english turns %d, latin matched %d, english matched %d, cost %.1f' % r)
    refs, latin_by_ref, units, ref_to_unit, uncovered = units_from(out, a.tess)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import proper_names as V
    pairs = [(latin_by_ref[r], units[u]) for r, u in ref_to_unit.items()]
    hit, n = V.score(pairs, 'la', sample=800)
    print('sections %d, translated %d (%.1f%%), units %d' % (
        len(refs), len(ref_to_unit), 100.0 * len(ref_to_unit) / len(refs), len(units)))
    print('uncovered:', ', '.join(r.replace('cic. leg. ', '') for r in uncovered) or 'none')
    sizes = {}
    for u in ref_to_unit.values():
        sizes[u] = sizes.get(u, 0) + 1
    print('largest unit covers %d sections; name check %.3f on %d' % (max(sizes.values()), hit or 0, n))
    rec = {
        'tess_work': 'la/cicero.de_legibus',
        'language': 'la',
        'n_tess_refs': len(refs),
        'n_translated': len(ref_to_unit),
        'coverage': round(len(ref_to_unit) / len(refs), 4),
        'mean_source_lines_per_translation_unit': round(len(ref_to_unit) / max(1, len(units)), 1),
        'alignment_confidence': 'high' if (hit or 0) >= 0.70 else 'medium',
        'name_check_hit_rate': hit,
        'name_check_n': n,
        'sources': [{
            'translator': 'Francis Barham',
            'year': 1841,
            'title': 'Treatise on the Laws, in The Treatises of M. T. Cicero (Bohn\'s '
                     'Classical Library, ed. C. D. Yonge, London, 1878 printing)',
            'publisher': 'Henry G. Bohn',
            'mode': 'speaker-turn',
            'ref_composition': ['book', 'section'],
            'source_url': 'https://archive.org/details/treatisesofcicer00ciceuoft',
            'rights_basis': 'Translated 1841 by Francis Barham (died 1871); public domain',
            'short_attribution': 'Francis Barham (1841)',
            'note': 'Aligned by speaker turn: sections that share a speaker turn share one unit.',
        }],
        'unit_sources': [0] * len(units),
        'license': 'Public domain (Francis Barham, 1841).',
        'attribution': 'Francis Barham (1841), Bohn edition',
        'n_units_stored': len(units),
        'units': units,
        'ref_to_unit': ref_to_unit,
    }
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(rec, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print('wrote', a.out)


if __name__ == '__main__':
    sys.exit(main())
