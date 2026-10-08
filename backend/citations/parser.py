"""
Recognizer/parser for canonical citations in running text, reimplementing the
semantics of CitationParser's three-stage ANTLR grammar (lexer + parser +
tree parser: cp_lexer.g / cp_parser.g / cp_treeparser.g, read in full from
raw/citationparser/) as a single hand-written Python scan over the token
stream from tokenizer.py, PLUS the extensions the task asked for that the
original grammar (built to process already-isolated citation strings, not to
find them inside prose) does not cover:

  - Roman-numeral book numbers ("Verg. A. I 1", "Aeneid i. 1"), which the
    ANTLR grammar has no rule for at all (LITERAL would swallow "I" as an
    ordinary word). We detect a LIT token as a roman numeral only when it is
    functioning as a locus LEVEL (see is_level_token / the single-bare-roman
    guard below), never as a substitute for real word matching.
  - "f."/"ff."/"s."/"sq."/"sqq." ("and the following") as an explicit
    open-ended range marker. The original README describes "1.124 s." as
    shorthand for a closed range (124-125), but the shipped .g grammar has no
    rule that actually parses it (a trailing "s." there falls out as a
    dangling LITERAL/`editor`, not a scope). We resolve these deliberately as
    OPEN-ENDED (locus_end=None, reason='open_ended_following_marker') rather
    than guessing a fixed line count.
  - En/em dashes as range hyphens, since running prose (unlike a curated
    citation list) mixes typography.

Kept from the original grammar, ported directly:
  - comma/dot as an equivalent hierarchy-level separator ("1,124" == "1.124")
  - hyphen as a range marker
  - semicolon as a same-citation chain separator, with the work carried over
    from the previous ref when a later ref in the chain omits it
    (cp_treeparser.g's prev_ref/curr_ref inheritance)
  - the two range-shorthand rules from CitationParser.scope2urn and
    cp_treeparser.g's scp_range handling: a range end with FEWER hierarchy
    LEVELS than the start borrows the missing higher levels from the start
    ("1.124-125" -> end becomes [1, 125]); a range end whose LAST level has
    FEWER DIGITS than the start's last level is left-padded with the start's
    leading digits ("124-5" -> end becomes "125"). Both are applied in
    resolver.py, not here (this module only produces the raw token strings).

Four defects found by running the extractor over real pre-1923 journal
prose (JSTOR's Early Journal Content), fixed here:
  - Book lists. "Aeneid I, II", "Verg. Aen. i, ii", "Aeneid i, ii, iii" were
    parsed as one multi-level book.line locus (1.2, 1.2.3). Line numbers are
    conventionally Arabic; a comma-separated run of two or more Roman-
    numeral-shaped levels with no Arabic numeral anywhere and no range means
    a LIST of separate book-level citations ("book I, book II"), never a
    single deeper locus. Detected only when every separator between the
    levels is an explicit comma -- a whitespace- or dot-joined sequence
    ("Serm. II i, i", book.poem.line) is left as an ordinary locus, since
    that punctuation is how this corpus writes a genuine deeper level.
  - Bare-number continuation. See the single-bare-roman guard below, now
    extended to bare Arabic numbers too.
  - Range depth mismatch. "Aen. i-vi, 296" (edition-advertisement copy: a
    whole-book range with a trailing price/page count coincidentally comma-
    attached) was parsed as a range end reaching into a third, phantom
    level ("6.296"). A genuine range's end is never deeper than its start;
    when the naive scan finds an end deeper than the start, the excess is
    noise, not hierarchy -- the range is truncated to the start's own
    depth (a book span, "1" to "6", no line), and the excess token is left
    for separate (almost always failed) parsing rather than folded into
    this citation.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from .tokenizer import tokenize, Token
from .abbrev_index import normalize_abbr
from .resolver import greek_letter_to_int

FOLLOWING_MARKERS = {"f", "ff", "s", "sq", "sqq"}
ROMAN_CHARS = set("IVXLCDM")
MAX_WORK_PREFIX_TOKENS = 4

# Generic scholarly-apparatus abbreviations (page/verse/volume/note markers)
# that happen to collide with some author's or work's real abbreviation in
# the abbreviations table (e.g. 'P.' is registered for Sextus Empiricus'
# Pyrrhoniae Hypotyposes, 'Ch.' for Aeschylus' Choephori/Libation-Bearers,
# 'VV.' for [Aristotle] Virtues and Vices) but overwhelmingly mean "page"/
# "verse(s)"/"chapter"/"volume"/"note" in running English prose. Confirmed as
# the single largest source of false positives when testing against real
# commentary text: a single-token match against one of these is rejected
# outright, regardless of what the
# abbreviation index says, UNLESS it is combined with another token (e.g.
# 'Hor. C.' is fine; a bare 'P.' or 'p.' by itself is not).
GENERIC_APPARATUS_STOPLIST = {
    "p", "pp", "v", "vv", "l", "ll", "n", "nn", "ch", "chh",
    "no", "vol", "ed", "cf", "sec", "col",
}


def is_roman_shaped(text):
    core = text.rstrip(".")
    if not core or len(core) > 7:
        return False
    return all(c.upper() in ROMAN_CHARS for c in core)


def is_greek_book_letter(text):
    """A single (optionally accented) Greek letter, standing in for a Homeric
    book number (Α/α=1 .. Ω/ω=24). See resolver.greek_letter_to_int. Never
    true for a bare Latin letter -- see that function's docstring."""
    return greek_letter_to_int(text) is not None


