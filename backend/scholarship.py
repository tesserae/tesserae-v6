"""Secondary scholarship on a passage, from open sources only.

What this module does, and what it deliberately does not do. It asks the
open scholarly metadata services (OpenAlex, then Crossref) for articles,
chapters and books whose title or abstract cite a passage or a pair of
passages, asks Unpaywall for a legal open copy of each, and reads the
public-domain commentaries the site holds (data/commentaries/). It never
fetches subscription content: a reader reaches an article through the DOI
or through their own library's link resolver, in their own browser.

Requests are cached on disk for thirty days (cache/scholarship/), one
request per distinct query, because the services ask for restraint and the
literature changes slowly. Every request carries the project's contact
address, which is what the services ask of a polite client.
"""
import glob
import hashlib
import html
import json
import logging
import math
import os
import re
import time

import requests

from backend import scripture
from backend import citations
from backend.utils import format_short_locus, get_text_metadata
from backend.work_names import base_work

logger = logging.getLogger(__name__)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, 'cache', 'scholarship')
COMMENTARY_DIR = os.path.join(ROOT, 'data', 'commentaries')
CONTACT = os.environ.get('TESSERAE_CONTACT_EMAIL', 'ncoffee@buffalo.edu')
TTL = 30 * 24 * 3600
TIMEOUT = 20
UA = f'Tesserae V6 (https://tesserae.caset.buffalo.edu; mailto:{CONTACT})'

# ---------------------------------------------------------------- caching

def _cached(key, fn):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, hashlib.md5(key.encode('utf-8')).hexdigest() + '.json')  # nosec B324
    try:
        if os.path.exists(path) and time.time() - os.path.getmtime(path) < TTL:
            with open(path, encoding='utf-8') as fh:
                return json.load(fh)
    except (OSError, ValueError):
        pass
    value = fn()
    try:
        tmp = f'{path}.{os.getpid()}.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(value, fh, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError as e:
        logger.warning('scholarship cache not written: %s', e)
    return value


def _get(url, params):
    r = requests.get(url, params=params, timeout=TIMEOUT, headers={'User-Agent': UA, 'Accept': 'application/json'})
    r.raise_for_status()
    return r.json()

# ------------------------------------------------------- naming a passage

def passage_names(work, ref_start, ref_end=None):
    """The ways scholars write this passage, for searching: ("Vergil", "Aeneid",
    "Aen.", "1.1", "1.1-12"). Author and title come from the site's metadata;
    the short title from the line tag's abbreviation ("verg. aen. 1.1" -> "Aen.")."""
    work = (work or '').replace('.tess', '')
    base = base_work(work)
    # Scripture is cited by book, chapter and verse whatever the version, and
    # the same citation serves the Hebrew, the Greek, the Coptic and the
    # English of one verse (backend/scripture.py).
    c1 = scripture.canonical(work, ref_start)
    if c1:
        c2 = scripture.canonical(work, ref_end) if ref_end else None
        v2 = c2['verse'] if c2 and c2['chapter'] == c1['chapter'] else None
        full, short = scripture.citation(c1['book'], c1['chapter'], c1['verse'], v2)
        lo = f"{c1['chapter']}:{c1['verse']}" if c1['verse'] else str(c1['chapter'])
        hi = f"{c2['chapter']}:{c2['verse']}" if c2 and c2['verse'] else lo
        return {'work': base, 'author': '', 'title': full.rsplit(' ', 1)[0], 'abbrev': short.rsplit(' ', 1)[0],
                'locus': full.rsplit(' ', 1)[1], 'lo': lo, 'hi': hi, 'scripture': c1, 'scripture_end': c2}
    try:
        m = get_text_metadata(f'{base}.tess') or {}
    except Exception:
        m = {}
    author = (m.get('author') or base.split('.')[0].replace('_', ' ').title()).strip()
    title = (m.get('title') or m.get('work') or base.split('.')[-1].replace('_', ' ').title()).strip()
    lo = format_short_locus(ref_start or '')
    hi = format_short_locus(ref_end or '') if ref_end else ''
    locus = lo if not hi or hi == lo else f'{lo}-{hi.split(".")[-1] if hi.split(".")[:-1] == lo.split(".")[:-1] else hi}'
    words = [w for w in re.split(r'\s+', (ref_start or '').strip()) if w and not re.match(r'^[\d.\-]+$', w)]
    abbrev = words[-1].capitalize() if words else title
    return {'work': base, 'author': author, 'title': title, 'abbrev': abbrev, 'locus': locus, 'lo': lo, 'hi': hi or lo}


def _queries(a, b=None):
    """Search strings, most specific first: both passages, both works, one passage."""
    q = []
    if b:
        q.append((1, f'{a["author"]} {a["title"]} {a["locus"]} {b["author"]} {b["title"]} {b["locus"]}'))
        q.append((1, f'{a["abbrev"]} {a["locus"]} {b["abbrev"]} {b["locus"]}'))
        q.append((2, f'{a["author"]} {a["title"]} {b["author"]} {b["title"]}'))
    q.append((3, f'{a["author"]} {a["title"]} {a["locus"]}'))
    q.append((3, f'{a["abbrev"]} {a["locus"]}'))
    return q

# ------------------------------------------------------------- services

def _openalex(query):
    def run():
        d = _get('https://api.openalex.org/works', {'search': query, 'per-page': 15, 'mailto': CONTACT})
        out = []
        for w in d.get('results', []):
            inv = w.get('abstract_inverted_index') or {}
            abstract = ''
            if inv:
                pos = {}
                for word, idxs in inv.items():
                    for i in idxs:
                        pos[i] = word
                abstract = ' '.join(pos[i] for i in sorted(pos))
            loc = w.get('primary_location') or {}
            src = (loc.get('source') or {}).get('display_name')
            out.append({
                'title': w.get('title') or '',
                'authors': [x.get('author', {}).get('display_name') for x in (w.get('authorships') or [])][:6],
                'year': w.get('publication_year'),
                'venue': src,
                'type': w.get('type'),
                'doi': (w.get('doi') or '').replace('https://doi.org/', '') or None,
                'oa_url': (w.get('open_access') or {}).get('oa_url'),
                'cited_by': w.get('cited_by_count') or 0,
                'abstract': abstract,
                'source': 'openalex',
            })
        return out
    return _cached('openalex|' + query, run)


def _crossref(query):
    def run():
        d = _get('https://api.crossref.org/works', {'query.bibliographic': query, 'rows': 10, 'mailto': CONTACT})
        out = []
        for w in (d.get('message') or {}).get('items', []):
            year = None
            for k in ('published-print', 'published-online', 'issued'):
                parts = (w.get(k) or {}).get('date-parts') or []
                if parts and parts[0]:
                    year = parts[0][0]; break
            out.append({
                'title': (w.get('title') or [''])[0],
                'authors': [' '.join(x for x in (p.get('given'), p.get('family')) if x) for p in (w.get('author') or [])][:6],
                'year': year,
                'venue': (w.get('container-title') or [None])[0],
                'type': w.get('type'),
                'doi': w.get('DOI'),
                'oa_url': None,
                'cited_by': w.get('is-referenced-by-count') or 0,
                'abstract': re.sub(r'<[^>]+>', '', w.get('abstract') or ''),
                'source': 'crossref',
            })
        return out
    return _cached('crossref|' + query, run)


