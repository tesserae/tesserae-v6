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
from collections import Counter

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
# One search was enough for a first question and never enough for a follow-up:
# "are you sure it's not in Eobanus?" needs the phrase looked up AND the author
# resolved. The cap exists to stop a model spending the machine on an open
# question, so it rises rather than disappears.
MAX_SEARCHES = 3

# Questions the seeded listing already answers. Asking the model what else to
# search when the answer is already in hand is a wasted round trip.
# Questions ABOUT the tool rather than about the corpus. These must reach the
# guide, which knows how the site works and how to connect an outside assistant.
# Two things would otherwise go wrong: the carry-over heuristic treats any short
# question as a follow-up, so "How can I use my AI agent with Tesserae?" would
# inherit the previous phrase and search for it; and the no-punt rule, added so
# corpus questions are never handed back as advice, would answer a how-to
# question with a list of Latin works.
_ABOUT_THE_TOOL = (
    'my ai', 'own ai', 'ai agent', 'ai assistant', 'chatgpt', 'claude',
    'connector', 'mcp', 'api', 'export', 'csv', 'download',
    'how do i use', 'how can i use', 'how does this', 'how do you',
    'what is the difference between', 'what does this site', 'log in', 'account',
)


def _is_about_the_tool(question):
    q = (question or '').lower()
    return any(t in q for t in _ABOUT_THE_TOOL)


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


# Words that look like names but are not people.
_NOT_PEOPLE = {'latin', 'greek', 'hebrew', 'coptic', 'english', 'book', 'corpus',
               'tesserae', 'bible', 'renaissance', 'classical', 'what', 'where',
               'which', 'does', 'this', 'that', 'they', 'there', 'about', 'also'}


def _highlight_terms(facts):
    """The words worth marking in an answer: the phrase, and its inflections.

    A listing of six lines of Latin with nothing marked makes the reader hunt
    for what matched. The phrase searched for is known exactly, and the variant
    pass knows the inflected forms, so both can be marked.
    """
    terms = set()
    for f in facts or []:
        q = (f.get('args') or {}).get('query') or f.get('phrase')
        if q:
            terms.add(str(q))
            terms.update(w for w in str(q).split() if len(w) > 3)
        for e in (f.get('examples') or []) + (f.get('lines') or []):
            for w in (e.get('matched_words') or []) if isinstance(e, dict) else []:
                if isinstance(w, str) and len(w) > 3:
                    terms.add(w)
    return sorted(terms, key=len, reverse=True)[:12]


def _integrity_warning(removed, invented, fabricated, mispaired):
    """A visible note when a guard failed, in the reader's own view.

    Detecting a fabricated citation and then printing it unannotated is worse
    than not checking: it lends the invention the authority of a tool that
    claims to verify. If a check fails the reader must be told, in the answer,
    not in a log file they will never see.
    """
    parts = []
    if mispaired:
        refs = ', '.join(r for r, _ in mispaired[:4])
        parts.append(f'the text shown under {refs} does not match what the search '
                     f'returned for those references')
    if fabricated:
        parts.append('some quoted text could not be found in the search results')
    if removed:
        refs = ', '.join(str(r) for r in list(removed)[:4])
        parts.append(f'these citations did not come from a search that ran: {refs}')
    if invented:
        parts.append('some figures above are not in the results: '
                     + ', '.join(str(n) for n in list(invented)[:4]))
    if not parts:
        return ''
    return ('\n\n\u26a0 Do not rely on the passage list above: '
            + '; '.join(parts) + '. This is an automatic check of the answer '
            'against the searches that ran. Verify against the text itself.')


def _offer_phrase(facts):
    for f in facts or []:
        if str(f.get('kind', '')).startswith('VARIANT') and f.get('phrase'):
            return f['phrase']
    return None


