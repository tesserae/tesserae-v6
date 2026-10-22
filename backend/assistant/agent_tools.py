"""The experimental Tessa: the model reads the conversation and chooses the searches itself (2026-10-22).

The ordinary Tessa (agent.py) decides in code which search a question needs and asks the model only to
write the answer, which keeps her right for every phrasing the code expects and blind to the rest
("analysis of those results", "there should be instances in the Aeneid (Pallas)"). Here the model is
given the conversation and the searches as tools, through the gateway's tool-calling interface, and
calls them as it sees fit. Texts are named in plain words ("Aeneid 1"); the tools resolve them with the
ordinary Tessa's resolver (corpus_lookup). Opt-in only: the page sends mode "tools".

A citation check runs on the answer: a sentence that gives a reference (such as 11.151) found in no
search result is dropped, so the reader never sees a locus the searches did not return.
"""
import json
import re
import urllib.error
import urllib.parse
import urllib.request

from backend.assistant import corpus_lookup, model, prompts, searches, site_help
from backend.logging_config import get_logger

logger = get_logger('assistant.tools')

MAX_ROUNDS = 5
ANSWER_TOKENS = 900


def _chat(messages, tools=None):
    name = model.MODEL_NAME
    body = {'model': name, 'messages': messages, 'temperature': 0, 'max_tokens': ANSWER_TOKENS,
            **(model._fields_for(name) or {})}
    if tools:
        body['tools'] = tools
        body['tool_choice'] = 'auto'
    req = urllib.request.Request(f'{model.ENDPOINT}/v1/chat/completions', data=json.dumps(body).encode(),
                                 headers=model._headers())
    with model._open(req, model._GEN_TIMEOUT) as r:  # nosec B310 - fixed endpoint from configuration
        return json.loads(r.read())['choices'][0]['message']


# ---------------------------------------------------------------- names and compact results

_VOCAB = {}
# English spellings the listing does not use; the closest listed word would be wrong (Virgil to Virgilii).
_ALIASES = {'virgil': 'vergil', 'virgils': 'vergil', 'vergils': 'vergil', 'aeneis': 'aeneid', 'homers': 'homer'}


def _corrected(name):
    """The name with each word the corpus listing does not know replaced by the closest word it does
    ("Vergils Aenied" to "Vergil Aeneid", "Virgil" to "Vergil"). 2026-10-22: asked for "Vergils Aenied" book
    6, she spent 82 seconds and said the corpus had no Aeneid."""
    import difflib
    if 'words' not in _VOCAB:
        words = set()
        for r in corpus_lookup._all_texts():
            for f in ('author', 'author_key', 'work', 'title', 'display_name'):
                words |= set(corpus_lookup._norm(r.get(f)).split())
        _VOCAB['words'] = sorted(w for w in words if len(w) >= 4 and not w.isdigit())
        _VOCAB['set'] = set(_VOCAB['words'])
    out = []
    for tok in str(name or '').split():
        w = corpus_lookup._norm(tok)
        if w in _ALIASES:
            tok = _ALIASES[w].title() if tok[:1].isupper() else _ALIASES[w]
        elif w.endswith('s') and w[:-1] in _VOCAB['set']:
            tok = tok.rstrip("'s").rstrip("’") if tok.lower().endswith("'s") else tok[:-1]
        elif len(w) >= 4 and w.isalpha() and w not in _VOCAB['set'] and w not in corpus_lookup._NOISE:
            near = difflib.get_close_matches(w, _VOCAB['words'], 1, 0.8)
            if near:
                tok = near[0].title() if tok[:1].isupper() else near[0]
        out.append(tok)
    return ' '.join(out)


def _named(question, limit):
    hits = corpus_lookup.named_texts(question, limit=limit)
    try:
        fixed = _corrected(question)
    except Exception as e:                                # noqa: BLE001 -- the listing may be unavailable
        logger.info('[ASSISTANT] name correction failed: %s', e)
        fixed = question
    if fixed != question:
        better = corpus_lookup.named_texts(fixed, limit=limit)
        if len(better) >= len(hits):
            return better
    return hits


def _one(name):
    """One work named in plain words. A title match from the listing comes first, with its book number
    ("Claudian De raptu Proserpinae" went to the Gothic War through the sentence parser, which reads at
    most two capitalized words); otherwise the sentence parser, which knows authors' single works."""
    try:
        fixed = _corrected(name)
    except Exception:                                     # noqa: BLE001 -- the listing may be unavailable
        fixed = str(name or '')
    m = re.match(r'^(.*?)[\s,]*(?:(?:book|bk\.?)\s*)?(\d{1,3})?\s*$', fixed, re.I)
    title, num = (m.group(1), m.group(2)) if m else (fixed, None)
    best = corpus_lookup.find_texts(title, limit=1)
    if best and best[0].get('matched') != 'author':
        hit = best[0]
        return (corpus_lookup.book_of(hit, num) or hit) if num else hit
    hits = _named(name, 1) or _named(str(name).title(), 1)
    return hits[0] if hits else None


