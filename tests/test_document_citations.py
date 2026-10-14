"""Document-citation recogniser (backend/document_citations.py): inscriptions,
papyri, ostraca and coins in scholarly prose. Strings are real ones from the
documents collection's apparatus and commentary notes, the literary
commentaries (data/commentaries) and the historians notes, plus the spellings
the task lists. Needs no data files, so it runs in CI.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend import citations as C  # noqa: E402
from backend.document_citations import (  # noqa: E402
    DocumentEditionIndex, find_document_citations, link_documents)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

POSITIVES = [
    # CIL
    ('CIL VI 1234', 'CIL:CIL:6:1234:'),
    ('CIL 6.1234', 'CIL:CIL:6:1234:'),
    ('C.I.L. VI, 1234', 'CIL:CIL:6:1234:'),
    ('C. I. L. 4.1261', 'CIL:CIL:4:1261:'),
    ('CIL 03, 11305', 'CIL:CIL:3:11305:'),
    ('CIL 13, 07465a', 'CIL:CIL:13:7465:a'),
    ('CIL, VI 38880', 'CIL:CIL:6:38880:'),
    ('CIL I² 207', 'CIL:CIL:1^2:207:'),
    ('CIL II (2. Aufl.) 5, 73', 'CIL:CIL:2.5^2:73:'),
    ('CIL III 14206, 3', 'CIL:CIL:3:14206:'),
    ('CIL 10.7347', 'CIL:CIL:10:7347:'),
    # ILS, AE
    ('ILS 6011', 'ILS:ILS::6011:'),
    ('I.L.S. 8903', 'ILS:ILS::8903:'),
    ('AE 1976, 123', 'AE:AE:1976:123:'),
    ('AE 1976.123', 'AE:AE:1976:123:'),
    ('AE 1975, 0422d', 'AE:AE:1975:422:d'),
    ('AE 1969/70, 99', 'AE:AE:1969/70:99:'),
    ("L'Année épigraphique 1976, 123", 'AE:AE:1976:123:'),
    # IG
    ('IG II² 1234', 'IG:IG:2^2:1234:'),
    ('IG XII 5, 123', 'IG:IG:12.5:123:'),
    ('IG I³ 40', 'IG:IG:1^3:40:'),
    ('IG 14.556', 'IG:IG:14:556:'),
    ('IG 14, 00952', 'IG:IG:14:952:'),
    ('IG XIV 530b', 'IG:IG:14:530:b'),
    ('IG 9/1 879', 'IG:IG:9.1:879:'),
    # SEG, ILLRP, CLE, RIB
    ('SEG 33.1234', 'SEG:SEG:33:1234:'),
    ('SEG XXXIII 1234', 'SEG:SEG:33:1234:'),
    ('SEG 37.0385', 'SEG:SEG:37:385:'),
    ('ILLRP 801', 'ILLRP:ILLRP::801:'),
    ('CLE 1786', 'CLE:CLE::1786:'),
    ('RIB 1555', 'RIB:RIB::1555:'),
    ('RIB I 1234', 'RIB:RIB:1:1234:'),
    ('RIB 2441.12', 'RIB:RIB::2441:12'),
    # old Greek corpora
    ('C. I. G. 1877', 'CIG:CIG::1877:'),
    ('CIG III 5652', 'CIG:CIG:3:5652:'),
    ('Dittenberger Syll. 589', 'SIG:SIG::589:'),
    # papyri and ostraca
    ('P.Oxy. XII 1453', 'PAP:P.Oxy:12:1453:'),
    ('P. Oxy. 1453', 'PAP:P.Oxy::1453:'),
    ('P.Oxy 12.1453', 'PAP:P.Oxy:12:1453:'),
    ('P.Oxy. 79 5202', 'PAP:P.Oxy:79:5202:'),
    ('BGU IV 1050', 'PAP:BGU:4:1050:'),
    ('BGU 4.1050', 'PAP:BGU:4:1050:'),
    ('P.Mich. III 183', 'PAP:P.Mich:3:183:'),
    ('P.Tebt. IV 1109', 'PAP:P.Tebt:4:1109:'),
    ('SB XVI 13060', 'PAP:SB:16:13060:'),
    ('SB 16.13060', 'PAP:SB:16:13060:'),
    ('PSI I23', 'PAP:PSI:1:23:'),
    ('CPR XVIIB 10', 'PAP:CPR:17:10:'),
    ('P.Cair.Masp. 1 67007', 'PAP:P.Cair.Masp:1:67007:'),
    ('O.Claud. I 123', 'PAP:O.Claud:1:123:'),
    ('O.Wilck. 1277', 'PAP:O.Wilck::1277:'),
    ('T.Vindol. II 343', 'PAP:T.Vindol:2:343:'),
    # coins
    ('RIC I² 207', 'RIC:RIC:1^2:207:'),
    ('RIC II 123', 'RIC:RIC:2:123:'),
    ('RIC IV.1 123', 'RIC:RIC:4.1:123:'),
    ('RRC 335/1', 'RRC:RRC::335:1'),
    ('Crawford, RRC no.216', 'RRC:RRC::216:'),
    ('BMCRE I 123', 'BMC:BMCRE:1:123:'),
    ('BMCRE II p. 12 no. 55', 'BMC:BMCRE:2:55:'),
    ('RPC I 1234', 'RPC:RPC:1:1234:'),
    ('RPC 1.670', 'RPC:RPC:1:670:'),
]

NEGATIVES = [
    'AD 1976, 123',                       # a date, not AE
    'In 1976, 123 men were counted',
    'pp. 1234-45',
    'see pp. 123-145 and 200',
    'the RIC of the northern provinces',  # RIC as a word
    'RIC the king',
    'SB 12',                              # SB as an abbreviation
    'He was sb. 12 years old',
    'IGNORE 5 of them',                   # IG inside a word
    'DIGITAL 1234',
    'AE 1976',                            # year alone is not an item
    'AE 1979: Z. 3: [---]G',
    'CIL VI',                             # volume alone
    'CIL III; ILS: Z. 6',
    'CIL X, p. 772',                      # a page, not an inscription
    'CIL 11, p. 1353',
    'SEG 30: πολῖται',                    # volume alone
    'P. Vergilius Maro 70',               # praenomen, not a papyrus series
    'P. Cornelius Scipio 205',
    'cp. O.T. 829 n.',                    # Sophocles, not an ostracon
    'Soph. O.C. 1620 and P.V. 348',
    'Milton, P.L. 2. 579',
    'O. Henry 1850',
    'BGU XX, S. 998',                     # a page of a volume
    'SPP III2.5, S. 192',
    'P.Heid. VIII, S. 178, Anm. 13',
    'ChLA VI, S. 93',
    'CLE 2.7257',                         # not a well-formed CLE number
    'D. J. Crawford 1974',
    'Crawford, Dollings, Lundqvist, Thayer',
    'SB 1976',                            # a year
    'RPC online',
    'BMCRE I p. 12',
    'IG XIV in volume',
    'ILS',
    'the CLE',
]


@pytest.mark.parametrize('text,key', POSITIVES)
def test_positive(text, key):
    hits = find_document_citations('see ' + text + ' for this')
    assert [h['key'] for h in hits] == [key], hits


def test_at_least_forty_positive_and_twenty_negative_cases():
    assert len(POSITIVES) >= 40 and len(NEGATIVES) >= 20


@pytest.mark.parametrize('text', NEGATIVES)
def test_negative(text):
    assert find_document_citations(text) == []


def test_several_references_in_one_sentence():
    text = 'Compare CIL XI 3200 = ILS 89 and AE 1984, 272; also P.Oxy. III 496 (RIC II 123).'
    assert [h['key'] for h in find_document_citations(text)] == [
        'CIL:CIL:11:3200:', 'ILS:ILS::89:', 'AE:AE:1984:272:', 'PAP:P.Oxy:3:496:', 'RIC:RIC:2:123:']


def test_offsets_index_the_original_text():
    text = 'ΙG XIV 558 and CIL VI 1234'    # Greek capital Iota, no-break space
    hits = find_document_citations(text)
    assert [h['key'] for h in hits] == ['IG:IG:14:558:', 'CIL:CIL:6:1234:']
    assert text[hits[0]['start']:hits[0]['end']] == 'ΙG XIV 558'


def test_range_is_captured():
    h = find_document_citations('RIB 1234-1236')[0]
    assert (h['number'], h['number_end']) == (1234, 1236)


# ------------------------------------------------------------------ linking
ROWS = [
    ('edh:HD1', 'edh', 'CIL 06, 01234.'),
    ('edr:A1', 'edr', 'CIL 06, 01234 (1)'),
    ('edh:HD2', 'edh', 'AE 1975, 0422a.'),
    ('edh:HD3', 'edh', 'AE 1975, 0422b.'),
    ('edh:HD4', 'edh', 'AE 1976, 0123.'),
    ('papyri:1', 'papyri', 'P.Oxy. 12 1453'),
    ('papyri:2', 'papyri', 'P.Mich. 3 183'),
    ('papyri:3', 'papyri', 'P.Mich. 5 183'),
    ('edr:A2', 'edr', 'IG 14, 1005 (1)'),
    ('isicily:1', 'isicily', 'CIL 7190'),
    ('edh:HD5', 'edh', 'R. Frei-Stolba, Holzfässer. Studien (Zürich 2017) 179, Nr. 49.'),
    ('edr:A3', 'edr', 'CIL 02 (2. Aufl.) 05, 00535'),
]


@pytest.fixture(scope='module')
def idx():
    return DocumentEditionIndex.from_rows(ROWS)


def _link(idx, text):
    return [h['doc_ids'] for h in link_documents(find_document_citations(text), idx)]


def test_link_exact_and_across_sources(idx):
    assert _link(idx, 'CIL VI 1234') == [['edh:HD1', 'edr:A1']]


def test_link_year_number_ignores_zero_padding(idx):
    assert _link(idx, 'AE 1976, 123') == [['edh:HD4']]


def test_link_without_sub_letter_matches_every_lettered_doc(idx):
    assert _link(idx, 'AE 1975, 422') == [['edh:HD2', 'edh:HD3']]
    assert _link(idx, 'AE 1975, 422b') == [['edh:HD3']]


def test_link_papyrus_needs_the_volume_when_numbers_repeat(idx):
    assert _link(idx, 'P.Oxy. XII 1453') == [['papyri:1']]
    assert _link(idx, 'P.Oxy. 1453') == [['papyri:1']]          # one volume holds 1453
    assert _link(idx, 'P.Mich. 183') == [[]]                     # ambiguous: vols 3 and 5
    assert _link(idx, 'P.Mich. III 183') == [['papyri:2']]


def test_link_sicily_volume_is_inferred(idx):
    assert _link(idx, 'CIL X 7190') == [['isicily:1']]


def test_link_edition_marker_must_agree(idx):
    assert _link(idx, 'CIL II² 5, 535') == [['edr:A3']]
    assert _link(idx, 'CIL II 535') == [[]]


def test_link_unknown_is_empty(idx):
    assert _link(idx, 'CIL VI 9999') == [[]]


def test_edition_strings_that_are_not_references_are_skipped(idx):
    assert 'edh:HD5' not in {d for ds in idx.by_num.values() for es in ds.values() for d, _, _ in es}


# ------------------------------------------------------------------ integration
def test_extract_documents_entry_point(idx):
    hits = C.extract_documents('cf. CIL VI 1234', idx)
    assert hits[0]['doc_ids'] == ['edh:HD1', 'edr:A1']
    assert C.extract_documents('cf. CIL VI 1234')[0].get('doc_ids') is None


@pytest.mark.skipif(C.index() is None, reason='needs data/citations/abbreviations.json')
def test_literary_extraction_is_unchanged_by_document_citations():
    text = 'Verg. Aen. 1.1; Il. 1.1-7; CIL VI 1234'
    lit = [(h['surface'], h['work_id'], h['locus_start']) for h in C.extract(text) if h['resolved']]
    assert ('Verg. Aen. 1.1', 'vergil.aeneid', '1.1') in lit
    # extract() is untouched, so it still reads "CIL VI 1234" as Iliad 6.1234 ...
    assert any(s.startswith('CIL') for s, _, _ in lit)
    # ... and extract_all() is the call that removes that clash.
    both = C.extract_all(text)
    assert [h['surface'] for h in both['literary']] == ['Verg. Aen. 1.1', 'Il. 1.1-7']
    assert [h['key'] for h in both['documents']] == ['CIL:CIL:6:1234:']


# ------------------------------------------------------------------ measured sample
@pytest.mark.parametrize('name', ['doc_citations_sample200.json', 'doc_citations_heldout.json'])
def test_precision_and_recall_on_hand_labelled_windows(name):
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'documents'))
    from eval_doc_citations import evaluate
    res = evaluate(os.path.join(ROOT, 'tests', 'fixtures', name))
    assert res['precision'] >= 0.95, res
    assert res['recall'] >= 0.95, res
