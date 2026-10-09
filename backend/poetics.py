"""
Tesserae V6 -- Refrain-and-rhyme ("form") channel for Persian and Urdu ghazals.

A ghazal is defined by its form: every line (the two hemistichs of the opening
couplet, and the second hemistich of every later couplet) ends with the same
refrain word or phrase, the RADIF, immediately preceded by a rhyming syllable,
the QAFIA. An answer poem (javab, nazira) takes over a model's radif and
qafia. The eleven wording-based fusion channels see such a pair as two lines
sharing one or two common words and rank it thousands of places down; this
channel detects the shared form directly, at the level of the whole poem
rather than individual words.

Spec: research/languages/FORM_CHANNEL_SPEC_2026-09-05.md (Tesserae V6 dev repo).

Public API:
    segment_poems(units, language) -> list[Poem]
    poem_signature(poem, language) -> (radif_tokens, qafia, radif_line_idxs)
    find_form_matches(source_units, target_units, settings) -> (matches, stats)
"""

import math
import os
import re
from collections import Counter, defaultdict, namedtuple

# A poem: a contiguous run of V6 line units (all belonging to one ghazal).
#   key        -- an identifying string (poem-numbered ref minus its last
#                 component, or the ref of the poem's first line for
#                 heuristically-segmented poems).
#   units      -- the unit dicts belonging to this poem, in order.
#   unit_idxs  -- the SAME units' indices into the original source_units /
#                 target_units list passed to segment_poems.
#   layout     -- 'couplet_pipe' (one full couplet per .tess line, hemistichs
#                 joined by ' | ') or 'hemistich' (one hemistich per line).
Poem = namedtuple('Poem', ['key', 'units', 'unit_idxs', 'layout', 'meter'], defaults=(None,))

# Poem boundaries and meter labels fetched from Ganjoor for the line-numbered
# Persian divans (scripts/fetch_ganjoor_poems.py -> data/poetics/
# ganjoor_<stem>.json). When a text has such a file, its aligned poems are
# used instead of the refrain-run heuristic, each carrying its meter
# (Ganjoor's rhythm string, e.g. "مفاعیلن مفاعیلن مفاعیلن مفاعیلن (هزج مثمن سالم)").
_GANJOOR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'poetics')
_GANJOOR_CACHE = {}


def _ganjoor_records(stem):
    if stem in _GANJOOR_CACHE:
        return _GANJOOR_CACHE[stem]
    path = os.path.join(_GANJOOR_DIR, f'ganjoor_{stem}.json')
    recs = None
    if os.path.exists(path):
        try:
            import json
            recs = [r for r in json.load(open(path, encoding='utf-8'))
                    if r.get('first_ref') and r.get('contiguous')]
        except Exception:  # pragma: no cover
            recs = None
    _GANJOOR_CACHE[stem] = recs
    return recs


def _text_stem(ref):
    parts = (ref or '').split('.')
    while parts and _INT_RE.match(parts[-1]):
        parts.pop()
    return '.'.join(parts)


_ARABIC_METERS_CACHE = {}


_ARABIC_PROSE_PREFIXES = ('quran.', 'nawawi.')
# Rhyme-letter pairs (Arabic) yield only the first lines of each poem.
_ARABIC_RAWI_LINES = 3
# Refrain-and-rhyme pairs (Persian, Urdu) pair at most this many lines of each poem.
_MAX_LINES_PER_POEM = 8


def arabic_meter(stem):
    """Meter label of an Arabic poem from data/poetics/arabic_meters.json
    (scripts/classify_arabic_meters.py), or None."""
    if not _ARABIC_METERS_CACHE:
        path = os.path.join(_GANJOOR_DIR, 'arabic_meters.json')
        try:
            import json
            _ARABIC_METERS_CACHE.update(json.load(open(path, encoding='utf-8')))
        except Exception:
            _ARABIC_METERS_CACHE['__missing__'] = True
    rec = _ARABIC_METERS_CACHE.get(stem)
    return rec.get('meter') if isinstance(rec, dict) else None


def meter_family(rhythm):
    """The meter's family name from Ganjoor's rhythm string: the part in
    parentheses ("هزج مثمن سالم") when present, else the whole string.
    Two poems in the same family share the meter for the purposes of the
    form channel."""
    if not rhythm:
        return None
    m = re.search(r'\(([^)]+)\)', rhythm)
    return (m.group(1) if m else rhythm).strip()

_INT_RE = re.compile(r'^\d+$')

# Trailing punctuation the tokenizers currently leave attached to line-final
# tokens: Arabic-script comma/semicolon/question-mark/full-stop plus ASCII
# punctuation. Stripped before a token is used as (part of) a line-final
# radif/qafia position.
_TRAILING_PUNCT = '،؛؟۔.,!?;:«»"\'()[]'

