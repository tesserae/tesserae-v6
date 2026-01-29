"""
Tesserae V6 - PHI-Style Wildcard/Boolean Search

Provides Packard Humanities Institute-style search with:
- Wildcards: * (any characters), ? (single character)
- Boolean operators: AND, OR, NOT
- Proximity: ~ (words within ~100 characters)
- Word break: # (word boundary marker)
- Case-insensitive matching (default)
- Results with highlighted matches
"""

import os
import re
import unicodedata
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from backend.logging_config import get_logger
from backend.utils import get_text_metadata, detect_text_type

logger = get_logger('wildcard_search')

def get_author_dates():
    """Get author dates from app.py"""
    try:
        from backend.app import AUTHOR_DATES
        return AUTHOR_DATES
    except ImportError:
        return {}

GREEK_DIACRITICAL_MAP = {
    'ά': 'α', 'ὰ': 'α', 'ᾶ': 'α', 'ἀ': 'α', 'ἁ': 'α', 'ἂ': 'α', 'ἃ': 'α', 'ἄ': 'α', 'ἅ': 'α', 'ἆ': 'α', 'ἇ': 'α',
    'ᾀ': 'α', 'ᾁ': 'α', 'ᾂ': 'α', 'ᾃ': 'α', 'ᾄ': 'α', 'ᾅ': 'α', 'ᾆ': 'α', 'ᾇ': 'α', 'ᾲ': 'α', 'ᾳ': 'α', 'ᾴ': 'α', 'ᾷ': 'α',
    'έ': 'ε', 'ὲ': 'ε', 'ἐ': 'ε', 'ἑ': 'ε', 'ἒ': 'ε', 'ἓ': 'ε', 'ἔ': 'ε', 'ἕ': 'ε',
    'ή': 'η', 'ὴ': 'η', 'ῆ': 'η', 'ἠ': 'η', 'ἡ': 'η', 'ἢ': 'η', 'ἣ': 'η', 'ἤ': 'η', 'ἥ': 'η', 'ἦ': 'η', 'ἧ': 'η',
    'ᾐ': 'η', 'ᾑ': 'η', 'ᾒ': 'η', 'ᾓ': 'η', 'ᾔ': 'η', 'ᾕ': 'η', 'ᾖ': 'η', 'ᾗ': 'η', 'ῂ': 'η', 'ῃ': 'η', 'ῄ': 'η', 'ῇ': 'η',
    'ί': 'ι', 'ὶ': 'ι', 'ῖ': 'ι', 'ἰ': 'ι', 'ἱ': 'ι', 'ἲ': 'ι', 'ἳ': 'ι', 'ἴ': 'ι', 'ἵ': 'ι', 'ἶ': 'ι', 'ἷ': 'ι', 'ϊ': 'ι', 'ΐ': 'ι', 'ῒ': 'ι', 'ῗ': 'ι',
    'ό': 'ο', 'ὸ': 'ο', 'ὀ': 'ο', 'ὁ': 'ο', 'ὂ': 'ο', 'ὃ': 'ο', 'ὄ': 'ο', 'ὅ': 'ο',
    'ύ': 'υ', 'ὺ': 'υ', 'ῦ': 'υ', 'ὐ': 'υ', 'ὑ': 'υ', 'ὒ': 'υ', 'ὓ': 'υ', 'ὔ': 'υ', 'ὕ': 'υ', 'ὖ': 'υ', 'ὗ': 'υ', 'ϋ': 'υ', 'ΰ': 'υ', 'ῢ': 'υ', 'ῧ': 'υ',
    'ώ': 'ω', 'ὼ': 'ω', 'ῶ': 'ω', 'ὠ': 'ω', 'ὡ': 'ω', 'ὢ': 'ω', 'ὣ': 'ω', 'ὤ': 'ω', 'ὥ': 'ω', 'ὦ': 'ω', 'ὧ': 'ω',
    'ᾠ': 'ω', 'ᾡ': 'ω', 'ᾢ': 'ω', 'ᾣ': 'ω', 'ᾤ': 'ω', 'ᾥ': 'ω', 'ᾦ': 'ω', 'ᾧ': 'ω', 'ῲ': 'ω', 'ῳ': 'ω', 'ῴ': 'ω', 'ῷ': 'ω',
    'ῤ': 'ρ', 'ῥ': 'ρ',
}


