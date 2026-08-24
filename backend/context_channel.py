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
rescaled so that only agreement above the corpus baseline counts:

    context = clamp((cosine - NEUTRAL) / (CONFIRMED - NEUTRAL), 0, 1)

Below NEUTRAL the pair gets nothing (no penalty: absence of thematic agreement
is not evidence against a verbal parallel, since a quotation can be transplanted
into a wholly different setting). At or above CONFIRMED it gets the full signal.
"""
from backend.logging_config import get_logger
from backend import scene_index

logger = get_logger('context_channel')

# Cosine between two description embeddings, calibrated 2026-08-24 against the
# actual distribution over the 143,947-window index rather than by eye:
#   20,000 random cross-work pairs  median 0.844, p90 0.873, p99 0.901
#   genuine best-match-in-another-work  p10 0.915, median 0.939
# The random median is the CHANCE level, so anything at or below it is no
# evidence at all. NEUTRAL sits at the 99th percentile of chance, which is where
# agreement starts to mean something, and CONFIRMED at the median of genuine
# cross-work matches. An earlier hand-guessed pair (0.840 / 0.905) put the zero
# point at chance itself and therefore rewarded unrelated passages.
NEUTRAL_AGREEMENT = 0.901
CONFIRMED_AGREEMENT = 0.939

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
    if not scene_index.is_available():
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
            wid = scene_index.window_for_passage(work, ref, ref, prefer='fine')
            row = None
            if wid:
                try:
                    row = scene_index._ids.index(wid)
                except ValueError:
                    row = None
            win_cache[key] = row
        return win_cache[key]

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
        a = np.asarray(scene_index._emb[srow], dtype=np.float32)
        b = np.asarray(scene_index._emb[trow], dtype=np.float32)
        na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
        if na == 0.0 or nb == 0.0:
            continue
        cos = float(a @ b) / (na * nb)
        score = _clamp01((cos - NEUTRAL_AGREEMENT) /
                         (CONFIRMED_AGREEMENT - NEUTRAL_AGREEMENT))
        if score > 0.0:
            out[(src_ref, tgt_ref)] = round(score, 4)
    logger.info('[CONTEXT] confirmed %d of %d candidate pairs', len(out), considered)
    return out


def context_available():
    """True when the scene index backing this channel is loadable."""
    return scene_index.is_available()
