#!/usr/bin/env python3
"""
Merge several alignments of Paton's Greek Anthology made from different scans of
the same Loeb volume into one file per book.

WHY. Each archive.org scan of a Loeb volume loses different pages and different
epigram headings to OCR. align_anthologia_graeca.py run on one scan covered 58 to
63 percent of books 7, 8, 14, 15 and 16. Run on a better scan it covers 70 to 95
percent, and the epigrams each scan misses are largely not the ones another scan
misses. This script takes, for every Greek reference, the English unit from the
highest-coverage scan that has one, then recomputes the checks on the merged file.

A third check comes free: for every epigram two scans both aligned, the two
English texts are compared. Two OCR runs of the same page agree closely when the
alignment is right, and the agreement rate is reported per book. Scans disagreeing
about which epigram a text belongs to would show as a low rate.

Usage:
    python merge_anthologia_scans.py OUT_DIR BOOKS SCAN_DIR [SCAN_DIR ...]
(BOOKS is a comma list such as 7,8,14,15,16. Each SCAN_DIR holds the
grc__anthologia_graeca.part.N.json files one run of the aligner wrote.)
"""
import difflib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import proper_names as PN  # noqa: E402

TEXTS = os.path.join(os.environ.get('TESSERAE_TEXTS', '/var/www/tesseraev6_flask/texts'), 'grc')
YEAR = {7: 1917, 8: 1917, 9: 1917, 10: 1918, 11: 1918, 12: 1918, 13: 1918, 14: 1918, 15: 1918, 16: 1918}
ROMAN = {7: 'VII', 8: 'VIII', 10: 'X', 11: 'XI', 12: 'XII', 13: 'XIII', 14: 'XIV', 15: 'XV', 16: 'XVI'}


def epigram_of(ref):
    parts = ref.split()[-1].split('.')
    return parts[1] if len(parts) > 1 else None


def pearson(pairs):
    xs = [a for a, b in pairs]
    ys = [b for a, b in pairs]
    n = len(xs)
    if n < 10:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None


