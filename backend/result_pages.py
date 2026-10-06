"""Server-side pages over a finished search's result list.

A search still computes, scores and globally sorts its whole result set; this
module only changes delivery. When a request opts in with ``page_size``, the
list the endpoint would have sent is written once to a snapshot file and the
response carries the first page plus an opaque ``result_id``. Later pages,
other sort orders and the chart filter are served from that snapshot by
``GET /api/search-results/<result_id>``: filter, then sort, then slice, always
over the complete list, so concatenating the pages reproduces the old array.

Snapshots live on disk (not in process memory) so a page request can land on
any mod_wsgi worker, the same arrangement as tmp/search_cancellations. They
are a copy of exactly what was displayed, not a pointer into cache/, because a
cache file can be replaced by "Refresh results" or cleared while someone is
paging, and fusion caches its list before the formula filter is applied.
"""
import json
import os
import re
import secrets
import tempfile
import time

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULT_DIR = os.environ.get(
    'TESSERAE_RESULT_PAGES_DIR',
    os.path.join(_PROJECT_ROOT, 'tmp', 'search_results'),
)
TTL_SECONDS = 6 * 3600
# A 5000-row fusion snapshot is ~13 MB, so the bound is on bytes, not files.
MAX_TOTAL_BYTES = int(os.environ.get('TESSERAE_RESULT_PAGES_MAX_BYTES', 1024 ** 3))
MAX_LIMIT = 100
SORTS = ('score', 'source_locus', 'target_locus')

_ID_RE = re.compile(r'^[0-9a-f]{32}$')


def requested_page_size(data):
    """The request's page_size as an int in 1..MAX_LIMIT, or None (legacy,
    unpaged response). Anything else is treated as not asking for pages."""
    value = (data or {}).get('page_size')
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value if 1 <= value <= MAX_LIMIT else None


def _path(result_id):
    return os.path.join(RESULT_DIR, f'{result_id}.json')


