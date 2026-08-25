"""Ask, look, answer: the loop that lets the assistant use the corpus.

Without this the guide half can only name tools. Asked "recommend interesting
searches across Hebrew and Greek" it lists which searches exist, three times
running, because it has never seen a text. Here it picks a search, the backend
runs it, findings are computed in Python, and the model narrates those and
nothing else.

    question
      -> model returns JSON naming a search and its arguments
      -> the name is checked against the table; unknown names are refused
      -> the search RUNS
      -> what came back is reduced to computed facts
      -> model narrates the facts
      -> guardrails strip any locus or figure it added

The division of labour is the same one the analyse path already uses and which
made a 30B model safe there: EVERY FACT IS COMPUTED, the model only writes. What
changes here is that the facts now come from a search the assistant chose, rather
than from results a user already had.

Bounded at two searches. A loop able to call search repeatedly will, and an
assistant that can consume the machine on one open-ended question is worse than
one that cannot look at all.
"""
import json
import re

from backend.logging_config import get_logger
from backend.assistant import model, searches

logger = get_logger('assistant.agent')

# ONE chooser call after seeding, not two.
#
# Measured: census 1.0s (cached thereafter), a listing 0.1s, a chooser call 2.6s,
# the answer call 5.6s. The searches are nearly free; the model calls are the
# cost. Two chooser rounds bought a second search that rarely changed the answer
# and always cost another 2.6s, plus a longer facts block that slowed generation
# again. Seeding already puts the corpus holdings in front of the model, so one
# further search is enough for the questions this handles.
MAX_SEARCHES = 1

# Questions the seeded listing already answers. Asking the model what else to
# search when the answer is already in hand is a wasted round trip.
_HOLDINGS_QUESTION = (
    'what texts', 'which texts', 'what works', 'which works', 'what do you have',
    'what is in', "what's in", 'what does the corpus', 'how many', 'do you have',
    'what authors', 'which authors', 'recommend', 'suggest', 'interesting',
    'where do i start', 'where should i', 'what could i', 'ideas',
)

# A quoted phrase can be searched WITHOUT asking the model which tool to use.
# The question already says what to look for and the answer is always the same
# search, so the chooser call is pure latency. Matches "..." and 'the phrase X'.
# Character ranges the phrase extractor accepts. The first version covered
# Latin and basic Greek but NOT Greek Extended (U+1F00-1FFF), where the breathing
# marks live, so a question about ῥοδοδάκτυλος extracted nothing and the fast
# path silently did not fire. Hebrew and Coptic were missing entirely.
_SCRIPTS = (r'a-zA-Z'
            r'\u00c0-\u024f'      # Latin with diacritics
            r'\u0370-\u03ff'      # Greek and Coptic
            r'\u1f00-\u1fff'      # Greek Extended: breathings and accents
            r'\u0590-\u05ff'      # Hebrew
            r'\u2c80-\u2cff')     # Coptic

_QUOTED = re.compile(
    r'["\u201c\u2018]([^"\u201d\u2019]{3,60})["\u201d\u2019]'
    r'|\bphrase\s+([' + _SCRIPTS + r' ]{3,40}?)\s*'
    r'(?:appear|occur|used|found|in\b|\?|$)')


# Words too common to be a useful work-name probe.
_LOOKUP_STOP = {'book', 'the', 'and', 'with', 'for', 'what', 'where', 'which',
                'compare', 'comparing', 'between', 'against', 'search', 'text',
                'texts', 'work', 'works', 'passage', 'corpus', 'latin', 'greek',
                'hebrew', 'coptic', 'english', 'recommend', 'interesting'}


def _named_works(question):
    """Resolve author and work names in the question against the real listing.

    Runs on every question, whatever searches were chosen, because the failure it
    fixes had nothing to do with which search ran: the model was told the corpus
    holds 1,826 Latin works, shown 20 of them, and concluded that the 1,806 it
    could not see did not exist.
    """
    probes = {w.strip('.,;:?"\'').lower()
              for w in re.findall(r'\b([A-Z][a-zA-Z]{3,})\b', question)}
    probes -= _LOOKUP_STOP
    if not probes:
        return {}
    try:
        return searches.find_works(probes)
    except Exception as e:            # a lookup failure must not lose the answer
        logger.info('[ASSISTANT] work lookup failed: %s', e)
        return {}


def _quoted_phrase(question):
    m = _QUOTED.search(question)
    if not m:
        return None
    p = (m.group(1) or m.group(2) or '').strip(' ?.,')
    return p if len(p.split()) <= 6 and len(p) >= 3 else None