def _pair(a, b):
    """Each work looked up on its own first, so a title the sentence parser misreads (Claudian De raptu
    Proserpinae, 2026-10-22) is found; the sentence parser when that fails."""
    pair = [p for p in (_one(a), _one(b)) if p]
    if len(pair) < 2:
        pair = _named(f'compare {a} with {b}', 2)
    return pair if len(pair) == 2 else None


def _id(row):
    return str(row.get('id') or '').replace('.tess', '')


def _clip(obj, n=6000):
    s = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + ' ...(cut)'


def _fusion_compact(rows, k=15):
    out = []
    for r in (rows or [])[:k]:
        s, t = r.get('source') or {}, r.get('target') or {}
        shared = r.get('matched_lemmas') or [w.get('display') or w.get('source_word') for w in r.get('matched_words') or []]
        out.append({'source': s.get('citation') or s.get('ref'), 'source_text': s.get('text'),
                    'target': t.get('citation') or t.get('ref'), 'target_text': t.get('text'), 'shared_words': shared,
                    'channels': r.get('channels'), 'score': r.get('fused_score') or r.get('score') or r.get('overall_score'),
                    'pair_in_how_many_works': r.get('formula_count')})
    return out


def _theme_compact(d, k=12):
    rows = d.get('results') or d.get('passages') or []
    conf = d.get('confidence')
    return {'confidence': conf.get('label') if isinstance(conf, dict) else conf, 'total': d.get('total'),
            'results': [{'work': r.get('display_name') or r.get('work'), 'ref': r.get('ref_start') or r.get('ref'),
                         'ref_end': r.get('ref_end'), 'year': r.get('year'),
                         'language': r.get('language'), 'summary': r.get('gist') or r.get('summary'),
                         'names_in_the_passage_text': r.get('names_in_text') if isinstance(r.get('names_in_text'), list) else None,
                         'passage_text_start': _window_text(r.get('id')),
                         'tags': r.get('themes') or r.get('tags')} for r in rows[:k]]}


def _window_text(window_id, n=360):
    """The first words of a passage window's own text, so the model can see who is named in it."""
    if not window_id:
        return None
    try:
        from backend import window_texts
        t = window_texts.texts_for([window_id]).get(window_id)
    except Exception:                                     # noqa: BLE001 -- an excerpt is a help, not a need
        t = None
    return (t or '')[:n] or None


# ---------------------------------------------------------------- the tools

def t_site_help(a):
    return (site_help.context_for(a.get('question') or '') or '')[:6000] or 'The Help pages say nothing on this.'


def t_compare_texts(a):
    pair = _pair(a.get('text_a', ''), a.get('text_b', ''))
    if not pair:
        return f"Could not find both texts in the corpus: {a.get('text_a')!r}, {a.get('text_b')!r}."
    return _compare_rows(pair)


WHOLE_WORK_LINES = 4000


def _lines_in(row):
    """How many lines a text has (a book file counts its own lines), from the passage text store; 0 when
    unknown."""
    from backend import window_texts
    from backend.work_names import base_work, is_part
    rid = _id(row)
    c = window_texts._conn()
    if c is None:
        return 0
    base = base_work(rid + '.tess') or rid
    n = c.execute('SELECT count(*) FROM lines WHERE work = ?', (window_texts._base_work(base),)).fetchone()[0]
    if is_part(rid + '.tess') and n:
        # A book: its share of the whole, by the listing's count of books.
        books = sum(1 for r in corpus_lookup._all_texts(row.get('language')) if is_part(str(r.get('id') or ''))
                    and base_work(str(r.get('id') or '')) == base)
        return n // max(books, 1)
    return n


def _compare_rows(pair):
    la, lb = pair[0].get('language') or 'la', pair[1].get('language') or 'la'
    names = [p.get('display_name') or _id(p) for p in pair]
    # A full comparison of a whole epic runs for many minutes and takes a web worker past 15 GB (2026-10-22,
    # the Thebaid against the Aeneid in testing), so Tessa does not start one on a text of more than
    # WHOLE_WORK_LINES lines: she compares by content or asks which books.
    big = [n for n, p in zip(names, pair) if _lines_in(p) > WHOLE_WORK_LINES]
    if big:
        return (f'Not run: {" and ".join(big)} {"is a long whole work" if len(big) == 1 else "are long whole works"}, '
                'and the full comparison is run book against book. Use theme_compare for the whole works '
                '(passages telling similar scenes), and offer to compare named books (for example book 12 with '
                'book 11). Ask the reader which books they want, in plain words.')
    if la == lb:
        page = searches.fusion_page(_id(pair[0]), _id(pair[1]), la, 25)
    else:
        page = searches.crosslingual_page(_id(pair[0]), _id(pair[1]), la, lb, 25)
    if page is None:
        return RUNNING + f'{names[0]} with {names[1]}.'
    rows = page if isinstance(page, list) else (page.get('parallels') or page.get('results') or [])
    return _clip({'compared': names, 'top_parallels': _fusion_compact(rows)}, 7000)


