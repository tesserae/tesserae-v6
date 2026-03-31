"""
Tesserae V6 — Fusion Search Engine (Config K, Feb 28 2026)

Implements multi-channel weighted score fusion with a two-pass
line/window architecture for intertext detection.

Architecture
------------
The search operates in two passes over each text pair:

  Pass 1 — Line-level: All 9 channels run on individual verse lines.
      This is the primary search, providing full 9-channel coverage.

  Pass 2 — Window-level: A subset of channels (lemma, lemma_min1,
      rare_word, dictionary) run on sliding windows of 2 consecutive
      lines, capturing enjambed allusions split across line breaks.

Channel taxonomy
----------------
Channels are classified by the *level of linguistic representation*
at which they operate, which determines their behavior under windowing:

  LEXICAL channels (lemma, exact, rare_word, lemma_min1) match on the
  identity of word forms or lemmata.

  SUB-LEXICAL channels (edit_distance, sound) match on character-level
  similarity (Levenshtein distance, trigram overlap).

  DISTRIBUTIONAL channels (semantic, dictionary) match on vector
  similarity or curated synonym pairs.

  STRUCTURAL channels (syntax) match on dependency-tree patterns.

Scoring — Three-layer rarity system
------------------------------------
  base = sum(channel_score_i * weight_i)
  fused = base * mult^2 + conv * mult^conv_power

Layer 1 — Base score penalty (mult^2):
  mult = piecewise_linear(geom_mean_idf, idf_floor, idf_threshold)
  Applied as mult^2 to the base score. Common-word pairs get heavily
  penalized (e.g., geom_idf=0.36 → mult=0.33 → mult^2=0.11).

Layer 2 — IDF-weighted convergence:
  Each channel's convergence contribution is weighted by
  min(1.0, geom_mean_idf)^2, preventing common-word pairs from
  accumulating large bonuses despite matching on many channels.

Layer 3 — Rarity boost for rare multi-channel matches:
  When geom_idf exceeds the threshold, mult rises above 1.0 via a
  log curve, scaled by min(channel_factor, word_factor). Requires
  both multiple channels AND multiple distinct words for a boost.

The geometric mean IDF is computed from corpus-wide document frequencies
(1,429 Latin texts), with surface-form deduplication by (source_word,
target_word) to prevent inflected forms from inflating the mean.

Channel weights are from Config K (grid-search optimized, Feb 28 2026).
"""

import json
import math
import os
import re
import sqlite3
from collections import Counter, defaultdict

import numpy as np

from backend.logging_config import get_logger
from backend.matcher import DEFAULT_LATIN_STOP_WORDS, DEFAULT_GREEK_STOP_WORDS, DEFAULT_ENGLISH_STOP_WORDS

logger = get_logger('fusion')

# Stoplist lookup by language code
_STOPLISTS = {
    'la': DEFAULT_LATIN_STOP_WORDS,
    'grc': DEFAULT_GREEK_STOP_WORDS,
    'en': DEFAULT_ENGLISH_STOP_WORDS,
}


# ---------------------------------------------------------------------------
# Config K channel weights (Feb 28 2026)
#
# These weights were determined by grid-search optimization across Configs
# A through K, evaluated on 5 Latin benchmarks (862 gold-standard parallels).
# The optimizer (evaluation/scripts/run_weight_optimization.py v8) swept
# 34,992 weight combinations and 180 IDF curve parameter sets at each stage.
#
# Three-layer rarity scoring system
# ----------------------------------
# The scoring formula applies three independent mechanisms to suppress
# common-word noise while preserving (and boosting) rare-word matches.
# All three layers use the same geometric mean corpus-IDF as input.
#
# Layer 1 — Base score penalty (mult^2):
#   The raw weighted sum is multiplied by mult^2, where mult is a piecewise
#   linear function from idf_floor (0.2) at geom_idf < 0.1 to 1.0 at the
#   threshold (1.5). Common-word pairs are heavily penalized: a pair with
#   geom_idf=0.36 (e.g. "tum vero") gets mult=0.33, so mult^2=0.11 — an
#   89% reduction. Pairs with geom_idf >= threshold are unpenalized (1.0).
#
# Layer 2 — IDF-weighted convergence:
#   Each channel's contribution to the convergence bonus is scaled by
#   min(1.0, geom_mean_idf)^2 instead of counting as a flat 1.0. This
#   prevents common-word pairs that happen to match on many channels from
#   accumulating large bonuses: "tum vero" matching on 6 channels gets
#   weighted_n = 6 * 0.13 = 0.78, yielding zero convergence bonus (needs
#   weighted_n > 1.0). Distinctive pairs like "centum angues" with
#   geom_idf > 1.0 are unaffected (capped at 1.0 per channel).
#
# Layer 3 — Rarity boost for multi-channel rare matches:
#   When geom_idf exceeds the threshold, the multiplier rises above 1.0
#   via a log curve: 1.0 + boost_weight * channel_factor * log(geom_idf /
#   threshold), capped at boost_cap (2.0). The channel_factor is
#   (n_scoring_channels - 1) / 5, so single-channel noise (n=1, factor=0)
#   gets no boost — only multi-channel convergence on rare vocabulary is
#   promoted. This rewards the most distinctive, well-attested allusions.
#
# Combined effect on key test cases (from optimizer evaluation):
#   "tum vero"       (common): geom_idf=0.36, rank went from #37 to #903
#   "centum angues"  (rare):   geom_idf>3.0,  stable at #4
#   "Acheronta movebo" (rare): stable at #10
#   Top 100: 0% common-word matches; function-word noise eliminated.
#   Total recall: 784/862 (91.0%, unchanged by rarity scoring).
# ---------------------------------------------------------------------------
CHANNEL_WEIGHTS = {
    "edit_distance": 2.0,   # sub-lexical: Levenshtein fuzzy match
    "sound": 5.0,           # sub-lexical: character trigram overlap (LLM analysis: 1.74× lift
                            #   for A/B quality — best single-channel predictor after rare_word)
    "exact": 0.5,           # lexical: identical surface forms (LLM: only 1.08× lift, demoted)
    "lemma": 2.0,           # lexical: shared dictionary headwords (core V3-style matching)
    "dictionary": 0.10,     # distributional: curated V3 synonym pairs (LLM: 0.86× lift —
                            #   predicts noise; value is only as convergence evidence)
    "semantic": 1.0,        # distributional: SPhilBERTa cosine similarity (LLM: 1.30× lift)
    "rare_word": 7.0,       # lexical: shared low-frequency lemmata (LLM analysis: 1.94× lift —
                            #   strongest quality predictor; rare_word+sound = 68% A/B precision)
    "syntax": 0.3,          # structural: dependency pattern match (low — supplements other
                            #   channels but unreliable as primary signal)
    "syntax_structural": 0.5,  # structural: identical dependency head pattern with no shared
                            #   lemmas (low alone — too many false positives from common
                            #   syntactic patterns; rises when semantic recovery adds 2nd channel)
    "lemma_min1": 0.3,      # lexical: single shared lemma (low — very high recall, very
                            #   noisy; serves as a catch-all for otherwise missed pairs)
}

# Bonus added for each additional channel beyond the first that confirms
# a pair, rewarding cross-channel convergence as evidence of a true allusion.
# The raw bonus per extra channel is 0.75 * idf_weight, where idf_weight
# is min(1.0, geom_mean_idf)^2 (Layer 2). With squared IDF weighting,
# 0.75 is safe: even 8 extra channels on a common-word pair contribute
# little (0.75 * 8 * 0.13 = 0.78), while 4 extra channels on a distinctive
# pair contribute 0.75 * 4 * 1.0 = 3.0 — a meaningful boost.
CONVERGENCE_BONUS = 1.0   # LLM analysis: channel count ≥6 = 57-71% A/B precision; raised from 0.75

# Step bonus for high channel convergence (LLM analysis: AB precision jumps
# from 34% at 5 channels to 57% at 6 channels — a dramatic quality cliff).
HIGH_CONVERGENCE_THRESHOLD = 6      # channel count threshold for step bonus
HIGH_CONVERGENCE_BONUS = 1.0        # additive bonus when threshold met

# Interaction bonus when rare_word + sound both fire (LLM analysis: 68% AB
# precision when both present, vs 40% for rare_word alone).
RARE_SOUND_INTERACTION_BONUS = 1.5  # additive bonus for rare_word + sound synergy

# ---------------------------------------------------------------------------
# Rarity scoring parameters: graduated corpus-IDF multiplier
# ---------------------------------------------------------------------------
# The rarity multiplier uses the GEOMETRIC mean of corpus-wide IDF values
# for matched lemmas. Geometric mean penalizes pairs where even ONE word
# is ultra-common: "sum" (idf=0.007) + "locus" (idf=3.0) → geom=0.15
# (penalized) vs arithmetic mean=1.50 (not penalized). This is critical
# because function words like "est", "et", "in" appear in >95% of the
# 1429 Latin texts, making any pair containing them almost certainly noise.
#
# Entries with df=0 (surface forms not in the inverted index, e.g. "auras"
# instead of canonical "aura") are SKIPPED — treating them as ultra-rare
# would inflate the geometric mean and mask penalties for their common
# companions.
#
# Piecewise linear curve mapping geom_mean_idf → multiplier:
#   geom_idf < 0.1           → idf_floor (harshest penalty, near-stopwords)
#   0.1 ≤ geom_idf < thresh  → linear ramp from (idf_floor + 0.1) to 1.0
#   geom_idf ≥ thresh        → ≥ 1.0 (no penalty; rarity boost for Layer 3)
# ---------------------------------------------------------------------------

# Multiplier floor: the minimum rarity multiplier applied to pairs whose
# geometric mean IDF is below 0.1 (i.e., all matched lemmata are extremely
# common — words appearing in >90% of texts). Since mult is squared (Layer 1),
# the effective floor is 0.2^2 = 0.04 (96% score reduction).
RARITY_IDF_FLOOR = 0.05

# IDF threshold: the geometric mean IDF at which the multiplier reaches 1.0
# (no penalty). With 1429 Latin texts, IDF = log(1429/df):
#   df=954 (67% of texts) → idf=0.40 (penalized)
#   df=314 (22% of texts) → idf=1.51 (at threshold, no penalty)
#   df=50  (3.5% of texts) → idf=3.35 (boosted if multi-channel)
# Value of 1.5 means words appearing in more than ~22% of texts get penalized.
RARITY_IDF_THRESHOLD = 1.5

# Exponent for the base score penalty: base_score * multiplier^power.
# Higher values make the penalty steeper for common words without affecting
# rare words (mult=1.0 → 1.0^anything = 1.0). The squaring in Layer 2
# (IDF-weighted convergence) uses a fixed exponent of 2.
RARITY_PENALTY_POWER = 2.0

# Exponent applied to the rarity multiplier when scaling the convergence
# bonus: conv_mult = multiplier^power. With power=1.0, the convergence bonus
# gets the same rarity scaling as the base score (before squaring). Higher
# powers would penalize convergence more aggressively. Optimizer found 1.0
# optimal — further convergence penalty on top of squared IDF weighting
# (Layer 2) provides no benefit.
CONVERGENCE_IDF_POWER = 1.0

# Min-IDF gate: an additional penalty if ANY single matched lemma has corpus
# IDF below the threshold. Catches pairs containing truly ubiquitous words
# (per idf=0.046, cum idf=0.023, qui idf=0.002, hic idf=0.011) that
# inflate scores through multi-channel detection. Threshold 0.15 corresponds
# to words appearing in >86% of texts. Does NOT fire for moderately common
# content words like pectus (0.49), cura (0.35), arma (0.48), nec (0.44)
# which are allusive vocabulary in Latin epic despite being common in the
# corpus. Only stacks with NO_SIGNIFICANT_WORDS_PENALTY (not with normal
# multi-word matches that have at least one significant word).
RARITY_MIN_IDF_THRESHOLD = 0.15
RARITY_MIN_IDF_PENALTY = 0.30

# Rarity boost (Layer 3): for pairs with geom_idf above the threshold,
# the multiplier exceeds 1.0 to actively promote rare multi-channel matches.
# Formula: 1.0 + boost_weight * channel_factor * log(geom_idf / threshold)
# where channel_factor = min(1.0, (n_scoring_channels - 1) / 5).
# The log curve provides diminishing returns for extremely rare words,
# preventing runaway scores. The channel_factor ensures single-channel
# matches (n=1, factor=0) get zero boost — only multi-channel convergence
# on rare vocabulary is promoted. The cap prevents any multiplier from
# exceeding 2.0 regardless of how rare the vocabulary is.
# Rarity multiplier ramp start offset: the multiplier at the bottom of the
# linear ramp (geom_idf == RARITY_NEAR_STOPWORD_CUTOFF) is idf_floor + this
# value, avoiding a discontinuity at the floor/ramp boundary.
RARITY_RAMP_OFFSET = 0.1

# Geometric mean IDF below this value is treated as near-stopword territory
# (flat at idf_floor). Between this value and idf_threshold, the multiplier
# ramps linearly from (idf_floor + RARITY_RAMP_OFFSET) to 1.0.
RARITY_NEAR_STOPWORD_CUTOFF = 0.1

RARITY_BOOST_WEIGHT = 0.5          # Layer 3: scaling factor on the log-curve rarity boost for high-IDF pairs
RARITY_BOOST_CAP = 2.0             # Layer 3: hard ceiling on the rarity boost multiplier (prevents runaway scores)

