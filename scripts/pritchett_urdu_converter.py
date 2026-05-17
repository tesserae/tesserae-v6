"""
Convert Pritchett's custom Roman encoding to Urdu Nastaliq script.

Faithful port of the conversion logic from:
  franpritchett.com/script/main-tle2U4VR.js

The converter is context-sensitive: the same Roman sequence can produce
different Urdu output depending on word boundaries, preceding vowels/
consonants, and following characters.

Processing order:
1. Tokenize into words
2. For each word, scan left-to-right applying rules in priority order
3. Context rules (with <wb>, <consonant>, <vowel>) take priority
4. Fall back to simple (context-free) rules
5. Unknown characters pass through
"""

import re
import unicodedata


# ============================================================================
# Character classification
# ============================================================================

URDU_CONSONANTS_SET = set('بپتٹثجچحخدڈذرڑزژسشصضطظعغفقکگلمنںوہی')
URDU_VOWEL_MARKS = set('َُِ')  # zabar, zer, pesh
URDU_LONG_VOWELS = set('اآیےوُِ')

_CONSONANT_INPUTS = {
    'b', 'p', 't', 's', 'j', 'd', 'r', 'z', 'f', 'q', 'k', 'g',
    'l', 'm', 'n', 'v', 'w', 'h', 'y',
    'sh', 'ch', 'zh',
    '.s', '.z', '.r', ':t', ':z',
    ';T', ';D', ';R', ';h', ';x', ';G', ';s', ';z', ';N', ';m',
    ';Th', ';Dh', ';Rh',
    'bh', 'ph', 'th', 'dh', 'jh', 'kh', 'gh', 'nh',
    '((', '))',
}

_VOWEL_INPUTS = {'a', 'aa', 'i', 'ii', 'u', 'uu', 'e', 'o', 'ai', 'au',
                  '^a', '^i', '^u', '^ai', '^au', '^ii', '^uu', ';aa'}


# ============================================================================
# Simple rules (no context)
# ============================================================================

SIMPLE = {
    # Punctuation
    ',': '،', ';': '؛', '?': '؟', '--': '۔', '----': '۔۔',
    '- o -': ' و ',
    # Special consonants (3 char)
    ';Th': 'ٹھ', ';Dh': 'ڈھ', ';Rh': 'ڑھ',
    # Special consonants (2 char)
    '.s': 'ص', '.z': 'ض', '.r': 'ر', ':t': 'ط', ':z': 'ظ',
    ';T': 'ٹ', ';D': 'ڈ', ';R': 'ڑ', ';h': 'ح', ';x': 'خ',
    ';G': 'غ', ';N': 'ن', ';s': 'ث', ';z': 'ذ', ';m': 'ن',
    '((': 'ع', '))': 'ئ',
    # Digraph consonants
    'sh': 'ش', 'ch': 'چ',
    'bh': 'بھ', 'ph': 'پھ', 'th': 'تھ', 'dh': 'دھ',
    'jh': 'جھ', 'kh': 'کھ', 'gh': 'گھ', 'nh': 'نھ',
    'zh': 'ژ',
    # Single consonants
    'b': 'ب', 'p': 'پ', 't': 'ت', 's': 'س', 'j': 'ج',
    'd': 'د', 'r': 'ر', 'z': 'ز', 'f': 'ف', 'q': 'ق',
    'k': 'ک', 'g': 'گ', 'l': 'ل', 'm': 'م', 'n': 'ن',
    'v': 'و', 'w': 'و', 'h': 'ہ', 'y': 'ی',
    # Vowels (medial) -- ai/au are diphthongs in Pritchett's encoding
    'aa': 'ا', 'ii': 'ی', 'uu': 'و', 'ai': 'ی', 'au': 'و',
    'a': '', 'i': '', 'u': '', 'e': 'ے', 'o': 'و',
    # Short vowel marks
    '^a': 'َ', '^i': 'ِ', '^u': 'ُ',
    '^ai': 'ِی', '^au': 'َو', '^ii': 'ِی', '^uu': 'ُو',
    ';aa': 'ٰ',
    # Gemination
    'b b': 'بّ', 'd d': 'دّ', 'f f': 'فّ', 'g g': 'گّ',
    'h h': 'ہّ', 'j j': 'جّ', 'k k': 'کّ', 'l l': 'ل',
    'm m': 'مّ', 'n n': 'نّ', 'p p': 'پّ', 'q q': 'قّ',
    'r r': 'رّ', 's s': 'سّ', 't t': 'تّ', 'v v': 'وّ',
    'y y': 'یّ', 'z z': 'زّ', 'sh sh': 'شّ', 'ch ch': 'چّ',
    '(( ((': 'عّ',
    '.s .s': 'صّ', '.z .z': 'ضّ', ':t :t': 'طّ', ':z :z': 'ظّ',
    ';D ;D': 'ڈّ', ';G ;G': 'غّ', ';R ;R': 'ڑّ', ';T ;T': 'ٹّ',
    ';h ;h': 'حّ', ';s ;s': 'ثّ', ';x ;x': 'خّ',
    # Geminated aspirates
    'b bh': 'بّھ', 'd dh': 'دّھ', 'g gh': 'گّھ',
    'j jh': 'جّھ', 'k kh': 'کھ', 'p ph': 'پّھ',
    't th': 'تّھ', 'ch chh': 'چّھ',
    ';D ;Dh': 'ڈّھ', ';T ;Th': 'ٹّھ',
    # Hamza
    'a )) a': 'أ',
}

