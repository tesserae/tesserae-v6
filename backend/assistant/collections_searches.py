"""Three more searches Tessa runs herself: Inscriptions & Papyri, Coins, Objects.

The pages of the site's collections each have a plain search behind them. A
visitor can ask in a sentence ("find inscriptions that mention Augustus", "coins
of Hadrian with Felicitas", "museum objects showing Medusa") and get the page's
own answer, with a control that opens the page on the same search.

Built the way three_searches.py builds Search One Text, People & Places and
Events, and kept beside it so that module stays readable:

    detection   which questions reach each search, decided in code from the
                reader's words. The signal is a collection word (inscriptions,
                papyri, coins, museum objects), and the question must also hold
                something to look for. A question about the page, a comparison,
                a theme or a named work keeps its old route.
    summaries   the facts the model writes from, computed and compact. A count
                is the page's own total. Every reference is a field a route
                returned (the edition of a document written out as the page
                writes it, a coin's catalogue title, an object's title).
    code        the answer when nothing matched, written without the model.

The searches themselves are in `searches.TOOLS` (`documents_search`,
`coins_search`, `objects_search`), run over the same loopback requests as the
others.
"""
import re

from backend.assistant.three_searches import KIND_COLLECTION, KIND_NONE, date_label, fold
from backend.logging_config import get_logger

logger = get_logger('assistant.collections_searches')

DOCUMENTS = 'documents_search'
COINS = 'coins_search'
OBJECTS = 'objects_search'
NAMES = (DOCUMENTS, COINS, OBJECTS)

SHOWN = 5
TEXT_CHARS = 200

# --------------------------------------------------------------------------
# The edition of a document, written out as the page writes it
# --------------------------------------------------------------------------
# A port of client/src/utils/editionNames.js (the project lead, 2026-10-20: "We
# have the room to spell things out."). tests/test_assistant_collections_searches.py
# compares this table with the one in that file, so the two cannot drift apart.
EDITION_NAMES = {
    'AE': "L'Année épigraphique",
    'CIL': 'Corpus Inscriptionum Latinarum',
    'CIG': 'Corpus Inscriptionum Graecarum',
    'CIS': 'Corpus Inscriptionum Semiticarum',
    'IG': 'Inscriptiones Graecae',
    'IGUR': 'Inscriptiones Graecae Urbis Romae',
    'IGRR': 'Inscriptiones Graecae ad Res Romanas Pertinentes',
    'IGASM': 'Iscrizioni greche arcaiche di Sicilia e Magna Grecia',
    'IGDS': 'Inscriptions grecques dialectales de Sicile',
    'ILS': 'Inscriptiones Latinae Selectae',
    'ILLRP': 'Inscriptiones Latinae Liberae Rei Publicae',
    'ILJug': 'Inscriptiones Latinae quae in Iugoslavia repertae sunt',
    'ILBulg': 'Inscriptiones Latinae in Bulgaria repertae',
    'ILAlg': "Inscriptions latines de l'Algérie",
    'ILTun': 'Inscriptions latines de la Tunisie',
    'ICUR': 'Inscriptiones Christianae Urbis Romae',
    'InscrIt': 'Inscriptiones Italiae',
    'IDR': 'Inscriptiones Daciae Romanae',
    'IMS': 'Inscriptions de la Mésie Supérieure',
    'IScM': 'Inscriptiones Scythiae Minoris',
    'IRT': 'The Inscriptions of Roman Tripolitania',
    'RIB': 'The Roman Inscriptions of Britain',
    'RIU': 'Die römischen Inschriften Ungarns',
    'OGIS': 'Orientis Graeci Inscriptiones Selectae',
    'SEG': 'Supplementum Epigraphicum Graecum',
    'Syll.': 'Sylloge Inscriptionum Graecarum',
    'EphEp': 'Ephemeris Epigraphica',
    'Not. Sc.': 'Notizie degli Scavi di Antichità',
    'NSA': 'Notizie degli Scavi di Antichità',
    'SB': 'Sammelbuch griechischer Urkunden aus Ägypten',
    'BGU': 'Berliner Griechische Urkunden',
    'SPP': 'Studien zur Palaeographie und Papyruskunde',
    'PSI': 'Papiri greci e latini (Società Italiana)',
    'BASP': 'Bulletin of the American Society of Papyrologists',
    'P.Oxy.': 'The Oxyrhynchus Papyri',
    'P.Tebt.': 'The Tebtunis Papyri',
    'P.Lond.': 'Greek Papyri in the British Museum',
    'P.Mich.': 'Michigan Papyri',
    'P.Col.': 'Columbia Papyri',
    'P.Petr.': 'The Flinders Petrie Papyri',
    'P.Gurob': 'Greek Papyri from Gurob',
    'P.Brux.': 'Papyri Bruxellenses',
    'P.Cair. Zen.': 'Zenon Papyri in the Cairo Museum',
    'O.Mich.': 'Ostraca in the University of Michigan Collection',
    'O.Masada': 'Ostraca from Masada',
}
_EDITION_PATTERN = re.compile(
    '(^|[\\s;(–-])(' + '|'.join(re.escape(k) for k in sorted(EDITION_NAMES, key=len, reverse=True))
    + ')(?=[\\s\\d,.)]|$)')


