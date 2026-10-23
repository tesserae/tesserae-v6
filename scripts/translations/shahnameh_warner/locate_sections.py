"""Find each table-of-contents title in the body of its volume (OCR text).

Candidates are short blocks of text set off by blank lines (a heading is one to three lines).
Titles and candidates are compared by letters only, and the titles are matched to
candidates in order by dynamic programming (a weighted longest common subsequence), so a
heading garbled by the OCR does not pull its neighbours out of place.
"""

import re
import json
import sys
import unicodedata
from rapidfuzz import fuzz

base = sys.argv[1]
W = base + "/downloads/warner/"
toc = json.load(open(base + "/warner_toc.json"))


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


THRESH = 72.0
for v in range(1, 10):
    lines = (
        open(W + f"vol{v}.txt", encoding="utf-8", errors="replace").read().split("\n")
    )
    cs = [
        i for i, line in enumerate(lines[:1500]) if line.strip().startswith("CONTENTS")
    ]
    start = cs[-1] + 100
    if v == 1:
        start = 5060
    # candidate blocks
    cands = []
    i = start
    n = len(lines)
    while i < n:
        if lines[i].strip():
            j = i
            while j < n and lines[j].strip():
                j += 1
            blk = lines[i:j]
            for k in (1, 2, 3, 4):
                if k > len(blk):
                    break
                txt = " ".join(re.sub(r"\s+", " ", line).strip() for line in blk[:k])
                if 6 <= len(txt) <= 200:
                    cands.append((i, norm(txt)))
            i = j
        else:
            i += 1
    ents = [e for e in toc if e["vol"] == v]
    tn = [norm(e["title"]) for e in ents]
    # score matrix lazily
    N, M = len(ents), len(cands)
    import numpy as np

    sc = np.zeros((N, M), dtype=np.float32)
    for a in range(N):
        t = tn[a]
        for b in range(M):
            c = cands[b][1]
            if not c:
                continue
            if len(t) < 8:
                r = 100.0 if c == t else 0.0
            else:
                # the heading may be followed by an argument or have lost words: compare to prefix of same length
                r = max(
                    fuzz.ratio(t, c),
                    fuzz.ratio(t, c[: len(t)]) if len(c) > len(t) else 0,
                )
                if 0.5 * len(t) <= len(c) < len(t):
                    r = max(
                        r, 0.9 * fuzz.partial_ratio(c, t)
                    )  # a heading broken over two blocks
            sc[a, b] = r if r >= THRESH else 0
    dp = np.zeros((N + 1, M + 1), dtype=np.float32)
    bk = np.zeros((N + 1, M + 1), dtype=np.int8)
    for a in range(1, N + 1):
        for b in range(1, M + 1):
            best = dp[a - 1, b]
            k = 1
            if dp[a, b - 1] > best:
                best = dp[a, b - 1]
                k = 2
            if sc[a - 1, b - 1] > 0 and dp[a - 1, b - 1] + sc[a - 1, b - 1] > best:
                best = dp[a - 1, b - 1] + sc[a - 1, b - 1]
                k = 3
            dp[a, b] = best
            bk[a, b] = k
    a, b = N, M
    found = {}
    while a > 0 and b > 0:
        k = bk[a, b]
        if k == 3:
            found[a - 1] = (cands[b - 1][0], float(sc[a - 1, b - 1]))
            a -= 1
            b -= 1
        elif k == 1:
            a -= 1
        else:
            b -= 1
    for a, e in enumerate(ents):
        if a in found:
            e["line"], e["ratio"] = found[a][0], round(found[a][1] / 100, 2)
        else:
            e["line"] = None
            e["ratio"] = None
    print(v, N, "candidates", M, "located", len(found))
json.dump(toc, open(base + "/warner_toc_located.json", "w"), ensure_ascii=False)
