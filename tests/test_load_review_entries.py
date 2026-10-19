"""Loader for judged Greek-Latin pairs into the dictionary_review table (2026-10-19).
Uses a fake connection, no PostgreSQL."""
import importlib.util
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)
_spec = importlib.util.spec_from_file_location(
    'load_review_entries', os.path.join(ROOT, 'scripts', 'dictionary', 'load_review_entries.py'))
lre = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lre)

from backend.synonym_dict import _normalize_greek  # noqa: E402


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 0
        self._row = None

    def execute(self, sql, params=None):
        self.conn.statements.append((sql, params))
        if sql.startswith('INSERT'):
            key = (params[0], params[1], params[2])
            if key not in self.conn.rows:
                self.conn.rows[key] = params
                self.rowcount = 1
            else:
                self.rowcount = 0
        elif sql.startswith('DELETE'):
            gone = [k for k in self.conn.rows if k[2] == params[0]]
            for k in gone:
                del self.conn.rows[k]
            self.rowcount = len(gone)
        elif 'WHERE source' in sql:
            self._row = (sum(1 for k in self.conn.rows if k[2] == params[0]),)
        elif "status = 'accepted'" in sql:
            self._row = (len(self.conn.rows),)

    def fetchone(self):
        return self._row


class FakeConn:
    def __init__(self):
        self.statements = []
        self.rows = {}
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def write(path, text):
    path.write_text(text, encoding='utf-8')
    return str(path)


@pytest.fixture
def files(tmp_path):
    main = write(tmp_path / 'a.csv',
                 'greek_lemma,latin_lemma,extra\n'
                 'αβασ,abas,x\nαβατοσ,inaccessibilis,y\nαβασ,abas,dup\nτρισ,ter,z\nλογοσ,verbum,w\n')
    excl = write(tmp_path / 'ex.csv', 'greek_lemma,latin_lemma\nαβατοσ,inaccessibilis\n')
    judged = write(tmp_path / 'j.csv',
                   'greek_lemma,latin_lemma,verdict_qwen,reason_qwen,verdict_gptoss,reason_gptoss\n'
                   'αβασ,abas,ACCEPT,a name,ACCEPT,' + ('long ' * 200) + '\n')
    return main, excl, judged


def test_csv_reading_ignores_extra_columns_and_drops_duplicates(files):
    rows, dups = lre.read_pairs(files[0])
    assert dups == 1
    assert rows[0] == ('αβασ', 'abas') and len(rows) == 4


def test_form_round_trip_matches_app_key():
    for form in ['Ἄβας', 'τρίς', 'μάκαρ', 'λόγος', 'ἀβάτος', 'πᾶς']:
        app_key = _normalize_greek(form).replace('ς', 'σ')
        assert lre.normalize_greek(form) == app_key
        assert lre.normalize_greek(app_key) == app_key
    assert lre.normalize_greek('αβας') == 'αβασ'


def test_exclusion_and_curated_skip(files):
    rows, _ = lre.read_pairs(files[0])
    curated = {'τρισ': ['ter', 'terque']}
    to_insert, excluded, already = lre.plan(rows, lre.read_exclusions(files[1]), curated)
    assert excluded == 1 and already == 1
    assert [p[0] for p in to_insert] == ['αβασ', 'λογοσ']


def test_curated_match_treats_v_as_u():
    assert lre.in_curated({'λογοσ': ['verbum']}, 'λογοσ', 'uerbum')


def test_notes_building_and_cut(files):
    notes = lre.build_notes(files[2])
    note = notes[('αβασ', 'abas')]
    assert note.startswith('qwen: accept, a name | gpt-oss: accept, long')
    assert len(note) == 500


def test_apply_uses_conflict_clause_and_one_transaction(files):
    conn = FakeConn()
    rows, _ = lre.read_pairs(files[0])
    notes = lre.build_notes(files[2])
    inserted, skipped, before, after = lre.apply_load(conn, rows, 'src', notes, 'accepted', batch_size=2)
    assert (inserted, skipped, before, after) == (4, 0, 0, 4)
    assert conn.commits == 1 and conn.rollbacks == 0
    inserts = [s for s in conn.statements if s[0].startswith('INSERT')]
    assert all('ON CONFLICT (greek_lemma, latin_lemma, source) DO NOTHING' in s[0] for s in inserts)
    assert inserts[0][1][3:5] == ('accepted', lre.REVIEWER)
    again = lre.apply_load(conn, rows, 'src', notes, 'accepted')
    assert again[0] == 0 and again[1] == 4


def test_failure_rolls_back():
    conn = FakeConn()
    conn.cursor = lambda: (_ for _ in ()).throw(RuntimeError('boom'))
    with pytest.raises(RuntimeError):
        lre.apply_load(conn, [('a', 'b')], 's', {}, 'accepted')


def test_dry_run_writes_nothing(files, monkeypatch, capsys):
    monkeypatch.setenv('DATABASE_URL', 'postgres://fake')
    def no_connect():
        raise AssertionError('dry run must not connect')
    rc = lre.main(['--csv', files[0], '--source', 's', '--exclude', files[1], '--notes-from', files[2]],
                  connect_fn=no_connect, curated={})
    out = capsys.readouterr().out
    assert rc == 0 and 'Dry run. Nothing written' in out and 'To insert under source s with status accepted: 3' in out


def test_apply_via_main_prints_counts(files, monkeypatch, capsys):
    monkeypatch.setenv('DATABASE_URL', 'postgres://fake')
    conn = FakeConn()
    lre.main(['--csv', files[0], '--source', 's', '--apply'], connect_fn=lambda: conn, curated={})
    out = capsys.readouterr().out
    assert 'Inserted: 4' in out and '0 before, 4 after' in out


def test_unload_statement_and_count():
    conn = FakeConn()
    lre.apply_load(conn, [('a', 'b'), ('c', 'd')], 'one', {}, 'accepted')
    lre.apply_load(conn, [('a', 'b')], 'two', {}, 'accepted')
    deleted, before, after = lre.unload(conn, 'one')
    assert (deleted, before, after) == (2, 3, 1)
    assert conn.statements[-2][0] == 'DELETE FROM dictionary_review WHERE source = %s'
    assert conn.statements[-2][1] == ('one',)


def test_refuses_without_database_url(files, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(SystemExit):
        lre.main(['--csv', files[0], '--source', 's'], curated={})
    with pytest.raises(SystemExit):
        lre.main(['--unload', 's', '--apply'])
