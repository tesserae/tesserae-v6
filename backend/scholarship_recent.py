"""Recent articles for a question about one work, from the live services.

The Reader's Scholarship tab asks OpenAlex, Crossref, CORE, Google Books and
Semantic Scholar what cites a passage (backend/scholarship.py). This module
asks them the same thing for a QUESTION about a work ("Dido falls in love with
Aeneas" on the Aeneid), one service at a time so the page can paint each as it
answers, and filters what comes back.

Two modes. With a work, an item is kept when its title or abstract names the
author or the work and shares a content word with the question, and it is
dropped when its title is a schoolbook's or exam board's. Without a work (Theme
Search's list, where the question is the only thing known) the services are asked
the question alone and an item is kept when its title or abstract holds at least
two distinct content words of the question (every one when the question has
fewer than three) and at least one of them is in the title. Either way, naming
or matching that happens only in a CORE full text or beyond the first 1,500
characters of an abstract does not count. With a work the order is: the title
names the work, question words matched, newest. Without one: title words
matched, question words matched, newest.

Every service call goes through scholarship._cached, so the paragraph route
finds on disk what the page already fetched.
"""
import logging
import re

import requests

from backend import scholarship as sch

logger = logging.getLogger(__name__)

SERVICES = ('openalex', 'crossref', 'core', 'books', 's2')
LABELS = {'openalex': 'OpenAlex', 'crossref': 'Crossref', 'core': 'CORE', 'books': 'Google Books',
          's2': 'Semantic Scholar'}
MAX_PER_SERVICE = 8
EXCERPT_CHARS = 300

_STOP = {
    'about', 'after', 'again', 'also', 'among', 'been', 'before', 'being', 'between', 'both', 'could',
    'does', 'doing', 'during', 'each', 'from', 'have', 'having', 'here', 'into', 'just', 'like', 'made',
    'make', 'many', 'more', 'most', 'much', 'must', 'only', 'other', 'over', 'same', 'should', 'some',
    'such', 'than', 'that', 'their', 'them', 'then', 'there', 'these', 'they', 'this', 'those', 'through',
    'under', 'upon', 'very', 'want', 'were', 'what', 'when', 'where', 'which', 'while', 'whom', 'whose',
    'will', 'with', 'within', 'without', 'would', 'your', 'says', 'said',
}


def content_words(question):
    """The question's content words: four letters or more, not in a short stoplist."""
    out = []
    for w in re.findall(r"[^\W\d_]+", (question or '').lower()):
        if len(w) >= 4 and w not in _STOP and w not in out:
            out.append(w)
    return out


def _stem(w):
    return w[:5]


def _tokens(text):
    return re.findall(r"[^\W\d_]+", (text or '').lower())


def _work_names(a):
    """Author (with its variants) and title (five letters or more, and each
    parenthetical part of it) as lowercase needles."""
    names = []
    author = (a.get('author') or '').strip()
    if author:
        names.append(author)
        names.extend(sch.AUTHOR_VARIANTS.get(author.lower(), []))
    title = (a.get('title') or '').strip()
    for part in [title] + [p.strip() for p in re.split(r'[()]', title)]:
        if len(part) >= 5:
            names.append(part)
    return list(dict.fromkeys(n.lower() for n in names if n))


def names_work(text, a):
    """True when the text names the author (or a variant) or the title, as whole words."""
    low = (text or '').lower()
    return any(re.search(r'(?<!\w)' + re.escape(n) + r'(?!\w)', low) for n in _work_names(a))


def work_names_dict(work):
    from backend import passage_index
    from backend import work_names
    base = work_names.base_work(work)
    info = passage_index._naming(base) or {}
    author = str(info.get('author') or '').strip()
    title = str(info.get('title') or '').strip()
    return {'work': base, 'author': author, 'title': title, 'abbrev': title, 'locus': '', 'lo': '', 'hi': ''}


def _question_words_for_match(question, a):
    """Content words used to test an item. Words that are the author's or the
    title's own (a question that names the work) would make the test trivial,
    so they are left out unless nothing else remains."""
    words = content_words(question)
    own = {_stem(t) for n in _work_names(a) for t in _tokens(n)}
    rest = [w for w in words if _stem(w) not in own]
    return rest or words


def _matched(text, words):
    toks = _tokens(text)
    hit = set()
    for w in words:
        s = _stem(w)
        if any(t.startswith(s) for t in toks):
            hit.add(w)
    return hit


ABSTRACT_CHARS = 1500

# A title that is a school or exam-board book, not scholarship on the work.
_SCHOOL_TITLE = (
    r'\bA[- ]Level\b', r'\bAS[- ]Level\b', r'\bGCSE\b', r'\bOCR\b', r'\bComponent \d',
    r'\bRevision Guide\b', r"\bStudent'?s? Book\b", r'\bWorkbook\b', r'\bExam\b',
)
_SCHOOL_RE = re.compile('|'.join(_SCHOOL_TITLE), re.I)