def _unpaywall(doi):
    def run():
        try:
            d = _get(f'https://api.unpaywall.org/v2/{doi}', {'email': CONTACT})
        except requests.RequestException:
            return {}
        best = d.get('best_oa_location') or {}
        return {'oa_url': best.get('url_for_pdf') or best.get('url'), 'is_oa': bool(d.get('is_oa'))}
    return _cached('unpaywall|' + doi, run)

# --------------------------------------------------------------- ranking

def _cap_words(text, max_chars=400, include=None):
    """text capped near max_chars, but never inside a word: extended to the
    end of the word that straddles the cap, or (when that word runs on
    unreasonably long, e.g. no nearby space at all) cut back to the last
    space before the cap. A snippet that ends mid-word ("...advorsando
    Sti") reads as broken.

    include, when given, is the citation surface this snippet is meant to
    show: the cap is pushed out to clear it first, so the very thing being
    bolded is never the part cut away (a truncated snippet used to hide its
    own citation, leaving "cites Stich. 1" attached to a sentence that,
    once cut, no longer showed a "1" anywhere)."""
    text = (text or '').strip()
    if include:
        i = text.lower().find(re.sub(r'\s+', ' ', include).strip().lower())
        if i >= 0:
            max_chars = max(max_chars, i + len(include) + 20)
    if len(text) <= max_chars:
        return text
    m = re.compile(r'\S*').match(text, max_chars)
    end = m.end() if m else max_chars
    if end - max_chars > 40:
        cut = text.rfind(' ', 0, max_chars)
        end = cut if cut > 0 else max_chars
    return text[:end].rstrip()


def _sentence_with(text, needles):
    for s in re.split(r'(?<=[.!?])\s+', text or ''):
        low = s.lower()
        if any(n.lower() in low for n in needles if n):
            return _cap_words(s)
    return None


def _names(p):
    """The words that show a text is about this work: the author, the title
    (and its first word, so "Bellum Civile (Pharsalia)" also matches "Pharsalia"
    or "Bellum Civile"), and the tag abbreviation with its period."""
    out = {p['author'], p['title'], p['abbrev']}
    for part in re.split(r'[()]', p['title']):
        part = part.strip()
        if len(part) > 3:
            out.add(part)
    return {n.lower() for n in out if n and len(n) > 2}


REVIEW_AGGREGATOR_VENUES = {
    'choice reviews online', 'choice', 'kirkus reviews', 'kirkus', 'publishers weekly', 'booklist',
    'library journal', 'the booklist',
}


def _is_review_aggregator(item):
    """An unsigned capsule review, not a piece of scholarship: no author,
    and a venue that publishes only short book-notice reviews. "Choice
    Reviews Online" capsules on a book named "Aristophanes: myth, ritual
    and comedy" matched this work by author name alone."""
    if item.get('authors'):
        return False
    venue = (item.get('venue') or '').strip().lower()
    return venue in REVIEW_AGGREGATOR_VENUES


def _locus_anchor_names(p):
    """Names that may anchor a citation's locus: the title, its abbreviation,
    and its parenthetical alternatives -- not the bare author name alone.
    "Aristophanes ... 1" next to a stray page or footnote number is not a
    citation of a passage; "Ach. 1" or "Acharnians 1" is."""
    author = (p.get('author') or '').strip().lower()
    return {n for n in _names(p) if n != author}

# --------------------------------------------- titles shared by more than
# one author ("Argonautica": Apollonius Rhodius and Valerius Flaccus;
# "Metamorphoses": Ovid and Apuleius). A bare title match is not enough for
# one of these: a citation of "Argonautica 1.5-17" names Apollonius Rhodius
# only where an Apollonius signal (his name, or "A.R.") sits near the match,
# and not where a competing author of the same title (Valerius, "Val. Fl.")
# sits there instead. Built once per process from the corpus file list
# (texts/, each file's display author and work title after the overrides
# that give one author one canonical name), never from a per-article guess.

_SHARED_TITLES = None


def _load_shared_titles():
    """{title.lower(): {author_key: {'author': display name, 'work': base_work}}}
    for every title held by more than one author_key in the corpus."""
    global _SHARED_TITLES
    if _SHARED_TITLES is not None:
        return _SHARED_TITLES
    groups = {}
    for fp in glob.glob(os.path.join(ROOT, 'texts', '*', '*.tess')):
        try:
            m = get_text_metadata(fp)
        except Exception:
            continue
        title = (m.get('work') or '').strip().lower()
        akey = m.get('author_key')
        if not title or not akey or title == 'unknown' or len(title) < 4:
            continue
        g = groups.setdefault(title, {})
        if akey not in g:
            g[akey] = {'author': (m.get('author') or '').strip(), 'work': base_work(m['id'])}
    _SHARED_TITLES = {t: g for t, g in groups.items() if len(g) > 1}
    return _SHARED_TITLES


def _fuzzy_name_pattern(name):
    """A regex fragment for `name` that treats "A.R." and "A. R." (or
    "Val.Fl." and "Val. Fl.") as the same citation surface: every period may
    be followed by extra whitespace, every run of whitespace may be none,
    one, or more characters. The very last period is not allowed to eat the
    space after it, so the pattern's own end-of-name boundary still lands
    right after the dot, not past it."""
    out = []
    for ch in name:
        if ch == '.':
            out.append(r'\.\s*')
        elif ch.isspace():
            out.append(r'\s*')
        else:
            out.append(re.escape(ch))
    pat = ''.join(out)
    if pat.endswith(r'\.\s*'):
        pat = pat[:-len(r'\s*')]
    return pat


def _signal_regex(names):
    """One compiled, case-insensitive pattern matching any of `names` as a
    whole token (not inside a longer word), fuzzy on internal spacing -- or
    None if `names` is empty."""
    pats = sorted({_fuzzy_name_pattern(n.strip()) for n in names if n and len(n.strip()) > 1},
                  key=len, reverse=True)
    if not pats:
        return None
    return re.compile(r'(?<![A-Za-z])(?:' + '|'.join(pats) + r')(?![A-Za-z])', re.I)


def _author_signal_names(work, display_author):
    """Names and abbreviations that identify this work's author specifically:
    the display name from the filename, plus (where data/citations/
    abbreviations.json is present -- production, read-only; not every dev or
    test environment has it) its author_names and author_abbreviations, e.g.
    "Apollonius Rhodius", "Apollonius", "A. R." for apollonius_rhodius.argonautica."""
    names = {display_author} if display_author else set()
    idx = citations.index()
    if idx is not None:
        w = idx.works_by_base_id.get(work)
        if w:
            names.update(w.get('author_names') or [])
            names.update(w.get('author_abbreviations') or [])
    return names


def _work_abbrevs(idx, work):
    """Every citation-style short form data/citations/abbreviations.json
    carries for this base work: its native tag abbreviation, its combined
    and single abbreviations, its author abbreviation and its work
    abbreviation -- e.g. {"A.R.", "A. R."} for apollonius_rhodius.argonautica."""
    w = idx.works_by_base_id.get(work) if idx else None
    if not w:
        return set()
    out = set(w.get('abbreviations') or []) | set(w.get('author_abbreviations') or []) \
        | set(w.get('work_abbreviations') or [])
    if w.get('native_abbreviation'):
        out.add(w['native_abbreviation'])
    return {a for a in out if a}


_SHARED_TITLE_GUARD_WINDOW = 300


