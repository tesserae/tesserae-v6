"""Mentions stage 4: the heading rule for place entities, the stem test for key collisions, search names made
from the spellings, the Greek label of a split. A fixture store from the real schema, no live index and no
gateway."""
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


# ---------------------------------------------------------------- B. the heading rule for place entities

def test_a_demonym_ranks_below_every_place_name_form():
    forms = {'Massiliensium': 34, 'Massilienses': 23, 'Massilia': 3}
    assert pr.best_form(forms, 'latin') == 'Massiliensium'                 # a person or an untyped name: the old rule
    assert pr.best_form(forms, 'latin', place=True) == 'Massilia'          # a place: the demonyms rank below Massilia
    assert pr.best_form({'Massiliensium': 34, 'Massilienses': 23}, 'latin', place=True) == 'Massiliensium'   # nothing else to choose
    assert pr.best_form({'Atheniensis': 9, 'Athenae': 2}, 'latin', place=True) == 'Athenae'
    assert pr.is_demonym('Arpinates', 'latin') and pr.is_demonym('Hispani', 'latin') and not pr.is_demonym('Roma', 'latin')
    assert pr.best_form({'Ἀχαρνεῖς': 9, 'Ἀχαρναί': 2}, 'greek', place=True) == 'Ἀχαρναί'
    assert pr.best_form({'Ἀχαρνεῖς': 9, 'Ἀχαρναί': 2}, 'greek') == 'Ἀχαρνεῖς'
    assert pr.is_demonym('Ῥοδῖται', 'greek') and pr.is_demonym('Σικελιτῶν', 'greek') and not pr.is_demonym('Ῥόδος', 'greek')


def test_the_place_types_are_place_people_and_region_and_never_a_person():
    assert pr.PLACE_TYPES == ('place', 'people', 'region') and 'person' not in pr.PLACE_TYPES


def test_a_first_declension_oblique_heading_is_built_from_the_stem():
    forms = {'Massiliam': 55, 'Massiliae': 28, 'Massiliensium': 34, 'Massilienses': 23}
    assert pr.best_form(forms, 'latin', place=True) == 'Massilia'
    assert pr.best_form(forms, 'latin') == 'Massiliensium'
    # a nominative in -a that is attested is the heading as it stands
    assert pr.best_form({'Massilia': 2, 'Massiliam': 55}, 'latin', place=True) == 'Massilia'
    # -ae alone can be a plural nominative (Athenae), so nothing is built
    assert pr.best_form({'Athenae': 9, 'Atheniensis': 4}, 'latin', place=True) == 'Athenae'
    # another declension: the attested form is the heading
    assert pr.best_form({'Carthaginem': 20, 'Carthaginis': 18}, 'latin', place=True) == 'Carthaginis'
    # a form in -as is neither -am nor -ae: no build
    assert pr.best_form({'Massiliam': 5, 'Massilias': 4}, 'latin', place=True) == 'Massilias'


def test_a_place_group_label_prefers_a_place_name_to_a_demonym():
    assert pr.pick_group_label([('Massilienses', 90), ('Massilia', 10)], 'latin', place=True) == 'Massilia'
    assert pr.pick_group_label([('Massilienses', 90), ('Massilia', 10)], 'latin') == 'Massilienses'


def test_a_list_place_gets_its_greek_heading_by_the_place_rule(tmp_path):
    db = sqlite3.connect(str(tmp_path / 'l.sqlite'))
    db.executescript(ei.SCHEMA)
    db.executemany('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)', [
        (1, 'pl:1', 'place', 'Acharnae', 'list', None, None, None, None, None, 1, 0),
        (2, 'ln:2', 'person', 'Acharnes', 'list', None, None, None, None, None, 1, 0)])
    db.executemany('insert into windows values (?,?,?,?,?,?)', [(i, f'w:{i}', 'w.text', f'{i}.1', f'{i}.1', 'grc') for i in range(1, 30)])
    rows = [(1, i, 'Ἀχαρνεῖς', 1, 0, 0, 'lemma', 'lemma', 0) for i in range(1, 10)]
    rows += [(1, i, 'Ἀχαρναί', 1, 0, 0, 'lemma', 'lemma', 0) for i in range(10, 12)]
    rows += [(2, i, 'Ἀχαρνεῖς', 1, 0, 0, 'lemma', 'lemma', 0) for i in range(12, 21)]
    rows += [(2, i, 'Ἀχαρναί', 1, 0, 0, 'lemma', 'lemma', 0) for i in range(21, 23)]
    db.executemany('insert into mention_rows(eid, wid, form, cap, nb, ds, confidence, matcher, homonym) values (?,?,?,?,?,?,?,?,?)', rows)
    pr.write_display_labels(db, log=lambda *_: None)
    got = dict(db.execute('select eid, display_label_grc from entity_labels'))
    assert got == {1: 'Ἀχαρναί', 2: 'Ἀχαρνεῖς'}


