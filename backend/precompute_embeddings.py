"""
Tesserae V6 - Pre-compute Embeddings Script

Processes all texts in the corpus and saves their embeddings.
Run this once to enable fast semantic search.

Usage:
    python -m backend.precompute_embeddings [--language la|grc|en] [--force]
"""

import os
import sys
import glob
import time
from typing import List, Dict, Tuple

def get_all_corpus_texts() -> List[Dict]:
    """Get all .tess files from the texts directories."""
    texts_base = os.path.join(os.path.dirname(__file__), '..', 'texts')
    texts = []
    
    lang_map = {
        'la': 'la',
        'grc': 'grc', 
        'en': 'en'
    }
    
    for lang_dir, lang_code in lang_map.items():
        lang_path = os.path.join(texts_base, lang_dir)
        if not os.path.exists(lang_path):
            continue
        
        for tess_file in glob.glob(os.path.join(lang_path, '*.tess')):
            texts.append({
                'path': tess_file,
                'language': lang_code,
                'filename': os.path.basename(tess_file)
            })
    
    return texts

def parse_tess_file(file_path: str) -> List[Dict]:
    """Parse a .tess file and extract text units."""
    units = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '>' in line:
                    parts = line.split('>', 1)
                    if len(parts) == 2:
                        ref = parts[0].strip('<').strip()
                        text = parts[1].strip()
                        if text:
                            units.append({
                                'ref': ref,
                                'text': text
                            })
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
    
    return units

def compute_embeddings_for_text(text_path: str, language: str, 
                                 model, force: bool = False) -> Tuple[bool, int]:
    """
    Compute and save embeddings for a single text.
    
    Returns:
        Tuple of (success, n_lines)
    """
    from backend.embedding_storage import has_embeddings, save_embeddings
    
    if not force and has_embeddings(text_path, language):
        return True, 0
    
    units = parse_tess_file(text_path)
    if not units:
        print(f"  No units found in {text_path}")
        return False, 0
    
    texts = [u['text'] for u in units]
    refs = [u['ref'] for u in units]
    
    try:
        embeddings = model.encode(texts, show_progress_bar=False, batch_size=32)
        success = save_embeddings(text_path, language, embeddings, refs)
        return success, len(texts)
    except Exception as e:
        print(f"  Error computing embeddings: {e}")
        return False, 0

def precompute_all(language: str = None, force: bool = False, 
                   progress_callback=None) -> Dict:
    """
    Pre-compute embeddings for all corpus texts.
    
    Args:
        language: Filter to specific language ('la', 'grc', 'en') or None for all
        force: Re-compute even if embeddings exist
        progress_callback: Optional callback(current, total, text_name) for progress
        
    Returns:
        Statistics dict
    """
    from sentence_transformers import SentenceTransformer
    from backend.embedding_storage import get_embedding_stats
    
    texts = get_all_corpus_texts()
    
    if language:
        texts = [t for t in texts if t['language'] == language]
    
    print(f"Found {len(texts)} texts to process")
    
    models = {}
    stats = {
        'processed': 0,
        'skipped': 0,
        'failed': 0,
        'total_lines': 0,
        'start_time': time.time()
    }
    
    for lang in ['la', 'grc', 'en']:
        if language and lang != language:
            continue
        
        lang_texts = [t for t in texts if t['language'] == lang]
        if not lang_texts:
            continue
        
        model_name = 'all-MiniLM-L6-v2' if lang == 'en' else 'bowphs/SPhilBerta'
        
        if model_name not in models:
            print(f"\nLoading model {model_name}...")
            models[model_name] = SentenceTransformer(model_name)
            print(f"Model loaded")
        
        model = models[model_name]
        
        print(f"\nProcessing {len(lang_texts)} {lang} texts...")
        
        for i, text in enumerate(lang_texts):
            filename = text['filename']
            
            if progress_callback:
                progress_callback(i + 1, len(lang_texts), filename)
            
            success, n_lines = compute_embeddings_for_text(
                text['path'], text['language'], model, force
            )
            
            if n_lines > 0:
                stats['processed'] += 1
                stats['total_lines'] += n_lines
                print(f"  [{i+1}/{len(lang_texts)}] {filename}: {n_lines} lines")
            elif success:
                stats['skipped'] += 1
            else:
                stats['failed'] += 1
                print(f"  [{i+1}/{len(lang_texts)}] {filename}: FAILED")
    
    stats['elapsed_time'] = time.time() - stats['start_time']
    stats['storage'] = get_embedding_stats()
    
    return stats

def main():
    """Command-line interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Pre-compute embeddings for Tesserae corpus')
    parser.add_argument('--language', '-l', choices=['la', 'grc', 'en'],
                        help='Process only specified language')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Re-compute even if embeddings exist')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("TESSERAE V6 - Pre-compute Embeddings")
    print("=" * 60)
    
    stats = precompute_all(language=args.language, force=args.force)
    
    print("\n" + "=" * 60)
    print("COMPLETE")
    print("=" * 60)
    print(f"Processed: {stats['processed']} texts ({stats['total_lines']} lines)")
    print(f"Skipped (already computed): {stats['skipped']}")
    print(f"Failed: {stats['failed']}")
    print(f"Time: {stats['elapsed_time']:.1f} seconds")
    print(f"Storage: {stats['storage']['storage_size_mb']:.1f} MB")

if __name__ == '__main__':
    main()
