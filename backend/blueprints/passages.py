import re
"""
Tesserae V6 - Scene Blueprint

Passage-level content retrieval for the Reader: "Similar Passages" (what else in
the corpus is like this stretch of text) and "Theme Search" (find passages about
a described subject), plus the connection densities the Reader draws in its
gutter. Backed by backend/passage_index.py.

Endpoints (all GET, all under the app's API prefix):
    /passages/status                 index availability and size
    /passages/theme-search           ?q=...&limit=&offset=&languages=&scale=
                                     offset pages past the normal result set --
                                     results (offset+1) to (offset+limit) of the
                                     same ranking. Default 0, unchanged response.
    /passages/similar                ?work=&ref_start=&ref_end=  (or ?window=)
    /passages/density                ?work=&scale=
    /passages/export                 ?q=...&format=json|csv|pdf&languages=
                                     &order=score|date  the same search, with
                                     the source passages, in the page's order

Every route answers 200 with an `error` field rather than raising, so a missing
or half-built index degrades the Reader's panel instead of breaking the page.
"""
from urllib.parse import urlencode
import csv
import io
import os
from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request

from backend.logging_config import get_logger
from backend import passage_index
from backend import lexical_density
from backend import reader_rerank
from backend import translations
from backend import window_texts
from backend import theme_pdf
from backend import connections_map
from backend.inverted_index import get_corpus_version

logger = get_logger('blueprints.passages')

passages_bp = Blueprint('passages', __name__)

_MAX_LIMIT = 100
# How far a Theme Search page can be paged past the normal cap. Sane rather
# than unlimited: an offset this large already means scanning results a
# scholar would have to be quite determined to reach, and unbounded would let
# a request walk the whole ranking one `_rank` call at a time.
_MAX_OFFSET = 5000
_MAX_RESTRICT_WORKS = 200   # work ids accepted in one `works=` list
READER_HEADS = 100   # works fetched for the reader's 300 rows (3 rows each)


def _int_arg(name, default, lo=1, hi=_MAX_LIMIT):
    try:
        return max(lo, min(int(request.args.get(name, default)), hi))
    except (TypeError, ValueError):
        return default


def _languages():
    raw = (request.args.get('languages') or '').strip()
    if not raw:
        return None
    langs = [x.strip() for x in raw.split(',') if x.strip()]
    return langs or None


def _scale():
    s = (request.args.get('scale') or '').strip().lower()
    return s if s in ('fine', 'coarse') else None


def _reader_wanted():
    """False only if the request opts out with ?reader=0 (or false/no/off)."""
    raw = (request.args.get('reader') or '').strip().lower()
    return raw not in ('0', 'false', 'no', 'off')


@passages_bp.route('/passages/status')
def scene_status():
    return jsonify(passage_index.status())


@passages_bp.route('/passages/theme-search')
def theme_search():
    """Free-text content query across every indexed language at once."""
    q = (request.args.get('q') or request.args.get('query') or '').strip()
    if not q:
        return jsonify({'error': 'q is required', 'results': []})
    # The module contract is that these routes answer 200 with an error field
    # rather than raising, so a half-built index degrades the Reader's panel
    # instead of breaking the page. That was documented and not implemented:
    # on deployment this raised, Apache turned it into a bare 500, and the app
    # log was unreadable, so the cause could not be seen from the response at
    # all. An error the operator cannot read is an error they cannot fix.
    limit = _int_arg('limit', 25)
    offset = _int_arg('offset', 0, lo=0, hi=_MAX_OFFSET)
    # The reader re-orders the top K of the ranking. Every page that falls
    # inside those K is cut from the SAME re-ranked list (fetch the K from
    # offset 0, re-rank, then slice), so a passage promoted into page one
    # cannot appear again on page two and a demoted one is not lost. Pages
    # past K are served in index order as before, which the re-rank does not
    # touch. Scores are deterministic, so each page re-ranks the same K the
    # same way at the cost of one reader call per page.
    # Optional restriction to an author or to chosen works (`author=lucan`,
    # `works=lucan.bellum_civile,livy.ab_urbe_condita`). Resolved here so an
    # unknown name answers 200 with a note and no results, like every other
    # miss on this route.
    author_arg = (request.args.get('author') or '').strip()
    works_arg = [w.strip() for w in (request.args.get('works') or '').split(',')
                 if w.strip()][:_MAX_RESTRICT_WORKS]
    only_works = None
    books_searched = None
    if author_arg or works_arg:
        try:
            only_works, miss_note = passage_index.resolve_restriction(
                author=author_arg, works=works_arg, languages=_languages())
            # `books=1,2` or `books=1-6` with one base work: only those numbered
            # parts. A number the index does not hold is dropped silently.
            books_arg = (request.args.get('books') or '').strip()
            if books_arg and only_works and len(works_arg) == 1:
                base = passage_index.base_work(works_arg[0])
                if base in only_works:
                    part_ids, books_searched = passage_index.book_parts(
                        base, passage_index.parse_books(books_arg))
                    only_works = set(part_ids)
                    if not only_works:
                        miss_note = 'The index holds none of the books asked for in that work.'
        except Exception as e:
            logger.exception('[PASSAGES] theme-search restriction failed')
            return jsonify({'error': f'{type(e).__name__}: {e}', 'results': []})
        if not only_works:
            return jsonify({'query': q, 'results': [], 'restricted': True,
                            'strong_matches': 0, 'note': miss_note,
                            'confidence': {'level': 'restricted'},
                            **({'books_searched': books_searched}
                               if books_searched is not None else {})})
    K = reader_rerank.DEFAULT_K   # rows the reader re-scores (300: the whole composed list)
    reader_on = bool(os.environ.get('THEME_READER_URL')) and _reader_wanted() and offset < K
    # `fetch` counts WORKS (find_by_text's limit is one head per work, three
    # rows each), so a hundred works give the reader its 300 rows; a deeper
    # page asks for more works.
    fetch = max(offset + limit, READER_HEADS) if reader_on else limit
    fetch_offset = 0 if reader_on else offset
    try:
        # Only a restricted search passes `only_works`, so the corpus-wide call
        # is exactly the call it was before the restriction existed.
        extra = {'only_works': only_works} if only_works else {}
        out = passage_index.find_by_text(
            q, limit=fetch, offset=fetch_offset,
            languages=_languages(), scale=_scale(), **extra)
    except passage_index.EmbedUnavailable as e:
        # "cannot ask" is not "found nothing". Only one of those means the
        # corpus lacks the subject, and reporting the wrong one would be a
        # false negative dressed as a finding.
        logger.warning('[PASSAGES] encoder unavailable: %s', e)
        return jsonify({'error': 'theme search is unavailable: the query encoder '
                                 'service is not running', 'unavailable': True,
                        'results': []})
    except Exception as e:
        logger.exception('[PASSAGES] theme-search failed')
        return jsonify({'error': f'{type(e).__name__}: {e}', 'results': []})
    # Stamped so a Theme Search can be cited reproducibly (2026-09-08).
    out['corpus_version'] = passage_index.index_version()
    if books_searched is not None:
        out['books_searched'] = books_searched
    out['presentation'] = (
        'Each result is a passage whose CONTENT matches the description, not its '
        'wording, so results in different languages usually share no words with '
        'the query. Lead with the work and the gist; treat a result marked '
        'strong:false as a weak neighbor rather than a finding.')
    # Reader-at-top: re-score the head of the ranking with the trained free
    # reader model (services/reader_server.py) and re-order it by that score.
    # Only runs when THEME_READER_URL names a running service and the request
    # has not opted out with ?reader=0; a disabled or unreachable reader
    # leaves the response exactly as it was, with no 'reader' field at all,
    # so a request made before this feature existed gets the same answer.
    if reader_on and out.get('results'):
        out['results'], reader_meta = reader_rerank.apply(q, out['results'])
        out['reader'] = reader_meta
        out['results'] = out['results'][offset:offset + limit]
    return jsonify(out)


