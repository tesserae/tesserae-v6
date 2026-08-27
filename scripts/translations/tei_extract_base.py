#!/usr/bin/env python3
"""
Unified extractor. Walks the TEI body in document order and records, for every chunk of
translated text, the full set of citation anchors in force at that point:

  * structural <div n=".." subtype="book|chapter|section|card|..">
  * <milestone unit="book|chapter|section|verse|line|card|page" n=".."/>
  * <l n=".."/>  (dense = real lines, sparse = every-5th-line anchors)

The caller then decides how to compose a reference out of those anchors, and picks the
composition that best reproduces our own .tess reference scheme.
"""
import glob, json, os, re, collections
from lxml import etree

PARSER = etree.XMLParser(recover=True, resolve_entities=False, load_dtd=False, no_network=True)

T = "{http://www.tei-c.org/ns/1.0}"
ROOT = "/home/ncoffee/perseus_trans/work"

# <reg> holds an editorial/gazetteer normalisation that sits beside the reading itself,
# e.g. <name type="place"><reg>Bodrum ... Turkey, Asia </reg><placeName>Halicarnassus</placeName></name>
# Keeping it would splice gazetteer prose into the translation.
DROP = {f"{T}note", f"{T}bibl", f"{T}head", f"{T}gap", f"{T}figure",
        f"{T}castList", f"{T}argument", f"{T}del", f"{T}orig", f"{T}reg"}

# anchors we care about, coarse -> fine
UNITS = ["book", "chapter", "section", "subsection", "verse", "poem", "epistle",
         "letter", "fragment", "card", "para", "line", "page", "speech", "oath"]


def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace(" ", " ")).strip()


def header(r):
    m = {}
    ts = r.find(f".//{T}fileDesc/{T}titleStmt")
    def g(node, tag):
        e = node.find(tag) if node is not None else None
        return clean("".join(e.itertext())) if e is not None else None
    if ts is not None:
        m["title"] = g(ts, f"{T}title")
        m["author"] = g(ts, f"{T}author")
        eds = [clean("".join(x.itertext())) for x in ts.findall(f"{T}editor")]
        m["translator"] = eds[0] if eds else None
    mon = r.find(f".//{T}sourceDesc//{T}monogr")
    if mon is not None:
        m["source_title"] = g(mon, f"{T}title")
        if not m.get("translator"):
            se = [clean("".join(x.itertext())) for x in mon.findall(f"{T}editor")]
            m["translator"] = se[0] if se else None
    imp = r.find(f".//{T}sourceDesc//{T}imprint")
    if imp is not None:
        m["pub_date_raw"] = g(imp, f"{T}date")
        m["publisher"] = g(imp, f"{T}publisher")
        m["pub_place"] = g(imp, f"{T}pubPlace")
    m["year"] = None
    if m.get("pub_date_raw"):
        yrs = re.findall(r"(1[5-9]\d\d|20\d\d)", m["pub_date_raw"])
        if yrs:
            m["year_first"] = int(yrs[0])
            m["year"] = int(yrs[-1])
    rd = r.find(f".//{T}refsDecl[@n='CTS']")
    if rd is not None:
        m["ref_labels"] = list(reversed([c.get("n") for c in rd.iter(f"{T}cRefPattern")]))
    else:
        m["ref_labels"] = []
    return m


