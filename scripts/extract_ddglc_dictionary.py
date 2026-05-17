#!/usr/bin/env python3
"""
Extract Coptic-Greek dictionary from the DDGLC TEI XML lexicon.

The DDGLC (Database and Dictionary of Greek Loanwords in Coptic) provides
the authoritative mapping of Greek source words to their Coptic borrowings.
Each entry gives a Coptic lemma form, the Greek etymon, English meaning,
and part of speech.

This is a curated scholarly resource with 3,229 entries, far more precise
than the transliteration-based extraction from SCRIPTORIUM annotations.

Also processes the BBAW Lexicon of Coptic Egyptian (8,055 native Egyptian
entries) to extract English definitions for the English-pivot method.

Source: https://refubium.fu-berlin.de/handle/fub188/27813
License: CC BY-SA 4.0
"""

import csv
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DDGLC_PATH = '/tmp/ddglc_loanwords.xml'
BBAW_PATH = '/tmp/bbaw_egyptian.xml'
TEI_NS = {'tei': 'http://www.tei-c.org/ns/1.0'}


def normalize_coptic(text):
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
    return text.lower().strip()


def strip_greek_accents(s):
    nfd = unicodedata.normalize('NFD', s.lower())
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def extract_ddglc():
    """Extract Coptic-Greek pairs from DDGLC TEI XML."""
    print("Parsing DDGLC lexicon...")
    tree = ET.parse(DDGLC_PATH)
    root = tree.getroot()

    entries = root.findall('.//tei:entry', TEI_NS)
    print(f"  Total entries: {len(entries)}")

    pairs = []
    for entry in entries:
        # Get Coptic lemma form(s)
        lemma_els = entry.findall('.//tei:form[@type="lemma"]/tei:orth', TEI_NS)
        if not lemma_els:
            continue

        # Get Greek source lemma
        greek_el = entry.find('.//tei:etym//tei:ref[@type="greek_lemma::grl_lemma"]', TEI_NS)
        if greek_el is None or not greek_el.text:
            continue

        greek_lemma = strip_greek_accents(greek_el.text.strip())
        if not greek_lemma or len(greek_lemma) < 2:
            continue

        for lemma_el in lemma_els:
            if lemma_el.text:
                cop_lemma = normalize_coptic(lemma_el.text)
                if cop_lemma and len(cop_lemma) > 1:
                    pairs.append((cop_lemma, greek_lemma))

        # Also get variant/inflected forms
        variant_els = entry.findall('.//tei:form[@type="inflected"]/tei:orth', TEI_NS)
        for v_el in variant_els:
            if v_el.text:
                cop_variant = normalize_coptic(v_el.text)
                if cop_variant and len(cop_variant) > 1:
                    pairs.append((cop_variant, greek_lemma))

    return pairs


def extract_bbaw_english():
    """Extract Egyptian Coptic lemma -> English definitions from BBAW lexicon.

    Returns dict: coptic_lemma -> set of English words (for pivot to Greek).
    """
    print("Parsing BBAW Egyptian lexicon...")
    tree = ET.parse(BBAW_PATH)
    root = tree.getroot()

    entries = root.findall('.//tei:entry', TEI_NS)
    print(f"  Total entries: {len(entries)}")

    cop_english = {}
    for entry in entries:
        lemma_el = entry.find('.//tei:form[@type="lemma"]/tei:orth', TEI_NS)
        if lemma_el is None or not lemma_el.text:
            continue

        cop_lemma = normalize_coptic(lemma_el.text)
        if not cop_lemma or len(cop_lemma) < 2:
            continue

        # Collect English translations
        eng_words = set()
        # xml:lang needs special handling in ElementTree
        xml_ns = '{http://www.w3.org/XML/1998/namespace}'
        for quote in entry.findall('.//tei:sense//tei:cit[@type="translation"]/tei:quote', TEI_NS):
            if quote.get(f'{xml_ns}lang') == 'en' and quote.text:
                # Split into individual English words
                for word in re.split(r'[,;/\s()]+', quote.text.lower()):
                    word = re.sub(r'[^a-z]', '', word)
                    if word and len(word) > 2:
                        eng_words.add(word)

        if eng_words:
            cop_english[cop_lemma] = eng_words

    return cop_english