@passages_bp.route('/passages/mentions')
def mentions():
    """Windows of one work whose description names a person or thing.

    ?work=<base or part id>&names=<comma list>&books=<1,2 or 1-6>&limit=&offset=
    &q=<the question>&source=<text|description>
    With q the list is ranked by closeness to the question. A name the
    descriptions never mention is looked for in the text (source=text forces
    that for every name). A word search over the describer's participants, gist, setting and themes,
    for the case where Theme Search ranks a named subject too low."""
    work = (request.args.get('work') or '').strip()
    names = [n.strip() for n in (request.args.get('names') or '').split(',') if n.strip()][:20]
    if not names:
        return jsonify({'error': 'names is required', 'results': [], 'total': 0})
    if not work:
        return jsonify({'error': 'work is required', 'results': [], 'total': 0})
    limit = _int_arg('limit', 25)
    offset = _int_arg('offset', 0, lo=0, hi=_MAX_OFFSET)
    books = passage_index.parse_books(request.args.get('books')) or None
    try:
        q = (request.args.get('q') or '').strip() or None
        source = (request.args.get('source') or '').strip().lower() or None
        out = passage_index.mentions_in_work(work, names, books=books,
                                             query=q, source=source)
    except Exception as e:
        logger.exception('[PASSAGES] mentions failed')
        return jsonify({'error': f'{type(e).__name__}: {e}', 'results': [], 'total': 0})
    hits = out['hits']
    resp = {'work': out['work'], 'names': names, 'total': len(hits),
            'books_searched': out['books_searched'],
            'ranked_by': out.get('ranked_by', 'mentions'),
            'source': out.get('source', 'description'),
            'results': hits[offset:offset + limit]}
    if out.get('note'):
        resp['note'] = out['note']
    return jsonify(resp)


_SUMMARY_SYSTEM = (
    "You write for scholars. You are given a question about one ancient work and a list of "
    "passages from that work with a one-sentence description of each. Say in at most 120 words "
    "what the work says about the subject, drawing only on the descriptions given. Cite the "
    "passages you use by their reference in parentheses, exactly as given. Do not add anything "
    "the descriptions do not say, and if they do not answer the question, say so in one "
    "sentence. Plain words. No dashes, no semicolons, no lists, no headings.")
_SUMMARY_TIMEOUT = 40
_SUMMARY_MAX_PASSAGES = 12



def _locus(ref):
    """The numeric tail of a reference: "Tac. Ann. 1.73" gives "1.73",
    "thuc. pele. 2.47.3" gives "2.47.3"."""
    m = re.search(r'(\d+(?:\.\d+)*[a-z]?)\s*$', ref or '')
    return m.group(1) if m else None


def _cite_full_refs(text, refs):
    """The references the summary cites, and the text with every short
    citation written out in full. The model was asked to cite references
    exactly as given, and for the Aeneid it did (verg. aen. 4.61), but for
    Tacitus and Thucydides it wrote the bare locus in parentheses, (1.73) or
    (1.23.3), so nothing matched and the page had no citation to link
    (2026-10-11). A bare locus is recognised only inside parentheses, alone or
    in a comma-separated list, and only when exactly one passage has it."""
    cites = []
    by_locus = {}
    for ref in refs:
        loc = _locus(ref)
        if loc:
            by_locus.setdefault(loc, []).append(ref)
    def expand(match):
        parts = [p.strip() for p in match.group(1).split(',')]
        out = []
        for part in parts:
            if part in by_locus and len(by_locus[part]) == 1 and part not in refs:
                out.append(by_locus[part][0])
            else:
                out.append(part)
        return '(' + ', '.join(out) + ')'
    text = re.sub(r'\((\d+(?:\.\d+)*[a-z]?(?:\s*,\s*\d+(?:\.\d+)*[a-z]?)*)\)', expand, text or '')
    for ref in refs:
        if ref in text and ref not in cites:
            cites.append(ref)
    return text, cites

@passages_bp.route('/passages/ask-summary', methods=['POST'])
def ask_summary():
    """A short answer to the question, drawn only from the passages' gists."""
    import time
    import concurrent.futures
    from backend.assistant import model
    from backend import original_script
    data = request.get_json(silent=True) or {}
    question = str(data.get('question') or '').strip()
    label = str(data.get('work_label') or '').strip()
    passages = [p for p in (data.get('passages') or []) if isinstance(p, dict)
                and str(p.get('ref') or '').strip() and str(p.get('gist') or '').strip()]
    passages = passages[:_SUMMARY_MAX_PASSAGES]
    if not question:
        return jsonify({'available': False, 'error': 'question is required'})
    if not passages:
        return jsonify({'available': False, 'error': 'passages are required'})
    if not model.is_available():
        return jsonify({'available': False})
    user = '\n'.join([label, question] + [f"{p['ref'].strip()}: {p['gist'].strip()}"
                                           for p in passages])
    t0 = time.time()
    # complete() has its own 180 s socket timeout; the route's 40 s is enforced
    # by waiting on a worker thread, which is then left to finish on its own.
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        fut = pool.submit(model.complete, _SUMMARY_SYSTEM, user, 400, 0.2)
        try:
            text = fut.result(timeout=_SUMMARY_TIMEOUT)
            text, script_problems = original_script.settle(
                text, [p['gist'] for p in passages],
                lambda note: pool.submit(model.complete, _SUMMARY_SYSTEM, user + '\n' + note,
                                         400, 0.2).result(timeout=_SUMMARY_TIMEOUT))
        except concurrent.futures.TimeoutError:
            logger.info('[PASSAGES] ask-summary %r timed out after %.1fs', question, time.time() - t0)
            return jsonify({'available': False, 'error': 'the model took too long'})
        except Exception as e:
            logger.info('[PASSAGES] ask-summary %r failed after %.1fs: %s',
                        question, time.time() - t0, type(e).__name__)
            return jsonify({'available': False, 'error': 'the model could not answer'})
    finally:
        pool.shutdown(wait=False)
    logger.info('[PASSAGES] ask-summary %r answered in %.1fs', question, time.time() - t0)
    if not text:
        return jsonify({'available': False, 'error': 'the model could not answer'})
    text, cites = _cite_full_refs(text, [p['ref'] for p in passages])
    return jsonify({'available': True, 'summary': text, 'cites': cites,
                    'script_problems': script_problems})


_SCHOL_SYSTEM = (
    "You write for scholars. You are given a question about one ancient work and a numbered list "
    "of notes from commentaries and articles about it. Write at most {limit} words on what these "
    "notes and articles say about the subject. Cite each claim with the bracketed number of the "
    "note it came from, for example [2]. Say nothing the notes do not say. Call the sources what the "
    "list says they are, commentary notes or journal articles, and never mention a kind of source "
    "that is not in the list. Report what each "
    "note actually discusses, even when it is only a point of text or grammar, and do not "
    "infer a reading of the subject from it. If they do not answer the question, say so in one "
    "sentence. Start straight in with what the notes say, naming the commentator or the "
    "article as the list does (for example 'How and Wells take the word to mean...'). Do not "
    "open with a clause about where the material comes from: a line under your text already "
    "says that. Do not call the notes 'sources'. Do not use the word paragraph. Plain words. "
    "No dashes, no semicolons, no lists, no headings.")
# Added when articles from the live services are in the list: they are known only from an
# abstract or a short excerpt, and the paragraph must not claim more.
_SCHOL_RECENT_NOTE = (
    " The list may hold articles found online, known only from an abstract or a short excerpt. "
    "When you draw on one, say so (for example 'to judge from its abstract'), and never "
    "claim to have read such an article.")
