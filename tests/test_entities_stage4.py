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


def test_the_groups_of_a_key_are_its_spellings_by_stem():
    g = pr.collision_groups(_rows(MASSI))
    assert set(g) == {'massil', 'massiliens', 'massiniss', 'massic'}
    assert g['massil']['lines'] == 9 and g['massil']['works'] == 2
    assert g['massil']['forms'] == {'Massiliam': 6, 'Massiliae': 3}
    assert g['massiniss']['lines'] == 7 and g['massiniss']['works'] == 2
    # one name in its case forms is one group
    stems = {pr.group_stem(f) for f in ('Fabius', 'Fabium', 'Fabio', 'Fabii', 'Fabi')}
    assert stems == {'fabi'}
    assert pr.group_stem('Μασσαλία') == 'μασσαλ' and pr.group_stem('Μασσαλίαν') == 'μασσαλ'


def test_a_key_is_a_collision_when_two_groups_each_hold_five_lines_in_two_works():
    cand = pr.collision_candidate(pr.collision_groups(_rows(MASSI)))
    assert set(cand) == {'massil', 'massiniss'}               # Massicus has too few lines and one work
    one = {k: v for k, v in MASSI.items() if k.startswith('Massil')}
    assert pr.collision_candidate(pr.collision_groups(_rows(one))) == {}
    lines5_work1 = dict(MASSI, Massinissa=[('livy', str(i)) for i in range(1, 6)], Massinissam=[])
    assert pr.collision_candidate(pr.collision_groups(_rows(lines5_work1))) == {}        # five lines in one work: not enough


def _answer(typ, latin, greek=''):
    return {'type': typ, 'latin': latin, 'greek': greek, 'description': 'd', 'distinct_names': False, 'main_forms': []}


def _carve(old, cand_spec, answers, **kw):
    groups = pr.collision_groups(_rows(cand_spec))
    return pr.collision_judgments(old, {'k': groups}, {'k': answers}, log=lambda *_: None, min_lines=5, min_works=2, **kw)


NO_HEIR = {'k': {'type': 'other', 'latin': '', 'greek': '', 'description': '', 'distinct_names': False, 'main_forms': []}}


def test_the_model_carves_the_names_it_finds_in_a_key_with_no_heir():
    out, rep = _carve(NO_HEIR, MASSI, {'massil': _answer('place', 'Massilia', 'Μασσαλία'),
                                       'massiniss': _answer('person', 'Massinissa')})
    assert (rep['candidates'], rep['split'], rep['names']) == (1, 1, 2)
    carved = {v['latin']: v for k, v in out.items() if k != 'k'}
    assert carved['Massilia']['main_forms'] == ['Massiliae', 'Massiliam'] and carved['Massilia']['base'] == 'k'
    assert carved['Massinissa']['main_forms'] == ['Massinissa', 'Massinissam']
    assert out['k'] == NO_HEIR['k']                                    # the corpus name's judgment is untouched


def test_a_group_the_model_calls_other_or_the_same_name_stays_with_the_heir():
    heir = {'k': {'type': 'person', 'latin': 'Massilius', 'greek': 'Μασσίλιος', 'description': 'A man.',
                  'distinct_names': False, 'main_forms': []}}
    # the second group is called a common word: nothing is carved and the heir is untouched
    out, rep = _carve(heir, MASSI, {'massil': _answer('person', 'Massilius'), 'massiniss': _answer('other', '')})
    assert rep['split'] == 0 and out == heir
    # both groups name the heir (or a name inside it): nothing is carved
    out, rep = _carve(heir, MASSI, {'massil': _answer('person', 'Massilius'), 'massiniss': _answer('person', 'Massilius')})
    assert rep['split'] == 0 and out == heir
    # a different name that is too small on its own stays too (10 lines in 3 works are asked in the real run)
    groups = pr.collision_groups(_rows(MASSI))
    out, rep = pr.collision_judgments(heir, {'k': groups}, {'k': {'massil': _answer('person', 'Massilius'),
                                      'massiniss': _answer('person', 'Massinissa')}}, log=lambda *_: None)
    assert rep['split'] == 0 and out == heir


def test_the_heir_keeps_its_id_labels_and_description_when_a_name_is_carved():
    heir = {'k': {'type': 'person', 'latin': 'Massilius', 'greek': 'Μασσίλιος', 'description': 'A man.',
                  'distinct_names': False, 'main_forms': []}}
    out, rep = _carve(heir, MASSI, {'massil': _answer('person', 'Massilius'), 'massiniss': _answer('person', 'Massinissa')})
    assert rep['split'] == 1 and rep['names'] == 1
    h = out['k']
    assert (h['latin'], h['greek'], h['description'], h['type']) == ('Massilius', 'Μασσίλιος', 'A man.', 'person')
    assert h['distinct_names'] is True and 'Massinissa' not in h['main_forms'] and 'Massiliam' in h['main_forms']
    assert 'Massicus' in h['main_forms']                              # every spelling that was not carved stays
    # the heir loses its Greek label only when the carved group took that very spelling
    out, _r = _carve(dict(heir, k=dict(heir['k'], greek='Μασσινίσσα')), dict(MASSI, **{'Μασσινίσσα': [('x', str(i)) for i in range(5)] + [('y', '1')]}),
                     {'massil': _answer('person', 'Massilius'), 'massiniss': _answer('person', 'Massinissa'),
                      pr.group_stem('Μασσινίσσα'): _answer('person', 'Massinissa')})
    assert out['k']['greek'] == ''


