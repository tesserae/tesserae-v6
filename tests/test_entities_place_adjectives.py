"""People & Places, a place's page lists the lines that name it by its adjective (2026-10-20).
A fixture store from the real schema, a link table written to a temporary file, no live index."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend import entity_index as ei  # noqa: E402
from backend import passage_index  # noqa: E402
from backend import place_adjectives  # noqa: E402
from backend import window_texts  # noqa: E402
from backend.app import app, API_PREFIX  # noqa: E402
from backend.blueprints import entities as ent  # noqa: E402

P = f'{API_PREFIX}/entities' if API_PREFIX else '/entities'

TEXTS = {'livy:w1': 'Rusellanum agrum populabantur.', 'livy:w2': 'Rusellani fugerunt.',
         'cicero:w3': 'in Tusculano fui.', 'cicero:w4': 'Tusculanae disputationes scripsi.'}


def _store(tmp_path):
    path = str(tmp_path / 'entities.sqlite')
    db = sqlite3.connect(path)
    db.executescript(ei.SCHEMA)
    db.executemany('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)', [
        (10, 'pl:413288', 'place', 'Rusellae', 'list', '413288', None, None, None, None, 1, 0),
        (11, 'pl:423108', 'place', 'Tusculum', 'list', '423108', None, None, None, None, 1, 0),
        (12, 'pl:999', 'place', 'Nowhere', 'list', '999', None, None, None, None, 1, 0),
        (20, 'nm:rusel', 'name', 'Rusellanum', 'names', None, None, None, None, 'rusel', 0, 3),
        (21, 'nm:tusku', 'name', 'Tusculanum', 'names', None, None, None, None, 'tusku', 0, 2)])
    db.executemany('insert into variants values (?,?,?,?,?)', [
        (10, 'rusellae', 'en', 'form', 'list'), (11, 'tusculum', 'la', 'form', 'list'),
        (12, 'nowhere', 'en', 'form', 'list'),
        (20, 'rusellanum', '', 'form', 'names'), (21, 'tusculano', '', 'form', 'names')])
    db.executemany('insert into windows values (?,?,?,?,?,?)', [
        (1, 'livy:w1', 'livy.ab_urbe', '10.4.5', '10.4.5', 'la'),
        (2, 'livy:w2', 'livy.ab_urbe', '10.5.1', '10.5.1', 'la'),
        (3, 'cicero:w3', 'cicero.letters', '1.1', '1.1', 'la'),
        (4, 'cicero:w4', 'cicero.tusc', '1.1', '1.1', 'la')])
    db.executemany('insert into mention_rows values (?,?,?,?,?,?,?,?,?)', [
        (20, 1, 'Rusellanum', 1, 0, 0, 'lemma', 'lemma', 0), (20, 2, 'Rusellani', 1, 0, 0, 'lemma', 'lemma', 0),
        (21, 3, 'Tusculano', 1, 0, 0, 'lemma', 'lemma', 0), (21, 4, 'Tusculanae', 1, 0, 0, 'lemma', 'lemma', 0)])
    for col in ('line_ref', 'form_key'):
        db.execute(f'alter table mention_rows add column {col} TEXT')
    for wid, ref, fk in ((1, '10.4.5', 'rusellanum'), (2, '10.5.1', 'rusellani'),
                         (3, 'ad fam. 1.1', 'tusculano'), (4, 'tusc. 1.1', 'tusculanae')):
        db.execute('update mention_rows set line_ref = ?, form_key = ? where wid = ?', (ref, fk, wid))
    db.commit()
    db.close()
    return path


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = _store(tmp_path)
    table = tmp_path / 'place_adjectives.json'
    table.write_text(json.dumps({'version': 1, 'places': {
        'pl:413288': {'label': 'Rusellae', 'adjectives': [
            {'entity_id': 'nm:rusel', 'label': 'Rusellanum', 'exclude_lines': []},
            {'entity_id': 'nm:gone', 'label': 'Gone', 'exclude_lines': []}]},
        'pl:423108': {'label': 'Tusculum', 'adjectives': [
            {'entity_id': 'nm:tusku', 'label': 'Tusculanum',
             'exclude_lines': [{'work': 'cicero.tusc', 'key': 'tusc. 1.1|tusculanae'}]}]},
        'pl:missing': {'label': 'Missing', 'adjectives': [{'entity_id': 'nm:rusel', 'label': 'x'}]}}}))
    monkeypatch.setenv('TESSERAE_ENTITY_STORE', path)
    monkeypatch.setenv('TESSERAE_PLACE_ADJECTIVES', str(table))
    ent._cache.clear()
    monkeypatch.setattr(window_texts, 'texts_for', lambda ids: {i: TEXTS[i] for i in ids if i in TEXTS})
    monkeypatch.setattr(passage_index, '_naming', lambda w: {'title': w.split('.')[1].title(),
                                                             'author': w.split('.')[0].title()})
    monkeypatch.setattr(passage_index, '_short_locus_fields', lambda w, a, b: {'locus': a})
    return path


def get(url):
    return app.test_client().get(url)


def test_a_place_with_adjectives_lists_them_with_counts_and_forms(store):
    r = get(f'{P}/pl:413288').get_json()
    assert r['adjective_names'] == [{'entity_id': 'nm:rusel', 'label': 'Rusellanum', 'count': 2,
                                     'forms': [{'form': 'Rusellani', 'count': 1}, {'form': 'Rusellanum', 'count': 1}]}]


def test_a_place_without_adjectives_and_other_entities_get_an_empty_list(store):
    assert get(f'{P}/pl:999').get_json()['adjective_names'] == []
    assert get(f'{P}/nm:rusel').get_json()['adjective_names'] == []


def test_an_id_the_store_does_not_hold_is_skipped_and_a_missing_table_is_empty(store, monkeypatch, tmp_path):
    assert [a['entity_id'] for a in get(f'{P}/pl:413288').get_json()['adjective_names']] == ['nm:rusel']
    monkeypatch.setenv('TESSERAE_PLACE_ADJECTIVES', str(tmp_path / 'absent.json'))
    r = get(f'{P}/pl:413288')
    assert r.status_code == 200 and r.get_json()['adjective_names'] == []
    (tmp_path / 'bad.json').write_text('{not json')
    monkeypatch.setenv('TESSERAE_PLACE_ADJECTIVES', str(tmp_path / 'bad.json'))
    assert get(f'{P}/pl:413288').get_json()['adjective_names'] == []


def test_the_book_title_line_is_left_out_of_the_count_and_the_lines(store):
    r = get(f'{P}/pl:423108').get_json()
    assert [(a['label'], a['count']) for a in r['adjective_names']] == [('Tusculanum', 1)]
    lines = get(f'{P}/nm:tusku/mentions?adjective_of=pl:423108').get_json()
    assert lines['total'] == 1 and [x['window_id'] for x in lines['results']] == ['cicero:w3']
    whole = get(f'{P}/nm:tusku/mentions').get_json()
    assert whole['total'] == 2                              # the entity's own page is not filtered
    assert get(f'{P}/nm:tusku/mentions?adjective_of=pl:413288').get_json()['total'] == 2


def test_exclusions_lookup(store):
    assert place_adjectives.exclusions('pl:423108', 'nm:tusku') == [('cicero.tusc', 'tusc. 1.1|tusculanae')]
    assert place_adjectives.exclusions('pl:423108', 'nm:rusel') == []
    assert place_adjectives.exclusions('pl:none', 'nm:tusku') == []


def test_book_title_rule_and_the_id_check_of_the_builder(store, tmp_path):
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'entities'))
    import build_place_adjectives as b
    assert b.followed_by('Tusculanae disputationes scripsi', 'Tusculanae', 'disput') == [True]
    assert b.followed_by('in Tusculano fui, sed Tusculano disputatio', 'Tusculano', 'disput') == [False, True]
    assert b.followed_by('Tusculanarum quaestionum disputationes', 'Tusculanarum', 'disput') == [True]
    assert b.followed_by('Tusculanarum a b disputationes', 'Tusculanarum', 'disput') == [False]
    table = os.environ['TESSERAE_PLACE_ADJECTIVES']
    assert b.check(table, store) == [
        'adjective nm:gone (Gone) is not a corpus name (source names) in the store',
        'place pl:missing (Missing) is not a place entity in the store']
