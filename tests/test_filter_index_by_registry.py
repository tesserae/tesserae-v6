"""scripts/corpus/filter_index_by_registry.py on a throwaway index."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'scripts', 'corpus'))

import filter_index_by_registry as fir  # noqa: E402


def test_filter_removes_rows_and_recomputes_doc_freq(tmp_path):
    db = str(tmp_path / 'cop_index.db')
    con = sqlite3.connect(db)
    con.executescript('''
        create table texts (text_id integer primary key, filename text unique);
        create table lines (text_id integer, ref text, content text);
        create table postings (lemma text, text_id integer, ref text, positions text);
        create table lemma_doc_freq (lemma text primary key, df integer);
        insert into texts values (1, 'sahidica.john.tess'), (2, 'sahidic.genesis.tess');
        insert into lines values (1, 'a', 'x'), (2, 'b', 'y');
        insert into postings values ('p', 1, 'a', '[1]'), ('p', 2, 'b', '[1]'), ('q', 1, 'a', '[2]');
        insert into lemma_doc_freq values ('p', 2), ('q', 1);
    ''')
    con.commit()
    con.close()
    report = fir.filter_index(db, {'sahidica.john'})
    assert report['texts_removed'] == 1
    assert report['after'] == {'texts': 1, 'lines': 1, 'postings': 1, 'lemma_doc_freq': 1}
    con = sqlite3.connect(db)
    assert con.execute('select lemma, df from lemma_doc_freq').fetchall() == [('p', 1)]
    assert [f for (f,) in con.execute('select filename from texts')] == ['sahidic.genesis.tess']
