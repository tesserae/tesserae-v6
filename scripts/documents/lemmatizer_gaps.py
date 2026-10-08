#!/usr/bin/env python3
"""Lemmatizer gaps on the documentary corpus: Roman numerals, personal
names, and gap/fragment tokens (stage 1 found these as the three
recurring kinds of unlemmatized token; see
research/historians/DOCUMENTS_STAGE1_REPORT.md).

(a) Roman numerals (sequences of I, V, X, L, C, D, M, case-insensitive,
    with the classical V/U interchange) are classified as numerals,
    independent of whether they are also in the dictionary lookup table.
    Epigraphic numerals are often irregular (IIII for 4, XXXX for 40:
    both appear in stage 1's own examples), so this does NOT enforce
    well-formed subtractive notation, only the character set.
(b) Personal names: a candidate name list built from the corpus itself
    by finding word forms that are capitalized in nearly all of their
    occurrences (the editorially expanded `text` field does distinguish
    case: ordinary words are lowercase, proper names are capitalized,
    confirmed by inspection, e.g. "Lucius Satrienus Cai filius" keeps
    "filius" lowercase next to three capitalized names). This only
    MEASURES how many otherwise-unresolved tokens the list would cover;
    it does not lemmatize a name to anything (there is no sensible lemma
    for "Cnaeo" beyond itself), consistent with the spec asking only for
    the measurement at this stage.
(c) Fragments from step 2 (scripts/documents/restoration_tokens.py): a
    token broken by a gap cannot be lemmatized by definition (half a
    word has no dictionary entry), so it is excluded from the unresolved
    tally rather than counted as a lemmatizer failure.

IMPORTANT finding this script's "before" pass depends on, recorded here
and in the notes: text_processor.tokenize_latin/tokenize_greek strip any
character outside their letter set WITHOUT inserting a space, so feeding
a line's `text` (which still has the gap placeholder character embedded,
e.g. "XXV█stipendiorum") through the existing tokenizer SILENTLY
GLUES the two sides of the gap into one garbled token ("xxustipendiorum"
after the v/u Latin normalization), rather than keeping them separate.
The "before" pass below reproduces that exact (flawed) behavior on
purpose, because that is what stage 1 measured and what a reader needs
compared against. The "after" pass instead tokenizes with
`restoration_tokens.tokenize_with_restoration` FIRST (whitespace- and
gap-aware) and lemmatizes each surviving token directly
(`_latin_lemmatize`/`_greek_lemmatize` on a one-token list), which is the
correct order for any real pipeline and is the fix this script
recommends (see DOCUMENTS_STAGE2_REPORT.md).

Does not touch backend/ or /var/www. Imports backend.text_processor
read-only, the same functions the live search index uses, exactly as
stage 1 did.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.documents.restoration_tokens import tokenize_with_restoration, GAP_PLACEHOLDER

NUMERAL_CHARS_IV = set("ivxlcdm")
NUMERAL_CHARS_UV = set("iuxlcdm")  # v normalized to u, as text_processor does


def is_roman_numeral(token: str) -> bool:
    """True if `token` is composed entirely of Roman numeral letters
    (I V X L C D M), case-insensitive, allowing either spelling of the
    fifth letter (V or its classical/normalized form U). Empty strings
    and single ambiguous letters that are also common short words are
    NOT special-cased here; this function is only ever applied to tokens
    that already failed ordinary dictionary lookup (see `classify_token`),
    so a real short word like "id" never reaches it."""
    if not token:
        return False
    low = token.lower()
    return set(low) <= NUMERAL_CHARS_IV or set(low) <= NUMERAL_CHARS_UV


def iter_records(path, limit=None):
    n = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if limit is not None and n >= limit:
                return
            yield json.loads(line)
            n += 1


WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)


def build_name_candidates(paths, min_count=3, min_capitalized_share=0.9, sample_limit=None):
    """Scan the corpus's own `text` field (original case preserved) for
    word forms capitalized in nearly all of their occurrences. Returns a
    dict: lowercased form -> {"count": int, "capitalized_share": float}.
    """
    total = Counter()
    capitalized = Counter()
    for path in paths:
        for rec in iter_records(path, limit=sample_limit):
            text = rec.get("text") or ""
            if not text:
                continue
            for m in WORD_RE.finditer(text):
                w = m.group(0)
                if GAP_PLACEHOLDER in w or len(w) < 2:
                    continue
                low = w.lower()
                total[low] += 1
                if w[0].isupper():
                    capitalized[low] += 1

    candidates = {}
    for low, count in total.items():
        if count < min_count:
            continue
        share = capitalized[low] / count
        if share >= min_capitalized_share:
            candidates[low] = {"count": count, "capitalized_share": round(share, 4)}
    return candidates


def classify_token_before(tp, language, token, latin_table=None, greek_table=None):
    """Replicate stage 1's "before" unresolved test on ONE already
    lemmatizer-tokenized token: absent from the primary lookup table
    (after the lemmatizer's own enclitic-stripping/normalization) AND
    the lemmatizer's own returned lemma equals the normalized surface
    form (no lookup hit, no fallback model diverged from it)."""
    if language == "la":
        norm = token.lower().replace("j", "i").replace("v", "u")
        lemma = tp._latin_lemmatize([token])[0]
        in_table = norm in latin_table
        unresolved = (not in_table) and (lemma == norm)
    else:
        norm = tp._normalize_greek_token(token.lower())
        lemma = tp._greek_lemmatize([token])[0]
        in_table = norm in greek_table
        unresolved = (not in_table) and (lemma == norm)
    return unresolved


def run_before(tp, latin_table, greek_table, docs, language):
    """Naive pipeline: text_processor's own tokenize_* on the raw line
    text (gap placeholder silently glued into neighboring letters, see
    module docstring), then lemmatize, then test unresolved."""
    total_tokens = 0
    unresolved = 0
    for rec in docs:
        for ln in rec.get("lines", []):
            text = ln.get("text", "")
            if not text:
                continue
            if language == "la":
                _, tokens = tp.tokenize_latin(text, preserve_case=True)
            else:
                _, tokens = tp.tokenize_greek(text, preserve_case=True)
            for tok in tokens:
                total_tokens += 1
                if classify_token_before(tp, language, tok, latin_table, greek_table):
                    unresolved += 1
    return total_tokens, unresolved


def run_after(tp, latin_table, greek_table, docs, language, name_candidates):
    """Fixed pipeline: gap-aware whitespace tokenization first
    (restoration_tokens), fragments excluded from the unresolved tally,
    numerals classified and excluded, remaining unresolved tokens checked
    against the name-candidate list (coverage only, not a fix)."""
    total_tokens = 0
    unresolved = 0
    fragments_excluded = 0
    numerals_excluded = 0
    name_covered = 0
    for rec in docs:
        for ln in rec.get("lines", []):
            text = ln.get("text", "")
            flags = ln.get("restored_flags", [])
            if not text:
                continue
            for tok in tokenize_with_restoration(text, flags):
                if tok.fragment:
                    fragments_excluded += 1
                    continue
                total_tokens += 1
                if is_roman_numeral(tok.text):
                    numerals_excluded += 1
                    continue
                if classify_token_before(tp, language, tok.text, latin_table, greek_table):
                    unresolved += 1
                    if tok.text.lower() in name_candidates:
                        name_covered += 1
    return {
        "total_tokens": total_tokens,
        "unresolved": unresolved,
        "fragments_excluded": fragments_excluded,
        "numerals_excluded": numerals_excluded,
        "name_covered_of_remaining_unresolved": name_covered,
    }


def sample_docs(path, n, seed):
    docs = list(iter_records(path))
    rng = random.Random(seed)
    return rng.sample(docs, min(n, len(docs)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--edh", required=True)
    ap.add_argument("--edr", required=True)
    ap.add_argument("--papyri", required=True)
    ap.add_argument("--isicily", required=True)
    ap.add_argument("--sample-size", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20261007)
    ap.add_argument("--name-list-out", default=None)
    ap.add_argument("--output", required=True)
    args = ap.parse_args(argv)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from backend.text_processor import TextProcessor, get_latin_lemma_table, get_greek_lemma_table

    sources = {
        "edh": (args.edh, "la"),
        "edr": (args.edr, "la"),
        "papyri": (args.papyri, "grc"),
        "isicily": (args.isicily, "la"),
    }
    # papyri.info mixes la/grc; sample by the document's declared primary
    # language (languages[0]) rather than a fixed guess, recorded in the
    # per-source language breakdown below.

    tp = TextProcessor()
    tp._ensure_models_loaded()
    latin_table = get_latin_lemma_table()
    greek_table = get_greek_lemma_table()

    name_candidates = build_name_candidates(
        [args.edh, args.edr, args.papyri, args.isicily])
    if args.name_list_out:
        with open(args.name_list_out, "w", encoding="utf-8") as f:
            f.write("form\tcount\tcapitalized_share\n")
            for form, stats in sorted(name_candidates.items(),
                                       key=lambda kv: -kv[1]["count"]):
                f.write(f"{form}\t{stats['count']}\t{stats['capitalized_share']}\n")

    results = {"name_candidates_total": len(name_candidates)}
    for label, (path, default_lang) in sources.items():
        docs = sample_docs(path, args.sample_size, seed=hash((args.seed, label)) & 0xffffffff)
        by_lang = {}
        for rec in docs:
            langs = rec.get("languages") or [default_lang]
            lang = langs[0].split(",")[0].split("-")[0]
            if lang not in ("la", "grc"):
                lang = default_lang
            by_lang.setdefault(lang, []).append(rec)

        label_result = {}
        for lang, lang_docs in by_lang.items():
            total_before, unresolved_before = run_before(
                tp, latin_table, greek_table, lang_docs, lang)
            after = run_after(tp, latin_table, greek_table, lang_docs, lang, name_candidates)
            label_result[lang] = {
                "documents": len(lang_docs),
                "before": {
                    "tokens": total_before,
                    "unresolved": unresolved_before,
                    "unresolved_share": round(unresolved_before / total_before, 4) if total_before else None,
                },
                "after": {
                    **after,
                    "unresolved_share": round(after["unresolved"] / after["total_tokens"], 4) if after["total_tokens"] else None,
                },
            }
        results[label] = label_result

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(json.dumps(results, indent=2, ensure_ascii=False), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
