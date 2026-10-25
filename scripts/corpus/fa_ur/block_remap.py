#!/usr/bin/env python3
"""Find a work inside a held diwan file and map its old references to the new file.

Several diwan files (Ganjoor's Chronological Persian Poetry Dataset) carry whole
books as one contiguous block: the Masnavi inside rumi.diwan, the Bustan and the
Gulistan inside saadi.diwan, the Mantiq al-Tayr and the Tazkirat al-Awliya inside
attar.diwan. This script aligns the held block with the freshly converted work
line by line (difflib on the text with diacritics and punctuation removed) and
writes:

  <out>/<work>.old_to_new.json   {"saadi.diwan.12001": "saadi.bustan.1.1.1", ...}
  <out>/<work>.block.json        first and last old ref of the block, counts of
                                 matched and unmatched old lines, unmatched new
                                 lines, and the unmatched old refs inside the block
                                 (they leave with the block, they have no
                                 counterpart in the new text)

Nothing is written to any text store. Running it is the planning step of the split.

Usage:
    block_remap.py HELD.tess NEW.tess OUT_DIR
"""

import difflib
import json
import os
import re
import sys

DIACRITICS = re.compile("[ً-ٰٟـ‎‏]")


def norm(s):
    s = DIACRITICS.sub("", s)
    s = s.replace("ي", "ی").replace("ك", "ک").replace("‌", " ").replace("|", " ")
    s = re.sub(r"[^\w\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def read(path):
    out = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"<([^>]+)>\t(.*)", line.rstrip("\n"))
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def main():
    held_p, new_p, out = sys.argv[1:4]
    held, new = read(held_p), read(new_p)
    work = os.path.basename(new_p)[: -len(".tess")]
    # Compare the new work's lines with the held lines. A new line that holds a
    # couplet joined by " | " is compared against one or two consecutive held lines.
    hn = [norm(t) for _, t in held]
    nn = [norm(t) for _, t in new]
    # Seed: unique exact matches fix where in the held file the block lies.
    pos = {}
    for i, k in enumerate(hn):
        pos.setdefault(k, []).append(i)
    hits = sorted(pos[k][0] for k in nn if k in pos and len(pos[k]) == 1)
    if not hits:
        raise SystemExit("no exact matches: the work is not in this file")
    lo = hits[len(hits) // 200]
    hi = hits[-1 - len(hits) // 200]
    pad = max(500, (hi - lo) // 20)
    lo, hi = max(0, lo - pad), min(len(hn) - 1, hi + pad)
    sm = difflib.SequenceMatcher(None, hn[lo : hi + 1], nn, autojunk=False)
    old_to_new, matched_new = {}, set()
    for a, b, n in sm.get_matching_blocks():
        for k in range(n):
            old_to_new[held[lo + a + k][0]] = new[b + k][0]
            matched_new.add(b + k)
    idx = [i for i, (r, _) in enumerate(held) if r in old_to_new]
    first, last = min(idx), max(idx)
    inside = [held[i][0] for i in range(first, last + 1) if held[i][0] not in old_to_new]
    report = {
        "work": work,
        "held_file": os.path.basename(held_p),
        "held_lines": len(held),
        "new_lines": len(new),
        "block_first_ref": held[first][0],
        "block_last_ref": held[last][0],
        "block_lines": last - first + 1,
        "matched": len(old_to_new),
        "old_unmatched_inside_block": len(inside),
        "new_unmatched": len(new) - len(matched_new),
        "unmatched_old_refs": inside,
        "unmatched_new_refs": [new[i][0] for i in range(len(new)) if i not in matched_new],
    }
    os.makedirs(out, exist_ok=True)
    json.dump(old_to_new, open(os.path.join(out, work + ".old_to_new.json"), "w"))
    json.dump(report, open(os.path.join(out, work + ".block.json"), "w"), ensure_ascii=False)
    print({k: v for k, v in report.items() if not k.startswith("unmatched_")})


if __name__ == "__main__":
    main()
