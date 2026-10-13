"""A lemma's corpus document frequency depends on the lemma alone.

The index is stubbed with a dict. The stub of get_document_frequencies_batch
reproduces the real function's behaviour, including the one that made the old
cache order-dependent: it expands each form to its u/v variants, sums their
counts, and lets two forms that are u/v partners in the same call overwrite
each other.
"""
import itertools

import pytest

from backend import fusion

# raw index rows: form as stored -> number of documents
INDEX = {
    'uero': 5, 'vero': 9,
    'iustus': 7, 'justus': 12,
    'qui': 1426, 'quem': 164, 'quos': 8,
    'arma': 300, 'uirum': 40, 'virum': 22,
    'μῆνις': 30, 'ἀείδω': 55, 'θεά': 70, 'θεός': 400,
}
HEADWORDS_LA = {'quem': 'qui', 'quos': 'qui', 'qui': 'qui'}
HEADWORDS_GRC = {'θεά': 'θεός'}


def fake_batch(lemmas, language):
    expanded = {}
    for lemma in list(lemmas):
        variants = {lemma}
        if language == 'la':
            variants.add(lemma.replace('u', 'v'))
            variants.add(lemma.replace('v', 'u'))
        for v in variants:
            expanded[v] = lemma
    out = {}
    for form, n in INDEX.items():
        if form in expanded:
            orig = expanded[form]
            out[orig] = out.get(orig, 0) + n
    return out


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    import backend.blueprints.hapax as hapax
    monkeypatch.setattr(hapax, 'get_document_frequencies_batch', fake_batch)
    monkeypatch.setattr(fusion, '_get_headword_map',
                        lambda language: HEADWORDS_LA if language == 'la' else HEADWORDS_GRC)
    fusion._corpus_doc_freq_cache.clear()
    fusion._corpus_raw_df_cache.clear()
    yield
    fusion._corpus_doc_freq_cache.clear()
    fusion._corpus_raw_df_cache.clear()


def clear():
    fusion._corpus_doc_freq_cache.clear()
    fusion._corpus_raw_df_cache.clear()


def run(plan, language):
    """plan: list of batches; returns {lemma: value} accumulated over the batches."""
    clear()
    got = {}
    for batch in plan:
        got.update(fusion._get_corpus_doc_freqs(batch, language))
    return got


def plans_for(lemmas):
    orders = [list(lemmas), list(reversed(lemmas)), sorted(lemmas, key=lambda l: (len(l), l))]
    plans = []
    for o in orders:
        plans.append([o])                      # one batch
        plans.append([[l] for l in o])         # one lemma per batch
    heads = [l for l in lemmas if l in HEADWORDS_LA.values() or l in HEADWORDS_GRC.values()]
    rest = [l for l in lemmas if l not in heads]
    plans.append([heads, rest] if heads else [rest])   # headwords first
    plans.append([rest, heads] if heads else [rest])
    return plans


def check_all(lemmas, language, expected):
    results = [run(p, language) for p in plans_for(lemmas)]
    for r in results:
        assert r == results[0]
    for lemma, value in expected.items():
        assert results[0][lemma] == value


def test_uv_pair_same_in_every_order_and_split():
    # the stub sums u and v rows: uero+vero = 14, whichever form is asked
    check_all(['uero', 'vero'], 'la', {'uero': 14, 'vero': 14})


def test_ij_pair_both_take_the_larger_form():
    check_all(['iustus', 'justus', 'arma'], 'la', {'iustus': 12, 'justus': 12, 'arma': 300})


def test_headword_chain():
    # quem -> qui (qui itself is present): max(164, 1426) in every order
    check_all(['quem', 'qui', 'quos', 'arma'], 'la',
              {'quem': 1426, 'qui': 1426, 'quos': 1426, 'arma': 300})


def test_headword_not_present_in_the_batch():
    check_all(['quem'], 'la', {'quem': 1426})
    check_all(['quos', 'quem'], 'la', {'quos': 1426, 'quem': 1426})


def test_greek():
    check_all(['μῆνις', 'ἀείδω', 'θεά', 'θεός'], 'grc',
              {'μῆνις': 30, 'ἀείδω': 55, 'θεά': 400, 'θεός': 400})


def test_earlier_lookups_do_not_change_a_value_without_clearing():
    fusion._get_corpus_doc_freqs(['vero', 'quem', 'arma'], 'la')
    later = fusion._get_corpus_doc_freqs(['uero', 'qui', 'quos', 'justus'], 'la')
    clear()
    alone = fusion._get_corpus_doc_freqs(['uero', 'qui', 'quos', 'justus'], 'la')
    assert later == alone


def test_all_permutations_small_set():
    lemmas = ['uero', 'vero', 'quem', 'qui']
    base = None
    for perm in itertools.permutations(lemmas):
        r = run([list(perm)], 'la')
        base = base or r
        assert r == base
