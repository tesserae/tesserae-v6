"""
Top-level citation extractor API: find_citations(text) -> list of dicts, one
per recognized citation-reference, each with the surface string, character
offsets, and the resolved (work_id, locus_start, locus_end) or a failure
reason. This is Part 2 of the citation-extractor task; see parser.py for the
grammar reimplementation and resolver.py for locus resolution.
"""
import json
import os
import re
from dataclasses import asdict

from .abbrev_index import AbbrevIndex
from .parser import find_citations as _find_citations_raw, is_roman_shaped
from .resolver import resolve_ref, level_to_arabic, roman_to_int, levels_to_locus_string


_DEFAULT_INDEX = None

# Per-work locus depth, derived from the live corpus's own .tess tags by
# scripts/citations/derive_work_depth.py (see that script's docstring and
# COMMA_CHAIN_DIAGNOSIS.md section 1). {work_id: modal_depth} plus the list
# of work ids whose depth is NOT consistent across the corpus (a mix of
# depths in the tagged lines themselves, e.g. a preface tagged one level
# shallower) -- those are never trusted for truncation, since there's no
# single right answer to truncate to.
_CITATIONS_DIR = os.path.dirname(os.path.abspath(__file__))
_WORK_DEPTH = None
_WORK_DEPTH_INCONSISTENT = None

# A second per-work depth, from scripts/citations/derive_work_depth_journal.py:
# the modal number of locus levels a work is actually cited at in the EJC
# journal corpus itself (citations_v2.db, built before any depth rule
# existed), for any work with at least 10 citations there. Some works are
# conventionally cited MORE precisely than this corpus's own .tess tagging
# supports (Tacitus' Annales tagged book.chapter but cited book.chapter.
# section; Plautus tagged as one flat run of line numbers but cited act.
# scene.line -- COMMA_CHAIN_DIAGNOSIS.md section 3 items 6-7, confirmed
# live and harming real rows in REPORT_v3.md section 7). Truncating/
# splitting those citations down to the corpus's own (shallower) depth
# silently drops a real section number or fragments one citation into
# several wrong ones. See _apply_work_depth: the truncate/split rule now
# fires only when a locus exceeds BOTH depths; a locus AT the journal
# depth (deeper than the corpus depth) is left whole.
_WORK_DEPTH_JOURNAL = None

# A third, hand-curated override, backend/citations/work_depth_overrides.json:
# {work_id: depth}, loaded AFTER the journal table and taking precedence
# over both it and the corpus depth (work_depth.json) -- including that
# table's own "inconsistent, don't trust" exclusion. Exists because the
# automatic journal-depth derivation (above) cannot reliably tell a
# work's genuine-but-minority deeper citation convention apart from
# another work's similarly-large minority of citation noise (see
# derive_work_depth_journal.py's own docstring) -- Tacitus' Annales and
# Historiae (book.chapter.section) and every Plautus and Terence play
# (act.scene.line, the universal convention for Roman comedy) are
# confirmed by direct reading, the same way COMMA_CHAIN_DIAGNOSIS.md named
# them, not derived from a statistic. scripts/citations/
# list_depth_override_candidates.py surfaces further candidates for this
# file to be hand-extended later; it does not write to this file itself.
_WORK_DEPTH_OVERRIDES = None

# A per-work maximum line/locus value, from scripts/citations/
# derive_work_max_line.py, {work_id: max_line}. Used only for a depth-1
# work's OCR-digit-join guard below (_join_short_digit_levels): a joined
# number is kept only when it's inside the work's own actual line range,
# never accepted just because the digits happened to concatenate cleanly.
_WORK_MAX_LINE = None


def _load_work_depth():
    global _WORK_DEPTH, _WORK_DEPTH_INCONSISTENT
    if _WORK_DEPTH is None:
        try:
            with open(os.path.join(_CITATIONS_DIR, "work_depth.json"), encoding="utf-8") as f:
                _WORK_DEPTH = json.load(f)
        except (OSError, json.JSONDecodeError):
            _WORK_DEPTH = {}
        try:
            with open(os.path.join(_CITATIONS_DIR, "work_depth_inconsistent.json"), encoding="utf-8") as f:
                _WORK_DEPTH_INCONSISTENT = set(json.load(f))
        except (OSError, json.JSONDecodeError):
            _WORK_DEPTH_INCONSISTENT = set()
    return _WORK_DEPTH, _WORK_DEPTH_INCONSISTENT


