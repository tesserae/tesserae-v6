"""License class and credit on every connector result (backend/text_license.py).

One test per rule row of CLASS_RULES, one for unknown, one for a restricted
text, one per connector tool shape that carries the fields, and one for the
Reader's About-panel fact.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest  # noqa: E402

from backend import text_license  # noqa: E402
from backend import restricted_texts  # noqa: E402
from backend.blueprints import mcp_http  # noqa: E402

# (rule name, a string that must hit it, the class it gives)
RULE_CASES = {
    'unverified-upstream': (
        "The classical text is public domain. Ganjoor.net's own terms were not independently verified "
        "(which declares CC BY-SA 4.0).", 'unknown'),
    'academic-only': ('(c)2000-2006 by J Warren Wells, for academic use only.; CC-BY-SA 4.0', 'academic-only'),
    'cc-by-nc-sa': ('CC BY-NC-SA 3.0 IT (digilibLT TEI header)', 'cc-by-nc-sa'),
    'cc-by-nc': ('CC BY-NC 4.0', 'cc-by-nc'),
    'noncommercial': ('Noncommercial use only. All rights reserved by the Musisque Deoque project', 'noncommercial'),
    'all-rights-reserved': ('All rights reserved by the Fundacion Tomas de Aquino, no reuse license stated',
                            'restricted'),
    'cc-by-sa': ('CC BY-SA 4.0 (stated in the TEI header of the Perseus edition)', 'cc-by-sa'),
    'cc-by': ('CC-BY 4.0', 'cc-by'),
    'public-domain': ('Public domain (Internet Archive scan of an edition published 1872)', 'public-domain'),
}


def test_every_rule_row_has_a_case():
    assert set(RULE_CASES) == {name for name, _rx, _cls in text_license.CLASS_RULES}


@pytest.mark.parametrize('rule', [name for name, _rx, _cls in text_license.CLASS_RULES])
def test_rule_row(rule):
    string, cls = RULE_CASES[rule]
    assert text_license.classify(string) == (cls, rule)


@pytest.mark.parametrize('string', [None, '', '  ', 'unknown', 'Unknown', 'Some terms nobody wrote a rule for'])
def test_unknown(string):
    assert text_license.license_class(string) == 'unknown'


def test_all_classes_are_declared():
    for _name, _rx, cls in text_license.CLASS_RULES:
        assert cls in text_license.CLASSES
    assert 'unknown' in text_license.CLASSES


@pytest.mark.parametrize('string,label', [
    ('CC BY-SA 4.0 (Latin Wikisource)', 'CC BY-SA 4.0'),
    ('CC BY-SA 3.0 US (stated on the text page)', 'CC BY-SA 3.0 US'),
    ('CC BY-SA (Perseus: 3.0 US on the site, 4.0 in its repositories)', 'CC BY-SA'),
    ('CC-BY 4.0', 'CC BY 4.0'),
    ('CC BY-NC-SA 3.0 IT (digilibLT)', 'CC BY-NC-SA 3.0 IT'),
    ('Public domain in the USA (Project Gutenberg)', 'Public domain'),
    ('unknown', 'Not stated'),
])
def test_label_in_words(string, label):
    assert text_license.license_label(string) == label


def test_credit_line_orders_digital_then_print():
    assert text_license.credit_line({'e_source': 'Perseus', 'print_source': 'Teubner, 1900.'}) == \
        'Perseus. Teubner, 1900.'
    assert text_license.credit_line({'e_source': 'Perseus', 'print_source': ''}) == 'Perseus.'
    assert text_license.credit_line({}) is None


ROWS = [
    {'author': 'Vergil', 'work': 'Aeneid', 'e_source': 'Perseus', 'print_source': 'Greenough, 1900.',
     'license': 'CC BY-SA 4.0 (Perseus)'},
    {'author': 'Mystery', 'work': 'Poem', 'e_source': '', 'print_source': '', 'license': 'unknown'},
]


@pytest.fixture
def fixture_corpus(monkeypatch):
    monkeypatch.setattr(text_license, '_rows', lambda: ROWS)
    monkeypatch.setattr(restricted_texts, 'load', lambda: {
        'heldwork.history': {'credit': 'Source: Test Holder.', 'license': 'Indexing only'}})


def test_lookup_by_file_unrestricted(fixture_corpus):
    r = text_license.lookup_by_file('vergil.aeneid.part.3.tess')
    assert r['license'] == 'cc-by-sa'
    assert r['license_label'] == 'CC BY-SA 4.0'
    assert r['credit'] == 'Perseus. Greenough, 1900.'


def test_lookup_unmatched_text_is_unknown(fixture_corpus):
    r = text_license.lookup_by_file('nobody.nothing.tess')
    assert r == {'license': 'unknown', 'license_label': 'Not stated', 'license_text': None, 'credit': None}
    assert text_license.lookup_by_file('')['license'] == 'unknown'


def test_lookup_restricted_text_uses_the_registry(fixture_corpus):
    r = text_license.lookup_by_file('heldwork.history.part.2.tess')
    assert r['license'] == 'restricted'
    assert r['credit'] == 'Source: Test Holder.'
    assert r['license_text'] == 'Indexing only'


def test_lookup_by_names(fixture_corpus):
    assert text_license.lookup_by_names(' VERGIL ', 'aeneid')['license'] == 'cc-by-sa'
    assert text_license.lookup_by_names('', 'aeneid')['license'] == 'unknown'


def test_class_counts_and_unknown_strings():
    counts, unknown = text_license.class_counts(ROWS)
    assert counts['cc-by-sa'] == 1 and counts['unknown'] == 1
    assert sum(counts.values()) == 2
    assert unknown == {'unknown': 1}


# ------------------------------------------------------------- connector

def test_list_texts_carries_license_and_keeps_restricted_fields(fixture_corpus, monkeypatch):
    monkeypatch.setattr(mcp_http, '_get', lambda path, params=None: [
        {'id': 'vergil.aeneid.tess', 'author': 'Vergil', 'work': 'Aeneid', 'title': 'Aeneid'},
        {'id': 'heldwork.history.tess', 'author': 'Held', 'work': 'History', 'title': 'History',
         'restricted': True, 'credit': 'Source: Test Holder.'},
    ])
    by_id = {t['id']: t for t in mcp_http._t_list_texts({'language': 'la'})}
    assert by_id['vergil.aeneid.tess']['license'] == 'cc-by-sa'
    assert by_id['vergil.aeneid.tess']['credit'] == 'Perseus. Greenough, 1900.'
    assert 'restricted' not in by_id['vergil.aeneid.tess']
    held = by_id['heldwork.history.tess']
    assert held['restricted'] is True
    assert held['credit'] == 'Source: Test Holder.'
    assert held['license'] == 'restricted'


def test_get_passage_carries_license(fixture_corpus, monkeypatch):
    monkeypatch.setattr(mcp_http, '_get', lambda path, params=None: {
        'work': 'vergil.aeneid', 'author': 'Vergil', 'title': 'Aeneid', 'language': 'la',
        'lines': [{'ref': '1.1', 'text': 'arma virumque cano'}], 'returned': 1, 'total': 1})
    out = mcp_http._t_get_passage({'work': 'vergil.aeneid', 'ref_start': '1.1'})
    assert out['license'] == 'cc-by-sa'
    assert out['credit'] == 'Perseus. Greenough, 1900.'


def test_get_passage_restricted_text(fixture_corpus, monkeypatch):
    monkeypatch.setattr(mcp_http, '_get', lambda path, params=None: {
        'work': 'heldwork.history', 'lines': [], 'returned': 0, 'total': 0})
    out = mcp_http._t_get_passage({'work': 'heldwork.history'})
    assert out['license'] == 'restricted'
    assert out['credit'] == 'Source: Test Holder.'


def test_line_search_results_carry_license(fixture_corpus, monkeypatch):
    monkeypatch.setattr(mcp_http, '_post', lambda path, body, timeout=None: {
        'total': 1, 'distinct_loci': 1, 'results': [
            {'text_id': 'vergil.aeneid.tess', 'locus': '1.1', 'author': 'vergil', 'work': 'aeneid',
             'text': 'arma virumque cano', 'matched_words': ['arma', 'vir'], 'era': 'Augustan', 'year': -19}]})
    out = mcp_http._t_line_search({'query': 'arma virum', 'language': 'la'})
    assert out['results'][0]['license'] == 'cc-by-sa'
    assert out['results'][0]['credit'] == 'Perseus. Greenough, 1900.'


def test_pair_tools_carry_source_and_target_license(fixture_corpus):
    res = mcp_http._lic_pair({'status': 'complete'}, 'vergil.aeneid.tess', 'nobody.nothing.tess')
    assert res['source_license']['license'] == 'cc-by-sa'
    assert res['target_license'] == {'license': 'unknown', 'credit': None}


# ------------------------------------------------- the real file: Aeneid

def test_vergil_aeneid_in_the_real_sources():
    r = text_license.lookup_by_file('vergil.aeneid.tess')
    assert r['license'] == 'cc-by-sa'
    assert r['credit'].startswith('Perseus.')


def test_every_real_row_is_classed():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'backend', 'text_sources.json')
    with open(path, encoding='utf-8') as f:
        rows = json.load(f)
    counts, _unknown = text_license.class_counts(rows)
    assert sum(counts.values()) == len(rows)