def expand_editions(text):
    """The edition line with each known abbreviation written out, as the page writes it."""
    if not text:
        return text
    return _EDITION_PATTERN.sub(lambda m: f'{m.group(1)}{EDITION_NAMES[m.group(2)]} ({m.group(2)})', str(text))


# --------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------
_DOC_SIGNAL = re.compile(r'\b(?:inscriptions?|papyri|papyrus|ostraca|ostracon|graffiti|graffito|epigraphic)\b', re.I)
_COIN_SIGNAL = re.compile(
    r'\b(?:coins?|coinage|denarii|denarius|sestertii|sestertius|tetradrachms?|drachms?|staters?|aurei|aureus)\b', re.I)
_OBJECT_SIGNAL = re.compile(
    r'\bmuseums?\b|\b(?:ancient|greek|roman|etruscan|museum)\s+objects?\b|\bobjects?\s+(?:showing|depicting|decorated|'
    r'with|bearing|featuring)\b', re.I)
# A culture with a kind of object and nothing else ("Etruscan mirrors"): a short question only.
_OBJECT_TYPES = (r'mirrors?|vases?|lamps?|helmets?|statuettes?|figurines?|gems?|cameos?|bronzes?|amphorae?|'
                 r'kraters?|kylikes|kylix|hydriai|hydria|oinochoai|oinochoe|urns?|sarcophag(?:us|i)|reliefs?|'
                 r'jewel(?:ry|lery)|rings?|fibulae?|situlae?|cists?|pyxides|pyxis|terracottas?|mosaics?')
_CULTURE_OBJECT = re.compile(
    r'^\s*(?:(?:show|find|list|give)\s+me\s+|are\s+there\s+any\s+|any\s+)?(?:the\s+)?'
    r'(?:greek|roman|etruscan|egyptian|cypriot|hellenistic|attic|corinthian)\s+(?:[a-z\-]+\s+)?(?:' + _OBJECT_TYPES
    + r')\s*\??\s*$', re.I)

# A question about the page, the site or the data, not a search of the collection: the guide answers.
_ABOUT_THE_SITE = re.compile(
    r"\b(?:pages?|tabs?|features?|buttons?|filters?|menu|tessa|help|includes?|included)\b|^\s*(?:does|can|could|may)\b|\bhow (?:do|can|could|would|should) (?:i|we)\b|"
    r"\bdo you (?:have|hold|cover)\b|\bdoes (?:tesserae|the site|the corpus|it|this)\b|\bcome from\b|"
    r"\blicen[cs]es?\b|\bdownloads?\b|\bcatalogues?\b|\bsources? (?:of|for)\b|\bwhat (?:is|are) (?:an? |the )?"
    r"(?:inscriptions?|papyri|papyrus|coins?|museum objects?|objects?)\s*[?&]|\bwhat kinds? of\b",
    re.I)
