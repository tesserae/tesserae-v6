"""The Latin verse scanners work without the CLTK distribution installed."""
import importlib
import sys


def test_vendored_scanners_import_without_cltk(monkeypatch):
    for name in list(sys.modules):
        if name == 'cltk' or name.startswith('cltk.') or name.startswith('backend.metrical_scanner'):
            monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(sys.modules, 'cltk', None)   # makes "import cltk..." raise ImportError
    m = importlib.import_module('backend.metrical_scanner')
    try:
        assert m._CLTK_AVAILABLE is True
        assert m.HendecasyllableScanner.__module__ == 'backend.prosody_lat.hendecasyllable_scanner'
        result = m.scan_latin_verse('cui dono lepidum novum libellum', 'hendecasyllable')
        assert result and result['valid'] is True
        assert result['pattern'] == '-u-uu-u-u-u'
        assert m.scan_latin_verse('passer deliciae meae puellae', 'hendecasyllable')['valid'] is True
    finally:
        sys.modules.pop('backend.metrical_scanner', None)


def test_vendored_package_carries_its_licence():
    import pathlib
    folder = pathlib.Path(__file__).resolve().parents[1] / 'backend' / 'prosody_lat'
    assert (folder / 'LICENSE').read_text(encoding='utf-8').startswith('MIT License')
    assert 'Classical Language Toolkit' in (folder / '__init__.py').read_text(encoding='utf-8')
