"""Context channel: passage-level agreement as a confirmation signal in fusion.

The lexical channels find line pairs that share words. This channel asks a
different question about those pairs: do the two lines sit in passages that are
ABOUT the same kind of thing? Two lines sharing a rare word inside two arming
scenes are better evidence of a real intertext than two lines sharing the same
word where one sits in a battle and the other in a legal argument.

Design (from the 2026-08-21 motif scale evaluation and the 2026-08-23 probe
battery, see research/motif_feature/): passage similarity is a strong recall
signal and a weak precision signal on its own, since thematically adjacent
passages score highly whether or not they are related. So this channel does NOT
propose pairs of its own. It runs LAST, over pairs the lexical channels already
found, and contributes a bounded confirmation score. That is the same gating
logic the syntax_structural channel uses, and it keeps the failure mode of
scene similarity (confident thematic neighbours) out of the ranked output.

Score per pair is the cosine between the two passages' content descriptions,
expressed as a percentile of THIS TEXT PAIR'S OWN distribution rather than
against a fixed number.

That change is the whole point of the 2026-08-24 revision. A fixed threshold
cannot work, because how similar two passages look depends on what is being
compared. Random window pairs drawn from just two works score:

    Lucan x Aeneid    (same genre, same language)     median 0.848, p99 0.898
    Iliad x Aeneid    (same genre, cross-language)    median 0.855, p99 0.906
    Genesis x Aeneid  (different genre and language)  median 0.842, p99 0.882

The old fixed 0.901 therefore sat at the 99th percentile for Lucan, just under
it for Homer, and ABOVE THE MAXIMUM for Genesis against the Aeneid, where
nothing could ever have been confirmed. Two Latin epics share genre, register
and subject matter, so their floor is already high and the band in which
"recognisably the same kind of scene" lives is narrow: roughly 0.86 to 0.92,
with genuinely near-identical scenes reaching 0.95 and above.

So the baseline is measured per comparison, from random pairs of the two works,
and a candidate is scored by where it falls in that distribution. A pair at the
99.5th percentile of its own comparison means the same thing whether the texts
are two Latin epics or a Hebrew prophet and a Latin poet.

This is the same lesson the scene index itself learned: no absolute cosine
threshold survives contact with a different query, and everything has to be
relative to a baseline measured on the spot.

Below the lower percentile the pair gets nothing (no penalty: absence of
thematic agreement is not evidence against a verbal parallel, since a quotation
can be transplanted into a wholly different setting).
"""
from backend.logging_config import get_logger
from backend import passage_index

logger = get_logger('context_channel')

# Percentiles of the comparison's own baseline. A pair has to be unusual FOR
# THESE TWO TEXTS before it counts as confirmation: two prophecy scenes in two
# epics is not distinctive, because prophecy scenes are common in both.
#
# Fitted 2026-08-24 by reading the Lucan-Vergil pairs at each level. Above the
# 99th percentile sit the proem-to-proem invocation (causas ... expromere against
# Musa, mihi causas memora), a lion simile against a lion simile, and the
# socer/gener allusion to Anchises' lament over Caesar and Pompey. Around the
# 90th sit arming scene against arming scene. At the median sit pairs that are
# thematically adjacent but no more so than any two passages of these poems.
NEUTRAL_PERCENTILE = 0.90
CONFIRMED_PERCENTILE = 0.995

# Random pairs sampled per comparison to establish that baseline. Cheap: a few
# thousand dot products against rows already in memory.
BASELINE_SAMPLES = 4000

# The old absolute numbers, kept only so the previous behaviour can be measured
# against the new one. Not used for scoring.
LEGACY_NEUTRAL_AGREEMENT = 0.901
LEGACY_CONFIRMED_AGREEMENT = 0.939

# Only confirm pairs a lexical channel already proposed, and cap the work so a
# large comparison does not pay an unbounded cost for a confirmation signal.
MAX_PAIRS = 20000


def _clamp01(x):
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else x)


