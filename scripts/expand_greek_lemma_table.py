#!/usr/bin/env python3
"""
Expand the Greek lemma table with Koine Greek data from three new sources:

1. UD Ancient Greek-PTNK (LXX Genesis + Ruth, gold-standard lemmas)
2. MorphGNT SBLGNT (complete Greek NT, expert lemmas)
3. LXX-Rahlfs-1935 (complete Septuagint lexemes, if available)

Merges with the existing table built from UD Perseus + PROIEL treebanks.
"""

import json
import os
import re
import sys
import unicodedata
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def normalize_greek_form(text):
    """Normalize a Greek form for lookup: NFC, strip accents, lowercase."""
    text = unicodedata.normalize('NFC', text)
    # Strip combining diacriticals (accents, breathing marks)
    nfd = unicodedata.normalize('NFD', text.lower())
    stripped = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    return stripped.strip()


def normalize_greek_lemma(text):
    """Normalize a Greek lemma: NFC, strip accents, lowercase."""
    text = unicodedata.normalize('NFC', text)
    nfd = unicodedata.normalize('NFD', text.lower())
    stripped = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    return stripped.strip()


def extract_ptnk(ptnk_dir):
    """Extract form-to-lemma pairs from PTNK CoNLL-U files."""
    pairs = {}
    count = 0
    for conllu in Path(ptnk_dir).glob('*.conllu'):
        with open(conllu, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.rstrip()
                if not line or line.startswith('#'):
                    continue
                fields = line.split('\t')
                if len(fields) < 4:
                    continue
                if '-' in fields[0] or '.' in fields[0]:
                    continue
                form = fields[1]
                lemma = fields[2]
                if form and lemma and lemma != '_':
                    form_norm = normalize_greek_form(form)
                    lemma_norm = normalize_greek_lemma(lemma)
                    if form_norm and lemma_norm and len(form_norm) >= 2:
                        if form_norm not in pairs:
                            pairs[form_norm] = lemma_norm
                        count += 1
    return pairs, count


def extract_morphgnt(morphgnt_dir):
    """Extract form-to-lemma pairs from MorphGNT SBLGNT files."""
    pairs = {}
    count = 0
    for txt in sorted(Path(morphgnt_dir).glob('*-morphgnt.txt')):
        with open(txt, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 7:
                    continue
                # Column 6 = normalized word, column 7 = lemma
                form = parts[5]
                lemma = parts[6]
                if form and lemma:
                    form_norm = normalize_greek_form(form)
                    lemma_norm = normalize_greek_lemma(lemma)
                    if form_norm and lemma_norm and len(form_norm) >= 2:
                        if form_norm not in pairs:
                            pairs[form_norm] = lemma_norm
                        count += 1
    return pairs, count


def extract_rahlfs(rahlfs_dir):
    """Extract form-to-lemma pairs from LXX-Rahlfs-1935 data.

    Uses two files:
    - 01_wordlist_unicode/text_unaccented.csv: word_number<tab>unaccented_form
    - 02_lexemes/OSSP_lexemes.csv: word_number<tab>accented_lemma

    Both files are aligned by word number (1-based, covering the entire LXX).
    """
    pairs = {}
    count = 0

    forms_file = os.path.join(rahlfs_dir, '01_wordlist_unicode', 'text_unaccented.csv')
    lexemes_file = os.path.join(rahlfs_dir, '02_lexemes', 'OSSP_lexemes.csv')

    if not os.path.exists(forms_file) or not os.path.exists(lexemes_file):
        print(f"  Rahlfs files not found: {forms_file}, {lexemes_file}")
        return pairs, count

    # Load forms by word number
    forms = {}
    with open(forms_file, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                try:
                    word_num = int(parts[0])
                    form = parts[1].strip()
                    if form:
                        forms[word_num] = form
                except ValueError:
                    continue

    # Load lemmas by word number
    lemmas = {}
    with open(lexemes_file, 'r', encoding='utf-8') as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                try:
                    word_num = int(parts[0])
                    lemma = parts[1].strip()
                    if lemma:
                        lemmas[word_num] = lemma
                except ValueError:
                    continue

    print(f"  Rahlfs: {len(forms)} forms, {len(lemmas)} lemmas loaded")

    # Join on word number
    for word_num in forms:
        if word_num in lemmas:
            form = forms[word_num]
            lemma = lemmas[word_num]
            form_norm = normalize_greek_form(form)
            lemma_norm = normalize_greek_lemma(lemma)
            if form_norm and lemma_norm and len(form_norm) >= 2:
                if form_norm not in pairs:
                    pairs[form_norm] = lemma_norm
                count += 1

    return pairs, count


def main():
    # Load existing table
    table_path = os.path.join(PROJECT_ROOT, 'data', 'lemma_tables', 'greek_lemmas.json')
    with open(table_path, 'r', encoding='utf-8') as f:
        existing = json.load(f)
    print(f"Existing Greek lemma table: {len(existing)} entries")

    # Extract from PTNK
    ptnk_dir = '/tmp/UD_Ancient_Greek-PTNK'
    if os.path.isdir(ptnk_dir):
        ptnk_pairs, ptnk_count = extract_ptnk(ptnk_dir)
        new_ptnk = {k: v for k, v in ptnk_pairs.items() if k not in existing}
        print(f"PTNK (LXX Genesis+Ruth): {ptnk_count} tokens, {len(ptnk_pairs)} unique forms, {len(new_ptnk)} NEW")
        existing.update(new_ptnk)
    else:
        print("PTNK not found, skipping")

    # Extract from MorphGNT
    morphgnt_dir = '/tmp/morphgnt_sblgnt'
    if os.path.isdir(morphgnt_dir):
        mgnt_pairs, mgnt_count = extract_morphgnt(morphgnt_dir)
        new_mgnt = {k: v for k, v in mgnt_pairs.items() if k not in existing}
        print(f"MorphGNT (full NT): {mgnt_count} tokens, {len(mgnt_pairs)} unique forms, {len(new_mgnt)} NEW")
        existing.update(new_mgnt)
    else:
        print("MorphGNT not found, skipping")

    # Extract from Rahlfs
    rahlfs_dir = '/tmp/lxx_rahlfs'
    if os.path.isdir(rahlfs_dir):
        rahlfs_pairs, rahlfs_count = extract_rahlfs(rahlfs_dir)
        if rahlfs_pairs:
            new_rahlfs = {k: v for k, v in rahlfs_pairs.items() if k not in existing}
            print(f"Rahlfs LXX: {rahlfs_count} tokens, {len(rahlfs_pairs)} unique forms, {len(new_rahlfs)} NEW")
            existing.update(new_rahlfs)
        else:
            print("Rahlfs: no lexeme data extracted (format may differ)")
    else:
        print("Rahlfs LXX not found, skipping")

    # Write expanded table
    print(f"\nExpanded Greek lemma table: {len(existing)} entries")
    with open(table_path, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=0)
    print(f"Written to {table_path}")

    # Stats
    print(f"\nSample new PTNK entries:")
    if os.path.isdir(ptnk_dir):
        for k, v in list(new_ptnk.items())[:10]:
            print(f"  {k:20s} -> {v}")


if __name__ == '__main__':
    main()
