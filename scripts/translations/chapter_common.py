#!/usr/bin/env python3
# ruff: noqa: E741  (the corpus lines are called `l` in a dozen throwaway loops, as in the other scripts here)
"""Shared helpers for the chapter-level alignments of 2026-10-24 (Part C).

Every per-work script of that batch builds a mapping from our reference tails
(the last word of the tag, for example `3.12.4`) to English text, then calls
`finish()`, which

  1. gives each of our references the unit that covers it,
  2. measures the two checks the README describes (proper names, and the
     length correlation, here taken between the summed length of the source
     lines each unit covers and the length of its English, which is what a
     chapter-level unit can be asked to show),
  3. REFUSES to write when neither check vouches for the file, and
  4. writes the served shape through write_aligned.py and appends one line of
     measurements to $TESSERAE_C_STATS when that is set.

Nothing here installs anything: the output folder is a staging folder.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V                          # noqa: E402
from write_aligned import write_aligned           # noqa: E402

TEXTS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts')
STATS = os.environ.get('TESSERAE_C_STATS')       # a file to append one JSON line of measurements per work to

NAME_FLOOR = 0.30       # README: names under 0.3 ...
LEN_FLOOR = 0.80        # ... and length correlation under 0.8 means refuse
MIN_NAMES = 20          # fewer tested names than this and the name check abstains


def load_work(lang, stem):
    """-> (refs, src, files): our full tags in order (duplicates dropped) and
    the Latin or Greek text of each. Works held whole and in parts are read
    from whichever exists (the whole file, else the parts in numeric order)."""
    base = os.path.join(TEXTS, lang, stem)
    files = [base + '.tess'] if os.path.exists(base + '.tess') else []
    parts = glob.glob(base + '.part.*.tess')
    parts.sort(key=lambda p: [int(x) if x.isdigit() else x
                              for x in re.split(r'(\d+)', os.path.basename(p))])
    if not files:
        files = parts
    refs, src, seen = [], {}, set()
    for f in files:
        for line in open(f, encoding='utf-8', errors='replace'):
            if line.startswith('<') and '>' in line:
                tag, text = line[1:].split('>', 1)
                tag = tag.strip()
                if tag in seen:
                    continue
                seen.add(tag)
                refs.append(tag)
                src[tag] = text.strip()
    return refs, src, files


def tail(tag):
    return tag.split()[-1]


def unit_length_correlation(units, ref_to_unit, src):
    """Pearson r between each unit's English length and the summed length of the
    source lines that unit covers."""
    tot = {}
    for r, u in ref_to_unit.items():
        tot[u] = tot.get(u, 0) + len(src.get(r, ''))
    xs = [tot[u] for u in tot]
    ys = [len(units[u]) for u in tot]
    n = len(xs)
    if n < 10:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return round(num / (dx * dy), 3) if dx and dy else None


def finish(lang, stem, units, ref_to_unit, refs, src, *, out_dir, sources,
           attribution, license, notes=None, mode='chapter', dry=False,
           name_sample=800, exact=False, min_names=MIN_NAMES, extra_evidence=None):
    """Check, then write. Returns the measurement dict (written True/False)."""
    bad = [r for r in ref_to_unit if r not in src]
    if bad:
        raise ValueError(f'{stem}: refs not in our text: {bad[:3]}')
    cov = len(ref_to_unit) / len(refs) if refs else 0.0
    # name check on one pair per source line (our line, its unit's English)
    pairs = [(src[r], units[u]) for r, u in ref_to_unit.items()]
    hit, n = V.score(pairs, lang, sample=name_sample)
    corr = unit_length_correlation(units, ref_to_unit, src)
    rival, rival_n = rival_check(lang, units, ref_to_unit, src)
    names_ok = hit is not None and n >= min_names and hit >= NAME_FLOOR
    len_ok = corr is not None and corr >= LEN_FLOOR and mode != 'proportional'
    ok = (names_ok or len_ok) and cov > 0
    if rival is not None and rival_n >= 10 and rival < 0.5 and mode != 'proportional' and not len_ok:
        ok = False            # (not for proportional allocations, where the length check is circular and neighbours look alike) the English that belongs to a unit does not score best against its own Greek
    lines_per_unit = len(ref_to_unit) / max(1, len(units))
    verified = []
    if names_ok:
        verified.append(f'proper names {hit:.3f} on {n}')
    if len_ok:
        verified.append(f'length correlation {corr:.3f}')
    if extra_evidence:
        verified.append(extra_evidence)
    if rival is not None and rival_n >= 10:
        verified.append(f'rival-unit test: own English scores best for {rival:.2f} of {rival_n} units')
    if mode == 'proportional':
        verified = [v for v in verified if not v.startswith('length correlation')]
        verified.append('chapters allocated by cumulative length, so the length correlation is circular and is not counted')
    if exact:
        verified.insert(0, 'exact citation match')
    rec = {'work': f'{lang}/{stem}', 'coverage': round(cov, 4),
           'translated': len(ref_to_unit), 'refs': len(refs),
           'units': len(units), 'lines_per_unit': round(lines_per_unit, 1),
           'names': hit, 'names_n': n, 'length_corr': corr,
           'rival_own_best': None if rival is None else round(rival, 3), 'rival_n': rival_n,
           'accepted': bool(ok), 'mode': mode}
    print(f'{lang}/{stem:44s} cov {cov:.4f} ({len(ref_to_unit)}/{len(refs)}) '
          f'units {len(units)} ({lines_per_unit:.1f}/unit) names {hit}/{n} '
          f'len {corr} rival {None if rival is None else round(rival, 2)}/{rival_n} -> ' + ('ok' if ok else 'REFUSED'))
    if ok and not dry:
        conf = 'high' if (names_ok and hit >= 0.5) or (len_ok and corr >= 0.9) else 'medium'
        path = write_aligned(
            out_dir, lang, stem, units, ref_to_unit, attribution=attribution,
            license=license, sources=sources, confidence=conf,
            approximate=(mode != 'exact'), tess_refs=refs,
            name_check={'name_check_hit_rate': hit, 'name_check_n': n,
                        'unit_length_correlation': corr, 'rival_own_best': rival},
            verified_by='; '.join(verified), notes=notes)
        rec['file'] = os.path.basename(path)
    if STATS and not dry:
        os.makedirs(os.path.dirname(os.path.abspath(STATS)), exist_ok=True)
        with open(STATS, 'a') as f:
            f.write(json.dumps(rec) + '\n')
    return rec


def rival_check(lang, units, ref_to_unit, src, max_units=2000, window=3):
    """For every unit, count how many of its source lines hold a proper name that
    appears in the English of each unit, and report the share of units whose OWN
    English scores at least as high as any other unit's (ties count as a win).
    Units within `window` places of the one tested are not rivals: an alignment that
    allocates sections to neighbouring chapters by length expects neighbours to look alike.
    A wrong concordance (ours 11 paired with Taylor 11 when it is Taylor 1) shows up
    here as a collapse, where the plain name check, which only asks whether a name
    appears in its own unit, stays high because common names appear everywhere.
    Returns (share, tested_units) or (None, 0) when too few units can speak."""
    import collections
    if len(units) < 3 or len(units) > max_units:
        return None, 0
    prefix = collections.defaultdict(set)
    for i, t in enumerate(units):
        for e in V.english_stems(t):
            prefix[e[:4]].add(i)
    lines_of = collections.defaultdict(list)
    for r, u in ref_to_unit.items():
        lines_of[u].append(src[r])
    wins = tested = 0
    for u, lines in lines_of.items():
        cnt = collections.Counter()
        names = 0
        for l in lines:
            seen = set()
            for _, c in V.names_in(l, lang):
                for i in prefix.get(c[:4], ()):
                    if (i, c) not in seen:
                        seen.add((i, c))
                        cnt[i] += 1
                names += 1
        if sum(cnt.values()) < 3 or names < 3:
            continue
        tested += 1
        far = [v for i, v in cnt.items() if abs(i - u) > window]
        if cnt.get(u, 0) >= (max(far) if far else 0):
            wins += 1
    return (wins / tested if tested else None), tested


def clean(text):
    """Collapse whitespace; drop bracketed footnote marks like [12]."""
    text = re.sub(r'\[\d+\]', '', text)
    return re.sub(r'\s+', ' ', text).strip()


PERSEUS_WORK = os.environ.get('TESSERAE_PERSEUS_WORK',
                              os.path.expanduser('~/perseus_trans/work'))
_PERSEUS = None


def perseus_records():
    """The Perseus English translations already extracted on this machine
    (extracted6.json): a list of {'meta': {...}, 'chunks': [{'anchors', 'text'}]}."""
    global _PERSEUS
    if _PERSEUS is None:
        _PERSEUS = json.load(open(os.path.join(PERSEUS_WORK, 'extracted6.json')))
    return _PERSEUS


def perseus_find(author, translator_part, title=None, title_eq=None):
    out = []
    for r in perseus_records():
        m = r['meta']
        if m.get('author') != author or translator_part not in (m.get('translator') or ''):
            continue
        if title_eq is not None and m.get('title') != title_eq:
            continue
        if title is not None and title not in (m.get('title') or ''):
            continue
        out.append(r)
    return out


ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
_OCR_ROMAN = str.maketrans({'Y': 'V', 'T': 'I', 'l': 'I', '1': 'I', 'H': 'II', 'n': 'II',
                            'r': 'I', 'L': 'L', 'U': 'V', 'u': 'V', 'N': 'II', ' ': ''})


def roman_ocr(s):
    """Roman numeral with the usual OCR slips repaired (Y for V, l for I, n for II);
    None when it does not parse."""
    s = s.strip(' .,;:').translate(_OCR_ROMAN).upper()
    if not s or any(c not in ROMAN for c in s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN[ch]
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total


def dehyphenate(text):
    """Join words split across lines ('ven- geance' left by the OCR as 'ven-\\ngeance')."""
    return re.sub(r'(\w)-\s*\n\s*([a-z])', r'\1\2', text)


def drop_footnotes(lines):
    """Remove blocks that begin with a footnote mark (' ^ dagger) up to the next blank line."""
    out, skipping = [], False
    for ln in lines:
        s = ln.strip()
        if not s:
            skipping = False
            out.append(ln)
            continue
        if skipping:
            continue
        if re.match(r"^['‘’^†‡°]\s*\S", s) and len(s) > 3:
            skipping = True
            continue
        out.append(ln)
    return out


def roman_to_int(s):
    """Plain roman numeral (no OCR repair); None when it does not parse."""
    s = s.strip(' .').upper()
    if not s or any(c not in ROMAN for c in s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN[ch]
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total


def parse_headed(lines, book_re, chap_re, start=0, stop=None, strip_note=None):
    """Walk a transcription that carries `BOOK <roman>` and `CHAPTER <roman>` headings
    and return {(book, chapter): text}. `book_re` and `chap_re` are compiled patterns
    whose first group is the numeral (roman or digits); `strip_note` is an optional
    pattern for lines to drop (footnote lines, page furniture)."""
    out, book, chap, buf = {}, None, None, []

    def num(g):
        return int(g) if g.isdigit() else roman_to_int(g)

    def flush():
        if book is not None and chap is not None:
            out[(book, chap)] = clean(' '.join(buf))
    for ln in lines[start:stop]:
        m = book_re.match(ln) if book_re else None
        if m:
            flush()
            book, chap, buf = num(m.group(1)), None, []
            continue
        m = chap_re.match(ln)
        if m:
            flush()
            chap, buf = num(m.group(1)), []
            continue
        if chap is not None and not (strip_note and strip_note.match(ln)):
            buf.append(ln.strip())
    flush()
    return out


def roman_str(n):
    out = ''
    for v, s in ((1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'),
                 (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        while n >= v:
            out += s
            n -= v
    return out


def _edit1(a, b):
    """True when a and b differ by at most one inserted, deleted or changed character."""
    if abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) <= 1
    if len(a) > len(b):
        a, b = b, a
    for i in range(len(b)):
        if a == b[:i] + b[i + 1:]:
            return True
    return False


def _is_running_head(s):
    """A page's running head in OCR: mostly capitals, short, often with a page number."""
    t = s.strip()
    letters = [c for c in t if c.isalpha()]
    if not letters or len(t) > 70:
        return False
    return sum(c.isupper() for c in letters) / len(letters) > 0.8 and len(letters) >= 4 and \
        bool(re.search(r'[A-Z]{3,}', t)) and not re.match(r'^[IVXLC]+[.,]\s', t)


_MARK = re.compile(r'^\W{0,3}([A-Za-z0-9]{1,9})\s?[.,;:]\s+(\S.*)$')


def split_chapters_fuzzy(lines, max_skip=2):
    """Chapters of a Bohn-style translation whose OCR has damaged the roman numerals.

    A line opens chapter N when it begins with a short token and a point or comma
    and the token is, within one character, the roman numeral of the chapter the
    chain expects (N = previous + 1), or parses (with the usual OCR slips) to a
    number between N and N + max_skip. Returns ([(number, text)], ok) where ok means
    the numbers rise and none was lost without the text being kept (a lost marker
    merges its chapter into the one before)."""
    chapters, cur, buf = [], None, []

    def flush():
        if cur is not None:
            chapters.append((cur, clean(' '.join(buf))))
    for ln in lines:
        s = ln.rstrip()
        if _is_running_head(s):
            continue
        m = _MARK.match(s)
        n = None
        if m:
            expect = 1 if cur is None else cur + 1
            tok = m.group(1)
            if tok.upper() == roman_str(expect) or (len(tok) >= 2 and _edit1(tok.upper(), roman_str(expect))):
                n = expect
            else:
                p = roman_ocr(tok) if tok.isalpha() or tok.isalnum() else None
                clean_tok = p is not None and roman_str(p) == tok and tok.isalpha()
                if p is not None and tok[0].isupper() and (
                        expect <= p <= expect + max_skip or (clean_tok and len(tok) >= 2 and expect <= p <= expect + 8)):
                    n = p
            if tok == 'I' and expect == 1:
                n = 1
        if n is not None:
            flush()
            cur, buf = n, [m.group(2)]
            continue
        if cur is not None and s.strip() and not s.lstrip().startswith('['):
            buf.append(s)
    flush()
    nums = [n for n, _ in chapters]
    ok = bool(nums) and all(b > a for a, b in zip(nums, nums[1:])) and len(nums) >= 0.6 * nums[-1]
    return chapters, ok



def group_align(g_lens, e_lens, merge_cost=0.6, skip_cost=4.0):
    """Order-preserving alignment of two lists of chapters by length (Gale and Church's
    idea, simplified): each step pairs one Greek chapter with one English one, or two
    Greek with one English, or one Greek with two English, or two with two. Used where
    the translator's chapter count and ours differ by one: the chapters up to and after
    the difference pair one to one and the difference is absorbed where the lengths say
    two chapters on one side are one on the other.

    Returns a list of (greek indices, english indices) groups, in order. The cost of a
    group is the squared log of its English length over the overall English-to-Greek
    ratio times its Greek length, plus `merge_cost` for any group that is not one to one."""
    import math
    n, m = len(g_lens), len(e_lens)
    r = sum(e_lens) / max(1, sum(g_lens))
    INF = float('inf')
    cost = [[INF] * (m + 1) for _ in range(n + 1)]
    back = [[None] * (m + 1) for _ in range(n + 1)]
    cost[0][0] = 0.0
    moves = [(1, 1), (2, 1), (1, 2), (2, 2), (1, 0), (0, 1)]
    for i in range(n + 1):
        for j in range(m + 1):
            c = cost[i][j]
            if c == INF:
                continue
            for di, dj in moves:
                ni, nj = i + di, j + dj
                if ni > n or nj > m:
                    continue
                if di == 0 or dj == 0:
                    cc = c + skip_cost
                else:
                    gs = sum(g_lens[i:ni])
                    es = sum(e_lens[j:nj])
                    x = math.log((es + 30) / (gs * r + 30))
                    cc = c + x * x * 4 + (0 if (di, dj) == (1, 1) else merge_cost)
                if cc < cost[ni][nj]:
                    cost[ni][nj], back[ni][nj] = cc, (i, j)
    groups = []
    i, j = n, m
    while (i, j) != (0, 0):
        pi, pj = back[i][j]
        groups.append((list(range(pi, i)), list(range(pj, j))))
        i, j = pi, pj
    return groups[::-1]


def end_merge_map(g_lens, e_lens, max_odd=3):
    """When the translator's count of chapters (or sections) differs from ours, align the
    two lists by length with group_align and return {greek index: [english indices]}, or
    None when more than `max_odd` groups are other than one to one.

    Every group is a run of neighbouring chapters on each side whose total length agrees
    (two Greek chapters that are one English chapter, or the reverse, or two against two
    where the dividing line falls in a different place). Because the groups partition both
    lists in order, a repaired difference stays local: the chapters before and after the
    group still pair one to one. A book with several such groups is not repaired, since
    the length evidence is then too thin to say where the divisions fall."""
    groups = group_align(g_lens, e_lens)
    odd = [g for g in groups if len(g[0]) != 1 or len(g[1]) != 1]
    if len(odd) > max_odd:
        return None
    mapping = {}
    for a, b in groups:
        for i in a:
            mapping[i] = list(b)
    return mapping
