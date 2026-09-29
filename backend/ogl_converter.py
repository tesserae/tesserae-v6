#!/usr/bin/env python3
"""
OGL (Open Greek and Latin) to TESS format converter.

Converts TEI-XML/EpiDoc files from the OpenGreekAndLatin GitHub repositories
into .tess format for use with Tesserae.

Also reads the older TEI shape used by Corpus Corporum (mlat.uzh.ch) and
some MGH/Perseus-derived files: numbered `div1`..`div7` nesting keyed by
`@n` or `@id` (instead of `<div type="edition">` > `<div type="textpart">`),
files with no default namespace or the TEI P4 namespace, leaf text held in
`<p>`, `<l>` (verse lines) or `<ab>`, and `<milestone>` markers used to mark
sections inside a paragraph (or directly inside a div with no paragraph
wrapper at all) rather than one `<p>` per section. This legacy path is
tried only when the modern P5 `type="edition"` shape yields nothing, so it
never changes how an existing file converts.

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


def local_name(tag) -> str:
    """The element's tag name without its namespace, if any."""
    return etree.QName(tag).localname if isinstance(tag, str) else ''


def _first_by_path(root, path_localnames):
    """A namespace-agnostic stand-in for root.find('.//a/b') that matches
    on local element names only, for files with no default namespace or a
    namespace ElementPath doesn't already know about (old Perseus P4
    files declare none at all). Each name in path_localnames is searched
    for among all descendants of the previous match, in document order."""
    current = root
    for name in path_localnames:
        found = None
        for descendant in current.iter():
            if descendant is current:
                continue
            if local_name(descendant.tag) == name:
                found = descendant
                break
        if found is None:
            return None
        current = found
    return current


def extract_metadata(root) -> dict:
    """Extract author, title, and other metadata from TEI header."""
    metadata = {
        'author': 'Unknown',
        'title': 'Unknown',
        'language': 'lat',
        'urn': ''
    }

    title_elem = root.find('.//tei:titleStmt/tei:title', TEI_NS)
    if title_elem is None:
        title_elem = _first_by_path(root, ('titleStmt', 'title'))
    if title_elem is not None and title_elem.text:
        metadata['title'] = normalize_text(title_elem.text)

    author_elem = root.find('.//tei:titleStmt/tei:author', TEI_NS)
    if author_elem is None:
        author_elem = _first_by_path(root, ('titleStmt', 'author'))
    if author_elem is not None:
        author_text = author_elem.text or ''
        if not author_text:
            author_text = ''.join(author_elem.itertext())
        metadata['author'] = normalize_text(author_text)

    lang_elem = root.find('.//tei:profileDesc/tei:langUsage/tei:language', TEI_NS)
    if lang_elem is None:
        lang_elem = _first_by_path(root, ('profileDesc', 'langUsage', 'language'))
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
    if filename_elem is None:
        filename_elem = _first_by_path(root, ('publicationStmt', 'idno'))
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


# ---------------------------------------------------------------------------
# Legacy TEI shape: numbered div1..div7 (Corpus Corporum, MGH-derived files,
# old Perseus P4 files), rather than P5's <div type="edition"> nesting
# <div type="textpart">. See the module docstring.
# ---------------------------------------------------------------------------

DIV_LOCAL_NAMES = {f'div{i}' for i in range(1, 8)}
_MILESTONE_SKIP_TAGS = {'note', 'app', 'rdg', 'lem', 'gap', 'supplied',
                         'unclear', 'head'}
_ROMAN_NUMERAL_RE = re.compile(r'^[IVXLCDM]+$')

# Old title headers spell out a book number as a word ("LIBER QUINTUS") or,
# for two-book works, "LIBER PRIOR"/"LIBER POSTERIOR". Keys are normalized
# with V read as U below, so a single entry covers both classical spellings.
_LATIN_BOOK_ORDINALS = {
    'PRIMUS': 1, 'SECUNDUS': 2, 'TERTIUS': 3, 'QUARTUS': 4, 'QUINTUS': 5,
    'SEXTUS': 6, 'SEPTIMUS': 7, 'OCTAVUS': 8, 'NONUS': 9, 'DECIMUS': 10,
    'UNDECIMUS': 11, 'DUODECIMUS': 12, 'TERTIUSDECIMUS': 13,
    'QUARTUSDECIMUS': 14, 'QUINTUSDECIMUS': 15, 'SEXTUSDECIMUS': 16,
    'SEPTIMUSDECIMUS': 17, 'DUODEVICESIMUS': 18, 'UNDEVICESIMUS': 19,
    'VICESIMUS': 20, 'PRIOR': 1, 'POSTERIOR': 2,
}
_NORMALIZED_LATIN_ORDINALS = {
    key.replace('V', 'U'): val for key, val in _LATIN_BOOK_ORDINALS.items()
}


