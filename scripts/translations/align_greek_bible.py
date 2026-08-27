#!/usr/bin/env python3
"""Pair the Greek Bible with English, verse by verse, and PROVE the pairing.

The Septuagint and Greek New Testament are the largest block of untranslated
Greek we hold: 29,417 and 7,916 lines. They need no alignment SEARCH at all,
because our reference tags already end in chapter.verse and so does the English.
Verse 1.1 is verse 1.1.

That makes the whole job a book-name map, which is exactly why it is dangerous.
A wrong entry pairs one prophet with another and nothing in the output looks
wrong. Two things are therefore measured rather than assumed:

  * THE BOOK MAP. `abdias` is Obadiah, `sophonias` is Zephaniah, `kritai` is
    Judges, `basileion_g` is 3 Kingdoms which is 1 Kings. Every one of those is
    a guess until proper names in the Greek are found in the English beside it.
    Each book is scored against its proposed English AND against a handful of
    rivals, and a book whose proposed match does not beat every rival is not
    written.

  * THE VERSE NUMBERS. The Septuagint Psalms run one behind the Masoretic
    numbering for most of the Psalter, and the Greek chapter divisions of
    Jeremiah differ wholesale. Where numbering disagrees, pairing verse n with
    verse n is wrong for a whole book and still produces a full-looking file. So
    each book is also tried at a few chapter offsets and the best-scoring one
    wins, with the offset recorded.

WHY BRENTON FOR THE SEPTUAGINT AND THE WEB FOR THE NEW TESTAMENT

Brenton 1851 is a translation OF the Septuagint, so it follows Septuagint
numbering and renders the Greek we actually hold. The World English Bible
translates the Masoretic Hebrew for the Old Testament, which is the wrong text
here, but it is a fine public-domain New Testament. Both are already on disk and
both are already used in production for Coptic.
"""
import collections
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

# Kept OUTSIDE any temp directory. The first run of this pointed at a session
# scratchpad, which was cleaned between sessions and took the sources with it.
SRC = os.environ.get('TESSERAE_BIBLE_SRC', '/home/ncoffee/perseus_trans/bible_src')
BRENTON = f'{SRC}/brenton'
WEB = f'{SRC}/web'
TESS = os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts') + '/grc'
OUT = os.environ.get('TESSERAE_BIBLE_OUT', '/home/ncoffee/perseus_trans/translations_bible')

# Our book name -> USFM code. EVERY ONE OF THESE IS A HYPOTHESIS, checked below.
LXX = {
    'genesis': 'GEN', 'exodus': 'EXO', 'levitikon': 'LEV', 'arithmoi': 'NUM',
    'deuteronomion': 'DEU', 'josue': 'JOS', 'kritai': 'JDG', 'ruth': 'RUT',
    # The four books of Kingdoms are 1-2 Samuel and 1-2 Kings.
    'basileion_a': '1SA', 'basileion_b': '2SA',
    'basileion_g': '1KI', 'basileion_d': '2KI',
    'paralipomenon_i_sive_chronicon_i': '1CH', 'paralipomenon_b': '2CH',
    'esdras_a': '1ES', 'esdras_b': 'EZR',
    'esther': 'ESG', 'judith': 'JDT', 'tobias': 'TOB',
    'machabaeorum_i': '1MA', 'machabaeorum_b': '2MA',
    'machabaeorum_g': '3MA', 'machabaeorum_d': '4MA',
    'psalmi': 'PSA', 'job': 'JOB', 'proverbia': 'PRO',
    'ecclesiastes': 'ECC', 'canticum': 'SNG',
    'sapientia_salomonis': 'WIS', 'ecclesiasticus': 'SIR',
    'osee': 'HOS', 'amos': 'AMO', 'michaeas': 'MIC', 'joel': 'JOL',
    'abdias': 'OBA', 'jonas': 'JON', 'nahum': 'NAM', 'habacuc': 'HAB',
    'sophonias': 'ZEP', 'aggaeus': 'HAG', 'zacharias': 'ZEC',
    'malachias': 'MAL', 'isaias': 'ISA', 'jeremias': 'JER',
    'baruch': 'BAR', 'threni_seu_lamentationes': 'LAM',
    'epistula_jeremiae': 'LJE', 'ezechiel': 'EZK',
    'susanna_theodotionis': 'SUS', 'susanna_translatio_graeca': 'SUS',
    # Brenton prints Theodotion's Daniel, filed under the Greek-Daniel code, so
    # both of our Daniels point at it. Either is a translation of Daniel; the two
    # Greek versions differ but no separate public-domain English of the Old
    # Greek is on hand, and the rival test cannot tell two Daniels apart anyway.
    'daniel_theodotionis': 'DAG', 'daniel_translatio_graeca': 'DAG',
    'bel_et_draco_theodotionis': 'BEL', 'bel_et_draco_translatio_graeca': 'BEL',
}
NT = {
    'mathew': 'MAT', 'mark': 'MRK', 'luke': 'LUK', 'john': 'JHN', 'acts': 'ACT',
    'romans': 'ROM', 'i_corinthinians': '1CO', 'ii_corinthinians': '2CO',
    'galatians': 'GAL', 'ephesians': 'EPH', 'philippians': 'PHP',
    'colossians': 'COL', 'i_thessalonians': '1TH', 'ii_thessalonians': '2TH',
    'i_timothy': '1TI', 'ii_timothy': '2TI', 'titus': 'TIT',
    'philemon': 'PHM', 'hebrews': 'HEB', 'james': 'JAS',
    'i_peter': '1PE', 'ii_peter': '2PE', 'i_john': '1JN', 'ii_john': '2JN',
    'iii_john': '3JN', 'jude': 'JUD', 'revelation': 'REV',
}