def find_context_confirmations(pairs, source_id, target_id,
                               source_language='la', target_language='la'):
    """Score how much the passages around each candidate pair agree in content.

    Args:
        pairs: iterable of (source_ref, target_ref) for pairs already found by
            the lexical channels.
        source_id, target_id: .tess basenames of the two texts.

    Returns:
        dict {(source_ref, target_ref): score in 0..1}. Pairs whose passages do
        not agree, or that have no indexed window, are simply absent.
    """
    if not passage_index.is_available():
        return {}
    try:
        import numpy as np
    except ImportError:
        return {}

    src_work = source_id[:-5] if source_id.endswith('.tess') else source_id
    tgt_work = target_id[:-5] if target_id.endswith('.tess') else target_id

    # One window lookup per distinct reference, not per pair: a work's lines
    # collapse into far fewer windows, so this is the difference between
    # thousands of lookups and tens.
    win_cache = {}

    def window_row(work, ref):
        key = (work, ref)
        if key not in win_cache:
            wid = passage_index.window_for_passage(work, ref, ref, prefer='fine')
            row = None
            if wid:
                try:
                    row = passage_index._ids.index(wid)
                except ValueError:
                    row = None
            win_cache[key] = row
        return win_cache[key]

    # Baseline for THIS comparison: how similar do random passages of these two
    # works look? Everything below is measured against it.
    lo, hi = _pair_baseline(src_work, tgt_work)
    if lo is None:
        logger.info('[CONTEXT] no baseline for %s x %s; not confirming', src_work, tgt_work)
        return {}
    span = hi - lo

    out = {}
    considered = 0
    for src_ref, tgt_ref in pairs:
        if considered >= MAX_PAIRS:
            logger.info('[CONTEXT] pair cap %d reached; remaining pairs unconfirmed', MAX_PAIRS)
            break
        considered += 1
        srow = window_row(src_work, src_ref)
        trow = window_row(tgt_work, tgt_ref)
        if srow is None or trow is None:
            continue
        a = np.asarray(passage_index._emb[srow], dtype=np.float32)
        b = np.asarray(passage_index._emb[trow], dtype=np.float32)
        na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
        if na == 0.0 or nb == 0.0:
            continue
        cos = float(a @ b) / (na * nb)
        score = _clamp01((cos - lo) / span) if span > 0 else 0.0
        if score > 0.0:
            out[(src_ref, tgt_ref)] = round(score, 4)
    logger.info('[CONTEXT] confirmed %d of %d candidate pairs '
                '(baseline for this comparison: p90=%.3f p99.5=%.3f)',
                len(out), considered, lo, hi)
    return out


_baseline_cache = {}


def _pair_baseline(src_work, tgt_work):
    """Cosine at the neutral and confirmed percentiles for this pair of works.

    Sampled from the two works' own windows, so the answer reflects how alike
    these particular texts look before any candidate is considered. Cached: a
    comparison asks for it once and it does not change.
    """
    key = (src_work, tgt_work)
    if key in _baseline_cache:
        return _baseline_cache[key]
    try:
        import numpy as np
        import random as _random
    except ImportError:
        return None, None

    def fine_rows(work):
        rows = passage_index._by_work.get(work) or []
        # Fall back to the work group when a part file is named, since that is
        # what the index keys on.
        if not rows and '.part.' in work:
            rows = passage_index._by_work.get(work.split('.part.')[0]) or []
        return [i for i in rows if passage_index._records[i].get('scale') == 'fine']

    a, b = fine_rows(src_work), fine_rows(tgt_work)
    if not a or not b:
        _baseline_cache[key] = (None, None)
        return None, None

    emb = passage_index._emb
    # A fixed seed so the same comparison scores identically every time, which
    # matters for a tool whose results people cite.
    rnd = _random.Random(20260824)
    vals = []
    for _ in range(BASELINE_SAMPLES):
        i, j = rnd.choice(a), rnd.choice(b)
        x = np.asarray(emb[i], dtype=np.float32)
        y = np.asarray(emb[j], dtype=np.float32)
        nx, ny = float(np.linalg.norm(x)), float(np.linalg.norm(y))
        if nx and ny:
            vals.append(float(x @ y) / (nx * ny))
    if len(vals) < 100:
        _baseline_cache[key] = (None, None)
        return None, None
    vals.sort()
    lo = vals[int(NEUTRAL_PERCENTILE * (len(vals) - 1))]
    hi = vals[int(CONFIRMED_PERCENTILE * (len(vals) - 1))]
    _baseline_cache[key] = (lo, hi)
    return lo, hi


def context_available():
    """True when the scene index backing this channel is loadable."""
    return passage_index.is_available()
