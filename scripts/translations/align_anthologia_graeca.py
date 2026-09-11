#!/usr/bin/env python3
"""
Align W. R. Paton's Loeb translation (5 vols, 1916-1918, US public domain) of
the Greek Anthology to our anthologia_graeca.part.N .tess files, book by book.

THE PROBLEM WITH THE PREVIOUS ATTEMPT (kept at
/home/ncoffee/tesserae-backups/curtius_batch_scratch_2026-09-10/scratch_curtius/
converters/paton_align.py for the record)

That version separated Greek pages from English pages using the printed
running heads: a bare "GREEK ANTHOLOGY" line meant a Greek page, "BOOK <roman>"
meant an English page. Two things break that:

  1. On the FIRST English page of every book (the one carrying the section
     title, e.g. "BOOK IX / - THE DECLAMATORY AND DESCRIPTIVE EPIGRAMS"), the
     running head reads "GREEK ANTHOLOGY" too -- Loeb's own convention, not an
     OCR error. A header-only classifier reads that page as Greek and throws
     the section's first few epigrams away.
  2. Running heads are themselves OCR'd, and roman numerals and repeated
     words are exactly the kind of short, low-redundancy text OCR drops or
     garbles most often. When a head fails to recognize, the previous
     approach's state machine got stuck, and coverage collapsed on the
     affected books (down to single digits of percent on some).

THIS VERSION classifies by the actual body content instead of the running
head, per the brief: "a page whose letters are mostly Greek script is a Greek
page; drop it." There are no real page breaks in the archive.org djvu text
(no form feeds), so this works on lines, not pages:

  1. Vote each line 'greek' or 'latin' by counting alphabetic characters in
     the Greek Unicode blocks vs the Latin alphabet (ignore lines with too
     few letters to have an opinion).
  2. Smooth the vote sequence with a majority filter over a 9-line window.
     A real page is many dozens of lines long, so this leaves genuine
     transitions alone. It absorbs the single most damaging piece of noise
     in this OCR: on a Greek page, the epigram's poet-name heading is set in
     Greek capitals, and Greek capitals are, letter for letter, mostly the
     same glyphs as Latin capitals (A, B, E, Z, H, I, K, M, N, O, P, T, Y, X
     among them) -- so a heading like ΠΟΛΥΑΙΝΟΥ ΣΑΡΔΙΑΝΟΥ OCRs as the pure
     ASCII "TOATAINOT SAPAIANOT" and reads, one line at a time, as English.
     Surrounded on both sides by dozens of lines of real lower-case Greek
     verse, the smoothing filter keeps the whole run classified Greek and the
     heading goes with it.
  3. A second, per-line safety net then drops any individual line that is
     itself still majority-Greek even inside a run smoothed to 'latin' (the
     reverse case: a couplet of real Greek text spilling a line or two past
     where the smoothing settled at a boundary).
  4. We never need the Greek-page heading anyway: the poet's name is printed
     again, correctly, as plain English on the facing English page ("1--
     POLYAENUS OF SARDIS"), which is the only heading this script reads.

Epigram markers and numbering
------------------------------
On an English page each epigram opens with a short, standalone line: the
epigram number, a period and/or dash, and the poet in caps or title case
("363.--MELEAGER", "2.--TIBERIUS ILLUSTRIUS", "3.--ANTIPATER, By some
attributed to Plato"). We require the line to be short (<=60 chars after
stripping) so we don't mistake an in-sentence "2." for a heading.

OCR turns 1 into l/I and 0 into O inside these numbers reasonably often. We
normalize l/I->1 and O->0 in the numeral token before comparing it to the
expected sequence for the book (read from our own .tess refs, so it already
carries every real lettered exception, e.g. 9.13b). Where that normalization
still doesn't produce the number in hand, and the book's own expected
sequence increases monotonically otherwise, we accept a numeral within edit
distance 1 of the currently-expected number as a repair, and log it -- never
a silent guess.

Volumes hold several books, and Paton restarts numbering at 1 for every book.
We exploit that: rather than trust "BOOK <roman>" headers (same OCR fragility
as above) to say where one book ends and the next begins, we concatenate the
expected epigram sequences of every book in a volume, in book order, and
align the found marker sequence against that ONE long expected sequence, in
order. A found "1" that arrives only after the previous book's last epigram
has been matched is simply the next book beginning; nothing has to name it.
"""
import re
import os
import sys
import json
import unicodedata
import difflib
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import proper_names as PN  # noqa: E402

# Where the five archive.org djvu text files live. Pass the directory as the
# first argument, or set PATON_SRC_DIR; the default is the machine this was
# first run on.
SRC_DIR = (sys.argv[1] if len(sys.argv) > 1 else
           os.environ.get('PATON_SRC_DIR',
                          '/home/ncoffee/tesserae-backups/curtius_batch_scratch_2026-09-10/'
                          'scratch_curtius/translations_src'))
TESS_DIR = os.path.join(ROOT, 'texts', 'grc')
OUT_DIR = os.path.join(ROOT, 'data', 'translations')