def _shared_title_guard(p):
    """None when p's title is not held by more than one author in the corpus
    (most works: nothing to guard), OR when data/citations/abbreviations.json
    is not loaded (dev and test environments, almost always -- the file is
    large and lives only on production, read-only). Without that table there
    is no reliable way to tell a real second author of the title from a
    corpus filing quirk (texts/la/maffeo_veggio.aeneid.tess duplicates his
    own "Supplementum" under a stray "Aeneid" title, which would otherwise
    make every plain Vergil citation start demanding "Vergil" by name), so
    the guard stays off rather than risk that. In production the table's own
    match_method marks exactly this: an 'unmatched' entry (no author_names,
    no work_titles -- never resolved to a real catalogue work) does not
    count as a second author and is dropped before anything else runs.

    Otherwise a dict:

    'disambiguating' -- a regex of citation abbreviations that belong to
    this work ALONE among the authors sharing the title ("A.R." for
    Apollonius Rhodius's Argonautica, never "Val. Fl."): a match on one of
    these already names the right author and needs no further check.

    'own' / 'competing' -- regexes of this author's / the other authors'
    names and remaining abbreviations, for a match made on the bare,
    ambiguous title or author name instead: 'own' must be found within
    _SHARED_TITLE_GUARD_WINDOW characters of that match, 'competing' must
    not be (a competing author's name there means the piece is about their
    copy of the title, not this one).

    Scripture passages (no 'author' field; the book/chapter/verse already
    disambiguates them) are never guarded."""
    if not p.get('author'):
        return None
    idx = citations.index()
    if idx is None:
        return None
    groups = _load_shared_titles().get((p.get('title') or '').strip().lower())
    if not groups:
        return None
    recognized = {k: info for k, info in groups.items()
                  if (idx.works_by_base_id.get(info['work']) or {}).get('match_method', 'unmatched') != 'unmatched'}
    if len(recognized) < 2 or p.get('work') not in {info['work'] for info in recognized.values()}:
        return None
    own_key = next(k for k, info in recognized.items() if info['work'] == p.get('work'))
    own_work = recognized[own_key]['work']
    own_abbrevs = _work_abbrevs(idx, own_work)
    competing_abbrevs = set()
    competing_names = set()
    for k, info in recognized.items():
        if k == own_key:
            continue
        competing_abbrevs |= _work_abbrevs(idx, info['work'])
        competing_names |= _author_signal_names(info['work'], info['author'])
    disambiguating = {a for a in own_abbrevs if a.lower() not in {c.lower() for c in competing_abbrevs}}
    own_names = _author_signal_names(own_work, recognized[own_key]['author']) | (own_abbrevs - disambiguating)
    return {
        'disambiguating': _signal_regex(disambiguating),
        'own': _signal_regex(own_names),
        'competing': _signal_regex(competing_names - own_names),
    }


def _signal_ok(text, start, end, guard):
    """True unless `guard` (see _shared_title_guard) says the match at
    text[start:end] belongs to a different author of the same title: a
    competing author's name/abbreviation within _SHARED_TITLE_GUARD_WINDOW
    characters rejects it; otherwise this author's own name/abbreviation
    within that window, including in the piece's own title field, is
    required. A piece titled "Apollonius Rhodius, Herodotus and
    Historiography" names its author in the very field being searched --
    that counts the same as a name next to the citation itself."""
    if guard is None:
        return True
    lo = max(0, start - _SHARED_TITLE_GUARD_WINDOW)
    hi = min(len(text), end + _SHARED_TITLE_GUARD_WINDOW)
    neighborhood = text[lo:hi]
    competing_re = guard['competing']
    if competing_re and competing_re.search(neighborhood):
        return False
    own_re = guard['own']
    return bool(own_re and own_re.search(neighborhood))


def _mentions_work(text, p):
    # The tag abbreviation ("aen.") counts only before a number: a rat heart
    # study came back for the Aeneid because it abbreviated its nettle extract
    # to "AEN." (2026-09-13).
    abbrev = (p.get('abbrev') or '').lower()
    guard = _shared_title_guard(p)
    if guard and guard['disambiguating']:
        if re.search(guard['disambiguating'].pattern + r'\s*\d', text, re.I):
            return True
    for n in _names(p):
        if n == abbrev:
            for m in re.finditer(re.escape(n) + r'\s*\d', text):
                if _signal_ok(text, m.start(), m.end(), guard):
                    return True
        elif n in text:
            start = 0
            while True:
                i = text.find(n, start)
                if i < 0:
                    break
                if _signal_ok(text, i, i + len(n), guard):
                    return True
                start = i + 1
    return False


def _locus_match(text, p):
    """The citation as written, e.g. "Aeneid 1.1-156", or None. The locus counts
    only next to the work's name: "Aen. 1.1", "Aeneid 1.1", "Vergil 1.1". A
    bare "1.1" in an abstract about anything at all is not a citation (a carbon
    budget and a sinus study came back for Lucan 1.1). When the title is one
    shared by more than one author, a citation abbreviation unique to this
    author ("A.R.") is accepted outright; a match on the bare, ambiguous
    title or author name also needs that author's own name or abbreviation
    nearby, and not a competing author of the same title (the Argonautica is
    Apollonius Rhodius's or Valerius Flaccus's; "Valerius Flaccus'
    Argonautica 1.5-21" is not a citation of the other one's passage just
    because it names the same title)."""
    lo = re.escape(p['lo']).replace(r'\:', '[.:]').replace(r'\.', '[.:]')
    guard = _shared_title_guard(p)
    if guard and guard['disambiguating']:
        m = re.search(guard['disambiguating'].pattern + r'[^.;]{0,40}?\b' + lo + r'\b(?:[-\u2013]\d+(?:[.:]\d+)*)?',
                       text, re.I)
        if m:
            return m.group(0)
    for n in sorted(_locus_anchor_names(p), key=len, reverse=True):
        for m in re.finditer(re.escape(n) + r'[^.;]{0,40}?\b' + lo + r'\b(?:[-\u2013]\d+(?:[.:]\d+)*)?', text, re.I):
            if _signal_ok(text, m.start(), m.end(), guard):
                return m.group(0)
    return None


def _cites_locus(text, p):
    return _locus_match(text, p) is not None


def _guard_abbrevs(text, p):
    # Same length as the text: an abbreviation's period becomes a one-dot
    # leader so sentence splitting does not stop at "Aen." or "Verg."
    guarded = text or ''
    for n in sorted(_names(p) | _stems(p), key=len, reverse=True):
        if n.endswith('.'):
            guarded = re.sub(re.escape(n), lambda m: m.group(0)[:-1] + '\u2024', guarded, flags=re.I)
    # Short capitalised abbreviations ("Verg.", "Od.") and Roman numerals
    # before a number ("i. 1") do not end sentences either.
    guarded = re.sub(r'\b([A-Z][a-z]{0,3})\.', lambda m: m.group(1) + '\u2024', guarded)
    return re.sub(r'\b([ivxlcIVXLC]{1,6})\.(?=\s*\d)', lambda m: m.group(1) + '\u2024', guarded)


def _stems(p):
    """Short forms a citation may use for the author or work: "Verg.",
    "Virg.", "A.", "Aen." for Vergil's Aeneid."""
    out = set()
    for n in (p.get('author') or '', p.get('title') or ''):
        n = n.lower()
        if len(n) >= 4:
            out.add(n[:4] + '.'); out.add(n[:3] + '.')
    ab = (p.get('abbrev') or '').lower()
    if ab:
        out.add(ab)
    return out

