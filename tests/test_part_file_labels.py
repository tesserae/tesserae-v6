"""Part files carrying a label after their number are titled by the label
(#565, and the Vulgate and English Bible rows of #564)."""
from backend.utils import format_part_label, get_text_metadata


def test_labels_read_as_readers_know_them():
    assert format_part_label('books_21-30') == 'Books 21-30'
    assert format_part_label('book_6-10') == 'Books 6-10'
    assert format_part_label('1_chronicles') == '1 Chronicles'
    assert format_part_label('vespasian') == 'Vespasian'
    assert format_part_label('ad_lentulum') == 'Ad Lentulum'
    assert format_part_label('against_the_stepmother_for_poisoning') == 'Against the Stepmother for Poisoning'
    assert format_part_label('91-100') == '91-100'
    assert format_part_label('preface') == 'Preface'


def test_titles_use_the_label_and_keep_the_bare_number_otherwise():
    assert get_text_metadata('livy.ab_urbe_condita.part.2.books_21-30.tess')['title'] == 'Ab Urbe Condita, Books 21-30'
    assert get_text_metadata('jerome.vulgate.part.12.1_chronicles.tess')['title'] == 'Vulgate, 1 Chronicles'
    assert get_text_metadata('pliny_the_elder.naturalis_historia.part.0.preface.tess')['title'] == 'Naturalis Historia, Preface'
    assert get_text_metadata('vergil.aeneid.part.2.tess')['title'].endswith('Book 2')
