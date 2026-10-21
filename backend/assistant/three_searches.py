"""Three more searches Tessa runs herself: Search One Text, People & Places, Events.

Until 2026-10-21 she ran Line Search, Rare Words, Theme Search, the Theme
Comparison and the corpus listing, and only described the rest. These three are
pages of the site with a plain request behind each, so a visitor can ask in a
sentence and get the page's own answer with a control that opens the page.

WHAT IS HERE

    detection   which questions reach each search, decided in code from the
                reader's words. Each pattern is narrow on purpose: a question
                that line_search, theme_search, a comparison or the guide
                already answers well must keep going where it went.
    summaries   the facts the model writes from, computed and compact. Every
                reference in them is built from a field the route returned.
    matching    which People & Places entries and which Events a name means.

The searches themselves are in `searches.TOOLS` (`one_text_search`,
`people_places`, `events`), run over the same loopback requests as the others.
"""
import re
import unicodedata

from backend.logging_config import get_logger
from backend.work_names import base_work

logger = get_logger('assistant.three_searches')

ONE_TEXT = 'one_text_search'
PEOPLE_PLACES = 'people_places'
EVENTS = 'events'
# The three collection searches (collections_searches.py): Inscriptions & Papyri, Coins, Objects.
COLLECTION_NAMES = ('documents_search', 'coins_search', 'objects_search')
NAMES = (ONE_TEXT, PEOPLE_PLACES, EVENTS) + COLLECTION_NAMES

# Kinds of fact that carry something for the model to write from. The others
# (nothing found, several matches, an author with several works) are answered
# in code, because a sentence that lists matches and asks which is not a place
# for a model to be creative.
KIND_ONE_TEXT = 'ONE TEXT SEARCH, run on the Search One Text request.'
KIND_PLACES = 'PEOPLE & PLACES ENTRY, read from the People & Places page.'
KIND_EVENT = 'AN EVENT, read from the Events page.'
KIND_COLLECTION = 'RESULTS OF A COLLECTION SEARCH, read from the site\'s own page.'
KIND_NONE = 'NOTHING FOUND by a search of the site.'
KIND_SEVERAL = 'SEVERAL MATCHES for the name asked about.'

SHOWN_PASSAGES = 5
SHOWN_EVENT_PASSAGES = 5
SHOWN_WORKS = 5
SHOWN_MATCHES = 6


