"""Scene index: passage-level content retrieval over LLM-written descriptions.

The index holds, for every scene-sized window of the corpus, a structured English
description of WHAT THE PASSAGE CONTAINS (mode, setting, participants, actions,
themes, imagery, gist) plus an embedding of that description. Retrieval runs over
the descriptions rather than the ancient text, which is what lets a Latin passage
match a Hebrew or Greek one that shares no vocabulary.

Two query modes back the Reader:
  * by passage  -- "what else in the corpus is like this stretch of text"
  * by text     -- "find passages about grain shortage and famine relief"

Data (built offline, see research/motif_feature/DEVELOPMENT_LOG_2026-08.md):
  data/scene_index/descriptions.jsonl   one JSON record per window
  data/scene_index/embeddings.npy       float16 (N, D), row i matches ids[i]
  data/scene_index/ids.json             window ids, embedding row order

Embeddings are memory-mapped, so the resident cost is the id/description tables
rather than the matrix. Loading is lazy: nothing touches disk until the first
query, and a missing index degrades to "unavailable" instead of failing import.
"""
import json
import os
import re
import threading

from backend.logging_config import get_logger

logger = get_logger('scene_index')

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'data', 'scene_index')

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
MODERATE_COMBINED = 1.30
STRONG_COMBINED = 1.65
# A floor purely to stop the tail: results below the query's baseline are noise.
BASELINE_MARGIN = 0.010

_lock = threading.Lock()
_state = {'loaded': False, 'ok': False, 'error': None}
_ids = None            # list[str]
_records = None        # list[dict] in embedding-row order
_emb = None            # np.memmap (N, D) float16
_by_work = None        # work -> list[row index]
_model = None


def _norm_work(work):
    """Collapse a .part.N filename to its base work, so hom.iliad.part.2 and
    hom.iliad are one work for exclusion and dedup purposes."""
    return (work or '').split('.part.')[0]


def _ref_numbers(ref):
    """Trailing numeric coordinates of a reference tag, e.g.
    'verg. aen. 6.268' -> (6, 268); 'hebrew_bible.genesis.41.47' -> (41, 47)."""
    nums = re.findall(r'\d+', str(ref or ''))
    return tuple(int(n) for n in nums[-2:]) if nums else ()


def is_available():
    """True when the index files are present and loadable."""
    _ensure_loaded()
    return _state['ok']


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
                _state['error'] = f"scene index not built ({', '.join(os.path.basename(m) for m in missing)} absent)"
                logger.info('[SCENE] %s', _state['error'])
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
                logger.error('[SCENE] %s', _state['error'])
                return
            _by_work = {}
            for i, r in enumerate(_records):
                _by_work.setdefault(_norm_work(r.get('work')), []).append(i)
            _state['ok'] = True
            logger.info('[SCENE] index ready: %d windows, %d works, dim %d',
                        len(_ids), len(_by_work), _emb.shape[1])
        except Exception as e:  # index problems must not break the app
            _state['error'] = f'{type(e).__name__}: {e}'
            logger.error('[SCENE] index load failed: %s', _state['error'])