def is_level_token(tok: Token):
    if tok.type == "NUM":
        return True
    if tok.type == "LIT":
        return is_roman_shaped(tok.text) or is_greek_book_letter(tok.text)
    return False


@dataclass
class Ref:
    work_surface: Optional[str]       # matched abbreviation text, or None if inherited
    work_candidates: Optional[list]   # [(base_id, priority, src), ...] or None if inherited
    start_levels: List[str]
    end_levels: Optional[List[str]]
    following_marker: Optional[str]
    start_offset: int
    end_offset: int
    locus_start_offset: int           # offset where the locus itself begins (after work prefix)
    book_list: Optional[List[str]] = None  # set instead of a single locus when this
                                            # ref is a comma-separated list of Roman-
                                            # numeral book numbers (see module docstring)
    start_seps: Optional[List[str]] = None  # separator TYPE ('COMMA'/'DOT'/'COLON'/None
                                             # for whitespace-only) between each pair of
                                             # consecutive start_levels -- one shorter than
                                             # start_levels. Used only by extractor.py's
                                             # depth-aware truncation, to tell a genuine
                                             # dot-joined deeper locus (never truncated
                                             # past a corpus-resolution gap) from a
                                             # comma-joined chain that may bundle in noise
                                             # or several separate citations.


@dataclass
class Citation:
    refs: List[Ref]
    start_offset: int
    end_offset: int
    surface: str


def _match_work_prefix(tokens, i, abbrev_index):
    """Greedily match the longest run of consecutive LIT tokens starting at i
    against the abbreviation index. Returns (end_index, candidates, surface,
    start_offset, end_offset) or None."""
    lit_run = []
    k = i
    while k < len(tokens) and tokens[k].type == "LIT" and len(lit_run) < MAX_WORK_PREFIX_TOKENS:
        lit_run.append(tokens[k])
        k += 1
    for length in range(len(lit_run), 0, -1):
        cand = lit_run[:length]
        surface = " ".join(t.text for t in cand)
        # An abbreviation always carries either a period or a capital letter
        # in real usage ('Aen.', 'OT', 'verg. aen.'). Reject an all-lowercase,
        # no-period token run: it is indistinguishable from ordinary prose
        # ('and' vs the Andocides abbreviation 'And.') and is the single
        # biggest source of false positives in casual testing.
        if not (any(c == "." for c in surface) or any(c.isupper() for c in surface)):
            continue
        if length == 1 and cand[0].text.rstrip(".").lower() in GENERIC_APPARATUS_STOPLIST:
            continue
        key = normalize_abbr(surface)
        hits = abbrev_index.lookup(key)
        if not hits and length > 1:
            # Fallback for sigla stored unspaced ('OT') but written in the
            # source with a period after every letter ('O.T.'): normalize_abbr
            # joins multi-token candidates with a space, which would never
            # match a stored single-token key. Try the despaced form too.
            despaced = key.replace(" ", "")
            hits = abbrev_index.lookup(despaced)
        if hits:
            return i + length, hits, surface, cand[0].start, cand[-1].end
    return None


