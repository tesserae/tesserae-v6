"""Reader for the corpus connections map cache built by
scripts/build_connections_map.py.

The cache is a SQLite file at cache/connections_map/<index_fingerprint>.db,
keyed by the SAME fingerprint backend.passage_index.index_fingerprint() uses
for its own caches, so a rebuilt passage index invalidates this one exactly
the way it invalidates the density cache. Every function here is read-only
and answers "unavailable" rather than raising when the cache has not been
built yet (see is_available()) -- this is a picture of Theme Search's own
connections, not a live computation, and it fails the same honest way the
rest of the passage-index code does when its data is missing.

Views ("author", "work", "century", "genre") are all derived, AT REQUEST
TIME, from the work_pairs and works tables rather than from the precomputed
author_pairs/century_pairs/genre_pairs tables the build also writes. That
keeps `languages` and `translations` filtering uniform across every view
(work_pairs already carries both languages and both translation flags per
pair, so filtering there is a single pass over a few tens of thousands of
rows) without needing four separately-filtered code paths. The precomputed
tables stay in the cache as the build's own record of its unfiltered
totals -- meta.author_pairs etc. cite their row counts -- but are not read
by these functions.
"""
import bisect
import math
import glob
import json
import os
import re
import sqlite3

from backend.logging_config import get_logger
from backend.passage_index import index_fingerprint
from backend.utils import format_display_name

logger = get_logger('connections_map')

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE_DIR = os.path.join(_ROOT, 'cache', 'connections_map')
_IDS_PATH = os.path.join(_ROOT, 'data', 'passage_index', 'ids.json')
_TRANSLATION_PAIRS_PATH = os.path.join(_ROOT, 'data', 'translation_pairs.json')

VIEWS = ('work', 'author', 'century', 'genre')
DEFAULT_TOP = 60
MAX_TOP = 200
DEFAULT_PAIR_LIMIT = 25
MAX_PAIR_LIMIT = 100


def _db_path():
    return os.path.join(_CACHE_DIR, f'{index_fingerprint()}.db')


def _cache_dir():
    return _CACHE_DIR


# Staleness fallback (NC, 2026-09-19): a small corpus edit (even a two-window
# retirement) changes index_fingerprint(), and a full rebuild runs 35-45
# minutes (scripts/build_connections_map.py's own estimate). Refusing to
# answer until that rebuild finishes made the map unusable after any edit at
# all. Instead, when no cache matches the CURRENT fingerprint exactly, the
# most recently built cache present is served instead, marked `stale` in
# every response it appears in, rather than a flat "not built" error.
def _meta_from_conn(conn):
    """The meta table of an already-open connection, as a plain dict."""
    out = {}
    for key, value in conn.execute('SELECT key, value FROM meta').fetchall():
        try:
            out[key] = json.loads(value)
        except (TypeError, ValueError):
            out[key] = value
    return out


def _cache_meta(path):
    """The meta table of one cache file, as a plain dict, or {} if it can't
    be read (a half-written .tmp file, a corrupt db, etc -- staleness
    fallback must never raise on a file that happens to be there)."""
    try:
        conn = sqlite3.connect(path)
        try:
            return _meta_from_conn(conn)
        finally:
            conn.close()
    except sqlite3.Error:
        return {}


def _latest_cache_file():
    """The path of the most recently BUILT cache present (by its own meta
    built_at, an ISO-ish string that sorts chronologically), or None if the
    cache directory holds nothing readable. Not file mtime: a copy or rsync
    of an old cache changes mtime without rebuilding anything."""
    best_path, best_built_at = None, None
    try:
        candidates = sorted(glob.glob(os.path.join(_cache_dir(), '*.db')))
    except OSError:
        candidates = []
    for path in candidates:
        built_at = _cache_meta(path).get('built_at')
        if not built_at:
            continue
        if best_built_at is None or built_at > best_built_at:
            best_path, best_built_at = path, built_at
    return best_path


_current_ids_cache = None


def _current_ids():
    """The passage index's own current window ids, loaded once per process
    (NC, 2026-09-19) -- reused both to filter drill-down edges against
    windows the corpus no longer has (get_pair, get_books_map) and to report
    the current window count next to a stale cache's own count. Loaded once,
    not re-checked against the file's mtime: a long-running worker is meant
    to pick this up on its next restart, the same way it picks up any other
    change to data/passage_index/."""
    global _current_ids_cache
    if _current_ids_cache is None:
        try:
            with open(_IDS_PATH, encoding='utf-8') as fh:
                _current_ids_cache = set(json.load(fh))
        except (OSError, ValueError):
            logger.warning('[connections_map] could not read %s for the '
                           'stale-cache window count / edge filter', _IDS_PATH)
            _current_ids_cache = set()
    return _current_ids_cache


