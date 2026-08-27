#!/usr/bin/env python3
"""
Alignment build, twelfth pass.

For each .tess work:
  1. take the Perseus WORK confirmed by content comparison of the original-language
     text (verify2.py, verified.json),
  2. consider every public-domain English translation of that work,
  3. search compositions of the translation's anchors for the one that reproduces
     our own refs most FINELY, subject to near-maximal coverage,
  4. merge several English works when one .tess work spans several of them (Livy),
  5. write an aligned file per work plus a manifest.

WHAT CHANGED FROM align11, AND WHY
----------------------------------

align11 left roughly 76,000 lines of already-licensed, already-downloaded English
on the floor. Four separate causes, fixed here.

1. IDENTITY CAME FROM TITLE STRINGS.  align11 read work_map.json, built by
   matching author and title text. That is why Lucan, Thucydides, Phaedrus,
   Claudian, Ammianus, Apuleius' Metamorphoses, Tacitus' Germania, Sallust's
   Jugurtha, Boethius and Ovid's Heroides have no English today: their titles did
   not score highly enough against Perseus' own wording.

   The obvious repair, taking the URN from matches.json instead, is WRONG and
   would be worse than the disease. matches.json is a scored candidate list, not
   a decision: it pairs Boethius with Suetonius, Claudianus Mamertus with Horace
   and Aethelwulf with Catullus. Serving one author's translation beside another
   author's text is undetectable to a reader, which makes it the most damaging
   thing this pipeline can do.

   verified.json answers the question properly, by comparing the VOCABULARY of
   our own Latin or Greek against each Perseus work. It agrees with work_map on
   461 of the 463 works they share, and supplies 116 more that carry an extracted
   English text. Identity is now decided on content, and title matching is kept
   only as a fallback where content verification is silent.

2. THE PUBLIC DOMAIN MOVED.  Works published in 1930 entered the US public
   domain on 1 January 2026. The cutoff was still excluding them.

3. COVERAGE OUTRANKED PRECISION.  The composition search maximised coverage and
   used granularity only to break ties, so a book-level index covering 100% beat
   a section-level index covering 98%. That is how Lucretius came to be served in
   units of 1,250 source lines when 35 was available, and the Metamorphoses in
   units of 809. Coverage you cannot locate a line within is not much use to a
   reader, so the choice now takes the FINEST composition whose coverage is
   within a small tolerance of the best available.

4. THE PROPER-NAME CHECK BOTH REJECTED CORRECT WORK AND ABSTAINED TOO OFTEN.  The check compares proper names
   in our source line against the English assigned to it, and it exists to catch
   a translation aligned to the wrong text. At a flat 0.45 it also threw out
   Coleridge's Euripides, Jebb's Ajax and Trachiniae and twelve Plautus plays,
   all correct, because those translators Anglicise or Latinise names.

   The floor is now conditional. Where identity is confirmed by content, we
   already know the work is right, and the check has only to catch a grossly
   wrong ref composition, so a low floor suffices. Where identity rests on title
   matching alone, the old strict floor stands, because there the check is the
   only thing standing between a reader and someone else's translation.

   The other half of this is worse and was found by reading the output. The check
   refuses to speak on fewer than twenty sampled names, and align11 read silence
   as approval. Ovid's Medicamina is a hundred lines about face cream, offers
   twelve names, agreed on NONE of them, and was published anyway under a HIGH
   confidence label, with English about pendants and lockets standing beside
   Latin about mixing powdered meal. A reader without Latin cannot detect that,
   and is exactly the reader this feature is for.

   So abstention is now its own answer. Where the name check cannot speak, two
   things happen: a length correlation is tried instead, which needs no proper
   nouns and cleanly separates the Medicamina (0.03) from the median work (0.93);
   and no work that nothing could verify is allowed to call itself high
   confidence.
"""
import json, os, re, collections, bisect, itertools, glob
import proper_names as V


