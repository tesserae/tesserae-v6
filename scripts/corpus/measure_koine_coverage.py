"""Measure how much the new Koine lemma table would improve Greek lemma
coverage on the Septuagint and Greek New Testament, read-only, against the
PRODUCTION Greek index.

Reads (read-only, sqlite URI mode):
    /var/www/tesseraev6_flask/data/inverted_index/grc_index.db
    tables: texts(text_id, filename), lines(text_id, ref, content, lemmas
    JSON list, tokens JSON list)

For the Septuagint (filename LIKE 'septuaginta.%') and separately for the
Greek New Testament, this script counts, over every token/lemma pair in
those texts' lines:
  - tokens skipped because they contain the ano teleia '·' or start
    with the spacing psili '᾿' (known tokenizer artifacts being fixed
    elsewhere, per instructions -- excluded from all counts below)
  - "unresolved": tokens whose current lemma, once normalized, is not a
    known lemma, where known = normalized values of
    data/lemma_tables/greek_lemmas.json, union normalized keys of the
    Greek-Latin dictionary from backend.synonym_dict.get_greek_latin_dict()
  - of those unresolved tokens, how many would find an entry by exact
    normalized-token lookup in the new data/lemma_tables/greek_koine_lemmas.json

NOTE on the GNT filename pattern: the task spec's 'sblgnt.%' does not match
anything in this index. The 27-book Greek New Testament is present under
'novum_testamentum.%' instead (confirmed: exactly 27 texts, one per NT
book). This script uses that pattern and reports the discrepancy.

Also reports the 20 most frequent tokens still unresolved after the new
table, and the new table's size / proper-noun count (read from the build
script's JSON outputs).
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
MAIN_TABLE = TABLES / "greek_lemmas.json"
KOINE_TABLE = TABLES / "greek_koine_lemmas.json"

DB_PATH = "file:/var/www/tesseraev6_flask/data/inverted_index/grc_index.db?mode=ro"

sys.path.insert(0, str(ROOT))  # so `import backend.synonym_dict` resolves within this worktree


def normalize(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = s.replace("ς", "σ")
    s = re.sub(r"[^a-zα-ωϛ]", "", s)
    return s


def is_skip_token(tok):
    if tok is None:
        return True
    if "·" in tok:  # ano teleia
        return True
    if tok.startswith("᾿"):  # spacing psili
        return True
    return False


def load_known_set():
    main_table = json.load(open(MAIN_TABLE, encoding="utf-8"))
    known = set(main_table.values())  # already normalized convention

    from backend.synonym_dict import get_greek_latin_dict

    _orig, normalized = get_greek_latin_dict()
    for k in normalized.keys():
        known.add(normalize(k))
    print(f"  known set: {len(known)} (main table values + normalized Greek-Latin dict keys)")
    return known


def measure(con, filename_pattern, label, known_set, koine_table):
    cur = con.cursor()
    cur.execute("SELECT text_id FROM texts WHERE filename LIKE ?", (filename_pattern,))
    text_ids = [r[0] for r in cur.fetchall()]
    print(f"[{label}] {len(text_ids)} texts matching '{filename_pattern}'")
    if not text_ids:
        return None

    total_tokens = 0
    skipped_tokens = 0
    unresolved = 0
    now_resolved_by_koine = 0
    unresolved_token_counter = Counter()  # surface token -> count, among still-unresolved after koine

    qmarks = ",".join("?" for _ in text_ids)
    cur.execute(
        f"SELECT lemmas, tokens FROM lines WHERE text_id IN ({qmarks})", text_ids
    )
    for lemmas_json, tokens_json in cur:
        if not lemmas_json or not tokens_json:
            continue
        lemmas = json.loads(lemmas_json)
        tokens = json.loads(tokens_json)
        n = min(len(lemmas), len(tokens))
        for i in range(n):
            tok = tokens[i]
            lem = lemmas[i]
            if is_skip_token(tok):
                skipped_tokens += 1
                continue
            total_tokens += 1
            lem_norm = normalize(lem)
            if lem_norm in known_set:
                continue
            unresolved += 1
            tok_norm = normalize(tok)
            if tok_norm in koine_table:
                now_resolved_by_koine += 1
            else:
                unresolved_token_counter[tok] += 1

    pct_unresolved = unresolved / total_tokens * 100 if total_tokens else 0.0
    pct_fixed = now_resolved_by_koine / unresolved * 100 if unresolved else 0.0
    still_unresolved = unresolved - now_resolved_by_koine

    print(f"[{label}] total tokens counted: {total_tokens} (skipped {skipped_tokens} marked-artifact tokens)")
    print(f"[{label}] unresolved (lemma not known): {unresolved} ({pct_unresolved:.2f}%)")
    print(f"[{label}] of those, resolved by new koine table: {now_resolved_by_koine} ({pct_fixed:.2f}% of unresolved)")
    print(f"[{label}] still unresolved after koine table: {still_unresolved}")
    print(f"[{label}] top 20 most frequent still-unresolved tokens:")
    for tok, cnt in unresolved_token_counter.most_common(20):
        print(f"    {tok!r}: {cnt}")

    return {
        "label": label,
        "total_tokens": total_tokens,
        "skipped_tokens": skipped_tokens,
        "unresolved": unresolved,
        "resolved_by_koine": now_resolved_by_koine,
        "still_unresolved": still_unresolved,
        "top20_unresolved": unresolved_token_counter.most_common(20),
    }


def main():
    print("Loading known-lemma set...")
    known_set = load_known_set()

    print("Loading new koine table...")
    koine_table = json.load(open(KOINE_TABLE, encoding="utf-8"))
    print(f"  koine table size: {len(koine_table)}")

    conflicts = json.load(open(TABLES / "greek_koine_conflicts.json", encoding="utf-8"))
    print(f"  koine conflicts file: {len(conflicts)} entries (not applied, for review)")

    print(f"Connecting read-only to {DB_PATH} ...")
    con = sqlite3.connect(DB_PATH, uri=True)

    results = {}
    results["septuagint"] = measure(con, "septuaginta.%", "Septuagint", known_set, koine_table)
    results["gnt"] = measure(con, "novum_testamentum.%", "GNT (novum_testamentum.*)", known_set, koine_table)

    # combined
    if results["septuagint"] and results["gnt"]:
        tt = results["septuagint"]["total_tokens"] + results["gnt"]["total_tokens"]
        un = results["septuagint"]["unresolved"] + results["gnt"]["unresolved"]
        rk = results["septuagint"]["resolved_by_koine"] + results["gnt"]["resolved_by_koine"]
        print(f"[COMBINED] total tokens: {tt}, unresolved: {un} ({un/tt*100:.2f}%), "
              f"resolved by koine: {rk} ({rk/un*100:.2f}% of unresolved)")

    con.close()


if __name__ == "__main__":
    main()
