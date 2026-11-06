#!/usr/bin/env python3
"""Lay a new alignment over an installed one, keeping both translators (`unit_sources`).

Part F of the 2026-10-24 translation batch. Some works have an installed
translation that is coarse or partial (Whiston for Josephus, Bostock for Pliny,
Duff plus Kline for Silius) and a finer alignment to put over it where it
exists. The served format lets one file hold several translators: `sources` is
the list, `unit_sources[i]` names the source of unit i (backend/translations.py).

    merge_unit_sources.py BASE.json NEW.json OUT.json

BASE is a copy of the installed file (read only, never edited in place), NEW the
staged alignment. Every reference NEW covers takes NEW's unit, every other
reference keeps BASE's. Base units no reference points at any more are dropped.
Nothing is installed by this script.
"""
import json
import sys


def merge(base, new):
    bsrc = base.get('sources') or []
    nsrc = new.get('sources') or []
    bus = base.get('unit_sources')
    units, ref2u, usrc, remap = [], {}, [], {}
    over = set(new['ref_to_unit'])
    for ref, i in base['ref_to_unit'].items():
        if ref in over:
            continue
        if i not in remap:
            remap[i] = len(units)
            units.append(base['units'][i])
            usrc.append(bus[i] if bus else 0)
        ref2u[ref] = remap[i]
    nus = new.get('unit_sources')
    nmap = {}
    for ref, i in new['ref_to_unit'].items():
        if i not in nmap:
            nmap[i] = len(units)
            units.append(new['units'][i])
            usrc.append(len(bsrc) + (nus[i] if nus else 0))
        ref2u[ref] = nmap[i]
    out = dict(base)
    out['sources'] = list(bsrc) + list(nsrc)
    out['units'] = units
    out['ref_to_unit'] = ref2u
    out['unit_sources'] = usrc
    out['n_units_stored'] = len(units)
    n_refs = base.get('n_tess_refs') or len(ref2u)
    out['n_translated'] = len(ref2u)
    out['coverage'] = round(len(ref2u) / n_refs, 4) if n_refs else 0.0
    out['mean_source_lines_per_translation_unit'] = round(len(ref2u) / len(units), 2) if units else 0
    conf = {'high': 2, 'exact': 3, 'medium': 1, 'low': 0}
    a, b = base.get('alignment_confidence', 'medium'), new.get('alignment_confidence', 'medium')
    out['alignment_confidence'] = a if conf.get(a, 1) <= conf.get(b, 1) else b
    out['license'] = (base.get('license') or '').rstrip('. ') + '. ' + (new.get('license') or '')
    out['attribution'] = ' and '.join(x for x in (base.get('attribution'), new.get('attribution')) if x)
    # the checks describe the alignment that was laid over, with the earlier file's own kept beside them
    for k in ('name_check_hit_rate', 'name_check_n', 'length_correlation', 'verified_by'):
        if k in base:
            out['earlier_' + k] = base[k]
        if k in new:
            out[k] = new[k]
        else:
            out.pop(k, None)
    out['n_refs_from_new_alignment'] = len(over)
    out['notes'] = (f"{len(over)} references take the {nsrc[0].get('translator') if nsrc else 'new'} alignment "
                    f"laid over the earlier file by merge_unit_sources.py; every other reference keeps the earlier unit.")
    return out


if __name__ == '__main__':
    base = json.load(open(sys.argv[1]))
    new = json.load(open(sys.argv[2]))
    out = merge(base, new)
    json.dump(out, open(sys.argv[3], 'w'), ensure_ascii=False)
    print(f"merged: {out['n_translated']} of {out['n_tess_refs']} refs, {out['n_units_stored']} units, "
          f"{len(out['sources'])} sources")
