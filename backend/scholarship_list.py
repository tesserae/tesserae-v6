"""The full list of articles citing a scope of a work (GET /api/scholarship/list).

Reads the three citation indexes (EJC, Project MUSE, JSTOR) once per scope,
merges one article held by several indexes into one item with the same keys
the Scholarship tab uses (scholarship.article_keys), and answers filters,
search, sort and paging from memory. The Reader tab's own reader,
scholarship._index_articles, cuts each index at 5,000 rows and keeps one
citation per article, which is right for a tab and wrong for a list, so this
module reads the rows itself and reuses that module's locus helpers
(_coords, _locus_overlaps, _citation_span, _locus_depth_note, _cap_words).

JSTOR's condition (2026-11-09) is citation and link only: no sentence of its
text is ever returned. The sentences are read so that a search term can match
them, and are dropped from every answer.
"""
import re
import sqlite3
import threading
import time
import unicodedata

from backend import scholarship as S

SCOPES = ('passage', 'book', 'work')
SOURCES = ('ejc', 'muse', 'jstor')
KINDS = ('article', 'review', 'other')
SORTS = ('newest', 'oldest', 'author', 'journal', 'most')
MAX_PER_PAGE = 200
MAX_CITES = 60          # per article, in locus order; `cites_total` says how many there are
MAX_SENTENCES = 20      # per article
SCAN_TTL = 600          # seconds
SCAN_MAX = 4            # scans held in the process
_TAG = {'ejc': 'citation_index', 'muse': 'muse', 'jstor': 'jstor'}

_scans = {}
_scans_lock = threading.Lock()


# The combining marks Latin, Greek, Hebrew and Arabic text carries (a regex is several times faster than
# testing every character with unicodedata.combining).
_MARKS = re.compile('[\u0300-\u036f\u0483-\u0489\u0591-\u05c7\u064b-\u065f\u0670\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]')


class BadRequest(ValueError):
    pass


def norm(text):
    """Lowercase, accents and combining marks removed (the form the indexes' titles are compared in)."""
    t = text or ''
    if t.isascii():
        return t.lower()
    return _MARKS.sub('', unicodedata.normalize('NFKD', t)).lower()


def _surname(authors):
    if not authors:
        return ''
    first = authors[0].strip()
    if ',' in first:
        return norm(first.split(',')[0]).strip()
    parts = first.split()
    return norm(parts[-1]) if parts else ''


def _locus_text(start, end):
    start = (start or '').strip()
    end = (end or '').strip()
    if not end or end == start:
        return start
    sp, ep = start.split('.'), end.split('.')
    if len(sp) == len(ep) and sp[:-1] == ep[:-1]:
        return f'{start}-{ep[-1]}'
    return f'{start}-{end}'


# ----------------------------------------------------------------- reading