def _load_work_depth_journal():
    global _WORK_DEPTH_JOURNAL
    if _WORK_DEPTH_JOURNAL is None:
        try:
            with open(os.path.join(_CITATIONS_DIR, "work_depth_journal.json"), encoding="utf-8") as f:
                _WORK_DEPTH_JOURNAL = json.load(f)
        except (OSError, json.JSONDecodeError):
            _WORK_DEPTH_JOURNAL = {}
    return _WORK_DEPTH_JOURNAL


def _load_work_depth_overrides():
    global _WORK_DEPTH_OVERRIDES
    if _WORK_DEPTH_OVERRIDES is None:
        try:
            with open(os.path.join(_CITATIONS_DIR, "work_depth_overrides.json"), encoding="utf-8") as f:
                _WORK_DEPTH_OVERRIDES = json.load(f)
        except (OSError, json.JSONDecodeError):
            _WORK_DEPTH_OVERRIDES = {}
    return _WORK_DEPTH_OVERRIDES


def _load_work_max_line():
    global _WORK_MAX_LINE
    if _WORK_MAX_LINE is None:
        try:
            with open(os.path.join(_CITATIONS_DIR, "work_max_line.json"), encoding="utf-8") as f:
                _WORK_MAX_LINE = json.load(f)
        except (OSError, json.JSONDecodeError):
            _WORK_MAX_LINE = {}
    return _WORK_MAX_LINE


def _is_short_digit_run(token):
    return token.isdigit() and 1 <= len(token) <= 2


def _join_short_digit_levels(levels):
    """OCR sometimes splits one multi-digit line number into several short
    digit runs across whitespace ('Ar. Ach. 1 1 24' for line 1124) -- the
    tokenizer has no way to tell that apart from a genuine multi-level
    locus at parse time, so it reads three levels. If EVERY level here is
    a bare 1-2 digit run (never a Roman numeral -- a real book/act number
    is never this kind of OCR artifact), concatenating them back in order
    is a plausible undo. Returns the joined digit string, or None if any
    level doesn't qualify (a Roman numeral, a 3+ digit run, anything
    else) -- callers must still range-check the result themselves."""
    if not levels or not all(_is_short_digit_run(t) for t in levels):
        return None
    return "".join(levels)


def _is_clean_split_level(token):
    """A remaining, truncated-off level is safe to read as its OWN separate
    citation only when it is a plain Arabic number that isn't 4 digits (a
    publication year, footnote number, or Stephanus/edition page number --
    see COMMA_CHAIN_DIAGNOSIS.md section 3, items 1 and 2) or a Roman
    numeral of two or more characters (a single Roman letter, e.g. 'C' or
    'I', is exactly as likely to be an edition-page letter or an OCR'd
    '(c.' abbreviation for 'circa' as a real numeral -- same section)."""
    if token.isdigit():
        return len(token) != 4
    if is_roman_shaped(token):
        return len(token.rstrip(".")) >= 2
    return False


