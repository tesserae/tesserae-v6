"""
Tesserae V6 - Reuse Table

Query layer for the corpus-wide verbatim/near-verbatim line reuse table,
cache/reuse_pairs/<lang>.db, built by scripts/reuse/build_reuse_table.py.
See that script's module docstring and research/reuse_table/REPORT_2026-09-18.md
for what the table measures (shared word-triples above a Jaccard/containment
threshold) and its known limitations (a locus label is occasionally not
unique within a work; corpus-hygiene duplicate files still surface as
"reuse" until they are retired -- see the report's "Top 20 work pairs").

Backs GET /api/reuse/line and GET /api/reuse/marks (backend/blueprints/reuse.py).
Latin only as of 2026-09-19; other languages answer is_available() = False
until their table is built.

Table schema (written by the build script):
    pairs(work_a, line_a_ref, work_b, line_b_ref, shared, jaccard, span_len)
    line_counts(work, line_ref, n_works)
    meta(key, value)  -- built_at, corpus_version, corpus_file_count, ...
"""
import json
import os
import sqlite3
from collections import defaultdict
from functools import lru_cache

from backend.logging_config import get_logger
from backend.lemma_cache import get_cache_path
from backend.passage_index import _norm_work
from backend.utils import normalize_author_date_key

logger = get_logger('reuse_table')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_DIR = os.path.join(BASE_DIR, 'cache', 'reuse_pairs')
CACHE_LEMMAS_DIR = os.path.join(BASE_DIR, 'cache', 'lemmas')
AUTHOR_DATES_PATH = os.path.join(BASE_DIR, 'backend', 'author_dates.json')

_connections = {}
_author_dates = None


def _load_author_dates():
    global _author_dates
    if _author_dates is None:
        try:
            with open(AUTHOR_DATES_PATH, 'r', encoding='utf-8') as f:
                _author_dates = json.load(f)
        except Exception:
            _author_dates = {}
    return _author_dates


def _author_year(language, work):
    """Author's year for a work, for newest-first ordering in the Reader's
    Reuse tab, or None when the author is not in author_dates.json."""
    dates = _load_author_dates().get(language, {})
    author_key = (work or '').split('.')[0]
    info = (dates.get(author_key) or dates.get(author_key.lower())
            or dates.get(normalize_author_date_key(author_key)) or {})
    return info.get('year')


def _db_path(language):
    return os.path.join(DB_DIR, f'{language}.db')


def is_available(language):
    """Whether a reuse table exists for this language. A language the table
    has not been built for (or not yet, or never will) is a normal state,
    not an error -- callers should answer 404 with a plain message, not a
    500 or a silently-empty 200."""
    return os.path.exists(_db_path(language))


def _get_connection(language):
    if language in _connections:
        return _connections[language]
    path = _db_path(language)
    if not os.path.exists(path):
        return None
    try:
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _connections[language] = conn
        return conn
    except Exception as e:
        logger.error(f"Failed to open reuse table for '{language}': {e}")
        return None


def meta(language):
    """The build's meta key/value pairs (built_at, corpus_version, ...), or
    {} if the table is missing or has no meta table."""
    conn = _get_connection(language)
    if not conn:
        return {}
    try:
        rows = conn.execute("SELECT key, value FROM meta").fetchall()
        return {r['key']: r['value'] for r in rows}
    except Exception:
        return {}


def _work_has_rows(language, work):
    """Whether `work` (an already-stripped id, exact match) is a key the
    table actually has rows for. Cheap indexed lookup (line_counts.work is
    indexed) used only to disambiguate in _resolve_work."""
    conn = _get_connection(language)
    if not conn:
        return False
    try:
        return conn.execute(
            "SELECT 1 FROM line_counts WHERE work = ? LIMIT 1", (work,)
        ).fetchone() is not None
    except Exception:
        return False


def _resolve_work(language, work):
    """Map a Reader work id to the id build_reuse_table.py actually keyed
    the table on.

    The Reader sends the work it has open, which for a multi-part text is
    a part-file id (vergil.aeneid.part.7.tess) -- the Reader's own default
    and normal navigation unit. discover_corpus() in
    scripts/reuse/build_reuse_table.py collapses a .part.N file into its
    base id whenever a base (whole-text) file exists for that work, which
    covers nearly every multi-part work, so vergil.aeneid.part.7 must
    resolve to vergil.aeneid to find anything -- passing the part id
    through unchanged is what made GET /api/reuse/marks answer
    `lines: []` for a part-file work while the base id for the same
    range answered correctly.

    A handful of works ship as parts only, with no base file at all (e.g.
    paschasius_radbertus.epitaphium_arsenii) -- discover_corpus() never
    drops those, so the table keys them on their own full part id. Try
    the part-collapsed id first (the common case); if it has no rows in
    the table but the raw (stripped-of-.tess-only) id does, use the raw
    id instead, so those works keep working too."""
    w = (work or '')
    if '/' in w:
        w = w.rsplit('/', 1)[-1]
    if w.endswith('.tess'):
        w = w[:-5]
    raw = w
    collapsed = _norm_work(raw)
    if collapsed == raw:
        return raw
    if _work_has_rows(language, collapsed):
        return collapsed
    if _work_has_rows(language, raw):
        return raw
    return collapsed


