#!/usr/bin/env python3
"""Convert Petrarch's Africa from Latin Wikisource wikitext to .tess.

Source: https://la.wikisource.org/wiki/Africa (all nine books on one page,
fetched via the MediaWiki API as wikitext; the page credits
petrarca.letteraturaoperaomnia.org as its source). The Latin Library has no
Africa, so Wikisource is the accessible public-domain transcription.

Refs: petr. afr. book.line (books I-IX from the === headings, lines counted
per book inside the <poem> blocks).

The Wikisource page is missing the Liber IX heading: its ===VIII=== section
holds books 8 and 9 run together. Book 9 is split off at its incipit,
'Scipio provectus pelago Romanaque classis' (Festa's 1926 edition, as given
by Perseus, text 2011.01.0865 section 9).

Usage:
  python wikisource_africa_to_tess.py --src africa_wikitext.json --out <dir>

where --src is the raw JSON reply of
  https://la.wikisource.org/w/api.php?action=parse&page=Africa&prop=wikitext&format=json
"""
import argparse
import json
import os
import re

ROMAN = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7,
         'VIII': 8, 'IX': 9, 'X': 10}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    wikitext = json.load(open(args.src, encoding='utf-8'))['parse']['wikitext']['*']

    rows = []
    book, line = None, 0
    for raw in wikitext.split('\n'):
        s = raw.strip()
        m = re.fullmatch(r'=+\s*([IVX]+)\s*=+', s)
        if m and m.group(1) in ROMAN:
            book, line = ROMAN[m.group(1)], 0
            continue
        if not book:
            continue
        s = re.sub(r'</?poem[^>]*>', '', s)
        s = re.sub(r'\{\{[^}]*\}\}', '', s)      # templates
        s = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]', r'\1', s)  # links
        s = re.sub(r"''+", '', s)
        s = re.sub(r'<[^>]+>', ' ', s)
        s = re.sub(r'\s+', ' ', s).strip()
        if not s or s.startswith('[[') or s.startswith('Categoria:'):
            continue
        if book == 8 and s.startswith('Scipio provectus pelago'):
            book, line = 9, 0  # Liber IX heading missing on the source page
        line += 1
        rows.append((f'petr. afr. {book}.{line}', s))

    os.makedirs(args.out, exist_ok=True)
    dest = os.path.join(args.out, 'petrarch.africa.tess')
    with open(dest, 'w', encoding='utf-8') as fh:
        for ref, text in rows:
            fh.write(f'<{ref}>\t{text}\n')
    print(f'petrarch.africa: {len(rows)} lines -> {dest}')


if __name__ == '__main__':
    main()