def _variant_offer(facts, text):
    """A sentence offering the inflected forms, when the answer omits one.

    The prompt asks for this and the model does it when the answer is short and
    forgets when it is long, which is exactly when it matters most: a listing of
    six exact hits is precisely the answer that hides the twenty-one inflected
    ones. Prompt-only fixes have failed all day, so this is computed.
    """
    if not facts:
        return ''
    low = (text or '').lower()
    if 'variant' in low or 'inflect' in low:
        return ''
    for f in facts:
        if not str(f.get('kind', '')).startswith('VARIANT'):
            continue
        # Read the TOTALS, not the truncated top-15 list. Reading the truncated
        # dict is how the offer once reported 175 where the answer was 194.
        authors = f.get('authors_with_variants_TOP15_ONLY') or {}
        n = f.get('total_variant_occurrences') or sum(authors.values())
        count = f.get('authors_with_variants_count') or len(authors)
        if not n:
            continue
        names = ', '.join(list(authors)[:3])
        more = f' and {count - 3} more' if count > 3 else ''
        return (f'\n\n\u201c{f.get("phrase")}\u201d also {OFFER_MARK} '
                f'{n} times, across {count} authors not listed above '
                f'({names}{more}). Would you like those as well?')
    return ''


def _lines_for_author(raw, who):
    """Citation and text for one author's hits, out of a raw search response."""
    out = []
    for r in ((raw or {}).get('results') or []):
        if who.lower() not in str(r.get('author') or '').lower():
            continue
        bits = [r.get('author'), r.get('work'), r.get('locus')]
        out.append({'ref': ' '.join(str(b) for b in bits if b),
                    'text': str(r.get('text') or '')[:200]})
    return out


def _named_people(question):
    """Capitalised names in the question, as author candidates.

    Deliberately loose. It costs nothing to check a name that turns out not to
    be an author, and it cost a whole exchange to miss one that was.
    """
    out = []
    for w in re.findall(r'\b([A-Z][a-zA-Z]{3,})\b', question or ''):
        k = w.strip('.,;:?"\'')
        if k.lower() not in _NOT_PEOPLE and k not in out:
            out.append(k)
    return out[:4]


_AFFIRMATIVE = {'yes', 'yes please', 'yep', 'yeah', 'ok', 'okay', 'sure',
                'please', 'please do', 'go ahead', 'show me', 'show them',
                'list them', 'yes list them', 'i would', 'y'}


def _variant_answer(phrase, history, step):
    """The inflected forms, grouped by author, as a fact block to narrate from.

    Computed rather than left to a chooser, because the reader has already said
    what they want and a second round of deliberation can only lose it.
    """
    from collections import Counter
    step(f'listing the inflected forms of "{phrase}"')
    try:
        exact = searches.run('line_search', {'query': phrase, 'language': 'la',
                                             'search_type': 'exact', 'max_results': 60})
        var = searches.run('line_search', {'query': phrase, 'language': 'la',
                                           'search_type': 'lemma', 'max_results': 300})
    except searches.SearchError as e:
        return {'error': f'the search failed: {e}'}

    exact_authors = {str(r.get('author')) for r in (exact.get('results') or [])}
    rows = [r for r in (var.get('results') or [])
            if str(r.get('author')) not in exact_authors]
    by_author = Counter(str(r.get('author')) for r in rows)

    def ref_of(r):
        return ' '.join(str(b) for b in (r.get('author'), r.get('work'), r.get('locus')) if b)

    # Grouped, and spread across authors rather than 20 lines of Livy.
    seen, lines = Counter(), []
    for r in rows:
        a = str(r.get('author'))
        if seen[a] >= 3:
            continue
        seen[a] += 1
        lines.append({'ref': ref_of(r), 'text': str(r.get('text') or '')[:160]})
        if len(lines) >= 24:
            break

    facts = [{
        'kind': f'THE INFLECTED FORMS of "{phrase}", which the reader has just '
                f'asked for. These are the authors who do NOT have the phrase '
                f'exactly as written. Report the totals, then LIST these lines '
                f'grouped by author. Do NOT repeat the exact occurrences: the '
                f'reader has already seen them.',
        'phrase': phrase,
        'total_occurrences': len(rows),
        'author_count': len(by_author),
        'by_author': dict(by_author.most_common(20)),
        'lines': lines,
    }]
    block = ('THE READER ASKED FOR THE INFLECTED FORMS. Answer with these and '
             'nothing else.\n'
             + json.dumps(facts, ensure_ascii=False)[:FACTS_CHAR_CAP])
    return {'block': block, 'facts': facts,
            # The model is asked the QUESTION, and the question was the word
            # "yes". Given a block of Cicero and Sallust and the prompt "yes",
            # it reproduced the previous answer instead. An acceptance has to
            # reach the model as the request it stands for.
            'question_override': (
                f'List the inflected forms of "{phrase}" in the authors who do '
                f'not have it exactly as written. Give the totals, then list the '
                f'lines grouped by author.'),
            'ran': ['line_search(exact)', 'line_search(lemma variants)']}


