#!/usr/bin/env python3
"""Lemma lookups for event names, from the per-work lemma caches (read only).

Usage: lemma_name_index.py EVENTS LABELS COUNTRIES SAMPLE OUT_DIR

Pass 1. Each name token of each event entity (Wikidata labels in English, Latin and Greek, plus the
hand-curated names) is normalised like the name index (norm_full). Every token in every Latin and
Greek cache line whose normalised surface form is one of these is counted with its lemma. The most
frequent lemma of each surface form is the name's lemma. A surface form that never occurs gets no
lemma (the dossier falls back to stem matching for that token).
Pass 2. Every cache line holding a token whose normalised lemma is one of those name lemmas is
recorded as (work, line ord) -> lemmas. build_event_dossier.py maps lines to windows (12 lines each,
stride 6).
Writes OUT_DIR/name_lemmas.json and OUT_DIR/lemma_hits.pkl. Cache line i of a work is line ord i of
window_texts.db (checked on Livy 21-30).
"""
import collections, glob, json, os, pickle, sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_event_dossier as b  # noqa: E402

CACHE = os.path.join(b.PROD, "cache", "lemmas")


def _files():
    return sorted(glob.glob(os.path.join(CACHE, "la", "*-*.json")) + glob.glob(os.path.join(CACHE, "grc", "*-*.json")))


def _lines(path):
    d = json.load(open(path, encoding="utf-8"))
    work = d["text_id"][:-5] if d["text_id"].endswith(".tess") else d["text_id"]
    return work, d["units_line"]


def pass1(args):
    path, surfaces = args
    work, units = _lines(path)
    c = collections.defaultdict(collections.Counter)
    for u in units:
        toks = u.get("original_tokens") or u.get("tokens") or []
        lem = u.get("lemmas") or []
        for t, l in zip(toks, lem):
            n = b.norm_full(t)
            if n in surfaces:
                c[("all", n)][l] += 1
                if t[:1].isupper():
                    c[("cap", n)][l] += 1
    return {k: dict(v) for k, v in c.items()}


def pass2(args):
    path, targets = args
    work, units = _lines(path)
    hits = {}
    for i, u in enumerate(units):
        found = {b.norm_full(l) for l in (u.get("lemmas") or [])} & targets
        if found:
            hits[i] = sorted(found)
    return work, hits


def main(events, labels, countries, sample, out):
    ev, lab, co = b.load_jsonl(events), b.load_jsonl(labels), b.load_jsonl(countries)
    surfaces = set()
    for s in json.load(open(sample))["events"]:
        for e in b.build_entities(ev[s["qid"]], lab, co, s.get("curated_names", [])):
            for v in e["names"]:
                surfaces |= b.label_tokens(v)
    print("name surfaces", len(surfaces), file=sys.stderr)
    files = _files()
    cnt = collections.defaultdict(collections.Counter)
    with Pool(5) as p:
        for i, r in enumerate(p.imap_unordered(pass1, [(f, surfaces) for f in files], chunksize=1)):
            for k, v in r.items():
                cnt[k].update(v)
            if i % 300 == 0:
                print("pass1", i, len(files), file=sys.stderr)
    top_all = {k[1]: v.most_common(1)[0][0] for k, v in cnt.items() if k[0] == "all"}
    top_cap = {k[1]: v.most_common(1)[0][0] for k, v in cnt.items() if k[0] == "cap"}
    # the lemma of a name: the most frequent lemma of its CAPITALISED occurrences, else of all of them
    top = dict(top_all)
    top.update(top_cap)
    alts = {k[0] + ":" + k[1]: v.most_common(4) for k, v in cnt.items()}
    os.makedirs(out, exist_ok=True)
    json.dump({"top": top, "top_all": top_all, "top_cap": top_cap, "counts": alts},
              open(os.path.join(out, "name_lemmas.json"), "w"), ensure_ascii=False, indent=1)
    targets = {b.norm_full(l) for l in list(top_all.values()) + list(top_cap.values())}
    print("surfaces with a lemma", len(top), "target lemmas", len(targets), file=sys.stderr, flush=True)
    hits = {}
    with Pool(5) as p:
        for i, (work, h) in enumerate(p.imap_unordered(pass2, [(f, targets) for f in files], chunksize=1)):
            if h:
                hits.setdefault(work, {}).update(h)
            if i % 300 == 0:
                print("pass2", i, len(files), file=sys.stderr)
    pickle.dump(hits, open(os.path.join(out, "lemma_hits.pkl"), "wb"))
    print("works with hits", len(hits), "lines", sum(len(v) for v in hits.values()))


if __name__ == "__main__":
    main(*sys.argv[1:6])