def normalize_greek(text: str) -> str:
    """
    Normalize Greek text by removing diacriticals (accents, breathings, iota subscripts).
    This allows searches like 'λογος' to match 'λόγος'.
    """
    result = []
    for char in text:
        if char in GREEK_DIACRITICAL_MAP:
            result.append(GREEK_DIACRITICAL_MAP[char])
        else:
            result.append(char)
    return ''.join(result)

TEXTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')


def parse_query(query: str) -> Dict:
    """
    Parse a PHI-style query into structured components.
    
    Supports:
    - Simple terms: amor
    - Wildcards: am* (starts with), *or (ends with), ?or (single char wildcard)
    - Boolean AND: amor AND dolor
    - Boolean OR: virtus OR honos
    - Boolean NOT: amor NOT bellum
    - Phrase (quoted): "arma virumque"
    - Proximity: amor ~ dolor (words within ~100 characters)
    - Word break: amor# (explicit word boundary)
    """
    query = query.strip()
    
    if not query:
        return {'type': 'empty', 'terms': []}
    
    # Check for proximity operator ~ (words within ~100 chars)
    if ' ~ ' in query:
        parts = query.split(' ~ ', 1)
        if len(parts) == 2:
            return {
                'type': 'proximity',
                'term1': parse_term(parts[0].strip()),
                'term2': parse_term(parts[1].strip()),
                'distance': 100  # ~100 characters as per PHI
            }
    
    if ' AND ' in query.upper():
        parts = re.split(r'\s+AND\s+', query, flags=re.IGNORECASE)
        return {
            'type': 'and',
            'terms': [parse_term(p.strip()) for p in parts if p.strip()]
        }
    
    if ' OR ' in query.upper():
        parts = re.split(r'\s+OR\s+', query, flags=re.IGNORECASE)
        return {
            'type': 'or', 
            'terms': [parse_term(p.strip()) for p in parts if p.strip()]
        }
    
    if ' NOT ' in query.upper():
        parts = re.split(r'\s+NOT\s+', query, flags=re.IGNORECASE, maxsplit=1)
        if len(parts) == 2:
            return {
                'type': 'not',
                'include': parse_term(parts[0].strip()),
                'exclude': parse_term(parts[1].strip())
            }
    
    return {'type': 'simple', 'terms': [parse_term(query)]}


def parse_term(term: str) -> Dict:
    """Parse a single search term into a pattern."""
    term = term.strip()
    
    if term.startswith('"') and term.endswith('"'):
        phrase = term[1:-1]
        return {'type': 'phrase', 'value': phrase, 'pattern': phrase_to_regex(phrase)}
    
    # Handle word break character # (explicit word boundary)
    has_word_break = '#' in term
    if has_word_break:
        term = term.replace('#', '')
    
    if '*' in term or '?' in term:
        return {'type': 'wildcard', 'value': term, 'pattern': wildcard_to_regex(term), 'word_break': has_word_break}
    
    return {'type': 'exact', 'value': term, 'pattern': re.escape(term), 'word_break': has_word_break}


def wildcard_to_regex(pattern: str) -> str:
    """Convert PHI-style wildcards to regex."""
    regex = ''
    for char in pattern:
        if char == '*':
            regex += r'\w*'
        elif char == '?':
            regex += r'\w'
        else:
            regex += re.escape(char)
    return regex


def phrase_to_regex(phrase: str) -> str:
    """Convert phrase to regex that matches the words in sequence."""
    words = phrase.split()
    pattern = r'\b' + r'\s+'.join(re.escape(w) for w in words) + r'\b'
    return pattern