def _parse_level_seq(tokens, k):
    """LEVEL (SEP? LEVEL)* -- SEP (comma/dot) is optional so that adjacent
    numeral-shaped tokens separated only by whitespace ('I 1') are also
    accepted as consecutive levels. Returns (level_tokens, separators,
    token_index_after_each_level, new_k), or (None, [], [], k) if no level
    found at k. separators[i] is the separator TYPE ('COMMA'/'DOT'/'COLON')
    between levels[i] and levels[i+1], or None when they were joined only by
    whitespace; token_index_after_each_level[i] is the tokens-list index
    right after levels[i] was consumed (lets a caller truncate the sequence
    to a shorter prefix and know exactly where to resume scanning)."""
    if k >= len(tokens) or not is_level_token(tokens[k]):
        return None, [], [], k
    levels = [tokens[k]]
    idx_after = [k + 1]
    seps = []
    k += 1
    while True:
        k2 = k
        sep = None
        if k2 < len(tokens) and tokens[k2].type in ("COMMA", "DOT", "COLON"):
            sep = tokens[k2].type
            k2 += 1
        if k2 < len(tokens) and is_level_token(tokens[k2]):
            levels.append(tokens[k2])
            seps.append(sep)
            k = k2 + 1
            idx_after.append(k)
            continue
        break
    return levels, seps, idx_after, k


def _parse_locus(tokens, j, has_explicit_work):
    """Returns a dict with start_levels/end_levels/following_marker/end_index
    /end_offset/book_list, or None if no valid locus starts at j."""
    start_toks, start_seps, _start_idx_after, k = _parse_level_seq(tokens, j)
    if start_toks is None:
        return None

    # Safety guard against false positives: a single bare level (Roman or
    # Arabic) with no explicit work token right before it in this ref is too
    # easy to confuse with ordinary prose picked up only via semicolon-chain
    # inheritance -- a lone Roman-letter word (LIVID, CIVIL, MIX...), or (the
    # bare-Arabic case, found on the finished JSTOR index, see module
    # docstring) a footnote marker or enumeration-list number riding along on
    # an unrelated earlier "Author. Work." match several clauses back in the
    # same "sentence". Require either a real work match in this ref, or more
    # than one level.
    if not has_explicit_work and len(start_toks) == 1:
        return None

    # Book list: a comma-separated run of two or more Roman-numeral-shaped
    # levels, with no Arabic numeral and no range, is a list of separate
    # book-level citations, not one multi-level locus -- see module
    # docstring. Requires EVERY separator between the levels to be an
    # explicit comma; a whitespace- or dot-joined sequence is left as an
    # ordinary (possibly multi-level) locus.
    is_book_list = (
        len(start_toks) >= 2
        and all(t.type == "LIT" and is_roman_shaped(t.text) for t in start_toks)
        and all(s == "COMMA" for s in start_seps)
        and not (k < len(tokens) and tokens[k].type == "HYPH")
    )
    if is_book_list:
        following_marker = None
        end_offset = start_toks[-1].end
        if k < len(tokens) and tokens[k].type == "LIT":
            core = tokens[k].text.rstrip(".").lower()
            if core in FOLLOWING_MARKERS:
                following_marker = tokens[k].text
                end_offset = tokens[k].end
                k += 1
        return {
            "start_levels": [start_toks[0].text.rstrip(".")],
            "start_seps": [],
            "end_levels": None,
            "following_marker": following_marker,
            "end_index": k,
            "end_offset": end_offset,
            "book_list": [t.text.rstrip(".") for t in start_toks],
        }

    end_toks = None
    if k < len(tokens) and tokens[k].type == "HYPH":
        maybe_end, _end_seps, end_idx_after, k3 = _parse_level_seq(tokens, k + 1)
        if maybe_end is not None:
            if len(maybe_end) > len(start_toks):
                # Range depth mismatch: the naive scan found more levels at
                # the end than the start has -- e.g. "Aen. i-vi, 296", where
                # ", 296" is edition-advertisement copy (a price or page
                # count), not a third citation level. A genuine range's end
                # is never deeper than its start; truncate to the start's
                # own depth (a book span) and stop consuming tokens there,
                # leaving the excess for separate parsing.
                keep = len(start_toks)
                end_toks = maybe_end[:keep]
                k = end_idx_after[keep - 1]
            else:
                end_toks = maybe_end
                k = k3

    following_marker = None
    end_offset = (end_toks[-1] if end_toks else start_toks[-1]).end
    if k < len(tokens) and tokens[k].type == "LIT":
        core = tokens[k].text.rstrip(".").lower()
        if core in FOLLOWING_MARKERS:
            following_marker = tokens[k].text
            end_offset = tokens[k].end
            k += 1

    start_levels = [t.text.rstrip(".") for t in start_toks]
    end_levels = [t.text.rstrip(".") for t in end_toks] if end_toks else None
    return {
        "start_levels": start_levels,
        "start_seps": start_seps,
        "end_levels": end_levels,
        "following_marker": following_marker,
        "end_index": k,
        "end_offset": end_offset,
        "book_list": None,
    }


