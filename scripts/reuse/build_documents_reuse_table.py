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

LITERARY DOCUMENT FREQUENCY (--max-literary-works)
  The formula test above measures how many DOCUMENTS use a phrase. A phrase
  can be rare among documents and still be a stock phrase of the literature
  (Galen repeats his formulas hundreds of times, so any ordinary phrase is
  most likely to turn up in him). For every shared n-gram the build counts
  the distinct LITERARY WORKS (not lines) whose lines contain it, in the same
  combined index the pairs come from, and a pair's `lit_works` is the
  smallest such count over its non-formula shared n-grams. A pair whose
  every shared n-gram occurs in more than N works is dropped. N = 0 turns the
  test off. Only n-grams that survived --max-df (at most that many lines in
  both collections together) are in the index, so the count is exact where it
  matters. Per literary work, the stats file reports pairs per 1,000 lines so
  one author's share is judged against his size.

REORDER RULE (--no-reorder turns it off)
  The ordered rule cannot see a parody that changes word order (the Pompeian
  fullers' "Fullones ululamque cano, non arma virumque" against Aen. 1.1).
  The reorder rule indexes every set of 3 distinct CONTENT lemmas (function
  words and numerals excluded) lying within a window of 6 tokens, in any
  order, and pairs lines that share one. It is stricter than the ordered
  rule where it matters: 3 content lemmas on each side (the ordered rule needs
  2 adjacent), the set must occur in at most --reorder-max-df lines of the
  two collections together, it is subject to the same formula and literary-
  works tests, and it only ADDS pairs that share no ordered n-gram at all.
  Such a pair has rule = 'reorder', jaccard 0 and shared = the number of
  shared sets (so a single-set match reads as the 'possible' tier).

CANDIDATES CACHE (--candidates-cache PATH)
  After the index and pair scan, every candidate pair that passed the tier
  tests is saved with its quality verdict and its literary-works count.
  When PATH exists the next run skips the index build entirely and only
  applies the cheap filters (--max-literary-works, --sweep-max-works), in
  seconds. Tier thresholds and the quality thresholds are baked into the
  cache, so changing them needs a fresh cache.

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


def load_function_words(language):
    """Function-word lemmas (data/documents/function_words_<lang>.txt:
    CLTK stopword list plus a few frequent pronoun lemmas, see the file's
    own header) used by the pair quality filter."""
    path = os.path.join(FORMULA_WORDS_DIR_DEFAULT, f'function_words_{language}.txt')
    words = set()
    if not os.path.exists(path):
        return words
    with open(path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            raw_line = raw_line.split('#', 1)[0].strip()
            if raw_line:
                words.add(_fold_simple(raw_line))
    return words


import re  # noqa: E402

# Roman numerals: a valid numeral string (m, then d/c, l/x, v/i groups in
# order). The lemma table cannot tell a numeral from a word (it lists i, ii,
# iii, li, dc as entries), so a few real words that happen to be valid
# numerals are excluded by hand.
_ROMAN_RE = re.compile(r'^m{0,4}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$')
_ROMAN_REAL_WORDS = {'mi', 'di', 'dii', 'li', 'ci', 'mix'}
# Greek alphabetic numerals as the caches store them (accents and the
# keraia are gone, so a token cannot be told from a word by its mark):
# at most one hundreds letter, then one tens letter, then one units letter,
# in that order, 1 to 3 letters (ib = 12, lb = 32, rkh = 128). Words that
# fit the shape (me, se, pe) are function words anyway.
_GREEK_NUM_RE = re.compile(
    '^[ρστυφχψωϡ]?[ικλμνξοπϙ]?[αβγδεϛζηθ]?$')


def is_numeral_lemma(word, language=None):
    """True if `word` is a Roman numeral (Latin) or an alphabetic numeral
    (Greek) rather than an ordinary word. Single letters count (sigla)."""
    if not word:
        return False
    if language == 'la':
        return word not in _ROMAN_REAL_WORDS and bool(_ROMAN_RE.match(word))
    if language == 'grc':
        return len(word) <= 3 and bool(_GREEK_NUM_RE.match(word))
    return False


REORDER_WINDOW = 6
REORDER_MAX_DF_DEFAULT = 40
REORDER_MIN_CONTENT = 3
# Each side's shared content lemmas must be at least this share of that
# side's content lemmas (a lemma set that is only a small part of a long
# line is a coincidence of vocabulary, not a reworded line).
REORDER_MIN_COVERAGE = 0.5
# Chosen by the sweep in docs/DECISIONS.md / the PR description; 0 = off.
MAX_LITERARY_WORKS_DEFAULT = 0


def reorder_triples(lemmas, is_content, window=REORDER_WINDOW):
    """Yield each distinct sorted triple of 3 different content lemmas whose
    positions in the line lie within `window` tokens (last position minus
    first at most window - 1), in any order. `is_content(lemma)` says
    whether a lemma counts (not a function word, not a numeral)."""
    pos = [i for i, w in enumerate(lemmas) if is_content(w)]
    seen = set()
    n = len(pos)
    for x in range(n):
        for y in range(x + 1, n):
            if pos[y] - pos[x] > window - 2:
                break
            for z in range(y + 1, n):
                if pos[z] - pos[x] > window - 1:
                    break
                trio = (lemmas[pos[x]], lemmas[pos[y]], lemmas[pos[z]])
                if len(set(trio)) < 3:
                    continue
                key = tuple(sorted(trio))
                if key not in seen:
                    seen.add(key)
                    yield key


def shared_coverage(lit_lemmas, doc_lemmas, function_words, language=None):
    """Smaller of the two coverages: distinct shared content lemmas divided
    by the number of distinct content lemmas on each side (0.0 if a side has
    none)."""
    def cont(L):
        return {x for x in (_fold_simple(w) for w in L)
                if x and x not in function_words and not is_numeral_lemma(x, language)}
    a, b = cont(lit_lemmas), cont(doc_lemmas)
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a), len(b))


