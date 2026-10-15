"""Tests for the speed changes to the inscriptions browser, the rare-word and
rare-pair searches, and the cached fusion read (2026-10-14).

Each change must leave every answer identical, so these compare the new code
with a plain re-statement of what the old code did, on small hand-made data.
No corpus, no network.
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backend.documents_browse as browse_mod
import backend.blueprints.hapax as hapax
from backend import result_view_cache


# ---------------------------------------------------------------------------
# result_view_cache
# ---------------------------------------------------------------------------

def test_result_view_cache_keeps_until_the_file_changes():
    result_view_cache.clear()
    result_view_cache.put('/x/a.json', ((10, 1),), 10, 'A')
    assert result_view_cache.get('/x/a.json', ((10, 1),)) == 'A'
    assert result_view_cache.get('/x/a.json', ((10, 2),)) is None   # rewritten
    assert result_view_cache.get('/x/b.json', ((10, 1),)) is None


def test_result_view_cache_is_capped_by_file_size(monkeypatch):
    result_view_cache.clear()
    monkeypatch.setattr(result_view_cache, 'MAX_TOTAL_BYTES', 100)
    assert not result_view_cache.put('/x/big.json', 1, 101, 'big')   # too large to keep
    assert result_view_cache.put('/x/1.json', 1, 60, 'one')
    assert result_view_cache.put('/x/2.json', 1, 60, 'two')           # evicts the oldest
    assert result_view_cache.get('/x/1.json', 1) is None
    assert result_view_cache.get('/x/2.json', 1) == 'two'
    result_view_cache.clear()


def test_result_view_cache_stamp_of_missing_file(tmp_path):
    f = tmp_path / 'f.json'
    f.write_text('{}')
    stamp = result_view_cache.stamp_of(str(f), str(tmp_path / 'absent'))
    assert stamp[0][0] == 2 and stamp[1] is None


# ---------------------------------------------------------------------------
# documents_browse: the facet view equals the old four-pass computation
# ---------------------------------------------------------------------------

def _records(n=400, seed=3):
    rnd = random.Random(seed)
    kinds = ['inscriptions', 'papyri']
    regions = ['Roma', 'Aegyptus', 'Dalmatia', 'Unknown nome']
    findspots = [None, 'Oxyrhynchos', 'Arsinoites']
    centuries = [('1st century AD', 100), ('2nd century AD', 200), ('1st century BC', -100), ('Undated', 10 ** 9)]
    types = [None, 'epitaph', 'letter', 'dedication']
    materials = [None, 'stone', 'papyrus']
    objects = [None, 'stele', 'altar']
    langs = [None, 'la', 'grc']
    out = []
    for i in range(n):
        c = rnd.choice(centuries)
        out.append(browse_mod.DocRecord(
            doc_id=f'd{i}', kind=rnd.choice(kinds), region=rnd.choice(regions),
            region_raw=None, findspot=rnd.choice(findspots), century_label=c[0],
            century_sort=c[1], date_label=None, text_type=rnd.choice(types),
            material=rnd.choice(materials), object_type=rnd.choice(objects),
            language=rnd.choice(langs), principal_edition=None))
    return out


def _old_view(records, kind, region, findspot, century, text_type, material, object_type, language):
    """The previous browse(): each flat facet counted over its own pool."""
    def matches(r, **f):
        for k, v in f.items():
            if v and getattr(r, k) != v:
                return False
        return True
    by_kind = [r for r in records if not kind or r.kind == kind]
    by_region = [r for r in by_kind if not region or r.region == region]
    by_findspot = [r for r in by_region if not findspot or r.findspot == findspot]
    matching = [r for r in by_findspot if not century or r.century_label == century]
    flt = dict(text_type=text_type, material=material, object_type=object_type, language=language)
    filtered = [r for r in matching if matches(r, **flt)]
    facets = {}
    for name, attr in (('text_types', 'text_type'), ('materials', 'material'),
                       ('objects', 'object_type'), ('languages', 'language')):
        pool = [r for r in matching if matches(r, **{k: (None if k == attr else v) for k, v in flt.items()})]
        counts = {}
        for r in pool:
            v = getattr(r, attr)
            if v:
                counts[v] = counts.get(v, 0) + 1
        facets[name] = sorted(({'value': v, 'count': c} for v, c in counts.items()),
                              key=lambda e: (-e['count'], e['value']))
    return facets, filtered


def test_facet_view_matches_the_four_pass_computation():
    records = _records()
    rnd = random.Random(9)
    for _ in range(60):
        args = dict(
            kind=rnd.choice([None, 'inscriptions', 'papyri']),
            region=rnd.choice([None, 'Roma', 'Aegyptus']),
            findspot=rnd.choice([None, None, 'Oxyrhynchos']),
            century=rnd.choice([None, None, '1st century AD']),
            text_type=rnd.choice([None, 'epitaph', 'letter']),
            material=rnd.choice([None, 'stone']),
            object_type=rnd.choice([None, 'stele']),
            language=rnd.choice([None, 'la', 'grc']))
        facets, filtered = browse_mod._compute_view(records, **args)
        old_facets, old_filtered = _old_view(records, **args)
        assert facets['filters'] == old_facets
        assert [r.doc_id for r in filtered] == [r.doc_id for r in old_filtered]


def test_browse_keeps_the_view_per_filter_set(monkeypatch):
    records = _records(50)
    monkeypatch.setattr(browse_mod, 'get_records', lambda: records)
    browse_mod.reset_cache()
    calls = []
    real = browse_mod._compute_view
    monkeypatch.setattr(browse_mod, '_compute_view',
                        lambda *a, **k: calls.append(1) or real(*a, **k))
    first = browse_mod.browse(kind='papyri', page=1, page_size=10)
    second = browse_mod.browse(kind='papyri', page=2, page_size=10)
    assert len(calls) == 1                       # page 2 only slices
    assert first['total'] == second['total']
    assert first['documents'] != second['documents'] or first['total'] <= 10
    browse_mod.browse(kind='inscriptions')
    assert len(calls) == 2
    browse_mod.reset_cache()


def test_first_line_is_remembered_unless_the_lookup_failed(monkeypatch):
    browse_mod.reset_cache()
    monkeypatch.setattr(browse_mod.docs, 'is_index_available', lambda lang: True)
    monkeypatch.setattr(browse_mod, '_index_stamp', lambda: ('stamp',))
    reads = []

    def lines(lang, doc_id):
        reads.append((lang, doc_id))
        if doc_id == 'bad':
            raise RuntimeError('transient')
        return {'lines': [{'text': '  ' + doc_id + ' first line  '}]}
    monkeypatch.setattr(browse_mod.docs, 'get_document_lines', lines)
    assert browse_mod.first_line_for('ok', 'la') == 'ok first line'
    assert browse_mod.first_line_for('ok', 'la') == 'ok first line'
    assert reads.count(('la', 'ok')) == 1
    assert browse_mod.first_line_for('bad', 'la') is None
    assert browse_mod.first_line_for('bad', 'la') is None
    assert reads.count(('la', 'bad')) == 2        # a failure is tried again
    browse_mod.reset_cache()


# ---------------------------------------------------------------------------
# hapax: line texts read once per file, with the old parsing
# ---------------------------------------------------------------------------

TEXT = """# a comment
<a. 1.1> first line
  <a. 1.2>   second line
