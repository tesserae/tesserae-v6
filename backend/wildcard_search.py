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

from backend import fspaths
import re
import sys
import unicodedata
from typing import List, Dict, Optional, Tuple
import time

from backend.logging_config import get_logger
from backend.metadata_cache import get_text_metadata_cached as get_text_metadata
from backend.utils import detect_text_type, resolve_text_path

logger = get_logger('wildcard_search')

# Coptic normalization reconciles the two Unicode encodings of Coptic
# (legacy "Greek and Coptic" block vs the modern Coptic block) and strips
# supralinear strokes, so a typed query matches the stored text. Guarded so a
# missing coptic package can never break Latin/Greek/English wildcard search.
try:
    from backend.coptic.processor import normalize_coptic
except Exception:  # pragma: no cover
    def normalize_coptic(text):
        return text

from backend.string_fold import RULES_LABEL, fold_arabic_script, fold_hebrew_accents, fold_hebrew_script  # noqa: E402

# Persian, Urdu, Arabic and Hebrew: String Search compares spelling variants
# (the default) or the characters as typed (spelling='strict').
SCRIPT_LANGUAGES = ('fa', 'ur', 'ar', 'he')
_SEP_CLASS = '[\\s\u200c]*'
_SEP_RUN = re.compile('[\\s\u200c]+')
_EDGE_SEPS = re.compile('^[\\s\u200c]+|[\\s\u200c]+$')


def spelling_mode(language: str, spelling: Optional[str] = None) -> str:
    """'variants', 'strict' or (he only) 'points' for fa, ur, ar and he, 'literal' for every other language."""
    if language not in SCRIPT_LANGUAGES:
        return 'literal'
    if spelling == 'points' and language == 'he':
        return 'points'
    return 'strict' if spelling == 'strict' else 'variants'


def _trim(text: str, mode: str) -> str:
    """Edges trimmed: whitespace, and for the four languages also the zero-width non-joiner."""
    if mode in ('variants', 'strict', 'points'):
        return _EDGE_SEPS.sub('', text)
    return text.strip()


def get_author_dates():
    """Get author dates from app.py"""
    try:
        from backend.app import AUTHOR_DATES
        return AUTHOR_DATES
    except ImportError:
        return {}

_COMBINING_RE = None
_COMBINING_TABLE = None

# Text longer than this is stripped of its combining marks with a lookup table
# over its code points (numpy) instead of a regex substitution, which is the
# same operation at several times the speed.
_BULK_MARKS_FROM = 20000
_BULK_MARKS_CHUNK = 4_000_000


def _combining_re():
    """A compiled class of every code point for which unicodedata.combining() is nonzero.

    Built once per process from the interpreter's own Unicode tables, so a regex
    substitution with it removes exactly the characters the per-character test
    `unicodedata.combining(ch)` removes, at C speed.
    """
    global _COMBINING_RE
    if _COMBINING_RE is None:
        ranges = []
        start = None
        for cp in range(sys.maxunicode + 1):
            if unicodedata.combining(chr(cp)):
                if start is None:
                    start = cp
            elif start is not None:
                ranges.append((start, cp - 1))
                start = None
        if start is not None:
            ranges.append((start, sys.maxunicode))
        body = ''.join(
            f'\\U{a:08x}' if a == b else f'\\U{a:08x}-\\U{b:08x}' for a, b in ranges)
        _COMBINING_RE = re.compile('[' + body + ']')
    return _COMBINING_RE


def _combining_table():
    """A boolean array over every code point: True where unicodedata.combining() is nonzero."""
    global _COMBINING_TABLE
    if _COMBINING_TABLE is None:
        import numpy as np
        table = np.zeros(sys.maxunicode + 1, dtype=bool)
        for cp in range(sys.maxunicode + 1):
            if unicodedata.combining(chr(cp)):
                table[cp] = True
        _COMBINING_TABLE = table
    return _COMBINING_TABLE


def _strip_combining(decomposed: str) -> str:
    """The text of an NFD string with every combining character removed."""
    if len(decomposed) >= _BULK_MARKS_FROM:
        try:
            import numpy as np
            table = _combining_table()
            parts = []
            for i in range(0, len(decomposed), _BULK_MARKS_CHUNK):
                chunk = decomposed[i:i + _BULK_MARKS_CHUNK]
                codes = np.frombuffer(chunk.encode('utf-32-le'), dtype='<u4')
                marks = table[codes]
                if marks.any():
                    chunk = codes[~marks].tobytes().decode('utf-32-le')
                parts.append(chunk)
            return ''.join(parts)
        except Exception:
            pass  # a string numpy cannot take (a lone surrogate): the regex below handles it
    return _combining_re().sub('', decomposed)


