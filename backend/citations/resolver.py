"""
Resolve a parsed Ref/Citation (parser.py) to a Tesserae (work_id, locus_start,
locus_end) or a structured failure reason.

Implements the two shorthand-expansion rules from CitationParser (see the
docstring in parser.py for where each comes from):
  1. level-count borrowing: a range end with fewer hierarchy levels than the
     start borrows the missing leading (higher) levels from the start.
  2. digit-shorthand: a range end whose last level has fewer digits than the
     start's last level is left-padded with the start's leading digits.
Then converts any Roman-numeral level to Arabic, joins levels with '.', and
picks a single Tesserae work id from the ref's candidate list, preferring the
lowest-priority-number (most specific) match and flagging ambiguity when two
candidates tie at the same priority.
"""
import re
import unicodedata
from dataclasses import dataclass, asdict
from typing import Optional

ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

# Greek-letter book numbers (Homer's 24-book Iliad/Odyssey convention: the
# Greek alphabet's own letter order gives the book number directly, Α/α=1
# through Ω/ω=24 -- no digamma, no classical-numeral values). Keyed on
# the bare lowercase letter after
# accent-stripping and casefold (see greek_letter_to_int below); "ς" (final
# sigma) is included as an alias for "σ" (both position 18), since OCR and
# hand-typesetting sometimes render the lone book-letter with the
# word-final sigma form.
_GREEK_BOOK_ORDER = "αβγδεζηθικλμνξοπρστυφχψω"
GREEK_LETTER_VALUES = {ch: i + 1 for i, ch in enumerate(_GREEK_BOOK_ORDER)}
GREEK_LETTER_VALUES["ς"] = GREEK_LETTER_VALUES["σ"]


def roman_to_int(s):
    s = s.upper().rstrip(".")
    total = 0
    prev = 0
    for ch in reversed(s):
        v = ROMAN_VALUES.get(ch)
        if v is None:
            return None
        if v < prev:
            total -= v
        else:
            total += v
            prev = v
    return total if total > 0 else None


def _strip_combining(ch):
    """Strip a combining diacritic (tonos, breathing, etc.) off one base
    character via NFD decomposition, so accented Greek letters ('ά', 'Ἀ')
    still match the same bare-letter book-number key as the unaccented
    form. Never touches ASCII/Latin letters (nothing to decompose there)."""
    decomposed = unicodedata.normalize("NFD", ch)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def greek_letter_to_int(text):
    """A single Greek letter (optionally with a trailing period, optionally
    accented) -> its 1-24 Homeric book number, or None. Deliberately never
    matches a bare Latin letter (even one historically used as a Greek-
    letter stand-in, like 'B' for Beta): those collide with real registered
    sigla elsewhere in the abbreviation table, so only real Greek Unicode
    letters are accepted."""
    core = text.rstrip(".")
    if len(core) != 1:
        return None
    base = _strip_combining(core).casefold()
    return GREEK_LETTER_VALUES.get(base)


def level_to_arabic(level_str):
    """A level token's text (roman, arabic, or a Greek book letter) -> its
    Arabic-numeral string form for locus addressing, or None if it isn't a
    valid level."""
    if level_str.isdigit():
        return level_str
    v = roman_to_int(level_str)
    if v is not None:
        return str(v)
    v = greek_letter_to_int(level_str)
    return str(v) if v is not None else None


# Stephanus pagination (Plato's own 1578 edition, still how every Plato
# dialogue is cited today): an Arabic page number followed by a single
# subdivision letter a-e ("514d", "391e"). The letter is NOT a locus
# level of its own -- it's a lowercase suffix on the page -- but 'A'
# through 'E' includes four letters (C, D plus the lowercase-only 'a'/'e'
# don't collide, but 'C'/'D' do) that ARE also valid Roman-numeral
# letters, so level_to_arabic above would silently misread "514 D" as
# page level 500 (D=500) rather than reading "514d" as one Stephanus
# locus -- found live: "Rep. 514 D" was resolving as book/page
# 514.500. Only ever applied to a work whose
# abbreviations.json entry sets "stephanus": true (Plato's dialogues;
# see resolve_ref, which looks the flag up once it knows the resolved
# work) and only when the letter directly follows a plain Arabic page
# number -- a Roman-numeral BOOK level before the page ("Rep. VI. 511 D")
# is unaffected, since the letter here is still the LAST level, not the
# one right after the book.
STEPHANUS_LETTERS = set("abcde")


def _stephanus_letter_suffix(levels):
    """True if `levels` ends in a single Stephanus subdivision letter
    (a-e, case-insensitive) directly following a plain Arabic page
    number level."""
    if len(levels) < 2:
        return False
    last = levels[-1].rstrip(".")
    if len(last) != 1 or last.lower() not in STEPHANUS_LETTERS:
        return False
    return levels[-2].isdigit()


def levels_to_locus_string(levels, stephanus=False):
    """Join a list of raw locus level tokens into the dot-separated,
    Arabic-numeral locus string used throughout this codebase. When
    stephanus=True and the levels end in a Stephanus subdivision letter
    (_stephanus_letter_suffix), that letter is folded as a lowercase
    suffix onto the (already-converted) page number instead of being run
    through level_to_arabic itself -- which would treat 'C'/'D' as Roman
    numerals 100/500. Returns None if any level (other than a folded
    Stephanus letter) fails to convert."""
    if stephanus and _stephanus_letter_suffix(levels):
        letter = levels[-1].rstrip(".").lower()
        page_levels = levels[:-1]
        arabic = [level_to_arabic(l) for l in page_levels]
        if any(a is None for a in arabic):
            return None
        arabic[-1] = arabic[-1] + letter
        return ".".join(arabic)
    arabic = [level_to_arabic(l) for l in levels]
    if any(a is None for a in arabic):
        return None
    return ".".join(arabic)