# Quoted Greek and Hebrew stay in their own letters (backend/original_script.py).
from backend.original_script import SCRIPT_RULE as _SCRIPT_RULE  # noqa: E402
_SUMMARY_SYSTEM += _SCRIPT_RULE
_SCHOL_SYSTEM += _SCRIPT_RULE
_SCHOL_RECENT = 4
_SCHOL_KEEP = 8
_SCHOL_DEPTH = 100
# Up to this many of the eight are reserved for journal articles when any
# qualify (2026-10-12, the owner: "Why does the paragraph on the Aeneid have
# to draw only on commentaries when you also have articles?"). Notes on the
# very lines outrank an article's passing mention every time, so without a
# reserved share the articles never reach the eight. An article qualifies
# when its title or snippet names the author, the work, or a capitalised
# name from the question itself (Dido, Aeneas).
_SCHOL_ARTICLES = 2
_SCHOL_STOP = {'The', 'A', 'An', 'What', 'How', 'Why', 'Where', 'When', 'Who', 'Which', 'I', 'In', 'On', 'Of'}


def _question_names(question):
    words = re.findall(r"[A-Z][\w'\u2019]+", question or '')
    out = []
    for w in words:
        w = re.sub(r"['\u2019]s$", '', w)
        if w not in _SCHOL_STOP and len(w) > 2:
            out.append(w.lower())
    return out[:4]

# One sentence saying what the scholarship collection holds for the work. The
# phrasing is picked by a hash of the question so a question always gets the
# same sentence and different questions differ. No colons, semicolons or dashes.
_HOLDINGS_WITH = (
    "The secondary sources I can read include {n} {things} from {who} on {title}.",
    "For {title} I have {n} {things} from {who} to draw on.",
    "The secondary sources I have access to give {n} {things} from {who} on {title}.",
    "My secondary sources on {title} for this question are {n} {things} from {who}.",
    "I found {n} {things} from {who} on {title} among the secondary sources I can read.",
)
# Every "none" sentence says "for this question": the collection may well hold
# notes on the work that this question did not reach (2026-10-12, Thucydides).
_HOLDINGS_NONE = (
    "I have no secondary sources on {title} to draw on for this question.",
    "I don't have access to any secondary sources on {title} that match this question.",
    "The secondary sources I can read have nothing on {title} for this question.",
    "No secondary source I can read speaks to {title} on this question.",
    "I can find no secondary literature on {title} for this question in what I have access to.",
)


# The second clause of the holdings sentence, about the live services. Five
# phrasings per state, picked by the same hash as the first clause. No colons,
# semicolons or dashes.
_RECENT_FOUND = (
    "the live services list {m} {art} for this question",
    "the live services add {m} {art}",
    "I also found {m} {art} online",
    "{m} {art} turned up in the live services",
    "the live services give {m} {art} on it",
)
_RECENT_NONE = (
    "the live services list no articles for this question",
    "the live services add nothing",
    "no article turned up in the live services",
    "I found no articles online",
    "the live services give no articles on it",
)
_RECENT_FAILED = (
    "{k} of the live services did not answer",
    "{k} of the live services failed to answer",
    "{k} of the live services gave no answer",
    "{k} of the live services could not be reached",
    "{k} of the live services returned no answer",
)


def _pick(options, question):
    import hashlib
    h = int(hashlib.sha256((question or '').strip().lower().encode('utf-8')).hexdigest(), 16)
    return options[h % len(options)]


def _join_names(names):
    names = list(dict.fromkeys(n for n in names if n))
    if not names:
        return 'the collection'
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f'{names[0]} and {names[1]}'
    return f'{names[0]}, {names[1]} and {len(names) - 2} more'


_ALIASES = {'vergil': ('virgil',), 'virgil': ('vergil',)}


def _scholarship_keep(cards, work, question=''):
    """The cards about this work: commentary notes on it (book files collapsed),
    notes on other works that name its author, and articles whose title or
    snippet names the author, the work, or a name from the question. Articles
    hold a reserved share of the eight (_SCHOL_ARTICLES) when any qualify;
    the rest fill in the search's order."""
    from backend import work_names
    base = work_names.base_work(work)
    info = passage_index._naming(base) or {}
    author = str(info.get('author') or '').strip().lower()
    title = str(info.get('title') or '').strip().lower()
    names = [n for n in (author,) if n]
    for n in list(names):
        names.extend(_ALIASES.get(n, ()))
    # A title of three letters or fewer ("Odes") would match anything.
    if len(title) >= 5:
        names.append(title)
    qnames = _question_names(question)
    notes, arts = [], []
    for c in cards or []:
        hay = ' '.join(str(c.get(k) or '') for k in ('title', 'snippet')).lower()
        names_it = bool(names) and any(re.search(r'\b' + re.escape(n) + r'\b', hay) for n in names)
        if c.get('kind') == 'commentary':
            # A note on the work itself, or a note on another work that names
            # this author (Page on the Aeneid comparing Thucydides' plague is
            # secondary literature on Thucydides too, 2026-10-12).
            if (c.get('work') and work_names.base_work(c['work']) == base) or names_it:
                notes.append(c)
        elif c.get('kind') == 'article':
            if names_it or any(re.search(r'\b' + re.escape(n) + r'\b', hay) for n in qnames):
                arts.append(c)
    n_arts = min(len(arts), _SCHOL_ARTICLES)
    kept = notes[:_SCHOL_KEEP - n_arts] + arts[:n_arts]
    if len(kept) < _SCHOL_KEEP:
        kept += arts[n_arts:_SCHOL_KEEP - len(kept) + n_arts]
    return kept[:_SCHOL_KEEP], info


def _scholarship_label(c):
    if c.get('kind') in ('article', 'recent'):
        t = (c.get('title') or 'Article').strip()
        return f"{t} ({c['year']})" if c.get('year') else t
    who = (c.get('commentator') or 'Commentary').strip()
    return f"{who} on {c['ref_start']}" if c.get('ref_start') else who


def _recent_clause(question, n_recent, n_failed):
    """(clause for the first sentence, extra sentence). Items found: the found
    clause, and a separate sentence when some service also failed. None found:
    the failed clause when a service failed, else the none clause."""
    if n_recent:
        art = 'article' if n_recent == 1 else 'articles'
        clause = _pick(_RECENT_FOUND, question).format(m=n_recent, art=art)
        extra = (_pick(_RECENT_FAILED, question).format(k=n_failed) if n_failed else '')
        return clause, (extra[0].upper() + extra[1:] + '.') if extra else ''
    if n_failed:
        return _pick(_RECENT_FAILED, question).format(k=n_failed), ''
    return _pick(_RECENT_NONE, question), ''


def _scholarship_holdings(question, kept, info, work, n_recent=None, n_failed=0):
    """One or two sentences on what is held. n_recent None leaves the live
    services out of it (the held sentence alone)."""
    sentence = _scholarship_held_sentence(question, kept, info, work)
    if n_recent is None:
        return sentence
    clause, extra = _recent_clause(question, n_recent, n_failed)
    out = sentence.rstrip('.') + ' and ' + clause + '.'
    return out + (' ' + extra if extra else '')


def _scholarship_held_sentence(question, kept, info, work):
    title = info.get('display_name') or info.get('title') or str(work)
    if not kept:
        return _pick(_HOLDINGS_NONE, question).format(title=title)
    arts = [c for c in kept if c.get('kind') == 'article']
    notes = [c for c in kept if c.get('kind') != 'article']
    if arts and notes:
        things = 'notes and articles'
    elif arts:
        things = 'articles' if len(kept) > 1 else 'article'
    else:
        things = 'notes' if len(kept) > 1 else 'note'
    who = _join_names([c.get('commentator') for c in notes] +
                      [c.get('journal') or 'journal articles' for c in arts])
    return _pick(_HOLDINGS_WITH, question).format(n=len(kept), things=things, who=who, title=title)


