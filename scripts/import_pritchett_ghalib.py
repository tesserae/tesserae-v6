#!/usr/bin/env python3
"""
Import Ghalib's complete Diwan from Frances Pritchett's website
(franpritchett.com/00ghalib/) into Tesserae .tess format.

The site stores poetry in a custom Roman transliteration. This script:
1. Scrapes ghazal index pages to get verse text in Pritchett's encoding
2. Converts the encoding to Urdu script using the site's own mapping rules
3. Writes .tess files organized by ghazal number

The ghazals themselves are public domain (Ghalib d. 1869).
Source: Frances Pritchett, "A Desertful of Roses," Columbia University.
"""

import os
import re
import sys
import time
import urllib.request
from html.parser import HTMLParser

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTS_DIR = os.path.join(PROJECT_ROOT, 'texts', 'ur')
BASE_URL = "https://franpritchett.com/00ghalib"

# ============================================================================
# Pritchett encoding -> Urdu script converter
# Based on the mapping in franpritchett.com/script/main-tle2U4VR.js
# ============================================================================

# Basic consonant mappings (Pritchett encoding -> Urdu character)
CONSONANTS = {
    # IMPORTANT: Order matters for matching -- longest first
    # Aspirated consonants (3 chars)
    ';Th': 'ٹھ', ';Dh': 'ڈھ', ';Rh': 'ڑھ',
    # Digraphs and special consonants (2 chars)
    'sh': 'ش', 'ch': 'چ', 'bh': 'بھ', 'ph': 'پھ', 'th': 'تھ',
    'jh': 'جھ', 'dh': 'دھ', 'kh': 'کھ', 'gh': 'گھ', 'nh': 'نہ',
    'zh': 'ژ', '.s': 'ص', '.z': 'ض', '.r': 'ر', ':t': 'ط', ':z': 'ظ',
    ';T': 'ٹ', ';D': 'ڈ', ';R': 'ڑ', ';h': 'ح', ';x': 'خ',
    ';G': 'غ', ';N': 'ں', ';s': 'ث', ';z': 'ذ', ';m': 'ں',
    '((': 'ع', '))': 'ئ',
    # Single consonants
    'b': 'ب', 'p': 'پ', 't': 'ت', 's': 'س', 'j': 'ج',
    'd': 'د', 'r': 'ر', 'z': 'ز', 'f': 'ف', 'q': 'ق',
    'k': 'ک', 'g': 'گ', 'l': 'ل', 'm': 'م', 'n': 'ن',
    'v': 'و', 'w': 'و', 'h': 'ہ', 'y': 'ی',
}

# Sorted by length (longest first) for matching
CONSONANT_KEYS = sorted(CONSONANTS.keys(), key=len, reverse=True)

# Vowel mappings
VOWELS = {
    'aa': 'ا', 'ii': 'ی', 'uu': 'و',
    'a': '', 'i': '', 'u': '',  # short vowels often unmarked in Urdu
    'e': 'ے', 'o': 'و', 'ai': 'ای', 'au': 'او',
}

# Special symbols
SPECIAL = {
    '))': 'ئ', '((': 'ع', ';N': 'ں', ';aa': 'ٰ',
    ',': '،', '--': '۔', '?': '؟', ';': '؛',
}


def pritchett_to_urdu(text):
    """Convert Pritchett's custom encoding to Urdu script.

    This is a simplified converter that handles the most common patterns.
    It won't be perfect on every edge case but should produce readable
    Urdu text suitable for lemmatization and matching.
    """
    if not text:
        return ''

    # Clean up HTML entities and formatting
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = re.sub(r'<[^>]+>', '', text)  # strip any HTML tags
    text = text.strip()

    # Handle word-by-word
    words = text.split()
    urdu_words = []

    for word in words:
        # Skip pure punctuation
        if word in (',', '.', '!', '?', '--', ';', ':'):
            urdu_words.append(SPECIAL.get(word, word))
            continue

        urdu_word = _convert_word(word)
        if urdu_word:
            urdu_words.append(urdu_word)

    return ' '.join(urdu_words)


