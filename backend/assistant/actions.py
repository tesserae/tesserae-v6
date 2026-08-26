"""Links into the site, built from the searches that actually ran.

WHY THE MODEL DOES NOT WRITE THESE

Tessa's new job is to help someone USE Tesserae rather than to reprint results
in a chat panel. That means handing the reader a control that opens the real
search page with the real query in it.

A link is a promise that something exists. If the model wrote the URLs it would
eventually offer a search of a work that is not in the corpus, in a language the
page does not accept, and the reader would land on an empty page believing the
corpus had been consulted. So the model never composes one. Every action here is
built in code from arguments a search has ALREADY been run with, or from
identifiers the corpus itself returned.

The vocabulary is the site's own, and most of it already existed:

    /line-search?q=&type=       reads and auto-runs both parameters
    /theme-search?query=&languages=
    /?source=&target=&lang=     the same shape buildShareableUrl() produces
    /read?work=&ref=&refEnd=&tab=

Actions are plain data: {kind, label, detail, url}. The page renders them as
ordinary links, so they can be middle-clicked, bookmarked and shared. Nothing
navigates on its own.
"""
from urllib.parse import urlencode

# What the page will accept. A language the site cannot search is not offered.
LANGUAGES = {'la', 'grc', 'he', 'cop', 'en', 'fa', 'ur', 'ar'}
SEARCH_TYPES = {'exact', 'lemma', 'regex'}
MAX_ACTIONS = 4

_TYPE_WORD = {'exact': 'exact', 'lemma': 'all inflected forms', 'regex': 'pattern'}
_LANG_WORD = {'la': 'Latin', 'grc': 'Greek', 'he': 'Hebrew', 'cop': 'Coptic',
              'en': 'English', 'fa': 'Persian', 'ur': 'Urdu', 'ar': 'Arabic'}


def _line_search(phrase, search_type='exact', language='la'):
    if not phrase or search_type not in SEARCH_TYPES:
        return None
    if language not in LANGUAGES:
        return None
    q = urlencode({'q': phrase, 'type': search_type})
    return {
        'kind': 'line_search',
        'label': f'Search “{phrase}” · {_TYPE_WORD[search_type]}',
        'detail': _LANG_WORD.get(language, language),
        'url': f'/line-search?{q}',
    }


def _theme_search(query, language=None):
    if not query:
        return None
    args = {'query': query}
    if language in LANGUAGES:
        args['languages'] = language
    return {
        'kind': 'theme_search',
        'label': f'Theme Search: “{query}”',
        'detail': ('passages matched by content'
                   + (f' · {_LANG_WORD[language]} only' if language in LANGUAGES else '')),
        'url': f'/theme-search?{urlencode(args)}',
    }


def _compare(source, target, language='la', source_author=None,
             target_author=None, label=None):
    """The main fusion search over two texts, or over two authors.

    AUTHOR-LEVEL IS NOT A FALLBACK, it is the honest answer to a question that
    named no work. Asked about "echoes of Vergil in Statius", picking a work for
    each is a guess, and the guess was wrong: an id-length tiebreak made Statius
    the Silvae and Ovid the Ibis. The site searches by author, so a reader who
    named an author gets an author search.
    """
    if language not in LANGUAGES:
        return None
    args = {'lang': language}
    if source and target:
        args.update({'source': source, 'target': target})
        detail = f'{source} and {target}'
    elif source_author and target_author:
        args.update({'source_author': source_author, 'target_author': target_author})
        detail = f'all of {source_author} against all of {target_author}'
    else:
        return None
    # SAY WHAT IT DOES. Line search and Theme Search run themselves from a URL;
    # the main comparison only fills the form in, and a comparison is expensive
    # enough that pressing Search yourself is reasonable. Labelling it as though
    # it ran would be a small lie told every time.
    detail += ' · opens the search ready to run'
    return {
        'kind': 'compare',
        'label': label or 'Compare these two texts',
        'detail': detail,
        'url': f'/?{urlencode(args)}',
    }


def _read(work, ref=None, ref_end=None, language=None, name=None):
    """Open a text in the Reader, at a passage when one is known.

    `ref` is optional: "how do I read the Aeneid?" names a work and no line, and
    refusing to build a link without one left that question with no answer at
    all. With a ref it lands on the passage; without, it opens the work.
    """
    if not work:
        return None
    args = {'work': work if str(work).endswith('.tess') else f'{work}.tess'}
    if language in LANGUAGES:
        args['lang'] = language
    if ref:
        args.update({'ref': ref, 'refEnd': ref_end or ref, 'tab': 'translation'})
    return {
        'kind': 'read',
        'label': (f'Open {ref} in the Reader' if ref
                  else f'Read {name or work} in the Reader'),
        'detail': ('with the translation alongside' if ref
                   else 'with connections to the rest of the corpus'),
        'url': f'/read?{urlencode(args)}',
    }