@passages_bp.route('/passages/ask-scholarship', methods=['POST'])
def ask_scholarship():
    """What the secondary literature says about the question, for one work."""
    import time
    import concurrent.futures
    from backend.assistant import model
    from backend import scholarship_theme
    from backend import original_script
    data = request.get_json(silent=True) or {}
    question = str(data.get('question') or '').strip()
    work = str(data.get('work') or '').strip()
    if not question or not work:
        return jsonify({'available': False, 'error': 'question and work are required'})
    # The search carries the author's and the work's names in front of the
    # question, so notes and articles about this author rank ahead of notes
    # on the same subject in other authors (2026-10-12: "the plague at
    # Athens" alone reached nothing naming Thucydides in the first thirty;
    # with his name in front, twelve).
    from backend import work_names as _wn
    _info = passage_index._naming(_wn.base_work(work)) or {}
    _prefix = ' '.join(x for x in (_info.get('author'), _info.get('title')) if x)
    query_used = f'{_prefix}: {question}' if _prefix else question
    try:
        found = scholarship_theme.theme(query_used, k=_SCHOL_DEPTH)
    except Exception as e:
        logger.info('[PASSAGES] ask-scholarship search failed: %s', type(e).__name__)
        return jsonify({'available': False, 'error': 'the scholarship search is not available'})
    kept, info = _scholarship_keep(found.get('results'), work, question)
    recent, services, n_found = _recent_for_paragraph(question, work)
    n_failed = sum(1 for v in services.values() if v == 'failed')
    holdings = _scholarship_holdings(question, kept, info, work, n_found, n_failed)
    base = {'holdings': holdings, 'query_used': query_used, 'recent': recent, 'services': services}
    if (not kept and not recent) or not model.is_available():
        return jsonify(dict(base, available=False))
    n_art = sum(1 for c in kept if c.get('kind') == 'article')
    n_note = len(kept) - n_art
    kind_names = []
    if n_note:
        kind_names.append('commentary notes')
    if n_art:
        kind_names.append('journal articles')
    if recent:
        kind_names.append('articles found online, known from abstracts')
    kinds = kind_names[0] if len(kind_names) == 1 else ', '.join(kind_names[:-1]) + ' and ' + kind_names[-1]
    # The model is told what kinds it has, so it does not write "the
    # commentaries and articles" over notes alone (owner, 2026-10-12).
    cards = list(kept) + [dict(r, kind='recent', link={'kind': 'web', 'url': _recent_link(r)}) for r in recent]
    lines = [f"{info.get('display_name') or work}", question,
             f"The sources below are {kinds} only. Name them as such."]
    for i, c in enumerate(cards, 1):
        if c.get('kind') == 'recent':
            venue = f", {c['venue']}" if c.get('venue') else ''
            year = f" ({c['year']})" if c.get('year') else ''
            lines.append(f"[{i}] Article found online, known from its abstract or an excerpt: "
                         f"{c.get('title')}{year}{venue}: {c.get('excerpt') or ''}")
        else:
            lines.append(f"[{i}] {_scholarship_label(c)}: {c.get('snippet') or ''}")
    system = _SCHOL_SYSTEM.format(limit=150 if recent else 120) + (_SCHOL_RECENT_NOTE if recent else '')
    t0 = time.time()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        fut = pool.submit(model.complete, system, '\n'.join(lines), 400, 0.2)
        try:
            text = fut.result(timeout=_SUMMARY_TIMEOUT)
            user_msg = '\n'.join(lines)
            text, script_problems = original_script.settle(
                text, [c.get('snippet') or c.get('excerpt') or '' for c in cards],
                lambda note: pool.submit(model.complete, system, user_msg + '\n' + note,
                                         400, 0.2).result(timeout=_SUMMARY_TIMEOUT))
        except concurrent.futures.TimeoutError:
            logger.info('[PASSAGES] ask-scholarship %r timed out after %.1fs', question, time.time() - t0)
            return jsonify(dict(base, available=False, error='the model took too long'))
        except Exception as e:
            logger.info('[PASSAGES] ask-scholarship %r failed: %s', question, type(e).__name__)
            return jsonify(dict(base, available=False, error='the model could not answer'))
    finally:
        pool.shutdown(wait=False)
    if not text:
        return jsonify(dict(base, available=False, error='the model could not answer'))
    used = sorted({int(n) for n in re.findall(r'\[(\d+)\]', text) if 1 <= int(n) <= len(cards)})
    cites = [{'n': n, 'kind': cards[n - 1].get('kind'), 'label': _scholarship_label(cards[n - 1]),
              'link': cards[n - 1].get('link')} for n in used]
    return jsonify(dict(base, available=True, summary=text, cites=cites, kept=len(cards),
                        script_problems=script_problems))


def _recent_link(item):
    doi = item.get('doi')
    return item.get('oa_url') or (f'https://doi.org/{doi}' if doi else None) or item.get('url')


def _recent_for_paragraph(question, work):
    """The live services' recent articles for the paragraph: each service asked
    in its own thread with ten seconds for the group (the page has usually
    fetched them already, so the answers come off the disk cache). Returns
    (up to _SCHOL_RECENT merged items, {service: 'ok'|'none'|'failed'|'off'},
    the number of distinct recent articles the services listed)."""
    import concurrent.futures
    from backend import scholarship_recent as sr
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=5)
    try:
        futs = {pool.submit(sr.recent_safe, question, work, name): name for name in sr.SERVICES}
        done, _pending = concurrent.futures.wait(futs, timeout=10)
        services, lists = {}, []
        for f, name in futs.items():
            if f in done:
                res = f.result()
                services[name] = sr.state(res)
                lists.append(res.get('results') or [])
            else:
                services[name] = 'failed'
    finally:
        pool.shutdown(wait=False)
    merged = sr.merge(lists)
    return merged[:_SCHOL_RECENT], services, len(merged)


@passages_bp.route('/passages/recent-scholarship', methods=['GET'])
def recent_scholarship():
    """Recent articles one live service gives for a question, about a work when
    one is given (work is optional: Theme Search's list has none).
    One service per request so the page can fire them in parallel and paint
    each as it lands. A service that fails answers available False, never 500."""
    from backend import scholarship_recent as sr
    question = (request.args.get('question') or '').strip()
    work = (request.args.get('work') or '').strip() or None
    service = (request.args.get('service') or '').strip().lower()
    if not question or service not in sr.SERVICES:
        return jsonify({'service': service, 'available': False, 'results': [],
                        'reason': 'a question and a known service are required'})
    return jsonify(sr.recent_safe(question, work, service))


def _chronological(results):
    """Oldest first, undated last.

    The same order the site shows results in, and the order the export has to
    keep: a themed set that crosses centuries is read as a line of descent, and
    a spreadsheet sorted by relevance score throws that away.
    """
    def key(r):
        y = r.get('year')
        return (0, y) if isinstance(y, (int, float)) else (1, 0)
    return sorted(results, key=key)


# The columns, in the order a reader wants to see them. Passage text last,
# because it is the long field and a spreadsheet is easier to scan when the
# labels come first.
_EXPORT_COLUMNS = [
    ('n', 'n'),
    ('author', 'author'),
    ('title', 'work'),
    ('locus', 'locus'),
    ('date', 'date'),
    ('era', 'era'),
    ('language', 'language'),
    ('score', 'score'),
    ('strong', 'strong'),
    ('themes', 'themes'),
    ('summary', 'gist'),
    ('passage', 'text'),
]

