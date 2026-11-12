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
- `hebrews_psalms_verbatim_29.csv` — the hand-curated list of 29 verbatim
  Hebrews x Psalms quotations (article §3.2 and the verified-quotation
  benchmark), one row per pair with the Hebrews verse, the LXX Psalm verse
  and a short English gloss. Curated by hand from standard listings of New
  Testament quotations of the Psalms on 2026-05-15, after the weight sweeps
  of that day had ended. Fifteen of the 29 are among the 124 pairs of
  `tsk_hebrews_psalms_gold_124.csv`. The experimental thematic sweeps
  (`run_optimization_thematic.py`, `VERBATIM_GOLD_PATH`) read this file as a
  constraint. Added to the release 2026-11-11. Checked against Nestle-Aland
  28, Appendix III (loci citati vel allegati), s.v. Psalmi, on 2026-11-11 by
  the method used for the Romans-Isaiah list: 28 of the 29 pairs are direct
  citations there (italic entries, grouped Psalm ranges covering each verse),
  and the one exception, Hebrews 10:13 with Psalm 109:1 (110:1 in the Hebrew
  numbering), is listed as an allusion at Hebrews 10:12.
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

- `hebrews_psalms_top50_adjudicated.csv` — the top 50 rows of
  `hebrews_psalms_ranked_10000.jsonl` with a category for each pair
  (article §4.2 and its precision figure), added 2026-09-04. Categories:
  Q = documented quotation of the cited psalm, including re-quotations of
  the same verse at other points in Hebrews and verse-boundary spillover;
  A = unmarked allusion to the cited psalm; D = the same wording in a
  different psalm from the one Hebrews is quoting; F = formulaic or
  coincidental overlap. Counts: Q 30, A 3, D 6, F 11. Citation status was
  checked against Nestle-Aland 28, Appendix III; the `basis` column gives
  the reason for each assignment. Three rows (ranks 39, 42, 50) have an
  empty `quotation_run_length`: those pairs carry no quotation-channel run
  and reached the top 50 on the lemma and sound channels.

These outputs carry references and scores; the two JSONL files contain no
text and redistribute nothing.

Note on run-to-run variation: the V6 fusion search parallelizes across
worker processes, and tie-adjacent ranks can shift by a pair or two
between runs. Against `tsk_hebrews_psalms_gold_124.csv`, this release's
Hebrews-Psalms run finds 18 of 124 in the top 100; the article's
development-sequence table, measured on earlier runs, reports 17. The
held-out Romans-Isaiah run is the single run the article reports and is
not subject to this caveat.

- `hebrews_psalms_benchmark124_shared_runs.csv` — for each of the 124
  broad-benchmark pairs, the longest run of consecutive shared words and of
  shared lemmas between the Hebrews verse and the Psalm verse, in the Sahidic
  texts and in the Greek (Swete's Septuagint for the Psalms, the SBL Greek New
  Testament for Hebrews), with the vote count
  and whether the pair is on the hand-curated list of verbatim quotations
  (article §3.2). Added 2026-11-11, produced by
  `scripts/measure_benchmark_shared_runs.py` from the production lemma caches.
  94 of the 124 pairs share no run of three or more words in either language.
  Words are compared lower-cased with punctuation tokens dropped; Greek verses
  are matched by chapter and verse. No text is included.

- `besa_wordnet_2026-11-11.json`, `besa_psalms_ranked_2026-11-11.json`,
  `besa_psalms_ranked_2026-11-11_no_dictionary.json`,
  `besa_psalms_ranked_2026-11-11_latin_epic_weights.json` — the search of
  Besa's Letters (156 lines) against the Sahidic Psalms (2,531 lines) on the
  deployed code of 2026-11-11 (article §5), 5,000 ranked results, run with
  the default Coptic weight profile, again with the dictionary channel (the
  Coptic Wordnet synonym pairs) turned off, and again under the latin_epic
  profile, whose weights are the defaults the first run of this comparison
  used on 2026-05-14. The summary file holds the channel firing counts in the
  5,000 and in the top 100 for each run, the dictionary firings by rank band,
  the pairs present only with the channel on, and the overlap of the top 20
  and the top 100 between the runs. On the deployed code the dictionary
  channel fires in 1,721 of the 5,000 results, 15 of them in the top 100, and
  turning it off changes 727 of the 5,000 pairs, 0 of the top 20 and 4 of
  the top 100. Each ranked file lists [Besa line reference, Psalm verse
  reference, channels that fired, fused score]. No text is included. Produced
  by `scripts/besa_wordnet.py`. Added 2026-11-11.