def search_file(filepath: str, parsed_query: Dict, case_sensitive: bool = False, language: str = 'la') -> List[Dict]:
    """Search a single .tess file for matches."""
    results = []
    is_greek = language == 'grc'
    filename = os.path.basename(filepath)
    is_prose = detect_text_type(filename) == 'prose'
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        return results
    
    flags = 0 if case_sensitive else re.IGNORECASE
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        match = re.match(r'^<([^>]+)>\s*(.+)$', line)
        if not match:
            continue
        
        ref = match.group(1)
        text = match.group(2)
        
        search_text = normalize_greek(text) if is_greek else text
        
        if matches_query(search_text, parsed_query, flags, is_greek):
            highlight_indices = get_highlight_indices(text, parsed_query, flags, is_greek)
            
            # For prose, extract only sentences containing matches
            display_text = text
            if is_prose and len(text) > 150:
                display_text = extract_sentences_with_matches(text, highlight_indices)
                # Recalculate indices for the extracted text
                highlight_indices = get_highlight_indices(display_text, parsed_query, flags, is_greek)
            
            # Apply HTML highlighting
            highlighted_text = apply_highlighting(display_text, highlight_indices)
            
            results.append({
                'ref': ref,
                'text': display_text,
                'highlighted_text': highlighted_text,
                'is_prose': is_prose
            })
    
    return results


def matches_query(text: str, parsed_query: Dict, flags: int, is_greek: bool = False) -> bool:
    """Check if text matches the parsed query."""
    query_type = parsed_query.get('type', 'simple')
    
    if query_type == 'empty':
        return False
    
    if query_type == 'simple':
        return all(matches_term(text, term, flags, is_greek) for term in parsed_query['terms'])
    
    if query_type == 'and':
        return all(matches_term(text, term, flags, is_greek) for term in parsed_query['terms'])
    
    if query_type == 'or':
        return any(matches_term(text, term, flags, is_greek) for term in parsed_query['terms'])
    
    if query_type == 'not':
        include_match = matches_term(text, parsed_query['include'], flags, is_greek)
        exclude_match = matches_term(text, parsed_query['exclude'], flags, is_greek)
        return include_match and not exclude_match
    
    if query_type == 'proximity':
        return matches_proximity(text, parsed_query, flags, is_greek)
    
    return False


def matches_proximity(text: str, parsed_query: Dict, flags: int, is_greek: bool = False) -> bool:
    """Check if two terms appear within the specified character distance."""
    term1 = parsed_query['term1']
    term2 = parsed_query['term2']
    distance = parsed_query.get('distance', 100)
    
    pattern1 = term1['pattern']
    pattern2 = term2['pattern']
    
    if is_greek:
        pattern1 = normalize_greek(pattern1)
        pattern2 = normalize_greek(pattern2)
    
    pattern1 = r'\b' + pattern1 + r'\b'
    pattern2 = r'\b' + pattern2 + r'\b'
    
    search_text = normalize_greek(text) if is_greek else text
    
    matches1 = list(re.finditer(pattern1, search_text, flags))
    matches2 = list(re.finditer(pattern2, search_text, flags))
    
    if not matches1 or not matches2:
        return False
    
    # Check if any pair of matches is within distance
    for m1 in matches1:
        for m2 in matches2:
            # Calculate distance between end of first and start of second (or vice versa)
            if m1.end() <= m2.start():
                dist = m2.start() - m1.end()
            else:
                dist = m1.start() - m2.end()
            if dist <= distance:
                return True
    
    return False


def matches_term(text: str, term: Dict, flags: int, is_greek: bool = False) -> bool:
    """Check if text matches a single term."""
    pattern = term['pattern']
    if is_greek:
        pattern = normalize_greek(pattern)
    pattern = r'\b' + pattern + r'\b'
    return bool(re.search(pattern, text, flags))


