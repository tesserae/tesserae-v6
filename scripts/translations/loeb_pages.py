#!/usr/bin/env python3
"""Shared parts of the Loeb running-header aligners for translations of 1931 to 1963.

Part F of the 2026-10-24 translation batch. The method is the one the Statius,
Aristophanes and Ovid aligners use (a Loeb page of English carries a running
header giving the exact source range it translates), with the pieces every
volume needs kept here once: tolerant number reading, the extraction of a page's
English from an OCR column that also holds the facing source page and the
apparatus, repair of misread header numbers by the page's own plausible length,
the two measured checks, and the writer.

Wrong English beside right source text is invisible to the reader who needs the
English, so nothing is written unless a check vouches for it
(scripts/translations/README.md, "Why this is delicate").
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

OCR_DIGIT = str.maketrans({'O': '0', 'o': '0', 'l': '1', 'I': '1', 'S': '5',
                           'B': '8', 'Z': '2', 'q': '9', 'G': '6', 'T': '1'})
NUM = r'[0-9OolISBZqGT]{1,4}'
GREEK_RE = re.compile(r'[Ͱ-Ͽἀ-῿]')
STOP_EN = set('''the and of to in a is that was his he for with as her on at by
from they their she it not be but had have this which him who were are all so
or when what there its'''.split())
ROMAN_VAL = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}


def digits(s):
    s = s.translate(OCR_DIGIT)
    return int(s) if s.isdigit() else None


def roman(s):
    """Roman numeral to int, tolerant of the usual OCR slips; None if hopeless."""
    s = s.upper().replace('1', 'I').replace('|', 'I').replace('U', 'I')
    s = s.replace('T', 'I').replace('Y', 'V')
    if not s or any(c not in ROMAN_VAL for c in s):
        return None
    tot = 0
    for i, c in enumerate(s):
        v = ROMAN_VAL[c]
        if i + 1 < len(s) and ROMAN_VAL[s[i + 1]] > v:
            tot -= v
        else:
            tot += v
    return tot


def roman_in(s, lo, hi):
    """Roman numeral within [lo, hi], trying the OCR slips (L read for I, and so on)."""
    for cand in (s, s.replace('L', 'I'), s.replace('l', 'I'), s.replace('L', 'I').replace('V', 'Y')):
        v = roman(cand)
        if v is not None and lo <= v <= hi:
            return v
    return None


def english_ratio(text):
    words = re.findall(r"[A-Za-z']+", text.lower())
    if not words:
        return 0.0
    return sum(1 for w in words if w in STOP_EN) / len(words)


FOOT = re.compile(r'^\s*[<*†‡§¶^~¹²³]')


def page_english(body_lines, stop_re=None, min_ratio=0.18, min_block=0, cut_footnotes=False):
    """The English of one page out of the OCR column that follows its header.

    Stops at `stop_re` (the facing source page's running head or the start of
    the notes), drops lines that carry source-language letters, bare numbers and
    short all-capital furniture, splits into blocks at blank lines, and keeps a
    block only if common English words make up enough of it and it does not open
    with a footnote mark.
    """
    blocks, cur = [], []
    for raw in body_lines:
        if stop_re and stop_re.search(raw):
            break
        line = raw.strip()
        if not line:
            if cur:
                blocks.append(cur)
                cur = []
            continue
        if len(GREEK_RE.findall(line)) >= 2:
            continue
        if re.fullmatch(r'[\dIVXLCivxlc .,\-–*]+', line):
            continue
        letters = re.sub(r'[^A-Za-z]', '', line)
        if letters and letters.isupper() and len(line) < 60:
            continue
        cur.append(line)
    if cur:
        blocks.append(cur)
    kept = []
    for b in blocks:
        text = ' '.join(b)
        if cut_footnotes and kept and len(text) < 900 and \
                re.match(r'^[\"\'\u201c\u2018*^\u2022\u00b0\u00b7\u2020\u2021\d]', text.strip()):
            break           # the footnotes begin (a short block opening with a mark or a number)
        if len(text) < min_block:
            continue
        if FOOT.match(text):
            continue
        if english_ratio(text) < min_ratio:
            continue
        kept.append(b)
    paras = []
    for b in kept:
        t = ' '.join(b)
        t = re.sub(r'(\w)- (\w)', r'\1\2', t)
        t = re.sub(r'[*^~]+', '', t)
        t = re.sub(r'\s+([,.;:?!])', r'\1', t)
        t = re.sub(r'\bVOL\. [IVXl1]+\.? ?[A-Z]? ?\d+\b', '', t)
        paras.append(re.sub(r'\s{2,}', ' ', t).strip())
    return ' '.join(paras).strip()


def load_refs(path, depth):
    """{numeric tuple (last `depth` numbers): full ref} for one .tess file."""
    refs = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'^<([^>]*)>', line)
            if not m:
                continue
            ref = m.group(1).strip()
            nums = re.findall(r'(\d+)', ref)
            if len(nums) < depth:
                continue
            refs.setdefault(tuple(int(x) for x in nums[-depth:]), ref)
    return refs


def source_for(path):
    out = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'^<([^>]*)>\s*(.*)$', line)
            if m:
                out.setdefault(m.group(1).strip(), m.group(2).strip())
    return out


def corr(pairs):
    xs = [len(a) for a, b in pairs if a and b]
    ys = [len(b) for a, b in pairs if a and b]
    n = len(xs)
    if n < 10:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None


def checks(pairs, lang, name_floor=0.25, corr_floor=0.45):
    """(hit, n, r, ok, verified_by) for [(source line, english unit)] pairs."""
    hit, n = V.score(pairs, lang, sample=300)
    r = corr(pairs)
    # the name check abstains on fewer than twenty names (README, "Abstention is not approval")
    by_names = hit is not None and n >= 20 and hit >= name_floor
    by_len = r is not None and r >= corr_floor
    return hit, n, r, (by_names or by_len), ('names' if by_names else 'length correlation')


def contiguity_repair(pages, min_span, max_span, keyfn):
    """Repair misread header numbers by the page's own plausible span.

    Same rule as align_statius.repair: a header with a sane span is believed as
    printed even when it does not follow the previous page (the scan lost the
    page between), an impossible span means a digit was misread and contiguity
    supplies the start, anything still implausible is dropped, and two pages may
    not claim the same line. Returns (pages, repaired, dropped, trimmed).
    pages: list of dicts with keys book, start, end, text.
    """
    fixed = dropped = trimmed = 0
    out, prev_key, prev_end = [], None, None
    for p in pages:
        key = keyfn(p)
        if key != prev_key:
            prev_key, prev_end = key, None
        start, end = p['start'], p['end']
        span = end - start + 1
        if not (min_span <= span <= max_span) and prev_end is not None:
            cand = prev_end + 1
            if min_span <= end - cand + 1 <= max_span:
                start, fixed = cand, fixed + 1
                span = end - start + 1
        if not (min_span <= span <= max_span):
            dropped += 1
            continue
        if prev_end is not None and start <= prev_end:
            trimmed += 1
            start = prev_end + 1
            if start > end:
                dropped += 1
                continue
        q = dict(p)
        q['start'], q['end'] = start, end
        out.append(q)
        prev_end = end
    return out, fixed, dropped, trimmed


def build_units(mapping_pages, refs):
    """mapping_pages: [(key_fn(line)->numeric tuple, start, end, text)] -> (units, ref2u)."""
    units, idx, ref2u = [], {}, {}
    for keyof, start, end, text in mapping_pages:
        if not text:
            continue
        for ln in range(start, end + 1):
            ref = refs.get(keyof(ln))
            if ref and ref not in ref2u:
                if text not in idx:
                    idx[text] = len(units)
                    units.append(text)
                ref2u[ref] = idx[text]
    return units, ref2u


def imprint_license(extra=''):
    return ('Public domain in the United States: published 1931 to 1963 with a '
            'United States imprint and no renewal of the copyright found '
            '(renewal check 2026-10-24). ' + extra).strip()


def unit_corr(units, ref2u, src):
    """Correlation between a unit's English length and the length of the source
    text of the references it covers. For prose in page-sized units this is the
    strong test (a misplaced page puts long English beside short source)."""
    tot = {}
    for ref, i in ref2u.items():
        tot[i] = tot.get(i, 0) + len(src.get(ref, ''))
    pairs = [('x' * tot[i], units[i]) for i in tot if tot[i]]
    return corr(pairs) if len(pairs) >= 10 else None


def drop_marginal(blocks, min_chars=60):
    """Drop short blocks (marginal summaries, stray fragments) from a page."""
    return [b for b in blocks if len(' '.join(b)) >= min_chars]


def chap_values(tok):
    """Chapter numbers a lower-case header numeral might be, given OCR slips
    (i read as r, t, l or 1; ii read as u or n)."""
    t = tok.lower().replace('1', 'i').replace('l', 'i').replace('|', 'i').replace('r', 'i').replace('t', 'i')
    outs = {t, t.replace('n', 'ii'), t.replace('u', 'ii'), t.replace('n', 'iii'),
            t.replace('u', 'ii').replace('n', 'ii'), t.replace('c', 'x')}
    vals = set()
    for o in outs:
        v = roman(o.upper())
        if v and 0 < v < 200:
            vals.add(v)
    return sorted(vals)


def pick_near(vals, prev, back=1, ahead=6):
    """The candidate closest to the previous page's last chapter, within a window."""
    if not vals:
        return None
    if prev is None:
        return vals[0]
    ok = [v for v in vals if prev - back <= v <= prev + ahead]
    return min(ok, key=lambda v: abs(v - prev)) if ok else None
