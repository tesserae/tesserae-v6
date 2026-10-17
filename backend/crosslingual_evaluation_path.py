"""The evaluation scorer as a second live Greek-Latin path.

Setting ``crosslingual_scorer`` = ``evaluation`` makes the live Greek-Latin
cross-language search rank pairs with the scoring rules of the evaluation
benchmarks (evaluation/scripts/crosslingual_common.py, ``make_fused_scorer``),
instead of the live channels in backend/blueprints/search.py. The default,
``live``, never reaches this module.

What the evaluation scorer does, and so what this path does:
  * every pair of lines is scored from the full cosine matrix (no top-20 per
    line, no hubness correction, no recovery threshold). A pair is LISTED when
    it has a dictionary match, a syntax match, or a cosine above 0.3;
  * the dictionary score counts matched lemma pairs and uses corpus
    document-frequency IDF (genre-aware where both texts share a meter);
  * the rarity multiplier is squared, with its floor and cap, and is held at
    1.0 for a lone dictionary pair without syntax (the "v2" rule);
  * the convergence bonus is 0.5 times the square of min(1, geometric mean IDF)
    when two of semantic (cosine above 0.3), dictionary and syntax fire;
  * syntax enters at weight 0.5.
Left out because the evaluation scorer does not have them: the phonetic
channel, the translated-run boost, the live top-20 candidate list, and the
refrain-and-rhyme channel (not used for Greek-Latin anyway).

The two-lemma gate is a separate, optional step on top: under this path it
defaults to ``off`` (the caller sets that), and ``exclude`` or ``penalty``
count distinct lemma pairs as the live gate does (the smaller of the distinct
Greek and distinct Latin lemmas among the matched pairs).

The evaluation scorer is read from the evaluation folder, which the production
checkout carries; its imports (numpy and backend.*) are already in the web
application's environment.
"""
import importlib.util
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COMMON_PATH = PROJECT_ROOT / 'evaluation' / 'scripts' / 'crosslingual_common.py'

# Cosine above this counts as the semantic channel firing (the evaluation scorer's rule).
SEMANTIC_THRESHOLD = 0.3

# With no result cap, how many cosine-only pairs are listed besides the pairs that
# have a dictionary or syntax match.
COSINE_ONLY_UNCAPPED = 2000

# The full cosine matrix is held in memory with the dictionary, syntax and IDF tables
# built around it. Measured 2026-10-17: Aeneid against Iliad as whole works (9,896 x 15,683
# lines, 155 million cells) took 119 seconds and 8.7 GB, and the same search with no result
# cap was killed at a 12 GB limit. About 56 bytes a cell, so 25 million cells is about
# 1.4 GB. Beyond that the path declines instead of risking the worker.
MAX_MATRIX_CELLS = 25_000_000

_common = None
_common_lock = threading.Lock()


class EvaluationPathError(Exception):
    """The evaluation path cannot answer this search; the message is for the reader."""


def _load_common():
    """The evaluation scorer's module, loaded once from its file."""
    global _common
    with _common_lock:
        if _common is None:
            if not COMMON_PATH.is_file():
                raise EvaluationPathError(
                    'The evaluation scorer is not installed on this server '
                    f'({COMMON_PATH.relative_to(PROJECT_ROOT)} is missing).')
            spec = importlib.util.spec_from_file_location('tesserae_crosslingual_common', COMMON_PATH)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _common = module
        return _common


def _strip_accents(common, s):
    return common.strip_accents(s)


def _best_cosine_only(cosine, keyed, limit, block=256):
    """The best ``limit`` pairs by cosine that clear the semantic threshold and are not in ``keyed``.

    Works a block of rows at a time so the index arrays stay small. Returns
    (list of (greek_idx, latin_idx), count of cells above the threshold).
    """
    import numpy as np
    n_grc, n_lat = cosine.shape
    pool = []
    n_above = 0
    keyed_rows = {}
    for g, _ in keyed:
        keyed_rows[g] = keyed_rows.get(g, 0) + 1
    for r0 in range(0, n_grc, block):
        sub = cosine[r0:r0 + block]
        n_above += int((sub > SEMANTIC_THRESHOLD).sum())
        flat = sub.ravel()
        extra = sum(keyed_rows.get(g, 0) for g in range(r0, min(r0 + block, n_grc)))
        kk = min(flat.size, limit + extra)
        if kk <= 0:
            continue
        top = np.argpartition(-flat, kk - 1)[:kk] if kk < flat.size else np.arange(flat.size)
        for f in top:
            v = float(flat[f])
            if v <= SEMANTIC_THRESHOLD:
                continue
            g, lt = r0 + int(f) // n_lat, int(f) % n_lat
            if (g, lt) not in keyed:
                pool.append((v, g, lt))
    pool.sort(key=lambda t: (-t[0], t[1], t[2]))
    return [(g, lt) for _, g, lt in pool[:limit]], n_above


