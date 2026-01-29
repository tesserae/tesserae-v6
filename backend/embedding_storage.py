"""
Tesserae V6 - Pre-computed Embedding Storage

Stores and loads pre-computed embeddings for all corpus texts.
This enables fast semantic search by avoiding real-time embedding computation.

Storage format:
- embeddings/la/<author>/<work>.npy - Latin embeddings
- embeddings/grc/<author>/<work>.npy - Greek embeddings  
- embeddings/en/<author>/<work>.npy - English embeddings
- embeddings/manifest.json - Index of all computed embeddings with metadata
"""

import os
import json
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import hashlib

EMBEDDINGS_DIR = os.path.join(os.path.dirname(__file__), 'embeddings')
MANIFEST_FILE = os.path.join(EMBEDDINGS_DIR, 'manifest.json')

_manifest_cache = None

def get_embedding_path(text_path: str, language: str) -> str:
    """Get the storage path for a text's embeddings."""
    basename = os.path.splitext(os.path.basename(text_path))[0]
    lang_dir = os.path.join(EMBEDDINGS_DIR, language)
    os.makedirs(lang_dir, exist_ok=True)
    return os.path.join(lang_dir, f"{basename}.npy")

def get_metadata_path(text_path: str, language: str) -> str:
    """Get the metadata path for a text's embeddings."""
    basename = os.path.splitext(os.path.basename(text_path))[0]
    lang_dir = os.path.join(EMBEDDINGS_DIR, language)
    return os.path.join(lang_dir, f"{basename}.meta.json")

def load_manifest() -> Dict:
    """Load the embeddings manifest."""
    global _manifest_cache
    if _manifest_cache is not None:
        return _manifest_cache
    
    if os.path.exists(MANIFEST_FILE):
        try:
            with open(MANIFEST_FILE, 'r') as f:
                _manifest_cache = json.load(f)
                return _manifest_cache
        except:
            pass
    
    _manifest_cache = {
        'version': 1,
        'model': 'bowphs/SPhilBerta',
        'english_model': 'all-MiniLM-L6-v2',
        'texts': {},
        'stats': {
            'total_texts': 0,
            'total_lines': 0,
            'last_updated': None
        }
    }
    return _manifest_cache

def save_manifest():
    """Save the embeddings manifest."""
    global _manifest_cache
    if _manifest_cache is None:
        return
    
    os.makedirs(EMBEDDINGS_DIR, exist_ok=True)
    _manifest_cache['stats']['last_updated'] = datetime.now().isoformat()
    
    with open(MANIFEST_FILE, 'w') as f:
        json.dump(_manifest_cache, f, indent=2)

def invalidate_manifest_cache():
    """Force reload of manifest on next access."""
    global _manifest_cache
    _manifest_cache = None

def save_embeddings(text_path: str, language: str, embeddings: np.ndarray, 
                    line_refs: List[str] = None) -> bool:
    """
    Save pre-computed embeddings for a text.
    
    Args:
        text_path: Path to the original .tess file
        language: Language code ('la', 'grc', 'en')
        embeddings: NumPy array of shape (n_lines, embedding_dim)
        line_refs: Optional list of line references for verification
        
    Returns:
        True if saved successfully
    """
    try:
        emb_path = get_embedding_path(text_path, language)
        meta_path = get_metadata_path(text_path, language)
        
        np.save(emb_path, embeddings)
        
        metadata = {
            'text_path': text_path,
            'language': language,
            'n_lines': embeddings.shape[0],
            'embedding_dim': embeddings.shape[1],
            'created': datetime.now().isoformat(),
            'line_refs': line_refs[:10] if line_refs else None
        }
        
        with open(meta_path, 'w') as f:
            json.dump(metadata, f)
        
        manifest = load_manifest()
        manifest['texts'][text_path] = {
            'language': language,
            'n_lines': embeddings.shape[0],
            'embedding_dim': embeddings.shape[1],
            'file': os.path.basename(emb_path),
            'created': metadata['created']
        }
        manifest['stats']['total_texts'] = len(manifest['texts'])
        manifest['stats']['total_lines'] = sum(t['n_lines'] for t in manifest['texts'].values())
        save_manifest()
        
        return True
        
    except Exception as e:
        print(f"Error saving embeddings for {text_path}: {e}")
        return False

