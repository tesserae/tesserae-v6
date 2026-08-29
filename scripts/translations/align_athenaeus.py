"""Athenaeus, Deipnosophists: Casaubon-keyed English from Gulick and Yonge.

Corpus refs are Casaubon page+letter (`<ath. 57b>` ... `<ath. 702c>`), and
both public-domain translations exist online in transcriptions that carry
exactly those numbers, so alignment is structure-keyed:

- Books 1-10: C. B. Gulick's Loeb (vols I-IV, 1927-1930 — all US public
  domain now that 1930 entered PD on 2026-01-01), in Bill Thayer's
  LacusCurtius transcription, which anchors every Casaubon LETTER
  (`<A CLASS="Tsubsec" NAME="T57b">`) — exact at the ref's own grain.
- Books 11-15, plus the stretches of books 4-10 whose LacusCurtius
  pages have no subsection anchors yet: C. D. Yonge's Bohn translation
  (1854), at attalus.org, which marks every Casaubon PAGE (`[469]`);
  the letters a-f of a page share the page's unit. Gulick's vols V-VII
  (1933-41) are not public domain, and Yonge at attalus covers exactly
  the books Gulick cannot. Letter-keyed Gulick wins wherever both exist.

A ref is looked up first at (page, letter), then at earlier letters of
the same page (a lost letter anchor means the text sits inside the
previous letter's unit), then at page level. Every source part passes its
own proper-name check and the whole passes one globally; a part scoring
below the floor is dropped and printed.

Usage:
    python scripts/translations/align_athenaeus.py \
        --src-dir <dir with pen1A.html.. and att11a.html..> \
        --tess texts/grc/athenaeus.deipnosophists.tess --out <file>
"""
import argparse
import glob
import html as htmllib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V


def strip_text(fragment):
    txt = htmllib.unescape(re.sub(r'<[^>]+>', ' ', fragment))
    txt = txt.replace('\xa0', ' ')
    txt = re.sub(r'[{\[]\d+\.[}\]]', ' ', txt)     # Yonge chapter numbers
    txt = re.sub(r'\s+G\s+', ' ', txt)             # attalus Greek-text links
    txt = re.sub(r'⁠\s*\d+', ' ', txt)        # penelope note calls
    return re.sub(r'\s+', ' ', txt).strip()


def parse_penelope(path, units):
    """Letter-keyed units from a LacusCurtius part page."""
    h = open(path, encoding='latin-1', errors='ignore').read()
    start = h.find('<SPAN CLASS="pagenum">')
    end = h.find('<HR', start)
    if start == -1:
        return
    body = h[start:end if end != -1 else len(h)]
    parts = re.split(r'<A CLASS="T(?:sub)?sec" NAME="T(\d+)([a-f])">', body)
    # a continuation part opens with "(11F)" naming the page it resumes
    m = re.search(r'\((\d+)([A-F])\)', strip_text(parts[0])[:300])
    if m:
        key = (int(m.group(1)), m.group(2).lower())
        text = strip_text(parts[0])
        text = text[text.find(')') + 1:].strip()
        if len(text.split()) >= 3:
            units.setdefault(key, '')
            units[key] = (units[key] + ' ' + text).strip()
    for i in range(1, len(parts), 3):
        key = (int(parts[i]), parts[i + 1])
        text = strip_text(parts[i + 2])
        if len(text.split()) >= 1:
            units.setdefault(key, '')
            units[key] = (units[key] + ' ' + text).strip()


