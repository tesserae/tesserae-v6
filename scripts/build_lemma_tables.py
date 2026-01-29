#!/usr/bin/env python3
"""
Build lemma lookup tables from Universal Dependencies treebanks.
Extracts surface form → lemma mappings for Latin and Greek.
"""
import os
import json
import re
from collections import defaultdict

TREEBANK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'treebanks')
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'lemma_tables')

def normalize_latin(word):
    """Normalize Latin orthography (j→i, v→u, lowercase)"""
    return word.lower().replace('j', 'i').replace('v', 'u')

def normalize_greek(word):
    """Normalize Greek (lowercase, strip diacritics for matching)"""
    import unicodedata
    word = word.lower()
    nfkd = unicodedata.normalize('NFKD', word)
    normalized = ''.join(c for c in nfkd if not unicodedata.combining(c))
    normalized = normalized.replace('ς', 'σ')
    return normalized

def parse_conllu(filepath, language):
    """Parse CoNLL-U file and extract surface→lemma mappings"""
    mappings = defaultdict(lambda: defaultdict(int))
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split('\t')
            if len(parts) < 3:
                continue
            
            token_id = parts[0]
            if '-' in token_id or '.' in token_id:
                continue
            
            surface = parts[1]
            lemma = parts[2]
            
            if not surface or not lemma or lemma == '_':
                continue
            
            if language == 'la':
                surface_norm = normalize_latin(surface)
                lemma_norm = normalize_latin(lemma)
            else:
                surface_norm = normalize_greek(surface)
                lemma_norm = normalize_greek(lemma)
            
            mappings[surface_norm][lemma_norm] += 1
    
    return mappings

def build_lookup_table(mappings):
    """Convert frequency mappings to single surface→lemma lookup"""
    lookup = {}
    for surface, lemma_counts in mappings.items():
        best_lemma = max(lemma_counts.items(), key=lambda x: x[1])[0]
        lookup[surface] = best_lemma
    return lookup

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    latin_dirs = ['UD_Latin-Perseus', 'UD_Latin-PROIEL']
    greek_dirs = ['UD_Ancient_Greek-Perseus', 'UD_Ancient_Greek-PROIEL']
    
    print("Building Latin lemma table...")
    latin_mappings = defaultdict(lambda: defaultdict(int))
    for dirname in latin_dirs:
        dirpath = os.path.join(TREEBANK_DIR, dirname)
        if not os.path.exists(dirpath):
            print(f"  Skipping {dirname} (not found)")
            continue
        for filename in os.listdir(dirpath):
            if filename.endswith('.conllu'):
                filepath = os.path.join(dirpath, filename)
                print(f"  Processing {filename}...")
                mappings = parse_conllu(filepath, 'la')
                for surface, lemma_counts in mappings.items():
                    for lemma, count in lemma_counts.items():
                        latin_mappings[surface][lemma] += count
    
    latin_lookup = build_lookup_table(latin_mappings)
    latin_output = os.path.join(OUTPUT_DIR, 'latin_lemmas.json')
    with open(latin_output, 'w', encoding='utf-8') as f:
        json.dump(latin_lookup, f, ensure_ascii=False, indent=None)
    print(f"  Saved {len(latin_lookup)} Latin mappings to {latin_output}")
    
    print("\nBuilding Greek lemma table...")
    greek_mappings = defaultdict(lambda: defaultdict(int))
    for dirname in greek_dirs:
        dirpath = os.path.join(TREEBANK_DIR, dirname)
        if not os.path.exists(dirpath):
            print(f"  Skipping {dirname} (not found)")
            continue
        for filename in os.listdir(dirpath):
            if filename.endswith('.conllu'):
                filepath = os.path.join(dirpath, filename)
                print(f"  Processing {filename}...")
                mappings = parse_conllu(filepath, 'grc')
                for surface, lemma_counts in mappings.items():
                    for lemma, count in lemma_counts.items():
                        greek_mappings[surface][lemma] += count
    
    greek_lookup = build_lookup_table(greek_mappings)
    greek_output = os.path.join(OUTPUT_DIR, 'greek_lemmas.json')
    with open(greek_output, 'w', encoding='utf-8') as f:
        json.dump(greek_lookup, f, ensure_ascii=False, indent=None)
    print(f"  Saved {len(greek_lookup)} Greek mappings to {greek_output}")
    
    print("\nSample Latin mappings:")
    samples = ['arma', 'uirumque', 'cano', 'troiae', 'qui', 'primus', 'ab', 'oris']
    for s in samples:
        s_norm = normalize_latin(s)
        if s_norm in latin_lookup:
            print(f"  {s} → {latin_lookup[s_norm]}")
        else:
            print(f"  {s} → (not found)")
    
    print("\nDone!")

if __name__ == '__main__':
    main()
