"""Fixed letter tables for Greek and Hebrew.

The page shows a transliteration after each Greek or Hebrew word in the
written paragraphs. It is made here, by a table, never by the language
model, so nothing is invented. The same rules are in
client/src/utils/transliterate.js, and both are tested against
tests/fixtures/transliteration_cases.json so they cannot drift apart.

Beta code (the TLG convention) is provided for export controls and is not
shown on any page.
"""
import unicodedata

_ROUGH = '̔'
_SMOOTH = '̓'
_SUBSCRIPT = 'ͅ'
_DIAERESIS = '̈'
_ACUTE = '́'
_GRAVE = '̀'
_CIRCUMFLEX = '͂'

_GREEK_LATIN = {
    'α': 'a', 'β': 'b', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z', 'η': 'ē', 'θ': 'th',
    'ι': 'i', 'κ': 'k', 'λ': 'l', 'μ': 'm', 'ν': 'n', 'ξ': 'x', 'ο': 'o', 'π': 'p',
    'ρ': 'r', 'σ': 's', 'ς': 's', 'ϲ': 's', 'τ': 't', 'υ': 'y', 'φ': 'ph', 'χ': 'ch',
    'ψ': 'ps', 'ω': 'ō',
}
_GREEK_BETA = {
    'α': 'a', 'β': 'b', 'γ': 'g', 'δ': 'd', 'ε': 'e', 'ζ': 'z', 'η': 'h', 'θ': 'q',
    'ι': 'i', 'κ': 'k', 'λ': 'l', 'μ': 'm', 'ν': 'n', 'ξ': 'c', 'ο': 'o', 'π': 'p',
    'ρ': 'r', 'σ': 's', 'ς': 's', 'ϲ': 's', 'τ': 't', 'υ': 'u', 'φ': 'f', 'χ': 'x',
    'ψ': 'y', 'ω': 'w',
}
_VOWELS = 'αεηιουω'
_DIPHTHONGS = {'αι', 'ει', 'οι', 'υι', 'αυ', 'ευ', 'ηυ', 'ου'}
_NASALISING = 'γκξχ'
_LONG_WITH_IOTA = {'α': 'āi', 'η': 'ēi', 'ω': 'ōi'}


def _letters(text):
    """Split into tokens: (base lower-case letter, is_upper, marks) for a Greek
    letter, (None, char, None) for anything else. NFD puts the marks after
    their letter."""
    out = []
    for ch in unicodedata.normalize('NFD', text):
        if unicodedata.combining(ch) and out and out[-1][0] is not None:
            out[-1][2].add(ch)
        elif ch.lower() in _GREEK_LATIN:
            out.append((ch.lower(), ch != ch.lower(), set()))
        else:
            out.append((None, ch, None))
    return out


def _cap(s):
    return s[0].upper() + s[1:]


def greek_to_latin(text):
    """Classical scholarly transliteration of Greek. See the module notes."""
    toks = _letters(text)
    out = []
    skip_h = False
    for i, (b, up, marks) in enumerate(toks):
        if b is None:
            out.append(up)
            skip_h = False
            continue
        nxt = toks[i + 1] if i + 1 < len(toks) and toks[i + 1][0] is not None else None
        prev = toks[i - 1] if i > 0 and toks[i - 1][0] is not None else None
        piece = None
        if b in _VOWELS:
            dipth = bool(nxt and _DIAERESIS not in nxt[2] and (b + nxt[0]) in _DIPHTHONGS)
            rough = _ROUGH in marks or (dipth and _ROUGH in nxt[2])
            h = ''
            if rough and not skip_h:
                h = 'h'
            skip_h = dipth
            if b == 'υ':
                u = (nxt is not None and nxt[0] == 'ι' and _DIAERESIS not in nxt[2]
                     and _DIAERESIS not in marks) or \
                    (prev is not None and prev[0] in 'αεηο' and _DIAERESIS not in marks
                     and (prev[0] + 'υ') in _DIPHTHONGS and _DIAERESIS not in prev[2])
                core = 'u' if u else 'y'
            elif _SUBSCRIPT in marks and b in _LONG_WITH_IOTA:
                core = _LONG_WITH_IOTA[b]
            else:
                core = _GREEK_LATIN[b]
            piece = h + core
        else:
            skip_h = False
            if b == 'γ' and nxt and nxt[0] in _NASALISING:
                piece = 'n'
            elif b == 'ρ' and _ROUGH in marks:
                piece = 'rh'
            else:
                piece = _GREEK_LATIN[b]
        out.append(_cap(piece) if up else piece)
    return unicodedata.normalize('NFC', ''.join(out))