_OTHER_SEARCH = ('compare', 'comparing', 'versus', ' vs ', 'parallel', 'echo', 'allusion', 'theme search',
                 'similar passages')

_STOP = set('''a an the of in on at from to for with without by and or that which who whom whose what where when how
why is are was were be been do does did can could would will you me i we us any some all show shows showed find
finds found list lists give get gets search look looking tell about mention mentions mentioned mentioning
naming named name names containing contain contains phrase phrases word words reading read reads says say saying
showing depicting depict depicts bearing bear bears featuring feature features there here please like have has
having many much types type kind kinds examples example ones one made minted mint these those it its their them
also only just other another both either each every more most new use used using call called calling carry
carrying hold holding holds mark marked marks record records recorded written write writes text texts line lines
about around concerning regarding relating related into onto over under between among through during while
but so if then than too very really still yet ever never always often sometimes may might must shall should
'''.split())
_SIGNAL_WORDS = set('''inscription inscriptions papyri papyrus ostraca ostracon graffiti graffito epigraphic coin coins
coinage denarii denarius sestertii sestertius tetradrachm tetradrachms drachm drachms stater staters aurei aureus museum
museums object objects collection collections'''.split())
_DENOMINATIONS = {'denarii': 'Denarius', 'denarius': 'Denarius', 'sestertii': 'Sestertius', 'sestertius': 'Sestertius',
                  'aurei': 'Aureus', 'aureus': 'Aureus', 'tetradrachm': 'Tetradrachm', 'tetradrachms': 'Tetradrachm',
                  'drachm': 'Drachma', 'drachms': 'Drachma', 'stater': 'Stater', 'staters': 'Stater'}
_MINT = re.compile(
    r"\b(?:minted|struck|made)\s+(?:at|in)\s+(?:the\s+)?(?P<m>[A-Z][\w'\u2019\-]*(?:\s+[A-Z][\w'\u2019\-]*)?)|"
    r"\b(?:from|of)\s+the\s+mint\s+(?:of|at)\s+(?P<m2>[A-Z][\w'\u2019\-]*(?:\s+[A-Z][\w'\u2019\-]*)?)")
_LANGUAGE_WORDS = {'latin': 'la', 'greek': 'grc'}
_ORDINALS = {'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5, 'sixth': 6, 'seventh': 7, 'eighth': 8,
             'ninth': 9, 'tenth': 10}
_CENTURY = re.compile(
    r'\b(?:in\s+|from\s+|of\s+|during\s+)?(?:the\s+)?(?P<n>\d{1,2}(?:st|nd|rd|th)|' + '|'.join(_ORDINALS) +
    r')[\s-]+century(?:\s+(?P<era>BCE|BC|CE|AD|B\.C\.E\.|B\.C\.|A\.D\.|C\.E\.))?', re.I)
_PLACE = re.compile(
    r"\b(?:from|at|in|near)\s+(?:the\s+)?(?P<p>[A-Z][\w'’\-]*(?:\s+[A-Z][\w'’\-]*)?)")
_PLACE_SKIP = {'latin', 'greek', 'english', 'roman', 'the', 'ad', 'bc', 'bce', 'ce'}
_PHRASE_MARK = re.compile(r'\b(?:phrase|phrases|words|formula|reading|reads|inscribed|text)\b|["“‘]', re.I)
_GREEK = re.compile(r'[Ͱ-Ͽἀ-῿]')


def _century(question):
    """(date_from, date_to, span_text) for "the 2nd century AD", else None. Years are signed, BCE negative."""
    m = _CENTURY.search(question)
    if not m:
        return None
    raw = m.group('n').lower()
    n = _ORDINALS.get(raw) or int(re.sub(r'\D', '', raw))
    era = (m.group('era') or 'CE').upper().replace('.', '')
    if n < 1 or n > 20:
        return None
    if era in ('BCE', 'BC'):
        return -n * 100, -((n - 1) * 100 + 1), m.group(0)
    return (n - 1) * 100 + 1, n * 100, m.group(0)


