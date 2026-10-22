"""People & Places search: a case form copied from a line finds the entry the scan filed it under."""
import sqlite3

from backend import entity_extras as x


def _conn(rows):
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE form_entities (form_key TEXT PRIMARY KEY, eid INTEGER, n INTEGER)')
    c.executemany('insert into form_entities values (?, ?, ?)', rows)
    return c


CAT = {'by_eid': {7: {'eid': 7, 'id': 'pl:590031', 'label': 'Rhodos (island)'}},
       'names': {9: {'eid': 9, 'id': 'nm:iulia', 'label': 'Iulia'}}}


def test_a_case_form_finds_its_entity():
    c = _conn([(x.ei.fold('Rhodum'), 7, 12), (x.ei.fold('Iuliam'), 9, 3)])
    assert x.entity_for_form(CAT, c, 'Rhodum')['id'] == 'pl:590031'
    assert x.entity_for_form(CAT, c, 'Iuliam')['id'] == 'nm:iulia'


def test_no_row_no_table_or_unknown_entity_gives_none():
    c = _conn([(x.ei.fold('Lesbum'), 99, 1)])
    assert x.entity_for_form(CAT, c, 'Thyesten') is None
    assert x.entity_for_form(CAT, c, 'Lesbum') is None
    assert x.entity_for_form(CAT, sqlite3.connect(':memory:'), 'Rhodum') is None
