import re
import json
import sys

base = sys.argv[1]
W = base + "/downloads/warner/"
toc = json.load(open(base + "/warner_toc_located.json"))
RUNHEAD = [
    re.compile(r"^\s*\d{1,3}\s+THE\s+SHAHNAMA\s+OF\s+FIRD"),
    re.compile(r"^\s*THE\s+SHAHNAMA\s+OF\s+FIRD.{0,12}\s+\d{1,3}\s*$"),
    re.compile(r"^\s*[A-Z][A-Za-z ,'’\.\-\(\)]{3,45}\s+\d{1,3}\s*$"),
    re.compile(r"^\s*\d{1,3}\s+[A-Z][A-Z ,'’\.\-]{3,45}\s*$"),
    re.compile(r"^\s*THE\s+SHAHNAMA\s+OF\s+FIRDAUSI\s*$"),
]
PAGEONLY = re.compile(r"^\s*[\d\s]{1,5}\s*$")
SECT = re.compile(r"^\s*[§S8]\s*[§]?\s*[\dIOlio!]{1,3}\s*$|^\s*§")
FOOT = re.compile(r"^\s*[\dil]{1,2}\s+[A-Za-z\"“‘\'\-]|^\s*\d{1,3}\s*[;,\.]")
FOOT2 = re.compile(r"\(Mohl\)|Mohl\.\s*$|§|\b[A-Z]{2,5},\s+[ivx]+\.\s*\d")
JUNKLINE = re.compile(r"^[\s\dioOlIrjJ\|\]\[\.\-]{1,8}$")
CMARK = re.compile(r"(?:^|\s)[cC]\.\s*\d{3,4}\b")
LEADNUM = re.compile(r"^\s*\d{3,4}\s+(?=\S)")
MARGIN = re.compile(r"(?:^|[\s\"\'“])[vV][\.,]\s*[\dOolIiu]{1,5}\b")
import difflib  # noqa: E402


def is_runhead(t):
    n = re.sub(r"[^a-z]", "", t.lower())
    if len(n) < 32:
        return difflib.SequenceMatcher(None, n, "theshahnamaoffirdausi").ratio() > 0.72
    return False


def clean_lines(lines):
    out = []
    for line in lines:
        t = line.rstrip()
        if is_runhead(t):
            out.append("\x00")
            continue
        if not t.strip():
            out.append("")
            continue
        if PAGEONLY.match(t) or SECT.match(t):
            out.append("")
            continue
        if any(r.match(t) for r in RUNHEAD):
            out.append("\x00")
            continue
        if FOOT.match(t) or FOOT2.search(t):
            out.append("\x01")
            continue
        t = MARGIN.sub(" ", t)
        t = CMARK.sub(" ", t)
        if JUNKLINE.match(t) and re.search(r"[\dio]", t):
            out.append("")
            continue
        t = LEADNUM.sub("", t)
        out.append(re.sub(r"\s+", " ", t).strip())
    return out


def paragraphs(lines):
    cl = clean_lines(lines)
    paras = []
    cur = []
    for t in cl:
        if t == "\x00" or t == "\x01":
            continue
        if t == "":
            if cur:
                paras.append(cur)
                cur = []
            continue
        cur.append(t)
    if cur:
        paras.append(cur)

    # Warner's explanatory notes at the end of each reign are set in full-width prose lines
    # (mean line length above 54 characters, against about 41 for the verse): drop those blocks.
    def prose(b):
        m = sum(len(line) for line in b) / len(b)
        return (len(b) >= 2 and m >= 54) or (len(b) == 1 and m >= 62)

    paras = [b for b in paras if not prose(b)]
    # The OCR leaves a blank line inside stanzas and at page breaks, so blocks are joined
    # until one ends a sentence and holds at least MINW words.
    MINW = 30
    merged = []
    buf = []
    for p in paras:
        buf += p
        words = sum(len(line.split()) for line in buf)
        if words >= MINW and re.search(r'[\.\!\?]["”’»\)]*\s*$', buf[-1]):
            merged.append(buf)
            buf = []
    if buf:
        if merged and sum(len(line.split()) for line in buf) < MINW:
            merged[-1] += buf
        else:
            merged.append(buf)
    return [" / ".join(p) for p in merged]


allsec = []
for v in range(1, 10):
    lines = (
        open(W + f"vol{v}.txt", encoding="utf-8", errors="replace").read().split("\n")
    )
    ents = [e for e in toc if e["vol"] == v]
    if v == 1:
        for k, line in enumerate(lines):
            if (
                re.match(r"^\s*In\s+the\s+Name\s+of\s+God\s+the\s+Merciful", line)
                and k > 4000
            ):
                ents[0]["line"] = k
                ents[0]["ratio"] = 1.0
                break
    # interpolate missing
    idx = [k for k, e in enumerate(ents) if e["line"] is not None]
    for k, e in enumerate(ents):
        e["interpolated"] = False
        if e["line"] is None:
            lo = max([i for i in idx if i < k], default=None)
            hi = min([i for i in idx if i > k], default=None)
            if lo is None or hi is None:
                continue
            a, b = ents[lo], ents[hi]
            if (
                a["page"]
                and b["page"]
                and e["page"]
                and b["page"] > a["page"]
                and a["page"] <= e["page"] <= b["page"]
            ):
                f = (e["page"] - a["page"]) / (b["page"] - a["page"])
            else:
                f = (k - lo) / (hi - lo)
            e["line"] = int(a["line"] + f * (b["line"] - a["line"]))
            e["interpolated"] = True
    # fix non-monotone
    prev = -1
    for e in ents:
        if e["line"] is not None and e["line"] <= prev:
            e["line"] = prev + 1
            e["interpolated"] = True
        if e["line"] is not None:
            prev = e["line"]
    ents = [e for e in ents if e["line"] is not None]
    # end of volume body: the first line reading INDEX after the body has started
    endv = len(lines)
    for i in range(ents[0]["line"] + 500, len(lines)):
        if re.match(r"^\s*INDEX\s*$", lines[i]):
            endv = i
            break
    ents = [e for e in ents if e["line"] < endv]
    for k, e in enumerate(ents):
        s = e["line"]
        t = ents[k + 1]["line"] if k + 1 < len(ents) else endv
        body = lines[s:t]
        # drop heading lines: first non-blank lines up to blank
        i = 0
        while i < len(body) and not body[i].strip():
            i += 1
        j = i
        while j < len(body) and body[j].strip():
            j += 1
        e["paragraphs"] = paragraphs(body[j:])
        e["start_line"] = s
        e["end_line"] = t
        e["words"] = sum(len(p.split()) for p in e["paragraphs"])
        allsec.append(e)
    print(v, len(ents), "body lines", ents[0]["line"], endv)
for n, e in enumerate(allsec):
    e["id"] = n + 1
json.dump(allsec, open(base + "/warner_stories.json", "w"), ensure_ascii=False)
import statistics  # noqa: E402

print(
    len(allsec),
    "words total",
    sum(e["words"] for e in allsec),
    "median",
    statistics.median(e["words"] for e in allsec),
    "tiny(<60w)",
    sum(1 for e in allsec if e["words"] < 60),
    "interp",
    sum(1 for e in allsec if e["interpolated"]),
)
