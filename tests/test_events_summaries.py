"""scripts/events/add_summaries.py and relink_scholarship.py on a fixture
database of three events (one with a Wikipedia intro, one without, one whose
passages cite nothing), and the Events API fields they feed."""
import json
import os
import sqlite3
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, 'scripts', 'events')
sys.path.insert(0, SCRIPTS)
import add_summaries  # noqa: E402
import relink_scholarship  # noqa: E402

LONG = ('The siege lasted a week. ' * 30).strip()


def _build(path):
    c = sqlite3.connect(path)
    c.executescript('''
    CREATE TABLE events (id TEXT PRIMARY KEY, label TEXT, type TEXT, date_start INTEGER, date_end INTEGER,
      place TEXT, lat REAL, lon REAL, pleiades_id TEXT, participants TEXT, wikipedia_title TEXT, description TEXT);
    CREATE TABLE passages (event_id TEXT, rank INTEGER, work TEXT, ref_start TEXT, ref_end TEXT, score REAL,
      llm_label TEXT, names_matched TEXT, snippet TEXT, language TEXT, window_id TEXT);
    CREATE TABLE documents (event_id TEXT, doc_id TEXT, date_start INTEGER, date_end INTEGER, place TEXT,
      distance_km REAL, text_snippet TEXT, language TEXT, lat REAL, lon REAL);
    CREATE TABLE scholarship (event_id TEXT, kind TEXT, title TEXT, page_ref TEXT, url TEXT);
    CREATE TABLE judgements (event_id TEXT, window_id TEXT, label TEXT);
    ''')
    c.executemany('INSERT INTO events (id, label, type, date_start, date_end, wikipedia_title, description) '
                  'VALUES (?,?,?,?,?,?,?)', [
        ('Q1', 'Siege of Corfinium', 'siege', -49, -49, 'Siege of Corfinium', 'siege in 49 BC'),
        ('Q2', 'Battle of Nowhere', 'battle', -300, -300, None, 'a battle'),
        ('Q3', 'Treaty of Silence', 'treaty', -200, -200, 'Treaty of Silence', 'a treaty'),
    ])
    P = 'INSERT INTO passages (event_id, rank, work, ref_start, ref_end, llm_label) VALUES (?,?,?,?,?,?)'
    c.executemany(P, [
        ('Q1', 1, 'caesar.de_bello_civili', 'caes. bel. civ. 1.16.2', 'caes. bel. civ. 1.18.5', 'yes'),
        ('Q1', 2, 'caesar.de_bello_civili', 'caes. bel. civ. 1.20.1', 'caes. bel. civ. 1.22.1', 'yes'),
        ('Q1', 30, 'caesar.de_bello_civili', 'caes. bel. civ. 2.1.1', 'caes. bel. civ. 2.2.1', 'mention'),
        ('Q3', 1, 'caesar.de_bello_civili', 'caes. bel. civ. 3.40.1', 'caes. bel. civ. 3.41.1', 'yes'),
    ])
    c.executemany('INSERT INTO scholarship VALUES (?,?,?,?,?)', [
        ('Q1', 'article', 'Old row', 'old', 'https://x/old'),
        ('Q1', 'commentary', 'Commentator on caesar', 'caes. bel. civ. 1.21.2', None),
        ('Q1', 'commentary', 'Commentator on caesar', 'caes. bel. civ. 9.9.9', None),
    ])
    c.commit()
    c.close()


