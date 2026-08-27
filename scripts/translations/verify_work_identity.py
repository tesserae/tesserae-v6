#!/usr/bin/env python3
"""
Content-based verification: confirm that a .tess work really IS a given Perseus work
by comparing the actual source-language text, not the title string.
Also lets one .tess work map to several Perseus work URNs (e.g. Livy's book groups).
"""
import glob, json, os, re, collections, unicodedata
from lxml import etree

PARSER = etree.XMLParser(recover=True, resolve_entities=False, load_dtd=False, no_network=True)

T = "{http://www.tei-c.org/ns/1.0}"
ROOT = os.environ.get("TESSERAE_PERSEUS_WORK", "/home/ncoffee/perseus_trans/work")
TEXTS = os.environ.get("TESSERAE_TEXTS", "/var/www/tesseraev6_flask/texts")
DROP = {f"{T}note", f"{T}bibl", f"{T}head", f"{T}speaker", f"{T}teiHeader"}


def strip_acc(s):
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def toks(s, lang):
    s = strip_acc(s.lower())
    s = s.replace("j", "i").replace("v", "u")
    if lang == "grc":
        return re.findall(r"[Ͱ-Ͽἀ-῿]{4,}", s)
    return re.findall(r"[a-z]{4,}", s)


def xml_text(path):
    try:
        r = etree.parse(path, PARSER).getroot()
    except Exception:
        return ""
    body = r.find(f".//{T}text/{T}body")
    if body is None:
        return ""
    out = []
    def rec(e):
        if e.tag in DROP:
            if e.tail: out.append(e.tail)
            return
        if e.text: out.append(e.text)
        for c in e: rec(c)
        if e.tail: out.append(e.tail)
    rec(body)
    return " ".join(out)


def build_source_index():
    """Perseus work_urn -> token multiset of the ORIGINAL-language text."""
    idx = {}
    files = glob.glob(f"{ROOT}/canonical-greekLit/data/*/*/*.xml") + \
            glob.glob(f"{ROOT}/canonical-latinLit/data/*/*/*.xml")
    for p in files:
        b = os.path.basename(p)
        if b == "__cts__.xml" or "-eng" in b:
            continue
        lang = "grc" if "greekLit" in p else "la"
        if lang == "grc" and "-grc" not in b:
            continue
        if lang == "la" and not re.search(r"-(lat|lat\d)", b):
            continue
        wk = ".".join(b[:-4].split(".")[:2])
        t = toks(xml_text(p), lang)
        if not t:
            continue
        cur = idx.setdefault(wk, {"lang": lang, "tokens": collections.Counter(), "files": []})
        cur["tokens"].update(t)
        cur["files"].append(b)
    return idx


def main():
    cache = f"{ROOT}/source_index.json"
    if os.path.exists(cache):
        raw = json.load(open(cache))
        idx = {k: {"lang": v["lang"], "tokens": collections.Counter(v["tokens"]), "files": v["files"]}
               for k, v in raw.items()}
    else:
        idx = build_source_index()
        json.dump({k: {"lang": v["lang"], "tokens": dict(v["tokens"]), "files": v["files"]}
                   for k, v in idx.items()}, open(cache, "w"), ensure_ascii=False)
    print("perseus source works indexed:", len(idx))

    # inverted index over distinctive tokens
    df = collections.Counter()
    for wk, v in idx.items():
        for t in v["tokens"]:
            df[t] += 1
    inv = collections.defaultdict(set)
    N = len(idx)
    for wk, v in idx.items():
        for t in v["tokens"]:
            if df[t] <= N * 0.05:  # distinctive
                inv[t].add(wk)

    # tess work token sets
    tess_files = collections.defaultdict(list)
    for lang in ("la", "grc"):
        for p in sorted(glob.glob(f"{TEXTS}/{lang}/*.tess")):
            base = os.path.basename(p)[:-5]
            wk = re.sub(r"\.part\.\d+(\.[a-z0-9_\-]+)?$", "", base)
            tess_files[(lang, wk)].append(p)

    results = []
    for (lang, wk), paths in sorted(tess_files.items()):
        cnt = collections.Counter()
        n_tok = 0
        for p in paths:
            with open(p, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = re.sub(r"^<[^>]*>", "", line)
                    for t in toks(line, lang):
                        cnt[t] += 1
                        n_tok += 1
        if not cnt:
            continue
        # score candidates by distinctive-token containment
        votes = collections.Counter()
        dist = [t for t in cnt if df.get(t, 0) and df[t] <= N * 0.05]
        for t in dist:
            for wkc in inv.get(t, ()):
                votes[wkc] += 1
        cands = []
        for wkc, v in votes.most_common(25):
            if idx[wkc]["lang"] != lang:
                continue
            a, b = set(cnt), set(idx[wkc]["tokens"])
            containment = len(a & b) / len(a) if a else 0        # how much of OUR text is in theirs
            rev = len(a & b) / len(b) if b else 0                # how much of theirs is in ours
            cands.append({"work_urn": wkc, "containment": round(containment, 4),
                          "reverse": round(rev, 4), "jaccard": round(len(a & b) / len(a | b), 4)})
        cands.sort(key=lambda c: -c["containment"])
        results.append({"tess": f"{lang}/{wk}", "lang": lang, "n_tokens": n_tok,
                        "n_types": len(cnt), "candidates": cands[:8]})
    json.dump(results, open(f"{ROOT}/verified.json", "w"), indent=1, ensure_ascii=False)
    strong = [r for r in results if r["candidates"] and r["candidates"][0]["containment"] >= 0.75]
    print("tess works:", len(results), "with a strong content match:", len(strong))


if __name__ == "__main__":
    main()
