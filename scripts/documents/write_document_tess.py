#!/usr/bin/env python3
"""Stage 3b-1: write packed .tess files, plus restored-word sidecars, for
the documentary corpus, from the stage 2 merged corpus.

Reuses `index_layout.py`'s bucketing (slugify, tag_prefix, classify,
region_of, century_of, find_oversized_short_buckets, short_bucket_key,
short_bucket_filename, clean_text) and `restoration_tokens.py`'s
`tokenize_with_restoration` for restored/fragment/gap handling, so neither
module's own rules are reimplemented here.

Design (owner-approved 2026-10-07/08, the stage 3b-1 spec's main-session
architecture decisions):

- PACKED files: every document, short or long, lands in its own
  source/region[/century] bucket .tess file (about 200 files total, not
  one file per long document the way the stage 2 prototype counted it).
  Bucket routing is `index_layout.short_bucket_key`, applied to every
  document regardless of its short/long classification (the function
  only looks at source/region/date, never line count).
- Citation tag is the document's own merged-corpus `id` field, already
  "source:local_id" (e.g. "edh:HD067781", "papyri:290109",
  "merged:<tm_id>") -- the same id `metadata.db`'s `documents.id` column
  carries, so a query can join the two directly without reformatting
  either side:
    - short document (<= SHORT_LINE_THRESHOLD lines): one .tess line,
      ref "<ID>".
    - long document: one .tess line per edition line, ref "<ID LINE>".
      LINE is the line's 1-based POSITION in the record's own `lines`
      array, not its own "n" field: 44% of long documents (measured
      directly against the full merged corpus before choosing this)
      repeat "n" values across columns or bilingual text, which would
      collide as a duplicate tag within one packed file; position is
      always unique. `scripts/corpus/validate_tess.py`'s own monotonic-
      ref check reads the SAME convention existing literary .tess files
      use ("<work locus>", the trailing space-separated token is the
      numeric part): confirmed against that script's `ref_key` before
      choosing the "<ID LINE>" (space, not dot) form.
- Text is the restored (expanded) reading (`lines[].text`, confirmed
  against sample records to equal `expanded`). A token made entirely of
  the gap placeholder is dropped from the matching text (kept only as a
  count); a token that MIXES the placeholder with real characters is
  split at the gap into its surviving pieces (restoration_tokens' own
  "fragment" pieces), which ARE kept in the matching text -- they are
  real transcribed characters, just partial. Restored-word and fragment
  positions (0-based, in the FINAL written token stream) go to a sidecar
  JSONL, one record per written .tess line, for later highlighting or
  exclusion; they are never written into the .tess text itself.
- A short document's several source lines are joined with a literal "/"
  token (matching how such documents are normally cited, by inventory
  number not by internal line) when reconstructing its one packed line;
  the "/" is itself never counted restored or fragment.
- A document whose every line is empty after gap-dropping (nothing left
  to match on) is skipped and counted, not written as an empty .tess
  line (`validate_tess.py`'s own empty-text check would fail it).
- Only documents whose own `languages` field is exactly `["la"]` or
  exactly `["grc"]` are written (98.5% of the corpus, measured directly:
  179,495 + 74,102 of 257,428). Bilingual ("la,grc", 632 documents, one
  comma-joined list entry per stage 2's own known data quirk -- never
  split into two `languages` entries), Coptic, and the smaller
  script-variant codes are out of scope for this stage (a separate
  Coptic/other-language documents index is not requested here) and are
  counted, not silently dropped.

Outputs, under --output-root (default ~/tesserae-docs/stage3/texts_documents):
  <lang>/<source>/<bucket>.tess
  <lang>/<source>/<bucket>.restored_words.jsonl
      one JSON object per written .tess line, same order as the .tess
      file: {"ref": "...", "restored": [idx, ...], "fragment": [idx, ...]}

`build_documents_index.py` derives its own doc_meta table (doc_id ->
bucket file, first_ref, last_ref) later, straight from the built index's
own `lines` table, so no separate manifest is written here.

Does not touch the search index, backend/, or /var/www. Offline, reads
the stage 2 merged corpus JSONL only; writes under --output-root only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from index_layout import (  # noqa: E402
    TESS_LINE_RE,
    classify,
    clean_text,
    find_oversized_short_buckets,
    iter_records,
    local_id,
    region_of,
    short_bucket_filename,
    short_bucket_key,
    tag_prefix,
)
from restoration_tokens import GAP_PLACEHOLDER, tokenize_with_restoration  # noqa: E402


def assign_language(rec: dict) -> str | None:
    """'la' or 'grc' for a document whose `languages` field is exactly
    that one language; None (skip) for anything else (bilingual,
    Coptic, script-variant codes, empty, etc.) -- see module docstring."""
    langs = tuple(sorted(set(rec.get("languages") or [])))
    if langs == ("la",):
        return "la"
    if langs == ("grc",):
        return "grc"
    return None


def doc_id_of(rec: dict) -> str:
    """The document's own citation id, already "source:local_id" in the
    merged corpus's own `id` field (confirmed directly against sample
    records: "edh:HD067781", "papyri:290109", "merged:122862", etc.)."""
    return rec.get("id") or f"{tag_prefix(rec)}:{local_id(rec)}"


def _line_tokens(text: str, flags: list):
    """Tokenize one source line with restoration awareness; returns
    (surviving_token_texts, restored_indices, fragment_indices,
    gap_chars_dropped) where the indices are positions within
    surviving_token_texts."""
    gap_chars_dropped = text.count(GAP_PLACEHOLDER)
    toks = tokenize_with_restoration(text, flags)
    texts = []
    restored = []
    fragment = []
    for tok in toks:
        if tok.restored:
            restored.append(len(texts))
        if tok.fragment:
            fragment.append(len(texts))
        texts.append(tok.text)
    return texts, restored, fragment, gap_chars_dropped


def build_short_doc_unit(rec: dict):
    """Return (text, restored_idx, fragment_idx, gap_chars_dropped) for a
    short document's single packed .tess line, or (None, [], [], N) if
    every line was empty after gap-dropping (caller skips it)."""
    final_tokens: list[str] = []
    restored_idx: list[int] = []
    fragment_idx: list[int] = []
    gap_chars_dropped = 0
    wrote_any_line = False
    for ln in rec.get("lines") or []:
        text = ln.get("text") or ""
        if not text:
            continue
        flags = ln.get("restored_flags") or [False] * len(text)
        texts, restored, fragment, gaps = _line_tokens(text, flags)
        gap_chars_dropped += gaps
        if not texts:
            continue
        if wrote_any_line:
            final_tokens.append("/")
        offset = len(final_tokens)
        for i in restored:
            restored_idx.append(offset + i)
        for i in fragment:
            fragment_idx.append(offset + i)
        final_tokens.extend(texts)
        wrote_any_line = True
    if not final_tokens:
        return None, [], [], gap_chars_dropped
    text_out = clean_text(" ".join(final_tokens))
    if not text_out:
        return None, [], [], gap_chars_dropped
    return text_out, restored_idx, fragment_idx, gap_chars_dropped


def build_long_doc_lines(rec: dict):
    """Return (list of (line_no, text, restored_idx, fragment_idx),
    gap_chars_dropped) for a long document, one entry per surviving
    (non-empty-after-gap-dropping) source line. line_no is the line's
    1-based position in rec['lines'], not its own 'n' field (see module
    docstring: 'n' collides across columns/bilingual text in 44% of
    long documents, measured directly)."""
    out = []
    gap_chars_dropped = 0
    for i, ln in enumerate(rec.get("lines") or [], start=1):
        text = ln.get("text") or ""
        if not text:
            continue
        flags = ln.get("restored_flags") or [False] * len(text)
        texts, restored, fragment, gaps = _line_tokens(text, flags)
        gap_chars_dropped += gaps
        if not texts:
            continue
        line_text = clean_text(" ".join(texts))
        if not line_text:
            continue
        out.append((i, line_text, restored, fragment))
    return out, gap_chars_dropped


class BucketWriter:
    """Holds open file handles for every (lang, source, bucket_filename)
    seen so far, so the whole corpus can be streamed through in one pass
    without buffering document text in memory. Call `close_all()` when
    done."""

    def __init__(self, output_root: str):
        self.output_root = output_root
        self._tess = {}
        self._sidecar = {}
        self.bucket_dirs_made = set()

    def _paths(self, lang: str, source: str, bucket_filename: str):
        # Flat per-language directory (texts_documents/<lang>/<name>.tess,
        # no source subdirectory): `build_inverted_index.get_text_files()`
        # lists a language directory with a plain, non-recursive
        # `os.listdir`, so a nested source/ level would silently vanish
        # from every build. The source still has to disambiguate the
        # filename (two sources can share a region slug, e.g. both edh and
        # edr have a "dalmatia" bucket), so it goes into the basename
        # instead: "<source>__<bucket>.tess".
        d = os.path.join(self.output_root, lang)
        name = f"{source}__{bucket_filename}"
        return (
            d,
            os.path.join(d, f"{name}.tess"),
            os.path.join(d, f"{name}.restored_words.jsonl"),
        )

    def handles_for(self, lang: str, source: str, bucket_filename: str):
        key = (lang, source, bucket_filename)
        if key not in self._tess:
            d, tess_path, sidecar_path = self._paths(lang, source, bucket_filename)
            if d not in self.bucket_dirs_made:
                os.makedirs(d, exist_ok=True)
                self.bucket_dirs_made.add(d)
            # "w": each bucket's handle is opened exactly once per run (cached
            # above) and kept open for the whole pass, so this always starts
            # the file fresh rather than risking a duplicate append onto
            # stale content from an earlier run.
            self._tess[key] = open(tess_path, "w", encoding="utf-8")  # noqa: SIM115
            self._sidecar[key] = open(sidecar_path, "w", encoding="utf-8")  # noqa: SIM115
        return self._tess[key], self._sidecar[key]

    def close_all(self):
        for f in self._tess.values():
            f.close()
        for f in self._sidecar.values():
            f.close()


def process_corpus(input_path: str, output_root: str, limit: int | None = None):
    """One streaming pass (two sub-passes: bucket-sizing, then writing).
    Returns a summary dict. Overwrites any existing output under
    output_root for the buckets it touches (callers wanting a clean
    build should pass a fresh/empty output_root)."""
    t0 = time.time()
    oversized = find_oversized_short_buckets(input_path)

    writer = BucketWriter(output_root)
    stats = {
        "by_lang": {"la": Counter(), "grc": Counter()},
        "skipped_other_language": Counter(),
        "empty_skipped": Counter(),
        "regex_failures": [],
        "gap_chars_dropped": Counter(),
        "oversized_buckets": sorted(f"{s}/{r}" for s, r in oversized),
    }

    n_read = 0
    try:
        for rec in iter_records(input_path):
            if limit is not None and n_read >= limit:
                break
            n_read += 1

            lang = assign_language(rec)
            if lang is None:
                langs = tuple(sorted(set(rec.get("languages") or [])))
                stats["skipped_other_language"][langs] += 1
                continue

            did = doc_id_of(rec)
            source = tag_prefix(rec)
            bucket = short_bucket_key(rec, oversized)
            bucket_filename = short_bucket_filename(bucket)
            tess_f, sidecar_f = writer.handles_for(lang, source, bucket_filename)

            if classify(rec) == "short":
                text, restored_idx, fragment_idx, gaps = build_short_doc_unit(rec)
                stats["gap_chars_dropped"][lang] += gaps
                if text is None:
                    stats["empty_skipped"][lang] += 1
                    continue
                ref = did
                line = f"<{ref}>\t{text}"
                if not TESS_LINE_RE.match(line):
                    stats["regex_failures"].append(line[:160])
                    continue
                tess_f.write(line + "\n")
                sidecar_f.write(json.dumps(
                    {"ref": ref, "restored": restored_idx, "fragment": fragment_idx},
                    ensure_ascii=False) + "\n")
                stats["by_lang"][lang]["documents"] += 1
                stats["by_lang"][lang]["tess_lines"] += 1
            else:
                doc_lines, gaps = build_long_doc_lines(rec)
                stats["gap_chars_dropped"][lang] += gaps
                if not doc_lines:
                    stats["empty_skipped"][lang] += 1
                    continue
                wrote_any = False
                for line_no, text, restored_idx, fragment_idx in doc_lines:
                    ref = f"{did} {line_no}"
                    line = f"<{ref}>\t{text}"
                    if not TESS_LINE_RE.match(line):
                        stats["regex_failures"].append(line[:160])
                        continue
                    tess_f.write(line + "\n")
                    sidecar_f.write(json.dumps(
                        {"ref": ref, "restored": restored_idx, "fragment": fragment_idx},
                        ensure_ascii=False) + "\n")
                    stats["by_lang"][lang]["tess_lines"] += 1
                    wrote_any = True
                if wrote_any:
                    stats["by_lang"][lang]["documents"] += 1
                else:
                    stats["empty_skipped"][lang] += 1
    finally:
        writer.close_all()

    stats["records_read"] = n_read
    stats["bucket_files_written"] = len(writer._tess)  # noqa: SLF001
    stats["elapsed_s"] = time.time() - t0
    # Counters aren't JSON-able directly in nested form; flatten for output.
    stats["by_lang"] = {k: dict(v) for k, v in stats["by_lang"].items()}
    stats["skipped_other_language"] = {
        (",".join(k) if k else "(none)"): v
        for k, v in stats["skipped_other_language"].items()
    }
    stats["empty_skipped"] = dict(stats["empty_skipped"])
    stats["gap_chars_dropped"] = dict(stats["gap_chars_dropped"])
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="stage 2 merged corpus JSONL")
    ap.add_argument("--output-root", default=os.path.expanduser(
        "~/tesserae-docs/stage3/texts_documents"))
    ap.add_argument("--limit", type=int, default=None,
                     help="process only the first N input records (pilot runs)")
    ap.add_argument("--summary-out", default=None, help="summary JSON path")
    ap.add_argument("--only-bucket", action="append", default=None,
                     help="restrict output to lang/source/bucket_filename "
                          "(repeatable); for a small, realistic pilot slice")
    args = ap.parse_args(argv)

    only = None
    if args.only_bucket:
        only = {tuple(b.split("/", 2)) for b in args.only_bucket}

    if only is None:
        result = process_corpus(args.input, args.output_root, limit=args.limit)
    else:
        # Filtered variant: same logic, but skip any document whose
        # (lang, source, bucket_filename) is not in `only`. Implemented by
        # wrapping process_corpus's per-record routing would duplicate the
        # function; instead do a direct filtered pass here, reusing the
        # same helpers, since --only-bucket is a dev/pilot convenience.
        t0 = time.time()
        oversized = find_oversized_short_buckets(args.input)
        writer = BucketWriter(args.output_root)
        stats = {"by_lang": {"la": Counter(), "grc": Counter()},
                  "skipped_other_language": Counter(), "empty_skipped": Counter(),
                  "regex_failures": [], "gap_chars_dropped": Counter(),
                  "oversized_buckets": sorted(f"{s}/{r}" for s, r in oversized)}
        n_read = 0
        try:
            for rec in iter_records(args.input):
                if args.limit is not None and n_read >= args.limit:
                    break
                n_read += 1
                lang = assign_language(rec)
                if lang is None:
                    continue
                source = tag_prefix(rec)
                bucket = short_bucket_key(rec, oversized)
                bucket_filename = short_bucket_filename(bucket)
                if (lang, source, bucket_filename) not in only:
                    continue
                did = doc_id_of(rec)
                tess_f, sidecar_f = writer.handles_for(lang, source, bucket_filename)
                if classify(rec) == "short":
                    text, restored_idx, fragment_idx, gaps = build_short_doc_unit(rec)
                    stats["gap_chars_dropped"][lang] += gaps
                    if text is None:
                        stats["empty_skipped"][lang] += 1
                        continue
                    ref = did
                    line = f"<{ref}>\t{text}"
                    if not TESS_LINE_RE.match(line):
                        stats["regex_failures"].append(line[:160])
                        continue
                    tess_f.write(line + "\n")
                    sidecar_f.write(json.dumps(
                        {"ref": ref, "restored": restored_idx, "fragment": fragment_idx},
                        ensure_ascii=False) + "\n")
                    stats["by_lang"][lang]["documents"] += 1
                    stats["by_lang"][lang]["tess_lines"] += 1
                else:
                    doc_lines, gaps = build_long_doc_lines(rec)
                    stats["gap_chars_dropped"][lang] += gaps
                    wrote_any = False
                    for line_no, text, restored_idx, fragment_idx in doc_lines:
                        ref = f"{did} {line_no}"
                        line = f"<{ref}>\t{text}"
                        if not TESS_LINE_RE.match(line):
                            stats["regex_failures"].append(line[:160])
                            continue
                        tess_f.write(line + "\n")
                        sidecar_f.write(json.dumps(
                            {"ref": ref, "restored": restored_idx, "fragment": fragment_idx},
                            ensure_ascii=False) + "\n")
                        stats["by_lang"][lang]["tess_lines"] += 1
                        wrote_any = True
                    if wrote_any:
                        stats["by_lang"][lang]["documents"] += 1
                    else:
                        stats["empty_skipped"][lang] += 1
        finally:
            writer.close_all()
        stats["records_read"] = n_read
        stats["elapsed_s"] = time.time() - t0
        stats["by_lang"] = {k: dict(v) for k, v in stats["by_lang"].items()}
        stats["skipped_other_language"] = dict(stats["skipped_other_language"])
        stats["empty_skipped"] = dict(stats["empty_skipped"])
        stats["gap_chars_dropped"] = dict(stats["gap_chars_dropped"])
        result = stats

    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as f:
            f.write(out)
    print(out, file=sys.stderr)
    return 0 if not result.get("regex_failures") else 1


if __name__ == "__main__":
    raise SystemExit(main())