def _apply_work_depth(out_dict, ref, depth_map=None, inconsistent=None, journal_depth_map=None,
                       overrides=None, max_line_map=None):
    """When a resolved citation's own locus has more levels than its work's
    known, consistent depth, truncate it to that depth. Split the
    truncated-off remainder into further whole citations ONLY in the one
    clean case COMMA_CHAIN_DIAGNOSIS.md's own hand-check found reliable:
    the remainder is exactly a multiple of the work's depth, every
    remaining level passes _is_clean_split_level, and this citation is not
    already a range (a range's start levels reflect level-count/digit-
    shorthand borrowing from resolver._expand_range, not a comma chain, and
    splitting one apart was the single largest source of wrong rows in
    that diagnosis's own hand-check). Otherwise: truncate and drop the
    remainder. Always returns a non-empty list of output dicts.

    The truncation target depth, and the threshold a locus must exceed
    before the rule fires at all, come from three layered sources:

    1. overrides (work_depth_overrides.json): a hand-curated {work_id:
       depth}. When present for this work_id, it is FINAL -- it is used as
       both the truncation target and the threshold, and bypasses the
       corpus depth entirely, including its "inconsistent, don't trust"
       exclusion (see work_depth_inconsistent.json). This exists because
       neither of the two tables below can reliably tell a work's
       genuine-but-minority deeper citation convention apart from another
       work's similarly large minority of citation noise (see
       derive_work_depth_journal.py's own docstring) -- some works need a
       human-confirmed answer instead.
    2. Otherwise, the threshold is max(corpus depth, journal depth): the
       rule fires only when the locus exceeds BOTH the corpus depth
       (depth_map, from the corpus's own .tess tags) AND the work's
       journal depth (journal_depth_map, from how this genre of journal
       prose actually cites the work in citations_v2.db). A work with no
       journal-depth entry (fewer than 10 citations there) falls back to
       the corpus depth alone. The truncation target in this case is
       still the CORPUS depth (the shallower one), same as before this
       parameter existed.

    This protects a work whose real citation convention is genuinely
    deeper than the corpus's own tagging (Tacitus' Annales, book.chapter
    tagged but book.chapter.section cited; Plautus and Terence, tagged
    flat or act.scene but cited act.scene.line) from having a correct,
    more precise locus truncated or fragmented -- see REPORT_v3.md
    section 7.

    A depth-1 work (a single running number: a line, a section...) never
    goes through the truncate/split path described above at all -- see
    the dedicated depth==1 branch below and _join_short_digit_levels's
    own docstring for why (a fault seen live in the preview, 2026-09-18:
    OCR splitting one multi-digit line number across whitespace, "Ar.
    Ach. 1 1 24" for line 1124, was being truncated to line 1 and shown
    that way in the connection panel).

    depth_map/inconsistent/journal_depth_map/overrides/max_line_map
    default to the loaded, cached module data; a caller (tests) may
    inject its own dict to exercise this logic without depending on the
    real, derived tables."""
    if not out_dict["resolved"] or not out_dict["work_id"] or not out_dict["locus_start"]:
        return [out_dict]

    if depth_map is None or inconsistent is None:
        loaded_depth_map, loaded_inconsistent = _load_work_depth()
        depth_map = loaded_depth_map if depth_map is None else depth_map
        inconsistent = loaded_inconsistent if inconsistent is None else inconsistent
    if journal_depth_map is None:
        journal_depth_map = _load_work_depth_journal()
    if overrides is None:
        overrides = _load_work_depth_overrides()

    work_id = out_dict["work_id"]
    override_depth = overrides.get(work_id)
    if override_depth:
        depth = override_depth
        threshold = override_depth
    else:
        depth = depth_map.get(work_id)
        if not depth or work_id in inconsistent:
            return [out_dict]
        journal_depth = journal_depth_map.get(work_id, depth)
        threshold = max(depth, journal_depth)

    start_parts = out_dict["locus_start"].split(".")
    if len(start_parts) <= threshold:
        return [out_dict]

    if depth == 1:
        # A depth-1 work is addressed by a single running number. Unlike
        # a deeper work, "truncate to the first level" is actively wrong
        # here: the first level of an over-deep depth-1 locus is very
        # often just the LEADING digits of the real number, not an
        # independent citation on its own -- confirmed live in the
        # preview, 2026-09-18: "Ar. Ach. 1 1 24" and "Aristoph. Ach. 1 1
        # 28" (OCR splitting "1124"/"1128" across whitespace) were being
        # truncated to line 1 and shown that way in the connection panel.
        # So a depth-1 work bypasses the comma-boundary/truncate/split
        # path entirely:
        if max_line_map is None:
            max_line_map = _load_work_max_line()
        joined = _join_short_digit_levels(ref.start_levels)
        max_line = max_line_map.get(work_id)
        if joined is not None and max_line is not None and 1 <= int(joined) <= max_line:
            rejoined = dict(out_dict)
            rejoined["locus_start"] = joined
            rejoined["locus_end"] = None
            rejoined["reason"] = "joined_ocr_split_digits"
            return [rejoined]
        # Not a safe join (a Roman numeral among the levels, a level
        # already 3+ digits, or the joined number falls outside this
        # work's own line range) -- drop the whole citation. A leading
        # "1" or "2" is almost always the start of a longer number, not
        # a line of its own, so keeping it as a truncated first level
        # would just move the same wrong-line fault somewhere else.
        return []

    # Only ever truncate/split at a COMMA boundary. A citation that reaches
    # past the work's depth using DOTS the whole way ("Cic. Leg. 3. 6",
    # Tacitus "Ann. iii. 53. 7", Cicero "De Or. II, 45, 189" once past the
    # first comma) is far more likely to be a genuine attempt at a citation
    # more precise than this corpus's own tagging supports -- a corpus-
    # resolution gap (COMMA_CHAIN_DIAGNOSIS.md section 3, item 6) -- than a
    # fabricated locus. Every one of this task's own worked examples
    # ("Aen. 2, 283, 10, 327", "Aen. 3.296, 7.433, 11.270", "Aen. III. 581,
    # I", "Arch. XXII, 1913") crosses the depth boundary at a comma; none
    # crosses it at a dot. Leaving a dot-joined over-deep locus untouched
    # (rather than truncating it) matches how the rest of this codebase
    # already treats comma and dot as similar-but-not-identical separators
    # (see parser.py's own book-list fix, gated the same way).
    seps = ref.start_seps or []
    boundary = depth - 1
    if boundary >= len(seps) or seps[boundary] != "COMMA":
        return [out_dict]

    truncated = dict(out_dict)
    truncated["locus_start"] = ".".join(start_parts[:depth])
    if truncated["locus_end"]:
        end_parts = truncated["locus_end"].split(".")
        if len(end_parts) > depth:
            truncated["locus_end"] = ".".join(end_parts[:depth])
    truncated["reason"] = "truncated_to_work_depth"

    if out_dict["locus_end"] is not None:
        # A range: truncate, never split further.
        return [truncated]

    remainder_raw = list(ref.start_levels[depth:])
    if not remainder_raw or len(remainder_raw) % depth != 0:
        return [truncated]
    if not all(_is_clean_split_level(t) for t in remainder_raw):
        return [truncated]

    splits = [truncated]
    for i in range(0, len(remainder_raw), depth):
        group = remainder_raw[i:i + depth]
        arabic = [level_to_arabic(t) for t in group]
        if any(a is None for a in arabic):
            return [truncated]
        split_dict = dict(out_dict)
        split_dict["locus_start"] = ".".join(arabic)
        split_dict["locus_end"] = None
        split_dict["reason"] = "split_from_over_deep_locus"
        splits.append(split_dict)
    return splits

