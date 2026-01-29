#!/usr/bin/env python3
"""
First1KGreek Ingestion Script

Downloads and converts Greek texts from the OpenGreekAndLatin First1KGreek repository
to .tess format for Tesserae.

Uses incremental HTTP downloads to avoid cloning the large repository.
"""

import os
import sys
import json
import re
import time
import argparse
import requests
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.ogl_converter import extract_metadata, extract_sections, normalize_text, generate_tess_id
from lxml import etree

CATALOG_URL = "https://raw.githubusercontent.com/OpenGreekAndLatin/First1KGreek/master/catalog.json"
BASE_RAW_URL = "https://raw.githubusercontent.com/OpenGreekAndLatin/First1KGreek/master/data"
TEXTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts', 'grc')
PROVENANCE_FILE = os.path.join(os.path.dirname(__file__), 'text_provenance.json')
CORPUS_STATUS_FILE = os.path.join(os.path.dirname(__file__), 'corpus_status.json')


def load_catalog() -> List[Dict]:
    """Download and parse the First1KGreek catalog."""
    print("Downloading First1KGreek catalog...")
    response = requests.get(CATALOG_URL, timeout=30)
    response.raise_for_status()
    data = response.json()
    catalog = data.get('catalog', [])
    print(f"Found {len(catalog)} works in catalog")
    return catalog


def urn_to_path(urn: str) -> str:
    """Convert a CTS URN to a file path.
    
    Example: urn:cts:greekLit:tlg0057.tlg010.1st1K-grc1
           → tlg0057/tlg010/tlg0057.tlg010.1st1K-grc1.xml
    """
    parts = urn.split(':')
    if len(parts) < 4:
        return ""
    work_id = parts[3]
    segments = work_id.split('.')
    if len(segments) < 3:
        return ""
    author_id = segments[0]
    work_num = segments[1]
    return f"{author_id}/{work_num}/{work_id}.xml"


def normalize_filename(author: str, title: str) -> str:
    """Create a normalized filename from author and title."""
    author = author.lower().strip()
    title = title.lower().strip()
    
    author = re.sub(r'[^\w\s]', '', author)
    title = re.sub(r'[^\w\s]', '', title)
    
    author = re.sub(r'\s+', '_', author)
    title = re.sub(r'\s+', '_', title)
    
    author = author[:30]
    title = title[:50]
    
    return f"{author}.{title}.tess"


def get_existing_texts() -> set:
    """Get set of existing Greek text filenames."""
    if not os.path.exists(TEXTS_DIR):
        os.makedirs(TEXTS_DIR, exist_ok=True)
        return set()
    return {f for f in os.listdir(TEXTS_DIR) if f.endswith('.tess')}


def check_duplicate(author: str, title: str, existing: set) -> bool:
    """Check if a similar text already exists in the corpus."""
    if not author or not title:
        return False
        
    author_lower = author.lower().strip()
    title_lower = title.lower().strip()
    
    if not author_lower or not title_lower:
        return False
    
    author_words = author_lower.split()
    title_words = title_lower.split()
    
    if not author_words or not title_words:
        return False
    
    for existing_file in existing:
        existing_lower = existing_file.lower()
        if author_words[0] in existing_lower and any(
            word in existing_lower for word in title_words[:2] if len(word) > 2
        ):
            return True
    return False


