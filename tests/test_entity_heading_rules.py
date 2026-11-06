from backend import entity_heading_rules as hr


def test_accusative_folds_to_attested_nominative():
    forms = {'Childeberthi': 46, 'Childeberthum': 39, 'Childeberthus': 36, 'Childebertho': 16}
    rule, new, ev = hr.propose('Childeberthum', forms)
    assert (rule, new) == ('rule', 'Childeberthus')
    assert ev[0].startswith('Childeberthi')


def test_nominative_heading_is_left_alone():
    assert hr.propose('Gunthchramnus', {'Gunthchramnus': 5, 'Gunthchramnum': 141}) is None


def test_other_headings_are_asked():
    assert hr.propose('Latium', {'Latium': 9, 'Latio': 4})[:2] == ('ASK', None)
    assert hr.propose('Abrunculus', {'Abrunculus': 2}) is None


def test_sure_oblique_without_nominative_is_asked():
    rule, new, _ = hr.propose('Macedoniis', {'Macedoniis': 3, 'Macedoniorum': 2})
    assert (rule, new) == ('ASK', None)


def test_greek_accusative_folds():
    rule, new, _ = hr.propose('Ῥομπέρτον', {'Ῥομπέρτον': 50, 'Ῥομπέρτος': 20})
    assert (rule, new) == ('rule', 'Ῥομπέρτος')


def test_first_declension_accusative_folds_but_plural_ae_stays():
    rule, new, _ = hr.propose('Rusellam', {'Rusellam': 3, 'Rusella': 1})
    assert (rule, new) == ('rule', 'Rusella')
    assert hr.propose('Athenae', {'Athenae': 30, 'Athena': 2})[0] == 'ASK'


def test_heading_keeps_its_capital():
    assert hr.propose('Euboicum', {'Euboicum': 3, 'euboicus': 2})[1] == 'Euboicus'
