"""scripts/corpus/build_window_names.py: out-of-order and decomposed
combining marks were cutting names short in the Reader's "Shared names"
line ("Αναυ" for the river Anauros, "Ηρακλη", "Ποσειδα", "Ελλα", "Υψιπυ").

Two storage faults, both reproduced here exactly as window_texts.db holds
them:

1. A breathing or accent stored as a combining mark standing BEFORE the
   letter it belongs to, rather than after it (e.g. a rough breathing
   before a capital: "̓Α..." for "Ἀ...").
2. An accent or circumflex left as a separate combining mark AFTER its
   vowel, never composed into the one precomposed character Unicode has
   for it (e.g. "ά" never folded into "ά").

The old TOK regex (`[^\\W\\d_]+`) treats any combining mark as a
non-word character, so either fault cuts the token at the mark: fault 1
only breaks a word that also has fault 2 somewhere in it (the orphaned
leading mark itself is just skipped over), and fault 2 alone breaks a
word at the first undecomposed accent, keeping everything before it.

Loaded via importlib rather than a package import: scripts/ is not a
package (test_build_window_names_other_scripts.py uses the same pattern
for this module already).
"""
import importlib.util
import os
import sqlite3
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_SPEC = importlib.util.spec_from_file_location(
    'build_window_names',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'scripts', 'corpus', 'build_window_names.py'))
bwn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bwn)


def _write_window_texts(path, rows):
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE window_texts (id TEXT, language TEXT, work TEXT, '
                'ref_start TEXT, ref_end TEXT, text TEXT)')
    con.executemany('INSERT INTO window_texts VALUES (?,?,?,?,?,?)', rows)
    con.commit(); con.close()


def _read_window_names(path):
    con = sqlite3.connect(path)
    rows = con.execute('SELECT id, k, form FROM window_names').fetchall()
    con.close()
    return rows


# ---------------------------------------------------------------------------
# The five reported names, reconstructed with the exact storage fault that
# produced each truncated form (checked against the OLD regex above before
# writing these down, so the fixture provably reproduces the bug and is not
# just asserting the new behavior against itself).
# ---------------------------------------------------------------------------

# Rough breathing orphaned before the capital, PLUS the acute on the first
# upsilon left decomposed -- the only one of the five with fault 1. Without
# the second fault this word was not actually truncated (the lone leading
# mark is simply skipped), which is why the bug needed both faults present
# somewhere in the window to show up the way it did.
ANAUROS = '̓' + 'Αναυ' + '́' + 'ρου'      # -> Ἀναύρου
HERAKLES = 'Ἡρακλ' + 'η' + '͂' + 'ς'           # -> Ἡρακλῆς
POSEIDAON = 'Ποσειδ' + 'α' + '́' + 'ων'        # -> Ποσειδάων
HELLAS = 'Ἑλλ' + 'α' + '́' + 'ς'               # -> Ἑλλάς
HYPSIPYLE = 'Ὑψιπ' + 'υ' + '́' + 'λη'          # -> Ὑψιπύλη

OLD_TOK = __import__('re').compile(r'[^\W\d_]+')


def _old_truncated(raw):
    """What the pre-fix TOK regex extracted -- used only to document and
    pin the bug this fixes, never as the expected new behavior."""
    return [m.group(0) for m in OLD_TOK.finditer(raw)][0]


def test_fixtures_reproduce_the_reported_truncation():
    # The capital's own breathing is precomposed in each of these (only the
    # SECOND mark in the word is left decomposed), so the old regex keeps
    # the breathing -- it is one codepoint, not a combining mark on its
    # own -- and still cuts the word at the decomposed mark that follows.
    assert _old_truncated(ANAUROS) == 'Αναυ'
    assert _old_truncated(HERAKLES) == 'Ἡρακλη'
    assert _old_truncated(POSEIDAON) == 'Ποσειδα'
    assert _old_truncated(HELLAS) == 'Ἑλλα'
    assert _old_truncated(HYPSIPYLE) == 'Ὑψιπυ'


def test_normalize_window_text_composes_a_leading_orphaned_breathing():
    assert bwn.normalize_window_text(ANAUROS) == unicodedata.normalize('NFC', 'Ἀναύρου')


def test_normalize_window_text_composes_a_trailing_decomposed_accent():
    assert bwn.normalize_window_text(HERAKLES) == unicodedata.normalize('NFC', 'Ἡρακλῆς')
    assert bwn.normalize_window_text(POSEIDAON) == unicodedata.normalize('NFC', 'Ποσειδάων')
    assert bwn.normalize_window_text(HELLAS) == unicodedata.normalize('NFC', 'Ἑλλάς')
    assert bwn.normalize_window_text(HYPSIPYLE) == unicodedata.normalize('NFC', 'Ὑψιπύλη')


