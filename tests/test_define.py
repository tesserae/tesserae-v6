"""The /api/define route and the connector's define tool. No network: the
upstream fetchers are replaced."""
import json
import os

import pytest
from flask import Flask

import backend.blueprints.define as D
import backend.blueprints.mcp_http as M


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(D, 'CACHE_DIR', str(tmp_path / 'definitions'))
    monkeypatch.setattr(D, 'MIN_FETCH_INTERVAL', 0)
    D._memory.clear()
    monkeypatch.setattr(D.hapax, 'get_dictionary_lemma', lambda w, lang: {'arma': 'arma', 'armis': 'arma'}.get(w, w))
    monkeypatch.setattr(D, '_known_latin_form', lambda f: f in ('arma', 'armis'))
    app = Flask(__name__)
    app.register_blueprint(D.define_bp, url_prefix='/api')
    return app.test_client()


def test_latin_from_logeion_then_cached(client, monkeypatch):
    calls = []

    def fake_logeion(lemma, language):
        calls.append(lemma)
        return 'arma, orum, n. arms', 'Lewis and Short'

    monkeypatch.setattr(D, 'fetch_logeion_definition', fake_logeion)
    r = client.get('/api/define?word=armis&language=la').get_json()
    assert r['lemma'] == 'arma' and r['word'] == 'armis'
    assert r['definition'] == 'arma, orum, n. arms'
    assert r['dictionary'] == 'Lewis and Short'
    assert r['url'] == 'https://logeion.uchicago.edu/arma'
    assert r['cached'] is False
    again = client.get('/api/define?word=arma&language=la').get_json()
    assert again['cached'] is True and again['definition'] == r['definition']
    assert calls == ['arma']
    assert json.load(open(D._cache_path('la')))['arma']['dictionary'] == 'Lewis and Short'


def test_fallback_fetcher_when_logeion_has_nothing(client, monkeypatch):
    monkeypatch.setattr(D, 'fetch_logeion_definition', lambda lem, g: None)
    monkeypatch.setattr(D.hapax, 'get_definition', lambda lem, g: 'a gloss')
    r = client.get('/api/define?word=arma&language=grc').get_json()
    assert r['definition'] == 'a gloss' and r['dictionary'] == 'Wiktionary or Perseus'


def test_english_uses_its_fetcher(client, monkeypatch):
    monkeypatch.setattr(D.hapax, 'get_definition', lambda lem, g: f'{g}:{lem}')
    r = client.get('/api/define?word=Plague&language=en').get_json()
    assert r['lemma'] == 'plague' and r['definition'] == 'en:plague'
    assert r['url'] == 'https://en.wiktionary.org/wiki/plague'


def test_miss_is_not_cached(client, monkeypatch):
    monkeypatch.setattr(D, 'fetch_logeion_definition', lambda lem, g: None)
    monkeypatch.setattr(D.hapax, 'get_definition', lambda lem, g: None)
    r = client.get('/api/define?word=zzzqq&language=la').get_json()
    assert r['definition'] is None and r['url'].endswith('/zzzqq')
    assert not os.path.exists(D._cache_path('la'))


@pytest.mark.parametrize('language,host', [
    ('cop', 'coptic-dictionary.org'), ('he', 'wiktionary.org'),
    ('fa', 'vajehyab.com'), ('ur', 'rekhtadictionary.com'), ('ar', 'almaany.com')])
def test_unsupported_language_returns_url_with_null_definition(client, monkeypatch, language, host):
    def boom(*a):
        raise AssertionError('no fetch for this language')
    monkeypatch.setattr(D, 'fetch_logeion_definition', boom)
    monkeypatch.setattr(D.hapax, 'get_definition', boom)
    r = client.get(f'/api/define?word=word&language={language}').get_json()
    assert r['definition'] is None and r['lemma'] == 'word' and host in r['url']


@pytest.mark.parametrize('query', [
    '', 'word=', 'word=two words', 'word=123', 'word=' + 'a' * 61, 'word=arma&language=xx'])
def test_bad_input_is_400(client, query):
    assert client.get('/api/define?' + query).status_code == 400


def test_cache_cap_drops_oldest(client, monkeypatch):
    monkeypatch.setattr(D, 'MAX_ENTRIES', 3)
    for i in range(5):
        D._store('la', f'w{i}', {'definition': str(i), 'dictionary': 'x'})
    assert list(json.load(open(D._cache_path('la')))) == ['w2', 'w3', 'w4']


def test_strip_html():
    assert D._strip_html('<i>arma</i>, <b>orum</b>&nbsp;n.') == 'arma, orum n.'


