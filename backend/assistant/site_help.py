"""What the site does, taken from the Help page rather than written out again.

WHY

Tessa's guide half knew about the SEARCHES and nothing else. It had never heard
of the Reader or Theme Search, so "how do I read the Aeneid?" fell through to a
corpus listing, and every gap got closed by adding another keyword to another
tuple in agent.py, which raised the real question: would feeding the model
the Help page directly be enough, instead of preprogramming every response?

Mostly it is enough. The model explains things well when it has something true
to explain from, and the Help page is 44,000 characters of exactly that,
maintained because readers use it. Hand-copying any of it into a prompt creates
a second version to keep in step, and the copy is the one that goes stale.

So the Help page is the source. It is JSX, so the prose is extracted, merged
back into paragraphs (JSX splits sentences across elements) and cached. The
whole thing is far too much to send with every question -- prompt processing is
already five seconds on this CPU -- so a handful of relevant sections are
selected per question.

WHAT THIS DOES NOT SOLVE

Identifiers. The model chose "Vergil_Aeneid" and "Statius_Thebaid" for a search,
neither of which exists, and no amount of documentation fixes that: it does not
have 1,826 work ids memorised and never will. Prose comes from here; ids and
URLs are still resolved and built in code. That division is the whole design.
"""
import html
import json
import math
import os
import re
import threading

from backend.logging_config import get_logger

logger = get_logger('assistant.site_help')

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PAGES = os.path.join(_ROOT, 'client', 'src', 'components', 'pages')
HELP_SOURCE = os.path.join(_PAGES, 'HelpPage.jsx')
# The other pages a reader asks about (2026-10-21: asked where the texts come from,
# whether a text can be downloaded and under what license, Tessa answered that the
# site does not say, because only the Help page was read). Each page's chunks carry
# the page's name before the heading, so the model can say where a fact is found.
OTHER_SOURCES = [
    (os.path.join(_PAGES, 'AboutPage.jsx'), 'About page'),
    (os.path.join(_PAGES, 'DownloadsPage.jsx'), 'Downloads page'),
    (os.path.join(_PAGES, 'ScholarshipSourcesPage.jsx'), 'Scholarship sources page'),
    (os.path.join(_PAGES, 'PrivacyPage.jsx'), 'Privacy page'),
]
CACHE_PATH = os.path.join(_ROOT, 'cache', 'site_help_chunks.json')
# Raise this when _extract changes, so a cache written by the old code is not
# trusted just because the Help page itself has not changed.
EXTRACTOR_VERSION = 6   # 6: inline code, em, i, b and span text kept in its sentence (2026-10-21)

# Long enough to carry an idea, short enough that four of them fit in a prompt
# without adding seconds of prompt processing.
CHUNK_MIN = 200
CHUNK_MAX = 900

_lock = threading.Lock()
_chunks = None

# Words that say nothing about which section a question is about.
_STOP = {
    'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'to', 'from', 'with', 'for',
    'is', 'are', 'was', 'were', 'be', 'been', 'it', 'its', 'this', 'that',
    'these', 'those', 'what', 'which', 'who', 'how', 'do', 'does', 'did', 'can',
    'could', 'would', 'should', 'i', 'you', 'we', 'they', 'my', 'your', 'me',
    'at', 'by', 'as', 'if', 'so', 'not', 'no', 'yes', 'but', 'about', 'there',
    'here', 'when', 'then', 'than', 'into', 'out', 'up', 'down', 'more', 'most',
    'some', 'any', 'all', 'want', 'like', 'get', 'use', 'using', 'used', 'one',
    # "if I don't have a Greek keyboard" and "without a Greek keyboard" ask the same thing
    # (2026-10-22: the Help answer was missed and the model told a reader to type Greek in Latin letters).
    'don', 'dont', 'have', 'has', 'without',
}


