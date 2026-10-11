"""Pack script and /api/scholarship/theme on a fixture of six windows."""
import json
import os
import sqlite3
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'scripts', 'scholarship'))

import pack_scholarship_theme as pack  # noqa: E402
from backend import scholarship_theme as st  # noqa: E402

DIM = 8
ROWS = [
    # id, source, work, ref, commentator, text
    ('allen:homer.iliad:0', 'commentary', 'homer.iliad', 'il. 1.1', 'Leaf', 'The wrath of Achilles begins the poem and the plague.'),
    ('conington:vergil.aeneid:0', 'commentary', 'vergil.aeneid', 'verg. aen. 1.8', 'Conington', 'The Muse is asked about the cause of the goddess anger.'),
    ('servius:vergil.aeneid:1', 'commentary', 'vergil.aeneid', 'verg. aen. 2.10', 'Servius', 'A catalogue of ships is a poetic device of Homer.'),
    ('ejc:1:0', 'ejc', 'vergil.aeneid', '1.1', 'A. Author (1866), Hermes', 'On the proem of the Aeneid and its models.'),
    ('ejc:2:0', 'ejc', 'homer.iliad', '2.484', 'B. Writer (1901), Classical Review', 'The catalogue of ships in the second book of the Iliad.'),
    ('ejc:3:0', 'ejc', 'nowhere.unknown', '3', 'C. Hand (1890), Hermes', 'Nothing about the matter at all, only filler words.'),
]


def unit(i):
    v = np.zeros(DIM, dtype=np.float32)
    v[i % DIM] = 1.0
    v[(i + 1) % DIM] = 0.3 * ((i * 7) % 5 + 1) / 5
    return v / np.linalg.norm(v)


@pytest.fixture
def index(tmp_path):
    d = tmp_path / 'idx'
    d.mkdir()
    ids = [r[0] for r in ROWS]
    np.save(d / 'embeddings.npy', np.stack([unit(i) * 1.01 for i in range(len(ROWS))]))
    json.dump(ids, open(d / 'ids.json', 'w'))
    with open(d / 'descriptions.jsonl', 'w', encoding='utf-8') as fh:
        for wid, src, work, ref, who, text in ROWS:
            fh.write(json.dumps({'id': wid, 'language': 'en', 'work': work, 'scale': 'note', 'ref_start': ref,
                                 'ref_end': 'verg. aen. 2.12' if wid.startswith('servius') else ref, 'commentator': who, 'source': src,
                                 'desc': {'mode': 'commentary', 'gist': text}, 'blob': text}) + '\n')
    cit = tmp_path / 'citations.db'
    c = sqlite3.connect(cit)
    c.executescript('CREATE TABLE articles (id INTEGER PRIMARY KEY, journal TEXT, title TEXT, authors TEXT, '
                    'year INTEGER, url_jstor TEXT, url_ia TEXT);'
                    'CREATE TABLE citations (id INTEGER PRIMARY KEY, article_id INTEGER);')
    c.executemany('INSERT INTO articles VALUES (?,?,?,?,?,?,?)', [
        (1, 'Hermes', 'Zum Proemium', 'A. Author', 1866, 'https://www.jstor.org/stable/1', None),
        (2, 'Classical Review', 'The Catalogue', 'B. Writer', 1901, None, 'https://archive.org/details/x2'),
        (3, 'Hermes', 'Fillers', 'C. Hand', 1890, 'https://www.jstor.org/stable/3', None)])
    c.executemany('INSERT INTO citations VALUES (?,?)', [(1, 1), (2, 2), (3, 3)])
    c.commit(); c.close()
    texts = tmp_path / 'texts'
    (texts / 'grc').mkdir(parents=True)
    (texts / 'la').mkdir()
    (texts / 'grc' / 'homer.iliad.tess').write_text('x')
    (texts / 'la' / 'vergil.aeneid.part.1.tess').write_text('x')
    return d, cit, texts


