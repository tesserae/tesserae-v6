"""Characterization tests for backend/metrical_scanner.py.

Expected values come from running the current code and reading each one.

The MQDQ scansion table (data/scansion/mqdq_scansions.json) is not in CI, so
lookup tests put a small table of their own in its place. The verse scanner
needs no data file: it is the copy of the CLTK scanners kept in
backend/prosody_lat, and it gives the same answer on every run (checked by
running each line twice), so the tests below call it for real. If neither
CLTK nor the copy imports, those tests are skipped.
"""
import pytest

import backend.utils as utils
from backend import metrical_scanner as ms


@pytest.fixture(autouse=True)
def no_text_files(monkeypatch):
    # is_prose_text reads the text file if the name decides nothing; keep it name-only.
    monkeypatch.setattr(utils, '_resolve_text_filepath', lambda *a, **k: None)


@pytest.fixture
def table(monkeypatch):
    """A three-entry stand-in for the MQDQ table."""
    t = {
        'vergilius.Aeneis': {'lines': {
            '1.1': {'meter': 'H', 'pattern': 'SDSS', 'scansion': 'ignored'},
            '1.2': {'meter': 'H', 'pattern': '', 'scansion': '-uu-uu-uu-uu-uu-x'},   # no pattern code
            '1.3': {'meter': 'H', 'pattern': '', 'scansion': ''},                    # nothing usable
        }},
        'martialis.epigrammata_9': {'lines': {
            '84.10': {'meter': 'E', 'pattern': 'U-U-U-U-U-U'},
        }},
        'ouidius.amores_1': {'lines': {
            '1.1': {'meter': 'H', 'pattern': 'DSDS'},
            '1.2': {'meter': 'P', 'pattern': 'D|SD'},
        }},
    }
    monkeypatch.setattr(ms, '_mqdq_scansions', t)
    return t


# ---- expand_mqdq_pattern ---------------------------------------------------

@pytest.mark.parametrize('code,meter,expected', [
    ('DDDD', 'H', '–∪∪–∪∪–∪∪–∪∪–∪∪–×'),    # four dactyls, then the fifth foot and adonic end are added
    ('SSSS', 'H', '–––––––––∪∪–×'),       # four spondees (8 marks) + dactyl + anceps
    ('DS', 'H', '–∪∪–––∪∪–×'),            # short code: completed the same way
    ('D|SD', 'P', '–∪∪|–––∪∪'),           # pentameter: caesura bar kept, nothing added
    ('U-ux=', 'X', '∪–∪×–'),              # every letter code in one string
    ('DSDS', 'X', '–∪∪–––∪∪––'),          # other meters get no completion
    ('DDDDDD', 'H', '–∪∪–∪∪–∪∪–∪∪–∪∪–∪∪×'),   # long code: only a final anceps added
    ('xyz', 'H', None),                   # 'y' and 'z' are not codes: no pattern, so the caller uses the stored scansion
    ('DDQDDD', 'H', None),                # one unknown letter among known ones: no pattern, never a shortened one
    ('not scanned', 'H', None),           # the text the database holds for 205 unscanned lines
    ('D S', 'P', '–∪∪––'),                # spaces are ignored
    ('   ', 'H', None),
    ('', 'H', None),
    (None, 'H', None),
])
def test_expand_mqdq_pattern(code, meter, expected):
    assert ms.expand_mqdq_pattern(code, meter) == expected


# ---- calculate_metrical_similarity -----------------------------------------

@pytest.mark.parametrize('a,b,expected', [
    ('-uu-uu', '-uu-uu', 1.0),                    # identical
    ('-uu-uu', '-uu--u', 5 / 6),                  # one syllable different
    ('-uu-uu', '-uu', 0.5),                       # all of the short one matches, half the length
    ('- u u', '-UU', 1.0),                        # spaces ignored, case ignored
    ('-----', 'uuuuu', 0.0),                      # nothing in common
    ('', '-uu', 0.0),
    ('-uu', None, 0.0),
    ('   ', '-uu', 0.0),                          # only spaces
])
def test_calculate_metrical_similarity(a, b, expected):
    assert ms.calculate_metrical_similarity(a, b) == pytest.approx(expected)