# WHERE THINGS LIVE. These are the paths this pipeline was actually run against,
# kept as defaults so the record is honest, and overridable so nobody has to edit
# a checked-in file to run it elsewhere.
#   TESSERAE_PERSEUS_WORK  the working directory holding the cloned Perseus
#                          repositories and this pipeline's JSON intermediates
#   TESSERAE_TEXTS         our own .tess corpus
#   TESSERAE_TRANS_OUT     where aligned files are written
ROOT = os.environ.get("TESSERAE_PERSEUS_WORK", "/home/ncoffee/perseus_trans/work")
OUT = os.environ.get("TESSERAE_TRANS_OUT", "/home/ncoffee/perseus_trans/translations_v3")

# 1930 publications entered the US public domain on 2026-01-01, so the test is
# "published before 1931". Confirmed at the Duke Center for the Study of the
# Public Domain, Public Domain Day 2026.
PD_CUTOFF = 1931

# Content verification: how alike our own Latin or Greek vocabulary and the
# Perseus work's must be before we call them the same work. The distribution is
# strongly bimodal, real matches sitting at 0.93 and above and coincidences well
# below 0.5, so anywhere in the trough separates them.
VERIFY_JACCARD = 0.60

# Proper-name agreement floors. See point 4 in the header.
NAME_FLOOR_VERIFIED = 0.20
NAME_FLOOR_UNVERIFIED = 0.45

# Second opinion for works too short for the name check. Across the 244 works
# whose refs map one to one, the median correlation between source-line length
# and translated-unit length is 0.93 and the lower quartile 0.78. Ovid's
# Medicamina, misaligned, is 0.03. The floor sits in the empty ground between.
LENGTH_CORR_FLOOR = 0.30

# How much coverage we will trade for a finer alignment. A candidate must reach
# 85% of the best coverage on offer and 80% of the work outright.
COVERAGE_RATIO = 0.85
COVERAGE_FLOOR = 0.80

UNITS = ["book", "chapter", "section", "subsection", "verse", "poem", "epistle",
         "letter", "fragment", "card", "para", "line", "page", "speech", "oath"]
RANGE_UNITS = {"line", "card", "page"}


def pd_status(meta):
    y = meta.get("year")
    if y is None:
        return False, "no publication date in the TEI header"
    if y < PD_CUTOFF:
        return True, "published %d, US public domain" % y
    return False, "published %d, still under US copyright" % y


def tail(ref):
    m = re.search(r"([\dA-Za-z]+(?:[.][\dA-Za-z]+)*)\s*$", ref.strip())
    return m.group(1) if m else ref.strip()


def numkey(s):
    m = re.match(r"^(\d+)", str(s))
    return int(m.group(1)) if m else None


def compositions(units):
    order = [u for u in UNITS if u in units]
    out = []
    for k in (3, 2, 1):
        out += list(itertools.combinations(order, k))
    seen, res = set(), []
    for c in out:
        if c not in seen:
            seen.add(c)
            res.append(c)
    return res[:40]


def build_exact(chunks, comp, their_trunc=0):
    """
    their_trunc>0 folds a translation FINER than our refs up to our level: their
    book.chapter.section units are concatenated, in document order, under book.chapter.
    """
    idx = collections.OrderedDict()
    keep = len(comp) - their_trunc
    if keep < 1:
        return idx
    for c in chunks:
        a = c["anchors"]
        if not all(u in a for u in comp):
            continue
        k = ".".join(a[u] for u in comp[:keep])
        idx[k] = (idx[k] + " " + c["text"]) if k in idx else c["text"]
    return idx


def build_range(chunks, comp):
    by = collections.defaultdict(dict)
    for c in chunks:
        a = c["anchors"]
        if not all(u in a for u in comp):
            continue
        n = numkey(a[comp[-1]])
        if n is None:
            continue
        pre = ".".join(a[u] for u in comp[:-1])
        d = by[pre]
        d[n] = (d.get(n, "") + " " + c["text"]).strip()
    idx = {}
    for pre, agg in by.items():
        ns = sorted(agg)
        segs = [(n, (ns[i + 1] - 1 if i + 1 < len(ns) else None), agg[n]) for i, n in enumerate(ns)]
        idx[pre] = ([s[0] for s in segs], segs)
    return idx