# ---------------------------------------------------------------- C. the stem test for key collisions

def _rows(spec):
    """spec: {spelling: [(work, line), ...]} into the rows collision_groups reads."""
    return [(f, w, ln) for f, lines in spec.items() for w, ln in lines]


MASSI = {
    'Massiliam': [('caesar', str(i)) for i in range(1, 7)], 'Massiliae': [('lucan', str(i)) for i in range(1, 4)],
    'Massilienses': [('cicero', '1')],
    'Massinissa': [('livy', str(i)) for i in range(1, 6)], 'Massinissam': [('sallust', '1'), ('sallust', '2')],
    'Massicus': [('vergil', '1'), ('vergil', '2')],              # a group with two lines in one work: not qualifying
}


def test_the_groups_of_a_key_are_its_spellings_by_first_six_letters():
    g = pr.collision_groups(_rows(MASSI))
    assert set(g) == {'massil', 'massin', 'massik'}
    assert g['massil']['lines'] == 10 and g['massil']['works'] == 3
    assert g['massil']['forms'] == {'Massiliam': 6, 'Massiliae': 3, 'Massilienses': 1}
    assert g['massin']['lines'] == 7 and g['massin']['works'] == 2
    assert pr.group_stem('Μασσαλία') == 'massal'            # the transliteration of the key, six letters at most


def test_a_key_is_a_collision_when_two_groups_each_hold_five_lines_in_two_works():
    cand = pr.collision_candidate(pr.collision_groups(_rows(MASSI)))
    assert set(cand) == {'massil', 'massin'}                  # Massicus has too few lines and one work
    one = {k: v for k, v in MASSI.items() if k.startswith('Massil')}
    assert pr.collision_candidate(pr.collision_groups(_rows(one))) == {}
    lines5_work1 = dict(MASSI, Massinissa=[('livy', str(i)) for i in range(1, 6)], Massinissam=[])
    assert pr.collision_candidate(pr.collision_groups(_rows(lines5_work1))) == {}        # five lines in one work: not enough


def _answer(typ, latin, greek=''):
    return {'type': typ, 'latin': latin, 'greek': greek, 'description': 'd', 'distinct_names': False, 'main_forms': []}


