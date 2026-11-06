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
        # A fixed http(s) endpoint from configuration, never user input.
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:  # nosec B310
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise SearchError(f'search returned {e.code}') from e
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise SearchError(str(e)) from e


def _base_id(work):
    """A work id without its .tess suffix and without a book: the one-text scope of Theme Search passes this."""
    from backend.work_names import base_work
    return base_work(str(work or ''))


def _one_text(a):
    """Theme Search restricted to one work: the request the one-text scope of Theme Search makes."""
    params = {'q': a['query'], 'works': _base_id(a['work']), 'limit': int(a.get('limit') or 25)}
    if a.get('languages'):
        params['languages'] = a['languages']
    if a.get('books'):
        params['books'] = a['books']
    return _get('/passages/theme-search', params)


def _people_places(a):
    """The People & Places search for a name, with the full entry of each entry it means (three at most)."""
    from backend.assistant import three_searches
    name = str(a['name']).strip()
    search = _get('/entities/search', {'q': name})
    entries, _exact = three_searches.match_entities(name, search)
    if entries and a.get('pick_index') is not None:
        entries = [entries[min(int(a['pick_index']), len(entries) - 1)]]
    details = {}
    for e in entries[:3]:
        try:
            details[e['id']] = _get('/entities/' + urllib.parse.quote(str(e['id']), safe=':'), {})
        except SearchError as ex:
            logger.info('[ASSISTANT] entry %s unreadable: %s', e.get('id'), ex)
    return {'search': search, 'details': details}


def _events(a):
    """The Events search by name (the full title first, then the name alone), and the dossier of a single match."""
    import re
    lst = {}
    for q in [x for x in (a.get('label'), a['name']) if x]:
        lst = _get('/events', {'q': q, 'per_page': 8, 'sort': 'evidence'})
        if q == a['name'] and lst.get('events'):
            # The route matches letters inside a word (Troy finds Troyes). A name alone must be a whole
            # word of the event's title or of its place, ancient or modern.
            word = re.compile(r'\b' + re.escape(q.lower()) + r'\b')
            keep = [e for e in lst['events']
                    if any(word.search(str(e.get(k) or '').lower()) for k in ('label', 'place', 'place_ancient'))]
            if len(keep) != len(lst['events']):
                lst = dict(lst, events=keep, total=len(keep))
        if lst.get('events'):
            break
    if a.get('year') is not None and len(lst.get('events') or []) > 1:
        # The reader chose one of several events of this name by its year (three_searches.event_choice).
        lo, hi = int(a['year']), int(a.get('year_to', a['year']))
        keep = [e for e in lst['events'] if e.get('date_start') is not None
                and min(e['date_start'], e.get('date_end') or e['date_start']) <= hi
                and max(e['date_start'], e.get('date_end') or e['date_start']) >= lo]
        if keep:
            lst = dict(lst, events=keep, total=len(keep))
    detail = coins = None
    if len(lst.get('events') or []) == 1:
        eid = urllib.parse.quote(str(lst['events'][0]['id']))
        detail = _get('/events/' + eid, {})
        try:
            # The event page's Coins tab. It needs the encoder, so a failure leaves the coins out, never the event.
            coins = _get('/events/' + eid + '/coins', {})
        except SearchError:
            coins = None
    return {'list': lst, 'detail': detail, 'coins': coins}


_FINDSPOT_ALIASES = {'rome': 'Roma'}
_mint_cache = {}


def _findspot(name, language):
    """The Place control's value for a findspot a reader named, or None. The list is the page's own (/documents/places).

    The list spells places the way the editions do (Oxyrhynchos, Roma), so the name is looked up by its stem too
    (Oxyrhynch) and the commonest place that begins with it is taken. A place spelled exactly as typed is taken
    when it holds a fifth or more of the documents the commonest does: the list holds a few stray spellings
    (one "Oxyrhynchus" among 4,400 documents from Oxyrhynchos) that hold nothing worth searching.
    """
    from backend.assistant.three_searches import fold
    name = _FINDSPOT_ALIASES.get(fold(name), name)
    want = fold(name)
    stem = fold(name[:-2] if len(name) >= 7 else name)
    found = {}
    for q in dict.fromkeys((name, stem)):
        listing = _get('/documents/places', {'q': q, 'language': language or '', 'limit': 12})
        for p in listing.get('places') or []:
            if isinstance(p, dict) and p.get('value') and (fold(p['value']).startswith(stem)
                                                           or want in (fold(p['value']), fold(p.get('modern')))):
                found[p['value']] = int(p.get('count') or 0)
    if not found:
        return None
    best = max(found, key=lambda v: found[v])
    exact = [v for v in found if want in (fold(v),)]
    if exact and found[exact[0]] * 5 >= found[best]:
        return exact[0]
    return best