def roman_to_int(s):
    """Convert a Roman numeral string to an int, or None if it is not a
    well-formed Roman numeral (also rejects the empty string)."""
    if not s or not _ROMAN_NUMERAL_RE.match(s):
        return None
    values = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total = 0
    prev = 0
    for ch in reversed(s):
        v = values[ch]
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total


def latin_ordinal_word_to_int(word):
    """'QUINTUS' -> 5, 'PRIOR' -> 1, etc. None if the word isn't one of
    the ordinals old title headers use for book numbers."""
    if not word:
        return None
    return _NORMALIZED_LATIN_ORDINALS.get(word.upper().replace('V', 'U').replace('J', 'I'))


def child_by_localname(elem, name):
    for c in elem:
        if local_name(c.tag) == name:
            return c
    return None


def children_by_localnames(elem, names):
    return [c for c in elem if local_name(c.tag) in names]


def find_body(root):
    for d in root.iter():
        if local_name(d.tag) == 'body':
            return d
    return None


def head_derived_number(div):
    """A citation number parsed from a div's own <head>, for old title
    pages that give no @n/@id at all: either a leading Roman numeral
    ('VI. Some Chapter Title' -> 'VI') or an old-style running title
    ending 'LIBER QUINTUS' -> 'QUINTUS'. Returns the matched token
    (still a Roman numeral or Latin word, not yet normalized to Arabic),
    or None."""
    head = child_by_localname(div, 'head')
    if head is None:
        return None
    text = normalize_text(''.join(head.itertext()))
    if not text:
        return None
    m = re.match(r'^([IVXLCDM]+)\.', text)
    if m and roman_to_int(m.group(1)) is not None:
        return m.group(1)
    last_match = None
    for last_match in re.finditer(r'\bLIBER\s+([A-Z]+)\b', text.upper()):
        pass
    if last_match is not None:
        word = last_match.group(1).rstrip('.')
        if latin_ordinal_word_to_int(word) is not None:
            return word
    return None


def _looks_like_a_citation_token(val):
    """@n/@id values that are really a prose label (a work's own
    abbreviation, e.g. 'Sidon. epp.') rather than a citation number have
    a space or a period in them; a real citation token never does (a
    Roman numeral, an Arabic number, or a short literal like 'pr')."""
    return ' ' not in val and '.' not in val


def legacy_div_number(div, allow_raw_fallback=True):
    """The raw citation token for a legacy divN element: its own @n or
    @id if set and it looks like a citation token, else a number parsed
    from its <head>, else (if allow_raw_fallback) @n/@id anyway if
    that's all there is. None if nothing usable was found. The <head>
    fallback matters for a div whose @n is the whole work's own label
    rather than a number -- Sidonius' Corpus Corporum files give book 1
    no separate part-level div of its own, so its letters attach
    directly to the work-level div, whose @n is "Sidon. epp." but whose
    <head> also spells out "LIBER PRIMUS". allow_raw_fallback is turned
    off for a work/edition wrapper div: unlike a real citable level (say
    a praefatio marked '@n="pr"'), a whole work's own label is never
    itself a meaningful citation component, so it is better omitted than
    included literally when no number can be found for it."""
    for attr in ('n', 'id'):
        val = div.get(attr)
        if val and _looks_like_a_citation_token(val):
            return val
    head_number = head_derived_number(div)
    if head_number is not None:
        return head_number
    if allow_raw_fallback:
        for attr in ('n', 'id'):
            val = div.get(attr)
            if val:
                return val
    return None


def normalize_citation_token(token):
    """Roman numerals and Latin ordinal words become Arabic numbers, to
    match the book.chapter.section-in-Arabic-numerals convention already
    used across the corpus. A literal, non-numeric label (a praefatio
    marked '@n="pr"', say) passes through unchanged."""
    if token is None:
        return None
    if token.isdigit():
        return token
    r = roman_to_int(token)
    if r is not None:
        return str(r)
    w = latin_ordinal_word_to_int(token)
    if w is not None:
        return str(w)
    return token


