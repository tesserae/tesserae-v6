"""One rule for Latin u/v and i/j, in one place.

Classical Latin is written with u or v, and i or j, for the same sounds, so
"uirum" and "virum" are the same word and a search has to treat them so.
Before 2026-09-21 five functions answered that question, three of them named
`normalize_latin`, and they disagreed:

    backend/matcher.py            lowercase, v->u.  No i/j at all.
    backend/wildcard_search.py    v/V->u/U, j/J->i/I, word-final -om->-um,
                                  case preserved.
    backend/distance_filter.py    v->u, j->i, case preserved.
    backend/app.py                v->u, j->i, case preserved.
    scripts/build_lemma_tables.py lowercase, j->i, v->u.

So the same pair of words could be judged equivalent in one part of a search
and different in another, with nothing erroring to say so.

TWO JOBS, NOT ONE, which is why one function is not enough:

`fold_latin` is for anything compared against the lemma tables or the
inverted index. Its rule is not a matter of taste: it is what the stored
data already is. `data/lemma_tables/latin_lemmas.json` holds 111,739 keys,
not one of which contains a `v` or a `j`, and every one of which is
lowercase ("uirum" is a key, "virum" is not; "iam" is, "jam" is not),
because `scripts/build_lemma_tables.py` folded them when it built the file.
A query folded any other way simply misses.

`fold_latin_surface` is for searching the raw text of the corpus, where the
words appear as the edition printed them. It keeps case, because a search
over displayed text should be able to keep it, and it also folds the archaic
word-final -om to -um, so a search for "divum" finds Ennius' "diuom".

THE ARCHAIC -om RULE BELONGS ONLY TO THE SURFACE FORM. The September 2026
code review proposed making it part of the single shared rule, on the
grounds that it is the most complete. It would have broken lemma lookups:
the table has fourteen keys that genuinely end in -om, including "diuom",
which maps to "deus", and "aequom", "arduom" and "nouom". Folding a query's
-om to -um turns "diuom" into "diuum", which is in no table and no index.
The two rules stay two rules.
"""

import re

__all__ = ['fold_latin', 'fold_latin_surface']

_SURFACE_PAIRS = (('v', 'u'), ('V', 'U'), ('j', 'i'), ('J', 'I'))


def fold_latin(text):
    """Lowercase, v to u, j to i: the form the lemma tables and index use.

    Use this for a lemma, a stopword comparison, an index lookup, or any
    place where a word is compared with stored data. Idempotent: folding an
    already folded word returns it unchanged.
    """
    if not text:
        return text
    return text.lower().replace('v', 'u').replace('j', 'i')


def fold_latin_surface(text, archaic_om=True):
    """v/u and i/j for raw text, keeping case, with the archaic -om ending.

    Use this for searching the text of the corpus as printed, never for a
    lemma or an index key: see this module's docstring for why -om must not
    reach a table lookup. `archaic_om=False` gives the fold alone.
    """
    if not text:
        return text
    for old, new in _SURFACE_PAIRS:
        text = text.replace(old, new)
    if archaic_om:
        text = re.sub(r'om\b', 'um', text)
        text = re.sub(r'Om\b', 'Um', text)
        text = re.sub(r'OM\b', 'UM', text)
    return text
