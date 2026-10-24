"""drop_stale_rule_rows: only rows that left the radius and do not name the event are removed."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts', 'events'))
import drop_stale_rule_rows as D  # noqa: E402


def store(rows):
    c = sqlite3.connect(':memory:')
    c.execute('CREATE TABLE events (id TEXT, label TEXT, place TEXT, pleiades_id TEXT, participants TEXT)')
    c.execute('INSERT INTO events VALUES (?,?,?,?,?)', ('E1', 'Battle', 'Placeville', '1', json.dumps(['Caesar'])))
    c.execute('CREATE TABLE documents (event_id TEXT, doc_id TEXT, distance_km REAL)')
    c.executemany('INSERT INTO documents VALUES (?,?,?)', rows)
    return c


def test_removes_only_stale_rule_rows_not_naming_rows_or_far_rows_already_far():
    live = store([('E1', 'stale', 40.0), ('E1', 'names_place', 40.0), ('E1', 'names_person', 99.0),
                  ('E1', 'far_before', 500.0), ('E1', 'near', 10.0), ('E1', 'nodist', None)])
    new = store([('E1', 'stale', 1500.0), ('E1', 'names_place', 1500.0), ('E1', 'names_person', 1500.0),
                 ('E1', 'far_before', 3000.0), ('E1', 'near', 0.0), ('E1', 'nodist', None)])
    ent = sqlite3.connect(':memory:')
    ent.execute('CREATE TABLE document_mentions (eid TEXT, doc_id TEXT)')
    ent.executemany('INSERT INTO document_mentions VALUES (?,?)', [('P1', 'names_place'), ('C1', 'names_person'),
                                                                   ('P1', 'unrelated_to_event')])

    def resolve(name):
        return {'Caesar': 'C1', 'Placeville': 'P1'}.get(name)
    remove, kept, cands = D.plan_removals(new, live, ent, resolve)
    assert remove == [('E1', 'stale')]
    assert sorted(kept) == [('E1', 'names_person'), ('E1', 'names_place')]
    assert len(cands) == 3
