"""Citation recognizer, round 6: the six rules a hand check of 200 sampled rows
named, and one small seventh. Each string is constructed in the shape of the
rows that check read (no article text). Needs data/citations/abbreviations.json
(not in the repository or CI), so the module is skipped without it."""
import pytest

from backend import citations as C

pytestmark = pytest.mark.skipif(
    C.index() is None,
    reason='needs data/citations/abbreviations.json, not shipped (GPL-3.0 source data)')


def _hits(text, context=''):
    return [(h['work_id'], h['locus_start'], h['locus_end'], h['surface'])
            for h in C.extract(text, context) if h['resolved']]


def _loci(text, context=''):
    return [(w, lc) if e is None else (w, lc, e) for w, lc, e, _s in _hits(text, context)]


# --- 1. Italian and French elision -------------------------------------------

@pytest.mark.parametrize('text', [
    "Dell'Ode Per l'inclita Nice di G. Parini",
    "Per l’interpretazione del libro di Filodemo",
    "Qui Sert l'enging en tel manière",
    "Per d'oro e d'argento",
    "Per c'est 5",
    "Sert s'en 3",
    "Per qu'il 2",
    "Per dell'Arte 4",
    "Per nell'ombra 4",
    "Per all'alba 4",
])
def test_elided_article_is_no_roman_numeral(text):
    assert _hits(text) == []


def test_lone_roman_numeral_without_apostrophe_still_counts():
    assert _loci('Per. 50') == [('plutarch.pericles', '50')]
    assert _loci('Plut. Per. l') == [('plutarch.pericles', '50')]


# --- 2. modern references -----------------------------------------------------

def test_publication_year_as_locus_is_dropped():
    assert _hits('On Some Points in the Life of Thucydides, 1873; On a Passage in Homer') == []


def test_locus_followed_by_year_and_pages_is_dropped():
    assert _hits('Arch. I. XV, 1900, pp. 155-195 (32 figs.)') == []


def test_locus_followed_by_page_range_marker_is_dropped():
    assert _hits('Cic. Arch. 8, pp. 12-15') == []


def test_single_page_marker_after_a_book_keeps_the_book():
    # "Plat. Rep. VIII, p. 549 E": the page belongs to the ancient edition
    assert _loci('Plat. Rep. VIII, p. 549 E') == [('plato.respublica', '8')]


def test_locus_followed_by_a_year_after_a_page_range_is_dropped():
    assert _hits('Man 21: 1–17. ———. 1996. Gift') == []


def test_man_with_a_real_locus_stays_manilius():
    assert _loci('Man. 1.1') == [('manilius.astronomica', '1.1')]
    assert _loci('Man 21:1–17') == [('manilius.astronomica', '21.1', '21.17')]


def test_year_after_a_line_that_is_a_plausible_line_is_kept():
    assert _hits('Ar. Av. 1714 ; 1745') != []


def test_journal_title_with_for_hides_the_work_inside_it():
    assert _hits('Gislason: Tid. for fil. og paed. vi 231-253, p. 31;') == []
    assert _hits('Bugge: Rev. de Philol. vi 317') == []


def test_author_abbreviation_followed_by_de_is_not_a_journal():
    assert _loci('Cic. de Orat. 3.155') == [('cicero.de_oratore', '3.155')]


def test_full_title_with_of_is_not_a_journal():
    assert _loci('Flavius Josephus (Antiquities of the Jews, X., 11, 3) renders')[0][0] == (
        'flavius_josephus.antiquitates_judaicae')


def test_lowercase_mos_is_a_footnote_not_the_mosella():
    assert _hits('the de\\mos. 1 In addition') == []
    assert _loci('Mos. 106') == [('ausonius.mosella', '106')]


# --- 3. a nearer author, a biblical book, a locus beyond the work ------------

def test_tertullian_title_is_not_plautus():
    assert _hits('Tert. de Poen. 1 1 num ergo in coccino') == []
    assert _loci('Plaut. Poen. 1 1') == [('plautus.poenulus', '1.1')]


def test_author_of_the_previous_list_item_carries_to_a_bare_title():
    assert _loci('cf. Sen. Ep. 95, 22; 24,14; de Ira, 2, 33, 4;') == [
        ('seneca.ad_lucilium_epistulae_morales', '95.22'),
        ('seneca.ad_lucilium_epistulae_morales', '24.14'),
        ('seneca.de_ira', '2.33.4')]


def test_author_name_is_not_carried_onto_another_author_abbreviation():
    assert _loci('Cic. Att. 5.1; Quint. ii. 6. 7')[-1][0] == 'quintilian.institutio_oratoria'


