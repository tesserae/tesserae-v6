"""People & Places regroup: layer 1 (headings and case forms), the answer parser, the moves and the carve."""
import os
import sqlite3
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import entity_regroup as rg  # noqa: E402

SCHEMA = '''
create table entities (eid integer primary key, entity_id text unique, type text, label text, source text,
  pleiades_id text, pleiades_candidates text, prosopography_id text, homonym_group text, name_key text,
  distinctive integer, n_windows integer);
create table variants (eid integer, form text, language text, role text, source text);
create table windows (wid integer primary key, window_id text, work text, ref_start text, ref_end text, language text);
create table mention_rows (eid integer, wid integer, form text, cap integer, nb integer, ds integer, confidence text,
  matcher text, homonym integer, line_ref text, form_key text);
create table entity_labels (eid integer primary key, display_label text, display_label_la text,
  display_label_grc text, description text);
create table entity_merges (eid integer primary key, list_eid integer);
create table search_names (eid integer, name text, source text);
create table document_mentions (eid integer, doc_id text, language text, form text, kind text, adjective integer);
'''


def store():
    db = sqlite3.connect(':memory:')
    db.executescript(SCHEMA)
    db.execute("insert into entities values (1, 'pn:silan', 'person', 'Silanus', 'promoted', null, null, null, null, 'silan', 0, 0)")
    db.execute("insert into entities values (2, 'nm:silan2', 'name', 'Silanion', 'names', null, null, null, null, 'silan', 0, 0)")
    db.execute("insert into entity_labels values (1, 'Silanus', 'Silanus', 'Σιλανός', null)")
    db.execute("insert into entity_labels values (2, 'Silanion', 'Silanion', null, null)")
    wid = 0
    for eid, form, n in ((1, 'Silanus', 3), (1, 'Silano', 2), (1, 'Σιλανοῦ', 1), (1, 'Silanion', 2), (1, 'Silanoque', 1),
                         (2, 'Silanion', 1)):
        for _ in range(n):
            wid += 1
            db.execute('insert into windows values (?,?,?,?,?,?)', (wid, f'w{wid}', 'work', 'a', 'b', 'la'))
            db.execute('insert into mention_rows values (?,?,?,0,0,0,?,?,0,?,?)', (eid, wid, form, 'high', 'stem', 'r', form.lower()))
    return db


def test_case_forms_enclitic_and_greek_stay_and_a_different_name_is_a_candidate():
    db = store()
    acc, rest = rg.layer1(db, 1, {'Silanus': 3, 'Silano': 2, 'Σιλανοῦ': 1, 'Silanion': 2, 'Silanoque': 1})
    assert rest == {'Silanion'}
    assert acc == {'Silanus', 'Silano', 'Σιλανοῦ', 'Silanoque'}


def test_lunate_sigma_is_a_sigma():
    assert 'ϲ' not in rg.prep('Κρεμαϲτή')


def test_protected_entities():
    assert rg.protected('nm:lauin:main') and rg.protected('pn:lauinia') and rg.protected('pl:393444')
    assert rg.protected('pn:lauinium')
    assert not rg.protected('pn:silan')


def test_parse_answer():
    assert rg.parse_answer('One sentence.\nANSWER: DIFFERENT')[0] == 'DIFFERENT'
    assert rg.parse_answer('x\nANSWER: same')[0] == 'SAME'
    assert rg.parse_answer('no verdict')[0] is None


def test_a_different_group_moves_to_the_one_entity_it_is_a_case_form_of():
    db = store()
    db.execute('delete from entities where eid = 2')
    db.execute('delete from mention_rows where eid = 2')
    db.execute("insert into entities values (3, 'pn:silanion', 'person', 'Silanion', 'promoted', null, null, null, null, 'silan', 0, 0)")
    db.execute("insert into entity_labels values (3, 'Silanion', 'Silanion', null, null)")
    rep = rg.apply_differences(db, [('pn:silan', 'sila', {'Silanion': 2})])
    assert rep['moved_groups'] == 1 and rep['rows_moved'] == 2 and rep['carved_groups'] == 0
    assert db.execute("select count(*) from mention_rows where eid = 3").fetchone()[0] == 2
    assert db.execute("select count(*) from mention_rows where eid = 1 and form = 'Silanion'").fetchone()[0] == 0


