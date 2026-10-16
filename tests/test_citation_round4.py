"""Citation recognizer, round 4: the orators' speech numbers, Pindar,
Theocritus, Bacchylides and the Libanius tie. Each string is a constructed
citation in the shape the Project MUSE audit counted (no article text).

The new forms live in data/citations/abbrev_patch_round4.json, which the lead
applies to the production table. These tests apply the patch to a COPY of the
table (scripts/citations/apply_abbrev_patch.py, in a temporary folder) and
extract against that copy, like tests/test_citation_round3.py. The speech
numbers are in backend/citations/speech_numbers.json, the author-context
choices and defaults in backend/citations/abbrev_context_rules.json, and the
Libanius tie is resolved in backend/citations/resolver.py.

Needs data/citations/abbreviations.json (not in the repository or CI), so the
module is skipped without it.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

from backend import citations as C
from backend.citations.abbrev_index import AbbrevIndex
from backend.citations.extractor import extract

pytestmark = pytest.mark.skipif(
    C.index() is None,
    reason='needs data/citations/abbreviations.json, not shipped (GPL-3.0 source data)')

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCH = os.path.join(REPO, 'data', 'citations', 'abbrev_patch_round4.json')
SCRIPT = os.path.join(REPO, 'scripts', 'citations', 'apply_abbrev_patch.py')
SPEECHES = os.path.join(REPO, 'backend', 'citations', 'speech_numbers.json')
CORPUS = os.path.join(REPO, 'texts', 'grc')


def _run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)


@pytest.fixture(scope='module')
def patched_table(tmp_path_factory):
    table = str(tmp_path_factory.mktemp('round4') / 'abbreviations.json')
    shutil.copyfile(os.path.realpath(C._DATA), table)
    done = _run(PATCH, table, '--apply')
    assert done.returncode == 0, done.stdout + done.stderr
    return table


@pytest.fixture(scope='module')
def idx(patched_table):
    return AbbrevIndex(patched_table)


def _hits(idx, text, context=''):
    return [(h['part_id'] or h['work_id'], h['locus_start'])
            for h in extract(text, idx, context) if h['resolved']]


def _one(idx, text, context=''):
    hits = _hits(idx, text, context)
    assert len(hits) == 1, (text, hits)
    return hits[0]


# ---- the orators: the speech number chooses the file ---------------------

@pytest.mark.parametrize('text, expected', [
    ('Dem. 21.72', ('demosthenes.against_midias', '21.72')),
    ('Dem. 18.72', ('demosthenes.on_the_crown', '18.72')),
    ('Dem. 1.5', ('demosthenes.olynthiac_1', '1.5')),
    ('Dem. 9.36', ('demosthenes.philippic_3', '9.36')),
    ('Dem. 4.10', ('demosthenes.philippic_1', '4.10')),
    ('Dem. 30.2', ('demosthenes.against_onetor_30', '30.2')),
    ('Dem. 59.18', ('demosthenes.against_neaera', '59.18')),
    ('Dem. 61.3', ('demosthenes.erotic_essay', '61.3')),
    ('Dem. xxi. 72', ('demosthenes.against_midias', '21.72')),
    ('Aeschin. 1.5', ('aeschines.against_timarchus', '1.5')),
    ('Aeschin. 2.87', ('aeschines.on_the_embassy', '2.87')),
    ('Aeschin. 3.41', ('aeschines.against_ctesiphon', '3.41')),
    ('Andoc. 1.133', ('andocides.on_the_mysteries', '1.133')),
    ('Andoc. 2.5', ('andocides.on_his_return', '2.5')),
    ('Andoc. 3.38', ('andocides.on_the_peace', '3.38')),
    ('Andoc. 4.13', ('andocides.against_alcibiades', '4.13')),
    ('Din. 1.23', ('dinarchus.against_demosthenes', '1.23')),
    ('Din. 2.4', ('dinarchus.against_aristogiton', '2.4')),
    ('Din. 3.1', ('dinarchus.against_philocles', '3.1')),
    ('Lycurg. 1.100', ('lycurgus.against_leocrates', '1.100')),
    ('Lys. 12.4', ('lysias.speeches', '12.4')),
    ('Lys. 30.17', ('lysias.speeches', '30.17')),
    ('Isoc. 4.1', ('isocrates.speeches', '4.1')),
    ('Isoc. 15.200', ('isocrates.speeches', '15.200')),
    ('Isoc. Ep. 2.3', ('isocrates.letters', '2.3')),
    ('Isae. 8.43', ('isaeus.speeches', '8.43')),
    ('Hyp. 3.1', ('hyperides.speeches', '3.1')),
    ('Hyperid. 3.1', ('hyperides.speeches', '3.1')),
])
def test_orators(idx, text, expected):
    assert _one(idx, text) == expected


def test_demosthenes_range_keeps_the_speech(idx):
    hit = [h for h in extract('Dem. 21.72-75', idx) if h['resolved']][0]
    assert (hit['work_id'], hit['locus_start'], hit['locus_end']) == \
        ('demosthenes.against_midias', '21.72', '21.75')


def test_d_needs_demosthenes_named(idx):
    assert _hits(idx, 'D. 21.72') == []
    assert _one(idx, 'D. 21.72', 'Demosthenes attacks Meidias.') == ('demosthenes.against_midias', '21.72')
    assert _one(idx, 'Demosthenes (D. 18.72) says so.') == ('demosthenes.on_the_crown', '18.72')
    assert _one(idx, 'D. 5.200', 'Nonnus tells the tale.')[0] == 'nonnus_of_panopolis.dionysiaca'


def test_speech_number_alone_or_unknown_stays_unresolved(idx):
    for text in ['Dem. 21', 'Dem. 99.1', 'Aeschin. 7.1', 'Andoc. 9.1']:
        assert _hits(idx, text) == [], text


def test_bare_lys_with_one_level_stays_unresolved(idx):
    # one number is a Lysistrata line as likely as a Lysias speech
    assert _hits(idx, 'Lys. 99') == []
    assert _one(idx, 'Aristophanes ends the war (Lys. 1).')[0] == 'aristophanes.lysistrata'


def test_is_needs_its_author(idx):
    assert _hits(idx, 'Is. 2.1') == []
    assert _one(idx, 'Is. 2.1', 'Isaeus pleads for the heirs.') == ('isaeus.speeches', '2.1')


def test_speech_map_matches_the_corpus():
    """Every mapped file exists and holds that speech: its first tag carries
    the number (Andocides 1 also holds speeches 2 to 4)."""
    with open(SPEECHES, encoding='utf-8') as f:
        table = json.load(f)
    if not os.path.isdir(CORPUS):
        pytest.skip('texts/grc not present')
    checked = 0
    for author, entries in table.items():
        if author.startswith('_'):
            continue
        for key, work in entries.items():
            path = os.path.join(CORPUS, work + '.tess')
            assert os.path.exists(path), work
            if '-' in key:
                continue
            with open(path, encoding='utf-8') as f:
                first = f.readline()
            tag = first[1:first.index('>')].split()[-1]
            assert tag.split('.')[0] == key, (work, tag)
            checked += 1
    assert checked >= 70
    assert sorted(table['demosthenes'], key=int) == [str(n) for n in range(1, 62)]


# ---- Pindar: the book letter goes in front of the locus ------------------

@pytest.mark.parametrize('text, expected', [
    ('Ol. 1.1', 'o.1.1'),
    ('Pind. Ol. 1.1', 'o.1.1'),
    ('Pyth. 4.299', 'p.4.299'),
    ('Nem. 3.5', 'n.3.5'),
    ('Isth. 8.70', 'i.8.70'),
    ('Isthm. 8.51', 'i.8.51'),
])
def test_pindar_book_forms(idx, text, expected):
    assert _one(idx, text) == ('pindar.odes', expected)


def test_pindar_range_prefixes_both_ends(idx):
    hit = [h for h in extract('Ol. 1.1-5', idx) if h['resolved']][0]
    assert (hit['work_id'], hit['locus_start'], hit['locus_end']) == ('pindar.odes', 'o.1.1', 'o.1.5')


@pytest.mark.parametrize('text, book', [
    ('O. 1.1', 'o'), ('P. 4.1', 'p'), ('N. 5.1', 'n'), ('I. 1.1', 'i'), ('Is. 2.1', 'i'),
])
def test_pindar_bare_letters_with_pindar_named(idx, text, book):
    locus = text.split()[1]
    assert _one(idx, text, 'Pindar sings of the victor.') == ('pindar.odes', book + '.' + locus)
    assert _one(idx, 'In Pindar the line runs (%s).' % text) == ('pindar.odes', book + '.' + locus)


def test_pindar_bare_letters_without_pindar(idx):
    for text in ['O. 1.1', 'P. 4.1', 'N. 5.1', 'I. 1.1']:
        assert _hits(idx, text) == [], text


def test_i_alone_is_not_pindar_and_stays_unresolved(idx):
    hit = extract('as in I. 1.1', idx)[0]
    assert not hit['resolved']
    assert hit['reason'].startswith('ambiguous_work')


def test_p_and_n_with_one_number_are_pages_and_notes(idx):
    for text in ['P. 45', 'N. 12']:
        assert _hits(idx, text, 'Pindar sings of the victor.') == [], text


def test_pindar_part_forms_are_unchanged(idx):
    assert _one(idx, 'Pind. P. 4.1') == ('pindar.odes.part.4.pythians', '4.1')


# ---- Theocritus -----------------------------------------------------------

@pytest.mark.parametrize('text, expected', [
    ('Theoc. 1.5', ('theocritus.idylls', '1.5')),
    ('Theocr. 1.5', ('theocritus.idylls', '1.5')),
    ('Theoc. Id. 15.133', ('theocritus.idylls', '15.133')),
    ('Theocr. Id. 13.6', ('theocritus.idylls', '13.6')),
    ('Theoc. Ep. 3.1', ('theocritus.epigrams', '3.1')),
    ('Theocr. Ep. 3.1', ('theocritus.epigrams', '3.1')),
])
def test_theocritus(idx, text, expected):
    assert _one(idx, text) == expected


def test_id_needs_theocritus_named(idx):
    assert _hits(idx, 'Id. 1.5') == []
    assert _one(idx, 'Id. 1.5', 'Theocritus opens with the goatherd.') == ('theocritus.idylls', '1.5')
    assert _hits(idx, 'Theocr. 1.1; Id. 2.3') == [('theocritus.idylls', '1.1'), ('theocritus.idylls', '2.3')]


# ---- Bacchylides: the ode number chooses the work -------------------------

@pytest.mark.parametrize('text, expected', [
    ('B. 1.1', ('bacchylides.epinicians', '1.1')),
    ('B. 5.10', ('bacchylides.epinicians', '5.10')),
    ('B. 14.1', ('bacchylides.epinicians', '14.1')),
    ('B. 15.1', ('bacchylides.dithyrambs', '15.1')),
    ('B. 17.1', ('bacchylides.dithyrambs', '17.1')),
    ('B. 20.11', ('bacchylides.dithyrambs', '20.11')),
])
def test_bacchylides_range_boundary(idx, text, expected):
    assert _one(idx, text, 'Bacchylides celebrates the victor.') == expected


def test_bacchylides_longer_forms(idx):
    assert _one(idx, 'Bacchyl. 17.1') == ('bacchylides.dithyrambs', '17.1')
    assert _one(idx, 'Bacchyl. 5.10') == ('bacchylides.epinicians', '5.10')
    assert _one(idx, 'Bacch. 5.10', 'Bacchylides celebrates the victor.') == ('bacchylides.epinicians', '5.10')


def test_b_needs_bacchylides_named(idx):
    assert _hits(idx, 'B. 5.10') == []


def test_bare_bacch_stays_plautus(idx):
    assert _one(idx, 'Bacch. 5.10') == ('plautus.bacchides', '5.10')
    assert _one(idx, 'Plaut. Bacch. 5.10') == ('plautus.bacchides', '5.10')
    assert _one(idx, 'Bacch. 5.10', 'Plautus stages the sisters.') == ('plautus.bacchides', '5.10')


def test_bacchylides_odes_outside_the_range(idx):
    assert _hits(idx, 'B. 25.1', 'Bacchylides celebrates the victor.') == []


# ---- Libanius ---------------------------------------------------------------

def test_libanius_orations_and_declamations(idx):
    assert _one(idx, 'Lib. Or. 11.1') == ('libanius.orations', '11.1')
    assert _one(idx, 'Lib. Or. 64.18') == ('libanius.orations', '64.18')
    assert _one(idx, 'Lib. Decl. 1.1') == ('libanius.declamations', '1.1')
    assert _one(idx, 'Or. 11.1', 'Libanius delivered it at Antioch.') == ('libanius.orations', '11.1')


def test_libanius_bare_lib_and_bare_or_stay_unresolved(idx):
    assert _hits(idx, 'Lib. 11.1') == []     # orations or declamations
    assert _hits(idx, 'Or. 11.1') == []
    assert _one(idx, 'Or. 1.1', 'Euripides stages the matricide.')[0] == 'euripides.orestes'


def test_range_records_count_as_parts_of_their_whole():
    from backend.citations.resolver import _collapse_whole_and_parts
    assert _collapse_whole_and_parts(
        ['libanius.orations', 'libanius.orations_1-11', 'libanius.orations_26-50']) == ['libanius.orations']
    assert _collapse_whole_and_parts(
        ['libanius.orations', 'libanius.declamations']) == ['libanius.orations', 'libanius.declamations']
    assert _collapse_whole_and_parts(
        ['libanius.orations', 'libanius.orationsx_1-11']) == ['libanius.orations', 'libanius.orationsx_1-11']


# ---- the patch script ---------------------------------------------------

def test_patch_is_idempotent_and_overlap_is_declared(tmp_path):
    table = str(tmp_path / 'abbreviations.json')
    shutil.copyfile(os.path.realpath(C._DATA), table)
    first = _run(PATCH, table, '--apply')
    # 'nothing to do' once the lead has applied round 4 to the production table
    assert first.returncode == 0 and ('wrote' in first.stdout or 'nothing to do' in first.stdout)
    assert 'CONFLICT' not in first.stdout
    again = _run(PATCH, table, '--apply')
    assert again.returncode == 0 and 'nothing to do' in again.stdout
    with open(PATCH, encoding='utf-8') as f:
        patch = json.load(f)
    assert patch['allow_overlap'] == ['Bacch.']


def test_overlap_is_refused_unless_declared(tmp_path):
    table = str(tmp_path / 'abbreviations.json')
    shutil.copyfile(os.path.realpath(C._DATA), table)
    patch = {'works': {'isaeus.speeches': {'abbreviations': ['Bacch.']}}}
    undeclared = tmp_path / 'patch.json'
    undeclared.write_text(json.dumps(patch))
    refused = _run(str(undeclared), table)
    assert refused.returncode == 2 and 'CONFLICT' in refused.stdout and 'plautus.bacchides' in refused.stdout
    patch['allow_overlap'] = ['Bacch.']
    undeclared.write_text(json.dumps(patch))
    allowed = _run(str(undeclared), table)
    assert allowed.returncode == 0 and 'CONFLICT' not in allowed.stdout


def test_range_records_also_settle_augustine_letters(idx):
    assert _one(idx, 'Aug. Ep. 5.2') == ('augustine.epistulae', '5.2')
