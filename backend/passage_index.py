"""Scene index: passage-level content retrieval over LLM-written descriptions.

The index holds, for every passage-sized window of the corpus, a structured English
description of WHAT THE PASSAGE CONTAINS (mode, setting, participants, actions,
themes, imagery, gist) plus an embedding of that description. Retrieval runs over
the descriptions rather than the ancient text, which is what lets a Latin passage
match a Hebrew or Greek one that shares no vocabulary.

Two query modes back the Reader:
  * by passage  -- "what else in the corpus is like this stretch of text"
  * by text     -- "find passages about grain shortage and famine relief"

Data (built offline, see research/motif_feature/DEVELOPMENT_LOG_2026-08.md):
  data/passage_index/descriptions.jsonl   one JSON record per window
  data/passage_index/embeddings.npy       float16 (N, D), row i matches ids[i]
  data/passage_index/ids.json             window ids, embedding row order

Embeddings are memory-mapped, so the resident cost is the id/description tables
rather than the matrix. Loading is lazy: nothing touches disk until the first
query, and a missing index degrades to "unavailable" instead of failing import.
"""
from collections import Counter
import json
import math
import os
import re
import threading

from backend import scripture_id
from backend import restricted_texts
from backend.logging_config import get_logger
from backend.work_names import base_work, is_part, work_id

logger = get_logger('passage_index')

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'passage_index')

# The query encoder must match the model the descriptions were embedded with.
EMBED_MODEL = 'intfloat/multilingual-e5-large'
# e5 expects this prefix on both sides; the offline build used it too.
_E5_PREFIX = 'query: '

# Match confidence, measured rather than assumed (2026-08-23, 18 probe queries
# against the 143,947-window index: 10 subjects the corpus really contains, 8 it
# cannot). Two facts came out of that measurement and both shape this code.
#
# 1. No ABSOLUTE cosine threshold works. Raw score scales with query length, so a
#    long query about an absent subject outscores a short query about a present
#    one. Everything below is relative to the query's own corpus baseline (the
#    median score across all windows).
# 2. No SINGLE relative signal separates present from absent subjects cleanly.
#    Top-hit lift over baseline overlapped (real 0.080-0.135, fake 0.048-0.084),
#    and so did the coherence of the top-20 cluster (real 0.878-0.940, fake
#    0.848-0.894). Combined and standardised, the two nearly separate (real
#    -0.75 to 4.25, fake -4.07 to -0.31), which supports a GRADED confidence but
#    not a hard verdict. So the API reports a band and never claims certainty.
STRONG_LIFT = 0.090      # top-hit lift at or above the real-subject median
WEAK_LIFT = 0.070        # below this, treat the result set as neighbours only
COHERENCE_K = 20         # top-k cluster used for the agreement signal
STRONG_COHERENCE = 0.900 # top-k agreement typical of a real subject
# Decision boundary on the combined score, fitted 2026-08-24 to a 22-query probe
# set (12 subjects the corpus holds, 10 it cannot). Combined = lift*10 +
# (coherence-0.85)*10. Real subjects scored 1.20-2.35, absent ones 0.46-1.29, so
# the classes overlap slightly and 1.30 is the accuracy-maximising split (91%).
# 'strong' sits well above the overlap; 'moderate' spans it and is reported as
# genuinely uncertain rather than as a verdict.
# Refitted 2026-08-25 against the full 603,594-window index, using the 28-query
# probe set in evaluation/probe_sets/tesserae_2026-08.json (12 subjects the
# corpus holds, 16 it does not). Accuracy 93%.
#
# Six of the absent queries are deliberate NEAR MISSES, classical in register
# with one thing in them that does not exist in antiquity, and they are what
# makes this fit worth anything. "A farmer lifts potatoes out of the ground and
# sorts them for seed" scored 1.76, higher than eight of the twelve REAL
# subjects, because everything in it but the potato is deeply present in the
# corpus. Without those queries the strong boundary would have been set at 1.28,
# from a tea ceremony, and Theme Search would have called near misses strong.
# REFITTED 2026-08-27, after the Persian/Urdu re-describe, against the same
# 32-query probe set (12 present, 20 absent). Both numbers moved, which is the
# whole reason the refit was necessary: the window count did not change by one,
# so nothing in the code would have reported these as stale.
#
#     before (fitted 2026-08-25)   MODERATE 1.40   STRONG 1.7613   accuracy 93%
#     after  (fitted 2026-08-27)   MODERATE 1.27   STRONG 1.83     accuracy 88%
#
# ACCURACY FELL, and that is a real finding rather than noise in the fit. The
# re-described Persian windows carry far more content than before -- 1.46 action
# steps to 8.99 -- so there is simply more for an absent subject to half-match
# against, and the two classes overlap more than they did. "A farmer lifts
# potatoes out of the ground" now scores 1.83 and "antibiotics are prescribed"
# 1.83, against a present-subject floor of 1.11.
#
# The practical effect: STRONG is now a higher bar than it was, deliberately,
# because it is set above every absent subject tested. Fewer result sets will be
# called strong, and that is the correct direction to err.
#
# REFITTED 2026-08-27 (second time that day) against an 80-QUERY probe set, 40
# present and 40 absent, in evaluation/probe_sets/tesserae_2026-08-27.json. The
# set was enlarged because 32 queries put roughly +/-12 points of error on the
# reported accuracy, and because the strong boundary is pinned to the single
# highest absent score, which on 20 absent queries is one noisy number.
#
#     before (32 queries)   MODERATE 1.27   STRONG 1.83   accuracy 88%
#     after  (80 queries)   MODERATE 1.21   STRONG 1.83   accuracy 79%
#
# STRONG DID NOT MOVE. Doubling the absent queries left it exactly where twenty
# had put it, which is the best evidence available that 1.83 is a property of the
# corpus and not of the probe set.
#
# THE ACCURACY DROP IS THE MEASUREMENT GETTING HARDER, NOT THE TOOL GETTING
# WORSE. The old figure was taken on 20 absent queries; this one on 40, most of
# them deliberate near misses. Ten of the first forty absent queries had to be
# replaced during construction because they turned out to be PRESENT: a jury, a
# census, a potter, a glassblower, a bee-keeper, a manumission, a watermill, an
# illuminated manuscript, a naturalist classifying by genus and species, and
# whaling from an open boat. Every one sounds unmodern and every one is
# thoroughly ancient. See evaluation/probe_sets/TESTING_RECORD_2026-08.md.
#
# MODERATE MOVED DOWN, and the reason is worth stating because it looks like
# loosening. Accuracy is FLAT from 1.14 to 1.25, and 1.27 sits just past the end
# of that plateau, where it was costing real subjects for almost nothing:
#
#     threshold 1.21   present kept 39/40   absent rejected 24/40   79%
#     threshold 1.27   present kept 34/40   absent rejected 25/40   74%
#
# Six genuine subjects were being called low so that one more near miss could be.
# 1.21 rather than the fit's own 1.17, because 1.17 is exactly the lowest present
# score observed and would be fitted to a single query.
MODERATE_COMBINED = 1.21
STRONG_COMBINED = 1.83
# The index those two numbers were fitted against. They are a property of THAT
# corpus, not of the method, and the corpus has since grown: merging Persian and
# Urdu added 220,361 windows, which moves the median every lift is measured
# against. So the constants are held next to the size they were fitted at, and a
# live index that no longer matches gets told so in its own output rather than
# reporting a band it has not earned. Refit with
# evaluation/scripts/calibrate_confidence.py and update both numbers together.
FITTED_AT_WINDOWS = 603594
FITTED_TOLERANCE = 0.15     # beyond 15% drift, stop vouching for the band
# Growth since the fit, recorded rather than refitted: the Latin import batches
# and the dual-phrasing pass brought the index to 610,670, and the vernacular
# pilot (Commedia, Roland, Nibelungenlied) to 617,137 on 2026-09-01. That is
# 2.2% drift, well inside the tolerance above, so the band still stands. Refit
# when a batch takes it past 15%, or after any corpus-wide re-describe, which
# the count alone cannot detect.
# THE COUNT IS NOT THE ONLY THING THAT INVALIDATES THE FIT, and the guard below
# only watches the count. It was written for "the corpus grew", which is what
# had happened at the time, and it does not notice "the corpus was re-described".
#
# The Persian/Urdu re-describe rewrites the descriptions of 220,361 windows,
# a third of the index, and re-embeds them. Every score in Theme Search is
# measured against the median of the whole index, so that median moves and the
# two constants above no longer sit where they were fitted -- while the window
# count does not change by one, so _calibration_drift() reports nothing wrong
# and the bands keep being published as though they were still earned.
#
# So: REFIT AFTER THE MERGE, with evaluation/scripts/calibrate_confidence.py
# against evaluation/probe_sets/tesserae_2026-08.json, and update both
# constants together. Recorded here rather than only in a report because this
# is the line someone will read when they wonder whether the numbers still hold.

# A floor purely to stop the tail: results below the query's baseline are noise.
BASELINE_MARGIN = 0.010

# How many passages one work may show on a Theme Search page. The Iliad has four
# canonical arming scenes and a reader looking for the type-scene wants to see
# that it recurs, so one per work is too few; more than three and a long epic
# starts crowding the page again.
PASSAGES_PER_WORK = 3

# Lexical boost (2026-09-20: the light boost was adopted in production).
# A word index over the descriptions (scripts/build_desc_fts.py, SQLite
# FTS5 with BM25 over gist, themes, action steps, participants, setting)
# adds a little to the cosine of windows whose description shares words
# with the query: cosine + LEXICAL_BETA x BM25 normalised to [0, 1] over the
# top LEXICAL_TOPN lexical hits, nothing for the rest. Measured on this
# code path against the shipped page on the 16-query benchmark
# (docs/DECISIONS.md, 2026-09-20): first-ten precision 0.434 -> 0.453, the
# four held-out topoi 0.325 -> 0.375; the Odyssey on "a wife or child
# recognizes someone long thought dead or lost" from the 63rd work to the
# 50th, and onto the page (row 15) when the reader is given all 300
# composed rows instead of 100. An offline harness had shown 0.506, but it
# let a passage appear twice (whole-file and book-file copies); this path
# collapses those, and 0.453 is the honest figure. The boost is skipped, with one logged
# warning, when the index file is missing or was built for a different
# set of windows, and can be turned off with THEME_LEXICAL=0.
LEXICAL_BETA = 0.02
LEXICAL_TOPN = 3000
_LEX_PATH = os.path.join(_DATA_DIR, 'desc_fts.sqlite')
_lex_lock = threading.Lock()
_lex_state = {'checked': False, 'ok': False, 'row_by_id': None}

# "Same people and places": a second Similar-Passages grouping, by shared rare
# proper names rather than by content embedding alone (research/theme_search/
# names_panel/NOTES.md). The name index (window_names.db, built offline by
# research/theme_search/names_panel/build_names.py) is optional: when it is
# absent the feature is simply off and nothing else about Similar Passages
# changes. Opened once per process and kept open, same convention as
# _lex_state above for desc_fts.sqlite, except here the connection itself is
# cached (not reopened per call) because every query needs it.
_NAMES_PATH = os.path.join(_DATA_DIR, 'window_names.db')
_names_lock = threading.Lock()
_names_state = {'checked': False, 'conn': None, 'df': None, 'N': 0, 'N_by_lang': {}}
NAMES_IDF_THRESHOLD = 4.5   # a name rarer than roughly 1 window in 90 counts
NAMES_LAMBDA = 0.008        # weight of the shared-name-rarity term in scoring
NAMES_WEAK_STRENGTH = 2.0   # below this summed rarity, flag the group as weak
NAMES_COMMENTARY_MARKERS = (
    'lactantius_placidus', 'servius', 'scholia', 'donatus', 'porphyrio',
    'pseudo_acro', 'commentar')

_lock = threading.Lock()
_state = {'loaded': False, 'ok': False, 'error': None}
_ids = None            # list[str]
_undescribed = set()   # row indices with no description: excluded from results
_records = None        # list[dict] in embedding-row order
_emb = None            # np.memmap (N, D) float16
_by_work = None        # work -> list[row index]
_by_language = None    # language code -> np.int64 array of row indices
_model = None


def _norm_work(work):
    """Collapse a work identifier to the index's key form.

    The Reader sends the work as its corpus filename, and for a multi-part
    work the .part split incidentally removed the .tess suffix too, so
    vergil.aeneid.part.1.tess matched while a single-file work like
    shenoute.a22.tess never did: its Similar Passages answered "no indexed
    window covers that passage" for every selection. Strip the language
    directory and the .tess suffix explicitly, then collapse parts."""
    return base_work(work)


