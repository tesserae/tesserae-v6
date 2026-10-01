"""Build a Koine Greek lemma lookup table from the LXX-Rahlfs-1935 morphology.

Reads (plain-text TSV files despite their .csv extension), downloaded under
``_source/`` from https://github.com/eliranwong/LXX-Rahlfs-1935 (branch
``master``):

  - ``_source/text_accented.csv``        (idx, idx, accented surface form)
  - ``_source/OSSP_lexemes.csv``         (idx, accented lexeme/lemma)
      Per-occurrence lemma integrated from the Open Scriptures Septuagint
      Project (David Troidl / openscriptures/GreekResources).
  - ``_source/Lex_LXXno.csv``            (idx, numeric CATSS/CCAT lexeme id)
  - ``_source/09a_01-04.csv``            (lexeme id, HTML lexicon entry with
      lemma text and a part-of-speech label, e.g. "Proper Noun")
      This is ``09a_LXX_lexicon/01-04.csv`` in the source repo.

All four per-occurrence files (``text_accented.csv``, ``OSSP_lexemes.csv``,
``Lex_LXXno.csv``, and incidentally ``text_unaccented.csv`` /
``patched_623693.csv``, not used here) have exactly 623,693 rows, one per
LXX word occurrence, in lock-step order (verified: the leading index column
matches 1:1 across all of them, zero mismatches over the full file).
``09a_01-04.csv`` is the CATSS/CCAT analytical lexicon keyed by the numeric
id in ``Lex_LXXno.csv`` (14,176 entries, one per unique lexeme id; covers
every id used). Comparing, for every one of the 623,693 occurrences, the
normalized lemma taken directly from ``OSSP_lexemes.csv`` against the
normalized lemma looked up via ``Lex_LXXno.csv`` -> ``09a_01-04.csv`` gives
100% agreement, so this script uses the simpler direct path
(``OSSP_lexemes.csv``) for the lemma itself, and the id -> lexicon join only
to read off the part-of-speech label (to flag proper nouns).

Writes, under ``data/lemma_tables/``:

  - ``greek_koine_lemmas.json``   normalized surface form -> normalized lemma,
    for forms NOT already present as a key in ``greek_lemmas.json`` with the
    same value. When a surface form has more than one attested lexeme in the
    Septuagint, the most frequent (by occurrence count) is kept; ties are
    broken by picking the alphabetically first lemma, for determinism.
  - ``greek_koine_conflicts.json`` forms that already exist in
    ``greek_lemmas.json`` with a DIFFERENT value, for a human to adjudicate:
    ``{form: {"main": <existing lemma>, "koine": <new lemma>,
    "koine_count": <occurrences of the koine lemma for this form>}}``.
  - ``GREEK_KOINE_LICENSE.txt`` attribution/licence text.

Normalization matches the conventions already used in
``data/lemma_tables/greek_lemmas.json``: NFD-decompose, drop combining marks
(accents/breathings/iota subscript), lowercase, final sigma (``ς``) rewritten
as medial sigma (``σ``), and anything left that is not a Greek letter (or
plain a-z) is dropped. A form or lemma that normalizes to the empty string
(stray punctuation, ano teleia, numeral marks, etc.) is skipped.

Licence: the source repository (eliranwong/LXX-Rahlfs-1935) is released
under CC BY-NC-SA 4.0, itself a derivative of the CATSS/CCAT LXX morphology
(Thesaurus Linguae Graecae / CATSS, dir. R. Kraft) and, for the per-word
lexeme integration used here, of the Open Scriptures Septuagint Project
(David Troidl). See ``GREEK_KOINE_LICENSE.txt`` for the full text.

Usage:
    python scripts/corpus/build_greek_koine_table.py
Run from the repository root (expects ``_source/`` beside it and
``data/lemma_tables/greek_lemmas.json`` to already exist).
"""

import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_source"
TABLES = ROOT / "data" / "lemma_tables"

