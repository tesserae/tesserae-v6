#!/usr/bin/env python3
"""Coptic Old Testament books that follow the Septuagint, paired with Brenton (1851).

The installed Coptic Old Testament files pair each verse with the World English
Bible, which translates the Hebrew. Where the Coptic follows the Septuagint the
two diverge: the Psalter counts the title as a verse (or does not), Daniel carries
the additions, Proverbs runs in the Septuagint's order. Brenton's translation is
OF the Septuagint, so it is the right English for these books.

Method (see coptic_align_common.py): our references end in chapter.verse, but
the numbering is a hypothesis, not a fact, so each chapter is paired by length
with dynamic programming, then judged by the two checks of README.md (names, here
read through the Coptic consonant skeleton, and length correlation), each against
a displaced control. A work whose checks do not clear its control is not written.

Usage:
    python align_coptic_brenton.py WORK [WORK ...]     (e.g. bohairic.psalmi)
    TESSERAE_COP_OUT=<staging folder>
"""
import collections
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import align_greek_bible as G
import coptic_align_common as C
from write_aligned import write_aligned

TEXTS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/cop'
OUT = os.environ.get('TESSERAE_COP_OUT', '/home/ncoffee/tesserae-backups/tr-d-staging/brenton')
SOURCE = {
    'translator': 'Lancelot C. L. Brenton', 'year': 1851,
    'title': 'The Septuagint Version of the Old Testament, with an English Translation',
    'place': 'London', 'publisher': 'Samuel Bagster and Sons', 'license': 'public domain',
    'url': 'https://archive.org/details/isbn_851501710 (text as distributed by ebible.org)',
}

# Coptic work -> Brenton book(s). A list means several English books are tried and the
# chapter-by-chapter map is chosen by the checks (Daniel).
WORKS = {
    'bohairic.psalmi': ['PSA'],
    'sahidic.proverbs': ['PRO'],
    'sahidic.habakkuk': ['HAB'],
    'sahidic.epistle_of_jeremiah': ['LJE'],
    'sahidic.bel_and_the_dragon': ['BEL'],
    'sahidic.i_chronicles': ['1CH'],
    'sahidic.daniel': ['DAG'],
    'bohairic.daniel': ['DAG', 'SUS', 'BEL'],
}


PARTS = {}


def _clean_verse(buf):
    txt = ' '.join(buf).strip()
    txt = re.sub(r'\\f .*?\\f\*', '', txt)
    txt = re.sub(r'\\x .*?\\x\*', '', txt)
    txt = re.sub(r'\\\+?\w+\*?', '', txt)
    return re.sub(r'\s+', ' ', txt).strip()


def load_brenton():
    """Brenton by book. G.load_usfm keeps one entry per verse NUMBER, so a verse printed in
    parts (Proverbs 4:27a, 4:27b) lost all but its last part and kept the stray letter in the
    text. Here the parts are kept apart for the aligner (PARTS) and joined for the verse map."""
    merged, parts = {}, {}
    for path in sorted(glob.glob(os.path.join(G.BRENTON, '*.usfm'))):
        m = re.search(r'-([A-Z0-9]{3})eng-Brenton', os.path.basename(path))
        if not m:
            continue
        book = m.group(1)
        chapter, cur, buf, entries = None, None, [], []
        for raw in open(path, encoding='utf-8'):
            line = raw.rstrip('\n')
            c = re.match(r'\\c\s+(\d+)', line)
            v = re.match(r'\\v\s+(\d+)[a-z]?(?:-\d+)?\s*(.*)', line)
            if c or (v and chapter is not None):
                if cur is not None and _clean_verse(buf):
                    entries.append((cur[0], cur[1], _clean_verse(buf)))
                if c:
                    chapter, cur, buf = int(c.group(1)), None, []
                else:
                    cur, buf = (chapter, int(v.group(1))), [v.group(2)]
                continue
            if line.startswith('\\') and line[:2] not in ('\\q', '\\p', '\\m'):
                continue
            if cur is not None:
                buf.append(re.sub(r'^\\\w+\*?\s*', '', line))
        if cur is not None and _clean_verse(buf):
            entries.append((cur[0], cur[1], _clean_verse(buf)))
        if not entries:
            continue
        mg, pt, seen = {}, {}, {}
        for c_, v_, t in entries:
            mg[(c_, v_)] = (mg.get((c_, v_), '') + ' ' + t).strip()
            k = seen.get((c_, v_), 0)
            seen[(c_, v_)] = k + 1
            pt[(c_, v_ * 10 + k % 10)] = t
        merged[book], parts[book] = mg, pt
    PARTS.update(parts)
    return merged


