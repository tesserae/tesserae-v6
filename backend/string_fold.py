"""Comparison forms for String Search in Persian, Urdu, Arabic and Hebrew.

The "Match spelling variants" mode of String Search compares the typed query
and each line after both have passed through one of these functions. They are
deliberately separate from the language plugins' normalizers
(backend/persian/processor.py, backend/urdu/processor.py), which delete the
zero-width non-joiner and fold alef with madda to bare alef. String Search
keeps the non-joiner (its separator rule is applied to the query, see
backend/wildcard_search.py) and keeps alef with madda apart from alef.

RULES_LABEL changes whenever a fold family or the separator rule changes, so
an exported result can be read later.
"""
import re

RULES_LABEL = 'string-fold-1'

# Vowel marks and other combining marks, tatweel, zero-width joiner and the
# direction marks. The zero-width non-joiner (U+200C) is not here: it stays.
_ARABIC_MARKS = (
    'ً-ٰٟۖ-ۭ࣓-ࣿ'
    'ـ‍‎‏‪-‮⁦-⁩'
)
_ARABIC_MARKS_RE = re.compile('[' + _ARABIC_MARKS + ']')

# Letters that are one letter in different code points. One heh form (U+0647)
# stands for heh, heh goal and both teh marbuta forms.
_ARABIC_LETTERS = {
    0x0643: 'ک',   # Arabic kaf -> Persian kaf
    0x064A: 'ی',   # Arabic yeh -> Farsi yeh
    0x0649: 'ی',   # alef maqsura -> Farsi yeh
    0x06C1: 'ه',   # heh goal -> heh
    0x0629: 'ه',   # teh marbuta -> heh
    0x06C3: 'ه',   # teh marbuta goal -> heh
    0x0623: 'ا',   # alef with hamza above -> alef
    0x0625: 'ا',   # alef with hamza below -> alef
    0x0671: 'ا',   # alef wasla -> alef
}

_HEBREW_MARKS_RE = re.compile('[֑-ֽֿ-ׇׂׅׄ]')


def fold_arabic_script(text: str, marks: bool = True, letters: bool = True) -> str:
    """The comparison form of fa, ur and ar text.

    marks=False or letters=False leaves that family of the fold out; the
    match notes of String Search use this to find out which family made a
    line match. Both default to on.
    """
    if text.isascii():
        return text
    if marks:
        text = _ARABIC_MARKS_RE.sub('', text)
    if letters:
        text = text.translate(_ARABIC_LETTERS)
    return text


def fold_hebrew_script(text: str, marks: bool = True) -> str:
    """The comparison form of Hebrew text: points and cantillation removed."""
    if not marks or text.isascii():
        return text
    return _HEBREW_MARKS_RE.sub('', text)
