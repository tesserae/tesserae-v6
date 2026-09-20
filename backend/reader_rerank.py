"""Reader-at-top: re-rank Theme Search's top results with the trained free
reader model, over HTTP to services/reader_server.py.

Disabled unless THEME_READER_URL is set (see backend/reader_client.py).
When disabled, or when the reader call fails for any reason, this hands
results back exactly as it received them: Theme Search's response shape
never changes on failure, only on a successful re-rank.

Ordering (R1, chosen in evaluation/theme_benchmark/reader_at_top/rerank.py):
sort the top K by reader score descending, index score as the tiebreak.
Results past K keep the order find_by_text already gave them.
"""
import os
import time

from backend import reader_client
from backend import translations
from backend import window_texts
from backend.logging_config import get_logger

logger = get_logger('reader_rerank')

# Rows the reader re-scores: the whole composed list (about 100 works x 3
# windows) since 2026-09-20, not its first hundred rows. Measured on the
# 16-query benchmark: precision neutral (0.444 against 0.453 at 100), and a
# work whose rows sit past the first hundred can now reach the page: the
# Odyssey's recognitions on "a wife or child recognizes someone long
# thought dead or lost" were at rows 146 to 148 and landed at row 15 once
# the reader saw them. About 9 s a query instead of 4 s (NC: "Give the
# reader all 300 composed rows"). The reader service accepts up to 400.
DEFAULT_K = int(os.environ.get('THEME_READER_K', '300'))
# Named in the reproducible citation so a re-ranked search can be re-run
# the same way; change it when the checkpoint changes.
MODEL_ID = os.environ.get('THEME_READER_MODEL', 'minilm-distill-2026-09-17')


def build_passage_text(gist, translation, text):
    """[gist] + [translation if present] + [original text], in that order.

    Copied from evaluation/theme_benchmark/distill_train/common.py
    (build_passage_text): the reader was trained on inputs joined in exactly
    this order, so truncation to 512 tokens at score time trims the
    original-language text last and leaves the gist and translation intact.
    """
    parts = []
    gist = (gist or '').strip()
    if gist:
        parts.append(gist)
    translation = (translation or '').strip()
    if translation:
        parts.append(translation)
    text = (text or '').strip()
    if text:
        parts.append(text)
    return '\n\n'.join(parts)


def _translation_for(result):
    """The aligned public-domain translation for a result, or ''.

    Training used a one-time machine translation of every passage
    (evaluation/theme_benchmark/distill/translate.py); that is a paid call
    and cannot run in the live request path (CLAUDE.md: no recurring paid
    API calls). At serving time this uses the same aligned-translation
    lookup the Reader's Translation tab already uses, which covers about
    30 percent of Greek and 18 percent of Latin -- most passages simply
    have no translation part, the same as at training time for the texts
    the teacher had to read cold.
    """
    try:
        info = translations.for_passage(
            result.get('work'), [result.get('ref_start'), result.get('ref_end')])
    except Exception:  # noqa: BLE001 - a missing/malformed translation must not break the rerank
        return ''
    if not info or not info.get('available'):
        return ''
    return info.get('text') or ''


def _reader_texts(results):
    """{id: reader text} for a list of Theme Search result dicts."""
    ids = [r.get('id') for r in results if r.get('id')]
    texts_by_id = window_texts.texts_for(ids)
    out = {}
    for r in results:
        wid = r.get('id')
        out[wid] = build_passage_text(
            r.get('gist'), _translation_for(r), texts_by_id.get(wid, ''))
    return out


def apply(query, results, k=None, timeout=6.0):
    """Re-rank the top `k` of `results` by reader score, index score as the
    tiebreak. `results` is assumed already sorted by index score.

    Returns (results, meta). On any failure (disabled, unreachable, no
    results) returns the ORIGINAL list unchanged and meta {'applied': False}.
    On success returns a new list (re-ordered head + untouched tail) and
    meta {'applied': True, 'k': k, 'ms': elapsed, 'model': MODEL_ID}. Never raises.
    """
    k = DEFAULT_K if k is None else k
    if not results:
        return results, {'applied': False}

    head = results[:k]
    tail = results[k:]

    t0 = time.time()
    texts = _reader_texts(head)
    passages = [{'id': r.get('id'), 'text': texts.get(r.get('id'), '')} for r in head]

    scores = reader_client.score(query, passages, timeout=timeout)
    if scores is None:
        return results, {'applied': False}
    ms = int((time.time() - t0) * 1000)

    missing = [r.get('id') for r in head if r.get('id') not in scores]
    if missing:
        logger.warning('[READER] %d of %d passages came back with no score',
                       len(missing), len(head))

    for r in head:
        s = scores.get(r.get('id'))
        if s is not None:
            r['reader_score'] = float(s)

    def sort_key(r):
        reader_score = r.get('reader_score')
        reader_score = reader_score if reader_score is not None else -1.0
        return (-reader_score, -(r.get('score') or 0.0))

    head_sorted = sorted(head, key=sort_key)
    return head_sorted + tail, {'applied': True, 'k': k, 'ms': ms, 'model': MODEL_ID}
