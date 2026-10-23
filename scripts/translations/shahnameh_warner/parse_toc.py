import re
import json
import sys

base = sys.argv[1]
W = base + "/downloads/warner/"
ENT = re.compile(r"^\s*['‘]?([0-9iIl][0-9iIlO ]{0,3})[\.,]\s+(\S.*)$")


def isheader(t):
    t = re.sub(r"\s+", " ", t)
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return False
    up = sum(c.isupper() for c in letters) / len(letters)
    return (
        t.endswith(("—", "-", "–"))
        and not re.search(r"\.\s*\d+$", t)
        or up > 0.7
        or re.match(r"^(PART|Part)\s+[IVX]+", t)
        or "CONTENTS" in t
        or re.match(r"^(SECT|sect|PAGE|page|PAGK|PACK|FAOE)", t)
    )


out = []
for v in range(1, 10):
    lines = (
        open(W + f"vol{v}.txt", encoding="utf-8", errors="replace").read().split("\n")
    )
    cs = [
        i for i, line in enumerate(lines[:1500]) if line.strip().startswith("CONTENTS")
    ]
    s = cs[0]
    last = cs[-1]
    end = min(len(lines), last + 130)
    for i in range(last + 3, end):
        if re.match(r"^\s*(INDEX|ERRATA|THE\s+SHAHNAMA)\b", lines[i]):
            end = i
            break
    ents = []
    cur = None
    for line in lines[s:end]:
        t = line.strip()
        if not t:
            continue
        m = ENT.match(t)
        if m and not (cur is None and False):
            cur = {
                "title": m.group(2),
                "num": m.group(1)
                .replace(" ", "")
                .replace("i", "1")
                .replace("I", "1")
                .replace("l", "1")
                .replace("O", "0"),
                "vol": v,
            }
            ents.append(cur)
            continue
        if isheader(t):
            cur = None
            continue
        if cur is not None:
            cur["title"] += " " + t
    for e in ents:
        t = re.sub(r"\s+", " ", e["title"])
        pg = None
        m = re.search(r"(?:[ \.\-_·•']{2,}|\s)(\d[\d ]{0,5})\s*$", t)
        if m:
            pg = int(m.group(1).replace(" ", ""))
            t = t[: m.start()]
        e["title"] = re.sub(r"[\s\.\-_,'•·]+$", "", t).strip()
        e["page"] = pg
    out += ents
    nums = [e["num"] for e in ents]
    print(
        v,
        len(ents),
        "resets",
        sum(1 for e in ents if e["num"] == "1"),
        "nopage",
        sum(1 for e in ents if e["page"] is None),
    )
json.dump(out, open(base + "/warner_toc.json", "w"), ensure_ascii=False, indent=0)