def _read_index(path, source, work, shape, lo, hi, book):
    """{article_id: record} for one index, every citation of `work` kept with
    flags for the passage and book scopes; None when the file is unreadable."""
    deeper_last_level, whole_work = shape
    try:
        con = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
        have_kind = any(r[1] == 'kind' for r in con.execute('PRAGMA table_info(articles)'))
        kind_col = 'a.kind' if have_kind else "'article'"
        rows = con.execute(
            'SELECT c.article_id, c.page, c.locus_start, c.locus_end, c.open_ended, c.surface, c.sentence, '  # nosec B608
            'a.title, a.authors, a.journal, a.year, a.volume, a.issue, a.url_ia, a.url_jstor, a.doi, a.first_page, '
            f'{kind_col} AS kind FROM citations c JOIN articles a ON a.id = c.article_id WHERE c.work_id = ?',
            (work,)).fetchall()
        con.close()
    except sqlite3.Error as e:
        S.logger.warning('citation index unreadable (%s): %s', source, e)
        return None
    line_level = len(lo or ()) > 1
    book_scope_ok = not (whole_work or deeper_last_level)
    span_memo = {}
    recs = {}
    for (article_id, page, locus_start, locus_end, open_ended, surface, sentence, title, authors, journal, year,
         volume, issue, url_ia, url_jstor, doi_raw, first_page, kind_raw) in rows:
        surface = surface or ''
        if not re.search(r'[A-Za-z]', surface):
            continue
        mk = (locus_start, locus_end, open_ended)
        got = span_memo.get(mk)
        if got is None:
            cs, ce, span_note = S._citation_span(work, locus_start, locus_end, deeper_last_level, whole_work)
            skip = False
            if not whole_work and ce and cs and len(cs) > 1 and len(ce) > 1 and ce[0] != cs[0]:
                skip = True
            if open_ended and not whole_work:
                ce = cs[:-1] + (cs[-1] + 30,) if len(cs) > 1 else (10 ** 6,)
            note = S._locus_depth_note(work, cs)
            if span_note:
                note = f'{note}; {span_note}' if note else f' ({span_note})'
            in_book = in_passage = True
            if not whole_work:
                in_passage = bool(lo) and S._locus_overlaps(cs, ce, lo, hi)
                in_book = book is not None and book_scope_ok and S._locus_overlaps(cs, ce, (book,), (book,))
            got = span_memo[mk] = (cs, skip, note, in_book, in_passage,
                                   _locus_text(locus_start, locus_end))
        cs, skip, note, in_book, in_passage, locus = got
        if skip:
            continue
        # A bare book named when lines are selected is a list of books, not that line.
        if in_passage and not whole_work and line_level and (len(cs) < 2 or not re.search(r'\d', surface)):
            in_passage = False
        if not whole_work and not book_scope_ok:
            in_book = True
        rec = recs.get(article_id)
        if rec is None:
            doi = doi_raw or ''
            if source == 'muse':
                link = {'url': f'https://doi.org/{doi}' if doi else None, 'url_jstor': None, 'url_ia': None}
            elif source == 'jstor':
                link = {'url': None, 'url_jstor': None, 'url_ia': None, '_doi': doi, '_base': url_jstor}
            else:
                link = {'url': url_jstor or url_ia, 'url_jstor': url_jstor, 'url_ia': url_ia}
            kind = kind_raw if kind_raw in KINDS else 'article'
            rec = recs[article_id] = {
                'title': title, 'authors': [x for x in (authors or '').split('; ') if x],
                'venue': journal, 'year': year, 'volume': volume, 'issue': issue,
                'doi': doi_raw, 'kind': kind, 'source': source, 'first_page': first_page, **link, 'cites': []}
        # (locus, note, in_book, in_passage, page, surface, sentence, locus start for sorting)
        rec['cites'].append((locus, note, in_book, in_passage, page, surface, sentence, cs))
    # JSTOR: a stable link opens on the citing page (?seq=), taken from the first citation kept.
    if source == 'jstor':
        for rec in recs.values():
            doi, base = rec.pop('_doi'), rec.pop('_base')
            url = base or (f'https://doi.org/{doi}' if doi else None)
            if url and '/stable/' in url and rec['cites'] and rec['cites'][0][4] is not None and '?' not in url:
                url = f'{url}?seq={int(rec["cites"][0][4]) + 1}'
            rec['url'] = rec['url_jstor'] = url
    return recs


def _scan_uncached(work, lo_ref, hi_ref):
    extra, jstor = S._extra_index_path(), S._jstor_index_path()
    have_ejc = bool(S.os.path.exists(S.CITATION_INDEX))
    if not (have_ejc or extra or jstor):
        return None
    lo, hi = S._coords(lo_ref) if lo_ref else (), S._coords(hi_ref) if hi_ref else ()
    if lo and not hi:
        hi = lo
    book = lo[0] if lo else None
    _depth, deeper_last_level, whole_work = S._override_depth_shape(work)
    shape = (deeper_last_level, whole_work)
    per_source = {}
    for source, path in (('ejc', S.CITATION_INDEX if have_ejc else None), ('muse', extra), ('jstor', jstor)):
        if path:
            got = _read_index(path, source, work, shape, lo, hi, book)
            if got is not None:
                per_source[source] = got
    if not per_source:
        return {'available': False}
    # Merge: EJC, then MUSE, then JSTOR; a MUSE row has a DOI only and its JSTOR twin a stable id,
    # so every key of the article is looked up (a title-and-year key counts from 12 letters on).
    merged, alias = [], {}
    for source in SOURCES:
        for rec in (per_source.get(source) or {}).values():
            keys = S.article_keys(rec)
            usable = [k for k in keys if k[0] != 'title' or len(k[1]) >= 12]
            found = next((alias[k] for k in usable if k in alias), None)
            if found is None:
                found = {'key': keys[0] if keys else ('title', '', rec.get('year') or ''), 'recs': []}
                merged.append(found)
            for k in usable or keys[:1]:
                alias.setdefault(k, found)
            found['recs'].append((source, rec))
    articles = []
    for m in merged:
        arts = _finish(m, work)
        if arts:
            articles.append(arts)
    return {'available': True, 'articles': articles, 'note': _note(have_ejc, extra, jstor)}


