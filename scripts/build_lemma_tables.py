#!/usr/bin/env python3
"""
Build lemma lookup tables from Universal Dependencies treebanks + LatinPipe syntax data.
Extracts surface form → lemma mappings for Latin and Greek.

Sources (in priority order):
1. UD treebanks (gold standard, manually annotated)
2. LatinPipe syntax database (machine-parsed, broad corpus coverage)

The UD treebanks provide high-quality lemmatization for forms they cover.
LatinPipe fills in gaps for forms not seen in the treebanks.
"""
import os
import sys
import json
import sqlite3
from collections import defaultdict

TREEBANK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'treebanks')
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'lemma_tables')
SYNTAX_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'inverted_index', 'syntax_latin.db')

# One shared rule, backend/latin_orthography.py. The tables this script
# writes are WHY that rule is what it is: every key it stores is folded here.
from backend.latin_orthography import fold_latin as normalize_latin  # noqa: E402

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

def extract_latinpipe_mappings(db_path):
    """Extract form→lemma mappings from LatinPipe syntax database"""
    if not os.path.exists(db_path):
        print(f"  LatinPipe database not found: {db_path}")
        return {}
    
    conn = sqlite3.connect(db_path)
    form_lemma_counts = defaultdict(lambda: defaultdict(int))
    
    cursor = conn.execute('SELECT tokens, lemmas FROM syntax')
    total_lines = 0
    for row in cursor:
        total_lines += 1
        toks = json.loads(row[0]) if row[0].startswith('[') else row[0].split()
        lems = json.loads(row[1]) if row[1].startswith('[') else row[1].split()
        for t, l in zip(toks, lems):
            t_norm = normalize_latin(t)
            l_norm = normalize_latin(l)
            if not t_norm.isalpha() or not l_norm.isalpha():
                continue
            form_lemma_counts[t_norm][l_norm] += 1
    
    conn.close()
    
    lookup = build_lookup_table(form_lemma_counts)
    print(f"  Extracted {len(lookup)} mappings from {total_lines} parsed lines")
    return lookup

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    latin_dirs = [
        'UD_Latin-Perseus',
        'UD_Latin-PROIEL',
        'UD_Latin-ITTB',
        'UD_Latin-LLCT',
        'UD_Latin-UDante',
        'UD_Latin-CIRCSE',
    ]
    greek_dirs = ['UD_Ancient_Greek-Perseus', 'UD_Ancient_Greek-PROIEL']
    
    print("=" * 60)
    print("Building Latin lemma table")
    print("=" * 60)
    
    print("\nStep 1: Processing UD treebanks (gold standard)...")
    latin_mappings = defaultdict(lambda: defaultdict(int))
    for dirname in latin_dirs:
        dirpath = os.path.join(TREEBANK_DIR, dirname)
        if not os.path.exists(dirpath):
            print(f"  Skipping {dirname} (not found)")
            continue
        conllu_files = [f for f in os.listdir(dirpath) if f.endswith('.conllu')]
        if not conllu_files:
            print(f"  Skipping {dirname} (no .conllu files)")
            continue
        for filename in conllu_files:
            filepath = os.path.join(dirpath, filename)
            mappings = parse_conllu(filepath, 'la')
            for surface, lemma_counts in mappings.items():
                for lemma, count in lemma_counts.items():
                    latin_mappings[surface][lemma] += count
        count = sum(len(v) for v in latin_mappings.values())
        print(f"  {dirname}: cumulative {len(latin_mappings)} forms")
    
    ud_lookup = build_lookup_table(latin_mappings)
    print(f"\n  UD treebanks total: {len(ud_lookup)} unique form→lemma mappings")
    
    print("\nStep 2: Extracting LatinPipe corpus mappings (fill gaps)...")
    lp_lookup = extract_latinpipe_mappings(SYNTAX_DB)
    
    print("\nStep 3: Merging (UD takes priority over LatinPipe)...")
    merged = dict(ud_lookup)
    new_from_lp = 0
    for form, lemma in lp_lookup.items():
        if form not in merged:
            merged[form] = lemma
            new_from_lp += 1
    
    print(f"  UD forms: {len(ud_lookup)}")
    print(f"  New forms from LatinPipe: {new_from_lp}")
    print(f"  Total merged: {len(merged)}")
    
    latin_output = os.path.join(OUTPUT_DIR, 'latin_lemmas.json')
    with open(latin_output, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=None)
    print(f"\n  Saved {len(merged)} Latin mappings to {latin_output}")
    
    print("\n" + "=" * 60)
    print("Building Greek lemma table")
    print("=" * 60)
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
    
    print("\n" + "=" * 60)
    print("Validation: Key Latin forms")
    print("=" * 60)
    test_forms = {
        'crinis': 'crinis', 'crines': 'crinis', 'crinem': 'crinis',
        'crinibus': 'crinis', 'crine': 'crinis',
        'uertex': 'uertex', 'uertice': 'uertex', 'uerticem': 'uertex',
        'uertices': 'uertex',
        'flauus': 'flauus', 'flauo': 'flauus', 'flauum': 'flauus',
        'flaua': 'flauus',
        'intonsus': 'intonsus', 'intonso': 'intonsus', 'intonsum': 'intonsus',
        'arma': 'arma', 'uirum': 'uir', 'cano': 'cano',
    }
    ok = 0
    issues = 0
    for form, expected in sorted(test_forms.items()):
        actual = merged.get(form, 'NOT FOUND')
        status = 'OK' if actual == expected else 'ISSUE'
        if status == 'OK':
            ok += 1
        else:
            issues += 1
        print(f"  {form:15s} → {actual:15s} (expected: {expected:15s}) [{status}]")
    print(f"\n  {ok} OK, {issues} issues")
    
    print("\nDone!")

if __name__ == '__main__':
    main()