def normalize_greek(text: str) -> str:
    """
    Remove Greek diacritics (accents, breathings, iota subscripts) so an
    accented query matches accentless text and vice versa -- e.g. both 'λογος'
    and 'λόγος' match the corpus.

    Works regardless of Unicode normalization form: the text is decomposed
    (NFD) so every diacritic becomes a combining mark, then all combining marks
    are stripped. The Greek corpus is stored in NFD while typed/pasted queries
    are usually NFC; the previous precomposed-only character map reduced NFC
    queries to base letters but left the NFD corpus untouched, so accented
    queries matched nothing. Case is preserved -- the caller controls
    case-sensitivity via regex flags.

    The marks are removed with a table or a regex built from
    unicodedata.combining (see _strip_combining), which gives the same string
    as joining the characters whose combining class is zero; ASCII text, which
    holds no mark, is returned as it is.
    """
    if text.isascii():
        return text
    return _strip_combining(unicodedata.normalize('NFD', text))

# One shared rule, backend/latin_orthography.py. This is the SURFACE form:
# case is kept and the archaic word-final -om folds to -um, so a search for
# "divum" finds "diuom". It must never be used for a lemma or an index key,
# because the tables hold "diuom" itself.
from backend.latin_orthography import fold_latin_surface as normalize_latin  # noqa: E402


TEXTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'texts')


_QUERY_TYPES = ('empty', 'simple', 'and', 'or', 'not', 'proximity')


def _split_on(query: str, operator: str) -> List[str]:
    """Split on a word operator (AND, OR, NOT), case-insensitively."""
    return re.split(r'\s+' + operator + r'\s+', query, flags=re.IGNORECASE)


def _parse_not(query: str, mode: str = 'literal') -> Dict:
    """NOT binds tightest and reads left to right: a NOT b NOT c is (a NOT b) NOT c."""
    if ' NOT ' not in query.upper():
        return parse_term(query, mode)
    parts = _split_on(query, 'NOT')
    if len(parts) < 2:
        return parse_term(query, mode)
    node = parse_term(_trim(parts[0], mode), mode)
    for part in parts[1:]:
        node = {'type': 'not', 'include': node, 'exclude': parse_term(_trim(part, mode), mode)}
    return node


def _strip_not(node: Dict) -> Tuple[Dict, List[Dict]]:
    """Return the term under a chain of NOT nodes and the excluded terms, leftmost first."""
    excluded = []
    while node['type'] == 'not':
        excluded.append(node['exclude'])
        node = node['include']
    return node, list(reversed(excluded))


def _parse_proximity(query: str, mode: str = 'literal') -> Dict:
    """Proximity takes two operands, so a NOT inside an operand is moved out to
    cover the whole pair: a ~ b NOT c is (a ~ b) NOT c, and a NOT b ~ c is
    (a ~ c) NOT b."""
    if ' ~ ' not in query:
        return _parse_not(query, mode)
    left, right = query.split(' ~ ', 1)
    term1, excluded1 = _strip_not(_parse_not(_trim(left, mode), mode))
    term2, excluded2 = _strip_not(_parse_not(_trim(right, mode), mode))
    node = {
        'type': 'proximity',
        'term1': term1,
        'term2': term2,
        'distance': 100,  # ~100 characters as per PHI
    }
    for term in excluded1 + excluded2:
        node = {'type': 'not', 'include': node, 'exclude': term}
    return node