def longest_shared_run(a, b):
    """Length of the longest contiguous run of lemmas that appears, in the
    same order and adjacent, in both lists (longest common substring)."""
    best = 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            if x == y:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
        prev = cur
    return best


def pair_quality(lit_lemmas, doc_lemmas, function_words, min_content=2, min_run=2,
                 language=None):
    """Quality test for one literary/document line pair. Returns
    (content_shared, longest_run, fails_content, fails_run): the number of
    distinct shared lemmas that are not function words, the longest
    contiguous shared lemma run (function words included), and whether each
    threshold was missed. A pair that shares only function words (a Greek
    pair sharing o, kai, en, eis) fails the content test; two content
    lemmas that are not adjacent fail the run test."""
    lit_l = [_fold_simple(w) for w in lit_lemmas]
    doc_l = [_fold_simple(w) for w in doc_lemmas]
    content = {w for w in set(lit_l) & set(doc_l)
               if w and w not in function_words and not is_numeral_lemma(w, language)}
    run = longest_shared_run(lit_l, doc_l)
    return len(content), run, len(content) < min_content, run < min_run


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
                          formula_words, doc_lemma_counts, language=None,
                          function_words=None, reorder=False,
                          reorder_window=REORDER_WINDOW,
                          reorder_max_df=REORDER_MAX_DF_DEFAULT):
    # lit_cache_data: a mapping {basename: cache} or any iterable of
    # (basename, cache) pairs, so main() can hand over one work at a time.
    # Formula n-grams are found line by line as the index is written, not in
    # a second pass over a list of every line: holding every Greek cache
    # plus that list reached the 12 GB cap and stalled (2026-10-09).
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
    formula_hashes = set()

    # Reorder rule (see the module docstring): postings of order-free
    # content-lemma triples. Only triples that occur in some document can
    # ever pair, so the document lines are scanned first and the literary
    # lines index only the hashes found there.
    function_words = function_words or set()
    bag_batch = []
    doc_bag_hashes = set()
    n_bag_postings = 0
    if reorder:
        conn.execute("CREATE TABLE postings_bag_raw (ngram_hash INTEGER, line_id INTEGER)")

    def is_content(w):
        w = _fold_simple(w)
        return bool(w) and w not in function_words and not is_numeral_lemma(w, language)

    def is_formula_lemma(w):
        w = _fold_simple(w)
        return w in formula_words or doc_lemma_counts.get(w, 0) > DOCUMENT_FORMULA_MAX_DOCS

    def bag_hashes(tokens, lemmas):
        if not reorder or len(tokens) < 3:
            return
        lemmas = lemmas if len(lemmas) == len(tokens) else tokens
        for trio in reorder_triples(lemmas, is_content, reorder_window):
            if all(is_formula_lemma(w) for w in trio):
                continue
            yield lit.hash_ngram(trio)

    def add_bag(tokens, lemmas, line_id_, only_known):
        nonlocal bag_batch, n_bag_postings
        for h in bag_hashes(tokens, lemmas):
            if only_known and h not in doc_bag_hashes:
                continue
            bag_batch.append((h, line_id_))
        if len(bag_batch) >= BATCH:
            conn.executemany("INSERT INTO postings_bag_raw VALUES (?,?)", bag_batch)
            n_bag_postings += len(bag_batch)
            bag_batch = []

    if reorder:
        for unit in doc_lines:
            doc_bag_hashes.update(bag_hashes(unit['tokens'], unit['lemmas']))
        print(f"[build_documents_reuse_table] index: {len(doc_bag_hashes)} distinct "
              f"order-free content-lemma sets in documents", flush=True)

    def note_formulas(tokens, lemmas):
        # FORMULA n-grams: every word of the triple is a formula word (on
        # the word list) or a lemma used by more than
        # DOCUMENT_FORMULA_MAX_DOCS distinct documents -- see this module's
        # docstring.
        if len(tokens) < 3:
            return
        lemmas = lemmas if len(lemmas) == len(tokens) else tokens
        for idxs in gen_ngram_indices(len(tokens)):
            tok_gram = tuple(tokens[i] for i in idxs)
            if all(
                _fold_simple(tokens[i]) in formula_words
                or doc_lemma_counts.get(lemmas[i], 0) > DOCUMENT_FORMULA_MAX_DOCS
                for i in idxs
            ):
                formula_hashes.add(lit.hash_ngram(tok_gram))

    pairs = lit_cache_data.items() if hasattr(lit_cache_data, 'items') else lit_cache_data
    for tess_basename, data in pairs:
        work_id = data.get('text_id', tess_basename)
        if work_id.endswith('.tess'):
            work_id = work_id[:-len('.tess')]
        for seq, unit in enumerate(data.get('units_line', [])):
            tokens = unit.get('tokens') or []
            lemmas = lit._line_lemmas(unit)
            ref = unit.get('ref', '')
            n_lit_lines += 1
            note_formulas(tokens, lemmas)
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
            add_bag(tokens, lemmas, line_id, True)
            line_rows.append((line_id, 'lit', work_id, ref, seq, len(tokens)))
            line_id += 1
            if len(line_rows) >= BATCH:
                flush_lines()

    for unit in doc_lines:
        tokens = unit['tokens']
        lemmas = unit['lemmas'] if len(unit['lemmas']) == len(tokens) else tokens
        n_doc_lines += 1
        note_formulas(tokens, lemmas)
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
        add_bag(tokens, unit['lemmas'], line_id, False)
        line_rows.append((line_id, 'doc', unit['doc_id'], unit['ref'], unit['doc_seq'], len(tokens)))
        line_id += 1
        if len(line_rows) >= BATCH:
            flush_lines()

    flush_postings()
    flush_lines()
    if reorder and bag_batch:
        conn.executemany("INSERT INTO postings_bag_raw VALUES (?,?)", bag_batch)
        n_bag_postings += len(bag_batch)
        bag_batch = []
    doc_bag_hashes = None
    conn.commit()

    print(f"[build_documents_reuse_table] index: {n_lit_lines} literary lines, "
          f"{n_doc_lines} document lines ({n_too_short} under 3 tokens), "
          f"elapsed {time.time()-t0:.1f}s")

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
    n_bag_kept = 0
    if reorder:
        conn.execute("CREATE INDEX idx_bag_raw ON postings_bag_raw(ngram_hash)")
        conn.execute("""CREATE TABLE postings_bag AS
            SELECT ngram_hash, line_id FROM postings_bag_raw
            WHERE ngram_hash IN (
                SELECT ngram_hash FROM postings_bag_raw GROUP BY ngram_hash HAVING COUNT(*) <= ?
            )""", (reorder_max_df,))
        n_bag_kept = conn.execute("SELECT COUNT(*) FROM postings_bag").fetchone()[0]
        conn.execute("DROP TABLE postings_bag_raw")
        conn.execute("CREATE INDEX idx_postings_bag ON postings_bag(ngram_hash)")
        print(f"[build_documents_reuse_table] index: {n_bag_postings} order-free postings, "
              f"{n_bag_kept} kept at <= {reorder_max_df} lines per set", flush=True)
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
        'reorder_postings_written': n_bag_kept,
        'index_elapsed_seconds': time.time() - t0,
    }
    return stats, formula_hashes


