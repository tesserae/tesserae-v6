#!/usr/bin/env python3
"""Measurements for the Greek-Latin counting and lone-pair settings (2026-10-17).

Settings of the evaluation scorer (evaluation/scripts/crosslingual_common.py, make_fused_scorer):
  crosslingual_dict_count  pairs (default) | words
  crosslingual_lone_pair   keep (default)  | rare | drop
Four variants are measured:  a = pairs/keep, b = words/keep, c = words/rare, d = words/drop.
All use the evaluation path's lone-pair rule v2 and the two-lemma gate off.

Every command reads lemma units ONLY from a lemma-cache folder (default: the production folder,
read-only) and refuses to lemmatize or write when a cache file is missing or stale.

  knauer VARIANT            runs benchmark_knauer_crosslingual.py (412 pairs) on those units
  juhnke VARIANT OUT.json   runs benchmark_juhnke_crosslingual.py (2,397 rows, all lines) and
                            adds recall at 200
  precision VARIANT OUT     Aeneid 1 against each Iliad book through score_pairs (top 50 rows):
                            precision at 50 against the Knauer gold and the share of one-word rows
  keytable OUT.json         the gold pairs that rest on one distinct word, and how many clear the
                            rarity threshold on both sides
  thresholds                the two thresholds and the shares on Aeneid 1 against Iliad 1
  identity                  the changed scorer under its defaults against the scorer as it was
                            on origin/main (needs --old PATH to that file), all 461,916 pairs
  sheet OUT_DIR             the second blind sheet for Aeneid 1 against Iliad 1

Run each under ~/bin/tess-job (the lemma caches and embeddings are large).
"""
import argparse
import csv
import importlib.util
import json
import os
import random
import re
import resource
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation" / "scripts"))
os.environ.setdefault("TESSERAE_USE_DIRECT_SEARCH", "1")

PROD_CACHE = "/var/www/tesseraev6_flask/cache/lemmas"
PROD_EMBEDDINGS = "/var/www/tesseraev6_flask/backend/embeddings"
# Optional: another copy of the Achilleid vectors with one row per text line (see install()).
ALT_ACHILLEID = os.environ.get("XL_ACHILLEID_VECTORS")
VARIANTS = {"a": ("pairs", "keep"), "b": ("words", "keep"),
            "c": ("words", "rare"), "d": ("words", "drop")}
GREEK, LATIN = "homer.iliad.part.1", "vergil.aeneid.part.1"
LATIN_BOOK = "vergil.aeneid.part.1"


def use_cache(cache_dir):
    """Make every units loader read cache_dir and never write it."""
    from backend import lemma_cache
    lemma_cache.CACHE_DIR = cache_dir
    lemma_cache.save_cached_units = lambda *a, **k: (_ for _ in ()).throw(
        RuntimeError("refusing to write a lemma cache"))
    return lemma_cache


class CacheProcessor:
    """Stands in for TextProcessor: process_file returns the units of the lemma cache, or fails."""

    def process_file(self, path, language, unit_type="line"):
        from backend import lemma_cache
        name = os.path.basename(path)
        cached = lemma_cache.get_cached_units(name, language)
        if not cached:
            raise RuntimeError(f"no current lemma cache for {language}/{name} in {lemma_cache.CACHE_DIR}")
        return cached["units_phrase" if unit_type == "phrase" else "units_line"]


def install(cache_dir):
    lc = use_cache(cache_dir)
    import backend.text_processor as tpm
    tpm.TextProcessor = CacheProcessor
    # The embeddings, also read-only, from the production folder (a worktree holds only a few).
    from backend import embedding_storage
    embedding_storage.EMBEDDINGS_DIR = PROD_EMBEDDINGS
    # The vectors for statius.achilleid in production have 1,127 rows against 1,125 text lines,
    # and the Juhnke benchmark refuses a mismatch. XL_ACHILLEID_VECTORS names a copy with one
    # row per line, read instead (the run prints a note when it does).
    real_load = embedding_storage.load_embeddings

    def load(text_path, language, space="mono"):
        if ALT_ACHILLEID and os.path.basename(text_path) == "statius.achilleid.tess":
            import numpy as np
            print(f"note: statius.achilleid vectors read from {ALT_ACHILLEID}", flush=True)
            return np.load(ALT_ACHILLEID, allow_pickle=False)
        return real_load(text_path, language, space)
    embedding_storage.load_embeddings = load
    return lc