_curated_pairs_cache = None


def _curated_pairs():
    """The curated translation-pair set (data/translation_pairs.json),
    loaded once per process and checked LIVE against every work_pairs row --
    not only the is_translation_curated column a cache baked in at build
    time. NC, 2026-09-19: the curated list itself was missing most scripture
    book pairs (the World English Bible's coarse Pentateuch/Prophets/
    Writings groupings against most of the Hebrew Bible and Septuagint, and
    the Bohairic against the same), so those cells stayed dark with
    translations hidden; regenerating the JSON alone would do nothing until
    the next ~40-minute rebuild re-baked work_pairs from it. This overlay
    makes a curated-list fix effective immediately, the same reasoning as
    the staleness fallback not waiting on a rebuild for a fingerprint
    change."""
    global _curated_pairs_cache
    if _curated_pairs_cache is None:
        try:
            with open(_TRANSLATION_PAIRS_PATH, encoding='utf-8') as fh:
                data = json.load(fh)
            _curated_pairs_cache = {tuple(sorted((p['work_a'], p['work_b'])))
                                    for p in data.get('pairs', [])}
        except (OSError, ValueError, KeyError, TypeError):
            logger.warning('[connections_map] could not read %s for the live '
                           'curated-pairs overlay', _TRANSLATION_PAIRS_PATH)
            _curated_pairs_cache = set()
    return _curated_pairs_cache


def _is_translation_pair(row):
    """Whether a work_pairs row is a translation pair: the cache's own
    baked-in curated or heuristic flag, OR a live check against the current
    data/translation_pairs.json (see _curated_pairs)."""
    if row['is_translation_curated'] or row['is_translation_heuristic']:
        return True
    return tuple(sorted((row['work_a'], row['work_b']))) in _curated_pairs()


def _resolve_path():
    """(path, is_stale) -- which db a request should read. is_stale is False
    on an exact fingerprint match, True when falling back to the most
    recently built cache present. path is None only when there is no cache
    at all, anywhere, to fall back to (a fresh checkout that has never run
    the build)."""
    exact = _db_path()
    if os.path.exists(exact):
        return exact, False
    latest = _latest_cache_file()
    return (latest, True) if latest else (None, False)


def is_available():
    path, _is_stale = _resolve_path()
    return path is not None


def _stale_info(conn, meta):
    """The staleness notice for a fallback cache already open as `conn`.

    NC, 2026-09-19 (correction to the first version of this, which compared
    the cache's own five-language fine-scale subset count against the WHOLE
    current index -- every language, both scales -- and so could report a
    six-figure "window_diff" for a two-window edit): `current_window_count`
    is now counted over exactly the same population `cache_window_count`
    covers, filtering the current ids.json (already loaded once, see
    _current_ids()) down to fine-scale ids whose work belongs to THIS
    cache's own works table -- no rebuild, no descriptions.jsonl scan, just
    the id set plus one more table already in the connection. window_diff is
    therefore a true before/after of the same population, not an estimate.
    """
    cache_works = {r[0] for r in conn.execute('SELECT work FROM works')}
    current_n = 0
    for window_id in _current_ids():
        parts = window_id.split(':')
        if len(parts) < 2 or parts[1] != 'fine':
            continue
        work = parts[0].split('.part.')[0]   # norm_work(), matching the works table's own ids
        if work in cache_works:
            current_n += 1
    cache_n = meta.get('subset_windows')
    return {
        'cache_built_at': meta.get('built_at'),
        'cache_window_count': cache_n,
        'current_window_count': current_n,
        'window_diff': abs(current_n - cache_n) if isinstance(cache_n, int) else None,
    }


def _connect_for_request():
    """(conn, stale) for the current request -- see _resolve_path(). conn is
    None (with stale None too) only when nothing is available at all,
    matching is_available()'s own check."""
    path, is_stale = _resolve_path()
    if path is None:
        return None, None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    stale = _stale_info(conn, _meta_from_conn(conn)) if is_stale else None
    return conn, stale


def _unavailable():
    return {'error': 'the connections map has not been built for this index '
                     '(cache/connections_map/ has no db for the current '
                     'passage index fingerprint, and no earlier cache is '
                     'present to fall back to)'}


def _with_stale(result, stale):
    """Attach the staleness notice to a result dict, when there is one."""
    if stale:
        result['stale'] = stale
    return result


_TRAILING_LOCUS = re.compile(r'(\d+(?:\.\d+)*)\s*$')