VOLUMES = [
    # 'year' is read from each volume's own title/copyright page ("First
    # printed/published ..."), confirmed in the OCR text: vol 1 "First
    # printed 1916", vol 2 "First published 1917", vol 4's title page reads
    # "MCMXVIII" (1918). Vol 3's own copyright page OCR's as "First printed
    # 1915", which conflicts with the standard bibliographic date for this
    # volume (1917) by exactly the kind of digit the OCR elsewhere confuses
    # (5/7); 1917 is used here as the far more likely reading, not the raw
    # OCR digit. Vol 5's copyright page did not OCR at all; 1918 is used by
    # analogy with vol 4 (published the same year per the standard LCL
    # record), not independently confirmed from this scan.
    {'file': 'greekanthology01pato_djvu.txt', 'books': list(range(1, 7)),
     'vol': 1, 'first_roman': 'I', 'year': 1916},
    {'file': 'greekanthologyii0002pato_djvu.txt', 'books': [7, 8],
     'vol': 2, 'first_roman': 'VII', 'year': 1917},
    {'file': 'greekanthology03pato_djvu.txt', 'books': [9],
     'vol': 3, 'first_roman': 'IX', 'year': 1917},
    {'file': 'greekanthology0004wrpa_djvu.txt', 'books': [10, 11, 12],
     'vol': 4, 'first_roman': 'X', 'year': 1918},
    {'file': 'greekanthology0005wrpa_djvu.txt', 'books': [13, 14, 15, 16],
     'vol': 5, 'first_roman': 'XIII', 'year': 1918},
]
BOOK_YEAR = {b: v['year'] for v in VOLUMES for b in v['books']}

ROMAN = {1: 'I', 2: 'II', 3: 'III', 4: 'IV', 5: 'V', 6: 'VI', 7: 'VII', 8: 'VIII',
         9: 'IX', 10: 'X', 11: 'XI', 12: 'XII', 13: 'XIII', 14: 'XIV', 15: 'XV', 16: 'XVI'}

GREEK_RANGES = [(0x0370, 0x03FF), (0x1F00, 0x1FFF)]


def is_greek_char(ch):
    o = ord(ch)
    return any(a <= o <= b for a, b in GREEK_RANGES)


def line_vote(line):
    """('greek'|'latin'|None), counting only alphabetic characters."""
    greek = latin = 0
    for ch in line:
        if ch.isalpha():
            if is_greek_char(ch):
                greek += 1
            elif 'a' <= ch.lower() <= 'z':
                latin += 1
    if greek + latin < 5:
        return None
    return 'greek' if greek > latin else 'latin'


def smooth_labels(votes, window=9, need=5):
    """Majority-filter the vote sequence, restricted to substantive (non-None)
    votes, then fill blank/ambiguous lines from their nearest neighbour."""
    idxs = [i for i, v in enumerate(votes) if v is not None]
    vals = [votes[i] for i in idxs]
    n = len(vals)
    half = window // 2
    smoothed = list(vals)
    for k in range(n):
        lo, hi = max(0, k - half), min(n, k + half + 1)
        c = Counter(vals[lo:hi])
        best, cnt = c.most_common(1)[0]
        if cnt >= need or (hi - lo) < window:
            smoothed[k] = best
    out = [None] * len(votes)
    for pos, i in enumerate(idxs):
        out[i] = smoothed[pos]
    last = None
    for i in range(len(out)):
        if out[i] is None:
            out[i] = last
        else:
            last = out[i]
    nxt = None
    for i in range(len(out) - 1, -1, -1):
        if out[i] is None:
            out[i] = nxt
        else:
            nxt = out[i]
    return out


HEADER_RE = re.compile(
    r'^\s*[-–—]?\s*(?:THE\s+)?(?:GREEK\s+ANTHOLOGY|BOOK\s+[IVXLCM0-9]+)\b.*$',
    re.IGNORECASE)
PAGE_NUM_RE = re.compile(r'^\s*[0-9]{1,4}\s*$')
SHORT_NOISE_RE = re.compile(r'^\s*[^A-Za-z0-9]{0,4}\s*$')

# A heading line: short, starts with a numeral-like token, then a dash, then a
# name. Digits may be OCR-confused with l/I (->1) or O (->0).
MARKER_RE = re.compile(
    r'^\s*([0-9lIoO]{1,4})\s*([a-zA-Z])?\s*[.,]?\s*[—–-]+\s*([A-Z][^\n]*)$')

NUMERAL_MAP = str.maketrans({'l': '1', 'I': '1', 'o': '0', 'O': '0'})


def normalize_numeral(tok):
    return tok.translate(NUMERAL_MAP)


def build_english_lines(raw_lines):
    """Lines classified as English content, header/page-number noise already
    stripped, in original reading order."""
    votes = [line_vote(l) for l in raw_lines]
    labels = smooth_labels(votes)
    kept = []
    for i, line in enumerate(raw_lines):
        if labels[i] != 'latin':
            continue
        # per-line safety net: a stray Greek line inside a 'latin' block
        if votes[i] == 'greek':
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if HEADER_RE.match(stripped):
            continue
        if PAGE_NUM_RE.match(stripped):
            continue
        if SHORT_NOISE_RE.match(stripped):
            continue
        # an all-caps short leftover fragment of a wrapped section title
        # next to a header (e.g. "AND DESCRIPTIVE EPIGRAMS" on its own line)
        if (stripped.isupper() and len(stripped) <= 40
                and not MARKER_RE.match(stripped)):
            near_header = False
            for j in range(max(0, i - 2), min(len(raw_lines), i + 3)):
                if HEADER_RE.match(raw_lines[j].strip()):
                    near_header = True
                    break
            if near_header:
                continue
        kept.append(stripped)
    return kept


