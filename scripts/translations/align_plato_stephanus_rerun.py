#!/usr/bin/env python3
"""The earlier Plato files re-run with the page-break rule (Part H, 2026-10-25).

The 27 Plato translation files installed from the Perseus TEI before Part G were paired by exact Stephanus key,
which drops the bare page-number chunks Perseus uses for the Loeb's page breaks (see `stephanus_text` in
g_common.py). For each file this script reads the installed file's Perseus URN and translator, takes the same
Perseus record, pairs again with the page-break rule, runs the Part G checks, and compares the result with the
installed file reference by reference. A new file is a candidate for install only under the rule in `decide`;
otherwise it is written to OUT_DIR/review/ with the reason, and the installed file stays.

    align_plato_stephanus_rerun.py OUT_DIR [--dry] [--only STEM] [--installed DIR] [--log DIR]

The comparison goes to LOG_DIR/compare.tsv (default: next to OUT_DIR, in ../logs).
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from g_common import (load_work, tail, finish, perseus_records, stephanus_text, pair_by_key,   # noqa: E402
                      source_dict, license_for)

INSTALLED = '/var/www/tesseraev6_flask/data/translations'
NAME_TOLERANCE = 0.02


def words(t):
    return len((t or '').split())


def compare_units(old, new):
    """old, new: {ref: English}. -> dict with the references whose English grew, shrank, was lost or gained."""
    grew, shrank, lost, gained = [], [], [], []
    for r in sorted(set(old) | set(new)):
        o, n = old.get(r), new.get(r)
        if o and not n:
            lost.append(r)
        elif n and not o:
            gained.append(r)
        elif o and n:
            d = words(n) - words(o)
            if d > 0:
                grew.append((r, d))
            elif d < 0:
                shrank.append((r, d))
    return {'grew': grew, 'shrank': shrank, 'lost': lost, 'gained': gained,
            'words_gained': sum(d for _, d in grew) + sum(words(new[r]) for r in gained)}


def decide(old_cov, new_cov, old_names, new_names, cmp):
    """-> (is_candidate, reasons). The rule of the spec: coverage not lower, names not lower by more than
    0.02, and no unit lost English (a reference that lost all of its English, or whose English got shorter)."""
    why = []
    if new_cov < old_cov:
        why.append(f'coverage fell {old_cov:.4f} to {new_cov:.4f}')
    if old_names is not None and new_names is not None and new_names < old_names - NAME_TOLERANCE:
        why.append(f'names fell {old_names:.3f} to {new_names:.3f}')
    if cmp['lost']:
        why.append(f'{len(cmp["lost"])} references lost their English')
    if cmp['shrank']:
        why.append(f'{len(cmp["shrank"])} units shrank')
    return (not why), why


def relabel_bare_chunks(rec, our_keys):
    """A copy of the Perseus record in which a bare page number takes the label of one of OUR sections that Perseus
    leaves out, when there is one between the section before it and the section N+'a' that follows it.

    `stephanus_text` reads a bare number N as the tail of the chunk before it. That is wrong when the Loeb's page
    break falls at the start of a Stephanus section Perseus does not label (Menexenus: the chunk marked '235' is
    section 234c, and joining it to 234b put 92 words of 234c's English into 234b). Our references name the
    missing section; the bare chunk then stands for it. Returns (record, [(bare, new label), ...])."""
    pos = {k: i for i, k in enumerate(our_keys)}
    lettered = {c['anchors']['section'] for c in rec['chunks']
                if c['anchors'].get('section') and not c['anchors']['section'].isdigit()}
    chunks, moved, last = [], [], None
    for c in rec['chunks']:
        sec = c['anchors'].get('section')
        if sec and sec.isdigit() and (sec + 'a') in lettered and last in pos and (sec + 'a') in pos:
            gap = [k for k in our_keys[pos[last] + 1:pos[sec + 'a']] if k not in lettered]
            if gap:
                c = {**c, 'anchors': {**c['anchors'], 'section': gap[0]}}
                moved.append((sec, gap[0]))
                sec = gap[0]
                lettered.add(sec)
        if sec and not sec.isdigit():
            last = sec
        chunks.append(c)
    return {**rec, 'chunks': chunks}, moved


def english_by_ref(units, r2u):
    return {r: units[i] for r, i in r2u.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out_dir')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--only')
    ap.add_argument('--installed', default=INSTALLED)
    ap.add_argument('--log')
    a = ap.parse_args()
    log_dir = a.log or os.path.join(os.path.dirname(os.path.abspath(a.out_dir)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    by_urn = {r['meta'].get('cts_urn'): r for r in perseus_records() if r['meta'].get('author') == 'Plato'}
    rows = []
    for path in sorted(glob.glob(os.path.join(a.installed, 'grc__plato.*.json'))):
        stem = os.path.basename(path)[5:-5]
        if a.only and stem != a.only:
            continue
        inst = json.load(open(path))
        s0 = inst['sources'][0]
        urn = s0.get('cts_urn')
        if not urn or stem == 'plato.leges':
            continue                       # Part G files carry no URN; the Laws have their own script
        rec = by_urn[urn]
        year = rec['meta']['year']
        if year >= 1931:
            raise SystemExit(f'{stem}: volume dated {year}, renewal check needed; stopping')
        refs, src, _ = load_work('grc', stem)
        rec, moved = relabel_bare_chunks(rec, [tail(r) for r in refs])
        english = {k[1]: t for k, t in stephanus_text(rec).items()}
        units, r2u, _ = pair_by_key(refs, tail, english, share_previous=False)
        translator = s0['translator']
        title = f'Plato, {rec["meta"]["title"]} (Loeb Classical Library, Plato in Twelve Volumes)'
        sd = source_dict(translator, year, title, 'https://www.perseus.tufts.edu/', ref_composition=['stephanus section'],
                         scan=f'by date (published {year}), no title page read')
        sd['cts_urn'] = urn
        sd['source_file'] = rec['meta'].get('source_file')
        kw = dict(mode='exact', exact=True,
                  attribution=f'{translator}, {title}; Perseus Digital Library, Tufts University (TEI markup, CC BY-SA 4.0)',
                  license=license_for(year), sources=[sd],
                  notes=f'One unit per Stephanus section, from Perseus {urn}, paired with the page-break rule '
                        f'(Part H). {len(refs) - len(r2u)} references of ours have no section of that number in Perseus and stay unpaired.')
        res = finish('grc', stem, units, r2u, refs, src, out_dir=a.out_dir, dry=True, **kw)
        old_en = english_by_ref([inst_u for inst_u in inst['units']], inst['ref_to_unit'])
        cmp = compare_units(old_en, english_by_ref(units, r2u))
        ok, why = decide(inst['coverage'], res['coverage'], inst.get('name_check_hit_rate'), res['names'], cmp)
        if not res['accepted']:
            ok, why = False, why + ['Part G checks refuse the new file']
        dest = a.out_dir if ok else os.path.join(a.out_dir, 'review')
        held = False
        if not a.dry and not res['accepted']:
            # Held for reading, as the Lovers were in Part G: fewer than 20 names to test and a length correlation under
            # 0.8, so no check vouches for it; the pairing rests on the exact Stephanus keys. Lower name floor, review/ only.
            held = True
            res2 = finish('grc', stem, units, r2u, refs, src, out_dir=dest, dry=False, min_names=8,
                          extra_evidence='HELD: the name check had fewer than 20 names to test and the length correlation is '
                                         'under 0.8; the pairing rests on the exact Stephanus section numbers and on reading', **kw)
            if not res2['accepted']:
                why.append('refused even at the lower name floor')
        if not a.dry and (res['accepted'] or held):
            if res['accepted']:
                finish('grc', stem, units, r2u, refs, src, out_dir=dest, dry=False, **kw)
            if not ok:
                json.dump({'stem': stem, 'reasons': why, 'shrank': cmp['shrank'], 'lost': cmp['lost']},
                          open(os.path.join(dest, f'{stem}.reason.json'), 'w'), indent=1)
        rows.append(dict(work=stem, old_cov=inst['coverage'], new_cov=res['coverage'], old_refs=inst['n_translated'],
                         new_refs=res['translated'], old_names=inst.get('name_check_hit_rate'), new_names=res['names'],
                         grew=len(cmp['grew']), words=cmp['words_gained'], gained=len(cmp['gained']),
                         shrank=len(cmp['shrank']), lost=len(cmp['lost']), corr=res['length_corr'], rival=res['rival_own_best'],
                         relabeled=len(moved), relabeled_refs=' '.join(f'{b}>{m}' for b, m in moved), candidate='yes' if ok else 'no', why='; '.join(why),
                         shrank_refs=' '.join(f'{r}({d})' for r, d in cmp['shrank'][:20])))
    if rows:
        cols = list(rows[0])
        with open(os.path.join(log_dir, 'compare.tsv'), 'w') as f:
            f.write('\t'.join(cols) + '\n')
            for r in rows:
                f.write('\t'.join('' if r[c] is None else str(r[c]) for c in cols) + '\n')
        print('wrote', os.path.join(log_dir, 'compare.tsv'))


if __name__ == '__main__':
    main()
