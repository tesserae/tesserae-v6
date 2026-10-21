"""scripts/events/add_naming_documents.py and the two-index run of
scripts/events/relink_scholarship.py, on small fixture stores."""
import os
import sqlite3
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts', 'events'))

import add_naming_documents as A  # noqa: E402
import relink_scholarship as R  # noqa: E402

DOC_COLS = '(event_id TEXT, doc_id TEXT, date_start INTEGER, date_end INTEGER, place TEXT, distance_km REAL, ' \
           'text_snippet TEXT, language TEXT, lat REAL, lon REAL)'


@pytest.fixture
def stores(tmp_path):
    ev = tmp_path / 'events.sqlite'
    c = sqlite3.connect(ev)
    c.execute('CREATE TABLE events (id TEXT, label TEXT, date_start INTEGER, date_end INTEGER, place TEXT, '
              'lat REAL, lon REAL, participants TEXT)')
    c.execute(f'CREATE TABLE documents {DOC_COLS}')
    c.execute('CREATE TABLE passages (event_id TEXT, rank INTEGER, work TEXT, ref_start TEXT, ref_end TEXT, llm_label TEXT)')
    c.execute('CREATE TABLE scholarship (event_id TEXT, kind TEXT, title TEXT, page_ref TEXT, url TEXT)')
    c.execute("INSERT INTO events VALUES ('E1','With coords',-415,-413,'Sicily',37.5,14.0,'[\"Gylippus\"]')")
    c.execute("INSERT INTO events VALUES ('E2','No coords',-415,-413,'Sicily',NULL,NULL,'[]')")
    c.execute("INSERT INTO events VALUES ('E3','Nothing resolves',-415,-413,'Nowhere',NULL,NULL,'[]')")
    c.execute("INSERT INTO documents VALUES ('E1','d_old',-420,-410,'X',1.0,'x','grc',37.0,14.0)")
    c.commit()
    c.close()
    ent = tmp_path / 'entities.sqlite'
    c = sqlite3.connect(ent)
    c.execute('CREATE TABLE document_mentions (eid INTEGER, doc_id TEXT, language TEXT, form TEXT, kind TEXT, adjective INTEGER)')
    rows = [(1, 'd_old'), (1, 'd_in'), (1, 'd_edge'), (1, 'd_far'), (1, 'd_undated'), (1, 'd_nopt'), (2, 'd_in')]
    rows += [(1, f'd_bulk{i:02d}') for i in range(60)]
    c.executemany("INSERT INTO document_mentions VALUES (?,?,'grc','f','form',0)", rows)
    c.commit()
    c.close()
    meta = tmp_path / 'metadata.db'
    c = sqlite3.connect(meta)
    c.execute('CREATE TABLE documents (id TEXT, date_not_before INTEGER, date_not_after INTEGER, ancient_place TEXT, '
              'pleiades_id TEXT, text_type_label TEXT, object_type_label TEXT, principal_edition TEXT)')
    docs = [('d_old', -420, -410, 'X', '1'), ('d_in', -430, -400, 'Syracuse', '2'), ('d_edge', -365, -360, 'Gela', '3'),
            ('d_far', 100, 200, 'Rome', '4'), ('d_undated', None, None, 'Motya', '3'), ('d_nopt', -415, -415, 'Z', None)]
    docs += [(f'd_bulk{i:02d}', -415, -413, 'B', '2') for i in range(60)]
    c.executemany("INSERT INTO documents VALUES (?,?,?,?,?,'dedication','plaque','IG 1')", docs)
    c.commit()
    c.close()
    pts = tmp_path / 'points.tsv'
    pts.write_text('pleiades_id\tlat\tlon\ttitle\n1\t37.0\t14.0\ta\n2\t37.5\t14.5\tb\n3\t38.0\t15.0\tc\n4\t41.9\t12.5\td\n')
    return dict(ev=str(ev), ent=str(ent), meta=str(meta), pts=str(pts), tmp=tmp_path)


def resolver(name):
    return {'Gylippus': 2, 'Sicily': 1}.get(name)


def plan(s, cap=50):
    return A.add_naming_documents(s['ev'], str(s['tmp'] / 'out.sqlite'), s['ent'], s['meta'], s['pts'],
                                  cap, False, resolve=resolver, log=lambda *a: None)