# A comparison not yet in the cache starts on the server and takes a minute or two. The answer loop waits
# for it, telling the reader it is still running, rather than leaving the reader to come back later
# (2026-10-22: "will you let me know when it's done?" got "I can't watch it in the background").
RUNNING = 'STILL RUNNING: the comparison of '
COMPARE_WAIT = 240
COMPARE_POLL = 10


def _waiting(fetch, clock=None, sleep=None, budget=None):
    """Generator: calls fetch() until it no longer says RUNNING or the wait runs out, yielding a
    ('step', ...) line on each wait so the page shows progress and the connection stays open. Its return
    value (StopIteration.value) is the last output. `budget` ({'left': seconds}) is shared by every
    comparison of one answer, so several comparisons wait COMPARE_WAIT in all, not each (2026-10-22: a
    turn with two new comparisons took 515 seconds)."""
    import time
    clock, sleep = clock or time.monotonic, sleep or time.sleep
    budget = budget if budget is not None else {'left': COMPARE_WAIT}
    start = clock()
    out = fetch()
    while isinstance(out, str) and out.startswith(RUNNING) and clock() - start < budget['left']:
        yield ('step', f'the comparison is still running on the server ({int(clock() - start)} s so far)')
        sleep(COMPARE_POLL)
        out = fetch()
    budget['left'] = max(0, budget['left'] - (clock() - start))
    if isinstance(out, str) and out.startswith(RUNNING):
        out += (' It is still running. Tell the reader plainly that the full comparison is not finished, give '
                'what the shared rare words (rare_words) and the passages telling similar scenes (theme_compare) '
                'show now, and say that the full comparison will be ready if they ask again in a few minutes.')
    return out


def t_read_passage(a):
    """The lines of one passage with a few lines around it, so a follow-up ("who is speaking there?", "the
    second one in full") is answered from the text and not from memory (2026-10-22: asked who speaks Lucan
    1.237, she named Cato "in the Senate in Carthage")."""
    from backend import window_texts
    w = _one(a.get('work') or '')
    if not w:
        return f"No work found for {a.get('work')!r}."
    base = window_texts._base_work(_id(w))
    c = window_texts._conn()
    if c is None or not base:
        return 'No passage text is available.'

    def tag(ref):
        ref = str(ref or '').strip()
        if not ref:
            return None
        row = c.execute('SELECT ref FROM lines WHERE work = ? AND (ref = ? OR ref LIKE ?) ORDER BY ord LIMIT 1',
                        (base, ref, '% ' + ref)).fetchone()
        return row[0] if row else None
    start = tag(a.get('ref'))
    if not start:
        return f"No line {a.get('ref')!r} in {w.get('display_name') or base}."
    end = tag(a.get('ref_end')) or start
    try:
        context = max(0, min(12, int(a.get('context') or 6)))
    except (TypeError, ValueError):
        context = 6
    out = window_texts.passage_lines(base, start, end, context=context)
    lines = [f"{x.get('ref')}: {x.get('text')}" for x in out.get('lines') or []]
    return _clip({'work': w.get('display_name') or base, 'lines': lines}, 6000) if lines else 'No lines found.'


def t_people_places(a):
    """The People & Places entry, with the inscriptions and papyri its page lists. 2026-10-22: asked
    "inscriptions too?" about Rusellae, she searched the documents for the word Rusellae, found none, and
    said none name it; the entry lists four (Rusellis, Rusellanus) that its page shows."""
    out = searches.run('people_places', a)
    docs = []
    rows = ((out or {}).get('search') or {}).get('results') or []
    for r in rows[:2]:
        if not (r.get('document_counts') or {}) or not r.get('id'):
            continue
        try:
            d = searches._get('/entities/' + urllib.parse.quote(str(r['id']), safe=':') + '/documents', {'limit': 10})
        except (searches.SearchError, OSError, ValueError) as e:
            logger.info('[ASSISTANT] documents of %s unreadable: %s', r.get('id'), e)
            continue
        for x in d.get('results') or []:
            docs.append({'entry': r.get('display_label') or r.get('label'), 'document': x.get('doc_id'),
                         'edition': (x.get('credit') or {}).get('principal_edition'),
                         'found_at': x.get('ancient_place') or x.get('modern_place'),
                         'date': [x.get('date_not_before'), x.get('date_not_after')],
                         'form_in_the_text': x.get('matched_form'), 'text': str(x.get('text') or '')[:200]})
    head = {'inscriptions_and_papyri_naming_it': docs} if docs else {}
    return _clip({**head, 'people_and_places': out}, 7000)