# --------------------------------------------------- locus depth labelling
# A citation found by the extractor carries a coordinate depth ("1" is an
# act; "1.1" an act and scene; "1.2.33" act, scene and line). When that
# depth is shallower than how this work is normally cited, the locus is a
# whole act or scene, not the specific line: said outright rather than
# shown as a bare, falsely precise number.

GENRE_LEVEL_NAMES = {
    'drama': ['act', 'scene', 'line'],
    'epic': ['book', 'line'],
}

_GENRE_BY_WORK = None
_WORK_DEPTH = None
_WORK_DEPTH_OVERRIDES = None


def _load_genres():
    global _GENRE_BY_WORK
    if _GENRE_BY_WORK is None:
        _GENRE_BY_WORK = {}
        try:
            import csv
            with open(os.path.join(ROOT, 'data', 'text_genres.csv'), encoding='utf-8') as fh:
                for row in csv.DictReader(fh):
                    fn = base_work(row.get('filename') or '')
                    if fn and row.get('genre'):
                        _GENRE_BY_WORK[fn] = row['genre']
        except OSError:
            pass
    return _GENRE_BY_WORK


def _load_work_depths():
    global _WORK_DEPTH, _WORK_DEPTH_OVERRIDES
    if _WORK_DEPTH is None:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'citations')
        try:
            with open(os.path.join(base, 'work_depth.json'), encoding='utf-8') as fh:
                _WORK_DEPTH = json.load(fh)
        except (OSError, ValueError):
            _WORK_DEPTH = {}
        try:
            with open(os.path.join(base, 'work_depth_overrides.json'), encoding='utf-8') as fh:
                _WORK_DEPTH_OVERRIDES = json.load(fh)
        except (OSError, ValueError):
            _WORK_DEPTH_OVERRIDES = {}
    return _WORK_DEPTH, _WORK_DEPTH_OVERRIDES


def _expected_depth(work):
    """How many coordinate levels a full citation of this work normally
    carries (the hand-curated override first, else the corpus norm)."""
    depth_map, overrides = _load_work_depths()
    base = base_work(work or '')
    if base in overrides:
        return overrides[base]
    return depth_map.get(base)


def _locus_depth_note(work, cs):
    """' (act and scene)', ' (book)', etc. when a citation's own coordinate
    is shallower than this work's normal citation depth -- else ''."""
    expected = _expected_depth(work)
    if not expected or not cs or len(cs) >= expected:
        return ''
    genre = _load_genres().get(base_work(work or ''))
    names = GENRE_LEVEL_NAMES.get(genre)
    if not names or len(names) < expected:
        return ''
    have = names[:len(cs)]
    return f' ({have[0]})' if len(have) == 1 else f' ({" and ".join(have)})'


def _cites_and_note(text, p):
    """(surface, depth note), the surface exactly as _cites(text, p) would
    return it, paired with the note for that same match -- never a note
    computed from a different hit than the surface shown."""
    m = _locus_match(text, p)
    if m:
        return m, ''
    hits = _citations_of(text, p)
    if hits:
        return hits[0]['surface'], _locus_depth_note(p.get('work'), hits[0].get('cs'))
    return None, ''


def _sentence_spans(text, p):
    guarded = _guard_abbrevs(text, p)
    spans, start = [], 0
    for m in re.finditer(r'(?<=[.!?])\s+', guarded):
        spans.append((start, m.start())); start = m.end()
    spans.append((start, len(guarded)))
    return spans


def _citations_of(text, p):
    """Citations of this passage found by the extractor: hits whose work is
    the passage's work and whose locus touches the selected span. Only
    sentences naming the work (or its abbreviation) are parsed, which keeps
    a 500,000-character article to a fraction of a second."""
    if not text or not p.get('work'):
        return []
    keys = [n for n in (_names(p) | _stems(p))]
    lo, hi = _coords(p['lo']), _coords(p['hi'])
    hits = []
    for a, b in _sentence_spans(text, p):
        sent = text[a:b]
        low = sent.lower()
        if not any(k in low for k in keys):
            continue
        for h in citations.extract(sent):
            if not h.get('resolved') or h.get('work_id') != p['work']:
                continue
            cs = _coords(h.get('locus_start') or '')
            ce = _coords(h.get('locus_end') or h.get('locus_start') or '')
            if not cs:
                continue
            if h.get('open_ended'):
                ce = ce[:1] + (10 ** 6,) if len(ce) > 1 else (10 ** 6,)
            # overlap of [cs, ce] with [lo, hi] on the common prefix length
            n = min(len(cs), len(lo))
            if cs[:n] <= hi[:n] and ce[:n] >= lo[:n]:
                hits.append({'surface': h['surface'], 'start': a + h['start'], 'end': a + h['end'],
                             'sentence': _cap_words(sent, include=h['surface']), 'cs': cs})
    return hits


def _cites(text, p):
    """The citation as written, by pattern or by the extractor, else None."""
    return _cites_and_note(text, p)[0]


def _sentences(text, p):
    # "Aen. 1.1" must not end a sentence at its own abbreviation.
    return [x.replace('\u2024', '.') for x in re.split(r'(?<=[.!?])\s+', _guard_abbrevs(text, p))]


def _citing_sentence(text, p, names):
    """The sentence that cites the passage, else the first that names the work."""
    for s in _sentences(text, p):
        m = _locus_match(s, p)
        if m:
            return _cap_words(s, include=m)
    hits = _citations_of(text, p)
    if hits:
        return hits[0]['sentence']
    return _sentence_with(text, names)


def _score(item, a, b):
    """(band, score), or (None, 0) for an item that never names the work."""
    if _is_review_aggregator(item):
        return None, 0
    text = f'{item.get("title", "")} {item.get("abstract", "")}'.lower()
    ma, mb = _mentions_work(text, a), (_mentions_work(text, b) if b else False)
    if not ma and not mb:
        return None, 0
    ca, cb = _cites_locus(text, a), (_cites_locus(text, b) if b else False)
    if b and ca and cb:
        band = 1
    elif b and ma and mb:
        band = 2
    elif ma:
        band = 3
    else:
        return None, 0
    score = 2 * (ca + cb) + (ma + mb) + 0.2 * math.log1p(item.get('cited_by') or 0)
    return band, score