def score_pairs(source_units, target_units, source_language, source_path, target_path,
                source_emb, target_emb, *, gate, penalty_factor, min_lemma_matches,
                min_matches, max_results, cancellation=None):
    """Score the candidate pairs with the evaluation scorer.

    Returns a list of dicts, one per listed pair, sorted by score (highest
    first) and cut at ``max_results`` when that is above zero. Each dict holds
    src_idx, tgt_idx (indices into the units as the search holds them, source
    first), score, cosine, has_semantic, has_dict, has_syntax, syntax_score,
    pairs (the matched (greek lemma, latin lemma) pairs, accent-stripped Greek),
    distinct (the gate count), triggered (below the gate threshold),
    n_channels and idf (the scorer's pair IDF, by matched pair).
    """
    common = _load_common()

    greek_is_source = source_language == 'grc'
    if greek_is_source:
        grc_units, lat_units = source_units, target_units
        grc_path, lat_path = source_path, target_path
        grc_emb, lat_emb = source_emb, target_emb
    else:
        grc_units, lat_units = target_units, source_units
        grc_path, lat_path = target_path, source_path
        grc_emb, lat_emb = target_emb, source_emb

    if grc_emb is None or lat_emb is None:
        raise EvaluationPathError(
            'The evaluation scorer needs the precomputed embeddings of both texts, '
            'and one of them is missing.')
    if len(grc_units) * len(lat_units) > MAX_MATRIX_CELLS:
        raise EvaluationPathError(
            'These two texts are too long to compare line by line with the evaluation '
            f'scorer ({len(grc_units)} x {len(lat_units)} lines). Choose a book or a part of each.')

    fused_score, _ = common.make_fused_scorer(
        grc_path, lat_path, grc_units, lat_units, grc_emb, lat_emb,
        verbose=False, lone_pair_rule='v2', cancellation=cancellation)
    parts = fused_score.parts
    cosine = parts['cosine_matrix']
    dict_matches = parts['dict_matches']
    syntax_scores = parts['syntax_scores']

    # Candidate pairs: every pair with a dictionary or syntax match, and the best
    # cosine-only pairs (cosine above 0.3, nothing else). A cosine-only pair scores
    # 1.2 * cosine (one channel, rarity 1.0, no bonus), so under a cap of M rows only
    # its best M can reach the cut and the list is exactly what scoring every pair
    # would give. With no cap, almost every pair of two books clears 0.3 (456,000 of
    # 462,000 for Aeneid 1 against Iliad 1), so the cosine-only pairs are limited to
    # COSINE_ONLY_UNCAPPED, as the live search limits its semantic channel to 2000.
    keyed = set(dict_matches) | set(syntax_scores)
    limit = max_results if max_results > 0 else COSINE_ONLY_UNCAPPED
    cosine_only, n_above = _best_cosine_only(cosine, keyed, limit)
    candidates = set(keyed)
    candidates.update(cosine_only)

    listed = []
    for n, (g, lt) in enumerate(candidates):
        if cancellation and n % 5000 == 0:
            cancellation.check()
        wms = dict_matches.get((g, lt))
        has_dict = bool(wms)
        distinct = 0
        if has_dict:
            distinct = min(len({a for a, _ in wms}), len({b for _, b in wms}))
        if min_matches > 1 and distinct < min_matches:
            continue
        triggered = distinct < min_lemma_matches
        if triggered and gate == 'exclude':
            continue
        cos = float(cosine[g, lt])
        syn = syntax_scores.get((g, lt), 0.0)
        has_semantic = cos > SEMANTIC_THRESHOLD
        has_syntax = syn > 0
        if not (has_semantic or has_dict or has_syntax):
            continue
        score = fused_score(g, lt)
        if triggered and gate == 'penalty':
            score *= penalty_factor
        src_idx, tgt_idx = (g, lt) if greek_is_source else (lt, g)
        listed.append({
            'src_idx': src_idx, 'tgt_idx': tgt_idx, 'score': score, 'cosine': cos,
            'has_semantic': has_semantic, 'has_dict': has_dict, 'has_syntax': has_syntax,
            'syntax_score': syn, 'pairs': sorted(wms) if has_dict else [],
            'distinct': distinct, 'triggered': triggered,
            'n_channels': int(has_semantic) + int(has_dict) + int(has_syntax),
        })

    # Stable order for ties: score, then position.
    listed.sort(key=lambda r: (-r['score'], r['src_idx'], r['tgt_idx']))
    if max_results > 0:
        listed = listed[:max_results]
    calc_idf = parts['calc_idf']
    for r in listed:
        r['idf'] = {p: (calc_idf(p[0], is_greek=True) + calc_idf(p[1], is_greek=False)) / 2
                    for p in r['pairs']}
    logger.info('Evaluation scorer: %d candidate pairs, %d listed (%d dictionary, %d syntax, %d cosine above %s)',
                len(candidates), len(listed), len(dict_matches), len(syntax_scores),
                n_above, SEMANTIC_THRESHOLD)
    return listed


def display_word_matches(pairs, idf, grc_unit, lat_unit, greek_is_source):
    """Word-match dicts for the row builder, from the pairs the scorer used.

    Each entry names the lemma on both sides and where it sits in each line, so
    the card highlights exactly the words that scored. The Greek and Latin
    lemmas shown are those of the line, not the accent-stripped form.
    """
    common = _load_common()
    grc_lemmas = grc_unit.get('lemmas', [])
    lat_lemmas = lat_unit.get('lemmas', [])
    out = []
    for grc_norm, lat_lemma in pairs:
        g_idx = [i for i, lem in enumerate(grc_lemmas) if common.strip_accents(lem) == grc_norm]
        l_idx = [i for i, lem in enumerate(lat_lemmas) if lem.lower() == lat_lemma]
        if not g_idx or not l_idx:
            continue
        grc_lemma = grc_lemmas[g_idx[0]]
        lat_lemma_shown = lat_lemmas[l_idx[0]]
        entry = {
            'greek_lemma': grc_lemma, 'latin_lemma': lat_lemma_shown,
            'greek_indices': g_idx, 'latin_indices': l_idx,
            'idf_score': idf.get((grc_norm, lat_lemma), 0),
        }
        if greek_is_source:
            entry.update(source_lemma=grc_lemma, target_lemma=lat_lemma_shown,
                         source_indices=g_idx, target_indices=l_idx)
        else:
            entry.update(source_lemma=lat_lemma_shown, target_lemma=grc_lemma,
                         source_indices=l_idx, target_indices=g_idx)
        out.append(entry)
    return out