def test_dating_window_dedupe_and_order(stores):
    p = plan(stores, cap=100)
    ids = [r[1] for r in p['E1']]
    assert 'd_old' not in ids                     # already in the event's documents
    assert 'd_far' not in ids                     # outside the years widened by 50
    assert 'd_edge' in ids                        # dated -365 to -360, overlaps -465 to -363
    assert 'd_undated' in ids                     # no dating at all is kept
    assert ids.count('d_in') == 1                 # named by two entities, one row


def test_window_is_fifty_years_each_side():
    assert A.overlaps(-364, -360, -465, -363)
    assert not A.overlaps(-362, -360, -465, -364)
    assert A.overlaps(None, None, 0, 1)
    assert A.overlaps(-415, None, -465, -363)


def test_cap_and_nearest_first(stores):
    p = plan(stores, cap=5)
    rows = p['E1']
    assert len(rows) == 5
    d = [r[5] for r in rows]
    assert d == sorted(d)


def test_distance_with_and_without_event_coordinates(stores):
    p = plan(stores, cap=100)
    with_c = {r[1]: r for r in p['E1']}
    assert with_c['d_in'][5] is not None and 40 < with_c['d_in'][5] < 50   # (37.5,14.0) to (37.5,14.5), about 44 km
    assert with_c['d_in'][8:] == (37.5, 14.5)
    assert with_c['d_nopt'][5] is None and with_c['d_nopt'][8] is None    # no Pleiades point
    assert all(r[5] is None for r in p['E2'])                            # event without coordinates
    assert {r[1] for r in p['E2']} >= {'d_in'} and p['E2'][0][8] is not None
    assert 'E3' not in p


def test_apply_writes_output_and_leaves_input(stores):
    before = open(stores['ev'], 'rb').read()
    out = str(stores['tmp'] / 'out.sqlite')
    A.add_naming_documents(stores['ev'], out, stores['ent'], stores['meta'], stores['pts'], 50, True,
                           resolve=resolver, log=lambda *a: None)
    assert open(stores['ev'], 'rb').read() == before
    c = sqlite3.connect(out)
    assert c.execute("SELECT COUNT(*) FROM documents WHERE event_id = 'E1'").fetchone()[0] == 51
    row = c.execute("SELECT * FROM documents WHERE doc_id = 'd_bulk00' AND event_id = 'E1'").fetchone()
    assert row[4] == 'B' and row[6] == 'dedication / plaque; IG 1' and row[7] == 'grc'


def test_undated_last_orders_dated_first(stores):
    p = A.add_naming_documents(stores['ev'], str(stores['tmp'] / 'o2.sqlite'), stores['ent'], stores['meta'],
                               stores['pts'], 100, False, resolve=resolver, log=lambda *a: None, undated='last')
    assert p['E1'][-1][1] == 'd_undated'
    p = A.add_naming_documents(stores['ev'], str(stores['tmp'] / 'o3.sqlite'), stores['ent'], stores['meta'],
                               stores['pts'], 100, False, resolve=resolver, log=lambda *a: None, undated='drop')
    assert 'd_undated' not in [r[1] for r in p['E1']]


def test_only_prefix_keeps_one_collection(stores):
    p = A.add_naming_documents(stores['ev'], str(stores['tmp'] / 'o4.sqlite'), stores['ent'], stores['meta'], stores['pts'],
                               100, False, resolve=resolver, log=lambda *a: None, only_prefix='d_bulk')
    assert p['E1'] and all(r[1].startswith('d_bulk') for r in p['E1'])
    assert all(r[1].startswith('d_bulk') for r in p['E2'])      # d_in is named too and is left out


def test_dry_run_writes_nothing(stores):
    plan(stores)
    assert not (stores['tmp'] / 'out.sqlite').exists()


