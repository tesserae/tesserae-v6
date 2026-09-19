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
       OR shared == 1 and that n-gram's corpus-wide line-df < --rare-max-df
          and containment >= --rare-min-containment
     where containment = shared / min(ngrams_a, ngrams_b) (the fraction of
     the SHORTER line's surviving n-grams the match accounts for -- this
     replaced a raw shared-count-only override that let long, unrelated
     prose paragraphs through on a handful of coincidental function-word
     n-grams; see REPORT_2026-09-18.md "Follow-up: the prose length fix").
     The third rule (added 2026-09-19, see find_pairs's docstring for the
     full investigation) recovers a short, isolated quotation -- as little
     as three words -- that shares only one n-gram with its source and so
     never reaches --min-shared, PROVIDED that one n-gram is corpus-rare
     AND containment clears a much lower floor than the main override's
     0.5 (default 0.06). Banality (step 4) turned out not to be why famous
     openings like Vergil's "arma virumque cano" were under-detected:
     measured against the live corpus, none of that line's sixteen n-grams
     reach anywhere near --max-df=200 (worst case, 9 lines). The real gap
     was min-shared -- and rarity alone, with no containment floor, floods
     (6.4M pairs on the live corpus; see find_pairs's docstring for the
     measurement that walked this back to a containment floor instead).
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
import unicodedata
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
# gen_ngram_indices/gen_ngrams moved to backend/ngram_utils.py (2026-09-19)
# so backend/reuse_table.py can reconstruct the SAME word-triples at read
# time, to bold shared words in the Reader's Reuse tab, without
# reimplementing (and risking drifting from) this exact window definition.
from backend.ngram_utils import gen_ngram_indices, gen_ngrams  # noqa: E402


def hash_ngram(tokens):
    """Hash a tuple of tokens to a signed 64-bit int (SQLite INTEGER is signed
    64-bit, so the blake2b digest's top bit is kept as sign, not truncated)."""
    joined = '\x1f'.join(tokens).encode('utf-8')
    digest = hashlib.blake2b(joined, digest_size=8).digest()
    return int.from_bytes(digest, 'big', signed=True)


def _line_lemmas(unit):
    """A unit's lemmas, positionally aligned with its tokens -- or the
    tokens themselves when there is no lemmas array, or it doesn't match
    the tokens array in length (a stale or partial cache entry): treating
    each surface form as its own "lemma" in that fallback case is exactly
    the old, less accurate behavior, not a crash or a silently wrong
    alignment."""
    tokens = unit.get('tokens') or []
    lemmas = unit.get('lemmas')
    if not lemmas or len(lemmas) != len(tokens):
        return tokens
    return lemmas


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


def _repair_surrogates(text, fallback):
    """(text with any surrogate-escaped bytes decoded back to UTF-8, changed?).
    A lone surrogate that is not a surrogateescape byte falls back to
    `fallback` (or is replaced) rather than crashing the build."""
    if not isinstance(text, str) or not any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
        return text, False
    try:
        return text.encode('utf-8', 'surrogateescape').decode('utf-8'), True
    except UnicodeError:
        return (fallback or text.encode('utf-8', 'replace').decode('utf-8')), True


def _stopset_for(language):
    """Function words for `language` from the backend's cross-lingual
    stoplists (backend/synonym_dict.py), lowercase and accent-stripped, or an
    empty set for a language without one. Used alongside the data-driven
    commonplace threshold: on the English corpus that threshold (8% of the
    top lemma's line-df) missed "shall" and "do", so Hamlet's "What shall I
    do?" still came out quoted by Bunyan's "what shall I do?" (2026-09-19)."""
    try:
        from backend import synonym_dict as sd
    except Exception:  # noqa: BLE001 - the builder must still run without the web app's deps
        return frozenset()
    raw = {
        'la': getattr(sd, 'CROSSLINGUAL_STOPLIST_LATIN', set()),
        'grc': getattr(sd, 'CROSSLINGUAL_STOPLIST_GREEK', set()),
        'en': getattr(sd, 'CROSSLINGUAL_STOPLIST_ENGLISH', set()),
    }.get(language, set())
    return frozenset(_fold(w) for w in raw)


def _fold(token):
    """Lowercase, accents and combining marks removed, u/v and j/i folded (Latin
    orthography), so a stoplist entry matches however the cache spells it."""
    t = unicodedata.normalize('NFD', str(token).lower())
    t = ''.join(ch for ch in t if not unicodedata.combining(ch))
    return t.replace('v', 'u').replace('j', 'i')


