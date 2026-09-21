"""The reference search, as a test rather than a checklist.

`tests/search_reference_tests.md` says a search for "arma virum" must return
Ovid, Quintilian and Seneca, and that a search which drops them is broken.
It has been a manual list since it was written, which is the same shape of
gap that let the quotation channel sit dead in production for eleven weeks:
the check existed and nothing ran it.

The real check needs the corpus and a 2 GB index, which continuous
integration does not have, so this builds a miniature index in the shape of
the real one and runs the actual lookup code over it. It cannot tell you
that recall across 1,800 Latin works is still 367 lines. It tells you that
the machinery which produces that number is wired up: that two lemmas are
found co-occurring in one line, across several authors, that a line holding
only one of them is not returned, and that the distance limit and the
dedupliction between a whole work and its parts still work.

`scripts/reference_search_check.py` beside this file is the other half: it
runs the real query against a running site and is what a deploy should use.
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend import inverted_index  # noqa: E402

# Four lines in the shape the real index stores them. Three hold both lemmas
# of the reference query; the fourth holds only one and must not come back.
CORPUS = [
    # (filename, author, title, ref, content, lemmas)
    ('vergil.aeneid.part.1.tess', 'vergil', 'aeneid', 'verg. aen. 1.1',
     'Arma virumque cano Troiae qui primus ab oris', ['arma', 'uir', 'cano']),
    ('ovid.metamorphoses.tess', 'ovid', 'metamorphoses', 'ov. met. 14.573',
     'arma ferunt contra uirumque', ['arma', 'fero', 'uir']),
    ('quintilian.institutio_oratoria.tess', 'quintilian', 'institutio', 'quint. inst. 8.3.24',
     'arma uirumque cano principium', ['arma', 'uir', 'cano']),
    ('seneca.epistulae.tess', 'seneca', 'epistulae', 'sen. ep. 1.1',
     'arma tantum sine uiro', ['arma']),
]


@pytest.fixture
def index(tmp_path, monkeypatch):
    """A miniature index with the real schema, in place of the corpus."""
    db_path = tmp_path / 'la_index.db'
    db = sqlite3.connect(db_path)
    db.execute('CREATE TABLE texts (text_id INTEGER PRIMARY KEY, filename TEXT UNIQUE, '
               'author TEXT, title TEXT, line_count INTEGER)')
    db.execute('CREATE TABLE postings (lemma TEXT, text_id INTEGER, ref TEXT, positions TEXT)')
    db.execute('CREATE TABLE lines (text_id INTEGER, ref TEXT, content TEXT, lemmas TEXT, tokens TEXT)')
    db.execute('CREATE TABLE lemma_doc_freq (lemma TEXT PRIMARY KEY, df INTEGER)')
    db.execute('CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)')
    for i, (filename, author, title, ref, content, lemmas) in enumerate(CORPUS, start=1):
        db.execute('INSERT INTO texts VALUES (?,?,?,?,?)', (i, filename, author, title, 1))
        db.execute('INSERT INTO lines VALUES (?,?,?,?,?)',
                   (i, ref, content, json.dumps(lemmas), json.dumps(content.split())))
        for pos, lemma in enumerate(lemmas):
            db.execute('INSERT INTO postings VALUES (?,?,?,?)', (lemma, i, ref, json.dumps([pos])))
    for lemma in ('arma', 'uir', 'cano', 'fero'):
        db.execute('INSERT INTO lemma_doc_freq VALUES (?,?)', (lemma, 2))
    db.commit()
    db.close()
    monkeypatch.setattr(inverted_index, 'INDEX_DIR', str(tmp_path))
    monkeypatch.setattr(inverted_index, '_connections', {}, raising=False)
    return tmp_path


def _authors(results):
    return sorted({filename.split('.')[0] for filename, _ref, _lemmas, _pos in results})


class TestTheReferenceQuery:
    def test_two_lemmas_co_occurring_are_found(self, index):
        hits = inverted_index.find_co_occurring_lemmas(['arma', 'uir'], 'la', min_matches=2)
        assert len(hits) == 3

    def test_it_spans_several_authors(self, index):
        """The checklist's own red flag is "only one author represented"."""
        hits = inverted_index.find_co_occurring_lemmas(['arma', 'uir'], 'la', min_matches=2)
        assert _authors(hits) == ['ovid', 'quintilian', 'vergil']

    def test_a_line_with_only_one_of_the_two_is_not_a_hit(self, index):
        hits = inverted_index.find_co_occurring_lemmas(['arma', 'uir'], 'la', min_matches=2)
        assert 'seneca.epistulae.tess' not in {f for f, _, _, _ in hits}

    def test_one_lemma_alone_still_finds_every_line_holding_it(self, index):
        hits = inverted_index.find_co_occurring_lemmas(['arma'], 'la', min_matches=1)
        assert len(hits) == 4

    def test_the_distance_limit_drops_a_far_apart_pair(self, index):
        near = inverted_index.find_co_occurring_lemmas(['arma', 'cano'], 'la', min_matches=2,
                                                       max_distance=5)
        far = inverted_index.find_co_occurring_lemmas(['arma', 'cano'], 'la', min_matches=2,
                                                      max_distance=1)
        assert len(near) == 2
        assert far == []

    def test_a_lemma_nothing_holds_returns_nothing(self, index):
        assert inverted_index.find_co_occurring_lemmas(['nusquam'], 'la', min_matches=1) == []
