"""
build_reuse_table.py

Corpus-wide table of verbatim and near-verbatim line reuse (alNaql-style),
production port of the prototype at research/reuse_table/ (build_reuse_index.py
+ find_reuse_pairs.py; see research/reuse_table/REPORT_2026-09-18.md for the
full design history, including why the pair filter uses a containment rule
rather than a raw shared-count override).

What it does, in one pass:
  1. Determines the live corpus for a language from texts/<lang>/*.tess (the
     source of truth for what is currently shipped -- NOT cache/lemmas/<lang>/,
     which can carry stale entries for texts retired from texts/ but not yet
     cleaned out of the cache. A retired file is simply absent from texts/,
     so listing texts/ is what "skip retired files" means in practice).
  2. Applies the part-file skip rule: when both a base file (author.work.tess)
     and its author.work.part.N.tess splits exist in texts/, the base file's
     cache already contains every line the parts do, so the .part. files are
     dropped (same rule as backend/bigram_frequency.py).
  3. For each surviving base file, reads surface tokens from its lemma cache
     (already normalized: lowercase, punctuation stripped, v->u, j->i for
     Latin -- see backend/text_processor.py tokenize_latin), resolved via
     backend.lemma_cache.get_cached_units -- the SAME resolution production
     uses (scripts/batch_lemma_cache.py, backend/text_service.py,
     backend/app.py all call it), not a plain <text_id>.json guess. The
     current cache filename is content-hash-free and ASCII-safe:
     <ascii_hint>-<md5(text_id including .tess)>.json (get_cache_path); an
     older plain <text_id>.json name is checked as a fallback
     (_legacy_cache_path) for caches predating that scheme. Either way the
     cache is only used if its stored file_hash (an MD5 of the .tess file's
     CONTENT) matches the live file's current hash -- a stale cache is
     treated as missing, not silently served. A base file with no valid
     cache under either name is skipped and counted (a recall gap to close
     by rebuilding that cache, not a design choice).
  4. Builds an n-gram inverted index (contiguous 3-grams plus one-gap skip-
     3-grams per line), hashes each n-gram to a signed 64-bit int, and drops
     any n-gram whose posting list exceeds --max-df lines corpus-wide (the
     banality cutoff). This step streams into a temporary SQLite DB and does
     the banality count with SQL GROUP BY / HAVING rather than an in-memory
     Python dict -- the original prototype attempt OOM'd under a 12G cap on
     the full corpus with the dict approach; the SQL version does not.
  5. Finds candidate cross-work line pairs from the filtered postings,
     scores them by Jaccard and containment, keeps a pair if
       shared >= --min-shared and jaccard >= --min-jaccard
       OR shared >= --min-shared-override and containment >= --min-containment
     where containment = shared / min(ngrams_a, ngrams_b) (the fraction of
     the SHORTER line's surviving n-grams the match accounts for -- this
     replaced a raw shared-count-only override that let long, unrelated
     prose paragraphs through on a handful of coincidental function-word
     n-grams; see REPORT_2026-09-18.md "Follow-up: the prose length fix").
  6. Chains adjacent line matches (seq s/t and s+1/t+1 in the same work
     pair) into spans and writes everything to
     cache/reuse_pairs/<lang>.db:
       pairs(work_a, line_a_ref, work_b, line_b_ref, shared, jaccard, span_len)
       line_counts(work, line_ref, n_works)
       meta(key, value) -- built_at, corpus_version, corpus_file_count, and
       the run's parameters/stats.

Usage:
  python3 scripts/reuse/build_reuse_table.py --language la
  python3 scripts/reuse/build_reuse_table.py --language la --max-df 200

Run under a memory cap in production, e.g.:
  systemd-run --user --scope -p MemoryMax=12G \\
      venv/bin/python3 scripts/reuse/build_reuse_table.py --language la

Rebuild after any corpus change to that language (new imports, retirements,
lemma-cache rebuilds) -- this table is a snapshot, not live-computed.
"""
import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEXTS_DIR = os.path.join(BASE_DIR, 'texts')
CACHE_DIR = os.path.join(BASE_DIR, 'cache', 'lemmas')
OUT_DIR = os.path.join(BASE_DIR, 'cache', 'reuse_pairs')
INDEX_DIR = os.path.join(BASE_DIR, 'data', 'inverted_index')