def _singular(word):
    """"mirrors" to "mirror": the page's search matches the start of a word, so the shorter form finds both.
    A name (Felicitas) is left as it was typed."""
    if word[:1].isupper():
        return word
    if len(word) > 4 and word.lower().endswith('s') and not word.lower().endswith(('ss', 'us', 'is')):
        return word[:-1]
    return word


def _signal(question):
    kinds = []
    if _DOC_SIGNAL.search(question):
        kinds.append(DOCUMENTS)
    if _COIN_SIGNAL.search(question):
        kinds.append(COINS)
    if _OBJECT_SIGNAL.search(question) or _CULTURE_OBJECT.match(question):
        kinds.append(OBJECTS)
    return kinds


def _words(text, drop_languages):
    out = []
    for w in re.findall(r"[\w’'\-]+", text):
        low = fold(w)
        if low in _STOP or low in _SIGNAL_WORDS:
            continue
        if drop_languages and low in _LANGUAGE_WORDS:
            continue
        out.append(w.strip("'’-"))
    return [w for w in out if w]


def collection_request(question):
    """A request dict for a question that asks to find something in the inscriptions and papyri, the coins or the objects, else None.

    {'search', 'subject' (the words as asked), 'words' (the words to search for),
    'language', 'kind', 'place', 'date_from', 'date_to', 'phrase'}. The question
    must hold a collection word and at least one thing to look for. A question
    about the page or the data, a comparison, and a question naming two collections
    are left to the routes they had.
    """
    q = re.sub(r'\s+', ' ', str(question or '')).strip()
    if not q or len(q) > 400:
        return None
    low = q.lower()
    if _ABOUT_THE_SITE.search(q) or any(w in low for w in _OTHER_SEARCH):
        return None
    kinds = _signal(q)
    if len(kinds) != 1:
        return None
    which = kinds[0]
    rest = q
    century = _century(rest)
    if century:
        rest = rest.replace(century[2], ' ')
    req = {'search': which, 'language': None, 'kind': '', 'place': '', 'date_from': None, 'date_to': None,
           'phrase': False}
    if century:
        req['date_from'], req['date_to'] = century[0], century[1]
    if which == DOCUMENTS:
        for m in _PLACE.finditer(rest):
            place = m.group('p')
            if fold(place).split()[0] in _PLACE_SKIP:
                continue
            req['place'] = place
            rest = rest.replace(m.group(0), ' ')
            break
        for w in re.findall(r'[A-Za-z]+', rest):
            if fold(w) in _LANGUAGE_WORDS:
                req['language'] = _LANGUAGE_WORDS[fold(w)]
                break
        has_i, has_p = re.search(r'\binscriptions?\b|\bepigraphic\b', rest, re.I), re.search(
            r'\bpapyri\b|\bpapyrus\b|\bostrac', rest, re.I)
        if has_i and not has_p:
            req['kind'] = 'inscriptions'
        elif has_p and not has_i:
            req['kind'] = 'papyri'
    if which == COINS:
        for w in re.findall(r'[A-Za-z]+', rest):
            if w.lower() in _DENOMINATIONS:
                req['denomination'] = _DENOMINATIONS[w.lower()]
                break
        m = _MINT.search(rest)
        if m:
            req['mint'] = m.group('m') or m.group('m2')
            rest = rest.replace(m.group(0), ' ')
    words = _words(rest, drop_languages=(which == DOCUMENTS))
    if which != DOCUMENTS and fold(' '.join(words)) in ('roman', 'greek'):
        words = []                                   # a culture alone is not something to look for
    if not words and not req.get('mint'):
        return None
    req['subject'] = ' '.join(words[:6])
    req['phrase'] = bool(_PHRASE_MARK.search(q)) or bool(_GREEK.search(req['subject']))
    if which == DOCUMENTS:
        if not req['language']:
            req['language'] = 'grc' if (_GREEK.search(req['subject']) or req['kind'] == 'papyri') else 'la'
        req['words'] = req['subject']
    else:
        req['words'] = ' '.join(_singular(w) for w in words[:6])
    if not req['subject'] and which == COINS:
        req['subject'] = req.get('mint') or req.get('denomination') or ''
    return req


