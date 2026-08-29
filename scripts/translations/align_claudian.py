#!/usr/bin/env python3
"""Claudian: the nine wholly untranslated poems, from Platnauer's Loeb
(1922) in the clean Project Gutenberg transcription (51443/51444).

4,716 lines: In Rufinum, the panegyrics on the third, fourth and sixth
consulates of Honorius, on Olybrius and Probinus and on Manlius
Theodorus, the Gothic and Gildonic wars, and the wedding poems. (The
Perseus run covered the rest of Claudian; those works are not touched.)

WHY NO TITLE PARSING AT ALL

The transcription interleaves the LATIN pages (with their printed
line numbers) and the facing English pages, separated by page markers.
So every English page sits right after a Latin page that says exactly
which lines it translates -- and the Latin page can identify its own
poem by simply LOOKING ITSELF UP in our corpus: the first verse line of
each Latin block, normalised (v=u, i=j, punctuation off), is matched
against the corpus's Latin, which yields work, ref and a cross-check
(the corpus line number must equal the number computed from the block's
printed markers). A block that cannot be found and confirmed is skipped
with its English. This sidesteps every title/numbering trap the other
aligners fight, because the pairing key is the text itself.

Latin vs English blocks are told apart by the pure-English stopword
test (the Propertius guard): Latin scores ~0, real English a third.

Usage:
    python scripts/translations/align_claudian.py \
        --src-dir <dir with pg51443.txt pg51444.txt> \
        --tess-dir texts/la --out-dir <dir>
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V

WORKS = [
    'claudian.in_rufinum',
    'claudian.panegyricus_de_sexto_consulatu_honorii_augusti',
    'claudian.panegyricus_de_quarto_consulatu_honorii_augusti',
    'claudian.panegyricus_de_tertio_consulatu_honorii_augusti',
    'claudian.de_bello_gothico',
    'claudian.de_bello_gildonico',
    'claudian.epithalamium_de_nuptiis_honorii_augusti',
    'claudian.panegyricus_dictus_manlio_theodoro_consuli',
    'claudian.in_consulatum_olybrii_et_probini',
]

STOP = {'the', 'of', 'and', 'to', 'that', 'with', 'for', 'her', 'his',
        'thy', 'thou', 'he', 'she', 'not', 'but', 'by', 'was', 'from',
        'all', 'shall', 'thee', 'when', 'their', 'or', 'be', 'now',
        'is', 'have', 'hath', 'will', 'you', 'your'}


def eng_share(text):
    words = [w.lower().strip('.,;:?!()"’“”') for w in text.split()]
    if len(words) < 8:
        return None
    return sum(1 for w in words if w in STOP) / len(words)


def norm(s):
    s = s.lower().replace('v', 'u').replace('j', 'i')
    s = re.sub(r'[^a-z]', '', s)
    return s[:24]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src-dir', required=True)
    ap.add_argument('--tess-dir', required=True)
    ap.add_argument('--out-dir', required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    # corpus index: normalised line text -> (work, ref, seq)
    # and per work the ordered refs, so a Latin block's computed span can
    # be walked forward from its matched first line
    index, order, latin_of = {}, {}, {}
    for work in WORKS:
        path = os.path.join(args.tess_dir, work + '.tess')
        refs = []
        for line in open(path, encoding='utf-8', errors='replace'):
            m = re.match(r'^<([^>]+)>\s*(.*)', line)
            if not m:
                continue
            ref, latin = m.group(1).strip(), m.group(2).strip()
            refs.append(ref)
            latin_of[ref] = latin
            key = norm(latin)
            if len(key) >= 12 and key not in index:
                index[key] = (work, len(refs) - 1)
        order[work] = refs

    # walk both volumes: blocks between page markers / asterisk rules
    blocks = []
    for fname in ('pg51443.txt', 'pg51444.txt'):
        cur = []
        for ln in open(os.path.join(args.src_dir, fname),
                       encoding='utf-8', errors='replace'):
            s = ln.rstrip('\n')
            if re.match(r'^\s*(Page \d+|\*\s+\*.*|\*\*\* (START|END))', s.strip()) \
                    or re.match(r'^\s*\*\s+\*', s):
                if cur:
                    blocks.append(cur)
                cur = []
                continue
            cur.append(s)
        if cur:
            blocks.append(cur)

    # PASS 1: classify blocks; match Latin blocks to the corpus
    seq = []          # ('la', work, i0, n_verses) / ('en', text)
    stats = {'latin': 0, 'english': 0, 'unmatched': 0}
    for block in blocks:
        body = [l for l in block if l.strip()]
        if not body:
            continue
        text = ' '.join(l.strip() for l in body)
        share = eng_share(text)
        if share is None:
            continue
        if share < 0.12:
            stats['latin'] += 1
            hit = None
            for l in body:
                t = re.sub(r'\s+\d+\s*$', '', l.strip())
                key = norm(t)
                if len(key) >= 12 and key in index:
                    hit = index[key]
                    break
            if not hit:
                stats['unmatched'] += 1
                seq.append(('la-unmatched',))
                continue
            work, i0 = hit
            n_verses = sum(
                1 for l in body
                if len(norm(re.sub(r'\s+\d+\s*$', '', l))) >= 8
                and not l.strip().isupper())      # titles are set in caps
            seq.append(('la', work, i0, n_verses))
        else:
            stats['english'] += 1
            en = re.sub(r'\[\d+\]', '', text)
            en = re.sub(r'\s+', ' ', en).strip()
            seq.append(('en', en))

    # PASS 2: each English block serves the span of the Latin block just
    # before it; the span END is taken from the NEXT matched Latin block
    # of the same work (facing pages are contiguous), with the block's
    # own verse count as the fallback and a hard cap -- the first draft
    # counted title lines as verses and let unmatched blocks inflate a
    # span across a whole lost page
    mapping, pairs = {}, {}
    la_positions = [k for k, e in enumerate(seq) if e[0] == 'la']
    next_start = {}
    for a, b in zip(la_positions, la_positions[1:]):
        if seq[a][1] == seq[b][1]:
            next_start[a] = seq[b][2]
    for k, entry in enumerate(seq):
        if entry[0] != 'la':
            continue
        work, i0, n_verses = entry[1], entry[2], entry[3]
        if k + 1 >= len(seq) or seq[k + 1][0] != 'en':
            continue
        en = seq[k + 1][1]
        if len(en.split()) < 12:
            continue
        i1 = next_start.get(k, i0 + n_verses) - 1
        if i1 < i0 or i1 - i0 > 45:
            i1 = min(i0 + max(n_verses, 1) - 1, i0 + 44)
        i1 = min(i1, len(order[work]) - 1)
        for i in range(i0, i1 + 1):
            ref = order[work][i]
            if ref not in mapping.setdefault(work, {}):
                mapping[work][ref] = en
                pairs.setdefault(work, []).append((latin_of[ref], en))

    print(f"blocks: latin {stats['latin']} english {stats['english']} "
          f"latin-unmatched {stats['unmatched']}")
    for work in WORKS:
        refs = order[work]
        mp = mapping.get(work, {})
        cov = len(mp) / len(refs) if refs else 0
        hit, n = V.score(pairs.get(work, []), 'la', sample=500)
        ulist, idx, ref2u = [], {}, {}
        for ref, txt in mp.items():
            if txt not in idx:
                idx[txt] = len(ulist)
                ulist.append(txt)
            ref2u[ref] = idx[txt]
        ok = hit is not None and hit >= 0.25 and cov >= 0.5
        print(f'{work:55s} cov {cov:.4f} ({len(mp)}/{len(refs)}) '
              f'units {len(ulist)} names {hit}/{n} '
              + ('ok' if ok else 'REJECTED'))
        if not ok:
            continue
        json.dump({
            'tess_work': f'la/{work}', 'language': 'la',
            'n_tess_refs': len(refs), 'n_translated': len(mp),
            'coverage': round(cov, 4),
            'mean_source_lines_per_translation_unit':
                round(len(mp) / max(1, len(ulist)), 1),
            'alignment_confidence': 'high' if hit >= 0.5 else 'medium',
            'name_check_hit_rate': hit, 'name_check_n': n,
            'verified_by': 'names',
            'sources': [{'translator': 'Maurice Platnauer', 'year': 1922,
                         'title': 'Claudian, with an English translation '
                                  '(Loeb, 2 vols)',
                         'publisher': 'William Heinemann '
                                      '(via Project Gutenberg 51443/51444)',
                         'mode': 'page',
                         'ref_composition': ['facing-page line span'],
                         'source_url':
                             'https://www.gutenberg.org/ebooks/51443'}],
            'license': 'Public domain in the United States: published '
                       '1922. Text from Project Gutenberg.',
            'attribution': 'Maurice Platnauer (Loeb, 1922), '
                           'via Project Gutenberg',
            'n_units_stored': len(ulist), 'units': ulist,
            'ref_to_unit': ref2u,
        }, open(os.path.join(args.out_dir, f'la__{work}.json'), 'w'),
            ensure_ascii=False)


if __name__ == '__main__':
    main()
