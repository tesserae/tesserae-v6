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
    'grc': ('LSJ', 'Middle Liddell'),
}
LOGEION_DISPLAY = {
    'LewisShort': 'Lewis and Short',
    'LSJ': 'Liddell-Scott-Jones (LSJ)',
    'Middle Liddell': 'Middle Liddell',
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
        dicos = {d.get('dname'): d for d in (data.get('detail') or {}).get('dicos') or []}
        for name in wanted:
            entries = (dicos.get(name) or {}).get('es') or []
            for html in entries:
                text = re.sub(r'\s*\[cf\.[^\]]*\]', '', _strip_html(html))  # etymology
                if text:
                    if len(text) > MAX_DEFINITION:
                        text = text[:MAX_DEFINITION].rstrip() + '…'
                    return text, LOGEION_DISPLAY.get(name, name)
    except Exception as e:
        logger.debug(f"Logeion lookup failed for {lemma}: {e}")
    return None


def look_up(lemma, language):
    """(definition, dictionary) for a lemma, or (None, None). Fetches upstream."""
    found = fetch_logeion_definition(lemma, language)
    if found:
        return found
    _throttle()
    definition = hapax.get_definition(lemma, language)
    if not definition:
        return None, None
    if language == 'en':
        return definition, 'Free Dictionary API'
    return definition, 'Wiktionary or Perseus'


def define_word(word, language):
    """The route's answer for a word already validated."""
    lemma = hapax.get_dictionary_lemma(word, language) if language in ('la', 'grc') else word.lower().strip()
    out = {'word': word, 'lemma': lemma, 'language': language,
           'definition': None, 'dictionary': None,
           'url': dictionary_url(lemma, language), 'cached': False}
    if language not in FETCHED_LANGUAGES:
        out['dictionary'] = EXTERNAL_DICTIONARIES[language][0]
        return out
    hit = _load(language).get(lemma)
    if hit:
        out.update(definition=hit.get('definition'), dictionary=hit.get('dictionary'), cached=True)
        return out
    definition, dictionary = look_up(lemma, language)
    if definition:
        out.update(definition=definition, dictionary=dictionary)
        _store(language, lemma, {'definition': definition, 'dictionary': dictionary})
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