def _ref_numbers(ref):
    """Trailing numeric coordinates of a reference tag, e.g.
    'verg. aen. 6.268' -> (6, 268); 'hebrew_bible.genesis.41.47' -> (41, 47)."""
    nums = re.findall(r'\d+', str(ref or ''))
    return tuple(int(n) for n in nums[-2:]) if nums else ()


def _ref_numbers_in(work, ref):
    """_ref_numbers, protected from digits in the WORK name itself.

    'shenoute.a22.1' parsed bare gives (22, 1): the 22 is from the work name
    a22, and the reader's selection header then displayed lines 1-3 as
    "22.1-22.3". Both sides of the window match were polluted the same way,
    which happened to cancel out, but any comparison against an unpolluted
    ref breaks. Strip the work name (in any of its forms) off the front
    before reading digits."""
    s = str(ref or '')
    w = _norm_work(work)
    for prefix in (str(work or ''), w):
        if prefix and s.startswith(prefix):
            s = s[len(prefix):]
            break
    nums = re.findall(r'\d+', s)
    if not nums:
        return _ref_numbers(ref)
    return tuple(int(n) for n in nums[-2:])


def _ref_coords(ref):
    """EVERY numeric coordinate, for comparing two spans of the same work.

    _ref_numbers keeps only the last two, which is right for its own callers and
    wrong for overlap tests. Ammianus is referenced book.chapter.section, so
    'amm. 21.13.14' becomes (13, 14) and 'amm. 17.13.30' becomes (13, 30): the
    book is discarded and two passages four books apart compare as overlapping.
    The dedup then drops one of them, silently, from a live Theme Search page.

    Caught by the automated review on PR #269, which flagged the tuple
    comparison as suspicious without knowing it already had a victim. Verified
    against real Ammianus references before the fix and after.

    Differing lengths are safe here because this only ever compares references
    within ONE work, where the citation depth is consistent.
    """
    return tuple(int(n) for n in re.findall(r'\d+', str(ref or '')))


def is_available():
    """True when the index files are present and consistent.

    Deliberately does NOT load the index. It used to, and that made a question
    as cheap as "is this feature on?" cost 1.2GB of embeddings: the per-request
    tool list calls this, and so does startup. A reference test that only wanted
    to run a line search was OOM-killed at 16GB because asking this question
    pulled in the whole passage index.

    Presence and agreement of the three files is what "available" means. A file
    that is present but corrupt still fails at load time, and _state['error']
    then carries the reason, which is why a completed load takes precedence.
    """
    if _state['loaded']:
        return _state['ok']
    try:
        ids_path = os.path.join(_DATA_DIR, 'ids.json')
        emb_path = os.path.join(_DATA_DIR, 'embeddings.npy')
        desc_path = os.path.join(_DATA_DIR, 'descriptions.jsonl')
        return all(os.path.getsize(p) > 0 for p in (ids_path, emb_path, desc_path))
    except OSError:
        return False


def index_version():
    """A date stamp for the passage index, for citing a Theme Search.

    The per-language inverted indexes carry a corpus_version in a meta table;
    this index has no such table, so the stamp comes from the build date of
    ids.json, which is rewritten whenever windows are added or dropped. Same
    fallback the inverted index uses when its stamp is missing. Returns None
    rather than raising: a missing stamp costs a clause in a citation
    (2026-09-08).
    """
    try:
        import datetime
        p = os.path.join(_DATA_DIR, 'ids.json')
        return datetime.date.fromtimestamp(os.path.getmtime(p)).isoformat()
    except Exception:                                            # noqa: BLE001
        return None


def status():
    _ensure_loaded()
    return {
        'available': _state['ok'],
        'error': _state['error'],
        'index_version': index_version(),
        'windows': len(_ids) if _ids else 0,
        'works': len(_by_work) if _by_work else 0,
        'model': EMBED_MODEL,
        'strong_lift': STRONG_LIFT,
        'weak_lift': WEAK_LIFT,
        'head_weak': HEAD_WEAK,
        'head_strong': HEAD_STRONG,
        'confidence_mode': CONF_MODE,
        'combined_weak': COMBINED_WEAK,
        'combined_strong': COMBINED_STRONG,
        'fitted_at_windows': FITTED_AT_WINDOWS,
        'confidence_file': _state.get('confidence_file'),
    }


_works_by_language_cache = {}  # language -> [base work id, ...]
_sidecar_written = False  # this worker has already tried writing the sidecar once

WORKS_SIDECAR_FILENAME = 'works_by_language.json'


def _works_sidecar_path():
    return os.path.join(_DATA_DIR, WORKS_SIDECAR_FILENAME)


def _read_works_sidecar():
    """Read the works-by-language sidecar, if present and current.

    Right after a deploy touches the wsgi file, all three Apache workers
    reload and each one pays the ~90-second, ~2GB cost of _ensure_loaded()
    on its first request. Browse Corpus asks "which works have Theme
    Search coverage" during exactly that window, and a slow or failed
    answer used to render as "0 of 782 works covered" -- indistinguishable
    from a real gap. This sidecar answers the question from a few KB on
    disk instead, with no index load at all.

    Returns the sidecar's {language: [work id, ...]} mapping, or None if
    the file is absent, unreadable, or stamped with a different
    index_version than what's on disk right now (a rebuild in progress,
    or a stale file a previous index left behind). A version mismatch
    means the caller must fall back to _ensure_loaded() rather than serve
    a wrong answer quickly.
    """
    try:
        with open(_works_sidecar_path(), encoding='utf-8') as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get('index_version') != index_version():
        return None
    languages = payload.get('languages')
    return languages if isinstance(languages, dict) else None


def _write_works_sidecar(languages):
    """Write the works-by-language sidecar, best-effort.

    Called once per worker, right after the first successful
    _ensure_loaded(), so production gets the file after one warm request
    with no rebuild needed. (The index build script also writes this file
    directly, so a fresh deploy usually never needs this lazy path at
    all.) A write failure -- read-only mount, a race with another worker,
    the directory missing in a dev checkout -- is swallowed: the sidecar
    is a speed-up, never a dependency, and _ensure_loaded() is always the
    fallback.
    """
    try:
        tmp = _works_sidecar_path() + '.tmp'
        payload = {'index_version': index_version(), 'languages': languages}
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, _works_sidecar_path())
    except OSError as e:
        logger.warning('[PASSAGES] could not write works-by-language sidecar: %s', e)


def _compute_works_by_language():
    """Every language's work list, in one pass over the loaded index.

    Assumes _ensure_loaded() has already run. Same membership test
    works_for_language used before the sidecar existed: a work counts for
    a language if any one of its rows carries that language.
    """
    by_lang = {}
    if _by_work and _records:
        for work, rows in _by_work.items():
            langs = {_records[row].get('language') for row in rows}
            for lang in langs:
                if lang:
                    by_lang.setdefault(lang, set()).add(work)
    return {lang: sorted(works) for lang, works in by_lang.items()}


def works_for_language(language):
    """Base work ids that have at least one passage window in this language.

    Feeds the Browse Corpus "Theme Search" badge: a work with no rows here
    never appears in Theme Search or Similar Passages results. Mirrors
    translations.available() in spirit.

    Tries the on-disk sidecar first, which costs a small file read and
    nothing else. Only when that sidecar is missing or stale does this
    load the full passage index (_ensure_loaded(), ~2GB, ~90s on a cold
    worker) to compute the answer directly -- and it then writes the
    sidecar so the next call, in this worker or the next one, skips the
    load. Cached per worker either way, since the answer does not change
    for the life of the process.
    """
    global _sidecar_written
    if language in _works_by_language_cache:
        return _works_by_language_cache[language]

    sidecar = _read_works_sidecar()
    if sidecar is not None:
        for lang, works in sidecar.items():
            _works_by_language_cache.setdefault(lang, list(works))
        if language in _works_by_language_cache:
            return _works_by_language_cache[language]
        # Sidecar is current but silent on this language (e.g. a language
        # added since it was written without windows yet): fall through to
        # the loaded index rather than guess.

    _ensure_loaded()
    full = _compute_works_by_language()
    for lang, works in full.items():
        _works_by_language_cache.setdefault(lang, works)
    _works_by_language_cache.setdefault(language, [])
    if not _sidecar_written and _state['ok']:
        _write_works_sidecar(full)
        _sidecar_written = True
    return _works_by_language_cache.get(language, [])


def _ensure_loaded():
    global _ids, _records, _emb, _by_work, _by_language
    if _state['loaded']:
        return
    with _lock:
        if _state['loaded']:
            return
        _state['loaded'] = True
        try:
            import numpy as np
            ids_path = os.path.join(_DATA_DIR, 'ids.json')
            emb_path = os.path.join(_DATA_DIR, 'embeddings.npy')
            desc_path = os.path.join(_DATA_DIR, 'descriptions.jsonl')
            missing = [p for p in (ids_path, emb_path, desc_path) if not os.path.exists(p)]
            if missing:
                _state['error'] = f"passage index not built ({', '.join(os.path.basename(m) for m in missing)} absent)"
                logger.info('[PASSAGES] %s', _state['error'])
                return
            _ids = json.load(open(ids_path, encoding='utf-8'))
            by_id = {}
            with open(desc_path, encoding='utf-8') as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    by_id[r['id']] = r
            _records = [by_id.get(i, {'id': i}) for i in _ids]
            # mmap keeps the matrix on disk; rows are read per query.
            _emb = np.load(emb_path, mmap_mode='r')
            if _emb.shape[0] != len(_ids):
                _state['error'] = f'index mismatch: {_emb.shape[0]} embeddings vs {len(_ids)} ids'
                logger.error('[PASSAGES] %s', _state['error'])
                return
            _by_work = {}
            by_lang_lists = {}
            for i, r in enumerate(_records):
                _by_work.setdefault(_norm_work(r.get('work')), []).append(i)
                by_lang_lists.setdefault(r.get('language'), []).append(i)
            # One language's row indices, for a single-language Theme Search
            # to measure its OWN score distribution rather than borrowing the
            # whole, multilingual corpus's (see _language_rows below).
            _by_language = {lg: np.asarray(rows, dtype=np.int64)
                            for lg, rows in by_lang_lists.items() if lg}
            _state['ok'] = True
            _apply_index_confidence()
            # WINDOWS WITH NO DESCRIPTION ARE POISON. 128 records were never
            # described, and an empty description embeds near the centre of the
            # space, so it is weakly similar to EVERYTHING. They dominated any
            # query without strong signal: "plague", "airplanes" and
            # "television" all returned the same undescribed passages, and the
            # head lift that decides confidence was computed over them.
            #
            # They carry no information and can only mislead, so they are
            # excluded from ranking. They stay in the index, keeping ids and
            # embedding rows in lockstep, and should be re-described.
            global _undescribed
            # _records is a LIST in embedding-row order, not a dict.
            _undescribed = {i for i, rec in enumerate(_records)
                            if not ((rec or {}).get('desc') or {})
                            .get('gist', '').strip()}
            if _undescribed:
                logger.warning('[PASSAGES] %d windows have no description and are '
                               'excluded from results', len(_undescribed))
            logger.info('[PASSAGES] index ready: %d windows, %d works, dim %d',
                        len(_ids), len(_by_work), _emb.shape[1])
        except Exception as e:  # index problems must not break the app
            _state['error'] = f'{type(e).__name__}: {e}'
            logger.error('[PASSAGES] index load failed: %s', _state['error'])


# The query encoder runs as its own service, not inside the web application.
# See services/embed_server.py for why: Apache runs three workers that recycle
# every 1000 requests, so an in-process model would be loaded three times over
# and reloaded, at 22 seconds a time, forever.
EMBED_ENDPOINT = os.environ.get('TESSERAE_EMBED_ENDPOINT', 'http://127.0.0.1:8090')
EMBED_TIMEOUT = 60


class EmbedUnavailable(RuntimeError):
    """The encoder service could not be reached. Say so; never guess a vector."""


def embed_query(text):
    """One query string to its vector, via the encoder service.

    Returns a float32 numpy array. Raises EmbedUnavailable if the service is not
    running, which the caller turns into an honest "unavailable" rather than an
    empty result set: no results and cannot ask are different answers, and only
    one of them means the corpus lacks the subject.
    """
    import json as _json
    import urllib.error
    import urllib.request

    import numpy as np

    payload = _json.dumps({'texts': [text], 'normalize': True}).encode('utf-8')
    req = urllib.request.Request(f'{EMBED_ENDPOINT}/embed', data=payload,
                                 headers={'Content-Type': 'application/json'})
    try:
        # A fixed http(s) endpoint from configuration, never user input.
        with urllib.request.urlopen(req, timeout=EMBED_TIMEOUT) as r:  # nosec B310
            body = _json.loads(r.read())
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise EmbedUnavailable(
            f'the query encoder service is not reachable at {EMBED_ENDPOINT}: {e}'
        ) from e
    vectors = body.get('vectors') or []
    if not vectors:
        raise EmbedUnavailable(f'encoder returned no vector: {body.get("error")}')
    return np.asarray(vectors[0], dtype=np.float32)


