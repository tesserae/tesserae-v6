#!/usr/bin/env python3
"""Trismegistos-place to Pleiades crosswalk, and EDH/EDR findspot
coverage after applying it.

Stage 1 found EDH and EDR link findspots to Trismegistos place ids inside
`<placeName ref="...">` (0.0% direct Pleiades coverage for both), while
I.Sicily and papyri.info/HGV link straight to Pleiades (97.5% / 74.7%).
This script builds a Trismegistos-place-id -> Pleiades-id crosswalk from
two openly licensed sources and reports what it buys EDH and EDR.

Crosswalk sources (both read-only, nothing fetched here is modified):

1. **EDH's own geography file**, `geography/edhGeographicData.json` in the
   EDH GitHub repository (CC BY-SA 4.0, the same license as the rest of
   EDH), which pairs a `trismegistos_geo_uri` and a `pleiades_uri` for
   each of its ~2,000 named findspots directly: EDH already maintains
   this crosswalk for its own use, openly. This is the primary source.
2. **The Pleiades places dump** itself (CC BY 3.0,
   https://pleiades.stoa.org/downloads), whose `references` array
   sometimes cites a place's Trismegistos record (`shortTitle: "TM"`,
   `accessURI` containing `trismegistos.org/place/<id>`). Used to
   cross-check EDH's file and to independently supplement it.

Where to find the id to join on: EDH's and (checked here, see
`count_edr_place_refs`) NOT EDR's raw inscription XML tags the ancient
findspot's `<placeName>` with `ref="http://www.trismegistos.org/place/<id>"`
(confirmed directly in the source XML; EDH's own converted JSON, from
stage 1, does not carry this attribute, since
`scripts/documents/epidoc_convert.py`'s `extract_findspot` never read it;
this script re-reads the raw XML instead of changing that converter).

EDR's raw XML carries NO `ref=` attribute on any `<placeName>` anywhere
in its full 115,591-file export (verified with a full-corpus grep, not a
sample, before writing this module), and the EDR Zenodo deposit ships no
separate geography file the way EDH's GitHub repository does. EDR
findspots are plain text only; this crosswalk cannot add an identifier
EDR never recorded. Matching EDR's place names to Pleiades by text
similarity would need fuzzy name matching, which the spec's "use only
openly licensed data" ask does not extend to call for scraping or
guessing; left as an open idea in the report, not attempted here.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
from collections import Counter, defaultdict

from lxml import etree

TM_URI_RE = re.compile(r"trismegistos\.org/place/0*(\d+)", re.IGNORECASE)
PLEIADES_URI_RE = re.compile(r"pleiades\.stoa\.org/places/(\d+)")


def build_crosswalk_from_edh_geography(path: str):
    """tm_place_id (int) -> {"pleiades_id": str, "ancient_findspot": str}"""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    crosswalk = {}
    for feat in data.get("features", []):
        props = feat.get("properties", {}) or {}
        tm_uri = props.get("trismegistos_geo_uri")
        pl_uri = props.get("pleiades_uri")
        if not tm_uri or not pl_uri:
            continue
        m_tm = TM_URI_RE.search(tm_uri)
        m_pl = PLEIADES_URI_RE.search(pl_uri)
        if not m_tm or not m_pl:
            continue
        tm_id = int(m_tm.group(1))
        crosswalk[tm_id] = {
            "pleiades_id": m_pl.group(1),
            "ancient_findspot": props.get("ancient_findspot"),
            "source": "edh_geography",
        }
    return crosswalk


def build_crosswalk_from_pleiades(path: str):
    """tm_place_id (int) -> {"pleiades_id": str, "title": str}, from the
    Pleiades CC BY 3.0 places dump's own Trismegistos backlinks.

    Streams the dump with ijson, one `@graph` item at a time, instead of
    `json.load`-ing the whole 135MB (decompressed) file: a first attempt
    with a plain `json.load` measured a 16.3GB peak RSS (the place
    records carry large nested `locations`/`connections`/`names` arrays
    that are not needed here), well over this stage's 6G job cap; ijson
    discards each place's structure as soon as its few needed fields are
    read, and peak memory for this function alone measured under 300MB."""
    import ijson

    opener = gzip.open if path.endswith(".gz") else open
    crosswalk = {}
    with opener(path, "rb") as f:
        for place in ijson.items(f, "@graph.item"):
            pid = place.get("id")
            for ref in place.get("references", []) or []:
                blob = " ".join(str(ref.get(k, "")) for k in
                                 ("accessURI", "shortTitle", "citationDetail"))
                m = TM_URI_RE.search(blob)
                if m and pid:
                    tm_id = int(m.group(1))
                    crosswalk[tm_id] = {
                        "pleiades_id": pid,
                        "title": place.get("title"),
                        "source": "pleiades_dump",
                    }
    return crosswalk


def merge_crosswalks(primary: dict, secondary: dict):
    """primary (EDH geography) wins; secondary (Pleiades dump) fills gaps
    and its agreement/disagreement with primary is tallied."""
    merged = dict(primary)
    agree = disagree = added = 0
    for tm_id, rec in secondary.items():
        if tm_id in primary:
            if primary[tm_id]["pleiades_id"] == rec["pleiades_id"]:
                agree += 1
            else:
                disagree += 1
        else:
            merged[tm_id] = rec
            added += 1
    return merged, {"agree": agree, "disagree": disagree, "added_from_secondary": added}


def find_disagreements(primary: dict, secondary: dict):
    """List every tm_id both crosswalks cover with a DIFFERENT Pleiades
    id, each as (tm_id, primary_pleiades_id, secondary_pleiades_id,
    primary_label, secondary_label), sorted by tm_id. Used for the
    manual spot check of which source to trust on conflict; not called
    by `merge_crosswalks` itself (which already picks primary and only
    tallies the count)."""
    rows = []
    for tm_id, prim_rec in primary.items():
        sec_rec = secondary.get(tm_id)
        if sec_rec and sec_rec["pleiades_id"] != prim_rec["pleiades_id"]:
            rows.append((
                tm_id, prim_rec["pleiades_id"], sec_rec["pleiades_id"],
                prim_rec.get("ancient_findspot") or "",
                sec_rec.get("title") or "",
            ))
    rows.sort(key=lambda r: r[0])
    return rows


def iter_edh_files(input_dir: str):
    for dirpath, _, filenames in os.walk(input_dir):
        for name in filenames:
            if name.endswith(".xml"):
                yield os.path.join(dirpath, name)


NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def extract_edh_ancient_place_tm_ref(path: str):
    """Return (edh_id, tm_place_id or None, ancient_place_text or None)
    from one raw EDH inscription XML file, reading the
    <origPlace><placeName ref="...trismegistos.org/place/NNN"> the
    convert script does not currently capture."""
    try:
        root = etree.parse(path).getroot()
    except etree.XMLSyntaxError:
        return None, None, None
    edh_id = os.path.splitext(os.path.basename(path))[0]
    tm_id = None
    text = None
    for origin in root.iter("{http://www.tei-c.org/ns/1.0}origin"):
        for pn in origin.iter("{http://www.tei-c.org/ns/1.0}placeName"):
            ref = pn.get("ref") or ""
            m = TM_URI_RE.search(ref)
            if m:
                ptype = pn.get("type")
                if ptype not in ("provinceItalicRegion", "region"):
                    tm_id = int(m.group(1))
                    text = "".join(pn.itertext()).strip()
                    break
        if tm_id is not None:
            break
    return edh_id, tm_id, text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edh-geography-json", required=True)
    ap.add_argument("--pleiades-dump", required=True)
    ap.add_argument("--edh-inscriptions-dir", required=True)
    ap.add_argument("--edr-inscriptions-dir", required=True)
    ap.add_argument("--crosswalk-out", required=True)
    ap.add_argument("--edh-place-links-out", required=True)
    ap.add_argument("--summary-out", required=True)
    ap.add_argument("--disagreements-out", default=None,
                     help="optional TSV of every tm_id where the EDH "
                          "geography file and the Pleiades dump's own "
                          "backlink disagree, for a manual spot check")
    args = ap.parse_args(argv)

    edh_cw = build_crosswalk_from_edh_geography(args.edh_geography_json)
    pleiades_cw = build_crosswalk_from_pleiades(args.pleiades_dump)
    crosswalk, cw_stats = merge_crosswalks(edh_cw, pleiades_cw)

    if args.disagreements_out:
        rows = find_disagreements(edh_cw, pleiades_cw)
        with open(args.disagreements_out, "w", encoding="utf-8") as f:
            f.write("tm_id\tedh_pleiades_id\tpleiades_dump_pleiades_id\t"
                    "edh_label\tpleiades_dump_title\n")
            for tm_id, p_id, s_id, p_label, s_label in rows:
                f.write(f"{tm_id}\t{p_id}\t{s_id}\t{p_label}\t{s_label}\n")

    with open(args.crosswalk_out, "w", encoding="utf-8") as f:
        f.write("tm_place_id\tpleiades_id\tsource\tlabel\n")
        for tm_id, rec in sorted(crosswalk.items()):
            label = rec.get("ancient_findspot") or rec.get("title") or ""
            f.write(f"{tm_id}\t{rec['pleiades_id']}\t{rec['source']}\t{label}\n")

    # EDH: re-read raw XML for the ancient-place TM ref per document.
    edh_total = 0
    edh_with_tm_ref = 0
    edh_with_pleiades_via_crosswalk = 0
    rows = []
    for path in iter_edh_files(args.edh_inscriptions_dir):
        edh_total += 1
        edh_id, tm_id, text = extract_edh_ancient_place_tm_ref(path)
        if edh_id is None:
            continue
        pleiades_id = None
        if tm_id is not None:
            edh_with_tm_ref += 1
            rec = crosswalk.get(tm_id)
            if rec:
                pleiades_id = rec["pleiades_id"]
                edh_with_pleiades_via_crosswalk += 1
        rows.append((edh_id, tm_id, pleiades_id, text))

    with open(args.edh_place_links_out, "w", encoding="utf-8") as f:
        f.write("edh_id\ttm_place_id\tpleiades_id\tancient_place_text\n")
        for edh_id, tm_id, pleiades_id, text in rows:
            f.write(f"{edh_id}\t{tm_id if tm_id is not None else ''}\t"
                    f"{pleiades_id if pleiades_id is not None else ''}\t{text or ''}\n")

    # EDR: confirm, over the FULL corpus (not a sample), that no raw file
    # carries a placeName ref attribute at all.
    edr_total = 0
    edr_with_ref = 0
    for dirpath, _, filenames in os.walk(args.edr_inscriptions_dir):
        for name in filenames:
            if not name.endswith(".xml"):
                continue
            edr_total += 1
            path = os.path.join(dirpath, name)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
            except OSError:
                continue
            if re.search(r'placeName[^>]*\bref=', content):
                edr_with_ref += 1

    summary = {
        "crosswalk_entries": len(crosswalk),
        "crosswalk_merge": cw_stats,
        "edh_geography_entries": len(edh_cw),
        "pleiades_dump_tm_backlinks": len(pleiades_cw),
        "edh_total_documents": edh_total,
        "edh_with_ancient_place_tm_ref": edh_with_tm_ref,
        "edh_with_ancient_place_tm_ref_share": round(edh_with_tm_ref / edh_total, 4) if edh_total else None,
        "edh_with_pleiades_via_crosswalk": edh_with_pleiades_via_crosswalk,
        "edh_with_pleiades_via_crosswalk_share": round(edh_with_pleiades_via_crosswalk / edh_total, 4) if edh_total else None,
        "edh_pleiades_coverage_before_stage1": 0.0,
        "edr_total_documents": edr_total,
        "edr_with_any_placeName_ref_attr": edr_with_ref,
        "edr_pleiades_coverage_after_crosswalk": 0.0,
        "edr_note": "EDR raw XML carries no placeName ref attribute anywhere "
                     "in the full export; this crosswalk cannot add an "
                     "identifier EDR never recorded.",
    }
    with open(args.summary_out, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(json.dumps(summary, indent=2, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