# Reuse production's own cache-file resolution (hashed name first, legacy
# plain name as fallback, file_hash-validated either way) rather than
# guessing a filename -- see the module docstring's item 3. This is the
# same function scripts/batch_lemma_cache.py, backend/text_service.py and
# backend/app.py all call.
sys.path.insert(0, BASE_DIR)
from backend.lemma_cache import get_cached_units  # noqa: E402


def hash_ngram(tokens):
    """Hash a tuple of tokens to a signed 64-bit int (SQLite INTEGER is signed
    64-bit, so the blake2b digest's top bit is kept as sign, not truncated)."""
    joined = '\x1f'.join(tokens).encode('utf-8')
    digest = hashlib.blake2b(joined, digest_size=8).digest()
    return int.from_bytes(digest, 'big', signed=True)


def gen_ngrams(tokens):
    """Yield contiguous 3-grams and one-gap skip-3-grams for a token list."""
    n = len(tokens)
    for i in range(n - 2):
        yield (tokens[i], tokens[i + 1], tokens[i + 2])
    for i in range(n - 3):
        yield (tokens[i], tokens[i + 1], tokens[i + 3])
        yield (tokens[i], tokens[i + 2], tokens[i + 3])


def get_corpus_version(language):
    """Read meta.corpus_version from data/inverted_index/<lang>_index.db, the
    same stamp backend.inverted_index.get_corpus_version serves. Falls back to
    the index DB's file mtime when there is no meta table/row (some plugin-
    language builds predate the stamping), and to None if there is no index
    DB at all."""
    db_path = os.path.join(INDEX_DIR, f'{language}_index.db')
    if not os.path.exists(db_path):
        return None
    v = None
    try:
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT value FROM meta WHERE key='corpus_version'").fetchone()
            if row is not None:
                v = row[0]
        except sqlite3.OperationalError:
            v = None
        finally:
            conn.close()
    except Exception:
        v = None
    if v is None:
        try:
            from datetime import date
            v = date.fromtimestamp(os.path.getmtime(db_path)).isoformat()
        except Exception:
            v = None
    return v


def discover_corpus(language):
    """Return (kept, skipped_parts, missing_cache) where kept is
    {tess_basename: cache_dict} for the live, base-file, hash-valid-cached
    corpus -- cache_dict is the already-loaded, already file_hash-validated
    JSON payload from backend.lemma_cache.get_cached_units.

    Source of truth for "live" is texts/<lang>/*.tess, not cache/lemmas/, so
    a text retired from texts/ (simply absent there now) is never included
    even if a stale cache file for it still exists."""
    texts_dir = os.path.join(TEXTS_DIR, language)
    cache_dir = os.path.join(CACHE_DIR, language)
    if not os.path.isdir(texts_dir):
        raise SystemExit(f"No texts/{language}/ directory found at {texts_dir}")
    if not os.path.isdir(cache_dir):
        raise SystemExit(f"No cache/lemmas/{language}/ directory found at {cache_dir}")

    all_tess = [f for f in os.listdir(texts_dir) if f.endswith('.tess')]

    # part-file skip: base file present in texts/ => drop its .part.N siblings.
    full_versions = set()
    for fname in all_tess:
        if '.part.' not in fname:
            full_versions.add(fname[:-len('.tess')])

    surviving = []
    skipped_parts = []
    for fname in all_tess:
        if '.part.' in fname:
            base = fname.split('.part.')[0]
            if base in full_versions:
                skipped_parts.append(fname)
                continue
        surviving.append(fname)

    kept = {}
    missing_cache = []
    for fname in surviving:
        cached = get_cached_units(fname, language)
        if cached is not None:
            kept[fname] = cached
        else:
            missing_cache.append(fname)

    return kept, skipped_parts, missing_cache