_LANG_NAME = {'la': 'Latin', 'grc': 'Greek', 'en': 'English', 'he': 'Hebrew',
              'cop': 'Coptic', 'fa': 'Persian', 'ur': 'Urdu', 'ar': 'Arabic',
              # The theme tier's medieval vernaculars (2026-09-01). Without
              # these the export labelled Dante's passages "it".
              'it': 'Italian', 'fro': 'Old French', 'gmh': 'Middle High German'}


def _order():
    """'score' (strongest first, the page's default) or 'date' (oldest first)."""
    o = (request.args.get('order') or '').strip().lower()
    return o if o in ('score', 'date') else 'date'


_ORDER_LABEL = {'score': 'strongest match first',
                'date': 'oldest first; undated last'}


def _by_score(results):
    """Strongest first, the page's Best-match order: works ranked by their best
    passage, each work's passages kept together (client utils/chronology.js)."""
    best = {}
    for r in results:
        w = r.get('work') or ''
        best[w] = max(best.get(w, 0), r.get('score') or 0)
    return sorted(results, key=lambda r: (-best.get(r.get('work') or '', 0),
                                          r.get('work') or '',
                                          -(r.get('score') or 0)))


def _export_rows(results, texts, order='date'):
    """Flatten results into labelled rows carrying their source passage.

    The rows follow the order the reader chose on the page. The export used to
    be oldest first regardless, so a Best-match list on screen came out as a
    different document in the download.
    """
    rows = []
    ordered = _by_score(results) if order == 'score' else _chronological(results)
    for i, r in enumerate(ordered, start=1):
        # Without the work id the reference tags repeat ("mir.kulliyat_wikisource
        # .ghazal.341.8-mir.kulliyat_wikisource.ghazal.343.7" was half the line).
        prefix = f"{r.get('work') or ''}."
        start = str(r.get('ref_start') or '')
        end = str(r.get('ref_end') or '')
        if prefix != '.':
            start = start[len(prefix):] if start.startswith(prefix) else start
            end = end[len(prefix):] if end.startswith(prefix) else end
        locus = start
        if end and end != start:
            locus = f"{start}-{end}"
        rows.append({
            'n': i,
            'author': r.get('author') or '',
            'work': r.get('title') or r.get('work') or '',
            'locus': locus,
            # The dating note ("d. c. 1020 CE") says more than the bare year and
            # is what a scholar would cite, so it leads where it exists.
            'date': r.get('date_note') or (str(r['year']) if isinstance(
                r.get('year'), (int, float)) else ''),
            'era': r.get('era') or '',
            'language': _LANG_NAME.get(r.get('language'), r.get('language') or ''),
            'score': round(r['score'], 4) if isinstance(
                r.get('score'), (int, float)) else '',
            'strong': 'yes' if r.get('strong') else 'no',
            'themes': '; '.join(str(t) for t in (r.get('themes') or [])),
            'gist': r.get('gist') or '',
            # Absent rather than empty when the lookup has no text, so a hole is
            # visible in the export instead of looking like a blank passage.
            'text': texts.get(r.get('id'), '[source text unavailable]'),
            'id': r.get('id') or '',
        })
    return rows


@passages_bp.route('/passages/lines')
def passage_lines_route():
    """The actual lines at a reference. The half of retrieval that was missing.

    Claude desktop, testing the connector: theme_search instructs the agent
    "the gist is a machine-written summary of the passage, never the passage
    itself: fetch the lines before quoting", and no tool could do it. The only
    way through was an exact-phrase search on wording the user already knew from
    memory, which is precisely the reader this feature exists to serve without.

    Takes exactly the fields theme_search and similar_passages already emit, so
    a result can be handed straight back without the caller reshaping anything.
    """
    work = (request.args.get('work') or '').strip()
    if not work:
        return jsonify({'error': 'work is required', 'lines': []})
    try:
        context = max(0, min(20, int(request.args.get('context') or 0)))
    except (TypeError, ValueError):
        context = 0
    out = window_texts.passage_lines(
        work,
        (request.args.get('ref_start') or '').strip() or None,
        (request.args.get('ref_end') or '').strip() or None,
        context=context)
    if out.get('error'):
        return jsonify(out)

    # The same naming the theme-search results carry, so a citation built from
    # this matches a citation built from those.
    naming = passage_index._naming(work.replace('.tess', ''))
    language = window_texts.language_of(work)
    out.update({
        'work': work,
        'author': naming.get('author') or '',
        'title': naming.get('title') or '',
        'display_name': naming.get('display_name') or '',
        'language': language or '',
        'corpus_version': get_corpus_version(language) if language else None,
        # So a quotation can always be taken back to the real thing.
        'web_url': ('/read?work=' + quote(work if work.endswith('.tess')
                                          else work + '.tess')
                    + (f"&at={quote(out['lines'][0]['ref'])}"
                       if out.get('lines') else '')),
    })
    if out.get('capped'):
        out['note'] = (f"Showing {out['returned']} of {out['total']} lines. "
                       f"Narrow ref_start/ref_end for the rest.")
    return jsonify(out)


@passages_bp.route('/passages/export')
def export_theme_search():
    """The same Theme Search, with the source passages, oldest first.

    Theme Search results name a work and a line range and carry a machine-written
    summary, but never the passage itself, so what a reader could take away was a
    list of pointers. This returns the passages, labelled, in chronological
    order, as JSON for the printable view or CSV for a spreadsheet.
    """
    q = (request.args.get('q') or request.args.get('query') or '').strip()
    fmt = (request.args.get('format') or 'json').strip().lower()
    if not q:
        return jsonify({'error': 'q is required', 'results': []})
    if fmt not in ('json', 'csv', 'pdf'):
        return jsonify({'error': f'unknown format {fmt}', 'results': []})
    try:
        out = passage_index.find_by_text(
            q, limit=_int_arg('limit', 25), languages=_languages(), scale=_scale())
    except passage_index.EmbedUnavailable as e:
        logger.warning('[PASSAGES] encoder unavailable: %s', e)
        return jsonify({'error': 'theme search is unavailable: the query encoder '
                                 'service is not running', 'unavailable': True,
                        'results': []})
    except Exception as e:
        logger.exception('[PASSAGES] export failed')
        return jsonify({'error': f'{type(e).__name__}: {e}', 'results': []})

    results = out.get('results') or []
    texts = window_texts.texts_for([r.get('id') for r in results])
    order = _order()
    rows = _export_rows(results, texts, order)
    langs = _languages()
    lang_label = (', '.join(_LANG_NAME.get(x, x) for x in langs)
                  if langs else 'all languages')
    missing = sum(1 for r in rows if r['text'] == '[source text unavailable]')
    if missing:
        logger.warning('[PASSAGES] export: %d of %d passages had no source text',
                       missing, len(rows))

    if fmt == 'pdf':
        # A real file, not a printable page. The browser still renders the
        # scripts better than any PDF library will, so the printable route
        # stays; this is for a reader who wants something to keep or send.
        if not theme_pdf.available():
            return jsonify({'error': 'PDF export is unavailable on this server '
                                     '(reportlab or the fonts are missing)',
                            'results': []})
        try:
            body = theme_pdf.build({'query': q, 'count': len(rows),
                                    'missing_text': missing,
                                    'confidence': out.get('confidence'),
                                    'order_label': _ORDER_LABEL[order],
                                    'languages_label': lang_label,
                                    'results': rows})
        except Exception as e:                                   # noqa: BLE001
            logger.exception('[PASSAGES] pdf export failed')
            return jsonify({'error': f'could not build the PDF: {e}',
                            'results': []})
        stamp = ''.join(ch if ch.isalnum() else '_' for ch in q)[:40].strip('_')
        return Response(body, content_type='application/pdf', headers={
            'Content-Disposition':
                f'attachment; filename="tesserae_theme_{stamp or "search"}.pdf"'})

    if fmt == 'csv':
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([label for label, _ in _EXPORT_COLUMNS])
        for row in rows:
            w.writerow([row[key] for _, key in _EXPORT_COLUMNS])
        # BOM: Excel reads a UTF-8 CSV as the system codepage without one, which
        # turns every Greek, Hebrew and Persian passage in the file into mojibake.
        body = '﻿' + buf.getvalue()
        stamp = ''.join(ch if ch.isalnum() else '_' for ch in q)[:40].strip('_')
        # content_type, not mimetype: Flask appends its own charset to a
        # mimetype, so passing one here produced "text/csv; charset=utf-8;
        # charset=utf-8".
        return Response(body, content_type='text/csv; charset=utf-8', headers={
            'Content-Disposition':
                f'attachment; filename="tesserae_theme_{stamp or "search"}.csv"'})

    return jsonify({
        'query': q,
        'count': len(rows),
        'missing_text': missing,
        'confidence': out.get('confidence'),
        'note': out.get('note'),
        'order': _ORDER_LABEL[order],
        'languages': lang_label,
        'results': rows,
    })


