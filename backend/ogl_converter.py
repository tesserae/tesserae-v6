#!/usr/bin/env python3
"""
OGL (Open Greek and Latin) to TESS format converter.

Converts TEI-XML/EpiDoc files from the OpenGreekAndLatin GitHub repositories
into .tess format for use with Tesserae.

Usage:
    python ogl_converter.py <input_xml> <output_tess>
    python ogl_converter.py --batch <input_dir> <output_dir>
"""

import os
import re
import sys
import argparse
from pathlib import Path
from lxml import etree
import unicodedata

TEI_NS = {'tei': 'http://www.tei-c.org/ns/1.0'}


def normalize_text(text: str) -> str:
    """Normalize whitespace and clean up text."""
    if not text:
        return ""
    text = unicodedata.normalize('NFC', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text


def extract_metadata(root) -> dict:
    """Extract author, title, and other metadata from TEI header."""
    metadata = {
        'author': 'Unknown',
        'title': 'Unknown',
        'language': 'lat',
        'urn': ''
    }
    
    title_elem = root.find('.//tei:titleStmt/tei:title', TEI_NS)
    if title_elem is not None and title_elem.text:
        metadata['title'] = normalize_text(title_elem.text)
    
    author_elem = root.find('.//tei:titleStmt/tei:author', TEI_NS)
    if author_elem is not None:
        author_text = author_elem.text or ''
        if not author_text:
            author_text = ''.join(author_elem.itertext())
        metadata['author'] = normalize_text(author_text)
    
    lang_elem = root.find('.//tei:profileDesc/tei:langUsage/tei:language', TEI_NS)
    if lang_elem is not None:
        lang_id = lang_elem.get('ident', 'lat')
        if lang_id in ['grc', 'greek']:
            metadata['language'] = 'grc'
        elif lang_id in ['eng', 'en', 'english']:
            metadata['language'] = 'en'
        else:
            metadata['language'] = 'la'
    
    edition_div = root.find('.//tei:body/tei:div[@type="edition"]', TEI_NS)
    if edition_div is not None:
        urn = edition_div.get('n', '')
        if urn:
            metadata['urn'] = urn
    
    filename_elem = root.find('.//tei:publicationStmt/tei:idno[@type="filename"]', TEI_NS)
    if filename_elem is not None and filename_elem.text:
        metadata['filename'] = filename_elem.text.replace('.xml', '')
    
    return metadata


def get_text_from_element(elem) -> str:
    """Extract text content from an element, excluding notes and apparatus."""
    if elem is None:
        return ""
    
    text_parts = []
    
    if elem.text:
        text_parts.append(elem.text)
    
    for child in elem:
        tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ''
        
        if tag in ['note', 'app', 'rdg', 'lem', 'gap', 'supplied', 'unclear']:
            pass
        elif tag == 'lb':
            text_parts.append(' ')
        elif tag == 'pb':
            pass
        elif tag == 'milestone':
            pass
        else:
            text_parts.append(get_text_from_element(child))
        
        if child.tail:
            text_parts.append(child.tail)
    
    return ''.join(text_parts)


def extract_sections(root) -> list:
    """Extract text sections with their citations.
    
    Uses a deterministic approach to prevent duplicates:
    1. Find leaf-level textparts (those without nested textparts)
    2. For each leaf, extract paragraphs or direct text
    3. Build citation from ancestor hierarchy
    """
    sections = []
    seen_citations = set()
    
    edition_div = root.find('.//tei:body/tei:div[@type="edition"]', TEI_NS)
    if edition_div is None:
        edition_div = root.find('.//tei:body/tei:div', TEI_NS)
    
    if edition_div is None:
        return sections
    
    all_divs = edition_div.findall('.//tei:div[@type="textpart"]', TEI_NS)
    if not all_divs:
        all_divs = edition_div.findall('.//tei:div[@n]', TEI_NS)
    
    leaf_divs = []
    for div in all_divs:
        nested = div.findall('./tei:div[@type="textpart"]', TEI_NS)
        if not nested:
            nested = div.findall('./tei:div[@n]', TEI_NS)
        if not nested:
            leaf_divs.append(div)
    
    def get_citation_path(elem):
        """Build citation from ancestor @n attributes."""
        path_parts = []
        current = elem
        while current is not None:
            if hasattr(current, 'get'):
                n = current.get('n')
                if n:
                    path_parts.insert(0, n)
            current = current.getparent()
        return '.'.join(path_parts) if path_parts else '1'
    
    for div in leaf_divs:
        base_citation = get_citation_path(div)
        
        paragraphs = div.findall('./tei:p', TEI_NS)
        if paragraphs:
            for i, p in enumerate(paragraphs, 1):
                text = get_text_from_element(p)
                text = normalize_text(text)
                if text:
                    citation = f"{base_citation}.{i}" if len(paragraphs) > 1 else base_citation
                    if citation not in seen_citations:
                        sections.append({'citation': citation, 'text': text})
                        seen_citations.add(citation)
        else:
            text = get_text_from_element(div)
            text = normalize_text(text)
            if text and base_citation not in seen_citations:
                sections.append({'citation': base_citation, 'text': text})
                seen_citations.add(base_citation)
    
    if not sections:
        paragraphs = edition_div.findall('.//tei:p', TEI_NS)
        for i, p in enumerate(paragraphs, 1):
            text = get_text_from_element(p)
            text = normalize_text(text)
            if text:
                citation = str(i)
                if citation not in seen_citations:
                    sections.append({'citation': citation, 'text': text})
                    seen_citations.add(citation)
    
    return sections


def generate_tess_id(metadata: dict) -> str:
    """Generate a .tess filename from metadata."""
    author = metadata['author'].lower()
    author = re.sub(r'[^a-z0-9]+', '_', author)
    author = author.strip('_')
    
    title = metadata['title'].lower()
    title = re.sub(r'[^a-z0-9]+', '_', title)
    title = title.strip('_')
    
    if len(title) > 40:
        title = title[:40].rstrip('_')
    
    return f"{author}.{title}"


def convert_xml_to_tess(xml_path: str, output_path: str = None) -> dict:
    """
    Convert a single OGL TEI-XML file to .tess format.
    
    Returns metadata about the conversion.
    """
    with open(xml_path, 'rb') as f:
        content = f.read()
    
    root = etree.fromstring(content)
    
    metadata = extract_metadata(root)
    sections = extract_sections(root)
    
    if not sections:
        return {'success': False, 'error': 'No text content found', 'metadata': metadata}
    
    tess_id = generate_tess_id(metadata)
    
    if output_path is None:
        output_path = f"{tess_id}.tess"
    
    lines = []
    for section in sections:
        citation = f"<{tess_id} {section['citation']}>"
        lines.append(f"{citation}\t{section['text']}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    return {
        'success': True,
        'metadata': metadata,
        'tess_id': tess_id,
        'output_path': output_path,
        'section_count': len(sections),
        'word_count': sum(len(s['text'].split()) for s in sections)
    }


def batch_convert(input_dir: str, output_dir: str, language: str = None) -> list:
    """
    Batch convert all XML files in a directory.
    
    Args:
        input_dir: Directory containing XML files
        output_dir: Directory for output .tess files
        language: Optional filter for language ('la', 'grc', 'en')
    
    Returns:
        List of conversion results
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = []
    xml_files = list(input_path.rglob('*.xml'))
    
    print(f"Found {len(xml_files)} XML files to process")
    
    for i, xml_file in enumerate(xml_files):
        try:
            print(f"[{i+1}/{len(xml_files)}] Processing {xml_file.name}...")
            
            with open(xml_file, 'rb') as f:
                content = f.read()
            root = etree.fromstring(content)
            metadata = extract_metadata(root)
            
            if language and metadata['language'] != language:
                print(f"  Skipping (language: {metadata['language']})")
                continue
            
            tess_id = generate_tess_id(metadata)
            output_file = output_path / f"{tess_id}.tess"
            
            if output_file.exists():
                print(f"  Skipping (already exists)")
                continue
            
            result = convert_xml_to_tess(str(xml_file), str(output_file))
            results.append(result)
            
            if result['success']:
                print(f"  Created {result['tess_id']}.tess ({result['section_count']} sections, {result['word_count']} words)")
            else:
                print(f"  Failed: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            print(f"  Error: {e}")
            results.append({
                'success': False,
                'error': str(e),
                'file': str(xml_file)
            })
    
    successful = sum(1 for r in results if r.get('success'))
    print(f"\nCompleted: {successful}/{len(results)} files converted successfully")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Convert OGL TEI-XML to TESS format')
    parser.add_argument('input', help='Input XML file or directory')
    parser.add_argument('output', help='Output .tess file or directory')
    parser.add_argument('--batch', action='store_true', help='Batch convert directory')
    parser.add_argument('--language', choices=['la', 'grc', 'en'], help='Filter by language')
    
    args = parser.parse_args()
    
    if args.batch:
        batch_convert(args.input, args.output, args.language)
    else:
        result = convert_xml_to_tess(args.input, args.output)
        if result['success']:
            print(f"Converted successfully: {result['output_path']}")
            print(f"  Author: {result['metadata']['author']}")
            print(f"  Title: {result['metadata']['title']}")
            print(f"  Sections: {result['section_count']}")
            print(f"  Words: {result['word_count']}")
        else:
            print(f"Conversion failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)


if __name__ == '__main__':
    main()
