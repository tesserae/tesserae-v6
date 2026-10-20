"""Citation recognizer, round 7: three rules the round 6 hand check left open.
1. A one-level locus past the last line of a one-level work is dropped.
2. A line past the end of its book, for verse works cited by book and line.
3. A number in parentheses glued to a book number is no locus level.
The strings are built in the shape of the rows the check read, with no article
text. The unit tests at the top need no abbreviation table. The recognizer
tests need data/citations/abbreviations.json (not in the repository or CI)."""
import json
import os
import subprocess
import sys

import pytest

from backend import citations as C
from backend.citations import extractor as E
from backend.citations import parser as P
from backend.citations import tokenizer as T

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
needs_table = pytest.mark.skipif(
    C.index() is None,
    reason='needs data/citations/abbreviations.json, not shipped (GPL-3.0 source data)')


@pytest.fixture
def tables(monkeypatch):
    """Small tables in place of the committed ones."""
    monkeypatch.setattr(E, '_WORK_SINGLE_LEVEL_MAX', {'x.life': 430})
    monkeypatch.setattr(E, '_WORK_BOOK_LINE_MAX', {'x.epic': {'1': 756, '2': 804, '3': 322}})


# --- 1. one-level locus beyond the work --------------------------------------

def test_single_level_beyond_last_line_of_a_one_level_work(tables):
    assert E._beyond_work('x.life', '466') == 'single_level'
    assert E._beyond_work('x.life', '430') is None
    assert E._beyond_work('x.life', '440') is None        # within a twentieth of the work
    assert E._beyond_work('x.life', '452') == 'single_level'
    assert E._beyond_work('x.life', '1') is None


def test_short_work_has_a_slack_of_two(tables, monkeypatch):
    monkeypatch.setattr(E, '_WORK_SINGLE_LEVEL_MAX', {'x.short': 48})
    assert E._beyond_work('x.short', '50') is None
    assert E._beyond_work('x.short', '51') == 'single_level'


def test_rule_one_leaves_mixed_depth_and_deeper_works_alone(tables):
    assert E._beyond_work('x.mixed', '466') is None      # not in the table: corpus depth is mixed
    assert E._beyond_work('x.prose', '466') is None      # not in the table: cited at two levels
    assert E._beyond_work('x.unknown', '466') is None


def test_letter_after_the_number_does_not_hide_the_overshoot(tables):
    assert E._beyond_work('x.life', '466b') == 'single_level'


# --- 2. line beyond its book -------------------------------------------------

def test_line_beyond_book(tables):
    assert E._beyond_work('x.epic', '3.463') == 'book_line'
    assert E._beyond_work('x.epic', '3.322') is None
    assert E._beyond_work('x.epic', '1.756') is None
    assert E._beyond_work('x.epic', '1.758') is None      # editions differ by a line or two
    assert E._beyond_work('x.epic', '1.759') == 'book_line'


def test_book_missing_from_table_or_work_not_in_table_is_left_alone(tables):
    assert E._beyond_work('x.epic', '13.5000') is None   # book 13: the book-number rule's business
    assert E._beyond_work('x.prose', '2.5000') is None   # not a verse work


def test_line_range_end_and_third_level_do_not_matter(tables):
    assert E._beyond_work('x.epic', '1.700') is None


def test_fits_work_is_positive_only(tables):
    assert E._fits_work('x.epic', '3.300') is True
    assert E._fits_work('x.epic', '3.463') is False
    assert E._fits_work('x.epic', '13.1') is False
    assert E._fits_work('x.life', '300') is True


