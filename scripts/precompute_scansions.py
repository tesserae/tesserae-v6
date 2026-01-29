#!/usr/bin/env python3
"""
Pre-compute CLTK scansions for hendecasyllabic and elegiac Latin poetry.
Saves results to JSON file that can be merged with MQDQ scansions.

This script processes:
- Catullus carmina (hendecasyllables poems 1-60, elegiacs 65-116, hexameter 62-64)
- Tibullus elegies
- Propertius elegies  
- Martial epigrams (hendecasyllables)
- Ovid elegiac works (Amores, Ars, Fasti, Tristia, Heroides, Ex Ponto)
"""

import os
import sys
import json
import re
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEXTS_DIR = Path(__file__).parent.parent / 'texts' / 'la'
OUTPUT_FILE = Path(__file__).parent.parent / 'data' / 'scansion' / 'cltk_scansions.json'

HENDECASYLLABLE_TEXTS = [
    'catullus.carmina',
    'martial.epigrams',
]

ELEGIAC_TEXTS = [
    'tibullus.elegies',
    'propertius.elegies',
    'ovid.amores',
    'ovid.ars_amatoria',
    'ovid.fasti',
    'ovid.tristia',
    'ovid.heroides',
    'ovid.epistulae_ex_ponto',
]

CATULLUS_HENDECASYLLABLE_POEMS = set(range(1, 61))
CATULLUS_HEXAMETER_POEMS = {62, 63, 64}
CATULLUS_ELEGIAC_POEMS = set(range(65, 117)) - CATULLUS_HEXAMETER_POEMS

def get_scanner(meter_type):
    """Lazy-load the appropriate scanner"""
    if meter_type == 'hendecasyllable':
        from cltk.prosody.lat.hendecasyllable_scanner import HendecasyllableScanner
        return HendecasyllableScanner()
    elif meter_type == 'elegiac':
        from cltk.prosody.lat.pentameter_scanner import PentameterScanner
        return PentameterScanner()
    else:
        from cltk.prosody.lat.hexameter_scanner import HexameterScanner
        return HexameterScanner()

def parse_tess_file(filepath):
    """Parse a .tess file and yield (locus, text) tuples"""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'<([^>]+)>\s*(.*)', line)
            if match:
                locus = match.group(1)
                text = match.group(2)
                yield locus, text

def extract_line_ref(locus):
    """Extract line reference from locus like 'catu. carm. 30.9' -> '30.9'"""
    parts = locus.replace(' ', '').split('.')
    if len(parts) >= 4:
        return f"{parts[2]}.{parts[3]}"
    elif len(parts) >= 3:
        return parts[2]
    return None

def extract_poem_number(locus):
    """Extract poem number from locus like 'catu. carm. 30.9' -> 30"""
    parts = locus.replace(' ', '').split('.')
    if len(parts) >= 3:
        try:
            return int(parts[2])
        except ValueError:
            return None
    return None

def determine_catullus_meter(poem_num):
    """Determine meter type for Catullus poem"""
    if poem_num in CATULLUS_HENDECASYLLABLE_POEMS:
        return 'hendecasyllable'
    elif poem_num in CATULLUS_ELEGIAC_POEMS:
        return 'elegiac'
    elif poem_num in CATULLUS_HEXAMETER_POEMS:
        return 'hexameter'
    return None

def scan_text(text, scanner):
    """Scan a line of text and return scansion info"""
    try:
        result = scanner.scan(text)
        if hasattr(result, 'scansion') and result.scansion:
            is_valid = getattr(result, 'valid', False)
            raw_scansion = result.scansion.strip()
            pattern = raw_scansion.replace(' ', '')
            
            formatted = []
            for char in pattern.upper():
                if char == '-':
                    formatted.append('–')
                elif char == 'U':
                    formatted.append('∪')
                elif char == 'X':
                    formatted.append('×')
            
            return {
                'pattern': pattern,
                'scansion': ''.join(formatted),
                'valid': is_valid,
                'meter': 'H' if len(pattern) > 13 else 'F' if len(pattern) == 11 else 'D'
            }
    except Exception as e:
        print(f"  Error scanning: {e}")
    return None