def encoder_available():
    """True when the encoder service answers. Cheap: does not load the model."""
    import urllib.error
    import urllib.request
    try:
        # A fixed http(s) endpoint from configuration, never user input.
        with urllib.request.urlopen(f'{EMBED_ENDPOINT}/health', timeout=3) as r:  # nosec B310
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


# Query scoring is one pass over the whole embedding matrix, 785 MB at the
# current index size, and numpy's matrix-vector product is SINGLE-THREADED. So
# every Theme Search and every Similar Passages query ran on one core while the
# other thirty-one idled. Splitting the matrix across threads is a measured 4.1x
# (1.15s to 0.29s on 383,201 windows), and it needs no extra memory: each thread
# converts and multiplies its own slice, so the 1.5 GB float32 copy the old path
# allocated in one block never exists.
#
# The GIL is not a problem here because numpy releases it inside the BLAS call.
_SCORE_THREADS = min(16, max(2, (os.cpu_count() or 4) - 2))


def _mask_undescribed(scores):
    """Put undescribed windows out of reach.

    Done to the SCORES rather than at ranking time, because the confidence
    measure reads the score distribution: leaving them in made head lift a
    measure of how well the query matched a passage with no description.
    """
    if _undescribed:
        import numpy as np
        idx = np.fromiter(_undescribed, dtype=np.int64, count=len(_undescribed))
        idx = idx[idx < scores.shape[0]]
        scores[idx] = -1.0
    return scores


def _score_all(q):
    """Cosine-ish scores of every window against a query vector, in parallel."""
    import numpy as np
    from concurrent.futures import ThreadPoolExecutor
    n = _emb.shape[0]
    out = np.empty(n, dtype=np.float32)
    step = (n + _SCORE_THREADS - 1) // _SCORE_THREADS

    def part(i):
        lo = i * step
        hi = min(n, lo + step)
        if lo < hi:
            out[lo:hi] = np.asarray(_emb[lo:hi], dtype=np.float32) @ q

    with ThreadPoolExecutor(_SCORE_THREADS) as ex:
        list(ex.map(part, range(_SCORE_THREADS)))
    return out


def _score_block(rows, chunk=32768):
    """Scores of every window against EACH of `rows`, as an (N, len(rows)) array.

    The batched counterpart to _score_all. Same arithmetic, one BLAS call per
    chunk instead of one per query, which is the difference between re-reading
    the corpus once per query and reading it once in total.

    Chunked so no full float32 copy of the corpus ever exists.
    """
    import numpy as np
    n = _emb.shape[0]
    q = np.asarray(_emb[rows], dtype=np.float32).T      # (D, len(rows))
    out = np.empty((n, len(rows)), dtype=np.float32)
    for i in range(0, n, chunk):
        j = min(n, i + chunk)
        out[i:j] = np.asarray(_emb[i:j], dtype=np.float32) @ q
    return out


def index_fingerprint():
    """Short identifier that changes whenever the index does, from file stats.

    Anything cached off this index has to be dropped when it changes. Adding a
    text alters the answer for passages throughout the corpus, not only in the
    new work: gutter density asks how many OTHER works hold a similar passage,
    so one new text moves it everywhere. A cache keyed on the work name alone
    would serve stale densities after every addition and nobody would notice.

    COSTS NOTHING TO COMPUTE. It used to call _ensure_loaded() for len(_ids),
    so asking "which index is this?" pulled the whole 1.2 GB index into memory --
    thirteen seconds on a worker that had not loaded it yet. Since this names
    the density cache file, even a cache HIT paid that, and Apache recycles
    workers every 1000 requests, so the Reader went back to being slow at
    intervals for no reason at all.

    Size and mtime of the two index files change whenever the index changes,
    which is the only guarantee required, and every worker computes the same
    value without reading anything.
    """
    parts = []
    for name in ('ids.json', 'embeddings.npy'):
        try:
            st = os.stat(os.path.join(_DATA_DIR, name))
            parts.append(f'{st.st_size}-{int(st.st_mtime)}')
        except OSError:
            parts.append('0-0')
    return '.'.join(parts)


# Author dates, for putting results in chronological order. The same table the
# rest of the site uses, so a date here matches a date anywhere else.
_DATES = None


def _author_dates():
    global _DATES
    if _DATES is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'author_dates.json')
        try:
            with open(path, encoding='utf-8') as fh:
                _DATES = json.load(fh)
        except (OSError, ValueError):
            _DATES = {}
    return _DATES


def _dating(work, language):
    """year / era / note for a work, or empty when the author is not dated.

    Persian, Urdu and Arabic authors are absent from the table, so those results
    carry no date. They are shown as undated rather than guessed at, and sorted
    after everything that has one.
    """
    key = str(work or '').split('.')[0].lower()
    info = (_author_dates().get(language) or {}).get(key)
    if not info:
        return {}
    # The preview trimmed notes at the first semicolon and dropped parentheses
    # because its Persian, Urdu and Arabic rows carried curation remarks. On
    # the production table that rule cut real dating: "Greek philosopher
    # (d. 322 BCE); Latin translations ..." lost its date, and "fl. c. 55 CE
    # (date contested; ...)" was left with an open parenthesis. The note is
    # shown as written; clean the table rows instead.
    return {'year': info.get('year'), 'era': info.get('era'),
            'date_note': info.get('note')}


def _naming(work):
    """author / title / display_name for a work id, or {} if it cannot be read."""
    if not work:
        return {}
    try:
        from backend.utils import get_text_metadata
        m = get_text_metadata(f'{work}.tess')
    except Exception:
        return {}
    author = m.get('author')
    title = m.get('title') or m.get('work')
    display = ', '.join(x for x in (author, title) if x)
    out = {'author': author, 'title': title,
           'display_name': m.get('display_name') or display or None}
    # Licensed for indexing and search only: Similar Passages, Theme Search
    # and Theme Comparison all build their result cards from this function,
    # so flagging it here is the one place that reaches every one of them.
    if restricted_texts.is_restricted(work):
        out['restricted'] = True
        out['credit'] = restricted_texts.credit_for(work)
    return out


def _result(row, score, strong=None, extra=None):
    r = _records[row]
    d = r.get('desc') or {}
    out = {
        'id': r.get('id'),
        'language': r.get('language'),
        'work': r.get('work'),
        'scale': r.get('scale'),
        'ref_start': r.get('ref_start'),
        'ref_end': r.get('ref_end'),
        'score': round(float(score), 4),
        'strong': bool(strong) if strong is not None else None,
        'gist': d.get('gist'),
        'themes': d.get('themes') or [],
        'mode': d.get('mode'),
        # Whether the people this description names actually appear in the
        # passage. False means the summary identified someone the text does not
        # name, which is sometimes sound inference and sometimes the wrong
        # person, and a served result cannot tell those apart. None means the
        # question could not be asked: no names given, or a passage in Greek,
        # Hebrew or Coptic script where an English name would never match.
        'names_in_text': d.get('names_in_text'),
        # WHICH names could not be found, not just whether any could. The
        # verdict alone hid the case this exists for: Valerius Flaccus 1.1-30 is
        # described with "Apollo, Cumaean Sibyl, Aeneas". Apollo is there
        # (Phoebe, 1.5) and the Sibyl is there (Cumaeae uatis, 1.5). Aeneas is
        # not: 1.9 has Phrygios Iulos, and the summary reached from Iulus back
        # to Aeneas. The record passed on Apollo's strength and said nothing.
        #
        # Unverified is NOT proof of invention. A passage may call Jupiter
        # 'Pater' or refer to Achilles only as 'he'. It marks a name worth
        # checking, which is what a reader can act on.
        'names_unverified': d.get('names_unverified') or [],
        **_dating(r.get('work'), r.get('language')),
        # A readable author and title. Results were showing the raw file id,
        # "aeschylus.seven_against_thebes", where the rest of the site says
        # "Aeschylus, Seven Against Thebes". Same source the corpus listing uses,
        # and it works from the filename alone, so it costs no file reads.
        **_naming(r.get('work')),
    }
    if extra:
        out.update(extra)
    return out


# Languages whose passage windows are held back from Theme Search and Similar
# Passages on this server (2026-10-06: Arabic, until a reader has graded it;
# the windows are indexed so opening it needs no rebuild). A server that serves
# the language through TESSERAE_LANGUAGES (the preview) shows it regardless.
# Override with TESSERAE_HELD_LANGUAGES (comma-separated; empty for none).
def held_languages():
    from backend.served_languages import allowed_languages
    raw = os.environ.get('TESSERAE_HELD_LANGUAGES')
    held = {'ar'} if raw is None else {x.strip() for x in raw.split(',') if x.strip()}
    served = allowed_languages()
    return held - served if served else held


def _rank(scores, limit, exclude_work=None, languages=None, scale=None,
          dedup=True, baseline=None, strong_at=None, exclude_span=None,
          per_work=None, only_works=None, offset=0):
    """Shared ranking: sort, filter, and collapse near-duplicate windows.

    Duplicates are real in this corpus: a work and its .part.N file both carry
    the same lines, and the fine/coarse scales overlap by design, so without a
    dedup pass a single passage can occupy an entire page of results.

    Scripture needs a second kind of dedup that no other text does. The corpus
    holds the Bible in Hebrew, Greek twice, Latin, English and Coptic twice, so
    asking what resembles Coptic Genesis 22 returns the same chapter in six
    versions before it returns anything a reader did not already know. Those are
    collapsed into one result carrying the other versions, and the passage the
    query itself came from is dropped, which is what `exclude_span` is for.

    `per_work` caps how many windows any one work may contribute, and
    `only_works` restricts the whole ranking to a chosen set. Both exist for the
    two-pass diversity in `find_by_text`; the default leaves ranking unchanged.

    `offset` skips the first `offset` positions of THIS SAME ranking -- same
    filters, same dedup, same per-work cap -- before `limit` results are
    collected. That is what lets Theme Search page past its normal cap: page 2
    is `_rank(scores, limit, offset=limit, ...)`, which lines up exactly with
    what page 1 already showed, rather than a fresh ranking that happens to use
    a bigger limit (which is how the existing 25/50/75/100 stepping works, and
    why it tops out at 100: `_int_arg` caps `limit` itself there).
    """
    import numpy as np
    if baseline is None:
        baseline = float(np.median(scores))
    floor = baseline + BASELINE_MARGIN
    if strong_at is None:
        strong_at = baseline + STRONG_LIFT
    held = held_languages()
    order = np.argsort(-scores)
    seen = {}          # work -> [(start, end)] already taken, for overlap dedup
    per_work_count = {}
    by_passage = {}       # canonical scripture span -> index into out
    # Scripture spans consumed while skipping toward `offset`. A later
    # duplicate of one of them (same verses, another version) has to be
    # dropped rather than merged: the entry it would merge into was never
    # added to `out` on this page, so there is nothing to hang it off.
    swallowed_spans = set()
    out = []
    rank = 0   # positions that have passed every filter; what `offset` counts
    for row in order:
        score = float(scores[row])
        if score < floor:
            break
        r = _records[row]
        work = _norm_work(r.get('work'))
        if exclude_work and work == exclude_work:
            continue
        if only_works is not None and work not in only_works:
            continue
        if per_work is not None and per_work_count.get(work, 0) >= per_work:
            continue
        if languages and r.get('language') not in languages:
            continue
        if held and r.get('language') in held:
            continue
        if scale and r.get('scale') != scale:
            continue
        if dedup:
            # OVERLAP, not an identical start. Keying on ref_start alone let
            # near-duplicates through, because two windows over the same lines
            # rarely begin on the same one: Caesar came back as both
            # 2.31.6-2.35.4 and 2.32.10-2.34.4, one wholly inside the other, and
            # Homer as both the whole Iliad and .part.17 for adjacent spans.
            # Claude desktop, testing the connector, counted these eating
            # ranking slots. Measured on one query, 9 of 75 results were the same
            # underlying text arriving twice.
            #
            # Iteration is in descending score, so the first window over a
            # stretch of text is the best one and later overlaps are dropped.
            lo = _ref_coords(r.get('ref_start'))
            hi = _ref_coords(r.get('ref_end')) or lo
            if lo > hi:
                lo, hi = hi, lo
            spans = seen.setdefault(work, [])
            if any(lo <= b and a <= hi for a, b in spans):
                continue
            spans.append((lo, hi))

        sp = scripture_id.span(work, r.get('ref_start'), r.get('ref_end'))
        if sp is not None:
            # The query's own passage in another version is not a finding.
            if exclude_span is not None and scripture_id.overlaps(sp, exclude_span):
                continue
            if sp in swallowed_spans:
                continue
            prev = by_passage.get(sp)
            if prev is not None:
                # Same verses, different version. Hang it off the entry already
                # there rather than spending another result slot on it.
                out[prev].setdefault('also_in', []).append({
                    'language': r.get('language'),
                    'work': r.get('work'),
                    'ref_start': r.get('ref_start'),
                    'score': round(score, 4),
                })
                continue

        # Everything above has decided whether this row occupies a genuine
        # position in the ranking (a new entry, not a duplicate or an
        # excluded one). THAT position is what `offset` pages against.
        if rank < offset:
            rank += 1
            per_work_count[work] = per_work_count.get(work, 0) + 1
            if sp is not None:
                swallowed_spans.add(sp)
            continue
        rank += 1

        result = _result(row, score, strong=score >= strong_at)
        if sp is not None:
            by_passage[sp] = len(out)
            result['scripture_ref'] = f'{sp[0]} {sp[1][0]}:{sp[1][1]}'
        per_work_count[work] = per_work_count.get(work, 0) + 1
        out.append(result)
        if len(out) >= limit:
            break
    return out


