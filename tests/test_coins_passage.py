"""The Reader's Coins tab and the Theme Search coins option: pack_descriptions.py,
/api/coins/for-passage, /api/coins/theme and the person filter, on the 12-type
fixture with seeded 8-dimension vectors. The query encoder, the passage index
and the lemma cache are replaced by small stand-ins, so nothing here loads a
model or reads production data."""
import json
import os
import subprocess
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, 'tests', 'fixtures', 'coins', 'coins.jsonl')
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'coins'))

from embed_descriptions import describe  # noqa: E402
from backend import coins_passage as CP  # noqa: E402

DIM = 8


def _vec(i):
    v = np.random.RandomState(1000 + i).randn(DIM)
    return v / np.linalg.norm(v)


@pytest.fixture(scope='module')
def site(tmp_path_factory):
    d = tmp_path_factory.mktemp('coins2')
    db = str(d / 'coins.sqlite')
    subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'scripts', 'coins', 'build_coins_db.py'),
                    '--input', FIX, '--out', db], check=True)
    strings, index, types = [], {}, {}
    for line in open(FIX, encoding='utf-8'):
        r = json.loads(line)
        t = describe(r)
        if t not in index:
            index[t] = len(strings)
            strings.append(t)
        types[r['id']] = index[t]
    emb = d / 'emb'
    emb.mkdir()
    np.save(emb / 'vectors.npy', np.stack([_vec(i) for i in range(len(strings))]).astype(np.float16))
    json.dump(strings, open(emb / 'strings.json', 'w'))
    json.dump(types, open(emb / 'types.json', 'w'))
    subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'scripts', 'coins', 'pack_descriptions.py'),
                    '--emb', str(emb), '--out', str(d)], check=True)
    return {'dir': d, 'db': db, 'strings': strings}


@pytest.fixture
def client(site, monkeypatch):
    monkeypatch.setenv('TESSERAE_COINS_DB', site['db'])
    CP._cache.clear()
    from backend.app import app
    app.config['TESTING'] = True
    return app.test_client()


GIST = 'Augustus born under the sign of Capricorn'
WINDOWS = [
    {'id': 'w1', 'ref_start': 'aug. 94.1', 'ref_end': 'aug. 94.6',
     'desc': {'gist': 'A plain window.', 'props': [], 'participants': 'a man'}},
    {'id': 'w2', 'ref_start': 'aug. 94.4', 'ref_end': 'aug. 94.12',
     'desc': {'gist': GIST, 'props': ['star', 'globe', 'rudder'],
              'participants': 'Augustus, Nigidius, the astrologer', 'setting': 'the house at Rome at night'}},
]


def _unit(ref, words):
    """words: [(token as written, lemma)]"""
    return {'ref': ref, 'tokens': [w.lower() for w, _ in words],
            'original_tokens': [w for w, _ in words], 'lemmas': [l for _, l in words]}


UNITS = [_unit('aug. 94.4', [('Cum', 'cum'), ('Augusto', 'augustus'), ('natus', 'nascor'),
                             ('augustus', 'augustus'), ('Galba', 'galba')]),
         _unit('aug. 94.5', [('et', 'et'), ('Tiberium', 'tiberius')])]


@pytest.fixture
def stubs(monkeypatch, site):
    calls = {'embed': 0, 'texts': []}
    # the query vector is the vector of the description of the Capricorn type
    row = next(i for i, s in enumerate(site['strings']) if 'Capricorn' in s)

    def fake_embed(text):
        calls['embed'] += 1
        calls['texts'].append(text)
        return _vec(row) * 0.98 + _vec((row + 1) % len(site['strings'])) * 0.02

    monkeypatch.setattr(CP, 'embed', fake_embed)
    monkeypatch.setattr(CP, 'windows_covering', lambda w, a, b: WINDOWS)
    monkeypatch.setattr(CP, 'passage_units', lambda w, lang, a, b: UNITS)
    calls['row'] = row
    return calls