# Signature parameters (spec section 1, "Signature").
_MIN_RADIF_LINES = 3
_MIN_RADIF_FRACTION = 0.6
_MAX_RADIF_TOKENS = 4
# Share of the form score given to line pairs other than the two poems'
# opening lines. Since 2026-10-06 the channel emits ONE match per poem pair
# (the opening-line pair, with the other refrain lines listed on it), so
# this share applies only when the opening pair itself cannot be placed
# and a later line pair stands in for it.
_NON_OPENING_SHARE = 0.6

# Corpus-wide refrain-and-rhyme counts (scripts/build_form_signatures.py ->
# data/poetics/form_signatures_<lang>.json): how many poems in the whole
# corpus of a language carry a given (radif, qafia) signature. A signature
# that only these two poems carry keeps its full score; one that dozens of
# ghazals carry (Urdu "hai" with the rhyme "-ri": 2026-10-05 review, six of
# thirty Urdu rows were one such poem pair) is discounted by
# corpus_form_factor. Loaded once per language; None when no table exists,
# in which case the factor is 1.0 and the channel behaves as before.
_FORM_SIG_CACHE = {}


def load_form_signatures(language):
    """{'signatures': {'radif|qafia': poems}, 'radifs': {radif: poems},
    'total_poems': n} for `language`, or None when no table is built."""
    if language in _FORM_SIG_CACHE:
        return _FORM_SIG_CACHE[language]
    path = os.path.join(_GANJOOR_DIR, f'form_signatures_{language}.json')
    table = None
    if os.path.exists(path):
        try:
            import json
            with open(path, encoding='utf-8') as fh:
                table = json.load(fh)
        except Exception:                                   # noqa: BLE001
            table = None
    _FORM_SIG_CACHE[language] = table
    return table


def corpus_form_factor(corpus_poems):
    """Discount for a signature carried by `corpus_poems` poems across the
    corpus: 1.0 for two or fewer (only this pair), 0.5 for eight, 0.25 for
    thirty-two, 0.1 for two hundred."""
    if not corpus_poems or corpus_poems <= 2:
        return 1.0
    return math.sqrt(2.0 / corpus_poems)


def signature_key(radif, qafia):
    return ' '.join(radif) + '|' + (qafia or '')
# Share kept by a refrain-and-rhyme match whose two poems are in different meters.
_METER_MISMATCH_SHARE = 0.3

# Run-heuristic parameters (spec section 1, "Run heuristic"), copied from
# the benchmark builder (scratchpad/build_fa_javab_benchmark.py::segment).
_HEURISTIC_MIN_POEM_LINES = 6
_HEURISTIC_MIN_RADIF_LINES = 3


def _normalizer_for(language):
    """Return the language's own text normalizer (used for token comparison).

    fa -> backend.persian.processor.normalize_persian
    ur -> backend.urdu.processor.normalize_urdu
    Anything else: identity (this channel is only wired for fa/ur, but the
    segmentation/signature helpers are plain functions a test may call
    directly with an unsupported language code).
    """
    if language == 'ur':
        from backend.urdu.processor import normalize_urdu
        return normalize_urdu
    if language == 'fa':
        from backend.persian.processor import normalize_persian
        return normalize_persian
    if language == 'ar':
        from backend.arabic.processor import normalize_arabic
        return normalize_arabic
    return lambda t: t


def _strip_trailing_punct(token):
    return token.rstrip(_TRAILING_PUNCT) if token else token


def _final_tokens_with_positions(unit, normalize):
    """Normalize + strip trailing punctuation from a unit's tokens.

    Returns (tokens, positions): tokens is the cleaned, order-preserving
    token list with pure-punctuation tokens dropped; positions[i] is the
    index of tokens[i] in the unit's ORIGINAL (unstripped) tokens list, so a
    later match position can be reported in terms of the tokens array the
    scorer/highlighter actually sees.
    """
    tokens, positions = [], []
    for i, t in enumerate(unit.get('tokens', [])):
        nt = _strip_trailing_punct(normalize(t))
        if nt:
            tokens.append(nt)
            positions.append(i)
    return tokens, positions


def _final_tokens(unit, normalize):
    tokens, _ = _final_tokens_with_positions(unit, normalize)
    return tokens


def _last_final_token(unit, normalize):
    tokens = _final_tokens(unit, normalize)
    return tokens[-1] if tokens else None


def _radif_start_position(unit, radif, normalize):
    """Index of the first radif token in unit['tokens'] (the original,
    punctuation-inclusive list), or None if this unit's line-final tokens
    don't actually end with `radif`."""
    if not radif:
        return None
    tokens, positions = _final_tokens_with_positions(unit, normalize)
    n = len(radif)
    if len(tokens) < n or tuple(tokens[-n:]) != tuple(radif):
        return None
    return positions[-n]


# ---------------------------------------------------------------------------
# Poem boundary detection
# ---------------------------------------------------------------------------

