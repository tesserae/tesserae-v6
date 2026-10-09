"""
build_documents_reuse_table.py

Cross-collection reuse table: for each LITERARY line, which DOCUMENT units
(inscriptions, papyri) quote or near-quote it. Same word-triple containment
logic and strict/possible tiers as scripts/reuse/build_reuse_table.py (the
literary-vs-literary table), applied to literary-vs-document pairs only, and
written to a SEPARATE database -- cache/reuse_pairs/<lang>_documents.db -- so
the literary-only table (cache/reuse_pairs/<lang>.db) is untouched by this
script and unaffected if this one is ever rebuilt or removed.

Why a separate script rather than a flag on build_reuse_table.py: the two
corpora are read from different places (the literary lemma cache vs. the
documents index's own `lines` table, see below) and the "banality" rule is
different in kind -- the literary table calls an n-gram banal by corpus-wide
LINE frequency; here a shared word is called a documentary FORMULA by
corpus-wide DOCUMENT frequency (how many distinct inscriptions/papyri use
it), which the literary script's commonplace-lemma-ratio test has no
equivalent for. Keeping them separate scripts avoids threading a second,
unrelated exclusion rule through code that already carries a lot of
commentary about the first one.

INPUTS
  Literary side: the SAME lemma cache files scripts/reuse/build_reuse_table.py
  reads (cache/lemmas/<lang>/*.json via backend.lemma_cache.get_cached_units),
  via that script's own discover_corpus() -- imported, not re-implemented, so
  "which literary lines count" never drifts between the two tables. Default
  texts/cache roots point at this script's own repo root; --literary-texts-
  root/--literary-cache-root override them (a worktree that does not carry the
  large texts/cache/lemmas trees can point at another checkout's absolute
  paths instead of copying gigabytes of data into itself).

  Document side: data/inverted_index/<lang>_documents_index.db's own `lines`
  table (text_id, ref, content, lemmas, tokens -- built by
  scripts/documents/build_documents_index.py, the same index backend/app.py's
  documents-collection search already reads). `tokens` there is already
  normalized the same way the literary cache's `tokens` are (lowercase,
  punctuation stripped, v->u/j->i for Latin -- backend/text_processor.py's
  tokenize_latin, since both are produced by the same tokenizer); `content` is
  the original-case text, used only for display and for locating a shared
  word's character span to bold (see backend/reuse_table.py's _bold_spans,
  reused as-is by backend/reuse_documents.py).

  Restored-word flags: read directly from each document bucket's own sidecar
  (<bucket>.restored_words.jsonl, written by scripts/documents/
  write_document_tess.py) under --documents-sidecar-root, which defaults to
  data/documents/restored/ -- the SAME layout and filenames
  backend/documents.py's own _sidecar_root()/restored_indices() read on
  production -- rather than calling restored_indices() itself, since this
  script runs offline and wants every bucket's sidecar loaded once, not one
  lazy per-bucket cache entry per request. A dev checkout whose
  data/documents/restored/ is not populated (the indexes and metadata.db
  were copied for development, the sidecars were not) points
  --documents-sidecar-root at wherever its raw stage-3 tree is instead
  (e.g. ~/tesserae-docs/stage3/texts_documents, which write_document_tess.py
  wrote the identical files into in the first place) -- see this script's
  own --help and the production install steps in docs/DATA_OPERATIONS.md.

FORMULA EXCLUSION (replaces the literary script's commonplace-lemma test)
  A shared n-gram is a FORMULA n-gram if every one of its three words is
  either (a) on data/documents/formula_words_<lang>.txt (hand-reviewed
  funerary/honorific/legal/dating formula vocabulary, stage 2 review
  2026-10-08), or (b) a lemma shared by more than DOCUMENT_FORMULA_MAX_DOCS
  individual documents in this language's OWN documents index (not the
  160-bucket-file granularity backend/app.py's lemma_doc_freq table already
  carries -- see below).

  DOCUMENT_FORMULA_MAX_DOCS = 100, reusing backend/app.py's own
  DOCUMENTS_FORMULA_DEFAULT_N measurement verbatim rather than re-deriving a
  threshold: that constant was fitted against the real documents corpus
  (comment there: "arma virumque cano", 8 documents, a genuine parallel, vs.
  the smallest formula at 3,535 -- three orders of magnitude of headroom on
  both sides) for exactly this question, "is a shared word distinctive
  enough, by how many documents actually use it, to be evidence of reuse
  rather than boilerplate." The existing lemma_doc_freq table in
  <lang>_documents_index.db cannot answer that directly: it counts document
  frequency across the 160 BUCKET FILES (one per region/period), not across
  the ~179K individual inscriptions/papyri doc_meta tracks, so a lemma's
  bucket-df of 13 (e.g. "armo") says nothing about how many actual documents
  use it. This script computes its own per-language DOCUMENT-granular lemma
  count once, the same way backend/app.py's _documents_formula_count does at
  request time (group postings by lemma, map each hit's ref to its doc_id by
  splitting on the first space -- backend/documents.py's own doc_for
  convention -- and count distinct doc_ids), via one SQL pass over `postings`
  rather than one request-time query per lemma.

  A pair whose shared n-grams are ALL formula n-grams is dropped entirely
  (mirrors the literary script's drop_all_commonplace rule); the
  rare-single-ngram rule's one contributing n-gram is also checked, so a
  corpus-rare SHAPE built only from formula words still cannot pass on
  rarity alone (mirrors the literary script's commonplace_hashes gate on
  that same rule).

TIERS: identical thresholds to build_reuse_table.py's defaults (min_shared=2,
min_jaccard=0.15; min_shared_override=4, min_containment=0.5; rare_max_df=20,
rare_min_containment=0.06) -- `shared==1` rows are 'possible', everything
else kept is 'strict', exactly as backend/reuse_table.py's line()/marks()
already define the tier from `shared` alone for the literary table, so
backend/reuse_documents.py (the query layer for this table) can reuse that
same one-line rule.

OUTPUT cache/reuse_pairs/<lang>_documents.db:
    pairs(lit_work TEXT, lit_ref TEXT, lit_seq INTEGER,
          doc_id TEXT, doc_bucket TEXT, doc_ref TEXT, doc_seq INTEGER,
          shared INTEGER, jaccard REAL, span_len INTEGER, doc_restored INTEGER)
      doc_restored: 1 if EVERY document-side word contributing to the
      pair's shared n-grams is marked restored by that document's own
      sidecar, 0 if some or none are (see _pair_restored_flag) -- the
      Reuse tab's "match on restored text" / "match partly on restored
      text" distinction.
    meta(key, value)

Usage:
  python3 scripts/reuse/build_documents_reuse_table.py --language la

Run under a memory cap, same as the literary build:
  ~/bin/tess-job reuse-documents-la 12 \\
      venv/bin/python3 scripts/reuse/build_documents_reuse_table.py --language la
"""
import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.join(BASE_DIR, 'scripts', 'reuse'))

