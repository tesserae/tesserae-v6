#!/usr/bin/env python3
"""Seneca, Epistulae morales: all 124 letters, section-exact, from Gummere.

The largest single Seneca gap (2,263 corpus lines) and the only major
Latin prose work still blank whose standard English is public domain:
Richard Mott Gummere's Loeb, vols I-III, 1917/1920/1925. Source is the
English Wikisource transcription ("Moral letters to Lucilius"), which is
clean keyed text, no OCR: each letter is its own page, the salutation
("Greetings from Seneca to his friend Lucilius") opens it, and Gummere's
printed SECTION numbers survive as "1.", "2." in the body.

Our refs are letter.section with the salutation as section 0 -- the same
shape, so the alignment is exact: section 0 takes the salutation plus
section 1's text (Wikisource folds no text into the salutation line
itself; serving 0 from unit 1 follows the Jerome-letters precedent),
and section n takes its numbered paragraph. Section numbers are accepted
only in exact sequence; a letter whose parsed maximum disagrees with the
corpus maximum by more than one is refused and printed.

Wikisource footnotes render as trailing "↑ ..." blocks and inline
"[ 1 ]" markers; both are cut.

Run after caching the letters (the download script is five lines of curl
against the Wikisource API; the cache directory is the input here).

Usage:
    python scripts/translations/align_seneca_epistles.py \
        --ws-dir <dir with letter_N.json> \
        --tess texts/la/seneca.ad_lucilium_epistulae_morales.tess \
        --out la__seneca.ad_lucilium_epistulae_morales.json
"""
import argparse
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V


def letter_sections(path):
    """{section: text}, or None if the page is missing/unparsable."""
    try:
        d = json.load(open(path))
        t = d['parse']['text']['*']
    except Exception:
        return None
    t = re.sub(r'<style.*?</style>', '', t, flags=re.S)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = html.unescape(t)
    t = re.sub(r'\s+', ' ', t)
    t = re.sub(r'\[\s*\d+\s*\]', '', t)   # inline footnote markers, which
    t = re.sub(r'\s+', ' ', t)               # otherwise sit between title and "1."
    # most letters open directly under their printed title ("II. ON
    # DISCURSIVENESS IN READING"); letter 1 alone carries the salutation
    m = re.search(r'Greetings from Seneca', t)
    if m:
        t = t[m.start():]
    else:
        # every page prints "Seneca<ZWSP>" right before the letter's
        # title; the body starts at the first "1." after it (title shapes
        # vary too much to pattern-match: "ON BENEFITS.", "SOME
        # ARGUMENTS...", one letter with no numeral at all)
        anchor = t.find('Seneca \u200b')
        if anchor == -1:
            return None
        m = re.search(r'\b1\.\s', t[anchor:anchor + 400])
        if not m:
            return None
        t = t[anchor + m.start():]
    t = t.split('↑')[0]                       # footnote block
    # split on every candidate marker and let the SEQUENCE decide: a
    # sentence-boundary lookbehind missed every section opening after a
    # colon or a quotation mark and cost half the corpus; a prose number
    # that happens to be followed by a period is rejected by the chain
    # below instead
    parts = re.split(r'\s(\d{1,3})\.\s+', t)
    out, cur = {}, 0
    head = parts[0].strip()
    if head.startswith('1. '):
        # no salutation: the head IS section 1
        out[1], cur = head[3:].strip(), 1
    else:
        out[0] = head
    i = 1
    while i + 1 < len(parts) + 1 and i < len(parts):
        n = int(parts[i])
        if cur + 1 <= n <= cur + 3:
            # the expected successor, or a short jump over a marker the
            # transcription lost (that section stays uncovered)
            out[n] = parts[i + 1].strip()
            cur = n
        else:
            # a number out of sequence is a quantity in the prose, not a
            # section; glue it back onto the previous section
            prev = max(out) if out else 0
            out.setdefault(prev, '')
            out[prev] = (out[prev] + f' {n}. ' + parts[i + 1]).strip()
        i += 2
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ws-dir', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    refs, lat = {}, {}
    import collections
    corpus_max = collections.defaultdict(int)
    for line in open(args.tess, encoding='utf-8', errors='replace'):
        m = re.match(r'^<(sen\.ep\. (\d+)\.(\d+))>\s*(.*)', line)
        if not m:
            continue
        l, s = int(m.group(2)), int(m.group(3))
        refs[(l, s)] = m.group(1)
        lat[m.group(1)] = m.group(4)
        corpus_max[l] = max(corpus_max[l], s)

    mapping, pairs, refused, missing = {}, [], [], []
    for l in sorted(corpus_max):
        secs = letter_sections(os.path.join(args.ws_dir, f'letter_{l}.json'))
        if not secs:
            missing.append(l)
            continue
        got_max = max(secs)
        if abs(got_max - corpus_max[l]) > 1:
            refused.append((l, got_max, corpus_max[l]))
            continue
        for (ll, s), ref in refs.items():
            if ll != l:
                continue
            text = secs.get(s)
            if s == 0:
                # our section 0 is the salutation line; serve it with the
                # letter's opening section so the reader gets real text
                text = (secs.get(0, '') + ' ' + secs.get(1, '')).strip()
            if text:
                mapping[ref] = text
                pairs.append((lat[ref], text))

    cov = len(mapping) / len(refs)
    hit, n = V.score(pairs, 'la', sample=800)
    if refused:
        print(f'refused letters (section-count mismatch): {refused}')
    if missing:
        print(f'missing/unparsable letters: {missing}')
    ulist, idx, ref2u = [], {}, {}
    for ref, txt in mapping.items():
        if txt not in idx:
            idx[txt] = len(ulist)
            ulist.append(txt)
        ref2u[ref] = idx[txt]
    print(f'coverage {cov:.4f} ({len(mapping)}/{len(refs)}), '
          f'{len(ulist)} units, names {hit}/{n}')
    if hit is None or hit < 0.25:
        print('REJECTED')
        return
    json.dump({
        'tess_work': 'la/seneca.ad_lucilium_epistulae_morales',
        'language': 'la',
        'n_tess_refs': len(refs), 'n_translated': len(mapping),
        'coverage': round(cov, 4),
        'mean_source_lines_per_translation_unit':
            round(len(mapping) / max(1, len(ulist)), 1),
        'alignment_confidence': 'high' if hit >= 0.5 else 'medium',
        'name_check_hit_rate': hit, 'name_check_n': n,
        'verified_by': 'names',
        'sources': [{'translator': 'Richard Mott Gummere',
                     'year': 1925,
                     'title': 'Ad Lucilium Epistulae Morales (Loeb, '
                              'vols I-III, 1917-1925)',
                     'publisher': 'William Heinemann / G. P. Putnam',
                     'mode': 'exact',
                     'ref_composition': ['letter', 'section'],
                     'source_url': 'https://en.wikisource.org/wiki/'
                                   'Moral_letters_to_Lucilius'}],
        'license': 'Public domain in the United States: published '
                   '1917-1925. Text from the English Wikisource '
                   'transcription.',
        'attribution': 'R. M. Gummere (Loeb, 1917-25), via Wikisource',
        'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
    }, open(args.out, 'w'), ensure_ascii=False)


if __name__ == '__main__':
    main()
