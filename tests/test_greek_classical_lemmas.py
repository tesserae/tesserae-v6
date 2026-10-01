"""The classical lemma table fills the gaps the treebank table and the
Koine table both leave, and never overrides either (2026-10-01)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.text_processor import get_greek_lemma_table  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_classical_forms_are_looked_up():
    table = get_greek_lemma_table()
    # Attic ξ- spellings of συν- compounds, common in Thucydides, absent
    # from both the treebank table and the Koine table.
    assert table['ξυμβαινειν'] == 'συμβαινω'
    assert table['ξυμμαχοισ'] == 'συμμαχοσ'
    assert table['ξυναγαγων'] == 'συναγω'


def test_existing_table_wins_on_a_shared_form():
    table = get_greek_lemma_table()
    conflicts = json.load(open(os.path.join(ROOT, 'data', 'lemma_tables', 'greek_classical_conflicts.json'), encoding='utf-8'))
    assert conflicts, 'the conflicts file is empty'
    for form, entry in list(conflicts.items())[:50]:
        assert table[form] == entry['existing']


def test_classical_table_follows_the_main_conventions():
    classical = json.load(open(os.path.join(ROOT, 'data', 'lemma_tables', 'greek_classical_lemmas.json'), encoding='utf-8'))
    for form, lemma in list(classical.items())[:2000]:
        assert form == form.lower() and lemma == lemma.lower()
        assert 'ς' not in form and 'ς' not in lemma
        assert not any('̀' <= c <= 'ͯ' or 'ἀ' <= c <= '῿' for c in form + lemma)
