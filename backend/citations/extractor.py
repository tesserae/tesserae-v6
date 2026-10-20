"""
Top-level citation extractor API: find_citations(text) -> list of dicts, one
per recognized citation-reference, each with the surface string, character
offsets, and the resolved (work_id, locus_start, locus_end) or a failure
reason. This is Part 2 of the citation-extractor task; see parser.py for the
grammar reimplementation and resolver.py for locus resolution.
"""
import bisect
import json
import os
import re
from dataclasses import asdict, replace

from .abbrev_index import AbbrevIndex, normalize_abbr
from .parser import find_citations as _find_citations_raw, is_roman_shaped
from .resolver import resolve_ref, level_to_arabic, roman_to_int, levels_to_locus_string


_DEFAULT_INDEX = None

# Per-work locus depth, derived from the live corpus's own .tess tags by
# scripts/citations/derive_work_depth.py (see that script's docstring).
# {work_id: modal_depth} plus the list
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
# scene.line -- confirmed, by hand-checking real citations, to be live
# and harming real rows when truncated). Truncating/
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
# confirmed by direct reading, not derived from a statistic. scripts/citations/
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


# Where a work ends, from scripts/citations/derive_work_line_limits.py, both
# in data/citations/ beside the abbreviation table: the per-book last line of
# the verse works cited by book and line ({work_id: {book: last_line}}), and the
# last number of the works whose every corpus locus has one level.
_WORK_BOOK_LINE_MAX = None
# The package sits in backend/citations/ in the repository and in citations/ in
# the rebuild toolkit, so the data folder is searched for beside either parent.
_DATA_DIR = next((d for d in (os.path.join(os.path.dirname(os.path.dirname(_CITATIONS_DIR)), "data", "citations"),
                              os.path.join(os.path.dirname(_CITATIONS_DIR), "data", "citations"))
                  if os.path.exists(os.path.join(d, "work_book_line_max.json"))),
                 os.path.join(os.path.dirname(os.path.dirname(_CITATIONS_DIR)), "data", "citations"))
_BOOK_LINE_MAX_PATH = os.path.join(_DATA_DIR, "work_book_line_max.json")


_WORK_SINGLE_LEVEL_MAX = None
_SINGLE_LEVEL_MAX_PATH = os.path.join(os.path.dirname(_BOOK_LINE_MAX_PATH), "work_single_level_max.json")


def _load_work_single_level_max():
    global _WORK_SINGLE_LEVEL_MAX
    if _WORK_SINGLE_LEVEL_MAX is None:
        try:
            with open(_SINGLE_LEVEL_MAX_PATH, encoding="utf-8") as f:
                _WORK_SINGLE_LEVEL_MAX = json.load(f)
        except (OSError, json.JSONDecodeError):
            _WORK_SINGLE_LEVEL_MAX = {}
    return _WORK_SINGLE_LEVEL_MAX


def _load_work_book_line_max():
    global _WORK_BOOK_LINE_MAX
    if _WORK_BOOK_LINE_MAX is None:
        try:
            with open(_BOOK_LINE_MAX_PATH, encoding="utf-8") as f:
                _WORK_BOOK_LINE_MAX = json.load(f)
        except (OSError, json.JSONDecodeError):
            _WORK_BOOK_LINE_MAX = {}
    return _WORK_BOOK_LINE_MAX


# Short forms that need the author named nearby (abbrev_context_rules.json):
# "form." for Eucherius, "Mem." for Aristotle, "Hel.", "Pol.", "Merc."...
# A hit passes only when the rule's author regex matches the sentence before
# this one or the text of this sentence ahead of the citation, and no
# veto_before pattern (another author, "Ath.", "ad", a commentary title)
# stands right in front of it.
_CONTEXT_RULES = None
_CONTEXT_BEFORE = 300     # characters of context searched on each side
_AFTER_BIBLE_WINDOW = 120  # round 8: a biblical neighbor after the form counts too
_VETO_TAIL = 60           # characters before the citation a veto looks at


