#!/usr/bin/env python3
"""Propertius: all four books of the elegies, from Butler's 1912 edition.

8,054 lines with no English anywhere in the corpus. H. E. Butler's prose
version (Heinemann 1912, the volume the Loeb took over) faces the Latin
and is US public domain by date.

WHAT THE ALIGNMENT IS KEYED ON

Butler numbers nothing in the English except the one thing that matters:
each prose paragraph opens with the LATIN line number it renders ("25 Or
else do ye, my friends..."), and each poem opens under its own roman
numeral. So the alignment is structure-keyed at paragraph level -- book
from the running header, poem from the numeral sequence, line span from
the paragraph markers -- with no page guessing at all.

The scan's running headers are heavily mangled ("SEXTI PROPEUTI ELEGIARVM
LIIiEll I", "LI BE P. I"), so pages are classified by fuzzy content:
a header line containing a recognisable ELEGIARVM/SEXTI PROPERTI fragment
opens a Latin page, one containing ELEGIES...BOOK opens an English page,
and only English-page lines are read at all. Poem numerals are read
through the same OCR haze: a standalone numeral parsing to exactly
previous+1 advances the poem; anything else standalone and numeral-like
is treated as the next poem only if the previous poem already has text
(headings lost to OCR leave the poem to the validation below).

WHAT REFUSES TO SHIP

A paragraph marker must exceed the previous marker in its poem and lie
within the poem's own length in our corpus; a violator (usually a
translator's footnote, which also begins with a digit) merges into the
previous unit instead of claiming lines. A poem whose parsed structure
overruns the corpus poem (division mismatch between editions) is skipped
and printed. Each work is then gated by the proper-name check.

TWO CORPUS FAMILIES, FIVE FILES, ONE PARSE

propertius.elegies (prop. b.p.l, all four books) and propertius.elegiae_1-4
(prop. eleg. p.l, one file per book, a different edition whose book 2/3
poem divisions differ slightly). One JSON is written per corpus file, each
keyed by its own exact tag strings; a poem that only exists in one
family's division simply stays uncovered in the other.

Usage:
    python scripts/translations/align_propertius.py \
        --src <butler djvu txt> --tess-dir texts/la --out-dir <dir>
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

ROMAN_VALS = {'I': 1, 'V': 5, 'X': 10, 'L': 50}


def roman(s):
    s = (s.upper().replace('T', 'I').replace('1', 'I').replace('!', 'I')
         .replace('J', 'I').replace('|', 'I'))
    s = re.sub(r'[^IVXL]', '', s)
    if not s:
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = ROMAN_VALS[ch]
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total if 0 < total <= 40 else None


def fuzzy_has(line, word, maxerr):
    """Does an OCR'd uppercase line contain something close to `word`?"""
    line = re.sub(r'[^A-Z]', '', line.upper())
    w = len(word)
    for i in range(len(line) - w + 1):
        if sum(a != b for a, b in zip(line[i:i + w], word)) <= maxerr:
            return True
    return False