def test_the_model_splits_a_collision_into_one_judgment_per_name():
    cand = pr.collision_candidate(pr.collision_groups(_rows(MASSI)))
    answers = {'massi': {'massil': _answer('place', 'Massilia', 'Μασσαλία'), 'massin': _answer('person', 'Masinissa')}}
    old = {'massi': {'type': 'other', 'latin': '', 'greek': '', 'description': '', 'distinct_names': True,
                     'main_forms': ['Massiliam']}, 'other': _answer('person', 'Other')}
    out, rep = pr.collision_judgments(old, {'massi': cand}, answers, log=lambda *_: None)
    assert 'massi' not in out and out['other'] == old['other']
    assert out['massil']['latin'] == 'Massilia' and out['massil']['base'] == 'massi' and out['massil']['distinct_names'] is True
    assert out['massil']['main_forms'] == ['Massiliae', 'Massiliam', 'Massilienses']
    assert out['massin']['latin'] == 'Masinissa' and out['massin']['main_forms'] == ['Massinissa', 'Massinissam']
    assert (rep['candidates'], rep['split'], rep['not_split'], rep['names']) == (1, 1, 0, 2)
    # the earlier judgment named Massilia: that name keeps its id pn:massi and the listed spellings that no group names
    old2 = {'massi': {'type': 'place', 'latin': 'Massilia', 'greek': '', 'description': '', 'distinct_names': True,
                      'main_forms': ['Massiliam', 'Massicus']}}
    out2, _r = pr.collision_judgments(old2, {'massi': cand}, answers, log=lambda *_: None)
    assert out2['massil']['entity_key'] == 'massi' and 'entity_key' not in out2['massin']
    # a name found in a Latin group and a Greek-script group takes the Greek label the Greek group gave
    two = {'massi': {'massil': _answer('place', 'Massilia'), 'massin': _answer('person', 'Masinissa', 'Μασινίσσα')}}
    cand3 = dict(cand, massil3=dict(cand['massil'], lines=3, works=3))
    two['massi']['massil3'] = _answer('place', 'Massilia', 'Μασσαλία')
    out3, _r = pr.collision_judgments(old, {'massi': cand3}, two, log=lambda *_: None)
    assert out3['massil']['greek'] == 'Μασσαλία'
    # both groups name the same entity: no split and the old judgment stands
    same = {'massi': {'massil': _answer('person', 'Masinissa'), 'massin': _answer('person', 'Masinissa')}}
    out, rep = pr.collision_judgments(old, {'massi': cand}, same, log=lambda *_: None)
    assert out['massi'] == old['massi'] and rep['not_split'] == 1 and rep['split'] == 0
    # both groups are common words: no split either
    none = {'massi': {'massil': _answer('other', ''), 'massin': _answer('other', '')}}
    assert pr.collision_judgments(old, {'massi': cand}, none, log=lambda *_: None)[1]['split'] == 0
    # one name and one common word is no split: the name's earlier judgment stands
    one = {'massi': {'massil': _answer('place', 'Massilia'), 'massin': _answer('other', '')}}
    out, rep = pr.collision_judgments(old, {'massi': cand}, one, log=lambda *_: None)
    assert rep['split'] == 0 and out['massi'] == old['massi']
    # two names of one type that differ by a letter or two, or by a word, are one name
    near = {'massi': {'massil': _answer('people', 'Romani'), 'massin': _answer('people', 'Romans')}}
    assert pr.collision_judgments(old, {'massi': cand}, near, log=lambda *_: None)[1]['split'] == 0
    assert pr.same_collision_name(_answer('place', 'Mount Olympus'), _answer('place', 'Olympus'))
    # a place and its people are two entities, and two different people are two entities
    assert not pr.same_collision_name(_answer('place', 'Italy'), _answer('people', 'Italians'))
    assert not pr.same_collision_name(_answer('person', 'Aristotle'), _answer('person', 'Aristides'))


# ---------------------------------------------------------------- A and E on a fixture store

def _store(path):
    db = sqlite3.connect(path)
    db.executescript(ei.SCHEMA)
    db.executescript(pr.LABEL_SCHEMA)
    for col in ('line_ref', 'form_key'):
        db.execute(f'alter table mention_rows add column {col} TEXT')
    db.executemany('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)', [
        (10, 'nm:massi', 'name', 'Massiliensium', 'names', None, None, None, None, 'massi', 0, 0),
        (11, 'pn:masin', 'person', 'Masinissa', 'promoted', None, None, None, None, 'masin', 0, 0),
        (12, 'nm:karno', 'name', 'Carnotensis', 'names', None, None, None, None, 'karno', 0, 0),
        (13, 'nm:masal', 'name', 'Μασσαλία', 'names', None, None, None, None, 'masal', 0, 0)])
    var = [(10, f, '', 'form', 'names') for f in ('massiliam', 'massiliae', 'massiliensium', 'massilienses', 'massinissa', 'massinissam')]
    var += [(11, f, '', 'form', 'names') for f in ('masinissa', 'masinissae')]
    var += [(12, f, '', 'form', 'names') for f in ('carnotensis', 'carnotensium', 'καρνοι', 'καρνοισ', 'καρνοσ')]
    var += [(13, 'μασσαλια', '', 'form', 'names')]
    db.executemany('insert into variants values (?,?,?,?,?)', var)
    rows, wins, wid = [], [], 0
    for eid, form, n in ((10, 'Massiliam', 6), (10, 'Massiliae', 4), (10, 'Massiliensium', 3), (10, 'Massilienses', 2),
                         (10, 'Massinissa', 4), (10, 'Massinissam', 3), (11, 'Masinissa', 5), (11, 'Masinissae', 2),
                         (12, 'Carnotensis', 3), (12, 'Carnotensium', 2), (12, 'Κάρνοις', 2), (12, 'Κάρνοι', 2), (12, 'Κάρνος', 1),
                         (13, 'Μασσαλία', 3)):
        for i in range(n):
            wid += 1
            work = f'w{(wid % 3) + 1}.text'
            wins.append((wid, f'{work}:{wid}', work, f'{wid}.1', f'{wid}.1', 'la'))
            rows.append((eid, wid, form, 1, 0, 0, 'lemma', 'lemma', 0, f'{wid}.1', ei.fold(form)))
    db.executemany('insert into windows values (?,?,?,?,?,?)', wins)
    db.executemany('insert into mention_rows values (?,?,?,?,?,?,?,?,?,?,?)', rows)
    db.commit()
    return db