def get_highlight_indices(text: str, parsed_query: Dict, flags: int, is_greek: bool = False) -> List[List[int]]:
    """Get character indices to highlight in the text."""
    indices = []
    terms = []
    
    query_type = parsed_query.get('type', 'simple')
    
    if query_type in ('simple', 'and', 'or'):
        terms = parsed_query.get('terms', [])
    elif query_type == 'not':
        terms = [parsed_query['include']]
    elif query_type == 'proximity':
        terms = [parsed_query['term1'], parsed_query['term2']]
    
    search_text = normalize_greek(text) if is_greek else text
    
    for term in terms:
        pattern = term['pattern']
        if is_greek:
            pattern = normalize_greek(pattern)
        pattern = r'\b' + pattern + r'\b'
        for match in re.finditer(pattern, search_text, flags):
            indices.append([match.start(), match.end()])
    
    indices.sort(key=lambda x: x[0])
    return indices


def apply_highlighting(text: str, indices: List[List[int]]) -> str:
    """Apply HTML highlighting to text at the specified indices."""
    if not indices:
        return text
    
    # Merge overlapping indices
    merged = []
    for start, end in sorted(indices):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    
    # Build highlighted text from right to left to preserve indices
    result = text
    for start, end in reversed(merged):
        result = result[:start] + '<mark class="bg-yellow-200">' + result[start:end] + '</mark>' + result[end:]
    
    return result


def extract_sentences_with_matches(text: str, indices: List[List[int]], context_chars: int = 80) -> str:
    """Extract only the sentence(s) or snippets containing the search matches for prose.
    
    For prose texts, returns just the relevant portions containing matches,
    rather than the entire passage.
    """
    if not indices:
        return text
    
    # For very long texts, use snippet-based extraction
    if len(text) > 300:
        # Extract snippets around each match
        snippets = []
        used_ranges = []
        
        for start, end in indices:
            # Check if this match is already covered
            already_covered = False
            for used_start, used_end in used_ranges:
                if start >= used_start and end <= used_end:
                    already_covered = True
                    break
            
            if already_covered:
                continue
            
            # Get snippet around the match
            snippet_start = max(0, start - context_chars)
            snippet_end = min(len(text), end + context_chars)
            
            # Expand to word boundaries
            while snippet_start > 0 and text[snippet_start] not in ' \t\n':
                snippet_start -= 1
            while snippet_end < len(text) and text[snippet_end] not in ' \t\n':
                snippet_end += 1
            
            used_ranges.append((snippet_start, snippet_end))
        
        # Merge overlapping ranges
        used_ranges.sort()
        merged_ranges = []
        for start, end in used_ranges:
            if merged_ranges and start <= merged_ranges[-1][1] + 20:
                merged_ranges[-1] = (merged_ranges[-1][0], max(merged_ranges[-1][1], end))
            else:
                merged_ranges.append((start, end))
        
        # Build result
        result_parts = []
        for i, (start, end) in enumerate(merged_ranges):
            snippet = text[start:end].strip()
            # Add ellipsis at start if not at beginning
            if start > 0:
                snippet = '...' + snippet
            # Add ellipsis at end if not at end
            if end < len(text):
                snippet = snippet + '...'
            result_parts.append(snippet)
        
        return ' '.join(result_parts)
    
    # For shorter texts, try sentence-based extraction
    sentence_pattern = r'[^.!?]*[.!?](?:\s|$)'
    sentences = list(re.finditer(sentence_pattern, text))
    
    if not sentences:
        return text
    
    # Find which sentences contain matches
    matching_sentences = set()
    for start, end in indices:
        for i, sentence_match in enumerate(sentences):
            sent_start = sentence_match.start()
            sent_end = sentence_match.end()
            if start < sent_end and end > sent_start:
                matching_sentences.add(i)
    
    if not matching_sentences:
        return text
    
    sorted_indices = sorted(matching_sentences)
    result_parts = []
    
    for i in sorted_indices:
        sentence_match = sentences[i]
        sent_text = sentence_match.group().strip()
        if sent_text:
            result_parts.append(sent_text)
    
    if len(result_parts) > 1:
        final_parts = [result_parts[0]]
        prev_idx = sorted_indices[0]
        for j, idx in enumerate(sorted_indices[1:], 1):
            if idx != prev_idx + 1:
                final_parts.append('...')
            final_parts.append(result_parts[j])
            prev_idx = idx
        return ' '.join(final_parts)
    
    return ' '.join(result_parts)


