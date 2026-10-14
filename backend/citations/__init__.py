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


def extract_documents(text, edition_index=None):
    """References to inscriptions, papyri, ostraca and coins in text ("CIL VI
    1234", "AE 1976, 123", "P.Oxy. XII 1453", "RIC I² 207"), each with a
    normalised key. Independent of extract(): needs no abbreviation table, and
    literary citations are resolved exactly as before. With a
    backend.document_citations.DocumentEditionIndex, each hit also carries
    'doc_ids', the documents whose stored edition reference matches."""
    from backend import document_citations as dc
    cits = dc.find_document_citations(text)
    if edition_index is not None:
        dc.link_documents(cits, edition_index)
    return cits


def extract_all(text, edition_index=None):
    """{'literary': [...], 'documents': [...]} for text. A literary hit that
    overlaps a document citation is dropped from 'literary': the literary
    grammar reads "CIL VI 1234" as Iliad 6.1234 and "SB XVI 13060" as a work
    abbreviation, so callers that want both kinds must not take them side by
    side. extract() itself is untouched."""
    docs = extract_documents(text, edition_index)
    lit = [h for h in extract(text)
           if not any(h['start'] < d['end'] and d['start'] < h['end'] for d in docs)]
    return {'literary': lit, 'documents': docs}