# ---- display formatting ----------------------------------------------------

def test_format_scansion_for_display():
    assert ms.format_scansion_for_display('-uu-uu') == '– ∪ ∪ – ∪ ∪'
    assert ms.format_scansion_for_display('-UU-U') == '– ∪ ∪ – ∪'      # upper case accepted
    assert ms.format_scansion_for_display('-x-x-') == '–   –   –'      # other marks become blanks
    assert ms.format_scansion_for_display('-uu') is None                # under five marks: not shown
    assert ms.format_scansion_for_display('') is None
    assert ms.format_scansion_for_display(None) is None


def test_format_scansion_display():
    assert ms.format_scansion_display('arma', '-uu x') == {
        'text': 'arma', 'scansion': '–∪∪  ', 'pattern': '-uu x'}      # lower or upper u both give a breve
    assert ms.format_scansion_display('arma', '-U') ['scansion'] == '–∪'
    assert ms.format_scansion_display('arma', '') == 'arma'           # no pattern: the text back unchanged
    assert ms.format_scansion_display('arma', None) == 'arma'


# ---- prose and meter detection ---------------------------------------------

@pytest.mark.parametrize('text_id,prose', [
    ('cicero.in_catilinam.tess', True),
    ('vergil.aeneid.tess', False),
    ('ovid.amores.tess', False),
])
def test_is_prose_text(text_id, prose):
    assert ms.is_prose_text(text_id) is prose


def test_is_suitable_for_meter():
    assert ms.is_suitable_for_meter('vergil.aeneid.tess', 'ovid.amores.tess') is True
    assert ms.is_suitable_for_meter('vergil.aeneid.tess', 'cicero.in_catilinam.tess') is False   # prose target
    assert ms.is_suitable_for_meter('vergil.aeneid.tess', 'ovid.amores.tess', 'grc') is False    # Latin only


@pytest.mark.parametrize('text_id,meter', [
    ('vergil.aeneid.tess', 'hexameter'),
    ('verg. aen.', 'hexameter'),
    ('ovid.metamorphoses', 'hexameter'),
    ('ovid.amores', 'elegiac'),
    ('tibullus.elegies', 'elegiac'),
    ('catullus.carmina', 'hendecasyllable'),
    ('martial.epigrams', 'hendecasyllable'),
    ('statius.silvae', 'hendecasyllable'),
    ('statius.thebaid', 'hexameter'),
    ('cicero.in_catilinam.tess', 'hexameter'),   # prose gets the default too; callers check prose first
    ('unknown.work', 'hexameter'),               # default
    ('VERGIL.Aeneid', 'hexameter'),              # case ignored
])
def test_detect_meter_type(text_id, meter):
    assert ms.detect_meter_type(text_id) == meter


# ---- scan_latin_verse (real scanner, no data file) -------------------------

needs_scanner = pytest.mark.skipif(not ms._CLTK_AVAILABLE, reason='no Latin scanner importable')


@needs_scanner
def test_scan_aeneid_first_line_with_macrons():
    line = 'Arma virumque cano, Troiae qui primus ab oris'
    first = ms.scan_latin_verse(line, 'hexameter')
    # Until 2026-10-13 this line did not scan: without vowel lengths two
    # syllables (qui, pri) were unknown and two patterns fitted. The macron
    # table gives "quī prīmus ab ōrīs" and the scanner finds DDSS, the
    # pattern MQDQ records for Aeneid 1.1.
    assert first == {'pattern': '-uu-uu-----uu--', 'raw': '– ∪ ∪ – ∪ ∪ – – – – – ∪ ∪ – –',
                     'valid': True, 'meter': 'hexameter'}
    assert ms.scan_latin_verse(line, 'hexameter') == first          # same answer twice (cached)
    assert ms._SCAN_CACHE[(line, 'hexameter')] == first