def _extract(source=None, page=''):
    """Visible prose from the Help page, merged back into paragraphs.

    JSX splits a sentence across elements -- "Most people start with the default"
    then ", which compares two texts" -- so consecutive fragments are joined
    until they make something of readable length.
    """
    path = source or HELP_SOURCE
    try:
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
    except OSError as e:
        logger.info('[HELP] cannot read %s: %s', path, e)
        return []

    # HEADINGS ARE BOUNDARIES, not more text to glue on.
    #
    # Merging fragments blindly produced "Theme Search (its own tab) Read a text
    # with a gutter showing where the rest of the corpus connects to each line",
    # which describes the READER under the Theme Search heading. The Help page
    # is right; two <h4> headings sit next to each other and the merge ran
    # straight through the second one. Feeding the model a sentence that is
    # false is worse than giving it nothing, so a heading now closes the chunk
    # before it and opens the one after.
    # A HEADING IS TAKEN WHOLE, from its opening tag to its closing one.
    #
    # Reading it as "the next text fragment" got it wrong twice. First the
    # closing '<' of a paragraph swallowed the '<' opening the heading, so
    # headings after text were never seen at all and "Theme Search" ran on into
    # the Reader's description. Then, with that fixed, <h4>Read <span>(its own
    # tab)</span></h4> yielded "Read " -- five characters, under the minimum
    # fragment length -- so the heading became "(its own tab)" and the word Read
    # was lost. Both are the same mistake: inferring structure from the text
    # instead of reading it.
    # A link's text belongs to its sentence. Read as a separate fragment, a short
    # link (a person's name) fell below the fragment length and vanished, so the
    # About page's "Founded in 2008 by Neil Coffee and J. P. Koenig" reached Tessa
    # as "J. P. Koenig", and she named him the maker of the site (2026-10-21).
    src = re.sub(r"\{'\s*'\}", ' ', src)
    src = re.sub(r'<a\b[^>]*>', '', src, flags=re.S).replace('</a>', '')
    # The same for inline formatting: the Coptic keyboard table writes each letter
    # as <code>j</code> = djandja, and every short <code> fragment was dropped, so
    # Tessa told a reader that "=" stands for three different letters (2026-10-21).
    src = re.sub(r'</?(?:code|em|i|b|span)\b[^>]*>', '', src, flags=re.S)
    heading_re = re.compile(r'<(h[1-6])\b[^>]*>(.*?)</\1>', re.S)
    headings = []          # (start, end, text)
    for m in heading_re.finditer(src):
        inner = ' '.join(re.sub(r'<[^>]+>', ' ', m.group(2)).split())
        inner = re.sub(r'\{[^{}]*\}', '', inner).strip()
        inner = html.unescape(inner)
        if inner:
            headings.append((m.start(), m.end(), inner))

    def heading_at(pos):
        """The heading this position sits under, and whether it is inside one."""
        current = ''
        for start, end, text in headings:
            if start <= pos < end:
                return text, True
            if start < pos:
                current = text
            else:
                break
        return current, False

    chunks, buf, heading = [], '', ''

    def flush():
        # A paragraph longer than a chunk is split at sentence ends into several
        # chunks, each under its heading. It used to be cut at CHUNK_MAX, which lost
        # the end of twelve paragraphs (about 3,750 characters), among them the rules
        # that order an event's articles, so Tessa answered that her text "cuts off"
        # (2026-10-20).
        nonlocal buf
        body = buf.strip()
        buf = ''
        title = ', '.join(x for x in (page, heading) if x)
        prefix = f'{title}: ' if title else ''
        if len((prefix + body).strip(': ')) < 60:
            return
        room = max(CHUNK_MAX - len(prefix), 200)
        pieces, cur = [], ''
        for sent in re.split(r'(?<=[.!?])\s+', body):
            if cur and len(cur) + 1 + len(sent) > room:
                pieces.append(cur)
                cur = sent
            else:
                cur = f'{cur} {sent}'.strip()
        if cur:
            pieces.append(cur)
        for piece in pieces:
            chunks.append((prefix + piece)[:CHUNK_MAX])

    # Text between tags, and also a short bold label such as <strong>Scholarship</strong>:
    # it names the feature the paragraph describes, and at under twelve
    # characters it was being dropped (so the Scholarship tab's paragraph never
    # said "Scholarship" and no question about it could find it).
    fragment_re = re.compile(r'(?:(?<=<strong>)([^<>{}]{3,})|>([^<>{}]{12,}))(?=<)')
    if page:
        # A data list entry { file: ..., name: 'Window Texts', note: '...' } reads as
        # "Window Texts: ..." so a note is never separated from what it describes.
        src = re.sub(r"name:\s*'([^'\n]+)',\s*note:\s*'([^'\n]+)'",
                     lambda m: '>Data file ' + m.group(1) + ': ' + m.group(2) + '.<', src)
        # The other pages keep much of their prose in JavaScript strings (the
        # Downloads page lists every release, its size and license that way), so
        # a quoted string of a sentence's length counts as a fragment too. CSS
        # class lists and paths are left out.
        fragment_re = re.compile(r"(?:(?<=<strong>)([^<>{}]{3,})|>([^<>{}]{12,}))(?=<)"
                                 r"|'([^'\n]{40,})'|\"([^\"\n]{40,})\"")
    for m in fragment_re.finditer(src):
        raw = next((g for g in m.groups() if g), '')
        if m.lastindex and m.lastindex >= 3 and (re.search(r'\b(px|py|bg|flex|text|rounded|hover|border)-', raw)
                                                  or raw.startswith(('/', 'http')) or ' ' not in raw):
            continue
        t = ' '.join(html.unescape(raw).split())
        if not t or t.startswith('//') or re.fullmatch(r'[\s{}();,.\-–—|]+', t):
            continue
        own, inside = heading_at(m.start())
        if inside:
            continue                        # the heading's own words
        if own != heading:
            flush()
            heading = own
        buf = f'{buf} {t}'.strip() if buf else t
        if len(buf) >= CHUNK_MIN:
            flush()
    flush()

    seen, out = set(), []
    for c in chunks:
        key = c[:120].lower()
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _load():
    """Chunks, from the cache when the Help page has not changed since."""
    global _chunks
    if _chunks is not None:
        return _chunks
    with _lock:
        if _chunks is not None:
            return _chunks
        stamp = None
        try:
            stamp = '|'.join(str(os.path.getmtime(p)) for p in [HELP_SOURCE] + [p for p, _ in OTHER_SOURCES]
                             if os.path.exists(p))
        except OSError:
            pass
        try:
            with open(CACHE_PATH, encoding='utf-8') as fh:
                cached = json.load(fh)
            if (stamp and cached.get('source_mtime') == stamp
                    and cached.get('extractor') == EXTRACTOR_VERSION):
                _chunks = cached.get('chunks') or []
                return _chunks
        except (OSError, ValueError):
            pass

        _chunks = _extract()
        for path, label in OTHER_SOURCES:
            if os.path.exists(path):
                _chunks += _extract(path, page=label)
        try:
            os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
            with open(CACHE_PATH, 'w', encoding='utf-8') as fh:
                json.dump({'source_mtime': stamp, 'extractor': EXTRACTOR_VERSION,
                           'chunks': _chunks}, fh)
        except OSError as e:
            logger.info('[HELP] could not cache chunks: %s', e)
        return _chunks