def find(work, ref_start, ref_end=None, work2=None, ref2_start=None, ref2_end=None, limit=20, quote=None):
    """Articles, chapters and books on a passage (or a pair), ranked: both
    passages cited together first, then both works, then one passage."""
    a = passage_names(work, ref_start, ref_end)
    b = passage_names(work2, ref2_start, ref2_end) if work2 and ref2_start else None
    seen = {}
    for band, q in _queries(a, b):
        for src in (_openalex, _crossref):
            try:
                items = src(q)
            except requests.RequestException as e:
                logger.warning('scholarship lookup failed (%s): %s', q, e)
                continue
            for it in items:
                key = (it.get('doi') or it.get('title', '').lower()[:80])
                if not key or key in seen:
                    continue
                it['band'], it['score'] = _score(it, a, b)
                if it['band'] is None:
                    continue
                names = sorted(_names(a) | (_names(b) if b else set()), key=len, reverse=True)
                it['snippet'] = _citing_sentence(it.get('abstract'), a, names)
                # What the piece actually cites, shown in place of a vague label.
                it['cites'], it['cites_note'] = _cites_and_note(f"{it.get('title', '')} {it.get('abstract', '')}", a)
                it['cites2'], it['cites2_note'] = (_cites_and_note(f"{it.get('title', '')} {it.get('abstract', '')}", b)
                                                    if b else (None, ''))
                # A piece that names the work without citing the passage is
                # one of thousands and says nothing about these lines: dropped.
                # Pieces on both compared works stay.
                if it['band'] in (2, 3) and not it['cites']:
                    continue
                seen[key] = it
    ranked = sorted(seen.values(), key=lambda x: (x['band'], -x['score'], -(x.get('year') or 0)))[:limit]
    for it in ranked:
        if it.get('doi') and not it.get('oa_url'):
            it.update({k: v for k, v in _unpaywall(it['doi']).items() if v})
        it.pop('abstract', None)
    bk = books(a)
    bk['hathitrust_url'] = hathitrust_search_url(a)
    # For a verse of the Tanakh, the whole commentary tradition at that verse
    # is one link away at Sefaria (a link the reader follows, not a request).
    links = []
    sc = a.get('scripture')
    if sc and sc['book'] in scripture.TANAKH and sc.get('verse'):
        name = scripture.citation(sc['book'], sc['chapter'], sc['verse'])[0].rsplit(' ', 1)[0].replace(' ', '_')
        links.append({'label': 'All commentaries on this verse at Sefaria',
                      'url': f"https://www.sefaria.org/{name}.{sc['chapter']}.{sc['verse']}?with=Commentary"})
    return {'passage': a, 'passage2': b, 'results': ranked, 'fulltext': fulltext(a, quote=quote), 'index': citation_index(a), 'books': bk, 'links': links,
            'note': ('Open metadata services only; subscription articles open through your library link or the DOI. '
                     'Band 1 cites both passages, band 2 names both works and cites the first, band 3 cites the first passage alone.')}

# ------------------------------------------------------- full text search
# Two services search the full text of open-access papers and return the
# sentences that match, which is what a reader wants: the author's own words
# on the passage, not our summary. Both need free keys, applied for and kept
# in the .env like the Google Books key; without a key the section is
# skipped and says so. OpenAlex and Crossref above cover only titles and
# abstracts.

S2_API_KEY = os.environ.get('S2_API_KEY', '')
CORE_API_KEY = os.environ.get('CORE_API_KEY', '')


def _s2_snippets(query):
    def run():
        r = requests.get('https://api.semanticscholar.org/graph/v1/snippet/search',
                         params={'query': query, 'limit': 10}, timeout=TIMEOUT,
                         headers={'User-Agent': UA, 'Accept': 'application/json', 'x-api-key': S2_API_KEY})
        r.raise_for_status()
        out = []
        for it in (r.json().get('data') or []):
            paper = it.get('paper') or {}
            snip = (it.get('snippet') or {}).get('text') or ''
            ids = paper.get('externalIds') or {}
            cid = paper.get('corpusId')
            out.append({'title': paper.get('title') or '', 'authors': [a.get('name') for a in (paper.get('authors') or []) if a.get('name')][:6],
                        'year': paper.get('year'), 'venue': paper.get('venue'), 'doi': ids.get('DOI'),
                        'url': f'https://www.semanticscholar.org/p/{cid}' if cid else None,
                        'oa_url': (paper.get('openAccessPdf') or {}).get('url') if isinstance(paper.get('openAccessPdf'), dict) else None,
                        'snippet': _cap_words(snip, 500), 'source': 'semantic_scholar'})
        return out
    return _cached('s2snippet|' + query, run)


def _core_fulltext(phrase, must, a):
    needles = sorted(_names(a), key=len, reverse=True)
    # CORE's parser rejects a bare quoted phrase and any fullText: field
    # query (500, "abstract is not a searchable field"); the same phrase
    # inside a boolean expression works. Found 2026-09-13.
    query = f'"{phrase}" AND ({must})'
    def run():
        r = requests.get('https://api.core.ac.uk/v3/search/works/', params={'q': query, 'limit': 10},
                         timeout=TIMEOUT, headers={'User-Agent': UA, 'Accept': 'application/json', 'Authorization': f'Bearer {CORE_API_KEY}'})
        r.raise_for_status()
        out = []
        for w in (r.json().get('results') or []):
            text = (w.get('fullText') or w.get('abstract') or '')[:600000]
            snip = _citing_sentence(text, a, needles) if text else None
            cites, cites_note = _cites_and_note(f"{w.get('title', '')} {text}", a) if text else (None, '')
            out.append({'title': w.get('title') or '', 'authors': [a.get('name') for a in (w.get('authors') or []) if isinstance(a, dict) and a.get('name')][:6],
                        'year': w.get('yearPublished'), 'venue': w.get('publisher'), 'doi': w.get('doi'),
                        'url': f"https://core.ac.uk/works/{w.get('id')}" if w.get('id') else None,
                        'oa_url': w.get('downloadUrl'), 'snippet': _cap_words(snip or '', 500), 'has_text': bool(text),
                        'cites': cites, 'cites_note': cites_note,
                        'abstract': (w.get('abstract') or '')[:2000], 'source': 'core'})
        return out
    return _cached('core|' + query, run)


AUTHOR_VARIANTS = {'vergil': ['Virgil'], 'virgil': ['Vergil'], 'horace': ['Horatius'], 'ovid': ['Ovidius'],
                   'livy': ['Livius'], 'lucan': ['Lucanus'], 'homer': ['Homerus']}



def _quote_phrase(quote, max_words=6, min_words=3):
    """The opening words as a phrase the services can take. CORE's parser
    answers a phrase containing an apostrophe with a 500 (found 2026-09-16
    on "Of Man's first disobedience"), so the phrase is the longest run of
    apostrophe-free words among the first eight, at least three long."""
    words = [w for w in (quote or '').split()][:8]
    best, run = [], []
    for w in words:
        if any(c in w for c in "'\u2019\u02bc\""):
            run = []
            continue
        run.append(w)
        if len(run) > len(best):
            best = list(run)
    best = best[:max_words]
    return ' '.join(best) if len(best) >= min_words else ''

