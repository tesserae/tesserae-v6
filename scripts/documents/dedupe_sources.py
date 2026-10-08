#!/usr/bin/env python3
"""Deduplicate EDH and EDR by shared Trismegistos id, and cross-check the
other two converted sources (papyri.info, I.Sicily) against the rest by TM
id too.

Stage 1 found 10,238 Trismegistos ids shared between EDH and EDR (plus much
smaller overlaps: EDH/I.Sicily 170, I.Sicily/EDR 719, EDH/papyri 89,
I.Sicily/papyri 1, papyri/EDR 2). This script:

1. Indexes every converted source by `tm_id` (records with no tm_id are
   left alone; they cannot be deduplicated by this method).
2. For the EDH/EDR overlap, writes a field-by-field comparison sample
   (`--sample-out`) for a given number of shared pairs, for human review.
3. Merges EDH/EDR pairs under a fixed, recorded per-field rule (see
   `merge_edh_edr_pair`) into one record carrying both source ids and a
   `provenance` map naming which source supplied each field.
4. Reports the small cross-source overlaps (EDH/I.Sicily, I.Sicily/EDR,
   EDH/papyri, I.Sicily/papyri, papyri/EDR) by tm_id, without merging them:
   stage 1 found these overlaps too small (1 to 719 pairs) to justify a
   second merge rule, and the four sources are catalogued independently
   enough (different scripts/genres mostly) that flagging, not merging, is
   the safer default. The flag is carried as `cross_source_overlap` listing
   the other source ids sharing this tm_id, added to every record (EDH/EDR
   merged or not, papyri, I.Sicily) that has a tm_id appearing in more than
   one source.

Does not touch any file under /var/www. Reads the stage 1 converted JSONL,
writes to --output and --sample-out only.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict


def load_jsonl(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def index_by_tm(records):
    by_tm = defaultdict(list)
    for r in records:
        tm = r.get("tm_id")
        if tm is not None:
            by_tm[tm].append(r)
    return by_tm


def total_chars_restored(rec):
    return rec.get("total_chars", 0), rec.get("supplied_chars", 0)


def pick_text_source(edh_rec, edr_rec):
    """Rule: prefer the record with the lower supplied_share (less of its
    text was supplied by an editor, i.e. more of it was actually read on
    the stone), since that is a direct, recorded measure of how much of
    the transcription is the editor's guess rather than the source. Ties
    (equal supplied_share, including both 0.0) break toward the record
    with more total_chars (the fuller transcription). A remaining tie
    breaks toward EDH, recorded as a decision below, not a measurement."""
    edh_total, edh_sup = total_chars_restored(edh_rec)
    edr_total, edr_sup = total_chars_restored(edr_rec)
    edh_share = (edh_sup / edh_total) if edh_total else 1.0
    edr_share = (edr_sup / edr_total) if edr_total else 1.0
    if edh_share < edr_share:
        return "edh"
    if edr_share < edh_share:
        return "edr"
    if edh_total > edr_total:
        return "edh"
    if edr_total > edh_total:
        return "edr"
    return "edh"  # recorded tie-break, see module docstring / report


def pick_date_source(edh_rec, edr_rec):
    """Rule: prefer the record with a narrower non-null date range (more
    precise dating); a record with no date range at all loses to one that
    has any range. Equal range width breaks toward EDH (tie-break, see
    report): EDH's dating is centrally reviewed by a single editorial
    board page by page, which is the stated basis for preferring it on a
    tie, not a measured property of this sample."""
    def width(rec):
        a, b = rec.get("date_not_before"), rec.get("date_not_after")
        if a is None or b is None:
            return None
        return b - a

    wh, wr = width(edh_rec), width(edr_rec)
    if wh is None and wr is None:
        return "edh"
    if wh is None:
        return "edr"
    if wr is None:
        return "edh"
    if wh < wr:
        return "edh"
    if wr < wh:
        return "edr"
    return "edh"


def pick_place_source(edh_rec, edr_rec):
    """Rule: prefer the record that names an ancient_place (not just a
    modern_place) over one that does not; then prefer the one with a
    pleiades_id; then a region string; ties break toward EDR, because EDR
    is the source weighted toward Italy and specifically curates findspot
    detail for Italian material, which is where most of the EDH/EDR
    overlap sits (both catalogue widely, but the shared ids are
    disproportionately Italian: see report for the sample evidence)."""
    def score(rec):
        fs = rec.get("findspot") or {}
        s = 0
        if fs.get("ancient_place"):
            s += 4
        if fs.get("pleiades_id"):
            s += 2
        if fs.get("region"):
            s += 1
        return s

    sh, sr = score(edh_rec), score(edr_rec)
    if sh > sr:
        return "edh"
    if sr > sh:
        return "edr"
    return "edr"


def merge_edh_edr_pair(edh_rec, edr_rec):
    text_src = pick_text_source(edh_rec, edr_rec)
    date_src = pick_date_source(edh_rec, edr_rec)
    place_src = pick_place_source(edh_rec, edr_rec)
    text_from = edh_rec if text_src == "edh" else edr_rec
    date_from = edh_rec if date_src == "edh" else edr_rec
    place_from = edh_rec if place_src == "edh" else edr_rec

    merged = {
        "id": f"merged:{edh_rec.get('tm_id')}",
        "source": "edh+edr",
        "tm_id": edh_rec.get("tm_id"),
        "hgv_id": edh_rec.get("hgv_id") or edr_rec.get("hgv_id"),
        "edh_id": edh_rec.get("edh_id"),
        "edr_id": edr_rec.get("edr_id"),
        "edcs_id": edh_rec.get("edcs_id") or edr_rec.get("edcs_id"),
        "languages": text_from.get("languages"),
        "bilingual": text_from.get("bilingual"),
        "title": text_from.get("title") or (edh_rec if text_src != "edh" else edr_rec).get("title"),
        "object_type": edh_rec.get("object_type") or edr_rec.get("object_type"),
        "material": edh_rec.get("material") or edr_rec.get("material"),
        "date_not_before": date_from.get("date_not_before"),
        "date_not_after": date_from.get("date_not_after"),
        "findspot": place_from.get("findspot"),
        "lines": text_from.get("lines"),
        "text": text_from.get("text"),
        "supplied_chars": text_from.get("supplied_chars"),
        "total_chars": text_from.get("total_chars"),
        "gap_count": text_from.get("gap_count"),
        "supplied_share": text_from.get("supplied_share"),
        "provenance": {
            "text": text_src,
            "date": date_src,
            "findspot": place_src,
            "ids": "both",
        },
    }
    return merged


def write_sample(pairs, sample_size, out_path, seed=20261007):
    rng = random.Random(seed)
    chosen = rng.sample(pairs, min(sample_size, len(pairs)))
    rows = []
    for edh_rec, edr_rec in chosen:
        rows.append({
            "tm_id": edh_rec.get("tm_id"),
            "edh_id": edh_rec.get("edh_id"),
            "edr_id": edr_rec.get("edr_id"),
            "edh_text": edh_rec.get("text"),
            "edr_text": edr_rec.get("text"),
            "edh_supplied_share": edh_rec.get("supplied_share"),
            "edr_supplied_share": edr_rec.get("supplied_share"),
            "edh_date": [edh_rec.get("date_not_before"), edh_rec.get("date_not_after")],
            "edr_date": [edr_rec.get("date_not_before"), edr_rec.get("date_not_after")],
            "edh_findspot": edh_rec.get("findspot"),
            "edr_findspot": edr_rec.get("findspot"),
            "text_pick": pick_text_source(edh_rec, edr_rec),
            "date_pick": pick_date_source(edh_rec, edr_rec),
            "place_pick": pick_place_source(edh_rec, edr_rec),
        })
    with open(out_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edh", required=True)
    ap.add_argument("--edr", required=True)
    ap.add_argument("--papyri", default=None)
    ap.add_argument("--isicily", default=None)
    ap.add_argument("--output", required=True, help="merged corpus JSONL (all sources)")
    ap.add_argument("--sample-out", default=None, help="field-comparison sample JSONL")
    ap.add_argument("--sample-size", type=int, default=50)
    args = ap.parse_args(argv)

    edh = load_jsonl(args.edh)
    edr = load_jsonl(args.edr)
    papyri = load_jsonl(args.papyri) if args.papyri else []
    isicily = load_jsonl(args.isicily) if args.isicily else []

    edh_by_tm = index_by_tm(edh)
    edr_by_tm = index_by_tm(edr)
    papyri_by_tm = index_by_tm(papyri)
    isicily_by_tm = index_by_tm(isicily)

    shared_tm = sorted(set(edh_by_tm) & set(edr_by_tm))
    pairs = []
    for tm in shared_tm:
        # stage 1's overlap count assumed 1:1; guard against a tm id
        # mapping to more than one record in a source by taking the first
        # and recording how many times that happened.
        pairs.append((edh_by_tm[tm][0], edr_by_tm[tm][0]))

    multi_edh = sum(1 for tm in shared_tm if len(edh_by_tm[tm]) > 1)
    multi_edr = sum(1 for tm in shared_tm if len(edr_by_tm[tm]) > 1)

    if args.sample_out:
        write_sample(pairs, args.sample_size, args.sample_out)

    # Cross-source overlap flags (not merged).
    all_tm_sets = {
        "edh": set(edh_by_tm), "edr": set(edr_by_tm),
        "papyri": set(papyri_by_tm), "isicily": set(isicily_by_tm),
    }
    overlap_counts = {}
    names = list(all_tm_sets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if a == "edh" and b == "edr":
                continue  # handled by the merge itself
            overlap_counts[f"{a}_vs_{b}"] = len(all_tm_sets[a] & all_tm_sets[b])

    def overlap_flags(tm, own_source):
        others = []
        for name, s in all_tm_sets.items():
            if name != own_source and tm in s:
                others.append(name)
        return others

    merged_count = 0
    written = 0
    with open(args.output, "w", encoding="utf-8") as out:
        for edh_rec, edr_rec in pairs:
            m = merge_edh_edr_pair(edh_rec, edr_rec)
            tm = m["tm_id"]
            others = overlap_flags(tm, "edh")  # edh/edr already merged
            others = [o for o in others if o not in ("edh", "edr")]
            if others:
                m["cross_source_overlap"] = others
            out.write(json.dumps(m, ensure_ascii=False) + "\n")
            written += 1
            merged_count += 1

        edh_only = set(edh_by_tm) - set(shared_tm)
        edr_only = set(edr_by_tm) - set(shared_tm)
        for tm in sorted(edh_only):
            for rec in edh_by_tm[tm]:
                rec = dict(rec)
                rec["provenance"] = {"text": "edh", "date": "edh", "findspot": "edh", "ids": "edh_only"}
                others = overlap_flags(tm, "edh")
                if others:
                    rec["cross_source_overlap"] = others
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1
        for tm in sorted(edr_only):
            for rec in edr_by_tm[tm]:
                rec = dict(rec)
                rec["provenance"] = {"text": "edr", "date": "edr", "findspot": "edr", "ids": "edr_only"}
                others = overlap_flags(tm, "edr")
                if others:
                    rec["cross_source_overlap"] = others
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1
        # Records with no tm_id at all in EDH/EDR cannot be deduplicated;
        # pass them through unchanged with a null-provenance note.
        for rec in edh:
            if rec.get("tm_id") is None:
                rec = dict(rec)
                rec["provenance"] = {"text": "edh", "date": "edh", "findspot": "edh", "ids": "edh_only_no_tm"}
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1
        for rec in edr:
            if rec.get("tm_id") is None:
                rec = dict(rec)
                rec["provenance"] = {"text": "edr", "date": "edr", "findspot": "edr", "ids": "edr_only_no_tm"}
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1

        for rec in papyri:
            rec = dict(rec)
            tm = rec.get("tm_id")
            if tm is not None:
                others = overlap_flags(tm, "papyri")
                if others:
                    rec["cross_source_overlap"] = others
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1
        for rec in isicily:
            rec = dict(rec)
            tm = rec.get("tm_id")
            if tm is not None:
                others = overlap_flags(tm, "isicily")
                if others:
                    rec["cross_source_overlap"] = others
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1

    summary = {
        "edh_total": len(edh),
        "edr_total": len(edr),
        "papyri_total": len(papyri),
        "isicily_total": len(isicily),
        "shared_tm_ids": len(shared_tm),
        "edh_tm_with_multiple_records": multi_edh,
        "edr_tm_with_multiple_records": multi_edr,
        "merged_records": merged_count,
        "total_written": written,
        "cross_source_overlap_counts": overlap_counts,
        "text_pick_counts": {
            "edh": sum(1 for p in pairs if pick_text_source(*p) == "edh"),
            "edr": sum(1 for p in pairs if pick_text_source(*p) == "edr"),
        },
        "date_pick_counts": {
            "edh": sum(1 for p in pairs if pick_date_source(*p) == "edh"),
            "edr": sum(1 for p in pairs if pick_date_source(*p) == "edr"),
        },
        "place_pick_counts": {
            "edh": sum(1 for p in pairs if pick_place_source(*p) == "edh"),
            "edr": sum(1 for p in pairs if pick_place_source(*p) == "edr"),
        },
    }
    print(json.dumps(summary, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