def set_variant(v):
    count, lone = VARIANTS[v]
    os.environ["XL_DICT_COUNT"] = count
    os.environ["XL_LONE_PAIR"] = lone
    # The evaluation path always uses the v2 lone-pair rule; XL_RULE=baseline reproduces the
    # benchmark scripts' own default for comparison with earlier figures.
    os.environ["XL_RARITY_VARIANT"] = os.environ.get("XL_RULE", "v2")
    return count, lone


def peak_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def run_script(path, argv):
    import runpy
    sys.argv = [str(path)] + argv
    try:
        runpy.run_path(str(path), run_name="__main__")
    except SystemExit as e:
        if e.code not in (None, 0):
            raise


# --------------------------------------------------------------------------------------
def cmd_knauer(a):
    install(a.cache)
    print("variant", a.variant, set_variant(a.variant), flush=True)
    t0 = time.time()
    run_script(ROOT / "evaluation" / "scripts" / "benchmark_knauer_crosslingual.py", [])
    print(f"wall {time.time() - t0:.0f}s peak {peak_mb():.0f} MB")


def cmd_juhnke(a):
    install(a.cache)
    print("variant", a.variant, set_variant(a.variant), flush=True)
    t0 = time.time()
    run_script(ROOT / "evaluation" / "scripts" / "benchmark_juhnke_crosslingual.py",
               ["--gold", a.gold, "--query-lines", "all", "--grade-column", "grade", "--out", a.out])
    d = json.load(open(a.out))
    rows = [r for r in d["pairs"] if r["status"] == "ok"]
    out = {}
    for k in (10, 50, 100, 200):
        out[f"exact@{k}"] = sum(1 for r in rows if r.get("rank_exact") is not None and r["rank_exact"] <= k)
        out[f"tolerance@{k}"] = sum(1 for r in rows if r.get("rank_tolerance") is not None and r["rank_tolerance"] <= k)
    out["rows"] = len(rows)
    d["recall_counts"] = out
    json.dump(d, open(a.out, "w"), ensure_ascii=False, indent=1)
    print("RECALL_COUNTS", json.dumps(out))
    print(f"wall {time.time() - t0:.0f}s peak {peak_mb():.0f} MB")


# --------------------------------------------------------------------------------------
def load_knauer():
    from crosslingual_common import BENCHMARKS_DIR
    gold = json.load(open(BENCHMARKS_DIR / "knauer_aeneid1_iliad.json"))
    by_book = defaultdict(list)
    for gp in gold:
        m = re.search(r"part\.(\d+)", gp.get("source_work", ""))
        if m:
            by_book[int(m.group(1))].append(gp)
    return gold, by_book


