"""A bare "Leg." is Cicero's De legibus when Cicero is named and Plato's Laws
when Plato is named (2026-10-19).

The abbreviation table lists Leg. for both works once the round 7 patch is
applied (data/citations/abbrev_patch_round7.json, the record De legibus lacked
until the work was imported). Two tables in abbrev_context_rules.json then
decide: "disambiguate" picks the work whose author is named nearest before
the citation, and "rules" drops a Leg. with neither author in reach, so a
bare "Leg. 1.20" stays unresolved rather than guessing.

The recognizer tests need data/citations/abbreviations.json, which is not in
the repository (GPL-3.0 source data), and are skipped without it. The first
test reads the rule file alone and always runs.
"""
import json
import os
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import citations as C  # noqa: E402
from backend.citations.abbrev_index import AbbrevIndex  # noqa: E402
from backend.citations.extractor import extract  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = os.path.join(REPO, 'backend', 'citations', 'abbrev_context_rules.json')
PATCH = os.path.join(REPO, 'data', 'citations', 'abbrev_patch_round7.json')
SCRIPT = os.path.join(REPO, 'scripts', 'citations', 'apply_abbrev_patch.py')


def test_leg_rule_lists_both_works_with_author_contexts():
    rules = json.load(open(RULES, encoding='utf-8'))
    leg = rules['rules']['leg']
    works = {r['work']: r['context'] for r in leg}
    assert set(works) == {'plato.leges', 'cicero.de_legibus'}
    assert 'Plat' in works['plato.leges']
    assert 'Cic' in works['cicero.de_legibus']
    dis = {r['work']: r['context'] for r in rules['disambiguate']['leg']}
    assert set(dis) == {'plato.leges', 'cicero.de_legibus'}


needs_table = pytest.mark.skipif(
    C.index() is None,
    reason='needs data/citations/abbreviations.json, not shipped (GPL-3.0 source data)')


@pytest.fixture(scope='module')
def idx(tmp_path_factory):
    table = str(tmp_path_factory.mktemp('legibus') / 'abbreviations.json')
    shutil.copyfile(os.path.realpath(C._DATA), table)
    done = subprocess.run([sys.executable, SCRIPT, PATCH, table, '--apply'],
                          capture_output=True, text=True)
    # The patch may already be in the table (it was applied to production on
    # 2026-10-19); the script then has nothing to add and exits cleanly.
    assert done.returncode == 0, done.stdout + done.stderr
    return AbbrevIndex(table)


def _hits(idx, text, context=''):
    return [(h['part_id'] or h['work_id'], h['locus_start'])
            for h in extract(text, idx, context) if h['resolved']]


@needs_table
def test_cicero_named_gives_de_legibus(idx):
    hits = _hits(idx, 'Cicero returns to the point at Leg. 1.20.')
    assert [w for w, _ in hits] == ['cicero.de_legibus']


@needs_table
def test_plato_named_gives_the_laws(idx):
    hits = _hits(idx, 'Plato, Leg. 625a, opens with the same question.')
    assert [w for w, _ in hits] == ['plato.leges']


@needs_table
def test_bare_leg_stays_unresolved(idx):
    assert _hits(idx, 'See Leg. 1.20 for the definition.') == []


@needs_table
def test_nearest_author_wins_when_both_are_named(idx):
    hits = _hits(idx, "Plato's Laws is the model, but Cicero's own words at Leg. 1.15 differ.")
    assert [w for w, _ in hits] == ['cicero.de_legibus']
    hits = _hits(idx, 'Cicero drew on it, as Plato shows at Leg. 631b.')
    assert [w for w, _ in hits] == ['plato.leges']


@needs_table
def test_author_in_the_sentence_before_counts(idx):
    hits = _hits(idx, 'The passage at Leg. 2.8 is the clearest statement.',
                 context='Cicero defines law as right reason.')
    assert [w for w, _ in hits] == ['cicero.de_legibus']