def format_title(filename: str, metadata: Dict) -> Dict:
    """Format title information for display."""
    author = metadata.get('author', '')
    title = metadata.get('title', '')
    
    # Clean up filename-based fallbacks
    if not author or not title:
        base = filename.replace('.tess', '')
        parts = base.split('.')
        if len(parts) >= 2:
            author = parts[0].replace('_', ' ').title()
            # Extract title parts (exclude part.N suffixes)
            title_parts = []
            for p in parts[1:]:
                if p == 'part':
                    break
                title_parts.append(p)
            title = ' '.join(title_parts).replace('_', ' ').title()
    
    return {
        'author': author,
        'title': title,
        'display_name': f"{author}, {title}" if author and title else filename
    }


def wildcard_search(
    language: str,
    query: str,
    target_text: Optional[str] = None,
    case_sensitive: bool = False,
    max_results: int = 500,
    era_filter: Optional[str] = None
) -> Dict:
    """
    Perform a wildcard/boolean search across the corpus.
    
    Args:
        language: 'la', 'grc', or 'en'
        query: The search query with wildcards/boolean operators
        target_text: Optional specific text to search (filename)
        case_sensitive: Whether to match case
        max_results: Maximum results to return
        era_filter: Optional era to filter by
        
    Returns:
        Dict with results and metadata
    """
    start_time = time.time()
    
    parsed_query = parse_query(query)
    
    if parsed_query['type'] == 'empty':
        return {
            'results': [],
            'total_matches': 0,
            'search_time': 0,
            'query': query,
            'parsed': parsed_query
        }
    
    lang_dir = os.path.join(TEXTS_DIR, language)
    
    if not os.path.exists(lang_dir):
        return {
            'results': [],
            'total_matches': 0,
            'search_time': 0,
            'error': f'No texts found for language: {language}'
        }
    
    if target_text:
        files_to_search = [target_text] if target_text.endswith('.tess') else [f"{target_text}.tess"]
        files_to_search = [f for f in files_to_search if os.path.exists(os.path.join(lang_dir, f))]
    else:
        files_to_search = [f for f in os.listdir(lang_dir) if f.endswith('.tess')]
    
    all_results = []
    total_match_count = 0
    texts_searched = 0
    
    # Get author dates for chronological sorting
    author_dates = get_author_dates()
    lang_dates = author_dates.get(language, {})
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {}
        for filename in files_to_search:
            filepath = os.path.join(lang_dir, filename)
            metadata = get_text_metadata(filepath)
            future = executor.submit(search_file, filepath, parsed_query, case_sensitive, language)
            futures[future] = (filename, metadata)
        
        for future in as_completed(futures):
            filename, metadata = futures[future]
            texts_searched += 1
            
            try:
                file_results = future.result()
                total_match_count += len(file_results)
                
                # Format title information
                title_info = format_title(filename, metadata)
                
                # Get era and year info for sorting
                author_key = filename.split('.')[0].lower()
                author_info = lang_dates.get(author_key, {})
                era = author_info.get('era', 'Unknown')
                year = author_info.get('year', 9999)
                
                for result in file_results:
                    result['text_id'] = filename
                    result['author'] = title_info['author']
                    result['title'] = title_info['title']
                    result['display_name'] = title_info['display_name']
                    result['era'] = era
                    result['year'] = year
                    result['is_poetry'] = metadata.get('is_poetry', True)
                    # Format reference to be cleaner
                    ref = result.get('ref', '')
                    result['reference'] = ref
                    all_results.append(result)
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
    
    # Sort chronologically by year, then by author name
    all_results.sort(key=lambda r: (r.get('year', 9999), r.get('author', ''), r.get('reference', '')))
    
    # Truncate after sorting
    truncated = len(all_results) > max_results
    all_results = all_results[:max_results]
    
    search_time = time.time() - start_time
    
    return {
        'results': all_results,
        'total_matches': total_match_count,
        'truncated': truncated,
        'texts_searched': texts_searched,
        'total_texts': len(files_to_search),
        'search_time': round(search_time, 3),
        'query': query,
        'parsed_type': parsed_query['type']
    }
