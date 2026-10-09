"""scripts/corpus/build_window_names.py's Hebrew, Coptic, Persian and Urdu
passes (research/specs/2026-10-07_names_other_scripts_build_spec.md).

Loaded via importlib rather than a package import: scripts/ is not a
package (tests/test_build_connections_map_pruning.py already uses this
pattern for a sibling script). The module's top-level backend imports
(backend.hebrew.processor etc.) are lightweight -- no CLTK, no Stanza
pipeline load -- so importing it costs nothing extra at collection time.

No live data needed anywhere: every fixture is a toy built in a tmp dir,
and `main()` itself is exercised end-to-end by monkeypatching the module's
path constants (IDX, LEMMA_TABLES_DIR, SYNTAX_COPTIC_DB, CACHE_LEMMAS_DIR)
to point at those toy fixtures instead of the real data stack.
"""
import importlib.util
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SPEC = importlib.util.spec_from_file_location(
    'build_window_names',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'scripts', 'corpus', 'build_window_names.py'))
bwn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bwn)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_hebrew_name_set_keeps_only_nmpr():
    table = {'אברהם': 'nmpr', 'מלך': 'subs', 'הלך': 'verb', 'נח': 'nmpr'}
    assert bwn.hebrew_name_set(table) == {'אברהם', 'נח'}


def test_propn_purity_set_requires_both_rate_and_count():
    pairs = (
        [('yusuf', 'PROPN')] * 9 + [('yusuf', 'NOUN')] * 1 +     # 9/10 = 90%, enough occurrences
        [('rare', 'PROPN')] * 2 +                                 # 2/2 = 100% but under min_total
        [('noisy', 'PROPN')] * 2 + [('noisy', 'NOUN')] * 2        # 2/4 = 50%, fails the rate
    )
    names = bwn.propn_purity_set(pairs, min_total=3, min_rate=0.85)
    assert names == {'yusuf'}


def test_propn_purity_set_boundary_is_inclusive():
    # Exactly at both thresholds should pass (>=, not >).
    pairs = [('x', 'PROPN')] * 17 + [('x', 'NOUN')] * 3  # 17/20 = 0.85
    assert bwn.propn_purity_set(pairs, min_total=20, min_rate=0.85) == {'x'}
    assert bwn.propn_purity_set(pairs, min_total=21, min_rate=0.85) == set()


def test_names_in_window_keeps_first_spelling_and_ignores_non_names():
    orig = ['Abraham', 'walked', 'Avraham', 'again']
    norm = ['אברהם', 'הלך', 'אברהם', 'הלך']
    ks = bwn.names_in_window(orig, norm, {'אברהם'})
    assert ks == {'אברהם': 'Abraham'}  # first occurrence wins, not the second spelling


def test_names_in_window_empty_when_no_names_match():
    assert bwn.names_in_window(['a', 'b'], ['a', 'b'], {'zzz'}) == {}


def test_parse_lexicon_skips_comments_and_blanks_keeps_word_column():
    lines = [
        '# a header comment',
        '',
        'یوسف\tJoseph',
        '   ',
        '# another comment\twith a tab in it',
        'موسی\tMoses',
    ]
    assert bwn.parse_lexicon(lines) == ['یوسف', 'موسی']


def test_urdu_ghazal_stoplist_contains_the_documented_images():
    # Spot-check a few of the words the report and the build-script comment
    # both name (wine, tulip, beloved); normalize_urdu is idempotent on them.
    for w in ('می', 'لالہ', 'محبوب'):
        assert bwn.normalize_urdu(w) in bwn.URDU_GHAZAL_STOPLIST


def test_fa_and_ur_lexicons_share_the_quranic_prophets_but_not_identically():
    # Both carry Joseph/Moses; the Urdu list is the documented SUBSET of the
    # Quranic roster (see the UR_LEXICON comment), so it must not be a
    # superset of the Persian one.
    assert 'یوسف' in bwn.FA_LEXICON and 'موسی' in bwn.FA_LEXICON
    assert 'یوسف' in bwn.UR_LEXICON
    assert not set(bwn.UR_LEXICON) >= set(bwn.FA_LEXICON)


# ---------------------------------------------------------------------------
# File/DB-shaped readers, on toy fixtures
# ---------------------------------------------------------------------------