def _head_text(it):
    """Title and abstract (the first 1,500 characters): the text an item must
    name the work or match the question in. The snippet (a CORE full-text
    sentence, a Google Books excerpt) is left out."""
    return (it.get('title') or '') + ' ' + str(it.get('abstract') or '')[:ABSTRACT_CHARS]


def _excerpt(it, words):
    text = it.get('snippet') or it.get('abstract') or ''
    ex = sch._sentence_with(text, [_stem(w) for w in words])
    if ex:
        return sch._cap_words(ex, EXCERPT_CHARS)
    return sch._cap_words(text, EXCERPT_CHARS) if text else ''


def _filter(items, a, words):
    """Items to keep (matched on a five-letter stem). With a work (a), the
    title or abstract must name the author or the work and share a question
    word. With a None, the title or abstract must hold two question words (all
    of them when there are fewer than three) and the title at least one. A
    schoolbook title, or no title, is dropped. Deduped by DOI, then by the
    first 80 characters of the title."""
    kept, seen = [], set()
    need = 2 if len(words) >= 3 else len(words)
    for it in items or []:
        title = (it.get('title') or '').strip()
        if not title or _SCHOOL_RE.search(title):
            continue
        head = _head_text(it)
        hit = _matched(head, words)
        title_hits = 0
        title_names = False
        if a is None:
            title_hits = len(_matched(title, words))
            if len(hit) < need or not title_hits:
                continue
        else:
            title_names = names_work(title, a)
            if not (title_names or names_work(head, a)) or not hit:
                continue
        doi = (it.get('doi') or '').replace('https://doi.org/', '').lower()
        keys = [k for k in (doi, title.lower()[:80]) if k]
        if any(k in seen for k in keys):
            continue
        seen.update(keys)
        # Naming in the full text or the excerpt is not a pass, only a tie-breaker.
        full = bool(a is not None and (it.get('names_work') or names_work(it.get('snippet') or '', a)))
        kept.append({
            'title': title,
            'authors': [x for x in (it.get('authors') or []) if x][:4],
            'year': it.get('year') or None,
            'venue': it.get('venue') or None,
            'doi': doi or None,
            'url': it.get('url') or None,
            'oa_url': it.get('oa_url') or None,
            'excerpt': _excerpt(it, words),
            'source': it.get('source') or '',
            'has_text': bool(it.get('has_text')),
            'score': len(hit),
            'title_names_work': title_names,
            'title_hits': title_hits,
            'full_names_work': full,
        })
    return kept


def order(items):
    """The title names the work (or, without a work, more question words in the
    title) first, then most question words matched, then naming in the full
    text, then newest."""
    def year(it):
        try:
            return int(it.get('year') or 0)
        except (TypeError, ValueError):
            return 0
    return sorted(items, key=lambda it: (
        -int(bool(it.get('title_names_work'))), -int(it.get('title_hits') or 0), -it.get('score', 0),
        -int(bool(it.get('full_names_work'))), -year(it)))


def merge(lists):
    """Items from several services as one list: deduped by DOI, then by the
    first 80 characters of the title, a duplicate lending its free copy or
    excerpt to the item kept, ordered by score then year."""
    by_key, out = {}, []
    for items in lists:
        for it in items or []:
            keys = [k for k in ((it.get('doi') or '').lower(), (it.get('title') or '').lower()[:80]) if k]
            hit = next((by_key[k] for k in keys if k in by_key), None)
            if hit is not None:
                for f in ('oa_url', 'excerpt', 'url', 'venue', 'year', 'doi'):
                    if not hit.get(f) and it.get(f):
                        hit[f] = it[f]
                hit['has_text'] = bool(hit.get('has_text') or it.get('has_text'))
                for k in keys:
                    by_key.setdefault(k, hit)
                continue
            it = dict(it)
            out.append(it)
            for k in keys:
                by_key[k] = it
    return order(out)


# ------------------------------------------------------------- the services

def _books_items(q):
    key = sch.GOOGLE_BOOKS_KEY

    def run():
        try:
            d = sch._get_retry('https://www.googleapis.com/books/v1/volumes',
                         {'q': q, 'maxResults': 10, 'key': key, 'printType': 'books'})
        except requests.RequestException as e:
            # The exception text carries the request URL with the key: raise a bare error.
            raise RuntimeError('books lookup failed: %s %s' % (
                type(e).__name__, getattr(getattr(e, 'response', None), 'status_code', ''))) from None
        out = []
        for it in d.get('items', []) or []:
            v = it.get('volumeInfo') or {}
            si = it.get('searchInfo') or {}
            out.append({'title': v.get('title'), 'authors': v.get('authors') or [],
                        'year': (v.get('publishedDate') or '')[:4], 'venue': v.get('publisher'),
                        'snippet': sch._clean_snippet(si.get('textSnippet')),
                        'abstract': sch._clean_snippet(v.get('description'))[:1500],
                        'url': v.get('infoLink') or v.get('previewLink'), 'source': 'google_books'})
        return out
    return sch._cached('recentbooks|' + q, run)


