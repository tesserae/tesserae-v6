# Data operations on production

The live site's state is code (this repository, deployed from `main`) plus
data that is not in git: the inverted indexes, the lemma and frequency
caches, the passage index, the translation maps, cached results. Changes to
that data are made by scripts under `scripts/corpus/`, each with a dry run
by default, a dated backup beside the file it replaces, and a copy-and-
rename swap so the live app never reads a half-written file. This file
lists every such operation, newest first, with the script and the backup
name. CHANGELOG.md carries the one-line summary; the detail is here.

Conventions
- Run as the deploy user from the production root with the production venv,
  inside `systemd-run --user --scope -p MemoryMax=<n>G`.
- One heavy job at a time. Never `pkill -f`.
- After any swap: `touch tesseraev6_flask.wsgi` so the workers reopen files.
- Verify with the reference tests in `tests/search_reference_tests.md`
  ("arma virum" lemma search: 324 distinct loci as of 2026-09) and a search
  that exercises the store changed.
- Files owned by the web app's account cannot be opened for writing; write
  beside them and rename over them (the directory allows it).
- Stamp backups to the second; a rerun must never overwrite the first
  run's backup.

## 2026-09-13 Lucan correction and Lucretius edition change applied to the stores
- What: after the text files changed in git (Lucan whole file: six lines;
  Lucretius: whole file retagged "lucr. N.L", six book files regenerated
  from it), the eight texts' lemma caches were rebuilt, their entries
  replaced in the Latin index (which rebuilds document frequency
  canonically), the passage index's refs for the whole Lucretius renamed
  and the book works' line texts replaced, the Lucretius translation map's
  Perseus-aligned key family renamed with the Latin Library family
  dropped, cached results naming the texts deleted, and the Latin
  rare-bigram cache rebuilt.
- Scripts: `scripts/batch_lemma_cache.py la`;
  `scripts/corpus/add_texts_to_index.py --replace ...` on a copy, then swap;
  `scripts/corpus/apply_lucretius_lucan_editions.py --apply`;
  `scripts/corpus/rebuild_bigrams.py la`.
- Backups: `la_index.db.bak-editions-<stamp>`, `window_texts.db.bak-editions-<stamp>`,
  `descriptions.jsonl.bak-editions-<stamp>`, `la__lucretius.de_rerum_natura.json.bak-editions-<stamp>`,
  `la_bigrams.json.pre-rebuild-<stamp>.bak`.
- Note: the six Lucretius book works keep their passage windows and locus
  ranges; the Perseus and Latin Library lineation differ by a few lines at
  book ends, so a handful of lines at a book's end may fall outside the
  last window until those windows are rebuilt.
- Checks: reference test 324; Lucretius 1.1 in line search, passage lines
  and the Reader under the new tag; a Lucretius translation lookup; Lucan
  1.445 reads "Teutates" in the Reader.

## 2026-09-13 Document frequency: canonical rule restored
- What happened: the stale-entry drop of 2026-09-12 recomputed
  `lemma_doc_freq` with a plain COUNT(DISTINCT text_id), which counts every
  file, so a word in a work held whole and by book counted once per file
  ("et" in 1,656 Latin documents). The canonical builder
  (`scripts/build_inverted_index.build_lemma_doc_freq`, restored 2026-08-29)
  collapses book files to their base work, matching the app's run-time
  fallback (`_base_filename_expr` in `backend/blueprints/hapax.py`).
- Fix: both Latin and Greek tables rebuilt on copies with the canonical
  builder and swapped in (Latin 782 works, Greek 853 works). An interim
  rebuild earlier the same day used a nearby rule (whole files plus orphan
  book files counted singly: Latin 812, Greek 900) and was superseded.
- Scripts: `scripts/corpus/rebuild_docfreq.py --language <lang> --apply`
  (now a thin wrapper around the canonical builder);
  `scripts/corpus/drop_stale_index_entries.py` now calls the same builder.
  Rule for the future: any script that deletes from or rebuilds
  `lemma_doc_freq` must call `build_lemma_doc_freq`.
- Backups: `*_index.db.bak-docfreq-20260913` (interim) and
  `*_index.db.bak-docfreq-<stamp>` (canonical swap).
- Checks: reference test 324; rare-words comparison returns; sample df
  values fall to the work counts.