def corpus_words(subject, language):
    """The Latin or Greek words to search for, from the English subject a reader typed. None when the model cannot say.

    The documents are searched by their own words, so "grain" is searched as
    sitos and "Hadrian" as Hadrianus. The answer says which words were searched.
    """
    from backend.assistant import model
    name = 'Greek' if language == 'grc' else 'Latin'
    text = model.complete(
        f'You turn a short English subject into the {name} words to search for in a collection of ancient '
        f'{name} inscriptions and papyri. Reply with the {name} dictionary forms only, one to three words '
        'separated by single spaces, with no punctuation and no explanation. A name of a person or place is '
        f'written in its {name} nominative form.',
        f'Subject: {subject}', max_tokens=24, temperature=0.0)
    if not text:
        return None
    first = re.sub(r'[^\w\sͰ-Ͽἀ-῿]', ' ', text.splitlines()[0])
    words = first.split()
    if not 1 <= len(words) <= 3:
        return None
    if language == 'grc' and not _GREEK.search(first):
        return None
    if language != 'grc' and _GREEK.search(first):
        return None
    return ' '.join(words)


def search_args(req):
    """The arguments of the search tool for a request, translating an English subject for the documents."""
    which = req['search']
    if which == DOCUMENTS:
        words = req['words']
        if not req['phrase']:
            words = corpus_words(req['subject'], req['language']) or words
        args = {'query': words, 'language': req['language']}
        if fold(words) != fold(req['subject']):
            args['asked_as'] = req['subject']
        for k in ('kind', 'place'):
            if req.get(k):
                args[k] = req[k]
    else:
        args = {'query': req['words']}
        for k in ('mint', 'denomination'):
            if req.get(k):
                args[k] = req[k]
    for k in ('date_from', 'date_to'):
        if req.get(k) is not None:
            args[k] = req[k]
    return args


# --------------------------------------------------------------------------
# Facts
# --------------------------------------------------------------------------
def _date_span(args):
    if args.get('date_from') is None and args.get('date_to') is None:
        return ''
    return date_label(args.get('date_from'), args.get('date_to'))


def _clip(text, n=TEXT_CHARS):
    s = re.sub(r'\s+', ' ', str(text or '')).strip()
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + '...'


def _doc_date(r):
    nb, na = r.get('date_not_before'), r.get('date_not_after')
    if nb is None and na is None:
        return ''

    def fmt(y):
        return f'{-y} BC' if y < 0 else f'{y} AD'
    if nb is not None and na is not None and nb != na:
        return f'{fmt(nb)} to {fmt(na)}'
    return fmt(nb if nb is not None else na)


_ABBREVIATED_PLACE = ((re.compile(r'\bHr\.\s*'), 'Henchir '), (re.compile(r'\bKh\.\s*'), 'Khirbet '))


def _doc_place(r):
    place = r.get('ancient_place') or r.get('modern_place') or ''
    for pat, word in _ABBREVIATED_PLACE:
        place = pat.sub(word, place)
    return place


_UNKNOWN = {'unknown', 'unbekannt', '?', 'n/a', 'none'}


def _none(which, args, note, searched):
    return {'kind': KIND_NONE, 'search': which, 'args': args, 'what_was_searched': searched, 'note': note}