def _note(have_ejc, extra, jstor):
    note = ('From the full text of journals before 1923 (JSTOR Early Journal Content, on the Internet Archive), '
            'indexed by passage with the citation extractor.')
    if extra:
        note += " Project MUSE journals from 1996 on are read under the library's license; one sentence is shown per citation."
    if jstor:
        note += " JSTOR journals are read under JSTOR's text-analysis terms; each citing article is listed with a link and no excerpt."
    return note


def _finish(m, work):
    """One merged article: per-scope citations and the fields of its kept source."""
    recs = m['recs']
    first_source, first = recs[0]          # EJC before MUSE before JSTOR
    kind = next((r['kind'] for s, r in recs if r['kind'] != 'article'), 'article')
    citations = []                          # one per distinct locus, with scope flags
    seen = {}
    sentences = []                          # (in_book, in_passage, normalized, shown text or None)
    pages = []
    for source, rec in recs:
        for locus, note, in_book, in_passage, page, surface, sentence, cs in rec['cites']:
            c = seen.get(locus)
            if c is None:
                c = seen[locus] = [locus, note, False, False, cs]
                citations.append(c)
            c[2] = c[2] or in_book
            c[3] = c[3] or in_passage
            if source != 'jstor':
                if page and page not in pages:
                    pages.append(page)
            elif rec.get('first_page') is not None and page is not None:
                # JSTOR stores the page's index in the scan; the printed page is known
                # only when the index carries the article's first printed page.
                printed = int(rec['first_page']) + int(page)
                if printed not in pages:
                    pages.append(printed)
            if sentence:
                shown = None
                if source != 'jstor':
                    shown = S._cap_words(re.sub(r'\s+', ' ', sentence).strip(),
                                         include=re.sub(r'\s+', ' ', surface).strip())
                sentences.append([in_book, in_passage, sentence, shown, None])
    return {
        'key': '|'.join(str(x) for x in m['key']),
        'title': first['title'], 'authors': first['authors'], 'year': first['year'], 'venue': first['venue'],
        'volume': first['volume'], 'issue': first['issue'], 'pages': pages, 'kind': kind,
        'source': first_source, 'sources': [s for s, _ in recs],
        'doi': next((r['doi'] for _, r in recs if r['doi']), None),
        'url': next((r['url'] for _, r in recs if r['url']), None),
        'url_jstor': next((r['url_jstor'] for _, r in recs if r['url_jstor']), None),
        'url_ia': next((r['url_ia'] for _, r in recs if r['url_ia']), None),
        '_cites': citations, '_sentences': sentences,
        '_n': norm(' '.join([first['title'] or '', '; '.join(first['authors']), first['venue'] or ''])),
        '_surname': _surname(first['authors']),
    }


def scan(work, lo_ref, hi_ref):
    """The merged articles of `work` with their citations, cached ten minutes by (work, lo, hi)."""
    key = (work, lo_ref or '', hi_ref or '')
    now = time.time()
    with _scans_lock:
        hit = _scans.get(key)
        if hit and now - hit[0] < SCAN_TTL:
            return hit[1]
    got = _scan_uncached(work, lo_ref, hi_ref)
    with _scans_lock:
        _scans[key] = (now, got)
        for k in [k for k, v in _scans.items() if now - v[0] >= SCAN_TTL]:
            _scans.pop(k, None)
        while len(_scans) > SCAN_MAX:
            _scans.pop(min(_scans, key=lambda k: _scans[k][0]), None)
    return got


