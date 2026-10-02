"""The 55 Septuagint files show readers' book names, the Greek book's
conventional English name with the Hebrew Bible's name in brackets where
the two differ (#564)."""
import os
from backend.utils import get_text_metadata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_every_septuagint_file_has_a_display_name():
    files = [f for f in os.listdir(os.path.join(ROOT, 'texts', 'grc')) if f.startswith('septuaginta.') and f.endswith('.tess')]
    assert len(files) >= 50
    for f in files:
        m = get_text_metadata(f)
        assert m['author'] == 'Septuagint', f
        assert '_' not in m['title'] and m['title'] != m['title'].lower(), (f, m['title'])


def test_known_names():
    assert get_text_metadata('septuaginta.basileion_g.tess')['title'] == '3 Kingdoms (1 Kings)'
    assert get_text_metadata('septuaginta.kritai.tess')['title'] == 'Judges'
    assert get_text_metadata('septuaginta.machabaeorum_g.tess')['title'] == '3 Maccabees'
    assert get_text_metadata('septuaginta.threni_seu_lamentationes.tess')['title'] == 'Lamentations'
    assert get_text_metadata('septuaginta.daniel_theodotionis.tess')['title'] == 'Daniel (Theodotion)'
