"""Measure how much the new classical Greek lemma table (GLAUx-derived)
would improve lemma coverage, read-only against the PRODUCTION Greek index.

Reads (read-only, sqlite URI mode):
    /var/www/tesseraev6_flask/data/inverted_index/grc_index.db
    tables: texts(text_id, filename), lines(text_id, ref, content, lemmas
    JSON list, tokens JSON list)

Definition of "unresolved", per the task spec this script follows exactly:
a token is unresolved if its CURRENT stored lemma, once normalized, equals
the token's own normalized surface form, AND that normalized form is not a
key of EITHER existing table (data/lemma_tables/greek_lemmas.json or
greek_koine_lemmas.json). This matches the documented fallback behaviour:
"Forms in neither table keep their surface form as lemma." A token whose
true lemma happens to equal its own surface form (e.g. undeclinable
particles) is correctly excluded by the "not a key of either table" clause,
since such a form IS a key of one of the tables.

Text-group patterns (task spec): homer.iliad%, homer.odyssey%,
plato.respublica%, thucydides%, plutarch.%, herodotus%, sophocles.%,
septuaginta.%, plus the whole Greek index.

WHOLE-VS-PARTS DEDUP (found while building this, not asked for but
necessary for a correct count): 29 works in the Greek index are stored
TWICE -- once as a single whole-work file (e.g. homer.iliad.tess) and once
as a set of per-book/part files (homer.iliad.part.1.tess, .part.2.tess,
...) -- verified identical line-for-line (same ref, same tokens) on
Iliad, Odyssey, Republic, Thucydides and Herodotus (all five text groups
in this task's spec that have part files). Four of this task's eight
groups (Iliad, Odyssey, Republic, Thucydides) and Herodotus are affected;
Plutarch, Sophocles and Septuaginta are not (one file per work, no parts).
Counting both representations would double tokens for the affected works
and inflate the whole-index total by the sum of all duplicated texts. This
script excludes the whole-file text_id whenever part files for the same
work are also present, keeping only the parts, for every group and for the
whole-index figure. This is a counting choice for this measurement only;
nothing in the corpus or index is touched.

Also reports the new classical table's size / conflict count (read from the
build script's JSON outputs) and the 25 most frequent tokens still
unresolved after the new table is applied, computed over the WHOLE index
(not per group).

Usage:
    python scripts/corpus/measure_classical_coverage.py
"""

import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TABLES = ROOT / "data" / "lemma_tables"
MAIN_TABLE_PATH = TABLES / "greek_lemmas.json"
KOINE_TABLE_PATH = TABLES / "greek_koine_lemmas.json"
CLASSICAL_TABLE_PATH = TABLES / "greek_classical_lemmas.json"
CLASSICAL_CONFLICTS_PATH = TABLES / "greek_classical_conflicts.json"

DB_PATH = "file:/var/www/tesseraev6_flask/data/inverted_index/grc_index.db?mode=ro"

GROUP_PATTERNS = [
    ("homer.iliad%", "Iliad"),
    ("homer.odyssey%", "Odyssey"),
    ("plato.respublica%", "Plato Republic"),
    ("thucydides%", "Thucydides"),
    ("plutarch.%", "Plutarch"),
    ("herodotus%", "Herodotus"),
    ("sophocles.%", "Sophocles"),
    ("septuaginta.%", "Septuagint"),
]

PART_RE = re.compile(r"^(.*)\.part\.[^.]+\.tess$")


