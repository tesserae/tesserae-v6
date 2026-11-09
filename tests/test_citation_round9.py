"""Citation recognizer, round 9 (2026-11-09): three shared short forms found by the
precision audit of the JSTOR index. Every sentence is written for this test to show
the pattern, none comes from an article. Needs data/citations/abbreviations.json
(not in the repository or CI)."""
import pytest

from backend import citations as C

needs_table = pytest.mark.skipif(
    C.index() is None,
    reason='needs data/citations/abbreviations.json, not shipped (GPL-3.0 source data)')


def _loci(text, context=''):
    return [(h['work_id'], h['locus_start']) for h in C.extract(text, context) if h['resolved']]


# --- Per il, Per i: the Italian article was read as a Roman numeral -----------------

@needs_table
def test_italian_per_il_is_not_pericles():
    assert _loci('Per il resto si veda la nota precedente.') == []
    assert _loci('Per i frammenti Hollis ipotizza una collocazione diversa.') == []
    assert _loci('Per il momento basti questo.') == []


@needs_table
def test_pericles_with_plutarch_named_or_a_two_level_locus_stays():
    assert _loci('Plut. Per. 9.1 reports the same.') == [('plutarch.pericles', '9.1')]
    assert _loci('As Plutarch says (Per. 12), the buildings rose.') == [('plutarch.pericles', '12')]
    assert _loci('See Per. 12.3 on the buildings.') == [('plutarch.pericles', '12.3')]
    assert _loci('The Pericles says so (Per. 9).') == [('plutarch.pericles', '9')]


@needs_table
def test_a_bare_one_level_per_without_plutarch_is_dropped():
    assert _loci('See Per. 9 on the buildings.') == []


# --- inv.: museum inventory numbers -------------------------------------------------

@needs_table
def test_inventory_numbers_are_not_de_inventione():
    assert _loci('Athens, inv. 0.18: a lamp of the fourth century.') == []
    assert _loci('Athens, inv. 12: a lamp.') == []
    assert _loci('Athens, Agora Museum inv. 1234, a cup.') == []


@needs_table
def test_de_inventione_with_cicero_named_stays():
    assert _loci('Cic. inv. 1.5 defines it.') == [('cicero.de_inventione', '1.5')]
    assert _loci('Cicero discusses the point (inv. 1.5).') == [('cicero.de_inventione', '1.5')]
    assert _loci('De inv. 2.4 treats the same.') == [('cicero.de_inventione', '2.4')]


# --- Eutrop.: the historian, not Claudian's poem, unless Claudian is named ---------

@needs_table
def test_bare_eutrop_is_eutropius_the_historian():
    assert _loci('Eutrop. 10.1 records the reign.') == [('eutropius.breviarium', '10.1')]
    assert _loci('Eutrop. 8.1 gives the date.') == [('eutropius.breviarium', '8.1')]


@needs_table
def test_claudian_named_or_in_before_keeps_in_eutropium():
    assert _loci('Claud. Eutrop. 1.5 mocks him.') == [('claudian.in_eutropium', '1.5')]
    assert _loci('Claudian, In Eutrop. 2.20, is harsher.') == [('claudian.in_eutropium', '2.20')]
    assert _loci('In Eutrop. 2.20 the poet is harsher.') == [('claudian.in_eutropium', '2.20')]