# A book must beat every rival by this much before we believe the map.
MARGIN = 0.15
FLOOR = 0.30
# Numbering disagreements come in two shapes and both are systematic.
# CHAPTER: the Septuagint Psalms run one behind the Masoretic for most of the
# Psalter. VERSE: Brenton numbers the superscription of the Epistle of Jeremiah
# as verse 1, which our Greek does not, so every one of its 72 verses is off by
# one. Searching only chapters found the first kind and silently mis-paired the
# second at full coverage, which is the worst way to fail.
CHAPTER_OFFSETS = (0, -1, 1)
VERSE_OFFSETS = (0, 1, -1)

# SECOND OPINION, for the books where proper names run out.
#
# Names are scarce in exactly the books that most need checking. Proverbs scores
# 0.032, Wisdom 0.000, Job 0.122, and none of that means the pairing is wrong: it
# means a wisdom book has almost nobody in it to name. Judged on names alone,
# eleven correct books would have been thrown away.
#
# Verse length settles it without needing a single proper noun. Where the pairing
# is right, a long Greek verse gets a long English one, measured across the book.
# Against the correct English the correlation runs 0.53 to 0.97; against a
# deliberately wrong book it runs -0.15 to 0.34. The floor sits in the gap, and
# the rival must be beaten on this too.
CORR_FLOOR = 0.45
CORR_MARGIN = 0.20

# Below this, one of our lines is not a verse. Our Septuagint Lamentations puts
# each acrostic letter on its own reference line -- 88 of its 150 lines are a
# bare "Ἄλεφ." with the verse body missing -- and pairing five characters of
# Greek against a full English verse drags the correlation to -0.65 for a
# pairing that is in fact correct. A stub is not evidence either way, so it is
# left out of the measurement rather than allowed to decide it.
STUB_CHARS = 15


def load_usfm(directory, tag):
    """USFM to {BOOK: {(chapter, verse): english}}."""
    out = {}
    for path in sorted(glob.glob(os.path.join(directory, '*.usfm'))):
        m = re.search(r'-([A-Z0-9]{3})' + re.escape(tag), os.path.basename(path))
        if not m:
            continue
        book = m.group(1)
        verses, state = {}, {'ch': None, 'vs': None, 'buf': []}

        def flush():
            if state['ch'] is not None and state['vs'] is not None:
                txt = ' '.join(state['buf']).strip()
                if txt:
                    verses[(state['ch'], state['vs'])] = re.sub(r'\s+', ' ', txt)

        with open(path, encoding='utf-8') as fh:
            for line in fh:
                line = line.rstrip('\n')
                c = re.match(r'\\c\s+(\d+)', line)
                if c:
                    flush()
                    state.update(ch=int(c.group(1)), vs=None, buf=[])
                    continue
                v = re.match(r'\\v\s+(\d+)(?:-\d+)?\s*(.*)', line)
                if v:
                    flush()
                    state.update(vs=int(v.group(1)), buf=[v.group(2)])
                    continue
                if line.startswith('\\') and line[:2] not in ('\\q', '\\p', '\\m'):
                    continue
                if state['vs'] is not None:
                    state['buf'].append(re.sub(r'^\\\w+\*?\s*', '', line))
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
            out[book] = clean
    return out