def test_pack_writes_matching_files(site):
    m = np.load(site['dir'] / 'descriptions.npy')
    rows = json.load(open(site['dir'] / 'descriptions_ids.json'))
    assert m.dtype == np.float16 and m.shape == (len(site['strings']), DIM) and len(rows) == m.shape[0]
    assert sum(len(r['types']) for r in rows) == 12
    assert all(r['text'] and r['types'] for r in rows)


def test_pack_refuses_unnormalised_vectors(tmp_path):
    emb = tmp_path / 'e'
    emb.mkdir()
    np.save(emb / 'vectors.npy', np.ones((2, 4), dtype=np.float16))
    json.dump(['a', 'b'], open(emb / 'strings.json', 'w'))
    json.dump({'x:1': 0, 'x:2': 1}, open(emb / 'types.json', 'w'))
    r = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'scripts', 'coins', 'pack_descriptions.py'),
                        '--emb', str(emb), '--out', str(tmp_path / 'o')], capture_output=True, text=True)
    assert r.returncode != 0 and 'normalised' in (r.stderr + r.stdout)


def test_embed_server_assembly_checks_ids(tmp_path):
    import embed_descriptions as ed
    np.save(tmp_path / 'vectors-000.npy', np.zeros((3, 4), dtype=np.float32))
    json.dump(['0', '1', '2'], open(tmp_path / 'ids-000.json', 'w'))
    assert ed.assemble_parts(str(tmp_path), 3).dtype == np.float16
    with pytest.raises(SystemExit):
        ed.assemble_parts(str(tmp_path), 4)


def test_best_window_is_the_most_concrete():
    assert CP.best_window(WINDOWS)['id'] == 'w2'
    assert CP.best_window([{'id': 'x', 'desc': {}}]) is None


def test_for_passage_related_imagery(client, stubs):
    d = client.get('/api/coins/for-passage', query_string={
        'work': 'suetonius.de_vita_caesarum.part.2.augustus', 'lang': 'la', 'ref': 'aug. 94.4',
        'ref_end': 'aug. 94.6'}).get_json()
    assert d['available'] and d['query'] == GIST and d['window']['id'] == 'w2'
    assert len(d['related']) == 5
    top = d['related'][0]
    assert 'Capricorn' in top['description'] and top['coin_id'] == 'ocre:ric.1(2).aug.125'
    from urllib.parse import unquote
    assert unquote(top['coin_url']) == '/coins/ocre:ric.1(2).aug.125' and top['authorities'] == ['Augustus']
    assert top['confidence']['level'] in ('higher', 'usual') and top['confidence']['score'] > 0.9
    assert len({r['description'] for r in d['related']}) == 5
    assert d['related'][0]['score'] >= d['related'][-1]['score']
    assert 'one match in three' in d['hit_rate_label']
    assert stubs['texts'] == [GIST]  # only the gist sentence is ever encoded


def test_for_passage_is_cached_per_work_and_ref(client, stubs):
    q = {'work': 'w', 'lang': 'la', 'ref': 'aug. 94.4', 'ref_end': 'aug. 94.6'}
    client.get('/api/coins/for-passage', query_string=q)
    client.get('/api/coins/for-passage', query_string=q)
    assert stubs['embed'] == 1
    client.get('/api/coins/for-passage', query_string={**q, 'ref': 'aug. 94.5'})
    assert stubs['embed'] == 2


def test_name_links(client, stubs):
    d = client.get('/api/coins/for-passage', query_string={
        'work': 'w', 'lang': 'la', 'ref': 'aug. 94.4', 'ref_end': 'aug. 94.5'}).get_json()
    names = {n['name']: n for n in d['name_links']}
    assert 'Augustus' in names and 'Galba' in names and 'Tiberius' not in names  # Tiberium: not in the fixture
    assert names['Augustus']['n_types'] >= 3
    assert names['Augustus']['coins_url'] == '/coins?person=Augustus'
    assert 'not an echo' in d['name_links_note']