def test_a_different_group_with_no_home_is_carved_into_a_new_name():
    db = store()
    db.execute('delete from entities where eid = 2')
    db.execute('delete from mention_rows where eid = 2')
    rep = rg.apply_differences(db, [('pn:silan', 'sila', {'Silanion': 2})])
    assert rep['carved_groups'] == 1 and rep['rows_carved'] == 2
    row = db.execute("select eid, entity_id, type, source, label from entities where entity_id like 'nm:silan%:r%'").fetchone()
    assert row[1] == 'nm:silan:r1' and row[2:] == ('name', 'names', 'Silanion')
    assert db.execute('select count(*) from mention_rows where eid = ?', (row[0],)).fetchone()[0] == 2
    assert db.execute('select display_label from entity_labels where eid = ?', (row[0],)).fetchone()[0] == 'Silanion'
    assert db.execute('select n_windows from entities where eid = 1').fetchone()[0] == 7


def test_protected_group_is_skipped():
    db = store()
    db.execute("update entities set entity_id = 'nm:lauin:main' where eid = 1")
    rep = rg.apply_differences(db, [('nm:lauin:main', 'sila', {'Silanion': 2})])
    assert rep['groups'] == 0 and rep['skipped_protected'] == 1


def test_letter_check_and_forced_answer():
    """The computed consonant rule (second pass, 2026-10-22): a missing consonant makes DIFFERENT whatever the
    model said, ordinary variants and case endings do not, and the -que enclitic is taken off."""
    from backend import entity_regroup as rg
    assert rg.consonants_differ('Ἑρμίππου', {'Herippus'})
    assert not rg.consonants_differ('Caipha', {'Caiaphas'})
    assert not rg.consonants_differ('Caipham', {'Caiaphas', 'Καϊάφας'})
    assert not rg.consonants_differ('Romanoque', {'Romano'})
    assert not rg.consonants_differ('Μυκάλην', {'Mycale (mountain)'})
    same = 'SPELLING: x\nCONSONANTS: differ\nEXCEPTION: no\nANSWER: SAME'
    assert rg.final_answer4(same, 'Ἑρμίππου', {'Herippus'}) == 'DIFFERENT'
    yes = same.replace('EXCEPTION: no', 'EXCEPTION: yes')
    assert rg.final_answer4(yes, 'Φοίνισσαι', {'Phoenicians'}) == 'SAME'
    assert rg.final_answer4('no answer here', 'x', {'y'}) is None


# ---------------------------------------------------------------- third pass (2026-10-24)

def _entry(db, eid, entity_id, label, name_key, rows):
    db.execute("insert into entities values (?, ?, 'person', ?, 'promoted', null, null, null, null, ?, 0, 0)",
               (eid, entity_id, label, name_key))
    db.execute('insert into entity_labels values (?, ?, ?, null, null)', (eid, label, label))
    for form, n in rows.items():
        for _ in range(n):
            wid = db.execute('select coalesce(max(wid), 0) + 1 from windows').fetchone()[0]
            db.execute('insert into windows values (?,?,?,?,?,?)', (wid, f'x{wid}', 'work', 'a', 'b', 'la'))
            db.execute('insert into mention_rows values (?,?,?,0,0,0,?,?,0,?,?)', (eid, wid, form, 'high', 'stem', 'r', form.lower()))


def test_hebrew_accent_marks_are_folded_away():
    """Adonai written with Hebrew accent marks and vowel points is the same spelling as the unmarked Hebrew name."""
    plain = 'אדני'
    marked1 = 'אֲדֹנָ֣י'
    marked2 = '\u05d0\u05b2\u05d3\u05b9\u05e0\u05b4\u05a3\u05d9'
    assert rg.prep('אֲֽדֹֿנָ֑י') == plain
    assert rg.prep('Anton|ino') == 'Antonino' and rg.prep('Anton- ino') == 'Antonino'
    db = store()
    _entry(db, 10, 'pn:adonai', 'Adonai', plain, {marked1: 3, marked2: 2})
    acc, rest = rg.layer1(db, 10, dict(db.execute('select form, count(*) from mention_rows where eid = 10 group by form')))
    assert not rest and len(acc) == 2
    shalom = 'שלום'     # another Hebrew word is still a candidate
    _entry(db, 11, 'pn:adonai2', 'Adonai', plain, {shalom: 2})
    assert rg.layer1(db, 11, {shalom: 2})[1] == {shalom}