def test_a_greek_spelling_with_the_stem_of_the_heirs_label_stays_with_the_heir():
    assert pr.stays_with_heir('Καρνούτων', 'Carnutes') and pr.stays_with_heir('Καρνούτῳ', 'Carnutes')
    assert not pr.stays_with_heir('Κάρνοι', 'Carnutes') and not pr.stays_with_heir('Carnutum', 'Carnutes')
    assert not pr.stays_with_heir('Ἀβισάρου', 'Abisai')          # starts like the label but is not its stem plus an ending
    spec = {'Carnotensis': [('a', str(i)) for i in range(1, 7)], 'Carnotensium': [('b', '1')],
            'Κάρνοις': [('c', str(i)) for i in range(1, 4)], 'Κάρνοι': [('d', '1'), ('d', '2')],
            'Καρνούτων': [('e', '1'), ('e', '2'), ('e', '3')], 'Καρνούτῳ': [('f', '1')]}
    heir = {'k': {'type': 'people', 'latin': 'Carnutes', 'greek': 'Κάρνοι', 'description': 'A tribe.', 'distinct_names': True,
                  'main_forms': ['Carnotensis', 'Carnotensium']}}
    groups = pr.collision_groups(_rows(spec))
    ans = {pr.group_stem('Κάρνοι'): _answer('people', 'Carni', 'Κάρνοι'), pr.group_stem('Καρνούτων'): _answer('place', 'Carnuntum'),
           pr.group_stem('Carnotensis'): _answer('people', 'Carnutes')}
    out, rep = pr.collision_judgments(heir, {'k': groups}, {'k': ans}, log=lambda *_: None, min_lines=3, min_works=2)
    names = {v['latin']: v for kk, v in out.items() if kk != 'k'}
    assert 'Carni' in names and names['Carni']['main_forms'] == ['Κάρνοι', 'Κάρνοις']
    assert 'Carnuntum' not in names or 'Καρνούτων' not in names['Carnuntum']['main_forms']
    assert out['k']['greek'] == ''                                    # Carni took the spelling Κάρνοι
    assert 'Καρνούτων' in out['k']['main_forms'] or out['k']['main_forms'] == ['Carnotensis', 'Carnotensium']


def test_a_place_group_with_the_stem_of_a_peoples_name_stays_with_the_people():
    assert pr._prefix_of_label('μακεδον', 'Macedonians') and pr._prefix_of_label('macedon', 'Macedonians')
    assert not pr._prefix_of_label('apollu', 'Apollo')
    spec = {'Macedonum': [('a', str(i)) for i in range(12)] + [('b', '1'), ('c', '1')],
            'Macedonia': [('d', str(i)) for i in range(12)], 'Macedonicus': [('e', str(i)) for i in range(6)] + [('f', '1')]}
    heir = {'k': {'type': 'people', 'latin': 'Macedonians', 'greek': 'Μακεδόνες', 'description': 'A people.',
                  'distinct_names': False, 'main_forms': []}}
    groups = pr.collision_groups(_rows(spec))
    out, rep = pr.collision_judgments(heir, {'k': groups}, {'k': {pr.group_stem('Macedonia'): _answer('place', 'Macedonia'),
                                      pr.group_stem('Macedonicus'): _answer('person', 'Macedonicus')}}, log=lambda *_: None,
                                      min_lines=5, min_works=2)
    names = {v['latin'] for kk, v in out.items() if kk != 'k'}
    assert 'Macedonia' not in names and out['k']['greek'] == 'Μακεδόνες'