def parse_query(query: str, mode: str = 'literal') -> Dict:
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

    Several operators in one query follow the ordinary precedence, tightest
    first: NOT, then proximity (~), then AND, then OR, each read left to right.
    So "a OR b AND c" is a OR (b AND c), and "a AND b NOT c" is a AND (b NOT c).
    A query with one operator parses as a flat node. A mixed query nests: the
    "terms" of an and/or node, the "include" and "exclude" of a not node, hold
    the nested node where a plain term would be. Proximity takes two terms, so
    a NOT written inside a proximity operand covers the whole pair.

    mode is 'literal' (every language but fa, ur, ar and he), 'variants' or
    'strict' (see spelling_mode). In the two script modes the edges of the
    query and of each term lose stray spaces and non-joiners, and in
    'variants' a separator inside a term (spaces, non-joiners, or both)
    matches any separator in the text or none.
    """
    query = _trim(query, mode)

    if not query:
        return {'type': 'empty', 'terms': []}

    node = _parse_or(query, mode)
    if node['type'] not in _QUERY_TYPES:
        return {'type': 'simple', 'terms': [node]}
    return node


def _parse_or(query: str, mode: str = 'literal') -> Dict:
    if ' OR ' in query.upper():
        parts = [_trim(p, mode) for p in _split_on(query, 'OR')]
        return {'type': 'or', 'terms': [_parse_and(p, mode) for p in parts if p]}
    return _parse_and(query, mode)


def _parse_and(query: str, mode: str = 'literal') -> Dict:
    if ' AND ' in query.upper():
        parts = [_trim(p, mode) for p in _split_on(query, 'AND')]
        return {'type': 'and', 'terms': [_parse_proximity(p, mode) for p in parts if p]}
    return _parse_proximity(query, mode)


def parse_term(term: str, mode: str = 'literal') -> Dict:
    """Parse a single search term into a pattern."""
    term = _trim(term, mode)
    broad = mode in ('variants', 'points')
    
    if term.startswith('"') and term.endswith('"'):
        phrase = _trim(term[1:-1], mode)
        return {'type': 'phrase', 'value': phrase, 'pattern': phrase_to_regex(phrase, broad)}
    
    # Handle word break character # (explicit word boundary)
    has_word_break = '#' in term
    if has_word_break:
        term = term.replace('#', '')
    
    if '*' in term or '?' in term:
        return {'type': 'wildcard', 'value': term, 'pattern': wildcard_to_regex(term, broad), 'word_break': has_word_break}
    
    pattern = wildcard_to_regex(term, True) if broad else re.escape(term)
    return {'type': 'exact', 'value': term, 'pattern': pattern, 'word_break': has_word_break}


def wildcard_to_regex(pattern: str, broad_separators: bool = False) -> str:
    """Convert PHI-style wildcards to regex.

    With broad_separators, a run of spaces and non-joiners becomes a pattern
    that matches any such run in the text or none.
    """
    regex = ''
    in_sep = False
    for char in pattern:
        if broad_separators:
            if _SEP_RUN.fullmatch(char):
                if not in_sep:
                    regex += _SEP_CLASS
                in_sep = True
                continue
            in_sep = False
        if char == '*':
            regex += r'\w*'
        elif char == '?':
            regex += r'\w'
        else:
            regex += re.escape(char)
    return regex


def phrase_to_regex(phrase: str, broad_separators: bool = False) -> str:
    """Convert phrase to regex that matches the words in sequence."""
    if broad_separators:
        words = [w for w in _SEP_RUN.split(phrase) if w]
        return r'\b' + _SEP_CLASS.join(re.escape(w) for w in words) + r'\b'
    words = phrase.split()
    pattern = r'\b' + r'\s+'.join(re.escape(w) for w in words) + r'\b'
    return pattern


_REF_LINE = re.compile(r'^<([^>]+)>\s*(.+)$')


def _is_prose_file(filename: str, language: str) -> bool:
    return detect_text_type(filename, language=language) == 'prose'


def _folder(language: str, spelling: Optional[str] = None):
    """The function that puts a line (or a pattern) into the form it is compared in, or None.

    Greek, Latin and Coptic fold as they always have. Persian, Urdu, Arabic
    and Hebrew fold in the 'variants' spelling mode (the default) and are
    compared as typed in 'strict'. Every other language is compared as it is.
    """
    if language == 'grc':
        return normalize_greek
    if language == 'la':
        return normalize_latin
    if language == 'cop':
        return normalize_coptic
    mode = spelling_mode(language, spelling)
    if mode == 'points':
        return fold_hebrew_accents
    if mode == 'variants':
        return fold_hebrew_script if language == 'he' else fold_arabic_script
    return None


def _flags_for(case_sensitive: bool, language: str) -> int:
    """Regex flags: case is ignored unless asked for, and always for fa, ur, ar and he."""
    if language in SCRIPT_LANGUAGES:
        return re.IGNORECASE
    return 0 if case_sensitive else re.IGNORECASE


def _search_text(text: str, language: str, spelling: Optional[str] = None) -> str:
    """The text of one line in the form the query is matched against."""
    fold = _folder(language, spelling)
    return fold(text) if fold else text


def _fold_pattern(pattern: str, language: str, spelling: Optional[str] = None) -> str:
    """A term's pattern folded the way matches_term folds it."""
    fold = _folder(language, spelling)
    return fold(pattern) if fold else pattern