def find_candidates(index_db_path, min_shared, min_jaccard, min_shared_override,
                     min_containment, rare_max_df, rare_min_containment, formula_hashes):
    """The pair scan. Same scoring as build_reuse_table.py's find_pairs
    (jaccard rule, containment override, rare-single-ngram rule,
    formula_hashes gate), but a pair is only ever formed between a 'lit' line
    and a 'doc' line -- never lit-lit (that is the literary table's own job)
    or doc-doc (out of scope for a "quoted in a document" feature).

    Returns (cands, work_lines, stats). Each candidate is
    (lit_work, lit_ref, lit_seq, doc_id, doc_ref, doc_seq, shared, jaccard,
    rule, min_works): `rule` is 'ordered' or 'reorder' (module docstring),
    `min_works` the smallest number of distinct literary works any of the
    pair's non-formula shared n-grams occurs in (module docstring,
    "LITERARY DOCUMENT FREQUENCY"). Quality and works filters are NOT
    applied here; see select_pairs."""
    t0 = time.time()
    conn = sqlite3.connect(index_db_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA temp_store = FILE")

    line_meta = {}      # line_id -> (collection, work, ref, seq)
    work_lines = defaultdict(int)
    for line_id, collection, work, ref, seq in conn.execute(
            "SELECT line_id, collection, work, ref, seq FROM lines"):
        line_meta[line_id] = (collection, work, ref, seq)
        if collection == 'lit':
            work_lines[work] += 1

    conn.execute("CREATE TABLE pair_hits (a INTEGER, b INTEGER, group_size INTEGER, "
                 "ngram_hash INTEGER, formula INTEGER, lit_works INTEGER)")
    hit_batch = []
    HIT_BATCH = 500000

    def flush_hits():
        nonlocal hit_batch
        if hit_batch:
            conn.executemany("INSERT INTO pair_hits VALUES (?,?,?,?,?,?)", hit_batch)
            hit_batch = []

    line_ngram_count = defaultdict(int)

    def scan(table, formula_set, count_lines):
        current_hash = None
        current_lines = []
        n_groups = 0

        def flush_group(lines_in_group, ngram_hash):
            is_formula = 1 if (formula_set and ngram_hash in formula_set) else 0
            if count_lines:
                for lid in lines_in_group:
                    line_ngram_count[lid] += 1
            lits = [l for l in lines_in_group if line_meta[l][0] == 'lit']
            docs = [l for l in lines_in_group if line_meta[l][0] == 'doc']
            n_works = len({line_meta[l][1] for l in lits})
            for a in lits:
                for b in docs:
                    lo, hi = (a, b) if a < b else (b, a)
                    hit_batch.append((lo, hi, len(lines_in_group), ngram_hash, is_formula, n_works))
                    if len(hit_batch) >= HIT_BATCH:
                        flush_hits()

        for ngram_hash, line_id in conn.execute(
                f"SELECT ngram_hash, line_id FROM {table} ORDER BY ngram_hash"):
            if ngram_hash != current_hash:
                if current_hash is not None:
                    flush_group(current_lines, current_hash)
                    n_groups += 1
                current_hash = ngram_hash
                current_lines = []
            current_lines.append(line_id)
        if current_lines:
            flush_group(current_lines, current_hash)
            n_groups += 1
        flush_hits()
        return n_groups

    n_ngrams = scan('postings', formula_hashes, True)
    conn.commit()
    print(f"[build_documents_reuse_table] pairs: {n_ngrams} n-grams scanned, "
          f"elapsed {time.time()-t0:.1f}s")

    conn.execute("CREATE INDEX idx_pair_hits_ab ON pair_hits(a, b)")
    conn.commit()

    cands = []          # (a, b, shared, jaccard, rule, min_works)
    n_candidates = 0
    n_excluded_all_formula = 0
    n_kept_via_rare_single = 0
    n_excluded_formula_rare = 0
    for a, b, shared, min_gdf, single_hash, n_formula, min_works in conn.execute(
            "SELECT a, b, COUNT(*), MIN(group_size), MIN(ngram_hash), SUM(formula), "
            "MIN(CASE WHEN formula = 0 THEN lit_works END) FROM pair_hits GROUP BY a, b"):
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
            cands.append((a, b, shared, jaccard, 'ordered', min_works))

    n_ordered = len(cands)
    n_reorder_candidates = n_reorder = 0
    has_bag = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = 'postings_bag'").fetchone()
    if has_bag:
        # Order-free sets: pairs that share no ordered n-gram at all (not
        # even one the ordered rule then rejected) and share >= 1 set.
        ordered_pairs = {(a, b) for a, b in conn.execute("SELECT DISTINCT a, b FROM pair_hits")}
        conn.execute("DELETE FROM pair_hits")
        scan('postings_bag', None, False)
        conn.commit()
        for a, b, shared, min_works in conn.execute(
                "SELECT a, b, COUNT(*), MIN(lit_works) FROM pair_hits GROUP BY a, b"):
            n_reorder_candidates += 1
            if (a, b) in ordered_pairs:
                continue
            cands.append((a, b, shared, 0.0, 'reorder', min_works))
            n_reorder += 1
        del ordered_pairs

    conn.execute("DROP TABLE pair_hits")
    conn.commit()
    conn.close()

    print(f"[build_documents_reuse_table] pairs: {n_candidates} candidate cross-collection "
          f"pairs, {n_ordered} pass the tier rules ({n_kept_via_rare_single} via the rare-single-ngram "
          f"rule, {n_excluded_all_formula} dropped as all-formula, {n_excluded_formula_rare} more "
          f"would have qualified for the rare-single rule but were formula-only); "
          f"{n_reorder} order-free candidates added; elapsed {time.time()-t0:.1f}s")

    # Resolve to (lit_work, lit_ref, lit_seq, doc_id, doc_ref, doc_seq, shared, jaccard, rule, min_works)
    resolved = []
    for a, b, shared, jaccard, rule, min_works in cands:
        ca, wa, ra, sa = line_meta[a]
        cb, wb, rb, sb = line_meta[b]
        if ca == 'lit':
            resolved.append((wa, ra, sa, wb, rb, sb, shared, jaccard, rule, min_works))
        else:
            resolved.append((wb, rb, sb, wa, ra, sa, shared, jaccard, rule, min_works))
    stats = {
        'candidate_cross_pairs': n_candidates,
        'candidates_passing_tier_rules': n_ordered,
        'pairs_kept_via_rare_single_ngram': n_kept_via_rare_single,
        'candidates_excluded_all_formula': n_excluded_all_formula,
        'reorder_pairs_considered': n_reorder_candidates,
        'reorder_candidates_added': n_reorder,
        'pairs_elapsed_seconds': time.time() - t0,
    }
    return resolved, dict(work_lines), stats


def select_pairs(cands, verdicts, max_works=0, reorder_min_content=REORDER_MIN_CONTENT,
                 reorder_min_coverage=REORDER_MIN_COVERAGE):
    """Apply the cheap filters to scanned candidates and chain spans.
    `verdicts[i]` is (content_shared, fails_content, fails_run[, coverage])
    for cands[i],
    or None / (None, False, False) when quality was not tested. A candidate
    is dropped when it fails the quality test (an ordered pair: content or
    run; a reorder pair: fewer than `reorder_min_content` shared content
    lemmas or a coverage below `reorder_min_coverage`, no run test), or when `max_works` is set and every non-formula
    shared n-gram occurs in more than `max_works` literary works. Returns
    pair_info rows (lit_work, lit_ref, lit_seq, doc_id, doc_ref, doc_seq,
    shared, jaccard, span_len, content_shared, lit_works, rule)."""
    pair_info = []
    for c, v in zip(cands, verdicts):
        (lit_work, lit_ref, lit_seq, doc_id, doc_ref, doc_seq, shared, jaccard, rule, min_works) = c
        n_content, fails_c, fails_r = v[:3] if v is not None else (None, False, False)
        coverage = v[3] if v is not None and len(v) > 3 else None
        if rule == 'reorder':
            if n_content is not None and n_content < reorder_min_content:
                continue
            if coverage is not None and coverage < reorder_min_coverage:
                continue
        elif fails_c or fails_r:
            continue
        # The literary-works discount applies to the single-phrase tier only
        # (shared == 1, shown as "possible"). A pair sharing two or more
        # phrases is a quotation whatever the phrase's currency: at N=10 the
        # discount was dropping Vulgate verses on stones that Ambrose, Jerome
        # and Sedulius all quote (edh:HD025119, 17 shared phrases in 14 works)
        # while keeping the Fathers who happened to share one rarer phrase.
        # Measured 2026-10-09: 123 Latin pairs with shared >= 2 reclaimed,
        # none in Greek. (Aeneid 1.204 on edh:HD019352, shared == 1 and its
        # one phrase in 12 works, stays lost: the limit of frequency alone.)
        if max_works and min_works is not None and min_works > max_works and shared < 2:
            continue
        pair_info.append([lit_work, lit_ref, lit_seq, doc_id, doc_ref, doc_seq, shared,
                          jaccard, 1, n_content, min_works, rule])
    chain_spans(pair_info)
    return pair_info


def chain_spans(pair_info):
    """Chain adjacent quoted lines into spans, same rule as the literary
    table: the literary line advances by 1 AND the document's own local
    line sequence advances by 1 in the same pair of works. Sets column 8
    (span_len) in place."""
    pair_by_seq = {}
    for idx, p in enumerate(pair_info):
        pair_by_seq[(p[0], p[3], p[2], p[5])] = idx
    visited = set()
    for idx, p in enumerate(pair_info):
        if idx in visited:
            continue
        lit_work, lit_seq, doc_id, doc_seq = p[0], p[2], p[3], p[5]
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


def find_cross_pairs(index_db_path, min_shared, min_jaccard, min_shared_override,
                      min_containment, rare_max_df, rare_min_containment, formula_hashes,
                      quality_filter=None, max_works=0):
    """find_candidates + the quality test + select_pairs in one call (the
    shape the build used before the candidates cache). Returns
    (pair_info, stats)."""
    t0 = time.time()
    cands, work_lines, stats = find_candidates(
        index_db_path, min_shared, min_jaccard, min_shared_override, min_containment,
        rare_max_df, rare_min_containment, formula_hashes)
    verdicts, quality_stats = annotate_quality(cands, quality_filter)
    pair_info = select_pairs(cands, verdicts, max_works)
    stats.update({
        'pairs_kept': len(pair_info),
        'pairs_before_quality_filter': len(cands),
        'quality_filter': quality_stats,
        'work_lines': work_lines,
    })
    stats['pairs_elapsed_seconds'] = stats.get('pairs_elapsed_seconds', 0) + time.time() - t0
    return pair_info, stats


def annotate_quality(cands, quality_filter):
    """verdicts, stats for a candidate list; quality_filter(resolved8) ->
    (verdicts, stats) as built by main()."""
    if quality_filter is None:
        return [None] * len(cands), {}
    verdicts, quality_stats = quality_filter([c[:8] for c in cands])
    print(f"[build_documents_reuse_table] quality filter: {quality_stats}", flush=True)
    return verdicts, quality_stats


def per_work_report(pair_info, work_lines):
    """{work: {'pairs', 'lines', 'pairs_per_1000_lines'}} for every literary
    work with at least one kept pair: the author-size normalisation, so a
    large work's share is judged against its size."""
    counts = defaultdict(int)
    for p in pair_info:
        counts[p[0]] += 1
    out = {}
    for w, n in counts.items():
        lines = work_lines.get(w, 0)
        out[w] = {'pairs': n, 'lines': lines,
                  'pairs_per_1000_lines': round(1000.0 * n / lines, 3) if lines else None}
    return out


def save_candidates_cache(path, cands, verdicts, buckets, work_lines, meta):
    if os.path.exists(path):
        os.remove(path)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("""CREATE TABLE cand (
        lit_work TEXT, lit_ref TEXT, lit_seq INTEGER, doc_id TEXT, doc_ref TEXT,
        doc_seq INTEGER, doc_bucket TEXT, shared INTEGER, jaccard REAL, rule TEXT,
        min_works INTEGER, content INTEGER, fails_content INTEGER, fails_run INTEGER,
        coverage REAL)""")
    rows = []
    for c, v in zip(cands, verdicts):
        content, fc, fr = v[:3] if v is not None else (None, False, False)
        cov = v[3] if v is not None and len(v) > 3 else None
        rows.append((c[0], c[1], c[2], c[3], c[4], c[5], buckets.get(c[3], ''), c[6], c[7],
                     c[8], c[9], content, int(bool(fc)), int(bool(fr)), cov))
    conn.executemany("INSERT INTO cand VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.execute("CREATE TABLE work_lines (work TEXT PRIMARY KEY, n INTEGER)")
    conn.executemany("INSERT INTO work_lines VALUES (?,?)", list(work_lines.items()))
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany("INSERT INTO meta VALUES (?,?)",
                     [(k, json.dumps(v)) for k, v in meta.items()])
    conn.commit()
    conn.close()


def load_candidates_cache(path):
    """-> (cands, verdicts, buckets, work_lines, meta), the inverse of
    save_candidates_cache."""
    conn = sqlite3.connect(path)
    cands, verdicts, buckets = [], [], {}
    for (lw, lr, ls, di, dr, ds, db, sh, j, rule, mw, content, fc, fr, cov) in conn.execute(
            "SELECT lit_work, lit_ref, lit_seq, doc_id, doc_ref, doc_seq, doc_bucket, shared, "
            "jaccard, rule, min_works, content, fails_content, fails_run, coverage "
            "FROM cand ORDER BY rowid"):
        cands.append((lw, lr, ls, di, dr, ds, sh, j, rule, mw))
        verdicts.append((content, bool(fc), bool(fr), cov))
        buckets[di] = db
    work_lines = dict(conn.execute("SELECT work, n FROM work_lines"))
    meta = {k: json.loads(v) for k, v in conn.execute("SELECT key, value FROM meta")}
    conn.close()
    return cands, verdicts, buckets, work_lines, meta


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
        shared INTEGER, jaccard REAL, span_len INTEGER, doc_restored INTEGER,
        content_shared INTEGER, lit_works INTEGER, rule TEXT
    )""")
    rows = []
    for lit_work, lit_ref, lit_seq, doc_id, doc_ref, doc_seq, shared, jaccard, span_len, content_shared, lit_works, rule in pair_info:
        doc_bucket = doc_sidecars_by_pair_bucket.get(doc_id, '')
        restored = _pair_restored_flag(
            doc_sidecars_by_pair_bucket.get('__sidecars__', {}), doc_id, doc_ref, doc_bucket)
        rows.append((lit_work, lit_ref, lit_seq, doc_id, doc_bucket, doc_ref, doc_seq,
                     shared, jaccard, span_len, restored, content_shared, lit_works, rule))
    conn.executemany("INSERT INTO pairs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.executemany("INSERT INTO meta VALUES (?,?)",
                      [(k, '' if v is None else str(v)) for k, v in meta.items()])
    conn.execute("CREATE INDEX idx_pairs_lit ON pairs(lit_work, lit_ref)")
    conn.execute("CREATE INDEX idx_pairs_doc ON pairs(doc_id)")
    conn.commit()
    conn.close()


def make_quality_filter(args, doc_lines, lit_files, function_words):
    """quality_filter(resolved8) -> (verdicts, stats); verdicts[i] is
    (content_shared, fails_content, fails_run). Lemma lists for every
    candidate pair's two lines: document lines from doc_lines (in memory),
    literary lines by re-reading only the caches of works that appear in a
    pair."""
    def quality_filter(resolved):
        need_lit = defaultdict(set)
        need_doc = set()
        for lw, _lr, ls, di, _dr, ds, _sh, _j in resolved:
            need_lit[lw].add(ls)
            need_doc.add((di, ds))
        doc_lem = {}
        for u in doc_lines:
            key = (u['doc_id'], u['doc_seq'])
            if key in need_doc:
                toks = u['tokens']
                doc_lem[key] = u['lemmas'] if len(u['lemmas']) == len(toks) else toks
        lit_lem = {}
        saved = ((lit.TEXTS_DIR, lit.CACHE_DIR),
                 (lemma_cache_mod.TEXTS_DIR, lemma_cache_mod.CACHE_DIR))
        lit.TEXTS_DIR = lemma_cache_mod.TEXTS_DIR = args.literary_texts_root
        lit.CACHE_DIR = lemma_cache_mod.CACHE_DIR = args.literary_cache_root
        try:
            for fname in lit_files:
                base = fname[:-len('.tess')] if fname.endswith('.tess') else fname
                if base not in need_lit:
                    continue
                data = lit.get_cached_units(fname, args.language)
                if data is None:
                    continue
                wanted = need_lit[base]
                for seq, unit in enumerate(data.get('units_line', [])):
                    if seq in wanted:
                        lit_lem[(base, seq)] = lit._line_lemmas(unit)
                del data
        finally:
            (lit.TEXTS_DIR, lit.CACHE_DIR), (lemma_cache_mod.TEXTS_DIR, lemma_cache_mod.CACHE_DIR) = saved
        verdicts = []
        n_fail_c = n_fail_r = n_fail_both = n_no_lemmas = 0
        for lw, _lr, ls, di, _dr, ds, _sh, _j in resolved:
            ll, dl = lit_lem.get((lw, ls)), doc_lem.get((di, ds))
            if ll is None or dl is None:
                # Cannot test: keep the pair rather than silently drop it.
                n_no_lemmas += 1
                verdicts.append((None, False, False, None))
                continue
            n_content, _run, fc, fr = pair_quality(
                ll, dl, function_words, args.min_content_lemmas, args.min_run,
                language=args.language)
            n_fail_c += fc and not fr
            n_fail_r += fr and not fc
            n_fail_both += fc and fr
            verdicts.append((n_content, fc, fr,
                             shared_coverage(ll, dl, function_words, args.language)))
        stats = {
            'pairs_tested': len(resolved), 'function_words': len(function_words),
            'min_content_lemmas': args.min_content_lemmas, 'min_run': args.min_run,
            'removed_only_content_lemmas_below_min': int(n_fail_c),
            'removed_only_run_below_min': int(n_fail_r),
            'removed_both_conditions': int(n_fail_both),
            'removed_total': int(n_fail_c + n_fail_r + n_fail_both),
            'removed_by_content_condition': int(n_fail_c + n_fail_both),
            'removed_by_run_condition': int(n_fail_r + n_fail_both),
            'untestable_kept_unfiltered': n_no_lemmas,
        }
        return verdicts, stats
    return quality_filter


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
    ap.add_argument('--min-content-lemmas', type=int, default=2,
                    help='quality filter: minimum distinct shared non-function-word lemmas')
    ap.add_argument('--min-run', type=int, default=2,
                    help='quality filter: minimum longest contiguous run of shared lemmas')
    ap.add_argument('--no-quality-filter', action='store_true',
                    help='disable the quality filter (keeps the old noisy behaviour)')
    ap.add_argument('--max-literary-works', type=int, default=MAX_LITERARY_WORKS_DEFAULT,
                    help='drop a pair whose every non-formula shared n-gram occurs in more than N '
                         'distinct literary works (0 = off); see the module docstring')
    ap.add_argument('--sweep-max-works', default=None,
                    help='comma list of N values (e.g. 5,10,20,50): print pairs kept at each and exit '
                         'unless --out-db is also given; with --candidates-cache this takes seconds')
    ap.add_argument('--candidates-cache', default=None,
                    help='SQLite file: load the scanned candidates from it when it exists, save '
                         'them to it after the scan when it does not')
    ap.add_argument('--no-reorder', action='store_true',
                    help='disable the order-free (reorder) rule')
    ap.add_argument('--reorder-max-df', type=int, default=REORDER_MAX_DF_DEFAULT,
                    help='reorder rule: drop an order-free content-lemma set found in more than '
                         'this many lines of the two collections together')
    ap.add_argument('--out-db', default=None)
    ap.add_argument('--stats-out', default=None)
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    out_db = args.out_db or os.path.join(OUT_DIR, f'{args.language}_documents.db')
    stats_out = args.stats_out or os.path.join(OUT_DIR, f'{args.language}_documents_stats.json')
    sweep_values = [int(x) for x in args.sweep_max_works.split(',')] if args.sweep_max_works else []

    t_start = time.time()
    scan_params = {
        'language': args.language, 'max_df': args.max_df, 'min_shared': args.min_shared,
        'min_jaccard': args.min_jaccard, 'min_shared_override': args.min_shared_override,
        'min_containment': args.min_containment, 'rare_max_df': args.rare_max_df,
        'rare_min_containment': args.rare_min_containment,
        'min_content_lemmas': args.min_content_lemmas, 'min_run': args.min_run,
        'quality_filter': not args.no_quality_filter,
        'reorder': not args.no_reorder, 'reorder_max_df': args.reorder_max_df,
    }

    if args.candidates_cache and os.path.exists(args.candidates_cache):
        cands, verdicts, buckets, work_lines, cmeta = load_candidates_cache(args.candidates_cache)
        if cmeta.get('scan_params') != scan_params:
            raise SystemExit(f"{args.candidates_cache} was scanned with different parameters "
                              f"({cmeta.get('scan_params')}) than this run ({scan_params}); "
                              f"delete it to rescan")
        print(f"[build_documents_reuse_table] loaded {len(cands)} candidates from "
              f"{args.candidates_cache}", flush=True)
        index_stats = cmeta['index_stats']
        pair_stats = cmeta['pair_stats']
        quality_stats = cmeta['quality_stats']
        corpus_version, built_at = cmeta['corpus_version'], cmeta['built_at']
        n_doc_lines = cmeta['document_lines']
        n_lit_works = cmeta['literary_works']
        formula_words_count = cmeta['formula_words_count']
    else:
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
            lit_files, skipped_parts = lit.list_corpus_files(args.language)
        finally:
            lit.TEXTS_DIR, lit.CACHE_DIR = orig_lit
            lemma_cache_mod.TEXTS_DIR, lemma_cache_mod.CACHE_DIR = orig_lcm
        missing_cache = []
        loaded_works = []

        def iter_literary():
            # One work's cache in memory at a time (see build_combined_index).
            saved = ((lit.TEXTS_DIR, lit.CACHE_DIR),
                     (lemma_cache_mod.TEXTS_DIR, lemma_cache_mod.CACHE_DIR))
            lit.TEXTS_DIR = lemma_cache_mod.TEXTS_DIR = args.literary_texts_root
            lit.CACHE_DIR = lemma_cache_mod.CACHE_DIR = args.literary_cache_root
            try:
                for fname in lit_files:
                    cached = lit.get_cached_units(fname, args.language)
                    if cached is None:
                        missing_cache.append(fname)
                        continue
                    loaded_works.append(fname)
                    yield fname, cached
            finally:
                (lit.TEXTS_DIR, lit.CACHE_DIR), (lemma_cache_mod.TEXTS_DIR, lemma_cache_mod.CACHE_DIR) = saved

        print(f"[build_documents_reuse_table] {len(lit_files)} literary works to read "
              f"({len(skipped_parts)} .part. skipped)", flush=True)

        doc_lines, doc_lemma_counts = discover_documents(args.language, args.documents_index_dir)
        print(f"[build_documents_reuse_table] {len(doc_lines)} document lines, "
              f"{len(doc_lemma_counts)} lemmas with a document-frequency count")

        formula_words = load_formula_words(args.language)
        formula_words_count = len(formula_words)
        print(f"[build_documents_reuse_table] {len(formula_words)} formula words loaded "
              f"for '{args.language}'")

        function_words = load_function_words(args.language)
        tmp_dir = tempfile.mkdtemp(prefix=f'reuse_documents_{args.language}_')
        index_db_path = os.path.join(tmp_dir, f'{args.language}_index.db')
        try:
            index_stats, formula_hashes = build_combined_index(
                iter_literary(), doc_lines, index_db_path, args.max_df,
                formula_words, doc_lemma_counts, language=args.language,
                function_words=function_words, reorder=not args.no_reorder,
                reorder_max_df=args.reorder_max_df)

            cands, work_lines, pair_stats = find_candidates(
                index_db_path, args.min_shared, args.min_jaccard, args.min_shared_override,
                args.min_containment, args.rare_max_df, args.rare_min_containment, formula_hashes)
            quality_filter = None if args.no_quality_filter else make_quality_filter(
                args, doc_lines, lit_files, function_words)
            verdicts, quality_stats = annotate_quality(cands, quality_filter)
            print(f"[build_documents_reuse_table] {len(loaded_works)} literary works read, "
                  f"{len(missing_cache)} missing cache", flush=True)
            doc_id_to_bucket = {u['doc_id']: u['bucket'] for u in doc_lines}
            buckets = {c[3]: doc_id_to_bucket.get(c[3], '') for c in cands}
            corpus_version = lit.get_corpus_version(args.language)
            built_at = datetime.now(timezone.utc).isoformat()
            n_doc_lines = len(doc_lines)
            n_lit_works = len(loaded_works)
            if args.candidates_cache:
                save_candidates_cache(args.candidates_cache, cands, verdicts, buckets, work_lines, {
                    'scan_params': scan_params, 'index_stats': index_stats,
                    'pair_stats': pair_stats, 'quality_stats': quality_stats,
                    'corpus_version': corpus_version, 'built_at': built_at,
                    'document_lines': n_doc_lines, 'literary_works': n_lit_works,
                    'formula_words_count': formula_words_count})
                print(f"[build_documents_reuse_table] saved {len(cands)} candidates to "
                      f"{args.candidates_cache}", flush=True)
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    sweep = {}
    for n in sweep_values:
        kept = select_pairs(cands, verdicts, n)
        sweep[n] = len(kept)
        print(f"[build_documents_reuse_table] --max-literary-works {n}: {len(kept)} pairs kept",
              flush=True)
    if sweep_values:
        print(f"[build_documents_reuse_table] --max-literary-works off: "
              f"{len(select_pairs(cands, verdicts, 0))} pairs kept", flush=True)
        if not args.out_db:
            return

    pair_info = select_pairs(cands, verdicts, args.max_literary_works)
    n_reorder_kept = sum(1 for p in pair_info if p[11] == 'reorder')
    print(f"[build_documents_reuse_table] {len(pair_info)} pairs kept "
          f"(--max-literary-works {args.max_literary_works}; {n_reorder_kept} by the reorder rule)",
          flush=True)

    # Restored-word sidecars, loaded only for buckets a kept pair touches.
    buckets_needed = {buckets.get(p[3], '') for p in pair_info}
    sidecars = {b: load_sidecar(args.documents_sidecar_root, args.language, b)
                for b in buckets_needed if b}
    bucket_map = dict(buckets)
    bucket_map['__sidecars__'] = sidecars

    meta = {
        'built_at': built_at, 'corpus_version': corpus_version,
        'language': args.language,
        'literary_works': n_lit_works, 'document_lines': n_doc_lines,
        'max_df': args.max_df, 'min_shared': args.min_shared,
        'min_jaccard': args.min_jaccard, 'min_shared_override': args.min_shared_override,
        'min_containment': args.min_containment, 'rare_max_df': args.rare_max_df,
        'rare_min_containment': args.rare_min_containment,
        'document_formula_max_docs': DOCUMENT_FORMULA_MAX_DOCS,
        'formula_words_count': formula_words_count,
        'formula_ngrams': index_stats['formula_ngrams'],
        'max_literary_works': args.max_literary_works,
        'reorder': 'off' if args.no_reorder else f'on,max_df={args.reorder_max_df}',
        'pairs_kept': len(pair_info),
        'pairs_before_quality_filter': len(cands),
        'quality_filter': 'off' if args.no_quality_filter else (
            f'content>={args.min_content_lemmas},run>={args.min_run}'),
    }
    write_output_db(out_db, pair_info, bucket_map, meta)

    elapsed = time.time() - t_start
    per_work = per_work_report(pair_info, work_lines)
    by_rate = sorted(((w, d) for w, d in per_work.items() if d['lines'] >= 1000),
                     key=lambda x: -(x[1]['pairs_per_1000_lines'] or 0))[:30]
    stats = {**index_stats, **pair_stats, 'pairs_kept': len(pair_info),
             'pairs_kept_reorder_rule': n_reorder_kept,
             'max_literary_works': args.max_literary_works,
             'sweep_max_literary_works': sweep,
             'quality_filter': quality_stats,
             'top_works_by_pairs': sorted(per_work.items(), key=lambda x: -x[1]['pairs'])[:30],
             'top_works_by_pairs_per_1000_lines_min1000_lines': by_rate,
             'per_work': per_work,
             'total_elapsed_seconds': elapsed, 'out_db': out_db,
             'corpus_version': corpus_version, 'built_at': built_at}
    with open(stats_out, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"[build_documents_reuse_table] done in {elapsed:.1f}s. DB: {out_db}")
    print(json.dumps({k: v for k, v in stats.items()
                      if k not in ('per_work', 'top_works_by_pairs',
                                   'top_works_by_pairs_per_1000_lines_min1000_lines')}, indent=2))


if __name__ == '__main__':
    main()