@pytest.fixture
def packed(index, tmp_path):
    d, cit, texts = index
    out = tmp_path / 'packed'
    m = pack.pack(str(d), str(out), str(cit), str(texts))
    return out, m


def test_pack_writes_the_files_and_halves_the_matrix(packed):
    out, m = packed
    assert sorted(os.listdir(out)) == ['embeddings.npy', 'ids.json', 'manifest.json', 'windows.jsonl', 'windows_fts.db']
    e = np.load(out / 'embeddings.npy')
    assert e.dtype == np.float16 and e.shape == (6, DIM)
    assert np.allclose(np.linalg.norm(e.astype(np.float32), axis=1), 1.0, atol=1e-2)
    assert m['rows'] == 6 and m['article_windows_with_metadata'] == 3
    assert m['sizes']['embeddings.npy'] == os.path.getsize(out / 'embeddings.npy')


def test_pack_reduces_windows_and_adds_article_metadata_and_work_language(packed):
    out, _ = packed
    rows = [json.loads(l) for l in open(out / 'windows.jsonl', encoding='utf-8')]
    assert [r['id'] for r in rows] == json.load(open(out / 'ids.json'))
    assert set(rows[0]) == {'id', 'source', 'language', 'work', 'work_language', 'ref_start', 'ref_end',
                            'commentator', 'journal', 'title', 'authors', 'year', 'url', 'text'}
    assert rows[0]['work_language'] == 'grc' and rows[1]['work_language'] == 'la'
    assert rows[5]['work_language'] is None
    assert rows[3]['journal'] == 'Hermes' and rows[3]['year'] == 1866 and rows[3]['url'].endswith('/stable/1')
    assert rows[4]['url'] == 'https://archive.org/details/x2'
    assert rows[0]['journal'] is None


def test_pack_fts_table_is_keyed_to_the_row(packed):
    out, _ = packed
    con = sqlite3.connect(out / 'windows_fts.db')
    hit = con.execute("SELECT rowid, id FROM f WHERE f MATCH 'catalogue' ORDER BY rowid").fetchall()
    assert hit == [(2, 'servius:vergil.aeneid:1'), (4, 'ejc:2:0')]


def test_rrf_orders_by_summed_reciprocal_rank():
    out = st.rrf([[5, 1, 2], [1, 5, 9]])
    assert [d for d, _ in out] == [5, 1, 2, 9]
    assert out[0][1] == pytest.approx(1 / 61 + 1 / 62)
    assert dict(out)[9] == pytest.approx(1 / 63)


def test_fts_query_quotes_words_and_drops_stop_words():
    assert st.fts_query('the catalogue of ships NEAR') == '"catalogue" OR "ships" OR "near"'
    assert st.fts_query('of the') == ''


@pytest.fixture
def client(packed, monkeypatch):
    out, _ = packed
    monkeypatch.setenv('TESSERAE_SCHOLARSHIP_THEME_DIR', str(out))
    from backend.app import app
    app.config['TESTING'] = True
    return app.test_client()


def fake_embed(vec):
    return lambda q: vec


def test_route_fuses_meaning_and_keyword(client, monkeypatch):
    # The vector sits on row 0, the keyword hits are rows 2 and 4: row 0 leads
    # the meaning list, rows 2 and 4 lead the keyword list.
    monkeypatch.setattr(st.coins_passage, 'embed', fake_embed(unit(2)))
    body = client.get('/api/scholarship/theme?q=catalogue of ships&k=4').get_json()
    assert body['available'] is True
    assert [r['rank'] for r in body['results']] == [1, 2, 3, 4]
    top = body['results'][0]
    assert top['id'] == 'servius:vergil.aeneid:1'
    assert top['meaning_rank'] == 1 and top['keyword_rank'] in (1, 2)
    scores = [r['score'] for r in body['results']]
    assert scores == sorted(scores, reverse=True)
    both = [r for r in body['results'] if r['meaning_rank'] and r['keyword_rank']]
    assert both and body['results'][0] in both
    assert 'fused' not in top
    assert body['label'] == ('Ranked by a blend of meaning and keyword search over 6 commentary notes and article '
                             'sentences. On fifteen test questions, thirteen had a strongly relevant note in the first ten.')


