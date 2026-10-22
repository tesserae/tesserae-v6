"""The EpiDoc edition rendered with the Leiden signs (scripts/documents/build_leiden_display.py)."""
import importlib.util
import os

from lxml import etree

spec = importlib.util.spec_from_file_location(
    'bld', os.path.join(os.path.dirname(__file__), '..', 'scripts', 'documents', 'build_leiden_display.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

XML = ('<div xmlns="http://www.tei-c.org/ns/1.0" type="edition"><ab><lb n="1"/>'
       '<supplied reason="lost"><expan><abbr>C</abbr><ex>aium</ex></expan> Caesare</supplied>m bello '
       'Pe<unclear>r</unclear><supplied reason="lost">usino</supplied><lb n="2"/>'
       '<gap reason="lost" extent="unknown" unit="character"/>uf <expan><ex>duoviri</ex></expan></ab></div>')


def test_signs():
    t = b.render(etree.fromstring(XML))
    assert t == '[C(aium) Caesare]m bello Per\u0323[usino] / [---]uf (duoviri)'


def test_agreement_ignores_signs_and_line_splits():
    assert b.agrees('[C(aium) Caesare]m bello / Pe[rusino]', 'Caium Caesarem bel / lo Perusino')
    assert not b.agrees('Dis Manibus Zethi', 'Imperatori Caesari Augusto pontifici maximo')
