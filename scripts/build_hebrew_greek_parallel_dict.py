#!/usr/bin/env python3
"""
Build a Hebrew-Greek cross-lingual dictionary from verse-aligned parallel texts.

The Hebrew Bible and the Septuagint (LXX) contain the same content in different
languages. By aligning verses by chapter.verse reference and finding which Hebrew
and Greek lemmas co-occur in parallel verses, we can build a translation dictionary
far richer than the English-pivot approach.

This is the standard statistical word alignment technique applied to the oldest
parallel corpus in existence.

Method:
  1. Parse Hebrew .tess files and Greek LXX .tess files
  2. Align by chapter.verse reference (e.g., Daniel 1.1 in both)
  3. For each aligned verse pair, record all (hebrew_lemma, greek_lemma) co-occurrences
  4. Score pairs by PMI (pointwise mutual information) to separate true translations
     from accidental co-occurrences
  5. Merge with the existing English-pivot dictionary

Output: backend/synonymy/v6_additions/hebrew_greek.csv (replaces the pivot-only version)
"""

import csv
import json
import math
import os
import re
import sys
import unicodedata
from collections import defaultdict, Counter

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Register Hebrew handler
from backend.hebrew import register as register_hebrew
register_hebrew()

from backend.text_processor import TextProcessor


def normalize_hebrew(text):
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'[\u0591-\u05BD\u05BF-\u05C7]', '', text)
    text = text.replace('\u05BE', ' ').replace('\u05C3', '')
    return text.strip()


def strip_greek_accents(s):
    nfd = unicodedata.normalize('NFD', s.lower())
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


# Parallel book mappings: Hebrew filename -> LXX filename
PARALLEL_BOOKS = {
    'hebrew_bible.daniel.tess': 'septuaginta.daniel_translatio_graeca.tess',
    'hebrew_bible.isaiah.part.1_12.tess': 'septuaginta.isaias.tess',
    'hebrew_bible.psalms.part.1_30.tess': 'septuaginta.psalmi.tess',
    'hebrew_bible.1_chronicles.tess': 'septuaginta.paralipomenon_i_sive_chronicon_i.tess',
    'hebrew_bible.ruth.tess': None,  # Ruth not in LXX corpus
    'hebrew_bible.1_samuel.tess': None,  # Not available as LXX
    'hebrew_bible.2_samuel.tess': None,
    'hebrew_bible.1_kings.tess': None,
    'hebrew_bible.genesis.part.1_3.tess': None,  # Genesis LXX not in corpus
    'hebrew_bible.exodus.part.15.tess': None,
    'hebrew_bible.deuteronomy.part.32.tess': None,
}


def extract_verse_ref(ref_str):
    """Extract (chapter, verse) from a reference string.

    Handles formats like:
      hebrew_bible.daniel.1.1
      septuaginta.daniel_translatio_graeca urn:cts:greekLit:tlg0527.tlg056.1st1K-grc1.1.1
    """
    # Try simple dot-separated format: book.chapter.verse
    parts = ref_str.strip().split('.')
    # Take last two numeric parts as chapter.verse
    nums = [p for p in parts if p.isdigit()]
    if len(nums) >= 2:
        return (int(nums[-2]), int(nums[-1]))
    elif len(nums) == 1:
        return (0, int(nums[0]))
    return None


def load_text_units(filepath, language):
    """Load and process text units, extracting verse references."""
    tp = TextProcessor()
    units = tp.process_file(filepath, language, 'line')

    verse_units = {}  # (chapter, verse) -> unit
    for unit in units:
        ref = unit.get('ref', '')
        cv = extract_verse_ref(ref)
        if cv and unit.get('lemmas'):
            verse_units[cv] = unit
    return verse_units