# Plain 'Od.' (the bare, single-token abbreviation -- match_priority 2; not
# combined with 'Hom.' at priority 1, and not the spelled-out 'Odyssey'
# title at priority 3) genuinely competes with Horace's four-book Odes when
# the book number is 1-4 -- about 40% of the time in a 28,612-article
# journal sample (see HOMER_DIAGNOSIS.md section 1). Books 5-24 are
# impossible for Horace (he wrote only four books) and are always safe.
# A Greek-letter book number ('Od. λ 90') carries none of this risk at all
# -- Horace's Odes are never numbered with Greek letters -- so the guard
# below only ever applies when the book level was Roman or Arabic.
_OD_HORACE_RISK_WINDOW = 30
_HOM_RE = re.compile(r"\bhom", re.IGNORECASE)


def _od_book_1_4_needs_context(res, ref, text):
    """True if this resolved Odyssey citation is the bare 'Od.' + Roman/
    Arabic book 1-4 form and no 'Hom'/'Homer' appears in the preceding
    window -- i.e. it should be treated as unresolved rather than assumed
    to be Homer over Horace."""
    if not res.resolved or res.work_id != "homer.odyssey":
        return False
    if res.match_priority != 2:
        return False
    if not ref.start_levels:
        return False
    first_level = ref.start_levels[0]
    if not (first_level.isdigit() or is_roman_shaped(first_level)):
        return False  # Greek-letter book: no Horace risk, never guarded
    try:
        book = int(res.locus_start.split(".")[0])
    except (AttributeError, ValueError, IndexError):
        return False
    if not (1 <= book <= 4):
        return False
    window_start = max(0, ref.start_offset - _OD_HORACE_RISK_WINDOW)
    context = text[window_start:ref.start_offset]
    return not _HOM_RE.search(context)


