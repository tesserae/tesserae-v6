"""
Tesserae V6 - Inverted Index

Pre-built SQLite index for fast corpus-wide lemma searches.
Enables O(1) lookup of any lemma to find all occurrences across the corpus.

Structure:
    lemma → [(text_id, line_reference, word_positions), ...]

Index Files:
    - data/inverted_index/la_index.db: Latin corpus
    - data/inverted_index/grc_index.db: Greek corpus
    - data/inverted_index/en_index.db: English corpus

Usage:
    from backend.inverted_index import lookup_lemmas
    
    results = lookup_lemmas(['amor', 'bellum'], 'la')
    # Returns dict: {(text_id, ref) -> {'lemmas': [...], 'positions': [...]}}
"""
import os

from backend import fspaths
import sqlite3
import json
from collections.abc import Mapping
from functools import lru_cache

from backend.logging_config import get_logger
from backend.thread_connections import PerThreadConnections

logger = get_logger('inverted_index')

INDEX_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'inverted_index')

_connections = PerThreadConnections()  # one sqlite3 connection per thread (backend/thread_connections.py)

# json.loads wraps the C scanner in several Python calls, which costs more than
# the scan itself for the short lists the index stores (a few hundred thousand
# of them in one common-word search). _scan_json calls the scanner directly and
# gives the same value; any text it cannot take whole goes to json.loads.
_json_scan = json.decoder.JSONDecoder().scan_once


def _scan_json(text):
    try:
        value, end = _json_scan(text, 0)
        if end == len(text):
            return value
    except (StopIteration, ValueError, IndexError):
        pass
    return json.loads(text)

class _LazyPositions(Mapping):
    """The position lists of one location, read from their JSON text when first asked for.

    A listing of every line holding one very common lemma (the lemma "sum" has
    some 290,000) builds a location for each line, and the page counts them
    and shows five hundred; the positions of the rest are never looked at.
    This behaves as the dict of lemma to position list it stands in for."""
    __slots__ = ('_raw', '_parsed')

    def __init__(self, raw):
        self._raw = raw
        self._parsed = {}

    def __getitem__(self, key):
        got = self._parsed.get(key)
        if got is None:
            got = self._parsed[key] = _scan_json(self._raw[key])
        return got

    def __iter__(self):
        return iter(self._raw)

    def __len__(self):
        return len(self._raw)


def get_connection(language):
    """Get SQLite connection for a language index (lazy loading)"""
    if language not in _connections:
        db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                _connections[language] = conn
            except Exception as e:
                logger.error(f"Failed to open {language} index: {e}")
                return None
        else:
            return None
    return _connections[language]

def is_index_available(language):
    """Check if inverted index is available for a language"""
    db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
    return os.path.exists(db_path)

_corpus_version = {}

def get_corpus_version(language):
    """Return the corpus/index version stamp (a date string) for a language, or
    None if the index has no `meta` table / corpus_version row.

    The stamp names the exact corpus state a count came from, so a figure that
    shifts as dedup/ingestion/lemmatization improve can still be cited. Bump the
    `meta.corpus_version` value whenever the corpus changes. Memoized per process
    (a re-swapped index is picked up on WSGI reload)."""
    if language in _corpus_version:
        return _corpus_version[language]
    v = None
    conn = get_connection(language)
    if conn:
        try:
            row = conn.execute("SELECT value FROM meta WHERE key='corpus_version'").fetchone()
            if row is not None:
                v = row[0]
        except Exception:
            v = None
    # Fallback: some indexes (notably the he/cop plugin builds) predate the
    # meta-table stamping in scripts/build_inverted_index.py, so they carry no
    # corpus_version row. Rather than return null (which left he/cop responses
    # unstamped while la/grc/en were dated), derive a date stamp from the index
    # DB file's modification time, which tracks when the corpus was last built.
    if v is None:
        try:
            db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
            if os.path.exists(db_path):
                from datetime import date
                v = date.fromtimestamp(os.path.getmtime(db_path)).isoformat()
        except Exception:
            v = None
    # The stamp in `meta` is written by full rebuilds only. Texts added or
    # removed piece by piece change the index file without touching it, so
    # the Latin stamp stayed at 2026-08-16 through months of additions. Use
    # the later of the stamp and the index file's own modification date.
    try:
        db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
        if os.path.exists(db_path):
            from datetime import date
            file_day = date.fromtimestamp(os.path.getmtime(db_path)).isoformat()
            if v is None or (len(str(v)) == 10 and file_day > str(v)):
                v = file_day
    except Exception:
        pass
    _corpus_version[language] = v
    return v

