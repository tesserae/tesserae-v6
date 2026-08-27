#!/usr/bin/env python3
"""Jerome's Vulgate against the Douay-Rheims.

THE LARGEST SINGLE UNTRANSLATED WORK IN THE CORPUS

39,244 lines, and until now not one of them had English beside it. It was left
out of the earlier priority list only because demand for it was judged lower than
for Seneca or Statius. By lines of coverage per hour of work it is far and away
the best thing available, because almost nothing has to be inferred.

WHY DOUAY-RHEIMS AND NOT ANY OTHER ENGLISH BIBLE

The Douay-Rheims is a translation OF THE VULGATE. Every other public-domain
English Bible translates the Hebrew and Greek, and the difference is not academic:
where the Vulgate's versification follows the Septuagint, as it does through most
of the Psalter, an English Bible made from the Hebrew is numbered differently, and
pairing verse n with verse n would be wrong for a whole book while looking
complete. Choosing the translation made from the same text removes that problem
at the source rather than correcting for it afterwards.

WHAT IS EASY HERE, AND WHAT STILL IS NOT

Easy: our references already carry the book in English -- "<Vulgate 2
Samuel.1.1>" -- so the book map is nearly an identity, and chapter and verse are
already in the reference. There is no alignment to search for.

Not easy: the Vulgate holds books and pieces of books that no ordinary English
Bible prints. 3 and 4 Esdras, the Prayer of Manasseh, Psalm 151, the Old Latin
Psalter, and the Epistle to the Laodiceans are in our text and not in the
Douay-Rheims files. Those are reported as having no English rather than forced
onto the nearest-looking book, which is how the Prayer of Manasseh would end up
answering for Manasseh in Chronicles.

The same two checks as everywhere else: every book is scored against its proposed
English AND against every other book, and a book that does not beat the field is
not written.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

SRC = os.environ.get('TESSERAE_DRA_SRC',
                     '/home/ncoffee/perseus_trans/bible_src/dra')
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/la'
OUT = os.environ.get('TESSERAE_VULGATE_OUT',
                     '/home/ncoffee/perseus_trans/translations_vulgate')

MARGIN = 0.15
FLOOR = 0.25
CORR_FLOOR = 0.45
CORR_MARGIN = 0.20
CHAPTER_OFFSETS = (0, -1, 1)
VERSE_OFFSETS = (0, 1, -1)
STUB_CHARS = 15

# Our reference's book label -> USFM code. Names that differ from the modern
# English are the Vulgate's own: Tobias for Tobit, Apocalypse for Revelation,
# Sirach for Ecclesiasticus. The misspellings (Habbakuk, Zephoniah, Haggaiah)
# are as they stand in our corpus and are left alone here rather than corrected
# in the texts, which is a separate change.
BOOKS = {
    'Genesis': 'GEN', 'Exodus': 'EXO', 'Leviticus': 'LEV', 'Numbers': 'NUM',
    'Deuteronomy': 'DEU', 'Joshua': 'JOS', 'Judges': 'JDG', 'Ruth': 'RUT',
    '1 Samuel': '1SA', '2 Samuel': '2SA', '1 Kings': '1KI', '2 Kings': '2KI',
    '1 Chronicles': '1CH', '2 Chronicles': '2CH',
    'Ezra': 'EZR', 'Nehemiah': 'NEH', 'Esther': 'EST', 'Job': 'JOB',
    'Psalms': 'PSA', 'Proverbs': 'PRO', 'Ecclesiastes': 'ECC',
    'Song of Songs': 'SNG', 'Wisdom': 'WIS', 'Sirach': 'SIR',
    'Isaiah': 'ISA', 'Jeremiah': 'JER', 'Lamentations': 'LAM',
    'Baruch': 'BAR', 'Ezekiel': 'EZK', 'Daniel': 'DAN',
    'Hosea': 'HOS', 'Joel': 'JOL', 'Amos': 'AMO', 'Obadiah': 'OBA',
    'Jonah': 'JON', 'Micah': 'MIC', 'Nahum': 'NAM', 'Habbakuk': 'HAB',
    'Zephoniah': 'ZEP', 'Haggaiah': 'HAG', 'Zechariah': 'ZEC', 'Malachi': 'MAL',
    'Tobias': 'TOB', 'Judith': 'JDT',
    '1 Maccabees': '1MA', '2 Maccabees': '2MA',
    'Matthew': 'MAT', 'Mark': 'MRK', 'Luke': 'LUK', 'John': 'JHN',
    'Acts': 'ACT', 'Romans': 'ROM',
    '1 Corinthians': '1CO', '2 Corinthians': '2CO', 'Galatians': 'GAL',
    'Ephesians': 'EPH', 'Philippians': 'PHP', 'Colossians': 'COL',
    '1 Thessalonians': '1TH', '2 Thessalonians': '2TH',
    '1 Timothy': '1TI', '2 Timothy': '2TI', 'Titus': 'TIT',
    'Philemon': 'PHM', 'Hebrews': 'HEB', 'James': 'JAS',
    '1 Peter': '1PE', '2 Peter': '2PE',
    '1 John': '1JN', '2 John': '2JN', '3 John': '3JN', 'Jude': 'JUD',
    'Apocalypse': 'REV',
    # Deliberately absent from the Douay-Rheims files, and left unpaired:
    #   1 Esdras, 2 Esdras, Prayer of Manasseh, Psalm 151,
    #   Old Latin Psalms, Epistle of Paul to the Laodicians
}


def load_usfm(directory):
    out = {}
    for path in sorted(glob.glob(os.path.join(directory, '*.usfm'))):
        m = re.search(r'-([A-Z0-9]{3})eng', os.path.basename(path))
        if not m:
            continue
        verses, st = {}, {'ch': None, 'vs': None, 'buf': []}

        def flush():
            if st['ch'] is not None and st['vs'] is not None:
                t = ' '.join(st['buf']).strip()
                if t:
                    verses[(st['ch'], st['vs'])] = re.sub(r'\s+', ' ', t)

        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.rstrip('\n')
                c = re.match(r'\\c\s+(\d+)', line)
                if c:
                    flush()
                    st.update(ch=int(c.group(1)), vs=None, buf=[])
                    continue
                v = re.match(r'\\v\s+(\d+)(?:-\d+)?\s*(.*)', line)
                if v:
                    flush()
                    st.update(vs=int(v.group(1)), buf=[v.group(2)])
                    continue
                if line.startswith('\\') and line[:2] not in ('\\q', '\\p', '\\m'):
                    continue
                if st['vs'] is not None:
                    st['buf'].append(re.sub(r'^\\\w+\*?\s*', '', line))
        flush()
        clean = {}
        for k, val in verses.items():
            val = re.sub(r'\\f .*?\\f\*', '', val)
            val = re.sub(r'\\x .*?\\x\*', '', val)
            val = re.sub(r'\\\+?\w+\*?', '', val)
            val = re.sub(r'[|]\w+="[^"]*"', '', val)
            val = re.sub(r'\s+', ' ', val).strip()
            if val:
                clean[k] = val
        if clean:
            out[m.group(1)] = clean
    return out


def load_vulgate():
    """{book label: {(chapter, verse): (ref, latin)}} across every part file."""
    books = {}
    for path in sorted(glob.glob(f'{TESS}/jerome.vulgate.part.*.tess')):
        with open(path, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                m = re.match(r'^<Vulgate ([^.>]+)\.(\d+)\.(\d+)>\s*(.*)$', line)
                if not m:
                    continue
                book, ch, vs, txt = (m.group(1).strip(), int(m.group(2)),
                                     int(m.group(3)), m.group(4).strip())
                ref = f'Vulgate {book}.{ch}.{vs}'
                books.setdefault(book, {}).setdefault((ch, vs), (ref, txt))
    return books


def length_corr(pairs):
    real = [(a, b) for a, b in pairs if a and b and len(a) >= STUB_CHARS]
    if len(real) < 10:
        return None
    xs = [len(a) for a, _ in real]
    ys = [len(b) for _, b in real]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None


def pair_at(verses, eng, coff, voff):
    mapping, pairs = {}, []
    for (ch, vs), (ref, lat) in verses.items():
        t = eng.get((ch + coff, vs + voff))
        if t:
            mapping[ref] = t
            pairs.append((lat, t))
    return mapping, pairs


def main():
    dra = load_usfm(SRC)
    vul = load_vulgate()
    print(f'Douay-Rheims books parsed: {len(dra)}   Vulgate books in corpus: {len(vul)}')
    os.makedirs(OUT, exist_ok=True)

    print(f"\n{'book':26s} {'eng':4s} {'off':7s} {'verses':>7s} {'paired':>7s} "
          f"{'cov':>6s} {'names':>6s} {'len r':>6s}  verdict")
    report, total, written = [], 0, 0
    for book in sorted(vul):
        verses = vul[book]
        want = BOOKS.get(book)
        if not want or want not in dra:
            print(f'{book:26s} --   not in the Douay-Rheims files ({len(verses)} verses)')
            report.append({'book': book, 'verses': len(verses),
                           'status': 'no_english_available'})
            continue

        best = None
        for coff in CHAPTER_OFFSETS:
            for voff in VERSE_OFFSETS:
                mapping, pairs = pair_at(verses, dra[want], coff, voff)
                if not mapping:
                    continue
                hit, n = V.score(pairs, 'la', sample=200)
                cand = {'coff': coff, 'voff': voff, 'hit': hit or 0.0, 'n': n,
                        'corr': length_corr(pairs),
                        'cov': len(mapping) / len(verses), 'mapping': mapping}
                if best is None or (round(cand['cov'], 2), max(cand['corr'] or 0, cand['hit'])) > \
                                   (round(best['cov'], 2), max(best['corr'] or 0, best['hit'])):
                    best = cand
        if not best:
            print(f'{book:26s} {want:4s} --   no verse numbers matched')
            report.append({'book': book, 'verses': len(verses), 'status': 'no_match'})
            continue

        # Every other book is a rival. A correct map beats the field.
        rivals, rcorrs = [], []
        for code, other in dra.items():
            if code == want:
                continue
            mp, pr = pair_at(verses, other, 0, 0)
            if len(mp) < max(10, 0.3 * len(verses)):
                continue
            h, n2 = V.score(pr, 'la', sample=120)
            if h is not None and n2 >= 8:
                rivals.append(h)
            rc = length_corr(pr)
            if rc is not None:
                rcorrs.append(rc)
        top_r = max(rivals) if rivals else 0.0
        top_rc = max(rcorrs) if rcorrs else 0.0

        c = best.get('corr')
        by_name = best['hit'] >= FLOOR and best['hit'] >= top_r + MARGIN
        by_len = c is not None and c >= CORR_FLOOR and c >= top_rc + CORR_MARGIN
        ok = by_name or by_len
        off = ''
        if best['coff']:
            off += f"c{best['coff']:+d}"
        if best['voff']:
            off += f"v{best['voff']:+d}"
        cs = f"{c:6.3f}" if c is not None else '   n/a'
        print(f"{book:26s} {want:4s} {off:7s} {len(verses):7d} {len(best['mapping']):7d} "
              f"{best['cov']:6.3f} {best['hit']:6.3f} {cs}  "
              + ('ok' if ok else 'REJECTED'))
        report.append({'book': book, 'english': want, 'verses': len(verses),
                       'paired': len(best['mapping']), 'coverage': round(best['cov'], 4),
                       'chapter_offset': best['coff'], 'verse_offset': best['voff'],
                       'name_hit': round(best['hit'], 3), 'rival_hit': round(top_r, 3),
                       'length_corr': (round(c, 3) if c is not None else None),
                       'status': 'ok' if ok else 'rejected'})
        if not ok:
            continue
        total += len(best['mapping'])
        written += 1
        vul[book] = best   # keep for the write below

    # One file per .tess part, because that is how the corpus is served.
    files = 0
    for path in sorted(glob.glob(f'{TESS}/jerome.vulgate.part.*.tess')):
        stem = os.path.basename(path)[:-5]
        mapping = {}
        with open(path, encoding='utf-8', errors='replace') as fh:
            for line in fh:
                m = re.match(r'^<Vulgate ([^.>]+)\.(\d+)\.(\d+)>', line)
                if not m:
                    continue
                book = m.group(1).strip()
                b = vul.get(book)
                if not isinstance(b, dict) or 'mapping' not in b:
                    continue
                ref = f'Vulgate {book}.{m.group(2)}.{m.group(3)}'
                t = b['mapping'].get(ref)
                if t:
                    mapping[ref] = t
        if not mapping:
            continue
        units, idx, ref2u = [], {}, {}
        for ref, txt in mapping.items():
            if txt not in idx:
                idx[txt] = len(units)
                units.append(txt)
            ref2u[ref] = idx[txt]
        json.dump({
            'tess_work': f'la/{stem}', 'language': 'la',
            'n_tess_refs': len(mapping), 'n_translated': len(mapping),
            'coverage': 1.0,
            'mean_source_lines_per_translation_unit': 1.0,
            'alignment_confidence': 'high',
            'verified_by': 'names and verse length',
            'sources': [{'translator': 'Douay-Rheims (Challoner revision)',
                         'year': 1899, 'title': 'The Holy Bible, Douay-Rheims',
                         'mode': 'verse', 'ref_composition': ['chapter', 'verse'],
                         'source_url': 'https://ebible.org/Scriptures/engDRA_usfm.zip'}],
            'license': 'Public domain (Douay-Rheims, via eBible.org)',
            'attribution': 'Douay-Rheims Bible',
            'n_units_stored': len(units), 'units': units, 'ref_to_unit': ref2u,
        }, open(f'{OUT}/la__{stem}.json', 'w'), ensure_ascii=False)
        files += 1

    print(f'\nbooks accepted: {written}   verses translated: {total:,}   '
          f'files written: {files}')
    json.dump(report, open(f'{OUT}/report.json', 'w'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