def build_index(cache_data, index_db_path, max_df, commonplace_ratio=0.08, language=None):
    """Stage 1: stream per-line n-grams from cache_data (already-loaded,
    already-validated {tess_basename: cache_dict}, from discover_corpus)
    into a temporary SQLite index DB (lines, postings after banality
    filtering). Returns (stats, commonplace_hashes). Mirrors
    research/reuse_table/build_reuse_index.py.

    commonplace_hashes: the set of n-gram hashes composed ENTIRELY of
    commonplace LEMMAS -- a lemma whose own corpus-wide line-df is at least
    `commonplace_ratio` of the most frequent lemma's df (the same
    ratio-of-max-df design backend/app.py's rare_focus_filter already uses,
    RARE_FOCUS_COMMON_RATIO=0.45 there for a different purpose and scale;
    0.08 is what a 2026-09-19 measurement against the live corpus found --
    see below). find_pairs uses this to keep the rare-single-ngram rule
    (see its own docstring) from passing a trigram that is corpus-rare only
    as a specific ORDERED combination of otherwise ordinary words --
    ('ut', 'in', 'ista'), ('cum', 'in', 'ius'), ('et', 'qua', 'tibi') and
    the like, which is what most of a first 30-pair sample turned out to be
    even after adding a containment floor: individually common words
    rarely co-occur in this exact trigram shape, so the SHAPE is rare even
    though nothing about the words is. A genuine echo -- "ad sidera
    palmas", "iste dei sanctus", "magna de stirpe" -- has at least one word
    distinctive enough on its own to be memorable, which is what this
    excludes-if-none-are-distinctive test asks for directly.

    LEMMAS, NOT SURFACE TOKENS, because Latin's inflection spreads one
    ordinary word over many surface forms, each individually rarer than
    the word actually is -- "amat" (768 lines) looks almost as rare as a
    genuinely distinctive word by raw surface count, but its lemma "amo"
    is unremarkable (5237). A first attempt used surface-token df and
    found no threshold worked: low enough to catch the commonplace-only
    false positives in the 30-pair sample also caught genuine echoes
    ("ad sidera palmas" has surface df low enough to look rare), and high
    enough to spare them caught almost nothing. Lemma df fixed this: at
    ratio 0.08 every genuine echo in that sample survived (none of its
    three lemmas individually exceeded the threshold) while 9 of the
    remaining 21 commonplace-word matches were correctly excluded. Falls
    back to the surface token itself when a unit has no lemmas array (or a
    misaligned one), which only affects languages/caches predating
    lemmatization."""
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
    n_ids_repaired = 0
    # Corpus-wide line-document-frequency per LEMMA (once per line it
    # appears in, not per raw occurrence) -- cheap: Latin's lemma
    # vocabulary is in the tens of thousands, nowhere near the n-gram
    # count, so this dict stays small next to postings_raw. See the
    # docstring above for why lemmas rather than surface tokens.
    lemma_df = defaultdict(int)

    for tess_basename, data in cache_data.items():
        work_id = data.get('text_id', tess_basename)
        # Some Greek lemma caches were written under an ASCII locale, so a
        # Greek file name sits in text_id as surrogate-escaped bytes; SQLite
        # refuses to store those ("surrogates not allowed", 2026-09-19).
        # Re-encoding with surrogateescape recovers the real UTF-8 name.
        work_id, fixed = _repair_surrogates(work_id, tess_basename)
        if fixed:
            n_ids_repaired += 1
        if work_id.endswith('.tess'):
            work_id = work_id[:-len('.tess')]
        units = data.get('units_line', [])
        if not units:
            continue
        works_indexed += 1
        for seq, unit in enumerate(units):
            tokens = unit.get('tokens') or []
            lemmas = _line_lemmas(unit)
            ref, _ = _repair_surrogates(unit.get('ref', ''), '')
            n_lines_seen += 1
            for lem in set(lemmas):
                lemma_df[lem] += 1
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

    if n_ids_repaired:
        print(f"[build_reuse_table] index: {n_ids_repaired} work id(s) carried surrogate-escaped "
              f"bytes in their lemma cache text_id and were decoded back to UTF-8")
    print(f"[build_reuse_table] index: {n_lines_seen} lines read from {works_indexed} works "
          f"({n_lines_too_short} lines under 3 tokens, kept with no n-grams), "
          f"{n_gram_instances} n-gram instances, elapsed {time.time()-t0:.1f}s")

    # Which n-grams are commonplace-LEMMA-only: a second, in-memory-only
    # pass (cache_data is already loaded; no re-reading from disk) now that
    # lemma_df's totals -- and so the commonplace threshold -- are known.
    # Kept as a Python set of hashes (keyed on the SURFACE n-gram, since
    # that is what postings/pair_hits key on): bounded by the lemma
    # vocabulary's combinatorics, not by postings_raw's size, so nowhere
    # near the scale that forced pair_hits onto disk (see find_pairs's
    # docstring).
    max_lemma_df = max(lemma_df.values()) if lemma_df else 0
    commonplace_threshold = max_lemma_df * commonplace_ratio
    stopset = _stopset_for(language)
    n_stoplist_only = 0

    def _commonplace(lem, tok):
        return (lemma_df.get(lem, 0) >= commonplace_threshold
                or _fold(lem) in stopset or _fold(tok) in stopset)

    commonplace_hashes = set()
    for tess_basename, data in cache_data.items():
        for unit in data.get('units_line', []):
            tokens = unit.get('tokens') or []
            if len(tokens) < 3:
                continue
            lemmas = _line_lemmas(unit)
            for idxs in gen_ngram_indices(len(tokens)):
                lemma_gram = tuple(lemmas[i] for i in idxs)
                token_gram = tuple(tokens[i] for i in idxs)
                if all(_commonplace(lem, tok) for lem, tok in zip(lemma_gram, token_gram)):
                    h = hash_ngram(token_gram)
                    if h not in commonplace_hashes and not all(
                            lemma_df.get(lem, 0) >= commonplace_threshold for lem in lemma_gram):
                        n_stoplist_only += 1
                    commonplace_hashes.add(h)
    print(f"[build_reuse_table] index: {len(lemma_df)} distinct lemmas, "
          f"commonplace threshold {commonplace_threshold:.0f} (of max lemma df {max_lemma_df}), "
          f"{len(commonplace_hashes)} n-grams are commonplace-word-only "
          f"({n_stoplist_only} of them only because of the {language or 'no'} stoplist, "
          f"{len(stopset)} entries), elapsed {time.time()-t0:.1f}s")

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
    stats = {
        'works_indexed': works_indexed,
        'lines_indexed': n_lines_seen,
        'lines_under_3_tokens': n_lines_too_short,
        'distinct_ngrams_total': distinct_ngrams_total,
        'ngrams_kept': n_ngrams_kept,
        'ngrams_dropped_banal_over_max_df': n_ngrams_dropped_banal,
        'postings_written': n_postings_written,
        'distinct_lemmas': len(lemma_df),
        'commonplace_ngrams': len(commonplace_hashes),
        'index_elapsed_seconds': elapsed,
    }
    return stats, commonplace_hashes