CHOOSE_SYSTEM = """You are choosing which search to run against a corpus of ancient literature to answer a scholar's question.

Available searches:
{menu}

Reply with ONLY a JSON object:
  {{"search": "<name>", "args": {{...}}, "why": "<one clause>"}}

Or, if no search would help and the question is about how the tool works:
  {{"search": null, "why": "<one clause>"}}

Rules:
- Use only a search named above. Never invent one.
- If the question is open ("what is interesting in X"), start with list_texts to
  find out what the corpus actually holds, so your answer names real works.
- Text ids come from list_texts. Do not guess them.
- line_search matches the ORIGINAL SCRIPT. Greek texts are in Greek letters,
  Hebrew in Hebrew letters, Coptic in Coptic letters. A transliteration will not
  match: search for the Greek word as the Greek writes it, not as
  "rhododaktylos". If you cannot write the original script, use list_texts and
  answer from the holdings instead of running a search that cannot succeed.
- line_search matches the ORIGINAL-LANGUAGE TEXT. Searching an English word
  against Greek, Hebrew or Coptic finds nothing, because those texts are not in
  English. To search Homer for "rosy-fingered dawn" you must search the Greek
  (rhododaktylos); to ask what Coptic holds on monasticism, use list_texts and
  read the titles, because "monasticism" is an English abstraction that appears
  in no Coptic line.
- Word-based searches (line_search, rare_words) work WITHIN one language only.
  Across two languages they return noise. That does NOT mean no search helps:
  list_texts still tells you what each language holds, which is usually what an
  open question needs.
No prose outside the JSON."""

ANSWER_SYSTEM = """You are answering a scholar's question about a corpus of ancient literature.

A search has been RUN and its results are given to you below. These are your only
source of fact.

Absolute rules:
- Name only works, authors and passages that appear in the results.
- Never state a number that is not in the results.
- If the results are thin or empty, say so plainly. "The corpus holds little on
  this" is a real answer and a useful one.
- A corpus census is given first. It is TRUE. Never write that the corpus lacks
  a language or an author that the census shows it holds. A search returning
  nothing shows only that THAT search returned nothing.
- Do not describe what other searches would find. You have one set of results;
  report it.

Three to five sentences of plain scholarly English. No headings, no lists."""


