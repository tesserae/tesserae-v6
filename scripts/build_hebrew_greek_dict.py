#!/usr/bin/env python3
"""
Build a Hebrew-Greek cross-lingual dictionary using English as a pivot.

Sources:
  - BHSA: Hebrew lexemes with English glosses (6,461 entries)
  - Perseus: Greek-English dictionary (data/perseus_lexicon/extracted/greek_english.csv)

Method: Match Hebrew and Greek words that share English glosses.
This is the same English-pivot approach used for Greek-Latin and Latin-English.

Output: backend/synonymy/v6_additions/hebrew_greek.csv
"""

import csv
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


def normalize_hebrew(text):
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'[\u0591-\u05BD\u05BF-\u05C7]', '', text)
    text = text.replace('\u05BE', ' ')
    text = text.replace('\u05C3', '')
    text = re.sub(r'[/=\[\]()]', '', text).strip()
    return text


def normalize_greek(text):
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'[\u0300-\u036F]', '', text)
    return text.lower()


def normalize_gloss(gloss):
    """Normalize an English gloss for matching."""
    # Split on common separators
    parts = re.split(r'[,;/]', gloss.lower())
    # Clean each part
    senses = set()
    for part in parts:
        part = part.strip()
        # Remove parenthetical content
        part = re.sub(r'\([^)]*\)', '', part).strip()
        # Remove articles and common prefixes
        part = re.sub(r'^(a |an |the |to )', '', part).strip()
        if part and len(part) > 2:
            senses.add(part)
    return senses


def main():
    print("Loading BHSA Hebrew glosses...")
    from tf.app import use
    A = use('ETCBC/bhsa', hoist=globals(), silent='deep')
    api = A.api
    F = api.F

    # Build Hebrew: gloss -> set of Hebrew lemmas
    hebrew_by_gloss = defaultdict(set)
    hebrew_glosses = {}  # lemma -> original gloss

    seen = set()
    for word in F.otype.s('word'):
        lex = F.lex_utf8.v(word)
        gloss = F.gloss.v(word)
        if not lex or not gloss or lex in seen:
            continue
        seen.add(lex)

        lex_norm = normalize_hebrew(lex)
        if not lex_norm or len(lex_norm) < 2:
            continue

        hebrew_glosses[lex_norm] = gloss
        senses = normalize_gloss(gloss)
        for sense in senses:
            hebrew_by_gloss[sense].add(lex_norm)

    print(f"  {len(hebrew_glosses)} Hebrew lexemes, {len(hebrew_by_gloss)} unique English senses")

    # Load Greek-English data from Perseus
    greek_english_path = os.path.join(PROJECT_ROOT, 'data', 'perseus_lexicon', 'extracted', 'greek_english.csv')
    print(f"Loading Greek-English data from {greek_english_path}...")

    greek_by_gloss = defaultdict(set)
    greek_glosses = {}

    with open(greek_english_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) < 2:
                continue
            greek_word = row[0]
            english_senses = row[1] if len(row) > 1 else ''

            greek_norm = normalize_greek(greek_word)
            if not greek_norm or len(greek_norm) < 2:
                continue

            greek_glosses[greek_norm] = english_senses
            senses = normalize_gloss(english_senses)
            for sense in senses:
                greek_by_gloss[sense].add(greek_norm)

    print(f"  {len(greek_glosses)} Greek lexemes, {len(greek_by_gloss)} unique English senses")

    # Find matches via shared English senses
    print("Finding Hebrew-Greek pairs via English pivot...")
    pair_scores = defaultdict(float)

    for sense in hebrew_by_gloss:
        if sense in greek_by_gloss:
            hebrew_words = hebrew_by_gloss[sense]
            greek_words = greek_by_gloss[sense]
            # Score inversely proportional to ambiguity
            score = 1.0 / (len(hebrew_words) * len(greek_words))
            for hw in hebrew_words:
                for gw in greek_words:
                    pair_scores[(hw, gw)] += score

    # Sort by score (best matches first)
    sorted_pairs = sorted(pair_scores.items(), key=lambda x: -x[1])

    print(f"  {len(sorted_pairs)} total pairs found")

    # Filter: require score >= 0.1 to avoid very noisy low-confidence pairs
    good_pairs = [(hw, gw, score) for (hw, gw), score in sorted_pairs if score >= 0.1]
    print(f"  {len(good_pairs)} pairs with score >= 0.1")

    # Write output
    output_dir = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'v6_additions')
    os.makedirs(output_dir, exist_ok=True)

    # Full scored version
    full_path = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'hebrew_greek_pivot.csv')
    with open(full_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['hebrew', 'greek', 'score', 'hebrew_gloss', 'greek_gloss'])
        for hw, gw, score in good_pairs:
            writer.writerow([hw, gw, f'{score:.3f}',
                           hebrew_glosses.get(hw, ''),
                           greek_glosses.get(gw, '')])
    print(f"  Full scored output: {full_path}")

    # V6 synonymy format (just word pairs)
    v6_path = os.path.join(output_dir, 'hebrew_greek.csv')
    with open(v6_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for hw, gw, score in good_pairs:
            writer.writerow([hw, gw])
    print(f"  V6 synonymy format: {v6_path}")

    # Print top 30
    print("\nTop 30 Hebrew-Greek pairs:")
    for hw, gw, score in good_pairs[:30]:
        hg = hebrew_glosses.get(hw, '')
        gg = greek_glosses.get(gw, '')
        print(f"  {hw:15s} <-> {gw:15s} (score={score:.2f}) [{hg} / {gg[:40]}]")


if __name__ == '__main__':
    main()