def _is_affirmative(question):
    q = (question or '').strip().lower().rstrip('.!')
    return q in _AFFIRMATIVE or q.startswith(('yes', 'please show', 'show me the',
                                              'list the', 'show the'))


# The exact sentence the offer is made with. Kept as a constant so the thing
# that WRITES the offer and the thing that RECOGNISES it cannot drift apart,
# which is how this broke the first time.
OFFER_MARK = 'occurs in other inflected forms'


def _pending_offer_from(history):
    """The phrase an offer in the recent history was about, or None.

    A fallback for when the server-side record is unavailable: reads the last
    assistant turn, and only accepts an offer that is the MOST RECENT thing
    said, so "yes" cannot reach back past an intervening question.
    """
    for turn in reversed(history or []):
        role = (turn or {}).get('role')
        if role != 'assistant':
            continue
        text = str(turn.get('text') or '')
        if OFFER_MARK not in text:
            return None            # the last thing said was not an offer
        # The offer NAMES its phrase in curly quotes, so accepting it needs no
        # guessing. Deriving it from the sentence instead once returned the word
        # "also", because "phrase also occurs" matches the phrase pattern.
        m = re.search(r'\u201c([^\u201d]{3,60})\u201d', text)
        return m.group(1) if m else _last_phrase(history)
    return None


def _last_phrase(history):
    for turn in reversed(history or []):
        if (turn or {}).get('role') == 'user':
            p = _quoted_phrase(turn.get('text') or '')
            if p:
                return p
    return None


def _carried_phrase(question, history):
    """The phrase an earlier turn established, when this turn omits it.

    A follow-up rarely repeats its subject. "How about in any post-classical
    authors?" and "are you sure it's not in Eobanus?" are both about the phrase
    named two turns earlier, and without it the assistant had nothing to search
    for, so it asked the user to do the searching.

    Only fills a GAP: a question carrying its own quoted phrase keeps it.
    """
    if not history or _quoted_phrase(question) or _is_about_the_tool(question):
        return None
    # A follow-up is short and refers back. A fresh question that simply
    # happens to lack quotation marks should not inherit the last subject.
    ql = (question or '').lower()
    refers_back = (len(ql.split()) <= 14
                   or any(w in ql for w in (' it ', "it's", 'it?', 'that one',
                                            'how about', 'what about', 'any other',
                                            'the phrase', 'same phrase')))
    if not refers_back:
        return None
    for turn in reversed(history[-6:]):
        if (turn or {}).get('role') != 'user':
            continue
        found = _quoted_phrase(turn.get('text') or '')
        if found:
            return found
    return None


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

# 260 tokens truncated answers mid-word: "...including Eobanus, Iliad, Book 2;
# Eobanus, I" and then nothing. A listing answer needs room for the list.
# A listing answer is long: thirteen citations with their lines ran past 900 and
# stopped mid-word, losing the count and the offer that should close it.
ANSWER_TOKENS = 1500

