"""Lemma normalisation shared by Line Search and the documents collection.

Moved out of backend/app.py unchanged (application-factory job, 2026-10-12).
"""



# One shared rule, backend/latin_orthography.py. This used to keep case,
# which a lemma from the tables never has.
from backend.latin_orthography import fold_latin as _normalize_latin_lemma  # noqa: E402


def _normalize_lemma(lem, language='la'):
    """Normalize a lemma for index lookup. Handles Latin u/v/j/i and Greek diacritics.

    Latin folding applies to Latin ONLY (2026-09-20). It used to fall through
    to every other language, so an English query "love" became "loue",
    "jove" became "ioue" and "voice" became "uoice": the English line search
    then returned only Spenser's spellings (love: 500 Spenser lines and no
    other author; voice: nothing at all), and the results page's corpus
    panel was blank for any shared word with a v or a j. The English index
    stores lemmas as written ("love" 2,193 postings in 124 works, "loue" 553
    in 6), so the query must stay as written too.
    """
    if language == 'grc':
        import unicodedata
        decomposed = unicodedata.normalize('NFD', lem)
        stripped = ''.join(c for c in decomposed if unicodedata.category(c) != 'Mn')
        return stripped.lower().replace('ς', 'σ')
    if language == 'la':
        return _normalize_latin_lemma(lem)
    return lem.lower()