def _leaf_regex_fold(term: Dict, flags: int, fold):
    pattern = term['pattern']
    return re.compile(r'\b' + (fold(pattern) if fold else pattern) + r'\b', flags)


def _leaf_regex(term: Dict, flags: int, language: str, spelling: Optional[str] = None):
    """The compiled pattern matches_term and matches_proximity search with."""
    return _leaf_regex_fold(term, flags, _folder(language, spelling))


def _build_matcher(node: Dict, flags: int, language: str, spelling: Optional[str] = None):
    """matches_query with the patterns folded and compiled once.

    Returns a function of the (already folded) line text that answers exactly
    what matches_query(text, node, flags, ...) answers for this language; the
    folding of each pattern, which matches_query repeats for every line, is
    done here once.
    """
    return _build_matcher_fold(node, flags, _folder(language, spelling),
                               refold=language in ('grc', 'la'))


def _build_matcher_fold(node: Dict, flags: int, fold, refold: bool = False):
    """_build_matcher with the folding function given directly (None folds nothing)."""
    query_type = node.get('type', 'simple')

    if query_type == 'empty':
        return lambda text: False

    def child(sub):
        if sub.get('type') in _QUERY_TYPES:
            return _build_matcher_fold(sub, flags, fold, refold)
        rx = _leaf_regex_fold(sub, flags, fold)
        return lambda text: bool(rx.search(text))

    if query_type in ('simple', 'and'):
        subs = [child(t) for t in node['terms']]
        return lambda text: all(m(text) for m in subs)

    if query_type == 'or':
        subs = [child(t) for t in node['terms']]
        return lambda text: any(m(text) for m in subs)

    if query_type == 'not':
        include = child(node['include'])
        exclude = child(node['exclude'])
        return lambda text: include(text) and not exclude(text)

    if query_type == 'proximity':
        rx1 = _leaf_regex_fold(node['term1'], flags, fold)
        rx2 = _leaf_regex_fold(node['term2'], flags, fold)
        distance = node.get('distance', 100)

        def near(text):
            if refold:
                # matches_proximity folds the text again, as it always has
                text = fold(text)
            matches1 = list(rx1.finditer(text))
            matches2 = list(rx2.finditer(text))
            if not matches1 or not matches2:
                return False
            for m1 in matches1:
                for m2 in matches2:
                    if m1.end() <= m2.start():
                        dist = m2.start() - m1.end()
                    else:
                        dist = m1.start() - m2.end()
                    if dist <= distance:
                        return True
            return False
        return near

    return lambda text: False


def _required_leaves(node: Dict):
    """Plain terms of which a line must match at least one to match the query, or None.

    A line that satisfies the query satisfies at least one of these terms, so a
    line none of them matches can be skipped without being tested. None when
    the node gives no such guarantee (then every line is tested).
    """
    query_type = node.get('type', 'simple')
    if query_type not in _QUERY_TYPES:
        return [node] if 'pattern' in node else None
    if query_type in ('simple', 'and'):
        for term in node.get('terms', []):
            leaves = _required_leaves(term)
            if leaves:
                return leaves
        return None
    if query_type == 'or':
        leaves = []
        for term in node.get('terms', []):
            sub = _required_leaves(term)
            if not sub:
                return None
            leaves.extend(sub)
        return leaves or None
    if query_type == 'not':
        return _required_leaves(node['include'])
    if query_type == 'proximity':
        return [node['term1']]
    return None


def _fold_whole(raw: str, language: str, spelling: Optional[str] = None) -> str:
    """The whole file folded for language; line breaks stay where they were."""
    return _search_text(raw, language, spelling)


