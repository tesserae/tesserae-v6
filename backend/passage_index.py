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
import json
import os
import re
import threading

from backend import scripture_id
from backend.logging_config import get_logger

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

_lock = threading.Lock()
_state = {'loaded': False, 'ok': False, 'error': None}
_ids = None            # list[str]
_undescribed = set()   # row indices with no description: excluded from results
_records = None        # list[dict] in embedding-row order
_emb = None            # np.memmap (N, D) float16
_by_work = None        # work -> list[row index]
_model = None


def _norm_work(work):
    """Collapse a work identifier to the index's key form.

    The Reader sends the work as its corpus filename, and for a multi-part
    work the .part split incidentally removed the .tess suffix too, so
    vergil.aeneid.part.1.tess matched while a single-file work like
    shenoute.a22.tess never did: its Similar Passages answered "no indexed
    window covers that passage" for every selection. Strip the language
    directory and the .tess suffix explicitly, then collapse parts."""
    w = (work or '')
    if '/' in w:
        w = w.rsplit('/', 1)[-1]
    if w.endswith('.tess'):
        w = w[:-5]
    return w.split('.part.')[0]


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


def status():
    _ensure_loaded()
    return {
        'available': _state['ok'],
        'error': _state['error'],
        'windows': len(_ids) if _ids else 0,
        'works': len(_by_work) if _by_work else 0,
        'model': EMBED_MODEL,
        'strong_lift': STRONG_LIFT,
        'weak_lift': WEAK_LIFT,
    }


def _ensure_loaded():
    global _ids, _records, _emb, _by_work
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
            for i, r in enumerate(_records):
                _by_work.setdefault(_norm_work(r.get('work')), []).append(i)
            _state['ok'] = True
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
    return {'author': author, 'title': title,
            'display_name': m.get('display_name') or display or None}


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


