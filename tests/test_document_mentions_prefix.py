"""build_document_mentions with doc_prefix and rows_out (backend/entity_extras.py), added for the review of
#1089: it reads only the documents whose id starts with the prefix, writes nothing to the store, appends the
candidate rows to rows_out, and treats a LIKE wildcard in the prefix as an ordinary character. Fixtures only."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend import entity_extras as extras  # noqa: E402
from backend import entity_index as ei  # noqa: E402

# Every document names Athens, so a row appears for every document that is read.
DOCS = ['aio:A1', 'aio:A2', 'edr:B1', 'a%o:C1', 'a_o:D1', 'aioXE1']


@pytest.fixture
def fixture_paths(tmp_path):
    store = str(tmp_path / 'entities.sqlite')
    db = sqlite3.connect(store)
    db.executescript(ei.SCHEMA)
    db.execute('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)',
               (10, 'ln:E1', 'place', 'Athens', 'list', None, None, None, None, None, 1, 0))
    db.execute('insert into variants values (?,?,?,?,?)', (10, 'αθηναι', 'grc', 'form', 'list'))
    db.execute("insert into meta values ('document_mentions', '{}')")
    db.executescript(extras.DOC_SCHEMA)
    db.execute("insert into document_mentions values (10, 'old:Z', 'grc', 'αθηναι', 'form', 0)")
    db.commit()
    db.close()
    d = tmp_path / 'docs'
    d.mkdir()
    c = sqlite3.connect(str(d / 'grc_documents_index.db'))
    c.executescript('''
      create table texts (text_id integer primary key, filename text unique, author text, title text, line_count integer);
      create table lines (text_id integer, ref text, content text, lemmas text, tokens text, primary key (text_id, ref));
    ''')
    c.execute("insert into texts values (1, 'x.tess', 'x', 'X', 6)")
    for ref in DOCS:
        c.execute('insert into lines values (1, ?, ?, ?, ?)', (ref, 'Ἀθῆναι', '[]', json.dumps(['Ἀθῆναι'])))
    c.commit()
    c.close()
    return store, str(d)


def snapshot(store):
    db = sqlite3.connect(store)
    try:
        return (db.execute('select * from document_mentions order by 1, 2').fetchall(),
                db.execute('select * from meta order by 1').fetchall(),
                db.execute("select count(*) from sqlite_master where name = 'ix_dm_eid'").fetchone()[0])
    finally:
        db.close()


def run(store, docs, prefix):
    rows = []
    counts = extras.build_document_mentions(store, docs, log=lambda *a: None, doc_prefix=prefix, rows_out=rows)
    return rows, counts


def test_prefix_reads_only_its_documents_and_writes_nothing_to_the_store(fixture_paths):
    store, docs = fixture_paths
    before = snapshot(store)
    rows, counts = run(store, docs, 'aio:')
    assert {r[1] for r in rows} == {'aio:A1', 'aio:A2'}        # not edr:B1, not aioXE1
    assert all(r[1].startswith('aio:') for r in rows)
    assert all(r[0] == 10 and r[2] == 'grc' and r[3] == 'αθηναι' for r in rows)
    assert counts['candidate_rows'] == len(rows) == 2
    assert counts['documents_scanned_grc'] == 2
    assert snapshot(store) == before                            # table, meta and index untouched


def test_an_underscore_in_the_prefix_is_not_a_wildcard(fixture_paths):
    store, docs = fixture_paths
    rows, _ = run(store, docs, 'a_o:')
    assert {r[1] for r in rows} == {'a_o:D1'}                   # unescaped, _ would also match aio:


def test_a_percent_sign_in_the_prefix_is_not_a_wildcard(fixture_paths):
    store, docs = fixture_paths
    rows, _ = run(store, docs, 'a%')
    assert {r[1] for r in rows} == {'a%o:C1'}                   # unescaped, a% would match all but edr:B1


def test_a_backslash_in_the_prefix_is_not_an_escape(fixture_paths):
    store, docs = fixture_paths
    rows, _ = run(store, docs, 'a\\')
    assert rows == []


def test_rows_are_appended_to_the_list_given(fixture_paths):
    store, docs = fixture_paths
    rows = [('sentinel',)]
    extras.build_document_mentions(store, docs, log=lambda *a: None, doc_prefix='edr:', rows_out=rows)
    assert rows[0] == ('sentinel',) and [r[1] for r in rows[1:]] == ['edr:B1']


def test_a_prefix_without_a_list_to_fill_is_refused(fixture_paths):
    store, docs = fixture_paths
    with pytest.raises(ValueError):
        extras.build_document_mentions(store, docs, log=lambda *a: None, doc_prefix='aio:')