def t_rare_words(a):
    pair = _pair(a.get('text_a', ''), a.get('text_b', ''))
    if not pair:
        return 'Could not find both texts.'
    d = searches.run('rare_words', {'source': _id(pair[0]), 'target': _id(pair[1])})
    words = [{'word': r.get('display_form') or r.get('lemma'), 'texts_in_the_corpus_with_it': r.get('corpus_count'),
              'in_text_a': [x.get('citation') + ': ' + (x.get('text') or '') for x in r.get('source_locations') or []][:3],
              'in_text_b': [x.get('citation') + ': ' + (x.get('text') or '') for x in r.get('target_locations') or []][:3]}
             for r in d.get('results') or []]
    return _clip({'text_a': pair[0].get('display_name'), 'text_b': pair[1].get('display_name'),
                  'lemmas_shared': d.get('shared_lemmas'),
                  'rare_means': f"found in at most {d.get('max_occurrences')} texts of the corpus",
                  'rare_words_shared': words}, 5000)


def t_theme_search(a):
    args = {'query': a.get('description') or ''}
    if a.get('languages'):
        args['languages'] = a['languages']
    return _clip(_theme_compact(searches.run('theme_search', args)))


def t_search_one_text(a):
    w = _one(a.get('work') or '')
    if not w:
        return f"No work found for {a.get('work')!r}."
    args = {'work': _id(w), 'query': a.get('subject') or ''}
    if a.get('books'):
        args['books'] = str(a['books'])
    return _clip({'work': w.get('display_name'), **_theme_compact(searches.run('one_text_search', args))})


def t_theme_compare(a):
    pair = _pair(a.get('text_a', ''), a.get('text_b', ''))
    if not pair:
        return 'Could not find both texts.'
    return _clip(searches.run('theme_compare', {'work_a': _id(pair[0]), 'work_b': _id(pair[1]), 'limit': 15}))


LANGUAGES = ('la', 'grc', 'en', 'cop', 'he', 'fa', 'ur')


def t_list_texts(a):
    """Counts of works and authors with the titles, from the ordinary Tessa's holdings fact. With no
    language, the counts for every language (2026-10-22: asked "How big is the corpus?", the model listed
    the texts five times, got a list cut short each time, and said it could not give a total)."""
    from backend.assistant import agent as ordinary
    code = (a.get('language') or '').strip().lower()
    if code in LANGUAGES:
        fact = ordinary._language_holdings_fact(code)
        if 'authors_with_work_counts' in fact:
            # The ordinary Tessa's fact stops at 150 authors (alphabetical), which left out Statius and
            # Vergil. Every author, with the number of works, fits.
            from backend.work_names import base_work
            by_author = {}
            for r in searches.run('list_texts', {'language': code}) or []:
                if isinstance(r, dict):
                    by_author.setdefault(str(r.get('author') or 'Unknown'), set()).add(
                        base_work(str(r.get('id') or '')) or str(r.get('display_name') or ''))
            fact['authors_with_work_counts'] = {a: len(w) for a, w in sorted(by_author.items())}
            fact['note'] = 'Too many works to list titles. Ask list_texts again for one author, or search the work.'
        return _clip(fact, 9000)
    counts = {}
    for c in LANGUAGES:
        f = ordinary._language_holdings_fact(c)
        counts[f.get('language') or c] = {'works': f.get('works'), 'authors': f.get('authors')}
    return _clip({'literary_works_by_language': counts,
                  'total_works': sum(v['works'] or 0 for v in counts.values()),
                  'note': 'A work divided into books counts once.'}, 3000)


def _direct(name):
    return lambda a: _clip(searches.run(name, a))


