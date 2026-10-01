"""The registry of texts held under an indexing-and-search-only licence.

Some texts come to the corpus under a licence that allows them to sit in the
index and be searched, but never to be redistributed: no standalone download,
no copy in the public repository, no passing the text on. The first such
licence is from the Packard Humanities Institute (PHI). This module is the
single place that answers "is this text one of those, and if so what must be
shown beside it": `data/restricted_texts.json` is the registry, and every
other guardrail (the .gitignore block, the downloads blueprint, the release
scripts, the credit shown beside a passage) reads it through here rather than
parsing the file itself.

The text id is a work's base name: the filename under `texts/<lang>/` with
the `.tess` extension and any `.part.N` suffix removed, so one registry entry
covers a work stored as a single file or split across many. `is_restricted`,
`credit_for` and `license_for` all tolerate a bare id, a filename, a book-part
filename, and an id prefixed with a language directory (`la/...`), so a
caller holding any of the forms this codebase passes around can ask directly
without first normalizing it itself.

Loaded once and cached; re-read when the registry file's mtime changes, the
same pattern `load_descriptions` in backend/blueprints/corpus.py uses for
data/text_descriptions.json.
"""
import json
import os
from pathlib import Path

from backend.work_names import base_work

REGISTRY_PATH = Path(__file__).parent.parent / 'data' / 'restricted_texts.json'

_cache = {'mtime': None, 'texts': {}}


def load():
    """The registry's `texts` mapping: {text_id: {holder, credit, license,
    added, ends}}. {} if the file is missing or unreadable, so a corpus with
    no restricted texts (the normal case) needs no special handling anywhere
    that calls this.
    """
    try:
        mtime = os.path.getmtime(REGISTRY_PATH)
    except OSError:
        return {}
    if _cache['mtime'] != mtime:
        try:
            with open(REGISTRY_PATH, encoding='utf-8') as f:
                data = json.load(f)
            _cache['texts'] = data.get('texts', {}) or {}
            _cache['mtime'] = mtime
        except (OSError, ValueError):
            # Keep serving the last good load rather than letting a bad edit
            # to the registry make every restricted text look unrestricted.
            return _cache['texts']
    return _cache['texts']


def _normalize(text_id_or_filename):
    """A bare base-work id, from any of the forms callers hold: a registry
    key already ('vergil.aeneid'), a filename ('vergil.aeneid.tess'), a book
    file ('vergil.aeneid.part.3.tess'), or any of those prefixed with a
    language directory ('la/vergil.aeneid.tess').
    """
    name = text_id_or_filename or ''
    if '/' in name:
        name = name.rsplit('/', 1)[-1]
    if name.endswith('.tess'):
        name = name[:-len('.tess')]
    return base_work(name)


def is_restricted(text_id_or_filename):
    """Whether this text is held under an indexing-only licence."""
    return _normalize(text_id_or_filename) in load()


def _entry(text_id_or_filename):
    return load().get(_normalize(text_id_or_filename))


def credit_for(text_id_or_filename):
    """The fixed credit line to show beside a passage from this text, or
    None when the text is not restricted (or carries no credit line)."""
    entry = _entry(text_id_or_filename)
    return entry.get('credit') if entry else None


def license_for(text_id_or_filename):
    """The licence terms string for this text, or None."""
    entry = _entry(text_id_or_filename)
    return entry.get('license') if entry else None


def filenames(language, texts_root='texts'):
    """The actual .tess filenames under texts/<language>/ (whole files and
    book parts alike) that this registry restricts -- what the downloads
    blueprint and the release scripts need to leave out of a listing, without
    each working out book-part matching for itself.

    The registry does not carry a language field (an id is just a work's base
    name, and a licence holder names the work, not where it lives on disk), so
    this is the one place that connects a registry id to real files: it looks
    at what is actually on disk under `texts_root/language/` and keeps the
    names whose base work is registered. A text not yet present on this
    checkout (restricted texts are never in the public repository) simply
    yields nothing here, which is correct: there is nothing on this disk to
    withhold.
    """
    if not load():
        return []
    lang_dir = os.path.join(texts_root, language)
    try:
        entries = os.listdir(lang_dir)
    except OSError:
        return []
    return sorted(f for f in entries if f.endswith('.tess') and is_restricted(f))
