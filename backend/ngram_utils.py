"""
Tesserae V6 - N-gram window definition

The word-triple window (contiguous 3-grams plus one-gap skip-3-grams) that
scripts/reuse/build_reuse_table.py matches on when it builds
cache/reuse_pairs/<lang>.db. Factored out to its own module, imported by
BOTH the build script and backend/reuse_table.py (which reconstructs the
same triples at read time to bold the words a Reuse tab quotation shares
with the selected line -- see reuse_table.py's docstring), so the two can
never drift apart: a "shared triple" the Reader shows is always exactly
what the build actually matched on, not a reimplementation of it.
"""


def gen_ngram_indices(n):
    """Yield index triples for contiguous 3-grams and one-gap skip-3-grams
    over a sequence of length n: (i, i+1, i+2) for every position, plus
    (i, i+1, i+3) and (i, i+2, i+3) wherever a one-token gap still fits.
    Factored out of gen_ngrams so a caller can apply the SAME index
    pattern to a positionally-parallel array other than the surface
    tokens -- e.g. build_index applying it to a line's lemmas to judge
    n-gram commonality without recomputing the pattern."""
    for i in range(n - 2):
        yield (i, i + 1, i + 2)
    for i in range(n - 3):
        yield (i, i + 1, i + 3)
        yield (i, i + 2, i + 3)


def gen_ngrams(tokens):
    """Yield contiguous 3-grams and one-gap skip-3-grams for a token list."""
    for idxs in gen_ngram_indices(len(tokens)):
        yield tuple(tokens[i] for i in idxs)
