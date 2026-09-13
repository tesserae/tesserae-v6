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

## 2026-09-13 Document frequency, one document per work
- What: `lemma_doc_freq` in `data/inverted_index/la_index.db` and
  `grc_index.db` rebuilt over whole works plus book files that have no
  whole (the rule `backend/bigram_frequency.py` already used). Latin 812
  documents, Greek 900.
- Script: `scripts/corpus/rebuild_docfreq.py` (prepared on copies; the
  swap was done by hand with `cp`, `mv`, `touch`).
- Backups: `la_index.db.bak-docfreq-20260913`, `grc_index.db.bak-docfreq-20260913`.
- Checks: no df value rose; 110 Latin lemmas that occur only in Lucretius
  and Lucan book files left the table (callers treat a missing lemma as
  df 0); reference test 324; rare-words comparison returns.

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