def _stem(w):
    """A word without a common English ending, so "edition" meets "editions" and
    "rated" meets "rating" (2026-10-21: both questions missed the section that
    answered them)."""
    for suffix in ('ings', 'ing', 'ed', 'es', 's'):
        if w.endswith(suffix) and len(w) - len(suffix) >= 3 and not w.endswith('ss'):
            return w[:-len(suffix)]
    return w


def _words(text):
    return {_stem(w) for w in re.findall(r'[a-z]{3,}', str(text or '').lower())
            if w not in _STOP}


def _scored(question):
    """The Help sections most likely to answer this question.

    Scored on shared vocabulary, which works better here than it would in
    general: a reader asking about the site uses the site's own words -- theme
    search, lemma, export, reader, corpus -- and those are exactly the words the
    Help page uses back.
    """
    chunks = _load()
    if not chunks:
        return []
    want = _words(question)
    if not want:
        return []
    # A word found in few sections says more than one found everywhere:
    # "tab" is in dozens of sections and "scholarship" in three, so the
    # Scholarship paragraph lost to any section that said "tab" twice.
    have_by_chunk = [_words(c) for c in chunks]
    doc_freq = {}
    for have in have_by_chunk:
        for w in have:
            doc_freq[w] = doc_freq.get(w, 0) + 1
    scored = []
    for i, (c, have) in enumerate(zip(chunks, have_by_chunk)):
        overlap = want & have
        if not overlap:
            continue
        weight = sum(math.log(1 + len(chunks) / doc_freq[w]) ** 2 for w in overlap)
        # Favour density as well as count, so a short precise section beats a
        # long one that happens to mention everything.
        score = weight + len(overlap) / max(len(have), 1)
        # A section whose HEADING carries the question's words is about the
        # thing asked, so its heading words count twice over (2026-10-11: the
        # Reader's Scholarship paragraph kept losing to every new section that
        # mentioned scholarship once).
        title = c.split(':', 1)[0] if ':' in c else ''
        title_overlap = want & _words(title)
        score += 2 * sum(math.log(1 + len(chunks) / doc_freq[w]) ** 2 for w in title_overlap)
        scored.append((score, i))
    return scored


