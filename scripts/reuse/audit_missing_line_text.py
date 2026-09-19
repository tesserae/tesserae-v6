"""
audit_missing_line_text.py

Scans every distinct (work, ref) the reuse table (cache/reuse_pairs/<lang>.db,
built by build_reuse_table.py) cites on either side of a pair, and reports how
many resolve to empty text through backend.reuse_table._line_text -- the same
lookup GET /api/reuse/line uses to fill in a quotation's text for the Reader's
Reuse tab.

Written to investigate the 2026-09-19 report that Tertullian's Ad Nationes
Libri Duo showed a reuse reference with no text: that work has a STALE
plain-named lemma cache file (an old CTS-URN tagging scheme) sitting alongside
a current, correctly-tagged hashed one, and _work_cache_path used to prefer
the stale plain file whenever both existed for the same work. The fix (hashed
name checked first, matching backend/lemma_cache.py's own convention) is in
backend/reuse_table.py; this script is the before/after measurement, and
stays as a standing check for a future case of the same failure mode (a work
whose lemma cache was rebuilt under a new tagging scheme without the old
plain-named file being cleaned up).

Before the fix (2026-09-19, la): 13,983 missing / 211,231 checked, across 101
works. After: 1,158 missing, across 4 works -- eugippius.excerpta_ex_operibus
_augustini (976), magnus_felix_ennodius.carmina (171), pseudo_cyprian.carmina
(6), juvencus_caius_vettius_aquilinus.evangeliorum_libri_quattuor (5). Those
four are NOT a lookup bug: each has a stale plain cache (old CTS-URN tags,
file_hash not matching the live .tess file) and NO hashed cache at all under
the current spelling -- i.e. the lemma cache for that exact work was simply
never rebuilt after its .tess file's tags were simplified, a data gap to
close by rebuilding those four caches (scripts/batch_lemma_cache.py or
equivalent), not something a smarter lookup can paper over. This script's
per-work breakdown is what to re-check after that rebuild.

Usage:
  python3 scripts/reuse/audit_missing_line_text.py --language la
"""
import argparse
import os
import sys
from collections import Counter, defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, BASE_DIR)

from backend import reuse_table  # noqa: E402


def audit(language):
    """Grouped by work BEFORE checking, and each work's refs checked as one
    contiguous run -- backend.reuse_table._load_work_lines is memoized with
    lru_cache(maxsize=128), and the corpus here has 700+ distinct works
    among the pairs. Checking refs in the table's own row order interleaves
    works throughout the scan, so the 129th distinct work evicts the 1st
    and its next ref re-parses that work's whole lemma cache file from
    scratch -- with hundreds of works this thrashes the cache on nearly
    every lookup instead of loading each file once, which is what made an
    early version of this scan still running after ten minutes."""
    conn = reuse_table._get_connection(language)
    if not conn:
        raise SystemExit(f"No reuse table for language '{language}'")
    rows = conn.execute("SELECT work_a, line_a_ref, work_b, line_b_ref FROM pairs").fetchall()

    refs_by_work = defaultdict(set)
    for r in rows:
        refs_by_work[r['work_a']].add(r['line_a_ref'])
        refs_by_work[r['work_b']].add(r['line_b_ref'])

    missing_by_work = Counter()
    checked = 0
    for work, refs in refs_by_work.items():
        for ref in refs:
            checked += 1
            if not reuse_table._line_text(language, work, ref):
                missing_by_work[work] += 1

    return {
        'pair_rows': len(rows),
        'distinct_refs_checked': checked,
        'missing_total': sum(missing_by_work.values()),
        'missing_by_work': dict(missing_by_work),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--language', default='la')
    args = ap.parse_args()

    result = audit(args.language)
    print(f"[audit_missing_line_text] {result['pair_rows']} pair rows, "
          f"{result['distinct_refs_checked']} distinct (work, ref) refs checked")
    print(f"[audit_missing_line_text] {result['missing_total']} refs resolve to empty text, "
          f"across {len(result['missing_by_work'])} works")
    for work, n in sorted(result['missing_by_work'].items(), key=lambda kv: -kv[1]):
        print(f"    {work}: {n}")


if __name__ == '__main__':
    main()
