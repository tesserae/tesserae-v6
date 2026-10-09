#!/usr/bin/env python3
"""Map character-level restoration (restored_flags, from
scripts/documents/epidoc_convert.py) to word tokens, for a documentary
text's `text` + `restored_flags` pair.

Three things happen to the whitespace-split token stream:

1. A token made up ENTIRELY of the gap placeholder character(s) (one or
   more consecutive `GAP_PLACEHOLDER` characters, nothing else) is a
   lost-and-unguessed passage with no word in it at all. It is dropped
   from the returned token list, but its position is kept: each returned
   token carries a `gap_before` count (how many such all-gap tokens sat
   immediately before it in the original stream), so a position is never
   silently lost, it is just not treated as if it were a word.
2. A token that MIXES the gap placeholder with ordinary characters (e.g.
   "XXV█stipendiorum", a word broken in the middle by damage) is split
   at every gap-placeholder run into its surviving pieces. Each surviving
   piece is marked `fragment=True`: it touches a gap boundary and is a
   partial word, not a transcribed whole. The gap character itself is
   dropped the same way as case 1 (not kept as a token, position implied
   by the split).
3. Every surviving token (whether split out of a mixed token or never
   touched a gap) gets `restored`: True when more than half of its
   characters were supplied by an editor (`restored_flags` True), using
   the token's own character span. A token whose share is exactly 0.5 is
   NOT counted restored (the rule is "most", a strict majority).

A `fragment` token's `restored` flag is still computed and kept (a
fragment can itself be partly restored), but callers doing word-level
matching should exclude `fragment=True` tokens regardless of `restored`,
per the spec's "flag fragments ... so they can be excluded from matching."

This module does not change the matcher, the index, or anything under
backend/ or /var/www. It is used here only to measure how many tokens
fall into each class per source (see `main`), and is meant to be reused
by a later indexing step.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field

GAP_PLACEHOLDER = "█"


@dataclass
class Token:
    text: str
    restored: bool
    fragment: bool
    gap_before: int = 0
    restored_share: float = 0.0


def _char_spans(text: str):
    """Yield (start, end, substring) for each whitespace-delimited run in
    text, end exclusive."""
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        start = i
        while i < n and not text[i].isspace():
            i += 1
        yield start, i, text[start:i]


def _split_gap_run(run: str, start: int, flags: list[bool]):
    """Split one whitespace-delimited run into pieces at every maximal
    run of GAP_PLACEHOLDER characters. Returns a list of
    (piece_text, piece_flags, was_all_gap: bool, touched_gap: bool)."""
    pieces = []
    i = 0
    n = len(run)
    cur_start = 0
    while i < n:
        if run[i] == GAP_PLACEHOLDER:
            if i > cur_start:
                piece = run[cur_start:i]
                piece_flags = flags[cur_start:i]
                pieces.append((piece, piece_flags, False, True))
            j = i
            while j < n and run[j] == GAP_PLACEHOLDER:
                j += 1
            pieces.append((run[i:j], flags[i:j], True, True))
            cur_start = j
            i = j
        else:
            i += 1
    if cur_start < n:
        piece = run[cur_start:n]
        piece_flags = flags[cur_start:n]
        touched = any(p[2] is False and p[3] for p in pieces) or (cur_start > 0)
        pieces.append((piece, piece_flags, False, cur_start > 0))
    return pieces


def tokenize_with_restoration(text: str, restored_flags: list[bool]) -> list[Token]:
    """Whitespace-tokenize `text`, using `restored_flags` (one bool per
    character of `text`, True = supplied by an editor) to classify each
    surviving token. See module docstring for the gap/fragment rules."""
    if len(restored_flags) != len(text):
        # Defensive: never crash on a length mismatch, pad/truncate.
        if len(restored_flags) < len(text):
            restored_flags = restored_flags + [False] * (len(text) - len(restored_flags))
        else:
            restored_flags = restored_flags[: len(text)]

    tokens: list[Token] = []
    pending_gap_before = 0
    for start, end, run in _char_spans(text):
        run_flags = restored_flags[start:end]
        if run and all(c == GAP_PLACEHOLDER for c in run):
            # Whole run is gap placeholder(s): drop, remember count.
            pending_gap_before += len(run)
            continue
        if GAP_PLACEHOLDER not in run:
            supplied = sum(1 for f in run_flags if f)
            share = supplied / len(run) if run else 0.0
            tokens.append(Token(
                text=run, restored=share > 0.5, fragment=False,
                gap_before=pending_gap_before, restored_share=share,
            ))
            pending_gap_before = 0
            continue
        # Mixed run: split at gap boundaries.
        pieces = _split_gap_run(run, start, run_flags)
        first_piece_emitted = False
        for piece_text, piece_flags, is_all_gap, touched in pieces:
            if is_all_gap:
                pending_gap_before += len(piece_text)
                continue
            if not piece_text:
                continue
            supplied = sum(1 for f in piece_flags if f)
            share = supplied / len(piece_text) if piece_text else 0.0
            tokens.append(Token(
                text=piece_text, restored=share > 0.5, fragment=True,
                gap_before=pending_gap_before if not first_piece_emitted else 0,
                restored_share=share,
            ))
            pending_gap_before = 0
            first_piece_emitted = True
    return tokens


def classify_corpus(path: str) -> dict:
    """Run tokenize_with_restoration over every line of every document in
    a converted JSONL source file, and tally class counts."""
    counts = Counter()
    docs = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            docs += 1
            for ln in rec.get("lines", []):
                text = ln.get("text", "")
                flags = ln.get("restored_flags", [])
                if not text:
                    continue
                gap_tokens_dropped = text.count(GAP_PLACEHOLDER)
                counts["gap_placeholder_chars_dropped"] += gap_tokens_dropped
                for tok in tokenize_with_restoration(text, flags):
                    counts["tokens_total"] += 1
                    if tok.fragment:
                        counts["fragment"] += 1
                    elif tok.restored:
                        counts["restored_whole_word"] += 1
                    else:
                        counts["clean"] += 1
                    if tok.fragment and tok.restored:
                        counts["fragment_and_restored"] += 1
    counts["documents"] = docs
    return dict(counts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", action="append", required=True,
                     help="converted JSONL file; repeat for multiple sources")
    ap.add_argument("--label", action="append", required=True,
                     help="label for the matching --input, same order")
    ap.add_argument("--output", required=True, help="summary JSON path")
    args = ap.parse_args(argv)

    if len(args.input) != len(args.label):
        print("ERROR: --input and --label counts must match", file=sys.stderr)
        return 2

    results = {}
    for path, label in zip(args.input, args.label):
        results[label] = classify_corpus(path)

    overall = Counter()
    for r in results.values():
        for k, v in r.items():
            if k != "documents":
                overall[k] += v
    overall["documents"] = sum(r["documents"] for r in results.values())
    results["overall"] = dict(overall)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(json.dumps(results, indent=2, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