<a. 1.3>
< a. 1.4 > spaced ref
<a. 1.1> a repeated ref, the last one wins
not a tagged line <a. 1.9> inside
<a. 1.5> last line"""


def _hapax_with_text(monkeypatch, tmp_path):
    (tmp_path / 'la').mkdir()
    (tmp_path / 'la' / 'w.tess').write_text(TEXT, encoding='utf-8')
    monkeypatch.setattr(hapax, '_texts_dir', str(tmp_path))
    hapax._line_text_cache.clear()
    hapax._line_store.clear()
    monkeypatch.setattr(hapax, '_line_store_lines', 0)


def test_request_line_texts_equal_get_line_text_from_file(monkeypatch, tmp_path):
    _hapax_with_text(monkeypatch, tmp_path)
    refs = ['a. 1.1', 'a. 1.2', 'a. 1.3', 'a. 1.4', 'a. 1.5', 'a. 1.9', 'a. 9.9']
    old = {r: hapax.get_line_text_from_file('w.tess', 'la', r) for r in refs}
    rows = [{'text_id': 'w.tess', 'ref': r, 'positions_json': '[0]', 'language': 'la'} for r in refs]
    got = hapax._RequestLineTexts().locations(rows)
    assert {loc['ref']: loc['text'] for loc in got} == {r: (old[r] or '') for r in refs}
    assert old['a. 1.1'] == 'a repeated ref, the last one wins'


def test_request_line_texts_are_kept_between_requests(monkeypatch, tmp_path):
    _hapax_with_text(monkeypatch, tmp_path)
    row = {'text_id': 'w.tess', 'ref': 'a. 1.5', 'positions_json': None, 'language': 'la'}
    assert hapax._RequestLineTexts().location(row)['text'] == 'last line'
    # a second request must not open the file again
    monkeypatch.setattr(hapax.fspaths, 'open_text',
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError('file read again')))
    assert hapax._RequestLineTexts().location(row)['text'] == 'last line'
    # an edited file is read again
    monkeypatch.undo()
    (tmp_path / 'la' / 'w.tess').write_text('<a. 1.5> changed text\n', encoding='utf-8')
    monkeypatch.setattr(hapax, '_texts_dir', str(tmp_path))
    assert hapax._RequestLineTexts().location(row)['text'] == 'changed text'


def test_lookup_lemma_locations_keeps_its_shape(monkeypatch, tmp_path):
    _hapax_with_text(monkeypatch, tmp_path)
    monkeypatch.setattr(hapax, '_lemma_location_rows', lambda lemma, language: [
        {'text_id': 'w.tess', 'ref': 'a. 1.2', 'positions_json': '[1, 3]', 'language': 'la'}])
    locs = hapax.lookup_lemma_locations('x', 'la')
    assert len(locs) == 1
    assert locs[0]['text'] == 'second line'
    assert locs[0]['positions'] == [1, 3]
    assert set(locs[0]) == {'text_id', 'author', 'work', 'ref', 'locus', 'citation', 'text', 'positions'}


# ---------------------------------------------------------------------------
# hapax: the bigram table is read once, then again only when the file changes
# ---------------------------------------------------------------------------

def test_bigram_cache_is_not_reread_on_every_request(monkeypatch, tmp_path):
    import backend.bigram_frequency as bf
    path = tmp_path / 'la_bigrams.json'
    path.write_text('{"total_docs": 3, "doc_frequencies": {}}')
    monkeypatch.setattr(bf, 'CACHE_DIR', str(tmp_path))
    bf._bigram_cache.pop('la', None)
    hapax._bigram_cache_stamps.pop('la', None)
    reads = []
    real = bf.load_bigram_cache
    monkeypatch.setattr(bf, 'load_bigram_cache', lambda lang: reads.append(lang) or real(lang))
    hapax._load_bigram_cache_if_changed('la')
    hapax._load_bigram_cache_if_changed('la')
    assert reads == ['la']
    path.write_text('{"total_docs": 4, "doc_frequencies": {"a|b": 1}}')
    hapax._load_bigram_cache_if_changed('la')
    assert reads == ['la', 'la']
    assert bf._bigram_cache['la']['total_docs'] == 4
    bf._bigram_cache.pop('la', None)
    hapax._bigram_cache_stamps.pop('la', None)


def test_extract_bigram_locations_normalizes_each_line_once(monkeypatch):
    calls = []
    monkeypatch.setattr(hapax, 'normalize_line_text', lambda t, lang: calls.append(t) or t.upper())
    units = [{'ref': 'r1', 'text': 'a b c d', 'lemmas': ['a', 'b', 'c', 'd']},
             {'ref': 'r2', 'text': 'e', 'lemmas': ['e']}]
    out = hapax._extract_bigram_locations(units, lambda x, y: f'{x}|{y}', 'la')
    assert calls == ['a b c d']
    assert out['b|c'] == [{'ref': 'r1', 'text': 'A B C D', 'words': ['b', 'c']}]
