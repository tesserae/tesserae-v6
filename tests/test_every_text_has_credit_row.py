"""Every text file has a credit row in backend/text_sources.json, so the gap cannot reopen.

The Credits page and the Downloads manifests are built from that file, and a file is matched to its row
by author and work as the Reader shows them. The 2026-10-25 coverage check found 73 Greek texts, 6 English,
14 Coptic and 10 Persian and Urdu ones with no matching row, mostly because a rename left the row under
the old title. A new import, rename or display-title override that does not touch the credit file now
fails here.

TESSERAE_CREDIT_TEST_TEXTS=/var/www/tesseraev6_flask/texts runs the same check over the production
texts, which hold files the repository does not track (read only).
"""
import importlib.util
import os

import pytest

import backend.restricted_texts as restricted_texts
from backend import utils

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LANGUAGES = ('la', 'grc', 'en', 'cop', 'he', 'fa', 'ur')
TEXTS = os.environ.get('TESSERAE_CREDIT_TEST_TEXTS') or os.path.join(ROOT, 'texts')

spec = importlib.util.spec_from_file_location(
    'build_text_archives', os.path.join(ROOT, 'scripts', 'corpus', 'build_text_archives.py'))
bta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bta)


def _without_credit_row(lang):
    folder = os.path.join(TEXTS, lang)
    if not os.path.isdir(folder):
        return []
    index = bta.SourceIndex(bta.load_sources(ROOT))
    missing = []
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith('.tess') or restricted_texts.is_restricted(fn):
            continue
        md = utils.get_text_metadata(os.path.join(folder, fn))
        if index.find(md.get('author', ''), md.get('work', '')) is None:
            missing.append(f"{fn} (shown as {md.get('author')!r}, {md.get('work')!r})")
    return missing


@pytest.mark.parametrize('lang', LANGUAGES)
def test_every_text_has_a_credit_row(lang):
    missing = _without_credit_row(lang)
    assert not missing, (
        f'{len(missing)} {lang} texts have no row in backend/text_sources.json under the author and work '
        'the Reader shows. Add the row, or retitle the row of the old title:\n  ' + '\n  '.join(missing[:40]))


def test_a_part_without_a_work_name_takes_its_authors_one_row():
    index = bta.SourceIndex([{'author': 'Anthologia Graeca', 'work': 'Anthologia Palatina'},
                             {'author': 'Homer', 'work': 'Iliad'}, {'author': 'Homer', 'work': 'Odyssey'}])
    assert index.find('Anthologia Graeca', 'Unknown')['work'] == 'Anthologia Palatina'
    assert index.find('Homer', 'Unknown') is None       # two rows: no guess
    assert index.find('Nobody', 'Unknown') is None
