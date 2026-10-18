#!/usr/bin/env python3
"""
Benchmark cross-lingual fusion search against Knauer's Aeneid 1 / Iliad gold pairs.

Evaluation methodology (matching article):
  For each gold pair (Il X.Y, Aen 1.Z), rank ALL Iliad lines in book X
  by their fusion score with Aen 1.Z. If Il X.Y is in the top 50, count as found.

Usage:
    source venv/bin/activate && source .env
    python evaluation/scripts/benchmark_knauer_crosslingual.py
"""

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crosslingual_common import (  # noqa: E402
    BENCHMARKS_DIR, TEXTS_DIR, make_fused_scorer, ref_matches, normalize_ref,
)


def load_benchmark():
    with open(BENCHMARKS_DIR / "knauer_aeneid1_iliad.json") as f:
        return json.load(f)


def run_benchmark_for_book(grc_file, lat_file, gold_pairs, book_num):
    """Run per-target-line evaluation for one Iliad book vs Aeneid 1."""
    from backend.text_processor import TextProcessor
    from backend.embedding_storage import load_embeddings

    tp = TextProcessor()

    grc_path = TEXTS_DIR / "grc" / grc_file
    lat_path = TEXTS_DIR / "la" / lat_file

    grc_units = tp.process_file(str(grc_path), 'grc')
    lat_units = tp.process_file(str(lat_path), 'la')
    print(f"  {len(grc_units)} Greek × {len(lat_units)} Latin units")

    grc_emb = load_embeddings(str(grc_path), 'grc')
    lat_emb = load_embeddings(str(lat_path), 'la')
    fused_score, _ = make_fused_scorer(grc_path, lat_path, grc_units, lat_units, grc_emb, lat_emb)

    # --- Per-target-line evaluation ---
    # For each gold pair, rank all Greek lines for the gold's Aeneid target line
    found_at = {10: 0, 50: 0, 100: 0, 200: 0}
    total = len(gold_pairs)
    missed = []

    for gp in gold_pairs:
        # Find the target (Latin/Aeneid) unit index
        tgt_ref_parsed = normalize_ref(gp['target_ref'])
        if tgt_ref_parsed is None:
            continue

        lat_idx = None
        for i, unit in enumerate(lat_units):
            if ref_matches(unit.get('ref', ''), gp['target_ref'], tolerance=0):
                lat_idx = i
                break
        if lat_idx is None:
            # Try with tolerance
            for i, unit in enumerate(lat_units):
                if ref_matches(unit.get('ref', ''), gp['target_ref'], tolerance=1):
                    lat_idx = i
                    break
        if lat_idx is None:
            missed.append((gp, 'target_not_found'))
            continue

        # Find the gold source (Greek/Iliad) unit index
        src_idx = None
        for i, unit in enumerate(grc_units):
            if ref_matches(unit.get('ref', ''), gp['source_ref'], tolerance=0):
                src_idx = i
                break
        if src_idx is None:
            for i, unit in enumerate(grc_units):
                if ref_matches(unit.get('ref', ''), gp['source_ref'], tolerance=1):
                    src_idx = i
                    break
        if src_idx is None:
            missed.append((gp, 'source_not_found'))
            continue

        # Score ALL Greek lines for this Latin target line
        gold_score = fused_score(src_idx, lat_idx)
        rank = 1  # 1-indexed
        if gold_score == float('-inf'):
            # Removed by XL_LONE_PAIR=drop: the pair is not listed, so it is not retrieved.
            rank = len(grc_units) + 1
        else:
            for gi in range(len(grc_units)):
                if gi == src_idx:
                    continue
                if fused_score(gi, lat_idx) > gold_score:
                    rank += 1

        for cutoff in found_at:
            if rank <= cutoff:
                found_at[cutoff] += 1

        if rank > 50:
            missed.append((gp, f'rank_{rank}'))

    return found_at, total, missed, grc_units, lat_units


def main():
    gold_pairs = load_benchmark()
    print(f"Loaded {len(gold_pairs)} Knauer gold pairs")

    by_book = {}
    for gp in gold_pairs:
        m = re.search(r'part\.(\d+)', gp.get('source_work', ''))
        if m:
            book = int(m.group(1))
            by_book.setdefault(book, []).append(gp)

    print(f"Books: {sorted(by_book.keys())}")

    overall = {10: 0, 50: 0, 100: 0, 200: 0}
    overall_total = 0
    all_missed = []

    for book in sorted(by_book.keys()):
        grc_file = f"homer.iliad.part.{book}.tess"
        lat_file = "vergil.aeneid.part.1.tess"
        if not (TEXTS_DIR / "grc" / grc_file).exists():
            print(f"  SKIP: {grc_file}")
            continue

        n_gold = len(by_book[book])
        print(f"\n{'='*60}")
        print(f"Iliad {book} vs Aeneid 1 ({n_gold} gold pairs)")
        print(f"{'='*60}")

        t0 = time.time()
        found_at, total, missed, _, _ = run_benchmark_for_book(
            grc_file, lat_file, by_book[book], book)
        elapsed = time.time() - t0

        for cutoff in found_at:
            overall[cutoff] += found_at[cutoff]
        overall_total += total
        all_missed.extend(missed)

        print(f"  Time: {elapsed:.1f}s")
        for cutoff in sorted(found_at):
            print(f"  @{cutoff:>3}: {found_at[cutoff]:>2}/{total} ({found_at[cutoff]/total*100:.1f}%)")

    print(f"\n{'='*60}")
    print(f"OVERALL ({overall_total} gold pairs)")
    print(f"{'='*60}")
    for cutoff in sorted(overall):
        pct = overall[cutoff] / overall_total * 100 if overall_total else 0
        print(f"  @{cutoff:>3}: {overall[cutoff]:>3}/{overall_total} ({pct:.1f}%)")

    # Show some missed pairs
    rank_misses = [(gp, reason) for gp, reason in all_missed if reason.startswith('rank_')]
    ref_misses = [(gp, reason) for gp, reason in all_missed if not reason.startswith('rank_')]
    print(f"\nMissed @50: {len(rank_misses)} (ranked too low)")
    print(f"Unresolved refs: {len(ref_misses)}")
    if rank_misses:
        # Show worst-ranked
        ranked = sorted(rank_misses, key=lambda x: int(x[1].split('_')[1]))
        for gp, reason in ranked[:15]:
            print(f"  {reason}: {gp['source_ref']} / {gp['target_ref']}")


if __name__ == '__main__':
    main()