def _rank(scores, limit, exclude_work=None, languages=None, scale=None,
          dedup=True, baseline=None, strong_at=None, exclude_span=None,
          per_work=None, only_works=None):
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
    """
    import numpy as np
    if baseline is None:
        baseline = float(np.median(scores))
    floor = baseline + BASELINE_MARGIN
    if strong_at is None:
        strong_at = baseline + STRONG_LIFT
    order = np.argsort(-scores)
    seen = {}          # work -> [(start, end)] already taken, for overlap dedup
    per_work_count = {}
    by_passage = {}       # canonical scripture span -> index into out
    out = []
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
    (NC, 2026-08-31). Measured on the 74-instance pilot benchmark at rank
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


def _cluster_coherence(scores, k=COHERENCE_K):
    """How much the top-k results agree with each other.

    A subject the corpus really holds returns a coherent cluster of passages;
    an absent subject returns scattered strays that resemble the query a little
    and each other hardly at all.
    """
    import numpy as np
    top = np.argsort(-scores)[:k]
    block = np.asarray(_emb[top], dtype=np.float32)
    norms = np.linalg.norm(block, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    block = block / norms
    sim = block @ block.T
    n = len(top)
    return float((sim.sum() - n) / (n * n - n)) if n > 1 else 0.0


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


def _confidence_level(head_lift, coherence):
    """Graded, never certain. Works for one word or for a sentence.

    head_lift is the mean of the top ten scores above the corpus median.
    """
    if coherence >= DEGENERATE_COHERENCE:
        return 'low'
    if head_lift < HEAD_WEAK:
        return 'low'
    if head_lift >= HEAD_STRONG:
        return 'strong'
    return 'moderate'


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


def _confidence_note(level):
    drift = _calibration_drift()
    if drift:
        now, _ = drift
        warning = _UNCALIBRATED.format(fitted=FITTED_AT_WINDOWS, now=now)
        base = _confidence_note_fitted(level)
        return f'{warning} {base}' if base else warning
    return _confidence_note_fitted(level)


def _confidence_note_fitted(level):
    if level == 'strong':
        return None
    if level == 'moderate':
        return ('Moderate confidence: the corpus holds passages of this kind, but the '
                'match is looser than a clear case. Read the results before relying on them.')
    return ('The corpus does not appear to contain passages of this kind. Anything '
            'the search returns for it is a nearest neighbour, not a finding.')


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


def find_by_text(query, limit=25, languages=None, scale=None, expand=True):
    """Theme Search: free-text description of the wanted content."""
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
    baseline = float(np.median(scores))
    top = float(scores.max())
    lift = top - baseline
    # The GROUP at the head, not the single best hit: one lucky vector is not a
    # subject, and the top hit alone is what made short queries unreadable.
    k = min(10, len(scores))
    head_lift = float(np.sort(scores)[-k:].mean()) - baseline
    coherence = _cluster_coherence(scores)
    level = _confidence_level(head_lift, coherence)
    strong_at = baseline + (STRONG_LIFT if level == 'strong' else 1e9)

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
    heads = _rank(scores, limit, languages=languages, scale=scale,
                  baseline=baseline, strong_at=strong_at, per_work=1)
    # Multi-language pages are composed by per-language round-robin rather
    # than one global cutoff; see _interleave_languages for the measurements
    # behind the choice.
    if not languages or len(languages) > 1:
        pool = _rank(scores, limit * 6, languages=languages, scale=scale,
                     baseline=baseline, strong_at=strong_at, per_work=1)
        heads = _interleave_languages(heads, pool)
    chosen = [_norm_work(r.get('work')) for r in heads]
    results = _rank(scores, limit * PASSAGES_PER_WORK, languages=languages,
                    scale=scale, baseline=baseline, strong_at=strong_at,
                    per_work=PASSAGES_PER_WORK, only_works=set(chosen))
    # Back into the order the first pass established, so the page still reads
    # best-work-first and each work's passages sit together.
    rank_of = {w: n for n, w in enumerate(chosen)}
    results.sort(key=lambda r: (rank_of.get(_norm_work(r.get('work')), 10**9),
                                -r.get('score', 0)))
    return {
        'query': query,
        'results': results,
        'strong_matches': sum(1 for r in results if r['strong']),
        'confidence': {'top': round(top, 4), 'baseline': round(baseline, 4),
                       'head_lift': round(head_lift, 4),
                       'lift': round(lift, 4),
                       'coherence': round(coherence, 4), 'level': level},
        'note': _confidence_note(level),
    }


def find_similar_to_window(window_id, limit=15, languages=None,
                           include_same_work=False, suppress_other_versions=True):
    """Similar Passages, given an index window id."""
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
    return {
        'source': _result(row, 1.0, strong=True),
        'results': results,
        'confidence': {'top': round(float(top), 4), 'baseline': round(baseline, 4),
                       'lift': round(float(top) - baseline, 4)},
    }


def window_for_passage(work, ref_start=None, ref_end=None, prefer='fine'):
    """Map a reader selection to the index window that best covers it.

    The Reader hands us a work and a reference span; the index is built on fixed
    overlapping windows, so we choose the window of the requested scale whose
    reference range covers the most of the selection.
    """
    _ensure_loaded()
    if not _state['ok']:
        return None
    rows = _by_work.get(_norm_work(work)) or []
    if not rows:
        return None
    want = _ref_numbers_in(work, ref_start) or ()
    want_end = _ref_numbers_in(work, ref_end) or want
    best, best_key = None, None
    for row in rows:
        r = _records[row]
        if prefer and r.get('scale') != prefer:
            continue
        lo = _ref_numbers_in(r.get('work'), r.get('ref_start'))
        hi = _ref_numbers_in(r.get('work'), r.get('ref_end'))
        if not (lo and hi):
            continue
        if not want:
            return r.get('id')
        # same book (or no book component) and the window brackets the selection
        covers = lo <= want <= hi or (want <= lo <= want_end)
        if not covers:
            continue
        # prefer the window whose start sits closest to the selection start
        key = abs((lo[-1] if lo else 0) - (want[-1] if want else 0))
        if best_key is None or key < best_key:
            best, best_key = r.get('id'), key
    if best is None and prefer:
        return window_for_passage(work, ref_start, ref_end, prefer=None)
    return best


def find_similar_to_passage(work, ref_start=None, ref_end=None, limit=15,
                            languages=None, scale='fine',
                            suppress_other_versions=True):
    """Similar Passages, given a reader selection (work + reference span)."""
    wid = window_for_passage(work, ref_start, ref_end, prefer=scale)
    if not wid:
        return {'error': 'no indexed window covers that passage', 'results': []}
    return find_similar_to_window(wid, limit=limit, languages=languages,
                                  suppress_other_versions=suppress_other_versions)


# UNDER cache/, NOT beside the index.
#
# data/passage_index/ is owned by ncoffee:zodfaculty and the web user is
# tess-flask, which is in tess-flask, users and tessdev -- not zodfaculty. So
# this directory could never be created, the cache was NEVER written, and every
# single Reader page load recomputed an 18-second matrix multiply against the
# whole corpus. Three Apache workers, CPU-bound under the GIL, and the site
# stops answering: NC reported the Reader's dropdowns "all frozen", which is
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
    exact = [i for i in range(len(_records)) if _records[i].get('work') == work]
    rows = exact or (_by_work.get(_norm_work(work)) or [])
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
    out = []
    all_scores = _score_block(rows)
    for n_row, row in enumerate(rows):
        scores = all_scores[:, n_row]
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
