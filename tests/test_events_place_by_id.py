"""The events naming step resolves an event's place by its Pleiades id first, and the repair script removes
the documents a label-resolved place wrongly gave (2026-10-24: "Akri", Pleiades 530771, Actium, had resolved
to Akriai in Laconia and took two Agrigentum stones)."""
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'events'))
import add_naming_documents as A  # noqa: E402
import remove_misresolved_place_documents as R  # noqa: E402

ENTITIES = {
    126: {'eid': 126, 'label': 'Akriai', 'type': 'place', 'total': 5, 'pleiades_id': '570058'},
    134: {'eid': 134, 'label': 'Actium', 'type': 'place', 'total': 99, 'pleiades_id': '530771'},
    135: {'eid': 135, 'label': 'Actium (person)', 'type': 'person', 'total': 500, 'pleiades_id': '530771'},
    136: {'eid': 136, 'label': 'Actium (small)', 'type': 'place', 'total': 3, 'pleiades_id': '530771'},
    200: {'eid': 200, 'label': 'Hero', 'type': 'person', 'total': 10, 'pleiades_id': None},
    300: {'eid': 300, 'label': 'Merged heading', 'type': 'place', 'total': 50, 'pleiades_id': None},
}
LABELS = {'Akri': 126, 'Hero': 200, 'Merged': 300}


def by_label(name):
    return LABELS.get(name)


def test_the_entity_of_the_pleiades_id_is_found_a_place_first_then_the_most_lines():
    assert A.entity_by_pleiades(ENTITIES.values(), '530771') == 134
    assert A.entity_by_pleiades(ENTITIES.values(), 530771) == 134
    assert A.entity_by_pleiades(ENTITIES.values(), '999') is None
    assert A.entity_by_pleiades(ENTITIES.values(), None) is None
    assert A.entity_by_pleiades(ENTITIES.values(), '') is None


def test_the_id_wins_over_the_label():
    assert A.resolve_place_entity('Akri', '530771', ENTITIES, by_label) == (134, 'id')


def test_a_label_hit_with_another_pleiades_id_is_refused_and_logged():
    logged = []
    assert A.resolve_place_entity('Akri', '111', ENTITIES, by_label, logged.append) == (None, 'refused')
    assert len(logged) == 1 and A.REFUSED in logged[0]


def test_a_label_hit_with_no_pleiades_id_is_kept_and_so_is_an_event_without_an_id():
    assert A.resolve_place_entity('Merged', '111', ENTITIES, by_label) == (300, 'label')
    assert A.resolve_place_entity('Akri', None, ENTITIES, by_label) == (126, 'label')
    assert A.resolve_place_entity('Nowhere', '111', ENTITIES, by_label) == (None, 'none')
    assert A.resolve_place_entity('', None, ENTITIES, by_label) == (None, 'none')


class Resolver:
    def __call__(self, name):
        return by_label(name)

    def place(self, label, pid, log=None):
        return A.resolve_place_entity(label, pid, ENTITIES, by_label, log)