def _convert_word(word):
    """Convert a single word from Pritchett encoding to Urdu."""
    result = []
    i = 0
    word_len = len(word)

    # Build combined lookup sorted by length (longest first)
    all_mappings = {}
    all_mappings.update(SPECIAL)
    all_mappings.update(CONSONANTS)
    all_mappings.update(VOWELS)
    sorted_keys = sorted(all_mappings.keys(), key=len, reverse=True)

    while i < word_len:
        matched = False

        for key in sorted_keys:
            klen = len(key)
            if i + klen <= word_len and word[i:i+klen] == key:
                result.append(all_mappings[key])
                i += klen
                matched = True
                break

        if not matched:
            ch = word[i]
            if ch == '-':
                pass  # izafat separator
            elif ch == '`' or ch == "'":
                result.append('ع')
            elif ch == '.':
                pass  # sometimes used as separator
            elif ch == ':':
                pass  # sometimes used in encoding
            elif ch.isdigit():
                result.append(ch)
            elif ch.isalpha():
                result.append(ch)  # pass through unknown letters
            else:
                result.append(ch)
            i += 1

    return ''.join(result)


# ============================================================================
# HTML scraper
# ============================================================================

class UrduTextExtractor(HTMLParser):
    """Extract text from <em class="urdu"> elements in Pritchett's pages."""

    def __init__(self):
        super().__init__()
        self.in_urdu = False
        self.urdu_texts = []
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == 'em' and attrs_dict.get('class') == 'urdu':
            self.in_urdu = True
            self.current_text = []

    def handle_endtag(self, tag):
        if tag == 'em' and self.in_urdu:
            self.in_urdu = False
            text = ''.join(self.current_text).strip()
            if text:
                self.urdu_texts.append(text)

    def handle_data(self, data):
        if self.in_urdu:
            self.current_text.append(data)


def fetch_page(url):
    """Fetch a page with proper User-Agent."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'TesseraeV6/1.0 (academic research; ncoffee@buffalo.edu)'
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None


def extract_ghazal_verses(ghazal_num):
    """Extract all verses of a ghazal from its index page."""
    # Fetch the ghazal index page
    padded = str(ghazal_num).zfill(3)
    url = f"{BASE_URL}/{padded}/index_{padded}.html"
    html = fetch_page(url)
    if not html:
        return []

    # Extract Urdu-encoded text from <em class="urdu"> elements
    parser = UrduTextExtractor()
    parser.feed(html)

    # The index page lists verses as first lines
    # Each verse's first line appears in an <em class="urdu"> tag
    verses = []
    for text in parser.urdu_texts:
        # Skip very short fragments (single words from notes)
        if len(text.split()) >= 3:
            verses.append(text)

    return verses


def main():
    os.makedirs(TEXTS_DIR, exist_ok=True)

    print("Importing Ghalib's Diwan from Pritchett's website...")
    print("Source: franpritchett.com/00ghalib/")
    print()

    all_ghazal_lines = []
    ghazals_found = 0
    ghazals_empty = 0

    # Scan ghazals 1-234 (published) + 235-441 (unpublished, marked with x)
    for ghazal_num in range(1, 442):
        padded = str(ghazal_num).zfill(3)
        url = f"{BASE_URL}/{padded}/index_{padded}.html"
        html = fetch_page(url)

        if not html:
            if ghazal_num <= 234:
                ghazals_empty += 1
            continue

        # Extract verse texts
        parser = UrduTextExtractor()
        parser.feed(html)

        # Filter to actual verse lines (not commentary fragments)
        verse_texts = []
        for text in parser.urdu_texts:
            # Verse lines are typically longer (full couplet hemistichs)
            words = text.split()
            if len(words) >= 3 and not text.startswith('(') and not text.startswith('['):
                verse_texts.append(text)

        if not verse_texts:
            if ghazal_num <= 234:
                ghazals_empty += 1
            continue

        ghazals_found += 1

        # Convert each verse to Urdu script and add to corpus
        for verse_idx, verse_text in enumerate(verse_texts, 1):
            from pritchett_urdu_converter import pritchett_to_urdu as convert
            urdu_text = convert(verse_text)
            if urdu_text and len(urdu_text) > 5:
                ref = f'<ghalib.diwan.{ghazal_num}.{verse_idx}>'
                all_ghazal_lines.append(f'{ref}\t{urdu_text}')

        if ghazals_found % 50 == 0:
            print(f"  Processed {ghazals_found} ghazals ({len(all_ghazal_lines)} lines)...")

        # Be polite to the server
        time.sleep(0.3)

    print(f"\nGhazals found: {ghazals_found}")
    print(f"Ghazals empty/missing: {ghazals_empty}")
    print(f"Total verse lines: {len(all_ghazal_lines)}")

    if all_ghazal_lines:
        # Write the .tess file
        output_path = os.path.join(TEXTS_DIR, 'ghalib.diwan_pritchett.tess')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(all_ghazal_lines) + '\n')
        print(f"\nWritten to {output_path}")

        # Show sample
        print("\nSample lines:")
        for line in all_ghazal_lines[:5]:
            print(f"  {line[:80]}")


if __name__ == '__main__':
    main()
