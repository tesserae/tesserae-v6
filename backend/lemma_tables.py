"""One loader for the Latin lemma table.

The table `data/lemma_tables/latin_lemmas.json` (form to lemma, one lemma per
form) is read by the live server, the index builder, the hapax and fusion
paths, the prose describer and the cache manifest. Since 2026-10-18 a second
file beside it, `data/lemma_tables/latin_corrections.json`, is applied on top
of the table: where both name a form, the corrections file wins, and its
extra forms are added. Its provenance (one row per form, with the source and
the evidence) is `latin_corrections_provenance.csv` in the same folder.

Every reader calls `load_latin_lemma_table()` so that all of them see one table.
A missing corrections file is not an error (the overlay is empty) and is
logged once.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

LEMMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'lemma_tables')
LATIN_TABLE_NAME = 'latin_lemmas.json'
LATIN_CORRECTIONS_NAME = 'latin_corrections.json'

_missing_logged = set()


def latin_table_path():
    return os.path.join(LEMMA_DIR, LATIN_TABLE_NAME)


def latin_corrections_path(table_path=None):
    """The corrections file that sits beside the table file."""
    folder = os.path.dirname(table_path) if table_path else LEMMA_DIR
    return os.path.join(folder, LATIN_CORRECTIONS_NAME)


def load_latin_corrections(table_path=None):
    """The corrections overlay as a dict (empty when the file is absent)."""
    path = latin_corrections_path(table_path)
    if not os.path.exists(path):
        if path not in _missing_logged:
            _missing_logged.add(path)
            logger.info('No Latin corrections file at %s; using the lemma table unchanged', path)
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_latin_lemma_table(path=None):
    """Load the Latin lemma table and apply the corrections file on top of it.

    `path` is the table file (default: the checkout's latin_lemmas.json); the
    corrections file is looked up beside it. Returns a new dict. A missing
    table file raises FileNotFoundError, as opening it would.
    """
    table_path = path or latin_table_path()
    with open(table_path, 'r', encoding='utf-8') as f:
        table = json.load(f)
    table.update(load_latin_corrections(table_path))
    return table