TOOLS = {
    'site_help': (t_site_help, 'Read the Tesserae Help pages on a question about how the site, a page, a feature, a '
                  'setting, the sources or the project work. Use for any question about Tesserae itself.',
                  {'question': 'the question, in plain words'}),
    'compare_texts': (t_compare_texts, 'Run the full intertextual comparison of two texts (every channel: shared '
                      'words, sound, meaning, syntax) and get its top parallels. Texts in plain words with a book if '
                      'given, e.g. "Aeneid 1", "Lucan Bellum Civile 1". Two languages run the cross-language search. '
                      'Use it again to analyze the results of a comparison asked for earlier.',
                      {'text_a': 'first text', 'text_b': 'second text'}),
    'read_passage': (t_read_passage, 'The text of one passage with the lines around it. Use it before saying who '
                     'speaks, what happens or what a line says, and before quoting a line from an earlier answer.',
                     {'work': 'the work in plain words, with the book if given ("Lucan 1", "Aeneid 4")',
                      'ref': 'the line reference, e.g. 1.237', 'ref_end': 'optional last line',
                      'context': 'optional lines on each side (default 6)'}),
    'rare_words': (t_rare_words, 'Rare words two texts share (words found in few texts of the corpus).',
                   {'text_a': 'first text', 'text_b': 'second text'}),
    'line_search': (_direct('line_search'), 'Every line in the corpus where a word or phrase occurs.',
                    {'query': 'the word or phrase in the original language', 'language': 'la, grc, he, cop or en',
                     'search_type': 'exact for a quoted phrase, lemma for dictionary forms'}),
    'theme_search': (t_theme_search, 'Find passages anywhere in the corpus by what happens in them. Write the '
                     'description as the scene itself (who does what), not as a request: "a young warrior dies '
                     'before his time and is mourned", not "the theme of early death in epic".',
                     {'description': 'a sentence describing the scene', 'languages': 'optional: la, grc, en, he, cop, fa, ur'}),
    'search_one_text': (t_search_one_text, 'What one work says about a subject: Theme Search inside one work. Use it '
                        'when the reader names a work, or names passages to look for in particular works.',
                        {'work': 'the work in plain words', 'subject': 'the scene or subject', 'books': 'optional book or range'}),
    'theme_compare': (t_theme_compare, 'Passages of two works that tell similar scenes (content, not wording).',
                      {'text_a': 'first work', 'text_b': 'second work'}),
    'people_places': (t_people_places, 'Where a person, place or god is named in the corpus, with the inscriptions '
                      'and papyri that name it in any case form. Use it, not documents_search, for "which '
                      'inscriptions name X".', {'name': 'the name'}),
    'events': (_direct('events'), 'An ancient battle, siege, treaty or campaign: date, place, passages, documents.',
               {'name': 'the event or its place', 'label': 'optional full title'}),
    'documents_search': (_direct('documents_search'), 'Inscriptions and papyri, by words in Latin or Greek.',
                         {'query': 'Latin or Greek words', 'language': 'la or grc',
                          'kind': 'optional: inscriptions or papyri', 'place': 'optional findspot'}),
    'coins_search': (_direct('coins_search'), 'Greek and Roman coin types.', {'query': 'English words or legend', 'mint': 'optional'}),
    'objects_search': (_direct('objects_search'), 'Museum objects.', {'query': 'English words'}),
    'list_texts': (t_list_texts, 'How many works and authors the corpus holds, with the titles, in one language; '
                   'with no language, the counts for every language (use it for "how big is the corpus").',
                   {'language': 'optional: la, grc, en, cop, he, fa or ur'}),
}
OPTIONAL = {'languages', 'books', 'label', 'kind', 'place', 'mint', 'search_type', 'language', 'ref_end', 'context'}
STEP = {'site_help': 'reading the Help pages', 'read_passage': 'reading the passage', 'compare_texts': 'running the comparison',
        'rare_words': 'finding the rare words', 'line_search': 'searching the lines',
        'theme_search': 'running a Theme Search', 'search_one_text': 'searching inside the work',
        'theme_compare': 'comparing the two works by content', 'people_places': 'looking up the name',
        'events': 'looking up the event', 'documents_search': 'searching the inscriptions and papyri',
        'coins_search': 'searching the coins', 'objects_search': 'searching the objects', 'list_texts': 'listing the texts'}


def tool_specs():
    out = []
    for name, (_f, desc, args) in TOOLS.items():
        props = {k: {'type': 'string', 'description': v} for k, v in args.items()}
        out.append({'type': 'function', 'function': {'name': name, 'description': desc, 'parameters': {
            'type': 'object', 'properties': props, 'required': [k for k in args if k not in OPTIONAL]}}})
    return out


SYSTEM = """You are Tessa, the assistant of Tesserae, a free site for finding intertextual parallels and themes in Latin, Greek, English, Coptic, Hebrew, Persian and Urdu literature, with inscriptions, papyri, coins, museum objects and ancient events.

{pages}

How you work:
- Read the whole conversation. A follow-up ("those results", "the second one", "what about book 4", "in Greek?") refers to what came before: resolve it from the conversation and act on it.
- For anything about the corpus, a text, a search or its results, call the tools. Do not answer from memory when a tool can answer. If the reader names passages or works to look in, search those works.
- For a question about Tesserae itself (pages, features, settings, sources, accounts, the project), call site_help and answer from what it returns. If Help does not say, say so.
- Cite only passages, references and numbers that appear in tool results of THIS turn or your earlier answers. Quote a line only from a tool result of this turn: to quote, explain or name the speaker of a line from an earlier answer, call read_passage first.
- Do not add facts from memory: who speaks, where a place is, who a person was, what happens in a passage, which book tells an event. Take them from the tool results; if they do not say, say that briefly. Your memory of these texts is unreliable and the readers are specialists.
- A comparison still running is waited for (up to four minutes). If a tool result still says STILL RUNNING, say so plainly and give what the faster searches show.
- Never say what the corpus does or does not hold from a few search results: a short list is only the top of a ranking.
- Never report the results of a search that was not run. If a follow-up needs a search, run it.
- For a follow-up about the results of a comparison or search asked for earlier, run that search again (it answers at once) and cite from it.
- When the reader asks for passages about a named person, keep a passage only if its names_in_the_passage_text or passage_text_start names that person, or its summary plainly tells that person's story; leave out the others rather than attaching them to the person.
- Name a person in a passage only when the search result names them. The passage summaries often leave names out on purpose ("a young warrior"); keep their wording rather than guessing who it is.
- Speak of searches in plain words. Never name a tool, and never describe how the site looked a name up.
- Answer in plain prose, at most about 200 words, no headings. Write for a scholar of literature."""

