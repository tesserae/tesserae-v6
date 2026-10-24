"""The Events documents rule through the real name resolution and the real
document_mentions lookup, on a small fixture Mentions store."""
import sqlite3

import pytest

from backend import entity_extras as extras
from backend import entity_index as ei
from backend.blueprints import events as E


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = str(tmp_path / 'entities.sqlite')
    db = sqlite3.connect(path)
    db.executescript(ei.SCHEMA)
    db.executemany('insert into entities values (?,?,?,?,?,?,?,?,?,?,?,?)', [
        (10, 'pl:1', 'place', 'Sicilia', 'list', None, None, None, None, None, 1, 0),
        (11, 'ln:H', 'person', 'Hermocrates', 'list', None, None, None, None, None, 1, 0),
        # the event's place by Pleiades id (2026-10-24): Actium carries 530771, Akriai does not
        (12, 'pl:530771', 'place', 'Actium', 'list', '530771', None, None, None, None, 1, 99),
        (13, 'pl:570058', 'place', 'Akriai', 'list', '570058', None, None, None, None, 1, 5)])
    db.executemany('insert into variants values (?,?,?,?,?)', [
        (10, 'sicilia', 'la', 'form', 'list'), (11, 'hermocrates', 'grc', 'form', 'list'),
        (12, 'actium', 'la', 'form', 'list'), (13, 'akri', 'la', 'form', 'list')])
    db.executescript(extras.DOC_SCHEMA)
    db.executemany('insert into document_mentions values (?,?,?,?,?,?)', [
        (11, 'isicily:ISic1', 'grc', 'hermocrates', 'form', 0),
        (10, 'isicily:ISic2', 'la', 'sicilia', 'form', 0),
        (11, 'isicily:ISicElsewhere', 'grc', 'hermocrates', 'form', 0),
        (12, 'edh:HD_actium', 'la', 'actium', 'form', 0),
        (13, 'isicily:ISic004485', 'grc', 'ακραγαντινοσ', 'corpus_name', 1)])
    db.commit()
    db.close()
    monkeypatch.setenv('TESSERAE_ENTITY_STORE', path)
    extras.CATALOG_CACHE.clear()
    yield path
    extras.CATALOG_CACHE.clear()


def test_a_name_resolves_to_the_entity_the_search_lists_first(store):
    assert extras.resolve_name_to_eid(store, 'Hermocrates') == 11
    assert extras.resolve_name_to_eid(store, 'Sicilia') == 10
    assert extras.resolve_name_to_eid(store, 'Nobody Atall') is None
    assert extras.resolve_name_to_eid(store, 'x') is None
    assert extras.resolve_name_to_eid(store + '.missing', 'Hermocrates') is None


def test_the_documents_that_name_a_participant_or_the_place_are_found(store):
    found = E._documents_naming(['isicily:ISic1', 'isicily:ISic2', 'isicily:ISic3'], ['Hermocrates', 'Sicilia', 'Gylippus'])
    # {doc_id: the word forms that matched}, the forms used to highlight the text (2026-10-20)
    assert set(found) == {'isicily:ISic1', 'isicily:ISic2'}
    assert all(found[k] for k in found)
    assert E._documents_naming(['isicily:ISic3'], ['Hermocrates']) == {}


def test_naming_documents_lead_through_the_real_path(store):
    docs = [{'doc_id': 'isicily:ISic3', 'date_start': -415, 'date_end': -413, 'distance_km': 1},
            {'doc_id': 'isicily:ISic1', 'date_start': -430, 'date_end': -401, 'distance_km': 60}]
    naming = E._documents_naming([d['doc_id'] for d in docs], ['Hermocrates'])
    out = E.rank_documents(docs, naming)
    assert [(d['doc_id'], d['group']) for d in out] == [('isicily:ISic1', 'names'), ('isicily:ISic3', 'dated')]


def test_an_undated_document_is_kept_and_follows_every_dated_one():
    docs = [{'doc_id': 'undated', 'date_start': None, 'date_end': None, 'distance_km': 0.1},
            {'doc_id': 'dated', 'date_start': -430, 'date_end': -401, 'distance_km': 90}]
    out = E.rank_documents(docs, set())
    assert [d['doc_id'] for d in out] == ['dated', 'undated']
    assert out[1]['date_span'] is None


def test_naming_by_text_reads_restored_names_and_the_divi_iuli_phrase():
    texts = {
        'edh:HD052963': '[Imp(eratori) Caes]ari / divi [f(ilio)] / [Augus]to',
        'edh:HD023503': '[Nep]tuno [et Ma]rt[i Imp(erator) Caesa]r Div[i Iuli] f(ilius) vict[oriam',
        'edh:other': 'Marcus Tullius Lucius f(ilius)',
    }
    found = E._documents_naming_by_text(texts, ['Cleopatra', 'Augustus', 'Marcus Vipsanius Agrippa', 'Aktio'])
    assert found['edh:HD052963'] == {'augusto'}
    assert found['edh:HD023503'] == {'diui', 'iuli'}
    assert 'edh:other' not in found   # a first name alone names no one


def test_naming_by_text_leaves_out_peoples_and_victory_titles():
    texts = {'a': 'Cai Caesaris Augusti Germanici', 'b': 'pro salute populi Romanorum', 'c': 'Germanico Caesari'}
    assert E._documents_naming_by_text(texts, ['Germanic people', 'Ancient Rome', 'Germania']) == {}
    assert set(E._documents_naming_by_text(texts, ['Germanicus'])) == {'a', 'c'}


def test_the_place_resolves_by_the_events_pleiades_id_first(store):
    # the label "Akri" alone finds Akriai (eid 13) and its Agrigentum stone
    assert extras.resolve_name_to_eid(store, 'Akri') == 13
    assert E._place_eid(store, 'Akri', None) == 13
    # with the event's Pleiades id the place is Actium (eid 12), whatever the label says
    assert E._place_eid(store, 'Akri', '530771') == 12
    found = E._documents_naming(['edh:HD_actium', 'isicily:ISic004485'], [], place='Akri', pleiades_id='530771')
    assert set(found) == {'edh:HD_actium'}
    # an id the store lacks falls back to the label, unless the label's own id differs
    assert E._place_eid(store, 'Akri', '999999') is None
    assert E._place_eid(store, 'Sicilia', '999999') == 10
    # without a place nothing is added
    assert E._documents_naming(['edh:HD_actium'], ['Hermocrates'], place=None, pleiades_id=None) == {}