def _opt_int(name):
    """A non-negative integer query parameter, or None when absent or not one."""
    raw = (request.args.get(name) or '').strip()
    return int(raw) if raw.isdigit() else None


@passages_bp.route('/passages/similar')
def similar_passages():
    """Passages whose content resembles a given passage.

    Accepts either an index window id (?window=) or a reader selection
    (?work= plus optional ?ref_start= and ?ref_end=).
    """
    window = (request.args.get('window') or '').strip()
    work = (request.args.get('work') or '').strip()
    limit = _int_arg('limit', 15)
    langs = _languages()
    include_same = (request.args.get('include_same_work') or '').lower() in ('1', 'true', 'yes')
    # By default the same Bible passage in the corpus's other versions is not
    # reported back: a reader in Coptic Genesis knows it is also in Hebrew and
    # Latin. A scholar comparing versions can ask for them with
    # ?include_other_versions=1.
    include_versions = (request.args.get('include_other_versions') or '').lower() in ('1', 'true', 'yes')
    # "Same people and places": a second grouping, behind this parameter, for
    # windows sharing rare proper names with the selection rather than only
    # content similarity (backend/passage_index.py:same_names_for_window).
    # Omitted, the response is byte-for-byte what it has always been.
    same_names_requested = (request.args.get('same_names') or '').strip() in ('1', 'true', 'yes')
    # Per-language sections under the main list (2026-10-07): ?by_language=1.
    by_language = (request.args.get('by_language') or '').strip() in ('1', 'true', 'yes')
    if window:
        out = passage_index.find_similar_to_window(
            window, limit=limit, languages=langs, include_same_work=include_same,
            suppress_other_versions=not include_versions, by_language=by_language)
    elif work:
        out = passage_index.find_similar_to_passage(
            work, request.args.get('ref_start'), request.args.get('ref_end'),
            limit=limit, languages=langs, scale=_scale() or 'fine',
            suppress_other_versions=not include_versions, by_language=by_language,
            char_start=_opt_int('char_start'), char_end=_opt_int('char_end'))
    else:
        return jsonify({'error': 'work or window is required', 'results': []})
    if same_names_requested:
        src_wid = window or (out.get('source') or {}).get('id')
        same_names = passage_index.same_names_for_window(src_wid) if src_wid else None
        out['same_names'] = same_names
        if same_names:
            exclude = {r.get('id') for r in same_names.get('results', [])}
            exclude |= {r.get('id') for r in same_names.get('commentaries', [])}
            out['results'] = [r for r in out.get('results', [])
                              if r.get('id') not in exclude]
            for lang, rows in list((out.get('by_language') or {}).items()):
                rows = [r for r in rows if r.get('id') not in exclude]
                if rows:
                    out['by_language'][lang] = rows
                else:
                    del out['by_language'][lang]
    out['presentation'] = (
        'These passages resemble the selection in CONTENT (scene type, theme, '
        'situation) rather than in wording. Say what kind of resemblance each '
        'shows, and note that a cross-language match shares no vocabulary. '
        'A result carrying `also_in` is one scriptural passage present in several '
        'of the corpus versions, collapsed into a single entry.')
    return jsonify(out)


# BOTH PATHS, deliberately. Every other route in this blueprint carries the
# /passages/ prefix in its own decorator, and these two do not, so they answer at
# /api/lexical-density and /api/translation while /api/passages/... 404s. The
# frontend calls the short paths and has always worked; the cost is that anyone
# reasoning from the neighbouring routes gets a 404 that reads exactly like a
# stale deploy, which cost an hour on 2026-08-27. Moving them would be the tidier
# fix and would break every existing caller, so the prefixed path is added
# alongside rather than instead. See issue #275.

# -- Phrase parallels inside a theme-comparison pair -----------------------
#
# The two "echo each other" tools, Theme Comparison (content) and fusion
# search (wording), have never answered a question together: of the passage
# pairs Theme Comparison surfaces, which ones ALSO share actual words? That
# needs a cached fusion run over the same two texts to already exist --
# running one live from this route would turn a sub-second comparison into a
# multi-minute one -- so this only ever JOINS against whatever is already in
# cache/, the way a page that has already run the word-level comparison, or
# whose server has, gets it for free.
_PHRASE_LOOKUP_CAP = 50     # distinct per-window work pairs probed for a cache hit
_PHRASES_PER_PAIR = 10      # phrase parallels kept per theme pair, highest score first


def _fusion_cache_for_book_pair(work_a, work_b, language_a, language_b):
    """Cached fusion rows for one (book-level) work pair, tried in both
    directions, or None if neither is cached.

    Cross-lingual theme pairs (a Latin passage matched to a Greek one by
    content) are skipped: fusion search's cache key assumes one language for
    both sides (see _default_fusion_cache_settings), and the dedicated
    cross-lingual search is a different endpoint entirely, so there is no
    single-language settings dict to build for them. Returns (rows,
    a_is_source) so the caller knows which side of each cached row is work_a's.
    """
    if not language_a or language_a != language_b:
        return None
    from backend.blueprints.fusion import _default_fusion_cache_settings, _poll_use_meter
    from backend.cache import get_cached_results
    a_id = work_a if work_a.endswith('.tess') else f'{work_a}.tess'
    b_id = work_b if work_b.endswith('.tess') else f'{work_b}.tess'
    use_meter = _poll_use_meter(a_id, b_id, language_a)
    # Same settings dict the plain GET /fusion-search poll builds for a caller
    # that passes no overrides -- the exact path the Search page's results are
    # cached under, so a pair already run there is found here unchanged.
    settings = _default_fusion_cache_settings(language_a, 5000, use_meter)
    rows, _meta = get_cached_results(a_id, b_id, language_a, settings)
    if rows:
        return rows, True
    rows, _meta = get_cached_results(b_id, a_id, language_a, settings)
    if rows:
        return rows, False
    return None


def _ref_within_window(work, ref, ref_start, ref_end):
    """Same ref-to-number covering test window_for_passage uses: ref's
    trailing numeric coordinates (stripped of the work name) fall between the
    window's start and end coordinates."""
    want = passage_index._ref_numbers_in(work, ref)
    lo = passage_index._ref_numbers_in(work, ref_start)
    hi = passage_index._ref_numbers_in(work, ref_end)
    if not (want and lo and hi):
        return False
    return lo <= want <= hi


