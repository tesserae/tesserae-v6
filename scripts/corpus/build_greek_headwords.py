#!/usr/bin/env python3
"""
Build data/lemma_tables/greek_headwords.json: the accented LSJ headwords for
each accent-stripped Greek lemma.

The Greek lemma table (greek_lemmas.json) is keyed and valued in stripped
letters (no accents or breathings, final sigma written σ), the form the search
index uses. A dictionary wants the headword as it is spelled: Logeion answers
"μῆνις" and nothing to "μηνισ". This table bridges the two: for each stripped
spelling, the LSJ headwords that reduce to it, in the order LSJ lists them.

    μηνισ -> ["μῆνις"]
    θεα   -> ["θέα", "θεά"]

Source: the Perseus Digital Library's TEI text of Liddell, Scott and Jones, A
Greek-English Lexicon (data/perseus_lexicon/source_lexicons/lsj_part*.xml,
headwords in beta code), Creative Commons Attribution-ShareAlike 3.0. Only
headwords are taken, not entry text.

Usage: python scripts/corpus/build_greek_headwords.py [--source DIR] [--out FILE]
"""
import argparse
import glob
import json
import os
import re
import unicodedata

import beta_code

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SOURCE = os.path.join(ROOT, 'data', 'perseus_lexicon', 'source_lexicons')
OUT = os.path.join(ROOT, 'data', 'lemma_tables', 'greek_headwords.json')

ENTRY = re.compile(r'<entryFree\b[^>]*>(.*?)</entryFree>', re.S)
ORTH = re.compile(r'<orth\b([^>]*)>([^<]*)</orth>')


def strip_greek(word):
    """The lemma table's spelling: no accents or breathings, σ for ς, lower case."""
    nfkd = unicodedata.normalize('NFKD', word)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).replace('ς', 'σ').lower()


def headword(beta):
    """A beta code headword as accented Unicode (NFC), without length marks
    (_ and ^ in beta code) and without the sense digits LSJ appends."""
    beta = re.sub(r'[_^]', '', beta.strip())
    beta = re.sub(r'\d+$', '', beta)
    if not beta:
        return None
    word = unicodedata.normalize('NFC', beta_code.beta_code_to_greek(beta))
    word = word.replace('-', '')
    if not re.search(r'[Ͱ-Ͽἀ-῿]', word):
        return None
    return word


def build(source):
    table = {}
    entries = 0
    for path in sorted(glob.glob(os.path.join(source, 'lsj_part*.xml'))):
        with open(path, encoding='utf-8') as f:
            text = f.read()
        for m in ENTRY.finditer(text):
            entries += 1
            for attrs, beta in ORTH.findall(m.group(1)):
                if 'extent="full"' not in attrs:
                    continue
                hw = headword(beta)
                if not hw:
                    continue
                key = strip_greek(hw)
                if key and hw not in table.setdefault(key, []):
                    table[key].append(hw)
                break   # the first full orth is the headword
    return table, entries


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default=SOURCE)
    ap.add_argument('--out', default=OUT)
    args = ap.parse_args()
    table, entries = build(args.source)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(dict(sorted(table.items())), f, ensure_ascii=False, separators=(',', ':'))
    several = sum(1 for v in table.values() if len(v) > 1)
    print(f'{entries} entries read, {len(table)} stripped spellings, {several} with more than one headword, '
          f'written to {args.out} ({os.path.getsize(args.out) // 1024} KB)')


if __name__ == '__main__':
    main()
