#!/usr/bin/env python3
"""
Re-shape each aligned file so a translation unit is stored once and our refs point at it.
Range alignments repeat the same English passage across every source line it covers, so
the naive form is many times larger than the text it holds: 3.75 GB becomes 59 MB.

THIS STEP IS NOT OPTIONAL. backend/translations.py reads `units` and `ref_to_unit`
and nothing else, so an alignment installed without being compacted first loads
without error and answers every request with "this work has a translation, but
not for the selected lines."

Output per work:
  {..., "units": ["...English...", ...], "ref_to_unit": {"<our ref>": unit_index}}

Usage:
    python compact_for_serving.py <directory of aligned .json files>
"""
import json, glob, os, sys, collections

# The directory of aligned files to reshape, in place. Given as the first
# argument, because this runs against whichever build was just produced.
OUT = (sys.argv[1] if len(sys.argv) > 1
       else os.environ.get("TESSERAE_TRANS_OUT",
                           "/home/ncoffee/perseus_trans/translations_v3"))


def main():
    total_before = total_after = 0
    n = 0
    for p in sorted(glob.glob(f"{OUT}/*.json")):
        if os.path.basename(p) in ("manifest.json", "poc_iliad.json"):
            continue
        total_before += os.path.getsize(p)
        d = json.load(open(p))
        tr = d.pop("translations", None)
        if tr is None:
            total_after += os.path.getsize(p)
            continue
        units, idx, ref2u = [], {}, {}
        for ref, txt in tr.items():
            if txt not in idx:
                idx[txt] = len(units)
                units.append(txt)
            ref2u[ref] = idx[txt]
        d["n_units_stored"] = len(units)
        d["units"] = units
        d["ref_to_unit"] = ref2u
        json.dump(d, open(p, "w"), ensure_ascii=False)
        total_after += os.path.getsize(p)
        n += 1
    print("files compacted:", n)
    print("before: %.1f MB  after: %.1f MB" % (total_before / 1e6, total_after / 1e6))


if __name__ == "__main__":
    main()
