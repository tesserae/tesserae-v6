"""Modal locus depth per work AS THE JOURNALS ACTUALLY CITE IT.

backend/citations/work_depth.json (derive_work_depth.py) gives each work's
depth according to the CORPUS's own .tess tagging. That is the wrong
number for a work whose scholarly citation convention is genuinely deeper
than this corpus tags it at -- Tacitus' Annales is tagged book.chapter but
routinely cited book.chapter.section; Plautus' plays are tagged as one
flat run of line numbers but routinely cited act.scene.line. Confirmed to
be live and harming real rows: Tacitus citations silently losing their
section number, Plautus act.scene.line citations fragmenting into three
separate, individually-wrong single-level rows.

This script reads a rebuilt journal-citation index (citations_v2.db, as it
stood BEFORE any depth-truncation rule existed, passed with --source) and
re-parses each citation's
own stored `surface` text (not the already-joined `locus_start` column) to
recover its real locus levels and separator types, the same way
extractor.py's live depth-truncation logic does. That lets this script
apply the SAME noise filter extractor.py already trusts
(_is_clean_split_level: reject a bare 4-digit number -- a publication
year -- or a single-character Roman numeral -- an edition-page letter --
riding past a comma) before counting a citation's depth, rather than
trusting the raw, unfiltered locus_start string.

This distinction matters in practice, not just in theory: a first version
of this script that took the modal depth straight from locus_start (no
re-parsing, no noise filter) gave cicero.pro_archia a journal depth of 2,
not 1 -- because "Arch. <section>, <year>" (a common bibliographic-
citation-abbreviation collision in this corpus, 'Arch.' also being a
journal abbreviation, not just Cicero's Pro Archia) is itself a very
common SHAPE, and it happens to have exactly 2 raw levels. Applying that
naive journal depth would have UNDONE the "no more than depth 1 for Pro
Archia" fix this task's own required tests depend on
(test_trailing_four_digit_year_is_dropped_not_split): a locus that is only
2 levels deep because its second level is a fabricated year is not
evidence of a genuine 2-level citation convention. The noise filter here
exists specifically to keep that distinction intact while still letting a
GENUINE deeper convention (Tacitus, Plautus) register if a plain
majority-vote modal computation ever supports it.

Finding, reported rather than silently forced: even with this filter, a
strict single-value mode over ALL of a work's citations still comes out
equal to its corpus depth for tacitus.annales (2) and plautus.stichus (1)
-- the deeper book.chapter.section / act.scene.line convention is real
(about a quarter and a seventh of their citations respectively, hand-
confirmed against real examples) but a MINORITY, and no
single-value mode can surface a minority pattern by definition. No other
automatic statistic tried (mode restricted to the over-corpus-depth
subset, share of a work's total citations reaching the deeper form,
count of distinct citing articles) reliably told this genuine-but-
minority convention apart from Pro Archia's similarly large minority of
noise without risking the same kind of regression found above on some
OTHER work. This script's method is there for anyone who re-runs it
later, and to record why a plain "most common depth" answer, applied
faithfully, does not by itself relieve Tacitus or Plautus: those two
works are handled instead by an injected depth override
(work_depth_overrides.json), not this script's live output.

Output: backend/citations/work_depth_journal.json, {work_id: modal_depth},
for every work_id with at least MIN_CITATIONS rows in citations_v2.db.
Consumed by extractor.py._apply_work_depth, which truncates/splits an
over-deep locus only when it exceeds BOTH the corpus depth (work_depth.
json) AND this journal depth (falling back to the corpus depth alone when
a work has no journal-depth entry here).

Usage:
  python3 derive_work_depth_journal.py --source PATH [--min-citations N]
"""
import argparse
import collections
import json
import os
import sqlite3
import sys

WORK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, WORK)

from backend.citations import index as get_abbrev_index
from backend.citations.parser import find_citations
from backend.citations.extractor import _is_clean_split_level

MIN_CITATIONS = 10
OUT_DIR = os.path.join(WORK, "backend", "citations")


def _clean_depth(start_levels, start_seps, corpus_depth):
    """How many of this citation's own locus levels are trustworthy,
    starting from the corpus depth and extending outward only through
    levels that either aren't comma-joined (a dot/whitespace-joined level
    is never noise-checked, matching extractor.py's own truncation gate)
    or pass _is_clean_split_level. Stops at the first untrustworthy level
    -- deliberately mirrors extractor.py._apply_work_depth's own logic, so
    this script measures depth the same way the live rule will apply it."""
    n = len(start_levels)
    depth = min(corpus_depth, n)
    for i in range(corpus_depth, n):
        sep = start_seps[i - 1] if start_seps and i - 1 < len(start_seps) else None
        if sep == "COMMA" and not _is_clean_split_level(start_levels[i]):
            break
        depth = i + 1
    return depth


def derive(source_path, min_citations, corpus_depth_map):
    idx = get_abbrev_index()
    conn = sqlite3.connect(source_path)
    rows = conn.execute(
        "SELECT work_id, surface FROM citations WHERE work_id IS NOT NULL AND surface IS NOT NULL"
    ).fetchall()
    conn.close()

    totals = collections.Counter()
    depth_counts = collections.defaultdict(collections.Counter)
    n_unparsed = 0
    for work_id, surface in rows:
        totals[work_id] += 1
        corpus_depth = corpus_depth_map.get(work_id, 1)
        citations = find_citations(surface, idx)
        if not citations or not citations[0].refs:
            # Couldn't re-derive a ref from the stored surface (rare --
            # an already-resolved v2 row whose surface no longer parses
            # the same way under the current grammar). Fall back to
            # crediting it at the corpus depth: no evidence either way.
            n_unparsed += 1
            depth_counts[work_id][corpus_depth] += 1
            continue
        ref = citations[0].refs[0]
        if ref.book_list:
            depth_counts[work_id][1] += 1
            continue
        depth_counts[work_id][_clean_depth(ref.start_levels, ref.start_seps or [], corpus_depth)] += 1

    result = {}
    skipped_low_count = 0
    for work_id, total in totals.items():
        if total < min_citations:
            skipped_low_count += 1
            continue
        modal_depth, _n = depth_counts[work_id].most_common(1)[0]
        result[work_id] = modal_depth
    return result, len(rows), skipped_low_count, n_unparsed


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True,
                    help="path to the rebuilt journal-citation sqlite database")
    ap.add_argument("--min-citations", type=int, default=MIN_CITATIONS)
    ap.add_argument("--out-dir", default=OUT_DIR)
    args = ap.parse_args()

    if not os.path.exists(args.source):
        print(f"ERROR: source db not found at {args.source}", file=sys.stderr)
        sys.exit(1)

    with open(os.path.join(OUT_DIR, "work_depth.json"), encoding="utf-8") as f:
        corpus_depth_map = json.load(f)

    result, n_rows, n_skipped, n_unparsed = derive(args.source, args.min_citations, corpus_depth_map)
    print(f"read {n_rows} citation rows from {args.source} ({n_unparsed} surfaces didn't "
          f"re-parse under the current grammar, credited at corpus depth)", file=sys.stderr)
    print(f"{len(result)} work ids with >= {args.min_citations} citations get a journal depth "
          f"({n_skipped} work ids fell below that and were skipped)", file=sys.stderr)

    os.makedirs(args.out_dir, exist_ok=True)
    out_path = os.path.join(args.out_dir, "work_depth_journal.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, sort_keys=True, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
