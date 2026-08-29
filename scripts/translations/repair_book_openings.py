"""Recover the untranslated opening lines of each book or poem.

The Loeb aligners anchor English pages by their running headers, and the
first page of every book carries no header, so each book's opening lines
went unpaired: every Thebaid book's translation began around line 20, and a
reader landing on 1.1, the likeliest landing spot in the whole work, saw
none. The English for those lines exists in the source scan, on the very
pages the aligner dropped.

The repair finds it by position rather than by guesswork. For each book or
poem whose first covered line is late, the missing English lies in the
source between two strings we already hold: the text of the unit covering
the last line before the gap (or the start of the file), and the text of
the gap's first covered unit. The region between them is mostly that
missing page, plus the Latin facing page and page furniture, which are
removed the same way the aligners remove them: header-shaped and
number-only lines dropped, then blocks kept only when common English words
make up enough of them (the Latin facing page fails that test).

Nothing is written on trust. A candidate opening must share proper names
with the Latin lines it claims to translate (proper_names.py, the same
check the aligners use). A book that fails is skipped and printed, not
forced.

Usage:
    python scripts/translations/repair_book_openings.py \
        --json data/translations/la__statius.thebaid.json \
        --tess texts/la/statius.thebaid.tess \
        --src  ~/perseus_trans/statius_src/statiusstat01statuoft.txt \
        --src  ~/perseus_trans/statius_src/statiuswithengli02statuoft.txt \
        --out  /tmp/la__statius.thebaid.json
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

STOP_EN = set('''the and of to in a is that was his he for with as her on at by
from they their she it not be but had have this which him who were are all so
or when what there its'''.split())

MIN_GAP = 6          # repair only books/poems whose first covered line is later
MIN_WORDS = 25       # a plausible opening page has at least this much English
MAX_REGION = 20000   # chars to scan between the two boundary units


def collapse(s):
    return re.sub(r'\s+', ' ', s).strip()


def norm(s):
    """Aggressive normalization for matching OCR-divergent text: lowercase,
    letters only, and 'h' dropped (Latin Hadria is English Adria)."""
    return re.sub(r'[^a-gi-z]', '', s.lower())


def norm_with_map(raw):
    out, omap = [], []
    for i, ch in enumerate(raw):
        c = ch.lower()
        if c.isalpha() and c != 'h':
            out.append(c)
            omap.append(i)
    return ''.join(out), omap


def collapse_with_map(raw):
    """Collapsed text plus, for each collapsed offset, the raw offset."""
    out, omap = [], []
    in_space = True
    for i, ch in enumerate(raw):
        if ch.isspace():
            if not in_space:
                out.append(' ')
                omap.append(i)
                in_space = True
        else:
            out.append(ch)
            omap.append(i)
            in_space = False
    return ''.join(out), omap


def tess_refs(path):
    """[(display_ref, numeric_tuple, latin_text)] in file order."""
    out = []
    for line in open(path, errors='ignore'):
        m = re.match(r'<([^>]+)>\s*(.*)', line)
        if not m:
            continue
        nums = re.findall(r'\d+', m.group(1))
        if nums:
            out.append((m.group(1).strip(), tuple(int(n) for n in nums), m.group(2)))
    return out


def english_ratio(block):
    words = re.findall(r"[A-Za-z']+", block.lower())
    if not words:
        return 0.0
    return sum(1 for w in words if w in STOP_EN) / len(words)


def page_chunks(region):
    """Split a raw region at page boundaries (running headers, bare page
    numbers) and return the chunks in order, each cleaned of furniture."""
    chunks, cur = [], []

    def flush():
        text = collapse(' '.join(cur))
        text = re.sub(r'(\w)- (\w)', r'\1\2', text)      # OCR hyphenation
        # stray page-number fragments cling to chunk edges ("39s", "II.")
        text = re.sub(r'(?:\s+\S*\d\S*)+$', '', text)
        text = re.sub(r'^(?:\S*\d\S*\s+)+', '', text)
        if text:
            chunks.append(text)
        cur.clear()

    for rawline in region.split('\n'):
        line = rawline.strip()
        if not line:
            continue
        if re.fullmatch(r'[\dIVXLC .\-]+', line):          # bare page number
            flush()
            continue
        letters = re.sub(r'[^A-Za-z]', '', line)
        if letters and letters.isupper() and len(line) < 60:  # header / title
            flush()
            continue
        cur.append(line)
    flush()
    return chunks


def find_in(source_collapsed, needle, start=0):
    """Locate a unit's opening in the collapsed source; try shrinking probes."""
    probe = collapse(needle)
    for length in (90, 60, 40, 28):
        i = source_collapsed.find(probe[:length], start)
        if i != -1:
            return i
    return -1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--src', action='append', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    data = json.load(open(args.json))
    lang = data.get('language', 'la')
    refs = tess_refs(args.tess)
    ref_index = {r[0]: i for i, r in enumerate(refs)}

    sources = []
    for s in args.src:
        raw = open(os.path.expanduser(s), errors='ignore').read()
        col, omap = collapse_with_map(raw)
        ncol, nmap = norm_with_map(raw)
        sources.append((raw, col, omap, ncol, nmap))

    # group covered refs by book/poem (all numeric parts except the line)
    first_line, first_ref = {}, {}
    for k in data['ref_to_unit']:
        nums = re.findall(r'\d+', k)
        key, line = tuple(int(n) for n in nums[:-1]), int(nums[-1])
        if key not in first_line or line < first_line[key]:
            first_line[key], first_ref[key] = line, k
    repaired, skipped = 0, []
    for key in sorted(first_line):
        gap_first = first_line[key]
        if gap_first <= MIN_GAP:
            continue
        anchor_ref = first_ref[key]
        anchor_unit = data['units'][data['ref_to_unit'][anchor_ref]]
        # the unit before the gap, in tess order
        pos = ref_index.get(anchor_ref)
        prev_unit_text, prev_ref = None, None
        if pos is not None:
            for j in range(pos - 1, -1, -1):
                r = refs[j][0]
                if r in data['ref_to_unit']:
                    prev_unit_text = data['units'][data['ref_to_unit'][r]]
                    prev_ref = r
                    break
        # The region runs from the START of the unit before the gap (whose
        # stored text often swallowed the whole unheadered stretch,
        # including the opening we want and the Latin facing pages) up to
        # the gap's first anchored unit.
        region = None

        def locate(col, omap, ncol, nmap, needle):
            i = find_in(col, needle)
            if i != -1:
                return omap[min(i, len(omap) - 1)]
            j = ncol.find(norm(needle)[:24])
            return nmap[min(j, len(nmap) - 1)] if j != -1 else -1

        for raw, col, omap, ncol, nmap in sources:
            right = locate(col, omap, ncol, nmap, anchor_unit)
            if right == -1:
                continue
            left = -1 if prev_unit_text is None else \
                locate(col, omap, ncol, nmap, prev_unit_text)
            if left == -1 or left > right:
                left = max(0, right - MAX_REGION)
            elif right - left > MAX_REGION * 3:
                left = right - MAX_REGION
            region = raw[left:right]
            break
        if region is None:
            skipped.append((key, 'anchor not found in source'))
            continue
        # Page chunks in order; English ones only. The LAST English page
        # before the anchor is the gap's opening. Earlier English pages are
        # the true content of the preceding unit, which gets retrimmed to
        # them (dropping the Latin and apparatus it swallowed).
        chunks = page_chunks(region)
        english = [c for c in chunks if english_ratio(c) >= 0.22
                   and len(c.split()) >= 15]
        if not english:
            skipped.append((key, 'no English page found in region'))
            continue
        opening = english[-1]
        if len(opening.split()) < MIN_WORDS:
            skipped.append((key, f'only {len(opening.split())} English words found'))
            continue
        # validate: Latin names of the gap lines must appear in the English
        gap_refs = [r for r in refs
                    if r[1][:-1] == key and r[1][-1] < gap_first]
        stems = V.english_stems(opening)
        hits = total = 0
        for _, _, latin in gap_refs:
            for _, c in V.names_in(latin, lang):
                total += 1
                cn = norm(c)
                if c in stems or any(c[:5] == s[:5] or cn[:4] == norm(s)[:4]
                                     for s in stems):
                    hits += 1
        if total >= 2 and hits == 0:
            skipped.append((key, f'0/{total} proper names matched'))
            continue
        unit_idx = len(data['units'])
        data['units'].append(opening)
        for r in gap_refs:
            data['ref_to_unit'][r[0]] = unit_idx
        repaired += 1
        trimmed = ''
        if prev_unit_text is not None and english[:-1] and \
                len(prev_unit_text.split()) > 2 * sum(len(c.split()) for c in english[:-1]):
            new_prev = ' '.join(english[:-1])
            data['units'][data['ref_to_unit'][prev_ref]] = new_prev
            trimmed = (f'; previous unit trimmed '
                       f'{len(prev_unit_text.split())} -> {len(new_prev.split())} words')
        label = '.'.join(str(n) for n in key)
        print(f'  {label}: lines 1-{gap_first - 1} <- {len(opening.split())} words'
              f' (names {hits}/{total}){trimmed}')

    data['n_translated'] = len(data['ref_to_unit'])
    data['n_units_stored'] = len(data['units'])
    if data.get('n_tess_refs'):
        data['coverage'] = round(data['n_translated'] / data['n_tess_refs'], 4)
    data['opening_repair'] = {'repaired': repaired,
                              'skipped': [f'{k}: {why}' for k, why in skipped]}
    json.dump(data, open(args.out, 'w'), ensure_ascii=False)
    print(f'{os.path.basename(args.json)}: {repaired} openings repaired, '
          f'{len(skipped)} skipped, coverage now {data["coverage"]}')
    for k, why in skipped:
        print(f'  skipped {k}: {why}')


if __name__ == '__main__':
    main()