def _dedupe(actions):
    seen, out = set(), []
    for a in actions:
        if not a or a['url'] in seen:
            continue
        seen.add(a['url'])
        out.append(a)
    return out[:MAX_ACTIONS]


def _real_text(text_id):
    """Does the corpus hold this id? Fails CLOSED: if the corpus cannot be
    consulted, no link is offered, because an unchecked link is the thing this
    module exists to prevent."""
    try:
        from backend.assistant import corpus_lookup
        return corpus_lookup.is_text_id(text_id)
    except Exception:                                    # noqa: BLE001
        return False


def build(facts, question=''):
    """Actions for this answer, most useful first.

    Reads only the slots a search recorded. A fact with no usable arguments
    contributes nothing rather than a guess.
    """
    out = []
    for f in facts or []:
        kind = str(f.get('kind') or '')

        # The search that was actually run, with the arguments it was run with.
        if kind == 'phrase occurrences' and isinstance(f.get('args'), dict):
            a = f['args']
            phrase = a.get('query')
            out.append(_line_search(phrase, a.get('search_type') or 'exact',
                                    a.get('language') or 'la'))
            # The same phrase the other way, which is the commonest next
            # question and the one the tool descriptions warn about.
            if (a.get('search_type') or 'exact') == 'exact':
                out.append(_line_search(phrase, 'lemma', a.get('language') or 'la'))

        # The offer of the inflected forms, as something clickable rather than a
        # question that has to be answered in words.
        if kind.startswith('VARIANT FORMS') and f.get('phrase'):
            out.append(_line_search(f['phrase'], 'lemma', 'la'))

        if kind.startswith('THE INFLECTED FORMS') and f.get('phrase'):
            out.append(_line_search(f['phrase'], 'lemma', 'la'))

        # Two texts the reader asked to have compared. Nothing was searched:
        # this IS the answer, and the fusion search is what does the comparing.
        if kind.startswith('TWO TEXTS') and isinstance(f.get('args'), dict):
            a = f['args']
            out.append(_compare(
                a.get('source'), a.get('target'), a.get('language') or 'la',
                source_author=a.get('source_author'),
                target_author=a.get('target_author'),
                label=f'Compare {f.get("source")} with {f.get("target")}'))

        # A text the reader asked to open.
        if kind.startswith('A TEXT THE READER WANTS TO OPEN') and isinstance(f.get('args'), dict):
            a = f['args']
            out.append(_read(a.get('work'), language=a.get('language'),
                             name=f.get('text_name')))

        # A theme search that ran: the page is where the reader can widen it,
        # narrow it to one language, or read any of the passages.
        if kind == 'passages matching a description' and isinstance(f.get('args'), dict):
            out.append(_theme_search((f['args'] or {}).get('query')))

        # Two named texts that were compared for rare shared vocabulary: the
        # full fusion search over the same pair is the deeper version of it.
        #
        # These ids are CHECKED, unlike the phrase search's arguments. rare_words
        # is given its texts by the MODEL, and asked about echoes of Vergil in
        # Statius it chose "Vergil_Aeneid" and "Statius_Thebaid" -- neither of
        # which exists. The search still ran and still returned something, so
        # "a search ran with these arguments" is not evidence the texts are real.
        if kind == 'rare shared words' and isinstance(f.get('args'), dict):
            a = f['args']
            src = str(a.get('source') or '').replace('.tess', '')
            tgt = str(a.get('target') or '').replace('.tess', '')
            if _real_text(src) and _real_text(tgt):
                out.append(_compare(src, tgt, a.get('language') or 'la'))

    return _dedupe(out)


# What a question is ASKING FOR, decided by its words. The model is not asked,
# for the same reason it is not asked to write URLs: a guide that recommends the
# wrong tool confidently is worse than one that says less.
_COMPARE_INTENT = ('compare', 'echoes', 'echo of', 'borrow', 'parallel',
                   'allusion', 'allude', 'imitat', 'influence', 'reuse',
                   'intertext', 'model for', 'draw on', 'draws on')
_READ_INTENT = ('read ', 'reading ', 'open ', 'look at ', 'see the text',
                'show me the text', 'view ')
_THEME_INTENT = ('passages about', 'passages where', 'scenes', 'scene where',
                 'theme of', 'themes of', 'motif', 'episodes', 'anything about',
                 'passages describing', 'where someone', 'depictions of',
                 'descriptions of')