@pytest.fixture
def stores(tmp_path):
    ev = str(tmp_path / 'events.sqlite')
    c = sqlite3.connect(ev)
    c.executescript('''
      CREATE TABLE events (id TEXT PRIMARY KEY, label TEXT, date_start INTEGER, date_end INTEGER, place TEXT,
                           lat REAL, lon REAL, pleiades_id TEXT, participants TEXT);
      CREATE TABLE documents (event_id TEXT, doc_id TEXT, date_start INTEGER, date_end INTEGER, place TEXT,
                              distance_km REAL, text_snippet TEXT, language TEXT, lat REAL, lon REAL);
      CREATE TABLE requests (id INTEGER);''')
    c.execute("INSERT INTO events VALUES ('E1', 'Battle', -435, -435, 'Akri', NULL, NULL, '530771', '[\"Hero\"]')")
    c.execute("INSERT INTO events VALUES ('E2', 'Unchanged', -435, -435, 'Merged', NULL, NULL, NULL, '[]')")
    for e, d in (('E1', 'wrong'), ('E1', 'hero_and_wrong'), ('E2', 'wrong')):
        c.execute('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)', (e, d, -440, -430, 'x', None, '', 'la', None, None))
    c.execute('INSERT INTO requests VALUES (1)')
    c.commit()
    c.close()
    en = str(tmp_path / 'entities.sqlite')
    c = sqlite3.connect(en)
    c.execute('CREATE TABLE document_mentions (eid INTEGER, doc_id TEXT, language TEXT, form TEXT, kind TEXT, adjective INTEGER)')
    c.executemany('INSERT INTO document_mentions VALUES (?,?,?,?,?,?)', [
        (126, 'wrong', 'grc', 'x', 'corpus_name', 0),
        (126, 'hero_and_wrong', 'grc', 'x', 'corpus_name', 0), (200, 'hero_and_wrong', 'grc', 'h', 'form', 0),
        (134, 'right', 'grc', 'aktio', 'form', 0), (134, 'right_undated', 'grc', 'aktio', 'form', 0),
        (134, 'right_far_later', 'grc', 'aktio', 'form', 0),
        (300, 'wrong', 'grc', 'x', 'form', 0)])
    c.commit()
    c.close()
    md = str(tmp_path / 'metadata.db')
    c = sqlite3.connect(md)
    c.execute('CREATE TABLE documents (id TEXT, date_not_before INTEGER, date_not_after INTEGER, ancient_place TEXT, '
              'pleiades_id TEXT, place_tm_id TEXT, text_type_label TEXT, object_type_label TEXT, principal_edition TEXT, languages TEXT)')
    c.executemany('INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)', [
        ('right', -450, -440, 'Actium', None, None, 'dedication', None, 'IG 1', 'grc'),
        ('right_undated', None, None, 'Actium', None, None, 'dedication', None, 'IG 2', 'grc'),
        ('right_far_later', 200, 250, 'Actium', None, None, 'dedication', None, 'IG 3', 'grc'),
        ('wrong', -440, -430, 'Agrigentum', None, None, 'dedication', None, 'IG 4', 'grc'),
        ('hero_and_wrong', -440, -430, 'Agrigentum', None, None, 'dedication', None, 'IG 5', 'grc')])
    c.commit()
    c.close()
    return ev, en, md, tmp_path


def rows(path, event):
    c = sqlite3.connect(path)
    out = sorted(r[0] for r in c.execute('SELECT doc_id FROM documents WHERE event_id = ?', (event,)))
    c.close()
    return out


def test_the_wrong_places_documents_go_and_the_right_places_come(stores):
    ev, en, md, tmp = stores
    out = str(tmp / 'out.sqlite')
    rep = R.run(ev, out, en, md, None, None, undated='drop', apply=True, resolve=Resolver(), log=lambda *a: None)
    # 'wrong' is linked to Akriai only: removed. 'hero_and_wrong' is also linked to a participant: kept.
    assert rows(out, 'E1') == ['hero_and_wrong', 'right']
    # E2 resolves the same by label and by id (no id): untouched, though its row is linked to another entity
    assert rows(out, 'E2') == ['wrong']
    assert (rep['rows_removed'], rep['rows_added'], rep['changed']) == (1, 1, 1)
    c = sqlite3.connect(out)
    assert c.execute('SELECT COUNT(*) FROM requests').fetchone()[0] == 1
    assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    # the input is never modified
    assert rows(ev, 'E1') == ['hero_and_wrong', 'wrong']


def test_a_dry_run_writes_nothing_and_remove_only_adds_nothing(stores):
    ev, en, md, tmp = stores
    out = str(tmp / 'out.sqlite')
    rep = R.run(ev, out, en, md, None, None, undated='drop', apply=False, resolve=Resolver(), log=lambda *a: None)
    assert not os.path.exists(out)
    assert (rep['rows_removed'], rep['rows_added']) == (1, 1)
    R.run(ev, out, en, md, None, None, apply=True, resolve=Resolver(), log=lambda *a: None, remove_only=True)
    assert rows(out, 'E1') == ['hero_and_wrong']


def test_the_run_stops_when_more_rows_would_go_than_allowed(stores):
    ev, en, md, tmp = stores
    with pytest.raises(SystemExit):
        R.run(ev, str(tmp / 'o.sqlite'), en, md, None, None, max_removals=0, apply=True, resolve=Resolver(),
              log=lambda *a: None)
    assert not os.path.exists(str(tmp / 'o.sqlite'))


def test_a_path_under_var_www_is_refused(stores):
    ev, en, md, tmp = stores
    with pytest.raises(SystemExit):
        R.run(ev, '/var/www/x.sqlite', en, md, None, None, resolve=Resolver(), log=lambda *a: None)
