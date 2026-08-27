"""The searches the assistant is allowed to run, and how it runs them.

The guide half of the assistant could only ever say WHICH search to use, because
it had no corpus access. Asked three times to recommend interesting searches
across Hebrew and Greek, it three times listed tools. This module is what lets it
look instead.

WHY LOOPBACK HTTP RATHER THAN IMPORTING THE SEARCH CODE

The searches are Flask routes, not library functions, and they carry a good deal
of request handling: parameter coercion, text resolution, caching, cancellation.
Calling them over 127.0.0.1 reuses all of that exactly as a browser would, so the
assistant cannot drift from what the site actually does. It also isolates
failures: a search that hangs or dies takes an HTTP timeout with it rather than
the request thread.

WHAT IS DELIBERATELY NOT HERE

No fusion comparison of two large works. That takes minutes, and a model that can
start one will. Only searches that return in seconds are exposed, so the
assistant stays responsive and cannot be made to consume the machine by asking it
an open-ended question.
"""
import json
import urllib.error
import urllib.parse
import urllib.request

from backend.logging_config import get_logger

logger = get_logger('assistant.searches')

# The site talks to itself over loopback. HTTPS with an explicit Host header,
# because Apache serves Tesserae on a name-based virtual host and redirects
# plain HTTP: a bare http://127.0.0.1 request lands on the default vhost and
# 404s. Certificate verification is off because the peer is this machine, reached
# by address, so there is no name to verify and nothing in between to spoof it.
BASE = 'https://127.0.0.1/api'
HOST_HEADER = 'tesserae.caset.buffalo.edu'

# A search the assistant starts must not outlive the patience of the person who
# asked. Anything slower belongs in the interface, where a user can watch it.
TIMEOUT = 25


class SearchError(Exception):
    """A search could not be run. The caller says so rather than inventing."""


def _get(path, params):
    import ssl
    url = f'{BASE}{path}?{urllib.parse.urlencode(params)}'
    req = urllib.request.Request(url, headers={'Host': HOST_HEADER})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SearchError(f'search returned {e.code}') from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise SearchError(str(e)) from e


# --------------------------------------------------------------------------
# The tools, as a schema the model chooses from
# --------------------------------------------------------------------------
# Structured choice, not free text. A model asked to name a tool in prose will
# eventually name one that does not exist, which is the same failure as an
# invented citation and harder to catch. It returns JSON, the name is checked
# against this table, and an unknown name is refused rather than guessed at.
TOOLS = {
    'line_search': {
        # search_type matters more than it looks. Asked where "arma virumque"
        # occurs, a LEMMA search returns every line sharing the lemmas arma and
        # uir -- hundreds of them, ranked so that Aeneid 1.1, the origin of the
        # phrase, falls below position 60 and is invisible at any sane result
        # cap. EXACT puts Aeneid 1.1 first, then Ovid, Seneca and Quintilian
        # quoting it. For a phrase the user has quoted, exact is almost always
        # what they meant.
        'what': 'Find a word or phrase across the whole corpus. Use exact when '
                'the user QUOTES a phrase and wants where it occurs; use lemma '
                'when they want a word in all its inflected forms.',
        'args': {'query': 'the word or phrase, in the original language',
                 'language': 'la, grc, he, cop or en',
                 'search_type': 'exact for a quoted phrase, lemma for a word'},
        'run': lambda a: _get('/line-search', {
            'query': a['query'], 'language': a.get('language', 'la'),
            'search_type': a.get('search_type', 'lemma'),
            # The variant pass asks for more, because a lemma search spreads
            # across far more authors than an exact one and a cap of 60 hid most
            # of them: Eobanus has 35 lines carrying the phrase inflected, and
            # only 5 survived the cap.
            # WHERE to look, when the question named an author. "Can you give
            # the Eobanus instances?" searched the whole corpus and answered
            # with 30 other authors, because the restriction the reader asked
            # for was thrown away between the question and the search.
            **({'author': a['author']} if a.get('author') else {}),
            'max_results': int(a.get('max_results') or 60)}),
    },
    'rare_words': {
        # SAME LANGUAGE ONLY, and the description has to say so. Asked about
        # Hebrew and Greek, the model ran this between Deuteronomy and the Iliad.
        # Hebrew and Greek share no vocabulary, so it returned index artefacts
        # (*lyrcea, aaaicti), and the model then concluded from that failure that
        # the corpus holds no Hebrew at all -- having just been told by
        # list_texts that it holds 39 Hebrew books.
        'what': 'Uncommon single words shared by two named texts IN THE SAME '
                'LANGUAGE. Fast and high precision. Never use it across two '
                'different languages: they share no vocabulary and the result is '
                'meaningless noise, not evidence of absence.',
        'args': {'source': 'source text id', 'target': 'target text id'},
        # /hapax-search, NOT /rare-lemmata.
        #
        # /rare-lemmata returns the raw 273,091-entry rare index in ALPHABETICAL
        # order, so the first thirty are the head of the alphabet, which is OCR
        # debris: *lyrcea, aaa, aaaicti, aaaipsa, aaaxeotou. Tessa reported those
        # as "shared rare terms suggesting allusive engagement".
        #
        # /hapax-search is what the site's own Rare Words search uses, and it
        # works: the same pair returns 186 real results -- alcathoum, belidae,
        # echionium, exsaturabile, interfata, menoetes. I had assumed the site
        # shared the broken endpoint and said so; NC had tested it and knew
        # otherwise. The endpoint was the bug, not the feature.
        'run': lambda a: _get('/hapax-search', {
            'source': a['source'] if str(a['source']).endswith('.tess')
                      else f"{a['source']}.tess",
            'target': a['target'] if str(a['target']).endswith('.tess')
                      else f"{a['target']}.tess",
            'language': a.get('language', 'la'),
            'max_occurrences': int(a.get('max_occurrences') or 10)}),
    },
    'theme_search': {
        # Content, not wording. A thematic question used to reach line_search,
        # which is a search for WORDS: asked for passages about a storm at sea it
        # translated the subject into Greek, searched for the two words, and
        # timed out. The passage index answers descriptions of what happens, and
        # it is the only tool here that crosses languages without a shared word.
        'what': 'Passages whose CONTENT matches a description, across every '
                'language at once. Use for any question about what happens in a '
                'passage -- a theme, a scene, a motif, a situation -- rather '
                'than about particular words. Give a short SENTENCE describing '
                'the scene, not a keyword.',
        'args': {'query': 'a sentence describing what happens in the passage',
                 'languages': 'optional: la, grc, he, cop, en, fa or ur'},
        'run': lambda a: _get('/passages/theme-search', {
            'query': a['query'], 'limit': int(a.get('limit') or 25),
            **({'languages': a['languages']} if a.get('languages') else {})}),
    },
    'list_texts': {
        'what': 'What the corpus actually holds in a language. Use FIRST when '
                'the user asks an open question about a language or period, so '
                'the answer names works that exist.',
        'args': {'language': 'la, grc, he, cop or en'},
        'run': lambda a: _get('/texts', {'language': a.get('language', 'la')}),
    },
}