def _interleave_languages(heads, pool):
    """Compose a multi-language page by round-robin over each language's own
    ranking. A single global cutoff lets the biggest corpora own the page:
    "a parent sacrifices a child" filled every slot with Greek tragedy and
    Latin epic while the Akedah, the top Hebrew result, sat past the cutoff
    (2026-08-31). Measured on the 74-instance pilot benchmark at rank
    100: global cutoff 15, appended per-language guarantee 15, promoted
    guarantee 15-18, deeper per-work groups 15 and worse at the head, and
    THIS round-robin 18 with the head intact, so it shipped. Languages with
    nothing above the relevance floor are absent from the pool and get
    nothing: interleaving never fabricates relevance. The cycle order is
    each language's first appearance in the global ranking, so the page
    still opens with the strongest match overall.
    """
    by_lang, order = {}, []
    for r in pool:
        lg = r.get('language')
        if lg not in by_lang:
            by_lang[lg] = []
            order.append(lg)
        by_lang[lg].append(r)
    out, i = [], 0
    total = sum(len(v) for v in by_lang.values())
    while len(out) < len(heads) and len(out) < total:
        lg = order[i % len(order)]
        if by_lang[lg]:
            out.append(by_lang[lg].pop(0))
        i += 1
    return out


def _coherence_of_rows(rows):
    """How much a chosen set of windows (given as global row indices) agree
    with each other. The arithmetic _cluster_coherence runs on the top-k of
    the whole corpus; factored out so a single-language Theme Search can run
    the same measure on the top-k of ONE LANGUAGE's rows instead (see
    _language_rows)."""
    import numpy as np
    block = np.asarray(_emb[rows], dtype=np.float32)
    norms = np.linalg.norm(block, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    block = block / norms
    sim = block @ block.T
    n = len(rows)
    return float((sim.sum() - n) / (n * n - n)) if n > 1 else 0.0


def _cluster_coherence(scores, k=COHERENCE_K):
    """How much the top-k results agree with each other.

    A subject the corpus really holds returns a coherent cluster of passages;
    an absent subject returns scattered strays that resemble the query a little
    and each other hardly at all.
    """
    import numpy as np
    top = np.argsort(-scores)[:k]
    return _coherence_of_rows(top)


def _language_rows(languages):
    """Row indices for ONE selected language, or None when the request does
    not narrow to exactly one.

    Multi-language and the default "all languages" search keep measuring
    confidence against the whole corpus, which is what the bands below were
    fitted against. A single-language search is measured against that one
    language's own rows instead -- see _is_pervasive for why."""
    if not languages or len(languages) != 1 or not _by_language:
        return None
    return _by_language.get(languages[0])


# A description is a sentence. Below this, the confidence signals are not
# measuring anything: every probe the thresholds were fitted on is a full
# sentence, and raw similarity scales with query length, so a keyword and a
# description are not on the same footing at all.
#
# Measured on the live index:
#     "plague"                    lift 0.093  -> would read LOW, top hit is a
#                                                plague passage in Silius
#     "airplanes"                 lift 0.095  -> would read STRONG, top hit is
#                                                nothing of the kind
#
# "airplanes" outscores "plague". The band cannot be reported for queries like
# these, and reporting one anyway is worse than declining: it puts a confident
# label on a number that does not mean what it says.
# CONFIDENCE THAT WORKS AT ANY QUERY LENGTH (2026-08-25)
#
# The first measure compared the top hit against the corpus median, and raw
# similarity scales with query length, so a keyword and a sentence were not on
# the same footing. Measured on this index, "airplanes" outscored "plague".
#
# Two statistics fix it, and the second only works once the first has run:
#
# 1. DEGENERACY. When nothing in the corpus resembles the query, the top results
#    are uniformly distant from it and therefore identical to each other, and
#    coherence goes to exactly 1.000. That is not agreement, it is the absence of
#    any structure to agree about. Over a 28-query test set spanning one word to
#    ten, NINE queries were degenerate and every one of them was a subject the
#    corpus does not contain: airplanes, locomotive, telegraph, antibiotics,
#    spacecraft, photograph, submarine, television, airplanes-and-locomotives.
#
# 2. HEAD LIFT, the mean of the top ten above the median, rather than the single
#    top hit. A real subject brings a GROUP; a stray brings one lucky vector.
#    With the degenerate cases removed it separates cleanly and at every length:
#    present >= 0.080, absent <= 0.072.
#
# Neither works alone. Every magnitude statistic tried -- lift, z-score, robust
# z, ratio, head z-score -- topped out at 82% because "photograph" and
# "television" score high on all of them. Coherence alone reaches 57%.
# Fitted 2026-08-25 against BOTH probe sets at once, 57 queries from one word to
# ten: 91% accuracy with a single pair of thresholds. The old measure managed 93%
# on sentences alone and was unusable on keywords, where it rated "airplanes"
# above "plague".
DEGENERATE_COHERENCE = 0.995   # no structure at all: nothing resembles the query
HEAD_WEAK = 0.0750             # below this, the top ten are not a group
HEAD_STRONG = 0.1006           # above every absent subject in either probe set

# PERVASIVE THEMES, FITTED ON LATIN AND GREEK, MISREAD IN A LYRIC CORPUS
# (2026-10-08). head_lift and coherence above were measured against the whole,
# multilingual index, including for a search the caller narrowed to one
# language. That is backwards for a language where the asked-about theme is
# common: a Persian search for "passionate love" came back Rumi, Rudaki, and
# Anvari addressing the beloved -- on topic by any reading -- yet scored LOW
# (head_lift 0.0522, coherence 0.8996), because the one number the whole
# measure rests on, the corpus median, was the median of ALL 600,000-plus
# windows in seven languages, most of which are not love poetry. Loosen the
# query into a full sentence and the same bug still shows: every language this
# was probed against (fa, ur, la, grc, en, he, cop, and "all languages" with no
# filter) reported the IDENTICAL confidence block for the identical query text,
# because `languages` never reached the statistics at all, only the results
# list. Fixed below: a search narrowed to one language measures head_lift,
# coherence, baseline and top against THAT language's own rows (_language_rows),
# not the whole corpus. A multi-language or unfiltered search is unaffected.
#
# Restricting the measure does not, by itself, turn a pervasive theme's "low"
# into "strong": a love poem competing against the REST OF PERSIAN LYRIC still
# has a high bar to clear, because Persian lyric is largely about love already,
# which is exactly the situation that needs its OWN answer rather than either
# of the two the corpus already had. "Nothing like this exists" is false; "a
# clear, specific match" overstates it; the honest answer is a third thing --
# the theme is common here, so take what comes back as typical rather than
# as the one precise case.
#
# PERVASIVE_EXCESS_BASELINE operationalises that: how much higher is this one
# language's median score for the query than the WHOLE corpus's median for the
# same query. A theme equally rare (or equally common) everywhere scores near
# zero here; a theme concentrated in one language's own literature, which is
# exactly what drags its within-language head_lift down, pushes this well
# above zero. Reasoned from the existing BASELINE_MARGIN (0.010, the floor
# already used to tell signal from noise at this embedding's scale) rather
# than measured against real per-language score distributions: the service
# that holds those distributions is the one being patched, so there was
# nothing to calibrate this against before the fix shipped. Refit with
# evaluation/scripts/calibrate_confidence.py and a probe set built after
# deployment once single-language queries have run for a while; record the
# refit the way every other constant in this file has been.
PERVASIVE_EXCESS_BASELINE = 0.015


def _apply_index_confidence():
    """An index may carry its own fitted bands in confidence.json beside
    ids.json (2026-09-06): head_weak, head_strong, fitted_at_windows. A slice
    of the index served elsewhere (the Persian/Urdu/Arabic preview) has a
    different median for every lift to be measured against, so the numbers
    fitted for the full index are wrong there; a file next to the index says
    what they are for THAT index, and production, which has no such file,
    keeps its constants."""
    global HEAD_WEAK, HEAD_STRONG, FITTED_AT_WINDOWS, CONF_MODE, COMBINED_WEIGHT, COMBINED_WEAK, COMBINED_STRONG
    path = os.path.join(_DATA_DIR, 'confidence.json')
    if not os.path.exists(path):
        return
    try:
        import json
        d = json.load(open(path, encoding='utf-8'))
        HEAD_WEAK = float(d['head_weak'])
        HEAD_STRONG = float(d['head_strong'])
        FITTED_AT_WINDOWS = int(d.get('fitted_at_windows') or len(_ids or []))
        if d.get('mode') == 'combined':
            CONF_MODE = 'combined'
            COMBINED_WEIGHT = float(d.get('coherence_weight', 10.0))
            COMBINED_WEAK = float(d['combined_weak'])
            COMBINED_STRONG = float(d['combined_strong'])
        _state['confidence_file'] = path
        logger.info('[PASSAGES] confidence bands from %s: mode %s, head weak %.4f strong %.4f, combined weak %s strong %s, fitted at %d windows',
                    path, CONF_MODE, HEAD_WEAK, HEAD_STRONG, COMBINED_WEAK, COMBINED_STRONG, FITTED_AT_WINDOWS)
    except Exception:
        logger.warning('[PASSAGES] confidence.json unreadable; keeping the built-in bands', exc_info=True)


# An index's confidence.json may switch the rule to the combined score
# (head_lift*10 + (coherence-0.85)*weight) with its own two boundaries. On the
# Persian/Urdu/Arabic slice head lift alone separates present from absent
# subjects poorly (64% on 50 probes): subjects the corpus is saturated with sit
# close to everything, so their lift over the median is small even when the
# top hits are exact, and the agreement of the top group carries the signal.
CONF_MODE = 'head'
COMBINED_WEIGHT = 10.0
COMBINED_WEAK = None
COMBINED_STRONG = None


def _is_pervasive(baseline, global_baseline):
    """Is a weak or middling head_lift explained by the theme running through
    much of ONE language's own corpus, rather than by nothing resembling the
    query at all?

    `baseline` is the median score within the searched language alone;
    `global_baseline` is the median across the whole, multilingual corpus for
    the SAME query. Both None (no language narrowed the search) means the
    question does not apply. See PERVASIVE_EXCESS_BASELINE above."""
    if baseline is None or global_baseline is None:
        return False
    return (baseline - global_baseline) >= PERVASIVE_EXCESS_BASELINE


def _confidence_level(head_lift, coherence, baseline=None, global_baseline=None):
    """Graded, never certain. Works for one word or for a sentence.

    head_lift is the mean of the top ten scores above the corpus median (or,
    for a single-language search, above that language's own median).

    `baseline`/`global_baseline` are only given for a single-language search
    (see _language_rows) and only matter when head_lift would otherwise read
    'low' or 'moderate': they ask whether that is because nothing resembles
    the query, or because the query's theme is common enough in this one
    language that even a real, good match cannot clear much past a typical
    passage of it. The second case is reported as 'pervasive', a third
    outcome distinct from both 'low' (nothing resembles it) and a plain
    'moderate'/'strong' (a specific match, clear of the ordinary run of the
    language's own corpus).
    """
    if coherence >= DEGENERATE_COHERENCE:
        # No structure at all: every top result is the same distance from
        # the query, which is the absence of a match, not a common one.
        # Pervasiveness does not apply here.
        return 'low'
    pervasive = _is_pervasive(baseline, global_baseline)
    if CONF_MODE == 'combined' and COMBINED_WEAK is not None:
        combined = head_lift * 10.0 + (coherence - 0.85) * COMBINED_WEIGHT
        if combined < COMBINED_WEAK:
            return 'pervasive' if pervasive else 'low'
        if combined >= COMBINED_STRONG:
            return 'strong'
        return 'pervasive' if pervasive else 'moderate'
    if head_lift < HEAD_WEAK:
        return 'pervasive' if pervasive else 'low'
    if head_lift >= HEAD_STRONG:
        return 'strong'
    return 'pervasive' if pervasive else 'moderate'


def _calibration_drift():
    """How far the live index has moved from the one the bands were fitted to.

    Returns None when the index is not loaded or the drift is within tolerance.
    """
    try:
        n = len(_ids) if _ids is not None else 0
    except NameError:
        return None
    if not n or not FITTED_AT_WINDOWS:
        return None
    drift = abs(n - FITTED_AT_WINDOWS) / float(FITTED_AT_WINDOWS)
    return None if drift <= FITTED_TOLERANCE else (n, drift)


_UNCALIBRATED = (
    'This confidence band is provisional. The thresholds were fitted against an '
    'index of {fitted:,} windows and this index holds {now:,}, so the baseline '
    'they assume has moved. The passages below are unaffected; only the '
    'strong/moderate/low label is.')


# Names used only to write the pervasive-theme note in plain language (e.g.
# "the Persian corpus"). Mirrors the code -> name tables already kept in
# theme_pdf.py and blueprints/scholarship.py; a shared module would be
# cleaner, but three small, independent copies already exist in this
# codebase and this note is the only thing in this file that needs one.
_LANGUAGE_NAME = {
    'la': 'Latin', 'grc': 'Greek', 'en': 'English', 'cop': 'Coptic',
    'he': 'Hebrew', 'fa': 'Persian', 'ur': 'Urdu', 'ar': 'Arabic',
    'it': 'Italian', 'fro': 'Old French', 'gmh': 'Middle High German',
}

# A query of a few words is answered badly (see QUERY EXPANSION below): the
# index holds full-sentence descriptions, and a bare noun or two is not on
# the same footing as a sentence. Measured on probe queries built for this
# fix, a single word ("love", "wine", "prayer") read 'low' or 'pervasive'
# where the same subject written as a sentence read 'moderate' or 'strong'.
# Rather than silently answer a short query worse, say so.
_SHORT_QUERY_WORDS = 3


def _is_short_query(query):
    return len(re.findall(r'\w+', query or '')) <= _SHORT_QUERY_WORDS


_SHORT_QUERY_HINT = (
    ' This search was only a few words. Theme Search matches a full sentence '
    'much better than a single word or short phrase: try describing who does '
    'what, and where.')


def _confidence_note(level, query=None, language=None):
    drift = _calibration_drift()
    base = _confidence_note_fitted(level, language)
    if drift:
        now, _ = drift
        warning = _UNCALIBRATED.format(fitted=FITTED_AT_WINDOWS, now=now)
        base = f'{warning} {base}' if base else warning
    if base and level != 'strong' and query is not None and _is_short_query(query):
        base += _SHORT_QUERY_HINT
    return base


def _confidence_note_fitted(level, language=None):
    if level == 'strong':
        return None
    if level == 'pervasive':
        name = _LANGUAGE_NAME.get(language) if language else None
        corpus = f'the {name} corpus' if name else 'this part of the corpus'
        return (f'This theme runs through much of {corpus}, so these are typical '
                'examples. To find a particular kind of passage, describe what '
                'happens in it: who, doing what, where.')
    if level == 'moderate':
        return ('Moderate confidence: the corpus holds passages of this kind, but the '
                'match is looser than a clear case. Read the results before relying on them.')
    return ('The corpus does not appear to contain passages of this kind. Anything '
            'the search returns for it is a nearest neighbor, not a finding.')


# QUERY EXPANSION: make the query look like the thing being searched.
#
# The index is built from SENTENCES describing what happens in a passage, so it
# answers sentences. Measured 2026-08-25:
#
#   "warrior arming scene"                         Iliad 19.361 at rank 1440,
#                                                  0 of 245 arming windows in
#                                                  the top 50
#   "a warrior arms himself before battle"         rank 66, 7 in the top 50
#   "the shortness of life"                        best Seneca rank 31
#   "life is short"                                rank 1
#
# Templates in code recover some of it and not enough, because "a passage in
# which warrior arming scene" is not English and the embedding only drifts
# toward sentence-space. A model writes a real sentence, which lands in it.
#
# Also handles stance: Seneca argues life is NOT short, and embeddings handle
# negation poorly, so one paraphrase is asked to state the opposite.
EXPAND_ENDPOINT = os.environ.get('TESSERAE_EXPAND_ENDPOINT',
                                 'http://127.0.0.1:8081/v1/chat/completions')
EXPAND_TIMEOUT = 20
EXPAND_MAX_WORDS = 6        # longer queries are already sentences

_EXPAND_SYSTEM = """Rewrite a search query as sentences describing what happens in
a passage of ancient literature. Reply with JSON only: {"forms": ["...", "..."]}.

Give exactly three, each a short plain sentence:
  1. the query as a scene, in the present tense, saying who does what
  2. the same scene described differently
  3. the same subject stated the OTHER way round, so that a passage ARGUING
     about it is also matched. For "the shortness of life" that is "life is not
     short, it is wasted".

No commentary, no names the query did not give, nothing about literature or
authors. Just the scene."""

_expand_cache = {}
_expand_cache_mtime = [0.0]
# Expansions are written here so that a query keeps the same answer.
#
# Temperature 0 was NOT enough on its own: two identical calls minutes apart
# still came back with different sentences (observed 2026-08-26, three runs of
# tests/test_passage_diversity.py), and since scores here sit hundredths of a
# cosine apart, different sentences mean a different page. On top of that the
# site runs three Apache worker processes, so an in-memory cache alone would
# have given the same reader a different answer depending on which worker took
# the request.
#
# So the first expansion of a query is arbitrary and every one after it is
# fixed. Append-only, because three processes write to it.
# It lives under cache/ rather than beside the index because the index directory
# is not writable by the web user. Putting it there looked fine locally and did
# nothing in production: _save_expansion failed, logged at info level, and every
# request re-expanded, so two live searches for one query still came back in a
# different order. cache/ is where the app already writes at runtime.
EXPAND_CACHE_PATH = os.environ.get(
    'TESSERAE_EXPAND_CACHE',
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 'cache', 'query_expansions.jsonl'))


