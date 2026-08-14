"""
Tesserae V6 - Matcher

Core matching engine for finding shared vocabulary between texts.
Identifies word-level correspondences using various matching strategies.

Match Types:
    - lemma: Match by dictionary form (e.g., "arma" matches "armis", "armorum")
    - exact: Match only identical surface forms
    - sound: Phonetic similarity via character trigrams

Stoplist Generation:
    Uses Zipf's law elbow detection to automatically identify
    high-frequency function words to exclude from matching.

Stoplist Basis Options:
    - corpus: Use corpus-wide frequencies (default)
    - source: Use source text frequencies only
    - target: Use target text frequencies only
    - source_target: Use combined source+target frequencies
"""
import unicodedata

def normalize_greek(text):
    """Strip accents/diacritics from Greek text for stoplist comparison"""
    # NFD decomposes characters, then we filter out combining marks
    normalized = unicodedata.normalize('NFD', text)
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').lower()

def normalize_latin(text):
    """Normalize Latin text for stoplist comparison (u/v equivalence)"""
    # Classical Latin texts often use 'u' where modern editions use 'v'
    return text.lower().replace('v', 'u')


# ── Greek-to-Latin transliteration ───────────────────────────────────────
# Maps Greek characters to their Latin-alphabet equivalents for cross-lingual
# phonetic comparison.  Accent-stripped (NFD + remove combining marks) before
# mapping, so only base characters appear here.

_GREEK_TO_LATIN = {
    'α': 'a', 'β': 'b', 'γ': 'g', 'δ': 'd', 'ε': 'e',
    'ζ': 'z', 'η': 'e', 'θ': 'th', 'ι': 'i', 'κ': 'c',
    'λ': 'l', 'μ': 'm', 'ν': 'n', 'ξ': 'x', 'ο': 'o',
    'π': 'p', 'ρ': 'r', 'σ': 's', 'ς': 's', 'τ': 't',
    'υ': 'u', 'φ': 'ph', 'χ': 'ch', 'ψ': 'ps', 'ω': 'o',
    # rough breathing mark (if surviving NFD) and digamma
    'ϝ': 'v', 'ϛ': 'st',
}


def transliterate_greek_to_latin(token):
    """Transliterate a Greek token to Latin characters for phonetic comparison.

    Strips accents first, then maps each Greek character.  Non-Greek characters
    (punctuation, already-Latin) pass through unchanged.
    """
    # Strip accents/diacritics
    nfd = unicodedata.normalize('NFD', token.lower())
    stripped = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    # Replace final sigma
    stripped = stripped.replace('ς', 'σ')
    result = []
    for ch in stripped:
        result.append(_GREEK_TO_LATIN.get(ch, ch))
    return ''.join(result)


# ── Coptic-to-Greek transliteration ───────────────────────────────────────
# Coptic uses a Greek-derived alphabet: 24 of its letters are visually and
# phonetically identical to Greek letters, just at a different Unicode
# codepoint (the Coptic block U+2C80-U+2CB1).  The remaining 7 letters are
# Coptic-specific (shei ϣ, fei ϥ, khei ϧ, hori ϩ, gangia ϫ, shima ϭ, dei ϯ);
# they live at U+03E2-U+03EF in the legacy "Greek and Coptic" block, and
# also at U+2CB2-U+2CBF in the primary Coptic block.  Texts in our corpus
# mix both encodings.
#
# The Coptic-specific letters are mapped to their nearest Greek phonetic
# equivalent.  These are heuristic choices — Coptic phonology had sounds
# Greek did not — but they keep edit distance to genuine Greek loanwords
# small, which is the goal of this channel.
#
#   ϣ shei  → σ      (sibilant /ʃ/, closest Greek is /s/)
#   ϥ fei   → φ      (/f/)
#   ϧ khei  → χ      (Bohairic /x/, same as Greek chi)
#   ϩ hori  → ''     (/h/; Greek has no /h/ letter, traditionally a breathing)
#   ϫ gangia → γ     (/dʒ/ ≈ /g/ in Greek loanwords like ϫⲱⲣ/γωρ-)
#   ϭ shima → κ      (palatalised /c/, closest Greek is /k/)
#   ϯ dei   → τι     (this letter encodes the syllable /ti/)

_COPTIC_TO_GREEK = {
    # Primary Coptic block (U+2C80-U+2CB1) — direct Greek equivalents
    'ⲁ': 'α', 'ⲃ': 'β', 'ⲅ': 'γ', 'ⲇ': 'δ', 'ⲉ': 'ε',
    'ⲋ': 'στ',  # Coptic sou ≈ Greek stigma/digamma
    'ⲍ': 'ζ', 'ⲏ': 'η', 'ⲑ': 'θ', 'ⲓ': 'ι', 'ⲕ': 'κ',
    'ⲗ': 'λ', 'ⲙ': 'μ', 'ⲛ': 'ν', 'ⲝ': 'ξ', 'ⲟ': 'ο',
    'ⲡ': 'π', 'ⲣ': 'ρ', 'ⲥ': 'σ', 'ⲧ': 'τ',
    'ⲩ': 'υ', 'ⲫ': 'φ', 'ⲭ': 'χ', 'ⲯ': 'ψ', 'ⲱ': 'ω',
    # Coptic-specific letters in the primary Coptic block (U+2CB2-U+2CBF)
    # These are the secondary encoding for shei/fei/khei/hori/gangia/shima/dei
    'ⲳ': 'σ',   # U+2CB3 dialect-P alef — used by some converters as shei
    'ⲵ': 'φ',   # U+2CB5 old Coptic ain — used by some converters as fei
    'ⲷ': 'χ',   # U+2CB7 cryptogrammic eie — used as khei
    'ⲹ': '',    # U+2CB9 dialect-P kapa — used as hori, drop
    'ⲻ': 'γ',   # U+2CBB dialect-P ni — used as gangia
    'ⲽ': 'κ',   # U+2CBD cryptogrammic ni — used as shima
    'ⲿ': 'τι',  # U+2CBF old Coptic oou — used as dei
    # Coptic-specific letters in the legacy "Greek and Coptic" block
    # (U+03E2-U+03EF) — most actual SCRIPTORIUM texts use these
    'ϣ': 'σ',
    'ϥ': 'φ',
    'ϧ': 'χ',
    'ϩ': '',
    'ϫ': 'γ',
    'ϭ': 'κ',
    'ϯ': 'τι',
}


def transliterate_coptic_to_greek(token):
    """Transliterate a Coptic token to the Greek alphabet for phonetic comparison.

    Strips diacritics (combining marks including the supralinear stroke
    U+0305), lowercases, then maps each Coptic character to its Greek
    equivalent.  Coptic-specific letters (shei, fei, khei, hori, gangia,
    shima, dei) are mapped to their nearest Greek phonetic equivalent.
    Non-Coptic characters (punctuation, already-Greek) pass through unchanged.
    """
    # NFC then NFD to strip combining marks (includes supralinear stroke)
    nfc = unicodedata.normalize('NFC', token.lower())
    nfd = unicodedata.normalize('NFD', nfc)
    stripped = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    result = []
    for ch in stripped:
        result.append(_COPTIC_TO_GREEK.get(ch, ch))
    return ''.join(result)