_REF = re.compile(r'\b\d{1,3}\.\d{1,4}\b')


def unsupported_refs(text, outputs):
    blob = ' '.join(outputs)
    return sorted({r for r in _REF.findall(text) if r not in blob})


_ITEM = re.compile(r'^\s*(?:[-*\u2022]|\d+[.)])\s')
# A sentence ends at . ! or ? followed by a capital letter, but not after a short abbreviation such as
# "Aen." or "BC." (2026-10-22: splitting at "Aen." cut list items into fragments).
_SENT_END = re.compile(r'(?<=[.!?])\s+(?=[A-Z"\u201c(])')
_ABBREV = re.compile(r'\b[A-Z][a-z]{0,3}\.$')


def _sentences(para):
    parts, cur = [], ''
    for piece in _SENT_END.split(para):
        cur = f'{cur} {piece}' if cur else piece
        if not _ABBREV.search(cur):
            parts.append(cur)
            cur = ''
    if cur:
        parts.append(cur)
    return parts


def check_citations(text, outputs):
    """(text, dropped): a list item, or a sentence of prose, that gives a reference no search returned is
    removed whole."""
    bad = set(unsupported_refs(text, outputs))
    if not bad:
        return text, []
    kept, dropped = [], []
    for line in text.split('\n'):
        if _ITEM.match(line):
            (dropped if set(_REF.findall(line)) & bad else kept).append(line)
            continue
        sents = _sentences(line)
        keep = [x for x in sents if not (set(_REF.findall(x)) & bad)]
        dropped += [x for x in sents if set(_REF.findall(x)) & bad]
        kept.append(' '.join(keep))
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(kept)).strip(), dropped


# A quotation of the text, as opposed to a title or an English rendering: three or more words in quotation
# marks, or four or more in italics, with none of the common English words.
_QUOTE = re.compile(r'["\u201c\u00ab]([^"\u201d\u00bb\n]{8,300})["\u201d\u00bb]|(?<![*\w])\*([^*\n]{12,300})\*(?![*\w])')
_ENGLISH = {'the', 'and', 'of', 'to', 'that', 'with', 'from', 'was', 'are', 'they', 'their', 'she', 'it', 'on',
            'by', 'for', 'is', 'his', 'her', 'he', 'who', 'this', 'an', 'be', 'not', 'my', 'your', 'we', 'you', 'in', 'at',
            'as', 'or', 'its', 'one', 'all', 'when', 'how', 'what', 'has', 'have', 'can', 'will', 'into'}


def _fold(text):
    import unicodedata
    t = unicodedata.normalize('NFD', str(text)).lower().replace('v', 'u').replace('j', 'i')
    return ' '.join(re.sub(r'[^\w\s]|\d|_', ' ', ''.join(ch for ch in t if not unicodedata.combining(ch))).split())


def _quotes(text):
    out = []
    for m in _QUOTE.finditer(text):
        q = m.group(1) or m.group(2)
        words = _fold(q).split()
        if len(words) >= (3 if m.group(1) else 4) and not (set(words) & _ENGLISH):
            out.append(q)
    return out


def unverified_quotes(text, outputs):
    """Quotations of the text that no tool output of this turn holds (2026-10-22: asked about the second
    parallel, she quoted Aeneid 1.154 as a line it is not). A quotation passes when most of its runs of three
    words occur in the outputs, so a line quoted across a line break still passes."""
    blob = ' ' + _fold(' '.join(outputs)) + ' '
    bad = []
    for q in _quotes(text):
        w = _fold(q).split()
        grams = [' '.join(w[i:i + 3]) for i in range(len(w) - 2)]
        if sum(f' {g} ' in blob for g in grams) < 0.7 * len(grams):
            bad.append(q)
    return bad


def _drop_where(text, bad):
    """Remove each list item, or sentence of prose, for which bad(segment) is true."""
    kept, dropped = [], []
    for line in text.split('\n'):
        if _ITEM.match(line):
            (dropped if bad(line) else kept).append(line)
            continue
        sents = _sentences(line)
        kept.append(' '.join(x for x in sents if not bad(x)))
        dropped += [x for x in sents if bad(x)]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(kept)).strip(), dropped