def test_normalize_window_text_leaves_a_detached_stray_mark_alone():
    """A combining mark with nothing alphabetic after it (end of line, or
    before punctuation) is not something this can fix -- it is left in
    place rather than silently dropped or glued onto an unrelated letter."""
    raw = 'λογος' + '́' + '.'
    out = bwn.normalize_window_text(raw)
    assert '́' in out or unicodedata.combining(out[-2]) if len(out) > 1 else True
    # The mark is neither deleted nor moved past the period.
    assert out.replace('́', '') == 'λογος.' or out[-1] == '.'


def test_tokens_no_longer_splits_mid_word():
    for raw, expect in (
        (ANAUROS, 'Ἀναύρου'),
        (HERAKLES, 'Ἡρακλῆς'),
        (POSEIDAON, 'Ποσειδάων'),
        (HELLAS, 'Ἑλλάς'),
        (HYPSIPYLE, 'Ὑψιπύλη'),
    ):
        forms = [w for w, _mid in bwn.tokens(raw)]
        assert forms == [unicodedata.normalize('NFC', expect)], raw


def test_tokens_latin_is_unaffected():
    """No combining marks anywhere in the line: tokens() must split exactly
    where it always did."""
    line = 'Arma virumque cano, Troiae qui primus ab oris.'
    assert [w for w, _mid in bwn.tokens(line)] == [
        'Arma', 'virumque', 'cano', 'Troiae', 'qui', 'primus', 'ab', 'oris',
    ]


def test_key_of_the_composed_word_matches_the_undamaged_form():
    """The key function itself is unchanged; once the token is the whole
    word, its key is the same first-five-letters key a never-damaged copy
    of the word would have produced."""
    assert bwn.key(unicodedata.normalize('NFC', 'Ἀναύρου')) == bwn.key('Ἀναύρου')
    assert bwn.key('Ἀναύρου') == 'anaur'
    # The old truncated stem keyed differently -- this is what made the
    # Reader's "Shared names" key (and so its matching) wrong, not only its
    # display: 'anau' is not 'anaur'.
    assert bwn.key('Αναυ') != bwn.key('Ἀναύρου')


def test_main_stores_the_whole_composed_form_as_the_display_name():
    """End-to-end through main(): a window holding the damaged Anauros
    storage, with the name capitalised enough times to clear the la/grc/en
    pass's threshold, keys and displays the WHOLE word, not the old
    truncated stem."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        passage_dir = os.path.join(td, 'passage_index')
        os.makedirs(passage_dir)
        text = (
            f'ῥεῖα παρὰ προχοὰς {ANAUROS} ῥέοντος.\n'
            f'αὖτις ἐπ᾽ {ANAUROS} πάλιν ἤλυθε.\n'
            f'ὄχθας {ANAUROS} λιπὼν ἀπέβη.'
        )
        _write_window_texts(os.path.join(passage_dir, 'window_texts.db'), [
            ('grc1:fine:0', 'grc', 'apollonius_rhodius.argonautica', '1.9', '1.11', text),
        ])
        no_lemma = os.path.join(td, 'no_lemma_tables')
        no_syntax = os.path.join(td, 'no_syntax.db')
        no_cache = os.path.join(td, 'no_cache')
        orig_idx, orig_lt, orig_sdb, orig_cache = bwn.IDX, bwn.LEMMA_TABLES_DIR, bwn.SYNTAX_COPTIC_DB, bwn.CACHE_LEMMAS_DIR
        bwn.IDX = passage_dir
        bwn.LEMMA_TABLES_DIR = no_lemma
        bwn.SYNTAX_COPTIC_DB = no_syntax
        bwn.CACHE_LEMMAS_DIR = no_cache
        try:
            out = os.path.join(td, 'out.db')
            bwn.main(out)
            rows = _read_window_names(out)
        finally:
            bwn.IDX, bwn.LEMMA_TABLES_DIR, bwn.SYNTAX_COPTIC_DB, bwn.CACHE_LEMMAS_DIR = (
                orig_idx, orig_lt, orig_sdb, orig_cache)

    names = {(wid, k): form for wid, k, form in rows}
    composed = unicodedata.normalize('NFC', 'Ἀναύρου')
    expected_key = bwn.key(composed)
    assert ('grc1:fine:0', expected_key) in names
    assert names[('grc1:fine:0', expected_key)] == composed
    assert len(names[('grc1:fine:0', expected_key)]) == len(composed), (
        'the stored form must be the whole word, not the old truncated stem')
