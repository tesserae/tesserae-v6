"""The precomputed lemma_doc_freq fast path must return exactly what the live
COUNT(DISTINCT) fallback returns — including part->base-work collapse and u/v
variant summing."""
import sqlite3
import pytest
import backend.blueprints.hapax as hx


def _make_index():
    """Tiny in-memory index: an Aeneid (whole + one part), Bellum Civile, Metamorphoses."""
    conn = sqlite3.connect(':memory:')
    conn.executescript(
        """
        CREATE TABLE texts (text_id INTEGER PRIMARY KEY, filename TEXT UNIQUE);
        CREATE TABLE postings (lemma TEXT, text_id INTEGER, ref TEXT, positions TEXT);
        INSERT INTO texts VALUES
            (1,'vergil.aeneid.tess'),
            (2,'vergil.aeneid.part.1.tess'),
            (3,'lucan.bellum_civile.tess'),
            (4,'ovid.metamorphoses.tess');
        -- 'arma' in Aeneid (whole+part, collapses to 1 work) and Bellum Civile -> df 2
        INSERT INTO postings VALUES ('arma',1,'1.1','[]'),('arma',2,'1.1','[]'),('arma',3,'1.1','[]');
        -- 'rara' only in Metamorphoses -> df 1
        INSERT INTO postings VALUES ('rara',4,'1.1','[]');
        -- 'uirtus' (u-form, as index stores it) in Aeneid and Metamorphoses -> df 2
        INSERT INTO postings VALUES ('uirtus',1,'1.1','[]'),('uirtus',4,'1.1','[]');
        """
    )
    conn.commit()
    return conn


def _add_precomputed(conn):
    base = ("CASE WHEN instr(t.filename,'.part.')>0 "
            "THEN substr(t.filename,1,instr(t.filename,'.part.')-1)||'.tess' "
            "ELSE t.filename END")
    conn.execute('CREATE TABLE lemma_doc_freq (lemma TEXT PRIMARY KEY, df INTEGER)')
    conn.execute(
        f'INSERT INTO lemma_doc_freq (lemma, df) '
        f'SELECT p.lemma, COUNT(DISTINCT {base}) '
        f'FROM postings p JOIN texts t ON p.text_id=t.text_id GROUP BY p.lemma')
    conn.commit()


def _run(monkeypatch, conn):
    monkeypatch.setattr(hx, 'get_connection', lambda language: conn)
    hx._lemma_doc_freq_available = {}  # reset memoization
    # query 'virtus' too: v-variant of stored 'uirtus', must sum to the same df
    return hx.get_document_frequencies_batch({'arma', 'rara', 'virtus'}, 'la')


def test_fallback_values(monkeypatch):
    conn = _make_index()  # no lemma_doc_freq table -> fallback path
    out = _run(monkeypatch, conn)
    assert out == {'arma': 2, 'rara': 1, 'virtus': 2}


def test_fast_path_matches_fallback(monkeypatch):
    conn = _make_index()
    _add_precomputed(conn)  # now the fast path is used
    hx._lemma_doc_freq_available = {}  # fresh check (new process/connection would too)
    assert hx._has_lemma_doc_freq(conn, 'la') is True
    out = _run(monkeypatch, conn)
    assert out == {'arma': 2, 'rara': 1, 'virtus': 2}