class _Lines:
    def __init__(self, texts):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('create table window_texts (id text, language text, work text, ref_start text, ref_end text, text text)')
        for k, t in texts.items():
            self.db.execute('insert into window_texts values (?, ?, ?, ?, ?, ?)', (k, 'la', 'w', 'a', 'b', t))


def test_a_word_broken_across_a_line_stays_with_its_heading():
    db = store()
    _entry(db, 12, 'nm:anton', 'Antoninus', 'anton', {'Antoninus': 3, 'Anton': 2})
    lines = _Lines({'x4': 'et Hadrianum Anton-   inus reservavit', 'x5': 'ut ille Anton|inus esse'})
    # the two Anton rows sit in windows x4 and x5
    db.execute("update windows set window_id = 'x4' where wid = (select min(wid) from mention_rows where eid = 12 and form = 'Anton')")
    db.execute("update windows set window_id = 'x5' where wid = (select max(wid) from mention_rows where eid = 12 and form = 'Anton')")
    pairs = {'Antoninus': 3, 'Anton': 2}
    assert rg.layer1(db, 12, pairs)[1] == {'Anton'}               # without the lines it is a candidate
    assert rg.layer1(db, 12, pairs, lines)[1] == set()            # with them it is Antoninus broken by the line
    other = _Lines({'x4': 'urbs Anton ibat', 'x5': 'Anton ibat'})
    assert rg.layer1(db, 12, pairs, other)[1] == {'Anton'}        # a bare Anton stays a candidate


def test_greek_and_latin_spellings_of_one_hebrew_name_are_variants():
    assert rg.is_variant('Abessalon', {'Absalom'})
    assert rg.is_variant('Samuhel', {'Samuel'})
    assert rg.is_variant('Caipha', {'Caiaphas'})
    assert rg.is_variant('Hiezechiel', {'Ezechiel'})
    assert rg.is_variant('Gedeona', {'Gideon'})


def test_a_derivational_suffix_is_not_a_variant():
    assert not rg.is_variant('Hecataeus', {'Hecate'})
    assert not rg.is_variant('Maximin', {'Maximianus'})
    assert not rg.is_variant('Graeculus', {'Graeci'})
    assert not rg.is_variant('Hermippus', {'Herippus'})


def test_hecataeus_is_not_accepted_through_a_chain_of_case_forms():
    db = store()
    _entry(db, 13, 'pn:ekate', 'Hecate', 'ekate', {'Hecate': 5, 'Hecates': 3, 'Hecaten': 2, 'Hecatae': 2, 'Hecataei': 2,
                                                      'Hecataeus': 4, 'Hecataeo': 3})
    pairs = dict(db.execute('select form, count(*) from mention_rows where eid = 13 group by form'))
    acc, rest = rg.layer1(db, 13, pairs)
    assert {'Hecataeus', 'Hecataeo', 'Hecataei'} <= rest
    assert {'Hecate', 'Hecates', 'Hecaten', 'Hecatae'} <= acc


def test_a_case_form_of_a_heading_with_its_own_suffix_is_kept():
    db = store()
    _entry(db, 14, 'pn:caecilius', 'Caecilius', 'kaeci', {'Caecilius': 5, 'Caecilii': 2, 'Caecilio': 2, 'Caecilianus': 1})
    pairs = dict(db.execute('select form, count(*) from mention_rows where eid = 14 group by form'))
    acc, rest = rg.layer1(db, 14, pairs)
    assert {'Caecilius', 'Caecilii', 'Caecilio'} <= acc


# ---------------------------------------------------------------- third pass, second round

def test_a_spelling_equal_to_the_entrys_own_greek_label_stays():
    """Samples 28 and 36 of the third pass: the Greek label of the entry is the spelling itself."""
    db = store()
    agr = 'Ἀγριοφάγων'
    _entry(db, 20, 'nm:agrio', 'Agriofaguitai', 'agrio', {'Agriofaguitai': 1, agr: 1})
    db.execute('update entity_labels set display_label_grc = ? where eid = 20', (agr,))
    assert rg.layer1(db, 20, {'Agriofaguitai': 1, agr: 1})[1] == set()
    # a Greek plural or accusative of the same ethnic stem stays with its people
    pl = 'Ἀγριοφάγοι'
    acc = 'Ἀγριοφάγους'
    assert rg.layer1(db, 20, {pl: 1, acc: 1})[1] == set()
    # another Greek name is still a candidate
    other = 'Σκύθαι'
    assert rg.layer1(db, 20, {other: 1})[1] == {other}
    _entry(db, 21, 'nm:farit', 'Pharitae', 'farit', {'Pharitae': 2})
    pha = 'Φαρίτιδος'
    db.execute('update entity_labels set display_label_grc = ? where eid = 21', (pha,))
    assert rg.layer1(db, 21, {'Pharitae': 2, pha: 1})[1] == set()