def _ref_poem_key(ref):
    """Poem key for a "poem-numbered" ref (spec's rule): split the ref on
    '.'; if there are at least 4 total components and the last two are both
    integers, the poem key is the ref without its last component (the
    couplet/line number within the poem). Returns None when the rule does
    not apply (caller falls back to the run heuristic, or to radif-block
    grouping).

    Examples (see the spec's layout table):
      mir.kulliyat_wikisource.ghazal.1.1   -> mir.kulliyat_wikisource.ghazal.1
      ghalib.diwan_wikisource.ghazal.1.2   -> ghalib.diwan_wikisource.ghazal.1
      iqbal.zabur_e_ajam.118.2             -> iqbal.zabur_e_ajam.118
      hafez.diwan.882                      -> None (only 3 components)
      ghalib.diwan.radif_ے.1                -> None (second-to-last isn't an int)
    """
    if not ref:
        return None
    parts = ref.split('.')
    if len(parts) >= 4 and _INT_RE.match(parts[-1]) and _INT_RE.match(parts[-2]):
        return '.'.join(parts[:-1])
    return None


def _ref_block_key(ref):
    """Grouping key for the old-format "radif block" refs (spec row 4):
    ghalib.diwan.radif_ے.1 -- one block per radif-letter group, with the
    run heuristic (not ref numbering) finding individual ghazals inside it.
    """
    if not ref:
        return None
    parts = ref.split('.')
    if len(parts) >= 3 and _INT_RE.match(parts[-1]) and any(
        p.startswith('radif_') for p in parts[:-1]
    ):
        return '.'.join(parts[:-1])
    return None


def _make_poem(key, units_list, idxs, meter=None):
    layout = 'couplet_pipe' if any(' | ' in u.get('text', '') for u in units_list) else 'hemistich'
    return Poem(key=key, units=list(units_list), unit_idxs=list(idxs), layout=layout, meter=meter)


def _segment_by_ganjoor(units, recs):
    """Poems from Ganjoor-aligned ref ranges; lines outside any range are
    segmented by the refrain-run heuristic in their gaps."""
    num = lambda ref: int(ref.rsplit('.', 1)[-1])
    by_num = {num(u.get('ref', '0')): i for i, u in enumerate(units) if u.get('ref')}
    ranges = []
    for r in recs:
        lo, hi = num(r['first_ref']), num(r['last_ref'])
        if lo in by_num and hi in by_num and by_num[hi] >= by_num[lo]:
            ranges.append((by_num[lo], by_num[hi], r))
    ranges.sort(key=lambda t: (t[0], t[1]))
    poems = []
    cursor = 0
    for lo, hi, r in ranges:
        if lo < cursor:
            continue  # overlapping record, skip
        if lo > cursor:
            poems.extend(_segment_heuristic(units[cursor:lo], cursor, 'fa'))
        idxs = list(range(lo, hi + 1))
        poems.append(_make_poem(units[lo]['ref'], [units[i] for i in idxs], idxs,
                                meter=meter_family(r.get('rhythm'))))
        cursor = hi + 1
    if cursor < len(units):
        poems.extend(_segment_heuristic(units[cursor:], cursor, 'fa'))
    return poems


def _segment_heuristic(units, idx_offset, language,
                       min_len=_HEURISTIC_MIN_POEM_LINES,
                       min_radif=_HEURISTIC_MIN_RADIF_LINES):
    """Run heuristic (spec section 1): walk the lines; the current poem's
    candidate radif is the final token of its first line; a line continues
    the poem if it or the previous line ends with that token; two
    consecutive non-radif lines close it. Keep poems with at least min_len
    lines of which at least min_radif end with the radif.

    `idx_offset` is added to every local index in `units` to recover the
    caller's original (global) unit indices in the returned Poems.
    """
    normalize = _normalizer_for(language)
    finals = [_last_final_token(u, normalize) for u in units]

    groups = []  # (local_idxs, radif_key)
    cur_idxs = []
    radif = None
    miss = 0
    for i in range(len(units)):
        key = finals[i]
        if radif is not None and key == radif:
            cur_idxs.append(i)
            miss = 0
            continue
        if radif is not None and miss == 0:
            # Tolerate one non-radif line between radif lines.
            cur_idxs.append(i)
            miss = 1
            continue
        if cur_idxs:
            groups.append((cur_idxs, radif))
        cur_idxs = [i]
        radif = key
        miss = 0
    if cur_idxs:
        groups.append((cur_idxs, radif))

    poems = []
    for idxs, radif_key in groups:
        n_r = sum(1 for i in idxs if finals[i] == radif_key)
        if len(idxs) >= min_len and n_r >= min_radif:
            poem_units = [units[i] for i in idxs]
            global_idxs = [idx_offset + i for i in idxs]
            poems.append(_make_poem(units[idxs[0]]['ref'], poem_units, global_idxs))
    return poems


