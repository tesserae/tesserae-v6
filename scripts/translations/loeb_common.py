#!/usr/bin/env python3
"""Shared pieces for the 2026-10-24 exact-numbering batch (Part A).

Every per-work script in this batch ends the same way: a mapping of our
reference to a stretch of English, two checks, and a served file that is written
only if a check vouches for it. That ending, and the cleaning that every OCR'd
Loeb page needs, live here so the nine scripts cannot drift apart.

The two checks are the project's standing pair (README, "Why this is delicate"):
proper names carried across the translation, and the correlation between source
length and English length per unit. A file is refused when neither speaks for it.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

NAME_FLOOR = 0.25
CORR_FLOOR = 0.45

TEXTS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts')
STAGE = os.environ.get('TESSERAE_BATCH_STAGE',
                       os.path.expanduser('~/tesserae-backups/translations_exact_2026-10-24'))
SRC = os.path.join(STAGE, 'src')
OUT = os.path.join(STAGE, 'out')

# A footnote on a scanned Loeb page begins with a marker the OCR renders as one
# stray symbol or a lone letter, then a citation. The test is deliberately
# strict about where the notes start (after a blank gap, in the lower part of
# the page) and loose about what they look like.
CITE = re.compile(r'(\bcf\b|\bCf\b|\bOf\.|\bibid\b|\bi\.e\.|\bHom\b|\bHes\b|\bPind\b|\bHdt\b|'
                  r'\bHerod\b|\bVerg\b|\bOv\b|\bTheocr\b|\bCallim\b|\bLucr\b|\bPlin\b|\bStrabo\b|'
                  r'\bIl\.|\bOd\.|\bid\.|\bAesch\b|\bEur\b|\bSoph\b|\bApollod\b|\bNonn\b|\bHor\b|\bCic\b|'
                  r'\b[ec]f\.|\bAthen\b|\bPlut\b|\bArist\b|\bAelian\b|\bSchol\b|\bsc\.|\bl\. ?c\.|\bLc\.|'
                  r'\bPaus\b|\bStat\b|\bLuc\b|\bSen(?:ec)?\b|\bNic\b|\bPlaut\b|\bGrat+\b|\bMart\b|\bClaud\b)')


COMMON = set('the and of to in a is he his for with that as by on was it be at from her they are which who not '
             'or this their all but had have so when then thou thy thee me my you your we us our them him '
             'she an were has one will would shall may no nor if there now upon'.split())


def english_score(line):
    """Share of a line's words that are very common English words. Body lines
    score 0.3 or more, scan-mangled Greek in a footnote scores near zero."""
    w = re.findall(r"[A-Za-z']+", line.lower())
    if len(w) < 5:
        return 1.0
    return sum(1 for x in w if x in COMMON) / len(w)


def strip_footnotes(lines):
    """Drop the footnote block at the foot of one OCR'd English page.

    Notes follow the body after a gap of one or more blank lines. The last gap
    whose following block is shorter than the body before it and shows citation
    habits (or opens with a stray marker symbol) is the start of the notes.
    """
    blocks, cur = [], []
    for ln in lines:
        if ln.strip():
            cur.append(ln)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    if len(blocks) < 2:
        return [ln for b in blocks for ln in b]
    keep = list(blocks)
    # a printed rule or the folio number sits below the notes
    while len(keep) > 1 and len(' '.join(keep[-1]).strip()) <= 14 \
            and not re.search(r'[A-Za-z]{4}', ' '.join(keep[-1])):
        keep.pop()
    # peel notes blocks off the end while they look like notes
    while len(keep) > 1:
        last = keep[-1]
        text = ' '.join(last)
        first = last[0].strip()
        opens_marked = bool(re.match(r"^[\*\^'\"«»¢®°©†‡§¶~‘’“”\d]{1,3}\s|^[a-d]\s", first))
        cites = len(CITE.findall(text))
        body_len = sum(len(b) for b in keep[:-1])
        if (opens_marked or cites >= 1) and len(last) <= max(8, body_len):
            keep.pop()
        else:
            break
    # the last body block may still end in note lines that ran on without a gap
    tail = list(keep[-1])
    while len(tail) > 3 and (CITE.search(tail[-1]) or english_score(tail[-1]) < 0.1):
        tail.pop()
    keep[-1] = tail
    flat = [ln for b in keep for ln in b]
    return _cut_note_tail(flat)


def _bad_line(line):
    t = line.strip()
    return bool(CITE.search(t) or english_score(t) < 0.12 or
                re.match(r"^[>#@\u00ae\u00a9\u00a2\u00ab\u2020\u2021\u00a7\u00b6\u00b0*\^]\s?\S", t))


def _cut_note_tail(flat):
    """Notes that ran on from the body with no gap: cut at the first line in the
    lower half of the page that is note-like when at least half of everything
    from there to the end is note-like too."""
    n = len(flat)
    bad = [_bad_line(ln) for ln in flat]
    for i in range(n // 2, n):
        if bad[i] and sum(bad[i:]) >= 0.5 * (n - i):
            return flat[:i]
    return flat


def clean_english(lines):
    """One page or one passage of English out of a column of OCR."""
    out = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        s = re.sub(r'[*^~]+', '', s)
        s = re.sub(r'^[_—\-]{1,3}\s+', '', s)        # scan-edge debris at line starts
        s = re.sub(r'\s+', ' ', s)
        out.append(s)
    text = ' '.join(out)
    text = re.sub(r'(\w)- (\w)', r'\1\2', text)           # words broken across scan lines
    text = re.sub(r'\s+([,.;:?!])', r'\1', text)
    text = text.replace('_', '')
    text = re.sub(r'(\s+(?:TRY\s?PHIODORUS|COLLUTHUS|OPPIAN))?(\s+\d{3})\s*[\W_]*$', '', text)   # folio at the foot
    text = re.sub(r'^[^\w\u201c\u2018"\']+', '', text)         # stray marks before the first word
    return re.sub(r'\s{2,}', ' ', text).strip()


def greek_fraction(text):
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if 'Ͱ' <= c <= '῿') / len(letters)


def load_tess(path):
    """[(ref, text)] in file order, one entry per line of the .tess file."""
    out = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'^<([^>]*)>\s*(.*)$', line)
            if m:
                out.append((m.group(1).strip(), m.group(2).strip()))
    return out


def corr(xs, ys):
    n = len(xs)
    if n < 10:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None

# ---------------------------------------------------------------------------
# Footnote text left inside a finished unit
#
# strip_footnotes works on a page of lines. Some notes survive it because the scan
# ran them on from the body with no blank line, or glued them to the last word
# ("wrestlingThessaly"). strip_unit_notes works on the finished unit and removes
# what is left, by four patterns seen in these scans:
#   1. a note number or stray mark after a sentence end, then a capital: "... of
#      Argos. 2 Proetus and his twin-brother ..." or "precinct 1 Poseidon, of ..."
#   2. a lowercase word fused to a capitalised one, where the page foot was
#      joined to the body, in the lower half of the unit
#   3. trailing sentences that cite an edition, a scholar or an ancient work by
#      its siglum (Apost. p. 11, A. 567a10, Cf., [=Coris iulis]) or that are
#      scan-mangled Greek
#   4. stray note marks inside the text (a symbol standing alone, ",?")
# Everything is cut from the first match, never from the middle of a sentence
# of the body, and never from the first half of a unit.
# ---------------------------------------------------------------------------
SCHOLARS = re.compile(
    r'\b(Schneider|Kaibel|Koechly|Hermann|Brunck|Bekker|Hauvette|Dissen|Bergk|Boeckh|Donaldson|'
    r'Mommsen|Freeman|Lobeck|Pfeiffer|Wilamowitz|Welcker|Apost|Ridg|Gildersleeve|Farnell|Mezger|'
    r'Christ|Bury|Mair|Schol|schol|Hiller|Hecker|Ahrens|Meineke|Hephaest|Callim|Plin|Arist|Ael)\b|'
    r'\bMSS?\b|\bcodd?\b|\[=|\b[A-Z]\.\s?\d{3}[a-z]?\s?\d*|\b[ivxl]+\.\s\d+|\bpp?\.\s?[ivxl\d]+|'
    r'\bM\.G\.|\bc?[ec]p\.\s|\bff\.|\b[ec]f\b\.?|\bn\.\s|\bibid|\bl\.\s?c\.')
_NOTE_ANCHOR = re.compile(r'(?<=[.;:!?\u201d\u2019)"a-z,])\s(?:[1-9]\d?|[?!\u00a2\u00ae\u00b0\u00a9\u2020])\s+(?=[A-Z\u201c\u2018])')
_GLUED = re.compile(r'(?<=[a-z])(?=[A-Z][a-z]{3,}[ ,.;])')
_SYMBOLS = re.compile(r'\s?[\u00a2\u00ae\u00b0\u00a9\u2020\u2021\u00a7\u00b6#>]+(?=\s|$|[.,;:])|(?<=[,;:.])\?(?=\s)')
_SENT = re.compile(r'(?<=[.!?\u201d\u2019])\s+(?=[A-Z\u201c\u2018])')


def _note_sentence(sent):
    if CITE.search(sent) or SCHOLARS.search(sent):
        return True
    w = re.findall(r"[A-Za-z']+", sent)
    if len(w) >= 4 and english_score(sent) < 0.12:
        return True
    letters = [c for c in sent if c.isalpha()]
    return len(letters) > 12 and sum(c.isupper() for c in letters) / len(letters) > 0.5


_VOCAB = None


def vocabulary():
    """Words that appear at least twice in the 25 largest installed translation files.
    Scan-mangled Greek in a footnote is made of words that are in no such list."""
    global _VOCAB
    if _VOCAB is None:
        import collections
        import glob
        d = os.environ.get('TESSERAE_TRANS_VOCAB', '/var/www/tesseraev6_flask/data/translations')
        files = sorted(glob.glob(d + '/*.json'), key=os.path.getsize, reverse=True)[:25]
        cnt = collections.Counter()
        for f in files:
            try:
                for u in json.load(open(f)).get('units', []):
                    cnt.update(w.lower() for w in re.findall(r"[A-Za-z]+", u))
            except (OSError, ValueError):
                pass
        _VOCAB = {w for w, c in cnt.items() if c >= 2}
    return _VOCAB


_WORD = re.compile(r"[A-Za-z\u00c0-\u024f\u2019']+")
_MARK = re.compile(r'(?:^|\s)[\u00bb>]\s|\s\d{1,2}\.\s[a-z]|[a-z]\d+[a-z]*\s|\s[A-Z]\.\s[a-z]{3,}\saea')


def _first_cue(text, start):
    """Position of the first sign of a note at or after `start`, and whether it is a
    citation (which may sit inside a quotation, so the cut backs up to a sentence end)."""
    best = None
    for rx, cite in ((SCHOLARS, True), (_MARK, False)):
        m = rx.search(text, start)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), cite)
    vocab = vocabulary()
    words = [(m.start(), m.group(0)) for m in _WORD.finditer(text, start)]
    flags = []
    for pos, w in words:
        lw = w.lower().strip("'\u2019")
        flags.append(len(lw) >= 4 and w[0].islower() and (lw not in vocab or re.search(r'[\u00c0-\u024f]', w) is not None))
    for i in range(len(words) - 5):
        if sum(flags[i:i + 6]) >= 3 and flags[i]:
            if best is None or words[i][0] < best[0]:
                best = (words[i][0], False)
            break
    if best and best[1]:
        # a scan-mangled word just before a citation belongs to the note that began there
        lo = max(start, best[0] - 140)
        for m in _WORD.finditer(text, lo, best[0]):
            w = m.group(0)
            if len(w) >= 5 and w[0].islower() and w.lower().strip("'\u2019") not in vocab:
                best = (m.start(), False)
                break
    return best


def strip_unit_notes(text):
    """Remove footnote residue from one finished unit (see the comment above)."""
    n = len(text)
    half = n // 2
    cut = n
    cue = _first_cue(text, half)
    if cue:
        pos, is_cite = cue
        if is_cite:
            b = max((m.end() for m in re.finditer(r'[.!?\u201d\u2019]\s', text[:pos])), default=0)
            pos = b if b >= 0.4 * n else pos
        cut = min(cut, pos)
    m = _NOTE_ANCHOR.search(text, half)
    if m:
        cut = min(cut, m.start())
    for g in _GLUED.finditer(text, half):
        # fused words in the body are rare, a name after a foot-of-page join is the case seen
        cut = min(cut, g.start())
        break
    text = text[:cut].rstrip()
    sents = _SENT.split(text)
    while len(sents) > 1 and _note_sentence(sents[-1]):
        sents.pop()
    text = ' '.join(sents)
    # a sentence the page broke off in the middle can end in a lone note-ish run
    text = _SYMBOLS.sub('', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


def finish(work, lang, tess_lines, mapping, source, license_text, attribution,
           confidence='medium', name_floor=NAME_FLOOR, corr_floor=CORR_FLOOR,
           unit_sources=None, out_dir=None, clean_notes=False):
    """Run both checks and write the served file if one of them vouches.

    work         our work id, e.g. 'tibullus.elegies'
    tess_lines   [(ref, source text)] from load_tess
    mapping      {ref: english}; refs absent from it are simply unpaired
    clean_notes  True for works whose unit is one scanned page (the notes sit at the end
                 of the unit): strip_unit_notes cuts from the first note anchor to the end.
                 Left False for units that join several pages or come from clean HTML or TEI,
                 where a cut would take body text with it.
    Returns a report dict. Nothing is written for a refused work.
    """
    refs = []
    seen = set()
    src_of = {}
    for ref, txt in tess_lines:
        if ref not in seen:
            seen.add(ref)
            refs.append(ref)
        src_of.setdefault(ref, txt)
    n_refs = len(refs)
    cache = {}
    paired = {}
    for r in refs:
        t = mapping.get(r)
        if not t:
            continue
        if t not in cache:
            cache[t] = strip_unit_notes(t) if clean_notes else t
        if cache[t]:
            paired[r] = cache[t]
    changed = sum(1 for a, b in cache.items() if a != b)
    if changed:
        print(f'    note residue stripped from {changed} of {len(cache)} units')
    cov = len(paired) / n_refs if n_refs else 0.0

    name_pairs = [(src_of[r], t) for r, t in paired.items()]
    hit, n = V.score(name_pairs, lang, sample=400)

    # length correlation per unit: summed source length against English length
    by_unit = {}
    for r, t in paired.items():
        a = by_unit.setdefault(t, [0, len(t)])
        a[0] += len(src_of[r])
    r_len = corr([v[0] for v in by_unit.values()], [v[1] for v in by_unit.values()])

    units = len(by_unit)
    per = round(len(paired) / units, 1) if units else 0.0
    ok = ((hit is not None and hit >= name_floor) or
          (r_len is not None and r_len >= corr_floor)) and bool(paired)
    row = {'work': work, 'refs': n_refs, 'paired': len(paired),
           'coverage': round(cov, 4), 'units': units, 'lines_per_unit': per,
           'name_hit': round(hit, 3) if hit is not None else None, 'name_n': n,
           'length_corr': round(r_len, 3) if r_len is not None else None,
           'status': 'ok' if ok else 'REFUSED'}
    hs = f'{hit:.3f}' if hit is not None else 'n/a'
    rs = f'{r_len:.3f}' if r_len is not None else 'n/a'
    print(f'{work:42s} refs={n_refs:5d} paired={len(paired):5d} cov={cov:.3f} '
          f'names={hs} (n={n}) len_r={rs} units={units} per={per}  {row["status"]}')
    if not ok:
        return row

    ulist, idx, ref2u = [], {}, {}
    for ref in refs:
        t = paired.get(ref)
        if t is None:
            continue
        if t not in idx:
            idx[t] = len(ulist)
            ulist.append(t)
        ref2u[ref] = idx[t]
    d = {
        'tess_work': f'{lang}/{work}', 'language': lang,
        'n_tess_refs': n_refs, 'n_translated': len(paired),
        'coverage': round(cov, 4),
        'mean_source_lines_per_translation_unit': per,
        'alignment_confidence': confidence,
        'name_check_hit_rate': round(hit, 3) if hit is not None else None,
        'name_check_n': n,
        'length_correlation': round(r_len, 3) if r_len is not None else None,
        'verified_by': 'names' if (hit is not None and hit >= name_floor) else 'length',
        'sources': source if isinstance(source, list) else [source],
        'license': license_text, 'attribution': attribution,
        'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
    }
    if unit_sources:
        d['unit_sources'] = unit_sources
    out_dir = out_dir or OUT
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f'{lang}__{work}.json'), 'w') as fh:
        json.dump(d, fh, ensure_ascii=False)
    return row


def save_report(name, rows):
    rdir = os.path.join(STAGE, 'reports')      # not in out/: compact_for_serving.py reads every json there
    os.makedirs(rdir, exist_ok=True)
    with open(os.path.join(rdir, f'report_{name}.json'), 'w') as fh:
        json.dump(rows, fh, indent=1, ensure_ascii=False)