def map_exact(tails, idx, trunc=0, depth=None):
    """
    trunc>0 lets a coarser translation serve finer refs: our book.chapter.section is
    looked up as book.chapter when the translation only goes down to the chapter.
    The number of our refs sharing one translated unit becomes the granularity.
    """
    out = {}
    for t in tails:
        p = t.split(".")
        for d in range(0, trunc + 1):
            if depth is not None and len(p) - d != depth:
                continue
            k = ".".join(p[:len(p) - d]) if d else t
            if k and k in idx:
                out[t] = (k, None)
                break
    if trunc:
        share = collections.Counter(k for k, _ in out.values())
        for t, (k, _) in list(out.items()):
            out[t] = (k, share[k])
    else:
        for t, (k, _) in list(out.items()):
            out[t] = (k, 1)
    return out


def map_range(tails, idx):
    out = {}
    for t in tails:
        p = t.split(".")
        n = numkey(p[-1])
        if n is None:
            continue
        pre = ".".join(p[:-1])
        cand = idx.get(pre)
        if cand is None and len(idx) == 1 and pre == "":
            cand = next(iter(idx.values()))
        if cand is None:
            continue
        starts, segs = cand
        i = bisect.bisect_right(starts, n) - 1
        if i < 0:
            continue
        s = segs[i]
        if s[1] is not None and n > s[1]:
            continue
        out[t] = ((pre, s[0]), (s[1] - s[0] + 1) if s[1] is not None else None)
    return out


def our_max_by_prefix(tails):
    mx = collections.defaultdict(int)
    for t in tails:
        p = t.split(".")
        n = numkey(p[-1])
        if n is None:
            continue
        mx[".".join(p[:-1])] = max(mx[".".join(p[:-1])], n)
    return mx


