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

    fragments = []
    for raw in re.findall(r'>([^<>{}]{12,})<', src):
        t = ' '.join(raw.split())
        if not t or t.startswith('//'):
            continue
        if re.fullmatch(r'[\s{}();,.\-–—|]+', t):
            continue
        fragments.append(t)

    chunks, buf = [], ''
    for t in fragments:
        buf = f'{buf} {t}'.strip() if buf else t
        if len(buf) >= CHUNK_MIN:
            chunks.append(buf[:CHUNK_MAX])
            buf = ''
    if len(buf) >= 60:
        chunks.append(buf)

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
