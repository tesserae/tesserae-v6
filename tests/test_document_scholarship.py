"""Document scholarship index: the builder on a three-article, two-document
fixture, and GET /api/documents/<id>/scholarship over the built file. No
corpus data and no network."""
import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.documents.build_document_citation_index import build, split_sentences  # noqa: E402
import backend.document_scholarship as ds  # noqa: E402
import backend.documents as docs  # noqa: E402


@pytest.fixture
def built(tmp_path):
    meta = tmp_path / 'metadata.db'
    c = sqlite3.connect(meta)
    c.execute('CREATE TABLE documents (id TEXT, source TEXT, principal_edition TEXT)')
    c.executemany('INSERT INTO documents VALUES (?,?,?)', [
        ('edh:D1', 'edh', 'CIL VI 1234.'),
        ('edh:D2', 'edh', 'AE 1976, 123.'),
    ])
    c.commit()
    c.close()
    arts = tmp_path / 'articles.db'
    c = sqlite3.connect(arts)
    c.execute('CREATE TABLE articles (id INTEGER PRIMARY KEY, ia_id TEXT, jstor_id TEXT, journal TEXT, title TEXT, '
              'authors TEXT, year INTEGER, first_page INTEGER, status TEXT)')
    c.executemany('INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?)', [
        (1, 'jstor-1', '1', 'Hermes', 'Old notes', 'A. Author', 1866, 10, 'ok'),
        (2, 'jstor-2', '2', 'Classical Review', 'New notes', 'B. Writer; C. Other', 1905, 100, 'ok'),
        (3, 'jstor-3', '3', 'Hermes', 'Back Matter', None, 1910, 1, 'ok'),
    ])
    c.commit()
    c.close()
    raw = tmp_path / 'raw'
    raw.mkdir()
    (raw / 'jstor-1_djvu.txt').write_text('Intro text.\n\x0cThe tombstone (CIL VI 1234) names a freedman. Nothing else here.')
    (raw / 'jstor-2_djvu.txt').write_text('See AE 1976, 123 for the date. Also CIL VI 99999, which is not in the corpus.')
    (raw / 'jstor-3_djvu.txt').write_text('CIL VI 1234 in an index of names.')
    comm = tmp_path / 'comm'
    comm.mkdir()
    (comm / 'x__work.json').write_text(json.dumps({
        'title': 'A Commentary', 'commentator': 'D. Editor',
        'units': [{'ref': 'l. 5', 'text': 'Compare CIL VI 1234 for the name.'}]}))
    out = tmp_path / 'document_citations.db'
    m = build(str(out), str(meta), str(arts), str(raw), str(comm))
    return out, m


def test_builder_rows(built):
    out, m = built
    assert m['rows'] == 3 and m['distinct_documents'] == 2 and m['distinct_articles'] == 2
    assert m['skipped_matter'] == 1 and m['unlinked'] == 1
    c = sqlite3.connect(out)
    rows = c.execute('SELECT doc_id, source, year, page, family_key FROM citations ORDER BY id').fetchall()
    assert ('edh:D1', 'ejc', 1866, 11, 'CIL:CIL:6:1234:') in rows   # second page of the article
    assert ('edh:D2', 'ejc', 1905, 100, 'AE:AE:1976:123:') in rows
    assert ('edh:D1', 'commentary', None, None, 'CIL:CIL:6:1234:') in rows
    assert c.execute("SELECT value FROM meta WHERE key='rows'").fetchone()[0] == '3'


def test_builder_refuses_to_overwrite(built, tmp_path):
    out, _ = built
    with pytest.raises(SystemExit):
        build(str(out), '', '', '', '')


def test_sentence_split_keeps_citation_whole():
    parts = [s for _, s in split_sentences('First. See CIL. VI 1234 now. Next one.')]
    assert any('CIL. VI 1234' in p for p in parts)


def test_scholarship_for_orders_newest_first_with_links(built):
    out, _ = built
    r = ds.scholarship_for('edh:D1', str(out))
    assert r['available'] and r['count'] == 2
    assert [x['source'] for x in r['results']] == ['ejc', 'commentary']   # dated before undated
    j = r['results'][0]
    assert j['url'] == 'https://www.jstor.org/stable/1'
    assert 'tombstone' in j['excerpt'] and 'Hermes' in j['citation']
    assert r['results'][1]['commentary_file'] == 'x__work.json'
    assert ds.scholarship_for('edh:NONE', str(out))['count'] == 0


def test_scholarship_for_without_index(tmp_path):
    assert ds.scholarship_for('edh:D1', str(tmp_path / 'absent.db')) == {'available': False, 'count': 0, 'results': []}


def test_route(built, monkeypatch):
    from backend.app import app
    out, _ = built
    monkeypatch.setattr(ds, 'DOCUMENT_CITATIONS', str(out))
    monkeypatch.setattr(docs, 'enabled', lambda: True)
    client = app.test_client()
    r = client.get('/api/documents/edh:D2/scholarship')
    assert r.status_code == 200
    j = r.get_json()
    assert j['doc_id'] == 'edh:D2' and j['count'] == 1 and j['results'][0]['url'].endswith('/2')
    monkeypatch.setattr(docs, 'enabled', lambda: False)
    assert client.get('/api/documents/edh:D2/scholarship').status_code == 404
