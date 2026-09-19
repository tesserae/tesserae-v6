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
import re
import sqlite3
from collections import defaultdict
from functools import lru_cache

from backend.logging_config import get_logger
from backend.lemma_cache import get_cache_path
from backend.ngram_utils import gen_ngram_indices, gen_ngrams
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
    """Whether a reuse table exists for this language AND can actually be
    opened and read -- not just whether the file exists. A language the
    table has not been built for (or not yet, or never will) is a normal
    state, not an error -- callers should answer 404 with a plain message,
    not a 500 or a silently-empty 200. A CORRUPT file (present but not a
    valid SQLite database) gets the SAME 404 rather than a 200 with
    available:false: this routes through _get_connection, which validates
    a file before ever caching a connection to it (see its own docstring),
    so backend/blueprints/reuse.py's existing `if not is_available(...):
    return 404` gate -- unchanged -- already covers both cases with no
    blueprint code of its own."""
    return _get_connection(language) is not None


def _drop_connection(language):
    """Evict and close a cached connection, so the NEXT call re-attempts
    from scratch via _get_connection (which will not re-cache a still-bad
    file, but will pick up a since-fixed one). Used when a query against
    an already-cached connection turns out to fail with
    sqlite3.DatabaseError -- e.g. the file was replaced with garbage, or
    corrupted on disk, after this process already validated and cached
    it; without this the same broken connection would be reused and fail
    the same way on every subsequent request for the language."""
    conn = _connections.pop(language, None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass


def _get_connection(language):
    """A cached sqlite3 connection for `language`, or None if the db file
    is missing, or present but not actually openable/readable as SQLite.

    VALIDATES BEFORE CACHING. sqlite3.connect() on a garbage (non-SQLite)
    file succeeds -- SQLite defers file-format validation until the first
    real read, not connect time -- so a connection is never handed back
    (or cached in _connections) until a cheap query against it has
    actually succeeded. Without this, a corrupt db would connect
    successfully, get cached, and then fail on EVERY subsequent caller's
    first real query (meta/line/marks each running their own SELECT),
    every time, for the life of the process -- not just once at open.

    Only THIS MODULE ever touches this database, and only ever with
    SELECT (grep backend/reuse_table.py for '.execute(' -- there is no
    INSERT/UPDATE/DELETE/CREATE anywhere in it); the table is written
    exclusively by scripts/reuse/build_reuse_table.py, a separate offline
    process against a separate temp file swapped into place after the
    build finishes. So `sqlite3.DatabaseError` here always means "this
    file is not a valid database" (corrupt, truncated, or garbage), not a
    write conflict or a locked-by-another-writer condition."""
    if language in _connections:
        return _connections[language]
    path = _db_path(language)
    if not os.path.exists(path):
        return None
    conn = None
    try:
        conn = sqlite3.connect(path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("SELECT 1 FROM meta LIMIT 1")
    except sqlite3.DatabaseError as e:
        logger.error(f"Reuse table for '{language}' is not a valid database: {e}")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        return None
    except Exception as e:
        logger.error(f"Failed to open reuse table for '{language}': {e}")
        return None
    _connections[language] = conn
    return conn


def meta(language):
    """The build's meta key/value pairs (built_at, corpus_version, ...), or
    {} if the table is missing or has no meta table."""
    conn = _get_connection(language)
    if not conn:
        return {}
    try:
        rows = conn.execute("SELECT key, value FROM meta").fetchall()
        return {r['key']: r['value'] for r in rows}
    except sqlite3.DatabaseError as e:
        # A connection validated fine at open but has since gone bad (the
        # file was replaced or corrupted on disk) -- drop it so the NEXT
        # call re-opens from scratch instead of hitting the same broken
        # connection on every future request (see _drop_connection).
        logger.error(f"reuse_table.meta query failed for '{language}': {e}")
        _drop_connection(language)
        return {}
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
    """The lemma cache file for `work`: the CURRENT content-hashed name
    (<ascii_hint>-<md5(text_id)>.json) production's own lemma cache uses
    first -- computed with backend.lemma_cache.get_cache_path (the exact
    function that named the file), pointed at THIS module's own
    CACHE_LEMMAS_DIR rather than that module's CACHE_DIR, so a test that
    patches CACHE_LEMMAS_DIR still gets a self-contained fixture directory
    -- and only when that does not exist, the plain <work>.json legacy
    name (what the reuse-route test fixtures write, and what a handful of
    real caches predating the hashed scheme still use).

    HASHED FIRST, NOT PLAIN FIRST (changed 2026-09-19; see the module's
    git history for the version this replaced). Checking plain first
    missed every work whose cache has no legacy copy at all -- Geoffrey of
    Vinsauf's Documentum, whose Reuse tab entries carried a ref but no line
    text -- but plain-first has a second, worse failure mode when BOTH
    names exist for the same work: Tertullian's Ad Nationes has a stale
    plain-named cache from an old CTS-URN tagging scheme
    ("tertullian.ad_nationes_libri_duo urn:cts:latinLit:...2.17") sitting
    alongside a current, file-hash-matching, correctly-tagged hashed one
    ("tertullian.ad_nationes_libri_duo 2.17", the .tess file's own tag
    shape). Plain-first served the stale file, so a ref in the shape the
    reuse table (and the .tess file) actually uses was never in it -- ref
    shown, no text. This is not a tag-SHAPE problem to special-case (short
    abbreviation vs. full id vs. dot-glued forms all already round-trip
    correctly once the right cache file is read, since the build and this
    lookup both read a line's `ref` verbatim from whatever cache file
    backs `work`); it is a stale-file problem, fixed the same way
    backend.lemma_cache.get_cached_units already avoids it for every other
    caller -- hashed is the name a rebuild actually writes, so it is
    checked first, and a plain-named leftover only wins when hashed is
    altogether absent. Still no file_hash validation against a live .tess
    file (unlike get_cached_units): a reuse lookup only wants a line's
    text, and requiring a fresh match would also make it impossible to
    test with a fixture cache and no fixture corpus."""
    hashed = get_cache_path(work + '.tess', language, cache_dir=CACHE_LEMMAS_DIR)
    if os.path.exists(hashed):
        return hashed
    plain = os.path.join(CACHE_LEMMAS_DIR, language, work + '.json')
    if os.path.exists(plain):
        return plain
    return None


@lru_cache(maxsize=128)
def _load_work_lines(language, work):
    """{'ordered', 'text', 'seq', 'tokens', 'original_tokens'} for one
    work, built once from its lemma cache -- the same per-line source the
    table itself was built from, so a reuse-table ref always resolves to
    real line data. See _work_cache_path for how the file is found.

    'tokens' is the already-normalized surface form (lowercase, punctuation
    stripped, v->u, j->i for Latin -- see backend/text_processor.py
    tokenize_latin) the build script matched n-grams on; 'original_tokens'
    is the same length and order, case-preserved and still punctuation-free,
    for finding a token's position back in 'text' (see _bold_spans). Both
    are what bold_shared_words (line(), below) needs to reconstruct which
    words a quotation shares with the selected line -- reading them from
    here means that computation uses the EXACT tokens the build indexed,
    not a fresh re-tokenization that could drift from it.

    A locus label can repeat within a work (see the module docstring's
    duplicate-locus caveat); the per-ref maps keep the FIRST occurrence,
    same as the build script's own line-lookup convention. Memoized per
    (language, work) for the life of the process -- a lemma cache file
    does not change without a deploy, which restarts workers."""
    empty = {'ordered': [], 'text': {}, 'seq': {}, 'tokens': {}, 'original_tokens': {}}
    path = _work_cache_path(language, work)
    if path is None:
        return empty
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.warning(f"Could not read lemma cache for {language}/{work}: {e}")
        return empty
    ordered = []
    ref_to_text = {}
    ref_to_seq = {}
    ref_to_tokens = {}
    ref_to_original_tokens = {}
    for seq, unit in enumerate(data.get('units_line', [])):
        ref = unit.get('ref', '')
        ordered.append(ref)
        if ref and ref not in ref_to_text:
            ref_to_text[ref] = unit.get('text', '')
            ref_to_seq[ref] = seq
            ref_to_tokens[ref] = unit.get('tokens') or []
            ref_to_original_tokens[ref] = unit.get('original_tokens') or []
    return {
        'ordered': ordered, 'text': ref_to_text, 'seq': ref_to_seq,
        'tokens': ref_to_tokens, 'original_tokens': ref_to_original_tokens,
    }


def _line_text(language, work, ref):
    return _load_work_lines(language, work)['text'].get(ref, '')


def _line_tokens(language, work, ref):
    """(tokens, original_tokens) for one line -- see _load_work_lines. A
    missing or misaligned original_tokens array falls back to the
    normalized tokens themselves, same fallback build_reuse_table.py's
    _line_lemmas uses for the same reason (an older cache predating the
    field, or one that failed to populate it)."""
    data = _load_work_lines(language, work)
    tokens = data['tokens'].get(ref) or []
    original = data['original_tokens'].get(ref) or []
    if len(original) != len(tokens):
        original = tokens
    return tokens, original


def _shared_word_mask(source_tokens, quote_tokens):
    """Boolean mask over quote_tokens: True for a position belonging to at
    least one word-triple -- contiguous or one-gap skip, EXACTLY as
    scripts/reuse/build_reuse_table.py's find_pairs defines them
    (backend/ngram_utils.gen_ngrams, imported by both) -- shared with
    source_tokens. This is what the pairs table itself was built to
    detect, reconstructed at read time rather than stored, so bolding a
    quotation costs nothing when the table is built and never drifts from
    what the build actually matched on.

    FALLS BACK to a plain shared-TOKEN mask (no triple structure) when no
    triple reconstructs. Two cases: a quoting line under three tokens can
    never form a triple at all, and a possible-echo pair (see line()'s
    tier docstring) can have as few as ONE shared token once its match is
    embedded in an otherwise unrelated sentence -- exactly the shape the
    rare-single-ngram rule exists for, so bolding just that shared word
    still shows a reader what earned the match, rather than bolding
    nothing at all."""
    n = len(quote_tokens)
    mask = [False] * n
    if len(source_tokens) >= 3 and n >= 3:
        source_ngrams = set(gen_ngrams(source_tokens))
        matched = False
        for idxs in gen_ngram_indices(n):
            if tuple(quote_tokens[i] for i in idxs) in source_ngrams:
                matched = True
                for i in idxs:
                    mask[i] = True
        if matched:
            return mask
    source_set = set(source_tokens)
    for i, t in enumerate(quote_tokens):
        if t and t in source_set:
            mask[i] = True
    return mask


def _bold_spans(text, original_tokens, mask):
    """[start, end) character spans in `text` for the tokens where mask[i]
    is True, for the client to wrap in <b>. Found by scanning
    original_tokens (case-preserved, already punctuation-free -- see
    _load_work_lines) against `text` left to right, matched as WHOLE
    WORDS (\\b...\\b), not substrings: a first version used text.find,
    which happily matches "cano" inside "canorum" or "arma" inside
    "armatum" and would bold a fragment of an unrelated word that merely
    contains a shared token's letters. \\b in Python's re is Unicode-aware
    or a str pattern (the default, no flag needed), so this holds for
    accented Latin and Greek text the same as plain ASCII.

    A token the word-boundary regex cannot locate at or after the previous
    token's end (a rare cache/text mismatch) is skipped rather than
    raising or aborting, so one bad token does not blank bolding for the
    whole line; a case-insensitive retry covers the ordinary reason a
    plain match fails, a casing difference between the cache and a
    since-corrected text file."""
    spans = []
    pos = 0
    for i, tok in enumerate(original_tokens):
        if not tok:
            continue
        pattern = r'\b' + re.escape(tok) + r'\b'
        m = re.compile(pattern).search(text, pos)
        if m is None:
            m = re.compile(pattern, re.IGNORECASE).search(text, pos)
        if m is None:
            continue
        if i < len(mask) and mask[i]:
            spans.append([m.start(), m.end()])
        pos = m.end()
    return spans


def line(language, work, ref):
    """Other works' lines that repeat this line (from `pairs`, both
    directions), each carrying what the Reader needs to open it there.

    Returns {'available': False} if no table exists for the language, else
    {'available': True, 'quotations': [...], 'meta': {...}} where each
    quotation is {work, ref, language, text, bold_spans, shared, jaccard,
    span_len, tier}, ordered by shared descending.

    BOLD_SPANS (2026-09-19): [[start, end], ...] character ranges in
    `text` -- the quoting line's own words that belong to a word-triple
    (or, failing that, a plain shared token; see _shared_word_mask) it
    shares with the SELECTED line (`ref` on `work`, the argument to this
    call). Computed fresh on every request rather than stored: it depends
    on which line the reader has selected, not on the pair alone, and
    computing it is cheap (a handful of short token lists, not a corpus
    scan). The selected line's own locus/ref label is unaffected either
    way -- only a quotation's TEXT gets bold_spans, never its `ref`.

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
    except sqlite3.DatabaseError as e:
        logger.error(f"reuse_table.line query failed for {language}/{work}/{ref}: {e}")
        _drop_connection(language)
        return {'available': False, 'quotations': []}
    except Exception as e:
        logger.error(f"reuse_table.line query failed for {language}/{work}/{ref}: {e}")
        return {'available': False, 'quotations': []}

    source_tokens, _ = _line_tokens(language, work, ref)
    quotations = []
    for r in rows:
        other_work, other_ref = r['other_work'], r['other_ref']
        text = _line_text(language, other_work, other_ref)
        quote_tokens, quote_original_tokens = _line_tokens(language, other_work, other_ref)
        mask = _shared_word_mask(source_tokens, quote_tokens)
        quotations.append({
            'work': other_work,
            'ref': other_ref,
            'language': language,
            'text': text,
            'bold_spans': _bold_spans(text, quote_original_tokens, mask),
            'shared': r['shared'],
            'jaccard': r['jaccard'],
            'span_len': r['span_len'],
            'year': _author_year(language, other_work),
            'tier': 'possible' if r['shared'] == 1 else 'strict',
        })
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
    except sqlite3.DatabaseError as e:
        logger.error(f"reuse_table.marks query failed for {language}/{work}: {e}")
        _drop_connection(language)
        return {'available': False, 'lines': []}
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
        ref_to_seq = _load_work_lines(language, work)['seq']
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