def test_syntax_coptic_pairs_reads_token_upos_arrays(tmp_path):
    db = str(tmp_path / 'syntax_coptic.db')
    con = sqlite3.connect(db)
    con.execute('CREATE TABLE syntax (text_id INTEGER, ref TEXT, tokens TEXT, '
                'lemmas TEXT, upos TEXT, heads TEXT, deprels TEXT, feats TEXT)')
    con.execute('INSERT INTO syntax VALUES (1, "t.1", ?, "[]", ?, "[]", "[]", "[]")',
               (json.dumps(['ⲓⲏⲥⲟⲩⲥ', 'ⲁ', 'ϥⲙⲟⲟϣⲉ']),
                json.dumps(['PROPN', 'AUX', 'VERB'])))
    con.commit(); con.close()

    pairs = list(bwn.syntax_coptic_pairs(db, lambda t: t))
    assert ('ⲓⲏⲥⲟⲩⲥ', 'PROPN') in pairs
    assert ('ϥⲙⲟⲟϣⲉ', 'VERB') in pairs
    assert len(pairs) == 3


def test_cache_pos_pairs_reads_units_line_tokens_and_pos_tags(tmp_path):
    cache_dir = tmp_path / 'fa'
    cache_dir.mkdir()
    (cache_dir / 'hafez.diwan-abc123.json').write_text(json.dumps({
        'text_id': 1, 'language': 'fa',
        'units_line': [
            {'ref': 'hafez.diwan.1.1', 'tokens': ['يوسف', 'گم', 'گشته'],
             'pos_tags': ['PROPN', 'ADJ', 'VERB']},
            {'ref': 'hafez.diwan.1.2', 'tokens': ['باز', 'آید'],
             'pos_tags': ['ADV', 'VERB']},
        ],
    }), encoding='utf-8')
    pairs = list(bwn.cache_pos_pairs(str(cache_dir), lambda t: t))
    assert ('يوسف', 'PROPN') in pairs
    assert len(pairs) == 5


# ---------------------------------------------------------------------------
# main() end to end, against toy fixtures standing in for the whole data
# stack (window_texts.db, hebrew_pos.json, syntax_coptic.db, cache/lemmas).
# ---------------------------------------------------------------------------

def _write_window_texts(path, rows):
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE window_texts (id TEXT, language TEXT, work TEXT, '
                'ref_start TEXT, ref_end TEXT, text TEXT)')
    con.executemany('INSERT INTO window_texts VALUES (?,?,?,?,?,?)', rows)
    con.commit(); con.close()


def _read_window_names(path):
    con = sqlite3.connect(path)
    rows = con.execute('SELECT id, k, form FROM window_names').fetchall()
    meta = dict(con.execute('SELECT key, value FROM meta').fetchall())
    con.close()
    return rows, meta


