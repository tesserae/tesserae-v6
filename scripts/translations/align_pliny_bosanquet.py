#!/usr/bin/env python3
"""Pliny the Younger, Letters: books 6 to 10 from Melmoth's translation as revised
by Bosanquet (Bohn's Classical Library), added to Firth for books 1 to 5.

WHY. The installed file covers 47 percent: books 1 to 5 from Firth (1900), and
nothing for books 6 to 10, because Firth's second volume was never digitized on
Project Gutenberg and the Gutenberg Melmoth (PG 2811) is the Harvard Classics
SELECTION, whose numbering for Book 10 drifts (the earlier attempt withdrew it
after a spot-read served the Prusa bath letter under 10.33). The complete
Bohn volume II (Books VI to X, Hinds, Noble and Eldredge) is on the Internet
Archive as lettersofplinyyo00plin.

HOW THE LETTERS ARE PAIRED. Numbers are NOT trusted. The OCR damages headings
(LETTEK, L*, XXL) and Bosanquet renumbered Book 10 into the modern order
(his heading "LETTER IV. [xx.]" carries the old Melmoth number in brackets). So for
each book the English letters, in the order printed, are aligned to the Latin
letters, in the order of the corpus, by a monotone dynamic-programming alignment
whose score for a pair is the proper-name agreement of the two letters plus how
well their lengths fit the book's typical ratio. A skipped letter costs a fixed
penalty. The result is then judged by the same independent checks as every other
alignment: names over all pairs and length correlation per letter, plus the share of
pairs whose position agrees with the printed number.

CLEANING. Running heads ("THE LETTERS OF PLINY. [Book 6."), page numbers, the
letter's heading line, and the translator's footnotes (a block opening with a
symbol, running to the next running head) are removed.

Usage:
    python align_pliny_bosanquet.py --firth PG3234.txt --bohn2 VOL2.txt \\
        --tess texts/la/pliny_the_younger.letters.tess --out OUT.json
"""
import argparse
import json
import math
import os
import re
import sys
from collections import OrderedDict, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V  # noqa: E402

ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}


def roman_to_int(s):
    total, prev = 0, 0
    for ch in reversed(s.strip('. ').upper()):
        v = ROMAN.get(ch)
        if v is None:
            return None
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total or None


def clean_text(lines):
    text = ' '.join(lx.strip() for lx in lines if lx.strip())
    text = re.sub(r'\[\d+\]', '', text)
    return re.sub(r'\s+', ' ', text).strip()


# --- Firth, books 1 to 5 (as align_misc_prose.py read them) -------------------
def parse_firth(path):
    lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
    english, cur, buf = {}, None, []
    for ln in lines:
        m = re.match(r'^(\d+)\.([IVXLC]+)\.?--', ln.strip())
        if m and roman_to_int(m.group(2)):
            if cur:
                english[cur] = clean_text(buf)
            cur, buf = (int(m.group(1)), roman_to_int(m.group(2))), []
            continue
        if re.match(r'^\*\*\* END', ln):
            break
        if cur:
            buf.append(ln)
    if cur:
        english[cur] = clean_text(buf)
    return english


# --- Bohn volume II, books 6 to 10 ----------------------------------------------
BOOK_RE = re.compile(r'^\s*BOOK\s+(VI|VII|VIII|IX|X)\.?\s*$')
HEAD_RE = re.compile(r'^\s*\S{0,3}\s*[LB][EF]TT?[EKBRF]{1,2}\s+\S.*\b(To|TO|Trajan|to Pliny|to Puny)\b')
RUNHEAD_RE = re.compile(r'(THE\s+L[EF]T+[EKRF]*S\s+O[FP]|PLINY\.?\s*\[?\s*Boo|^\s*Letter\s+\d+\.\]|LET[^\s]{0,3}RS\s+OF\s+PLIN)', re.I)
FOOT_START = re.compile(r'^\s*[*†‡§¶|]+\s*\S')