def test_case_forms_of_a_split_off_heading_go_with_it():
    """Maximin is carved from Maximianus: Maximinum, Maximini and Maximine, case forms of the new heading
    Maximinus, move too; Maximiano stays."""
    db = store()
    _entry(db, 22, 'pn:maximian', 'Maximianus', 'maksi',
           {'Maximianus': 6, 'Maximiano': 3, 'Maximinus': 8, 'Maximinum': 3, 'Maximini': 2, 'Maximine': 1})
    db.execute("insert into search_names values (22, 'Maximinus', 'model')")
    rep = rg.apply_differences(db, [('pn:maximian', 'maximin', {'Maximinus': 8})])
    assert rep['carved_groups'] == 1 and rep['rows_carved'] == 14
    new = db.execute("select eid from entities where entity_id like 'nm:maksi%:r%'").fetchone()[0]
    got = {f for (f,) in db.execute('select distinct form from mention_rows where eid = ?', (new,))}
    assert got == {'Maximinus', 'Maximinum', 'Maximini', 'Maximine'}
    left = {f for (f,) in db.execute('select distinct form from mention_rows where eid = 22')}
    assert left == {'Maximianus', 'Maximiano'}
    assert db.execute("select eid from search_names where name = 'Maximinus'").fetchone()[0] == new


def test_audit_limited_to_listed_entities():
    db = store()
    everything = rg.audit(db)['groups']
    assert {g[0] for g in everything} == {1}
    assert rg.audit(db, only={'pn:silan'})['groups'] == everything
    assert rg.audit(db, only={'nm:silan2'})['groups'] == []


def test_near_variant_final_m_n_and_one_inner_letter():
    assert rg.near_variant('Sichen', {'Sichem'})
    assert rg.near_variant('Sichem', {'Sichen'})
    assert rg.near_variant('Philinus', {'Philonus'})          # one letter inside an identical stem
    assert not rg.near_variant('Fulvia', {'Fulvius'})         # the last letter differs: another name
    assert not rg.near_variant('Marcus', {'Marcius'})         # an inserted vowel is another name
    assert rg.near_variant('Ἐδόβιχον', {'Ἐδόβινχον'})         # an inserted n inside the stem
    assert not rg.near_variant('Roma', {'Roma'})


def test_place_adjective_stays_with_its_place():
    assert rg.place_adjective_of('Euboicorum', {'Euboea'}, 'place')
    assert rg.place_adjective_of('Αἰγαίαις', {'Aegean Sea'}, 'place')
    assert rg.place_adjective_of('Agennensibus', {'Agenneton'}, 'name')
    assert rg.place_adjective_of('Ἀλεξανδρέας', {'Alexandrinum'}, 'name')
    assert rg.place_adjective_of('Δαλμάτιος', {'Dalmatia'}, 'place')
    assert rg.place_adjective_of('Ἰθακησία', {'Ithaces'}, 'name')
    assert not rg.place_adjective_of('Maximinus', {'Maximianus'}, 'person')       # a person entry never qualifies
    assert not rg.place_adjective_of('Maximinus', {'Maximianus'}, 'name')         # and a longer stem is another name
    assert not rg.place_adjective_of('Hecataeus', {'Hecate'}, 'deity')


def test_two_adjective_stems_differing_by_a_vowel_match():
    assert rg.place_adjective_of('Neustriensibus', {'Neustria'}, 'name')
    assert rg.place_adjective_of('Namnitico', {'Ναμνιτῶν'}, 'name')
    assert not rg.place_adjective_of('Maximinus', {'Maximianus'}, 'name')


def test_adjective_genitive_plural_and_english_adjective():
    assert rg.place_adjective_of('Norwegensium', {'Norwegia'}, 'name')
    assert rg.place_adjective_of('Delphic', {'Delphi'}, 'place')
    assert not rg.place_adjective_of('Delphic', {'Delphi'}, 'person')


def test_adjective_in_ae_stays_with_its_place():
    assert rg.place_adjective_of('Samosatenae', {'Samosatum'}, 'name')