# Sort by length descending for matching
SIMPLE_KEYS = sorted(SIMPLE.keys(), key=len, reverse=True)


def _is_consonant_output(ch):
    """Check if a character is an Urdu consonant."""
    return ch in URDU_CONSONANTS_SET


def _is_vowel_output(ch):
    """Check if a character is an Urdu vowel or vowel mark."""
    return ch in URDU_LONG_VOWELS or ch in URDU_VOWEL_MARKS


def convert_word(word):
    """Convert a single word from Pritchett encoding to Urdu script.

    Handles context-sensitive rules at word boundaries.
    """
    if not word:
        return ''

    result = []
    i = 0
    wlen = len(word)

    while i < wlen:
        at_start = (i == 0)
        remaining = word[i:]
        last_urdu = result[-1] if result else ''
        matched = False

        # --- Context-sensitive rules ---

        # Word-initial vowels get alif
        if at_start:
            for pattern, urdu in [
                ('aa', 'آ'), ('ai', 'ای'), ('au', 'او'),
                ('ii', 'ای'), ('uu', 'او'),
                ('^ai', 'اِی'), ('^au', 'اَو'),
                ('^ii', 'اِی'), ('^uu', 'اُو'),
                ('^a', 'اَ'), ('^i', 'اِ'), ('^u', 'اُ'),
                ('e', 'ای'), ('o', 'او'),
                ('a', 'ا'), ('i', 'ا'), ('u', 'ا'),
            ]:
                if remaining.startswith(pattern):
                    # Check if this is the whole word or followed by consonant
                    rest = remaining[len(pattern):]
                    if not rest or rest[0] in ' \t' or rest[0] in '.-;:()':
                        result.append(urdu)
                        # Word-final e -> اے
                        if pattern == 'e' and not rest.strip():
                            result[-1] = 'اے'
                        elif pattern == 'ai' and not rest.strip():
                            result[-1] = 'اے'
                    else:
                        result.append(urdu)
                    i += len(pattern)
                    matched = True
                    break

        # Word-final rules
        if not matched:
            for pattern, urdu in [
                ('e ;N g e', 'یں گے'), ('e ;N g ii', 'یں گی'),
                ('e g aa', 'ےگا'), ('e g ii', 'ےگی'),
                ('a :n', 'اً'),
            ]:
                if remaining.startswith(pattern) and i + len(pattern) >= wlen:
                    result.append(urdu)
                    i += len(pattern)
                    matched = True
                    break

        # Izafat: -e anywhere in word (typically before word boundary or hyphen)
        if not matched and remaining.startswith('-e'):
            next_after = remaining[2:3] if len(remaining) > 2 else ''
            if not next_after or next_after == ' ' or next_after == '-':
                # End of word or before another compound
                if last_urdu and last_urdu.endswith('ہ'):
                    result[-1] = result[-1][:-1] + 'ۂ'
                elif last_urdu and last_urdu[-1] in 'اآوی':
                    result.append('ئے')
                else:
                    result.append('ِ')
                i += 2
                matched = True

        # Word-final e -> ے
        if not matched and remaining == 'e':
            result.append('ے')
            i += 1
            matched = True

        # Word-final i -> ی
        if not matched and remaining == 'i':
            result.append('ی')
            i += 1
            matched = True

        # Word-final ;N -> ں
        if not matched and remaining in (';N', ';m'):
            result.append('ں')
            i += len(remaining)
            matched = True

        # hai/hai;N special cases
        if not matched and at_start and word in ('hai', 'hu))aa', 'hu))e', 'hu))ii'):
            special = {
                'hai': 'ہے', 'hu))aa': 'ہوا', 'hu))e': 'ہوئے', 'hu))ii': 'ہوئی',
            }
            result.append(special[word])
            return ''.join(result)

        # kah special case
        if not matched and at_start and word == 'kah':
            result.append('کہہ')
            return ''.join(result)

        # )) after vowel -> ؤ (for u/uu) or ئ
        if not matched and remaining.startswith('))'):
            if last_urdu and last_urdu[-1] in 'وُ':
                result.append('ؤ')
            else:
                result.append('ئ')
            i += 2
            matched = True

        # --- Simple rules (no context) ---
        if not matched:
            for key in SIMPLE_KEYS:
                if remaining.startswith(key):
                    result.append(SIMPLE[key])
                    i += len(key)
                    matched = True
                    break

        # --- Fallback ---
        if not matched:
            ch = word[i]
            if ch == '-':
                pass  # izafat/compound separator
            elif ch == "'":
                result.append('ع')
            elif ch == '.':
                pass
            elif ch == ':':
                pass
            elif ch.isdigit():
                result.append(ch)
            else:
                result.append(ch)
            i += 1

    return ''.join(result)


def pritchett_to_urdu(text):
    """Convert a full line of Pritchett encoding to Urdu script."""
    if not text:
        return ''

    # Clean HTML
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = re.sub(r'<[^>]+>', '', text)
    text = text.strip()

    # Handle special multi-word patterns first
    text = text.replace('- o -', ' و ')

    words = text.split()
    urdu_words = []

    for word in words:
        if word in (',', '.', '!', '--', '----', ';', ':'):
            urdu_words.append(SIMPLE.get(word, word))
        elif word == '?':
            urdu_words.append('؟')
        elif word == 'o':
            urdu_words.append('و')
        else:
            converted = convert_word(word)
            if converted:
                urdu_words.append(converted)

    return ' '.join(urdu_words)