def find_crosslingual_phonetic_matches_cop_grc(source_units, target_units,
                                                source_language, target_language,
                                                min_similarity=0.65,
                                                min_token_len=3):
    """Find Coptic↔Greek token-level edit-distance matches via transliteration.

    Mirrors `find_crosslingual_phonetic_matches` (Greek↔Latin) but transliterates
    the Coptic side to the Greek alphabet rather than the Latin one.  Coptic
    and Greek alphabets are nearly identical, so this is mostly a Unicode
    remapping plus accent-stripping; only the 7 Coptic-specific letters
    require phonetic approximation.

    Returns dict: {(src_idx, tgt_idx): [{'source_token', 'target_token',
                    'source_original', 'target_original', 'similarity'}, ...]}
    """
    from rapidfuzz import fuzz

    # Determine which side is Coptic and which is Greek
    if source_language == 'cop' and target_language == 'grc':
        cop_units, grc_units = source_units, target_units
        cop_is_source = True
    elif source_language == 'grc' and target_language == 'cop':
        cop_units, grc_units = target_units, source_units
        cop_is_source = False
    else:
        return {}  # Not a Coptic-Greek pair — nothing to do

    threshold = int(min_similarity * 100)

    # Pre-transliterate Coptic tokens to Greek alphabet
    cop_translit = []  # [(unit_idx, [(original, transliterated), ...])]
    for i, unit in enumerate(cop_units):
        tokens = unit.get('tokens', [])
        pairs = []
        for tok in tokens:
            if len(tok) < min_token_len:
                continue
            tr = transliterate_coptic_to_greek(tok)
            if len(tr) >= min_token_len:
                pairs.append((tok, tr))
        cop_translit.append((i, pairs))

    # Normalise Greek tokens (strip accents, replace final sigma)
    grc_normalized = []  # [(unit_idx, [(original, normalised), ...])]
    for i, unit in enumerate(grc_units):
        tokens = unit.get('tokens', [])
        pairs = []
        for tok in tokens:
            if len(tok) < min_token_len:
                continue
            norm = normalize_greek(tok).replace('ς', 'σ')
            if len(norm) >= min_token_len:
                pairs.append((tok, norm))
        grc_normalized.append((i, pairs))

    # Build trigram index on Greek tokens for pre-filtering
    grc_trigram_index = {}  # trigram -> list of grc_unit indices
    for grc_idx, grc_pairs in grc_normalized:
        trigrams_seen = set()
        for _, norm in grc_pairs:
            for tri in _get_trigrams(norm):
                trigrams_seen.add(tri)
        for tri in trigrams_seen:
            if tri not in grc_trigram_index:
                grc_trigram_index[tri] = []
            grc_trigram_index[tri].append(grc_idx)

    # For each Coptic line, find Greek candidates via shared trigrams, then
    # run pairwise token edit-distance.
    results = {}  # (src_idx, tgt_idx) -> list of match dicts

    for cop_idx, cop_pairs in cop_translit:
        if not cop_pairs:
            continue

        candidate_counts = {}
        for _, tr in cop_pairs:
            for tri in _get_trigrams(tr):
                for grc_idx in grc_trigram_index.get(tri, []):
                    candidate_counts[grc_idx] = candidate_counts.get(grc_idx, 0) + 1

        # At least one shared trigram (Coptic-Greek pairs are usually
        # near-identical loanwords; a single shared trigram is sufficient)
        candidates = [idx for idx, cnt in candidate_counts.items() if cnt >= 1]

        for grc_idx in candidates:
            _, grc_pairs = grc_normalized[grc_idx]
            if not grc_pairs:
                continue

            token_matches = []
            used_cop = set()
            used_grc = set()

            all_sims = []
            for ci, (cop_orig, cop_tr) in enumerate(cop_pairs):
                for gi, (grc_orig, grc_norm) in enumerate(grc_pairs):
                    sim = fuzz.ratio(cop_tr, grc_norm)
                    if sim >= threshold:
                        all_sims.append((sim, ci, gi, cop_orig, cop_tr, grc_orig, grc_norm))

            # Greedy best-first assignment (each token used at most once)
            all_sims.sort(key=lambda x: x[0], reverse=True)
            for sim, ci, gi, cop_orig, cop_tr, grc_orig, grc_norm in all_sims:
                if ci in used_cop or gi in used_grc:
                    continue
                used_cop.add(ci)
                used_grc.add(gi)
                token_matches.append({
                    'source_original': cop_orig,
                    'target_original': grc_orig,
                    'source_token': cop_tr,
                    'target_token': grc_norm,
                    'similarity': sim / 100.0,
                })

            if token_matches:
                if cop_is_source:
                    pair_key = (cop_idx, grc_idx)
                else:
                    pair_key = (grc_idx, cop_idx)
                results[pair_key] = token_matches

    return results


