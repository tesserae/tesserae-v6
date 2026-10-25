#!/usr/bin/env python3
"""Merge two aligned files of one work into one file with `unit_sources`.

Where two translators cover different parts of a work (Pausanias: the Loeb volume that is already
installed covers books 6 to 8.21, a Bohn translation covers every book), each reference takes the
PRIMARY file's unit when the primary covers it and the SECONDARY file's unit otherwise. The merged
file lists both sources, with a `unit_sources` entry (an index into `sources`) for every unit, which is
what backend/translations.py reads to credit the translator whose words are on the screen.

    merge_translation_files.py PRIMARY.json SECONDARY.json OUT.json

Every source in the output carries a `license`: its own when the input source had one, else the
file-level license of the input file it came from. The file-level `license` is one sentence that names
each source with its license. The coverage fields are recomputed from our own text (chapter_common.load_work). Nothing is written when
the two files name different works.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chapter_common import load_work   # noqa: E402


def _label(src):
    """A short name for a source in the file-level sentence."""
    return src.get('translator') or src.get('title') or src.get('name') or 'unnamed translation'


def with_licenses(sources, file_license):
    """Copies of the sources, each with its own license, else the input file's license."""
    out = []
    for s in sources:
        s = dict(s)
        if not s.get('license') and file_license:
            s['license'] = file_license
        out.append(s)
    return out


def license_sentence(sources):
    """One sentence naming each source with its license."""
    parts = []
    for s in sources:                              # a translator with several volumes is named once per license
        if s.get('license'):
            item = f"{_label(s)}: {s['license']}"
            if item not in parts:
                parts.append(item)
    return '; '.join(parts) + '.' if parts else ''


def merge(a, b, refs):
    """The merged file for two aligned files of one work; refs is the work's reference list in order."""
    sa, sb = a.get('sources') or [{}], b.get('sources') or [{}]
    sa, sb = with_licenses(sa, a.get('license')), with_licenses(sb, b.get('license'))
    units, unit_sources, ref_to_unit = [], [], {}
    index = {}                                    # (which file, unit index) -> merged unit index
    taken = {'primary': 0, 'secondary': 0}
    for r in refs:
        if r in a['ref_to_unit']:
            which, u = 'primary', a['ref_to_unit'][r]
        elif r in b['ref_to_unit']:
            which, u = 'secondary', b['ref_to_unit'][r]
        else:
            continue
        key = (which, u)
        if key not in index:
            index[key] = len(units)
            if which == 'primary':
                units.append(a['units'][u])
                unit_sources.append((a.get('unit_sources') or [0] * len(a['units']))[u])
            else:
                units.append(b['units'][u])
                unit_sources.append(len(sa) + (b.get('unit_sources') or [0] * len(b['units']))[u])
        ref_to_unit[r] = index[key]
        taken[which] += 1
    sources = sa + sb
    out = dict(a)
    out.update({
        'sources': sources,
        'units': units, 'n_units_stored': len(units), 'unit_sources': unit_sources, 'ref_to_unit': ref_to_unit,
        'n_tess_refs': len(refs), 'n_translated': len(ref_to_unit),
        'coverage': round(len(ref_to_unit) / len(refs), 4) if refs else 0.0,
        'mean_source_lines_per_translation_unit': round(len(ref_to_unit) / max(1, len(units)), 2),
        'attribution': '; '.join(x for x in (a.get('attribution'), b.get('attribution')) if x),
        'license': license_sentence(sources),
        'approximate': bool(a.get('approximate') or b.get('approximate')),
        'verified_by': f"primary: {a.get('verified_by')}; secondary: {b.get('verified_by')}",
        'notes': f"{taken['primary']} references from the first file, {taken['secondary']} from the second. " + (b.get('notes') or ''),
    })
    return out, taken


def main():
    primary_path, secondary_path, out_path = sys.argv[1:4]
    a = json.load(open(primary_path))
    b = json.load(open(secondary_path))
    if a['tess_work'] != b['tess_work']:
        sys.exit(f"different works: {a['tess_work']} and {b['tess_work']}")
    lang, stem = a['tess_work'].split('/')
    refs, src, _ = load_work(lang, stem)
    out, taken = merge(a, b, refs)
    json.dump(out, open(out_path, 'w'), ensure_ascii=False)
    print(f"{a['tess_work']}: {taken['primary']} references from the primary, {taken['secondary']} from the secondary, "
          f"coverage {out['coverage']} of {len(refs)}")


if __name__ == '__main__':
    main()
