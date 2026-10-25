"""backend/entity_new_works.py: rows for works added after the People & Places store was built are filed
against a copy of the store, and nothing already in the store changes. A synthetic store, no live index."""
import collections
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import entity_index as ei  # noqa: E402
from backend import entity_new_works as nw  # noqa: E402


def test_stem_and_unit():
    assert nw.stem_of('plotinus.enneades.part.3') == 'plotinus.enneades'
    assert nw.stem_of('milton.in_quintum_novembris') == 'milton.in_quintum_novembris'
    assert nw.stem_of('dio_chrysostom.orationes.part.77_78') == 'dio_chrysostom.orationes'
    ids = ['a.b.part.1:fine:0', 'a.b.part.1:prosem:0', 'a.b.part.1:coarse:0', 'c.d:fine:0', 'c.d:coarse:0']
    assert nw.new_unit(ids, ['a.b']) == {'a.b.part.1:prosem:0'}
    assert nw.new_unit(ids, ['c.d']) == {'c.d:fine:0'}


def test_list_candidates_follow_the_stores_decisions():
    attested = {'roma': {1: 5}, 'sinon': {2: 3, 3: 1}, 'alexandra': {4: 2}}
    cands = [(1, 'w:fine:0', 'Roma'), (9, 'w:fine:0', 'Roma'),       # entity 9 never carried the spelling: dropped
             (2, 'w:fine:1', 'Sinon'), (3, 'w:fine:1', 'Sinon'),     # two entities kept: homonym
             (7, 'w:fine:2', 'Novum')]                               # a spelling nobody has seen: the matcher stands
    rows, counts = nw.attribute_list(cands, attested)
    got = {(e, w, f): (h, how) for e, w, f, h, how in rows}
    assert (9, 'w:fine:0', 'Roma') not in got
    assert got[(1, 'w:fine:0', 'Roma')] == (0, 'attested')
    assert got[(2, 'w:fine:1', 'Sinon')][0] == 1 and got[(3, 'w:fine:1', 'Sinon')][0] == 1
    assert got[(7, 'w:fine:2', 'Novum')] == (0, 'unseen')
    assert counts['dropped_spelling_filed_elsewhere'] == 1


def _case_form_of(form, heads):
    f = ei.fold(form)
    return any(f.startswith(ei.fold(h)[:5]) for h in heads) or None


def test_names_go_where_the_store_files_the_spelling():
    rows = [('khild', 'w:fine:0', 'Childeberthi'),     # filed by the store
            ('khild', 'w:fine:1', 'Childeberthum'),    # same key, never seen: the key's only entity
            ('hekat', 'w:fine:2', 'Hecataeus'),        # spelling a hand pass dropped
            ('zzzzz', 'w:fine:3', 'Zzyzx'),            # a key nobody has: new entity
            ('zzzzz', 'w:fine:4', 'Zzyzxum')]
    learned = {ei.fold('Childeberthi'): 10}
    dropped = {ei.fold('Hecataeus')}
    by_key = {'khild': [(10, 40)]}
    placed, new_rows, new_names, counts = nw.attribute_names(
        rows, learned, dropped, by_key, lambda eid: ['Childeberthus'], _case_form_of, lambda s: s)
    assert [(p[0], p[1]) for p in placed] == [(10, 'w:fine:0'), (10, 'w:fine:1')]
    assert counts['left_out_dropped_by_hand_pass'] == 1
    assert {r[0] for r in new_rows} == {'zzzzz'} and set(new_names) == {'zzzzz'}
    assert counts['new_key'] == 2 and counts['learned'] == 1 and counts['by_key'] == 1


def test_spellings_of_one_key_split_into_names():
    forms = collections.Counter({'Abellino': 3, 'Abellinum': 2, 'Abelardus': 4})
    clusters = nw.cluster_forms(forms, lambda form, heads: any(
        ei.fold(form)[:6] == ei.fold(h)[:6] and ei.fold(form) != ei.fold(h) for h in heads) or None, lambda s: s)
    names = [sorted(c) for c in clusters]
    assert ['Abelardus'] in names and ['Abellino', 'Abellinum'] in names


def test_write_rows_adds_and_leaves_old_rows():
    db = sqlite3.connect(':memory:')
    db.executescript(ei.SCHEMA)
    db.execute('alter table mention_rows add column line_ref TEXT')
    db.execute('alter table mention_rows add column form_key TEXT')
    db.execute("insert into entities values (1,'pl:1','place','Roma','list','1','[\"1\"]',NULL,NULL,'roma',1,1)")
    db.execute("insert into windows values (1,'old:fine:0','old','o 1','o 2','la')")
    db.execute("insert into mention_rows values (1,1,'Roma',1,0,0,'lemma','lemma',0,'o 1','roma')")
    before = nw.entities_digest(db)
    old_rows = db.execute('select * from mention_rows').fetchall()
    wmeta = {'new:fine:0': ('la', 'new', 'n 1', 'n 2')}
    stats = nw.write_rows(db, [(1, 'new:fine:0', 'Romae', 0, 'attested')], [], [('zz', 'new:fine:0', 'Zzyzx', 'zzyzx', 'new_key')],
                          {'zz': collections.Counter({'Zzyzx': 1})}, wmeta, lambda tag: tag.split(':')[0],
                          lambda forms: ('Zzyzx', 'Zzyzx', None))
    assert db.execute('select count(*) from windows').fetchone()[0] == 2
    assert db.execute('select count(*) from mention_rows').fetchone()[0] == 3
    assert db.execute('select * from mention_rows where rowid = 1').fetchall() == old_rows
    assert nw.entities_digest(db, max_eid=1) == before
    assert stats['new_entities'][0][1] == 'nm:zz' and db.execute('select max(eid) from entities').fetchone()[0] == 2