def tool_menu():
    """The tool list as the model sees it, built from the table above."""
    out = []
    for name, spec in TOOLS.items():
        args = ', '.join(f'{k} ({v})' for k, v in spec['args'].items())
        out.append(f'- {name}: {spec["what"]}\n    arguments: {args}')
    return '\n'.join(out)


_census_cache = {}


def corpus_census():
    """Works per language, always shown to the answering step.

    The fix for a failure that instruction could not stop. Twice the model
    reasoned from "my search returned nothing" to "the corpus contains nothing":
    it listed Hebrew, saw no Greek in the Hebrew listing, and wrote that the
    corpus holds little Greek literature. It holds 703 Greek works.

    A prompt rule against this did not take. So the census is put in front of the
    model on every answer, whatever searches ran. It cannot write that a language
    is absent while looking at the count of works in it.
    """
    if _census_cache:
        return _census_cache
    for code, name in (('la', 'Latin'), ('grc', 'Greek'), ('he', 'Hebrew'),
                       ('cop', 'Coptic'), ('en', 'English')):
        try:
            rows = _get('/texts', {'language': code})
            _census_cache[name] = len(rows) if isinstance(rows, list) else 0
        except SearchError:
            continue
    return _census_cache


def authors_matching(name, language='la'):
    """Work ids and display names for an author, by loose name match.

    Needed so a follow-up like "is it in Eobanus?" can be ANSWERED rather than
    handed back as advice. Without it the assistant had no way to turn a name
    into something searchable.
    """
    hits = []
    try:
        rows = _get('/texts', {'language': language})
    except SearchError:
        return hits
    nl = str(name).lower()
    for r in rows or []:
        if nl in str(r.get('author') or '').lower() or nl in str(r.get('display_name') or '').lower():
            hits.append({'id': r.get('id'), 'display_name': r.get('display_name'),
                         'author': r.get('author')})
    return hits


_listing_cache = {}


def find_works(probes):
    """Which of these names the corpus actually holds, across every language.

    Asked to recommend a comparison of Statius Thebaid 12 with the Aeneid, the
    model replied that the corpus contained neither. It holds 23 Statius entries
    and 14 Aeneid entries. It had been shown a 20-author sample of 1,826 Latin
    works, neither name was in the sample, and it read the sample as the corpus.

    The census stopped this at the language level by putting the real counts in
    front of the model on every answer. This is the same repair at the work
    level: a name in the question is looked up in code, against the actual
    listing, so the model is told the work exists instead of inferring it from a
    sample that was never meant to be exhaustive.

    Returns {probe: [display names]} for what is present, {} for what is not.
    """
    for code in ('la', 'grc', 'he', 'cop', 'en'):
        if code in _listing_cache:
            continue
        try:
            rows = _get('/texts', {'language': code})
            _listing_cache[code] = rows if isinstance(rows, list) else []
        except SearchError:
            _listing_cache[code] = []
    out = {}
    for p in probes:
        pl = p.lower()
        hits = []
        for code, rows in _listing_cache.items():
            for r in rows:
                name = str(r.get('display_name') or '')
                if pl in name.lower() or pl in str(r.get('author') or '').lower():
                    hits.append(name)
        if hits:
            # Shortest first: "Statius, Thebaid" before "Statius, Thebaid, Book 9".
            out[p] = sorted(set(hits), key=len)[:8]
    return out


def run(name, args):
    """Run one chosen search. Raises SearchError; never invents a result."""
    spec = TOOLS.get(name)
    if spec is None:
        raise SearchError(f'no such search: {name}')
    # 'language' and 'languages' are always optional: a search that does not
    # name one has a sensible default, and requiring them made theme_search
    # unusable for the ordinary case of "across everything".
    optional = {'language', 'languages'}
    missing = [k for k in spec['args'] if k not in args and k not in optional]
    if missing:
        raise SearchError(f'{name} needs {missing}')
    logger.info('[ASSISTANT] running %s %s', name, args)
    return spec['run'](args)