def segment_poems(units, language):
    """Group a text's V6 line units (in file order) into Poem objects.

    Chooses one of three strategies per the spec's layout table, decided
    from the first unit's ref (layout is a per-text property):
      1. Poem-numbered ref (_ref_poem_key matches): group by ref-minus-last-
         component. Covers both hemistich-per-line and couplet-per-line-with-
         pipe poem-numbered texts.
      2. Radif-block ref (_ref_block_key matches): group into blocks by that
         key, then run the heuristic *inside* each block (a block can hold
         several distinct ghazals that merely share a rhyme-letter).
      3. No usable ref info: run the heuristic over the whole text.
    """
    if not units:
        return []

    first_ref = units[0].get('ref', '')

    if language == 'ar':
        # Arabic mode (2026-09-05): qasidas with a single rhyme letter (rawi)
        # on every verse and no refrain. A file with flat refs (stem.N) is one
        # poem; a diwan with poem-numbered refs (stem.P.N, from the Arabic
        # Wikisource import of 2026-09-06) is segmented on the poem number
        # below, each poem taking its own meter label. Qur'an suras and the
        # hadith collections are prose and are excluded; a text that does not
        # share a rhyme letter on most of its verses fails the signature
        # threshold anyway.
        if first_ref.startswith(_ARABIC_PROSE_PREFIXES) or len(units) < _HEURISTIC_MIN_POEM_LINES:
            return []
        if _ref_poem_key(first_ref) is None:
            key = '.'.join(first_ref.split('.')[:-1]) or first_ref
            return [_make_poem(key, units, list(range(len(units))), meter=arabic_meter(key))]

    if _ref_poem_key(first_ref) is not None:
        poems = []
        cur_key = None
        cur_units, cur_idxs = [], []
        for i, u in enumerate(units):
            k = _ref_poem_key(u.get('ref', '')) or cur_key
            if k != cur_key and cur_units:
                poems.append(_make_poem(cur_key, cur_units, cur_idxs))
                cur_units, cur_idxs = [], []
            cur_key = k
            cur_units.append(u)
            cur_idxs.append(i)
        if cur_units:
            poems.append(_make_poem(cur_key, cur_units, cur_idxs))
        if language == 'ar':
            poems = [p._replace(meter=arabic_meter(p.key)) for p in poems
                     if len(p.units) >= _HEURISTIC_MIN_POEM_LINES]
        if language == 'fa':
            # Poem-numbered text with a Ganjoor file: keep the ref boundaries,
            # attach the meter of the record whose first line falls in the poem.
            recs = _ganjoor_records(_text_stem(first_ref))
            if recs:
                meter_by_key = {}
                for r in recs:
                    k = _ref_poem_key(r['first_ref'])
                    if k and k not in meter_by_key:
                        meter_by_key[k] = meter_family(r.get('rhythm'))
                poems = [p._replace(meter=meter_by_key.get(p.key)) if p.key in meter_by_key else p
                         for p in poems]
        return poems

    if language == 'fa':
        recs = _ganjoor_records(_text_stem(first_ref))
        if recs:
            return _segment_by_ganjoor(units, recs)

    if _ref_block_key(first_ref) is not None:
        poems = []
        cur_key = None
        block_units, block_idxs = [], []
        for i, u in enumerate(units):
            k = _ref_block_key(u.get('ref', '')) or cur_key
            if k != cur_key and block_units:
                poems.extend(_segment_heuristic(block_units, block_idxs[0], language))
                block_units, block_idxs = [], []
            cur_key = k
            block_units.append(u)
            block_idxs.append(i)
        if block_units:
            poems.extend(_segment_heuristic(block_units, block_idxs[0], language))
        return poems

    return _segment_heuristic(units, 0, language)


# ---------------------------------------------------------------------------
# Signature: radif + qafia
# ---------------------------------------------------------------------------

def _best_shared_suffix(seqs, min_lines, min_frac, max_len=_MAX_RADIF_TOKENS,
                        expected=None):
    """Longest trailing token sequence (1..max_len tokens) shared by at
    least min_frac of the lines expected to carry it (`expected`, default
    the number of `seqs`), requiring at least min_lines such sequences.
    `seqs` are the (up to max_len) trailing tokens of each candidate line.
    Returns () if no length reaches the threshold."""
    n = expected if expected else len(seqs)
    if n == 0 or not seqs:
        return ()
    for length in range(max_len, 0, -1):
        counts = Counter(s[-length:] for s in seqs if len(s) >= length)
        if not counts:
            continue
        seq, cnt = counts.most_common(1)[0]
        if cnt >= min_lines and cnt / n >= min_frac:
            return seq
    return ()


def _majority_qafia(line_finals, idxs, radif_len):
    """Most common last-two-letters of the token immediately before the
    radif (or of the final token itself when radif_len is 0, i.e. a
    radif-less poem)."""
    counts = Counter()
    for i in idxs:
        toks = line_finals[i]
        pre_idx = len(toks) - radif_len - 1
        if 0 <= pre_idx < len(toks) and len(toks[pre_idx]) >= 2:
            counts[toks[pre_idx][-2:]] += 1
    return counts.most_common(1)[0][0] if counts else ''


