#!/usr/bin/env python3
"""Aristophanes, from Rogers' Loeb of 1924.

WHAT IS LEFT OF GREEK DRAMA

Aeschylus, Sophocles and Euripides all came in with the Perseus rebuild. Of the
eleven surviving comedies of Aristophanes, Perseus carries an English text of
two. The other nine are 12,000-odd lines with nothing beside them, and a reader
browsing Attic comedy meets a wall of blank tabs where tragedy reads through.

Same source shape as Statius, so the same trick: Rogers' Loeb prints the line
range of every page in its running header, and the Internet Archive scan keeps
it. Three volumes, all 1924 and so US public domain by date of publication:

  aristophanes0001benj  Acharnians, Knights, Clouds, Wasps
  AristophanesVolIi     Peace, Birds, Frogs
  AristophanesVolIii    Lysistrata, Thesmophoriazusae, Ecclesiazusae, Plutus

WHY THIS NEEDED MORE THAN A COPY OF THE STATIUS SCRIPT

The scan is dirtier. Statius' headers came through clean enough to match on the
literal word; these do not. "THE PEACE" is read as "THE PEACH", "LYSISTRATA" as
"LCYSISTRATA", and "THESMOPHORIAZUSAE" arrives in six different spellings across
its forty pages. Matching on the exact string would silently drop a third of the
corpus, and matching on a prefix would confuse nothing here but would be luck
rather than method.

So the play name is matched by similarity, against the eleven titles that are the
only possible answers, with a threshold high enough that a word which is not a
play title matches none of them. The alternative -- a hand-written list of
observed misspellings -- fails on the first misspelling nobody happened to see.

Everything else is as in align_statius: the page's own span decides whether its
header is believable, contiguity supplies a digit only when the span is
impossible, overlapping pages are trimmed, and the pairing is checked by proper
names before anything is written.
"""
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

SRC = os.environ.get('TESSERAE_ARISTOPHANES_SRC',
                     '/home/ncoffee/perseus_trans/aristophanes_src')
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/grc'
OUT = os.environ.get('TESSERAE_ARISTOPHANES_OUT',
                     '/home/ncoffee/perseus_trans/translations_aristophanes')

VOLUMES = ['aristophanes0001benj', 'AristophanesVolIi', 'AristophanesVolIii']

# Loeb page of Aristophanes: twenty-odd lines of comic trimeter.
MIN_SPAN = 10
MAX_SPAN = 45
NAME_FLOOR = 0.20        # comedy names fewer heroes than epic does
CORR_FLOOR = 0.45

# How alike an OCR'd word must be to a play title before we believe it is that
# title. 0.75 accepts PEACH for PEACE and LCYSISTRATA for LYSISTRATA, and
# rejects every other capitalised word in the scan.
TITLE_CUTOFF = 0.75

PLAYS = {
    'ACHARNIANS': 'aristophanes.acharnians',
    'KNIGHTS': 'aristophanes.knights',
    'CLOUDS': 'aristophanes.clouds',
    'WASPS': 'aristophanes.wasps',
    'PEACE': 'aristophanes.peace',
    'BIRDS': 'aristophanes.birds',
    'FROGS': 'aristophanes.frogs',
    'LYSISTRATA': 'aristophanes.lysistrata',
    'THESMOPHORIAZUSAE': 'aristophanes.thesmophoriazusae',
    'ECCLESIAZUSAE': 'aristophanes.ecclesiazusae',
    'PLUTUS': 'aristophanes.plutus',
}

HEADER = re.compile(r'^\s*(?:THE\s+)?([A-Za-z]{4,22})[,.]?\s+'
                    r'(\d{1,4})\s*[-–—]\s*(\d{1,4})\s*$')

EDITORIAL = re.compile(r'(Rogers|see Introduction|\bcf\.|\bibid\b)', re.I)