def _candidate_lines(raw: str, parsed_query: Dict, flags: int, language: str, spelling: Optional[str] = None):
    """Indexes (ascending) of the lines of `raw` that can match the query, or None for all.

    Folds the whole file once and runs the required terms over it. A line the
    query matches holds a match of one of those terms, and a match of the
    folded line is also a match of the folded file around it, so every line
    that matches is kept; the lines kept are then tested exactly, line by
    line, as before. A match that runs over a line break marks every line it
    touches.
    """
    leaves = _required_leaves(parsed_query)
    if not leaves:
        return None
    folded = _fold_whole(raw, language, spelling)
    if folded.count('\n') != raw.count('\n'):
        return None
    found = set()
    for term in leaves:
        # The term's pattern without its word-boundary tests: whatever the
        # term matches this matches at the same place, and without the leading
        # \b the regex engine can skip ahead to the first letter instead of
        # trying every position (about twice as fast).
        rx = re.compile(_fold_pattern(term['pattern'], language, spelling), flags)
        line = 0
        last = 0
        for m in rx.finditer(folded):
            start, end = m.span()
            line += folded.count('\n', last, start)
            last = start
            found.add(line)
            if end > start:
                for k in range(1, folded.count('\n', start, end) + 1):
                    found.add(line + k)
    return sorted(found)


def scan_file(filepath: str, parsed_query: Dict, case_sensitive: bool = False, language: str = 'la',
              spelling: Optional[str] = None) -> List[Tuple[str, str]]:
    """The (reference, text) of every line of one .tess file that matches, in file order.

    Nothing is built for a match beyond those two strings; finish_match turns
    one into the row search_file returns.
    """
    matches = []
    try:
        with fspaths.open_text(filepath, 'r', encoding='utf-8') as f:
            raw = f.read()
    except Exception as e:
        logger.error(f"Error reading {filepath}: {e}")
        return matches

    flags = _flags_for(case_sensitive, language)
    wanted = _candidate_lines(raw, parsed_query, flags, language, spelling)
    if wanted is not None and not wanted:
        return matches
    lines = raw.split('\n')
    matcher = _build_matcher(parsed_query, flags, language, spelling)

    candidates = []
    for i in (range(len(lines)) if wanted is None else wanted):
        line = lines[i].strip()
        if not line or line.startswith('#'):
            continue

        match = _REF_LINE.match(line)
        if not match:
            continue

        candidates.append((match.group(1), match.group(2)))

    # Fold the texts of the candidate lines together, in one piece. A line
    # break is a boundary for every fold, so the folded block cut at its line
    # breaks is each text folded alone.
    if language in ('grc', 'la') and len(candidates) > 1:
        folded = _fold_whole('\n'.join(text for _ref, text in candidates), language, spelling).split('\n')
        if len(folded) != len(candidates):
            folded = [_search_text(text, language, spelling) for _ref, text in candidates]
    else:
        folded = [_search_text(text, language, spelling) for _ref, text in candidates]

    for (ref, text), search_text in zip(candidates, folded):
        if matcher(search_text):
            matches.append((ref, text))

    return matches


def get_folded_highlight_indices(text: str, parsed_query: Dict, flags: int, fold) -> List[List[int]]:
    """Whole-token highlight spans on the raw text for a fold that only removes or swaps single characters.

    The text is folded character by character with a map back to the raw
    positions, the terms are matched on the folded text (so a phrase of two
    words can match across the space), and each match is widened to the
    whitespace-delimited tokens it touches.
    """
    terms = _leaf_terms(parsed_query)
    if not terms:
        return []
    chars = []
    origin = []
    for i, ch in enumerate(text):
        folded_ch = fold(ch)
        for c in folded_ch:
            chars.append(c)
            origin.append(i)
    folded = ''.join(chars)
    spans = []
    for term in terms:
        rx = re.compile(r'\b' + fold(term['pattern']) + r'\b', flags)
        for m in rx.finditer(folded):
            if m.end() <= m.start():
                continue
            start = origin[m.start()]
            end = origin[m.end() - 1] + 1
            while start > 0 and not text[start - 1].isspace():
                start -= 1
            while end < len(text) and not text[end].isspace():
                end += 1
            spans.append([start, end])
    spans.sort(key=lambda x: x[0])
    return spans