def _prune():
    """Drop expired snapshots, then the oldest until the rest fit in
    MAX_TOTAL_BYTES. Stray .tmp files from a killed worker age out too."""
    try:
        entries = []
        for name in os.listdir(RESULT_DIR):
            path = os.path.join(RESULT_DIR, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            entries.append((st.st_mtime, st.st_size, path))
    except OSError:
        return
    cutoff = time.time() - TTL_SECONDS
    kept = 0
    for mtime, size, path in sorted(entries, reverse=True):  # newest first
        if mtime >= cutoff and path.endswith('.tmp'):
            continue  # another worker may be writing it right now
        if mtime >= cutoff and kept + size <= MAX_TOTAL_BYTES:
            kept += size
            continue
        try:
            os.unlink(path)
        except OSError:
            pass


def store(results):
    """Persist a finished result list; return its new opaque id."""
    os.makedirs(RESULT_DIR, exist_ok=True)
    _prune()
    result_id = secrets.token_hex(16)
    fd, tmp = tempfile.mkstemp(dir=RESULT_DIR, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(results, f)
        # Atomic: another worker sees either no file or the whole file.
        os.replace(tmp, _path(result_id))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return result_id


def load(result_id):
    """The stored list, or None for a malformed, unknown or expired id."""
    if not isinstance(result_id, str) or not _ID_RE.match(result_id):
        return None
    path = _path(result_id)
    try:
        if os.path.getmtime(path) < time.time() - TTL_SECONDS:
            os.unlink(path)
            return None
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---- Ports of the browser's former full-array logic (SearchResults.jsx) ----

def _score(r):
    for key in ('fused_score', 'score', 'overall_score'):
        v = r.get(key)
        if v is not None:
            return v if isinstance(v, (int, float)) else 0
    return 0


def _locus(r, side):
    return str(r.get(f'{side}_locus') or (r.get(side) or {}).get('ref') or '')


def _natural_key(s):
    # Stand-in for localeCompare(..., {numeric: true}): digit runs compare as
    # numbers, text case-insensitively. split() always starts with a text part,
    # so text and number positions line up between any two keys.
    parts = re.split(r'(\d+)', s)
    return [int(p) if i % 2 else p.casefold() for i, p in enumerate(parts)]


def _numbers(locus):
    return [int(n) for n in re.findall(r'\d+', locus)]


def sort_rows(rows, sort):
    """Stable, like Array.prototype.sort, so ties keep their stored order."""
    if sort == 'source_locus' or sort == 'target_locus':
        side = sort.split('_')[0]
        return sorted(rows, key=lambda r: _natural_key(_locus(r, side)))
    return sorted(rows, key=_score, reverse=True)


def filter_rows(rows, view, book=None, line_min=None, line_max=None):
    """The chart-bar filter: a book label ("Book 3" / "Other") or a line band
    on the source or target locus."""
    out = []
    for r in rows:
        nums = _numbers(_locus(r, view))
        if line_min is not None:
            line = nums[-1] if nums else None
            if line is not None and line_min <= line <= line_max:
                out.append(r)
        elif (f'Book {nums[0]}' if nums else 'Other') == book:
            out.append(r)
    return out


def distribution(rows, view):
    """Chart data for one view: by book when the loci span several books,
    otherwise parallels per line band. None when there is nothing to plot."""
    pts = []
    for r in rows:
        nums = _numbers(_locus(r, view))
        pts.append((nums[0] if len(nums) >= 2 else None, nums[-1] if nums else None))
    if not pts:
        return None
    books = {b for b, _ in pts if b is not None}
    if len(books) <= 1:
        lines = [n for _, n in pts if n is not None]
        if not lines:
            return None
        max_line = max(lines)
        band = next((b for b in (10, 25, 50, 100, 200, 500, 1000)
                     if -(-max_line // b) <= 18), 1000)
        n_bands = max(1, -(-max_line // band))
        counts = [0] * n_bands
        for n in lines:
            if n < 1:
                continue  # the browser's counts[-1] landed outside the bars
            counts[min(n_bands - 1, (n - 1) // band)] += 1
        return {'mode': 'line', 'band': band,
                'labels': [f'{i * band + 1}–{(i + 1) * band}' for i in range(n_bands)],
                'counts': counts}
    by_book = {}
    for b, _ in pts:
        label = f'Book {"null" if b is None else b}'
        by_book[label] = by_book.get(label, 0) + 1
    labels = sorted(by_book, key=lambda k: int(re.sub(r'\D', '', k) or 0))
    return {'mode': 'book', 'labels': labels, 'counts': [by_book[k] for k in labels]}


def paginate_payload(payload, page_size):
    """Turn a finished response dict into its paged form, in place: store the
    full ``results`` list, keep only the first page, add the id and the
    aggregates the page used to compute from every row."""
    rows = payload.get('results') or []
    if not rows:
        return payload  # nothing to page; the client shows the empty state
    ordered = sort_rows(rows, 'score')
    payload['result_id'] = store(rows)
    payload['result_total'] = len(rows)
    payload['page_size'] = page_size
    payload['results'] = ordered[:page_size]
    payload['aggregates'] = {'distribution': {
        'source': distribution(rows, 'source'),
        'target': distribution(rows, 'target'),
    }}
    return payload


def query_page(rows, args):
    """Apply a page request's query args. Raises ValueError on bad input."""
    def as_int(name, default):
        raw = args.get(name)
        if raw is None or raw == '':
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ValueError(f'{name} must be an integer')

    offset = as_int('offset', 0)
    limit = as_int('limit', 50)
    if offset < 0:
        raise ValueError('offset must be >= 0')
    if not 1 <= limit <= MAX_LIMIT:
        raise ValueError(f'limit must be between 1 and {MAX_LIMIT}')
    sort = args.get('sort') or 'score'
    if sort not in SORTS:
        raise ValueError(f'sort must be one of {", ".join(SORTS)}')

    view = args.get('filter_view')
    if view:
        if view not in ('source', 'target'):
            raise ValueError('filter_view must be source or target')
        line_min = as_int('filter_line_min', None)
        line_max = as_int('filter_line_max', None)
        book = args.get('filter_book')
        if (line_min is None) != (line_max is None):
            raise ValueError('filter_line_min and filter_line_max go together')
        if line_min is None and not book:
            raise ValueError('filter_view needs filter_book or a line range')
        rows = filter_rows(rows, view, book, line_min, line_max)

    rows = sort_rows(rows, sort)
    return {'results': rows[offset:offset + limit], 'total': len(rows),
            'offset': offset, 'limit': limit}
