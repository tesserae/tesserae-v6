#!/usr/bin/env python3
"""Cut our Persian line files into poems, and cut the English books into poems, so the two
lists can be matched (persian_semantic_common.py)."""
import re
import unicodedata


def _end(t, n=2):
    t = unicodedata.normalize('NFKC', t).replace('‌', '')
    t = re.sub(r'[^؀-ۿ]', '', t)
    t = re.sub(r'[ً-ٰٟ]', '', t)
    return t[-n:]


def _csl(a, b):
    """Length of the common suffix of two rhyme tails (the last four letters of each line)."""
    n = 0
    for x, y in zip(reversed(a), reversed(b)):
        if x != y:
            break
        n += 1
    return n


def rubai_groups(lines):
    """Segment hemistich lines into quatrains of 4 lines (3 or 5 where the rhyme says so).
    A quatrain rhymes a a x a: lines 1, 2 and 4 end alike. Returns [(first, last+1)]."""
    n = len(lines)
    tails = [_end(t, 4) for t in lines]
    INF = 1e9
    best = [INF] * (n + 1)
    back = [0] * (n + 1)
    best[0] = 0.0
    for i in range(n):
        if best[i] >= INF:
            continue
        for size in (4, 3, 5):
            j = i + size
            if j > n:
                continue
            if size == 3:
                cost = 4.0 + (0 if _csl(tails[i], tails[i + 1]) >= 1 else 2.0)
            else:
                g = tails[i:j]
                s = (min(_csl(g[0], g[1]), 2) + min(_csl(g[1], g[3 if size >= 4 else 2]), 2)) / 4.0
                cost = (1 - s) * 3.0 + (0 if size == 4 else 4.0)
            if best[i] + cost < best[j]:
                best[j] = best[i] + cost
                back[j] = i
    out, j = [], n
    while j > 0:
        i = back[j]
        out.append((i, j))
        j = i
    return out[::-1]


_ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}


def roman_value(s):
    s = s.upper().replace('1', 'I').replace(' ', '').strip('.,')
    if not s or any(c not in _ROMAN for c in s):
        return None
    total = 0
    for k, c in enumerate(s):
        v = _ROMAN[c]
        total += -v if k + 1 < len(s) and _ROMAN[s[k + 1]] > v else v
    return total


def english_quatrains(path, first_line, stop_line):
    """Whinfield 1882: a Roman numeral line, then four lines of verse, then the source mark
    ("n. 13, L."). The scan sometimes loses a numeral, wraps a long line, or leaves a stray
    mark, so each block is cleaned and then cut into groups of four lines. A block whose
    clean line count is not a multiple of four is dropped, not guessed.
    Returns [(numeral value or None, text)]."""
    lines = open(path, encoding='utf-8', errors='replace').read().split('\n')[first_line:stop_line]
    num = re.compile(r'^\s*([IVXLCivxlc1lo ]{1,10})[a-z]?[.,]?\s*$')
    junk = re.compile(r'QUATRAIN|QUATRAIK|^\s*\d{1,3}\s*$|^[A-Za-z]{1,3}\.?\s*$|^[nNxXlLbB.,\d\s\-i]{1,14}$|\bL\.\s*$|^\W{1,3}$')
    cite = re.compile(r'^[NnXxMm]?\.?\s*\d+[, ].*[LB]\.?\s*$|^[A-Z]\.?(\s*[A-Z]\.)*$')
    blocks, cur = [], None
    for raw in lines:
        t = re.sub(r'\s+', ' ', raw.strip())
        if re.search(r'N\s*0\s*T\s*E\s*S', t):
            break
        if num.match(t) and len(t) <= 11 and re.search(r'[IVXLCivxlc]', t):
            cur = [t, []]
            blocks.append(cur)
            continue
        if cur is None or not t:
            continue
        letters = [c for c in t if c.isalpha()]
        if letters and len(t) > 12 and sum(c.isupper() for c in letters) > 0.6 * len(letters):
            continue                     # a running head, however the scan spelled it
        if (junk.search(t) and len(t) < 16) or cite.match(t):
            continue
        if len(t) <= 7 and cur[1]:       # a wrapped tail, e.g. "thee,"
            cur[1][-1] += ' ' + t
            continue
        cur[1].append(t)
    out, dropped = [], []
    for numeral, ls in blocks:
        if len(ls) and len(ls) % 4 == 0:
            for k in range(0, len(ls), 4):
                out.append((roman_value(re.sub(r'[a-z]$', '', numeral)) if k == 0 else None, ' / '.join(ls[k:k + 4])))
        elif ls:
            dropped.append((numeral, len(ls)))
    english_quatrains.dropped = dropped
    return out