def load_tess(path):
    """{full ref: greek}, keeping the chapter.verse we will align on."""
    refs = collections.OrderedDict()
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = re.match(r'^<([^>]*)>\s*(.*)$', line)
            if not m:
                continue
            ref, txt = m.group(1).strip(), m.group(2).strip()
            if ref not in refs:
                refs[ref] = txt
    return refs


def chapter_verse(ref):
    """The trailing chapter.verse of one of our refs, as ints.

    A one-chapter book carries a bare verse number: the Epistle of Jeremiah runs
    "epistula_jeremiae 1" through "72", with no chapter at all, where the English
    files still key it as chapter 1. Read as chapter 1, or all 72 verses of it go
    unpaired for want of a dot.
    """
    m = re.search(r'(\d+)\.(\d+)\s*$', ref)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.search(r'(?:^|\s)(\d+)\s*$', ref)
    return (1, int(m.group(1))) if m else None


def try_pairing(refs, eng, offset, voffset=0):
    """Pair our refs with English at a chapter and verse offset."""
    pairs, mapping = [], {}
    for ref, gk in refs.items():
        cv = chapter_verse(ref)
        if not cv:
            continue
        txt = eng.get((cv[0] + offset, cv[1] + voffset))
        if txt:
            mapping[ref] = txt
            pairs.append((gk, txt))
    return pairs, mapping


def length_corr(pairs):
    """Do longer Greek verses get longer English? See CORR_FLOOR."""
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


def best_offset(refs, eng):
    """The chapter and verse offset that makes the two texts agree best.

    Coverage alone cannot choose, because an off-by-one verse offset pairs just
    as many verses as the right one and pairs every one of them wrongly. So
    coverage only GATES: an offset that loses much of the book is out, and among
    those that keep it, the evidence decides. Length correlation leads where it
    can be measured, since it works on books with no proper nouns.
    """
    cands = []
    for off in CHAPTER_OFFSETS:
        for voff in VERSE_OFFSETS:
            pairs, mapping = try_pairing(refs, eng, off, voff)
            if not mapping:
                continue
            hit, n = V.score(pairs, 'grc', sample=200)
            cands.append({'offset': off, 'voffset': voff, 'hit': hit or 0.0, 'n': n,
                          'corr': length_corr(pairs),
                          'coverage': len(mapping) / len(refs) if refs else 0,
                          'mapping': mapping})
    if not cands:
        return None
    top_cov = max(c['coverage'] for c in cands)
    pool = [c for c in cands if c['coverage'] >= top_cov - 0.05] or cands
    return max(pool, key=lambda c: (max(c['corr'] or 0.0, c['hit']), c['coverage']))


