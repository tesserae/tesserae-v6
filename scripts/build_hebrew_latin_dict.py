#!/usr/bin/env python3
"""Build a Hebrew->Latin cross-lingual dictionary by bridging the existing
Hebrew->Greek dictionary through the Greek->Latin dictionaries.

He->Grc: backend/synonymy/v6_additions/hebrew_greek.csv  (hebrew,greek ; bare Greek)
Grc->La: greek_latin_v6_additions.csv + perseus_greek_latin_v6_additions.csv
         (greek,latin[,latin...] ; accented Greek)

Join key = Greek normalized to lowercase, accents stripped, final sigma folded.
Output: backend/synonymy/v6_additions/hebrew_latin.csv  (hebrew,latin ; one pair/line)
The Hebrew keys are kept verbatim (already compatible with the Hebrew lemmatizer, since
he-grc works) and the Latin values verbatim (already compatible with the Latin index,
since grc-la works), so both sides match at runtime with no further normalization.
"""
import os, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SYN = os.path.join(HERE, '..', 'backend', 'synonymy', 'v6_additions')

def norm_gr(s):
    s = unicodedata.normalize('NFD', s.strip().lower())
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return s.replace('ς', 'σ')  # final sigma -> sigma

def load_greek_latin():
    gl = {}
    for fn in ['greek_latin_v6_additions.csv', 'perseus_greek_latin_v6_additions.csv']:
        with open(os.path.join(SYN, fn), encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 2:
                    continue
                g = norm_gr(parts[0])
                lats = [p.lower() for p in parts[1:] if p]
                if g and lats:
                    gl.setdefault(g, [])
                    for lat in lats:
                        if lat not in gl[g]:
                            gl[g].append(lat)
    return gl

def main():
    gl = load_greek_latin()
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
        f.write('# Built by bridging hebrew_greek.csv (He->Grc, CATSS-derived) through\n')
        f.write('# greek_latin + perseus_greek_latin (Grc->La). Format: hebrew,latin (one pair/line).\n')
        f.write('# Purpose: Hebrew Bible <-> Latin Vulgate (and wider Latin corpus) cross-lingual search.\n')
        for he in sorted(pairs):
            for lat in pairs[he]:
                f.write(f'{he},{lat}\n')
    print(f"He->Grc entries bridged: {bridged}")
    print(f"Hebrew words covered: {len(pairs)}")
    print(f"He->La pairs written: {n_pairs}")
    print(f"Output: {out}")

if __name__ == '__main__':
    main()