TEXT_ACCENTED = SRC / "text_accented.csv"
OSSP_LEXEMES = SRC / "OSSP_lexemes.csv"
LEX_LXXNO = SRC / "Lex_LXXno.csv"
LEXICON_01_04 = SRC / "09a_01-04.csv"

MAIN_TABLE = TABLES / "greek_lemmas.json"
OUT_TABLE = TABLES / "greek_koine_lemmas.json"
OUT_CONFLICTS = TABLES / "greek_koine_conflicts.json"
OUT_LICENSE = TABLES / "GREEK_KOINE_LICENSE.txt"

LEMMA_HTML_RE = re.compile(r"<font color='3'>(.*?)</font>")
POS_HTML_RE = re.compile(r"】<i>(.*?)</i>")  # after the 【...】 bracket marker

LICENSE_TEXT = """\
Koine Greek lemma table: source licence and attribution
=========================================================

data/lemma_tables/greek_koine_lemmas.json and
data/lemma_tables/greek_koine_conflicts.json are built by
scripts/corpus/build_greek_koine_table.py from word-occurrence and lexicon
data published in the GitHub repository:

    eliranwong/LXX-Rahlfs-1935
    https://github.com/eliranwong/LXX-Rahlfs-1935
    Copyright 2017 Eliran Wong

That repository is licensed under a Creative Commons
Attribution-NonCommercial-ShareAlike 4.0 International License
(CC BY-NC-SA 4.0): https://creativecommons.org/licenses/by-nc-sa/4.0/

Files used here (branch master):
  - 01_wordlist_unicode/text_accented.csv  (word occurrences, accented)
  - 02_lexemes/OSSP_lexemes.csv            (per-occurrence lexeme/lemma)
  - 02_lexemes/Lex_LXXno.csv               (per-occurrence lexeme id)
  - 09a_LXX_lexicon/01-04.csv              (lexicon: lemma text + part of
                                             speech, including proper-noun
                                             marking, keyed by lexeme id)

Per the source repository's own README, this material is itself a
derivative work. Two upstream sources are acknowledged by name there and
are acknowledged again here:

  - The CATSS/CCAT morphologically analyzed Septuagint text (LXXM), the
    computer form of the Septuagint (Rahlfs 1935) prepared by the
    Thesaurus Linguae Graecae (TLG) project (dir. T. Brunner, UC Irvine)
    and morphologically analyzed by CATSS under the direction of Robert
    Kraft, University of Pennsylvania (CCAT):
    http://ccat.sas.upenn.edu/gopher/text/religion/biblical/lxxmorph/
  - The Open Scriptures Septuagint Project (lexeme integration), shared by
    David Troidl: https://github.com/openscriptures/GreekResources

Because the CC BY-NC-SA 4.0 licence is NonCommercial and ShareAlike, any
redistribution of greek_koine_lemmas.json or greek_koine_conflicts.json
(or of a lemma table built from them) must carry the same attribution and
licence terms, and must not be used commercially without separate
permission from Eliran Wong / the CATSS and OSSP source projects.
"""


def normalize(s):
    """Normalize a Greek string to the main table's convention: NFD-decompose,
    drop combining marks, lowercase, final sigma -> medial sigma, drop
    anything left that isn't a letter."""
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = s.replace("ς", "σ")  # ς -> σ
    s = re.sub(r"[^a-zα-ωϛ]", "", s)  # a-z, greek lower, stigma
    return s


def load_lexicon_pos(path):
    """id (str) -> part-of-speech label string, from the 09a HTML lexicon."""
    pos_by_id = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 2:
                continue
            lid, html = parts[0], parts[1]
            m = POS_HTML_RE.search(html)
            pos_by_id[lid] = m.group(1) if m else None
    return pos_by_id


