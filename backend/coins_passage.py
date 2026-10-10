"""Coins for a passage: the logic behind /api/coins/for-passage and /api/coins/theme.

Two links from literature to coins, kept apart on purpose.

Related imagery. The passage index already holds a model-written English
description of every fine window. The gist sentence of the covering window with
the most concrete nouns is encoded through the query encoder SERVICE (never
in this process: see passage_index.embed_query), compared by cosine with the
vectors of the 26,461 distinct coin-type descriptions, and the five nearest
distinct descriptions are returned. Measured on ten passages with known coin
parallels, about one top-five match in three is a real parallel; the page says
so. The Latin text, the translation and the full labelled description all did
far worse (research notes, 2026-10-09), so the gist is the only query used.

Name links. A person named on a coin (the authority or the obverse portrait)
and named in the passage. Shown as a name link, never as an echo: the coin does
not quote the passage, it names the same man. A name matches when every word of
one of its Latin forms occurs as a capitalised word of the passage's lines
(token or lemma, from cache/lemmas). Latin only.

The vectors are data/coins/descriptions.npy (float16) with
descriptions_ids.json beside the coins database; with no vectors the routes say
available=false. Nothing here loads a model.
"""
import json
import os
import re
import threading
from collections import OrderedDict
from urllib.parse import quote

from backend.logging_config import get_logger

logger = get_logger('coins_passage')

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMES_FILE = os.path.join(_ROOT, 'backend', 'coins_authority_names.json')
PREFIX = 'query: '          # same as backend/passage_index.py _E5_PREFIX
TOP_K = 5
MAX_QUERY_CHARS = 1500
CACHE_SIZE = 256

# The measured rate, in the words the page uses (ten passages, 50 top-five
# slots, 17 judged real parallels: 0.34 over all ten, 0.325 over eight).
HIT_RATE_LABEL = ('About one match in three is right. These are coin types whose catalogue '
                  'description of the imagery is close in meaning to the passage, not coins '
                  'known to refer to it.')
THEME_LABEL = ('Ranked by how close each coin description is in meaning to your words. '
               'Described the way a coin catalogue would, a query found about one right coin '
               'in two in our test; a vague or abstract query finds fewer.')

# Per-card confidence from the cosine. On the 50 judged hits of the ten test
# passages the cosine separated right from wrong only at the top: 7 of the 10
# hits at 0.83 or above were real parallels, against 10 of the other 40. Below
# 0.83 the cosine said nothing (the middle band did worst), so there are two
# levels, not three, and the test is small.
CONF_HIGHER = 0.83
CONF_RATES = {'higher': '7 in 10', 'usual': '1 in 4'}

DESC_KEYS = ('mode', 'setting', 'participants', 'action_steps', 'props',
             'themes', 'imagery_tone', 'gist')

_lock = threading.Lock()
_vec = {'key': None, 'matrix': None, 'rows': None}
_names = {'key': None, 'entries': None}
_cache = OrderedDict()


# -- seams the tests replace -------------------------------------------------

def embed(text):
    """The query vector, from the encoder service."""
    from backend import passage_index
    return passage_index.embed_query(PREFIX + text.strip()[:MAX_QUERY_CHARS])


class EncoderUnavailable(RuntimeError):
    pass


def windows_covering(work, ref_start, ref_end):
    """Fine windows of the passage index whose reference range overlaps the
    selection, as dicts with id, ref_start, ref_end and desc."""
    from backend import passage_index as pi
    pi._ensure_loaded()
    if not pi._state.get('ok'):
        return []
    group = pi._by_work.get(pi._norm_work(work)) or []
    wid = pi.work_id(work)
    exact = [r for r in group if pi._records[r].get('work') == wid]
    rows = exact if (pi.is_part(wid) and exact) else group
    want = pi._ref_coords_in(work, ref_start) or ()
    want_end = pi._ref_coords_in(work, ref_end) or want
    out = []
    for row in rows:
        r = pi._records[row]
        if r.get('scale') != 'fine':
            continue
        lo = pi._ref_coords_in(r.get('work'), r.get('ref_start'))
        hi = pi._ref_coords_in(r.get('work'), r.get('ref_end'))
        if not (lo and hi):
            continue
        if want:
            n = min(len(lo), len(hi), len(want), len(want_end))
            if not (lo[:n] <= want_end[:n] and hi[:n] >= want[:n]):
                continue
        out.append({'id': r.get('id'), 'ref_start': r.get('ref_start'),
                    'ref_end': r.get('ref_end'), 'desc': r.get('desc') or {}})
    return out