def test_juv_in_a_list_of_christian_poets_is_juvencus():
    got = _loci('Ennod. 563; primus pater, Avit.; pater aeternus, Juv. III. 203')
    assert got[-1] == ('juvencus.historia_evangelica', '3.203')
    assert _loci('Juv. III. 203') == [('juvenal.satires', '3.203')]
    assert _loci('Juvenal 3: see Juv. III. 203') == [('juvenal.satires', '3.203')]


def test_juvencus_chosen_by_the_list_must_have_the_book():
    # Juvencus wrote four books, so book VI is Juvenal even among Christian poets
    assert _loci('Ennod. 563; Avit.; Juv. VI 306')[-1] == ('juvenal.satires', '6.306')


def test_marc_with_chapter_and_verse_after_biblical_books_is_the_gospel():
    text = 'baurjgim Marc. 1, 38. gabaurjAai Marc. 6, 4. 8, 38. Luke i. 5, Matth. 11, 5.'
    assert _hits('Matth. 11, 5. Marc. 1, 38. Marc. 6, 20') == []
    assert _hits('Jets over Marc 9:48.') == []
    assert text


def test_marc_as_marcellus_still_resolves_without_biblical_signs():
    assert _loci('Plut. Marc. 6') == [('plutarch.marcellus', '6')]


def test_num_after_exodus_is_numbers():
    assert _hits('cases like Exod. xvii. 3 ; Num. ix. 7, 8 ; xiv. 3 ; xxi. 5 in view') == []


def test_att_after_vita_is_nepos_not_cicero():
    assert _hits('Dorgcfdjfagene vit. Att. c. 3 Midiae') == []
    assert _loci('Cic. Att. 12.32.3') == [('cicero.letters_to_atticus', '12.32.3')]


def test_phoen_beyond_seneca_goes_to_euripides():
    assert _loci('Phoen. 1005') == [('euripides.phoenissae', '1005')]
    assert _loci('Phoen. 88') == [('seneca.phoenissae', '88')]


def test_apo_needs_aristotle():
    assert _hits('a prize (Apo. 1.5–6).') == []
    assert _loci('Aristotle, Apo. 1.5–6')[0][0] == 'aristotle.analytica_priora'


def test_first_level_beyond_the_last_book_is_dropped():
    assert _hits('Cic. de Div. 11, 67') == []
    assert _loci('Cic. de Div. 2, 67') == [('cicero.de_divinatione', '2.67')]


def test_pindar_ode_number_beyond_the_book_is_dropped():
    assert _hits('Pyth. 143, where the verb') == []
    assert _loci('Pind. Pyth. 8') == [('pindar.odes', 'p.8')]


# --- 4. a parenthesized continuous line -------------------------------------

def test_plautus_takes_the_continuous_line_from_the_parenthesis():
    assert _loci('Plaut. Men. 1, 1, 26 (102).') == [('plautus.menaechmi', '102')]


def test_terence_keeps_act_scene_line_and_drops_the_parenthesis():
    assert _loci('where none of the mss. indicate a new scene, is at Haut 4, 4, 21 (v. 743).') == [
        ('terence.heautontimorumenos', '4.4.21')]


def test_parenthesized_range_with_a_line_marker():
    assert _loci('Plaut. Men. 1, 1, 26 (ll. 102-105).') == [('plautus.menaechmi', '102', '105')]


def test_parenthesis_after_a_single_level_is_left_as_it_was():
    assert _loci('Plaut. Men. 1 (102)') == [('plautus.menaechmi', '1.102')]


def test_parenthesis_that_is_not_a_line_stays_out_of_the_locus():
    assert _loci('Verg. Aen. 6.847 (cf. 5.12)') == [('vergil.aeneid', '6.847')]


# --- 5. a comma between two loci -------------------------------------------

def test_comma_before_a_range_after_one_level_is_a_level():
    assert _loci('Livy, 34, 1-8 and more') == [('livy.ab_urbe_condita', '34.1', '34.8')]


def test_comma_before_a_range_after_a_range_splits():
    assert _loci('Hes. Theog. 53\u201379, 915\u201317.') == [
        ('hesiod.theogony', '53', '79'), ('hesiod.theogony', '915', '917')]


def test_comma_before_a_number_with_a_point_splits():
    assert _loci('Suet. Iul. 2, 49.1– 4; on both') == [
        ('suetonius.de_vita_caesarum.part.1.julius', '2'),
        ('suetonius.de_vita_caesarum.part.1.julius', '49.1', '49.4')]


