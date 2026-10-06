#!/usr/bin/env python3
"""Quintus Curtius Rufus, Historiae Alexandri Magni: J. C. Rolfe's 1946 Loeb
translation (Harvard University Press / William Heinemann), aligned to the
corpus text books 3-10.

SOURCE OCR: the two Loeb volumes (HathiTrust rights "pd, Full view" for
mdp.39015008158415 v.1 and mdp.39015008158407 v.2), scanned by the Internet
Archive and run through its OCR (djvu text), one book per volume pair
(vol.1 = books 3-5 plus the introduction and summaries of the lost books
1-2; vol.2 = books 6-10).

LAYOUT: Latin and English pages alternate, each carrying its own running
header ("QUINTUS CURTIUS" / "QUINTUS CURTIUS RUFUS" on a Latin page,
"HISTORY OF ALEXANDER..." on an English page), a page number, and a
footnote block at the foot (critical apparatus on Latin pages, explanatory
notes on English pages, the latter keyed by a superscript letter or symbol
that OCR mangles unpredictably -- @, °, >, ¢ all turn up for the same
dagger/letter). A book opens with a "CONTENTS OF BOOK <roman>" synopsis
page (English prose, NOT the translation -- its parenthesised "(i)" "(ii)"
markers are plot-summary chapter tags, not section numbers) before the real
"BOOK <roman>" heading.

METHOD:
1. Split on running-header and bare-page-number lines into page-sized
   chunks; classify each chunk Latin/English by function-word share.
2. Within the chunks classified English, drop footnote/junk lines, rejoin
   hyphenated line-breaks, and scan for chapter starts (a roman numeral
   followed by a period at the start of a line, in sequence within the
   book) and section starts (a plain integer at the start of a line, in
   sequence within the chapter; the chapter's own first section carries no
   numeral).
3. Book 6: Curtius' real opening is lost: the "first chapter" is a modern
   reconstruction from other sources. The Loeb prints it with NO chapter
   numeral at all (the first numeral it prints, "I.", is Rolfe's chapter
   1 -- our corpus's 6.1). Whatever the scan collects before that first
   numeral is the reconstruction and is filed as the corpus's 6.1a, a
   single section. See `--book6-report` output.
4. Validate per book against the corpus's own chapter and section counts;
   a chapter whose section sequence cannot be recovered in order falls
   back to one unit for the whole chapter (printed); a book whose chapter
   count disagrees with the corpus is not written.

Usage:
    python scripts/translations/align_curtius.py \
        --vol1 <vol1.txt> --vol2 <vol2.txt> \
        --tess texts/la/curtius_rufus.historiae_alexandri_magni.tess \
        --out  la__curtius_rufus.historiae_alexandri_magni.json
"""
import argparse
import json
import os
import re
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

LATIN_FUNC = set('et in ad cum ex atque quoque enim sed non est'.split())
ENGLISH_FUNC = set('the of and to with'.split())

HEADER_RE = re.compile(
    r'^(QUINTUS CURTIUS(\s+RUFUS)?|HISTORY OF ALEXANDER\b.*|'
    r'CONTENTS OF BOOK\b.*|BOOKS?\s+[IVXLC]+[\s,.-].*)\s*$')
PAGENUM_RE = re.compile(r'^\d{1,4}\s*$')
VOLNUM_RE = re.compile(r'^VOL\.\s*[IVXLC]+\s+[A-Z]?\s*\d+\s*$', re.IGNORECASE)
BOOK_START_RE = re.compile(r'^BOOK\s+([IVXLC]+)\s*$')

ROMAN_VALS = [('XL', 40), ('L', 50), ('X', 10), ('IX', 9), ('V', 5),
              ('IV', 4), ('I', 1)]
ROMAN_BOOK = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6,
              'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10}

TARGET_BOOKS = [3, 4, 5, 6, 7, 8, 9, 10]

OCR_DIGIT = str.maketrans({'O': '0', 'o': '0', 'l': '1', 'I': '1',
                            'S': '5', 'B': '8', 'Z': '2'})

# An English page's footnote block: a lettered marker (a-f) needs a capital
# letter after it (the article "a " / "a certain " etc. is far too common a
# false positive otherwise -- checked against the actual OCR); a symbol
# marker (the OCR's mangling of a superscript dagger/letter: @, deg sign,
# cent sign, ?, *, copyright sign) does not, since footnotes often open by
# quoting a lower-cased Latin word and none of these symbols occurs at a
# true prose line's start in this corpus.
FOOTNOTE_MARK_RE = re.compile(r'^(?:[a-f]\s+[A-Z]|[@°¢?*©]\s+\S)')

# A Latin page's critical apparatus: either a known editor's surname (OCR
# sometimes renders "Mützell" as "Miitzell") or the structural shape
# "word Name; word A" (a reading, the editor who proposed it, the
# manuscript's reading, and a one-letter manuscript siglum).
EDITOR_NAMES = {'Modius', 'Hedicke', 'Vogel', 'Zumpt', 'Foss', 'Bentley',
                'Warmington', 'Lauer', 'Hussner', 'Jeep', 'Mutzell',
                'Miitzell', 'Mützell', 'Acidalius', 'Stangl'}
APPARATUS_PATTERN = re.compile(r'\b\w+\s+[A-Z][a-zA-Z]*\s*;\s*\w+\s+[A-Z]\b')
PAREN_CROSSREF_RE = re.compile(r'^\([A-Z][A-Za-z]*\.?[^()]*\)\.?,?\s*$')
SEE_REF_RE = re.compile(r'^See\s+[A-Z]')


