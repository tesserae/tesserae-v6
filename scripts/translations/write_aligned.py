#!/usr/bin/env python3
"""Write an aligned translation file in the served (compact) shape.

backend/translations.py reads `units` (a list of English strings) and
`ref_to_unit` (our line reference -> index into units) and nothing else, so
this writes that shape directly, plus the metadata fields the earlier Latin
and Greek aligners record (see la__juvenal.satires.json on production).

    from write_aligned import write_aligned
    write_aligned(out_dir, language, work_stem, units, ref_to_unit,
                  attribution=..., license=..., sources=[...],
                  confidence='exact'|'high'|'medium', approximate=False,
                  tess_refs=[all refs of the work, for coverage])

The file is named <language>__<work_stem>.json. Nothing is written when a
unit list is empty or ref_to_unit points outside it.
"""
import json
import os


def write_aligned(out_dir, language, work_stem, units, ref_to_unit, *, attribution,
                  license, sources, confidence='medium', approximate=True,
                  tess_refs=None, name_check=None, verified_by=None, notes=None):
    if not units:
        raise ValueError(f'{work_stem}: no units')
    bad = [r for r, i in ref_to_unit.items() if not (0 <= i < len(units))]
    if bad:
        raise ValueError(f'{work_stem}: {len(bad)} refs point outside the unit list, e.g. {bad[:3]}')
    # backend/translations.py reads sources[0] as a dict (translator, year).
    sources = [s if isinstance(s, dict) else {'url': s} for s in (sources or [])]
    n_refs = len(tess_refs) if tess_refs else len(ref_to_unit)
    covered = len([r for r in (tess_refs or ref_to_unit) if r in ref_to_unit])
    record = {
        'tess_work': f'{language}/{work_stem}',
        'language': language,
        'n_tess_refs': n_refs,
        'n_translated': covered,
        'coverage': round(covered / n_refs, 4) if n_refs else 0.0,
        'mean_source_lines_per_translation_unit': round(covered / len(units), 2),
        'alignment_confidence': confidence,
        'approximate': approximate,
        'sources': sources,
        'license': license,
        'attribution': attribution,
        'n_units_stored': len(units),
        'units': units,
        'ref_to_unit': ref_to_unit,
    }
    if name_check:
        record.update(name_check)
    if verified_by:
        record['verified_by'] = verified_by
    if notes:
        record['notes'] = notes
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f'{language}__{work_stem}.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(record, f, ensure_ascii=False)
    return path


def tess_refs(path):
    """All line references of a .tess file, in order, without the angle brackets."""
    out = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            if line.startswith('<') and '>' in line:
                out.append(line[1:line.index('>')].strip())
    return out