def normalize(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = s.replace("ς", "σ")
    s = re.sub(r"[^a-zα-ωϛ]", "", s)
    return s


def compute_whole_dup_exclusions(all_texts):
    """all_texts: list of (text_id, filename). Returns the set of text_ids
    for whole-work files that duplicate a set of .part. files for the same
    work (see module docstring)."""
    bases_with_parts = set()
    for _tid, fn in all_texts:
        m = PART_RE.match(fn)
        if m:
            bases_with_parts.add(m.group(1))
    excluded = set()
    for tid, fn in all_texts:
        if fn.endswith(".tess") and ".part." not in fn:
            base = fn[:-5]
            if base in bases_with_parts:
                excluded.add(tid)
    return excluded


def text_ids_for_pattern(all_texts, pattern, excluded):
    # translate a SQL LIKE pattern ('%' wildcard, no other specials used here)
    regex = re.escape(pattern).replace("%", ".*")
    rx = re.compile("^" + regex + "$")
    return [tid for tid, fn in all_texts if rx.match(fn) and tid not in excluded]


def measure(con, text_ids, label, main_table, koine_table, classical_table,
            collect_unresolved_tokens=None):
    if not text_ids:
        print(f"[{label}] 0 texts matched -- skipping")
        return None

    total_tokens = 0
    unresolved = 0
    resolved_by_classical = 0

    qmarks = ",".join("?" for _ in text_ids)
    cur = con.cursor()
    cur.execute(f"SELECT lemmas, tokens FROM lines WHERE text_id IN ({qmarks})", text_ids)
    for lemmas_json, tokens_json in cur:
        if not lemmas_json or not tokens_json:
            continue
        lemmas = json.loads(lemmas_json)
        tokens = json.loads(tokens_json)
        n = min(len(lemmas), len(tokens))
        for i in range(n):
            tok = tokens[i]
            lem = lemmas[i]
            tok_norm = normalize(tok)
            lem_norm = normalize(lem)
            if not tok_norm:
                continue
            total_tokens += 1
            if lem_norm != tok_norm:
                continue
            if tok_norm in main_table or tok_norm in koine_table:
                continue
            unresolved += 1
            if tok_norm in classical_table:
                resolved_by_classical += 1
            elif collect_unresolved_tokens is not None:
                collect_unresolved_tokens[tok] += 1

    pct_unresolved = unresolved / total_tokens * 100 if total_tokens else 0.0
    pct_fixed = resolved_by_classical / unresolved * 100 if unresolved else 0.0
    still_unresolved = unresolved - resolved_by_classical

    print(f"[{label}] texts: {len(text_ids)}")
    print(f"[{label}] tokens: {total_tokens}")
    print(f"[{label}] unresolved: {unresolved} ({pct_unresolved:.2f}% of tokens)")
    print(f"[{label}] resolved by classical table: {resolved_by_classical} "
          f"({pct_fixed:.2f}% of unresolved)")
    print(f"[{label}] still unresolved after classical table: {still_unresolved}")

    return {
        "label": label,
        "n_texts": len(text_ids),
        "total_tokens": total_tokens,
        "unresolved": unresolved,
        "resolved_by_classical": resolved_by_classical,
        "still_unresolved": still_unresolved,
    }


def main():
    print("Loading tables...")
    main_table = json.load(open(MAIN_TABLE_PATH, encoding="utf-8"))
    koine_table = json.load(open(KOINE_TABLE_PATH, encoding="utf-8"))
    classical_table = json.load(open(CLASSICAL_TABLE_PATH, encoding="utf-8"))
    classical_conflicts = json.load(open(CLASSICAL_CONFLICTS_PATH, encoding="utf-8"))
    print(f"  greek_lemmas.json: {len(main_table)}")
    print(f"  greek_koine_lemmas.json: {len(koine_table)}")
    print(f"  greek_classical_lemmas.json: {len(classical_table)}")
    print(f"  greek_classical_conflicts.json: {len(classical_conflicts)}")

    print(f"Connecting read-only to {DB_PATH} ...")
    con = sqlite3.connect(DB_PATH, uri=True)
    cur = con.cursor()
    cur.execute("SELECT text_id, filename FROM texts")
    all_texts = cur.fetchall()
    print(f"  {len(all_texts)} texts in the index")

    excluded = compute_whole_dup_exclusions(all_texts)
    print(f"  whole-file texts excluded as duplicates of .part. files: {len(excluded)}")
    for tid, fn in all_texts:
        if tid in excluded:
            print(f"    excluded: {fn}")

    results = {}
    for pattern, label in GROUP_PATTERNS:
        tids = text_ids_for_pattern(all_texts, pattern, excluded)
        results[label] = measure(con, tids, label, main_table, koine_table, classical_table)

    print("\n=== WHOLE GREEK INDEX ===")
    all_tids = [tid for tid, _fn in all_texts if tid not in excluded]
    overall_unresolved_tokens = Counter()
    results["WHOLE INDEX"] = measure(
        con, all_tids, "WHOLE INDEX", main_table, koine_table, classical_table,
        collect_unresolved_tokens=overall_unresolved_tokens,
    )

    print("\n=== 25 most frequent tokens still unresolved after the classical table (whole index) ===")
    for tok, cnt in overall_unresolved_tokens.most_common(25):
        print(f"    {tok!r}: {cnt}")

    print("\n=== SUMMARY TABLE (counts and percentages per group) ===")
    for label, r in results.items():
        if not r:
            continue
        pct_unres = r["unresolved"] / r["total_tokens"] * 100 if r["total_tokens"] else 0.0
        pct_fixed = r["resolved_by_classical"] / r["unresolved"] * 100 if r["unresolved"] else 0.0
        print(f"{label:16s} tokens={r['total_tokens']:>9} "
              f"unresolved={r['unresolved']:>8} ({pct_unres:5.2f}%) "
              f"resolved_by_classical={r['resolved_by_classical']:>8} ({pct_fixed:5.2f}% of unresolved) "
              f"still_unresolved={r['still_unresolved']:>8}")

    con.close()


if __name__ == "__main__":
    main()