def load_cop(work):
    rows = collections.OrderedDict()
    for line in open(f'{TEXTS}/{work}.tess', encoding='utf-8'):
        m = re.match(r'^<([^>]*)>\s*(.*)$', line.rstrip('\n'))
        if m and m.group(1) not in rows:
            rows[m.group(1)] = m.group(2).strip()
    return rows


def split_ref(ref):
    m = re.search(r'\.(\d+)\.(\d+)$', ref)
    return (int(m.group(1)), int(m.group(2))) if m else None


def by_chapter(rows):
    ch = collections.OrderedDict()
    for ref, txt in rows.items():
        cv = split_ref(ref)
        if cv:
            ch.setdefault(cv[0], []).append((cv[1], ref, txt))
    return ch


def eng_chapters(book_verses):
    ch = collections.OrderedDict()
    for (c, v), t in sorted(book_verses.items()):
        ch.setdefault(c, []).append((v, t))
    return ch


def align_work(work, chapter_map, eng, ratio=None, free_ends=False):
    """chapter_map: {coptic chapter: (english book code, english chapter)}"""
    rows = load_cop(work)
    cops = by_chapter(rows)
    if ratio is None:
        tc = sum(len(t) for _, _, t in (x for v in cops.values() for x in v))
        te = sum(len(t) for c, (bk, ec) in chapter_map.items() for _, t in eng_chapters(eng[bk]).get(ec, []))
        ratio = te / max(tc, 1)
    ref_to_text = {}
    stats = collections.Counter()
    for c, items in cops.items():
        if c not in chapter_map:
            continue
        bk, ec = chapter_map[c]
        ev = eng_chapters(eng[bk]).get(ec, [])
        if not ev:
            continue
        spans = C.gale_church([len(t) for _, _, t in items], [len(t) for _, t in ev], ratio, free_ends)
        for i0, i1, j0, j1 in spans:
            if i1 == i0:
                continue
            txt = ' '.join(t for _, t in ev[j0:j1]).strip()
            if not txt:
                stats['unmatched'] += i1 - i0
                continue
            for _, ref, _ in items[i0:i1]:
                ref_to_text[ref] = txt
            stats[f'{i1 - i0}-{j1 - j0}'] += 1
    return rows, ref_to_text, stats, ratio


def judge(rows, ref_to_text):
    pairs = [(rows[r], t) for r, t in ref_to_text.items()]
    pairs_n = pairs
    hit, n = C.name_rate(pairs_n)
    chit, cn = C.name_rate(C.displaced(pairs_n))
    corr = C.length_corr(pairs)
    ccorr = C.length_corr(C.displaced(pairs))
    by_names = hit is not None and n >= 15 and hit >= 0.30 and hit >= (chit or 0) + 0.15
    by_len = corr is not None and corr >= 0.45 and corr >= (ccorr or 0) + 0.20
    return {'name_hit': hit, 'name_n': n, 'control_name_hit': chit, 'length_corr': corr,
            'control_length_corr': ccorr, 'verified_by': ('names and length' if by_names and by_len else
                                                          'names' if by_names else
                                                          'length' if by_len else None)}


def write(work, rows, ref_to_text, verdict, extra_note=''):
    units, idx, r2u = [], {}, {}
    for r in rows:
        t = ref_to_text.get(r)
        if t is None:
            continue
        if t not in idx:
            idx[t] = len(units)
            units.append(t)
        r2u[r] = idx[t]
    src = dict(SOURCE, mode='chapter and verse by length', ref_composition=['chapter', 'verse'])
    return write_aligned(
        OUT, 'cop', work, units, r2u,
        attribution="Brenton's Septuagint (1851), public domain", license='Public domain',
        sources=[src], confidence=CONFIDENCE.get(work, 'medium'),
        approximate=work in ('bohairic.psalmi', 'sahidic.proverbs'), tess_refs=list(rows),
        name_check={'name_check_hit_rate': round(verdict['name_hit'] or 0, 3),
                    'name_check_n': verdict['name_n'],
                    'control_name_hit_rate': round(verdict['control_name_hit'] or 0, 3),
                    'length_correlation': round(verdict['length_corr'] or 0, 3),
                    'control_length_correlation': round(verdict['control_length_corr'] or 0, 3)},
        verified_by=verdict['verified_by'], notes=extra_note or None)


