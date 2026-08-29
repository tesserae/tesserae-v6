"""Jerome, Epistulae: letter+section-exact English from Fremantle's NPNF.

Corpus refs are `<jer. ep. LETTER.SECTION.PARA(.SENT)>` with the standard
(Vallarsi/Hilberg) letter numbering, 154 letters including 18A/18B. The
alignment key is (letter, section): W. H. Fremantle's translation (Nicene
and Post-Nicene Fathers, series 2, volume 6, 1893, public domain) prints
Jerome's own section numbers inline, so each section of English can be
attached to the refs that carry that section number, mode 'exact'.

Source: CCEL's ThML transcription of the volume (npnf206.xml), letters
as <div2 type="Letter" n="ROMAN">. Fremantle's editorial summary precedes
section 1 of every letter and is discarded, never served as translation.

What stays honestly uncovered:
- letters Fremantle omits or abridges past recognition: a letter whose
  parsed section chain misses more than a tenth of the corpus's sections
  for that letter is skipped and printed;
- letters 151-154 (Hilberg's supplement, not in NPNF);
- NPNF letter XVIII against our 18A/18B: Fremantle translates it as one
  letter whose chain matches 18A's sections; 18B is only served if a
  second chain restarting at 1 follows the first.

Corpus section 0 (the salutation Hilberg numbers separately) is served
from the letter's section-1 unit, counted as a merged neighbour.

Usage:
    python scripts/translations/align_jerome.py \
        --xml npnf206.xml --tess texts/la/jerome.epistulae.tess --out out.json
"""
import argparse
import html as htmllib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100}


def roman_to_int(s):
    total, prev = 0, 0
    for ch in reversed(s.strip('. ').upper()):
        v = ROMAN.get(ch)
        if v is None:
            return None
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total or None


SECTION = re.compile(r'(?:(?<=[.!?”’")\]:;])|(?<=^))\s*(\d+)\.\s+'
                     r'(?=[A-Z“‘"(—])')


def sections_of(text):
    """[(chain_index, section_number, text)] — chains of inline section
    numbers; a restart at 1 after a chain of 3+ opens a new chain."""
    marks = []
    prev = 0
    chain = 0
    for m in SECTION.finditer(text):
        n = int(m.group(1))
        if n == prev + 1 or (prev + 1 < n <= prev + 3):
            marks.append((chain, n, m))
            prev = n
        elif n == 1 and prev >= 3:
            chain += 1
            marks.append((chain, 1, m))
            prev = 1
    out = []
    for i, (ch, n, m) in enumerate(marks):
        end = marks[i + 1][2].start() if i + 1 < len(marks) else len(text)
        body = text[m.end():end].strip()
        if len(body.split()) >= 3:
            out.append((ch, n, body))
    return out


