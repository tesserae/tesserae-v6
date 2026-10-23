#!/usr/bin/env python3
"""Align A. G. and E. Warner's Shahnama (1905-1925, public domain) to the Persian text,
story by story, in the served translation shape (see write_aligned.py).

Inputs (all produced by the scripts beside this one, run in the order in
shahnameh_warner/run_pipeline.sh): the restructured text, the Ganjoor story list, Warner's
sections with their paragraphs, and the story match path.

For each matched group (a run of Persian stories against a run of Warner sections) the
Warner paragraphs are laid along the group's couplets in proportion to length, with
anchors at proper names that occur exactly once on each side (Rustam, Zal, Kai Khusrau
and so on, compared by consonant skeleton, see match_stories.py), kept in order and
thinned until every segment between anchors has a plausible length ratio. Each couplet
takes the paragraph that covers its midpoint. A paragraph that receives no couplet is
joined to the unit before it, so no translated text is dropped.

Usage:
    python align_shahnameh_warner.py --work DIR --tess FILE --out-dir DIR
"""

import argparse
import collections
import json
import math
import os
import re
import sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "shahnameh_warner"))
import shahnameh_common as ms  # consonant-skeleton helpers and name extraction  # noqa: E402


def couplets_of(tess):
    """[(story_number, [ref1, ref2], [line1, line2])] in order."""
    by = collections.OrderedDict()
    for tag, txt in tess:
        parts = tag.strip("<>").split(".")
        s, c = int(parts[2]), int(parts[3])
        by.setdefault((s, c), []).append((tag.strip("<>"), txt))
    return [(s, [r for r, _ in v], [t for _, t in v]) for (s, c), v in by.items()]


def name_stream_w(wp):
    """[(skeleton, position as a fraction of the group's words)] for capitalised names."""
    tot = sum(len(p.split()) for p in wp) or 1
    out = []
    off = 0
    for p in wp:
        for m in re.finditer(
            r"(?<![\.\!\?\"”“/:;] )(?<!^)\b([A-Z][a-z\u00c0-\u024f'’\-]{2,})", p
        ):
            w = m.group(1)
            if w in ms.STOP:
                continue
            k = ms.lat_skel(w)
            if len(k) >= 3:
                out.append((k, (off + len(p[: m.start()].split()) + 0.5) / tot))
        off += len(p.split())
    return out


def name_stream_p(pc, keys):
    nc = len(pc)
    out = []
    for k, (_, _, lines) in enumerate(pc):
        for t in " ".join(lines).split():
            sk = ms.pers_skel(t)
            if sk in keys:
                out.append((sk, (k + 0.5) / nc))
    return out