def build_index(cache_data, index_db_path, max_df):
    """Stage 1: stream per-line n-grams from cache_data (already-loaded,
    already-validated {tess_basename: cache_dict}, from discover_corpus)
    into a temporary SQLite index DB (lines, postings after banality
    filtering). Returns a stats dict. Mirrors
    research/reuse_table/build_reuse_index.py."""
    t0 = time.time()
    if os.path.exists(index_db_path):
        os.remove(index_db_path)
    conn = sqlite3.connect(index_db_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store = FILE")
    conn.execute("""CREATE TABLE lines (
        line_id INTEGER PRIMARY KEY,
        work TEXT, line_ref TEXT, token_count INTEGER, seq_in_work INTEGER
    )""")
    conn.execute("CREATE TABLE postings_raw (ngram_hash INTEGER, line_id INTEGER)")

    line_rows = []
    posting_batch = []
    BATCH = 500000
    n_gram_instances = 0

    def flush_postings():
        nonlocal posting_batch
        if posting_batch:
            conn.executemany("INSERT INTO postings_raw VALUES (?,?)", posting_batch)
            posting_batch = []

    line_id = 0
    n_lines_seen = 0
    n_lines_too_short = 0
    works_indexed = 0

    for tess_basename, data in cache_data.items():
        work_id = data.get('text_id', tess_basename)
        if work_id.endswith('.tess'):
            work_id = work_id[:-len('.tess')]
        units = data.get('units_line', [])
        if not units:
            continue
        works_indexed += 1
        for seq, unit in enumerate(units):
            tokens = unit.get('tokens') or []
            ref = unit.get('ref', '')
            n_lines_seen += 1
            if len(tokens) < 3:
                n_lines_too_short += 1
                line_rows.append((line_id, work_id, ref, len(tokens), seq))
                line_id += 1
                continue
            seen_this_line = set()
            for gram in gen_ngrams(tokens):
                h = hash_ngram(gram)
                if h in seen_this_line:
                    continue
                seen_this_line.add(h)
                n_gram_instances += 1
                posting_batch.append((h, line_id))
                if len(posting_batch) >= BATCH:
                    flush_postings()
            line_rows.append((line_id, work_id, ref, len(tokens), seq))
            line_id += 1
            if len(line_rows) >= BATCH:
                conn.executemany("INSERT INTO lines VALUES (?,?,?,?,?)", line_rows)
                line_rows = []

    flush_postings()
    if line_rows:
        conn.executemany("INSERT INTO lines VALUES (?,?,?,?,?)", line_rows)
    conn.commit()

    print(f"[build_reuse_table] index: {n_lines_seen} lines read from {works_indexed} works "
          f"({n_lines_too_short} lines under 3 tokens, kept with no n-grams), "
          f"{n_gram_instances} n-gram instances, elapsed {time.time()-t0:.1f}s")

    print("[build_reuse_table] index: computing n-gram document frequencies (SQL GROUP BY)...")
    conn.execute("CREATE INDEX idx_raw_ngram ON postings_raw(ngram_hash)")
    conn.commit()

    distinct_ngrams_total = conn.execute(
        "SELECT COUNT(*) FROM (SELECT ngram_hash FROM postings_raw GROUP BY ngram_hash)"
    ).fetchone()[0]

    n_ngrams_dropped_banal = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT ngram_hash FROM postings_raw GROUP BY ngram_hash HAVING COUNT(*) > ?
        )
    """, (max_df,)).fetchone()[0]
    n_ngrams_kept = distinct_ngrams_total - n_ngrams_dropped_banal

    print("[build_reuse_table] index: materializing filtered postings table...")
    conn.execute("""CREATE TABLE postings AS
        SELECT ngram_hash, line_id FROM postings_raw
        WHERE ngram_hash IN (
            SELECT ngram_hash FROM postings_raw GROUP BY ngram_hash HAVING COUNT(*) <= ?
        )
    """, (max_df,))
    conn.commit()
    n_postings_written = conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0]

    conn.execute("DROP TABLE postings_raw")
    conn.commit()
    conn.execute("VACUUM")

    print("[build_reuse_table] index: creating indexes...")
    conn.execute("CREATE INDEX idx_postings_ngram ON postings(ngram_hash)")
    conn.execute("CREATE INDEX idx_postings_line ON postings(line_id)")
    conn.execute("CREATE INDEX idx_lines_work ON lines(work)")
    conn.commit()
    conn.close()

    elapsed = time.time() - t0
    return {
        'works_indexed': works_indexed,
        'lines_indexed': n_lines_seen,
        'lines_under_3_tokens': n_lines_too_short,
        'distinct_ngrams_total': distinct_ngrams_total,
        'ngrams_kept': n_ngrams_kept,
        'ngrams_dropped_banal_over_max_df': n_ngrams_dropped_banal,
        'postings_written': n_postings_written,
        'index_elapsed_seconds': elapsed,
    }


def find_pairs(index_db_path, min_shared, min_jaccard, min_shared_override, min_containment):
    """Stage 2: stream postings ordered by ngram_hash, accumulate cross-work
    shared-ngram counts, score by jaccard/containment, chain adjacent kept
    pairs into spans. Returns (pair_info, line_to_other_works, stats).
    Mirrors research/reuse_table/find_reuse_pairs.py."""
    t0 = time.time()
    conn = sqlite3.connect(index_db_path)
    cur = conn.cursor()

    line_meta = {}
    for line_id, work, ref, token_count, seq in cur.execute(
            "SELECT line_id, work, line_ref, token_count, seq_in_work FROM lines"):
        line_meta[line_id] = (work, ref, seq)
    n_lines = len(line_meta)
    print(f"[build_reuse_table] pairs: {n_lines} lines loaded, elapsed {time.time()-t0:.1f}s")

    line_ngram_count = defaultdict(int)
    overlap = defaultdict(int)
    current_hash = None
    current_lines = []
    n_ngrams_processed = 0
    n_pair_increments = 0

    def flush_group(lines_in_group):
        nonlocal n_pair_increments
        L = len(lines_in_group)
        for lid in lines_in_group:
            line_ngram_count[lid] += 1
        if L < 2:
            return
        for i in range(L):
            wi = line_meta[lines_in_group[i]][0]
            for j in range(i + 1, L):
                a, b = lines_in_group[i], lines_in_group[j]
                if line_meta[b][0] == wi:
                    continue
                if a > b:
                    a, b = b, a
                overlap[(a, b)] += 1
                n_pair_increments += 1

    for ngram_hash, line_id in cur.execute("SELECT ngram_hash, line_id FROM postings ORDER BY ngram_hash"):
        if ngram_hash != current_hash:
            if current_hash is not None:
                flush_group(current_lines)
                n_ngrams_processed += 1
            current_hash = ngram_hash
            current_lines = []
        current_lines.append(line_id)
    if current_lines:
        flush_group(current_lines)
        n_ngrams_processed += 1

    print(f"[build_reuse_table] pairs: {n_ngrams_processed} n-grams scanned, "
          f"{len(overlap)} candidate cross-work line pairs, "
          f"{n_pair_increments} pair-increments, elapsed {time.time()-t0:.1f}s")

    kept = []
    n_excluded_by_raw_override = 0
    for (a, b), shared in overlap.items():
        na = line_ngram_count[a]
        nb = line_ngram_count[b]
        union = na + nb - shared
        jaccard = shared / union if union > 0 else 0.0
        min_ngrams = min(na, nb)
        containment = shared / min_ngrams if min_ngrams > 0 else 0.0
        meets_jaccard = shared >= min_shared and jaccard >= min_jaccard
        meets_containment_override = shared >= min_shared_override and containment >= min_containment
        if shared >= min_shared_override and not meets_jaccard and not meets_containment_override:
            n_excluded_by_raw_override += 1
        if meets_jaccard or meets_containment_override:
            kept.append((a, b, shared, jaccard))

    print(f"[build_reuse_table] pairs: {len(kept)} pairs kept after threshold "
          f"({n_excluded_by_raw_override} excluded by the containment gate: "
          f"shared>={min_shared_override} but containment<{min_containment} and jaccard<{min_jaccard}), "
          f"elapsed {time.time()-t0:.1f}s")

    pair_by_seq = {}
    pair_info = []
    for a, b, shared, jaccard in kept:
        wa, ra, sa = line_meta[a]
        wb, rb, sb = line_meta[b]
        if wa > wb:
            wa, ra, sa, wb, rb, sb = wb, rb, sb, wa, ra, sa
        idx = len(pair_info)
        pair_info.append([wa, ra, sa, wb, rb, sb, shared, jaccard, 1])
        pair_by_seq[(wa, wb, sa, sb)] = idx

    visited = set()
    for idx, (wa, ra, sa, wb, rb, sb, shared, jaccard, _) in enumerate(pair_info):
        if idx in visited:
            continue
        chain = [idx]
        visited.add(idx)
        cs, ct = sa, sb
        while True:
            nxt = pair_by_seq.get((wa, wb, cs + 1, ct + 1))
            if nxt is None or nxt in visited:
                break
            chain.append(nxt)
            visited.add(nxt)
            cs, ct = cs + 1, ct + 1
        if len(chain) > 1:
            span_len = len(chain)
            for i in chain:
                pair_info[i][8] = span_len

    n_spans = sum(1 for p in pair_info if p[8] > 1)
    print(f"[build_reuse_table] pairs: chaining done: rows in a span > 1: {n_spans}, "
          f"elapsed {time.time()-t0:.1f}s")

    line_to_other_works = defaultdict(set)
    for wa, ra, sa, wb, rb, sb, shared, jaccard, span_len in pair_info:
        line_to_other_works[(wa, ra)].add(wb)
        line_to_other_works[(wb, rb)].add(wa)

    conn.close()
    elapsed = time.time() - t0
    stats = {
        'lines_loaded': n_lines,
        'ngrams_scanned': n_ngrams_processed,
        'candidate_cross_work_pairs': len(overlap),
        'pairs_kept': len(pair_info),
        'candidates_excluded_by_containment_gate': n_excluded_by_raw_override,
        'rows_in_spans_gt1': n_spans,
        'lines_with_at_least_one_other_work': len(line_to_other_works),
        'pairs_elapsed_seconds': elapsed,
    }
    return pair_info, line_to_other_works, stats


def write_output_db(out_db_path, pair_info, line_to_other_works, meta):
    if os.path.exists(out_db_path):
        os.remove(out_db_path)
    conn = sqlite3.connect(out_db_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("""CREATE TABLE pairs (
        work_a TEXT, line_a_ref TEXT, work_b TEXT, line_b_ref TEXT,
        shared INTEGER, jaccard REAL, span_len INTEGER
    )""")
    conn.executemany(
        "INSERT INTO pairs VALUES (?,?,?,?,?,?,?)",
        [(wa, ra, wb, rb, shared, jaccard, span_len)
         for wa, ra, sa, wb, rb, sb, shared, jaccard, span_len in pair_info]
    )

    conn.execute("CREATE TABLE line_counts (work TEXT, line_ref TEXT, n_works INTEGER)")
    conn.executemany(
        "INSERT INTO line_counts VALUES (?,?,?)",
        [(work, ref, len(others)) for (work, ref), others in line_to_other_works.items()]
    )

    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany(
        "INSERT INTO meta VALUES (?,?)",
        [(k, '' if v is None else str(v)) for k, v in meta.items()]
    )

    conn.execute("CREATE INDEX idx_pairs_work_a ON pairs(work_a)")
    conn.execute("CREATE INDEX idx_pairs_work_b ON pairs(work_b)")
    conn.execute("CREATE INDEX idx_line_counts_work ON line_counts(work, line_ref)")
    conn.commit()
    conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--language', default='la')
    ap.add_argument('--max-df', type=int, default=200,
                     help='drop n-grams occurring in more than this many lines corpus-wide')
    ap.add_argument('--min-shared', type=int, default=2)
    ap.add_argument('--min-jaccard', type=float, default=0.15)
    ap.add_argument('--min-shared-override', type=int, default=4,
                     help='keep if shared >= this AND containment >= --min-containment, regardless of jaccard')
    ap.add_argument('--min-containment', type=float, default=0.5,
                     help='containment = shared / min(ngrams_a, ngrams_b)')
    ap.add_argument('--out-db', default=None)
    ap.add_argument('--stats-out', default=None)
    ap.add_argument('--keep-index-db', action='store_true',
                     help='keep the intermediate n-gram index db (for debugging) instead of deleting it')
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    out_db = args.out_db or os.path.join(OUT_DIR, f'{args.language}.db')
    stats_out = args.stats_out or os.path.join(OUT_DIR, f'{args.language}_stats.json')

    t_start = time.time()

    cache_data, skipped_parts, missing_cache = discover_corpus(args.language)
    print(f"[build_reuse_table] {len(cache_data)} works to index "
          f"({len(skipped_parts)} .part. files skipped in favor of their base file, "
          f"{len(missing_cache)} base files skipped for missing/invalid lemma cache)")
    if missing_cache:
        print(f"[build_reuse_table] WARN: {len(missing_cache)} live .tess files have no "
              f"file_hash-valid lemma cache under either the current hashed name or the "
              f"legacy plain name, and are excluded from this run (rebuild their cache to "
              f"close the gap): "
              + ', '.join(sorted(missing_cache)[:10]) + (' ...' if len(missing_cache) > 10 else ''))

    tmp_dir = tempfile.mkdtemp(prefix=f'reuse_table_{args.language}_')
    index_db_path = os.path.join(tmp_dir, f'{args.language}_index.db')
    try:
        index_stats = build_index(cache_data, index_db_path, args.max_df)
        pair_info, line_to_other_works, pair_stats = find_pairs(
            index_db_path, args.min_shared, args.min_jaccard,
            args.min_shared_override, args.min_containment)

        corpus_version = get_corpus_version(args.language)
        built_at = datetime.now(timezone.utc).isoformat()
        meta = {
            'built_at': built_at,
            'corpus_version': corpus_version,
            'corpus_file_count': len(cache_data),
            'language': args.language,
            'max_df': args.max_df,
            'min_shared': args.min_shared,
            'min_jaccard': args.min_jaccard,
            'min_shared_override': args.min_shared_override,
            'min_containment': args.min_containment,
            'works_indexed': index_stats['works_indexed'],
            'lines_indexed': index_stats['lines_indexed'],
            'pairs_kept': pair_stats['pairs_kept'],
            'lines_with_at_least_one_other_work': pair_stats['lines_with_at_least_one_other_work'],
            'skipped_part_files': len(skipped_parts),
            'skipped_missing_cache': len(missing_cache),
        }
        write_output_db(out_db, pair_info, line_to_other_works, meta)
    finally:
        if args.keep_index_db:
            kept_path = os.path.join(OUT_DIR, f'{args.language}_index.db')
            shutil.move(index_db_path, kept_path)
            print(f"[build_reuse_table] kept intermediate index db at {kept_path}")
        shutil.rmtree(tmp_dir, ignore_errors=True)

    elapsed = time.time() - t_start
    stats = {**index_stats, **pair_stats, 'total_elapsed_seconds': elapsed, 'out_db': out_db, **{
        'skipped_part_files': len(skipped_parts),
        'skipped_missing_cache': len(missing_cache),
        'corpus_version': corpus_version,
        'built_at': built_at,
    }}
    with open(stats_out, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"[build_reuse_table] done in {elapsed:.1f}s. DB: {out_db}")
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