def fulltext(a, quote=None, limit=12):
    """Sentences from open-access full text that cite the passage, found by
    its number ("Aeneid 1.1") and by its own opening words ("arma virumque
    cano"), which is how papers most often quote a line."""
    if not (S2_API_KEY or CORE_API_KEY):
        return {'available': False, 'results': [],
                'reason': 'Full-text search is not set up: it needs free keys from Semantic Scholar and CORE.'}
    names = sorted(_names(a), key=len, reverse=True)
    must_terms = [a['author'], a['title']] + AUTHOR_VARIANTS.get(a['author'].lower(), [])
    must = ' OR '.join(f'"{t}"' if ' ' in t else t for t in dict.fromkeys(t for t in must_terms if t))
    phrases = [f'{a["title"]} {a["lo"]}', f'{a["abbrev"]} {a["lo"]}']
    quote = _quote_phrase(quote)
    if quote:
        phrases.append(quote)
    needles = names + [a['lo']] + ([quote] if quote else [])
    seen, out, warnings = set(), [], []
    for phrase in phrases:
        sources = []
        if S2_API_KEY:
            sources.append(lambda ph: _s2_snippets(ph))
        if CORE_API_KEY:
            sources.append(lambda ph: _core_fulltext(ph, must, a))
        for src in sources:
            try:
                items = src(phrase)
            except requests.RequestException as e:
                status = getattr(getattr(e, 'response', None), 'status_code', '')
                logger.warning('full-text lookup failed: %s %s', type(e).__name__, status)
                # A lapsed key (CORE's expire monthly) must say so, not go quiet.
                if status in (401, 403):
                    msg = 'A full-text search key has expired or been refused; that source is off until it is renewed.'
                    if msg not in warnings:
                        warnings.append(msg)
                continue
            for it in items:
                key = (it.get('doi') or it.get('title', '').lower()[:80])
                if not key or key in seen:
                    continue
                text = f"{it.get('title', '')} {it.get('snippet', '')} {it.get('abstract', '')}".lower()
                if not it.get('cites'):
                    it['cites'], it['cites_note'] = _cites_and_note(text, a)
                cited = bool(it.get('cites'))
                quoted = bool(quote) and quote.lower() in text
                # A hit whose text the service withholds still matched the
                # phrase on its side; keep it, without a sentence.
                unseen_text = it.get('has_text') is False
                if not (cited or quoted or unseen_text):
                    continue
                seen.add(key)
                it.pop('abstract', None); it.pop('has_text', None)
                out.append(it)
    return {'available': True, 'results': out[:limit], 'warnings': warnings,
            'note': 'Sentences from open-access papers, found by Semantic Scholar and CORE in the full text by the passage number and its opening words.'}

# --------------------------------------------------- citation index
# Articles indexed by passage from full text we hold or may hold: first the
# pre-1923 journals of JSTOR's Early Journal Content (free, on the Internet
# Archive), later whatever the library's agreements bring. Built offline
# by the citation extractor into a SQLite file; absent file, empty section.

CITATION_INDEX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'citation_index', 'citations.db')


def _locus_overlaps(cs, ce, lo, hi):
    n = min(len(cs), len(lo))
    return bool(cs) and cs[:n] <= hi[:n] and ce[:n] >= lo[:n]


# A work on the curated override (work_depth_overrides.json) is cited more
# precisely, by scholars, than this corpus's own .tess tags support --
# that's the whole point of the override (see backend/citations/extractor.
# py's own docstring). A STORED citation for such a work can carry more
# coordinate levels than this corpus's passages do, and matching it
# against a Reader passage needs to know which of the citation's own
# levels corresponds to our own addressing:
#
# - corpus depth >1 (book.chapter tagged, book.chapter.section cited,
#   e.g. Tacitus/cicero.in_catilinam): unchanged, no special-casing needed
#   -- _locus_overlaps already compares only the shared PREFIX length, so
#   a 3-level citation naturally overlaps a 2-level passage on their
#   common book.chapter levels.
# - corpus depth 1 (one flat running number -- a speech's own continuous
#   section numbering) but the citation carries more levels (a chapter.
#   section cite): the LAST level is the one that means the same thing as
#   our own numbering (the section) -- comparing the FIRST level, as the
#   ordinary prefix comparison would, compares a chapter number against a
#   section number, categorically different units.
# - corpus depth 1 for a work whose deeper convention does NOT run
#   straight through but resets per subdivision (Plautus and Terence:
#   act.scene.LINE, where "line" restarts at 1 in every new scene) --
#   there is no way to derive the true absolute line number from the
#   citation alone without the act/scene boundary data this corpus
#   doesn't have. Rather than guess a wrong line, such a citation is
#   treated as matching anywhere in the whole work, with a note.
_RESETS_PER_SUBDIVISION_PREFIXES = ('plautus.', 'terence.')


def _override_depth_shape(work):
    """(corpus_depth, deeper_last_level, whole_work) for `work`: whether
    its curated override depth is deeper than its corpus depth, and if
    so, whether that extra precision maps onto our own single coordinate
    by the citation's LAST level (deeper_last_level) or can't be mapped
    at all without act/scene boundaries we don't have (whole_work)."""
    depth_map, overrides = _load_work_depths()
    base = base_work(work or '')
    corpus_depth = depth_map.get(base)
    override_depth = overrides.get(base)
    deeper = bool(corpus_depth == 1 and override_depth and override_depth > corpus_depth)
    whole_work = deeper and base.startswith(_RESETS_PER_SUBDIVISION_PREFIXES)
    return corpus_depth, (deeper and not whole_work), whole_work


def _citation_span(work, locus_start, locus_end, deeper_last_level, whole_work):
    """(cs, ce, note) for comparing one stored/extracted citation's own
    locus against a passage's coordinates, per _override_depth_shape."""
    cs = _coords(locus_start or '')
    ce = _coords(locus_end or locus_start or '')
    if whole_work:
        return cs, ce, ('cited more precisely (act.scene.line) than this corpus can place '
                         'without act/scene boundaries; shown for the whole work')
    if deeper_last_level and len(cs) > 1:
        cs = (cs[-1],)
        ce = (ce[-1],) if len(ce) > 1 else ce
    return cs, ce, ''


def citation_index(a, limit=40):
    """Articles in the offline index that cite the passage, grouped by
    article with the pages and sentences, newest first."""
    if not a or not a.get('work') or not os.path.exists(CITATION_INDEX):
        return {'available': False, 'results': [], 'reason': 'No offline citation index on this server yet.'}
    import sqlite3
    lo, hi = _coords(a['lo']), _coords(a['hi'])
    book = lo[0] if lo else None
    _corpus_depth, deeper_last_level, whole_work = _override_depth_shape(a['work'])
    try:
        con = sqlite3.connect(f'file:{CITATION_INDEX}?mode=ro', uri=True)
        con.row_factory = sqlite3.Row
        cols = ('c.article_id, c.page, c.locus_start, c.locus_end, c.open_ended, c.surface, c.sentence, '
                'a.title, a.authors, a.journal, a.year, a.volume, a.issue, a.first_page, a.url_ia, a.url_jstor, a.doi')
        base_query = f'SELECT {cols} FROM citations c JOIN articles a ON a.id = c.article_id WHERE c.work_id = ?'  # nosec B608
        if whole_work:
            # Can't narrow by locus at all -- the citation's own first
            # level (act/scene) has nothing to do with our line numbering.
            rows = con.execute(base_query + ' LIMIT 5000', (a['work'],)).fetchall()
        elif deeper_last_level:
            # Our single coordinate is the citation's LAST level (the
            # section), not its first (the chapter) -- match on either a
            # bare section number or one trailing a chapter prefix.
            rows = con.execute(
                base_query + ' AND (c.locus_start = ? OR c.locus_start LIKE ?) LIMIT 5000',
                (a['work'], str(book) if book is not None else '', f'%.{book}' if book is not None else '%')).fetchall()
        else:
            # Narrow by work and by the first coordinate as a string prefix,
            # then check the overlap exactly in Python.
            rows = con.execute(
                base_query + ' AND (c.locus_start LIKE ? OR c.locus_start = ?) LIMIT 5000',
                (a['work'], f'{book}.%' if book is not None else '%', str(book) if book is not None else '')).fetchall()
        con.close()
    except sqlite3.Error as e:
        logger.warning('citation index unreadable: %s', e)
        return {'available': False, 'results': [], 'reason': 'The citation index could not be read.'}
    by_article = {}
    line_level = len(lo or ()) > 1
    for r in rows:
        cs, ce, span_note = _citation_span(a['work'], r['locus_start'], r['locus_end'], deeper_last_level, whole_work)
        surface = r['surface'] or ''
        # Noise the extractor lets through (seen on the first EJC index,
        # 2026-09-17): a bare number as the whole citation ("1" in a
        # glossary list), a book named without a line ("Aen. I", "Aeneid,
        # I, II") when the reader has selected lines, and edition
        # advertisements that cite a span of whole books ("Aen. i-vi, 296").
        if not re.search(r'[A-Za-z]', surface):
            continue
        if not whole_work and line_level and (len(cs) < 2 or not re.search(r'\d', surface)):
            continue  # a book named without a line ("Aen. i, ii" is a list of books, not 1.2)
        if not whole_work and ce and cs and len(cs) > 1 and len(ce) > 1 and ce[0] != cs[0]:
            continue
        if r['open_ended'] and not whole_work:
            # "69 f.", "35 ff.", "136 sqq.": a short run after the start,
            # not the rest of the book.
            ce = cs[:-1] + (cs[-1] + 30,) if len(cs) > 1 else (10 ** 6,)
        if not whole_work and not _locus_overlaps(cs, ce, lo, hi):
            continue
        clean_surface = re.sub(r'\s+', ' ', surface).strip()
        note = _locus_depth_note(a['work'], cs)
        if span_note:
            note = f'{note}; {span_note}' if note else f' ({span_note})'
        art = by_article.setdefault(r['article_id'], {
            'title': r['title'], 'authors': [x for x in (r['authors'] or '').split('; ') if x], 'venue': r['journal'],
            'year': r['year'], 'volume': r['volume'], 'issue': r['issue'], 'doi': r['doi'],
            'url': r['url_jstor'] or r['url_ia'], 'url_jstor': r['url_jstor'], 'url_ia': r['url_ia'], 'pages': [],
            'cites': clean_surface, 'cites_note': note,
            'snippet': _cap_words(re.sub(r'\s+', ' ', r['sentence'] or '').strip(), include=clean_surface),
            'source': 'citation_index'})
        if r['page'] and r['page'] not in art['pages']:
            art['pages'].append(r['page'])
    out = sorted(by_article.values(), key=lambda x: (-(x['year'] or 0), x['title'] or ''))
    return {'available': True, 'results': out[:limit], 'total': len(by_article),
            'note': 'From the full text of journals before 1923 (JSTOR Early Journal Content, on the Internet Archive), indexed by passage with the citation extractor.'}

