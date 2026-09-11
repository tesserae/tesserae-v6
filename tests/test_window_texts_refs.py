"""passage_lines accepts a cleaned reference for a work whose stored tags are
malformed (Sallust: "sal.  Cat..58.15"), since that is the form the connector
now shows and an agent hands straight back."""
import sqlite3

import pytest

from backend import window_texts as W


@pytest.fixture
def db(monkeypatch):
    c = sqlite3.connect(':memory:', check_same_thread=False)
    c.execute('CREATE TABLE lines (work TEXT, ord INTEGER, ref TEXT, text TEXT)')
    c.executemany('INSERT INTO lines VALUES (?,?,?,?)', [
        ('sallust.catilina', 0, 'sal.  Cat..58.14', 'a'),
        ('sallust.catilina', 1, 'sal.  Cat..58.15', 'b'),
        ('sallust.catilina', 2, 'sal.  Cat..58.16', 'c'),
    ])
    monkeypatch.setattr(W, '_conn', lambda: c)
    return c


def test_passage_lines_accepts_cleaned_ref(db):
    out = W.passage_lines('sallust.catilina', 'sal. Cat. 58.15', 'sal. Cat. 58.16')
    assert [l['text'] for l in out['lines']] == ['b', 'c']


def test_passage_lines_still_accepts_raw_ref(db):
    out = W.passage_lines('sallust.catilina', 'sal.  Cat..58.14')
    assert [l['text'] for l in out['lines']] == ['a']


def test_passage_lines_unknown_ref_is_an_error(db):
    out = W.passage_lines('sallust.catilina', 'sal. Cat. 99.1')
    assert 'not found' in out['error']
