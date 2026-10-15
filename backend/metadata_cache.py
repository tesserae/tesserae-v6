"""get_text_metadata with a per-process memory of its answers.

get_text_metadata (backend/utils.py) works out a text's author, title and kind
from its file name, the two metadata files (overrides and provenance) and, for a
text whose kind no list names, the first lines of the file. A Line Search or a
wildcard search asks about a thousand texts in one request, and doing that
afresh each time (a stat, a file read) took seconds.

The answer depends only on the file name, the file itself, and the two
metadata files, so it is kept together with their modification stamps and
reused while all of them are unchanged. A text that is replaced, or an edit to
either metadata file, changes a stamp and the answer is worked out again; nothing
has to be cleared by hand and no worker serves an old answer.
"""
import os

from backend import fspaths
from backend import utils

_cache = {}


def _stamp(path):
    try:
        st = os.stat(path)
        return (st.st_mtime_ns, st.st_size)
    except OSError:
        return None


def get_text_metadata_cached(filepath):
    """Same answer as backend.utils.get_text_metadata(filepath), a copy each call."""
    file_stamp = None
    try:
        st = os.stat(fspaths.fs_path(filepath))
        file_stamp = (st.st_mtime_ns, st.st_size)
    except OSError:
        pass
    if file_stamp is None:
        return utils.get_text_metadata(filepath)
    stamp = (file_stamp, _stamp(utils.OVERRIDES_PATH), _stamp(utils.PROVENANCE_PATH))
    hit = _cache.get(filepath)
    if hit is not None and hit[0] == stamp:
        return dict(hit[1])
    metadata = utils.get_text_metadata(filepath)
    _cache[filepath] = (stamp, metadata)
    return dict(metadata)
