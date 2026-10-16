"""The optional second citation index (TESSERAE_CITATIONS_EXTRA, Project MUSE).

Setting absent: the answers are exactly the EJC index's (two recorded requests,
compared as JSON text). Setting present: its rows are added with source 'muse'
and a doi.org link. Missing file: logged once, ignored."""
import json
import logging
import sqlite3

SCHEMA = '''
  CREATE TABLE articles(id INTEGER PRIMARY KEY, ia_id TEXT, jstor_id TEXT, doi TEXT, journal TEXT, title TEXT, authors TEXT,
    year INTEGER, volume TEXT, issue TEXT, first_page INTEGER, n_pages INTEGER, url_ia TEXT, url_jstor TEXT, fetched_at TEXT, status TEXT);
  CREATE TABLE citations(id INTEGER PRIMARY KEY, article_id INTEGER, page INTEGER, work_id TEXT, locus_start TEXT, locus_end TEXT,
    open_ended INTEGER, surface TEXT, sentence TEXT, char_offset INTEGER);
'''


def _ejc(tmp_path):
    db = tmp_path / 'citations.db'
    con = sqlite3.connect(db)
    con.executescript(SCHEMA + '''
      INSERT INTO articles VALUES (1,'jstor-1','1',NULL,'Classical Philology','On the proem','A. Author; B. Other',1910,'5','3',375,3,'https://archive.org/details/jstor-1','https://www.jstor.org/stable/1','','ok');
      INSERT INTO citations VALUES (1,1,376,'vergil.aeneid','1.1','1.7',0,'Aen. 1.1-7','The proem (Aen. 1.1-7) states the theme.',0);
      INSERT INTO citations VALUES (2,1,377,'vergil.aeneid','8.1',NULL,0,'Aen. 8.1','Book eight opens (Aen. 8.1).',0);
    ''')
    con.commit()
    con.close()
    return str(db)


def _muse(tmp_path):
    db = tmp_path / 'citations_muse.db'
    con = sqlite3.connect(db)
    con.executescript(SCHEMA + '''
      INSERT INTO articles VALUES (1,'10.1353/ajp.2001.0001',NULL,'10.1353/ajp.2001.0001','American Journal of Philology','Arms and the poem','C. Scholar',2001,'122','1',5,20,NULL,'https://doi.org/10.1353/ajp.2001.0001','','ok');
      INSERT INTO citations VALUES (1,1,9,'vergil.aeneid','1.1',NULL,0,'Aen. 1.1','The opening line (Aen. 1.1) names arms before the man.',0);
      INSERT INTO citations VALUES (2,1,11,'vergil.aeneid','6.1',NULL,0,'Aen. 6.1','Book six begins (Aen. 6.1).',0);
    ''')
    con.commit()
    con.close()
    return str(db)


def _dump(x):
    return json.dumps(x, sort_keys=False, ensure_ascii=False)


# Recorded from the code before this change, fixture EJC database above.
RECORDED = {
    '1.3': '{"available": true, "results": [{"title": "On the proem", "authors": ["A. Author", "B. Other"], "venue": "Classical Philology", "year": 1910, "volume": "5", "issue": "3", "doi": null, "url": "https://www.jstor.org/stable/1", "url_jstor": "https://www.jstor.org/stable/1", "url_ia": "https://archive.org/details/jstor-1", "pages": [376], "cites": "Aen. 1.1-7", "cites_note": "", "snippet": "The proem (Aen. 1.1-7) states the theme.", "source": "citation_index"}], "total": 1, "note": "From the full text of journals before 1923 (JSTOR Early Journal Content, on the Internet Archive), indexed by passage with the citation extractor."}',
    '8.1': '{"available": true, "results": [{"title": "On the proem", "authors": ["A. Author", "B. Other"], "venue": "Classical Philology", "year": 1910, "volume": "5", "issue": "3", "doi": null, "url": "https://www.jstor.org/stable/1", "url_jstor": "https://www.jstor.org/stable/1", "url_ia": "https://archive.org/details/jstor-1", "pages": [377], "cites": "Aen. 8.1", "cites_note": "", "snippet": "Book eight opens (Aen. 8.1).", "source": "citation_index"}], "total": 1, "note": "From the full text of journals before 1923 (JSTOR Early Journal Content, on the Internet Archive), indexed by passage with the citation extractor."}',
}


