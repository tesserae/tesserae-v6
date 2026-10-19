"""Entity mentions, merge pass 4d: layer 1 (stems) on the split-sample keys. The WRONG keys are the 11 carves
the lead read as one referent in two (2026-10-19), the RIGHT keys carves that separate different referents.
Fixtures are the headings, listed spellings and mention-row counts of the stage 4c store."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import entity_mergeback as mb  # noqa: E402


# ---------------------------------------------------------------- the WRONG keys layer 1 merges

def test_nerea_is_a_case_form_of_nereus():
    assert mb.same_stem(['Nereus', 'Νηρεύς'], {'Nerea': 23}, 'person', 'place')


def test_tyrians_are_the_tyrii_in_greek_and_latin():
    forms = {'Τυρίου': 79, 'Τυρίων': 69, 'Τύριοι': 40, 'Τύριον': 34, 'Τυρίῳ': 24, 'Τυρίοις': 20, 'Τύριος': 14}
    assert mb.same_stem(['Tyrii', 'Τύριοι'], forms, 'people', 'people', ['tyrio', 'tyrios', 'tyrii', 'tyriis'])


def test_madian_is_the_land_of_the_midianites_the_parent_already_lists():
    assert mb.same_stem(['Midianites', 'Μαδιάμ'], {'Madian': 99}, 'people', 'people', ['madiae', 'madianitis', 'midian'])


def test_chaonians_are_the_chaones():
    forms = {'Chaonias': 8, 'Chaonio': 8, 'Chaonios': 4, 'CHAONIAS': 2}
    assert mb.same_stem(['Chaones', 'Χάονες'], forms, 'people', 'people', ['chaoniam', 'χαονων', 'chaones'])


# ---------------------------------------------------------------- the WRONG keys left to the model

def test_the_cases_for_the_model_are_not_merged_by_layer_1():
    # Ephesius beside the Ephesians, Gordyene beside the Gordyaei, Parasius the painter beside the place Parrhasius
    assert not mb.same_stem(['Ephesians', 'Ἐφέσιοι'], {'Ephesium': 12, 'Ephesiam': 1}, 'people', 'person',
                            ['ephesiorum', 'εφεσιοι'])
    assert not mb.same_stem(['Gordyaei', 'Γορδυαῖοι'], {'Γορδυηνὴν': 3, 'Γορδυηνῆς': 3, 'Γορδυηνῶν': 2}, 'people', 'place')
    assert not mb.same_stem(['Parrhasius'], {'Παρράσιος': 17, 'Παρράσιον': 11}, 'place', 'person')


def test_the_cue_for_the_model_finds_the_parents_own_name_among_the_carved_spellings():
    assert mb.case_form_of('Iberiam', ['Iberia']) is not None
    assert mb.case_form_of('Iberiae', ['Iberia']) is not None
    assert mb.case_form_of('Iberi', ['Iberia']) is None
    assert mb.case_form_of('Ephesium', ['Ephesians']) is None


# ---------------------------------------------------------------- RIGHT keys that must stay apart

def test_ten_right_carves_are_not_merged():
    pairs = [
        (['Atalanta'], {'Atalaricus': 40, 'Atalarici': 9}, 'person', 'person'),
        (['Sidon', 'Σιδών'], {'Sidonii': 30, 'Sidoniorum': 10, 'Σιδωνίων': 20}, 'place', 'people'),
        (['Fidenae'], {'Fidenates': 22, 'Fidenatium': 4}, 'place', 'people'),
        (['Thebes', 'Θῆβαι'], {'Thebani': 50, 'Thebanorum': 20, 'Θηβαῖοι': 70}, 'place', 'people'),
        (['Philip', 'Φίλιππος'], {'Philippenses': 11, 'Philippensium': 3}, 'person', 'people'),
        (['Arpinum'], {'Arpinates': 15, 'Arpinatium': 3}, 'place', 'people'),
        (['Valerius'], {'Valens': 40, 'Valentis': 12}, 'person', 'person'),
        (['Julius'], {'Julia': 60, 'Juliae': 20}, 'person', 'person'),
        (['Alcathous'], {'Alcathoe': 9, 'Alcathoen': 2}, 'person', 'place'),
        (['Papia'], {'Papias': 12, 'Papiae': 1}, 'place', 'person'),
        (['Polycrates', 'Πολυκράτης'], {'Πολυκλείτου': 30, 'Πολύκλειτος': 40}, 'person', 'person'),
    ]
    for heads, forms, pt, ct in pairs:
        assert not mb.same_stem(heads, forms, pt, ct), heads


def test_a_stem_of_three_letters_matches_only_between_two_peoples():
    assert not mb.same_stem(['Titus'], {'Titans': 30}, 'person', 'people')
    assert not mb.same_stem(['Tyre'], {'Tyrians': 30, 'Tyrii': 20}, 'place', 'people')


def test_a_latin_oe_is_not_the_greek_plural():
    assert mb.case_form_of('Alcathoe', ['Alcathous']) is None
    assert mb.case_form_of('Spartan', ['Sparta']) is None
    assert mb.case_form_of('Spartam', ['Sparta']) is not None
    assert mb.case_form_of('Φωκαιεῖς', ['Φώκαια']) is None
    assert mb.case_form_of('Φωκαίας', ['Φώκαια']) is not None


# ---------------------------------------------------------------- the kind veto

def test_a_place_and_its_inhabitants_are_vetoed_without_a_shared_case_form():
    place = {'label': 'Fidenae', 'type': 'place', 'forms': [('Fidenae', 5)]}
    people = {'label': 'Fidenates', 'type': 'people', 'forms': [('Fidenates', 22)]}
    assert mb.kind_veto(place, people)
    own = {'label': 'Iberi', 'type': 'people', 'forms': [('Iberi', 11), ('Iberis', 7), ('Iberia', 3), ('Iberiam', 2), ('Iberiae', 1)]}
    assert not mb.kind_veto({'label': 'Iberia', 'type': 'place', 'forms': []}, own)
    spartans = {'label': 'Spartans', 'type': 'people', 'forms': [('Spartanorum', 23), ('Spartani', 21), ('Spartan', 6)]}
    assert mb.kind_veto({'label': 'Sparta', 'type': 'place', 'forms': []}, spartans)
    assert not mb.kind_veto(place, {'label': 'Fidenae', 'type': 'place', 'forms': [('Fidenae', 1)]})


# ---------------------------------------------------------------- the answer

def test_parse_answer():
    assert mb.parse_answer('{"answer": "SAME", "reason": "x"}') == ('SAME', 'x')
    assert mb.parse_answer('{"answer": "different"}')[0] == 'DIFFERENT'
    assert mb.parse_answer('no json')[0] is None
    assert mb.parse_answer('{"answer": "MAYBE"}')[0] is None


# ---------------------------------------------------------------- the merge itself

SCHEMA = '''
CREATE TABLE entities (eid INTEGER PRIMARY KEY, entity_id TEXT UNIQUE, type TEXT, label TEXT, source TEXT,
  pleiades_id TEXT, pleiades_candidates TEXT, prosopography_id TEXT, homonym_group TEXT, name_key TEXT,
  distinctive INTEGER, n_windows INTEGER);
CREATE TABLE variants (eid INTEGER, form TEXT, language TEXT, role TEXT, source TEXT);
CREATE TABLE mention_rows (eid INTEGER, wid INTEGER, form TEXT, cap INTEGER, nb INTEGER, ds INTEGER, confidence TEXT,
  matcher TEXT, homonym INTEGER, line_ref TEXT, form_key TEXT);
CREATE TABLE entity_aliases (eid INTEGER, alias_id TEXT, label TEXT, type TEXT, rule TEXT);
CREATE TABLE entity_labels (eid INTEGER PRIMARY KEY, display_label TEXT, display_label_la TEXT, display_label_grc TEXT,
  description TEXT);
CREATE TABLE entity_merges (eid INTEGER PRIMARY KEY, list_eid INTEGER);
CREATE TABLE search_names (eid INTEGER, name TEXT, source TEXT);
'''


def _store():
    db = sqlite3.connect(':memory:')
    db.executescript(SCHEMA)
    db.executemany('insert into entities (eid, entity_id, type, label, source, homonym_group, n_windows) values (?,?,?,?,?,?,0)',
                   [(1, 'pn:nereo', 'person', 'Nereus', 'promoted', None), (2, 'pn:nere2', 'place', 'Nerea', 'promoted', 'collision')])
    db.executemany('insert into mention_rows (eid, wid, form, form_key) values (?,?,?,?)',
                   [(1, 1, 'Nereus', 'nereus'), (1, 2, 'Nereo', 'nereo'), (2, 2, 'Nerea', 'nerea'), (2, 3, 'Nerea', 'nerea'),
                    (2, 1, 'Nereus', 'nereus')])
    db.executemany('insert into variants values (?,?,?,?,?)', [(1, 'nereus', 'la', 'form', 'x'), (2, 'nerea', 'la', 'form', 'x')])
    db.execute("insert into entity_labels values (2, 'Nerea', 'Nerea', NULL, 'a place')")
    db.execute("insert into search_names values (2, 'Nerea sea', 'model')")
    return db


def test_apply_merge_moves_rows_spellings_names_and_keeps_the_parent():
    db = _store()
    r = mb.apply_merge(db, 2, 1, 'merge4d_stem')
    assert r == {'moved': 2, 'dropped': 1, 'forms': 1}
    assert db.execute('select count(*) from entities').fetchone()[0] == 1
    assert db.execute('select count(*) from mention_rows where eid = 1').fetchone()[0] == 4
    assert db.execute('select count(*) from mention_rows where eid = 2').fetchone()[0] == 0
    assert {f for (f,) in db.execute('select form from variants where eid = 1')} == {'nereus', 'nerea'}
    assert db.execute('select label from entities where eid = 1').fetchone()[0] == 'Nereus'
    assert db.execute("select alias_id, rule from entity_aliases where eid = 1").fetchall() == [('pn:nere2', 'merge4d_stem')]
    assert db.execute("select name from search_names where eid = 1").fetchall() == [('Nerea sea',)]
    assert db.execute('select n_windows from entities where eid = 1').fetchone()[0] == 3


def test_apply_partial_moves_only_the_named_spellings_and_keeps_the_host():
    db = _store()
    db.execute("update entities set homonym_group = NULL where eid = 2")
    r = mb.apply_partial(db, 2, 1, {'Nerea'})
    assert r['moved'] == 2 and r['dropped'] == 0
    assert db.execute('select count(*) from entities').fetchone()[0] == 2
    assert [f for (f,) in db.execute('select form from mention_rows where eid = 2')] == ['Nereus']