# "Rep." with no author context is ambiguous between Cicero's De Republica
# and Plato's Republic (both registered as candidates -- see the 2026-09-18
# abbreviation-table fix), and the resolver correctly leaves it unresolved
# rather than guess. REPORT_v3.md's rebuild found this costs real recall:
# plato.respublica dropped from a wrongly-confident 839 (nearly all really
# Plato or noise, per HOMER_DIAGNOSIS.md-style hand-checking) to 15, and a
# few genuine Plato citations with the author named a sentence or more
# away (outside the author-context window) now resolve to neither work.
#
# One positive signal doesn't need any author name at all: Stephanus
# pagination. Plato's Republic is always cited by a page number printed in
# Stephanus' 1578 edition (327-621 for the Republic specifically) plus a
# subdivision letter a-e, optionally with a leading book number (Republic
# is divided into both 10 books AND continuous Stephanus pages) --
# "Rep. VI. 511 D" or bare "Rep. 511 D". Cicero's own six-book De
# Republica is never cited this way (no Stephanus edition, no a-e
# subdivision letters, and none of its own section numbers reach anywhere
# near 327-621). A bare book.section locus with small numbers and no
# trailing letter -- Cicero's own shape -- carries no such signal and is
# left unresolved, same as before this fix.
_REP_AMBIGUOUS_PAIR = {"cicero.de_republica", "plato.respublica"}
_STEPHANUS_LETTERS = set("abcde")
_STEPHANUS_PAGE_MIN, _STEPHANUS_PAGE_MAX = 327, 621
_STEPHANUS_BOOK_MIN, _STEPHANUS_BOOK_MAX = 1, 10


def _is_stephanus_locus(levels):
    """levels: raw (pre-arabic) locus levels, most specific last. True for
    an Arabic Stephanus page (327-621) followed by a single subdivision
    letter (a-e), optionally preceded by a Roman book number (1-10)."""
    if len(levels) not in (2, 3):
        return False
    letter = levels[-1].rstrip(".")
    if len(letter) != 1 or letter.lower() not in _STEPHANUS_LETTERS:
        return False
    page = levels[-2]
    if not page.isdigit() or not (_STEPHANUS_PAGE_MIN <= int(page) <= _STEPHANUS_PAGE_MAX):
        return False
    if len(levels) == 3:
        book = levels[0]
        if not is_roman_shaped(book):
            return False
        book_val = roman_to_int(book)
        if book_val is None or not (_STEPHANUS_BOOK_MIN <= book_val <= _STEPHANUS_BOOK_MAX):
            return False
    return True


def _rep_stephanus_override(res, ref):
    """When res is the unresolved 'Rep.' ambiguity (Cicero/Plato tied) and
    the raw locus is Stephanus-shaped, return the {work_id, part_id,
    locus_start} to resolve it to plato.respublica outright. Returns None
    when it doesn't apply (including: already resolved, a different
    ambiguity, or no Stephanus shape) -- callers should leave res alone."""
    if res.resolved or not res.reason or not res.reason.startswith("ambiguous_work"):
        return None
    candidates = {c[0] for c in (ref.work_candidates or [])}
    if not _REP_AMBIGUOUS_PAIR.issubset(candidates):
        return None
    if not ref.start_levels or not _is_stephanus_locus(ref.start_levels):
        return None
    locus_start = levels_to_locus_string(ref.start_levels, stephanus=True)
    if locus_start is None:
        return None
    return {"work_id": "plato.respublica", "part_id": None, "locus_start": locus_start}


def get_default_index(abbreviations_path="data/abbreviations.json"):
    global _DEFAULT_INDEX
    if _DEFAULT_INDEX is None:
        _DEFAULT_INDEX = AbbrevIndex(abbreviations_path)
    return _DEFAULT_INDEX