# --------------------------------------------------------------- answering

def _in_scope(article, scope):
    idx = {'work': None, 'book': 2, 'passage': 3}[scope]
    if idx is None:
        return True
    return any(c[idx] for c in article['_cites'])


def _scoped_cites(article, scope):
    idx = {'work': None, 'book': 2, 'passage': 3}[scope]
    return [c for c in article['_cites'] if idx is None or c[idx]]


def _matches(article, q, scope):
    if q in article['_n']:
        return True
    idx = {'work': None, 'book': 0, 'passage': 1}[scope]
    for s in article['_sentences']:
        if idx is None or s[idx]:
            if s[4] is None:
                s[4] = norm(s[2])
            if q in s[4]:
                return True
    return False


def _decade(y):
    return str(y // 10 * 10)


def answer(p, scope_info, counts_note=None):
    """The list response for validated parameters `p` (see parse_params)."""
    data = scan(p['work'], p['lo'], p['hi'])
    if not data or not data.get('available'):
        return {'available': False, 'results': [],
                'reason': 'No offline citation index on this server yet.' if data is None
                else 'The citation index could not be read.'}
    arts = data['articles']
    scope = p['scope']
    counts = {s: sum(1 for a in arts if _in_scope(a, s)) for s in SCOPES if s != 'passage' or p['lo']}
    if not p['lo']:
        counts['passage'] = counts['book'] = None
    pool = [a for a in arts if _in_scope(a, scope)]
    q = norm(p['q']) if p['q'] else ''
    sel = []
    for a in pool:
        if p['sources'] and not (set(a['sources']) & p['sources']):
            continue
        if p['year_from'] is not None and (a['year'] is None or a['year'] < p['year_from']):
            continue
        if p['year_to'] is not None and (a['year'] is None or a['year'] > p['year_to']):
            continue
        if p['journal'] and a['venue'] != p['journal']:
            continue
        if p['kinds'] and a['kind'] not in p['kinds']:
            continue
        if q and not _matches(a, q, scope):
            continue
        sel.append(a)
    facets = {'source': {}, 'decade': {}, 'kind': {}}
    jc = {}
    for a in sel:
        for s in a['sources']:
            facets['source'][s] = facets['source'].get(s, 0) + 1
        if a['year']:
            d = _decade(a['year'])
            facets['decade'][d] = facets['decade'].get(d, 0) + 1
        facets['kind'][a['kind']] = facets['kind'].get(a['kind'], 0) + 1
        if a['venue']:
            jc[a['venue']] = jc.get(a['venue'], 0) + 1
    facets['decade'] = dict(sorted(facets['decade'].items()))
    facets['journal'] = [[j, n] for j, n in sorted(jc.items(), key=lambda kv: (-kv[1], kv[0]))[:15]]
    sel = _sort(sel, p['sort'], scope)
    start = (p['page'] - 1) * p['per_page']
    results = [_shape(a, scope) for a in sel[start:start + p['per_page']]]
    return {'available': True, 'scope': scope_info, 'counts': counts, 'total': len(sel),
            'page': p['page'], 'per_page': p['per_page'], 'results': results, 'facets': facets,
            'note': data['note']}


_KIND_ORDER = {'article': 0, 'review': 1, 'other': 2}


def _sort(sel, how, scope):
    t = lambda a: norm(a['title'])  # noqa: E731
    y = lambda a: a['year'] or 0    # noqa: E731
    if how == 'oldest':
        return sorted(sel, key=lambda a: (a['year'] is None, y(a), t(a)))
    if how == 'author':
        return sorted(sel, key=lambda a: (a['_surname'] == '', a['_surname'], y(a), t(a)))
    if how == 'journal':
        return sorted(sel, key=lambda a: (not a['venue'], norm(a['venue']), -y(a), t(a)))
    if how == 'most':
        return sorted(sel, key=lambda a: (-len(_scoped_cites(a, scope)), -y(a), t(a)))
    return sorted(sel, key=lambda a: (_KIND_ORDER.get(a['kind'], 3), -y(a), t(a)))


def _shape(a, scope):
    cites = _scoped_cites(a, scope)
    cites = sorted(cites, key=lambda c: (c[4], c[0]))
    idx = {'work': None, 'book': 0, 'passage': 1}[scope]
    sentences, seen = [], set()
    for s in a['_sentences']:
        if s[3] and (idx is None or s[idx]) and s[3] not in seen:
            seen.add(s[3])
            sentences.append(s[3])
    return {
        'key': a['key'], 'title': a['title'], 'authors': a['authors'], 'year': a['year'], 'venue': a['venue'],
        'volume': a['volume'], 'issue': a['issue'], 'pages': a['pages'], 'kind': a['kind'],
        'source': a['source'], 'sources': a['sources'],
        'cites': [{'locus': c[0], 'note': (c[1] or '').strip(' ()')} for c in cites[:MAX_CITES]],
        'cites_total': len(cites),
        'sentences': sentences[:MAX_SENTENCES],
        'url': a['url'], 'url_jstor': a['url_jstor'], 'url_ia': a['url_ia'], 'doi': a['doi']}


# ------------------------------------------------------------- parameters

def _int(args, name, lo=None, hi=None):
    raw = (args.get(name) or '').strip()
    if not raw:
        return None
    try:
        n = int(raw)
    except ValueError:
        raise BadRequest(f'{name} must be a whole number')
    if lo is not None and n < lo:
        raise BadRequest(f'{name} must be at least {lo}')
    return n if hi is None else min(n, hi)


def _choices(args, name, allowed):
    raw = (args.get(name) or '').strip()
    if not raw:
        return None
    got = {x.strip().lower() for x in raw.split(',') if x.strip()}
    bad = sorted(got - set(allowed))
    if bad:
        raise BadRequest(f'{name} takes {", ".join(allowed)}, not {", ".join(bad)}')
    return got


def parse_params(args):
    work = (args.get('work') or '').strip()
    if not work:
        raise BadRequest('work is required')
    lo = (args.get('lo') or '').strip() or None
    hi = (args.get('hi') or '').strip() or None
    if hi and not lo:
        raise BadRequest('hi needs lo')
    scope = (args.get('scope') or '').strip().lower() or ('passage' if lo else 'work')
    if scope not in SCOPES:
        raise BadRequest(f'scope takes {", ".join(SCOPES)}')
    if scope in ('passage', 'book') and not lo:
        raise BadRequest(f'scope {scope} needs lo')
    if lo and not S._coords(lo):
        raise BadRequest('lo is not a locus')
    if hi and not S._coords(hi):
        raise BadRequest('hi is not a locus')
    sort = (args.get('sort') or '').strip().lower() or 'newest'
    if sort not in SORTS:
        raise BadRequest(f'sort takes {", ".join(SORTS)}')
    yf, yt = _int(args, 'year_from'), _int(args, 'year_to')
    if yf is not None and yt is not None and yf > yt:
        raise BadRequest('year_from is after year_to')
    page = _int(args, 'page', lo=1) or 1
    per_page = _int(args, 'per_page', lo=1, hi=MAX_PER_PAGE) or 50
    return {'work': work, 'lo': lo, 'hi': hi or lo, 'scope': scope,
            'q': (args.get('q') or '').strip(), 'sources': _choices(args, 'source', SOURCES),
            'year_from': yf, 'year_to': yt, 'journal': (args.get('journal') or '').strip() or None,
            'kinds': _choices(args, 'kind', KINDS), 'sort': sort, 'page': page, 'per_page': per_page}


def scope_label(p):
    """The scope as the response names it, with the tab's own abbreviation of the work."""
    names = S.passage_names(p['work'], p['lo'], p['hi']) if p['lo'] else S.passage_names(p['work'], '')
    abbrev, title = names.get('abbrev') or '', names.get('title') or p['work']
    if p['scope'] == 'work':
        label = title
    elif p['scope'] == 'book':
        label = f'{abbrev} {S._coords(p["lo"])[0]}'.strip()
    else:
        label = f'{abbrev} {names.get("locus") or p["lo"]}'.strip()
    return {'work': p['work'], 'lo': p['lo'], 'hi': p['hi'], 'scope': p['scope'], 'label': label}
