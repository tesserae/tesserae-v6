# Data release: Multi-Channel Feature Fusion for Finding Coptic Text Reuse

Evaluation data, gold-standard files, run logs, ranked outputs, and
reproduction scripts for the article "Multi-Channel Feature Fusion for
Finding Coptic Text Reuse" (Coffee et al.). The Coptic search itself is
free to use at https://tesserae.caset.buffalo.edu. The Tesserae V6 code is
at https://github.com/tesserae/tesserae-v6.

## Contents

### gold/
- `romans_isaiah_gold_22.csv` — the held-out benchmark (article §3.2,
  §4.3): the 22 citations of Isaiah in Romans marked by an explicit
  citation formula. Fixed from standard reference lists before any V6
  output for the pair was seen; all 22 appear as direct citations in
  Nestle-Aland 28, Appendix III (loci citati vel allegati), s.v. Isaias.
- `tsk_hebrews_psalms_gold_124.csv` — the broad development benchmark
  (article §3.2): Hebrews-Psalms cross-references derived from the
  OpenBible.info dataset (itself derived from the Treasury of Scripture
  Knowledge), filtered to crowd-vote counts of 20 or higher, with Psalm
  numbers converted to LXX numbering (conversion table in the article's
  Appendix B).
- `tsk_hebrews_psalms_strict_11.csv` — the stricter subset (votes >= 50,
  best Psalm verse per NT verse): 11 widely attested verbatim quotations.
- `tsk_hebrews_psalms_all_votes_lxx.csv` — the unfiltered Hebrews-Psalms
  candidate set with vote counts, before the vote-20 filter (all NT books,
  LXX numbering), for anyone who wants a different threshold.
- `greek_hebrews_psalms_gold_849.csv` — the Greek-diagnostic gold set
  (article §3.3), the 849 candidate pairs used in the Greek NT x LXX
  comparison.

### outputs/
- `hebrews_psalms_ranked_10000.jsonl` — Sahidic Hebrews x Sahidic Psalms,
  top 10,000 fused ranks, produced 2026-08-27 on the deployed system with
  the shipped biblical-Coptic profile. Fields: rank, source_ref (Psalms),
  target_ref (Hebrews), fused_score, match_basis, quotation_run_length.
- `romans_isaiah_ranked_10000.jsonl` — Sahidica Romans x Sahidic Isaiah,
  the single held-out run reported in the article (produced 2026-08-27,
  weights frozen, never re-run). Recomputing the article's Table 4 from
  this file with `gold/romans_isaiah_gold_22.csv` reproduces it exactly:
  8 / 11 / 13 / 17 / 17 / 20 of 22 at top 10 / 50 / 100 / 500 / 1,000 /
  5,000.
- `shenoute_abraham_bible_top50.csv` — Sahidic Bible x Shenoute, Abraham
  Our Father, top 50 fused ranks with matched text (article §4.4),
  generated 2026-06-15 with the post-punctuation-fix configuration whose
  ranks the article cites. New Testament line text is omitted per the
  Sahidica license (see Licensing below); references are given instead.
  A 2026-08-29 regeneration on the then-current code reproduces the top
  five exactly, swaps two equal-run-length pairs at ranks 6 and 7, and
  ranks the 9-token Isaiah 56:5 fragment below the top 50; see the
  run-to-run note below.

These outputs carry references and scores; the two JSONL files contain no
text and redistribute nothing.

Note on run-to-run variation: the V6 fusion search parallelizes across
worker processes, and tie-adjacent ranks can shift by a pair or two
between runs. Against `tsk_hebrews_psalms_gold_124.csv`, this release's
Hebrews-Psalms run finds 18 of 124 in the top 100; the article's
development-sequence table, measured on earlier runs, reports 17. The
held-out Romans-Isaiah run is the single run the article reports and is
not subject to this caveat.

### logs/
Weight-optimization run logs (JSONL, one iteration per line) and the
best-weights snapshots for the sweeps described in the article: the
initial re-tuning sweep, the full-inventory re-optimization, the
quotation-channel baselines, the Greek diagnostic baseline, and the
experimental thematic sweeps. The experimental thematic profile in these
logs used a separate hand-curated quotation list as a tuning constraint;
no result in the article depends on that profile.

### scripts/
- `build_gold_set.py`, `build_greek_gold.py` — benchmark construction
  from the OpenBible.info cross-reference data (download that dataset
  from OpenBible.info; it is not redistributed here).
- `run_optimization.py`, `run_optimization_thematic.py`,
  `run_greek_validation.py` — the weight sweeps.
- `run_pair_search.py` — reproduces the two ranked JSONL outputs on a
  Tesserae V6 checkout with the Coptic corpus.
- `becky_abraham_parallels.py` — generates the Shenoute x Bible parallels
  file (the specialist-review deliverable and the released top-50 CSV).
- `check_punct_fix.py` — the punctuation-tolerance regression check.
- `strip_sahidica_text.py` — produced the released Shenoute CSV from the
  raw output; documents exactly what was omitted and why.

## Licensing
The Coptic corpus is not uniformly licensed (article §3.1 note): of the
180 indexed texts, 97 are CC BY-SA, 51 CC BY 4.0, 27 are the Sahidica
New Testament ((c) 2000-2006 J. Warren Wells, academic use only), 4 are
CC BY-NC-SA 4.0, and 1 is unstated. This release therefore includes no
Sahidica line text: the ranked JSONL outputs carry references only, and
the Shenoute CSV replaces New Testament line text with the verse
reference. Every result is fully reproducible by anyone holding the
freely obtainable Sahidica text, using the scripts above. Sahidic Old
Testament and Shenoute text included here is from Coptic Scriptorium
under its CC licenses.

Gold-standard CSVs and logs produced by this project are released under
CC BY 4.0. The OpenBible.info cross-reference data from which the TSK
benchmarks derive is available from OpenBible.info under its own terms.
