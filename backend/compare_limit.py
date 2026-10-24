"""The size limit on a live comparison of two works (2026-10-24).

A comparison of two whole epics holds one web worker for an hour and up to
12 GB, so a pair above COMPARE_MAX_LINE_PAIRS (source lines times target lines)
is not run live. The route answers with the per-book files of each side, so
the page can offer book by book now, and with the address of the download queue
(backend/blueprints/comparison_jobs.py), so it can offer a prepared file later.

The line counts come from the corpus files themselves: the non-blank lines of
the .tess file, which is what the search reads. The count is kept per file and
modification time. Measured pairs: Aeneid 1 against Metamorphoses 1 is 0.59
million pairs (314 s, 3.0 GB), the Aeneid against the whole Metamorphoses 9.1
million (1,136 s, 5.8 GB), the Aeneid against the Metamorphoses 118 million
(killed at 12 GB after an hour).
"""
import os
import re

from backend import fspaths
from backend.utils import resolve_text_path, get_text_metadata

DEFAULT_MAX_LINE_PAIRS = 12_000_000
LIMIT_ENV = 'COMPARE_MAX_LINE_PAIRS'
JOBS_URL = '/api/comparisons/jobs'

_PART_RE = re.compile(r'\.part\.\d+(?:\.[^.]+)?\.tess$')
_line_counts = {}


def max_line_pairs():
    """The limit, read from the environment on every call (default 12,000,000)."""
    raw = (os.environ.get(LIMIT_ENV) or '').strip().replace(',', '').replace('_', '')
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_LINE_PAIRS
    return value if value > 0 else DEFAULT_MAX_LINE_PAIRS


def email_notice_available():
    """True when the site can mail a visitor: an SMTP host is set in the environment."""
    return bool((os.environ.get('SMTP_HOST') or '').strip())


def text_line_count(texts_dir, language, text_id):
    """Non-blank lines of one text file, or None when the file cannot be found."""
    try:
        path = resolve_text_path(texts_dir, language, text_id)
        if not path:
            return None
        st = os.stat(fspaths.fs_path(path))
    except (OSError, TypeError, ValueError):
        return None
    key = (path, st.st_mtime_ns, st.st_size)
    hit = _line_counts.get(path)
    if hit and hit[0] == key:
        return hit[1]
    n = 0
    try:
        with fspaths.open_text(path, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                if line.strip():
                    n += 1
    except OSError:
        return None
    _line_counts[path] = (key, n)
    return n


def is_book_file(text_id):
    return bool(_PART_RE.search(text_id or ''))


def book_files(texts_dir, language, text_id, line_count_fn=None):
    """The per-book files of a whole-file work: [{id, label, lines}], in book order.

    Empty when text_id is already a book file or the work has no book files.
    """
    if is_book_file(text_id):
        return []
    count = line_count_fn or (lambda tid: text_line_count(texts_dir, language, tid))
    base = re.sub(r'\.tess$', '', text_id or '')
    lang_dir = os.path.join(texts_dir, language)
    try:
        names = fspaths.listdir_text(lang_dir)
    except OSError:
        return []
    pat = re.compile(r'^' + re.escape(base) + r'\.part\.(\d+)(?:\.[^.]+)?\.tess$')
    found = []
    for name in names:
        m = pat.match(name)
        if m:
            found.append((int(m.group(1)), name))
    out = []
    for num, name in sorted(found):
        label = None
        try:
            label = get_text_metadata(os.path.join(lang_dir, name)).get('part')
        except Exception:
            label = None
        out.append({'id': name, 'label': label or f'Book {num}', 'lines': count(name)})
    return out


def size_message(source_lines, target_lines, line_pairs, limit):
    """The sentence a connector or a person reads when a pair is refused."""
    return (
        f"These two works are {source_lines:,} by {target_lines:,} lines, "
        f"{line_pairs / 1e6:.0f} million line pairs, above the live limit of {limit / 1e6:.0f} million. "
        "A comparison this size takes the server about an hour, so it is not run live. "
        "To proceed, compare one book of either work against the other text "
        "(the per-book file ids are in `books`; pass one as source or target), "
        "or open the pair on the Tesserae page and ask for the whole comparison "
        "as a prepared file, which the person can fetch when it is ready."
    )


def check_size(texts_dir, language, source_id, target_id, line_count_fn=None):
    """None when the pair may run live, else the too_large answer as a dict.

    line_count_fn(text_id) returns a file's line count; the default reads the
    corpus. A pair with a missing file is left to the route's own error.
    """
    count = line_count_fn or (lambda tid: text_line_count(texts_dir, language, tid))
    n_source = count(source_id)
    n_target = count(target_id)
    if not n_source or not n_target:
        return None
    pairs = n_source * n_target
    limit = max_line_pairs()
    if pairs <= limit:
        return None
    books = []
    for side, tid in (('source', source_id), ('target', target_id)):
        for b in book_files(texts_dir, language, tid, line_count_fn=line_count_fn):
            books.append({'side': side, 'work': tid, **b})
    return {
        'too_large': True,
        'line_pairs': pairs,
        'limit': limit,
        'source_lines': n_source,
        'target_lines': n_target,
        'books': books,
        'download_job_url': JOBS_URL,
        'email_notice': email_notice_available(),
        'message': size_message(n_source, n_target, pairs, limit),
    }