def line_anchor_is_source_numbered(idx, mode, comp, ourmax):
    """
    A translation's <l n=..> may number the ENGLISH verse rather than the source line.
    Compare the highest anchor per book with the highest source line we hold for that
    book. A verse translation always runs longer than its original, so a ratio well
    above 1 means the anchors count English lines and must not be read as source lines.
    """
    if comp[-1] not in ("line", "card"):
        return True, None
    theirs = collections.defaultdict(int)
    if mode == "range":
        for pre, (starts, segs) in idx.items():
            theirs[pre] = max(starts) if starts else 0
    else:
        for k in idx:
            p = k.split(".")
            n = numkey(p[-1])
            if n is None:
                continue
            theirs[".".join(p[:-1])] = max(theirs[".".join(p[:-1])], n)
    ratios = []
    for pre, mx in theirs.items():
        om = ourmax.get(pre)
        if om and mx:
            ratios.append(mx / om)
    if not ratios:
        return True, None
    ratios.sort()
    med = ratios[len(ratios) // 2]
    return (0.55 <= med <= 1.12), round(med, 3)


def length_correlation(pairs):
    """Do longer source lines get longer English? A second opinion on alignment.

    The proper-name check starves on short works: Ovid's Medicamina is a hundred
    lines about face cream and offers twelve names to test, below the twenty the
    check needs before it will speak. It scored 0.000 there, meaning not one name
    agreed, and was served anyway, labelled high confidence, with English about
    pendants and lockets beside Latin about mixing powdered meal.

    Length needs no proper nouns. Where our refs map one to one onto units of
    translation, the length of each English unit should track the length of the
    line it claims to render, and a mapping shifted by even one line breaks that
    correlation. Across the 244 testable works the median is 0.93. The Medicamina
    is 0.03.

    Meaningless where one unit of translation serves many source lines, since
    every one of them then gets the same English and the correlation collapses
    to nothing for a perfectly good alignment. The caller checks the span first.
    """
    xs = [len(s) for s, t in pairs if s and t]
    ys = [len(t) for s, t in pairs if s and t]
    n = len(xs)
    if n < 10:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    if not dx or not dy:
        return None
    return num / (dx * dy)


def rebuild_index(chunks, cand):
    """The winning candidate's index, rebuilt after the scoring pass discarded it."""
    comp = tuple(cand["full_comp"])
    if cand["mode"] == "exact":
        return build_exact(chunks, comp, cand["their_trunc"])
    return build_range(chunks, comp)


def pick_finest(cands):
    """The finest alignment among those that cover nearly as much as the best.

    Coverage alone picks the coarsest unit every time, because a translation
    divided only by book necessarily covers every ref in the book. mean_span is
    the number of source lines a reader must search within one unit of
    translation, so it is the thing they actually feel: at 800 they are told the
    answer is somewhere in this book, which is barely better than nothing.

    So the two are traded rather than ranked. A candidate is admissible if it
    covers at least COVERAGE_RATIO of what the best candidate covers, and at
    least COVERAGE_FLOOR of the work outright. Among those, the finest wins.

    Lucan is the case that sets the ratio: book-level covers 100% at 795 source
    lines per unit, and card-level covers 88% at 118. Losing an eighth of the
    work to put a reader seven times closer is worth it. Losing half of it would
    not be, which is what the absolute floor is for.
    """
    if not cands:
        return None
    top = max(c["coverage"] for c in cands)
    floor = max(COVERAGE_FLOOR, top * COVERAGE_RATIO)
    pool = [c for c in cands if c["coverage"] >= floor]
    if not pool:
        # Nothing clears the floor, which happens on short works where the only
        # fine composition matches a handful of refs. Falling through to "take
        # the finest anyway" is how Claudian's panegyrics came back with one
        # translated line each out of twenty-seven. When precision cannot be had
        # honestly, coverage is what is left.
        return max(cands, key=lambda c: (c["coverage"], -c["mean_span"]))
    return min(pool, key=lambda c: (c["mean_span"], -c["coverage"], len(c["comp"])))


def evaluate(tails, chunks, units, ourmax):
    """
    Return best {mode, comp, coverage, mean_span, mapping, index}.

    The composition search scores on a sample of our refs, because mapping every ref for
    every candidate composition is the dominant cost on large works. Only the winning
    composition is then mapped in full.

    THE CHOICE IS NOT SIMPLY THE HIGHEST COVERAGE.  A translation divided only by
    book covers every line of the Metamorphoses, and tells a reader that their
    line is somewhere in these 809. A translation divided by card covers slightly
    less and puts them within eight. The second is worth far more, so the winner
    is the FINEST candidate whose coverage is within COVERAGE_TOLERANCE of the
    best on offer, and coverage decides only among equals.

    Candidates are scored without keeping their indexes, which would hold every
    unit of every composition of every work in memory at once. The winner's index
    is rebuilt afterwards, which costs one more pass over the chunks.
    """
    if len(tails) > 600:
        step = len(tails) // 600 + 1
        sample = tails[::step]
    else:
        sample = tails
    scale = len(tails) / len(sample) if sample else 1.0
    cands = []
    coarsest = next((u for u in UNITS if u in units), None)
    for comp in compositions(units):
        for mode in ("exact", "range"):
            if mode == "range" and comp[-1] not in RANGE_UNITS:
                continue
            # their_trunc: fold a translation finer than our refs up to our level
            for ttr in ((0, 1, 2) if mode == "exact" else (0,)):
                if mode == "exact" and len(comp) - ttr < 1:
                    continue
                idx = build_exact(chunks, comp, ttr) if mode == "exact" else build_range(chunks, comp)
                if not idx:
                    continue
                eff = comp[:len(comp) - ttr] if mode == "exact" else comp
                ok, ratio = line_anchor_is_source_numbered(idx, mode, eff, ourmax)
                if not ok:
                    continue
                # our_trunc only makes sense when the composition is anchored at the
                # outermost level, else book.chapter.section cut to "book" is looked up
                # in a chapter-keyed index and matches by accident.
                max_tr = 2 if (coarsest is None or coarsest in eff) else 0
                truncs = tuple(range(0, max_tr + 1)) if mode == "exact" else (0,)
                for tr in truncs:
                    mp = map_exact(sample, idx, tr, len(eff)) if mode == "exact" else map_range(sample, idx)
                    cov = len(mp) / len(sample) if sample else 0.0
                    if cov == 0:
                        continue
                    spans = [v[1] for v in mp.values() if v[1]]
                    span = round(sum(spans) / len(spans), 1) if spans else 1.0
                    # THE TWO MODES MEASURE SPAN DIFFERENTLY, and only one of them
                    # survives sampling. In range mode the span is the width of a
                    # translated segment in source-line numbers, which does not
                    # depend on how many of our refs we looked at. In exact mode
                    # with truncation it is a COUNT of our refs sharing one unit,
                    # so on a 600-ref sample of a 12,000-ref work it comes out
                    # twenty times too small. Comparing the two unscaled is how
                    # the Metamorphoses came to report 40 lines per unit and
                    # deliver 809. Scale it back up before anything is compared.
                    if mode == "exact" and tr:
                        span = round(span * scale, 1)
                    # No index kept here: see the docstring. The winner is rebuilt,
                    # which needs the FULL composition, since build_exact folds it
                    # down by their_trunc itself. eff is what the caller reports.
                    cands.append({"mode": mode, "comp": list(eff), "full_comp": list(comp),
                                  "coverage": round(cov, 4),
                                  "mean_span": span, "n_units": len(idx),
                                  "our_ref_truncation": tr, "their_trunc": ttr})
    best = pick_finest(cands)
    if best is not None:
        best["index"] = rebuild_index(chunks, best)
    if best is not None and sample is not tails:
        comp = tuple(best["comp"])
        if best["mode"] == "exact":
            best["mapping"] = map_exact(tails, best["index"], best["our_ref_truncation"], len(comp))
        else:
            best["mapping"] = map_range(tails, best["index"])
        best["coverage"] = round(len(best["mapping"]) / len(tails), 4) if tails else 0.0
        spans = [v[1] for v in best["mapping"].values() if v[1]]
        best["mean_span"] = round(sum(spans) / len(spans), 1) if spans else 1.0
    elif best is not None:
        best["mapping"] = map_exact(tails, best["index"], best["our_ref_truncation"], len(tuple(best["comp"]))) \
            if best["mode"] == "exact" else map_range(tails, best["index"])
    return best


def text_for(best, key):
    if best["mode"] == "exact":
        return best["index"].get(key)
    pre, start = key
    cand = best["index"].get(pre)
    if cand is None and len(best["index"]) == 1 and pre == "":
        cand = next(iter(best["index"].values()))
    if cand is None:
        return None
    starts, segs = cand
    i = bisect.bisect_left(starts, start)
    if i < len(segs) and segs[i][0] == start:
        return segs[i][2]
    return None


def safe(s):
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)


