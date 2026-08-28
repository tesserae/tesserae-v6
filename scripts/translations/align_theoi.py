#!/usr/bin/env python3
"""Quintus of Smyrna (Way 1913) and Apollonius Rhodius (Seaton 1912), from the
Theoi Classical Texts Library transcriptions.

Theoi prints both translations as paragraphs, each opening with a bracketed
line number: "[559] Now when they had left...". That marker is the whole
alignment, and what it counts differs between the two authors, which is the
trap this script exists to step around:

- Apollonius (Seaton's prose): the markers are GREEK line numbers. Book 4's
  last marker is 1773 against our 1781 Greek lines. A paragraph covers the
  Greek lines from its marker to the next marker minus one, directly.

- Quintus (Way's verse): the markers are WAY'S ENGLISH verse lines. Book 1's
  last marker is 1103 against our 830 Greek lines, the same off-by-a-third
  that the README's Seneca note warns about. Mapping them straight across
  would pair book ends with nothing and drift forty lines by mid-book. So the
  English marker positions are rescaled onto the Greek: the book's English
  length is estimated from its last marker plus the last paragraph's share of
  words, and each marker is mapped proportionally. The units are ~20 Greek
  lines wide, the rescale error measured by the name check is small against
  that, and the name check is the judge of whether this was good enough.

Both works exist twice in the corpus under different names (and, for Quintus,
with slightly different line counts): quintus_smyrnaeus.fall_of_troy /
quintus_smyrnaeus.posthomerica, and apollonius.argonautica /
apollonius_rhodius.argonautica. One alignment is computed per author and
written once per work id, each against that copy's own refs and book lengths.

Nothing is written for a work whose name check and length correlation both
fail (the same floors as align_aristophanes.py, epic being name-rich).

Source pages, cached locally (TESSERAE_THEOI_SRC):
  https://www.theoi.com/Text/QuintusSmyrnaeus{1-14}.html
  https://www.theoi.com/Text/ApolloniusRhodius{1-4}.html
"""
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

SRC = os.environ.get('TESSERAE_THEOI_SRC', '/home/ncoffee/perseus_trans/theoi_src')
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/grc'
OUT = os.environ.get('TESSERAE_THEOI_OUT', '/home/ncoffee/perseus_trans/translations_theoi')

NAME_FLOOR = 0.25
CORR_FLOOR = 0.45

AUTHORS = [
    {
        'pages': [('qs%d.html' % b, b) for b in range(1, 15)],
        'markers': 'english',          # Way's verse line numbers
        'works': ['quintus_smyrnaeus.fall_of_troy', 'quintus_smyrnaeus.posthomerica'],
        'source': {
            'translator': 'A. S. Way', 'year': 1913,
            'title': 'Quintus Smyrnaeus: The Fall of Troy (Loeb Classical Library 19)',
            'publisher': 'William Heinemann',
            'mode': 'paragraph', 'ref_composition': ['book', 'line range'],
            'source_url': 'https://www.theoi.com/Text/QuintusSmyrnaeus1.html',
        },
        'license': ('Public domain in the United States: published 1913. '
                    'Text from the Theoi Classical Texts Library transcription.'),
        'attribution': 'A. S. Way (1913), via theoi.com',
    },
    {
        'pages': [('ar%d.html' % b, b) for b in range(1, 5)],
        'markers': 'greek',            # Seaton's prose is keyed to the Greek
        'works': ['apollonius_rhodius.argonautica', 'apollonius.argonautica'],
        'source': {
            'translator': 'R. C. Seaton', 'year': 1912,
            'title': 'Apollonius Rhodius: Argonautica (Loeb Classical Library 1)',
            'publisher': 'William Heinemann',
            'mode': 'paragraph', 'ref_composition': ['book', 'line range'],
            'source_url': 'https://www.theoi.com/Text/ApolloniusRhodius1.html',
        },
        'license': ('Public domain in the United States: published 1912. '
                    'Text from the Theoi Classical Texts Library transcription.'),
        'attribution': 'R. C. Seaton (1912), via theoi.com',
    },
]

PAR = re.compile(r'<p>\s*\[(\d+)\]\s*(.*?)</p>', re.S)


def clean(fragment):
    t = re.sub(r'<[^>]+>', ' ', fragment)
    t = html.unescape(t)
    return re.sub(r'\s+', ' ', t).strip()


def parse_book(path):
    """[(marker, text)] for one book page, markers strictly increasing."""
    raw = open(path, encoding='utf-8', errors='replace').read()
    pars, last, dropped = [], 0, 0
    for m in PAR.finditer(raw):
        n, text = int(m.group(1)), clean(m.group(2))
        if n <= last:                     # a mistyped marker on theoi's side
            dropped += 1
            continue
        pars.append((n, text))
        last = n
    if dropped:
        print(f'    {os.path.basename(path)}: dropped {dropped} non-monotonic marker(s)')
    return pars


