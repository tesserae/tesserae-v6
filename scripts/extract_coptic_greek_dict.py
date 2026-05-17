#!/usr/bin/env python3
"""
Extract Coptic-Greek cross-lingual dictionary from SCRIPTORIUM CoNLL-U annotations.

Words tagged with OrigLang=grc in the MISC column are Greek loanwords in Coptic.
Their lemma is the Coptic-adapted form; we map this to the likely Greek equivalent.

Also extracts from the Coptic Dictionary Online if available.

Output: backend/synonymy/coptic_greek_loanwords.csv
"""

import csv
import os
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTORIUM_DIR = '/tmp/coptic_scriptorium'
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'backend', 'synonymy')


def normalize_coptic(text):
    """Normalize Coptic text."""
    text = unicodedata.normalize('NFC', text)
    legacy_map = {
        '\u03E2': '\u2CB2', '\u03E3': '\u2CB3', '\u03E4': '\u2CB4', '\u03E5': '\u2CB5',
        '\u03E6': '\u2CB6', '\u03E7': '\u2CB7', '\u03E8': '\u2CB8', '\u03E9': '\u2CB9',
        '\u03EA': '\u2CBA', '\u03EB': '\u2CBB', '\u03EC': '\u2CBC', '\u03ED': '\u2CBD',
        '\u03EE': '\u2CBE', '\u03EF': '\u2CBF',
    }
    for legacy, primary in legacy_map.items():
        text = text.replace(legacy, primary)
    text = re.sub(r'[\u0300-\u036F]', '', text)
    return text.lower()


def normalize_greek(text):
    """Normalize Greek text (strip accents, lowercase)."""
    text = unicodedata.normalize('NFC', text)
    # Strip combining diacriticals (accents, breathing marks)
    text = re.sub(r'[\u0300-\u036F]', '', text)
    return text.lower()


# Coptic-to-Greek script mapping for loanwords
# Coptic letters that map to Greek equivalents
COPTIC_TO_GREEK = {
    'ⲁ': 'α', 'ⲃ': 'β', 'ⲅ': 'γ', 'ⲇ': 'δ', 'ⲉ': 'ε',
    'ⲍ': 'ζ', 'ⲏ': 'η', 'ⲑ': 'θ', 'ⲓ': 'ι', 'ⲕ': 'κ',
    'ⲗ': 'λ', 'ⲙ': 'μ', 'ⲛ': 'ν', 'ⲝ': 'ξ', 'ⲟ': 'ο',
    'ⲡ': 'π', 'ⲣ': 'ρ', 'ⲥ': 'σ', 'ⲧ': 'τ', 'ⲩ': 'υ',
    'ⲫ': 'φ', 'ⲭ': 'χ', 'ⲯ': 'ψ', 'ⲱ': 'ω',
}


def coptic_to_greek_form(coptic_word):
    """Convert a Coptic Greek-loanword form to its Greek equivalent.

    This is approximate -- Coptic adapted Greek words phonetically.
    The first 24 Coptic letters correspond to Greek letters.
    """
    coptic_normalized = normalize_coptic(coptic_word)
    greek_form = ''
    for ch in coptic_normalized:
        if ch in COPTIC_TO_GREEK:
            greek_form += COPTIC_TO_GREEK[ch]
        else:
            # Demotic-derived letters (ϣ, ϥ, ϩ, ϫ, ϭ, ϯ) have no Greek equivalent
            # Keep them as-is (these indicate native Egyptian words, not Greek loans)
            greek_form += ch
    return greek_form


def extract_greek_loanwords():
    """Extract Greek loanwords from SCRIPTORIUM CoNLL-U files."""
    loanwords = defaultdict(int)  # (coptic_lemma, greek_form) -> count

    conllu_files = list(Path(SCRIPTORIUM_DIR).rglob('*.conllu'))
    print(f"Scanning {len(conllu_files)} CoNLL-U files for Greek loanwords...")

    for filepath in conllu_files:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip('\n')
                if line.startswith('#') or not line.strip():
                    continue

                fields = line.split('\t')
                if len(fields) < 10:
                    continue

                token_id = fields[0]
                if '-' in token_id or '.' in token_id:
                    continue  # skip multi-word token and empty word lines

                form = fields[1]
                lemma = fields[2]
                misc = fields[9]

                # Check for Greek loanword tag
                if 'OrigLang=grc' in misc:
                    cop_lemma = normalize_coptic(lemma) if lemma != '_' else normalize_coptic(form)
                    if cop_lemma and len(cop_lemma) > 1:
                        greek_form = coptic_to_greek_form(cop_lemma)
                        loanwords[(cop_lemma, greek_form)] += 1

    return loanwords


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    loanwords = extract_greek_loanwords()
    print(f"Found {len(loanwords)} unique Coptic-Greek loanword pairs")

    # Sort by frequency (most common first)
    sorted_pairs = sorted(loanwords.items(), key=lambda x: -x[1])

    # Write as CSV in Tesserae synonymy format
    output_path = os.path.join(OUTPUT_DIR, 'coptic_greek_loanwords.csv')
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['coptic_lemma', 'greek_form', 'count'])
        for (cop, grk), count in sorted_pairs:
            writer.writerow([cop, grk, count])

    print(f"Written to {output_path}")

    # Also write in the V6 synonymy CSV format (word1,word2)
    v6_path = os.path.join(OUTPUT_DIR, 'v6_additions', 'coptic_greek.csv')
    os.makedirs(os.path.dirname(v6_path), exist_ok=True)

    # Only include pairs where the Greek form looks like valid Greek
    # (all characters are in the Greek range)
    valid_pairs = []
    for (cop, grk), count in sorted_pairs:
        # Check that the Greek form is all Greek characters
        is_greek = all(
            ('\u0370' <= ch <= '\u03FF') or  # Greek and Coptic block
            ('\u1F00' <= ch <= '\u1FFF') or  # Greek extended
            ch in ' -'
            for ch in grk
        )
        if is_greek and count >= 2:
            valid_pairs.append((cop, grk, count))

    with open(v6_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for cop, grk, count in valid_pairs:
            writer.writerow([cop, grk])

    print(f"V6 synonymy format ({len(valid_pairs)} pairs with count>=2): {v6_path}")

    # Print top 20 most common loanwords
    print("\nTop 20 most common Greek loanwords in Coptic:")
    for (cop, grk), count in sorted_pairs[:20]:
        print(f"  {cop:20s} -> {grk:20s} ({count} occurrences)")


if __name__ == '__main__':
    main()
