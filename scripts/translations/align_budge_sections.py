#!/usr/bin/env python3
"""Budge's English beside our Coptic lines, at the level of a section.

Source: E. A. Wallis Budge, Miscellaneous Coptic Texts (1915) and Coptic Apocrypha (1913),
British Museum, text from the Internet Archive (djvu text). Both are US public domain
by date of publication.

Our Coptic files number the manuscript lines in order (`<mercurius.1>`, `.2`, ...) and
carry no folio or paragraph markers, so there is nothing to look up. The alignment is a
monotone one: the English is cut into segments of two or three sentences, and dynamic
programming pairs each segment with a run of Coptic lines, using

  * length (Gale and Church: a Coptic character costs about 1.5 English ones, here
    measured from the work itself),
  * and the proper names of every second English name, read through the Coptic consonant
    skeleton (coptic_align_common.py).

The OTHER half of the names is never shown to the aligner. It is the check: the share of
segments whose held-out names occur in the Coptic run they were paired with, against the
same share for a control that shifts the segments by five. Length cannot be the check
here because the aligner already uses it, and the README's rule still holds: a file whose
check does not clear its control is not written.

Usage: python align_budge_sections.py WORK   (mercurius, theodosius.alexandria,
       book.bartholomew, dormition.john)
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coptic_align_common as C
from write_aligned import write_aligned

TEXTS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/cop'
SRC = os.environ.get('TESSERAE_BUDGE_SRC', '/home/ncoffee/tesserae-backups/tr-d-staging/src')
OUT = os.environ.get('TESSERAE_COP_OUT', '/home/ncoffee/tesserae-backups/tr-d-staging/budge')

MISC = {
    'translator': 'E. A. Wallis Budge',
    'title': 'Miscellaneous Coptic Texts in the Dialect of Upper Egypt',
    'year': 1915, 'place': 'London', 'publisher': 'British Museum', 'license': 'public domain',
    'url': 'https://archive.org/details/miscellaneouscop00budguoft',
}
APOC = {
    'translator': 'E. A. Wallis Budge',
    'title': 'Coptic Apocrypha in the Dialect of Upper Egypt',
    'year': 1913, 'place': 'London', 'publisher': 'British Museum', 'license': 'public domain',
    'url': 'https://archive.org/details/copticapocryphai00budguoft',
}

# work -> source file, source record, the English parts (label: first-line regex, regex of the first
# line after the part, line to start looking from) and the orders in which the parts are tried.
WORKS = {
    # The Coptic file holds the Acacius encomium (item XI, MS 6802 fol. 25 on) and the Martyrdom and
    # Miracles (item X, the same manuscript, fol. 1 to 24) in an order that is not Budge's, so both
    # orders are tried and the cheaper alignment is kept.
    'mercurius': ('miscellaneouscop00budguoft.txt', MISC, {
        'XI': (r'^THE ENCOMIUM WHICH SAINT APA ACACIUS', r'^A DISCOURSE ON THE ARCHANGEL', 40000),
        'X': (r'^THE MARTYRDOM AND MIRACLES OF', r'^THE ENCOMIUM OF ACACIUS, BISHOP OF', 40000),
        'IX': (r'^THE MARTYEDOM OF SAINT MEECUHIUS', r'^THE MARTYRDOM AND MIRACLES OF', 40000),
    }, [['XI', 'X'], ['X', 'XI'], ['XI', 'X', 'IX'], ['IX', 'X', 'XI']]),
    'theodosius.alexandria': ('miscellaneouscop00budguoft.txt', MISC, {
        'XIII': (r'^ENCOMIUM OF THEODOSIUS, ARCHBISHOP', r'^\[?HISTORIES OF THE MONKS', 50000),
    }, [['XIII']]),
    'book.bartholomew': ('copticapocryphai00budguoft.txt', APOC, {
        'I': (r'^THE BOOK OF THE KESURRECTION OF', r'^APPENDIX', 11000),
    }, [['I']]),
    'dormition.john': ('copticapocryphai00budguoft.txt', APOC, {
        'II': (r'^THE REPOSE OF SAINT JOHN THE EVANGELIST', r'^THE MYSTERIES OF SAINT JOHN THE', 14000),
    }, [['II']]),
}

PAGE_HEAD = re.compile(r"^\s*(\d{3,4})\s+[A-Z][A-Z ,.'\-\[\]]+$|^[A-Z][A-Z ,.'\-\[\]]+?\s+(\d{3,4})\s*$")
FOLIO = re.compile(r'F[o0][li1I]\.?\s*\d+\s*\S{0,2}(?=\s|$)')
FOOT_START = re.compile(r'^\s*(?:[\^*\-]\s*\d*|\d{1,2})\s+(?:Ps|Matt|Mark|Luke|John|Acts|Rom|Cor|Gen|Exod|Lev|Num|Deut|Isa|Jer|Dan|Hos|Compare|Comp|See|Cf|Text|The|A|An|Perhaps|Or|Lit|i\.|Probably|Read|MS|Cod|Hebr|Heb|Eph|Col|Rev|Zech|Prov|Job|Sam|Kings|Chron|Judg|Joel|Amos|Jonah|Micah|Nah|Hab|Zeph|Hag|Mal|Wisd|Ecclus|Tob|1|2|3)\b')


def extract(path, start_re, end_re, after=0):
    lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
    norm = [re.sub(r'\s+', ' ', ln.strip()) for ln in lines]
    s = next(i for i in range(after, len(lines)) if re.match(start_re, norm[i]))
    e = next(i for i in range(s + 5, len(lines)) if re.match(end_re, norm[i]))
    body, foot = [], False
    for ln in lines[s:e]:
        t = ln.rstrip()
        if PAGE_HEAD.match(t.strip()) and len(t.strip()) < 70:
            foot = False
            continue
        if not t.strip():
            foot = False
            body.append('')
            continue
        if foot:
            continue
        if FOOT_START.match(t) and body and body[-1] == '':
            foot = True
            continue
        body.append(t)
    text = '\n'.join(body)
    text = re.sub(r'-\n\s*', '', text)
    text = FOLIO.sub(' ', text)
    text = re.sub(r'\[[\^6cdeabEg]\]|\^+|\|', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def sentences(text):
    parts = re.split(r"(?<=[.?!])(?:['’”\"]?)\s+(?=['‘“\"]?[A-Z])", text)
    return [p.strip() for p in parts if p.strip()]


def segments(text, target=280):
    out, cur = [], ''
    for s in sentences(text):
        cur = (cur + ' ' + s).strip()
        if len(cur) >= target:
            out.append(cur)
            cur = ''
    if cur:
        if out and len(cur) < target / 3:
            out[-1] += ' ' + cur
        else:
            out.append(cur)
    return out


def load_cop(work):
    rows = []
    for line in open(f'{TEXTS}/{work}.tess', encoding='utf-8'):
        m = re.match(r'^<([^>]*)>\s*(.*)$', line.rstrip('\n'))
        if m:
            rows.append((m.group(1), m.group(2).strip()))
    return rows


def dp(clens, slens, hitsA, ratio, name_bonus=3.0, max_run=14):
    """Pair each segment with a run of Coptic lines (possibly none)."""
    n, m = len(clens), len(slens)
    pre = [0]
    for x in clens:
        pre.append(pre[-1] + x)
    INF = 1e18
    best = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[0] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    for j in range(m):
        hp = hitsA[j]  # prefix sums over lines
        sl = slens[j]
        for i in range(n + 1):
            b = best[i][j]
            if b >= INF:
                continue
            # the segment has no Coptic (lacuna in the manuscript or an omission)
            c = b + 5.0
            if c < best[i][j + 1]:
                best[i][j + 1] = c
                back[i][j + 1] = 0
            for d in range(1, max_run + 1):
                ni = i + d
                if ni > n:
                    break
                lc = pre[ni] - pre[i]
                c = b + C._cost(lc, sl, ratio[j] if isinstance(ratio, list) else ratio) + 0.15 * d
                if hp is not None:
                    c -= name_bonus * min(hp[ni] - hp[i], 2)
                if c < best[ni][j + 1]:
                    best[ni][j + 1] = c
                    back[ni][j + 1] = d
    # Coptic lines left over at the end are charged, then trace back from the best end row
    end_i = min(range(n + 1), key=lambda i: best[i][m] + 3.0 * (n - i))
    runs, i = [], end_i
    for j in range(m, 0, -1):
        d = back[i][j]
        runs.append((i - d, i))
        i -= d
    runs.reverse()
    return runs, best[end_i][m]


RARE = 6  # a name counts only if it occurs in at most this many segments: Mercurius and Decius are everywhere


def prepare_hits(segs, cop_skel):
    """Per segment: prefix sums over Coptic lines of how many of its A-names occur (None if no names),
    and the held-out B-names. Only names rare across the English count, so a name is evidence of place."""
    per = []
    df = {}
    for s in segs:
        uniq = []
        for x in C.eng_name_skeletons(s):
            if x not in uniq:
                uniq.append(x)
        per.append(uniq)
        for x in uniq:
            df[x] = df.get(x, 0) + 1
    hitsA, namesB = [], []
    for uniq in per:
        rare = [x for x in uniq if df[x] <= RARE]
        a, b = rare[0::2], rare[1::2]
        namesB.append(b)
        if not a:
            hitsA.append(None)
            continue
        pre = [0]
        for sk in cop_skel:
            pre.append(pre[-1] + sum(1 for x in a if x in sk))
        hitsA.append(pre)
    return hitsA, namesB


def check(runs, namesB, cop_skel, shift=5):
    def rate(order):
        tested = hit = 0
        for j, (a, b) in enumerate(runs):
            if b <= a:
                continue
            nb = namesB[order(j)] if order(j) < len(namesB) else []
            if not nb:
                continue
            sk = ''.join(cop_skel[a:b])
            sk = re.sub(r'(.)\1+', r'\1', sk)
            tested += 1
            hit += any(x in sk for x in nb)
        return (hit / tested if tested else None), tested
    real = rate(lambda j: j)
    ctrl = rate(lambda j: (j + shift) % len(runs))
    return real, ctrl


def run(work):
    fname, source, parts, orders = WORKS[work]
    texts = {lab: extract(os.path.join(SRC, fname), *spec) for lab, spec in parts.items()}
    rows = load_cop(work)
    clens = [len(t) for _, t in rows]
    cop_skel = [re.sub(r'(.)\1+', r'\1', C.cop_skeleton(t)) for _, t in rows]
    best = None
    for order in orders:
        text = ' '.join(texts[lab] for lab in order)
        segs = segments(text)
        ratio = len(text) / max(sum(clens), 1)
        hitsA, namesB = prepare_hits(segs, cop_skel)
        runs, cost = dp(clens, [len(s) for s in segs], hitsA, ratio)
        # second pass: the ratio of English to Coptic differs between the parts (translators and
        # scribes differ), so each part's own ratio is measured from the first pass and the DP is rerun
        bounds, pos = {}, 0
        for lab in order:
            n = len(segments(texts[lab]))
            bounds[lab] = (pos, pos + n)
            pos += n
        rj = [ratio] * len(segs)
        for _lab, (lo, hi) in bounds.items():
            ec = sum(len(segs[j]) for j in range(lo, min(hi, len(segs))))
            cc = sum(sum(clens[a:b]) for a, b in runs[lo:hi])
            if cc:
                for j in range(lo, min(hi, len(segs))):
                    rj[j] = ec / cc
        runs, cost = dp(clens, [len(s) for s in segs], hitsA, rj)
        print(f'  order {"+".join(order)}: {len(text)} English characters, {len(segs)} segments, ratio {ratio:.2f}, '
              f'cost {cost:.0f}, per segment {cost / len(segs):.2f}')
        if best is None or cost / len(segs) < best[0]:
            best = (cost / len(segs), order, segs, runs, namesB, ratio)
    _, order, segs, runs, namesB, ratio = best
    real, ctrl = check(runs, namesB, cop_skel)
    print(f'{work}: English parts {"+".join(order)}; {len(rows)} Coptic lines, ratio {ratio:.2f}')
    skipped = sum(1 for a, b in runs if b == a)
    print(f'  segments with no Coptic run: {skipped}; held-out names: real {real}, control {ctrl}')
    lens = [b - a for a, b in runs if b > a]
    print(f'  Coptic lines per segment: mean {sum(lens) / max(len(lens), 1):.1f}, max {max(lens)}')
    corr = C.length_corr([(''.join(t for _, t in rows[a:b]), segs[j]) for j, (a, b) in enumerate(runs) if b > a], 20)
    print(f'  length correlation (the aligner uses length, so this is not independent): {corr}')
    ok = (real[0] is not None and real[1] >= 25 and real[0] >= 0.30
          and real[0] >= (ctrl[0] or 0) + 0.15)
    return rows, segs, runs, real, ctrl, corr, ok, source


def write(work, rows, segs, runs, real, ctrl, corr, source):
    units, r2u = [], {}
    for j, (a, b) in enumerate(runs):
        if b <= a:
            continue
        units.append(segs[j])
        for ref, _ in rows[a:b]:
            r2u[ref] = len(units) - 1
    src = dict(source, mode='section by length and proper names', ref_composition=['line'])
    return write_aligned(
        OUT, 'cop', work, units, r2u,
        attribution=f"{source['translator']}, {source['title']} ({source['year']}), public domain",
        license='Public domain',
        sources=[src], confidence='medium', approximate=True, tess_refs=[r for r, _ in rows],
        name_check={'name_check_hit_rate': round(real[0], 3), 'name_check_n': real[1],
                    'control_name_hit_rate': round(ctrl[0] or 0, 3),
                    'length_correlation': round(corr or 0, 3)},
        verified_by='proper names held out from the aligner',
        notes='Section-level: each unit is two or three sentences paired with the run of Coptic '
              'manuscript lines the alignment placed it against. Budge prints the Coptic text and '
              'the translation apart, with folio marks that our line numbers do not carry.')


if __name__ == '__main__':
    for w in sys.argv[1:] or list(WORKS):
        rows, segs, runs, real, ctrl, corr, ok, source = run(w)
        if not ok:
            print('  NOT WRITTEN: the held-out name check does not clear its control')
            continue
        print('  wrote', write(w, rows, segs, runs, real, ctrl, corr, source))