# Large enough to hold a listing answer's worth of lines. The old 3,000 silently
# dropped the very facts the question was about.
FACTS_CHAR_CAP = 14000

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

LISTING. When the user asks for the instances, the occurrences, the passages or
the examples, GIVE THEM: one per line, citation first, then the line of text if
the results carry it. That is the answer to that question, and a paragraph
describing that instances exist is not. Do not stop at three of them because
prose habit says to; list what the results hold, up to about fifteen, and say
how many more there are. Asked "can you give the Eobanus instances?", the right
answer is the list of Eobanus lines.

OFFER WHAT THEY CANNOT SEE. If the results include variant forms, say how many
there are and offer to list them. A reader told only about exact matches has no
way to know the inflected ones exist, so mentioning the count and asking is the
difference between a true answer and a useful one.

Otherwise three to five sentences of plain scholarly English, no headings."""


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

        def excerpt(r, width=200):
            """The passage around the MATCH, not its first 200 characters.

            A prose window can be 1,400 characters with the phrase near the end,
            so a head-truncated excerpt showed Salutati discoursing on poetry and
            stopped before reaching "arma virumque" at all. The reader was shown
            a citation with nothing in it to justify the citation.
            """
            t = ' '.join(str(r.get('text') or '').split())
            if len(t) <= width:
                return t
            # The words the SEARCH says it matched. _summarise does not see the
            # query, and does not need to: the result carries what matched.
            words = [w for w in (r.get('matched_words') or []) if isinstance(w, str)]
            low = t.lower()
            at = -1
            for w in words:
                at = low.find(str(w).lower())
                if at >= 0:
                    break
            if at < 0:
                return t[:width] + '...'
            start = max(0, at - width // 3)
            end = min(len(t), start + width)
            return ('...' if start else '') + t[start:end] + ('...' if end < len(t) else '')
        works = sorted({f"{r.get('author')}, {r.get('work')}"
                        for r in results if r.get('author')})
        # Authors and eras, counted. The variant pass compares author sets, and
        # a question like "any post-classical authors?" is answerable directly
        # from era rather than by the model guessing from names -- it guessed
        # wrong, calling Salutati's De Laboribus Herculis Renaissance and then
        # saying in the same breath that it does not contain the phrase, having
        # itself reported the phrase there one turn earlier.
        authors = Counter(str(r.get('author')) for r in results if r.get('author'))
        eras = Counter(str(r.get('era')) for r in results if r.get('era'))
        by_era = {}
        for r in results:
            if r.get('author') and r.get('era'):
                by_era.setdefault(str(r['era']), set()).add(str(r['author']))
        return {'kind': 'phrase occurrences',
                'authors': dict(authors.most_common(20)),
                'eras': dict(eras.most_common()),
                'authors_by_era': {k: sorted(v) for k, v in sorted(by_era.items())},
                'hits_returned': len(results),
                'hits_in_corpus': raw.get('total') or raw.get('total_at_least'),
                'distinct_loci': raw.get('distinct_loci'),
                'works_containing_it': works[:15],
                # Six examples against twelve hits made the model report "6
                # distinct occurrences". It was counting what it could see. Show
                # enough to list, and say how many exist either way.
                'examples_shown': min(len(results), 20),
                'examples': [{'ref': ref_of(r),
                              'matched_words': r.get('matched_words'),
                              'text': excerpt(r)}
                             for r in results[:20]]}
    if name == 'rare_words':
        return {'kind': 'rare shared words', 'returned': len(results),
                'total_rare_in_corpus': raw.get('total_rare_words'),
                'words': [{'word': w.get('lemma') or w.get('word'),
                           'occurrences': w.get('count') or w.get('occurrences')}
                          for w in results[:15]]}
    return {'kind': name, 'raw_size': len(results)}


def answer_stream(question, on_step=None, history=None, offered_phrase=None):
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
            # history MUST be threaded here too. It was not, and that is the
            # whole reason the conversation fix appeared to work in testing and
            # did nothing in the browser: answer() passes history, this streaming
            # path did not, and the browser uses this one. Tested through the
            # HTTP endpoint now, not through answer(), so the two cannot diverge
            # again without a test noticing.
            prep_result.update(_prepare(question, q.put, history, offered_phrase) or {})
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
    asked = prep.get('question_override') or question
    for piece in model.stream(ANSWER_SYSTEM,
                              f'{block}\n\nQuestion: {asked}\n\nAnswer:',
                              max_tokens=ANSWER_TOKENS, temperature=0.2):
        collected.append(piece)
        yield ('chunk', piece)

    text = ''.join(collected)
    # Every place a citation can legitimately come from. This read only
    # 'examples', so the twelve genuine Eobanus citations, which arrive under
    # 'lines', were all counted as unsupported and the answer was marked
    # unclean for quoting exactly what it was given.
    allowed = []
    for f in all_facts:
        for key in ('examples', 'lines'):
            allowed += [e.get('ref') for e in (f.get(key) or [])
                        if isinstance(e, dict) and e.get('ref')]
    _, removed = model.strip_unsupported_references(text, allowed)
    ok_numbers, invented = model.numbers_preserved(block, text, question)
    ok_quotes, fabricated = model.quotes_supported(block, text)
    ok_pairs, mispaired = model.quotes_paired(all_facts, text)

    # SAY SO, IN THE ANSWER. The guards used to log and let the text stand, so a
    # reader saw a fabricated citation with nothing to warn them. Streaming means
    # the words are already on their screen and cannot be retracted, so the
    # correction is appended where they will read it.
    warn = _integrity_warning(removed, invented, fabricated, mispaired)
    if warn:
        yield ('chunk', warn)

    offer = _variant_offer(all_facts, text)
    if offer:
        yield ('chunk', offer)
    yield ('done', {'searches_run': ran, 'facts': all_facts,
                    'highlight': _highlight_terms(all_facts),
                    # So the server can remember that an offer was made. The
                    # session cookie carries QUESTIONS only, so an assistant
                    # offer is invisible to a follow-up unless it is recorded.
                    'offered_variants': bool(offer),
                    'offer_phrase': _offer_phrase(all_facts) if offer else None,
            'guardrails': {'references_removed': removed,
                                   'unsupported_numbers': invented,
                                   'fabricated_quotes': fabricated,
                                   'mispaired_quotes': mispaired,
                                   'clean': (not removed and ok_numbers
                                             and ok_quotes and ok_pairs)}})


def _prepare(question, step, history=None, offered_phrase=None):
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

    # A question about the tool is answered by the guide, which has the facts
    # about connectors and CSV export. Searching the corpus for it is nonsense.
    if _is_about_the_tool(question):
        return {'needs_model_only': True}

    # "YES" MEANS THE THING THAT WAS OFFERED.
    #
    # She offers the inflected forms, the reader says "yes", and she re-ran the
    # same exact search and printed the same six lines again. The affirmative
    # carried no content of its own, so the carry-over logic just repeated the
    # previous question. An offer that cannot be accepted is not an offer.
    # AN OFFER AND ITS ACCEPTANCE ARE ONE PIECE OF STATE.
    #
    # This was three separate conditions -- is the reply affirmative, did the
    # previous answer mention variants, can a phrase be recovered -- and any one
    # of them failing silently made "yes" repeat the previous answer instead. It
    # failed three times for three different reasons, each invisible.
    #
    # Now the offer carries what accepting it means. If it is pending and the
    # reader says yes, it is taken. Nothing to re-derive, nothing to match on.
    pending = offered_phrase or _pending_offer_from(history)
    if pending and _is_affirmative(question):
        logger.info('[ASSISTANT] accepting the pending offer: variants of %r', pending)
        return _variant_answer(pending, history, step)

    # RESOLVE THE QUESTION AGAINST THE CONVERSATION FIRST.
    #
    # "are you sure it's not in Eobanus?" arrived with no idea what "it" was,
    # because nothing carried the previous turn. So no phrase was found, no
    # search ran, and the question fell through to the guide, which has no
    # corpus access and could only recite tool names. The user had to be told
    # to run the search himself, which is the failure this whole module exists
    # to remove.
    carried = _carried_phrase(question, history)

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
    phrase = _quoted_phrase(question) or carried
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
            ran.append(f'line_search({mode})')

            # THE VARIANT PASS. An exact search finds the phrase as written and
            # nothing else, so "arma virumque" misses Eobanus entirely while he
            # has 35 lines carrying arma with vir in some other case: "arma
            # virosque", "arma viros", "arma virum". Reporting the exact hits
            # alone and stopping there is a true answer that leaves the more
            # interesting one unsaid. So whenever an exact search runs, the
            # inflected forms get looked up too, and the extra authors it turns
            # up are offered as variants rather than folded in as if identical.
            if mode == 'exact':
                try:
                    step(f'checking inflected variants of "{phrase}"')
                    var = searches.run('line_search', {
                        'query': phrase, 'language': lang, 'search_type': 'lemma',
                        'max_results': 300})
                    vf = _summarise('line_search', var)
                    exact_authors = set((facts.get('authors') or {}))
                    extra = {a: n for a, n in (vf.get('authors') or {}).items()
                             if a not in exact_authors}
                    if extra:
                        # Totals from the WHOLE set, before any truncation. The
                        # offer used to sum a dict capped at 15 authors and
                        # reported 175 where the answer is 194, across 30
                        # authors rather than 13.
                        total_variant_hits = sum(extra.values())
                        variant_author_count = len(extra)
                        all_facts.append({
                            'kind': 'VARIANT FORMS of the same phrase, found by '
                                    'lemma search. These authors do NOT have the '
                                    'phrase exactly as written, but do have it in '
                                    'other inflected forms. Tell the user how many '
                                    'there are and offer to list them.',
                            'phrase': phrase,
                            'total_variant_occurrences': total_variant_hits,
                            'authors_with_variants_count': variant_author_count,
                            'authors_with_variants_TOP15_ONLY': dict(sorted(
                                extra.items(), key=lambda kv: -kv[1])[:15]),
                            'variant_lines': [
                                {'ref': ' '.join(str(b) for b in
                                                 (x.get('author'), x.get('work'), x.get('locus')) if b),
                                 'text': str(x.get('text') or '')[:160]}
                                for x in (var.get('results') or [])
                                if str(x.get('author')) not in exact_authors][:20],
                            'example_lines': (vf.get('examples') or [])[:6]})
                        ran.append('line_search(lemma variants)')

                    # THE LINES THEMSELVES, for any author the question names.
                    # "Can you give the Eobanus instances?" could not be answered
                    # because the facts carried the number 21 and no lines. A
                    # count is not an instance.
                    for who in _named_people(question):
                        lines = _lines_for_author(var, who) or _lines_for_author(raw, who)
                        if lines:
                            all_facts.append({
                                'kind': f'THE ACTUAL LINES in {who}. If the user asks '
                                        f'for the instances, occurrences or examples, '
                                        f'LIST THESE, citation first.',
                                'author': who,
                                'total_found': len(lines),
                                'lines': lines[:12]})
                except searches.SearchError as e:
                    logger.info('[ASSISTANT] variant search failed: %s', e)

            # If the question names an author, answer FOR THAT AUTHOR instead of
            # leaving the user to scan a list.
            for who in _named_people(question):
                hits = [a for a in (facts.get('authors') or {}) if who.lower() in a.lower()]
                all_facts.append({
                    'kind': f'the user asked specifically about {who}',
                    'exact_phrase_in_' + who: hits or 'no exact occurrences',
                    'note': ('Check the variant-forms fact above before saying the '
                             'phrase is absent from this author.')})
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
        # Falling back to the guide here is what produced "use string_search
        # with the exact phrase". The guide cannot see the corpus, so it can
        # only name tools. If the question is about the corpus at all, list
        # what is there and answer from that rather than handing the work back.
        try:
            step('listing what the corpus holds')
            f = _summarise('list_texts', searches.run('list_texts', {'language': 'la'}))
            f.update({'search': 'list_texts', 'args': {'language': 'la'}})
            all_facts.append(f)
            ran.append('list_texts(la)')
        except searches.SearchError:
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

    # MOST SPECIFIC FACTS FIRST, and a cap that does not cut them.
    #
    # This was 3,000 characters with the facts in the order they were gathered.
    # Asked "can you give the Eobanus instances?", the block ran to 5,723
    # characters, the 21 Eobanus lines sat at 3,867-5,512, and every one of them
    # was discarded before the model saw it. It then produced twelve fabricated
    # citations, each quoting the Aeneid's opening line as though it were
    # Eobanus. Invented primary text is the worst thing this tool can emit.
    #
    # So: facts carrying actual LINES go first, because they are what a question
    # about instances is answered from, and the cap is large enough to hold them.
    def specificity(f):
        if f.get('lines'):
            return 0
        if f.get('kind', '').startswith('VARIANT'):
            return 1
        if f.get('search') == 'line_search':
            return 2
        return 3

    ordered = sorted(all_facts, key=specificity)
    body = json.dumps(ordered, ensure_ascii=False)
    if len(body) > FACTS_CHAR_CAP:
        body = body[:FACTS_CHAR_CAP] + (
            '\n\n[TRUNCATED. Some results were not shown. Say so if the user asks '
            'for a complete list; do NOT invent the remainder.]')
    block += ('SEARCH RESULTS (your only source of fact about specific passages).\n'
              'Quote passage text ONLY as it appears here, character for character.\n'
              'If a line you want is not here, say it is not shown rather than '
              'reconstructing it.\n' + body)
    return {'block': block, 'facts': all_facts, 'ran': ran}


def answer(question, on_step=None, history=None, offered_phrase=None):
    """Non-streaming answer. Kept for callers that want the whole thing at once."""
    step = on_step or (lambda _s: None)
    prep = _prepare(question, step, history, offered_phrase)
    if prep.get('error') or prep.get('needs_model_only'):
        return prep
    block, all_facts, ran = prep['block'], prep['facts'], prep['ran']
    step('reading the results')
    text = model.complete(ANSWER_SYSTEM,
                          f'{block}\n\nQuestion: '
                          f'{prep.get("question_override") or question}\n\nAnswer:',
                          max_tokens=ANSWER_TOKENS, temperature=0.2)
    if not text:
        return {'error': 'could not compose an answer', 'facts': all_facts}
    # Every place a citation can legitimately come from. This read only
    # 'examples', so the twelve genuine Eobanus citations, which arrive under
    # 'lines', were all counted as unsupported and the answer was marked
    # unclean for quoting exactly what it was given.
    allowed = []
    for f in all_facts:
        for key in ('examples', 'lines'):
            allowed += [e.get('ref') for e in (f.get(key) or [])
                        if isinstance(e, dict) and e.get('ref')]
    text, removed = model.strip_unsupported_references(text, allowed)
    ok_numbers, invented = model.numbers_preserved(block, text, question)
    ok_quotes, fabricated = model.quotes_supported(block, text)
    ok_pairs, mispaired = model.quotes_paired(all_facts, text)
    text += _integrity_warning(removed, invented, fabricated, mispaired)
    text += _variant_offer(all_facts, text)
    return {'answer': text, 'searches_run': ran, 'facts': all_facts,
            'highlight': _highlight_terms(all_facts),
            'guardrails': {'references_removed': removed,
                           'unsupported_numbers': invented,
                           'fabricated_quotes': fabricated,
                           'mispaired_quotes': mispaired,
                           'clean': (not removed and ok_numbers
                                     and ok_quotes and ok_pairs)}}
