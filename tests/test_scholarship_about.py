"""GET /api/scholarship/about on fixtures: two citation databases with the
same schema (the 1827 to 1922 index and the second index), a commentaries
folder, and a texts folder that gives the commented works their language."""
import json
import os
import sqlite3

import pytest

from backend import scholarship as S
from backend import scholarship_about as A

SCHEMA = """
CREATE TABLE articles (id INTEGER PRIMARY KEY, ia_id TEXT, jstor_id TEXT, doi TEXT, journal TEXT, title TEXT,
  authors TEXT, year INTEGER, volume TEXT, issue TEXT, first_page INTEGER, n_pages INTEGER, url_ia TEXT,
  url_jstor TEXT, fetched_at TEXT, status TEXT);
CREATE TABLE citations (id INTEGER PRIMARY KEY, article_id INTEGER, page INTEGER, work_id TEXT, locus_start TEXT,
  locus_end TEXT, open_ended INTEGER, surface TEXT, sentence TEXT, char_offset INTEGER);
"""


def make_db(path, journal, years):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    for i, y in enumerate(years, 1):
        con.execute("INSERT INTO articles (id, journal, year, status) VALUES (?, ?, ?, 'ok')", (i, journal, y))
    con.execute("INSERT INTO articles (id, journal, year, status) VALUES (99, ?, 1800, 'error:x')", (journal,))
    con.execute("INSERT INTO citations (article_id, work_id, locus_start, sentence) VALUES (1, 'vergil.aeneid', '1.1', 's')")
    con.execute("INSERT INTO citations (article_id, work_id, locus_start, sentence) VALUES (1, 'vergil.aeneid', '1.2', 's')")
    con.execute("INSERT INTO citations (article_id, work_id, locus_start, sentence) VALUES (2, 'vergil.aeneid', '2.1', 's')")
    con.commit()
    con.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    ejc = tmp_path / 'ejc.db'
    muse = tmp_path / 'muse.db'
    make_db(ejc, 'Hermes', [1866, 1869, 1867])
    make_db(muse, 'Classical Journal', [2007, 2026])
    com = tmp_path / 'commentaries'
    com.mkdir()
    (com / 'servius__vergil.aeneid.json').write_text(json.dumps({
        'work': 'vergil.aeneid', 'commentator': 'Servius', 'title': 'In Aeneidos', 'edition': 'Thilo',
        'source': 'https://example.org/servius', 'license': 'Public domain', 'language': 'la',
        'units': [{'ref': 'verg. aen. 1.1', 'text': 'x'}, {'ref': 'verg. aen. 1.2', 'text': 'y'}]}), encoding='utf-8')
    (com / 'mystery__nowhere.work.json').write_text(json.dumps({
        'work': 'nowhere.work', 'commentator': 'Mystery', 'title': 'T', 'units': [{'ref': '1', 'text': 'z'}]}), encoding='utf-8')
    texts = tmp_path / 'texts' / 'la'
    texts.mkdir(parents=True)
    (texts / 'vergil.aeneid.tess').write_text('')
    monkeypatch.setattr(S, 'ROOT', str(tmp_path))
    monkeypatch.setattr(S, 'COMMENTARY_DIR', str(com))
    monkeypatch.setattr(S, 'CITATION_INDEX', str(ejc))
    monkeypatch.setenv(S.CITATIONS_EXTRA_ENV, str(muse))
    S._sources_cache.update(stamp=None, rows=None)
    A.clear_cache()
    from backend.app import app
    yield app.test_client(), str(ejc), str(muse), str(com)
    A.clear_cache()
    S._sources_cache.update(stamp=None, rows=None)


def get(c):
    for path in ('/api/scholarship/about', '/scholarship/about'):
        r = c.get(path)
        if r.status_code == 200:
            return r.get_json()
    raise AssertionError('about route not found')


def test_shape_and_journal_tables(client):
    c, ejc, muse, com = client
    d = get(c)
    assert set(d) == {'commentaries', 'journals', 'online', 'methods', 'updated'}
    by_id = {b['id']: b for b in d['journals']}
    assert list(by_id) == ['ejc', 'muse']
    assert by_id['ejc']['journals'] == [{'journal': 'Hermes', 'year_from': 1866, 'year_to': 1869, 'articles': 3,
                                         'articles_with_citations': 2, 'citations': 3}]
    assert by_id['muse']['journals'][0]['year_to'] == 2026
    assert by_id['ejc']['totals'] == {'articles': 3, 'articles_with_citations': 2, 'citations': 3}


def test_terms_are_written_in_the_backend(client):
    d = get(client[0])
    terms = {b['id']: b['terms'] for b in d['journals']}
    assert terms['ejc'] == 'Public domain, full text indexed and quoted by the sentence.'
    assert 'never displayed beyond one sentence in the Reader' in terms['muse']
    assert 'article titles and links are shown' in terms['muse'].lower()


def test_commentaries_grouped_by_language_of_the_work(client):
    d = get(client[0])
    groups = {g['language']: g for g in d['commentaries']}
    assert [r['commentator'] for r in groups['la']['commentaries']] == ['Servius']
    assert groups['la']['language_name'] == 'Latin'
    assert [r['commentator'] for r in groups['other']['commentaries']] == ['Mystery']
    assert d['commentaries'][-1]['language'] == 'other'


def test_services_and_methods_text(client):
    d = get(client[0])
    names = [s['name'] for s in d['online']['services']]
    assert names == ['OpenAlex', 'Crossref', 'Unpaywall', 'CORE', 'Semantic Scholar', 'Google Books', 'HathiTrust']
    assert 'library link' in d['online']['note']
    ids = [m['id'] for m in d['methods']]
    assert ids == ['recognition', 'citing', 'paragraph', 'online', 'never']
    text = ' '.join(m['text'] for m in d['methods'])
    assert '58 of 60' in text and '88 percent' in text and '13 of 15' in text and '0.64' in text


def test_mtimes(client):
    c, ejc, muse, com = client
    d = get(c)
    assert d['updated']['indexes'] == {'ejc': int(os.path.getmtime(ejc)), 'muse': int(os.path.getmtime(muse))}
    assert d['updated']['commentaries'] >= int(os.path.getmtime(os.path.join(com, 'servius__vergil.aeneid.json')))


def test_second_index_off_when_unset(client, monkeypatch):
    monkeypatch.delenv(S.CITATIONS_EXTRA_ENV)
    A.clear_cache()
    d = get(client[0])
    assert [b['id'] for b in d['journals']] == ['ejc']


def test_answer_is_cached_for_an_hour(client, monkeypatch):
    c = client[0]
    get(c)
    monkeypatch.setattr(A, 'build', lambda: pytest.fail('rebuilt inside the hour'))
    get(c)