_CAP = re.compile(r"\b[A-Z][a-z]{3,}\b")
# Capitalized words that are not names of persons or places in the texts.
_NOT_NAMES = {'latin', 'greek', 'english', 'coptic', 'hebrew', 'persian', 'urdu', 'arabic', 'roman', 'romans',
              'greeks', 'help', 'tesserae', 'tessa', 'search', 'searches', 'theme', 'reader', 'passages', 'similar',
              'intertextual', 'inscriptions', 'papyri', 'coins', 'objects', 'events', 'people', 'places', 'browse',
              'corpus', 'line', 'lines', 'phrase', 'rare', 'words', 'cross', 'language', 'book', 'books', 'both',
              'christian', 'christians', 'god', 'gods', 'bible', 'gospel', 'church', 'empire', 'republic', 'epic',
              'tragedy', 'comedy', 'senate', 'hellenistic', 'imperial', 'late', 'antiquity', 'classical',
              'collections', 'documents', 'downloads', 'about', 'connector', 'claude', 'compare', 'texts'}


def unsupported_names(text, context):
    """Names of persons or places in the middle of a sentence that appear nowhere in the search results,
    the question or the conversation (2026-10-22: she named Euryalus' mother "Caillina" and the mother of
    Aeneid 3.337 "Cassandra"). A name matches by its first five letters, so a case form counts."""
    known = {w[:5] for w in _fold(' '.join(context)).split()}
    try:
        _corrected('')                                    # loads the listing's author and title words
        known |= {w[:5] for w in _VOCAB.get('words', ())}
    except Exception:                                     # noqa: BLE001 -- the listing may be unavailable
        pass
    out = []
    for m in _CAP.finditer(text):
        word = m.group(0)
        before = text[:m.start()].rstrip(' *_"\'\u201c\u2018([')
        initial = not before or before[-1] in '.!?:\n-\u2022\u2014' or before.endswith('**')
        if (initial and not text[m.end():].startswith("'s")) or word.lower() in _NOT_NAMES:
            continue
        if _fold(word)[:5] not in known and word not in out:
            out.append(word)
    return out


RETRY = ('[Note from the site, not from the reader. The reader has not seen your draft.] Your draft {what}, '
         'which no search in this conversation returned. Call the tools that do (read_passage for the text of a '
         'line, compare_texts, search_one_text, events, people_places), then write your answer to the reader\'s '
         'question as if for the first time. Leave out whatever no tool gives. Do not mention this note, a draft, '
         'checking, confirming or re-running anything.')

# Openings that answer the note instead of the reader, removed if the model writes one anyway.
_CHECK_TALK = re.compile(r"^\s*(?:you'?re right[^.!?\n]*[.!?]|confirmed[^.!?\n]*[.!?:]|now (?:everything|i can)[^.!?\n]*[.!?]|"
                         r"(?:i'?ve|i have) (?:now )?(?:re-?run|re-?read|checked|verified)[^.!?\n]*[.!?])\s*", re.I)
_NUMBERED = re.compile(r'^(\s*)\d+([.)]\s)')
# After a send-back, a sentence that corrects a draft the reader never saw (2026-10-22: "I need to correct my
# earlier answer: the Thebaid was not written by Lucan").
_SELF_FIX = re.compile(r"\b(?:correct(?:ing)? my (?:earlier|previous)|my (?:earlier|previous) (?:answer|reply|draft)|"
                       r"i should not have|i was wrong|my mistake|i misspoke)\b", re.I)


def _tidy(text):
    """Removes an opening that talks about the check, and renumbers a numbered list from which items
    were removed (2026-10-22: lists read 3, 4, 6)."""
    for _ in range(2):
        text = _CHECK_TALK.sub('', text, count=1)
    out, n, prev_numbered = [], 0, False
    for line in text.split('\n'):
        m = _NUMBERED.match(line)
        if m:
            n = n + 1 if prev_numbered else 1
            line = f'{m.group(1)}{n}{m.group(2)}' + line[m.end():]
            prev_numbered = True
        elif line.strip():
            prev_numbered, n = False, 0
        out.append(line)
    return '\n'.join(out).strip()


def _problems(text, outputs, earlier, said=()):
    refs = unsupported_refs(text, outputs + earlier)
    quotes = unverified_quotes(text, outputs)
    names = unsupported_names(text, list(outputs) + list(earlier) + list(said))
    parts = []
    if names:
        parts.append('names ' + ', '.join(names[:8]))
    if refs:
        parts.append('cites ' + ', '.join(refs[:8]))
    if quotes:
        parts.append('quotes ' + '; '.join(f'"{q[:60]}"' for q in quotes[:4]))
    return ' and '.join(parts)


class GaveUp(Exception):
    """No clean answer: the caller lets the ordinary Tessa answer instead."""


