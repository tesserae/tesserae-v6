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
