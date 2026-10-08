#!/usr/bin/env python3
"""Stage 3b-1 follow-up: build ONE shard of a language's documents lemma
cache. Lemma caches are per `.tess` file, so a language's bucket files can
be split across several of these, each run as its own `tess-job` scope,
to use the machine's many idle cores instead of one process working
through every bucket file in sequence.

Deterministic split: every `.tess` file under `--texts-root/--language`,
sorted by filename, assigned to shard `i` when `i % --num-shards ==
--shard-index`. Sorting by filename (not by size) is simple and stable
across repeated runs; `--num-shards`/`--shard-index` are the only inputs
that decide the split, so two runs with the same arguments always touch
the same files.

Reuses `backend.lemma_cache.rebuild_lemma_cache`'s new `file_filter`/
`fast_greek` parameters unchanged (added specifically for this), via the
same TEXTS_DIR/CACHE_DIR monkeypatch `build_documents_index.py` already
uses. Prints one progress line per file (filename, line count, elapsed)
to stdout so a wrapping `tess-job` log can be read for live throughput,
the same way `scripts/build_inverted_index.py`'s own verbose build does.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

import backend.lemma_cache as lemma_cache_mod  # noqa: E402
from backend.text_processor import TextProcessor  # noqa: E402


def shard_files(lang_dir: str, num_shards: int, shard_index: int) -> list[str]:
    """Greedy balance by LINE COUNT, not file count: the documentary
    bucket files are heavily skewed (the Latin corpus's largest bucket,
    `edr__roma__1_ad.tess`, alone holds 38,742 of 411,466 total Latin
    lines), so a plain `index % num_shards` split (by file count) can
    land most of the real work on one shard while the others finish
    almost immediately. Sort files descending by their own line count,
    then assign each file to whichever shard currently holds the fewest
    lines so far (longest-processing-time-first bin packing). This is
    deterministic given the same directory contents and `num_shards`
    (ties broken by filename, so repeated calls agree)."""
    all_files = sorted(f for f in os.listdir(lang_dir) if f.endswith(".tess"))
    sized = sorted(
        ((count_lines(os.path.join(lang_dir, f)), f) for f in all_files),
        key=lambda t: (-t[0], t[1]),
    )
    shard_lines = [0] * num_shards
    shard_members: list[list[str]] = [[] for _ in range(num_shards)]
    for lines, f in sized:
        target = min(range(num_shards), key=lambda i: shard_lines[i])
        shard_lines[target] += lines
        shard_members[target].append(f)
    return shard_members[shard_index]


def count_lines(path: str) -> int:
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--language", required=True, choices=["la", "grc"])
    ap.add_argument("--texts-root", required=True)
    ap.add_argument("--cache-root", required=True)
    ap.add_argument("--num-shards", type=int, required=True)
    ap.add_argument("--shard-index", type=int, required=True)
    ap.add_argument("--fast-greek", action="store_true",
                     help="table-only lemmatization for Greek (ignored for Latin)")
    ap.add_argument("--summary-out", default=None)
    args = ap.parse_args(argv)

    lang_dir = os.path.join(args.texts_root, args.language)
    files = shard_files(lang_dir, args.num_shards, args.shard_index)
    file_lines = {f: count_lines(os.path.join(lang_dir, f)) for f in files}
    total_lines = sum(file_lines.values())

    orig = (lemma_cache_mod.TEXTS_DIR, lemma_cache_mod.CACHE_DIR)
    lemma_cache_mod.TEXTS_DIR = args.texts_root
    lemma_cache_mod.CACHE_DIR = args.cache_root
    text_processor = TextProcessor()

    t0 = time.time()
    lines_done = 0

    def progress(processed, total, filename):
        nonlocal lines_done
        lines_done += file_lines.get(filename, 0)
        elapsed = time.time() - t0
        rate = lines_done / elapsed if elapsed > 0 else 0.0
        print(f"shard {args.shard_index}/{args.num_shards} [{processed}/{total}] "
              f"{filename} — {file_lines.get(filename, 0)} lines | "
              f"shard total: {lines_done}/{total_lines} lines, {elapsed:.0f}s "
              f"({rate:.1f} lines/s)", flush=True)

    try:
        # build_phrase_units=False: measured directly against this
        # corpus's own largest bucket file (edr__roma__1_ad.tess, a
        # 706-line run with no sentence-ending punctuation at all) at
        # 5.24 GB peak RSS for phrase-mode alone on that one file, against
        # 1.45 GB for line mode alone. Nothing in this stage reads a
        # documents phrase-mode cache entry; see backend/lemma_cache.py's
        # own docstring for the full measurement.
        result = lemma_cache_mod.rebuild_lemma_cache(
            args.language, text_processor, progress_callback=progress,
            file_filter=files, fast_greek=args.fast_greek,
            build_phrase_units=False)
    finally:
        lemma_cache_mod.TEXTS_DIR, lemma_cache_mod.CACHE_DIR = orig

    elapsed = time.time() - t0
    summary = {
        "shard_index": args.shard_index, "num_shards": args.num_shards,
        "language": args.language, "files_in_shard": len(files),
        "lines_in_shard": total_lines, "elapsed_s": round(elapsed, 1),
        "lines_per_s": round(total_lines / elapsed, 2) if elapsed > 0 else None,
        "result": result,
    }
    out = json.dumps(summary, indent=2, ensure_ascii=False)
    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as f:
            f.write(out)
    print(out, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