def _work_cache_path(language, work):
    """The lemma cache file for `work`: the plain <work>.json name if that
    exists (the legacy naming, and what the reuse-route test fixtures
    write), else the current content-hashed name
    (<ascii_hint>-<md5(text_id)>.json) production's own lemma cache uses --
    computed with backend.lemma_cache.get_cache_path (the exact function
    that named the file), pointed at THIS module's own CACHE_LEMMAS_DIR
    rather than that module's CACHE_DIR, so a test that patches
    CACHE_LEMMAS_DIR still gets a self-contained fixture directory.

    Reading only the plain name here used to miss every work whose cache
    has no legacy copy -- Geoffrey of Vinsauf's Documentum among them,
    present only under its hashed name, so its Reuse tab entries carried a
    ref but no line text (2026-09-19). This does not validate the cache
    against a live .tess file's hash (unlike get_cached_units): a reuse
    lookup only wants a line's text, and requiring a fresh match would also
    make it impossible to test with a fixture cache and no fixture corpus."""
    plain = os.path.join(CACHE_LEMMAS_DIR, language, work + '.json')
    if os.path.exists(plain):
        return plain
    hashed = get_cache_path(work + '.tess', language, cache_dir=CACHE_LEMMAS_DIR)
    if os.path.exists(hashed):
        return hashed
    return None


@lru_cache(maxsize=128)
def _load_work_lines(language, work):
    """(ordered_refs, ref_to_text, ref_to_seq) for one work, built once from
    its lemma cache -- the same per-line source the table itself was built
    from, so a reuse-table ref always resolves to real line text. See
    _work_cache_path for how the file is found.

    A locus label can repeat within a work (see the module docstring's
    duplicate-locus caveat); ref_to_text/ref_to_seq keep the FIRST
    occurrence, same as the build script's own line-lookup convention.
    Memoized per (language, work) for the life of the process -- a lemma
    cache file does not change without a deploy, which restarts workers."""
    path = _work_cache_path(language, work)
    if path is None:
        return ([], {}, {})
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read lemma cache for {language}/{work}: {e}")
        return ([], {}, {})
    ordered = []
    ref_to_text = {}
    ref_to_seq = {}
    for seq, unit in enumerate(data.get('units_line', [])):
        ref = unit.get('ref', '')
        ordered.append(ref)
        if ref and ref not in ref_to_text:
            ref_to_text[ref] = unit.get('text', '')
            ref_to_seq[ref] = seq
    return (ordered, ref_to_text, ref_to_seq)


def _line_text(language, work, ref):
    _, ref_to_text, _ = _load_work_lines(language, work)
    return ref_to_text.get(ref, '')


def line(language, work, ref):
    """Other works' lines that repeat this line (from `pairs`, both
    directions), each carrying what the Reader needs to open it there.

    Returns {'available': False} if no table exists for the language, else
    {'available': True, 'quotations': [...], 'meta': {...}} where each
    quotation is {work, ref, language, text, shared, jaccard, span_len,
    tier}, ordered by shared descending.

    TIERED (2026-09-19): `tier` is 'strict' for a pair kept by the jaccard
    rule or the containment override (both require shared>=2 --
    scripts/reuse/build_reuse_table.py's find_pairs) and 'possible' for one
    kept only by the rare-single-ngram rule, which requires shared==1
    exactly. Since shared==1 is never reachable through the other two
    rules, the tier is fully determined by `shared` already in this row --
    no rebuild or schema change needed to add it. NC, after reviewing a
    30-pair sample of the rare-single rule's yield: "a quarter genuine is
    too noisy for the Reader mark" -- the Reuse tab lists strict pairs
    first with no heading (unchanged from before tiering) and possible
    pairs in a separate, collapsed "Possible echoes" section."""
    if not is_available(language):
        return {'available': False, 'quotations': []}
    conn = _get_connection(language)
    if not conn:
        return {'available': False, 'quotations': []}
    work = _resolve_work(language, work)
    try:
        rows = conn.execute(
            """SELECT work_b AS other_work, line_b_ref AS other_ref, shared, jaccard, span_len
                 FROM pairs WHERE work_a = ? AND line_a_ref = ?
               UNION ALL
               SELECT work_a AS other_work, line_a_ref AS other_ref, shared, jaccard, span_len
                 FROM pairs WHERE work_b = ? AND line_b_ref = ?
               ORDER BY shared DESC""",
            (work, ref, work, ref)
        ).fetchall()
    except Exception as e:
        logger.error(f"reuse_table.line query failed for {language}/{work}/{ref}: {e}")
        return {'available': False, 'quotations': []}

    quotations = [{
        'work': r['other_work'],
        'ref': r['other_ref'],
        'language': language,
        'text': _line_text(language, r['other_work'], r['other_ref']),
        'shared': r['shared'],
        'jaccard': r['jaccard'],
        'span_len': r['span_len'],
        'year': _author_year(language, r['other_work']),
        'tier': 'possible' if r['shared'] == 1 else 'strict',
    } for r in rows]
    return {'available': True, 'quotations': quotations, 'meta': meta(language)}


