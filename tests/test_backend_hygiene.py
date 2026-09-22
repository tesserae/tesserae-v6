"""Three small correctness fixes from the September 2026 code review.

Each is the kind of thing that never appears as a failure: a connection that
leaks only when a row is malformed, a log line that goes where nobody looks,
an exception clause that catches more than it means to.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402


class TestTheSyntaxDatabaseIsAlwaysClosed:
    """backend/fusion.py's syntax loader closed its connection on three paths
    by hand and leaked it on any fourth. A row with unreadable JSON is the
    one that happens in life, because the syntax database is machine-built.
    """

    @staticmethod
    def _db(tmp_path, tokens='["arma"]'):
        path = tmp_path / 'syntax.db'
        db = sqlite3.connect(path)
        db.execute('CREATE TABLE texts (text_id INTEGER, filename TEXT)')
        db.execute('CREATE TABLE syntax (text_id INTEGER, ref TEXT, tokens TEXT, '
                   'lemmas TEXT, upos TEXT, heads TEXT, deprels TEXT, feats TEXT)')
        db.execute('INSERT INTO texts VALUES (1, ?)', ('vergil.aeneid.tess',))
        db.execute('INSERT INTO syntax VALUES (1, ?, ?, ?, ?, ?, ?, ?)',
                   ('verg. aen. 1.1', tokens, '["arma"]', '["NOUN"]', '[0]', '["root"]', '[]'))
        db.commit()
        db.close()
        return str(path)

    def _clear_cache(self):
        from backend import fusion
        fusion._SYNTAX_PARSE_CACHE.clear()

    def test_a_good_row_is_read(self, tmp_path):
        from backend import fusion
        self._clear_cache()
        parses = fusion._load_syntax_for_text(self._db(tmp_path), 'vergil.aeneid.tess')
        assert parses['verg. aen. 1.1']['tokens'] == ['arma']

    def test_a_row_with_unreadable_json_does_not_leak_the_connection(self, tmp_path, monkeypatch):
        from backend import fusion
        self._clear_cache()
        opened = []

        real_connect = sqlite3.connect

        def tracking_connect(*a, **k):
            conn = real_connect(*a, **k)
            opened.append(conn)
            return conn

        monkeypatch.setattr(fusion.sqlite3, 'connect', tracking_connect)
        path = self._db(tmp_path, tokens='{not json')
        with pytest.raises(Exception):
            fusion._load_syntax_for_text(path, 'vergil.aeneid.tess')
        assert opened, 'the test did not observe a connection'
        for conn in opened:
            with pytest.raises(sqlite3.ProgrammingError):
                conn.execute('SELECT 1')      # raises only if it is closed

    def test_a_missing_text_closes_too(self, tmp_path, monkeypatch):
        from backend import fusion
        self._clear_cache()
        opened = []
        real_connect = sqlite3.connect
        monkeypatch.setattr(fusion.sqlite3, 'connect',
                            lambda *a, **k: opened.append(real_connect(*a, **k)) or opened[-1])
        assert fusion._load_syntax_for_text(self._db(tmp_path), 'nobody.nothing.tess') == {}
        for conn in opened:
            with pytest.raises(sqlite3.ProgrammingError):
                conn.execute('SELECT 1')


class TestLoginFailuresReachTheLog:
    def test_the_auth_module_has_a_logger_and_no_prints(self):
        """Under Apache and mod_wsgi a print does not reliably reach the
        application log, so a run of failed logins went unseen."""
        import inspect
        import re

        from backend import replit_auth
        source = inspect.getsource(replit_auth)
        assert 'logger' in source
        # A word boundary, because "blueprint(" contains "print(" and the
        # module is full of blueprints. The first version of this test failed
        # on make_replit_blueprint().
        calls = re.findall(r'(?<![\w.])print\s*\(', source)
        assert calls == [], 'a print is back in the authentication path'


class TestNoBareExceptionClauses:
    def test_none_left_in_the_backend(self):
        """A bare `except:` also swallows KeyboardInterrupt and SystemExit,
        so a worker being shut down mid-request answers politely instead of
        stopping."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent / 'backend'
        offenders = []
        for path in root.rglob('*.py'):
            for number, line in enumerate(path.read_text(encoding='utf-8',
                                                         errors='replace').splitlines(), 1):
                if line.strip() == 'except:':
                    offenders.append(f'{path.relative_to(root)}:{number}')
        assert offenders == [], offenders
