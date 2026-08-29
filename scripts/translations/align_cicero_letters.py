#!/usr/bin/env python3
"""Cicero's correspondence: all four collections, from Shuckburgh (1908-9).

3,091 corpus lines (ad Atticum, ad Familiares, ad Quintum fratrem, ad
Brutum) had no English. The English has been sitting in our own Perseus
extraction all along: canonical-latinLit carries Shuckburgh's complete
Bell & Sons translation (1908-9, public domain) as perseus-eng1 files, and
`tei_extract.py` already pulled clean letter-keyed chunks out of it. The
earlier Perseus alignment run never shipped them because those chunks
carry no ref_labels (their divpaths are letter anchors, "text=A:book=1:
letter=5"), which align_perseus.py cannot key. This aligner reads the
anchors directly.

Alignment is EXACT at letter level: our refs are book.letter.section, the
chunk is book.letter, and every section of a letter is served the letter's
English. Both sides use the same traditional book.letter numbering (the
per-book letter counts agree across all 16 books of Atticus and Fam).
Letters Shuckburgh splits with a suffix (11a, 12b...) have no corpus
counterpart and are skipped; a corpus letter with no chunk stays uncovered.

Shuckburgh prefaces many letters with his own historical headnote, and the
extraction concatenates it with the letter. Serving a translator's essay as
the translation of section 1 is the Medicamina failure, so the headnote is
cut: the letter proper begins at the first CAPITALISED salutation line
("TO ATTICUS (AT ATHENS) ROME", "BRUTUS TO CICERO"), and text before that
marker is dropped. A chunk with no such marker is served whole and counted.

Usage:
    python scripts/translations/align_cicero_letters.py \
        --extracted ~/perseus_trans/work/extracted6.json \
        --tess-dir texts/la --out-dir <dir>
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

WORKS = [
    # (extraction title, corpus file, ref regex)
    ('Letters to Atticus', 'cicero.letters_to_atticus',
     r'^<(cic\. att\. (\d+)\.(\d+)\.(\d+))>\s*(.*)'),
    ('Letters to his Friends', 'cicero.epistulae_ad_familiares',
     r'^<(cic\. fam\. (\d+)\.(\d+)\.(\d+))>\s*(.*)'),
    ('Letters to his brother Quintus', 'cicero.letters_to_quintus',
     r'^<(cic\. quint\. (\d+)\.(\d+)\.(\d+))>\s*(.*)'),
    ('Letters to Brutus', 'cicero.letters_to_brutus',
     r'^<(cic\. brut\. (\d+)\.(\d+)\.(\d+))>\s*(.*)'),
]

SALUTATION = re.compile(
    r'\b(?:TO [A-Z][A-Z. ]{2,}|[A-Z]{3,}[A-Z. ]* TO [A-Z][A-Z. ]{2,}'
    r'|GREETING)')


def strip_headnote(text):
    m = SALUTATION.search(text[:4000])
    if m and m.start() > 40:
        return text[m.start():], True
    return text, m is not None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--extracted', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    data = json.load(open(os.path.expanduser(args.extracted)))
    for title, tessname, pat in WORKS:
        entry = next((x for x in data if x['meta'].get('title') == title), None)
        if entry is None:
            print(f'{tessname}: extraction entry missing, skipped')
            continue
        chunks, unheaded, suffixed = {}, 0, 0
        for c in entry['chunks']:
            # the Quintus file anchors letters two levels deep, so the
            # anchor lives in the second divpath element; and it splits a
            # long letter into several chunks under the SAME anchor, so
            # chunks sharing a key are concatenated in order
            m = re.search(r'book=(\w+):letter=(\w+)', ' '.join(c['divpath']))
            if not m:
                continue
            b, l = m.group(1), m.group(2)
            if not (b.isdigit() and l.isdigit()):
                suffixed += 1
                continue
            text = re.sub(r'\s+', ' ', c['text']).strip()
            key = (int(b), int(l))
            if key in chunks:
                chunks[key] += ' ' + text
                continue
            text, had = strip_headnote(text)
            if not had:
                unheaded += 1
            if len(text.split()) >= 5:
                chunks[key] = text

        refs, mapping, pairs = 0, {}, []
        for line in open(os.path.join(args.tess_dir, tessname + '.tess'),
                         encoding='utf-8', errors='replace'):
            m = re.match(pat, line)
            if not m:
                continue
            refs += 1
            key = (int(m.group(2)), int(m.group(3)))
            if key in chunks:
                mapping[m.group(1)] = chunks[key]
                pairs.append((m.group(5), chunks[key]))

        cov = mapping and len(mapping) / refs or 0
        hit, n = V.score(pairs, 'la', sample=800)
        ulist, idx, ref2u = [], {}, {}
        for ref, txt in mapping.items():
            if txt not in idx:
                idx[txt] = len(ulist)
                ulist.append(txt)
            ref2u[ref] = idx[txt]
        ok = hit is not None and hit >= 0.25
        print(f'{tessname:36s} cov {cov:.4f} ({len(mapping)}/{refs}) '
              f'units {len(ulist)} names {hit}/{n} headnote-less {unheaded} '
              f'suffixed-skipped {suffixed} ' + ('ok' if ok else 'REJECTED'))
        if not ok:
            continue
        json.dump({
            'tess_work': f'la/{tessname}', 'language': 'la',
            'n_tess_refs': refs, 'n_translated': len(mapping),
            'coverage': round(cov, 4),
            'mean_source_lines_per_translation_unit':
                round(len(mapping) / max(1, len(ulist)), 1),
            'alignment_confidence': 'high' if hit >= 0.5 else 'medium',
            'name_check_hit_rate': hit, 'name_check_n': n,
            'verified_by': 'names',
            'sources': [{'translator': 'Evelyn S. Shuckburgh', 'year': 1909,
                         'title': 'The Letters of Cicero (Bell & Sons)',
                         'publisher': 'George Bell and Sons',
                         'mode': 'exact',
                         'ref_composition': ['book', 'letter'],
                         'source_url': 'https://github.com/PerseusDL/'
                                       'canonical-latinLit (perseus-eng1)'}],
            'license': 'Public domain: published 1908-1909. Text from the '
                       'Perseus Digital Library TEI (CC BY-SA 4.0 markup '
                       'over the public-domain translation).',
            'attribution': 'Evelyn S. Shuckburgh (1908-9), '
                           'via the Perseus Digital Library',
            'n_units_stored': len(ulist), 'units': ulist,
            'ref_to_unit': ref2u,
        }, open(os.path.join(args.out_dir, f'la__{tessname}.json'), 'w'),
            ensure_ascii=False)


if __name__ == '__main__':
    main()
