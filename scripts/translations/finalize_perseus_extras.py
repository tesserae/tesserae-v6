#!/usr/bin/env python3
"""Check and label the files align_perseus.py wrote for works that are new to the
corpus since the 2026-08-27 build (Part C, 2026-10-24).

Run align_perseus.py into a staging folder, compact_for_serving.py over the files
you want, then this script over each. It re-measures the file against our own
text with the two checks of chapter_common.py (proper names, and length
correlation per unit), writes the same measurements and a `verified_by` line into
the file, and sorts it:

  OUT_DIR/         both checks (or one of them) clear the bar
  OUT_DIR/review/  neither does: nothing is installed from here without a reading

    finalize_perseus_extras.py OUT_DIR FILE.json [FILE.json ...]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import proper_names as V                                    # noqa: E402
from chapter_common import (load_work, unit_length_correlation, NAME_FLOOR,   # noqa: E402
                            LEN_FLOOR, MIN_NAMES)

out_dir = sys.argv[1]
for path in sys.argv[2:]:
    d = json.load(open(path))
    lang, stem = d['tess_work'].split('/')
    refs, src, _ = load_work(lang, stem)
    if not refs:
        print(f'{stem}: no such text in the corpus, skipped')
        continue
    r2u = {r: u for r, u in d['ref_to_unit'].items() if r in src}
    pairs = [(src[r], d['units'][u]) for r, u in r2u.items()]
    hit, n = V.score(pairs, lang, sample=800)
    corr = unit_length_correlation(d['units'], r2u, src)
    names_ok = hit is not None and n >= MIN_NAMES and hit >= NAME_FLOOR
    len_ok = corr is not None and corr >= LEN_FLOOR
    v = ['exact citation match (Perseus, identity verified by comparing the Greek text)']
    if names_ok:
        v.append(f'proper names {hit:.3f} on {n}')
    if len_ok:
        v.append(f'length correlation {corr:.3f}')
    d['verified_by'] = '; '.join(v)
    d['name_check_hit_rate'], d['name_check_n'] = hit, n
    d['unit_length_correlation'] = corr
    ok = names_ok or len_ok
    dest = out_dir if ok else os.path.join(out_dir, 'review')
    os.makedirs(dest, exist_ok=True)
    json.dump(d, open(os.path.join(dest, os.path.basename(path)), 'w'), ensure_ascii=False)
    print(f'{os.path.basename(path):55s} cov {len(r2u) / len(refs):.3f} units {len(d["units"])} '
          f'names {hit} on {n} length {corr} -> ' + ('ok' if ok else 'REVIEW'))