def find_crosslingual_phonetic_matches(source_units, target_units,
                                        source_language, target_language,
                                        min_similarity=0.70, min_token_len=3,
                                        cancellation=None):
    """Find cross-lingual token-level edit-distance matches via transliteration.

    Transliterates Greek tokens to Latin characters, then compares each
    transliterated token against target tokens using RapidFuzz.

    Returns dict: {(src_idx, tgt_idx): [{'source_token', 'target_token',
                    'source_original', 'target_original', 'similarity'}, ...]}
    """
    from rapidfuzz import fuzz

    # Determine which side is Greek
    if source_language == 'grc':
        grc_units, lat_units = source_units, target_units
        grc_is_source = True
    elif target_language == 'grc':
        grc_units, lat_units = target_units, source_units
        grc_is_source = False
    else:
        return {}  # No Greek side — nothing to do

    threshold = int(min_similarity * 100)

    # Pre-transliterate Greek tokens and normalize Latin tokens
    grc_translit = []  # [(unit_idx, [(original, transliterated), ...])]
    for i, unit in enumerate(grc_units):
        if cancellation:
            cancellation.check()
        tokens = unit.get('tokens', [])
        pairs = []
        for tok in tokens:
            if len(tok) < min_token_len:
                continue
            tr = transliterate_greek_to_latin(tok)
            if len(tr) >= min_token_len:
                pairs.append((tok, tr))
        grc_translit.append((i, pairs))

    lat_normalized = []  # [(unit_idx, [(original, normalized), ...])]
    for i, unit in enumerate(lat_units):
        if cancellation:
            cancellation.check()
        tokens = unit.get('tokens', [])
        pairs = []
        for tok in tokens:
            if len(tok) < min_token_len:
                continue
            # Normalize: lowercase, v→u for classical Latin
            norm = tok.lower().replace('v', 'u')
            pairs.append((tok, norm))
        lat_normalized.append((i, pairs))

    # Build trigram index on Latin tokens for pre-filtering
    lat_trigram_index = {}  # trigram -> set of lat_unit indices
    for lat_idx, lat_pairs in lat_normalized:
        if cancellation:
            cancellation.check()
        trigrams_seen = set()
        for _, norm in lat_pairs:
            for tri in _get_trigrams(norm):
                trigrams_seen.add(tri)
        for tri in trigrams_seen:
            if tri not in lat_trigram_index:
                lat_trigram_index[tri] = []
            lat_trigram_index[tri].append(lat_idx)

    # For each Greek line, find Latin candidates via shared trigrams, then
    # run pairwise token edit-distance
    results = {}  # (src_idx, tgt_idx) -> list of match dicts

    for grc_idx, grc_pairs in grc_translit:
        if cancellation:
            cancellation.check()
        if not grc_pairs:
            continue

        # Candidate Latin lines sharing trigrams with this Greek line
        candidate_counts = {}
        for _, tr in grc_pairs:
            for tri in _get_trigrams(tr):
                for lat_idx in lat_trigram_index.get(tri, []):
                    candidate_counts[lat_idx] = candidate_counts.get(lat_idx, 0) + 1

        # Require at least 1 shared trigram (cross-lingual echoes can be a
        # single token pair, e.g. μῆνιν/mene sharing only trigram "men")
        candidates = [idx for idx, cnt in candidate_counts.items() if cnt >= 1]

        for lat_idx in candidates:
            if cancellation:
                cancellation.check()
            _, lat_pairs = lat_normalized[lat_idx]
            if not lat_pairs:
                continue

            token_matches = []
            used_grc = set()
            used_lat = set()

            # Find best-matching token pairs
            all_sims = []
            for gi, (grc_orig, grc_tr) in enumerate(grc_pairs):
                for li, (lat_orig, lat_norm) in enumerate(lat_pairs):
                    sim = fuzz.ratio(grc_tr, lat_norm)
                    if sim >= threshold:
                        all_sims.append((sim, gi, li, grc_orig, grc_tr, lat_orig, lat_norm))

            # Greedy best-first assignment (each token used once)
            all_sims.sort(key=lambda x: x[0], reverse=True)
            for sim, gi, li, grc_orig, grc_tr, lat_orig, lat_norm in all_sims:
                if gi in used_grc or li in used_lat:
                    continue
                used_grc.add(gi)
                used_lat.add(li)
                # The per-token match dict's source / target fields must
                # match the orientation of the pair_key below. When Latin
                # is the source (grc_is_source=False), swap the labels so
                # source_original is the Latin token and target_original is
                # the Greek token. Previously these were hardcoded to the
                # Greek-source case, which silently mislabeled every
                # Latin-source / Greek-target search and broke downstream
                # highlighting in one direction.
                if grc_is_source:
                    token_matches.append({
                        'source_original': grc_orig,
                        'target_original': lat_orig,
                        'source_token': grc_tr,
                        'target_token': lat_norm,
                        'similarity': sim / 100.0,
                    })
                else:
                    token_matches.append({
                        'source_original': lat_orig,
                        'target_original': grc_orig,
                        'source_token': lat_norm,
                        'target_token': grc_tr,
                        'similarity': sim / 100.0,
                    })

            if token_matches:
                # Map back to (src_idx, tgt_idx) in original orientation
                if grc_is_source:
                    pair_key = (grc_idx, lat_idx)
                else:
                    pair_key = (lat_idx, grc_idx)
                results[pair_key] = token_matches

    return results

from collections import defaultdict, Counter
import os
import json
from backend.logging_config import get_logger
from backend.zipf import find_zipf_elbow
from backend.worker_util import safe_worker_count
from backend.search_cancellation import cancellable_pool_map

logger = get_logger('matcher')


def _get_trigrams(token):
    """Extract character trigrams (standalone for pickling)."""
    if len(token) < 3:
        return set()
    token = token.lower()
    return set(token[i:i+3] for i in range(len(token) - 2))


def _sound_chunk_worker(args):
    """Process a chunk of source units for sound matching."""
    chunk_src, tgt_trigram_cache, min_sound_score, top_n_per_source = args

    matches = []
    for src_idx, src_tokens, src_trigrams in chunk_src:
        if not src_trigrams:
            continue

        src_candidates = []
        for tgt_idx, (tgt_tokens, tgt_trigrams) in enumerate(tgt_trigram_cache):
            if not tgt_trigrams:
                continue
            intersection = len(src_trigrams & tgt_trigrams)
            union = len(src_trigrams | tgt_trigrams)
            sim = intersection / union if union > 0 else 0
            if sim >= min_sound_score:
                src_candidates.append((tgt_idx, tgt_tokens, sim))

        src_candidates.sort(key=lambda x: x[2], reverse=True)
        for tgt_idx, tgt_tokens, sim in src_candidates[:top_n_per_source]:
            tgt_trigrams = tgt_trigram_cache[tgt_idx][1]
            shared = sorted(
                list(src_trigrams & tgt_trigrams),
                key=lambda t: sum(1 for tok in src_tokens + tgt_tokens
                                  if t in tok.lower()),
                reverse=True
            )[:10]

            trigram_tokens = {}
            for tri in shared:
                src_toks = [t for t in src_tokens if tri in t.lower()]
                tgt_toks = [t for t in tgt_tokens if tri in t.lower()]
                if src_toks and tgt_toks:
                    for st in src_toks[:2]:
                        for tt in tgt_toks[:2]:
                            if st.lower() != tt.lower():
                                trigram_tokens[tri] = (st, tt)
                                break
                        if tri in trigram_tokens:
                            break

            matches.append({
                'source_idx': src_idx,
                'target_idx': tgt_idx,
                'matched_lemmas': [],
                'match_basis': 'sound',
                'sound_score': sim,
                'shared_trigrams': shared,
                'trigram_tokens': trigram_tokens
            })

    return matches


def _edit_distance_chunk_worker(args):
    """Process a chunk of source units for edit distance matching.

    Runs in a separate process for true CPU parallelism.
    """
    from rapidfuzz import fuzz

    (chunk, tgt_token_lists, trigram_to_targets,
     min_similarity, min_matches, include_exact_in_count,
     min_shared_trigrams, top_n_per_source) = args

    threshold = int(min_similarity * 100)
    matches = []
    comparisons = 0

    for src_idx, src_tokens in chunk:
        if not src_tokens:
            continue

        # Find candidate targets sharing trigrams
        candidate_targets = Counter()
        for token in src_tokens:
            for trigram in _get_trigrams(token):
                for tgt_idx in trigram_to_targets.get(trigram, ()):
                    candidate_targets[tgt_idx] += 1

        filtered = [i for i, c in candidate_targets.items()
                    if c >= min_shared_trigrams]

        src_candidates = []
        for tgt_idx in filtered:
            tgt_tokens = tgt_token_lists[tgt_idx]
            if not tgt_tokens:
                continue

            comparisons += 1

            # Fuzzy matching (inline to avoid pickling feature_extractor)
            fuzzy_matches = []
            for st in src_tokens:
                if len(st) < 3:
                    continue
                for tt in tgt_tokens:
                    if len(tt) < 3:
                        continue
                    sim = fuzz.ratio(st, tt)
                    if sim >= threshold and st != tt:
                        fuzzy_matches.append({
                            'source_token': st,
                            'target_token': tt,
                            'similarity': sim / 100.0
                        })

            # Count exact matches
            src_norm = {normalize_greek(t) for t in src_tokens}
            tgt_norm = {normalize_greek(t) for t in tgt_tokens}
            exact_count = len(src_norm & tgt_norm) if include_exact_in_count else 0
            unique_src = set(m['source_token'] for m in fuzzy_matches)
            unique_tgt = set(m['target_token'] for m in fuzzy_matches)
            num_fuzzy = min(len(unique_src), len(unique_tgt))
            num_total = exact_count + num_fuzzy

            if num_total >= min_matches:
                avg_sim = (sum(m['similarity'] for m in fuzzy_matches)
                           / len(fuzzy_matches)) if fuzzy_matches else 1.0
                src_candidates.append(
                    (tgt_idx, tgt_tokens, fuzzy_matches, avg_sim, num_total)
                )

        src_candidates.sort(key=lambda x: (x[4], x[3]), reverse=True)
        for tgt_idx, tgt_tokens, fuzzy_matches, avg_sim, num_pairs in \
                src_candidates[:top_n_per_source]:
            matches.append({
                'source_idx': src_idx,
                'target_idx': tgt_idx,
                'matched_lemmas': [],
                'match_basis': 'edit_distance',
                'edit_score': avg_sim,
                'num_matches': num_pairs,
                'fuzzy_matches': fuzzy_matches[:8]
            })

    return matches, comparisons