def anchors(pc, wp, df_p, df_w, band=0.12):
    """Anchors (w_fraction, p_fraction): a weighted longest common subsequence of the name
    sequences of the two sides (names compared by consonant skeleton), kept inside a band
    around the diagonal, then cleaned of outliers by a running median of the residuals."""
    A = name_stream_w(wp)
    keys = set(k for k, _ in A)
    B = name_stream_p(pc, keys)
    if not A or not B:
        return [(0.0, 0.0), (1.0, 1.0)], 0
    wt = {k: 1.0 / math.log(2.5 + df_w.get(k, 1) + df_p.get(k, 1)) for k in keys}
    n = len(A)
    bpos = [b[1] for b in B]
    import bisect

    lo = [bisect.bisect_left(bpos, A[i][1] - band) for i in range(n)]
    hi = [bisect.bisect_right(bpos, A[i][1] + band) for i in range(n)]
    # dp[i][j] over j in [lo_i, hi_i); store as lists with offset
    dp_prev = None
    lo_prev = 0
    cells = []
    for i in range(n):
        li, hi_i = lo[i], hi[i]
        row = [0.0] * (hi_i - li)
        bk = [0] * (hi_i - li)
        for j in range(li, hi_i):
            best = 0.0
            b = 0
            # up (i-1, j)
            if dp_prev is not None and lo_prev <= j < lo_prev + len(dp_prev):
                v = dp_prev[j - lo_prev]
                if v > best:
                    best = v
                    b = 1
            # left (i, j-1)
            if j - 1 >= li:
                v = row[j - 1 - li]
                if v > best:
                    best = v
                    b = 2
            # diag
            if A[i][0] == B[j][0]:
                dv = 0.0
                if dp_prev is not None and lo_prev <= j - 1 < lo_prev + len(dp_prev):
                    dv = dp_prev[j - 1 - lo_prev]
                v = dv + wt[A[i][0]]
                if v > best:
                    best = v
                    b = 3
            row[j - li] = best
            bk[j - li] = b
        cells.append((li, bk))
        dp_prev = row
        lo_prev = li
    # backtrace from the best cell of the last rows
    i = n - 1
    j = lo[i] + len(cells[i][1]) - 1
    pairs = []
    while i >= 0 and j >= 0:
        li, bk = cells[i]
        if not (li <= j < li + len(bk)):
            # fell outside the band of row i: step up
            i -= 1
            continue
        b = bk[j - li]
        if b == 3:
            pairs.append((A[i][1], B[j][1]))
            i -= 1
            j -= 1
        elif b == 2:
            j -= 1
        elif b == 1:
            i -= 1
        else:
            break
    pairs.reverse()
    if len(pairs) < 3:
        return [(0.0, 0.0), (1.0, 1.0)], len(pairs)
    # drop anchors far from the running median of residuals
    res = np.array([q - w for w, q in pairs])
    keep = []
    W_ = 9
    for k in range(len(pairs)):
        seg = res[max(0, k - W_) : k + W_ + 1]
        if abs(res[k] - np.median(seg)) <= 0.03:
            keep.append(pairs[k])
    # one anchor per bin of 0.5 percent of the group so close repeats do not dominate
    binned = collections.OrderedDict()
    for w, q in keep:
        binned.setdefault(int(w * 200), []).append((w, q))
    chain = (
        [(0.0, 0.0)]
        + [
            (float(np.mean([a for a, _ in v])), float(np.mean([b for _, b in v])))
            for v in binned.values()
        ]
        + [(1.0, 1.0)]
    )
    xs = np.maximum.accumulate([c[0] for c in chain])
    ys = np.maximum.accumulate([c[1] for c in chain])
    return list(zip(xs.tolist(), ys.tolist())), len(chain) - 2


import induce_lexicon as il  # noqa: E402


class LexDims:
    """Shared dimensions for the second pass: English words of the induced list and name skeletons."""

    def __init__(self, lex, W):
        self.lex = lex
        names = set()
        for w in W:
            for k in ms.warner_tokens(w):
                if not k.startswith("#"):
                    names.add("#" + k)
        self.index = {}
        for e in sorted(set(lex.values())):
            self.index[e] = len(self.index)
        for k in sorted(names):
            self.index[k] = len(self.index)
        self.D = len(self.index)
        self.df = np.zeros(self.D)

    def pvec(self, lines):
        v = np.zeros(self.D, np.float32)
        for t in " ".join(lines).split():
            f = il.norm_fa(t)
            e = self.lex.get(f)
            if e is not None and e in self.index:
                v[self.index[e]] += 1
            sk = ms.pers_skel(t)
            if len(sk) >= 3 and ("#" + sk) in self.index:
                v[self.index["#" + sk]] += 1
        return v

    def wvec(self, para):
        v = np.zeros(self.D, np.float32)
        for w in il.en_words(para):
            if w in self.index:
                v[self.index[w]] += 1
        for m in re.finditer(
            r"(?<![\.\!\?\"”“/:;] )(?<!^)\b([A-Z][a-z\u00c0-\u024f'’\-]{2,})", para
        ):
            if m.group(1) in ms.STOP:
                continue
            sk = ms.lat_skel(m.group(1))
            if len(sk) >= 3 and ("#" + sk) in self.index:
                v[self.index["#" + sk]] += 1
        return v