def cmd_precision(a):
    install(a.cache)
    count, lone = set_variant(a.variant)
    from crosslingual_common import TEXTS_DIR, ref_matches
    from backend import crosslingual_evaluation_path as ev
    from backend.embedding_storage import load_embeddings
    gold, by_book = load_knauer()
    tp = CacheProcessor()
    lat_path = TEXTS_DIR / "la" / f"{LATIN_BOOK}.tess"
    lat_units = tp.process_file(str(lat_path), "la")
    lat_emb = load_embeddings(str(lat_path), "la")
    res = {"variant": a.variant, "count": count, "lone": lone, "books": {}}
    t0 = time.time()
    tot_hits = tot_rows = 0
    basis = Counter()
    for book in sorted(by_book):
        grc_path = TEXTS_DIR / "grc" / f"homer.iliad.part.{book}.tess"
        grc_units = tp.process_file(str(grc_path), "grc")
        grc_emb = load_embeddings(str(grc_path), "grc")
        t1 = time.time()
        listed = ev.score_pairs(grc_units, lat_units, "grc", str(grc_path), str(lat_path), grc_emb, lat_emb,
                                gate="off", penalty_factor=0.5, min_lemma_matches=2, min_matches=1,
                                max_results=50, dict_count=count, lone_pair=lone)
        secs = time.time() - t1
        hits = 0
        kinds = Counter()
        for r in listed:
            g_ref = grc_units[r["src_idx"]]["ref"]
            l_ref = lat_units[r["tgt_idx"]]["ref"]
            if any(ref_matches(g_ref, gp["source_ref"], 3) and ref_matches(l_ref, gp["target_ref"], 3)
                   for gp in by_book[book]):
                hits += 1
            n = r["distinct"] if r["has_dict"] else 0
            kinds["none" if n == 0 else ("1" if n == 1 else ("2" if n == 2 else "3+"))] += 1
        res["books"][book] = {"rows": len(listed), "hits": hits, "kinds": dict(kinds), "secs": secs}
        tot_hits += hits
        tot_rows += len(listed)
        basis.update(kinds)
        print(f"book {book}: {len(listed)} rows, {hits} hits, {secs:.1f}s", flush=True)
    res["precision_at_50_mean_over_books"] = tot_hits / tot_rows if tot_rows else None
    res["hits"], res["rows"] = tot_hits, tot_rows
    res["kinds_total"] = dict(basis)
    res["one_word_share"] = basis["1"] / tot_rows if tot_rows else None
    res["wall_secs"] = time.time() - t0
    res["peak_mb"] = peak_mb()
    json.dump(res, open(a.out, "w"), indent=1)
    b1 = res["books"][1]
    print(f"PRECISION variant {a.variant} ({count}/{lone}): all 24 books {tot_hits}/{tot_rows} = "
          f"{100 * tot_hits / tot_rows:.2f}%; Iliad 1 {b1['hits']}/{b1['rows']}; "
          f"rows by distinct words {dict(basis)}; one-word share {100 * res['one_word_share']:.1f}%")
    print(f"wall {res['wall_secs']:.0f}s peak {res['peak_mb']:.0f} MB")


# --------------------------------------------------------------------------------------
def rare_context(grc_units, lat_units):
    """Corpus document frequencies and thresholds, as the scorer's 'rare' option reads them."""
    from crosslingual_common import strip_accents
    from backend.fusion import _get_corpus_doc_freqs
    from backend.blueprints.hapax import rare_word_threshold, corpus_work_count
    grc_l = {strip_accents(x) for u in grc_units for x in u.get("lemmas", [])}
    lat_l = {x.lower() for u in lat_units for x in u.get("lemmas", [])}
    return {"grc_df": _get_corpus_doc_freqs(grc_l, "grc"), "la_df": _get_corpus_doc_freqs(lat_l, "la"),
            "grc_thr": rare_word_threshold("grc"), "la_thr": rare_word_threshold("la"),
            "grc_works": corpus_work_count("grc"), "la_works": corpus_work_count("la")}


def wms_rare(wms, ctx):
    """Every matched word on both sides at or under its threshold (the scorer's rule)."""
    return all(ctx["grc_df"].get(g, 0) <= ctx["grc_thr"] and ctx["la_df"].get(lw, 0) <= ctx["la_thr"]
               for g, lw in wms)


def wms_rare_any(wms, ctx):
    """Looser reading: some matched Greek-Latin word pair has both words under their thresholds."""
    return any(ctx["grc_df"].get(g, 0) <= ctx["grc_thr"] and ctx["la_df"].get(lw, 0) <= ctx["la_thr"]
               for g, lw in wms)


def distinct(wms):
    return min(len({g for g, _ in wms}), len({lw for _, lw in wms}))