def _mint_value(name):
    """The Coins page's mint value for a mint a reader named, or None. The list is the page's own (/coins/facets)."""
    from backend.assistant.three_searches import fold
    if not _mint_cache:
        for m in (_get('/coins/facets', {}).get('facets') or {}).get('mint') or []:
            _mint_cache[m['value']] = int(m.get('count') or 0)
    want = fold(name)
    exact = [v for v in _mint_cache if fold(v) == want]
    if exact:
        return exact[0]
    near = sorted((v for v in _mint_cache if fold(v).startswith(want)), key=lambda v: -_mint_cache[v])
    return near[0] if near else None


def _documents(a):
    """The Inscriptions & Papyri search: the request the page makes (documents only, dictionary forms), with the
    page's own retry on the letters for one word that is no dictionary form."""
    place = None
    if a.get('place'):
        place = _findspot(str(a['place']), a.get('language'))
        if not place:
            return {'search': None, 'place': None}
    params = {'collection': 'documents', 'query': a['query'], 'language': a.get('language') or 'la',
              'search_type': 'lemma', 'limit': int(a.get('limit') or 8)}
    if a.get('kind'):
        params['kind'] = a['kind']
    if place:
        params['doc_place'] = place
    for k in ('date_from', 'date_to'):
        if a.get(k) is not None:
            params[k] = int(a[k])
    resp = _get('/line-search', params)
    used = 'lemma'
    if not resp.get('total') and ' ' not in str(a['query']).strip():
        retry = _get('/line-search', dict(params, search_type='exact'))
        if retry.get('total'):
            resp, used = retry, 'exact'
    return {'search': resp, 'place': place, 'type': used}


def _coins(a):
    """The Coins search: the page's own request. A mint the reader named is the Mint filter when the page lists it,
    and a word of the search when it does not; a denomination is the Denomination filter."""
    params = _collection_params(a)
    mint = _mint_value(a['mint']) if a.get('mint') else None
    if a.get('mint') and not mint:
        params['q'] = (params['q'] + ' ' + str(a['mint'])).strip()
    if mint:
        params['mint'] = mint
    if a.get('denomination'):
        params['denomination'] = a['denomination']
    return {'search': _get('/coins', params), 'mint': mint, 'query': params['q']}


