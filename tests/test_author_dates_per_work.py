"""A work-level date entry wins over its author's (2026-10-07)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.utils import enrich_metadata_with_author_dates  # noqa: E402

DATES = {'anonymus': {'era': 'Unknown', 'year': None},
         'anonymus.carmen_de_pippino': {'era': 'Carolingian', 'year': 800},
         'vergil': {'era': 'Augustan', 'year': -19}}


def test_work_entry_wins():
    m = enrich_metadata_with_author_dates({'author_key': 'anonymus', 'work_key': 'carmen_de_pippino'}, DATES)
    assert (m['era'], m['year']) == ('Carolingian', 800)


def test_author_entry_when_no_work_entry():
    m = enrich_metadata_with_author_dates({'author_key': 'anonymus', 'work_key': 'other'}, DATES)
    assert m['era'] == 'Unknown'
    m = enrich_metadata_with_author_dates({'author_key': 'vergil', 'work_key': 'aeneid'}, DATES)
    assert m['year'] == -19


def test_part_file_uses_its_work_entry():
    m = enrich_metadata_with_author_dates({'author_key': 'anonymus', 'work_key': 'carmen_de_pippino.part.2'}, DATES)
    assert m['era'] == 'Carolingian'