def lex_boundaries(CP, wv, nwords, K, lp=0.15, empty=-0.2):
    """Choose, for each Warner paragraph, how many couplets it receives, by dynamic programming:
    cosine between the paragraph's word vector and the vector of the couplets it covers, minus a
    penalty for departing from the proportional length, boundaries kept near the proportional line."""
    P = len(wv)
    tot = float(sum(nwords)) or 1.0
    cum = np.cumsum(nwords) / tot
    exp_end = cum * K
    delta = max(8, int(0.10 * K))
    G = CP @ CP.T
    dg = np.diag(G)
    rng = []
    for i in range(P):
        lo = max(0, int(round(exp_end[i])) - delta)
        hi = min(K, int(round(exp_end[i])) + delta)
        if i == P - 1:
            lo = hi = K
        rng.append(np.arange(lo, hi + 1))
    prev_b = np.array([0])
    prev_s = np.array([0.0])
    backs = []
    for i in range(P):
        bs = rng[i]
        Vi = wv[i]
        nv = np.linalg.norm(Vi)
        s_all = CP @ Vi
        A = prev_b[:, None]
        B = bs[None, :]
        ok = B >= A
        dif = s_all[B] - s_all[A]
        nrm = np.sqrt(np.maximum(dg[B] + dg[A] - 2 * G[A, B], 1e-9))
        cosv = dif / (nv * nrm + 1e-9) if nv > 0 else np.zeros_like(dif)
        elen = K * nwords[i] / tot
        ln = np.log(np.maximum(B - A + 1.0, 1e-6) / (elen + 1.0))
        S = cosv - lp * np.abs(ln)
        S = np.where(B == A, empty, S)
        tot_s = prev_s[:, None] + S
        tot_s = np.where(ok, tot_s, -1e9)
        bi = np.argmax(tot_s, axis=0)
        new_s = tot_s[bi, np.arange(len(bs))]
        backs.append(bi)
        prev_b, prev_s = bs, new_s
    # backtrace from the forced end K
    j = len(prev_b) - 1
    ends = [0] * P
    for i in range(P - 1, -1, -1):
        ends[i] = int(rng[i][j])
        j = int(backs[i][j])
    starts = [0] + ends[:-1]
    return starts, ends


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--work",
        required=True,
        help="scratch folder holding stories_raw.json, warner_stories.json, match_path2.json",
    )
    ap.add_argument(
        "--tess", required=True, help="the restructured ferdowsi.shahnameh.tess"
    )
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--min-cos", type=float, default=0.08)
    ap.add_argument(
        "--lexicon",
        default=None,
        help="lexicon.json from induce_lexicon.py: switches to the second, lexicon-guided pass",
    )
    a = ap.parse_args()
    from write_aligned import write_aligned, tess_refs

    stories = json.load(open(a.work + "/stories_raw.json"))
    W = json.load(open(a.work + "/warner_stories.json"))
    path = json.load(open(a.work + "/match_path2.json"))
    tess = [line.rstrip("\n").split("\t", 1) for line in open(a.tess, encoding="utf-8")]
    cps = couplets_of(tess)
    by_story = collections.defaultdict(list)
    for c in cps:
        by_story[c[0]].append(c)
    refs = tess_refs(a.tess)
    n_couplets = len(cps)
    # global document frequency of name skeletons
    df_w = collections.Counter()
    df_p = collections.Counter()
    for w in W:
        for k in ms.warner_tokens(w):
            df_w[k] += 1
    for s in stories:
        for k in set(
            ms.pers_skel(t)
            for st in by_story[s["number"]]
            for t in " ".join(st[2]).split()
        ):
            df_p[k] += 1
    lex = None
    if a.lexicon:
        L = json.load(open(a.lexicon))["lexicon"]
        dims = LexDims(L, W)
        lex_w, lex_p = dims.wvec, dims.pvec
        dfv = np.zeros(dims.D)
        for w in W:
            for pa in w["paragraphs"]:
                dfv += lex_w(pa) > 0
        lex_idf = np.log(
            1.0 + sum(len(w["paragraphs"]) for w in W) / (1.0 + dfv)
        ).astype(np.float32)
        lex = True
    units = []
    ref_to_unit = {}
    table = []
    r0 = sum(w["words"] for w in W) / n_couplets
    for g0, w0, g1, w1, m in path:
        if isinstance(m, str):
            table.append(
                {
                    "status": "unmatched "
                    + ("Persian story" if m == "gskip" else "Warner section"),
                    "stories": [] if m == "wskip" else list(range(g0 + 1, g1 + 1)),
                    "warner": []
                    if m == "gskip"
                    else [W[k]["id"] for k in range(w0, w1)],
                }
            )
            continue
        gs = list(range(g0, g1))
        ws = list(range(w0, w1))
        pc = [c for g in gs for c in by_story[stories[g]["number"]]]
        wp = [p for k in ws for p in W[k]["paragraphs"]]
        nw = sum(len(p.split()) for p in wp)
        # raw cosine and length ratio of the group, to decide whether to show it
        cosv = m[3]
        lr = (nw / max(len(pc), 1)) / r0
        nst, nse = len(gs), len(ws)
        manual = (
            m[2] == 0.0 and m[3] == 0.0
        )  # the Prelude pairs and the out-of-order pair, set by hand in match_stories.py
        small = (nst, nse) in ((1, 1), (1, 2), (2, 1), (2, 2)) and 0.65 <= lr <= 1.5
        weak = not (manual or cosv >= 0.25 or (cosv >= 0.10 and small))
        status = (
            "matched by title, set by hand"
            if manual
            else (
                "matched, names and words confirm"
                if cosv >= 0.25
                else (
                    "matched by order and length"
                    if not weak
                    else "left untranslated: weak match"
                )
            )
        )
        row = {
            "status": status,
            "stories": [stories[g]["number"] for g in gs],
            "warner": [W[k]["id"] for k in ws],
            "score": round(cosv, 3),
            "words_per_couplet_ratio": round(lr, 2),
            "couplets": len(pc),
            "words": nw,
        }
        if weak or not wp or not pc:
            table.append(row)
            continue
        if lex is not None:
            Wv = np.array([lex_w(pa) for pa in wp])
            Pv = np.array([lex_p(c[2]) for c in pc])
            CPm = np.vstack(
                [np.zeros((1, Pv.shape[1]), np.float32), np.cumsum(Pv * lex_idf, 0)]
            )
            starts, ends = lex_boundaries(
                CPm, Wv * lex_idf, [len(pa.split()) for pa in wp], len(pc)
            )
            assign = []
            for i in range(len(wp)):
                assign += [i] * (ends[i] - starts[i])
            row["anchors"] = "lexicon"
        else:
            chain, n_anch = anchors(pc, wp, df_p, df_w)
            row["anchors"] = n_anch
            xs = np.array([c[0] for c in chain])
            ys = np.array([c[1] for c in chain])
            cum = np.cumsum([0] + [len(pa.split()) for pa in wp]) / nw
            assign = []
            for k in range(len(pc)):
                yp = (k + 0.5) / len(pc)
                xw = float(np.interp(yp, ys, xs))
                j = int(np.searchsorted(cum, xw, side="right") - 1)
                assign.append(min(max(j, 0), len(wp) - 1))
        for k in range(1, len(assign)):
            assign[k] = max(assign[k], assign[k - 1])
        # runs of equal paragraph -> unit; unassigned paragraphs join the unit before them
        run_starts = [0] + [
            k for k in range(1, len(assign)) if assign[k] != assign[k - 1]
        ]
        for ri, rs in enumerate(run_starts):
            re_ = run_starts[ri + 1] if ri + 1 < len(run_starts) else len(assign)
            p_from = 0 if ri == 0 else assign[rs]
            p_to = assign[run_starts[ri + 1]] if ri + 1 < len(run_starts) else len(wp)
            text = "\n\n".join(wp[p_from:p_to])
            uid = len(units)
            units.append(text)
            for k in range(rs, re_):
                for r in pc[k][1]:
                    ref_to_unit[r] = uid
        table.append(row)
    note = (
        f"Warner sections matched to the Persian stories by order, length and proper names; within a matched run of stories the "
        f"paragraphs are laid along the couplets in proportion to length with name anchors. {len(units)} units cover "
        f"{len(ref_to_unit)} of {len(refs)} lines; stories without a match are left untranslated."
    )
    write_aligned(
        a.out_dir,
        "fa",
        "ferdowsi.shahnameh",
        units,
        ref_to_unit,
        attribution="A. G. Warner and E. Warner, The Shahnama of Firdausi (London: Kegan Paul, Trench, Trubner, 1905-1925), via the Internet Archive",
        license="Public domain (published 1905 to 1925)",
        sources=[
            {
                "translator": "A. G. Warner and E. Warner",
                "year": "1905-1925",
                "title": "The Sháhnáma of Firdausí",
                "url": "https://archive.org/details/shahnama01firduoft",
                "source_url": "https://archive.org/details/shahnama01firduoft",
                "urls": [
                    f"https://archive.org/details/shahnama0{v}firduoft"
                    for v in range(1, 10)
                ],
                "publisher": "Kegan Paul, Trench, Trübner (Trübner's Oriental Series), London, 9 volumes",
                "mode": "proportional with name and word anchors",
            }
        ],
        confidence="medium",
        approximate=True,
        tess_refs=refs,
        notes=note,
    )
    json.dump(
        table, open(a.work + "/match_table.json", "w"), ensure_ascii=False, indent=1
    )
    print(
        "units",
        len(units),
        "lines translated",
        len(ref_to_unit),
        "of",
        len(refs),
        "couplets",
        len(ref_to_unit) // 2,
        "of",
        n_couplets,
    )


if __name__ == "__main__":
    main()