def test_name_links_are_latin_only(client, stubs):
    d = client.get('/api/coins/for-passage', query_string={'work': 'w', 'lang': 'grc', 'ref': 'x 1'}).get_json()
    assert d['name_links'] == [] and d['related']


def test_lowercase_word_is_not_a_name(client, stubs, monkeypatch):
    monkeypatch.setattr(CP, 'passage_units', lambda *a: [_unit('aug. 94.4', [('augustus', 'augustus')])])
    d = client.get('/api/coins/for-passage', query_string={'work': 'w', 'lang': 'la', 'ref': 'aug. 94.4'}).get_json()
    assert d['name_links'] == []


def test_no_window_means_no_imagery_and_no_encoder_call(client, stubs, monkeypatch):
    monkeypatch.setattr(CP, 'windows_covering', lambda *a: [])
    d = client.get('/api/coins/for-passage', query_string={'work': 'w', 'lang': 'la', 'ref': 'aug. 94.4'}).get_json()
    assert d['related'] == [] and 'No passage window' in d['note'] and stubs['embed'] == 0


def test_encoder_down_is_said_plainly(client, stubs, monkeypatch):
    def boom(text):
        raise RuntimeError('connection refused')
    monkeypatch.setattr(CP, 'embed', boom)
    r = client.get('/api/coins/for-passage', query_string={'work': 'w', 'lang': 'la', 'ref': 'aug. 94.4'})
    d = r.get_json()
    assert r.status_code == 200 and d['unavailable'] and 'encoder' in d['error'] and d['related'] == []


def test_arguments_and_missing_data(client, monkeypatch, tmp_path):
    assert 'required' in client.get('/api/coins/for-passage?work=w').get_json()['error']
    assert 'required' in client.get('/api/coins/theme').get_json()['error']
    monkeypatch.setenv('TESSERAE_COINS_DB', str(tmp_path / 'none.sqlite'))
    assert client.get('/api/coins/for-passage?work=w&ref=1').get_json()['available'] is False
    assert client.get('/api/coins/theme?q=ship').get_json()['available'] is False


def test_vectors_not_installed(site, tmp_path, monkeypatch):
    import shutil
    db = tmp_path / 'coins.sqlite'
    shutil.copy(site['db'], db)
    monkeypatch.setenv('TESSERAE_COINS_DB', str(db))
    from backend.app import app
    c = app.test_client()
    d = c.get('/api/coins/for-passage?work=w&ref=aug.%201.1&lang=grc').get_json()
    assert d['available'] is False and 'not installed' in d['reason']
    assert c.get('/api/coins/theme?q=ship').get_json()['available'] is False


def test_theme_ranks_descriptions(client, stubs):
    d = client.get('/api/coins/theme?q=goat-fish+and+globe&limit=3').get_json()
    assert d['available'] and len(d['results']) == 3
    assert 'Capricorn' in d['results'][0]['description'] and d['results'][0]['coin_id']
    assert 'about one right coin in two' in d['label']
    assert stubs['texts'] == ['goat-fish and globe']


def test_person_filter_on_the_list(client):
    d = client.get('/api/coins?person=Augustus').get_json()
    assert d['total'] >= 3 and all('Augustus' in (c['authority'] or '') or c['portrait'] == 'Augustus'
                                   for c in d['coins'])
    assert client.get('/api/coins?person=Augustu').get_json()['total'] == 0  # whole names only
    assert client.get('/api/coins?person=Nobody+At+All').get_json()['total'] == 0


def test_generated_forms_skip_symbols_and_lone_initials():
    assert CP._generated_forms('L. Piso Frugi') == ['piso frugi']
    assert CP._generated_forms('C. Antonius') is None
    assert CP._generated_forms('Owl (Republican Moneyer)') is None
    assert CP._generated_forms('Gallia Personification') is None
    assert CP._generated_forms('B12') is None
    assert CP._generated_forms('Saturninus') == ['saturninus']
    assert CP.norm_word('Vespasiani') == 'uespasiani'