def load_tess(path):
    """{book: {line: (ref, greek)}}"""
    books = {}
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'^<([^>]*)>\s*(.*)$', line)
            if not m:
                continue
            ref = m.group(1).strip()
            bl = re.search(r'(\d+)\.(\d+)\s*$', ref)
            if not bl:
                continue
            books.setdefault(int(bl.group(1)), {})[int(bl.group(2))] = (ref, m.group(2).strip())
    return books


def spans(pars, greek_max, markers):
    """[(g_start, g_end, text)]: the Greek lines each paragraph covers."""
    if markers == 'greek':
        starts = [n for n, _ in pars]
    else:
        # Way's English line numbers, rescaled. His book length is his last
        # marker plus the last paragraph's share, estimated by words per line
        # over the rest of the book.
        last_n = pars[-1][0]
        body_words = sum(len(t.split()) for _, t in pars[:-1])
        wpl = body_words / max(last_n - pars[0][0], 1)
        eng_total = last_n - 1 + max(round(len(pars[-1][1].split()) / max(wpl, 1)), 1)
        scale = greek_max / eng_total
        starts = [max(1, round(1 + (n - 1) * scale)) for n, _ in pars]
        for i in range(1, len(starts)):          # keep strictly increasing
            starts[i] = max(starts[i], starts[i - 1] + 1)
    out = []
    for i, (_, text) in enumerate(pars):
        g0 = starts[i]
        g1 = (starts[i + 1] - 1) if i + 1 < len(pars) else greek_max
        if g1 >= g0:
            out.append((g0, g1, text))
    return out


def align(author):
    per_book = {}
    for fn, book in author['pages']:
        path = os.path.join(SRC, fn)
        if not os.path.exists(path):
            print(f'  missing page: {path}')
            continue
        pars = parse_book(path)
        if pars:
            per_book[book] = pars

    for work in author['works']:
        tess = os.path.join(TESS, work + '.tess')
        books = load_tess(tess)
        mapping = {}
        for book, lines in sorted(books.items()):
            pars = per_book.get(book)
            if not pars:
                continue
            gmax = max(lines)
            for g0, g1, text in spans(pars, gmax, author['markers']):
                for l in range(g0, g1 + 1):
                    if l in lines:
                        ref, greek = lines[l]
                        if ref not in mapping:
                            mapping[ref] = text
        # line-level pairs for the name check, unit-level for the correlation
        name_pairs = [(g, mapping[r]) for b in books.values()
                      for (r, g) in b.values() if r in mapping]
        unit_len = {}
        for b in books.values():
            for r, g in b.values():
                if r in mapping:
                    u = mapping[r]
                    src_len, eng_len = unit_len.get(id(u), (0, len(u)))
                    unit_len[id(u)] = (src_len + len(g), eng_len)
        n_refs = sum(len(b) for b in books.values())
        cov = len(mapping) / n_refs if n_refs else 0
        hit, n = V.score(name_pairs, 'grc', sample=400)
        xs = [a for a, _ in unit_len.values()]
        ys = [b for _, b in unit_len.values()]
        r = corr(xs, ys)
        units = len(set(mapping.values()))
        per = round(len(mapping) / units, 1) if units else 0.0
        ok = (hit is not None and hit >= NAME_FLOOR) or (r is not None and r >= CORR_FLOOR)
        hs = f'{hit:.3f}' if hit is not None else 'n/a'
        rs = f'{r:.3f}' if r is not None else 'n/a'
        print(f'{work:40s} refs={n_refs:5d} paired={len(mapping):5d} cov={cov:.3f} '
              f'names={hs} (n={n}) len_r={rs} lines/unit={per}  '
              + ('ok' if ok else 'REJECTED'))
        if not ok or not mapping:
            continue
        ulist, idx, ref2u = [], {}, {}
        for ref, txt in mapping.items():
            if txt not in idx:
                idx[txt] = len(ulist)
                ulist.append(txt)
            ref2u[ref] = idx[txt]
        os.makedirs(OUT, exist_ok=True)
        json.dump({
            'tess_work': f'grc/{work}', 'language': 'grc',
            'n_tess_refs': n_refs, 'n_translated': len(mapping),
            'coverage': round(cov, 4),
            'mean_source_lines_per_translation_unit': per,
            'alignment_confidence': 'high' if author['markers'] == 'greek' else 'medium',
            'name_check_hit_rate': round(hit, 3) if hit is not None else None,
            'name_check_n': n,
            'length_correlation': round(r, 3) if r is not None else None,
            'verified_by': 'names' if (hit is not None and hit >= NAME_FLOOR) else 'length',
            'sources': [dict(author['source'])],
            'license': author['license'],
            'attribution': author['attribution'],
            'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
        }, open(os.path.join(OUT, f'grc__{work}.json'), 'w'), ensure_ascii=False)


def corr(xs, ys):
    n = len(xs)
    if n < 10:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None


if __name__ == '__main__':
    for a in AUTHORS:
        align(a)
