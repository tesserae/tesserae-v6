#!/usr/bin/env python3
"""Export V6 gold-standard benchmark subsets as labeled CSV + JSON files.

Reads each gold JSON from evaluation/benchmarks/, writes:
  - A CSV with a metadata header comment block (provenance, pair count, parent dataset)
  - A copy of the original JSON

Output directory: static/downloads/benchmarks/v6_gold/
"""

import csv
import json
import os
import shutil
import sys

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BENCHMARKS_DIR = os.path.join(PROJECT_ROOT, "evaluation", "benchmarks")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "static", "downloads", "benchmarks", "v6_gold")

# Benchmark definitions: source JSON filename -> metadata
BENCHMARKS = [
    {
        "json_file": "lucan_vergil_lexical_benchmark.json",
        "output_stem": "lucan_vergil_gold",
        "title": "Lucan Bellum Civile 1 vs Vergil Aeneid",
        "pair_count": 213,
        "gold_criterion": "Types 4-5 on 1-5 scholarly relevance scale",
        "parent_dataset": "bench41.txt (3,410 entries, Tesserae V3 benchmark)",
        "commentators": "Roche, Wick/Viansino, Haskins, Teubner-Braun",
        "reference": "Coffee et al. (2012); see BENCHMARK_METHODOLOGY.md",
        "language": "Latin to Latin",
        "csv_columns": ["source_ref", "target_ref", "type", "target_work"],
    },
    {
        "json_file": "vf_vergil_gold.json",
        "output_stem": "vf_vergil_gold",
        "title": "Valerius Flaccus Argonautica 1 vs Vergil Aeneid",
        "pair_count": 521,
        "gold_criterion": "Commentary-attested parallels (binary: attested or not)",
        "parent_dataset": "Dexter et al. 2024 VF intertext dataset (945 entries)",
        "commentators": "Kleywegt, Zissos, Spaltenstein",
        "reference": "Dexter et al. (2023) JOHD 10.5334/johd.153; see BENCHMARK_METHODOLOGY.md",
        "language": "Latin to Latin",
        "csv_columns": ["source_ref", "target_ref", "target_work"],
    },
    {
        "json_file": "achilleid_gold_2plus_commentators.json",
        "output_stem": "achilleid_gold",
        "title": "Statius Achilleid vs Vergil Aeneid, Ovid Metamorphoses, Statius Thebaid",
        "pair_count": 128,
        "gold_criterion": "2+ independent commentators citing the parallel",
        "parent_dataset": "Geneva 2015 seminar dataset (904 entries)",
        "commentators": "Dilke, Nuzzo, Ripoll-Soubiran, Uccellini",
        "reference": "Geneva 2015 seminar (Galli-Milic, Forstall et al.); see BENCHMARK_METHODOLOGY.md",
        "language": "Latin to Latin",
        "csv_columns": ["source_ref", "target_ref", "target_work", "auth", "auth_count", "note"],
    },
    {
        "json_file": "apollonius_homer_gold.json",
        "output_stem": "apollonius_homer_gold",
        "title": "Apollonius Argonautica 3 vs Homer (Iliad and Odyssey)",
        "pair_count": 448,
        "gold_criterion": "All entries from Hunter 1989 commentary (types 1-5; 121 are type 4+5)",
        "parent_dataset": "Hunter (1989) commentary on Argonautica Book III",
        "commentators": "Hunter",
        "reference": "Hunter (1989) Apollonius of Rhodes: Argonautica Book III; see BENCHMARK_METHODOLOGY.md",
        "language": "Greek to Greek",
        "csv_columns": [
            "source_ref", "source_work", "source_file", "source_book", "source_line",
            "source_text", "target_ref", "target_work", "target_file", "target_book",
            "target_line", "target_text", "type", "authority", "auth_note"
        ],
    },
    {
        "json_file": "knauer_aeneid1_iliad.json",
        "output_stem": "knauer_aeneid1_iliad_gold",
        "title": "Vergil Aeneid 1 vs Homer Iliad (cross-lingual)",
        "pair_count": 412,
        "gold_criterion": "All Knauer 1964 catalog entries for Aeneid Book 1",
        "parent_dataset": "Knauer (1964) Die Aeneis und Homer, full Aeneid-Iliad catalog",
        "commentators": "Knauer",
        "reference": "Knauer (1964) Die Aeneis und Homer; see BENCHMARK_METHODOLOGY.md",
        "language": "Greek to Latin (cross-lingual)",
        "csv_columns": [
            "source_ref", "target_ref", "source_work", "target_work",
            "source_language", "target_language", "source_text", "target_text", "authority"
        ],
    },
    {
        "json_file": "loci_similes_gold.json",
        "output_stem": "loci_similes_gold",
        "title": "Jerome and Lactantius vs Classical Latin Authors",
        "pair_count": 421,
        "gold_criterion": "Type 4 (strong parallel) from Schelb et al. 2026 loci similes dataset",
        "parent_dataset": "Schelb et al. 2026 loci similes dataset (HuggingFace: Heidelberg-NLP/loci-similes)",
        "commentators": "Schelb, Betz, Dinkova-Bruun, et al.",
        "reference": "Schelb et al. (2026); see BENCHMARK_METHODOLOGY.md",
        "language": "Latin to Latin",
        "csv_columns": [
            "source_ref", "target_ref", "source_work", "target_work",
            "ls_id", "ls_query_citation", "ls_corpus_citation", "type"
        ],
    },
]


def write_csv_with_header(data, benchmark, output_path):
    """Write a CSV file with a metadata comment header."""
    meta = benchmark
    columns = meta["csv_columns"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        # Write metadata comment header
        f.write(f"# Tesserae V6 Gold Standard: {meta['title']}\n")
        f.write(f"# {meta['pair_count']} parallel passages\n")
        f.write(f"# Gold criterion: {meta['gold_criterion']}\n")
        f.write(f"# Language pair: {meta['language']}\n")
        f.write(f"# Parent dataset: {meta['parent_dataset']}\n")
        f.write(f"# Commentators: {meta['commentators']}\n")
        f.write(f"# Reference: {meta['reference']}\n")
        f.write(f"# Source JSON: evaluation/benchmarks/{meta['json_file']}\n")
        f.write(f"# Generated by: scripts/export_gold_benchmarks.py\n")
        f.write(f"# URL: https://tesserae.caset.buffalo.edu\n")
        f.write("#\n")

        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in data:
            writer.writerow(row)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for bm in BENCHMARKS:
        json_src = os.path.join(BENCHMARKS_DIR, bm["json_file"])
        if not os.path.exists(json_src):
            print(f"WARNING: {json_src} not found, skipping")
            continue

        with open(json_src, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Verify pair count
        actual_count = len(data)
        if actual_count != bm["pair_count"]:
            print(f"NOTE: {bm['json_file']} has {actual_count} pairs (expected {bm['pair_count']})")

        stem = bm["output_stem"]

        # Copy JSON to output directory
        json_dst = os.path.join(OUTPUT_DIR, f"{stem}.json")
        shutil.copy2(json_src, json_dst)
        print(f"  JSON: {json_dst}")

        # Write CSV with metadata header
        csv_dst = os.path.join(OUTPUT_DIR, f"{stem}.csv")
        write_csv_with_header(data, bm, csv_dst)
        print(f"  CSV:  {csv_dst} ({actual_count} rows)")

    print(f"\nDone. {len(BENCHMARKS)} benchmarks exported to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