DEFAULT_LATIN_STOP_WORDS_LIST = [
    'et', 'in', 'est', 'non', 'ut', 'cum', 'ad', 'sed', 'si', 'quod',
    'qui', 'quae', 'que', 'de', 'ex', 'per', 'ab', 'ac', 'atque',
    'aut', 'nec', 'neque', 'enim', 'nam', 'iam', 'tamen', 'autem',
    'quidem', 'hic', 'haec', 'hoc', 'ille', 'illa', 'illud', 'is', 
    'ea', 'id', 'ipse', 'ipsa', 'ipsum', 'se', 'suus', 'sua', 'suum',
    'esse', 'sum', 'fui', 'sunt', 'erat', 'erant', 'fuit', 'ait', 'a', 'o',
    'te', 'tu', 'me', 'ego', 'nos', 'vos', 'noster', 'vester',
    'omnis', 'omnia', 'omnes', 'nullus', 'nulla', 'nullum',
    'unus', 'duo', 'tres', 'primus', 'secundus', 'tertius',
    'ubi', 'nunc', 'sic', 'tam', 'tum', 'ita', 'ibi', 'hinc', 'inde',
    'quo', 'qua', 'quam', 'quando', 'unde', 'cur', 'ergo', 'igitur'
]

DEFAULT_GREEK_STOP_WORDS_LIST = [
    # Particles and conjunctions
    'και', 'δε', 'τε', 'γαρ', 'μεν', 'δη', 'ου', 'ουκ', 'ουχ', 'μη',
    'αλλα', 'αλλ', 'ουδε', 'μηδε', 'ουτε', 'μητε', 'ειτε', 'ητοι',
    'νυ', 'τοι', 'περ', 'γε', 'κε', 'κεν', 'ρα',
    # Prepositions
    'εν', 'εις', 'εκ', 'εξ', 'προς', 'απο', 'περι', 'κατα',
    'μετα', 'δια', 'υπο', 'υπερ', 'παρα', 'επι', 'αντι', 'συν', 'προ',
    # Elided forms (base without final vowel)
    'αλλ', 'αρ', 'επ', 'απ', 'κατ', 'μετ', 'παρ', 'υπ', 'αμφ', 'αντ',
    # Article forms (all cases)
    'ο', 'η', 'το', 'οι', 'αι', 'τα', 'τον', 'την', 'του', 'της',
    'τω', 'τη', 'τοις', 'ταις', 'τους', 'τας', 'των',
    # Relative/demonstrative pronouns
    'ος', 'ης', 'ον', 'οστις', 'ητις', 'οτι', 'ως', 'αν', 'ει',
    'ου', 'ης', 'ω', 'ην', 'οις', 'αις', 'ους', 'ας', 'ων', 'α',
    # αυτος forms (all cases)
    'αυτος', 'αυτη', 'αυτο', 'αυτον', 'αυτην', 'αυτου', 'αυτης',
    'αυτω', 'αυτοι', 'αυται', 'αυτα', 'αυτους', 'αυτας', 'αυτων', 'αυτοις', 'αυταις',
    # ουτος forms
    'ουτος', 'αυτη', 'τουτο', 'τουτον', 'ταυτην', 'τουτου', 'ταυτης',
    'τουτω', 'ταυτη', 'ουτοι', 'αυται', 'ταυτα', 'τουτους', 'ταυτας', 'τουτων', 'τουτοις', 'ταυταις',
    # εκεινος forms  
    'εκεινος', 'εκεινη', 'εκεινο', 'εκεινον', 'εκεινην', 'εκεινου', 'εκεινης',
    'εκεινω', 'εκεινοι', 'εκειναι', 'εκεινα', 'εκεινους', 'εκεινας', 'εκεινων', 'εκεινοις', 'εκειναις',
    # Personal pronouns
    'εγω', 'εμε', 'με', 'εμου', 'μου', 'εμοι', 'μοι',
    'συ', 'σε', 'σου', 'σοι',
    'ημεις', 'ημας', 'ημων', 'ημιν',
    'υμεις', 'υμας', 'υμων', 'υμιν',
    # τις/τι (indefinite/interrogative)
    'τις', 'τι', 'τινα', 'τινος', 'τινι', 'τινες', 'τινων', 'τισι', 'τισιν',
    # ειμι (to be) forms
    'εστι', 'εστιν', 'ειμι', 'ην', 'ησαν', 'ει', 'εσμεν', 'εστε', 'εισι', 'εισιν',
    # Common verbs - βαινω (go), φημι (say), ερχομαι (come)
    'βη', 'βαν', 'βας', 'βησαν', 'εβη', 'φη', 'εφη', 'φησι', 'ηλθε', 'ηλθον',
    # Common adverbs
    'νυν', 'ετι', 'ουν', 'αρα', 'τοτε', 'ποτε', 'πω', 'πως', 'που', 'οπου', 'οθεν',
    'ενθα', 'ενθεν', 'οπως', 'ωστε', 'ουτω', 'ουτως'
]

