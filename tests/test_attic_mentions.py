"""The Attic matcher (backend/attic_mentions.py, backend/attic_demes.py), the two faults of the documents
builder it needed fixed (promoted entities in the name index, a missing name string), and the rule that
the builder can produce candidate rows for one collection without touching the table. Fixtures only."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend import attic_demes as demes  # noqa: E402
from backend import attic_mentions as am  # noqa: E402
from backend import entity_extras as extras  # noqa: E402
from backend import entity_index as ei  # noqa: E402


def ent(eid, entity_id, typ, label, source, grc=(), blank=()):
    return {'eid': eid, 'id': entity_id, 'type': typ, 'label': label, 'source': source,
            'forms': {'la': set(), 'grc': set(grc), 'en': set(), '': set(blank)}}


@pytest.fixture
def world():
    ents = {e['eid']: e for e in [
        ent(1, 'ln:E0279', 'place', 'Apollonia', 'list', ['απολλωνια']),
        ent(2, 'ln:E0278', 'deity', 'Apollo/Phoebus', 'list', ['απολλων']),
        ent(3, 'ln:E0052', 'place', 'Athens', 'list', ['αθηναι']),
        ent(4, 'ln:E0051', 'deity', 'Athena/Minerva', 'list', ['αθηνα']),
        ent(5, 'pl:580021', 'place', 'Marathon', 'list', ['μαραθων']),
        ent(6, 'pn:diotim', 'person', 'Diotima', 'promoted', blank=['διοτιμα']),
        ent(7, 'ln:E0582', 'deity', 'Zeus/Jupiter', 'list', ['ζευσ']),
        ent(8, 'ln:E0335', 'person', 'Asclepius', 'list', ['ασκληπιοσ']),
        ent(9, 'pn:mounu', 'place', 'Munychia', 'promoted', blank=['μουνιχιωνοσ', 'μουνιχια']),
        ent(10, 'pn:αχαρν2', 'place', 'Acharnae', 'promoted', blank=['αχαρναι']),
        ent(11, 'ln:E9001', 'person', 'Themistocles', 'list', ['θεμιστοκλησ']),
        ent(12, 'ln:E9002', 'person', 'Alexander', 'list', ['αλεξανδροσ']),
        ent(13, 'pn:αθηναι', 'people', 'Athenians', 'promoted', blank=['αθηναιων', 'αθηναιοι']),
        ent(14, 'nm:dios', 'name', 'Dios', 'names', blank=['διοσ']),
        ent(15, 'ln:E9003', 'place', 'Eurymedon', 'list', ['ευρυμεδων']),
        ent(16, 'ln:E1129', 'place', 'Peiraieus/Piraeus', 'list', ['πειραιευσ']),
    ]}
    labels = {11: 'Athenian archon of 493/2, statesman'}
    exact, stems, _n = extras.build_maps(ents, log=lambda *a: None)
    return am.AtticMatcher(ents, exact, stems, labels)


def kept(world, text):
    occ, unlinked = world.read_document(text)
    rows, _drops = am.aggregate(occ)
    return {world.ents[e]['id'] for e in rows}, occ, unlinked


# ---- the builder -----------------------------------------------------------

def make_store(tmp_path):
    path = str(tmp_path / 'entities.sqlite')
    db = sqlite3.connect(path)
    db.executescript(ei.SCHEMA)
    db.executemany('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)', [
        (10, 'ln:E1', 'place', 'Athens', 'list', None, None, None, None, None, 1, 0),
        (20, 'pn:aaron', 'person', 'Aaron', 'promoted', None, None, None, None, None, 1, 0),
        (21, 'pn:empty', 'person', 'Nobody', 'promoted', None, None, None, None, None, 1, 0),
        (22, 'nm:zeus', 'name', 'Zeusx', 'names', None, None, None, None, None, 1, 0)])
    db.executemany('insert into variants values (?,?,?,?,?)', [
        (10, 'αθηναι', 'grc', 'form', 'list'), (20, 'ααρων', '', 'form', 'promoted'), (22, 'zeusx', '', 'form', 'names')])
    db.execute("insert into meta values ('document_mentions', '{}')")
    db.executescript(extras.DOC_SCHEMA)
    db.execute("insert into document_mentions values (10, 'edr:OLD', 'grc', 'αθηναι', 'form', 0)")
    db.commit()
    db.close()
    return path


def make_documents(tmp_path):
    d = tmp_path / 'docs'
    d.mkdir()
    c = sqlite3.connect(str(d / 'grc_documents_index.db'))
    c.executescript('''
      create table texts (text_id integer primary key, filename text unique, author text, title text, line_count integer);
      create table lines (text_id integer, ref text, content text, lemmas text, tokens text, primary key (text_id, ref));
    ''')
    c.execute("insert into texts values (1, 'x.tess', 'x', 'X', 2)")
    for ref, toks in (('aio:A1', ['Ἀθῆναι', 'Ἀαρών']), ('edr:B1', ['Ἀθῆναι'])):
        c.execute('insert into lines values (1, ?, ?, ?, ?)', (ref, ' '.join(toks), '[]', json.dumps(toks)))
    c.commit()
    c.close()
    return str(d)


def test_a_promoted_entity_is_in_the_name_index_and_a_missing_name_string_is_skipped(tmp_path):
    db = sqlite3.connect(make_store(tmp_path))
    ents = extras._load_entities(db)
    index, name_strings, _dup = extras._name_index_and_excluded(ents)
    assert 20 in name_strings and 22 in name_strings           # promoted and names
    assert 10 not in name_strings                               # a list entity is not a name
    ents[21]['forms'][''].clear()
    ents[999] = ent(999, 'pn:ghost', 'person', 'Ghost', 'promoted')
    exact, _stems, _n = extras.build_maps(ents, log=lambda *a: None)    # the KeyError of 2026-10-20
    assert any(e[0] == 20 for e in exact['grc'].get('ααρων', []))


def test_candidate_rows_for_one_collection_leave_the_table_alone(tmp_path):
    store = make_store(tmp_path)
    docs = make_documents(tmp_path)
    before = sqlite3.connect(store).execute('select * from document_mentions').fetchall()
    rows = []
    counts = extras.build_document_mentions(store, docs, log=lambda *a: None, doc_prefix='aio:', rows_out=rows)
    assert {r[1] for r in rows} == {'aio:A1'}                    # nothing of edr:B1
    assert any(r[0] == 20 for r in rows) and any(r[0] == 10 for r in rows)
    assert counts['candidate_rows'] == len(rows)
    db = sqlite3.connect(store)
    assert db.execute('select * from document_mentions').fetchall() == before
    assert db.execute("select count(*) from sqlite_master where name = 'ix_dm_eid'").fetchone()[0] == 0
    with pytest.raises(ValueError):
        extras.build_document_mentions(store, docs, log=lambda *a: None, doc_prefix='aio:')


def test_the_whole_table_build_still_reads_every_document(tmp_path):
    store = make_store(tmp_path)
    docs = make_documents(tmp_path)
    counts = extras.build_document_mentions(store, docs, log=lambda *a: None)
    assert counts['documents_scanned_grc'] == 2
    docs_in_table = {r[0] for r in sqlite3.connect(store).execute('select doc_id from document_mentions')}
    assert docs_in_table == {'aio:A1', 'edr:B1'}


# ---- the words and their places --------------------------------------------

def test_words_keep_capitals_and_the_stone_line():
    ws = am.words('ἐπ’ Εὐβολίδο ἄρχοντος · / ἔδοξεν τῆι βολῆι')
    assert [w[0] for w in ws][:3] == ['ἐπ', 'Εὐβολίδο', 'ἄρχοντος']
    assert ws[0][2] == 0 and ws[-1][2] == 1
    assert am.capitalized('Ἀθηναίων') and not am.capitalized('ἀθηναίων') and am.capitalized('ΑΘΗΝΑ')


def test_archon_context_marks_the_name_between_epi_and_archontos_and_after_it():
    ws = am.words('ἐπὶ Διοτίμου ἄρχοντος ἔδοξεν')
    assert am.archon_context(ws, 1) and not am.archon_context(ws, 3)
    ws = am.words('ἐπὶ ἄρχοντος Λουκίου Ῥαμνουσίου ἔδοξεν')
    assert am.archon_context(ws, 2) and not am.archon_context(ws, 4)
    ws = am.words('Διοτίμου υἱός ἄρχοντος')
    assert not am.archon_context(ws, 0)


def test_patronymic_is_a_capitalized_genitive_after_a_capitalized_name():
    ws = am.words('Κλεάνθης Σωκράτους καὶ Λυσίας τοῦ Νικίου')
    assert am.is_patronymic(ws, 1) and am.is_patronymic(ws, 5)
    assert not am.is_patronymic(ws, 0) and not am.is_patronymic(am.words('ἱερεὺς Ἀθηνᾶς'), 1)
    assert am.patronymic_follows(am.words('Εὐρυμέδων Ἡγεμάχου'), 0)


def test_masculine_name_forms_and_feminine_place_names():
    for f in ('απολλωνιοσ', 'απολλωνιου', 'διονυσιασ', 'ερμαιοσ'):
        assert am.masculine_name_form(f)
    assert not am.masculine_name_form('αθηναιοσ') and not am.masculine_name_form('αθηναιων')
    assert am.feminine_or_neuter_place('Apollonia', ['απολλωνια']) and not am.feminine_or_neuter_place('Peiraieus', ['πειραιευσ'])


def test_months_are_recognized_in_every_case():
    for f in ('μουνιχιωνοσ', 'ποσειδεωνοσ', 'θαργηλιωνοσ', 'μεταγειτνιωνι', 'εκατομβαιων'):
        assert am.is_month(f)
    assert not am.is_month('ποσειδωνοσ') and not am.is_month('μουνιχια')


def test_athenai_and_athenas_are_read_from_the_accent():
    assert am.athena_or_athens('Ἀθῆναι') == 'athens' and am.athena_or_athens('Ἀθήνας') == 'athens'
    assert am.athena_or_athens('Ἀθηνᾶι') == 'athena' and am.athena_or_athens('Ἀθηνᾶς') == 'athena'
    assert am.athena_or_athens('ΑΘΗΝΑΙ') is None


# ---- the demes -------------------------------------------------------------

def test_demotics_have_no_clash_and_cover_the_cases():
    assert demes.demotic_clashes() == []
    table = demes.demotic_table()
    for f in ('σφηττιοσ', 'σφηττιου', 'φρεαρριοσ', 'παιανιευσ', 'παιανιεωσ', 'αλωπεκηθεν', 'ξυπεταιων', 'οηθεν', 'αχαρνεωσ'):
        assert f in table
    assert table['φρεαρριοσ'] == 'Phrearrhioi' and table['πειραιευσ'] == 'Piraeus'
    assert set(am.DEME_ENTITIES) <= {d[0] for d in demes.DEMES}


# ---- each rule on a document -----------------------------------------------

def test_masculine_personal_name_is_not_a_feminine_place(world):
    rows, occ, _ = kept(world, 'Ἀπολλώνιος ἀνέθηκεν')
    assert 'ln:E0279' not in rows
    assert any(o[5] == 'masculine_name' for o in occ)
    rows, _, _ = kept(world, 'Ἀπολλωνία ἀνέθηκεν')                     # the place itself is kept
    assert 'ln:E0279' in rows


def test_a_demotic_links_to_its_deme_and_not_to_a_person(world):
    rows, occ, _ = kept(world, 'Λυσίας Ἀχαρνεύς')
    assert 'pn:αχαρν2' in rows
    rows, occ, _ = kept(world, 'Ἀπολλόδωρος Μαραθώνιος')
    assert 'pl:580021' in rows
    rows, occ, _ = kept(world, 'Σφήττιος ἀνέθηκεν')                    # a demotic of a deme with no entity: no row
    assert not rows


def test_an_archon_name_is_unlinked_unless_the_entity_is_that_archon(world):
    rows, _occ, unlinked = kept(world, 'ἐπὶ Ἀλέξανδρος ἄρχοντος')
    assert 'ln:E9002' not in rows and unlinked == 1
    rows, _occ, _ = kept(world, 'ἐπὶ Θεμιστοκλῆς ἄρχοντος')
    assert 'ln:E9001' in rows                                           # its description names the archonship
    rows, _occ, _ = kept(world, 'Θεμιστοκλῆς εἶπεν')                      # not in an archon date: a person, unlinked
    assert 'ln:E9001' not in rows


def test_a_god_in_a_dedication_links_to_the_god_only(world):
    rows, _, _ = kept(world, 'Διὸς Σωτῆρος')
    assert rows == {'ln:E0582'}                                         # not the name entity Dios
    rows, _, _ = kept(world, 'Ἀπόλλωνι ἀνέθηκεν')
    assert rows == {'ln:E0278'}                                         # not Apollonia
    rows, _, _ = kept(world, 'Ἀσκληπιῷ')
    assert rows == {'ln:E0335'}                                         # the god, though the store types it person


def test_the_nominative_of_a_god_who_is_also_a_name_is_not_a_god(world):
    rows, _, _ = kept(world, 'Ἀσκληπιός Ἀπολλόδωρος')
    assert 'ln:E0335' not in rows


def test_athena_and_athens_are_told_apart_by_the_accent(world):
    assert kept(world, 'ἐν Ἀθήναις')[0] == {'ln:E0052'}
    assert kept(world, 'ἐς Ἀθήνας')[0] == {'ln:E0052'}
    assert kept(world, 'τῆς Ἀθηνᾶς')[0] == {'ln:E0051'}
    rows, occ, _ = kept(world, 'ΑΘΗΝΑΣ')
    assert rows == set() and any(o[5] == 'athena_or_athens' for o in occ)


def test_a_patronymic_and_a_name_with_a_father_are_unlinked(world):
    assert 'ln:E9003' not in kept(world, 'Εὐρυμέδων Ἡγεμάχου')[0]
    assert 'ln:E9003' in kept(world, 'ὁ ποταμὸς Εὐρυμέδων')[0]


def test_a_month_is_not_the_harbor(world):
    rows, occ, _ = kept(world, 'Μουνιχιῶνος ἕκτηι')
    assert 'pn:mounu' not in rows and any(o[5] == 'month' for o in occ)


def test_a_person_is_not_linked_and_a_name_entity_is_not_a_link(world):
    rows, occ, _ = kept(world, 'Ἀλέξανδρος Ἀλεξάνδρου')
    assert rows == set()
    assert any(o[5] in ('person', 'patronymic') for o in occ)
    assert 'nm:dios' not in kept(world, 'Δῖος')[0]


def test_a_proper_name_needs_its_capital_and_a_people_its_stored_spelling(world):
    assert 'pn:αθηναι' in kept(world, 'τοῦ δήμου τοῦ Ἀθηναίων')[0]
    assert 'pn:αθηναι' not in kept(world, 'τοῦ δήμου τοῦ ἀθηναίων')[0]


def test_the_row_keeps_the_best_surviving_occurrence(world):
    occ, _ = world.read_document('ἐς Ἀθήνας καὶ ἐν Ἀθήναις')
    rows, drops = am.aggregate(occ)
    eid = world.athens
    assert eid in rows and rows[eid][4] in (1, 4)
    assert max(drops[eid]) == len(am.RULES)