def _theme_subject(question):
    """The thing a thematic question is about, with the asking stripped off."""
    q = str(question or '').strip().rstrip('?')
    for lead in ('are there any', 'are there', 'is there any', 'is there',
                 'can you find', 'can i find', 'find me', 'show me', 'i want',
                 'how do i find', 'how can i find', 'where can i find',
                 'i am looking for', "i'm looking for", 'look for'):
        if q.lower().startswith(lead):
            q = q[len(lead):].strip()
    for cut in ('passages about', 'passages where', 'passages describing',
                'descriptions of', 'depictions of', 'scenes of', 'scene where',
                'scenes where', 'scenes', 'theme of', 'themes of', 'episodes of',
                'anything about', 'motif of'):
        idx = q.lower().find(cut)
        if idx != -1:
            q = q[idx + len(cut):].strip()
            break
    q = q.strip(' ,.:;"\'')
    return q if len(q) >= 4 else ''


# The bare pages, for a how-to that names no subject to work on. "How do I
# search for a phrase?" is a fair question with no phrase in it, and answering
# it with prose alone leaves the reader to go and find the page themselves --
# which is the work Tessa exists to save.
_BARE_TOOLS = (
    (('phrase', 'word search', 'search for a word', 'exact search',
      'lemma search', 'line search', 'find a word', 'search for a phrase'),
     {'kind': 'line_search', 'label': 'Open Line Search',
      'detail': 'find a word or phrase across the corpus', 'url': '/line-search'}),
    (('theme', 'passages about', 'content search', 'by content', 'theme search'),
     {'kind': 'theme_search', 'label': 'Open Theme Search',
      'detail': 'find passages by what happens in them', 'url': '/theme-search'}),
    (('compare', 'comparison', 'two texts', 'intertext'),
     {'kind': 'compare', 'label': 'Open the comparison search',
      'detail': 'score two texts against each other', 'url': '/'}),
    (('read', 'reader', 'reading'),
     {'kind': 'read', 'label': 'Open the Reader',
      'detail': 'read a text with its connections alongside', 'url': '/read'}),
)


def bare_tool(question):
    """The page a how-to is about, when no subject was named."""
    q = str(question or '').lower()
    for words, action in _BARE_TOOLS:
        if any(w in q for w in words):
            return dict(action)
    return None


def suggest(question, lookup=None):
    """Actions for a question where NO search has run.

    This is the guide half: someone asks how to do something, and the useful
    answer is the tool, already set up, rather than its name. Everything is
    decided from the reader's own words and from texts the corpus really holds;
    where a name cannot be resolved, nothing is offered.
    """
    if lookup is None:
        from backend.assistant import corpus_lookup as lookup
    q = str(question or '').lower()
    out = []

    if any(t in q for t in _COMPARE_INTENT):
        try:
            hits = lookup.named_texts(question, limit=2)
        except Exception:                                # noqa: BLE001
            hits = []
        if len(hits) >= 2:
            a, b = hits[0], hits[1]
            lang = a.get('language') or 'la'
            if a.get('matched') == 'author' and b.get('matched') == 'author':
                out.append(_compare(
                    None, None, lang,
                    source_author=a.get('author'), target_author=b.get('author'),
                    label=f'Compare {a.get("author")} with {b.get("author")}'))
            else:
                out.append(_compare(
                    str(a.get('id') or '').replace('.tess', ''),
                    str(b.get('id') or '').replace('.tess', ''), lang,
                    label=(f'Compare {a.get("display_name") or a.get("id")} '
                           f'with {b.get("display_name") or b.get("id")}')))

    if any(t in q for t in _THEME_INTENT):
        subject = _theme_subject(question)
        if subject:
            out.append(_theme_search(subject))

    if any(t in q for t in _READ_INTENT):
        try:
            hits = lookup.named_texts(question, limit=1)
        except Exception:                                # noqa: BLE001
            hits = []
        if hits:
            t = hits[0]
            out.append(_read(str(t.get('id') or '').replace('.tess', ''),
                             language=t.get('language'),
                             name=t.get('display_name')))

    # Only when nothing specific was found: a bare page beats no control at all,
    # but a set-up search beats a bare page.
    if not any(a for a in out):
        out.append(bare_tool(question))

    return _dedupe(out)


def for_suggestion(kind, **slots):
    """An action for something Tessa RECOMMENDS but has not run.

    Used by the guide path, where no search has happened and the useful answer
    is "this is the tool you want, here it is set up".
    """
    builders = {'line_search': _line_search, 'theme_search': _theme_search,
                'compare': _compare, 'read': _read}
    fn = builders.get(kind)
    if not fn:
        return None
    try:
        return fn(**slots)
    except TypeError:
        return None