DEFAULT_ENGLISH_STOP_WORDS_LIST = [
    # Modern common words
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
    'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
    'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
    'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their', 'what',
    'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go', 'me',
    'when', 'make', 'can', 'like', 'no', 'just', 'him', 'know', 'take', 'into',
    'your', 'some', 'could', 'them', 'see', 'other', 'than', 'then', 'now', 'its',
    'is', 'am', 'are', 'was', 'were', 'been', 'being', 'has', 'had', 'having',
    # Early Modern / Archaic English (Shakespeare, Milton, etc.)
    'thou', 'thee', 'thy', 'thine', 'thyself', 'ye', 'art', 'doth', 'dost',
    'hath', 'hast', 'shalt', 'wilt', 'canst', 'wouldst', 'shouldst', 'couldst',
    'didst', 'hadst', 'mayst', 'mightst', 'wast', 'wert', 'wherefore', 'wherein',
    'whereon', 'thereof', 'therein', 'herein', 'hereby', 'hither', 'thither',
    'whither', 'hence', 'thence', 'ere', 'oft', 'nay', 'yea', 'aye', 'prithee',
    'methinks', 'forsooth', 'verily', 'tis', 'twas', 'twere', 'twill', 'twould',
    'o', 'oh', 'ah', 'alas', 'lo', 'behold', 'nought', 'naught', 'upon', 'unto',
    'hither', 'hence', 'thus', 'such', 'each', 'every', 'both', 'own', 'same',
    'much', 'more', 'most', 'yet', 'still', 'even', 'also', 'too', 'very',
    'here', 'how', 'why', 'where', 'whence', 'whether', 'while', 'whilst',
    'though', 'although', 'because', 'since', 'before', 'after', 'until', 'till',
    'shall', 'should', 'may', 'might', 'must', 'need', 'dare', 'let', 'lest',
    'nor', 'neither', 'either', 'none', 'any', 'many', 'few', 'less', 'least'
]

DEFAULT_LATIN_STOP_WORDS = set(DEFAULT_LATIN_STOP_WORDS_LIST)
DEFAULT_GREEK_STOP_WORDS = set(DEFAULT_GREEK_STOP_WORDS_LIST)
DEFAULT_ENGLISH_STOP_WORDS = set(DEFAULT_ENGLISH_STOP_WORDS_LIST)


_greek_display_map = None


def _get_greek_display_map():
    """Load the accentless -> polytonic display map for the Greek stoplist.

    Display only. The matcher itself keeps filtering on the accentless
    normalized forms; this restores accents and breathings for the Help page.
    Returns {} if the data file is missing, so display falls back to the
    normalized word.
    """
    global _greek_display_map
    if _greek_display_map is None:
        path = os.path.join(os.path.dirname(__file__), 'data', 'greek_stoplist_display.json')
        try:
            with open(path, encoding='utf-8') as f:
                _greek_display_map = json.load(f)
        except (OSError, ValueError):
            _greek_display_map = {}
    return _greek_display_map


def get_curated_stoplists():
    """Return the primary matcher stoplists in a display-safe API shape.

    The matcher keeps ordered lists because manual stoplist sizes use their
    ranking, while matching itself uses sets. De-duplicate the public view
    without changing matching behavior or manual-list ordering. Each language
    also carries a ``display`` list: the same words in the form meant for
    reading. For Greek that is the polytonic (accented) form; for Latin and
    English it is identical to ``words``.
    """
    stoplists = (
        ('la', 'Latin', DEFAULT_LATIN_STOP_WORDS_LIST),
        ('grc', 'Greek', DEFAULT_GREEK_STOP_WORDS_LIST),
        ('en', 'English', DEFAULT_ENGLISH_STOP_WORDS_LIST),
    )
    greek_display = _get_greek_display_map()
    result = {}
    for language, label, words in stoplists:
        deduped = list(dict.fromkeys(words))
        if language == 'grc':
            display = [greek_display.get(w, w) for w in deduped]
        else:
            display = list(deduped)
        result[language] = {
            'label': label,
            'words': deduped,
            'display': display,
            'count': len(deduped),
        }
    return result