- `greek_hebrews_psalms_two_pairs_latin_epic_2026-11-12.json` and
  `greek_hebrews_psalms_two_pairs_latin_epic_2026-11-12_scoring_table.jsonl` —
  the Greek Hebrews (SBL Greek New Testament) against the Greek Psalms
  (Swete's Septuagint) on the deployed code of 2026-11-12 (commit 4066a232)
  with the `latin_epic` weight profile, the search of article §3.3 as the
  code runs it today, 50,000 results kept. The summary file gives, for
  Hebrews 13:6 with Psalm 117:6 and with Psalm 117:7, the rank (35 and 121),
  the fused score as listed (26.11 and 15.28), the channels that fired, and
  the full scoring table: each channel's raw score and weighted contribution,
  the shared words counted for rarity, their geometric-mean IDF (1.04 over six
  words, 1.73 over two), the rarity multiplier (0.720 and 1.024), the
  quotation term that bypasses the multiplier (18.0 and 6.0), the convergence
  bonus, and the fused score reassembled from those terms (equal to the listed
  score). The scoring table file holds the same two rows as JSON lines. The
  profile today carries the quotation channel at weight 10, and the May 2026
  baseline run in `logs/greek_baseline_log.jsonl` had no quotation channel, so
  these figures describe today's code, not the May run. Produced by
  `scripts/greek_two_pairs_latin_epic.py`. Added 2026-11-12.
- `hebrews_psalms_semantic_ablation_2026-11-12.json` and
  `hebrews_psalms_semantic_ablation_2026-11-12_ranked.json` — Sahidic Hebrews
  against Sahidic Psalms on the deployed code of 2026-11-12 (commit 4066a232),
  10,000 ranked results, run twice with the shipped biblical-Coptic weights and
  once with the semantic weight set from 11.216 to 0 (the ablation of article
  §3.4, first run 2026-08-27 and then recorded as recall only). The summary
  file compares the three lists position by position and as sets (first
  position that differs, pairs shared in the top 10 to 10,000, pairs whose
  score changed) and gives the recall of the 124-pair benchmark and of the
  29-pair verbatim list in each run. The two shipped-weight runs are identical
  in all 10,000 rows and scores. With the semantic weight at 0 the order first
  differs at position 58, the top 10, 50 and 100 hold the same pairs, 498 of
  the top 500, 989 of the top 1,000 and 4,885 of the top 5,000 are shared,
  9,339 pairs appear in both lists of 10,000, and 501 shared pairs change
  score (largest change 3.83). Recall is the same in all three runs: 6, 18,
  18, 20, 21 and 27 of 124 and 9, 25, 26, 27, 28 and 29 of 29 within the top
  10, 50, 100, 500, 1,000 and 5,000. The ranked file holds
  the three lists as [Psalm verse reference, Hebrews verse reference, fused
  score]. No text is included. Produced by
  `scripts/semantic_ablation_lists.py`. Added 2026-11-12.

### logs/
Weight-optimization run logs (JSONL, one iteration per line) and the
best-weights snapshots for the sweeps described in the article: the
initial re-tuning sweep, the full-inventory re-optimization, the
quotation-channel baselines, the Greek diagnostic baseline, and the
experimental thematic sweeps. The experimental thematic profile in these
logs used the hand-curated quotation list `gold/hebrews_psalms_verbatim_29.csv` as a tuning constraint;
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

- `measure_benchmark_shared_runs.py` — produces
  `outputs/hebrews_psalms_benchmark124_shared_runs.csv` from the lemma caches
  of a Tesserae V6 checkout with the Coptic and Greek corpora (added
  2026-11-11).
- `besa_wordnet.py` — runs Besa's Letters against the Sahidic Psalms on a
  Tesserae V6 checkout with the Coptic corpus, with and without the dictionary
  channel and under two weight profiles, and writes the four `outputs/besa_*`
  files (added 2026-11-11).
- `greek_two_pairs_latin_epic.py` — runs the Greek Hebrews against the Greek
  Psalms on a Tesserae V6 checkout with the Greek corpus under the `latin_epic`
  profile and writes the two `outputs/greek_hebrews_psalms_two_pairs_*` files,
  re-executing the two scoring functions of `backend/fusion.py` from their own
  source with recording lines so that each channel's score and the rarity
  multiplier of the two pairs are the ones the code computed (added
  2026-11-12).
- `semantic_ablation_lists.py` — runs Sahidic Hebrews against Sahidic Psalms on
  a Tesserae V6 checkout with the Coptic corpus twice with the shipped weights
  and once with the semantic weight at 0, and writes the two
  `outputs/hebrews_psalms_semantic_ablation_*` files (added 2026-11-12). It sets
  the weights on the profile itself, because the search's `channel_weights`
  argument is the web form's path and caps each weight at 20, below the shipped quotation
  and sound weights.

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
