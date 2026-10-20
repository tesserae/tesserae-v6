"""Citation recognizer, round 8: the author written just before a shared abbreviation,
the modern references that are not ancient works, and the loci that were joined
or lost. Every sentence is written for this test to show the pattern, none comes from
an article. The unit tests at the top need no abbreviation table. The recognizer tests
need data/citations/abbreviations.json (not in the repository or CI)."""
import pytest

from backend import citations as C
from backend.citations import extractor as E

needs_table = pytest.mark.skipif(
    C.index() is None,
    reason='needs data/citations/abbreviations.json, not shipped (GPL-3.0 source data)')


def _loci(text, context=''):
    out = []
    for h in C.extract(text, context):
        if h['resolved']:
            out.append((h['work_id'], h['locus_start']) if h['locus_end'] is None
                       else (h['work_id'], h['locus_start'], h['locus_end']))
    return out


def _works(text, context=''):
    return [w for w, *_ in _loci(text, context)]


# --- unit tests, no table ----------------------------------------------------

def test_token_before_reads_the_word_in_front_of_a_form():
    def before(text, form):
        return E._token_before(text, text.index(form))
    assert before('as Opp. Cyn. 2', 'Cyn.') == 'Opp'
    assert before('Aristaenetus ( Epist. 1', 'Epist.') == 'Aristaenetus'
    assert before('Ovid, Ars am. 2', 'Ars') == 'Ovid'
    assert before('Schol. in Luc. Eun. 2', 'Eun.') == 'Luc'
    assert before('see 33, Oth. 1', 'Oth.') is None      # a number stands in front, not a word
    assert before('on Lys. 643', 'Lys.') is None


def test_thorn_text_is_recognized_and_ordinary_prose_is_not():
    thorn = 'I haf fat fe lawe & fat fe tyme, fat fis man saide'
    assert E._is_thorn_ocr(thorn)
    assert not E._is_thorn_ocr('Die fe sind fat in Fraktur gesetzt')          # too few of the words
    assert not E._is_thorn_ocr('Cic. Fat. 12 and Cic. Fam. 3.4 say the same')
    assert not E._is_thorn_ocr('Das Haus, fe fe fe fe fe, steht dort')         # no "fat"


def test_the_token_rule_needs_a_name_and_a_shared_form():
    class Idx:
        works_by_base_id = {'a.work': {'author_abbreviations': ['Aa.'], 'author_names': ['Aaus']},
                            'b.other': {'author_abbreviations': ['Bb.'], 'author_names': ['Bbius'],
                                        'work_titles': ['Cynegetica']}}
    idx = Idx()
    shared = [('a.work', 2, 'Cyn.'), ('c.work', 2, 'Cyn.')]
    assert E._author_token_decision(shared, 'Cyn.', 'Bb', False, idx) == ('use', [('b.other', 0, 'Cyn.')])
    assert E._author_token_decision(shared, 'Cyn.', 'Aa', False, idx) == ('use', [('a.work', 0, 'Cyn.')])
    assert E._author_token_decision(shared, 'Cyn.', 'Xxxxxxxxxx', False, idx) is None
    assert E._author_token_decision(shared, 'Cyn.', 'Aristaenetus', False, idx) == (
        'drop', 'requires_author_context:author_not_in_corpus')
    assert E._author_token_decision(shared, 'Cyn.', 'Aristaenetus', True, idx) is None     # a name carried along a list
    assert E._author_token_decision([('a.work', 1, 'Aa. Cyn.')], 'Aa. Cyn.', 'Bb', False, idx) is None


# --- 1. the author named just before the form decides ----------------------------

@needs_table
def test_oppian_before_cyn_is_not_arrian():
    assert _loci('The editor of Opp. Cyn. III 84 reads the verb twice.') == [('oppian_of_apamea.cynegetica', '3.84')]
    assert _works('Arr. Cyn. III 84 describes the hounds') == ['arrian.cynegeticus']


@needs_table
def test_author_carries_across_a_list():
    got = _loci('Compare Sueton Claud. 35, Oth. 1 on the same point.')
    assert got == [('suetonius.de_vita_caesarum.part.5.claudius', '35'),
                   ('suetonius.de_vita_caesarum.part.8.otho', '1')]
    assert _works('Plut. Oth. 1 has it too') == ['plutarch.otho']


@needs_table
def test_nepos_eum_in_a_list_of_lives():
    assert _loci('The verb stands twice in Nepos (Epam. 5, 1; Eum. 8, 2).') == [('nepos.vitae', 'eum.8.2')]
    assert _works('Aesch. Eum. 100 has a different sense') == ['aeschylus.eumenides']


@needs_table
def test_theog_after_lyric_poets_is_not_hesiod():
    assert _loci('Anakr. 453 has the form, so does Theog. 243 and Archil. 123.') == []
    assert _works('Hes. Theog. 243 has it') == ['hesiod.theogony']


@needs_table
def test_scholion_on_lys_with_a_line_number_is_the_lysistrata():
    assert _loci('The scholion (Schol. on Lys. 643) glosses the word.') == [('aristophanes.lysistrata', '643')]
    assert _works('Lys. 12.4 is the speech') == ['lysias.speeches']
    assert _works('Schol. on Lys. 12.4 is the speech') != ['aristophanes.lysistrata']   # a speech number stays