def cmd_thresholds(a):
    install(a.cache)
    from crosslingual_common import TEXTS_DIR, build_dictionary_scores
    tp = CacheProcessor()
    gu = tp.process_file(str(TEXTS_DIR / "grc" / f"{GREEK}.tess"), "grc")
    lu = tp.process_file(str(TEXTS_DIR / "la" / f"{LATIN}.tess"), "la")
    ctx = rare_context(gu, lu)
    dm = build_dictionary_scores(gu, lu)
    n = len(dm)
    by = Counter()
    lone_rare = lone_rare_any = 0
    for wms in dm.values():
        d = distinct(wms)
        by[d if d < 3 else 3] += 1
        if d == 1:
            lone_rare += wms_rare(wms, ctx)
            lone_rare_any += wms_rare_any(wms, ctx)
    word_pairs = {p for wms in dm.values() for p in wms}
    wp_rare = sum(1 for g, lw in word_pairs
                  if ctx["grc_df"].get(g, 0) <= ctx["grc_thr"] and ctx["la_df"].get(lw, 0) <= ctx["la_thr"])
    out = {"grc_threshold": ctx["grc_thr"], "la_threshold": ctx["la_thr"],
           "grc_works": ctx["grc_works"], "la_works": ctx["la_works"],
           "line_pairs_with_dictionary_match": n, "by_distinct_words": dict(by),
           "lone_pairs": by[1], "lone_pairs_rare_all_words": lone_rare, "lone_pairs_rare_any_word_pair": lone_rare_any,
           "dictionary_channel_kept_under_rare": by[2] + by[3] + lone_rare,
           "distinct_lemma_pairs": len(word_pairs), "lemma_pairs_both_rare": wp_rare}
    print(json.dumps(out, indent=1))
    json.dump(out, open(a.out, "w"), indent=1)
    print(f"peak {peak_mb():.0f} MB")