def _load_expansions():
    """Read the shared cache if another worker has written to it since we looked."""
    try:
        mtime = os.path.getmtime(EXPAND_CACHE_PATH)
    except OSError:
        return
    if mtime <= _expand_cache_mtime[0]:
        return
    try:
        with open(EXPAND_CACHE_PATH, encoding='utf-8') as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get('q') is not None:
                    _expand_cache[rec['q']] = rec.get('forms') or []
    except OSError:
        return
    _expand_cache_mtime[0] = mtime


def _save_expansion(q, forms):
    try:
        os.makedirs(os.path.dirname(EXPAND_CACHE_PATH), exist_ok=True)
        with open(EXPAND_CACHE_PATH, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'q': q, 'forms': forms}, ensure_ascii=False) + '\n')
        _expand_cache_mtime[0] = os.path.getmtime(EXPAND_CACHE_PATH)
    except OSError as e:
        # Warning, not info. This failing is not cosmetic: it silently returns
        # Theme Search to giving a different answer for the same query, which is
        # exactly how it went unnoticed the first time.
        logger.warning('[PASSAGES] could not persist query expansion to %s: %s. '
                       'The same query will give different results.',
                       EXPAND_CACHE_PATH, e)


def expand_query(query):
    """Sentence-shaped forms of a query, or [] when expansion is not wanted.

    Never raises and never blocks a search: if the model is unavailable the
    search proceeds with the query as typed.

    Temperature is 0 because the same query must give the same results. At 0.3
    it did not: two searches for "warrior arming scene" minutes apart returned
    different works, since a different paraphrase moves scores that sit five
    hundredths of a cosine apart across thousands of ranks. A scholar who cites
    a result has to be able to find it again.
    """
    q = (query or '').strip()
    if not q or len(q.split()) > EXPAND_MAX_WORDS:
        return []
    if q in _expand_cache:
        return _expand_cache[q]
    _load_expansions()
    if q in _expand_cache:
        return _expand_cache[q]
    import json as _json
    import re as _re
    import urllib.error
    import urllib.request
    body = _json.dumps({
        'messages': [{'role': 'system', 'content': _EXPAND_SYSTEM},
                     {'role': 'user', 'content': q}],
        'max_tokens': 220, 'temperature': 0.0, 'stream': False,
    }).encode('utf-8')
    req = urllib.request.Request(EXPAND_ENDPOINT, data=body,
                                 headers={'Content-Type': 'application/json'})
    forms = []
    try:
        # A fixed http(s) endpoint from configuration, never user input.
        with urllib.request.urlopen(req, timeout=EXPAND_TIMEOUT) as r:  # nosec B310
            out = _json.loads(r.read())
        txt = out['choices'][0]['message']['content'] or ''
        m = _re.search(r'\{.*\}', txt, _re.S)
        if m:
            forms = [str(f).strip() for f in (_json.loads(m.group(0)).get('forms') or [])
                     if str(f).strip()][:3]
    except (urllib.error.URLError, OSError, ValueError, KeyError) as e:
        logger.info('[PASSAGES] query expansion unavailable: %s', e)
    _expand_cache[q] = forms
    # A failed expansion is not cached: the model being down for one request is
    # no reason to answer that query without expansion for good.
    if forms:
        _save_expansion(q, forms)
    return forms


def _lexical_words(query):
    """Query words the word index should see: lower-cased, letters and
    digits only, English function words dropped (the curated list in
    backend/matcher.py; queries are English descriptions)."""
    from backend.matcher import DEFAULT_ENGLISH_STOP_WORDS
    words = []
    for w in re.split(r"[^\w']+", (query or '').lower()):
        w = w.strip("'")
        if len(w) > 1 and w not in DEFAULT_ENGLISH_STOP_WORDS and w not in words:
            words.append(w)
    return words