def test_connector_tool_passes_fields_through(monkeypatch):
    seen = {}

    def fake_get(path, params=None):
        seen['path'], seen['params'] = path, params
        return {'word': 'arma', 'lemma': 'arma', 'definition': 'arms'}

    monkeypatch.setattr(M, '_get', fake_get)
    out = M._t_define({'word': ' arma '})
    assert seen == {'path': '/define', 'params': {'word': 'arma', 'language': 'la'}}
    assert out['definition'] == 'arms'
    assert M._t_define({'word': ''}) == {'error': 'word is required'}
    assert any(t['name'] == 'define' for t in M.TOOLS)


def test_latin_lemma_folds_spelling_and_takes_off_enclitics(monkeypatch):
    table = {'uirum': 'uir', 'inferret': 'infero', 'arma': 'arma', 'breue': 'breuis', 'daphne': 'daphne'}
    monkeypatch.setattr(D.hapax, 'get_dictionary_lemma', lambda w, lang: table.get(w, w))
    monkeypatch.setattr(D, '_known_latin_form', lambda f: f in table)
    assert D.latin_lemma('virum') == ('uir', None)
    assert D.latin_lemma('Virumque') == ('uir', 'que')
    assert D.latin_lemma('inferretque') == ('infero', 'que')
    # -que comes off even when the base is unknown; -ve and -ne only when the base is a known form.
    assert D.latin_lemma('ignotumque') == ('ignotum', 'que')
    assert D.latin_lemma('armave') == ('arma', 've')
    assert D.latin_lemma('breve') == ('breuis', None)
    assert D.latin_lemma('Daphne') == ('daphne', None)
    assert D.latin_lemma('urbisne') == ('urbisne', None)


def test_latin_spellings_write_consonantal_u_as_v():
    assert D.latin_spellings('uir') == ['uir', 'vir']
    assert D.latin_spellings('seruus') == ['seruus', 'servus']
    assert D.latin_spellings('suauis') == ['suauis', 'suavis', 'svavis']
    assert D.latin_spellings('arma') == ['arma']
    assert D.latin_spellings('quis') == ['quis']


def test_enclitic_word_answers_with_the_base_lemma_in_dictionary_spelling(client, monkeypatch):
    table = {'uirum': 'uir', 'inferret': 'infero'}
    monkeypatch.setattr(D.hapax, 'get_dictionary_lemma', lambda w, lang: table.get(w, w))
    monkeypatch.setattr(D, '_known_latin_form', lambda f: f in table)
    asked = []

    def fake_logeion(lemma, language):
        asked.append(lemma)
        return ('vir, viri, m. a man', 'Lewis and Short') if lemma == 'vir' else None

    monkeypatch.setattr(D, 'fetch_logeion_definition', fake_logeion)
    r = client.get('/api/define?word=virumque&language=la').get_json()
    assert r['lemma'] == 'vir' and r['enclitic'] == 'que'
    assert r['definition'] == 'vir, viri, m. a man'
    assert r['url'] == 'https://logeion.uchicago.edu/vir'
    assert asked == ['uir', 'vir']
    again = client.get('/api/define?word=uirum&language=la').get_json()
    assert again['cached'] is True and again['lemma'] == 'vir' and again['enclitic'] is None
    assert again['url'] == 'https://logeion.uchicago.edu/vir'
    assert asked == ['uir', 'vir']


def test_logeion_entries_keeps_every_homograph():
    data = {'detail': {'dicos': [
        {'dname': 'LewisShort', 'es': ['<b>lābor</b>, lapsus, v. dep. n., to move gently along',
                                       '<b>lăbor</b>, ōris, m., labor, toil, exertion']},
        {'dname': 'Georges', 'es': ['labor, oris']},
    ]}}
    definition, dictionary = D.logeion_entries(data, 'la')
    assert dictionary == 'Lewis and Short'
    assert definition.split('\n\n') == ['lābor, lapsus, v. dep. n., to move gently along',
                                        'lăbor, ōris, m., labor, toil, exertion']
    # Each entry gets a share of the length limit, so a long first entry cannot crowd out the second.
    long = {'detail': {'dicos': [{'dname': 'LewisShort', 'es': ['x' * 900, 'y' * 900, 'z' * 900, 'w' * 900]}]}}
    definition, _ = D.logeion_entries(long, 'la')
    parts = definition.split('\n\n')
    assert len(parts) == 3 and all(len(p) <= D.MAX_DEFINITION // 3 + 1 for p in parts)
    assert D.logeion_entries({'detail': {'dicos': []}}, 'la') is None
    assert D.logeion_entries({'detail': {'dicos': [{'dname': 'LSJ', 'es': ['λόγος, ὁ, word']}]}}, 'grc') == (
        'λόγος, ὁ, word', 'Liddell-Scott-Jones (LSJ)')
