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

MAX_SEARCHES = 2

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


def answer(question, on_step=None):
    """Answer a question by running a search and reporting what it returned.

    on_step, if given, is called with short progress strings, so an interface can
    say "looking..." rather than showing a blank while a search runs.

    Returns {answer, searches_run, facts, guardrails} or falls back to
    {needs_model_only: True} when no search applies.
    """
    if not model.is_available():
        return {'error': 'the assistant is not running just now'}

    step = on_step or (lambda _s: None)
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

    for _ in range(MAX_SEARCHES):
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

    step('reading the results')
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
    block += ('SEARCH RESULTS (your only source of fact about specific passages):\n'
              + json.dumps(all_facts, ensure_ascii=False, indent=1)[:6000])
    text = model.complete(ANSWER_SYSTEM, f'{block}\n\nQuestion: {question}\n\nAnswer:',
                          max_tokens=380, temperature=0.2)
    if not text:
        return {'error': 'could not compose an answer', 'facts': all_facts}

    # The same guardrails the analyse path uses. Loci the model produced that are
    # not in the results are removed rather than trusted.
    allowed = []
    for f in all_facts:
        allowed += [e.get('ref') for e in (f.get('examples') or []) if e.get('ref')]
    text, removed = model.strip_unsupported_references(text, allowed)
    ok_numbers, invented = model.numbers_preserved(block, text)
    return {'answer': text, 'searches_run': ran, 'facts': all_facts,
            'guardrails': {'references_removed': removed,
                           'unsupported_numbers': invented,
                           'clean': not removed and ok_numbers}}