def extract(path):
    r = etree.parse(path, PARSER).getroot()
    meta = header(r)
    base = os.path.basename(path)[:-4]
    meta["cts_urn"] = "urn:cts:%sLit:%s" % ("greek" if "greekLit" in path else "latin", base)
    meta["source_file"] = os.path.relpath(path, ROOT)
    body = r.find(f".//{T}text/{T}body")
    if body is None:
        return meta, []

    chunks = []          # [{"anchors": {...}, "divpath": [...], "text": str}]
    divstack = []        # [(subtype, n)]
    ms = {}              # unit -> value
    buf = []
    state = [None]

    def snapshot():
        a = {}
        for st, n in divstack:
            if n is not None and not str(n).startswith("urn:"):
                a.setdefault(st or "div", str(n))
        for u, v in ms.items():
            v = str(v)
            cur = a.get(u)
            if cur is None:
                a[u] = v
            elif v.startswith(cur) and len(v) > len(cur):
                # a finer subdivision of the same anchor, e.g. Stephanus 17a inside div 17
                a[u] = v
            # otherwise the real <div> anchor wins over a stray milestone
        return a

    def flush():
        t = clean("".join(buf))
        buf.clear()
        if t and state[0] is not None:
            chunks.append({"anchors": state[0][0], "divpath": state[0][1], "text": t})

    def newstate():
        dp = [str(n) for st, n in divstack if n is not None and not str(n).startswith("urn:")]
        state[0] = (snapshot(), dp)

    def rec(e):
        tag = e.tag
        if tag in DROP:
            if e.tail:
                buf.append(e.tail)
            return
        if tag == f"{T}milestone":
            u = (e.get("unit") or "").lower()
            if u in UNITS and e.get("n") is not None:
                flush()
                ms[u] = e.get("n")
                # clear finer units
                if u in UNITS:
                    i = UNITS.index(u)
                    for f in UNITS[i + 1:]:
                        ms.pop(f, None)
                newstate()
            if e.tail:
                buf.append(e.tail)
            return
        if tag in (f"{T}div", f"{T}div1", f"{T}div2", f"{T}div3"):
            n = e.get("n")
            st = (e.get("subtype") or e.get("type") or "div").lower()
            if st in ("textpart",):
                st = (e.get("subtype") or "div").lower()
            flush()
            divstack.append((st if st in UNITS else "div", n))
            # entering a div clears milestone anchors finer than it
            if st in UNITS:
                for f in UNITS[UNITS.index(st):]:
                    ms.pop(f, None)
            newstate()
            if e.text:
                buf.append(e.text)
            for c in e:
                rec(c)
            flush()
            divstack.pop()
            newstate()
            if e.tail:
                buf.append(e.tail)
            return
        if tag == f"{T}l" and e.get("n") is not None:
            flush()
            ms["line"] = e.get("n")
            newstate()
            if e.text:
                buf.append(e.text)
            for c in e:
                rec(c)
            flush()
            if e.tail:
                buf.append(e.tail)
            return
        if e.text:
            buf.append(e.text)
        for c in e:
            rec(c)
        if e.tail:
            buf.append(e.tail)

    newstate()
    if body.text:
        buf.append(body.text)
    for c in body:
        rec(c)
    flush()

    # merge consecutive chunks that share the identical anchor set
    merged = []
    for c in chunks:
        if merged and merged[-1]["anchors"] == c["anchors"]:
            merged[-1]["text"] += " " + c["text"]
        else:
            merged.append(c)
    meta["anchor_units"] = sorted({u for c in merged for u in c["anchors"]})
    return meta, merged


def main():
    files = sorted(glob.glob(f"{ROOT}/canonical-greekLit/data/*/*/*eng*.xml")) + \
            sorted(glob.glob(f"{ROOT}/canonical-latinLit/data/*/*/*eng*.xml"))
    out = []
    errs = 0
    for p in files:
        try:
            meta, chunks = extract(p)
        except Exception as e:
            errs += 1
            out.append({"meta": {"source_file": os.path.relpath(p, ROOT), "cts_urn": None},
                        "error": str(e), "chunks": []})
            continue
        meta["n_chunks"] = len(chunks)
        out.append({"meta": meta, "chunks": chunks})
    json.dump(out, open(f"{ROOT}/extracted5.json", "w"), ensure_ascii=False)
    print("files:", len(out), "errors:", errs,
          "chunks:", sum(len(r["chunks"]) for r in out))
    cu = collections.Counter()
    for r in out:
        cu[tuple(r["meta"].get("anchor_units") or [])] += 1
    for k, v in cu.most_common(15):
        print(f"  {v:5d} {k}")


if __name__ == "__main__":
    main()
