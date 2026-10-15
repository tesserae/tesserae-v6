"""Cached search results kept in memory, one file read per change.

A cached search result is one JSON file (cache/<key>.json) of five to a few
hundred megabytes. The routes that serve a result from it used to read and
parse the whole file on every request, and the fusion route also recounted
each row's formula count and the per-book distribution every time.

This keeps the parsed result in memory, a few at a time, and gives it back
for as long as the file and the tables its derived fields read are unchanged.
The key is each file's size and modification time, the way the connections
map is kept, so a result that is recomputed (the file is rewritten) or a
bigram table that is rebuilt is read again on the next request.

A parsed result is about six times the size of its file in memory, so the
total is capped by file size: an entry larger than the cap is never kept, and
the oldest entries leave first.
"""
import os
import threading
from collections import OrderedDict

MAX_TOTAL_BYTES = 32 * 1024 * 1024

_lock = threading.Lock()
_entries = OrderedDict()   # path -> (stamp, size, value)
_total = 0


def stamp_of(*paths):
    """(size, mtime_ns) of each file, None for a file that is absent."""
    out = []
    for p in paths:
        try:
            st = os.stat(p)
            out.append((st.st_size, st.st_mtime_ns))
        except OSError:
            out.append(None)
    return tuple(out)


def get(path, stamp):
    """The value kept for `path` if it was stored under this stamp."""
    with _lock:
        entry = _entries.get(path)
        if entry is None or entry[0] != stamp:
            return None
        _entries.move_to_end(path)
        return entry[2]


def put(path, stamp, size, value):
    """Keep `value` for `path` under `stamp`; `size` is the result file's size
    in bytes. Returns False (keeping nothing) when it exceeds the cap."""
    global _total
    with _lock:
        old = _entries.pop(path, None)
        if old is not None:
            _total -= old[1]
        if size > MAX_TOTAL_BYTES:
            return False
        _entries[path] = (stamp, size, value)
        _total += size
        while _total > MAX_TOTAL_BYTES and len(_entries) > 1:
            _, (_, evicted_size, _) = _entries.popitem(last=False)
            _total -= evicted_size
        return True


def clear():
    global _total
    with _lock:
        _entries.clear()
        _total = 0