def test_comma_after_a_range_before_a_range_splits():
    assert _loci('See Lucr. 1.823–27, 2.688–99, 2.1013–22; further') == [
        ('lucretius.de_rerum_natura', '1.823', '1.827'),
        ('lucretius.de_rerum_natura', '2.688', '2.699'),
        ('lucretius.de_rerum_natura', '2.1013', '2.1022')]


def test_roman_book_after_an_arabic_chapter_starts_a_new_locus():
    assert _loci('Hdt. I 191, VIII 40, IX 60 are') == [
        ('herodotus.histories', '1.191'), ('herodotus.histories', '8.40'), ('herodotus.histories', '9.60')]


def test_comma_list_of_speeches_routes_each_item():
    assert _loci('Dem. 20.35, [49.52], 53.1 (a passage') == [
        ('demosthenes.against_leptines', '20.35'),
        ('demosthenes.against_timotheus', '49.52'),
        ('demosthenes.against_nicostratus', '53.1')]


def test_plautus_line_numbers_after_commas_are_separate_lines():
    assert _loci('Plaut. Mil. 146, 298 ; Hor. O. 3, 4, 76') == [
        ('plautus.miles_gloriosus', '146'), ('plautus.miles_gloriosus', '298')]
    assert _loci('Poen. 312, 365, 908') == [
        ('plautus.poenulus', '312'), ('plautus.poenulus', '365'), ('plautus.poenulus', '908')]


def test_plautus_act_scene_line_is_not_a_line_list():
    assert _loci('Plaut. Men. 1, 1, 26') == [('plautus.menaechmi', '1.1.26')]


def test_a_pronoun_after_a_line_is_no_level():
    assert _loci('In Aul. 538, I should follow the MSS') == [('plautus.aulularia', '538')]


def test_tight_comma_and_end_of_sentence_stay_levels():
    assert _loci('Fast. 1, 553. \n\n8 Other examples') == [('ovid.fasti', '1.553')]
    assert _loci('Il. 1,12-20') == [('homer.iliad', '1.12', '1.20')]


def test_four_numbers_joined_by_points_are_no_locus():
    # the comma rule does not turn an IP address into a second locus
    assert ('vergil.aeneid', '128.205.2.231') not in _loci('Serv. Dan. on Aen. 1.287, [128.205.2.231] Project')


def test_comma_list_item_with_points_is_not_joined_into_a_line():
    # "AJ 4.100, 9.7": chapter and verse of a work held by line, not the line 97
    assert ('sophocles.ajax', '97') not in _loci('AJ 4.100, 9.7, 14.54')


# --- 6. chapter and section --------------------------------------------------

@pytest.mark.parametrize('text,work,locus', [
    ('Cf. Cic. Verr. II 4, 52, 117 : est ita', 'cicero.in_verrem', '2.4.117'),
    ('apud Cic. de orat. 1, 52, 225 eripite', 'cicero.de_oratore', '1.225'),
    ('(Cic. Ac. 2, 40, 125 ne asciveris', 'cicero.academica', '2.125'),
    ('Cic. Cat. I 13, 31', 'cicero.in_catilinam', '1.31'),
    ('Balb. 28, 64', 'cicero.pro_balbo', '64'),
])
def test_cicero_chapter_level_is_dropped_for_the_corpus_section(text, work, locus):
    assert _loci(text) == [(work, locus)]


def test_section_that_is_smaller_than_the_chapter_is_left_alone():
    assert _loci('Cicero (Tusc. 3.26.13) to the Iliad.') == [('cicero.tusculanae_disputationes', '3.26.13')]


def test_third_level_that_is_not_a_number_is_left_alone():
    assert _loci('Cic. de Orat. 2, 89 vix')[0][1] == '2.89.4'


def test_letters_keep_the_letter_level():
    assert _loci('Cic. Att. 4, 3, 5') == [('cicero.letters_to_atticus', '4.3.5')]


def test_works_outside_the_section_list_keep_three_levels():
    assert _loci('Tac. Ann. 3. 53. 7') == [('tacitus.annales', '3.53.7')]


# --- 7. a locus after a closing parenthesis ---------------------------------

def test_locus_after_a_closing_parenthesis_and_comma_belongs_to_the_next_item():
    assert _hits('("Hippolytus," cf. Eur. Hipp.), 2.10 ("Cassandra," cf. Aesch. Ag.), 2.29') == []
    assert _loci('(cf. Eur. Hipp. 12), 2.10') == [('euripides.hippolytus', '12')]