def test_decision_sets_a_heading_and_moves_rows():
    db = store()
    done = rg.apply_decisions(db, [{'id': 'd1', 'entity_id': 'pn:silan', 'heading': 'Silanos', 'move_forms': ['Silanion'],
                                    'reason': 'test'}], log=lambda *_a: None)
    assert done == ['d1']
    assert db.execute("select label from entities where entity_id = 'pn:silan'").fetchone()[0] == 'Silanos'
    assert db.execute("select display_label from entity_labels where eid = 1").fetchone()[0] == 'Silanos'
    left = [f for (f,) in db.execute('select distinct form from mention_rows where eid = 1')]
    assert 'Silanion' not in left


def test_decisions_only_mode_runs_nothing_else(tmp_path, monkeypatch):
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location('regroup_names', os.path.join(os.path.dirname(__file__), '..', 'scripts', 'entities', 'regroup_names.py'))
    rn = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rn)
    path = str(tmp_path / 'e.sqlite')
    sqlite3.connect(path).close()
    called = []
    monkeypatch.setattr(rn, 'run_decisions_only', lambda db, a: called.append(a.decisions))
    monkeypatch.setattr(rn, 'run_pass3', lambda db, a: called.append('pass3'))
    monkeypatch.setattr('sys.argv', ['regroup_names.py', path, '--decisions-only', '--decisions', 'x.json'])
    rn.main()
    assert called == ['x.json']


# ---- fifth rules (2026-10-25): Greek forms of a name the host carries, own forms of the host, the line lookup

def test_greek_form_of_a_latin_heading_stays():
    assert rg.greek_form_of('Δοροστόλῳ', {'Dorostorus'})            # one inner letter of the stem
    assert rg.greek_form_of('Melampodem', {'Melampus'})              # third-declension stem melamp + od
    assert rg.greek_form_of('Garamum', {'Garamantes'})               # garam + ant
    assert not rg.greek_form_of('Σύροι', {'Syros'})                   # four letters do not vouch (Syrians, the island)
    assert not rg.greek_form_of('Ἰωβιανός', {'Iobiaco'})              # a changed letter needs eight
    assert rg.greek_form_of('Ζανός', {'Zeus'})                       # the lexical pair table, Doric genitive
    assert not rg.greek_form_of('Maximinus', {'Maximianus'})          # another name
    assert not rg.greek_form_of('Fulvia', {'Fulvius'})
    assert not rg.greek_form_of('Silanion', {'Silanus'})
    assert not rg.greek_form_of('Hecataeus', {'Hecate'})


def test_lexical_pair_table_is_read_from_its_file():
    assert rg.LEXICAL_PAIRS
    assert rg.mb._norm(rg.prep('Ζανός')) in rg.LEXICAL_PAIRS


def store_with_stray_heading():
    """A name entry whose heading is a stray form (Cavelle) beside its other spellings (Cavelonensis, Cavellionensim)."""
    db = sqlite3.connect(':memory:')
    db.executescript(SCHEMA)
    db.execute("insert into entities values (1, 'nm:kauel', 'name', 'Cavelle', 'names', null, null, null, null, 'kauel', 0, 0)")
    db.execute("insert into entity_labels values (1, 'Cavelle', 'Cavelle', null, null)")
    wid = 0
    for form, n in (('Cavelle', 2), ('Cavelonensis', 1), ('Cavellionensim', 2), ('Cavellonum', 1)):
        for _ in range(n):
            wid += 1
            db.execute('insert into windows values (?,?,?,?,?,?)', (wid, f'w{wid}', 'work', 'a', 'b', 'la'))
            db.execute('insert into mention_rows values (?,?,?,0,0,0,?,?,0,?,?)', (1, wid, form, 'high', 'stem', 'r', form.lower()))
    return db


def test_place_adjective_matches_the_hosts_own_forms_not_only_its_heading():
    db = store_with_stray_heading()
    own = rg.own_forms(db, 1)
    assert 'Cavellionensim' in own and 'Cavelonensis' in own
    assert not rg.place_adjective_of('Cavellonum', {'Cavelle'}, 'name')          # the heading alone does not keep it
    out = rg.keep_by_rules(db, 'nm:kauel', {'Cavellonum': 1, 'Cavelonensis': 1})
    assert 'Cavellonum' in out or 'Cavelonensis' in out
    assert 'place adjective (own form)' in out.values()