def _documents_searched(args):
    bits = [f"words '{args.get('query')}'", 'Latin' if args.get('language') != 'grc' else 'Greek']
    if args.get('kind'):
        bits.append(args['kind'])
    if args.get('place'):
        bits.append(f"findspot {args['place']}")
    if _date_span(args):
        bits.append(_date_span(args))
    return 'Inscriptions & Papyri, ' + ', '.join(bits)


def summarise_documents(bundle, args):
    """Facts for an Inscriptions & Papyri search, from {'search': /line-search response, 'place': ..., 'type': ...}."""
    bundle = bundle if isinstance(bundle, dict) else {}
    if bundle.get('place'):
        args = dict(args, place=bundle['place'])             # the page's spelling of the findspot
    searched = _documents_searched(args)
    if args.get('place') and not bundle.get('place'):
        return _none(DOCUMENTS, args, f"The findspot list holds no place called {args['place']}.", searched)
    resp = bundle.get('search') or {}
    rows = [r for r in (resp.get('results') or []) if r.get('collection') == 'documents']
    total = int(resp.get('total') or 0)
    if resp.get('error') or not rows or not total:
        return _none(DOCUMENTS, args, 'No inscription or papyrus matches these words and filters.', searched)
    used = dict(args, search_type=bundle.get('type') or 'lemma')
    examples, seen = [], set()
    for r in rows:
        if r.get('doc_id') in seen:                              # a document with several matching lines is listed once
            continue
        seen.add(r.get('doc_id'))
        if len(examples) == SHOWN:
            break
        credit = r.get('credit') or {}
        edition = expand_editions(credit.get('principal_edition')) or r.get('doc_id')
        labels = [x for x in (r.get('text_type_label'), r.get('object_type_label'), r.get('material_label'))
                  if x and str(x).strip().lower() not in _UNKNOWN]
        ex = {'ref': edition, 'date': _doc_date(r), 'findspot': _doc_place(r), 'region': r.get('region') or '',
              'kind_of_document': ', '.join(labels), 'matching_line': _clip(r.get('text'))}
        examples.append({k: v for k, v in ex.items() if v})
    fact = {
        'kind': KIND_COLLECTION, 'search': DOCUMENTS, 'args': used,
        'collection': 'Inscriptions & Papyri',
        'words_searched': args.get('query'),
        'language_searched': 'Greek' if args.get('language') == 'grc' else 'Latin',
        'documents_found': total,
        'examples_note': f'only the first {len(examples)} of {total} documents are listed; the total is documents_found',
        'examples': examples,
    }
    if args.get('asked_as'):
        fact['asked_as'] = args['asked_as']
    if args.get('kind'):
        fact['limited_to_kind'] = args['kind']
    if bundle.get('place'):
        fact['limited_to_findspot'] = bundle['place']
    if _date_span(args):
        fact['limited_to_dates'] = _date_span(args)
    if bundle.get('type') == 'exact':
        fact['search_note'] = 'No dictionary form matched, so the letters were searched.'
    return fact


def _coin_date(c):
    return date_label(c.get('date_start'), c.get('date_end')) or 'undated'