def split_by_milestones(elem):
    """Split an element's mixed content at each direct-child <milestone>,
    in document order. Returns a list of (n, text) pairs, where n is the
    milestone's own @n (the edition's section number) and text is
    everything from that milestone up to the next one (notes, apparatus
    and <head> dropped; <lb>/<pb> collapsed, same as get_text_from_element).
    Text preceding the first milestone, if any, is folded into the first
    milestone's text rather than dropped. If elem has no <milestone>
    children at all, returns [(None, text)] with the element's whole text
    (or [] if that text is empty) -- callers treat n=None as "no
    milestones here, do whatever you'd otherwise do."""
    groups = [[None, []]]

    def emit(s):
        if s:
            groups[-1][1].append(s)

    emit(elem.text)
    for child in elem:
        tag = local_name(child.tag)
        if tag == 'milestone':
            groups.append([child.get('n'), []])
        elif tag in _MILESTONE_SKIP_TAGS:
            pass
        elif tag == 'lb':
            emit(' ')
        elif tag == 'pb':
            pass
        else:
            emit(get_text_from_element(child))
        emit(child.tail)

    if len(groups) == 1:
        text = normalize_text(''.join(groups[0][1]))
        return [(None, text)] if text else []

    if any(s.strip() for s in groups[0][1]):
        groups[1][1] = groups[0][1] + groups[1][1]
    groups = groups[1:]

    result = []
    for n, parts in groups:
        text = normalize_text(''.join(parts))
        if text:
            result.append((n, text))
    return result


def extract_legacy_leaf_sections(div):
    """The (suffix, text) pairs for one legacy leaf div, where suffix is
    appended to the div's own citation path (None means the leaf is a
    single section, cited by its ancestors' numbers alone)."""
    paragraphs = children_by_localnames(div, {'p', 'ab'})
    lines = children_by_localnames(div, {'l'})
    line_groups = children_by_localnames(div, {'lg'})

    if paragraphs:
        results = []
        counter = 0
        for p in paragraphs:
            groups = split_by_milestones(p)
            if not groups:
                continue
            if len(groups) == 1 and groups[0][0] is None:
                counter += 1
                results.append((str(counter) if len(paragraphs) > 1 else None,
                                 groups[0][1]))
            else:
                for n, text in groups:
                    counter += 1
                    results.append((n if n is not None else str(counter), text))
        return results

    if lines and not line_groups:
        div_kind = (div.get('subtype') or div.get('type') or '').lower()
        if div_kind == 'verse':
            # An already-atomic unit (e.g. one Biblical verse laid out
            # across several typeset <l> lines): keep it as one section,
            # matching the existing prose/Lamentations behaviour.
            text = normalize_text(' '.join(
                t for t in (normalize_text(get_text_from_element(l)) for l in lines) if t
            ))
            return [(None, text)] if text else []
        # A leaf with no finer subdivision than bare <l> lines: an entire
        # poem or book of verse with no per-verse numbering in the source.
        # One citation per line, matching the corpus's verse convention
        # (e.g. "verg. aen. 1.1").
        results = []
        for i, l in enumerate(lines, 1):
            text = normalize_text(get_text_from_element(l))
            if text:
                results.append((str(i), text))
        return results

    # No <p>/<ab> and no bare <l>: text sits directly in the div, in some
    # editions split into sections by <milestone> markers with no
    # paragraph wrapper at all (Corpus Corporum's house style for Varro
    # and Isidore, among others).
    groups = split_by_milestones(div)
    if len(groups) == 1 and groups[0][0] is None:
        return [(None, groups[0][1])]
    return [(n if n is not None else str(i), text)
            for i, (n, text) in enumerate(groups, 1)]