def _compare_run_url(work_a, work_b, language):
    a_id = work_a if work_a.endswith('.tess') else f'{work_a}.tess'
    b_id = work_b if work_b.endswith('.tess') else f'{work_b}.tess'
    return '/?' + urlencode({'lang': language or '', 'source': a_id, 'target': b_id})


def _attach_phrase_parallels(out, work_a, work_b):
    """Joins cached word-level (fusion) results onto `out['pairs']`, in place.

    Looks up the cache once per distinct (window_a.work, window_b.work) pair
    actually present among the theme pairs -- a whole work compared as books
    this way costs one lookup per book pair involved, not one per theme pair
    -- capped at _PHRASE_LOOKUP_CAP. When nothing is cached anywhere, every
    pair is left alone and `out['phrases']` says so with a link that opens the
    word-level comparison ready to run. When something is cached, every pair
    whose book combination hit the cache gets its `phrases` list (possibly
    empty, when no cached parallel's two lines land inside both windows).
    """
    pairs = out.get('pairs') or []
    combos = []
    for p in pairs:
        wa = (p.get('a') or {}).get('work')
        wb = (p.get('b') or {}).get('work')
        if wa and wb and (wa, wb) not in combos:
            combos.append((wa, wb))
        if len(combos) >= _PHRASE_LOOKUP_CAP:
            break
    cache_by_combo = {}
    for wa, wb in combos:
        la = next((p['a'].get('language') for p in pairs if p['a'].get('work') == wa), None)
        lb = next((p['b'].get('language') for p in pairs if p['b'].get('work') == wb), None)
        cache_by_combo[(wa, wb)] = _fusion_cache_for_book_pair(wa, wb, la, lb)
    if not any(v is not None for v in cache_by_combo.values()):
        language = pairs[0]['a'].get('language') if pairs else None
        out['phrases'] = {'available': False,
                          'run_url': _compare_run_url(work_a, work_b, language)}
        return
    pairs_with_phrases = 0
    for p in pairs:
        a_rec, b_rec = p.get('a') or {}, p.get('b') or {}
        wa, wb = a_rec.get('work'), b_rec.get('work')
        hit = cache_by_combo.get((wa, wb))
        if hit is None:
            continue
        rows, a_is_source = hit
        found = []
        for row in rows:
            s, t = row.get('source') or {}, row.get('target') or {}
            if a_is_source:
                a_ref, b_ref = s.get('ref'), t.get('ref')
                a_text, b_text = s.get('text'), t.get('text')
            else:
                a_ref, b_ref = t.get('ref'), s.get('ref')
                a_text, b_text = t.get('text'), s.get('text')
            if _ref_within_window(wa, a_ref, a_rec.get('ref_start'), a_rec.get('ref_end')) and \
               _ref_within_window(wb, b_ref, b_rec.get('ref_start'), b_rec.get('ref_end')):
                found.append({'source_ref': a_ref, 'target_ref': b_ref,
                              'matched_words': row.get('matched_words'),
                              'score': row.get('fused_score'),
                              'source_text': a_text, 'target_text': b_text})
        if found:
            found.sort(key=lambda x: -(x.get('score') or 0))
            p['phrases'] = found[:_PHRASES_PER_PAIR]
            pairs_with_phrases += 1
    out['phrases'] = {'available': True, 'pairs_with_phrases': pairs_with_phrases}


@passages_bp.route('/passages/compare')
def compare_works_route():
    """Theme comparison of two works or books, by content rather than words.

    GET /api/passages/compare?work_a=vergil.aeneid.part.1&work_b=lucan.bellum_civile.part.1
        [&scale=fine|coarse&limit=50&per_window=3&with_phrases=1]
    Every window of work_a is scored against every window of work_b on the
    Similar Passages vectors; the best pairs come back with both windows'
    descriptions and a confidence block (median baseline, head lift, level).
    with_phrases=1 additionally joins each pair against any already-cached
    word-level (fusion) comparison of the two works, see _attach_phrase_parallels.
    """
    work_a = (request.args.get('work_a') or '').strip().replace('.tess', '')
    work_b = (request.args.get('work_b') or '').strip().replace('.tess', '')
    if not work_a or not work_b:
        return jsonify({'error': 'work_a and work_b are required', 'pairs': []})
    scale = (request.args.get('scale') or 'fine').strip()
    if scale not in ('fine', 'coarse'):
        scale = 'fine'
    with_phrases = (request.args.get('with_phrases') or '').strip().lower() in ('1', 'true', 'yes')
    out = passage_index.compare_works(
        work_a, work_b, scale=scale,
        limit=_int_arg('limit', 50, lo=1, hi=passage_index.COMPARE_PAIR_LIMIT),
        per_window=_int_arg('per_window', 3, lo=1, hi=10))
    for p in out.get('pairs') or []:
        for side in ('a', 'b'):
            w = p[side]
            w['reader_url'] = '/read?' + urlencode({
                'work': f"{w.get('work')}.tess", 'lang': w.get('language') or '',
                'ref': w.get('ref_start') or '', 'refEnd': w.get('ref_end') or w.get('ref_start') or '',
                'tab': 'similar'})
    if with_phrases and not out.get('error') and out.get('pairs'):
        _attach_phrase_parallels(out, work_a, work_b)
    # Like every route in this blueprint: 200 with an `error` field, so a page
    # or a connector reads one shape whatever happened.
    return jsonify(out)


@passages_bp.route('/passages/pair-lift', methods=['POST'])
def pair_lift_route():
    """The Theme Comparison reading of up to 100 word-level result pairs.

    POST /api/passages/pair-lift {"pairs": [{"work_a","ref_a","work_b","ref_b"}, ...]}
    For each pair, the cosine between the fine passage windows covering ref_a
    (in work_a) and ref_b (in work_b), and its lift above the two works'
    general resemblance (backend.passage_index.pair_lift, which caches the
    baseline per work pair so a page of 25 results costs one matrix pass).
    Returns {"results": [{"score","lift","level"}, ...]} in request order,
    with null score/lift/level where no indexed window covers one of the lines.
    """
    body = request.get_json(silent=True) or {}
    pairs = body.get('pairs')
    if not isinstance(pairs, list) or not pairs:
        return jsonify({'error': 'pairs is required (a non-empty list)', 'results': []})
    results = []
    for p in pairs[:100]:
        out = None
        if isinstance(p, dict):
            work_a = str(p.get('work_a') or '').strip().replace('.tess', '')
            work_b = str(p.get('work_b') or '').strip().replace('.tess', '')
            ref_a, ref_b = p.get('ref_a'), p.get('ref_b')
            if work_a and work_b and ref_a and ref_b:
                out = passage_index.pair_lift(work_a, ref_a, work_b, ref_b)
        results.append(out or {'score': None, 'lift': None, 'level': None})
    return jsonify({'results': results})


@passages_bp.route('/passages/lexical-density')
@passages_bp.route('/lexical-density')
def lexical_density_route():
    """Per-line lexical connection counts, for the Reader's red gutter marks.

    Answers the older question ("what else uses these words?") beside the scene
    index's newer one ("what else is about this?"). Read off the precomputed
    lemma_doc_freq table and cached per work, so it costs a file read after the
    first call.
    """
    work = (request.args.get('work') or '').strip()
    if not work:
        return jsonify({'error': 'work is required', 'lines': []})
    language = (request.args.get('language') or 'la').strip()
    return jsonify(lexical_density.line_density(work, language=language))