def download_and_convert(entry: Dict, existing: set, dry_run: bool = False) -> Tuple[bool, str]:
    """Download a single XML file and convert to .tess format.
    
    Returns: (success, message)
    """
    urn = entry.get('urn', '')
    author = entry.get('group_name', 'Unknown')
    title = entry.get('work_name', 'Unknown')
    wordcount = entry.get('wordcount', 0)
    
    if not urn:
        return False, "No URN"
    
    filepath = urn_to_path(urn)
    if not filepath:
        return False, "Invalid URN format"
    
    output_filename = normalize_filename(author, title)
    
    if output_filename in existing:
        return False, f"Already exists: {output_filename}"
    
    if check_duplicate(author, title, existing):
        return False, f"Probable duplicate: {author} - {title}"
    
    if dry_run:
        return True, f"Would add: {author} - {title} ({wordcount} words)"
    
    url = f"{BASE_RAW_URL}/{filepath}"
    
    try:
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        xml_content = response.content
    except requests.RequestException as e:
        return False, f"Download failed: {e}"
    
    try:
        root = etree.fromstring(xml_content)
        
        metadata = extract_metadata(root)
        metadata['author'] = author
        metadata['title'] = title
        metadata['language'] = 'grc'
        
        sections = extract_sections(root)
        
        if not sections:
            return False, "No text content extracted"
        
        tess_id = generate_tess_id(metadata)
        output_path = os.path.join(TEXTS_DIR, output_filename)
        
        lines = []
        for section in sections:
            citation = f"<{tess_id} {section['citation']}>"
            lines.append(f"{citation}\t{section['text']}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        if os.path.exists(output_path):
            return True, f"Added: {author} - {title} ({len(sections)} sections)"
        else:
            return False, "Output file not created"
            
    except Exception as e:
        return False, f"Conversion failed: {e}"


def update_provenance(new_texts: List[Dict]):
    """Update the provenance tracking file."""
    provenance = {"sources": {}, "texts": {}}
    if os.path.exists(PROVENANCE_FILE):
        with open(PROVENANCE_FILE, 'r') as f:
            provenance = json.load(f)
    
    if 'texts' not in provenance:
        provenance['texts'] = {}
    
    for text in new_texts:
        filename = text['filename']
        provenance['texts'][filename] = {
            'source': 'first1k_greek',
            'original_id': text.get('urn', ''),
            'author': text.get('author', ''),
            'title': text.get('title', ''),
            'date_added': datetime.now().isoformat()
        }
    
    with open(PROVENANCE_FILE, 'w') as f:
        json.dump(provenance, f, indent=2)


def update_corpus_status(stats: Dict):
    """Update the corpus status file with ingestion stats."""
    status = {}
    if os.path.exists(CORPUS_STATUS_FILE):
        with open(CORPUS_STATUS_FILE, 'r') as f:
            status = json.load(f)
    
    if 'ingestion_history' not in status:
        status['ingestion_history'] = []
    
    status['ingestion_history'].append({
        'date': datetime.now().isoformat()[:10],
        'source': 'first1k_greek',
        'source_name': 'First1KGreek - Open Greek and Latin Project',
        'source_url': 'https://github.com/OpenGreekAndLatin/First1KGreek',
        'description': 'Classical Greek texts from Homer to 250 CE',
        'language': 'grc',
        'files_in_catalog': stats['total'],
        'files_processed': stats['processed'],
        'new_texts_added': stats['added'],
        'duplicates_skipped': stats['duplicates'],
        'errors': stats['errors'],
        'notes': 'Incremental download via GitHub raw URLs',
        'embeddings_computed': False
    })
    
    texts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')
    status['summary'] = {
        'total_texts': {
            'la': len([f for f in os.listdir(os.path.join(texts_dir, 'la')) if f.endswith('.tess')]) if os.path.exists(os.path.join(texts_dir, 'la')) else 0,
            'grc': len([f for f in os.listdir(os.path.join(texts_dir, 'grc')) if f.endswith('.tess')]) if os.path.exists(os.path.join(texts_dir, 'grc')) else 0,
            'en': len([f for f in os.listdir(os.path.join(texts_dir, 'en')) if f.endswith('.tess')]) if os.path.exists(os.path.join(texts_dir, 'en')) else 0,
        }
    }
    
    with open(CORPUS_STATUS_FILE, 'w') as f:
        json.dump(status, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Ingest First1KGreek texts')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of texts to process')
    parser.add_argument('--min-words', type=int, default=500, help='Minimum word count (default: 500)')
    parser.add_argument('--author', type=str, default=None, help='Filter by author name')
    args = parser.parse_args()
    
    catalog = load_catalog()
    existing = get_existing_texts()
    print(f"Existing Greek texts: {len(existing)}")
    
    filtered = [
        e for e in catalog
        if e.get('wordcount', 0) >= args.min_words
        and (args.author is None or args.author.lower() in e.get('group_name', '').lower())
    ]
    print(f"Texts meeting criteria: {len(filtered)}")
    
    if args.limit:
        filtered = filtered[:args.limit]
    
    stats = {'total': len(filtered), 'processed': 0, 'added': 0, 'duplicates': 0, 'errors': 0}
    new_texts = []
    
    for i, entry in enumerate(filtered):
        success, message = download_and_convert(entry, existing, args.dry_run)
        stats['processed'] += 1
        
        if success:
            stats['added'] += 1
            if not args.dry_run:
                new_texts.append({
                    'filename': normalize_filename(entry.get('group_name', ''), entry.get('work_name', '')),
                    'urn': entry.get('urn', ''),
                    'author': entry.get('group_name', ''),
                    'title': entry.get('work_name', '')
                })
                existing.add(normalize_filename(entry.get('group_name', ''), entry.get('work_name', '')))
        elif 'duplicate' in message.lower() or 'already exists' in message.lower():
            stats['duplicates'] += 1
        else:
            stats['errors'] += 1
        
        print(f"[{i+1}/{len(filtered)}] {message}")
        
        if not args.dry_run and success:
            time.sleep(0.5)
    
    print("\n" + "="*50)
    print(f"SUMMARY")
    print(f"  Total in catalog: {stats['total']}")
    print(f"  Processed: {stats['processed']}")
    print(f"  New texts added: {stats['added']}")
    print(f"  Duplicates skipped: {stats['duplicates']}")
    print(f"  Errors: {stats['errors']}")
    
    if not args.dry_run and new_texts:
        print("\nUpdating provenance and corpus status...")
        update_provenance(new_texts)
        update_corpus_status(stats)
        print("Done!")


if __name__ == '__main__':
    main()
