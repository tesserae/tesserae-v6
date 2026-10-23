"""Write old_to_new_refs.json for the Shahnameh from the story ranges in stories.json.

The installed text had one running number per hemistich (1 to 99,218). The
re-tagged text reads <ferdowsi.shahnameh.S.C.H>: story S in Ganjoor's order,
couplet C inside the story, hemistich H (1 or 2). Each story in stories.json
records the old numbers it covers (old_first, old_last), and the stories are
contiguous, so the map follows from the ranges alone. The file is 3.7 MB and
is not committed; this script regenerates it byte for byte (sha256
0c29dc0dbebc0da7abd649e9ecda338a048d9f498265d93b1e42f770f826de44 on
2026-10-23).

Usage: python old_to_new_refs.py [stories.json] [old_to_new_refs.json]
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DEFAULT_IN = os.path.join(
    ROOT, "data", "text_structure", "ferdowsi.shahnameh", "stories.json"
)
DEFAULT_OUT = os.path.join(
    ROOT, "data", "text_structure", "ferdowsi.shahnameh", "old_to_new_refs.json"
)


def build(stories):
    out = {}
    expected = 1
    for st in stories:
        first, last = st["old_first"], st["old_last"]
        if first != expected:
            raise SystemExit(
                f"story {st['number']} starts at old line {first}, expected {expected}"
            )
        if last - first + 1 != 2 * st["n_couplets"]:
            raise SystemExit(
                f"story {st['number']} covers {last - first + 1} lines for {st['n_couplets']} couplets"
            )
        for i in range(first, last + 1):
            k = i - first
            out[str(i)] = f"ferdowsi.shahnameh.{st['number']}.{k // 2 + 1}.{k % 2 + 1}"
        expected = last + 1
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_IN
    dst = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT
    with open(src, encoding="utf-8") as f:
        stories = json.load(f)
    refs = build(stories)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(refs, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(refs)} references written to {dst}")


if __name__ == "__main__":
    main()
