"""Install an in-memory list of window records as the passage index's per-row state.

The index keeps descriptions on disk and per-row facts in numpy arrays
(backend/passage_index.py). Tests that used to set the list of records now call
install_records(monkeypatch, pi, records), which fills the arrays from the list and
makes pi._record(i) read the list.
"""


def install_records(monkeypatch, pi, records):
    if records is None:
        tables = {'_work_ix': None, '_lang_ix': None, '_scale_ix': None,
                  '_has_gist': None, '_has_desc': None, '_offsets': None,
                  '_work_names': [], '_lang_names': [], '_scale_names': [],
                  '_work_lookup': {}}
    else:
        tables = pi._tables_from_records(records)
    for name, value in tables.items():
        monkeypatch.setattr(pi, name, value)
    monkeypatch.setattr(pi, '_mem_records', records)
    # The window ids are the records' ids (ids.json lines up with the records).
    monkeypatch.setattr(pi, '_ids', None if records is None else [r.get('id') for r in records])