def _book_of(ref_start):
    """The "book" a ref belongs to, for the third (books x books) drill-down
    level (NC, 2026-09-19): the first level of a window's ref_start, e.g.
    "hom. il. 4.446" -> book "4". A ref carrying only one numeric level (a
    bare line number, no book/chapter prefix) is split instead into blocks of
    100 lines labelled by the block's own first line.

    Returns (book_id, book_label) -- book_id is a stable grouping key
    ("b4" or "block101"), book_label is what a reader sees ("4" or "101") --
    or (None, None) when ref_start carries no recognisable locus number.
    """
    if not ref_start:
        return None, None
    m = _TRAILING_LOCUS.search(ref_start)
    if not m:
        return None, None
    parts = m.group(1).split('.')
    if len(parts) >= 2:
        book = parts[0]
        return f'b{book}', book
    try:
        line = int(parts[0])
    except ValueError:
        return None, None
    block_start = ((line - 1) // 100) * 100 + 1
    return f'block{block_start}', str(block_start)


def _book_sort_key(book_id):
    """Numeric books ("b2" before "b10") and line blocks sort by their
    number; anything unrecognised sorts after, alphabetically."""
    # "block" is checked before the bare "b" prefix -- "block1" also starts
    # with "b", and stripping only one character from it would leave "lock1",
    # not the number.
    if book_id.startswith('block'):
        raw = book_id[5:]
    elif book_id.startswith('b'):
        raw = book_id[1:]
    else:
        raw = book_id
    try:
        return (0, int(raw))
    except ValueError:
        return (1, raw)


def _log_scale(counts):
    """(normalised, legend) for a counts matrix, colour on a LOG scale:
    normalised = log(1 + count) / log(1 + largest count).

    History (NC, 2026-09-19). A linear count/max scale left almost every
    cell the same pale grey: a handful of huge counts (Homer x Quintus
    Smyrnaeus, over 20,000 links) flattened the ordinary few-hundred-link
    cells. Percentile rank fixed that but overshot: by construction it
    paints the top fifth of cells in the darkest shade, so the top-50
    author grid read as mostly dark red. On the same grid the log scale
    puts about 7% of cells in the darkest fifth of the ramp, a third in the
    next shade down, and the median (about 220 links) at a middle tone.
    Each step of shade stands for roughly the same RATIO of links, so only
    the genuinely largest counts go fully dark.

    `legend` gives the low (smallest nonzero count), middle (median) and
    high (largest count) raw counts, for a small legend under the grid.
    """
    nonzero = sorted(v for row in counts for v in row if v > 0)
    if not nonzero:
        zeros = [[0.0 for _ in row] for row in counts]
        return zeros, {'low': 0, 'mid': 0, 'high': 0}
    n = len(nonzero)
    denom = math.log1p(nonzero[-1])

    def scale_of(v):
        if v <= 0:
            return 0.0
        if denom <= 0:
            return 1.0
        return min(1.0, math.log1p(v) / denom)

    normalised = [[scale_of(v) for v in row] for row in counts]
    mid_i = n // 2
    mid = nonzero[mid_i] if n % 2 else (nonzero[mid_i - 1] + nonzero[mid_i]) / 2
    legend = {'low': nonzero[0], 'mid': mid, 'high': nonzero[-1]}
    return normalised, legend


def _work_label(work, author_display):
    """A short display label for a work id, e.g. "Vergil, Aeneid".

    Everything else this module answers comes from the cache db alone, which
    does not carry a work's proper title (only backend.utils.get_text_metadata
    does the full job, reading provenance/override files this module has no
    business opening at request time). backend.utils.format_display_name is
    the one piece of that machinery that is pure string formatting -- no file
    I/O beyond a static dict already imported into the process -- so titles
    here match Browse Corpus's own ("Iliad", "Fall of Troy") rather than a
    bare underscores-to-spaces slug (NC, 2026-09-19: "must be proper titles").
    """
    rest = work.split('.', 1)[1] if '.' in work else work
    return f"{author_display}, {format_display_name(rest)}"


# Scripture/translation date overrides (NC, 2026-09-19): author_dates.json
# dates an AUTHOR, but several of this corpus's scripture entities are not
# authors in that sense -- an edition or translation transmits a text far
# older (or, for a modern translation, far newer) than any date attached to
# whoever produced that particular edition, which is why "the World English
# Bible, the Hebrew Bible, the Septuagint and the Coptic Bibles are undated
# or dated by translation" and sort late/wrong. Sorting each by the date of
# the TEXT IT TRANSMITS keeps a scholar's line-of-descent reading intact
# (Hebrew Bible, then Septuagint, then New Testament, then Vulgate/Coptic)
# instead of scattering them by whatever author_dates.json happened to say.
# Applied at READ time in get_map() below, not at build time, so it takes
# effect against an already-built cache with no rebuild.
#
# Keyed by (language, author_key) for an author whose ENTIRE indexed body of
# work IS a scripture edition/translation; jerome.vulgate is keyed by work
# id instead, since Jerome also wrote original works of his own (letters,
# commentaries) that keep his own author_dates.json year. Eobanus (a poet
# who versified Homer, not a Bible) is deliberately absent -- he stays at
# his own author date.
SCRIPTURE_AUTHOR_DATE_OVERRIDES = {
    ('he', 'hebrew_bible'): {'year': -600},
    ('grc', 'septuaginta'): {'year': -250},
    ('grc', 'novum_testamentum'): {'year': 80},
    ('grc', 'new_testament'): {'year': 80},
    ('cop', 'bohairic'): {'year': 300},
    ('cop', 'sahidic'): {'year': 300},
    ('cop', 'sahidica'): {'year': 300},
    # A modern English translation, not an ancient witness in its own right --
    # marked "(tr.)" so grouping it with -600 BCE material (by ITS source,
    # Old and New Testament alike) is not mistaken for an ancient English text.
    ('en', 'world_english_bible'): {'year': -600, 'label_suffix': '(tr.)'},
}
SCRIPTURE_WORK_DATE_OVERRIDES = {
    'jerome.vulgate': {'year': 400},
}


def _scripture_override(work, language, author_key):
    """The date/label override for one row's work, or None. Work id is
    checked first (more specific than an author-wide override)."""
    o = SCRIPTURE_WORK_DATE_OVERRIDES.get(work)
    if o is not None:
        return o
    return SCRIPTURE_AUTHOR_DATE_OVERRIDES.get((language, author_key))


def _entity(view, row, side):
    """Entity id/label/language for one side ('a' or 'b') of a work_pairs row.

    Returns (id, label, language) or (None, None, None) when this view has
    nothing to group this work under (no century, no genre).
    """
    work = row[f'work_{side}']
    language = row[f'lang_{side}']
    author_key = row[f'author_key_{side}']
    author_display = row[f'author_display_{side}']
    century = row[f'century_{side}']
    century_label = row[f'century_label_{side}']
    genre = row[f'genre_{side}']
    if view == 'work':
        return work, _work_label(work, author_display), language
    if view == 'author':
        return f'{author_key}::{language}', f'{author_display} ({language})', language
    if view == 'century':
        if century is None:
            return None, None, None
        return f'{century}::{language}', f'{century_label} ({language})', language
    if view == 'genre':
        if not genre:
            return None, None, None
        return genre, genre, None
    return None, None, None


_JOIN_SQL = '''
    SELECT wp.work_a, wp.work_b, wp.lang_a, wp.lang_b, wp.count, wp.count_notrans,
           wp.is_translation_curated, wp.is_translation_heuristic,
           wa.author_key AS author_key_a, wa.author_display AS author_display_a,
           wa.year AS year_a, wa.century AS century_a, wa.century_label AS century_label_a,
           wa.genre AS genre_a,
           wb.author_key AS author_key_b, wb.author_display AS author_display_b,
           wb.year AS year_b, wb.century AS century_b, wb.century_label AS century_label_b,
           wb.genre AS genre_b
    FROM work_pairs wp
    JOIN works wa ON wa.work = wp.work_a
    JOIN works wb ON wb.work = wp.work_b
'''


def _rows(conn, languages=None):
    cur = conn.execute(_JOIN_SQL)
    for row in cur:
        if languages and (row['lang_a'] not in languages or row['lang_b'] not in languages):
            continue
        yield row


def get_map(view, languages=None, top=DEFAULT_TOP, translations=False):
    if view not in VIEWS:
        return {'error': f'unknown view {view!r}; choose one of {", ".join(VIEWS)}'}
    conn, stale = _connect_for_request()
    if conn is None:
        return _unavailable()
    top = max(2, min(int(top or DEFAULT_TOP), MAX_TOP))
    try:
        entity_label = {}
        entity_lang = {}
        entity_year = {}
        entity_total = {}
        pair_weight = {}
        n_translation_pairs_excluded = 0
        for row in _rows(conn, languages):
            is_trans = _is_translation_pair(row)
            weight = row['count'] if (translations or not is_trans) else 0
            if is_trans and not translations:
                n_translation_pairs_excluded += 1
            if not weight:
                continue
            ea, la, langa = _entity(view, row, 'a')
            eb, lb, langb = _entity(view, row, 'b')
            if ea is None or eb is None:
                continue
            # Scripture/translation date overrides -- see
            # SCRIPTURE_AUTHOR_DATE_OVERRIDES above. Only author/work views
            # sort by year at all, so the label suffix ("(tr.)") is only
            # meaningful there; a century or genre id would gain nothing
            # from it (and "1st c. BCE (tr.)" would be nonsense).
            year_a, year_b = row['year_a'], row['year_b']
            override_a = _scripture_override(row['work_a'], row['lang_a'], row['author_key_a'])
            override_b = _scripture_override(row['work_b'], row['lang_b'], row['author_key_b'])
            if override_a:
                year_a = override_a['year']
                if view in ('author', 'work') and override_a.get('label_suffix'):
                    la = f"{la} {override_a['label_suffix']}"
            if override_b:
                year_b = override_b['year']
                if view in ('author', 'work') and override_b.get('label_suffix'):
                    lb = f"{lb} {override_b['label_suffix']}"
            entity_label[ea] = la
            entity_label[eb] = lb
            entity_lang[ea] = langa
            entity_lang[eb] = langb
            # Author/work chronology: the underlying work's own year (author
            # and work share one, since work-level year IS the author's
            # year). Century's numeric value is parsed back out of its id
            # (f'{century}::{language}') when sorting, and genre sorts on
            # its own label, so neither needs tracking here.
            entity_year[ea] = year_a
            entity_year[eb] = year_b
            entity_total[ea] = entity_total.get(ea, 0) + weight
            entity_total[eb] = entity_total.get(eb, 0) + weight
            key = (ea, eb) if ea <= eb else (eb, ea)
            pair_weight[key] = pair_weight.get(key, 0) + weight

        # The Top N control still chooses the N most-connected entities by
        # link count; ONLY the display order changes below. NC (owner),
        # 2026-09-19: rows/columns should read chronologically, not by how
        # connected an author happens to be, so a scholar can trace a line
        # of descent across the grid rather than hunt for a name.
        ranked = sorted(entity_total.items(), key=lambda kv: -kv[1])[:top]
        ids = [e for e, _ in ranked]
        if view in ('author', 'work'):
            # BCE years are negative (backend/author_dates.json), so a plain
            # ascending sort already puts BCE before CE; entities with no
            # dated author sort last, tie-broken by name/title.
            ids.sort(key=lambda e: (entity_year.get(e) is None,
                                    entity_year.get(e) if entity_year.get(e) is not None else 0,
                                    entity_label.get(e, '')))
        elif view == 'century':
            # id is f'{century}::{language}'; century is signed (BCE
            # negative), same convention as year above.
            ids.sort(key=lambda e: (int(e.split('::', 1)[0]), entity_lang.get(e) or ''))
        elif view == 'genre':
            ids.sort(key=lambda e: entity_label.get(e, '').lower())
        index_of = {e: i for i, e in enumerate(ids)}
        n = len(ids)
        counts = [[0] * n for _ in range(n)]
        for (ea, eb), w in pair_weight.items():
            if ea in index_of and eb in index_of:
                i, j = index_of[ea], index_of[eb]
                counts[i][j] += w
                if i != j:
                    counts[j][i] += w
        normalised, legend = _log_scale(counts)
        return _with_stale({
            'view': view,
            'languages': languages or None,
            'translations': bool(translations),
            'top': top,
            'labels': [entity_label[e] for e in ids],
            'ids': ids,
            'entity_languages': [entity_lang[e] for e in ids],
            'legend': legend,
            'counts': counts,
            'normalised': normalised,
            'translation_pairs_hidden': 0 if translations else n_translation_pairs_excluded,
            'index_fingerprint': index_fingerprint(),
        }, stale)
    finally:
        conn.close()


def get_cell(view, a, b, languages=None, translations=False):
    """The work pairs behind one matrix cell, plus (NC, 2026-09-19) a
    works x works matrix over the same rows for the UI's "second heatmap":
    clicking an author-by-author cell drills into a grid of that author's
    works against the other author's, rather than a flat list. `work_pairs`
    is kept exactly as it was for the century/genre views (and anyone else
    still reading it), and `works_matrix` is None when there is nothing to
    grid (no matching rows).

    Each row's own work_a/work_b columns are not reliably "a's work then b's
    work" -- a row matches this cell whichever way its two entities landed --
    so both the flat list's fields and the matrix's sides are read off of
    which entity (`ea`/`eb`) the row's work_a actually belongs to, not off
    column position.
    """
    if view not in VIEWS:
        return {'error': f'unknown view {view!r}; choose one of {", ".join(VIEWS)}'}
    if not (a and b):
        return {'error': 'a and b are required'}
    conn, stale = _connect_for_request()
    if conn is None:
        return _unavailable()
    try:
        out = []
        works_a, works_b = {}, {}
        cell_counts = {}
        for row in _rows(conn, languages):
            ea, la, _ = _entity(view, row, 'a')
            eb, lb, _ = _entity(view, row, 'b')
            if ea is None or eb is None:
                continue
            pair = {ea, eb}
            if pair != {a, b}:
                continue
            is_trans = _is_translation_pair(row)
            weight = row['count'] if (translations or not is_trans) else 0
            if not weight and not translations:
                continue
            out.append({
                'work_a': row['work_a'], 'work_b': row['work_b'],
                'lang_a': row['lang_a'], 'lang_b': row['lang_b'],
                'count': row['count'],
                'is_translation': is_trans,
                'is_translation_curated': bool(row['is_translation_curated']),
                'is_translation_heuristic': bool(row['is_translation_heuristic']),
            })
            if not weight:
                continue
            if ea == a:
                wa_id, wa_label = row['work_a'], _work_label(row['work_a'], row['author_display_a'])
                wb_id, wb_label = row['work_b'], _work_label(row['work_b'], row['author_display_b'])
            else:
                wa_id, wa_label = row['work_b'], _work_label(row['work_b'], row['author_display_b'])
                wb_id, wb_label = row['work_a'], _work_label(row['work_a'], row['author_display_a'])
            works_a[wa_id] = wa_label
            works_b[wb_id] = wb_label
            cell_counts[(wa_id, wb_id)] = cell_counts.get((wa_id, wb_id), 0) + weight
        out.sort(key=lambda r: -r['count'])

        works_matrix = None
        if works_a and works_b:
            ids_a = sorted(works_a, key=lambda w: works_a[w].lower())
            ids_b = sorted(works_b, key=lambda w: works_b[w].lower())
            counts = [[cell_counts.get((wa, wb), 0) for wb in ids_b] for wa in ids_a]
            normalised, legend = _log_scale(counts)
            works_matrix = {
                'ids_a': ids_a, 'labels_a': [works_a[w] for w in ids_a],
                'ids_b': ids_b, 'labels_b': [works_b[w] for w in ids_b],
                'counts': counts, 'normalised': normalised, 'legend': legend,
            }

        return _with_stale({'view': view, 'a': a, 'b': b, 'work_pairs': out, 'count': len(out),
                           'works_matrix': works_matrix}, stale)
    finally:
        conn.close()


def get_pair(work_a, work_b, limit=DEFAULT_PAIR_LIMIT, book_a=None, book_b=None):
    """The strongest passage pairs behind one work pair.

    `edges` is written directionally, once per window's OWN nearest-neighbour
    search (see scripts/build_connections_map.py): a window i in work_a can
    find window j in work_b a neighbour, and separately window j can find
    window i a neighbour of ITS OWN, and because cosine similarity is
    symmetric that is very often the identical passage pair recorded twice,
    not two different findings. NC, 2026-09-19, reported exactly this: the
    same pair "once in each direction". Fixed here two ways:
      * deduplicated on the UNORDERED window pair, keeping the higher-scoring
        (or first-seen, when scores tie) occurrence;
      * `window_a` in the response always names the side belonging to the
        `work_a` PARAMETER, `window_b` the `work_b` parameter -- previously
        this was read off the matching row's own work_a/work_b columns, which
        is only "work_a-first" for rows found from work_a's own search and
        backwards for rows found from work_b's, i.e. the second, uncredited
        source of the same "shown twice, reversed" complaint.

    `book_a`/`book_b`, when given, filter to pairs whose respective side
    falls in that book (see _book_of) -- the third drill-down level's cell.
    """
    if not (work_a and work_b):
        return {'error': 'work_a and work_b are required'}
    conn, stale = _connect_for_request()
    if conn is None:
        return _unavailable()
    limit = max(1, min(int(limit or DEFAULT_PAIR_LIMIT), MAX_PAIR_LIMIT))
    try:
        wmeta = {}
        for r in conn.execute('SELECT * FROM works WHERE work IN (?, ?)', (work_a, work_b)):
            wmeta[r['work']] = dict(r)
        if work_a not in wmeta or work_b not in wmeta:
            return {'error': f'work not found in the connections map cache: '
                             f'{work_a if work_a not in wmeta else work_b}',
                    'pairs': []}
        # A book filter needs every candidate scored against its own ref, not
        # just the first `limit` by score, so fetch a generous candidate set
        # (or, with a book filter, all of them -- a few hundred edges per work
        # pair at most in practice) rather than adding a second query.
        fetch_cap = None if (book_a or book_b) else min(limit * 4, MAX_PAIR_LIMIT * 4)
        query = ('SELECT window_a, window_b, score, work_a, work_b FROM edges '
                'WHERE (work_a=? AND work_b=?) OR (work_a=? AND work_b=?) '
                'ORDER BY score DESC')
        params = (work_a, work_b, work_b, work_a)
        if fetch_cap is not None:
            query += ' LIMIT ?'
            params = params + (fetch_cap,)
        rows = conn.execute(query, params).fetchall()

        # Skip an edge whose window no longer exists in the CURRENT passage
        # index (NC, 2026-09-19): a cache -- current or a stale fallback --
        # can name a window a corpus edit since retired, and the drill-down
        # must never link the Reader to a passage that is not there any
        # more. current_ids empty means ids.json could not be read, which is
        # an environment problem, not evidence every window is gone -- fail
        # open rather than returning nothing.
        current_ids = _current_ids()

        # Deduplicate on the unordered window pair (see docstring); ORDER BY
        # score DESC above means the first occurrence kept is the
        # higher-scoring one.
        seen = set()
        deduped = []
        for r in rows:
            if current_ids and (r['window_a'] not in current_ids or r['window_b'] not in current_ids):
                continue
            key = frozenset((r['window_a'], r['window_b']))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)

        win_ids = set()
        for r in deduped:
            win_ids.add(r['window_a'])
            win_ids.add(r['window_b'])
        windows = {}
        if win_ids:
            qmarks = ','.join('?' * len(win_ids))
            for r in conn.execute(f'SELECT * FROM windows WHERE id IN ({qmarks})', tuple(win_ids)):  # nosec B608 - placeholders only, ids bound as parameters
                windows[r['id']] = dict(r)

        def side(win_id, work_key):
            w = windows.get(win_id) or {}
            m = wmeta[work_key]
            rest = work_key.split('.', 1)[1] if '.' in work_key else work_key
            return {
                'window_id': win_id,
                'work': work_key,
                # Proper title (NC, 2026-09-19: "author and work in full,
                # then the reference"), not the bare underscored slug.
                'title': format_display_name(rest),
                'language': w.get('language') or m['language'],
                'ref_start': w.get('ref_start'),
                'ref_end': w.get('ref_end'),
                'gist': w.get('gist'),
                'author_display': m['author_display'],
                'reader_url': (f"/read?work={work_key}.tess&lang={w.get('language') or m['language']}"
                              f"&ref={w.get('ref_start') or ''}&refEnd={w.get('ref_end') or w.get('ref_start') or ''}"
                              f"&tab=similar"),
            }

        pairs = []
        for r in deduped:
            # Always work_a-parameter's window on the left, work_b's on the
            # right, regardless of which direction this row was found from.
            if r['work_a'] == work_a:
                win_left, win_right = r['window_a'], r['window_b']
            else:
                win_left, win_right = r['window_b'], r['window_a']
            if book_a or book_b:
                ref_left = (windows.get(win_left) or {}).get('ref_start')
                ref_right = (windows.get(win_right) or {}).get('ref_start')
                bl, _ = _book_of(ref_left)
                br, _ = _book_of(ref_right)
                if book_a and bl != book_a:
                    continue
                if book_b and br != book_b:
                    continue
            pairs.append({
                'score': round(r['score'], 4),
                'window_a': side(win_left, work_a),
                'window_b': side(win_right, work_b),
            })
            if len(pairs) >= limit:
                break
        return _with_stale({
            'work_a': work_a, 'work_b': work_b,
            'meta_a': {'language': wmeta[work_a]['language'], 'author_display': wmeta[work_a]['author_display']},
            'meta_b': {'language': wmeta[work_b]['language'], 'author_display': wmeta[work_b]['author_display']},
            'count': len(pairs),
            'pairs': pairs,
        }, stale)
    finally:
        conn.close()


