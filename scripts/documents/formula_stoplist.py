#!/usr/bin/env python3
"""Formula stoplist candidates: document frequency of expanded words per
language across the deduplicated documentary corpus.

For each document, every language in its `languages` list is credited with
one occurrence per DISTINCT word in that document's text (document
frequency, not raw token count): a word that appears five times in one
epitaph counts once toward that word's document frequency. A document
tagged with more than one language (e.g. I.Sicily's Latin/Punic or
Greek/Oscan bilinguals) credits BOTH languages with its full word set,
because the converted record carries no per-line language tag to split on;
this over-attributes a handful of words to a second language and is
recorded as a known limitation, not hidden.

Tokenization: runs of Unicode letters (`[^\\W\\d_]+`, Unicode-aware),
lowercased. This drops the gap placeholder character, digits, and
punctuation automatically (none of those are letters), but does NOT
distinguish a real word from a Roman-numeral-as-letters token (XXV -> an
"xxv" token) or from a word fragment broken by a gap (step 2's problem);
both can and do show up in the top candidates, flagged separately
(`numeral_like`) so a reviewer is not misled into reading them as formula
vocabulary.

Writes a TSV, one row per (language, rank) in the top N by document
frequency, with example document ids, to --output. Does NOT finalize a
stoplist: this is explicitly a candidate list for the main session to
review (see module docstring in the spec).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict

TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# Spec-named obvious Latin formula words, plus the standard funerary/
# honorific/legal formula vocabulary confirmed in stage 1's own top-100
# frequency list and the sample texts seen while building this script.
LATIN_FORMULA = {
    "dis", "manibus", "vixit", "annis", "annos", "annorum", "hic", "situs",
    "sita", "siti", "est", "sunt", "filius", "filia", "filio", "filiae",
    "sacrum", "votum", "libens", "merito", "fecit", "fecerunt", "fecerat",
    "curavit", "curaverunt", "coeravit", "coeravere", "posuit", "posuerunt",
    "bene", "merenti", "merenti", "coniugi", "coniugo", "carissimo",
    "carissimae", "pius", "pia", "piissimo", "piissimae", "testamento",
    "heres", "heredes", "locus", "titulum", "memoriae", "mensibus",
    "diebus", "dies", "aug", "augusto", "imp", "leg", "cos", "tribunicia",
    "potestate", "pontifex", "maximus", "senatus", "consulto", "populus",
    "romanus", "vivus", "sibi", "suis", "parentibus", "coniuge", "uxori",
    "marito", "libertis", "libertabusque",
}

# Greek funerary/dating formula vocabulary (epitaph closing formulas,
# document dating formulas common in papyri).
GREEK_FORMULA = {
    "ετη", "ετων", "ετει", "ετους", "ζησας", "ζησασα", "χαιρε", "χρηστε",
    "χρηστη", "μνημης", "ενεκεν", "ετος", "βασιλευοντος", "ινδικτιωνος",
    "μηνος", "αγαθη", "τυχη", "θεοις", "καταχθονιοις",
}

# Function words: closed classes (conjunctions, prepositions, pronouns,
# articles, common forms of "to be"), not content vocabulary.
LATIN_FUNCTION = {
    "et", "in", "ad", "de", "ex", "cum", "ab", "a", "ut", "qui", "quae",
    "quod", "sed", "atque", "aut", "vel", "non", "se", "sibi", "sui",
    "is", "ea", "id", "haec", "hoc", "hunc", "hanc", "huius", "qua",
    "quibus", "quem", "per", "pro", "sub", "super", "inter", "apud",
    "ante", "post", "sine", "cui", "cuius", "eius", "eorum", "earum",
    "ille", "illa", "illud", "nam", "enim", "autem", "ergo", "quoque",
}
GREEK_FUNCTION = {
    "και", "καὶ", "δε", "του", "τησ", "τῆς", "των", "τῶν", "ο", "η", "το",
    "εισ", "εν", "επι", "προσ", "απο", "δια", "τω", "τον", "την", "τοισ",
    "ταισ", "τα", "τοι", "οι", "αι", "μεν", "γαρ", "αλλα", "ει", "η",
}

FORMULA_BY_LANG = {"la": LATIN_FORMULA, "grc": GREEK_FORMULA}
FUNCTION_BY_LANG = {"la": LATIN_FUNCTION, "grc": GREEK_FUNCTION}


def iter_records(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def tokenize(text: str) -> set:
    return {m.group(0).lower() for m in TOKEN_RE.finditer(text or "")}


def build_doc_frequencies(path: str):
    doc_freq = defaultdict(Counter)          # lang -> token -> doc count
    examples = defaultdict(lambda: defaultdict(list))  # lang -> token -> [doc ids]
    doc_count_by_lang = Counter()

    for rec in iter_records(path):
        langs = rec.get("languages") or []
        if not langs:
            continue
        text = rec.get("text") or ""
        if not text:
            continue
        words = tokenize(text)
        if not words:
            continue
        doc_id = rec.get("id")
        # EDH stores a handful of bilingual records as a single list entry
        # "la,grc" rather than two entries ["la", "grc"] (656 of 79,201 EDH
        # records, confirmed by grep against the converted source file);
        # split on comma so those documents are credited to both
        # languages' document counts instead of a spurious third bucket.
        norm_langs = []
        for lang in langs:
            norm_langs.extend(lang.split(","))
        for lang in norm_langs:
            doc_count_by_lang[lang] += 1
            for w in words:
                doc_freq[lang][w] += 1
                exs = examples[lang][w]
                if len(exs) < 3:
                    exs.append(doc_id)
    return doc_freq, examples, doc_count_by_lang


NUMERAL_RE = re.compile(r"^[ivxlcdm]+$")
GREEK_LETTER_RE = re.compile(r"^[Ͱ-Ͽἀ-῿]+$")


def strip_accents(s: str) -> str:
    """NFD-decompose and drop combining marks, so an accented Greek token
    (τοῦ) matches an unaccented entry in GREEK_FORMULA/GREEK_FUNCTION
    (του). Greek tokens here keep their accents in the output TSV; this
    is only used to decide the formula/function flags."""
    decomposed = unicodedata.normalize("NFD", s)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def classify(lang: str, token: str) -> tuple[bool, bool, bool]:
    base = lang.split("-")[0]
    key = strip_accents(token) if base == "grc" else token
    formula = key in FORMULA_BY_LANG.get(base, ())
    function = key in FUNCTION_BY_LANG.get(base, ())
    numeral_like = False
    if base == "la":
        numeral_like = bool(NUMERAL_RE.match(token))
    elif base == "grc":
        # A single isolated Greek letter in running text is almost always
        # an alphabetic numeral (the Greek numeral system reuses letters:
        # alpha=1, iota=10, kappa=20, ...) or an abbreviation remnant, not
        # a one-letter word; heuristic, not a lemmatizer-grade check.
        numeral_like = len(token) == 1 and bool(GREEK_LETTER_RE.match(token))
    return formula, function, numeral_like


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="deduplicated merged corpus JSONL")
    ap.add_argument("--output", required=True, help="candidate TSV path")
    ap.add_argument("--top-n", type=int, default=300)
    ap.add_argument("--min-docs-for-language", type=int, default=20,
                     help="skip languages with fewer documents than this")
    args = ap.parse_args(argv)

    doc_freq, examples, doc_count_by_lang = build_doc_frequencies(args.input)

    rows = []
    summary = {}
    for lang, counter in doc_freq.items():
        n_docs = doc_count_by_lang[lang]
        if n_docs < args.min_docs_for_language:
            continue
        top = counter.most_common(args.top_n)
        formula_n = function_n = numeral_n = 0
        for rank, (token, df) in enumerate(top, start=1):
            formula, function, numeral_like = classify(lang, token)
            formula_n += formula
            function_n += function
            numeral_n += numeral_like
            rows.append({
                "language": lang,
                "rank": rank,
                "token": token,
                "doc_frequency": df,
                "doc_freq_share": round(df / n_docs, 4) if n_docs else 0.0,
                "is_formula": formula,
                "is_function": function,
                "numeral_like": numeral_like,
                "examples": ";".join(examples[lang][token]),
            })
        summary[lang] = {
            "documents_with_this_language": n_docs,
            "distinct_tokens": len(counter),
            "top_n_marked_formula": formula_n,
            "top_n_marked_function": function_n,
            "top_n_numeral_like": numeral_n,
        }

    with open(args.output, "w", encoding="utf-8") as f:
        f.write("language\trank\ttoken\tdoc_frequency\tdoc_freq_share\t"
                "is_formula\tis_function\tnumeral_like\texamples\n")
        for r in rows:
            f.write(f"{r['language']}\t{r['rank']}\t{r['token']}\t"
                    f"{r['doc_frequency']}\t{r['doc_freq_share']}\t"
                    f"{r['is_formula']}\t{r['is_function']}\t{r['numeral_like']}\t"
                    f"{r['examples']}\n")

    print(json.dumps(summary, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