def build_bbaw_pivot_to_greek(cop_english):
    """Use BBAW English definitions to pivot Egyptian words to Greek."""
    # Load Perseus Greek-English
    grc_eng_path = os.path.join(PROJECT_ROOT, 'data', 'perseus_lexicon', 'extracted', 'greek_english.csv')
    if not os.path.exists(grc_eng_path):
        print("  Perseus Greek-English not found, skipping BBAW pivot")
        return []

    eng_to_greek = defaultdict(set)
    with open(grc_eng_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if len(row) < 2:
                continue
            grc = strip_greek_accents(row[0])
            for word in re.split(r'[,;/\s]+', row[1].lower()):
                word = re.sub(r'[^a-z]', '', word)
                if word and len(word) > 3:
                    eng_to_greek[word].add(grc)

    # Pivot
    pivot_pairs = []
    for cop, eng_words in cop_english.items():
        for eng in eng_words:
            if eng in eng_to_greek:
                for grc in eng_to_greek[eng]:
                    pivot_pairs.append((cop, grc))

    return pivot_pairs


def main():
    # =========================================================================
    # DDGLC: direct Coptic-Greek loanword mappings
    # =========================================================================
    ddglc_pairs = extract_ddglc()
    ddglc_set = set(ddglc_pairs)
    print(f"  DDGLC pairs: {len(ddglc_pairs)} raw, {len(ddglc_set)} unique")

    # =========================================================================
    # BBAW: Egyptian-English -> pivot to Greek
    # =========================================================================
    cop_english = extract_bbaw_english()
    print(f"  BBAW entries with English: {len(cop_english)}")
    bbaw_pivot = build_bbaw_pivot_to_greek(cop_english)
    bbaw_set = set(bbaw_pivot)
    print(f"  BBAW pivot pairs: {len(bbaw_pivot)} raw, {len(bbaw_set)} unique")

    # =========================================================================
    # Merge with existing dictionary
    # =========================================================================
    existing_path = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'v6_additions', 'coptic_greek.csv')
    existing = set()
    if os.path.exists(existing_path):
        with open(existing_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    existing.add((row[0], row[1]))

    merged = existing | ddglc_set | bbaw_set
    print(f"\n  Existing: {len(existing)}")
    print(f"  + DDGLC: {len(ddglc_set)} ({len(ddglc_set - existing)} new)")
    print(f"  + BBAW pivot: {len(bbaw_set)} ({len(bbaw_set - existing - ddglc_set)} new)")
    print(f"  = Merged: {len(merged)}")

    # Write
    with open(existing_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        for c, g in sorted(merged):
            writer.writerow([c, g])
    print(f"  Written to {existing_path}")

    # Save DDGLC-specific file
    ddglc_out = os.path.join(PROJECT_ROOT, 'backend', 'synonymy', 'coptic_greek_ddglc.csv')
    with open(ddglc_out, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['coptic', 'greek'])
        for c, g in sorted(ddglc_set):
            writer.writerow([c, g])
    print(f"  DDGLC-only: {ddglc_out} ({len(ddglc_set)} pairs)")

    # Top DDGLC pairs
    print(f"\nSample DDGLC pairs:")
    for c, g in sorted(ddglc_set)[:20]:
        print(f"  {c:20s} <-> {g}")

    # Sample BBAW pivot pairs (new ones not in existing)
    new_bbaw = sorted(bbaw_set - existing - ddglc_set)
    print(f"\nSample NEW BBAW pivot pairs:")
    for c, g in new_bbaw[:20]:
        print(f"  {c:20s} <-> {g}")


if __name__ == '__main__':
    main()