def passage_units(work, language, ref_start, ref_end):
    """The cached lemma units (ref, tokens, lemmas) of the selected lines."""
    from backend import lemma_cache
    from backend.work_names import base_work
    w = re.sub(r'\.tess$', '', str(work or ''))
    seen, data = set(), None
    for cand in (w, base_work(w)):
        if cand in seen:
            continue
        seen.add(cand)
        for path in (lemma_cache.get_cache_path(f'{cand}.tess', language),
                     lemma_cache._legacy_cache_path(cand, language)):
            if os.path.exists(path):
                try:
                    with open(path, encoding='utf-8') as f:
                        data = json.load(f)
                except (OSError, ValueError):
                    data = None
                if data:
                    break
        if data:
            break
    if not data:
        return []
    lo = _coords(ref_start)
    hi = _coords(ref_end) or lo
    out = []
    for u in data.get('units_line') or []:
        c = _coords(u.get('ref'))
        if not c or not lo:
            continue
        n = min(len(c), len(lo), len(hi))
        if lo[:n] <= c[:n] <= hi[:n]:
            out.append(u)
    return out


# -- helpers -----------------------------------------------------------------

def _coords(ref):
    nums = re.findall(r'\d+', str(ref or '').rsplit(' ', 1)[-1])
    return tuple(int(n) for n in nums)


def norm_word(w):
    """Lower-case with the corpus's spelling (u for v, i for j)."""
    return str(w or '').lower().replace('v', 'u').replace('j', 'i')


def concreteness(desc):
    """How many named things a window description carries: props, participants
    and setting words. The window with the most is the one that is queried."""
    n = len(desc.get('props') or [])
    part = desc.get('participants') or ''
    n += len([x for x in re.split(r',| and ', part if isinstance(part, str) else ', '.join(part)) if x.strip()])
    n += len((desc.get('setting') or '').split()) // 3
    return n


def best_window(windows):
    """The covering window with the most concrete nouns and a gist."""
    with_gist = [w for w in windows if (w['desc'].get('gist') or '').strip()]
    if not with_gist:
        return None
    return max(with_gist, key=lambda w: concreteness(w['desc']))


def confidence_level(score):
    return 'higher' if score >= CONF_HIGHER else 'usual'


# -- the description vectors ---------------------------------------------------

def _data_dir(db_path):
    return os.path.dirname(os.path.abspath(db_path))


def load_vectors(db_path):
    """(float16 matrix, rows) or (None, None) when the vectors are not installed.
    Re-read when either file changes."""
    d = _data_dir(db_path)
    npy, ids = os.path.join(d, 'descriptions.npy'), os.path.join(d, 'descriptions_ids.json')
    if not (os.path.exists(npy) and os.path.exists(ids)):
        return None, None
    key = (npy, os.path.getmtime(npy), os.path.getmtime(ids))
    with _lock:
        if _vec['key'] != key:
            import numpy as np
            matrix = np.load(npy, mmap_mode='r')
            with open(ids, encoding='utf-8') as f:
                rows = json.load(f)
            if matrix.shape[0] != len(rows):
                logger.error('coins vectors out of step: %d vectors, %d rows', matrix.shape[0], len(rows))
                return None, None
            _vec.update(key=key, matrix=matrix, rows=rows)
            _cache.clear()
        return _vec['matrix'], _vec['rows']


def rank(matrix, qvec, k=TOP_K, chunk=4096):
    """Indices and cosines of the k rows nearest the (unit) query vector."""
    import numpy as np
    q = np.asarray(qvec, dtype=np.float32)
    n = np.linalg.norm(q)
    if n:
        q = q / n
    scores = np.empty(matrix.shape[0], dtype=np.float32)
    for i in range(0, matrix.shape[0], chunk):
        scores[i:i + chunk] = np.asarray(matrix[i:i + chunk], dtype=np.float32) @ q
    top = np.argsort(-scores)[:k]
    return [(int(i), float(scores[i])) for i in top]