def match_play(word):
    """The play this OCR'd title word names, or None."""
    hits = difflib.get_close_matches(word.upper(), list(PLAYS), n=1,
                                     cutoff=TITLE_CUTOFF)
    return hits[0] if hits else None


def clean(lines):
    out = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        s = re.sub(r'[*^~]+', '', s)
        out.append(re.sub(r'\s+', ' ', s))
    text = ' '.join(out)
    text = text.replace('- ', '')
    text = re.sub(r'\s+([,.;:?!])', r'\1', text)
    return re.sub(r'\s{2,}', ' ', text).strip()


# A page more Greek than this is the facing original, not the translation.
#
# MEASURED, and the measurement changed the number by a lot. The first guess was
# 0.25, on the reasoning that an English page has no Greek in it. It does: the
# volume II and III scans bleed Greek out of the facing page and out of Rogers'
# footnotes, so genuine English pages sit at 0.23 to 0.33 and the guess was
# throwing away 297 of them -- every page of seven plays. Across all 646 pages
# nothing exceeds 0.4, because the Greek pages carry Greek headers and never
# match the pattern in the first place. So this guard never fires on this scan.
# It is kept, well above the real distribution, for the volume where it would.
GREEK_PAGE = 0.60


def greek_fraction(text):
    """How much of a page is Greek letters. The Loeb sets Greek and English on
    facing pages, and a Greek page taken for the translation would put the
    original beside itself."""
    if not text:
        return 0.0
    g = sum(1 for ch in text if 'Ͱ' <= ch <= 'Ͽ' or 'ἀ' <= ch <= '῿')
    return g / len(text)


def parse_volume(path, volume):
    pages, cur = [], None
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = HEADER.match(line)
            play = match_play(m.group(1)) if m else None
            if play:
                if cur:
                    pages.append(cur[:3] + (clean(cur[3]), volume))
                cur = (play, int(m.group(2)), int(m.group(3)), [])
                continue
            if cur:
                cur[3].append(line)
    if cur:
        pages.append(cur[:3] + (clean(cur[3]), volume))
    return pages


def repair(pages):
    fixed = dropped = editorial = overlaps = greekpages = 0
    out, prev_play, prev_end = [], None, None
    for play, start, end, text, volume in pages:
        if play != prev_play:
            prev_play, prev_end = play, None
        span = end - start + 1
        if not (MIN_SPAN <= span <= MAX_SPAN) and prev_end is not None:
            cand = prev_end + 1
            if MIN_SPAN <= end - cand + 1 <= MAX_SPAN:
                start, span = cand, end - cand + 1
                fixed += 1
        if not (MIN_SPAN <= span <= MAX_SPAN):
            dropped += 1
            continue
        if greek_fraction(text) > GREEK_PAGE:
            greekpages += 1
            continue
        if EDITORIAL.search(text[:400]):
            editorial += 1
            continue
        if prev_end is not None and start <= prev_end:
            overlaps += 1
            start = prev_end + 1
            if start > end:
                dropped += 1
                continue
        out.append((play, start, end, text, volume))
        prev_end = end
    return out, fixed, dropped, editorial, overlaps, greekpages


def load_tess(path):
    refs, greek = {}, {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'^<([^>]*)>\s*(.*)$', line)
            if not m:
                continue
            ref = m.group(1).strip()
            n = re.search(r'(\d+)\s*$', ref)
            if n:
                refs.setdefault(int(n.group(1)), ref)
                greek.setdefault(ref, m.group(2).strip())
    return refs, greek


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


