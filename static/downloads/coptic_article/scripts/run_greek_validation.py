"""Run Greek-Greek validation with Phase 6 best weights.

Loads the iter-27 best-composite weights from phase6_best_weights.json,
applies them to Greek Hebrews × Greek LXX Psalms, and compares recall to
the Greek-Greek baseline from Phase 5.
"""
import json
import os
import sys
import time
import csv

sys.path.insert(0, '/home/ncoffee/tesserae-v6-dev')
os.chdir('/home/ncoffee/tesserae-v6-dev')

from dotenv import load_dotenv
load_dotenv('/home/ncoffee/tesserae-v6-dev/.env')

from backend.fusion import iter_fusion_search
from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
import backend.fusion as fusion_mod


def load_gold(path):
    pairs = []
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                v = int(r['votes'])
            except ValueError:
                v = 0
            if v >= 20:
                pairs.append({
                    'nt_v6_ref': r['nt_v6_ref'],
                    'lxx_v6_ref': r['lxx_v6_ref'],
                    'votes': v,
                })
    return pairs


def normalize_ref(s):
    return ' '.join((s or '').split()).lower()


def main():
    # Load Phase 6 best weights
    with open('evaluation/coptic_recall/phase6_best_weights.json') as f:
        phase6 = json.load(f)

    print(f"Greek-Greek validation: applying Phase 6 best-composite weights (iter {phase6['best_composite']['iteration']})")
    print(f"Coptic R@100 with these weights: {phase6['best_composite']['recall_at']['100']:.3f}")
    print(f"Coptic R@500 with these weights: {phase6['best_composite']['recall_at']['500']:.3f}")
    print()
    print(f"Weights to apply:")
    for k, v in phase6['best_composite']['weights'].items():
        print(f"  {k:<20} {v}")
    print()

    weights = phase6['best_composite']['weights']

    # Greek-Greek setup
    src_id = 'novum_testamentum.ad_hebraeos.tess'
    tgt_id = 'septuaginta.psalmi.tess'
    src_path = f'/home/ncoffee/tesserae-v6-dev/texts/grc/{src_id}'
    tgt_path = f'/home/ncoffee/tesserae-v6-dev/texts/grc/{tgt_id}'

    gold = load_gold('evaluation/coptic_recall/nt_psalm_gold_greek.csv')
    print(f"Greek gold: {len(gold)} pairs (Heb × LXX Psalmi, votes ≥ 20)")
    print()

    # Save baseline weights, swap to Phase 6
    saved_weights = dict(fusion_mod.CHANNEL_WEIGHTS)
    fusion_mod.CHANNEL_WEIGHTS.clear()
    fusion_mod.CHANNEL_WEIGHTS.update(weights)

    try:
        tp = TextProcessor()
        matcher = Matcher()
        scorer = Scorer()
        print(f"Loading Greek texts...")
        src_units = tp.process_file(src_path, language='grc')
        tgt_units = tp.process_file(tgt_path, language='grc')
        print(f"src={len(src_units)}, tgt={len(tgt_units)}")
        print()
        print(f"Running V6 fusion (Greek, will take ~10 min — has semantic channel)...")
        t0 = time.time()
        final = []
        for evt, data in iter_fusion_search(
            source_units=src_units, target_units=tgt_units,
            matcher=matcher, scorer=scorer,
            source_id=src_id, target_id=tgt_id,
            language='grc', mode='merged', max_results=5000,
            source_path=src_path, target_path=tgt_path,
        ):
            if evt == 'complete':
                final = data.get('results', [])
        elapsed = time.time() - t0
        print(f"Done in {elapsed:.0f}s. Got {len(final)} results.")
    finally:
        fusion_mod.CHANNEL_WEIGHTS.clear()
        fusion_mod.CHANNEL_WEIGHTS.update(saved_weights)

    # Measure recall
    rank_index = {}
    for i, r in enumerate(final):
        s = normalize_ref(r.get('source', {}).get('ref', ''))
        t = normalize_ref(r.get('target', {}).get('ref', ''))
        rank_index[(s, t)] = i + 1

    per_pair = []
    for g in gold:
        key = (normalize_ref(g['nt_v6_ref']), normalize_ref(g['lxx_v6_ref']))
        rank = rank_index.get(key)
        per_pair.append({**g, 'rank': rank})

    n = len(per_pair)
    recall_at = {}
    for K in (10, 50, 100, 200, 500, 1000, 2000, 5000):
        hits = sum(1 for p in per_pair if p['rank'] and p['rank'] <= K)
        recall_at[K] = hits / n if n else 0.0

    print()
    print(f"=== Greek-Greek recall with Phase 6 weights ===")
    for K in (50, 100, 500, 1000, 5000):
        print(f"  R@{K:<5} {recall_at[K]:.3f}  ({sum(1 for p in per_pair if p['rank'] and p['rank']<=K)}/{n})")

    print()
    print(f"=== Comparison ===")
    print(f"{'':16}{'baseline':>12}{'Phase 6':>12}{'delta':>12}")
    baseline_greek = {50: 0.000, 100: 0.032, 500: 0.121, 1000: 0.129}
    for K in (50, 100, 500, 1000):
        b = baseline_greek[K]
        p = recall_at[K]
        delta = p - b
        rel = (p/b - 1)*100 if b > 0 else float('inf')
        rel_str = f"{rel:+.0f}%" if b > 0 else "(undef)"
        print(f"  R@{K:<5}{'':<8}{b:>10.3f} {p:>10.3f}  {delta:+.3f} ({rel_str})")

    # Save
    out = {
        'phase6_weights': weights,
        'phase6_iteration': phase6['best_composite']['iteration'],
        'greek_baseline_recall': baseline_greek,
        'greek_phase6_recall': recall_at,
        'n_gold_pairs': n,
        'elapsed_s': round(elapsed, 1),
        'per_pair': per_pair,
    }
    with open('evaluation/coptic_recall/greek_phase6_validation.json', 'w') as f:
        json.dump(out, f, indent=2)
    print()
    print(f"Saved greek_phase6_validation.json")


if __name__ == '__main__':
    main()
