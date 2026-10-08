#!/usr/bin/env python3
"""Prototype the file layout for indexing the documentary corpus, and
count it across the full deduplicated corpus. Does NOT build the index
or touch backend/ beyond reading its own tagged-line format for
comparison (process_file's own `^<([^>]+)>\\s*(.+)$` line regex).

Design (see DOCUMENTS_STAGE2_NOTES.md / DOCUMENTS_STAGE2_REPORT.md for
the evidence behind the threshold):

- A document with at most SHORT_LINE_THRESHOLD (default 10) transcribed
  lines is "short". Short documents are packed one-document-per-index-line
  into a collection file grouped by (source, region): one physical .tess
  line per document, its citation tag naming the document (not a line
  within it), its text the document's lines joined with " / " so a
  multi-line epitaph still reads as one unit. This matches how documents
  are normally cited in scholarship (by inventory number, not by line),
  and keeps the huge share of five-and-ten-word inscriptions from
  producing one tiny file each.
- A document with MORE than SHORT_LINE_THRESHOLD lines is "long" (a
  minority overall, but 37.2% of papyri.info specifically: see the
  per-source line-count distribution in the notes). A long document gets
  its own file, one physical .tess line per transcribed line, exactly
  like an existing literary .tess file (citation tag names document AND
  line).
- Region grouping: `findspot.region`, slugified (lowercase, spaces and
  punctuation to underscores); records with no region go to an
  `unknown_region` bucket per source. EDH/EDR merged records use the
  merge's chosen findspot (see step 1); papyri.info and I.Sicily use
  their own.

Citation tags: `<source.local_id>` for a short document (e.g.
`<edh.HD033000>`), `<merged.tm<tm_id>>` for an EDH/EDR merged record;
`<source.local_id.line_n>` for a long document's line (e.g.
`<papyri.219272b.7>`). local_id is edh_id/edr_id/local papyri or isicily
id, whichever the record actually carries (merged records may carry
both edh_id and edr_id, so merged ids use the tm_id instead, which is
always present and always unique per merged record).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

SHORT_LINE_THRESHOLD = 10

TESS_LINE_RE = re.compile(r'^<([^>]+)>\s*(.+)$')


def slugify(s: str) -> str:
    if not s:
        return "unknown_region"
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "unknown_region"


def local_id(rec: dict) -> str:
    source = rec.get("source", "")
    if source == "edh+edr":
        return f"tm{rec.get('tm_id')}"
    if source == "edh":
        return rec.get("edh_id") or f"tm{rec.get('tm_id')}"
    if source == "edr":
        return rec.get("edr_id") or f"tm{rec.get('tm_id')}"
    # papyri, isicily: use the record's own id, minus its "source:" prefix.
    rid = rec.get("id") or ""
    if ":" in rid:
        return rid.split(":", 1)[1]
    return rid


def tag_prefix(rec: dict) -> str:
    source = rec.get("source", "")
    return "merged" if source == "edh+edr" else source


def classify(rec: dict) -> str:
    n_lines = len(rec.get("lines") or [])
    return "long" if n_lines > SHORT_LINE_THRESHOLD else "short"


def region_of(rec: dict) -> str:
    fs = rec.get("findspot") or {}
    return slugify(fs.get("region"))


WHITESPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Collapse any whitespace run (including a literal newline or tab)
    to one space. Needed because 7,751 of 257,428 merged-corpus
    documents (3.0%; 6,490 of them papyri.info, 1,028 EDR, 118 merged
    EDH/EDR, 115 I.Sicily, ZERO EDH) carry a raw newline+tab sequence
    inside a line's own `text` field: a stage 1 `epidoc_convert.py` bug
    (its default "transparent container" branch copies an XML element's
    `tail` text verbatim, including the source file's own pretty-printed
    indentation whitespace, when that tail happens to span a line break
    in the RAW XML). One `.tess` line must be one physical line; this
    collapse is the fix for this script's OWN output. The upstream bug
    in epidoc_convert.py is not fixed here (out of this step's scope,
    and stage 1 already merged as PR #668); see the report."""
    return WHITESPACE_RE.sub(" ", text).strip()


def short_doc_tess_line(rec: dict) -> str:
    tag = f"{tag_prefix(rec)}.{local_id(rec)}"
    lines = rec.get("lines") or []
    text = " / ".join(clean_text(ln.get("text", "")) for ln in lines if ln.get("text"))
    if not text:
        text = clean_text(rec.get("text") or "")
    return f"<{tag}>\t{text}"