def main():
    pages = []
    for vol in VOLUMES:
        p = f'{SRC}/{vol}.txt'
        if not os.path.exists(p):
            print(f'missing volume: {p}')
            continue
        pages += parse_volume(p, vol)
    print(f'page headers parsed: {len(pages)}')
    pages, fixed, dropped, editorial, overlaps, greekpages = repair(pages)
    print(f'  repaired by contiguity: {fixed}   dropped as unreconcilable: {dropped}'
          f'   Greek pages skipped: {greekpages}   editorial: {editorial}'
          f'   overlaps trimmed: {overlaps}')

    os.makedirs(OUT, exist_ok=True)
    print(f"\n{'play':34s} {'refs':>5s} {'paired':>7s} {'cov':>6s} {'names':>6s} "
          f"{'len r':>6s} {'l/page':>7s}  verdict")
    report, total, written = [], 0, 0
    for title, work in sorted(PLAYS.items(), key=lambda x: x[1]):
        path = f'{TESS}/{work}.tess'
        if not os.path.exists(path):
            print(f'{work:34s} -- no .tess file')
            continue
        refs, greek = load_tess(path)
        mine = [p for p in pages if p[0] == title]
        mapping, pairs, vols = {}, [], []
        for _, start, end, text, volume in mine:
            if volume not in vols:
                vols.append(volume)
            if not text:
                continue
            for ln in range(start, end + 1):
                ref = refs.get(ln)
                if ref and ref not in mapping:
                    mapping[ref] = text
                    pairs.append((greek.get(ref, ''), text))
        cov = len(mapping) / len(refs) if refs else 0
        hit, n = V.score(pairs, 'grc', sample=300)
        r = corr(pairs)
        units = len(set(mapping.values()))
        per = round(len(mapping) / units, 1) if units else 0.0
        ok = (hit is not None and hit >= NAME_FLOOR) or (r is not None and r >= CORR_FLOOR)
        hs = f'{hit:6.3f}' if hit is not None else '   n/a'
        rs = f'{r:6.3f}' if r is not None else '   n/a'
        print(f'{work:34s} {len(refs):5d} {len(mapping):7d} {cov:6.3f} {hs} {rs} '
              f'{per:7.1f}  ' + ('ok' if ok else 'REJECTED'))
        report.append({'work': work, 'refs': len(refs), 'paired': len(mapping),
                       'coverage': round(cov, 4), 'pages': len(mine),
                       'name_hit': (round(hit, 3) if hit is not None else None),
                       'length_corr': (round(r, 3) if r is not None else None),
                       'status': 'ok' if ok else 'rejected'})
        if not ok or not mapping:
            continue
        ulist, idx, ref2u = [], {}, {}
        for ref, txt in mapping.items():
            if txt not in idx:
                idx[txt] = len(ulist)
                ulist.append(txt)
            ref2u[ref] = idx[txt]
        json.dump({
            'tess_work': f'grc/{work}', 'language': 'grc',
            'n_tess_refs': len(refs), 'n_translated': len(mapping),
            'coverage': round(cov, 4),
            'mean_source_lines_per_translation_unit': per,
            'alignment_confidence': 'medium',
            'name_check_hit_rate': (round(hit, 3) if hit is not None else None),
            'name_check_n': n,
            'length_correlation': (round(r, 3) if r is not None else None),
            'verified_by': 'names' if (hit is not None and hit >= NAME_FLOOR) else 'page length',
            'sources': [{'translator': 'B. B. Rogers', 'year': 1924,
                         'title': 'Aristophanes, with an English translation (Loeb)',
                         'publisher': 'William Heinemann / G. P. Putnam',
                         'mode': 'page', 'ref_composition': ['loeb page'],
                         'source_url': ', '.join(
                             f'https://archive.org/details/{v}' for v in vols)}],
            'license': ('Public domain in the United States: published 1924. '
                        'Text from the Internet Archive scan.'),
            'attribution': 'B. B. Rogers (1924), via the Internet Archive',
            'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
        }, open(f'{OUT}/grc__{work}.json', 'w'), ensure_ascii=False)
        written += 1
        total += len(mapping)
    print(f'\nplays written: {written}   lines translated: {total:,}')
    json.dump(report, open(f'{OUT}/report.json', 'w'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
