"""Mentions stage 3a: display labels for corpus names, the gateway judgment, promotion, merging
into a list entity, a split key, and the routes that show them. A fixture store from the real
schema, no live index and no gateway."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend import entity_extras as extras  # noqa: E402
from backend import entity_index as ei  # noqa: E402
from backend import entity_promote as pr  # noqa: E402
from backend import passage_index  # noqa: E402
from backend import window_texts  # noqa: E402
from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import entities as ent  # noqa: E402

P = f'{API_PREFIX}/entities' if API_PREFIX else '/entities'


def test_the_heading_is_latin_script_nominative_and_mixed_case():
    forms = {'SARPEDON': 2, 'Sarpedon': 33, 'Sarpedona': 35, 'Sarpedonis': 33, 'Σαρπηδόνα': 49, 'Σαρπηδών': 13,
             'Σαρπηδὼν': 25}
    assert pr.display_labels(forms) == ('Sarpedon', 'Sarpedon', 'Σαρπηδών')     # the grave form counts as the acute
    assert pr.display_labels({'Σαρπηδόνα': 49, 'Σαρπηδών': 13}) == ('Σαρπηδών', None, 'Σαρπηδών')    # Greek only
    assert pr.display_labels({'CAIUS': 9, 'Caio': 3})[0] == 'Caio'                                  # mixed case wins
    assert pr.display_labels({'CAIUS': 9})[0] == 'Caius'                                            # only capitals
    assert pr.display_labels({'dido': 4})[0] == 'Dido'
    assert pr.display_labels({'Iolen': 21, 'Iolenses': 1})[0] == 'Iolen'          # frequency outweighs a lone nominative-looking ending
    assert pr.display_labels({}) == (None, None, None)


def test_a_reply_is_read_into_a_judgment_or_refused():
    spell = ['Sarpedon', 'Sarpedonius', 'Σαρπηδών']
    ok = pr.parse_judgment('```json\n{"type": "person", "latin": "Sarpedon", "greek": "Σαρπηδών", '
                           '"description": "Lycian prince killed at Troy by Patroclus.", "distinct_names": true, '
                           '"main_forms": ["Sarpedon", "Σαρπηδών", "not listed"]}\n```', spell)
    assert ok['type'] == 'person' and ok['distinct_names'] is True and ok['main_forms'] == ['Sarpedon', 'Σαρπηδών']
    # a split with no listed main form is no split
    assert pr.parse_judgment('{"type": "place", "latin": "Troy", "distinct_names": true, "main_forms": ["x"]}',
                             spell)['distinct_names'] is False
    assert pr.parse_judgment('{"type": "person", "latin": ""}', spell) is None       # a name with no label
    assert pr.parse_judgment('{"type": "other", "latin": ""}', spell)['type'] == 'other'
    assert pr.parse_judgment('{"type": "animal", "latin": "x"}', spell) is None
    assert pr.parse_judgment('no json here', spell) is None
    assert pr.parse_judgment(None, spell) is None


def _build(path):
    db = sqlite3.connect(path)
    db.executescript(ei.SCHEMA)
    for col in ('line_ref', 'form_key'):
        db.execute(f'alter table mention_rows add column {col} TEXT')
    db.executemany('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)', [
        (1, 'ln:E1', 'place', 'Troy', 'list', None, None, None, None, None, 1, 0),
        (2, 'ln:E2', 'person', 'Hector', 'list', None, None, None, None, None, 1, 0),
        (10, 'nm:sarpe', 'name', 'Σαρπηδόνα', 'names', None, None, None, None, 'sarpe', 0, 0),
        (11, 'nm:troia', 'name', 'Troia', 'names', None, None, None, None, 'troia', 0, 0),
        (12, 'nm:gaiu', 'name', 'GAIVS', 'names', None, None, None, None, 'gaiu', 0, 0),
        (13, 'nm:sabin', 'name', 'Sabini', 'names', None, None, None, None, 'sabin', 0, 0)])
    var = [(1, 'troia', 'la', 'form', 'list'), (2, 'hector', 'la', 'form', 'list'),
           (10, 'sarpedon', '', 'form', 'names'), (10, 'sarpedona', '', 'form', 'names'),
           (10, 'σαρπηδων', '', 'form', 'names'), (10, 'sarpedonius', '', 'form', 'names'),
           (11, 'troia', '', 'form', 'names'), (12, 'gaiuus', '', 'form', 'names'),
           (13, 'sabini', '', 'form', 'names')]
    db.executemany('insert into variants values (?,?,?,?,?)', var)
    rows = []       # (eid, wid, form)
    wins = []
    wid = 0
    for eid, form, n in ((10, 'Sarpedon', 3), (10, 'Sarpedona', 2), (10, 'Σαρπηδών', 2), (10, 'Sarpedonius', 2),
                         (11, 'Troia', 4), (12, 'GAIVS', 2), (13, 'Sabini', 3), (1, 'Troia', 1)):
        for i in range(n):
            wid += 1
            work = f'w{(wid % 3) + 1}.text'
            wins.append((wid, f'{work}:{wid}', work, f'{wid}.1', f'{wid}.1', 'la'))
            rows.append((eid, wid, form, 1, 0, 0, 'lemma', 'lemma', 0, f'{wid}.1', ei.fold(form)))
    db.executemany('insert into windows values (?,?,?,?,?,?)', wins)
    db.executemany('insert into mention_rows values (?,?,?,?,?,?,?,?,?,?,?)', rows)
    db.commit()
    return db


JUDGMENTS = {
    'sarpe': {'type': 'person', 'latin': 'Sarpedon', 'greek': 'Σαρπηδών', 'description': 'Lycian prince killed at Troy.',
              'distinct_names': True, 'main_forms': ['Sarpedon', 'Sarpedona', 'Σαρπηδών']},
    'troia': {'type': 'place', 'latin': 'Troy', 'greek': 'Τροία', 'description': 'City in the Troad.',
              'distinct_names': False, 'main_forms': []},
    'gaiu': {'type': 'person', 'latin': 'Gaius', 'greek': '', 'description': 'A Roman forename.',
             'distinct_names': False, 'main_forms': []},
    'sabin': {'type': 'other', 'latin': '', 'greek': '', 'description': '', 'distinct_names': False, 'main_forms': []},
}


@pytest.fixture
def built(tmp_path):
    path = str(tmp_path / 'stage3a.sqlite')
    db = _build(path)
    pr.write_display_labels(db, log=lambda *_: None)
    rep = pr.promote_store(db, JUDGMENTS, log=lambda *_: None)
    db.commit()
    db.close()
    extras.write_catalog(path, log=lambda *_: None)
    return path, rep


def test_every_corpus_name_gets_a_proper_heading(tmp_path):
    db = _build(str(tmp_path / 's.sqlite'))
    changed = pr.write_display_labels(db, log=lambda *_: None)
    got = {eid: new for eid, _old, new in changed}
    assert got[10] == 'Sarpedon' and got[12] == 'Gaivs'
    assert db.execute('select display_label, display_label_la, display_label_grc from entity_labels where eid = 10'
                      ).fetchone() == ('Sarpedon', 'Sarpedon', 'Σαρπηδών')
    assert db.execute('select label from entities where eid = 10').fetchone()[0] == 'Sarpedon'


def test_promotion_counts_a_merge_and_a_split(built):
    path, rep = built
    assert (rep['promoted'], rep['merged'], rep['split_promoted']) == (2, 1, 1)
    assert rep['by_type'] == {'person': 2}
    db = sqlite3.connect(path)
    # Troy merged into the list entity: the promoted id is its alias, its own mentions are untouched,
    # and the corpus name stays, hidden from the search and attached to it
    assert {r[0] for r in db.execute('select alias_id from entity_aliases where eid = 1')} == {'pn:troia'}
    assert db.execute('select count(*) from mention_rows where eid = 1').fetchone()[0] == 1
    assert db.execute('select list_eid from entity_merges where eid = 11').fetchone() == (1,)
    assert db.execute("select source from entities where entity_id = 'nm:troia'").fetchone() == ('names',)
    # Gaius promoted in place, the old id kept as an alias
    assert db.execute("select eid, type, source from entities where entity_id = 'pn:gaiu'").fetchone() == (12, 'person', 'promoted')
    assert db.execute("select alias_id from entity_aliases where eid = 12").fetchall() == [('nm:gaiu',)]
    # the split: the main name moved to a new entity, Sarpedonius stays a plain corpus name
    new = db.execute("select eid, source from entities where entity_id = 'pn:sarpe'").fetchone()
    assert new[1] == 'promoted' and new[0] != 10
    assert db.execute('select count(*) from mention_rows where eid = ?', (new[0],)).fetchone()[0] == 7
    assert db.execute('select source, label from entities where eid = 10').fetchone() == ('names', 'Sarpedonius')
    assert db.execute('select count(*) from mention_rows where eid = 10').fetchone()[0] == 2
    # a name judged other is left alone
    assert db.execute("select source from entities where entity_id = 'nm:sabin'").fetchone() == ('names',)


@pytest.fixture
def client(built, monkeypatch):
    path, _rep = built
    monkeypatch.setenv('TESSERAE_ENTITY_STORE', path)
    ent._cache.clear()
    monkeypatch.setattr(window_texts, 'texts_for', lambda ids: {})
    monkeypatch.setattr(passage_index, '_naming', lambda w: {'title': w, 'author': 'A'})
    monkeypatch.setattr(passage_index, '_short_locus_fields', lambda w, a, b: {'locus': a})
    return app.test_client()


def test_a_promoted_entity_ranks_with_the_list_and_ahead_of_plain_names(client):
    r = client.get(f'{P}/search?q=sarpedon').get_json()
    assert [(x['id'], x['source']) for x in r['results']] == [('pn:sarpe', 'promoted'), ('nm:sarpe', 'corpus')]
    top = r['results'][0]
    assert top['type'] == 'person' and top['label'] == 'Sarpedon' and top['display_label_grc'] == 'Σαρπηδών'
    assert top['description'] == 'Lycian prince killed at Troy.'
    assert top['provenance'] == 'Named in the corpus, identified by a language model'
    assert r['results'][1]['label'] == 'Sarpedonius' and 'provenance' not in r['results'][1]
    # a list entity and a promoted one share the first group, sorted by rank and size
    r = client.get(f'{P}/search?q=ga').get_json()
    assert [x['id'] for x in r['results']] == ['pn:gaiu']


def test_the_heading_fields_come_with_every_source(client):
    promoted = client.get(f'{P}/pn:gaiu').get_json()
    assert promoted['display_label'] == 'Gaius' and promoted['display_label_grc'] is None
    assert promoted['identifiers']['also_listed_as'] == ['nm:gaiu']
    assert client.get(f'{P}/nm:gaiu').get_json()['id'] == 'pn:gaiu'                    # the old id still opens
    plain = client.get(f'{P}/nm:sarpe').get_json()
    assert plain['display_label'] == 'Sarpedonius' and plain['source'] == 'corpus' and plain['display_label_grc'] is None
    listed = client.get(f'{P}/ln:E1').get_json()                      # Troy keeps its own mentions
    assert listed['display_label'] == 'Troy' and listed['mentions_total'] == 1 and listed['source'] == 'list'
    assert [(n['id'], n['mentions_total']) for n in listed['corpus_names']] == [('nm:troia', 4)]
    assert client.get(f'{P}/pn:troia').get_json()['id'] == 'ln:E1'
    assert [x['id'] for x in client.get(f'{P}/search?q=troia').get_json()['results']] == ['ln:E1']


def test_an_older_store_without_labels_still_answers(tmp_path, monkeypatch):
    path = str(tmp_path / 'old.sqlite')
    db = _build(path)
    db.commit()
    db.close()
    monkeypatch.setenv('TESSERAE_ENTITY_STORE', path)
    ent._cache.clear()
    r = app.test_client().get(f'{P}/search?q=sarpedon').get_json()
    assert r['results'][0]['display_label'] == 'Σαρπηδόνα' and r['results'][0]['display_label_grc'] is None