def _judgments(db):
    cand = pr.collision_candidate(pr.collision_groups(
        [(f, w, ln) for f, w, ln in db.execute(
            "select m.form, w.work, m.line_ref from mention_rows m join windows w on w.wid = m.wid where m.eid = 10")]))
    # every spelling of both groups, the way the script stores them
    answers = {'massi': {'massil': _answer('place', 'Massilia', 'Μασσαλία'), 'massin': _answer('person', 'Massinissa', 'Μασινίσσα')}}
    old = {'massi': {'type': 'other', 'latin': '', 'greek': '', 'description': '', 'distinct_names': True, 'main_forms': ['Massiliam']},
           'karno': {'type': 'people', 'latin': 'Carnutes', 'greek': 'Κάρνοι', 'description': 'A tribe.', 'distinct_names': True,
                     'main_forms': ['Carnotensis', 'Carnotensium']}}
    return pr.collision_judgments(old, {'massi': cand}, answers, log=lambda *_: None)[0]


def test_massilia_is_promoted_and_masinissa_joins_its_entity(tmp_path):
    path = str(tmp_path / 's.sqlite')
    db = _store(path)
    pr.write_display_labels(db, log=lambda *_: None)
    j = _judgments(db)
    rep = pr.promote_store(db, j, log=lambda *_: None, greek_stems=pr.greek_stems_of_store(db))
    dd = pr.dedupe_promoted(db, log=lambda *_: None)
    assert dd['groups'] == 1                                                  # the Massinissa group joins pn:masin (single s)
    ent_ids = dict(db.execute("select entity_id, type from entities where source = 'promoted'"))
    assert ent_ids == {'pn:masin': 'person', 'pn:massil': 'place', 'pn:karno': 'people'}
    eid = db.execute("select eid from entities where entity_id = 'pn:massil'").fetchone()[0]
    assert db.execute('select display_label, display_label_grc from entity_labels where eid = ?', (eid,)).fetchone() == ('Massilia', 'Μασσαλία')
    assert db.execute("select label from entities where entity_id = 'pn:masin'").fetchone() == ('Masinissa',)    # the label with more lines
    assert db.execute('select count(*) from mention_rows where eid = ?', (eid,)).fetchone()[0] == 15
    masin = db.execute("select eid from entities where entity_id = 'pn:masin'").fetchone()[0]
    assert db.execute('select count(*) from mention_rows where eid = ?', (masin,)).fetchone()[0] == 7 + 7      # the Massinissa spellings moved
    assert {r[0] for r in db.execute('select alias_id from entity_aliases where eid = ?', (masin,))} >= {'pn:massin'}
    assert db.execute("select count(*) from mention_rows where eid = 10").fetchone()[0] == 0                    # nothing is left under the demonym
    assert rep['promoted'] == 3


def test_the_heir_does_not_keep_a_greek_label_that_is_a_spelling_of_another_name():
    cand = {'karno': {'karnot': {'forms': {'Carnotensis': 12, 'Carnotensium': 9}, 'lines': 21, 'works': 14},
                      'karnoi': {'forms': {'Κάρνοις': 5, 'Κάρνοι': 3}, 'lines': 7, 'works': 5}}}
    old = {'karno': {'type': 'people', 'latin': 'Carnutes', 'greek': 'Κάρνοι', 'description': '', 'distinct_names': True,
                     'main_forms': ['Carnotensis', 'Carnotensium']}}
    answers = {'karno': {'karnot': _answer('people', 'Carnutes'), 'karnoi': _answer('people', 'Carni', 'Κάρνοι')}}
    out, rep = pr.collision_judgments(old, cand, answers, log=lambda *_: None)
    assert rep['split'] == 1
    assert out['karnot']['latin'] == 'Carnutes' and out['karnot']['greek'] == '' and out['karnot']['entity_key'] == 'karno'
    assert out['karnoi']['latin'] == 'Carni' and out['karnoi']['greek'] == 'Κάρνοι'
    # the model gives Κάρνοι to the Carnutes group as well: still left out, a spelling of the Carni group
    again = {'karno': {'karnot': _answer('people', 'Carnutes', 'Κάρνοι'), 'karnoi': _answer('people', 'Carni', 'Κάρνοι')}}
    out, _r = pr.collision_judgments(old, cand, again, log=lambda *_: None)
    assert out['karnot']['greek'] == '' and out['karnoi']['greek'] == 'Κάρνοι'
    # no group gives Κάρνοι to the Carni group: the earlier label is still left out, because the Carni group spells it
    out, _r = pr.collision_judgments(old, cand, {'karno': {'karnot': _answer('people', 'Carnutes'), 'karnoi': _answer('people', 'Carni')}},
                                     log=lambda *_: None)
    assert out['karnot']['greek'] == '' and out['karnoi']['greek'] == ''