def extract_legacy_sections(root) -> list:
    """extract_sections()'s fallback for the old div1..div7 TEI shape."""
    body = find_body(root)
    if body is None:
        return []

    all_divs = [d for d in body.iter() if local_name(d.tag) in DIV_LOCAL_NAMES]
    if not all_divs:
        return []

    def own_div_children(div):
        return [c for c in div if local_name(c.tag) in DIV_LOCAL_NAMES]

    leaf_divs = [d for d in all_divs if not own_div_children(d)]

    def ancestor_chain(div):
        chain = []
        current = div
        while current is not None and current is not body:
            chain.append(current)
            current = current.getparent()
        chain.reverse()
        return chain

    def base_citation_parts(div):
        chain = ancestor_chain(div)
        # A whole-work wrapper (Sidonius's Corpus Corporum files nest each
        # book inside one of these) is only redundant once a nested "part"
        # (book) division also exists for this leaf. Sidonius' own book 1
        # gets no such div of its own -- its letters attach directly to
        # the work-level div, so THAT div's own number is the only source
        # of the book number and must not be skipped.
        has_part_level = any((a.get('type') or '').lower() == 'part' for a in chain)
        parts = []
        for anc in chain:
            div_kind = (anc.get('type') or '').lower()
            is_wrapper = div_kind in ('work', 'edition')
            if is_wrapper and has_part_level:
                continue
            token = legacy_div_number(anc, allow_raw_fallback=not is_wrapper)
            if token is None:
                if not is_wrapper:
                    print(f"WARNING: legacy TEI div <{local_name(anc.tag)}> has "
                          f"no @n, @id, or parseable <head> number; omitting "
                          f"this level from the citation", file=sys.stderr)
                continue
            parts.append(normalize_citation_token(token))
        return parts

    sections = []
    seen = {}
    for leaf in leaf_divs:
        base_parts = base_citation_parts(leaf)
        if not base_parts:
            continue
        for suffix, text in extract_legacy_leaf_sections(leaf):
            parts = list(base_parts)
            if suffix is not None:
                parts.append(normalize_citation_token(suffix))
            citation = '.'.join(parts)
            if citation in seen:
                seen[citation] += 1
                disambiguated = f"{citation}b{seen[citation]}"
                print(f"WARNING: duplicate citation '{citation}' (the "
                      f"source has a repeated @id/@n); keeping this text "
                      f"under '{disambiguated}' rather than dropping it",
                      file=sys.stderr)
                citation = disambiguated
            else:
                seen[citation] = 1
            sections.append({'citation': citation, 'text': text})
    return sections


def extract_sections(root) -> list:
    """Extract text sections with their citations.

    Tries the modern P5 shape first (unchanged from before); if that
    finds nothing, falls back to the legacy div1..div7 shape (see the
    module docstring). A file already handled by the P5 path is
    unaffected by the fallback existing at all.
    """
    sections = _extract_sections_p5(root)
    if sections:
        return sections
    return extract_legacy_sections(root)


def _extract_sections_p5(root) -> list:
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
                # The edition division carries the work's URN as its n; a
                # citation is the chain of textpart numbers beneath it.
                if n and ':' not in n:
                    path_parts.insert(0, n)
            current = current.getparent()
        return '.'.join(path_parts) if path_parts else '1'
    
    for div in leaf_divs:
        base_citation = get_citation_path(div)
        
        paragraphs = div.findall('./tei:p', TEI_NS)
        lines = div.findall('./tei:l', TEI_NS) + div.findall('./tei:lg', TEI_NS)
        if paragraphs and not lines:
            for i, p in enumerate(paragraphs, 1):
                text = get_text_from_element(p)
                text = normalize_text(text)
                if text:
                    citation = f"{base_citation}.{i}" if len(paragraphs) > 1 else base_citation
                    if citation not in seen_citations:
                        sections.append({'citation': citation, 'text': text})
                        seen_citations.add(citation)
        elif paragraphs and lines:
            # A leaf that mixes paragraphs and lines is one section with all
            # of them in document order. Swete's Lamentations gives each verse
            # a paragraph holding the acrostic letter and then the verse as
            # lines; taking the paragraphs alone left 88 of 150 verses as a
            # bare letter name (issue #276).
            parts = []
            for child in div:
                tag = etree.QName(child.tag).localname if isinstance(child.tag, str) else ''
                if tag in ('p', 'l', 'lg'):
                    part = normalize_text(get_text_from_element(child))
                    if part:
                        parts.append(part)
            text = ' '.join(parts)
            if text and base_citation not in seen_citations:
                sections.append({'citation': base_citation, 'text': text})
                seen_citations.add(base_citation)
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
