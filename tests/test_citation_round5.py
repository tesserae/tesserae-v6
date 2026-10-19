"""Citation recognizer, round 5: Pindar book letters on lists and on a letter
after the author's name, the space after a colon that ends a locus, a level
with a leading zero, and default works for Ann., Th., Str., Arr. and Ben.
Each string is constructed in the shape the Project MUSE audit counted (no
article text). Needs data/citations/abbreviations.json (not in the repository
or CI), so the module is skipped without it."""
import pytest

from backend import citations as C

pytestmark = pytest.mark.skipif(
    C.index() is None,
    reason='needs data/citations/abbreviations.json, not shipped (GPL-3.0 source data)')


def _hits(text, context=''):
    return [(h['work_id'], h['locus_start'], h['locus_end'], h['citation_surface'])
            for h in C.extract(text, context) if h['resolved']]


def _one(text, context=''):
    got = _hits(text, context)
    assert len(got) == 1, got
    return got[0]


# --- Pindar ---------------------------------------------------------------

def test_pindar_book_list_gets_the_book_letter():
    got = _hits('See Pind. Pyth. IV, V, IX.')
    assert [(w, lc) for w, lc, _e, _s in got] == [
        ('pindar.odes', 'p.4'), ('pindar.odes', 'p.5'), ('pindar.odes', 'p.9')]


def test_pindar_olympian_list_gets_the_book_letter():
    got = _hits('Pind. Ol. I, II, III.')
    assert [lc for _w, lc, _e, _s in got] == ['o.1', 'o.2', 'o.3']


def test_pindar_letter_after_the_name_is_not_a_first_level():
    assert _one('Pi. I. 8.47')[:2] == ('pindar.odes', 'i.8.47')


def test_pindar_spelled_book_with_line_unchanged():
    assert _one('Pind. Pyth. IV 299')[:2] == ('pindar.odes', 'p.4.299')
    assert _one('Pind. Ol. XIII 5')[:2] == ('pindar.odes', 'o.13.5')


# --- a colon followed by a space ends the locus ----------------------------

@pytest.mark.parametrize('text,locus', [
    ('Isth. I, 23: 07', 'i.1.23'),
    ('Verg. A. 7.259: di and more', '7.259'),
    ('Hor. Od. IV, 3, 18 : 0', '4.3.18'),
    ('Sol. 23: vd', None),
])
def test_colon_with_space_ends_the_locus(text, locus):
    got = _hits(text)
    if locus is None:
        assert all('495' not in (lc or '') for _w, lc, _e, _s in got)
    else:
        assert got[0][1] == locus


def test_colon_with_space_after_a_range_adds_no_level():
    w, start, end, surface = _one('Fast. 5.379–414): 1')
    assert (w, start, end) == ('ovid.fasti', '5.379', '5.414')


def test_tight_colon_is_still_a_level():
    assert _one('Man 21:1–17')[:3] == ('manilius.astronomica', '21.1', '21.17')


def test_level_with_a_leading_zero_is_not_a_level():
    assert _hits('Diod. : 01 8') == []
    assert _one('Isth. I, 23: 07')[3] == 'Isth. I, 23'


# --- default works ----------------------------------------------------------

def test_ann_with_two_levels_is_tacitus():
    assert _one('Ann. 14.20')[:2] == ('tacitus.annales', '14.20')


def test_ann_with_one_level_stays_open():
    assert _hits('Ann. 5') == []


def test_ann_with_ennius_named_is_ennius():
    assert _one('Enn. Ann. 12')[0] == 'ennius.annales'


def test_th_with_two_levels_is_thucydides_and_one_level_stays_open():
    assert _one('Th. 3.49')[:2] == ('thucydides.peloponnesian_war', '3.49')
    assert _hits('Th. 590') == []


def test_str_is_strabo_geography():
    assert _one('Str. 8.3.30')[:2] == ('strabo.geography', '8.3.30')


def test_arr_with_three_levels_is_the_anabasis():
    assert _one('Arr. 2.14.4')[:2] == ('arrian.anabasis', '2.14.4')
    assert _hits('Arr. 5') == []


def test_ben_with_book_chapter_section_is_seneca():
    assert _one('Ben. 4.8.3')[:2] == ('seneca.de_beneficiis', '4.8.3')


def test_ben_with_fewer_levels_needs_seneca_named():
    assert _hits('Ben. 4') == []
    assert _one('Sen. Ben. 4')[0] == 'seneca.de_beneficiis'


def test_ben_after_regula_stays_open():
    assert _hits('Regula Ben. 4.8.3') == []


# --- forms round 3 settled, kept under test --------------------------------

@pytest.mark.parametrize('text,work', [
    ('Polyb. 1.84.6', 'polybius.histories'),
    ('Diod. 17.38.4', 'diodorus_siculus.bibliotheca_historica'),
    ('Diod. Sic. 17.38.4', 'diodorus_siculus.bibliotheca_historica'),
    ('Xen. Hell. 3.1.2', 'xenophon.hellenica'),
])
def test_forms_from_round_3_resolve(text, work):
    assert _one(text)[0] == work


def test_default_works_need_a_firm_first_level():
    # Annali dell'Istituto and "Arr. c. 6": a lower-case d or c reads as 500 or 100.
    assert _hits('Wissowa, Ann. d. 1st. 1883') == []
    assert _hits('So in Arr. c. 6, 9') == []
    assert _one('Ann. XIV, 31')[:2] == ('tacitus.annales', '14.31')


# --- a closing parenthesis ends the locus ----------------------------------

def test_close_paren_ends_the_locus():
    assert _one('(Aen. 7.803–17).2 Nor is Camilla')[:3] == ('vergil.aeneid', '7.803', '7.817')
    assert _one('(Cic. de Orat. 3.197):16 nihil est')[:2] == ('cicero.de_oratore', '3.197')


# --- lower-case abbreviations that are not works ----------------------------

@pytest.mark.parametrize('text', ['rec. man. 5', 'about long. 99°, lat. 35°', 'C. V. cur. publ. C. V.'])
def test_lowercase_apparatus_words_are_not_works(text):
    assert _hits(text) == []


def test_capital_man_is_still_manilius():
    assert _one('Man. 1.189')[0] == 'manilius.astronomica'


@pytest.mark.parametrize('text,work,locus', [
    ('Compare Th. I.22 and', 'thucydides.peloponnesian_war', '1.22'),
    ('Compare Ann. I.2.', 'tacitus.annales', '1.2'),
    ('See Str. V.8.30', 'strabo.geography', '5.8.30'),
    ('Ann. X.1', 'tacitus.annales', '10.1'),
])
def test_single_letter_roman_book_i_v_x_starts_a_default(text, work, locus):
    assert _one(text)[:2] == (work, locus)


def test_single_letter_roman_other_than_i_v_x_does_not():
    assert _hits('Ann. D. 1') == []
    assert _hits('Ann. A. 1') == []
    assert _hits('Wissowa, Ann. d. 1st. 1883') == []