def extract(text, index=None):
    """Returns a list of dicts:
      {
        surface, start, end,               # whole ref span (chain-relative)
        citation_surface, citation_start, citation_end,  # whole semicolon-chained group
        work_surface,                      # matched abbreviation text, or None if inherited
        inherited_work,                    # bool
        resolved,                          # bool
        work_id, locus_start, locus_end,   # set iff resolved
        open_ended, open_ended_marker,
        reason,                            # set iff not resolved, or as a caveat
      }
    """
    if index is None:
        index = get_default_index()

    citations = _find_citations_raw(text, index)
    out = []
    for cit in citations:
        inherited_candidates = None
        inherited_surface = None
        for ref in cit.refs:
            effective_candidates = ref.work_candidates
            inherited = False
            if effective_candidates is None:
                effective_candidates = inherited_candidates
                inherited = True
            else:
                inherited_candidates = effective_candidates
                inherited_surface = ref.work_surface

            # build a shallow copy of ref with effective candidates for resolution
            ref_for_resolution = ref
            if inherited:
                ref_for_resolution = type(ref)(
                    work_surface=ref.work_surface,
                    work_candidates=effective_candidates,
                    start_levels=ref.start_levels,
                    end_levels=ref.end_levels,
                    following_marker=ref.following_marker,
                    start_offset=ref.start_offset,
                    end_offset=ref.end_offset,
                    locus_start_offset=ref.locus_start_offset,
                    book_list=ref.book_list,
                    start_seps=ref.start_seps,
                )

            base_out = {
                "surface": text[ref.start_offset:ref.end_offset],
                "start": ref.start_offset,
                "end": ref.end_offset,
                "citation_surface": cit.surface,
                "citation_start": cit.start_offset,
                "citation_end": cit.end_offset,
                "work_surface": ref.work_surface if not inherited else inherited_surface,
                "inherited_work": inherited,
            }

            if ref_for_resolution.book_list:
                # A comma-separated Roman-numeral book list ("Aeneid I, II")
                # resolves to one citation PER book, all sharing the same
                # matched surface/span -- see parser.py's module docstring.
                for book in ref_for_resolution.book_list:
                    book_ref = type(ref_for_resolution)(
                        work_surface=ref_for_resolution.work_surface,
                        work_candidates=ref_for_resolution.work_candidates,
                        start_levels=[book],
                        end_levels=None,
                        following_marker=ref_for_resolution.following_marker,
                        start_offset=ref_for_resolution.start_offset,
                        end_offset=ref_for_resolution.end_offset,
                        locus_start_offset=ref_for_resolution.locus_start_offset,
                        book_list=None,
                    )
                    res = resolve_ref(book_ref, index.works_by_base_id)
                    out.extend(_apply_work_depth(_build_out(base_out, res, book_ref, text), book_ref))
                continue

            res = resolve_ref(ref_for_resolution, index.works_by_base_id)
            out.extend(_apply_work_depth(_build_out(base_out, res, ref_for_resolution, text), ref_for_resolution))
    return out


# A depth-1 work's own bare-number citation ("Arch. 8") is, by design,
# never touched by _apply_work_depth's over-deep guard: a single-level
# locus for a depth-1 work matches the work's own depth EXACTLY, so it
# was never "over-deep" in the first place. REPORT_v7.md section 5 found
# the gap this leaves open: "Arch. 1888" (a bibliographic reference to a
# JOURNAL's volume year, "Archaeologischer Anzeiger 1888, pp. 193 ff.")
# resolves to cicero.pro_archia exactly the same way a genuine section
# number would, with no range check at all -- pro_archia's own line
# range is only 32 (work_max_line.json).
#
# Guard: a single-level (no dot), four-digit Arabic locus in the range a
# real publication year would plausibly fall in is dropped UNLESS the
# work's own line range reaches that number AND the surrounding text
# doesn't otherwise look bibliographic (followed by a comma and a page
# marker, or another year that ISN'T itself a plausible line for this
# work either). Only ever applies to a depth-1 work (its own single-
# level locus is the whole address; the same shape for a deeper work,
# e.g. "Aen. 1888", is an ordinary UNDER-deep book-only citation, an
# existing, accepted class this guard leaves alone entirely -- a book
# number in the high hundreds/low thousands for the Aeneid is obviously
# wrong, but that's a different, pre-existing gap, not this one).
#
# Deliberately NOT checking "wrapped in parentheses" as its own signal,
# despite that being one of the shapes this guard was asked to catch: a
# hand check of this guard's own effect on citations_v7.db found real,
# correct citations in exactly that shape for a long depth-1 work
# ("(Ar. Av. 1714)", Aristophanes' Birds, a genuine line 1714 of a
# 1,765-line play) -- a bare classical locus reference and a bare
# bibliographic year are syntactically identical inside parentheses, so
# parenthesization alone can't tell them apart. The range check already
# catches every case this guard actually needs to catch (a work whose
# own range doesn't reach the number at all, e.g. cicero.pro_archia's 32
# lines against "1888") regardless of parentheses; for a work whose
# range DOES reach the number, being parenthesised is unremarkable.
_YEAR_LOCUS_MIN, _YEAR_LOCUS_MAX = 1500, 2030
_YEAR_CONTEXT_WINDOW = 20
# ", pp. 123" / ", p. 45" (a page reference -- this grammar's own locus
# continuation never uses "p."/"pp.", so this is unconditionally
# bibliographic) or ", 1889" (another four-digit number riding the same
# comma, captured separately since it's only a bibliographic signal when
# THAT number also fails the range check -- a hand check found this
# matching "Aristoph. Av. 1745 ff., 1749 ff.", two genuine, separate line
# citations to the same work, both within its own range).
_TRAILING_BIB_RE = re.compile(r"^\s*,\s*(?:(pp?\.\s*\d)|(\d{4})\b)")