def is_apparatus_line(s):
    words = re.findall(r"[A-Za-zü]+", s)
    if any(w in EDITOR_NAMES for w in words):
        return True
    return bool(APPARATUS_PATTERN.search(s))


def int_to_roman(n):
    """Chapters here never exceed 16 (book 4), so I/V/X suffice."""
    vals = [(10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')]
    out = ''
    for v, sym in vals:
        while n >= v:
            out += sym
            n -= v
    return out


NUMERAL_OCR_CHARS = set('IVXLCJTY1[]!|')
NUMERAL_FOLD = {'J': 'I', 'T': 'I', '1': 'I', 'L': 'I', 'Y': 'V',
                '[': 'I', ']': 'I', '!': 'I', '|': 'I'}


def canon_numeral(tok):
    """Fold common OCR confusions onto canonical roman letters: J/T/1/L/
    brackets/bars -> I (L=50 never legitimately occurs here, chapters top
    out at XVI), Y -> V. Returns None if the token has any character
    outside the roman/OCR-confusible set, so it cannot spuriously match an
    ordinary word."""
    if not tok or not (1 <= len(tok) <= 6):
        return None
    out = []
    for ch in tok.upper():
        if ch not in NUMERAL_OCR_CHARS:
            return None
        out.append(NUMERAL_FOLD.get(ch, ch))
    return ''.join(out)


def word_tokens(text):
    return re.findall(r"[A-Za-z']+", text)


def classify_chunk(lines):
    """-> ('latin'|'english'|'junk', latin_share, english_share, n_tokens)."""
    text = ' '.join(lines)
    toks = [t.lower() for t in word_tokens(text)]
    n = len(toks)
    if n < 4:
        return 'junk', 0.0, 0.0, n
    lat = sum(1 for t in toks if t in LATIN_FUNC)
    eng = sum(1 for t in toks if t in ENGLISH_FUNC)
    ls, es = lat / n, eng / n
    if ls > es:
        return 'latin', ls, es, n
    return 'english', ls, es, n


def split_pages(raw_text):
    """[(lines_in_chunk, trigger_line_or_None)] -- trigger is the header/
    page-number line that ENDED the chunk (None for the trailing chunk)."""
    lines = raw_text.split('\n')
    chunks, buf = [], []
    for line in lines:
        s = line.rstrip()
        if HEADER_RE.match(s.strip()) or PAGENUM_RE.match(s.strip()) or \
                VOLNUM_RE.match(s.strip()):
            chunks.append((buf, s.strip()))
            buf = []
            continue
        buf.append(s)
    chunks.append((buf, None))
    return chunks


def clean_english_lines(lines):
    """Drop footnote/apparatus/junk lines, return a list of cleaned lines
    (order preserved) still starting fresh at original line breaks so
    chapter/section markers remain at a line's start.

    A page's tail runs from its first footnote-marker line (English page)
    or its first critical-apparatus line (a Latin page's tail that got
    glued onto this chunk because a running header was missed) to the foot
    of the page: no main-text prose resumes after it. So once either marker
    is seen, the REST of the chunk is dropped too, not just that one line --
    otherwise a footnote's or an apparatus entry's own continuation lines
    (no marker of their own) read as ordinary prose and splice citation
    Latin into the English stream."""
    out = []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if FOOTNOTE_MARK_RE.match(s):
            break
        if is_apparatus_line(s):
            break
        if PAREN_CROSSREF_RE.match(s) or SEE_REF_RE.match(s):
            continue  # a standalone cross-reference line, not page-tail
        letters = sum(c.isalpha() for c in s)
        if letters < max(2, len(s) * 0.3):
            continue  # OCR junk line, mostly non-letters
        out.append(s)
    return out


def dehyphenate(lines):
    """Join a trailing '-' at a line's end into the next line's first word,
    while keeping each logical line as its own list entry so a marker that
    starts the FOLLOWING physical line is not swallowed into the previous
    one. Returns a new list of lines."""
    out = []
    i = 0
    while i < len(lines):
        cur = lines[i]
        while cur.endswith('-') and i + 1 < len(lines) and lines[i + 1]:
            nxt = lines[i + 1]
            m = re.match(r'^(\S+)(.*)$', nxt)
            if not m:
                break
            cur = cur[:-1] + m.group(1)
            rest = m.group(2).lstrip()
            i += 1
            if rest:
                lines[i] = rest
            else:
                lines[i] = ''
        out.append(cur)
        i += 1
    return [l for l in out if l]


CHAP_RE = re.compile(r'^([A-Za-z0-9\[\]!|]{1,6})[.,]\s*(.*)$')
SEC_RE = re.compile(r'^(\d[0-9OolI]{0,2})\s*(\S.*)$')
# A chapter break that falls inside a quoted speech is sometimes printed
# INLINE after a colon rather than at a line's start (e.g. "...as follows:
# XIV. that emensis..."), and the continuation after it is NOT capitalised
# since the quotation runs straight on. Tried only when the line-start form
# fails, and only an exact next-chapter match is accepted (no resync, and
# no capital-letter check: both would be false security here).
INLINE_CHAP_RE = re.compile(r'^(.*[.:,]\s*)([A-Za-z0-9\[\]!|]{1,6})[.,]\s*(\S.*)$')


def parse_book_english(lines, book, report):
    """lines: cleaned, de-hyphenated English lines for one book's span.
    -> ({chapter_label: [line, line, ...]}, pre_chapter_lines, skipped_chapters).

    This finds only CHAPTER boundaries (a roman numeral, in sequence, at a
    line's start or inline after a quotation's colon/comma) and buckets the
    book's lines by chapter, unmodified and in order. Section markers are
    NOT resolved here -- a single garbled or footnote-borrowed digit must
    not be allowed to derail every later marker in the chapter the way a
    strict running count would, so that is done as a separate pass (see
    `extract_sections`) that looks at a whole chapter's lines at once and
    picks the longest increasing run of candidates.
    """
    chapters = OrderedDict()   # label -> [line, line, ...]
    pre_chapter = []
    cur_chapter = None
    expect_chapter = 1

    def bucket(label):
        chapters.setdefault(label, [])
        return chapters[label]

    RESYNC_WINDOW = 3
    skipped_chapters = []
    for raw_line in lines:
        # A stray leading punctuation mark (a lone comma, quote, dash) is a
        # common OCR artifact ahead of a marginal section number or a
        # chapter numeral ("‚ 2 Lydia against Croesus"); drop it before
        # testing for a marker, but keep the original for plain text.
        line = re.sub(r'^[,;:\'"‘’“”\-\s]+', '', raw_line)
        if not line:
            line = raw_line
        m = CHAP_RE.match(line)
        if m:
            numeral, rest = m.group(1), m.group(2)
            rest_sentence_start = re.sub(r'^[^A-Za-z]+', '', rest)
            canon = canon_numeral(numeral)
            matched_val = None
            if canon and rest_sentence_start[:1].isupper() \
                    and len(rest_sentence_start) > 1:
                for cand in range(expect_chapter, expect_chapter + RESYNC_WINDOW + 1):
                    if canon == int_to_roman(cand):
                        matched_val = cand
                        break
            if matched_val is not None:
                if matched_val > expect_chapter:
                    skipped_chapters.extend(range(expect_chapter, matched_val))
                cur_chapter = matched_val
                expect_chapter = matched_val + 1
                buf_target = bucket(cur_chapter)
                if rest:
                    buf_target.append(rest)
                continue
        im = INLINE_CHAP_RE.match(line)
        if im and canon_numeral(im.group(2)) == int_to_roman(expect_chapter):
            prefix, rest = im.group(1), im.group(3)
            if cur_chapter is not None:
                bucket(cur_chapter).append(prefix)
            else:
                pre_chapter.append(prefix)
            cur_chapter = expect_chapter
            expect_chapter += 1
            bucket(cur_chapter).append(rest)
            continue
        # continuation line
        if cur_chapter is not None:
            bucket(cur_chapter).append(line)
        else:
            pre_chapter.append(line)
    return chapters, pre_chapter, skipped_chapters


def lis_candidates(chapter_lines, n_max):
    """[(line_index, value, rest_text)] for every line that opens with an
    integer (OCR-digit-tolerant, glued or spaced) whose value could be a
    real section number (2..n_max) -- not yet filtered for being correct,
    just plausible. Noise (footnote numbers, cross-reference numbers) is
    expected among these and is rejected by the longest-increasing pass,
    not here."""
    out = []
    for idx, line in enumerate(chapter_lines):
        m = SEC_RE.match(line)
        if not m:
            continue
        digits = m.group(1).translate(OCR_DIGIT)
        if not digits.isdigit():
            continue
        n = int(digits)
        if 2 <= n <= n_max:
            out.append((idx, n, m.group(2)))
    return out


def longest_increasing(candidates):
    """The longest strictly-increasing-by-value subsequence of candidates
    (candidates are already in line order), standard patience-sorting
    O(n log n) LIS with back-pointers for reconstruction. candidates:
    [(idx, value, rest)]."""
    if not candidates:
        return []
    import bisect
    tails_val, tails_idx, prev = [], [], [-1] * len(candidates)
    for i, (_, v, _) in enumerate(candidates):
        pos = bisect.bisect_left(tails_val, v)
        if pos == len(tails_val):
            tails_val.append(v)
            tails_idx.append(i)
        else:
            tails_val[pos] = v
            tails_idx[pos] = i
        prev[i] = tails_idx[pos - 1] if pos > 0 else -1
    seq, k = [], tails_idx[-1]
    while k != -1:
        seq.append(candidates[k])
        k = prev[k]
    seq.reverse()
    return seq


def build_section_units(chapter_lines, chosen):
    """-> [(anchor_section, text), ...] in ascending anchor order, anchor 1
    always first. `chosen`: the accepted [(idx, value, rest)] markers.

    Joined with newlines, not spaces: the text-cleanup pass (rule 4, cutting
    a unit's trailing garbage LINE) needs the original OCR line boundaries,
    which it collapses to spaces itself once it is done with them."""
    if not chosen:
        return [(1, '\n'.join(l for l in chapter_lines if l).strip())]
    first_idx = chosen[0][0]
    units = [(1, '\n'.join(l for l in chapter_lines[:first_idx] if l).strip())]
    for i, (idx, v, rest) in enumerate(chosen):
        end_idx = chosen[i + 1][0] if i + 1 < len(chosen) else len(chapter_lines)
        parts = [rest] if rest else []
        parts.extend(l for l in chapter_lines[idx + 1:end_idx] if l)
        units.append((v, '\n'.join(parts).strip()))
    return units


def sections_from_units(units, n_max):
    """Map every corpus section 1..n_max to (mode, text): 'section' when
    that section is itself a chosen anchor, 'section-merged' when its own
    marker was never found and it inherits the preceding anchor's unit."""
    import bisect
    anchors = [a for a, _ in units]
    out = {}
    for s in range(1, n_max + 1):
        j = bisect.bisect_right(anchors, s) - 1
        j = max(j, 0)
        mode = 'section' if anchors[j] == s else 'section-merged'
        out[s] = (mode, units[j][1])
    return out


# ---------------------------------------------------------------------------
# Third pass: clean residual OCR noise OUT OF UNIT TEXT ONLY. None of this
# touches which ref maps to which unit -- it runs after ref_to_unit and
# unit_sources are already final, mutating units[i] in place, so the
# mapping is unaffected by construction.
# ---------------------------------------------------------------------------

HEADER_FRAGMENT_RE = re.compile(
    r'\bHISTORY\s+OF\s+ALEXANDER(\s+THE)?(\s+GREAT)?(\s+OF\s+MACEDON)?\b'
    r'|\bQUINTUS\s+CURTIUS(\s+RUFUS)?\b'
    r'|\bGREAT\s+OF\s+MACEDON\b'
    r'|\bALEXANDER\s+THE\s+GREAT\b'
    r'|\bBOOK\s+[IVX]{1,6}\b',
    re.IGNORECASE)


def strip_header_fragments(text):
    new_text, n = HEADER_FRAGMENT_RE.subn(' ', text)
    return new_text, (1 if n else 0)


# "@ 383 2.0." etc: a footnote-style lead symbol followed by one to three
# short digit/dot/letter tokens, appearing right after the chapter's
# opening words (within the first ~80 characters of the unit) -- a
# marginal date or cross-reference caught mid-sentence, not a real section
# number (those are handled by strip_section_numbers below).
MARGINALIA_RE = re.compile(
    r'[@°¢©®*]\s*(?:[0-9][0-9.]{0,3}|[A-Za-z]\.){1,3}(?:\s+(?:[0-9][0-9.]{0,3}|[A-Za-z]\.)){0,2}\s*'
    r'(?=[a-z])')


def strip_marginalia(text):
    head, rest = text[:80], text[80:]
    new_head, n = MARGINALIA_RE.subn(' ', head)
    return new_head + rest, (1 if n else 0)


# A marginal section number sitting between a sentence end (or a footnote
# mark) and the next capitalised word ("Celaenae.(R) 2 Through"), between
# an ordinary word and a capitalised one ("songs of the 3 Greeks" -- no
# punctuation precedes it at all, just a line-wrap), or glued straight onto
# the next lower-case word ("4and"). Only the digit itself is matched (both
# sides are zero-width lookaround), so surrounding whitespace -- including
# a real newline -- is left untouched; that matters because this runs
# AFTER the trailing-garbage cut (rule 4), which needs those line breaks
# intact to tell a genuine footnote block from ordinary prose. Only
# removed when its value is a plausible section number (1..n_max) for the
# unit's own chapter.
SECTION_NUM_RE = re.compile(r'(?<=\s)(\d{1,2})(?=\s+[A-Z]|[a-z])')


def strip_section_numbers(text, n_max):
    changed = [False]

    def repl(m):
        val = int(m.group(1))
        if n_max and 1 <= val <= n_max:
            changed[0] = True
            return ''
        return m.group(0)

    new_text = SECTION_NUM_RE.sub(repl, text)
    return new_text, (1 if changed[0] else 0)


FOOTNOTE_SYMBOL_RE = re.compile(r'[@°¢©®*]')


def strip_footnote_symbols(text):
    new_text, n = FOOTNOTE_SYMBOL_RE.subn(' ', text)
    return new_text, (1 if n else 0)


def rejoin_hyphens(text):
    return re.sub(r'(\w)-\s+(\w)', r'\1\2', text)


def is_good_token(tok):
    core = re.sub(r"^[^A-Za-z']+|[^A-Za-z']+$", '', tok)
    return len(core) >= 2 and core.replace("'", '').isalpha()


MAX_TRAILING_WINDOW = 8


def _worst_failing_window(lines):
    """The largest k (1..MAX_TRAILING_WINDOW, capped at len(lines)-1 so at
    least one line always survives) such that the last k lines COMBINED
    score under 60% good tokens, or 0 if none do. A short garbage footnote
    is often two or three OCR lines (a numbered citation, then a line of
    scanner noise) where the LAST line alone can look deceptively wordy
    (real letters, just not real words) while the combined block is
    plainly not prose -- so the window grows until it stops finding a
    failure, not just a single line at a time."""
    worst = 0
    limit = min(len(lines) - 1, MAX_TRAILING_WINDOW)
    for k in range(1, limit + 1):
        toks = ' '.join(lines[-k:]).split()
        if not toks:
            continue
        good = sum(1 for t in toks if is_good_token(t))
        if good / len(toks) < 0.6:
            worst = k
    return worst


def strip_trailing_garbage(text):
    """Repeatedly drop the unit's trailing OCR line(s) while some trailing
    window of them scores under 60% good tokens (see `_worst_failing_window`).
    Never reduces a unit to nothing: always leaves at least one line."""
    lines = [l for l in text.strip().split('\n') if l.strip()]
    n_cut = 0
    while True:
        k = _worst_failing_window(lines)
        if not k:
            break
        del lines[-k:]
        n_cut += 1
    return '\n'.join(lines), (1 if n_cut else 0)


def ends_in_garbage(text):
    lines = [l for l in text.strip().split('\n') if l.strip()]
    return bool(_worst_failing_window(lines))


def clean_unit_text(text, source_idx, n_max, counts):
    orig = text
    text, c1 = strip_header_fragments(text)
    counts['header'] += c1
    text, c3b = strip_marginalia(text)
    counts['marginalia'] += c3b
    # Trailing-garbage removal runs BEFORE the section-number strip: a
    # footnote block's own digits (its number, a page or line citation)
    # are exactly what makes that block fail the good-token ratio test, so
    # stripping them first would make leftover scanner noise look more
    # like prose than it is and let it survive.
    text, c4 = strip_trailing_garbage(text)
    counts['trailing'] += c4
    c2 = 0
    if source_idx in (1, 2):  # chapter-level and section-merged units only
        text, c2 = strip_section_numbers(text, n_max)
    counts['secnum'] += c2
    text, c3 = strip_footnote_symbols(text)
    counts['footnote'] += c3
    text = rejoin_hyphens(text)
    # Collapse ALL whitespace runs (including the lone newlines still
    # separating lines at this point) down to single spaces.
    text = re.sub(r'\s+', ' ', text).strip()
    # Compared against the ORIGINAL with its own whitespace likewise
    # collapsed, so a unit that is only rejoined across the newlines this
    # pass's own text construction introduced does not count as "changed"
    # -- only a unit an actual rule above touched does.
    orig_collapsed = re.sub(r'\s+', ' ', orig).strip()
    if text != orig_collapsed:
        counts['changed'] += 1
    return text


def process_volume(path, vol_label, report):
    raw = open(path, encoding='utf-8', errors='replace').read()
    page_chunks = split_pages(raw)

    counts = {'latin': 0, 'english': 0, 'junk': 0}
    boundary_pages = []
    classified = []  # (kind, lines, trigger)
    for lines, trigger in page_chunks:
        kind, ls, es, n = classify_chunk(lines)
        counts[kind] += 1
        classified.append((kind, lines, trigger))
        if n >= 4 and abs(ls - es) < 0.01:
            boundary_pages.append((trigger, kind, round(ls, 3), round(es, 3), n))

    report.append(f'{vol_label}: page chunks latin={counts["latin"]} '
                   f'english={counts["english"]} junk={counts["junk"]}')
    if boundary_pages:
        report.append(f'{vol_label}: {len(boundary_pages)} boundary pages '
                       f'(close latin/english call):')
        for trig, kind, ls, es, n in boundary_pages[:15]:
            report.append(f'    trigger={trig!r} -> {kind} '
                           f'(latin_share={ls}, english_share={es}, n={n})')

    # Locate real 'BOOK <roman>' headings: the body line (not a header
    # delimiter) "BOOK III" etc. These sit INSIDE a chunk's lines (they are
    # ordinary content, not one of our split delimiters), so scan the
    # (still raw, uncleaned) lines of every chunk for them, remembering
    # which chunk index each falls in. For each target roman numeral, the
    # LAST occurrence in the volume is the real book-opening heading (an
    # earlier one, if any, is the CONTENTS synopsis page's own mangled or
    # clean repeat of the heading).
    occurrences = {}  # book_int -> list of (chunk_idx, line_idx_within_chunk)
    for ci, (kind, lines, trigger) in enumerate(classified):
        for li, line in enumerate(lines):
            m = BOOK_START_RE.match(line.strip())
            if m:
                b = ROMAN_BOOK.get(m.group(1))
                if b:
                    occurrences.setdefault(b, []).append(ci)

    book_starts = {}  # book -> chunk index where its real text begins
    for b, idxs in occurrences.items():
        book_starts[b] = max(idxs)

    present_books = sorted(b for b in book_starts if b in TARGET_BOOKS)
    report.append(f'{vol_label}: books found = {present_books} '
                   f'(chunk indices {[book_starts[b] for b in present_books]})')

    # Each book's "CONTENTS OF BOOK <roman>" synopsis page sits right
    # before that book's real heading -- i.e. at the numeric TAIL of the
    # PREVIOUS book's chunk range -- and is genuine English prose (a plot
    # summary), so it passes the language classifier and would otherwise
    # be spliced onto the previous book's last chapter. Record where each
    # book's synopsis starts (the chunk right after its own "CONTENTS OF
    # BOOK" trigger) so it can be excluded from whichever span it would
    # numerically fall into.
    contents_idx = {}  # book -> chunk index where that book's synopsis begins
    back_matter_idx = None  # chunk index where a GENERAL INDEX etc. begins
    for ci, (kind, lines, trigger) in enumerate(classified):
        if trigger:
            m = re.match(r'CONTENTS OF BOOK\s+([IVXLC]+)', trigger.strip(), re.I)
            if m:
                b = ROMAN_BOOK.get(m.group(1).upper())
                if b:
                    contents_idx[b] = ci + 1
        if back_matter_idx is None:
            # A stray single-character OCR artifact ("|", a pipe) sometimes
            # precedes the heading as its own "line", so check the first
            # few non-blank lines, not only the very first.
            lead = [l.strip() for l in lines if l.strip()][:3]
            if any(re.match(r'^GENERAL INDEX\s*$', l, re.I) for l in lead):
                back_matter_idx = ci

    # Build, for each present book, the ordered list of ENGLISH-classified
    # chunks between its start chunk and the next book's start chunk (or
    # end of file), trimmed before the next book's own CONTENTS synopsis.
    boundaries = sorted(book_starts[b] for b in present_books)
    book_lines = {}
    for i, b in enumerate(present_books):
        start = book_starts[b]
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(classified)
        if i + 1 < len(present_books):
            nxt_b = present_books[i + 1]
            if nxt_b in contents_idx and start < contents_idx[nxt_b] < end:
                end = contents_idx[nxt_b]
        if back_matter_idx is not None and start < back_matter_idx < end:
            end = back_matter_idx
        lines_for_book = []
        for ci in range(start, end):
            kind, lines, trigger = classified[ci]
            if kind != 'english':
                continue
            cleaned = clean_english_lines(lines)
            cleaned = dehyphenate(cleaned)
            lines_for_book.extend(cleaned)
        book_lines[b] = lines_for_book
    return book_lines


def load_corpus(tess_path):
    refs = []          # [(ref, book, chap_label, sec, latin)]
    latin_by_ref = {}
    corpus_struct = {}  # book -> {chap_label: set(sec)}
    for line in open(tess_path, encoding='utf-8', errors='replace'):
        m = re.match(r'^<([^>]+)>\s*(.*)$', line)
        if not m:
            continue
        ref, latin = m.group(1).strip(), m.group(2).strip()
        mm = re.match(r'curt\. hist\. (\d+)\.([0-9a-z]+)\.(\d+)$', ref)
        if not mm:
            continue
        book, chap_raw, sec = int(mm.group(1)), mm.group(2), int(mm.group(3))
        chap_label = chap_raw if not chap_raw.isdigit() else int(chap_raw)
        refs.append((ref, book, chap_label, sec))
        latin_by_ref[ref] = latin
        corpus_struct.setdefault(book, {}).setdefault(chap_label, set()).add(sec)
    return refs, latin_by_ref, corpus_struct


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--vol1', required=True)
    ap.add_argument('--vol2', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    report = []
    book_lines = {}
    book_lines.update(process_volume(args.vol1, 'vol1', report))
    book_lines.update(process_volume(args.vol2, 'vol2', report))

    refs, latin_by_ref, corpus_struct = load_corpus(args.tess)
    report.append(f'corpus refs total: {len(refs)}')

    all_units = {}       # (book, chap_label) -> {sec: (mode, text)}
    chapter_fallback = {}  # (book, chap_label) -> merged text (chapter mode)
    book_chapter_counts = {}
    fallback_list = []
    skipped_books = []
    chapters_with_no_text = []
    marker_stats = []   # (book, chap_label, n_max, found, expected, pct)

    for book in TARGET_BOOKS:
        lines = book_lines.get(book, [])
        chapters, pre_chapter, skipped_in_book = parse_book_english(
            lines, book, report)
        for c in skipped_in_book:
            chapters_with_no_text.append((book, c))

        corpus_chaps = corpus_struct.get(book, {})

        # Re-label book 6's pre-chapter-I content as the reconstructed
        # chapter '1a' (a single corpus section -- always "section" mode,
        # never put through the marker-recovery pass below); chapter 1
        # stays as corpus chapter 1.
        labelled = OrderedDict()
        if book == 6:
            text = '\n'.join(l for l in pre_chapter if l).strip()
            if text:
                labelled['1a'] = ('section', {1: ('section', text)})
            else:
                report.append('BOOK 6: no reconstructed-opening text found '
                               'before the first numbered chapter (Loeb "I."); '
                               '6.1a will be missing.')
        else:
            leftover = ' '.join(l for l in pre_chapter if l).strip()
            if len(leftover.split()) > 30:
                report.append(f'BOOK {book}: {len(leftover.split())} words '
                               f'found before chapter I (discarded, title '
                               f'material expected): {leftover[:150]!r}')

        for lbl, chap_lines in chapters.items():
            corpus_secs = corpus_chaps.get(lbl, set())
            n_max = max(corpus_secs) if corpus_secs else 0
            candidates = lis_candidates(chap_lines, n_max)
            chosen = longest_increasing(candidates)
            found = len(chosen)
            expected_markers = max(0, n_max - 1)
            pct = (found / expected_markers * 100) if expected_markers else 100.0
            marker_stats.append((book, lbl, n_max, found, expected_markers, pct))
            if expected_markers == 0 or pct >= 70.0:
                unit_list = build_section_units(chap_lines, chosen)
                labelled[lbl] = ('section', sections_from_units(unit_list, n_max))
            else:
                merged = '\n'.join(l for l in chap_lines if l).strip()
                labelled[lbl] = ('chapter', merged)
                fallback_list.append((book, lbl, found, expected_markers, pct))

        parsed_chap_count = len(labelled)
        corpus_chap_count = len(corpus_chaps)
        book_chapter_counts[book] = (parsed_chap_count, corpus_chap_count)
        if parsed_chap_count != corpus_chap_count:
            skipped_books.append((book, parsed_chap_count, corpus_chap_count,
                                   sorted(map(str, labelled.keys())),
                                   sorted(map(str, corpus_chaps.keys()))))
            continue

        for chap_label, (mode, payload) in labelled.items():
            if mode == 'section':
                all_units[(book, chap_label)] = payload
            else:
                chapter_fallback[(book, chap_label)] = payload

    report.append('')
    report.append('per-chapter section-marker recovery (expected sections, '
                   'markers found/possible, percent):')
    for book, lbl, n_max, found, expected_markers, pct in marker_stats:
        report.append(f'  book {book} chapter {lbl}: expected sections '
                       f'{n_max}, markers found {found}/{expected_markers} '
                       f'({pct:.0f}%)')

    report.append('')
    report.append('per-book chapter counts (parsed vs corpus):')
    for book in TARGET_BOOKS:
        p, c = book_chapter_counts.get(book, (0, 0))
        report.append(f'  book {book}: parsed={p} corpus={c}'
                       + ('  SKIPPED' if (book, *book_chapter_counts.get(book, (0, 0))) in
                          [(b, p2, c2) for b, p2, c2, *_ in skipped_books] else ''))
    if skipped_books:
        report.append('SKIPPED books (chapter count disagreement):')
        for book, p, c, got, want in skipped_books:
            report.append(f'  book {book}: parsed {p} chapters {got} vs '
                           f'corpus {c} chapters {want}')

    report.append('')
    report.append(f'chapters falling back to one unit per chapter '
                   f'(markers found below 70%): {len(fallback_list)}')
    for book, chap, found, expected_markers, pct in fallback_list:
        report.append(f'  book {book} chapter {chap}: markers found '
                       f'{found}/{expected_markers} ({pct:.0f}%)')

    # ---- build units / ref_to_unit -------------------------------------
    # source index 0 = section (exact marker found), 1 = chapter (whole-
    # chapter fallback), 2 = section-merged (marker missing, inherited the
    # preceding found section's text).
    units, ref_to_unit, unit_sources = [], {}, []
    unit_index = {}
    unit_nmax = []  # parallel to units: the originating chapter's corpus
                     # section count, N -- not part of the written schema,
                     # used only to bound the text-cleanup pass below.

    def get_unit(text, source_idx, n_max):
        # Keyed by (text, source_idx), not text alone: a section-merged
        # ref shares its anchor section's exact text, but must still record
        # its own "section-merged" mode rather than silently inheriting
        # the anchor's "section" mode through text-only deduplication.
        key = (text, source_idx)
        if key not in unit_index:
            unit_index[key] = len(units)
            units.append(text)
            unit_sources.append(source_idx)
            unit_nmax.append(n_max)
        return unit_index[key]

    n_section_units = n_merged_units = n_chapter_units = 0
    for ref, book, chap_label, sec in refs:
        if book not in TARGET_BOOKS:
            continue
        key = (book, chap_label)
        corpus_secs_here = corpus_struct.get(book, {}).get(chap_label, set())
        n_max_here = max(corpus_secs_here) if corpus_secs_here else 0
        if key in all_units and sec in all_units[key]:
            sec_mode, text = all_units[key][sec]
            if text:
                src_idx = 0 if sec_mode == 'section' else 2
                ref_to_unit[ref] = get_unit(text, src_idx, n_max_here)
                if sec_mode == 'section':
                    n_section_units += 1
                else:
                    n_merged_units += 1
            continue
        if key in chapter_fallback:
            text = chapter_fallback[key]
            if text:
                ref_to_unit[ref] = get_unit(text, 1, n_max_here)
                n_chapter_units += 1

    coverage = len(ref_to_unit) / len(refs) if refs else 0
    n_section_level = n_section_units + n_merged_units
    report.append('')
    report.append(f'units from exact section markers: {n_section_units} refs; '
                   f'section-merged (marker missing, inherited): '
                   f'{n_merged_units} refs; chapter-level fallback: '
                   f'{n_chapter_units} refs; {len(units)} distinct units stored')
    report.append(f'section-level total (section + section-merged): '
                   f'{n_section_level}/{len(refs)} '
                   f'({n_section_level / len(refs):.4f})')
    report.append(f'coverage: {coverage:.4f} ({len(ref_to_unit)}/{len(refs)})')

    # ---- third pass: clean residual OCR noise out of unit TEXT only ------
    # ref_to_unit and unit_sources are already final above and are not
    # touched again here; only units[i] strings are rewritten in place.
    clean_counts = {'header': 0, 'marginalia': 0, 'secnum': 0,
                     'footnote': 0, 'trailing': 0, 'changed': 0}
    for i in range(len(units)):
        units[i] = clean_unit_text(units[i], unit_sources[i], unit_nmax[i],
                                    clean_counts)

    n_header_frag_left = sum(1 for u in units if HEADER_FRAGMENT_RE.search(u))
    n_garbage_end_left = sum(1 for u in units if ends_in_garbage(u))

    report.append('')
    report.append('cleanup pass (units changed per rule, of '
                   f'{len(units)} total units):')
    report.append(f'  rule 1 (running headers removed): {clean_counts["header"]}')
    report.append(f'  rule 2 (marginal section numbers removed, chapter/'
                   f'merged units only): {clean_counts["secnum"]}')
    report.append(f'  rule 3 (footnote symbols removed): '
                   f'{clean_counts["footnote"]}')
    report.append(f'  rule 3 (marginalia near chapter opening removed): '
                   f'{clean_counts["marginalia"]}')
    report.append(f'  rule 4 (trailing garbage cut): {clean_counts["trailing"]}')
    report.append(f'  units with any change: {clean_counts["changed"]}')
    report.append(f'units still containing a running-head fragment: '
                   f'{n_header_frag_left} (must be 0)')
    report.append(f'units still ending in a garbage line (rule 4 test): '
                   f'{n_garbage_end_left} (must be 0)')

    # ---- name check (300 sampled units / ref pairs) ---------------------
    pairs = [(latin_by_ref[ref], units[ref_to_unit[ref]])
             for ref, book, chap_label, sec in refs if ref in ref_to_unit]
    hit, n_tested = V.score(pairs, 'la', sample=300)
    report.append(f'name check: hit_rate={hit} n={n_tested} '
                   f'(of {len(pairs)} translated-ref pairs available)')

    # ---- Latin-leakage check (unambiguous words only: "in", "non" etc are
    # also ordinary English and swamp the count in a long unit) -----------
    UNAMBIGUOUS_LATIN = set('atque quoque enim autem igitur etiam tamen '
                             'neque quidem inquit'.split())

    def unambiguous_latin_count(text):
        toks = [t.lower() for t in word_tokens(text)]
        return sum(1 for t in toks if t in UNAMBIGUOUS_LATIN)

    leaking = sum(1 for u in units if unambiguous_latin_count(u) >= 2)
    leakage_share = leaking / len(units) if units else 0
    report.append(f'Latin leakage (unambiguous words, >=2 per unit): '
                   f'{leaking}/{len(units)} units ({leakage_share:.4%})')

    # ---- footnote/apparatus-contamination check --------------------------
    FOOTNOTE_SIGNS_RE = re.compile(
        r'\(Arr\.|\(Curt\.|\(Diod\.|See Cicero|' +
        '|'.join(re.escape(n) for n in EDITOR_NAMES))
    contaminated = sum(1 for u in units if FOOTNOTE_SIGNS_RE.search(u))
    contaminated_share = contaminated / len(units) if units else 0
    report.append(f'footnote/apparatus contamination: '
                   f'{contaminated}/{len(units)} units '
                   f'({contaminated_share:.4%}) contain "(Arr.", "(Curt.", '
                   f'"(Diod.", "See Cicero", or an editor\'s name')

    # ---- requested passages ----------------------------------------------
    report.append('')
    report.append('requested passages (Latin / English):')
    wanted = ['3.1.1', '3.1.2', '4.1.1', '6.1a.1', '8.14.46', '10.10.20']
    for suffix in wanted:
        ref = f'curt. hist. {suffix}'
        lat = latin_by_ref.get(ref, '<ref not in corpus>')
        if ref in ref_to_unit:
            eng = units[ref_to_unit[ref]]
        else:
            eng = '<NOT TRANSLATED>'
        report.append(f'  {ref}')
        report.append(f'    LA: {lat}')
        report.append(f'    EN: {eng[:2000]}')

    # ---- write -------------------------------------------------------------
    sources = [
        {
            'translator': 'J. C. Rolfe',
            'year': 1946,
            'title': 'Quintus Curtius, History of Alexander, 2 vols '
                     '(Loeb Classical Library)',
            'publisher': 'Harvard University Press / William Heinemann',
            'mode': 'section',
            'ref_composition': ['book', 'chapter', 'section'],
            'source_url': 'https://archive.org/details/'
                          'quintus.-curtius.-rufus.-history.of.-alexander.'
                          '-loeb.-one-vol-version_202511',
            'rights_basis': 'HathiTrust rights pd (Full view) for '
                            'mdp.39015008158415 and mdp.39015008158407',
            'short_attribution': 'J. C. Rolfe (1946)',
        },
        {
            'translator': 'J. C. Rolfe',
            'year': 1946,
            'title': 'Quintus Curtius, History of Alexander, 2 vols '
                     '(Loeb Classical Library)',
            'publisher': 'Harvard University Press / William Heinemann',
            'mode': 'chapter',
            'ref_composition': ['book', 'chapter'],
            'source_url': 'https://archive.org/details/'
                          'quintus.-curtius.-rufus.-history.of.-alexander.'
                          '-loeb.-one-vol-version_202511',
            'rights_basis': 'HathiTrust rights pd (Full view) for '
                            'mdp.39015008158415 and mdp.39015008158407',
            'short_attribution': 'J. C. Rolfe (1946)',
        },
        {
            'translator': 'J. C. Rolfe',
            'year': 1946,
            'title': 'Quintus Curtius, History of Alexander, 2 vols '
                     '(Loeb Classical Library)',
            'publisher': 'Harvard University Press / William Heinemann',
            'mode': 'section-merged',
            'ref_composition': ['book', 'chapter', 'section'],
            'source_url': 'https://archive.org/details/'
                          'quintus.-curtius.-rufus.-history.of.-alexander.'
                          '-loeb.-one-vol-version_202511',
            'rights_basis': 'HathiTrust rights pd (Full view) for '
                            'mdp.39015008158415 and mdp.39015008158407',
            'short_attribution': 'J. C. Rolfe (1946)',
            'note': 'This section\'s own marker could not be found in the '
                    'OCR; it shares the Loeb English of the nearest '
                    'preceding section whose marker WAS found.',
        },
    ]
    out = {
        'tess_work': 'la/curtius_rufus.historiae_alexandri_magni',
        'language': 'la',
        'n_tess_refs': len(refs),
        'n_translated': len(ref_to_unit),
        'coverage': round(coverage, 4),
        'mean_source_lines_per_translation_unit':
            round(len(ref_to_unit) / max(1, len(units)), 1),
        'alignment_confidence': 'high' if (hit or 0) >= 0.70 else 'medium',
        'name_check_hit_rate': hit,
        'name_check_n': n_tested,
        'sources': sources,
        'unit_sources': unit_sources,
        'license': 'Public domain in the United States (HathiTrust rights '
                   'determination for the 1946 Loeb volumes).',
        'attribution': 'J. C. Rolfe (1946)',
        'n_units_stored': len(units),
        'units': units,
        'ref_to_unit': ref_to_unit,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False)
    report.append('')
    report.append(f'wrote {args.out}')

    print('\n'.join(report))


if __name__ == '__main__':
    main()
