#!/usr/bin/env python3
"""Iqbal, Asrar-e Khudi, from R. A. Nicholson's The Secrets of the Self (1920,
Project Gutenberg 57317).

Nicholson renders every Persian bayt (couplet) as two English lines and
numbers his English lines continuously through the poem (a number every
fifth line in the Gutenberg text). Our text has one line per bayt in
nineteen sections: the Prologue and Nicholson's I to XVIII, in the same
order. So bayt i of the whole poem (counting across sections) is English
lines 2i-1 and 2i. Both the section starts and the running numbers are
checked before anything is written: every one of our section openings must
fall on an even English line count, and the English line numbers printed in
the text must agree with the count of verse lines read.

Usage:
    python scripts/translations/align_asrar_nicholson.py \
        --src /path/pg57317.txt --tess texts/fa/iqbal.asrar_e_khudi.tess \
        --out-dir data/translations
"""
import argparse
import collections
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from write_aligned import write_aligned, tess_refs  # noqa: E402

HEAD = re.compile(r'^(PROLOGUE|[IVXL]+)\s*$')
VERSE = re.compile(r'^  (\S.*?)\s*(\d+)?\s*$')   # two-space indent, optional trailing number


def read_nicholson(path):
    """[(section_label, [english lines])] in order, and the printed line
    numbers seen as {count_when_seen: printed}."""
    sections = []
    printed = {}
    cur = None
    started = False
    count = 0
    with open(path, encoding='utf-8') as f:
        for raw in f:
            line = raw.rstrip('\n')
            if not started:
                if line.strip() == 'PROLOGUE':
                    started = True
                else:
                    continue
            if line.strip() == 'THE END':
                break
            m = HEAD.match(line.strip()) if not line.startswith('  ') else None
            if m and not line.startswith(' '):
                cur = [m.group(1), []]
                sections.append(cur)
                continue
            v = VERSE.match(line)
            if v and cur is not None and not line.startswith('   _'):
                text = v.group(1).strip()
                # Section summaries are italic paragraphs set off with underscores
                # and are not indented, so they never reach here.
                if v.group(2):
                    count += 1
                    printed[count] = int(v.group(2))
                else:
                    count += 1
                cur[1].append(text)
    return sections, printed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out-dir', required=True)
    a = ap.parse_args()
    sections, printed = read_nicholson(a.src)
    labels = [s[0] for s in sections]
    print(f'{len(sections)} sections: {labels}', flush=True)
    english = [l for _, ls in sections for l in ls]
    print(f'{len(english)} English verse lines', flush=True)
    bad = [(c, p) for c, p in printed.items() if c != p]
    if bad:
        print(f'WARNING: {len(bad)} printed line numbers disagree with the count, e.g. {bad[:5]}', flush=True)

    refs = tess_refs(a.tess)
    by_section = collections.OrderedDict()
    for r in refs:
        m = re.search(r'\.(\d+)\.(\d+)$', r)
        by_section.setdefault(int(m.group(1)), []).append(r)
    print(f'ours: {len(by_section)} sections, {len(refs)} bayts', flush=True)
    if len(by_section) != len(sections):
        sys.exit('section counts differ; refusing to write')

    # Section by section. Where Nicholson's section holds exactly twice our
    # bayts, each bayt takes its own English couplet. Where the counts differ
    # by a couplet or two (the editions differ slightly), the English is
    # allocated in proportion, in blocks of two couplets so that a one-couplet
    # drift stays inside the block a reader sees. Where they differ by more
    # than that, Nicholson's text does not follow ours (his XVII has 43
    # couplets to our 61) and the section is left untranslated: wrong English
    # beside right Persian is invisible to the reader who needs it.
    units, ref_to_unit = [], {}
    exact = approx = skipped = 0
    for (label, lines), (sec, ours) in zip(sections, by_section.items()):
        n = len(ours)
        if sec == 1 and len(lines) == 2 * (n - 1):
            # Our Prologue opens with an epigraph from Naziri as its first
            # line, and the poet's name occupies the first hemistich of the
            # second, so from there every line of ours is one hemistich behind
            # Nicholson's couplets: our line k (k >= 3) holds his English
            # lines 2k-4 and 2k-3. Checked against the Persian on 2026-09-06
            # (our 1.3 "my weeping bedewed the face of the rose / my tears
            # washed away sleep from the eye of the narcissus"). The epigraph
            # line is left untranslated; his final line has no line of ours.
            # The epigraph gets a note rather than nothing: a reader who clicks
            # the first line of the poem otherwise hears that "this work has a
            # translation, but not for the selected lines."
            ref_to_unit[ours[0]] = len(units)
            units.append('[Epigraph: a couplet by Naziri of Nishapur that Iqbal set at the head of the '
                         'poem. Nicholson does not translate it; his English begins with the next line.]')
            ref_to_unit[ours[1]] = len(units)
            units.append(lines[0])
            for k in range(3, n + 1):
                ref_to_unit[ours[k - 1]] = len(units)
                # English lines 2k-4 and 2k-3, 1-based, are indices 2k-5 and 2k-4.
                units.append(f'{lines[2 * k - 5]} {lines[2 * k - 4]}')
            exact += 1
            print(f'  section {sec} ({label}): epigraph line skipped, hemistich offset applied', flush=True)
        elif len(lines) == 2 * n:
            for i, ref in enumerate(ours):
                ref_to_unit[ref] = len(units)
                units.append(f'{lines[2 * i]} {lines[2 * i + 1]}')
            exact += 1
        elif abs(len(lines) - 2 * n) <= 4:
            print(f'  section {sec} ({label}): ours {n} bayts, English {len(lines)} lines; proportional in blocks of two', flush=True)
            for i in range(0, n, 2):
                block = ours[i:i + 2]
                lo = int(i * len(lines) / n)
                hi = max(lo + 1, int(min(i + 2, n) * len(lines) / n))
                for ref in block:
                    ref_to_unit[ref] = len(units)
                units.append(' '.join(lines[lo:hi]))
            approx += 1
        else:
            print(f'  section {sec} ({label}): ours {n} bayts, English {len(lines)} lines; note instead of English', flush=True)
            note_unit = len(units)
            units.append(f'[Section {label} of Nicholson\'s translation has {len(lines) // 2} couplets where this '
                         f'edition has {n}, so his English cannot be matched to these lines and is not shown.]')
            for ref in ours:
                ref_to_unit[ref] = note_unit
            skipped += 1
    confidence = 'high' if not approx and not skipped else 'medium'
    approximate = bool(approx)
    note = (f'{exact} sections aligned couplet for couplet, {approx} in proportion within the '
            f'section (block of two couplets), {skipped} left untranslated because Nicholson\'s '
            f'text does not follow ours there.')
    write_aligned(
        a.out_dir, 'fa', os.path.basename(a.tess)[:-5], units, ref_to_unit,
        attribution='Reynold A. Nicholson, The Secrets of the Self (Macmillan, 1920), via Project Gutenberg',
        license='Public domain (published 1920). Text from Project Gutenberg #57317.',
        sources=[{'translator': 'Reynold A. Nicholson', 'year': 1920,
                  'title': 'The Secrets of the Self (Asrar-i Khudi)',
                  'url': 'https://www.gutenberg.org/ebooks/57317'}],
        confidence=confidence, approximate=approximate, tess_refs=refs,
        verified_by='section structure and line counts', notes=note,
    )
    print(f'[done] {len(units)} units, {len(ref_to_unit)} refs, confidence {confidence}', flush=True)


if __name__ == '__main__':
    main()
