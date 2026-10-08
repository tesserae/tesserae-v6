#!/usr/bin/env python3
"""Saadi's Gulistan, embedded whole inside texts/fa/saadi.diwan.tess, from
Edward B. Eastwick's 1880 translation.

Today's prose audit (research/languages/2026-10-08_persian_prose_audit.md)
found the Gulistan's prose bundled into the larger diwan file, refs
`.29808` to `.32003`. Checking that range against the Persian confirms it
is not merely the audit's flagged *prose* lines: `.29808` is the Gulistan's
own opening sentence ("Praise be to the glorious and almighty God...") and
`.32003` is its own closing sentence ("The book of the Gulistan is
finished..."), so the whole range -- prose and the verse epigrams
interleaved through it alike -- is the complete Gulistan, all eight
chapters, 2,196 refs.

This is a one-unit (whole-work) alignment, not a chapter-or-story-level
one, and that is a considered choice, not a shortcut:

  * This particular digitization of the Persian carries no inline chapter
    dividers. The table of contents at `.29993`-`.32000` names the eight
    chapters but nothing in the body repeats a heading at each chapter's
    start.
  * A quantitative check (binned counts of chapter-signature words --
    "king" words for Chapter I, "darvish" for Chapter II, "contentment"
    for Chapter III, and so on, in windows of 60 refs) was run before
    writing this script, to see whether word clustering could substitute
    for a missing marker. It could not: the signal is noisy throughout
    (kingship vocabulary recurs across every chapter, as a storytelling
    frame, not just Chapter I), so any chapter boundary picked from it
    would be a guess dressed up as a measurement.
  * Eastwick's own scan has true chapter headers (`CHAPTER I.` etc.), but
    its running page headers lag the body by about a page in places
    (`CHAPTER III. STORY XXVIII.` printed after the scan has already
    reached Chapter IV's opening), which is a known verso/recto artifact
    of this OCR, not a position a split should be anchored to.

Rather than invent a chapter boundary that cannot be checked, this ships
the one honest thing that can be checked exactly: that this Persian block,
start to finish, IS this English block, start to finish. Every one of the
2,196 refs maps to the same single unit, which is the entire translated
Gulistan. `backend/translations.py` already has a name for this grain
(`block_only`, the same case as Lucretius) and tells the reader plainly
what they are getting rather than implying a precision the data does not
have. A chapter-or-story split is real follow-on work, not abandoned here;
it would need either a differently-marked digitization of the Persian or
a hand read through the text chapter by chapter, which today's investigation
timeboxed rather than invented a half-checked answer.

Usage:
    python scripts/translations/align_saadi_gulistan_eastwick.py \
        --src /path/eastwick_djvu.txt \
        --tess texts/fa/saadi.diwan.tess \
        --first-ref saadi.diwan.29808 --last-ref saadi.diwan.32003 \
        --out-dir data/translations

--src is the raw OCR text layer (DjVuTXT) of archive.org's
TheGulistanOrRose-GardenOfShekhMuslihud-dinSadiOfShiraz-EdwardB.Eastwick
item, not committed here (public domain, 1880, but large and not this
repo's to carry).
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from write_aligned import write_aligned, tess_refs  # noqa: E402

START_MARKER = 'IN THE NAME OF GOD'
END_MARKER = 'STEPHEN AUSTIN AND SONS, PRINTERS, HERTFORD.'

# Running headers and page-number artifacts that recur throughout the OCR
# text but are not part of the translation itself.
HEADER_RE = re.compile(
    r'^\s*CHAPTER\s+[IVXL0-9]+\.?\s*(STORY|MAXIM|S\s*TOR\s*Y)?\s*[IVXL0-9.\s]*$',
    re.IGNORECASE)
CONCLUSION_HEADER_RE = re.compile(r'^\s*CONCLUSIO[NX]?\.?(\s+OF\s+THE\s+BOOK)?\.?\s*$', re.IGNORECASE)
PAGE_NUMBER_RE = re.compile(r'^\s*\d+(\s+\d+)?\s*$')


def clean_english(raw_text):
    """Strip OCR running headers and page numbers, collapse blank runs."""
    out_lines = []
    for line in raw_text.split('\n'):
        stripped = line.strip()
        if not stripped:
            out_lines.append('')
            continue
        if HEADER_RE.match(stripped) or CONCLUSION_HEADER_RE.match(stripped) \
                or PAGE_NUMBER_RE.match(stripped):
            continue
        out_lines.append(stripped)
    # Collapse 2+ blank lines to one paragraph break, join wrapped lines
    # with a space (this OCR wraps every physical line of the print page).
    paragraphs, cur = [], []
    for line in out_lines:
        if line == '':
            if cur:
                paragraphs.append(' '.join(cur))
                cur = []
        else:
            cur.append(line)
    if cur:
        paragraphs.append(' '.join(cur))
    return '\n\n'.join(p for p in paragraphs if p.strip())


def extract_translation(src_path):
    with open(src_path, encoding='utf-8', errors='replace') as f:
        text = f.read()
    start = text.find(START_MARKER)
    # The printer's imprint also appears on the title page, so the END
    # marker's FIRST occurrence is near the start of the file, not the
    # end; its last occurrence is the real colophon that closes the book.
    end = text.rfind(END_MARKER)
    if start == -1 or end == -1 or end <= start:
        sys.exit(f'could not locate start ({START_MARKER!r}) and end '
                  f'({END_MARKER!r}) markers in {src_path}')
    return clean_english(text[start:end])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--first-ref', required=True)
    ap.add_argument('--last-ref', required=True)
    ap.add_argument('--out-dir', required=True)
    a = ap.parse_args()

    english = extract_translation(a.src)
    print(f'{len(english)} characters of cleaned English extracted from {a.src}', flush=True)
    if len(english) < 10000:
        sys.exit('extracted English looks far too short for the whole Gulistan; refusing to write')

    all_refs = tess_refs(a.tess)
    if a.first_ref not in all_refs or a.last_ref not in all_refs:
        sys.exit(f'{a.first_ref} or {a.last_ref} not found in {a.tess}')
    i0, i1 = all_refs.index(a.first_ref), all_refs.index(a.last_ref)
    if i1 < i0:
        sys.exit(f'{a.last_ref} precedes {a.first_ref} in {a.tess}')
    refs = all_refs[i0:i1 + 1]
    print(f'{len(refs)} refs from {a.first_ref} to {a.last_ref}', flush=True)

    units = [english]
    ref_to_unit = {ref: 0 for ref in refs}

    write_aligned(
        a.out_dir, 'fa', os.path.basename(a.tess)[:-5], units, ref_to_unit,
        attribution=('Edward B. Eastwick, The Gulistan; or, Rose-Garden, of Shekh '
                     "Muslihu'd-din Sadi of Shiraz (London: Trübner & Co., 2nd ed., 1880)"),
        license=('Public domain (published 1880, well over 95 years before this file '
                  'was built). Text from the Internet Archive scan '
                  'archive.org/details/TheGulistanOrRose-GardenOfShekhMuslihud-dinSadiOfShiraz-EdwardB.Eastwick '
                  '(DjVuTXT OCR layer, marked public domain by the uploader; the scanned '
                  'title page itself shows "1880" and the original printer\'s imprint, '
                  'confirmed by direct inspection before use here).'),
        sources=[{'translator': 'Edward B. Eastwick', 'year': 1880,
                  'title': "The Gulistan; or, Rose-Garden, of Shekh Muslihu'd-din Sadi of Shiraz",
                  'url': 'https://archive.org/details/TheGulistanOrRose-GardenOfShekhMuslihud-dinSadiOfShiraz-EdwardB.Eastwick'}],
        confidence='exact', approximate=False, tess_refs=refs,
        verified_by=('the Persian range itself: ref .29808 is the Gulistan\'s own opening '
                     'sentence and .32003 its own closing sentence, so the whole range is '
                     'exactly the work Eastwick translated, start to finish, with no partial '
                     'overlap to misjudge.'),
        notes=('One unit covering the whole Gulistan. This is a deliberate whole-work '
               'alignment, not a partial one: this edition of the Persian has no inline '
               'chapter dividers to anchor a finer split on, and a check of chapter-signature '
               'word clustering across the range found the signal too noisy to trust (see the '
               'script\'s module docstring for the check). A chapter-or-story split is '
               'possible future work with either a differently-marked Persian source or a '
               'hand read through the text.'),
    )
    print(f'[done] 1 unit, {len(ref_to_unit)} refs, confidence exact, whole-work grain', flush=True)


if __name__ == '__main__':
    main()