def cmd_keytable(a):
    install(a.cache)
    from crosslingual_common import TEXTS_DIR, build_dictionary_scores, ref_matches
    tp = CacheProcessor()
    gold, by_book = load_knauer()
    lat_path = TEXTS_DIR / "la" / f"{LATIN}.tess"
    lat_units = tp.process_file(str(lat_path), "la")
    result = {}
    # Knauer: each gold pair is one Greek line and one Latin line.
    k = Counter()
    ctx = None
    for book in sorted(by_book):
        gu = tp.process_file(str(TEXTS_DIR / "grc" / f"homer.iliad.part.{book}.tess"), "grc")
        if ctx is None:
            ctx = rare_context(gu, lat_units)
        else:
            more = rare_context(gu, lat_units)
            ctx["grc_df"].update(more["grc_df"])
            ctx["la_df"].update(more["la_df"])
        for gp in by_book[book]:
            gi = next((i for i, u in enumerate(gu) if ref_matches(u.get("ref", ""), gp["source_ref"], 0)), None)
            li = next((i for i, u in enumerate(lat_units) if ref_matches(u.get("ref", ""), gp["target_ref"], 0)), None)
            if gi is None or li is None:
                k["unresolved"] += 1
                continue
            dm = build_dictionary_scores([gu[gi]], [lat_units[li]]).get((0, 0))
            d = distinct(dm) if dm else 0
            k["pairs"] += 1
            if d == 0:
                k["no dictionary match"] += 1
            elif d == 1:
                k["one distinct word"] += 1
                if wms_rare(dm, ctx):
                    k["one word, clears (all words)"] += 1
                if wms_rare_any(dm, ctx):
                    k["one word, clears (some word pair)"] += 1
            else:
                k["two or more distinct words"] += 1
    result["knauer"] = dict(k)
    # Juhnke line gold: every Latin line of a row with every Homer line of its range; the row's
    # distinct count is the largest over those pairs.
    import csv as _csv
    from benchmark_juhnke_crosslingual import index_units, to_int
    j = Counter()
    rows = [r for r in _csv.DictReader(open(a.gold, encoding="utf-8")) if r["resolved"] == "yes"]
    lat_cache, grc_cache = {}, {}
    for r in rows:
        lw, hw = r["latin_work"], r["homer_work"]
        lb, ls, le = to_int(r["latin_book"]), to_int(r["latin_line_start"]), to_int(r["latin_line_end"])
        hb, hs, he = to_int(r["homer_book"]), to_int(r["homer_line_start"]), to_int(r["homer_line_end"])
        if None in (lb, ls, hb, hs):
            continue
        le = le or ls
        he = he or hs
        if lw not in lat_cache:
            p = TEXTS_DIR / "la" / f"{lw}.tess"
            u = tp.process_file(str(p), "la")
            lat_cache[lw] = (u, index_units(u))
        if (hw, hb) not in grc_cache:
            p = TEXTS_DIR / "grc" / f"{hw}.part.{hb}.tess"
            if not p.exists():
                continue
            u = tp.process_file(str(p), "grc")
            grc_cache[(hw, hb)] = (u, index_units(u))
            more = rare_context(u, [])
            ctx["grc_df"].update(more["grc_df"])
        lu, lidx = lat_cache[lw]
        gu2, gidx = grc_cache[(hw, hb)]
        lis = [lidx[(lb, n)] for n in range(ls, le + 1) if (lb, n) in lidx]
        gis = [gidx[(hb, n)] for n in range(hs, he + 1) if (hb, n) in gidx]
        if not lis or not gis:
            j["unresolved"] += 1
            continue
        for li in lis:
            if lw + str(li) not in ctx.setdefault("_lat_seen", set()):
                ctx["_lat_seen"].add(lw + str(li))
                more = rare_context([], [lu[li]])
                ctx["la_df"].update(more["la_df"])
        best, clears_all, clears_any = 0, False, False
        for li in lis:
            for gi in gis:
                dm = build_dictionary_scores([gu2[gi]], [lu[li]]).get((0, 0))
                d = distinct(dm) if dm else 0
                if d > best:
                    best = d
                    clears_all = d == 1 and wms_rare(dm, ctx)
                    clears_any = d == 1 and wms_rare_any(dm, ctx)
                elif d == best == 1:
                    clears_all = clears_all or wms_rare(dm, ctx)
                    clears_any = clears_any or wms_rare_any(dm, ctx)
        j["rows"] += 1
        if best == 0:
            j["no dictionary match"] += 1
        elif best == 1:
            j["one distinct word"] += 1
            j["one word, clears (all words)"] += clears_all
            j["one word, clears (some word pair)"] += clears_any
        else:
            j["two or more distinct words"] += 1
    result["juhnke"] = dict(j)
    ctx_out = {kk: vv for kk, vv in ctx.items() if kk in ("grc_thr", "la_thr", "grc_works", "la_works")}
    result["thresholds"] = ctx_out
    print(json.dumps(result, indent=1))
    json.dump(result, open(a.out, "w"), indent=1)
    print(f"peak {peak_mb():.0f} MB")


