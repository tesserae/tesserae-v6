import os
import json
import sys
import math
import collections
import numpy as np

base = sys.argv[1]
stories = json.load(open(base + "/stories_raw.json"))
W = json.load(open(base + "/warner_stories.json"))
newt = [
    line.rstrip("\n").split("\t", 1)
    for line in open(base + "/ferdowsi.shahnameh.new.tess", encoding="utf-8")
]
bystory = collections.defaultdict(list)
for t, x in newt:
    bystory[int(t.strip("<>").split(".")[2])].append(x)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shahnameh_common import persian_tokens, warner_tokens  # noqa: E402

PT = [persian_tokens(st, bystory[st["number"]]) for st in stories]
WT = [warner_tokens(w) for w in W]
LEXP = sys.argv[7] if len(sys.argv) > 7 else None
WT = [collections.Counter(t) for t in WT]
if LEXP:
    import induce_lexicon as il

    LEX = json.load(open(LEXP))["lexicon"]
    VALS = set(LEX.values())
    for i, st in enumerate(stories):
        for line in bystory[st["number"]]:
            for t in line.split():
                e = LEX.get(il.norm_fa(t))
                if e:
                    PT[i]["@" + e] += 1
    for j, w in enumerate(W):
        for pa in w["paragraphs"]:
            for e in il.en_words(pa):
                if e in VALS:
                    WT[j]["@" + e] += 1
vocab = set().union(*[set(t) for t in WT]) & set().union(*[set(t) for t in PT])
print("vocab", len(vocab))
vl = sorted(vocab)
vi = {k: n for n, k in enumerate(vl)}
dfw = collections.Counter(k for t in WT for k in t if k in vocab)
dfp = collections.Counter(k for t in PT for k in t if k in vocab)
idf = np.array([math.log((len(WT) + len(PT)) / (1 + dfw[k] + dfp[k])) for k in vl])


def mat(T):
    M = np.zeros((len(T), len(vl)), dtype=np.float32)
    for r, t in enumerate(T):
        for k, v in t.items():
            if k in vi:
                M[r, vi[k]] = 1 + math.log(v)
    return M


MP = mat(PT) * idf
MW = mat(WT) * idf
CP = np.vstack([np.zeros(len(vl), np.float32), np.cumsum(MP, 0)])
CW = np.vstack([np.zeros(len(vl), np.float32), np.cumsum(MW, 0)])

B1, SK1, B2, SK2 = [float(x) for x in sys.argv[2:6]]
MAXM2 = int(sys.argv[6]) if len(sys.argv) > 6 else 12
BAND = float(sys.argv[10]) if len(sys.argv) > 10 else 0.06
MAXLR = float(sys.argv[8]) if len(sys.argv) > 8 else 1.6
EXPO = float(sys.argv[9]) if len(sys.argv) > 9 else 0.5


def dp(
    CPs,
    CWs,
    gcs,
    wws,
    B,
    SK,
    band,
    maxm=4,
    LAM=0.25,
    ratio_rule=True,
    force_start=False,
    force_end=False,
):
    nG = len(CPs) - 1
    nW = len(CWs) - 1
    r0 = wws[-1] / max(gcs[-1], 1)

    def cosf(i1, i2, j1, j2):
        a = CPs[i2] - CPs[i1]
        b = CWs[j2] - CWs[j1]
        d = np.linalg.norm(a) * np.linalg.norm(b)
        return float(a @ b / d) if d > 0 else 0.0

    moves = [
        (a, b)
        for a in range(1, maxm + 1)
        for b in range(1, maxm + 1)
        if (not ratio_rule) or max(a, b) <= 3 * min(a, b) + 1
    ]
    NEG = -1e9
    best = np.full((nG + 1, nW + 1), NEG)
    back = {}
    best[0, 0] = 0
    for i in range(nG + 1):
        for j in range(nW + 1):
            v = best[i, j]
            if v == NEG:
                continue
            skip_ok = not (force_start and i == 0 and j == 0)
            if (
                skip_ok
                and i < nG
                and v - SK > best[i + 1, j]
                and not (force_end and i + 1 == nG and j == nW)
            ):
                best[i + 1, j] = v - SK
                back[(i + 1, j)] = (i, j, "gskip")
            if (
                skip_ok
                and j < nW
                and v - SK > best[i, j + 1]
                and not (force_end and i == nG and j + 1 == nW)
            ):
                best[i, j + 1] = v - SK
                back[(i, j + 1)] = (i, j, "wskip")
            for a, b in moves:
                i2, j2 = i + a, j + b
                if i2 > nG or j2 > nW:
                    continue
                fg = gcs[i2] / gcs[-1]
                fw = wws[j2] / wws[-1]
                if abs(fg - fw) > band:
                    continue
                ng = gcs[i2] - gcs[i]
                nw = wws[j2] - wws[j]
                if ng <= 0 or nw <= 0:
                    continue
                lr = abs(math.log((nw / ng) / r0))
                if lr > math.log(MAXLR) and not (a == 1 and b == 1):
                    continue
                cs = cosf(i, i2, j, j2)
                sc = cs - LAM * lr
                val = v + (sc + B) * ((a + b) / 2) ** EXPO
                if val > best[i2, j2]:
                    best[i2, j2] = val
                    back[(i2, j2)] = (i, j, (a, b, sc, cs, (nw / ng) / r0))
    i, j = nG, nW
    path = []
    while (i, j) != (0, 0):
        pi, pj, m = back[(i, j)]
        path.append((pi, pj, i, j, m))
        i, j = pi, pj
    path.reverse()
    return path


