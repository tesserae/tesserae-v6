#!/usr/bin/env python3
"""Build data/scansion/latin_macrons.json: word -> macronized form, one form per word.

Source: the CLTK Latin models (lat_models_cltk, MIT licence, Classical Language
Toolkit), file taggers/macrons/macrons.py, a table of 257,615 word forms each with
one or more (tag, lemma, macronized form) entries derived from Morpheus. The
first entry's form is kept, lower-cased, for every word whose form carries a
macron and nothing but letters (209,072 words). The part-of-speech choice the CLTK macronizer makes with
its tagger is dropped: measured on 2026-10-13 against the MQDQ scansions of 400
lines each of the Aeneid, the Metamorphoses and the Pharsalia, the first-entry
table scanned 46 to 48 percent of lines correctly against 32 to 36 without
macrons and 47 to 58 with the tagger, and gave fewer wrong scansions than either
(3.5 to 4.2 percent against 6.5 to 7.2 plain and 5.2 to 7.2 with the tagger).
The tagger needs the whole CLTK stack, which the live site does not carry.

    python scripts/corpus/build_latin_macrons.py ~/cltk_data/lat/model/lat_models_cltk/taggers/macrons/macrons.py
"""
import importlib.machinery
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', '..', 'data', 'scansion', 'latin_macrons.json')
GOOD = re.compile(r'[a-zāēīōūȳ]+')


def main(src):
    mod = importlib.machinery.SourceFileLoader('macrons', src).load_module()
    table = mod.vowel_len_map
    out = {}
    for word, entries in table.items():
        if not entries:
            continue
        form = entries[0][2].lower()
        # 1,689 forms carry '_' or '+' (other length marks in the source);
        # they are left out rather than guessed at.
        if form != word.lower() and GOOD.fullmatch(form):
            out[word.lower()] = form
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    print(f'{len(table)} words read, {len(out)} written to {OUT}')


if __name__ == '__main__':
    main(sys.argv[1])