# Single-word match penalty: applied to multiplier when only one unique
# lexical word is matched (n_unique_words <= 1). Since multiplier is squared
# in Layer 1, the effective penalty is 0.15^2 = 0.0225 (97.75% reduction).
# This ensures unigrams ALWAYS rank below multi-word matches, even
# penalized common-word bigrams (which get ~96% reduction). A single
# shared word is inherently less valuable than two shared words.
# Combined with convergence zeroing (Layer 2), single-word matches
# score: base * (0.15 * mult)^2 = base * 0.0225 * mult^2.
SINGLE_WORD_PENALTY = 0.12

# No-significant-words penalty: applied when a multi-word match has NO word
# with IDF >= RARITY_IDF_THRESHOLD.  These are bigrams of common vocabulary
# (e.g., "num + campus", "ter + centum") that carry weak allusion signal.
# Milder than SINGLE_WORD_PENALTY because having two common content words
# IS more informative than one word, just not as much as normal scoring
# suggests.  Combined with convergence zeroing, these pairs get:
#   score = base * (NO_SIG_PENALTY * mult)^2  (no convergence)
# The convergence zeroing is the primary mechanism — it removes the
# multi-channel inflation that made common-word pairs score so high.
NO_SIGNIFICANT_WORDS_PENALTY = 0.50

# ---------------------------------------------------------------------------
# Channel classification for two-pass architecture
# ---------------------------------------------------------------------------

# Lexical channels (require token co-occurrence in unit)
LEXICAL_CHANNELS = ["lemma", "lemma_min1", "exact", "rare_word"]

# Window pass: channels that benefit from 2-line sliding windows.
# Includes lexical channels (minus exact) plus dictionary.
# - Exact is excluded: it duplicates lemma's coverage on windows while being
#   the slowest window channel (character-level comparison on large pairs can
#   take 30+ minutes). Benchmark impact: 1/862 gold pairs lost (VF-Vergil).
# - Dictionary is included: its min_matches>=2 co-occurrence threshold gives
#   it the same sensitivity to unit boundaries as lexical channels.
WINDOW_CHANNELS = ["lemma", "lemma_min1", "rare_word", "dictionary"]

# Channels whose matching is exhaustive at line level (pairwise token similarity)
LINE_ONLY_CHANNELS = ["edit_distance", "sound", "semantic"]

# All channels run in the line pass
ALL_CHANNELS = list(CHANNEL_WEIGHTS.keys())

# Execution order: fast channels first for progressive streaming.
# Users see results within seconds (lemma completes in <1s) rather than
# waiting minutes for edit_distance/sound to finish.
CHANNEL_ORDER = [
    "lemma",         # fast, high quality — gives first results immediately
    "exact",         # fast, high precision
    "rare_word",     # fast, sparse
    "dictionary",    # fast-medium
    "syntax",        # fast, DB lookup
    "lemma_min1",    # fast, high-recall
    "semantic",      # slow (~2 min), I/O-bound
    "sound",         # slow (~3 min), CPU-bound multiprocessing
    "edit_distance",  # slowest (~3.5 min), CPU-bound multiprocessing
]

# Channels that require language-specific resources. Channels not listed
# here run for all languages (lemma, lemma_min1, exact, semantic, rare_word).
# If a channel's required resource is missing for the search language, it is
# skipped and not counted in the "N channels" progress message.
CHANNEL_LANGUAGE_SUPPORT = {
    "dictionary":    {"la", "grc"},      # Latin/Greek synonym pairs only
    "sound":         {"la", "grc"},      # character trigram matching designed for Latin/Greek
    "edit_distance": {"la", "grc"},      # Levenshtein designed for Latin/Greek morphology
    "syntax":        {"la", "grc"},      # requires syntax DB (syntax_latin.db / syntax_greek.db)
}


def get_channels_for_language(language):
    """Return the list of channels that are meaningful for a given language."""
    return [ch for ch in CHANNEL_ORDER
            if ch not in CHANNEL_LANGUAGE_SUPPORT
            or language in CHANNEL_LANGUAGE_SUPPORT[ch]]

