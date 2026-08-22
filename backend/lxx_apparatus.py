"""Strip critical-apparatus debris from Septuagint (LXX) .tess text.

Some LXX .tess lines carry a critical edition's apparatus merged into the text
field. Two kinds of contamination occur:

  1. Full apparatus blocks. At page/column boundaries a whole apparatus block was
     spliced into the middle of a verse, e.g.
       "... δέδωκα ὑμῖν πᾶν 14 καὶ ἄρχειν ... νυκτος I°] καὶ ἀρχέτωσαν (D) ...
        πάντα D sil χόρτον σπόριμον ..."
     Clean verse text runs before and after one contiguous apparatus block.
     These lines carry a lemma bracket "]" or a variant separator "|".

  2. Stray inline reference markers. Otherwise-clean verses carry a loose verse
     number or chapter siglum, e.g. "... θυγατέρα 10 Λαβὰν ...", "(32) VIΛάμεχ",
     "50(50 a)", "52b", "55 (XXX)".

Arabic digits never occur in clean LXX Greek (numbers are spelled out or written
with Greek numerals), so a digit is a reliable apparatus signal. The lemma
bracket "]" and the "|" separator likewise never occur in clean text.

strip_lxx_apparatus() removes both kinds. It is deliberately conservative about
clean text: for the heavy blocks it deletes one contiguous span anchored on the
hard signals (digits, "]", "|") and the manuscript sigla that hug it, then tidies
the head and tail of stray reference markers.

This is a best-effort cleanup of digitization debris, not a critical-edition
parser. A handful of sigla may survive and a rare clean word adjacent to an
apparatus block may be clipped. Run it only on Septuagint texts.
"""
import re
import unicodedata

# Manuscript sigla and apparatus abbreviations used in the Rahlfs/Brooke-McLean
# style apparatus present in these files. Bare uppercase Latin A-E and V are
# manuscript sigla; the lowercase tokens are apparatus abbreviations.
_SIGLA_LETTERS = set('ABCDEV')
_ABBREV = {
    'om', 'pr', 'sil', 'mg', 'vid', 'ras', 'sup', 'seq', 'rescr', 'hab', 'incl',
    'perier', 'uncis', 'litt', 'quae', 'post', 'sd', 'sq', 'cf', 'add', 'del',
    'tr', 'ras', 'a', 'b', 'c', 'bis', 'ter', 'in', 'vel', 'sunt', 'ex', 'corr',
}
_ROMAN = re.compile(r'^[IVXLC]+$')


def _strip_combining(tok):
    nfd = unicodedata.normalize('NFD', tok)
    return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')


def _is_hard(tok):
    """A token that can only be apparatus: an arabic digit, the variant separator
    "|", or a lemma bracket "]".

    A "]" with no matching "[" in the same token is an apparatus lemma bracket
    ("νυκτος]"). A "]" that pairs with a "[" is an editorial restoration in clean
    verse text ("[ὑ]μῖν") and must NOT be treated as apparatus.
    """
    if re.search(r'[0-9\|]', tok):
        return True
    if ']' in tok and '[' not in tok:
        return True
    return False


# Single-letter manuscript sigla appear as bare Latin A-E/V or as bare Greek
# capitals (this edition mixes Ε/Α into the apparatus). A standalone single Greek
# capital is effectively never a word, so treating it as a siglum is safe.
_GREEK_CAPS = set('ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ')


def _is_bare_siglum(tok):
    base = _strip_combining(tok).strip('().,·;:*°?§’\'')
    if not base:
        return False
    if all(ch in _SIGLA_LETTERS for ch in base):
        return True
    if len(base) == 1 and base in _GREEK_CAPS:
        return True
    return False