def parse_bohn2(path):
    lines = open(path, encoding='utf-8', errors='ignore').read().split('\n')
    books = OrderedDict()
    book, cur, in_foot = None, None, False
    # start after the title pages
    start = next(i for i, lx in enumerate(lines) if BOOK_RE.match(lx) and 'VI' in lx)
    blocks = []
    buf = []
    for ln in lines[start:] + ['']:
        if ln.strip():
            buf.append(ln)
        elif buf:
            blocks.append(buf)
            buf = []
    for blk in blocks:
        first = blk[0]
        m = BOOK_RE.match(first)
        if m:
            book = {'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10}[m.group(1)]
            books.setdefault(book, [])
            cur, in_foot = None, False
            blk = blk[1:]
            if not blk:
                continue
            first = blk[0]
        if book is None:
            continue
        # a running head ends a footnote run; blocks that are only a running head vanish
        head_idx = [i for i, lx in enumerate(blk) if RUNHEAD_RE.search(lx) and len(lx) < 90]
        if head_idx:
            in_foot = False
            blk = [lx for i, lx in enumerate(blk) if i not in head_idx]
            if not blk:
                continue
            first = blk[0]
        if HEAD_RE.match(first):
            in_foot = False
            books[book].append({'heading': first.strip(), 'text': []})
            cur = books[book][-1]
            blk = blk[1:]
            if not blk:
                continue
            first = blk[0]
        if FOOT_START.match(first):
            in_foot = True
        if in_foot or cur is None:
            continue
        if re.fullmatch(r'\s*\S{0,3}\s*\d{0,4}\s*', ' '.join(blk)):
            continue
        cur['text'].append(' '.join(blk))
    out = {}
    for b, letters in books.items():
        out[b] = [(e['heading'], clean_text(e['text'])) for e in letters]
    return out


# --- the clean text of the same translation, where the Gutenberg selection has it ----
def parse_pg2811(path):
    """Letters of the Harvard Classics selection of Melmoth/Bosanquet (Project
    Gutenberg 2811): the same translation as the Bohn volume, typed rather than
    OCR'd, for the letters it holds. Returns [text]."""
    lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
    # the body starts at the second "I -- To ..." (the first is the contents list)
    starts = [i for i, lx in enumerate(lines) if re.match(r'^I -- To SEPT', lx.strip())]
    body = lines[starts[-1] if len(starts) > 1 else starts[0]:]
    out, buf = [], None
    for ln in body:
        if re.match(r'^FOOTNOTES', ln.strip()):
            if buf is not None:
                out.append(buf)
            buf = None
            continue
        if re.match(r'^[IVXLC]+ -- ', ln.strip()):
            if buf is not None:
                out.append(buf)
            buf = []
            continue
        if buf is not None:
            buf.append(ln)
    if buf is not None:
        out.append(buf)
    texts = []
    for b in out:
        t = clean_text(b)
        t = re.sub(r'\[\d{1,4}\]', '', t)
        if len(t) > 80:
            texts.append(re.sub(r'\s+', ' ', t).strip())
    return texts


def norm_key(t):
    return re.sub(r'[^a-z]', '', t.lower())


def clean_from_pg(letters, pg_texts, log):
    """Replace OCR text by the typed text of the same letter when the two agree on
    the opening and on length. Returns the number replaced."""
    import difflib
    keys = [(norm_key(t)[:300], t) for t in pg_texts]
    n = 0
    for k, t in list(letters.items()):
        kk = norm_key(t)[:300]
        best = max(keys, key=lambda kv: difflib.SequenceMatcher(None, kk, kv[0]).quick_ratio())
        r = difflib.SequenceMatcher(None, kk, best[0]).ratio()
        if r >= 0.72 and 0.5 <= len(best[1]) / max(1, len(t)) <= 1.5:
            letters[k] = best[1]
            n += 1
    return n


def load_tess(path):
    refs = []
    order = OrderedDict()
    for line in open(path, encoding='utf-8', errors='ignore'):
        m = re.match(r'<(pliny_the_younger\. Letters (\d+)\.(\d+)([A-Z]?)\.(\d+))>\s*(.*)', line)
        if m:
            # a letter the Latin edition splits ("10.3A", "10.3B") is its own letter
            lid = int(m.group(3)) if not m.group(4) else m.group(3) + m.group(4)
            refs.append((m.group(1), int(m.group(2)), lid, m.group(6)))
    for ref, b, lx, text in refs:
        order.setdefault((b, lx), []).append(text)
    return refs, order


def direction_of_english(heading):
    """Book 10 alternates Pliny to Trajan and Trajan to Pliny; the Bohn heading says which."""
    h = re.sub(r'\s+', ' ', heading)
    if re.search(r'Trajan\s+to\s+P', h, re.I) or re.search(r'Trajan to', h):
        return 'T'
    return 'P'


def direction_of_latin(first_line):
    return 'T' if first_line.strip().lower().startswith('traian') else 'P'


def heading_numeral(h):
    m = re.match(r'^\s*\S{0,3}\s*[LB][EF]TT?[EKBRF]{1,2}\s+([IVXLCl1!*]+)', h)
    if not m:
        return None
    t = m.group(1).replace('l', 'I').replace('1', 'I').replace('!', 'I').replace('*', '')
    return roman_to_int(t)


SALUTATION = {'plinius', 'plinio', 'traiano', 'traianus', 'imperatori', 'traianum', 'caesar', 'domine', 'imperator'}


def letter_names(latin):
    """Distinct proper-name stems of a Latin letter (salutation words left out)."""
    out = {}
    for w, c in V.names_in(latin, 'la'):
        if w.lower() not in SALUTATION:
            out[c] = w
    return list(out)


def name_hits(stems_latin, english_stems):
    n = 0
    for c in stems_latin:
        sc = V.skel(c)
        for e in english_stems:
            if e[:4] == c[:4] or (len(c) >= 5 and len(e) >= 5 and e[:5] == c[:5]):
                n += 1
                break
            se = V.skel(e)
            if len(sc) >= 3 and len(se) >= 3 and se[:3] == sc[:3]:
                n += 1
                break
    return n


def heading_numeral_candidates(h):
    """All integers the OCR'd numeral of a heading could stand for: the OCR reads a
    final I as L (XXL for XXI), l, 1, ! or | for I, and drops letters."""
    m = re.match(r'^\s*\S{0,3}\s*[LB][EF]TT?[EKBRF]{1,2}\s+([IVXLCl1!|*]+)', h)
    if not m:
        return set()
    t = m.group(1).replace('l', 'I').replace('1', 'I').replace('!', 'I').replace('|', 'I').replace('*', '')
    out = set()
    for cand in {t, re.sub(r'L$', 'I', t), re.sub(r'L(?=[IVX])', 'I', t), re.sub(r'IL$', 'II', t)}:
        v = roman_to_int(cand)
        if v:
            out.add(v)
    return out


def pair_score(latin, english, r0):
    hit, n = V.score([(latin, english)], 'la', sample=500)
    name = hit if (hit is not None and n >= 1) else 0.35
    ratio = len(english) / max(1, len(latin))
    fit = 1.0 - min(1.0, abs(math.log(max(ratio, 1e-6) / r0)) / 1.2)
    return 1.6 * name + 0.9 * fit


def numeral_pairs(lat, eng):
    """Books 6 to 9: Bosanquet and the Latin edition number the letters alike, so a
    heading whose OCR'd numeral reads as the number of a Latin letter pairs with it.
    The pairs must run in increasing order (the longest increasing run is kept) and
    each English letter's length must fit its Latin letter's. Returns [(i, j)]."""
    ids = {int(re.match(r'\d+', str(lx)).group()): i for i, (lx, _) in enumerate(lat)
           if not isinstance(lx, str)}
    tot_l = sum(len(t) for _, t in lat)
    tot_e = sum(len(t) for _, t in eng)
    r0 = tot_e / max(1, tot_l)
    cand = []
    for j, (h, t) in enumerate(eng):
        for c in sorted(heading_numeral_candidates(h)):
            if c in ids:
                i = ids[c]
                ratio = len(t) / max(1, len(lat[i][1]))
                if 0.4 * r0 <= ratio <= 2.5 * r0:
                    cand.append((j, i))
                    break
    # longest strictly increasing (j, i) run
    best = []
    for k, (j, i) in enumerate(cand):
        best.append((1, None))
        for m in range(k):
            if cand[m][0] < j and cand[m][1] < i and best[m][0] + 1 > best[k][0]:
                best[k] = (best[m][0] + 1, m)
    if not cand:
        return []
    end = max(range(len(cand)), key=lambda k: best[k][0])
    chain = []
    k = end
    while k is not None:
        chain.append((cand[k][1], cand[k][0]))
        k = best[k][1]
    return list(reversed(chain))


def dp_align(lat, eng, gap=0.55, ldir=None, edir=None):
    """Global monotone alignment of two lists; returns list of (i, j) matches."""
    n, m = len(lat), len(eng)
    tot_l = sum(len(t) for _, t in lat)
    tot_e = sum(len(t) for _, t in eng)
    r0 = tot_e / max(1, tot_l)
    S = [[pair_score(lat[i][1], eng[j][1], r0) for j in range(m)] for i in range(n)]
    if ldir and edir:
        for i in range(n):
            for j in range(m):
                if ldir[i] != edir[j]:
                    S[i][j] -= 6.0     # a Pliny letter can never be Trajan's reply
    NEG = -1e9
    dp = [[NEG] * (m + 1) for _ in range(n + 1)]
    bk = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            if dp[i][j] == NEG:
                continue
            if i < n and j < m:
                v = dp[i][j] + S[i][j]
                if v > dp[i + 1][j + 1]:
                    dp[i + 1][j + 1], bk[i + 1][j + 1] = v, 'd'
            if i < n:
                v = dp[i][j] - gap
                if v > dp[i + 1][j]:
                    dp[i + 1][j], bk[i + 1][j] = v, 'u'
            if j < m:
                v = dp[i][j] - gap
                if v > dp[i][j + 1]:
                    dp[i][j + 1], bk[i][j + 1] = v, 'l'
    i, j, pairs = n, m, []
    while i > 0 or j > 0:
        t = bk[i][j]
        if t == 'd':
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif t == 'u':
            i -= 1
        else:
            j -= 1
    return list(reversed(pairs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--firth', required=True)
    ap.add_argument('--bohn2', required=True)
    ap.add_argument('--pg2811', default=None, help='Gutenberg 2811 text, used to clean the OCR where it holds the same letter')
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--report', default=None)
    args = ap.parse_args()

    firth = parse_firth(args.firth)
    bohn = parse_bohn2(args.bohn2)
    refs, order = load_tess(args.tess)

    letter_text = {}      # (book, letter) -> english
    letter_src = {}
    for k, t in firth.items():
        if t and 1 <= k[0] <= 5:
            letter_text[k] = t
            letter_src[k] = 0
    report = []
    for b in range(6, 11):
        lat = [(lx, ' '.join(order[(bb, lx)])) for (bb, lx) in order if bb == b]
        eng = [(h, t) for h, t in bohn.get(b, []) if len(t) > 40]
        eng_stems = [V.english_stems(t) for _, t in eng]
        ldir = edir = None
        if b == 10:
            ldir = [direction_of_latin(order[(10, lx)][0]) for lx, _ in lat]
            edir = [direction_of_english(h) for h, _ in eng]
        dp_pairs = dp_align(lat, eng, ldir=ldir, edir=edir)
        num_pairs = numeral_pairs(lat, eng) if b != 10 else []
        pairs = list(num_pairs)
        used_i = {i for i, _ in pairs}
        used_j = {j for _, j in pairs}
        # pairs from the order search are added where the numeral pass has none, if the
        # printed number agrees, or the pair sits between two numbered pairs that are
        # adjacent to it in both lists (a damaged heading inside a verified run)
        dp_ok = {}
        for k, (i, j) in enumerate(dp_pairs):
            dp_ok[k] = b != 10 and int(re.match(r'\d+', str(lat[i][0])).group()) in heading_numeral_candidates(eng[j][0])
        for k, (i, j) in enumerate(dp_pairs):
            if i in used_i or j in used_j:
                continue
            nb = (b != 10 and 0 < k < len(dp_pairs) - 1 and dp_ok[k - 1] and dp_ok[k + 1]
                  and dp_pairs[k - 1][0] == i - 1 and dp_pairs[k - 1][1] == j - 1
                  and dp_pairs[k + 1][0] == i + 1 and dp_pairs[k + 1][1] == j + 1)
            if b != 10 and (dp_ok[k] or nb):
                pairs.append((i, j))
                used_i.add(i)
                used_j.add(j)
        if b == 10:
            pairs = list(dp_pairs)
        kept = by_num = by_names = by_run = 0
        anchors = []
        if b == 10:
            for k, (i, j) in enumerate(pairs):
                ln = letter_names(lat[i][1])
                hits_own = name_hits(ln, eng_stems[j])
                others = max((name_hits(ln, eng_stems[m]) for m in range(len(eng)) if m != j), default=0)
                # book 10 is reordered by Bosanquet against the Latin edition, so the
                # printed number cannot vouch. A letter's own names can: at least three turn
                # up in its English, and at least two more than in any other English letter
                if len(ln) >= 3 and hits_own >= 3 and hits_own >= 0.6 * len(ln) and hits_own >= others + 2:
                    anchors.append(k)
        accepted = {}
        for k in anchors:
            accepted[k] = 'names'
        # Between two name-verified anchors, every pair of the order search is kept only
        # if the whole stretch runs in step in both lists (each step one letter on each side),
        # because then no letter can have been moved inside it.
        for a1, a2 in zip(anchors, anchors[1:]):
            seg = pairs[a1:a2 + 1]
            if all(seg[t + 1][0] == seg[t][0] + 1 and seg[t + 1][1] == seg[t][1] + 1 for t in range(len(seg) - 1)):
                for k in range(a1, a2 + 1):
                    accepted.setdefault(k, 'run')
        for k, (i, j) in enumerate(pairs):
            lid = lat[i][0]
            if b != 10:
                letter_text[(b, lid)] = eng[j][1]
                letter_src[(b, lid)] = 1
                kept += 1
                by_num += 1
            elif k in accepted:
                letter_text[(b, lid)] = eng[j][1]
                letter_src[(b, lid)] = 1
                kept += 1
                if accepted[k] == 'names':
                    by_names += 1
                else:
                    by_run += 1
        report.append((b, len(lat), len(eng), len(pairs), kept))
        print(f'book {b}: latin letters {len(lat)}, english letters {len(eng)}, order search paired {len(pairs)}, '
              f'kept {kept} (vouched by printed number {by_num}, by names {by_names}, by an in-step run between two name-vouched letters {by_run})')

    if args.pg2811:
        six_ten = {k: v for k, v in letter_text.items() if letter_src[k] == 1}
        n_clean = clean_from_pg(six_ten, parse_pg2811(args.pg2811), None)
        letter_text.update(six_ten)
        print(f'letters of books 6-10 replaced by the typed Gutenberg text of the same translation: {n_clean} of {len(six_ten)}')
    units, unit_src, unit_of, ref_to_unit = [], [], {}, {}
    for ref, b, lx, latin in refs:
        t = letter_text.get((b, lx))
        if not t:
            continue
        if (b, lx) not in unit_of:
            unit_of[(b, lx)] = len(units)
            units.append(t)
            unit_src.append(letter_src[(b, lx)])
        ref_to_unit[ref] = unit_of[(b, lx)]
    pairs_all = [(latin, units[ref_to_unit[ref]]) for ref, b, lx, latin in refs if ref in ref_to_unit]
    score = V.score(pairs_all, 'la', sample=900)
    per_book = {}
    for bk in range(1, 11):
        pb = [(latin, units[ref_to_unit[ref]]) for ref, b, lx, latin in refs
              if b == bk and ref in ref_to_unit]
        per_book[bk] = V.score(pb, 'la', sample=600) if pb else (None, 0)
    xs, ys = [], []
    byl = defaultdict(int)
    for ref, b, lx, latin in refs:
        if ref in ref_to_unit:
            byl[(b, lx)] += len(latin)
    for (b, lx), n in byl.items():
        xs.append(n)
        ys.append(len(letter_text[(b, lx)]))
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    corr = sum((a - mx) * (c - my) for a, c in zip(xs, ys)) / (
        (sum((a - mx) ** 2 for a in xs) * sum((c - my) ** 2 for c in ys)) ** 0.5)
    sources = [{
        'translator': 'John B. Firth', 'year': 1900,
        'title': 'The Letters of the Younger Pliny (Books 1-5)',
        'publisher': 'Walter Scott / Project Gutenberg 3234',
        'mode': 'exact', 'ref_composition': ['book', 'letter'],
        'source_url': 'https://www.gutenberg.org/ebooks/3234',
    }, {
        'translator': 'William Melmoth, revised by F. C. T. Bosanquet', 'year': 1900,
        'title': 'The Letters of Pliny the Younger (Books 6-10), Bohn\'s Classical Library',
        'publisher': 'Hinds, Noble and Eldredge, New York (the Bohn text as revised by Bosanquet)',
        'mode': 'exact', 'ref_composition': ['book', 'letter'],
        'source_url': 'https://archive.org/details/lettersofplinyyo00plin',
    }]
    out = {
        'tess_work': 'la/pliny_the_younger.letters', 'language': 'la',
        'n_tess_refs': len(refs), 'n_translated': len(ref_to_unit),
        'coverage': round(len(ref_to_unit) / len(refs), 4),
        'mean_source_lines_per_translation_unit': round(len(ref_to_unit) / len(units), 1),
        'alignment_confidence': 'high' if score[0] >= 0.5 else 'medium',
        'name_check_hit_rate': score[0], 'name_check_n': score[1],
        'name_check_by_book': {str(k): v[0] for k, v in per_book.items()},
        'length_correlation': round(corr, 3), 'verified_by': 'names',
        'sources': sources,
        'license': 'Public domain: Firth 1900, Melmoth/Bosanquet (Bohn) 1878.',
        'attribution': 'J. B. Firth (books 1-5, via Project Gutenberg); William Melmoth, revised by '
                       'F. C. T. Bosanquet (books 6-10, Bohn, via the Internet Archive)',
        'n_units_stored': len(units), 'units': units, 'unit_sources': unit_src,
        'ref_to_unit': ref_to_unit,
    }
    json.dump(out, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'refs {len(refs)} translated {len(ref_to_unit)} coverage {out["coverage"]:.4f} units {len(units)}')
    print('names', score, 'length_r (per letter)', round(corr, 3))
    print('names by book', {k: (None if v[0] is None else round(v[0], 2), v[1]) for k, v in per_book.items()})
    missing = sorted({(b, lx) for (b, lx) in order if (b, lx) not in letter_text}, key=lambda x: (x[0], str(x[1])))
    print('letters with no English:', missing)


if __name__ == '__main__':
    main()