def run(which, book_map, usfm, tag, prefix, source_label, license_text):
    files = sorted(glob.glob(f'{TESS}/{prefix}.*.tess'))
    print(f'\n{"="*78}\n{which}: {len(files)} files, English from {source_label}\n{"="*78}')
    rows, written = [], 0
    os.makedirs(OUT, exist_ok=True)
    for path in files:
        stem = os.path.basename(path)[:-5]
        book = stem[len(prefix) + 1:]
        want = book_map.get(book)
        refs = load_tess(path)
        if not want:
            rows.append({'book': book, 'status': 'no_english_book_known',
                         'n_refs': len(refs)})
            print(f'  {book:38s} -- no English book identified')
            continue
        if want not in usfm:
            rows.append({'book': book, 'status': 'english_book_absent',
                         'wanted': want, 'n_refs': len(refs)})
            print(f'  {book:38s} -- {want} not in the {source_label} files')
            continue

        best = best_offset(refs, usfm[want])
        if not best:
            rows.append({'book': book, 'status': 'no_verses_matched',
                         'wanted': want, 'n_refs': len(refs)})
            print(f'  {book:38s} -- no verse numbers matched')
            continue

        # THE RIVAL TEST. Score this book against other English books too. A
        # correct map beats them; a wrong one usually does not, because the
        # proper names of Zephaniah are not the proper names of Obadiah.
        rivals, rival_corrs = [], []
        for code, other in usfm.items():
            if code == want:
                continue
            pairs, mp = try_pairing(refs, other, 0)
            if len(mp) < max(10, 0.3 * len(refs)):
                continue
            hit, n = V.score(pairs, 'grc', sample=120)
            rc = length_corr(pairs)
            if hit is not None and n >= 8:
                rivals.append((hit, code))
            if rc is not None:
                rival_corrs.append(rc)
        rivals.sort(reverse=True)
        top_rival = rivals[0] if rivals else (0.0, None)
        top_rival_corr = max(rival_corrs) if rival_corrs else 0.0

        by_name = best['hit'] >= FLOOR and best['hit'] >= top_rival[0] + MARGIN
        c = best.get('corr')
        by_length = (c is not None and c >= CORR_FLOOR
                     and c >= top_rival_corr + CORR_MARGIN)
        ok = by_name or by_length
        row = {'book': book, 'english': want, 'offset': best['offset'],
               'name_hit': round(best['hit'], 3), 'name_n': best['n'],
               'voffset': best.get('voffset', 0),
               'length_corr': (round(c, 3) if c is not None else None),
               'rival_corr': round(top_rival_corr, 3),
               'accepted_on': 'names' if by_name else ('length' if by_length else None),
               'coverage': round(best['coverage'], 4),
               'n_refs': len(refs), 'n_translated': len(best['mapping']),
               'best_rival': top_rival[1],
               'best_rival_hit': round(top_rival[0], 3),
               'status': 'ok' if ok else 'rejected_ambiguous'}
        rows.append(row)
        flag = '' if ok else '   <-- REJECTED'
        off = ''
        if best['offset']:
            off += f" c{best['offset']:+d}"
        if best.get('voffset'):
            off += f" v{best['voffset']:+d}"
        off = f'{off:<7s}' if off else ''
        cs = f'{c:.3f}' if c is not None else '  n/a'
        print(f"  {book:34s} {want:4s}{off:5s} names {best['hit']:.3f}/{top_rival[0]:.3f} "
              f"len {cs}/{top_rival_corr:.3f} cov {best['coverage']:.3f} "
              f"{len(best['mapping']):5d} refs  [{'names' if by_name else ('length' if by_length else '-')}]{flag}")
        if not ok:
            continue

        units, idx, ref2u = [], {}, {}
        for ref, txt in best['mapping'].items():
            if txt not in idx:
                idx[txt] = len(units)
                units.append(txt)
            ref2u[ref] = idx[txt]
        fn = f'grc__{stem}.json'
        json.dump({
            'tess_work': f'grc/{stem}', 'language': 'grc',
            'n_tess_refs': len(refs), 'n_translated': len(best['mapping']),
            'coverage': round(best['coverage'], 4),
            'mean_source_lines_per_translation_unit': 1.0,
            'alignment_confidence': 'high',
            'name_check_hit_rate': round(best['hit'], 3),
            'name_check_n': best['n'],
            'length_correlation': (round(c, 3) if c is not None else None),
            'verified_by': 'names' if by_name else 'verse length',
            'sources': [{'translator': source_label, 'title': source_label,
                         'mode': 'verse', 'ref_composition': ['chapter', 'verse'],
                         'chapter_offset': best['offset'],
                         'verse_offset': best.get('voffset', 0),
                         'english_book': want}],
            'license': license_text,
            'attribution': source_label,
            'n_units_stored': len(units), 'units': units, 'ref_to_unit': ref2u,
        }, open(f'{OUT}/{fn}', 'w'), ensure_ascii=False)
        written += 1
    return rows, written


def main():
    brenton = load_usfm(BRENTON, 'eng-Brenton')
    web = load_usfm(WEB, 'eng-web')
    print(f'Brenton books parsed: {len(brenton)}   WEB books parsed: {len(web)}')

    lxx_rows, lxx_n = run(
        'SEPTUAGINT', LXX, brenton, 'eng-Brenton', 'septuaginta',
        "Brenton's Septuagint (1851)",
        'Public domain (Brenton, The Septuagint Version of the Old Testament, 1851)')
    nt_rows, nt_n = run(
        'GREEK NEW TESTAMENT', NT, web, 'eng-web', 'new_testament',
        'World English Bible',
        'Public domain (World English Bible)')

    total = sum(r.get('n_translated', 0) for r in lxx_rows + nt_rows
                if r.get('status') == 'ok')
    print(f'\n{"="*78}')
    print(f'written: {lxx_n} Septuagint books + {nt_n} New Testament books')
    print(f'lines translated: {total:,}')
    bad = [r for r in lxx_rows + nt_rows if r.get('status') != 'ok']
    print(f'not written: {len(bad)}')
    for r in bad:
        print(f"   {r['book']:38s} {r['status']}"
              + (f" (hit {r.get('name_hit')} vs rival {r.get('best_rival')} "
                 f"{r.get('best_rival_hit')})" if r.get('name_hit') is not None else ''))
    json.dump({'septuagint': lxx_rows, 'new_testament': nt_rows},
              open(f'{OUT}/report.json', 'w'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()