def load_embeddings(text_path: str, language: str) -> Optional[np.ndarray]:
    """
    Load pre-computed embeddings for a text.
    
    Args:
        text_path: Path to the original .tess file
        language: Language code
        
    Returns:
        NumPy array of embeddings or None if not found
    """
    emb_path = get_embedding_path(text_path, language)
    
    if not os.path.exists(emb_path):
        return None
    
    try:
        # Explicitly disable memory mapping to avoid I/O errors on constrained VMs
        # allow_pickle=False for security, mmap_mode=None to load fully into memory
        return np.load(emb_path, mmap_mode=None, allow_pickle=False)
    except Exception as e:
        print(f"Error loading embeddings from {emb_path}: {e}")
        # Try alternative loading approach
        try:
            with open(emb_path, 'rb') as f:
                return np.load(f, allow_pickle=False)
        except Exception as e2:
            print(f"Fallback loading also failed: {e2}")
            return None

def has_embeddings(text_path: str, language: str) -> bool:
    """Check if embeddings exist for a text."""
    emb_path = get_embedding_path(text_path, language)
    return os.path.exists(emb_path)

def get_embedding_stats() -> Dict:
    """Get statistics about pre-computed embeddings."""
    manifest = load_manifest()
    
    by_language = {'la': 0, 'grc': 0, 'en': 0}
    lines_by_language = {'la': 0, 'grc': 0, 'en': 0}
    
    for text_path, info in manifest['texts'].items():
        lang = info.get('language', 'la')
        by_language[lang] = by_language.get(lang, 0) + 1
        lines_by_language[lang] = lines_by_language.get(lang, 0) + info.get('n_lines', 0)
    
    storage_size = 0
    if os.path.exists(EMBEDDINGS_DIR):
        for root, dirs, files in os.walk(EMBEDDINGS_DIR):
            for f in files:
                storage_size += os.path.getsize(os.path.join(root, f))
    
    return {
        'total_texts': manifest['stats'].get('total_texts', 0),
        'total_lines': manifest['stats'].get('total_lines', 0),
        'by_language': by_language,
        'lines_by_language': lines_by_language,
        'storage_size_mb': round(storage_size / (1024 * 1024), 2),
        'last_updated': manifest['stats'].get('last_updated'),
        'model': manifest.get('model', 'unknown'),
        'english_model': manifest.get('english_model', 'unknown')
    }

def delete_embeddings(text_path: str, language: str) -> bool:
    """Delete embeddings for a text."""
    try:
        emb_path = get_embedding_path(text_path, language)
        meta_path = get_metadata_path(text_path, language)
        
        if os.path.exists(emb_path):
            os.remove(emb_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        
        manifest = load_manifest()
        if text_path in manifest['texts']:
            del manifest['texts'][text_path]
            manifest['stats']['total_texts'] = len(manifest['texts'])
            manifest['stats']['total_lines'] = sum(t['n_lines'] for t in manifest['texts'].values())
            save_manifest()
        
        return True
    except Exception as e:
        print(f"Error deleting embeddings for {text_path}: {e}")
        return False

def clear_all_embeddings() -> bool:
    """Delete all pre-computed embeddings."""
    global _manifest_cache
    
    try:
        import shutil
        if os.path.exists(EMBEDDINGS_DIR):
            shutil.rmtree(EMBEDDINGS_DIR)
        
        _manifest_cache = None
        os.makedirs(EMBEDDINGS_DIR, exist_ok=True)
        
        return True
    except Exception as e:
        print(f"Error clearing embeddings: {e}")
        return False

def list_missing_embeddings(corpus_texts: List[Dict]) -> List[Dict]:
    """
    Find texts in the corpus that don't have pre-computed embeddings.
    
    Args:
        corpus_texts: List of text dicts with 'path' and 'language' fields
        
    Returns:
        List of texts without embeddings
    """
    manifest = load_manifest()
    missing = []
    
    for text in corpus_texts:
        text_path = text.get('path', '')
        language = text.get('language', 'la')
        
        if text_path not in manifest['texts']:
            missing.append(text)
    
    return missing