def test_setting_absent_gives_the_ejc_answers_unchanged(tmp_path, monkeypatch):
    from backend import scholarship as S
    monkeypatch.delenv('TESSERAE_CITATIONS_EXTRA', raising=False)
    monkeypatch.setattr(S, 'CITATION_INDEX', _ejc(tmp_path))
    for lo, hi in (('1.3', '1.4'), ('8.1', '8.2')):
        assert _dump(S.citation_index({'work': 'vergil.aeneid', 'lo': lo, 'hi': hi})) == RECORDED[lo]


def test_second_index_adds_rows_with_tag_and_doi_link(tmp_path, monkeypatch):
    from backend import scholarship as S
    monkeypatch.setattr(S, 'CITATION_INDEX', _ejc(tmp_path))
    monkeypatch.setenv('TESSERAE_CITATIONS_EXTRA', _muse(tmp_path))
    out = S.citation_index({'work': 'vergil.aeneid', 'lo': '1.1', 'hi': '1.2'})
    assert out['available'] and out['total'] == 2
    by = {r['source']: r for r in out['results']}
    assert set(by) == {'citation_index', 'muse'}
    m = by['muse']
    assert m['url'] == 'https://doi.org/10.1353/ajp.2001.0001' and m['doi'] == '10.1353/ajp.2001.0001'
    assert m['url_jstor'] is None and m['url_ia'] is None
    assert m['year'] == 2001 and m['pages'] == [9] and m['cites'] == 'Aen. 1.1'
    assert 'Project MUSE' in out['note']
    assert out['results'][0]['source'] == 'muse'          # newest first
    assert by['citation_index']['url_jstor'].endswith('/stable/1')
    # A passage only MUSE cites; and one neither cites.
    only = S.citation_index({'work': 'vergil.aeneid', 'lo': '6.1', 'hi': '6.2'})
    assert [r['source'] for r in only['results']] == ['muse']
    assert S.citation_index({'work': 'vergil.aeneid', 'lo': '9.1', 'hi': '9.2'})['results'] == []


def test_second_index_alone_is_available_when_the_ejc_file_is_absent(tmp_path, monkeypatch):
    from backend import scholarship as S
    monkeypatch.setattr(S, 'CITATION_INDEX', str(tmp_path / 'none.db'))
    monkeypatch.setenv('TESSERAE_CITATIONS_EXTRA', _muse(tmp_path))
    out = S.citation_index({'work': 'vergil.aeneid', 'lo': '1.1', 'hi': '1.2'})
    assert out['available'] and [r['source'] for r in out['results']] == ['muse']


def test_missing_second_file_is_logged_once_and_ignored(tmp_path, monkeypatch, caplog):
    from backend import scholarship as S
    ejc = _ejc(tmp_path)
    monkeypatch.setattr(S, 'CITATION_INDEX', ejc)
    monkeypatch.setattr(S, '_extra_missing_logged', set())
    monkeypatch.setenv('TESSERAE_CITATIONS_EXTRA', str(tmp_path / 'absent.db'))
    a = {'work': 'vergil.aeneid', 'lo': '1.3', 'hi': '1.4'}
    with caplog.at_level(logging.WARNING, logger=S.logger.name):
        first = S.citation_index(dict(a))
        second = S.citation_index(dict(a))
    warns = [r for r in caplog.records if 'TESSERAE_CITATIONS_EXTRA' in r.getMessage()]
    assert len(warns) == 1
    assert first['total'] == 1 and _dump(first['results']) == _dump(second['results'])
    assert 'Project MUSE' not in first['note']