@needs_table
def test_luc_before_eun_is_lucian():
    assert _loci('as the scholion says (Schol. in Luc. Eun. 2)') == [('lucian.eunuchus', '2')]
    assert _works('Ter. Eun. 4.3.1 and the scholion') == ['terence.eunuchus']


@needs_table
def test_name_that_is_no_author_of_the_corpus_drops_a_shared_form():
    assert _loci('the late letter writer Aristaenetus ( Epist. 1.10)') == []
    assert _works('the poet Horace (Epist. 1.10)') == ['horace.epistles']


@needs_table
def test_ars_am_is_the_ars_amatoria_and_keeps_its_first_word():
    assert _loci('Ovid (Ars am. 2.691)') == [('ovid.ars_amatoria', '2.691')]
    assert _works('Ov. Am. 2.1') == ['ovid.amores']
    assert _works('Ars Amat. 1, 25') == ['ovid.ars_amatoria']


@needs_table
def test_marc_with_luther_or_genesis_is_the_gospel():
    assert _loci('Luther has hurt Marc. 5, 12 beside Gen. 19, 12.') == []
    assert _loci('The form Marc. 4, 6, 46 stands with Gen. 21, 17 in the same text.') == []
    assert _works('Plut. Marc. 3, 2 gives the date') == ['plutarch.marcellus']


@needs_table
def test_vit_with_seneca_named_is_de_vita_beata():
    assert _works('As Seneca writes in Vit. 3.1 about the wise man') == ['seneca.de_vita_beata']
    assert _works('Josephus tells it in Vit. 20') == ['flavius_josephus.josephi_vita']


@needs_table
def test_brev_vit_is_the_other_seneca_work():
    assert _works('Sen. de Brev. Vit. 6, 4') == ['seneca.de_brevitate_vitae']


# --- 2. modern references -------------------------------------------------

@needs_table
def test_inventory_number_after_inv_is_no_citation():
    assert _loci('a small clay lamp in the case, Inv. 4861 (Fig. 2)') == []
    assert _works('Cic. Inv. 2, 14 says so') == ['cicero.de_inventione']


@needs_table
def test_journal_with_a_page_after_the_locus():
    assert _loci('as the Bullettino (Bull. d. Comm. arch., i, p. 33 f) has suggested') == []
    assert _works('Strabo X 3, 6, p. 465 has the same story') == ['strabo.geography']       # old edition page
    assert _works('Plat. Rep. VIII, p. 549 E') == ['plato.respublica']                       # Stephanus letter


@needs_table
def test_format_word_after_the_number_is_no_locus():
    assert _loci('A copy in small char., 4to, ff. 20, is listed in the catalog') == []
    assert _works('Theophr. Char. 4 and the rest') == ['theophrastus.characters']


@needs_table
def test_modern_reference_list():
    assert _loci('see the Thes. L. L. under this word') == []
    assert _loci('Compare the passage in Chaucer, T. and C., 3, 1025') == []


@needs_table
def test_middle_english_with_thorn_misread_is_dropped():
    assert _loci('He sayde fat fe man saw fat fe child, fat fis tyme') == []
    assert _works('Cic. Fat. 12 is meant') == ['cicero.de_fato']


@needs_table
def test_count_in_square_brackets_is_no_locus():
    assert _loci('the noun cum (Cic., Verg.) [3 verbs]') == []


@needs_table
def test_footnote_number_after_a_name_without_an_abbreviation_period():
    assert _loci('as told by Livy. 7 See the lexicon for the word') == []
    assert _works('as Livy 21.30.11 has it') == ['livy.ab_urbe_condita']


@needs_table
def test_first_level_past_the_last_book_of_a_two_level_work():
    assert _loci('Boethius says (Cons. 11, 42)') == []
    assert _works('Boethius says (Cons. 3, 12)') == ['boethius.consolatio_philosophiae']
    assert _works('Hor. Sat. 2, 4, 73') == ['horace.satires']


# --- 3. loci joined or lost ----------------------------------------------

@needs_table
def test_two_chapters_after_a_comma():
    assert _loci('Odd forms recur in Hdt. IV, 77, 156, as noted') == [('herodotus.histories', '4.77'), ('herodotus.histories', '4.156')]
    assert _loci('Hdt. 3, 80, 12 has it') == [('herodotus.histories', '3.80.12')]


@needs_table
def test_line_range_without_a_hyphen_in_a_one_level_work():
    assert _loci('as Arist. Av. 17. 18 shows') == [('aristophanes.birds', '17', '18')]
    assert _loci('as Ar. Ach. 1 1 24 shows') == [('aristophanes.acharnians', '1124')]       # a split number stays joined


@needs_table
def test_next_line_of_the_same_book_after_a_comma():
    assert _loci('Ovid, Ars am. 2.691, 721') == [('ovid.ars_amatoria', '2.691'), ('ovid.ars_amatoria', '2.721')]
    assert _loci('Verg. Aen. 10. 681, 683') == [('vergil.aeneid', '10.681'), ('vergil.aeneid', '10.683')]