def dehyphenate_join(lines):
    out = []
    for line in lines:
        if not line:
            continue
        if (out and out[-1].endswith('-') and not out[-1].endswith('--')
                and not MARKER_RE.match(line)):
            out[-1] = out[-1][:-1] + line
        else:
            out.append(line)
    return out


# A poet-name heading whose text is itself Greek-page bleed-through (Greek
# capitals OCR'd as pseudo-Latin, see module docstring) is recognizable at
# the text level, independent of any page/line classification: Greek names
# on the Greek page are printed in the genitive ("of so-and-so"), so they
# overwhelmingly end in the transliterated genitive endings -ΟΥ/-ΟΝ (OCR's
# upsilon and omicron-upsilon as Latin OT/OY), and the OCR pass on this
# heavily-capitalized, accent-heavy text also throws in stray symbols no
# real English heading contains. Real English headings (poet names in their
# ordinary English/Latinised form, "ANONYMOUS", "By THE SAME") essentially
# never end this way. Filtering these out at the source, rather than only
# reconciling duplicate number sequences after the fact, is what actually
# catches a bleed heading that isn't immediately adjacent to (or in the same
# order as) its real English counterpart.
BLEED_SUFFIX_RE = re.compile(r'(?:OT|OY)\s*$')
# Embedded (no preceding space) -- a symbol stuck to a letter is corruption
# inside the OCR'd word itself. A symbol set off by a space is instead very
# often this OCR's rendering of a footnote marker on a perfectly real
# English heading ("Another (R)", "GAETULICUS 4"), so that is stripped
# separately below rather than used as bleed evidence.
BLEED_SYMBOL_EMBEDDED_RE = re.compile(r'\S[<>{}\[\]|~^§†‡]')
FOOTNOTE_TAIL_RE = re.compile(r'\s*[®0-9|?}\]>*]+$')


def clean_heading_text(rest):
    """Strip a trailing, space-separated footnote marker (a superscript
    number or symbol this OCR renders inline), which is not part of the
    heading itself."""
    prev = None
    while prev != rest:
        prev = rest
        rest = FOOTNOTE_TAIL_RE.sub('', rest).strip()
    return rest


def looks_like_bleed(rest):
    # A real poet-name heading never contains a digit once its own trailing
    # footnote marker has been cleaned off; a caption from the volume's
    # front-matter List of Illustrations ("Rep. i. p. 527, 3. An athlete
    # running.") does, throughout, not just at the end -- and looks like a
    # heading only because it happens to start with a number too.
    if re.search(r'\d', rest):
        return True
    return bool(BLEED_SUFFIX_RE.search(rest) or BLEED_SYMBOL_EMBEDDED_RE.search(rest))


ENGLISH_STOPWORDS = frozenset(
    'the of and a an in to is his her with for on by as at from he she it '
    'they that this was were are not but or thou thy thee my your our '
    'their who which what have has had be been will would shall should'.split())


def looks_like_non_english_body(body):
    """Genuine Paton prose is dense with ordinary English function words.
    Greek-page bleed-through (verse OCR'd with a heavy admixture of Latin
    look-alike letters) essentially never contains one, even when its own
    heading passed every other check. Only judged with enough words to have
    an opinion -- an epigram of two or three words is rare but real."""
    words = re.findall(r"[A-Za-z']+", body)
    if len(words) < 12:
        return False
    hits = sum(1 for w in words if w.lower() in ENGLISH_STOPWORDS)
    return (hits / len(words)) < 0.06


def find_markers(lines):
    """[(line_index, raw_num_token, letter_suffix, heading_rest), ...] for
    every SHORT standalone line that looks like a genuine English epigram
    heading (Greek-bleed-looking headings are dropped at the source)."""
    out = []
    for i, line in enumerate(lines):
        if len(line) > 60:
            continue
        m = MARKER_RE.match(line)
        if not m:
            continue
        num_tok, letter, rest = m.groups()
        rest = clean_heading_text(rest.strip())
        if looks_like_bleed(rest):
            continue
        out.append((i, num_tok, (letter or ''), rest))
    return out


def load_expected(book_n):
    """Ordered, de-duplicated epigram ids (e.g. '13', '13b') for one book, as
    they occur in our .tess file."""
    seen = set()
    ordered = []
    with open(os.path.join(TESS_DIR, f'anthologia_graeca.part.{book_n}.tess'),
               encoding='utf-8') as f:
        for line in f:
            if '\t' not in line:
                continue
            ref = line.split('\t')[0].strip('<>')
            tail = ref.split()[-1]
            parts = tail.split('.')
            if len(parts) < 2:
                continue
            ep = parts[1]
            if ep not in seen:
                seen.add(ep)
                ordered.append(ep)
    return ordered


def load_greek_refs(book_n):
    """ref -> greek text line, in file order, for the name check and to know
    every ref that must be covered."""
    refs = []
    with open(os.path.join(TESS_DIR, f'anthologia_graeca.part.{book_n}.tess'),
               encoding='utf-8') as f:
        for line in f:
            if '\t' not in line:
                continue
            ref, text = line.rstrip('\n').split('\t', 1)
            refs.append((ref.strip('<>'), text.strip()))
    return refs