# The Psalter and Proverbs are paired by length where the two traditions divide verses differently,
# and a neighbour can be one verse off; Daniel and the Epistle pair one to one in all but a few verses.
CONFIDENCE = {'bohairic.daniel': 'high', 'sahidic.epistle_of_jeremiah': 'high'}
RATIO = 1.25  # English characters per Coptic character, measured on the complete books (1.25 to 1.27)
COST_DROP = 3.0  # a psalm whose own alignment costs more than this per line is left unpaired


def block_cost(il, el, spans, ratio=RATIO):
    return sum(C._cost(sum(len(x) for x in il[i0:i1]), sum(len(x) for x in el[a:b]), ratio)
               + C.PRIOR[(i1 - i0, b - a)] for i0, i1, a, b in spans) / max(len(il), 1)


def dp_block(items, eng, free_ends=False, ratio=RATIO, vc=None, ve=None, weight=0.0):
    """items [(ref, text)], eng [text]. Returns ({ref: english}, cost per line).
    vc and ve, with a weight, add the verse-number prior: a move pays weight per verse of
    disagreement between the Coptic verse number and the English one (capped at five)."""
    il = [t for _, t in items]
    extra = None
    if weight and vc is not None and ve is not None:
        def extra(i, j):
            return weight * min(abs(vc[i] - ve[j]), 5)
    spans = C.gale_church([len(t) for t in il], [len(t) for t in eng], ratio, free_ends, extra)
    out = {}
    for i0, i1, a, b in spans:
        if i1 == i0 or b == a:
            continue
        txt = ' '.join(eng[a:b]).strip()
        for ref, _ in items[i0:i1]:
            out[ref] = txt
    return out, block_cost(il, eng, spans, ratio)


def number_block(items, eng_by_verse, offsets):
    """Pair verse v with English verse v+offset. Returns the candidate list sorted by length correlation."""
    res = []
    for o in offsets:
        cost, pairs, n = C.number_cost(items, eng_by_verse, o, RATIO)
        if cost is None or n < 8:
            continue
        cor = C.length_corr([(t, e) for _, t, e in pairs], 5)
        if cor is None:
            continue
        res.append((cor, o, n, pairs))
    res.sort(key=lambda x: -x[0])
    return res


def number_work(work, eng, books, offsets, report):
    """Fragmentary books: each Coptic chapter is placed by verse offset and judged on its own."""
    rows = load_cop(work)
    cops = by_chapter(rows)
    r2t = {}
    for c, items in cops.items():
        its = [(v, r, t) for v, r, t in items]
        cands = []
        for bk in books:
            for ec, vs in eng_chapters(eng[bk]).items():
                for cor, o, n, pairs in number_block(its, dict(vs), offsets):
                    cands.append((cor, bk, ec, o, n, pairs))
        cands.sort(key=lambda x: -x[0])
        if len(its) < 8 or not cands:
            report.append(f'  chapter {c}: {len(its)} lines, too few to test, left unpaired')
            continue
        top = cands[0]
        # the runner-up must be a different placement, not the same chapter shifted by one with the same corr
        second = cands[1][0] if len(cands) > 1 else 0.0
        nr, nn = C.name_rate([(t, e) for _, t, e in top[5]])
        strong_names = nr is not None and nn >= 8 and nr >= 0.7 and top[0] >= 0.45
        ok = ((top[0] >= 0.45 and top[0] - second >= 0.20 and (nr is None or nn < 4 or nr >= 0.3))
              or strong_names)
        report.append(f'  chapter {c}: {len(its)} lines -> {top[1]} {top[2]} offset {top[3]:+d}, '
                      f'{top[4]} paired, corr {top[0]:.2f} vs runner-up {second:.2f}, names {nr}/{nn}  '
                      f'{"WRITTEN" if ok else "refused"}')
        if ok:
            for ref, t, e in top[5]:
                r2t[ref] = e
    return rows, r2t


def per_chapter_work(work, eng, bk, report, chapters=None, drop=True):
    rows = load_cop(work)
    cops = by_chapter(rows)
    E = eng_chapters(PARTS[bk])
    r2t = {}
    for c, items in cops.items():
        el = [t for _, t in E.get(c, [])]
        if not el:
            report.append(f'  chapter {c}: no English chapter')
            continue
        out, cost = dp_block([(r, t) for _, r, t in items], el)
        if drop and cost > COST_DROP:
            report.append(f'  chapter {c}: {len(items)} lines vs {len(el)} verses, cost {cost:.2f} per line, left unpaired')
            continue
        r2t.update(out)
    return rows, r2t


