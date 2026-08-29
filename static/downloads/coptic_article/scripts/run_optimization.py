"""Iterative weight optimization for Coptic-Coptic recall on Hebrews × Psalms.

Strategy:
  1. Load TSK gold pairs (verse-strong subset, votes >= 20).
  2. Each iteration: pick a weight config (one of: baseline, randomized search
     in a sensible range, or hill-climbed from best-so-far).
  3. Run V6 fusion with those weights.
  4. For each gold pair, find rank in V6's output. Compute recall@50/100/500/1000.
  5. Keep best, log everything.

Each fusion run is ~30 seconds. Default budget: 15 iterations.
"""
import os
import sys
import json
import time
import random
import argparse
import csv
from copy import deepcopy
from datetime import datetime, timezone

sys.path.insert(0, '/home/ncoffee/tesserae-v6-dev')
os.chdir('/home/ncoffee/tesserae-v6-dev')

from dotenv import load_dotenv
load_dotenv('/home/ncoffee/tesserae-v6-dev/.env')

# Avoid importing fusion before env is set
from backend.fusion import (
    iter_fusion_search,
    CHANNEL_WEIGHTS as DEFAULT_WEIGHTS,
)
from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer


# Channels active for Coptic. semantic was added 2026-05-15 (multilingual_e5 embeddings).
# quotation was added 2026-05-15 (Phase 7 finder for runs of consecutive identical tokens).
COPTIC_CHANNELS = [
    'edit_distance', 'sound', 'exact', 'lemma', 'dictionary',
    'rare_word', 'syntax', 'syntax_structural', 'lemma_min1',
    'semantic', 'quotation',
]


def load_gold(path, book='Heb', min_votes=20):
    """Load TSK gold and filter to one NT book."""
    pairs = []
    with open(path) as f:
        for row in csv.DictReader(f):
            if row['nt_book'] != book:
                continue
            try:
                v = int(row['votes'])
            except ValueError:
                continue
            if v < min_votes:
                continue
            pairs.append({
                'nt_v6_ref': row['nt_v6_ref'],
                'lxx_v6_ref': row['lxx_v6_ref'],
                'votes': v,
            })
    return pairs


def normalize_ref(s):
    return ' '.join((s or '').split()).lower()


def run_fusion(source_id, target_id, language, weights, src_path, tgt_path):
    """Run V6 fusion with custom weights, return ranked results.

    Weights are applied by mutating fusion.CHANNEL_WEIGHTS in place — the
    fusion pipeline reads from this module-level dict during scoring.
    """
    import backend.fusion as fusion_mod

    # Save and replace global weights
    saved_weights = dict(fusion_mod.CHANNEL_WEIGHTS)
    fusion_mod.CHANNEL_WEIGHTS.clear()
    fusion_mod.CHANNEL_WEIGHTS.update(weights)

    try:
        tp = TextProcessor()
        matcher = Matcher()
        scorer = Scorer()

        src_units = tp.process_file(src_path, language=language)
        tgt_units = tp.process_file(tgt_path, language=language)

        final = []
        for evt, data in iter_fusion_search(
            source_units=src_units, target_units=tgt_units,
            matcher=matcher, scorer=scorer,
            source_id=source_id, target_id=target_id,
            language=language, mode='merged', max_results=5000,
            source_path=src_path, target_path=tgt_path,
        ):
            if evt == 'complete':
                final = data.get('results', [])
    finally:
        # Restore baseline weights
        fusion_mod.CHANNEL_WEIGHTS.clear()
        fusion_mod.CHANNEL_WEIGHTS.update(saved_weights)

    return final


def measure_recall(results, gold_pairs):
    """For each gold pair, find its rank in results.

    Returns:
      per_pair: list of dicts with rank (or None) for each gold pair
      recall_at: dict K -> recall@K
    """
    rank_index = {}
    for i, r in enumerate(results):
        sref = normalize_ref(r.get('source', {}).get('ref', ''))
        tref = normalize_ref(r.get('target', {}).get('ref', ''))
        rank_index[(sref, tref)] = i + 1

    per_pair = []
    for g in gold_pairs:
        key = (normalize_ref(g['nt_v6_ref']), normalize_ref(g['lxx_v6_ref']))
        rank = rank_index.get(key)
        per_pair.append({**g, 'rank': rank})

    n = len(per_pair)
    recall_at = {}
    for K in (10, 50, 100, 200, 500, 1000, 2000, 5000):
        hits = sum(1 for p in per_pair if p['rank'] and p['rank'] <= K)
        recall_at[K] = hits / n if n else 0.0

    return per_pair, recall_at


