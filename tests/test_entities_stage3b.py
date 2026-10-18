"""Mentions stage 3b: the case-form lemma sets, the search names and near spellings of the search, the
Greek label rule, the heading of a merged group and the label asked for from a split. Fixture data
only, no live index and no gateway."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend import entity_extras as extras  # noqa: E402
from backend import entity_index as ei  # noqa: E402
from backend import entity_lemma as el  # noqa: E402
from backend import entity_promote as pr  # noqa: E402
from backend import passage_index  # noqa: E402
from backend import window_texts  # noqa: E402
from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import entities as ent  # noqa: E402

P = f'{API_PREFIX}/entities' if API_PREFIX else '/entities'


# ---------------------------------------------------------------- the case-form lemma sets

def _lemma_fixture():
    """Rhodus is listed, its nominative lemma is rhodus, its oblique cases carry the table lemma rhodos."""
    entities = [{'entity_id': 'pl:1', 'type': 'place', 'label': 'Rhodos', 'merged_from': [],
                 'keys': [{'latin': ['Rhodus'], 'greek': '', 'english': None}]}]
    types = {'la': {'rhodus': [14, 13, 14, 13, 'rhodus'], 'rhodi': [58, 46, 58, 46, 'rhodi'],
                    'rhodum': [121, 110, 121, 110, 'rhodum'], 'rhodo': [56, 2, 56, 2, 'rhodo'],
                    'rhodae': [3, 0, 3, 0, 'rhodae'], 'rhodis': [4, 4, 4, 4, 'rhodis'], 'rhodam': [5, 5, 5, 5, 'rhodam']},
             'grc': {}, 'en': {}}
    stats = {'la': {'rhodus': [14, 13, 14, 13], 'rhodos': [179, 156, 179, 156], 'rhodo': [56, 2, 56, 2],
                    'rhodae': [3, 0, 3, 0], 'rhodan': [5, 5, 5, 5]}, 'grc': {}, 'en': {}}
    prep = {'type_lemma': {'la': {'rhodus': 'rhodus', 'rhodi': 'rhodos', 'rhodum': 'rhodos', 'rhodo': 'rhodo',
                                  'rhodae': 'rhodae', 'rhodis': 'rhodus', 'rhodam': 'rhodan'}, 'grc': {}, 'en': {}},
            'stats': stats, 'form_lemma': [('la', 0, 'rhodus', 'rhodus')], 'form_source': {}}
    return entities, types, prep


def test_the_lemma_of_an_oblique_case_joins_the_set_when_it_is_a_name():
    entities, types, prep = _lemma_fixture()
    present = {'la': {0: {'rhodus'}}, 'grc': {}, 'en': {}}
    ext = el.case_form_extension(entities, types, prep, present)
    # rhodam carries the lemma rhodan, which minus no ending is not the stem rhod: the stem gate refuses it
    assert set(el.case_form_extension(entities, types, prep, present, stem_gate=False)) == {
        ('la', 0, 'rhodos'), ('la', 0, 'rhodan')}
    # rhodi and rhodum carry the lemma rhodos, which is mostly capitalized. rhodo is a common word
    # (2 of 56 capitalized), rhodae is never capitalized, and rhodis is the lemma already held.
    assert ext == {('la', 0, 'rhodos'): ['rhodi', 'rhodum']}
    old, _ = el.assemble_matcher(entities, types, prep, audit_fixes=False, overrides=False, log=lambda *_: None)
    new, info = el.assemble_matcher(entities, types, prep, audit_fixes=False, overrides=False, log=lambda *_: None,
                                    case_forms=True)
    assert 'rhodi' not in old['la'] and new['la']['rhodi'] == (0,) and new['la']['rhodum'] == (0,)
    assert 'rhodo' not in new['la']
    assert info['extension'] == {('la', 0, 'rhodos'): ['rhodi', 'rhodum']}


def test_a_model_decision_still_removes_a_case_form_lemma():
    entities, types, prep = _lemma_fixture()
    new, info = el.assemble_matcher(entities, types, prep, audit_fixes=False, overrides=False, log=lambda *_: None,
                                    case_forms=True, decisions={('la', 'pl:1', 'rhodos'): 'drop'})
    assert 'rhodi' not in new['la']                                     # judged a demonym or a common word
    new, info = el.assemble_matcher(entities, types, prep, audit_fixes=False, overrides=False, log=lambda *_: None,
                                    case_forms=True, decisions={('la', 'pl:1', 'rhodos'): 'other'})
    assert new['la']['rhodi'] == (0,) and 'rhodi' in info['amb_tokens']['la']     # kept, and its windows are asked


def test_the_stem_gate():
    assert el.stem_consistent('rhodos', 'rhodus', 'la')            # rhodos minus os is rhod, the stem of rhodus
    assert el.stem_consistent('rhodus', 'rhodus', 'la')            # the lemma is the listed form
    assert not el.stem_consistent('rhodan', 'rhodus', 'la')
    assert not el.stem_consistent('alexander', 'alexandra', 'la')  # a different name with a similar start
    assert el.stem_consistent('αθηναι', 'αθηνα', 'grc')
    assert not el.stem_consistent('ελλην', 'ελλασ', 'grc')         # Hellen is not a case form of Hellas
    entities, types, prep = _lemma_fixture()
    new, info = el.assemble_matcher(entities, types, prep, audit_fixes=False, overrides=False, log=lambda *_: None,
                                    case_forms=True, case_allowed={('la', 'pl:1', 'rhodos')})
    assert new['la']['rhodi'] == (0,)
    new, info = el.assemble_matcher(entities, types, prep, audit_fixes=False, overrides=False, log=lambda *_: None,
                                    case_forms=True, case_allowed=set())       # the confirmation kept nothing
    assert 'rhodi' not in new['la'] and info['extension'] == {}


def test_the_stem_needs_four_letters():
    assert el.case_stems('rhodus', 'la') == 'rhod'
    assert el.case_stems('roma', 'la') is None or el.case_stems('roma', 'la') == 'roma'
    assert el.case_stems('hannibal', 'la') == 'hannibal'
    assert el.case_stems('ροδοσ', 'grc') == 'ροδοσ'


# ---------------------------------------------------------------- search names and near spellings

TEXTS = {}


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = str(tmp_path / 'entities.sqlite')
    db = sqlite3.connect(path)
    db.executescript(ei.SCHEMA)
    db.executescript(pr.LABEL_SCHEMA)
    db.executemany('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)', [
        (1, 'pl:590031', 'place', 'Rhodos (island)', 'list', None, None, None, None, None, 1, 0),
        (2, 'pn:rodio', 'people', 'Rhodians', 'promoted', None, None, None, None, 'rodio', 0, 0),
        (3, 'nm:rhode', 'name', 'Rhodes', 'names', None, None, None, None, 'rhode', 0, 0),
        (4, 'pl:413288', 'place', 'Rusellae', 'list', None, None, None, None, None, 1, 0),
        (5, 'nm:russe', 'name', 'Russelae', 'names', None, None, None, None, 'russe', 0, 0),
        (6, 'pl:thebe', 'place', 'Thebes', 'list', None, None, None, None, None, 1, 0),
        (7, 'pl:thebi', 'place', 'Thebe', 'list', None, None, None, None, None, 1, 0),
        (8, 'pl:thbas', 'place', 'Thebas', 'list', None, None, None, None, None, 1, 0),
        (9, 'pl:thbar', 'place', 'Thebar', 'list', None, None, None, None, None, 1, 0)])
    db.executemany('insert into variants values (?,?,?,?,?)', [
        (1, 'rhodos', 'la', 'form', 'list'), (2, 'rhodii', '', 'form', 'promoted'), (3, 'rhodes', '', 'form', 'names'),
        (4, 'rusellae', 'en', 'form', 'list'), (5, 'russelae', '', 'form', 'names')])
    db.executemany('insert into windows values (?,?,?,?,?,?)', [(i, f'w:{i}', 'w.work', f'{i}.1', f'{i}.1', 'la') for i in range(1, 400)])
    rows, n = [], 0

    def add(eid, count):
        nonlocal n
        for _ in range(count):
            n += 1
            rows.append((eid, n, 'x', 1, 0, 0, 'lemma', 'lemma', 0))
    for eid, count in ((1, 12), (2, 30), (3, 3), (4, 20), (5, 3), (6, 50), (7, 5), (8, 60), (9, 4)):
        add(eid, count)
    db.executemany('insert into mention_rows values (?,?,?,?,?,?,?,?,?)', rows)
    db.executescript('CREATE TABLE search_names (eid INTEGER, name TEXT, source TEXT);')
    db.executemany('insert into search_names values (?,?,?)', [
        (1, 'Rhodes', 'model'), (1, 'Rhodos', 'model'), (2, 'Rhodians', 'model'), (2, 'Rhodes', 'model')])
    db.commit()
    db.close()
    extras.write_catalog(path, log=lambda *_: None)
    monkeypatch.setenv('TESSERAE_ENTITY_STORE', path)
    ent._cache.clear()
    monkeypatch.setattr(window_texts, 'texts_for', lambda ids: {})
    monkeypatch.setattr(passage_index, '_naming', lambda w: {'title': 'T', 'author': 'A'})
    return path


def get(url):
    return app.test_client().get(url)


def test_the_usual_english_name_finds_the_island_first(store):
    r = get(f'{P}/search?q=rhodes').get_json()
    # the island's usual name is Rhodes, the Rhodians are also called Rhodes (a second name) and have more
    # lines, and the plain corpus name Rhodes comes last, under its own heading
    assert [(x['id'], x['source']) for x in r['results']] == [
        ('pl:590031', 'list'), ('pn:rodio', 'promoted'), ('nm:rhode', 'corpus')]
    r = get(f'{P}/search?q=rho').get_json()                              # a prefix of a search name ranks like a label prefix
    assert r['results'][0]['id'] in ('pn:rodio', 'pl:590031')


def test_search_names_are_for_search_only(store):
    cat = ent._catalog(store)
    assert cat['by_id']['pl:590031']['search_names'] == ['rhodes', 'rhodos']
    db = sqlite3.connect(store)
    forms = {r[0] for r in db.execute('select form from variants where eid = 1')}
    assert forms == {'rhodos'}                                           # nothing was added to the matching forms


def test_near_spellings_when_only_corpus_names_match(store):
    r = get(f'{P}/search?q=russelae').get_json()
    assert [x['id'] for x in r['results']] == ['nm:russe']
    assert [(x['id'], x['distance']) for x in r['near_spellings']] == [('pl:413288', 2)]


def test_near_spellings_when_the_best_match_has_fewer_lines(store):
    r = get(f'{P}/search?q=thebes').get_json()
    # Thebes (50 lines) matches by equality. Thebas (60) is one edit away and has more lines than the best
    # match, so it is offered. Thebe (5) and Thebar (4) have fewer and are not.
    assert r['results'][0]['id'] == 'pl:thebe'
    assert [(x['id'], x['distance']) for x in r['near_spellings']] == [('pl:thbas', 1)]
    assert 'near_spellings' not in get(f'{P}/search?q=rusellae').get_json()


def test_near_spellings_are_bounded_by_the_length_of_the_query(store):
    cat = ent._catalog(store)
    near = lambda q: [x['id'] for x in ent._near_spellings(cat, q, [], [])]     # noqa: E731
    assert near('thbe') == [] and near('thebs') != []         # four letters, none. five letters, one edit (Thebes, Thebas)
    assert set(near('thebus')) == {'pl:thbas', 'pl:thebe'}                       # six letters allow one edit
    assert near('thabus') == []                                 # and not two: thabus is two edits from Thebas
    assert 'pl:413288' in near('russelae')                      # eight letters allow two


# ---------------------------------------------------------------- the three label faults

def test_a_greek_label_needs_a_greek_form_that_agrees_with_it():
    assert pr.greek_label_ok('Ἀβραάμ', [])                                           # no Greek-script form: kept
    assert pr.greek_label_ok('Ἀβραάμ', ['abraham', 'abrahami'])                      # Latin forms only: kept
    assert pr.greek_label_ok('Ἀπουλία', ['apulia', 'απουλιασ'])                      # a Greek form with the same stem
    assert pr.greek_label_ok('Ἀβραάμ', ['αβρααμ'])
    assert not pr.greek_label_ok('Κάρνοι', ['carnutes', 'καρνουτων'])                # stem karn against karnout: too short
    assert not pr.greek_label_ok('', ['abraham'])


def test_a_merged_group_takes_the_nominative_looking_label():
    assert pr.pick_group_label([('Baias', 40), ('Baiae', 25)], 'latin') == 'Baiae'
    assert pr.pick_group_label([('Baiae', 5), ('Baiae', 3), ('Baias', 4)], 'latin') == 'Baiae'
    assert pr.pick_group_label([('Narseh', 10), ('Narses', 5)], 'latin') == 'Narses'
    assert pr.pick_group_label([('Sarpedona', 90), ('Sarpedon', 10)], 'latin') == 'Sarpedon'  # an ending beats the count
    assert pr.pick_group_label([('Ἀθηνᾶς', 90), ('Ἀθήνη', 10)], 'greek') == 'Ἀθήνη'
    assert pr.pick_group_label([], 'latin') is None


def test_a_group_label_and_greek_label_are_rederived_in_the_merge(tmp_path):
    db = sqlite3.connect(str(tmp_path / 'g.sqlite'))
    db.executescript(ei.SCHEMA)
    db.executescript(pr.LABEL_SCHEMA)
    db.executemany('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)', [
        (1, 'pn:baias', 'place', 'Baias', 'promoted', None, None, None, None, 'baias', 0, 0),
        (2, 'pn:baiai', 'place', 'Baiae', 'promoted', None, None, None, None, 'baiai', 0, 0)])
    db.executemany('insert into windows values (?,?,?,?,?,?)', [(i, f'w:{i}', 'w.work', f'{i}.1', f'{i}.1', 'la') for i in range(1, 10)])
    for col in ('line_ref', 'form_key'):
        db.execute(f'alter table mention_rows add column {col} TEXT')
    db.executemany('insert into mention_rows(eid, wid, form, cap, nb, ds, confidence, matcher, homonym) values (?,?,?,?,?,?,?,?,?)',
                   [(1, i, 'Baias', 1, 0, 0, 'name', 'names', 0) for i in range(1, 6)]
                   + [(2, i, 'Baiae', 1, 0, 0, 'name', 'names', 0) for i in range(6, 9)])
    # the two labels share a Greek form: Baias is the key with more lines, Baiae the one whose label is the nominative
    db.executemany('insert into entity_labels values (?,?,?,?,?)', [
        (1, 'Baias', 'Baias', 'Βαΐαι', None), (2, 'Baiae', 'Baiae', None, None)])
    db.commit()
    rep = pr.dedupe_promoted(db, log=lambda *_: None)
    assert rep['after'] == 1 and rep['labels_changed'] == 1
    eid, ent_id, label = db.execute("select eid, entity_id, label from entities where source = 'promoted'").fetchone()
    assert ent_id == 'pn:baias' and label == 'Baiae'                                  # the key survives, the label is the heading
    # neither entity has a Greek-script form, so the Greek label stays (the stage 3a behavior)
    assert db.execute('select display_label, display_label_grc from entity_labels where eid = ?', (eid,)).fetchone() == ('Baiae', 'Βαΐαι')


def test_the_label_of_a_split_is_asked_from_its_main_spellings():
    j = {'type': 'place', 'latin': 'Rhodes', 'greek': 'Ῥόδος', 'description': '', 'distinct_names': True,
         'main_forms': ['Rhodopen', 'Rhodopes']}
    assert pr.still_contradicts({'rhodo': j}) == ['rhodo']
    q = pr.label_question('place', [('Rhodopen', 2), ('Rhodopes', 7)], [['Ovid', 'Latin', 'Rhodopes et Haemus']])
    assert 'Rhodopen (2), Rhodopes (7)' in q and 'Type: place' in q
    assert pr.parse_label('{"latin": "Rhodope", "greek": "Ῥοδόπη"}') == ('Rhodope', 'Ῥοδόπη')
    assert pr.parse_label('{"latin": ""}') is None and pr.parse_label('nope') is None
    judgments = {'rhodo': dict(j)}
    assert pr.apply_label_fix(judgments, {'rhodo': ('Rhodope', 'Ῥοδόπη')}) == 1
    assert judgments['rhodo']['latin'] == 'Rhodope' and pr.still_contradicts(judgments) == []
    assert pr.apply_label_fix(judgments, {'rhodo': ('Rhodope', 'Ῥοδόπη')}) == 0         # the same label again is no change


def test_a_second_label_is_accepted_only_when_it_passes_the_tests():
    j = {'type': 'place', 'latin': 'Rhodes', 'greek': 'Ῥόδος', 'description': '', 'distinct_names': True,
         'main_forms': ['Rhodopen', 'Rhodopes']}
    for bad in (('Rhoda', 'Ῥόδα'),                # shares only four letters with the main spellings
                ('Rhodοpe', 'Ῥοδόπη'),            # a Greek omicron inside a Latin label
                ('Rhodope', 'Rhodope')):          # a Latin word as the Greek label
        judgments = {'rhodo': dict(j)}
        assert pr.apply_label_fix(judgments, {'rhodo': bad}) == 0
        assert judgments['rhodo']['latin'] == 'Rhodes' and judgments['rhodo']['greek'] == 'Ῥόδος'    # the earlier label stays


def test_the_case_form_extension_is_off_by_default():
    import inspect
    assert inspect.signature(ei.build_store).parameters['case_forms'].default is False
    assert inspect.signature(el.assemble_matcher).parameters['case_forms'].default is False
    assert inspect.signature(el.build_lemma_matcher).parameters['case_forms'].default is False
