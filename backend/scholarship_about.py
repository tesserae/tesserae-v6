"""What the scholarship results are made from: sources, terms and methods.

GET /api/scholarship/about assembles this for the page /scholarship-sources,
read-only and kept for an hour. The fixed text (terms, services, methods)
lives here, not in the data and not in the front end, so the page and the API
agree. The figures in METHODS are those of SCHOLARSHIP_ROW and
SCHOLARSHIP_THEME_ROW in client/src/data/searchScope.js and must be changed
together with them.
"""
import os
import sqlite3
import threading
import time

from backend import scholarship as S
from backend.work_names import base_work

CACHE_SECONDS = 3600

LANGUAGE_NAMES = {'la': 'Latin', 'grc': 'Greek', 'he': 'Hebrew', 'ar': 'Arabic', 'fa': 'Persian',
                  'ur': 'Urdu', 'cop': 'Coptic', 'en': 'English', 'de': 'German', 'fr': 'French', 'it': 'Italian'}

# The terms of each journal index, written here and not read from the data.
EJC_TERMS = 'Public domain, full text indexed and quoted by the sentence.'
MUSE_TERMS = ('Licensed text, indexed for citations, never displayed beyond one sentence in the Reader. '
              'Article titles and links are shown.')

INDEX_DESCRIPTIONS = {
    'ejc': {
        'name': 'JSTOR Early Journal Content',
        'description': 'Journals published before 1923, public domain, fetched from the Internet Archive. '
                       'Every page was read for citations of the works held here.',
        'terms': EJC_TERMS,
    },
    'muse': {
        'name': 'Project MUSE',
        'description': 'Journals on Project MUSE, read under the University at Buffalo Libraries\' text and data '
                       'mining permission of 12 October 2026, one article a minute. One sentence is kept for each citation.',
        'terms': MUSE_TERMS,
    },
}

# Keyed by the service's name. Each value says what the service returns and what is read.
SERVICES = {
    'OpenAlex': 'Titles and abstracts of articles, chapters and books, searched for the passage\'s citation forms. '
                'Only open metadata is read.',
    'Crossref': 'Titles and abstracts of articles and chapters, searched in the same way. Only open metadata is read.',
    'Unpaywall': 'Whether a legal free copy of an article exists, and where. It supplies the "free copy" badge. '
                 'Only the address of the open copy is read.',
    'CORE': 'Sentences from the full text of open-access papers that quote the passage. Only open-access text is read.',
    'Semantic Scholar': 'Short text snippets from open-access papers that cite the passage. Only open-access text is read.',
    'Google Books': 'Book titles and the short snippet Google shows for a citation on a book page. No book text is read beyond that snippet.',
    'HathiTrust': 'A link into HathiTrust\'s full-text search for the passage\'s citation forms. '
                  'The site does not query HathiTrust. The link opens the search in the reader\'s browser.',
}
SERVICES_NOTE = ('Only open metadata and open-access text are read. A subscription article opens through the '
                 'reader\'s own library link, set under My library in the Reader\'s Scholarship tab.')

# Fixed text of the methods. Figures copied exactly from client/src/data/searchScope.js.
METHODS = [
    {'id': 'recognition', 'title': 'How a citation is recognized',
     'text': 'A citation is found in the text of an article by a table of abbreviations (for example "Aen." and '
             '"Verg. A.") joined to a locus, with the author named near it deciding between works that share an '
             'abbreviation. On sixty citing sentences read by eye from the journals of 1827 to 1922, 58 of 60 cite the '
             'passage they are attached to (October 2026). On a read of sixty citations from the Project MUSE index, '
             '88 percent were right.'},
    {'id': 'citing', 'title': 'Articles that cite these passages',
     'text': 'The passages found by the search are looked up by their locus in both citation indexes. The articles '
             'that cite them are merged by article, with the passages each cites, and listed newest first.'},
    {'id': 'paragraph', 'title': 'What the notes and articles say',
     'text': 'The question is matched by meaning and by keyword against the commentary notes and the sentences of '
             'journals from before 1923, restricted to the work. The language model writes one paragraph from the best '
             'matches, with numbered citations that link to the note or article, and a holdings line says what was '
             'searched. In the test of fifteen scholar questions, judged on the first 230 characters of each note, '
             'a strongly relevant note was in the first ten for 13 of 15 questions (nDCG at 10 of 0.64). Meaning alone '
             'gave 11 of 15 and keyword alone 12 of 15 (October 2026).'},
    {'id': 'online', 'title': 'Found online for this question',
     'text': 'The words of the question are sent to the live services listed above. Each result is ranked by the '
             'service that returned it and carries the badge "book" or "article". A result shows "free copy" when '
             'Unpaywall or CORE gives a legal open copy. Each result appears as its service answers.'},
    {'id': 'never', 'title': 'What is never shown',
     'text': 'More than one sentence of a licensed article is never shown. Nothing is shown from a service that did '
             'not answer.'},
]