def epigram_id_of(ref_tail):
    parts = ref_tail.split()[-1].split('.')
    return parts[1] if len(parts) > 1 else None


def base_num(ep_id):
    m = re.match(r'^(\d+)', ep_id)
    return m.group(1) if m else ep_id


def edit_distance_le1(a, b):
    if a == b:
        return True
    if abs(len(a) - len(b)) > 1:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= (1 - 1.0 / max(len(a), len(b), 1))


WINDOW = 8
WIDE_SEARCH_CAP = 250  # generous, but bounded to the current book (see below)


def _tok_matches(num_tok, letter, exp):
    raw = normalize_numeral(num_tok)
    cand_l = (raw + letter.lower()) if letter else raw
    return exp == raw + letter or exp == cand_l or exp.lower() == cand_l.lower()


def _confirms_resync(markers, mi, concat_expected, p, cur_book, book_of_index):
    """After tentatively placing markers[mi] at expected position p, does the
    sequence keep making sense? Require that at least one of the next two
    found markers lands where it should right after p (allowing one
    intervening spurious marker, e.g. an uncaught duplicate heading)."""
    n = len(concat_expected)
    for lookahead in (1, 2):
        if mi + lookahead >= len(markers):
            break
        nxt_num, nxt_letter = markers[mi + lookahead][0], markers[mi + lookahead][1]
        target = p + lookahead
        if target >= n or book_of_index[target] != cur_book:
            continue
        if _tok_matches(nxt_num, nxt_letter, concat_expected[target]):
            return True
    return False


def align_volume(concat_expected, book_of_index, markers, log, vol_n):
    """Greedy alignment of found markers, in order, against the concatenated
    expected epigram-id sequence for the whole volume.

    Returns {expected_index: text}. Lettered ids with no marker of their own
    are attached to the immediately preceding matched id (same book only) and
    logged, not counted as missing.

    A found heading that doesn't match within the next few expected ids is
    first tried as a small numeral repair (single OCR digit confusion), then,
    if that fails too, as an exact match anywhere later IN THE SAME BOOK. That
    second step matters: Paton's own numbering sometimes really does skip
    several epigrams in a row (a stretch the OCR mangled past recognition, or
    numbers Paton or his source omitted outright), and a small lookahead
    window has no way back from that -- it desyncs once and stays desynced
    for the rest of the book. An exact match on the number itself, found
    later but still inside the same book, is strong enough evidence to jump
    to it directly; everything skipped over is logged as a real gap.
    """
    result = {}
    attach = {}  # expected_index (lettered, unmatched) -> expected_index it attaches to
    ei = 0
    n = len(concat_expected)
    last_matched_ei = None

    def emit(idx, text):
        text = ' '.join(text.split())
        if text:
            result[idx] = (result.get(idx, '') + ' ' + text).strip() if idx in result else text

    for mi, (num_tok, letter, rest, body) in enumerate(markers):
        raw = normalize_numeral(num_tok)
        cand = raw + letter
        cand_l = (raw + letter.lower()) if letter else raw
        matched_idx = None
        wide_jump = False
        # 1) exact match at current position (case-insensitive letter)
        window = concat_expected[ei:ei + WINDOW]
        for off, exp in enumerate(window):
            if exp == cand or exp == cand_l or exp.lower() == cand_l.lower():
                matched_idx = ei + off
                break
        # 2) numeral repair: expected[ei] is within edit distance 1 of `raw`,
        # SAME LENGTH only (a single misread digit, "l for 1, O for 0"-style
        # -- the documented failure mode). A length mismatch is a different,
        # riskier kind of error (a whole digit dropped or gained), and for a
        # short token in particular it is also exactly what a genuine "1"
        # opening the NEXT book looks like next to an expected id like "31"
        # -- too dangerous to paper over here; left to the wide search below,
        # which requires confirmation from the following marker too.
        if matched_idx is None and ei < n:
            exp = concat_expected[ei]
            exp_base = base_num(exp)
            if (letter == '' and len(exp_base) == len(raw)
                    and edit_distance_le1(exp_base, raw) and exp_base != raw):
                matched_idx = ei
                log['numeral_repairs'].append(
                    {'vol': vol_n, 'expected': exp, 'found_token': num_tok,
                     'interpreted_as': exp})
        # 3) wide exact-match search, capped to the current book only, and
        # only accepted if at least one of the next couple of found markers
        # then continues in sequence right after it -- a real resync, not a
        # lone coincidental collision with some garbage numeral elsewhere in
        # the same book.
        if matched_idx is None and ei < n:
            cur_book = book_of_index[ei]
            hi = min(n, ei + WIDE_SEARCH_CAP)
            for p in range(ei + WINDOW, hi):
                if book_of_index[p] != cur_book:
                    break
                exp = concat_expected[p]
                if exp == cand or exp == cand_l or exp.lower() == cand_l.lower():
                    if _confirms_resync(markers, mi, concat_expected, p, cur_book, book_of_index):
                        matched_idx = p
                        wide_jump = True
                    break
        if matched_idx is None:
            log['spurious_markers'].append(
                {'vol': vol_n, 'found_token': num_tok, 'letter': letter,
                 'near_expected_index': ei,
                 'near_expected': concat_expected[ei:ei + 3]})
            continue
        if wide_jump:
            log['wide_jumps'].append(
                {'vol': vol_n, 'from_expected_index': ei, 'to_expected_index': matched_idx,
                 'epigram_id': concat_expected[matched_idx],
                 'n_skipped': matched_idx - ei})
        # anything strictly between ei and matched_idx was skipped: lettered
        # ones attach to the last matched id IN THE SAME BOOK, everything
        # else is really missing
        skipped = list(range(ei, matched_idx))
        for s in skipped:
            sid = concat_expected[s]
            if (re.search(r'[a-zA-Z]$', sid) and last_matched_ei is not None
                    and book_of_index[last_matched_ei] == book_of_index[s]):
                attach[s] = last_matched_ei
                log['lettered_attached'].append(
                    {'vol': vol_n, 'epigram_id': sid, 'attached_to_index': last_matched_ei,
                     'attached_to_id': concat_expected[last_matched_ei]})
            else:
                log['skipped_missing'].append({'vol': vol_n, 'epigram_id': sid})
        emit(matched_idx, body)
        last_matched_ei = matched_idx
        ei = matched_idx + 1

    # trailing expected entries never reached by any marker
    for s in range(ei, n):
        sid = concat_expected[s]
        if (re.search(r'[a-zA-Z]$', sid) and last_matched_ei is not None
                and book_of_index[last_matched_ei] == book_of_index[s]):
            attach[s] = last_matched_ei
            log['lettered_attached'].append(
                {'vol': vol_n, 'epigram_id': sid, 'attached_to_index': last_matched_ei,
                 'attached_to_id': concat_expected[last_matched_ei]})
        else:
            log['skipped_missing'].append({'vol': vol_n, 'epigram_id': sid})

    return result, attach


