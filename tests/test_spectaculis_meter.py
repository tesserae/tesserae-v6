"""De Spectaculis lines find their MQDQ scansion (2026-10-28).

Its tags read <mart. libe. POEM.LINE>, which the Martial branch of
lookup_mqdq_scansion did not parse, so the 220 scansions MQDQ gives under
martialis.de_spectaculis were never used for the meter boost."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from backend import metrical_scanner as ms  # noqa: E402

if not ms.get_mqdq_scansions() or 'martialis.de_spectaculis' not in ms.get_mqdq_scansions():
    pytest.skip('MQDQ scansions not available', allow_module_level=True)


@pytest.mark.parametrize('locus', ['<mart. libe. 1.1>', 'mart. libe. 1.1', 'martialis.de_spectaculis.1.1'])
def test_first_line_is_a_hexameter(locus):
    r = ms.lookup_mqdq_scansion(locus)
    assert r and r['source'] == 'mqdq' and r['meter'] == 'hexameter'


def test_second_line_is_a_pentameter():
    r = ms.lookup_mqdq_scansion('<mart. libe. 1.2>')
    assert r and r['meter'] == 'pentameter'


def test_epigrams_unchanged():
    assert ms.lookup_mqdq_scansion('mart. 9.84.10') == ms.lookup_mqdq_scansion('martial.epigrams.9.84.10')
