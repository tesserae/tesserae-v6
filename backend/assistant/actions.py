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


def _compare(source, target, language='la'):
    """The main fusion search over two texts."""
    if not source or not target or language not in LANGUAGES:
        return None
    args = {'source': source, 'target': target, 'lang': language}
    return {
        'kind': 'compare',
        'label': 'Compare these two texts',
        'detail': f'{source} and {target}',
        'url': f'/?{urlencode(args)}',
    }


def _read(work, ref, ref_end=None):
    if not work or not ref:
        return None
    args = {'work': work if str(work).endswith('.tess') else f'{work}.tess',
            'ref': ref, 'refEnd': ref_end or ref, 'tab': 'translation'}
    return {
        'kind': 'read',
        'label': f'Open {ref} in the Reader',
        'detail': 'with the translation alongside',
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

        # Two named texts that were compared for rare shared vocabulary: the
        # full fusion search over the same pair is the deeper version of it.
        if kind == 'rare shared words' and isinstance(f.get('args'), dict):
            a = f['args']
            out.append(_compare(a.get('source'), a.get('target'),
                                a.get('language') or 'la'))

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