def fold(s):
    """Lower case, no accents, single spaces: how names are compared."""
    s = unicodedata.normalize('NFD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s).strip().lower()


def _quoted(question):
    """A quoted phrase names words, not a subject: line_search keeps it."""
    return bool(re.search(r'["\u201c\u2018]', question or ''))


def is_new_fact(fact):
    return fact.get('search') in NAMES


def model_writes(facts):
    """True when one of these facts is for the model to write from."""
    return any(f.get('search') in NAMES and f.get('kind') in (KIND_ONE_TEXT, KIND_PLACES, KIND_EVENT, KIND_COLLECTION)
               for f in facts or [])


def code_answers(facts):
    """True when the facts hold an answer that is written in code."""
    return any(f.get('search') in NAMES and f.get('kind') in (KIND_NONE, KIND_SEVERAL) for f in facts or [])


# --------------------------------------------------------------------------
# Search One Text
# --------------------------------------------------------------------------
# A question that asks what ONE work says about a subject. "Say about" verbs
# only: "mention" and "name" belong to People & Places, and a bare "passages
# about" with no work named still goes to Theme Search across everything.
_SAY = (r'(?:say|says|said|talk|talks|speak|speaks|spoke|write|writes|wrote|tell|tells|told|treat|treats|'
        r'discuss|discusses|describe|describes|depict|depicts|portray|portrays|handle|handles|show|shows|'
        r'think|thinks|have to say)')
_ABOUT = re.compile(
    r'\b(?:what|how|where|when|why|which)\b[^?]*?\b' + _SAY + r'\b[^?]*?\b(?:about|of|on|regarding|concerning)\s+'
    r'(?P<subject>[^?]+?)\s*\??\s*$', re.I)
_DESCRIBE = re.compile(
    r'\b(?:how|where|when)\b[^?]*?\b(?:describe|describes|depict|depicts|portray|portrays|narrate|narrates)\s+'
    r'(?P<subject>[^?]+?)\s*\??\s*$', re.I)
_IN_WORK = re.compile(r'^\s*in\s+(?:the\s+)?(?P<work>[^,?]+?)\s*,\s*(?P<rest>.+?)\s*\??\s*$', re.I)
_WHERE_IN = re.compile(
    r'^\s*where\s+in\s+(?:the\s+)?(?P<work>[^?]+?)\s+(?:does|do|did|is|are|was|were)\s+(?P<rest>.+?)\s*\??\s*$', re.I)
_PASSAGES_IN = re.compile(
    r'\b(?:passages|scenes|episodes|lines)\s+(?:about|on|of|where|in which|describing)\s+(?P<subject>.+?)\s+'
    r'(?:in|of|from)\s+(?:the\s+)?(?P<work>[A-Z][^?]*?)\s*\??\s*$')
_LEAD_WH = re.compile(r'^(?:where|when|how|what|which|why)\s+(?:(?:does|do|did|is|are|was|were|can|could)\s+)?', re.I)
_COMMON_WORDS = {'ancient', 'old', 'new', 'great', 'first', 'second', 'last', 'war', 'wars', 'history', 'histories',
                 'life', 'lives', 'love', 'letters', 'letter', 'poems', 'poem', 'songs', 'song', 'age', 'man', 'men',
                 'tale', 'tales', 'book', 'books', 'works', 'work', 'speeches', 'orations', 'epistles', 'against',
                 'concerning', 'natural', 'complete', 'selected', 'fragments', 'sources', 'texts', 'days', 'day'}
_GENERIC_SUBJECT = {'it', 'this', 'that', 'them', 'things', 'something', 'anything', 'everything', 'him', 'her'}


def _clean_subject(text):
    s = re.sub(r'\s+', ' ', str(text or '')).strip(' ?.,;:"\'')
    s = re.sub(r'^(?:the\s+)?(?:theme|subject|topic|idea|motif)\s+of\s+', '', s, flags=re.I)
    return s


def _one_text_subject(question):
    """(subject, work_phrase_or_None) when the question asks what a text says about something."""
    q = str(question or '').strip()
    m = _IN_WORK.match(q)
    if m and re.match(r'(?i)(?:where|when|how|what|which|why|is there|are there|does|do)\b', m.group('rest')):
        rest = m.group('rest')
        rest = re.sub(r'(?i)^(?:is there|are there)\s+(?:any\s+)?', '', rest)
        subject = _clean_subject(_LEAD_WH.sub('', rest))
        return subject, m.group('work')
    m = _WHERE_IN.match(q)
    if m:
        return _clean_subject(m.group('rest')), m.group('work')
    m = _PASSAGES_IN.search(q)
    if m:
        return _clean_subject(m.group('subject')), m.group('work')
    m = _ABOUT.search(q) or _DESCRIBE.search(q)
    if m:
        return _clean_subject(m.group('subject')), None
    return '', None


def one_text_request(question, lookup=None):
    """{'row', 'subject', 'books'} for a question that names one work and a subject, else None.

    Exactly one text must be named, found by the same resolution every other
    path uses (corpus_lookup.named_texts). An author with one work in the corpus
    counts as that work. An author with several does not: asking which work is
    a question for the reader, and the old routing for that question stays.
    """
    q = str(question or '')
    if _quoted(q) or not q.strip():
        return None
    subject, _work_phrase = _one_text_subject(q)
    if len(subject) < 3 or fold(subject) in _GENERIC_SUBJECT:
        return None
    if lookup is None:
        from backend.assistant import corpus_lookup as lookup
    try:
        hits = lookup.named_texts(q, limit=3)
    except Exception as e:                                       # noqa: BLE001
        logger.info('[THREE] named_texts failed: %s', e)
        return None
    # One work named twice ("Aeneid 6" is the sixth book and the work) is still one work; the book wins.
    by_work = {}
    for h in hits:
        key = base_work(str(h.get('id') or ''))
        if key not in by_work or (h.get('is_part') and not by_work[key].get('is_part')):
            by_work[key] = h
    if len(by_work) != 1:
        return None
    row = next(iter(by_work.values()))
    # A title that matched only on an ordinary word ("ancient sources" and the Rime of the Ancient
    # Mariner) was not named.
    named = set(fold(f"{row.get('title')} {row.get('author')}").split()) & set(fold(q).split())
    if named and named <= _COMMON_WORDS:
        return None
    if row.get('matched') == 'author':
        row = lookup._single_work(row, row.get('language'))       # noqa: SLF001
        if not row:
            return None
    # The subject must not itself be the work's name ("what does the Aeneid say about the Aeneid").
    if fold(subject) in (fold(row.get('title')), fold(row.get('author'))):
        return None
    # "a storm in Aeneid 1": the work and book are the scope of the search, not part of the subject.
    tail = re.search(r'\s+(?:in|of|from|by)\s+(?:the\s+)?([A-Z][\w\' ]*)$', subject)
    if tail:
        known = set(fold(f"{row.get('title')} {row.get('author')} {row.get('id')}").replace('.', ' ').split())
        if any(w in known for w in fold(tail.group(1)).split() if len(w) > 3):
            subject = subject[:tail.start()].strip()
    if len(subject) < 3:
        return None
    wid = str(row.get('id') or '').replace('.tess', '')
    m = re.search(r'\.part\.(\d+)', wid)
    return {'row': row, 'subject': subject, 'books': m.group(1) if m else ''}


def one_text_args(req):
    row = req['row']
    wid = base_work(str(row.get('id') or ''))
    args = {'work': wid, 'query': req['subject'], 'languages': row.get('language') or 'la'}
    if req.get('books'):
        args['books'] = req['books']
    return args


def _short_title(title):
    return re.sub(r',?\s*Book\s+\d+.*$', '', str(title or '')).strip()


def passage_ref(r):
    """"Vergil, Aeneid 1.85" from one theme-search result: author, title without its book, first locus."""
    author = str(r.get('author') or '').strip()
    title = _short_title(r.get('title') or r.get('work'))
    locus = str(r.get('locus_start') or r.get('locus') or '').split('\u2013')[0].strip()
    return ' '.join(b for b in (f'{author},' if author and title else author, title, locus) if b).strip()


# The page's labels for the confidence bands (AskAWorkPage BANDS), used only when the
# route says the band was fitted; the lowest is "Closest passages".
BANDS = {'low': 'Closest passages', 'moderate': 'Moderate match', 'strong': 'Strong match'}


def summarise_one_text(raw, args):
    """Facts for a Search One Text request: the best passages with references, and the band the page shows."""
    raw = raw if isinstance(raw, dict) else {}
    rows = raw.get('results') or []
    conf = raw.get('confidence') or {}
    level, fitted = conf.get('level'), bool(conf.get('fitted'))
    note = str(raw.get('note') or '')
    searched = f"Search One Text, work {args.get('work')}, subject '{args.get('query')}'"
    # The page offers no list when no word of the subject is known to the index, and says nothing in the
    # work resembles it when the lowest band was not fitted for this work; Tessa says the same.
    if conf.get('no_known_words'):
        return {'kind': KIND_NONE, 'search': ONE_TEXT, 'args': args, 'what_was_searched': searched,
                'note': 'Nothing to search for. ' + note}
    if not rows or (level == 'low' and not fitted):
        return {'kind': KIND_NONE, 'search': ONE_TEXT, 'args': args, 'what_was_searched': searched,
                'note': ('Nothing in this work resembles that subject. ' + note).strip() if rows
                        else (note or 'The passage index returned no passages for this work and subject.')}
    r0 = rows[0]
    name = ', '.join(b for b in (r0.get('author'), _short_title(r0.get('title') or r0.get('work'))) if b)
    return {
        'kind': KIND_ONE_TEXT, 'search': ONE_TEXT, 'args': args,
        'work_searched': name or args.get('work'),
        'subject_searched': args.get('query'),
        'books_searched': args.get('books') or 'the whole work',
        'passages_returned': len(rows),
        'match_band': BANDS.get(level) if fitted else 'not rated',
        'page_note': note,
        'examples_note': (f'only the first {min(SHOWN_PASSAGES, len(rows))} of {len(rows)} passages are listed; '
                          f'the total is passages_returned'),
        'examples': [{'ref': passage_ref(r),
                      'strong_match': bool(r.get('strong')),
                      'text': str(r.get('gist') or '')[:220]}
                     for r in rows[:SHOWN_PASSAGES]]}


# --------------------------------------------------------------------------
# People & Places
# --------------------------------------------------------------------------
_NAME = (r"(?P<name>[A-Z][\w'\u2019\-]*(?:\s+(?:of\s+|the\s+|de\s+|ad\s+)?[A-Z][\w'\u2019\-]*){0,2})")
_SCOPE = (r"(?P<scope>(?:the\s+)?[A-Z][\w'\u2019\-]*(?:\s+[A-Z][\w'\u2019\-]*){0,2}(?:\s+\d{1,2})?)")
_MENTION_VERBS = r"(?:mention|mentions|name|names|refer to|refers to|invoke|invokes|speak of|speaks of|cite|cites)"
_MENTIONED = r"(?:mentioned|named|referred to|invoked|cited|spoken of|found)"
_SCOPE_TAIL = re.compile(r'\s+(?:in|by|within)\s+(?:the\s+)?(?P<scope>[A-Z][^?]*?)\s*\??\s*$')

_MENTION_PATTERNS = (
    # how often does Tibullus mention Delia / where does the Aeneid mention Sarpedon
    re.compile(r"(?i:\b(?:where|how often|how many times|how many lines|how many works|which passages|which books)\b"
               r"[^?]*?\b(?:does|do|did)\s+)" + _SCOPE + r"\s+(?i:" + _MENTION_VERBS + r")\s+(?:the\s+)?" + _NAME),
    # where is Sarpedon mentioned / how often is Troy named
    re.compile(r"(?i:\b(?:where|how often|how many times|how many lines|how many works|which works|which texts|"
               r"which authors|in which works|in which texts)\b[^?]*?\b(?:is|are|was|were|does|do)\s+(?:the\s+)?)" +
               _NAME + r"\s+(?i:" + _MENTIONED + r")"),
    # which works name Perusia / who mentions Sarpedon / which texts speak of Troy
    re.compile(r"(?i:\b(?:which|what)\s+(?:\w+\s+){0,2}?(?:works|texts|authors|books|poems|poets|passages|lines)\s+"
               + _MENTION_VERBS + r")\s+(?:the\s+)?" + _NAME),
    re.compile(r"(?i:\bwho\s+" + _MENTION_VERBS + r")\s+(?:the\s+)?" + _NAME),
    re.compile(r"(?i:\b(?:passages|lines|places|works)\s+(?:that\s+|which\s+)?" + _MENTION_VERBS + r")\s+(?:the\s+)?" + _NAME),
    re.compile(r"(?i:\b(?:mentions|references)\s+of)\s+(?:the\s+)?" + _NAME),
)


_NAME_LC = r"(?P<name>[a-z][\w'\u2019\-]*(?:\s+[a-z][\w'\u2019\-]*)?)"
_NOT_A_NAME = {'the', 'a', 'an', 'this', 'that', 'it', 'them', 'they', 'phrase', 'word', 'words', 'text', 'texts',
               'work', 'works', 'line', 'lines', 'passage', 'passages', 'author', 'authors', 'anyone', 'anything',
               'someone', 'something', 'you', 'we', 'i', 'he', 'she', 'one', 'there'}
_MENTION_PATTERNS_LC = (
    re.compile(r"(?i:\b(?:where|how often|how many times|how many lines|how many works|which works|which texts|"
               r"which authors|in which works|in which texts)\b[^?]*?\b(?:is|are|was|were)\s+(?:the\s+)?)" +
               _NAME_LC + r"\s+(?i:" + _MENTIONED + r")"),
    re.compile(r"(?i:\b(?:which|what)\s+(?:\w+\s+){0,2}?(?:works|texts|authors|books|poems|poets|passages|lines)\s+"
               + _MENTION_VERBS + r")\s+(?:the\s+)?" + _NAME_LC),
    re.compile(r"(?i:\bwho\s+" + _MENTION_VERBS + r")\s+(?:the\s+)?" + _NAME_LC),
)


def mention_request(question):
    """{'name', 'scope'} for a question about where a person, place or god is named, else None.

    'scope' is the text of an author or work the question limits it to ("how
    often does Tibullus mention Delia"), or ''. Needs a capitalized name and one
    of the verbs of naming, so a question about a word still goes to Line Search.
    """
    q = str(question or '').strip()
    if _quoted(q) or not q:
        return None
    for pat in _MENTION_PATTERNS:
        m = pat.search(q)
        if not m:
            continue
        name = re.sub(r'\s+', ' ', m.group('name')).strip()
        if fold(name.split()[0]) in {'the', 'a', 'an', 'what', 'which', 'where', 'who', 'how', 'this', 'that'}:
            continue
        scope = ''
        if 'scope' in m.groupdict() and m.group('scope'):
            scope = m.group('scope')
        else:
            tail = _SCOPE_TAIL.search(q[m.end():])
            if tail:
                scope = tail.group('scope')
        scope = re.sub(r'^(?:the)\s+', '', scope.strip(), flags=re.I)
        return {'name': name, 'scope': scope}
    # A name typed in lower case is taken only when the entry list has exactly that name:
    # the caller sets 'lowercase' and declines when there is none.
    for pat in _MENTION_PATTERNS_LC:
        m = pat.search(q)
        if not m:
            continue
        words = m.group('name').split()
        if not words or any(w in _NOT_A_NAME for w in words):
            continue
        tail = _SCOPE_TAIL.search(q[m.end():])
        return {'name': ' '.join(words), 'scope': tail.group('scope') if tail else '', 'lowercase': True}
    return None


def _label_forms(e):
    """The spellings an entry answers to: its label split at slashes and brackets, and its Latin and Greek forms."""
    out = set()
    for f in (e.get('display_label'), e.get('label'), e.get('display_label_la'), e.get('display_label_grc')):
        for part in re.split(r'[/()]', str(f or '')):
            if fold(part):
                out.add(fold(part))
    return out


def match_entities(name, search):
    """(entries, exact): the entries of a People & Places search that mean this name.

    Entries whose label (any of its spellings) is the name; where there are none,
    the first result alone, marked inexact, because the route ranks the search
    names of an entry first (Troy finds Ilium/Troia). Names that exist only as
    spellings in the corpus (source 'corpus') are never taken as the first guess.
    """
    results = [r for r in ((search or {}).get('results') or []) if isinstance(r, dict)]
    want = fold(name)
    exact = [r for r in results if want in _label_forms(r)]
    if exact:
        return exact[:SHOWN_MATCHES], True
    firsts = [r for r in results[:1] if r.get('source') != 'corpus']
    return firsts, False


def _base_title(display_name, title):
    t = _short_title(title) or _short_title(display_name)
    return t


def works_of_entry(detail):
    """[{'work', 'lines'}] by base work, most lines first. A work held in books is added up across its books."""
    agg = {}
    for w in (detail or {}).get('works') or []:
        key = base_work(str(w.get('work') or ''))
        if not key:
            continue
        a = agg.setdefault(key, {'work': ', '.join(b for b in (w.get('author'), _base_title(w.get('display_name'), w.get('title'))) if b)
                                 or key, 'author': w.get('author') or '', 'language': w.get('language'), 'lines': 0, 'id': key})
        a['lines'] += int(w.get('count') or 0)
    return sorted(agg.values(), key=lambda a: (-a['lines'], a['work']))


def _entry_fact(entry, detail, scope_row=None):
    works = works_of_entry(detail)
    out = {
        'heading': entry.get('display_label') or entry.get('label'),
        'type': entry.get('type'),
        'lines_naming_it': entry.get('mentions_total'),
        'lines_by_language': entry.get('mention_counts'),
        'works_naming_it': len(works),
        'works_with_most_lines_TOP5_ONLY': [f"{w['work']}: {w['lines']} line{'' if w['lines'] == 1 else 's'}" for w in works[:SHOWN_WORKS]],
        'works_note': (f'only the first {min(SHOWN_WORKS, len(works))} of {len(works)} works are listed; '
                       f'the total is works_naming_it'),
    }
    if entry.get('description'):
        out['description'] = entry['description']
    if entry.get('label_shared'):
        out['name_shared_with'] = entry.get('label_shared_with')
    docs = (detail or {}).get('document_counts') or {}
    if docs:
        out['inscriptions_and_papyri_naming_it'] = sum(docs.values())
    if scope_row:
        out['asked_about'] = scope_row
    return out


def scope_lines(works, scope_row):
    """Lines in the works the question limited it to: an author's, or one work's. None without a scope."""
    if not scope_row:
        return None
    if scope_row.get('matched') == 'author':
        a = fold(scope_row.get('author'))
        n = sum(w['lines'] for w in works if fold(w.get('author')) == a)
    else:
        base = base_work(str(scope_row.get('id') or ''))
        n = sum(w['lines'] for w in works if w['id'] == base)
    return n


def summarise_people_places(bundle, args, scope_row=None):
    """Facts for a People & Places lookup, from {'search': ..., 'details': {entry id: detail}}."""
    name = str(args.get('name') or '')
    search = (bundle or {}).get('search') or {}
    details = (bundle or {}).get('details') or {}
    entries, exact = match_entities(name, search)
    if entries and args.get('pick_index') is not None:
        # The reader chose one of the entries Tessa listed (entry_choice): same search, same order.
        entries = [entries[min(int(args['pick_index']), len(entries) - 1)]]
    if not entries:
        return {'kind': KIND_NONE, 'search': PEOPLE_PLACES, 'args': {'name': name},
                'what_was_searched': f"People & Places, name '{name}'",
                'note': 'No entry of People & Places matches this name.',
                'suggestions': [r.get('display_label') for r in (search.get('near_spellings') or [])[:3]]}
    if exact and len(entries) > 1:
        rows = []
        for e in entries:
            rows.append({'heading': e.get('display_label') or e.get('label'), 'type': e.get('type'),
                         'entry_id': e.get('id'), 'lines_naming_it': e.get('mentions_total'),
                         'works_naming_it': len(works_of_entry(details.get(e.get('id')))) or None,
                         'description': e.get('description')})
        return {'kind': KIND_SEVERAL, 'search': PEOPLE_PLACES, 'args': {'name': name},
                'name_asked': name, 'matches': rows, 'match_count': len(rows),
                'ask': 'Say that more than one entry carries this name, list them, and ask which one is meant.'}
    e = entries[0]
    detail = details.get(e.get('id')) or {}
    fact = _entry_fact(e, detail, None)
    works = works_of_entry(detail)
    n = scope_lines(works, scope_row)
    if scope_row is not None:
        fact['limited_to'] = (scope_row.get('author') if scope_row.get('matched') == 'author'
                              else scope_row.get('display_name') or scope_row.get('author'))
        fact['lines_naming_it_within_that_limit'] = n or 0
    fact.update({'kind': KIND_PLACES, 'search': PEOPLE_PLACES,
                 'args': {'name': name, 'entry': e.get('id'), 'heading': fact['heading']},
                 'name_asked': name,
                 'exact_label_match': exact})
    if not exact:
        fact['closest_entry_note'] = (f'No entry is labeled exactly {name}. This is the closest entry the '
                                      f'search found, so say that it is the closest.')
    return fact


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------
_EVENT_NOUN = r"(?i:battle|siege|treaty|campaign|war|sack|naval battle|peace|capture|fall|destruction)"
_EVENT_PHRASE = re.compile(
    r"\b(?P<label>(?P<noun>" + _EVENT_NOUN + r")s?\s+(?:of|at|near)\s+(?:the\s+)?"
    r"(?P<name>[A-Z][\w'\u2019\-]*(?:\s+(?:of\s+|the\s+|de\s+)?[A-Z][\w'\u2019\-]*){0,2}))")
_EVENT_VERBS = re.compile(
    r"(?i)\b(?:which|what)\s+(?:\w+\s+){0,2}?(?:texts|sources|authors|works|writers|historians)\s+"
    r"(?:describe|narrate|tell of|tell about|report|record|cover|recount|say|mention|speak of)\b[^?]*?"
    r"(?<![\w'])(?P<name>[A-Z][\w'\u2019\-]*(?:\s+[A-Z][\w'\u2019\-]*){0,2})\s*\??\s*$")
_COMPARE_WORDS = ('compare', 'comparing', 'versus', ' vs ', 'parallel', 'echo', 'allusion', 'quot')


def event_request(question):
    """{'name', 'label', 'explicit'} for a question about a battle, siege, treaty or campaign, else None.

    An event noun with a name ("the siege of Perusia") always counts. A bare
    place ("which texts describe Thermopylae?") counts only when the caller
    finds an event of that name, so a question about a person or a theme is not
    taken.
    """
    q = str(question or '').strip()
    if _quoted(q) or not q:
        return None
    if any(w in q.lower() for w in _COMPARE_WORDS):
        return None
    m = _EVENT_PHRASE.search(q)
    if m:
        return {'name': m.group('name').strip(), 'label': re.sub(r'\s+', ' ', m.group('label')).strip(),
                'explicit': True}
    m = _EVENT_VERBS.search(q)
    if m:
        return {'name': m.group('name').strip(), 'label': '', 'explicit': False}
    return None


def year_label(y):
    if y is None:
        return ''
    return f'{-y} BCE' if y < 0 else f'{y} CE'


def date_label(start, end):
    """The date as the Events page writes it: 31 BCE, 52 to 49 BCE, 5 BCE to 14 CE."""
    if start is None:
        return ''
    if end is None or end == start:
        return year_label(start)
    if (start < 0) == (end < 0):
        return f'{abs(start)} to {year_label(end)}'
    return f'{year_label(start)} to {year_label(end)}'


def place_label(place, ancient):
    """The place as the page names it: "Perusia (modern Perugia)", or the place alone."""
    if not ancient:
        return place or ''
    if not place or fold(place) == fold(ancient):
        return ancient or place
    return f'{ancient} (modern {place})'


def _heading_of_work(work_id):
    """"Suetonius, De Vita Caesarum" for a work id, from the corpus listing; the id read as words without one."""
    wid = base_work(str(work_id or ''))
    try:
        from backend.assistant import corpus_lookup
        for r in corpus_lookup._all_texts(None):                  # noqa: SLF001
            if base_work(str(r.get('id') or '')) == wid:
                name = r.get('display_name') or ''
                if name:
                    return _short_title(name)
                break
    except Exception:                                             # noqa: BLE001
        pass
    return ', '.join(' '.join(w.capitalize() for w in p.split('_') if w) for p in wid.split('.') if p)


def _event_passage_ref(p):
    """"Plutarch, Antony 64.2" from an event passage: its work's heading and the locus of its first line."""
    locus = str(p.get('ref_start') or '').split()[-1] if p.get('ref_start') else ''
    return ' '.join(b for b in (_heading_of_work(p.get('work')), locus) if b)


def event_row_fact(row):
    return {'event': row.get('label'), 'event_id': row.get('id'), 'type': row.get('type'),
            'date': date_label(row.get('date_start'), row.get('date_end')),
            'place': place_label(row.get('place'), row.get('place_ancient')),
            'passages': row.get('n_passages'), 'documents': row.get('n_documents')}


def summarise_events(bundle, args):
    """Facts for an Events lookup, from {'list': /events response, 'detail': /events/<id> response or None}."""
    name = str(args.get('name') or '')
    lst = (bundle or {}).get('list') or {}
    rows = [r for r in (lst.get('events') or []) if isinstance(r, dict)]
    if not rows:
        return {'kind': KIND_NONE, 'search': EVENTS, 'args': {'name': name},
                'what_was_searched': f"Events, name '{name}'",
                'note': ('The Events page holds no battle, siege, treaty or campaign matching this name '
                         'that has passages or documents attached.')}
    if len(rows) > 1:
        return {'kind': KIND_SEVERAL, 'search': EVENTS, 'args': {'name': name},
                'name_asked': name, 'match_count': int(lst.get('total') or len(rows)),
                'matches': [event_row_fact(r) for r in rows[:SHOWN_MATCHES]],
                'ask': 'Say that more than one event carries this name, list them with their dates, and ask which one is meant.'}
    detail = (bundle or {}).get('detail') or {}
    ev = detail.get('event') or rows[0]
    counts = detail.get('passage_counts') or {}
    passages = [p for p in (detail.get('passages') or []) if p.get('llm_label') == 'yes']
    examples = []
    for p in passages[:SHOWN_EVENT_PASSAGES]:
        ex = (p.get('excerpts') or [{}])[0].get('text') or ''
        examples.append({'ref': _event_passage_ref(p), 'text': str(ex)[:160]})
    arts = [s for s in (detail.get('scholarship') or []) if s.get('kind') == 'article']
    fact = {
        'kind': KIND_EVENT, 'search': EVENTS, 'args': {'name': name, 'id': ev.get('id')},
        'event': ev.get('label'), 'type': ev.get('type'),
        'date': date_label(ev.get('date_start'), ev.get('date_end')),
        'place': place_label(ev.get('place'), ev.get('place_ancient')),
        'narrative_passages': counts.get('yes', 0),
        'mention_passages': counts.get('mention', 0),
        'documents_nearby': len(detail.get('documents') or []) if detail else rows[0].get('n_documents'),
        'articles': len(arts),
        'examples_note': (f'the first {len(examples)} of the {len(passages)} narrative passages; '
                          f'the total is narrative_passages'),
        'examples': examples,
    }
    if ev.get('description'):
        fact['description'] = ev['description']
    return fact


# --------------------------------------------------------------------------
# What the answer says when code writes it
# --------------------------------------------------------------------------
def _join(items):
    items = [str(i) for i in items if i]
    if len(items) <= 1:
        return ''.join(items)
    return ', '.join(items[:-1]) + ' and ' + items[-1]


def code_sentence(fact):
    """The whole answer for a fact of kind NOTHING FOUND or SEVERAL MATCHES."""
    which = fact.get('search')
    if which in COLLECTION_NAMES:
        from backend.assistant import collections_searches
        return collections_searches.code_sentence(fact)
    if fact.get('kind') == KIND_NONE:
        if which == ONE_TEXT:
            return (f"Search One Text found no passages in this work about \u201c{fact['args'].get('query')}\u201d. "
                    f"{fact.get('note') or ''}").strip()
        if which == PEOPLE_PLACES:
            name = fact['args'].get('name')
            s = f"People & Places has no entry for {name}."
            if fact.get('suggestions'):
                s += f" Entries with a near spelling are {_join(fact['suggestions'])}."
            return s
        return (f"The Events page has no event named {fact['args'].get('name')} that has passages or "
                f"documents attached.")
    rows = fact.get('matches') or []
    if which == PEOPLE_PLACES:
        parts = []
        for r in rows:
            bit = f"{r.get('heading')} ({r.get('type')}, {r.get('lines_naming_it')} lines"
            if r.get('works_naming_it'):
                bit += f" in {r['works_naming_it']} works"
            parts.append(bit + ')')
        return (f"People & Places has {fact.get('match_count')} entries for {fact.get('name_asked')}: "
                f"{'; '.join(parts)}. Which one do you mean?")
    def count(n, noun):
        return f"{n} {noun}" + ('' if n == 1 else 's')
    parts = []
    for r in rows:
        bit = f"{r.get('event')} ({r.get('date')}"
        if r.get('place'):
            bit += f", {r['place']}"
        bit += f", {count(r.get('passages') or 0, 'passage')}"
        if r.get('documents'):
            bit += f", {count(r['documents'], 'document')}"
        parts.append(bit + ')')
    more = ''
    if (fact.get('match_count') or 0) > len(rows):
        more = f" The first {len(rows)} are listed."
    labels = {r.get('event') for r in rows}
    called = labels.pop() if len(labels) == 1 else fact.get('name_asked')
    return (f"The Events page has {fact.get('match_count')} events called {called}: "
            f"{'; '.join(parts)}.{more} Which one do you mean?")


# The instruction the answering model gets for these facts, in place of the one
# about listings. The passages are the answer here, so they are named.
RULE = ('THE FACTS ABOVE ARE THE ANSWER FROM ONE OF THE SITE\'S OWN PAGES. Report what came back and nothing '
        'else. Search One Text: name the work and the subject searched, give the match band as the page '
        'words it (match_band, with page_note when it says something), then every passage listed in '
        'examples, one per line, reference first and then what the description says, and say how many '
        'came back. People & Places: give the entry\'s heading, how many lines and works name it, and the works '
        'with the most lines, each written as "work: N lines". Events: give the date and place, how many '
        'narrative and mention passages, documents and articles, and the first narrative passages with '
        'their references. Inscriptions & Papyri, Coins and Objects: say how many were found (documents_found, '
        'coin_types_found or objects_found) and the words searched. Only when the facts hold asked_as, say that '
        'the documents are searched by their own Latin or Greek words and give both asked_as and the words '
        'searched. Then every example listed, '
        'one per line, reference first and then the date, place or mint and what the line, legend or description '
        'says, and say that only these are listed. Never mention an entry or event identifier. Use only references and figures that are in the facts, and do not add what the '
        'page would show beyond them. The control beneath your answer opens the page.')


# A REPLY TO "WHICH ONE DO YOU MEAN?" (2026-10-21). Asked about the battle of Actium, Tessa
# lists the two events of that name; the reader's "the one in 31 BCE" was then taken for a
# phrase and searched in the corpus. A reply naming a year or an order ("31 BCE", "the
# second", "the earlier one") after that list now opens the event chosen.
_LISTING = re.compile(r'The Events page has \d+ events called (?P<label>[^:]+): (?P<items>.*?)(?: The first \d+ are listed\.)? Which one do you mean\?', re.S)
_ITEM = re.compile(r'(?P<label>[^;(]+?) \((?P<date>\d+(?: (?:BCE|CE))?(?: to \d+ (?:BCE|CE))?)')
_ORDINALS = {'first': 0, 'second': 1, 'third': 2, 'fourth': 3, 'fifth': 4, 'last': -1,
             'earlier': 'min', 'earliest': 'min', 'later': 'max', 'latest': 'max'}


def _signed(n, era):
    return -n if era in ('BCE', 'BC') else n


def _years_of(date_text):
    out = []
    for m in re.finditer(r'(\d+) (BCE|CE)', date_text):
        out.append(_signed(int(m.group(1)), m.group(2)))
    return out


def event_choice(question, history):
    """{'name', 'label', 'year', 'explicit'} when the question picks one of the events Tessa just listed."""
    last = next((t.get('text') for t in reversed(history or []) if isinstance(t, dict) and t.get('role') == 'assistant'), '')
    m = _LISTING.search(str(last or ''))
    if not m:
        return None
    items = []
    for it in m.group('items').split('; '):
        mi = _ITEM.match(it.strip())
        if mi:
            years = _years_of(mi.group('date'))
            if years:
                items.append({'label': mi.group('label').strip(), 'years': years})
    if not items:
        return None
    q = str(question or '').lower()
    pick = None
    my = re.search(r'\b(\d{1,4})\s*(bce|bc|b\.c\.|ce|ad|a\.d\.)?(?![\d])', q)
    if my:
        n = int(my.group(1))
        era = (my.group(2) or '').replace('.', '').upper()
        wanted = _signed(n, 'BCE' if era in ('BCE', 'BC') else 'CE') if era else None
        for it in items:
            lo, hi = min(it['years']), max(it['years'])
            if (wanted is not None and lo <= wanted <= hi) or (wanted is None and n in [abs(y) for y in it['years']]):
                pick = it
                break
    if pick is None:
        for word, idx in _ORDINALS.items():
            if re.search(r'\b' + word + r'\b', q):
                if idx == 'min':
                    pick = min(items, key=lambda it: min(it['years']))
                elif idx == 'max':
                    pick = max(items, key=lambda it: max(it['years']))
                elif -len(items) <= idx < len(items):
                    pick = items[idx]
                break
    if pick is None:
        return None
    return {'name': pick['label'], 'label': pick['label'], 'year': min(pick['years']), 'year_to': max(pick['years']),
            'explicit': True}


# The same for People & Places: "People & Places has 2 entries for Mars: Mars (deity, 412 lines
# in 60 works); Mars (person, ...). Which one do you mean?" answered "the god" or "the second".
_ENTRY_LISTING = re.compile(r'People & Places has \d+ entries for (?P<name>[^:]+): (?P<items>.*?)\. Which one do you mean\?', re.S)
_ENTRY_ITEM = re.compile(r'(?P<heading>[^;(]+?) \((?P<type>[a-z]+)')
_TYPE_WORDS = {
    'deity': ('god', 'goddess', 'deity', 'divinity'),
    'person': ('person', 'man', 'woman', 'hero', 'king', 'queen', 'human', 'mortal', 'family', 'general', 'emperor'),
    'place': ('place', 'city', 'town', 'river', 'mountain', 'island', 'region', 'country'),
    'people': ('people', 'tribe', 'nation'),
}


def entry_choice(question, history):
    """{'name', 'pick_index'} when the question picks one of the entries Tessa just listed."""
    last = next((t.get('text') for t in reversed(history or []) if isinstance(t, dict) and t.get('role') == 'assistant'), '')
    m = _ENTRY_LISTING.search(str(last or ''))
    if not m:
        return None
    items = [mi.groupdict() for mi in (_ENTRY_ITEM.match(it.strip()) for it in m.group('items').split('; ')) if mi]
    if len(items) < 2:
        return None
    q = str(question or '').lower()
    for idx, it in enumerate(items):
        if any(re.search(r'\b' + w + r's?\b', q) for w in _TYPE_WORDS.get(it['type'], (it['type'],))):
            if sum(1 for o in items if o['type'] == it['type']) == 1:
                return {'name': m.group('name').strip(), 'pick_index': idx}
    for word, idx in _ORDINALS.items():
        if isinstance(idx, int) and re.search(r'\b' + word + r'\b', q) and -len(items) <= idx < len(items):
            return {'name': m.group('name').strip(), 'pick_index': idx % len(items)}
    return None