@dataclass
class Resolution:
    work_id: Optional[str]           # Tesserae work id, or None
    part_id: Optional[str]           # specific .part.N file if base id unresolved (fallback)
    locus_start: Optional[str]       # 'book.line' or 'line'
    locus_end: Optional[str]         # same, or None (single locus / open-ended)
    open_ended: bool
    open_ended_marker: Optional[str]
    resolved: bool
    reason: Optional[str]            # failure/caveat reason, always set for reason tracking
    work_candidates_considered: int
    match_priority: Optional[int]


def _pad_end_digits(start_last, end_last):
    """'124-5' -> end '5' padded from start '124' -> '125'."""
    if start_last.isdigit() and end_last.isdigit() and len(end_last) < len(start_last):
        diff = len(start_last) - len(end_last)
        return start_last[:diff] + end_last
    return end_last


def _expand_range(start_levels, end_levels):
    """Apply level-count borrowing then digit-shorthand padding. Returns
    (start_levels, end_levels) both fully expanded, or None if levels are
    not convertible."""
    if end_levels is None:
        return start_levels, None
    end_levels = list(end_levels)
    if len(end_levels) < len(start_levels):
        missing = len(start_levels) - len(end_levels)
        end_levels = start_levels[:missing] + end_levels
    # digit-shorthand on the last level only, using the ORIGINAL (pre-borrow)
    # last element, i.e. the true rightmost element already present in
    # end_levels after borrowing (borrowing only ever prepends).
    end_levels[-1] = _pad_end_digits(start_levels[-1], end_levels[-1])
    return start_levels, end_levels


def _pick_candidate(candidates):
    """candidates: [(base_id, priority, src), ...]. Returns (base_id, priority,
    ambiguous_bool, n_at_best_priority)."""
    if not candidates:
        return None, None, False, 0
    best_prio = min(c[1] for c in candidates)
    at_best = sorted(set(c[0] for c in candidates if c[1] == best_prio))
    ambiguous = len(at_best) > 1
    return at_best[0], best_prio, ambiguous, len(at_best)


def _route_to_part(work_rec, locus_start_arabic):
    """work_rec: entry from abbreviations.json. If it has no combined base
    file (tesserae_work_id is None), pick the .part.N whose locus range
    contains the citation's first (book) level."""
    if not work_rec.get("part_locus_ranges"):
        return None
    try:
        book = int(locus_start_arabic.split(".")[0])
    except (ValueError, IndexError):
        return None
    for p in work_rec["part_locus_ranges"]:
        fl = p.get("first_locus") or ""
        ll = p.get("last_locus") or ""
        fbook = fl.split(".")[0] if fl else None
        lbook = ll.split(".")[0] if ll else None
        if fbook and fbook.isdigit() and lbook and lbook.isdigit():
            if int(fbook) <= book <= int(lbook):
                return p["part_id"]
    return None


def resolve_ref(ref, works_by_base_id):
    """ref: a parser.Ref (possibly with work_candidates=None if inherited --
    caller must have already substituted the inherited candidates before
    calling, see extractor.py)."""
    candidates = ref.work_candidates
    base_id, priority, ambiguous, n_at_best = _pick_candidate(candidates)

    if base_id is None:
        return Resolution(None, None, None, None, False, None, False,
                           "no_work_matched", 0, None)
    if ambiguous:
        return Resolution(None, None, None, None, False, None, False,
                           f"ambiguous_work:{n_at_best}_candidates_tied_at_priority_{priority}",
                           len(candidates), priority)

    work_rec = works_by_base_id.get(base_id, {})
    stephanus = bool(work_rec.get("stephanus"))

    start_levels, end_levels = _expand_range(ref.start_levels, ref.end_levels)
    locus_start = levels_to_locus_string(start_levels, stephanus=stephanus)
    if locus_start is None:
        return Resolution(base_id, None, None, None, False, None, False,
                           "unparseable_locus_level", len(candidates), priority)

    locus_end = None
    if end_levels is not None:
        locus_end = levels_to_locus_string(end_levels, stephanus=stephanus)
        if locus_end is None:
            return Resolution(base_id, None, locus_start, None, False, None, False,
                               "unparseable_locus_level_in_range_end", len(candidates), priority)

    open_ended = ref.following_marker is not None and locus_end is None

    tesserae_work_id = work_rec.get("tesserae_work_id")
    part_id = None
    reason = None
    if tesserae_work_id is None:
        part_id = _route_to_part(work_rec, locus_start)
        if part_id is None:
            reason = "no_combined_file_and_no_part_route_found"

    resolved = tesserae_work_id is not None or part_id is not None
    return Resolution(
        work_id=tesserae_work_id,
        part_id=part_id,
        locus_start=locus_start,
        locus_end=locus_end,
        open_ended=open_ended,
        open_ended_marker=ref.following_marker,
        resolved=resolved,
        reason=reason,
        work_candidates_considered=len(candidates),
        match_priority=priority,
    )
