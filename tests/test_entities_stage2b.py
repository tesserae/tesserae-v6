"""Mentions stage 2b: corpus names beside the list entities, near spellings, one row per matched
line, and the inscriptions and papyri. A fixture store built from the real schema, a fixture
documents index with two documents, no live index."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend import entity_extras as extras  # noqa: E402
from backend import entity_index as ei  # noqa: E402
from backend import passage_index  # noqa: E402
from backend import window_texts  # noqa: E402
from backend import documents as docs  # noqa: E402
from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import entities as ent  # noqa: E402
from backend.entity_lemma_audit import adjective_form  # noqa: E402

P = f'{API_PREFIX}/entities' if API_PREFIX else '/entities'

TEXTS = {'martial:w1': 'Primus in his Mentor, dum facit illa, bibit.', 'martial:w2': 'Primus in his Mentor, dum facit illa, bibit.',
         'livy:w3': 'Rusellanum agrum populabantur.'}
ORDS = {'14.88.1': 0, '14.93.2': 5, '14.91.1': 3, '14.96.2': 8}      # w1 spans 0-5, w2 spans 3-8


def _fixture_documents(tmp_path):
    d = tmp_path / 'docs'
    d.mkdir()
    c = sqlite3.connect(str(d / 'la_documents_index.db'))
    c.executescript('''
      create table texts (text_id integer primary key, filename text unique, author text, title text, line_count integer);
      create table lines (text_id integer, ref text, content text, lemmas text, tokens text, primary key (text_id, ref));
      create table doc_meta (doc_id text primary key, text_id integer, first_ref text, last_ref text);
    ''')
    c.execute("insert into texts values (1, 'edr.tess', 'edr', 'EDR', 2)")
    for ref, content, toks in (('edr:A1', 'Publicum Coloniae Rusellanorum', ['publicum', 'coloniae', 'rusellanorum']),
                               ('edr:A2', 'Rusellae in agro', ['rusellae', 'in', 'agro'])):
        c.execute('insert into lines values (1, ?, ?, ?, ?)', (ref, content, '[]', json.dumps(toks)))
        c.execute('insert into doc_meta values (?, 1, ?, ?)', (ref, ref, ref))
    c.commit()
    c.close()
    return str(d)


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = str(tmp_path / 'entities.sqlite')
    db = sqlite3.connect(path)
    db.executescript(ei.SCHEMA)
    db.executemany('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)', [
        (10, 'pl:413288', 'place', 'Rusellae', 'list', '413288', None, None, None, None, 1, 0),
        (11, 'ln:M', 'person', 'Mentor', 'list', None, None, None, None, None, 1, 2),
        (20, 'nm:rusel', 'name', 'Rusellanum', 'names', None, None, None, None, 'rusel', 0, 1),
        (21, 'nm:mento', 'name', 'Mentor', 'names', None, None, None, None, 'mento', 0, 2)])
    db.executemany('insert into variants values (?,?,?,?,?)', [
        (10, 'rusellae', 'en', 'form', 'list'), (11, 'mentor', 'la', 'form', 'list'),
        (20, 'rusellanum', '', 'form', 'names'), (20, 'rusellani', '', 'form', 'names'),
        (21, 'mentor', '', 'form', 'names')])
    db.executemany('insert into windows values (?,?,?,?,?,?)', [
        (1, 'martial:w1', 'martial.epigrams', '14.88.1', '14.93.2', 'la'),
        (2, 'martial:w2', 'martial.epigrams', '14.91.1', '14.96.2', 'la'),
        (3, 'livy:w3', 'livy.ab_urbe', '10.4.5', '10.4.5', 'la')])
    db.executemany('insert into mention_rows values (?,?,?,?,?,?,?,?,?)', [
        (11, 1, 'Mentor', 1, 0, 0, 'lemma', 'lemma', 0), (11, 2, 'Mentor', 1, 0, 0, 'lemma', 'lemma', 0),
        (21, 1, 'Mentor', 1, 0, 0, 'lemma', 'lemma', 0), (21, 2, 'Mentor', 1, 0, 0, 'lemma', 'lemma', 0),
        (20, 3, 'Rusellanum', 1, 0, 0, 'lemma', 'lemma', 0)])
    for col in ('line_ref', 'form_key'):
        db.execute(f'alter table mention_rows add column {col} TEXT')
    db.execute("update mention_rows set line_ref = '14.93.2', form_key = 'mentor' where wid in (1, 2)")
    db.execute("update mention_rows set line_ref = '10.4.5', form_key = 'rusellanum' where wid = 3")
    db.commit()
    db.close()
    monkeypatch.setenv('TESSERAE_ENTITY_STORE', path)
    ent._cache.clear()
    monkeypatch.setattr(window_texts, 'texts_for', lambda ids: {i: TEXTS[i] for i in ids if i in TEXTS})
    monkeypatch.setattr(passage_index, '_naming', lambda w: {'title': w.split('.')[1].title(),
                                                             'author': w.split('.')[0].title()})
    monkeypatch.setattr(passage_index, '_short_locus_fields',
                        lambda w, a, b: {'locus': a if a == b else f'{a} to {b}'})
    monkeypatch.setattr(ent, '_line_ords', lambda w, refs: {r: ORDS[r] for r in refs if r in ORDS})
    return path


def get(url):
    return app.test_client().get(url)


def test_search_lists_corpus_names_after_the_list_and_not_twice(store):
    r = get(f'{P}/search?q=rusell').get_json()
    assert [(x['id'], x['source']) for x in r['results']] == [('pl:413288', 'list'), ('nm:rusel', 'corpus')]
    assert r['results'][1]['type'] == 'name' and r['results'][1]['mention_counts'] == {'la': 1}
    r = get(f'{P}/search?q=mentor').get_json()
    assert [(x['id'], x['source']) for x in r['results']] == [('ln:M', 'list')]     # the same name, once


def test_entity_view_names_the_corpus_forms_and_marks_the_adjective(store):
    r = get(f'{P}/pl:413288').get_json()
    assert [(n['id'], n['label'], n['mentions_total'], n['adjective']) for n in r['corpus_names']] == [
        ('nm:rusel', 'Rusellanum', 1, True)]
    assert get(f'{P}/ln:M').get_json()['corpus_names'] == []
    assert get(f'{P}/nm:rusel').get_json()['label'] == 'Rusellanum'                 # a corpus name opens too


def test_a_search_with_no_match_offers_near_spellings(store):
    r = get(f'{P}/search?q=russelae').get_json()
    assert r['results'] == []
    assert [(s['label'], s['distance']) for s in r['suggestions']] == [('Rusellae', 2)]
    assert get(f'{P}/search?q=zzzzzz').get_json()['suggestions'] == []
    assert 'suggestions' not in get(f'{P}/search?q=mentor').get_json()


def test_two_windows_with_one_matched_line_are_one_row_and_one_count(store):
    ent_ = get(f'{P}/ln:M').get_json()
    assert ent_['mention_counts'] == {'la': 1} and ent_['mentions_total'] == 1 and ent_['mention_unit'] == 'lines'
    assert [(w['work'], w['count']) for w in ent_['works']] == [('martial.epigrams', 1)]
    r = get(f'{P}/ln:M/mentions').get_json()
    assert r['total'] == 1 and r['windows_total'] == 2 and r['unit'] == 'lines'
    row = r['results'][0]
    assert row['locus'] == '14.93.2' and row['line_ref'] == '14.93.2' and row['windows_merged'] == 2
    # w2 (3 to 8, center 5.5) centers better on the line at 5 than w1 (0 to 5, center 2.5)
    assert row['window_id'] == 'martial:w2' and row['window_locus'] == '14.91.1 to 14.96.2'


def test_a_store_without_line_refs_still_counts_windows(tmp_path, store, monkeypatch):
    db = sqlite3.connect(store)
    db.execute('update mention_rows set line_ref = null, form_key = null')
    db.commit()
    db.close()
    ent._cache.clear()
    assert get(f'{P}/ln:M').get_json()['mentions_total'] == 2      # no line ref: each window is its own line
    # the older column-less store: SCHEMA only
    db = sqlite3.connect(store)
    db.execute('alter table mention_rows drop column line_ref')
    db.execute('alter table mention_rows drop column form_key')
    db.commit()
    db.close()
    ent._cache.clear()
    assert get(f'{P}/ln:M').get_json()['mentions_total'] == 2
    assert get(f'{P}/ln:M/mentions').get_json()['total'] == 2


def test_adjective_rule_on_forms():
    assert adjective_form('Rusellanorum') and adjective_form('Rusellanum')
    assert not adjective_form('Mentor') and not adjective_form('Rusellae')


@pytest.fixture
def documents(store, tmp_path, monkeypatch):
    d = _fixture_documents(tmp_path)
    monkeypatch.setenv('TESSERAE_DOCUMENTS', '1')
    monkeypatch.setenv('TESSERAE_DOCUMENTS_INDEX_DIR', d)
    monkeypatch.setenv('TESSERAE_DOCUMENTS_META', str(tmp_path / 'absent.db'))
    docs.reset_caches()
    counts = extras.build_document_mentions(store, d, log=lambda *a: None)
    ent._cache.clear()
    credit = {'principal_edition': 'EDR020542', 'source_name': 'Epigraphic Database Roma', 'licence_name': 'CC BY-SA 4.0'}
    monkeypatch.setattr(docs, 'bulk_meta', lambda ids: {i: {'doc_id': i, 'credit': credit, 'ancient_place': 'Rusellae',
                                                          'date_not_before': 1, 'date_not_after': 100,
                                                          'text_type_label': 'tessera'} for i in ids})
    yield counts
    docs.reset_caches()


def test_document_build_matches_forms_and_adjectives_and_stores_no_text(documents, store):
    db = sqlite3.connect(store)
    rows = db.execute('select e.entity_id, d.doc_id, d.language, d.form, d.kind, d.adjective '
                      'from document_mentions d join entities e on e.eid = d.eid order by d.doc_id, e.entity_id').fetchall()
    assert ('pl:413288', 'edr:A1', 'la', 'rusellanorum', 'adjective_stem', 1) in rows
    assert ('pl:413288', 'edr:A1', 'la', 'rusellanum', 'corpus_name', 1) not in rows      # that token is not in A1
    assert ('pl:413288', 'edr:A2', 'la', 'rusellae', 'form', 0) in rows
    assert ('nm:mento', 'edr:A1', 'la', 'mentor', 'form', 0) not in rows
    assert all(len(r) == 6 for r in rows)
    assert documents['rows'] == len(rows) and documents['documents_scanned_la'] == 2
    assert extras.extras_problems(store) == ['line_ref not built: run scripts/build_entity_index.py --lines']
    meta = dict(db.execute('select key, value from meta'))
    assert 'document_mentions' in meta and 'documents_fingerprint' in meta


def test_documents_route_returns_credit_on_every_row_and_counts(documents, store):
    r = get(f'{P}/pl:413288').get_json()
    assert r['document_counts'] == {'la': 2}
    d = get(f'{P}/pl:413288/documents').get_json()
    assert d['total'] == 2
    by = {x['doc_id']: x for x in d['results']}
    assert by['edr:A2']['match_kind'] == 'form' and by['edr:A1']['adjective'] is True
    assert [x['doc_id'] for x in d['results']] == ['edr:A2', 'edr:A1']                 # plain forms first
    assert all(x['credit']['source_name'] == 'Epigraphic Database Roma' for x in d['results'])
    assert by['edr:A1']['text'] == 'Publicum Coloniae Rusellanorum' and by['edr:A1']['ancient_place'] == 'Rusellae'
    assert get(f'{P}/pl:413288/documents?lang=grc').get_json()['total'] == 0


def test_documents_route_is_503_when_the_collection_is_off(documents, monkeypatch):
    monkeypatch.setenv('TESSERAE_DOCUMENTS', '0')
    r = get(f'{P}/pl:413288/documents')
    assert r.status_code == 503 and r.get_json()['available'] is False
    assert get(f'{P}/pl:413288').get_json()['document_counts'] == {}


def test_line_refs_find_the_line_that_holds_the_token(tmp_path, store):
    tx = str(tmp_path / 'window_texts.db')
    c = sqlite3.connect(tx)
    c.execute('create table lines (work text, ord integer, ref text, text text)')
    c.executemany('insert into lines values (?,?,?,?)', [
        ('martial.epigrams', 0, '14.88.1', 'Nihil hic.'), ('martial.epigrams', 1, '14.91.1', 'Alius versus.'),
        ('martial.epigrams', 2, '14.93.2', 'Primus in his Mentor, dum facit illa, bibit.'),
        ('martial.epigrams', 3, '14.96.2', 'Finis.'),
        ('livy.ab_urbe', 0, '10.4.5', 'Rusellanum agrum populabantur.')])
    c.commit()
    c.close()
    db = sqlite3.connect(store)
    db.execute('update mention_rows set line_ref = null, form_key = null')
    db.commit()
    db.close()
    stats = extras.add_line_refs(store, tx, log=lambda *a: None)
    assert stats == {'placed': 5, 'unplaced': 0}
    db = sqlite3.connect(store)
    assert set(db.execute('select distinct line_ref from mention_rows where eid = 11').fetchall()) == {('14.93.2',)}
    assert db.execute('select form_key from mention_rows where eid = 20').fetchone() == ('rusellanum',)
