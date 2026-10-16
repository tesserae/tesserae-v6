"""Citation recognizer, round 2: abbreviation collisions found in the MUSE
and EJC runs. Each sentence is the surface form from a real article. A short
form that means another work most of the time counts only with its author
named in the sentence or the one before.

Needs data/citations/abbreviations.json (not in the repository or CI), so the
module is skipped without it, like tests/test_citation_aliases.py.
"""
import pytest

from backend import citations as C

pytestmark = pytest.mark.skipif(
    C.index() is None,
    reason='needs data/citations/abbreviations.json, not shipped (GPL-3.0 source data)')


def _resolved(text, context=''):
    return [(h['work_id'], h['locus_start']) for h in C.extract(text, context) if h['resolved']]


def test_form_needs_eucherius():
    assert _resolved('in outline form. 1. The next stage') == []
    assert _resolved('a new art form.3 In this') == []
    assert _resolved('Eucher. Form. 3') == [('eucherius_of_lyon.formulae_spiritalis_intellegentiae', '3')]
    assert _resolved('Form. 5 shows', 'Eucherius of Lyon wrote a handbook.') \
        == [('eucherius_of_lyon.formulae_spiritalis_intellegentiae', '5')]


def test_epicurus_letter_to_herodotus_is_not_herodotus():
    assert _resolved('Epicurus, Ep. Hdt. 37') == [('epicurus.epistula_ad_herodotum', '37')]
    assert _resolved('Hdt. 1.1') == [('herodotus.histories', '1.1')]


def test_memorabilia_is_not_aristotle_de_memoria():
    assert _resolved('Xenophon terms such leadership (Mem. 1.1.8)') == []
    assert _resolved('Xen. Mem. 1.2.3') == []
    assert _resolved('Mem. 1.2', 'Aristotle treats memory in a short work.') \
        == [('aristotle.de_memoria_et_reminiscentia', '1.2')]


def test_meno_stephanus_page_is_not_menaechmi():
    assert _resolved('Plato Men. 97d') == [('plato.meno', '97d')]
    assert _resolved('Pl. Men. 97d') == [('plato.meno', '97d')]
    assert _resolved('Plaut. Men. 97d') == []
    assert _resolved('Plaut. Men. 219') == [('plautus.menaechmi', '219')]


def test_jerome_against_rufinus_is_not_rufus_of_ephesus():
    assert _resolved('Jerome, adv. Ruf. 1.2') == []
    assert _resolved('Ruf. 5, 2, 21') == [('rufus_of_ephesus.de_renum_et_vesicae_affectionibus', '5.2.21')]


def test_homeric_hymn_to_hermes_is_not_plautus_mercator():
    assert _resolved('h. Merc. 20') == []
    assert _resolved('Merc. 111', 'Plautus staged it.') == [('plautus.mercator', '111')]
    assert _resolved('Plaut. Merc. 123') == [('plautus.mercator', '123')]


def test_april_is_not_prior_analytics():
    assert _resolved('Ovid dates it to Apr. 22 in the Fasti') == []
    assert _resolved('Apr. 1.38', 'Aristotle argues in the Prior Analytics.') \
        == [('aristotle.analytica_priora', '1.38')]


def test_politics_needs_aristotle_and_not_ad_pol_or_ath_pol():
    assert _resolved('Seneca, ad Pol. 3.2') == []
    # never Politics; since round 3 the combined form names the Athenaion Politeia
    assert 'aristotle.politics' not in [w for w, _ in _resolved('Ath. Pol. 22.3')]
    assert 'aristotle.politics' not in [
        w for w, _ in _resolved('Ath.Pol. 22.3', 'Aristotle (or his school) reports it.')]
    assert _resolved('Pol. 1.2') == []
    assert _resolved('Pol. 1.2', 'Aristotle begins with the household.') == [('aristotle.politics', '1.2')]
    assert _resolved('Arist. Pol. 1.2') == [('aristotle.politics', '1.2')]


def test_gorgias_helen_is_not_euripides():
    assert _resolved('Gorgias, Hel. 18') == []
    assert _resolved('Hel. 18') == []
    assert _resolved('Hel. 1050', 'Euripides repeats the line.') == [('euripides.helen', '1050')]
    assert _resolved('Eur. Hel. 1050') == [('euripides.helen', '1050')]


def test_commentary_on_a_work_is_not_the_work():
    assert _resolved('Damascius, In Phaed. 1.2') == []
    assert _resolved('Simplicius: On Aristotle On the Heavens 1.2-3') == []
    assert _resolved('Philoponus: On Aristotle Posterior Analytics 1.19-34.') == []


def test_astronomica_goes_to_manilius_with_manilius_named():
    assert _resolved('Astr. 1', 'Manilius wrote on astrology.') == [('manilius.astronomica', '1')]
    assert _resolved('Astr. 2.3', 'Hyginus describes the constellations.') == [('hyginus.astronomica', '2.3')]
    assert _resolved('Astr. 2.3') == []


@pytest.mark.parametrize('text', ['Aen. 1583', 'Verg. Aen. 1583', 'Aen. 21'])
def test_aeneid_locus_without_a_book_is_dropped(text):
    assert _resolved(text) == []


def test_aeneid_with_two_parts_or_a_book_alone_stays():
    assert _resolved('Aen. 6.847') == [('vergil.aeneid', '6.847')]
    assert _resolved('Aen. 6') == [('vergil.aeneid', '6')]


def test_stephanus_work_keeps_a_plain_page():
    assert _resolved('Rep. 514 D') == [('plato.respublica', '514d')]
