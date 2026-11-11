"""The third citation index (TESSERAE_CITATIONS_JSTOR, the JSTOR text-analysis
delivery of 2026-11-09): rows carry source 'jstor', a link back to JSTOR and
no sentence, at JSTOR's request. Absent setting: answers unchanged."""
import importlib.util
import json
import os
import sqlite3

# tests/ is not a package: load the fixtures of the second-index test by path.
_spec = importlib.util.spec_from_file_location('citations_extra_fixtures',
                                               os.path.join(os.path.dirname(__file__), 'test_citations_extra.py'))
_extra = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_extra)
SCHEMA, _ejc, _muse = _extra.SCHEMA, _extra._ejc, _extra._muse


def _jstor(tmp_path):
    db = tmp_path / 'citations_jstor.db'
    con = sqlite3.connect(db)
    con.executescript(SCHEMA + '''
      INSERT INTO articles VALUES (1,'0001728e-aa11-388b-be1e-83f362e78455','0001728e-aa11-388b-be1e-83f362e78455','10.2307/123456','Classical Philology','The proem again','D. Reader',1988,'83','2',NULL,12,NULL,'https://www.jstor.org/stable/123456','2026-11-09','ok');
      INSERT INTO citations VALUES (1,1,3,'vergil.aeneid','1.1',NULL,0,'Aen. 1.1','A licensed sentence that must never be served (Aen. 1.1).',0);
      INSERT INTO articles VALUES (2,'id-2','id-2','10.2307/654321','Phoenix','No stable link kept','E. Writer',1975,'29','1',NULL,8,NULL,NULL,'2026-11-09','ok');
      INSERT INTO citations VALUES (2,2,5,'vergil.aeneid','1.2',NULL,0,'Aen. 1.2','Another licensed sentence (Aen. 1.2).',0);
      INSERT INTO articles VALUES (3,'id-3','id-3','10.2307/777777','Vergilius','Pages known','L. Reader',2025,'71',NULL,23,32,NULL,'https://www.jstor.org/stable/777777','2026-11-09','ok');
      INSERT INTO citations VALUES (3,3,2,'vergil.aeneid','1.2',NULL,0,'Aen. 1.2','A third licensed sentence (Aen. 1.2).',0);
    ''')
    con.commit()
    con.close()
    return str(db)


def test_setting_absent_leaves_the_answers_unchanged(tmp_path, monkeypatch):
    from backend import scholarship as S
    monkeypatch.setattr(S, 'CITATION_INDEX', _ejc(tmp_path))
    monkeypatch.setenv('TESSERAE_CITATIONS_EXTRA', _muse(tmp_path))
    monkeypatch.delenv('TESSERAE_CITATIONS_JSTOR', raising=False)
    before = json.dumps(S.citation_index({'work': 'vergil.aeneid', 'lo': '1.1', 'hi': '1.2'}), ensure_ascii=False)
    assert '"jstor"' not in before and 'JSTOR journals are read' not in before


def test_jstor_rows_carry_a_link_and_no_sentence(tmp_path, monkeypatch):
    from backend import scholarship as S
    monkeypatch.setattr(S, 'CITATION_INDEX', _ejc(tmp_path))
    monkeypatch.setenv('TESSERAE_CITATIONS_EXTRA', _muse(tmp_path))
    monkeypatch.setenv('TESSERAE_CITATIONS_JSTOR', _jstor(tmp_path))
    out = S.citation_index({'work': 'vergil.aeneid', 'lo': '1.1', 'hi': '1.2'})
    assert out['available'] and out['total'] == 5
    by = {}
    for r in out['results']:
        by.setdefault(r['source'], []).append(r)
    assert set(by) == {'citation_index', 'muse', 'jstor'}
    paged, stable, bare = sorted(by['jstor'], key=lambda r: r['year'], reverse=True)
    # When the index knows the article's first printed page (23 here), the
    # citing page is listed as a printed page number (index 2 -> p. 25) and
    # the link still opens on that page of the scan (?seq=3).
    assert paged['pages'] == [25] and paged['url'] == 'https://www.jstor.org/stable/777777?seq=3'
    # The delivery has no printed page numbers: the stable link opens on the
    # citing page (?seq= counts from 1, the stored page index from 0) and no
    # page number is listed.
    assert stable['url'] == 'https://www.jstor.org/stable/123456?seq=4' and stable['url_jstor'] == stable['url']
    assert stable['url_ia'] is None and stable['snippet'] is None
    assert stable['cites'] == 'Aen. 1.1' and stable['pages'] == []
    assert bare['url'] == 'https://doi.org/10.2307/654321' and bare['snippet'] is None
    assert 'licensed sentence' not in json.dumps(out, ensure_ascii=False)
    assert 'no excerpt' in out['note']
    # The MUSE sentence and the EJC sentence are still there.
    assert by['muse'][0]['snippet'] and by['citation_index'][0]['snippet']


def test_jstor_index_alone_is_available(tmp_path, monkeypatch):
    from backend import scholarship as S
    monkeypatch.setattr(S, 'CITATION_INDEX', str(tmp_path / 'none.db'))
    monkeypatch.delenv('TESSERAE_CITATIONS_EXTRA', raising=False)
    monkeypatch.setenv('TESSERAE_CITATIONS_JSTOR', _jstor(tmp_path))
    out = S.citation_index({'work': 'vergil.aeneid', 'lo': '1.1', 'hi': '1.2'})
    assert out['available'] and sorted(r['source'] for r in out['results']) == ['jstor', 'jstor', 'jstor']


def test_citing_articles_never_returns_a_jstor_sentence(tmp_path, monkeypatch):
    from backend import scholarship as S
    monkeypatch.setattr(S, 'CITATION_INDEX', _ejc(tmp_path))
    monkeypatch.setenv('TESSERAE_CITATIONS_JSTOR', _jstor(tmp_path))
    monkeypatch.setattr(S, 'passage_names', lambda work, lo, hi: {'work': work, 'lo': lo, 'hi': hi or lo})
    out = S.citing_articles('vergil.aeneid', [('1.1', '1.2')])
    assert out['available']
    by = {}
    for r in out['results']:
        by.setdefault(r['source'], []).append(r)
    assert set(by) == {'ejc', 'jstor'} and len(by['jstor']) == 3
    urls = sorted(r['url'] for r in by['jstor'])
    assert urls == ['https://doi.org/10.2307/654321', 'https://www.jstor.org/stable/123456?seq=4', 'https://www.jstor.org/stable/777777?seq=3']
    assert all(r['sentences'] == [] for r in by['jstor'])
    assert by['ejc'][0]['sentences']
    assert 'licensed sentence' not in json.dumps(out, ensure_ascii=False)


def test_about_page_lists_the_jstor_index(tmp_path, monkeypatch):
    from backend import scholarship as S
    from backend import scholarship_about as A
    monkeypatch.setattr(S, 'CITATION_INDEX', _ejc(tmp_path))
    monkeypatch.setenv('TESSERAE_CITATIONS_JSTOR', _jstor(tmp_path))
    monkeypatch.delenv('TESSERAE_CITATIONS_EXTRA', raising=False)
    built = A.build()
    ids = [b['id'] for b in built['journals']]
    assert ids == ['ejc', 'jstor']
    j = built['journals'][1]
    assert j['available'] and 'No sentence' in j['terms'] and j['totals']['articles'] == 3
