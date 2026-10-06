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

FOOTNOTE_LEAD = set('¢@°*©>§†‡¶#~^%­•·«»')
OCR_DIGIT = str.maketrans({'O': '0', 'o': '0', 'l': '1', 'I': '1',
                            'S': '5', 'B': '8', 'Z': '2'})


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
    """Drop footnote/junk lines, de-hyphenate, return a list of cleaned
    lines (order preserved) still starting fresh at original line breaks
    so chapter/section markers remain at a line's start.

    A page's footnote block runs from its first marker line (a stray
    symbol -- @, degree sign, etc, the OCR's rendering of a superscript
    letter) to the foot of the page: no main-text prose resumes after it on
    the same page. So once that marker is seen, the REST of the chunk is
    dropped too, not just that one line -- otherwise a footnote's own
    continuation lines (no leading symbol of their own) read as ordinary
    prose and splice citation Latin into the English stream."""
    out = []
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if s[0] in FOOTNOTE_LEAD:
            continue
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
    -> {chapter_label: {section_int: text}} plus pre-chapter text (book 6).
    chapter_label is an int, except book 6's reconstructed opening which
    the caller files as '1a'.
    """
    chapters = OrderedDict()   # label -> OrderedDict(section -> [text parts])
    pre_chapter = []
    cur_chapter = None
    cur_section = None
    expect_chapter = 1

    def cell(label, sec):
        chapters.setdefault(label, OrderedDict())
        chapters[label].setdefault(sec, [])
        return chapters[label][sec]

    RESYNC_WINDOW = 3
    skipped_chapters = []
    buf_target = None  # list currently receiving text
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
                cur_section = 1
                expect_chapter = matched_val + 1
                buf_target = cell(cur_chapter, cur_section)
                if rest:
                    buf_target.append(rest)
                continue
        m = SEC_RE.match(line)
        if m and cur_chapter is not None:
            digits = m.group(1).translate(OCR_DIGIT)
            if digits.isdigit():
                n = int(digits)
                if n == cur_section + 1:
                    cur_section = n
                    buf_target = cell(cur_chapter, cur_section)
                    buf_target.append(m.group(2))
                    continue
        im = INLINE_CHAP_RE.match(line)
        if im and canon_numeral(im.group(2)) == int_to_roman(expect_chapter):
            prefix, rest = im.group(1), im.group(3)
            if buf_target is not None:
                buf_target.append(prefix)
            elif cur_chapter is None:
                pre_chapter.append(prefix)
            cur_chapter = expect_chapter
            cur_section = 1
            expect_chapter += 1
            buf_target = cell(cur_chapter, cur_section)
            buf_target.append(rest)
            continue
        # continuation line
        if buf_target is not None:
            buf_target.append(line)
        elif cur_chapter is None:
            pre_chapter.append(line)
    return chapters, pre_chapter, skipped_chapters


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

    # Build, for each present book, the ordered list of ENGLISH-classified
    # chunks between its start chunk and the next book's start chunk
    # (or end of file).
    boundaries = sorted(book_starts[b] for b in present_books)
    book_lines = {}
    for i, b in enumerate(present_books):
        start = book_starts[b]
        end = boundaries[i + 1] if i + 1 < len(boundaries) else len(classified)
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

    all_units = {}       # (book, chap_label) -> {sec: text} (section mode)
    chapter_fallback = {}  # (book, chap_label) -> merged text (chapter mode)
    book_chapter_counts = {}
    fallback_list = []
    skipped_books = []
    chapters_with_no_text = []

    for book in TARGET_BOOKS:
        lines = book_lines.get(book, [])
        chapters, pre_chapter, skipped_in_book = parse_book_english(
            lines, book, report)
        for c in skipped_in_book:
            chapters_with_no_text.append((book, c))

        # Re-label book 6's pre-chapter-I content as the reconstructed
        # chapter '1a'; re-key chapter 1 stays as corpus chapter 1.
        labelled = OrderedDict()
        if book == 6:
            text = ' '.join(l for l in pre_chapter if l).strip()
            if text:
                labelled['1a'] = {1: [text]}
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
        for lbl, secs in chapters.items():
            labelled[lbl] = secs

        corpus_chaps = corpus_struct.get(book, {})
        parsed_chap_count = len(labelled)
        corpus_chap_count = len(corpus_chaps)
        book_chapter_counts[book] = (parsed_chap_count, corpus_chap_count)
        if parsed_chap_count != corpus_chap_count:
            skipped_books.append((book, parsed_chap_count, corpus_chap_count,
                                   sorted(map(str, labelled.keys())),
                                   sorted(map(str, corpus_chaps.keys()))))
            continue

        for chap_label, secs in labelled.items():
            corpus_secs = corpus_chaps.get(chap_label, set())
            parsed_secs = set(secs.keys())
            if parsed_secs == corpus_secs and corpus_secs:
                all_units[(book, chap_label)] = {
                    s: ' '.join(p for p in parts if p).strip()
                    for s, parts in secs.items()}
            else:
                merged = ' '.join(
                    p for s in sorted(secs.keys())
                    for p in secs[s] if p).strip()
                chapter_fallback[(book, chap_label)] = merged
                fallback_list.append(
                    (book, chap_label, sorted(parsed_secs), sorted(corpus_secs)))

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
    report.append(f'chapters falling back to one unit per chapter: '
                   f'{len(fallback_list)}')
    for book, chap, got, want in fallback_list:
        report.append(f'  book {book} chapter {chap}: parsed sections {got} '
                       f'vs corpus sections {want}')

    # ---- build units / ref_to_unit -------------------------------------
    units, ref_to_unit, unit_sources = [], {}, []
    unit_index = {}

    def get_unit(text, source_idx):
        if text not in unit_index:
            unit_index[text] = len(units)
            units.append(text)
            unit_sources.append(source_idx)
        return unit_index[text]

    n_section_units = n_chapter_units = 0
    for ref, book, chap_label, sec in refs:
        if book not in TARGET_BOOKS:
            continue
        key = (book, chap_label)
        if key in all_units and sec in all_units[key]:
            text = all_units[key][sec]
            if text:
                ref_to_unit[ref] = get_unit(text, 0)
                n_section_units += 1
            continue
        if key in chapter_fallback:
            text = chapter_fallback[key]
            if text:
                ref_to_unit[ref] = get_unit(text, 1)
                n_chapter_units += 1

    coverage = len(ref_to_unit) / len(refs) if refs else 0
    report.append('')
    report.append(f'units from section-level text: {n_section_units} refs; '
                   f'from chapter-level fallback: {n_chapter_units} refs; '
                   f'{len(units)} distinct units stored')
    report.append(f'coverage: {coverage:.4f} ({len(ref_to_unit)}/{len(refs)})')

    # ---- name check (300 sampled units / ref pairs) ---------------------
    pairs = [(latin_by_ref[ref], units[ref_to_unit[ref]])
             for ref, book, chap_label, sec in refs if ref in ref_to_unit]
    hit, n_tested = V.score(pairs, 'la', sample=300)
    report.append(f'name check: hit_rate={hit} n={n_tested} '
                   f'(of {len(pairs)} translated-ref pairs available)')

    # ---- Latin-leakage check ---------------------------------------------
    def latin_func_count(text):
        toks = [t.lower() for t in word_tokens(text)]
        return sum(1 for t in toks if t in LATIN_FUNC)

    leaking = sum(1 for u in units if latin_func_count(u) >= 2)
    leakage_share = leaking / len(units) if units else 0
    report.append(f'Latin leakage: {leaking}/{len(units)} units '
                   f'({leakage_share:.4%}) contain >=2 Latin function words')

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
