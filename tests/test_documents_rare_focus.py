"""rare_focus applies to collection='documents' (the Reader's Inscriptions and
papyri section): a document sharing only commonplaces is hidden and counted.

Runs on a fixture, so it needs neither the documents index nor the literary one:
the document search and the document-frequency table are replaced by small stand-ins.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.app  # noqa: E402,F401  (the application must be built first)
import backend.documents as docs  # noqa: E402
import backend.lexical_density as ld  # noqa: E402
from backend.app import app, rare_focus_filter  # noqa: E402
from backend.blueprints import documents as D  # noqa: E402
from backend.blueprints import line_search as L  # noqa: E402

DF = {'top': 767, 'quis': 699, 'uarius': 481, 'adfatibus': 4}


def _fixture(monkeypatch, tmp_path):
    db = tmp_path / 'df.db'
    conn = sqlite3.connect(db)
    conn.execute('CREATE TABLE lemma_doc_freq (lemma TEXT PRIMARY KEY, df INT)')
    conn.executemany('INSERT INTO lemma_doc_freq VALUES (?, ?)', DF.items())
    conn.commit()
    conn.close()
    monkeypatch.setattr(ld, '_index_path', lambda lang: str(db))
    rows = [
        {'doc_id': 'edr:A', 'matched_lemmas': ['quis', 'uarius'], 'matched_words': ['quis', 'varii']},
        {'doc_id': 'edr:B', 'matched_lemmas': ['quis', 'adfatibus'], 'matched_words': ['quis', 'adfatibus']},
    ]
    monkeypatch.setattr(D, '_search_documents_collection',
                        lambda *a, **k: (list(rows), 2, [], [], {
                            'restored_excluded_count': 0, 'formulas_hidden_count': 0,
                            'formula_summary': None}))
    monkeypatch.setattr(D, '_lemmatize_query_simple', lambda q, lang, tp: {'quis', 'uarius', 'adfatibus'})
    monkeypatch.setattr(docs, 'get_corpus_version', lambda lang: 'test')


def _call(**extra):
    with app.test_request_context():
        resp = D._line_search_documents_only(
            'quis uarius adfatibus', 'la', 'lemma', 0, 20, 'relevance', False,
            None, None, None, None, None, None, 0.0, **extra)
        return resp.get_json()


def test_commonplace_only_document_is_hidden_and_counted(monkeypatch, tmp_path):
    _fixture(monkeypatch, tmp_path)
    d = _call(rare_focus_filter=rare_focus_filter)
    assert [r['doc_id'] for r in d['results']] == ['edr:B']
    assert d['rare_focus'] == {'hidden': 1, 'common_lemmas': ['quis', 'uarius']}


def test_without_rare_focus_nothing_is_hidden(monkeypatch, tmp_path):
    _fixture(monkeypatch, tmp_path)
    d = _call()
    assert [r['doc_id'] for r in d['results']] == ['edr:A', 'edr:B']
    assert 'rare_focus' not in d


def test_documents_only_passes_the_filter_only_when_asked(monkeypatch):
    seen = {}
    monkeypatch.setattr(L, '_line_search_documents_only', lambda *a, **k: seen.update(k) or 'ok')
    for flag, expect in ((True, L.rare_focus_filter), (False, None)):
        with app.test_request_context():
            params = L._read_params({'query': 'x y', 'language': 'la', 'search_type': 'lemma',
                                     'collection': 'documents', 'rare_focus': flag})
            params.documents_active = True
            assert L._documents_only(params, 0.0) == 'ok'
        assert seen['rare_focus_filter'] is expect
