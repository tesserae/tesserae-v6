"""Optimize the biblical_coptic_thematic weight profile.

Starts from the unoptimized biblical_coptic_thematic profile in
backend/fusion.py and searches for weights that maximize recall on the
broader TSK 124-pair benchmark (paraphrase + thematic recall), while
keeping verbatim quotation recall above a sanity floor.

Why two co-tracked benchmarks?
  - TSK 124-pair (votes >= 20) measures thematic + paraphrase + verbatim
    together. R@500 is the optimization objective.
  - 29-pair verified-verbatim benchmark measures only verbatim quotation
    recall. We refuse iterations where R@50 on this benchmark drops below
    a sanity floor (default 60 percent, 18 of 29), to keep the thematic
    profile from collapsing the verbatim capability entirely.

Usage:
    python evaluation/coptic_recall/run_optimization_thematic.py
    python evaluation/coptic_recall/run_optimization_thematic.py --iterations 50

Each iteration runs the full Hebrews x Sahidic Psalms fusion search
(roughly 9 minutes). 30 iterations is roughly 4.5 hours. The script logs
to a JSONL file, so it can be killed and resumed by re-running.
"""
import argparse
import csv
import json
import os
import random
import sys
import time
from copy import deepcopy
from datetime import datetime, timezone

sys.path.insert(0, '/home/ncoffee/tesserae-v6-dev')
os.chdir('/home/ncoffee/tesserae-v6-dev')

from dotenv import load_dotenv
load_dotenv('/home/ncoffee/tesserae-v6-dev/.env')

from backend.fusion import iter_fusion_search, WEIGHT_PROFILES
from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer

# Channels active for Coptic.
COPTIC_CHANNELS = [
    'edit_distance', 'sound', 'exact', 'lemma', 'dictionary',
    'rare_word', 'syntax', 'syntax_structural', 'lemma_min1',
    'semantic', 'quotation',
]

SRC_ID = 'sahidica.hebrews.tess'
TGT_ID = 'sahidic.psalms.tess'
SRC_PATH = f'/home/ncoffee/tesserae-v6-dev/texts/cop/{SRC_ID}'
TGT_PATH = f'/home/ncoffee/tesserae-v6-dev/texts/cop/{TGT_ID}'

BROAD_GOLD_PATH = 'evaluation/coptic_recall/nt_psalm_gold_lxx.csv'
VERBATIM_GOLD_PATH = 'evaluation/coptic_recall/nt_psalm_gold_verbatim.csv'


def load_broad_gold(path, book='Heb', min_votes=20):
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
            pairs.append({'nt_v6_ref': row['nt_v6_ref'], 'lxx_v6_ref': row['lxx_v6_ref']})
    return pairs


def load_verbatim_gold(path):
    pairs = []
    with open(path) as f:
        for row in csv.DictReader(f):
            pairs.append({'nt_v6_ref': row['nt_v6_ref'], 'lxx_v6_ref': row['lxx_v6_ref']})
    return pairs


def normalize_ref(s):
    return ' '.join((s or '').split()).lower()


def run_fusion(weights):
    """Run a single fusion search with the given weights. Returns ranked results.

    Important: for Coptic, fuse_results() in fusion.py reads weights from
    get_weight_profile(language='cop'), which returns WEIGHT_PROFILES['biblical_coptic'].
    Mutating CHANNEL_WEIGHTS at the module level has no effect on Coptic searches.
    To make the optimizer's weight choices actually flow through, we temporarily
    overwrite WEIGHT_PROFILES['biblical_coptic'] with the test weights, then
    restore it after the run.
    """
    import backend.fusion as fusion_mod
    saved = dict(fusion_mod.WEIGHT_PROFILES['biblical_coptic'])
    fusion_mod.WEIGHT_PROFILES['biblical_coptic'].clear()
    fusion_mod.WEIGHT_PROFILES['biblical_coptic'].update(weights)
    try:
        tp = TextProcessor()
        src_units = tp.process_file(SRC_PATH, language='cop')
        tgt_units = tp.process_file(TGT_PATH, language='cop')
        final = []
        for evt, data in iter_fusion_search(
            source_units=src_units, target_units=tgt_units,
            matcher=Matcher(), scorer=Scorer(),
            source_id=SRC_ID, target_id=TGT_ID,
            language='cop', mode='merged', max_results=5000,
            source_path=SRC_PATH, target_path=TGT_PATH,
        ):
            if evt == 'complete':
                final = data.get('results', [])
        return final
    finally:
        fusion_mod.WEIGHT_PROFILES['biblical_coptic'].clear()
        fusion_mod.WEIGHT_PROFILES['biblical_coptic'].update(saved)


def measure_recall(results, gold):
    rank_index = {}
    for i, r in enumerate(results):
        s = normalize_ref(r.get('source', {}).get('ref', ''))
        t = normalize_ref(r.get('target', {}).get('ref', ''))
        rank_index[(s, t)] = i + 1
    per_pair = []
    for g in gold:
        key = (normalize_ref(g['nt_v6_ref']), normalize_ref(g['lxx_v6_ref']))
        per_pair.append({**g, 'rank': rank_index.get(key)})
    n = len(per_pair)
    recall_at = {}
    for K in (10, 50, 100, 200, 500, 1000, 2000, 5000):
        hits = sum(1 for p in per_pair if p['rank'] and p['rank'] <= K)
        recall_at[K] = hits / n if n else 0.0
    return per_pair, recall_at