def test_find_form_matches_decomposed_accents_and_misplaced_marks():
    # the text writes the accent as a separate combining mark, and a breathing before its letter
    assert rg.find_form('ἀρχομένου Μαρωνίδος ἔμπλεον', 'Μαρωνίδος') is not None
    nfd = unicodedata.normalize('NFD', 'ἐπὶ Κυδωνιάτιδος ἤγγειλαν')
    assert rg.find_form(nfd, 'Κυδωνιάτιδος') is not None
    t = 'ἐν ̓Ολυμπίοισί́ τε'
    span = rg.find_form(t, 'Ὀλυμπίοισί')
    assert span is not None and t[span[0]:span[1]].startswith('Ολυμπ')
    assert t[span[1]:].startswith(' τε')           # the stray accent after the last letter is inside the span
    assert '⟦' in rg.mark(t, 'Ὀλυμπίοισί')
    assert rg.find_form('nothing here', 'Μαρωνίδος') is None


def test_the_five_no_line_forms_find_a_line():
    class FakeLines:
        def __init__(self, text):
            self.text = text
            self.db = sqlite3.connect(':memory:')
            self.db.execute('create table window_texts (id text, text text)')

        def line(self, work, ref, form):
            return self.text if rg.find_form(self.text, form) else None

    texts = {
        'Μαρωνίδος': unicodedata.normalize('NFD', 'τῆς πολιῆς τόδε σῆμα Μαρωνίδος, ἧς ἐπὶ τύμβῳ'),
        'Ὀλυμπίοισί': 'ἐν ̓Ολυμπίοισί́ τε καὶ βαθυκόλπου',
        'Κυδωνιάτιδος': unicodedata.normalize('NFD', 'ἐκ τῆς Κυδωνιάτιδος ἤγγειλαν'),
        'Δίναμις': 'ἡ τοῦ Θεοῦ Δίναμις ὁ Λόγος',
        'Ἰθακησία': unicodedata.normalize('NFD', 'ἡ Ἰθακησία χώρα'),
    }
    for form, text in texts.items():
        db = sqlite3.connect(':memory:')
        db.executescript(SCHEMA)
        db.execute("insert into entities values (1, 'nm:x', 'name', 'Other', 'names', null, null, null, null, 'x', 0, 0)")
        db.execute("insert into entities values (2, 'nm:y', 'name', 'Held', 'names', null, null, null, null, 'y', 0, 0)")
        db.execute('insert into windows values (1, ?, ?, ?, ?, ?)', ('w1', 'work', 'a', 'b', 'grc'))
        # the rows sit under entry 2, the split's destination is entry 1 (a carve with no rows of its own)
        db.execute('insert into mention_rows values (2, 1, ?, 0, 0, 0, ?, ?, 0, ?, ?)', (form, 'high', 'stem', 'r', form.lower()))
        got = rg.example_lines(db, FakeLines(text), 1, [form], n=1)
        assert got and '⟦' in got[0], form


def test_malformed_or_missing_pair_file_warns_and_gives_an_empty_table(tmp_path, caplog):
    bad = tmp_path / 'pairs.json'
    bad.write_text('{"pairs": [["Ζανός"', encoding='utf-8')
    with caplog.at_level('WARNING', logger=rg.__name__):
        assert rg._load_pairs(str(bad)) == {}
        assert rg._load_pairs(str(tmp_path / 'missing.json')) == {}
    assert str(bad) in caplog.text and 'missing.json' in caplog.text
    assert rg._load_pairs()                      # the real file still loads


def _host(rows, label, entity_id='pn:test', kind='person'):
    db = sqlite3.connect(':memory:')
    db.executescript(SCHEMA)
    _entry(db, 1, entity_id, label, 'test', rows)
    db.execute('update entities set type = ? where eid = 1', (kind,))
    return db


def test_a_latin_case_form_of_an_own_spelling_stays():
    db = _host({'Godigisclus': 1, 'Godigisilus': 2, 'Godigiselus': 1, 'Godigiselo': 1, 'Godigisili': 1, 'Godigisilo': 1},
               'Godigisclus', 'nm:godig')
    out = rg.keep_by_rules(db, 'nm:godig', {'Godigisili': 1, 'Godigisilo': 1})
    assert out == {'Godigisili': 'case form of own spelling', 'Godigisilo': 'case form of own spelling'}
    db = _host({'Attila': 5, 'Attilae': 1, 'Attilanem': 1}, 'Attila', 'pn:attil')
    assert rg.keep_by_rules(db, 'pn:attil', {'Attilanem': 1}) == {'Attilanem': 'case form of own spelling'}
    assert rg.case_form_of_own('Scipionem', {'Scipio'})