def _core_items(query, a, words):
    needles = [_stem(w) for w in words]

    def run():
        r = sch._core_get({'q': query, 'limit': 10})
        r.raise_for_status()
        out = []
        for w in (r.json().get('results') or []):
            full = (w.get('fullText') or '')[:300000]
            text = full or (w.get('abstract') or '')
            best = None
            for s in re.split(r'(?<=[.!?])\s+', text):
                low = s.lower()
                if any(n in low for n in needles):
                    if a is not None and names_work(s, a):
                        best = s
                        break
                    if best is None:
                        best = s
            out.append({
                'title': w.get('title') or '',
                'authors': [x.get('name') for x in (w.get('authors') or []) if isinstance(x, dict) and x.get('name')][:6],
                'year': w.get('yearPublished'), 'venue': w.get('publisher'), 'doi': w.get('doi'),
                'url': f"https://core.ac.uk/works/{w.get('id')}" if w.get('id') else None,
                'oa_url': w.get('downloadUrl'),
                'snippet': sch._cap_words(best or '', 500), 'abstract': (w.get('abstract') or '')[:2000],
                'has_text': bool(full), 'names_work': a is not None and bool(full) and names_work(full, a),
                'source': 'core'})
        return out
    return sch._cached('recentcore|' + query, run)


def _core_query_forms(words, a):
    """The content words joined by AND (a question is not a phrase), then the
    first three quoted, each with the author/title in an OR group."""
    anded = ' AND '.join(words[:6])
    quoted = ' AND '.join(f'"{w}"' for w in words[:3])
    if a is None:
        return [anded, quoted]
    must_terms = [a['author'], a['title']] + sch.AUTHOR_VARIANTS.get(a['author'].lower(), [])
    must = ' OR '.join(f'"{t}"' if ' ' in t else t for t in dict.fromkeys(t for t in must_terms if t))
    return [f'{anded} AND ({must})', f'{quoted} AND ({must})']


def recent(question, work, service):
    """The filtered, scored items one live service gives for the question.
    Returns {'service', 'available', 'results', 'reason'}. Raises when the
    service itself fails (recent_safe wraps that)."""
    if service not in SERVICES:
        return {'service': service, 'available': False, 'results': [], 'reason': 'unknown service'}
    a = work_names_dict(work) if work else None
    words = _question_words_for_match(question, a) if a else content_words(question)
    if not words or (a is not None and not (a['author'] or a['title'])):
        return {'service': service, 'available': True, 'results': [], 'reason': ''}
    q = ' '.join(x for x in ((a['author'], a['title']) if a else ()) + (question,) if x)
    if service == 'openalex':
        raw = sch._openalex(q)
    elif service == 'crossref':
        raw = sch._crossref(q)
    elif service == 'books':
        if not sch.GOOGLE_BOOKS_KEY:
            return {'service': service, 'available': False, 'results': [], 'reason': 'off'}
        raw = _books_items(' '.join(x for x in ([a['author'], a['title']] if a else []) + content_words(question) if x))
    elif service == 's2':
        if not sch.S2_API_KEY:
            return {'service': service, 'available': False, 'results': [], 'reason': 'off'}
        raw = sch._s2_snippets(q)
    else:
        raw = None
        forms = _core_query_forms(content_words(question) or words, a)
        for i, form in enumerate(forms):
            try:
                raw = _core_items(form, a, words)
                break
            except requests.RequestException as e:
                if i == len(forms) - 1:
                    raise
                logger.info('[RECENT] CORE rejected the AND form (%s %s), trying quoted words',
                            type(e).__name__, getattr(getattr(e, 'response', None), 'status_code', ''))
    items = order(_filter(raw, a, words))[:MAX_PER_SERVICE]
    for it in items[:3]:
        if it.get('doi') and not it.get('oa_url'):
            try:
                it['oa_url'] = (sch._unpaywall(it['doi']) or {}).get('oa_url') or None
            except Exception as e:  # noqa: BLE001  a free-copy lookup must not sink the item
                logger.info('[RECENT] unpaywall failed: %s', type(e).__name__)
    return {'service': service, 'available': True, 'results': items, 'reason': ''}


def recent_safe(question, work, service):
    """recent(), but a service that raises answers available False with a plain reason."""
    try:
        return recent(question, work, service)
    except Exception as e:  # noqa: BLE001  one service's failure must not take the answer down
        # Type and status only: some exception texts carry a URL with a key.
        logger.info('[RECENT] %s failed: %s %s', service, type(e).__name__,
                    getattr(getattr(e, 'response', None), 'status_code', ''))
        return {'service': service, 'available': False, 'results': [], 'reason': 'the service did not answer'}


def state(result):
    """'ok' (items), 'none', 'failed' or 'off' for one service's answer."""
    if result.get('results'):
        return 'ok'
    if result.get('available'):
        return 'none'
    return 'off' if result.get('reason') == 'off' else 'failed'