def sample_weight_config(base, rng, log_range=1.5, thematic_bias=True):
    """Sample a perturbed weight config from base.

    log_range=1.5 means each weight is multiplied by a factor in
    [2^-1.5, 2^1.5] = [~0.35x, ~2.83x].

    thematic_bias=True biases the search toward thematic-recall-appropriate
    configurations:
      - semantic, dictionary: pull upward (the paraphrase signals)
      - quotation, sound: pull downward (verbatim dominators)
      - rare_word: pull slightly upward (rare paraphrase content words help)
    """
    out = dict(base)
    for k in COPTIC_CHANNELS:
        if k not in out:
            continue
        factor = 2 ** rng.uniform(-log_range, log_range)
        if thematic_bias:
            if k == 'semantic':
                factor *= 1.5
            elif k == 'dictionary':
                factor *= 1.4
            elif k == 'quotation':
                factor *= 0.6
            elif k == 'sound':
                factor *= 0.7
            elif k == 'rare_word':
                factor *= 1.2
        out[k] = round(out[k] * factor, 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iterations', type=int, default=30)
    ap.add_argument('--seed', type=int, default=2026)
    ap.add_argument('--log', default='evaluation/coptic_recall/optimization_thematic_log.jsonl')
    ap.add_argument('--results-dir', default='evaluation/coptic_recall/runs_thematic')
    ap.add_argument('--objective', default='recall_at_500',
                    help='K to optimize on the broad TSK benchmark (R@50, _100, _500, _1000)')
    ap.add_argument('--verbatim-floor', type=float, default=0.70,
                    help='Verbatim 29-pair R@50 floor below which iterations are rejected')
    ap.add_argument('--log-range', type=float, default=1.5)
    ap.add_argument('--start-profile', default='biblical_coptic',
                    help='Profile name to start the search from (biblical_coptic gives a '
                         'verbatim-strong starting point we can thematic-bias from)')
    args = ap.parse_args()

    os.makedirs(args.results_dir, exist_ok=True)
    rng = random.Random(args.seed)

    broad_gold = load_broad_gold(BROAD_GOLD_PATH)
    verbatim_gold = load_verbatim_gold(VERBATIM_GOLD_PATH)
    print(f"[setup] broad gold: {len(broad_gold)} pairs (TSK Heb votes>=20)")
    print(f"[setup] verbatim gold: {len(verbatim_gold)} pairs")
    print(f"[setup] iterations: {args.iterations}, objective: {args.objective}")
    print(f"[setup] verbatim R@50 floor: {args.verbatim_floor:.0%}")

    starting_weights = dict(WEIGHT_PROFILES[args.start_profile])
    print(f"[setup] starting from {args.start_profile} profile")
    print(f"        {starting_weights}")

    log_f = open(args.log, 'a')
    best = None
    objective_key = int(args.objective.split('_')[-1])

    iterations = [(f'{args.start_profile}_baseline', dict(starting_weights))]
    for i in range(args.iterations - 1):
        iterations.append((f'sample_{i+1}', None))

    for idx, (label, weights) in enumerate(iterations):
        if weights is None:
            seed_w = best['weights'] if best else dict(starting_weights)
            weights = sample_weight_config(seed_w, rng, log_range=args.log_range,
                                           thematic_bias=True)

        t0 = time.time()
        results = run_fusion(weights)
        broad_per_pair, broad_recall = measure_recall(results, broad_gold)
        _, verb_recall = measure_recall(results, verbatim_gold)
        elapsed = time.time() - t0

        objective_score = broad_recall[objective_key]
        verbatim_r50 = verb_recall[50]

        if verbatim_r50 < args.verbatim_floor:
            verdict = f"rejected (verbatim R@50={verbatim_r50:.0%} below floor {args.verbatim_floor:.0%})"
            improved = False
        else:
            improved = best is None or objective_score > best['broad_recall'][objective_key]
            verdict = "new best" if improved else "no improvement"

        record = {
            'iteration': idx,
            'label': label,
            'weights': weights,
            'broad_recall': broad_recall,
            'verbatim_recall': verb_recall,
            'objective_score': objective_score,
            'verbatim_r50': verbatim_r50,
            'verdict': verdict,
            'elapsed_s': round(elapsed, 1),
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        log_f.write(json.dumps(record) + '\n')
        log_f.flush()

        print(f"[iter {idx:2}] {label:<22} broad_R@500={broad_recall[500]:.3f} "
              f"R@100={broad_recall[100]:.3f}  verbatim_R@50={verbatim_r50:.3f}  "
              f"({elapsed:.0f}s)  {verdict}")

        if improved:
            best = record
            csv_path = os.path.join(args.results_dir, f"iter_{idx:02d}_{label}_pairs.csv")
            with open(csv_path, 'w', newline='') as f:
                w = csv.DictWriter(f, fieldnames=list(broad_per_pair[0].keys()))
                w.writeheader()
                w.writerows(broad_per_pair)

    log_f.close()
    if best:
        print(f"\n[done] best iteration {best['iteration']}, {best['label']}")
        print(f"       broad TSK R@500={best['broad_recall'][500]:.3f}, "
              f"R@100={best['broad_recall'][100]:.3f}, "
              f"R@1000={best['broad_recall'][1000]:.3f}")
        print(f"       verbatim 29-pair R@50={best['verbatim_r50']:.3f}, "
              f"R@500={best['verbatim_recall'][500]:.3f}")
        print(f"       weights: {best['weights']}")
    else:
        print("[done] no iteration passed the verbatim floor; consider lowering --verbatim-floor")


if __name__ == '__main__':
    main()
