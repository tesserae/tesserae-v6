"""Citation extractor: references to ancient texts in running prose
("Aen. 1.1", "Verg. A. I 1", "Il. 1.1-7"), resolved to Tesserae work ids.

Grammar rules follow Matteo Romanello's CitationParser, reimplemented in
Python; the abbreviation table (data/citations/abbreviations.json, not in
git) is built from his hucitlib knowledge base (GPL-3.0) and the Perseus
catalogue. Built 2026-09-13; provenance and figures in the private notes.
"""
import os

from .abbrev_index import AbbrevIndex
from .extractor import extract as _extract

_INDEX = None
_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'data', 'citations', 'abbreviations.json')


def index():
    global _INDEX
    if _INDEX is None and os.path.exists(_DATA):
        _INDEX = AbbrevIndex(_DATA)
    return _INDEX


def extract(text):
    """Citations found in text, resolved where possible; [] without the table."""
    idx = index()
    return _extract(text, idx) if idx else []