# ----------------------------------------------------------------- books

GOOGLE_BOOKS_KEY = os.environ.get('GOOGLE_BOOKS_KEY', '')


def hathitrust_search_url(p):
    """A link into HathiTrust's full-text search for the passage's citation
    forms. HathiTrust offers no search API and its search is a web page, so
    this is a link the reader follows, not a request we make."""
    from urllib.parse import quote
    q = f'{p["abbrev"]} {p["lo"]}'
    return f'https://babel.hathitrust.org/cgi/ls?q1={quote(q)};anyall1=phrase;lmt=ft'



def _clean_snippet(s):
    """A service's snippet as plain text: tags out, HTML entities decoded
    (Google Books sends &quot; and &nbsp;), whitespace collapsed."""
    s = re.sub(r'<[^>]+>', '', s or '')
    s = html.unescape(s).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', s).strip()

def books(p, limit=8):
    """Books whose text mentions the passage, from the Google Books API, with
    the snippet the service returns around the match and a link to the page
    in the book's preview. Needs an API key (the anonymous quota is shared
    and exhausted); without one the tab shows the HathiTrust link only."""
    if not GOOGLE_BOOKS_KEY:
        return {'available': False, 'reason': 'Book search needs a Google Books API key (GOOGLE_BOOKS_KEY).', 'results': []}
    def run():
        out = []
        for q in (f'"{p["abbrev"]} {p["lo"]}" {p["author"]}', f'"{p["title"]} {p["lo"]}"'):
            try:
                d = _get('https://www.googleapis.com/books/v1/volumes',
                         {'q': q, 'maxResults': limit, 'key': GOOGLE_BOOKS_KEY, 'printType': 'books'})
            except requests.RequestException as e:
                # Never log the exception text itself: it carries the request URL with the key.
                logger.warning('books lookup failed: %s %s', type(e).__name__, getattr(getattr(e, 'response', None), 'status_code', '')); continue
            for it in d.get('items', []) or []:
                v = it.get('volumeInfo') or {}; si = it.get('searchInfo') or {}; ai = it.get('accessInfo') or {}
                out.append({'title': v.get('title'), 'authors': v.get('authors') or [], 'year': (v.get('publishedDate') or '')[:4],
                            'publisher': v.get('publisher'), 'snippet': _clean_snippet(si.get('textSnippet')),
                            'preview': v.get('previewLink'), 'viewability': ai.get('viewability'), 'id': it.get('id')})
        seen = set(); uniq = []
        for b in out:
            if b['id'] in seen: continue
            seen.add(b['id']); uniq.append(b)
        return {'available': True, 'results': uniq[:limit]}
    out = _cached('books|' + p['work'] + '|' + p['lo'] + '|' + p['hi'], run)
    # Filtered on every call, not inside run(): a book already on disk from
    # before this guard existed (cached up to thirty days) is checked against
    # the current rule immediately, not only once its cache entry expires.
    # Google's own search has no author filter at all for a bare title
    # ("Argonautica" 1.5, no distinction between Apollonius Rhodius and
    # Valerius Flaccus); this is the only check these results get.
    if out.get('results'):
        out = dict(out, results=[b for b in out['results'] if _mentions_work(_book_text(b), p)])
    return out


def _book_text(b):
    return ' '.join(x for x in (b.get('title'), ' '.join(b.get('authors') or []), b.get('snippet')) if x).lower()


# ------------------------------------------------------------ commentary

_commentaries = {}
_commentaries_stamp = None


def _commentary_dir_stamp():
    """Changes whenever a commentary file is added, removed or rewritten in
    place (a rewrite leaves the directory's own time unchanged)."""
    try:
        return (os.path.getmtime(COMMENTARY_DIR),
                max((e.stat().st_mtime for e in os.scandir(COMMENTARY_DIR) if e.name.endswith('.json')), default=0))
    except OSError:
        return None


def _load_commentaries(work):
    global _commentaries_stamp
    base = base_work(work or '')
    # Forget everything when the directory changes (a commentary added while
    # the app runs would otherwise stay invisible until a reload).
    stamp = _commentary_dir_stamp()
    if stamp != _commentaries_stamp:
        _commentaries.clear()
        _commentaries_stamp = stamp
    if base in _commentaries:
        return _commentaries[base]
    out = []
    if os.path.isdir(COMMENTARY_DIR):
        for fn in sorted(os.listdir(COMMENTARY_DIR)):
            # One file per work, or one per part (allen__homer.hymns.part.2.json).
            if fn.endswith(f'__{base}.json') or (f'__{base}.part.' in fn and fn.endswith('.json')):
                try:
                    with open(os.path.join(COMMENTARY_DIR, fn), encoding='utf-8') as fh:
                        doc = json.load(fh)
                    doc['_who'] = fn.split('__', 1)[0]
                    out.append(doc)
                except (OSError, ValueError) as e:
                    logger.warning('commentary %s unreadable: %s', fn, e)
    _commentaries[base] = out
    return out


