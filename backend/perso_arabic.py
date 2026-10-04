"""A shared comparison form for Persian, Urdu and Arabic words (2026-09-05).

The three languages write one script with local conventions. Persian and
Urdu poetry carry a large Arabic and (for Urdu) Persian vocabulary, so a
word that is the same word in two of these languages should match across
them without a dictionary. Each language's own normalizer already folds its
ye and kaf to the Arabic letters; what remains are the Urdu-only letters and
heh, and the Arabic ta marbuta, which Persian and Urdu write as either heh
or te depending on the word (rahmat, madrasa).

cross_form(word, lang) returns the comparison form. cross_variants(word,
lang) returns the set of forms a word may take on the other side (the ta
marbuta case), so that an index built with cross_variants on one side and
looked up with cross_form on the other matches every spelling.
"""
import re

_URDU_MAP = str.maketrans({
    'ہ': 'ه',  # heh goal -> heh
    'ھ': 'ه',  # heh doachashmee (aspiration) -> heh
    'ۂ': 'ه',  # heh goal with hamza -> heh
    'ۃ': 'ه',  # teh marbuta goal -> heh
    'ے': 'ي',  # yeh barree -> yeh
    'ۓ': 'ي',  # yeh barree with hamza -> yeh
    'ں': 'ن',  # noon ghunna -> noon
    'ٹ': 'ت',  # tteh -> teh
    'ڈ': 'د',  # ddal -> dal
    'ڑ': 'ر',  # rreh -> reh
    'ە': 'ه',  # ae -> heh
})
_ARABIC_MAP = str.maketrans({
    'ة': 'ه',  # ta marbuta -> heh (Persian madrasa, Urdu likewise)
    'ى': 'ي',  # alef maksura -> yeh
})
_STRIP = re.compile('[ؐ-ًؚ-ْٔ-ٰٕۖ-ۭ‌‍ـ]')


def _base_normalize(word, lang):
    if lang == 'ur':
        from backend.urdu.processor import normalize_urdu
        return normalize_urdu(word)
    if lang == 'fa':
        from backend.persian.processor import normalize_persian
        return normalize_persian(word)
    if lang == 'ar':
        from backend.arabic.processor import normalize_arabic
        return normalize_arabic(word)
    return word


def cross_form(word, lang):
    """The comparison form of a word for matching across fa, ur and ar."""
    if not word:
        return ''
    w = _STRIP.sub('', _base_normalize(word, lang))
    if lang == 'ur':
        w = w.translate(_URDU_MAP)
    w = w.translate(_ARABIC_MAP)
    # Persian and Urdu write initial hamza-alef as plain alef; Arabic
    # normalizers already fold alef variants. Final hamza after alef is
    # dropped in Persian spelling of Arabic words (sama' -> sama).
    w = w.replace('ء', '') if w.endswith('ء') else w
    return w


def cross_variants(word, lang):
    """Forms this word may take on the other side of a shared-script pair.
    Arabic ta marbuta appears in Persian and Urdu as heh (default in
    cross_form) or as te; Persian/Urdu final heh may stand for a ta marbuta.
    """
    f = cross_form(word, lang)
    if not f:
        return set()
    out = {f}
    raw = _STRIP.sub('', _base_normalize(word, lang))
    if lang == 'ar' and raw.endswith('ة'):
        out.add(raw[:-1] + 'ت')
    # Only words long enough to be Arabic loans carry the heh/te variant;
    # two-letter words (ke, na, be, che) are Persian function words.
    if lang in ('fa', 'ur') and len(f) >= 3 and f.endswith('ه'):
        out.add(f[:-1] + 'ت')
    if lang in ('fa', 'ur') and len(f) >= 3 and f.endswith('ت'):
        out.add(f[:-1] + 'ه')
    return out


def cross_stoplist(lang):
    """The language's curated stoplist in comparison form."""
    try:
        from backend.fusion import _STOPLISTS
        words = _STOPLISTS.get(lang, set())
    except Exception:  # pragma: no cover
        words = set()
    return {cross_form(w, lang) for w in words} | {w for w in words}