# --------------------------------------------------------------------------------------
def cmd_identity(a):
    """New scorer under its defaults against the scorer as it was, every pair of Aeneid 1 x Iliad 1."""
    install(a.cache)
    from backend.embedding_storage import load_embeddings
    from crosslingual_common import TEXTS_DIR
    import crosslingual_common as new
    spec = importlib.util.spec_from_file_location("crosslingual_common_old", a.old)
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)
    tp = CacheProcessor()
    gp = TEXTS_DIR / "grc" / f"{GREEK}.tess"
    lp = TEXTS_DIR / "la" / f"{LATIN}.tess"
    gu, lu = tp.process_file(str(gp), "grc"), tp.process_file(str(lp), "la")
    ge, le = load_embeddings(str(gp), "grc"), load_embeddings(str(lp), "la")
    for k in ("XL_DICT_COUNT", "XL_LONE_PAIR"):
        os.environ.pop(k, None)
    out = {}
    for rule in ("baseline", "v2"):
        f_old, _ = old.make_fused_scorer(gp, lp, gu, lu, ge, le, verbose=False, lone_pair_rule=rule)
        f_new, _ = new.make_fused_scorer(gp, lp, gu, lu, ge, le, verbose=False, lone_pair_rule=rule)
        worst, differ, n = 0.0, 0, 0
        top_old, top_new = [], []
        for g in range(len(gu)):
            for lx in range(len(lu)):
                so, sn = f_old(g, lx), f_new(g, lx)
                n += 1
                d = abs(so - sn)
                if so != sn:
                    differ += 1
                worst = max(worst, d)
                top_old.append((-so, g, lx))
                top_new.append((-sn, g, lx))
        top_old.sort()
        top_new.sort()
        out[rule] = {"pairs": n, "pairs_with_different_score": differ, "largest_difference": worst,
                     "top200_same_order": top_old[:200] == top_new[:200]}
        print(rule, out[rule], flush=True)
    print(f"peak {peak_mb():.0f} MB")
    return 0 if all(v["pairs_with_different_score"] == 0 and v["top200_same_order"] for v in out.values()) else 1


# --------------------------------------------------------------------------------------
def basis_label(r):
    n = r["distinct"] if r["has_dict"] else 0
    if n == 0:
        return "no dictionary word"
    if n == 1:
        return "1 rare word"
    return f"{n} words"


def cmd_sheet(a):
    install(a.cache)
    from crosslingual_common import TEXTS_DIR
    from backend import crosslingual_evaluation_path as ev
    from backend.embedding_storage import load_embeddings
    from backend.blueprints import search as sm
    tp = CacheProcessor()
    gp = TEXTS_DIR / "grc" / f"{GREEK}.tess"
    lp = TEXTS_DIR / "la" / f"{LATIN}.tess"
    gu, lu = tp.process_file(str(gp), "grc"), tp.process_file(str(lp), "la")
    ge, le = load_embeddings(str(gp), "grc"), load_embeddings(str(lp), "la")
    os.environ["XL_RARITY_VARIANT"] = "v2"
    lists = {}
    for name, lone in (("c", "rare"), ("d", "drop")):
        lists[name] = ev.score_pairs(gu, lu, "grc", str(gp), str(lp), ge, le, gate="off", penalty_factor=0.5,
                                     min_lemma_matches=2, min_matches=1, max_results=50,
                                     dict_count="words", lone_pair=lone)
    union = {}
    for name, rows in lists.items():
        for rank, r in enumerate(rows, 1):
            key = (r["src_idx"], r["tgt_idx"])
            e = union.setdefault(key, {"row": r, "c": "", "d": ""})
            e[name] = rank
    # Marked rows of the first sheet, by their loci.
    base = Path(a.first_sheet)
    marked = {m["row_id"] for m in csv.DictReader(open(a.marks, encoding="utf-8"))}
    first = {}
    for r in csv.DictReader(open(base / "blind_aeneid1_iliad1.csv", encoding="utf-8")):
        first[r["row_id"]] = (r["latin_locus"], r["greek_locus"])
    marked_loci = {first[i] for i in marked if i in first}

    def loci(key):
        g, lx = key
        return (sm.format_short_locus(lu[lx]["ref"]), sm.format_short_locus(gu[g]["ref"]))
    keys = sorted(union, key=lambda k: (k[1], k[0]))
    keep = [k for k in keys if loci(k) not in marked_loci]
    excluded = len(keys) - len(keep)
    random.Random(a.seed).shuffle(keep)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    counts = Counter()
    with open(out / "blind2_aeneid1_iliad1.csv", "w", newline="", encoding="utf-8") as fb, \
            open(out / "key2_aeneid1_iliad1.csv", "w", newline="", encoding="utf-8") as fk:
        wb, wk = csv.writer(fb), csv.writer(fk)
        wb.writerow(["row_id", "latin_locus", "latin_text", "greek_locus", "greek_text",
                     "dictionary_pairs", "basis"])
        wk.writerow(["row_id", "variant_c_rank", "variant_d_rank", "in_both"])
        for i, k in enumerate(keep, 1):
            e = union[k]
            r = e["row"]
            g, lx = k
            pairs = surface_pairs(sm, lu[lx], gu[g])
            rid = f"Q1-{i:03d}"
            basis = basis_label(r)
            counts[basis] += 1
            wb.writerow([rid, loci(k)[0], lu[lx].get("text", ""), loci(k)[1], gu[g].get("text", ""), pairs, basis])
            wk.writerow([rid, e["c"], e["d"], bool(e["c"] and e["d"])])
    n_c = sum(1 for k in keep if union[k]["c"])
    n_d = sum(1 for k in keep if union[k]["d"])
    n_both = sum(1 for k in keep if union[k]["c"] and union[k]["d"])
    summary = {"union_before_exclusion": len(keys), "excluded_already_marked": excluded,
               "rows": len(keep), "in_c_top50": n_c, "in_d_top50": n_d, "in_both": n_both,
               "marked_rows_in_either_top50": excluded, "basis": dict(counts),
               "c_top50_in_union_before_exclusion": sum(1 for k in keys if union[k]["c"]),
               "d_top50_in_union_before_exclusion": sum(1 for k in keys if union[k]["d"])}
    print(json.dumps(summary, indent=1))
    json.dump(summary, open(out / "sheet_summary.json", "w"), indent=1)