def test_a_cluster_tries_the_earlier_label_first_and_falls_back_to_the_groups_labels(tmp_path):
    cand = {'fabio': {'fabio': {'forms': {'Fabio': 5, 'Φαβίῳ': 4}, 'lines': 9, 'works': 5},
                      'fabiol': {'forms': {'Fabiola': 6}, 'lines': 6, 'works': 3}}}
    old = {'fabio': {'type': 'person', 'latin': 'Fabius', 'greek': 'Φάβιος', 'description': '', 'distinct_names': False,
                     'main_forms': []}}
    answers = {'fabio': {'fabio': _answer('person', 'Fabius', 'Φαβίῳ'), 'fabiol': _answer('person', 'Fabiola')}}
    out, _r = pr.collision_judgments(old, cand, answers, log=lambda *_: None)
    assert out['fabio2']['greek'] == 'Φάβιος' and out['fabio2']['greek_alternatives'] == ['Φαβίῳ']
    assert out['fabio2']['entity_key'] == 'fabio'
    # the first label that passes the Greek-form test at promotion is the one stored
    db = _store(str(tmp_path / 'a.sqlite'))
    pr.write_display_labels(db, log=lambda *_: None)
    db.execute("insert into variants values (10, 'φαβιω', '', 'form', 'names')")
    j = {'massil': {'type': 'place', 'latin': 'Massilia', 'greek': 'Μασσιλία', 'greek_alternatives': ['Μασσαλία'],
                    'description': '', 'distinct_names': True, 'main_forms': ['Massiliam', 'Massiliae'], 'base': 'massi'}}
    pr.promote_store(db, j, log=lambda *_: None, greek_stems=pr.greek_stems_of_store(db))
    eid = db.execute("select eid from entities where entity_id = 'pn:massil'").fetchone()[0]
    assert db.execute('select display_label_grc from entity_labels where eid = ?', (eid,)).fetchone() == ('Μασσαλία',)


def test_a_greek_label_check_by_the_model_is_asked_for_the_carnutes_pattern_only():
    j = {'karno': {'type': 'people', 'latin': 'Carnutes', 'greek': 'Κάρνοι', 'description': '', 'distinct_names': True,
                   'main_forms': ['Carnotensis']},
         'fabio': {'type': 'person', 'latin': 'Fabius', 'greek': 'Φάβιος', 'description': '', 'distinct_names': True,
                   'main_forms': ['Φάβιος', 'Fabius']},                                  # a Greek main spelling: the ordinary rule
         'plain': {'type': 'person', 'latin': 'Plato', 'greek': 'Πλάτων', 'description': '', 'distinct_names': False, 'main_forms': []}}
    spellings = {'karno': ['Carnotensis', 'Κάρνοις', 'Κάρνος', 'Καρνούτων'], 'fabio': ['Φάβιος', 'Φαβίου'], 'plain': ['Πλάτων']}
    got = pr.greek_candidates(j, lambda k: spellings[k])
    assert got == {'karno': ['Κάρνοις', 'Κάρνος']}
    assert pr.parse_greek_fix('{"answer": "Different"}') == 'different' and pr.parse_greek_fix('maybe') is None
    assert pr.apply_greek_fix(j, {'karno': 'different', 'plain': 'same'}) == 1 and j['karno']['greek'] == '' and j['plain']['greek'] == 'Πλάτων'


def test_a_collision_group_keeps_a_greek_label_the_corpus_spells(tmp_path):
    # a group's Greek label is not checked against the spellings of the other names found under its key
    # (Fabius and Fabii share the Greek stem Φαβι), only against the corpus
    db = _store(str(tmp_path / 's.sqlite'))
    pr.write_display_labels(db, log=lambda *_: None)
    j = _judgments(db)
    assert 'other_forms' not in j['massil']
    pr.promote_store(db, j, log=lambda *_: None, greek_stems=pr.greek_stems_of_store(db))
    eid = db.execute("select eid from entities where entity_id = 'pn:massil'").fetchone()[0]
    assert db.execute('select display_label_grc from entity_labels where eid = ?', (eid,)).fetchone() == ('Μασσαλία',)