def marks(language, work, ref_start=None, ref_end=None):
    """Per-line count of other works repeating each line, for the Reader's
    margin marker -- split into two tiers (2026-09-19; see line()'s
    docstring for the tier rule and why no rebuild was needed): `n_works`
    counts only STRICT pairs (shared>=2, the original jaccard/containment
    rules) and `n_possible_works` counts only POSSIBLE pairs (shared==1,
    the rare-single-ngram rule). The Reader shows the solid "quoted in N
    works" mark when n_works>0, and only when it is 0 falls back to a
    lighter outline mark reading "possible echo in N works" -- a line
    never shows both.

    Computed directly from `pairs` (indexed on work_a/work_b) rather than
    the precomputed `line_counts` table, which only ever held one combined
    count and would need a rebuild to carry the split; `pairs` already has
    everything (shared, and both directions) needed to compute both tiers
    live, at the cost of aggregating this work's own rows on every call
    instead of one indexed lookup -- still a small, indexed slice of the
    table per work, not a full scan.

    ref_start/ref_end (either or both optional) restrict the range using the
    work's own line ORDER (seq_in_work, from the lemma cache), not a string
    comparison of ref labels, since a citation label like "verg. aen. 1.9"
    does not sort correctly as a string against "verg. aen. 1.10". Omitting
    both returns every reused line in the work.

    `work` is resolved the same way `line()` resolves it (see
    _resolve_work): the Reader sends whatever part-file id it has open,
    but the table is keyed on the collapsed base id for nearly every
    work, so vergil.aeneid.part.7 must resolve to vergil.aeneid before
    querying `pairs` -- otherwise this always answers `lines: []` for a
    part-file work even when the base id has marks."""
    if not is_available(language):
        return {'available': False, 'lines': []}
    conn = _get_connection(language)
    if not conn:
        return {'available': False, 'lines': []}
    work = _resolve_work(language, work)
    try:
        rows = conn.execute(
            """SELECT line_a_ref AS ref, work_b AS other, shared FROM pairs WHERE work_a = ?
               UNION ALL
               SELECT line_b_ref AS ref, work_a AS other, shared FROM pairs WHERE work_b = ?""",
            (work, work)
        ).fetchall()
    except Exception as e:
        logger.error(f"reuse_table.marks query failed for {language}/{work}: {e}")
        return {'available': False, 'lines': []}

    if not rows:
        return {'available': True, 'lines': []}

    strict_others = defaultdict(set)
    possible_others = defaultdict(set)
    for r in rows:
        bucket = possible_others if r['shared'] == 1 else strict_others
        bucket[r['ref']].add(r['other'])

    seq_start = seq_end = None
    ref_to_seq = {}
    if ref_start or ref_end:
        _, _, ref_to_seq = _load_work_lines(language, work)
        if ref_start:
            seq_start = ref_to_seq.get(ref_start)
        if ref_end:
            seq_end = ref_to_seq.get(ref_end)

    out = []
    for ref in set(strict_others) | set(possible_others):
        if seq_start is not None or seq_end is not None:
            seq = ref_to_seq.get(ref)
            if seq is None:
                continue
            if seq_start is not None and seq < seq_start:
                continue
            if seq_end is not None and seq > seq_end:
                continue
        out.append({
            'ref': ref,
            'n_works': len(strict_others.get(ref, ())),
            'n_possible_works': len(possible_others.get(ref, ())),
        })
    return {'available': True, 'lines': out}
