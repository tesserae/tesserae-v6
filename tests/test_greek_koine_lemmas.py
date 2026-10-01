"""The Koine lemma table fills the gaps the treebank table leaves on
Septuagint forms, and never overrides it (2026-10-01)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.text_processor import get_greek_lemma_table  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_koine_forms_are_looked_up():
    table = get_greek_lemma_table()
    # ὑμνεῖτε "praise!" and ὑπερυψοῦτε "exalt!" (the Song of the Three
    # Children) were lemmatized as υμνειτοσ and υπερυψουτοσ before.
    assert table['υμνειτε'] == 'υμνεω'
    assert table['υπερυψουτε'] == 'υπερυψοω'
    assert table['λημψομαι'] == 'λαμβανω'


def test_treebank_table_wins_on_a_shared_form():
    table = get_greek_lemma_table()
    main = json.load(open(os.path.join(ROOT, 'data', 'lemma_tables', 'greek_lemmas.json'), encoding='utf-8'))
    conflicts = json.load(open(os.path.join(ROOT, 'data', 'lemma_tables', 'greek_koine_conflicts.json'), encoding='utf-8'))
    assert conflicts, 'the conflicts file is empty'
    for form, entry in list(conflicts.items())[:50]:
        assert table[form] == main[form] == entry['main']


def test_koine_table_follows_the_main_conventions():
    koine = json.load(open(os.path.join(ROOT, 'data', 'lemma_tables', 'greek_koine_lemmas.json'), encoding='utf-8'))
    for form, lemma in list(koine.items())[:2000]:
        assert form == form.lower() and lemma == lemma.lower()
        assert 'ς' not in form and 'ς' not in lemma
        assert not any('̀' <= c <= 'ͯ' or 'ἀ' <= c <= '῿' for c in form + lemma)
