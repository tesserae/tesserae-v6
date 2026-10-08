"""List candidate works for backend/citations/work_depth_overrides.json.

work_depth_overrides.json is a hand-curated {work_id: depth} table:
derive_work_depth_journal.py's own docstring explains why an automatic
statistic (a single-value mode) cannot reliably tell a work's genuine-
but-minority deeper citation convention (Tacitus' Annales/Historiae,
book.chapter.section; every Plautus and Terence play, act.scene.line)
apart from another work's similarly large minority of citation noise
(cicero.pro_archia's bibliographic-abbreviation collisions). The task
this script was written for confirmed the three already in that file by
direct reading, the same way COMMA_CHAIN_DIAGNOSIS.md itself named
Tacitus and Plautus as examples of the "corpus-resolution gap" problem.

This script does NOT decide which further works belong in that file --
it only surfaces candidates, using the same noise-aware re-parse
derive_work_depth_journal.py uses (surface text re-tokenized under the
current grammar, _is_clean_split_level filtering out an obvious 4-digit
year or single-Roman-letter riding a comma before counting a level as
real), for a human to read and confirm or reject by hand, the same way
Tacitus/Plautus/Terence were.

Criterion: every work with at least 30 citations in citations_v2.db where
15% or more of its citations have a (noise-filtered) depth exceeding the
work's own corpus depth (work_depth.json). For each: the share over
threshold, the corpus depth, the most common deeper depth reached, and
three example surfaces at that deeper depth.

Output: writes a Markdown table to
/home/ncoffee/tesserae-backups/ejc_index_2026-09-14/DEPTH_OVERRIDE_CANDIDATES.md
(read-only against citations_v2.db; writes only that one report file).

2026-09-18 follow-up: every candidate at >=50% share was hand-read (the
full surface list per work, not just the report's 3 examples) and six
were added to work_depth_overrides.json as genuine chapter.section (or
book.chapter.section) conventions -- cicero.in_catilinam (3),
athenaeus.deipnosophists (2), cicero.philippicae (3),
rufus_of_ephesus.de_renum_et_vesicae_affectionibus (3),
cicero.pro_a_cluentio (2), cicero.de_lege_agraria_contra_rullum (3).
The rest of that >=50% band were left out on the same read: plautus.
truculentus was already covered by the blanket plautus.* entry;
cicero.pro_murena, cicero.pro_l_flacco, and cicero.pro_sestio had a
second "level" whose values were implausibly large or scaled for a
chapter number (or, for pro_sestio, carried the double-newline-before-
a-bare-number shape this task has already identified elsewhere as a
footnote marker) -- reading as page/edition/footnote noise, not a
citation dimension; cicero.de_amicitia's own examples were mostly a
different, pre-existing bug (bare "Cic. Leg." mis-resolving to this work
instead of the uncorpused De Legibus), not evidence about this work's
real convention; aristotle.de_memoria_et_reminiscentia was excluded
because COMMA_CHAIN_DIAGNOSIS.md had already flagged its corpus depth as
unreliable (based on 3 tagged lines) and its real citation practice as
Bekker-page, not chapter-based -- confirmed again here (its first two
"levels" are almost always the fixed placeholder 1/I/i, never a real
varying hierarchy); ausonius.mosella is a single continuous poem with no
chapters at all, so a second level there cannot be anything but noise.

Second pass, same day: cicero.de_oratore (requested directly, confirmed
by a book.chapter.section pattern climbing steadily through book I's
chapters) plus a read of the 30-50% band added cicero.de_officiis,
cicero.academica, cicero.de_natura_deorum (all book.chapter.section with
climbing chapters), cicero.pro_publio_quinctio, cicero.pro_balbo,
cicero.de_domo_sua (single-speech chapter.section, each with the same
chapter recurring at different, consecutive sections in the data). Left
out: cicero.orator (one of its own 3 examples, "Orat. 839 d", is far too
large for a ~238-section work, and its first level is almost always the
fixed placeholder "I"/"1") and claudius_ptolemaeus.musica (the same
fixed-placeholder pattern, plus a direct year example, "Mus., I (1897),
66" -- also flagged inconsistent in work_depth.json already, so it was
never touched without an override anyway); plautus.cistellaria, also in
this band, was already covered by the blanket plautus.* entry.

Note for whoever wires this up to a live index: keeping a locus whole at
this deeper, scholars'-convention depth is NOT the same as the corpus
being able to resolve/display it. The lookup side (backend/scholarship.py
and friends) still needs its own chapter.section -> our-section-only-tag
mapping for every one of these works before a kept-whole citation finds
an actual passage; until that exists, it will correctly fail to find one
rather than resolve to the wrong passage, which is the point of doing it
this way instead of truncating.

Usage:
  python3 list_depth_override_candidates.py [--source PATH] [--min-citations N] [--min-share F] [--out PATH]
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

DEFAULT_SOURCE = "/home/ncoffee/tesserae-backups/ejc_index_2026-09-14/citations_v2.db"
DEFAULT_OUT = "/home/ncoffee/tesserae-backups/ejc_index_2026-09-14/DEPTH_OVERRIDE_CANDIDATES.md"
MIN_CITATIONS = 30
MIN_SHARE = 0.15
MAX_EXAMPLES = 3


def _clean_depth(start_levels, start_seps, corpus_depth):
    n = len(start_levels)
    depth = min(corpus_depth, n)
    for i in range(corpus_depth, n):
        sep = start_seps[i - 1] if start_seps and i - 1 < len(start_seps) else None
        if sep == "COMMA" and not _is_clean_split_level(start_levels[i]):
            break
        depth = i + 1
    return depth


def derive(source_path, corpus_depth_map):
    idx = get_abbrev_index()
    conn = sqlite3.connect(source_path)
    rows = conn.execute(
        "SELECT work_id, surface FROM citations WHERE work_id IS NOT NULL AND surface IS NOT NULL"
    ).fetchall()
    conn.close()

    totals = collections.Counter()
    over_counts = collections.Counter()
    # per work: Counter of (deeper depth reached) -> count, among over-depth rows
    deeper_depth_counts = collections.defaultdict(collections.Counter)
    # per work: {deeper_depth: [example surfaces]}
    examples = collections.defaultdict(lambda: collections.defaultdict(list))

    for work_id, surface in rows:
        totals[work_id] += 1
        corpus_depth = corpus_depth_map.get(work_id)
        if not corpus_depth:
            continue
        citations = find_citations(surface, idx)
        if not citations or not citations[0].refs:
            continue
        ref = citations[0].refs[0]
        if ref.book_list:
            continue
        cd = _clean_depth(ref.start_levels, ref.start_seps or [], corpus_depth)
        if cd > corpus_depth:
            over_counts[work_id] += 1
            deeper_depth_counts[work_id][cd] += 1
            if len(examples[work_id][cd]) < MAX_EXAMPLES:
                examples[work_id][cd].append(surface)

    return totals, over_counts, deeper_depth_counts, examples


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default=DEFAULT_SOURCE)
    ap.add_argument("--min-citations", type=int, default=MIN_CITATIONS)
    ap.add_argument("--min-share", type=float, default=MIN_SHARE)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    if not os.path.exists(args.source):
        print(f"ERROR: source db not found at {args.source}", file=sys.stderr)
        sys.exit(1)

    citations_dir = os.path.join(WORK, "backend", "citations")
    with open(os.path.join(citations_dir, "work_depth.json"), encoding="utf-8") as f:
        corpus_depth_map = json.load(f)

    totals, over_counts, deeper_depth_counts, examples = derive(args.source, corpus_depth_map)

    candidates = []
    for work_id, total in totals.items():
        if total < args.min_citations:
            continue
        over = over_counts.get(work_id, 0)
        share = over / total
        if share < args.min_share:
            continue
        deeper_depth, _n = deeper_depth_counts[work_id].most_common(1)[0]
        candidates.append({
            "work_id": work_id,
            "total": total,
            "over": over,
            "share": share,
            "corpus_depth": corpus_depth_map[work_id],
            "deeper_depth": deeper_depth,
            "examples": examples[work_id][deeper_depth][:MAX_EXAMPLES],
        })
    candidates.sort(key=lambda c: c["share"], reverse=True)

    lines = []
    lines.append("# Depth-override candidates")
    lines.append("")
    lines.append(f"Generated by scripts/citations/list_depth_override_candidates.py from "
                 f"{args.source}, {sys.argv}.")
    lines.append("")
    lines.append(f"Every work with at least {args.min_citations} citations in citations_v2.db "
                 f"where {args.min_share:.0%} or more of its citations have a (noise-filtered) "
                 f"locus depth exceeding the work's own corpus depth (work_depth.json). Read-only "
                 f"listing, not an automatic decision: backend/citations/work_depth_overrides.json "
                 f"is meant to be hand-extended from this list, the same way tacitus.annales, "
                 f"tacitus.historiae, and every plautus.*/terence.* work were confirmed by direct "
                 f"reading, not derived.")
    lines.append("")
    lines.append(f"{len(candidates)} candidate works.")
    lines.append("")
    lines.append("| work_id | total citations | over-depth | share | corpus depth | deeper depth | example surfaces |")
    lines.append("|---|---|---|---|---|---|---|")
    for c in candidates:
        ex = "; ".join(repr(e) for e in c["examples"])
        lines.append(
            f"| {c['work_id']} | {c['total']} | {c['over']} | {c['share']:.1%} | "
            f"{c['corpus_depth']} | {c['deeper_depth']} | {ex} |"
        )

    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"{len(candidates)} candidates written to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