def _is_soft(tok):
    """A token that is apparatus when it hugs a hard token: a bare manuscript
    siglum, an apparatus abbreviation, a roman-numeral chapter marker, or an
    editorial mark."""
    if tok in ('§', '°', '*', ')', '('):
        return True
    base = _strip_combining(tok).strip('().,·;:*°?§')
    if not base:
        return True
    # Bare sigla like A, D, E, V, DE, AD, ADE and single Greek capitals.
    if _is_bare_siglum(tok):
        return True
    low = base.lower()
    if low in _ABBREV:
        return True
    if _ROMAN.match(base):
        return True
    # Nomina-sacra overline / unusual combining marks used only in sigla notation
    if any(unicodedata.category(c) == 'Mn' and ord(c) > 0x750 for c in tok):
        return True
    return False


def _strip_inline_markers(text):
    """Remove stray verse/chapter reference debris from otherwise-clean text."""
    # Parenthesized reference groups: (32), (52 a), (XXX), (50 a), (D)
    text = re.sub(r'\((?:[0-9IVXLC]+|[A-EV]| |[a-z]){1,8}\)', ' ', text)
    # Number glued to a paren group: 50(50 a) leftover "50"
    # Roman-numeral chapter marker glued to a Greek word: VIΛάμεχ -> Λάμεχ
    text = re.sub(r'\b[IVXLC]{1,5}(?=[Ͱ-Ͽἀ-῿])', ' ', text)
    # Standalone arabic-digit tokens (verse numbers), incl. forms like 52b, 50a
    text = re.sub(r'\b[0-9]+[a-z]?\b', ' ', text)
    # Verse numbers fused to a word ("4καὶ", "θρό9", "π0λάκες") and superscript
    # digits ("5²Εὐλογητὸς", "⁶9εὐλογεῖτε"). Clean LXX text carries no digits at
    # all, so removing every digit character is safe and unglues these.
    text = re.sub(r'[0-9²³¹⁰-⁹]', '', text)
    # Loose editorial marks
    text = text.replace('§', ' ')
    # Collapse whitespace
    return re.sub(r'\s{2,}', ' ', text).strip()


def strip_lxx_apparatus(text):
    """Return `text` with LXX critical-apparatus debris removed.

    Clean lines (no arabic digit, no "]" or "|") are returned unchanged apart from
    whitespace, so the 90%+ of verses that are clean are never touched.
    """
    if not text:
        return text

    heavy = (']' in text) or ('|' in text)

    if heavy:
        tokens = text.split()
        hard_idx = [i for i, t in enumerate(tokens) if _is_hard(t)]
        if hard_idx:
            start, end = hard_idx[0], hard_idx[-1]
            # Extend the span over sigla/abbreviations that hug the hard block.
            while start > 0 and _is_soft(tokens[start - 1]):
                start -= 1
            while end < len(tokens) - 1 and _is_soft(tokens[end + 1]):
                end += 1
            head = tokens[:start]
            tail = tokens[end + 1:]
            text = ' '.join(head + tail)

    # Second pass: remove any remaining stray reference markers and lone sigla.
    text = _strip_inline_markers(text)
    # Drop surviving apparatus debris left in the head/tail. LXX verse text is
    # pure Greek script, so any token that is entirely Latin-script letters
    # (sigla A/D/E, abbreviations sil/mg/ras/sup/vid/rescr, fragments "a?"/"b?")
    # is apparatus, never a word. Also drop single Greek-capital sigla.
    def _debris(t):
        if _is_bare_siglum(t):
            return True
        # Nomina-sacra overline sigla (κݲςݲ, θݲυݲ) only occur in apparatus here.
        if any(0x0740 <= ord(c) <= 0x077F for c in t):
            return True
        # Any token whose letters are all Latin script (no Greek letter at all) is
        # apparatus: sigla, abbreviations, roman chapter refs ("xxxvii.R."), and
        # punctuated fragments like "Ba?AF", "V*vid", "Mcovo^fl". LXX verse text is
        # entirely Greek script, so this never removes a real word.
        letters = [c for c in t if c.isalpha()]
        if letters and all('A' <= c <= 'Z' or 'a' <= c <= 'z' for c in letters):
            return True
        return False
    kept = [t for t in text.split() if not _debris(t)]
    return re.sub(r'\s{2,}', ' ', ' '.join(kept)).strip()