# ---- hand-set cut points (a Ganjoor story that begins where a Warner section begins).
# Warner puts the chess story (Raja of Hind, Nard, Gav and Talhand) and Barzwi's journey in one run
# and the dynamic programme could not place the long Gav and Talhand section by the word-overlap
# score alone (checked by reading the titles and page counts: Ganjoor 714-721 hold 527 couplets,
# Warner's section holds 9,345 words, 17.7 words per couplet against 18.0 for the whole book).
PINS = [
    (13, 1, "The Greatness of Ga"),
    (712, 7, "How Buzurjmihr counselled Nushirwan"),
    (713, 7, "How the Raja of Hind sent the Game of Chess"),
    (714, 7, "The Story of Gav and Talhand"),
    (722, 7, "How Nushirwiin sent Barzwi"),
    (723, 8, "How Nushirwan was wroth with Buzurjmihr"),
]
pin_pos = []
for sn, vol, tp in PINS:
    wj = [k for k, w in enumerate(W) if w["vol"] == vol and w["title"].startswith(tp)]
    assert len(wj) == 1, (tp, wj)
    pin_pos.append((sn - 1, wj[0]))
# ---- one pass over the whole book, cut at the hand-set points
cutlist = sorted(pin_pos)
bounds = [(0, 0)] + cutlist + [(len(stories), len(W))]
CPall = np.vstack([np.zeros(MP.shape[1], np.float32), np.cumsum(MP, 0)])
CWall = np.vstack([np.zeros(MW.shape[1], np.float32), np.cumsum(MW, 0)])
gcs_all = np.array([0] + [x["n_couplets"] for x in stories]).cumsum()
wws_all = np.array([0] + [x["words"] for x in W]).cumsum()
path = []
for si, ((ga, wa), (gb, wb)) in enumerate(zip(bounds[:-1], bounds[1:])):
    if (ga, gb, wa, wb) == (0, 12, 0, 12):
        # The Prelude: Ganjoor's twelve opening sections and Warner's twelve Prelude sections are the
        # same twelve pieces in the same order (checked by reading the titles).
        for k in range(12):
            path.append((k, k, k + 1, k + 1, [1, 1, 0.0, 0.0, 1.0]))
        continue
    ss = dp(
        CPall[ga : gb + 1] - CPall[ga],
        CWall[wa : wb + 1] - CWall[wa],
        gcs_all[ga : gb + 1] - gcs_all[ga],
        wws_all[wa : wb + 1] - wws_all[wa],
        B2,
        SK2,
        BAND,
        maxm=MAXM2,
        ratio_rule=False,
        force_start=si > 0,
        force_end=si < len(bounds) - 2,
    )
    for a_, b_, c_, d_, mm in ss:
        if isinstance(mm, str):
            path.append(
                (
                    ga + a_ if mm == "gskip" else None,
                    wa + b_ if mm == "wskip" else None,
                    ga + c_ if mm == "gskip" else None,
                    wa + d_ if mm == "wskip" else None,
                    mm,
                )
            )
        else:
            path.append((ga + a_, wa + b_, ga + c_, wa + d_, list(mm)))
# Out-of-order pairs (Warner puts these episodes elsewhere than the Moscow text does; the monotone
# programme cannot match them, so they are set by hand when both sides came out unmatched).
MANUAL = [((616, 617), (7, "How Bahram, returning"))]
for sts, (vol, tp) in MANUAL:
    wj = [k for k, w in enumerate(W) if w["vol"] == vol and w["title"].startswith(tp)][
        0
    ]
    gi = [n - 1 for n in sts]
    free_g = all(any(r[4] == "gskip" and r[0] == g for r in path) for g in gi)
    free_w = any(r[4] == "wskip" and r[1] == wj for r in path)
    if free_g and free_w:
        path = [
            r
            for r in path
            if not (r[4] == "gskip" and r[0] in gi)
            and not (r[4] == "wskip" and r[1] == wj)
        ]
        nw = W[wj]["words"]
        ng = sum(stories[g]["n_couplets"] for g in gi)
        path.append(
            (
                gi[0],
                wj,
                gi[-1] + 1,
                wj + 1,
                [len(gi), 1, 0.0, 0.0, (nw / ng) / (wws_all[-1] / gcs_all[-1])],
            )
        )
        print("manual pair", sts, "<->", W[wj]["title"][:40])
json.dump(path, open(base + "/match_path2.json", "w"))
groups = [p for p in path if not isinstance(p[4], str)]
print(
    "groups",
    len(groups),
    "g matched",
    sum(p[2] - p[0] for p in groups),
    "of",
    len(stories),
    "w matched",
    sum(p[3] - p[1] for p in groups),
    "of",
    len(W),
)
