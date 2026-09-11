#!/usr/bin/env python3
"""Prudentius' Liber Cathemerinon, from R. Martin Pope's 1905 verse translation.

WHY THIS ONE NEEDED ITS OWN SCRIPT

The Cathemerinon (twelve hymns, 1,745 lines in our .tess text) has no English
in Perseus. Pope's translation (Project Gutenberg 14959, London: J. M. Dent &
Co., 1905) is the only easily available public-domain English verse rendering,
and it translates hymn by hymn, stanza by stanza, printing the Latin text
first and the English immediately after it for each hymn in turn -- not
interleaved line by line, and not carrying our reference numbers at all.

WHY THE ALIGNMENT IS STANZA-EXACT RATHER THAN SEARCHED

The Cathemerinon is stanzaic throughout (four-line iambic dimeric stanzas in
most hymns, five in III and VII, six in IV, three in IX), and Pope preserves
that structure: his Gutenberg text prints the SAME NUMBER of stanzas in the
same order for the Latin and the English half of every one of the twelve
hymns. That makes the alignment a positional zip -- Latin stanza N in reading
order pairs with English stanza N in reading order -- rather than a search
over candidate compositions.

The Latin half also carries the editor's own apparatus: a line number set off
by two or more spaces at the end of every fifth verse line (`...victimam.
5`), which is what a critical edition prints in the margin. Those markers are
used to recover the ACTUAL Latin line number of every stanza, rather than
just counting lines from the top of the hymn -- because hymn VII has one.

THE ONE REAL GAP: HYMN VII, LINES 116-125

Pope's Latin prints a row of asterisks at that point (`*   *   *   *   *`)
between the stanza ending "...alvi capacis vivus hauritur specu." (our line
115) and the stanza beginning "Intactus exin tertiae noctis vice..." (our
line 126), and his own line-number markers jump straight from 115 to 130 --
his edition simply does not have the ten lines our .tess text carries there
(Jonah lingering, then vomited up, inside the fish). Our text is not
defective: those ten lines were restored by manuscripts Pope's 1905 edition
did not use. Pope draws the same gap in his English, with his own row of
asterisks at the matching point, so the stanza counts either side of it still
match -- but those ten lines get no English, honestly, because none exists in
this source. This is the only shortfall against 100% coverage in the whole
work.

THE ONE THING TO WATCH ON PARSING

The Gutenberg text also carries, right after Hymn XII's English, a thirteenth
poem -- the "EPILOGUS" / "EPILOGUE" -- that is NOT part of the Cathemerinon in
our .tess file (which stops at Hymn XII, line 208) and must not be read into
Hymn XII's stanza list. It is excluded by stopping Hymn XII's English block at
the EPILOGUS heading rather than at the NOTES section that follows the
Epilogue; the earlier boundary (before this was noticed) silently pulled the
Epilogue AND part of Pope's prose Introduction into "Hymn XII", nearly
doubling its apparent English text.

WHAT IS STILL CHECKED

The same two tests the rest of this pipeline uses, for the same reason: wrong
English beside right Latin is invisible to the reader who needs the English.
Proper names, and the correlation between Latin stanza length and English
stanza length. Computed once globally (this is a single small work) and
reported per hymn as well.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

SRC = os.environ.get('TESSERAE_PRUDENTIUS_SRC',
                     os.path.expanduser('~/perseus_trans/prudentius_src/pg14959.txt'))
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/la'
OUT = os.environ.get('TESSERAE_PRUDENTIUS_OUT',
                     os.path.expanduser('~/perseus_trans/translations_prudentius'))

WORK = 'prudentius.cathemerinon'

# (hymn number, Latin heading exactly as printed, English heading exactly as printed)
HYMNS = [
    (1, 'I. HYMNUS AD GALLI CANTUM', 'I. HYMN AT COCK-CROW'),
    (2, 'II. HYMNUS MATUTINUS', 'II. MORNING HYMN'),
    (3, 'III. HYMNUS ANTE CIBUM', 'III. HYMN BEFORE MEAT'),
    (4, 'IV. HYMNUS POST CIBUM', 'IV. HYMN AFTER MEAT'),
    (5, 'V. HYMNUS AD INCENSUM LUCERNAE', 'V. HYMN FOR THE LIGHTING OF THE LAMPS'),
    (6, 'VI. HYMNUS ANTE SOMNUM', 'VI. HYMN BEFORE SLEEP'),
    (7, 'VII. HYMNUS IEIUNANTIUM', 'VII. HYMN FOR THOSE WHO FAST'),
    (8, 'VIII. HYMNUS POST IEIUNIUM', 'VIII. HYMN AFTER FASTING'),
    (9, 'IX. HYMNUS OMNIS HORAE', 'IX. HYMN FOR ALL HOURS'),
    (10, 'X. HYMNUS AD EXEQUIAS DEFUNCTI', 'X. HYMN FOR THE BURIAL OF THE DEAD'),
    (11, 'XI. HYMNUS VIII. KALENDAS IANUARIAS', 'XI. HYMN FOR CHRISTMAS-DAY'),
    (12, 'XII. HYMNUS EPIPHANIAE', 'XII. HYMN FOR THE EPIPHANY'),
]

# Hymn XII's English is followed immediately by a thirteenth poem, the
# Epilogus/Epilogue, which is not part of the Cathemerinon in our .tess file
# and must not be swept into Hymn XII's stanza list. See module docstring.
EPILOGUS_HEADING = 'EPILOGUS'

NAME_FLOOR = 0.20
CORR_FLOOR = 0.30
LICENSE = ('Public domain. R. Martin Pope, The Hymns of Prudentius '
           '(London: J. M. Dent & Co., 1905); text from Project Gutenberg '
           '14959, with the Project Gutenberg header and licence removed.')

# A marker is a Latin critical-edition line number: a run of digits at the end
# of a line, set off from the verse by two or more spaces, the same
# convention Miller's Seneca used. Only ever applied to the Latin half.
MARKER = re.compile(r'^(.*?)\s{2,}(\d{1,4})\s*$')
# A row of three or more asterisks marks an editorial lacuna and is treated
# as a stanza break, not as text.
LACUNA = re.compile(r'^\s*(\*\s*){3,}$')


def find_one(lines, heading):
    hits = [i for i, l in enumerate(lines) if l.strip() == heading]
    if len(hits) != 1:
        raise SystemExit(f'expected exactly one heading {heading!r}, found {len(hits)}')
    return hits[0]


def segments(block_lines, is_latin):
    """Split a block into stanzas at blank lines and lacuna rows.

    Each stanza is a list of (raw_stripped, marker_or_None, text_without_marker).
    """
    segs, cur = [], []
    for raw in block_lines:
        s = raw.rstrip('\n')
        if s.strip() == '' or LACUNA.match(s):
            if cur:
                segs.append(cur)
                cur = []
            continue
        m = MARKER.match(s) if is_latin else None
        if m:
            cur.append((s.strip(), int(m.group(2)), m.group(1).strip()))
        else:
            cur.append((s.strip(), None, s.strip()))
    if cur:
        segs.append(cur)
    return segs


def resolve_latin_stanzas(segs):
    """[(start_line, end_line, [text lines])], using markers to fix each
    stanza's true starting line number rather than trusting contiguous count.

    Any marker inside a stanza is trusted over the running count from the
    previous stanza -- that is what lets Hymn VII's gap self-correct: the
    first stanza after the lacuna carries a marker of its own (130 on its
    fifth line) and that alone fixes its start at 126, four lines discovered
    to be missing rather than assumed present.
    """
    out = []
    running = 0
    for seg in segs:
        markers = [(i, mval) for i, (_, mval, _) in enumerate(seg) if mval is not None]
        if markers:
            i0, m0 = markers[0]
            start = m0 - i0
            for i, mv in markers[1:]:
                if start + i != mv:
                    print(f'   ! marker disagreement within one stanza: {seg}')
        else:
            start = running + 1
        texts = [t for _, _, t in seg]
        end = start + len(texts) - 1
        out.append((start, end, texts))
        running = end
    return out


def corr(pairs):
    xs = [len(a) for a, b in pairs if a and b]
    ys = [len(b) for a, b in pairs if a and b]
    n = len(xs)
    if n < 10:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None


def load_tess(path):
    """{hymn: {line: ref}} for every <prud. cath. H.L> reference."""
    out = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'^<prud\. cath\. (\d+)\.(\d+)>', line)
            if not m:
                continue
            h, l = int(m.group(1)), int(m.group(2))
            out.setdefault(h, {})[l] = f'prud. cath. {h}.{l}'
    return out


def main():
    if not os.path.exists(SRC):
        raise SystemExit(f'source text not found: {SRC}')
    lines = open(SRC, encoding='utf-8', errors='replace').read().split('\n')

    lat_idx = {n: find_one(lines, lh) for n, lh, eh in HYMNS}
    eng_idx = {n: find_one(lines, eh) for n, lh, eh in HYMNS}
    epilogus_idx = find_one(lines, EPILOGUS_HEADING)

    path = f'{TESS}/{WORK}.tess'
    if not os.path.exists(path):
        raise SystemExit(f'.tess file not found: {path}')
    tess = load_tess(path)

    def latin_end(n):
        return eng_idx[n]

    def english_end(n):
        return epilogus_idx if n == 12 else lat_idx[n + 1]

    os.makedirs(OUT, exist_ok=True)
    units, idx, ref2u = [], {}, {}
    all_pairs = []
    per_hymn_report = []
    n_tess_refs = sum(len(v) for v in tess.values())
    n_translated = 0

    print(f"{'hymn':4s} {'lat lines':>9s} {'stanzas':>8s} {'matched':>8s} "
          f"{'covered':>8s} {'cov':>6s}  note")

    for n, lat_head, eng_head in HYMNS:
        lat_block = lines[lat_idx[n] + 1: latin_end(n)]
        eng_block = lines[eng_idx[n] + 1: english_end(n)]
        lat_segs = segments(lat_block, True)
        eng_segs = segments(eng_block, False)
        lat_stanzas = resolve_latin_stanzas(lat_segs)

        hymn_lines = tess.get(n, {})
        hymn_total = len(hymn_lines)

        if len(lat_stanzas) != len(eng_segs):
            # No natural fallback boundary exists in this source below "whole
            # hymn"; the whole hymn becomes one unit rather than guessing at
            # a stanza correspondence the source does not actually give us.
            eng_text = '\n'.join(
                t for seg in eng_segs for _, _, t in seg).strip()
            covered = 0
            if eng_text:
                if eng_text not in idx:
                    idx[eng_text] = len(units)
                    units.append(eng_text)
                for l, ref in hymn_lines.items():
                    ref2u[ref] = idx[eng_text]
                    covered += 1
            lat_all = '\n'.join(t for s, e, txts in lat_stanzas for t in txts)
            all_pairs.append((lat_all, eng_text))
            n_translated += covered
            note = 'STANZA COUNT MISMATCH -- fell back to whole-hymn unit'
            print(f'{n:4d} {hymn_total:9d} {len(lat_stanzas):8d} {len(eng_segs):8d} '
                  f'{covered:8d} {covered / hymn_total if hymn_total else 0:6.3f}  {note}')
            per_hymn_report.append({'hymn': n, 'granularity': 'hymn',
                                    'lines': hymn_total, 'covered': covered,
                                    'coverage': round(covered / hymn_total, 4) if hymn_total else 0})
            continue

        covered = 0
        gap_lines = 0
        for (start, end, lat_texts), eng_seg in zip(lat_stanzas, eng_segs):
            eng_text = '\n'.join(t for _, _, t in eng_seg).strip()
            lat_text = '\n'.join(lat_texts).strip()
            if not eng_text:
                continue
            if eng_text not in idx:
                idx[eng_text] = len(units)
                units.append(eng_text)
            u = idx[eng_text]
            for l in range(start, end + 1):
                ref = hymn_lines.get(l)
                if ref is None:
                    continue
                ref2u[ref] = u
                covered += 1
            all_pairs.append((lat_text, eng_text))
        matched_lines = sum(e - s + 1 for s, e, _ in lat_stanzas)
        gap_lines = hymn_total - matched_lines
        note = '' if gap_lines == 0 else f'{gap_lines} Latin lines absent from Pope\'s source text'
        cov = covered / hymn_total if hymn_total else 0
        n_translated += covered
        print(f'{n:4d} {hymn_total:9d} {len(lat_stanzas):8d} {len(eng_segs):8d} '
              f'{covered:8d} {cov:6.3f}  {note}')
        per_hymn_report.append({'hymn': n, 'granularity': 'stanza',
                                'lines': hymn_total, 'stanzas': len(lat_stanzas),
                                'covered': covered, 'coverage': round(cov, 4),
                                'gap_lines': gap_lines})

    coverage = n_translated / n_tess_refs if n_tess_refs else 0
    hit, n_names = V.score(all_pairs, 'la', sample=1200)
    r = corr(all_pairs)
    verified_by = 'names' if (hit is not None and n_names >= 25) else 'length correlation'
    ok = (hit is not None and n_names >= 25 and hit >= NAME_FLOOR) or (r is not None and r >= CORR_FLOOR)
    confidence = 'high' if (coverage >= 0.98 and ((hit or 0) >= 0.35 or (r or 0) >= 0.6)) else 'medium'

    print(f"\noverall: {n_translated}/{n_tess_refs} lines covered "
          f"({coverage:.4f}), {len(units)} stored units, "
          f"name-check {hit} (n={n_names}), length corr {r}")
    if not ok:
        print('VERIFICATION FAILED -- refusing to write output')
        json.dump(per_hymn_report, open(f'{OUT}/report.json', 'w'), indent=1, ensure_ascii=False)
        raise SystemExit(1)

    out_doc = {
        'tess_work': f'la/{WORK}', 'language': 'la',
        'n_tess_refs': n_tess_refs, 'n_translated': n_translated,
        'coverage': round(coverage, 4),
        'mean_source_lines_per_translation_unit': round(n_translated / len(units), 1) if units else None,
        'alignment_confidence': confidence,
        'name_check_hit_rate': round(hit, 3) if hit is not None else None,
        'name_check_n': n_names,
        'length_correlation': round(r, 3) if r is not None else None,
        'verified_by': verified_by,
        'sources': [{'translator': 'R. Martin Pope', 'year': 1905,
                     'title': 'The Hymns of Prudentius',
                     'publisher': 'J. M. Dent & Co.',
                     'mode': 'stanza', 'ref_composition': ['hymn', 'line'],
                     'source_url': 'https://www.gutenberg.org/ebooks/14959'}],
        'license': LICENSE,
        'attribution': 'R. Martin Pope (1905), via Project Gutenberg',
        'n_units_stored': len(units), 'units': units, 'ref_to_unit': ref2u,
    }
    out_path = f'{OUT}/la__{WORK}.json'
    json.dump(out_doc, open(out_path, 'w'), ensure_ascii=False)
    json.dump(per_hymn_report, open(f'{OUT}/report.json', 'w'), indent=1, ensure_ascii=False)
    print(f'wrote {out_path}')


if __name__ == '__main__':
    main()
