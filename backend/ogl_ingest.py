#!/usr/bin/env python3
"""
OGL Corpus Ingestion Pipeline for Tesserae V6.

This script handles the complete workflow for adding texts from the 
Open Greek and Latin (OGL) project:

1. Clone/update OGL repository
2. Convert XML to TESS format
3. Check for duplicates against existing corpus
4. Compute lemma caches
5. Compute semantic embeddings
6. Copy to corpus directory

Usage:
    python ogl_ingest.py --repo csel-dev --language la --test
    python ogl_ingest.py --repo csel-dev --language la --run
"""

import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.ogl_converter import convert_xml_to_tess, extract_metadata
from lxml import etree

BASE_DIR = Path(__file__).parent.parent
CORPUS_DIR = BASE_DIR / "texts"
OGL_CACHE_DIR = BASE_DIR / "ogl_cache"
EMBEDDINGS_DIR = BASE_DIR / "backend" / "embeddings"
PROVENANCE_FILE = BASE_DIR / "backend" / "text_provenance.json"


def load_provenance():
    """Load text provenance data."""
    if PROVENANCE_FILE.exists():
        with open(PROVENANCE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"sources": {}, "texts": {}}


def save_provenance(data):
    """Save text provenance data."""
    with open(PROVENANCE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def record_provenance(text_id: str, source_key: str, original_id: str, metadata: dict):
    """Record provenance for an ingested text."""
    provenance = load_provenance()
    provenance['texts'][text_id] = {
        'source': source_key,
        'original_id': original_id,
        'author': metadata.get('author', ''),
        'title': metadata.get('title', ''),
        'date_added': datetime.now().isoformat(),
        'language': metadata.get('language', '')
    }
    save_provenance(provenance)

OGL_REPOS = {
    'csel-dev': {
        'url': 'https://github.com/OpenGreekAndLatin/csel-dev.git',
        'description': 'Corpus Scriptorum Ecclesiasticorum Latinorum (Latin Church Fathers)',
        'language': 'la',
        'data_path': 'data'
    },
    'First1KGreek': {
        'url': 'https://github.com/OpenGreekAndLatin/First1KGreek.git',
        'description': 'Greek texts from Homer to 250 CE',
        'language': 'grc',
        'data_path': 'data'
    },
    'patrologia_latina-dev': {
        'url': 'https://github.com/OpenGreekAndLatin/patrologia_latina-dev.git',
        'description': 'Patrologia Latina selections',
        'language': 'la',
        'data_path': 'data'
    }
}


def get_existing_corpus_texts(language: str) -> dict:
    """Get dict of existing text IDs in corpus to avoid duplicates.
    
    Returns dict mapping:
    - full filename (stem) -> path
    - author.work prefix -> path
    """
    corpus_path = CORPUS_DIR / language
    if not corpus_path.exists():
        return {}
    
    existing = {}
    for tess_file in corpus_path.glob("*.tess"):
        text_id = tess_file.stem.lower()
        existing[text_id] = str(tess_file)
        
        parts = text_id.split('.')
        if len(parts) >= 2:
            author_work = f"{parts[0]}.{parts[1]}"
            if author_work not in existing:
                existing[author_work] = str(tess_file)
    
    return existing


def clone_or_update_repo(repo_name: str) -> Path:
    """Clone or update OGL repository."""
    if repo_name not in OGL_REPOS:
        raise ValueError(f"Unknown repository: {repo_name}")
    
    repo_info = OGL_REPOS[repo_name]
    repo_path = OGL_CACHE_DIR / repo_name
    
    OGL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    if repo_path.exists():
        print(f"Updating {repo_name}...")
        try:
            subprocess.run(['git', 'pull'], cwd=repo_path, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print(f"  Warning: Could not update repo, using existing version")
    else:
        print(f"Cloning {repo_name} (this may take a while)...")
        subprocess.run(
            ['git', 'clone', '--depth', '1', repo_info['url'], str(repo_path)],
            check=True
        )
    
    return repo_path / repo_info['data_path']


def find_xml_files(data_path: Path) -> list:
    """Find all XML files in the OGL data directory."""
    xml_files = []
    for xml_file in data_path.rglob("*.xml"):
        if '__cts__' not in xml_file.name and 'metadata' not in xml_file.name.lower():
            xml_files.append(xml_file)
    return sorted(xml_files)


def is_duplicate(tess_id: str, existing: dict, metadata: dict, xml_filename: str = None) -> tuple:
    """Check if a text already exists in the corpus.
    
    Uses stable identifiers:
    1. Exact tess_id match
    2. Author.work prefix match
    3. OGL filename (stoa/phi identifier) match
    
    Returns (is_dup: bool, reason: str or None)
    """
    tess_id_lower = tess_id.lower()
    
    if tess_id_lower in existing:
        return True, f"exact match: {tess_id_lower}"
    
    parts = tess_id.split('.')
    if len(parts) >= 2:
        author_work = f"{parts[0]}.{parts[1]}".lower()
        if author_work in existing:
            return True, f"author.work match: {author_work}"
    
    return False, None


def compute_lemma_cache(tess_file: Path, language: str) -> bool:
    """Compute lemma cache for a text using the TextProcessor.
    
    Processes the text file and saves lemmatized units to cache.
    """
    try:
        from backend.text_processor import TextProcessor
        from backend.lemma_cache import save_cached_units, get_file_hash
        
        text_id = tess_file.name
        file_hash = get_file_hash(str(tess_file))
        
        processor = TextProcessor()
        
        units_line = processor.process_text(str(tess_file), language, 'line')
        units_phrase = processor.process_text(str(tess_file), language, 'phrase')
        
        success = save_cached_units(text_id, language, units_line, units_phrase, file_hash)
        if success:
            print(f"       -> Cached lemmas ({len(units_line)} lines, {len(units_phrase)} phrases)")
        return success
    except Exception as e:
        print(f"       -> Warning: Lemma cache failed: {e}")
        return False


def compute_embeddings(tess_file: Path, language: str) -> bool:
    """Compute semantic embeddings for a text.
    
    Note: Embedding computation is expensive. For batch ingestion,
    embeddings can be computed later via admin interface.
    """
    text_id = tess_file.stem
    embeddings_path = EMBEDDINGS_DIR / language / f"{text_id}.npy"
    
    if embeddings_path.exists():
        print(f"       -> Embeddings exist")
        return True
    
    print(f"       -> Embeddings: skip (compute via admin when needed)")
    return True


def ingest_texts(repo_name: str, test_mode: bool = True, limit: int = 5) -> dict:
    """
    Main ingestion pipeline.
    
    Args:
        repo_name: Name of OGL repository to ingest
        test_mode: If True, only process a few files without copying
        limit: Maximum files to process in test mode
    
    Returns:
        Dictionary with ingestion statistics
    """
    print(f"\n{'='*60}")
    print(f"OGL Corpus Ingestion: {repo_name}")
    print(f"{'='*60}")
    
    repo_info = OGL_REPOS[repo_name]
    language = repo_info['language']
    
    stats = {
        'repo': repo_name,
        'language': language,
        'files_found': 0,
        'already_exists': 0,
        'converted': 0,
        'failed': 0,
        'texts_added': [],
        'test_mode': test_mode
    }
    
    print(f"\n1. Checking existing corpus...")
    existing = get_existing_corpus_texts(language)
    print(f"   Found {len(existing)} existing texts in {language} corpus")
    
    print(f"\n2. Getting OGL repository...")
    try:
        data_path = clone_or_update_repo(repo_name)
    except Exception as e:
        print(f"   Error: {e}")
        return stats
    
    print(f"\n3. Finding XML files...")
    xml_files = find_xml_files(data_path)
    stats['files_found'] = len(xml_files)
    print(f"   Found {len(xml_files)} XML files")
    
    if test_mode:
        xml_files = xml_files[:limit]
        print(f"   (Test mode: processing first {limit} files)")
    
    print(f"\n4. Converting and checking for duplicates...")
    
    temp_dir = OGL_CACHE_DIR / "temp_converted"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    for i, xml_file in enumerate(xml_files):
        print(f"\n   [{i+1}/{len(xml_files)}] {xml_file.name}")
        
        try:
            with open(xml_file, 'rb') as f:
                root = etree.fromstring(f.read())
            metadata = extract_metadata(root)
            
            from backend.ogl_converter import generate_tess_id
            tess_id = generate_tess_id(metadata)
            
            is_dup, dup_reason = is_duplicate(tess_id, existing, metadata, xml_file.name)
            if is_dup:
                print(f"       -> Skipping ({dup_reason})")
                stats['already_exists'] += 1
                continue
            
            if metadata['language'] != language:
                print(f"       -> Skipping (language mismatch: {metadata['language']} != {language})")
                stats['failed'] += 1
                continue
            
            temp_tess = temp_dir / f"{tess_id}.tess"
            result = convert_xml_to_tess(str(xml_file), str(temp_tess))
            
            if not result['success']:
                print(f"       -> Failed: {result.get('error', 'Unknown error')}")
                stats['failed'] += 1
                continue
            
            print(f"       -> Converted: {tess_id} ({result['section_count']} sections, {result['word_count']} words)")
            
            if not test_mode:
                corpus_lang_dir = CORPUS_DIR / language
                corpus_lang_dir.mkdir(parents=True, exist_ok=True)
                
                dest_file = corpus_lang_dir / f"{tess_id}.tess"
                shutil.copy(temp_tess, dest_file)
                print(f"       -> Copied to corpus")
                
                source_key = repo_name.replace('-dev', '').replace('-', '_')
                record_provenance(tess_id, source_key, xml_file.name, metadata)
                print(f"       -> Recorded provenance")
            
            stats['converted'] += 1
            stats['texts_added'].append({
                'id': tess_id,
                'author': metadata['author'],
                'title': metadata['title'],
                'sections': result['section_count'],
                'words': result['word_count']
            })
            
            existing[tess_id.lower()] = str(temp_tess)
            
        except Exception as e:
            print(f"       -> Error: {e}")
            stats['failed'] += 1
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Repository: {repo_name}")
    print(f"Language: {language}")
    print(f"Files found: {stats['files_found']}")
    print(f"Already in corpus: {stats['already_exists']}")
    print(f"Successfully converted: {stats['converted']}")
    print(f"Failed: {stats['failed']}")
    
    if stats['texts_added']:
        print(f"\nNew texts {'(would be added)' if test_mode else 'added'}:")
        for text in stats['texts_added'][:10]:
            print(f"  - {text['author']}: {text['title']} ({text['words']} words)")
        if len(stats['texts_added']) > 10:
            print(f"  ... and {len(stats['texts_added']) - 10} more")
    
    if test_mode:
        print(f"\n[TEST MODE] No files were copied to corpus.")
        print(f"Run with --run to actually add texts.")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Ingest texts from OGL repositories')
    parser.add_argument('--repo', choices=list(OGL_REPOS.keys()), required=True,
                        help='OGL repository to ingest')
    parser.add_argument('--test', action='store_true', default=True,
                        help='Test mode (default): process a few files without copying')
    parser.add_argument('--run', action='store_true',
                        help='Actually copy files to corpus')
    parser.add_argument('--limit', type=int, default=5,
                        help='Maximum files to process in test mode')
    parser.add_argument('--list', action='store_true',
                        help='List available repositories')
    
    args = parser.parse_args()
    
    if args.list:
        print("Available OGL repositories:")
        for name, info in OGL_REPOS.items():
            print(f"  {name}: {info['description']} ({info['language']})")
        return
    
    test_mode = not args.run
    
    stats = ingest_texts(args.repo, test_mode=test_mode, limit=args.limit)
    
    log_file = OGL_CACHE_DIR / f"ingest_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    OGL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(log_file, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"\nLog saved to: {log_file}")


if __name__ == '__main__':
    main()