def set_corpus_version(conn, version):
    """Stamp an index DB with a corpus_version (idempotent). Call whenever the
    corpus changes — a full rebuild, a dedup pass, or a lemmatization change.
    `conn` is an open sqlite3 connection to the index DB."""
    conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.execute("INSERT INTO meta (key, value) VALUES ('corpus_version', ?) "
                 "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (version,))
    conn.commit()

# A lemma with at least this many postings is "common" for the rarest-first
# lookup below (in Latin: sum, et, qui, in, non, ut, ad, cum...). Below it the
# plain fetch is cheap and nothing changes.
COMMON_LEMMA_POSTINGS = 20000
# The common lemma is probed on the candidate lines only when its posting list
# is at least this many times longer than the candidates' own lists together.
COMMON_LEMMA_RATIO = 6
_PROBE_CHUNK = 400
_POSTINGS_PER_LINE = 20   # rough, to cost a probe of a text's own postings
# A text's own postings are read in C by SQLite, a common lemma's posting list is
# read into Python objects, so the first may hold several times more rows.
_DUP_TEXT_SCAN_FACTOR = 4


_DUP_REF_CACHE = {}


def _index_stamp(language):
    """(language, size, modification time) of a language's index file: what a kept answer about the index is valid for."""
    try:
        st = os.stat(os.path.join(INDEX_DIR, f'{language}_index.db'))
        return (language, st.st_size, st.st_mtime_ns)
    except OSError:
        return None


def _duplicate_refs(conn, text_id, stamp=None):
    """Refs of a text whose postings are not exactly those of its row in `lines` (a ref held by several lines, or drift).

    A line gives one posting row for each distinct lemma it holds, so a ref
    whose postings number other than the distinct lemmas of its row of `lines`
    is held by more than one line (the later lines add rows) or has drifted.
    Read once for each text and kept for the life of the process, under `stamp`
    (the index file's name, size and date, so a swapped index is read afresh and
    every thread's connection shares the answer); without one, under the connection."""
    key = (id(conn) if stamp is None else stamp, text_id)
    got = _DUP_REF_CACHE.get(key)
    if got is None:
        expected = {ref: len(set(_scan_json(lemmas_json)))
                    for ref, lemmas_json in conn.execute('SELECT ref, lemmas FROM lines WHERE text_id = ?', (text_id,))}
        got = frozenset(
            ref for ref, rows in conn.execute(
                'SELECT ref, COUNT(*) FROM postings INDEXED BY idx_text WHERE text_id = ? GROUP BY ref', (text_id,))
            if rows != expected.get(ref, -1))
        _DUP_REF_CACHE[key] = got
    return got


def _lookup_rarest_first(conn, canonicals, lemma_mapping, min_matches, stamp=None):
    """lookup_lemmas for a query holding a very common lemma, without fetching that lemma's postings.

    Returns what lookup_lemmas returns for this query (the same locations in the
    same order, with the same lemmas and positions), or None when the plain
    fetch should be used (nothing is common enough, the common lemma's variants
    sort among the others, or anything about the index is not as expected).

    A location holding at least `min_matches` of the n query lemmas holds one of
    any n - min_matches + 1 of them, so the postings of the rarest
    n - min_matches + 1 lemmas (F) find every candidate location. The commonest
    min_matches - 1 lemmas (P), when they are common enough to matter, are looked
    up in each candidate line's own row of the `lines` table (one primary-key
    probe per candidate) instead of through their posting lists.

    The plain fetch sees rows in the order of the index on the lemma column, that
    is by lemma spelling and then by row. The first row of a location decides
    where it falls in the result, so this is used only when every spelling of P
    sorts after every spelling of F: then the first row of each location is an F
    row, and F alone gives the order. When a location holds several spellings of
    one lemma the plain fetch keeps the last row seen, which is the largest
    spelling; that is reproduced here.
    """
    m = min_matches
    n = len(canonicals)
    if m < 2 or n < m:
        return None
    owners_of = {v: list(o) for v, o in lemma_mapping.items()}
    variants_of = {c: sorted(v for v, o in owners_of.items() if c in o) for c in canonicals}
    all_variants = sorted({v for vs in variants_of.values() for v in vs})
    marks = ','.join('?' for _ in all_variants)
    counts = dict(conn.execute(
        f'SELECT lemma, COUNT(*) FROM postings WHERE lemma IN ({marks}) GROUP BY lemma',  # nosec B608
        all_variants).fetchall())
    size = {c: sum(counts.get(v, 0) for v in variants_of[c]) for c in canonicals}
    by_size = sorted(canonicals, key=lambda c: (-size[c], c))
    common = [c for c in by_size[:m - 1] if size[c] >= COMMON_LEMMA_POSTINGS]
    if not common:
        return None
    rest = [c for c in canonicals if c not in common]
    rest_total = sum(size[c] for c in rest)
    if min(size[c] for c in common) < COMMON_LEMMA_RATIO * rest_total:
        return None
    f_variants = sorted({v for c in rest for v in variants_of[c]})
    p_variants = sorted({v for c in common for v in variants_of[c]})
    if set(f_variants) & set(p_variants):
        return None
    if not f_variants or f_variants[-1] >= p_variants[0]:
        return None

    marks = ','.join('?' for _ in f_variants)
    pending = {}
    for lemma, filename, ref, positions_json, text_id in conn.execute(
            f'''
            SELECT p.lemma, t.filename, p.ref, p.positions, p.text_id
            FROM postings p JOIN texts t ON p.text_id = t.text_id
            WHERE p.lemma IN ({marks})
            ''',  # nosec B608
            f_variants):
        entry = pending.get((filename, ref))
        if entry is None:
            entry = pending[(filename, ref)] = ({}, set(), text_id)
        for canonical in owners_of.get(lemma, [lemma]):
            entry[0][canonical] = positions_json
            entry[1].add(canonical)

    # Look the common lemmas up on the candidate lines, one text at a time.
    wanted_variants = set(p_variants)
    by_text = {}
    for key, entry in pending.items():
        by_text.setdefault(entry[2], []).append(key)
    # A ref held by several lines has a single row in `lines` (the first line)
    # but postings for every line, and the plain fetch keeps the last row seen,
    # so the row of `lines` would be the wrong line. Such refs (found by
    # _duplicate_refs, only in texts whose line_count exceeds their rows of
    # `lines`) are looked up in the text's own postings instead.
    text_ids = list(by_text)
    suspect = {}
    for i in range(0, len(text_ids), _PROBE_CHUNK):
        chunk = text_ids[i:i + _PROBE_CHUNK]
        marks = ','.join('?' for _ in chunk)
        for text_id, line_count, line_rows in conn.execute(
                'SELECT t.text_id, t.line_count, (SELECT COUNT(*) FROM lines l WHERE l.text_id = t.text_id) '
                f'FROM texts t WHERE t.text_id IN ({marks})', chunk):  # nosec B608
            if line_count != line_rows:
                suspect[text_id] = line_count or 0
    slow_refs = {}
    for text_id in suspect:
        dup = _duplicate_refs(conn, text_id, stamp)
        hit = {ref for _, ref in by_text[text_id] if ref in dup}
        if hit:
            slow_refs[text_id] = hit
    if sum(suspect[t] for t in slow_refs) * _POSTINGS_PER_LINE > _DUP_TEXT_SCAN_FACTOR * min(size[c] for c in common):
        return None
    extra = {}
    p_marks = ','.join('?' for _ in p_variants)
    for text_id, hit in slow_refs.items():
        rows = [(lemma, rowid, ref, positions_json) for lemma, rowid, ref, positions_json in conn.execute(
            'SELECT lemma, rowid, ref, positions FROM postings INDEXED BY idx_text '
            f'WHERE text_id = ? AND lemma IN ({p_marks})', [text_id] + p_variants)  # nosec B608
            if ref in hit]
        rows.sort(key=lambda r: (r[0], r[1]))        # the order the plain fetch sees them
        for lemma, _rowid, ref, positions_json in rows:
            found = extra.setdefault((text_id, ref), {})
            positions = _scan_json(positions_json)
            for canonical in owners_of[lemma]:
                found[canonical] = positions
    for text_id, keys in by_text.items():
        refs = sorted({ref for _, ref in keys} - slow_refs.get(text_id, set()))
        for i in range(0, len(refs), _PROBE_CHUNK):
            chunk = refs[i:i + _PROBE_CHUNK]
            marks = ','.join('?' for _ in chunk)
            seen = 0
            for ref, lemmas_json in conn.execute(
                    f'SELECT ref, lemmas FROM lines WHERE text_id = ? AND ref IN ({marks})',  # nosec B608
                    [text_id] + chunk):
                seen += 1
                if lemmas_json is None:
                    raise ValueError('line without lemmas')
                line_lemmas = _scan_json(lemmas_json)
                present = wanted_variants.intersection(line_lemmas)
                if present:
                    found = {}
                    for variant in sorted(present):
                        positions = [k for k, lem in enumerate(line_lemmas) if lem == variant]
                        for canonical in owners_of[variant]:
                            found[canonical] = positions
                    extra[(text_id, ref)] = found
            if seen != len(chunk):
                raise ValueError('a candidate line has no row in lines')
    results = {}
    for key, (raw_positions, canonicals_found, text_id) in pending.items():
        found = extra.get((text_id, key[1]))
        positions = {c: _scan_json(raw) for c, raw in raw_positions.items()}
        if found:
            for canonical, plist in found.items():
                canonicals_found.add(canonical)
                positions[canonical] = plist
        if len(canonicals_found) < m:
            continue
        results[key] = {'lemmas': canonicals_found, 'positions': positions}
    return results


def lookup_lemmas(lemmas, language, fallback_forms=None, conn=None, min_matches=1):
    """
    Look up multiple lemmas and return matching text locations.

    Args:
        lemmas: List of lemmas to search for
        language: 'la', 'grc', or 'en'
        fallback_forms: Optional dict mapping lemma -> set of inflected forms to also
                       search for. Matches on fallback forms count as matches for the
                       canonical lemma. This bridges the gap between properly lemmatized
                       queries and indexes built with older/incomplete lemma tables.
        conn: Optional sqlite3 connection to use instead of this module's own
                       get_connection(language) (stage 3b-2: backend/documents.py passes
                       its own documents-index connection here so a documents-collection
                       lookup reuses this exact query and the Latin u/v, i/j variant
                       expansion below, keyed on the real `language` ('la'/'grc'), not a
                       pseudo-language — without changing this function's own behaviour
                       for every existing caller, which still passes no `conn` and gets
                       get_connection(language) as before).
        min_matches: Locations holding fewer than this many of the query lemmas
                       are left out (default 1: every location is returned, as
                       always). A caller that wants only locations with several
                       of the lemmas (find_co_occurring_lemmas) passes it, and
                       the positions of the locations that would be dropped are
                       not read.

    Returns:
        Dict mapping (text_id, ref) to list of matching lemmas and positions
    """
    own_connection = conn is None
    if conn is None:
        conn = get_connection(language)
    if not conn:
        return {}

    cursor = conn.cursor()
    results = {}
    
    # Map expanded variants back to the query lemmas they stand for. A variant
    # can stand for SEVERAL: the joined Latin word quousque is a fallback form
    # of both "quo" (qui) and "usque" in a query "quo usque", and must count
    # for each. (A single canonical per variant, as this used to hold, let the
    # last query lemma take it and the others lose the hit.)
    lemma_mapping = {}
    expanded_lemmas = set(lemmas)

    def _map(variant, orig):
        owners = lemma_mapping.setdefault(variant, [])
        if orig not in owners:
            owners.append(orig)

    for orig in lemmas:
        _map(orig, orig)
        if language == 'la':
            for variant in [orig.replace('u', 'v'), orig.replace('v', 'u'),
                           orig.replace('i', 'j'), orig.replace('j', 'i')]:
                expanded_lemmas.add(variant)
                _map(variant, orig)
        # Fallback forms apply in every language (until 2026-10-01 only in
        # Latin, so the Hebrew homograph readings a bare query expands to
        # were ignored); the u/v and i/j spellings are Latin's alone.
        if fallback_forms and orig in fallback_forms:
            fb_list = list(fallback_forms[orig])[:30]
            for fb in fb_list:
                expanded_lemmas.add(fb)
                _map(fb, orig)
                if language == 'la':
                    for variant in [fb.replace('u', 'v'), fb.replace('v', 'u'),
                                   fb.replace('i', 'j'), fb.replace('j', 'i')]:
                        expanded_lemmas.add(variant)
                        _map(variant, orig)
    
    # A query holding a very common lemma, on the index's own connection: find
    # the locations from the other lemmas and look the common one up only on
    # those lines (documents-collection callers pass their own `conn` and keep
    # the plain fetch below). Falls back to the plain fetch when it does not apply.
    if own_connection and min_matches > 1 and language in ('la', 'grc'):
        try:
            fast = _lookup_rarest_first(conn, list(dict.fromkeys(lemmas)), lemma_mapping, min_matches,
                                        stamp=_index_stamp(language))
        except Exception as e:
            logger.warning(f"Rarest-first lookup skipped: {e}")
            fast = None
        if fast is not None:
            return fast

    expanded_list = list(expanded_lemmas)
    placeholders = ','.join(['?' for _ in expanded_list])
    query = f'''
        SELECT p.lemma, t.filename, p.ref, p.positions
        FROM postings p
        JOIN texts t ON p.text_id = t.text_id
        WHERE p.lemma IN ({placeholders})
    '''  # nosec B608
    
    try:
        cursor.execute(query, expanded_list)  # nosec B608
        if min_matches > 1:
            # Collect each location's lemmas and the raw positions first, and
            # read the positions only of the locations that hold enough lemmas.
            # The locations kept, their order and their contents are those the
            # single pass below gives.
            pending = {}
            for lemma, filename, ref, positions_json in cursor.fetchall():
                entry = pending.get((filename, ref))
                if entry is None:
                    entry = pending[(filename, ref)] = ({}, set())
                for canonical in lemma_mapping.get(lemma, [lemma]):
                    entry[0][canonical] = positions_json
                    entry[1].add(canonical)
            for key, (raw_positions, canonicals) in pending.items():
                if len(canonicals) < min_matches:
                    continue
                results[key] = {'lemmas': canonicals,
                                'positions': {c: _scan_json(raw) for c, raw in raw_positions.items()}}
        elif own_connection:
            # A plain listing on the index's own connection: positions are kept
            # as their JSON text and read when something asks for them.
            cursor.row_factory = None
            for lemma, filename, ref, positions_json in cursor.fetchall():
                key = (filename, ref)
                entry = results.get(key)
                if entry is None:
                    entry = results[key] = {'lemmas': set(), 'raw': {}}
                for canonical in lemma_mapping.get(lemma, [lemma]):
                    entry['lemmas'].add(canonical)
                    entry['raw'][canonical] = positions_json
            for entry in results.values():
                entry['positions'] = _LazyPositions(entry.pop('raw'))
        else:
            for row in cursor.fetchall():
                lemma, filename, ref, positions_json = row
                key = (filename, ref)
                if key not in results:
                    results[key] = {'lemmas': set(), 'positions': {}}
                positions = _scan_json(positions_json)
                for canonical in lemma_mapping.get(lemma, [lemma]):
                    results[key]['lemmas'].add(canonical)
                    results[key]['positions'][canonical] = positions
    except Exception as e:
        logger.error(f"Index lookup error: {e}")
    
    return results

def find_co_occurring_lemmas(lemmas, language, min_matches=2, max_distance=None, fallback_forms=None, conn=None):
    """
    Find all text locations where at least min_matches of the given lemmas co-occur.

    Args:
        lemmas: List of query lemmas
        language: 'la', 'grc', or 'en'
        min_matches: Minimum number of lemmas that must appear together
        max_distance: Maximum token distance between any matching lemmas (None = no limit)
        fallback_forms: Optional dict mapping lemma -> set of inflected forms to also
                       search for. Matches on fallback forms count as matches for the
                       canonical lemma.
        conn: Optional sqlite3 connection, passed straight through to lookup_lemmas
                       (see its own docstring) — every existing caller leaves this None.

    Returns:
        List of (filename, ref, matching_lemmas, positions_dict) tuples
    """
    all_matches = lookup_lemmas(lemmas, language, fallback_forms=fallback_forms, conn=conn, min_matches=min_matches)
    
    results = []
    for (filename, ref), data in all_matches.items():
        matching_lemmas = data['lemmas']
        if len(matching_lemmas) >= min_matches:
            if max_distance is not None:
                positions = data['positions']
                all_positions = []
                for lemma in matching_lemmas:
                    if lemma in positions:
                        all_positions.extend(positions[lemma])
                if len(all_positions) >= 2:
                    all_positions.sort()
                    min_span = all_positions[-1] - all_positions[0]
                    if min_span > max_distance:
                        continue
            results.append((filename, ref, matching_lemmas, data['positions']))
    
    return results

def get_text_metadata(language):
    """Get list of all indexed texts with metadata"""
    conn = get_connection(language)
    if not conn:
        return []
    
    cursor = conn.cursor()
    cursor.execute('SELECT filename, author, title, line_count FROM texts')
    return [dict(row) for row in cursor.fetchall()]

def get_index_stats(language):
    """Get statistics about the index"""
    conn = get_connection(language)
    if not conn:
        return None
    
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM texts')
    texts = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(DISTINCT lemma) FROM postings')
    lemmas = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM postings')
    postings = cursor.fetchone()[0]
    
    # Check if lines table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lines'")
    has_lines = cursor.fetchone() is not None
    lines_count = 0
    if has_lines:
        cursor.execute('SELECT COUNT(*) FROM lines')
        lines_count = cursor.fetchone()[0]
    
    db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
    size_mb = os.path.getsize(db_path) / (1024 * 1024)
    
    return {
        'texts': texts,
        'unique_lemmas': lemmas,
        'total_postings': postings,
        'lines_cached': lines_count,
        'has_lines_table': has_lines,
        'size_mb': round(size_mb, 1)
    }

def ensure_lines_table(language):
    """Create lines table if it doesn't exist"""
    conn = get_connection(language)
    if not conn:
        return False
    
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lines (
            text_id INTEGER,
            ref TEXT,
            content TEXT,
            lemmas TEXT,
            tokens TEXT,
            PRIMARY KEY (text_id, ref),
            FOREIGN KEY (text_id) REFERENCES texts(text_id)
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_lines_text_ref ON lines(text_id, ref)')
    conn.commit()
    return True

def get_line_data(filename, ref, language):
    """Get line content and lemmas directly from index"""
    conn = get_connection(language)
    if not conn:
        return None
    
    cursor = conn.cursor()
    cursor.execute('''
        SELECT l.content, l.lemmas, l.tokens
        FROM lines l
        JOIN texts t ON l.text_id = t.text_id
        WHERE t.filename = ? AND l.ref = ?
    ''', (filename, ref))
    
    row = cursor.fetchone()
    if row:
        return {
            'text': row[0],
            'lemmas': json.loads(row[1]) if row[1] else [],
            'tokens': json.loads(row[2]) if row[2] else []
        }
    return None

def get_lines_batch(filename, refs, language, conn=None):
    """Get multiple lines at once for efficiency.

    conn: Optional sqlite3 connection override — see lookup_lemmas' docstring
    for why (backend/documents.py reuse); every existing caller leaves it None.
    """
    if conn is None:
        conn = get_connection(language)
    if not conn:
        return {}
    
    cursor = conn.cursor()
    placeholders = ','.join(['?' for _ in refs])
    cursor.execute(f'''
        SELECT l.ref, l.content, l.lemmas, l.tokens
        FROM lines l
        JOIN texts t ON l.text_id = t.text_id
        WHERE t.filename = ? AND l.ref IN ({placeholders})
    ''', [filename] + list(refs))  # nosec B608
    
    results = {}
    for row in cursor.fetchall():
        results[row[0]] = {
            'text': row[1],
            'lemmas': _scan_json(row[2]) if row[2] else [],
            'tokens': _scan_json(row[3]) if row[3] else []
        }
    return results

def has_lines_data(language, conn=None):
    """Check if lines table exists and has data.

    conn: Optional sqlite3 connection override — see lookup_lemmas' docstring
    for why (backend/documents.py reuse); every existing caller leaves it None.
    """
    if conn is None:
        conn = get_connection(language)
    if not conn:
        return False
    
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lines'")
    if not cursor.fetchone():
        return False
    
    cursor.execute('SELECT COUNT(*) FROM lines LIMIT 1')
    return cursor.fetchone()[0] > 0

def index_single_text(filepath, language, text_processor):
    """
    Index a single text file and add it to the inverted index.
    Called when a new text is added to the corpus.
    
    Args:
        filepath: Full path to the .tess file
        language: 'la', 'grc', or 'en'
        text_processor: TextProcessor instance
    
    Returns:
        dict with indexing results or None on error
    """
    if not fspaths.exists(filepath):
        return {'error': 'File not found'}
    
    filename = os.path.basename(filepath)
    db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
    
    if not os.path.exists(db_path):
        return {'error': 'Index not initialized for this language'}
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT text_id FROM texts WHERE filename = ?', (filename,))
        if cursor.fetchone():
            conn.close()
            return {'status': 'already_indexed', 'filename': filename}
        
        units = text_processor.process_file(filepath, language, unit_type='line')
        
        parts = filename.replace('.tess', '').split('.')
        author = parts[0] if parts else ''
        title = '.'.join(parts[1:]) if len(parts) > 1 else ''
        
        cursor.execute(
            'INSERT INTO texts (filename, author, title, line_count) VALUES (?, ?, ?, ?)',
            (filename, author, title, len(units))
        )
        text_id = cursor.lastrowid
        
        postings_count = 0
        for unit in units:
            ref = unit.get('ref', '')
            lemmas = unit.get('lemmas', [])
            tokens = unit.get('tokens', [])
            text_content = unit.get('text', '')
            
            lemma_positions = {}
            for i, lemma in enumerate(lemmas):
                if lemma not in lemma_positions:
                    lemma_positions[lemma] = []
                lemma_positions[lemma].append(i)
            
            for lemma, positions in lemma_positions.items():
                cursor.execute(
                    'INSERT INTO postings (lemma, text_id, ref, positions) VALUES (?, ?, ?, ?)',
                    (lemma, text_id, ref, json.dumps(positions))
                )
                postings_count += 1
            
            cursor.execute(
                'INSERT OR IGNORE INTO lines (text_id, ref, content, lemmas, tokens) VALUES (?, ?, ?, ?, ?)',
                (text_id, ref, text_content, json.dumps(lemmas), json.dumps(tokens))
            )
        
        conn.commit()
        conn.close()
        
        if language in _connections:
            del _connections[language]
        
        return {
            'status': 'indexed',
            'filename': filename,
            'lines': len(units),
            'postings': postings_count
        }
        
    except Exception as e:
        return {'error': str(e)}

if __name__ == '__main__':
    for lang in ['la', 'grc']:
        if is_index_available(lang):
            stats = get_index_stats(lang)
            logger.info(f"{lang.upper()}: {stats}")
        else:
            logger.info(f"{lang.upper()}: No index available")