def main():
    out_dir, books = sys.argv[1], [int(b) for b in sys.argv[2].split(',')]
    scans = sys.argv[3:]
    os.makedirs(out_dir, exist_ok=True)
    for b in books:
        name = f'grc__anthologia_graeca.part.{b}.json'
        runs = []
        for s in scans:
            p = os.path.join(s, name)
            if os.path.exists(p):
                d = json.load(open(p, encoding='utf-8'))
                runs.append((d['coverage'], s, d))
        runs.sort(key=lambda r: -r[0])
        greek = []
        for line in open(os.path.join(TEXTS, f'anthologia_graeca.part.{b}.tess'), encoding='utf-8'):
            if '\t' in line:
                ref, text = line.rstrip('\n').split('\t', 1)
                greek.append((ref.strip('<>'), text.strip()))
        units, idx, ref2u, from_scan = [], {}, {}, {}
        # A fill from a lower-ranked scan is trusted only where that scan has been
        # SEEN to agree with the better one. One scan of volume 5 numbered its
        # riddles two off for a whole stretch of Book 14, and filling blindly from
        # it would have put the wrong English beside right Greek, the failure this
        # project fears most. For each epigram the top scan lacks, the filler scan
        # must agree with the top scan (same opening text, ratio 0.6) on the
        # nearest epigram before AND after it that both scans aligned, each within
        # six epigrams. Where that cannot be shown, the epigram stays empty.
        order = []
        for ref, _ in greek:
            e = epigram_of(ref)
            if e not in order:
                order.append(e)
        first_ref = {}
        for ref, _ in greek:
            first_ref.setdefault(epigram_of(ref), ref)

        def unit_text(d, e, first_ref=first_ref):
            u = d['ref_to_unit'].get(first_ref[e])
            return None if u is None else d['units'][u]

        def same(a, b):
            return difflib.SequenceMatcher(None, a[:300].lower(), b[:300].lower()).ratio() >= 0.6

        def trusted(top, d, e, order=order):
            pos = order.index(e)
            ok_before = ok_after = False
            for k in range(pos - 1, max(-1, pos - 7), -1):
                a, c = unit_text(top, order[k]), unit_text(d, order[k])
                if a is not None and c is not None:
                    ok_before = same(a, c)
                    break
            for k in range(pos + 1, min(len(order), pos + 7)):
                a, c = unit_text(top, order[k]), unit_text(d, order[k])
                if a is not None and c is not None:
                    ok_after = same(a, c)
                    break
            return ok_before and ok_after

        top = runs[0][2]
        fill_ok = {}
        rejected_fills = 0
        for e in order:
            if unit_text(top, e) is not None:
                continue
            for rank in range(1, len(runs)):
                d = runs[rank][2]
                if unit_text(d, e) is not None:
                    if trusted(top, d, e):
                        fill_ok[e] = rank
                        break
                    rejected_fills += 1
        for ref, _ in greek:
            e = epigram_of(ref)
            rank = 0 if top['ref_to_unit'].get(ref) is not None else fill_ok.get(e)
            if rank is None:
                continue
            d = runs[rank][2]
            u = d['ref_to_unit'].get(ref)
            if u is None:
                continue
            txt = d['units'][u]
            if txt not in idx:
                idx[txt] = len(units)
                units.append(txt)
            ref2u[ref] = idx[txt]
            from_scan[ref] = rank
        # cross-scan agreement per epigram
        agree = total = 0
        seen = set()
        for ref, _ in greek:
            e = epigram_of(ref)
            if e in seen:
                continue
            seen.add(e)
            texts = []
            for cov, s, d in runs:
                u = d['ref_to_unit'].get(ref)
                if u is not None:
                    texts.append(d['units'][u])
            if len(texts) >= 2:
                total += 1
                if any(difflib.SequenceMatcher(None, texts[0][:300].lower(), t[:300].lower()).ratio() >= 0.6
                       for t in texts[1:]):
                    agree += 1
        by_e = {}
        for ref, g in greek:
            by_e.setdefault(epigram_of(ref), []).append(g)
        pairs, lens, done = [], [], set()
        for ref, g in greek:
            e = epigram_of(ref)
            if e in done or ref not in ref2u:
                continue
            done.add(e)
            gt = ' '.join(by_e[e])
            pairs.append((gt, units[ref2u[ref]]))
            lens.append((len(gt), len(units[ref2u[ref]])))
        hit, n_names = PN.score(pairs, 'grc')
        corr = pearson(lens)
        n_refs = len(greek)
        n_tr = len(ref2u)
        cov = n_tr / n_refs
        verified = 'names' if (hit is not None and n_names >= 10) else ('length' if corr is not None else None)
        conf = 'high' if cov >= 0.95 and (corr is None or corr >= 0.5) else (
            'medium' if cov >= 0.90 else ('low' if cov >= 0.5 else 'very low'))
        out = {
            'tess_work': f'grc/anthologia_graeca.part.{b}', 'language': 'grc',
            'n_tess_refs': n_refs, 'n_translated': n_tr, 'coverage': round(cov, 4),
            'mean_source_lines_per_translation_unit': round(n_tr / max(1, len(units)), 2),
            'alignment_confidence': conf,
            'name_check_hit_rate': round(hit, 3) if hit is not None else None,
            'name_check_n': n_names,
            'length_correlation': round(corr, 3) if corr is not None else None,
            'cross_scan_agreement': (round(agree / total, 3) if total else None),
            'cross_scan_agreement_n': total,
            'verified_by': verified,
            'sources': [{
                'translator': 'W. R. Paton', 'year': YEAR[b],
                'title': f'The Greek Anthology, Book {ROMAN[b]} (Loeb Classical Library)',
                'publisher': "William Heinemann / G. P. Putnam's Sons",
                'mode': 'epigram', 'ref_composition': ['epigram'],
                'source_url': 'https://archive.org/details/greekanthology02unse',
            }],
            'license': 'Public domain in the United States (published 1916-1918).',
            'attribution': 'W. R. Paton (1916-1918), Loeb Classical Library, via archive.org',
            'n_units_stored': len(units), 'units': units, 'ref_to_unit': ref2u,
        }
        json.dump(out, open(os.path.join(out_dir, name), 'w', encoding='utf-8'), ensure_ascii=False)
        used = {}
        for r in from_scan.values():
            used[runs[r][1].rstrip('/').split('/')[-1]] = used.get(runs[r][1].rstrip('/').split('/')[-1], 0) + 1
        print(f'book {b}: coverage {cov:.1%} ({n_tr}/{n_refs}) names {hit if hit is None else round(hit,3)} (n={n_names}) '
              f'length_r {None if corr is None else round(corr,3)} agreement {agree}/{total} units {len(units)} conf {conf}')
        print('   refs by scan:', used, 'fills rejected for lack of agreement:', rejected_fills)


if __name__ == '__main__':
    main()