def test_book_line_table_builder(tmp_path):
    root = tmp_path / 'texts'
    (root / 'la').mkdir(parents=True)
    (root / 'he').mkdir()
    (root / 'la' / 'verse.epic.tess').write_text(
        '<v. e. 1.1> arma virum\n<v. e. 1.2> cano troiae\n<v. e. 1.3> qui primus\n'
        '<v. e. 2.1> conticuere omnes\n<v. e. 2.2> intentique ora\n', encoding='utf-8')
    (root / 'la' / 'prose.work.tess').write_text(
        '<p. w. 1.1> ' + 'x' * 200 + '\n<p. w. 1.2> ' + 'y' * 200 + '\n', encoding='utf-8')
    (root / 'la' / 'mixed.work.tess').write_text(
        '<m. w. 1.1> arma\n<m. w. 1.2.3> virum\n<m. w. 1.3.4> cano\n', encoding='utf-8')
    (root / 'la' / 'life.tess').write_text('<l. 1> vita prima\n<l. 2> vita secunda\n<l. 3b> tertia\n', encoding='utf-8')
    (root / 'la' / 'chunks.tess').write_text(
        '<c. 1> ' + 'x' * 1500 + '\n<c. 2> ' + 'y' * 1500 + '\n', encoding='utf-8')
    (root / 'he' / 'psalm.tess').write_text('<ps. 1.1> a\n', encoding='utf-8')
    out, single = tmp_path / 'out.json', tmp_path / 'single.json'
    done = subprocess.run([sys.executable, os.path.join(REPO, 'scripts', 'citations', 'derive_work_line_limits.py'),
                           '--corpus-root', str(root), '--out', str(out), '--out-single', str(single)],
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert json.load(open(out, encoding='utf-8')) == {'verse.epic': {'1': 3, '2': 2}}
    # the chunked work (lines of 1,500 characters) is left out, and so is every two-level work
    assert json.load(open(single, encoding='utf-8')) == {'life': 3}


def test_committed_single_level_table_keeps_chunked_works_out():
    table = E._load_work_single_level_max()
    if not table:
        pytest.skip('data/citations/work_single_level_max.json missing')
    assert table['flavius_josephus.josephi_vita'] == 430
    assert 'cicero.brutus' not in table   # corpus chunks of 1,700 characters, printed sections run to 333


def test_committed_table_holds_the_known_ends():
    table = E._load_work_book_line_max()
    if not table:
        pytest.skip('data/citations/work_book_line_max.json missing')
    assert table['juvenal.satires']['3'] == 322
    assert table['vergil.aeneid']['12'] >= 900
    assert table['juvencus.historia_evangelica']['3'] >= 463


# --- 3. glued alternate book number ------------------------------------------

def _levels(text):
    toks = T.tokenize(text) if hasattr(T, 'tokenize') else None
    assert toks is not None
    start = next(i for i, t in enumerate(toks) if t.type == 'NUM')
    levels, _seps, _idx, _k = P._parse_level_seq(toks, start, {})
    return [t.text for t in levels]


def test_alternate_book_number_is_dropped_by_the_parser():
    assert _levels('Ac. 1(4).15') == ['1', '15']
    assert _levels('Ac. 2(5).40') == ['2', '40']


def test_parenthesis_after_a_space_or_a_locus_of_two_levels_is_not_touched():
    assert _levels('Men. 1.26 (102)') == ['1', '26']
    assert _levels('Aen. 1 (4)') == ['1', '4']  # unchanged: only a parenthesis glued to the book number is dropped


@needs_table
def test_academica_alternate_numbering_gives_book_and_section():
    hits = [h for h in C.extract('Cic. Ac. 1(4).15–18') if h['resolved']]
    assert [(h['work_id'], h['locus_start'], h['locus_end']) for h in hits] == [('cicero.academica', '1.15', '1.18')]


@needs_table
def test_round_six_parenthesized_line_still_works():
    hits = [h for h in C.extract('Plaut. Men. 1, 1, 26 (102)') if h['resolved']]
    assert [(h['work_id'], h['locus_start']) for h in hits] == [('plautus.menaechmi', '102')]
    hits = [h for h in C.extract('Ter. Haut 4, 4, 21 (v. 743)') if h['resolved']]
    assert [(h['work_id'], h['locus_start']) for h in hits] == [('terence.heautontimorumenos', '4.4.21')]


# --- the rules through extract() -----------------------------------------------

@needs_table
def test_brutus_section_beyond_the_corpus_chunks_is_kept():
    hits = [(h['work_id'], h['locus_start']) for h in C.extract('Cicero, Brut. 123') if h['resolved']]
    assert hits == [('cicero.brutus', '123')]


@needs_table
def test_josephus_life_section_beyond_430_is_dropped():
    assert [h for h in C.extract('Joseph. Vit. 466') if h['resolved']] == []
    hits = [h for h in C.extract('Joseph. Vit. 430') if h['resolved']]
    assert [(h['work_id'], h['locus_start']) for h in hits] == [('flavius_josephus.josephi_vita', '430')]


@needs_table
def test_juvenal_line_beyond_the_satire_goes_to_juvencus_when_named():
    text = 'Ennodius, Paulinus and Juvencus (Juv. III. 463) treat the Gospels'
    hits = [(h['work_id'], h['locus_start']) for h in C.extract(text) if h['resolved']]
    assert ('juvencus.historia_evangelica', '3.463') in hits
    assert all(w != 'juvenal.satires' for w, _ in hits)


@needs_table
def test_juvenal_line_inside_the_satire_stays():
    hits = [(h['work_id'], h['locus_start']) for h in C.extract('Juv. 3.300') if h['resolved']]
    assert hits == [('juvenal.satires', '3.300')]


@needs_table
def test_aeneid_line_beyond_its_book_is_dropped_and_a_real_line_stays():
    assert [h for h in C.extract('Verg. Aen. 1.1000') if h['resolved']] == []
    hits = [(h['work_id'], h['locus_start']) for h in C.extract('Verg. Aen. 1.756') if h['resolved']]
    assert hits == [('vergil.aeneid', '1.756')]


# --- 4. De legibus: Legg. needs its author ---------------------------------------

@needs_table
@pytest.mark.parametrize('text, work, locus', [
    ('Plato, Legg. 12.942', 'plato.leges', None),
    ('See Plat. Legg. 914 C', 'plato.leges', None),
    ('Cic. Legg. 3, 1, 1', 'cicero.de_legibus', '3.1.1'),
    ('Cicero, de Legg. 2, 23, 59', 'cicero.de_legibus', '2.23.59'),
])
def test_legg_follows_the_author_named(text, work, locus):
    hits = [(h['work_id'], h['locus_start']) for h in C.extract(text) if h['resolved']]
    assert hits and hits[0][0] == work
    if locus:
        assert hits[0][1] == locus


@needs_table
def test_bare_legg_stays_unresolved():
    assert [h for h in C.extract('and for the periphrastic opt. Legg. 678 E, 753 E') if h['resolved']] == []


@needs_table
@pytest.mark.parametrize('text, work', [
    ('Plato, Laws 715e', 'plato.leges'),
    ('Laws 715 e', 'plato.leges'),
    ('Cicero, Laws 1.20', 'cicero.de_legibus'),
])
def test_laws_is_plato_unless_cicero_is_named(text, work):
    assert [h['work_id'] for h in C.extract(text) if h['resolved']][:1] == [work]