def test_the_heirs_greek_label_is_tested_against_the_spellings_it_had_before_the_carve(tmp_path):
    db = _store(str(tmp_path / 'h.sqlite'))
    pr.write_display_labels(db, log=lambda *_: None)
    j = {'massi': {'type': 'person', 'latin': 'Massilius', 'greek': 'Μασσαλία', 'description': 'd', 'distinct_names': True,
                   'main_forms': ['Massiliam', 'Massiliae', 'Massilienses'], 'label_forms': ['massiliam', 'μασσαλια']}}
    pr.promote_store(db, j, log=lambda *_: None, greek_stems=set())
    eid = db.execute("select eid from entities where entity_id = 'pn:massi'").fetchone()[0]
    assert db.execute('select display_label_grc from entity_labels where eid = ?', (eid,)).fetchone() == ('Μασσαλία',)
    j['massi']['label_forms'] = ['massiliam', 'ψευδο']                       # a Greek spelling that does not agree with the label
    db2 = _store(str(tmp_path / 'i.sqlite'))
    pr.write_display_labels(db2, log=lambda *_: None)
    pr.promote_store(db2, j, log=lambda *_: None, greek_stems=set())
    eid = db2.execute("select eid from entities where entity_id = 'pn:massi'").fetchone()[0]
    assert db2.execute('select display_label_grc from entity_labels where eid = ?', (eid,)).fetchone() == (None,)