def _try_parse_ref(tokens, i, abbrev_index, inherited):
    work_match = _match_work_prefix(tokens, i, abbrev_index)
    if work_match:
        j, hits, surface, wstart, wend = work_match
        work_candidates, work_surface = hits, surface
        ref_start_offset = wstart
        # A single comma or colon directly after the work abbreviation, before
        # the locus proper, is common stylistic punctuation ('Aen., 2.504',
        # 'Aen.: 2.504') rather than a level separator itself -- skip at most
        # one before parsing the locus.
        if j < len(tokens) and tokens[j].type in ("COMMA", "COLON"):
            j += 1
    else:
        j = i
        work_candidates, work_surface = None, None
        ref_start_offset = tokens[i].start if i < len(tokens) else None

    if work_candidates is None and inherited is None:
        return None, i

    locus = _parse_locus(tokens, j, has_explicit_work=(work_candidates is not None))
    if locus is None:
        return None, i

    if ref_start_offset is None:
        ref_start_offset = tokens[j].start

    ref = Ref(
        work_surface=work_surface,
        work_candidates=work_candidates,
        start_levels=locus["start_levels"],
        end_levels=locus["end_levels"],
        following_marker=locus["following_marker"],
        start_offset=ref_start_offset,
        end_offset=locus["end_offset"],
        locus_start_offset=tokens[j].start if j < len(tokens) else locus["end_offset"],
        book_list=locus.get("book_list"),
        start_seps=locus.get("start_seps"),
    )
    return ref, locus["end_index"]


def _try_parse_citation(tokens, i, abbrev_index):
    refs = []
    inherited_candidates = None
    inherited_surface = None
    pos = i
    while True:
        ref, new_pos = _try_parse_ref(tokens, pos, abbrev_index, inherited_candidates)
        if ref is None:
            break
        refs.append(ref)
        if ref.work_candidates is not None:
            inherited_candidates = ref.work_candidates
            inherited_surface = ref.work_surface
        pos = new_pos
        if pos < len(tokens) and tokens[pos].type == "SEMI":
            pos += 1
            continue
        break
    if not refs:
        return None, i
    return refs, pos


def find_citations(text, abbrev_index):
    """Scan `text`, returning a list of Citation objects (each one ref chain,
    semicolon-separated) with character offsets into `text`."""
    tokens = tokenize(text)
    citations = []
    i = 0
    n = len(tokens)
    while i < n:
        refs, new_i = _try_parse_citation(tokens, i, abbrev_index)
        if refs:
            start = refs[0].start_offset
            end = refs[-1].end_offset
            citations.append(Citation(refs=refs, start_offset=start, end_offset=end,
                                       surface=text[start:end]))
            i = new_i
        else:
            i += 1
    return citations