class Matcher:
    def __init__(self):
        self.synonym_dict = {}
        self.stoplist_cache = {}
    
    def load_synonyms(self, filepath):
        """Load synonym dictionary for semantic matching"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('\t')
                    if len(parts) >= 2:
                        word = parts[0]
                        synonyms = parts[1].split(',')
                        self.synonym_dict[word] = set(synonyms)
        except FileNotFoundError:
            pass
    
    def build_stoplist(self, source_units, target_units, stoplist_basis='source_target', language='la', corpus_frequencies=None, match_type='lemma', cancellation=None):
        """Build stoplist using Zipf elbow detection based on specified text basis"""
        # For exact match, use tokens; otherwise use lemmas
        use_tokens = (match_type == 'exact')
        feature_key = 'tokens' if use_tokens else 'lemmas'
        
        if stoplist_basis == 'corpus' and corpus_frequencies and not use_tokens:
            freq = Counter()
            freq.update(corpus_frequencies)
        elif stoplist_basis == 'source':
            all_features = []
            for unit in source_units:
                if cancellation:
                    cancellation.check()
                all_features.extend(unit.get(feature_key, unit.get('lemmas', [])))
            freq = Counter(all_features)
        elif stoplist_basis == 'target':
            all_features = []
            for unit in target_units:
                if cancellation:
                    cancellation.check()
                all_features.extend(unit.get(feature_key, unit.get('lemmas', [])))
            freq = Counter(all_features)
        else:
            all_features = []
            for unit in source_units + target_units:
                if cancellation:
                    cancellation.check()
                all_features.extend(unit.get(feature_key, unit.get('lemmas', [])))
            freq = Counter(all_features)
        
        # Exact match on tokens needs more aggressive stoplist since token distributions
        # are more gradual than lemma distributions (accents create variants, and 
        # articles/pronouns/conjunctions have many inflected forms)
        if use_tokens:
            # For tokens: Zipf elbow often finds early cutoff, but function words
            # extend much further due to inflection. Use both elbow detection AND
            # a frequency-based minimum to catch all high-frequency function words
            zipf_stops = find_zipf_elbow(freq, min_stopwords=50, max_stopwords=120)
            
            # Additionally, stop all tokens appearing 40+ times - this catches
            # articles, pronouns, conjunctions, common verbs like φάτο ("said"),
            # forms of "or" (ἤ, ἠέ), demonstratives (τάδε), etc.
            # For exact match, we need aggressive filtering since inflected forms
            # spread frequency across many surface tokens
            high_freq_stops = set(word for word, count in freq.items() if count >= 40)
            zipf_stops = zipf_stops.union(high_freq_stops)
        else:
            zipf_stops = find_zipf_elbow(freq, min_stopwords=10, max_stopwords=50)
        
        if language == 'la':
            base_stops = DEFAULT_LATIN_STOP_WORDS
        elif language == 'grc':
            base_stops = DEFAULT_GREEK_STOP_WORDS
        elif language == 'cop':
            try:
                from backend.coptic.stopwords import COPTIC_STOP_WORDS
                base_stops = COPTIC_STOP_WORDS
            except ImportError:
                base_stops = set()
            if len(freq) < 2000:
                zipf_stops = set()
        else:
            base_stops = DEFAULT_ENGLISH_STOP_WORDS

        return zipf_stops.union(base_stops)
    
    def build_stoplist_auto(self, source_units, target_units, language='la'):
        """Build automatic stoplist using Zipf elbow detection (backward compatible)"""
        return self.build_stoplist(source_units, target_units, 'source_target', language)
    
    def build_stoplist_manual(self, units, stoplist_size=10, language='la', match_type='lemma'):
        """Build manual stoplist with fixed size"""
        if stoplist_size == 0:
            return set()
        
        # For exact match, use tokens; otherwise use lemmas
        use_tokens = (match_type == 'exact')
        feature_key = 'tokens' if use_tokens else 'lemmas'
        
        all_features = []
        for unit in units:
            all_features.extend(unit.get(feature_key, unit.get('lemmas', [])))
        
        freq = Counter(all_features)
        
        if language == 'la':
            base_stops = set(DEFAULT_LATIN_STOP_WORDS_LIST[:stoplist_size])
        elif language == 'grc':
            base_stops = set(DEFAULT_GREEK_STOP_WORDS_LIST[:stoplist_size])
        elif language == 'cop':
            try:
                from backend.coptic.stopwords import COPTIC_STOP_WORDS
                base_stops = set(list(COPTIC_STOP_WORDS)[:stoplist_size])
            except ImportError:
                base_stops = set()
        else:
            base_stops = set(DEFAULT_ENGLISH_STOP_WORDS_LIST[:stoplist_size])
        
        top_freq = set(w for w, _ in freq.most_common(stoplist_size))
        
        return base_stops.union(top_freq)
    
    def find_matches(self, source_units, target_units, settings=None,
                     corpus_frequencies=None, cancellation=None):
        """Find matching lemmas between source and target texts"""
        settings = settings or {}
        min_matches = settings.get('min_matches', 2)
        match_type = settings.get('match_type', 'lemma')
        stoplist_basis = settings.get('stoplist_basis', 'source_target')
        language = settings.get('language', 'la')
        max_distance = settings.get('max_distance', 999)
        stoplist_size = settings.get('stoplist_size', 0)
        custom_stopwords = settings.get('custom_stopwords', '')
        if cancellation:
            cancellation.check()
        
        if match_type == 'sound':
            return self.find_sound_matches(source_units, target_units, settings,
                                           cancellation=cancellation)
        
        if stoplist_size == -1:
            stop_words = set()
        elif stoplist_size > 0:
            stop_words = self.build_stoplist_manual(source_units + target_units, stoplist_size, language, match_type)
        else:
            stop_words = self.build_stoplist(
                source_units, target_units, stoplist_basis, language,
                corpus_frequencies, match_type, cancellation)
        
        if custom_stopwords:
            custom_list = [w.strip().lower() for w in custom_stopwords.split(',') if w.strip()]
            stop_words = stop_words.union(set(custom_list))

        # Coptic uses sub-word tokenisation (one morpheme per token), so the
        # corpus-frequency-driven Zipf stoplist alone leaves many bound
        # function morphemes (articles, possessives, copulas) un-filtered.
        # Always merge in the curated COPTIC_STOP_WORDS list.
        if language == 'cop':
            try:
                from backend.coptic.stopwords import COPTIC_STOP_WORDS
                stop_words = stop_words | COPTIC_STOP_WORDS
            except Exception:
                pass

        # Create normalized stopwords sets for language-specific matching
        if language == 'grc':
            normalized_stop_words = set(normalize_greek(w) for w in stop_words)
        elif language == 'la':
            normalized_stop_words = set(normalize_latin(w) for w in stop_words)
        else:
            normalized_stop_words = set(w.lower() for w in stop_words)
        
        def is_stopword(word):
            """Check if word is a stopword, using language-specific normalization"""
            if word in stop_words:
                return True
            if language == 'grc':
                normalized = normalize_greek(word)
                if normalized in normalized_stop_words:
                    return True
                clean_word = normalized.rstrip("'᾽'")
                if clean_word in normalized_stop_words:
                    return True
            elif language == 'la':
                # Latin u/v normalization
                normalized = normalize_latin(word)
                if normalized in normalized_stop_words:
                    return True
            return False
        
        target_index = defaultdict(list)
        for i, unit in enumerate(target_units):
            if cancellation:
                cancellation.check()
            if match_type == 'exact':
                features = set(unit['tokens'])
            else:
                features = set(unit['lemmas'])
            
            for feature in features:
                if not is_stopword(feature) and len(feature) > 2:
                    target_index[feature].append(i)
                    
                    if match_type == 'syn' and feature in self.synonym_dict:
                        for syn in self.synonym_dict[feature]:
                            target_index[syn].append(i)
        
        matches = []
        
        for src_idx, src_unit in enumerate(source_units):
            if cancellation:
                cancellation.check()
            if match_type == 'exact':
                src_features = set(f for f in src_unit['tokens'] 
                                  if not is_stopword(f) and len(f) > 2)
            else:
                src_features = set(f for f in src_unit['lemmas'] 
                                  if not is_stopword(f) and len(f) > 2)
            
            target_matches = defaultdict(set)
            
            for feature in src_features:
                if feature in target_index:
                    for tgt_idx in target_index[feature]:
                        target_matches[tgt_idx].add(feature)
                
                if match_type == 'syn' and feature in self.synonym_dict:
                    for syn in self.synonym_dict[feature]:
                        if syn in target_index:
                            for tgt_idx in target_index[syn]:
                                target_matches[tgt_idx].add(feature)
            
            for tgt_idx, matched_features in target_matches.items():
                tgt_unit = target_units[tgt_idx]
                # Adjacency-aware effective match count, gated to Coptic for now.
                # Sub-word tokenisation splits fixed Coptic compound verbs
                # (ⲁϩⲉⲣⲁⲧ- "stand-foot-", ϣⲛϩⲧⲏ- "ask-heart-", ⲣϩⲟⲧⲉ ϩⲏⲧ-
                # "do-fear-heart-") into 2-3 morphemes that each match
                # individually, inflating the lemma count above min_matches=2
                # on a single underlying compound. If two matched lemmas
                # appear at adjacent positions in BOTH source and target,
                # they're effectively a co-attested compound and should
                # count as one match for the threshold.
                effective_count = len(matched_features)
                if language == 'cop' and len(matched_features) >= 2:
                    effective_count = self._effective_match_count_with_adjacency(
                        src_unit, tgt_unit, matched_features, match_type
                    )
                if effective_count >= min_matches:
                    src_distance = self._get_feature_span(src_unit, matched_features, match_type)
                    tgt_distance = self._get_feature_span(tgt_unit, matched_features, match_type)

                    if src_distance <= max_distance and tgt_distance <= max_distance:
                        matches.append({
                            'source_idx': src_idx,
                            'target_idx': tgt_idx,
                            'matched_lemmas': list(matched_features)
                        })
        
        return matches, len(stop_words)
    
    def find_sound_matches(self, source_units, target_units, settings=None,
                           cancellation=None):
        """
        Find matches based on sound similarity using character trigrams.
        Parallelized for large text pairs.
        """
        settings = settings or {}
        min_sound_score = settings.get('min_sound_score', 0.25)
        max_results = settings.get('max_results', 500)
        top_n_per_source = settings.get('sound_top_n', 10)

        src_trigram_cache = []
        for src_unit in source_units:
            if cancellation:
                cancellation.check()
            src_tokens = [t for t in src_unit.get('tokens', []) if len(t) >= 3]
            src_trigrams = set()
            for token in src_tokens:
                src_trigrams.update(_get_trigrams(token))
            src_trigram_cache.append((src_tokens, src_trigrams))

        tgt_trigram_cache = []
        for tgt_unit in target_units:
            if cancellation:
                cancellation.check()
            tgt_tokens = [t for t in tgt_unit.get('tokens', []) if len(t) >= 3]
            tgt_trigrams = set()
            for token in tgt_tokens:
                tgt_trigrams.update(_get_trigrams(token))
            tgt_trigram_cache.append((tgt_tokens, tgt_trigrams))

        num_source = len(source_units)
        num_workers = safe_worker_count()
        use_parallel = num_source >= 200 and num_workers > 1

        if use_parallel:
            indexed_src = [(i, toks, tris)
                           for i, (toks, tris) in enumerate(src_trigram_cache)]
            chunk_size = max(1, len(indexed_src) // num_workers)
            chunks = [indexed_src[i:i + chunk_size]
                      for i in range(0, len(indexed_src), chunk_size)]

            worker_args = [(chunk, tgt_trigram_cache, min_sound_score,
                            top_n_per_source) for chunk in chunks]

            matches = []
            for chunk_matches in cancellable_pool_map(
                    _sound_chunk_worker, worker_args, num_workers, cancellation):
                matches.extend(chunk_matches)
        else:
            indexed_src = [(i, toks, tris)
                           for i, (toks, tris) in enumerate(src_trigram_cache)]
            args = (indexed_src, tgt_trigram_cache, min_sound_score,
                    top_n_per_source)
            if cancellation:
                cancellation.check()
            matches = _sound_chunk_worker(args)

        matches.sort(key=lambda x: x.get('sound_score', 0), reverse=True)

        if max_results > 0:
            matches = matches[:max_results]

        return matches, 0
    def find_quotation_matches(self, source_units, target_units, settings=None):
        """
        Find runs of consecutive identical surface tokens between source and target lines.

        Detects verbatim quotation that other channels miss because individual word
        matches get demoted by the rarity penalty (Phase 5 diagnosis, V6 Coptic project).
        A run of 3+ consecutive identical words is intrinsically distinctive — the
        probability of 3 consecutive same words by chance is ~10^-9 for common
        vocabulary — so this channel intentionally does NOT apply IDF weighting.

        Punctuation-tolerant: tokens consisting only of punctuation marks (periods,
        commas, semicolons, etc.) are stripped from the token sequence before
        run detection.  This handles the case where one text has a period or
        comma inside a quoted run that the other doesn't — common in biblical
        text where one translator punctuates more heavily than another.

        Args:
            source_units, target_units: V6 unit dicts with 'tokens' field
            settings:
                quotation_min_run (int, default 3): minimum consecutive matching
                    tokens required to register a quotation
                quotation_max_results (int, default 50000): per-channel cap

        Returns:
            (matches, 0) where each match is:
                {'source_idx', 'target_idx', 'match_basis': 'quotation',
                 'run_length', 'run_text', 'source_position', 'target_position',
                 'quotation_score'}
            quotation_score = run_length / 5.0 (uncapped — 3-word run = 0.6,
                5-word = 1.0, 10-word = 2.0, etc.)
        """
        from collections import defaultdict

        settings = settings or {}
        min_run = settings.get('quotation_min_run', 3)
        max_results = settings.get('quotation_max_results', 50000)

        # Punctuation marker characters. Tokens consisting only of these are
        # treated as not-tokens for purposes of run detection. Source/target
        # positions are kept aligned with the original token list so highlight
        # offsets remain correct in scorer output.
        _PUNCT_CHARS = set('.,;:!?·•‧⸱"\'`’‘“”«»()[]{}<>—–-')

        def _is_punct(tok):
            return bool(tok) and all(c in _PUNCT_CHARS for c in tok)

        # Normalize tokens once (lowercase) and build punctuation-stripped views
        # paired with original positions, so the matcher operates on a
        # "content-token" sequence but can report positions in the full token list.
        src_toks_raw = [[t.lower() for t in u.get('tokens', [])] for u in source_units]
        tgt_toks_raw = [[t.lower() for t in u.get('tokens', [])] for u in target_units]

        def _content_view(toks):
            """Return (content_tokens, original_positions) skipping punctuation-only tokens."""
            content, positions = [], []
            for i, t in enumerate(toks):
                if not _is_punct(t):
                    content.append(t)
                    positions.append(i)
            return content, positions

        src_views = [_content_view(t) for t in src_toks_raw]
        tgt_views = [_content_view(t) for t in tgt_toks_raw]

        # Aliases — downstream code uses the content-only views for matching but
        # records run positions back in the original token list via the positions array.
        src_toks = [v[0] for v in src_views]
        src_orig_positions = [v[1] for v in src_views]
        tgt_toks = [v[0] for v in tgt_views]
        tgt_orig_positions = [v[1] for v in tgt_views]

        # Build target n-gram index: tuple of MIN_RUN consecutive tokens -> [(tgt_idx, pos)]
        tgt_ngram_index = defaultdict(list)
        for tgt_idx, toks in enumerate(tgt_toks):
            for i in range(len(toks) - min_run + 1):
                ng = tuple(toks[i:i + min_run])
                tgt_ngram_index[ng].append((tgt_idx, i))

        # For each source position, look up MIN_RUN-gram in target index;
        # extend forward to find the maximum run length.
        best_per_pair = {}  # (src_idx, tgt_idx) -> best match dict
        for src_idx, s_toks in enumerate(src_toks):
            for s_pos in range(len(s_toks) - min_run + 1):
                ng = tuple(s_toks[s_pos:s_pos + min_run])
                hits = tgt_ngram_index.get(ng)
                if not hits:
                    continue
                for tgt_idx, t_pos in hits:
                    t_toks = tgt_toks[tgt_idx]
                    run_len = min_run
                    while (s_pos + run_len < len(s_toks) and
                           t_pos + run_len < len(t_toks) and
                           s_toks[s_pos + run_len] == t_toks[t_pos + run_len]):
                        run_len += 1
                    key = (src_idx, tgt_idx)
                    prev = best_per_pair.get(key)
                    if prev is None or run_len > prev['run_length']:
                        # Translate the content-token positions back to original
                        # token positions in source_units / target_units so the
                        # scorer highlights the correct (punctuation-inclusive)
                        # tokens.
                        s_orig = src_orig_positions[src_idx]
                        t_orig = tgt_orig_positions[tgt_idx]
                        s_pos_orig = s_orig[s_pos] if s_pos < len(s_orig) else s_pos
                        t_pos_orig = t_orig[t_pos] if t_pos < len(t_orig) else t_pos
                        best_per_pair[key] = {
                            'source_idx': src_idx,
                            'target_idx': tgt_idx,
                            'match_basis': 'quotation',
                            'run_length': run_len,
                            'run_text': list(s_toks[s_pos:s_pos + run_len]),
                            'source_position': s_pos_orig,
                            'target_position': t_pos_orig,
                            'quotation_score': run_len / 5.0,
                            'matched_lemmas': [],
                        }

        matches = list(best_per_pair.values())
        # Sort by run length descending so the strongest quotations are kept first
        matches.sort(key=lambda m: -m['run_length'])
        if max_results > 0 and len(matches) > max_results:
            matches = matches[:max_results]
        return matches, 0

    def find_edit_distance_matches(self, source_units, target_units, settings=None,
                                   cancellation=None):
        """
        Find matches based on edit distance (fuzzy string matching).
        Like Filum from QCL: finds phrases with multiple fuzzy word matches.
        Uses trigram-based candidate filtering to avoid O(n²) full comparison.
        Requires min_matches (default 2) fuzzy word pairs per match.
        """
        import time
        from collections import defaultdict
        
        settings = settings or {}
        if cancellation:
            cancellation.check()
        min_similarity = settings.get('min_edit_similarity', 0.7)
        min_matches = settings.get('min_matches', 2)
        max_results = settings.get('max_results', 500)
        top_n_per_source = settings.get('edit_top_n', 10)
        stoplist_size = settings.get('stoplist_size', 0)
        include_exact_in_count = settings.get('edit_include_exact', True)  # Count exact matches toward min_matches (Filum-like)
        min_shared_trigrams = settings.get('edit_min_shared_trigrams', 2)
        
        num_source = len(source_units)
        num_target = len(target_units)
        
        logger.info(f"[EDIT_DISTANCE] source_units={num_source}, target_units={num_target}")
        logger.info(f"[EDIT_DISTANCE] stoplist_size={stoplist_size}")
        
        # Build stoplist from token frequencies if stoplist_size > 0
        stop_words = set()
        if stoplist_size > 0:
            token_freq = Counter()
            for unit in source_units:
                if cancellation:
                    cancellation.check()
                for token in unit.get('tokens', []):
                    if len(token) >= 3:
                        token_freq[normalize_greek(token)] += 1
            for unit in target_units:
                if cancellation:
                    cancellation.check()
                for token in unit.get('tokens', []):
                    if len(token) >= 3:
                        token_freq[normalize_greek(token)] += 1
            
            most_common = token_freq.most_common(stoplist_size)
            stop_words = set(word for word, count in most_common)
            logger.info(f"[EDIT_DISTANCE] Built stoplist with {len(stop_words)} words")
        
        # Pre-process: extract tokens for each unit
        src_token_lists = []
        for unit in source_units:
            if cancellation:
                cancellation.check()
            tokens = [t for t in unit.get('tokens', []) 
                     if len(t) >= 3 and normalize_greek(t) not in stop_words]
            src_token_lists.append(tokens)
        
        tgt_token_lists = []
        for unit in target_units:
            if cancellation:
                cancellation.check()
            tokens = [t for t in unit.get('tokens', []) 
                     if len(t) >= 3 and normalize_greek(t) not in stop_words]
            tgt_token_lists.append(tokens)
        
        # Build trigram index for target tokens → target unit indices
        trigram_to_targets = defaultdict(list)
        for tgt_idx, tgt_tokens in enumerate(tgt_token_lists):
            if cancellation:
                cancellation.check()
            for token in tgt_tokens:
                for trigram in _get_trigrams(token):
                    trigram_to_targets[trigram].append(tgt_idx)
        # Convert to tuples for faster pickling
        trigram_to_targets = {k: tuple(v) for k, v in trigram_to_targets.items()}

        logger.info(f"[EDIT_DISTANCE] Built trigram index with {len(trigram_to_targets)} unique trigrams")

        start_time = time.time()

        # Decide whether to parallelize based on problem size
        num_workers = safe_worker_count()
        use_parallel = num_source >= 200 and num_workers > 1

        if use_parallel:
            # Split source units into chunks for parallel processing
            indexed_src = list(enumerate(src_token_lists))
            chunk_size = max(1, len(indexed_src) // num_workers)
            chunks = [indexed_src[i:i + chunk_size]
                      for i in range(0, len(indexed_src), chunk_size)]

            logger.info(f"[EDIT_DISTANCE] Parallel: {len(chunks)} chunks across {num_workers} workers")

            worker_args = [
                (chunk, tgt_token_lists, trigram_to_targets,
                 min_similarity, min_matches, include_exact_in_count,
                 min_shared_trigrams, top_n_per_source)
                for chunk in chunks
            ]

            matches = []
            comparisons_made = 0
            for chunk_matches, chunk_comparisons in cancellable_pool_map(
                    _edit_distance_chunk_worker, worker_args, num_workers,
                    cancellation):
                matches.extend(chunk_matches)
                comparisons_made += chunk_comparisons
        else:
            # Small text: run sequentially (no subprocess overhead)
            all_src = list(enumerate(src_token_lists))
            args = (all_src, tgt_token_lists, trigram_to_targets,
                    min_similarity, min_matches, include_exact_in_count,
                    min_shared_trigrams, top_n_per_source)
            if cancellation:
                cancellation.check()
            matches, comparisons_made = _edit_distance_chunk_worker(args)

        elapsed = time.time() - start_time
        mode = "parallel" if use_parallel else "sequential"
        logger.info(f"[EDIT_DISTANCE] Complete ({mode}): {comparisons_made:,} comparisons in {elapsed:.1f}s (vs {num_source * num_target:,} full)")
        
        matches.sort(key=lambda x: (x.get('num_matches', 0), x.get('edit_score', 0)), reverse=True)
        
        if max_results > 0:
            matches = matches[:max_results]
        
        return matches, len(stop_words)
    
    def _get_feature_span(self, unit, matched_features, match_type):
        """Get the minimal span covering all matched features in a unit (V3-style)"""
        if match_type == 'exact':
            features = unit['tokens']
        else:
            features = unit['lemmas']
        
        positions = []
        for i, feat in enumerate(features):
            if feat in matched_features:
                positions.append(i)
        
        if len(positions) < 2:
            return 1

        span = max(positions) - min(positions)
        return max(span, 1)

    def _adjacent_matched_pairs(self, unit, matched_features, match_type):
        """Return a set of frozenset({A,B}) for matched lemmas appearing at
        adjacent token positions in `unit`."""
        features = unit['tokens'] if match_type == 'exact' else unit['lemmas']
        pairs = set()
        for i in range(len(features) - 1):
            a, b = features[i], features[i + 1]
            if a == b:
                continue  # same lemma adjacent to itself (reduplication etc.) — skip
            if a in matched_features and b in matched_features:
                pairs.add(frozenset((a, b)))
        return pairs

    def _effective_match_count_with_adjacency(self, src_unit, tgt_unit,
                                               matched_features, match_type):
        """Count matched lemmas, treating compound-verb co-occurrences as one
        match. A compound is a pair of matched lemmas that are adjacent in
        BOTH source and target — strong evidence the "two matches" are really
        one fixed phrase split by sub-word tokenisation. Each compound pair
        collapses 2 matched lemmas → 1 effective match.

        Greedy resolution when one lemma is in multiple potential compounds:
        accept compounds in arbitrary order, mark their members consumed,
        skip subsequent compounds whose members are already consumed."""
        src_pairs = self._adjacent_matched_pairs(src_unit, matched_features, match_type)
        tgt_pairs = self._adjacent_matched_pairs(tgt_unit, matched_features, match_type)
        compound_pairs = src_pairs & tgt_pairs
        if not compound_pairs:
            return len(matched_features)

        consumed = set()
        n_compounds = 0
        for pair in compound_pairs:
            if any(lemma in consumed for lemma in pair):
                continue
            n_compounds += 1
            consumed |= pair
        n_solo = len(matched_features) - len(consumed)
        return n_compounds + n_solo