def test_macronize_latin_keeps_case_punctuation_and_unknown_words():
    assert ms.macronize_latin('Arma virumque cano, Troiae qui primus ab oris') == \
        'Arma virumque canō, Trōiae quī prīmus ab ōrīs'
    assert ms.macronize_latin('xyzzy, 123') == 'xyzzy, 123'        # not in the table: unchanged
    assert ms.macronize_latin('') == ''


def test_macronize_latin_without_table_returns_text(monkeypatch):
    monkeypatch.setattr(ms, '_macrons', None)
    monkeypatch.setattr(ms, '_MACRONS_PATH', '/nonexistent/latin_macrons.json')
    assert ms.macronize_latin('Arma virumque cano') == 'Arma virumque cano'
    assert ms.get_macrons() == {}


@needs_scanner
def test_scan_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(ms, '_SCAN_CACHE', {})
    monkeypatch.setattr(ms, '_SCAN_CACHE_MAX', 2)
    for line in ('Arma virumque cano, Troiae qui primus ab oris',
                 'Italiam, fato profugus, Laviniaque venit',
                 'litora, multum ille et terris iactatus et alto'):
        ms.scan_latin_verse(line, 'hexameter')
    assert len(ms._SCAN_CACHE) == 1                                  # cleared at the cap, then refilled


def test_vendored_hexameter_scanner_optional_transform_does_not_recurse():
    from backend.prosody_lat.hexameter_scanner import HexameterScanner
    verse = HexameterScanner(optional_transform=True).scan('Italiam, fato profugus, Laviniaque venit')
    assert verse.valid in (True, False)                              # returned, no RecursionError


@needs_scanner
def test_scan_valid_hendecasyllable_and_pentameter():
    h = ms.scan_latin_verse('Cui dono lepidum novum libellum', 'hendecasyllable')
    # With the macron table 'dōnō' is read long-long, the spondaic base of
    # Catullus 1.1; before 2026-10-13 the second syllable came out short.
    assert h['valid'] is True and h['pattern'] == '---uu-u-u-u' and len(h['pattern']) == 11   # eleven syllables
    assert h['raw'] == '– – – ∪ ∪ – ∪ – ∪ – ∪' and h['meter'] == 'hendecasyllable'
    p = ms.scan_latin_verse('Nec nos exiguae, quis mea cura, deae', 'elegiac')
    assert p['valid'] is True and p['meter'] == 'elegiac' and p['pattern'] == '------uu-uu-'


@needs_scanner
def test_scan_line_that_cannot_scan_and_empty():
    assert ms.scan_latin_verse('xyz qrs', 'hexameter') is None
    assert ms.scan_latin_verse('', 'hexameter') is None


def test_scan_without_scanner_warns_once(monkeypatch, caplog):
    monkeypatch.setattr(ms, 'get_hexameter_scanner', lambda: None)
    monkeypatch.setattr(ms, '_MISSING_SCANNER_NOTED', set())
    assert ms.scan_latin_verse('Arma virumque cano', 'hexameter') is None
    assert ms.scan_latin_verse('Arma virumque cano', 'hexameter') is None
    assert ms._MISSING_SCANNER_NOTED == {'hexameter'}      # recorded once, so logged once


def test_scan_survives_a_scanner_error(monkeypatch):
    class Boom:
        def scan(self, text):
            raise RuntimeError('bad')

    monkeypatch.setattr(ms, 'get_pentameter_scanner', lambda: Boom())
    assert ms.scan_latin_verse('x', 'elegiac') is None