def test_main_builds_names_for_every_new_language(tmp_path, monkeypatch):
    passage_dir = tmp_path / 'passage_index'
    passage_dir.mkdir()
    _write_window_texts(str(passage_dir / 'window_texts.db'), [
        # la: unchanged capitalisation pass, one real window to prove it
        # still runs inside main() after the refactor. 'Aeneas' needs 3+
        # mid-line capitalised occurrences to clear the la/grc/en pass's own
        # threshold (unchanged by this spec); 'Itaque' is deliberately the
        # first word of its line (not mid-line) so it stays excluded, same
        # as in the live index.
        ('la1:fine:0', 'la', 'ovid.metamorphoses', '1.1', '1.2',
         'dux Aeneas videt Aeneas audit Aeneas currit.\nItaque media nocte venit.'),
        # he: Abraham (אברהם, nmpr) pointed in the text, 'walked' is not a name.
        ('he1:fine:0', 'he', 'genesis', '12.1', '12.1', 'אַבְרָהָם הָלַךְ'),
        # cop: a PROPN-tagged name from the toy syntax db, plus a non-name word.
        ('cop1:fine:0', 'cop', 'shenoute.text', '1.1', '1.1', 'ⲓⲏⲥⲟⲩⲥ ϥⲙⲟⲟϣⲉ'),
        # fa: يوسف passes the purity filter on its own in the toy cache below.
        ('fa1:fine:0', 'fa', 'hafez.diwan', '1.1', '1.1', 'يوسف گم گشته'),
        # ur: علي passes purity; می is in the ghazal stoplist and must NOT
        # show up as a name even though it is PROPN-tagged every time below.
        ('ur1:fine:0', 'ur', 'ghalib.diwan', '1.1', '1.1', 'علي می نوشید'),
    ])

    lemma_tables = tmp_path / 'lemma_tables'
    lemma_tables.mkdir()
    (lemma_tables / 'hebrew_pos.json').write_text(
        json.dumps({'אברהם': 'nmpr', 'הלך': 'verb'}), encoding='utf-8')

    syntax_db = tmp_path / 'syntax_coptic.db'
    con = sqlite3.connect(str(syntax_db))
    con.execute('CREATE TABLE syntax (text_id INTEGER, ref TEXT, tokens TEXT, '
                'lemmas TEXT, upos TEXT, heads TEXT, deprels TEXT, feats TEXT)')
    # ⲓⲏⲥⲟⲩⲥ tagged PROPN enough times to clear the 2-occurrence/85% bar;
    # ϥⲙⲟⲟϣⲉ never PROPN.
    for _ in range(3):
        con.execute('INSERT INTO syntax VALUES (1, "t.1", ?, "[]", ?, "[]", "[]", "[]")',
                   (json.dumps(['ⲓⲏⲥⲟⲩⲥ', 'ϥⲙⲟⲟϣⲉ']), json.dumps(['PROPN', 'VERB'])))
    con.commit(); con.close()

    cache_dir = tmp_path / 'cache_lemmas'
    fa_dir = cache_dir / 'fa'; fa_dir.mkdir(parents=True)
    ur_dir = cache_dir / 'ur'; ur_dir.mkdir(parents=True)
    (fa_dir / 'hafez.diwan.json').write_text(json.dumps({
        'units_line': [{'ref': 'hafez.diwan.1.1', 'tokens': ['يوسف'] * 5 + ['گشته'],
                        'pos_tags': ['PROPN'] * 5 + ['VERB']}],
    }), encoding='utf-8')
    (ur_dir / 'ghalib.diwan.json').write_text(json.dumps({
        'units_line': [{'ref': 'ghalib.diwan.1.1',
                        'tokens': ['علي'] * 5 + ['می'] * 5 + ['نوشید'],
                        'pos_tags': ['PROPN'] * 5 + ['PROPN'] * 5 + ['VERB']}],
    }), encoding='utf-8')

    monkeypatch.setattr(bwn, 'IDX', str(passage_dir))
    monkeypatch.setattr(bwn, 'LEMMA_TABLES_DIR', str(lemma_tables))
    monkeypatch.setattr(bwn, 'SYNTAX_COPTIC_DB', str(syntax_db))
    monkeypatch.setattr(bwn, 'CACHE_LEMMAS_DIR', str(cache_dir))

    out = str(tmp_path / 'out.db')
    bwn.main(out)

    rows, meta = _read_window_names(out)
    by_window = {}
    for wid, k, form in rows:
        by_window.setdefault(wid, {})[k] = form

    assert by_window['la1:fine:0'] == {'ainea': 'Aeneas'}  # unchanged la pass
    assert by_window['he1:fine:0'] == {'אברהם': 'אַבְרָהָם'}
    assert by_window['cop1:fine:0'] == {'ⲓⲏⲥⲟⲩⲥ': 'ⲓⲏⲥⲟⲩⲥ'}
    assert by_window['fa1:fine:0'] == {'يوسف': 'يوسف'}
    assert by_window['ur1:fine:0'] == {'علي': 'علي'}, \
        'می must be excluded by the ghazal stoplist even though it is always PROPN-tagged'
    # One window per language in the fixture: Latin keeps its own total, each
    # new script group its own, Persian and Urdu sharing one (2026-10-07).
    assert meta['windows'] == '1'
    assert meta['windows_he'] == '1' and meta['windows_cop'] == '1'
    assert meta['windows_fa'] == meta['windows_ur'] == '2'
    assert os.path.exists(out + '.done')


def test_urdu_lexicon_entry_overrides_the_stoplist(tmp_path, monkeypatch):
    """main() applies the stoplist subtraction BEFORE the lexicon union, so a
    word that is both hand-listed and (hypothetically) stoplisted stays in --
    the hand list is the more specific, human-checked signal."""
    passage_dir = tmp_path / 'passage_index'
    passage_dir.mkdir()
    _write_window_texts(str(passage_dir / 'window_texts.db'), [
        ('ur1:fine:0', 'ur', 'test.work', '1.1', '1.1', 'می'),
    ])
    (tmp_path / 'lemma_tables').mkdir()
    cache_dir = tmp_path / 'cache_lemmas'
    ur_dir = cache_dir / 'ur'; ur_dir.mkdir(parents=True)
    (ur_dir / 'test.json').write_text(json.dumps({
        'units_line': [{'ref': 'test.work.1.1', 'tokens': ['می'] * 5,
                        'pos_tags': ['PROPN'] * 5}],
    }), encoding='utf-8')

    monkeypatch.setattr(bwn, 'IDX', str(passage_dir))
    monkeypatch.setattr(bwn, 'LEMMA_TABLES_DIR', str(tmp_path / 'lemma_tables'))
    monkeypatch.setattr(bwn, 'SYNTAX_COPTIC_DB', str(tmp_path / 'no_such.db'))
    monkeypatch.setattr(bwn, 'CACHE_LEMMAS_DIR', str(cache_dir))
    monkeypatch.setattr(bwn, 'UR_LEXICON', ['می'])

    out = str(tmp_path / 'out.db')
    bwn.main(out)
    rows, _ = _read_window_names(out)
    assert rows, 'می should survive: stoplisted by default but hand-listed in this test'
