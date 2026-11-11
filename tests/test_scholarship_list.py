"""GET /api/scholarship/list on three fixture indexes. Every title, name and
sentence below is invented; the JSTOR sentences are stand-ins and are never
returned by the route, only matched against."""
import importlib.util
import os
import sqlite3

import pytest
from flask import Flask

_spec = importlib.util.spec_from_file_location('citations_extra_fixtures',
                                               os.path.join(os.path.dirname(__file__), 'test_citations_extra.py'))
_extra = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_extra)
SCHEMA, _ejc = _extra.SCHEMA, _extra._ejc


def _muse(tmp_path):
    db = tmp_path / 'm.db'
    con = sqlite3.connect(db)
    con.executescript(SCHEMA + '''
      INSERT INTO articles VALUES (1,'x',NULL,'10.1353/ajp.2001.0001','American Journal of Philology','Arms and the poem','C. Scholar',2001,'122','1',5,20,NULL,'https://doi.org/10.1353/ajp.2001.0001','','ok');
      INSERT INTO citations VALUES (1,1,9,'vergil.aeneid','1.1',NULL,0,'Aen. 1.1','The opening line (Aen. 1.1) names arms before the man.',0);
      INSERT INTO citations VALUES (2,1,11,'vergil.aeneid','1.40',NULL,0,'Aen. 1.40','A later line (Aen. 1.40) in the same book.',0);
      INSERT INTO articles VALUES (2,'y',NULL,'10.1353/phx.2010.0002','Phoenix','Dido and the nymphs of Carthage','Hélène Dupré; Q. Second',2010,'64','2',1,9,NULL,NULL,'','ok');
      INSERT INTO citations VALUES (3,2,3,'vergil.aeneid','1.2',NULL,0,'Aen. 1.2','Her grief at the shore (Aen. 1.2) recalls a résumé of exile.',0);
      INSERT INTO citations VALUES (4,2,4,'vergil.aeneid','4.1',NULL,0,'Aen. 4.1','Book four begins (Aen. 4.1).',0);
    ''')
    con.commit()
    con.close()
    return str(db)


def _jstor(tmp_path, kind=False):
    db = tmp_path / ('j_kind.db' if kind else 'j.db')
    con = sqlite3.connect(db)
    con.executescript(SCHEMA + '''
      INSERT INTO articles VALUES (1,'a1','a1','10.2307/123456','Classical Philology','The proem again','D. Reader',1988,'83','2',NULL,12,NULL,'https://www.jstor.org/stable/123456','','ok');
      INSERT INTO citations VALUES (1,1,3,'vergil.aeneid','1.1',NULL,0,'Aen. 1.1','An invented sentence about a naiad (Aen. 1.1).',0);
      INSERT INTO articles VALUES (2,'a2','a2','10.2307/654321','Phoenix','Notes on a book of verse','E. Writer',1975,'29','1',NULL,8,NULL,NULL,'','ok');
      INSERT INTO citations VALUES (2,2,5,'vergil.aeneid','1.2',NULL,0,'Aen. 1.2','Another invented sentence (Aen. 1.2).',0);
      INSERT INTO articles VALUES (3,'a3','a3','10.1353/ajp.2001.0001','American Journal of Philology','Arms and the poem','C. Scholar',2001,'122','1',NULL,20,NULL,'https://www.jstor.org/stable/777','','ok');
      INSERT INTO citations VALUES (3,3,7,'vergil.aeneid','1.40',NULL,0,'Aen. 1.40','Invented (Aen. 1.40).',0);
      INSERT INTO articles VALUES (4,'a4','a4','10.2307/555','Classical World','Eighth book gloss','F. Last',1990,'3','1',NULL,2,NULL,'https://www.jstor.org/stable/555','','ok');
      INSERT INTO citations VALUES (4,4,1,'vergil.aeneid','8.5',NULL,0,'Aen. 8.5','Invented (Aen. 8.5).',0);
    ''')
    # Article 1 has a known first printed page (23): its citation on page index 3 is p. 26.
    con.execute("UPDATE articles SET first_page=23 WHERE id=1")
    if kind:
        con.executescript("ALTER TABLE articles ADD COLUMN kind TEXT; UPDATE articles SET kind='review' WHERE id=2; "
                          "UPDATE articles SET kind='other' WHERE id=4; UPDATE articles SET kind='article' WHERE id IN (1,3);")
    con.commit()
    con.close()
    return str(db)