def test_the_group_that_keeps_the_old_id_keeps_the_old_greek_rules(tmp_path):
    db = _store(str(tmp_path / 's.sqlite'))
    pr.write_display_labels(db, log=lambda *_: None)
    j = _judgments(db)
    j['massil']['greek'] = 'Μασσιλία'                                        # no such spelling in the store
    j['massil']['entity_key'] = 'massi'
    pr.promote_store(db, j, log=lambda *_: None, greek_stems=pr.greek_stems_of_store(db))
    eid = db.execute("select eid from entities where entity_id = 'pn:massi'").fetchone()[0]
    assert db.execute('select display_label_grc from entity_labels where eid = ?', (eid,)).fetchone() == ('Μασσιλία',)


def test_a_greek_label_the_corpus_never_spells_is_dropped_for_a_group(tmp_path):
    db = _store(str(tmp_path / 's.sqlite'))
    pr.write_display_labels(db, log=lambda *_: None)
    j = _judgments(db)
    j['massil']['greek'] = 'Μασσιλία'                                        # no such spelling in the store
    pr.promote_store(db, j, log=lambda *_: None, greek_stems=pr.greek_stems_of_store(db))
    eid = db.execute("select eid from entities where entity_id = 'pn:massil'").fetchone()[0]
    assert db.execute('select display_label_grc from entity_labels where eid = ?', (eid,)).fetchone() == (None,)


# ---------------------------------------------------------------- D. search names made from the spellings

def test_a_spelling_is_cut_to_its_stem():
    assert extras.form_stem('massiliam') == 'massil' and extras.form_stem('massiliae') == 'massil'
    assert extras.form_stem('massilia') == 'massil' and extras.form_stem('massilienses') == 'massiliens'
    assert extras.form_stem('roma') == 'roma'                                   # four letters: nothing is cut
    assert extras.form_stem('romam') == 'romam'                                # no ending leaves five letters
    assert extras.form_stem('μασσαλιαν') == 'μασσαλ'


@pytest.fixture
def stems_store(tmp_path, monkeypatch):
    path = str(tmp_path / 'e.sqlite')
    db = _store(path)
    pr.write_display_labels(db, log=lambda *_: None)
    # the name entity of Massilia keeps only oblique spellings and its heading is a demonym
    db.execute("delete from variants where eid = 10 and form in ('massinissa', 'massinissam')")
    db.commit()
    extras.add_form_search_names(db, log=lambda *_: None)
    db.commit()
    db.close()
    extras.write_catalog(path, log=lambda *_: None)
    monkeypatch.setenv('TESSERAE_ENTITY_STORE', path)
    ent._cache.clear()
    monkeypatch.setattr(window_texts, 'texts_for', lambda ids: {})
    monkeypatch.setattr(passage_index, '_naming', lambda w: {'title': 'T', 'author': 'A'})
    return path


def test_the_stems_are_stored_as_search_names_of_source_form(stems_store):
    db = sqlite3.connect(stems_store)
    rows = {(eid, name) for eid, name, src in db.execute("select eid, name, source from search_names where source = 'form'")}
    assert (10, 'massil') in rows and (10, 'massiliens') in rows and (12, 'carnotens') in rows
    assert not any(eid == 10 and name == 'massiliam' for eid, name in rows)       # stems, not the spellings
    cat = ent._catalog(stems_store)
    assert 'massil' in cat['names'][10]['form_stems']
    assert cat['names'][10]['forms'][:2] == ['massiliam', 'massiliae']            # the matching forms are not touched


def test_a_nominative_finds_an_entity_whose_spellings_are_all_oblique(stems_store):
    r = get(f'{P}/search?q=massilia').get_json()
    assert r['results'][0]['id'] == 'nm:massi'                                   # the stem massil is the stem of the query
    r = get(f'{P}/search?q=Massilienses').get_json()
    assert r['results'][0]['id'] == 'nm:massi'
    assert 'nm:massi' not in [x['id'] for x in get(f'{P}/search?q=carnotensis').get_json()['results']]


def get(url):
    return app.test_client().get(url)
