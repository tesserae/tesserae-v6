#!/usr/bin/env python3
"""
Extract Hebrew-Greek word-level dictionary from CATSS parallel data.

CATSS (Computer Assisted Tools for Septuagint Studies) provides word-by-word
alignment of the Hebrew Masoretic Text and the Greek Septuagint. Each line
in a .par file pairs one Hebrew word/phrase (CCAT betacode) with its Greek
translation (TLG betacode).

This is the gold standard for Hebrew-Greek lexical correspondence -- it captures
the actual translation choices made by the LXX translators, not statistical
approximations or dictionary glosses.

Sources: http://ccat.sas.upenn.edu/gopher/text/religion/biblical/parallel/
License: UPenn CCAT (restricted redistribution; used here for internal dictionary)

Output: Merged into backend/synonymy/v6_additions/hebrew_greek.csv
"""

import csv
import os
import re
import sys
import unicodedata
from collections import defaultdict, Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATSS_DIR = '/tmp/catss_parallel'

# ============================================================================
# CCAT Hebrew betacode -> Unicode conversion
# ============================================================================
HEBREW_BETACODE = {
    ')': 'א', 'B': 'ב', 'G': 'ג', 'D': 'ד', 'H': 'ה',
    'W': 'ו', 'Z': 'ז', 'X': 'ח', '+': 'ט', 'Y': 'י',
    'K': 'כ', 'L': 'ל', 'M': 'מ', 'N': 'נ', 'S': 'ס',
    '(': 'ע', 'P': 'פ', 'C': 'צ', 'Q': 'ק', 'R': 'ר',
    '$': 'שׁ', '&': 'שׂ', 'T': 'ת',
    # Final forms (CATSS doesn't distinguish, but some variants do)
}

# Greek betacode -> Unicode
GREEK_BETACODE = {
    'A': 'α', 'B': 'β', 'G': 'γ', 'D': 'δ', 'E': 'ε',
    'Z': 'ζ', 'H': 'η', 'Q': 'θ', 'I': 'ι', 'K': 'κ',
    'L': 'λ', 'M': 'μ', 'N': 'ν', 'C': 'ξ', 'O': 'ο',
    'P': 'π', 'R': 'ρ', 'S': 'σ', 'T': 'τ', 'U': 'υ',
    'F': 'φ', 'X': 'χ', 'Y': 'ψ', 'W': 'ω',
}

def hebrew_betacode_to_unicode(text):
    """Convert CCAT Hebrew betacode to Unicode consonantal Hebrew."""
    result = []
    text = text.strip()
    # Remove morphological markers: /, =, prefixes like W/, B/, etc.
    # Keep the root consonants
    # Strip text-critical markers
    text = re.sub(r'\..*$', '', text)  # strip annotations after .
    text = re.sub(r'\{[^}]*\}', '', text)  # strip lacunae
    text = re.sub(r'=.*$', '', text)  # strip variant readings

    for ch in text:
        if ch in HEBREW_BETACODE:
            result.append(HEBREW_BETACODE[ch])
        # Skip punctuation, numbers, markers
    return ''.join(result)


def greek_betacode_to_unicode(text):
    """Convert TLG Greek betacode to Unicode Greek (lowercase, no accents)."""
    result = []
    text = text.strip()
    text = re.sub(r'\{[^}]*\}', '', text)  # strip lacunae
    text = re.sub(r'=.*$', '', text)  # strip variant readings

    i = 0
    while i < len(text):
        ch = text[i].upper()
        if ch in GREEK_BETACODE:
            result.append(GREEK_BETACODE[ch])
        elif ch == '*':
            # Capital letter indicator - next char is the letter
            pass
        # Skip accents (/\=), breathing marks (())), and other markers
        i += 1

    return ''.join(result)


def normalize_hebrew(text):
    """Normalize Hebrew: strip nikkud, NFC."""
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'[\u0591-\u05BD\u05BF-\u05C7]', '', text)
    text = text.replace('\u05BE', '').replace('\u05C3', '')
    return text.strip()