@pytest.fixture
def client(tmp_path, monkeypatch):
    from backend import scholarship as S
    from backend import scholarship_list as L
    from backend.blueprints.scholarship import scholarship_bp
    monkeypatch.setattr(S, 'CITATION_INDEX', _ejc(tmp_path))
    monkeypatch.setenv('TESSERAE_CITATIONS_EXTRA', _muse(tmp_path))
    monkeypatch.setenv('TESSERAE_CITATIONS_JSTOR', _jstor(tmp_path))
    monkeypatch.setattr(S, 'passage_names', lambda work, lo, hi=None: {
        'work': work, 'title': 'Aeneid', 'abbrev': 'Aen.', 'lo': lo, 'hi': hi or lo,
        'locus': lo if not hi or hi == lo else f'{lo}-{hi.split(".")[-1]}'})
    L._scans.clear()
    app = Flask(__name__)
    app.register_blueprint(scholarship_bp, url_prefix='/api')
    c = app.test_client()

    def get(**params):
        params.setdefault('work', 'vergil.aeneid')
        return c.get('/api/scholarship/list', query_string=params)
    get.tmp_path, get.monkeypatch = tmp_path, monkeypatch
    return get


def titles(r):
    return [x['title'] for x in r.get_json()['results']]


def test_counts_for_the_three_scopes(client):
    d = client(lo='1.1', hi='1.33').get_json()
    assert d['available'] and d['scope']['label'] == 'Aen. 1.1-33' and d['scope']['scope'] == 'passage'
    assert d['counts'] == {'passage': 5, 'book': 5, 'work': 6}
    assert d['total'] == 5
    assert client(lo='1.1', scope='book').get_json()['total'] == 5
    w = client(scope='work').get_json()
    assert w['total'] == 6 and w['scope']['label'] == 'Aeneid'
    assert client().get_json()['scope']['scope'] == 'work'
    assert client(lo='1.40', hi='1.41').get_json()['total'] == 1    # the merged MUSE/JSTOR article only


def test_jstor_printed_page_when_the_first_page_is_known(client):
    rows = {x['title']: x for x in client(scope='work').get_json()['results']}
    assert rows['The proem again']['pages'] == [26]          # first page 23 + page index 3
    assert rows['Notes on a book of verse']['pages'] == []   # first page unknown
    assert rows['The proem again']['url'] == 'https://www.jstor.org/stable/123456?seq=4'


def test_merge_lists_one_article_with_both_sources(client):
    d = client(scope='work', q='arms and the poem').get_json()
    assert d['total'] == 1
    r = d['results'][0]
    assert r['source'] == 'muse' and r['sources'] == ['muse', 'jstor']
    assert [c['locus'] for c in r['cites']] == ['1.1', '1.40']
    assert r['url'] == 'https://doi.org/10.1353/ajp.2001.0001' and r['url_jstor'] == 'https://www.jstor.org/stable/777?seq=8'
    assert len(r['sentences']) == 2
    assert r['key']


def test_filters_narrow(client):
    assert sorted(titles(client(scope='work', source='ejc'))) == ['On the proem']
    assert len(titles(client(scope='work', source='muse,jstor'))) == 5
    assert titles(client(scope='work', year_from=2000)) == ['Dido and the nymphs of Carthage', 'Arms and the poem']
    assert titles(client(scope='work', year_to=1950)) == ['On the proem']
    assert titles(client(scope='work', journal='Phoenix', sort='oldest')) == [
        'Notes on a book of verse', 'Dido and the nymphs of Carthage']
    assert client(scope='work', journal='Phoenix').get_json()['total'] == 2


def test_search_matches_title_author_journal_and_sentences(client):
    assert titles(client(scope='work', q='PROEM AGAIN')) == ['The proem again']       # title, case
    assert titles(client(scope='work', q='helene dupre')) == ['Dido and the nymphs of Carthage']  # author, accents
    assert titles(client(scope='work', q='Hélène')) == ['Dido and the nymphs of Carthage']
    assert titles(client(scope='work', q='classical world')) == ['Eighth book gloss']  # journal
    assert titles(client(scope='work', q='grief at the shore')) == ['Dido and the nymphs of Carthage']  # MUSE sentence
    assert titles(client(scope='work', q='resume of exile')) == ['Dido and the nymphs of Carthage']  # accent-insensitive
    r = client(scope='work', q='states the theme')                                   # EJC sentence
    assert titles(r) == ['On the proem'] and r.get_json()['results'][0]['sentences']
    j = client(scope='work', q='about a naiad').get_json()                           # JSTOR sentence
    assert [x['title'] for x in j['results']] == ['The proem again']
    assert j['results'][0]['sentences'] == [] and 'naiad' not in str(j)


