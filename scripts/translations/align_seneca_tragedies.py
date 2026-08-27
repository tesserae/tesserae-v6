#!/usr/bin/env python3
"""Seneca's ten tragedies, from Frank Justus Miller's translation.

WHY THIS ONE NEEDED ITS OWN SCRIPT

Seneca's tragedies were the largest canonical Latin gap in the corpus with no
English at all: 12,033 lines across ten plays, and Perseus carries a translation
of none of them. They are also the corner of the corpus that scholars search
hardest, because Flavian and Elizabethan intertextual work runs straight through
them.

The source is Frank Justus Miller's translation (Project Gutenberg 57999, the
1907 Chicago edition; Miller went on to do the Loeb). Public domain in the US by
publication date and clear in the EU too, Miller having died in 1938.

WHY THE ALIGNMENT IS EXACT RATHER THAN APPROXIMATE

This is the rare case where the two sides were built for each other without
either knowing it.

Our .tess files do not number Seneca line by line. They number in FIVE-LINE
BLOCKS: `<sen. oed. 200-4>` covers Latin 200 to 204. Miller, following the
convention for a verse translation, prints the LATIN line number in the margin
every five lines. So his marker 200 opens exactly the stretch of English that
renders our block 200-4, and the alignment is one block to one block with nothing
to search for.

That the markers really are Latin line numbers, and not a count of English
verses, is not assumed. For every one of the ten plays the highest marker is
exactly four less than our highest block start -- 1060 against 1064 in Oedipus,
1995 against 1999 in Hercules Oetaeus -- and the marker count matches our block
count to within a handful. An English-line count would run half again as long.

WHAT IS STILL CHECKED

The same two tests the rest of this pipeline uses, for the same reason: wrong
English beside right Latin is invisible to the reader who needs the English.
Proper names, and the correlation between Latin block length and English block
length. A play that fails both is not written.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

SRC = os.environ.get('TESSERAE_SENECA_SRC',
                     '/home/ncoffee/perseus_trans/seneca_src/pg57999.txt')
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/la'
OUT = os.environ.get('TESSERAE_SENECA_OUT',
                     '/home/ncoffee/perseus_trans/translations_seneca')

# Heading as Miller prints it, and our work. The line number is found by search
# rather than hard-coded, so a re-download with different front matter still works.
PLAYS = [
    ('OEDIPUS', 'seneca.oedipus'),
    ('PHOENISSAE, OR THEBAÏS', 'seneca.phoenissae'),
    ('MEDEA', 'seneca.medea'),
    ('HERCULES FURENS', 'seneca.hercules_furens'),
    ('HIPPOLYTUS OR PHAEDRA', 'seneca.phaedra'),
    ('HERCULES OETAEUS', 'seneca.hercules_oetaeus'),
    ('THYESTES', 'seneca.thyestes'),
    ('TROADES', 'seneca.troades'),
    ('AGAMEMNON', 'seneca.agamemnon'),
    ('OCTAVIA', 'seneca.octavia'),
]

NAME_FLOOR = 0.25
CORR_FLOOR = 0.45
LICENSE = ('Public domain. Frank Justus Miller, The Tragedies of Seneca '
           '(Chicago, 1907); text from Project Gutenberg 57999, with the '
           'Project Gutenberg header and licence removed.')

# A marker is a run of digits at the end of a line, set off by whitespace from
# the verse. Two spaces or more, so a line ending in a numeral of its own
# ("threescore and 10") cannot be mistaken for one.
MARKER = re.compile(r'^(.*?)\s{2,}(\d{1,4})\s*$')


def play_bounds(lines):
    """First body line of each play. The heading appears twice, in the contents
    and again over the play, so we take the LAST standalone occurrence."""
    at = {}
    for i, line in enumerate(lines):
        s = line.strip()
        for head, _ in PLAYS:
            if s == head:
                at[head] = i + 1
    return at


def blocks_for_play(body):
    """{latin line number: English rendering it opens}.

    A marker sits on the English line that renders the Latin line it names, so a
    block runs from its own marked line up to, but not including, the next
    marked line.
    """
    marked = []
    for i, line in enumerate(body):
        m = MARKER.match(line)
        if m:
            marked.append((i, int(m.group(2)), m.group(1)))
    out = {}
    for j, (i, n, first) in enumerate(marked):
        stop = marked[j + 1][0] if j + 1 < len(marked) else len(body)
        chunk = [first] + body[i + 1:stop]
        txt = '\n'.join(c.rstrip() for c in chunk).strip()
        txt = re.sub(r'\n{3,}', '\n\n', txt)
        if txt:
            out[n] = txt
    return out


def load_tess_blocks(path):
    """{block start: (full ref, joined Latin)} for a five-line-block work."""
    refs = {}
    order = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'^<([^>]*)>\s*(.*)$', line)
            if not m:
                continue
            ref, txt = m.group(1).strip(), m.group(2).strip()
            n = re.search(r'(\d+)-\d+\s*$', ref)
            if not n:
                continue
            start = int(n.group(1))
            if start not in refs:
                refs[start] = [ref, []]
                order.append(start)
            refs[start][1].append(txt)
    return {k: (v[0], ' '.join(v[1])) for k, v in refs.items()}, order


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
    lines = open(SRC, encoding='utf-8').read().split('\n')
    at = play_bounds(lines)
    missing = [h for h, _ in PLAYS if h not in at]
    if missing:
        raise SystemExit(f'headings not found in the source: {missing}')
    starts = sorted(at.values())
    os.makedirs(OUT, exist_ok=True)

    print(f"{'play':22s} {'blocks':>7s} {'paired':>7s} {'cov':>6s} "
          f"{'names':>6s} {'len r':>6s}  verdict")
    written = total = 0
    report = []
    for head, work in PLAYS:
        begin = at[head]
        after = [s for s in starts if s > begin]
        body = lines[begin:(after[0] if after else len(lines))]
        eng = blocks_for_play(body)

        path = f'{TESS}/{work}.tess'
        if not os.path.exists(path):
            print(f'{work:22s} -- no .tess file')
            continue
        tess, order = load_tess_blocks(path)

        mapping, pairs = {}, []
        for start, (ref, latin) in tess.items():
            # Exactly one marker per five-line block, at the block's own start.
            txt = eng.get(start)
            if txt is None:
                # Miller occasionally sets the marker a line early or late where
                # a speech breaks; accept the nearest marker inside the block.
                for d in (1, 2, 3, 4, -1):
                    if start + d in eng:
                        txt = eng[start + d]
                        break
            if txt:
                mapping[ref] = txt
                pairs.append((latin, txt))

        cov = len(mapping) / len(tess) if tess else 0
        hit, n = V.score(pairs, 'la', sample=300)
        r = corr(pairs)
        ok = (hit is not None and hit >= NAME_FLOOR) or (r is not None and r >= CORR_FLOOR)
        rs = f'{r:6.3f}' if r is not None else '   n/a'
        hs = f'{hit:6.3f}' if hit is not None else '   n/a'
        print(f'{work:22s} {len(tess):7d} {len(mapping):7d} {cov:6.3f} {hs} {rs}  '
              f"{'ok' if ok else 'REJECTED'}")
        report.append({'work': work, 'blocks': len(tess), 'paired': len(mapping),
                       'coverage': round(cov, 4),
                       'name_hit': (round(hit, 3) if hit is not None else None),
                       'name_n': n, 'length_corr': (round(r, 3) if r is not None else None),
                       'status': 'ok' if ok else 'rejected'})
        if not ok:
            continue

        units, idx, ref2u = [], {}, {}
        for ref, txt in mapping.items():
            if txt not in idx:
                idx[txt] = len(units)
                units.append(txt)
            ref2u[ref] = idx[txt]
        json.dump({
            'tess_work': f'la/{work}', 'language': 'la',
            'n_tess_refs': len(tess), 'n_translated': len(mapping),
            'coverage': round(cov, 4),
            # Our refs ARE five-line blocks, so one reference gets one block of
            # English. The Reader is told 5 rather than 1 because that is how
            # many Latin lines the English beside it actually covers.
            'mean_source_lines_per_translation_unit': 5.0,
            'alignment_confidence': 'high',
            'name_check_hit_rate': (round(hit, 3) if hit is not None else None),
            'name_check_n': n,
            'length_correlation': (round(r, 3) if r is not None else None),
            'verified_by': 'names' if (hit is not None and hit >= NAME_FLOOR) else 'block length',
            'sources': [{'translator': 'Frank Justus Miller', 'year': 1907,
                         'title': 'The Tragedies of Seneca',
                         'publisher': 'University of Chicago Press',
                         'mode': 'block', 'ref_composition': ['line block'],
                         'source_url': 'https://www.gutenberg.org/ebooks/57999'}],
            'license': LICENSE,
            'attribution': 'Frank Justus Miller (1907), via Project Gutenberg',
            'n_units_stored': len(units), 'units': units, 'ref_to_unit': ref2u,
        }, open(f'{OUT}/la__{work}.json', 'w'), ensure_ascii=False)
        written += 1
        total += len(mapping)

    print(f'\nplays written: {written}   references translated: {total:,}')
    json.dump(report, open(f'{OUT}/report.json', 'w'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