def _extract_json(text):
    m = re.search(r'\{.*\}', text or '', re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except ValueError:
        return None


def _summarise(name, raw):
    """Reduce a raw search response to the facts a narration may use.

    Computed here rather than handed to the model whole: a full result payload
    is thousands of lines, and a model given the raw thing will quote the parts
    that look quotable rather than the parts that matter.
    """
    if name == 'list_texts':
        rows = raw if isinstance(raw, list) else []
        authors = sorted({r.get('author') for r in rows if r.get('author')})
        # SPREAD the sample across the alphabet, do not take the head. Listing
        # returns authors in order, so the first twelve Greek authors are
        # Aeschylus, Aelian, Aelius Aristides, Achilles Tatius and so on. Given
        # only those, the model suggested comparing kingship in Samuel with
        # Aelian's Varia Historia: a real work, poorly chosen, because it was the
        # only thing on offer. A spread gives Homer, Plato and Sophocles a chance
        # to appear.
        def spread(xs, n):
            if len(xs) <= n:
                return xs
            step = len(xs) / n
            return [xs[int(i * step)] for i in range(n)]
        return {'kind': 'corpus listing', 'works': len(rows),
                'authors': len(authors),
                'sample_authors': spread(authors, 20),
                'sample_authors_note': 'a spread across the whole alphabetical '
                                       'listing, not the first few',
                'sample_works': spread([r.get('display_name') for r in rows], 12)}
    results = (raw.get('results') or raw.get('matches') or
               raw.get('words') or []) if isinstance(raw, dict) else []
    if name == 'line_search':
        # The real field names are author / work / locus, NOT reference or ref.
        # Looking for the wrong ones returned empty refs for every hit, and the
        # model duly reported that "specific references are not provided".
        def ref_of(r):
            bits = [r.get('author'), r.get('work'), r.get('locus')]
            return ' '.join(str(b) for b in bits if b)
        works = sorted({f"{r.get('author')}, {r.get('work')}"
                        for r in results if r.get('author')})
        return {'kind': 'phrase occurrences',
                'hits_returned': len(results),
                'hits_in_corpus': raw.get('total') or raw.get('total_at_least'),
                'distinct_loci': raw.get('distinct_loci'),
                'works_containing_it': works[:15],
                'examples': [{'ref': ref_of(r),
                              'matched_words': r.get('matched_words'),
                              'text': str(r.get('text') or '')[:160]}
                             for r in results[:6]]}
    if name == 'rare_words':
        return {'kind': 'rare shared words', 'returned': len(results),
                'total_rare_in_corpus': raw.get('total_rare_words'),
                'words': [{'word': w.get('lemma') or w.get('word'),
                           'occurrences': w.get('count') or w.get('occurrences')}
                          for w in results[:15]]}
    return {'kind': name, 'raw_size': len(results)}


def answer_stream(question, on_step=None):
    """Same loop, but yield the answer as it is written.

    Total time is 18-36s and most of it is generation. First tokens arrive in
    about two seconds, so streaming is most of the difference between this
    feeling immediate and feeling broken: the reader starts reading at once and
    generation outpaces reading.

    Yields ('step', text) while searching, then ('chunk', text) repeatedly, then
    ('done', {facts, searches_run, guardrails}). The guardrails can only run on
    the finished text, so their verdict comes last and the caller decides what to
    do about it -- the same contract the analyse endpoint already uses.
    """
    # Steps are forwarded through a queue as they happen, not collected and
    # flushed at the end. Collected, they all appeared at once after eight
    # seconds of silence, which tells the reader nothing while they are waiting
    # and everything once they no longer need it.
    import queue
    q = queue.Queue()
    prep_result = {}

    def worker():
        try:
            prep_result.update(_prepare(question, q.put) or {})
        finally:
            q.put(None)

    import threading
    th = threading.Thread(target=worker, daemon=True)
    th.start()
    while True:
        item = q.get()
        if item is None:
            break
        yield ('step', item)
    th.join()
    prep = prep_result
    if prep.get('error') or prep.get('needs_model_only'):
        yield ('done', prep)
        return

    block, all_facts, ran = prep['block'], prep['facts'], prep['ran']
    yield ('step', 'reading the results')
    collected = []
    for piece in model.stream(ANSWER_SYSTEM,
                              f'{block}\n\nQuestion: {question}\n\nAnswer:',
                              max_tokens=260, temperature=0.2):
        collected.append(piece)
        yield ('chunk', piece)

    text = ''.join(collected)
    allowed = []
    for f in all_facts:
        allowed += [e.get('ref') for e in (f.get('examples') or []) if e.get('ref')]
    _, removed = model.strip_unsupported_references(text, allowed)
    ok_numbers, invented = model.numbers_preserved(block, text, question)
    yield ('done', {'searches_run': ran, 'facts': all_facts,
                    'guardrails': {'references_removed': removed,
                                   'unsupported_numbers': invented,
                                   'clean': not removed and ok_numbers}})


def _prepare(question, step):
    """Run the searches and build the fact block. Shared by both answer paths.

    Everything up to composing prose: seeding, the fast paths, the chooser, and
    reducing raw results to computed facts. Returns either
    {block, facts, ran} or {error} / {needs_model_only}.
    """
    if not model.is_available():
        return {'error': 'the assistant is not running just now'}
    if not model.is_available():
        return {'error': 'the assistant is not running just now'}

    ran, all_facts = [], []

    # SEED THE LOOP IN CODE, not by asking. Whichever languages the question
    # names get listed before the model chooses anything.
    #
    # This is the structural fix for a failure that three rounds of prompt
    # wording could not stop. Left to choose, the model either ran a meaningless
    # cross-language word search and read its noise as evidence of absence, or,
    # once told not to, refused to search at all and returned nothing. Neither
    # is acceptable, and both came from it deciding what to look at.
    #
    # A question that names a language always gets that language's holdings.
    for code, words in (('he', ('hebrew',)), ('grc', ('greek',)),
                        ('la', ('latin',)), ('cop', ('coptic',)),
                        ('en', ('english',))):
        if any(w in question.lower() for w in words):
            try:
                step(f'listing what the corpus holds in {words[0]}')
                facts = _summarise('list_texts', searches.run('list_texts', {'language': code}))
                facts.update({'search': 'list_texts', 'args': {'language': code}})
                all_facts.append(facts)
                ran.append(f'list_texts({code})')
            except searches.SearchError as e:
                logger.info('[ASSISTANT] seed listing %s failed: %s', code, e)

    # A quoted phrase needs no deliberation: run the exact search for it.
    phrase = _quoted_phrase(question)
    if phrase:
        lang = next((c for c, w in (('he', 'hebrew'), ('grc', 'greek'),
                                    ('cop', 'coptic'), ('en', 'english'))
                     if w in question.lower()), 'la')
        # EXACT only for Latin-script languages. Greek exact search returns
        # nothing at all -- ῥοδοδάκτυλος finds 0 hits exact and 5 hits by lemma,
        # correctly landing on Homer 24.788 -- almost certainly because the
        # stored text carries diacritics that exact matching does not normalise.
        # Hebrew and Coptic are untested and presumed to share the problem, so
        # they take the mode that is known to work.
        mode = 'exact' if lang in ('la', 'en') else 'lemma'
        try:
            step(f'searching for "{phrase}"')
            raw = searches.run('line_search', {'query': phrase, 'language': lang,
                                               'search_type': mode})
            facts = _summarise('line_search', raw)
            facts.update({'search': 'line_search',
                          'args': {'query': phrase, 'search_type': mode}})
            all_facts.append(facts)
            ran.append('line_search(exact)')
        except searches.SearchError as e:
            logger.info('[ASSISTANT] phrase search failed: %s', e)

    # If the seed answered a holdings question, go straight to composing.
    skip_chooser = bool(all_facts) and (phrase or any(
        h in question.lower() for h in _HOLDINGS_QUESTION))
    for _ in range(0 if skip_chooser else MAX_SEARCHES):
        prompt = f'Question: {question}\n'
        if all_facts:
            prompt += (f'\nAlready found:\n{json.dumps(all_facts, ensure_ascii=False)[:1500]}'
                       f'\n\nIf that is enough to answer, reply with search null.')
        raw = model.complete(CHOOSE_SYSTEM.format(menu=searches.tool_menu()),
                             prompt, max_tokens=200, temperature=0.1)
        choice = _extract_json(raw)
        if not choice or not choice.get('search'):
            break
        name, args = choice['search'], choice.get('args') or {}
        if any(f.get('search') == name and f.get('args') == args for f in all_facts):
            # It already ran this exact search. Asking again wastes a model call
            # and a search, and it did exactly that on "arma virumque".
            break
        step(f'running {name}')
        try:
            result = searches.run(name, args)
        except searches.SearchError as e:
            # Say what failed. An assistant that silently drops a failed search
            # and answers anyway is inventing.
            logger.info('[ASSISTANT] %s failed: %s', name, e)
            all_facts.append({'search': name, 'args': args, 'failed': str(e)})
            break
        facts = _summarise(name, result)
        facts.update({'search': name, 'args': args})
        all_facts.append(facts)
        ran.append(name)

    if not all_facts:
        return {'needs_model_only': True}

    # The census goes in FIRST, before the search results. Without it the model
    # reads "my search found no Greek" as "there is no Greek", and no wording of
    # the rules prevented that.
    try:
        census = searches.corpus_census()
    except Exception:
        census = {}
    block = ''
    if census:
        block += ('WHAT THE CORPUS CONTAINS (true regardless of any search below):\n'
                  + ', '.join(f'{k}: {v} works' for k, v in census.items())
                  + '\n\n')
    named = _named_works(question)
    if named:
        block += ('WORKS THE QUESTION NAMES, LOOKED UP IN THE CORPUS (authoritative;\n'
                  'these ARE present, whether or not a search below happened to '
                  'return them):\n')
        for probe, hits in named.items():
            block += f'  {probe}: {len(hits)} matching, e.g. ' + '; '.join(hits[:4]) + '\n'
        block += ('\nSo do NOT write that the corpus lacks any of these. If the user '
                  'asks how to compare them, recommend an approach using them.\n\n')

    block += ('SEARCH RESULTS (your only source of fact about specific passages):\n'
              + json.dumps(all_facts, ensure_ascii=False)[:3000])
    return {'block': block, 'facts': all_facts, 'ran': ran}


def answer(question, on_step=None):
    """Non-streaming answer. Kept for callers that want the whole thing at once."""
    step = on_step or (lambda _s: None)
    prep = _prepare(question, step)
    if prep.get('error') or prep.get('needs_model_only'):
        return prep
    block, all_facts, ran = prep['block'], prep['facts'], prep['ran']
    step('reading the results')
    text = model.complete(ANSWER_SYSTEM,
                          f'{block}\n\nQuestion: {question}\n\nAnswer:',
                          max_tokens=260, temperature=0.2)
    if not text:
        return {'error': 'could not compose an answer', 'facts': all_facts}
    allowed = []
    for f in all_facts:
        allowed += [e.get('ref') for e in (f.get('examples') or []) if e.get('ref')]
    text, removed = model.strip_unsupported_references(text, allowed)
    ok_numbers, invented = model.numbers_preserved(block, text, question)
    return {'answer': text, 'searches_run': ran, 'facts': all_facts,
            'guardrails': {'references_removed': removed,
                           'unsupported_numbers': invented,
                           'clean': not removed and ok_numbers}}
