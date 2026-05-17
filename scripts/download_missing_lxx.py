#!/usr/bin/env python3
"""
Download and convert missing Septuagint books from First1KGreek to .tess format.

Source: github.com/OpenGreekAndLatin/First1KGreek/data/tlg0527/
Format: TEI XML -> .tess

The existing 33 LXX books came from this same source.
"""

import os
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXTS_DIR = os.path.join(PROJECT_ROOT, 'texts', 'grc')
BASE_URL = "https://raw.githubusercontent.com/OpenGreekAndLatin/First1KGreek/master/data/tlg0527"

tei = '{http://www.tei-c.org/ns/1.0}'

# TLG numbers we already have
EXISTING = {
    'tlg015', 'tlg017', 'tlg019', 'tlg020', 'tlg021', 'tlg023',
    'tlg027', 'tlg028', 'tlg029', 'tlg031', 'tlg032', 'tlg033',
    'tlg036', 'tlg037', 'tlg038', 'tlg039', 'tlg040', 'tlg041',
    'tlg042', 'tlg043', 'tlg044', 'tlg045', 'tlg046', 'tlg047',
    'tlg048', 'tlg049', 'tlg050', 'tlg051', 'tlg052', 'tlg053',
    'tlg054', 'tlg056', 'tlg058',
}

# All available TLG numbers
ALL_AVAILABLE = [
    'tlg001', 'tlg002', 'tlg003', 'tlg004', 'tlg005', 'tlg006', 'tlg008',
    'tlg010', 'tlg011', 'tlg012', 'tlg013', 'tlg014', 'tlg015', 'tlg016',
    'tlg017', 'tlg018', 'tlg019', 'tlg020', 'tlg021', 'tlg023', 'tlg024',
    'tlg025', 'tlg026', 'tlg027', 'tlg028', 'tlg029', 'tlg030', 'tlg031',
    'tlg032', 'tlg033', 'tlg034', 'tlg035', 'tlg036', 'tlg037', 'tlg038',
    'tlg039', 'tlg040', 'tlg041', 'tlg042', 'tlg043', 'tlg044', 'tlg045',
    'tlg046', 'tlg047', 'tlg048', 'tlg049', 'tlg050', 'tlg051', 'tlg052',
    'tlg053', 'tlg054', 'tlg055', 'tlg056', 'tlg057', 'tlg058', 'tlg059',
]


def get_all_text(element):
    """Recursively get all text from an element and its children."""
    text = element.text or ''
    for child in element:
        text += get_all_text(child)
        if child.tail:
            text += child.tail
    return text


def convert_tei_to_tess(xml_path, tlg_num):
    """Convert a First1KGreek TEI XML file to .tess format."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Get the title
    title_el = root.find(f'.//{tei}title')
    title = title_el.text if title_el is not None and title_el.text else f'tlg0527.{tlg_num}'

    # Get the URN from the edition div
    edition_div = root.find(f'.//{tei}div[@type="edition"]')
    urn = edition_div.get('n', f'urn:cts:greekLit:tlg0527.{tlg_num}.1st1K-grc1') if edition_div is not None else f'urn:cts:greekLit:tlg0527.{tlg_num}.1st1K-grc1'

    lines = []

    # Find all chapters
    chapters = root.findall(f'.//{tei}div[@subtype="chapter"]')
    if not chapters:
        # Try alternate structure
        chapters = root.findall(f'.//{tei}div[@type="textpart"][@subtype="chapter"]')

    for chapter in chapters:
        ch_num = chapter.get('n', '0')

        # Find verses within chapter
        verses = chapter.findall(f'.//{tei}div[@subtype="verse"]')
        if not verses:
            verses = chapter.findall(f'.//{tei}div[@type="textpart"][@subtype="verse"]')

        if verses:
            for verse in verses:
                v_num = verse.get('n', '0')
                text = get_all_text(verse)
                text = re.sub(r'\s+', ' ', text).strip()
                # Remove verse numbers embedded in text
                text = re.sub(r'^\d+\s*', '', text)
                if text:
                    ref = f'<septuaginta.{tlg_num} {urn}.{ch_num}.{v_num}>'
                    lines.append(f'{ref}\t{text}')
        else:
            # No verse subdivision - treat each p as a line
            for p in chapter.findall(f'.//{tei}p'):
                text = get_all_text(p)
                text = re.sub(r'\s+', ' ', text).strip()
                if text:
                    p_num = p.get('n', '0')
                    ref = f'<septuaginta.{tlg_num} {urn}.{ch_num}.{p_num}>'
                    lines.append(f'{ref}\t{text}')

    if not lines:
        # Fallback: try to get any text content
        body = root.find(f'.//{tei}body')
        if body is not None:
            for p in body.findall(f'.//{tei}p'):
                text = get_all_text(p)
                text = re.sub(r'\s+', ' ', text).strip()
                if text and len(text) > 10:
                    lines.append(f'<septuaginta.{tlg_num}>\t{text}')

    return title, lines


def main():
    missing = [t for t in ALL_AVAILABLE if t not in EXISTING]
    print(f"Missing LXX books: {len(missing)}")

    for tlg_num in missing:
        url = f"{BASE_URL}/{tlg_num}/tlg0527.{tlg_num}.1st1K-grc1.xml"
        xml_path = f"/tmp/lxx_{tlg_num}.xml"

        print(f"\n  {tlg_num}: downloading...")
        req = urllib.request.Request(url, headers={
            'User-Agent': 'TesseraeV6/1.0 (academic research)'
        })
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                with open(xml_path, 'wb') as f:
                    f.write(resp.read())
        except Exception as e:
            print(f"    FAILED to download: {e}")
            continue

        time.sleep(0.5)  # be polite

        try:
            title, lines = convert_tei_to_tess(xml_path, tlg_num)
        except Exception as e:
            print(f"    FAILED to parse: {e}")
            continue

        if not lines:
            print(f"    No text extracted from {tlg_num}")
            continue

        # Generate filename matching existing convention
        # Use title if available, otherwise tlg number
        safe_title = re.sub(r'[^a-zA-Z0-9_]', '_', title.lower()).strip('_')
        if not safe_title or len(safe_title) < 3:
            safe_title = tlg_num

        filename = f'septuaginta.{safe_title}.tess'
        filepath = os.path.join(TEXTS_DIR, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')

        print(f"    {title}: {len(lines)} lines -> {filename}")

        # Clean up
        os.remove(xml_path)

    print("\nDone!")


if __name__ == '__main__':
    main()