def finish_match(ref: str, text: str, parsed_query: Dict, case_sensitive: bool, language: str, is_prose: bool,
                 spelling: Optional[str] = None) -> Dict:
    """The row for one matching line: display text, highlighting and flags."""
    is_greek = language == 'grc'
    is_latin = language == 'la'
    is_coptic = language == 'cop'
    flags = _flags_for(case_sensitive, language)
    script_fold = _folder(language, spelling) if language in SCRIPT_LANGUAGES else None

    # Coptic and Greek normalizers change string length (strokes /
    # combining accents are stripped), so match positions on the
    # normalized text don't map back to the raw display text. Highlight
    # whole tokens for those; Latin/English keep exact-span highlights.
    token_normalizer = normalize_coptic if is_coptic else (normalize_greek if is_greek else None)

    def highlights(shown):
        # Points mode reorders marks, which breaks the one-to-one character map
        # of the folded path, so it highlights whole tokens.
        if script_fold is fold_hebrew_accents:
            return get_token_highlight_indices(shown, parsed_query, flags, script_fold)
        if script_fold:
            return get_folded_highlight_indices(shown, parsed_query, flags, script_fold)
        if token_normalizer:
            return get_token_highlight_indices(shown, parsed_query, flags, token_normalizer)
        return get_highlight_indices(shown, parsed_query, flags, is_greek, is_latin)

    highlight_indices = highlights(text)

    # For prose, extract only sentences containing matches
    display_text = text
    if is_prose and len(text) > 150:
        display_text = extract_sentences_with_matches(text, highlight_indices)
        highlight_indices = highlights(display_text)

    # Apply HTML highlighting
    highlighted_text = apply_highlighting(display_text, highlight_indices)

    return {
        'ref': ref,
        'text': display_text,
        'highlighted_text': highlighted_text,
        'is_prose': is_prose
    }


def search_file(filepath: str, parsed_query: Dict, case_sensitive: bool = False, language: str = 'la',
                spelling: Optional[str] = None) -> List[Dict]:
    """Search a single .tess file for matches."""
    filename = os.path.basename(filepath)
    is_prose = _is_prose_file(filename, language)
    return [finish_match(ref, text, parsed_query, case_sensitive, language, is_prose, spelling)
            for ref, text in scan_file(filepath, parsed_query, case_sensitive, language, spelling)]


_NOTE_MARKS = 'vowel marks ignored'
_NOTE_SEPARATOR = 'separator variant matched'
_NOTE_LETTERS = 'letter variant matched'
_NOTE_ACCENTS = 'accents ignored'


def make_match_noter(query: str, language: str, case_sensitive: bool = False, mode: str = 'variants'):
    """A function of a raw matching line that says why the line matched, in variants mode.

    It returns [] for a line the query matches exactly as typed. Otherwise it
    refolds with one family (marks, separators, letters) disabled at a time
    and lists each family whose absence breaks the match, in the order marks,
    separators, letters. Three extra regex runs per matched line, none on the
    candidate scan.
    """
    flags = _flags_for(case_sensitive, language)
    literal = _build_matcher_fold(parse_query(query, 'strict'), flags, None)
    if mode == 'points':
        accent_match = _build_matcher_fold(parse_query(query, 'points'), flags, fold_hebrew_accents)

        def accent_note(text: str) -> List[str]:
            if literal(text):
                return []
            return [_NOTE_ACCENTS] if accent_match(fold_hebrew_accents(text)) else []

        return accent_note
    broad = parse_query(query, 'variants')
    hebrew = language == 'he'

    def fold_with(marks, letters):
        if hebrew:
            return lambda t: fold_hebrew_script(t, marks=marks)
        return lambda t: fold_arabic_script(t, marks=marks, letters=letters)

    def matcher(marks, separators, letters):
        node = broad if separators else parse_query(query, 'strict')
        fold = fold_with(marks, letters)
        return fold, _build_matcher_fold(node, flags, fold)

    families = [(_NOTE_MARKS, (False, True, True)), (_NOTE_SEPARATOR, (True, False, True))]
    if not hebrew:
        families.append((_NOTE_LETTERS, (True, True, False)))
    without = [(label, matcher(*on)) for label, on in families]

    def note(text: str) -> List[str]:
        if literal(text):
            return []
        notes = []
        for label, (fold, match) in without:
            if not match(fold(text)):
                notes.append(label)
        return notes

    return note


def matches_query(text: str, parsed_query: Dict, flags: int, is_greek: bool = False, is_latin: bool = False, is_coptic: bool = False) -> bool:
    """Check if text matches the parsed query."""
    query_type = parsed_query.get('type', 'simple')

    if query_type == 'empty':
        return False

    def hit(node):
        # A nested node (from a mixed query) is a query of its own; anything
        # else is a plain term.
        if node.get('type') in _QUERY_TYPES:
            return matches_query(text, node, flags, is_greek, is_latin, is_coptic)
        return matches_term(text, node, flags, is_greek, is_latin, is_coptic)

    if query_type in ('simple', 'and'):
        return all(hit(term) for term in parsed_query['terms'])

    if query_type == 'or':
        return any(hit(term) for term in parsed_query['terms'])

    if query_type == 'not':
        return hit(parsed_query['include']) and not hit(parsed_query['exclude'])

    if query_type == 'proximity':
        return matches_proximity(text, parsed_query, flags, is_greek, is_latin, is_coptic)

    return False