def _load_context_rules():
    global _CONTEXT_RULES
    if _CONTEXT_RULES is None:
        try:
            with open(os.path.join(_CITATIONS_DIR, "abbrev_context_rules.json"), encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            raw = {}
        rules = {}
        for key, lst in (raw.get("rules") or {}).items():
            rules[key] = [{
                "work": r["work"],
                "context": re.compile(r["context"]) if r.get("context") else None,
                "veto_before": re.compile(r["veto_before"]) if r.get("veto_before") else None,
                "min_levels_alone": r.get("min_levels_alone", 0),
                "redirect": ({"context": re.compile(r["redirect"]["context"]), "work": r["redirect"]["work"]}
                             if r.get("redirect") else None),
            } for r in lst]
        veto_all = raw.get("veto_before_all")
        disambiguate = {
            key: [{
                "work": r.get("work"),
                "family": r.get("family"),
                "context": re.compile(r["context"]),
                "veto_before": re.compile(r["veto_before"]) if r.get("veto_before") else None,
            } for r in lst]
            for key, lst in (raw.get("disambiguate") or {}).items()}
        ap = raw.get("author_prefix") or {}
        bible = raw.get("bible") or {}
        _CONTEXT_RULES = {"rules": rules, "veto_all": re.compile(veto_all) if veto_all else None,
                          "disambiguate": disambiguate, "defaults": raw.get("defaults") or {},
                          "author_prefix": re.compile(ap["regex"]) if ap.get("regex") else None,
                          "author_prefix_works": ap.get("authors") or {},
                          "bible_forms": set(bible.get("forms") or []),
                          "bible_neighbor": re.compile(bible["neighbor"]) if bible.get("neighbor") else None,
                          "exceeds": raw.get("exceeds") or {},
                          "scholia": ({"regex": re.compile(raw["scholia"]["regex"]), "forms": raw["scholia"].get("forms") or {}}
                                      if raw.get("scholia") else None),
                          "locus_prefix": raw.get("locus_prefix") or {},
                          "modern": [re.compile(x) for x in raw.get("modern_references") or []],
                          "bare_number_limit": raw.get("bare_number_limit") or {}}
    return _CONTEXT_RULES


def _apply_context_rules(work_id, work_surface, anchor_start, text, context, n_levels=0, seps=None, after=""):
    """Returns (work_id, reason). work_id is None when the citation must be
    dropped (reason says why); it may be a different work (redirect) or the
    one given, unchanged, with reason None."""
    if not work_id or not work_surface:
        return work_id, None
    cfg = _load_context_rules()
    ahead = (context or "")[-_CONTEXT_BEFORE:] + " " + text[max(0, anchor_start - _CONTEXT_BEFORE):anchor_start]
    tail = ahead[-_VETO_TAIL:]
    if cfg["veto_all"] and cfg["veto_all"].search(tail):
        return None, "commentary_or_other_author_before"
    # "Tert. de Poen. 1 1", "Lact. de Ira": an author abbreviation stands right
    # before a short title. The citation is to that author, so a work of any
    # other author (Plautus's Poenulus, Seneca's De ira) is wrong.
    if cfg["author_prefix"]:
        m = cfg["author_prefix"].search(tail)
        if m:
            prefix = cfg["author_prefix_works"].get(m.group(1).lower())
            if prefix and not work_id.startswith(prefix):
                return None, "requires_author_context:other_author_before"
    # A biblical book (Marc., Num., Luc., Joh.): chapter:verse with a tight
    # colon, or another biblical book with chapter and verse just before.
    form = normalize_abbr(work_surface)
    if form in cfg["bible_forms"] and (
            "COLON" in (seps or []) or (cfg["bible_neighbor"] and (
                cfg["bible_neighbor"].search(ahead) or cfg["bible_neighbor"].search(after)))):
        return None, "requires_author_context:biblical_book"
    for rule in cfg["rules"].get(normalize_abbr(work_surface), []):
        if rule["work"] != work_id:
            continue
        if rule["veto_before"] and rule["veto_before"].search(tail):
            return None, "requires_author_context:other_author_before"
        if rule["context"] and not rule["context"].search(ahead):
            if rule["min_levels_alone"] and n_levels >= rule["min_levels_alone"]:
                continue
            if rule["redirect"] and rule["redirect"]["context"].search(ahead):
                return rule["redirect"]["work"], None
            return None, "requires_author_context:" + normalize_abbr(work_surface)
    return work_id, None


def _disambiguate_candidates(candidates, work_surface, anchor_start, text, context, works, n_levels=0,
                             first_level=""):
    """Author-context choice among works that share one short form. The
    "disambiguate" table in abbrev_context_rules.json lists, per form
    ("met", "ep", "ecl"), the works it can mean and a regex for the author
    that picks each. The rule whose author is named closest before the
    citation (sentence before, or this sentence ahead of it) wins, and its
    work becomes the only candidate, at priority 0. A rule may name a
    "family" (an author in speech_numbers.json) instead of one work: every
    file of that author becomes a candidate, and _route_speech_family then
    picks the file from the speech number. When no author is named, a form
    listed under "defaults" falls back to its default work if that work is
    among the candidates and the citation has at least min_levels locus
    levels ("Lys. 12.4" is Lysias, not the Lysistrata, whose lines are
    cited with a single number). Returns the candidates unchanged when
    nothing applies, so a bare "Met." stays unresolved."""
    if not work_surface or anchor_start is None:
        return candidates
    cfg = _load_context_rules()
    key = normalize_abbr(work_surface)
    scholia = cfg["scholia"]
    if scholia and key in scholia["forms"]:
        # Round 8: "Schol. on Lys. 643" is a scholion on the Lysistrata (lines are
        # cited by one number), since no speech of Lysias has so high a number.
        rule = scholia["forms"][key]
        near = (context or "")[-_CONTEXT_BEFORE:] + " " + text[max(0, anchor_start - _CONTEXT_BEFORE):anchor_start]
        if (scholia["regex"].search(near[-_VETO_TAIL:]) and first_level.isdigit()
                and int(first_level) > rule["first_level_above"] and rule["work"] in works):
            return [(rule["work"], 0, work_surface)]
    rules = cfg["disambiguate"].get(key)
    if rules:
        ahead = (context or "")[-_CONTEXT_BEFORE:] + " " + text[max(0, anchor_start - _CONTEXT_BEFORE):anchor_start]
        best_end, best = -1, None
        for rule in rules:
            if rule["work"] and rule["work"] not in works:
                continue
            if rule["veto_before"] and rule["veto_before"].search(ahead[-_VETO_TAIL:]):
                continue
            for m in rule["context"].finditer(ahead):
                if m.end() > best_end:
                    best_end, best = m.end(), rule
        if best is not None:
            if best["family"]:
                ids = sorted(set(_load_speech_numbers().get(best["family"], {}).get("ids", [])))
                return [(i, 0, work_surface) for i in ids if i in works] or candidates
            return [(best["work"], 0, work_surface)]
    default = cfg["defaults"].get(key)
    if default and default.get("firm_first") and not (
            first_level.isdigit() or (first_level.isupper() and is_roman_shaped(first_level)
                                        and (len(first_level) >= 2 or first_level in ("I", "V", "X")))):
        # "Ann. d. 1" (Annali dell'Istituto) reads d as 500: a default work
        # needs an Arabic number or an upper-case Roman numeral to start on.
        default = None
    if default and n_levels >= default.get("min_levels", 1):
        for c in candidates:
            if c[0] == default["work"]:
                return [(c[0], c[1], work_surface)]
    return candidates


# Authors the corpus files one speech (or ode group) per work: the number at
# the head of the locus chooses the file ("Dem. 21.72" is the speech Against
# Midias). speech_numbers.json: {author: {"21": file, ..., "1-14": file}}.
_SPEECH_NUMBERS = None


def _load_speech_numbers():
    global _SPEECH_NUMBERS
    if _SPEECH_NUMBERS is None:
        try:
            with open(os.path.join(_CITATIONS_DIR, "speech_numbers.json"), encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            raw = {}
        out = {}
        for author, table in raw.items():
            if author.startswith("_") or not isinstance(table, dict):
                continue
            exact, ranges = {}, []
            for k, work in table.items():
                if "-" in k:
                    lo, hi = k.split("-", 1)
                    ranges.append((int(lo), int(hi), work))
                else:
                    exact[int(k)] = work
            out[author] = {"exact": exact, "ranges": ranges,
                           "ids": sorted(set(exact.values()) | {r[2] for r in ranges})}
        _SPEECH_NUMBERS = out
    return _SPEECH_NUMBERS


def _route_speech_family(ref, works):
    """When a citation's candidates are all files of one author in
    speech_numbers.json ("Dem.", "Aeschin.", "Andoc.", "Din.", "B."), and
    the first locus level is a known speech number, keep only the file that
    holds that speech. The locus is left as written: these files are tagged
    speech.section (<dem. 21.72>), so "Dem. 21.72" stays 21.72. Anything else
    comes back unchanged."""
    cands = ref.work_candidates
    if not cands or not ref.start_levels or len(ref.start_levels) < 2:
        return ref
    best = min(c[1] for c in cands)
    top = {c[0] for c in cands if c[1] == best}
    authors = {i.split(".", 1)[0] for i in top}
    if len(top) < 2 or len(authors) != 1:
        return ref
    fam = _load_speech_numbers().get(next(iter(authors)))
    if not fam:
        return ref
    number = level_to_arabic(ref.start_levels[0])
    if number is None or not number.isdigit():
        return ref
    n = int(number)
    target = fam["exact"].get(n)
    if target is None:
        for lo, hi, work in fam["ranges"]:
            if lo <= n <= hi:
                target = work
                break
    if target is None or target not in works or target not in top:
        return ref
    return replace(ref, work_candidates=[(target, best, cands[0][2])])


# Pindar: pindar.odes holds all four books under one file whose lines are
# tagged <pind. o. 1.1>, so Olympian 1 line 1 and Pythian 1 line 1 share the
# locus 1.1. The book letter, taken from the form that named the work
# ("Ol.", "Pyth.", "Nem.", "Isth.", or the bare letter), is put in front:
# o.1.1. A form that names no book (Pind., Pi.) is left alone.
_PINDAR_BOOK = {
    "o": "o", "ol": "o", "olymp": "o",
    "p": "p", "py": "p", "pyth": "p",
    "n": "n", "ne": "n", "nem": "n",
    "i": "i", "is": "i", "isth": "i", "isthm": "i",
}


_PINDAR_LETTER_LEVEL = re.compile(r"[\s,:]*(O|P|N|I)\.?[\s,]+\d")


_MAX_PINDAR_ODES = 14


def _prefix_pindar_book(outs):
    for d in outs:
        # P. and N. are admitted by the parser only for Pindar; a single
        # number after them is a page or a note ("P. 45").
        if (d.get("resolved") and d.get("work_id") == "pindar.odes"
                and normalize_abbr(d.get("work_surface") or "") in ("p", "n")
                and "." not in (d.get("locus_start") or "")):
            d.update(resolved=False, work_id=None, part_id=None, locus_start=None,
                     reason="requires_two_levels:" + normalize_abbr(d["work_surface"]))
            continue
        if not d.get("resolved") or d.get("work_id") != "pindar.odes" or not d.get("work_surface"):
            continue
        book = _PINDAR_BOOK.get(normalize_abbr(d["work_surface"]).split(" ")[-1])
        if not book and d.get("locus_start") and d["locus_start"].count(".") == 2:
            # "Pi. I. 8.47": the book letter came after the author's name and
            # was read as a first level (I = 1). Three levels with a letter
            # in front are letter, ode, line.
            m = _PINDAR_LETTER_LEVEL.match((d.get("surface") or "")[len(d["work_surface"]):])
            if m:
                book = _PINDAR_BOOK[m.group(1).lower()]
                d["locus_start"] = d["locus_start"].split(".", 1)[1]
                if d.get("locus_end") and d["locus_end"].count(".") == 2:
                    d["locus_end"] = d["locus_end"].split(".", 1)[1]
        if not book or not d.get("locus_start") or d["locus_start"][:2] == book + ".":
            continue
        if d["locus_start"].isdigit() and int(d["locus_start"]) > _MAX_PINDAR_ODES:
            # "Pyth. 143": a single number after a book letter is an ode, and no
            # book has more than fourteen
            d.update(resolved=False, work_id=None, part_id=None, locus_start=None, locus_end=None,
                     reason="ode_number_beyond_book")
            continue
        d["locus_start"] = book + "." + d["locus_start"]
        if d.get("locus_end"):
            d["locus_end"] = book + "." + d["locus_end"]
    return outs


_WORK_MAX_BOOK = None


def _load_work_max_book():
    global _WORK_MAX_BOOK
    if _WORK_MAX_BOOK is None:
        try:
            with open(os.path.join(_CITATIONS_DIR, "work_max_book.json"), encoding="utf-8") as f:
                _WORK_MAX_BOOK = json.load(f)
        except (OSError, json.JSONDecodeError):
            _WORK_MAX_BOOK = {}
    return _WORK_MAX_BOOK


def _dropped_by_round2(out_dict):
    reason = out_dict.get("reason") or ""
    return not out_dict["resolved"] and (
        reason.startswith("requires_author_context:") or reason == "dropped_missing_book_number"
        or reason.startswith("dropped_locus_beyond_work")
        or reason == "commentary_or_other_author_before")


def _impossible_book_locus(work_id, locus_start, works=None):
    """"Aen. 1583": a locus on a work cited at two or more levels whose first
    number is beyond the highest first level (book) the work has in the corpus.
    With one level, the book number is missing and the digits are a line
    number, a page or a year. With more ("Div. 11, 67", OCR of II for 11), the
    first level cannot be a book (round 6). Either way the citation cannot be
    placed."""
    if not work_id or not locus_start:
        return False
    if works and (works.get(work_id) or {}).get("stephanus"):
        return False  # cited by Stephanus page, a plain number is legitimate
    overrides = _load_work_depth_overrides()
    depth_map, inconsistent = _load_work_depth()
    depth = overrides.get(work_id) or (None if work_id in inconsistent else depth_map.get(work_id))
    if not depth or depth < 2:
        return False
    # Terence's lines, Horace's satires and others are cited by one running
    # number in the journals; only a work actually cited at two or more
    # levels there (Aeneid: book and line) has a "missing book number".
    # Round 8: a locus that already has two levels ("Cons. 11, 42") names a book
    # first, whatever the journals do with the bare number, so the journal-depth
    # guard holds for one level only. (A work whose first level only ever takes the
    # values 1 and 2 is left out: the Verrines open with the speech, so a 3 or 4
    # there is a book of the second speech, not a book.)
    max_book = _load_work_max_book().get(work_id)
    if (_load_work_depth_journal().get(work_id) or 0) < 2 and ("." not in locus_start or (max_book or 0) <= 2):
        return False
    m = re.match(r"\d+", locus_start)
    return bool(max_book and m and int(m.group()) > max_book)


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
    publication year, footnote number, or Stephanus/edition page number)
    or a Roman numeral of two or more characters (a single Roman letter,
    e.g. 'C' or 'I', is exactly as likely to be an edition-page letter or
    an OCR'd '(c.' abbreviation for 'circa' as a real numeral)."""
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
    clean case a hand-check of real citations found reliable:
    the remainder is exactly a multiple of the work's depth, every
    remaining level passes _is_clean_split_level, and this citation is not
    already a range (a range's start levels reflect level-count/digit-
    shorthand borrowing from resolver._expand_range, not a comma chain, and
    splitting one apart was the single largest source of wrong rows found
    by hand-checking real citations). Otherwise: truncate and drop the
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
       prose actually cites the work in a sample of pre-1923 journal
       citations). A work with no
       journal-depth entry (fewer than 10 citations there) falls back
       to
       the corpus depth alone. The truncation target in this case is
       still the CORPUS depth (the shallower one), same as before this
       parameter existed.

    This protects a work whose real citation convention is genuinely
    deeper than the corpus's own tagging (Tacitus' Annales, book.chapter
    tagged but book.chapter.section cited; Plautus and Terence, tagged
    flat or act.scene but cited act.scene.line) from having a correct,
    more precise locus truncated or fragmented.

    A depth-1 work (a single running number: a line, a section...) never
    goes through the truncate/split path described above at all -- see
    the dedicated depth==1 branch below and _join_short_digit_levels's
    own docstring for why: OCR splitting one multi-digit line number
    across whitespace ("Ar. Ach. 1 1 24" for line 1124) was being
    truncated to line 1 and shown that way in the connection panel.

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
        # independent citation on its own -- confirmed live: "Ar. Ach.
        # 1 1 24" and "Aristoph. Ach. 1 1 28" (OCR splitting "1124"/
        # "1128" across whitespace) were being truncated to line 1 and
        # shown that way in the connection panel.
        # So a depth-1 work bypasses the comma-boundary/truncate/split
        # path entirely:
        if max_line_map is None:
            max_line_map = _load_work_max_line()
        # OCR splits one number across whitespace or a thousands comma ("Ach. 1 1
        # 24", "Ach. 1,124"). A point-joined item of a comma list ("AJ 4.100,
        # 9.7, 14.54") is chapter and verse, not a split number (round 6).
        joined = (None if "DOT" in (ref.start_seps or []) and (ref.after_comma or ref.comma_chain)
                  else _join_short_digit_levels(ref.start_levels))
        max_line = max_line_map.get(work_id)
        levels = ref.start_levels or []
        if (len(levels) == 2 and (ref.start_seps or []) == ["DOT"] and not out_dict.get("locus_end")
                and all(t.isdigit() for t in levels) and 0 < int(levels[1]) - int(levels[0]) <= _MAX_DOTTED_RANGE
                and max_line is not None and int(levels[1]) <= max_line):
            # Round 8: "Av. 17. 18" is lines 17 to 18 written without the hyphen. The
            # work has one level, so a dot cannot join a book and a line.
            ranged = dict(out_dict, locus_start=levels[0], locus_end=levels[1], reason="range_without_hyphen")
            return [ranged]
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
    # resolution gap -- than a fabricated locus. Every one of these
    # worked examples
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
    if (_SPLIT_NEXT_LINE and len(remainder_raw) == 1 and depth == 2 and remainder_raw[0].isdigit() and len(remainder_raw[0]) != 4
            and out_dict["locus_end"] is None
            and _line_beyond_book(work_id, start_parts[:depth - 1] + remainder_raw) is False):
        # Round 8: "Ars am. 2.691, 721" is two lines of book 2: one level more than
        # the work has, after a comma, is the next line of the same book. Only for
        # the verse works of the book-line table, whose next number fits the book
        # (a prose work cited by book, chapter and section has no such list).
        extra = dict(out_dict)
        extra["locus_start"] = ".".join(start_parts[:depth - 1] + remainder_raw)
        extra["locus_end"] = None
        extra["reason"] = "split_from_over_deep_locus"
        return [truncated, extra]
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
# the book number is 1-4 -- about 40% of the time in a sample of over
# 28,000 journal articles. Books 5-24 are
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
# and Plato's Republic (both registered as candidates), and the resolver
# correctly leaves it unresolved rather than guess. This costs real
# recall: plato.respublica dropped from a wrongly-confident 839 (nearly
# all really Plato or noise, by hand-checking) to 15, and a
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


# Round 8. Middle English set in a typeface with the thorn, read by OCR as f
# ("fe" for the, "fat" for that, "fou" for thou): "I. doo fat. I. haf euerlaatinge
# lijf" is no citation of De fato. Latin, Greek and the modern languages of the
# journals have no such run of words.
_THORN_WORDS = {"fe", "fat", "fis", "fou", "fei", "fai", "fan", "fanne", "fenne", "fer", "fere", "fus", "fam",
                "fem", "fyng", "fey", "fese"}
_THORN_MIN_WORDS, _THORN_MIN_FE, _THORN_MIN_FAT = 5, 2, 2    # German Fraktur OCR has "fe" (sie) too, but no "fat"


def _is_thorn_ocr(text):
    words = re.findall(r"[A-Za-z]+", text.lower())
    hits = [w for w in words if w in _THORN_WORDS]
    return len(hits) >= _THORN_MIN_WORDS and hits.count("fe") >= _THORN_MIN_FE and hits.count("fat") >= _THORN_MIN_FAT


def get_default_index(abbreviations_path="data/abbreviations.json"):
    global _DEFAULT_INDEX
    if _DEFAULT_INDEX is None:
        _DEFAULT_INDEX = AbbrevIndex(abbreviations_path)
    return _DEFAULT_INDEX


def extract(text, index=None, context=""):
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
    if _is_thorn_ocr(text):
        return []

    # `context` is the sentence before `text`, for the author-context rules.
    citations = _find_citations_raw(text, index, context)
    out = []
    chain_author = None
    chain_token = None       # the author word of the last reference with one (round 8)
    chain_decision = None    # what that word decided, carried to the items that inherit the work
    prev_cit_end = 0
    for cit in citations:
        inherited_candidates = None
        inherited_surface = None
        anchor_start = None
        chain_dropped = False
        # The author of the previous reference carries over to a bare title that
        # follows within a list ("Sen. Ep. 95, 22; 24,14; de Ira, 2, 33, 4").
        if not _LIST_GAP.fullmatch(text[prev_cit_end:cit.start_offset]):
            chain_author = None
            chain_token = None
        prev_cit_end = cit.end_offset
        for ref in cit.refs:
            effective_candidates = ref.work_candidates
            inherited = False
            if effective_candidates is None:
                effective_candidates = inherited_candidates
                inherited = True
            else:
                inherited_candidates = effective_candidates
                inherited_surface = ref.work_surface
                anchor_start = ref.start_offset
                chain_dropped = False

            # build a shallow copy of ref with effective candidates for resolution
            ref_for_resolution = ref
            if inherited:
                ref_for_resolution = replace(ref, work_candidates=effective_candidates)

            if not inherited:
                near = _author_named_nearby(ref_for_resolution.work_candidates, ref.work_surface,
                                            ref.start_offset, text, chain_author, index)
                if near is not ref_for_resolution.work_candidates:
                    ref_for_resolution = replace(ref_for_resolution, work_candidates=near)
                    chain_decision = None
                else:
                    tok = _token_before(text, ref.start_offset)
                    chain_decision = _author_token_decision(
                        ref.work_candidates, ref.work_surface, tok or chain_author or chain_token,
                        not tok, index)
                    if chain_decision and chain_decision[0] == "use":
                        ref_for_resolution = replace(ref_for_resolution, work_candidates=chain_decision[1])
                    if tok and _author_slugs(tok, index):
                        chain_token = tok
                first_word = (ref.work_surface or "").split(" ")[0].rstrip(".")
                if first_word[:1].isupper() and (" " in (ref.work_surface or "").strip()
                                                 or min(c[1] for c in ref.work_candidates) < 2):
                    chain_author = first_word  # an "Author. Work." form names its author
            key_surface = ref.work_surface if not inherited else inherited_surface
            if inherited and chain_decision and chain_decision[0] == "use":
                ref_for_resolution = replace(ref_for_resolution, work_candidates=chain_decision[1])
            if chain_decision and chain_decision[0] == "use":
                forced = ref_for_resolution.work_candidates    # the name before the form has decided
            else:
                forced = _disambiguate_candidates(
                    ref_for_resolution.work_candidates, key_surface, anchor_start, text, context, index.works_by_base_id,
                    len(ref_for_resolution.start_levels or []),
                    (ref_for_resolution.start_levels or [""])[0])
            if forced is not ref_for_resolution.work_candidates:
                ref_for_resolution = replace(ref_for_resolution, work_candidates=forced)
            if not ref_for_resolution.book_list:
                ref_for_resolution = _route_speech_family(ref_for_resolution, index.works_by_base_id)

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
                    book_out = _beyond_work_rows(_finish_ref(
                        _build_out(base_out, res, book_ref, text, anchor_start, context, index.works_by_base_id), book_ref),
                        book_ref, text, context, anchor_start, index.works_by_base_id)
                    book_out = _drop_named_foreign(book_out, chain_decision)
                    chain_dropped = chain_dropped or any(_dropped_by_round2(d) for d in book_out)
                    out.extend(book_out)
                continue

            res = resolve_ref(ref_for_resolution, index.works_by_base_id)
            ref_out = _beyond_work_rows(_finish_ref(
                _build_out(base_out, res, ref_for_resolution, text, anchor_start, context, index.works_by_base_id),
                ref_for_resolution), ref_for_resolution, text, context, anchor_start, index.works_by_base_id)
            ref_out = _drop_named_foreign(ref_out, chain_decision)
            if not inherited:
                ref_out = _drop_footnote_number(ref_out, ref, text, index)
            if inherited and chain_dropped:
                # The ref that named the work was dropped (no author context,
                # impossible book number): what it carried along goes too.
                ref_out = [dict(d, resolved=False, work_id=None, part_id=None, locus_start=None,
                                reason="chain_anchor_dropped") for d in ref_out]
            elif not inherited:
                chain_dropped = any(_dropped_by_round2(d) for d in ref_out)
            out.extend(ref_out)
    return out


# A depth-1 work's own bare-number citation ("Arch. 8") is, by design,
# never touched by _apply_work_depth's over-deep guard: a single-level
# locus for a depth-1 work matches the work's own depth EXACTLY, so it
# was never "over-deep" in the first place. That leaves open the gap
# where "Arch. 1888" (a bibliographic reference to a
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


def _author_year_page_should_drop(locus_start, ref):
    """'Quint. 1989, 37' and 'Livy 1996, 12': an author-year reference with a
    page after the comma reads as a two-level locus 1989.37. No ancient work
    has a first level in the range of publication years, so a comma-joined
    first level that is a four-digit year is a bibliography entry."""
    first = locus_start.split(".")[0]
    seps = ref.start_seps or []
    return (first.isdigit() and len(first) == 4
            and _YEAR_LOCUS_MIN <= int(first) <= _YEAR_LOCUS_MAX
            and bool(seps) and seps[0] == "COMMA")


def _year_like_locus_should_drop(work_id, locus_start, ref, text):
    if work_id and locus_start and "." in locus_start:
        return _author_year_page_should_drop(locus_start, ref)
    if not work_id or not locus_start:
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



# ---------------------------------------------------------------------------
# Round 6.

# "Thucydides, 1873", "Arch. I., 1900, pp. 155-195", "Man 21: 1-17. ---. 1996":
# a citation followed by "pp." or by a publication year (with at most a page
# range between) is a bibliography entry. A single "p." is not enough: "Plat.
# Rep. VIII, p. 549 E" gives the page of the edition the ancient text is cited by. A year that is a plausible line of
# the work ("Ar. Av. 1745") is not a year.
_AFTER_PP = re.compile(r"^\s{0,3},?\s{0,3}(?:pp\.|pages\b)\s*\d")
_AFTER_YEAR = re.compile(r"^[\s.,;:\-‐-―]*(?:[A-Z]{1,4}[\s.,;:]+)?"
                         r"(?:\d{1,4}\s*[-‐-―]\s*\d{1,4}[\s.,;:\-‐-―]*)?"
                         r"(1[5-9]\d\d|20[0-3]\d)\b")
_AFTER_WINDOW = 40


# Round 8. "Bull. d. Comm. arch., i, p. 33 f": a single "p." after the locus,
# with no Stephanus letter after the page, gives the page of a modern book or
# journal ("Plat. Rep. VIII, p. 549 E" keeps its letter and stays). "Babb. char.,
# 4to, ff. 20": a format word glued to the last digit. "(Livy, Suet.) [2 verbs]":
# a number in square brackets followed by a word is a count.
_AFTER_PAGE = re.compile(r"^\s{0,3},?\s{0,3}p\.\s*\d+\s*([A-Za-z]?)")
_AFTER_FORMAT = re.compile(r"^(?:to|vo|mo)\b")
_AFTER_COUNT = re.compile(r"^\s+[a-z]+\]")


def _cited_by_one_number(work_id, works):
    """True for a work whose corpus locus is one running number and that is not
    cited by Stephanus page. Authors cited by book and chapter with the page of
    an old edition after them (Strabo X 3, 6, p. 465, Casaubon's page; Athenaeus)
    have more levels and keep their locus."""
    depth_map, inconsistent = _load_work_depth()
    return (depth_map.get(work_id) == 1 and work_id not in inconsistent
            and not (works and (works.get(work_id) or {}).get("stephanus")))


def _modern_reference_round8(work_id, locus_start, ref, text, works):
    after = text[ref.end_offset:ref.end_offset + _AFTER_WINDOW]
    m = _AFTER_PAGE.match(after)
    if m and m.group(1).lower() not in ("a", "b", "c", "d", "e") and _cited_by_one_number(work_id, works):
        return True
    if _AFTER_FORMAT.match(after) and text[ref.end_offset - 1:ref.end_offset].isdigit():
        return True
    if ref.locus_start_offset and text[ref.locus_start_offset - 1:ref.locus_start_offset] == "[" and _AFTER_COUNT.match(after):
        return True
    cfg = _load_context_rules()
    window = text[max(0, ref.start_offset - 24):ref.end_offset + 14]
    if any(r.search(window) for r in cfg["modern"]):
        return True
    limit = cfg["bare_number_limit"].get(normalize_abbr(ref.work_surface or ""))
    if (limit and limit["work"] == work_id and locus_start.isdigit() and int(locus_start) > limit["max"]):
        return True
    return False


def _modern_reference(work_id, locus_start, ref, text, works=None):
    """True when the citation is a modern bibliographic reference: a locus that
    is a publication year no line or book of the work reaches, or a locus
    followed by "pp." or by a year."""
    if not work_id or not locus_start:
        return False
    if _modern_reference_round8(work_id, locus_start, ref, text, works):
        return True
    max_line = _load_work_max_line().get(work_id)
    max_book = _load_work_max_book().get(work_id)
    if locus_start.isdigit() and len(locus_start) == 4 and _YEAR_LOCUS_MIN <= int(locus_start) <= _YEAR_LOCUS_MAX:
        value = int(locus_start)
        if (not max_line or max_line < value) and (not max_book or max_book < value):
            return True
    after = text[ref.end_offset:ref.end_offset + _AFTER_WINDOW]
    if _AFTER_PP.match(after):
        return True
    m = _AFTER_YEAR.match(after)
    if m and not (max_line and max_line >= int(m.group(1))):
        return True
    return False


def _apply_exceeds(work_id, work_surface, locus_start, works):
    """A short form that two authors share ("Phoen.", "Juv.") is read as the
    default work. A locus beyond the last line (or book) of that work cannot be
    it: the citation goes to the other work when its extent admits the locus,
    and is dropped when no other work is named. Returns (work_id, reason)."""
    cfg = _load_context_rules()["exceeds"].get(normalize_abbr(work_surface or ""))
    if not cfg or not locus_start:
        return work_id, None
    max_line, max_book = _load_work_max_line(), _load_work_max_book()
    parts = locus_start.split(".")
    if not parts[0].isdigit():
        return work_id, None

    def beyond(w):
        if len(parts) == 1:
            return bool(max_line.get(w)) and int(parts[0]) > max_line[w]
        return (bool(max_book.get(w)) and int(parts[0]) > max_book[w]) or _line_beyond_book(w, parts) is True

    for rule in cfg:
        if rule["work"] != work_id or not beyond(work_id):
            continue
        other = rule.get("instead")
        if other and other in works and not beyond(other):
            return other, None
        return None, "requires_author_context:locus_beyond_work"
    return work_id, None


_LIST_GAP = re.compile(r"[\s;,.]*(?:[dD]e\s+)?")
_AUTHOR_BEFORE = re.compile(r"\b([A-Z][a-z]{1,8})\.?,?\s+(?:[dD]e\s+|[iI]n\s+)?$")
_NEAR_AUTHOR_CHARS = 40


def _author_named_nearby(candidates, work_surface, start_offset, text, chain_author, index):
    """"Sen. Ep. 95, 22; 24,14; de Ira, 2, 33, 4": the bare title Ira names
    Lactantius in the table, but the author named right before it ("Sen. de
    Ira") or in the previous item of the same list has a work of that title
    ("Sen. Ira" is the table's form for Seneca's De ira). Looks the title up
    with that author in front and returns the work found as the only
    candidate. A form that is itself an author's abbreviation ("Quint.") is
    left alone. Returns the candidates unchanged when no author
    helps or when the form already names its author."""
    if not work_surface or not candidates or min(c[1] for c in candidates) < 2:
        return candidates
    key = normalize_abbr(work_surface)
    for c in candidates:
        authors = index.works_by_base_id.get(c[0], {}).get("author_abbreviations") or []
        if key in {normalize_abbr(a) for a in authors}:
            return candidates
    tail = text[max(0, start_offset - _NEAR_AUTHOR_CHARS):start_offset]
    m = _AUTHOR_BEFORE.search(tail)
    words = [m.group(1)] if m else []
    if chain_author:
        words.append(chain_author)
    seen = set()
    for word in words:
        if word in seen:
            continue
        seen.add(word)
        hits = index.lookup(normalize_abbr(word + " " + work_surface))
        if hits:
            best = min(h[1] for h in hits)
            ids = sorted({h[0] for h in hits if h[1] == best})
            return [(i, 0, work_surface) for i in ids]
    return candidates


# ---------------------------------------------------------------------------
# Round 8, rule 1: the author written just before a shared abbreviation decides.
#
# Order of the author rules for one reference, nearest evidence first:
#   1. _author_named_nearby (round 3): the author word plus the form is itself a
#      form in the table ("Sen. Ira"), so the table decides.
#   2. _author_token_decision (round 8): the capitalized word right before the
#      form (or the author of the item before it in a list) names an author. A
#      work of that author with the form decides, a work of that author whose
#      title begins with the form decides, and a name that belongs to no author
#      of the corpus drops the reference when the form is shared.
#   3. _disambiguate_candidates (round 3, with the round 8 "scholia" step): the
#      author named anywhere in the 300 characters before, then the defaults.
# A step that decides stops the later ones, so a name directly in front of the
# form beats an author named a sentence earlier.

_AUTHOR_LEX = {}
_TOKEN_BEFORE = re.compile(r"(?<![A-Za-z])([A-Z][A-Za-z]{1,14})\.?,?\s*\(?\s*(?:[dD]e\s+|[iI]n\s+)?$")
_SLUG_STOP = {"the", "saint", "bishop", "elder", "younger", "from", "that", "with"}
_WORD_STOP = {"part", "libri", "liber", "opera", "works", "the", "and"}
_FOREIGN_NAME = re.compile(r"[A-Z][a-z]{7,}us")     # Aristaenetus, Heraclitus: a Latinized ancient name
_NAMED_AUTHOR_WINDOW = 40


def _author_lexicon(index):
    """{key: {author slug}} for the author words of the table (author
    abbreviations, one-word author names, the words of the slug) and, per author,
    the words of each work's title and short forms."""
    lex = _AUTHOR_LEX.get(id(index))
    if lex is not None:
        return lex
    exact, works = {}, {}
    for base_id, w in index.works_by_base_id.items():
        slug, _, rest = base_id.partition(".")
        keys = {slug}
        keys.update(p for p in slug.split("_") if len(p) >= 4 and p not in _SLUG_STOP)
        for a in w.get("author_abbreviations") or []:
            k = normalize_abbr(a)
            if k and " " not in k:
                keys.add(k)
        for n in w.get("author_names") or []:
            k = normalize_abbr(n)
            if " " not in k and len(k) >= 4:
                keys.add(k)
        for k in keys:
            exact.setdefault(k, set()).add(slug)
        words = set(re.split(r"[._]", rest))
        for t in w.get("work_titles") or []:
            words.update(normalize_abbr(t).split(" "))
        for a in (w.get("abbreviations") or []) + (w.get("work_abbreviations") or []):
            words.update(normalize_abbr(a).split(" "))
        works.setdefault(slug, []).append(
            (base_id, {x for x in words if len(x) >= 3 and not x.isdigit() and x not in _WORD_STOP}))
    lex = (exact, works, sorted(exact))
    _AUTHOR_LEX[id(index)] = lex
    return lex


def _author_slugs(tok, index):
    exact, _works, keys = _author_lexicon(index)
    n = normalize_abbr(tok)
    slugs = set(exact.get(n, ()))
    if not slugs and len(n) >= 5:
        i = bisect.bisect_left(keys, n)
        while i < len(keys) and keys[i].startswith(n):
            slugs |= exact[keys[i]]
            i += 1
    return slugs


def _author_token_decision(candidates, work_surface, tok, from_chain, index):
    """Round 8, rule 1. `tok` is the word right before a form that several works
    share (or the author word of the item before it in a list). Returns
    ("use", candidates) when the author it names has a work with the form (or a
    work whose title begins with the form), ("drop", reason) when the word is the
    name of an ancient author the corpus does not hold and the form is shared,
    and None when it decides nothing."""
    if not tok or not work_surface or not candidates or min(c[1] for c in candidates) < 2:
        return None
    slugs = _author_slugs(tok, index)
    if slugs:
        mine = [c for c in candidates if c[0].split(".", 1)[0] in slugs]
        if mine:
            return "use", [(c[0], 0, work_surface) for c in mine]
        key = normalize_abbr(work_surface)
        if " " not in key and len(key) >= 3:
            _exact, works, _keys = _author_lexicon(index)
            hit = [wid for s in sorted(slugs) for wid, words in works.get(s, ())
                   if any(w.startswith(key) for w in words)]
            if len(hit) == 1:
                return "use", [(hit[0], 0, work_surface)]
        return None
    if (not from_chain and _FOREIGN_NAME.fullmatch(tok)
            and len({c[0].split(".", 1)[0] for c in candidates}) >= 2):
        return "drop", "requires_author_context:author_not_in_corpus"
    return None


def _drop_named_foreign(rows, decision):
    """The rows of a reference whose preceding word names an author the corpus
    does not hold: unresolved, with the reason."""
    if not decision or decision[0] != "drop":
        return rows
    return [dict(d, resolved=False, work_id=None, part_id=None, locus_start=None, reason=decision[1])
            for d in rows]


_FOOTNOTE_AFTER = re.compile(r"\s+[A-Z]")


def _drop_footnote_number(rows, ref, text, index):
    """Round 8. "...presented by Livy. 21 TLL, vol. 4": a whole name that carries
    no abbreviation period (Livy, Thucydides) ends its sentence with the period, so
    the one- to three-digit number after it, followed by a capital word, is a
    footnote number."""
    ws = ref.work_surface or ""
    levels = ref.start_levels or []
    if (ws.endswith(".") and normalize_abbr(ws) in index.bare_aliases and len(levels) == 1
            and levels[0].isdigit() and len(levels[0]) <= 3 and not ref.end_levels
            and _FOOTNOTE_AFTER.match(text[ref.end_offset:ref.end_offset + 3])):
        return [dict(d, resolved=False, work_id=None, part_id=None, locus_start=None,
                     reason="dropped_modern_reference") for d in rows]
    return rows


def _token_before(text, start_offset):
    m = _TOKEN_BEFORE.search(text[max(0, start_offset - _NAMED_AUTHOR_WINDOW):start_offset])
    return m.group(1) if m else None


_LEADING_NUMBER = re.compile(r"\d+")
# Editions differ by a section or a line at the end of a work ("Cic. Fat. 50"
# against a corpus that stops at 48), so a number is beyond the work only when
# it passes the corpus's last by more than this slack.
_LINE_SLACK = 2
_SECTION_SLACK_SHARE = 20      # one twentieth of the work, at least _LINE_SLACK


def _past(value, last, share=0):
    return value > last + max(_LINE_SLACK, last // share if share else 0)


def _line_beyond_book(work_id, parts):
    """Round 7, rule 2. True when the first two levels of a locus ("3.463") are a
    book and a line of a verse work whose book has fewer lines (Juvenal 3 ends
    at 322). False when they fit, None when the table says nothing (a work or
    book it does not hold, a level that is not a number)."""
    books = _load_work_book_line_max().get(work_id)
    if not books or len(parts) < 2:
        return None
    book, line = _LEADING_NUMBER.match(parts[0]), _LEADING_NUMBER.match(parts[1])
    if not book or not line:
        return None
    last = books.get(str(int(book.group())))
    if last is None:
        return None
    return _past(int(line.group()), last)


def _single_level_beyond(work_id, parts):
    """Round 7, rule 1. True when a locus of one level is a number past the last
    number of a work whose every corpus locus has one level ("Vit. 466": the Life
    of Josephus has 430 sections). False when it fits, None when the table does
    not hold the work (a work cited at several levels, one with mixed depth, or
    one whose corpus unit is longer than a section)."""
    if len(parts) != 1:
        return None
    last = _load_work_single_level_max().get(work_id)
    num = _LEADING_NUMBER.match(parts[0])
    if not last or not num:
        return None
    return _past(int(num.group()), last, _SECTION_SLACK_SHARE)


def _beyond_work(work_id, locus_start):
    """"single_level", "book_line" or None: which round 7 rule finds the locus
    beyond the end of the work (or of its book)."""
    if not work_id or not locus_start:
        return None
    parts = locus_start.split(".")
    if len(parts) == 1:
        return "single_level" if _single_level_beyond(work_id, parts) else None
    return "book_line" if _line_beyond_book(work_id, parts) else None


def _fits_work(work_id, locus_start):
    """True when the round 7 tables positively place the locus inside the work."""
    parts = locus_start.split(".")
    if len(parts) == 1:
        return _single_level_beyond(work_id, parts) is False
    return _line_beyond_book(work_id, parts) is False


def _name_key(word):
    return word.lower().replace("j", "i").replace("v", "u")


_NAMED_WINDOW = 150


def _author_named_before(work_id, ahead, works):
    """True when the text just before a citation names the work's author in full
    (or by an abbreviation of four or more letters)."""
    rec = works.get(work_id) or {}
    names = {_name_key(n.rstrip(".")) for n in (rec.get("author_names") or []) + (rec.get("author_abbreviations") or [])
             if len(n.rstrip(".")) >= 4}
    tail = _name_key(ahead[-_NAMED_WINDOW:])
    return any(re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", tail) for n in names)


def _beyond_work_rows(rows, ref, text, context, anchor_start, works):
    """Round 7, rules 1 and 2: a locus past the end of its work (or book) cannot
    be that work. The row goes to another candidate for the same short form whose
    extent holds the locus and whose author is named in the words just before
    (the existing nearest-author rule), and is dropped when there is none."""
    out = []
    for d in rows:
        kind = _beyond_work(d.get("work_id"), d.get("locus_start")) if d.get("resolved") else None
        if not kind:
            out.append(d)
            continue
        start = ref.start_offset if anchor_start is None else anchor_start
        ahead = (context or "")[-_CONTEXT_BEFORE:] + " " + text[max(0, start - _CONTEXT_BEFORE):start]
        for cand in (ref.work_candidates or []):
            wid = cand[0]
            if wid != d["work_id"] and wid in works and _fits_work(wid, d["locus_start"]) \
                    and _author_named_before(wid, ahead, works):
                out.append(dict(d, work_id=wid, part_id=None, reason="redirected_locus_beyond_work"))
                break
        else:
            out.append(dict(d, resolved=False, work_id=None, part_id=None, locus_start=None,
                            reason="dropped_locus_beyond_work:" + kind))
    return out


# Chapter-and-section numbering. Cicero's prose is cited by book, chapter and
# section ("de orat. 1, 52, 225"), while the corpus numbers it by book and
# section ("1.225"). For a work listed in work_section_numbered.json (consistent
# corpus depth n, section numbering) a printed locus with n + 1 levels drops its
# second-to-last level, the chapter.
_WORK_SECTION_NUMBERED = None


def _load_work_section_numbered():
    global _WORK_SECTION_NUMBERED
    if _WORK_SECTION_NUMBERED is None:
        try:
            with open(os.path.join(_CITATIONS_DIR, "work_section_numbered.json"), encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            raw = {}
        _WORK_SECTION_NUMBERED = set(raw.get("works") or [])
    return _WORK_SECTION_NUMBERED


def _drop_chapter_level(out_dict, ref):
    work_id = out_dict.get("work_id")
    if not out_dict.get("resolved") or not work_id or not out_dict.get("locus_start"):
        return out_dict
    if work_id not in _load_work_section_numbered():
        return out_dict
    depth_map, inconsistent = _load_work_depth()
    depth = depth_map.get(work_id)
    if not depth or work_id in inconsistent:
        return out_dict
    start = out_dict["locus_start"].split(".")
    if len(start) != depth + 1 or not all(p.isdigit() for p in start):
        return out_dict
    # Both printed levels must be Arabic numbers ("2, 89 vix" is no section),
    # and a section number runs on through the book, so it is never smaller than
    # its chapter ("Tusc. 3.26.13" has a subsection, not a section, at the end).
    last_two = (ref.start_levels or [])[-2:]
    if len(last_two) < 2 or not all(t.isdigit() for t in last_two) or int(start[-1]) < int(start[-2]):
        return out_dict
    out = dict(out_dict, locus_start=".".join(start[:-2] + start[-1:]), reason="chapter_level_dropped")
    if out.get("locus_end"):
        end = out["locus_end"].split(".")
        if len(end) == depth + 1 and all(p.isdigit() for p in end):
            out["locus_end"] = ".".join(end[:-2] + end[-1:])
    return out


def _use_parenthesized_numbering(out_dict, ref):
    """"Men. 1, 1, 26 (102)", "Haut 4, 4, 21 (v. 743)": the parenthesis holds the
    same line in the other numbering. The corpus numbers Plautus by continuous
    line and Terence by act, scene and line, so the form with as many levels as
    the work's corpus depth is the locus and the other form is dropped."""
    if not out_dict.get("resolved") or not out_dict.get("locus_start"):
        return out_dict
    paren = ref.paren_levels
    if not paren:
        return out_dict
    depth_map, inconsistent = _load_work_depth()
    work_id = out_dict["work_id"]
    depth = depth_map.get(work_id)
    if not depth or work_id in inconsistent:
        return out_dict
    if len(ref.start_levels) == depth or len(paren) != depth:
        return out_dict
    start = levels_to_locus_string(paren)
    if start is None:
        return out_dict
    out = dict(out_dict, locus_start=start, locus_end=None, reason="parenthesized_numbering_used")
    if ref.paren_end_levels:
        out["locus_end"] = levels_to_locus_string(ref.paren_end_levels)
    return out


# Plautus is cited by act, scene and line, or by one running line, and the corpus
# holds it by running line (depth 1), so "Mil. 146, 298" is two lines, since no
# act number reaches 146. A level that is not a number ("Aul. 538, I should")
# is not a line.
_MAX_ACT = 5
_SPLIT_NEXT_LINE = True  # round 8 switch (the measurement script turns it off to count the rule)
_MAX_DOTTED_RANGE = 3    # round 8: "Av. 17. 18" (lines 17 to 18), but not "Ach. 11. 24" (line 1124 split by OCR)


def _split_line_list(out_dict, ref):
    if not out_dict.get("resolved") or not out_dict.get("locus_start") or out_dict.get("locus_end"):
        return [out_dict]
    levels = ref.start_levels or []
    seps = ref.start_seps or []
    if len(levels) < 2 or not seps or any(sep != "COMMA" for sep in seps):
        return [out_dict]
    depth_map, inconsistent = _load_work_depth()
    work_id = out_dict["work_id"]
    if depth_map.get(work_id) != 1 or work_id in inconsistent:
        return [out_dict]
    if not work_id.startswith("plautus."):
        return [out_dict]  # Plautus is held by running line but cited by act, scene and line
    if len(out_dict["locus_start"].split(".")) != len(levels):
        return [out_dict]  # another rule has already changed the locus
    if not levels[0].isdigit() or int(levels[0]) <= _MAX_ACT:
        return [out_dict]
    outs = []
    for lv in levels:
        if lv.isdigit():
            outs.append(dict(out_dict, locus_start=lv, locus_end=None, reason="split_line_list"))
    return outs or [out_dict]


def _split_comma_pair(out_dict, ref):
    """Round 8. "Hdt. IV, 77, 156": three levels, all joined by commas, in a work
    whose journals cite book and chapter, and the last number is past the highest
    section the corpus holds for the work. The third number cannot be a section, so
    the locus is two chapters of one book (4.77 and 4.156)."""
    work_id = out_dict.get("work_id")
    if not out_dict.get("resolved") or not work_id or not out_dict.get("locus_start") or out_dict.get("locus_end"):
        return [out_dict]
    levels, seps = ref.start_levels or [], ref.start_seps or []
    parts = out_dict["locus_start"].split(".")
    if len(levels) != 3 or len(parts) != 3 or any(sep != "COMMA" for sep in seps) or not parts[2].isdigit():
        return [out_dict]
    depth_map, inconsistent = _load_work_depth()
    if depth_map.get(work_id) != 3 or work_id in inconsistent or _load_work_depth_journal().get(work_id) != 2:
        return [out_dict]
    if work_id in _load_work_depth_overrides():
        return [out_dict]
    last = _load_work_max_line().get(work_id)
    if not last or not _past(int(parts[2]), last):
        return [out_dict]
    return [dict(out_dict, locus_start=".".join(parts[:2]), reason="split_comma_pair"),
            dict(out_dict, locus_start=parts[0] + "." + parts[2], reason="split_comma_pair")]


def _finish_ref(out_dict, ref):
    """Everything that turns one resolved reference into its output rows
    (round 6 order: parenthesized numbering, chapter level, line lists, then the
    depth rule of rounds 3 and 4 and the Pindar book letter)."""
    out = _use_parenthesized_numbering(out_dict, ref)
    out = _drop_chapter_level(out, ref)
    outs = _split_line_list(out, ref)
    if len(outs) == 1:
        outs = _split_comma_pair(outs[0], ref)
        if len(outs) > 1:
            return _prefix_pindar_book(outs)
    rows = []
    for o in outs:
        rows.extend(_apply_work_depth(o, ref) if len(outs) == 1 else [o])
    return _prefix_pindar_book(rows)


def _build_out(base_out, res, ref, text, anchor_start=None, context="", works=None):
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

    if resolved and work_id and base_out.get("work_surface"):
        new_work, why = _apply_context_rules(
            work_id, base_out["work_surface"],
            ref.start_offset if anchor_start is None else anchor_start, text, context,
            len(ref.start_levels or []), ref.start_seps,
            text[ref.end_offset:ref.end_offset + _AFTER_BIBLE_WINDOW])
        if new_work is None:
            resolved, work_id, part_id, locus_start, reason = False, None, None, None, why
        elif new_work != work_id:
            work_id = new_work
            part_id = None
            reason = "redirected_by_author_context"

    if resolved and work_id and base_out.get("work_surface"):
        new_work, why = _apply_exceeds(work_id, base_out["work_surface"], locus_start, works or {})
        if new_work is None:
            resolved, work_id, part_id, locus_start, reason = False, None, None, None, why
        elif new_work != work_id:
            work_id = new_work
            part_id = None
            reason = "redirected_locus_beyond_work"

    if resolved and _modern_reference(work_id, locus_start, ref, text, works):
        resolved = False
        work_id = None
        part_id = None
        locus_start = None
        reason = "dropped_modern_reference"

    if resolved and _impossible_book_locus(work_id, locus_start, works):
        resolved = False
        work_id = None
        part_id = None
        locus_start = None
        reason = "dropped_missing_book_number"

    if resolved and _year_like_locus_should_drop(work_id, locus_start, ref, text):
        resolved = False
        work_id = None
        part_id = None
        locus_start = None
        reason = "dropped_year_like_locus"

    locus_end = res.locus_end
    prefix = (_load_context_rules()["locus_prefix"].get(work_id) or {}).get(normalize_abbr(base_out.get("work_surface") or ""))
    if resolved and prefix and locus_start:
        # The corpus tags Nepos by life: "Eum. 8. 2" is eum.8.2.
        locus_start = prefix + "." + locus_start
        locus_end = prefix + "." + locus_end if locus_end else locus_end

    return {
        **base_out,
        "resolved": resolved,
        "work_id": work_id,
        "part_id": part_id,
        "locus_start": locus_start,
        "locus_end": locus_end,
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
