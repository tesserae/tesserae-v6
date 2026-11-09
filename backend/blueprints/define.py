"""
Tesserae V6 - Define Blueprint

GET /api/define?word=...&language=...

One dictionary lookup for the Reader's "Look up" popover and the connector's
`define` tool. The form is lemmatized with the same table the rare-word pages
use, then the lemma is looked up: Lewis and Short (Latin) or LSJ (Greek)
through the Logeion service first, then the Wiktionary and Perseus fetchers
the rare-word pages already use, and the English dictionary API for English.
Languages with no fetcher (Coptic, Hebrew, Persian, Urdu, Arabic) return the
lemma and the external dictionary link with a null definition.

Results are cached on disk under cache/definitions/<language>.json, at most
50,000 entries per language, and upstream fetches are spaced so a burst of
requests never becomes a burst against the dictionary sites.
"""

import json
import logging
import os
import re
import threading
import time
import unicodedata
import urllib.parse
import urllib.request

from flask import Blueprint, jsonify, request

from backend.blueprints import hapax

logger = logging.getLogger(__name__)

define_bp = Blueprint('define', __name__)

# Anchored on the project root, as the other caches are: under Apache the
# working folder is not the checkout.
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(_ROOT, 'cache', 'definitions')
MAX_ENTRIES = 50000
MIN_FETCH_INTERVAL = 0.25  # seconds between upstream fetches
MAX_WORD_LENGTH = 60
MAX_DEFINITION = 600

FETCHED_LANGUAGES = ('la', 'grc', 'en')
LANGUAGES = ('la', 'grc', 'en', 'cop', 'he', 'fa', 'ur', 'ar')

# Which Logeion dictionary to read, in order of preference.
LOGEION_DICTIONARIES = {
    'la': ('LewisShort',),
    # The two Homeric lexicons last: they hold the patronymics LSJ leaves out
    # (Πηληϊάδης, Ἀτρεΐδης), both public domain (2026-11-08).
    'grc': ('LSJ', 'Middle Liddell', 'Autenrieth Homer', 'Cunliffe Homer'),
}
LOGEION_DISPLAY = {
    'LewisShort': 'Lewis and Short',
    'LSJ': 'Liddell-Scott-Jones (LSJ)',
    'Middle Liddell': 'Middle Liddell',
    'Autenrieth Homer': 'Autenrieth, Homeric Dictionary',
    'Cunliffe Homer': 'Cunliffe, Lexicon of the Homeric Dialect',
}

# The external entry for a word, by language. Mirrors getDictionaryUrl in
# client/src/utils/linkUtils.js; keep the two in step.
EXTERNAL_DICTIONARIES = {
    'la': ('Logeion', 'https://logeion.uchicago.edu/{}'),
    'grc': ('Logeion', 'https://logeion.uchicago.edu/{}'),
    'en': ('Wiktionary', 'https://en.wiktionary.org/wiki/{}'),
    'fa': ('Vajehyab', 'https://www.vajehyab.com/?q={}'),
    'ur': ('Rekhta Dictionary', 'https://rekhtadictionary.com/search?keyword={}'),
    'ar': ('Almaany', 'https://www.almaany.com/ar/dict/ar-ar/{}/'),
    'he': ('Wiktionary', 'https://en.wiktionary.org/w/index.php?search={}'),
    'cop': ('Coptic Dictionary Online', 'https://coptic-dictionary.org/results.cgi?quick_search={}'),
}

_lock = threading.Lock()
_fetch_lock = threading.Lock()
_last_fetch = [0.0]
_memory = {}


def dictionary_url(word, language):
    """The external dictionary link for a word, or None."""
    entry = EXTERNAL_DICTIONARIES.get(language)
    if not entry or not word:
        return None
    return entry[1].format(urllib.parse.quote(word, safe=''))


def _cache_path(language):
    return os.path.join(CACHE_DIR, f'{language}.json')


def _load(language):
    """The language's cache as a dict, re-read when the file changed."""
    path = _cache_path(language)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {}
    held = _memory.get(language)
    if held and held[0] == mtime:
        return held[1]
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except Exception as e:
        logger.warning(f"definition cache {path} unreadable: {e}")
        data = {}
    _memory[language] = (mtime, data)
    return data


def _store(language, key, value):
    """Add one entry, dropping the oldest beyond the cap, written atomically."""
    with _lock:
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            data = dict(_load(language))
            data.pop(key, None)
            data[key] = value
            while len(data) > MAX_ENTRIES:
                data.pop(next(iter(data)))
            path = _cache_path(language)
            tmp = f'{path}.{os.getpid()}.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, path)
            _memory[language] = (os.path.getmtime(path), data)
        except Exception as e:
            logger.warning(f"could not write definition cache for {language}: {e}")


