"""Targeted re-run: Hebrews x Sahidic Psalms search with biblical_coptic profile.

Checks:
  1. Specific rank of Heb 1:11 / Ps 101:27 (was rank 6,519 pre-fix due to a
     period breaking the quotation run; expected to move into top 50 post-fix).
  2. Overall recall at K on the 29-pair verified-verbatim benchmark.
"""
import os, sys, csv
sys.path.insert(0, '/home/ncoffee/tesserae-v6-dev')
os.chdir('/home/ncoffee/tesserae-v6-dev')
from dotenv import load_dotenv
load_dotenv('/home/ncoffee/tesserae-v6-dev/.env')

from backend.text_processor import TextProcessor
from backend.matcher import Matcher
from backend.scorer import Scorer
from backend.fusion import iter_fusion_search

SOURCE_ID = 'sahidic.psalms.tess'
TARGET_ID = 'sahidica.hebrews.tess'
SOURCE_PATH = f'/home/ncoffee/tesserae-v6-dev/texts/cop/{SOURCE_ID}'
TARGET_PATH = f'/home/ncoffee/tesserae-v6-dev/texts/cop/{TARGET_ID}'

GOLD = '/home/ncoffee/tesserae-v6-dev/evaluation/coptic_recall/nt_psalm_gold_verbatim.csv'

def run():
    tp = TextProcessor()
    src = tp.process_file(SOURCE_PATH, language='cop')
    tgt = tp.process_file(TARGET_PATH, language='cop')
    print(f"source (Psalms): {len(src)} units")
    print(f"target (Hebrews): {len(tgt)} units")
    print("running fusion (biblical_coptic profile)...")
    results = []
    for evt, data in iter_fusion_search(
        source_units=src, target_units=tgt,
        matcher=Matcher(), scorer=Scorer(),
        source_id=SOURCE_ID, target_id=TARGET_ID,
        language='cop', mode='merged',
        max_results=10000,
        source_path=SOURCE_PATH, target_path=TARGET_PATH,
    ):
        if evt == 'complete':
            results = data.get('results', [])
    print(f"got {len(results)} results")

    # Read 29-pair gold. Gold CSV columns: nt_v6_ref, lxx_v6_ref, description.
    # Our search runs source=Psalms (LXX), target=Hebrews (NT), so the pair
    # match in the result list is (lxx_v6_ref, nt_v6_ref).
    gold_pairs = set()
    with open(GOLD) as f:
        reader = csv.DictReader(f)
        for row in reader:
            nt_ref = row.get('nt_v6_ref', '').strip()
            lxx_ref = row.get('lxx_v6_ref', '').strip()
            if nt_ref and lxx_ref:
                gold_pairs.add((lxx_ref, nt_ref))
    print(f"\nGold pairs loaded: {len(gold_pairs)}")

    # Inspect first result's keys to figure out ref format
    if results:
        print(f"\nFirst result keys: {sorted(results[0].keys())[:15]}")
        print(f"First result sample: src_ref={results[0].get('source_ref')}, "
              f"tgt_ref={results[0].get('target_ref')}, "
              f"src_id={results[0].get('source_id')}, "
              f"tgt_id={results[0].get('target_id')}")

    # Save full results for downstream comparison
    import json
    OUT_JSON = '/tmp/punct_fix_hebrews_psalms_results.json'
    with open(OUT_JSON, 'w') as f:
        # Strip non-serializable bits
        slim = []
        for r in results:
            slim.append({k: v for k, v in r.items()
                         if isinstance(v, (str, int, float, bool, list, dict, type(None)))})
        json.dump({'gold_pairs': sorted(list(gold_pairs)), 'results': slim}, f)
    print(f"Saved {len(results)} results to {OUT_JSON}")

    # Build rank lookup for benchmark pairs
    Ks = [10, 50, 100, 500, 1000, 5000]
    hits_at = {K: 0 for K in Ks}
    found_ranks = {}
    for rank_idx, r in enumerate(results, start=1):
        src_ref = r.get('source_ref') or r.get('source_id') or ''
        tgt_ref = r.get('target_ref') or r.get('target_id') or ''
        pair = (str(src_ref).strip(), str(tgt_ref).strip())
        if pair in gold_pairs and pair not in found_ranks:
            found_ranks[pair] = rank_idx

    for pair, rank in sorted(found_ranks.items(), key=lambda x: x[1]):
        for K in Ks:
            if rank <= K:
                hits_at[K] += 1

    print(f"\nRecall@K (n={len(gold_pairs)}):")
    for K in Ks:
        pct = 100.0 * hits_at[K] / len(gold_pairs) if gold_pairs else 0.0
        print(f"  Top {K:>5}: {pct:5.1f}% ({hits_at[K]} of {len(gold_pairs)})")

    # Specific check: Heb 1:11 / Ps 101:27
    print("\nSpecific case checks:")
    target_pairs = [
        ('sahidic.psalms.101.27', 'sahidica.hebrews.1.11'),
        ('sahidic.psalms.101.27', 'sahidica.hebrews.1:11'),
    ]
    for tp in target_pairs:
        rank = found_ranks.get(tp) or "not found (or different ref format)"
        print(f"  {tp}: rank {rank}")

    # Show all benchmark pairs and their ranks
    print(f"\nAll {len(gold_pairs)} benchmark pairs and ranks:")
    found_set = set(found_ranks.keys())
    for p in sorted(gold_pairs):
        rank = found_ranks.get(p, "missing")
        print(f"  rank {rank:>6}: {p[0]:<35} -> {p[1]}")

if __name__ == "__main__":
    run()