def test_an_installed_id_never_disappears_in_a_carve():
    heir = {'k': {'type': 'person', 'latin': 'Massilius', 'greek': '', 'description': '', 'distinct_names': False, 'main_forms': []}}
    out, _r = _carve(heir, MASSI, {'massil': _answer('person', 'Massilius'), 'massiniss': _answer('person', 'Massinissa')})
    assert 'k' in out and out['k']['latin'] == 'Massilius'            # the heir is still judged under its own key


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
        (13, 'nm:masal', 'name', 'Μασσαλία', 'names', None, None, None, None, 'masal', 0, 0)])
    var = [(10, f, '', 'form', 'names') for f in ('massiliam', 'massiliae', 'massiliensium', 'massilienses', 'massinissa', 'massinissam')]
    var += [(11, f, '', 'form', 'names') for f in ('masinissa', 'masinissae')]
    var += [(13, 'μασσαλια', '', 'form', 'names')]
    db.executemany('insert into variants values (?,?,?,?,?)', var)
    rows, wins, wid = [], [], 0
    for eid, form, n in ((10, 'Massiliam', 6), (10, 'Massiliae', 4), (10, 'Massiliensium', 3), (10, 'Massilienses', 2),
                         (10, 'Massinissa', 4), (10, 'Massinissam', 3), (11, 'Masinissa', 5), (11, 'Masinissae', 2),
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
    groups = pr.collision_groups(
        [(f, w, ln) for f, w, ln in db.execute(
            "select m.form, w.work, m.line_ref from mention_rows m join windows w on w.wid = m.wid where m.eid = 10")])
    answers = {'massi': {'massil': _answer('place', 'Massilia', 'Μασσαλία'), 'massiniss': _answer('person', 'Massinissa', 'Μασινίσσα'),
                         'massiliens': _answer('people', 'Massilians')}}
    old = {'massi': {'type': 'other', 'latin': '', 'greek': '', 'description': '', 'distinct_names': True, 'main_forms': ['Massiliam']}}
    return pr.collision_judgments(old, {'massi': groups}, answers, log=lambda *_: None, min_lines=5, min_works=2)[0]


def test_massilia_is_promoted_and_masinissa_joins_its_entity(tmp_path):
    path = str(tmp_path / 's.sqlite')
    db = _store(path)
    pr.write_display_labels(db, log=lambda *_: None)
    j = _judgments(db)
    pr.promote_store(db, j, log=lambda *_: None, greek_stems=pr.greek_stems_of_store(db))
    dd = pr.dedupe_promoted(db, log=lambda *_: None)
    assert dd['groups'] == 1                                                  # the Massinissa group joins pn:masin (single s)
    ent_ids = dict(db.execute("select entity_id, type from entities where source = 'promoted'"))
    assert ent_ids['pn:masin'] == 'person' and ent_ids['pn:massil'] == 'place'
    eid = db.execute("select eid from entities where entity_id = 'pn:massil'").fetchone()[0]
    assert db.execute('select display_label, display_label_grc from entity_labels where eid = ?', (eid,)).fetchone() == ('Massilia', 'Μασσαλία')
    assert db.execute("select label from entities where entity_id = 'pn:masin'").fetchone() == ('Masinissa',)    # the label with more lines
    masin = db.execute("select eid from entities where entity_id = 'pn:masin'").fetchone()[0]
    assert db.execute('select count(*) from mention_rows where eid = ?', (masin,)).fetchone()[0] == 7 + 7      # the Massinissa spellings moved
    assert {r[0] for r in db.execute('select alias_id from entity_aliases where eid = ?', (masin,))} >= {'pn:massiniss'}


def test_a_greek_label_the_corpus_never_spells_is_dropped_for_a_new_name(tmp_path):
    db = _store(str(tmp_path / 's.sqlite'))
    pr.write_display_labels(db, log=lambda *_: None)
    j = _judgments(db)
    j['massil']['greek'] = 'Μασσιλία'                                        # no such spelling in the store
    pr.promote_store(db, j, log=lambda *_: None, greek_stems=pr.greek_stems_of_store(db))
    eid = db.execute("select eid from entities where entity_id = 'pn:massil'").fetchone()[0]
    assert db.execute('select display_label_grc from entity_labels where eid = ?', (eid,)).fetchone() == (None,)


def test_a_cluster_tries_its_labels_in_order_and_falls_back(tmp_path):
    db = _store(str(tmp_path / 'a.sqlite'))
    pr.write_display_labels(db, log=lambda *_: None)
    j = {'massil': {'type': 'place', 'latin': 'Massilia', 'greek': 'Μασσιλία', 'greek_alternatives': ['Μασσαλία'],
                    'description': '', 'distinct_names': True, 'main_forms': ['Massiliam', 'Massiliae'], 'base': 'massi'}}
    pr.promote_store(db, j, log=lambda *_: None, greek_stems=pr.greek_stems_of_store(db))
    eid = db.execute("select eid from entities where entity_id = 'pn:massil'").fetchone()[0]
    assert db.execute('select display_label_grc from entity_labels where eid = ?', (eid,)).fetchone() == ('Μασσαλία',)


def test_the_people_rule_leaves_a_peoples_own_name_alone():
    forms = {'Σαυνῖται': 15, 'Σαυνιτῶν': 58, 'Σαυνίτης': 1}
    assert pr.best_form(forms, 'greek', place='people' in pr.PLACE_TYPES) == pr.best_form(forms, 'greek')
    assert 'people' not in pr.PLACE_TYPES and 'person' not in pr.PLACE_TYPES
    assert pr.best_form({'Γετέων': 3, 'Γέται': 9}, 'greek', place=True) == 'Γέται'


def test_a_list_entity_with_a_people_pleiades_type_is_typed_people(tmp_path):
    db = sqlite3.connect(str(tmp_path / 'l.sqlite'))
    db.executescript(ei.SCHEMA)
    db.executemany('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)', [
        (1, 'pl:442765', 'place', 'Samnites', 'list', '442765', None, None, None, None, 1, 0),
        (2, 'pl:1', 'place', 'Athens', 'list', '1', None, None, None, None, 1, 0)])
    db.executemany('insert into windows values (?,?,?,?,?,?)', [(i, f'w:{i}', 'w.text', f'{i}.1', f'{i}.1', 'grc') for i in range(1, 40)])
    rows = [(1, i, 'Σαυνιτῶν', 1, 0, 0, 'lemma', 'lemma', 0) for i in range(1, 6)]
    rows += [(1, i, 'Σαυνίτης', 1, 0, 0, 'lemma', 'lemma', 0) for i in range(6, 8)]
    rows += [(2, i, 'Ἀθηνῶν', 1, 0, 0, 'lemma', 'lemma', 0) for i in range(8, 13)]
    rows += [(2, i, 'Ἀθήνας', 1, 0, 0, 'lemma', 'lemma', 0) for i in range(13, 16)]
    db.executemany('insert into mention_rows(eid, wid, form, cap, nb, ds, confidence, matcher, homonym) values (?,?,?,?,?,?,?,?,?)', rows)
    pr.write_display_labels(db, log=lambda *_: None, people_pleiades={'442765'})
    got = dict(db.execute('select eid, display_label_grc from entity_labels'))
    assert got == {1: 'Σαυνιτῶν', 2: 'Ἀθήνας'}


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
    assert (10, 'massil') in rows and (10, 'massiliens') in rows and (13, 'μασσαλ') in rows
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


# ---------------------------------------------------------------- fix pass 4c, adjectives formed from a name

def test_a_derived_adjective_shape_is_blocked_when_the_entity_has_a_noun_form():
    from backend import entity_lemma as el
    assert el.derived_adjective_shape('palatinus', 'la', ['palatium', 'palatinus'])
    assert el.derived_adjective_shape('dardanus', 'la', ['dardania', 'dardanus'])
    assert el.derived_adjective_shape('ἀρκαδικός', 'grc', ['Ἀρκαδία'])
    assert not el.derived_adjective_shape('palatinus', 'la', ['palatinus'])             # no noun form of its own: the name itself
    assert not el.derived_adjective_shape('cerberus', 'la', ['cerberus'])
    assert not el.derived_adjective_shape('alcaeus', 'la', ['alcaeus', 'alkaios'])      # a noun form that does not share five letters
    assert not el.derived_adjective_shape('iris', 'la', ['iris'])


def test_the_second_question_keeps_only_the_name():
    import importlib.util
    spec = importlib.util.spec_from_file_location('es3b', os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'entity_stage3b.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.parse_derived('{"answer": "name"}') == 'NAME' and mod.parse_derived('```json\n{"answer": "DERIVED"}\n```') == 'DERIVED'
    assert mod.parse_derived('{"answer": "maybe"}') is None and mod.parse_derived('') is None