def process_catullus():
    """Process Catullus carmina with mixed meters"""
    results = {'catullus.carmina': {'author': 'catullus', 'work': 'carmina', 'meter_type': 'mixed', 'lines': {}}}
    
    filepath = TEXTS_DIR / 'catullus.carmina.tess'
    if not filepath.exists():
        print(f"File not found: {filepath}")
        return results
    
    print(f"Processing Catullus carmina...")
    
    scanners = {}
    line_count = 0
    success_count = 0
    
    for locus, text in parse_tess_file(filepath):
        poem_num = extract_poem_number(locus)
        if poem_num is None:
            continue
            
        meter = determine_catullus_meter(poem_num)
        if meter is None or meter == 'hexameter':
            continue
            
        if meter not in scanners:
            print(f"  Loading {meter} scanner...")
            scanners[meter] = get_scanner(meter)
        
        line_ref = extract_line_ref(locus)
        if not line_ref:
            continue
        
        line_count += 1
        if line_count % 100 == 0:
            print(f"  Processed {line_count} lines...")
        
        scan_result = scan_text(text, scanners[meter])
        if scan_result and scan_result['valid']:
            results['catullus.carmina']['lines'][line_ref] = {
                'pattern': scan_result['pattern'],
                'scansion': scan_result['scansion'],
                'meter': scan_result['meter']
            }
            success_count += 1
    
    print(f"  Catullus: {success_count}/{line_count} lines scanned successfully")
    return results

def process_text_file(filepath, meter_type, work_key):
    """Process a single text file"""
    results = {work_key: {'author': work_key.split('.')[0], 'work': work_key.split('.')[1] if '.' in work_key else work_key, 'meter_type': meter_type, 'lines': {}}}
    
    if not filepath.exists():
        print(f"  File not found: {filepath}")
        return results
    
    print(f"  Loading {meter_type} scanner...")
    scanner = get_scanner(meter_type)
    
    line_count = 0
    success_count = 0
    
    for locus, text in parse_tess_file(filepath):
        line_ref = extract_line_ref(locus)
        if not line_ref:
            continue
        
        line_count += 1
        if line_count % 100 == 0:
            print(f"    Processed {line_count} lines...")
        
        scan_result = scan_text(text, scanner)
        if scan_result and scan_result['valid']:
            results[work_key]['lines'][line_ref] = {
                'pattern': scan_result['pattern'],
                'scansion': scan_result['scansion'],
                'meter': scan_result['meter']
            }
            success_count += 1
    
    print(f"    {work_key}: {success_count}/{line_count} lines scanned successfully")
    return results

def find_text_files(pattern):
    """Find text files matching a pattern"""
    files = []
    for f in TEXTS_DIR.glob('*.tess'):
        if pattern.replace('.', '_') in f.stem.replace('.', '_') or pattern in f.stem:
            files.append(f)
    return files

def main():
    print("Pre-computing CLTK scansions for hendecasyllabic and elegiac poetry")
    print("=" * 60)
    
    all_results = {}
    
    catullus_results = process_catullus()
    all_results.update(catullus_results)
    
    for text_id in ELEGIAC_TEXTS:
        print(f"\nProcessing {text_id}...")
        files = find_text_files(text_id)
        if not files:
            print(f"  No files found for {text_id}")
            continue
        
        for filepath in files:
            work_key = filepath.stem
            results = process_text_file(filepath, 'elegiac', work_key)
            all_results.update(results)
    
    for text_id in HENDECASYLLABLE_TEXTS:
        if text_id == 'catullus.carmina':
            continue
        print(f"\nProcessing {text_id}...")
        files = find_text_files(text_id)
        if not files:
            print(f"  No files found for {text_id}")
            continue
        
        for filepath in files:
            work_key = filepath.stem
            results = process_text_file(filepath, 'hendecasyllable', work_key)
            all_results.update(results)
    
    print(f"\n{'=' * 60}")
    print(f"Saving results to {OUTPUT_FILE}...")
    
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    total_lines = sum(len(v.get('lines', {})) for v in all_results.values())
    print(f"Done! Saved {total_lines} scansions across {len(all_results)} works.")

if __name__ == '__main__':
    main()