def surface_pairs(sm, lat_unit, grc_unit):
    """The word-for-word dictionary pairs of one pair of lines, as the first sheet showed them."""
    found = sm._find_dictionary_matches_fast([lat_unit], [grc_unit], "la", "grc").get((0, 0)) or []
    src_tokens = lat_unit.get("original_tokens", lat_unit.get("tokens", []))
    tgt_tokens = grc_unit.get("original_tokens", grc_unit.get("tokens", []))
    shown = set()
    for wm in found:
        si, ti = wm.get("source_indices") or [], wm.get("target_indices") or []
        sw = src_tokens[si[0]] if si and si[0] < len(src_tokens) else wm.get("source_lemma", "")
        tw = tgt_tokens[ti[0]] if ti and ti[0] < len(tgt_tokens) else wm.get("target_lemma", "")
        shown.add(f"{sw}->{tw}")
    return " | ".join(sorted(shown))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", default=PROD_CACHE, help="lemma cache folder (read only)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("knauer", "juhnke", "precision"):
        p = sub.add_parser(name)
        p.add_argument("variant", choices=sorted(VARIANTS))
        if name != "knauer":
            p.add_argument("out")
        if name == "juhnke":
            p.add_argument("--gold", required=True, help="the Juhnke line-gold CSV")
    p = sub.add_parser("keytable")
    p.add_argument("out")
    p.add_argument("--gold", required=True, help="the Juhnke line-gold CSV")
    p = sub.add_parser("thresholds")
    p.add_argument("out")
    p = sub.add_parser("identity")
    p.add_argument("--old", required=True)
    p = sub.add_parser("sheet")
    p.add_argument("out_dir")
    p.add_argument("--seed", type=int, default=20261018)
    p.add_argument("--first-sheet", required=True, help="folder holding blind_aeneid1_iliad1.csv")
    p.add_argument("--marks", required=True, help="marks.csv of the first sheet (row_id column)")
    a = ap.parse_args()
    rc = {"knauer": cmd_knauer, "juhnke": cmd_juhnke, "precision": cmd_precision, "keytable": cmd_keytable,
          "thresholds": cmd_thresholds, "identity": cmd_identity, "sheet": cmd_sheet}[a.cmd](a)
    return rc or 0


if __name__ == "__main__":
    sys.exit(main())