def _get_model():
    """Lazy-load the query encoder (only needed for free-text queries)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info('[SCENE] loading query encoder %s', EMBED_MODEL)
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


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
    }
    if extra:
        out.update(extra)
    return out


def _rank(scores, limit, exclude_work=None, languages=None, scale=None,
          dedup=True, baseline=None, strong_at=None):
    """Shared ranking: sort, filter, and collapse near-duplicate windows.

    Duplicates are real in this corpus: a work and its .part.N file both carry
    the same lines, and the fine/coarse scales overlap by design, so without a
    dedup pass a single passage can occupy an entire page of results.
    """
    import numpy as np
    if baseline is None:
        baseline = float(np.median(scores))
    floor = baseline + BASELINE_MARGIN
    if strong_at is None:
        strong_at = baseline + STRONG_LIFT
    order = np.argsort(-scores)
    seen = set()
    out = []
    for row in order:
        score = float(scores[row])
        if score < floor:
            break
        r = _records[row]
        work = _norm_work(r.get('work'))
        if exclude_work and work == exclude_work:
            continue
        if languages and r.get('language') not in languages:
            continue
        if scale and r.get('scale') != scale:
            continue
        if dedup:
            key = (work, _ref_numbers(r.get('ref_start')))
            if key in seen:
                continue
            seen.add(key)
        out.append(_result(row, score, strong=score >= strong_at))
        if len(out) >= limit:
            break
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


def _confidence_level(lift, coherence):
    """Graded, never certain: see the calibration note at the top of the file.

    Neither signal separates present from absent subjects alone, but they fail
    in different directions, so requiring BOTH for 'strong' and EITHER for
    'moderate' left 'moderate' meaningless (it caught real and absent subjects
    alike). Combining them into one score separates better than either does:
    on the 18-query probe set, real subjects score above 1.75 and absent ones
    below it, with the single exception noted in the log.
    """
    combined = lift * 10.0 + (coherence - 0.85) * 10.0
    if combined >= STRONG_COMBINED:
        return 'strong'
    if combined >= MODERATE_COMBINED:
        return 'moderate'
    return 'low'


def _confidence_note(level):
    if level == 'strong':
        return None
    if level == 'moderate':
        return ('Moderate confidence: the corpus holds passages of this kind, but the '
                'match is looser than a clear case. Read the results before relying on them.')
    return ('No strong content match in the corpus for this description. The passages '
            'below resemble the query only weakly, and should be read as neighbours '
            'rather than findings.')


def find_by_text(query, limit=25, languages=None, scale=None):
    """Theme Search: free-text description of the wanted content."""
    _ensure_loaded()
    if not _state['ok']:
        return {'error': _state['error'], 'results': []}
    if not (query or '').strip():
        return {'error': 'empty query', 'results': []}
    import numpy as np
    q = _get_model().encode([_E5_PREFIX + query.strip()[:1500]],
                            normalize_embeddings=True)[0].astype(np.float32)
    scores = np.asarray(_emb, dtype=np.float32) @ q
    baseline = float(np.median(scores))
    top = float(scores.max())
    lift = top - baseline
    coherence = _cluster_coherence(scores)
    level = _confidence_level(lift, coherence)
    results = _rank(scores, limit, languages=languages, scale=scale,
                    baseline=baseline,
                    strong_at=baseline + (STRONG_LIFT if level == 'strong' else 1e9))
    return {
        'query': query,
        'results': results,
        'strong_matches': sum(1 for r in results if r['strong']),
        'confidence': {'top': round(top, 4), 'baseline': round(baseline, 4),
                       'lift': round(lift, 4),
                       'coherence': round(coherence, 4), 'level': level},
        'note': _confidence_note(level),
    }


def find_similar_to_window(window_id, limit=15, languages=None,
                           include_same_work=False):
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
    scores = np.asarray(_emb, dtype=np.float32) @ q
    scores[row] = -1.0
    exclude = None if include_same_work else _norm_work(_records[row].get('work'))
    baseline = float(np.median(scores))
    results = _rank(scores, limit, exclude_work=exclude, languages=languages,
                    baseline=baseline)
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
    want = _ref_numbers(ref_start) or ()
    want_end = _ref_numbers(ref_end) or want
    best, best_key = None, None
    for row in rows:
        r = _records[row]
        if prefer and r.get('scale') != prefer:
            continue
        lo = _ref_numbers(r.get('ref_start'))
        hi = _ref_numbers(r.get('ref_end'))
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
                            languages=None, scale='fine'):
    """Similar Passages, given a reader selection (work + reference span)."""
    wid = window_for_passage(work, ref_start, ref_end, prefer=scale)
    if not wid:
        return {'error': 'no indexed window covers that passage', 'results': []}
    return find_similar_to_window(wid, limit=limit, languages=languages)


def connection_density(work, scale='fine'):
    """Per-window content-connection density for the Reader's gutter.

    For each window of a work, how many other works hold a strongly similar
    passage. Computed once per work and small enough to cache client-side; the
    Reader pairs it with the lexical density to draw the two-mark gutter.
    """
    _ensure_loaded()
    if not _state['ok']:
        return {'error': _state['error'], 'windows': []}
    import numpy as np
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
    mat = np.asarray(_emb, dtype=np.float32)
    out = []
    for row in rows:
        scores = mat @ np.asarray(_emb[row], dtype=np.float32)
        strong_at = float(np.median(scores)) + STRONG_LIFT
        strong = 0
        seen = set()
        for other in np.argsort(-scores)[:200]:
            if float(scores[other]) < strong_at:
                break
            w = _norm_work(_records[other].get('work'))
            if w == base or w in seen:
                continue
            seen.add(w)
            strong += 1
        r = _records[row]
        out.append({'id': r.get('id'), 'ref_start': r.get('ref_start'),
                    'ref_end': r.get('ref_end'), 'connections': strong})
    peak = max((w['connections'] for w in out), default=0) or 1
    for w in out:
        w['density'] = round(w['connections'] / peak, 3)
    return {'work': work, 'scale': scale, 'peak': peak, 'windows': out}
