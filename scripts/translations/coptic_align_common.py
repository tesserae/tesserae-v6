#!/usr/bin/env python3
"""Shared checks and a length-based aligner for the Coptic translation builds.

Coptic has no capital letters, so proper_names.py cannot find a name on the
Coptic side. The name check here works the other way round: take the capitalized
names of the ENGLISH unit, fold them to a consonant skeleton, and look for that
skeleton inside the consonant skeleton of the Coptic verse it was paired with
(Coptic writes Greek names in Greek spelling: Nabuchodonosor appears as
ⲛⲁⲃⲟⲩⲭⲟⲇⲟⲛⲟⲥⲟⲣ). The same test is run on a deliberately displaced pairing as a
control, and the pairing is believed only where the real rate clears the control.

The length check is the one README.md describes: do longer Coptic verses get
longer English? A displaced pairing is measured the same way.

The aligner is the textbook length-based one (Gale and Church 1993): within one
chapter, dynamic programming over verse lengths allows one-to-one, one-to-two,
two-to-one and unmatched verses, so a chapter whose two traditions divide the
verses differently is still paired by content and never by number alone.
"""
import math
import re
import unicodedata

COP = {
    'ⲁ': 'a', 'ⲃ': 'b', 'ⲅ': 'g', 'ⲇ': 'd', 'ⲉ': 'e', 'ⲋ': 's', 'ⲍ': 'z', 'ⲏ': 'e',
    'ⲑ': 't', 'ⲓ': 'i', 'ⲕ': 'k', 'ⲗ': 'l', 'ⲙ': 'm', 'ⲛ': 'n', 'ⲝ': 'ks', 'ⲟ': 'o',
    'ⲡ': 'p', 'ⲣ': 'r', 'ⲥ': 's', 'ⲧ': 't', 'ⲩ': 'u', 'ⲫ': 'p', 'ⲭ': 'k', 'ⲯ': 'ps',
    'ⲱ': 'o', 'ϣ': 'sh', 'ϥ': 'f', 'ϧ': 'k', 'ϩ': 'h', 'ϫ': 'k', 'ϭ': 'k', 'ϯ': 't',
}
FOLD = str.maketrans({'c': 'k', 'q': 'k', 'g': 'k', 'd': 't', 'b': 'p', 'v': 'p', 'f': 'p',
                      'z': 's', 'x': 's', 'j': 'k', 'y': 'i', 'w': 'u'})
STOPCAP = set('''the and but for with from that this than then when where who whom whose which what
while into unto upon down over under after before through against among his her its our your their
them they thee thou hath hast doth did was were been being not nor yet all any some such more most
only very much many one two three said say says now here there thus therefore because since though
although lord god king son behold wherefore truly hear thus saith let but and also then so for'''.split())


def cop_skeleton(text):
    """Consonant skeleton of a Coptic line, folded."""
    out = []
    for ch in unicodedata.normalize('NFC', text):
        t = COP.get(ch)
        if t is None:
            lo = ch.lower()
            t = COP.get(lo, '')
        out.append(t)
    s = ''.join(out).translate(FOLD)
    s = s.replace('sh', 's').replace('ks', 's').replace('ps', 'ps')
    return re.sub(r'[aeiouh]', '', s)


def eng_name_skeletons(text):
    names = []
    words = re.findall(r"[A-Za-z']+", text)
    for i, w in enumerate(words):
        if i == 0 or not w[0].isupper() or len(w) < 5 or w.lower() in STOPCAP:
            continue
        s = w.lower().replace('ph', 'p').replace('th', 't').replace('ch', 'k').replace('sh', 's')
        s = s.translate(FOLD)
        s = re.sub(r'[aeiouh]', '', s)
        s = re.sub(r'(.)\1+', r'\1', s)
        if len(s) >= 3:
            names.append(s[:4])
    return names


def name_rate(pairs, sample=400):
    """Share of English units with at least one name whose skeleton occurs in the Coptic line."""
    tested = hits = 0
    for cop, eng in pairs:
        ns = eng_name_skeletons(eng)
        if not ns:
            continue
        sk = re.sub(r'(.)\1+', r'\1', cop_skeleton(cop))
        tested += 1
        if any(n in sk or n[:3] in sk for n in ns):
            hits += 1
        if tested >= sample:
            break
    return (hits / tested if tested else None), tested


def length_corr(pairs, min_chars=15):
    real = [(a, b) for a, b in pairs if a and b and len(a) >= min_chars]
    if len(real) < 10:
        return None
    xs = [len(a) for a, _ in real]
    ys = [len(b) for _, b in real]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None


def displaced(pairs, shift=7):
    """Control: the same Coptic lines paired with English from `shift` places along."""
    n = len(pairs)
    if n <= shift:
        return []
    return [(pairs[i][0], pairs[(i + shift) % n][1]) for i in range(n)]


def _cost(lc, le, ratio, var=6.8):
    """Gale-Church style cost of aligning Coptic length lc with English length le."""
    if lc == 0 and le == 0:
        return 0.0
    mean = (lc + le / ratio) / 2.0
    if mean == 0:
        return 0.0
    delta = (le - lc * ratio) / math.sqrt(mean * ratio * var + 1e-9)
    return delta * delta / 2.0 + math.log(2.0) + 0.0  # monotone in |delta|


PRIOR = {(1, 1): 0.0, (1, 0): 5.5, (0, 1): 5.5, (1, 2): 2.6, (2, 1): 2.6, (2, 2): 4.0,
         (1, 3): 5.0, (3, 1): 5.0, (1, 4): 6.5, (4, 1): 6.5, (1, 5): 8.0, (5, 1): 8.0}


def gale_church(cl, el, ratio, free_ends=False, extra=None):
    """cl, el: lists of lengths. Returns list of (i0, i1, j0, j1) spans.

    extra(i, j), if given, adds a cost to any move that pairs Coptic line i with English
    verse j (a prior from the verse numbers, where they are trusted).

    With free_ends the English side may start and stop anywhere: the Coptic is a
    fragment of the chapter, and English verses before and after it cost nothing.
    The spans then cover all of the Coptic and only the English between the ends.
    """
    n, m = len(cl), len(el)
    INF = 1e18
    best = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    best[0][0] = 0.0
    if free_ends:
        for j in range(m + 1):
            best[0][j] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            b = best[i][j]
            if b >= INF:
                continue
            for (di, dj), pen in PRIOR.items():
                ni, nj = i + di, j + dj
                if ni > n or nj > m:
                    continue
                c = b + pen + _cost(sum(cl[i:ni]), sum(el[j:nj]), ratio)
                if extra is not None and di and dj:
                    c += extra(i, j)
                if c < best[ni][nj]:
                    best[ni][nj] = c
                    back[ni][nj] = (i, j)
    j = m
    if free_ends:
        j = min(range(m + 1), key=lambda jj: best[n][jj])
    spans, i = [], n
    while back[i][j] is not None:
        pi, pj = back[i][j]
        spans.append((pi, i, pj, j))
        i, j = pi, pj
    return spans[::-1]


def number_cost(items, ev, offset, ratio):
    """Pair Coptic verse v with English verse v+offset, one to one. items: [(v, ref, text)],
    ev: {verse: text}. Returns (mean squared log length deviation, pairs, number paired)."""
    pairs, devs = [], []
    for v, ref, t in items:
        e = ev.get(v + offset)
        if e is None or not t:
            continue
        d = math.log((len(e) + 5) / ((len(t) + 5) * ratio))
        devs.append(d * d)
        pairs.append((ref, t, e))
    if not devs:
        return None, [], 0
    return sum(devs) / len(devs), pairs, len(devs)
