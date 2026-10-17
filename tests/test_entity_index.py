"""backend/entity_index.py: a tiny store built from three synthetic windows, mentions read
back, the stoplist removing a known false positive, the English label parsing and the
lockstep check. No live index is read."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import entity_index as ei  # noqa: E402

KEYS = [
    {'id': 'E0001', 'greek': 'Ῥώμη', 'latin': ['Roma'], 'english': 'Rome', 'type': 'place', 'pleiades': ['423025']},
    {'id': 'E0002', 'greek': 'Ῥώμα', 'latin': ['Romae'], 'english': 'Rome', 'type': 'place', 'pleiades': ['423025']},
    {'id': 'E0003', 'greek': 'Σίνων', 'latin': ['Sinon'], 'english': 'Sinon', 'type': 'person', 'pleiades': []},
]
WINDOWS = [
    ('w:fine:0', 'la', 'w', 'w 1', 'w 2', 'Tum Roma vicit et Sinon fugit.'),
    ('w:fine:1', 'la', 'w', 'w 3', 'w 4', 'Pax in Romae rure, roma minor.'),
    ('w:fine:2', 'la', 'w', 'w 5', 'w 6', 'Nihil hic est.'),
]


def _passage_dir(tmp_path):
    d = tmp_path / 'pi'
    d.mkdir()
    json.dump([w[0] for w in WINDOWS], open(d / 'ids.json', 'w'))
    t = sqlite3.connect(d / 'window_texts.db')
    t.execute('CREATE TABLE window_texts (id TEXT PRIMARY KEY, language TEXT, work TEXT, ref_start TEXT, ref_end TEXT, text TEXT)')
    t.executemany('INSERT INTO window_texts VALUES (?,?,?,?,?,?)', WINDOWS)
    t.commit()
    t.close()
    n = sqlite3.connect(d / 'window_names.db')
    n.execute('CREATE TABLE window_names (id TEXT, k TEXT, form TEXT)')
    n.execute('CREATE TABLE name_df (k TEXT PRIMARY KEY, df INTEGER)')
    n.execute('CREATE TABLE meta (key TEXT, value TEXT)')
    n.executemany('INSERT INTO window_names VALUES (?,?,?)',
                  [('w:fine:0', 'roma', 'Roma'), ('w:fine:0', 'sinon', 'Sinon'), ('w:fine:1', 'roma', 'Romae')])
    n.executemany('INSERT INTO name_df VALUES (?,?)', [('roma', 2), ('sinon', 1)])
    n.execute("INSERT INTO meta VALUES ('windows', '3')")
    n.commit()
    n.close()
    return str(d)


def _stoplist(tmp_path, entities):
    p = tmp_path / 'stop.json'
    json.dump({'entities': entities, 'neighbor_words': {'la': ['pax'], 'grc': [], 'en': []}}, open(p, 'w'))
    return str(p)


def test_build_and_read_back(tmp_path):
    pdir = _passage_dir(tmp_path)
    out = str(tmp_path / 'entities.sqlite')
    counts, _, ents = ei.build_store(KEYS, pdir, out, stoplist_path=_stoplist(tmp_path, {}), log=lambda *_: None)
    # the two Rome keys share a Pleiades id, so they merge into one entity
    assert counts['entities_list'] == 2
    conn = ei.open_store(out)
    rome = ei.mentions_of(conn, 'pl:423025')
    # capital initial required: lower-case "roma" in window 1 does not count
    assert sorted(r[0] for r in rome) == ['w:fine:0', 'w:fine:1']
    assert {r[5] for r in rome} == {'Roma', 'Romae'}
    # Roma has a four-letter stem, so it is not distinctive; "pax" within three tokens confirms window 1
    conf = {r[0]: r[7] for r in rome}
    assert conf['w:fine:1'] == 'neighbor'
    assert conf['w:fine:0'] == 'unconfirmed'
    # the second source: the corpus's own names, linked by name_key
    sinon = ei.mentions_of(conn, 'ln:E0003')
    assert [r[0] for r in sinon] == ['w:fine:0']
    assert ei.mentions_of(conn, 'nm:sinon')[0][0] == 'w:fine:0'
    assert conn.execute("select name_key from entities where entity_id='pl:423025'").fetchone()[0] == 'roma'
    assert ei.find_entities(conn, 'Sinon')[0][0] == 'ln:E0003'
    assert ei.counts_by_work(conn, 'pl:423025') == [('w', 2)]


def test_stoplist_removes_known_false_positive(tmp_path):
    pdir = _passage_dir(tmp_path)
    plain = str(tmp_path / 'a.sqlite')
    stopped = str(tmp_path / 'b.sqlite')
    ei.build_store(KEYS, pdir, plain, stoplist_path=_stoplist(tmp_path, {}), log=lambda *_: None)
    counts, _, _ = ei.build_store(
        KEYS, pdir, stopped, log=lambda *_: None,
        stoplist_path=_stoplist(tmp_path, {'Ῥώμη': {'forms': ['Romae'], 'reason': 'test'}}))
    assert counts['removed_by_stoplist'] == 1
    a = {r[0] for r in ei.mentions_of(ei.open_store(plain), 'pl:423025')}
    b = {r[0] for r in ei.mentions_of(ei.open_store(stopped), 'pl:423025')}
    assert a == {'w:fine:0', 'w:fine:1'}
    assert b == {'w:fine:0'}


def test_english_forms_drop_parenthetical_notes():
    assert ei._english_forms('Arar (river)') == ['Arar']
    assert ei._english_forms('Gortyn(a)') == ['Gortyn']
    assert ei._english_forms('Rhaga(i)/Europos/Ray') == ['Rhaga', 'Europos']
    assert ei._english_forms('Ilium/Troia') == ['Ilium', 'Troia']


def test_lockstep_check_reports_a_store_left_behind(tmp_path):
    pdir = _passage_dir(tmp_path)
    out = str(tmp_path / 'entities.sqlite')
    ei.build_store(KEYS, pdir, out, stoplist_path=_stoplist(tmp_path, {}), log=lambda *_: None)
    assert ei.check_lockstep(out, pdir) == []
    ids = json.load(open(os.path.join(pdir, 'ids.json')))
    json.dump(ids + ['w:fine:3'], open(os.path.join(pdir, 'ids.json'), 'w'))
    problems = ei.check_lockstep(out, pdir)
    assert any('unit_windows' in p for p in problems)