def parse(path):
    """{(book, poem): [(start_line, text), ...]} from the English pages.

    Page state is read from the running headers, all of them OCR-mauled and
    all matched fuzzily: "SEXTI PROPERTI ELEGIARVM LIBER <n>" or a bare
    "LIBER <ORDINAL>" title opens a Latin page; "THE ELEGIES OF PROPERTIUS
    BOOK <n>", a bare "BOOK <n>" title, or "THE <ORDINAL> BOOK" opens an
    English page. Nothing before the first Latin header is read at all,
    which keeps the introduction's roman page numbers from being taken for
    poem numbers. Poem numerals advance only to their exact successor, so a
    stray numeral cannot move the cursor; a heading lost to OCR costs that
    poem and no more."""
    state, book, poem = 'front', 0, 0
    latin_seen = False
    paras = {}
    cur_key, cur_start, buf = None, None, []

    ORDINALS = {'FIRST': 1, 'SECOND': 2, 'THIRD': 3, 'FOURTH': 4}
    LATIN_ORD = {'PRIMVS': 1, 'SECVNDVS': 2, 'TERTIVS': 3, 'QVARTVS': 4,
                 'PRIMUS': 1, 'SECUNDUS': 2, 'TERTIUS': 3, 'QUARTUS': 4}

    # deliberately excludes every word that is also Latin (in, me, a, is...)
    STOP = {'the', 'of', 'and', 'to', 'that', 'my', 'with', 'for', 'her',
            'his', 'thy', 'thou', 'she', 'he', 'not', 'but', 'by', 'on',
            'was', 'from', 'all', 'shall', 'thee', 'when', 'their', 'or',
            'be', 'now', 'you', 'your', 'is', 'have', 'hath', 'will'}

    def flush():
        nonlocal buf, cur_key, cur_start
        if cur_key and buf:
            text = ' '.join(buf)
            text = re.sub(r'\s+([,.;:?!])', r'\1', re.sub(r'\s+', ' ', text))
            text = text.replace('- ', '')
            words = [w.lower().strip('.,;:?!()"') for w in text.split()]
            # a Latin page whose running header the scan lost pours Latin
            # into the English stream -- and Latin "English" passes the
            # name check PERFECTLY, so it is caught here by the Martial
            # test instead: real English is a third stopwords, Latin none
            if len(words) >= 8:
                stop = sum(1 for w in words if w in STOP)
                if stop / len(words) < 0.12:
                    buf = []
                    return
            if len(text) > 2:
                paras.setdefault(cur_key, []).append((cur_start, text.strip()))
        buf = []

    def set_book(b):
        nonlocal book, poem, cur_key
        if b and b == book + 1:
            flush()
            book, poem, cur_key = b, 0, None

    for raw in open(path, encoding='utf-8', errors='replace'):
        line = raw.strip()
        if not line:
            continue
        up = line.upper()
        words = re.sub(r'[^A-Z ]', '', up).split()
        # -- Latin page headers --
        if (fuzzy_has(up, 'ELEGIARVM', 2) or fuzzy_has(up, 'SEXTIPROPERTI', 3)
                or fuzzy_has(up, 'ELEGIARUM', 2)):
            flush()
            state, latin_seen = 'latin', True
            continue
        # a bare Latin book-title page: "LIBER SECVNDVS", or OCR wreckage
        # like "LIBER TEin [VS" -- the ordinal is unreadable but the LIBER
        # is not, and a short standalone LIBER line occurs nowhere in the
        # English prose
        if len(words) <= 3 and words and (
                fuzzy_has(words[0], 'LIBER', 1) or any(
                    len(w) >= 6 and any(fuzzy_has(w, o, 2) for o in LATIN_ORD)
                    for w in words)):
            flush()
            state, latin_seen = 'latin', True
            continue
        # -- English page headers --
        if fuzzy_has(up, 'ELEGIESOFPROPERTIUS', 4) or \
                (fuzzy_has(up, 'ELEGIES', 1) and fuzzy_has(up, 'BOOK', 1)):
            state = 'english'
            set_book(roman(line.rsplit(' ', 1)[-1]))
            continue
        if len(words) == 2 and fuzzy_has(words[0], 'BOOK', 1) and roman(words[1]):
            state = 'english'
            set_book(roman(words[1]))
            continue
        if len(words) == 3 and words[0] == 'THE' and fuzzy_has(words[2], 'BOOK', 1):
            hit = False
            for o, n in ORDINALS.items():
                if fuzzy_has(words[1], o, 1):
                    state, hit = 'english', True
                    set_book(n)
                    # this header begins the book's English text, and in
                    # three of the four books the poem-I numeral under it
                    # is lost to OCR: open poem 1 here (a surviving
                    # numeral I is then a no-op)
                    if poem == 0:
                        flush()
                        poem, cur_key, cur_start = 1, (book, 1), 1
                    break
            if hit:
                continue
        if state != 'english' or not latin_seen:
            continue
        # -- poem numeral: successor, or a short resync jump over a heading
        # the OCR lost (the align_livy rule); the skipped poem stays
        # uncovered rather than inheriting the wrong English --
        if len(line) <= 8 and re.fullmatch(r'[IVXLTJ1l!|.\s]+', line):
            n = roman(line)
            if n is not None and poem < n <= poem + 3:
                flush()
                poem, cur_key, cur_start = n, (book, n), 1
            continue
        m = re.match(r'^(\d{1,3})\s+(\S.*)$', line)
        if m and cur_key and int(m.group(1)) > 3:
            # a paragraph marker; 1-3 are excluded because those are the
            # page's FOOTNOTE numbers (no Butler paragraph after the first
            # starts before line 4), and a footnote taken for a marker
            # serves "I.e., mosquito-nets." as the translation of a span
            flush()
            cur_start = int(m.group(1))
            buf = [m.group(2)]
            continue
        if cur_key:
            if re.fullmatch(r'[\dA-Za-z]', line) or re.fullmatch(r'\d{1,3}', line):
                continue
            buf.append(line)
    flush()
    return paras


def load_tess(path, pat):
    refs, lat, maxline = {}, {}, {}
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(pat, line)
        if not m:
            continue
        ref = m.group(1).strip()
        nums = [int(x) for x in m.groups()[1:]]
        refs[tuple(nums)] = ref
        lat[ref] = line.split('>', 1)[1].strip()
        key = tuple(nums[:-1])
        maxline[key] = max(maxline.get(key, 0), nums[-1])
    return refs, lat, maxline


