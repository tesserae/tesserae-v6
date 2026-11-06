#!/usr/bin/env python3
"""Convert fetched Ganjoor books (ganjoor_fetch.py output) to .tess files.

Verse works put one hemistich on each line with the reference
`<work>.<major>.<couplet>.<hemistich>`: major is the book (daftar), chapter (bab)
or poem ordinal, couplet counts continuously inside the major unit (so the
Masnavi's couplet numbers run through a whole daftar as in Nicholson's
translation), hemistich is 1 or 2. Prose works put one paragraph on a line with
`<work>.<chapter>.<paragraph>`. Gulistan mixes both: `<work>.<bab>.<story>.<n>`
where n runs over the story's lines (a prose paragraph or one hemistich).

Also writes <work>.sections.json (title, first and last reference, Ganjoor poem
id, source name) for the Reader.

Usage:
    ganjoor_to_tess.py KIND SRC_DIR WORK OUT_DIR
KIND is one of masnavi, bustan, mantiq, gulistan, tazkirat.
"""

import json
import os
import re
import sys

DIACRITICS = re.compile("[ً-ٰٟـ‎‏]")


def clean(text):
    text = DIACRITICS.sub("", text)
    text = text.replace("ي", "ی").replace("ك", "ک").replace("ۀ", "ۀ")
    text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip("‌").strip()
    return text


def poems_in_order(node):
    for p in node["poems"]:
        yield node, p
    for ch in node["children"]:
        yield from poems_in_order(ch)


def load(src, pid):
    with open(os.path.join(src, "poems", f"{pid}.json"), encoding="utf-8") as f:
        return json.load(f)


def verse_lines(d):
    """[(couplet_index, hemistich 1/2, text)] from a poem's verses, in order."""
    out = []
    for v in sorted(d["verses"], key=lambda v: v["vOrder"]):
        t = clean(v["text"])
        if not t:
            continue
        pos = v["versePosition"]
        if pos == 0 and " / " in t:
            # a couplet stored as one verse, hemistichs separated by " / "
            a, b = (x.strip() for x in t.split(" / ", 1))
            out.append((v["coupletIndex"], 1, a, 0))
            out.append((v["coupletIndex"], 2, b, 1))
            continue
        out.append((v["coupletIndex"], 1 if pos == 0 else 2, t, pos))
    return out


def build_verse(kind, src, work):
    tree = json.load(open(os.path.join(src, "tree.json"), encoding="utf-8"))
    lines, sections = [], []
    if kind == "mantiq":
        # one major unit per poem
        items = []
        for i, (_, p) in enumerate(poems_in_order(tree), 1):
            items.append((i, [(tree, p)]))
    else:
        items = []
        kids = tree["children"]
        for i, ch in enumerate(kids):
            major = i + 1 if kind == "masnavi" else i  # bustan: 0 is the prologue
            items.append((major, list(poems_in_order(ch))))
    for major, plist in items:
        c = 0
        for _node, p in plist:
            d = load(src, p["id"])
            first = None
            for ci, h, t, pos in verse_lines(d):
                if pos not in (0, 1):
                    raise SystemExit(f"unexpected verse position {pos} in {p['id']}")
                if h == 1:
                    c += 1
                ref = f"{work}.{major}.{c}.{h}"
                lines.append((ref, t))
                first = first or ref
            sections.append(
                {
                    "major": major,
                    "title": d["title"],
                    "full_title": d["fullTitle"],
                    "ganjoor_poem_id": p["id"],
                    "first_ref": first,
                    "last_ref": lines[-1][0],
                    "source_name": d.get("sourceName"),
                }
            )
    return lines, sections


def build_gulistan(src, work):
    tree = json.load(open(os.path.join(src, "tree.json"), encoding="utf-8"))
    lines, sections = [], []
    groups = [(0, tree["poems"])] + [
        (i + 1, ch["poems"]) for i, ch in enumerate(tree["children"])
    ]
    for bab, plist in groups:
        for s, p in enumerate(plist, 1):
            d = load(src, p["id"])
            n = 0
            first = None
            vs = sorted(d["verses"], key=lambda v: v["vOrder"])
            i = 0
            while i < len(vs):
                v = vs[i]
                t = clean(v["text"])
                if v["versePosition"] == 0 and i + 1 < len(vs):
                    # keep a couplet together on one line, hemistichs joined by " | "
                    t2 = clean(vs[i + 1]["text"])
                    t = f"{t} | {t2}"
                    i += 1
                i += 1
                if not t:
                    continue
                n += 1
                ref = f"{work}.{bab}.{s}.{n}"
                lines.append((ref, t))
                first = first or ref
            sections.append(
                {
                    "major": bab,
                    "story": s,
                    "title": d["title"],
                    "ganjoor_poem_id": p["id"],
                    "first_ref": first,
                    "last_ref": lines[-1][0],
                    "source_name": d.get("sourceName"),
                }
            )
    return lines, sections


def build_tazkirat(src, work):
    tree = json.load(open(os.path.join(src, "tree.json"), encoding="utf-8"))
    lines, sections = [], []
    for ch, (_node, p) in enumerate(poems_in_order(tree), 1):
        d = load(src, p["id"])
        n = 0
        first = None
        vs = sorted(d["verses"], key=lambda v: v["vOrder"])
        i = 0
        while i < len(vs):
            v = vs[i]
            t = clean(v["text"])
            if v["versePosition"] == 0 and i + 1 < len(vs):
                t = f"{t} | {clean(vs[i + 1]['text'])}"
                i += 1
            i += 1
            if not t:
                continue
            n += 1
            ref = f"{work}.{ch}.{n}"
            lines.append((ref, t))
            first = first or ref
        sections.append(
            {
                "major": ch,
                "title": d["title"],
                "ganjoor_poem_id": p["id"],
                "first_ref": first,
                "last_ref": lines[-1][0],
                "source_name": d.get("sourceName"),
            }
        )
    return lines, sections


def main():
    kind, src, work, out = sys.argv[1:5]
    if kind in ("masnavi", "bustan", "mantiq"):
        lines, sections = build_verse(kind, src, work)
    elif kind == "gulistan":
        lines, sections = build_gulistan(src, work)
    elif kind == "tazkirat":
        lines, sections = build_tazkirat(src, work)
    else:
        raise SystemExit("unknown kind")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, work + ".tess"), "w", encoding="utf-8") as f:
        for ref, t in lines:
            f.write(f"<{ref}>\t{t}\n")
    with open(os.path.join(out, work + ".sections.json"), "w", encoding="utf-8") as f:
        json.dump(sections, f, ensure_ascii=False, indent=1)
    print(work, len(lines), "lines", len(sections), "sections")


if __name__ == "__main__":
    main()
