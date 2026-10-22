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

def _one(name):
    hits = corpus_lookup.named_texts(name, limit=1) or corpus_lookup.named_texts(str(name).title(), limit=1)
    return hits[0] if hits else None


def _pair(a, b):
    pair = corpus_lookup.named_texts(f'compare {a} with {b}', limit=2)
    if len(pair) < 2:
        pair = [p for p in (_one(a), _one(b)) if p]
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


def _compare_rows(pair):
    la, lb = pair[0].get('language') or 'la', pair[1].get('language') or 'la'
    names = [p.get('display_name') or _id(p) for p in pair]
    if la == lb:
        page = searches.fusion_page(_id(pair[0]), _id(pair[1]), la, 25)
    else:
        page = searches.crosslingual_page(_id(pair[0]), _id(pair[1]), la, lb, 25)
    if page is None:
        return (f'The comparison of {names[0]} with {names[1]} has started and is still running on the server. '
                'Tell the reader so, and that the Intertextual Search page shows it when it finishes.')
    rows = page if isinstance(page, list) else (page.get('parallels') or page.get('results') or [])
    return _clip({'compared': names, 'top_parallels': _fusion_compact(rows)}, 7000)


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
        return _clip(ordinary._language_holdings_fact(code), 6000)
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
    'people_places': (_direct('people_places'), 'Where a person, place or god is named in the corpus.', {'name': 'the name'}),
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
OPTIONAL = {'languages', 'books', 'label', 'kind', 'place', 'mint', 'search_type', 'language'}
STEP = {'site_help': 'reading the Help pages', 'compare_texts': 'running the comparison',
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
- Cite only passages, references and numbers that appear in tool results. Anything you add from general knowledge, mark as background.
- If a comparison is still running, say so plainly.
- Never say what the corpus does or does not hold from a few search results: a short list is only the top of a ranking.
- Never report the results of a search that was not run. If a follow-up needs a search, run it.
- For a follow-up about the results of a comparison or search asked for earlier, run that search again (it answers at once) and cite from it.
- When the reader asks for passages about a named person, keep a passage only if its names_in_the_passage_text or passage_text_start names that person, or its summary plainly tells that person's story; leave out the others rather than attaching them to the person.
- Name a person in a passage only when the search result names them. The passage summaries often leave names out on purpose ("a young warrior"); keep their wording rather than guessing who it is.
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
    # A follow-up about the results of a comparison asked for earlier ("which of them are the
    # strongest?"): the comparison is fetched again (from the cache) and given to the model first, so
    # every line it cites is in front of it. The model did not always run it again itself.
    try:
        from backend.assistant import agent as ordinary
        if history and ordinary._results_followup(question):
            pair = ordinary._earlier_pair(history)
            if pair and len(pair) == 2:
                yield ('step', 'fetching the comparison again')
                out = _compare_rows(pair)
                outputs.append(out)
                calls.append({'name': 'compare_texts', 'args': {'from_conversation': True}})
                # Appended to the opening instructions: the gateway's chat template takes a system message
                # only at the start of the conversation (HTTP 400 otherwise).
                messages[0]['content'] += ('\n\nThe comparison asked for earlier in this conversation, '
                                           'fetched again for this question:\n' + out)
    except Exception as e:                                # noqa: BLE001 -- the model can still run it itself
        logger.info('[ASSISTANT] tools mode could not refetch the comparison: %s', e)
    text = None
    for _ in range(MAX_ROUNDS):
        m = _chat(messages, specs)
        tcs = m.get('tool_calls') or []
        if not tcs:
            text = (m.get('content') or '').strip()
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
                out = TOOLS[name][0](args) if name in TOOLS else f'No such search: {name}'
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
    earlier = [t.get('text') or '' for t in history or [] if t.get('role') != 'user']
    text, dropped = check_citations(text, outputs + earlier)
    if dropped:
        logger.info('[ASSISTANT] tools mode dropped %d sentence(s) with unsupported references', len(dropped))
    yield ('chunk', text)
    yield ('done', {'searches_run': [c['name'] for c in calls], 'tool_calls': calls, 'mode': 'tools',
                    'citations_dropped': len(dropped)})