_TOOL_TEXT = re.compile(r'<tool_call>|<function=|</function>')


def answer_stream(question, history=None):
    """Yields ('step', text), ('chunk', text) and one ('done', info). Raises on a gateway failure before
    any answer text, so the caller can fall back to the ordinary Tessa."""
    messages = [{'role': 'system', 'content': SYSTEM.format(pages=prompts.site_pages())}]
    for t in history or []:
        messages.append({'role': 'user' if t.get('role') == 'user' else 'assistant', 'content': t.get('text') or ''})
    messages.append({'role': 'user', 'content': question})
    calls, outputs, specs = [], [], tool_specs()
    wait = {'left': COMPARE_WAIT}
    # A follow-up about the results of a comparison asked for earlier ("which of them are the
    # strongest?"): the comparison is fetched again (from the cache) and given to the model first, so
    # every line it cites is in front of it. The model did not always run it again itself.
    try:
        from backend.assistant import agent as ordinary
        if history and ordinary._results_followup(question):
            pair = ordinary._earlier_pair(history)
            if pair and len(pair) == 2:
                yield ('step', 'fetching the comparison again')
                out = yield from _waiting(lambda: _compare_rows(pair), budget=wait)
                outputs.append(out)
                calls.append({'name': 'compare_texts', 'args': {'from_conversation': True}})
                # Appended to the opening instructions: the gateway's chat template takes a system message
                # only at the start of the conversation (HTTP 400 otherwise).
                messages[0]['content'] += ('\n\nThe comparison asked for earlier in this conversation, '
                                           'fetched again for this question:\n' + out)
    except Exception as e:                                # noqa: BLE001 -- the model can still run it itself
        logger.info('[ASSISTANT] tools mode could not refetch the comparison: %s', e)
    earlier = [t.get('text') or '' for t in history or [] if t.get('role') != 'user']
    said = [question] + [t.get('text') or '' for t in history or [] if t.get('role') == 'user']
    text, retried = None, False
    for rnd in range(MAX_ROUNDS):
        m = _chat(messages, specs)
        tcs = m.get('tool_calls') or []
        if not tcs:
            text = (m.get('content') or '').strip()
            # Cited or quoted from memory: sent back once to run the search, rather than shown with those
            # sentences cut (2026-10-22: a Latin storms list was cut to "Virgil, *A" after 25 citations
            # were dropped; follow-ups answered with no search invented speakers and lines).
            problem = _problems(text, outputs, earlier, said) if text and not _TOOL_TEXT.search(text) else ''
            if problem and not retried and rnd < MAX_ROUNDS - 1:
                retried = True
                logger.info('[ASSISTANT] tools mode sent the answer back: %s', problem[:200])
                yield ('step', 'checking the passages against the searches')
                messages.append({'role': 'user', 'content': RETRY.format(what=problem)})
                text = None
                continue
            break
        messages.append({'role': 'assistant', 'content': m.get('content') or '', 'tool_calls': tcs})
        for tc in tcs:
            name = tc.get('function', {}).get('name')
            try:
                args = json.loads(tc['function'].get('arguments') or '{}')
            except (ValueError, KeyError):
                args = {}
            yield ('step', STEP.get(name, 'searching'))
            try:
                if name in TOOLS:
                    out = yield from _waiting(lambda f=TOOLS[name][0], a=args: f(a), budget=wait)
                else:
                    out = f'No such search: {name}'
            except (searches.SearchError, urllib.error.URLError, OSError, ValueError, KeyError) as e:
                out = f'The search failed: {e}'
            calls.append({'name': name, 'args': args})
            outputs.append(out)
            messages.append({'role': 'tool', 'tool_call_id': tc.get('id'), 'content': out})
    if text is None:
        messages.append({'role': 'user', 'content': 'Answer the question now from the search results above. '
                                                   'Do not call any more searches.'})
        text = (_chat(messages, None).get('content') or '').strip()
    if not text or _TOOL_TEXT.search(text):
        raise GaveUp(f'no clean answer after {len(calls)} searches')
    text, dropped = check_citations(text, outputs + earlier)
    bad_quotes = set(unverified_quotes(text, outputs))
    if bad_quotes:
        text, more = _drop_where(text, lambda seg: any(q in seg for q in bad_quotes))
        dropped += more
    if dropped:
        logger.info('[ASSISTANT] tools mode dropped %d sentence(s) with unsupported references or quotes', len(dropped))
    text = _tidy(text)
    if retried:
        text, more = _drop_where(text, lambda seg: bool(_SELF_FIX.search(seg)))
        dropped += more
    if not text.strip():
        raise GaveUp('every sentence of the answer cited something no search returned')
    yield ('chunk', text)
    yield ('done', {'searches_run': [c['name'] for c in calls], 'tool_calls': calls, 'mode': 'tools',
                    'citations_dropped': len(dropped)})