def test_search_sentence_follows_the_scope(client):
    assert titles(client(lo='1.1', hi='1.33', q='later line')) == []   # 1.40 is outside the passage
    assert titles(client(lo='1.1', scope='book', q='later line')) == ['Arms and the poem']


def test_sorts(client):
    assert titles(client(scope='work')) == ['Dido and the nymphs of Carthage', 'Arms and the poem', 'Eighth book gloss',
                                            'The proem again', 'Notes on a book of verse', 'On the proem']
    assert titles(client(scope='work', sort='oldest')) == ['On the proem', 'Notes on a book of verse', 'The proem again',
                                                           'Eighth book gloss', 'Arms and the poem',
                                                           'Dido and the nymphs of Carthage']
    assert titles(client(scope='work', sort='author')) == ['On the proem', 'Dido and the nymphs of Carthage',
                                                           'Eighth book gloss', 'The proem again', 'Arms and the poem',
                                                           'Notes on a book of verse']
    assert titles(client(scope='work', sort='journal')) == ['Arms and the poem', 'The proem again', 'On the proem',
                                                            'Eighth book gloss', 'Dido and the nymphs of Carthage',
                                                            'Notes on a book of verse']
    most = client(lo='1.1', scope='book', sort='most').get_json()['results']
    assert most[0]['title'] == 'Arms and the poem' and len(most[0]['cites']) == 2
    assert client(lo='1.1', hi='1.33', sort='most').get_json()['results'][0]['title'] != ''


def test_paging(client):
    d = client(scope='work', per_page=2, page=2).get_json()
    assert d['page'] == 2 and d['per_page'] == 2 and d['total'] == 6 and len(d['results']) == 2
    assert client(scope='work', per_page=2, page=4).get_json()['results'] == []
    assert titles(client(scope='work', per_page=2, page=1)) + titles(client(scope='work', per_page=2, page=2)) \
        + titles(client(scope='work', per_page=2, page=3)) == titles(client(scope='work'))
    assert client(scope='work', per_page=500).get_json()['per_page'] == 200


def test_facets_describe_the_filtered_set(client):
    f = client(scope='work').get_json()['facets']
    assert f['source'] == {'ejc': 1, 'muse': 2, 'jstor': 4}
    assert f['decade'] == {'1910': 1, '1970': 1, '1980': 1, '1990': 1, '2000': 1, '2010': 1}
    assert f['kind'] == {'article': 6}
    assert f['journal'][:2] == [['Classical Philology', 2], ['Phoenix', 2]] and len(f['journal']) == 4
    g = client(scope='work', year_from=1980).get_json()['facets']
    assert g['decade'] == {'1980': 1, '1990': 1, '2000': 1, '2010': 1}


def test_kind_column_present_and_absent(client):
    d = client(scope='work').get_json()
    assert {r['kind'] for r in d['results']} == {'article'}               # column absent: all articles
    client.monkeypatch.setenv('TESSERAE_CITATIONS_JSTOR', _jstor(client.tmp_path, kind=True))
    from backend import scholarship_list as L
    L._scans.clear()
    d = client(scope='work').get_json()
    assert d['facets']['kind'] == {'article': 4, 'review': 1, 'other': 1}
    assert titles(client(scope='work', kind='review')) == ['Notes on a book of verse']
    assert sorted(titles(client(scope='work', kind='review,other'))) == ['Eighth book gloss', 'Notes on a book of verse']
    assert [r['kind'] for r in d['results']] == ['article'] * 4 + ['review', 'other']   # articles first, default sort


def test_invalid_parameters_answer_400(client):
    for bad in ({'work': ''}, {'scope': 'chapter'}, {'scope': 'passage'}, {'lo': '1.1', 'sort': 'random'},
                {'source': 'ejc,bogus'}, {'kind': 'book'}, {'year_from': 'x'}, {'page': 0}, {'per_page': 'many'},
                {'year_from': 2000, 'year_to': 1990}, {'hi': '1.3'}):
        r = client(**bad)
        assert r.status_code == 400, bad
        assert r.get_json()['error'] and len(r.get_json()['error']) < 80


def test_no_index_is_unavailable(client):
    from backend import scholarship as S
    client.monkeypatch.setattr(S, 'CITATION_INDEX', str(client.tmp_path / 'none.db'))
    client.monkeypatch.delenv('TESSERAE_CITATIONS_EXTRA')
    client.monkeypatch.delenv('TESSERAE_CITATIONS_JSTOR')
    from backend import scholarship_list as L
    L._scans.clear()
    d = client(scope='work').get_json()
    assert d['available'] is False and d['results'] == []