def test_case_form_rule_does_not_hold_two_names_of_one_stem_family_together():
    assert not rg.case_form_of_own('Fulvia', {'Fulvius'})
    assert not rg.case_form_of_own('Maximinus', {'Maximianus', 'Maximiani'})
    assert not rg.case_form_of_own('Hadrianus', {'Hadria'})            # nominative: no extension
    assert not rg.case_form_of_own('Marcellus', {'Marcus', 'Marcum'})
    db = _host({'Attila': 3, 'Attilanem': 1, 'Attilanus': 1}, 'Attila', 'pn:attil')
    # the other spelling of the same group is not an own spelling
    assert rg.keep_by_rules(db, 'pn:attil', {'Attilanem': 1, 'Attilanus': 1}, suspect={'Attilanus'}).get('Attilanem')


def test_a_misprint_of_a_spelling_carved_in_the_same_pass_joins_that_entry():
    db = _host({'Κοντοπορίαν': 3, 'Κοντοστέγανον': 1, 'Kontostephanos': 2}, 'Κοντοπορίαν', 'nm:konto', 'name')
    rep = rg.apply_differences(db, [('nm:konto', 'a', {'Kontostephanos': 2}), ('nm:konto', 'b', {'Κοντοστέγανον': 1})], cap=None)
    assert rep['carved_groups'] == 1 and rep['redirect_rule']['same_pass'] == 1
    ids = db.execute("select eid from entities where entity_id like 'nm:konto:r%'").fetchall()
    assert len(ids) == 1
    assert {f for (f,) in db.execute('select form from mention_rows where eid = ?', (ids[0][0],))} == {'Kontostephanos', 'Κοντοστέγανον'}
    assert db.execute('select label from entities where eid = ?', (ids[0][0],)).fetchone()[0] == 'Kontostephanos'
    # the other way round: the misprint carved first, the right spelling joins it, and the heading becomes the commonest
    db = _host({'Κοντοπορίαν': 3, 'Κοντοστέγανον': 1, 'Kontostephanos': 2}, 'Κοντοπορίαν', 'nm:konto', 'name')
    rep = rg.apply_differences(db, [('nm:konto', 'b', {'Κοντοστέγανον': 1}), ('nm:konto', 'a', {'Kontostephanos': 2})], cap=None)
    assert rep['carved_groups'] == 1
    assert db.execute("select label from entities where entity_id like 'nm:konto:r%'").fetchone()[0] == 'Kontostephanos'


def test_a_variant_of_a_heading_of_its_host_stays_and_one_of_an_existing_entity_moves_there():
    db = _host({'Ἰερουσαλήμ': 3, 'Ἱερουτσαλήμ': 1}, 'Ἰερουσαλήμ', 'nm:ierou:r1', 'name')
    rep = rg.apply_differences(db, [('nm:ierou:r1', 'a', {'Ἱερουτσαλήμ': 1})], cap=None)
    assert rep['carved_groups'] == 0 and rep['redirect_rule']['stay'] == 1
    assert db.execute("select count(*) from mention_rows where eid = 1").fetchone()[0] == 4
    # the host's heading is itself a misprint (Ἰερουσαήμ): the spelling goes to the Jerusalem entry
    db = _host({'Ἰερουσαήμ': 1, 'Ἱερουτσαλήμ': 1}, 'Ἰερουσαήμ', 'nm:ierou:r1', 'name')
    _entry(db, 2, 'pn:hieru', 'Jerusalem', 'hieru', {'Jerusalem': 4})
    rep = rg.apply_differences(db, [('nm:ierou:r1', 'a', {'Ἱερουτσαλήμ': 1})], cap=None)
    assert rep['carved_groups'] == 0 and rep['redirect_rule']['existing'] == 1
    assert db.execute("select count(*) from mention_rows where eid = 2").fetchone()[0] == 5


def test_other_names_are_still_carved():
    db = _host({'Fulvius': 3, 'Fulvia': 1}, 'Fulvius', 'pn:fulv')
    rep = rg.apply_differences(db, [('pn:fulv', 'a', {'Fulvia': 1})], cap=None)
    assert rep['carved_groups'] == 1 and sum(rep['redirect_rule'].values()) == 0
