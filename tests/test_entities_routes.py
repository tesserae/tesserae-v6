"""/api/entities/*: search, one entity, mentions with a shared name, and the 503 when the store
is absent. The store is built here from the real schema with three entities, one shared name and
two languages. No live index is read."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend import entity_index as ei  # noqa: E402
from backend import passage_index  # noqa: E402
from backend import window_texts  # noqa: E402
from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import entities as ent  # noqa: E402

P = f'{API_PREFIX}/entities' if API_PREFIX else '/entities'

TEXTS = {
    'vergil.aeneid:fine:1': 'Troia fuit, et Mars ferox.',
    'vergil.aeneid:fine:2': 'Mars in armis sedet.',
    'homer.iliad:fine:7': 'Τροίη ἁλώσεται.',
}


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = str(tmp_path / 'entities.sqlite')
    db = sqlite3.connect(path)
    db.executescript(ei.SCHEMA)
    ents = [
        (1, 'ln:E1', 'place', 'Troy', 'list', None, json.dumps(['1', '2']), None, None, None, 1, 2),
        (2, 'ln:E2', 'deity', 'Ares/Mars', 'list', None, None, None, None, None, 1, 2),
        (3, 'ln:E3', 'person', 'Mars (Roman family)', 'list', None, None, None, None, None, 0, 1),
    ]
    db.executemany('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)', ents)
    db.executemany('insert into variants values (?,?,?,?,?)', [
        (1, 'troia', 'la', 'form', 'list'), (1, 'τροιη', 'grc', 'form', 'list'),
        (2, 'mars', 'la', 'form', 'list'), (3, 'mars', 'la', 'form', 'list')])
    db.execute("insert into entity_aliases values (1, 'ln:E9', 'Ilium', 'place', 'forms')")
    db.executemany('insert into windows values (?,?,?,?,?,?)', [
        (1, 'vergil.aeneid:fine:1', 'vergil.aeneid', 'verg. aen. 1.1', 'verg. aen. 1.2', 'la'),
        (2, 'vergil.aeneid:fine:2', 'vergil.aeneid', 'verg. aen. 1.3', 'verg. aen. 1.4', 'la'),
        (3, 'homer.iliad:fine:7', 'homer.iliad', 'hom. il. 7.1', 'hom. il. 7.2', 'grc')])
    db.executemany('insert into mention_rows values (?,?,?,?,?,?,?,?,?)', [
        (1, 1, 'Troia', 1, 0, 0, 'lemma', 'lemma', 0),
        (1, 3, 'Τροίη', 1, 0, 0, 'lemma', 'lemma', 0),
        (2, 1, 'Mars', 1, 0, 0, 'lemma', 'lemma', 1),
        (3, 1, 'Mars', 1, 0, 0, 'lemma', 'lemma', 1),
        (2, 2, 'Mars', 1, 0, 0, 'lemma', 'lemma', 0)])
    db.commit()
    db.close()
    monkeypatch.setenv('TESSERAE_ENTITY_STORE', path)
    ent._cache.clear()
    monkeypatch.setattr(window_texts, 'texts_for', lambda ids: {i: TEXTS[i] for i in ids if i in TEXTS})
    monkeypatch.setattr(passage_index, '_naming', lambda w: {'title': w.split('.')[1].title(),
                                                             'author': w.split('.')[0].title()})
    monkeypatch.setattr(passage_index, '_short_locus_fields',
                        lambda w, a, b: {'locus': a.split()[-1] if a else ''})
    return path


def get(url):
    return app.test_client().get(url)


def test_search_matches_label_and_name_forms_and_flags_a_shared_name(store):
    r = get(f'{P}/search?q=troia').get_json()
    assert [x['id'] for x in r['results']] == ['ln:E1']
    troy = r['results'][0]
    assert troy['type'] == 'place' and troy['identifiers']['pleiades'] == ['1', '2']
    assert troy['identifiers']['also_listed_as'] == ['ln:E9']
    assert troy['mention_counts'] == {'la': 1, 'grc': 1} and troy['mentions_total'] == 2
    assert troy['label_shared'] is False
    r = get(f'{P}/search?q=mars').get_json()
    assert [x['id'] for x in r['results']] == ['ln:E3', 'ln:E2']      # the exact label (note dropped) first
    assert r['results'][1]['label_shared'] is True                    # a mention whose name is shared
    assert get(f'{P}/search?q=x').get_json()['results'] == []


def test_one_entity_has_its_counts_by_work_and_resolves_a_merged_id(store):
    r = get(f'{P}/ln:E1').get_json()
    assert r['label'] == 'Troy'
    assert [(w['work'], w['language'], w['count']) for w in r['works']] == [
        ('homer.iliad', 'grc', 1), ('vergil.aeneid', 'la', 1)]
    assert r['works'][0]['title'] == 'Iliad' and r['works'][0]['author'] == 'Homer'
    assert get(f'{P}/ln:E9').get_json()['id'] == 'ln:E1'
    assert get(f'{P}/ln:nothing').status_code == 404


def test_mentions_carry_text_token_locus_and_the_names_they_share(store):
    r = get(f'{P}/ln:E2/mentions').get_json()
    assert r['total'] == 2 and r['limit'] == 50
    by = {x['window_id']: x for x in r['results']}
    shared = by['vergil.aeneid:fine:1']
    assert shared['text'] == TEXTS['vergil.aeneid:fine:1'] and shared['token'] == 'Mars'
    assert shared['shared_with'] == ['Mars (Roman family)'] and shared['locus'] == '1.1'
    assert by['vergil.aeneid:fine:2']['shared_with'] == []
    one = get(f'{P}/ln:E1/mentions?lang=grc').get_json()
    assert [x['window_id'] for x in one['results']] == ['homer.iliad:fine:7']
    paged = get(f'{P}/ln:E2/mentions?limit=1&offset=1').get_json()
    assert paged['total'] == 2 and len(paged['results']) == 1
    assert get(f'{P}/ln:E2/mentions?limit=9999').get_json()['limit'] == 200
    assert len(get(f'{P}/ln:E2/mentions?work=vergil.aeneid.tess').get_json()['results']) == 2


def test_a_missing_store_answers_503_with_a_readable_error(tmp_path, monkeypatch):
    monkeypatch.setenv('TESSERAE_ENTITY_STORE', str(tmp_path / 'absent.sqlite'))
    ent._cache.clear()
    for url in (f'{P}/search?q=troy', f'{P}/ln:E1', f'{P}/ln:E1/mentions'):
        r = get(url)
        assert r.status_code == 503
        assert r.get_json()['available'] is False and 'not installed' in r.get_json()['error']
