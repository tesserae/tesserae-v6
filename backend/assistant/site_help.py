"""What the site does, taken from the Help page rather than written out again.

WHY

Tessa's guide half knew about the SEARCHES and nothing else. It had never heard
of the Reader or Theme Search, so "how do I read the Aeneid?" fell through to a
corpus listing, and every gap got closed by adding another keyword to another
tuple in agent.py. NC, correctly: "Is this thing so dumb that we really have to
preprogram every response? It won't be enough to just feed it the help Page?"

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
import json
import os
import re
import threading

from backend.logging_config import get_logger

logger = get_logger('assistant.site_help')

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HELP_SOURCE = os.path.join(_ROOT, 'client', 'src', 'components', 'pages', 'HelpPage.jsx')
CACHE_PATH = os.path.join(_ROOT, 'cache', 'site_help_chunks.json')

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
}


def _extract(source=None):
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
    heading_re = re.compile(r'<(h[1-6])\b[^>]*>(.*?)</\1>', re.S)
    headings = []          # (start, end, text)
    for m in heading_re.finditer(src):
        inner = ' '.join(re.sub(r'<[^>]+>', ' ', m.group(2)).split())
        inner = re.sub(r'\{[^{}]*\}', '', inner).strip()
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
        nonlocal buf
        text = f'{heading}: {buf}'.strip() if heading else buf.strip()
        if len(text.strip(': ')) >= 60:
            chunks.append(text[:CHUNK_MAX])
        buf = ''

    for m in re.finditer(r'>([^<>{}]{12,})(?=<)', src):
        t = ' '.join((m.group(1) or '').split())
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
            stamp = os.path.getmtime(HELP_SOURCE)
        except OSError:
            pass
        try:
            with open(CACHE_PATH, encoding='utf-8') as fh:
                cached = json.load(fh)
            if stamp and cached.get('source_mtime') == stamp:
                _chunks = cached.get('chunks') or []
                return _chunks
        except (OSError, ValueError):
            pass

        _chunks = _extract()
        try:
            os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
            with open(CACHE_PATH, 'w', encoding='utf-8') as fh:
                json.dump({'source_mtime': stamp, 'chunks': _chunks}, fh)
        except OSError as e:
            logger.info('[HELP] could not cache chunks: %s', e)
        return _chunks


def _words(text):
    return {w for w in re.findall(r'[a-z]{3,}', str(text or '').lower())
            if w not in _STOP}


def relevant(question, k=4):
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
    scored = []
    for c in chunks:
        have = _words(c)
        overlap = want & have
        if not overlap:
            continue
        # Favour density as well as count, so a short precise section beats a
        # long one that happens to mention everything.
        score = len(overlap) + len(overlap) / max(len(have), 1)
        scored.append((score, c))
    scored.sort(key=lambda kv: -kv[0])
    return [c for _, c in scored[:k]]


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
    """The Help sections as a prompt block, or '' when nothing matches."""
    hits = relevant(question, k=k)
    if not hits:
        return ''
    body = '\n\n'.join(f'- {h}' for h in hits)
    return ('FROM THE TESSERAE HELP PAGE (these are the facts about this site; '
            'answer from them and do not invent features):\n' + body)


def status():
    return {'chunks': len(_load()), 'source': HELP_SOURCE}
