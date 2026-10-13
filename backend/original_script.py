"""Keep quoted Greek and Hebrew in their own letters.

On Search One Text the Scholarship paragraph once showed "*euzen*" where the
note has the Greek words for "the good life": the model had transliterated
the Greek and wrapped it in asterisks. The prompt now forbids that, and
`problems` checks the answer: it finds asterisk spans and any word of the
text that is the transliteration, by the fixed table in
backend/transliterate.py, of a Greek or Hebrew word or phrase in the
sources. `settle` asks again once with the problems named, and strips the
asterisks if the second answer is still wrong.
"""
import logging
import re
import unicodedata

from backend.transliterate import greek_to_latin, hebrew_to_latin

logger = logging.getLogger(__name__)

SCRIPT_RULE = (
    " Quote Greek, Latin and Hebrew words exactly as the notes give them, in their own letters. "
    "Never transliterate them into the Latin alphabet, never wrap them in asterisks or quotation "
    "marks, and when the note gives an English meaning put it after the word in parentheses.")

_GREEK_WORD = re.compile(r'[Ͱ-Ͽἀ-῿]+')
_HEBREW_WORD = re.compile(r'[֐-׿]+')
_LATIN_WORD = re.compile(r"[A-Za-zÀ-ɏ]+")
_STARRED = re.compile(r'\*[^*\n]+\*')
_MAX_PHRASE = 3
# A key shorter than this is skipped: the transliteration of a short Greek word
# ("to", "he", "on") is also an ordinary English word.
_MIN_KEY = 4


def _key(s):
    """Lower case, no marks, no spaces or hyphens, so "eu zēn" and "euzen" meet."""
    s = unicodedata.normalize('NFD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[\s\-ʾʿ'’]", '', s)


def _source_keys(sources):
    """{key: original Greek or Hebrew text} for every word and every run of two or
    three adjacent words in the sources, and the set of Latin-alphabet words."""
    keys = {}
    latin = set()
    for src in sources:
        src = str(src or '')
        latin.update(w.lower() for w in _LATIN_WORD.findall(src))
        for rx, fn in ((_GREEK_WORD, greek_to_latin), (_HEBREW_WORD, hebrew_to_latin)):
            words = list(rx.finditer(src))
            for i in range(len(words)):
                for n in range(1, _MAX_PHRASE + 1):
                    run = words[i:i + n]
                    if len(run) < n:
                        break
                    if any(src[run[j].end():run[j + 1].start()].strip(' \t ') for j in range(n - 1)):
                        break
                    original = ' '.join(m.group() for m in run)
                    k = _key(fn(original))
                    if len(k) >= _MIN_KEY:
                        keys.setdefault(k, original)
    return keys, latin


def problems(text, sources):
    """The faults in a written paragraph, each a sentence the model can act on."""
    text = str(text or '')
    out = [f'You wrote {m.group()} in asterisks. Do not use asterisks.' for m in _STARRED.finditer(text)]
    keys, latin = _source_keys(sources)
    if not keys:
        return out
    words = [(m.group(), m.start()) for m in _LATIN_WORD.finditer(text)]
    i = 0
    seen = set()
    while i < len(words):
        hit = None
        for n in range(min(_MAX_PHRASE, len(words) - i), 0, -1):
            run = words[i:i + n]
            # words must be adjacent: only spaces or hyphens between them
            if any(text[run[j][1] + len(run[j][0]):run[j + 1][1]].strip(' -') for j in range(n - 1)):
                continue
            k = _key(''.join(w for w, _ in run))
            if k not in keys:
                continue
            phrase = ' '.join(w for w, _ in run)
            if all(w.lower() in latin for w, _ in run) or phrase.lower() in latin:
                continue
            hit = (n, phrase, keys[k])
            break
        if hit and hit[1].lower() not in seen:
            seen.add(hit[1].lower())
            out.append(f'You wrote {hit[1]}; the note has {hit[2]}. Quote the original letters.')
        i += hit[0] if hit else 1
    return out


def fix(text):
    """The text with asterisks removed."""
    return re.sub(r'\*+', '', str(text or ''))


def settle(text, sources, ask):
    """(text, problems) after at most one retry.

    `ask(note)` asks the model again with `note` added to the user message and
    returns its text. If the first answer has problems it is called once. A
    second answer that still has problems is used with `fix` applied, and the
    remaining problems are logged and returned."""
    found = problems(text, sources)
    if not found:
        return text, []
    note = ' '.join(found)
    try:
        second = ask(note)
    except Exception as e:
        logger.info('[SCRIPT] retry failed: %s', type(e).__name__)
        second = None
    if second:
        text, again = second, problems(second, sources)
    else:
        again = found
    if again:
        logger.info('[SCRIPT] problems after retry: %s', again)
    return fix(text), again