def _leaf_terms(parsed_query: Dict) -> List[Dict]:
    """The plain terms to highlight: the excluded side of a NOT is left out."""
    query_type = parsed_query.get('type', 'simple')
    if query_type in ('simple', 'and', 'or'):
        nodes = parsed_query.get('terms', [])
    elif query_type == 'not':
        nodes = [parsed_query['include']]
    elif query_type == 'proximity':
        nodes = [parsed_query['term1'], parsed_query['term2']]
    else:
        nodes = []
    leaves = []
    for node in nodes:
        if node.get('type') in _QUERY_TYPES:
            leaves.extend(_leaf_terms(node))
        else:
            leaves.append(node)
    return leaves


def matches_proximity(text: str, parsed_query: Dict, flags: int, is_greek: bool = False, is_latin: bool = False, is_coptic: bool = False) -> bool:
    """Check if two terms appear within the specified character distance."""
    term1 = parsed_query['term1']
    term2 = parsed_query['term2']
    distance = parsed_query.get('distance', 100)

    pattern1 = term1['pattern']
    pattern2 = term2['pattern']

    if is_greek:
        pattern1 = normalize_greek(pattern1)
        pattern2 = normalize_greek(pattern2)
    elif is_latin:
        pattern1 = normalize_latin(pattern1)
        pattern2 = normalize_latin(pattern2)
    elif is_coptic:
        pattern1 = normalize_coptic(pattern1)
        pattern2 = normalize_coptic(pattern2)
    
    pattern1 = r'\b' + pattern1 + r'\b'
    pattern2 = r'\b' + pattern2 + r'\b'
    
    if is_greek:
        search_text = normalize_greek(text)
    elif is_latin:
        search_text = normalize_latin(text)
    else:
        search_text = text
    
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


def matches_term(text: str, term: Dict, flags: int, is_greek: bool = False, is_latin: bool = False, is_coptic: bool = False) -> bool:
    """Check if text matches a single term."""
    pattern = term['pattern']
    if is_greek:
        pattern = normalize_greek(pattern)
    elif is_latin:
        pattern = normalize_latin(pattern)
    elif is_coptic:
        pattern = normalize_coptic(pattern)
    pattern = r'\b' + pattern + r'\b'
    return bool(re.search(pattern, text, flags))


def get_highlight_indices(text: str, parsed_query: Dict, flags: int, is_greek: bool = False, is_latin: bool = False) -> List[List[int]]:
    """Get character indices to highlight in the text."""
    indices = []
    terms = _leaf_terms(parsed_query)

    if is_greek:
        search_text = normalize_greek(text)
    elif is_latin:
        search_text = normalize_latin(text)
    else:
        search_text = text
    
    for term in terms:
        pattern = term['pattern']
        if is_greek:
            pattern = normalize_greek(pattern)
        elif is_latin:
            pattern = normalize_latin(pattern)
        pattern = r'\b' + pattern + r'\b'
        for match in re.finditer(pattern, search_text, flags):
            indices.append([match.start(), match.end()])
    
    indices.sort(key=lambda x: x[0])
    return indices