def long_doc_tess_lines(rec: dict) -> list[str]:
    tag_base = f"{tag_prefix(rec)}.{local_id(rec)}"
    out = []
    for i, ln in enumerate(rec.get("lines") or [], start=1):
        text = clean_text(ln.get("text", ""))
        if not text:
            continue
        out.append(f"<{tag_base}.{i}>\t{text}")
    return out


def iter_records(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def count_full_corpus(path: str):
    short_by_bucket = Counter()      # (source, region) -> doc count
    long_docs = Counter()            # source -> doc count
    long_lines = Counter()           # source -> total line count
    total_short_lines_as_index_lines = Counter()  # source -> short docs (1 index line each)

    for rec in iter_records(path):
        source = tag_prefix(rec)
        cls = classify(rec)
        if cls == "short":
            bucket = (source, region_of(rec))
            short_by_bucket[bucket] += 1
            total_short_lines_as_index_lines[source] += 1
        else:
            long_docs[source] += 1
            long_lines[source] += len(rec.get("lines") or [])

    n_short_files = len(short_by_bucket)
    n_long_files = sum(long_docs.values())
    n_short_index_lines = sum(short_by_bucket.values())
    n_long_index_lines = sum(long_lines.values())

    return {
        "short_line_threshold": SHORT_LINE_THRESHOLD,
        "short_files_by_source_region": {
            f"{s}/{r}": c for (s, r), c in sorted(short_by_bucket.items())
        },
        "n_short_collection_files": n_short_files,
        "n_short_docs_total": n_short_index_lines,
        "long_docs_by_source": dict(long_docs),
        "long_lines_by_source": dict(long_lines),
        "n_long_files": n_long_files,
        "n_long_index_lines": n_long_index_lines,
        "total_files": n_short_files + n_long_files,
        "total_index_lines": n_short_index_lines + n_long_index_lines,
    }


def write_sample(path: str, out_dir: str, sample_limit: int):
    """Actually write the proposed layout for a bounded sample of
    records (not the whole corpus), and validate every written line
    against the exact regex backend/text_processor.py's process_file
    uses to read an existing .tess file."""
    os.makedirs(out_dir, exist_ok=True)
    short_buckets: dict[tuple, list[str]] = defaultdict(list)
    long_files_written = 0
    long_lines_written = 0
    checked = 0
    regex_failures = []

    for i, rec in enumerate(iter_records(path)):
        if i >= sample_limit:
            break
        checked += 1
        if classify(rec) == "short":
            line = short_doc_tess_line(rec)
            short_buckets[(tag_prefix(rec), region_of(rec))].append(line)
            if not TESS_LINE_RE.match(line):
                regex_failures.append(line[:120])
        else:
            lines = long_doc_tess_lines(rec)
            if not lines:
                continue
            source_dir = os.path.join(out_dir, tag_prefix(rec), "long")
            os.makedirs(source_dir, exist_ok=True)
            fname = f"{local_id(rec)}.tess"
            fpath = os.path.join(source_dir, fname)
            with open(fpath, "w", encoding="utf-8") as f:
                for ln in lines:
                    f.write(ln + "\n")
                    if not TESS_LINE_RE.match(ln):
                        regex_failures.append(ln[:120])
            long_files_written += 1
            long_lines_written += len(lines)

    for (source, region), lines in short_buckets.items():
        source_dir = os.path.join(out_dir, source, "short")
        os.makedirs(source_dir, exist_ok=True)
        fpath = os.path.join(source_dir, f"{region}.tess")
        with open(fpath, "w", encoding="utf-8") as f:
            for ln in lines:
                f.write(ln + "\n")

    return {
        "sample_records_checked": checked,
        "short_collection_files_written": len(short_buckets),
        "short_docs_written": sum(len(v) for v in short_buckets.values()),
        "long_files_written": long_files_written,
        "long_lines_written": long_lines_written,
        "regex_failures": regex_failures,
        "all_lines_matched_tess_regex": len(regex_failures) == 0,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="merged corpus JSONL")
    ap.add_argument("--sample-out-dir", required=True)
    ap.add_argument("--sample-limit", type=int, default=3000)
    ap.add_argument("--output", required=True, help="summary JSON path")
    args = ap.parse_args(argv)

    sample_result = write_sample(args.input, args.sample_out_dir, args.sample_limit)
    full_result = count_full_corpus(args.input)

    result = {"sample": sample_result, "full_corpus": full_result}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(json.dumps(result, indent=2, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