def test_scan_with_stub_scanner_normalises_result(monkeypatch):
    class R:
        scansion = ' -uu -U- uu- '
        valid = True

    class S:
        def scan(self, text):
            return R()

    monkeypatch.setattr(ms, 'get_hendecasyllable_scanner', lambda: S())
    out = ms.scan_latin_verse('x', 'hendecasyllable')
    assert out['pattern'] == '-uu-u-uu-'     # spaces removed, U lowered
    assert out['valid'] is True and out['raw'] == '– ∪ ∪ – ∪ – ∪ ∪ –'


# ---- lookup_mqdq_scansion with the stand-in table --------------------------

def test_lookup_vergil_expands_pattern(table):
    out = ms.lookup_mqdq_scansion('<verg. aen. 1.1>')
    # SDSS = spondee, dactyl, spondee, spondee, then the fifth foot and ending
    assert out['pattern'] == '––' '–∪∪' '––' '––' '–∪∪–×'
    assert out['source'] == 'mqdq' and out['valid'] is True and out['meter'] == 'hexameter'
    assert out['raw'] == ' '.join(out['pattern'])
    assert ms.lookup_mqdq_scansion('vergilius.Aeneis.1.1') == out    # long form gives the same entry


def test_lookup_falls_back_to_stored_scansion(table):
    out = ms.lookup_mqdq_scansion('verg. aen. 1.2')
    assert out['pattern'] == '-uu-uu-uu-uu-uu-x' and out['meter'] == 'hexameter'


def test_lookup_misses(table):
    assert ms.lookup_mqdq_scansion('verg. aen. 1.3') is None     # entry with no data
    assert ms.lookup_mqdq_scansion('verg. aen. 9.9') is None     # line not in table
    assert ms.lookup_mqdq_scansion('verg. georg. 1.1') is None   # work not in table
    assert ms.lookup_mqdq_scansion('verg. 1') is None            # too few parts


def test_lookup_martial_book_poem_line(table):
    short = ms.lookup_mqdq_scansion('mart. 9.84.10')
    assert short['meter'] == 'hendecasyllable' and short['pattern'] == '∪–∪–∪–∪–∪–∪'    # eleven marks
    assert ms.lookup_mqdq_scansion('martial.epigrams.9.84.10') == short    # form from the feature extractor
    assert ms.lookup_mqdq_scansion('mart. 9.99.1') is None
    assert ms.lookup_mqdq_scansion('mart. epigrams') is None


def test_lookup_ovid_amores_book_specific(table):
    hexa = ms.lookup_mqdq_scansion('ov. am. 1.1.1')
    assert hexa['meter'] == 'hexameter' and hexa['pattern'].startswith('–∪∪')
    pent = ms.lookup_mqdq_scansion('ov. am. 1.1.2')
    assert pent['meter'] == 'pentameter' and pent['pattern'] == '–∪∪–––∪∪'   # caesura bar removed
    assert ms.lookup_mqdq_scansion('ov. am. 2.1.1') is None                  # book 2 not in table


def test_lookup_with_empty_table(monkeypatch):
    monkeypatch.setattr(ms, '_mqdq_scansions', {})
    assert ms.lookup_mqdq_scansion('verg. aen. 1.1') is None


# ---- get_scansion_for_line -------------------------------------------------

def test_get_scansion_prefers_mqdq(table):
    out = ms.get_scansion_for_line('verg. aen.', '1.1', 'Arma virumque cano')
    assert out['source'] == 'mqdq'


def test_get_scansion_falls_back_to_scanner(table, monkeypatch):
    seen = []
    monkeypatch.setattr(ms, 'scan_latin_verse', lambda text, meter: seen.append((text, meter)) or {'stub': 1})
    assert ms.get_scansion_for_line('catullus.carmina', '1.1', 'Cui dono') == {'stub': 1}
    assert seen == [('Cui dono', 'hendecasyllable')]       # meter chosen from the text id


def test_get_scansion_without_text_and_no_mqdq_hit(table):
    assert ms.get_scansion_for_line('catullus.carmina', '1.1') is None