def poem_signature(poem, language, min_lines=_MIN_RADIF_LINES,
                   min_frac=_MIN_RADIF_FRACTION):
    """(radif_tokens, qafia, radif_line_idxs) for one poem.

    radif_line_idxs are LOCAL indices into poem.units/poem.unit_idxs.

    Layout drives which lines are even candidates for carrying the radif:
      couplet_pipe -- every line (each line is a full couplet; both
        hemistichs conventionally end in the radif on the opening line, and
        the stored tokens end with the second hemistich's radif on every
        line).
      hemistich -- lines whose own last (normalized, punctuation-stripped)
        token equals the poem's first line's last token. This is exactly
        the same content-based test the run heuristic uses for poem
        continuation, so a stray non-radif filler line (or an off-parity
        misra1) simply isn't counted, without needing to track position
        parity explicitly.
    If no token sequence of 1-4 trailing tokens is shared by at least
    min_frac of the candidate lines (needing at least min_lines of them),
    the poem is radif-less: () is returned for radif, and qafia falls back
    to the most common last-two-letters of the plain final token.
    """
    normalize = _normalizer_for(language)
    line_finals = [_final_tokens(u, normalize) for u in poem.units]
    n_lines = len(line_finals)
    if n_lines == 0:
        return (), '', []

    if language == 'ar':
        # Rhyme letter (rawi): the last letter of the final token, shared by
        # at least min_frac of the verses. No refrain. The qafia string is
        # that one letter, so two qasidas match on the rawi alone (see the
        # matching rule), which is weaker evidence than refrain + rhyme and
        # scored accordingly.
        letters = Counter(toks[-1][-1] for toks in line_finals if toks and toks[-1])
        if not letters:
            return (), '', []
        rawi, cnt = letters.most_common(1)[0]
        if cnt < min_lines or cnt / n_lines < min_frac:
            return (), '', []
        idxs = [i for i, toks in enumerate(line_finals) if toks and toks[-1] and toks[-1][-1] == rawi]
        return (), rawi, idxs

    # Every line is a candidate. What differs by layout is how many lines
    # are EXPECTED to carry the radif: all of them when each line is a
    # couplet, about half (the second hemistichs, plus the opening line)
    # when each line is a hemistich. The threshold is taken against that
    # expectation, so a ghazal whose opening line lacks the radif (Ghalib,
    # Wikisource ghazal 3) or whose lines are off by one still signs.
    candidate_idxs = list(range(n_lines))
    if poem.layout == 'couplet_pipe':
        expected = n_lines
    else:
        expected = min(n_lines, n_lines // 2 + 1)

    seqs = [tuple(line_finals[i][-_MAX_RADIF_TOKENS:]) for i in candidate_idxs if line_finals[i]]
    radif = _best_shared_suffix(seqs, min_lines, min_frac, expected=expected)

    if radif:
        radif_len = len(radif)
        radif_line_idxs = [
            i for i in candidate_idxs
            if len(line_finals[i]) >= radif_len and tuple(line_finals[i][-radif_len:]) == radif
        ]
        qafia = _majority_qafia(line_finals, radif_line_idxs, radif_len)
        return radif, qafia, radif_line_idxs

    # Radif-less (spec: "qafia alone is too weak" -- no match emitted for
    # these in find_form_matches, but the signature is still meaningful).
    fallback_idxs = candidate_idxs if candidate_idxs else list(range(n_lines))
    qafia = _majority_qafia(line_finals, fallback_idxs, 0)
    return (), qafia, candidate_idxs


# ---------------------------------------------------------------------------
# Matching + emission
# ---------------------------------------------------------------------------

def find_form_matches(source_units, target_units, settings=None):
    """Find refrain-and-rhyme (radif/qafia) matches between two texts.

    Segments both sides into poems, computes each poem's signature, and for
    every (source poem, target poem) pair whose radif matches per the
    spec's matching rule, emits one raw match per (source line, target
    line) where both lines are radif-position lines of their poems.

    Returns (matches, stats) where stats is
    {'poems_source': n, 'poems_target': m, 'poem_pairs': k}.
    """
    settings = settings or {}
    language = settings.get('language', 'fa')
    max_results = settings.get('form_max_results', 50000)

    from backend.fusion import _STOPLISTS
    stoplist = _STOPLISTS.get(language, set())
    normalize = _normalizer_for(language)

    source_poems = segment_poems(source_units, language)
    target_poems = segment_poems(target_units, language)

    src_sigs = [(p,) + poem_signature(p, language) for p in source_poems]
    tgt_sigs = [(p,) + poem_signature(p, language) for p in target_poems]

    tgt_by_radif = defaultdict(list)
    for entry in tgt_sigs:
        _, radif, _, _ = entry
        if radif:
            tgt_by_radif[radif].append(entry)

    # How surprising is a shared form? A refrain-and-rhyme that many poems
    # on each side carry (Urdu "hai" + "-an": dozens of ghazals in any two
    # divans) is weak evidence of a relationship; one that a single poem on
    # each side carries is strong. Scale by the geometric mean of the two
    # counts, so a unique pairing keeps its full score and a ubiquitous one
    # is discounted (5 x 5 poems -> 0.2; 20 x 25 -> 0.045).
    src_sig_counts = Counter((r, q) for _, r, q, _ in src_sigs if r)
    tgt_sig_counts = Counter((r, q) for _, r, q, _ in tgt_sigs if r)
    src_radif_counts = Counter(r for _, r, _, _ in src_sigs if r)
    tgt_radif_counts = Counter(r for _, r, _, _ in tgt_sigs if r)

    matches_full = []   # form_score == 1.0
    matches_half = []   # form_score == 0.5
    poem_pairs = 0

    if language == 'ar':
        # Rhyme-letter matching for qasidas (mu'arada by rhyme; meter is not
        # yet available). Base 0.5, the same footing as a shared refrain
        # with a different rhyme in Persian and Urdu.
        src_q_counts = Counter(q for _, r, q, _ in src_sigs if q)
        tgt_q_counts = Counter(q for _, r, q, _ in tgt_sigs if q)
        for s_poem, s_radif, s_qafia, s_line_idxs in src_sigs:
            if not s_qafia:
                continue
            for t_poem, t_radif, t_qafia, t_line_idxs in tgt_sigs:
                if t_qafia != s_qafia:
                    continue
                # A mu'arada keeps the model's meter AND rhyme. Same rhyme
                # letter with a different meter (Banat Su'ad and Imru'
                # al-Qais, both on -l) is a weak coincidence. With whole
                # diwans on each side (2026-09-06: Mutanabbi's 288 poems,
                # 28 possible rhyme letters) almost every poem pair shares a
                # letter, so a labelled meter mismatch now excludes the pair
                # outright, and a rhyme-letter pair yields only its opening
                # lines (the first _ARABIC_RAWI_LINES of each poem), not
                # every line against every line. Meter labels come from
                # scripts/classify_arabic_meters.py.
                if s_poem.meter and t_poem.meter and s_poem.meter != t_poem.meter:
                    continue
                poem_pairs += 1
                rarity = 1.0 / math.sqrt(src_q_counts[s_qafia] * tgt_q_counts[t_qafia])
                for n_s, li in enumerate(s_line_idxs[:_ARABIC_RAWI_LINES]):
                    src_idx = s_poem.unit_idxs[li]
                    for n_t, lj in enumerate(t_line_idxs[:_ARABIC_RAWI_LINES]):
                        tgt_idx = t_poem.unit_idxs[lj]
                        opening = 1.0 if (n_s == 0 and n_t == 0) else _NON_OPENING_SHARE
                        matches_half.append({
                            'source_idx': src_idx,
                            'target_idx': tgt_idx,
                            'match_basis': 'form',
                            'form_score': round(0.5 * rarity * opening, 4),
                            'form_base': 0.5,
                            'form_rarity': round(rarity, 4),
                            'radif': '',
                            'qafia': s_qafia,
                            'meter': s_poem.meter if s_poem.meter == t_poem.meter else None,
                            'source_position': max(0, len(source_units[src_idx].get('tokens', [])) - 1),
                            'target_position': max(0, len(target_units[tgt_idx].get('tokens', [])) - 1),
                            'radif_len': 1,
                            'matched_lemmas': [],
                        })
        src_sigs = []  # the fa/ur loop below runs on nothing

    sig_table = load_form_signatures(language) if settings.get('form_corpus_rarity', True) else None
    sig_counts = (sig_table or {}).get('signatures', {})
    radif_counts_corpus = (sig_table or {}).get('radifs', {})

    for s_poem, s_radif, s_qafia, s_line_idxs in src_sigs:
        if not s_radif:
            # Radif-less poems: no match in this version -- qafia alone is
            # too weak a signal to pair on. TODO: revisit with a qafia-only
            # low-confidence channel once there's a benchmark to tune it on.
            continue
        for t_poem, t_radif, t_qafia, t_line_idxs in tgt_by_radif.get(s_radif, []):
            if s_qafia == t_qafia:
                base_score = 1.0
                rarity = 1.0 / math.sqrt(src_sig_counts[(s_radif, s_qafia)]
                                         * tgt_sig_counts[(t_radif, t_qafia)])
                corpus_poems = sig_counts.get(signature_key(s_radif, s_qafia))
            else:
                is_single_stoplisted = (
                    len(s_radif) == 1 and all(tok in stoplist for tok in s_radif)
                )
                if is_single_stoplisted:
                    continue  # shared by chance, not by design
                base_score = 0.5
                rarity = 1.0 / math.sqrt(src_radif_counts[s_radif] * tgt_radif_counts[t_radif])
                corpus_poems = radif_counts_corpus.get(' '.join(s_radif))

            # Meter, when both sides carry a label: an answer poem keeps its
            # model's meter, so a different meter is strong evidence against.
            if s_poem.meter and t_poem.meter:
                rarity *= 1.0 if s_poem.meter == t_poem.meter else _METER_MISMATCH_SHARE

            # Corpus-wide rarity of the shared form (see load_form_signatures).
            corpus_factor = corpus_form_factor(corpus_poems) if corpus_poems else 1.0
            rarity *= corpus_factor

            poem_pairs += 1
            radif_str = ' '.join(s_radif)
            radif_len = len(s_radif)
            bucket = matches_full if base_score == 1.0 else matches_half

            # ONE match per poem pair (2026-10-06). Before this the channel
            # emitted every (source line, target line) pair of the two poems'
            # refrain lines, so a ranking of 200 held a handful of poem pairs
            # repeated dozens of times (the 2026-10-05 review sheets: 24 of
            # 30 Persian rows were five poem pairs). The opening-line pair
            # carries the match (a ghazal is cited by its opening); the other
            # refrain lines of each poem are listed on it for display.
            src_lines = []   # (local order, unit idx, radif position)
            for n_s, li in enumerate(s_line_idxs[:_MAX_LINES_PER_POEM]):
                src_idx = s_poem.unit_idxs[li]
                pos = _radif_start_position(source_units[src_idx], s_radif, normalize)
                if pos is not None:
                    src_lines.append((n_s, src_idx, pos))
            tgt_lines = []
            for n_t, lj in enumerate(t_line_idxs[:_MAX_LINES_PER_POEM]):
                tgt_idx = t_poem.unit_idxs[lj]
                pos = _radif_start_position(target_units[tgt_idx], t_radif, normalize)
                if pos is not None:
                    tgt_lines.append((n_t, tgt_idx, pos))
            if not src_lines or not tgt_lines:
                continue
            n_s, src_idx, src_pos = src_lines[0]
            n_t, tgt_idx, tgt_pos = tgt_lines[0]
            opening = 1.0 if (n_s == 0 and n_t == 0) else _NON_OPENING_SHARE
            form_score = round(base_score * rarity * opening, 4)
            bucket.append({
                'source_idx': src_idx,
                'target_idx': tgt_idx,
                'match_basis': 'form',
                'form_score': form_score,
                'form_base': base_score,
                'form_rarity': round(rarity, 4),
                'form_corpus_poems': corpus_poems,
                'form_corpus_factor': round(corpus_factor, 4),
                'radif': radif_str,
                'qafia': s_qafia,
                'meter': s_poem.meter if s_poem.meter == t_poem.meter else None,
                'source_position': src_pos,
                'target_position': tgt_pos,
                'radif_len': radif_len,
                'matched_lemmas': [],
                # The poems' other refrain lines (refs), for the result card.
                'source_lines': [source_units[i].get('ref', '') for _, i, _ in src_lines],
                'target_lines': [target_units[i].get('ref', '') for _, i, _ in tgt_lines],
            })

    matches = matches_full + matches_half
    matches.sort(key=lambda m: -m['form_score'])
    if max_results > 0 and len(matches) > max_results:
        matches = matches[:max_results]

    stats = {
        'poems_source': len(source_poems),
        'poems_target': len(target_poems),
        'poem_pairs': poem_pairs,
    }
    return matches, stats


# ---------------------------------------------------------------------------
# Across Persian and Urdu (2026-10-07)
# ---------------------------------------------------------------------------

_CROSS_SIG_CACHE = {}


def _cross_key(radif, qafia, language):
    """A poem's refrain and rhyme in the comparison letter forms shared by
    Persian, Urdu and Arabic (backend/perso_arabic.cross_form), so that the
    same refrain written with Urdu or Persian letters compares equal."""
    from backend.perso_arabic import cross_form
    return (tuple(cross_form(t, language) for t in radif), cross_form(qafia or '', language))


def _cross_corpus_counts(language):
    """{cross key: poems in the whole corpus of `language`} from the form
    signature table, re-keyed in the comparison forms. Cached per language."""
    if language in _CROSS_SIG_CACHE:
        return _CROSS_SIG_CACHE[language]
    table = load_form_signatures(language) or {}
    counts = Counter()
    for sig, n in (table.get('signatures') or {}).items():
        radif, _, qafia = sig.partition('|')
        if radif:
            counts[_cross_key(tuple(radif.split()), qafia, language)] += n
    _CROSS_SIG_CACHE[language] = counts
    return counts


def find_cross_form_matches(source_units, target_units, source_language, target_language,
                            settings=None):
    """Refrain-and-rhyme matches between a Persian and an Urdu text.

    Each side is cut into poems and signed by its own language's rules
    (segment_poems, poem_signature). A pair matches when the refrain AND the
    rhyme are the same in the shared comparison letter forms. Urdu refrains
    are mostly Urdu words (hai, nahin), so a shared form is rare and, when
    it occurs, a strong sign of an answer poem or a Persian ghazal inside an
    Urdu poet's collection: of 2,633 Urdu poems in the corpus, 19 share a
    refrain and rhyme with a Persian poem (2026-10-07). A refrain shared
    with a different rhyme is not matched across the pair, and neither is a
    translated refrain (Persian ast for Urdu hai): without the meter, which
    the Urdu texts do not carry, those forms are too common to be evidence.

    Scored like the single-language channel: 1.0 for a pair unique on both
    sides, discounted by the geometric mean of how many poems on each side
    carry the form, by its corpus-wide frequency in the two languages, and
    by a meter mismatch when both poems are labelled. One match per poem
    pair, on the two poems' first refrain lines; the other refrain lines are
    listed for display. Returns (matches, stats) in find_form_matches' shape.
    """
    settings = settings or {}
    max_results = settings.get('form_max_results', 50000)
    s_norm = _normalizer_for(source_language)
    t_norm = _normalizer_for(target_language)

    source_poems = segment_poems(source_units, source_language)
    target_poems = segment_poems(target_units, target_language)
    src = [(p,) + poem_signature(p, source_language) for p in source_poems]
    tgt = [(p,) + poem_signature(p, target_language) for p in target_poems]

    src_keyed = [(e, _cross_key(e[1], e[2], source_language)) for e in src if e[1]]
    tgt_keyed = [(e, _cross_key(e[1], e[2], target_language)) for e in tgt if e[1]]
    src_counts = Counter(k for _, k in src_keyed)
    tgt_counts = Counter(k for _, k in tgt_keyed)
    tgt_by_key = defaultdict(list)
    for e, k in tgt_keyed:
        tgt_by_key[k].append(e)

    use_corpus = settings.get('form_corpus_rarity', True)
    corpus_s = _cross_corpus_counts(source_language) if use_corpus else {}
    corpus_t = _cross_corpus_counts(target_language) if use_corpus else {}

    # A refrain made only of function words on EITHER side is not evidence
    # across the pair: Urdu hua ("became") is spelled like Persian hava ("air"),
    # Urdu the ("were") folds to Persian tahi ("empty"), and Persian ra (the
    # object marker) closes thousands of ghazals. Both stoplists, compared in
    # the shared letter forms.
    from backend.perso_arabic import cross_stoplist
    function_words = cross_stoplist(source_language) | cross_stoplist(target_language)

    matches = []
    poem_pairs = 0
    for (s_poem, s_radif, s_qafia, s_line_idxs), key in src_keyed:
        if not key[1]:
            continue          # no rhyme: a bare refrain is too weak across languages
        if all(tok in function_words for tok in key[0]):
            continue
        for t_poem, t_radif, t_qafia, t_line_idxs in tgt_by_key.get(key, []):
            rarity = 1.0 / math.sqrt(src_counts[key] * tgt_counts[key])
            if s_poem.meter and t_poem.meter:
                rarity *= 1.0 if s_poem.meter == t_poem.meter else _METER_MISMATCH_SHARE
            n_s_corpus, n_t_corpus = corpus_s.get(key), corpus_t.get(key)
            corpus_poems = (round(math.sqrt(n_s_corpus * n_t_corpus))
                            if n_s_corpus and n_t_corpus else None)
            corpus_factor = corpus_form_factor(corpus_poems) if corpus_poems else 1.0
            rarity *= corpus_factor

            src_lines = []
            for n_s, li in enumerate(s_line_idxs[:_MAX_LINES_PER_POEM]):
                i = s_poem.unit_idxs[li]
                pos = _radif_start_position(source_units[i], s_radif, s_norm)
                if pos is not None:
                    src_lines.append((n_s, i, pos))
            tgt_lines = []
            for n_t, lj in enumerate(t_line_idxs[:_MAX_LINES_PER_POEM]):
                j = t_poem.unit_idxs[lj]
                pos = _radif_start_position(target_units[j], t_radif, t_norm)
                if pos is not None:
                    tgt_lines.append((n_t, j, pos))
            if not src_lines or not tgt_lines:
                continue
            poem_pairs += 1
            n_s, src_idx, src_pos = src_lines[0]
            n_t, tgt_idx, tgt_pos = tgt_lines[0]
            opening = 1.0 if (n_s == 0 and n_t == 0) else _NON_OPENING_SHARE
            matches.append({
                'source_idx': src_idx,
                'target_idx': tgt_idx,
                'match_basis': 'form',
                'form_score': round(rarity * opening, 4),
                'form_base': 1.0,
                'form_rarity': round(rarity, 4),
                'form_corpus_poems': corpus_poems,
                'form_corpus_factor': round(corpus_factor, 4),
                'radif': ' '.join(s_radif),
                'target_radif': ' '.join(t_radif),
                'qafia': s_qafia,
                'meter': s_poem.meter if s_poem.meter == t_poem.meter else None,
                'source_position': src_pos,
                'target_position': tgt_pos,
                'radif_len': len(s_radif),
                'target_radif_len': len(t_radif),
                'matched_lemmas': [],
                'source_lines': [source_units[i].get('ref', '') for _, i, _ in src_lines],
                'target_lines': [target_units[j].get('ref', '') for _, j, _ in tgt_lines],
            })

    matches.sort(key=lambda m: -m['form_score'])
    if max_results > 0 and len(matches) > max_results:
        matches = matches[:max_results]
    return matches, {'poems_source': len(source_poems), 'poems_target': len(target_poems),
                     'poem_pairs': poem_pairs}