from backend.ngram_utils import gen_ngram_indices, gen_ngrams  # noqa: E402
import backend.lemma_cache as lemma_cache_mod  # noqa: E402
import build_reuse_table as lit  # noqa: E402  (the literary builder, reused)

OUT_DIR = os.path.join(BASE_DIR, 'cache', 'reuse_pairs')
DOCUMENTS_INDEX_DIR_DEFAULT = os.path.join(BASE_DIR, 'data', 'inverted_index')
FORMULA_WORDS_DIR_DEFAULT = os.path.join(BASE_DIR, 'data', 'documents')
# The SAME layout backend/documents.py's own _sidecar_root() reads on
# production (<root>/<language>/<bucket>.restored_words.jsonl) -- see this
# module's docstring. Override with --documents-sidecar-root for a
# checkout whose data/documents/restored/ is not populated.
DOCUMENTS_SIDECAR_ROOT_DEFAULT = os.path.join(BASE_DIR, 'data', 'documents', 'restored')

# See this module's docstring, "FORMULA EXCLUSION": the same constant
# backend/app.py's DOCUMENTS_FORMULA_DEFAULT_N already measures and uses for
# the documents-collection search's "hide stock formulas" control.
DOCUMENT_FORMULA_MAX_DOCS = 100


def _fold_simple(word):
    """Lowercase only -- the documents index's own tokens/lemmas are already
    v->u/j->i folded for Latin at index-build time (scripts/documents/
    build_documents_index.py reuses backend/text_processor.py's tokenizer),
    so this does not re-fold; it only guards against a formula-word-list
    entry typed in a different case than the index's lemma strings."""
    return (word or '').strip().lower()