def test_scholarship_reads_both_indexes_and_counts_each(stores, monkeypatch, capsys):
    from backend import scholarship as S
    c = sqlite3.connect(stores['ev'])
    c.execute("INSERT INTO passages VALUES ('E1', 1, 'thucydides.history', '7.1', '7.5', 'yes')")
    c.commit()
    c.close()
    ejc = stores['tmp'] / 'citations.db'
    ejc.write_bytes(b'')
    muse = stores['tmp'] / 'citations_muse.db'
    muse.write_bytes(b'')
    seen = {}

    def fake_names(work, a, b=None):
        return {'work': work}

    def fake_index(a, limit=40):
        seen['extra'] = os.environ.get(S.CITATIONS_EXTRA_ENV)
        return {'results': [
            {'title': 'EJC article', 'url': 'u1', 'authors': ['A'], 'year': 1900, 'source': 'citation_index'},
            {'title': 'MUSE article', 'url': 'u2', 'authors': ['B'], 'year': 2001, 'source': 'muse'},
            {'title': 'MUSE two', 'url': 'u3', 'authors': ['C'], 'year': 2002, 'source': 'muse'}]}

    monkeypatch.setattr(S, 'passage_names', fake_names)
    monkeypatch.setattr(S, 'citation_index', fake_index)
    monkeypatch.delenv(S.CITATIONS_EXTRA_ENV, raising=False)
    out = str(stores['tmp'] / 'rel.sqlite')
    R.main([stores['ev'], out, '--citation-index', str(ejc)])      # the MUSE file beside it is found
    text = capsys.readouterr().out
    assert seen['extra'] == str(muse)
    assert 'ejc passage: 1 distinct articles, 1 rows' in text and 'muse passage: 2 distinct articles, 2 rows' in text
    assert 'events with any scholarship row: 1 of 3' in text
    R.main([stores['ev'], out, '--citation-index', str(ejc), '--extra-index', ''])
    assert seen['extra'] is None


def test_span_of_is_per_book_and_ignores_stray_passages():
    def P(work, a, b):
        return dict(work=work, ref_start=a, ref_end=b)
    ps = [P('w.a', 'thuc. 6.30', 'thuc. 6.32'), P('w.a', 'thuc. 7.10', 'thuc. 7.12'), P('w.a', 'thuc. 6.5', 'thuc. 6.6'),
          P('w.a', 'thuc. 7.80', 'thuc. 7.85'), P('w.a', 'thuc. 4.64', 'thuc. 4.65'), P('w.a', 'thuc. 8.47', 'thuc. 8.48'),
          P('w.b', 'plut. 12.1', 'plut. 12.3'), P('w.c', 'plut. 12', 'plut. 13'), P('w.c', 'plut. 30', 'plut. 30')]
    got = sorted(R.span_of(ps))
    assert got == [('w.a', 'thuc. 6.5', 'thuc. 6.32'), ('w.a', 'thuc. 7.10', 'thuc. 7.85'), ('w.c', 'plut. 12', 'plut. 30')]


def test_scholarship_span_group_follows_and_is_not_repeated(stores, monkeypatch, capsys):
    from backend import scholarship as S
    c = sqlite3.connect(stores['ev'])
    c.executemany("INSERT INTO passages VALUES ('E1', ?, 'thucydides.history', ?, ?, 'yes')",
                  [(1, 'thuc. 6.30', 'thuc. 6.32'), (2, 'thuc. 6.50', 'thuc. 6.52'), (3, 'thuc. 4.10', 'thuc. 4.11')])
    c.commit()
    c.close()
    ejc = stores['tmp'] / 'citations.db'
    ejc.write_bytes(b'')
    asked = []

    def fake_names(work, a, b=None):
        return {'work': work, 'lo': a, 'hi': b}

    def fake_index(a, limit=40):
        asked.append((a['lo'], a['hi']))
        wide = a['lo'] == 'thuc. 6.30' and a['hi'] == 'thuc. 6.52'
        res = [{'title': 'Same', 'url': 'u1', 'source': 'citation_index'}]
        if wide:
            res.append({'title': 'Elsewhere', 'url': 'u9', 'source': 'citation_index'})
        return {'results': res}

    monkeypatch.setattr(S, 'passage_names', fake_names)
    monkeypatch.setattr(S, 'citation_index', fake_index)
    out = str(stores['tmp'] / 'rel2.sqlite')
    R.main([stores['ev'], out, '--citation-index', str(ejc), '--extra-index', ''])
    rows = sqlite3.connect(out).execute(
        "SELECT title, passage_rank, passage_ref, scope FROM scholarship WHERE event_id = 'E1' ORDER BY rowid").fetchall()
    assert [r for r in rows if r[3] == 'span'] == [('Elsewhere', None, 'thuc. 6.30-6.52', 'span')]
    assert sum(1 for r in rows if r[0] == 'Same') == 3          # once per leading passage, never again in the span group
    assert 'ejc span: 1 distinct articles, 1 rows' in capsys.readouterr().out