def summarise_coins(bundle, args):
    """Facts for a Coins search, from {'search': /coins response, 'mint': the page's mint value or None, 'query': words}."""
    bundle = bundle if isinstance(bundle, dict) else {}
    resp = bundle.get('search') or {}
    args = dict(args)
    if args.get('mint'):
        if bundle.get('mint'):
            args['mint'] = bundle['mint']                       # the page's spelling of the mint
        else:
            args.pop('mint')                                    # not a mint the page lists: it was searched as a word
            args['query'] = bundle.get('query') or args.get('query')
    searched = (f"Coins, words '{args.get('query')}'" + (f", mint {args['mint']}" if args.get('mint') else '')
                + (f", {args['denomination']}" if args.get('denomination') else '')
                + (f", {_date_span(args)}" if _date_span(args) else ''))
    rows = [c for c in (resp.get('coins') or []) if isinstance(c, dict)]
    total = int(resp.get('total') or 0)
    if not resp.get('available', True) or not rows or not total:
        return _none(COINS, args, 'No coin type matches these words and filters.', searched)
    examples = []
    for c in rows[:SHOWN]:
        legend = ' / '.join(x for x in (c.get('obverse_legend'), c.get('reverse_legend')) if x)
        ex = {'ref': c.get('title') or c.get('id'), 'authority': c.get('authority') or '',
              'denomination': ' '.join(x for x in (c.get('material'), c.get('denomination')) if x),
              'mint': c.get('mint') or '', 'date': _coin_date(c), 'legend': _clip(legend, 120),
              'obverse': _clip(c.get('obverse_description'), 110), 'reverse': _clip(c.get('reverse_description'), 110)}
        examples.append({k: v for k, v in ex.items() if v})
    fact = {
        'kind': KIND_COLLECTION, 'search': COINS, 'args': args, 'collection': 'Coins',
        'words_searched': args.get('query'), 'coin_types_found': total,
        'examples_note': f'only the first {len(examples)} of {total} coin types are listed; the total is coin_types_found',
        'examples': examples,
    }
    if args.get('mint'):
        fact['limited_to_mint'] = args['mint']
    if args.get('denomination'):
        fact['limited_to_denomination'] = args['denomination']
    if _date_span(args):
        fact['limited_to_dates'] = _date_span(args)
    return fact


def summarise_objects(resp, args):
    """Facts for an Objects search, from the /objects response."""
    resp = resp if isinstance(resp, dict) else {}
    searched = f"Objects, words '{args.get('query')}'" + (f", {_date_span(args)}" if _date_span(args) else '')
    rows = [o for o in (resp.get('objects') or []) if isinstance(o, dict)]
    total = int(resp.get('total') or 0)
    if not resp.get('available', True) or not rows or not total:
        return _none(OBJECTS, args, 'No museum object matches these words.', searched)
    examples = []
    for o in rows[:SHOWN]:
        ex = {'ref': o.get('title') or o.get('id'), 'museum': o.get('museum_name') or o.get('museum') or '',
              'date': o.get('date_text') or date_label(o.get('date_start'), o.get('date_end')) or 'undated',
              'culture': o.get('culture') or '', 'kind_of_object': o.get('object_type') or '',
              'material': o.get('material') or '', 'description': _clip(o.get('short_text') or o.get('description'), 160)}
        examples.append({k: v for k, v in ex.items() if v})
    fact = {
        'kind': KIND_COLLECTION, 'search': OBJECTS, 'args': args, 'collection': 'Objects',
        'words_searched': args.get('query'), 'objects_found': total,
        'examples_note': f'only the first {len(examples)} of {total} objects are listed; the total is objects_found',
        'examples': examples,
    }
    if _date_span(args):
        fact['limited_to_dates'] = _date_span(args)
    return fact


def code_sentence(fact):
    """The whole answer when a collection search found nothing."""
    which, a = fact.get('search'), fact.get('args') or {}
    if which == DOCUMENTS:
        if 'findspot list' in str(fact.get('note')):
            return (f"The Inscriptions & Papyri page has no findspot called {a.get('place')}, so no search was run. "
                    f"Try the place under another spelling, or search without it.")
        bits = []
        if a.get('kind'):
            bits.append(a['kind'])
        if a.get('place'):
            bits.append(f"from {a['place']}")
        if _date_span(a):
            bits.append(f"dated {_date_span(a)}")
        extra = f" ({', '.join(bits)})" if bits else ''
        s = f"The Inscriptions & Papyri page finds no document for “{a.get('query')}”{extra}."
        if a.get('asked_as') and fold(a['asked_as']) != fold(a.get('query')):
            s += f" I searched {'Greek' if a.get('language') == 'grc' else 'Latin'} words for “{a['asked_as']}”."
        return s
    if which == COINS:
        return f"The Coins page finds no coin type for “{a.get('query')}”."
    return f"The Objects page finds no museum object for “{a.get('query')}”."