TEXTS = os.environ.get("TESSERAE_TEXTS", "/var/www/tesseraev6_flask/texts")


def load_source_lines():
    """tess work key -> {ref: source text} for the proper-name validation."""
    out = collections.defaultdict(dict)
    for lang in ("la", "grc"):
        for p in sorted(glob.glob(f"{TEXTS}/{lang}/*.tess")):
            base = os.path.basename(p)[:-5]
            wk = re.sub(r"\.part\.\d+(\.[a-z0-9_\-]+)?$", "", base)
            d = out[f"{lang}/{wk}"]
            with open(p, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    m = re.match(r"^<([^>]*)>\s*(.*)$", line)
                    if m and m.group(1).strip() not in d:
                        d[m.group(1).strip()] = m.group(2).strip()
    return out


ONLY = set(x for x in os.environ.get("ONLY_WORKS", "").split(",") if x)


def load_identity():
    """tess work -> {urn, source}, the Perseus work ours actually IS.

    align10 gathered candidates by TEXTGROUP and let whichever English work best
    reproduced our reference numbers win. For an author of many similarly
    numbered short works that is a lottery, and it is how one translation of
    Plutarch's Theseus came to answer for thirty-seven different essays. align11
    replaced it with author-and-title matching, which is sound but deaf: it
    cannot recognise a work whose title Perseus words differently, and it dropped
    Lucan, Thucydides, Phaedrus, Ammianus and a hundred more on that account.

    Identity is a question about the TEXT, so it is settled here by comparing the
    text. verified.json holds, for each of our works, the Perseus works ranked by
    how far their original-language vocabulary overlaps ours. A jaccard of 0.93
    or better means the same work; coincidences sit below 0.5. Title matching
    stays as the fallback for works content verification cannot speak to.
    """
    ident = {}
    for v in json.load(open(f"{ROOT}/verified.json")):
        c = (v.get("candidates") or [])
        if c and c[0].get("jaccard", 0) >= VERIFY_JACCARD:
            ident[v["tess"]] = {"urn": c[0]["work_urn"], "source": "content",
                                "jaccard": c[0]["jaccard"]}
    n_content = len(ident)
    for m in json.load(open(f"{ROOT}/work_map.json")):
        if m["tess"] not in ident:
            ident[m["tess"]] = {"urn": m["urn"], "source": "title",
                                "title_score": m.get("title_score")}
    print(f"identity: {n_content} works verified by content, "
          f"{len(ident) - n_content} by title only, {len(ident)} in all")
    return ident


def main():
    ex = json.load(open(f"{ROOT}/extracted6.json"))
    tess = json.load(open(f"{ROOT}/tess_index.json"))
    wmap = load_identity()
    os.makedirs(OUT, exist_ok=True)

    bywork = collections.defaultdict(list)
    for r in ex:
        u = r["meta"].get("cts_urn")
        if not u or not r["chunks"]:
            continue
        parts = u.split(":")[-1].split(".")
        if len(parts) >= 2:
            bywork[".".join(parts[:2])].append(r)

    srclines = load_source_lines()
    manifest, report = [], []
    for tkey in sorted(wmap):
        v = wmap[tkey]
        if ONLY and tkey not in ONLY:
            continue
        tv = tess.get(tkey)
        if not tv or not tv["tails"]:
            continue
        raw_refs, tails, seen = [], [], set()
        for full, x in zip(tv["refs"], tv["tails"]):
            if full in seen:
                continue
            seen.add(full)
            raw_refs.append(full)
            tails.append(tail(x))
        ourmax = our_max_by_prefix(tails)
        sl = srclines.get(tkey, {})
        tailmap = {}
        for full, tl in zip(raw_refs, tails):
            tailmap.setdefault(tl, full)
        # How hard the proper-name check should bite. When the work's identity is
        # settled by comparing the original-language text, we already KNOW this is
        # the right work, and the check has only to catch a badly wrong reference
        # composition, which shows up as near-total disagreement. Where identity
        # rests on a title string, the check is the only thing between a reader and
        # somebody else's translation, so it keeps its old strictness.
        verified = v.get("source") == "content"
        name_floor = NAME_FLOOR_VERIFIED if verified else NAME_FLOOR_UNVERIFIED
        screen_floor = name_floor * 0.78          # was 0.35 against a 0.45 final
        options = []
        for _one in (1,):
            for r in bywork.get(v["urn"], []):
                meta = r["meta"]
                pd, why = pd_status(meta)
                b = evaluate(tails, r["chunks"], meta.get("anchor_units") or [], ourmax)
                if not b or b["coverage"] == 0:
                    continue
                # independent sanity check: do proper names in the source line show up in
                # the English this alignment assigns to it? Rejects plausible-looking but
                # wrong pairings, e.g. one work's line numbers matched against another's.
                probe = []
                for t in list(b["mapping"])[:1200]:
                    raw = tailmap.get(t)
                    txt = text_for(b, b["mapping"][t][0])
                    if raw and txt:
                        probe.append((sl.get(raw, ""), txt))
                hit, n = V.score(probe, tv["lang"], sample=120)
                b["name_hit"], b["name_n"] = hit, n
                if hit is not None and n >= 25 and hit < screen_floor:
                    continue
                b["meta"] = meta
                b["pd"] = pd
                b["pd_reason"] = why
                options.append(b)
        pdo = [o for o in options if o["pd"]]
        if not pdo:
            report.append({"tess": tkey, "lang": tv["lang"], "n_lines": tv["n_lines"],
                           "status": "copyright_only" if options else "no_translation",
                           "best_nonpd_cov": max([o["coverage"] for o in options], default=None)})
            continue
        # greedy merge across English works
        pdo.sort(key=lambda o: (-o["coverage"], o["mean_span"]))
        chosen, covered = [], {}
        for o in pdo:
            new = {t: k for t, k in o["mapping"].items() if t not in covered}
            if not new:
                continue
            if chosen and len(new) < 0.01 * len(tails):
                continue
            chosen.append((o, new))
            for t in new:
                covered[t] = o
            if len(covered) >= len(tails):
                break
        # emit aligned file
        aligned = {}
        for raw, t in zip(raw_refs, tails):
            o = covered.get(t)
            if not o:
                continue
            txt = text_for(o, o["mapping"][t][0])
            if txt:
                aligned[raw] = txt
        cov = len(aligned) / len(raw_refs) if raw_refs else 0
        spans = [o["mapping"][t][1] for t, o in covered.items() if o["mapping"][t][1]]
        mean_span = round(sum(spans) / len(spans), 1) if spans else 1.0
        pairs = [(sl.get(r, ""), t) for r, t in aligned.items()]
        name_hit, name_n = V.score(pairs, tv["lang"])
        # A "suspect" file still gets served, and a served wrong translation is worse
        # than none at all: a scholar reading a work has no way to tell that the
        # English beside it belongs to a different text. So this is now a rejection.
        if name_hit is not None and name_n >= 20 and name_hit < name_floor:
            report.append({"tess": tkey, "lang": tv["lang"], "n_lines": tv["n_lines"],
                           "status": "rejected_name_check", "coverage": round(cov, 4),
                           "name_hit": round(name_hit, 3), "name_n": name_n,
                           "identity": v.get("source"), "floor": name_floor})
            continue
        # THE NAME CHECK ABSTAINS ON SHORT WORKS, and align11 read abstention as a
        # pass. It is not one. It is "cannot tell", and Ovid's Medicamina went out
        # with the wrong English under a HIGH confidence label because of it.
        #
        # Two extra tests run only where the name check could not speak for
        # itself. Neither overrules it: a work whose names agree stays, whatever
        # its lengths do, because names are the stronger evidence when there are
        # enough of them to count.
        checked = name_hit is not None and name_n >= 20
        corr = None
        if not checked and mean_span <= 1.2:
            corr = length_correlation(pairs)
        if not checked:
            why = None
            if corr is not None:
                # Where lengths can speak they are the better witness, and they
                # OVERRULE a zero name rate. Hippocrates' de officina medici is
                # the case: a short surgical treatise with almost no proper nouns,
                # zero of nineteen agreeing, and a length correlation of 0.989.
                # Judged on names alone it looks as bad as the Medicamina; judged
                # on lengths the two are nothing alike.
                if corr < LENGTH_CORR_FLOOR:
                    why = "line lengths uncorrelated (r=%.3f)" % corr
            elif name_hit == 0.0 and name_n >= 5:
                # No lengths to consult, because one unit of translation serves
                # many source lines. Zero out of twelve is then all we have, and
                # it is not a small sample failing to reach significance. It is
                # twelve chances to agree and none taken.
                why = "no proper name agreed (%d tested), lengths not testable" % name_n
            if why:
                report.append({"tess": tkey, "lang": tv["lang"], "n_lines": tv["n_lines"],
                               "status": "rejected_unverifiable", "coverage": round(cov, 4),
                               "name_hit": name_hit, "name_n": name_n,
                               "length_corr": (round(corr, 3) if corr is not None else None),
                               "reason": why})
                continue
        if cov >= 0.95 and mean_span <= 3:
            conf = "high"
        elif cov >= 0.95 and mean_span <= 12:
            conf = "medium"
        elif cov >= 0.85:
            conf = "medium"
        elif cov >= 0.5:
            conf = "low"
        else:
            conf = "very low"
        # Confidence described how NEATLY the refs mapped, and said nothing about
        # whether the English belongs to the Latin. Those are different questions,
        # and the Medicamina answered the first perfectly while failing the second.
        # A work no check could verify does not get to call itself high.
        verified_alignment = checked or (corr is not None and corr >= LENGTH_CORR_FLOOR)
        if conf == "high" and not verified_alignment:
            conf = "medium"
        srcs = []
        for o, _ in chosen:
            m = o["meta"]
            srcs.append({"cts_urn": m["cts_urn"], "translator": m.get("translator"),
                         "year": m.get("year"), "publisher": m.get("publisher"),
                         "title": m.get("title"), "mode": o["mode"],
                         "ref_composition": o["comp"], "mean_span_source_lines": o["mean_span"],
                         "our_ref_truncation": o.get("our_ref_truncation", 0),
                         "their_ref_aggregation": o.get("their_trunc", 0),
                         "pd_reason": o["pd_reason"], "source_file": m.get("source_file")})
        fn = safe(tkey.replace("/", "__")) + ".json"
        json.dump({"tess_work": tkey, "language": tv["lang"], "n_tess_refs": len(raw_refs),
                   "n_translated": len(aligned), "coverage": round(cov, 4),
                   "mean_source_lines_per_translation_unit": mean_span,
                   "alignment_confidence": conf,
                   "name_check_hit_rate": (round(name_hit, 3) if name_hit is not None else None),
                   "name_check_n": name_n, "sources": srcs,
                   "license": "CC BY-SA 4.0 (Perseus Digital Library TEI); "
                              "underlying translation is US public domain (published before 1931)",
                   "attribution": "Perseus Digital Library, Tufts University",
                   "translations": aligned},
                  open(f"{OUT}/{fn}", "w"), ensure_ascii=False)
        m0 = chosen[0][0]["meta"]
        manifest.append({"work_id_guess": tkey.split("/", 1)[1], "tess_key": tkey,
                         "language": tv["lang"], "author": m0.get("author"),
                         "title": m0.get("title"), "translator": m0.get("translator"),
                         "year": m0.get("year"), "publisher": m0.get("publisher"),
                         "source_url": "https://github.com/PerseusDL/canonical-%sLit/blob/master/%s" % (
                             "greek" if tv["lang"] == "grc" else "latin",
                             (m0.get("source_file") or "").split("/", 1)[-1]),
                         "cts_urn": m0.get("cts_urn"),
                         "license": "CC BY-SA 4.0 markup; translation US public domain (US public domain)",
                         "ref_scheme": ".".join(chosen[0][0]["comp"]) + (
                             " (exact)" if chosen[0][0]["mode"] == "exact" else " (range)"),
                         "n_units": chosen[0][0]["n_units"],
                         "n_tess_refs": len(raw_refs), "n_translated": len(aligned),
                         "coverage": round(cov, 4),
                         "mean_source_lines_per_unit": mean_span,
                         "n_merged_sources": len(chosen),
                         "alignment_confidence": conf,
                         "name_check_hit_rate": (round(name_hit, 3) if name_hit is not None else None),
                         "name_check_n": name_n, "file": fn})
        report.append({"tess": tkey, "lang": tv["lang"], "n_lines": tv["n_lines"],
                       "status": "ok", "coverage": round(cov, 4), "conf": conf,
                       "mean_span": mean_span, "n_sources": len(chosen),
                       "name_hit": (round(name_hit, 3) if name_hit is not None else None)})

    manifest.sort(key=lambda m: (-m["n_translated"]))
    mf = f"{OUT}/manifest.json" if not ONLY else f"{ROOT}/manifest_subset.json"
    json.dump(manifest, open(mf, "w"), indent=1, ensure_ascii=False)
    json.dump(report, open(f"{ROOT}/align_report12.json", "w"), indent=1, ensure_ascii=False)

    hi = [m for m in manifest if m["alignment_confidence"] == "high"]
    md = [m for m in manifest if m["alignment_confidence"] == "medium"]
    lo = [m for m in manifest if m["alignment_confidence"] in ("low", "very low")]
    print("works with a PD translation written:", len(manifest))
    print("  high  :", len(hi), "works", sum(m["n_translated"] for m in hi), "refs")
    print("  medium:", len(md), "works", sum(m["n_translated"] for m in md), "refs")
    print("  low   :", len(lo), "works", sum(m["n_translated"] for m in lo), "refs")
    print("total refs translated:", sum(m["n_translated"] for m in manifest))
    for lang in ("la", "grc"):
        ms = [m for m in manifest if m["language"] == lang]
        tot = sum(v["n_lines"] for v in tess.values() if v["lang"] == lang)
        print("  %s: %d works, %d of %d corpus lines (%.1f%%)" % (
            lang, len(ms), sum(m["n_translated"] for m in ms), tot,
            100.0 * sum(m["n_translated"] for m in ms) / tot))
    print("statuses:", dict(collections.Counter(r["status"] for r in report)))


if __name__ == "__main__":
    main()