def find_pairs(index_db_path, min_shared, min_jaccard, min_shared_override, min_containment,
               rare_max_df=20, rare_min_containment=0.06, commonplace_hashes=None):
    """Stage 2: stream postings ordered by ngram_hash, accumulate cross-work
    shared-ngram counts, score by jaccard/containment, chain adjacent kept
    pairs into spans. Returns (pair_info, line_to_other_works, stats).
    Mirrors research/reuse_table/find_reuse_pairs.py.

    A THIRD keep rule, alongside the jaccard rule and the containment
    override (see the module docstring's item 5): a pair sharing exactly
    ONE n-gram is kept anyway if that n-gram is rare corpus-wide (line-df
    under `rare_max_df`) AND containment is at least `rare_min_containment`
    (a much lower floor than the main override's 0.5). Investigating why
    only Quintilian and Geoffrey of Vinsauf showed up as reusing "arma
    virumque cano" (Aen. 1.1) found that banality was not the obstacle --
    none of that line's sixteen n-grams even approach the max-df=200 cutoff
    (worst case 9 lines corpus-wide; see research notes for the
    measurement). The obstacle was min_shared: a short, isolated quotation
    embedded in an otherwise unrelated line (Seneca, Ep. 113.25, quoting
    only the three words "arma virumque cano" inside a long sentence about
    grammar) shares exactly one n-gram with Aen. 1.1 and so never reached
    the shared>=2 floor.

    RARITY ALONE FLOODS. A first version dropped the containment check
    entirely (reasoning that Aen. 1.1's containment against Seneca's line
    is only shared/min(16,205)=0.0625, so no meaningful floor could pass
    genuine short quotations without a low bar). Built against the full
    Latin corpus, "rare, shared==1, no containment check" kept 6.4 MILLION
    pairs, essentially flooding: a random 30-pair sample (seed 43) was
    almost entirely unrelated prose paragraphs -- e.g. Cicero De Oratore
    and Columella De Re Rustica, containment 0.008 -- that happen to share
    one obscure trigram purely by the corpus's combinatorial size (36M
    distinct n-grams over 652K lines). The fix is not to drop containment
    but to lower its floor drastically instead of dropping it: containment
    is pinned to the SHORTER side, so it stays informative exactly when one
    line of the pair is short (a verse line, typically 13-16 n-grams here)
    -- which is what a famous short quotation embedded in a longer work
    looks like, and what a coincidental overlap between two long prose
    paragraphs does NOT look like (median containment among the flooded
    sample was ~0.005, an order of magnitude under Seneca's 0.0625). At
    rare_min_containment=0.06 (just under Seneca's own value, so the
    motivating case still passes) this rule keeps ~474K pairs instead of
    6.4M.

    CONTAINMENT ALONE STILL ISN'T ENOUGH. A fresh 30-pair sample (seed 43)
    of THAT set was better but still mostly noise -- roughly two-thirds
    read as coincidental, e.g. ('ut','in','ista'), ('cum','in','ius'),
    ('et','qua','tibi'): a SPECIFIC ORDERED triple of otherwise ordinary
    words can easily be corpus-rare (this exact shape just doesn't come up
    often) without the match meaning anything, since none of the three
    words is itself distinctive. The genuine hits in that sample -- "ad
    sidera palmas" (Ovid/Valerius Flaccus), "iste dei sanctus" (Alcuin/
    Walahfrid Strabo), "magna de stirpe" (an anonymous satirist echoing
    Vergil, quoted by Suetonius), "pusillanimitate spiritus" (Jerome
    quoting his own Vulgate) -- all share at least one word that is
    unusual on its own, not just in this combination. `commonplace_hashes`
    (from build_index, see its own docstring) is exactly this test: an
    n-gram in that set has EVERY token individually common, so the
    rare-single-ngram rule below also excludes it regardless of how rare
    the 3-word shape happens to be. On the live corpus this cut the rule's
    yield from 473K to 286K pairs (188K more excluded as commonplace-word
    matches that would otherwise have qualified).

    WHAT THIS RULE DOES AND DOES NOT ACHIEVE. On the motivating case it
    works cleanly: Aen. 1.1 now shows 7 works reusing it (Geoffrey of
    Vinsauf, Quintilian, Seneca, Valerius Flaccus twice, Claudian,
    Salutati -- all independently plausible: Valerius Flaccus and Claudian
    are both extensively documented Vergil-imitators, and Salutati's line
    is a literal gloss on "arma virumque cano" itself), up from 2. But a
    fresh corpus-wide 30-pair sample (seed 43) of the rule's full yield
    after both filters still reads as roughly a quarter to a third
    genuine (epic-formula echoes like "ab extremo aquilone" shared by
    Lucan and Pliny, "luci sociata perenni" linking Alcuin to his
    Carolingian-era predecessor Venantius Fortunatus) against a majority
    of generic, low-content phrases whose rarity is still just
    combinatorial accident -- a single 3-word match, however filtered,
    remains inherently weaker evidence than two or more, and no
    frequency-based filter fully closes that gap. This is the same
    tradeoff CLAUDE.md already documents for the fusion channel
    lemma_min1 ("high recall, noisy, catch-all"): the rule earns its
    place by recovering real cases the stricter rules miss entirely, not
    by matching their precision. A future pass could restrict it further
    (e.g. requiring the other work's author to postdate the quoted line,
    or having the Reader label a shared==1 match differently from a
    shared>=2 one) rather than tightening the frequency thresholds again,
    which has diminishing returns past this point -- pure rarity, then
    rarity+containment, then rarity+containment+commonplace-word
    exclusion were tried in that order to reach this version.

    CANDIDATE PAIRS ARE ACCUMULATED IN SQLITE, NOT A PYTHON DICT. The first
    version of the rare-single-ngram rule kept the existing `overlap =
    defaultdict(int)` (already ~28M entries keyed by (line_id, line_id)
    tuples on the full Latin corpus) and added a second, same-sized dict
    tracking each pair's rarest shared n-gram's df. That doubled the memory
    this stage held resident and got the run OOM-killed under a 12G cap at
    00:28 on 2026-09-19 (previously ~10G without the second dict). Both the
    count AND the rarest-df are now one SQL query (COUNT(*), MIN(group_size)
    ... GROUP BY a, b) against a `pair_hits` table streamed to disk in
    batches during the same postings scan -- the identical fix build_index
    already applies to n-gram document frequency, and for the identical
    reason (see that function's own comment)."""
    t0 = time.time()
    conn = sqlite3.connect(index_db_path)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA temp_store = FILE")
    cur = conn.cursor()

    line_meta = {}
    line_base = {}
    for line_id, work, ref, token_count, seq in cur.execute(
            "SELECT line_id, work, line_ref, token_count, seq_in_work FROM lines"):
        line_meta[line_id] = (work, ref, seq)
        # Part files of one work (spenser.faerie_queene.part.4 and .part.6,
        # indexed separately when no whole file exists) are the SAME work for
        # the purpose of "quoted in another work": the English table (2026-09-19)
        # was full of the Faerie Queene repeating its own formulas across parts.
        line_base[line_id] = work.split('.part.')[0] if '.part.' in work else work
    n_lines = len(line_meta)
    print(f"[build_reuse_table] pairs: {n_lines} lines loaded, elapsed {time.time()-t0:.1f}s")

    line_ngram_count = defaultdict(int)

    # Every (a, b, group_size, ngram_hash) row a co-occurring ngram-group
    # contributes, written to disk in batches rather than aggregated in
    # memory. group_size is that n-gram's own corpus-wide line-df (<=200,
    # since postings is already banality-filtered), which the closing
    # GROUP BY turns into the rarest-shared-ngram-df each pair needs for
    # the rare-single-ngram rule; ngram_hash lets that rule also check
    # commonplace_hashes for a shared==1 pair's one contributing n-gram
    # (MIN(ngram_hash) in a single-row group is just that row's hash).
    conn.execute("CREATE TABLE pair_hits (a INTEGER, b INTEGER, group_size INTEGER, ngram_hash INTEGER)")
    commonplace_hashes = commonplace_hashes or frozenset()
    n_commonplace_groups_skipped = 0
    hit_batch = []
    HIT_BATCH = 500000
    current_hash = None
    current_lines = []
    n_ngrams_processed = 0
    n_pair_increments = 0

    def flush_hits():
        nonlocal hit_batch
        if hit_batch:
            conn.executemany("INSERT INTO pair_hits VALUES (?,?,?,?)", hit_batch)
            hit_batch = []

    def flush_group(lines_in_group):
        nonlocal n_pair_increments, n_commonplace_groups_skipped
        # An n-gram made only of commonplace words ("what shall i do", "et in
        # illo") is evidence of nothing: it used to count toward the strict
        # rules and the n-gram totals, so Hamlet III.4.192 came out "quoted"
        # by eight Bible verses (English table, 2026-09-19). Such n-grams now
        # count for no rule and for neither line's total, so a line of pure
        # function words has no n-grams at all rather than a few worthless ones.
        if current_hash in commonplace_hashes:
            n_commonplace_groups_skipped += 1
            return
        L = len(lines_in_group)
        for lid in lines_in_group:
            line_ngram_count[lid] += 1
        if L < 2:
            return
        for i in range(L):
            wi = line_base[lines_in_group[i]]
            for j in range(i + 1, L):
                a, b = lines_in_group[i], lines_in_group[j]
                if line_base[b] == wi:
                    continue
                if a > b:
                    a, b = b, a
                hit_batch.append((a, b, L, current_hash))
                n_pair_increments += 1
                if len(hit_batch) >= HIT_BATCH:
                    flush_hits()

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
    flush_hits()
    conn.commit()

    print(f"[build_reuse_table] pairs: {n_ngrams_processed} n-grams scanned "
          f"({n_commonplace_groups_skipped} commonplace-word-only n-grams counted for nothing), "
          f"{n_pair_increments} pair-occurrences written, elapsed {time.time()-t0:.1f}s")

    print("[build_reuse_table] pairs: aggregating candidate pairs (SQL GROUP BY, not a Python dict)...")
    conn.execute("CREATE INDEX idx_pair_hits_ab ON pair_hits(a, b)")
    conn.commit()

    commonplace_hashes = commonplace_hashes or frozenset()
    kept = []
    n_excluded_by_raw_override = 0
    n_kept_via_rare_single = 0
    n_excluded_commonplace_rare = 0
    n_candidate_pairs = 0
    for a, b, shared, min_gdf, single_ngram_hash in conn.execute(
            "SELECT a, b, COUNT(*), MIN(group_size), MIN(ngram_hash) FROM pair_hits GROUP BY a, b"):
        n_candidate_pairs += 1
        na = line_ngram_count[a]
        nb = line_ngram_count[b]
        union = na + nb - shared
        jaccard = shared / union if union > 0 else 0.0
        min_ngrams = min(na, nb)
        containment = shared / min_ngrams if min_ngrams > 0 else 0.0
        meets_jaccard = shared >= min_shared and jaccard >= min_jaccard
        meets_containment_override = shared >= min_shared_override and containment >= min_containment
        # MIN(ngram_hash) over a shared==1 group is exactly that one row's
        # hash (there is only one row), so this is the single contributing
        # n-gram -- checked against commonplace_hashes (see this function's
        # and build_index's docstrings) so a corpus-rare SHAPE built from
        # otherwise ordinary words does not pass on rarity alone.
        meets_rare_single = (
            bool(rare_max_df) and shared == 1 and min_gdf < rare_max_df
            and containment >= rare_min_containment
        )
        if meets_rare_single and single_ngram_hash in commonplace_hashes:
            meets_rare_single = False
            n_excluded_commonplace_rare += 1
        if shared >= min_shared_override and not meets_jaccard and not meets_containment_override:
            n_excluded_by_raw_override += 1
        if meets_jaccard or meets_containment_override or meets_rare_single:
            if meets_rare_single and not meets_jaccard and not meets_containment_override:
                n_kept_via_rare_single += 1
            kept.append((a, b, shared, jaccard))

    conn.execute("DROP TABLE pair_hits")
    conn.commit()

    print(f"[build_reuse_table] pairs: {n_candidate_pairs} candidate cross-work line pairs, "
          f"{len(kept)} pairs kept after threshold "
          f"({n_excluded_by_raw_override} excluded by the containment gate: "
          f"shared>={min_shared_override} but containment<{min_containment} and jaccard<{min_jaccard}; "
          f"{n_kept_via_rare_single} kept via the rare-single-ngram rule (shared==1, line-df<"
          f"{rare_max_df}, containment>={rare_min_containment}); {n_excluded_commonplace_rare} more "
          f"would have qualified for that rule but were excluded as commonplace-word-only), "
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
        'candidate_cross_work_pairs': n_candidate_pairs,
        'pairs_kept': len(pair_info),
        'candidates_excluded_by_containment_gate': n_excluded_by_raw_override,
        'pairs_kept_via_rare_single_ngram': n_kept_via_rare_single,
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
    ap.add_argument('--rare-max-df', type=int, default=20,
                     help='keep a pair sharing exactly one n-gram if that n-gram\'s corpus-wide '
                          'line-df is under this AND containment >= --rare-min-containment (a '
                          'short, isolated quotation of a famous line, e.g. "arma virumque cano" '
                          'alone inside an unrelated sentence, shares only one n-gram with its '
                          'source and never reaches --min-shared); pass 0 to disable this rule')
    ap.add_argument('--rare-min-containment', type=float, default=0.06,
                     help='containment floor for the rare-single-ngram rule above -- much lower '
                          'than --min-containment because containment is pinned to the shorter '
                          'line, and a short famous line quoted in a much longer one has a low '
                          'containment no matter how genuine the match (0.0625 for Aen. 1.1 '
                          'against Seneca Ep. 113.25); rarity alone with no containment floor '
                          'floods (measured 6.4M pairs on the live Latin corpus, see find_pairs)')
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
        index_stats, commonplace_hashes = build_index(cache_data, index_db_path, args.max_df,
                                                      language=args.language)
        pair_info, line_to_other_works, pair_stats = find_pairs(
            index_db_path, args.min_shared, args.min_jaccard,
            args.min_shared_override, args.min_containment, args.rare_max_df,
            args.rare_min_containment, commonplace_hashes)

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
            'rare_max_df': args.rare_max_df,
            'rare_min_containment': args.rare_min_containment,
            'commonplace_ngrams': index_stats['commonplace_ngrams'],
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