def _citation_index(path):
    c = sqlite3.connect(path)
    c.executescript('''
    CREATE TABLE articles (id INTEGER PRIMARY KEY, ia_id TEXT, jstor_id TEXT, doi TEXT, journal TEXT, title TEXT,
      authors TEXT, year INTEGER, volume TEXT, issue TEXT, first_page INTEGER, n_pages INTEGER, url_ia TEXT,
      url_jstor TEXT, fetched_at TEXT, status TEXT);
    CREATE TABLE citations (id INTEGER PRIMARY KEY, article_id INTEGER, page INTEGER, work_id TEXT,
      locus_start TEXT, locus_end TEXT, open_ended INTEGER, surface TEXT, sentence TEXT, char_offset INTEGER);
    ''')
    c.execute("INSERT INTO articles (id, journal, title, authors, year, url_jstor) VALUES "
              "(1, 'Classical Philology', 'Mutiny in the Roman Army', 'Messer, William', 1920, 'https://j/1')")
    c.execute("INSERT INTO articles (id, journal, title, authors, year, url_jstor) VALUES "
              "(2, 'Classical Weekly', 'On the Second Passage', 'Doe, Jane', 1911, 'https://j/2')")
    C = ('INSERT INTO citations (article_id, page, work_id, locus_start, locus_end, open_ended, surface, sentence) '
         'VALUES (?,?,?,?,?,0,?,?)')
    c.execute(C, (1, 158, 'caesar.de_bello_civili', '1.17.2', None, 'Caes. Bel. Civ. i. 17', 'See Caes. Bel. Civ. i. 17.'))
    c.execute(C, (1, 160, 'caesar.de_bello_civili', '1.21.1', None, 'Caes. Bel. Civ. i. 21', 'And Caes. Bel. Civ. i. 21.'))
    c.execute(C, (2, 12, 'caesar.de_bello_civili', '1.21.1', None, 'Caes. Bel. Civ. i. 21', 'Also Caes. Bel. Civ. i. 21.'))
    c.execute(C, (2, 14, 'caesar.de_bello_civili', '2.1.2', None, 'Caes. Bel. Civ. ii. 1', 'Rank 30 only: Caes. Bel. Civ. ii. 1.'))
    c.commit()
    c.close()


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp('evsum')
    src, idx, intros = str(d / 'in.sqlite'), str(d / 'citations.db'), str(d / 'intros.json')
    _build(src)
    _citation_index(idx)
    json.dump({'Q1': {'title': 'Siege of Corfinium', 'description': 'siege', 'paragraph': LONG},
               'Q99': {'title': 'Not in the database', 'paragraph': 'Ignored.'}}, open(intros, 'w'))
    mid, out = str(d / 'mid.sqlite'), str(d / 'out.sqlite')
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'add_summaries.py'), src, intros, mid],
                       capture_output=True, text=True, check=True, cwd=ROOT)
    s = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'relink_scholarship.py'), mid, out,
                        '--citation-index', idx], capture_output=True, text=True, check=True, cwd=ROOT)
    return {'src': src, 'mid': mid, 'out': out, 'summ_report': r.stdout, 'link_report': s.stdout}


def test_summary_cut_at_a_sentence_end():
    s = add_summaries.summarise(LONG)
    assert len(s) <= 600 and s.endswith('.') and s == ('The siege lasted a week. ' * 24).strip()
    assert add_summaries.summarise('Short one. Two.') == 'Short one. Two.'
    one = add_summaries.summarise('word ' * 300)
    assert len(one) <= 600 and one.endswith('…')
    # an initial or an abbreviation is not a sentence end
    text = 'Gaius J. Caesar crossed in c. 49 BC. ' + 'It was long. ' * 60
    assert add_summaries.summarise(text).startswith('Gaius J. Caesar crossed in c. 49 BC. It was long.')


def test_add_summaries_fills_only_events_with_an_intro(built):
    assert '1 of 3 events' in built['summ_report']
    c = sqlite3.connect(built['mid'])
    rows = {r[0]: r[1:] for r in c.execute(
        'SELECT id, summary, summary_source, summary_url, summary_licence, description FROM events')}
    assert rows['Q1'][1:4] == ('Wikipedia', 'https://en.wikipedia.org/wiki/Siege_of_Corfinium', 'CC BY-SA 4.0')
    assert rows['Q1'][0].startswith('The siege lasted a week.')
    for q in ('Q2', 'Q3'):
        assert rows[q][0] is None and rows[q][4]  # the Wikidata description stays
    # the input file is untouched
    cols = {r[1] for r in sqlite3.connect(built['src']).execute('PRAGMA table_info(events)')}
    assert 'summary' not in cols