def _collection_params(a):
    params = {'q': a['query'], 'per_page': int(a.get('limit') or 8)}
    for k in ('date_from', 'date_to'):
        if a.get(k) is not None:
            params[k] = int(a[k])
    return params


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
        # echionium, exsaturabile, interfata, menoetes. The initial assumption
        # that the site shared the broken endpoint was wrong. Testing showed
        # the endpoint itself was the bug. The feature worked fine.
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
    'theme_compare': {
        'what': 'Two works or books read against each other by CONTENT: every '
                'passage of one scored against every passage of the other on '
                'the Similar Passages vectors, the best pairs returned with both '
                'descriptions. Use when a question asks what two named texts '
                'share in theme, scene or situation rather than in wording. '
                'Works across languages.',
        'args': {'work_a': 'work id of the first text (see list_texts)',
                 'work_b': 'work id of the second text',
                 'limit': 'optional, pairs to return (default 25)'},
        'run': lambda a: _get('/passages/compare', {
            'work_a': a['work_a'], 'work_b': a['work_b'],
            'limit': int(a.get('limit') or 25)}),
    },
    'one_text_search': {
        'what': 'Theme Search on one text: the passages of ONE work (or one book of it) that match a subject, found '
                'by content and not by wording. Use when a question names a single work and asks what it '
                'says about something ("what does the Aeneid say about storms?").',
        'args': {'work': 'work id of the one text (see list_texts)',
                 'query': 'the subject, in plain words',
                 'books': 'optional: a book number or range such as 6 or 1-6'},
        'run': _one_text,
    },
    'people_places': {
        'what': 'People & Places: look up a person, place or god by name and report its entry, how many '
                'lines and works name it and which works name it most. Use for "where is X mentioned?" '
                'and "which works name X?".',
        'args': {'name': 'the name, as a reader would write it'},
        'run': _people_places,
    },
    'events': {
        'what': 'Events: look up a battle, siege, treaty or campaign by name and report its date, place and '
                'how much the corpus says of it. Use for "what do the sources say about the battle of X?".',
        'args': {'name': 'the place or name of the event, such as Actium',
                 'label': 'optional: the full title, such as Battle of Actium'},
        'run': _events,
    },
    'documents_search': {
        'what': 'Inscriptions & Papyri: the documents (Latin and Greek inscriptions and papyri) whose own words '
                'match, with their edition, date, findspot and matching line. Use for "find inscriptions that '
                'mention Augustus" or "papyri about grain from Oxyrhynchus". The words are searched as they stand '
                'on the stone or papyrus, so give them in Latin or Greek.',
        'args': {'query': 'the words to find, in Latin or Greek',
                 'language': 'la or grc',
                 'kind': 'optional: inscriptions or papyri',
                 'place': 'optional: the findspot, such as Pompeii',
                 'date_from': 'optional: first year, negative for BC',
                 'date_to': 'optional: last year'},
        'run': _documents,
    },
    'coins_search': {
        'what': 'Coins: Greek and Roman coin types whose legends and descriptions match the words, with legend, '
                'mint and date. Use for "coins of Hadrian with Felicitas" or "coin types showing an elephant".',
        'args': {'query': 'the words, in English as the catalogues describe them, or a legend',
                 'mint': 'optional: the mint, such as Rome',
                 'denomination': 'optional: Denarius, Sestertius, Aureus, Tetradrachm, Stater',
                 'date_from': 'optional: first year, negative for BC',
                 'date_to': 'optional: last year'},
        'run': lambda a: _coins(a),
    },
    'objects_search': {
        'what': 'Objects: Greek, Roman and Etruscan museum objects whose museum descriptions match the words, with '
                'museum, date and title. Use for "museum objects showing Medusa" or "Etruscan mirrors".',
        'args': {'query': 'the words, in English as the museums describe them',
                 'date_from': 'optional: first year, negative for BC',
                 'date_to': 'optional: last year'},
        'run': lambda a: _get('/objects', _collection_params(a)),
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


def fusion_page(source, target, language, limit=25):
    """One page of the full comparison, or None while it is still running.

    The fusion route answers a cached pair at once and otherwise starts the
    run and says so. Ids need their .tess suffix here.
    """
    def _id(x):
        x = str(x or '')
        return x if x.endswith('.tess') else x + '.tess'
    data = _get('/fusion-search', {'source': _id(source), 'target': _id(target),
                                   'language': language or 'la', 'limit': int(limit)})
    if isinstance(data, dict) and data.get('status') == 'complete':
        # The route names its page 'parallels'; older callers read 'results'.
        return data.get('parallels') or data.get('results') or []
    return None


def translations_available(language):
    """{work: {attribution, coverage, confidence}} for the works of a language
    that have an aligned translation, from the route Browse Corpus reads."""
    data = _get('/passages/translations', {'language': language})
    works = data.get('works') if isinstance(data, dict) else None
    return works if isinstance(works, dict) else {}


def crosslingual_page(source, target, source_language, target_language, limit=25):
    """One page of the Cross-Language comparison, or None while it runs.

    Same shape as fusion_page, for a pair of texts in two languages. It calls
    the polled route the Cross-Language tab's search is cached through.
    """
    def _id(x):
        x = str(x or '')
        return x if x.endswith('.tess') else x + '.tess'
    data = _get('/crosslingual-search-poll', {
        'source': _id(source), 'target': _id(target),
        'source_language': source_language, 'target_language': target_language,
        'limit': int(limit)})
    if isinstance(data, dict) and data.get('status') == 'complete':
        return data.get('parallels') or data.get('results') or []
    return None


def run(name, args):
    """Run one chosen search. Raises SearchError; never invents a result."""
    spec = TOOLS.get(name)
    if spec is None:
        raise SearchError(f'no such search: {name}')
    # 'language' and 'languages' are always optional: a search that does not
    # name one has a sensible default, and requiring them made theme_search
    # unusable for the ordinary case of "across everything".
    optional = {'language', 'languages', 'books', 'label', 'kind', 'place', 'date_from', 'date_to', 'mint', 'denomination'}
    missing = [k for k in spec['args'] if k not in args and k not in optional]
    if missing:
        raise SearchError(f'{name} needs {missing}')
    logger.info('[ASSISTANT] running %s %s', name, args)
    return spec['run'](args)