def greek_to_betacode(text):
    """TLG beta code. Capitals are an asterisk, the marks, then the lower-case
    letter. Marks follow the letter in this order: diaeresis, breathing,
    accent, iota subscript."""
    out = []
    for b, up, marks in _letters(text):
        if b is None:
            out.append(up)
            continue
        d = ''
        if _DIAERESIS in marks:
            d += '+'
        if _SMOOTH in marks:
            d += ')'
        if _ROUGH in marks:
            d += '('
        if _ACUTE in marks:
            d += '/'
        if _GRAVE in marks:
            d += '\\'
        if _CIRCUMFLEX in marks:
            d += '='
        if _SUBSCRIPT in marks:
            d += '|'
        out.append(('*' + d + _GREEK_BETA[b]) if up else (_GREEK_BETA[b] + d))
    return ''.join(out)


# ---- Hebrew ---------------------------------------------------------------

_HEB_CONS = {
    'א': 'ʾ', 'ב': 'v', 'ג': 'g', 'ד': 'd', 'ה': 'h', 'ו': 'w', 'ז': 'z', 'ח': 'ḥ',
    'ט': 'ṭ', 'י': 'y', 'כ': 'kh', 'ך': 'kh', 'ל': 'l', 'מ': 'm', 'ם': 'm', 'נ': 'n',
    'ן': 'n', 'ס': 's', 'ע': 'ʿ', 'פ': 'f', 'ף': 'f', 'צ': 'ṣ', 'ץ': 'ṣ', 'ק': 'q',
    'ר': 'r', 'ש': 'sh', 'ת': 't',
}
_HEB_UNPOINTED = {'ב': 'b', 'כ': 'k', 'ך': 'k', 'פ': 'p', 'ף': 'p'}
_HEB_DAGESH_FORM = {'ב': 'b', 'כ': 'k', 'ך': 'k', 'פ': 'p', 'ף': 'p'}
_HEB_VOWELS = {
    'ֱ': 'e', 'ֲ': 'a', 'ֳ': 'o', 'ִ': 'i', 'ֵ': 'e',
    'ֶ': 'e', 'ַ': 'a', 'ָ': 'a', 'ֹ': 'o', 'ֺ': 'o',
    'ֻ': 'u', 'ׇ': 'a',
}
_SHEWA = 'ְ'
_DAGESH = 'ּ'
_SHIN_DOT = 'ׁ'
_SIN_DOT = 'ׂ'
_HEB_PUNCT = {'־': '-', '׃': '.'}


def _is_hebrew_letter(ch):
    return 'א' <= ch <= 'ת'


def hebrew_to_latin(text):
    """SBL general-purpose style. Consonants only for unpointed text, with
    vowels from the points for pointed text."""
    s = unicodedata.normalize('NFD', text)
    # Split into words and others, so shewa and the pointed test work per word.
    out = []
    i = 0
    n = len(s)
    while i < n:
        if not _is_hebrew_letter(s[i]):
            if s[i] in _HEB_PUNCT:
                out.append(_HEB_PUNCT[s[i]])
            elif not ('\u0591' <= s[i] <= '\u05C7'):
                out.append(s[i])
            i += 1
            continue
        # a word: letters with their marks
        letters = []
        while i < n and (_is_hebrew_letter(s[i]) or '֑' <= s[i] <= 'ׇ') \
                and s[i] not in _HEB_PUNCT:
            if _is_hebrew_letter(s[i]):
                letters.append([s[i], set()])
            elif letters:
                letters[-1][1].add(s[i])
            i += 1
        pointed = any(m in _HEB_VOWELS or m == _SHEWA for _, ms in letters for m in ms)
        last = len(letters) - 1
        for k, (c, ms) in enumerate(letters):
            vowel = ''.join(_HEB_VOWELS[m] for m in sorted(ms) if m in _HEB_VOWELS)
            has_dagesh = _DAGESH in ms
            if c == 'ו' and pointed:
                if 'ֹ' in ms or 'ֺ' in ms:
                    out.append('o')
                    continue
                if has_dagesh and not vowel:
                    out.append('u')
                    continue
            if c == 'י' and pointed and k > 0 and not vowel and _SHEWA not in ms:
                pm = letters[k - 1][1]
                if 'ִ' in pm or 'ֵ' in pm:
                    continue
            if c == 'ש':
                cons = 'ś' if _SIN_DOT in ms else 'sh'
            elif not pointed and c in _HEB_UNPOINTED:
                cons = _HEB_UNPOINTED[c]
            elif pointed and c in _HEB_DAGESH_FORM and has_dagesh:
                cons = _HEB_DAGESH_FORM[c]
            else:
                cons = _HEB_CONS[c]
            sh = ''
            if _SHEWA in ms and not vowel and k != last:
                sh = 'e'
            out.append(cons + vowel + sh)
    return unicodedata.normalize('NFC', ''.join(out))
