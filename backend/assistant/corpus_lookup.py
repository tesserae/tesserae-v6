"""Turn a name a reader typed into a text the corpus actually holds.

The guide half of Tessa recommends a search for a question where nothing has
been searched yet: "how do I find echoes of Vergil in Statius?". To offer that
as a control rather than as advice, the words "Vergil" and "Statius" have to
become real text ids, and they have to become the RIGHT ones or the link is a
lie.

So matching is deliberately conservative and ranked, never fuzzy:

    exact author key            vergil          -> vergil.aeneid
    author and work together    statius thebaid -> statius.thebaid
    a distinctive work title    aeneid          -> vergil.aeneid

A name that matches nothing returns nothing, and the guide then says what it can
in words instead of offering a link that goes somewhere wrong.

The listing is fetched once per language and kept, because it is 1,826 rows for
Latin alone and this runs on every guide question.
"""
import re
import threading

from backend.assistant import searches
from backend.logging_config import get_logger

logger = get_logger('assistant.corpus_lookup')

_lock = threading.Lock()
_texts = {}          # language -> list[row]

LANGUAGES = ('la', 'grc', 'he', 'cop', 'en')

# Words that are never part of a name, so a question can be scanned for one.
_NOISE = {
    'the', 'a', 'an', 'and', 'or', 'of', 'in', 'on', 'to', 'from', 'with',
    'how', 'do', 'does', 'did', 'can', 'could', 'would', 'should', 'i', 'you',
    'we', 'find', 'search', 'compare', 'comparing', 'compared', 'between',
    'against', 'echoes', 'echo', 'borrowings', 'borrowing', 'parallels',
    'parallel', 'allusions', 'allusion', 'influence', 'imitation', 'reuse',
    'passages', 'passage', 'lines', 'line', 'text', 'texts', 'work', 'works',
    'book', 'books', 'poem', 'show', 'me', 'my', 'is', 'are', 'was', 'were',
    'what', 'which', 'where', 'who', 'about', 'for', 'any', 'some', 'that',
    'this', 'there', 'their', 'his', 'her', 'its', 'latin', 'greek', 'hebrew',
    'coptic', 'english', 'want', 'like', 'looking', 'look', 'get', 'see',
    'read', 'reading', 'corpus', 'tesserae', 'please', 'thanks', 'similar',
}


def _all_texts(language=None):
    langs = [language] if language else list(LANGUAGES)
    out = []
    for code in langs:
        with _lock:
            rows = _texts.get(code)
        if rows is None:
            try:
                rows = searches.run('list_texts', {'language': code})
            except Exception as e:                      # noqa: BLE001
                logger.info('[GUIDE] could not list %s: %s', code, e)
                rows = []
            rows = rows if isinstance(rows, list) else []
            with _lock:
                _texts[code] = rows
        out += rows
    return out


def _norm(s):
    return re.sub(r'[^a-z0-9 ]+', ' ', str(s or '').lower()).strip()


def find_texts(name, language=None, limit=5):
    """Texts whose author or title matches `name`, best first.

    Ranked rather than filtered, so "vergil" prefers the Aeneid over a work that
    merely mentions him, and an unmatched name yields nothing at all.
    """
    q = _norm(name)
    if len(q) < 3:
        return []
    words = [w for w in q.split() if w not in _NOISE]
    if not words:
        return []

    scored = []
    for r in _all_texts(language):
        author = _norm(r.get('author'))
        akey = _norm(r.get('author_key'))
        title = _norm(r.get('title') or r.get('work'))
        wkey = _norm(r.get('work_key'))
        score, how = 0, 'work'
        if q == akey or q == author:
            # ONLY the author was named. Which of their works they meant is not
            # knowable, and guessing it is how "Statius" became the Silvae and
            # "Ovid" became the Ibis, both decided by an id-length tiebreak. The
            # site can search by author, so say so and let it.
            score, how = 100, 'author'
        elif all(w in f'{akey} {wkey}' for w in words):
            score = 80
        elif q and q in title:
            score = 70
        elif words[0] in (akey, author):
            extra = sum(6 for w in words[1:] if w in f'{title} {wkey}')
            score = 50 + extra
            if not extra:
                how = 'author'
        if not score:
            continue
        # Prefer a whole work over one of its books, and something substantial.
        if r.get('is_part'):
            score -= 12
        scored.append((score, dict(r, matched=how)))
    scored.sort(key=lambda kv: (-kv[0], len(str(kv[1].get('id') or ''))))
    return [r for _, r in scored[:limit]]


def resolve_one(name, language=None):
    """A single best text id for a name, or None if nothing matches well."""
    hits = find_texts(name, language=language, limit=1)
    return hits[0] if hits else None


def named_texts(question, language=None, limit=2):
    """Texts a question appears to name, in the order they are mentioned.

    Scans capitalised words and known author keys, because a reader writes
    "echoes of Vergil in Statius" rather than a pair of ids.
    """
    found, seen = [], set()
    # Capitalised runs first: "Silius Italicus", "Valerius Flaccus".
    for cand in re.findall(r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?', question or ''):
        if _norm(cand) in _NOISE:
            continue
        hit = resolve_one(cand, language=language)
        if hit and hit.get('id') not in seen:
            seen.add(hit['id'])
            found.append(hit)
        if len(found) >= limit:
            return found
    # Then bare lowercase words, for "compare vergil and ovid".
    for w in _norm(question).split():
        if w in _NOISE or len(w) < 4:
            continue
        hit = resolve_one(w, language=language)
        if hit and hit.get('id') not in seen:
            seen.add(hit['id'])
            found.append(hit)
        if len(found) >= limit:
            break
    return found