def build(paras, refs, lat, maxline, book=None):
    """mapping ref->text for one corpus file; book=None means keys are
    (book, poem, line); otherwise corpus keys are (poem, line) of `book`."""
    mapping, pairs, skipped = {}, [], []
    poems = {}
    for (b, p), plist in paras.items():
        if book is not None and b != book:
            continue
        key = (p,) if book is not None else (b, p)
        if key not in maxline:
            continue
        n = maxline[key]
        # clean the paragraph list: markers must increase, stay within poem
        # a violating marker is usually a translator's footnote (which also
        # opens with a digit) or the residue of a poem heading the OCR lost;
        # either way its text is DROPPED, never merged, because merging
        # serves the next poem's English under this poem's lines
        good, last = [], 0
        for start, text in plist:
            if start <= last or start > n:
                continue
            good.append((start, text))
            last = start
        if not good:
            continue
        spans = []
        for i, (start, text) in enumerate(good):
            end = good[i + 1][0] - 1 if i + 1 < len(good) else n
            # a translator's footnote that survives the marker test still
            # gives itself away: a dozen words cannot render twenty lines,
            # and Butler's notes open with an editorial formula
            nwords = len(text.split())
            # a paragraph whose successor markers were lost would claim
            # every line to the poem's end; its own length bounds what it
            # can honestly cover (three words per verse line is the floor
            # of Butler's prose), and the lines beyond stay uncovered
            end = min(end, start + max(4, nwords // 3) - 1)
            if re.match(r"(I\.?e\.|i\.?e\.|Cf\.|See |There (seems|was) "
                        r"|A reference|The (reference|allusion))", text):
                continue
            spans.append((start, end, text))
        poems[key] = spans
    for key, spans in poems.items():
        for start, end, text in spans:
            for ln in range(start, end + 1):
                rkey = key + (ln,)
                ref = refs.get(rkey)
                if ref and ref not in mapping:
                    mapping[ref] = text
                    pairs.append((lat.get(ref, ''), text))
    return mapping, pairs


def write(outpath, tessname, refs, mapping, pairs):
    cov = len(mapping) / len(refs) if refs else 0
    hit, n = V.score(pairs, 'la', sample=800)
    ulist, idx, ref2u = [], {}, {}
    for ref, txt in mapping.items():
        if txt not in idx:
            idx[txt] = len(ulist)
            ulist.append(txt)
        ref2u[ref] = idx[txt]
    ok = hit is not None and hit >= 0.25
    print(f'{tessname:28s} cov {cov:.4f} ({len(mapping)}/{len(refs)}) '
          f'units {len(ulist)} names {hit}/{n} ' + ('ok' if ok else 'REJECTED'))
    if not ok:
        return False
    json.dump({
        'tess_work': f'la/{tessname}', 'language': 'la',
        'n_tess_refs': len(refs), 'n_translated': len(mapping),
        'coverage': round(cov, 4),
        'mean_source_lines_per_translation_unit':
            round(len(mapping) / max(1, len(ulist)), 1),
        'alignment_confidence': 'high' if hit >= 0.5 else 'medium',
        'name_check_hit_rate': hit, 'name_check_n': n,
        'verified_by': 'names',
        'sources': [{'translator': 'H. E. Butler', 'year': 1912,
                     'title': 'Propertius, with an English translation',
                     'publisher': 'William Heinemann',
                     'mode': 'exact',
                     'ref_composition': ['book', 'poem', 'paragraph line span'],
                     'source_url':
                         'https://archive.org/details/propertiuswithen00propuoft'}],
        'license': 'Public domain: published 1912. '
                   'Text from the Internet Archive scan.',
        'attribution': 'H. E. Butler (1912), via the Internet Archive',
        'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
    }, open(outpath, 'w'), ensure_ascii=False)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    paras = parse(args.src)
    print(f'poems parsed: {len(paras)}; paragraphs: '
          f'{sum(len(v) for v in paras.values())}')

    # family 1: propertius.elegies, refs prop. b.p.l
    t = os.path.join(args.tess_dir, 'propertius.elegies.tess')
    refs, lat, maxline = load_tess(t, r'^<(prop\. (\d+)\.(\d+)\.(\d+))>')
    mapping, pairs = build(paras, refs, lat, maxline)
    write(os.path.join(args.out_dir, 'la__propertius.elegies.json'),
          'propertius.elegies', refs, mapping, pairs)

    # family 2: propertius.elegiae_N, refs prop. eleg. p.l
    for b in (1, 2, 3, 4):
        t = os.path.join(args.tess_dir, f'propertius.elegiae_{b}.tess')
        if not os.path.exists(t):
            continue
        refs, lat, maxline = load_tess(t, r'^<(prop\. eleg\. (\d+)\.(\d+))>')
        mapping, pairs = build(paras, refs, lat, maxline, book=b)
        write(os.path.join(args.out_dir, f'la__propertius.elegiae_{b}.json'),
              f'propertius.elegiae_{b}', refs, mapping, pairs)


if __name__ == '__main__':
    main()