def relevant(question, k=4):
    """The k Help chunks most likely to answer this question, best first."""
    chunks = _load()
    scored = sorted(_scored(question), key=lambda kv: -kv[0])
    return [chunks[i] for _, i in scored[:k]]


def _title(chunk):
    return chunk.split(': ', 1)[0] if ': ' in chunk else ''


SECTION_BUDGET = 9000     # characters of site text per question, in all
SECTION_MAX = 2600        # characters from any one section
SECTIONS_MAX = 7


def sections_for(question):
    """Whole sections around the best-scoring chunks, best section first.

    Four chunks of at most 900 characters each left Tessa without the
    sentence she needed for a third of twelve ordinary questions (2026-10-21):
    the chunk that matched the question's words was often the one beside the
    answer. A section is the run of consecutive chunks under one heading. Each
    chosen section is given whole when short, and otherwise as its best chunks
    with their neighbours, in page order. The answering model is hosted, so the
    few thousand extra characters cost a second at most.
    """
    chunks = _load()
    scored = _scored(question)
    if not scored:
        return []
    best = {}
    for score, i in scored:
        best[i] = score
    # Contiguous runs of one title.
    runs, start = [], 0
    for i in range(1, len(chunks) + 1):
        if i == len(chunks) or _title(chunks[i]) != _title(chunks[start]):
            runs.append((start, i))
            start = i
    ranked = []
    for a, b in runs:
        scores = sorted((best[i] for i in range(a, b) if i in best), reverse=True)
        if scores:
            ranked.append((scores[0] + 0.3 * (scores[1] if len(scores) > 1 else 0), a, b))
    ranked.sort(key=lambda r: -r[0])
    out, used = [], 0
    for _, a, b in ranked[:SECTIONS_MAX]:
        if used >= SECTION_BUDGET:
            break
        room = min(SECTION_MAX, SECTION_BUDGET - used)
        idx = list(range(a, b))
        if sum(len(chunks[i]) for i in idx) > room:
            keep = set()
            for i in sorted((i for i in idx if i in best), key=lambda i: -best[i]):
                for j in (i, i - 1, i + 1):
                    if a <= j < b and j not in keep and sum(len(chunks[k]) for k in keep) + len(chunks[j]) <= room:
                        keep.add(j)
            idx = sorted(keep) or [max((i for i in idx if i in best), key=lambda i: best[i])]
        title = _title(chunks[idx[0]])
        body = ' '.join(chunks[i][len(title) + 2:] if title else chunks[i] for i in idx)
        text = f'{title}: {body}' if title else body
        out.append(text)
        used += len(text)
    return out


def direct_answer(question, threshold=0.75):
    """The Help page's own answer, when the question IS one of its headings.

    The Help page is written as questions and answers -- "How do I save my
    results?", "Why is my search taking so long?" -- so for those the model was
    being asked to paraphrase a good answer into a worse one, at seven to
    fourteen seconds a time on this CPU. Where the reader has asked the page's
    own question, the page's own answer is better and instant.

    Deliberately strict, and the threshold is measured rather than guessed. At
    0.6 "What is the difference between lemma and exact search?" was answered
    with the Phrases-versus-Lines section: three shared words out of five
    ("difference", "between", "search") were enough, and the reply was wrong,
    confident and in the site's own voice. At 0.75 every one of the seven real
    FAQ questions still matches and none of the five near misses does.

    A heading that is not itself a question is never used this way.
    """
    want = _words(question)
    if not want:
        return None
    best, best_score = None, 0.0
    for c in _load():
        head, _, body = c.partition(': ')
        if not body or '?' not in head:
            continue
        have = _words(head)
        if not have:
            continue
        overlap = want & have
        # Both directions: the question must cover the heading AND the heading
        # must cover the question, or "how do I save my results" would answer
        # "how do I save my results as a chart".
        score = min(len(overlap) / len(have), len(overlap) / len(want))
        if score > best_score:
            best, best_score = body.strip(), score
    return best if best_score >= threshold else None


def context_for(question, k=4):
    """The site's own pages as a prompt block, or '' when nothing matches."""
    hits = sections_for(question)
    if not hits:
        return ''
    body = '\n\n'.join(f'- {h}' for h in hits)
    return ('FROM THE TESSERAE SITE PAGES (Help unless another page is named; these are the facts '
            'about this site. Answer from them and do not invent features. Where they describe a '
            'feature, label or page, it exists: never say it does not. Where they answer only part '
            'of the question, give that part and name the page that holds the rest when they name '
            'one):\n' + body)


def status():
    return {'chunks': len(_load()), 'source': HELP_SOURCE}