def sample_weight_config(base, rng, log_range=1.0, biblical_bias=False):
    """Sample a perturbed weight config around base. Multiplicative jitter.

    log_range: log-uniform jitter half-width. 1.0 = [0.5x, 2x], 2.0 = [0.25x, 4x],
        3.0 = [0.125x, 8x], 3.3 = [0.1x, ~10x].

    biblical_bias: if True, additionally bias the search toward configurations
        appropriate for biblical-prose recall:
          - rare_word: pull strongly downward (Phase 5 diagnosis — rarity penalizes
            common biblical vocabulary).
          - sound: pull upward (Phase 4 optimization signal — phonetic-trigram
            overlap is a more reliable channel for biblical Coptic).
          - lemma, lemma_min1: pull upward (verbatim biblical quotation matters).
    """
    out = dict(base)
    for k in COPTIC_CHANNELS:
        if k not in out:
            continue
        # Log-uniform jitter in [2^-log_range, 2^log_range]
        factor = 2 ** rng.uniform(-log_range, log_range)
        if biblical_bias:
            if k == 'rare_word':
                # pull toward downsweep: bias factor by 0.5x
                factor *= 0.5
            elif k == 'sound':
                # pull toward upsweep: bias factor by 1.5x
                factor *= 1.5
            elif k in ('lemma',):
                factor *= 1.25
        out[k] = round(out[k] * factor, 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--gold', default='evaluation/coptic_recall/nt_psalm_gold_lxx.csv')
    ap.add_argument('--source-id', default='sahidica.hebrews.tess')
    ap.add_argument('--target-id', default='sahidic.psalms.tess')
    ap.add_argument('--language', default='cop')
    ap.add_argument('--book', default='Heb')
    ap.add_argument('--min-votes', type=int, default=20)
    ap.add_argument('--iterations', type=int, default=15)
    ap.add_argument('--objective', default='recall_at_100',
                    help='Which K to optimize for (recall_at_50, _100, _500, _1000)')
    ap.add_argument('--profile', default='biblical_coptic',
                    help='weight profile to baseline from; cop uses biblical_coptic')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--log', default='evaluation/coptic_recall/optimization_log.jsonl')
    ap.add_argument('--results-dir', default='evaluation/coptic_recall/runs')
    ap.add_argument('--log-range', type=float, default=1.0,
                    help='Log-uniform jitter half-width. 1.0=[0.5x,2x], 3.3=[0.1x,10x]')
    ap.add_argument('--biblical-bias', action='store_true',
                    help='Bias perturbations toward biblical-prose-appropriate weights')
    args = ap.parse_args()

    os.makedirs(args.results_dir, exist_ok=True)
    rng = random.Random(args.seed)

    src_path = f'/home/ncoffee/tesserae-v6-dev/texts/{args.language}/{args.source_id}'
    tgt_path = f'/home/ncoffee/tesserae-v6-dev/texts/{args.language}/{args.target_id}'

    gold = load_gold(args.gold, book=args.book, min_votes=args.min_votes)
    print(f"[setup] {len(gold)} gold pairs ({args.book}, votes>={args.min_votes})")
    print(f"[setup] source={args.source_id}, target={args.target_id}")
    print(f"[setup] {args.iterations} iterations, objective={args.objective}")

    log_f = open(args.log, 'a')
    best = None
    objective_key = int(args.objective.split('_')[-1])

    # Iteration 0: baseline (current weights)
    # The baseline must be the profile this corpus ACTUALLY uses. It was
    # DEFAULT_WEIGHTS, the Latin-epic profile, in which quotation carries weight
    # 0.0 -- so a run meant to measure the Coptic quotation channel never
    # exercised it at all, and reported a baseline for a configuration the site
    # never applies to Coptic.
    from backend.fusion import WEIGHT_PROFILES
    base_weights = dict(WEIGHT_PROFILES.get(args.profile) or DEFAULT_WEIGHTS)
    print(f"[setup] weight profile: {args.profile} "
          f"(quotation={base_weights.get('quotation')})")
    iterations = [('baseline', base_weights)]

    # Subsequent iterations: random perturbations from baseline + hill-climbed
    for i in range(args.iterations - 1):
        iterations.append((f'sample_{i+1}', None))  # filled in dynamically

    for idx, (label, weights) in enumerate(iterations):
        if weights is None:
            # Hill-climb from current best (if any) else baseline
            seed_weights = best['weights'] if best else dict(base_weights)
            weights = sample_weight_config(seed_weights, rng,
                                           log_range=args.log_range,
                                           biblical_bias=args.biblical_bias)

        t0 = time.time()
        results = run_fusion(args.source_id, args.target_id, args.language,
                             weights, src_path, tgt_path)
        per_pair, recall_at = measure_recall(results, gold)
        elapsed = time.time() - t0

        score = recall_at[objective_key]
        improved = best is None or score > best['recall_at'][objective_key]
        record = {
            'iteration': idx,
            'label': label,
            'weights': weights,
            'recall_at': recall_at,
            'n_results': len(results),
            'elapsed_s': round(elapsed, 1),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        log_f.write(json.dumps(record) + '\n')
        log_f.flush()

        print(f"[iter {idx:2}] {label:<10}  R@50={recall_at[50]:.3f}  "
              f"R@100={recall_at[100]:.3f}  R@500={recall_at[500]:.3f}  "
              f"R@1000={recall_at[1000]:.3f}  ({elapsed:.0f}s)"
              + ("  ⭐ new best" if improved else ""))

        # Save the per-pair CSV for the first and best iterations
        if idx == 0 or improved:
            csv_path = os.path.join(args.results_dir,
                                    f"iter_{idx:02d}_{label}_pairs.csv")
            with open(csv_path, 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(per_pair[0].keys()))
                w.writeheader()
                w.writerows(per_pair)

        if improved:
            best = record

    log_f.close()
    print(f"\n[done] best: iter {best['iteration']}, {best['label']}, "
          f"recall@{objective_key}={best['recall_at'][objective_key]:.3f}")
    print(f"[done] best weights: {best['weights']}")


if __name__ == '__main__':
    main()