def get_token_highlight_indices(text: str, parsed_query: Dict, flags: int, normalizer) -> List[List[int]]:
    """Highlight indices at whole-token (whitespace-delimited) granularity.

    Used for languages whose normalizer changes string length, so exact match
    offsets on the normalized string don't line up with the raw display text:
    normalize_coptic() strips supralinear strokes, and normalize_greek() strips
    combining accents. Walk the raw text token by token, normalize each token,
    and mark the whole raw token when a query term matches inside it. Spans are
    on the raw text, so they align with apply_highlighting(). For Greek this is
    exactly word-level highlighting; for Coptic it highlights the bound group.
    """
    terms = _leaf_terms(parsed_query)

    patterns = [r'\b' + normalizer(t['pattern']) + r'\b' for t in terms]
    if not patterns:
        return []

    indices = []
    for m in re.finditer(r'\S+', text):
        token_norm = normalizer(m.group(0))
        if any(re.search(p, token_norm, flags) for p in patterns):
            indices.append([m.start(), m.end()])
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
    era_filter: Optional[str] = None,
    spelling: Optional[str] = None
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
        spelling: 'variants' (default) or 'strict' for fa, ur, ar and he, and 'points' for he only (treated as 'variants' elsewhere); ignored otherwise
        
    Returns:
        Dict with results and metadata
    """
    start_time = time.time()
    
    mode = spelling_mode(language, spelling)
    parsed_query = parse_query(query, mode)
    matching = {
        'mode': mode,
        'rules': RULES_LABEL,
        'query': query,
        'query_used': _trim(query, mode),
    }
    
    if parsed_query['type'] == 'empty':
        return {
            'results': [],
            'total_matches': 0,
            'search_time': 0,
            'query': query,
            'parsed': parsed_query,
            'matching': matching
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
        # Try with and without .tess suffix to match existing UI behaviour,
        # while resolve_text_path() handles Unicode normalization mismatches
        candidate = target_text if target_text.endswith('.tess') else f"{target_text}.tess"
        source_path = resolve_text_path(TEXTS_DIR, language, candidate) or \
                      resolve_text_path(TEXTS_DIR, language, target_text)
        files_to_search = [fspaths.fs_name(os.path.basename(fspaths.fs_path(source_path)))] if source_path else []
    else:
        files_to_search = [f for f in fspaths.listdir_text(lang_dir) if f.endswith('.tess')]
    
    # One entry per matching line: (sort key, file, metadata, reference, text).
    # The row itself (display text, highlighting) is built after the sort, for
    # the lines that are returned.
    found = []
    total_match_count = 0
    texts_searched = 0
    
    # Get author dates for chronological sorting
    author_dates = get_author_dates()
    lang_dates = author_dates.get(language, {})
    
    # The files are scanned one after another in the order the folder lists
    # them. They used to go to eight threads and be taken in the order the
    # scans finished, but the scan is Python code holding the interpreter lock,
    # so the threads took turns instead of running together, and rows that
    # share a sort key (the same reference under one author, as in a work held
    # whole and in book files) came back in whichever order the threads
    # happened to finish. Now they come back in folder order every time.
    for filename in files_to_search:
        filepath = os.path.join(lang_dir, filename)
        texts_searched += 1

        try:
            file_matches = scan_file(filepath, parsed_query, case_sensitive, language, spelling)
            total_match_count += len(file_matches)
            if not file_matches:
                continue

            # The title and kind of a text are worked out only for a text
            # that has a matching line.
            metadata = get_text_metadata(filepath)
            # Format title information
            title_info = format_title(filename, metadata)

            # Get era and year info for sorting
            author_key = filename.split('.')[0].lower()
            author_info = lang_dates.get(author_key, {})
            era = author_info.get('era', 'Unknown')
            # None (not the 9999 sentinel) for an unknown year, so it does not
            # leak into output and plot as year 9999 on a timeline. The sort
            # below coalesces None -> 9999 for ordering only.
            year = author_info.get('year')

            file_info = (filename, metadata, title_info, era, year)
            for ref, text in file_matches:
                found.append(((year or 9999, title_info['author'], ref), file_info, ref, text))
        except Exception as e:
            logger.error(f"Error processing {filename}: {e}")
    
    found.sort(key=lambda item: item[0])
    
    # Truncate after sorting
    truncated = len(found) > max_results
    found = found[:max_results]

    noter = make_match_noter(query, language, case_sensitive, mode) if mode in ('variants', 'points') and found else None
    prose_of = {}
    all_results = []
    for _key, (filename, metadata, title_info, era, year), ref, text in found:
        if filename not in prose_of:
            prose_of[filename] = _is_prose_file(filename, language)
        result = finish_match(ref, text, parsed_query, case_sensitive, language, prose_of[filename], spelling)
        if noter:
            result['match_note'] = noter(text)
        result['text_id'] = filename
        result['author'] = title_info['author']
        result['title'] = title_info['title']
        result['display_name'] = title_info['display_name']
        result['era'] = era
        result['year'] = year
        result['is_poetry'] = metadata.get('is_poetry', True)
        # Format reference to be cleaner
        result['reference'] = ref
        all_results.append(result)
    
    search_time = time.time() - start_time
    
    return {
        'results': all_results,
        'total_matches': total_match_count,
        'truncated': truncated,
        'texts_searched': texts_searched,
        'total_texts': len(files_to_search),
        'search_time': round(search_time, 3),
        'query': query,
        'parsed_type': parsed_query['type'],
        'matching': matching
    }