def test_relink_scholarship_rows(built):
    c = sqlite3.connect(built['out'])
    rows = c.execute("SELECT title, passage_rank, passage_ref FROM scholarship WHERE kind='article' "
                     "AND event_id='Q1' ORDER BY passage_rank, title").fetchall()
    # rank 1 holds 1.17, rank 2 holds 1.21 (both articles), rank 30 is not a leading passage
    assert rows == [('Mutiny in the Roman Army', 1, 'caes. bel. civ. 1.16.2-1.18.5'),
                    ('Mutiny in the Roman Army', 2, 'caes. bel. civ. 1.20.1-1.22.1'),
                    ('On the Second Passage', 2, 'caes. bel. civ. 1.20.1-1.22.1')]
    page_ref = c.execute("SELECT page_ref FROM scholarship WHERE title='On the Second Passage'").fetchone()[0]
    assert page_ref == 'Doe, Jane Classical Weekly 1911, p. 12; cites Caes. Bel. Civ. i. 21'
    # the event whose passages cite nothing has no article rows, and the old article row is gone
    assert c.execute("SELECT COUNT(*) FROM scholarship WHERE event_id='Q3'").fetchone()[0] == 0
    assert c.execute("SELECT COUNT(*) FROM scholarship WHERE title='Old row'").fetchone()[0] == 0
    comm = c.execute("SELECT page_ref, passage_rank FROM scholarship WHERE kind='commentary' ORDER BY page_ref").fetchall()
    assert comm == [('caes. bel. civ. 1.21.2', 2), ('caes. bel. civ. 9.9.9', None)]
    assert 'before 3, after 5' in built['link_report']
    assert 'Q18001862' in built['link_report']


def test_relink_refuses_a_missing_index(built, tmp_path):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, 'relink_scholarship.py'), built['mid'],
                        str(tmp_path / 'x.sqlite'), '--citation-index', str(tmp_path / 'none.db')],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode != 0 and 'not found' in r.stderr


def _client(db, monkeypatch):
    monkeypatch.setenv('TESSERAE_EVENTS_DB', db)
    from backend.app import app
    app.config['TESTING'] = True
    return app.test_client()


def test_api_carries_summary_and_one_row_per_article(built, monkeypatch):
    cl = _client(built['out'], monkeypatch)
    d = cl.get('/api/events/Q1').get_json()
    ev = d['event']
    assert ev['summary'].startswith('The siege lasted') and ev['summary_source'] == 'Wikipedia'
    assert ev['summary_url'].endswith('/Siege_of_Corfinium') and ev['summary_licence'] == 'CC BY-SA 4.0'
    arts = [s for s in d['scholarship'] if s['kind'] == 'article']
    assert [(a['title'], a['passage_rank']) for a in arts] == [('Mutiny in the Roman Army', 1),
                                                               ('On the Second Passage', 2)]
    assert arts[0]['passage_ref'] == 'caes. bel. civ. 1.16.2-1.18.5'
    comm = [s for s in d['scholarship'] if s['kind'] == 'commentary']
    assert [c['passage_rank'] for c in comm] == [2, None]
    assert 'summary' not in cl.get('/api/events/Q2').get_json()['event']


def test_api_with_an_older_database(built, monkeypatch):
    """No summary columns and no passage columns: the route answers as before."""
    cl = _client(built['src'], monkeypatch)
    d = cl.get('/api/events/Q1').get_json()
    assert 'summary' not in d['event'] and d['event']['description'] == 'siege in 49 BC'
    assert len(d['scholarship']) == 3
    assert 'passage_rank' not in d['scholarship'][0]
