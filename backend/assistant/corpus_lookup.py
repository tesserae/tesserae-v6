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


def _has_word(haystack, needle):
    """Whole words only.

    This was a plain substring test, so "rest" matched Euripides' ORESTES: the
    sentence "the Reader shows it with its connections to the rest of the
    corpus" resolved to two texts, and anything relying on how many texts a
    sentence names was wrong. Any question containing "rest", "arms", "one" and
    so on could pick up a work nobody mentioned.
    """
    if not needle:
        return False
    return re.search(rf'\b{re.escape(needle)}\b', haystack or '') is not None


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
        elif all(_has_word(f'{akey} {wkey}', w) for w in words):
            score = 80
        elif q and _has_word(title, q):
            score = 70
        elif words[0] in (akey, author):
            extra = sum(6 for w in words[1:] if _has_word(f'{title} {wkey}', w))
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


def book_of(row, number):
    """The named book of a work, when the corpus holds books separately.

    A reader who writes "Thebaid 12" means book 12, and the corpus has it as
    statius.thebaid.part.12. Answering with the whole Thebaid instead quietly
    widens the question by twelve times.
    """
    if not row or not number:
        return None
    base = str(row.get('id') or '').replace('.tess', '').split('.part.')[0]
    want = f'{base}.part.{int(number)}'
    for r in _all_texts(row.get('language')):
        if str(r.get('id') or '').replace('.tess', '') == want:
            return dict(r, matched='work')
    return None


def named_texts(question, language=None, limit=2):
    """Texts a question appears to name, in the order they are mentioned.

    Scans capitalised words and known author keys, because a reader writes
    "echoes of Vergil in Statius" rather than a pair of ids. A book number
    following a name is honoured: "Thebaid 12" is book 12, not the whole poem.
    """
    found, seen, authors_used = [], set(), set()

    def take(hit):
        """Keep a hit unless it merely re-resolves a name already used.

        "what about Statius Thebaid?" produced TWO texts: statius.thebaid from
        the capitalised run, then statius.SILVAE from the bare word "statius"
        further down. The second is not another text the reader named, it is the
        same name resolved a second time and worse -- and it made a
        one-text question look ambiguous everywhere that counts hits.
        """
        if not hit or hit.get('id') in seen:
            return False
        author = str(hit.get('author') or '').lower()
        if hit.get('matched') == 'author' and author in authors_used:
            return False
        seen.add(hit['id'])
        if author:
            authors_used.add(author)
        found.append(hit)
        return True

    # Capitalised runs first, each with any book number that follows it:
    # "Silius Italicus", "Statius Thebaid 12".
    for cand, num in re.findall(
            r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s*(\d{1,2})?\b', question or ''):
        if _norm(cand) in _NOISE:
            continue
        hit = resolve_one(cand, language=language)
        if hit and num:
            hit = book_of(hit, num) or hit
        take(hit)
        if len(found) >= limit:
            return found
    # Then bare lowercase words, for "compare vergil and ovid".
    for w in _norm(question).split():
        if w in _NOISE or len(w) < 4:
            continue
        take(resolve_one(w, language=language))
        if len(found) >= limit:
            break
    return found


def is_text_id(text_id):
    """Whether the corpus really holds this id.

    Text ids that reach `actions` are not all equal. Those recorded by the
    phrase search come from arguments the site itself accepted. Those recorded
    by rare_words were CHOSEN BY THE MODEL, and it chooses badly: asked about
    echoes of Vergil in Statius it produced "Vergil_Aeneid" and "Statius_Thebaid",
    neither of which exists, and a compare link built from them went nowhere.

    So an id from a model-chosen search is checked here before it becomes a link.
    """
    if not text_id:
        return False
    want = str(text_id).replace('.tess', '').strip().lower()
    if not want:
        return False
    for r in _all_texts(None):
        if str(r.get('id') or '').replace('.tess', '').lower() == want:
            return True
    return False
