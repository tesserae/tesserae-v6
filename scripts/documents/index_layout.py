#!/usr/bin/env python3
"""Prototype the file layout for indexing the documentary corpus, and
count it across the full deduplicated corpus. Does NOT build the index
or touch backend/ beyond reading its own tagged-line format for
comparison (process_file's own `^<([^>]+)>\\s*(.+)$` line regex).

Design (the evidence behind the threshold is the per-source line-count
distribution computed directly by this module's own full-corpus pass;
see the numbers printed by `count_full_corpus` and the per-source
percentiles discussed below):

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

# A short-document collection file over this many documents gets split
# further, by century of date_not_before (2026-10-08 review: the first
# full-corpus count put 39,249 documents in one file, edr/roma.tess,
# since EDR is weighted toward Italy and Rome specifically).
BUCKET_SPLIT_THRESHOLD = 10000

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


def century_of(date_not_before) -> str:
    """Century label for `date_not_before` (negative = BCE, matching the
    converted JSON's own convention): "undated" if null, else
    "<n>_ad"/"<n>_bc" where year 1-100 AD is the 1st century AD and
    year 1-100 BC (date_not_before -1 to -100) is the 1st century BC.
    Used only to split an oversized short-document collection file
    further; never changes which document counts as "short" vs "long"."""
    if date_not_before is None:
        return "undated"
    y = date_not_before
    if y > 0:
        return f"{(y - 1) // 100 + 1}_ad"
    if y < 0:
        return f"{(-y - 1) // 100 + 1}_bc"
    return "undated"


def find_oversized_short_buckets(path: str, threshold: int = BUCKET_SPLIT_THRESHOLD):
    """One streaming pass over the full corpus: which (source, region)
    short-document buckets would hold more than `threshold` documents.
    Returns a set of (source, region) tuples; callers then route those
    specific buckets' documents through `short_bucket_key` with
    century splitting instead of the plain (source, region) key."""
    counts = Counter()
    for rec in iter_records(path):
        if classify(rec) == "short":
            counts[(tag_prefix(rec), region_of(rec))] += 1
    return {bucket for bucket, n in counts.items() if n > threshold}


def short_bucket_key(rec: dict, oversized: set) -> tuple:
    """(source, region) normally; (source, region, century) when that
    (source, region) pair is in `oversized` (see
    `find_oversized_short_buckets`)."""
    source, region = tag_prefix(rec), region_of(rec)
    if (source, region) in oversized:
        return (source, region, century_of(rec.get("date_not_before")))
    return (source, region)


def short_bucket_filename(bucket: tuple) -> str:
    """bucket is (source, region) or (source, region, century); returns
    just the file's own basename (without the .tess extension), the
    source is the directory, not part of the filename."""
    if len(bucket) == 3:
        return f"{bucket[1]}__{bucket[2]}"
    return bucket[1]


WHITESPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Collapse any whitespace run (including a literal newline or tab)
    to one space. Originally added as a defensive fix for a bug found
    while prototyping this layout (an element's XML tail could leak raw
    newline/tab whitespace into a line's own `text` field, upstream in
    `epidoc_convert.py`): 7,751 of 257,428 merged-corpus documents
    (3.0%) were affected before that converter was fixed at the source
    (2026-10-08 review; it now normalizes whitespace itself, so this
    corpus no longer carries the bug at all). Kept here anyway as a
    second line of defense: one `.tess` line must always be one
    physical line, regardless of what upstream produces."""
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


def count_full_corpus(path: str, oversized: set = None):
    if oversized is None:
        oversized = find_oversized_short_buckets(path)
    short_by_bucket = Counter()      # (source, region[, century]) -> doc count
    long_docs = Counter()            # source -> doc count
    long_lines = Counter()           # source -> total line count

    for rec in iter_records(path):
        source = tag_prefix(rec)
        cls = classify(rec)
        if cls == "short":
            bucket = short_bucket_key(rec, oversized)
            short_by_bucket[bucket] += 1
        else:
            long_docs[source] += 1
            long_lines[source] += len(rec.get("lines") or [])

    n_short_files = len(short_by_bucket)
    n_long_files = sum(long_docs.values())
    n_short_index_lines = sum(short_by_bucket.values())
    n_long_index_lines = sum(long_lines.values())

    def bucket_label(bucket):
        if len(bucket) == 3:
            return f"{bucket[0]}/{bucket[1]}__{bucket[2]}"
        return f"{bucket[0]}/{bucket[1]}"

    return {
        "short_line_threshold": SHORT_LINE_THRESHOLD,
        "bucket_split_threshold": BUCKET_SPLIT_THRESHOLD,
        "oversized_buckets_split_by_century": sorted(
            f"{s}/{r}" for s, r in oversized),
        "short_files_by_bucket": {
            bucket_label(b): c for b, c in sorted(short_by_bucket.items())
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


def write_sample(path: str, out_dir: str, sample_limit: int, oversized: set = None):
    """Actually write the proposed layout for a bounded sample of
    records (not the whole corpus), and validate every written line
    against the exact regex backend/text_processor.py's process_file
    uses to read an existing .tess file. `oversized` (normally computed
    once over the FULL corpus by the caller, see `main`) decides which
    (source, region) buckets get split further by century; a sample
    this small would essentially never cross BUCKET_SPLIT_THRESHOLD on
    its own, so passing the full corpus's own oversized set is what
    makes the sample actually demonstrate the split."""
    if oversized is None:
        oversized = set()
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
            short_buckets[short_bucket_key(rec, oversized)].append(line)
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

    for bucket, lines in short_buckets.items():
        source = bucket[0]
        source_dir = os.path.join(out_dir, source, "short")
        os.makedirs(source_dir, exist_ok=True)
        fpath = os.path.join(source_dir, f"{short_bucket_filename(bucket)}.tess")
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


def validate_full_corpus_regex(path: str, oversized: set = None):
    """Generate every .tess line this layout would produce for the WHOLE
    corpus (not a sample) and check each one against TESS_LINE_RE,
    without writing any file to disk. Used to confirm the whitespace
    fix (epidoc_convert.py, 2026-10-08 review) actually holds over the
    full corpus, not just a 3,000-document sample."""
    if oversized is None:
        oversized = find_oversized_short_buckets(path)
    total_lines = 0
    failures = []
    for rec in iter_records(path):
        if classify(rec) == "short":
            line = short_doc_tess_line(rec)
            total_lines += 1
            if not TESS_LINE_RE.match(line):
                failures.append(line[:160])
        else:
            for line in long_doc_tess_lines(rec):
                total_lines += 1
                if not TESS_LINE_RE.match(line):
                    failures.append(line[:160])
    return {
        "total_lines_checked": total_lines,
        "regex_failures": failures,
        "all_lines_matched_tess_regex": len(failures) == 0,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="merged corpus JSONL")
    ap.add_argument("--sample-out-dir", required=True)
    ap.add_argument("--sample-limit", type=int, default=3000)
    ap.add_argument("--output", required=True, help="summary JSON path")
    ap.add_argument("--skip-full-validate", action="store_true",
                     help="skip the full-corpus regex check (it is run by "
                          "default; the whole corpus, not a sample)")
    args = ap.parse_args(argv)

    oversized = find_oversized_short_buckets(args.input)
    sample_result = write_sample(args.input, args.sample_out_dir, args.sample_limit, oversized)
    full_result = count_full_corpus(args.input, oversized)

    result = {"sample": sample_result, "full_corpus": full_result}
    if not args.skip_full_validate:
        result["full_corpus_regex_validation"] = validate_full_corpus_regex(args.input, oversized)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(json.dumps(result, indent=2, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