# Channel configurations (match the evaluation study)
CHANNEL_CONFIGS = {
    "lemma": {
        "match_type": "lemma",
        "min_matches": 2,
        "language": "la",
        "stoplist_basis": "source_target",
        "stoplist_size": -1,
        "unbounded_scoring": True,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "lemma_min1": {
        "match_type": "lemma",
        "min_matches": 1,
        "language": "la",
        "stoplist_basis": "source_target",
        "stoplist_size": -1,
        "unbounded_scoring": True,
        "max_results": 50000,  # cap: weight is only 0.3, diminishing returns beyond top 50K
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "exact": {
        "match_type": "exact",
        "min_matches": 2,
        "language": "la",
        "stoplist_basis": "source_target",
        "stoplist_size": -1,
        "unbounded_scoring": True,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "semantic": {
        "match_type": "semantic",
        "min_matches": 2,
        "language": "la",
        "unbounded_scoring": True,
        "min_semantic_matches": 0,
        "semantic_only_threshold": 0.85,
        "min_semantic_score": 0.5,
        "semantic_top_n": 100,
        "max_results": 50000,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "dictionary": {
        "match_type": "dictionary",
        "min_matches": 2,
        "language": "la",
        "include_lemma_matches": True,
        "unbounded_scoring": True,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "sound": {
        "match_type": "sound",
        "min_matches": 2,
        "language": "la",
        "unbounded_scoring": True,
        "max_results": 50000,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "edit_distance": {
        "match_type": "edit_distance",
        "min_matches": 2,
        "language": "la",
        "unbounded_scoring": True,
        "edit_include_exact": True,
        "edit_min_shared_trigrams": 1,
        "min_edit_similarity": 0.6,
        "edit_top_n": 100,
        "max_results": 50000,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
    "syntax": {
        "match_type": "syntax",
    },
    "rare_word": {
        "match_type": "rare_word",
        "min_matches": 1,
        "language": "la",
        "unbounded_scoring": True,
        "rare_word_max_occurrences": 100,
        "use_edit_distance": False,
        "use_sound": False,
        "use_pos": False,
        "use_syntax": False,
    },
}


def make_window_units(line_units):
    """Create 2-line sliding window units from line units.

    Each window combines consecutive lines into a single unit with
    combined text, tokens, lemmas, and a range ref like 'luc. 1.1-luc. 1.2'.
    """
    windows = []
    for i in range(len(line_units) - 1):
        u1 = line_units[i]
        u2 = line_units[i + 1]
        window = {
            'ref': f"{u1['ref']}-{u2['ref']}",
            'text': u1['text'] + '\n' + u2['text'],
            'tokens': u1['tokens'] + u2['tokens'],
            'original_tokens': (
                u1.get('original_tokens', u1['tokens'])
                + u2.get('original_tokens', u2['tokens'])
            ),
            'lemmas': u1['lemmas'] + u2['lemmas'],
            'pos_tags': u1.get('pos_tags', []) + u2.get('pos_tags', []),
            'line_refs': [u1['ref'], u2['ref']],
            'line_token_counts': [len(u1['tokens']), len(u2['tokens'])],
        }
        windows.append(window)
    return windows


def parse_ref(ref):
    """Parse a single-line ref like 'luc. 1.5' → (book, line)."""
    nums = [int(x) for x in re.findall(r'\d+', ref)]
    if len(nums) >= 2:
        return nums[-2], nums[-1]
    return None, None


def parse_range_ref(ref):
    """Parse a ref that may be a range like 'luc. 1.1-luc. 1.2'.
    Returns (book, start_line, end_line)."""
    if '-' in ref:
        parts = ref.split('-', 1)
        nums_left = [int(x) for x in re.findall(r'\d+', parts[0])]
        nums_right = [int(x) for x in re.findall(r'\d+', parts[1])]
        if len(nums_left) >= 2 and len(nums_right) >= 2:
            book_start, line_start = nums_left[-2], nums_left[-1]
            book_end, line_end = nums_right[-2], nums_right[-1]
            if book_start == book_end:
                return book_start, line_start, line_end
            else:
                return book_start, line_start, line_start
    book, line = parse_ref(ref)
    if book is not None:
        return book, line, line
    return None, None, None


# ---------------------------------------------------------------------------
# Syntax channel: load pre-parsed data from syntax DBs
# ---------------------------------------------------------------------------

_SYNTAX_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "inverted_index", "syntax_latin.db",
)

_SYNTAX_GREEK_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "inverted_index", "syntax_greek.db",
)

_SYNTAX_PARSE_CACHE = {}
_SYNTAX_CACHE_MAX = 50  # LRU-style cap: evict oldest when exceeded


def _load_syntax_for_text(db_path, text_filename):
    """Load syntax parses from syntax_latin.db for a text.

    Results are cached at module level so repeated searches on the same
    text avoid re-reading the database.  Cache is bounded to
    _SYNTAX_CACHE_MAX entries to prevent unbounded memory growth.

    Returns dict: ref → {"lemmas": [...], "upos": [...], "heads": [...],
                          "deprels": [...], "feats": [...], "tokens": [...]}
    """
    if text_filename in _SYNTAX_PARSE_CACHE:
        return _SYNTAX_PARSE_CACHE[text_filename]

    if not os.path.exists(db_path):
        return {}

    try:
        conn = sqlite3.connect(db_path, timeout=5)
    except sqlite3.OperationalError:
        # DB may be locked by a build process; try immutable read-only
        uri = f"file:{db_path}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
    cur = conn.cursor()

    try:
        cur.execute("SELECT text_id FROM texts WHERE filename = ?", (text_filename,))
    except sqlite3.OperationalError:
        conn.close()
        # Retry with immutable read-only
        uri = f"file:{db_path}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
        cur = conn.cursor()
        cur.execute("SELECT text_id FROM texts WHERE filename = ?", (text_filename,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {}

    text_id = row[0]
    cur.execute(
        "SELECT ref, tokens, lemmas, upos, heads, deprels, feats "
        "FROM syntax WHERE text_id = ?",
        (text_id,),
    )

    parses = {}
    for ref, tokens, lemmas, upos, heads, deprels, feats in cur.fetchall():
        parses[ref] = {
            "tokens": json.loads(tokens) if tokens else [],
            "lemmas": json.loads(lemmas) if lemmas else [],
            "upos": json.loads(upos) if upos else [],
            "heads": json.loads(heads) if heads else [],
            "deprels": json.loads(deprels) if deprels else [],
            "feats": json.loads(feats) if feats else [],
        }

    conn.close()
    # Evict oldest entries if cache exceeds limit
    if len(_SYNTAX_PARSE_CACHE) >= _SYNTAX_CACHE_MAX:
        oldest = next(iter(_SYNTAX_PARSE_CACHE))
        del _SYNTAX_PARSE_CACHE[oldest]
    _SYNTAX_PARSE_CACHE[text_filename] = parses
    return parses


def _compute_syntax_score(source_parse, target_parse):
    """Compute syntax similarity between two parsed lines.

    Mirrors compute_syntax_similarity() from syntax_parser.py but operates
    directly on the DB parse format (lists) without building SyntaxSentence
    objects, for efficiency in bulk comparison.

    Returns 0.0 if no shared lemmas; otherwise a score in [0, 1].
    """
    s_lemmas = source_parse["lemmas"]
    s_deprels = source_parse["deprels"]
    s_upos = source_parse["upos"]

    t_lemmas = target_parse["lemmas"]
    t_deprels = target_parse["deprels"]
    t_upos = target_parse["upos"]

    # Build lemma → (deprel, upos) maps, excluding punctuation
    s_roles = {}
    for i, lemma in enumerate(s_lemmas):
        if i < len(s_upos) and s_upos[i] not in ("PUNCT", "X") and lemma:
            s_roles[lemma.lower()] = (
                s_deprels[i] if i < len(s_deprels) else "",
                s_upos[i],
            )

    t_roles = {}
    for i, lemma in enumerate(t_lemmas):
        if i < len(t_upos) and t_upos[i] not in ("PUNCT", "X") and lemma:
            t_roles[lemma.lower()] = (
                t_deprels[i] if i < len(t_deprels) else "",
                t_upos[i],
            )

    shared = set(s_roles.keys()) & set(t_roles.keys())
    if not shared:
        return 0.0

    from backend.syntax_parser import get_deprel_category

    score = 0.0
    max_score = len(shared)

    for lemma in shared:
        s_deprel, s_pos = s_roles[lemma]
        t_deprel, t_pos = t_roles[lemma]

        if s_deprel == t_deprel:
            score += 1.0
        elif get_deprel_category(s_deprel) == get_deprel_category(t_deprel):
            score += 0.7
        elif s_pos == t_pos:
            score += 0.4

    # Structure signature bonus (core argument overlap)
    s_core = sorted(
        s_deprels[i]
        for i in range(len(s_deprels))
        if i < len(s_upos)
        and s_upos[i] not in ("PUNCT", "X")
        and get_deprel_category(s_deprels[i]) == "core"
    )
    t_core = sorted(
        t_deprels[i]
        for i in range(len(t_deprels))
        if i < len(t_upos)
        and t_upos[i] not in ("PUNCT", "X")
        and get_deprel_category(t_deprels[i]) == "core"
    )
    if s_core and t_core:
        overlap = len(set(s_core) & set(t_core))
        union = len(set(s_core) | set(t_core))
        if union > 0:
            score += (overlap / union) * 0.5
            max_score += 0.5

    return score / max_score if max_score > 0 else 0.0


def _compute_structural_score(source_parse, target_parse):
    """Score structural similarity based on dependency head patterns.

    For pairs with no shared lemmas — compares head arrays and deprel
    sequences directly to detect syntactic imitation without lexical overlap.

    Returns a score in [0, 1] or 0.0 if structures don't match well enough.
    """
    s_heads = source_parse.get("heads", [])
    t_heads = target_parse.get("heads", [])
    s_deprels = source_parse.get("deprels", [])
    t_deprels = target_parse.get("deprels", [])
    s_upos = source_parse.get("upos", [])
    t_upos = target_parse.get("upos", [])

    if not s_heads or not t_heads:
        return 0.0

    # Filter out punctuation tokens for comparison
    def _filter_non_punct(heads, deprels, upos):
        filtered_h, filtered_d, filtered_u = [], [], []
        for i in range(min(len(heads), len(upos))):
            if upos[i] not in ("PUNCT", "X"):
                filtered_h.append(heads[i])
                filtered_d.append(deprels[i] if i < len(deprels) else "")
                filtered_u.append(upos[i])
        return filtered_h, filtered_d, filtered_u

    s_h, s_d, s_u = _filter_non_punct(s_heads, s_deprels, s_upos)
    t_h, t_d, t_u = _filter_non_punct(t_heads, t_deprels, t_upos)

    if not s_h or not t_h:
        return 0.0

    # Must be same length to have identical structure
    if len(s_h) != len(t_h):
        return 0.0

    # 1. Head pattern match — compare relative head indices
    # Normalize: convert absolute head indices to relative patterns
    head_match = (tuple(s_h) == tuple(t_h))
    if not head_match:
        return 0.0

    # 2. Deprel sequence similarity
    deprel_matches = sum(1 for a, b in zip(s_d, t_d) if a == b)
    deprel_score = deprel_matches / len(s_d) if s_d else 0.0

    # 3. UPOS sequence similarity
    upos_matches = sum(1 for a, b in zip(s_u, t_u) if a == b)
    upos_score = upos_matches / len(s_u) if s_u else 0.0

    # Combined score: head match (0.5) + deprel agreement (0.3) + upos (0.2)
    score = 0.5 + 0.3 * deprel_score + 0.2 * upos_score
    return score


def _score_structural_chunk(args):
    """Worker function for parallel structural fingerprint scoring."""
    pairs, min_score = args
    hits = []
    for source_ref, source_parse, target_ref, target_parse in pairs:
        score = _compute_structural_score(source_parse, target_parse)
        if score >= min_score:
            hits.append((source_ref, target_ref, score))
    return hits


# Pair-size gates removed: dictionary (inverted index), lemma_min1 (IDF
# pre-filter), and syntax (caching + multiprocessing) are now fast enough
# to run on any pair size.  All 9 channels always run.


def _score_syntax_chunk(args):
    """Worker function for parallel syntax scoring."""
    pairs, min_score = args
    hits = []
    for source_ref, source_parse, target_ref, target_parse in pairs:
        score = _compute_syntax_score(source_parse, target_parse)
        if score >= min_score:
            hits.append((source_ref, target_ref, score))
    return hits


def find_syntax_matches(source_units, target_units, source_id, target_id,
                        min_score=0.1, max_results=50000,
                        source_language='la', target_language='la'):
    """Find syntax matches between source and target using syntax DBs.

    Two paths:
      A) Lemma-gated: pairs sharing content lemmas (excluding function words),
         scored by deprel/upos agreement at shared lemma positions
         (_compute_syntax_score). For Greek (large texts), requires 2+ shared
         content lemmas to keep candidates manageable. For Latin, 1+ suffices.
      B) Structural fingerprint: pairs with identical head patterns (no shared
         lemmas required), scored by deprel/upos sequence similarity
         (_compute_structural_score). Catches syntactic imitation without
         lexical overlap (e.g., Thomas's Georg. 3.481 / DRN 6.1140).

    For cross-lingual pairs (e.g., Greek source, Latin target), loads from
    the appropriate DB for each side. UD dependency labels are language-
    independent, so structural fingerprint matching works cross-lingually.

    Returns results in the same format as other channels.
    """
    source_db = _SYNTAX_GREEK_DB_PATH if source_language == 'grc' else _SYNTAX_DB_PATH
    target_db = _SYNTAX_GREEK_DB_PATH if target_language == 'grc' else _SYNTAX_DB_PATH
    source_parses = _load_syntax_for_text(source_db, source_id)
    target_parses = _load_syntax_for_text(target_db, target_id)

    if not source_parses or not target_parses:
        logger.info(f"[SYNTAX] No syntax data for {source_id} or {target_id}")
        return []

    # Build ref → unit lookup for both texts
    source_by_ref = {u["ref"]: u for u in source_units}
    target_by_ref = {u["ref"]: u for u in target_units}

    # For large Greek text pairs, use function-word stoplists to limit
    # candidate explosion. For Latin, skip stoplist filtering — function-word
    # syntax matches add convergence bonus for multi-channel pairs.
    n_source = len(source_parses)
    n_target = len(target_parses)
    large_pair = n_source * n_target > 20_000_000

    if large_pair:
        source_stoplist = _STOPLISTS.get(source_language, set())
        target_stoplist = _STOPLISTS.get(target_language, set())
        stoplist = source_stoplist | target_stoplist
        MIN_SHARED_CONTENT_LEMMAS = 2
    else:
        stoplist = set()
        MIN_SHARED_CONTENT_LEMMAS = 1

    # Build lemma → [target_ref] inverted index from parsed target data
    target_lemma_index = defaultdict(set)
    for ref, parse in target_parses.items():
        for i, lemma in enumerate(parse["lemmas"]):
            if (
                i < len(parse["upos"])
                and parse["upos"][i] not in ("PUNCT", "X")
                and lemma
                and (not stoplist or lemma.lower() not in stoplist)
            ):
                target_lemma_index[lemma.lower()].add(ref)

    # --- Path A: Lemma-gated candidates ---
    candidate_pairs = []
    for source_ref, source_parse in source_parses.items():
        if source_ref not in source_by_ref:
            continue

        # Count shared lemmas per target ref
        target_hit_counts = Counter()
        for i, lemma in enumerate(source_parse["lemmas"]):
            if (
                i < len(source_parse["upos"])
                and source_parse["upos"][i] not in ("PUNCT", "X")
                and lemma
                and (not stoplist or lemma.lower() not in stoplist)
            ):
                for target_ref in target_lemma_index.get(lemma.lower(), set()):
                    target_hit_counts[target_ref] += 1

        for target_ref, count in target_hit_counts.items():
            if count < MIN_SHARED_CONTENT_LEMMAS:
                continue
            if target_ref not in target_by_ref:
                continue
            target_parse = target_parses.get(target_ref)
            if target_parse:
                candidate_pairs.append(
                    (source_ref, source_parse, target_ref, target_parse)
                )

    num_candidates = len(candidate_pairs)

    # Score lemma-gated candidates — use multiprocessing for large sets
    if num_candidates > 50000:
        import multiprocessing
        from backend.worker_util import safe_worker_count
        num_workers = safe_worker_count()
        chunk_size = (num_candidates + num_workers - 1) // num_workers
        chunks = [
            candidate_pairs[i:i + chunk_size]
            for i in range(0, num_candidates, chunk_size)
        ]
        logger.info(f"[SYNTAX] Parallel: {num_candidates:,} candidates, "
                    f"{num_workers} workers, {chunk_size:,} per chunk")
        with multiprocessing.Pool(num_workers) as pool:
            chunk_results = pool.map(
                _score_syntax_chunk,
                [(chunk, min_score) for chunk in chunks],
            )
        scored_pairs = []
        for chunk_hits in chunk_results:
            scored_pairs.extend(chunk_hits)
    else:
        scored_pairs = []
        for source_ref, source_parse, target_ref, target_parse in candidate_pairs:
            score = _compute_syntax_score(source_parse, target_parse)
            if score >= min_score:
                scored_pairs.append((source_ref, target_ref, score))

    lemma_pair_set = {(s, t) for s, t, _ in scored_pairs}
    # Track fingerprint pairs separately for distinct channel output
    fingerprint_scored = []

    # --- Path B: Structural fingerprint candidates (no shared lemmas needed) ---
    # Build head-pattern → [target_ref] index from target parses
    def _head_fingerprint(parse):
        """Create a hashable fingerprint from non-punct head indices."""
        heads = parse.get("heads", [])
        upos = parse.get("upos", [])
        filtered = tuple(
            heads[i] for i in range(min(len(heads), len(upos)))
            if upos[i] not in ("PUNCT", "X")
        )
        return filtered if len(filtered) >= 3 else None  # skip trivially short

    target_fingerprint_index = defaultdict(list)
    target_fp_counts = Counter()
    for ref, parse in target_parses.items():
        if ref not in target_by_ref:
            continue
        fp = _head_fingerprint(parse)
        if fp is not None:
            target_fingerprint_index[fp].append(ref)
            target_fp_counts[fp] += 1

    # Count source fingerprint frequencies for rarity filtering
    source_fp_counts = Counter()
    for source_ref, source_parse in source_parses.items():
        if source_ref not in source_by_ref:
            continue
        fp = _head_fingerprint(source_parse)
        if fp is not None:
            source_fp_counts[fp] += 1

    # Fingerprint rarity filter: skip patterns that are too common in
    # the text pair.  Common patterns (e.g., Verb+Object 2-token lines)
    # match hundreds of unrelated line pairs.  Rare patterns are the
    # ones that indicate genuine structural imitation.
    MAX_FINGERPRINT_FREQ = 4  # combined source + target occurrences
    skipped_common = 0

    fingerprint_pairs = []
    for source_ref, source_parse in source_parses.items():
        if source_ref not in source_by_ref:
            continue
        fp = _head_fingerprint(source_parse)
        if fp is None:
            continue
        combined_freq = source_fp_counts[fp] + target_fp_counts.get(fp, 0)
        if combined_freq > MAX_FINGERPRINT_FREQ:
            skipped_common += target_fp_counts.get(fp, 0)
            continue
        matching_targets = target_fingerprint_index.get(fp, [])
        for target_ref in matching_targets:
            # Skip pairs already found by lemma gate
            if (source_ref, target_ref) in lemma_pair_set:
                continue
            target_parse = target_parses[target_ref]
            fingerprint_pairs.append(
                (source_ref, source_parse, target_ref, target_parse)
            )

    num_fp_candidates = len(fingerprint_pairs)
    logger.info(f"[SYNTAX] Fingerprint: {len(target_fingerprint_index):,} unique patterns, "
                f"{num_fp_candidates:,} novel candidate pairs "
                f"(skipped {skipped_common:,} from common patterns)")

    # Score fingerprint candidates
    if num_fp_candidates > 50000:
        import multiprocessing
        from backend.worker_util import safe_worker_count
        num_workers = safe_worker_count()
        chunk_size = (num_fp_candidates + num_workers - 1) // num_workers
        chunks = [
            fingerprint_pairs[i:i + chunk_size]
            for i in range(0, num_fp_candidates, chunk_size)
        ]
        with multiprocessing.Pool(num_workers) as pool:
            chunk_results = pool.map(
                _score_structural_chunk,
                [(chunk, min_score) for chunk in chunks],
            )
        for chunk_hits in chunk_results:
            fingerprint_scored.extend(chunk_hits)
    else:
        for source_ref, source_parse, target_ref, target_parse in fingerprint_pairs:
            score = _compute_structural_score(source_parse, target_parse)
            if score >= min_score:
                fingerprint_scored.append((source_ref, target_ref, score))

    # Cap scored pairs BEFORE building result dicts (avoids building millions
    # of dicts only to discard most of them)
    if max_results > 0 and len(scored_pairs) > max_results:
        scored_pairs.sort(key=lambda x: x[2], reverse=True)
        scored_pairs = scored_pairs[:max_results]

    logger.info(f"[SYNTAX] {len(source_parses)} source, {len(target_parses)} target parses; "
                f"{num_candidates:,} lemma-gated + {num_fp_candidates:,} fingerprint comparisons; "
                f"{len(scored_pairs)} lemma + {len(fingerprint_scored)} fingerprint matches (score >= {min_score})")

    # Build result dicts — separate lists for lemma-gated and fingerprint
    def _build_results(pair_list):
        out = []
        for source_ref, target_ref, score in pair_list:
            source_unit = source_by_ref[source_ref]
            target_unit = target_by_ref[target_ref]
            out.append({
                "source": {
                    "ref": source_ref,
                    "text": source_unit.get("text", ""),
                    "tokens": source_unit.get("tokens", []),
                    "lemmas": source_unit.get("lemmas", []),
                    "highlight_indices": [],
                },
                "target": {
                    "ref": target_ref,
                    "text": target_unit.get("text", ""),
                    "tokens": target_unit.get("tokens", []),
                    "lemmas": target_unit.get("lemmas", []),
                    "highlight_indices": [],
                },
                "score": score,
                "overall_score": score,
                "matched_words": [],
            })
        return out

    lemma_results = _build_results(scored_pairs)
    fp_results = _build_results(fingerprint_scored)

    return {"syntax": lemma_results, "syntax_structural": fp_results}


def run_channel(channel_name, config, source_units, target_units,
                matcher, scorer, source_id, target_id,
                source_path=None, target_path=None,
                source_language='la', target_language='la'):
    """Run a single search channel and return scored results."""
    match_type = config.get("match_type", "lemma")
    settings = dict(config)

    if match_type == "syntax":
        # Syntax channel uses its own scoring from syntax DBs
        # Returns dict: {"syntax": [...], "syntax_structural": [...]}
        max_results = config.get("max_results", 50000)
        min_score = settings.get("min_score", 0.1)
        return find_syntax_matches(
            source_units, target_units,
            source_id, target_id,
            min_score=min_score,
            max_results=max_results,
            source_language=source_language,
            target_language=target_language,
        )

    if match_type == "semantic":
        from backend.semantic_similarity import find_semantic_matches
        if source_path:
            settings["source_text_path"] = source_path
        if target_path:
            settings["target_text_path"] = target_path
        matches, _ = find_semantic_matches(source_units, target_units, settings)
    elif match_type == "dictionary":
        from backend.semantic_similarity import find_dictionary_matches
        matches, _ = find_dictionary_matches(source_units, target_units, settings)
    elif match_type == "sound":
        matches, _ = matcher.find_sound_matches(source_units, target_units, settings)
    elif match_type == "edit_distance":
        matches, _ = matcher.find_edit_distance_matches(
            source_units, target_units, settings
        )
    elif match_type == "rare_word":
        try:
            from backend.blueprints.hapax import find_rare_word_matches_direct
            max_occ = settings.get("rare_word_max_occurrences", 50)
            matches = find_rare_word_matches_direct(
                source_units, target_units,
                language=settings.get("language", "la"),
                max_occurrences=max_occ,
            )
        except (ImportError, AttributeError):
            matches = []
    else:
        # lemma or exact
        matches, _ = matcher.find_matches(source_units, target_units, settings, None)

    if not matches:
        return []

    # IDF pre-filter: when a per-channel cap is set and the raw match count
    # far exceeds it, estimate each match's score by summing IDF of matched
    # lemmas and keep only the top candidates.  This avoids scoring hundreds
    # of thousands of low-value matches (the main bottleneck for lemma_min1).
    max_results = config.get("max_results", 0)
    if max_results > 0 and len(matches) > max_results * 2:
        lemma_freq = Counter()
        for u in source_units:
            for lem in set(u.get('lemmas', [])):
                lemma_freq[lem] += 1
        for u in target_units:
            for lem in set(u.get('lemmas', [])):
                lemma_freq[lem] += 1
        total_docs = len(source_units) + len(target_units)

        def _quick_idf(match):
            return sum(
                math.log((total_docs + 1) / (lemma_freq.get(l, 1) + 1)) + 1
                for l in match.get('matched_lemmas', [])
            )

        for m in matches:
            m['_quick_score'] = _quick_idf(m)
        matches.sort(key=lambda m: m['_quick_score'], reverse=True)
        kept = max_results * 4  # 4x buffer for distance-factor reranking
        logger.info(f"[{channel_name.upper()}] IDF pre-filter: {len(matches):,} → {kept:,} matches")
        matches = matches[:kept]

    scored = scorer.score_matches(
        matches, source_units, target_units, settings, source_id, target_id
    )

    # Per-channel result cap: retain only the top-scoring results from each
    # channel before fusion.
    if max_results > 0 and len(scored) > max_results:
        scored.sort(
            key=lambda r: r.get("overall_score") or r.get("score") or 0,
            reverse=True,
        )
        scored = scored[:max_results]

    return scored


# ---------------------------------------------------------------------------
# Corpus-IDF utilities for graduated rarity multiplier
# ---------------------------------------------------------------------------

_corpus_doc_freq_cache = {}
_total_texts_cache = {}
_headword_map_cache = {}

# Meter-specific IDF caches (keyed by meter name, e.g. "hexameter")
_meter_doc_freq_cache = {}   # meter -> {lemma: doc_freq}
_meter_total_texts_cache = {}  # meter -> int
_text_genre_cache = None     # filename -> row dict from text_genres.csv
_meter_text_ids_cache = {}   # meter -> set of text_ids in the index


def _load_text_genres():
    """Load data/text_genres.csv into a dict keyed by filename (cached)."""
    global _text_genre_cache
    if _text_genre_cache is not None:
        return _text_genre_cache
    import csv
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'data', 'text_genres.csv')
    _text_genre_cache = {}
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                _text_genre_cache[row['filename']] = row
    except Exception as e:
        logger.warning(f"[METER IDF] Could not load text_genres.csv: {e}")
        _text_genre_cache = {}
    return _text_genre_cache


def _get_text_meter(filename):
    """Return the meter string for a text filename, or None if unknown."""
    genres = _load_text_genres()
    row = genres.get(filename)
    if row:
        meter = row.get('meter', '').strip().lower()
        if meter and meter not in ('unknown', 'mixed', ''):
            return meter
    return None


def _get_meter_text_ids(meter, language='la'):
    """Get set of text_ids from the inverted index that belong to a meter group.

    Joins text_genres.csv filenames against the index's texts table.
    Cached per (meter, language).
    """
    cache_key = (meter, language)
    if cache_key in _meter_text_ids_cache:
        return _meter_text_ids_cache[cache_key]

    genres = _load_text_genres()
    meter_filenames = {fn for fn, row in genres.items()
                       if row.get('meter', '').strip().lower() == meter}
    if not meter_filenames:
        _meter_text_ids_cache[cache_key] = set()
        return set()

    try:
        from backend.inverted_index import get_connection
        conn = get_connection(language)
        if not conn:
            _meter_text_ids_cache[cache_key] = set()
            return set()

        cursor = conn.cursor()
        # Fetch all text_id/filename pairs and filter in Python to avoid
        # huge IN clauses
        cursor.execute('SELECT text_id, filename FROM texts')
        text_ids = set()
        for text_id, filename in cursor.fetchall():
            if filename in meter_filenames:
                text_ids.add(text_id)

        _meter_text_ids_cache[cache_key] = text_ids
        logger.info(f"[METER IDF] Found {len(text_ids)} texts for meter "
                    f"'{meter}' (language={language})")
    except Exception as e:
        logger.error(f"[METER IDF] Failed to load text_ids for meter "
                     f"'{meter}': {e}")
        _meter_text_ids_cache[cache_key] = set()

    return _meter_text_ids_cache[cache_key]


def _get_meter_doc_freqs(lemmas, meter, language='la'):
    """Batch-fetch meter-specific document frequencies, with caching.

    Like _get_corpus_doc_freqs but restricted to texts of a given meter.
    Queries the inverted index postings table filtered by text_ids that
    belong to the meter group.

    Returns dict: lemma -> document count within the meter group.
    """
    cache_key = meter  # one flat cache per meter
    if cache_key not in _meter_doc_freq_cache:
        _meter_doc_freq_cache[cache_key] = {}
    meter_cache = _meter_doc_freq_cache[cache_key]

    uncached = [l for l in lemmas if l not in meter_cache]
    if not uncached:
        return {l: meter_cache.get(l, 0) for l in lemmas}

    text_ids = _get_meter_text_ids(meter, language)
    if not text_ids:
        # No texts for this meter — return zeros
        for l in uncached:
            meter_cache[l] = 0
        return {l: meter_cache.get(l, 0) for l in lemmas}

    try:
        from backend.inverted_index import get_connection
        conn = get_connection(language)
        if not conn:
            for l in uncached:
                meter_cache[l] = 0
            return {l: meter_cache.get(l, 0) for l in lemmas}

        cursor = conn.cursor()

        # Prepare u/v dedup for Latin (same logic as _get_corpus_doc_freqs)
        if language == 'la':
            canonical = {}
            query_set = set()
            for l in uncached:
                norm = l.replace('v', 'u').replace('j', 'i')
                if norm not in canonical:
                    canonical[norm] = l
                    query_set.add(l)
            query_lemmas = list(query_set)
        else:
            query_lemmas = list(set(uncached))

        # Expand u/v variants for SQL
        expanded_map = {}  # expanded_form -> original_lemma
        for lemma in query_lemmas:
            variants = {lemma}
            if language == 'la':
                variants.add(lemma.replace('u', 'v'))
                variants.add(lemma.replace('v', 'u'))
            for v in variants:
                expanded_map[v] = lemma

        # Query in batches, filtering by text_ids in the meter group
        text_id_list = list(text_ids)
        all_variants = list(expanded_map.keys())
        batch_size = 500

        # Build a temporary result dict: original_lemma -> count
        batch_result = {}
        for i in range(0, len(all_variants), batch_size):
            batch = all_variants[i:i + batch_size]
            lemma_ph = ','.join(['?' for _ in batch])
            tid_ph = ','.join(['?' for _ in text_id_list])
            sql = (f'SELECT lemma, COUNT(DISTINCT text_id) FROM postings '
                   f'WHERE lemma IN ({lemma_ph}) AND text_id IN ({tid_ph}) '
                   f'GROUP BY lemma')
            cursor.execute(sql, batch + text_id_list)
            for row_lemma, count in cursor.fetchall():
                original = expanded_map.get(row_lemma, row_lemma)
                batch_result[original] = batch_result.get(original, 0) + count

        # Populate cache
        if language == 'la':
            for l in uncached:
                norm = l.replace('v', 'u').replace('j', 'i')
                canon_lemma = canonical[norm]
                meter_cache[l] = batch_result.get(canon_lemma, 0)
        else:
            for l in uncached:
                meter_cache[l] = batch_result.get(l, 0)

        # Headword normalization (same as corpus version)
        headword_map = _get_headword_map(language)
        if headword_map:
            hw_to_fetch = set()
            for l in uncached:
                hw = headword_map.get(l)
                if hw and hw != l and hw not in meter_cache:
                    hw_to_fetch.add(hw)

            if hw_to_fetch:
                # Recurse for headwords
                hw_freqs = _get_meter_doc_freqs(list(hw_to_fetch), meter,
                                                 language)
                for hw, df in hw_freqs.items():
                    meter_cache[hw] = df

            for l in uncached:
                hw = headword_map.get(l)
                if hw and hw != l:
                    hw_df = meter_cache.get(hw, 0)
                    meter_cache[l] = max(meter_cache[l], hw_df)

    except Exception as e:
        logger.error(f"[METER IDF] Batch query failed for meter '{meter}': {e}")
        for l in uncached:
            meter_cache[l] = meter_cache.get(l, 0)

    return {l: meter_cache.get(l, 0) for l in lemmas}


def _get_meter_total_texts(meter, language='la'):
    """Get total text count for a meter group (cached)."""
    cache_key = (meter, language)
    if cache_key not in _meter_total_texts_cache:
        text_ids = _get_meter_text_ids(meter, language)
        _meter_total_texts_cache[cache_key] = len(text_ids) if text_ids else 0
    return _meter_total_texts_cache[cache_key]


def _get_headword_map(language='la'):
    """Load headword map from lemma table (cached at module level).

    Returns dict mapping inflected/variant forms to their dictionary
    headword. For Latin, uses data/lemma_tables/latin_lemmas.json (62K+
    entries). This is the same file TextProcessor already uses.

    Used by _get_corpus_doc_freqs() to normalize IDF lookups: "quem" →
    headword "qui" → use max(df("quem"), df("qui")) so that oblique
    forms of ultra-common words aren't treated as rare.
    """
    if language in _headword_map_cache:
        return _headword_map_cache[language]

    import json
    from pathlib import Path

    project_root = Path(__file__).resolve().parent.parent
    table_map = {
        'la': project_root / 'data' / 'lemma_tables' / 'latin_lemmas.json',
        'grc': project_root / 'data' / 'lemma_tables' / 'greek_lemmas.json',
    }
    path = table_map.get(language)
    if path and path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            _headword_map_cache[language] = json.load(f)
    else:
        _headword_map_cache[language] = {}
    return _headword_map_cache[language]


def _get_corpus_doc_freqs(lemmas, language='la'):
    """Batch-fetch corpus-wide document frequencies, with caching.

    Reuses get_document_frequencies_batch() from hapax.py which queries the
    inverted index (la_index.db / grc_index.db). The hapax function handles
    u/v expansion internally for Latin.

    IMPORTANT: For Latin, deduplicates u/v variants before batch querying
    to avoid a collision bug in get_document_frequencies_batch where the
    expanded_map overwrites entries when two input lemmas are u/v variants
    of each other (e.g., querying {'uero', 'vero'} causes 'uero' → df=0).

    Returns dict: lemma → document count (0 if not found).
    """
    uncached = [l for l in lemmas if l not in _corpus_doc_freq_cache]
    if uncached:
        from backend.blueprints.hapax import get_document_frequencies_batch

        if language == 'la':
            # Deduplicate u/v variants: keep only one canonical form per
            # variant group. Map all variants back to the same DF result.
            canonical = {}  # u-normalized form → first lemma seen
            query_set = set()
            for l in uncached:
                norm = l.replace('v', 'u').replace('j', 'i')
                if norm not in canonical:
                    canonical[norm] = l
                    query_set.add(l)
                # else: l is a u/v variant of an already-queued lemma

            batch_result = get_document_frequencies_batch(query_set, language)

            # Populate cache for all uncached lemmas, including variants
            for l in uncached:
                norm = l.replace('v', 'u').replace('j', 'i')
                canon_lemma = canonical[norm]
                _corpus_doc_freq_cache[l] = batch_result.get(canon_lemma, 0)
        else:
            batch_result = get_document_frequencies_batch(set(uncached), language)
            for l in uncached:
                _corpus_doc_freq_cache[l] = batch_result.get(l, 0)

        # Headword normalization: for each lemma, check if its dictionary
        # headword has a higher document frequency. This catches oblique
        # forms of ultra-common function words that appear rare in the
        # inverted index because they're stored under inflected forms:
        #   "quem" (df=164) → headword "qui" (df=1426) → use 1426
        #   "quos" (df=8)   → headword "qui" (df=1426) → use 1426
        # Without this, these forms escape rarity penalties entirely.
        headword_map = _get_headword_map(language)
        if headword_map:
            # Collect headwords that need df lookup but aren't cached yet
            hw_to_fetch = set()
            for l in uncached:
                hw = headword_map.get(l)
                if hw and hw != l and hw not in _corpus_doc_freq_cache:
                    hw_to_fetch.add(hw)

            if hw_to_fetch:
                hw_batch = get_document_frequencies_batch(hw_to_fetch, language)
                for hw in hw_to_fetch:
                    _corpus_doc_freq_cache[hw] = hw_batch.get(hw, 0)

            # Apply max(lemma_df, headword_df) normalization
            for l in uncached:
                hw = headword_map.get(l)
                if hw and hw != l:
                    hw_df = _corpus_doc_freq_cache.get(hw, 0)
                    _corpus_doc_freq_cache[l] = max(_corpus_doc_freq_cache[l], hw_df)

    return {l: _corpus_doc_freq_cache.get(l, 0) for l in lemmas}


def _get_total_texts(language='la'):
    """Get total text count from inverted index (cached)."""
    if language not in _total_texts_cache:
        try:
            from backend.inverted_index import get_connection
            conn = get_connection(language)
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM texts')
                _total_texts_cache[language] = cursor.fetchone()[0]
            else:
                # Fallback: known corpus sizes
                _total_texts_cache[language] = {'la': 1429, 'grc': 691}.get(
                    language, 1000)
        except Exception:
            _total_texts_cache[language] = {'la': 1429, 'grc': 691}.get(
                language, 1000)
    return _total_texts_cache[language]


def _recover_semantic_for_structural(line_channel_results, source_units,
                                     target_units, source_path, target_path,
                                     language='la'):
    """Recover semantic similarity for structural fingerprint pairs.

    The semantic channel's top_n cap (default 100 per source line) filters out
    many valid targets in dense similarity regions (e.g., plague narratives
    where hundreds of lines exceed the 0.5 threshold). Structural fingerprint
    pairs that have no shared lemmas may still have meaningful semantic
    similarity that was filtered by this cap.

    This function looks up the actual cosine similarity for each structural
    pair using precomputed embeddings and injects qualifying results into the
    semantic channel results, allowing fusion to naturally combine syntax +
    semantic evidence.
    """
    structural_results = line_channel_results.get("syntax_structural", [])
    if not structural_results:
        return

    # Build ref → unit-index mappings
    src_ref_to_idx = {}
    for i, u in enumerate(source_units):
        src_ref_to_idx[u.get("ref", "")] = i
    tgt_ref_to_idx = {}
    for i, u in enumerate(target_units):
        tgt_ref_to_idx[u.get("ref", "")] = i

    # Collect (source_idx, target_idx) pairs that need semantic lookup.
    # Skip pairs that already have semantic results (they passed the cap).
    existing_semantic = set()
    for r in line_channel_results.get("semantic", []):
        rs = r.get("source", {}).get("ref", "")
        rt = r.get("target", {}).get("ref", "")
        existing_semantic.add((rs, rt))

    pairs_to_check = []
    for r in structural_results:
        src_ref = r.get("source", {}).get("ref", "")
        tgt_ref = r.get("target", {}).get("ref", "")
        if (src_ref, tgt_ref) in existing_semantic:
            continue
        src_idx = src_ref_to_idx.get(src_ref)
        tgt_idx = tgt_ref_to_idx.get(tgt_ref)
        if src_idx is not None and tgt_idx is not None:
            pairs_to_check.append((src_ref, tgt_ref, src_idx, tgt_idx))

    if not pairs_to_check:
        return

    # Load precomputed embeddings
    try:
        from backend.embedding_storage import load_embeddings
        source_emb = load_embeddings(source_path, language)
        target_emb = load_embeddings(target_path, language)
        if source_emb is None or target_emb is None:
            return
    except Exception as e:
        logger.error(f"[SEMANTIC RECOVERY] Failed to load embeddings: {e}")
        return

    # Two-tier semantic threshold for structural pairs:
    #   - With dictionary confirmation (≥1 synonym pair): 0.575
    #   - Without dictionary confirmation: 0.70 (much stricter)
    # Thomas tricolon (Georg 3.481/DRN 6.1140) has cosine 0.5787 and
    # corrumpo↔vasto dictionary match, so it passes tier 1.
    MIN_SCORE_WITH_DICT = 0.575
    MIN_SCORE_NO_DICT = 0.70

    from backend.synonym_dict import find_synonym_pairs_in_passages

    recovered = []
    dict_confirmed = 0
    for src_ref, tgt_ref, src_idx, tgt_idx in pairs_to_check:
        if src_idx >= len(source_emb) or tgt_idx >= len(target_emb):
            continue
        s_vec = source_emb[src_idx]
        t_vec = target_emb[tgt_idx]
        s_norm = np.linalg.norm(s_vec)
        t_norm = np.linalg.norm(t_vec)
        if s_norm == 0 or t_norm == 0:
            continue
        sim = float(np.dot(s_vec, t_vec) / (s_norm * t_norm))

        # Check dictionary synonyms between the two lines
        src_unit = source_units[src_idx]
        tgt_unit = target_units[tgt_idx]
        src_lemmas = src_unit.get("lemmas", [])
        tgt_lemmas = tgt_unit.get("lemmas", [])
        syn_pairs = find_synonym_pairs_in_passages(
            src_lemmas, tgt_lemmas, language, include_lemma_matches=True
        ) if src_lemmas and tgt_lemmas else []

        has_dict = len(syn_pairs) > 0
        threshold = MIN_SCORE_WITH_DICT if has_dict else MIN_SCORE_NO_DICT

        if sim < threshold:
            continue

        if has_dict:
            dict_confirmed += 1

        # Build matched_words from dictionary pairs for display
        mw_list = []
        for sp in syn_pairs:
            mw_list.append({
                "lemma": sp["source_lemma"],
                "source_word": sp["source_lemma"],
                "target_word": sp["target_lemma"],
                "type": "dictionary" if sp["source_lemma"].lower() != sp["target_lemma"].lower() else "lemma",
                "similarity": 1.0,
            })

        recovered.append({
            "source": {
                "ref": src_ref,
                "text": src_unit.get("text", ""),
                "tokens": src_unit.get("tokens", []),
                "lemmas": src_lemmas,
                "highlight_indices": [],
            },
            "target": {
                "ref": tgt_ref,
                "text": tgt_unit.get("text", ""),
                "tokens": tgt_unit.get("tokens", []),
                "lemmas": tgt_lemmas,
                "highlight_indices": [],
            },
            "score": sim,
            "overall_score": sim,
            "matched_words": mw_list,
            "match_basis": "semantic",
        })

    if recovered:
        if "semantic" not in line_channel_results:
            line_channel_results["semantic"] = []
        line_channel_results["semantic"].extend(recovered)
        logger.info(f"[SEMANTIC RECOVERY] Recovered {len(recovered)} semantic scores "
                    f"for {len(pairs_to_check)} structural pairs "
                    f"({dict_confirmed} dictionary-confirmed, "
                    f"skipped {len(pairs_to_check) - len(recovered)} below threshold)")


def fuse_results(channel_results, weights=None, convergence_bonus=None,
                  idf_floor=None, idf_threshold=None,
                  convergence_idf_power=None, min_idf_threshold=None,
                  min_idf_penalty=None, language='la',
                  freq_basis='corpus', source_id=None, target_id=None):
    """Combine results from multiple channels using weighted score fusion.

    Three-layer rarity scoring for each (source_ref, target_ref) pair:

      base = sum(channel_score * channel_weight)
      mult = piecewise_linear(geom_mean_idf, idf_floor, threshold)
      idf_weight = min(1.0, min_word_idf)^2                     [Layer 2]
      weighted_n = n_scoring_channels * idf_weight              [Layer 2]
      conv = convergence_bonus * max(0, weighted_n - 1)         [Layer 2]
      fused = base * mult^penalty_power + conv * mult^conv_power

    Layer 3 boost: when geom_idf >= threshold, mult rises above 1.0 via
    log curve scaled by min(channel_factor, word_factor), requiring both
    multiple channels and multiple distinct words.

    Optional overrides allow testing different parameter configurations
    without modifying module globals (used by weight optimization).

    freq_basis controls which document-frequency baseline is used for IDF:
      "corpus" (default) — full corpus (all texts in the inverted index)
      "meter" — only texts sharing the same meter as source/target
                (falls back to corpus if texts don't share a meter,
                or if text_genres.csv lacks meter info)
    source_id/target_id: filenames needed for meter lookup.
    """
    _weights = weights if weights is not None else CHANNEL_WEIGHTS
    _convergence_bonus = convergence_bonus if convergence_bonus is not None else CONVERGENCE_BONUS
    _idf_floor = idf_floor if idf_floor is not None else RARITY_IDF_FLOOR
    _idf_threshold = idf_threshold if idf_threshold is not None else RARITY_IDF_THRESHOLD
    _conv_idf_power = convergence_idf_power if convergence_idf_power is not None else CONVERGENCE_IDF_POWER
    _min_idf_threshold = min_idf_threshold if min_idf_threshold is not None else RARITY_MIN_IDF_THRESHOLD
    _min_idf_penalty = min_idf_penalty if min_idf_penalty is not None else RARITY_MIN_IDF_PENALTY
    _rarity_boost_weight = RARITY_BOOST_WEIGHT
    _rarity_boost_cap = RARITY_BOOST_CAP
    _penalty_power = RARITY_PENALTY_POWER
    _stoplist = _STOPLISTS.get(language, set())

    pair_scores = defaultdict(lambda: {
        "score": 0.0,
        "channels": [],
        "n_scoring_channels": 0,  # channels with raw_score > 0
        "best_result": None,
        "best_score": 0.0,
        "all_source_highlights": set(),
        "all_target_highlights": set(),
        "all_matched_words": {},
    })

    import time as _time
    _t0 = _time.time()

    for ch_name, results in channel_results.items():
        weight = _weights.get(ch_name, 1.0)
        for r in results:
            rs = r.get("source", {}).get("ref", "")
            rt = r.get("target", {}).get("ref", "")
            key = (rs, rt)
            raw_score = r.get("overall_score") or r.get("score") or 0
            pair_scores[key]["score"] += raw_score * weight
            pair_scores[key]["channels"].append(ch_name)
            if raw_score > 0:
                pair_scores[key]["n_scoring_channels"] += 1

            # Accumulate highlight indices from all channels
            src = r.get("source", {})
            tgt = r.get("target", {})
            for idx in src.get("highlight_indices", []):
                pair_scores[key]["all_source_highlights"].add(idx)
            for idx in tgt.get("highlight_indices", []):
                pair_scores[key]["all_target_highlights"].add(idx)

            # Accumulate matched words (dedup by lemma, prefer entries with source_word)
            for mw in r.get("matched_words", []):
                lemma = mw.get("lemma", "")
                if not lemma:
                    continue
                existing = pair_scores[key]["all_matched_words"].get(lemma)
                if existing is None or (not existing.get("source_word") and mw.get("source_word")):
                    pair_scores[key]["all_matched_words"][lemma] = mw

            # Keep the result with the highest individual score for display
            if raw_score > pair_scores[key]["best_score"]:
                pair_scores[key]["best_result"] = r
                pair_scores[key]["best_score"] = raw_score

    _t1 = _time.time()
    logger.info(f"[FUSION] Accumulated {len(pair_scores):,} unique pairs from "
                f"{sum(len(r) for r in channel_results.values()):,} channel results in {_t1-_t0:.1f}s")

    # --- Pre-fusion cap: limit pairs entering rarity scoring ---
    # Rarity scoring is O(n) with expensive per-pair IDF lookups. For
    # large Greek text pairs, pair_scores can exceed 500K entries. Since
    # rarity scoring can only reduce scores (mult <= 1 for common words)
    # or boost already-high multi-channel pairs, the final top results
    # are almost always within the top 200K by raw weighted score. Cap
    # here to keep fusion tractable.
    PRE_FUSION_CAP = 500000
    total_pairs = len(pair_scores)
    if total_pairs > PRE_FUSION_CAP:
        # Keep pairs with highest raw weighted score (before rarity adjustment).
        # Rarity Layer 3 can boost rare-word pairs, so we use a generous cap
        # (500K) to avoid dropping gold pairs with low raw scores but rare vocab.
        top_keys = sorted(pair_scores.keys(),
                          key=lambda k: pair_scores[k]["score"],
                          reverse=True)[:PRE_FUSION_CAP]
        pair_scores = {k: pair_scores[k] for k in top_keys}
        logger.info(f"[FUSION] Pre-fusion cap: kept top {PRE_FUSION_CAP:,} of {total_pairs:,} pairs by raw score")

    # ===================================================================
    # RARITY SCORING: Three-layer system applied to every fused pair
    # ===================================================================
    #
    # This section implements all three layers of rarity scoring in a
    # single pass over all pairs, optimized to avoid per-pair function
    # call overhead (~100K pairs typical; inlining reduced runtime from
    # ~400s to ~58s for Aeneid x Met).
    #
    # Final formula for each pair:
    #   fused_score = base_score * mult^2 + conv_score * mult^power
    # where:
    #   base_score  = sum of (channel_score * channel_weight) across channels
    #   mult        = rarity multiplier from Layer 1 (piecewise linear on geom_idf)
    #                 OR rarity boost from Layer 3 (log curve, for rare words)
    #   conv_score  = convergence_bonus * (weighted_n - 1.0)   [Layer 2]
    #   weighted_n  = n_scoring_channels * min(1.0, geom_idf)^2  [Layer 2]
    #   power       = CONVERGENCE_IDF_POWER (currently 1.0)
    #
    # ===================================================================

    # --- Pre-fetch corpus document frequencies in one batch ---
    # Collect every unique lemma across all pairs (excluding sub-lexical
    # fragments like [que], [nti] from sound/edit_distance channels),
    # then query the inverted index once. This avoids per-pair DB queries
    # (which would mean ~100K separate queries for large text pairs).
    # NOTE: We include entries with idf=0 (from rare_word, semantic, etc.)
    # because they still have valid lemmas whose corpus df is needed for
    # rarity scoring. Only sub-lexical fragments (keys starting with '[')
    # are excluded.
    all_lexical_lemmas = set()
    for key, info in pair_scores.items():
        for lemma, mw in info["all_matched_words"].items():
            if lemma and not lemma.startswith('['):
                all_lexical_lemmas.add(lemma)
    # Select document-frequency baseline based on freq_basis parameter.
    # "corpus" (default): full inverted index.
    # "meter": restricted to texts sharing the same meter as source/target.
    _effective_freq_basis = 'corpus'  # fallback
    _shared_meter = None
    if freq_basis == 'meter' and source_id and target_id and language == 'la':
        src_meter = _get_text_meter(source_id)
        tgt_meter = _get_text_meter(target_id)
        if src_meter and tgt_meter and src_meter == tgt_meter:
            meter_n = _get_meter_total_texts(src_meter, language)
            if meter_n >= 5:  # need enough texts for meaningful IDF
                _shared_meter = src_meter
                _effective_freq_basis = 'meter'
                logger.info(f"[FREQ BASIS] Using meter-specific IDF: "
                            f"'{src_meter}' ({meter_n} texts)")
            else:
                logger.info(f"[FREQ BASIS] Meter '{src_meter}' has only "
                            f"{meter_n} texts, falling back to corpus")
        else:
            logger.info(f"[FREQ BASIS] Texts don't share a meter "
                        f"(source={src_meter}, target={tgt_meter}), "
                        f"falling back to corpus")

    if all_lexical_lemmas:
        if _effective_freq_basis == 'meter' and _shared_meter:
            total_texts = _get_meter_total_texts(_shared_meter, language)
            doc_freq_map = _get_meter_doc_freqs(
                list(all_lexical_lemmas), _shared_meter, language)
        else:
            total_texts = _get_total_texts(language)
            doc_freq_map = _get_corpus_doc_freqs(
                list(all_lexical_lemmas), language)
    else:
        total_texts = 1429
        doc_freq_map = {}

    # Pre-compute constants used in the inner loop to avoid repeated
    # arithmetic on every iteration.
    _log_total = math.log(total_texts)        # log(N) for IDF = log(N) - log(df)
    # IDF rescaling factor: normalizes the dynamic range so that the rarity
    # curve (calibrated for corpus-sized N) produces consistent multipliers
    # regardless of baseline size.  When freq_basis='corpus', scale=1.0
    # (identity). When hexameter (N=218), scale≈1.35, stretching meter IDF
    # values back into the range the piecewise curve was tuned for.
    _N_reference = _get_total_texts(language)  # full corpus N (the calibration target)
    _idf_scale = math.log(_N_reference) / _log_total if _log_total > 0 else 1.0
    _idf_scale = min(_idf_scale, 2.0)  # cap to prevent over-inflation for tiny baselines
    _cutoff = RARITY_NEAR_STOPWORD_CUTOFF     # geom_idf below this → flat at floor
    _ramp_offset = RARITY_RAMP_OFFSET         # offset above floor at ramp start
    _ramp_start = _idf_floor + _ramp_offset   # multiplier at geom_idf = cutoff
    _ramp_range = 1.0 - _ramp_start           # span of the linear ramp
    _thresh_range = _idf_threshold - _cutoff   # IDF span of the linear ramp

    for key, info in pair_scores.items():
        # ---------------------------------------------------------------
        # LAYER 1: Compute geometric mean IDF and piecewise multiplier
        # ---------------------------------------------------------------
        # For each matched lemma with nonzero IDF, compute corpus IDF =
        # log(N/df), then take the geometric mean. Map to a multiplier
        # via the same piecewise linear curve defined in the constants.
        mw_dict = info["all_matched_words"]
        # Collect corpus IDFs for all lexical entries (not sub-lexical
        # fragments). Deduplicate by (source_word, target_word) to avoid
        # counting both inflected surface forms (e.g., "pugnas" df=1) and
        # canonical lemmas (e.g., "pugna" df=596) for the same word —
        # keep the canonical form (highest df) for accurate rarity scoring.
        word_pair_best = {}  # (src_word, tgt_word) -> (corpus_idf, df)
        unique_src_words = set()  # distinct source words
        unique_tgt_words = set()  # distinct target words
        for lemma, mw in mw_dict.items():
            if lemma.startswith('['):
                continue  # sub-lexical fragment
            df = doc_freq_map.get(lemma, 0)
            if df <= 0:
                continue  # not in inverted index
            cidf = (_log_total - math.log(df)) * _idf_scale
            sw = mw.get('source_word', '')
            tw = mw.get('target_word', '')
            word_key = (sw, tw) if (sw or tw) else (lemma,)
            existing = word_pair_best.get(word_key)
            if existing is None or df > existing[1]:
                word_pair_best[word_key] = (cidf, df)
            # Track unique words on each side (using lemma as fallback)
            unique_src_words.add(sw.lower() if sw else lemma)
            unique_tgt_words.add(tw.lower() if tw else lemma)
        corpus_idfs = [cidf for cidf, _ in word_pair_best.values()]
        # True unique word count = min of source-side and target-side
        # distinct words. Prevents two source words mapping to one target
        # word (e.g., "agger"+"tumulus" → "tumulus") from counting as 2.
        n_unique_words = min(len(unique_src_words), len(unique_tgt_words)) if corpus_idfs else 0
        # Count "content" words — unique surface words NOT on the curated
        # function-word stoplist.  Must use the same unique word sets as
        # n_unique_words (not the raw lemma dict, which can have duplicate
        # entries like "fata" + "fatum" for the same surface word).
        # IDF can't distinguish "tum" (function word) from "pectore"
        # (content word, also common).  The curated stoplist can.
        n_content_src = sum(1 for w in unique_src_words
                           if w.replace('v', 'u') not in _stoplist)
        n_content_tgt = sum(1 for w in unique_tgt_words
                           if w.replace('v', 'u') not in _stoplist)
        n_content_words = min(n_content_src, n_content_tgt)
        has_structural = "syntax_structural" in info["channels"]

        if corpus_idfs:
            # Geometric mean via exp(mean(log(x))), with floor of 0.001
            # to avoid log(0) for words with corpus IDF very near zero
            log_sum = 0.0
            for cidf in corpus_idfs:
                log_sum += math.log(cidf) if cidf > 0.001 else math.log(0.001)
            geom_mean_idf = math.exp(log_sum / len(corpus_idfs))

            # Piecewise multiplier: maps geom_mean_idf to [idf_floor, 1.0]
            # for common words, or > 1.0 for rare multi-channel matches
            if geom_mean_idf < _cutoff:
                # Zone 1: Near-stopwords. Flat at idf_floor (0.2).
                # Examples: "est" (idf≈0.01), "et" (idf≈0.03)
                multiplier = _idf_floor
            elif geom_mean_idf < _idf_threshold:
                # Zone 2: Graduated penalty. Linear ramp from 0.3 to 1.0.
                # Example: "tum vero" with geom_idf=0.36 → t=0.19 → mult=0.33
                t = (geom_mean_idf - _cutoff) / _thresh_range
                multiplier = _ramp_start + t * _ramp_range
            else:
                # -------------------------------------------------------
                # LAYER 3: Rarity BOOST for rare multi-channel matches
                # -------------------------------------------------------
                # When geom_idf exceeds the threshold, the vocabulary is
                # rare enough to deserve promotion rather than penalty.
                # The boost is a log curve (diminishing returns for
                # extremely rare words) scaled by TWO convergence factors:
                #
                # 1. channel_factor = min(1.0, (n_channels - 1) / 5)
                #    Requires multiple channels to confirm the match.
                # 2. word_factor = min(1.0, (n_unique_words - 1) / 3)
                #    Requires multiple distinct words to be shared.
                #
                # The MINIMUM of these two factors is used, so both
                # conditions must be met for a large boost:
                #   - 1 word on 5 channels → min(0.8, 0) = 0 → no boost
                #   - 2 words on 3 channels → min(0.4, 0.33) = 0.33
                #   - 3 words on 6 channels → min(1.0, 0.67) = 0.67
                # This prevents single rare words (even genuinely rare
                # ones like "Erinys") from outranking multi-word allusions.
                n_for_boost = info["n_scoring_channels"]
                channel_factor = min(1.0, (n_for_boost - 1) / 5.0)
                word_factor = min(1.0, (n_unique_words - 1) / 3.0)
                boost_factor = min(channel_factor, word_factor)
                multiplier = min(_rarity_boost_cap,
                                 1.0 + _rarity_boost_weight * boost_factor * math.log(geom_mean_idf / _idf_threshold))

            # Single-word penalty: demote matches sharing only one
            # distinct word.  Applied before Layer 1 squaring, so
            # effective penalty is SINGLE_WORD_PENALTY^2.
            # Exception: structural fingerprint pairs — the syntactic
            # pattern match counts as additional evidence beyond lexical,
            # so even 1 dictionary synonym is meaningful confirmation.
            min_idf_gate_fired = False
            if n_unique_words <= 1 and not has_structural:
                multiplier *= SINGLE_WORD_PENALTY
            elif n_content_words == 0:
                # All-function-words penalty: every matched lemma is on the
                # curated stoplist (e.g., "tum + inde", "nec + sic", "ubi").
                # These matches arise from grammatical co-occurrence, not
                # allusion.  Penalized more aggressively than content-word
                # matches since the stoplist gives us certainty that no
                # content word is present.
                multiplier *= NO_SIGNIFICANT_WORDS_PENALTY
                min_idf_gate_fired = True
            elif n_content_words < n_unique_words:
                # Mixed penalty: some words are content, some are function
                # words (e.g., "tum + vires", "nec + priorem", "ubi + fata").
                # The function words add zero allusion signal — "tum" appears
                # in 70%+ of Latin texts.  Treat as effectively a
                # single-content-word match: apply the single-word penalty
                # and zero convergence.  A match on "tum + vires" should
                # rank like a match on just "vires", not like a genuine
                # 2-content-word allusion.
                multiplier *= SINGLE_WORD_PENALTY
                min_idf_gate_fired = True
        else:
            # No corpus IDF data: either all matched words are sub-lexical
            # fragments (sound/edit_distance) or had df=0.
            if "syntax_structural" in info["channels"]:
                # Structural fingerprint match: identical dependency head
                # pattern with no shared lemmas. This is genuine structural
                # evidence, not absence of evidence. Use neutral multiplier.
                multiplier = 1.0
                geom_mean_idf = _idf_threshold
            else:
                # Other channels: treat as common-word match — absence of
                # lexical evidence should not be rewarded.
                multiplier = _idf_floor
                geom_mean_idf = _idf_floor
            min_idf_gate_fired = False

        # ---------------------------------------------------------------
        # LAYER 2: IDF-weighted convergence bonus
        # ---------------------------------------------------------------
        # Convergence IDF weight uses the MINIMUM word IDF (not geometric
        # mean).  This provides continuous Zipf-like scaling: pairs with
        # a very common word (IDF ~0.3) get weight ~0.09, pairs with a
        # moderately common word (IDF ~0.7) get weight ~0.49, and pairs
        # where all words have IDF > 1.0 get full weight (1.0).  Using
        # min instead of geometric mean prevents a rare partner from
        # masking a function word — "nec absistit" is gated by nec's
        # low IDF, not rescued by absisto's high IDF.
        min_word_idf = min(corpus_idfs) if corpus_idfs else 0
        idf_weight = min(1.0, min_word_idf) ** 2
        base_score = info["score"]
        n = info["n_scoring_channels"]
        weighted_n = n * idf_weight
        # Hard zeroing for single-word matches and min-IDF gate hits.
        # Single-word: convergence from one shared word is noise.
        # Gate-fired: a ubiquitous function word (per, cum, qui)
        # drives multi-channel detection but carries no signal.
        # Common content-word pairs (pectus+cura, arma+genus) do NOT
        # get zeroed — their convergence is naturally suppressed by
        # the min-word-IDF^2 weighting in idf_weight above.
        if (n_unique_words <= 1 and not has_structural) or min_idf_gate_fired:
            weighted_n = 0.0
        conv_score = _convergence_bonus * (weighted_n - 1.0) if weighted_n > 1.0 else 0.0

        # Step bonus for high channel convergence (6+ channels)
        if n >= HIGH_CONVERGENCE_THRESHOLD and weighted_n > 1.0:
            conv_score += HIGH_CONVERGENCE_BONUS * idf_weight

        # Interaction bonus: rare_word + sound synergy
        ch_set = set(info["channels"])
        if "rare_word" in ch_set and "sound" in ch_set and weighted_n > 1.0:
            conv_score += RARE_SOUND_INTERACTION_BONUS * idf_weight

        # ---------------------------------------------------------------
        # Final score assembly
        # ---------------------------------------------------------------
        # Layer 1 (penalty): base_score * mult^2
        #   The squaring makes the penalty much steeper: mult=0.5 → 0.25,
        #   mult=0.2 → 0.04. Rare words (mult=1.0) are unaffected.
        # Layer 2 (convergence): conv_score * mult^power
        #   The convergence bonus is also scaled by the rarity multiplier,
        #   but only to the first power (not squared), since the IDF
        #   weighting in weighted_n already provides steep suppression.
        conv_mult = multiplier ** _conv_idf_power
        info["score"] = base_score * (multiplier ** _penalty_power) + conv_score * conv_mult

    _t2 = _time.time()
    logger.info(f"[FUSION] Rarity scoring complete for {len(pair_scores):,} pairs in {_t2-_t1:.1f}s")

    # Sort by fused score and build output
    sorted_pairs = sorted(pair_scores.items(), key=lambda x: x[1]["score"], reverse=True)
    merged = []
    for (rs, rt), info in sorted_pairs:
        result = dict(info["best_result"]) if info["best_result"] else {}
        # Merge highlights from all channels into the result
        if "source" in result:
            result["source"] = dict(result["source"])
            result["source"]["highlight_indices"] = sorted(
                info["all_source_highlights"]
            )
        if "target" in result:
            result["target"] = dict(result["target"])
            result["target"]["highlight_indices"] = sorted(
                info["all_target_highlights"]
            )
        result["matched_words"] = list(info["all_matched_words"].values())
        result["fused_score"] = round(info["score"], 4)
        result["channels"] = info["channels"]
        result["channel_count"] = len(info["channels"])
        merged.append(result)

    return merged


# Exponential distance decay for window results based on cross-break gap:
# the number of tokens between the last matched word on line 1 and the
# first matched word on line 2.  Tight enjambments (gap 0–1) get no/minimal
# penalty; wide gaps (8+) are heavily penalized.
WINDOW_DISTANCE_ALPHA = 0.25


def _matched_word_indices(tokens, word):
    """Find indices of a matched word in a token array (case-insensitive)."""
    if not word or not tokens:
        return []
    w = word.lower()
    return [i for i, t in enumerate(tokens) if t.lower() == w]


def _check_line_span(positions, boundary):
    """Check if any positions fall on both sides of a line boundary."""
    if not positions:
        return False
    return any(i < boundary for i in positions) and any(i >= boundary for i in positions)


def _which_line_has_matches(positions, boundary):
    """Return which line (0 or 1) has the most matched-word positions.
    Falls back to line 0 on tie."""
    if not positions:
        return 0
    on_line0 = sum(1 for i in positions if i < boundary)
    on_line1 = sum(1 for i in positions if i >= boundary)
    return 1 if on_line1 > on_line0 else 0


def _trim_to_line(side, line_num):
    """Trim a window unit dict to show only one line of text.

    Keeps the original range ref so merge_line_and_window treats it as a
    window (with one novel line pair), preserving recall for pairs found
    only via window channels. Trims text, tokens, and highlights to the
    relevant line. Removes line_token_counts so frontend renders as single line.
    """
    counts = side.get('line_token_counts', [])
    if not counts or len(counts) < 2:
        return side
    boundary = counts[0]
    tokens = side.get('tokens', [])
    text_lines = side.get('text', '').split('\n')
    highlights = side.get('highlight_indices', [])

    if line_num == 0:
        new_tokens = tokens[:boundary]
        new_text = text_lines[0] if text_lines else ''
        new_highlights = [i for i in highlights if i < boundary]
    else:
        new_tokens = tokens[boundary:]
        new_text = text_lines[1] if len(text_lines) > 1 else ''
        new_highlights = [i - boundary for i in highlights if i >= boundary]

    side['tokens'] = new_tokens
    side['text'] = new_text
    side['highlight_indices'] = sorted(new_highlights)
    # Keep the original range ref — merge_line_and_window needs it to
    # correctly identify this as a window result with a novel line pair.
    # Removing window metadata so frontend renders as single line.
    side.pop('line_token_counts', None)
    side.pop('line_refs', None)
    return side


def penalize_single_line_windows(window_results):
    """Filter and penalize window results based on enjambment quality.

    Three outcomes per result:
    1. Matched words span lines → genuine enjambment.  Apply exponential
       distance decay; keep as 2-line display.
    2. Matched words all on one line → not a genuine enjambment.  Trim to
       show only the line with matched words (single-line display).
       Preserves recall without visual clutter.
    3. No positions determinable → fall back to highlight_indices for the
       span check (handles scorer fallback to lemma forms).
    """
    out = []
    for r in window_results:
        src = r.get('source', {})
        tgt = r.get('target', {})
        src_counts = src.get('line_token_counts')
        tgt_counts = tgt.get('line_token_counts')
        if not src_counts or not tgt_counts:
            out.append(r)  # not a window result, keep as-is
            continue

        matched_words = r.get('matched_words', [])
        if not matched_words:
            continue  # no matched words at all, drop

        src_tokens = src.get('tokens', [])
        tgt_tokens = tgt.get('tokens', [])
        src_boundary = src_counts[0]
        tgt_boundary = tgt_counts[0]

        # Find positions of actual matched words
        src_positions = []
        tgt_positions = []
        for mw in matched_words:
            src_positions.extend(_matched_word_indices(src_tokens, mw.get('source_word', '')))
            tgt_positions.extend(_matched_word_indices(tgt_tokens, mw.get('target_word', '')))

        # Fall back to highlight_indices if matched-word lookup failed
        # (happens when scorer falls back to lemma form for source_word)
        if not src_positions:
            src_positions = list(src.get('highlight_indices', []))
        if not tgt_positions:
            tgt_positions = list(tgt.get('highlight_indices', []))

        src_spans = _check_line_span(src_positions, src_boundary)
        tgt_spans = _check_line_span(tgt_positions, tgt_boundary)

        if src_spans or tgt_spans:
            # Genuine enjambment — penalize by cross-break gap (tokens between
            # last matched word on line 1 and first matched word on line 2).
            # Tight enjambments (gap=0) get no penalty; wide gaps get heavy decay.
            gaps = []
            if src_spans:
                last_on_l1 = max(i for i in src_positions if i < src_boundary)
                first_on_l2 = min(i for i in src_positions if i >= src_boundary)
                gaps.append(first_on_l2 - last_on_l1 - 1)
            if tgt_spans:
                last_on_l1 = max(i for i in tgt_positions if i < tgt_boundary)
                first_on_l2 = min(i for i in tgt_positions if i >= tgt_boundary)
                gaps.append(first_on_l2 - last_on_l1 - 1)
            max_gap = max(gaps) if gaps else 0
            distance_factor = math.exp(-WINDOW_DISTANCE_ALPHA * max_gap)
            r['fused_score'] = round(r.get('fused_score', 0) * distance_factor, 4)
            out.append(r)
        else:
            # Not a genuine enjambment — trim to single-line display
            r['source'] = _trim_to_line(
                dict(src), _which_line_has_matches(src_positions, src_boundary))
            r['target'] = _trim_to_line(
                dict(tgt), _which_line_has_matches(tgt_positions, tgt_boundary))
            out.append(r)

    return out


def _dedup_overlapping_windows(window_results):
    """Remove overlapping window results that are duplicates of the same match.

    Sliding windows produce overlapping 2-line pairs: (140-141) and (141-142)
    on one side combined with (293-294) and (294-295) on the other yield up to
    4 copies of the same match.  Keep only the highest-scoring window when both
    the source and target ranges overlap with an already-kept window AND the
    lower-scored window's matched words are a subset of the kept window's.
    This preserves windows with genuinely different matches on adjacent lines.
    """
    if not window_results:
        return window_results

    parsed = []
    for r in window_results:
        rs = r.get("source", {}).get("ref", "")
        rt = r.get("target", {}).get("ref", "")
        sb, ss, se = parse_range_ref(rs)
        tb, ts, te = parse_range_ref(rt)
        parsed.append((sb, ss, se, tb, ts, te))

    # Extract matched-word lemma sets for each result
    word_sets = []
    for r in window_results:
        lemmas = frozenset(
            mw.get("lemma", "") for mw in r.get("matched_words", [])
            if mw.get("lemma")
        )
        word_sets.append(lemmas)

    # Sort by score descending so we greedily keep the best
    scored = sorted(range(len(window_results)),
                    key=lambda i: window_results[i].get('fused_score', 0),
                    reverse=True)

    kept = []
    # Index kept windows by target line numbers for fast overlap lookup.
    # Each target line maps to the kept windows that cover it, so we only
    # compare against windows that could actually overlap in the target.
    kept_by_tgt_line = defaultdict(list)  # tgt_line -> [(sb, ss, se, tb, ts, te, lemmas)]

    for i in scored:
        sb, ss, se, tb, ts, te = parsed[i]
        if sb is None or tb is None:
            kept.append(window_results[i])
            continue

        # Check only kept windows that overlap this window's target lines
        is_dup = False
        cand_lemmas = word_sets[i]
        # Collect candidate overlapping windows from target line index
        checked = set()  # avoid checking same kept window twice
        for tl in range(ts, te + 1):
            for entry in kept_by_tgt_line.get((tb, tl), []):
                eid = id(entry)
                if eid in checked:
                    continue
                checked.add(eid)
                ksb, kss, kse, _, kts, kte, k_lemmas = entry
                if sb != ksb:
                    continue
                src_overlaps = ss <= kse and kss <= se
                if src_overlaps:
                    if not cand_lemmas or cand_lemmas <= k_lemmas:
                        is_dup = True
                        break
            if is_dup:
                break

        if not is_dup:
            kept.append(window_results[i])
            entry = (sb, ss, se, tb, ts, te, cand_lemmas)
            for tl in range(ts, te + 1):
                kept_by_tgt_line[(tb, tl)].append(entry)

    return kept


def merge_line_and_window(line_results, window_results):
    """Merge line and window results, with windows superseding overlapping lines.

    When a window result overlaps any line result (shares at least one
    source×target line pair), the window replaces those line results,
    providing richer two-line context without duplicates.  Window results
    that are fully subsumed by line results (all their line pairs already
    covered) are dropped.  The merged list is sorted by fused_score.
    """
    window_results = _dedup_overlapping_windows(window_results)
    # Index line results by their (book, line, book, line) tuple
    line_by_ref = {}
    for i, r in enumerate(line_results):
        rs = r.get("source", {}).get("ref", "")
        rt = r.get("target", {}).get("ref", "")
        sb, sl = parse_ref(rs)
        tb, tl = parse_ref(rt)
        if sb is not None and tb is not None:
            line_by_ref[(sb, sl, tb, tl)] = i

    # Track which line results get superseded by windows
    superseded = set()

    kept_windows = []
    for r in window_results:
        rs = r.get("source", {}).get("ref", "")
        rt = r.get("target", {}).get("ref", "")
        rs_b, rs_start, rs_end = parse_range_ref(rs)
        rt_b, rt_start, rt_end = parse_range_ref(rt)

        if rs_b is None or rt_b is None:
            kept_windows.append(r)
            continue

        # Find all line results this window overlaps
        overlapping = []
        novel = False
        for sl in range(rs_start, rs_end + 1):
            for tl in range(rt_start, rt_end + 1):
                key = (rs_b, sl, rt_b, tl)
                if key in line_by_ref:
                    overlapping.append(line_by_ref[key])
                else:
                    novel = True

        if novel:
            # Window covers at least one line pair not in any line result —
            # always keep it (dropping would lose those novel pairs).
            window_score = r.get("fused_score", 0)
            kept_windows.append(r)
            for line_idx in overlapping:
                line_score = line_results[line_idx].get("fused_score", 0)
                if window_score >= line_score:
                    superseded.add(line_idx)
        # If fully subsumed (no novel pairs), drop the window

    merged = [r for i, r in enumerate(line_results) if i not in superseded]
    merged.extend(kept_windows)
    merged.sort(key=lambda r: r.get('fused_score', 0), reverse=True)
    return merged


def _run_channels_sequential(channels, configs, source_units, target_units,
                             matcher, scorer, source_id, target_id,
                             source_path, target_path, phase_label,
                             progress_callback,
                             source_language='la', target_language='la'):
    """Run channels sequentially in the main process.

    The heavy channels (edit_distance, sound) use internal multiprocessing
    to parallelize their own work across cores, so running channels
    sequentially here avoids nested parallelism overhead.
    """
    channel_results = {}
    total = len(channels)

    for i, ch_name in enumerate(channels):
        if progress_callback:
            progress_callback(i + 1, total, ch_name, phase_label)

        config = configs[ch_name]
        results = run_channel(
            ch_name, config, source_units, target_units,
            matcher, scorer, source_id, target_id,
            source_path=source_path, target_path=target_path,
            source_language=source_language, target_language=target_language,
        )
        if results:
            # Syntax returns dict with "syntax" and "syntax_structural" keys
            if isinstance(results, dict):
                for sub_ch, sub_results in results.items():
                    if sub_results:
                        channel_results[sub_ch] = sub_results
            else:
                channel_results[ch_name] = results

    return channel_results


def iter_fusion_search(source_units, target_units, matcher, scorer,
                       source_id, target_id, language='la',
                       mode='merged', max_results=5000,
                       source_path=None, target_path=None,
                       user_settings=None,
                       source_language=None, target_language=None,
                       freq_basis='corpus'):
    """Generator version of run_fusion_search for progressive SSE streaming.

    Yields (event_type, data) tuples as the search progresses:
        ("channel_start", {channel, step, total, phase})
        ("channel_done",  {channel, count, step, total, phase})
        ("intermediate",  {results, total_results, channels_done, phase})
        ("complete",      {results, total_results})

    Uses CHANNEL_ORDER (fast channels first) so intermediate results
    appear within seconds of starting the search.
    """
    user_settings = user_settings or {}
    if source_language is None:
        source_language = language
    if target_language is None:
        target_language = language

    # Build per-channel configs with language override and user settings
    configs = {}
    for name, cfg in CHANNEL_CONFIGS.items():
        c = dict(cfg)
        if "language" in c:
            c["language"] = language
        # Merge user settings (e.g., use_meter) into each channel config
        for k in ('use_meter',):
            if user_settings.get(k):
                c[k] = user_settings[k]
        configs[name] = c

    # --- Pass 1: Line-level (language-appropriate channels, fast-first order) ---
    line_channel_results = {}
    available_channels = get_channels_for_language(language)
    line_channels = [ch for ch in available_channels if ch in configs]
    total_line = len(line_channels)

    for i, ch_name in enumerate(line_channels):
        yield ("channel_start", {
            "channel": ch_name,
            "step": i + 1,
            "total": total_line,
            "phase": "line",
        })

        results = run_channel(
            ch_name, configs[ch_name], source_units, target_units,
            matcher, scorer, source_id, target_id,
            source_path=source_path, target_path=target_path,
            source_language=source_language, target_language=target_language,
        )
        # Syntax returns dict with "syntax" and "syntax_structural" keys
        if isinstance(results, dict):
            count = sum(len(v) for v in results.values() if v)
            for sub_ch, sub_results in results.items():
                if sub_results:
                    line_channel_results[sub_ch] = sub_results
        else:
            count = len(results) if results else 0
            if results:
                line_channel_results[ch_name] = results

        yield ("channel_done", {
            "channel": ch_name,
            "count": count,
            "step": i + 1,
            "total": total_line,
            "phase": "line",
            "skipped": False,
        })

        # Send intermediate fused results after each channel that found matches.
        # Skip when count==0 (no new data to fuse, saves bandwidth).
        # Cap intermediates at 500 (preview only) to avoid huge JSON payloads;
        # the full max_results set is sent in the final "complete" event.
        if count > 0 and line_channel_results:
            fused = fuse_results(line_channel_results, language=language,
                                 freq_basis=freq_basis,
                                 source_id=source_id, target_id=target_id)
            preview_cap = min(max_results, 500) if max_results > 0 else 500
            top = fused[:preview_cap]
            yield ("intermediate", {
                "results": top,
                "total_results": len(fused),
                "channels_done": list(line_channel_results.keys()),
                "channels_total": total_line,
                "phase": "line",
            })

    # Recover semantic scores for structural fingerprint pairs filtered
    # by the semantic_top_n cap.
    if "syntax_structural" in line_channel_results and source_path and target_path:
        _recover_semantic_for_structural(
            line_channel_results, source_units, target_units,
            source_path, target_path, language)

        # Gate: keep structural pairs that have semantic confirmation AND
        # either (a) dictionary synonym confirmation or (b) high cosine.
        # Semantic + structural alone is too noisy — many unrelated Latin
        # lines share dependency patterns and have moderate cosine (0.5-0.6).
        from backend.synonym_dict import find_synonym_pairs_in_passages as _find_syn
        semantic_scores = {}
        for r in line_channel_results.get("semantic", []):
            rs = r.get("source", {}).get("ref", "")
            rt = r.get("target", {}).get("ref", "")
            score = r.get("score", r.get("overall_score", 0))
            # Keep highest score if multiple semantic results for same pair
            if score > semantic_scores.get((rs, rt), 0):
                semantic_scores[(rs, rt)] = score

        # Build ref→unit index for dictionary lookup
        src_ref_to_idx = {u.get("ref", ""): i for i, u in enumerate(source_units)}
        tgt_ref_to_idx = {u.get("ref", ""): i for i, u in enumerate(target_units)}

        MIN_COSINE_NO_DICT = 0.70
        before = len(line_channel_results["syntax_structural"])
        kept = []
        for r in line_channel_results["syntax_structural"]:
            src_ref = r.get("source", {}).get("ref", "")
            tgt_ref = r.get("target", {}).get("ref", "")
            pair_key = (src_ref, tgt_ref)

            # Must have semantic confirmation
            if pair_key not in semantic_scores:
                continue

            cosine = semantic_scores[pair_key]

            # Check dictionary synonyms
            si = src_ref_to_idx.get(src_ref)
            ti = tgt_ref_to_idx.get(tgt_ref)
            has_dict = False
            if si is not None and ti is not None:
                sl = source_units[si].get("lemmas", [])
                tl = target_units[ti].get("lemmas", [])
                if sl and tl:
                    has_dict = len(_find_syn(sl, tl, language, include_lemma_matches=True)) > 0

            if has_dict or cosine >= MIN_COSINE_NO_DICT:
                kept.append(r)

        line_channel_results["syntax_structural"] = kept
        after = len(kept)
        if before != after:
            logger.info(f"[STRUCTURAL GATE] Kept {after}/{before} structural pairs "
                        f"(dictionary or cosine >= {MIN_COSINE_NO_DICT})")

    line_fused = fuse_results(line_channel_results, language=language,
                               freq_basis=freq_basis,
                               source_id=source_id, target_id=target_id)

    if mode == 'line':
        final = line_fused[:max_results] if max_results > 0 else line_fused
        yield ("complete", {"results": final, "total_results": len(line_fused)})
        return

    # --- Pass 2: Window-level (co-occurrence channels only) ---
    source_windows = make_window_units(source_units)
    target_windows = make_window_units(target_units)
    window_channel_results = {}
    window_channels = [ch for ch in WINDOW_CHANNELS if ch in configs
                       and ch in available_channels]
    total_window = len(window_channels)

    for i, ch_name in enumerate(window_channels):
        yield ("channel_start", {
            "channel": ch_name,
            "step": i + 1,
            "total": total_window,
            "phase": "window",
        })

        results = run_channel(
            ch_name, configs[ch_name], source_windows, target_windows,
            matcher, scorer, source_id, target_id,
            source_path=source_path, target_path=target_path,
            source_language=source_language, target_language=target_language,
        )
        count = len(results) if results else 0
        if results:
            window_channel_results[ch_name] = results

        yield ("channel_done", {
            "channel": ch_name,
            "count": count,
            "step": i + 1,
            "total": total_window,
            "phase": "window",
        })

    window_fused = fuse_results(window_channel_results, language=language,
                                 freq_basis=freq_basis,
                                 source_id=source_id, target_id=target_id)
    window_fused = penalize_single_line_windows(window_fused)

    if mode == 'window':
        final = window_fused[:max_results] if max_results > 0 else window_fused
        yield ("complete", {"results": final, "total_results": len(window_fused)})
        return

    # --- Merge: line results first, then novel window results ---
    merged = merge_line_and_window(line_fused, window_fused)
    final = merged[:max_results] if max_results > 0 else merged
    yield ("complete", {"results": final, "total_results": len(merged)})


def run_fusion_search(source_units, target_units, matcher, scorer,
                      source_id, target_id, language='la',
                      mode='merged', max_results=500,
                      source_path=None, target_path=None,
                      progress_callback=None,
                      source_language=None, target_language=None,
                      freq_basis='corpus'):
    """Run two-pass weighted fusion search.

    Pass 1 (line-level): All 9 channels run on individual verse lines.
    Pass 2 (window-level): Lexical channels only run on 2-line sliding
        windows, capturing enjambed allusions. Sub-lexical and
        distributional channels are omitted because their pairwise
        token comparisons are already exhaustive at the line level.

    Args:
        source_units: Processed line units for source text
        target_units: Processed line units for target text
        matcher: Matcher instance
        scorer: Scorer instance
        source_id: Source text filename
        target_id: Target text filename
        language: Language code ('la', 'grc', 'en')
        mode: 'line' (lines only), 'window' (windows only), 'merged' (both)
        max_results: Maximum results to return (0 = unlimited)
        source_path: Full path to source .tess file (for semantic)
        target_path: Full path to target .tess file (for semantic)
        progress_callback: Optional fn(step, total, channel_name, phase) for SSE
        freq_basis: IDF baseline ('corpus' or 'meter')

    Returns:
        List of result dicts sorted by fused_score descending.
    """
    if source_language is None:
        source_language = language
    if target_language is None:
        target_language = language

    # Update language in all configs
    configs = {}
    for name, cfg in CHANNEL_CONFIGS.items():
        c = dict(cfg)
        if "language" in c:
            c["language"] = language
        configs[name] = c

    # --- Pass 1: Line-level (language-appropriate channels) ---
    available_channels = get_channels_for_language(language)
    line_channels = [ch for ch in available_channels if ch in configs]

    line_channel_results = _run_channels_sequential(
        line_channels, configs, source_units, target_units,
        matcher, scorer, source_id, target_id,
        source_path, target_path, "line",
        progress_callback,
        source_language=source_language, target_language=target_language,
    )

    # Recover semantic scores for structural fingerprint pairs that were
    # filtered by the semantic_top_n cap. This lets fusion combine syntax +
    # semantic evidence for pairs with no shared lemmas.
    if "syntax_structural" in line_channel_results and source_path and target_path:
        _recover_semantic_for_structural(
            line_channel_results, source_units, target_units,
            source_path, target_path, language)

        # Gate: keep structural pairs that have semantic confirmation AND
        # either (a) dictionary synonym confirmation or (b) high cosine.
        from backend.synonym_dict import find_synonym_pairs_in_passages as _find_syn2
        semantic_scores2 = {}
        for r in line_channel_results.get("semantic", []):
            rs = r.get("source", {}).get("ref", "")
            rt = r.get("target", {}).get("ref", "")
            score = r.get("score", r.get("overall_score", 0))
            if score > semantic_scores2.get((rs, rt), 0):
                semantic_scores2[(rs, rt)] = score

        src_ref_to_idx2 = {u.get("ref", ""): i for i, u in enumerate(source_units)}
        tgt_ref_to_idx2 = {u.get("ref", ""): i for i, u in enumerate(target_units)}

        MIN_COSINE_NO_DICT2 = 0.70
        before = len(line_channel_results["syntax_structural"])
        kept2 = []
        for r in line_channel_results["syntax_structural"]:
            src_ref = r.get("source", {}).get("ref", "")
            tgt_ref = r.get("target", {}).get("ref", "")
            pair_key = (src_ref, tgt_ref)
            if pair_key not in semantic_scores2:
                continue
            cosine = semantic_scores2[pair_key]
            si = src_ref_to_idx2.get(src_ref)
            ti = tgt_ref_to_idx2.get(tgt_ref)
            has_dict = False
            if si is not None and ti is not None:
                sl = source_units[si].get("lemmas", [])
                tl = target_units[ti].get("lemmas", [])
                if sl and tl:
                    has_dict = len(_find_syn2(sl, tl, language, include_lemma_matches=True)) > 0
            if has_dict or cosine >= MIN_COSINE_NO_DICT2:
                kept2.append(r)

        line_channel_results["syntax_structural"] = kept2
        after = len(kept2)
        if before != after:
            logger.info(f"[STRUCTURAL GATE] Kept {after}/{before} structural pairs "
                        f"(dictionary or cosine >= {MIN_COSINE_NO_DICT2})")

    line_fused = fuse_results(line_channel_results, language=language,
                               freq_basis=freq_basis,
                               source_id=source_id, target_id=target_id)

    if mode == 'line':
        return line_fused[:max_results] if max_results > 0 else line_fused

    # --- Pass 2: Window-level (lexical channels only) ---
    # Only lexical channels benefit from windowing — see module docstring
    # for the channel-appropriate granularity rationale.
    window_channels = [ch for ch in WINDOW_CHANNELS if ch in configs
                       and ch in available_channels]

    source_windows = make_window_units(source_units)
    target_windows = make_window_units(target_units)

    window_channel_results = _run_channels_sequential(
        window_channels, configs, source_windows, target_windows,
        matcher, scorer, source_id, target_id,
        source_path, target_path, "window",
        progress_callback,
        source_language=source_language, target_language=target_language,
    )
    window_fused = fuse_results(window_channel_results, language=language,
                                 freq_basis=freq_basis,
                                 source_id=source_id, target_id=target_id)
    window_fused = penalize_single_line_windows(window_fused)

    if mode == 'window':
        return window_fused[:max_results] if max_results > 0 else window_fused

    # --- Merge: line results first, then novel window results ---
    merged = merge_line_and_window(line_fused, window_fused)

    return merged[:max_results] if max_results > 0 else merged