- Why the counts differ from the bigram caches: the bigram builder counts
  each orphan book file (a work with no whole-work file, such as the
  Greek Anthology's sixteen books) as its own document, so it reports
  Latin 812 and Greek 900; the document-frequency builder collapses those
  to their base work, so it reports Latin 782 and Greek 853. Both are
  one-per-work rules; they differ only on orphan books.

## 2026-09-12 Rare-bigram caches rebuilt
- What: `cache/bigrams/grc_bigrams.json` (610 to 900 documents) and
  `la_bigrams.json` (899 to 812) rebuilt from the lemma caches.
- Script: `scripts/corpus/rebuild_bigrams.py <lang>`.
- Backups: `*_bigrams.json.pre-rebuild-20260912*.bak`.
- Checks: rare-pairs comparison in each language returns.

## 2026-09-12 Stale index entries dropped
- What: 33 Greek and 1 English `texts` rows (with their lines and
  postings) whose files no longer exist; `lemma_doc_freq` recomputed.
- Script: `scripts/corpus/drop_stale_index_entries.py --language <lang>`.
- Backups: `grc_index.db.bak-stale-20260912-1425`, `en_index.db.bak-stale-20260912-1427`.
- Checks: Greek line search returns Homer for the Iliad's first line.

## 2026-09-12 Malformed reference tags repaired in every store
- What: after #371 repaired 54 text files, the same rule was applied to
  the lemma caches (refs and file hash), both indexes (lines and
  postings), the passage index (descriptions.jsonl, window_texts.db), 41
  translation maps and one cached fusion result.
- Script: `scripts/corpus/repair_ref_tags.py --root <prod> --list
  scripts/corpus/repair_ref_tags_2026-09-12.txt --lemma-cache --index
  --passage-index --translations --fusion-cache --apply`.
- Backups: `*.bak-reftags-20260912*` beside each file. The first Greek
  index backup was overwritten by a rerun (fixed in #372); the pristine
  fallback is `grc_index.db.pre-ctesiphon-20260910.bak`.
- Note: one duplicate heading line dropped from the Latin index (Peter
  Riga, Aurora part 18).
- Checks: reference test 324; Sallust clean in line search, passage lines,
  Theme Search and the Reader; Plautus translation lookup available.

## 2026-09-10 Curtius batch and duplicate retirement
- What: texts of #360 added to the Latin and Greek indexes, lemma caches
  and bigram caches; 9,771 passage windows described and appended in
  lockstep; 45 duplicate texts (#362) removed from indexes and caches and
  archived outside the repository; Aeschines Against Ctesiphon (#364)
  reindexed and its windows rebuilt.
- Scripts: `scripts/corpus/add_texts_to_index.py`,
  `scripts/corpus/apply_passage_rows.py`, `scripts/batch_lemma_cache.py`.
- Record: the coordinator log kept with the research notes.

---

# Backfill: 2026-08-25 to 2026-09-09

Reconstructed on 2026-09-13 from the session records and the merged pull
requests of the period, before this file existed. Where a backup name or a
count was never recorded, the entry says so. Newest first. The "Not
established" list at the end names operations that were referenced but
could not be pinned down, and two that turned out never to have reached
production.

## 2026-09-04 Coptic data release: adjudicated classification added
- What: the public Coptic article data release gained one file, the top 50 rows
  of the released Hebrews x Sahidic Psalms run, each hand-classified (30
  quotations of the cited psalm, 3 unmarked allusions, 6 same-wording matches
  in a different psalm, 11 formulaic or coincidental overlaps). The article's
  precision figure is computed from this file. The release zip was rebuilt and
  the Downloads page link updated.
- Scripts: none (data and one link change).
- Backups: the old release zip was removed, not backed up.
- Checks: not recorded beyond the file being present in the rebuilt zip.

## 2026-09-02 Coptic, Hebrew and passage indexes published; vernacular window text repaired
- What: the public reproducibility data release, previously offering only the
  Latin and Greek indexes, gained `cop_index.db`, `he_index.db`,
  `syntax_coptic.db`, and the passage index (`ids.json`, `embeddings.npy`,
  `descriptions.jsonl`). The passage-index release deliberately omits
  `window_texts.db` (so Theme Search ranks correctly on a fresh clone but
  returns no passage text until that file is rebuilt locally) and is filtered
  to the five languages whose `.tess` sources ship in the repository (Latin,
  Greek, English, Coptic, Hebrew); production's own passage index also holds
  Persian, Urdu and Arabic windows from a separate workspace, not published.
  Separately, `window_texts.db` on production was found to be missing rows for
  all but one of the 6,467 vernacular-tier windows (Italian, Middle High
  German, Old French, see the 2026-08-31 entry below): the batch that
  described and embedded them had skipped the step that populates this table.
  Rebuilt from each window's own line range in the indexed `.tess` source and
  applied to production.
- Scripts: not named for the release manifest step; the window-text repair
  used a script that rebuilds rows from the index's own line ranges (not
  named precisely in the source record).
- Backups: a backup of `window_texts.db` was taken before the repair (name not
  recorded in the source).
- Checks: 6,466 of 6,467 vernacular windows recovered (one window's references
  did not resolve against its source file and was left alone rather than
  guessed at); the published archive was confirmed to cover the languages the
  manifest and Downloads page claim.
- Note: the index-file publication is a public download, not a change to
  production's own working copies of those files.

## 2026-09-01 Satirists batch: Nigel Wireker, Johannes de Hauvilla, Carmina Burana
- What: three Latin texts added (Nigel Wireker's Speculum stultorum, Johannes
  de Hauvilla's Architrenius, a 31-poem subset of the Carmina Burana), 8,462
  lines. `la_index.db` grew from 1,680 to 1,683 texts (932,480 to 940,941
  lines); passage index grew from 623,196 to 625,167 windows (926 + 1,013 + 32
  per work). A structural defect found after the initial merge (three Carmina
  Burana poems had multiple numbered sub-items fused into single lines) was
  corrected, which required rebuilding that one text's lemma cache, its index
  postings, and its 25 passage windows (rebuilt as 32).
- Scripts: `scripts/corpus/add_texts_to_index.py`,
  `scripts/batch_lemma_cache.py`, `scripts/corpus/build_batch_windows.py`,
  `scripts/corpus/describe_windows.py`, an apply script built on the same
  lockstep-append pattern used in later batches (not yet named
  `apply_passage_rows.py` at this point in the batch sequence).
- Backups: `la_index.db.pre-satirists-batch-20260901.bak`,
  `la_index.db.pre-cb-fix-20260901.bak`, `la_bigrams.json.pre-satirists-batch-20260901.bak`,
  window_texts.db and passage-index files backed up before each write
  (`*.bak-satirists-batch-20260901`, `*.bak-cbfix-20260901`).
- Checks: reference test (lemma "arma virum", 324 distinct loci) passed before
  and after every index change. A single-word lemma query for the new text's
  title character ("Burnellus") returned zero through the live workers
  immediately after an index swap until the wsgi file was touched, confirming
  the documented worker-reload requirement applies to lemma queries and not
  only to the reference test.
- Note: two English translation searches (Nigel Wireker, Architrenius) came up
  empty after a genuine search for public-domain editions; the Carmina Burana's
  one usable public-domain translation (Symonds 1884) covers only one of the
  31 imported poems and was not aligned.

## 2026-08-31 to 2026-09-01 Medieval Latin batch: Alan of Lille, Walter of Chatillon, Bernard Silvestris, Venantius Fortunatus, Cassiodorus
- What: five Latin works added (Alan of Lille's Anticlaudianus and De planctu
  Naturae, Walter of Chatillon's Alexandreis, Bernard Silvestris's
  Cosmographia, Venantius Fortunatus's Carmina, Cassiodorus's Variae and
  Institutiones), full pipeline (index, lemma cache, passage windows,
  description, embedding). `la_index.db` grew to 1,673 texts (906,485 lines)
  by the batch's own accounting; the passage index moved from 617,137 (its
  count after the vernacular batch below) toward roughly 623,198 by the time
  the next batch started, though the medieval batch's own added-window total
  was not stated as a single figure in the session record.
- A pre-existing duplicate was found and removed during this batch: a stray
  text (the Variae preface only, 18 lines, from an old bulk import with no
  source metadata) had been served alongside the new comprehensive Cassiodorus
  Variae file. It was removed from the live `.tess` tree, the inverted index,
  the lemma cache, and the passage index (2 windows dropped).
- Scripts: `scripts/corpus/add_texts_to_index.py`,
  `scripts/batch_lemma_cache.py`, `scripts/corpus/build_batch_windows.py`,
  `scripts/corpus/describe_windows.py`, `scripts/corpus/apply_passage_rows.py`.
- Backups: `la_index.db.pre-batch3-20260830.bak` is named in the source for an
  adjacent batch; the medieval batch's own index and passage-index backups
  follow the same `*.bak-<name>-20260901` convention but exact filenames were
  not all captured in the record read for this backfill. The stray-duplicate
  removal used `la_index.db.bak-strayfix-20260901`.
- Checks: reference test (324 distinct loci) passed at each checkpoint,
  including before and after the stray-duplicate removal.
- Note: one work (Bernard Silvestris's Cosmographia) carries disclosed
  19th-century OCR residue, reviewed and shipped with two individual lines left
  as-found rather than guessed at. No public-domain English translation exists
  for any of the five works; all searches for one came up empty.

## 2026-08-31 to 2026-09-01 Vernacular theme-search tier: Dante, Chanson de Roland, Nibelungenlied
- What: three medieval vernacular works added to the passage index only (the
  same tier Persian and Urdu occupy: described, embedded, and searchable
  through Theme Search and Similar Passages, but not lemmatized and not part
  of ordinary lexical search). Dante's Commedia (Italian, 3,317 windows),
  the Chanson de Roland (Old French, 933 windows), and the Nibelungenlied
  (Middle High German, 2,217 windows), 6,467 windows total. The passage index
  grew from 610,670 to 617,137 windows, described from the original-language
  text (a small per-language check confirmed the describing model reads all
  three reliably, so no translation-route fallback was needed as it is for
  Coptic).
- Scripts: `scripts/corpus/build_batch_windows.py`,
  `scripts/corpus/describe_windows.py`, `scripts/corpus/apply_passage_rows.py`.
- Backups: not individually named in the source beyond the standard
  copy-before-write convention used by `apply_passage_rows.py`.
- Checks: all-languages Theme Search for a query about a poet guided through
  the underworld returned results in Latin, Greek, Italian (the Inferno),
  English, Persian and Urdu in rotation; a language-restricted search for
  Italian returned the Inferno directly. 179 frontend tests and the backend
  description tests passed.
- Note: as first built, `window_texts.db` was never populated for these
  windows (see the 2026-09-02 entry above for the repair). The Latin corpus
  already held a Neo-Latin verse translation of the Commedia, so the poem
  became searchable in the original and in Latin translation, a genuine
  cross-lingual pair.

## 2026-08-31 Dual-phrasing description pilot
- What: a pilot adding a generic paraphrase (every proper name replaced by a
  role, e.g. "a parent sacrifices a child") to the embedding text of 41,634
  passage-index windows drawn from eight name-heavy work prefixes (Hebrew
  Bible, Septuagint, New Testament, Bohairic and Sahidic Coptic biblical
  texts, the World English Bible, Philo, Josephus), to help generically
  phrased Theme Search queries reach windows whose descriptions lead with
  proper names. `embeddings.npy` was row-edited in place for all 41,634
  windows and `descriptions.jsonl` rewritten with the added field; no windows
  were added or removed (610,670 before and after).
- Scripts: a purpose-built generation and apply pair modeled on
  `scripts/corpus/apply_passage_rows.py`'s replace mode (not committed to the
  repository as of this backfill; logged as a pilot).
- Backups: `embeddings.npy.bak-dualnaming-20260831`,
  `descriptions.jsonl.bak-dualnaming-20260831` (copy-if-absent).
- Checks: reference test (324 total, 22 exact) passed, as expected since only
  passage-index files were touched. Measured directly against the embeddings
  (bypassing the API, whose result composition varies with page size): a
  random sample of 500 touched windows improved on average against two probe
  queries (mean similarity gain +0.0088 and +0.0033), with the largest gains
  among previously poorly matched windows and a small dilution effect on
  windows that were already strongly matched.
- Note: NC's own review of the result recommended a design change (a separate
  generic-phrasing vector rather than one blended embedding) before any
  full-corpus rollout; this pilot was not extended to the rest of the corpus
  within this window.

## 2026-08-30 Hebrew clitic-spacing fix
- What: seven Hebrew books (1 and 2 Samuel, 1 Kings, 1 Chronicles, Daniel,
  Ruth, one line of Deuteronomy) had shipped with clitic prefixes as separate
  space-delimited tokens, unlike the rest of the Tanakh's joined Masoretic
  orthography, which mismatched token-based search channels across book
  pairs. 3,655 lines were rejoined, verified as a no-op on the other 32 books.
  Following data steps: Hebrew inverted index rebuilt and embeddings
  recomputed for the seven affected books.
- Scripts: `scripts/corpus/fix_hebrew_clitic_spacing.py`,
  `scripts/build_inverted_index.py --language he --force`.
- Backups: not recorded in the source beyond the standard index-rebuild
  convention.
- Checks: hard per-line validation that non-space characters and reference
  tags were unchanged and that no single-consonant token remained; reference
  test and the held-out doublet benchmark were to be re-run after deploy.

## 2026-08-30 Latin corpus batch 3: Aquinas and Erasmus
- What: four Latin works added (Aquinas's Summa Theologiae Prima Pars and five
  eucharistic hymns, Erasmus's Moriae Encomium and a selection of 18
  Colloquia), 6,257 lines. `la_index.db` grew from 1,669 to 1,673 texts
  (906,485 lines). Passage index grew from 609,216 to 610,670 windows (1,454
  windows, including 50 hymn windows re-described after a review caught wiki
  markup residue in the converted hymn text).
- Scripts: `scripts/corpus/add_texts_to_index.py`,
  `scripts/batch_lemma_cache.py`, `scripts/corpus/build_batch_windows.py`,
  `scripts/corpus/describe_windows.py`, `scripts/corpus/apply_passage_rows.py`.
- Backups: `la_index.db.pre-batch3-20260830.bak`, passage-index files backed
  up under the batch's own `*.bak-batch3-20260830` convention.
- Checks: reference test (324 total, 22 exact) passed before and after the
  index swap and again after the final pull. Live searches on the new
  content-word text (proper-name and theme queries) returned correctly
  attributed results.
- Note: translations for three of the four works were deployed the same day
  (see the translation entries below); the hymns' translation was skipped, no
  public-domain non-paraphrase version was found.

## 2026-08-30 Latin corpus batch 2, Lactantius Placidus repair, Justin reference repair
- What: (1) `lactantius_placidus.in_statii_thebaida_commentum.tess` was found
  to have lost every capital letter in an earlier conversion pass; re-derived
  from the same source edition with capitals (and the restored all-capitals
  Statius quotations) intact, refs unchanged, 4,243 units, index postings for
  this text rose from 59,075 to 73,314, and its 988 passage windows were
  re-described. (2) Nine further Latin works added (Fronto's Epistulae,
  Nemesianus's Eclogae/Cynegetica and pseudo-Nemesianus's De Aucupio,
  Symmachus's Epistulae, Abelard's Historia calamitatum and Epistolae,
  Gregory the Great's Dialogi and Regula pastoralis), 8,105 lines.
  `la_index.db` grew to 1,669 texts (900,228 lines). (3) A defect from batch 1
  was found and fixed: Justin's Epitome had books 3 to 44 mislabeled, with a
  roman-numeral remnant left in the reference tag; corrected from each unit's
  own embedded numeral, requiring a re-run of the lemma cache, index entry,
  and passage windows for that one text. Passage index grew from 607,041 to
  609,216 windows across these three changes.
- Scripts: `scripts/corpus/add_texts_to_index.py`,
  `scripts/batch_lemma_cache.py`, `scripts/corpus/build_batch_windows.py`,
  `scripts/corpus/describe_windows.py`, `scripts/corpus/apply_passage_rows.py`,
  a dedicated Lactantius-repair script, and `scripts/corpus/batch2_to_tess.py`
  for the new-work conversions.
- Backups: `la_index.db.pre-batch2-20260830.bak`,
  `la_index.db.pre-justinfix-20260830.bak`, `la_bigrams.json.pre-batch2-20260830.bak`,
  passage-index files under `*.bak-batch2-20260830`.
- Checks: reference test (324 total, 22 exact) passed at every checkpoint (four
  separate checks that day). A live search for a phrase specific to the
  repaired Lactantius text confirmed the restoration; NC's own reported
  Similar Passages result on the affected passage was verified fixed live.
- Note: two translation efforts were refused rather than shipped with a known
  wrong-passage risk (Fronto against Haines' English, Gregory's Dialogi
  against a blackletter-headed scan); both are logged as open with a documented
  path forward.

## 2026-08-30 LXX orientation descriptions added; Torah and Kingdoms confirmed already complete
- What: a task to import the Septuagint's Torah and Kingdoms books found they
  were already complete in production (55 books, added 2026-08-22, before this
  backfill's window, commit `011a38e`), already indexed, theme-searched,
  translated (Brenton 1851), and routed through the Hebrew-to-Greek pivot. The
  only genuine gap found and acted on: `data/text_descriptions.json` had no
  Greek section at all; nine orientation descriptions were added for the five
  Torah books and the four Kingdoms books.
- Scripts: none (a single data-file addition).
- Backups: not applicable (additive edit to a tracked file, not an index
  rebuild).
- Checks: reference test (324, matching the standing baseline) passed after
  deploy; the new descriptions were confirmed served through the text
  descriptions endpoint.
- Note: two gaps were found and reported but not acted on, both requiring a
  separate decision: the Septuagint's own Ecclesiastes is absent from the
  corpus entirely (a similarly named text is Sirach, a different book), and
  the Greek rare-bigram cache was found stale (610 documents against a
  current index of over 1,300 Greek texts), predating and far broader than
  this task.

## 2026-08-29 to 2026-08-30 Latin corpus batch 1: Varro, Hyginus, Justin, Velleius, Frontinus, Mela, Sidonius, Isidore, Petrarch
- What: thirteen new Latin files across nine authors added, 20,482 lines
  (Varro's De lingua Latina and Res rusticae, Hyginus's Astronomica and
  Fabulae, Justin's Epitome, Velleius, Frontinus's Strategemata and De aquis,
  Pomponius Mela, Sidonius's Epistulae and Carmina, Isidore's Etymologiae,
  Petrarch's Africa). A pre-existing mislabeled duplicate was found and
  removed in the same batch: Petrarch's Africa had already been present under
  a wrong author and work name, attributed to a different author entirely,
  and missing one whole book; it was removed from the live text tree, the
  inverted index (42,620 postings), the lemma cache, and (at the passage-index
  apply step) 1,569 passage windows, replaced by the new complete,
  correctly-attributed file. `la_index.db` grew from 1,648 to 1,660 texts
  (897,599 lines). Passage index moved from 603,827 to 607,041 windows
  (net of 1,569 removed and 4,783 added). Bigram cache incremented for the 13
  new texts (858 to 871 documents, noted in the session record as still a
  stale snapshot of the full corpus).
- Scripts: `scripts/corpus/latinlibrary_to_tess.py`,
  `scripts/corpus/wikisource_africa_to_tess.py`,
  `scripts/corpus/validate_tess.py`, `scripts/batch_lemma_cache.py`,
  a precursor to `scripts/corpus/add_texts_to_index.py` (the batch-1 pipeline
  drivers were later rewritten as the named, reusable scripts used in batch 2
  onward), `build_inverted_index.build_lemma_doc_freq`.
- Backups: `la_index.db.pre-batch1-20260830.bak`, `window_texts.db.bak-batch1-20260830`,
  `la_bigrams.json.pre-batch1-20260830.bak`.
- Checks: reference test (324 total, 23 then 22 exact after the duplicate's
  removal) passed before and after the index swap. Theme Search and fusion
  smoke tests on the new texts returned sensible results (a Scipio-and-Hannibal
  query surfaced the new Petrarch text alongside Livy's account of Zama).
  Confidence probe sets scored identically to the pre-append snapshot,
  confirming the larger corpus did not change Theme Search's calibrated
  behavior.
- Note: this batch's texts were the first to require GPU description as part
  of an ordinary corpus import, establishing the pipeline (windows, describe,
  embed, lockstep append) that every later batch in this backfill reused.

## 2026-08-29 (night) 233 previously unindexed passage windows appended
- What: 254 passage windows identified as never indexed were investigated;
  233 were appended (the passage index moved from 603,594, the count fixed at
  launch, to 603,827). The remaining windows (seven Coptic windows whose
  underlying translation range is a lacuna placeholder) were left unindexed by
  design, since describing dots of ellipsis had previously produced an
  invented description. Four pipeline defects were found and fixed while
  doing this: the embed service silently truncated batches larger than 32
  texts; the apply script's backup was being overwritten on every run rather
  than only on the first; a Coptic reference parser was reading only the last
  number of a multi-part reference tag, mis-scoping Esther verses; and any
  window with fewer than 15 real English words is now skipped rather than
  described.
- Scripts: a hardened version of the lockstep append logic (later formalized
  as `scripts/corpus/apply_passage_rows.py`).
- Backups: `.good-20260829` snapshots of the passage-index files, described
  in the source as freshly taken and verified before the append.
- Checks: lockstep verified (ids count equals embeddings count) before and
  after. A live search on a passage NC had flagged as missing confirmed the
  fix (a specific Coptic passage now correctly reports no indexed window,
  since the English for those lines does not exist).

## 2026-08-29 (evening) Livy translation realigned chapter-exact
- What: the Livy translation was rebuilt from a book-level blob alignment to
  1,758 chapter-exact units, using the complete Bohn translation sourced from
  three named 19th-century translators across four volumes. Coverage rose
  from 0.29 to 0.9995 of the work's reference tags.
- Scripts: not named in the source beyond "a parser" for the chapter-numbered
  source; the general alignment pattern is in `scripts/translations/`.
- Backups: not recorded (translation files are additive; the source does not
  describe a prior version being overwritten in place versus replaced).
- Checks: a proper-name agreement check scored 0.935 across 800 sampled name
  pairs; live-verified through the translation endpoint.

## 2026-08-29 Downstream fixes: document frequency restored, downloads symlink fixed, Coptic article data posted, passage query cap added
- What: (1) an earlier index-builder change had dropped the step that
  computes `lemma_doc_freq`; restored, and the table rebuilt for all five
  languages then in production (Coptic and Hebrew had none at all; Latin's
  existing counts were confirmed not stale). (2) `/static/downloads` links had
  been serving the single-page application's fallback page instead of the
  requested file for some time, because the front-end web server served the
  built site directly and no `dist/static` path existed; fixed with a
  deploy-ensured symlink. (3) the Coptic article's data release was posted
  under the Downloads page. (4) the Reader's Verbal Parallels tab, when sent a
  multi-line selection, was reduced to its rarest lemmas above a length cap
  (12 lemmas) to avoid a near-two-minute query; disclosed in the response and
  the panel.
- Scripts: the index-builder's document-frequency step (part of
  `scripts/build_inverted_index.py`).
- Backups: not recorded.
- Checks: reference test (324) unchanged by the passage-query cap change
  (short queries are unaffected by construction); the downloads fix was
  verified by a successful file download after deploy.

## 2026-08-29 Ancient Latin translation sweep: 145 files
- What: a broad sweep of Latin authors born or active before 600 CE for
  public-domain English translations, yielding 145 new translation files
  across Silius Italicus (books 1 to 8 only, the remainder blocked by
  copyright until 2030), Propertius (both file families), Cicero (letters and
  ten treatises), Terence (six plays), Seneca's prose (epistles and twelve
  further works), Lactantius (seven works), John Cassian, Sulpicius Severus,
  Tertullian, Cyprian, Minucius Felix, Arnobius, Commodian, Ambrose (partial),
  Claudian, Juvenal, Persius, the Appendix Vergiliana, Ausonius, part of
  Paulinus of Nola, Pliny (books 1-5), Suetonius, Petronius, part of Horace,
  Ovid's Remedia, five Boethius opuscula, Nepos, and Eugippius. Measured Latin
  translation coverage rose from 37.2% to 47.6% of corpus lines by the
  session's own counting convention (+62,596 lines in one day).
- Scripts: `scripts/translations/align_silius.py`, `align_propertius.py`,
  `align_cicero_letters.py`, `align_cicero_treatises.py`, `align_terence.py`,
  `align_seneca_epistles.py`, `align_seneca_prose.py`, `align_anf.py`,
  `align_misc_prose.py`, `align_claudian.py`, `align_juvenal.py`,
  `align_appendix.py`, `align_ausonius.py`, `align_remedia.py`,
  `align_boethius.py`, `align_nepos.py`, `align_eugippius.py`.
- Backups: not recorded (translation files are additive; none replaced an
  existing file in this sweep).
- Checks: reference test (324) confirmed unaffected. Each work carries its own
  coverage and proper-name agreement figures in the corpus scope
  documentation; a sample of at least one passage per work was spot-checked
  live through the translation endpoint against the source.
- Note: a long list of authors were checked and found to have no usable
  public-domain English translation (Prudentius, Manilius, Dracontius, and
  others); recorded as open rather than silently skipped.

## 2026-08-29 Latin and Greek translation push: 89 files
- What: Martial (both file families, 16 files), Jerome's Epistulae (partial by
  design, since the source anthology itself abridges many letters), Augustine
  (43 files across 36 works), Philo (27 of 28 works), and Athenaeus (using two
  complementary public-domain sources for books 1-10 and 11-15). Measured
  coverage: Latin 32.1% to 37.2% (+30,344 lines), Greek 58.1% to 61.0%
  (+10,916 lines).
- Scripts: not named individually in the source beyond the general
  `scripts/translations/` alignment pattern; a proper-name matching
  improvement (a consonant-skeleton fallback) was added to the shared
  name-check code as part of this push.
- Backups: none recorded (all additive).
- Checks: reference test (324) unaffected. One spot-check passage per work
  verified live through the translation endpoint.

## 2026-08-28 to 2026-08-29 Translation book-opening repair
- What: Loeb-aligned translations (Statius's Thebaid and Achilleid, Ovid's
  Tristia and Ex Ponto) had systematically lost the opening ~15-20 lines of
  each book, because the source scans' unheaded book-title pages were not
  being captured by the aligner. Recovered by scanning source page images
  directly for each book's true opening and validating against shared proper
  names. Thebaid recovered 12 of 12 books, Achilleid 2 of 2, Tristia 8 of 11,
  Ex Ponto 4 of 5 (the remaining cases are honest refusals where the source
  page is missing or unmatchable). A related defect was also fixed: an
  earlier Statius alignment had glued several unheaded stretches into the
  preceding translated unit, serving readers a mix of English, Latin, and
  editorial apparatus; five oversized units were retrimmed.
- Scripts: a dedicated book-opening repair script (path not fully given in
  the source).
- Backups: `.backup-20260829-openings` (translation files).
- Checks: live-verified at one passage per affected work (Thebaid 1.1,
  Achilleid 1.1, Tristia 1.1.1, Ex Ponto 1.1.1).
- Note: the Silvae translation was deferred at this point (see the separate
  full realignment below); its gaps went beyond missing openings.

## 2026-08-27 Statius (Thebaid, Silvae, Achilleid) translated from Mozley 1928
- What: the largest remaining gap in Latin translation coverage, 14,783 lines
  with no English at all, filled using Mozley's 1928 Loeb (public domain by
  date). 10,991 lines translated. Coverage by work: Thebaid 80.1%, Achilleid
  88.6%, Silvae 56.5%. The alignment method used the Loeb's own running page
  headers (book and line range, printed in ordinary type) rather than
  attempting to read the much less reliable marginal line numbers; a first
  version that trusted contiguity between pages was found to stretch some
  English across the wrong lines when a header was lost, and was replaced
  with a rule that judges each page's header on its own plausibility first.
- Scripts: not named in the source beyond the general
  `scripts/translations/` pattern.
- Backups: none recorded (new file).
- Checks: proper-name agreement 0.814 (Thebaid), 0.798 (Achilleid), 0.783
  (Silvae); spot-read against the Latin at several passages before
  installing.
- Note: this alignment was itself corrected on 2026-08-29 by a fuller
  realignment of the Silvae specifically (see the entry above dated within
  the 2026-08-29 Ancient Latin sweep account; the full Silvae fix, raising
  coverage to 1.0, is recorded separately as it landed slightly later in the
  same week).

## 2026-08-28 Translations background job: coverage wording, SBLGNT remap, Quintus/Apollonius/Ovid
- What: (1) the Help page's translation-coverage sentence was corrected. (2)
  27 existing WEB-English translation files for the Greek New Testament,
  previously keyed to a legacy reference scheme, were remapped onto the
  SBLGNT's own reference tags (the text added to production 2026-08-21,
  before this backfill's window), reaching coverage 1.0000 on all 27 books
  after resolving four genuine versification differences. (3) new translation
  files were added for Quintus of Smyrna, Apollonius Rhodius, and Ovid's
  Fasti, Tristia, and Ex Ponto (7 files), using named 19th- and early
  20th-century public-domain translations.
- Scripts: `scripts/translations/remap_sblgnt.py`, `align_theoi.py` (Quintus,
  Apollonius), `align_ovid.py` (Fasti, Tristia, Ex Ponto).
- Backups: none recorded (all additive translation files).
- Checks: SBLGNT remap spot-verified at five passages (John 1:1, Romans 3:23,
  Acts 1:1, Revelation 22:21, Matthew 5:3); the new alignments were
  spot-checked by eye against the source at several passages per work.
- Note: this session also found that the Latin corpus held two duplicate
  copies each of Quintus of Smyrna and Apollonius Rhodius under different file
  names, flagged as a corpus-hygiene question rather than resolved at the
  time.

## 2026-08-27 Superseded Latin texts removed from the repository
- What: 86 Latin text files removed, an older, faulty patristic import (typos,
  truncated names, old spellings, inconsistent author-name forms) every one
  already superseded by a corrected counterpart added in an earlier
  2026-08-16 de-duplication. None of the 86 was present in the inverted index
  or the passage index at the time of removal (confirmed by direct count).
  Latin text count moved from 1,912 to 1,826 in the repository, matching what
  production was already serving.
- Scripts: not applicable (a git-level file removal, not a data-pipeline
  script).
- Backups: the removed files were kept in a repository subdirectory
  (`texts/la/_dedup_removed_20260816/`) and a copy was kept outside the
  repository as well.
- Checks: 79 of the 86 removed files were matched to their surviving
  counterpart by opening line, 7 by hand; a control query confirmed the
  corrected names remained indexed.

## 2026-08-25 Content search launch
- What: the passage index was built and shipped for the first time, 603,594
  windows across 1,849 works in seven languages (Latin, Greek, Persian,
  Coptic, Hebrew, Urdu, English, plus a small Arabic demo set withheld from
  any public release). The query encoder was split out to run as its own
  service rather than inside the web application. The eleventh fusion
  channel, quotation, which had been silently absent from production since
  June (a Coptic-support commit had shipped without a needed scoring module),
  was restored; this more than tripled recall on the Coptic benchmark then in
  use (R@100 from 0.040 to 0.145). A correction pass fixed 9,166 passage
  descriptions (of 151,484 checkable) that had invented named participants
  where a passage in fact named nobody, dropping the invented-name rate from
  6.1% to 0.1%; a separate metadata pass reduced the share of passages showing
  as undated (and therefore sorted last in every chronological result) from
  37.5% to 0.02%.
- Scripts: the passage-index build and describe pipeline as it existed at
  launch (the reusable, named scripts referenced throughout this document,
  such as `scripts/corpus/build_batch_windows.py` and
  `scripts/corpus/describe_windows.py`, were formalized in later batches
  building on this launch's pipeline).
- Backups: not recorded in the sources reviewed for this backfill; this
  predates the documented backup-naming convention used in later entries.
- Checks: reference test (arma virum, 324 distinct loci) passing was the
  baseline the whole build was measured against. Theme Search's confidence
  bands were fitted against 57 probe queries (91% accuracy) at launch and
  refit twice more in the following days (2026-08-27 and 2026-08-31) as probe
  sets grew and the index changed.
- Note: a known deployment hazard was identified the same day and is not yet
  fixed: `index.html` is served with no cache-control header, and the
  front-end server's fallback behavior for a missing bundle returns a normal
  success page, so a stale cached page can fail silently with a blank screen
  after a deploy. A save/restore script mitigates this around deploys; the
  underlying fix needs a web-server configuration change.

---

## Prior state (before this window, for context)

- **2026-08-22, Septuagint completed.** Commit `011a38e` added the Torah
  (Genesis, Exodus, Leviticus, Numbers, Deuteronomy), Joshua, Judges, Ruth, all
  four Kingdoms books (1-2 Samuel, 1-2 Kings), 2 Chronicles, 2 Esdras, 2-4
  Maccabees, Psalms of Solomon, and the Theodotion Daniel texts, bringing the
  Septuagint to 55 books, all indexed, theme-searched, and translated
  (Brenton 1851) at the time. Verified still complete and correctly routed
  during a 2026-08-30 task in this window (see that entry above).
- **2026-08-21, Hebrew launch.** The Hebrew Bible went live as a searchable
  text (prior to this backfill's window); full account in the project's
  existing Hebrew documentation.

---

## Not established

- **The 2026-08-27 Theme Search confidence refit** (production pull request
  referencing "the re-described index, which is already on production")
  plausibly refers to the same 9,166-description name-accuracy correction
  logged under 2026-08-25 above, but the source read for this backfill does
  not explicitly confirm the two are the same event, so they are logged
  separately rather than merged on an assumption.
- **The medieval Latin batch's own passage-window total** (Alan of Lille,
  Walter of Chatillon, Bernard Silvestris, Venantius Fortunatus, Cassiodorus)
  was not stated as a single figure in the session record reviewed; the
  passage index is known to have moved from 617,137 (after the vernacular
  batch) to approximately 623,198 (the figure in place just before the
  following batch's stray-duplicate cleanup), implying roughly 6,000 windows
  added, but this is inferred rather than directly recorded.
- **The 2026-09-05 Persian, Urdu and Arabic embedding run** (multilingual-e5
  embeddings computed for the full Persian, Urdu and Arabic corpus, about
  984,000 lines) ran on a separate development branch, explicitly recorded at
  the time as "nothing pushed, nothing in production." It is not a production
  data operation as of this backfill and is not entered above; noted here only
  because it was asked about directly.
- **The Ghalib edition retirement of 2026-09-07** (reducing three served
  editions of Ghalib's Diwan to one, in the Urdu index and passage index) was
  confirmed to have taken place in a separate development workspace, not
  production; the session's own note states production most likely needs no
  equivalent action, since the retired files were never merged to the main
  branch. Not a production data operation as of this backfill.
- **Exact backup filenames** for several translation-file deployments in this
  window were not recorded in the sources reviewed, beyond confirming that
  translation files are added rather than overwritten and that a mirrored
  development copy was kept in step with production.
- **A full rebuild of the Latin and Greek rare-bigram caches** was flagged as
  overdue at several points in this window (both caches remained snapshots of
  an earlier, smaller corpus throughout) but was not carried out until after
  this window closed.
