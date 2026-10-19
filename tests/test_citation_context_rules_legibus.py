"""Cic. Leg. names Cicero's De legibus when Cicero is the author named, Plato's Laws otherwise (2026-10-19)."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_leg_rule_lists_both_works_with_author_contexts():
    rules = json.load(open(os.path.join(ROOT, 'backend', 'citations', 'abbrev_context_rules.json'), encoding='utf-8'))
    leg = rules['rules']['leg']
    works = {r['work']: r['context'] for r in leg}
    assert 'plato.leges' in works
    assert 'cicero.de_legibus' in works
    assert 'Cic' in works['cicero.de_legibus']
