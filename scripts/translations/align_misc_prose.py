#!/usr/bin/env python3
"""Four quick structure-keyed wins from clean Gutenberg texts: Pliny the
Younger's letters, Suetonius' Caesars, Petronius, and the rest of Horace.

- PLINY (2,288 lines): two sources. Books 1-5 come letter-exact from
  Firth (PG 3234, "1.I.--TO SEPTICIUS." markers); his second volume was
  never digitized, so books 6-9 stay uncovered. Book 10 comes from the
  Melmoth/Bosanquet selection (PG 2811) ONLY if a constant offset can
  align it essentially perfectly, which it cannot: the offset search
  scored 0.60 on names, but spot-reads showed the numbering drift is
  VARIABLE (10.33 was served the Prusa bath letter, which is 10.23), so
  book 10 is refused along with 6-9. Wrong letters beside right refs is
  the failure this pipeline exists to prevent. OPEN until Firth's second
  volume is digitized.

- SUETONIUS (1,232 lines): Thomson/Forester (PG 6400). Chapters are
  inline roman chains ("I.  Julius Caesar, the Divine..."), and a chain
  restarting at I opens the next life. The twelve chains must match the
  canonical chapter counts (89, 101, 76, 60, 46, 57, 23, 12, 18, 25, 11,
  23) within one; the appended Lives of the Grammarians are extra chains
  and are ignored. Chapter-keyed exact.

- PETRONIUS (315 lines of the Satyricon): Firebaugh (PG 5225), whose
  "CHAPTER THE FIRST." headings are counted positionally and validated
  against the corpus's chapter numbers. (The corpus's petronius.fragmenta
  has no PD English counterpart and is not attempted.)

- HORACE, Epistles / Epodes / Carmen saeculare (2,193 lines): Smart's
  prose (PG 14020), poem-keyed exact — EPISTLE/EPODE headings under book
  headings, one unit per poem.

Usage:
    python scripts/translations/align_misc_prose.py \
        --src-dir <dir with pg2811 pg6400 pg5225 pg14020 .txt> \
        --tess-dir texts/la --out-dir <dir>
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

ROMAN = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500}


def roman_to_int(s):
    total, prev = 0, 0
    for ch in reversed(s.strip('. ').upper()):
        v = ROMAN.get(ch)
        if v is None:
            return None
        total += v if v >= prev else -v
        prev = max(prev, v)
    return total or None


def write(out_dir, tessname, n_refs, mapping, pairs, source, floor=0.25,
          cov_floor=0.5):
    cov = len(mapping) / n_refs if n_refs else 0
    hit, n = V.score(pairs, 'la', sample=800)
    ulist, idx, ref2u = [], {}, {}
    for ref, txt in mapping.items():
        if txt not in idx:
            idx[txt] = len(ulist)
            ulist.append(txt)
        ref2u[ref] = idx[txt]
    ok = hit is not None and hit >= floor and cov >= cov_floor
    print(f'{tessname:38s} cov {cov:.4f} ({len(mapping)}/{n_refs}) '
          f'units {len(ulist)} names {hit}/{n} ' + ('ok' if ok else 'REJECTED'))
    if not ok:
        return
    json.dump({
        'tess_work': f'la/{tessname}', 'language': 'la',
        'n_tess_refs': n_refs, 'n_translated': len(mapping),
        'coverage': round(cov, 4),
        'mean_source_lines_per_translation_unit':
            round(len(mapping) / max(1, len(ulist)), 1),
        'alignment_confidence': 'high' if hit >= 0.5 else 'medium',
        'name_check_hit_rate': hit, 'name_check_n': n,
        'verified_by': 'names',
        'sources': [source],
        'license': source['license'],
        'attribution': source['attribution'],
        'n_units_stored': len(ulist), 'units': ulist, 'ref_to_unit': ref2u,
    }, open(os.path.join(out_dir, f'la__{tessname}.json'), 'w'),
        ensure_ascii=False)


def tess_lines(path, pat):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(pat, line)
        if m:
            out.append(m.groups() + (line.split('>', 1)[1].strip(),))
    return out


def clean_block(lines):
    text = ' '.join(l.strip() for l in lines if l.strip())
    text = re.sub(r'\[\d+\]', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def do_pliny(src_dir, tess_dir, out_dir):
    refs = tess_lines(os.path.join(tess_dir, 'pliny_the_younger.letters.tess'),
                      r'^<(pliny_the_younger\. Letters (\d+)\.(\d+)\.\d+)>')
    english = {}

    # books 1-5: Firth, letter-exact
    lines = open(os.path.join(src_dir, 'pg3234.txt'),
                 encoding='utf-8', errors='replace').read().split('\n')
    cur, buf = None, []
    for ln in lines:
        m = re.match(r'^(\d+)\.([IVXLC]+)\.?--', ln.strip())
        if m and roman_to_int(m.group(2)):
            if cur:
                english[cur] = clean_block(buf)
            cur, buf = (int(m.group(1)), roman_to_int(m.group(2))), []
            continue
        if re.match(r'^\*\*\* END', ln):
            break
        if cur:
            buf.append(ln)
    if cur:
        english[cur] = clean_block(buf)

    # book 10: the Trajan run of the Melmoth selection, offset-searched
    lines = open(os.path.join(src_dir, 'pg2811.txt'),
                 encoding='utf-8', errors='replace').read().split('\n')
    trajan, cur_n, buf, run = [], 0, [], []
    for ln in lines:
        m = re.match(r'^([IVXLC]+) -- ', ln.strip())
        n = roman_to_int(m.group(1)) if m else None
        if n:
            if cur_n and buf:
                run.append((cur_n, clean_block(buf)))
            if n == 1 and run:
                trajan, run = run, []      # keep the previous run;
            cur_n, buf = n, [ln.split('--', 1)[1]]
            continue
        if re.match(r'^FOOTNOTES', ln.strip()):
            if cur_n and buf:
                run.append((cur_n, clean_block(buf)))
            cur_n, buf = 0, []
            continue
        if cur_n:
            buf.append(ln)
    if cur_n and buf:
        run.append((cur_n, clean_block(buf)))
    if len(run) > 50:                       # the last big run is Trajan's
        trajan = run
    lat10 = [(ref, int(l), latin) for ref, b, l, latin in refs if b == '10']
    if trajan and lat10:
        best = None
        for off in (-2, -1, 0, 1, 2):
            cand = {n + off: t for n, t in trajan}
            pairs = [(latin, cand[l]) for ref, l, latin in lat10
                     if l in cand]
            hit, n = V.score(pairs, 'la', sample=300)
            if hit is not None and (best is None or hit > best[1]):
                best = (off, hit, n)
        # tried and withdrawn: a constant offset scores 0.60 on names but
        # spot-reads show the drift is VARIABLE (10.33 was served the
        # Prusa bath letter, 10.23's), so the whole book is refused
        if best and best[1] >= 0.98:
            off = best[0]
            print(f'  pliny book 10: offset {off} accepted '
                  f'(names {best[1]:.2f}/{best[2]})')
            for n, t in trajan:
                english[(10, n + off)] = t
        else:
            print(f'  pliny book 10 REFUSED (best offset {best})')

    mapping, pairs = {}, []
    for ref, b, l, latin in refs:
        t = english.get((int(b), int(l)))
        if t:
            mapping[ref] = t
            pairs.append((latin, t))
    write(out_dir, 'pliny_the_younger.letters', len(refs), mapping, pairs, {
        'translator': 'J. B. Firth (books 1-5); William Melmoth, '
                      'rev. F. C. T. Bosanquet (book 10)', 'year': 1900,
        'title': 'The Letters of the Younger Pliny',
        'publisher': 'Project Gutenberg 3234 / 2811',
        'mode': 'exact', 'ref_composition': ['book', 'letter'],
        'source_url': 'https://www.gutenberg.org/ebooks/3234',
        'license': 'Public domain: Firth 1900, Melmoth/Bosanquet 1878. '
                   'Texts from Project Gutenberg.',
        'attribution': 'J. B. Firth and William Melmoth, '
                       'via Project Gutenberg'},
          cov_floor=0.4)   # books 6-10 have no digitized PD source:
                           # partial BY DESIGN, the Jerome-letters case


SUET_LIVES = [('jul', 89), ('aug', 101), ('tib', 76), ('cal', 60),
              ('cl', 46), ('nero', 57), ('gal', 23), ('otho', 12),
              ('vit', 18), ('ves', 25), ('tit', 11), ('dom', 23)]


def do_suetonius(src_dir, tess_dir, out_dir):
    lines = open(os.path.join(src_dir, 'pg6400.txt'),
                 encoding='utf-8', errors='replace').read().split('\n')
    chains, cur, curch, buf = [], None, 0, []

    def close():
        if cur is not None and curch and buf:
            cur[curch] = clean_block(buf)
    for ln in lines:
        m = re.match(r'^([IVXLC]+)\.\s+(\S.*)$', ln)
        n = roman_to_int(m.group(1)) if m else None
        if n:
            if n == 1:
                close()
                if cur:
                    chains.append(cur)
                cur, curch, buf = {}, 1, [m.group(2)]
                continue
            if cur is not None and curch + 1 <= n <= curch + 3:
                close()
                curch, buf = n, [m.group(2)]
                continue
        if cur is not None:
            buf.append(ln)
    close()
    if cur:
        chains.append(cur)
    chains = [c for c in chains if len(c) >= 8]

    refs = tess_lines(os.path.join(tess_dir, 'suetonius.de_vita_caesarum.tess'),
                      r'^<(suet\. vit\. (\w+)\. (\d+)\.\d+)>')
    english = {}
    for i, (tag, want) in enumerate(SUET_LIVES):
        if i >= len(chains):
            break
        got = max(chains[i])
        if abs(got - want) > 1:
            print(f'  suetonius {tag} REFUSED (parsed {got} vs {want})')
            continue
        for c, t in chains[i].items():
            english[(tag, c)] = t
    mapping, pairs = {}, []
    for ref, tag, c, latin in refs:
        t = english.get((tag, int(c)))
        if t:
            mapping[ref] = t
            pairs.append((latin, t))
    write(out_dir, 'suetonius.de_vita_caesarum', len(refs), mapping, pairs, {
        'translator': 'Alexander Thomson, revised by T. Forester',
        'year': 1855, 'title': 'The Lives of the Twelve Caesars (Bohn)',
        'publisher': 'Project Gutenberg 6400',
        'mode': 'exact', 'ref_composition': ['life', 'chapter'],
        'source_url': 'https://www.gutenberg.org/ebooks/6400',
        'license': 'Public domain: Bohn edition, 1855. '
                   'Text from Project Gutenberg.',
        'attribution': 'Alexander Thomson (Bohn), via Project Gutenberg'})


ORDWORDS = {
    'FIRST': 1, 'SECOND': 2, 'THIRD': 3, 'FOURTH': 4, 'FIFTH': 5,
    'SIXTH': 6, 'SEVENTH': 7, 'EIGHTH': 8, 'NINTH': 9, 'TENTH': 10,
    'ELEVENTH': 11, 'TWELFTH': 12, 'THIRTEENTH': 13, 'FOURTEENTH': 14,
    'FIFTEENTH': 15, 'SIXTEENTH': 16, 'SEVENTEENTH': 17,
    'EIGHTEENTH': 18, 'NINETEENTH': 19, 'TWENTIETH': 20,
    'THIRTIETH': 30, 'FORTIETH': 40, 'FIFTIETH': 50, 'SIXTIETH': 60,
    'SEVENTIETH': 70, 'EIGHTIETH': 80, 'NINETIETH': 90, 'HUNDREDTH': 100,
    'TWENTY': 20, 'THIRTY': 30, 'FORTY': 40, 'FIFTY': 50, 'SIXTY': 60,
    'SEVENTY': 70, 'EIGHTY': 80, 'NINETY': 90, 'HUNDRED': 100, 'ONE': 1,
}


def ordinal_words(s):
    total = 0
    for w in re.split(r'[\s\-]+', s.upper()):
        w = w.strip('.,')
        if w in ('AND', 'THE', 'CHAPTER'):
            continue
        v = ORDWORDS.get(w)
        if v is None:
            return None
        total += v
    return total or None


def do_petronius(src_dir, tess_dir, out_dir):
    lines = open(os.path.join(src_dir, 'pg5225.txt'),
                 encoding='utf-8', errors='replace').read().split('\n')
    chapters, cur, buf = {}, None, []

    def close():
        if cur and buf:
            chapters[cur] = clean_block(buf)
    pos = 0
    for ln in lines:
        m = re.match(r'^CHAPTER THE (.+?)\.?\s*$', ln.strip())
        if m:
            close()
            pos += 1
            n = ordinal_words(m.group(1))
            # positional count, cross-checked against the printed ordinal
            if n and abs(n - pos) > 2:
                pos = n
            cur, buf = pos, []
            continue
        if re.match(r'^(FOOTNOTES|COMPLETE AND UNEXPURG)', ln.strip()):
            close()
            cur = None
            continue
        if cur:
            buf.append(ln)
    close()

    refs = tess_lines(os.path.join(tess_dir, 'petronius.satyricon.tess'),
                      r'^<(petr\. saty\. (\d+)\.\d+)>')
    mapping, pairs = {}, []
    for ref, c, latin in refs:
        t = chapters.get(int(c))
        if t:
            mapping[ref] = t
            pairs.append((latin, t))
    write(out_dir, 'petronius.satyricon', len(refs), mapping, pairs, {
        'translator': 'W. C. Firebaugh', 'year': 1922,
        'title': 'The Satyricon of Petronius Arbiter',
        'publisher': 'Project Gutenberg 5225',
        'mode': 'exact', 'ref_composition': ['chapter'],
        'source_url': 'https://www.gutenberg.org/ebooks/5225',
        'license': 'Public domain: published 1922. '
                   'Text from Project Gutenberg.',
        'attribution': 'W. C. Firebaugh (1922), via Project Gutenberg'})


def do_horace(src_dir, tess_dir, out_dir):
    text = open(os.path.join(src_dir, 'pg14020.txt'),
                encoding='utf-8', errors='replace').read()
    lines = text.split('\n')
    # regions
    marks = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if re.match(r'^THE BOOK OF THE EPODES', s):
            marks.append((i, 'epod', None))
        elif re.match(r'^THE SECULAR POEM', s):
            marks.append((i, 'cs', None))
        elif re.match(r'^THE (FIRST|SECOND) BOOK OF THE EPISTLES', s):
            marks.append((i, 'ep', 1 if 'FIRST' in s else 2))
        elif re.match(r'^THE ART OF POETRY', s):
            marks.append((i, 'end', None))
    marks.append((len(lines), 'end', None))

    poems = {}      # ('epod', None, n) / ('ep', book, n) / ('cs', None, 1)
    for k in range(len(marks) - 1):
        i0, kind, book = marks[k]
        if kind == 'end':
            continue
        seg = lines[i0 + 1:marks[k + 1][0]]
        if kind == 'cs':
            poems[('cs', None, 1)] = clean_block(
                [l for l in seg if not l.strip().startswith('TO ')][:400])
            continue
        cur, buf = None, []
        head = 'EPISTLE' if kind == 'ep' else 'ODE'
        for ln in seg:
            s = ln.strip()
            m = re.match(rf'^{head}\s+([IVXLC]+)\.?', s)
            n = roman_to_int(m.group(1)) if m else None
            if n:
                if cur:
                    poems[(kind, book, cur)] = clean_block(buf)
                cur, buf = n, []
                continue
            if cur:
                buf.append(ln)
        if cur:
            poems[(kind, book, cur)] = clean_block(buf)

    jobs = [
        ('horace.epistles', r'^<(hor\. ep\. (\d+)\.(\d+)\.\d+)>',
         lambda b, p: ('ep', int(b), int(p))),
        ('horace.epodes', r'^<(hor\. epod\. (\d+)\.(\d+))>',
         lambda b, p: ('epod', None, int(b))),
        ('horace.carmen_saeculare', r'^<(hor\. c\.s\. ()(\d+))>',
         lambda b, p: ('cs', None, 1)),
    ]
    for tessname, pat, keyf in jobs:
        refs = tess_lines(os.path.join(tess_dir, tessname + '.tess'), pat)
        mapping, pairs = {}, []
        for ref, b, p, latin in refs:
            t = poems.get(keyf(b, p))
            if t:
                mapping[ref] = t
                pairs.append((latin, t))
        write(out_dir, tessname, len(refs), mapping, pairs, {
            'translator': 'Christopher Smart (Buckley revision)',
            'year': 1863, 'title': 'The Works of Horace, '
                                   'translated literally into English prose',
            'publisher': 'Project Gutenberg 14020',
            'mode': 'exact', 'ref_composition': ['book', 'poem'],
            'source_url': 'https://www.gutenberg.org/ebooks/14020',
            'license': 'Public domain: Smart 1756, Buckley revision 1863. '
                       'Text from Project Gutenberg.',
            'attribution': 'Christopher Smart, via Project Gutenberg'})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    do_pliny(args.src_dir, args.tess_dir, args.out_dir)
    do_suetonius(args.src_dir, args.tess_dir, args.out_dir)
    do_petronius(args.src_dir, args.tess_dir, args.out_dir)
    do_horace(args.src_dir, args.tess_dir, args.out_dir)


if __name__ == '__main__':
    main()