def _throttle():
    """Hold upstream fetches at least MIN_FETCH_INTERVAL apart."""
    with _fetch_lock:
        wait = _last_fetch[0] + MIN_FETCH_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last_fetch[0] = time.monotonic()


def _strip_html(html):
    text = re.sub(r'<[^>]+>', '', html or '')
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return ' '.join(text.split())


def fetch_logeion_definition(lemma, language):
    """(definition, dictionary name) from Logeion's Lewis and Short or LSJ, or None."""
    wanted = LOGEION_DICTIONARIES.get(language)
    if not wanted:
        return None
    try:
        q = urllib.parse.urlencode({'type': 'normal', 'w': lemma})
        req = urllib.request.Request(
            f'https://anastrophe.uchicago.edu/logeion-api/detail?{q}',
            headers={'User-Agent': 'Tesserae/6.0'})
        with urllib.request.urlopen(req, timeout=4) as response:  # nosec B310
            data = json.loads(response.read().decode('utf-8'))
        return logeion_entries(data, language)
    except Exception as e:
        logger.debug(f"Logeion lookup failed for {lemma}: {e}")
    return None


MAX_ENTRIES = 3


def logeion_entries(data, language):
    """(definition, dictionary name) from a Logeion detail record, or None.

    A spelling can head more than one entry (Lewis and Short has lābor, to
    slip, and lăbor, toil), and showing only the first sent a reader of
    'labores' to the verb (2026-11-08). Up to MAX_ENTRIES entries of the first
    dictionary that has any are returned, each cut to its share of
    MAX_DEFINITION and separated by a blank line.
    """
    wanted = LOGEION_DICTIONARIES.get(language) or ()
    dicos = {d.get('dname'): d for d in (data.get('detail') or {}).get('dicos') or []}
    for name in wanted:
        texts = []
        for html in (dicos.get(name) or {}).get('es') or []:
            text = re.sub(r'\s*\[cf\.[^\]]*\]', '', _strip_html(html))  # etymology
            if text:
                texts.append(text)
        if not texts:
            continue
        texts = texts[:MAX_ENTRIES]
        share = max(MAX_DEFINITION // len(texts), 120)
        cut = [t if len(t) <= share else t[:share].rstrip() + '…' for t in texts]
        return '\n\n'.join(cut), LOGEION_DISPLAY.get(name, name)
    return None


_ENCLITIC = re.compile(r'^([a-z]{3,}?)(que|ue|ne)$')


def latin_lemma(word):
    """(lemma, enclitic) for a Latin word as the text spells it.

    The lemma table keys its forms the treebank way (u for v, i for j), so
    'virum' is looked up as 'uirum'. A word the table lacks is tried without
    a final -que, -ve or -ne: 'inferretque' is 'inferret' plus -que, and the
    table knows 'inferret'. -que is taken off even when the base is unknown
    (no dictionary lists a -que form); -ve and -ne only when the base is a
    known form, since 'Daphne' and 'breve' end that way on their own.
    """
    folded = word.lower().strip().replace('v', 'u').replace('j', 'i')
    if _known_latin_form(folded):
        return hapax.get_dictionary_lemma(folded, 'la'), None
    m = _ENCLITIC.match(folded)
    if not m:
        return folded, None
    base, enclitic = m.group(1), {'que': 'que', 'ue': 've', 'ne': 'ne'}[m.group(2)]
    if enclitic == 'que' or _known_latin_form(base):
        return hapax.get_dictionary_lemma(base, 'la'), enclitic
    return folded, None


def _known_latin_form(form):
    """True when the Latin lemma table lists the form (as a key)."""
    if not hapax._latin_lemma_table:
        hapax.load_dictionary_tables()
    return form in hapax._latin_lemma_table


def latin_spellings(lemma):
    """The spellings a Latin dictionary may file a table lemma under: as it
    is, then with a consonantal u written v (uir is vir, seruus is servus)."""
    out = [lemma]
    for pattern in (r'(^|[aeiou])u(?=[aeiou])', r'(?<![qg])u(?=[aeiou])'):
        alt = re.sub(pattern, lambda m: m.group(0)[:-1] + 'v', lemma)
        if alt not in out:
            out.append(alt)
    return out


# GREEK. The Greek lemma table is keyed and valued in stripped letters (no
# accents or breathings, σ for ς), the search index's spelling, while LSJ wants
# the headword as spelled: Logeion answers "μῆνις" and nothing to "μηνισ", so
# the first word of the Iliad found no entry (2026-11-08). greek_headwords.json
# (built from the Perseus text of LSJ by scripts/corpus/build_greek_headwords.py)
# gives the accented headwords for each stripped spelling.
HEADWORDS_PATH = os.path.join(_ROOT, 'data', 'lemma_tables', 'greek_headwords.json')
MAX_GREEK_HEADWORDS = 3
_headwords = {}

# A grave accent is the acute of the word's last syllable before another word;
# the dictionary spells the headword with the acute.
_GRAVE_TO_ACUTE = str.maketrans(
    'ὰὲὴὶὸὺὼἂἃἒἓἢἣἲἳὂὃὒὓὢὣᾂᾃᾒᾓᾢᾣᾲῂῲᾺῈῊῚῸῪῺἊἋἚἛἪἫἺἻὊὋὛὪὫ',
    'άέήίόύώἄἅἔἕἤἥἴἵὄὅὔὕὤὥᾄᾅᾔᾕᾤᾥᾴῄῴΆΈΉΊΌΎΏἌἍἜἝἬἭἼἽὌὍὝὬὭ')


def greek_headwords():
    """The stripped-spelling to accented-headwords table, loaded once."""
    if not _headwords:
        try:
            with open(HEADWORDS_PATH, encoding='utf-8') as f:
                _headwords.update(json.load(f))
        except Exception as e:
            logger.warning(f"Greek headword table unreadable: {e}")
            _headwords['__loaded__'] = []
    return _headwords


def greek_form(word):
    """The word as the dictionary spells it: composed characters, acute for grave."""
    return unicodedata.normalize('NFC', word.strip()).translate(_GRAVE_TO_ACUTE)


def strip_greek(word):
    """The lemma table's spelling: no accents or breathings, σ for ς, lower case."""
    nfkd = unicodedata.normalize('NFKD', word)
    return ''.join(c for c in nfkd if not unicodedata.combining(c)).replace('ς', 'σ').lower()


def greek_lemmas(word):
    """The accented headwords to ask the dictionary for, best first.

    The word is stripped to the table's letters and taken to its lemma; the
    lemma's headwords come from the headword table. A word that is itself a
    headword (θεὰ, read as θεά) leads, so a homograph pair (θεά goddess, θέα
    sight) answers with the spelling in the text. A word the table does not
    know is asked for as written."""
    form = greek_form(word)
    stripped = strip_greek(form)
    lemma = hapax.get_dictionary_lemma(stripped, 'grc')
    table = greek_headwords()
    out = list(table.get(lemma) or [])
    if lemma != stripped:
        for hw in table.get(stripped) or []:
            if hw not in out:
                out.append(hw)
    for own in (form, form[:1].upper() + form[1:], form.lower()):
        if own in out:
            out.remove(own)
            out.insert(0, own)
            break
    if not out:
        out = [form]
    return out[:MAX_GREEK_HEADWORDS]


def dictionary_spellings(lemma, language):
    """The spellings to try at the dictionary, in order: the table's lower-case
    lemma (for Latin, with consonantal u written v as well; for Greek, the
    accented headwords of greek_lemmas), then each with a capital. Lewis and Short and LSJ file names under a capital (Troia, Iuno,
    Ἀχιλλεύς) and answer nothing to the lower case, so 'Troiae' in the first
    line of the Aeneid found no entry (2026-11-08)."""
    if language == 'grc':
        base = greek_lemmas(lemma)
    elif language == 'la':
        base = latin_spellings(lemma)
    else:
        base = [lemma]
    out = list(base)
    if language == 'la':
        for s in base:
            c = s[:1].upper() + s[1:]
            if c not in out:
                out.append(c)
    return out


def dictionary_lemma(word, language):
    """(lemma, enclitic) for the word in its language."""
    if language == 'la':
        return latin_lemma(word)
    if language == 'grc':
        return greek_lemmas(word)[0], None
    return word.lower().strip(), None


def logeion_parses(form):
    """The lemmas Logeion's morphological parse gives for a form, in its order,
    without the sense digits it appends (litus3), or []. Used when our own
    tables do not know the form (ψυχὰς, πολύτροπον, Πηληϊάδεω in Homer's
    first lines, 2026-11-08): the parse names the headword to ask for."""
    try:
        q = urllib.parse.urlencode({'w': form})
        req = urllib.request.Request(
            f'https://anastrophe.uchicago.edu/logeion-api/find?{q}',
            headers={'User-Agent': 'Tesserae/6.0'})
        with urllib.request.urlopen(req, timeout=4) as response:  # nosec B310
            data = json.loads(response.read().decode('utf-8'))
        out = []
        for parse in data.get('parses') or []:
            lemma = re.sub(r'\d+$', '', str(parse.get('lemma') or '').strip())
            if lemma and lemma not in out:
                out.append(lemma)
        return out[:MAX_GREEK_HEADWORDS]
    except Exception as e:
        logger.debug(f"Logeion parse failed for {form}: {e}")
        return []


# A short entry that only points at another ("Trōĭa, ae, v. 1. Tros, A.";
# "Διός [ῐ], gen. of Ζεύς.") is followed one step and the target's entry
# shown after it (2026-11-08). Only entries this short are followed, so a full
# article that mentions another word in passing is left alone.
CROSS_REFERENCE_MAX = 200
_CROSS_REFERENCE = (
    re.compile(r'\bv\.\s+(?:\d\.\s+)?([^\s,;.()\[\]]+)'),
    re.compile(r'\b(?:of|from|for)\s+([^\s,;.()\[\]]+)\.?\s*$'),
    re.compile(r'=\s*([^\s,;.()\[\]]+)'),
)


def cross_reference(definition, spelling):
    """The headword a short entry points at, or None."""
    text = (definition or '').strip()
    if not text or len(text) > CROSS_REFERENCE_MAX or '\n' in text:
        return None
    for pattern in _CROSS_REFERENCE:
        m = pattern.search(text)
        if m:
            target = m.group(1).strip('.')
            if target and target.lower() != spelling.lower() and re.search(r'[^\W\d_]', target):
                return target
    return None


def look_up(lemma, language):
    """(definition, dictionary, spelling) for a lemma, or (None, None, lemma).
    Fetches upstream. The spellings in dictionary_spellings are tried in turn,
    then the headwords Logeion's parse gives for them, and the one the
    dictionary answered to is returned. A short cross-reference entry carries
    the entry it points at after it."""
    spellings = dictionary_spellings(lemma, language)
    tried = []
    found = None
    for spelling in spellings:
        tried.append(spelling)
        hit = fetch_logeion_definition(spelling, language)
        if hit:
            found = (hit[0], hit[1], spelling)
            break
    if not found and language in LOGEION_DICTIONARIES:
        for spelling in spellings:
            parsed = [x for x in logeion_parses(spelling) if x not in tried]
            for headword in parsed:
                tried.append(headword)
                hit = fetch_logeion_definition(headword, language)
                if hit:
                    found = (hit[0], hit[1], headword)
                    break
            if found or parsed:
                break
    if found:
        definition, dictionary, spelling = found
        target = cross_reference(definition, spelling)
        if target and target not in tried:
            more = fetch_logeion_definition(target, language)
            if more and more[1] == dictionary:
                definition = f'{definition}\n\n{more[0]}'
        return definition, dictionary, spelling
    _throttle()
    for spelling in spellings:
        definition = hapax.get_definition(spelling, language)
        if definition:
            dictionary = 'Free Dictionary API' if language == 'en' else 'Wiktionary or Perseus'
            return definition, dictionary, spelling
    return None, None, lemma


def define_word(word, language):
    """The route's answer for a word already validated."""
    lemma, enclitic = dictionary_lemma(word, language)
    out = {'word': word, 'lemma': lemma, 'enclitic': enclitic, 'language': language,
           'definition': None, 'dictionary': None,
           'url': dictionary_url(lemma, language), 'cached': False}
    if language not in FETCHED_LANGUAGES:
        out['dictionary'] = EXTERNAL_DICTIONARIES[language][0]
        return out
    hit = _load(language).get(lemma)
    if hit:
        spelling = hit.get('spelling') or lemma
        out.update(definition=hit.get('definition'), dictionary=hit.get('dictionary'),
                   lemma=spelling, url=dictionary_url(spelling, language), cached=True)
        return out
    definition, dictionary, spelling = look_up(lemma, language)
    if definition:
        out.update(definition=definition, dictionary=dictionary,
                   lemma=spelling, url=dictionary_url(spelling, language))
        _store(language, lemma, {'definition': definition, 'dictionary': dictionary, 'spelling': spelling})
    return out


@define_bp.route('/define', methods=['GET'])
def define():
    """
    Define one word.

    Query params:
        word: the word as it stands in the text (required, one word)
        language: la, grc, en, cop, he, fa, ur or ar (default la)
    """
    word = (request.args.get('word') or '').strip()
    language = (request.args.get('language') or 'la').strip()
    if not word:
        return jsonify({'error': 'word is required'}), 400
    if len(word) > MAX_WORD_LENGTH or re.search(r'\s', word) or not re.search(r'[^\W\d_]', word):
        return jsonify({'error': 'word must be a single word of at most 60 characters'}), 400
    if language not in LANGUAGES:
        return jsonify({'error': f"language must be one of {', '.join(LANGUAGES)}"}), 400
    try:
        return jsonify(define_word(word, language))
    except Exception as e:
        logger.error(f"Error in define: {e}")
        return jsonify({'error': 'lookup failed'}), 500