def test_route_cards_carry_links_snippet_and_article_fields(client, monkeypatch):
    monkeypatch.setattr(st.coins_passage, 'embed', fake_embed(unit(2)))
    body = client.get('/api/scholarship/theme?q=catalogue ships Aeneid Iliad proem&k=30').get_json()
    assert len(body['results']) == 6
    by = {r['id']: r for r in body['results']}
    c = by['servius:vergil.aeneid:1']
    assert c['kind'] == 'commentary' and c['commentator'] == 'Servius' and c['journal'] is None
    assert c['link'] == {'kind': 'reader', 'url': '/read?work=vergil.aeneid.tess&lang=la&ref=2.10&refEnd=2.12'}
    assert by['allen:homer.iliad:0']['link']['url'] == '/read?work=homer.iliad.tess&lang=grc&ref=1.1'
    a = by['ejc:1:0']
    assert a['kind'] == 'article' and a['journal'] == 'Hermes' and a['title'] == 'Zum Proemium' and a['year'] == 1866
    assert a['link'] == {'kind': 'jstor', 'url': 'https://www.jstor.org/stable/1'}
    assert by['ejc:2:0']['link']['url'] == 'https://archive.org/details/x2'
    assert by['ejc:3:0']['link']['kind'] == 'jstor'
    assert all(len(r['snippet']) <= 303 for r in body['results'])


def test_snippet_cuts_at_300_characters():
    s = st.snippet('word ' * 200)
    assert s.endswith('...') and 299 <= len(s) <= 303
    assert st.snippet('short  text') == 'short text'


def test_k_defaults_to_ten_and_is_capped_at_thirty(client, monkeypatch):
    monkeypatch.setattr(st.coins_passage, 'embed', fake_embed(unit(0)))
    assert (st.DEFAULT_K, st.MAX_K) == (10, 30)
    assert len(client.get('/api/scholarship/theme?q=iliad').get_json()['results']) == 6
    assert len(client.get('/api/scholarship/theme?q=iliad&k=2').get_json()['results']) == 2
    monkeypatch.setattr(st, 'MAX_K', 3)
    assert len(client.get('/api/scholarship/theme?q=iliad&k=500').get_json()['results']) == 3


def test_unavailable_without_the_files(tmp_path, monkeypatch):
    monkeypatch.setenv('TESSERAE_SCHOLARSHIP_THEME_DIR', str(tmp_path / 'none'))
    from backend.app import app
    app.config['TESTING'] = True
    body = app.test_client().get('/api/scholarship/theme?q=iliad').get_json()
    assert body['available'] is False and body['results'] == [] and body['reason']


def test_empty_query_and_encoder_down(client, monkeypatch):
    assert client.get('/api/scholarship/theme').get_json()['results'] == []

    def boom(q):
        raise RuntimeError('refused')
    monkeypatch.setattr(st.coins_passage, 'embed', boom)
    body = client.get('/api/scholarship/theme?q=iliad').get_json()
    assert body['unavailable'] is True and body['results'] == []


def test_files_out_of_step_are_unavailable(packed, monkeypatch):
    out, _ = packed
    json.dump(['only'], open(out / 'ids.json', 'w'))
    assert st.load(str(out)) == (None, None, None)


def test_count_reads_the_header(packed):
    out, _ = packed
    assert st.count(str(out)) == 6
    assert st.count(str(out / 'missing')) is None


def test_reader_ref_strips_the_citation_prefix():
    assert st.reader_ref('verg. aen. 1.1') == '1.1'
    assert st.reader_ref('h.hom. 1.1') == '1.1'
    assert st.reader_ref('126.1') == '126.1'