def process_volume(vol, log):
    fn = os.path.join(SRC_DIR, vol['file'])
    raw_lines = open(fn, encoding='utf-8').read().split('\n')

    # Skip anything before the volume's own first book heading (front matter:
    # title page, preface, table of contents), so a stray numeral there can
    # never be mistaken for epigram 1.
    first_roman = vol['first_roman']
    start_idx = 0
    anchor = re.compile(r'^\s*BOOK\s+' + re.escape(first_roman) + r'\b', re.IGNORECASE)
    for i, l in enumerate(raw_lines):
        if anchor.match(l.strip()):
            start_idx = i
            break
    raw_lines = raw_lines[start_idx:]

    english_lines = build_english_lines(raw_lines)
    joined = dehyphenate_join(english_lines)
    markers_raw = find_markers(joined)

    # Duplicate heading BLOCKS: the Greek page's own corrupted heading for an
    # epigram (Greek capitals OCR'd as pseudo-Latin, see module docstring)
    # sometimes survives the script-smoothing filter right at a page
    # boundary, immediately before the real English heading for the SAME
    # epigram. Where OCR quality is worse (volumes 4 and 5 noticeably), this
    # doesn't happen one heading at a time -- a whole run of several Greek
    # pages' worth of headings ("1 NIKAPXOT", "2 KAAAIKTHPO", "3 AAESTIOTON")
    # leaks through as one block, immediately followed by the real English
    # block with the SAME sequence of numbers ("1 NICARCHUS", "2 CALLICTER",
    # "3 ANONYMOUS"). Numbers strictly increase within a book and never
    # repeat, so whenever a run of found numbers is immediately repeated
    # (same numbers, same order) by the next run, the earlier run cannot be
    # a second, real, set of epigrams -- it is always this bleed-through, and
    # is dropped, keeping the later, real run.
    numkeys = [normalize_numeral(m[1]) + m[2] for m in markers_raw]
    MAX_BLOCK = 20
    keep_mask = [True] * len(markers_raw)
    i = 0
    while i < len(markers_raw):
        best_l = 0
        max_l = min(MAX_BLOCK, (len(markers_raw) - i) // 2)
        for l in range(max_l, 0, -1):
            if numkeys[i:i + l] == numkeys[i + l:i + 2 * l]:
                best_l = l
                break
        if best_l:
            for k in range(i, i + best_l):
                keep_mask[k] = False
            log['duplicate_headings_dropped'].append(
                {'vol': vol['vol'], 'block_len': best_l,
                 'epigrams': numkeys[i:i + best_l],
                 'dropped_headings': [markers_raw[k][3] for k in range(i, i + best_l)],
                 'kept_headings': [markers_raw[k][3] for k in range(i + best_l, i + 2 * best_l)]})
            i += 2 * best_l
        else:
            i += 1
    markers_dedup = [m for m, keep in zip(markers_raw, keep_mask) if keep]

    # build per-marker body text: from the heading line's own "rest" is
    # EXCLUDED (it's the poet name/attribution, not the translation), body is
    # every joined line after the heading up to (not incl.) the next heading.
    marker_positions = [m[0] for m in markers_dedup]
    markers_all = []
    for k, (idx, num_tok, letter, rest) in enumerate(markers_dedup):
        end = marker_positions[k + 1] if k + 1 < len(marker_positions) else len(joined)
        body_lines = joined[idx + 1:end]
        body = ' '.join(body_lines)
        markers_all.append((num_tok, letter, rest, body))

    # A body-level English-word-density check was tried here (to catch a
    # heading whose own text passes every check, e.g. Greek ΑΔΗΛΟΝ
    # "anonymous" transliterated as "AAHAON", but whose body is still
    # Greek-page bleed-through). Net effect across all 16 books was NEGATIVE
    # (86.5% vs 87.5% overall): it recovered book 7 and fixed book 13
    # outright, but it also discarded real short-bodied epigrams elsewhere
    # (book 8's Gregory epigrams, book 14's riddles), which are terse enough
    # in translation to fall under the stopword-density floor legitimately.
    # Kept out for that reason; not applied.
    markers = markers_all

    expected_per_book = {b: load_expected(b) for b in vol['books']}
    concat_expected = []
    book_of_index = []
    for b in vol['books']:
        for eid in expected_per_book[b]:
            concat_expected.append(eid)
            book_of_index.append(b)

    result, attach = align_volume(concat_expected, book_of_index, markers, log, vol['vol'])

    # Build, per book, an ordered unit list (one entry per GLOBAL index that
    # was actually matched, in expected order) and an eid -> unit-position map
    # that also covers lettered epigrams attached to a base unit. Working in
    # GLOBAL concat_expected indices throughout avoids ever confusing a
    # book's own 0-based epigram position with its offset into the volume.
    per_book_units = {b: [] for b in vol['books']}
    per_book_eid_to_pos = {b: {} for b in vol['books']}
    global_idx_to_pos = {}  # global concat_expected index -> position in that book's unit list
    for idx, eid in enumerate(concat_expected):
        b = book_of_index[idx]
        if idx in result:
            pos = len(per_book_units[b])
            per_book_units[b].append(result[idx])
            global_idx_to_pos[idx] = pos
            per_book_eid_to_pos[b][eid] = pos
    for s, target in attach.items():
        b = book_of_index[s]
        eid = concat_expected[s]
        pos = global_idx_to_pos.get(target)
        if pos is not None:
            per_book_eid_to_pos[b][eid] = pos

    return per_book_units, per_book_eid_to_pos, expected_per_book


# --- Loeb small-capital first word ---------------------------------------
# The Loeb page sets the FIRST WORD of every translation in small capitals.
# Small caps are shorter than full capitals, and this OCR reads several of
# them, letter for letter, as if they were lower-case: most often H -> u
# ("THE" -> "Tue", "WHEN" -> "Wuen"), and occasionally another tall letter
# behaves the same way ("BLEST" -> "Buest", L -> u; "GUARDIAN" -> "Guarpian",
# D -> p). The table below is restricted to cases confirmed by reading the
# rest of the sentence -- each entry either matches the coordinator's own
# list outright, or was checked here against its actual context (logged
# case by case in the research thread) before being added. Two spellings are
# kept for "whether" ("Wueruer", "Wuertuer") because this OCR did not
# converge on one rendering of the double H. Deliberately EXCLUDED: "Curist"
# (Christ), "Luxe" (Luke) and "Tueses" (Thebes, confirmed by context, not
# "these") are all proper names and left untouched, per instruction; "Fue",
# "Suep", "Aut-wisE" and other one-off, low-confidence strings are also left
# untouched rather than guessed.
FIRST_WORD_REPAIRS = {
    'Tue': 'The', 'Wuen': 'When', 'Ir': 'If', 'Tuis': 'This', 'Tuou': 'Thou',
    'Wuart': 'What', 'Wuo': 'Who', 'Tuus': 'Thus', 'Wuy': 'Why',
    'Wuere': 'Where', 'Wuether': 'Whether', 'Tuese': 'These', 'Tuere': 'There',
    'Tuey': 'They', 'Tuen': 'Then', 'Wuile': 'While',
    # additional cases verified from their own sentence context:
    'Tuts': 'This', 'Tus': 'This', 'Sue': 'She', 'Buest': 'Blest',
    'Wuite': 'White', 'Guarpian': 'Guardian', 'Wueruer': 'Whether',
    'Wuertuer': 'Whether',
}
FIRST_WORD_RE = re.compile(r'^(\W*)([A-Za-z]+)(.*)$', re.DOTALL)


def repair_first_word(unit, counts):
    m = FIRST_WORD_RE.match(unit)
    if not m:
        return unit
    lead, word, rest = m.groups()
    repl = FIRST_WORD_REPAIRS.get(word)
    if repl is None:
        return unit
    counts[word] += 1
    return lead + repl + rest


# --- English-likeness test -------------------------------------------------
# Some units are Greek-page OCR that leaked through as if they were the
# English heading's body (see the module docstring on why that happens).
# Others are a genuine English opening followed by leaked Greek/footnote
# text appended after it (the marker boundary between one epigram's real
# body and the next heading was missed) -- still wrong to show whole, since
# the reader would see Greek text under "Translation". Both are caught the
# same way: real Paton prose is dense with ordinary English function words
# (the, and, of, who, this...) at a remarkably stable rate; transliterated
# Greek is not, even where individual tokens coincidentally resemble English
# words often enough to fool a general-vocabulary check (tried first here,
# and abandoned: at any threshold that did not also start rejecting real,
# short, proper-noun-heavy epigrams, the two categories overlapped too much
# to separate). Function-word DENSITY does not have that problem: measured
# across the two examples flagged for review here (7.607, 14.141) it sits at
# 0.03-0.05; every real spot-check and a broad manual sample of clean units
# sits at 0.3 or higher, and the handful of units found in the 0.10-0.15
# band on inspection all turned out to be exactly the "good opening + leaked
# Greek tail" case, not clean text -- so the floor is set at 0.15, with a
# cap on no-vowel tokens (another mark of letter-salad OCR) as a second,
# mostly redundant check.
STOPWORDS_EN = frozenset("""
the and for are but not you all any can had her was one our out day get has
him his how man new now old see two way who about after again also always
among another around as at away be because been before began begin being
below between both by call came can cannot could did do does down each even
every first from further gave get gets give given he here him himself
however i if in into is it its itself let like made make many may me might
more most much must my myself never no nor now of off on once only or other
our ours own same she should since so some such than that their them
themselves then there these they this those thou thy thee thus to too under
until up upon us we were what when where which while who whom whose why
will with within without would your yourself
""".split())
NOVOWEL_RE = re.compile(r'[aeiouyAEIOUY]')
ENGLISH_MIN_TOKENS = 6
ENGLISH_DENSITY_FLOOR = 0.15
ENGLISH_NOVOWEL_CAP = 0.30


def english_likeness(unit):
    """(is_english, density, novowel_frac, n_tokens). Units with too few
    tokens to judge reliably are passed (True) rather than guessed at."""
    toks = re.findall(r"[A-Za-z']+", unit)
    toks3 = [t for t in toks if len(t) >= 3]
    if len(toks3) < ENGLISH_MIN_TOKENS:
        return True, None, None, len(toks3)
    stop_hits = sum(1 for t in toks if t.lower() in STOPWORDS_EN)
    density = stop_hits / len(toks)
    novowel = sum(1 for t in toks3 if not NOVOWEL_RE.search(t))
    novowel_frac = novowel / len(toks3)
    ok = density >= ENGLISH_DENSITY_FLOOR and novowel_frac <= ENGLISH_NOVOWEL_CAP
    return ok, density, novowel_frac, len(toks3)


def clean_book_units(book_n, units, eid_to_pos, greek_refs, repair_counts, log):
    """Repair the first-word small-caps OCR, then drop any unit that fails
    the English-likeness test, compacting positions and remapping eid ->
    position (and the refs that pointed at each dropped position, for the
    log) accordingly. Only removes units; never invents or merges text."""
    units = [repair_first_word(u, repair_counts) for u in units]

    pos_to_refs = {}
    for ref, gtext in greek_refs:
        eid = epigram_id_of(ref)
        pos = eid_to_pos.get(eid)
        if pos is not None:
            pos_to_refs.setdefault(pos, []).append(ref)

    keep_remap = {}  # old pos -> new pos
    new_units = []
    for pos, u in enumerate(units):
        ok, density, novowel_frac, n_tok = english_likeness(u)
        if ok:
            keep_remap[pos] = len(new_units)
            new_units.append(u)
        else:
            log['dropped_non_english_units'].append({
                'book': book_n, 'refs': pos_to_refs.get(pos, []),
                'first_60_chars': u[:60],
                'density': round(density, 3) if density is not None else None,
                'novowel_frac': round(novowel_frac, 3) if novowel_frac is not None else None,
                'n_tokens': n_tok})

    new_eid_to_pos = {}
    for eid, pos in eid_to_pos.items():
        if pos in keep_remap:
            new_eid_to_pos[eid] = keep_remap[pos]
        # else: the unit this epigram pointed to was dropped -> unmatched
    return new_units, new_eid_to_pos


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    log = {'numeral_repairs': [], 'spurious_markers': [], 'skipped_missing': [],
           'lettered_attached': [], 'duplicate_headings_dropped': [], 'wide_jumps': [],
           'dropped_non_english_units': []}
    repair_counts = Counter()

    report_rows = []
    all_per_book_units = {}
    all_per_book_eid_to_pos = {}
    all_expected = {}

    for vol in VOLUMES:
        per_book_units, per_book_eid_to_pos, expected_per_book = process_volume(vol, log)
        all_per_book_units.update(per_book_units)
        all_per_book_eid_to_pos.update(per_book_eid_to_pos)
        all_expected.update(expected_per_book)

    grand_expected = 0
    grand_matched = 0
    for book_n in range(1, 17):
        expected = all_expected[book_n]
        greek_refs = load_greek_refs(book_n)
        units = all_per_book_units[book_n]
        eid_to_pos = all_per_book_eid_to_pos[book_n]  # epigram id -> unit position, this book only
        units, eid_to_pos = clean_book_units(
            book_n, units, eid_to_pos, greek_refs, repair_counts, log)

        ref_to_unit = {}
        n_translated_refs = 0
        pairs_for_check = []
        # group greek lines by epigram id for the name check
        greek_by_eid = {}
        for ref, gtext in greek_refs:
            eid = epigram_id_of(ref)
            greek_by_eid.setdefault(eid, []).append(gtext)
            pos = eid_to_pos.get(eid)
            if pos is None:
                continue
            ref_to_unit[ref] = pos
            n_translated_refs += 1

        for eid in expected:
            pos = eid_to_pos.get(eid)
            if pos is None:
                continue
            gtext = ' '.join(greek_by_eid.get(eid, []))
            if gtext and pos < len(units):
                pairs_for_check.append((gtext, units[pos]))

        n_refs = len(greek_refs)
        coverage = n_translated_refs / n_refs if n_refs else 0.0
        name_hit, name_n = PN.score(pairs_for_check, 'grc')
        lengths = [(len(g), len(t)) for g, t in pairs_for_check if g and t]
        corr = None
        if len(lengths) >= 10:
            xs = [a for a, b in lengths]
            ys = [b for a, b in lengths]
            n = len(xs)
            mx, my = sum(xs) / n, sum(ys) / n
            num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
            dx = sum((a - mx) ** 2 for a in xs) ** 0.5
            dy = sum((b - my) ** 2 for b in ys) ** 0.5
            if dx and dy:
                corr = num / (dx * dy)

        mean_span = 0
        if units:
            used_positions = set(eid_to_pos.values())
            mean_span = n_translated_refs / max(1, len(used_positions))

        if coverage >= 0.95 and (corr is None or corr >= 0.5):
            conf = 'high'
        elif coverage >= 0.90:
            conf = 'medium'
        elif coverage >= 0.5:
            conf = 'low'
        else:
            conf = 'very low'
        verified_by = 'names' if (name_hit is not None and name_n >= 10) else (
            'length' if corr is not None else None)

        out = {
            'tess_work': f'grc/anthologia_graeca.part.{book_n}',
            'language': 'grc',
            'n_tess_refs': n_refs,
            'n_translated': n_translated_refs,
            'coverage': round(coverage, 4),
            'mean_source_lines_per_translation_unit': round(mean_span, 2),
            'alignment_confidence': conf,
            'name_check_hit_rate': (round(name_hit, 3) if name_hit is not None else None),
            'name_check_n': name_n,
            'length_correlation': (round(corr, 3) if corr is not None else None),
            'verified_by': verified_by,
            'sources': [{
                'translator': 'W. R. Paton',
                'year': BOOK_YEAR[book_n],
                'title': f'The Greek Anthology, Book {ROMAN[book_n]} '
                         f'(Loeb Classical Library)',
                'publisher': 'William Heinemann / G. P. Putnam\'s Sons',
                'mode': 'epigram',
                'ref_composition': ['epigram'],
                'source_url': 'https://archive.org/details/greekanthology01pato',
            }],
            'license': 'Public domain in the United States (published 1916-1918).',
            'attribution': 'W. R. Paton (1916-1918), Loeb Classical Library, via archive.org',
            'n_units_stored': len(units),
            'units': units,
            'ref_to_unit': ref_to_unit,
        }
        fn = os.path.join(OUT_DIR, f'grc__anthologia_graeca.part.{book_n}.json')
        json.dump(out, open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

        report_rows.append({
            'book': book_n, 'n_epigrams_greek': len(expected),
            'n_epigrams_matched': len({eid_to_pos[e] for e in expected if e in eid_to_pos}),
            'n_refs': n_refs, 'n_translated_refs': n_translated_refs,
            'coverage': round(coverage, 4), 'name_hit': name_hit, 'name_n': name_n,
            'length_corr': corr, 'confidence': conf,
        })
        grand_expected += n_refs
        grand_matched += n_translated_refs

    print('%-6s %10s %10s %9s %10s %10s %8s %10s' % (
        'book', 'epigrams', 'matched', 'coverage', 'name_hit', 'name_n', 'len_r', 'conf'))
    for r in report_rows:
        print('%-6d %10d %10d %8.1f%% %10s %10d %8s %10s' % (
            r['book'], r['n_epigrams_greek'], r['n_epigrams_matched'],
            100 * r['coverage'], ('%.3f' % r['name_hit']) if r['name_hit'] is not None else 'n/a',
            r['name_n'], ('%.3f' % r['length_corr']) if r['length_corr'] is not None else 'n/a',
            r['confidence']))
    print()
    print('TOTAL refs: %d/%d matched (%.2f%%)' % (
        grand_matched, grand_expected, 100 * grand_matched / grand_expected))
    print('numeral repairs:', len(log['numeral_repairs']))
    print('lettered epigrams attached to base:', len(log['lettered_attached']))
    print('spurious markers (unmatched found headings):', len(log['spurious_markers']))
    print('epigrams never matched (real gaps):', len(log['skipped_missing']))
    print('non-English units dropped:', len(log['dropped_non_english_units']))
    print('first-word small-caps repairs, by replacement:')
    for word, repl in FIRST_WORD_REPAIRS.items():
        c = repair_counts.get(word, 0)
        if c:
            print('   %-10s -> %-8s  %d' % (word, repl, c))
    zero = [w for w in FIRST_WORD_REPAIRS if not repair_counts.get(w, 0)]
    if zero:
        print('   (0 occurrences):', ', '.join(zero))

    log['first_word_repairs'] = {w: repair_counts.get(w, 0) for w in FIRST_WORD_REPAIRS}
    json.dump(log, open(os.path.join(HERE, 'align_anthologia_graeca_log.json'), 'w'),
               ensure_ascii=False, indent=1)
    json.dump(report_rows, open(os.path.join(HERE, 'align_anthologia_graeca_report.json'), 'w'),
               ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