# -- cards -------------------------------------------------------------------

def _reverse_of(text):
    m = re.search(r'Reverse:\s*(.*)$', text or '')
    return m.group(1).strip() if m else None


def _obverse_of(text):
    m = re.search(r'Obverse:\s*(.*?)(?:\s+Reverse:|$)', text or '')
    return m.group(1).strip() if m else None


def description_card(conn, row, score):
    """One related-imagery card for a description row."""
    types = row['types']
    ph = ','.join('?' * min(len(types), 900))
    recs = conn.execute(
        f'SELECT id, authority, issuer, mint, date_start, date_end, denomination, title '  # nosec B608 -- placeholders only
        f'FROM coins WHERE id IN ({ph}) ORDER BY COALESCE(date_start, 99999), id',
        types[:900]).fetchall()
    ex = recs[0] if recs else None
    auth, seen = [], set()
    for r in recs:
        for a in (r['authority'] or '').split('; '):
            if a and a not in seen:
                seen.add(a)
                auth.append(a)
    starts = [r['date_start'] for r in recs if r['date_start'] is not None]
    ends = [r['date_end'] if r['date_end'] is not None else r['date_start'] for r in recs
            if r['date_start'] is not None]
    return {
        'description': row['text'],
        'obverse_description': _obverse_of(row['text']),
        'reverse_description': _reverse_of(row['text']),
        'score': round(score, 4),
        'confidence': {'level': confidence_level(score), 'score': round(score, 4),
                       'tested_rate': CONF_RATES[confidence_level(score)]},
        'n_types': len(types),
        'authorities': auth[:4],
        'authorities_total': len(auth),
        'date_start': min(starts) if starts else None,
        'date_end': max(ends) if ends else None,
        'mint': ex['mint'] if ex else None,
        'denomination': ex['denomination'] if ex else None,
        'coin_id': ex['id'] if ex else None,
        'coin_title': ex['title'] if ex else None,
        'coin_url': f'/coins/{quote(str(ex["id"]), safe="")}' if ex else None,
    }


# -- name links --------------------------------------------------------------

def _load_names_file():
    try:
        with open(NAMES_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'names': {}, 'skip': []}


def _generated_forms(label):
    """Latin-name words from an English label for a person with no hand entry:
    the last two words of the name once initials and bracketed parts are gone."""
    if ('(' in label or '[' in label or '/' in label or 'Moneyer' in label or 'Personi' in label
            or re.fullmatch(r'B?\d+', label)):
        return None
    parts = [w for w in re.split(r'\s+', label) if w and w.lower() not in ('the', 'of', 'de', 'and')]
    words = [norm_word(w) for w in parts if not w.endswith('.') and re.fullmatch(r"[A-Za-z]+", w)
             and len(w) >= 3]
    # A name whose praenomen and nomen were only initials, leaving one word
    # (C. Antonius), would link every namesake: leave it out.
    if not words or (len(words) == 1 and len(parts) > 1):
        return None
    return [' '.join(words[-2:])]


def name_entries(conn, db_key):
    """[{label, latin, forms:[set of words], n_types}] for every authority and
    portrait name in the database, hand table first."""
    with _lock:
        if _names['key'] == db_key:
            return _names['entries']
    table = _load_names_file()
    skip = set(table.get('skip') or [])
    hand = table.get('names') or {}
    counts = {}
    for r in conn.execute('SELECT authority, portrait, COUNT(*) AS n FROM coins GROUP BY 1, 2'):
        names = set()
        for field in (r['authority'], r['portrait']):
            for part in (field or '').split('; '):
                if part.strip():
                    names.add(part.strip())
        for nm in names:
            counts[nm] = counts.get(nm, 0) + r['n']
    entries = []
    for label, n in counts.items():
        if label in skip:
            continue
        if label in hand:
            latin, forms = hand[label]['latin'], hand[label]['forms']
        else:
            forms = _generated_forms(label)
            latin = label
            if not forms:
                continue
        entries.append({'label': label, 'latin': latin, 'n_types': n,
                        'forms': [set(f.split()) for f in forms if f.split()]})
    # Two labels with the same Latin words (Iulius Caesar and a moneyer of that
    # name) would show as one name twice: keep the one with the most types.
    best = {}
    for e in entries:
        for f in e['forms']:
            k = frozenset(f)
            if k not in best or e['n_types'] > best[k]['n_types']:
                best[k] = e
    keep = {id(e) for e in best.values()}
    entries = [e for e in entries if id(e) in keep]
    with _lock:
        _names.update(key=db_key, entries=entries)
    return entries