def get_books_map(work_a, work_b):
    """Books x books heatmap for one work pair -- the third drill-down level
    (NC, 2026-09-19). A "book" is _book_of(ref_start): the first level of a
    window's locus, or a block of 100 lines for a ref with only one level.
    Cell = number of edges (deduplicated the same way get_pair is) between
    windows of those two books. Built entirely from the edges/windows tables
    already in this cache -- no schema change, no rebuild.
    """
    if not (work_a and work_b):
        return {'error': 'work_a and work_b are required'}
    conn, stale = _connect_for_request()
    if conn is None:
        return _unavailable()
    try:
        wmeta = {}
        for r in conn.execute('SELECT * FROM works WHERE work IN (?, ?)', (work_a, work_b)):
            wmeta[r['work']] = dict(r)
        if work_a not in wmeta or work_b not in wmeta:
            return {'error': f'work not found in the connections map cache: '
                             f'{work_a if work_a not in wmeta else work_b}',
                    'ids_a': [], 'ids_b': []}

        rows = conn.execute('''
            SELECT e.window_a, e.window_b, e.work_a, e.work_b,
                   wa.ref_start AS ref_a, wb.ref_start AS ref_b
            FROM edges e
            JOIN windows wa ON wa.id = e.window_a
            JOIN windows wb ON wb.id = e.window_b
            WHERE (e.work_a=? AND e.work_b=?) OR (e.work_a=? AND e.work_b=?)
        ''', (work_a, work_b, work_b, work_a)).fetchall()

        # Skip an edge whose window the current corpus no longer has (NC,
        # 2026-09-19) -- see the matching comment in get_pair.
        current_ids = _current_ids()

        seen = set()
        books_a, books_b = {}, {}
        cell_counts = {}
        for r in rows:
            if current_ids and (r['window_a'] not in current_ids or r['window_b'] not in current_ids):
                continue
            key = frozenset((r['window_a'], r['window_b']))
            if key in seen:
                continue
            seen.add(key)
            if r['work_a'] == work_a:
                ref_left, ref_right = r['ref_a'], r['ref_b']
            else:
                ref_left, ref_right = r['ref_b'], r['ref_a']
            ba, ba_label = _book_of(ref_left)
            bb, bb_label = _book_of(ref_right)
            if ba is None or bb is None:
                continue
            books_a[ba] = ba_label
            books_b[bb] = bb_label
            cell_counts[(ba, bb)] = cell_counts.get((ba, bb), 0) + 1

        ids_a = sorted(books_a, key=_book_sort_key)
        ids_b = sorted(books_b, key=_book_sort_key)
        counts = [[cell_counts.get((ba, bb), 0) for bb in ids_b] for ba in ids_a]
        normalised, legend = _log_scale(counts)
        return _with_stale({
            'work_a': work_a, 'work_b': work_b,
            'meta_a': {'language': wmeta[work_a]['language'], 'author_display': wmeta[work_a]['author_display']},
            'meta_b': {'language': wmeta[work_b]['language'], 'author_display': wmeta[work_b]['author_display']},
            'ids_a': ids_a, 'labels_a': [books_a[i] for i in ids_a],
            'ids_b': ids_b, 'labels_b': [books_b[i] for i in ids_b],
            'counts': counts, 'normalised': normalised, 'legend': legend,
        }, stale)
    finally:
        conn.close()


