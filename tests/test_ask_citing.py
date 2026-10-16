"""POST /passages/ask-citing: articles in the two citation indexes that cite the
passages on the Search One Text page, merged by article. Project MUSE
sentences are never in the answer. All sentences here are invented."""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app  # noqa: E402
from backend import scholarship as S  # noqa: E402
from backend.blueprints import passages  # noqa: E402
import pytest  # noqa: E402

SCHEMA = '''
  CREATE TABLE articles(id INTEGER PRIMARY KEY, ia_id TEXT, jstor_id TEXT, doi TEXT, journal TEXT, title TEXT, authors TEXT,
    year INTEGER, volume TEXT, issue TEXT, first_page INTEGER, n_pages INTEGER, url_ia TEXT, url_jstor TEXT, fetched_at TEXT, status TEXT);
  CREATE TABLE citations(id INTEGER PRIMARY KEY, article_id INTEGER, page INTEGER, work_id TEXT, locus_start TEXT, locus_end TEXT,
    open_ended INTEGER, surface TEXT, sentence TEXT, char_offset INTEGER);
'''
MUSE_TEXT = 'MUSESENTENCE invented licensed words'
EJC_TEXT = 'EJCSENTENCE invented old words'


def _db(path, rows):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA + rows)
    con.commit()
    con.close()
    return str(path)


@pytest.fixture
def indexes(tmp_path, monkeypatch):
    ejc = _db(tmp_path / 'citations.db', f'''
      INSERT INTO articles VALUES (1,'jstor-1','1',NULL,'Classical Philology','On the proem','A. Author',1910,'5','3',375,3,'https://archive.org/details/jstor-1','https://www.jstor.org/stable/1','','ok');
      INSERT INTO citations VALUES (1,1,376,'vergil.aeneid','1.1',NULL,0,'Aen. 1.1','{EJC_TEXT} one (Aen. 1.1).',0);
      INSERT INTO citations VALUES (2,1,377,'vergil.aeneid','6.1',NULL,0,'Aen. 6.1','{EJC_TEXT} two (Aen. 6.1).',0);
    ''')
    muse = _db(tmp_path / 'citations_muse.db', f'''
      INSERT INTO articles VALUES (1,'10.1353/x.1',NULL,'10.1353/x.1','American Journal of Philology','Arms and the poem','C. Scholar',2001,'122','1',5,20,NULL,'https://doi.org/10.1353/x.1','','ok');
      INSERT INTO citations VALUES (1,1,9,'vergil.aeneid','1.1',NULL,0,'Aen. 1.1','{MUSE_TEXT} (Aen. 1.1).',0);
      INSERT INTO citations VALUES (2,1,11,'vergil.aeneid','6.1',NULL,0,'Aen. 6.1','{MUSE_TEXT} (Aen. 6.1).',0);
      INSERT INTO articles VALUES (2,'10.1353/x.2',NULL,'10.1353/x.2','Classical World','Only book one','D. Other',2015,'1','1',1,5,NULL,'https://doi.org/10.1353/x.2','','ok');
      INSERT INTO citations VALUES (3,2,3,'vergil.aeneid','1.1',NULL,0,'Aen. 1.1','{MUSE_TEXT} three (Aen. 1.1).',0);
    ''')
    monkeypatch.setattr(S, 'CITATION_INDEX', ejc)
    monkeypatch.setenv('TESSERAE_CITATIONS_EXTRA', muse)
    passages._citing_cache.clear()
    yield
    passages._citing_cache.clear()


def _post(refs, work='vergil.aeneid'):
    return app.test_client().post('/api/passages/ask-citing', json={'work': work, 'refs': refs})


def test_articles_merge_across_passages_with_cites_and_ejc_sentences(indexes):
    body = _post([{'ref_start': 'verg. aen. 1.1', 'ref_end': 'verg. aen. 1.1'},
                  {'ref_start': 'verg. aen. 6.1', 'ref_end': 'verg. aen. 6.1'}]).get_json()
    assert body['available'] and body['total'] == 3
    by = {r['title']: r for r in body['results']}
    assert [r['title'] for r in body['results']] == ['Only book one', 'Arms and the poem', 'On the proem']  # newest first
    assert by['Arms and the poem']['cites'] == ['verg. aen. 1.1', 'verg. aen. 6.1']
    assert by['Arms and the poem']['source'] == 'muse' and by['Arms and the poem']['url'] == 'https://doi.org/10.1353/x.1'
    assert by['Only book one']['cites'] == ['verg. aen. 1.1']
    ejc = by['On the proem']
    assert ejc['source'] == 'ejc' and ejc['url'].endswith('/stable/1') and ejc['journal'] == 'Classical Philology'
    assert ejc['cites'] == ['verg. aen. 1.1', 'verg. aen. 6.1']
    assert [s['ref'] for s in ejc['sentences']] == ['verg. aen. 1.1', 'verg. aen. 6.1']


def test_muse_sentences_are_never_in_the_response(indexes):
    resp = _post([{'ref_start': 'verg. aen. 1.1'}, {'ref_start': 'verg. aen. 6.1'}])
    assert 'MUSESENTENCE' not in resp.get_data(as_text=True)
    assert 'EJCSENTENCE' in resp.get_data(as_text=True)
    for r in resp.get_json()['results']:
        if r['source'] == 'muse':
            assert r['sentences'] == []


def test_a_passage_nobody_cites_gives_an_empty_available_answer(indexes):
    body = _post([{'ref_start': 'verg. aen. 9.1'}]).get_json()
    assert body['available'] and body['results'] == [] and body['total'] == 0


def test_at_most_twenty_five_ranges_are_read(indexes, monkeypatch):
    seen = []
    real = S.passage_names
    monkeypatch.setattr(S, 'passage_names', lambda w, a, b=None: (seen.append(a), real(w, a, b))[1])
    _post([{'ref_start': f'verg. aen. 9.{i}'} for i in range(1, 41)])
    assert len(seen) == 25


def test_no_index_is_unavailable_and_missing_fields_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(S, 'CITATION_INDEX', str(tmp_path / 'none.db'))
    monkeypatch.delenv('TESSERAE_CITATIONS_EXTRA', raising=False)
    passages._citing_cache.clear()
    assert _post([{'ref_start': 'verg. aen. 1.1'}]).get_json()['available'] is False
    assert _post([]).get_json()['available'] is False
    assert app.test_client().post('/api/passages/ask-citing', json={'refs': [{'ref_start': 'x'}]}).get_json()['available'] is False


def test_the_answer_is_cached_for_the_same_work_and_refs(indexes, monkeypatch):
    refs = [{'ref_start': 'verg. aen. 1.1'}, {'ref_start': 'verg. aen. 6.1'}]
    first = _post(refs).get_json()
    monkeypatch.setattr(S, 'citation_index', lambda *a, **k: pytest.fail('read the index again'))
    assert _post(list(reversed(refs))).get_json() == first
