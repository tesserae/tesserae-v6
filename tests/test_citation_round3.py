"""Citation recognizer, round 3: table entries and author-context choices
behind the Project MUSE audit's worklist. Each sentence is a constructed
citation string in the shape the audit counted (no article text).

The new forms live in data/citations/abbrev_patch_round3.json, which the lead
applies to the production table. These tests apply the patch to a COPY of the
table (scripts/citations/apply_abbrev_patch.py, in a temporary folder) and
extract against that copy. The disambiguation rules ("Met.", "Ep.", "Th." and
others that name several works) are in backend/citations/abbrev_context_rules.json
and need no table change.

Needs data/citations/abbreviations.json (not in the repository or CI), so the
module is skipped without it, like tests/test_citation_round2.py.
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
PATCH = os.path.join(REPO, 'data', 'citations', 'abbrev_patch_round3.json')
SCRIPT = os.path.join(REPO, 'scripts', 'citations', 'apply_abbrev_patch.py')


def _run(*args):
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True)


@pytest.fixture(scope='module')
def patched_table(tmp_path_factory):
    table = str(tmp_path_factory.mktemp('round3') / 'abbreviations.json')
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


# ---- one test per added work ------------------------------------------

@pytest.mark.parametrize('text, expected', [
    ('Polyb. 6.11.1', [('polybius.histories', '6.11.1')]),
    ('Diod. 17.38.4', [('diodorus_siculus.bibliotheca_historica', '17.38.4')]),
    ('Diod. Sic. 12.10.7', [('diodorus_siculus.bibliotheca_historica', '12.10.7')]),
    ('D.S. 14.34.2', [('diodorus_siculus.bibliotheca_historica', '14.34.2')]),
    ('Xen. Hell. 2.3.11', [('xenophon.hellenica', '2.3.11')]),
    ('X. HG 5.1.34', [('xenophon.hellenica', '5.1.34')]),
    ('Hes. Theog. 32', [('hesiod.theogony', '32')]),
    ('Theog. 116', [('hesiod.theogony', '116')]),
    ('Mostell. 431', [('plautus.mostellaria', '431')]),
    ('Cho. 964', [('aeschylus.libation_bearers', '964')]),
    ('Eum. 737', [('aeschylus.eumenides', '737')]),
    ('Phaen. 96', [('aratus.phaenomena', '96')]),
    ('Controv. 9.2.28', [('seneca_the_elder.controversiae', '9.2.28')]),
    ('BGall. 3.8', [('caesar.de_bello_gallico', '3.8')]),
    ('B. Gall. 3.8', [('caesar.de_bello_gallico', '3.8')]),
    ('BCiv. 2.4', [('caesar.de_bello_civili', '2.4')]),
    ('B. Civ. 2.4', [('caesar.de_bello_civili', '2.4')]),
    ('Suet. Aug. 29', [('suetonius.de_vita_caesarum.part.2.augustus', '29')]),
    ('Suet. Iul. 10', [('suetonius.de_vita_caesarum.part.1.julius', '10')]),
    ('Macrob. Sat. 2.7.5', [('macrobius.saturnalia', '2.7.5')]),
    ('Dion. Hal. 7.73.3', [('dionysius_halicarnassensis.antiquitates_romanae', '7.73.3')]),
    ('Vell. Pat. 2.81.3', [('velleius_paterculus.historiae_romanae', '2.81.3')]),
    ('Apollod. Bibl. 3.183', [('apollodorus.library', '3.183')]),
    ('Cass. Dio 54.6', [('cassius_dio.roman_history', '54.6')]),
    ('Dio Cass. 54.6', [('cassius_dio.roman_history', '54.6')]),
    ('Anth. Pal. 5.53', [('anthologia_graeca.part.5', '5.53')]),
    ('Ath. Pol. 26.4', [('aristotle.res_publica_atheniensium', '26.4')]),
])
def test_added_work(idx, text, expected):
    assert _hits(idx, text) == expected


def test_forms_that_need_their_author_named(idx):
    # form: (sentence with the author, work, the same form with no author)
    for text, context, work, locus in [
        ('G. 1.1', 'Vergil sets the scene.', 'vergil.georgics', '1.1'),
        ('Geo. 4.482', 'Virgil ends the poem.', 'vergil.georgics', '4.482'),
        ('Her. 7.1', 'Ovid has Dido write.', 'ovid.heroides', '7.1'),
        ('Ben. 4.8.3', 'Seneca argues the point.', 'seneca.de_beneficiis', '4.8.3'),
        ('Leg. 2.21', 'Plato writes of laws.', 'plato.leges', '2.21'),
        ('Ling. 5.107', 'Varro derives the word.', 'varro.de_lingua_latina', '5.107'),
        ('Gall. 1.2.3', 'Caesar opens the war.', 'caesar.de_bello_gallico', '1.2.3'),
        ('Hell. 2.3.56', 'Xenophon narrates the Thirty.', 'xenophon.hellenica', '2.3.56'),
        ('Cass. 54.6', 'Cassius Dio reports it.', 'cassius_dio.roman_history', '54.6'),
        ('Pun. 7.667', 'Silius describes the battle.', 'silius_italicus.punica', '7.667'),
        ('Imag. 2.7', 'Philostratus describes the painting.', 'philostratus_the_lemnian.imagines', '2.7'),
        ('Salt. 19', 'Lucian describes the dance.', 'lucian.de_saltatione', '19'),
        ('Dion. 5.200', 'Nonnus tells the tale.', 'nonnus_of_panopolis.dionysiaca', '5.200'),
    ]:
        assert _hits(idx, text, context) == [(work, locus)], text
        if text != 'Ben. 4.8.3':   # round 5: book, chapter and section name Seneca alone
            assert _hits(idx, text) == [], text


def test_ath_pol_is_not_the_politics(idx):
    assert [w for w, _ in _hits(idx, 'Ath. Pol. 22.3', 'Aristotle (or his school) reports it.')] \
        == ['aristotle.res_publica_atheniensium']
    assert _hits(idx, 'Pol. 1.2') == []   # bare Pol. still needs Aristotle named


def test_theogony_but_not_after_theognis(idx):
    assert _hits(idx, 'Theognis, Theog. 116') == []
    assert _hits(idx, 'Hesiod, Theog. 116') == [('hesiod.theogony', '116')]


# ---- ambiguous forms: the author named nearby decides -------------------

@pytest.mark.parametrize('form, text, work', [
    ('Met.', 'Ovid describes the flood (Met. 1.262).', 'ovid.metamorphoses'),
    ('Met.', 'Apuleius ends with the initiation of Lucius (Met. 11.24).', 'apuleius.metamorphoses'),
    ('Ep.', 'Horace addresses Maecenas at the start (Ep. 1.1.1).', 'horace.epistles'),
    ('Ep.', 'Seneca writes to Lucilius about time (Ep. 1.1).', 'seneca.ad_lucilium_epistulae_morales'),
    ('Ep.', 'Pliny asks about the Christians (Ep. 10.96).', 'pliny_the_younger.letters'),
    ('Ep.', 'Ovid has Phyllis write to Demophoon (Ep. 2.1).', 'ovid.heroides'),
    ('Epist.', 'Seneca writes to Lucilius about time (Epist. 1.1).', 'seneca.ad_lucilium_epistulae_morales'),
    ('Ecl.', 'Vergil opens the collection (Ecl. 1.1).', 'vergil.eclogues'),
    ('Ecl.', 'Calpurnius imitates him (Ecl. 4.1).', 'calpurnius_siculus.eclogae'),
    ('Od.', 'Homer begins with the man of many turns (Od. 1.1).', 'homer.odyssey'),
    ('Od.', 'Horace ends the first collection (Od. 1.1).', 'horace.odes'),
    ('Tr.', 'Ovid laments his exile (Tr. 1.1).', 'ovid.tristia'),
    ('Tr.', 'Euripides stages the fall of Troy (Tr. 25).', 'euripides.trojan_women'),
    ('Tr.', 'Sophocles shows Deianeira (Tr. 141).', 'sophocles.trachiniae'),
    ('Th.', 'Thucydides sets out his method (Th. 1.22).', 'thucydides.peloponnesian_war'),
    ('Th.', 'Hesiod invokes the Muses (Th. 1).', 'hesiod.theogony'),
    ('Th.', 'Aeschylus stages the siege (Th. 375).', 'aeschylus.seven_against_thebes'),
    ('Rust.', 'Varro opens the dialogue (Rust. 1.40.6).', 'varro.res_rusticae'),
    ('Rust.', 'Columella gives the rule (Rust. 1.40.6).', 'columella.de_re_rustica'),
    ('Arg.', 'Apollonius tells of Medea (Arg. 3.95).', 'apollonius_rhodius.argonautica'),
    ('Arg.', 'Valerius Flaccus tells of Medea (Arg. 3.95).', 'valerius_flaccus.argonautica'),
    ('Argon.', 'Apollonius tells of Jason (Argon. 1.485).', 'apollonius_rhodius.argonautica'),
    ('Argon.', 'Valerius Flaccus tells of Jason (Argon. 1.485).', 'valerius_flaccus.argonautica'),
    ('Sat.', 'Horace turns to his neighbors (Sat. 1.1).', 'horace.satires'),
    ('Sat.', 'Macrobius gathers the dinner talk (Sat. 2.7.5).', 'macrobius.saturnalia'),
    ('Ann.', 'Tacitus begins with the kings (Ann. 1.1).', 'tacitus.annales'),
    ('Ann.', 'Ennius wrote an epic on Rome (Ann. 1).', 'ennius.annales'),
    ('Ach.', 'Statius leaves it unfinished (Ach. 1.1).', 'statius.achilleid'),
    ('Ach.', 'Aristophanes mocks Lamachus (Ach. 1).', 'aristophanes.acharnians'),
    ('Brut.', 'Cicero lists the orators (Brut. 123).', 'cicero.brutus'),
    ('Brut.', 'Plutarch narrates the death (Brut. 5.1).', 'plutarch.brutus'),
    ('Phil.', 'Cicero attacks Antony (Phil. 2.1).', 'cicero.philippicae'),
    ('Phil.', 'Plutarch praises the Achaean (Phil. 3).', 'plutarch.philopoemen'),
    ('Inst.', 'Quintilian argues for early schooling (Inst. 1.1.1).', 'quintilian.institutio_oratoria'),
    ('Inst.', 'Lactantius answers the pagans (Inst. 1.1).', 'lactantius.divinarum_institutionum'),
    ('Med.', 'Seneca stages the witch (Med. 1).', 'seneca.medea'),
    ('Med.', 'Euripides stages the witch (Med. 1).', 'euripides.medea'),
    ('Dom.', 'Cicero defends his house (Dom. 1).', 'cicero.de_domo_sua'),
    ('Dom.', 'Suetonius records the end (Dom. 1).', 'suetonius.de_vita_caesarum.part.12.domitian'),
    ('An.', 'Arrian follows Alexander (An. 2.14.4).', 'arrian.anabasis'),
    ('An.', 'Xenophon follows Cyrus (An. 1.1).', 'xenophon.anabasis'),
    ('Alex.', 'Plutarch begins with Philip (Alex. 2).', 'plutarch.alexander'),
    ('Alex.', 'Lucian mocks the prophet (Alex. 5).', 'lucian.alexander'),
    ('Supp.', 'Aeschylus has the Danaids flee (Supp. 1).', 'aeschylus.suppliant_women'),
    ('Supp.', 'Euripides has the mothers plead (Supp. 1).', 'euripides.suppliants'),
    ('Ant.', 'Plutarch gives Antony a bad end (Ant. 1).', 'plutarch.antony'),
    ('Ant.', 'Sophocles stages the burial (Ant. 1).', 'sophocles.antigone'),
    ('Pers.', 'Persius opens with a rebuke (Pers. 1).', 'persius.saturae'),
    ('Pers.', 'Aeschylus stages Salamis (Pers. 1).', 'aeschylus.persians'),
    ('Hec.', 'Terence adapts the play (Hec. 1).', 'terence.hecyra'),
    ('Hec.', 'Euripides shows the queen (Hec. 1).', 'euripides.hecuba'),
    ('Alc.', 'Euripides saves the wife (Alc. 1).', 'euripides.alcestis'),
    ('Alc.', 'Plutarch follows the general (Alc. 1).', 'plutarch.alcibiades'),
    ('El.', 'Euripides recasts the story (El. 1).', 'euripides.electra'),
    ('El.', 'Sophocles recasts the story (El. 1).', 'sophocles.electra'),
    ('Mil.', 'Cicero defends the tribune (Mil. 1).', 'cicero.pro_milone'),
    ('Mil.', 'Plautus stages the braggart (Mil. 1).', 'plautus.miles_gloriosus'),
    ('Lys.', 'Aristophanes ends the war (Lys. 1).', 'aristophanes.lysistrata'),
    ('Lys.', 'Lysias speaks for the defendant (Lys. 1).', 'lysias.speeches'),
    ('Civ.', 'Caesar reports the war (Civ. 1.72.3).', 'caesar.de_bello_civili'),
    ('Civ.', 'Augustine answers the pagans (Civ. 1.1).', 'augustine.de_civitate_dei'),
])
def test_author_named_decides(idx, form, text, work):
    assert [w for w, _ in _hits(idx, text)] == [work]


def test_author_in_the_sentence_before_counts(idx):
    assert _hits(idx, 'Met. 7.365 is the key passage.', 'Ovid tells of Medea.') \
        == [('ovid.metamorphoses', '7.365')]
    assert _hits(idx, 'Ep. 9.43 is the key passage.', 'Pliny writes to a friend.') \
        == [('pliny_the_younger.letters', '9.43')]


def test_nearest_author_wins(idx):
    assert _hits(idx, 'Ovid and Apuleius both tell tales; in the second (Met. 4.28).') \
        == [('apuleius.metamorphoses', '4.28')]
    assert _hits(idx, 'Vergil and Calpurnius both write pastoral, in the second (Ecl. 4.1).') \
        == [('calpurnius_siculus.eclogae', '4.1')]


def test_bare_met_stays_unresolved(idx):
    # No default: Ovid is far likelier than Apuleius, but the code only
    # resolves a form that names several works when an author is named.
    hit = extract('as in Met. 7.365', idx)[0]
    assert not hit['resolved']
    assert hit['reason'].startswith('ambiguous_work')


def test_bare_forms_stay_as_they_were(idx):
    for text in ['Ep. 9.43', 'Ecl. 2', 'Tr. 2.5', 'Rust. 1.40.6', 'Arg. 3.95']:
        assert _hits(idx, text) == [], text
    assert _hits(idx, 'Od. 1.2') == []   # the round 1 guard: Odyssey 1 to 4 needs Homer
    assert _hits(idx, 'Od. 9.19') == [('homer.odyssey', '9.19')]
    for text in ['G. 1.1', 'Her. 7.1', 'Cass. 54.6', 'Gall. 1.2.3', 'Hell. 2.3.56']:
        assert _hits(idx, text) == [], text


# ---- the patch script ---------------------------------------------------

def _strip_round3(src, dst):
    """Copy the table with the round 3 patch undone: its forms removed and
    the works it creates dropped, so the test does not depend on whether the
    live table already holds round 3."""
    from backend.citations.abbrev_index import normalize_abbr
    with open(PATCH, encoding='utf-8') as f:
        patch = json.load(f)['works']
    with open(src, encoding='utf-8') as f:
        data = json.load(f)
    data['works'] = [w for w in data['works']
                     if not (w['base_id'] in patch and 'new_work' in patch[w['base_id']])]
    for w in data['works']:
        spec = patch.get(w['base_id'])
        if spec:
            drop = {normalize_abbr(x) for x in spec['abbreviations']}
            w['abbreviations'] = [a for a in w.get('abbreviations', []) if normalize_abbr(a) not in drop]
    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def test_patch_script_is_idempotent_and_backs_up(tmp_path):
    table = str(tmp_path / 'abbreviations.json')
    _strip_round3(os.path.realpath(C._DATA), table)
    before = open(table, encoding='utf-8').read()
    dry = _run(PATCH, table)
    assert dry.returncode == 0 and 'dry run' in dry.stdout
    assert open(table, encoding='utf-8').read() == before
    first = _run(PATCH, table, '--apply')
    assert first.returncode == 0 and 'wrote' in first.stdout
    backups = [n for n in os.listdir(tmp_path) if n.startswith('abbreviations.json.bak-')]
    assert len(backups) == 1
    assert open(tmp_path / backups[0], encoding='utf-8').read() == before
    after = open(table, encoding='utf-8').read()
    again = _run(PATCH, table, '--apply')
    assert again.returncode == 0 and 'nothing to do' in again.stdout
    assert open(table, encoding='utf-8').read() == after
    assert len([n for n in os.listdir(tmp_path) if n.startswith('abbreviations.json.bak-')]) == 1


def test_patch_script_refuses_a_form_that_resolves_elsewhere(tmp_path):
    table = str(tmp_path / 'abbreviations.json')
    shutil.copyfile(os.path.realpath(C._DATA), table)
    patch = tmp_path / 'patch.json'
    patch.write_text(json.dumps({'works': {'plautus.mostellaria': {'abbreviations': ['Hdt.']}}}))
    refused = _run(str(patch), table, '--apply')
    assert refused.returncode == 2 and 'CONFLICT' in refused.stdout
    assert 'Hdt.' not in json.load(open(table, encoding='utf-8'))['works'][0]['abbreviations']
    forced = _run(str(patch), table, '--apply', '--force')
    assert forced.returncode == 0 and 'wrote' in forced.stdout