def main():
    he_dir = os.path.join(PROJECT_ROOT, 'texts', 'he')
    grc_dir = os.path.join(PROJECT_ROOT, 'texts', 'grc')

    # Hebrew stopwords to exclude from alignment
    from backend.hebrew.stopwords import HEBREW_STOP_WORDS
    he_stops = HEBREW_STOP_WORDS

    # Greek stopwords
    grc_stops = {
        'ο', 'η', 'το', 'και', 'εν', 'δε', 'τον', 'την', 'του', 'τησ',
        'των', 'τοισ', 'ταισ', 'αυτοσ', 'αυτη', 'αυτο', 'αυτων', 'αυτοισ',
        'εισ', 'εκ', 'εξ', 'απο', 'προσ', 'επι', 'κατα', 'μετα', 'περι',
        'παρα', 'δια', 'υπο', 'υπερ', 'συν', 'αντι', 'ωσ', 'ειμι', 'γαρ',
        'μεν', 'ουν', 'τε', 'τισ', 'τι', 'ου', 'ουκ', 'ουχ', 'μη',
        'εγω', 'συ', 'ημεισ', 'υμεισ', 'αλλα', 'ει', 'αν', 'οτι',
    }

    # Collect co-occurrence counts
    cooccur = Counter()        # (he_lemma, grc_lemma) -> count
    he_freq = Counter()        # he_lemma -> count (in how many verses)
    grc_freq = Counter()       # grc_lemma -> count
    n_aligned = 0

    for he_file, grc_file in PARALLEL_BOOKS.items():
        if grc_file is None:
            continue

        he_path = os.path.join(he_dir, he_file)
        grc_path = os.path.join(grc_dir, grc_file)

        if not os.path.exists(he_path) or not os.path.exists(grc_path):
            print(f"  SKIP: {he_file} or {grc_file} not found")
            continue

        print(f"  Aligning {he_file} <-> {grc_file}...")

        he_units = load_text_units(he_path, 'he')
        grc_units = load_text_units(grc_path, 'grc')

        # Find shared verse references
        shared_refs = set(he_units.keys()) & set(grc_units.keys())
        print(f"    Hebrew verses: {len(he_units)}, Greek verses: {len(grc_units)}, Aligned: {len(shared_refs)}")

        for ref in shared_refs:
            he_unit = he_units[ref]
            grc_unit = grc_units[ref]

            he_lemmas = set(l for l in he_unit.get('lemmas', []) if l and l not in he_stops and len(l) > 1)
            grc_lemmas_raw = grc_unit.get('lemmas', [])
            grc_lemmas = set()
            for gl in grc_lemmas_raw:
                stripped = strip_greek_accents(gl)
                if stripped and stripped not in grc_stops and len(stripped) > 1:
                    grc_lemmas.add(stripped)

            if not he_lemmas or not grc_lemmas:
                continue

            n_aligned += 1

            # Record co-occurrences
            for hl in he_lemmas:
                he_freq[hl] += 1
                for gl in grc_lemmas:
                    cooccur[(hl, gl)] += 1

            for gl in grc_lemmas:
                grc_freq[gl] += 1

    print(f"\nTotal aligned verses: {n_aligned}")
    print(f"Raw co-occurrence pairs: {len(cooccur)}")

    if n_aligned == 0:
        print("No aligned verses found. Cannot build dictionary.")
        return

    # Score by PMI: log2(P(he,grc) / (P(he) * P(grc)))
    # Filter: require co-occurrence >= 2 and PMI > 0
    scored_pairs = []
    for (hl, gl), count in cooccur.items():
        if count < 2:
            continue
        p_joint = count / n_aligned
        p_he = he_freq[hl] / n_aligned
        p_grc = grc_freq[gl] / n_aligned
        if p_he > 0 and p_grc > 0:
            pmi = math.log2(p_joint / (p_he * p_grc))
            if pmi > 0:
                scored_pairs.append((hl, gl, pmi, count))

    scored_pairs.sort(key=lambda x: (-x[2], -x[3]))
    print(f"PMI-filtered pairs (count>=2, PMI>0): {len(scored_pairs)}")

    # Load existing English-pivot dictionary
    pivot_path = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'v6_additions', 'hebrew_greek.csv')
    existing_pairs = set()
    if os.path.exists(pivot_path):
        with open(pivot_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    existing_pairs.add((row[0], row[1]))
        print(f"Existing pivot pairs: {len(existing_pairs)}")

    # Merge: alignment pairs + pivot pairs
    all_pairs = set()
    for hl, gl, pmi, count in scored_pairs:
        all_pairs.add((hl, gl))
    all_pairs.update(existing_pairs)
    print(f"Merged total: {len(all_pairs)} (alignment: {len(scored_pairs)}, pivot: {len(existing_pairs)}, overlap: {len(set((hl,gl) for hl,gl,_,_ in scored_pairs) & existing_pairs)})")

    # Write merged dictionary
    output_path = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'v6_additions', 'hebrew_greek.csv')
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for hl, gl in sorted(all_pairs):
            writer.writerow([hl, gl])
    print(f"Written to {output_path}")

    # Write detailed scored version
    scored_path = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'hebrew_greek_alignment.csv')
    with open(scored_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['hebrew', 'greek', 'pmi', 'cooccur_count', 'source'])
        for hl, gl, pmi, count in scored_pairs:
            src = 'alignment+pivot' if (hl, gl) in existing_pairs else 'alignment'
            writer.writerow([hl, gl, f'{pmi:.3f}', count, src])
        for hl, gl in existing_pairs:
            if (hl, gl) not in set((h, g) for h, g, _, _ in scored_pairs):
                writer.writerow([hl, gl, '', '', 'pivot_only'])
    print(f"Detailed version: {scored_path}")

    # Print top 30 alignment pairs
    print("\nTop 30 verse-aligned Hebrew-Greek pairs:")
    for hl, gl, pmi, count in scored_pairs[:30]:
        marker = " [+pivot]" if (hl, gl) in existing_pairs else ""
        print(f"  {hl:15s} <-> {gl:15s} (PMI={pmi:.2f}, n={count}){marker}")


if __name__ == '__main__':
    main()
