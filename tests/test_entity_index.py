"""backend/entity_index.py: a tiny store built from three synthetic windows, mentions read
back, the stoplist removing a known false positive, the English label parsing and the
lockstep check. No live index is read."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import entity_index as ei  # noqa: E402

KEYS = [
    {'id': 'E0001', 'greek': 'Ῥώμη', 'latin': ['Roma'], 'english': 'Rome', 'type': 'place', 'pleiades': ['423025']},
    {'id': 'E0002', 'greek': 'Ῥώμα', 'latin': ['Romae'], 'english': 'Rome', 'type': 'place', 'pleiades': ['423025']},
    {'id': 'E0003', 'greek': 'Σίνων', 'latin': ['Sinon'], 'english': 'Sinon', 'type': 'person', 'pleiades': []},
]
WINDOWS = [
    ('w:fine:0', 'la', 'w', 'w 1', 'w 2', 'Tum Roma vicit et Sinon fugit.'),
    ('w:fine:1', 'la', 'w', 'w 3', 'w 4', 'Pax in Romae rure, roma minor.'),
    ('w:fine:2', 'la', 'w', 'w 5', 'w 6', 'Nihil hic est.'),
]


def _passage_dir(tmp_path):
    d = tmp_path / 'pi'
    d.mkdir()
    json.dump([w[0] for w in WINDOWS], open(d / 'ids.json', 'w'))
    t = sqlite3.connect(d / 'window_texts.db')
    t.execute('CREATE TABLE window_texts (id TEXT PRIMARY KEY, language TEXT, work TEXT, ref_start TEXT, ref_end TEXT, text TEXT)')
    t.executemany('INSERT INTO window_texts VALUES (?,?,?,?,?,?)', WINDOWS)
    t.commit()
    t.close()
    n = sqlite3.connect(d / 'window_names.db')
    n.execute('CREATE TABLE window_names (id TEXT, k TEXT, form TEXT)')
    n.execute('CREATE TABLE name_df (k TEXT PRIMARY KEY, df INTEGER)')
    n.execute('CREATE TABLE meta (key TEXT, value TEXT)')
    n.executemany('INSERT INTO window_names VALUES (?,?,?)',
                  [('w:fine:0', 'roma', 'Roma'), ('w:fine:0', 'sinon', 'Sinon'), ('w:fine:1', 'roma', 'Romae')])
    n.executemany('INSERT INTO name_df VALUES (?,?)', [('roma', 2), ('sinon', 1)])
    n.execute("INSERT INTO meta VALUES ('windows', '3')")
    n.commit()
    n.close()
    return str(d)


def _stoplist(tmp_path, entities):
    p = tmp_path / 'stop.json'
    json.dump({'entities': entities, 'neighbor_words': {'la': ['pax'], 'grc': [], 'en': []}}, open(p, 'w'))
    return str(p)


def test_build_and_read_back(tmp_path):
    pdir = _passage_dir(tmp_path)
    out = str(tmp_path / 'entities.sqlite')
    counts, _, ents = ei.build_store(KEYS, pdir, out, stoplist_path=_stoplist(tmp_path, {}), log=lambda *_: None)
    # the two Rome keys share a Pleiades id, so they merge into one entity
    assert counts['entities_list'] == 2
    conn = ei.open_store(out)
    rome = ei.mentions_of(conn, 'pl:423025')
    # capital initial required: lower-case "roma" in window 1 does not count
    assert sorted(r[0] for r in rome) == ['w:fine:0', 'w:fine:1']
    assert {r[5] for r in rome} == {'Roma', 'Romae'}
    # Roma has a four-letter stem, so it is not distinctive; "pax" within three tokens confirms window 1
    conf = {r[0]: r[7] for r in rome}
    assert conf['w:fine:1'] == 'neighbor'
    assert conf['w:fine:0'] == 'unconfirmed'
    # the second source: the corpus's own names, linked by name_key
    sinon = ei.mentions_of(conn, 'ln:E0003')
    assert [r[0] for r in sinon] == ['w:fine:0']
    assert ei.mentions_of(conn, 'nm:sinon')[0][0] == 'w:fine:0'
    assert conn.execute("select name_key from entities where entity_id='pl:423025'").fetchone()[0] == 'roma'
    assert ei.find_entities(conn, 'Sinon')[0][0] == 'ln:E0003'
    assert ei.counts_by_work(conn, 'pl:423025') == [('w', 2)]


def test_stoplist_removes_known_false_positive(tmp_path):
    pdir = _passage_dir(tmp_path)
    plain = str(tmp_path / 'a.sqlite')
    stopped = str(tmp_path / 'b.sqlite')
    ei.build_store(KEYS, pdir, plain, stoplist_path=_stoplist(tmp_path, {}), log=lambda *_: None)
    counts, _, _ = ei.build_store(
        KEYS, pdir, stopped, log=lambda *_: None,
        stoplist_path=_stoplist(tmp_path, {'Ῥώμη': {'forms': ['Romae'], 'reason': 'test'}}))
    assert counts['removed_by_stoplist'] == 1
    a = {r[0] for r in ei.mentions_of(ei.open_store(plain), 'pl:423025')}
    b = {r[0] for r in ei.mentions_of(ei.open_store(stopped), 'pl:423025')}
    assert a == {'w:fine:0', 'w:fine:1'}
    assert b == {'w:fine:0'}


def test_english_forms_drop_parenthetical_notes():
    assert ei._english_forms('Arar (river)') == ['Arar']
    assert ei._english_forms('Gortyn(a)') == ['Gortyn']
    assert ei._english_forms('Rhaga(i)/Europos/Ray') == ['Rhaga', 'Europos']
    assert ei._english_forms('Ilium/Troia') == ['Ilium', 'Troia']


def test_lockstep_check_reports_a_store_left_behind(tmp_path):
    pdir = _passage_dir(tmp_path)
    out = str(tmp_path / 'entities.sqlite')
    ei.build_store(KEYS, pdir, out, stoplist_path=_stoplist(tmp_path, {}), log=lambda *_: None)
    assert ei.check_lockstep(out, pdir) == []
    ids = json.load(open(os.path.join(pdir, 'ids.json')))
    json.dump(ids + ['w:fine:3'], open(os.path.join(pdir, 'ids.json'), 'w'))
    problems = ei.check_lockstep(out, pdir)
    assert any('unit_windows' in p for p in problems)


class _FakeResolver:
    """Stands in for backend.entity_lemma.Resolver: a fixed form-to-lemma map."""
    source = {}

    def __init__(self, table):
        self.table = table

    def lemmas(self, lang, forms):
        return {f: self.table[f] for f in dict.fromkeys(forms) if f in self.table}


def test_lemma_matcher_needs_a_capital_and_a_name_like_lemma(tmp_path):
    from backend import entity_lemma as el
    pdir = _passage_dir(tmp_path)
    texts = sqlite3.connect(os.path.join(pdir, 'window_texts.db'))
    unit = {w[0] for w in WINDOWS}
    types = el.count_types(texts, unit, log=lambda *_: None)
    # "roma" is written with a capital inside sentences, "romae" once with one
    assert types['la']['roma'][1] >= 1
    ents, _ = ei.merge_list_entities(KEYS)
    res = _FakeResolver({'roma': 'roma', 'romae': 'roma', 'sinon': 'sinon', 'pax': 'pax', 'nihil': 'nihil'})
    tok2ents, info = el.build_lemma_matcher(ents, types, res, log=lambda *_: None)
    rome = [i for i, e in enumerate(ents) if e['label'] == 'Rome'][0]
    # both Rome forms map to the lemma roma, and the lower-case "roma" in window 1 is not a mention
    assert tok2ents['la']['romae'] == (rome,)
    rows, _, _ = el.scan_windows_lemma(texts, unit, tok2ents, log=lambda *_: None)
    got = sorted((r['wid'], r['form']) for r in rows if r['eidx'] == rome)
    assert got == [('w:fine:0', 'Roma'), ('w:fine:1', 'Romae')]
    assert all(not r['homonym'] for r in rows)


def test_first_letter_skips_combining_marks():
    from backend import entity_lemma as el
    assert el.is_cap('̓Ατρεί̈δη')   # breathing before a capital
    assert not el.is_cap('ατρείδη')


def test_audit_drops_a_place_adjective_and_keeps_the_place_name():
    from backend import entity_lemma_audit as ela
    ents = [{'entity_id': 'pl:1', 'type': 'place', 'label': 'Latium'},
            {'entity_id': 'ln:2', 'type': 'person', 'label': 'Latius'}]
    stats = {'la': {'latium': [10, 10, 8, 8], 'latius': [10, 10, 8, 8]}, 'grc': {}, 'en': {}}
    out = ela.propose(ents, {'la': {0: {'latium', 'latius'}, 1: {'latius'}}, 'grc': {}, 'en': {}}, stats)
    assert out[('la', 0, 'latius')] == ('drop', 'demonym_or_adjective')
    assert out[('la', 0, 'latium')][0] == 'keep'
    # the person keeps the lemma it shares, flagged for review
    assert out[('la', 1, 'latius')][0] == 'review'
    assert ela.suffix_of('grc', 'Ἀθηναῖος') == 'αιος'


def test_override_form_counts_as_a_name_for_its_entity():
    from backend import entity_lemma as el
    ents, _ = ei.merge_list_entities(KEYS)
    sinon = [i for i, e in enumerate(ents) if e['label'] == 'Sinon'][0]
    path = None
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, 'o.json')
        json.dump({'overrides': [{'entity_id': ents[sinon]['entity_id'], 'lang': 'la', 'forms': ['Sinonem']}]},
                  open(path, 'w'))
        got = el.load_overrides(ents, path)
    assert got['la']['sinonem'] == {sinon}


def test_real_resolver_lemmatizes_capitalized_latin_and_greek_forms():
    """Runs the site's own lemmatizers through entity_lemma.Resolver (no fake), so a renamed
    private method in text_processor fails here. Skipped when the lemma tables are absent."""
    import pytest
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for t in ('latin_lemmas.json', 'greek_lemmas.json'):
        if not os.path.exists(os.path.join(root, 'data', 'lemma_tables', t)):
            pytest.skip('lemma tables absent')
    from backend import entity_lemma as el
    r = el.Resolver(log=lambda *_: None)
    la = r.lemmas('la', [ei.fold(w) for w in ('Romam', 'Troiae', 'Vergilium')])
    assert la == {'romam': 'roma', 'troiae': 'troia', 'uergilium': 'uergilius'}
    grc = r.lemmas('grc', ['Ἀχιλλέα'.lower(), 'Ἀθήνας'.lower(), 'Ὀδυσσέως'.lower()])
    assert list(grc.values()) == ['αχιλλευσ', 'αθηναι', 'οδυσσευσ']
