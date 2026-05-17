#!/usr/bin/env python3
"""
Extract Ghalib's Diwan from Urdu Wikisource.

The Diwan-e-Ghalib is organized by radif (rhyme-letter) on ur.wikisource.org.
We download each section via the MediaWiki API and extract the Urdu poetry text.

Output: texts/ur/ghalib.diwan.tess
"""

import json
import os
import re
import sys
import time
import urllib.request

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTS_DIR = os.path.join(PROJECT_ROOT, 'texts', 'ur')

# Wikisource API
API_URL = 'https://ur.wikisource.org/w/api.php'

# Pages to fetch (radif sections of Diwan-e-Ghalib)
GHALIB_PAGES = [
    'دیوان غالب/غزلیات/ردیف ے',
    'دیوان غالب/غزلیات/ردیف ن',
    'دیوان غالب/غزلیات/ردیف و',
    'دیوان غالب/غزلیات/ردیف د تا ز',
    'دیوان غالب/غزلیات/ردیف الف تا خ',
    'دیوان غالب/غزلیات/ردیف س تا غ',
    'دیوان غالب/غزلیات/ردیف ف تا م',
]


def fetch_page_text(title):
    """Fetch plain text content of a Wikisource page."""
    params = {
        'action': 'query',
        'titles': title,
        'prop': 'extracts',
        'explaintext': '1',
        'format': 'json',
    }
    url = API_URL + '?' + '&'.join(f'{k}={urllib.request.quote(str(v))}' for k, v in params.items())
    req = urllib.request.Request(url, headers={
        'User-Agent': 'TesseraeV6/1.0 (academic research; ncoffee@buffalo.edu)'
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            pages = data.get('query', {}).get('pages', {})
            for pid, page in pages.items():
                if pid != '-1':
                    return page.get('extract', '')
    except Exception as e:
        print(f"    Error fetching {title}: {e}")
    return ''


def fetch_page_wikitext(title):
    """Fetch raw wikitext of a page (better for extracting verse structure)."""
    params = {
        'action': 'query',
        'titles': title,
        'prop': 'revisions',
        'rvprop': 'content',
        'rvslots': 'main',
        'format': 'json',
    }
    url = API_URL + '?' + '&'.join(f'{k}={urllib.request.quote(str(v))}' for k, v in params.items())
    req = urllib.request.Request(url, headers={
        'User-Agent': 'TesseraeV6/1.0 (academic research; ncoffee@buffalo.edu)'
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            pages = data.get('query', {}).get('pages', {})
            for pid, page in pages.items():
                if pid != '-1':
                    revs = page.get('revisions', [])
                    if revs:
                        return revs[0].get('slots', {}).get('main', {}).get('*', '')
    except Exception as e:
        print(f"    Error fetching wikitext for {title}: {e}")
    return ''


def extract_verses_from_wikitext(wikitext):
    """Extract Urdu verse lines from Wikisource wikitext."""
    lines = []
    for line in wikitext.split('\n'):
        line = line.strip()
        # Skip headers, templates, categories, empty lines
        if not line or line.startswith('=') or line.startswith('{') or line.startswith('[') or line.startswith('<'):
            continue
        if line.startswith('__') or line.startswith('|'):
            continue
        # Skip lines that are mostly Latin characters (metadata, notes)
        urdu_chars = sum(1 for c in line if '\u0600' <= c <= '\u06FF')
        if urdu_chars < len(line) * 0.3:
            continue
        # Clean up wiki markup
        line = re.sub(r"'''?", '', line)  # bold/italic
        line = re.sub(r'\[\[([^\]|]+\|)?([^\]]+)\]\]', r'\2', line)  # wiki links
        line = re.sub(r'<[^>]+>', '', line)  # HTML tags
        line = line.strip()
        if line and len(line) > 5:
            lines.append(line)
    return lines


def extract_verses_from_plaintext(text):
    """Extract verses from plain text (fallback if wikitext parsing fails)."""
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        if not line:
            continue
        urdu_chars = sum(1 for c in line if '\u0600' <= c <= '\u06FF')
        if urdu_chars < 5:
            continue
        lines.append(line)
    return lines


def main():
    os.makedirs(TEXTS_DIR, exist_ok=True)
    all_lines = []
    ghazal_num = 0

    print("Extracting Ghalib's Diwan from Urdu Wikisource...")

    for page_title in GHALIB_PAGES:
        print(f"  Fetching: {page_title}...")
        time.sleep(1)  # be polite to Wikisource

        # Try wikitext first (better structure), fall back to plaintext
        wikitext = fetch_page_wikitext(page_title)
        if wikitext:
            verses = extract_verses_from_wikitext(wikitext)
        else:
            plaintext = fetch_page_text(page_title)
            verses = extract_verses_from_plaintext(plaintext)

        if not verses:
            print(f"    No verses found")
            continue

        # Group into ghazals (separated by blank-line-like gaps or numbered sections)
        # For simplicity, treat each verse line as a couplet
        section_name = page_title.split('/')[-1].replace('ردیف ', 'radif_')
        for i, verse in enumerate(verses, 1):
            ref = f'<ghalib.diwan.{section_name}.{i}>'
            all_lines.append(f'{ref}\t{verse}')

        print(f"    {len(verses)} verse lines extracted")

    if all_lines:
        filepath = os.path.join(TEXTS_DIR, 'ghalib.diwan.tess')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(all_lines) + '\n')
        print(f"\n  -> ghalib.diwan.tess: {len(all_lines)} lines")
    else:
        print("\n  No Ghalib text extracted. Wikisource may be unavailable.")

    print(f"Total: {len(all_lines)} lines")


if __name__ == '__main__':
    main()