def capitalised_words(units):
    """Normalised capitalised words of the units, from tokens and from lemmas."""
    out = set()
    for u in units:
        orig = u.get('original_tokens') or u.get('tokens') or []
        lem = u.get('lemmas') or []
        for i, o in enumerate(orig):
            if o[:1].isupper():
                out.add(norm_word(o))
                if i < len(lem) and lem[i]:
                    out.add(norm_word(lem[i]))
    return out


def name_links(conn, db_key, units):
    words = capitalised_words(units)
    if not words:
        return []
    hits = []
    for e in name_entries(conn, db_key):
        if any(f <= words for f in e['forms']):
            hits.append({'name': e['latin'], 'label': e['label'], 'n_types': e['n_types'],
                         'coins_url': f'/coins?person={quote(e["label"])}'})
    hits.sort(key=lambda h: (-h['n_types'], h['name']))
    return hits


# -- the two entry points ------------------------------------------------------

def _cache_get(key):
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    return None


def _cache_put(key, value):
    with _lock:
        _cache[key] = value
        while len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)


def for_passage(conn, db_path, work, lang, ref, ref_end=None):
    """The /api/coins/for-passage payload. Raises EncoderUnavailable (the
    caller says so honestly) when the query encoder cannot be reached."""
    matrix, rows = load_vectors(db_path)
    ref_end = ref_end or ref
    key = (str(work), str(lang), str(ref), str(ref_end), _vec['key'])
    hit = _cache_get(key)
    if hit is not None:
        return hit
    out = {'available': matrix is not None, 'work': work, 'language': lang, 'ref': ref,
           'hit_rate_label': HIT_RATE_LABEL, 'related': [], 'name_links': [],
           'name_links_note': 'A name link means the same person is named on the coin and in the '
                              'passage. It is not an echo of the passage.'}
    if lang == 'la':
        try:
            units = passage_units(work, lang, ref, ref_end)
            out['name_links'] = name_links(conn, os.path.getmtime(db_path), units)
        except Exception:  # a missing lemma cache must not take the imagery down
            logger.exception('coins name links failed for %s %s', work, ref)
    if matrix is None:
        out['reason'] = 'The coin description vectors are not installed.'
        return out
    win = best_window(windows_covering(work, ref, ref_end))
    if win is None:
        out['note'] = 'No passage window with a description covers this reference.'
        _cache_put(key, out)
        return out
    gist = win['desc']['gist'].strip()
    out['window'] = {'id': win['id'], 'ref_start': win['ref_start'], 'ref_end': win['ref_end']}
    out['query'] = gist
    try:
        qvec = embed(gist)
    except Exception as e:  # EmbedUnavailable and any transport error: say so, never guess
        raise EncoderUnavailable(str(e)) from e
    out['related'] = [description_card(conn, rows[i], s) for i, s in rank(matrix, qvec)]
    _cache_put(key, out)
    return out


def theme(conn, db_path, q, k=10):
    """The /api/coins/theme payload: the descriptions nearest the query."""
    matrix, rows = load_vectors(db_path)
    out = {'available': matrix is not None, 'query': q, 'results': [], 'label': THEME_LABEL}
    if matrix is None:
        out['reason'] = 'The coin description vectors are not installed.'
        return out
    try:
        qvec = embed(q)
    except Exception as e:
        raise EncoderUnavailable(str(e)) from e
    out['results'] = [description_card(conn, rows[i], s) for i, s in rank(matrix, qvec, k)]
    return out
