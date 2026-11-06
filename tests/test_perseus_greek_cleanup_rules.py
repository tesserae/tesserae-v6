"""The cleanup rules of scripts/corpus/perseus_greek_tei_to_tess.py (2026-10-25), on lines taken from the Greek tranche."""
import importlib.util
import os

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'scripts', 'corpus', 'perseus_greek_tei_to_tess.py')
spec = importlib.util.spec_from_file_location('perseus_greek_tei_to_tess', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
R = mod.RULES


def test_every_rule_in_the_tranche_script_exists():
    tranche = os.path.join(os.path.dirname(SCRIPT), 'grc_tranche_2026-10-24_convert.py')
    s = importlib.util.spec_from_file_location('tranche', tranche)
    t = importlib.util.module_from_spec(s)
    s.loader.exec_module(t)
    for stem, names in t.RULES_FOR.items():
        for n in names.split(','):
            assert n in R, (stem, n)


def test_edition_numbers_strips_section_and_verse_numbers():
    f = R['edition_numbers']
    assert f('81, Ἐπειδὴ δὲ ἐπάγει') == 'Ἐπειδὴ δὲ ἐπάγει'
    assert f('3Καὶ περὶ τῶν') == 'Καὶ περὶ τῶν'
    assert f('⁵ ὅτι αὐτοὶ') == 'ὅτι αὐτοὶ'
    assert ' '.join(f('χρόνον ὅτι (1.) ἦν ποτε').split()) == 'χρόνον ὅτι ἦν ποτε'
    assert f('ἀνομίας;6 Ὁ μὲν') == 'ἀνομίας; Ὁ μὲν'
    assert f('Ἕλληνας2καὶ ὥσπερ') == 'Ἕλληνας καὶ ὥσπερ'
    assert f('κακὸς δ᾿ ὑπὸ νείατα πνιχμὸς 190') == 'κακὸς δ᾿ ὑπὸ νείατα πνιχμὸς'
    assert f('Mt. 7, 21Μὴ μόνον') == 'Μὴ μόνον'


def test_edition_numbers_leaves_greek_alone():
    f = R['edition_numbers']
    for t in ('Ἐν ἀρχῇ ἦν ὁ λόγος', 'τοῦ ΔΙΟΣ ΤΑ περὶ', 'ΧΧ ἔτη'):
        assert f(t) == t or f(t) == 'ἔτη'


def test_origen_lemma_references_and_entity_residue():
    f = R['origen_john']
    assert f('εἶπεν. VIII, 20. Ταῦτα τὰ ῥήματα').split() == ['εἶπεν.', 'Ταῦτα', 'τὰ', 'ῥήματα']
    assert 'x003E' not in f('ἐὰν ἀναλεγώμεθα x003E; τὰς λοιπὰς')
    assert f('μείζονας 114r καὶ τελειο').split() == ['μείζονας', 'καὶ', 'τελειο']


def test_apparatus_runs_drops_sigla_and_numbers_but_keeps_greek():
    f = R['apparatus_runs_rule']
    assert f('τῆς Phot. ἱερὰν ἀνειπόντος') == 'τῆς ἱερὰν ἀνειπόντος'
    assert f('ἀφανές Ebd. 45 : Ὅτι δὲ') == 'ἀφανές Ὅτι δὲ'
    assert f('ἐκεῖ (näml. ὁ Ἀέτιος) καὶ') == 'ἐκεῖ καὶ'
    assert f('κωλύε 5>ἰδίας ἀπάτης') == 'κωλύε ἰδίας ἀπάτης'


def test_a_long_naml_stretch_keeps_its_text():
    text = '(näml. ' + 'λόγος ' * 20 + 'καὶ Ebd. 51: τέλος)'
    assert 'λόγος' in R['apparatus_runs_rule'](text)


def test_anna_comnena_margin_marks_and_headings():
    f = R['anna_comnena']
    assert f('τῶν V. 7 σκήπτρων ΑΛΕΞΙΑΣ λείᾳ') == 'τῶν σκήπτρων λείᾳ'
    assert f('τῶν C κροτάφων ὁρμαθοί') == 'τῶν κροτάφων ὁρμαθοί'
    assert f('ARGUMENTUM. ααα') == 'ARGUMENTUM. ααα'          # heading lines stay: removing them would change references


def test_stray_angle_marks_only_without_a_pair():
    f = R['stray_angle_marks']
    assert f('Ἀλέξανδρος >ἐν κυρίῳ χαίρειν.') == 'Ἀλέξανδρος  ἐν κυρίῳ χαίρειν.'
    assert f('ἀνα>κείμενος στρατὸς') == 'ἀνακείμενος στρατὸς'
    assert f('οἱ προφῆται >λόγοι< πιστεύονται') == 'οἱ προφῆται >λόγοι< πιστεύονται'


def test_a_rule_never_empties_a_line_of_its_greek():
    mod.ACTIVE_RULES[:] = ['edition_numbers']
    try:
        assert mod.GREEK.search(mod.clean(['12 Ἐν ἀρχῇ']))
        assert mod.clean(['77']) == '77'      # no Greek in, nothing to protect, text unchanged by the guard
    finally:
        mod.ACTIVE_RULES[:] = []