def load_formula_words(language):
    path = os.path.join(FORMULA_WORDS_DIR_DEFAULT, f'formula_words_{language}.txt')
    words = set()
    if not os.path.exists(path):
        return words
    with open(path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            raw_line = raw_line.split('#', 1)[0].strip()
            if raw_line:
                words.add(_fold_simple(raw_line))
    return words


def document_lemma_doc_counts(index_db_path):
    """{lemma: n_distinct_documents} for this language's documents index,
    computed from `postings` (lemma, text_id, ref, positions) by mapping
    each ref to its owning doc_id the same way backend/documents.py's
    doc_for does (split on the first space) -- see this module's docstring.
    One SQL pass, not one query per lemma."""
    conn = sqlite3.connect(index_db_path)
    conn.execute("PRAGMA query_only = ON")
    counts = {}
    seen = defaultdict(set)
    for lemma, ref in conn.execute("SELECT lemma, ref FROM postings"):
        doc_id = ref.split(' ', 1)[0] if ref else ref
        s = seen[lemma]
        if len(s) < DOCUMENT_FORMULA_MAX_DOCS + 1:
            # Capped: once a lemma's distinct-doc count is already past the
            # threshold we only need to know it stays past it, not the exact
            # final count -- this keeps the per-lemma sets from growing
            # without bound for ultra-common words ("et", "sum") while every
            # lemma near the threshold is still counted exactly.
            s.add(doc_id)
    for lemma, s in seen.items():
        counts[lemma] = len(s)
    conn.close()
    return counts


def discover_documents(language, documents_index_dir):
    """{bucket_filename: {'lines': [...]}} for every document line in
    <lang>_documents_index.db, grouped by doc_id in rowid order so each
    document's own local line sequence (doc_seq, for span-chaining
    adjacent quoted lines the same way the literary table chains
    seq_in_work) can be assigned. Each line dict carries
    {ref, content, tokens, lemmas, doc_id, bucket, doc_seq}.

    Mirrors scripts/documents/build_documents_index.py's own doc_meta
    convention: a ref's doc_id is the text before its first space."""
    db_path = os.path.join(documents_index_dir, f'{language}_documents_index.db')
    if not os.path.exists(db_path):
        raise SystemExit(f"No documents index at {db_path} "
                          f"(build it with scripts/documents/build_documents_index.py, "
                          f"or pass --documents-index-dir)")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA query_only = ON")
    text_by_id = {row[0]: row[1] for row in conn.execute("SELECT text_id, filename FROM texts")}
    doc_seq = defaultdict(int)
    out = []
    for text_id, ref, content, lemmas_json, tokens_json in conn.execute(
            "SELECT text_id, ref, content, lemmas, tokens FROM lines ORDER BY text_id, rowid"):
        try:
            lemmas = json.loads(lemmas_json) if lemmas_json else []
        except Exception:
            lemmas = []
        try:
            tokens = json.loads(tokens_json) if tokens_json else []
        except Exception:
            tokens = []
        doc_id = ref.split(' ', 1)[0] if ref else ref
        seq = doc_seq[doc_id]
        doc_seq[doc_id] += 1
        out.append({
            'ref': ref, 'content': content or '', 'tokens': tokens, 'lemmas': lemmas,
            'doc_id': doc_id, 'bucket': text_by_id.get(text_id, ''), 'doc_seq': seq,
        })
    conn.close()
    return out, document_lemma_doc_counts(db_path)


def load_sidecar(sidecar_root, language, bucket):
    """{ref: set(restored token positions)} for one bucket file, or {} if
    the sidecar is absent -- display-only, never a reason to drop a pair."""
    bucket_stem = bucket[:-5] if bucket.endswith('.tess') else bucket
    path = os.path.join(sidecar_root, language, f'{bucket_stem}.restored_words.jsonl')
    table = {}
    if not os.path.exists(path):
        return table
    with open(path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                rec = json.loads(raw_line)
            except Exception:
                continue
            ref = rec.get('ref')
            if ref:
                table[ref] = set(rec.get('restored') or [])
    return table


def build_combined_index(lit_cache_data, doc_lines, index_db_path, max_df,
                          formula_words, doc_lemma_counts, language=None):
    """Index BOTH collections' lines into one temp SQLite db (lines,
    postings), banality-filtered corpus-wide exactly like
    build_reuse_table.py's build_index -- a trigram common across either
    collection is still banal for both. `lines.collection` is 'lit' or
    'doc' so find_cross_pairs only pairs opposite collections.

    Returns (stats, formula_hashes) -- formula_hashes is the set of n-gram
    hashes whose three words are ALL formula words (see this module's
    docstring, "FORMULA EXCLUSION"), computed in a second pass over both
    collections exactly as build_reuse_table.py's build_index computes
    commonplace_hashes."""
    t0 = time.time()
    if os.path.exists(index_db_path):
        os.remove(index_db_path)
    conn = sqlite3.connect(index_db_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store = FILE")
    conn.execute("""CREATE TABLE lines (
        line_id INTEGER PRIMARY KEY, collection TEXT,
        work TEXT, ref TEXT, seq INTEGER, token_count INTEGER
    )""")
    conn.execute("CREATE TABLE postings_raw (ngram_hash INTEGER, line_id INTEGER)")

    line_rows = []
    posting_batch = []
    BATCH = 500000

    def flush_postings():
        nonlocal posting_batch
        if posting_batch:
            conn.executemany("INSERT INTO postings_raw VALUES (?,?)", posting_batch)
            posting_batch = []

    def flush_lines():
        nonlocal line_rows
        if line_rows:
            conn.executemany("INSERT INTO lines VALUES (?,?,?,?,?,?)", line_rows)
            line_rows = []

    line_id = 0
    n_lit_lines = n_doc_lines = n_too_short = 0
    formula_pass_items = []   # (tokens, lemmas) for every line, both collections

    for tess_basename, data in lit_cache_data.items():
        work_id = data.get('text_id', tess_basename)
        if work_id.endswith('.tess'):
            work_id = work_id[:-len('.tess')]
        for seq, unit in enumerate(data.get('units_line', [])):
            tokens = unit.get('tokens') or []
            lemmas = lit._line_lemmas(unit)
            ref = unit.get('ref', '')
            n_lit_lines += 1
            formula_pass_items.append((tokens, lemmas))
            if len(tokens) < 3:
                n_too_short += 1
                line_rows.append((line_id, 'lit', work_id, ref, seq, len(tokens)))
                line_id += 1
                continue
            seen_this_line = set()
            for gram in gen_ngrams(tokens):
                h = lit.hash_ngram(gram)
                if h in seen_this_line:
                    continue
                seen_this_line.add(h)
                posting_batch.append((h, line_id))
                if len(posting_batch) >= BATCH:
                    flush_postings()
            line_rows.append((line_id, 'lit', work_id, ref, seq, len(tokens)))
            line_id += 1
            if len(line_rows) >= BATCH:
                flush_lines()

    for unit in doc_lines:
        tokens = unit['tokens']
        lemmas = unit['lemmas'] if len(unit['lemmas']) == len(tokens) else tokens
        n_doc_lines += 1
        formula_pass_items.append((tokens, lemmas))
        if len(tokens) < 3:
            n_too_short += 1
            line_rows.append((line_id, 'doc', unit['doc_id'], unit['ref'], unit['doc_seq'], len(tokens)))
            line_id += 1
            continue
        seen_this_line = set()
        for gram in gen_ngrams(tokens):
            h = lit.hash_ngram(gram)
            if h in seen_this_line:
                continue
            seen_this_line.add(h)
            posting_batch.append((h, line_id))
            if len(posting_batch) >= BATCH:
                flush_postings()
        line_rows.append((line_id, 'doc', unit['doc_id'], unit['ref'], unit['doc_seq'], len(tokens)))
        line_id += 1
        if len(line_rows) >= BATCH:
            flush_lines()

    flush_postings()
    flush_lines()
    conn.commit()

    print(f"[build_documents_reuse_table] index: {n_lit_lines} literary lines, "
          f"{n_doc_lines} document lines ({n_too_short} under 3 tokens), "
          f"elapsed {time.time()-t0:.1f}s")

    # FORMULA n-grams: every word of the triple is a formula word (on the
    # word list) or a lemma used by more than DOCUMENT_FORMULA_MAX_DOCS
    # distinct documents -- see this module's docstring.
    formula_hashes = set()
    for tokens, lemmas in formula_pass_items:
        if len(tokens) < 3:
            continue
        lemmas = lemmas if len(lemmas) == len(tokens) else tokens
        for idxs in gen_ngram_indices(len(tokens)):
            tok_gram = tuple(tokens[i] for i in idxs)
            lem_gram = tuple(lemmas[i] for i in idxs)
            is_formula = all(
                _fold_simple(tok) in formula_words
                or doc_lemma_counts.get(lem, 0) > DOCUMENT_FORMULA_MAX_DOCS
                for tok, lem in zip(tok_gram, lem_gram)
            )
            if is_formula:
                formula_hashes.add(lit.hash_ngram(tok_gram))

    print(f"[build_documents_reuse_table] index: {len(formula_hashes)} n-grams are "
          f"formula-word-only (word list + >{DOCUMENT_FORMULA_MAX_DOCS}-document lemmas), "
          f"elapsed {time.time()-t0:.1f}s")

    print("[build_documents_reuse_table] index: computing n-gram document frequencies...")
    conn.execute("CREATE INDEX idx_raw_ngram ON postings_raw(ngram_hash)")
    conn.commit()
    n_dropped = conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT ngram_hash FROM postings_raw GROUP BY ngram_hash HAVING COUNT(*) > ?
        )""", (max_df,)).fetchone()[0]
    conn.execute("""CREATE TABLE postings AS
        SELECT ngram_hash, line_id FROM postings_raw
        WHERE ngram_hash IN (
            SELECT ngram_hash FROM postings_raw GROUP BY ngram_hash HAVING COUNT(*) <= ?
        )""", (max_df,))
    conn.commit()
    n_postings = conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
    conn.execute("DROP TABLE postings_raw")
    conn.commit()
    conn.execute("VACUUM")
    conn.execute("CREATE INDEX idx_postings_ngram ON postings(ngram_hash)")
    conn.execute("CREATE INDEX idx_postings_line ON postings(line_id)")
    conn.execute("CREATE INDEX idx_lines_work ON lines(work)")
    conn.commit()
    conn.close()

    stats = {
        'literary_lines': n_lit_lines, 'document_lines': n_doc_lines,
        'lines_under_3_tokens': n_too_short, 'ngrams_dropped_banal': n_dropped,
        'postings_written': n_postings, 'formula_ngrams': len(formula_hashes),
        'index_elapsed_seconds': time.time() - t0,
    }
    return stats, formula_hashes


def find_cross_pairs(index_db_path, min_shared, min_jaccard, min_shared_override,
                      min_containment, rare_max_df, rare_min_containment, formula_hashes):
    """Same scoring as build_reuse_table.py's find_pairs (jaccard rule,
    containment override, rare-single-ngram rule, formula_hashes gate), but
    a pair is only ever formed between a 'lit' line and a 'doc' line -- never
    lit-lit (that is the literary table's own job) or doc-doc (out of scope
    for a "quoted in a document" feature)."""
    t0 = time.time()
    conn = sqlite3.connect(index_db_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA temp_store = FILE")

    line_meta = {}      # line_id -> (collection, work, ref, seq)
    for line_id, collection, work, ref, seq in conn.execute(
            "SELECT line_id, collection, work, ref, seq FROM lines"):
        line_meta[line_id] = (collection, work, ref, seq)

    conn.execute("CREATE TABLE pair_hits (a INTEGER, b INTEGER, group_size INTEGER, "
                 "ngram_hash INTEGER, formula INTEGER)")
    hit_batch = []
    HIT_BATCH = 500000

    def flush_hits():
        nonlocal hit_batch
        if hit_batch:
            conn.executemany("INSERT INTO pair_hits VALUES (?,?,?,?,?)", hit_batch)
            hit_batch = []

    line_ngram_count = defaultdict(int)
    current_hash = None
    current_lines = []

    def flush_group(lines_in_group, ngram_hash):
        is_formula = 1 if ngram_hash in formula_hashes else 0
        for lid in lines_in_group:
            line_ngram_count[lid] += 1
        lits = [l for l in lines_in_group if line_meta[l][0] == 'lit']
        docs = [l for l in lines_in_group if line_meta[l][0] == 'doc']
        for a in lits:
            for b in docs:
                lo, hi = (a, b) if a < b else (b, a)
                hit_batch.append((lo, hi, len(lines_in_group), ngram_hash, is_formula))
                if len(hit_batch) >= HIT_BATCH:
                    flush_hits()

    n_ngrams = 0
    for ngram_hash, line_id in conn.execute("SELECT ngram_hash, line_id FROM postings ORDER BY ngram_hash"):
        if ngram_hash != current_hash:
            if current_hash is not None:
                flush_group(current_lines, current_hash)
                n_ngrams += 1
            current_hash = ngram_hash
            current_lines = []
        current_lines.append(line_id)
    if current_lines:
        flush_group(current_lines, current_hash)
        n_ngrams += 1
    flush_hits()
    conn.commit()

    print(f"[build_documents_reuse_table] pairs: {n_ngrams} n-grams scanned, "
          f"elapsed {time.time()-t0:.1f}s")

    conn.execute("CREATE INDEX idx_pair_hits_ab ON pair_hits(a, b)")
    conn.commit()

    kept = []
    n_candidates = 0
    n_excluded_all_formula = 0
    n_kept_via_rare_single = 0
    n_excluded_formula_rare = 0
    for a, b, shared, min_gdf, single_hash, n_formula in conn.execute(
            "SELECT a, b, COUNT(*), MIN(group_size), MIN(ngram_hash), SUM(formula) "
            "FROM pair_hits GROUP BY a, b"):
        n_candidates += 1
        if n_formula >= shared:
            n_excluded_all_formula += 1
            continue
        na, nb = line_ngram_count[a], line_ngram_count[b]
        union = na + nb - shared
        jaccard = shared / union if union > 0 else 0.0
        min_ngrams = min(na, nb)
        containment = shared / min_ngrams if min_ngrams > 0 else 0.0
        meets_jaccard = shared >= min_shared and jaccard >= min_jaccard
        meets_override = shared >= min_shared_override and containment >= min_containment
        meets_rare_single = (
            bool(rare_max_df) and shared == 1 and min_gdf < rare_max_df
            and containment >= rare_min_containment
        )
        if meets_rare_single and single_hash in formula_hashes:
            meets_rare_single = False
            n_excluded_formula_rare += 1
        if meets_jaccard or meets_override or meets_rare_single:
            if meets_rare_single and not meets_jaccard and not meets_override:
                n_kept_via_rare_single += 1
            kept.append((a, b, shared, jaccard))

    conn.execute("DROP TABLE pair_hits")
    conn.commit()
    conn.close()

    print(f"[build_documents_reuse_table] pairs: {n_candidates} candidate cross-collection "
          f"pairs, {len(kept)} kept ({n_kept_via_rare_single} via the rare-single-ngram rule, "
          f"{n_excluded_all_formula} dropped as all-formula, {n_excluded_formula_rare} more "
          f"would have qualified for the rare-single rule but were formula-only), "
          f"elapsed {time.time()-t0:.1f}s")

    # Resolve to (lit_work, lit_ref, lit_seq, doc_id, doc_bucket, doc_ref, doc_seq, shared, jaccard)
    pair_info = []
    pair_by_seq = {}
    for a, b, shared, jaccard in kept:
        ca, wa, ra, sa = line_meta[a]
        cb, wb, rb, sb = line_meta[b]
        if ca == 'lit':
            lit_work, lit_ref, lit_seq = wa, ra, sa
            doc_id, doc_ref, doc_seq = wb, rb, sb
        else:
            lit_work, lit_ref, lit_seq = wb, rb, sb
            doc_id, doc_ref, doc_seq = wa, ra, sa
        idx = len(pair_info)
        pair_info.append([lit_work, lit_ref, lit_seq, doc_id, doc_ref, doc_seq, shared, jaccard, 1])
        pair_by_seq[(lit_work, doc_id, lit_seq, doc_seq)] = idx

    # Chain adjacent quoted lines into spans, same rule as the literary
    # table: the literary line advances by 1 AND the document's own local
    # line sequence advances by 1 in the same pair of works.
    visited = set()
    for idx, (lit_work, lit_ref, lit_seq, doc_id, doc_ref, doc_seq, shared, jaccard, _) in enumerate(pair_info):
        if idx in visited:
            continue
        chain = [idx]
        visited.add(idx)
        cl, cd = lit_seq, doc_seq
        while True:
            nxt = pair_by_seq.get((lit_work, doc_id, cl + 1, cd + 1))
            if nxt is None or nxt in visited:
                break
            chain.append(nxt)
            visited.add(nxt)
            cl, cd = cl + 1, cd + 1
        if len(chain) > 1:
            for i in chain:
                pair_info[i][8] = len(chain)

    stats = {
        'candidate_cross_pairs': n_candidates, 'pairs_kept': len(pair_info),
        'pairs_kept_via_rare_single_ngram': n_kept_via_rare_single,
        'candidates_excluded_all_formula': n_excluded_all_formula,
        'pairs_elapsed_seconds': time.time() - t0,
    }
    return pair_info, stats


def _pair_restored_flag(doc_bucket_sidecars, doc_id, doc_ref, doc_bucket):
    """1 if the document line's sidecar marks it fully restored, 0
    otherwise (partly or not restored, or no sidecar data) -- a coarse
    per-LINE flag, not per-matched-word: this table stores one row per
    pair, with no record of exactly which token positions were shared
    (that is reconstructed at read time from the token arrays themselves,
    the same way backend/reuse_table.py's bold_spans is -- see
    backend/reuse_documents.py). A document line with ANY restored word is
    flagged, matching the Reader's existing "match on restored text"
    wording, which already treats a line as restored-or-not rather than
    counting words (backend/documents.py's restored_indices / the
    documents-collection card)."""
    sidecar = doc_bucket_sidecars.get(doc_bucket)
    if sidecar is None:
        return 0
    restored_positions = sidecar.get(doc_ref)
    return 1 if restored_positions else 0


def write_output_db(out_db_path, pair_info, doc_sidecars_by_pair_bucket, meta):
    if os.path.exists(out_db_path):
        os.remove(out_db_path)
    conn = sqlite3.connect(out_db_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("""CREATE TABLE pairs (
        lit_work TEXT, lit_ref TEXT, lit_seq INTEGER,
        doc_id TEXT, doc_bucket TEXT, doc_ref TEXT, doc_seq INTEGER,
        shared INTEGER, jaccard REAL, span_len INTEGER, doc_restored INTEGER
    )""")
    rows = []
    for lit_work, lit_ref, lit_seq, doc_id, doc_ref, doc_seq, shared, jaccard, span_len in pair_info:
        doc_bucket = doc_sidecars_by_pair_bucket.get(doc_id, '')
        restored = _pair_restored_flag(
            doc_sidecars_by_pair_bucket.get('__sidecars__', {}), doc_id, doc_ref, doc_bucket)
        rows.append((lit_work, lit_ref, lit_seq, doc_id, doc_bucket, doc_ref, doc_seq,
                     shared, jaccard, span_len, restored))
    conn.executemany("INSERT INTO pairs VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany("INSERT INTO meta VALUES (?,?)",
                      [(k, '' if v is None else str(v)) for k, v in meta.items()])
    conn.execute("CREATE INDEX idx_pairs_lit ON pairs(lit_work, lit_ref)")
    conn.execute("CREATE INDEX idx_pairs_doc ON pairs(doc_id)")
    conn.commit()
    conn.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--language', default='la', choices=['la', 'grc'])
    ap.add_argument('--literary-texts-root', default=os.path.join(BASE_DIR, 'texts'))
    ap.add_argument('--literary-cache-root', default=os.path.join(BASE_DIR, 'cache', 'lemmas'))
    ap.add_argument('--documents-index-dir', default=DOCUMENTS_INDEX_DIR_DEFAULT)
    ap.add_argument('--documents-sidecar-root', default=DOCUMENTS_SIDECAR_ROOT_DEFAULT)
    ap.add_argument('--max-df', type=int, default=200)
    ap.add_argument('--min-shared', type=int, default=2)
    ap.add_argument('--min-jaccard', type=float, default=0.15)
    ap.add_argument('--min-shared-override', type=int, default=4)
    ap.add_argument('--min-containment', type=float, default=0.5)
    ap.add_argument('--rare-max-df', type=int, default=20)
    ap.add_argument('--rare-min-containment', type=float, default=0.06)
    ap.add_argument('--out-db', default=None)
    ap.add_argument('--stats-out', default=None)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    out_db = args.out_db or os.path.join(OUT_DIR, f'{args.language}_documents.db')
    stats_out = args.stats_out or os.path.join(OUT_DIR, f'{args.language}_documents_stats.json')

    t_start = time.time()

    # Point the literary builder's own module globals at wherever this run's
    # texts/cache roots are (a worktree with no texts/cache/lemmas of its own
    # points these at another checkout's absolute paths -- see this module's
    # docstring) -- the same monkeypatch scripts/documents/build_documents_index.py
    # already uses for the identical reason.
    orig_lit = (lit.TEXTS_DIR, lit.CACHE_DIR)
    orig_lcm = (lemma_cache_mod.TEXTS_DIR, lemma_cache_mod.CACHE_DIR)
    lit.TEXTS_DIR = args.literary_texts_root
    lit.CACHE_DIR = args.literary_cache_root
    lemma_cache_mod.TEXTS_DIR = args.literary_texts_root
    lemma_cache_mod.CACHE_DIR = args.literary_cache_root
    try:
        lit_cache_data, skipped_parts, missing_cache = lit.discover_corpus(args.language)
    finally:
        lit.TEXTS_DIR, lit.CACHE_DIR = orig_lit
        lemma_cache_mod.TEXTS_DIR, lemma_cache_mod.CACHE_DIR = orig_lcm

    print(f"[build_documents_reuse_table] {len(lit_cache_data)} literary works "
          f"({len(skipped_parts)} .part. skipped, {len(missing_cache)} missing cache)")

    doc_lines, doc_lemma_counts = discover_documents(args.language, args.documents_index_dir)
    print(f"[build_documents_reuse_table] {len(doc_lines)} document lines, "
          f"{len(doc_lemma_counts)} lemmas with a document-frequency count")

    formula_words = load_formula_words(args.language)
    print(f"[build_documents_reuse_table] {len(formula_words)} formula words loaded "
          f"for '{args.language}'")

    tmp_dir = tempfile.mkdtemp(prefix=f'reuse_documents_{args.language}_')
    index_db_path = os.path.join(tmp_dir, f'{args.language}_index.db')
    try:
        index_stats, formula_hashes = build_combined_index(
            lit_cache_data, doc_lines, index_db_path, args.max_df,
            formula_words, doc_lemma_counts, language=args.language)
        pair_info, pair_stats = find_cross_pairs(
            index_db_path, args.min_shared, args.min_jaccard, args.min_shared_override,
            args.min_containment, args.rare_max_df, args.rare_min_containment, formula_hashes)

        # doc_id -> bucket filename (for the sidecar lookup) and the loaded
        # sidecar tables themselves, both built only for buckets a kept pair
        # actually touches.
        doc_id_to_bucket = {u['doc_id']: u['bucket'] for u in doc_lines}
        buckets_needed = {doc_id_to_bucket.get(p[3], '') for p in pair_info}
        sidecars = {b: load_sidecar(args.documents_sidecar_root, args.language, b)
                    for b in buckets_needed if b}
        bucket_map = dict(doc_id_to_bucket)
        bucket_map['__sidecars__'] = sidecars

        corpus_version = lit.get_corpus_version(args.language)
        built_at = datetime.now(timezone.utc).isoformat()
        meta = {
            'built_at': built_at, 'corpus_version': corpus_version,
            'language': args.language,
            'literary_works': len(lit_cache_data), 'document_lines': len(doc_lines),
            'max_df': args.max_df, 'min_shared': args.min_shared,
            'min_jaccard': args.min_jaccard, 'min_shared_override': args.min_shared_override,
            'min_containment': args.min_containment, 'rare_max_df': args.rare_max_df,
            'rare_min_containment': args.rare_min_containment,
            'document_formula_max_docs': DOCUMENT_FORMULA_MAX_DOCS,
            'formula_words_count': len(formula_words),
            'formula_ngrams': index_stats['formula_ngrams'],
            'pairs_kept': pair_stats['pairs_kept'],
        }
        write_output_db(out_db, pair_info, bucket_map, meta)
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    elapsed = time.time() - t_start
    stats = {**index_stats, **pair_stats, 'total_elapsed_seconds': elapsed, 'out_db': out_db,
             'corpus_version': corpus_version, 'built_at': built_at}
    with open(stats_out, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"[build_documents_reuse_table] done in {elapsed:.1f}s. DB: {out_db}")
    print(json.dumps(stats, indent=2))


if __name__ == '__main__':
    main()
