"""Measure Theme Search's confidence rule against a labeled probe set and,
optionally, sweep PERVASIVE_EXCESS_BASELINE to find where it should sit.

Referenced from backend/passage_index.py's own comments since before this
file existed; written 2026-10-08 to close that gap and to do the
single-language refit the pervasive-theme fix (docs/DECISIONS.md,
2026-10-08) left provisional.

A probe set is a JSON list of {"query": ..., "language": <code or "all">,
"present": true/false}, e.g. evaluation/probe_sets/theme_confidence_2026-10-08.json.
"language" absent or "all" means the unfiltered, whole-corpus search.

Usage:
    python evaluation/scripts/calibrate_confidence.py PROBE_SET.json
        [--data-dir DIR] [--embed-endpoint URL]
        [--sweep LO:HI:STEP] [--out OUT.json]

--data-dir points the SAME passage_index module (import, not a copy) at a
different data/passage_index directory -- e.g. a read-only production index
-- by overriding its module-level _DATA_DIR and _LEX_PATH before the first
query. This never writes anything; it only changes where reads come from.

Prints, per language: old-rule and new-rule accuracy against "present",
every remaining miss, and how many queries the new rule calls 'pervasive'.
With --sweep, also prints new-rule accuracy at each candidate
PERVASIVE_EXCESS_BASELINE in the range, for single-language queries only
(the sweep has no effect on an unfiltered query).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np  # noqa: E402

from backend import passage_index as pi  # noqa: E402


def _point_at(data_dir):
    if not data_dir:
        return
    pi._DATA_DIR = data_dir
    pi._LEX_PATH = os.path.join(data_dir, 'desc_fts.sqlite')


def _measure_one(query, language):
    """Every raw number a classification rule might want for one query,
    computed once so a threshold sweep afterward costs nothing further.
    `global_*` are what the shipped rule actually classifies on; `lang_*`
    (a single-language head_lift/coherence, recomputed from that language's
    own rows) are kept only as diagnostic data for comparing alternative
    designs -- the shipped rule (new_level, below) does not use them, because
    the design that did was measured to be worse for Latin, Greek, and
    English (see backend/passage_index.py's PERVASIVE THEMES comment)."""
    q = pi.embed_query(pi._E5_PREFIX + query.strip()[:1500])
    scores = pi._mask_undescribed(pi._score_all(q))
    global_baseline = float(np.median(scores))
    k = min(10, len(scores))
    global_head_lift = float(np.sort(scores)[-k:].mean()) - global_baseline
    global_coherence = pi._cluster_coherence(scores)

    lang_rows = pi._language_rows([language]) if language and language != 'all' else None
    if lang_rows is not None and len(lang_rows):
        lang_scores = scores[lang_rows]
        lang_baseline = float(np.median(lang_scores))
        lk = min(10, len(lang_scores))
        lang_head_lift = float(np.sort(lang_scores)[-lk:].mean()) - lang_baseline
        top_rows = lang_rows[np.argsort(-lang_scores)[:pi.COHERENCE_K]]
        lang_coherence = pi._coherence_of_rows(top_rows)
    else:
        lang_baseline = lang_head_lift = lang_coherence = None

    return {
        'query': query, 'language': language,
        'global_baseline': global_baseline,
        'global_head_lift': global_head_lift,
        'global_coherence': global_coherence,
        'lang_baseline': lang_baseline,
        'lang_head_lift': lang_head_lift,
        'lang_coherence': lang_coherence,
        'excess_baseline': (lang_baseline - global_baseline) if lang_baseline is not None else None,
    }


def old_level(m):
    """What the unfixed rule reports: always the whole-corpus figures,
    regardless of any language filter. Identical to new_level with
    pervasiveness disabled, since the shipped fix only ever PROMOTES this."""
    return pi._confidence_level(m['global_head_lift'], m['global_coherence'])


def new_level(m, pervasive_excess_baseline=None):
    """What the shipped fix reports: the whole-corpus level, promoted to
    'pervasive' when a single-language search's own median sits far enough
    above the whole corpus's (see backend/passage_index.py, _is_pervasive and
    the PERVASIVE THEMES comment above HEAD_WEAK/HEAD_STRONG for why
    head_lift and coherence themselves are never recomputed within one
    language -- an earlier version that did was measured, with this
    script, to make Latin, Greek, and English worse).
    `pervasive_excess_baseline` overrides pi.PERVASIVE_EXCESS_BASELINE for a
    sweep; None uses the module's current value."""
    level = old_level(m)
    if m['lang_baseline'] is None:
        return level
    threshold = (pi.PERVASIVE_EXCESS_BASELINE if pervasive_excess_baseline is None
                else pervasive_excess_baseline)
    old_threshold = pi.PERVASIVE_EXCESS_BASELINE
    pi.PERVASIVE_EXCESS_BASELINE = threshold
    try:
        if pi._is_pervasive(level, m['global_coherence'], m['lang_baseline'], m['global_baseline']):
            return 'pervasive'
        return level
    finally:
        pi.PERVASIVE_EXCESS_BASELINE = old_threshold


def accuracy(rows, measured, level_fn, **kwargs):
    """rows: probe-set entries. measured: same order, from _measure_one.
    Returns (per_language accuracy dict, list of misses)."""
    by_lang = {}
    misses = []
    for r, m in zip(rows, measured):
        lang = r.get('language') or 'all'
        lvl = level_fn(m, **kwargs)
        got_present = lvl != 'low'
        ok = got_present == bool(r['present'])
        by_lang.setdefault(lang, [0, 0])
        by_lang[lang][1] += 1
        if ok:
            by_lang[lang][0] += 1
        else:
            misses.append((lang, r['query'], lvl, r['present']))
    return by_lang, misses


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('probe_set')
    ap.add_argument('--data-dir', default=None,
                    help='override data/passage_index directory (read-only)')
    ap.add_argument('--embed-endpoint', default=None)
    ap.add_argument('--sweep', default=None,
                    help='LO:HI:STEP for PERVASIVE_EXCESS_BASELINE, e.g. 0.005:0.03:0.005')
    ap.add_argument('--out', default=None, help='write raw per-query measurements here')
    args = ap.parse_args()

    if args.embed_endpoint:
        pi.EMBED_ENDPOINT = args.embed_endpoint
    _point_at(args.data_dir)

    rows = json.load(open(args.probe_set, encoding='utf-8'))
    pi._ensure_loaded()
    if not pi._state['ok']:
        print(f'index did not load: {pi._state["error"]}', file=sys.stderr)
        sys.exit(1)
    print(f'index loaded from {pi._DATA_DIR}: {len(pi._ids)} windows', file=sys.stderr)

    measured = []
    for i, r in enumerate(rows):
        m = _measure_one(r['query'], r.get('language'))
        measured.append(m)
        print(f'  [{i+1}/{len(rows)}] {r.get("language","all"):4s} {r["query"][:50]:50s} '
              f'excess={m["excess_baseline"]}', file=sys.stderr)

    if args.out:
        json.dump([{**r, **m} for r, m in zip(rows, measured)], open(args.out, 'w'), indent=1)

    old_by_lang, old_misses = accuracy(rows, measured, old_level)
    new_by_lang, new_misses = accuracy(rows, measured, new_level)
    n_pervasive = sum(1 for r, m in zip(rows, measured) if new_level(m) == 'pervasive')

    langs = sorted(set(old_by_lang) | set(new_by_lang))
    print(f'\n{"language":10s} {"n":>4s} {"old":>8s} {"new":>8s}')
    tot_old = tot_new = tot_n = 0
    for lg in langs:
        o_ok, o_n = old_by_lang.get(lg, [0, 0])
        n_ok, n_n = new_by_lang.get(lg, [0, 0])
        tot_old += o_ok; tot_new += n_ok; tot_n += o_n
        print(f'{lg:10s} {o_n:4d} {100*o_ok/o_n:7.1f}% {100*n_ok/n_n:7.1f}%')
    print(f'{"ALL":10s} {tot_n:4d} {100*tot_old/tot_n:7.1f}% {100*tot_new/tot_n:7.1f}%')
    print(f'\n{n_pervasive} of {len(rows)} queries read as "pervasive" under the new rule '
          f'(PERVASIVE_EXCESS_BASELINE={pi.PERVASIVE_EXCESS_BASELINE})')

    print('\nremaining new-rule misses:')
    for lg, q, lvl, want in new_misses:
        print(f'  {lg:4s} lvl={lvl:9s} present={want!s:5s} {q}')

    if args.sweep:
        lo, hi, step = (float(x) for x in args.sweep.split(':'))
        print(f'\nPERVASIVE_EXCESS_BASELINE sweep ({lo}..{hi} step {step}):')
        print(f'{"value":>8s} {"all-lang acc":>13s}  per-language')
        v = lo
        while v <= hi + 1e-12:
            by_lang, _ = accuracy(rows, measured, new_level, pervasive_excess_baseline=v)
            ok = sum(x[0] for x in by_lang.values())
            n = sum(x[1] for x in by_lang.values())
            per_lang = ' '.join(f'{lg}:{100*x[0]/x[1]:.0f}%' for lg, x in sorted(by_lang.items()))
            print(f'{v:8.4f} {100*ok/n:12.1f}%  {per_lang}')
            v += step


if __name__ == '__main__':
    main()