def strip_greek_accents(s):
    nfd = unicodedata.normalize('NFD', s.lower())
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def parse_catss_file(filepath):
    """Parse a CATSS .par file into word-level Hebrew-Greek pairs."""
    pairs = []
    current_verse = ''

    with open(filepath, 'r', encoding='latin-1') as f:
        for line in f:
            line = line.rstrip('\n\r')

            # Verse reference lines (e.g., "Ruth 1:1")
            if re.match(r'^[A-Z][a-z]', line) and ':' in line:
                current_verse = line.strip()
                continue

            if not line.strip() or line.startswith('#'):
                continue

            # Word alignment line: HEBREW<tab>GREEK
            parts = line.split('\t')
            if len(parts) < 2:
                continue

            hebrew_bc = parts[0].strip()
            greek_bc = parts[1].strip()

            # Skip empty or marker-only entries
            if not hebrew_bc or hebrew_bc == '---' or not greek_bc or greek_bc == '---':
                continue

            # Handle compound entries (multiple words separated by spaces)
            # Split Hebrew compound (morphemes separated by /)
            hebrew_words = re.split(r'[/\s]+', hebrew_bc)
            greek_words = re.split(r'\s+', greek_bc)

            for hw in hebrew_words:
                hw = hw.strip()
                if not hw or hw == '---' or hw.startswith('=') or hw.startswith('.'):
                    continue
                he_unicode = hebrew_betacode_to_unicode(hw)
                he_normalized = normalize_hebrew(he_unicode)
                if not he_normalized or len(he_normalized) < 2:
                    continue

                for gw in greek_words:
                    gw = gw.strip()
                    if not gw or gw == '---' or gw.startswith('='):
                        continue
                    grc_unicode = greek_betacode_to_unicode(gw)
                    grc_normalized = strip_greek_accents(grc_unicode)
                    if not grc_normalized or len(grc_normalized) < 2:
                        continue

                    pairs.append((he_normalized, grc_normalized))

    return pairs


def main():
    print("Extracting CATSS Hebrew-Greek word alignments...")

    all_pairs = Counter()

    par_files = sorted(f for f in os.listdir(CATSS_DIR) if f.endswith('.par'))
    for par_file in par_files:
        filepath = os.path.join(CATSS_DIR, par_file)
        pairs = parse_catss_file(filepath)
        for he, grc in pairs:
            all_pairs[(he, grc)] += 1
        print(f"  {par_file}: {len(pairs)} word pairs")

    print(f"\nTotal raw pairs: {sum(all_pairs.values())}")
    print(f"Unique pairs: {len(all_pairs)}")

    # Filter: require count >= 2 to remove noise
    filtered = {(h, g): c for (h, g), c in all_pairs.items() if c >= 2}
    print(f"Pairs with count >= 2: {len(filtered)}")

    # Load existing dictionary
    existing_path = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'v6_additions', 'hebrew_greek.csv')
    existing = set()
    if os.path.exists(existing_path):
        with open(existing_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    existing.add((row[0], row[1]))

    catss_set = set(filtered.keys())
    merged = existing | catss_set
    print(f"\nExisting: {len(existing)}")
    print(f"CATSS: {len(catss_set)}")
    print(f"Overlap: {len(existing & catss_set)}")
    print(f"Merged: {len(merged)}")

    # Write
    with open(existing_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for h, g in sorted(merged):
            writer.writerow([h, g])
    print(f"Written to {existing_path}")

    # Save CATSS-specific file
    catss_path = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'hebrew_greek_catss.csv')
    with open(catss_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['hebrew', 'greek', 'count'])
        for (h, g), c in sorted(filtered.items(), key=lambda x: -x[1]):
            writer.writerow([h, g, c])
    print(f"CATSS-only: {catss_path}")

    # Top pairs
    top = sorted(filtered.items(), key=lambda x: -x[1])[:30]
    print("\nTop 30 CATSS Hebrew-Greek pairs (by frequency):")
    for (h, g), c in top:
        print(f"  {h:12s} <-> {g:15s} (n={c})")


if __name__ == '__main__':
    main()