# Rough date of each commentator, by file prefix: readers meet the ancient
# and medieval commentators before the modern ones. Unknown prefixes sort last.
COMMENTATOR_DATES = {
    'servius': 400, 'rashi': 1100, 'ibn_ezra': 1150, 'radak': 1200, 'ramban': 1260, 'ralbag': 1330,
    'sforno': 1500, 'metzudat_david': 1750, 'metzudat_zion': 1750, 'henry': 1710, 'anon1813': 1813, 'malbim': 1860,
    'conington': 1870, 'paley_sandys': 1875, 'papillon_haigh': 1892, 'page': 1894, 'merry': 1880, 'monro': 1880, 'cope': 1877,
    'goodwin': 1885, 'jebb': 1890, 'gildersleeve': 1890, 'merrill': 1893, 'seymour': 1890,
    'leaf': 1900, 'simmons': 1900, 'sharpley': 1900, 'allen': 1904, 'donkin': 1905, 'how_wells': 1912,
    'kitchin': 1867, 'variorum': 1932, 'clark_wright': 1874, 'masson': 1874, 'wright': 1877, 'de_selincourt': 1907, 'verity': 1910, 'shorey': 1919,
}


def _commentator_order(doc):
    return (COMMENTATOR_DATES.get(doc.get('_who'), 9999), doc.get('commentator') or '')


_LOCUS_TAIL = re.compile(r'(?<![A-Za-z])((?:[IVXLC]+|\d+)(?:\.(?:[IVXLC]+|\d+))*)\s*$')
_ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}


def _roman(tok):
    total = 0
    for i, ch in enumerate(tok):
        v = _ROMAN[ch]
        total += -v if i + 1 < len(tok) and _ROMAN[tok[i + 1]] > v else v
    return total


_sources_cache = {'stamp': None, 'rows': None}


def commentary_sources():
    """One row per commentator and edition: works covered, note count, source, licence.
    Reading every file takes seconds once the full catalogue is installed
    (about 400 files, 150 MB), so the rows are kept until a file changes."""
    stamp = _commentary_dir_stamp()
    if stamp is not None and _sources_cache['stamp'] == stamp:
        return _sources_cache['rows']
    rows_out = _commentary_sources_uncached()
    _sources_cache.update(stamp=stamp, rows=rows_out)
    return rows_out


def _commentary_sources_uncached():
    rows = {}
    if not os.path.isdir(COMMENTARY_DIR):
        return []
    for fn in sorted(os.listdir(COMMENTARY_DIR)):
        if not fn.endswith('.json') or '__' not in fn:
            continue
        try:
            with open(os.path.join(COMMENTARY_DIR, fn), encoding='utf-8') as fh:
                d = json.load(fh)
        except (OSError, ValueError):
            continue
        source = (d.get('source') or '').split(' ')[0]
        via_sefaria = 'sefaria.org' in source
        # Sefaria serves each book from a different edition: one row per
        # commentator there, with the licences it states collected.
        key = (d.get('commentator') or fn.split('__')[0], 'sefaria' if via_sefaria else (d.get('edition') or ''))
        row = rows.setdefault(key, {'commentator': key[0], 'title': d.get('title'),
                                    'edition': 'Hebrew text and English translations as served by Sefaria, edition per book' if via_sefaria else key[1],
                                    'source': 'https://www.sefaria.org/' if via_sefaria else source,
                                    'license': None if via_sefaria else d.get('license'), 'licenses': set(),
                                    'language': d.get('language'), 'works': [], 'notes': 0})
        if via_sefaria:
            for lic in (d.get('license'), d.get('license_translation')):
                if lic and lic.lower() != 'unknown':
                    row['licenses'].add(lic)
        work = base_work(d.get('work') or fn.split('__', 1)[1].replace('.json', ''))
        if work not in row['works']:
            row['works'].append(work)
        row['notes'] += len(d.get('units') or [])
    for r in rows.values():
        if r['licenses']:
            r['license'] = 'as stated by Sefaria per text: ' + ', '.join(sorted(r['licenses']))
        elif r['license'] is None and 'sefaria' in r['source']:
            r['license'] = 'as stated by Sefaria per text'
        del r['licenses']
    out = sorted(rows.values(), key=lambda r: (COMMENTATOR_DATES.get(r['commentator'].lower().split()[0].replace('.', ''), 9999), r['commentator']))
    return out


def _coords(ref):
    # The locus is the dotted run of numbers at the end of the tag. Play
    # tags number the act in Roman numerals (hamlet I.1.1), so those count
    # too; the earlier digits-only reading made acts I and II the same line.
    m = _LOCUS_TAIL.search(ref or '')
    if not m:
        return tuple(int(n) for n in re.findall(r'\d+', format_short_locus(ref or '')))
    return tuple(_roman(t) if t.isalpha() else int(t) for t in m.group(1).split('.'))


def _scripture_commentary(c1, c2):
    """Notes filed by the canonical key (data/commentaries/<who>__bible.<book>.json,
    refs "isaiah 40:3"), for any version of the verse."""
    lo = (c1['chapter'], c1['verse'] or 0)
    hi = (c2['chapter'], c2['verse'] or 999) if c2 else (c1['chapter'], c1['verse'] or 999)
    if hi < lo:
        lo, hi = hi, lo
    out = []
    for c in sorted(_load_commentaries(f"bible.{c1['book']}"), key=_commentator_order):
        notes = []
        for u in c.get('units', []):
            m = re.search(r'(\d+):(\d+)$', u.get('ref') or '')
            if m and lo <= (int(m.group(1)), int(m.group(2))) <= hi:
                notes.append({'ref': u.get('ref'), 'lemma': u.get('lemma'), 'text': u.get('text'), 'text_en': u.get('text_en')})
        if notes:
            out.append({'commentator': c.get('commentator'), 'title': c.get('title'), 'edition': c.get('edition'),
                        'translation': c.get('translation'), 'language': c.get('language') or 'he',
                        'source': c.get('source'), 'license': c.get('license'),
                        'version_note': (f"Shown for the {c1['version']}; chapter and verse follow the Hebrew numbering"
                                         + (', mapped approximately' if c1.get('approximate') else '') + '.')
                        if c1['version'] != 'Hebrew Bible' else None,
                        'notes': notes[:60]})
    return out


def commentary_at(work, ref_start, ref_end=None):
    """Notes from the site's public-domain commentaries on a span of a work."""
    c1 = scripture.canonical(work, ref_start)
    if c1:
        return _scripture_commentary(c1, scripture.canonical(work, ref_end) if ref_end else None)
    lo = _coords(ref_start); hi = _coords(ref_end) if ref_end else lo
    if not lo:
        return []
    if hi < lo:
        lo, hi = hi, lo
    out = []
    wanted = (work or '').replace('.tess', '')
    for c in sorted(_load_commentaries(work), key=_commentator_order):
        # A file that covers one part (gildersleeve__pindar.odes.part.3.olympians)
        # answers only for that part: Olympian 1.1 and Pythian 1.1 share coordinates.
        if '.part.' in (c.get('work') or '') and c.get('work') != wanted:
            continue
        notes = [u for u in c.get('units', []) if lo <= _coords(u.get('ref')) <= hi]
        if notes:
            out.append({'commentator': c.get('commentator'), 'title': c.get('title'), 'edition': c.get('edition'),
                        'language': c.get('language') or 'la',
                        'source': c.get('source'), 'license': c.get('license'),
                        'notes': [{'ref': u.get('ref'), 'lemma': u.get('lemma'), 'text': u.get('text')} for u in notes][:60]})
    return out
