"""Citation recognizer: Thucydides, Livy, Pliny the Elder, Apollonius Rhodius
and Tibullus, cited with forms the generated abbreviation table lacks
(Thuc., Livy, Plin. N. H., Ap. Rhod., Tibull.), and the whole-and-parts tie
that kept 'Liv.' and 'Plin. Nat.' from resolving. Each sentence is real text
from an early-journal article.

Needs data/citations/abbreviations.json (not in the repository or CI), so the
module is skipped without it, like tests/test_citations_forms.py.
"""
import pytest

from backend import citations as C

pytestmark = pytest.mark.skipif(
    C.index() is None,
    reason='needs data/citations/abbreviations.json, not shipped (GPL-3.0 source data)')


def _resolved(text):
    return [(h['work_id'], h['locus_start']) for h in C.extract(text) if h['resolved']]


def test_thucydides_abbreviated_and_spelled_out():
    assert _resolved('Compare also Thuc. VI 2, 4.') == [('thucydides.peleponnesian_war', '6.2.4')]
    assert _resolved('sag Ssoi, Thuc. 3, 102, cf. b. fin.') == [('thucydides.peleponnesian_war', '3.102')]
    assert _resolved('See Classen on Thuk. 1,6, 1, and often') == [('thucydides.peleponnesian_war', '1.6.1')]
    assert _resolved('as evinced by Thucydides (II, 15) and others') == [('thucydides.peleponnesian_war', '2.15')]


def test_livy_by_name_and_by_liv():
    assert _resolved("there is an ellipsis of the verb, e. g. Livy 2, 12, 13 'en tibi' inquit") \
        == [('livy.ab_urbe_condita', '2.12.13')]
    assert _resolved('Rome, I, 315. 6 Livy iii. 34. 6; Dionysius Hal. x. 57. 3.')[0] \
        == ('livy.ab_urbe_condita', '3.34.6')
    # 'Liv.' was tied across the whole work and its four parts
    assert _resolved('Liv. XXXV. 24.') == [('livy.ab_urbe_condita', '35.24')]


def test_pliny_the_elder_natural_history_forms():
    for text, locus in [
        ('cf. Ann. vi. 28 and Pliny N.H. x. 2. 5.', '10.2.5'),
        ('V 155; Plin. N. H. V 31; Plin. Ep. II 23', '5.31'),
        ('Plin. HN 3.26', '3.26'),
        ('Plin. Nat. 9, 3', '9.3'),
    ]:
        assert ('pliny_the_elder.naturalis_historia', locus) in _resolved(text)


def test_bare_plin_stays_ambiguous():
    # Pliny the Elder or the Younger: no guess
    assert _resolved('Plin. 12, 43') == []


def test_apollonius_rhodius_forms():
    assert _resolved("and 'AipaprfnaSai Ap. Rhod. 1. 151). The name") \
        == [('apollonius_rhodius.argonautica', '1.151')]
    assert _resolved('Apoll. Rhod. 2. 769') == [('apollonius_rhodius.argonautica', '2.769')]


def test_tibullus_by_name():
    assert _resolved('Cf. Tibullus, 3. 3. 10 (Lydgamus) : nudus') == [('tibullus.elegies', '3.3.10')]
    assert _resolved('Tibull. 1.1.1') == [('tibullus.elegies', '1.1.1')]


@pytest.mark.parametrize('text', [
    'Quint 1989, 37',
    'Livy 1989, 37',
    'Thucydides 1996, 2',
    'Tibullus 1989, 12',
])
def test_author_year_page_is_not_a_locus(text):
    assert _resolved(text) == []


@pytest.mark.parametrize('text', [
    'Livy did not make his dates agree',
    'the mind, of Thucydides, I am following a path',
])
def test_bare_name_before_an_ordinary_word_is_not_a_citation(text):
    assert _resolved(text) == []


def test_footnote_number_after_a_blank_line_is_not_a_locus_level():
    assert _resolved('Livy iii. 33. 1.\n\n3 Wordsworth, Early Latin') == [('livy.ab_urbe_condita', '3.33.1')]
    assert _resolved('Livy, XXVII 10.\n\n6 In Ribbeck') == [('livy.ab_urbe_condita', '27.10')]


def test_footnote_gluing_form_is_unchanged_for_other_authors():
    # The glued "9.35. 80" form was read this way before the alias work and
    # still is; the alias work must not change it.
    assert _resolved('Verg. Ecl. 9.35. 80') == [('vergil.eclogues', '9.35.80')]


def test_ocr_lowercase_l_in_a_capital_roman_numeral():
    assert _resolved('Cic. Fam. Ill, 4, 1') == [('cicero.epistulae_ad_familiares', '3.4.1')]
    assert _resolved('Sen. Ep. lxxix. 7') == [('seneca.ad_lucilium_epistulae_morales', '79.7')]