def _lexical_ready():
    """Whether the word index exists and describes THIS index's windows.
    Checked once per process; the answer is cached."""
    with _lex_lock:
        if _lex_state['checked']:
            return _lex_state['ok']
        _lex_state['checked'] = True
        if os.environ.get('THEME_LEXICAL', '1') in ('0', 'false', 'no'):
            logger.info('[PASSAGES] lexical boost disabled by THEME_LEXICAL')
            return False
        if not os.path.exists(_LEX_PATH):
            logger.warning('[PASSAGES] no word index at %s; Theme Search runs '
                           'without the lexical boost (scripts/build_desc_fts.py)', _LEX_PATH)
            return False
        try:
            import sqlite3
            conn = sqlite3.connect(f'file:{_LEX_PATH}?mode=ro', uri=True)
            meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
            conn.close()
            n = int(meta['rows'])
        except Exception as e:  # noqa: BLE001
            logger.warning('[PASSAGES] word index unreadable (%s); lexical boost off', e)
            return False
        n_desc = sum(1 for r in _records if r.get('desc'))
        if abs(n - n_desc) > max(50, n_desc // 100):
            logger.warning('[PASSAGES] word index has %d descriptions, the passage '
                           'index %d: stale, lexical boost off until it is rebuilt', n, n_desc)
            return False
        # An in-place edit of descriptions.jsonl keeps the count; the index
        # records the source file's size and mtime at build time, so compare
        # those too when the index carries them.
        desc_path = os.path.join(_DATA_DIR, 'descriptions.jsonl')
        if meta.get('source_size') and os.path.exists(desc_path):
            st = os.stat(desc_path)
            if str(st.st_size) != meta.get('source_size') or str(int(st.st_mtime)) != meta.get('source_mtime'):
                logger.warning('[PASSAGES] word index was built from a different '
                               'descriptions.jsonl (size or mtime differ): stale, lexical '
                               'boost off until it is rebuilt')
                return False
        _lex_state['row_by_id'] = {r.get('id'): i for i, r in enumerate(_records)}
        _lex_state['ok'] = True
        return True


def _lexical_boost(query, scores):
    """Add LEXICAL_BETA x normalised BM25 to the scores of the windows whose
    descriptions share words with the query. Returns the number of windows
    boosted (0 when the index is absent or the query has no content words).
    Modifies `scores` in place; call after the confidence figures are taken
    from the unboosted scores."""
    if not _lexical_ready():
        return 0
    words = _lexical_words(query)
    if not words:
        return 0
    import sqlite3
    match = ' OR '.join('"%s"' % w.replace('"', '') for w in words)
    try:
        conn = sqlite3.connect(f'file:{_LEX_PATH}?mode=ro', uri=True)
        rows = conn.execute('SELECT id, bm25(desc) FROM desc WHERE desc MATCH ? '
                            'ORDER BY bm25(desc) LIMIT ?', (match, LEXICAL_TOPN)).fetchall()
        conn.close()
    except Exception as e:  # noqa: BLE001
        logger.warning('[PASSAGES] lexical lookup failed (%s); no boost this query', e)
        return 0
    if not rows:
        return 0
    vals = [-b for _, b in rows]          # bm25() is negative, lower is better
    lo, hi = min(vals), max(vals)
    row_by_id = _lex_state['row_by_id']
    n = 0
    for (wid, _), v in zip(rows, vals):
        row = row_by_id.get(wid)
        if row is None or scores[row] <= -1.0:   # unknown id, or masked (undescribed)
            continue
        scores[row] += LEXICAL_BETA * ((v - lo) / (hi - lo) if hi > lo else 1.0)
        n += 1
    return n


def find_by_text(query, limit=25, languages=None, scale=None, expand=False,
                 offset=0):
    """Theme Search: free-text description of the wanted content.

    `expand` now defaults to False and no in-repo caller passes True: measured
    in `evaluation/theme_benchmark/expansion_test/REPORT.md`, expansion
    changed nothing on 15 of 16 test queries (it only ever runs for queries of
    six words or fewer) and on the one query it did touch, it pushed the
    corpus's one clear right answer (Odyssey 17, Argos) out of the top hundred
    entirely, a loss the reader re-rank could not recover from. The parameter
    and `expand_query` itself are left in place rather than removed.

    `offset` pages past the normal result set: results (offset+1) to
    (offset+limit) of the SAME ranking, not a re-run with a different cutoff.
    Verified 2026-09-10: passages a scholar would want for a broad topos --
    Alan of Lille Anticlaudianus 1.73, Nonnus Dionysiaca 3.147, Seneca Oedipus
    525, Pliny Letters 5.6.5 -- ranked 300 to 3000 for "a shaded natural spot
    with trees, a meadow, and a spring or brook", just past where the page
    used to stop with no way to see further. Results reached only by paging
    past the default view have their `strong` flag forced False: the
    confidence band was fitted to what page 1 shows, not to how deep a reader
    chooses to page, and individual scores can still clear STRONG_LIFT this
    deep because rank here is compressed, not confidence-ordered.
    """
    _ensure_loaded()
    if not _state['ok']:
        return {'error': _state['error'], 'results': []}
    if not (query or '').strip():
        return {'error': 'empty query', 'results': []}
    import numpy as np
    q = embed_query(_E5_PREFIX + query.strip()[:1500])
    scores = _mask_undescribed(_score_all(q))
    # A short query is probably a keyword or a noun phrase, which the index
    # answers badly. Score the sentence forms too and keep the best per window:
    # a passage that answers ANY reading of the query is a hit.
    forms = expand_query(query) if expand else []
    for f in forms:
        try:
            alt = _mask_undescribed(_score_all(embed_query(_E5_PREFIX + f[:1500])))
        except EmbedUnavailable:
            break
        scores = np.maximum(scores, alt)
    global_baseline = float(np.median(scores))
    # A search narrowed to ONE language is measured against that language's
    # own rows, not the whole, multilingual corpus: see the PERVASIVE THEMES
    # comment above HEAD_WEAK/HEAD_STRONG for why. `lang_rows` is None for a
    # multi-language or unfiltered ("all languages") search, which keeps the
    # original, whole-corpus measure unchanged.
    lang_rows = _language_rows(languages)
    # The GROUP at the head, not the single best hit, in both branches below:
    # one lucky vector is not a subject, and the top hit alone is what made
    # short queries unreadable.
    if lang_rows is not None and len(lang_rows):
        lang_scores = scores[lang_rows]
        baseline = float(np.median(lang_scores))
        top = float(lang_scores.max())
        k = min(10, len(lang_scores))
        head_lift = float(np.sort(lang_scores)[-k:].mean()) - baseline
        top_rows = lang_rows[np.argsort(-lang_scores)[:COHERENCE_K]]
        coherence = _coherence_of_rows(top_rows)
    else:
        baseline = global_baseline
        top = float(scores.max())
        k = min(10, len(scores))
        head_lift = float(np.sort(scores)[-k:].mean()) - baseline
        coherence = _cluster_coherence(scores)
    lift = top - baseline
    level = _confidence_level(
        head_lift, coherence,
        baseline=baseline if lang_rows is not None else None,
        global_baseline=global_baseline if lang_rows is not None else None)
    strong_at = baseline + (STRONG_LIFT if level == 'strong' else 1e9)
    # The confidence figures above describe the embedding alone; the lexical
    # boost then reorders the windows (see LEXICAL_BETA).
    n_lexical = _lexical_boost(query, scores)

    # WHY THE PAGE IS BUILT IN TWO PASSES
    #
    # Scores here are compressed to a degree that makes raw rank a poor guide:
    # on "warrior arming scene" the top window scored 0.8701 and rank 4546
    # scored 0.8174, so five hundredths of cosine covers four thousand places.
    # What fills a page is therefore not relevance but repetition. Ferdowsi's
    # and Nizami's Diwans are each ONE work holding tens of thousands of
    # windows, many described in near-identical words, and between them they
    # held 13 of the top 20 while the Aeneid sat at 89.
    #
    # So the works are chosen first, one window each, and only then is each
    # chosen work allowed to show its other strong passages. That keeps the
    # Iliad's four arming scenes, which a flat per-work cap would have thrown
    # away, while stopping any single work from owning the page.
    #
    #     scheme            Aeneid  Iliad  Odyssey  Thebaid   (display position)
    #     flat ranking          89      8       61        4
    #     one per work          19      5       14        3
    #
    # Measured on both "warrior arming scene" and the sentence form, with the
    # same ordering both times.
    heads = _rank(scores, limit, offset=offset, languages=languages, scale=scale,
                  baseline=baseline, strong_at=strong_at, per_work=1)
    # Multi-language pages are composed by per-language round-robin rather
    # than one global cutoff; see _interleave_languages for the measurements
    # behind the choice. `offset` shifts the pool the same way it shifts
    # `heads`, so an offset page's language mix starts where the previous
    # page's left off rather than repeating from the top.
    if not languages or len(languages) > 1:
        pool = _rank(scores, limit * 6, offset=offset, languages=languages,
                     scale=scale, baseline=baseline, strong_at=strong_at,
                     per_work=1)
        heads = _interleave_languages(heads, pool)
    # Works, not offset: once the (offset-adjusted) set of works for this page
    # is chosen, each one's own top passages are fetched from the start of ITS
    # ranking within `only_works`, same as page 1 -- offset only decided WHICH
    # works appear, not how many of a chosen work's passages to show.
    chosen = [_norm_work(r.get('work')) for r in heads]
    results = _rank(scores, limit * PASSAGES_PER_WORK, languages=languages,
                    scale=scale, baseline=baseline, strong_at=strong_at,
                    per_work=PASSAGES_PER_WORK, only_works=set(chosen))
    # Back into the order the first pass established, so the page still reads
    # best-work-first and each work's passages sit together.
    rank_of = {w: n for n, w in enumerate(chosen)}
    results.sort(key=lambda r: (rank_of.get(_norm_work(r.get('work')), 10**9),
                                -r.get('score', 0)))
    if offset:
        # Reached only by paging past the default view; see the docstring.
        for r in results:
            r['strong'] = False
    return {
        'query': query,
        'results': results,
        'strong_matches': sum(1 for r in results if r['strong']),
        'lexical_boost': n_lexical > 0,
        'confidence': {'top': round(top, 4), 'baseline': round(baseline, 4),
                       'head_lift': round(head_lift, 4),
                       'lift': round(lift, 4),
                       'coherence': round(coherence, 4), 'level': level},
        'note': _confidence_note(level, query=query,
                                 language=languages[0] if lang_rows is not None else None),
    }


# How many results each "in other languages" section holds (find_similar_to_window).
BY_LANGUAGE_K = 5


def _index_languages():
    """The languages present in the passage index, cached once loaded."""
    langs = _state.get('languages')
    if langs is None:
        langs = sorted({r.get('language') for r in _records if r.get('language')})
        _state['languages'] = langs
    return langs


def find_similar_to_window(window_id, limit=15, languages=None,
                           include_same_work=False, suppress_other_versions=True,
                           by_language=False):
    """Similar Passages, given an index window id.

    by_language (2026-10-07): also return, for every served language with fewer
    than BY_LANGUAGE_K results in the main list, that language's best matches
    above the ranking's similarity floor. The main list ranks all languages
    together, and the largest corpora fill it: an Urdu passage from Mir got 28
    Persian matches and 2 Urdu ones, because the index holds 220,000 Persian
    windows and 15,000 Urdu. The same rule serves every language, so a Latin
    passage shows its Greek and English matches the same way."""
    _ensure_loaded()
    if not _state['ok']:
        return {'error': _state['error'], 'results': []}
    try:
        row = _ids.index(window_id)
    except ValueError:
        return {'error': f'unknown window {window_id}', 'results': []}
    import numpy as np
    q = np.asarray(_emb[row], dtype=np.float32)
    scores = _mask_undescribed(_score_all(q))
    scores[row] = -1.0
    src = _records[row]
    exclude = None if include_same_work else _norm_work(src.get('work'))
    # When the query is itself a Bible passage, the same verses in the corpus's
    # other Bibles are not a discovery. Excluding the work alone does not cover
    # it: Coptic Genesis and Hebrew Genesis are different works.
    exclude_span = scripture_id.span(
        _norm_work(src.get('work')), src.get('ref_start'), src.get('ref_end')
    ) if suppress_other_versions else None
    baseline = float(np.median(scores))
    results = _rank(scores, limit, exclude_work=exclude, languages=languages,
                    baseline=baseline, exclude_span=exclude_span)
    top = results[0]['score'] if results else baseline
    by_lang = {}
    if by_language:
        shown = {r.get('id') for r in results}
        counts = Counter(r.get('language') for r in results)
        held = held_languages()
        for lang in _index_languages():
            if lang in held or (languages and lang not in languages):
                continue
            if counts.get(lang, 0) >= BY_LANGUAGE_K:
                continue
            sub = _rank(scores, BY_LANGUAGE_K + counts.get(lang, 0), exclude_work=exclude,
                        languages=[lang], baseline=baseline, exclude_span=exclude_span)
            sub = [r for r in sub if r.get('id') not in shown][:BY_LANGUAGE_K]
            if sub:      # every row _rank returns already clears the similarity floor
                by_lang[lang] = sub
    out_extra = {'by_language': by_lang} if by_language else {}
    return {
        **out_extra,
        'source': _result(row, 1.0, strong=True),
        'results': results,
        'confidence': {'top': round(float(top), 4), 'baseline': round(baseline, 4),
                       'lift': round(float(top) - baseline, 4)},
    }


def _ensure_names_loaded():
    """Open window_names.db once per process; return the cached connection,
    or None if the file is absent or unreadable (the feature is simply off).

    Caches the connection itself plus the name_df table (as a dict) and the
    window count from meta, read once, so every call after the first costs no
    disk access beyond the per-window lookups the caller itself does."""
    if _names_state['checked']:
        return _names_state['conn']
    with _names_lock:
        if _names_state['checked']:
            return _names_state['conn']
        _names_state['checked'] = True
        if not os.path.exists(_NAMES_PATH):
            logger.info('[PASSAGES] no name index at %s; "same people and '
                       'places" is off', _NAMES_PATH)
            return None
        try:
            import sqlite3
            conn = sqlite3.connect(f'file:{_NAMES_PATH}?mode=ro', uri=True,
                                   check_same_thread=False)
            meta = dict(conn.execute('SELECT key, value FROM meta'))
            n = int(meta.get('windows') or 0)
            # Per-script-group totals (windows_he, windows_cop, windows_fa,
            # windows_ur); a language without one uses 'windows' (Latin, Greek,
            # English). See scripts/corpus/build_window_names.py.
            n_by_lang = {k[len('windows_'):]: int(v) for k, v in meta.items()
                         if k.startswith('windows_') and str(v).isdigit()}
            df = dict(conn.execute('SELECT k, df FROM name_df'))
        except Exception as e:  # noqa: BLE001 -- a bad name index must not break Similar Passages
            logger.warning('[PASSAGES] window_names.db unreadable (%s); "same '
                           'people and places" is off', e)
            return None
        _names_state['conn'] = conn
        _names_state['df'] = df
        _names_state['N'] = n
        _names_state['N_by_lang'] = n_by_lang
        return conn


def _name_idf(k, df, n):
    return math.log(n / (1 + df.get(k, 0))) if n else 0.0


def same_names_for_window(wid, limit=12):
    """The "same people and places" grouping for a Similar Passages window:
    other windows that share RARE proper names with this one, scored by
    content similarity plus a bonus for the rarity of what they share.

    Returns None when the name index is missing or the window itself is not
    in the passage index (the feature does not apply, nothing else changes).
    Otherwise a dict: 'results' (up to `limit`, shaped like find_similar_to_
    window's, each carrying 'shared_names'), 'commentaries' (up to 5 more,
    for works that comment on a text rather than tell their own story, kept
    separate so they do not crowd out independent witnesses), 'strength'
    (summed rarity of the source window's own rare names) and 'weak' (True
    when that strength is thin -- a famous single name, say -- so the caller
    can show the group collapsed).
    """
    _ensure_loaded()
    if not _state['ok']:
        return None
    conn = _ensure_names_loaded()
    if conn is None:
        return None
    row = _row_of(wid)
    if row is None:
        return None
    import numpy as np
    src = _records[row]
    src_work = _norm_work(src.get('work'))
    qvec = np.asarray(_emb[row], dtype=np.float32)

    src_rows = conn.execute('SELECT k, form FROM window_names WHERE id=?', (wid,)).fetchall()
    src_form = {}
    for k, form in src_rows:
        src_form.setdefault(k, form)

    df = _names_state['df']
    n = _names_state.get('N_by_lang', {}).get(src.get('language')) or _names_state['N']
    rare = {k: _name_idf(k, df, n) for k in src_form}
    rare = {k: v for k, v in rare.items() if v > NAMES_IDF_THRESHOLD}
    strength = sum(v - NAMES_IDF_THRESHOLD for v in rare.values())

    cand_keys = {}  # row index -> set of shared keys
    if rare:
        held = held_languages()
        marks = ','.join('?' * len(rare))
        hits = conn.execute(
            f'SELECT id, k FROM window_names WHERE k IN ({marks})',  # nosec B608 -- marks is a run of '?', values are bound params
            list(rare.keys())).fetchall()
        for cwid, k in hits:
            if cwid == wid:
                continue
            crow = _row_of(cwid)
            if crow is None or crow in _undescribed:
                continue
            crec = _records[crow]
            if (crec.get('scale') or 'fine') != 'fine':
                continue
            if _norm_work(crec.get('work')) == src_work:
                continue
            if crec.get('language') in held:
                continue
            cand_keys.setdefault(crow, set()).add(k)

    scored = []
    for crow, ks in cand_keys.items():
        cvec = np.asarray(_emb[crow], dtype=np.float32)
        score = float(np.dot(qvec, cvec)) + NAMES_LAMBDA * sum(
            rare[k] - NAMES_IDF_THRESHOLD for k in ks)
        shared = [src_form[k] for k in sorted(ks, key=lambda k: -rare[k])]
        scored.append((score, crow, shared))
    scored.sort(key=lambda x: -x[0])

    def is_commentary(crow):
        work = str(_records[crow].get('work') or '')
        return any(marker in work for marker in NAMES_COMMENTARY_MARKERS)

    main = [s for s in scored if not is_commentary(s[1])]
    commentary = [s for s in scored if is_commentary(s[1])]
    results = [_result(r, sc, extra={'shared_names': shared})
              for sc, r, shared in main[:limit]]
    commentaries = [_result(r, sc, extra={'shared_names': shared})
                   for sc, r, shared in commentary[:5]]
    return {
        'results': results,
        'commentaries': commentaries,
        'strength': round(strength, 4),
        'weak': strength < NAMES_WEAK_STRENGTH,
    }


# --------------------------------------------------------------------------
# Theme comparison: two works, by content
# --------------------------------------------------------------------------
# Asked "what does Theme Search show about these two books", the assistant
# could only say that Theme Search reads the whole corpus. This is the pairwise
# form: every window of one work scored against every window of the other on
# the same vectors Similar Passages uses, the best pairs returned with both
# descriptions, so that the two poems can be read against each other by what
# happens in them rather than by shared words. Live, not from the connections
# map, so a pair of books works as well as a pair of works and nothing has to
# be prebuilt.
COMPARE_PAIR_LIMIT = 200
COMPARE_BLOCK = 512
COMPARE_MAX_CELLS = 40_000_000   # rows_a x rows_b beyond this is refused


def _rows_for_work(work, scale=None):
    """Row indexes for a work or a book file. A whole work stored as book
    files (vergil.aeneid) gathers its books' windows."""
    key = _norm_work(work)
    rows = list(_by_work.get(key) or [])
    if not rows:
        prefix = key + '.part.'
        for k, v in _by_work.items():
            if k.startswith(prefix):
                rows.extend(v)
    # _norm_work folds a book into its work, so asked for one book, keep only
    # the windows whose own record names that book.
    asked = str(work or '').replace('.tess', '')
    if '.part.' in asked:
        rows = [r for r in rows if str(_records[r].get('work') or '') == asked]
    if scale:
        rows = [r for r in rows if (_records[r].get('scale') or 'fine') == scale]
    if _undescribed:
        rows = [r for r in rows if r not in _undescribed]
    return sorted(rows)


def compare_works(work_a, work_b, scale='fine', limit=50, per_window=3):
    """The passage pairs of two works that most resemble each other in content.

    Returns pairs ordered by score, each window of work_a contributing at
    most `per_window` partners, deduplicated on the unordered pair. The
    confidence block reads the whole score matrix: `baseline` is its median,
    `head_lift` the mean of the top ten above it, and `level` follows the
    Theme Search convention that a lift of STRONG_LIFT or more is strong.
    """
    _ensure_loaded()
    if not _state['ok']:
        return {'error': _state['error'], 'pairs': []}
    import numpy as np
    limit = max(1, min(int(limit or 50), COMPARE_PAIR_LIMIT))
    per_window = max(1, min(int(per_window or 3), 10))
    rows_a = _rows_for_work(work_a, scale)
    rows_b = _rows_for_work(work_b, scale)
    if scale == 'fine' and (not rows_a or not rows_b):
        rows_a = rows_a or _rows_for_work(work_a, 'coarse')
        rows_b = rows_b or _rows_for_work(work_b, 'coarse')
    if not rows_a or not rows_b:
        missing = work_a if not rows_a else work_b
        return {'error': f'no described passage windows for {missing}', 'pairs': [],
                'n_a': len(rows_a), 'n_b': len(rows_b)}
    if len(rows_a) * len(rows_b) > COMPARE_MAX_CELLS:
        return {'error': 'these two works are too large to compare window by window '
                         'in one request; compare a book of each', 'pairs': [],
                'n_a': len(rows_a), 'n_b': len(rows_b)}
    E_b = np.asarray(_emb[rows_b], dtype=np.float32)
    idx_b = np.asarray(rows_b)
    candidates = []
    sample = []
    for lo in range(0, len(rows_a), COMPARE_BLOCK):
        chunk = rows_a[lo:lo + COMPARE_BLOCK]
        S = np.asarray(_emb[chunk], dtype=np.float32) @ E_b.T
        # A strided sample of the matrix for the baseline: deterministic, so the
        # level does not flip between runs, and the whole matrix when it is
        # small (the stride is 1 below 20,000 cells). Memory at the ceiling of
        # COMPARE_MAX_CELLS is E_b (n_b x dims float32, tens of MB for the
        # largest work) plus one block of 512 rows of scores, never the whole
        # matrix.
        if len(sample) < 200_000:
            sample.append(S.ravel()[:: max(1, S.size // 20_000)])
        k = min(per_window, S.shape[1])
        top = np.argpartition(-S, k - 1, axis=1)[:, :k]
        for i, row_a in enumerate(chunk):
            for j in top[i]:
                candidates.append((float(S[i, j]), row_a, int(idx_b[j])))
    flat = np.concatenate(sample) if sample else np.zeros(1, dtype=np.float32)
    baseline = float(np.median(flat))
    candidates.sort(key=lambda c: -c[0])
    seen, pairs = set(), []
    for score, ra, rb in candidates:
        key = (min(ra, rb), max(ra, rb))
        if key in seen:
            continue
        seen.add(key)
        lift = score - baseline
        pairs.append({'score': round(score, 4), 'lift': round(lift, 4),
                      'strong': bool(lift >= STRONG_LIFT),
                      'a': _result(ra, score), 'b': _result(rb, score)})
        if len(pairs) >= limit:
            break
    head = [p['score'] for p in pairs[:10]]
    head_lift = (sum(head) / len(head) - baseline) if head else 0.0
    level = ('strong' if head_lift >= STRONG_LIFT else
             'moderate' if head_lift >= STRONG_LIFT / 2 else 'low')
    return {
        'work_a': {'work': _norm_work(work_a), **_naming(_norm_work(work_a))},
        'work_b': {'work': _norm_work(work_b), **_naming(_norm_work(work_b))},
        'scale': (_records[rows_a[0]].get('scale') or 'fine'),
        'n_a': len(rows_a), 'n_b': len(rows_b),
        'pairs': pairs,
        'confidence': {'top': round(head[0], 4) if head else None,
                       'baseline': round(baseline, 4),
                       'head_lift': round(head_lift, 4), 'level': level},
    }

def _ref_coords_in(work, ref):
    """EVERY numeric coordinate of `ref`, with the work name stripped first
    (as _ref_numbers_in does), for locating a span inside one work."""
    s = str(ref or '')
    w = _norm_work(work)
    for prefix in (str(work or ''), w):
        if prefix and s.startswith(prefix):
            s = s[len(prefix):]
            break
    nums = re.findall(r'\d+', s)
    return tuple(int(n) for n in nums) if nums else _ref_coords(ref)


def window_for_passage(work, ref_start=None, ref_end=None, prefer='fine'):
    """Map a reader selection to the index window that best covers it.

    The Reader hands us a work and a reference span; the index is built on fixed
    overlapping windows, so we choose the window of the requested scale whose
    reference range covers the selection, starting closest to it.

    2026-10-06: this compared only the LAST TWO numbers of each reference and
    searched every book of the work, so Curtius 3.1.1-3.1.4 matched the window
    10.1.1-10.1.12 (both read as 1.1) and the Reader showed Similar Passages for
    Book 10 under a Book 3 selection. It now compares every coordinate and,
    when the caller names a book file that has windows of its own, looks only
    at that book's windows.
    """
    _ensure_loaded()
    if not _state['ok']:
        return None
    wid_work = work_id(work)
    group = _by_work.get(_norm_work(work)) or []
    exact = [row for row in group if _records[row].get('work') == wid_work]
    rows = exact if (is_part(wid_work) and exact) else group
    if not rows:
        return None
    want = _ref_coords_in(work, ref_start) or ()
    want_end = _ref_coords_in(work, ref_end) or want
    best, best_key = None, None
    for row in rows:
        r = _records[row]
        if prefer and r.get('scale') != prefer:
            continue
        lo = _ref_coords_in(r.get('work'), r.get('ref_start'))
        hi = _ref_coords_in(r.get('work'), r.get('ref_end'))
        if not (lo and hi):
            continue
        if not want:
            return r.get('id')
        # Compare on the depth both references share, from the left (book
        # before chapter before line), so a work whose references vary in depth
        # (a preface cited 1.pr, a poem 1.1.3) still finds its window.
        n = min(len(lo), len(hi), len(want), len(want_end))
        lo, hi, wn, we = lo[:n], hi[:n], want[:n], want_end[:n]
        covers = lo <= wn <= hi or (wn <= lo <= we)
        if not covers:
            continue
        # prefer the window that starts at or just before the selection start;
        # a window starting after it (it only overlaps the selection's tail)
        # ranks below every window that brackets the start
        key = (0, tuple(-x for x in lo)) if lo <= wn else (1, lo)
        if best_key is None or key < best_key:
            best, best_key = r.get('id'), key
    if best is None and prefer:
        return window_for_passage(work, ref_start, ref_end, prefer=None)
    return best


# Process-lifetime, not persisted: (norm_work_a, norm_work_b, scale) -> the
# median baseline compare_works would compute for that pair, or None when the
# pair can't be compared (missing windows, or too large). Small (one float per
# pair of works anyone has asked pair_lift about) and never invalidated within
# a process, same as _DENSITY_CACHE's in-memory sibling would be if it had one;
# a fresh deploy clears it along with everything else compare_works reads.
_PAIR_BASELINE_CACHE = {}


def _pair_baseline(work_a, work_b, scale='fine'):
    """The general-resemblance baseline between two works' windows, cached so a
    page of pair_lift calls over the same two works (backend/blueprints/
    passages.py /passages/pair-lift, 25 word-level results = one page) costs
    one score-matrix pass rather than one per row. Same computation and same
    convention (median of a strided sample of the score matrix) as
    compare_works's own baseline; kept separate because compare_works also
    needs the per-row top-k candidates in the same pass and this doesn't."""
    key = (_norm_work(work_a), _norm_work(work_b), scale)
    if key in _PAIR_BASELINE_CACHE:
        return _PAIR_BASELINE_CACHE[key]
    _ensure_loaded()
    if not _state['ok']:
        return None
    import numpy as np
    rows_a = _rows_for_work(work_a, scale)
    rows_b = _rows_for_work(work_b, scale)
    if scale == 'fine' and (not rows_a or not rows_b):
        rows_a = rows_a or _rows_for_work(work_a, 'coarse')
        rows_b = rows_b or _rows_for_work(work_b, 'coarse')
    if not rows_a or not rows_b or len(rows_a) * len(rows_b) > COMPARE_MAX_CELLS:
        _PAIR_BASELINE_CACHE[key] = None
        return None
    E_b = np.asarray(_emb[rows_b], dtype=np.float32)
    sample = []
    for lo in range(0, len(rows_a), COMPARE_BLOCK):
        chunk = rows_a[lo:lo + COMPARE_BLOCK]
        S = np.asarray(_emb[chunk], dtype=np.float32) @ E_b.T
        if len(sample) < 200_000:
            sample.append(S.ravel()[:: max(1, S.size // 20_000)])
    flat = np.concatenate(sample) if sample else np.zeros(1, dtype=np.float32)
    baseline = float(np.median(flat))
    _PAIR_BASELINE_CACHE[key] = baseline
    return baseline



_row_by_id = None


def _row_of(window_id):
    """Row index of a window id, from a dict built once. A list.index() scan
    over half a million ids per lookup made a page of results cost seconds."""
    global _row_by_id
    if _row_by_id is None or len(_row_by_id) != len(_ids or []):
        _row_by_id = {wid: i for i, wid in enumerate(_ids or [])}
    return _row_by_id.get(window_id)

def pair_lift(work_a, ref_a, work_b, ref_b, scale='fine'):
    """The Theme Comparison reading of one word-level result: the cosine
    between the fine windows that cover ref_a (in work_a) and ref_b (in
    work_b), and its lift above the two works' general resemblance to each
    other (_pair_baseline). Lets a fusion-search result that shares wording
    also say whether it sits in a thematically close stretch of the two
    works, or is isolated wording in otherwise unrelated passages.

    Returns None when either line falls outside every indexed window (no
    content coverage there) or the pair can't be compared at all; otherwise a
    dict with `score`, `lift`, and `level` (None lift/level when the pair is
    too large to baseline, same ceiling compare_works applies).
    """
    _ensure_loaded()
    if not _state['ok']:
        return None
    wid_a = window_for_passage(work_a, ref_a, ref_a, prefer=scale)
    wid_b = window_for_passage(work_b, ref_b, ref_b, prefer=scale)
    if not wid_a or not wid_b:
        return None
    row_a = _row_of(wid_a)
    row_b = _row_of(wid_b)
    if row_a is None or row_b is None:
        return None
    import numpy as np
    score = float(np.dot(np.asarray(_emb[row_a], dtype=np.float32),
                         np.asarray(_emb[row_b], dtype=np.float32)))
    baseline = _pair_baseline(work_a, work_b, scale)
    if baseline is None:
        return {'score': round(score, 4), 'lift': None, 'level': None}
    lift = score - baseline
    level = ('strong' if lift >= STRONG_LIFT else
             'moderate' if lift >= STRONG_LIFT / 2 else 'low')
    return {'score': round(score, 4), 'lift': round(lift, 4), 'level': level}


def find_similar_to_passage(work, ref_start=None, ref_end=None, limit=15,
                            languages=None, scale='fine',
                            suppress_other_versions=True, by_language=False):
    """Similar Passages, given a reader selection (work + reference span)."""
    wid = window_for_passage(work, ref_start, ref_end, prefer=scale)
    if not wid:
        return {'error': 'no indexed window covers that passage', 'results': []}
    return find_similar_to_window(wid, limit=limit, languages=languages,
                                  suppress_other_versions=suppress_other_versions,
                                  by_language=by_language)


# UNDER cache/, NOT beside the index.
#
# data/passage_index/ is owned by ncoffee:zodfaculty and the web user is
# tess-flask, which is in tess-flask, users and tessdev -- not zodfaculty. So
# this directory could never be created, the cache was NEVER written, and every
# single Reader page load recomputed an 18-second matrix multiply against the
# whole corpus. Three Apache workers, CPU-bound under the GIL, and the site
# stops answering: the Reader's dropdowns went "all frozen", which is
# what a wedged server looks like from the browser.
#
# The identical mistake put query_expansions.jsonl in the same directory a few
# hours earlier. I fixed that one and did not look for its siblings. Every other
# runtime cache on this system writes under cache/, which is world-writable with
# setgid tessdev; this was the only one that did not.
_DENSITY_CACHE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'cache', 'passage_density')


def _density_cache_path(work, scale):
    safe = re.sub(r'[^A-Za-z0-9._-]', '_', f'{work}.{scale}')
    return os.path.join(_DENSITY_CACHE, f'{index_fingerprint()}.{safe}.json')


def _row_scores(rows, chunk=256):
    """Yield (row, scores-against-every-window) for `rows`, a chunk at a time,
    so no more than `chunk` columns of the score block exist at once."""
    for c0 in range(0, len(rows), chunk):
        block_rows = rows[c0:c0 + chunk]
        block = _score_block(block_rows)
        for k, row in enumerate(block_rows):
            yield row, block[:, k]


def connection_density(work, scale='fine'):
    """Per-window content-connection density for the Reader's gutter.

    For each window of a work, how many other works hold a strongly similar
    passage. Computed once per work and small enough to cache client-side; the
    Reader pairs it with the lexical density to draw the two-mark gutter.
    """
    # THE CACHE IS READ BEFORE THE INDEX IS LOADED.
    #
    # _ensure_loaded() pulls 1.2 GB and takes thirteen seconds on a worker that
    # has not done it yet. Doing that first meant a cache HIT paid it too, for
    # an answer that is a small JSON file and needs nothing from the index. With
    # Apache recycling workers every 1000 requests, the Reader went back to
    # taking thirteen seconds at intervals, for nothing.
    # The caller may hand us the corpus filename or the bare work id. The
    # index stores the bare form, so `vergil.aeneid.part.6.tess` used to miss
    # the exact match below and fall through to the whole-work group, which
    # is precisely what that fallback's comment says must not happen: book 3
    # and book 7 densities painted beside book 6's lines. The Reader strips
    # the suffix itself and was never affected; anything else calling the
    # endpoint was (found 2026-09-21 while precomputing the cache).
    work = work_id(work)
    cache_path = _density_cache_path(work, scale)
    try:
        with open(cache_path, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        pass

    _ensure_loaded()
    if not _state['ok']:
        return {'error': _state['error'], 'windows': []}
    import numpy as np

    # Computing this is a matrix multiply against the whole corpus for every
    # window of the work, and the answer is identical until a text is added. The
    # fingerprint in the filename is what makes caching safe: a new index writes
    # to new paths and the stale files are simply never read again.
    # Match the EXACT work when the caller names a part file, since a reader is
    # looking at one book: collapsing vergil.aeneid.part.6 into vergil.aeneid
    # would paint book 3 and book 7 densities beside book 6's lines. Fall back to
    # the whole work group only when the caller names the group itself.
    #
    # THAT RULE WAS STATED HERE BUT NOT ENFORCED (2026-09-22). `exact or
    # fallback` only holds the line while the book file HAS windows of its own;
    # when it has none the fallback ran anyway and served the whole work's, which
    # is the very thing the paragraph above forbids. 68 Latin book files are in
    # that state, every one of them with the whole work indexed, so asking for
    # Suetonius' Augustus returned windows referenced `suet. vit. jul.`: the
    # Julius book's marks painted beside Augustus' lines. A book file now gets
    # its own windows or none, and none is honest. The fix for the missing marks
    # is to build those files their windows, not to borrow another book's.
    exact = [i for i in range(len(_records)) if _records[i].get('work') == work]
    rows = exact if is_part(work) else (exact or (_by_work.get(_norm_work(work)) or []))
    rows = [i for i in rows if not scale or _records[i].get('scale') == scale]
    if not rows:
        return {'work': work, 'windows': []}
    base = _norm_work(work)
    # ONE matrix-matrix multiply for every window of the work, not one
    # matrix-vector multiply per window. The gutter needs 150 windows for a book
    # of the Aeneid, and scoring them one at a time re-read the whole 785 MB
    # corpus matrix 150 times: 43 seconds. Handing BLAS all 150 query vectors at
    # once lets it reuse each chunk of the corpus across all of them, which is
    # what a matrix-matrix kernel is for. Measured 43s -> 2.2s, 19x.
    # Rows in chunks (2026-09-19): _score_block returns an (N windows in the
    # corpus) x (rows) float32 block, 2.5 MB per row at today's 619k windows,
    # so a whole work in one call was 5.0 GB for the Punica (2,032 windows)
    # and would be 11.6 GB for the Vulgate (6,540). That single allocation is
    # what pushed a preview server past its 6 and 8 GB caps and what a
    # production worker pays on the first open of any large uncached work.
    # 256 rows at a time keeps the block under 0.7 GB with the same answer.
    out = []
    for row, scores in _row_scores(rows):
        median = float(np.median(scores))
        # The best match OUTSIDE this work, and how far it stands above the
        # window's own baseline. This is the gutter's real signal, and it is
        # continuous: every line gets a reading rather than most getting zero.
        #
        # It replaces a count of works clearing STRONG_LIFT. That constant was
        # fitted to a different question, whether the corpus holds a subject at
        # all, and reused here it read 100 of the 150 windows of Aeneid 6 as
        # having no content connections whatever. What was actually happening is
        # that a passage's nearest neighbours are usually its own author, and
        # once those are excluded nothing cleared an absolute bar.
        best_lift = 0.0
        strong = 0
        seen = set()
        for other in np.argsort(-scores)[:400]:
            w = _norm_work(_records[other].get('work'))
            if w == base:
                continue
            s = float(scores[other])
            if best_lift == 0.0:
                best_lift = max(0.0, s - median)
            if w in seen:
                continue
            seen.add(w)
            if s >= median + STRONG_LIFT:
                strong += 1
            if len(seen) >= 25:
                break
        r = _records[row]
        out.append({'id': r.get('id'), 'ref_start': r.get('ref_start'),
                    'ref_end': r.get('ref_end'), 'connections': strong,
                    'lift': round(best_lift, 4)})
    # Normalise within the work, between its own 5th and 95th percentile, so the
    # gutter uses its full range on whatever text is open. Scaling from zero
    # instead left every mark between 0.57 and 1.00 on Aeneid 6, which is a
    # uniformly dark column telling a reader nothing. A per-corpus scale would
    # have the opposite fault, washing out a work whose connections are real but
    # uniformly modest.
    #
    # This makes density a RELATIVE reading: where this text is more and less
    # connected, not how it compares to another text. The absolute figure is
    # carried alongside as `connections`, the number of other works with a
    # strongly similar passage, which is what the tooltip should show.
    lifts = sorted(w['lift'] for w in out)
    if lifts:
        lo = lifts[int(0.05 * (len(lifts) - 1))]
        hi = lifts[int(0.95 * (len(lifts) - 1))]
    else:
        lo = hi = 0.0
    rng = hi - lo
    for w in out:
        w['density'] = round(min(1.0, max(0.0, (w['lift'] - lo) / rng)), 3) if rng > 0 else 0.0
    peak = max((w['connections'] for w in out), default=0)
    result = {'work': work, 'scale': scale, 'peak': peak,
              'lift_at_full_mark': round(hi, 4), 'lift_at_empty_mark': round(lo, 4),
              'windows': out}
    try:
        os.makedirs(_DENSITY_CACHE, exist_ok=True)
        tmp = cache_path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(result, fh)
        os.replace(tmp, cache_path)   # atomic, so a reader never sees half a file
    except OSError as e:
        # Loud, and it says what it costs. This failing silently is what made
        # every Reader visit pay eighteen seconds of BLAS instead of reading a
        # small JSON file.
        logger.warning('[PASSAGES] could not cache density for %s at %s: %s. '
                       'Every Reader load of this work will recompute it, which '
                       'takes seconds of CPU and will block other requests.',
                       work, _DENSITY_CACHE, e)
    return result
