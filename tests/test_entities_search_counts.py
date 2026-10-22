"""A place named only by its adjective, or only in documents, does not read as empty in the search list."""
from backend.blueprints import entities


def test_adjective_lines_and_documents_join_the_row(monkeypatch):
    monkeypatch.setattr(entities, '_document_counts', lambda path, e: {'la': 6})
    e = {'id': 'pl:413288', 'label': 'Rusellae', 'type': 'place', 'source': 'list', 'pleiades': ['413288'],
         'merged_ids': [], 'counts': {}, 'total': 0, 'shared_label_with': [], 'homonym_mentions': 0,
         'corpus_names': [{'id': 'nm:rusel', 'adjective': True, 'mentions_total': 3},
                          {'id': 'nm:other', 'adjective': False, 'mentions_total': 9}]}
    row = entities._with_more_counts('x', {'has_documents_table': True}, e)
    assert row['adjective_lines'] == 3 and row['document_counts'] == {'la': 6} and row['mentions_total'] == 0


def test_a_corpus_name_gets_no_document_lookup(monkeypatch):
    monkeypatch.setattr(entities, '_document_counts', lambda path, e: (_ for _ in ()).throw(AssertionError('called')))
    e = {'id': 'nm:rusel', 'label': 'Rusellanum', 'type': 'name', 'source': 'corpus', 'pleiades': [],
         'merged_ids': [], 'counts': {'la': 3}, 'total': 3, 'shared_label_with': [], 'homonym_mentions': 0}
    row = entities._with_more_counts('x', {'has_documents_table': True}, e)
    assert 'document_counts' not in row and 'adjective_lines' not in row