def proverbs(eng, report):
    """Chapters 24, 30 and 31 are not paired: the Septuagint prints Hebrew 30:1-14 and 31:1-9
    inside chapter 24 and then 31:10-31 as its own 31, and this Coptic follows the Hebrew
    chapter order, so no monotone alignment exists. The other 28 chapters are paired
    chapter by chapter, with the verse numbers as a prior (both sides number alike)."""
    rows = load_cop('sahidic.proverbs')
    cops = by_chapter(rows)
    E = eng_chapters(PARTS['PRO'])
    r2t = {}
    for c, items in cops.items():
        if c in (24, 30, 31):
            report.append(f'  chapter {c}: {len(items)} lines, Septuagint chapter order differs, left unpaired')
            continue
        ev = E[c]
        out, cost = dp_block([(r, t) for _, r, t in items], [t for _, t in ev],
                             vc=[v for v, _, _ in items], ve=[k // 10 for k, _ in ev], weight=2.0)
        r2t.update(out)
    return rows, r2t


def global_work(work, eng, bk, report, chapters_from=None):
    rows = load_cop(work)
    items = [(r, t) for r, t in rows.items()]
    ev = [t for (c, v), t in sorted(PARTS[bk].items())]
    out, cost = dp_block(items, ev)
    report.append(f'  whole-book alignment cost {cost:.2f} per line')
    return rows, out


def daniel_bohairic(eng, report):
    rows = load_cop('bohairic.daniel')
    cops = by_chapter(rows)
    r2t = {}
    main = [(r, t) for c in range(1, 15) for _, r, t in cops.get(c, [])]
    ev = [t for (c, v), t in sorted(PARTS['DAG'].items())]
    out, cost = dp_block(main, ev)
    report.append(f'  chapters 1 to 14 against Daniel 1 to 12 (Theodotion, as Brenton prints it): cost {cost:.2f} per line')
    r2t.update(out)
    for c, bk, lo, hi in [(16, 'SUS', 1, 64), (17, 'BEL', 2, 22), (18, 'BEL', 23, 42)]:
        el = [t for (cc, v), t in sorted(eng[bk].items()) if lo <= v <= hi]
        out, cost = dp_block([(r, t) for _, r, t in cops[c]], el)
        report.append(f'  chapter {c} against {bk} {lo}-{hi}: cost {cost:.2f} per line')
        r2t.update(out)
    report.append('  chapters 15 and 19 hold the Old Greek wording, which Brenton does not print: left unpaired')
    return rows, r2t


def main(argv):
    brenton = load_brenton()
    os.makedirs(OUT, exist_ok=True)
    summary = []
    for work in argv or list(WORKS):
        report = []
        print(f'== {work}')
        if work == 'bohairic.psalmi':
            rows, r2t = per_chapter_work(work, brenton, 'PSA', report)
        elif work == 'sahidic.proverbs':
            rows, r2t = proverbs(brenton, report)
        elif work == 'sahidic.epistle_of_jeremiah':
            rows, r2t = global_work(work, brenton, 'LJE', report)
        elif work == 'sahidic.habakkuk':
            rows, r2t = number_work(work, brenton, ['HAB'], range(-3, 4), report)
        elif work == 'sahidic.daniel':
            rows, r2t = number_work(work, brenton, ['DAG'], range(-5, 41), report)
        elif work == 'bohairic.daniel':
            rows, r2t = daniel_bohairic(brenton, report)
        else:
            rows = load_cop(work)
            r2t = {}
            report.append(f'  {len(rows)} lines: a fragment too short for either check (needs 15 names or 10 verses of length), refused')
        print('\n'.join(report))
        if not r2t:
            print('  NOT WRITTEN (nothing paired)')
            summary.append((work, len(rows), 0, None))
            continue
        v = judge(rows, r2t)
        print('  ', {k: (round(x, 3) if isinstance(x, float) else x) for k, x in v.items()})
        if not v['verified_by']:
            print('  NOT WRITTEN (both checks fail)')
            summary.append((work, len(rows), 0, v))
            continue
        path = write(work, rows, r2t, v, extra_note='; '.join(r.strip() for r in report if 'left unpaired' in r or 'refused' in r)[:600])
        print('  wrote', path, f'{len(r2t)} of {len(rows)} lines')
        summary.append((work, len(rows), len(r2t), v))
    return summary


if __name__ == '__main__':
    main(sys.argv[1:])