@passages_bp.route('/passages/works')
def works_available():
    """Which works of a language have passage windows, for the Browse Corpus
    "Theme Search" badge.

    A work with no passage windows never appears in Theme Search or Similar
    Passages, so Browse Corpus marks the ones that do.
    passage_index.works_for_language() answers this from a small on-disk
    sidecar when one is present and current, with no index load at all;
    only when the sidecar is missing or stale does it fall back to loading
    the full passage index, which is what made this route slow or empty
    right after a deploy reload. Cached per worker either way, since the
    index does not change for the life of the process."""
    language = (request.args.get('language') or 'la').strip()
    return jsonify({'language': language,
                    'index_version': passage_index.index_version(),
                    'works': passage_index.works_for_language(language)})


@passages_bp.route('/passages/translations')
def translations_available():
    """Which works of a language have aligned translations, with attribution.

    Feeds the Browse Corpus translation badges. Cached per worker against the
    translations directory listing."""
    language = (request.args.get('language') or 'la').strip()
    return jsonify({'language': language,
                    'works': translations.available(language)})


@passages_bp.route('/passages/translation-full')
def translation_full():
    """The whole translation of one work, in reading order, as blocks."""
    work = (request.args.get('work') or '').strip()
    if not work:
        return jsonify({'error': 'work is required'}), 400
    language = (request.args.get('language') or '').strip() or None
    return jsonify(translations.full_text(work, language))


@passages_bp.route('/passages/translation')
@passages_bp.route('/translation')
def translation_route():
    """Aligned public-domain English for a selected passage.

    Pass the work and the selected refs (comma-separated, or repeated `ref`).
    Answers with available:false and a plain reason when no aligned translation
    covers the passage, which is a normal outcome given partial coverage.
    """
    work = (request.args.get('work') or '').strip()
    if not work:
        return jsonify({'available': False, 'reason': 'work is required'})
    refs = request.args.getlist('ref')
    if not refs:
        raw = request.args.get('refs') or ''
        refs = [r for r in (x.strip() for x in raw.split('|')) if r]
    return jsonify(translations.for_passage(work, refs))


@passages_bp.route('/passages/density')
def density():
    """Per-window connection counts for the Reader's gutter."""
    work = (request.args.get('work') or '').strip()
    if not work:
        return jsonify({'error': 'work is required', 'windows': []})
    return jsonify(passage_index.connection_density(work, scale=_scale() or 'fine'))


# ---------------------------------------------------------------------------
# Corpus connections map: a picture of Theme Search's own connections
# (the same passage index, the same description embeddings), aggregated by
# work, author, century and genre. Backed entirely by the offline cache
# scripts/build_connections_map.py writes to cache/connections_map/; nothing
# below touches the passage index itself, so a request here costs a SQLite
# read rather than a matrix multiply. All four routes 404 with a plain
# message when that cache has not been built for the current index.
# ---------------------------------------------------------------------------
def _map_languages():
    raw = (request.args.get('languages') or '').strip()
    if not raw:
        return None
    langs = [x.strip() for x in raw.split(',') if x.strip()]
    return langs or None


def _map_translations():
    raw = (request.args.get('translations') or '').strip().lower()
    return raw in ('1', 'true', 'yes')


def _map_refresh():
    raw = (request.args.get('refresh') or '').strip().lower()
    return raw in ('1', 'true', 'yes')


@passages_bp.route('/passages/map')
def connections_map_route():
    """The matrix for one view: authors, works, centuries or genres.

    Translation pairs (curated or heuristic-detected) are excluded from the
    counts unless ?translations=1 is passed, since the strongest signal in
    this data is "the same text in two languages", which would otherwise
    swamp the allusive relationships a scholar is looking for.

    ?refresh=1 clears the module's process-level caches first (see
    connections_map.reset_process_caches()), so a newly built cache and the
    current window ids are picked up without a process restart.
    """
    if _map_refresh():
        connections_map.reset_process_caches()
    if not connections_map.is_available():
        return jsonify({'error': 'the connections map has not been built for '
                                 'this index'}), 404
    view = (request.args.get('view') or 'author').strip().lower()
    out = connections_map.get_map(
        view, languages=_map_languages(),
        top=_int_arg('top', connections_map.DEFAULT_TOP, lo=2, hi=connections_map.MAX_TOP),
        translations=_map_translations())
    return jsonify(out)


@passages_bp.route('/passages/map/cell')
def connections_map_cell_route():
    """The work pairs behind one matrix cell (view + the two entity ids).

    ?refresh=1 clears the module's process-level caches first (see
    connections_map.reset_process_caches())."""
    if _map_refresh():
        connections_map.reset_process_caches()
    if not connections_map.is_available():
        return jsonify({'error': 'the connections map has not been built for '
                                 'this index'}), 404
    view = (request.args.get('view') or 'author').strip().lower()
    a = (request.args.get('a') or '').strip()
    b = (request.args.get('b') or '').strip()
    out = connections_map.get_cell(view, a, b, languages=_map_languages(),
                                   translations=_map_translations())
    return jsonify(out)


@passages_bp.route('/passages/map/pair')
def connections_map_pair_route():
    """The strongest passage pairs behind one work pair, ready for the Reader.

    Each pair carries both window ids, refs, a one-line description, the
    score, and a `reader_url` per side built the same way Similar Passages'
    "Open in Reader" links are (work + language + ref span, landing on the
    Similar Passages tab so the connection is visible live). Deduplicated on
    the unordered window pair, work_a's window always on the left (2026-09-19
    convention -- see connections_map.get_pair). `book_a`/`book_b` filter to
    one cell of the books x books drill-down (`/passages/map/books`).

    ?refresh=1 clears the module's process-level caches first (see
    connections_map.reset_process_caches()).
    """
    if _map_refresh():
        connections_map.reset_process_caches()
    work_a = (request.args.get('work_a') or '').strip()
    work_b = (request.args.get('work_b') or '').strip()
    if not connections_map.is_available():
        return jsonify({'error': 'the connections map has not been built for '
                                 'this index'}), 404
    out = connections_map.get_pair(
        work_a, work_b,
        limit=_int_arg('limit', connections_map.DEFAULT_PAIR_LIMIT, lo=1,
                       hi=connections_map.MAX_PAIR_LIMIT),
        book_a=(request.args.get('book_a') or '').strip() or None,
        book_b=(request.args.get('book_b') or '').strip() or None)
    return jsonify(out)


@passages_bp.route('/passages/map/books')
def connections_map_books_route():
    """Books x books heatmap for one work pair -- the third drill-down level.

    A "book" is the first level of a window's ref_start (e.g. "hom. il.
    4.446" -> book 4); a work whose refs carry only one level is split into
    blocks of 100 lines labelled by the block's own first line. Computed from
    the edges/windows tables already in the cache -- no schema change, no
    rebuild required.

    ?refresh=1 clears the module's process-level caches first (see
    connections_map.reset_process_caches()).
    """
    if _map_refresh():
        connections_map.reset_process_caches()
    if not connections_map.is_available():
        return jsonify({'error': 'the connections map has not been built for '
                                 'this index'}), 404
    work_a = (request.args.get('work_a') or '').strip()
    work_b = (request.args.get('work_b') or '').strip()
    out = connections_map.get_books_map(work_a, work_b)
    return jsonify(out)


@passages_bp.route('/passages/map/work')
def connections_map_work_route():
    """One work's connections by work, for a "start from one work" view.

    ?refresh=1 clears the module's process-level caches first (see
    connections_map.reset_process_caches())."""
    if _map_refresh():
        connections_map.reset_process_caches()
    if not connections_map.is_available():
        return jsonify({'error': 'the connections map has not been built for '
                                 'this index'}), 404
    work = (request.args.get('work') or '').strip()
    out = connections_map.get_work_connections(
        work, languages=_map_languages(), translations=_map_translations(),
        limit=_int_arg('limit', 50, lo=1, hi=500))
    return jsonify(out)