def work_language_map():
    """({work: {languages}}, {language folders present}) from the texts folder."""
    texts_root = os.path.join(S.ROOT, 'texts')
    work_lang = {}
    try:
        for lang in os.listdir(texts_root):
            d = os.path.join(texts_root, lang)
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                if fn.endswith('.tess'):
                    work_lang.setdefault(base_work(fn[:-5]), set()).add(lang)
    except OSError:
        pass
    present = set(os.listdir(texts_root)) if os.path.isdir(texts_root) else set()
    return work_lang, present


def row_languages(row, work_lang, present):
    """Languages of the works one commentary row comments on."""
    bible_langs = {'he', 'grc', 'cop', 'en', 'la'} & present
    langs = set()
    for w in row.get('works') or []:
        if str(w).startswith('bible.'):
            langs.update(bible_langs)
        langs.update(work_lang.get(w, ()))
    return langs


def _commentaries():
    rows = S.commentary_sources() or []
    work_lang, present = work_language_map()
    groups = {}
    for r in rows:
        langs = row_languages(r, work_lang, present) or {'other'}
        for lg in langs:
            groups.setdefault(lg, []).append(r)
    out = []
    for lg in sorted(groups, key=lambda k: (k == 'other', LANGUAGE_NAMES.get(k, k))):
        out.append({'language': lg, 'language_name': LANGUAGE_NAMES.get(lg, 'Other' if lg == 'other' else lg),
                    'commentaries': groups[lg]})
    return out


def _mtime(path):
    try:
        return int(os.path.getmtime(path))
    except OSError:
        return None


def _journal_table(path):
    """Per journal: year span, articles, articles with a citation, citations.
    Counts articles whose fetch succeeded (status 'ok')."""
    con = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    try:
        arts = con.execute(
            "SELECT journal, MIN(year), MAX(year), COUNT(*) FROM articles WHERE status = 'ok' GROUP BY journal").fetchall()
        cited = dict(con.execute(
            "SELECT a.journal, COUNT(DISTINCT a.id) FROM articles a JOIN citations c ON c.article_id = a.id "
            "WHERE a.status = 'ok' GROUP BY a.journal").fetchall())
        ncit = dict(con.execute(
            "SELECT a.journal, COUNT(*) FROM articles a JOIN citations c ON c.article_id = a.id "
            "WHERE a.status = 'ok' GROUP BY a.journal").fetchall())
    finally:
        con.close()
    rows = [{'journal': j, 'year_from': y0, 'year_to': y1, 'articles': n,
             'articles_with_citations': cited.get(j, 0), 'citations': ncit.get(j, 0)}
            for j, y0, y1, n in arts if j]
    rows.sort(key=lambda r: (r['journal'].lower().removeprefix('the '), r['year_from'] or 0))
    return rows


def _index_block(key, path):
    info = INDEX_DESCRIPTIONS[key]
    block = {'id': key, 'name': info['name'], 'description': info['description'], 'terms': info['terms'],
             'available': False, 'journals': [], 'updated': _mtime(path) if path else None}
    if path and os.path.exists(path):
        try:
            block['journals'] = _journal_table(path)
            block['available'] = True
        except sqlite3.Error:
            block['available'] = False
    block['totals'] = {k: sum(j[k] for j in block['journals'])
                       for k in ('articles', 'articles_with_citations', 'citations')}
    return block


def _commentaries_updated():
    d = S.COMMENTARY_DIR
    try:
        return int(max([os.path.getmtime(d)] + [e.stat().st_mtime for e in os.scandir(d) if e.name.endswith('.json')]))
    except OSError:
        return None


def build():
    indexes = [_index_block('ejc', S.CITATION_INDEX)]
    extra = S._extra_index_path()
    if extra:
        indexes.append(_index_block('muse', extra))
    return {
        'commentaries': _commentaries(),
        'journals': indexes,
        'online': {'services': [{'name': k, 'text': v} for k, v in SERVICES.items()], 'note': SERVICES_NOTE},
        'methods': METHODS,
        'updated': {'commentaries': _commentaries_updated(),
                    'indexes': {b['id']: b['updated'] for b in indexes}},
    }


_cache = {'at': 0.0, 'value': None}
_lock = threading.Lock()


def about():
    with _lock:
        if _cache['value'] is not None and time.time() - _cache['at'] < CACHE_SECONDS:
            return _cache['value']
    value = build()
    with _lock:
        _cache.update(at=time.time(), value=value)
    return value


def clear_cache():
    with _lock:
        _cache.update(at=0.0, value=None)