def parse_letters(xml_path):
    """{letter_id(str): {section(int): english}}"""
    x = open(xml_path, encoding='utf-8', errors='ignore').read()
    out = {}
    for m in re.finditer(
            r'<div2 type="Letter"[^>]*n="([IVXLC]+)"[^>]*>(.*?)(?=<div2 |<div1 |\Z)',
            x, flags=re.S):
        n = roman_to_int(m.group(1))
        seg = m.group(2)
        seg = re.sub(r'<note place="end".*?</note>', ' ', seg, flags=re.S)
        txt = htmllib.unescape(re.sub(r'<[^>]+>', ' ', seg))
        txt = re.sub(r'\s+', ' ', txt)
        secs = sections_of(txt)
        chains = {}
        for ch, sn, body in secs:
            chains.setdefault(ch, {})[sn] = body
        if not chains:
            continue
        if n == 18:
            out['18A'] = chains.get(0, {})
            if 1 in chains:
                out['18B'] = chains[1]
        else:
            out[str(n)] = chains.get(0, {})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--xml', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    letters = parse_letters(args.xml)
    print(f'{len(letters)} letters with section chains in the NPNF text')

    refs = []
    corpus = {}
    for line in open(args.tess, errors='ignore'):
        m = re.match(r'<(jer\. ep\. ([0-9]+[AB]?)\.(\d+)[^>]*)>\s*(.*)', line)
        if not m:
            continue
        ref, L, s, latin = m.group(1), m.group(2), int(m.group(3)), m.group(4)
        refs.append((ref, L, s, latin))
        corpus.setdefault(L, set()).add(s)

    good, skipped = {}, []
    for L in sorted(corpus, key=lambda k: (len(k), k)):
        want = corpus[L] - {0}
        have = set(letters.get(L, {}))
        missing = want - have
        if not letters.get(L):
            skipped.append((L, 'not in NPNF / no section chain', len(want)))
        elif len(missing) > max(2, len(want) * 0.10):
            skipped.append((L, f'{len(missing)} of {len(want)} sections '
                               f'missing: {sorted(missing)[:8]}', len(want)))
        else:
            good[L] = letters[L]
            if missing:
                print(f'  letter {L}: sections {sorted(missing)} missing '
                      f'in the English, left uncovered')

    units, unit_of, ref_to_unit = [], {}, {}
    merged = 0
    for ref, L, s, _ in refs:
        if L not in good:
            continue
        key = (L, s)
        if s not in good[L]:
            # section 0 is the salutation; its English opens section 1
            if s == 0 and 1 in good[L]:
                key = (L, 1)
                merged += 1
            else:
                continue
        if key not in unit_of:
            unit_of[key] = len(units)
            units.append(good[L][key[1]])
        ref_to_unit[ref] = unit_of[key]
    if merged:
        print(f'  {merged} salutation lines served from section 1')

    # per-letter name guard: a letter pairing the wrong English scores
    # near zero on names and is withdrawn, chain or no chain
    by_letter = {}
    for ref, L, s, latin in refs:
        if ref in ref_to_unit:
            by_letter.setdefault(L, []).append(
                (latin, units[ref_to_unit[ref]]))
    for L, pairs in sorted(by_letter.items()):
        rate, n = V.score(pairs, 'la', sample=120)
        if rate is not None and n >= 10 and rate < 0.25:
            print(f'  letter {L}: name check {rate:.2f} on {n} — WITHDRAWN')
            for ref, LL, s, _ in refs:
                if LL == L:
                    ref_to_unit.pop(ref, None)

    used = sorted(set(ref_to_unit.values()))
    remap = {u: i for i, u in enumerate(used)}
    units = [units[u] for u in used]
    ref_to_unit = {r: remap[u] for r, u in ref_to_unit.items()}

    pairs = [(latin, units[ref_to_unit[ref]])
             for ref, L, s, latin in refs if ref in ref_to_unit]
    score = V.score(pairs, 'la', sample=800)

    out = {
        'tess_work': 'la/jerome.epistulae',
        'language': 'la',
        'n_tess_refs': len(refs),
        'n_translated': len(ref_to_unit),
        'coverage': round(len(ref_to_unit) / len(refs), 4),
        'mean_source_lines_per_translation_unit':
            round(len(ref_to_unit) / max(1, len(units)), 1),
        'alignment_confidence': 'high',
        'name_check_hit_rate': score,
        'name_check_n': score[1],
        'sources': [{
            'title': 'The Principal Works of St. Jerome (NPNF series 2, '
                     'volume 6)',
            'translator': 'W. H. Fremantle, with G. Lewis and W. G. Martley',
            'year': 1893,
            'publisher': 'Christian Literature Company (via CCEL)',
            'source_url': 'https://ccel.org/ccel/schaff/npnf206',
            'mode': 'exact',
            'ref_composition': ['letter', 'section'],
        }],
        'license': 'Public domain: translation published 1893. '
                   'Text from the Christian Classics Ethereal Library.',
        'attribution': 'W. H. Fremantle, G. Lewis and W. G. Martley, '
                       'Nicene and Post-Nicene Fathers series 2 vol. 6 '
                       '(1893), via CCEL',
        'n_units_stored': len(units),
        'units': units,
        'ref_to_unit': ref_to_unit,
    }
    json.dump(out, open(args.out, 'w'), ensure_ascii=False)
    print(f'\ncoverage {out["coverage"]} ({len(ref_to_unit)} of {len(refs)} '
          f'lines), {len(units)} section units, name check {score}')
    for L, why, n in skipped:
        print(f'  SKIPPED letter {L} ({n} sections): {why}')


if __name__ == '__main__':
    main()
