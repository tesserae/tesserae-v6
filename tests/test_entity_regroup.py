"""People & Places regroup: layer 1 (headings and case forms), the answer parser, the moves and the carve."""
import os
import sqlite3
import sys

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