def get_work_connections(work, languages=None, translations=False, limit=50):
    if not work:
        return {'error': 'work is required'}
    conn, stale = _connect_for_request()
    if conn is None:
        return _unavailable()
    limit = max(1, min(int(limit or 50), 500))
    try:
        me = conn.execute('SELECT * FROM works WHERE work=?', (work,)).fetchone()
        if not me:
            return {'error': f'work not found in the connections map cache: {work}',
                    'connections': []}
        rows = conn.execute('''
            SELECT wp.*, wa.author_display AS ad_a, wb.author_display AS ad_b
            FROM work_pairs wp
            JOIN works wa ON wa.work = wp.work_a
            JOIN works wb ON wb.work = wp.work_b
            WHERE wp.work_a=? OR wp.work_b=?
        ''', (work, work)).fetchall()
        out = []
        for r in rows:
            other_side = 'b' if r['work_a'] == work else 'a'
            other_work = r[f'work_{other_side}']
            other_lang = r[f'lang_{other_side}']
            other_display = r[f'ad_{other_side}']
            if languages and other_lang not in languages:
                continue
            is_trans = _is_translation_pair(r)
            weight = r['count'] if (translations or not is_trans) else 0
            if not weight:
                continue
            out.append({
                'work': other_work, 'language': other_lang, 'author_display': other_display,
                'count': weight, 'is_translation': is_trans,
            })
        out.sort(key=lambda r: -r['count'])
        return _with_stale({
            'work': work, 'language': me['language'], 'author_display': me['author_display'],
            'window_count': me['window_count'], 'total_links': me['total_links'],
            'connections': out[:limit],
            'count': len(out),
        }, stale)
    finally:
        conn.close()


def meta():
    """Build-time meta (built_at, counts) for a status display."""
    conn, stale = _connect_for_request()
    if conn is None:
        return _unavailable()
    try:
        out = {}
        for r in conn.execute('SELECT key, value FROM meta'):
            try:
                out[r['key']] = json.loads(r['value'])
            except ValueError:
                out[r['key']] = r['value']
        return _with_stale(out, stale)
    finally:
        conn.close()