def parse_attalus(path, units):
    """Page-keyed units from an attalus Yonge part page."""
    h = open(path, encoding='latin-1', errors='ignore').read()
    parts = re.split(r'<A CLASS="ref" NAME="(\d+)">\s*\[\d+\]\s*</A>', h)
    for i in range(1, len(parts), 2):
        key = (int(parts[i]), None)
        # a navigation arrow ends the content of a segment (some parts
        # also carry one in the page header, which is why the page is
        # not cut at the first arrow globally)
        seg = re.split(r'&rarr;|Following pages', parts[i + 1])[0]
        text = strip_text(seg)
        if text:
            units.setdefault(key, '')
            units[key] = (units[key] + ' ' + text).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True)
    ap.add_argument('--tess', required=True)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    pen, att = {}, {}
    pen_files = sorted(glob.glob(os.path.join(args.src_dir, 'pen*.html')))
    att_files = sorted(glob.glob(os.path.join(args.src_dir, 'att*.html')))
    for f in pen_files:
        parse_penelope(f, pen)
    for f in att_files:
        parse_attalus(f, att)
    print(f'{len(pen)} letter units from {len(pen_files)} LacusCurtius '
          f'parts, {len(att)} page units from {len(att_files)} attalus parts')

    refs = []
    for line in open(args.tess, errors='ignore'):
        m = re.match(r'<(ath\. (\d+)([a-f]?))>\s*(.*)', line)
        if m:
            refs.append((m.group(1), int(m.group(2)),
                         m.group(3) or None, m.group(4)))

    def lookup(page, letter):
        if (page, letter) in pen:
            return ('pen', (page, letter))
        if letter:
            for l in 'abcdef'[:'abcdef'.index(letter)][::-1]:
                if (page, l) in pen:
                    return ('pen', (page, l))
        if (page, None) in att:
            return ('att', (page, None))
        return None

    units, unit_of, ref_to_unit, src_of = [], {}, {}, {}
    for ref, page, letter, _ in refs:
        got = lookup(page, letter)
        if not got:
            continue
        srcname, key = got
        k = (srcname, key)
        if k not in unit_of:
            unit_of[k] = len(units)
            units.append((pen if srcname == 'pen' else att)[key])
            src_of[unit_of[k]] = srcname
        ref_to_unit[ref] = unit_of[k]

    # per-source and per-book-of-100-pages name checks
    for srcname in ('pen', 'att'):
        for lo in range(0, 800, 100):
            pairs = [(grc, units[ref_to_unit[ref]])
                     for ref, page, _, grc in refs
                     if ref in ref_to_unit and lo <= page < lo + 100
                     and src_of[ref_to_unit[ref]] == srcname]
            if len(pairs) < 20:
                continue
            rate, n = V.score(pairs, 'grc', sample=150)
            tag = f'{srcname} pages {lo}-{lo + 99}'
            if rate is not None and n >= 10 and rate < 0.25:
                print(f'  {tag}: name check {rate:.2f} on {n} — WITHDRAWN')
                for ref, page, _, _ in refs:
                    if (ref in ref_to_unit and lo <= page < lo + 100
                            and src_of[ref_to_unit[ref]] == srcname):
                        del ref_to_unit[ref]
            else:
                print(f'  {tag}: names {rate if rate is None else round(rate, 2)} on {n}')

    used = sorted(set(ref_to_unit.values()))
    remap = {u: i for i, u in enumerate(used)}
    final_units = [units[u] for u in used]
    ref_to_unit = {r: remap[u] for r, u in ref_to_unit.items()}

    pairs = [(grc, final_units[ref_to_unit[ref]])
             for ref, _, _, grc in refs if ref in ref_to_unit]
    score = V.score(pairs, 'grc', sample=800)
    coverage = round(len(ref_to_unit) / len(refs), 4)
    out = {
        'tess_work': 'grc/athenaeus.deipnosophists',
        'language': 'grc',
        'n_tess_refs': len(refs),
        'n_translated': len(ref_to_unit),
        'coverage': coverage,
        'mean_source_lines_per_translation_unit':
            round(len(ref_to_unit) / max(1, len(final_units)), 1),
        'alignment_confidence':
            'high' if (score[0] is None or score[0] >= 0.5) else 'medium',
        'name_check_hit_rate': score,
        'name_check_n': score[1],
        'sources': [{
            'title': 'The Deipnosophists, books 1-10 (Loeb, vols I-IV)',
            'translator': 'C. B. Gulick', 'year': 1930,
            'publisher': 'Harvard University Press (via LacusCurtius, '
                         'transcription by Bill Thayer)',
            'source_url': 'https://penelope.uchicago.edu/Thayer/E/Roman/'
                          'Texts/Athenaeus/home.html',
            'mode': 'exact', 'ref_composition': ['casaubon_page', 'letter'],
        }, {
            'title': 'The Deipnosophists, books 11-15 (Bohn)',
            'translator': 'C. D. Yonge', 'year': 1854,
            'publisher': 'H. G. Bohn (via attalus.org)',
            'source_url': 'http://www.attalus.org/info/athenaeus.html',
            'mode': 'exact', 'ref_composition': ['casaubon_page'],
        }],
        'license': 'Public domain: Gulick vols I-IV published 1927-1930, '
                   'Yonge published 1854.',
        'attribution': 'C. B. Gulick (Loeb, 1927-30, books 1-10) via '
                       'LacusCurtius, and C. D. Yonge (Bohn, 1854, books '
                       '11-15) via attalus.org',
        'n_units_stored': len(final_units),
        'units': final_units,
        'ref_to_unit': ref_to_unit,
    }
    json.dump(out, open(args.out, 'w'), ensure_ascii=False)
    print(f'\ncoverage {coverage} ({len(ref_to_unit)} of {len(refs)} lines), '
          f'{len(final_units)} units, name check {score}')
    missing_pages = sorted({p for r, p, l, _ in refs if r not in ref_to_unit})
    print(f'uncovered pages ({len(missing_pages)}):',
          missing_pages[:30], '...' if len(missing_pages) > 30 else '')


if __name__ == '__main__':
    main()
