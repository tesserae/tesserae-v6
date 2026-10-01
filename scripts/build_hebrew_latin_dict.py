#!/usr/bin/env python3
"""Build a Hebrew->Latin cross-lingual dictionary by bridging the existing
Hebrew->Greek dictionary through the Greek->Latin side of the dictionary --
the SAME Greek->Latin sources live Greek-to-Latin cross-lingual search uses
(backend.synonym_dict.find_greek_latin_matches), not just the two small
V6-additions CSVs. Fixes issue #518: with only the two small CSVs (~4,300
Greek->Latin lines), common pairs were missing even when the Greek link
existed (e.g. he:מים -> grc:υδωρ has no Latin because the small CSVs never
mention υδωρ, though the main V3 dictionary maps it to aqua).

He->Grc: backend/synonymy/v6_additions/hebrew_greek.csv  (hebrew,greek ; bare Greek)
Grc->La, every source live search itself draws on:
  - greek_latin_v6_additions.csv + perseus_greek_latin_v6_additions.csv
    (greek,latin[,latin...] ; accented Greek; curated for this corpus)
  - the main V3 dictionary, 34,535 entries (backend.synonym_dict.get_greek_latin_dict())
  - CURATED_GREEK_LATIN, ~76 hand-curated high-confidence pairs search checks first
Proper-name gazetteer and cognate/transliteration matching are NOT joined in: both
need the actual Greek and Latin lemmas of a live text pair to run (gazetteer keys on
exact proper names, cognate matching compares two specific word lists), so neither
has a static Greek->Latin table to bridge through ahead of time.

Join key = Greek normalized to lowercase, accents stripped, final sigma folded to
medial sigma (ς -> σ). hebrew_greek.csv itself mixes both sigma forms for the same
word (e.g. both αδελφοσ and αδελφος occur), so every source is folded the same way
here, wider than live search's own lookup (which only folds for CURATED_GREEK_LATIN,
leaving the V3 dictionary keyed on whichever sigma its source text used) -- the bridge
has no live text to fall back on if a fold mismatch drops a pair, so it folds
everywhere to avoid losing coverage to an orthography accident.
Latin values are folded v->u (venio -> uenio) for every source, matching what the
Latin text processor itself emits (find_greek_latin_matches applies the same fold
to the V3 dictionary and gazetteer for the same reason: the V3 dictionary's Latin
glosses are classical v-spellings, but the indexed Latin corpus is u-form throughout).
Output: backend/synonymy/v6_additions/hebrew_latin.csv  (hebrew,latin ; one pair/line)
The Hebrew keys are kept verbatim (already compatible with the Hebrew lemmatizer, since
he-grc works) and the Latin values verbatim (already compatible with the Latin index,
since grc-la works), so both sides match at runtime with no further normalization.
"""
import os, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
SYN = os.path.join(HERE, '..', 'backend', 'synonymy', 'v6_additions')

from backend.synonym_dict import get_greek_latin_dict, CURATED_GREEK_LATIN

def norm_gr(s):
    s = unicodedata.normalize('NFD', s.strip().lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.replace('ς', 'σ')  # final sigma -> medial sigma

def load_greek_latin():
    """Every Greek->Latin pair live Greek-to-Latin search can use, folded into
    one Greek(normalized) -> [Latin,...] table. Returns (table, counts) where
    counts reports how many raw entries each source contributed, for the
    before/after line in the PR report.
    """
    gl = {}
    counts = {}

    def add(source, g_raw, lats):
        g = norm_gr(g_raw)
        lats = [l.strip().lower().replace('v', 'u') for l in lats if l and l.strip()]
        if not g or not lats:
            return
        counts[source] = counts.get(source, 0) + 1
        gl.setdefault(g, [])
        for lat in lats:
            if lat not in gl[g]:
                gl[g].append(lat)

    for fn in ['greek_latin_v6_additions.csv', 'perseus_greek_latin_v6_additions.csv']:
        with open(os.path.join(SYN, fn), encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 2:
                    continue
                add(fn, parts[0], parts[1:])

    # The main V3 Greek-Latin dictionary (34,535 entries) -- the same table
    # live Greek-to-Latin search queries via get_greek_latin_dict().
    _, v3_norm = get_greek_latin_dict()
    for g_key, lats in v3_norm.items():
        add('v3_dictionary', g_key, lats)

    # The curated high-confidence pairs live search checks first.
    for g_key, lats in CURATED_GREEK_LATIN.items():
        add('curated_greek_latin', g_key, lats)

    return gl, counts

def main():
    gl, source_counts = load_greek_latin()
    pairs = {}  # hebrew -> list(latin), order-preserving
    bridged = 0
    with open(os.path.join(SYN, 'hebrew_greek.csv'), encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if len(parts) < 2:
                continue
            he = parts[0].strip()
            g = norm_gr(parts[1])
            if not he or g not in gl:
                continue
            bridged += 1
            pairs.setdefault(he, [])
            for lat in gl[g]:
                if lat not in pairs[he]:
                    pairs[he].append(lat)

    n_pairs = sum(len(v) for v in pairs.values())
    out = os.path.join(SYN, 'hebrew_latin.csv')
    with open(out, 'w', encoding='utf-8') as f:
        f.write('# Tesserae V6 Hebrew-Latin Cross-Lingual Dictionary\n')
        f.write('# Built by bridging hebrew_greek.csv (He->Grc, CATSS-derived) through every\n')
        f.write('# Greek->Latin source live search uses: the two small curated CSVs, the main\n')
        f.write('# V3 dictionary, and CURATED_GREEK_LATIN (see scripts/build_hebrew_latin_dict.py).\n')
        f.write('# Format: hebrew,latin (one pair/line).\n')
        f.write('# Purpose: Hebrew Bible <-> Latin Vulgate (and wider Latin corpus) cross-lingual search.\n')
        for he in sorted(pairs):
            for lat in pairs[he]:
                f.write(f'{he},{lat}\n')
    print("Greek->Latin source entries used for the join:")
    for source, n in sorted(source_counts.items()):
        print(f"  {source}: {n}")
    print(f"Distinct Greek keys available to bridge through: {len(gl)}")
    print(f"He->Grc entries bridged: {bridged}")
    print(f"Hebrew words covered: {len(pairs)}")
    print(f"He->La pairs written: {n_pairs}")
    print(f"Output: {out}")

if __name__ == '__main__':
    main()
