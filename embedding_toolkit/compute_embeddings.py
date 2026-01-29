#!/usr/bin/env python3
"""
Tesserae V6 Embedding Toolkit
Compute AI embeddings for classical texts offline.

Usage:
    python compute_embeddings.py corpus/la/vergil.aeneid.tess
    python compute_embeddings.py corpus/la/
    python compute_embeddings.py corpus/
"""

import os
import sys
import json
import re
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np

print("Loading AI models (this may take a minute on first run)...")
from sentence_transformers import SentenceTransformer

SPHILBERTA_MODEL = None
ENGLISH_MODEL = None

def get_model(language):
    """Load the appropriate model for the language."""
    global SPHILBERTA_MODEL, ENGLISH_MODEL
    
    if language in ('la', 'grc'):
        if SPHILBERTA_MODEL is None:
            print("Loading SPhilBERTa model for Latin/Greek...")
            SPHILBERTA_MODEL = SentenceTransformer('bowphs/SPhilBerta')
        return SPHILBERTA_MODEL
    else:
        if ENGLISH_MODEL is None:
            print("Loading all-MiniLM-L6-v2 model for English...")
            ENGLISH_MODEL = SentenceTransformer('all-MiniLM-L6-v2')
        return ENGLISH_MODEL

def parse_tess_file(filepath):
    """Parse a .tess file and extract lines with their references."""
    lines = []
    line_refs = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            match = re.match(r'<([^>]+)>\s*(.*)', line)
            if match:
                ref = match.group(1)
                text = match.group(2).strip()
                if text:
                    lines.append(text)
                    line_refs.append(ref)
    
    return lines, line_refs

def detect_language(filepath):
    """Detect language from file path."""
    path_str = str(filepath).lower()
    if '/la/' in path_str or '\\la\\' in path_str:
        return 'la'
    elif '/grc/' in path_str or '\\grc\\' in path_str:
        return 'grc'
    elif '/en/' in path_str or '\\en\\' in path_str:
        return 'en'
    else:
        return 'la'

def compute_embeddings_for_file(filepath, output_dir, batch_size=32):
    """Compute embeddings for a single .tess file."""
    filepath = Path(filepath)
    
    if not filepath.exists():
        print(f"  ERROR: File not found: {filepath}")
        return False
    
    if not filepath.suffix == '.tess':
        return False
    
    language = detect_language(filepath)
    text_name = filepath.stem
    
    lang_output_dir = Path(output_dir) / language
    lang_output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = lang_output_dir / f"{text_name}.npy"
    meta_file = lang_output_dir / f"{text_name}.meta.json"
    
    if output_file.exists():
        print(f"  SKIP: {text_name} (already computed)")
        return True
    
    print(f"  Processing: {text_name} ({language})...")
    
    lines, line_refs = parse_tess_file(filepath)
    
    if not lines:
        print(f"  WARNING: No lines found in {filepath}")
        return False
    
    model = get_model(language)
    
    print(f"    Computing embeddings for {len(lines)} lines...")
    embeddings = model.encode(
        lines,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True
    )
    
    np.save(output_file, embeddings)
    
    meta = {
        'text_name': text_name,
        'language': language,
        'num_lines': len(lines),
        'embedding_dim': embeddings.shape[1],
        'model': 'bowphs/SPhilBerta' if language in ('la', 'grc') else 'all-MiniLM-L6-v2',
        'computed_at': datetime.now().isoformat(),
        'source_file': str(filepath)
    }
    
    with open(meta_file, 'w') as f:
        json.dump(meta, f, indent=2)
    
    size_mb = output_file.stat().st_size / (1024 * 1024)
    print(f"    Saved: {output_file} ({size_mb:.1f} MB)")
    
    return True

def update_manifest(output_dir):
    """Update the manifest.json with all computed embeddings."""
    output_dir = Path(output_dir)
    manifest = {'texts': {}, 'updated_at': datetime.now().isoformat()}
    
    for lang_dir in output_dir.iterdir():
        if not lang_dir.is_dir():
            continue
        
        language = lang_dir.name
        
        for npy_file in lang_dir.glob('*.npy'):
            text_name = npy_file.stem
            meta_file = lang_dir / f"{text_name}.meta.json"
            
            if meta_file.exists():
                with open(meta_file) as f:
                    meta = json.load(f)
            else:
                embeddings = np.load(npy_file)
                meta = {
                    'num_lines': embeddings.shape[0],
                    'embedding_dim': embeddings.shape[1]
                }
            
            key = f"{language}/{text_name}"
            manifest['texts'][key] = {
                'file': str(npy_file.relative_to(output_dir)),
                'language': language,
                'num_lines': meta.get('num_lines', 0),
                'embedding_dim': meta.get('embedding_dim', 0)
            }
    
    manifest_file = output_dir / 'manifest.json'
    with open(manifest_file, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    print(f"\nManifest updated: {len(manifest['texts'])} texts indexed")

def find_tess_files(path):
    """Find all .tess files in a path (file or directory)."""
    path = Path(path)
    
    if path.is_file():
        if path.suffix == '.tess':
            return [path]
        return []
    
    if path.is_dir():
        return list(path.rglob('*.tess'))
    
    return []

def main():
    parser = argparse.ArgumentParser(
        description='Compute AI embeddings for Tesserae classical texts'
    )
    parser.add_argument(
        'input',
        help='Path to .tess file or directory containing .tess files'
    )
    parser.add_argument(
        '--output', '-o',
        default='embeddings',
        help='Output directory for embeddings (default: embeddings/)'
    )
    parser.add_argument(
        '--batch-size', '-b',
        type=int,
        default=32,
        help='Batch size for encoding (lower if running out of memory)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("TESSERAE V6 EMBEDDING TOOLKIT")
    print("=" * 60)
    
    tess_files = find_tess_files(args.input)
    
    if not tess_files:
        print(f"No .tess files found in: {args.input}")
        sys.exit(1)
    
    print(f"\nFound {len(tess_files)} text(s) to process")
    print(f"Output directory: {args.output}")
    print()
    
    success_count = 0
    skip_count = 0
    
    for filepath in sorted(tess_files):
        result = compute_embeddings_for_file(filepath, args.output, args.batch_size)
        if result:
            success_count += 1
    
    update_manifest(args.output)
    
    print()
    print("=" * 60)
    print(f"COMPLETE: {success_count} texts processed")
    print("=" * 60)
    print()
    print("Next steps:")
    print("1. Copy the 'embeddings/' folder to your Tesserae project")
    print("2. Place it at 'backend/embeddings/' in Replit")
    print("3. The semantic search will automatically use these embeddings")

if __name__ == '__main__':
    main()