def _year_like_locus_should_drop(work_id, locus_start, ref, text):
    if not work_id or not locus_start or "." in locus_start:
        return False  # not single-level -- this guard never applies
    if not locus_start.isdigit() or len(locus_start) != 4:
        return False
    value = int(locus_start)
    if not (_YEAR_LOCUS_MIN <= value <= _YEAR_LOCUS_MAX):
        return False
    depth_map, _inconsistent = _load_work_depth()
    if depth_map.get(work_id) != 1:
        return False  # under-deep for a deeper work ("Aen. 1888") -- untouched
    max_line_map = _load_work_max_line()
    max_line = max_line_map.get(work_id)
    if not max_line or max_line < value:
        return True  # depth-1, out of the work's own range: drop outright
    end = ref.end_offset
    after = text[end:end + _YEAR_CONTEXT_WINDOW]
    m = _TRAILING_BIB_RE.match(after)
    if m:
        if m.group(1):
            return True  # ", pp. NNN" / ", p. NNN"
        trailing = int(m.group(2))
        if not (1 <= trailing <= max_line):
            return True  # ", <number>" that isn't a plausible line either
    return False


def _build_out(base_out, res, ref, text):
    blocked = _od_book_1_4_needs_context(res, ref, text)
    rep_override = _rep_stephanus_override(res, ref)

    resolved = res.resolved and not blocked
    work_id = None if blocked else res.work_id
    part_id = None if blocked else res.part_id
    locus_start = res.locus_start
    reason = "requires_author_context:od_book_1_4" if blocked else res.reason

    if rep_override:
        resolved = True
        work_id = rep_override["work_id"]
        part_id = rep_override["part_id"]
        locus_start = rep_override["locus_start"]
        reason = "stephanus_locus_disambiguates_to_plato"

    if resolved and _year_like_locus_should_drop(work_id, locus_start, ref, text):
        resolved = False
        work_id = None
        part_id = None
        locus_start = None
        reason = "dropped_year_like_locus"

    return {
        **base_out,
        "resolved": resolved,
        "work_id": work_id,
        "part_id": part_id,
        "locus_start": locus_start,
        "locus_end": res.locus_end,
        "open_ended": res.open_ended,
        "open_ended_marker": res.open_ended_marker,
        "reason": reason,
        "match_priority": res.match_priority,
        "candidates_considered": res.work_candidates_considered,
    }


if __name__ == "__main__":
    import sys
    idx = get_default_index()
    samples = [
        "Aen. 1.1",
        "Verg. A. I 1",
        "Aeneid i. 1 ff.",
        "Il. 1.1-7",
        "Hom. Od. 9.19",
        "Soph. OT 1-13",
        "Hor. C. 1.1.1",
        "Hom. Il. 1,12-20; 2.240",
        "the poet echoes Verg. Aen. 6.847-853 in this passage",
    ]
    for s in samples:
        print(repr(s))
        for r in extract(s, idx):
            print("  ", r)