def main():
    for p in (TEXT_ACCENTED, OSSP_LEXEMES, LEX_LXXNO, LEXICON_01_04, MAIN_TABLE):
        if not p.exists():
            print(f"ERROR: required input missing: {p}", file=sys.stderr)
            sys.exit(1)

    print("Loading main table...")
    main_table = json.load(open(MAIN_TABLE, encoding="utf-8"))

    print("Loading 09a lexicon (id -> part of speech)...")
    pos_by_id = load_lexicon_pos(LEXICON_01_04)

    print("Streaming occurrence files and counting (surface, lemma) pairs...")
    # surface_norm -> Counter(lemma_norm -> occurrence count)
    counts = defaultdict(Counter)
    # surface_norm -> Counter(lemma_norm -> count of occurrences tagged Proper Noun)
    proper_counts = defaultdict(Counter)

    n_rows = 0
    n_skipped_empty = 0
    with open(TEXT_ACCENTED, encoding="utf-8") as f_surf, open(
        OSSP_LEXEMES, encoding="utf-8"
    ) as f_lem, open(LEX_LXXNO, encoding="utf-8") as f_id:
        for line_surf, line_lem, line_id in zip(f_surf, f_lem, f_id):
            n_rows += 1
            p_surf = line_surf.rstrip("\n").split("\t")
            p_lem = line_lem.rstrip("\n").split("\t")
            p_id = line_id.rstrip("\n").split("\t")
            if len(p_surf) < 3 or len(p_lem) < 2 or len(p_id) < 2:
                n_skipped_empty += 1
                continue
            surface_norm = normalize(p_surf[2])
            lemma_norm = normalize(p_lem[1])
            lid = p_id[1]
            if not surface_norm or not lemma_norm:
                n_skipped_empty += 1
                continue
            counts[surface_norm][lemma_norm] += 1
            pos = pos_by_id.get(lid)
            if pos and "Proper Noun" in pos:
                proper_counts[surface_norm][lemma_norm] += 1

    print(f"  rows read: {n_rows}, skipped (empty after normalization): {n_skipped_empty}")
    print(f"  unique normalized surface forms: {len(counts)}")

    print("Selecting most frequent lemma per surface form...")
    koine_table = {}
    conflicts = {}
    n_already_correct = 0
    n_proper_entries = 0

    for surface_norm, lemma_counter in counts.items():
        # most frequent; ties broken alphabetically for determinism
        best_count = max(lemma_counter.values())
        best_lemmas = sorted(l for l, c in lemma_counter.items() if c == best_count)
        best_lemma = best_lemmas[0]

        if surface_norm in main_table:
            if main_table[surface_norm] == best_lemma:
                n_already_correct += 1
                continue
            else:
                conflicts[surface_norm] = {
                    "main": main_table[surface_norm],
                    "koine": best_lemma,
                    "koine_count": best_count,
                }
                continue

        koine_table[surface_norm] = best_lemma
        if proper_counts[surface_norm][best_lemma] > best_count / 2:
            n_proper_entries += 1

    print(f"  already correct in main table (skipped): {n_already_correct}")
    print(f"  new koine table entries: {len(koine_table)}")
    print(f"  conflicts (different lemma in main table): {len(conflicts)}")
    print(f"  of the new entries, majority-Proper-Noun: {n_proper_entries}")

    TABLES.mkdir(parents=True, exist_ok=True)

    print(f"Writing {OUT_TABLE} ...")
    with open(OUT_TABLE, "w", encoding="utf-8") as f:
        json.dump(koine_table, f, ensure_ascii=False, indent=0, sort_keys=True)

    print(f"Writing {OUT_CONFLICTS} ...")
    with open(OUT_CONFLICTS, "w", encoding="utf-8") as f:
        json.dump(conflicts, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Writing {OUT_LICENSE} ...")
    with open(OUT_LICENSE, "w", encoding="utf-8") as f:
        f.write(LICENSE_TEXT)

    print("Done.")
    print(f"SUMMARY new_entries={len(koine_table)} conflicts={len(conflicts)} "
          f"already_correct={n_already_correct} proper_noun_entries={n_proper_entries}")


if __name__ == "__main__":
    main()
