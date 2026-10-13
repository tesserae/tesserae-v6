#!/usr/bin/env python3
"""
Rebuild the embeddings manifest.json from actual .npy files on disk.

Fixes the manifest when files exist but aren't registered (e.g., the Feb 13
batch of 583 files that were computed but never added to the manifest).

Usage:
    python scripts/rebuild_embedding_manifest.py
    python scripts/rebuild_embedding_manifest.py --dry-run   # just report, don't write
"""
import sys
import os
import json
import time
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMBEDDINGS_DIR = os.path.join(PROJ_ROOT, 'backend', 'embeddings')
TEXTS_DIR = os.path.join(PROJ_ROOT, 'texts')
MANIFEST_FILE = os.path.join(EMBEDDINGS_DIR, 'manifest.json')


def find_corpus_texts():
    """Build a map of basename -> relative text path for all .tess files."""
    corpus = {}
    for lang in ['la', 'grc', 'en']:
        lang_dir = os.path.join(TEXTS_DIR, lang)
        if not os.path.exists(lang_dir):
            continue
        for f in os.listdir(lang_dir):
            if f.endswith('.tess'):
                basename = os.path.splitext(f)[0]
                corpus[basename] = {
                    'language': lang,
                    'rel_path': f'texts/{lang}/{f}',
                    'abs_path': os.path.join(lang_dir, f),
                }
    return corpus


def scan_embeddings():
    """Scan all .npy files in the embeddings directory."""
    found = {}
    for lang in ['la', 'grc', 'en']:
        lang_dir = os.path.join(EMBEDDINGS_DIR, lang)
        if not os.path.exists(lang_dir):
            continue
        for f in sorted(os.listdir(lang_dir)):
            if not f.endswith('.npy'):
                continue
            basename = os.path.splitext(f)[0]
            npy_path = os.path.join(lang_dir, f)
            found[basename] = {
                'language': lang,
                'file': f,
                'npy_path': npy_path,
                'mtime': os.path.getmtime(npy_path),
            }
    return found


def main():
    dry_run = '--dry-run' in sys.argv

    print("Rebuilding embeddings manifest from disk...\n")

    # Load existing manifest for reference
    old_manifest = {}
    if os.path.exists(MANIFEST_FILE):
        with open(MANIFEST_FILE, 'r') as f:
            old_manifest = json.load(f)
    old_texts = old_manifest.get('texts', {})
    print(f"Existing manifest: {len(old_texts)} entries")

    # Scan disk
    corpus = find_corpus_texts()
    embeddings = scan_embeddings()
    print(f"Corpus texts: {len(corpus)}")
    print(f"Embedding .npy files on disk: {len(embeddings)}")

    # Build new manifest
    new_texts = {}
    matched = 0
    orphaned = 0
    errors = 0

    for basename, emb_info in sorted(embeddings.items()):
        npy_path = emb_info['npy_path']
        lang = emb_info['language']

        # Try to match to corpus text
        if basename in corpus:
            text_key = corpus[basename]['rel_path']
            matched += 1
        else:
            # Try the absolute path format used in some old entries
            text_key = f"texts/{lang}/{basename}.tess"
            orphaned += 1

        # Load array to get shape
        try:
            arr = np.load(npy_path, mmap_mode='r')
            n_lines, embedding_dim = arr.shape
        except Exception as e:
            print(f"  ERROR loading {npy_path}: {e}")
            errors += 1
            continue

        # Check if we have existing metadata (preserve created date)
        created = None
        for old_key, old_val in old_texts.items():
            if old_val.get('file') == emb_info['file']:
                created = old_val.get('created')
                break
        if not created:
            # Use file modification time
            created = datetime.fromtimestamp(emb_info['mtime']).isoformat()

        new_texts[text_key] = {
            'language': lang,
            'n_lines': int(n_lines),
            'embedding_dim': int(embedding_dim),
            'file': emb_info['file'],
            'created': created,
        }

    # Summary
    total_lines = sum(t['n_lines'] for t in new_texts.values())
    by_lang = {}
    for t in new_texts.values():
        lang = t['language']
        by_lang[lang] = by_lang.get(lang, 0) + 1

    print(f"\nResults:")
    print(f"  Matched to corpus: {matched}")
    print(f"  Orphaned (no .tess): {orphaned}")
    print(f"  Errors: {errors}")
    print(f"  Total in new manifest: {len(new_texts)}")
    print(f"  Total lines: {total_lines:,}")
    print(f"  By language: {by_lang}")
    print(f"  (was {len(old_texts)} entries)")

    if dry_run:
        print("\n  --dry-run: not writing manifest")
        return

    # Write new manifest
    new_manifest = {
        'version': 1,
        'model': old_manifest.get('model', 'bowphs/SPhilBerta'),
        'english_model': 'bowphs/SPhilBerta',
        'texts': new_texts,
        'stats': {
            'total_texts': len(new_texts),
            'total_lines': total_lines,
            'last_updated': datetime.now().isoformat(),
        }
    }

    # Backup old manifest
    if os.path.exists(MANIFEST_FILE):
        backup = MANIFEST_FILE + '.bak'
        os.rename(MANIFEST_FILE, backup)
        print(f"\n  Backed up old manifest to {backup}")

    with open(MANIFEST_FILE, 'w') as f:
        json.dump(new_manifest, f, indent=2)
    print(f"  Wrote new manifest: {len(new_texts)} texts, {total_lines:,} lines")


if __name__ == '__main__':
    main()
