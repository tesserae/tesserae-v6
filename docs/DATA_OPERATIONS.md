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
  ("arma virum" lemma search: 324 distinct loci as of early 2026-09; 367
  as of 2026-09-20 after the Martial rebuild from its per-book files and
  the September retirements; the exact search returns 21) and a search
  that exercises the store changed.
- Files owned by the web app's account cannot be opened for writing; write
  beside them and rename over them (the directory allows it).
- Stamp backups to the second; a rerun must never overwrite the first
  run's backup.
- Use `scripts/corpus/corpus_safety.py` to meet this convention rather than
  hand-rolling it: `add_apply_argument`/`make_parser` gives a script
  `--apply` with dry run as the default, `backup(path, tag)` makes the
  dated, collision-safe backup, and `atomic_write(path, data)` writes
  beside the target and renames over it without translating line endings
  (reading or writing a file in Python's default text mode silently
  rewrites `\r\n` to `\n`, which is how a corpus PR lost Windows line
  endings on 2026-09-20). `scripts/corpus/apply_whole_vs_parts_refs.py`
  and `scripts/corpus/rebuild_docfreq.py` already follow the convention by
  hand and are the models the helper matches.


## 2026-10-24 Translations: Loeb volumes of 1931 to 1963 with no renewal found (RUN 19:26 EDT, by hand)

## 2026-10-24 Translations: 85 chapter, section and speech level files for Greek and Latin works (PLANNED, built and checked, nothing installed)

Why. The public-domain sweep of 2026-10-24 found English translations for held works whose own divisions are the chapter, the speech or the section, not the line, and for some whose numbering is exact. Part C of the batch builds the alignments on staging copies and proves them.

What. `scripts/translations/chapter_common.py` (shared checks) and sixteen alignment scripts, listed in the README as Pipeline 9. They wrote 85 files in the served shape (`units`, `ref_to_unit`, `sources`, `verified_by`) to `~/tesserae-backups/translations_c_2026-10-24/out/`, 21,334 of 22,229 references of the works covered (17,929 Greek and 3,405 Latin). Four more files wait in `out/review/` for a reading (Euripides Rhesus, two short Plutarch essays, Cassiodorus Variae as a condensed translation). Each file records which check vouched for it. Every file was re-measured against the corpus (`measure_staging.py`, the table is in the staging folder as `logs/measure.tsv`) and read by eye at five passages per work. The scripts reproduce the staged files byte for byte in `units` and `ref_to_unit` (checked 2026-10-24).

Works and levels. Chapter: Eusebius (McGiffert), Pausanias (Shilleto), Arrian (Chinnock), Florus (Forster), Celsus (Greive), Eutropius (Watson, books 1, 3 to 8 and 10), Cicero In Verrem, De Oratore and De Fato (Yonge, Watson, by cumulative length, marked approximate), Brutus (Watson, exact), eleven Aristotle works (Oxford translation and Kenyon), Clement of Alexandria (Wilson) and Apuleius (Butler). Section: Isocrates (Norlin), three Demosthenes speeches (Vince), Apollodorus (Frazer), Epictetus (Long), Hippocrates (Adams, Jones), Gregory of Nazianzus orations 27 to 31, Aristotle Nicomachean Ethics by Bekker position (Rackham). Speech: 41 Demosthenes speeches, the Exordia and the Epistles (Kennedy). Dissertation: Maximus of Tyre (Taylor), through a concordance of his order and ours that the rival test found. Letter: Basil (Jackson, 322 of 452 references).

Not written and why is in the README (Hippocrates Aphorisms, Parts of Animals book 4, Problemata, Psalms of Solomon, Dionysius of Halicarnassus Spelman, Bacchylides, Achilles Tatius, Saxo, Valerius Maximus).

Conflict to decide before the install. `grc__pausanias.description_of_greece.json` was installed on production at 19:16 EDT today from the Loeb volume 3 (Jones and Ormerod, books 6 to 8.21, 553 references). The staged Shilleto file covers all ten books. Do not copy it over the live file. `scripts/translations/merge_translation_files.py` builds the file with both (`unit_sources`, the Loeb unit where the Loeb covers a reference and Shilleto elsewhere), staged as `out_merged/grc__pausanias.description_of_greece.json` (99.65 percent of 3,170 references, checked through `backend.translations.for_passage`: the Loeb credit on 6.2.1, Shilleto on 1.6.7 and 8.30.2). Dionysius of Halicarnassus and others may also have gained Loeb files today, so list the live folder again before copying.

Install order (PLANNED, main session). (1) `sha256sum -c SHA256SUMS.txt` in `out/`. (2) List `data/translations/` and drop from `out/` any file whose name is now live (Pausanias, and anything installed since 19:16 today), using the merged Pausanias file in its place if chosen. (3) Back up the live folder (`cp -a data/translations data/translations.bak-<stamp>`, stamped to the second). (4) Copy the files into `/var/www/tesseraev6_flask/data/translations/` at mode 664 (copy beside and rename over, never in place). (5) `touch tesseraev6_flask.wsgi`. (6) Check through the endpoint, for example `curl 'https://tesserae.caset.buffalo.edu/api/translation?work=grc/arrian.anabasis&refs=arr.%202.9.4'`, one reference per script. (7) The Sources page check (every new translator listed) and the golden check. (8) Decide the four files in `out/review/` by reading them (they are not installed by this order).
## 2026-10-24 Translations: Loeb volumes of 1931 to 1963 with no renewal found (PLANNED, built on staging copies, nothing installed)
Eighteen aligned English files for eleven works, from Loeb Classical Library volumes first published 1931 to 1963 with a United States publisher on the title page and no renewal in the NYPL cce-renewals data. Scripts and the method are in `scripts/translations/README.md` (pipelines 9 and 10), the whole run is `scripts/translations/run_unrenewed_batch.sh`. The files and `SHA256SUMS.txt` are in `~/tesserae-backups/tr_f_2026-10-24/final/`: `standalone/` (14 files for works with no installed English), `merged/` (Josephus Antiquities, Pliny the Elder and Silius Italicus laid over the installed files, both translators kept in `unit_sources`), `separate/` (Pausanias, and Silius vol. II alone). `partial/` holds the two alignments the merges were made from and is not installed.
Install order (PLANNED). (1) Back up the three files the merged ones replace, to the second: `grc__flavius_josephus.antiquitates_judaicae.json`, `la__pliny_the_elder.naturalis_historia.json`, `la__silius_italicus.punica.json`, from `data/translations/` to `~/tesserae-backups/translations_F_<stamp>/`. (2) Copy the 14 `standalone/` files, the 3 `merged/` files and `separate/grc__pausanias.description_of_greece.json` into `data/translations/`, mode 664. The Silius merge removes Kline's translation of books 9 to 17 (public domain first), leave the installed file in place if the Kline text is to stay. If the Spelman alignment of Dionysius or Shilleto's Pausanias from the other pull requests is installed first, merge with `merge_unit_sources.py` so that the earlier file is kept. (3) `touch tesseraev6_flask.wsgi`. (4) Check each work through the endpoint, for example `curl 'https://tesserae.caset.buffalo.edu/api/translation?work=grc/nonnus_of_panopolis.dionysiaca&refs=nonn.%20d.%2025.300'`, then the Sources page (the credits come from the files: Rouse, Bury, Thomson, Robbins, Shorey, Jones and Ormerod, Duff and Duff, Cary, Marcus, Rackham, Eichholz), then the golden check.
Not written: Nonnus books 1 to 15 (the only open scan of volume 1 has lost half its pages and many words), Ennius (Warmington's fragment order does not match our lines), the Prudentius Epilogus (34 lines, too few names), and Celsus volume 2 (open, but our references are not the Loeb's chapter and section numbers). Volumes with no open scan: Sextus 3, Minor Latin Poets II, Pausanias IV and V, Valerius Flaccus, Athenaeus 5 to 7, Celsus 1 and 3, Hyginus. Not attempted because a complete translation is installed: Diodorus (Oldfather) and Strabo (Hamilton). Outside the 1931 start: Plato's Republic books 1 to 5 are volume I of 1930.

Run record. The renewal reading adopted: a Loeb volume whose title page carries a US imprint beside London, first published 1931 to 1963, with no renewal record in the Catalog of Copyright Entries transcription (NYPL cce-renewals, searched per volume by title and translator, every search empty for these books), is treated as US public domain, the reasoning LacusCurtius follows; the project owner was told and did not object. After the heading-stripping pass (commit a77c7951: Duff's ARGUMENT summaries cut from eight Silius book openings, three Loeb poem titles cut from the Peristephanon) the staged files verified against SHA256SUMS.txt (21 OK) and the seventeen to install were checked for the served shape (no empty units, sources present). Not installed: Plato Republic 6 to 10 (names 0.58 on 66 names, length correlation 0.11; waits for the 1930 first volume), the separate Silius file (the merged one was used), the two partial files. Backups: the three replaced files kept as `grc__flavius_josephus.antiquitates_judaicae.json.bak-20261024-unrenewed`, `la__pliny_the_elder.naturalis_historia.json.bak-20261024-unrenewed`, `la__silius_italicus.punica.json.bak-20261024-unrenewed`; the fourteen others are new files. Copied 19:26 EDT, mode 664, wsgi touched 19:26:15, `/api/languages` 200. Granularity gained by the merges: Josephus Antiquities 20 units to 1,184, Pliny Natural History 37 to 2,387, with Whiston and Bostock kept where the Loeb lacks a page; Silius books 9 to 17 now Duff (public domain first), Kline kept only where Duff lacks. Live reads through `/api/translation`: Silius 9.1 (begins with the translation, no ARGUMENT) and 12.231 (Duff), Nonnus 40.444 (Rouse), Pliny 23.4 (Jones 1951), Josephus 11.269 (Marcus 1937), Dionysius 8.50.3 (Cary), Peristephanon 10.440 (Thomson 1953), Pausanias 7.23.3 (Jones and Ormerod), each with its credit and license line. Golden: `reader_translations_available` (eight new works listed) re-recorded; two theme requests also differed and were re-recorded, then checked for stability (see the journal of the day).
## 2026-10-24 Translations: six re-alignments where the installed English covers far less than its source (RUN 19:00 EDT, by hand)
Why. The sweep of 2026-10-24 found six works whose installed translation covers far less than a complete public-domain source. Four of the six shortfalls had a cause other than a poor scan (the corpus text for Martial and Petronius grew after their translations were built, and Book 8 and Book 14 of the Anthology print their epigram numbers in a layout the script did not read).
What. Scripts under `scripts/translations/` (README, "Pipeline 9") built these files in `~/tesserae-backups/tr_realign_2026-10-24/final/` with `SHA256SUMS.txt`, all in the served shape (`units`, `ref_to_unit`), `compact_for_serving.py` run, none installed. Coverage is the share of the work's references that have an English unit, installed file against staged file.
- `grc__anthologia_graeca.part.{7,8,14,15,16}.json`: 61.8, 57.7, 58.7, 63.3, 58.7 percent to 97.1, 99.2, 95.2, 90.6, 99.1. Names 0.85, 0.91, 0.78, 0.86, 0.83, length correlation 0.68, 0.84, 0.70, 0.66, 0.76. Paton's Loeb from five archive.org scans merged with an agreement check.
- `extra_books_10_13/grc__anthologia_graeca.part.{10,11,12,13}.json` (the same method, not asked for): 85.1, 71.8, 67.2, 88.5 percent to 99.8, 98.4, 96.2, 100.
- `la__martial.epigrams.json`: 67.4 to 99.2 percent (9,304 of 9,375 lines), Bohn with Ker for five epigrams (`unit_sources`), names 0.83, ten epigrams have English in neither book.
- `la__pliny_the_younger.letters.json`: 47.2 to 86.1 percent, Firth (books 1 to 5) and Melmoth revised by Bosanquet (books 6 to 9 and 14 letters of Book 10), names 0.63, length correlation 0.98. Book 10 stays mostly without English (see the README).
- `la__petronius.satyricon.json`: 27.6 to 76.8 percent, 21 of 29 verse passages, Heseltine, one page per passage.
- `la__seneca.apocolocyntosis.json`: 42.4 to 100 percent, Rouse, one page per passage.
- `grc__flavius_josephus.josephi_vita.json`: 17.7 to 100 percent, Thackeray, 79 units, names 1.0 on 79 pages.
Install order (PLANNED). (1) Check `df -h /` and `sha256sum -c SHA256SUMS.txt` in the staging folder. (2) Back up the ten target files (and the four extras if installed) in `data/translations/` to `data/translations/backup-20261024-realign/`, stamped to the second. (3) Copy each staged file beside its target and rename over it at mode 664 (the translations loader reads a file once per worker, so `touch tesseraev6_flask.wsgi` after the last one). (4) For each work request `/api/translation?work=<work>&refs=<ref>` for two references and read the English beside the source (the preview check in the run record shows which). (5) Open the Sources page and confirm Ker, Thackeray, Heseltine, Rouse, Melmoth and Bosanquet are listed with their own years, and that the Martial credit line names two translators. (6) The golden check. Rollback: the backups renamed back.
Run record. Preview on a copy of the production translations folder plus the staged files, port 8099, 22 translation requests (two per work) all returned the new English with the right translator, and the Reader's English view of Martial Book 11 showed the Bohn and Ker credit line. Not yet installed.
Run record. After the small-capital repair (commit e18f8ed1, 537 first words repaired across the nine Anthology files, logged in the staging folder's small_caps_repair_log.tsv) the fourteen staged files (ten in `final/`, the four extra Anthology books 10 to 13 in `final/extra_books_10_13/`) verified against their SHA256SUMS.txt files (14 OK) and were checked for the served shape (units, ref_to_unit, no empty units, sources present). The fourteen installed files they replace kept beside them as `*.bak-20261024-realign`. Copied at 19:00 EDT, mode 664, wsgi touched 19:00:28, `/api/languages` 200. Live reads: Anthology 7.392 and 10.56 (Paton, high), Martial 7.95 (Bohn, with Ker where Bohn lacks), Pliny Letters 5.8 (Firth 1900 and Melmoth), Petronius 89 (Heseltine, low), Josephus Vita 216 (Thackeray, high). Golden: `reader_translations_available` re-recorded, all 69 the same. Finding worth keeping: Martial and Petronius were never misaligned; their texts were replaced after the files were built, so a text replacement must rebuild its translation file in the same step.
## 2026-10-24 Coptic Septuagint books paired with Brenton 1851 (RUN 18:52 EDT, by hand)
Why. The Coptic Old Testament follows the Septuagint, and the installed Bohairic Daniel was paired with the World English Bible, which translates the Hebrew. The Bohairic text divides Daniel 3 over three chapters and carries Susanna and Bel, so Coptic chapters 3 to 12 sat beside the English of other chapters (Coptic 4.1, the prayer of Azariah, beside "Nebuchadnezzar the king, to all the peoples"). Five Coptic Septuagint books had no English at all.
What. `scripts/translations/align_coptic_brenton.py` (with `coptic_align_common.py`) writes six files to `~/tesserae-backups/tr-d-staging/brenton/` with `SHA256SUMS.txt`: `cop__bohairic.psalmi.json` (2,305 of 2,314 lines), `cop__bohairic.daniel.json` (533 of 623, replaces the installed file), `cop__sahidic.proverbs.json` (794 of 890), `cop__sahidic.epistle_of_jeremiah.json` (72 of 72), `cop__sahidic.habakkuk.json` (13 of 30) and `cop__sahidic.daniel.json` (57 of 183). Each file records its two checks and the control, and `sources` names Brenton (1851, London, Bagster, public domain). Not written, because both checks fail or cannot be run: Sahidic Bel (5 lines), Sahidic 1 Chronicles (2 lines), the remaining Habakkuk and Daniel chapters, Proverbs 24, 30 and 31 (the Septuagint prints them in another order), two Psalms, and chapters 15 and 19 of Bohairic Daniel (the Old Greek wording, which Brenton does not print).
Install order (PLANNED). (1) Back up `data/translations/cop__bohairic.daniel.json` to `~/tesserae-backups/translations_cop_septuagint_<stamp to the second>/`. (2) Copy the six staged files into `data/translations/`, mode 664, after checking `sha256sum -c SHA256SUMS.txt` in the staging folder. (3) `touch tesseraev6_flask.wsgi`. (4) Check through the endpoint, for example `/api/translation?work=cop/bohairic.daniel&refs=bohairic.daniel.4.1` (should read "Then Azarias stood up, and prayed") and `work=cop/bohairic.psalmi&refs=bohairic.psalmi.22.1`. (5) Open the Sources page and confirm Brenton appears against the five new Coptic works. (6) Run the golden check. Nothing in this entry has been run on production.
Not built, with the reason in `scripts/translations/README.md` (Pipeline 9): Budge's English for Mercurius, Theodosius on Michael, Bartholomew and the Repose of John (the held-out names do no better than the control), Khayyam against Whinfield 1882 (matched by meaning, no check can vouch for the pairs), Hafez, Nizami and the Urdu Hindustani Lyrics.
Run record. The six staged files verified against SHA256SUMS.txt (6 OK). The installed `cop__bohairic.daniel.json` (63,399 bytes, 2026-08-24) kept beside the new one as `cop__bohairic.daniel.json.bak-20261024-brenton`; the other five are new. Copied at 18:52 EDT, mode 664, wsgi touched 18:52:39. Live reads: Bohairic Psalter 49.4 and Bohairic Daniel 6.5 (Brenton, the Daniel chapter now the right one). Golden as in the Part A record.
## 2026-10-24 Translations: fourteen new aligned English files, exact numbering, Part A (RUN 18:52 EDT, by hand)
Why. The sweep of 2026-10-24 found free English translations that share our numbering for several held works. This is the first of two batches (the second re-aligns six works where an installed translation covers little of a complete source).
What. Fourteen files built by the scripts in `scripts/translations/` (README, "Pipelines 9 to 16"), kept in the staging folder `~/tesserae-backups/translations_exact_2026-10-24/out/` with `SHA256SUMS.txt` beside it. No file replaces an installed one, because none of the fourteen works has a translation file today. Works and coverage of our references: Oppian Halieutica 99.5 percent, Cynegetica 98.4, Colluthus 100, Tryphiodorus 100, Aratus 100, Callimachus Hymns 100, Lycophron 100, Bion Lament for Adonis 100, Theocritus Idylls 92.3 (Idylls 16, 19, 27 skipped, 20 absent), Pindar 89.5 (Pythian 6 skipped), Tibullus 92.4, Lysias 100, Gregory Dialogues 67.2 (Books 1 to 3), Polyaenus 45.1. All fourteen use the served shape (`units`, `ref_to_unit`), so `compact_for_serving.py` was run and changed nothing.
Install order (PLANNED). (1) In the staging folder run `sha256sum -c SHA256SUMS.txt`. (2) Back up the live folder: `tar czf ~/tesserae-backups/translations_dir_before_exact_batch_<stamp>.tgz data/translations` from the production root. (3) Copy the fourteen files into `data/translations/` at mode 664 (copy beside, then rename over, though no name exists yet). (4) `touch tesseraev6_flask.wsgi`, because `backend/translations.py` reads its index of works once per worker. (5) Verify through the endpoint, for example `curl 'https://tesserae.caset.buffalo.edu/api/translation?work=lysias.speeches&refs=lys.%20speeches%201.26'` and one reference of each of the other thirteen works. (6) Check the Sources page lists the new translators (Mair, Mair and Mair, Edmonds, Sandys, Postgate, Lamb, P. W. with Gardner, Shepherd). (7) Run the golden check. (8) Withdraw nothing: no work was rejected, so no installed file needs removing.
Checks. Each file passed proper-name agreement or length correlation (README table) and five passages of each were read against the original on a preview server with the files in place, with the Reader's Translation tab screenshot for Lysias 1.26. Not written: Seneca's tragedies (the installed 1907 files already cover 99.5 percent of the five-line blocks), Callimachus Epigrams and fragments, Gregory Book 4, and the poems whose printed numbering disagrees with ours (README, "Not written").
Run record. After the footnote-cleaning pass (commit e8a40cd1, five files changed, the other nine unchanged) the fourteen staged files verified against SHA256SUMS.txt (14 OK). None replaced an installed file (Seneca was not written: the installed Miller 1907 files already cover 99.5 percent of the tragedies at the five-line grain, the sweep's 19 percent was a miscount). Copied into `data/translations/` at 18:52 EDT by copy-and-rename, mode 664, together with the Coptic batch of the same minute, wsgi touched 18:52:39, `/api/languages` 200. Live reads through `/api/translation`: Lysias 10.29 (Lamb, high), Oppian Halieutica 2.367 (Mair, 22-line blocks, approximate), Tibullus 1.8.52 (Postgate, 27-line blocks), Pindar Pythian 2.33 (Sandys, 17-line blocks), each available with its credit and license line. Golden check: 1 of 69 different, `reader_translations_available` (Gregory Dialogues and Tibullus now listed), re-recorded after the Part B install at 19:00; then all 69 the same.

## 2026-10-24 Coins: stored thumbnails of the American Numismatic Society's own photographs (RUN 16:35 EDT install, 16:56 deploy, by hand)

Why. The coin cards link out to numismatics.org for pictures, and on 2026-10-23 that site was down and the cards were blank.

What. `scripts/coins/fetch_ans_thumbnails.py --specimens` asked the Nomisma SPARQL endpoint (GET only, one request a second) for every specimen of an OCRE type held by the American Numismatic Society (40,623 specimens, 12,205 types, 21.7 percent of the 56,113 OCRE types). Without `--specimens` it picks one specimen per type (one with both sides first), downloads the obverse and the reverse image from numismatics.org/collectionimages (one request a second, one user agent naming the project), scales each side to 160 px wide, joins them side by side and stores a JPEG under 12 KB. Only the Society's own photographs are taken, never another museum's.

Result. 12,156 types have a thumbnail (one is obverse only), 49 types have an ANS specimen without an image, no fetch errors, no 403 or 429. Mean 11.2 KB, largest 12,288 bytes, 143 MB on disk. The 43,957 OCRE types with no ANS specimen keep the link out, and so do all Greek types.

Install order (PLANNED). (1) Copy the staging folder's `thumbs/` to `data/coins/thumbs/` and `thumbnails.sqlite` to `data/coins/`, files mode 664 and the folder group-writable. (2) Deploy the pull request. (3) `touch tesseraev6_flask.wsgi`. (4) Check one pictured card (an Augustus aureus, `ocre:ric.1(2).aug.10`) shows the picture and the credit on hover, and one unpictured card (a Greek type) still shows the link out. The route is `/api/coins/thumb/<name>` and the field `thumb_url` appears on every coin row.
Run record. Permissibility checked on numismatics.org before the install: the collection's license field reads Public Domain Mark for images, and the site states that all images of objects produced on or before 1925 are in the public domain, which covers every ancient coin. Staging folder `~/tesserae-backups/coin_thumbnails_2026-10-24/`: 12,156 files, 143 MB. Installed 16:35 EDT: `data/coins/thumbs/` created mode 2775 (group tessdev), the files copied with their times and set to 664, `thumbnails.sqlite` copied beside `coins.sqlite` at 664 (sha256 6ad48f69... the same as the staging copy). #1193 merged and deployed 16:56 by the merge chain (bundle rebuilt, wsgi touched). Live checks 16:57: `ocre:ric.1(2).aug.10` answers `thumb_url` /api/coins/thumb/ric.1_2_.aug.10.jpg with the credit line, the file serves 200 image/jpeg 10,947 bytes (front and back of a denarius, read by eye), `ocre:ric.1(2).aug.100` has no picture and keeps the link out, a name not stored gives 404. Golden check: 67 of 69 requests the same, the two coin requests differ by the two new fields only, recorded as the new golden for those two names. Found at the check: the pictures came back with the site-wide no-store header, so the follow-up pull request exempts the picture route from that rule, as the museum pictures and the Events name list already are.
## 2026-10-24 Coins: the checked accounts of pass 5 installed for 4,943 Roman coin types (RUN 09:13 EDT, by hand)
Why. Pass 5 of the coin accounts (the model-written line on what a coin shows and commemorates, entry of 2026-10-23) put event context from the Events store and a legend glossary into the prompt for the 26,461 Roman types, then made a second model call that checked every new name, place, event and number against the inputs. On the hundred-search measure the result was flat (right coin in the first ten 77 live, 78 with every new account, 77 with the checked rows only), but in forty random rows read side by side the checked accounts read the legends better in 24 (consulships, tribunician years, vows and titles taken from the legend, invented occasions dropped), the same in 13 and worse in 2. The project owner chose the checked rows only (2026-10-24, "go with your recommendation").
What. `data/coins/descriptions_ids.json` and `data/coins/descriptions_meaning.npy` replaced by the install5b files: the live rows and vectors of 2026-10-23 with the `gist` text and the vector of each of the 4,943 checked rows substituted row by row (no re-encoding of the rest; built 2026-10-24 00:11 in `~/tesserae-backups/coin_gists_2026-10-23/install5b/`, SHA256SUMS.txt, sha256 882c6d27… and a3273409…). The 18,187 rows that changed in wording only were not checked and are not installed.
Run record. The staged files' checksums verified, the live files kept as `descriptions_ids.json.bak-20261024-install5b` and `descriptions_meaning.npy.bak-20261024-install5b`, each new file copied beside the live one at mode 664 and renamed over (the vectors first, then the ids), 09:13 EDT; the routes re-read the files when they change, so no reload. Checks: the installed files' sha256 equal the staged ones; the coin meaning search gives RIC I² Augustus 546, 275A and 275B for "the conquest of Egypt" and RRC 508/3 (the EID MAR denarius) first for "Brutus and the Ides of March"; the recorded check, all 69 requests the same. Rollback: the two backups renamed back.
## 2026-10-24 Coins: 74 accounts corrected by hand after the first pass of the step 5 review (RUN 11:14 EDT, by hand)
Why. Step 5 of the coin plan is a hand review of the accounts most likely to be wrong and most looked at: the 837 Republican types and the 825 Augustan to Domitianic types whose account names an event or a person. A first pass read 218 rows against the catalog fields and legends: the 138 rows the gateway checker had marked with a doubtful claim, and random samples of 40 Republican and 40 early imperial rows it had passed (seed 1024). 74 were wrong or misleading: 58 of the 138 flagged (42 percent) and 16 of the 80 unflagged (20 percent). The repeated faults: Flavian restoration coins (legend REST, "restituit") read as political restorations of the empire, the state or a temple (eleven rows); a consulship number given to the wrong man (COS V or COS VI of Titus or Domitian called Vespasian's); family relations wrong (Julia Titi called the wife of Titus or of Domitian, FELIX and FAVSTVS read as brothers, MAGN PRO COS read as Varro's father); legend abbreviations misexpanded (FORT RED, POPVL IVSSV, S P Q R CL V, OB CIV SERV, IMPER RECEPT, DIVA AVGVSTA, SIGNIS RECEPTIS of 71 CE); the Aqua Marcia credited to King Ancus; the mark of value S called a mint mark; mint codes B3 to B51 of the restoration series written as place names.
What. The 74 accounts rewritten by hand (research/coins/2026-10-24_hand_review/final_accounts.json, private; verdicts for all 218 rows in verdicts.tsv beside it), each from the catalog description, the legends and the standard references for the type, two sentences, 40 words on average. Vectors for the 74 made with the site's own encoder (port 8090, the "query: <description> Meaning: <account>" form of the other passes). Built as install5d from the live files of 11:02 (install5c): a row-by-row comparison showed 74 rows differing in the `gist` field only and the same 74 vector rows changed.
Run record. The live files kept as `descriptions_ids.json.bak-20261024-install5d` and `descriptions_meaning.npy.bak-20261024-install5d`, the new files copied beside them at mode 664 and renamed over (vectors first, then ids), 11:14 EDT; the routes re-read the files. Checks: installed checksums equal the staged ones (fce0c876… and 1e6219bc…); the coin pages for RRC 36/2, RIC II.1² Titus 472 and RIC I² Augustus 46A show the new accounts; the two live meaning searches unchanged; the recorded check, all 69 requests the same. Still to read: the remaining 1,444 rows of the two sheets, where the sample suggests about a fifth carry a fault of the same kinds. Rollback: the two backups renamed back.
## 2026-10-24 Coins: 127 accounts corrected by rule after the hand review found three mechanical fault kinds (RUN 11:23 EDT, by hand)
Why. The first pass of the step 5 hand review (its own entry of this date) found three faults that are mechanical and run through the whole Roman set, not only the two review sheets: (1) restoration coins, whose legend ends in REST or RESTITVIT ("restituit", the emperor reissued an old type), read as the restoration of the empire, the state, a temple or a statue; (2) a consulship number on a coin of Titus or Domitian attributed to Vespasian; (3) the mint codes B3 to B51 of RIC's restoration series written as place names ("Struck at B6").
What. A search over the 46,244 accounts with the legends in `coins.sqlite` found 130 restoration issues (Trajan 61, Titus 37, Antoninus Pius 13, Nerva 11, Domitian 7, Marcus Aurelius 1), of which 11 already said so and 13 (Antoninus Pius, TEMPLVM DIVI AVGVSTI RESTITVTVM, a temple restored, not a reissued coin) were rightly left alone; 17 consulship rows, of which one (COS VII under Vespasian on a Domitian denarius of 76) was right; 5 mint-code rows. The 127 rewrites keep each account's descriptive first sentence (an abbreviation-aware split, "M. Porcius Cato") and replace the interpretation: for a restoration issue "The legend <REST legend> marks it as a restoration coin: <emperor> reissued <the original type>", the original read from the other legend (DIVVS AVGVSTVS, TI CLAVDIVS, GERMANICVS, M AGRIPPA, ...) or from the description (Livia's dupondii, the Civitatibus Asiae sestertius), "a Republican denarius" for Trajan's restored Republican types, and one by hand (Marcus and Verus reissuing Antony's legionary denarius of the Sixth Legion); for a consulship row the name corrected to the man on the obverse (Titus's fifth consulship, 76 CE); for a mint code "Struck at Rome". All 127 read before the build (research/coins/2026-10-24_hand_review/mechanical_fixes_reading.txt, private). Vectors from the site's encoder; built as install5e from the live files of 11:14 (install5d); a row-by-row comparison showed 127 rows differing in `gist` only and the same 127 vector rows changed.
Run record. The live files kept as `descriptions_ids.json.bak-20261024-install5e` and `descriptions_meaning.npy.bak-20261024-install5e`, the new files copied beside them at mode 664 and renamed over (vectors first, then ids), 11:23 EDT; the routes re-read the files. Checks: installed checksums equal the staged ones (0789504e… and 10e87d59…); the coin pages for RIC II Nerva 126, RIC II.1² Vespasian 857 and RIC II Trajan 767 show the new accounts; the two live meaning searches unchanged; the recorded check: all 69 requests same. Rollback: the two backups renamed back.
## 2026-10-24 Coins: the checked wording-only accounts of pass 5 for 17,319 Roman coin types (RUN 11:02 EDT, by hand)
Why. The install of 09:13 EDT today took the 4,943 pass 5 rows whose new account changed a fact. The other 18,187 rows changed in wording only (for example "the valor of the emperor" for "the virtue of the emperor"). They were run through the same three checking passes (the fact check against the catalog fields, the event list and the legend glossary, a rewrite of each flagged row with the flags, a second check of the rewrite) on 2026-10-24, 09:29 to 10:50 EDT, on the free gateway model, 48 workers (157 rows a minute at 32 workers, 170 to 290 at 48, the model's decoding capacity being the limit), no errors that mattered. Of 18,187 rows, 16,277 had no flag on the first pass, 1,910 were flagged and rewritten, 1,068 of those rewrites passed the second check, and 842 stayed as installed. The passing 17,345 rows include 26 whose rewrite equals the installed account, so 17,319 rows change. The hundred-search measure on the result is 77 right coins in the first ten, 83 in the first 25, mean reciprocal rank 0.6651 (live: 77, 82, 0.649); a reading of 40 random substituted rows found 13 better, 26 the same and 1 worse, none wrong about a person or event.
What. `data/coins/descriptions_ids.json` and `data/coins/descriptions_meaning.npy` replaced by the install5c files: the live files of 09:13 (sha256 verified against install5b) with the `gist` text and the vector of each of the 17,319 rows substituted (vectors encoded on the campus GPU from "query: <description> Meaning: <account>", 50 rows checked against the site's encoder, cosine at least 0.99976). Built in `~/tesserae-backups/coin_gists_2026-10-23/install5c/` with SHA256SUMS.txt by `build_install5c.py`, checks by `check5w.py` into `checks_wording.sqlite`.
Install order (by hand, main session). Verify the staged checksums, keep the live files as `descriptions_ids.json.bak-20261024-install5c` and `descriptions_meaning.npy.bak-20261024-install5c`, copy each new file beside the live one at mode 664 and rename it over (the vectors first, then the ids), no reload because the routes re-read the files when they change. Then the two live searches ("the conquest of Egypt" gives RIC I2 Augustus 546, 275A and 275B first, "Brutus and the Ides of March" gives RRC 508/3 first), then the golden check. Rollback: rename the two backups back.
**Run record (11:02 EDT).** Before the install the live files still matched install5b (sha256 882c6d27… and a3273409…), the staged install5c files matched their SHA256SUMS.txt (1cd234c7… and da7b3df0…), and a row-by-row comparison showed 46,244 rows in the same order with 17,319 differing in the `gist` field only and the same 17,319 vector rows changed. The live files were kept as `descriptions_ids.json.bak-20261024-install5c` and `descriptions_meaning.npy.bak-20261024-install5c`, the new files copied beside them at mode 664 and renamed over (vectors first, then ids); the routes re-read the files, no reload. Live checks: "the conquest of Egypt" gives RIC I² Augustus 546, 275A, 275B; "Brutus and the Ides of March" RRC 508/3 first; "the port of Ostia" Nero's Ostia sestertii (RIC I² Nero 441, 440, 178); the recorded check, all 69 requests the same. Rollback: the two backups renamed back.
## 2026-10-24 Compare page: the size limit's download queue installed (RUN 10:21 EDT, by hand)
Why. A comparison of two whole epics held one of the three web workers for an hour at up to 12 GB (measured 2026-10-24: Aeneid against the Metamorphoses, 118 million line pairs, killed at 12 GB after an hour; Aeneid 1 against the whole Metamorphoses, 9.1 million, 19 minutes and 5.8 GB). The project owner chose a limit with a prepared download rather than a refusal (2026-10-24: "give users an option up front that if they want the whole thing, we can prep a download and let them know when it's done").
What. #1185 (deployed 10:21 EDT): above twelve million line pairs (`COMPARE_MAX_LINE_PAIRS`) the comparison route, the estimate route and the connector answer `too_large` with the per-book choices and the address of a queue; the page offers book by book now or a prepared file later, and lists the visitor's prepared comparisons. The queue is the table `comparison_jobs` (created at the reload), three routes under `/api/comparisons/jobs`, and `scripts/comparison_queue_runner.py`, which runs the oldest queued job through the same comparison function as the live route, with no row cap, writes the CSV under `data/comparison_jobs/` (gzip over 20 MB), keeps jobs 14 days, and never retries a job killed by the memory cap. Visitors are mailed only when `VISITOR_MAIL_ENABLED=1` is set in the production `.env` (default off, because the server's relay, `SMTP_HOST=localhost`, did not deliver a test message to an outside address); otherwise the status page and the Compare page's "Your prepared comparisons" list are the notice.
Run record. `data/comparison_jobs/` created (group tessdev, setgid, mode 2775); `server/systemd/tess-comparison-queue.service` and `.timer` copied from the production checkout to `~/.config/systemd/user/`, `daemon-reload`, the timer enabled and started 10:21:56 EDT (five minutes after each run ends, 30 s accuracy). The unit runs `/var/www/tesseraev6_flask/venv/bin/python /var/www/tesseraev6_flask/scripts/comparison_queue_runner.py` inside `systemd-run --user --scope --slice tesserae-jobs.slice -p MemoryMax=20G -p MemorySwapMax=0`, with the production `.env` as its environment file (mode 664 kept); the runner declines to start unless 26 GB are available and no tess-job scope is running. Live checks: Aeneid against the Metamorphoses answers `too_large` as JSON in 0.09 s with 27 book choices; the estimate route agrees; Aeneid 1 against Metamorphoses 1 streams as before; `/api/comparisons/jobs` answers; the recorded check, all 69 requests the same. Log: `~/tesserae-backups/jobs/comparison_queue.log`. Rollback: `systemctl --user disable --now tess-comparison-queue.timer` and the previous release; the table and folder may stay.
## 2026-10-24 People & Places: wrongly grouped spellings separated into their own entries (RUN 09:22 EDT, by hand)
Why. The People & Places scan filed spellings under an entry by a stem match, so different names shared one entry: Hecataeus under Hecate, Graeculus under the Greeks, Justina under Justinian, Theodotion under Theodosius, Hipponous under Hipponax. The project owner saw this on 2026-10-22 and asked that the plain errors be fixed before any install, and approved the install on 2026-10-24 ("yes").
What. `scripts/entities/regroup_names.py` with `backend/entity_regroup.py` (#1118), three passes: a rules layer keeps a spelling that is a case form of a heading, the gateway model (free) answers SAME, DIFFERENT or UNCLEAR per spelling group (answers cached across passes, 1,407 new questions in the last two), and since the third pass (2026-10-24) a spelling equal to the entry's own Greek label stays (with its Greek plural and genitive plural, counted only when the label's first five letters in Latin letters match a Latin heading), Hebrew accent marks and other combining marks are folded away, a spelling that is the front of a word broken across a line stays with its heading, a derived name reached through a chain of accepted case forms is refused (Hecataeus against Hecate), and after a carve-out the host's case forms of the new heading move with it together with their search names (Maximinum, Maximini, Maximine to Maximinus). Three sets that were iterated in hash order are now sorted, and the catalog time stamp comes from the input store, so two applies give byte-identical output (checked under two hash seeds, sha256 222097d6…). Applied to a copy of the live store of 2026-10-23 23:41: 19,321 spelling groups split, 1,911 moved to an existing entry, 17,899 carved into new entries, 11,637 mention rows moved, 861 dropped as duplicates, entities 42,355 to 60,254, mention rows 1,466,924 to 1,466,063, document mentions 602,278 to 602,269, catalog and form index rebuilt in the copy, integrity ok; Lavinia, Lavinium and pl:393444 untouched. A fresh random sample of forty splits (seed 2027): 38 right, 1 wrong (Laphitas split from Laphitarum), 1 unclear (Διοσπολιτικῷ against Diospolitana). Report: research/entities/2026-10-24_regroup_pass3/REPORT.md (private).
Run record. #1118 merged and deployed 09:21 EDT (its search change: a typed spelling that is not a heading opens the entry the scan filed it under). The copy's sha256 verified, the live file kept as `entities.sqlite.bak-20261024-regroup`, the copy renamed over at mode 664, WSGI touched 09:22. Live checks: Hecataeus opens its own entry, Hecate apart; Adonai one Hebrew deity entry of 616 lines (and a separate Coptic person entry, 81); Maximinus its own entry; Abessalon opens Absalom; Antoninus, Lavinia, Rusellae and Graeculus right; the recorded check, all 69 requests the same. Follow-up the same morning: 221 of the 19,009 carved entries carried a lower-case label ("hecataeus", "sextius"), from spellings that came from the lower-case Pliny scan; `scripts/entities/capitalize_carved_labels.py` (#1184) capitalized them on a copy of the live store (sha256 b6db4d93…, row counts unchanged, integrity ok), installed 09:29 EDT with the live file kept as `entities.sqlite.bak-20261024-labels`, WSGI touched; Hecataeus, Sextius and Nicander now open with capitalized labels. Rollback: the backup renamed back and the WSGI file touched.

## 2026-10-24 Documents: the Trismegistos-to-Pleiades crosswalk repaired against EDH's own findspots (crosswalk, metadata.db and events store RUN 06:35 EDT, the refreshed events store RUN 06:51 EDT, by hand)

Why. Three families of documents sat at the wrong place because rows of `trismegistos_to_pleiades.tsv` were wrong: 576 Ostia stones under Roma, 280 Aquileia stones under the German Aquileia (Aalen), 32 Turris Libisonis stones under Virunum, and a Rome, Saguntum or Aquincum row for a dozen other towns. `places_crosswalk.py` built the EDH rows with one entry per Trismegistos id, the Pleiades uri of the LAST findspot of that id winning, and one Trismegistos id covers many findspots. All 321 suspect rows from the EDH source carry exactly that last findspot's id.

What. `scripts/documents/check_crosswalk_against_edh.py` takes, for each Trismegistos id of the crosswalk that EDH's geography file carries, the median latitude and longitude of its findspots (the center) and the Pleiades id most findspots carry. A row is a suspect when the crosswalk id differs from EDH's id, its point is more than 20 km from the center and EDH's point is less than half as far (rule 1, Ostia against Roma at 22 km), or when its point is more than 100 km from the center whatever EDH says (rule 2, the German Aquileia 405 km from the Italian findspots). `repair_crosswalk.py` writes `trismegistos_to_pleiades.repaired.tsv` (a fifth column `repair` names the rule): rule 1 takes EDH's id, rule 2 the nearest Pleiades place to the center, within 25 km, whose title matches EDH's ancient name, a repair is withheld when the documents of the row lie less than 80 percent in one region (a bucket of homonyms such as Neapolis), and a rule 3 handles the rows whose Pleiades place has no point anywhere (the documents' own place name and the points of other documents with that name decide). It also adds rows for Trismegistos ids documents carry and the crosswalk lacks. `apply_crosswalk_repair.py INPUT OUTPUT` writes the repaired ids into a COPY of `metadata.db` (the id of a document is replaced only when it equals the old row's id or was filled on 2026-10-24, a document of a minority region keeps its id, and the 1,464 papyri of the Hermopolites nome with no place get Pleiades 756575). `rerun_event_documents.py` gained `--old-crosswalk` and `--old-pleiades-points`, so the old rule list is computed with the old crosswalk.

Result on copies. Rows checked 4,214 of the 4,320 that EDH's geography carries, suspects 332 (rule 1: 47, rule 2: 285), of which 75 are used by at least one document (4,249 documents). Repaired 170 rows (46 by rule 1, 124 by rule 2) covering 3,648 documents, plus 8 rows by rule 3 (4,654 documents, Roma 4,371 of them, which had carried the unlocated Andromachis), 6 repairs withheld as homonym buckets (174 documents), 162 suspects left (601 documents, most with no document). 8 rows added (152 documents, 1 of them without a Pleiades id). The 224 Pleiades ids that documents use and `pleiades_points.tsv` lacks (19,049 documents) have NO point in Pleiades itself (representative point, bounding box and the live JSON were all checked): they are unlocated places, and 17,280 of those documents come from two wrong rows, Trismegistos 2036 (Pyrreia, 12,909 EDH documents from every province, no place name) and 172 (Andromachis, 4,371 documents named Roma, now repaired). So the points file gets no additions. In the copy of `metadata.db` 9,808 documents change their Pleiades id (8,219 carried the old row's id, 125 EDR documents by place name, 1,464 Hermopolites papyri given an id), 83 minority-region documents kept theirs, and 0 documents with an id from the source itself differ. The events step on copies: 78 events change, 193 rows added and 168 removed, `documents` 18,299 to 18,324. Named cases afterward: all 6,176 Ostia stones within 10 km of Ostia (567 were 22 km out), all 2,642 Italian Aquileia stones within 10 km (221 were 405 km out), all 183 Turris Libisonis stones within 10 km (32 were under Virunum), and the 15 Heidenheim stones stay at Heidenheim.

Run record (06:35 EDT, by hand). The crosswalk, `metadata.db` and the events store were installed in the order below. Backups: `metadata.db.bak-20261024-crosswalk`, `event_dossiers.sqlite.bak-20261024-crosswalk` and `trismegistos_to_pleiades.tsv.bak-20261024-063510-crosswalk`. `pleiades_points.tsv` was left unchanged (no additions).

Stale values found after the install. The rows that the events rerun keeps (the naming rows and the unchanged rule rows) carry the `lat`, `lon` and `distance_km` computed under the old crosswalk: the Sack of Aquileia lists `merged:123194` ("Aquileia, bei", now Pleiades 187290) at 404.6 km and the point of Aalen. `scripts/events/refresh_document_distances.py INPUT OUTPUT --metadata PATH [--crosswalk PATH] [--pleiades-points PATH] [--apply]` recomputes `lat`, `lon` and `distance_km` of every row that has a distance from the document's current place (its `pleiades_id`, else its `place_tm_id` through the crosswalk) and the event's coordinates, with the rule's haversine. Rows with no `distance_km` (1,687 naming rows, shown without one on purpose), rows whose document has no place with a point (81) and rows already right (16,046) are left. On a copy of the live store of 06:35 (18,324 document rows): 510 rows change, among them the Aquileia row (404.6 km to 0.0 km, Aalen to Aquileia). 298 of the 510 fell from inside the rule's 100 km radius to outside it (Saguntum stones that an earlier rule run listed under Brundisium and Apamea at the old Valetium point, now 1,490 to 3,245 km away). The script does not remove rows, so those 298 stay listed, with their true distance, until a decision about them. The refreshed copy is `~/tesserae-backups/crosswalk_repair_2026-10-24/event_dossiers.distances.sqlite` (sha256 677e7c01, `integrity_check` ok, same 18,324 rows).

Install order. Done at 06:35: (1) the checksum check, (2) the crosswalk file replaced, (3) `pleiades_points.tsv` unchanged, (4) `metadata.db` swapped, (5) the events store swapped. Done at 06:51: (6) the live events store still had sha256 c7ac414d… (the store the refresh was made from) and `event_dossiers.final.sqlite` (sha256 8b0d811d…, distances and points refreshed on 214 rows, 296 stale rule rows removed, 2 kept as naming rows, `documents` 18,324 to 18,028) was compared with it table by table (every other table identical, 296 rows removed, none added) before the swap; (7) the live file kept as `event_dossiers.sqlite.bak-20261024-distances`, the copy renamed over at mode 664, WSGI touched; (8) live checks: `/api/languages` 200, the Sack of Aquileia (Q7396805) lists the Grado stone at 0.0 km, the 31 BCE Actium (Q160387) keeps its four rows with the three Nicopolis stones first, Perugia (Q960915) its 68, the Battle of Ostia its Ostia stones at 2.4 km; golden check 68 of 69, `events_list` re-recorded (the Battle of Adamclisi fell from 101 documents to 93 and left the top of the evidence listing), then 69 of 69. Code: #1176 and #1177. Still unplaced after this run: Trismegistos 2036 (12,909 documents with no place name), the 47 Baden-Baden documents, the 162 suspect rows without a repair (601 documents), the 224 unlocated Pleiades ids.

Open: Trismegistos 2036 (12,909 documents with no place name) stays unplaced, the 83 minority-region documents and 156 suspects with no repair are listed in the staging folder, the 298 rows now beyond the radius, and the 700 documents under added or missing rows whose Pleiades id is empty still have no point.

## 2026-10-24 Events: a place resolves by its Pleiades id, and the documents of wrongly resolved places are removed (built on copies by a delegate; RUN 03:49 EDT, by hand)

**Run record (03:49 EDT).** The `--remove-only` copy (`~/tesserae-backups/event_naming_2026-10-24/event_dossiers.removeonly.sqlite`, sha256 58cb7e94…) was installed as `data/events/event_dossiers.sqlite` after a table-by-table hash comparison with the live store showed every table identical except `documents` (18,314 to 18,299: the 15 rows listed above removed, none added); the live file was kept as `event_dossiers.sqlite.bak-20261024-placebyid`, the copy renamed over at mode 664, `integrity_check` ok. Live checks after the swap: `/api/events/Q9173813` lists no document, Naulochus (Q676692) 27 to 20, Pisa (Q30930263) 5 to 0, Sinope (Q3486025) 1 to 0, the 31 BCE Actium (Q160387) keeps its 4 rows with the three Nicopolis stones first, Perugia (Q960915) keeps its 68 rows. Golden check: 68 of 69 same, `events_list` re-recorded (one event left the evidence listing when its last document went, total 1,096 to 1,095, battles 732 to 731), then 69 of 69. The 59 additions were not installed, for the reason below. Code: #1170.

What. The naming step (`scripts/events/add_naming_documents.py`) resolved an event's place by its label through the People & Places search ranking. The 435 BCE "Battle of Actium" (Q9173813, label "Akri", Pleiades 530771) resolved to Akriai in Laconia (eid 126) and listed two Agrigentum stones 654.6 km away (`isicily:ISic004485`, `isicily:ISic004523`). The step now takes the entity whose own `pleiades_id` is the event's (a place before another type, then the most lines) and uses the label only when no entity carries the id, refusing a label hit whose own `pleiades_id` differs. `--report-place-resolution OUT.tsv` lists, for the 1,311 events with a place label, the entity each way resolves to: equal 105, different 17, only by id 14, only by label 648, neither 527; the new rule also refuses the label hit of 8 events (Megalopolis three times, Pisa, Sinop, Naulochus, Samnium twice). `scripts/events/remove_misresolved_place_documents.py INPUT OUTPUT --entities --metadata [--remove-only] [--apply]` takes the 39 events whose place resolves differently now, removes the rows linked to the old entity and not in the distance-rule list nor linked to the new place or a participant, and (without `--remove-only`) adds the new place's documents (dated within the event's years widened by 50, `--undated drop`, at most 50, participants untouched).

Result on a copy of the store of 2026-10-24 01:36: 15 rows removed in 4 events (Naulochus 7, Pisa 5, Actium of 435 BCE 2, Sinope 1), `documents` 18,314 to 18,299; with additions 59 rows more in 7 events (18,358). The additions are not recommended until the Mentions store's link rule is fixed: of the 59, 25 come from the adjective-stem rule, and the hand check found most of the Actium (31 BCE), Ascalon, Scarpheia, Amaseia and Corinth additions to be homonyms or personal names. Every other table has the same row count, `integrity_check` ok.

Install order, when approved: (1) check the live `event_dossiers.sqlite` still has the checksum in `input.sha256`, otherwise rerun the script on a fresh copy; (2) keep the live file as `event_dossiers.sqlite.bak-<date>-placebyid`, copy the `--remove-only` output beside it at mode 664 and rename over (remove the previous file's empty write-ahead files); (3) lockstep check: `/api/languages` 200, `/api/events/Q9173813` lists no document, `/api/events/Q160387` still lists the three Nicopolis stones first, `/api/events/Q960915` still lists the Perusia glandes (68 rows), the golden check. The events page's own naming highlight (`backend/blueprints/events.py`, `_documents_naming`) still resolves names by label, which is a separate change.

## 2026-10-24 Documents without a Pleiades place get one from their place name, and the events' documents redone (built on copies by a delegate; RUN 01:36 EDT, by hand)

Run record. The live `metadata.db` and `event_dossiers.sqlite` were unchanged since 2026-10-22 (the copies were taken from them at 01:29 and 01:34), so the filled copies were installed as built: `metadata.db` kept as `metadata.db.bak-20261024-places` and replaced (254,699 rows before and after; documents with a Pleiades id 112,721 to 229,409; integrity ok), `event_dossiers.sqlite` kept as `event_dossiers.sqlite.bak-20261024-docplaces` and replaced (documents 14,373 to 18,314 rows; events 1,485, passages 114,269, scholarship 16,165 and judgements 125,298 rows identical to the live store), both through a temporary name at mode 664, the WSGI file touched at 01:36. Checks: `/api/languages` 200; the Battle of Perugia lists 64 documents with the Perusia glandes at 0.1 km; the Battle of Actium keeps its three Nicopolis stones first and gains one Aegean inscription (SEG 29.167, 4.8 km); the golden check differed in four requests by the filled `pleiades_id` fields and the events' new documents alone (`ls_documents`, `ls_both`, `events_list`, `event_one`), re-recorded, all 69 the same at 01:43. Second run of the resolution before the install: Aquae (Civitas Aurelia Aquensis) and Apollonopolis left unresolved by hand, the sibling rule confined to one region field, a no-region name with candidates more than 150 km apart left unresolved (which also left the Hermopolites nome unplaced, about 1,500 papyri), 40 of 40 hand checks right. A filled id shows as a Pleiades link on the document page, as the checked ids are meant to. Left: the Hermopolites nome and the other 1,514 unresolved names; 19,049 documents whose Pleiades id has no point in `pleiades_points.tsv`; the EDH crosswalk's own wrong ids (567 Ostia documents under Roma, 280 Aquileia under Aalen, 43 Baden-Baden under Aachen), which this run never overwrote.

Why. An event's Inscriptions & Papyri tab is filled by distance from the event's point, and a document's point comes from its `pleiades_id` or, through the Trismegistos-to-Pleiades crosswalk, from its `place_tm_id`. Of 254,699 documents 141,978 had neither (all 105,191 EDR inscriptions, 20,219 EDH, 15,568 papyri, 637 EDH+EDR, 236 AIO, 127 I.Sicily), so they were never matched to any event. They do carry an `ancient_place` string, 3,110 distinct ones.

What. `scripts/documents/resolve_places_by_name.py OUTDIR --gateway --sample 40 --apply-to COPY.db` resolves each name (with its region, since one name can be several places) in order of trust: (a) siblings, other documents with the same normalized name that already have a place with a point (taken when one place holds 80 percent of them, counted only across the same region field, and set aside when the place does not carry the name and one other place does, or when the documents' region excludes it); (b) an exact title or name of a Roman-world place in the local Pleiades dump (`~/tesserae-docs/raw/pleiades/pleiades-places-latest.json.gz`, which holds the names the place JSON pages hold, so nothing was fetched); (c) several candidates, narrowed by the spread of the points of the region's resolved documents, then asked of the free gateway model (log kept). A name with no region whose candidates lie more than 150 km apart stays unresolved, and two names are left unresolved by hand (Apollonopolis, and Aquae (Civitas Aurelia Aquensis) whose sibling id is Aachen). It never overwrites a `pleiades_id`. Result on a copy: 1,650 name-and-region pairs resolved, 116,688 documents filled (sibling 83,150, title or name 25,183, region or model 8,355); documents with a point went from 93,672 to 210,360 of 254,699. The `documents` table has no coordinate columns, so the events step reads each point from `pleiades_points.tsv` through the filled `pleiades_id`. Row count unchanged.

Then `scripts/events/rerun_event_documents.py OLD_EVENTS.sqlite NEW_EVENTS.sqlite --old-metadata ... --new-metadata ... --apply` recomputes each event's documents by the installed rule (dated within the event's years widened by 10, dating span at most 50 years, within 100 km, ordered by span, distance and id, at most 50) on the old and the new metadata, and removes only the rows that left the rule's list and adds the rows that entered it, leaving rows that other steps added (names, Aegean inscriptions, the three Nicopolis stones of Actium). On the copy 334 events gained fill documents (54 of them had no document before), 4,975 rows were added (4,762 from the fill, 213 AIO documents that the rule admits and the installed store lacked), 1,034 pushed out, and the documents table went from 14,373 to 18,314 rows.

Install order, when approved: (1) check the live `metadata.db` and `event_dossiers.sqlite` still have the checksums the copies were made from, otherwise rerun both scripts on the live files copied fresh; (2) `metadata.db`: keep the live file as `metadata.db.bak-<date>-places`, copy the filled copy beside it at mode 664, rename over, touch the WSGI file; (3) the events store: keep the live file as `event_dossiers.sqlite.bak-<date>-docplaces`, same swap; (4) the lockstep check of the events entries above: `/api/languages` 200, `/api/events/Q960915` lists the Perusia glandes, `/api/events/Q160387` still lists the three Nicopolis stones first, the golden check. Open: whether a filled id should show as a Pleiades link on a document's page (the page reads `pleiades_id`), and 19,049 documents carry an id with no point in `pleiades_points.tsv` (mostly Fayum papyri, Pleiades 741589 and 741420).

## 2026-10-24 Latin documents: editor's glosses shown once, gap positions for the cards (built on copies by a delegate; RUN 04:47 EDT, by hand)

**Run record (04:46 to 04:47 EDT, after #1173 deployed at 04:46).** Backups first: the live index, Leiden table, reuse table and stats file, the 160 live sidecars and the 320 stage 3 files (484 files) copied to `~/tesserae-backups/inscr_expansions_2026-10-24/live_before_20261024-044652/`. Then, in this order and within one minute: the 160 `.tess` files and sidecars into stage 3, the 160 sidecars into `data/documents/restored/la/`, the index copied beside the live file and renamed over (mode 664), the Leiden table and the reuse table the same way, the stats file copied. Each installed file's SHA-256 matches the staged one (`install_sha256.txt`), the 160 sidecars identical. WSGI touched 04:46:59, `/api/languages` 200. Live checks: the Latin documents exact search for "duoviri" gives 225 lines (226 before) with no line reading the numeral and its gloss bare; "sit tibi terra levis" 1,347 lines (1,337 before, the joined lines); the EDR107014 record reads "uf IIviri (duoviri)" and its search hit carries `gap_before` and `gloss_indices`. Golden check: 64 of 69 same; the five that read the documents index were re-recorded after reading each difference (new corpus version 2026-10-24, joined first lines such as "Laurentia" for "Lauren / tia", the two new hit fields, reuse marks from the rebuilt table), then 69 of 69. Not installed: the Greek documents index (96 Greek EDR glosses wait for its next rebuild).

Why. The card for EDR107014 (the Perusine war in the consular fasti of Cupra Maritima) read "uf IIviri duoviri": the converter appended every `<expan><ex>` as a second word, so EDR's gloss of a numeral that is already written out ("IIviri <expan><ex>duoviri</ex></expan>") was searched and shown twice. And a card showed nothing where the stone has a gap, because `write_document_tess.py` drops a whole-gap token from the matching text and keeps only a count.

What. `scripts/documents/epidoc_convert.py` writes an `<expan>` that holds only `<ex>` (no `<abbr>`, no text of its own) into the expanded text in parentheses, flagged restored, and not into the diplomatic text; an expansion that already sits inside the editor's own parentheses is not wrapped twice, and an `<expan>` with an abbreviation is unchanged (EDH has none of the first kind, EDR 5,541 elements). `scripts/documents/write_document_tess.py` adds `gap_before` to every line of the restored-word sidecar: the positions in the index's own token list (the "/" between lines is not a token there) before which one or more whole-gap tokens were dropped, the number of tokens for a gap at the end. `backend/documents.py` reads it (`gap_positions`), `_document_hit` carries it in each hit, and `documentDisplay.jsx` shows a gray "[...]" (title "text lost") at each position. The converter also marks the characters of such a gloss (`gloss_flags` on the line, only on lines that have one), the writer turns them into `gloss_indices` in the sidecar (token positions in the index's list, like `gap_before`), and the card shows each run of gloss tokens in parentheses ("iiuiri (duouiri)"), keeping its dotted underline. Positions of `restored_indices` and `fragment_indices` stay as written and the card maps them to its own tokens.

Install order, each step after the backup of the file it replaces (stamp to the second): 1. `data/documents/restored/la/*.restored_words.jsonl` (160 files, the new field) and, in `~/tesserae-docs/stage3/texts_documents/la/`, the 160 `.tess` files with their sidecars; 2. `data/inverted_index/la_documents_index.db`; 3. `data/documents/leiden.sqlite`; 4. `cache/reuse_pairs/la_documents.db` (and its stats file). Index and sidecars go in the same minute (the lockstep: the sidecar positions count the index's tokens, so a new index with an old sidecar, or the reverse, puts the dotted underlines and the markers on the wrong words); then the WSGI file touched, `/api/languages` checked, a Latin documents search for "duoviri" and for "sit tibi terra levis" run. The code (this pull request) merges and deploys first: the old code ignores the new field, so a sidecar with `gap_before` is harmless under it.

Built from the unchanged raw files: `epidoc_convert.py` for EDR and EDH (58 s and 52 s), `dedupe_sources.py` over all four converted sources with the Oct 7 papyri and I.Sicily files (26 s, 257,428 records), `write_document_tess.py` (59 s), `build_documents_index.py --language la` (14 min 37 s, 2.5 GB), `build_leiden_display.py` (94 s), `build_documents_reuse_table.py --language la --max-literary-works 10` (15 min 53 s, 2.1 GB). The control runs (the unmodified converter) reproduce the Oct 7 converted and merged files byte for byte.

Sidecar regeneration (after the gloss flag was added, one conversion of EDR, one merge and one write pass, about 3 minutes in all): the 160 `.tess` files are byte for byte the same as the first build, so the index, the Leiden table and the reuse table (same SHA-256) are unchanged, and the 160 sidecars differ from the first build only by the new `gloss_indices` field: 8,482 gloss tokens on 4,000 lines of 3,073 documents (this includes EDR's descriptions of symbols, "(protome viri)", which are the same kind of element).

Counts. Documents whose searched text changed against the installed texts: 37,918, of which 36,144 are the line-join fix (below) and 2,214 the expansion rule (83 documents read a numeral followed by its gloss, "IIviri (duoviri)", "IIIIvir (quattuorvir)", "VIvir (sevir)"; 66 read it doubled before). Index: 160 texts, 411,455 lines (installed 411,466), 179,070 documents (same), 2,433,193 postings (2,495,435), 132,731 lemmas (139,134). Leiden table 207,699 rows (207,697). Documents reuse table 4,274 pairs (4,344).

Two findings the install must weigh. (1) The installed Latin texts were written on 8 October before the line-join step of `write_document_tess.py` existed, so a word broken across a line ("Res / titutori") is still two words in the installed index; rebuilding writes it whole in 36,144 documents, which is most of the change in postings and lemmas. (2) The installed index (built 19 October) was also built with an older lemma table than today's code: the same installed texts indexed today give 2,492,461 postings and 134,202 lemmas. The expansion rule itself adds no tokens. 16 EDH/EDR merged documents change which edition their text is taken from, because the expansion counts toward the share of supplied characters that picks the source.

Rollback: put back the four files from their backups and touch the WSGI file.

## 2026-10-23 Lavinium gets its Pleiades id (RUN 17:06 EDT, by hand)

The People & Places entry Lavinium (entity id 41901 in `data/entity_index/entities.sqlite`) had no Pleiades id, so the place could not be shown on a map or matched to dated documents. Set `pleiades_id` to 422960 and `pleiades_candidates` to `["422960"]` in the `entities` table, and `pleiades` to `["422960"]` in the `entity_catalog` row's data (verified on pleiades.stoa.org, 'An ancient city of Latium on the Numicus River'). Backup `entities.sqlite.bak-lavinium-20261023-1706` beside the store. The catalog is cached by file size and modification time, so the live API showed the id without a restart. Checked on the live site at 17:07.

## 2026-10-23 The Shahnameh with its stories, and Warner's translation (built on copies by a delegate; RUN 23:31 to 2026-10-24 00:04 EDT, by hand)

**Status.** INSTALLED. Copies and checksums of the built files are in `~/tesserae-backups/shahnameh_2026-10-23/outputs/` (`SHA256SUMS.txt`); backups of every production file the install touched, with checksums, in `~/tesserae-backups/shahnameh_install_2026-10-23/` (`SHA256SUMS.before`, 7.2 GB, twelve files).

Run record. Backups 23:31 to 23:32. `remap_refs.py --dry-run` against the production checkout at 23:32: every store scanned, nothing untranslatable (fa_index 651,379 rows, window_texts 145,518, descriptions.jsonl 23,150 of 684,650 lines, embeddings meta 99,218, entities 23,629, reuse pairs 277,311, each connections map 33,072, lemma cache 99,230 units, text 99,218 lines). #1165 merged 23:39. The production run at 23:40:46 with `--production` took 40 seconds and rewrote every store in the order above, each check passing; the five `ferdowsi.shahnameh.part.1` windows and the three in each connections map were left alone as planned. `check_remapped_refs.py` at 23:41: 25 checks PASS before its root-wide grep stopped on an unreadable file in `tmp/` owned by the web server; the grep was repeated by hand over data, cache, backend/embeddings and texts (23:42 to 23:49) and found the old shape only in `data/passage_index/descriptions.jsonl.bak-legibus-20261019`, a stale backup from an earlier operation. `data/translations/fa__ferdowsi.shahnameh.json` installed 23:50 (SHA-256 30609efa…, 7,881 blocks, coverage 0.9927), the wsgi file touched and the reader service restarted. Live checks 23:51 to 23:54: the text endpoint returns 99,218 units from 1.1.1 to 857.23.2; the Translation tab shows Warner's verse with the attribution for story 151; a Persian Theme Search returns Shahnameh windows with the new references; Similar Passages cites 'Ferdowsi, Shahnameh 1.1.1'; a Persian Line Search for a word of story 1 gives locus 1.1.1; Go to line 151.1.1 and the couplet margin numbers work in the live Reader (screenshots in the session scratchpad).

Correction to the plan: `desc_fts.sqlite` does NOT rebuild itself. The first golden check (23:54) showed `lexical_boost` false in four Theme Search requests. The word index was rebuilt with `scripts/build_desc_fts.py` (684,650 descriptions, 46 s, cap 4G) at 23:59, swapped in (backup `desc_fts.sqlite.bak-shahnameh-20261023`), the wsgi file touched; after that only the three requests that show Shahnameh references differed, by the new references alone; they were re-recorded and the golden check reads all 69 the same at 00:04. The deleted density cache: the live request timed out at the web server's 300 s limit and the worker recycle killed the computation; it was recomputed under tess-job (cap 10G) by calling `backend.passage_index.connection_density('ferdowsi.shahnameh', scale='fine')` from the production checkout, 00:04 to 00:26 EDT, 16,536 windows, after which the live route answers in 0.2 s with the new references, and `scripts/precompute_passage_density.py` now knows the Persian, Urdu, Arabic, Italian, Old French and Middle High German works and takes `--work`.

Left: the Reader's story list for the 857 stories (follow-up pull request); the stale 877 MB `descriptions.jsonl.bak-legibus-20261019` to delete with the next cleanup.

What. (1) `texts/fa/ferdowsi.shahnameh.tess` (99,218 hemistichs, one running number) is re-tagged `<ferdowsi.shahnameh.S.C.H>`. S is the story in the order of Ganjoor's 857 stories (61 reigns), C the couplet inside the story, H the hemistich. The text of every line is the installed text, unchanged, and the line count stays 99,218. The installed file is the Chronological Persian Poetry Dataset's copy of Ganjoor. Ganjoor today has 99,220 verses. It differs from the installed file in spelling throughout (a final -st written attached, ezafe, spacing), a mean similarity of 0.998 after normalization, and at seven places. Three couplets are only in Ganjoor (old lines 24,979 to 24,980, 25,747 to 25,748 and 51,725 to 51,726). Two couplets are only in the installed file (50,431 to 50,432 and 80,497 to 80,498). Two single lines read differently (31,443 and 52,656). (2) `data/text_structure/ferdowsi.shahnameh/stories.json` lists for each story its number, Persian and English title, reign, first and last reference, the old numbers it covers and its Warner match. `scripts/translations/shahnameh_warner/old_to_new_refs.py` writes `old_to_new_refs.json` (every old running number to its new reference, 3.7 MB) from the story ranges in `stories.json`; the map is not committed, a copy is in the backup folder. (3) `data/translations/fa__ferdowsi.shahnameh.json` has 7,881 units covering 98,498 of 99,218 lines (49,249 of 49,609 couplets), source A. G. and E. Warner, public domain. The scripts are `scripts/translations/align_shahnameh_warner.py` and the folder `scripts/translations/shahnameh_warner/`, where `run_pipeline.sh` gives the order.

Install order, by the project lead, with a dated backup of each file first. (a) On a preview, test the Reader's book grid, the line display and Similar Passages with three-level references before anything is swapped, since the other Persian works use two numbers or one. (b) Swap `texts/fa/ferdowsi.shahnameh.tess`. (c) Rebuild the Persian lemma cache for the work, its inverted index entries and bigram tables, and its passage index windows, whose references change. (d) Generate `old_to_new_refs.json` with the script and apply it to every store that holds old references (`scripts/corpus/rename_work.py` covers seven, saved links and the citation indexes are by hand), then grep production data for `ferdowsi.shahnameh.` followed by a single number. (e) Install `fa__ferdowsi.shahnameh.json` and check the Translation tab on stories 1, 10, 164 and 713. (f) The book-by-book grid should list the 857 stories.

Reference rewrite (the script as written and tested on copies; the run is recorded above). `scripts/corpus/remap_refs.py --map old_to_new_refs.json --work ferdowsi.shahnameh --new-tess ferdowsi.shahnameh.tess --root /var/www/tesseraev6_flask --production` replaces step (d) above. Run it first with `--dry-run`. It scans every store and refuses before writing if any reference of the work is not in the map, then rewrites in this order, with a check after each (old shape gone, row count unchanged): (1) `data/inverted_index/fa_index.db` `lines.ref` and `postings.ref` (99,218 and 552,161 rows); (2) `data/passage_index/window_texts.db` (`window_texts.ref_start` and `ref_end`, 23,150 windows, and `lines.ref`, 99,218 rows) and `descriptions.jsonl` (23,150 lines, streamed to a new file and renamed over the old one; `desc_fts.sqlite` keys on that file's size and mtime and must be rebuilt with `scripts/build_desc_fts.py`, see the run record); (3) `cache/passage_density/*.ferdowsi.shahnameh.*.json` deleted (the next Reader request rebuilds it, 17 minutes on the test copy); (4) `backend/embeddings/fa/ferdowsi.shahnameh.meta.json` `line_refs` (the .npy is untouched); (5) `data/entity_index/entities.sqlite` (7,138 windows, 9,353 mention rows); (6) `cache/reuse_pairs/fa.db` (160,644 + 71,665 pair refs, 45,002 line counts); (7) every `cache/connections_map/*.db` (16,536 windows each); (8) the lemma cache through `scripts/translations/shahnameh_warner/remap_lemma_cache.py`, with `file_hash` re-stamped; (9) the text file, last. The stray work `ferdowsi.shahnameh.part.1` (5 passage windows, 3 in each connections map) already has two-part references and is left alone. `scripts/corpus/check_remapped_refs.py` repeats the checks on a finished root. Run record to be filled in by whoever runs it.

Matching. 845 of 857 stories sit in a matched run with Warner sections. Proper names and the induced word list confirm 824 of them, 14 were set by hand and 7 rest on order and length alone. Eight stories were left untranslated as weak matches and four have no Warner counterpart. Warner's order differs from Ganjoor's in one place (Bahram Gur's night with the merchant), set by hand. Check on 40 couplets drawn at random (seed 1023) and read against Warner's text, 39 cover the story point and 1 does not.

## 2026-10-23 Greek corpus: stray marks removed from 133 files and a Scylax numeral (RUN 16:36 to 16:38 EDT, by hand)
- What: #1133 (1,347 combining accents and breathings removed from consonants, spaces and non-Greek characters in 133 Greek texts, issue #580 part B) and #1128 (Scylax 1.57, an unidentified placeholder read as the koppa numeral) merged and pulled to production at 16:33 and 16:34. The lemma caches of the 134 changed files were rebuilt and the files reindexed.
- Scripts: `scripts/batch_lemma_cache.py grc` (134 built, 1,198 already cached, 0 errors, 29 s, cap 8G); `scripts/corpus/add_texts_to_index.py --db data/inverted_index/grc_index.db.new --language grc --cache-dir cache/lemmas --replace <134 files>` on a copy (1,332 texts, 522,731 lines, lemma_doc_freq rebuilt), then the copy-and-rename swap.
- Backup: `data/inverted_index/grc_index.db.bak-straymarks-20261023-1638`.
- Checked: the golden check (69 recorded requests, all the same) and three Greek line searches (Iliad 1.1 found for the first words of the Iliad). Passage index windows untouched: the window texts of these files still carry the stray marks until the next windows rebuild.
- Held from 2026-10-22 to after the talk of 2026-10-23 13:30 on purpose: a Greek index change hours before a live demonstration.

## 2026-10-23 Coins: a model-written account of each coin type, and vectors that read it (RUN 08:05 EDT, by hand)

Why. The coin search compared a query with vectors of the catalog descriptions only ("Obverse: Head of L. Junius Brutus ... Reverse: Pileus between two daggers"), so a search worded as a meaning missed the coin that carries it: Brutus's EID MAR denarius ranked 11,245th of 46,244 for "the overthrow of tyrants" and 281st for "Brutus and the Ides of March".

What. For each of the 46,244 description rows the BullsAI gateway model (Qwen3.8-27B, temperature 0, no paid service) wrote one or two sentences, at most 45 words, on what the coin shows and what it commemorates, from the description, both legends, the issuer and the dates. Three passes of rules (2026-10-23, 00:49 to 07:20 EDT): legends in the input, no generic military message, VIRT as virtue, an enemy named only when the input or a famous type names it, VOT legends as vows, S C mentioned only with room, a personification given no meaning its legend does not carry, and the plain meaning of a famous occasion (EID MAR as the killing of a tyrant). 37 accounts were then written by hand, mostly the coins of Octavian and Antony from Perusia to Actium, and the VICTORIA NAVALIS types of Vespasian and Titus left without a named war. Vectors of "<description> Meaning: <account>" were made on the campus GPU (multilingual-e5-large, the encoder the site uses, cosine 0.9997 or more against the server's encoder on five rows), four jobs, each input folder deleted the same hour.

Measured. 24 meaning searches with a regex for the right coins (`~/tesserae-backups/coin_gists_2026-10-22/queries.json`): a right coin in the first ten for 9 with the description vectors and 17 with the new ones, mean reciprocal rank 0.336 to 0.553, median first right rank 28 to 2. Brutus for "the overthrow of tyrants" 11,245 to 111, "Brutus and the Ides of March" 281 to 1. Hand grading of random accounts: 36 of 40 right in each pass, the rest mostly vague. On the ten Reader test passages the new vectors did worse (about 9 right of 50 against 17), so the Reader keeps the description vectors.

Run record. The two files were copied into `data/coins/` at 08:05 EDT, each through a temporary name and a rename, mode 664, before pull request #1155 merged; the code then live ignored the new field and file, and the live coin search answered throughout. #1155 was deployed at 08:39. Checks after it: the SHA-256 of both files matched SHA256SUMS.txt; "the conquest of Egypt" on the coin search gave RIC I² Augustus 546, 275A and 275B first; the Battle of Actium's Coins tab listed twelve coins of the Actium war and its celebration, Octavian's naval trophy denarius first; the Battle of Perugia's tab put the L. Antonius denarius (RRC 517) first; the recorded check gave 67 of 69 the same, and the two coin requests that differed did so only by the new `gist` field and were re-recorded.

Files. `data/coins/descriptions_ids.json` replaced by the same rows in the same order with a `gist` field added (text and types checked identical row by row), and `data/coins/descriptions_meaning.npy` added (float16, 46,244 by 1,024, the coin search's vectors). `descriptions.npy` unchanged. Backups `descriptions_ids.json.bak-20261023`. Source folder `~/tesserae-backups/coin_gists_2026-10-22/install4/` with SHA256SUMS.txt. The routes re-read the files when they change, so no restart.

## 2026-10-22 Battle of Actium: three inscriptions from Nicopolis added to its Inscriptions & Papyri (RUN 23:10 EDT, by hand)

Why. The Actium event page showed no inscription or papyrus. Until 2026-10-20 the event's place was in the Ionian Sea off Calabria (38.85 N, 17.11 E), so its 53 documents were southern Italian. The place correction of that night moved it to Actium (38.925 N, 20.725 E) and they dropped out rightly. Nothing came in their place because the inscriptions of Nicopolis, the city Octavian founded beside Actium, carry no Pleiades id in EDH, so the matching step could not place them. One of them is Octavian's own dedication of the camp he set out from to Neptune and Mars after the naval victory "in hac regione" (EDH HD023503, AE 1928).

What. Three rows in `data/events/event_dossiers.sqlite` table `documents` for event Q160387, place Nicopolis (39.0063 N, 20.7316 E), 9.1 km: `edh:HD023503` (dated -29 to -29: EDH gives only the start, the text names Octavian consul for the fifth time, 29 BCE), `edh:HD052963` and `edh:HD064517` (Augustan dedications, -27 to 14). Backup `event_dossiers.sqlite.bak-20261022-actium-nicopolis`. Integrity ok, the event page lists the three with the dedication first, golden check 69 of 69 the same.

Open. Ten more events lost every document in the same place correction (Battle of the Willows 25, Nedao 18, Mons Graupius 5 and others), and documents with no Pleiades id are never matched by place. Both are on the list for the next events pass.

## 2026-10-22 Events store: eleven wrongly placed Theme Search passages removed by hand (RUN 14:43 EDT, by the project lead)

A reading of the passages kept by the entry below found eleven that tell the same people on another occasion or share only a name with the event. They were deleted by rowid from a copy of the live store: Q2666515 Ammianus 20.5.10, Q386578 Hegesippus 4.30.1, Q17622596 Livy 24.19.2, Q21152928 Livy 34.9.9, Q192473 Salvian 7.44, Q55630237 Cicero Fam. 15.4.2, Q16701442 Cassiodorus Var. 8.10.3, Q20009902 Silius 14.121, Q2542852 Sulpicius Severus 2.23.6, Q3625517 Vegetius 4.20, Q3636377 Tacitus Hist. 4.78 (a twelfth, Curtius 4.4.1, had already gone in the occasion check). Result: 624 rows with found_by 'theme search 2026-10-21' in 291 events, 114,269 passages, integrity ok. Starting store sha256 `f739bee113da35dad5947689a6f63315a726cea99d37d5e63c4f10c71b9d8144`, result `3a52c04a27149a8ed161b4ec4aed2e268743d951dcc207f167f00fe4ee69fd1a`. The live file was kept as `event_dossiers.sqlite.bak-20261022-minus12` and the copy moved into place at mode 664.

## 2026-10-22 Events store with checked Theme Search passages for about 280 more events (RUN 14:32 EDT, by the project lead)

The 1,369 Theme Search additions of 2026-10-21 for events not read by hand (`~/tesserae-backups/event_places_2026-10-21/event_dossiers_all_theme.sqlite`) went through `scripts/events/strict_theme_filter.py`: 631 rows in 331 events name the event's place, a participant or the event's own name word in the passage text; the free gateway model (Qwen3.8 27B, thinking off) read those against the event with a quote required (469 YES, 94 MENTION, 68 NO, 50 dropped because the quoted line is not in the passage), 513 kept. A first-pass grading of 120 kept rows read 80 right, 28 partly right, 12 wrong, the wrong ones nearly all the same people on another occasion (Livy's siege of Casilinum of 214 under the siege of 216). `scripts/events/occasion_check.py` then asked the model which occasion each kept passage concerns: 465 this event, 45 another (removed, about half rightly: Alexander at Tyre under Antigonus, Velleius's Actium under the Actium of 435 BCE; about half wrongly: Caesar's first invasion of Britain, Libanius on Olynthus). Result: 635 rows with found_by 'theme search 2026-10-21' in 297 events (167 before, the twenty hand-read events), 114,280 passages, integrity ok. Starting store sha256 `8494849b37186712d197b7b56076123c26ceaf6c8b358b33cd962b3433498ecd`, result `f739bee113da35dad5947689a6f63315a726cea99d37d5e63c4f10c71b9d8144`. The live file was kept as `event_dossiers.sqlite.bak-20261022-strict` and the copy moved into place at mode 664 at 14:32, before the deploy of #1140 reloaded the application.
## 2026-10-22 People & Places store: Pliny's plant, stone and other common words removed from the lower-case rows (RUN 14:56 EDT, by the project lead)

The lower-case scan of the entry below linked a form to a name when their stems matched, so Pliny's raphanus (radish) was filed under Raphania, lapathum (sorrel) under Lapathus, gentiana under Gentianus, galena (lead ore) under Galenus, and 19 further plant, stone, animal and common words (list and reasons in `scripts/entities/drop_lowercase_common_words.py`). The lower-case forms rare outside Pliny were read by hand. Forms that may be the name itself (chironis, memnonis, memnonia, melitis) were left. `drop_lowercase_common_words.py` removed 349 rows from 23 entries on a copy of the live store, recounted their windows and rebuilt the catalog (42,355 entities) and form index (134,925 forms). Lower-case rows 33,640 to 33,291, integrity ok. The tests `tests/test_entit*.py` pass on the copy (129), and the searches Rusellae, Laviniaque, Rhodum, Thyesten, Aeneas, Venus, Chiron, Italia and Hannibal give the same first entry as on the live store. Starting store sha256 `349ab71d7495f3610526f587d889fc48ce842df314c66aef0ad216ffdedd32f9`, result `35fb396b229652302b6399948b9c286ab86cb4b8c3b039541b95679a14be8986`. The live file was kept as `entities.sqlite.bak-20261022-commonwords` and the copy moved into place at mode 664, then the application reloaded.

## 2026-10-22 People & Places store: Pliny's Natural History scanned in lower case, and names found only in editors' notes removed (RUN 12:51 EDT, by the project lead)

Our edition of Pliny's Natural History prints every name in lower case, and the People & Places scan finds names by a capital initial, so the store held 424 mention rows for the Natural History against 51,326 for Livy, and Rusellae lacked NH 3.26 (Loeb 3.51, the colony "rusellana"). `scripts/entities/scan_lowercase_work.py` read the 3,268 passage windows of the Natural History and matched each word against the 40,766 spellings (of 45,468) that the scan had linked in Latin with a capital at least twice, have four letters or more, and never occur as an ordinary lower-case word in the other Latin texts; a word also counts when it is another case form of such a spelling (a stem of five letters or more with a Latin ending, "rusellana" beside "rusellanum") and never occurs lower case elsewhere. Each match is a mention row with matcher 'lowercase' for the entity that spelling is most often linked to, its section found in the window. 33,640 rows added (11,238 of them by the case-form rule), 2,237 windows added, 2,562 entities touched. Samples read by the lead: 34 of 40 right among the plain matches (wrong ones mostly repeat the store's grouping, Nicander under Nicanor, Plautus under Plautius, and "fulgentius", more brightly, read as a name), 27 of 30 among the case-form matches ("galena", lead ore, read as Galen). The same script removed the 1,365 document-mention rows whose spelling occurs only in an editor's note written into an EDR text (between 〈: and 〉), among them two of Rusellae's six (CIL 11.7055, CIL 11.327*). Then the stored catalog and the spelling table were rebuilt. Result: 1,467,273 mention rows, 602,278 document rows, 292,733 windows, integrity ok; Rusellae has four adjective lines (Livy 10.4.5, 10.37.3, 28.45.18, Pliny 3.26) and four inscriptions; Actium, Perusia, Lavinium and Lavinia unchanged apart from Pliny's mentions. Starting store sha256 `cc3098189cac0b599498c2f60aba18d44e7331616b916585222679ff41db957e`, result `349ab71d7495f3610526f587d889fc48ce842df314c66aef0ad216ffdedd32f9`. The live file was kept as `entities.sqlite.bak-20261022-pliny`, the copy moved into place at mode 664 at 12:51, the WSGI file touched, `/api/languages` answered 200.

## 2026-10-22 Edition texts with the Leiden signs for the documents (RUN 11:40 EDT, by the project lead)

The documents' cards showed the searched reading, with every editorial sign removed, so EDR107014 (the Perusine war in the consular fasti of Cupra Maritima) read "... bello Perusino / uf IIviri duoviri", a broken-off word and an editor's gloss shown as words of the stone. `scripts/documents/build_leiden_display.py` rendered the EpiDoc edition of every EDH, EDR, I.Sicily and papyri.info document in `~/tesserae-docs/raw/` with the Leiden signs, and kept a rendering only where its letters, signs and spaces removed, match the indexed reading by at least 75 percent (difflib ratio). Of 257,428 documents (AIO left out, its Greek has its own converter), 207,697 were written, 797 disagree with the indexed reading, 6,207 have an empty edition, and 42,727 have no raw file under the expected name or no indexed line (mostly papyri). Eight workers, about two minutes. The new file `data/documents/leiden.sqlite` (table `leiden`, id and text, 207,697 rows, integrity ok, sha256 `ea80cb3e2fae723372e5dbea0763a7c296a0ad37349f1fdafdcdcf8333d19af6`) was copied in at mode 664 at 11:40, before the code that reads it was deployed. Display only: the documents index and the search are unchanged.
## 2026-10-22 Placeholder papyri removed from the Greek documents index (RUN 20:46 EDT)

**Status.** Installed 20:46 EDT together with the PHI entry below. The 148 further PHI records arrived at 20:06, the PHI build was rerun on all of them, and this removal was applied to its output, so the counts on the installed files differ a little from those below, which were measured on the earlier build. Installed files: index lines 715,251 to 709,072, postings 4,295,927 unchanged, `doc_meta` 76,725 to 70,546, `metadata.db` documents 260,878 to 254,699, display rows 993,270 to 985,618, every kept row identical, integrity ok. sha256 `grc_documents_index.db` 872065a6..., `metadata.db` ed2b2d03..., `aio__attica.restored_words.jsonl` ee4e16d5.... Backups `.bak-20261022-phi-placeholder` beside each live file. The two events-store `documents` rows that pointed at removed papyri (`papyri:115528` under Q11794928, `papyri:832332` under Q132674932) were deleted, backup `event_dossiers.sqlite.bak-20261022-placeholder`, integrity ok. Checks after the reload: `/api/languages` 200, no placeholder line left, `papyri:115528` gives 404, the formula search ἔδοξεν τῆι βουλῆι καὶ τῶι δήμωι (Line Search, documents only, lemma) 824 lines before and 831 after (the joined PHI parts), `aio:IGII2_3346` credits PHI 5619, 5652 with a link for each. Golden check: scope, documents_browse and documents_facets_filter changed as intended (Greek documents 76,725 to 70,546, date groups held only by placeholders gone) and were re-recorded, then 69 of 69 the same.

Why. 6,179 papyri in the Greek documents index have no text but papyri.info's placeholder "This text has not been added to papyri.info yet." They match no search, but they filled Browse lists and counts, and a reader who opened one saw no text.

What. `scripts/documents/remove_placeholder_documents.py INDEX_DB METADATA_DB [--dry-run]` joins all lines of each document, folds whitespace, and removes the document where nothing but the placeholder remains. It deletes the document's rows from `lines`, `postings` (none existed, the placeholder has no lemmas), `doc_meta`, `documents` and `display`, lowers `texts.line_count`, and rebuilds `lemma_doc_freq` only if a posting was deleted (none was, so it is untouched). The six `papyri__unknown_region__*` files that held only placeholders keep their `texts` row with `line_count` 0. It prints counts and an order-independent hash of every kept row per table before and after, and exits 2 if any hash changes. A second run removes nothing.

Counts (run on copies of `~/tesserae-backups/phi_aio_2026-10-22/install2/`, copies and log in `~/tesserae-backups/placeholder_2026-10-22/`). 6,179 distinct ids. Index: lines 715,251 to 709,072, `doc_meta` 76,725 to 70,546, postings 4,295,231 unchanged, `lemma_doc_freq` 274,866 unchanged, `texts` 105 rows, sum of `line_count` 715,251 to 709,072. `metadata.db`: documents 260,878 to 254,699, display rows 993,135 to 985,483 (distinct ids 245,676 to 240,447). Every kept row of every table identical before and after, integrity ok on both files. sha256 of the results: `grc_documents_index.db` `0652ff122baefff290ac96d547d9e578f525adc612167fbd750878d23075b79c`, `metadata.db` `cd0edb358d36ff807f0c4f498b021b4dd0d0e7deea77dff008075d853f6cd23d`. Checks with the Flask test client: the Greek documents search for "ἔδοξεν τῆι βουλῆι καὶ τῶι δήμωι" gives 806 passages on the uncut and the cut files, Browse of papyri lists 67,980 documents before and 61,801 after, and none of the 61,801 has the placeholder as its first line.

Other stores. People & Places `document_mentions` holds 0 rows for the removed ids, `leiden.sqlite` 0, and the events store `documents` table 2 rows. Those files were not changed.

Install. After the PHI install steps, use the files from `~/tesserae-backups/placeholder_2026-10-22/` in place of those of `install2`: `df -h /`, `sha256sum -c` against the values above, dated backups (`.bak-placeholder-20261022`), copy under temporary names at mode 664 and rename, `touch /var/www/tesseraev6_flask/tesseraev6_flask.wsgi`, then `curl .../api/languages` (200) and the formula search (806 passages).

## 2026-10-22 Greek of 809 more Attic inscriptions, from PHI Greek Inscriptions, added to the Greek documents index (RUN 12:48 EDT, installed by the project lead)
## 2026-10-22 Every PHI record of an inscription joined in the Greek documents index (RUN 20:46 EDT, built by a delegate)

**Status.** Installed 20:46 EDT after all 148 further PHI records were fetched (0 missing) and the build script rerun, with the placeholder removal above applied to the result (see that entry for the installed counts and checks). Earlier text: built on copies and checked, not installed. It follows the entry of the same date that added the Greek of 809 inscriptions from PHI Greek Inscriptions, which used only the first PHI number of each inscription. The install is the project lead's, after this pull request is merged and deployed.

Why. 251 of the 815 inscriptions list more than one PHI number, 337 further numbers in all. A stone that PHI records in several parts showed only the first.

What. `aio_convert.py --phi-dir` now reads every number in `all_phi`, in the order AIO lists them, and joins the parts. A gap line stands between parts, because a heading line such as "PHI 8272" would be indexed as text. A part whose text equals an earlier part's (the same stone in two PHI records) is left out. The credit names every number, "Greek text: PHI Greek Inscriptions, The Packard Humanities Institute (PHI 5619, 5652)", the first number is the link of the credit and each further number is a link beside it, from `source_link` rows in the `display` table that the document page shows. `scripts/documents/build_phi_aio_install.sh` runs the whole build on copies and writes the install folder with its checksums, and can be run again when more records are in the PHI folder.

Counts (copy against the live files, after the earlier entry). Documents with several PHI parts 155, repeated parts left out 10, stone lines added 4,663. Index lines 715,251 (unchanged, because a document is one row), AIO characters 1,539,796 to 1,648,797, postings 4,293,812 to 4,295,231, distinct ids equal rows, the 711,801 non-AIO rows unchanged, integrity ok. `metadata.db` documents 260,878 unchanged, display rows 992,955 to 993,135 (180 `source_link` rows), integrity ok. A lemma search of the documents for "ἔδοξεν τῆι βουλῆι καὶ τῶι δήμωι" went from 802 to 806 passages and the exact search stayed at 50.

Known limits. 148 of the further PHI records could not be fetched before the service's daily allowance ran out. Inscriptions that list one of them show the parts that were fetched. Rerun the build script after the records arrive and compare the checksums.

Install (by the lead, after this pull request is merged and deployed). `S` is `~/tesserae-backups/phi_aio_2026-10-22/install2` and `D` is `/var/www/tesseraev6_flask/data`.
1. `df -h /` and `cd $S && sha256sum -c SHA256SUMS.txt`.
2. Dated backups of `$D/inverted_index/grc_documents_index.db` and `$D/documents/metadata.db` with the suffix `.bak-phiaio2-20261022`.
3. Copy under temporary names at mode 664 and rename, the same for `metadata.db` into `$D/documents/`, and `aio__attica.restored_words.jsonl` into `$D/documents/restored/grc/` at mode 664.
4. `touch /var/www/tesseraev6_flask/tesseraev6_flask.wsgi`, then `curl .../api/languages` (200), the formula search (806 passages) and `/api/documents/aio:IGII2_3346?language=grc` (credit "PHI 5619, 5652" with a link for each).

## 2026-10-22 Greek of 809 more Attic inscriptions, from PHI Greek Inscriptions, added to the Greek documents index (RUN time EDT to be filled in by the project lead, built by a delegate)

**Status.** Built on copies and checked, not installed. The install is the project lead's, after the pull request that carries `--phi-dir` is merged and deployed.

Why. The Packard Humanities Institute allowed (permission of 2026-10-22) the use of the Greek texts of the inscriptions that Attic Inscriptions Online (AIO) translates, on the same terms as its Latin texts: indexing and search on Tesserae only, never offered as a download, never placed in the public repository, never passed on. AIO's own Greek and the Berlin edition left 825 of its 3,466 translations without a Greek text here, so those were not shown (entry of 2026-10-20). 815 of the 825 have a PHI number.

What. The 812 distinct PHI records were fetched by the project lead from the PHI inscriptions service into `~/licensed_text/phi_greek_aio/raw/` (outside the repository, mode private). `scripts/documents/aio_fetch.py --html-for-phi` fetched the 815 AIO pages (one request a second, 0 failures) for the date, monument type and findspot. `scripts/documents/aio_convert.py --phi-dir DIR --phi-list phi_needed.json` read the PHI lines for every translation without AIO or Berlin Greek: restorations in square, round and angle brackets kept and flagged as restored, lost stretches (dashes, dotted runs, `c.10-11`) written as the gap sign, surplus letters in braces, superscript note marks, stop signs between numerals and the editors' remarks and Latin words dropped, and a word broken at a line end with a hyphen rejoined where the next line starts with a letter. `aio_metadata.py` wrote the credit rows: the Greek credited "Greek text: PHI Greek Inscriptions, The Packard Humanities Institute (PHI n)" with the link `https://epigraphy.packhum.org/text/n` and the license name "used with permission, for search only", the translation credited to AIO as for the other AIO documents. Date, findspot and region come from AIO's page, with PHI's `not_before` and `not_after` used where the page's date could not be read (32 documents) and Attica as the region for all. Document ids stay `aio:<sourcevolume>_<id>`. `write_document_tess.py --all-short` and `build_documents_index.py` ran unchanged. The documents route marks such a page `indexing_only` and sends `X-Robots-Tag: noindex, noarchive`. The routes that return text are the one document page, the matching line of a search result and the first-line snippets of Browse and Events, and none is a download (a test lists the routes and keeps the connector manifest `site_only` for the page and Browse). The documents index is already left out of the public bundle.

Counts (copy against the live files of 2026-10-22). Documents of source `aio` in the index 2,641 to 3,450 (546 with AIO's Greek, 2,095 Berlin, 809 PHI), lines 714,442 to 715,251, `doc_meta` 75,916 to 76,725, postings 4,264,830 to 4,293,812, the 711,801 non-AIO rows unchanged, distinct ids equal rows, no id with a space, integrity ok on both files. In `metadata.db` documents 260,069 to 260,878 and display rows 992,146 to 992,955, the 257,428 non-AIO rows unchanged, integrity ok. 815 listed, 809 written. Six were left out, one because PHI's record has no line and five because nothing but gaps, Latin words and editors' remarks remained. The rebuilt index equals the live index on every old row and posting. A lemma search of the documents for "ἔδοξεν τῆι βουλῆι καὶ τῶι δήμωι" went from 736 to 802 passages, and the exact search from 47 to 50.

Known limits. 251 of the 815 inscriptions list more than one PHI number in the list file (337 further numbers). Only the number the list names was fetched and converted, so a stone that PHI splits across records may show only one part. The notation of PHI's brackets for corrections by the stonecutter was read by sample and not exhaustively. A few lines keep a hyphen where the word continues after a gap.

Install (by the lead, after the pull request is merged and deployed). `S` is `~/tesserae-backups/phi_aio_2026-10-22/install` and `D` is `/var/www/tesseraev6_flask/data`.
1. `df -h /` and `cd $S && sha256sum -c SHA256SUMS.txt`.
2. Dated backups: `cp -p $D/inverted_index/grc_documents_index.db $D/inverted_index/grc_documents_index.db.bak-phiaio-20261022` and `cp -p $D/documents/metadata.db $D/documents/metadata.db.bak-phiaio-20261022`.
3. Copy under temporary names at mode 664 and rename: `cp $S/grc_documents_index.db $D/inverted_index/grc_documents_index.db.new && chmod 664 ... && mv ...new grc_documents_index.db`, the same for `metadata.db` into `$D/documents/`, and `cp $S/aio__attica.restored_words.jsonl $D/documents/restored/grc/` at mode 664. Keep the folder `$S` and the `licensed_text` folder out of every backup that leaves the machine.
4. `touch /var/www/tesseraev6_flask/tesseraev6_flask.wsgi`, then `curl .../api/languages` (200), the formula search (802 passages) and `/api/documents/aio:AgoraXV_301?language=grc` (credit "Greek text: PHI Greek Inscriptions ... (PHI 231173)" with its link, the AIO translation and credit, `indexing_only` true).
5. The Events and People & Places links for AIO documents are not built (entry of 2026-10-20), so nothing further changes there.

## 2026-10-21 Events store with hand-read Theme Search passages for twenty events (RUN 23:34 EDT, by the project lead)

`scripts/events/add_theme_passages.py` ran over all 1,485 events of the live store (sha256 `5a7443f6b3c40e8972f8008c045d5d713e99983a053c74314f70441859abacb3`, the Perusia store) from 16:30 to 23:34 on the free campus gateway (Qwen3.8 27B), a dry run then `--apply`: 363,553 Theme Search results, 349,249 judged, 1,190 yes and 370 mention, 2,618 failed the second reading, 1,560 rows added. A random sample of 40 added rows across events, read by the lead, was 17 right, 7 partly right (the run-up or the aftermath) and 11 wrong (a shared name, Phintias under Issus, or another event, Julian's Persian war under Rhandeia). Well-documented events did far better than obscure ones. So the additions of nineteen well-known battles (211 rows) were read by hand and 47 removed (Justin's Issus chapter filed under Gaugamela and his Gaugamela chapters under Issus, Livy's Metaurus under Cannae, and others), listed in `scripts/events/theme_additions_keep_2026-10-21.txt`, and `scripts/events/keep_theme_additions.py` removed every other added row. Result: 167 rows with found_by 'theme search 2026-10-21' (23 before, Actium and Perusia, 144 new), 113,812 passages, integrity ok. The full run's store, report and cache are kept in `~/tesserae-backups/event_places_2026-10-21/` for a stricter pass later. Result sha256 `8494849b37186712d197b7b56076123c26ceaf6c8b358b33cd962b3433498ecd`. The live file was kept as `event_dossiers.sqlite.bak-20261021-famous`, the copy moved into place at mode 664 at 23:34, the WSGI file touched, `/api/languages` answered 200, and the Battle of Marathon lists Herodotus 6.108.6, 6.112.3 and 6.116.1.

## 2026-10-21 People & Places store with Lavinia apart from Lavinium (RUN 22:25 EDT, by the project lead)

The 20:41 correction left the princess Lavinia and the town Lavinium in one entry, because the scan files Lavinia, Lavinium and the adjective Lavinian under one name. Each of the entry's 185 mention rows was read by the free gateway model (Qwen3.8 27B, thinking off) with about 600 characters around the word, as the person or as the town or its adjective. The lead read the doubtful answers (neuter forms called the person, Lavinia called the town) and changed 13: nine to the person (Ovid, Fasti 3.633, Vergil, Aeneid 12.194, Vegio, Supplementum 1.37 and 1.539, Carmina Burana 99, and others) and four to the town (Livy 1.14.2, two lines of Gellius 20.11 where Lavinius is a writer). The decisions are in `scripts/entities/lavinia_rows.csv`. `scripts/entities/split_lavinia.py` made the promoted person entry pn:lauinia (80 windows), moved its rows there, made the town the promoted place entry pn:lauinium (105 windows, 76 inscriptions, the old id nm:lauin:main kept as an alias), and rebuilt the stored catalog and the spelling table. 42,355 entities, 1,433,633 mention rows, integrity ok. Starting store sha256 `a61e2c8786cd8f702c716d31a7314ca326dab76099b97af4b087d8567104b886` (the 21:25 store), result sha256 `cc3098189cac0b599498c2f60aba18d44e7331616b916585222679ff41db957e`. The live file was kept as `entities.sqlite.bak-20261021-lavinia`, the copy moved into place at mode 664 at 22:25, the WSGI file touched, `/api/languages` answered 200, and the search for Lavinia lists the person first and the town second.

## 2026-10-21 People & Places store with a table of scanned spellings (RUN 21:25 EDT, by the project lead)

The Reader's "Shared names" links carry a name as the line spells it, and the search matched only headings and listed spellings, so Rhodum, Thyesten or Νέστορ found nothing. In a sample of 1,500 of the 143,042 rare name spellings in `data/passage_index/window_names.db`, 325 found nothing, 22 percent of the links by passage. `scripts/entities/write_form_index.py` added the table `form_entities` to a copy of `data/entity_index/entities.sqlite`: for each of the 132,820 folded tokens in `mention_rows.form_key`, the entity with most of its rows, taken to the list entity a corpus name was merged into or belongs to. The search falls back to it only when nothing else matches. On the same sample 4 of 1,500 still find nothing (Frivolaria, a run-together Syracusanisauxilia, Rigaltianae, Ἀχάζῳ). The fallback lands where the scan filed the word, so a wrong filing there shows here too (Leuconoe opens Leucon). Starting store sha256 `6c63c958adba3344ce196f7c72bf481011cd12cff9374a592854c222fc45c1ae` (the 20:41 Lavinium store), result sha256 `a61e2c8786cd8f702c716d31a7314ca326dab76099b97af4b087d8567104b886`, integrity ok. The live file was kept as `entities.sqlite.bak-20261021-formlink`, the copy moved into place at mode 664 at 21:25, the WSGI file touched, `/api/languages` answered 200.

## 2026-10-21 People & Places store with Lavinium as its own entry (RUN 20:41 EDT, by the project lead)

Searching Lavinium, Lavinia or Laviniaque found nothing. The stage 4 build had merged the corpus name Lavinium (Lavinia, Lavini, Lavinio, 86 lines), a second corpus name for the same forms headed "Lavinarium" (Laviniaque, Laviniam, 11 lines) and the Greek spellings (Λαουίνιον, 29 lines) into the river Labinios (Pleiades 393444), whose Latin spelling Lavinius shares the stem, and a name merged into a list entry is not offered by the search. `scripts/entities/correct_lavinium.py` ran on a copy of `data/entity_index/entities.sqlite`. It merged the two smaller names into Lavinium (`entity_mergeback.apply_merge`), removed Lavinium's merge into the river, moved the aliases pn:lauin and pn:λαουιν and the 76 document mentions in `lauin-` (Laurentes Lavinates) to it, dropped the spelling Lavinius from the river so the catalog does not attach Lavinium to it again, gave Lavinium the search names Lavinium, Lavinia and Lavinian and the Greek heading Λαουίνιον, and rebuilt the stored catalog (`entity_extras.write_catalog`). Result: Lavinium 185 passage windows, 126 lines (Latin 95, Greek 30, English 1), 76 inscriptions, the river 5 Greek windows, 42,354 entities, 1,433,633 mention rows, integrity ok. The entry still holds the name Lavinia beside the town, because the scan cannot tell the princess from the adjective. Starting store sha256 `159d538142d115a1857a0b56dd47e3755a97ae5e5aeedd25ab9bb14f13eb3814` (the live file, unchanged since 2026-10-20 22:56), result sha256 `6c63c958adba3344ce196f7c72bf481011cd12cff9374a592854c222fc45c1ae`. The live file was kept as `entities.sqlite.bak-20261021-lavinium`, the copy moved into place at mode 664 at 20:41, the WSGI file touched, `/api/languages` answered 200, and the search for Lavinium and Lavinia returned the entry.

## 2026-10-21 Objects store without eight out-of-scope records (RUN 14:37 to 14:45 EDT, by the project lead)

Eight records were deleted from a copy of `data/objects/objects.sqlite`: Cleveland cma:1988.5 (Turned Armilla, Hungary, Bronze Age), cma:2000.201 and cma:2000.202 (Vinca Idols, Serbia, Neolithic), and Smithsonian si:A45659-0, si:A326767-0, si:A348946-0, si:A45660-0 and si:A45658-0 (metal fittings from the support of the New York obelisk, dated 1479 BCE by the obelisk). The full-text index was rebuilt (`INSERT INTO objects_fts(objects_fts) VALUES('rebuild')`), and the eight ids were taken out of the `types` lists of `descriptions_ids.json` (seven rows changed, the vectors and their count of 1,210 unchanged), so Theme Search over the objects never points at a missing record. Result: 1,353 objects (Chicago 395, Cleveland 302, Smithsonian 656), integrity ok, "Vinca" finds nothing, "amazons" still 2, the theme query "wine mixed with water at a drinking party" returns ten results. Both live files were kept with the suffix `.bak-20261021-early`, the copies moved into place at mode 664 at 14:37, the WSGI file touched, `/api/languages` answered 200. The public download `public_data/objects.sqlite.tar.gz` was rebuilt with the new file and a README giving the new counts and the removal (sha256 `015cdb16a955d3656715a98d9bf1f8f500c671605aa3b6e99f9a7e440080abc5`, 684,293 bytes), and its entries in `index.json` and `SHA256SUMS.txt` updated. The previous files are in `~/tesserae-backups/objects_2026-10-21/`.

## 2026-10-21 Events store with Theme Search passages for the Battle of Actium (RUN 11:10 to 11:26 EDT, by the project lead)

The project lead plans the Battle of Actium as an example for a presentation on 2026-10-23. Its passages had been gathered on 2026-10-09 from 100 candidates found by names and a coarse score, and the accounts of the battle itself were not among them. `scripts/events/add_theme_passages.py --event Q160387` ran Theme Search on the live site with the event's description, with its name, place and four leading participants, with a one-sentence nameless account of the scene written by the free gateway model, and with two scene queries given by hand (`--extra-query`: "a great sea battle in which a queen's ships suddenly hoist sail and flee, and her lover abandons the fight to follow her" and "a poet calls for drinking and dancing because the mad queen who threatened the city with her fleet has been defeated"), 30 results each. Of 136 results, 24 shared a line with an existing passage. The rest were labeled by the free gateway model with the 2026-10-09 judge's instructions, four a request, a cut-off reply asked again one passage at a time. 19 were added with `found_by` 'theme search 2026-10-21'. The lead then read every Actium label and corrected six by hand: Vegetius 4.32, Strabo 8.4.3, Ammianus 22.16.22, Cassius Dio 51.4.8 and Propertius 3.11.53 from yes to mention, Velleius 2.83.2 to 2.86.2 from mention to yes (it holds his account of the battle at 2.85), and removed Petrarch, Africa 5.177 (a shipwreck simile, judged yes). The event now shows 30 passages, 13 yes and 17 mention. The starting store was the live file (sha256 `daa8c5059e99aea12275b89e6d0b301d39c4bc80f57db532d4244e83ffb9bf22`), the result has sha256 `1b48a6cd8ba54ff7a93ccf17560c4f5eb1e873a58aafb068a38c03a13c4a6a8e`, cache and report in `~/tesserae-backups/event_places_2026-10-21/`. The live file was kept as `event_dossiers.sqlite.bak-20261021-actium`, the copy moved into place at mode 664 at 11:25, the WSGI file touched, and `/api/languages` answered 200.

## 2026-10-21 Events store with participant names set aside where they mean someone else (RUN 10:32 to 11:10 EDT, by the project lead)

The names of an event passage are matched by their forms, so the Battle of Actium listed Marcus Agrippa for Suetonius, Augustus 19.2 ("Agrippam nepotem", Agrippa Postumus), and for Tacitus, Annals 2.51 ("Haterium Agrippam"). `scripts/events/check_participant_names.py` found 3,396 lines (up to three per name and passage) holding a participant's name in the passages not judged unrelated, and asked the free BullsAI gateway model (zai-org/GLM-5.3-Flash, 3,946 requests in all, no failures, about 1.7 a second at 8 in flight) whether the name there means the event's participant. Answers: YES 2,520, NO 830, UNSURE 24, unreadable 22 after the 559 answers cut off in the first pass were asked again with more room. A name is set aside only when every line checked is NO: 693 names in 664 of 113,645 passage rows, moved from `names_matched` to the new column `names_set_aside` with the line and the model's reason. Measured by the lead on two random samples of set-aside lines: 31 of 40 right with 9 unclear and none wrong, and 22 of 30 right with 5 unclear and 3 wrong. The three wrong were one fault, the Caucasian Albanians (Ἀλβανοῖς) read as the Caucasus mountains, so about 4 in 100 set-asides are wrong. A rule on neighboring words (nepos, rex, filius) was measured first and rejected (nearly all of 75 such names were right). The starting store was the live file (sha256 `540736a23af2843051edc984786a960c04d94add8b56d5b9756b9bc5ff2c958e`), the result has sha256 `daa8c5059e99aea12275b89e6d0b301d39c4bc80f57db532d4244e83ffb9bf22`, with the cache and report in `~/tesserae-backups/event_places_2026-10-21/`. The live file was kept as `event_dossiers.sqlite.bak-20261021-names`, the copy moved into place at mode 664, the WSGI file touched, and `/api/languages` checked.

## 2026-10-21 Events store with Actium, Perusia and Cumae under their right Pleiades places (RUN 00:3x EDT, by the project lead)

Three events carried the wrong Pleiades place or none. The battle of Actium of 31 BCE was filed under the Ionian Sea (Pleiades 1046), so its heading read "Ionian Sea". The Battle of Perugia (the siege of Perusia, 41 to 40 BCE) had no Pleiades place, so it had no ancient name. The sea battle of 474 BCE off Cumae was filed under the Bay of Naples (Pleiades Puteolanus Sinus) and placed at the bay's center. A search of every event whose Pleiades place is a sea, gulf, river, mountain or region while its title names a Pleiades site found only these three and Mons Graupius, which stays under Caledonia because the battle's site is unknown. `scripts/events/choose_place_names.py` gained the list `EVENT_PLACES`, which sets the Pleiades id, the ancient name and the modern place of each (Actium and Aktio, Perusia and Perugia, Cumae and Cuma), so a rerun keeps them. The Cumae point was moved to the Pleiades point of Cumae (40.84795, 14.05638) with `scripts/events/fix_event_coords.py` and the corrections file `~/tesserae-backups/event_places_2026-10-21/corrections_cumae.json`. No document is dated near 474 BCE within 100 km, so no document rows changed. The starting store was the live file installed at 00:22 (sha256 `43f41deb...2531`), the result has sha256 `540736a23af2843051edc984786a960c04d94add8b56d5b9756b9bc5ff2c958e`, and the live file was kept as `event_dossiers.sqlite.bak-20261021-eventplaces`. The page now also highlights the ancient place name in the passages.

## 2026-10-20 Events store with the ancient name of each place and the approximate-location flag (built by a delegate, INSTALLED 2026-10-21 00:22 EDT by the project lead)

Before the install the lead graded the 60 sampled headings at 52 right. The eight wrong were fixed by the title spelling rule and three English forms (see the CHANGELOG line of #1094), and the copy was rebuilt from the saved gateway answers. The live store still had the starting checksum and an empty journal file. It was kept as `event_dossiers.sqlite.bak-20261021-placenames`, the copy (sha256 `43f41deb8c5bec43f73f8d000b92c1b8366a38c2281cc5d9c91e2f83a2282531`) was moved into place at mode 664, the WSGI file touched, and `/api/languages` answered 200. Through the live route the Siege of Themiscyra reads Themiscyra, the Battle of Caphyae Caphyae, and the Battle on the Sindhu River is flagged as placed at a region center. 756 events have an ancient name and 234 are flagged.

The project lead asked that the place names of the Events pages be in English and, ideally, the names at the time of the event. The Pleiades names carry the periods in which each is attested, so 776 events with a Pleiades place can be given the name of their period, and the 747 events with no Wikidata point (738 events have one, 1,485 in all) were checked for a stored point that is only the center of a region, sea or river.

The build ran on copies and wrote nothing under `/var/www`. The starting store was a copy of the live `event_dossiers.sqlite`, sha256 `7b5a15c490f9fe7a51910aca323c35d8c5436d5adc10372988718bbf09d4a0fa` (the live file had this checksum at 23:38). `scripts/events/fetch_pleiades_names.py` fetched the Pleiades JSON of the 504 distinct places (one request per second, raw files in `~/tesserae-backups/event_places_2026-10-20/raw/`), `choose_place_names.py` added `events.place_ancient`. It lists each place's names in Latin, English, Greek or no stated language, written in Latin letters, with their attested periods, and asked the free gateway model (zai-org/GLM-5.3-Flash) one question per event, 766 questions, 100 percent answered, 10 NONE. Answers are cached in `~/tesserae-backups/event_places_2026-10-20/gateway_cache.sqlite`, and a table of nine hand overrides (Pherae, Caesarea, Olbia, Panormus, Hamath, Euphrates, Narnia, Dijon, Calagurris) changed 11 events. 756 events are named, 20 are empty, and 439 of the 756 equal the modern place. A sample of 60 events whose heading changes awaits the project lead's grade before install, `fetch_wikidata_places.py` fetched Wikidata (locations, classes) and Wikipedia coordinates, and `classify_event_points.py` classed the 747 events without a Wikidata point (a, a site or settlement: 335, b, the center of a region, sea or river: 234, c, undetermined: 178, of which 170 have no stored point) and added `events.location_approximate` = 1 for the 234. No Wikipedia page of a class b event has a coordinate, so no point changed (`corrections.json` lists none) and `fix_event_coords.py` recomputed no document rows. Tables, row counts (events 1,485, documents 14,372, passages 113,645) and integrity are as in the live store.

To install, check that the live store still has the starting checksum. If it has, copy `~/tesserae-backups/event_places_2026-10-20/install/event_dossiers.sqlite` (sha256 `43f41deb8c5bec43f73f8d000b92c1b8366a38c2281cc5d9c91e2f83a2282531`, rebuilt on 2026-10-21 by the lead with the title spelling rule from the saved gateway answers, no new requests) beside it under a temporary name at mode 664, keep the live file as `event_dossiers.sqlite.bak-<date>-places`, rename over, touch `tesseraev6_flask.wsgi`, check `/api/languages` and one event (`/api/events/Q160387` returns `place_ancient` "Ionian Sea"). If the live file has changed (a relink or a rating), run `choose_place_names.py --apply` (the cached answers cost nothing) and then `classify_event_points.py --apply` on a fresh copy of it with the same raw folders. The route reads both columns only when present, so the code can be deployed before the store.

## 2026-10-20 Events article ratings remade with Claude for every event (RUN 08:25 to 09:12 EDT, by the project lead)

Why. The Events page rates each journal article linked to an event YES, PARTLY or NO, with a one-line reason, and moves the NO articles out of the main list. The project lead found the YES rows for the Sicilian Expedition loose on 2026-10-19. Two stricter wordings and the larger gateway model gpt-oss-120b, measured on 532 articles of four events, gave no clear gain. Claude Sonnet, measured on the same 532 for about $1.60, caught articles rated YES that cite a different passage (Livy on the Gallic sack listed under Veii, Thucydides on Minoa listed under Plataea). The project lead decided on the full run.

Run. A copy of the live events store with the 532 test ratings kept was rated with Claude Sonnet through the Anthropic API from 08:25 to 09:09 (13,157 links, 8.66 million prompt and 0.65 million completion tokens, about $36), and 16 links without a readable answer were asked again (9 answered, 7 empty, left unrated). The ratings table of a fresh copy of the live store was replaced with the 13,698 Claude ratings, after checking that the events, scholarship and passages tables matched row for row (1,485, 15,415, 113,645), and the copy was swapped in at 09:12 (previous file kept as `event_dossiers.sqlite.bak-20261020-glm-ratings`, work files in `~/tesserae-backups/events_ratings_claude_2026-10-20/`). Integrity ok, `/api/languages` 200.

Result. YES 335 to 132, PARTLY 1,007 to 698, NO 12,612 to 12,868. Events with at least one YES article 199 to 87. The Sicilian Expedition shows 8 YES, 47 PARTLY and 78 NO. A spot check of 15 random YES rows outside the test events found all of them about their event ("Roman War Bread" now sits under the Sack of Rome), and of 10 random live YES rows that Claude lowered, all were lowered for a stated and correct reason. `scripts/events/judge_scholarship_relevance.py` now rates with Claude by default (`--provider gateway` keeps the old model), reading the key from `~/.config/tesserae/anthropic.env`, so later relinks rate their new links the same way.

## 2026-10-20 Citation indexes rebuilt with recognizer round 8 (RUN 15:46 to 15:52 EDT, built by a delegate, installed by the project lead)

**Run record.** Pull request #1078 merged and deployed at 15:45, after the project lead ran every citation test on the merged branch against the production abbreviation table (605 passed, none skipped) and read samples of the changes in context: 25 added rows, all real citations of the right work, and 20 removed rows, all of them wrong before (a museum inventory number read as De inventione, "cons. 1230" in a sentence about the cathedral of Burgos, Hyginus's Fabulae read as Plutarch's Fabius, Terence line lists merged into one impossible locus). Both live files were kept as `citations.db.bak-round7-20261020` and `citations_muse.db.bak-round7-20261020`, the delegate's builds copied in under temporary names at mode 664 and renamed over them at 15:46, the app reloaded, `/api/languages` 200, integrity ok, 43,588 and 29,997 rows. The rebuild toolkit was mirrored from main (`.bak-2026-10-20-recog8` copies). The events store was relinked on a copy (`~/tesserae-backups/events_relink_round8_2026-10-20/`): article rows 15,241 to 15,991, events with articles 1,113 to 1,130. The 737 new (event, article) links were rated with Claude Sonnet on the project lead's approval of the cost ("$2 ok"), with `--provider anthropic --spend-approved`, 15:48 to 15:51 (488,582 prompt and 45,627 completion tokens, about $2.15, none failed): YES 16, PARTLY 70, NO 651. The rated copy was installed at 15:52 after checking that the live store had not changed since it was copied (previous file kept as `event_dossiers.sqlite.bak-20261020-round8links`), integrity ok, `/api/languages` 200.


A second hand check of 200 rows drawn at random from the installed round 7 indexes found 19 rows that were not the work cited (ten with a shared abbreviation read as the wrong author, nine not citations of an ancient work) and 14 with a partial locus.

Built. Both indexes were rebuilt from the same article texts with the round 8 recognizer, into a private folder, never over the live files. The EJC index went from 41,724 to 43,588 rows and the MUSE index from 28,559 to 29,997 (after the same cleaning step as before). Most of the growth is references that were unresolved because the abbreviation is shared and the author is named in front (`Plato, Lysis, 207`, `Horace Odes 3.11`, `Ovid, Ars am. 2.691`). The tables are unchanged. The recognizer reads `backend/citations/abbrev_context_rules.json` (new sections `scholia`, `locus_prefix`, `modern_references`, `bare_number_limit`, new rows in `disambiguate` and `veto_before_all`) and `backend/citations/abbrev_aliases.json` (`Ars am.`, `Nat. D.`, `Brev. Vit.`).

To do, in this order. (1) Merge the pull request. (2) Mirror `backend/citations/*.py`, `abbrev_context_rules.json`, `abbrev_aliases.json` and the depth tables into the rebuild toolkit. (3) Rebuild the EJC index with `build_index_v*.py` and the four MUSE journals, then run `clean_muse_index.py` on the MUSE result. (4) Install both with dated backups, touch `tesseraev6_flask.wsgi`, check `/api/languages`, then relink the events Scholarship table with `scripts/events/relink_scholarship.py`. The checks are the row counts above and one lookup each for Oppian's Cynegetica, Ovid's Ars amatoria and Cicero's De natura deorum in the Scholarship tab.

## 2026-10-20 Citation indexes rebuilt with recognizer round 7 and De legibus (RUN 07:04 to 07:06 EDT, built by a delegate, installed by the project lead)

**Run record.** Pull request #1073 merged and deployed at 07:03, after the project lead ran every citation test on the merged branch against the production abbreviation table (576 passed, none skipped) and read twenty De legibus rows with their sentences (eighteen plainly Cicero, two garbled by OCR and plausible). The indexes were installed from the delegate's build, which used the merged code unchanged, as on 2026-10-19. Both live files were kept as `citations.db.bak-round6-20261020` and `citations_muse.db.bak-round6-20261020`, the new files copied in under temporary names at mode 664 and renamed over them at 07:04, the app reloaded, `/api/languages` 200, integrity ok, 41,724 and 28,559 rows, De legibus 145 and 85. The rebuild toolkit at `~/tesserae-backups/ejc_index_2026-09-14/` was mirrored from main at 07:05 (`backend/citations` with `.bak-2026-10-20-recog7` copies, and the two new tables under its `data/citations/`). The events store was relinked to the new indexes on a copy (`~/tesserae-backups/events_relink_2026-10-20/`): article rows 15,265 to 15,241, events with articles 1,113 unchanged, 3 new (event, article) pairs to rate, 1 rated and 2 without a readable answer, integrity ok. It was installed at 07:06 (previous file kept as `event_dossiers.sqlite.bak-20261020-round7links`), and the Sicilian Expedition page answers 133 article rows as before.


A hand check of 200 sampled rows after round 6 left three rules open (a bare number past the end of a one-level work, a line past the end of its book, a parenthesized alternate book number) and the De legibus form list was still waiting for a rebuild.

Built. Both indexes were rebuilt from the same article texts with the round 7 recognizer, into a private folder, never over the live files. The EJC index went from 41,792 to 41,724 rows and the MUSE index from 28,501 to 28,559 (after the same cleaning step as before). The tables the rebuild reads are `data/citations/work_book_line_max.json` and `data/citations/work_single_level_max.json` (both written by `scripts/citations/derive_work_line_limits.py`), and one new row for `cicero.de_legibus` in each of `work_depth.json`, `work_max_line.json`, `work_max_book.json`, `work_depth_journal.json` and `work_section_numbered.json`. The abbreviation table (`data/citations/abbreviations.json`) is unchanged by this pull request. It already carries the De legibus record that `data/citations/abbrev_patch_round7.json` adds.

To do, in this order. (1) Merge the pull request. (2) Mirror `backend/citations/*.py`, `abbrev_context_rules.json` and the five depth tables into the rebuild toolkit, and copy the two new tables to `data/citations/` beside the toolkit's abbreviation table. (3) Rebuild the EJC index with `build_index_v*.py` and the four MUSE journals, then run `clean_muse_index.py` on the MUSE result. (4) Install both with dated backups, touch `tesseraev6_flask.wsgi`, check `/api/languages`, then relink the events Scholarship table with `scripts/events/relink_scholarship.py`. The checks are the row counts above and one Plato Laws and one De legibus lookup in the Scholarship tab.
## 2026-10-20 People & Places store with the contents repairs of pass 4e (RUN 06:52 EDT, built by a delegate, installed by the project lead)

**Run record.** Pull request #1072 merged and deployed at 06:51 after the project lead checked the built store against the live one: Cypriots 952 to 247 rows, Cypris 43 to 748, Carii 14 to 2, Caresus new with 10, Gershom (person) 71 to 58, Geshur 23 to 36, Tarquinia 242 to 229, Tarracina 21 to 34, Nicaeans renamed Nicopolitans with its 11 rows, entities 42,355 to 42,356, mention rows 1,433,635 to 1,433,633, integrity ok, 25 merge tests passing on the merged branch. The live store was copied to `~/tesserae-backups/entity_store_pre_4e_contents_2026-10-20/entities.sqlite` (SHA-256 `edf4400d…`), the new store copied in under a temporary name at mode 664 and renamed over `entities.sqlite` at 06:52 (`c65fa3f7…`, the same as the built file), the app reloaded and `/api/languages` answered 200. The live search answers Cypris (deity), Caresus, Geshur and Tarracina (places), and Nicopolitans and Cypriots (peoples). Left for later passes, from the delegate's report: the Anxur entity (66 rows) is the same town as Tarracina, most of Tarquinia's remaining rows are Greek spellings of king Tarquinius, Crete's Greek label is the genitive Κρήτης, and the Greek Κύπριδος key sits under Aphrodite while Κύπρις sits under Cypris.

Why. The stage 4 review found five entities that hold names belonging to other entities (the Cypriots hold Aphrodite's epithet Κύπρις, the Carii hold the Caresus river and the English word caresses, Gershom holds Geshur, Tarquinia holds Terracina, and the Nicopolitans are headed Nicaeans). It also found that the merge pass read the Greek plural Κρῆτες as a case form of Κρήτη, so the veto that keeps a place apart from its people failed for Greek.

What. `data/entity_index/entities_stage4e_contents.sqlite` is the installed pass 4e store with the merge step re-run from the pass 4c store under the Greek exclusion (58 merges, 4,121 rows moved, as before, with the Cretans now kept apart by the rule and not by the hand list) and then the repairs of `scripts/entity_pass4e_repairs.py`. It holds 42,356 entities (one more, the Caresus river) and 1,433,633 mention rows (two fewer, the dropped English caresses). Integrity check ok. The search baseline of eight queries gives the same answers as the installed store.

Steps for the install, to be run by the project lead.
1. `cp -p /var/www/tesseraev6_flask/data/entity_index/entities.sqlite ~/tesserae-backups/entity_store_pre_4e_contents_2026-10-20/entities.sqlite` (make the folder first).
2. Copy the new store into the entity_index folder under a temporary name, `chmod 664`, rename it over `entities.sqlite`, then `touch tesseraev6_flask.wsgi` and check `curl .../api/languages` returns 200.
3. Search for Cypris, Caresus, Geshur, Tarracina and Nicopolitans on the People & Places page and check each shows its repaired rows.

## 2026-10-20 RUN 20:36 EDT Attic Inscriptions Online and the Berlin Inscriptiones Graecae added to the Greek documents index (built by a delegate, installed by the project lead)

**Run record.** Pull request #1086 merged and deployed at 20:36, after the project lead's review sent it back once (each AIO document had been written as one row per stone line, and words broken at a line end were left split) and the chain stopped once on four lint findings, fixed. Checked before install: 2,641 AIO rows, 2,641 distinct document ids, none with a space, the existing 711,801 rows of the Greek documents index unchanged, one line-break dash left, every Berlin file under CC BY 4.0, checksums OK. Backups `grc_documents_index.db.bak-aio-20261020` and `metadata.db.bak-aio-20261020`, the new files copied in under temporary names at mode 664 and renamed, `aio__attica.restored_words.jsonl` copied into `documents/restored/grc/`, the app reloaded, `/api/languages` 200. `/api/documents/aio:IGII34_1069?language=grc` answers IG II3 4 1069 with the Greek text, the credits "Greek text: Inscriptiones Graecae, Berlin-Brandenburg Academy of Sciences and Humanities" and "Translation: Attic Inscriptions Online (Stephen Lambert)", and the translation. Known limits: some words split across stone lines in the Berlin files carry no break mark and stay split (Ἀπόλλω / νι), and a few stones have their letters spaced apart (IG I³ 1147).

Step 5 (events links) was not run. The events store's "names a participant or the place" rows come from the People & Places store's document_mentions table, which holds no AIO documents. Rebuilding it showed three problems: the builder stops on promoted entities, which have no name strings; a full rebuild drops the 254,647 live rows of promoted entities; and with promoted entities indexed it reproduces 97.5 percent of the live rows but adds 94,635 rows nobody has reviewed. The 10,960 rows it makes for AIO documents were sampled at about half wrong (the personal name Apollonios read as the place Apollonia 175 times, the archon Diotimos as Diotima, the demotics Phrearrios and Sphettios as persons). Nothing was installed from that work, which is kept in `~/tesserae-backups/entity_docmentions_aio_2026-10-20/`. Linking AIO documents to events and to People & Places waits on a matcher for Attic names.

Why. Attic Inscriptions Online (AIO) allowed inclusion of its translations and Greek texts under its Creative Commons license (reply of its chief editor, 2026-10-20), and its technical consultant confirmed that the Greek texts are AIO's own editions. The Greek of 2,095 more of AIO's inscriptions is taken from the Berlin Inscriptiones Graecae digital edition, which carries the Creative Commons Attribution 4.0 license in every file (checked in all 2,111 files).

What. `scripts/documents/aio_fetch.py` fetched the 3,466 inscriptions from the AIO API (one request a second, the project User-Agent, 0 failures) and, for the 2,642 that have a Greek text here, their public HTML pages for the date, monument and inscription types, findspot and the edition heading (the API carries none of these). `scripts/documents/aio_fetch_bbaw.py` fetched 2,111 EpiDoc files from `https://telota.bbaw.de/ig/api/xml/` for the 2,095 inscriptions that link to the Berlin edition. `aio_convert.py` converted them (547 with AIO Greek, 2,095 with Berlin Greek, one of the 2,642 has no usable Greek line), `write_document_tess.py` and `build_documents_index.py` built the index with the unchanged code, and `aio_metadata.py` added the rows to a copy of `metadata.db`. Raw responses are in `~/tesserae-backups/aio_2026-10-20/` (`raw/`, `html/`, `bbaw_raw/`). Document ids are `aio:<sourcevolume>_<id>`, because the slash form `aio:IGII2/18` cannot reach the document route (the page sends the id percent-encoded and a percent-encoded slash does not match `/documents/<doc_id>`).

Counts. In the Greek documents index texts went from 104 to 105, lines 711,801 to 714,442, postings 4,166,593 to 4,265,119, `doc_meta` rows 73,275 to 75,916 (+2,641 documents and +2,641 rows, because each document is one row whose `ref` is the document id, as for the other sources, with the stone lines joined by " / "), integrity ok. In `metadata.db` documents went from 257,428 to 260,069 and display rows from 989,505 to 992,146, integrity ok. A lemma search of the documents for "ἔδοξεν τῆι βουλῆι καὶ τῶι δήμωι" returns 736 passages, 469 of them from 469 AIO documents (before, 267 passages from other sources). Words broken at a line end on the stone are rejoined (`<lb break="no"/>` in AIO's EpiDoc, the en dash or hyphen after the last letter in the Berlin files), and every AIO document has the region Attica. The principal edition is the heading AIO's page gives for 2,293 documents, the first IG reference on the page for 293 and the first SEG reference for 40 (where the heading is an AIO or AIUK number), another reference for 10, and six keep AIO's own number because the page cites no other edition (listed in the pull request). Duplicates by edition number: two Athenian stones are also in EDH (IG II2 1967 as `edh:HD065055`, SEG 21.498 as `edh:HD036976`). Both copies are kept because the texts differ in readings and AIO adds the translation.

Install (by the lead, after the pull request is merged and deployed). `S` is `~/tesserae-backups/aio_2026-10-20/install` and `D` is `/var/www/tesseraev6_flask/data`.
1. `df -h /` and `cd $S && sha256sum -c SHA256SUMS.txt`.
2. Dated backups: `cp -p $D/inverted_index/grc_documents_index.db $D/inverted_index/grc_documents_index.db.bak-aio-20261020` and `cp -p $D/documents/metadata.db $D/documents/metadata.db.bak-aio-20261020`.
3. Copy under temporary names at mode 664 and rename: `cp $S/grc_documents_index.db $D/inverted_index/grc_documents_index.db.new && chmod 664 ... && mv ...new grc_documents_index.db`, the same for `metadata.db` into `$D/documents/`, and `cp $S/aio__attica.restored_words.jsonl $D/documents/restored/grc/` at mode 664.
4. `touch /var/www/tesseraev6_flask/tesseraev6_flask.wsgi`, then `curl .../api/languages` (200), one Greek documents line search and `/api/documents/aio:IGII34_1069?language=grc` (credit names the Berlin edition and AIO).
5. The Events store links documents by place and date and through the Mentions store (entry of 2026-10-18), so it does need the links re-run after the install: `scripts/events/add_naming_documents.py` (dry run, then `--apply`) and the dated-by-place rows of `scripts/events/load_dossiers_sqlite.py`, on a copy of `event_dossiers.sqlite`. The comment in `EventView.jsx` that the collection holds no Attic inscriptions is out of date after this install. The citation indexes of journal articles are not rebuilt by this entry.

## 2026-10-20 Core bundle rebuilt with the corrected Coptic bigram table and installed (RUN 23:24 to 23:44 EDT, 2026-10-19 evening, by the project lead)

Why. The 19 October bundle carried the filtered copy of the 8 August Coptic bigram table, whose seven misplaced letters were found that evening (entry of 2026-10-19 on the Coptic bigram table). The project lead asked for the owed replacement the same night ("Go ahead and do that").

Run. `scripts/corpus/filter_language_caches_by_registry.py --lang cop` ran at 23:24 from the dev checkout against the corrected live table (8 GB cap) and wrote the three filtered copies into `~/tesserae-backups/core_bundle_2026-10-20/filtered/` (bigrams 178,656 keys, 1,805,039 occurrences, 153 documents, every key in the current letter block, frequencies 27,981 keys, 622 translation pairs, 0 restricted ids in any of them). The `substitutes` map in `scripts/ops/public_bundle_exclusions.json` points at that folder. `scripts/ops/build_public_bundle.sh --core` ran from 23:26 to 23:42 (962 seconds) from a worktree on main at `9085292f`, content scan OK. The build stamps its files with the build date, so the four files were renamed from 20261019 to 20261020 and the checksum file rewritten, which is the only change to them. Archive `tesserae-public-core-20261020.tar.zst`, 3,094,153,840 bytes, SHA-256 `0c953d8e2be07fd68e39a783e2c0f744990a0f45388da7ff269da396f20ebf2f`.

Checked from the archive itself. 8,855 members and 8,854 manifest rows, none missing, 0 restricted work ids in either, 47 Sahidic Old Testament texts in. The extracted `cop_index.db` has 153 texts, 0 in the registry, integrity ok, SHA-256 `9a107e07…` as before. The extracted bigram table has 178,656 keys, none in the old letter block and 101,771 in the current one. The bigram, frequency, translation-pair, description and source files and the license file have 0 restricted ids and no mention of the Sahidica. The manifest checksums of the three substituted files equal the checksums of the extracted files.

Installed 23:44. The four files were copied into `/var/www/tesseraev6_flask/static/downloads/bundle/` at mode 664 before the page change merged, since their names are new, `sha256sum -c` printed OK and each link answered 200 with the staged length. The Downloads page, the recipe and the data files reference name the 20 October bundle from the deploy of this pull request, and the four 19 October files are taken off the folder after that deploy.

## 2026-10-19 Coptic bigram table rebuilt in the current letter spelling, measured, restored, then installed on the project lead's decision (RUN 20:36 to 20:38 and 21:51 EDT, by the project lead)

**Installed 21:51.** The project lead read the measured comparison and answered "Install." The respelled table was copied over the live file (backup `cache/bigrams/cop_bigrams.json.pre-respell-20261019-215114.bak`, the 8 August table, SHA-256 `6f5df0de…`), the live file now hashes `eadf6e22…`, the same as the kept copy, and the app was reloaded. Checked through the shipped path: the live Rare Bigrams search for Hebrews against Psalms at the 0.9 bar with no stoplist returns 282 shared pairs and none with the never-seen score of 1.0, where the old table gave 924 with 785 never seen. The recall benchmark is unchanged by the table (see below). The Coptic bigram file inside the public core bundle of this date still carries the old spelling and is replaced at the next bundle build.

**Benchmark under both tables (20:40 to 20:45).** The Hebrews to Psalms recall run of `evaluation/coptic_recall/run_optimization.py` at the production weights, 124 gold pairs, gave recall at 50 0.145, at 100 0.145, at 500 0.161 under each table, with one gold rank moved by one place. The rare-bigram boost is an opt-in setting of Compare Texts that the fusion run does not use, so the published Coptic figures do not depend on the table.

Finding, from the bundle delegate and checked by the lead. The live `cache/bigrams/cop_bigrams.json` of 8 August 2026 holds 190,422 keys, and 108,312 of them contain one of seven Coptic letters (shei, fei, khei, hori, gangia, shima, dei) written at U+2CB3 to U+2CBF, while the lemmas in the live Coptic index (29,323) and in the frequency file write the same letters at U+03E3 to U+03EF, with no key in either place using the other block. A lookup for a word pair containing one of those letters therefore never finds its entry, and `get_bigram_rarity_score` treats a pair absent from the table as the rarest possible (score 1.0). Since hori, gangia and shei stand in some of the commonest Coptic words (the prepositions and the conjunction ϫⲉ among them), a pair of lines that shares such common words has been counted as sharing rare word pairs and has drawn the rare-bigram boost since 8 August.

Run. `scripts/corpus/rebuild_bigrams.py cop` from the production root under a 6 GB cap took 9 seconds (the lemma caches are current) and wrote a table with the same 190,422 keys, 2,030,320 occurrences and 180 documents, all in the current spelling. Backup `cache/bigrams/cop_bigrams.json.pre-rebuild-20261019-2036.bak`. The old table respelled and re-sorted key by key equals the new one in 190,419 of 190,422 keys, so the two differ only in the letters.

Measurement on the eleven strict Hebrews to Psalms gold pairs (`evaluation/coptic_recall/nt_psalm_gold_strict.csv`), rare-bigram boost and count of shared "rare" pairs under each table: Heb 13.6 and Ps 117.6 fell from 27.3 (24 pairs) to 17.7 (12), Heb 3.7 and Ps 94.7 from 18.6 (16) to 13.3 (10), Heb 1.5 and Ps 2.7 from 24.7 (23) to 12.5 (7), Heb 11.6 and Ps 104.3 from 7.0 (7) to 2.8 (2), Heb 4.12 and Ps 118.130 from 2.0 (2) to 0, Heb 13.5 and Ps 36.25 from 3.0 (3) to 1.0 (1), Heb 10.7 and Ps 39.7 from 1.0 (1) to 0, and the other four were unchanged. The boost has been inflated for every Coptic pair, gold or not, so the direction of the effect on ranking is not known from these numbers alone. The Hebrews to Psalms recall benchmark at the production weights is being run under both tables and the comparison goes to the project lead as a decision.

Restored 20:38, before the decision. Because the change alters Coptic scoring where the table is used and the published Coptic figures were measured under the 8 August table, the lead copied the backup over the live file (SHA-256 `6f5df0de…`, identical to the backup) and reloaded the app until the comparison above was in hand. The respelled table was kept at `~/tesserae-backups/cop_bigrams_2026-10-19/cop_bigrams.current_spelling.json` and is the table installed at 21:51. The public core bundle of this date carries the filtered copy of the 8 August table.

## 2026-10-19 Connection map rebuilt with the prose windows of works that have no fine windows, density recomputed (RUN 19:12 to 23:00 EDT, the map 19:12 to 20:24 and the density passes to 23:00, by the project lead)

Why. `verify_text_coverage.py` reported De legibus missing from the connection map after its install, because the map builder and the gutter's density route used fine windows only, and long prose imported since 2026-10-11 has paragraph-sized prose windows alone (#1061, deployed 19:11, `select_subset` in `scripts/build_connections_map.py` and the prose fallback in `connection_density`).

Run. The 16:55 map was backed up to `~/tesserae-backups/connections_map_2026-10-19_1655.db` and `scripts/build_connections_map.py` ran from the production root under a 10 GB cap from 19:12 to 20:19 (67 minutes, peak 7.8 GB), writing over the same fingerprint path `cache/connections_map/25912031-1792438953.1402163328-1792438951.db` (1,120.9 MB). The subset holds 379,035 windows (3,987 of them prose windows of nine works: Salutati De laboribus Herculis 1,349, Diodorus 1,334, Cassius Dio 1,129, Cicero De legibus 147, William of Tyre 16, Appian Foreign Wars 5, Pseudo-Hegesippus 3, Plato Epistles 2, Augustine De trinitate 2), 3,790,350 kept edges and 1,845 distinct works. The app reloaded at 20:24 with the deploy of #1063. `verify_text_coverage.py -l la cicero.de_legibus` now reports connmap ok (described and winvec stay MISSING by design for a prose-only work). The live density route answers 147 windows for De legibus and 1,349 for Salutati through the prose fallback. The golden check against the evening baseline changed in two of 69 requests, `map_author` and `map_cell` (the cache build time and one pair count 69 to 68 as prose windows took places under the per-window neighbor cap), both re-recorded at 20:34 in `~/tesserae-backups/golden/2026-10-19b_live`.

Density. The first `precompute_passage_density.py --language all` pass started with the De legibus install at 16:56 under an 8 GB cap, before the map rebuild, and ended at 22:56 after six hours, 3,322 computed, 3 cached, 0 failed, peak 5.9 GB. It ran with the code loaded before #1061, so for the 35 prose-only works it wrote no file. The second pass, run from 22:57 to 23:00 with the deployed prose fallback, computed the 35 works the first could not (the prose-only parts, among them Cassius Dio 36 to 55, Diodorus 1 to 5 and 18 to 20, Plato Epistles 10 and 12) and skipped the 3,290 cached ones, 0 failed. The density files for the current fingerprint number 3,326, the 3,325 works of the two passes plus one written on demand by the live route for a whole-work id, and the live route answers 147 windows for De legibus.

## 2026-10-19 Ten new public downloads built, checked and installed (RUN 18:20 EDT, built by a delegate, installed by the project lead)

**Run record.** A delegate built the ten archives in `~/tesserae-backups/public_data_2026-10-19_additions/` from copies of the production stores, and the project lead installed them at 18:20 after checking them. Before the install the lead verified every archive against the staged `SHA256SUMS.txt`, confirmed that the 13 lines for the archives already served were unchanged, and queried the built copies directly: the window-text file holds 0 rows of the 29 works in `data/restricted_texts.json` and 0 rows of any Iqbal, Persian or Arabic work (the 40 `sahidic.*` works that remain are the Sahidic Old Testament, whose files are in the public repository), both citation databases hold 41,792 and 28,501 rows with every `sentence` empty, and the People & Places store holds windows in Latin (123,914), Greek (89,611) and English (14,680) only. The lead changed `Licence:` to `License:` and `catalogues` to `catalogs` in the staged `index.html` before the copy. The earlier `index.html`, `index.json` and `SHA256SUMS.txt` are in `~/tesserae-backups/public_data_old_2026-10-19/before_additions/`. After the copy and `chmod 664`, `sha256sum -c SHA256SUMS.txt` in `public_data/` reported OK for all 24 lines (the `index.json` line now passes), and `curl -sI` returned 200 with the listed byte length for each of the ten archives. The build notes follow. `CHECKS.md` in the staging folder holds sizes, checksums and row counts before and after each exclusion, and `scripts/` there holds the build scripts that made the archives.

The ten archives each hold a `LICENSE.txt` and a `README.txt` at the top level. The Urdu index (`ur_index.db.tar.gz`, 12,481,097 bytes) without the four Iqbal collections, made with `scripts/corpus/filter_index_by_registry.py --ids` (texts 18 to 14, lines 58,855 to 54,137). The People & Places store (`entities.sqlite.tar.gz`, 67,926,814 bytes) cut to Latin, Greek and English windows (entities 42,355 to 39,369, windows 290,496 to 228,205, mention rows 1,433,635 to 1,316,921). The events store (`event_dossiers.sqlite.tar.gz`, 18,924,924 bytes) without `judgements` (125,298 rows) and `requests` (16,944 rows). Coins (`coins.tar.gz`, 10,808,721 bytes) as 94,263 ODbL types and 11,913 Corpus Nummorum types. Museum objects (`objects.sqlite.tar.gz`, 693,543 bytes, 1,361 rows). Dictionaries (`dictionaries.tar.gz`, 2,168,240 bytes) with 13,943 accepted review rows exported by a read-only query. The Latin lemma tables (`latin_lemma_tables.tar.gz`, 1,372,614 bytes). Text descriptions (`text_descriptions.tar.gz`, 560,999 bytes, 1,901 entries). Citation indexes (`citations_without_sentences.tar.gz`, 4,434,974 bytes) with the `sentence` column emptied in 41,792 and 28,501 rows. Window texts (`window_texts.db.tar.gz`, 495,728,110 bytes) from 689,207 windows to 460,652 and from 2,755,291 lines to 1,774,889, with zero restricted rows. The decisions and the license of each are in `docs/DECISIONS.md` (2026-10-19, ten more data sets). `index.html`, `index.json` and `SHA256SUMS.txt` for the served folder are in the staging folder, built from the live ones with the new entries added and nothing removed. The live `SHA256SUMS.txt` fails its own check on `index.json` (it lists `536dc303…` and the file is `1bba4ce4…`), and the new one lists the checksum of the new `index.json`.

Checks. Each archive was unpacked and each file compared with its recorded SHA-256, and each SQLite file passed `pragma integrity_check`. A dump of the citation indexes held none of 3,000 sampled sentence fragments from the originals. Raw-byte scans of the entity, events, coin, object, Urdu, description and dictionary files for 1,000 sampled article sentences found none (the only hits are article titles). No `sahidica` string remains in the entity, events, Urdu index or window-text file.

Install steps as run by the lead at 18:20 (step 5 remains for after the merge):
1. `mkdir -p ~/tesserae-backups/public_data_old_2026-10-19/before_additions && cp -p /var/www/tesseraev6_flask/public_data/{index.html,index.json,SHA256SUMS.txt} ~/tesserae-backups/public_data_old_2026-10-19/before_additions/`
2. `cd ~/tesserae-backups/public_data_2026-10-19_additions && cp ur_index.db.tar.gz entities.sqlite.tar.gz event_dossiers.sqlite.tar.gz coins.tar.gz objects.sqlite.tar.gz dictionaries.tar.gz latin_lemma_tables.tar.gz text_descriptions.tar.gz citations_without_sentences.tar.gz window_texts.db.tar.gz index.html index.json SHA256SUMS.txt /var/www/tesseraev6_flask/public_data/` and then `chmod 664` on those twelve files in `public_data/`.
3. `cd /var/www/tesseraev6_flask/public_data && sha256sum -c SHA256SUMS.txt`, which must report OK for every line.
4. `curl -sI https://tesserae.caset.buffalo.edu/tesserae-data/<name>` once per archive, expecting 200 and the byte length listed in `CHECKS.md`. Read the new rows on `https://tesserae.caset.buffalo.edu/tesserae-data/`.
5. After the pull request merges and the front end is rebuilt, open the Downloads page and follow three of the new links.

## 2026-10-19 Three public downloads withdrawn: window texts archive, 14 October bundle, GPU job inputs (RUN 15:40 EDT, by the project lead)

**Run record.** At 15:40 the project lead took three things off the public server. (1) `window_texts.db.tar.gz` (319 MB, served at `/tesserae-data/`). (2) The core bundle of 14 October (`/static/downloads/bundle/`, 3.3 GB, with its checksum, manifest and license file). (3) The four GPU job input folders under `public_data/jobs/` (about 211 MB: `glm-embed-20261003`, `multilang-windows-20261006`, `semantic-fill-20261006`, `semantic-fill2-20261006`). The copies are in `~/tesserae-backups/public_data_offline_2026-10-19/`. In the data folder `index.json`, `index.html` and `SHA256SUMS.txt` were edited to drop the archive, and the earlier versions sit beside the copies in the backup folder with a `.pre` suffix. After the edit the remaining 16 archives verify with `sha256sum -c SHA256SUMS.txt`, and the checksum of `index.json` matches.

The reason is the license. The window-text archive held 1,800 windows of 25 Sahidica works, and the bundle held the Sahidica New Testament (85 manifest entries, including the Coptic text files, their lemma caches and the Coptic index). The Sahidica license allows academic use only and no redistribution, and `data/restricted_texts.json` lists these works. The GPU job inputs held model-written descriptions of windows that include the Sahidica works and of Arabic works (Arabic is a held language), and the raw line text of 586,862 Latin, Greek and English lines, each readable by direct address although the folder listing was refused.

Gated item D7 still owes a window-text archive filtered through `scripts/corpus/filter_index_by_registry.py`'s registry, and a rebuilt core bundle without the restricted texts. The Downloads page says both are withdrawn and no link to either remains in `client/src/components/pages/DownloadsPage.jsx`.

## 2026-10-19 Core bundle rebuilt without the Sahidica New Testament (RUN 20:26 EDT, built by a delegate, installed by the project lead)

**Run record.** Pull request #1063 merged and deployed at 20:25 (the Downloads page offers the bundle again). The project lead checked the archive independently before the merge, from the archive itself: 8,855 members and 8,854 manifest rows with no restricted work id in either, the bundled `cop_index.db` with 153 texts and none from the registry and the same SHA-256 as the filtered copy of the morning (`9a107e07…`), the bundled bigram table, frequency file, translation pairs, text descriptions, text sources and license file with no restricted id and no mention of the Sahidica, and the manifest checksums of the three substituted files equal to the checksums of the extracted files. The automated review asked about the committed absolute substitute paths (accepted as a convention of the one machine the builder reads from), the Coptic letter spelling map (checked against the live table, see the entry on the Coptic bigram table) and the manifest accounting (checked as above). The four files were copied at 20:26 into `/var/www/tesseraev6_flask/static/downloads/bundle/` at mode 664, `sha256sum -c` printed OK, and each of the four links answered 200 with the staged length (the archive 3,094,071,846 bytes). The staging folder `~/tesserae-backups/core_bundle_2026-10-19/` keeps the archive, the filtered copies, the build log and the verification report. The bigram table inside this bundle is the filtered copy of the 8 August table and carries the letter spelling described in the Coptic bigram entry, so an installed copy behaves like the live site in that respect.

The builder (`scripts/ops/build_public_bundle.sh --core`) now takes a `substitutes` map from `scripts/ops/public_bundle_exclusions.json`. Four bundle members cover a whole language or the whole corpus and held the 29 registry works inside them, so each is replaced under its own bundle path by a filtered copy. A listed copy that does not exist stops the build. The plan step also refuses to run when a whole-language file of a language with restricted works is taken as it is, or when an index in the plan still has a registry text in its `texts` table.

| Bundle member | What it held of the 29 works | What was done |
|---|---|---|
| `data/inverted_index/cop_index.db` | 27 texts with their lines and postings (the other two ids, `sahidic.bible` and `sahidica.nt`, have no row) | Replaced by the copy filtered with `scripts/corpus/filter_index_by_registry.py` earlier the same day (153 texts left, 62,919 lines, 1,300,852 postings, integrity ok). Checked again before use, 0 registry texts, 0 orphan rows |
| `cache/bigrams/cop_bigrams.json` | Bigram counts and document counts from 27 works | Replaced by a copy with their counts subtracted: 190,422 keys to 178,656, 2,030,320 occurrences to 1,805,039, 180 documents to 153, 22.6 MB to 12.1 MB |
| `cache/frequencies/cop.json` | Lemma counts from 29 texts (including the two whole-Testament files) | Replaced by a copy with their counts subtracted and the text count and checksum set for the 158 remaining files: 29,323 keys to 27,981, 5,302,761 lemmas to 3,991,547, 1.34 MB to 0.73 MB. The key count equals the filtered index's `lemma_doc_freq` |
| `data/translation_pairs.json` | 108 mentions of Sahidica works in the list of work pairs | Replaced by a copy without the 108 pairs: 730 pairs to 622 |
| `cache/lemmas/cop.json` | No such combined file exists on the server | Nothing to do. The per-work lemma caches of the 29 works are left out by the existing rule |

How the counts were taken out. `scripts/corpus/filter_language_caches_by_registry.py` lemmatizes each registry work with the deployed text processor (and the lemma cache where it is current, as the bigram builder does), subtracts that from the original, and stops if the original does not contain it. It also adds up the whole language the same way and compares. The bigram table matches exactly (216,624 keys differ before a spelling map, 0 after). The frequency file matches except 4 tokens in 2 lemmas (the original was built slightly earlier), so its subtraction stands on the original file. The script writes only to the folder it is given.

Finding. In the production bigram table of 8 August, seven Coptic letters (shei, fei, khei, hori, gangia, shima, dei) are stored as U+2CB3, 2CB5, 2CB7, 2CB9, 2CBB, 2CBD and 2CBF, while the lemmas of the same texts use U+03E3, 03E5, 03E7, 03E9, 03EB, 03ED and 03EF today. A bigram containing one of those letters is therefore never found by a lookup with current lemmas. The filter applies the old code points to its own counts so it subtracts under the keys the table holds. The live table is unchanged by this work.

Build. `build_public_bundle.sh --core --measure` reported 17.33 GB uncompressed in 8,854 files. The build took 1,184 seconds and the content scan passed. Archive `tesserae-public-core-20261019.tar.zst`, 3,094,071,846 bytes, SHA-256 `1d75b5df8a33746bad8a9dbe77bd1a9df7cd28a5c46f85405155e4f027e4bb88`, built from production code commit `6214c215fc2ff8df1c5d740af2f2c0a810b2b382`.

Checked from the archive itself (`verify_bundle.py` and `verify_report.txt` in the staging folder). 8,855 members, 8,854 manifest rows, none missing. 0 members and 0 manifest rows whose work id is in the registry, 0 hits for any of the 29 ids across the whole decompressed stream, 47 `sahidic.*` Old Testament texts still in. The extracted `cop_index.db` has 153 texts, 0 in the registry, integrity ok. The extracted bigram table, frequency file and pair list have 0 hits for the 29 ids. `LICENSES.md` no longer lists the Sahidica license and still names every other source. No citation index, scholarship cache or model folder is among the members.

Install (by the lead, after the pull request is merged and the page deployed). Replace `S` with `~/tesserae-backups/core_bundle_2026-10-19`.
1. Copy `S/tesserae-public-core-20261019.tar.zst`, `S/tesserae-public-core-20261019.tar.zst.sha256`, `S/MANIFEST-core-20261019.tsv` and `S/LICENSES-core-20261019.md` into `/var/www/tesseraev6_flask/static/downloads/bundle/`, mode 664.
2. In that folder run `sha256sum -c tesserae-public-core-20261019.tar.zst.sha256`. It must print OK.
3. Run one `curl -sI https://tesserae.caset.buffalo.edu/static/downloads/bundle/<file>` for each of the four files. Each must answer 200, and the archive must report a length of 3094071846.

## 2026-10-19 Cicero, De legibus added (RUN 15:45 to 18:35 EDT, staged by a delegate, installed by the project lead)

**Run record.** The project lead installed the staged stores into `/var/www/tesseraev6_flask` between 15:45 and 17:00 and finished the checks at 18:35. Installed, with the backup beside each: the Latin index (`la_index.db`, text id 1834, backup `la_index.db.bak-legibus-20261019`), the lemma cache file, the rare-bigram table (`la_bigrams.json.pre-legibus-20261019.bak`), `window_texts.db` (`.bak-legibus-20261019`), the 147 prose windows appended to the passage index (ids, vectors and descriptions all at 684,650, from 684,503), the derived indexes (`desc_fts.sqlite` rebuilt, `desc_vocab.json` and `window_names.db` rebuilt to `.new` files and swapped in, backups `.bak-legibus`), the line vectors, the translation file, the round 7 abbreviation patch (14 forms added for `cicero.de_legibus`, backup `abbreviations.json.bak-20261019-155303`, the rebuild toolkit's copy patched in step) and the connection map (`cache/connections_map/25912031-1792438953.1402163328-1792438951.db`, 62.7 minutes, peak 7.5 GB, 1,105 MB). The reader service was restarted after the passage index changed and the WSGI file touched after each swap. Two stray `build_window_names.py` processes started by `--help` (the script has no argument parser and builds on any invocation) were killed before they wrote anything. The density precompute (`precompute_passage_density.py --language all`) started at 16:56 and was still running at 18:35, rewriting every work's density under the new map fingerprint (about 1,000 of some 1,800 works done). It is a cache warm-up, and the Reader computes a missing file on request.

Checks at 18:35: `verify_text_coverage.py -l la cicero.de_legibus` reports every store ok except `described`, `winvec` and `connmap`. The first two are expected for a prose-scale work (its 42 fine and coarse windows are kept undescribed and unindexed, as the recipe says). The third is a real gap, found here: the connection map builder uses fine-scale windows only and the density route accepts only the fine and coarse scales, so a work whose windows are all prose-sized (De legibus and 36 earlier parts of Cassius Dio, Diodorus, Appian and Augustine) has no map entry and an empty Reader gutter. Recorded as the next item, with the fix (fall back to the prose windows where a work has no fine windows, in both the builder and the density route, then rebuild the map). The reference search ("arma virum", lemma, Latin) returns Ovid, Quintilian and Seneca. A lemma search for "lex est ratio summa" finds the work. Similar Passages for `cicero.de_legibus:prosem:0` answers nine passages. Theme Search for "the origin of law in nature" ranks `cic. leg. 1.20` second (band moderate). The translation route answers for `cic. leg. 1.18` in Barham's words. The golden check against the morning's baseline showed 28 of 69 requests changed, every change traceable to the new text (corpus and index version dates, counts, the map's build time, density values, the new work in the Latin lists), and a fresh baseline was recorded at 18:28 (`~/tesserae-backups/golden/2026-10-19b_live`).

The staging notes follow as written before the install. Every store below was built on a copy in `~/tesserae-backups/de_legibus_2026-10-19/`, with `CHECKS.md` holding the figures.

What. `cicero.de_legibus` (`texts/la/cicero.de_legibus.tess`, reference form `cic. leg. book.section`) from The Latin Library pages `cicero/leg1.shtml`, `leg2.shtml`, `leg3.shtml` (edition not stated, retrieved 2026-10-19). 181 lines: 63, 69 and 49 sections in books 1 to 3, matching the pages' printed brackets, 18,633 words. Speakers are written inline as `Atticus:`, `Quintus:`, `Marcus:`, as `cicero.de_republica.tess` writes `Scipio:`. The pages' u for consonantal v is kept. The pages' bracketed testimonia (Plutarch, Macrobius), lacuna marks and stray characters are removed by the converter. The translation is Francis Barham's 1841 version of the treatise as reprinted in Bohn's Classical Library (ed. C. D. Yonge, 1878 printing), from the archive.org OCR `treatisesofcicer00ciceuoft`, public domain. It numbers the old chapters and not sections, so `scripts/translations/align_de_legibus.py` aligns by speaker turn (89, 83 and 50 English turns against 90, 82 and 50 Latin turns in the three books, with sections that share a turn sharing a unit): 181 of 181 sections covered, 69 units, name check 0.868 on 174 sections that name someone.

Staged outputs (all in the staging folder).
- `out/cicero.de_legibus.tess`, the converter output (identical to the file in the pull request).
- `lemma_cache/la/cicero.de_legibus-7a7421f2112e243d5c876367d0ef7cbc.json` (`batch_lemma_cache.py`, one file, 181 lines).
- `stores/la_index.db.new`: the live Latin index plus text id 1834 (13,380 postings), 1,834 texts, 955,043 lines, `lemma_doc_freq` rebuilt (248,485 lemmas), integrity ok.
- `stage_cache/bigrams/la_bigrams.json`: the rare-bigram table rebuilt over 784 documents (783 live), 3,550,849 keys, 15,345,317 occurrences.
- `stores/window_texts.db.new`: 189 rows added (42 fine and coarse windows from `build_batch_windows.py --upsert-db`, not described, and 147 prose windows) and the 181 line rows. The prose-scale cutter of 2026-10-11 applies by its own rule (a prose work whose median fine window is 8,302 characters against the 3,000 threshold). `prose_windows.py` cut 147 merged windows (median 830 characters, maximum 1,254), ids `cicero.de_legibus:prosem:0` to `:146`. The fine and coarse rows stay in the database as unused rows, as the old Thucydides rows did.
- `windows/descriptions.jsonl`: 147 of 147 described on the university gateway (`describe_prose_windows.py`, Qwen/Qwen3.8-27B-FP8, thinking off, stamp `legibus-20261019`, 0.7 minutes, 0 failures). `windows/vectors.npy` and `windows/ids.json`: 147 x 1024 unit vectors from the site's encoder service (`encode_with_embed_service.py`). `apply_passage_rows.py --mode append` was rehearsed on a staged copy of `ids.json`, `descriptions.jsonl` and `embeddings.npy` only (684,503 to 684,650 ids, vectors and descriptions in step). The live index was not touched.
- `vectors/la/cicero.de_legibus.npy` and `.meta.json`: 181 x 768 line vectors from bowphs/SPhilBerta, raw (mean norm 5.806, no NaN), as the existing files are.
- `translations/la__cicero.de_legibus.json`: the aligned translation (attribution "Francis Barham (1841)").
- `citations/dryrun_round7.txt`: the dry run of `data/citations/abbrev_patch_round7.json` against a copy of the production table: one new work, 14 forms to add, no conflicts with the patch's `allow_overlap` list (Cic., C., CIC. as every Cicero record carries them, Leg. and Laws, which `plato.leges` also carries). Without that list the dry run refuses on 136 conflicts. A bare Leg. stays with Plato by the rule "leg" in `backend/citations/abbrev_context_rules.json` until a rule for `cicero.de_legibus` with an author-context test is added.

Install (by the lead, after the pull request is merged and pulled). Each step runs under `~/bin/tess-job`, one at a time, and `touch tesseraev6_flask.wsgi` follows each swap. Replace `S` with `~/tesserae-backups/de_legibus_2026-10-19`.
1. Latin index swap, with a dated backup. `cp -p data/inverted_index/la_index.db data/inverted_index/la_index.db.bak-legibus-$(date +%Y%m%d)`, then `mv S/stores/la_index.db.new` over it beside the live file (write beside and rename over, because the web account owns the live file).
2. Lemma cache: `cp S/lemma_cache/la/cicero.de_legibus-*.json cache/lemmas/la/`.
3. Bigram table: back up `cache/bigrams/la_bigrams.json` as `la_bigrams.json.pre-legibus-$(date +%Y%m%d).bak`, then copy `S/stage_cache/bigrams/la_bigrams.json` in beside it and rename over.
4. Passage windows: back up `data/passage_index/window_texts.db`, then swap in `S/stores/window_texts.db.new`. Then `scripts/corpus/apply_passage_rows.py --index data/passage_index --sidecar S/windows/descriptions.jsonl --mode append --tag legibus-20261019 --vectors S/windows/vectors.npy --vector-ids S/windows/ids.json` (cap 12G). Check that ids, vectors and descriptions agree (684,650).
5. Derived indexes: `scripts/build_desc_fts.py`, `scripts/corpus/build_desc_vocab.py`, `scripts/corpus/build_window_names.py` to a `.new` file swapped in.
6. Line vectors: `cp S/vectors/la/cicero.de_legibus.* backend/embeddings/la/` (mode 664, group tessdev).
7. Translation: `cp S/translations/la__cicero.de_legibus.json data/translations/` (mode 664).
8. Connection map: `scripts/build_connections_map.py`, cap 10G, about 50 minutes, then `scripts/precompute_passage_density.py --language all`.
9. Abbreviation table: `python scripts/citations/apply_abbrev_patch.py data/citations/abbrev_patch_round7.json data/citations/abbreviations.json --apply`, add the author-context rule for bare Leg., then rebuild the citation indexes when next due.
10. `python scripts/corpus/verify_text_coverage.py` for `cicero.de_legibus`, one Similar Passages and one Theme Search request, the reference searches ("arma virum" must return Ovid, Quintilian, Seneca), a search for a phrase of the work, and `touch tesseraev6_flask.wsgi`.

Rollback: restore the dated backups of the index, the bigram table and `window_texts.db`, remove the new rows from the passage index with `apply_passage_rows.py --mode remove` (ids in `S/windows/ids.json`), delete the lemma cache, vector and translation files, and touch the wsgi file.


## 2026-10-19 Citation indexes rebuilt with recognizer round 6 and installed, the De legibus table slip fixed, events Scholarship table relinked (RUN 11:07 to 11:13 EDT, by the lead)

Why. Round 6 of the citation recognizer (#1049) came from the hand check of 200 round 5 rows: elided ranges, bibliography entries read as citations (a citation followed by `pp.` or a publication year), short titles resolved by the author named nearest, a parenthesized alternate line numbering, comma-separated lists of lines, Cicero's chapter-and-section numbering reduced to the corpus's section numbering (54 works, `backend/citations/work_section_numbered.json`), and a locus beyond the last line or book of a shared short form's default work (Phoen., Juv., Poen.). On the 200 hand-checked rows no correct row changed and 29 of the 41 wrong rows were fixed or dropped (bar 20). A spot check of 20 chapter-and-section rows from the MUSE index found all 20 right.

What. The two indexes were rebuilt by the delegate from the held article text (EJC 42,199 rows to 41,819, MUSE 27,708 to 28,524). Before the install the lead fixed one table slip the delegate found. The abbreviation table sent `Cic. Leg.`, `C. Leg.`, `CIC. Leg.` and `Cic. Legg.` to `cicero.de_amicitia` (De legibus is not in the corpus), so the four forms were removed from that record in the production table `data/citations/abbreviations.json` (backup `.bak-leg-20261019-1107` beside it) and in the rebuild toolkit's copy, and the 27 EJC and 23 MUSE rows they had produced were deleted from the rebuilt files. Installed at 11:07 by copy and rename, the round 5 files kept as `citations.db.bak-round5-20261019` and `citations_muse.db.bak-round5-20261019`, WSGI touched. Installed counts: EJC 41,792, MUSE 28,501, integrity ok. The rebuild toolkit was re-mirrored from `main` (recognizer code, rule tables, depth and maximum tables).

Then `scripts/events/relink_scholarship.py` ran on a copy of the live events store against the installed indexes (article rows 15,219 to 15,265, events with articles 1,088 to 1,113), `judge_scholarship_relevance.py` judged the 245 new (event, article) pairs on the copy (242 judged, 3 replies without a verdict), and the store went live at 11:13 by copy and rename, the previous file kept as `event_dossiers.sqlite.bak-20261019-round5links`. Verdicts in the live store: YES 335, PARTLY 1,007, NO 12,611.

Checks. `/api/languages` 200 after each swap. The live Scholarship route answers for the passages the new rules touched (Cicero, In Verrem 2.4.117 and Plutarch, Marcellus 9 each list articles from the index). The Sicilian Expedition event answers 133 article rows, YES 7, PARTLY 31, NO 95. Open for a later round: a single-level locus beyond a work's last line for forms without a configured rule (7 EJC rows cite Josephus's Life beyond its 430 sections), a parenthesized alternate book number (`Cic. Ac. 1(4).15`), and a fresh 200-row hand check to measure round 6 precision out of sample.

## 2026-10-19 Connector tool find_mentions switched on (RUN 09:01 EDT, by the lead)

Why. People & Places went live for everyone at 08:49 (#1045), and the project lead asked for the connector's mentions tool to follow.

What. `TESSERAE_ENTITY_TOOLS=1` appended to the production `.env` (mode kept 664, a copy of the previous file at `~/tesserae-backups/env_pre_entity_tools_2026-10-19.bak`), WSGI touched at 09:01. The gate in `backend/blueprints/mcp_http.py` is read per request, so the tool `find_mentions` is listed from the next request on.

Checks. `/api/languages` 200. The tools list needs the connector's own token, so the gate function was read in-process with the production environment and returned true. The connector notes that still called the page a trial are corrected in this pull request.

## 2026-10-19 People & Places: repaired entity store (pass 4e) installed and the page live for everyone (RUN 08:46 to 08:49 EDT, by the lead)

Why. The project lead decided on 2026-10-19 to run the repair first and then take People & Places live. The repaired store (#1016, passes 4b to 4e, report in the private research notes) carves names that two people or places share, then merges back the carves that split one referent in two. The merge pass uses a stem rule, a model question (openai/gpt-oss-120b on the campus gateway, 1,158 requests, no failures), and the lead's reading of the 69 merges (55 kept, 14 reverted by a committed hand list, `backend/entity_merge_hand_lists.json`, plus 3 hand merges). Measured on the store: the 180 fixed pairs 90 of 101, the stage 1d fresh 40 at 33 and 38 of 40, new list mentions 25 of 37, wrong splits on fresh samples 3 of 30 after against 11 of 47 before.

What. After #1016 deployed (08:46, production 42d4f11f): the live `data/entity_index/entities.sqlite` (stage 3b store, 340,160,512 bytes) copied to `~/tesserae-backups/entity_store_pre_4e_2026-10-19/entities.sqlite`. The 4e store (349,736,960 bytes, integrity ok, 42,355 entities, 92,151 spellings, 89,442 search names, 290,496 windows, the same 3,297 works as the live store with the 18 October renames) was copied beside it and moved into place, mode 664. WSGI touched 08:47, languages 200. Then #1045 (the trial gate removed, Help rewritten, DECISIONS entry) merged and deployed by the chain at 08:49 with the front end rebuilt.

Checks. Eight entity searches before and after the install: Massilia now returns Massilia (before only Massiliensium), Diocletian its own entry (before Diocles), Hercules five entries with Heracles and Alcides (before two), Carnutes with Carni and Carnuntum, Crete adds Cretenses, Rome 23 entries headed Roma then Rome, Masinissa and Delos unchanged. The golden check against the 2026-10-19_live baseline (which has no entity request) differed in one request, the cross-language search, which the dictionary load of 08:04 changed and which was re-recorded. Reversal: copy the backup back over `entities.sqlite` and touch the WSGI file.

Left for later passes (private list): Roma and Rome are two entries (a Latin against English split), the Cypriots entity holds Κύπρις, the Carii entity holds the Caresus river, the stem rule needs a Greek -es exclusion for the place-against-inhabitants veto, and the connector's entity tools stay behind `TESSERAE_ENTITY_TOOLS`.

## 2026-10-19 Public Coptic index download rebuilt without the Sahidica New Testament (RUN 08:16 EDT, by the lead)

**Run record.** Installed at 08:16 from the staging folder: the 2 September archive, the page and the checksum file copied to `~/tesserae-backups/public_data_old_2026-10-19/` first, then the new `cop_index.db.tar.gz` (39,294,127 bytes), `index.html` and `SHA256SUMS.txt` moved into `public_data/` with mode 664. The page note was reworded to drop the file count (the live index held 27 of the registry's 29 works). `sha256sum -c` passed on every archive, and the archive fetched from `https://tesserae.caset.buffalo.edu/tesserae-data/cop_index.db.tar.gz` has the recorded SHA-256 `4696f27b…324a05`. The page at `/tesserae-data/index.html` shows the note.

Why. The Sahidica New Testament (J. Warren Wells's edition) is held for academic use only, so the public Coptic index download may not carry it. The site search keeps it. The download of 2 September still held it and was left out of the regeneration earlier today for that reason.

What. A copy of the live `cop_index.db` was filtered with `scripts/corpus/filter_index_by_registry.py` (the live file was only read). The registry names 29 works. The live index held 27 of them (the 27 `sahidica.*` books of the New Testament), and the other two ids have no indexed file. Before and after, texts 180 to 153, lines 70,842 to 62,919, postings 1,466,155 to 1,300,852, `lemma_doc_freq` rows 29,323 to 27,981. The checks found no registry work left in `texts`, no orphan rows in `lines` or `postings`, zero occurrences of "sahidica" in a full dump of the copy and a clean integrity check, and lemma lookups through `backend.inverted_index` pointed at the copy answer for three Coptic searches. Peak memory 18 MB. The archive `cop_index.db.tar.gz` is 39,294,127 bytes (SHA-256 `4696f27b8417327148f5c3fab0e84470346ca7dadd9a8a7f0e7c8caabd324a05`), the extracted file 234,057,728 bytes (SHA-256 `9a107e078f1ab487a845505880b90266127db662fc183813035e7c06d50baa55`). The new `index.html` and `SHA256SUMS.txt` are built beside it. The staging folder is `~/tesserae-backups/public_data_2026-10-19_cop/`, with `CHECKS.md`.

Install (by the lead):
1. `mkdir -p ~/tesserae-backups/public_data_old_2026-10-19/cop_before_filter && cp -p /var/www/tesseraev6_flask/public_data/{cop_index.db.tar.gz,index.html,SHA256SUMS.txt} ~/tesserae-backups/public_data_old_2026-10-19/cop_before_filter/`, which keeps the earlier backups in the folder apart.
2. `cp ~/tesserae-backups/public_data_2026-10-19_cop/{cop_index.db.tar.gz,index.html,SHA256SUMS.txt} /var/www/tesseraev6_flask/public_data/`
3. Verify from the public URL. Download `cop_index.db.tar.gz`, compare its SHA-256 with `SHA256SUMS.txt`, and read the Coptic row on the page.

## 2026-10-19 Per-line vector files untracked from git, production and dev checkouts kept whole (RUN 07:42 to 07:54 EDT, by the lead)

**Run record.** #1041 merged by hand at 07:42 (the review and classifier jobs could not fetch a 1,703-file diff; test and build passed). Production: 7,130 files (9.5 GB) copied to `~/tesserae-backups/embeddings_untrack_2026-10-19/production/`, the 66 locally modified tracked files reverted, the pull removed 1,703 files (5,463 left), the copy restored to 7,130, file lists identical, git clean under the folder, the vector census 3,479 files with 0 mismatches, WSGI touched, languages 200, 80 files compared by checksum with the backup with 0 differences. Dev checkout the same at 07:51 to 07:54 (3,626 files, 3.6 GB, 40 checksums compared, 0 differences). The golden check against the 18 October baseline showed 20 of 69 requests different, all from the night's data operations (renames, map and reuse rebuilds, events store) and none a vector-dependent result, and the baseline was re-recorded as `2026-10-19_live`.

Why. The 1,703 files under `backend/embeddings/` (the per-line SPhilBERTa vectors, about 2 GB) were tracked in the public repository since January. Thirty-four of them were replaced in production on 2026-10-18 after the vector census found them out of step with their texts, and twenty show as modified in the dev checkout, so the copies on GitHub were stale and a `git pull` carried a risk of overwriting repaired vectors. The project lead decided on 2026-10-19 to untrack them (#1041). The directory stays in `.gitignore`.

Hazard. A pull of a commit that deletes tracked files removes those files from the working tree, and refuses to merge where a file is modified locally. So the deploy is by hand, not by the merge chain, in this order on each checkout (production first):
1. `rsync -a backend/embeddings/ ~/tesserae-backups/embeddings_untrack_2026-10-19/<checkout>/` and count the files (1,703 tracked plus any untracked ones).
2. `git checkout -- backend/embeddings` (reverts the locally modified tracked files to their old content for the length of the pull).
3. `git pull` (git deletes the 1,703 files from the working tree).
4. `rsync -a` the backup back; count the files again; `scripts/corpus/embedding_census.py` must report 0 mismatches.
5. Touch the WSGI file, `curl .../api/languages`, one Similar Passages request.

Production tail rule added. Every text replacement or repair re-encodes the work's vector file (`scripts/corpus/encode_with_embed_service.py` or the GPU route) and runs the census, alongside the lemma cache, index rows, bigram tables, passage index and reuse tables already listed.
## 2026-10-19 Greek-Latin set A loaded through the review table (RUN 08:04 to 08:08 EDT, by the lead)

**Run record.** Dry run then `--apply` from the production checkout at dc027534 with the production environment sourced inside one shell, `PYTHONPATH` set to the checkout because the script lacked a repository-root path line (added in this pull request). Input 13,831 pairs (0 duplicates), 67 excluded by the lead's hand audit of the 142 Knauer-harvested rows and the 35 rows with a wide Latin target (proper names turned into titles such as Agamemnon to rex, Latin sides that are inflected forms, one-passage glosses, wide common nouns), 4 already in the curated dictionary, 13,760 inserted under source `harvest_2026-10-19_set_a` with status accepted. Accepted rows in the table 183 before, 13,943 after. The production code then reads 13,943 accepted entries and the Greek-Latin dictionary holds 10,864 Greek keys (2,201 before). One cached cross-language job file moved to `~/tesserae-backups/results_cache_pre_seta_2026-10-19/`, WSGI touched 08:05, languages 200. Check: Od. 5.306 against Aen. 1.94 computed fresh on the live site ranks 15 of 526 candidate pairs (semantic 69 percent plus 3 dictionary words), against 7 of 445 on 18 October before the load, so the larger dictionary adds candidates above it. Reversal: `--unload harvest_2026-10-19_set_a --apply`.

Why. Both gateway models accepted 13,831 harvested Greek-Latin pairs (see DECISIONS.md, 2026-10-19). They go in as rows of `dictionary_review` with status `accepted` under one source name, so one command removes them. The CSV already holds the live dictionary's key form (no accents, final sigma as sigma), and the loader applies the app's own normalizer to be safe. Four pairs are already in the curated dictionary and are skipped, leaving 13,827 to insert before the exclusion file.

Commands (production root, production venv; `DATABASE_URL` comes from the environment, read inside the one `bash -c` and never printed):

    JUDGED=DIR_WITH_THE_TWO_CSV_FILES bash -c 'set -a; . /var/www/tesseraev6_flask/.env; set +a; cd /var/www/tesseraev6_flask && venv/bin/python scripts/dictionary/load_review_entries.py --csv "$JUDGED/extra_A.csv" --source harvest_2026-10-19_set_a --exclude EXCLUDE.csv --notes-from "$JUDGED/judged_candidates.csv"'
    # read the dry-run counts, then repeat the same command with --apply
    rm -f /var/www/tesseraev6_flask/cache/asyncjob_xlingual_*.json
    touch /var/www/tesseraev6_flask/tesseraev6_flask.wsgi
    curl -s https://tesserae.caset.buffalo.edu/api/languages | head -c 200

`DIR_WITH_THE_TWO_CSV_FILES` is the folder holding `extra_A.csv` and `judged_candidates.csv`, which are kept outside this repository. If the dictionary does not appear to change after the wsgi touch, find the worker processes with `pgrep -f` and a bracketed pattern (a plain `pkill -f` pattern matches the calling shell). Then rerun Od. 5.306 (`τρὶς μάκαρες Δαναοὶ καὶ τετράκις`) against Aen. 1.94 (`o terque quaterque beati`) in the cross-language search with skip_cache and record the rank (7 of 445 after #1023).

Reversal (one step, then the same cache deletion and wsgi touch):

    bash -c 'set -a; . /var/www/tesseraev6_flask/.env; set +a; cd /var/www/tesseraev6_flask && venv/bin/python scripts/dictionary/load_review_entries.py --unload harvest_2026-10-19_set_a --apply'

Verification. The loader prints inserted, skipped as duplicates, excluded and the accepted-row count before and after. The accepted count rises by exactly the inserted figure, and the reversal returns it to the earlier figure.


## 2026-10-19 Events store: every Scholarship article judged for its bearing on its event, verdicts installed (RUN 03:30 EDT, by the lead)

Why. The Scholarship tab of an event listed every article that cites one of the event's passages, and most cite a passage for another reason (a grammar paper on an optative in Thucydides 7.59 under the Sicilian Expedition). #1037 adds a verdict per article and event from the gateway model and orders and folds the tab by it.

What. `scripts/events/judge_scholarship_relevance.py` read a copy of the live store and asked GLM-5.3-Flash through the campus gateway, for each distinct (event, article) pair, whether the article bears on the event (YES), touches it in part (PARTLY) or cites the passage for another reason (NO), given the article's title, authors, journal and year and up to four sentences in which it cites the event's passages. It wrote the verdicts into a new table `scholarship_relevance` and left the other tables unchanged. 13,212 of 13,213 pairs judged (one reply never gave a verdict, and that article sorts with PARTLY), across 1,082 of 1,083 events with articles: YES 318, PARTLY 952, NO 11,942. The judged store was installed at 03:30 by copy and rename, the previous file kept as `event_dossiers.sqlite.bak-20261019-prerelevance`. The route reads the table when present, so an older store behaves as before. About 15,500 gateway requests, 6 to 7 million prompt tokens, no quota refusal.

Checks. Integrity check ok. The four other tables compare identical to the previous store row for row. The live route for the Sicilian Expedition (Q844289) answers its 132 article rows with YES 7, PARTLY 31, NO 94, the YES rows first in each group, no unjudged row.

Also, RUN 03:40 to 03:48 EDT by the lead. The Scholarship table had been linked from the round 4 citation indexes. `scripts/events/relink_scholarship.py` ran on a copy of the installed store against the round 5 indexes (both files, EJC and MUSE): 14,816 to 15,393 rows, 1,082 to 1,088 events with articles, 499 new (event, article) pairs, 27 pairs gone with the rows round 5 no longer recognizes. `judge_scholarship_relevance.py` then judged the new pairs on the copy in six minutes (it skips pairs already judged), 499 judged and one reply without a verdict. The store went live at 03:48 by copy and rename, the 03:30 file kept as `event_dossiers.sqlite.bak-20261019-round4links`. Verdicts in the live store: YES 335, PARTLY 999, NO 12,377, two pairs unjudged. The Sicilian Expedition now answers 135 article rows, YES 7, PARTLY 32, NO 96.

## 2026-10-19 Citation indexes rebuilt with recognizer round 5 and installed (RUN 02:14 EDT, by the lead); document image links rewritten for two hosts (RUN 00:32 EDT, by the lead)

Why. Round 5 of the citation recognizer (#1035) resolves Pindar book letters across lists of odes, stops page numbers glued after a colon from becoming locus levels, drops lower-case words read as works (317 false Manilius rows), and gives the bare forms Ann., Th., Str., Arr. and Ben. their default authors when the locus shape is firm (a single Roman numeral I, V or X counts as a first level). The image rules of #1030 came from a five-id browser check per host.

What. The two indexes were rebuilt by the delegate from the held article text into a private folder and installed at 02:14 by copy and rename, the previous files kept as `citations.db.bak-round4-20261019` and `citations_muse.db.bak-round4-20261019`, then the WSGI file touched. EJC `citations.db`: 42,212 rows to 42,199 (Arrian Anabasis 7 to 162, Tacitus Annales 545 to 703, Strabo 543 to 603, Manilius minus 317). MUSE `citations_muse.db`: 26,879 to 27,708. A gateway-model reading of a 200-row sample (100 per index) judged 171 correct, 85.5 percent (Wilson interval 80.0 to 89.7), with 17 wrong loci, 7 non-citations and 5 wrong works. The hand check of the same 200 rows (RUN 06:46 EDT, by the lead) puts precision at 159 of 200, 79.5 percent (Wilson interval 73.4 to 84.5), EJC 75 of 100 and MUSE 84 of 100, with 13 wrong works, 10 non-citations and 10 wrong loci, plus 4 rows coarser than the printed locus and 4 rows that keep a chapter-and-section form the corpus does not use (167 of 200, 83.5 percent, if those eight count). The model reading had accepted twelve wrong works and non-citations it could not tell from the sentence alone (Juvencus read as Juvenal, Gellius's Fronto as Fronto's letters, Euripides' Phoenissae as Seneca's). The figure to quote for the round 5 indexes is 79.5 percent. The Events store's Scholarship table (rebuilt 23:33 the night before from the round 4 indexes) was not relinked, so the new rows reach the Scholarship tab of Search One Text and the Reader at once and the Events page at its next relink.

Also. `scripts/documents/fix_image_urls.py --apply` ran on the live `data/documents/metadata.db` at 00:32 after #1030 merged and before any front-end build: 77 rows rewritten (59 U.S. Epigraphy Project image addresses to record pages, 18 old CIL viewer addresses to `cil.bbaw.de/ace/id`), the script's own backup at `metadata.db.bak-2026-10-19`. Still on dead hosts with no rule: 6,931 rows (3,424 bare I.Sicily file names, 2,271 access.bl.uk, 1,064 APIS, and smaller hosts); APIS needs a handle mapping table and the I.Sicily site refuses a headless browser.

Checks. `/api/languages` 200 after the reload. The installed indexes answer the row counts above, and the Events route for the Sicilian Expedition answers with its 132 article rows.

## 2026-10-19 Public data downloads regenerated: five index archives, the passage index as per-language slices, new page and checksums (RUN 00:50 to 01:05 EDT, by the lead)

Why. The downloads page served index archives of 10 February and a single passage-index bundle of 2 September, both far behind the live stores (the Latin index alone was rebuilt on 17 and 18 October), and the single bundle forced one licence onto slices that differ (the design in `scripts/build_passage_index_release.py`: Hebrew CC BY-NC, Coptic CC BY, the rest public domain or Ganjoor). The work-list item from 28 September asked for the regeneration.

What. From the live production stores: `la_index.db`, `grc_index.db`, `en_index.db`, `he_index.db` and (new) `fa_index.db` packed as `.tar.gz`; the passage index split by `build_passage_index_release.py` (run against the production index with its paths pointed at it) into seven slices (la 226,821 windows, grc 164,266, en 27,973, he 5,372, cop 11,400 with 1,800 search-only windows withheld, ur 14,751, fa 219,974) with `index.json`, each packed as `passage_index_<lang>.tar.gz`; a new `index.html` with a date column and the licence in each description; `SHA256SUMS.txt` over every archive. The old `passage_index.tar.gz` and the four replaced archives, with the old page and checksums, were moved to `~/tesserae-backups/public_data_old_2026-10-19/`. Not regenerated: `cop_index.db.tar.gz` (2 September; the Coptic index holds the 29 Sahidica works whose terms are an open decision), the three syntax databases (unchanged since March and May) and `window_texts.db.tar.gz` (2 September; a filtered rebuild without the search-only texts is the gated item D7). `DATA_MANIFEST.json` carries the new checksums (of the extracted files) and sizes, the Persian index as an optional entry, and the slices as a note; `docs/DATA_FILES_REFERENCE.md` rows updated.

Checks. The page answers 200 and the Latin slice and the Latin index archive are served with their full lengths. Italian, Old French and Middle High German windows (Dante, the Chanson de Roland, the Nibelungenlied) are withheld from the release because the release script has no licence entry for them yet.

## 2026-10-19 Latin documents index and documents reuse table rebuilt with the corrected lemma table and installed (RUN 23:56 to 00:21 EDT, by the lead)

Why. The 18 October Latin lemma corrections (#1009) were applied to the literary stores, and the record left the Latin documents index and the documents reuse table as "still to do", since they lemmatize the inscriptions and papyri with the same table.

What. Built in a staging folder (`~/tesserae-backups/docs_rebuild_2026-10-18/`) with the production interpreter: `scripts/documents/build_documents_index.py --language la` over the stage 3 document texts with a fresh lemma cache and scratch folder (the script refuses to write under the live checkout, so the index, cache and scratch all live in staging), then `scripts/reuse/build_documents_reuse_table.py --language la --max-literary-works 10` against the staged index and production's texts and lemma caches, each under an 8 GB cap. The index: 160 text files, 411,466 lines, 179,070 documents, 2,495,435 postings and 139,134 lemmas with a document-frequency count (the installed one had 2,492,715 and 135,748; the corrections split forms that the old table had collapsed). The reuse table: 4,344 pairs (4,173 before), 1,022 of them by the order-free rule, 17.5 minutes for the index and 2 minutes for the pairs. Installed at 00:21 by copy and rename with the previous files kept as `la_documents_index.db.bak-lemfix-20261019` and `cache/reuse_pairs/la_documents.db.bak-lemfix-20261019`, then the WSGI file touched.

Checks. `/api/languages` 200. A documents phrase search for "sit tibi terra levis" answers 1,779 documents with the collection fields present.

Also that night. The connections map cache was rebuilt after the 37 renames changed the index fingerprint (`scripts/build_connections_map.py`, 48.8 minutes, peak 7.53 GB, 1,105 MB) and the superseded cache of 16 October deleted. The live map no longer reports its cache stale and the two map requests of the golden set were re-recorded. The cached cross-language result lists (`cache/asyncjob_xlingual_*.json`, 17 files) were deleted after #1023 loaded the numeral adverbs, because the poll route has no cache bypass and kept serving pre-change lists. Odyssey 5.306 against Aeneid 1.94 then ranks 7 of 445 on the default request. Rule recorded: delete those files after every dictionary change.

## 2026-10-18 Events store: documents that name the participants or the place added, Scholarship table rebuilt against both citation indexes (RUN 23:33 to 23:39 EDT, by the lead)

Why. The Sicilian Expedition's Scholarship tab listed two articles, both on Plutarch's Nicias, because the table had been built before the Thucydides file ids were repaired and from the EJC index alone. The Inscriptions & Papyri tab held the fifty documents nearest the event's place among those dated within its years, none of which named a participant or the place. Pull requests #1021 and #1026 added the rules and the scripts.

What. `scripts/events/add_naming_documents.py` with `--undated drop` on the live `data/events/event_dossiers.sqlite` (dry run first, then `--apply`): 316 events gained 4,375 document rows that the Mentions store links to their participants or place, dated within the event's years widened by fifty, at most fifty per event, nearest first (documents rows 8,138 to 12,513). Then `scripts/events/relink_scholarship.py` on that output against both indexes (`citations.db` and `citations_muse.db`): scholarship rows 4,827 to 14,816 (11,075 articles citing a leading passage, 3,567 citing within the per-book span of the leading passages, 174 commentary rows; EJC 1,359 and 753 distinct articles in the two groups, MUSE 713 and 372). The live file was copied to `event_dossiers.sqlite.bak-20261018-events2`, the new file copied beside it and renamed into place at 23:39, and the previous file's empty write-ahead files removed.

Checks. The live route for Q844289 answers 200 with 154 article rows (65 citing a leading passage, 89 within Thucydides 6 and 7) and 49 dated documents, none naming a participant or Sicily, as the measurement on the copy predicted (the 29 I.Sicily documents that name Sicily are all dated 120 BCE or later). The rows still include articles that cite a passage for another reason (grammar, textual notes), so the route orders each group by title match and citation count in the pull request that carries this entry, and a gateway-model relevance verdict per article is being prepared as the next step.

## 2026-10-18 Thirty-six Greek-titled works and Ferdowsi's Shahnameh renamed to Latin titles in every store (RUN 21:55 to 23:09 EDT, by the lead)

Why. Thirty-six Greek works carried their Greek title inside the file id (`gorgias_of_leontini.ἑλένης_ἐγκώμιον`), so the Theme Search cards showed a Greek title where every other work shows a Latin one, and `ferdowsi.diwan` held the Shahnameh. Pull request #1017 renamed the text files and the records; the list with each new Latin title is in that pull request. The maintainer approved the list.

What. The 37 renames were applied to the production stores with `scripts/corpus/rename_work.py` (tess files, inverted index, lemma cache, embeddings, events store, translations, entity store, with a dated backup of each file it rewrote) and, for the passage index, one pass over ids.json, descriptions.jsonl, window_texts.db and works_by_language.json (27,468 ids and descriptions, 109,063 line rows). The follow-up rewrote the reuse tables (grc.db, fa.db, grc_documents.db) and the two citation indexes, then rebuilt desc_fts.sqlite, desc_vocab.json and window_names.db (1,370 s, 676,872 windows, 3,039,404 window-name pairs), cleared the Greek and Persian results caches and touched the WSGI file. Copies of every store as it stood before the run are in `~/tesserae-backups/rename37_2026-10-18/pre` (7.6 GB), kept a week.

Checks. Lockstep after the run: 684,503 ids = 684,503 descriptions, 689,018 window texts, no old id left in the passage index, the inverted indexes or the entity store. Golden check against the 2026-10-18 baseline: 18 of 69 requests differ, every one explained and re-recorded: the renamed ids and display names (texts, similar passages, status), the self-named works that now show one name (#1018), the trimmed author notes (#1018), the Hamlet locus I.1.1 (#1022), the strong mark order (#1019), the Events payload (#1021), and the connections map reporting its cache stale. The map cache keys on the index fingerprint, which the renames changed, so `scripts/build_connections_map.py` was started at 23:19 under an 8 GB cap, stopped at 23:22 when its first chunk peaked at 7.6 GB (the index has grown since the 5.8 GB peak of September), and restarted under a 10 GB cap with its own estimate of 62 minutes. Until it finishes the map serves the 16 October cache marked stale.

Noted. The passage index already held five windows of a `ferdowsi.shahnameh.part.1` sample with no text file behind it; they now sit in the same work family as the renamed Shahnameh and go when the Shahnameh is re-imported in sections. Backups of the per-row rewrites and the stale backups of 11 to 17 October (61 GB in all) were deleted after the checks.

## 2026-10-18 Latin lemma corrections file applied: caches, index, bigram table, frequency file and reuse table rebuilt and swapped (RUN 12:59 to 13:21 EDT, by the lead)

Why. The live Latin lemmatizer is the lookup table alone, so 6.8 percent of Latin tokens kept their own spelling as their lemma and four table entries were wrong (`c` read as `que`, `actius` as `ago`, `facies` as the verb, `actia` and `distrahor` absent). Pull request #1009 adds `data/lemma_tables/latin_corrections.json` (76,391 forms, of which 5 are hand corrections, 2,774 assimilated-prefix spellings, 73,612 forms filled from the LatinPipe parse under an 80 percent agreement rule, each with its source in `latin_corrections_provenance.csv`) and one loader, `backend/lemma_tables.py`, that every reader of the table calls. The decision and the measurements are in `docs/DECISIONS.md` (2026-10-18). The data stores that hold Latin lemmas had to be rebuilt from the corrected table and swapped together with the code.

What. Built into staging with the production interpreter from the merged code. The stores are the lemma caches (1,833 files, 4 min 29 s, 1.93 GB peak), index with `scripts/corpus/add_texts_to_index.py` (954,862 lines, 17,161,732 postings, `lemma_doc_freq` 248,278 lemmas against 327,498, corpus_version 2026-10-18, 2 min 33 s, 0.64 GB), bigram table (783 documents, 15,326,950 occurrences, 3,548,598 keys, 51 s, 1.10 GB), corpus frequency file (0.66 GB peak). The index equals the caches token for token on 200 random texts (93,935 lines). Against production, 236,324 of 967,935 cache lines (24.4 percent) and 501,995 of 22,128,881 tokens (2.27 percent) carry another lemma. #1009 merged 12:59:02 and pulled on production 12:59:50 (commit 4bba92c2), so the server ran the loader before the swap. The swap by rename ran 13:00:01 to 13:00:49, with `cache/lemmas/la` to `la.bak-lemfix-20261018`, `data/inverted_index/la_index.db` to `.bak-lemfix-20261018`, `cache/bigrams/la_bigrams.json` and `cache/frequencies/la.json` to `.pre-lemfix-20261018.bak`, the staged files moved in, group tessdev, modes 2775 and 664. `cache/lemmas/MANIFEST.json` was rewritten (it now hashes the corrections file, previous copy `.pre-lemfix-20261018.bak`) and `lemma_cache_manifest.py --check` reports in step. `cache/lexical_density/la__*` was deleted, the Latin results cache cleared (2 files) and the WSGI file touched. Latin reuse table (`cache/reuse_pairs/la.db`, the Reader's Reuse tab) rebuilt from the swapped caches with `scripts/reuse/build_reuse_table.py --root` (14 min 31 s at 0.88 GB, 783 works, 655,578 lines, 309,514 pairs against 309,361, the word trigrams unchanged and the commonplace rule reading the new lemmas) and installed 13:21:30 to 13:21:38 by copy to a temporary name, group tessdev, mode 664 and rename over `la.db` and `la_stats.json` with `.bak-lemfix-20261018` copies, WSGI touched again.

Checks. `/api/languages` 200. Reference searches "arma virum": lemma 372 results, exact 31, Ovid, Quintilian, Seneca and Vergil present, every check passed. In the golden check against the 2026-10-17 baseline 14 of 69 requests differ, all of the expected kinds. They are the corpus_version stamp (eight requests), the Latin frequency counts (sum 541,115 to 541,161), lexical density regenerated with a few more connections per line, the rare-word list without `fagos` (now the lemma `fagus`), the rare-pair list with `auena` and `modulor` at Eclogue 10.51, the Reader's stored lemmas (`carus` and `disicio` in place of `caris` and `disiecitque`), and the Eclogues against Calpurnius fusion search sharing 26 of its top 30 with the recording, the four newcomers being parallels found through newly lemmatized forms (modulor and auena with Calpurnius 1.93, corymbus and palleo, hirsutus and barba, cornu and ramosus). A lemma search for `actius` returns Aeneid 3.280 and 8.675 and four Propertius lines, which no search could reach through that lemma before the swap. New golden baseline `~/tesserae-backups/golden/2026-10-18_live`. After the reuse install the Reuse route answers from the new table (meta built 2026-10-18 17:21 UTC, corpus version 2026-10-18) and Aeneid 1.1 has its 9 quotations in the same six works as before. The two Reuse requests of the golden set were re-recorded and all 69 are the same.

Still to do. The Latin documents index (`la_documents_index.db`, built 2026-10-08) and the documents reuse table lemmatize the inscriptions and papyri with the table and were not rebuilt (the collection is behind `?documents=1`). They are to be rebuilt as their own job. The Mentions store takes entity-form lemmas from the table and is rebuilt in the next entity pass. Rollback: reverse the renames (the `.bak-lemfix-20261018` and `.pre-lemfix-20261018.bak` copies), restore the previous manifest, touch the WSGI file.

## 2026-10-18 Reader: Greek and Latin reuse tables rebuilt with the streaming builder and installed (RUN 09:23:36 to 09:24:26 EDT, by the lead)

Why. The two corpus-wide reuse tables (`cache/reuse_pairs/grc.db` and `la.db`, the Reader's Reuse tab) dated from 2026-09-19. Since then texts were imported and on 2026-10-17 both languages' lemma caches were rebuilt table-only and swapped, so the tables' tokens no longer matched the caches (18,713 Greek lines retokenized, 113,047 Latin lines with changed lemmas). A Greek rebuild on 2026-10-17 at 22:19 under the 12 GB job cap sat at 12.2 GB resident for over an hour and was stopped. The cause was `discover_corpus` in `scripts/reuse/build_reuse_table.py`, which loaded every lemma cache (5.7 GB of Greek JSON) into one dictionary before stage 1.

What. Pull request #1007 makes the builder read one cache at a time (`stream_corpus`, `CorpusLoader`), keeps the per-line tokens the commonplace pass needs in a temporary table of the index database, adds `--root DIR` (the checkout whose texts, caches and index are read) and prints resident memory per stage. Output schema and statistics keys unchanged. Both tables were built from the production root into `~/tesserae-backups/reuse_staging_2026-10-18/` under `~/bin/tess-job --wait --fg reuse 12 /usr/bin/time -v`: Greek 16 min 27 s at 0.91 GB resident, Latin 14 min 30 s at 0.89 GB. Installed by copy to a temporary name, group tessdev, mode 664, rename over the live file, for `grc.db`, `la.db` and both `_stats.json`, with `.bak-prestream-20261018` copies of all four beside them, then `tesseraev6_flask.wsgi` touched (the server caches one connection per language).

| | Greek old | Greek new | Latin old | Latin new |
|---|---|---|---|---|
| Works | 898 | 902 | 775 | 783 |
| Lines | 360,805 | 380,800 | 651,535 | 655,578 |
| Pairs | 114,359 | 111,066 | 308,688 | 309,361 |
| Lines with a pair in another work | 87,355 | 80,028 | 197,346 | 197,810 |
| Missing caches | 2 | 0 | 0 | 0 |

The Greek drop in pairs and in lines with a pair comes from Libanius. The old table held the orations under work ids no longer in `texts/` beside the whole files, so lines paired with their own copies (2,079 of the 2,178 retokenized lines that lost a pair are Libanius). Checks before the install (report `research/studies/2026-10-18_reuse_tables_rebuild/REPORT.md`): 10 of 10 random Greek pairs and 9 of 10 Latin pairs from the old table are in the new one (the miss shares one trigram now in 20 lines, the rule wants fewer than 20); Iliad 1.1 in Aelius Aristides, Homer in Plato's Republic (154 pairs both), Odyssey 7.219 in Athenaeus, Aeneid 1.1 in Seneca Ep. 113.25, Aeneid 9.321 in Macrobius 5.9.8 and Vergil in Ovid's Tristia (30 pairs both) are present and identical.

Checks after. `/api/languages` 200. The Reuse route answers from the new tables (meta built 2026-10-18, corpus version 2026-10-17): Aeneid 1.1 (Latin) 9 quotations (claudian.de_consulatu_stilichonis, geoffrey_of_vinsauf.documentum, quintilian.institutio_oratoria, salutati.de_laboribus_herculis, seneca.ad_lucilium_epistulae_morales, valerius_flaccus.argonautica), Iliad 1.1 (Greek) 1 quotations (aelius_aristides.ars_rhetorica). Rollback: rename the four `.bak-prestream-20261018` files over the live ones and touch the wsgi file. This closes the "Still to do" note of the 2026-10-17 cache swap entry.

## 2026-10-18 Semantic vectors: 33 files out of step with their texts re-encoded and replaced (RUN 02:09 to 02:10 EDT, by the lead)

Why. The cross-language counting study of 2026-10-17 found that the production vector file for `statius.achilleid` held 1,127 rows for 1,125 text lines. The semantic channel slices a text's vectors from the top, one row per search unit, so from line 1.662 on every Achilleid line read the vector of the line before it, and from 1.782 on the line two before. The cause is in the 2026-10-06 vector fill (semfill2-1006), which counted tag lines rather than text lines, so a text with empty tag lines (1.661 and 1.781 hold only their tags) got one row per tag line. The record of that operation said every file had one row per text line. It was wrong for these. A census of every production vector file (`scripts/corpus/embedding_census.py census`, 3,479 files across Latin, Greek and English) found 33 out of step with the cached search units: 29 from the tag-line count (22 Latin, among them the Achilleid and its part 1, Ovid Ex Ponto and two parts, Persius and his six parts, Paulinus of Nola, two Petronius files, two Plautus plays, Seneca's Apocolocyntosis and verse fragments, Claudian's Olybrius and Probinus, Walafrid Strabo; 7 Greek, three Euripides plays, Sophocles' Electra, Septuagint Numbers, Exodus and 3 Kingdoms), three with fewer rows than units (Macrobius Saturnalia and its part 2, one line skipped so every row after 617 sat one place early; Septuagint Lamentations, 150 rows for 151 units from a different encoding), Salutati's De laboribus Herculis with 97 rows for 1,450 units (a partial run over scattered lines), and the English New Testament with 7,548 rows for 7,952 units (a truncated run).

What. The 33 files (34 with the Achilleid's part 2, re-encoded with its whole work) were re-encoded on the server's processor with the models the site uses, bowphs/SPhilBerta for Latin and Greek and all-MiniLM-L6-v2 for English, raw vectors in float32 (`scripts/corpus/embedding_census.py rebuild`, 4 min 44 s for the 31 besides the Achilleid at a 1.87 GB peak, 21 s for the Achilleid). Checks before the install: every new file has one row per cached unit; for each of the 29 tag-line cases ten random rows find their nearest neighbor among the old rows at the same or the shifted position at cosine 0.998 to 1.000, so model and normalization match the October encoding; the English file's first 7,548 rows equal the old ones at cosine 1.000; Macrobius' old rows equal the new ones at a one-row shift after row 617. Installed into `backend/embeddings/<lang>/` by atomic rename with the .meta.json beside each (n_lines now equals the unit count), group tessdev, mode 664, and the same files into the dev checkout; the old production and dev files are under `~/tesserae-backups/embeddings_pre_fix_2026-10-18/{prod,dev}/`. Results cache cleared for Latin, Greek and English (2, 1 and 1 files); WSGI touched.

Checks after. `/api/languages` 200. Census after the install reports no file whose rows differ from its cached units. Golden check against the 2026-10-17 baseline at 02:14: all 69 requests the same (none of the recorded requests compares one of the 33 texts through the semantic channel). Any cross-language or fusion search touching one of the 33 texts now reads the right vector for each line. The benchmark numbers of the counting study used an older 1,125-row Achilleid file from the dev checkout, which is a different encoding from the October one (mean cosine 0.977), so a Juhnke recount with the repaired vectors is still to run. Rollback: copy the backup folders back.

## 2026-10-17 Latin and Greek lemma caches, inverted indexes and bigram tables rebuilt table-only and swapped, with a cache manifest (RUN 22:07 to 22:09 EDT, by the lead)

Why. The lemma caches the site reads (`cache/lemmas/la`, `grc`) differed from a fresh table-only lemmatization on 11.7 percent of Latin lines and 4.8 percent of Greek lines: 697 Latin cache files predated the 2026-08-30 table change, many files carried lemmas that only a fallback lemmatizer gives (the production venv has none, so the live server lemmatizes by table alone), and the Greek caches were built by a tokenizer without the 2026-10-01 stray-mark fix (18,713 lines). The Greek index equaled the old Greek cache token for token, and the Latin index recorded corpus_version 2026-08-16 and lacked 178 of the 1,833 Latin text files. The cache carried no record of what built it. Measurement: `research/studies/2026-10-17_lemma_cache_vs_fresh/` (private); the benchmarks the article quotes change by at most one gold row under either input.

What. Caches rebuilt into staging with the production interpreter and `TextProcessor.process_file` at commit cc584a62 (table only, every text file: la 1,833 in 4 min 19 s at 1.92 GB peak, grc 1,332 in 3 min 50 s at 2.34 GB). Indexes rebuilt from those caches with `scripts/corpus/add_texts_to_index.py` into new files (la 954,862 lines, 17.2M postings, 2.02 GB; grc 522,731 lines, 12.3M postings, 2.88 GB; `lemma_doc_freq` inside each, 327,498 and 228,273 lemmas), token for token equal to the caches on 200 random texts per language. Bigram tables rebuilt from the caches (85 s and 83 s). Benchmarks on the staging files: five Latin benchmarks 86.7 percent against 86.8, Lucan 82.6 unchanged, Knauer and Juhnke unchanged. Swap by rename: `cache/lemmas/la` and `grc` moved to `la.bak-lemrb-20261017` and `grc.bak-lemrb-20261017`, `data/inverted_index/la_index.db` and `grc_index.db` to `.bak-idxrb-20261017`, `cache/bigrams/la_bigrams.json` and `grc_bigrams.json` to `.pre-idxrb-20261017.bak`, the staging files moved in, group tessdev, modes 2775 and 664; `cache/lexical_density/la__*` and `grc__*` deleted (they regenerate); Latin and Greek results cache cleared with `backend.cache.clear_cache_for_language` (149 and 17 files); WSGI touched. `cache/lemmas/MANIFEST.json` now records the build date, the code commit, the sha256 of the four lemma tables and of `backend/text_processor.py`, the interpreter and the file counts; `scripts/corpus/lemma_cache_manifest.py --check cache/lemmas` reports in step or stale (#997).

Checks. `/api/languages` 200. Reference search "arma virum": exact 31 (Ovid, Quintilian, Seneca, two Martial lines), lemma 372 at the full list, as before the swap. Golden check against the 2026-10-12 baseline: 65 of 69 the same, three differences are the corpus_version stamp (2026-10-13 to 2026-10-17), one is the capped lemma search for arma virum whose top sixty hold 42 distinct loci instead of 60 by ordering and collapsing alone (lines whose stored lemmas hold arma and vir: 1,298 old, 1,299 new, none lost, all sixty recorded rows present in the full list). New golden baseline recorded to `~/tesserae-backups/golden/2026-10-17_live`, the old folder kept.

Still to do. The Greek reuse table (`cache/reuse_pairs/grc.db`) reads tokens from the caches and is out of step on the 18,713 retokenized lines: rebuild as its own job. Rollback: reverse the four groups of mv commands.

## 2026-10-16 Libanius orations: part-file line tags corrected, stores to follow (RUN 18:06 to 19:10 EDT, by the lead)

The three part files `texts/grc/libanius.orations.part.1/2/3.tess` carried the tag prefixes `libanius. orations_1-11.`, `orations_26-50.` and `orations_51-64.` (848, 805 and 796 lines), a leftover of the 2026-10-13 rename, while the whole file uses `libanius. orations.`. The files are corrected in git (only the prefix moved; `check_whole_vs_parts.py` now passes 145 of 145). Read-only survey of production, 2026-10-16, rows carrying the old prefix: Greek inverted index `lines` 2,438 and `postings` 123,807; lemma caches 1,691, 1,604 and 1,586 refs (one file each, whose file hash no longer matches the corrected text); passage index `window_texts.db` 1,756 windows and 2,449 line rows; `descriptions.jsonl` 1,756 records; reuse table `cache/reuse_pairs/grc.db` 2,715 `pairs` and 2,438 `line_counts` rows; events store 132 `passages` rows; connections map 407 windows; embeddings `meta.json` `line_refs` in all three. Not affected: `ids.json` (ids carry no tag), translations, citation indexes, bigram and frequency caches, `window_names.db`, cached results. Separate gap found in the same survey: the reuse table still names the works `libanius.orations_1-11.part.1`, `_26-50.part.2` and `_51-64.part.3` (2,715 pair rows, plus `line_counts`), and the events store names `libanius.orations_1-11` and its window ids, because the 2026-10-13 rename did not reach them; the dry run reports it, and `scripts/corpus/rename_stale_work_ids.py` (step 7) renames those ids.

Planned steps, in order, by the lead, each inside a memory-capped `tess-job`:
1. Production pull of this pull request (the three part files change). Check `git status` on the production checkout is clean first.
2. Lemma cache: first move the three orphan old-name caches aside with a dated backup (`cache/lemmas/grc/libanius.orations_1-11.part.1-*.json`, `libanius.orations_26-50.part.2-*.json`, `libanius.orations_51-64.part.3-*.json`, and their `.bak-rename-20261013-*` copies), since `rename_work.py` refuses while they sit beside the new ones. Then delete (keeping a backup) `cache/lemmas/grc/libanius.orations.part.{1,2,3}-*.json` and run `scripts/batch_lemma_cache.py grc` (builds only the missing entries). This must come before step 3, because the index rows are read from the cache.
3. Greek inverted index: copy `data/inverted_index/grc_index.db`, run `scripts/corpus/add_texts_to_index.py --db <copy> --language grc --cache-dir /var/www/tesseraev6_flask/cache/lemmas --replace libanius.orations.part.1.tess libanius.orations.part.2.tess libanius.orations.part.3.tess` (it rebuilds `lemma_doc_freq`), then swap the copy in. The dry-run counts for `lines` and `postings` above should fall to 0 for the old prefix.
4. Stores that hold the tag as a string, one at a time with `--only` (each writes a `.bak-fixrefs-<timestamp>` beside the store, and the large SQLite stores are rewritten on a copy and renamed in): `scripts/corpus/fix_ref_prefix.py --root /var/www/tesseraev6_flask --fix libanius.orations.part.1 'libanius. orations_1-11.' 'libanius. orations.' --fix libanius.orations.part.2 'libanius. orations_26-50.' 'libanius. orations.' --fix libanius.orations.part.3 'libanius. orations_51-64.' 'libanius. orations.' --apply --only <store>` for `window_texts`, `descriptions`, `reuse`, `events`, `embeddings`. Run it first without `--apply` and compare with the counts above. The passage index stores (`window_texts`, `descriptions`) are done together, then the lockstep check below.
5. Connections map: rebuild with `scripts/build_connections_map.py` (cap 10G; its key follows the passage index fingerprint, so it rebuilds anyway after any passage index change).
6. Passage index lockstep check: counts in step (`ids.json`, `descriptions.jsonl`, `window_texts.db` windows, `embeddings.npy` rows all 693,611 or the current figure), then one Similar Passages request and one Theme Search request that return a Libanius part-file window with the `libanius. orations.` locus.
7. Stale work ids in two stores, after the ref-prefix applies: `scripts/corpus/rename_stale_work_ids.py --root /var/www/tesseraev6_flask --rename libanius.orations_1-11.part.1 libanius.orations.part.1 --rename libanius.orations_26-50.part.2 libanius.orations.part.2 --rename libanius.orations_51-64.part.3 libanius.orations.part.3` (dry run first, then `--apply`). Dry run against production, 2026-10-16: events store `passages` 46, 22 and 64 rows and `judgements` 57, 30 and 79 rows (by window id; the `work` of those passages is set to the new part id); reuse table `cache/reuse_pairs/grc.db` `pairs` as work_a 19, 21 and 10 and as work_b 922, 869 and 874, and `line_counts` 841, 803 and 794. It refuses, writing nothing, if a new id already has rows in a store. Each store gets a `.bak-stalework-<timestamp>` beside it; the reuse table is rewritten on a copy and renamed in, the events store is updated in place after a WAL checkpoint.
8. `touch tesseraev6_flask.wsgi`, then the golden check and the reference test ("arma virum" returns Ovid, Quintilian, Seneca). Open Libanius Oration 1 in the Reader and confirm the loci read `libanius. orations. 1.1`.
**Run record (18:06 to 19:10).** Step 1: the pull request deployed at 18:06. Step 2: the three orphan old-name lemma caches with their `.bak-rename-20261013-*` copies and the three new-name caches moved to `~/tesserae-backups/libanius_refs_2026-10-16/lemmas/`, then `batch_lemma_cache.py grc` rebuilt the three (1,346 Greek cache files after). Step 3: `add_texts_to_index.py --replace` on a copy of `grc_index.db` (848, 805 and 796 lines, postings 36,671, 45,986 and 41,369, `lemma_doc_freq` rebuilt, 1,332 texts and 522,731 lines), `quick_check` ok, swapped in at 18:09 with the backup `grc_index.db.bak-libanius-20261016`. Step 4: `fix_ref_prefix.py --apply --only` for `window_texts` (1,756 windows, 2,449 line rows), `descriptions` (1,756), `reuse` (2,715 pairs, 2,438 line counts), `events` (132 passages) and `embeddings` (10 refs in each of three meta files); every after-count 0; backups `.bak-fixrefs-20261016-1810xx` beside each store. Step 7 (run before step 5): `rename_stale_work_ids.py --apply`, events passages 46, 22 and 64 and judgements 57, 30 and 79, reuse pairs 941, 890 and 884 and line counts 841, 803 and 794, all after-counts 0, `.bak-stalework-*` backups. Step 5: connections map rebuilt 18:11 to 19:01 (49.9 minutes, peak 7.54 GB under a 10 GB cap, same cache key, 375,048 windows; the Libanius part windows carry the corrected loci and no old prefix remains in any table). Step 6: `ids.json`, `descriptions.jsonl` and `embeddings.npy` all 684,503; `window_texts.db` holds 689,018 rows before and after (it keeps the shadowed chapter windows); `/api/passages/lines` for part 1 returns `libanius. orations. 1.2`; Similar Passages from a part 1 window shows the source as `libanius. orations. 1.1` to `1.30` after the reload. Step 8: wsgi touched 19:01; the reference search (arma virum) returns Ovid, Quintilian and Seneca among 317 results.

**A step the plan lacked.** The first golden run after the reload differed in nine theme and Search One Text requests, with `lexical_boost` false. The Theme Search word index `desc_fts.sqlite` records the size and modification time of `descriptions.jsonl` at build time and disables the boost when they differ, and the prefix rewrite changed both. `scripts/build_desc_fts.py` rebuilt it into a new file (684,503 descriptions, 39 seconds, 799 MB) which was swapped in at 19:08 with the backup `desc_fts.sqlite.bak-libanius-20261016`, followed by a second wsgi touch. Any in-place edit of `descriptions.jsonl` needs this rebuild afterwards. The golden check then differed only in `corpus_version` and `cache_built_at` dates in four requests (two Greek line searches, two map requests), which were re-recorded. One file still carries the old work id, `cache/reuse_pairs/grc_documents_stats.json`, a build log from 9 October that no code reads, left as it is.


## 2026-10-16 Thucydides rename: events store and translations remapped by hand (RUN, by the lead, 2026-10-16 09:45)

The Thucydides rename of 2026-10-15 and 16 (`scripts/corpus/rename_work.py`) did not know two stores, so the Events page still carried the old misspelled id. The lead remapped both by hand on production at 09:45. Events store `data/events/event_dossiers.sqlite`: 740 `passages` rows and 833 `judgements` rows (backup `event_dossiers.sqlite.bak-thucid-20261016-0945`). Translations: the file `grc__thucydides.peloponnesian_war.json` and 3 fields of `data/translations/manifest.json` (`work_id_guess`, `tess_key`, `file`; backup `manifest.json.bak-thucid-20261016-0945`). The old file is kept as `retired_grc__thucydides.peleponnesian_war.json.bak-thucid-20261016-0945`. `rename_work.py` now covers both stores, so the next rename needs no hand step for them: the events store (the three columns, backed up beside itself, checkpointed, verified to hold no row under the old id) and the translations (file, manifest, `links/`). The citation indexes are still remapped by hand, and the reuse tables and the connections map are rebuilt.

## 2026-10-16 Citation recognizer round 4: speech numbers, Pindar, Theocritus, Bacchylides, Libanius (RUN 12:22 to 12:42 EDT, by the lead)

Round 3 left four items. Round 4 builds them. The code ships with the pull request and the table patch is a data step. `Dem.`, `D.`, `Aeschin.`, `Andoc.`, `Din.`, `Lys.`, `Isoc.` and the Pindar forms `Ol.`, `Pyth.`, `Nem.`, `Isth.` were already in the table. What stopped them was the choice among many works (61 Demosthenes files, three Aeschines, four Andocides, three Dinarchus). Changes:
- `backend/citations/speech_numbers.json`: speech number to file for Demosthenes (1 to 61, since 62 Exordia and 63 Letters are tagged `ex.` and `L.` and have no numeric entry), Aeschines, Andocides, Dinarchus, Lycurgus, and the Bacchylides ranges (odes 1 to 14 epinicians, 15 to 20 dithyrambs). The extractor picks the file from the first locus level and keeps the locus as the file tags it (`Dem. 21.72` is `demosthenes.against_midias` locus `21.72`, because these files are tagged speech.section and `work_depth.json` records depth 2). `Andoc. 1` is the file `andocides.on_the_mysteries`, which also holds speeches 2 to 4.
- Pindar: `pindar.odes` loci get the book letter in front (`o.1.1`, `p.4.299`, `n.3.5`, `i.8.70`) from the form that named the work. The bare letters `O.`, `P.`, `N.`, `I.` and `Is.` count only with Pindar named in the sentence or the one before. `P.` and `N.` need two locus levels, because one number is a page or a note. `I.` alone stays unresolved. `Pind. P.`, `Pind. N.` and `Pind. I.` still reach the part files, unchanged.
- Theocritus: `Theoc.` and `Theocr.` mean the idylls unless `Ep.` is written (epigrams). `Id.` counts only with Theocritus named. Bacchylides: `B.` counts only with Bacchylides named and the ode number chooses the work. A bare `Bacch.` stays Plautus unless Bacchylides is named.
- Lysias and Isocrates: a bare `Lys.` or `Isoc.` with two locus levels is the speeches, since the Lysistrata is cited by one line number. `Is.` needs Isaeus or Pindar named.
- Libanius: decided in code, not by patch. The table holds the whole record and three range records for each of orations and declamations (`libanius.orations_1-11` and so on) whose part files do not exist in the corpus and carry the same forms, so `Lib. Or.` tied four ways. The patch script only adds forms, so `resolver.py` now counts a range record as a part of its whole (`_collapse_whole_and_parts`). `Lib. Or. 11.1` reaches `libanius.orations`, `Lib. Decl. 1.1` reaches `libanius.declamations`. A bare `Lib.` (orations or declamations) stays unresolved. The same rule resolves `Aug. Ep.` to `augustine.epistulae`, which tied ten ways before.
- `data/citations/abbrev_patch_round4.json`: 17 forms (`Isae.`, `Hyperid.`, `Isoc. Ep.`, `Isoc. Epist.`, `O.`, `N.`, `Isthm.`, `Theocr.`, `Theoc. Id.`, `Theocr. Id.`, `Id.`, `Theoc. Ep.`, `Theocr. Ep.`, and `Bacch.` and `Bacchyl.` for both Bacchylides works). It declares `Bacch.` an intended overlap with Plautus (`allow_overlap`, new in `scripts/citations/apply_abbrev_patch.py`). The author-context forms are in `backend/citations/abbrev_context_rules.json`, with a new `defaults` block and family rules.

Steps, in order:
1. After the pull request merges and is pulled on production, run a dry run of `python scripts/citations/apply_abbrev_patch.py data/citations/abbrev_patch_round4.json data/citations/abbreviations.json` (expect 17 forms, no new works, no CONFLICT lines), then the same with `--apply` (dated backup beside the table).
2. Mirror to the toolkit copy. Run the same script with `--apply` on `~/tesserae-backups/ejc_index_2026-09-14/data/citations/abbreviations.json`, and copy `backend/citations/` (`extractor.py`, `parser.py`, `resolver.py`, `abbrev_context_rules.json`, `speech_numbers.json`) beside it.
3. Rebuild the EJC citation index (v14, from v13) and the full Project MUSE index, each inside `systemd-run --user --scope -p MemoryMax=<cap>`.
4. Install both with dated backups, touch `tesseraev6_flask.wsgi`, and run the golden check. Compare counts with v13 and the previous MUSE build. Expect more citations to the Demosthenes speeches, Aeschines, Andocides, Dinarchus, Lysias, Isocrates, Isaeus, Pindar (loci now carry the book letter, so check one Olympian and one Pythian row against the text), Theocritus, Bacchylides, Libanius' orations and Augustine's letters.

Rollback: copy the dated backup over the table and rebuild. The code can be reverted without the table step (the new forms then resolve as before). One existing test, `test_patch_script_is_idempotent_and_backs_up` in `tests/test_citation_round3.py`, fails against a production table that already holds round 3, because its first apply finds nothing left to add. It fails the same way on main and is not touched here.

**Run record.** The 17-form patch applied at 12:22 to the production table (backup `abbreviations.json.bak-20261016-122244`) and the toolkit copy (tables identical); `extractor.py`, `parser.py`, `resolver.py`, `abbrev_context_rules.json`, `abbrev_aliases.json` and `speech_numbers.json` mirrored into the toolkit (`.bak-2026-10-16-recog4`); a smoke test through the toolkit resolved `Dem. 21.72` to `demosthenes.against_midias` 21.72, `O. 1.1` with Pindar named to `pindar.odes` o.1.1, `Aeschin. 3.1`, `Lys. 12.4`, `Theoc. 1.5`, and `B. 17.1` with Bacchylides named to the dithyrambs. EJC v14 (`build_index_v14.py`, 12:22 to 12:35, cap 6G): 42,212 citations in 537 works (v13 40,566 in 465). Project MUSE v7 in full over the four journals (12:36 to 12:39, cap 4G): 26,879 citations from 1,741 articles (v6 25,555 from 1,733). Per work (EJC, MUSE): Demosthenes On the Crown 74 and 42, Against Midias 31 and 22, Lysias 237 and 258, Isocrates speeches 80 and 105, Pindar 611 and 602, Theocritus idylls 205 and 118, Libanius orations 0 and 50. Both installed at 12:42 (backups `citations.db.bak-v13-<stamp>`, `citations_muse.db.bak-v6-<stamp>`), wsgi touched, golden check all 69 the same. Live: On the Crown 18.1 returns a 1921 article, Lysias 12 as a range 29 articles, Against Midias 28. Two notes for the next round: a spelled book with the author (`Pind. Pyth. IV`) still gives a bare book locus without the letter prefix, and a page number after a colon can glue onto the locus (`Isth. I, 23: 07`).

## 2026-10-16 Citation recognizer round 3: abbreviation patch applied to the table, indexes rebuilt (RUN 11:11 to 11:30 EDT, by the lead)

The audit of the 2,407 Project MUSE articles (`analysis/recognizer_audit/`, outside the repository) found 37,208 citation occurrences in 7,568 distinct forms the recognizer does not resolve. Round 3 decides the top 150 forms (37 added, 33 resolved by author context, 29 not held or not citations, 51 left unchanged because they are footnote numbers or need other fixes): 45 abbreviations for 32 works in `data/citations/abbrev_patch_round3.json`, and the author-context choices in `backend/citations/abbrev_context_rules.json`. The context rules ship with the code and need no data step. The table is not in git, so the patch is applied by script.

1. On production, from the root, with the production venv: `python scripts/citations/apply_abbrev_patch.py data/citations/abbrev_patch_round3.json data/citations/abbreviations.json` (a dry run that prints the 45 forms and 3 new works, `diodorus_siculus.bibliotheca_historica`, `xenophon.hellenica` and `cassius_dio.roman_history`, and exits 2 with CONFLICT lines if a form already resolves to another work). Then the same with `--apply`. The script copies the table to `abbreviations.json.bak-YYYYMMDD-HHMMSS` beside it, writes a temporary file beside the table and renames it over, and a second run reports "nothing to do". Never edit the table by hand.
2. Mirror to the toolkit copy. Run the same script with `--apply` on `~/tesserae-backups/ejc_index_2026-09-14/data/citations/abbreviations.json`, and copy `backend/citations/abbrev_context_rules.json`, `abbrev_aliases.json` and the code beside it.
3. Rebuild the EJC citation index (v13: `build_index_v13.py`, derived from v12 by the lead) and the Project MUSE index with the new table, each inside `systemd-run --user --scope -p MemoryMax=<cap>`.
4. Install both with dated backups, touch `tesseraev6_flask.wsgi`, and run the golden check. Compare counts with the previous builds. Expect more citations to Polybius, Diodorus, Xenophon's Hellenica, Cassius Dio, Hesiod's Theogony, the Greek Anthology, Seneca's De beneficiis, Caesar and Suetonius's Augustus, and fewer unresolved rows for `Met.`, `Ep.`, `Ecl.`, `Od.`, `Tr.`, `Th.`.

Rollback: copy the dated backup over the table and rebuild. Left for later: a speech-number map for `Dem.`, `D.`, `Aeschin.`, `Andoc.` and `Isoc.`, the Libanius tie (the whole record and three partial records carry the same forms), `Theoc.` and `B.` (the poem number decides), `O.` (Pindar, locus scheme unchecked), and a default work for a bare `Met.` (Ovid) if wanted.

**Run record.** Steps 1 and 2 at 11:11: dry runs clean on both tables (46 forms, 3 new works, no conflicts), then `--apply` on the production table (backup `abbreviations.json.bak-20261016-111145` beside it) and on the toolkit copy; the toolkit's `extractor.py`, `abbrev_context_rules.json` and `abbrev_aliases.json` were mirrored from the merged code first (`.bak-2026-10-16-recog3`). Step 3: EJC v13 (`build_index_v13.py`, 11:14 to 11:28, cap 6G) gave 40,566 citations in 465 works (v12: 36,163 in 451); 43 works gained 20 or more (Ovid Metamorphoses 92 to 501, Diodorus 0 to 301, Tacitus Annals 275 to 544, Horace Satires 538 to 778, Hesiod Theogony 38 to 208, Ovid Heroides 35 to 191, Cassius Dio 0 to 148, Polybius 1 to 140, Xenophon Hellenica 0 to 131, Aeschylus Eumenides 40 to 171, Cicero De officiis 55 to 173, Libation Bearers 0 to 118, Macrobius Saturnalia 26 to 139, Persians 6 to 110, Caesar Gallic War 0 to 43, Civil War 3 to 53), one lost (Augustine De civitate Dei 243 to 210, `Civ.` now decided by the author named). A read of 40 rows from the gaining works found all genuine. The Project MUSE index was rebuilt in full (11:18 to 11:22, cap 4G) over the four journals, now including Arethusa (download complete 11:05, 631 of 631 articles; text extracted with the development venv's interpreter because the production venv lacks `pypdf`): after cleaning, 25,555 citations from 1,733 articles (was 15,577 from 1,246); Arethusa alone 407 articles and 5,156 citations; a read of 36 rows across twelve newly recognized works found 32 right, 3 with a footnote number glued to the locus and 1 bibliography title. Step 4: MUSE v6 installed 11:22 (backup `citations_muse.db.bak-v5-20261016-1122`; a v5 built from the still-empty Arethusa text was installed at 11:10 with backup `.bak-v4-20261016-1108` and had the same content as v4), EJC v13 installed 11:30 (backup `citations.db.bak-v12-<stamp>`), wsgi touched after each, golden check all 69 the same after each. `/api/scholarship/about` reports both totals.

## 2026-10-16 Sahidica New Testament files leave the repository tree (RUN 08:33 EDT, by the lead)

The Sahidica files carry the license "(c)2000-2006 by J Warren Wells, for academic use only". They stay in the index and searchable, but may not be redistributed. The pull request adds 29 registry entries (28 `texts/cop/sahidica.*` files, 27 books plus `sahidica.nt`, and `sahidic.bible`, which holds the same text), the `.gitignore` block, and removes the 29 files from the tree with `git rm --cached`. The repository's history still holds them; purging history is a separate decision.

Production steps, in order:
1. Before `git pull`, copy the 29 files aside (the pull deletes files the commit removed from the tree): `mkdir -p ~/tesserae-backups/sahidica_2026-10-16 && cp -p texts/cop/sahidica.*.tess texts/cop/sahidic.bible.tess ~/tesserae-backups/sahidica_2026-10-16/`; count 29.
2. `git pull` on the production checkout.
3. Restore them: copy the 29 files back into `texts/cop/`, keeping mode and owner. Verify `ls texts/cop | grep -c -E '^sahidica|^sahidic.bible'` is 29, and that `texts/cop/` holds 187 files in all.
4. Touch `tesseraev6_flask.wsgi`. Verify that a Reader request for one Sahidica passage (for example `sahidica.john`) still answers and shows the credit line, and that the Coptic download bundle (`/api/downloads/info`, language `cop`) counts 158 and its zip contains no `sahidica.*` or `sahidic.bible` file.
5. The Coptic data release under Downloads (`static/downloads/coptic_article/`) needs no rebuild for text: it holds references and a stripping script, no Sahidica line text.

**Run record.** Steps 1 to 4 ran at 08:33 as written: 29 files copied to `~/tesserae-backups/sahidica_2026-10-16/`, pull (texts/cop fell to 158 files), restore (187 files, none shown by git), wsgi touched; `/api/texts?language=cop` lists 187 texts; `/api/downloads/info` counts 158 Coptic texts with the restricted-withheld note; golden check all 69 the same.

## 2026-10-16 Image host status file seeded and weekly check installed (RUN 09:10 EDT, by the lead)
Pull request: feat/image-hosts-down. The document page hides an image link while its host has failed two consecutive weekly checks. Steps after the pull request is merged and pulled on production:
1. Seed the status file from the 9 and 16 October audits (seven hosts down, two recovered): `/var/www/tesseraev6_flask/venv/bin/python /var/www/tesseraev6_flask/scripts/documents/check_image_hosts.py --seed`. It writes `data/documents/image_host_status.json` (not in git) and never overwrites a check already recorded.
2. Run one real check of the nine hosts: `... check_image_hosts.py --only petriecat.museums.ucl.ac.uk --only papyri-leipzig.dl.uni-leipzig.de --only papyri-erlangen.dl.uni-leipzig.de --only papyri-koeln.dl.uni-leipzig.de --only papyri-wuerzburg.dl.uni-leipzig.de --only www.ville-ge.ch --only papyri.uni-koeln.de --only www.uni-koeln.de --only papyri.uni-leipzig.de`. A check made on a date replaces a seeded check of the same date.
3. Install and enable the timer (Sunday 04:30, output in `~/tesserae-backups/jobs/image_hosts.last`): copy `tess-image-hosts.service` and `tess-image-hosts.timer` to `~/.config/systemd/user/`, then `systemctl --user daemon-reload && systemctl --user enable --now tess-image-hosts.timer`.
4. Check: `curl -s .../api/documents/<id of a Petrie Museum papyrus>` carries `image_hosts_down` with the host, and the page shows the "unavailable" line. The file is re-read when it changes, so no restart or wsgi touch is needed.
To turn it off, delete the status file (or disable the timer and remove the file).

**Run record.** Seeded at 09:10 (nine hosts, checks dated 9 and 16 October), then the real probe of the nine hosts: eight down (the Petrie catalog, the four Leipzig portal hosts, the Geneva library, the Cologne papyri server all 500 or 503; `www.uni-koeln.de` 403 on every sample) and `papyri.uni-leipzig.de` answering. The 403 host serves the same pages to a browser, so #962 (deployed 09:22) counts a bot refusal as answering and its one failed check will clear at the next run. `tess-image-hosts.timer` installed and enabled (next run Sunday 2026-10-18 04:30). Live check: document `papyri:171828` carries `image_hosts_down` for the Petrie host since 2026-10-09. The golden request `documents_one` gained the empty `image_hosts_down` field and was re-recorded.

## 2026-10-16 Coptic Scriptorium corpora cloned for per-work source rows (RUN 2026-10-16, delegate)
- **What.** `git clone --depth 1 https://github.com/CopticScriptorium/corpora.git` into `~/tesserae-backups/sources/coptic_scriptorium/corpora/` (2.5 GB, commit `3ac067f1709a0012daf39ea8da2fac79980176a5`, 5,561 files). Outside the repository and outside production; a read-only reference copy. In this commit the `sahidica.nt` CoNLL-U files are empty (2 bytes each), so its documents were listed by file name and described from `meta.json`; `sahidic.ot` ships only as zip files.
- **What it fed.** One row per Coptic work in `backend/text_sources.json` (187 rows, 2,429 to 2,616). Metadata per document came from the TEI headers where valid (1,415 documents) and from `meta.json` otherwise (1,213): 2,628 documents, each with a document URN.
- **Mapping of the 187 files to Scriptorium documents.** Rules follow `scripts/convert_coptic_scriptorium_full.py` (commit `cb34c3e1`): a file named like a corpus is that corpus (61 files); `sahidica.<book>`, `sahidic.<book>` and `bohairic.<book>` are the documents of that book in `sahidica.nt`, `sahidic.ot`, `bohairic.nt`, `bohairic.ot` (119 files); the seven whole-collection files (`bohairic.bible`, `bohairic.nt`, `bohairic.ot`, `sahidic.bible`, `sahidic.ot`, `sahidica.nt`, `shenoute.all`) map to every document of their corpora. All 187 map, none unmapped: 28 files to a single document, 152 to several documents, 7 to a whole collection. Checked by comparing the first document's sentence text with the file's lines (159 non-Sahidica files, 154 match at 80 percent or better, the other five differ in sentence splitting or empty upstream sentences, not in content) and by verse counts for the Sahidica books (within 5 of the file's line count).
- **Links.** A document or work URN links to `https://data.copticscriptorium.org/<urn>` only after the page's title was fetched and was not the site's "Search" fallback, which the site returns with status 200 for a URN it does not hold. 62 rows link that way. The other 125 (the Bible books of the Bohairic and Sahidica corpora, most Sahidic Old Testament books, the collections) link to the corpus folder on GitHub, and their notes give the first and last document URN.
- **Editions.** 49 rows name an edition as the metadata writes it (`bibl` in the TEI header, `Coptic_edition` in `meta.json`). The key is omitted when the metadata has none or when a row would need more than three (Apophthegmata Patrum, several Shenoute works).
- **Licenses as stated.** CC-BY 4.0 (112 rows), CC-BY-SA 4.0 (45), CC BY-NC-SA 4.0 (3), and "(c)2000-2006 ... for academic use only" (27: the Sahidica New Testament files and the whole-collection files that include them).
- **Undo.** Remove the 187 rows whose `e_source` is "Coptic Scriptorium"; delete the clone folder.

## 2026-10-16 Citation recognizer table: the Verrines entry corrected, Thucydides id renamed inside it, rows remapped (RUN 01:50 to 02:39 EDT, by the lead)
- `data/citations/abbreviations.json` (production, not in git: generated from HUCIT on 2026-10-07) carried the Verrines under the file id retired on 2026-10-13 (`cicero.divinatio_in_c_verrem`) and had paired that file with the record for De Divinatione (its titles, the forms `Cic. div.` and `div.`, the URN `phi0474.phi053`). The standard short form `Verr.` was therefore never a known form (no table held a single `Verr.` citation) and `Cic. Div.` resolved to two works. Corrected by hand: id `cicero.in_verrem` with its six parts, titles In Verrem, Verrines, Against Verres, forms `Cic. Verr.`, `Cic. Ver.`, `Verr.`, `In Verr.` (the bare `Ver.` was tried and removed: the early journals use it for verse), URN `phi0474.phi005`, `hucit_work_id` cleared, `match_method` noting the hand correction. The Thucydides id was renamed inside the same file (18 occurrences, `thuc. pele.` to `thuc. pelo.`) so the recognizer emits the current id without a row update after each build. Backups beside the file: `abbreviations.json.bak-verrines-20261016`, `abbreviations.json.bak-thucid-20261016`. The private toolkit's copy and its `work_depth.json`, `work_max_line.json` and `abbrev_aliases.json` were brought level with the repository (`.bak-2026-10-16-mirror`, `.bak-thucid-20261016`).
- Rows remapped `cicero.divinatio_in_c_verrem` to `cicero.in_verrem` with a `.bak-verrines-20261016` copy of each table first: `data/citation_index/citations.db` 9, `citations_muse.db` 10, the toolkit's v10 source 9, the three MUSE working tables 11, 10 and 7. The app reloaded (`touch tesseraev6_flask.wsgi`).
- EJC rebuilt as v12 with the corrected table (`build_index_v12.py`, cached text, no network; a v11 with the bare `Ver.` gave 1,586 Verrines rows, most of them verse numbers, and was discarded): 36,163 citations against 35,556 in v10 over the same 27,244 articles; the Verrines 9 to 381 rows (a 40-row read: all 40 genuine Verrines citations), De Divinatione 20 to 248 (`Cic. Div.` no longer ambiguous), no work lost 20 rows or more, 18 minutes. Installed as `citations.db` with backup `citations.db.bak-v10-<stamp>`. `document_citations.db` was left as it stood: it indexes citations of inscriptions and papyri by series, which this table does not touch. Golden check after the install at 02:39: all 69 recorded requests the same.
- Repository side (this pull request): `backend/citations/abbrev_aliases.json` keys Thucydides by the current id and adds the forms `Div. Caec.`, `Div. in Caec.`, `Cic. Div. Caec.`, `Div. in Q. Caec.` for the Divinatio in Caecilium; `tests/test_citation_aliases.py` covers the Verrines, De Divinatione and the Caecilius forms against the corrected table (skipped where the table is absent, as before).

## 2026-10-16 Journal citation indexes rebuilt with the recognizer fixes and installed (RUN 23:12 to 00:50 EDT)
- **EJC (JSTOR Early Journal Content, 29,055 articles).** Rebuilt twice with the private toolkit from the cached raw text, no network: v9 after pull #945 (missing abbreviations for Thucydides, Livy, Pliny, Apollonius, Tibullus; whole-versus-parts ties; author-year and footnote guards; OCR "Ill" = 3): 33,386 to 37,838 citations, 772 s; then v10 after pull #948 (context-only short forms, vetoes, Stephanus pages, book-depth check): 35,556 citations, Eucherius false positives 556 to 0 in the MUSE index and 26 to 0 in the sample. Installed as `data/citation_index/citations.db` each time (backups `citations.db.bak-v8-20261015`, `citations.db.bak-prev-20261016`), mode 664, group tessdev; wsgi touched.
- **Project MUSE (AJP 1,349 and TAPA 279 articles with text, read under the library's license).** `~/licensed_text/index/`: text extracted with pypdf (55 min AJP, 3 min TAPA), index built with the same toolkit (84 s), cleaned (`clean_muse_index.py`: sentence window of 400 characters, year loci and glued footnote numbers dropped, id variants resolved): v1 11,181 citations, v2 12,592 (v9 recognizer), v3 11,997 (v10 recognizer; 775 rows removed by the cleaning rules). Precision by hand on 60-row samples: 82 percent raw, 88 percent cleaned. Installed as `data/citation_index/citations_muse.db` (pull #944 reads it through `TESSERAE_CITATIONS_EXTRA` in the production `.env`, added 23:04 with the mode kept at 664, backup `~/tesserae-backups/env.bak-muse-20261015`); backups `.bak-v1-20261015`, `.bak-prev-20261016`. Live: `/api/scholarship` for Aen. 1.1 returns rows from both indexes. Classical Journal and Arethusa are appended when their downloads finish (the download stopped at 19:07 on three timeouts in a row and was restarted at 21:34; 2,228 of 3,040 articles at that point).
- **Inscriptions' citation index** `data/citation_index/document_citations.db` rebuilt from the new journal index both times with `scripts/documents/build_document_citation_index.py` (27,244 articles read, 288 citing, 392 commentary files), swapped with dated backups.

## 2026-10-16 Thucydides work id renamed (RUN 22:56 to 23:32 EDT on 2026-10-15, by the lead, supervised)
Run record (the plan it followed is kept below). Pull #943 deployed 22:54.
- **Stores, 22:56 to 23:09.** `rename_work.py --apply` nine times (whole file and parts 1 to 8): index rows, hashed lemma caches re-stamped, line embeddings moved. `rename_work_in_passage_index.py --apply` in prefix form: 1,985 ids and descriptions, 5,562 window rows, 3,577 line rows moved, 0 left under the old name, ids 684,503 unchanged. Reuse table `cache/reuse_pairs/grc.db`: `line_counts.work` 795 rows, `pairs.work_a` 7 and `pairs.work_b` 1,098 rows renamed on a copy, integrity ok, swapped (backup `.bak-thuc-20261016`).
- **Derived indexes, 23:09 to 23:32.** `build_desc_fts.py`, `build_desc_vocab.py`, `build_window_names.py` (22 min), each swapped with a `.bak-thuc-20261016`; wsgi touched.
- **Checks.** Lockstep 684,503 in all three files; the texts list reads "Thucydides, Peloponnesian War"; Similar Passages 15 results; Line Search with author Thucydides finds the work. Theme Search with author Thucydides returned nothing until `data/passage_index/works_by_language.json`, the author-to-works list the filter reads, had the id replaced by hand (00:20, backup `.bak-thuc-20261016`): the rename tool does not update that file (tool follow-up). The recorded API check re-recorded `texts_grc` and `ls_lemma_grc`; all 69 same.
- **Citation indexes.** The work id updated inside `citations.db`, `citations_muse.db` and the toolkit's v9 and v10 sources (`UPDATE citations SET work_id ...`, backups `.bak-thucid-20261016`).
- **Map and density.** Rebuilt after the whole night's index work (see the entry below).

Plan as written before the run:
The pull request renames the nine files `texts/grc/thucydides.peleponnesian_war.tess` and `.part.1` to `.part.8` to `thucydides.peloponnesian_war` (same suffixes; content unchanged). Line tags are `<thuc. pele. N.N.N>` and stay. It also updates the tracked occurrences of the id (the two citation tables, `data/text_descriptions.json`, the History view's Greek default, the Ask a Work example, tests, `scripts/review/route_speed_requests.json`) and removes the nine display overrides added in #939. Every other store changes by the steps below, run by the lead after the merge and deploy, one heavy job at a time through `~/bin/tess-job` with a dated backup of each store first. Fill in the times when run.

1. Rename in the stores outside git, once per file (nine files: the whole file and parts 1 to 8). Dry run, read the report, then apply; it moves the Greek inverted-index rows (filename, author, title), the lemma cache and the line embeddings. The line refs are abbreviations (`thuc. pele. 1.1.1`), so no ref carries the old id and none should change:
   - `scripts/corpus/rename_work.py --language grc --old thucydides.peleponnesian_war --new thucydides.peloponnesian_war` (then `--apply`)
   - the same with `--old thucydides.peleponnesian_war.part.N --new thucydides.peloponnesian_war.part.N` for N = 1 to 8.
   The passage index is not done here; step 2 does it once.
2. Passage index, once, prefix form (no `--leaf`; it moves the whole work and every part at once): `scripts/corpus/rename_work_in_passage_index.py --index data/passage_index --from thucydides.peleponnesian_war --to thucydides.peloponnesian_war --tag thuc-20261016`, dry run first, then `--apply`. Rehearse on a scratch copy first if the dry run shows anything unexpected. Window vectors are untouched because the content did not change.
3. Derived indexes, because the rename changes `descriptions.jsonl`: `scripts/build_desc_fts.py`, `scripts/corpus/build_desc_vocab.py`, `scripts/corpus/build_window_names.py` (to a `.new` file, swapped in), touching the wsgi file after each. Tables keyed by work id, checked read-only on 2026-10-16: `cache/bigrams/grc_bigrams.json` holds only bigram frequencies and totals and no work id, so it needs nothing. `cache/reuse_pairs/grc.db` does name the work: 795 `line_counts` rows and 1,105 `pairs` rows (either side) carry `thucydides.peleponnesian_war...`. The lines and their pairs are unchanged, so rather than the 9 GB rebuild, update the work column on a copy of the database (`UPDATE line_counts SET work = replace(work, 'peleponnesian', 'peloponnesian') WHERE work LIKE 'thucydides.pel%'`, the same for `pairs.work_a` and `pairs.work_b`), integrity check, swap in with a dated backup. Confirm the column names against `backend/reuse_table.py` before running.
4. Lockstep check: ids, descriptions, vectors and window_texts counts in step (684,503 at the last check); no id left under the old name; one Similar Passages request from a Thucydides window, one Theme Search request ("the plague at Athens" should still return Thucydides 2), and a Greek Line Search naming Thucydides (the result must name `thucydides.peloponnesian_war.part.N`). Reference search "arma virum" must return Ovid, Quintilian, Seneca.
5. Recorded API check (`scripts/review/golden_api.py`): run it and re-record the requests the rename alters (text lists, the Thucydides text and description requests, version stamps, theme requests that return Thucydides). `scripts/review/golden_requests.json` names no Thucydides work, so none of its requests is edited by hand. `scripts/review/route_speed_requests.json` was edited in this pull request (two targets).
6. Connections map (`scripts/build_connections_map.py`, cap 10G) and density cache (`scripts/precompute_passage_density.py --language all`), both keyed by the index fingerprint, which the rename changes.

Between step 1 and the deploy order, the live text list and the stores disagree: run steps 1 and 2 immediately after the deploy and touch the wsgi file after each.

Rollback: restore the dated backups of the Greek inverted index, the lemma cache files, the passage-index folder and the embeddings, rename the nine text files back (and restore the nine overrides from #939 if the old id stays), and touch the wsgi file.
## 2026-10-16 Project MUSE citation index installed as a second index (to run)
Pull request: feat/muse-citations-second-index (reads `TESSERAE_CITATIONS_EXTRA`). Built offline on the development machine from the journal PDFs by the citation extractor (1,628 articles from two journals, 11,988 citations), then cleaned by `clean_muse_index.py`: sentences cut to at most 400 characters around the citation, rows with a year or a footnote number in the locus removed, three work ids corrected, Homeric Hymns rows given the id `homer.hymns`. No article text goes to the server, only the database. Steps after the pull request is merged and deployed:
1. Copy the cleaned database to `data/citation_index/citations_muse.db` in the production checkout, mode 664, group tessdev.
2. Add `TESSERAE_CITATIONS_EXTRA=/var/www/tesseraev6_flask/data/citation_index/citations_muse.db` to the production `.env`, editing in place and keeping mode 664.
3. Touch `tesseraev6_flask.wsgi`, then check `curl .../api/languages`.
4. Make one Scholarship request for Aeneid 1.1 (`/api/scholarship?work=vergil.aeneid&ref_start=1.1&ref_end=1.1`) and confirm `index.results` holds a row with `"source": "muse"` and a `https://doi.org/` link.
To turn it off, remove the line from `.env` and touch the wsgi.
## 2026-10-15 Descriptions written for the 187 Coptic and 39 Hebrew works (RUN 22:46 to 23:10 EDT, delegate, from a worktree)
- `scripts/corpus/describe_works.py --lang cop --lang he` (the script gained the two languages, repeated `--lang`, and a `BLURBS_STYLE_EXTRA` setting added to the writer's instructions: one paragraph of 60 to 120 words, American spelling, book and version named first, no date finer than the century unless the source gives one). Writer GLM 5.3 Flash through the university gateway, shown the opening, a slice from the middle and the end of each work (`BLURBS_SAMPLE_WHOLE=1`) with an 8,000-token budget (the default 2,500 was spent on reasoning and returned nothing; 9 works needed 14,000). Concurrency 12, about 0.4 works a second: 226 written in about 9 minutes, 9 retried in 2. Logs in `~/tesserae-backups/jobs/blurbs_2026-10-15_cop_he/`.
- Checker Qwen 3.8 (thinking off): 149 passed, 77 flagged. It reads Coptic poorly (it called two whole-Bible files and two prophets treatises), so every blurb and every flag was read against the file.
- **Fixed by hand: 21 blurbs for factual slips and 8 for length** (over 120 words). The slips: a Dormition of John described as the apostle's own first-person account; a two-homily file (the Canaanite woman, then Susanna) described as one homily; a discourse on the sword described as one on blood; a whole-Bible file with the Testaments in the wrong order; and 12 books that survive only in part (two verses of 1 Chronicles, ten of 2 Chronicles, five of Bel and the Dragon, chapters 5 to 7 of 2 Maccabees, fragments of Kings, Tobit, Hosea, Amos, Nahum, Zechariah and Daniel) described as whole.
- Merged as new `cop` (187) and `he` (39) sections of `data/text_descriptions.json`, sorted by work id; the existing sections are unchanged.

## 2026-10-15 King James Bible: Revelation moved into the New Testament (RUN 20:30 to 21:50 EDT, by the lead, supervised)
Run record (the plan it followed is kept below). Pull #934 deployed 20:29. Steps and what happened:
- **Rename, 20:30.** `rename_work.py --apply`: the .tess had already moved with the pull (0 tagged lines; the tags are `<WEB Revelation N.M>` and stay); en index text 60 renamed (404 lines, 8,730 postings), the hashed lemma cache re-stamped, the line embeddings moved. `rename_work_in_passage_index.py --leaf --apply`: 93 ids, 93 descriptions, 93 window rows moved, 0 line rows; 0 left under the old name; ids 684,503 unchanged; backups `*.bak-revelation-20261015-20261015-203143`.
- **Whole-work file, 20:33.** Its lemma cache rebuilt (7,952 lines; `batch_lemma_cache.py en`, 1 built, 163 cached). `add_texts_to_index.py --replace world_english_bible.new_testament.tess` on a copy of `en_index.db`: text 10 now 7,952 lines; integrity ok; swapped in, backup `en_index.db.bak-revelation-20261015`. `rebuild_bigrams.py en`: 354,023 bigrams. `rebuild_docfreq.py` not needed (the tool rebuilt `lemma_doc_freq`).
- **Derived indexes, 20:33 to 20:57.** `build_desc_fts.py`; `build_desc_vocab.py` (684,503 rows, 105,502 words); `build_window_names.py` (22 min: Persian 1,336 s, Urdu 1,343 s), each swapped in with a `.bak-revelation-20261015`; wsgi touched.
- **Checks, 20:57.** Lockstep 684,503 = 684,503 = 684,503; Revelation ids 93 new, 0 old; Similar Passages 15 results; Theme Search 5 results; a King James search for "throne lamb" names the New Testament. Recorded API check: 12 of 69 differed, every one a version stamp (`corpus_version`, `index_version`, `index_fingerprint` 26000403... to 26522875-1792110726...) or the text list gaining "King James Bible, New Testament, Revelation"; re-recorded; all 69 same at 21:55.
- **Connections map, 21:00 to 21:49.** `build_connections_map.py` under a 10 GB cap: 375,048 windows, 35,862 author pairs, 1,550 century pairs, 282 genre pairs, 1,105.6 MB, 49.1 min, peak 7.54 GB; the first build to include Italian, Old French and Middle High German (#933). The site served the previous map marked stale meanwhile. Two older caches removed by the builder.
- **Density cache.** `precompute_passage_density.py --language all` queued at 21:55 under an 8 GB cap for the night (every work, since the fingerprint changed).
- **Download list.** `scripts/download_english.py` keeps the upstream filename and saves it under the new name (`LOCAL_NAMES`).

Plan as written before the run:
The pull request renames `texts/en/world_english_bible.revelation.tess` to `world_english_bible.new_testament.part.27.revelation.tess` (content unchanged, 404 lines) and appends those 404 lines to `texts/en/world_english_bible.new_testament.tess` (7,548 to 7,952 lines, Matthew to Revelation). Line tags stay `<WEB Revelation N.M>`. The pull changes the tracked files only (texts, `data/text_descriptions.json`, `data/translation_pairs.json`, the two citation tables, `scripts/download_english.py`, one test). Every other store changes by the steps below, run by the lead after the merge and deploy, one heavy job at a time, each inside `systemd-run --user --scope -p MemoryMax=<cap>` and through `~/bin/tess-job`, with a dated backup of each store first. Fill in the times when run.

1. Rename the work in the stores outside git. Dry run first, read what it reports, then apply (it moves the text, the en inverted-index rows, the lemma cache, and the line embeddings):
   - `scripts/corpus/rename_work.py --language en --old world_english_bible.revelation --new world_english_bible.new_testament.part.27.revelation`
   - `scripts/corpus/rename_work.py --language en --old world_english_bible.revelation --new world_english_bible.new_testament.part.27.revelation --apply`
   - the passage-index windows: `scripts/corpus/rename_work_in_passage_index.py --leaf world_english_bible.revelation world_english_bible.new_testament.part.27.revelation` (dry run), then the same with `--apply`. Rehearse on a scratch copy first, as on 2026-10-13. The line embeddings and window vectors are untouched, because the content did not change.
2. Give the whole-work index rows Revelation, on an index copy (cap 12G):
   - delete `cache/lemmas/en/world_english_bible.new_testament*.json` for the whole-work file (the hashed name, as on 2026-10-13), then `scripts/batch_lemma_cache.py en` (cap 8G) rebuilds it;
   - `scripts/corpus/add_texts_to_index.py --db <en_index.db copy> --language en --cache-dir /var/www/tesseraev6_flask/cache/lemmas --replace world_english_bible.new_testament.tess`, which also rebuilds `lemma_doc_freq`; integrity check, swap in with a dated backup, `touch tesseraev6_flask.wsgi`;
   - `scripts/corpus/rebuild_docfreq.py --language en --apply` if the tool did not leave the table current, and `scripts/corpus/rebuild_bigrams.py en` for the rare-bigram table.
   The whole-work file carries no passage windows (whole works with part files are dropped from the passage index), so no windows are added.
3. Passage-index lockstep check: counts of ids, descriptions, vectors and window_texts in step; then one Similar Passages request from a Revelation window and one Theme Search request; the rename changes `descriptions.jsonl`, so rebuild the keyword index (`scripts/build_desc_fts.py`), the description vocabulary (`scripts/corpus/build_desc_vocab.py`) and the names index (`scripts/corpus/build_window_names.py`, to a `.new` file and swapped in), touching the wsgi file after each.
4. Reference searches from `tests/search_reference_tests.md` ("arma virum" must return Ovid, Quintilian, Seneca), a search of the King James text for a Revelation phrase (the result must name `world_english_bible.new_testament.part.27.revelation`), and the translation pairs for Revelation (4 rows, `work_b` renamed).
5. The recorded API check (`scripts/review/golden_api.py`): run it, and re-record only the requests the data change alters (the text lists, the Revelation text and description requests, and the theme requests the rename moves).
6. The connections map (`scripts/build_connections_map.py`, cap 10G, about 50 minutes) and the passage density cache (`scripts/precompute_passage_density.py --language all`). Both are keyed by the index fingerprint, which the rename changes, so both are rebuilt; until then the Reader computes a first visit's gutter live.

Rollback: restore the dated backups of the English inverted index, the lemma cache files, the passage-index database and the embeddings folder, rename the two text files back, and touch the wsgi file.

## 2026-10-13 Small corpus leftovers: production run of the #904 tail (run 22:19 to 23:5x EDT, by the lead, supervised)
Prepared as PENDING steps in #904 (text changes by the pull; every other store by hand). Run order and what happened, with the two tool faults it found. Backups of the two inverted indexes and of ids.json and descriptions.jsonl taken first into `~/tesserae-backups/corpus_leftovers_2026-10-13/`; every tool kept its own dated `.bak-*` beside the file it changed.

- **Renames (Libanius six parts, Cicero Verrines whole file and six parts), 22:19 to 23:09.** The pull renamed the `.tess` files. `rename_work_in_passage_index.py --leaf` (new) moved the six Libanius part works' windows (549, 736, 885, 523, 643, 590 ids, descriptions and window_texts rows each) and the prefix form moved the Verrines' 1,051 windows and 974 line rows; a rehearsal on a scratch copy first showed the renamed rows moved and no other row changed. `rename_work.py --apply` then moved the inverted-index rows (filename, author, title), the lemma caches (hashed names, payload rewritten) and the line embeddings for all thirteen works. Two faults found and fixed in the tool on the way: it read the new `.tess` beside the gone old one as a collision and refused (now a collision only while the old file exists), and it cut every line ref at the old id's length, which for files whose refs are abbreviations (`libanius. decl. 1.1`, `cic. ver. 1.1.1`) made duplicates that the UNIQUE constraint refused (now only a ref carrying the old id moves). Between 22:19 and 23:09 the live text lists showed the new names while the inverted indexes still held the old ones, so a search naming a Libanius part or the Verrines would have found nothing in that window.
- **Confucius, Salutati, Lamentations, 23:10 to 23:15.** The four texts' lemma caches deleted and rebuilt (`batch_lemma_cache.py la grc`, 3 and 1 built, the rest skipped). Index rows replaced on copies and swapped in with dated backups: Confucius part 2 (235 lines, 25,965 postings), the whole file (255 lines, 28,599 postings), Salutati De laboribus Herculis (1,450 lines, 106,871 postings, was 56,558: the 97 chapter-sized lines had been cut short), Lamentations (151 lines, 2,031 postings); `lemma_doc_freq` rebuilt by the tool (329,188 Latin and 226,123 Greek lemmas). The Confucius windows' stored wording refreshed (210 windows, 47 line rows).
- **Roland window, 23:14.** `build_window_texts.py --work chanson_de_roland.chanson_de_roland --db <copy> --descriptions ... --apply`: the work's 933 window rows (the one at `fine:336` now holds 26.1 to 27.7, since laisse 25 ends at 25.6) and its 4,005 line rows; no row that existed before changed its text; copy swapped in.
- **Salutati's windows, 23:15 to 23:24.** The 1,450 new units cut by `prose_windows.py` into 1,349 prose windows (median 708 characters, maximum 1,200); the eight one-window poems made with `build_batch_windows.py --min-lines 1` (Alcuin carmina 73; Catullus 85, 93, 94, 105, 106, 112; Dracontius fragments); all 1,357 described on the gateway (`describe_prose_windows.py`, Qwen 3.8 27B, stamp `corpus904-20261013`, 5.8 minutes, 0 errors) and encoded with the site's own encoder (`encode_with_embed_service.py`, new: 1,357 x 1,024 unit vectors, same model and blob text as the GPU route). Texts upserted into `window_texts.db` on a copy (698,546 rows). The 937 old Salutati windows removed (`apply_passage_rows.py --mode remove`, 693,611 to 692,674) and the 1,357 new rows appended (to 694,031), lockstep checked after each.
- **Whole-work duplicates dropped, 23:24.** `drop_whole_file_windows.py --apply` without `--allow-incomplete`: fourteen whole works whose book files all have windows (Alcuin carmina, Appian foreign wars, Augustine De trinitate, Cassius Dio, Catullus carmina, Diodorus, Dracontius Romulea, pseudo-Hegesippus, Libanius declamations and orations (now that their parts carry the standard names), Plato epistles, Quran Al-Baqara and Al-Imran, William of Tyre): 9,247 windows and their window_texts rows (694,031 to 684,784).
- **Two duplicate texts retired (D5, D6), 23:25 to 23:32.** `remove_restricted_text.py --apply` for `ennodius.epigrammata` (the same Book 2 as `magnus_felix_ennodius.carmina_2`, which is kept: CSEL, Hartel 1882; 931 index lines, two cache files, 217 windows, 1,148 window_texts rows) and `aretaeus.signorum_acutorum_morbum` (18 lines wholly inside `aretaeus.curatione_acutorum_morbum`; 18 index lines, 64 windows). Archive with a README: `~/tesserae-backups/retired_duplicates_2026-10-13/`. The files and their rows in `text_genres.csv`, `text_sources.json`, `text_descriptions.json` and the two citation tables leave the repository in this pull request. Index after: 684,503 windows, ids, vectors and descriptions in step.
- **Derived indexes, 23:32 onward.** `build_desc_fts.py` (keyword index), `build_desc_vocab.py` (684,503 rows, 105,502 words), `build_window_names.py` to a `.new` file and swapped in; wsgi touched after each step; one Similar Passages and one Theme Search request answered; the reference searches passed; the golden check re-recorded for `texts_la` and `texts_grc` (the renamed and retired works) and the theme requests the index change moved.
- **Hebrew clitic spacing: nothing to run** (measured 2026-10-13: no space-separated one-consonant token in any of the 39 books; the fix of `2fb6e657` is in the files).
- **Not run tonight:** the connections map and the passage density cache (the Reader computes a first visit's gutter live until then); scheduled as the next night job.

## 2026-10-13 English cross-language embeddings installed as `en_cross` (RUN 13:09, live after the #892 deploy at 13:16)
- What: the 164 files `backend/embeddings/en_cross/<work>.npy` and `.meta.json` (float32 with 768 columns, one row per `.tess` line in file order), built with bowphs/SPhilBerta on one GPU of the campus cluster (181,515 lines, 72 seconds, hashes checked, input and upload folders deleted afterwards). Staged at `~/tesserae-backups/english_embeddings_sphilberta_2026-10-13/en/`. The monolingual set `backend/embeddings/en/` (MiniLM) is not touched and stays in service for English-English search.
- Checks made before staging. All 164 files are present. Each has the row count `parse_tess_file` returns for its text, 768 columns and no NaN. A line's cosine with itself is 1.0 and with an unrelated line well below 0.9. Thirteen files that still existed from the March 2026 CPU build match at cosine 1.0000.
- Install steps (run by the deploy user on the live server after the pull request is merged and deployed, the date entered here when run):
  1. `mkdir backend/embeddings/en_cross` and copy the staged files in: `cp -p ~/tesserae-backups/english_embeddings_sphilberta_2026-10-13/en/* backend/embeddings/en_cross/` (mode 664, group tessdev).
  2. `touch tesseraev6_flask.wsgi`. The hold on the two English pairs lifts itself when the folder holds a file, so no code change is needed.
  3. Check `/api/languages` (`crosslingual_held` empty, `la-en` and `grc-en` listed), run one Latin-English and one Greek-English search, and one English-English fusion search (it must read as before).
  4. Re-record the golden `languages` request (it differs only by the lifted hold).
- Rollback: remove the files from `backend/embeddings/en_cross/` (the folder may stay empty) and touch the wsgi file. The hold returns.

- Run record: the folder was made with group tessdev and mode 2775 and the 328 files copied in at 13:09, before the code deploy, which the old code ignored; after the #892 deploy the hold on the two English pairs lifted by itself (`/api/languages` lists la-en and grc-en, nothing held). Checks: a Latin-English search (Aeneid 1 against Paradise Lost 1) answered 78 rows and a Greek-English search (Iliad 1 against Paradise Lost 1) 82 rows, the Latin top row the one the probe set expects; the live golden check differed only in the `languages` request, re-recorded. The MiniLM set in `backend/embeddings/en/` is untouched.

## 2026-10-13 Licensed journal text: first supervised retrieval (DRAFT, date and time to be filled in on the day)
- What: retrieval of full text from the four Project MUSE classics journals
  (American Journal of Philology, Transactions of the American Philological
  Association, The Classical Journal, Arethusa) and from De Gruyter Brill's
  Philologus and Mnemosyne, under the licensors' agreements to automated
  retrieval at one item a minute from the web server's address. The text is
  read once to extract passage citations and echo claims for the scholarship
  index; it is not shown or redistributed. Status: the tooling exists and has
  been dry-run against a local stub only. Nothing has been fetched.
- Before the first run: the start date is sent to Project MUSE, who asked to
  be told it. The lists are built from Crossref's public metadata by
  `scripts/scholarship/licensed_lists.py build --publisher muse|degruyter`.
- Run: `scripts/scholarship/licensed_fetch.py run --publisher P --list CSV
  --out DIR --rate 60`, on the production server only (it refuses unless the
  outgoing address is 128.205.2.231), as the deploy user, inside
  `~/bin/tess-job`. The first run uses `--limit` and is watched.
- Where: DIR is a folder outside the repository and outside the web root,
  created mode 700; files are mode 600, readable by the deploy account alone.
  Layout `DIR/<publisher>/<journal>/<doi>.<pdf|html|xml>` with a metadata
  sidecar `<doi>.json` (status, content type, size, time) and the resumable
  log `DIR/fetched.jsonl`.
- Rate and manners: one article a minute (the landing page, then the full
  text a few seconds later); a fixed User-Agent naming the project and its
  university contact address; redirects only to the publisher's own hosts.
- Stop rule: the first 401, 403, 429 or captcha-like page ends the run,
  writes `DIR/STOPPED.json` and requests nothing further. Nothing is retried
  around a refusal. The next run refuses to start until a person has read
  `STOPPED.json` and passes `--clear-stop`. Three failures in a row (a
  missing page, a network error) stop it too.
- Resume: a restart skips every DOI already saved and waits out the rate
  from the last logged request.
- Purge rule: at project end, `licensed_fetch.py purge --out DIR --publisher
  P` deletes that publisher's text files, keeps the metadata sidecars and the
  log, and writes `DIR/PURGE_<publisher>_<date>.json`. Backups drop a deleted
  file thirty days later.
- Verification: the stub-server tests in `tests/test_licensed_fetch.py`
  (rate, stop on refusal, resume, purge, address check).

## 2026-10-13 Translation file installed: Saadi's Gulistan, Eastwick 1880 (RUN 07:41)
- What: `data/translations/fa__saadi.diwan.json`, built by
  `scripts/translations/align_saadi_gulistan_eastwick.py` (this pull request)
  from the Internet Archive scan of Edward B. Eastwick's 1880 translation,
  public domain. One whole-work unit covering refs `saadi.diwan.29808` to
  `.32003` (2,196 refs, the complete Gulistan embedded in the diwan file),
  confidence exact; the Reader's Translation tab shows the whole translated
  work for any selection in that range, with the note that the smallest unit
  is the work.
- How: the staged file copied into the translations folder on the live
  server, mode 664, group tessdev. No other Saadi translation existed, so
  nothing was replaced. The server lists the folder on each request, so no
  reload was needed.
- Check: `/api/translation?work=saadi.diwan&refs=saadi.diwan.30322` answers
  available true, block_lines 2196, attribution Eastwick 1880, text opening
  "Praise be to God!".

## 2026-10-12 Fifteen backup copies of index files deleted (RUN 20:00)

The scripts that append texts to a search index, repair references or rebuild a frequency table each leave a stamped `.bak-<tag>` copy of the index file beside it, as a way back if the change proves wrong. Fifteen such copies had accumulated under `data/inverted_index/` on the web machine, from 29 August to 10 October, 22 GB in all: six of the Latin index (7 and 8 October), three of the Greek index (4 to 10 October), two of the Persian index, and one each of the Coptic, English, Hebrew and Urdu indexes. The current indexes had been live for between two days and six weeks, the reference searches had passed after every deploy, no process had a copy open, and no code reads them. At the owner's instruction all fifteen were deleted. Free disk rose from 509 to 530 GB. The reference search check passed afterwards and Theme Search answered.

The files, for the record: cop_index.db.bak-letters-20260927-1451, en_index.db.bak-milton-20260916-213923, fa_index.db.bak-dropped-20261008-20261008-113645, fa_index.db.bak-swap-dropped-20261008, grc_index.db.bak-diodorus-loeb-20261010, grc_index.db.bak-historians-20261009, grc_index.db.bak-historians2-20261009, he_index.db.bak-homographs-20261001-1048, la_index.db.bak-docfreq-20261007-082418, la_index.db.bak-removed-20261007-20261007-081825, la_index.db.bak-stale-20261007-0201, la_index.db.bak-vegio-20261007, la_index.db.bak-vegiofix-20261007, la_index.db.bak-victor-minor-20261008, ur_index.db.bak-swap-dropped-20261008.

Rule from here: a `.bak` copy of an index is kept until the next deploy's reference check has passed, then deleted in the same turn, and the deletion is noted in this log with the append it belonged to.

## 2026-10-12 The local model server mothballed (RUN 18:06)

The assistant, the scholarship paragraph, Theme Search's query expansion and the Scholarship tab's note translation all go through one model client, which the live site points at the campus AI gateway. The local model server on the web machine (a llama-server holding about 20 GB of memory) had answered no request in a week, so at the owner's instruction it was stopped and disabled, leaving its unit file in place. Available memory rose from 27 to 52 GB, and the job launcher, which allowed one job at a time while that server ran, now lets jobs overlap within its 24 GB budget.

Reviving it, should the gateway be unreachable, is one command on the web machine: `tess-local-model revive` starts the server and points the site's model setting at it, saving the gateway settings aside. `tess-local-model mothball` reverses that, and `tess-local-model status` reports both. No key is printed by any of the three.

## 2026-10-12 Object pictures cached on the server (RUN 10:41 to 10:47)

Status: run on production 2026-10-12 at two requests a second. 684 of 694 pictures cached (134 MB); ten Art Institute of Chicago addresses answered 403 and are left out (the page hides the picture box for them). One thing went wrong first: the web worker had already created `data/objects/images/` when the deploy's live check fetched one picture, and its umask made the folder unwritable by the maintainer, so the first run failed on every file. The folder was moved aside as `data/objects/images.flask-owned/` (one file, to be deleted by the server administrator) and recreated group-writable; the route now creates the folder group-writable itself.

Command, from the production checkout, inside the job launcher:

    ~/bin/tess-job --fg objimg 2 python scripts/objects/fetch_object_images.py --db data/objects/objects.sqlite --out data/objects/images --rate 2

Expected: about 694 pictures (390 Art Institute of Chicago, 304 Cleveland Museum of Art), roughly six minutes at two requests a second; the final line reads `fetched 694, already cached 0, refused 0, failed 0`. Folder: `data/objects/images/` (files named by the SHA-1 of the image address). Safe to re-run: pictures already present are skipped. Not in git.

## 2026-10-11 Description vocabulary for Theme Search's unknown-word check (built 2026-10-11; installed 2026-10-11 22:03, rebuilt 23:47 after the prose append)

- What: `data/passage_index/desc_vocab.json`, the words that occur in at least two passage descriptions (every lowercase alphabetic token of each row's `blob` and of the string and list values in its `desc`, counted once per row). Theme Search uses it to tell a reader which words of a query no passage description contains, and to hold the list when none of them does. Without the file the check is off and the response carries `vocab_checked: false`.
- Script: `scripts/corpus/build_desc_vocab.py`, one pass over `descriptions.jsonl`, under 100 MB of memory, about 35 seconds.
- To run on production (tess-job, cap 4), then touch the wsgi file:
  `python scripts/corpus/build_desc_vocab.py --descriptions /var/www/tesseraev6_flask/data/passage_index/descriptions.jsonl --out /var/www/tesseraev6_flask/data/passage_index/desc_vocab.json`
  A copy built from the 542,625 production rows (88,473 words, 1.2 MB) is in `~/tesserae-backups/desc_vocab_2026-10-11/desc_vocab.json` and can be copied over instead.
- The file is rebuilt after every append to the passage index, listed with the keyword index and the names index in the post-append steps.
- Check: a query of nonsense words ("xqzv plorf wibble") answers "Nothing to search for"; "establishment of democracy" shows its list.

## 2026-10-11 Prose windows for every long-prose work: merged short units, Thucydides re-cut, the full run (staged 2026-10-11; run 2026-10-11 23:22 to 23:49)

- What: the cutter (`scripts/corpus/prose_windows.py`) gains `--merge-units`
  (on by default; `--no-merge-units` is the first run's behaviour). Within one
  part file, consecutive units shorter than the target are joined into one
  window until the next would pass 1,200 characters; the window's `ref_start`
  is the first unit's reference, `ref_end` the last's, `units` counts them and
  there is no `sub`. A unit longer than the target is cut into pieces with
  `sub` and character offsets as before and closes the group before it. A
  window never crosses a part file. Merged windows get ids
  `<part file>:prosem:<n>`, so they never collide with the first run's
  `<part file>:prose:<n>`. `--exclude-ids` skips the works a first run
  already cut. `apply_passage_rows.py` gains `--mode remove --remove-ids FILE`
  (deletes rows from `ids.json`, `embeddings.npy` and `descriptions.jsonl`
  together, with `.bak-<tag>` copies).
- Thucydides re-cut: its units are single sections of 300 to 500 characters.
  With merging, 3,577 windows (median 296 characters) become 1,159 (minimum
  319, median 1,038, 10th percentile 797, 90th 1,171, maximum 1,259, mean
  1,003). Described (stamp `prose-all-20261011`, 16 in flight, 3.2 windows a
  second, 6.6 minutes, no error rows) and encoded with the embed service
  (1,159 x 1,024, unit length).
- Replacing the old Thucydides rows: `--mode replace` works by id and only
  rewrites rows whose ids are already indexed, and the new ids differ in
  number and kind from the old ones, so the old 3,577 rows (ids
  `thucydides.peleponnesian_war.part.N:prose:n`, tag `prose-20261011`) are
  removed with `--mode remove` and the 1,159 new ones appended with
  `--mode append`.
- The full cut: the 1,510 prose works over the audit threshold (median fine
  window over 3,000 characters) less the 12 works that already hold prose
  windows (the Annals, Thucydides and the first run's ten) give 991 works and
  153,405 windows (minimum 22, median 1,031, 10th percentile 678, 90th 1,214,
  maximum 2,357, mean 1,009 characters; about 155 million characters). The
  first estimate was 274,684 windows without merging.
- Describing: job `prose-all-describe` (`~/bin/tess-job`, cap 4 GB, detached),
  Qwen 3.8 27B FP8, thinking off, 32 in flight (16 gave 3.2 windows a second
  on the Thucydides run, 32 gives 4.3), stamp `prose-all-20261011`, output
  `descriptions_all.jsonl`. Started 14:22 on 2026-10-11; after ten minutes 2,615
  rows, 4.3 windows a second (about 258 a minute), 7 error rows (the describer
  retries them on resume), key spend 4.53 to 5.97 units for the first 2,650
  windows, so about 80 units for the run; expected finish about 00:15 on
  2026-10-12. Resumable: rerunning the same command skips every id that
  already has a `desc`. Progress is the row count of `descriptions_all.jsonl`
  against 153,405.
- Outputs in `~/tesserae-backups/prose_windows_all_2026-10-11/`:
  `windows_thuc.jsonl`, `descriptions_thuc.jsonl`, `vectors_thuc.npy`,
  `ids_thuc.json`, `old_ids_thuc.json` (the 3,577 rows to remove),
  `windows_all.jsonl` (268 MB), `windows_report_all.json`,
  `descriptions_all.jsonl` (growing), and the describer's scripts.
- Steps on production, to run, once this pull request is merged and pulled and
  the description job has finished. Each under `~/bin/tess-job`, cap 10 for
  anything that reads the index:
  1. Resume the describer if it stopped (from the outputs folder): `~/bin/tess-job
     prose-all-describe 4 bash -c "cd ~/tesserae-backups/prose_windows_all_2026-10-11
     && python describe_prose_windows.py --windows windows_all.jsonl --model
     Qwen/Qwen3.8-27B-FP8 --stamp prose-all-20261011 --out descriptions_all.jsonl
     --no-think --concurrency 32"`. Run it once more at the end to retry the
     error rows. Done when `descriptions_all.jsonl` holds 153,405 rows with a
     `desc`.
  2. Lockstep check (ids, vectors and description rows equal), one Similar
     Passages and one Theme Search request.
  3. Back up `window_texts.db`; upsert `windows_thuc.jsonl` and
     `windows_all.jsonl` with `prose_windows.py --upsert-db
     data/passage_index/window_texts.db --upsert-from FILE`. The old
     Thucydides texts stay as unused rows.
  4. `make_encode_blobs.py descriptions_all.jsonl blobs_all.jsonl.gz`, then
     encode on the campus GPU by `research/threads/GPU_JOB_RECIPE.md`
     (`vectors_all.npy`, `ids_all.json`).
  5. Thucydides: `apply_passage_rows.py --index data/passage_index --mode remove
     --remove-ids old_ids_thuc.json --tag prose-all-20261011`, then
     `--mode append --sidecar descriptions_thuc.jsonl --tag prose-all-20261011
     --vectors vectors_thuc.npy --vector-ids ids_thuc.json`.
  6. Everything else: `apply_passage_rows.py --index data/passage_index --sidecar
     descriptions_all.jsonl --mode append --tag prose-all-20261011 --vectors
     vectors_all.npy --vector-ids ids_all.json` (cap 12G).
  7. `scripts/build_desc_fts.py`; `scripts/corpus/build_window_names.py` to a
     `.new` file, then swap in; `touch tesseraev6_flask.wsgi`; the lockstep
     check again.
- Checks: the reference search (arma virum); Ask a Work on Thucydides and on a
  merged work showing windows with `ref_start` different from `ref_end`; Similar
  Passages on a Thucydides section maps to a merged window.
- RUN 2026-10-11. Describing finished 23:14 after 532 minutes (4.8 windows a
  second at the end, 32 in flight): 153,404 of 153,405 windows described; one,
  `celsus.de_medicina.part.4:prosem:4`, failed on every attempt and is left
  out. Encoded on one campus GPU (job `prose-all-20261011-7c3eeda5`): 153,404
  vectors in 100 seconds in four parts, every part's SHA-256 matching the
  job's result lines, id order equal to the input, norms 1.000, cosine 1.000
  against the local encoder on three samples; the job and its public input
  deleted. Install 23:22 to 23:49 under tess-job: window texts upserted
  (153,405 rows plus the 1,159 Thucydides rows; `window_texts.db` 697,188
  rows, backup `.bak-prose-all-20261011`); Thucydides 3,577 rows removed
  (index 542,625 to 539,048) and 1,159 appended (540,207); the full run
  appended (693,611 ids, vectors and description rows, in lockstep at each
  step); keyword index 45 seconds; names index 22.8 minutes to `.new`,
  checked and swapped; `desc_vocab.json` rebuilt (41 seconds); wsgi touched.
  Checks passed: lockstep 693,611; the reference search (arma virum, Ovid
  present); Ask a Work on Thucydides for the plague gives a strong band with
  merged windows (2.57.1 to 2.58.1 first); Similar Passages on Thuc. 2.47.3
  maps to the merged window 2.47.1 to 2.47.4; the gibberish check still
  answers that nothing is known. Similar Passages for Annals 1.1 now leads
  with Appian's preface to the Civil Wars, Josephus 20.155, Tacitus'
  Histories 1.1, Dio's book 50 and Herodian 1.1.4, all paragraph windows
  (before the run: Plutarch, Publicola 1.1, then chapter-sized windows of
  Dio, Zosimus and Herodian).

## 2026-10-11 Finer passage windows for long prose chapters (run 2026-10-11 12:28 to 12:50)

- What: a new window scale, `prose`, for prose works whose corpus line is a
  whole chapter or section. The fine windows are a fixed twelve lines, so in
  the Annals one window (and one description) ran from 7,500 to 15,000
  characters and covered a dozen scenes; a question about one episode found
  its material only when the summary happened to mention it. The new windows
  are runs of whole sentences from one unit, about 1,200 characters each, with
  `ref_start` and `ref_end` both the unit's own reference (so the Reader and
  `GET /api/passages/lines` keep working), `sub` (ordinal in the unit, from 1)
  and `char_start`/`char_end` (offsets in the unit). Code:
  `scripts/corpus/prose_window_audit.py`, `scripts/corpus/prose_windows.py`,
  `scripts/corpus/describe_prose_windows.py`, `scripts/corpus/make_encode_blobs.py`,
  `--vectors`/`--vector-ids` in `scripts/corpus/apply_passage_rows.py`, and
  `backend/passage_index.py` (a work with `prose` windows is ranked, covered
  and mapped at that scale and its fine windows are left out of Theme Search,
  the neighbour lists and the passages-that-name-a-person list; coarse windows
  stay).
- Audit (fine windows measured against the corpus texts; 3,470 works,
  3,066 windows whose lines could not be located are not counted): 1,511
  works have a median fine window over 3,000 characters, holding 39,512 fine
  windows, and 1,510 of them are prose (39,506 windows). Cutting all 1,510 at
  1,200 characters gives 274,684 new windows, over the 25,000 the plan allowed
  for a full run, so the run covered the Annals, Thucydides and the ten works
  with the longest median.
- Run, 2026-10-11 (staged, nothing installed):
  - Cut: `prose_windows.py --work tacitus.annales --work
    thucydides.peleponnesian_war --audit audit.json --top 10` produced 6,438
    windows (median 501 characters, 10th percentile 189, 90th 1,196, maximum
    2,309). Annals 746 windows (median 874, was 7,500 to 15,000), Thucydides
    3,577 (median 296: its units are single sections of 300 to 500
    characters, so a window is now one section), the ten longest-median works
    2,115.
  - Described on the university gateway, Qwen 3.8 27B FP8 with thinking off,
    16 in flight, stamp `prose-fine-20261011`: 6,438 of 6,438, no error rows,
    26.3 minutes, 2.56 gateway units (key spend 1.12 to 3.67).
  - Encoded on the campus GPU by `research/threads/GPU_JOB_RECIPE.md`
    (job `prose-win-20261011-2d179`, one part, 19 seconds from start, 1,024
    dimensions, SHA-256 of both parts matched the job's report; cosine
    against the embed service on 16 random windows, minimum 0.99999857).
    6,438 vectors for 6,438 descriptions, ids identical and in the same order.
  - Outputs in `~/tesserae-backups/prose_windows_2026-10-11/`: `audit.json`
    (1.0 MB), `audit.md`, `windows.jsonl` (7.4 MB), `windows_report.json`,
    `descriptions.jsonl` (6.7 MB, the sidecar for the append), `blobs.jsonl.gz`,
    `vectors.npy` (26.4 MB, float32) and `ids.json`.
- Not done: the other 1,500 or so prose works (about 268,000 windows). Most are
  short works whose units are already short, so the gain is mainly the
  works with long units; the audit file lists them by median.
- Run on production 2026-10-11 12:28 to 12:50 (`install_prose.sh` in the session scratchpad, every heavy step under tess-job): lockstep before 536,187 / 536,187 / 536,187; `window_texts.db` backed up as `.bak-prose-20261011` and 6,438 rows upserted (542,624 rows); append with the GPU vectors, 6,438 new records, index 542,625 / 542,625 / 542,625 after; keyword index rebuilt in 31 s (670 MB); names index rebuilt to `.new` in 20 minutes, checked and swapped; wsgi touched; lockstep held. The first attempt failed because the cutter demanded `--out` for the upsert step, and a `--dry-run` of that step wrote the rows anyway; both fixed in this record's pull request.
- Checks 2026-10-11 12:50: the reference search (arma virum, 50 results, Ovid present); Ask a Work on Annals 1 to 6 for "mutinies of the legions" now leads with 1.31, 1.39, 1.30, 1.45, 1.32 and 1.16 at the prose scale (band moderate); "the death of Germanicus" with 2.73, 3.2, 2.82, 2.71, 2.70 and 2.75 (band strong); by one reading of the gists, passages directly on the subject in the first ten rose from 3 to 6 for both questions against the pilot; Similar Passages on Ann. 1.16 maps to a prose window; `GET /api/passages/lines` returns the chapter for a prose result when the reference is given in the index's own case.
- Steps on production, once this pull request is merged and pulled. Each under
  `~/bin/tess-job`, cap 10 for anything that reads the index:
  1. Lockstep check before touching anything: ids, vectors and description
     rows equal (535,272 and more as the index stands); one Similar Passages
     and one Theme Search request answer.
  2. Back up `window_texts.db`, then `python scripts/corpus/prose_windows.py
     --upsert-db data/passage_index/window_texts.db --upsert-from
     <outputs>/windows.jsonl` (adds 6,438 rows).
  3. `python scripts/corpus/apply_passage_rows.py --index data/passage_index
     --sidecar <outputs>/descriptions.jsonl --mode append --tag prose-20261011
     --vectors <outputs>/vectors.npy --vector-ids <outputs>/ids.json` (cap 10G;
     takes backups tagged `bak-prose-20261011`, asserts the counts before and
     after).
  4. Description keyword index: `scripts/build_desc_fts.py` (about 30 seconds).
  5. Names index: `scripts/corpus/build_window_names.py` to a `.new` file, then
     swap in.
  6. `touch tesseraev6_flask.wsgi`, then the lockstep check again.
  7. Not needed for the Reader or Ask a Work: line vectors (no text changed)
     and the connection map (it reads fine windows).
- Checks: Ask a Work on Annals 1 to 6 for "mutinies of the legions" shows
  windows with `sub` fields and gists that name one episode; the lockstep
  counts; the reference search ("arma virum"); `GET /api/passages/lines` for
  the `work` and `ref_start` of a prose result returns the whole unit.
- Backups to keep: `ids.json`, `embeddings.npy`, `descriptions.jsonl`
  (`.bak-prose-20261011`) and `window_texts.db`, `desc_fts.sqlite`,
  `window_names.db` as backed up in the steps.

## 2026-10-11 Translation files: facing-page OCR noise stripped from 19 of 25 Loeb-scan files (run 2026-10-11 09:00)
- What: 25 translation files aligned from Internet Archive scans of Loeb
  volumes carry the OCR of the facing Greek or Latin page in their English
  units (runs such as "143 ARISTOPHANES > / dwvi) juapd, yegovas ..."), the
  fifteen Aristophanes plays, Anthology books 7 and 10 to 16, Euclid's
  Elements, three Plato dialogues, the Catalepton and Varro's Res rusticae.
  The script finds runs of eight or more tokens in which fewer than three of
  every eight are English-like (English learned from the clean translation
  files) and removes them with the running headers. Units keep their index,
  so `ref_to_unit` is unchanged. Euclid's and the Plato files' measured
  "junk" is diagram letters and the speaker label "Str.", and the script
  changes almost nothing in them.
- Script: `scripts/translations/strip_ocr_noise.py` (test:
  `tests/test_strip_ocr_noise.py`). It refuses to write a file whose
  content words fall by more than 3 percent.
- Run 2026-10-11 08:50: the script over all 25 files into the backup folder.
  Before and after, as the share of alphabetic tokens that cannot be English:
  Wasps 13.5 to 6.1 percent, Acharnians 11.9 to 3.5, Knights 12.1 to 3.8, the
  other seven plays 2.9 to 6.4 down to 1.6 to 3.7, Anthology books 7 and 10 to
  16 8.4 to 10.9 down to 1.2 to 4.7 (book 8 6.1 to 3.5). 4,163 runs and 469
  running headers removed; content words (four or more letters, in the
  vocabulary) fell by 0 to 2.7 percent per file; two Anthology units (books 10
  and 16) were entirely Greek OCR and are now empty. The residue is shorter
  Greek runs under eight tokens, which the rule leaves.
- Installed 2026-10-11 09:00: the ten Aristophanes plays and the nine
  Anthology books (19 files), originals first copied to
  `~/tesserae-backups/translations_ocr_clean_2026-10-11/originals/`, mode 664,
  wsgi touched. NOT installed, after reading `samples.md`: Varro and the
  Catalepton, where the removed runs were real quotations and citations in
  the translator's notes (Latin verse quoted, a bibliographic reference) for
  a gain of 0.4 and 0.0 points; Euclid and the three Plato dialogues, where
  the measured junk is diagram letters and the speaker label and the script
  changes nothing. Their files on production are unchanged.
- Check 2026-10-11 09:01: Knights 196 through `/api/passages/translation`
  no longer carries the ARISTOPHANES header or the Greek run.
- The command, for the record (nothing is installed by this step):
  `~/bin/tess-job --fg ocr_run 4 python3 -I scripts/translations/strip_ocr_noise.py --src /var/www/tesseraev6_flask/data/translations --out ~/tesserae-backups/translations_ocr_clean_2026-10-11/cleaned --report ~/tesserae-backups/translations_ocr_clean_2026-10-11/report.md`
  writes the cleaned files, `report.md` and `samples.md`. Read the samples
  before installing.
- Install (after review): back up the 25 originals to
  `~/tesserae-backups/translations_ocr_clean_2026-10-11/originals/`, copy each
  cleaned file over `/var/www/tesseraev6_flask/data/translations/<name>`
  (keep mode 664), then `touch /var/www/tesseraev6_flask/tesseraev6_flask.wsgi`.
- Checks: `/api/passages/translation?work=aristophanes.knights&refs=arist.%20knights.%20196`
  (Knights unit 8) no longer carries "ARISTOPHANES >" or the Greek run; the
  Reader's Translation tab on Aristophanes, Knights 100 reads as English; the
  `/api/passages/translations?language=grc` list still shows the 25 works.

## 2026-10-10 Translation files: HTML character entities decoded (run 2026-10-10 23:58)
- What: 14 of the 1,043 translation files in `data/translations/` (not in git)
  held HTML entities from the web pages they were transcribed from, which the
  Reader showed as "C&aelig;sar" and "Augustus&mdash;more" (Tacitus, Annals
  1.1). Pliny the Elder's Natural History held 4,780 of them, Tacitus's Annals
  667, Ammianus 581, the Histories 360, and the rest a few each (`&aelig;`
  4,031 in all, `&mdash;` 1,120, `&oelig;` 495, `&AElig;` 482, and accented
  letters).
- Run: every string in each of the 14 files decoded with Python's
  `html.unescape` and the file rewritten in place, mode 664, after a copy to
  `~/tesserae-backups/translations_entities_bak-20261010/`; then the wsgi
  touch. Five malformed entities remain (two each in Aristophanes' Acharnians
  and Knights, one in Gellius), which `html.unescape` does not recognise.
- Code: `backend/translations.py` now decodes entities when a file is loaded,
  so a future transcription cannot show them.
## 2026-10-10 Scholarship Theme Search, packed index and install steps (packed 2026-10-10; installed 2026-10-11 00:58 EDT)

- Run: the five packed files (335 MB) were copied from
  `~/tesserae-backups/scholarship_theme_idx_2026-10-09/packed/` into
  `/var/www/tesseraev6_flask/data/scholarship_theme/` under temporary names
  and renamed, mode 664, with the wsgi touch, right after #798 deployed.
  Checks: `/api/scholarship/theme?q=the+catalogue+of+ships+as+a+poetic+device`
  answered `available: true` with ten results (Classical Philology sentences
  and commentary notes on the Aeneid among them); `/api/scope` reports 82,814
  scholarship windows.

- Source: the index built on 2026-10-09 with the campus GPU, `~/tesserae-backups/scholarship_theme_idx_2026-10-09/`
  (82,814 windows: 48,043 commentary notes and 34,771 article sentences), read only.
- Pack (run 2026-10-10, nothing on production touched):
  `python3 scripts/scholarship/pack_scholarship_theme.py --index ~/tesserae-backups/scholarship_theme_idx_2026-10-09 --out ~/tesserae-backups/scholarship_theme_idx_2026-10-09/packed`
  (reads `/var/www/tesseraev6_flask/data/citation_index/citations.db` for article journal, title, year and link, and
  `/var/www/tesseraev6_flask/texts/` for the language of each work, both only read; `--citations` and `--texts` change them).
- Files and sizes in `packed/`: `embeddings.npy` 169.6 MB (float16, 82,814 by 1,024), `ids.json` 2.1 MB,
  `windows.jsonl` 73.8 MB, `windows_fts.db` 89.2 MB (FTS5), and `manifest.json`. 335 MB in all.
- To run (install, after the pull request is merged and deployed): copy the four files into
  `/var/www/tesseraev6_flask/data/scholarship_theme/` (create the folder, mode 775 group tessdev, files 664) under
  temporary names such as `embeddings.npy.new`, rename each over its final name, then
  `touch /var/www/tesseraev6_flask/tesseraev6_flask.wsgi`. The route reads the files again whenever one changes.
- Checks: `curl 'https://tesserae.caset.buffalo.edu/api/scholarship/theme?q=the%20catalogue%20of%20ships%20as%20a%20poetic%20device'`
  answers `available: true` with ten results, both commentary and article rows, each with a `link`; `/api/scope`
  shows `scholarship_windows` 82814; `/api/languages` still answers. The query encoder service
  (`tesserae-embed`, port 8090) has to be running.

## 2026-10-10 Event summaries and scholarship tied to passages (run 2026-10-10 20:46)

- Run: the rebuilt file (summaries for 1,026 of 1,485 events from the Wikipedia
  paragraphs fetched on 2026-10-09; the scholarship table rebuilt from the
  citation index for every passage of rank 10 or better or judged yes, 4,827
  rows) was copied into `/var/www/tesseraev6_flask/data/events/` under a
  temporary name and renamed, the previous file kept as
  `event_dossiers.sqlite.bak-20261010-1800`, with the wsgi touch, right after
  #789 deployed. Checks: `/api/events` answers; the Siege of Corfinium carries
  the Wikipedia paragraph with its credit and licence and four articles with
  their passage ranks (1 and 5).

- What: the Events database gains a Wikipedia summary for 1,026 of 1,485 events
  (the other 459 have no article and keep the Wikidata description) and its
  `scholarship` table is rebuilt so that each article row names the passage that
  brought it in (`passage_rank`, `passage_ref`). Articles are looked up in the
  offline citation index (`data/citation_index/citations.db`, read-only) for the
  14,356 passages with rank 10 or better or judged "yes". The table went from
  1,693 rows to 4,827 (4,653 article rows, one per event, article and passage, and
  the 174 commentary rows, each tied to its passage when the reference falls in
  one). The API shows one row per article. Siege of Corfinium (Q18001862) keeps
  5 rows: 2 for Messer's article on mutiny, 3 for the Seneca, On Benefits 3.23.3
  to 3.28.1 articles (the passage at rank 5 spans six chapters).
- Build (run 2026-10-10 in a scratch copy, nothing on production touched):
  `python3 scripts/events/add_summaries.py ~/tesserae-backups/events/event_dossiers_2026-10-10.sqlite ~/tesserae-backups/sources/events/wikipedia_all/intros_all.json STAGE.sqlite`
  then `python3 scripts/events/relink_scholarship.py STAGE.sqlite ~/tesserae-backups/events/event_dossiers_2026-10-10_summaries.sqlite`
  (the second reads `/var/www/tesseraev6_flask/data/citation_index/citations.db`; `--citation-index PATH` changes it).
- To run (install, after the pull request is merged and deployed):
  `cp ~/tesserae-backups/events/event_dossiers_2026-10-10_summaries.sqlite /var/www/tesseraev6_flask/data/events/event_dossiers.sqlite.new`
  then `mv /var/www/tesseraev6_flask/data/events/event_dossiers.sqlite.new /var/www/tesseraev6_flask/data/events/event_dossiers.sqlite`
  then `touch /var/www/tesseraev6_flask/tesseraev6_flask.wsgi`. Keep the old file first as
  `event_dossiers.sqlite.bak-20261010`.
- Checks: `/api/events/Q18001862` has `event.summary` beginning "The siege of Corfinium was the first significant military confrontation" with `summary_url` ending `/Siege_of_Corfinium`, and its 5 scholarship rows carry `passage_ref`; `/api/events` still answers with 1,485 events in `total_all`.
- Source: English Wikipedia opening paragraphs fetched 2026-10-09
  (`~/tesserae-backups/sources/events/wikipedia_all/intros_all.json`), CC BY-SA 4.0, credited
  in `data/sources_credits.json`.

## 2026-10-10 Greek coin types added to the Coins collection (run 2026-10-10 18:30)

- Run: `coins.sqlite` rebuilt with the seven Greek catalogues (106,176 types) and
  the description vectors for all 46,244 distinct descriptions were installed in
  `/var/www/tesseraev6_flask/data/coins/` right after #774 deployed, the Roman
  files kept beside them as `*.bak-roman-20261010`. The vectors came from the
  campus GPU (job coins-greek-20261010-fb2223cd: 46,244 descriptions in 25 s
  from model load, one part, SHA-256 checked; the 26,461 Roman rows agree with
  the installed Roman vectors at cosine 1.00000 mean, 0.9967 minimum from
  float16 rounding). Checks: facets total 106176 over nine sources; "capricorn"
  143; the legend "basileos seleukou" typed without accents 1,720; "elephant"
  1,261; a Heracles theme query returns Greek types.
- Measured after the install (`scratchpad measure_live.py`, the ten test
  passages through the live route): over all nine catalogues the Greek types
  took 27 of the 50 top-five places and about 3 were real parallels, so the
  Roman figure fell from 0.34 to about 0.26. The next release restricts a
  Latin passage's related imagery to OCRE and CRRO, which gives the 2026-10-09
  lists back exactly (the Roman vectors are the same).

- What: seven Greek catalogues published through nomisma.org join the 58,715
  Roman types in `data/coins/coins.sqlite`, giving 106,176 types. Counts match the
  Nomisma dataset counts exactly (IRIS 13,399, Corpus Nummorum 11,913, Seleucid
  Coins Online 8,694, PELLA 7,228, Ptolemaic Coins Online 3,650, BIGR 2,107,
  Levantine Coinages Online (LCO) 470).
  The licences are ODbL for all but Corpus Nummorum (CC BY-NC-SA 3.0, from the Nomisma
  dataset list). One record each
  in `data/sources_credits.json`. Left out were the dataset coded AoD (Art of
  Devastation, First World War items, not coins of Antigonid kings), Antigonid
  Coins Online (182 types, no English descriptions), OSCAR (no English
  descriptions), Online Coins of Ostrogothic Italy, Condottieri Medals and Iron Age Coins in
  Britain (Celtic coinage, not Greek or Roman).
- Fetched 2026-10-10 with `scripts/coins/fetch_nomisma.py` (about 40 minutes for
  all seven run side by side) into one fresh folder per set under
  `~/tesserae-backups/sources/archaeology/` (`sco`, `pella`, `pco`, `bigr`,
  `iris`, `corpus_nummorum`, `lco`), each with a README giving the date,
  query and licence page, and `nomisma_refs_greek_2026-10-10/` for the labels:
  `python -I scripts/coins/fetch_nomisma.py types --dataset http://numismatics.org/sco/ --out sco/sco_types.jsonl`
  (dataset addresses: `http://numismatics.org/{sco,pella,pco}/`,
  `https://numismatics.org/{bigr,lco}/`, `https://greekcoinage.org/iris/`,
  `https://www.corpus-nummorum.eu/`), then
  `python -I scripts/coins/fetch_nomisma.py refs --types sco/sco_types.jsonl --refs nomisma_refs_greek_2026-10-10`.
- Rebuild, each through `tess-job` (cap 8 GB, convert 10 seconds, build 15 seconds):
  1. `python -I scripts/coins/convert_ocre.py --dataset ocre=ocre/ocre_types.jsonl --dataset crro=crro/crro_types.jsonl --dataset cn=corpus_nummorum/corpus_nummorum_types.jsonl --dataset sco=sco/sco_types.jsonl --dataset pella=pella/pella_types.jsonl --dataset pco=pco/pco_types.jsonl --dataset bigr=bigr/bigr_types.jsonl --dataset iris=iris/iris_types.jsonl --dataset lco=lco/lco_types.jsonl --refs nomisma_refs --refs nomisma_refs_greek_2026-10-10 --output coins.jsonl --stats-out coins_stats.json`
     (paths under `~/tesserae-backups/sources/archaeology/`). Keep `ocre` and
     `crro` first, because the order fixes the numbering of the descriptions.
  2. `python -I scripts/coins/build_coins_db.py --input coins.jsonl --out coins.sqlite`
     Expect `106176 types` with ocre 56113, crro 2602, cn 11913, sco 8694, pella 7228,
     pco 3650, bigr 2107, iris 13399, lco 470.
  3. `python scripts/coins/embed_descriptions.py --input coins.jsonl --out DIR --rows-out descriptions_input.jsonl`
     writes one row per distinct description: 46,244 rows, of which the first
     26,461 are the Roman descriptions in the order of the vectors already made (checked
     string for string), and 19,783 are new. Only the new rows need embedding.
- Install (after the pull request merges and the vectors exist):
  1. Copy `coins.sqlite` to `/var/www/tesseraev6_flask/data/coins/coins.sqlite.new`
     and rename it over `coins.sqlite`. The search text now folds final and
     lunate sigma to sigma and reads Latin look-alike capitals inside Greek
     words as Greek, so the database must be the rebuilt one, not the old one.
  2. When the 19,783 new vectors are embedded (campus GPU, `--blobs-out` as
     above on the full `coins.jsonl`, or `--from-parts`), run
     `embed_descriptions.py ... --from-parts` and
     `pack_descriptions.py --emb DIR --out data/coins`. Expect
     `packed 46244 descriptions for 99453 coin types`. Copy `descriptions.npy` and
     `descriptions_ids.json` to production under temporary names and rename them
     (ids file first). Until then, `descriptions_ids.json` of the Roman build
     still matches its own matrix, and the Greek types simply have no vectors.
  3. `touch /var/www/tesseraev6_flask/tesseraev6_flask.wsgi`, then `curl .../api/languages`.
- Checks: `curl .../api/coins/facets` answers `total` 106176 and nine sources.
  A Greek legend: `curl '.../api/coins?q=%CE%B2%CE%B1%CF%83%CE%B9%CE%BB%CE%B5%CF%89%CF%83+%CF%83%CE%B5%CE%BB%CE%B5%CF%85%CE%BA%CE%BF%CF%85'`
  (the words for "of King Seleucus" typed without accents) returns Seleucid
  types first. A Greek description search, `curl '.../api/coins?q=elephant&source=sco'`,
  returns Seleucid types. After the vectors are installed, rerun
  `scripts/coins/measure_for_passage.py` on the ten test passages (Roman-only
  figure: 17 of 50 matches right, 0.34) to see whether the Greek descriptions
  dilute the Roman results.
- Reader name links: the authority and portrait names of the Greek sets
  (Alexander III, Seleucus I, Ptolemy I and so on) are now offered to the
  name-link matcher in `backend/coins_passage.py`. Check a Latin passage that
  names Alexander after the install.

## 2026-10-10 Coins in the Reader and Theme Search, install of the description vectors (run 2026-10-10 16:50)

- Run: `descriptions.npy` (54 MB) and `descriptions_ids.json` (6.6 MB), packed
  from the 2026-10-09 vectors, were copied into
  `/var/www/tesseraev6_flask/data/coins/` under temporary names and renamed,
  mode 664, with the wsgi touch, right after #771 deployed. Checks: the theme
  query returned ten results; the Reader request for Suetonius, Augustus 94
  returned five related descriptions and the name links Augustus, Julius
  Caesar, Agrippa and Drusus Caesar. The campus GPU run below is still to do,
  for the record only (the installed vectors are the same encoder's output).
## 2026-10-10 Objects collection, build and install (run 2026-10-10 17:31)

- Run: the three files built on 2026-10-10 were copied into
  `/var/www/tesseraev6_flask/data/objects/` (new folder) under temporary names
  and renamed, with the wsgi touch, right after #773 deployed. Checks: facets
  total 1361 (chicago 395, cleveland 305, smithsonian 661); "amazons" 2 objects
  with the Chicago credit line; the theme query "wine mixed with water at a
  drinking party" returned ten results with the Cleveland dinos and a Chicago
  column krater among the first three.

- What: `data/objects/objects.sqlite` (1,361 Greek, Roman and Etruscan objects with a
  museum catalogue description) and, beside it, `descriptions.npy` and
  `descriptions_ids.json` (one 1,024-value float16 vector for each of 1,210
  distinct description texts, in the format of the coins vectors). Read by
  `/api/objects`, `/api/objects/facets`, `/api/objects/<id>` and `/api/objects/theme`.
  Sizes: 2.8 MB, 2.5 MB and 0.6 MB. None of them is in git. With no database the
  routes answer `available: false`. Path override: `TESSERAE_OBJECTS_DB`.
- Sources, read on 2026-10-10, each downloaded into a fresh folder under
  `~/tesserae-backups/sources/archaeology/` with a README that quotes the licence.
  Cleveland Museum of Art Open Access API (CC0): 688 records fetched, 305 kept.
  Art Institute of Chicago data dump `artic-api-data.tar.bz2` (records CC0,
  descriptions CC BY 4.0): 2,197 records in the department, 395 kept.
  Smithsonian Open Access (CC0), National Museum of Natural History Anthropology
  unit in the open-access bucket: 529,663 records read, 1,268 Greek, Roman or Etruscan,
  661 kept. Kept means a description or note of at least 40 characters. Coins are left
  out (they are the Coins collection), and for Chicago so are Byzantine, Coptic and
  Islamic objects, anything dated after 400 CE and places far to the east. 104
  Smithsonian cast-gem records are left out because their note says it was copied from
  another institution's database.
- Steps to build, each through `tess-job`, cap 8 GB:
  1. `python -I scripts/objects/fetch_objects.py --museum cleveland --out <new folder>`
  2. `python -I scripts/objects/fetch_objects.py --museum chicago --download --archive <new folder>/artic-api-data.tar.bz2 --out <new folder>`
  3. `python -I scripts/objects/fetch_objects.py --museum smithsonian --download --raw <new folder>/raw --out <new folder>`
     (about 1.1 GB of line-delimited JSON in `raw/`, which can be deleted afterwards)
  4. `python -I scripts/objects/build_objects_db.py --cleveland <folder> --chicago <folder> --smithsonian <folder> --out data/objects/objects.sqlite`
     Prints fetched, kept and dropped per museum and writes `objects_build_report.json`.
     Expect 1,361 objects (305, 395, 661).
  5. With the encoder service running, `python -I scripts/objects/embed_object_descriptions.py --db data/objects/objects.sqlite --out data/objects`
     Expect `embedded 1210 texts`. It took 479 seconds on 2026-10-10 against the
     site's own encoder on its processor. The script stops above 5,000 texts (that size
     goes to the campus GPU, see `scripts/coins/embed_descriptions.py --blobs-out`).
- Steps to install, on the production checkout, after the pull request merges:
  1. Copy the three files to `/var/www/tesseraev6_flask/data/objects/` under temporary
     names (`objects.sqlite.new`, `descriptions.npy.new`, `descriptions_ids.json.new`) and
     rename them into place, the database last, then `touch tesseraev6_flask.wsgi`.
     Nothing is installed on the server beyond these data files.
  2. Checks, with the encoder service running. `curl '.../api/objects/facets'` reports
     `total: 1361` and museums `{"chicago": 395, "cleveland": 305, "smithsonian": 661}`.
     `curl '.../api/objects?q=amazons'` returns the matching objects with a credit line.
     `curl '.../api/objects/theme?q=wine+mixed+with+water+at+a+drinking+party'` returns
     ten results, mixing krater and dinos descriptions from Cleveland and Chicago at the top.
- Memory: the matrix is 2.5 MB and the ids file 0.6 MB. No model is loaded.
- Not measured: how often the nearest description is a real match. The Theme Search
  label says so. Images are linked from the museums' servers (Cleveland, and Chicago only
  where its public domain flag is true) and never stored here. The Smithsonian records in
  the bucket carry no image address.


## 2026-10-10 Coins collection, build and install of `data/coins/coins.sqlite` (run 2026-10-10 16:50)

- Run: the file built on 2026-10-10 (47 MB, 58,715 types) was copied into
  `/var/www/tesseraev6_flask/data/coins/` (new folder, group tessdev) under a
  temporary name and renamed, mode 664, with the wsgi touch, right after
  #771 deployed. Checks: facets `available: true`, total 58715 (ocre 56113,
  crro 2602); "capricorn" 125 types; "harbor" 17; `/api/languages` 200.

- What: the Coins page and `/api/coins` read one SQLite file of 58,715 Roman
  coin types (56,113 from OCRE, 2,602 from CRRO, nomisma.org exports, ODbL),
  one row per type with its legends, both descriptions, mint and Pleiades id,
  dates, authority, portrait, denomination and material, and an FTS5 index
  over the legends and descriptions. The export, the three small label files
  and the converter come from the coins prototype (#736). The data file is not
  in git.
- Steps, in a checkout of the merged branch, each through `tess-job`:
  1. `df -h /` (100 GB free at least).
  2. Convert (peak under 4 GB, cap 8 GB, about a minute):
     `python -I scripts/coins/convert_ocre.py --ocre ~/tesserae-backups/sources/archaeology/ocre/ocre_types.jsonl --crro ~/tesserae-backups/sources/archaeology/crro/crro_types.jsonl --refs ~/tesserae-backups/sources/archaeology/nomisma_refs --output coins.jsonl --stats-out coins_stats.json`
     Expect 58,715 types (56,113 and 2,602), 53,993 with legend text.
  3. Build (cap 4 GB, under a minute, 47 MB out):
     `python -I scripts/coins/build_coins_db.py --input coins.jsonl --out data/coins/coins.sqlite`
     Expect `58715 types {'ocre': 56113, 'crro': 2602}`.
  4. Install: create `/var/www/tesseraev6_flask/data/coins/` if absent
     (group-writable, group tessdev), copy the file in under a temporary name,
     rename it into place, then touch `tesseraev6_flask.wsgi`.
  5. Check: `curl .../api/coins/facets` answers `available: true` and
     `total` 58715. `curl '.../api/coins?q=capricorn'` returns 125 types.
     `curl .../api/languages` still answers.
- Switching on: the Coins entry appears in the main menu only for a visitor who
  has the Coins collection on (the Archaeological and Everything profiles, or
  the switch by name).

## 2026-10-10 Page views table (created 09:56 on the reload after #761, confirmed)

Confirmed 2026-10-10 09:56: the table exists, a verification post from the server answered 204 and inserted one row, and that row (visit `0123456789abcdef01234567`) was deleted afterwards so the record starts clean.


The application creates the `page_views` table and its two indexes itself, on its first start after the deploy, with the same `CREATE TABLE IF NOT EXISTS` step that creates the search log. No data operation is needed. To confirm, run `SELECT count(*) FROM page_views` in the production database. The count is zero until the first visit after the deploy, and the admin Analytics tab shows "not being recorded yet" until the table exists.

## Standing rule: every import adds a credits record

Every import of texts, documents or a scholarship source (a commentary
collection, a citation index, a search service) adds one record to
`data/sources_credits.json` in the same pull request: collection, name, url,
licence_name, licence_url, version (commit, DOI or date), retrieved date,
what we use, notes. The Sources and credits section of the Text Credits page
(`/text-credits`) is built from that file, so no code change is needed.
Record only licence wording that was read at the source; say so in `notes`
where it could not be read. `tests/test_sources_credits.py` checks the
required fields.
## Restricted texts: how they are held

Some texts arrive under a licence that allows them to sit in the index and
be searched. They may never be copied elsewhere, as a standalone download, a
copy in the public repository, or a text passed on to someone else. Such a
text lives on
the production server under `texts/<lang>/` exactly like any other text, and
every search, the Reader and the passage windows treat it the same way.
What differs is everywhere the text could otherwise leave the server.

`data/restricted_texts.json` is the registry: an id, a holder, a fixed
credit line, the licence terms, and when the licence was added (and, if it
has ended, when). It ships empty and is read through one module,
`backend/restricted_texts.py`, so every other guardrail asks the same
question of that one module.

Two exits are closed. The registry never reaches the public repository:
`scripts/corpus/restricted_texts_gitignore.py` turns each entry into the
`.gitignore` rule that keeps its files out, regenerated whenever the
registry changes. And it never reaches a bundle anyone can take away: the
per-language texts download and the passage-index release script both
leave a restricted text out and report how many were withheld and why.

Wherever a passage is shown, its credit line follows it: in search results,
the Reader header, Similar Passages, Theme Comparison, and the Sources
page, a restricted text carries the registry's fixed credit line in place
of (or beside) its usual citation.

When a licence ends, `scripts/corpus/remove_restricted_text.py` is the
removal procedure: dry run by default, reporting what it would take out of
the texts, the lemma cache, the inverted index and the passage index before
anything is deleted, with a dated backup kept of each file it removes.

## 2026-10-10 Usage summary for the admin panel (run 09:15; nightly timer installed)

Run 2026-10-10 09:15 under `tess-job` (4 GB cap, 18 s): `data/usage/usage_stats.json` written with ten months (September 698 application loads), mode 664. The user timer `tess-usage-stats.timer` (03:10 nightly, `Persistent=true`) runs the script with `--force`, sets the mode, and copies the access log to `~/tesserae-backups/access_log/` so the visitor record does not depend on the server's log rotation. Rerun after the referrer rule change (same day).


The Analytics tab reads a JSON summary of the web server's access log. The
script `scripts/usage/build_usage_stats.py` writes it. It streams the log and
takes under a minute. The route `GET /api/admin/usage` serves the file named
by `TESSERAE_USAGE_STATS`, by default `data/usage/usage_stats.json`.

Steps on production
1. From the production root with the production venv, run
   `python scripts/usage/build_usage_stats.py --out /var/www/tesseraev6_flask/data/usage/usage_stats.json`
   (add `--force` to replace an existing file).
2. `chmod 664 /var/www/tesseraev6_flask/data/usage/usage_stats.json` so the web workers can read it.
3. The user timer `tess-usage-stats.timer` runs the script each night at 03:10 with `--force` (installed 2026-10-10).
4. Check the Analytics tab shows the months table.

## 2026-10-10 Journal citation index: seven Studies in Philology articles re-dated from 1992 to 1922 (run on production)

`data/citation_index/citations.db` carried seven articles of Studies in Philology volume 19 with year 1992; the volume is 1922 (the journal began in 1906, one volume a year) and the Early Journal Content ends at 1922. Three of the seven cite held works and were shown as 1992 articles in the Scholarship tab. Fixed in place with a backup first:

```
cp -p data/citation_index/citations.db ~/tesserae-backups/citations.db.bak-years-20261010
python3 -c "import sqlite3; c=sqlite3.connect('data/citation_index/citations.db'); c.execute(\"UPDATE articles SET year=1922 WHERE journal='Studies in Philology' AND year=1992\"); c.commit()"
```

Seven rows updated; `SELECT max(year) FROM articles` now returns 1922. The same change applied to the source copy `~/tesserae-backups/ejc_index_2026-09-14/citations.db` so a rebuild keeps it.

## 2026-10-09 Document scholarship index built, install steps for production (run 2026-10-10 00:24 EDT)

The file `data/citation_index/document_citations.db` holds the journal sentences (JSTOR Early Journal Content) and commentary notes that cite an inscription, papyrus or coin of the documents collection, linked by edition reference. Read by `GET /api/documents/<id>/scholarship` and shown as the Scholarship section of `/document`.

Built 2026-10-09 by `scripts/documents/build_document_citation_index.py` under `tess-job` (4 GB cap, 3 min 32 s, peak 138 MB resident) from the copied `documents/metadata.db`, `citation_index/citations.db` (article metadata), the cached full texts in `~/tesserae-backups/ejc_index_2026-09-14/raw/` and the 392 commentary files. Result: 956 rows, 742 distinct documents, 288 distinct articles (27,244 articles read, 1,368 front and back matter skipped). A hit that matches more than three documents is dropped as too ambiguous (25). All 49 commentary hits name works outside the corpus (mostly CIG), so the index holds no commentary rows yet. The built file is kept at `~/tesserae-backups/document_citations_2026-10-09.db`.

Steps for production, run 2026-10-10 00:24 after pull request #751 merged and was deployed (step 4 returned `count` 16):
1. `cp ~/tesserae-backups/document_citations_2026-10-09.db /var/www/tesseraev6_flask/data/citation_index/document_citations.db.new && mv /var/www/tesseraev6_flask/data/citation_index/document_citations.db.new /var/www/tesseraev6_flask/data/citation_index/document_citations.db`
2. `chmod 664 /var/www/tesseraev6_flask/data/citation_index/document_citations.db`
3. `touch /var/www/tesseraev6_flask/tesseraev6_flask.wsgi`, then `curl .../api/languages`.
4. Check one document: `curl '.../api/documents/edr:aEDR173504/scholarship'` returns `count` 16 with JSTOR links, and `/document?doc=edr:aEDR173504&documents=1` shows the Scholarship section.

After a change to the documents collection, the recogniser or the journal texts, rebuild by running the script with `--out` set to a new file. It refuses to overwrite.

## 2026-10-09 Xenophon's Hellenica and Cassius Dio, books 36 to 55: steps for production (run 16:55 to 17:17; windows and map with the second batch 19:08 to 21:41 EDT)
- What: `xenophon.hellenica` (1,146 lines, 7 book files) and
  `cassius_dio.roman_history` (4,403 lines, 20 book files, books 36 to 55),
  29 `.tess` files in `texts/grc/` that arrive with the merge, each with an
  English translation file under `data/translations/` that does not.
- Sources and rights: Greek from PerseusDL/canonical-greekLit
  `tlg0032.tlg001.perseus-grc2` (Marchant, OCT 1900) and
  `tlg0385.tlg001.perseus-grc2` (Cary, Loeb Greek 1914 to 1917), both CC BY-SA
  4.0 per the TEI headers, downloaded 2026-10-09 into
  `~/tesserae-backups/sources/historians/`. English for the Hellenica from
  the same repository (`tlg0032.tlg001.perseus-eng2`, Brownson, Loeb
  1918 to 1921, US public domain by date). English for Dio from Bill
  Thayer's LacusCurtius transcription of Cary's Loeb (1914 to 1927), pages
  `penelope.uchicago.edu/Thayer/E/Roman/Texts/Cassius_Dio/<book>*.html`. The
  home page states the volumes are in the public domain (earlier copyright
  lapsed, later not renewed), and the volumes the Greek comes from (1914 to
  1917) are public domain by date anyway. No licence doubt found. The credits
  page needs no new record. The existing "Literary texts" and "Translations"
  records cover them and the per-work rows are in `backend/text_sources.json`.
- Measured before production (all in a worktree, dev copies only):
  - conversion: the Greek letters in the TEI body and in the `.tess` lines
    agree (Dio 967,986 of 967,986, Hellenica 352,370 of 352,445 with the
    remainder being headings), all 29 files pass
    `scripts/corpus/validate_tess.py`.
  - Hellenica translation: 1,146 of 1,146 lines, one unit per line, proper
    names 0.964 of 500, length correlation 0.964, confidence high.
  - Dio translation: 4,384 of 4,403 lines (0.9957). 49 Greek sections whose
    number Thayer's page does not mark share the English of the preceding
    section in their chapter. The 19 uncovered lines are the book tables of
    contents (37.0.0 to 55.0.0). Proper names 0.914 of 500, length
    correlation 0.772, confidence high. Cary's English for 36.1 to 36.17 and
    55.9.5 to 55.34, which Perseus's Greek lacks, is dropped.
  - lemma caches built in the worktree: 29 files, 2 seconds.
  - index extension tried on a copy of `grc_index.db`: 1,268 to 1,297 texts,
    489,109 lines, lemma_doc_freq rebuilt, no errors.
  - reference tests through a dev server on the worktree (Latin index
    untouched): lemma "arma virum" 371 distinct loci with Vergil 24, Ovid
    14, Livy 42, Quintilian 1, Seneca 3, and the exact search 21.
- Steps on production, each under `~/bin/tess-job` with the caps shown:
  1. After the merge, pull on production (the `.tess` files, descriptions,
     provenance rows and Dio's date entry arrive). Run
     `scripts/keep_old_bundles.sh save` first only if the pull changes
     `client/`, which this one does not.
  2. Translations: copy the two files into `data/translations/` (they are not
     in git). They were made by `python scripts/translations/align_hellenica.py
     <tlg0032.tlg001.perseus-eng2.xml> texts/grc/xenophon.hellenica.tess <dir>`
     and `python scripts/translations/align_dio.py <dir of the 20 Thayer
     pages named 36.html to 55.html> texts/grc/cassius_dio.roman_history.tess
     <dir>`, and kept with these checksums in
     `~/tesserae-backups/sources/historians/translations_out/`:
     `grc__xenophon.hellenica.json` sha256
     `e3b9b4896e60e79eac54d836b8bda3c29e456f4b0ab968723ede227aed114970`,
     `grc__cassius_dio.roman_history.json` sha256
     `6c9707a2976c212b67104fcc9a13bb5e6c5c62d861d76950a92070ad5279909d`.
     The whole-work file serves the book files. Reloaded with the next
     `touch tesseraev6_flask.wsgi`.
  3. Lemma caches with `scripts/batch_lemma_cache.py grc` (cap 8G). Only the 29
     new files are computed.
  4. Extend the Greek index on a copy with `scripts/corpus/add_texts_to_index.py
     --db <copy of grc_index.db> --language grc --cache-dir
     <production>/cache/lemmas --add` with the 29 filenames (whole work and
     book files, as for Herodotus and Thucydides), check integrity, swap in,
     `touch tesseraev6_flask.wsgi`. Keep `grc_index.db.bak-historians-20261009`.
  5. Rare-bigram table: `scripts/corpus/rebuild_bigrams.py grc`.
  6. Passage windows, descriptions, vectors: `scripts/corpus/build_batch_windows.py
     --upsert-db`, `scripts/corpus/describe_windows.py` on the gateway,
     `scripts/corpus/apply_passage_rows.py --mode append`, then
     `scripts/build_desc_fts.py`, and the window names index
     (`scripts/corpus/build_window_names.py`). Follow the 2026-10-08 Victor
     entry and the lockstep check (counts in
     step, then one Similar Passages and one Theme Search request). The line
     vectors for the semantic channel were made for earlier imports by an
     encoding run with bowphs/SPhilBerta that has no committed script.
  7. Connection map: `scripts/build_connections_map.py` (cap 10G, about 50
     minutes), after step 6.
  8. The Greek phrase and quotation tables and the Greek literary reuse table
     are separate builds. Rebuild them only if the earlier entries do so for
     a Greek import of this size (the reuse table build for Greek has not
     finished within 12 GB before).
  9. Check: `scripts/corpus/verify_text_coverage.py --root <production>
     --language grc xenophon.hellenica cassius_dio.roman_history`, the
     reference search, and a Greek line search that returns the new works
     (for example the lemmas of "Pompeius" and "Mithridates" together).
- Backups to keep: each file replaced in steps 4 to 7, tagged
  `bak-historians-20261009`.

## 2026-10-09 Event dossiers installed, then refreshed after the historians import (19:00 and 22:50 EDT)
- What: `data/events/event_dossiers.sqlite`, read by the Events page
  (`/api/events`, #737), built offline by the event anchor scripts of #729
  (draft): for each of 1,485 Wikidata events (battles, sieges, treaties and
  campaigns, 800 BC to AD 600) the passages that name it, judged by Qwen 3.8
  27B on the university's AI gateway, the inscriptions and papyri near its
  place and date, and the scholarship that cites those passages.
- First install 19:00: the file built 18:54 (`event_dossiers_2026-10-09.sqlite`
  in the backups folder): 1,485 events, 110,496 passages, 8,138 documents,
  1,892 scholarship rows, 96,773 cached judgements; 11,350 gateway requests,
  36.7 million prompt tokens, 108 minutes of request time. 842 events had no
  passage judged to tell of them.
- Refresh 21:48 to 22:42, installed 22:50 after the two historians batches
  had their passage windows: a dated copy with the judgement cache kept, the
  five columns the final pass adds dropped first, the four result tables
  emptied, every event gathered again and only windows never judged sent to
  the gateway (5,594 requests). Result: 113,645 passages, 125,298 cached
  judgements, 787 events without a telling passage (55 filled); the new
  historians contribute 285 passages judged to tell of an event (Procopius
  121, Dio 66, Diodorus 46, Zosimus 30, Hellenica 20, Plutarch's Lysander 2).
  The 19:00 file is kept beside the refreshed one in the backups folder.
- Reload by touching the WSGI file; checked `/api/events` and the Sicilian
  Expedition dossier (46 passages, 39 judged to tell of it) after each
  install.

## 2026-10-09 Works-by-language sidecar rewritten; passage index folder made group-writable (21:48 EDT)
- What: `data/passage_index/works_by_language.json`, the small file Browse
  Corpus reads for its Theme Search coverage badge (and the event gatherer
  reads for the language of each work), had been stale since 19 September.
  The web workers detected the stale stamp and answered from the loaded
  index (the right answer, at about 90 seconds on each cold worker) but
  could not write the file back because the folder was not writable by the
  web account.
- Done: the file rewritten from the live answer (`/api/passages/works` for
  each language): Latin 726 to 737 works, Greek 828 to 837, Urdu 6 to 20,
  Persian 23 to 30, Arabic 6 to 147 (Arabic windows exist and stay held back
  from Theme Search by the index's own gate); the stamp set to the index's
  date. The folder's group set to the web group with the setgid bit, so the
  workers can refresh the file themselves from now on. The install script for
  a Greek batch rewrites the file at its end. The stale copy is kept as
  `works_by_language.json.bak-stale-20260919`.

## 2026-10-09 Both historians batches: what ran on production (16:55 to 21:41 EDT)
- Steps 1 to 5 and 9 ran once per batch with `~/bin/tess-install-greek-batch`
  (the first batch with its one-off predecessor script): pull, translations
  copied after a checksum, lemma caches (`scripts/batch_lemma_cache.py grc`,
  cap 8G, 29 new files each), the Greek index extended on a copy and swapped
  in (`scripts/corpus/add_texts_to_index.py --add`, cap 12G; after both,
  1,326 texts and 514,834 lines, `lemma_doc_freq` rebuilt, integrity ok;
  backups `grc_index.db.bak-historians-20261009` and
  `.bak-historians2-20261009`), rare-bigram table rebuilt
  (`scripts/corpus/rebuild_bigrams.py grc`, cap 8G), reference searches
  passed after each reload.
- Steps 6 and 7 ran once for both batches with
  `~/bin/tess-install-greek-windows` (config `hist12.cfg`):
  - 4,355 passage windows built (`scripts/corpus/build_batch_windows.py
    --upsert-db`, cap 8G) for the 27 files that carry windows (the part files
    of works that have parts, the whole file otherwise, as the index already
    does); `window_texts.db` 530,916 to 535,271 rows, backup
    `.bak-historians-windows-20261009`.
  - described by Qwen 3.8 27B on the university's AI gateway with thinking
    off (stamp `qwen38-bullsai-20261009`): 4,355 of 4,355 in 27.5 minutes at
    2.7 a second, no errors.
  - appended with `scripts/corpus/apply_passage_rows.py --mode append` (cap
    10G, vectors from the encoder service): the index went from 530,917 to
    535,272 ids, vectors and description rows, in step before and after.
  - description keyword index rebuilt (`scripts/build_desc_fts.py`, 34 s,
    665 MB; backup `desc_fts.sqlite.bak-historians-windows-20261009`).
  - names index rebuilt to `.new` and swapped (`scripts/corpus/build_window_names.py`,
    cap 4G): window-name pairs 2,504,787 to 2,593,052, distinct names 38,598
    to 39,081; backup `window_names.db.bak-historians-windows-20261009`.
  - line vectors for all 58 files (parts and wholes) with bowphs/SPhilBerta on
    the processor, raw float32, same meta format as the existing files
    (mean norms 5.6 to 5.8), written under `backend/embeddings/grc/`.
  - connection map rebuilt (`scripts/build_connections_map.py`, cap 10G):
    374,546 fine windows, 61.3 minutes, peak 7.38 GB.
- Checks: lockstep held at every step; reference searches passed; the
  coverage check reported every store present for all 58 files except the
  Sources page rows for Cassius Dio and Procopius (fixed in this entry's
  pull request: a row for Dio was missing and the Procopius row named the
  work differently from the catalogue).
- Memory: the launcher refused nothing; the steps waited for budget behind
  the event dossier run and a verification job earlier in the evening.
## 2026-10-09 Document image links: moved hosts rewritten in metadata.db (21:40 and 21:55 EDT)
- What: the documents collection's `display` table (`data/documents/metadata.db`,
  field `image_url`, 155,261 rows) carried the addresses of photographs as the
  source projects published them. Two hosts had moved. The Epigraphic
  Database Heidelberg's 24,851 photo addresses (`edh-www.adw.uni-heidelberg.de/fotos/F*.JPG`)
  returned 404; they were rewritten to the photo record pages
  `https://edh.ub.uni-heidelberg.de/edh/foto/F*` (four random samples
  answered 200 before the change; one PDF link on the same host was moved to
  the new host as well). The old CIL photo server's 3,018 addresses
  (`cil-old.bbaw.de/test06/bilder/datenbank/PH*.jpg`) were rewritten to
  `https://cil.bbaw.de/ace/resources/PH/<block>/PH*.jpg` (16 of 16 samples
  returned 200 image/jpeg; three more checked at apply time).
- How: the Heidelberg rows by a one-off statement after a backup
  (`~/tesserae-backups/documents/metadata.db.bak-edhlinks-20261009`); the CIL
  rows with `scripts/documents/fix_image_urls.py --apply` (this PR), which
  backs the file up beside itself first. Both rules live in
  `scripts/documents/image_url_rules.py`, which the extractor applies when it
  writes `image_url` rows, so a rebuild does not bring the old addresses back.
  Reload by touching the WSGI file.
- Not rewritten: 7,008 rows (4.5 percent) point at hosts that no longer serve
  anything and have no verified replacement (3,424 bare I.Sicily file names,
  2,271 access.bl.uk, 1,064 wwwapp.cc.columbia.edu, and six small hosts). The
  document page hides them and says how many were omitted
  (`client/src/components/documents/imageHosts.json` lists the hosts). About
  4,400 rows are on hosts that refuse scripts but serve browsers (Michigan's
  APIS, the British Museum, the Met) and are kept; about 2,000 are on hosts
  that answered with server errors on the audit night (Petrie Museum, several
  papyrus collections) and are kept for a recheck. Audit record (private):
  `research/documents/2026-10-09_image_link_audit.md`.

## 2026-10-09 Documentary reuse tables rebuilt with the literary-works discount and the order-free rule (built 19:05 to 20:05, installed 20:08, reinstalled 20:45 EDT)
- What: `cache/reuse_pairs/la_documents.db` and `grc_documents.db` (literature
  against the inscriptions and papyri, read by the Reader's Reuse tab under
  the documents trial) rebuilt with `scripts/reuse/build_documents_reuse_table.py
  --max-literary-works 10` and the order-free rule on, against production's
  texts, lemma caches and documents indexes. Each build under `~/bin/tess-job`
  with an 8 GB cap: Latin 42 minutes, Greek 17 minutes; the candidates caches
  (`la_candidates.sqlite`, `grc_candidates.sqlite`, kept beside the job log)
  let a threshold sweep run in seconds.
- Counts: Latin 4,173 pairs (3,412 before; 424 with two or more shared
  phrases, 956 by the order-free rule), Greek 1,725 (1,509 before; 68 and 153).
  Sweep: with the discount off, Latin 4,441 and Greek 1,785; N=5 keeps 3,332
  and 1,375; N=10 keeps 4,050 and 1,725. N=10 was chosen because N=5 dropped
  quotations of famous formulae that the literature itself repeats (Iliad 8.539
  "immortal and ageless" in a papyrus, Horace Ep. 2.1.190 "equitum peditumque
  catervae" on a stone); Aeneid 1.204 is lost at both (its one shared phrase
  is current in 12 works, the limit of frequency alone, open). Ten random
  pairs read per language: the two-or-more tier is nearly all real (Georgics
  1.20 and Aeneid 12.60 inscribed, Vulgate verses on stones, the Claudian
  titulature in Josephus and a papyrus, Iliad 1.400 in a papyrus); the
  single-phrase tier is still mostly coincidence, which is why the Reader
  labels it "possible".
- Second pass the same evening: reading what N=10 removed showed 123 Latin
  pairs with two or more shared phrases among them, all whole verses quoted
  on stones that several Fathers also quote (edh:HD025119, 17 shared phrases
  in 14 works; papyri:114821 in 56). The discount now applies to the
  single-phrase tier only (shared == 1); the two-or-more tier is kept whatever
  the phrase's currency. Rebuilt from the candidates caches in seconds and
  reinstalled 20:45: Latin 4,050 to 4,173, Greek unchanged.
- Backups: the 16:45 tables and stats at
  `~/tesserae-backups/reuse_pairs/*_documents*.bak-filtered-20261009`.
- Reload by touching the WSGI file; checked `/api/reuse/line` for Aeneid 1.1
  (seven inscriptions and the fullers' graffito) and Ephesians 5.16.

## 2026-10-09 Documentary reuse tables installed on production, then replaced by filtered builds (about 01:27 and 16:45 EDT)
- What: `cache/reuse_pairs/la_documents.db` (Latin literature against the
  inscriptions and papyri) installed about 01:27 from a build on production's
  own lemma caches and documents index: 6,769 pairs. Read by
  `backend/reuse_documents.py` for the Reader's Reuse tab under the
  documents trial (`?documents=1`).
- A hand check of a random sample found most pairs to be coincidences
  sharing only function words or numerals, kept by the rare-single-ngram
  rule. The build script gained a quality filter (#725): a pair is kept
  only if it shares at least two distinct content lemmas, in a contiguous
  run of at least two, with function words and numerals (spelled out, Roman,
  Greek alphabetic) not counting as content. Lists:
  `data/documents/function_words_la.txt` and `function_words_grc.txt`, from
  CLTK's stopword lists plus numeral blocks, sources in the file headers.
- Rebuilt with the filter (each under `~/bin/tess-job` with a 12G cap, peak
  under 3 GB, 11 to 16 minutes) and installed about 16:45:
  - Latin `la_documents.db`: 3,412 pairs (from 6,769). The unfiltered table
    and its stats are kept at
    `~/tesserae-backups/reuse_pairs/la_documents.db.bak-unfiltered-20261009`.
  - Greek `grc_documents.db`: 1,509 pairs (new on production; the earlier
    Greek build stalled at the memory cap until the one-cache-at-a-time
    change in #725). In the labelled sample every real quotation survived
    (Lord's Prayer, Ephesians 5.16, the Orphic gold-tablet verses, Greek
    Anthology epigrams inscribed at Pompeii, Hesiod Theogony 305 in a papyrus).
- Residual noise is shared technical vocabulary (medical, astronomical,
  accounting) and stock phrases. A discount for phrases common across the
  literature is the next step.
- Reload by touching the WSGI file; no index or frontend change was needed
  for the tables themselves.

## 2026-10-09 Names index rebuilt with Greek forms (morning)
- What: `cache/window_names.db` rebuilt so Greek names keep their full
  forms in the Names panel (#721: a misplaced accent no longer cuts a name
  short). Backup `~/tesserae-backups/window_names.db.bak-greekforms-20261009`.

## 2026-10-09 Diodorus (books 1 to 5, 18 to 20), Procopius' Wars, Zosimus and four Plutarch Lives, steps for production (run 18:35 to 18:59; windows and map with the first batch 19:08 to 21:41 EDT)
- What: `diodorus_siculus.bibliotheca_historica` (4,166 lines, 9 files),
  `procopius.wars` (7,240 lines, 9 files), `zosimus.historia_nova` (1,071 lines,
  7 files), `plutarch.lysander`, `plutarch.dion`, `plutarch.eumenes` and
  `plutarch.demosthenes` (771 lines, 4 files): 29 `.tess` files in
  `texts/grc/` that arrive with the merge, each work with an English
  translation file under `data/translations/` that does not. Diodorus books 11
  to 17 are not included (a decision on them is pending). The Hellenica and
  Dio import (the entry for #733) is a separate batch with the same steps and
  can be run in one pass with this one.
- Sources and rights, all downloaded 2026-10-09 into
  `~/tesserae-backups/sources/historians/`:
  - The Greek is CC BY-SA 4.0 per the TEI headers. It comes from
    PerseusDL/canonical-greekLit `tlg0060.tlg001.perseus-grc5` (Diodorus 1 to 5, Vogel, Teubner 1888 to
    1890) and `perseus-grc6` (Diodorus 18 to 20, Fischer, Teubner 1903 to
    1906), `tlg4029.tlg001.perseus-grc2` (Procopius, Dewing's Loeb Greek),
    `tlg0007.tlg032`, `tlg041`, `tlg054` and `tlg060` `perseus-grc2`
    (Plutarch, Perrin's Loeb Greek) and from OpenGreekAndLatin/First1KGreek
    `tlg4084.tlg001.1st1K-grc1` (Zosimus, Mendelssohn, Teubner 1887, which
    First1KGreek made by OCR of an Internet Archive scan).
  - English for Diodorus: Bill Thayer's LacusCurtius transcription of the Loeb
    volumes (pages `1A` to `5D` and `18A` to `20E` under
    `penelope.uchicago.edu/Thayer/E/Roman/Texts/Diodorus_Siculus/`). Thayer's
    Diodorus page states that Loeb volumes I to XI are in the public domain
    because their copyright was not renewed, with the renewal years named
    (volume I 1960/61, II 1962/63, III 1966/67, IX 1974/75, X 1981/82). The
    volumes used here are I, II, III (Oldfather, 1933 to 1939) and IX, X (Geer,
    1947 and 1954). All five are marked public domain, so no volume is skipped.
    That rests on non-renewal, not on the date, and on Thayer's reading of the
    1978 Copyright Act, which is the same ground the Dio volumes of #733 rest on.
  - English for Procopius: LacusCurtius, Dewing's Loeb (1914 to 1928), pages
    `1A` to `8J` under `.../Procopius/Wars/`. Thayer states volumes I to III
    have lapsed and IV and V were not renewed. Book 2 chapters 5 to 10 and some
    other pages carry his "not yet proofread" mark (`sec_for_proofing`), which
    the aligner accepts.
  - The English for the four Lives is Perrin's Loeb (1914 to 1926), from the Perseus
    repository (`tlg0007.tlg032`, `041`, `054`, `060` `perseus-eng2`).
  - English for Zosimus: "The History of Count Zosimus", London, Green and
    Chaplin, 1814, the OCR text of Internet Archive item
    `historyofcountzo00zosiuoft`. Public domain by date.
  The existing "Literary texts" and "Translations" credit records cover these
  and the per-work rows are in `backend/text_sources.json`.
- Measured before production (all in a worktree and on scratch copies):
  - conversion: Greek letters in the TEI body against the `.tess` lines,
    Diodorus 1 to 5 670,405 of 670,405 and 18 to 20 456,488 of 456,488,
    Procopius 1,191,955 of 1,192,183, Zosimus 347,749 of 347,749, Plutarch
    0.9997 to 0.9999 (the remainder is headings). All 29 files pass
    `scripts/corpus/validate_tess.py`.
  - repairs: `scripts/corpus/repair_zosimus_procopius_text.py` fixes 18
    words in Zosimus where the OCR lost a letter (20 places carried "??"
    between breathing marks), drops 2 unreadable consular numerals (6.2.1), and
    separates two words in Procopius 8 that a combining breathing had joined.
    Other OCR faults in the Zosimus Greek were not searched for.
  - Diodorus translation: 4,158 of 4,166 lines (0.9981), the other 8 being the
    book tables of contents (chapter 0). 16 Greek sections that Thayer does not
    mark share the English of the section before. Proper names 0.896 of 500,
    length correlation 0.923, confidence high.
  - Procopius translation: 7,240 of 7,240 lines, 19 sections sharing the
    English of the one before. Proper names 0.798 of 500, length correlation
    0.953, confidence high.
  - Plutarch translations: exact by chapter.section, every line matched. Proper
    names Lysander 0.943 (140), Eumenes 1.000 (90), Demosthenes 0.975 (118), Dion
    0.818 (313). Length correlation 0.924, 0.946, 0.930, 0.930.
  - Zosimus translation: the 1814 English has no chapter numbers, so 1,071 of
    1,071 lines are mapped to 420 English paragraphs (314 blocks, 3.4 lines
    each) by dynamic programming on proper names and position, recorded
    approximate with confidence medium. Proper names 0.942 of 500. The length
    correlation (0.08) is not meaningful for blocks. A spot check found the
    paragraph right for four of five lines and off by a few paragraphs for one
    (5.29.6). The scan reads well. About 5.3% of its words are not in the
    corpus's English vocabulary, mostly names, rare words and words split across
    lines, and a sample of 40 such words found five real OCR faults.
  - lemma caches built in the worktree: 29 files, 7 seconds.
  - index extension tried on a copy of `grc_index.db` with
    `scripts/corpus/add_texts_to_index.py --add` of the 29 filenames:
    1,268 to 1,297 texts, 478,011 to 503,736 lines (+25,725, the sum of the
    files), lemma_doc_freq rebuilt, no errors. Lemma lookups on the copy
    return the new works (Βελισάριος 340 postings in the Wars file, Λύσανδρος
    77 in the Lysander, Ἀγαθοκλῆς 162 in Diodorus, Ἀλάριχος in Procopius).
    No dev server was started, because the Greek frequency table recompute
    killed the one tried for #733, and the Latin index and all search code are
    untouched by this change, so the "arma virum" reference search was not rerun.
- Steps on production, each under `~/bin/tess-job` with the caps shown:
  1. After the merge, pull on production (the `.tess` files, descriptions,
     provenance rows and dates arrive). `client/` is untouched.
  2. Translations: copy the seven files into `data/translations/` (not in
     git). They were made with `scripts/translations/align_diodorus.py`,
     `align_procopius.py`, `align_plutarch.py` and `align_zosimus.py` and kept in
     `~/tesserae-backups/sources/historians/translations_out/` with these
     sha256 checksums:
     `grc__diodorus_siculus.bibliotheca_historica.json`
     `c355e6ce43bf1e6f41dc62644d13d7268178624d873a45c237320b22f128c192`,
     `grc__procopius.wars.json`
     `e553e185e3390713a3ceb975db431e1d86706187e72160f6651db9a2c781c834`,
     `grc__zosimus.historia_nova.json`
     `be7b99c9a54e99a94bff84a74970b81864a3a9fb7a14e01102cf071625ffbb7e`,
     `grc__plutarch.lysander.json`
     `08de98dccc4e2cdcdae79ff8528ff545c920b14dfc71f4c1c484b4578ab092b9`,
     `grc__plutarch.eumenes.json`
     `223134678eb44d0d7e279c9a55fb34a9d0ae4adb9954a1faca5557d9ddda98d8`,
     `grc__plutarch.dion.json`
     `8f9cc32e6b7e2a33bd6e2ba152e1e380261f2dc84d48337d457e29ec16e99b53`,
     `grc__plutarch.demosthenes.json`
     `f7631539f76bdcc2ae52c7f10ecc7496cf819efb8b95f7c10b033a7628a37ce1`.
     The whole-work file serves the book files. Reloaded with the next
     `touch tesseraev6_flask.wsgi`.
  3. Lemma caches with `scripts/batch_lemma_cache.py grc` (cap 8G). Only the 29
     new files are computed.
  4. Extend the Greek index on a copy exactly as in step 4 of the #733 entry,
     with the 29 filenames here (or all 58 in one pass), check integrity, swap
     in, `touch tesseraev6_flask.wsgi`. Keep
     `grc_index.db.bak-historians2-20261009`.
  5. Rare-bigram table: `scripts/corpus/rebuild_bigrams.py grc`.
  6. Passage windows, descriptions, vectors, names index, connection map and the
     Greek phrase, quotation and reuse tables follow steps 6 to 8 of the #733
     entry. Follow the lockstep check (counts in step, then one Similar
     Passages and one Theme Search request).
  7. Check: `scripts/corpus/verify_text_coverage.py --root <production>
     --language grc diodorus_siculus.bibliotheca_historica procopius.wars
     zosimus.historia_nova plutarch.lysander plutarch.dion plutarch.eumenes
     plutarch.demosthenes`, the reference search, and a Greek line search that
     returns the new works (for example the lemmas of "Belisarius" and
     "Chosroes" together).
- Backups to keep: each file replaced in steps 4 to 6, tagged
  `bak-historians2-20261009`.

## 2026-10-10 Diodorus books 11 to 17 from the Loeb Greek, steps for production (decided 21:45 EDT, run 23:49 to 01:41)

- Run, the owner having decided to import: the batch install script
  (`tess-install-greek-batch` with `diodorus_loeb.cfg`) pulled the merge,
  installed the regenerated whole-work translation after its checksum (the old
  file kept beside the sources as `.bak-diodorus-loeb-20261010`), built the
  lemma caches for the seven parts and, with its stale cache set aside, the
  whole file, added the seven parts to the Greek index on a copy and swapped it
  in, and rebuilt the rare-bigram table; then the whole file was re-indexed on
  a copy with `--replace` (text 1306, 8,123 lines, 273,617 postings, was
  142,894) and swapped in. The windows script (`tess-install-greek-windows`
  with an explicit window pattern for the seven parts) built 915 passage
  windows (113, 92, 148, 157, 93, 125 and 187 by book), had them described on
  the university's gateway (stamp `qwen38-bullsai-20261010`), appended them
  (535,272 to 536,187 windows, ids, vectors and descriptions in step), rebuilt
  the description keyword index and the names index, encoded line vectors for
  all eight changed files, and rebuilt the connection map (3,752,010 edges,
  61 minutes, 1.1 GB, peak 7.6 GB). The works sidecar was rewritten (Greek 837
  works). Coverage check: all sixteen Diodorus files complete in every store;
  the reference search passed. A Greek line search for the lemmas of Leonidas
  and Thermopylae returns 11.10.4 and 11.24.1 among its eight hits.
- One slip during the run: the batch script's first attempt stopped at its own
  count of new cache files (the pattern named the text files, which the cache
  files are not named after) after the caches were built, and was re-run with
  the pattern corrected. Two copies of the windows runner had been left waiting
  and both started the description step; both were stopped, one well-formed
  description per window was kept (725 of 915), and a single runner resumed
  from that step. Nothing reached the index twice (the lockstep counts above).
- Backups: every replaced file tagged `bak-diodorus-loeb-20261010`.

- What: seven new part files `diodorus_siculus.bibliotheca_historica.part.11`
  to `.part.17` in `texts/grc/` (491, 401, 691, 694, 448, 513 and 719 lines,
  3,957 in all, the same work id as books 1 to 5 and 18 to 20), and the
  whole-work file `diodorus_siculus.bibliotheca_historica.tess` extended from
  4,166 to 8,123 lines with the new books between 5 and 18. The nine existing
  part files are byte for byte unchanged and the old whole file is the
  concatenation of them, so the new whole file is the concatenation of all
  fifteen in book order.
- Rights, to be settled by the lead before anything is installed. The Greek is
  the Loeb text (Oldfather vols. IV to VI, Sherman vol. VII, Welles vol. VIII,
  1946 to 1963), not the Teubner that books 1 to 5 and 18 to 20 use. The
  Perseus encoding is CC BY-SA 4.0 per its header, which says nothing about the
  underlying edition. The U.S. position rests on non-renewal of the Loeb
  volumes and on the thin protection a critical edition's running text
  carries. A European court ruling of March 2026 makes the editor's choices
  less safe there. The renewal records have not been checked in the Stanford
  database for volume VIII (1963) or the others. The full note is private. The
  fallback if a rights holder objects is to build books 11 to 17 from the
  Teubner scans, which needs OCR correction and re-segmentation.
- Sources, downloaded 2026-10-09 and 2026-10-10 into
  `~/tesserae-backups/sources/historians/`: `diodorus_loeb/tlg0060.tlg001.perseus-grc4.xml`
  (sha256 `166fd9d2ce7461a876e3a3210b88267c0e622f79854729c12b0bb0e113212289`) and,
  for the English, 35 LacusCurtius pages `11A` to `17F` in `diodorus_en_loeb/`
  (one request every two seconds, cached). Thayer's Diodorus page states
  non-renewal for Loeb volumes IV (1973/74), V (1977/78), VI (1981/82), VII
  (1979/80) and VIII (1990/91), the volumes that carry books 11 to 17. Volume IV
  carries books 11 to 12.40, V books 12.41 to 13, VI books 14 to 15.19,
  VII books 15.20 to 16.65 and VIII books 16.66 to 17 (the page headers say
  which volume each page is from).
- Measured in a worktree and on scratch copies:
  - conversion with `scripts/corpus/perseus_greek_history_to_tess.py` as it
    stands: Greek letters in the TEI body against the `.tess` lines 1,054,393 of
    1,054,393. The seven new files and the new whole file pass
    `scripts/corpus/validate_tess.py` (as do the nine existing part files).
  - translation, `scripts/translations/align_diodorus.py` extended to books 11
    to 17: all fifteen books together 8,108 of 8,123 lines (0.9982), the 15
    uncovered being the book tables of contents (chapter 0). For books 11 to
    17 alone: 3,950 of 3,957 (0.9982), the 7 uncovered being the tables of
    contents, 9 Greek sections that Thayer does not mark sharing the English of
    the section before, proper names 0.938 of 500, length correlation 0.928,
    confidence high. For the whole file: 25 sections share a neighbour's
    English, proper names 0.934 of 500, length correlation 0.924. Two English
    sections in the new books have no Greek section (15.34.6 and 16.15.5).
- Steps on production, if the lead decides to import. Each under
  `~/bin/tess-job` with the caps shown:
  1. After the merge, pull on production.
  2. Translation. The regenerated whole-work file replaces the live one
     (`data/translations/grc__diodorus_siculus.bibliotheca_historica.json`, not in git). The new file is kept in
     `~/tesserae-backups/sources/historians/translations_out/diodorus_loeb/`
     with sha256
     `0cd02e0b814606515c8e1622171626a853d3633084224d129d3a58ed66a6b591`
     (also in `~/tesserae-backups/jobs/configs/diodorus_loeb.sums`). Back up the live file first.
  3. Lemma caches: delete `cache/lemmas/grc/diodorus_siculus.bibliotheca_historica.json`
     (the whole-work file changed), then `scripts/batch_lemma_cache.py grc` (cap 8G)
     builds it and the seven new parts.
  4. Greek index, on a copy as in the earlier Diodorus entry.
     Run `scripts/corpus/add_texts_to_index.py` with `--add` for the seven part
     filenames and `--replace diodorus_siculus.bibliotheca_historica.tess`. Check integrity,
     swap in, `touch tesseraev6_flask.wsgi`. Keep `grc_index.db.bak-diodorus-loeb-20261010`.
  5. Rare-bigram table: `scripts/corpus/rebuild_bigrams.py grc`.
  6. Passage windows for the seven new part files only (the whole file carries
     none), descriptions, vectors, names index, connection map, line vectors for
     the 8 changed or new files, and the Greek phrase, quotation and reuse
     tables, following the "what ran on production" entry above. Follow the
     lockstep check (counts in step, then one Similar Passages and one Theme
     Search request).
  7. Check: `scripts/corpus/verify_text_coverage.py --root <production> --language grc diodorus_siculus.bibliotheca_historica`,
     the reference search, and a Greek line search that returns book 11 to 17
     lines (for example the lemmas of "Thermopylae" and "Leonidas").
- Backups to keep: each file replaced in steps 2 to 6, tagged
  `bak-diodorus-loeb-20261010`.

## 2026-10-08 Documentary reuse table built in dev; not yet installed on production
- What: `scripts/reuse/build_documents_reuse_table.py` is new (feat/reuse-documents),
  pairing every literary line against the documents collection (inscriptions,
  papyri) with the same word-triple containment logic as the literary reuse
  table. Writes `cache/reuse_pairs/<lang>_documents.db`, read by
  `backend/reuse_documents.py` and served by the existing `GET /api/reuse/line`
  and `GET /api/reuse/marks` routes (an additional `documents`/`n_documents`
  field, only under `TESSERAE_DOCUMENTS=1`, which is already set on
  production). See `docs/DECISIONS.md` for the formula-exclusion threshold
  and tiers.
- Built against the DEV checkout's own data (not copied from production;
  this checkout already carries `data/inverted_index/{la,grc}_documents_index.db`,
  `cache/lemmas/{la,grc}/` and `data/documents/metadata.db` from earlier
  documents-stage work), each inside `~/bin/tess-job` with a 12G cap:
  - Latin: `tess-job reuse-documents-la 12 venv/bin/python3
    scripts/reuse/build_documents_reuse_table.py --language la
    --documents-sidecar-root ~/tesserae-docs/stage3/texts_documents`
    (the sidecar override is a dev-only path -- see below). 453,830
    literary lines against 411,466 documentary lines; 5,414 pairs kept
    (280 strict, 5,134 possible/rare-single-ngram) out of 632,199
    candidates, 605,758 dropped as all-formula. Peak memory 11.0 GB
    (`systemd-run`'s own "memory peak" figure), wall time 9m8s (548s).
    Output `la_documents.db`, 1.14 MB.
  - Greek: same command with `--language grc`. Ran in 159s, peak well
    under the cap, but found 0 literary works to index: this DEV
    checkout's Greek lemma cache (`cache/lemmas/grc/`) holds only 262
    files against 1,269 `texts/grc/*.tess` sources, so `discover_corpus`
    skipped all of them as "missing cache" (0 kept, 901 missing, 368
    `.part.` files skipped) and the Greek output db has 0 pairs. This
    matches CLAUDE.md's own note that the Greek LITERARY reuse table
    build "never finished" here (2026-09-19, 11+ GB and incomplete) --
    the same underlying gap, not a bug in this script. Production's
    Greek lemma cache should be checked before rerunning there; if it is
    materially more complete than this checkout's 262 files, the Greek
    documentary table is worth rebuilding on production directly rather
    than copying this (empty) result.
  - The `--documents-sidecar-root` override points at this MACHINE's raw
    stage-3 tree (`~/tesserae-docs/stage3/texts_documents/<lang>/
    <bucket>.restored_words.jsonl`) because this dev checkout's own
    `data/documents/restored/` was never populated (only the indexes and
    metadata.db were copied here for the documents-search work). The
    script's actual DEFAULT for `--documents-sidecar-root` is
    `data/documents/restored/` -- the same directory and filenames
    `backend/documents.py`'s own sidecar reader uses and which
    PRODUCTION already has populated (264 files, see the "Documentary
    texts in the corpus-wide phrase search" entry below) -- so the
    production run below needs NO override at all.
- Samples checked against the Latin output (`cache/reuse_pairs/la_documents.db`):
  - Aeneid 1.1 ("Arma virumque cano, Troiae qui primus ab oris"): a
    verbatim Pompeii-region graffito, `edr:aEDR175604` ("Arma virumque
    cano, Troiae qui primus ab oris", shared 16, jaccard 1.0, strict),
    and a longer graffito quoting lines 1-3 together, `edh:HD054282`
    ("Arma virumque cano Troiae qui primus ab oris Italiam fato profugus
    Lavinaque venit", shared 16, jaccard 0.52, strict). KNOWN GAP: the
    Pompeii fullers' parody ("Fullones ululamque cano, non arma
    virumque", `merged:249860`) is NOT found -- same three words, reverse
    order, no shared trigram; see docs/DECISIONS.md.
  - Aeneid 2.1 ("Conticuere omnes intentique ora tenebant"): two Pompeii-
    region graffiti opening with "Conticuere omnes" (`edh:HD046219`,
    `edr:aEDR159670`), both tier 'possible' (shared=1) -- the opening
    two words alone, not enough to reach the strict thresholds.
  - Aeneid 1.192 ("nec prius absistit, quam septem ingentia victor"):
    verbatim in `edr:aEDR159691` (shared 13, jaccard 0.59, strict).
  - Aeneid 6.429 / 11.28 ("abstulit atra dies et funere mersit acerbo" --
    Vergil's own line repeated twice in the poem, of someone dying before
    their time): verbatim, restored-text-free, in a funerary inscription,
    `edr:aEDR166892 11` (shared 13, jaccard 1.0, strict) -- a real
    epitaph borrowing Vergil's line about an untimely death.
  - Vulgate Psalms 69.2 ("Deus in adiutorium meum intende, Domine ad
    adiuvandum me festina" -- "O God, make speed to save me") quoted
    VERBATIM in `edh:HD047192` (shared 22, jaccard 1.0, strict) -- the
    opening of the psalm set to stone.
- Production install (not yet done):
  1. Copy `cache/reuse_pairs/la_documents.db` and `grc_documents.db`
     (once both are built on production's own data) into production's
     `cache/reuse_pairs/` -- the SAME directory the literary `la.db`/
     `grc.db` already live in; the `_documents` suffix keeps them apart.
  2. Or, build directly on production (its documents indexes, lemma
     caches and `data/documents/restored/` are already in place, per the
     "Documentary texts..." and "Documents trial opened" entries below):
     from the production root, inside `~/bin/tess-job`,
     `tess-job reuse-documents-la 12 venv/bin/python3
     scripts/reuse/build_documents_reuse_table.py --language la`
     (no overrides needed -- every default path already matches
     production's own layout), then the same for `--language grc`.
  3. No env change and no reload needed: `TESSERAE_DOCUMENTS=1` is
     already set on production (see "Documents trial opened" below), and
     `backend/blueprints/reuse.py` checks for the documents db file at
     request time, not at process start.
  4. Verify: `GET /api/reuse/line?work=vergil.aeneid&ref=verg.%20aen.%201.1&language=la`
     carries a `documents` field with `edr:aEDR175604`; the existing
     reference tests in `tests/search_reference_tests.md` still pass
     (this change adds a field, it does not touch the literary response).

## 2026-10-08 Rumi, Masnavi opening: Nicholson's translation installed (about 15:50 EDT)
- What: `fa__rumi.masnavi.part.1.json` (built by the aligner in #703) copied
  into production's `data/translations/` and the app reloaded. It covers
  all 18 couplets of the opening of the Masnavi (the "Song of the Reed")
  one to one, from R. A. Nicholson's translation of Book I (1925/1926),
  public domain in the United States.
- Checks: the Reader's translation route returns the English for the first
  couplet with its attribution. Reference searches passed.

## 2026-10-08 Persian and Urdu editorial prose removed, an outage repaired, a translation and reuse tables added
- Khayyam (about 11:36): 142 lines removed from `khayyam.diwan` (refs .713
  to .854), a signed 1934 editor's introduction to a Khayyam edition that
  had been imported inside the poems. Removed with
  `scripts/corpus/drop_lines_from_work.py` (#690) from the text, the Persian
  index, the line vectors and 37 passage windows. The remaining lines keep
  their references, so the gap shows where the essay stood.
- Outage, about 11:50 to 12:35. The removal tool dropped the 37 windows from
  `ids.json` and `descriptions.jsonl` but not from `embeddings.npy`, so the
  passage index refused to load and Similar Passages and Theme Search failed
  for every language. Repaired by removing the same 37 rows from
  `embeddings.npy` by position in the pre-removal order (backup kept). The
  tool now keeps all four window stores in step and refuses to finish
  otherwise (#693). After any change to the passage index, the counts of
  `ids.json`, `embeddings.npy` and `descriptions.jsonl` are compared and one
  Similar Passages and one Theme Search request are made.
- Ghalib (about 13:14): two Wikisource footnotes removed from
  `ghalib.diwan_wikisource` (ghazal 62.9 and 131.22) with the repaired tool,
  eight windows with them. The three passage index files stayed at 530,917
  rows each. The description keyword index was rebuilt after each removal.
- Lemma caches: the removal deleted the cached analyses of both works.
  Urdu analysis needs a library that production does not carry, so both
  caches were rebuilt by running production's `scripts/batch_lemma_cache.py`
  under the development environment, writing into production's cache. The
  Persian and Urdu rare-bigram tables were then rebuilt
  (`scripts/corpus/rebuild_bigrams.py`).
- Names index rebuilt (`scripts/corpus/build_window_names.py`, 17 minutes,
  518,659 windows) and the connection map rebuilt
  (`scripts/build_connections_map.py`, finished 14:24).
- Translation: R. A. Nicholson's The Secrets of the Self (Macmillan, 1920,
  via Project Gutenberg), aligned to Iqbal's Asrar-e Khudi on 2026-09-07,
  was installed in `data/translations/` (all 872 references match the live
  text). The aligner is now on main (#695).
- Reuse tables for Persian and Urdu built for the first time
  (`scripts/reuse/build_reuse_table.py --language fa` and `ur`, 13:51):
  `fa.db` 247 MB, `ur.db` 11 MB. Asrar-e Khudi 19.20 returns 13 quotations,
  among them its source in Rumi's Masnavi (1.6).
- Backups: every file the removal tool changed was backed up beside it.
  Backups of the text files, lemma caches and the pre-repair
  `embeddings.npy` were moved out of the served folders.
- Checks: reference searches passed after each step. Similar Passages,
  Theme Search, Persian and Urdu line search, and the Reuse and Translation
  tabs were also checked on the live site.

## 2026-10-08 Documents trial opened (about 07:30 EDT)
- What: `TESSERAE_DOCUMENTS=1` added to the production environment after
  #683, so the documents option on the corpus-wide phrase search is
  available to anyone who opens the site with `?documents=1`. Without that,
  the option stays hidden. `TESSERAE_DOCUMENTS_CONNECTOR` is not set, so the
  connector's `line_search` still ignores the documents parameters.
- Backups: the environment file was copied before the change.
- Checks: reference searches passed. Live, a "both" search for "arma
  virumque cano" returned literary and document hits, and the same search
  without `collection` returned the literature-only response with no
  documents fields.

## 2026-10-08 Documentary texts in the corpus-wide phrase search (files installed about 02:30 EDT, switch off)
- What: PR for documents stage 3b-2 adds `backend/documents.py` and an
  optional `collection` parameter to `/api/line-search`, both inert unless
  `TESSERAE_DOCUMENTS=1` is set on the server. Installing it on production
  is a separate step from merging the code, listed here so it is not
  forgotten: copying the stage 3b-1 build's output (built dark, never
  previously copied anywhere near `/var/www`) into place, and setting the
  env line.
- Files to copy (read-only once in place, never written by the running
  app):
  - `la_documents_index.db` (266 MB) and `grc_documents_index.db` (775 MB)
    into production's `data/inverted_index/` (the SAME directory the
    literary `la_index.db`/`grc_index.db` already live in. The suffixed
    filename keeps them apart, and `backend/documents.py` refuses to
    open or write a literary-named file).
  - `metadata.db` (252 MB, stage 3a) into production's
    `data/documents/metadata.db` (new directory).
  - The restored-word sidecars (about 70 MB total, 264 files) into
    production's `data/documents/restored/<la|grc>/`, preserving the
    `<source>__<bucket>.restored_words.jsonl` filenames stage 3b-1's
    `write_document_tess.py` gave them.
  - `data/documents/formula_words_la.txt` and `_grc.txt` are already
    tracked in git (committed in stage 3b-1) and need no copy.
- Env: add `TESSERAE_DOCUMENTS=1` to production's environment and reload
  (`touch tesseraev6_flask.wsgi`). Until this line is set, every part of
  this PR is unreachable and the site's behaviour is unchanged.
- Verify after: the ten phrase searches in the stage 3b-2 spec
  (`collection=documents` and `collection=both`) against the live site,
  plus the existing reference tests in `tests/search_reference_tests.md`
  with `collection` omitted, to confirm the literary path is still exactly
  what it was before this entry.
- Applied, with the switch still off: both documents indexes copied into
  `data/inverted_index/` (byte-identical to the build), `metadata.db` into
  `data/documents/` (rebuilt the same night so every document shows its
  source's deposit licence, see the CHANGELOG), and the 264 restored-word
  files into `data/documents/restored/la` (160) and `grc` (104). The
  production environment does not set `TESSERAE_DOCUMENTS`, so the site
  reports documents as not enabled and every search is unchanged.
  Reference searches passed. A one-off process running the production code
  with the switch on returned document hits with edition and licence for
  "dis manibus", "bene merenti", "arma virumque cano" (Both) and χαίρειν,
  in 0.2 to 1.7 seconds each.

## 2026-10-08 Origo Gentis Romanae: the 2004 tertullian.org translation added (about 01:00 EDT)
- What: `data/translations/la__pseudo_aurelius_victor.origo_gentis_romanae.json`
  built in the development checkout, covering all 126 refs (the preface
  plus chapters I-XXIII) of
  `texts/la/pseudo_aurelius_victor.origo_gentis_romanae.tess`. This closes
  the gap the Aurelius Victor entry below left open, where the
  translation's terms were still being checked.
- Source: the collaborative translation (https://www.tertullian.org/fathers/origo_01_trans.htm),
  ed. Roger Pearse, 2004, from the Teubner Latin text. The page states "All material on this
  page is in the public domain - copy freely." Raw HTML was kept outside
  the repository.
- Method: `scripts/translations/align_origo.py`. The translation's own
  chapter (roman numeral) and bracketed section markers align 1:1 to the
  corpus's chapter.section refs in every case but three, where the
  corpus's single Latin Library line visibly carries two of the
  translation's numbered sections: 3.7 (translation sections [7]+[8]), 4.3
  (translation sections [3]+[4], the corpus having no 4.4 of its own), and
  5.3 (translation sections [3]+[4]). Each merge is listed by hand in the
  script. Three places in 126 refs is too few to trust to an automatic
  rule. The preface ref (`pr.1`) maps to the page's opening dedication
  paragraph, read past the page's own title and navigation links.
- Checks: coverage 1.0 (126 of 126 refs). Proper-name survival 0.9915 on 118
  of the 126 pairs the check could sample, above the 0.70 threshold used
  elsewhere for "high" confidence. No footnote or apparatus text and no
  leftover HTML markup in any of the 126 stored units, checked against
  every unit. `backend.translations.for_passage` called directly against
  the built file (no server needed) returns the right English for the
  preface, an ordinary ref (1.1), all three merged refs, and the last ref
  (23.6), and reports unavailable for a ref outside the work.
  `tests/test_translations_unit_sources.py` and
  `tests/test_translation_route_alias.py` (12 tests, generic to the
  translation module) pass unchanged.
- Licence: public domain. Attribution "collaborative translation, ed.
  Roger Pearse (2004)" is stored in the file and shown with every display.
- Production steps (not yet run): copy
  `data/translations/la__pseudo_aurelius_victor.origo_gentis_romanae.json`
  from this operation into production's `data/translations/` (this
  directory is not tracked in git). `touch tesseraev6_flask.wsgi` so the
  three Apache workers rebuild their per-work file index and pick up the
  new file (the index is built once per worker and otherwise would not
  see it). No inverted-index, lemma-cache or passage-index rebuild is
  needed: the file only adds an English rendering for a work already
  indexed. Verify afterward with a request to the translation endpoint
  for `pseudo_aurelius_victor.origo_gentis_romanae` ref `ps-vict. orig.
  1.1`, and that the Reader's Translation tab shows it for that work.
- Applied: the built file copied into production `data/translations/`
  and the app reloaded. The Reader's translation route returns the English
  for ref 1.1 with its attribution and public-domain statement. Reference
  searches passed.

## 2026-10-08 Scholarship sources installed on the live site (about 23:10 EDT)
- What: the Reader's Scholarship tab (opt-in, `?scholarship=1`) went live
  with Servius only. These were installed beside it, outside git:
  - the remaining commentary catalogue, 389 files added to
    `data/commentaries/` for 393 in all (the Perseus open commentaries on
    Latin and Greek works under CC BY-SA, the Sefaria Tanakh commentators
    filtered to texts whose stated licence permits reuse, Matthew Henry from
    CCEL in the public domain, and public-domain English editions read from
    scans for Milton, Shakespeare, Spenser, Keats, Wordsworth and Vergil).
  - the offline citation index (`data/citation_index/citations.db`, 25 MB),
    article-to-passage citations extracted from the pre-1923 JSTOR Early
    Journal Content released for free reuse, covering 24 classical, biblical
    and English journals, with 82.5% precision on a 40-citation hand-checked
    sample.
  - the citation abbreviation table (`data/citations/abbreviations.json`,
    GPL-3.0, used on the server and not redistributed).
  - two keys in the production environment, for book-page search (Google
    Books) and open full text (CORE). The keys are not recorded here.
- Every commentary file's work id was checked against the live texts first.
  All match, and scripture uses one key across Bible versions.
- Scripts: none (files copied with `rsync --ignore-existing`, so the
  Servius files tracked in git were left untouched).
- Backups: the production environment file was copied before the keys were
  added. The data was additive, so no other backup was needed.
- Checks: reference test passed after reload. Live lookups returned
  commentators for the Aeneid, Iliad and Paradise Lost, citation-index hits
  for Aeneid 4.1, book pages, and full-text results. The credits list
  (`/api/scholarship/sources`) answers in under a second.
- Note: the full-text key expires on 14 October 2026 and must be renewed.

## 2026-10-08 Two works transmitted with Aurelius Victor added (23:00 to 00:17 EDT)
- What: `pseudo_aurelius_victor.de_viris_illustribus` (86 chapters, 519
  lines) and `pseudo_aurelius_victor.origo_gentis_romanae` (preface and 23
  chapters, 126 lines), from The Latin Library (#674), carried through every
  store the site reads.
- Steps, each under `~/bin/tess-job`:
  - lemma caches (`scripts/batch_lemma_cache.py la`, only the two new files
    computed).
  - Latin index extended on a copy (`scripts/corpus/add_texts_to_index.py
    --add`, text ids 1795 and 1796, 8,741 and 3,961 postings, 1,656 texts,
    933,463 lines, lemma_doc_freq rebuilt, integrity ok) and swapped in.
  - rare-bigram table rebuilt (`scripts/corpus/rebuild_bigrams.py la`, 87 s).
  - 148 passage windows built (`scripts/corpus/build_batch_windows.py
    --upsert-db`), described by Qwen 3.8 27B on the university's AI gateway
    with thinking off (stamp `qwen38-bullsai-20261008`, 148 of 148 in 1.4
    minutes), appended with `scripts/corpus/apply_passage_rows.py --mode
    append` (530,962 windows, ids, vectors and descriptions in step), and the
    description keyword index rebuilt (`scripts/build_desc_fts.py`, 37 s).
  - line vectors for both works encoded on the server's processor with
    bowphs/SPhilBerta, raw as in the existing files (519 and 126 rows, mean
    norms 5.8 and 6.0).
  - connection map rebuilt (`scripts/build_connections_map.py`, 49 minutes,
    peak 7.3 GB, up from 4.4 GB on 7 October as the window count grew.
    An 8 GB cap now leaves too little headroom, so use 10 GB).
- Dates: `backend/author_dates.json` gains a Latin entry for
  `pseudo_aurelius_victor` (Late Antique, 4th century CE) so the corpus
  browser shows an era.
- Backups: `la_index.db.bak-victor-minor-20261008`,
  `window_texts.db.bak-victor-minor-20261008`,
  `desc_fts.sqlite.bak-victor-minor-20261008`, and the passage index files'
  `.bak-victor-minor-20261008` copies made by the append script.
- Checks: reference searches passed after each reload. The coverage check
  (`scripts/corpus/verify_text_coverage.py`) passes for both works in every
  store except the browser era, which this change supplies.
- Note: no public-domain English translation was found for De viris
  illustribus. One exists online for the Origo and its terms are being
  checked.

## 2026-10-07 Connection map rebuilt with Persian and Urdu (15:25 to 16:12 EDT)
- `scripts/build_connections_map.py` with the language list of #658 (la, grc, en,
  cop, he, fa, ur): 371,354 fine windows in 1,838 works, 46.2 min, peak 7.3 GB
  under a 10 GB cap. The coverage checker then reports every Persian and Urdu text
  present in every store (28 and 18 texts, nothing missing), including the Sources
  credits added in #660.

## 2026-10-07 Names index extended to Hebrew, Coptic, Persian and Urdu (15:37 to 15:59 EDT)
- Built with `scripts/corpus/build_window_names.py` (#659) to
  `data/passage_index/window_names.db.new` on production (21 min, peak 1.9 GB):
  518,556 windows, 2,254,993 window-name pairs. Latin, Greek and English rows
  checked identical to the live file (SHA-256 over sorted rows).
- The build wrote one window total for all languages, which would have made
  every Latin name look twice as rare. The meta table was set by hand to the
  per-group totals the fixed builder now writes (windows 265,214 for la/grc/en,
  windows_he 5,372, windows_cop 13,200, windows_fa and windows_ur 234,770) before
  the swap at 15:59 (backup `window_names.db.bak-other-scripts-20261007`).
- After reload: a Genesis window naming Abraham and a Hafez window naming Joseph
  return their "same people and places" groups.

## 2026-10-07 Backups pruned; weekly pruning scheduled (15:08 to 15:16 EDT)
- `scripts/prune_backups.py --keep 1 --keep-days 3 --apply` (the rule of #466):
  64 copies, 79.8 GB deleted; 128 copies, 28.7 GB kept. Superseded snapshots in
  the home backup folder removed by hand (about 35 GB: a test copy of
  2026-09-20, the June index snapshots, an old staged passage index, two
  frequency-table builds, three old vector copies). Disk free 175 GB to 289 GB.
- A weekly user timer now runs the rule every Sunday at 03:30, keeping the
  newest copy of each file and anything under seven days old
  (`~/.config/systemd/user/tess-prune-backups.timer`, log under
  `~/tesserae-backups/jobs/prune/`). The rule had only ever been run by hand.

## 2026-10-07 Persian work iqbal_lahori.diwan renamed iqbal.diwan in every store (14:21 to 14:44 EDT)
- What: Iqbal's Ganjoor collection was filed under the author prefix
  `iqbal_lahori`, so lists and charts showed "Iqbal Lahori" beside "Iqbal" for
  his seven other Persian works. The repository side merged in #655; the
  stores were renamed with `scripts/corpus/rename_work.py --root
  /var/www/tesseraev6_flask --language fa --old iqbal_lahori.diwan --new
  iqbal.diwan --apply` (dry run first). Note the collection overlaps the seven
  works: 4,513 of its 16,274 half-lines appear word for word in them.
- Renamed by the script: texts/fa (16,274 line tags), fa_index.db (texts row,
  16,274 lines, 100,347 postings), the lemma cache (new content-hashed name),
  ids.json and descriptions.jsonl (3,797 windows). Backups
  `*.bak-rename-20261007-*`; the old text and lemma cache files moved to
  `~/tesserae-backups/rename_iqbal_2026-10-07/`.
- The script stopped at window_texts.db with "database is locked": the web
  workers hold it open. The same update was then made on a copy (3,797 windows,
  16,274 lines, quick_check ok) and swapped in at 14:25 (backup
  `window_texts.db.bak-rename-20261007-142330`). The script now works on a copy
  and swaps it in. The vector files were renamed by hand (meta paths and line
  refs rewritten).
- Rebuilt afterwards: keyword index (530,814 rows), Persian phrase table
  (1,420,609 keys), connection map (14.3 min, peak 4.4 GB). App reloaded; every
  reference search passed; the Persian text list shows all eight Persian works
  under "Iqbal", and the corpus chart counts him once (251 lines for "man ast").

## 2026-10-07 Persian and Urdu served on production; preview server closed (08:05 to 08:15 EDT)
- What: production's `.env` gains `TESSERAE_LANGUAGES=la,grc,en,cop,he,fa,ur,it,gmh,fro`,
  which registers the Persian and Urdu handlers, adds their tabs after Hebrew
  and adds the Persian against Urdu pair (backend/served_languages.py). Arabic
  is left out, so it stays unserved and its passage windows stay held. The
  stores were copied in on 2026-10-05 and the windows appended on 2026-10-06.
  Backup of the old file: `~/tesserae-backups/env.prod.bak-20261007-0805`.
  To undo, remove the line and reload.
- Checked afterwards: `/api/languages` lists la, grc, en, cop, he, fa, ur with
  the pairs grc-la, la-en, grc-en, cop-grc, he-grc, he-la, fa-ur. 28 Persian
  and 18 Urdu texts are listed. A Hafez against Saadi search, a Khayyam
  against Hafez combined search, a Persian against Urdu search (Iqbal, 1,300
  parallels) and a Persian Theme Search all return results. Every reference
  search passed. The web app has no Stanza model, so Persian and Urdu typed
  queries use the normalised word forms, as the preview did.
- The preview server and its tunnel were stopped, which frees its 20 GB
  memory allowance for jobs.
- Persian and Urdu phrase tables rebuilt with `scripts/corpus/rebuild_bigrams.py`
  (Persian 34 s, peak 2.1 GB, 1,420,609 keys, unchanged; Urdu 3 s, 176,629
  keys). Backups `*.pre-rebuild-20261007-*.bak`.

## 2026-10-07 Duplicate Augustine fragment removed from every store (08:17 to 08:43 EDT)
- What: `unknown.corpus_scriptorum_ecclesiasticorum_latin`, 20 lines of
  Augustine, De natura et gratia 32 to 46 from the CSEL edition, which the
  corpus holds whole (#645). Removed with
  `scripts/corpus/remove_restricted_text.py unknown.corpus_scriptorum_ecclesiasticorum_latin --apply`,
  its first run on real data (3 min, peak 3.1 GB): the text file, its lemma
  cache, 20 lines and 1 text from `la_index.db` (backup
  `la_index.db.bak-removed-20261007-20261007-081825`), 3 passage windows from
  ids.json, embeddings.npy and descriptions.jsonl, and 23 rows from
  window_texts.db, each backed up beside itself as `*.bak-removed-20261007-*`.
  The passage index went from 530,817 to 530,814 windows, with ids and vector
  rows checked in step afterwards.
- The script missed the lemma cache's content-hashed copy
  (`<work>-<hash>.json`), which was moved by hand. The finder is fixed in #647.
  The file's backups, that copy and its vector file were moved to
  `~/tesserae-backups/retired_duplicates_2026-10-07/`.
- Rebuilt afterwards: keyword index (`scripts/build_desc_fts.py`, 530,814
  rows, 31 s, backup `desc_fts.sqlite.bak-removed-20261007`); Latin
  lemma_doc_freq (`scripts/corpus/rebuild_docfreq.py --language la --apply`,
  1,654 files, 752 works, backup `la_index.db.bak-docfreq-20261007-082418`);
  names index (`scripts/corpus/build_window_names.py`, 265,214 windows, 19 min,
  peak 4.6 GB, backup `window_names.db.bak-removed-20261007`); connection map
  (`scripts/build_connections_map.py`, finished 08:38, peak 4.5 GB).
- After: app reloaded, every reference search passed, the fragment is gone from
  the Latin text list, and a Latin Theme Search returns results.

## 2026-10-07 Morning rebuilds after the night window
- Latin and Greek phrase tables rebuilt with the corrected builder (#639,
  counts as it reads and reads the lemma cache): Latin at 06:44 (165 MB), now
  with the Vegio supplement; Greek at 06:46 (412 MB), now with the work it
  lacked. Both under 4 GB.
- Names index for the two-group Similar Passages installed at 07:01
  (`data/passage_index/window_names.db`, built by
  `scripts/corpus/build_window_names.py`).
- The Paschasius Radbertus book file, converted from carriage-return line
  endings in #641, has a fresh lemma cache.

## 2026-10-07 Night window: Vegio relabel moved through the stores; connection map rebuilt
- Window: the preview server was stopped 02:00 to 02:56 (tunnel kept) so the
  jobs below had memory; every step under `~/bin/tess-job`.
- Vegio relabel (#636, #637: `polignac.imitatio` is Vegio's Aeneid supplement,
  now `maffeo_veggio.supplementum`, lines renumbered): lemma cache built;
  Latin index: the scheduled add pointed at the wrong cache folder and added
  nothing, then `drop_stale_index_entries.py` removed the old file (backup
  `la_index.db.bak-stale-20261007-0201`); at 02:05 the supplement was added to
  a copy with the correct `--cache-dir cache/lemmas` (1,655 texts, 932,838
  lines, lemma_doc_freq rebuilt, quick_check ok) and swapped in (backup
  `la_index.db.bak-vegiofix-20261007`). Vectors renamed (716 rows, refs from
  the renumbered file). Passage index: 166 windows renamed in ids.json,
  descriptions.jsonl and window_texts.db (backups `.bak-vegio-20261007`); 159
  had their references re-located by matching their first and last lines in
  the renumbered file, 7 kept a mechanically rewritten reference (to check);
  the Reader's lines for the work replaced (716). Keyword index rebuilt.
- Latin rare-phrase table rebuilt at 02:05, before the corrected index swap, so
  it lacks the supplement: rerun at the next window.
- Greek rare-phrase table: rebuild killed at its 12 GB cap after 9 minutes (it
  took 88 s on 2026-10-03); the live table is unchanged and still lacks one
  work. Cause under investigation.
- Connection map rebuilt (`scripts/build_connections_map.py`, 19.1 min, peak
  4.4 GB, 708 MB), now including the works added since 30 September; old cache
  removed.
- After: app reloaded, every reference search passed, preview restarted on its
  address; the coverage check passes for the supplement except the Latin
  rare-phrase table.

## 2026-10-06 Persian, Urdu and Arabic passage windows appended to the passage index (port stage 4b)
- What: 19,978 passage windows the production index lacked (Urdu 12,609, Arabic
  5,759, Persian 1,610; production already held 218,401 Persian, 2,150 Urdu and 32
  Arabic from August) appended at 19:16 EDT: `ids.json`, `embeddings.npy` and
  `descriptions.jsonl` grew in lockstep from 510,839 to 530,817; their wording went
  into `window_texts.db` (19,978 rows) and the Reader's `lines` table gained 86,381
  lines for 164 works that had none. Backups `<file>.bak-mlw-20261006` of all four
  files. Keyword index rebuilt with `scripts/build_desc_fts.py` (530,817 rows, 33 s)
  at 20:23, backup `desc_fts.sqlite.bak-mlw-20261006`; app reloaded each time.
- Descriptions: GLM 5.3 Flash on the campus gateway, the describer of the 3 October
  corpus re-description, 0 failures (the last 10,797 in 41 minutes once the gateway's
  team budget was set to reset daily).
- Vectors: multilingual-e5-large on the campus GPU (job mlwin-1006, 39 s), over the
  same text the index encodes (`"query: " + blob_for(desc)`, checked identical to the
  3 October job's input on 200 windows), results via the upload route (#596).
- Arabic held: Arabic is not yet graded, so #626 keeps Arabic windows out of Theme
  Search and Similar Passages on this server; they stay indexed.
- Checks: lockstep asserted before and after; every reference search passed after
  each reload; an All-languages Theme Search returns Persian and Urdu windows and no
  Arabic.
- Service change the same evening: the query encoder and Reader services were
  restarted to clear 2 GB of idle swap and set to `MemorySwapMax=0`.

## 2026-10-06 Semantic vectors computed for every Latin, Greek and English work that lacked them; defective vector files replaced
- What: before today 443 of 748 Latin whole works, 284 of 845 Greek and all 41
  English had no stored vectors, so the semantic channel returned nothing for any
  comparison touching them (the web app carries no model by design, and the log
  recorded that the Latin semantic model was unavailable). Two GPU
  jobs on the campus cluster (BullsAI, project tesserae, one B200) encoded every
  line of those works with the models the site uses (bowphs/SPhilBerta for Latin
  and Greek, all-MiniLM-L6-v2 for English), raw vectors as in the existing files.
  Job 1 (semfill-1006, 97 s): 768 works, 586,862 lines; 767 whole-work files copied
  into production `backend/embeddings/<lang>/` at 15:31 to 15:36 EDT
  (sappho.fragments held back, having no lemma cache to verify against), and 1,003
  part files derived from their whole works by reference. Job 2 (semfill2-1006,
  22 s): 29 whole works re-encoded whose OLD vector files held the wrong number of
  rows for their text (augustine.de_trinitate had 1 row for 624 lines,
  macrobius.saturnalia 1 for 2,072, seneca.quaestiones_naturales 4 for 897,
  couplet_et_alii.confucius_sinarum_philosophus 5 for 255; alcuin, claudian,
  persius, the Achilleid and six Greek works off by one to six), replaced at 15:49
  with 152 part files re-derived; and seven parts of petrus_riga.aurora (no whole
  file) re-encoded on the server's processor (6,959 lines, 24 s, about 400 lines a
  second). Old files kept in
  `~/tesserae-backups/jobs/semantic_fill_2026-10-06/replaced_old/`.
- Inputs: line text read from the .tess files (verified identical to the cached
  search units, by reference and wording); job folders
  `public_data/jobs/semantic-fill-20261006/` and `semantic-fill2-20261006/`
  (blobs.jsonl.gz, works.json, encode_fill.py); results via the upload route (#596).
- Checks: after the operation every vector file with a text behind it has one row
  per text line, except three texts with a malformed line
  (paschasius_radbertus.epitaphium_arsenii.part.2, ambrose.epistulae_variae,
  augustine.contra_faustum), where the row count equals the cached unit count the
  search uses. Vector norms 4.7 to 6.4 against 5.2 for the existing Latin files. A
  fresh live comparison (Curtius 5 against Justin) logged "Using pre-computed
  embeddings" and 21 of its top 30 parallels carry the semantic channel.
- Left as found: 148 old vector files whose text no longer exists under that name
  (renamed or retired works); harmless, to be archived in a later pass.
- Service: the channel reads a work's file by path, so no reload was needed. The
  English embeddings folder was owned by the web-app user and empty; replaced by a
  group-writable one. The embeddings manifest (admin statistics only) was not
  rebuilt on production. Vector files are not tracked in git.
- Counts after: Latin 1,804 vector files, Greek 1,237, English 93.

## 2026-10-06 Quintus Curtius: J. C. Rolfe's 1946 Loeb translation added (section-exact)
- What: `data/translations/la__curtius_rufus.historiae_alexandri_magni.json` created on
  production at 13:27 EDT, covering all 2,621 sections of books 3-10 of
  `texts/la/curtius_rufus.historiae_alexandri_magni.tess` (the whole-work file also
  serves the eight part files). 2,529 refs (96.5%) map to section-level units, 92 to
  four whole-chapter units (3.1, 4.1, 4.8, 5.11), where the OCR's marginal section
  numbers could not be recovered. 2,514 units stored.
- Source: J. C. Rolfe, Quintus Curtius, History of Alexander, 2 vols, Loeb Classical
  Library, Harvard 1946. Rights basis: HathiTrust rights "pd, Full view" (public domain
  in the United States) for the Michigan copies mdp.39015008158415 (v.1) and
  mdp.39015008158407 (v.2). Text: OCR of the same volumes from the archive.org item
  quintus.-curtius.-rufus.-history.of.-alexander.-loeb.-one-vol-version_202511
  (files Vol.1_djvu.txt, Vol.2_djvu.txt); raw copies kept outside the repository.
- Method: `scripts/translations/align_curtius.py`. English pages separated from Latin
  by function-word share; footnotes, apparatus, each book's synopsis and the index
  cut; chapter starts by roman numeral; section starts by the marginal integers,
  chosen as the longest increasing subsequence per chapter, a chapter accepted at
  section level when at least 70% of its markers were found and missing sections
  merged into the preceding one; validated per book against the corpus's chapter
  counts. A final pass removed running heads, stray section numbers, footnote marks
  and trailing OCR noise from the unit text without changing the mapping.
- Checks: coverage 1.0; proper-name survival 0.737 on 300 sampled units (the Loeb
  range in this corpus is 0.74-0.81); units with two or more unambiguous Latin words
  0.48%; footnote or apparatus traces 0.16%; 19 units keep a run of OCR garble.
- Licence: public domain in the United States; attribution "J. C. Rolfe (1946)" is
  stored in the file and shown with every display.
- Service: the per-work file index is built once per worker, so the Reader shows the
  new translation after the next reload.

## 2026-10-05 Persian, Urdu and Arabic stores copied into production, unserved (run 06:18 to 06:20 EDT)

### What and why
- The code for the three development languages reached main in #606,
  #608, #611 and #613 and registers only when TESSERAE_LANGUAGES names a
  language. This operation put the data beside it so that opening a
  language later is a setting and a reload. Nothing is served: the
  languages endpoint lists la, grc, en, cop and he as before.

### Steps
- From the development checkout, by rsync into the production tree:
  `texts/fa` (28 files), `texts/ur` (18), `texts/ar` (149, the whole-Qur'an
  file among them because the Arabic index holds it); the inverted indexes
  `fa_index.db` (848 MB), `ur_index.db` (71 MB), `ar_index.db` (62 MB); the
  lemma caches `cache/lemmas/{fa,ur,ar}` (1.5 GB, 106 MB, 121 MB); the bigram
  tables `cache/bigrams/{fa,ur,ar}_bigrams.json`; the frequency tables
  `cache/frequencies/{fa,ur,ar}.json`; and the line embeddings for the
  semantic channel `backend/embeddings/{fa,ur,ar}` (3.7 GB, 233 MB, 104 MB).
  Group set to the application's group, read permission given.
- No reload (nothing reads these files while the languages are unserved).

### Checked afterwards
- `/api/languages` on the live site unchanged. Disk free after: 276 GB.
- Still to come before the languages open: the passage windows for the
  three languages appended to the passage index with their vectors (the
  describing is 7,474 of 19,978 done and waits on the gateway's team
  budget), and a licence check of the text sources, the whole-Qur'an file
  included.

## 2026-10-04 Herodian On Enclitics line tags: the derived stores retagged (run 12:45 to 12:51 EDT)

### What and why
- #603 retagged the 26 lines of `texts/grc/aelius_herodianus.on_enclitics.tess`
  from a CTS-URN form to the plain `<aelius_herodianus.on_enclitics N>`,
  the last Greek file found carrying URN tags (the Septuagint's 21 were done
  on 2 October). Text unchanged. The reference string lives in several
  stores, so each followed. Production pulled to b5a8cf3.

### Steps
- Greek lemma cache: `scripts/batch_lemma_cache.py grc` rebuilt the one
  changed file by content hash.
- Index: `grc_index.db` copied, the file replaced in the copy with
  `scripts/corpus/add_texts_to_index.py --replace`, `lemma_doc_freq`
  rebuilt (221,709 lemmas), integrity ok, swapped in, backup
  `grc_index.db.bak-herodianrefs-20261004-1245`. After: 1,268 texts,
  478,011 lines, 10,860,180 postings. The file's refs now read
  `aelius_herodianus.on_enclitics 1` and so on, and no URN ref remains.
- Stored references: `scripts/corpus/retag_septuagint_refs.py --work herodian
  --apply` rewrote 34 values in `window_texts.db`, 8 in
  `descriptions.jsonl` and 8 in each of the two connections-map caches,
  each store backed up first.
- `touch tesseraev6_flask.wsgi` at 12:51, and `scripts/reference_search_check.py` passed.

### Checked afterwards
- No URN reference remains in the text, the index, the passage index or
  the map caches.
- A first run at 12:38 stopped at the integrity assertion on the index
  copy before any swap, with the lemma cache already rebuilt; the second
  run, from a fresh copy, passed the same check and completed. The
  Tessa change #602 was pulled and reloaded at 12:51 right after.

## 2026-10-04 Passage descriptions: the windows described after the swap (run 08:12 to 08:18 EDT)

### What and why
- 255 windows had kept their August description at the 3 October swap
  after three gateway failures each. Two more tries this morning (16 in
  flight, the second with a token budget of 8,000 against 3,000) described
  175 of them; 80 keep the August text, all ordinary passages (140 of the
  168 that failed the morning sweep were Latin), on which the model
  returned no parseable description in every try.

### Steps
- `scripts/corpus/apply_passage_rows.py --mode replace` on the live index
  with the 175 records: vectors from the local encoder, rows replaced in
  place, `descriptions.jsonl` rewritten (510,664 kept + 175 replaced =
  510,839), backups `*.bak-glm-delta-20261004-0812`. Index after: 510,839
  ids, 510,839 vectors, 510,839 description rows.
- `scripts/build_desc_fts.py` rebuilt the word index (510,839 rows, 32 s).
- `touch tesseraev6_flask.wsgi` at 08:18, and `scripts/reference_search_check.py` passed.

## 2026-10-03 Passage descriptions replaced by the whole-corpus re-description (swap run 23:30 to 23:35 EDT)

### What and why
- Every passage window's description was rewritten by a hosted open model
  (GLM 5.3 Flash on the campus gateway) from the window's own text, after
  a blind head-to-head on 2026-09-30 in which it beat the August
  descriptions 96 to 4 and put no invented proper name into 300
  descriptions. The run went from 2026-09-30 14:55 to 2026-10-03 14:52
  plus two sweeps. 510,584 of 510,839 windows carry the new text; 255
  keep the August text until a small second operation.
- Retrieval measured before the swap on the sixteen-query benchmark
  (9,485 windows described in both sets, every top-ten pair judged):
  precision at ten 0.381 with the August descriptions, 0.403 with the
  new, 0.400 to 0.442 on the twelve development queries, 0.325 to 0.287
  on the four held-out (forty pairs). Level or slightly better; the gain
  of the rewrite is in the text readers see.

### Steps
- Vectors: the new descriptions encoded with the production encoder
  (intfloat/multilingual-e5-large, the index's own blob text and prefix)
  on one campus GPU in 448 seconds, returned through `/api/jobs/upload`
  in eleven parts whose SHA-256 each matched the job's report, and
  checked against the local encoder (cosine 1.00000 on a sample). The
  612 windows described after that run were encoded locally.
- A working copy of the index received the rows in place
  (`apply_passage_vectors.py` in the job folder, then
  `scripts/corpus/apply_passage_rows.py --mode replace` for the 612), ids
  unchanged: 510,839 ids, 510,839 vectors.
- `descriptions.jsonl` cleaned to exactly one record per indexed id
  (production's file had held 229 duplicated ids and 14 records for
  windows no longer indexed; the application read the last record per
  id, so nothing had shown).
- `scripts/build_desc_fts.py --source <clean file>` built the word index
  (510,839 descriptions, 29 s, 634 MB) before anything moved.
- Backups `descriptions.jsonl.bak-glm-20261003-2330`,
  `embeddings.npy.bak-glm-20261003-2330`,
  `desc_fts.sqlite.bak-glm-20261003-2330`; then the three files copied in
  by rename swaps at 23:31:42, `touch tesseraev6_flask.wsgi`, and
  `scripts/reference_search_check.py` passed.

### Checked afterwards
- Theme Search on the live site answers with the new text: "a storm
  scatters the fleet at sea" returns Silius Italicus, Punica 17.247 ("A
  violent sea-storm, with warring winds, thunder, lightning, and darkness,
  overwhelms the fleet and shatters the mast over the helmsman's head")
  and Livy 37.12.12.
- A first attempt at 23:16 was stopped in its checking step before
  touching anything: the check rebuilt a set of all ids for every line
  and would have taken hours. Corrected and rerun.

## 2026-10-03 Full Greek rebuild for the breathing and accent fix (run 10:23 to 11:30 EDT)

### What and why
- #590 (issue #580) moved 208,992 breathing and accent marks in 774 Greek
  files onto the vowel, or rho, they belong to, and composed the
  precomposed letter (` ̔Ηροδότου` became `Ἡροδότου`). The stored form had
  tokenized as a stray mark plus a bare capital, so those words carried the
  wrong lemma or none. Every Greek derived store had to follow. Production
  pulled to d30a559.

### Steps
- Greek lemma caches: `scripts/batch_lemma_cache.py grc --force`, 1,268
  files, 97 seconds, peak 0.5 GB.
- Index: `scripts/build_inverted_index.py --language grc --force` in a
  worktree at the same commit, 56 minutes, peak 1.7 GB. After: 1,268
  texts, 478,011 lines, 10,860,180 postings, 221,708 lemmas, with
  `lemma_doc_freq` rebuilt. Integrity ok, swapped in, with the backup
  `grc_index.db.bak-greek-20261003-1023`.
- Greek bigram table rebuilt (900 documents, 13,685,991 bigrams, 88
  seconds) and the Greek frequency table (221,708 lemmas). No cached Greek
  search needed removing.
- Stored passage wording: `scripts/corpus/refresh_window_text.py` rewrote
  the text of 21,395 passage windows and 65,807 lines in `window_texts.db`
  for the 459 works whose files changed, so the Reader, Similar Passages
  and Theme Search show the corrected letters.
- `touch tesseraev6_flask.wsgi` at 11:30, and `scripts/reference_search_check.py`
  passed.

### Checked afterwards
- `scripts/corpus/scan_greek_capital_marks.py` over the production texts:
  1,268 files, 0 occurrences remaining.
- The 1,347 marks on consonants or spaces (part B of the issue) are not
  touched by this operation. They are listed in
  `data/proposals/greek_stray_marks_2026-10-03.csv` for a reader to settle
  by hand.

## 2026-10-02 Septuagint line tags: 21 files retagged, index rows, passage references and map caches rewritten (run 10:24 to 10:30 EDT)

### What and why
- #578 (issue #564) retagged the 21 Septuagint files that still carried
  CTS-URN line tags to the plain form the other 34 use
  (`<septuaginta.genesis 1.1>`), 13,729 lines, text unchanged. The
  reference string is stored in several places, so each had to follow.
  Production pulled to e267a63.

### Steps
- Greek lemma caches: `scripts/batch_lemma_cache.py grc` rebuilt the 21
  changed files by content hash (2 seconds).
- Index: `grc_index.db` copied, the 21 files replaced in the copy with
  `scripts/corpus/add_texts_to_index.py --replace`, `lemma_doc_freq`
  rebuilt (223,784 lemmas), integrity ok, swapped in, with the backup
  `grc_index.db.bak-lxxrefs-20261002-1024`. After: 1,268 texts, 478,011
  lines, 10,862,058 postings. Genesis line refs now read
  `septuaginta.genesis 1.1`.
- Stored references: `scripts/corpus/retag_septuagint_refs.py --apply`
  rewrote 20,098 values in `window_texts.db` (13,730 line refs, 3,184
  windows' start and end), 6,368 in `descriptions.jsonl` and 4,550 in each
  of the two connections-map caches, each store backed up first with the
  suffix `.bak-lxxrefs-20261002-102838`.
- `touch tesseraev6_flask.wsgi` at 10:29:42, and `scripts/reference_search_check.py`
  passed.

### Checked afterwards
- No Septuagint reference in the old form remains in the texts, the index,
  the passage index or the map caches. The scan found one other text with
  URN line tags, `aelius_herodianus.on_enclitics.tess` (26 lines), which is
  not part of this change and is listed as open work.
- The first two runs stopped before touching anything: the replace step
  wants bare filenames and the lemma cache root. The script was corrected
  and rerun.

## 2026-10-01 Full Greek rebuild for the classical lemma table (run 19:46 to 20:34 EDT)

### What and why
- #571 added the classical lemma table built from the GLAUx treebank corpus,
  loaded after the treebank and Koine tables and filling only what both
  lack. Production pulled to 4610086. The forms neither earlier table
  covered were 14.4% of all Greek tokens, and the new table resolves 90% of
  them (measured read-only before the build, per work).

### Steps
- Built in a fresh worktree of the same commit (`~/tesserae-grcbuild`),
  inside a 12 GB job scope, with the same script as the morning rebuild
  minus the stored-wording step. Lemma caches: `scripts/batch_lemma_cache.py
  grc --force`, 1,270 files. Index: `scripts/build_inverted_index.py
  --language grc --force`, 41 minutes, peak 1.7 GB. The copy verified
  (integrity ok) and swapped in. Backup `grc_index.db.bak-greek-20261001-1946`.
  Production lemma caches moved aside to `cache/lemmas/grc.bak-greek-20261001-1946/`
  and the new ones copied in. Greek frequency table recomputed (221,708
  lemmas), bigram table rebuilt (`scripts/corpus/rebuild_bigrams.py grc`,
  2,428,434 distinct bigrams, 85 seconds). App reloaded 20:34:06, and
  `scripts/reference_search_check.py` passed.
- Before: 1,268 texts, 478,011 lines, 11,063,906 postings, 464,732 lemmas.
  After: 1,268 texts, 478,011 lines, 10,860,180 postings, 221,708 lemmas.
  The fall in distinct lemmas is the unresolved surface forms, each of
  which had counted as a lemma of its own, folding into dictionary forms:
  ἐφάνησαν has no postings of its own now and φαίνω has 10,890.

### Checked afterwards
- Reference searches pass. The per-work unresolved share was not remeasured
  tonight. The read-only measurement before the build is in the #571
  record. The 6,136 forms where the new table disagrees with an existing
  one were not applied and remain for review.

## 2026-10-01 Full Greek rebuild for the tokenizer fix, the κα correction and the Koine lemma table (run 11:52 to 12:52 EDT)

### What and why
- Three merges changed what the Greek index holds: #558 (the tokenizer no
  longer keeps the ano teleia and the spacing breathings on a word), #559
  (262 bare κα corrected to καὶ in 11 Septuagint books) and #560 (the Koine
  lemma table for forms the treebank table lacks). Production pulled to
  be6ccc4. One rebuild served all three.

### Steps
- Built in a fresh worktree of the same commit (`~/tesserae-grcbuild`) so
  the live index was never removed mid-build, inside a 12 GB job scope.
  Lemma caches: `scripts/batch_lemma_cache.py grc --force`, 1,268 files in
  100 seconds, peak 0.4 GB. Index: `scripts/build_inverted_index.py
  --language grc --force`, 52 minutes, peak 1.6 GB. The copy verified
  (integrity ok) and swapped in; backup `grc_index.db.bak-greek-20261001-1152`.
  The production lemma caches moved aside to `cache/lemmas/grc.bak-greek-20261001-1152/`
  and the new ones copied in. Greek frequency table recomputed (464,732
  lemmas), bigram table rebuilt (`scripts/corpus/rebuild_bigrams.py grc`,
  3,250,475 distinct bigrams, 92 seconds). Stored passage wording refreshed
  for the 11 κα books (617 windows, 244 lines). App reloaded 12:52:05;
  `scripts/reference_search_check.py` passed.
- Before: 1,268 texts, 478,011 lines, 11,118,254 postings, 498,554 lemmas.
  After: 1,268 texts, 478,011 lines, 11,063,906 postings, 464,732 lemmas.
  The token "αυτου·" has no postings now (240 before); ὑμνέω has 471 where
  the invented stem υμνειτοσ had stood.

### Checked afterwards
- The share of tokens whose lemma is their own surface form fell in every
  text sampled, Septuagint and classical alike: Genesis 48.6% to 41.2%,
  Plutarch's Alexander 47.6% to 45.1%, Plato's Republic 48.9% to 46.9%,
  Thucydides 43.4% to 42.1%, the Iliad 36.7% to 36.6%. Distinct lemmas per
  text fell with it, which is the invented stems leaving.
- The production environment has no CLTK, so no backoff lemmatizer took
  part in this build or in live queries, and the index and the queries
  agree. The surface-form shares above include every word whose lemma is
  its own form (particles, prepositions, uninflected forms), so they
  overstate the gap. Counting only tokens whose form is in neither lemma
  table, the unresolved share is 4.3% of the Iliad, 10.7% of the Republic,
  10.6% of Thucydides, 15.1% across Plutarch and 14.4% of the whole Greek
  index (2.04 million of 14.19 million tokens, each work counted once).
  That gap is the open item; a table built from the GLAUx corpus covers
  90% of it and waits in a branch.

## 2026-10-01 Septuagint κοὶ corrected, Greek index rows, lemma caches and stored wording refreshed for 15 books (run 11:11 to 11:14 EDT)

### What and why
- PR #554 (issue #523) corrected 158 occurrences of κοὶ and κοί to καὶ and
  καί in 15 Septuagint books: the 157 listed in
  `data/proposals/septuagint_koi_2026-09-30.csv` and one in the Psalms of
  Solomon (5.16) that a paragraph mark had hidden from the search. No other
  word changed. Production pulled to ec31171.

### Steps
- Greek lemma caches: `scripts/batch_lemma_cache.py grc` rebuilt the 15
  changed files by content hash (1,253 already cached, 2 seconds).
- Index: `grc_index.db` copied, the 15 files replaced in the copy with
  `scripts/corpus/add_texts_to_index.py --replace`, `lemma_doc_freq`
  rebuilt (498,554 lemmas), integrity ok, swapped in. Backup
  `grc_index.db.bak-kai-20261001-1111`. After: 1,268 texts, 478,011 lines,
  11,118,254 postings. The corrected Genesis 22.6 line in the index now
  reads καὶ τὸ πῦρ.
- Stored passage wording: `scripts/corpus/refresh_window_text.py` over the
  15 works, 473 windows and 152 lines updated (a spelling change leaves the
  descriptions and vectors valid). No Septuagint window holds a standalone
  κοὶ any more.
- `touch tesseraev6_flask.wsgi` at 11:13:56.

### A false start, recorded
- The deploy chain first ran at 11:00 on an unmerged pull request: the
  merge had been refused for a changelog conflict and the chain did not
  check the merge result before pulling. It rebuilt the Greek index from
  the then-current caches and swapped it in (backup
  `grc_index.db.bak-kai-20261001-1100`), a change of a few postings and no
  text, and refreshed nothing. The chain now stops unless the pull request
  reports itself merged.

## 2026-10-01 Hebrew homographs, index, lemma cache, frequency and bigram tables rebuilt (run 10:48 to 10:56 EDT)

### Deploy
- Production moved to ff5014e (#552, Hebrew homographs told apart by their
  vowel points). `keep_old_bundles.sh save` (9 files), pull, the data
  operation below inside an 8 GB job scope, `restore` (7 older bundles
  kept), bundle rebuilt, `touch tesseraev6_flask.wsgi` at 10:49:45.

### Index
- Built in the worktree `~/tesserae-hebrew3` with
  `scripts/build_inverted_index.py --language he --force` (12 seconds),
  verified (integrity ok), copied in over the live file with the backup
  `he_index.db.bak-homographs-20261001-1049`. Before: 39 texts, 23,206
  lines, 267,637 postings, 5,980 lemmas. After: 39 texts, 23,206 lines,
  269,079 postings, 8,161 lemmas. The split readings, in postings: אל
  4,204, אל² 579 and אל³ 304. עם 1,670 and עם² 941. מלך 2,058 and מלך² 284.

### Caches
- `cache/lemmas/he/`: the 6 files there (built by the web server under the
  old tables) moved to `cache/lemmas/he.bak-homographs-20261001-1049/`, all
  39 rebuilt with `scripts/batch_lemma_cache.py he --force`.
- `cache/frequencies/he.json` (the web server's, 5,962 lemmas) moved aside
  as `he.json.bak-homographs-20261001-1049` and recomputed from the new
  lemmas: 8,115 lemmas. The live rare-words list for Hebrew now holds
  5,827 rare lemmas, 1,476 of them numbered readings.
- One cached Hebrew cross-language search removed from `cache/`.
- `cache/bigrams/he_bigrams.json`: the first rebuild wrote a table of 0
  bigrams over the live one, because `scripts/corpus/rebuild_bigrams.py`
  did not register the plugin languages and Hebrew fell through to the
  Latin tokenizer. The August table was restored from the script's own
  backup (`he_bigrams.json.pre-rebuild-20261001-1049.bak`) one minute
  later. After PR #553 (the script registers the plugin languages and
  refuses an empty table) was merged and pulled, the rebuild ran again
  inside an 8 GB job scope: 39 texts, 98,351 distinct bigrams, 282,346
  occurrences, 6 seconds, backup `he_bigrams.json.pre-rebuild-20261001-1056.bak`.
  21,959 of its keys carry a numbered reading. App reloaded at 10:56:24.

### Checks
- A live lemma search of 2 Samuel against Psalms answers with the numbered
  lemmas among its matched words (קדם², שאול², מות² on 22.6 = 18.6).

## 2026-09-30 Per-text blurbs written for the corpus works that had none (16:29 EDT 2026-09-30 to 01:15 EDT 2026-10-01)

### Descriptions
- Ran `scripts/corpus/describe_works.py` from a worktree, not production, to
  write `data/text_descriptions.json` blurbs for every work under
  `texts/{la,grc,en}` with none: 698 Latin, 843 Greek, 42 English, 1,583
  works in scope. GLM 5.3 Flash on the campus BullsAI gateway wrote each
  blurb from the work's opening lines (capped at 40 lines or about 3,000
  characters, whichever comes first, after a fix mid-run: a prose work's
  single `.tess` line can be a whole paragraph, and two works' opening
  excerpts ran to 11,900 and 161,600 characters before the cap, which made
  the model reason without ever finishing), the filename-derived author and
  title, the matching `backend/text_sources.json` record when one could be
  matched (exact or close author/work match, about 90% of works), and the
  `data/text_genres.csv` row when present. 1,583 of 1,583 works got a
  written blurb after four retry passes for items that failed every try
  (43, then 5, then 2, then 1 remained stuck. The character cap fixed the
  last two).
- First checked every blurb with Qwen 3.8 (thinking off) for any claim the
  inputs do not support: 116 ok, 1,467 flagged. That check was too strict.
  It can only verify against the same narrow excerpt the writer saw, not
  the work's full text, so true detail past the opening (named characters,
  later plot, a work's traditional title, a date known generally but not
  stated in the inputs) read as unsupported. These results are kept for
  the record at `checks_strict.jsonl`, not used for the merge below.
- Re-ran the check with a different question: does the blurb CONTRADICT
  the inputs, or state something a reference work would not say, rather
  than merely add detail the inputs cannot confirm. Result: 689 ok, 894
  flagged, run twice for 13 that errored on the first pass (11 of which
  then also flagged). Sampling the flagged list still finds some
  overcautious flags, but also genuine catches, among them a blurb that
  quoted a line from the wrong speaker, one that named a title at odds
  with the source record, and one that described plot events the opening
  excerpt rules out.
  Full counts, the held-back list and sample blurbs are in the pull
  request description.
- Merged the 689 checked-ok blurbs into a NEW `data/text_descriptions.json`
  built from the pre-batch file: 33 English (a new top-level key, English
  had no blurbs before), 355 Latin, 301 Greek. Existing entries stayed
  untouched, and new keys were sorted after the existing ones in each
  language. Nothing in the live index or app changed, since this is corpus
  metadata only, read at request time.
- Run data kept outside the repository at
  `~/tesserae-backups/jobs/blurbs_2026-09-30/` (`blurbs.jsonl`,
  `checks.jsonl`, `checks_strict.jsonl`): every write and check call,
  resume-safe. Key spend rose from 45.97 to 115.64 of that day's 500-unit
  budget for the write pass and the first check, then the daily reset at
  2026-10-01 00:00 UTC gave a fresh 500, against which the second check
  and its retries drew the key to 160.4, shared throughout with a
  concurrent, unrelated whole-corpus passage re-description job on the
  same key.

## 2026-09-30 Evening deploys, 16:27 to 2026-10-01 00:10 EDT (assistant, Theme Comparison, Hebrew)

### Assistant
- #531 (16:27, page rebuilt): prompts that judge as well as report, ten
  passages of 400 characters, token caps 900, the corpus holdings handed
  to the model for a named author. Live check: a reading of Thebaid 1
  against Aeneid 1 picked out 1.473 against 1.203, guards clean.
- #532 (17:29, page rebuilt): every exchange recorded under
  logs/assistant/ with no identifier (99 exchanges by 17:40), the
  background check of specific claims, the Privacy page corrected.
- #533 and #534 (17:45 and 17:54): a requested comparison is run and its
  first page read. #533 alone broke every comparison question for nine
  minutes (a yield inside the threaded preparation), #534 repaired it,
  live check passed. The copy now reads "Search, read, interpret".
- #540 (23:57): the router matches whole words, the number guard lets a
  definite "the two" pass. Live rerun of the graded set's failures: all
  resolved with #542.

### Theme Comparison
- #535 (18:35, page rebuilt): the pairwise form of Theme Search, route
  /api/passages/compare, page tab, connector tool, assistant path. The live
  check on Aeneid 1 against Lucan 1 gave moderate confidence, prophecy pairs first.
- #541 (00:10, page rebuilt): shared wording inside each pair from the
  cached word-level comparison, pair lift beside word-level results. In the
  live check nine of ten pairs carried their parallels for the cached Aeneid 1
  against Lucan 1.

### Hebrew
- #536 (23:10, page rebuilt): the Hebrew-Greek route as a choice
  (Septuagint default, direct, both), the Hebrew-Latin bridge rebuilt
  with the main dictionary (hebrew_latin.csv 20,631 to 29,907 lines and
  Vulgate Genesis coverage 42.7 to 59.3 percent). Four cached Hebrew
  result files cleared. Proposals for #519 and #523 under data/proposals/.
- #538 (23:20): twenty-six Hebrew-Greek equivalents added to
  hebrew_greek.csv from the aligned-verse evidence. Cached Hebrew results
  cleared again (none remained).

### Jobs
- The whole-corpus re-description with GLM 5.3 Flash restarted at 22:27
  with 64 requests in flight (from 24), 1.5 windows a second, 35,000 of
  510,839 by midnight. The demo site's reservation lowered in place from
  16 to 8 GB at 22:30.
- Per-text blurbs: 1,583 written (about 70 quota units). The check pass
  rerun as a contradiction test after a coverage test passed only 116;
  draft pull request #539, not merged, awaiting the maintainer's reading.

## 2026-09-30 The assistant moved to the campus AI gateway, seven re-sourced Latin poems rebuilt into the live indexes, whole-corpus re-description begun (14:35 to 14:56 EDT)

### Assistant
- #528 merged and pulled (14:35). The rebuilt page deployed with the
  previous bundles kept (`scripts/keep_old_bundles.sh save` and `restore`).
  Four settings added to the production environment file: gateway URL,
  model `Qwen/Qwen3.8-27B-FP8`, key, and the request field that turns the
  model's thinking off. App reloaded. Live check: the status route reports
  the model available, and two questions that need the model were answered
  in 2.2 s and 1.4 s with the model in use. The local model server
  (`tesserae-assistant`, llama-server, about 25 GB) was stopped and
  disabled at 14:47 after a like-for-like run of ten questions. Its unit
  file remains, and removing the four settings and reloading returns the
  assistant to it.

### Texts and index
- #529 merged and pulled (14:45): nine files for seven works replaced under
  `texts/la/` (Prudentius Apotheosis, Hamartigenia, Contra Symmachum whole
  and two book files, Dittochaeon, Epilogus, and Dracontius Orestes and
  Satisfactio), all validated. Stored window wording refreshed for the
  seven works with `scripts/corpus/refresh_window_text.py` (1,308 windows
  examined, 751 updated, 3,500 lines, backup
  `window_texts.db.bak-textrefresh-20260930-144830`). Descriptions and
  vectors kept, since the wording changes are spelling and punctuation
  except in Contra Symmachum, whose numbering shifts by one line from
  1.354 and from 2.330. Its windows keep their descriptions until the
  corpus re-description below reaches them.
- Lemma caches built for the nine files (`scripts/batch_lemma_cache.py la`,
  8 GB job, 14:47 to 14:49). `la_index.db` copied, the nine files replaced
  in the copy with `scripts/corpus/add_texts_to_index.py --replace` (12 GB
  job, 14:50 to 14:51, 1,655 texts, 932,822 lines, lemma_doc_freq rebuilt
  with 331,096 lemmas, integrity ok), swapped in at 14:52 with backup
  `la_index.db.bak-mqdq-20260930`, app reloaded. Latin frequency cache
  recalculated through the app's own route (83 s, 1,833 texts).
  Rare-bigram table rebuilt (`scripts/corpus/rebuild_bigrams.py la`, 101 s,
  783 works, 3,828,161 bigrams), app reloaded again. Every reference search
  passed after the index swap, and a live lemma search of the new
  Apotheosis against the Aeneid returned twenty parallels.

### Passage descriptions
- Whole-corpus re-description with GLM 5.3 Flash on the campus gateway
  began at 14:17 with a metered first thousand windows (994 described, 6
  without a parseable answer after four tries, 28.7 min, about 6.5 quota
  units) and continues as a detached job in chunks of 20,000 windows with
  24 requests in flight, sleeping through the daily quota reset. Output
  accumulates outside the index; nothing in the live index changes until
  the run completes and the descriptions are applied in one operation with
  `scripts/corpus/apply_passage_rows.py --mode replace`, followed by the
  retrieval and pairwise measurements. Expected duration about a week.

## 2026-09-30 Corpus: seven Prudentius and Dracontius texts re-sourced from Musisque Deoque (planned, not yet run)
- Why: Musisque Deoque's edition of these seven works is replaced with
  openly licensed text from Perseus (the five Prudentius works) and
  Corpus Corporum (Dracontius's Orestes and Satisfactio), so the corpus
  carries a clear licence for each. Full staging comparison in
  `backend/text_sources.json` (per-work `note` field) and the PR
  description.
- Source, Prudentius (Apotheosis, Hamartigenia, Contra Symmachum,
  Dittochaeon, Epilogus): `PerseusDL/canonical-latinLit`, author group
  `stoa0238`, H. J. Thomson's text (the Loeb edition), CC BY-SA 4.0 at the
  repository level. Converted with `backend/ogl_converter.py`, whose P5
  path is fixed in this PR. A leaf division of bare `<l>` verse lines with
  no `<p>` wrapper and no `verse`-typed subtype (the shape all five files
  use) now yields one output line per `<l>`, cited by the line's own `@n`,
  instead of flattening the whole division into one line. A leaf marked
  subtype `verse` (one verse typeset across several `<l>` elements, e.g.
  Lamentations) is unaffected.
- Source, Dracontius Orestes: Corpus Corporum idno 16685 (Vollmer's 1905
  MGH edition), text held public domain, Corpus Corporum's own annotations
  CC BY 4.0.
- Source, Dracontius Satisfactio: Corpus Corporum idno 7702 (Migne,
  Patrologia Latina 60, 1847), public domain. Idno 16685 carries the same
  poem too, but that digitization repeats two of its lines verbatim at a
  second position each, inflating its count well past the current file's.
  The Migne text matches line for line instead, at the cost of an older,
  less rigorous edition than Vollmer's.
- Counts (old lines / new lines, references shared / missing / new):
  Apotheosis 1152/1152, 1152/0/0. Hamartigenia 1029/1029, 1029/0/0.
  Dittochaeon 196/196, 196/0/0. Epilogus 34/34, 34/0/0. Orestes 974/973,
  973/1/0 (the old file's final line has no counterpart in the source).
  Satisfactio 316/316, 316/0/0. All six are identical or near-identical in
  wording once spelling and orthography are normalized. See
  `backend/text_sources.json` for the per-work figure.
- Contra Symmachum: 1944 old lines against 1943 new, 1942 references
  shared, 2 missing, 1 new. Its numbering changes at two points, both
  independent of the source swap. Book 1 shifts from line 354, where the
  old file had split one hexameter ("hoc tamen utcumque est tolerabile,
  quid," / "quod et ipsae") across two citation numbers that Perseus and
  the traditional numbering treat as one line. Book 2 shifts from line
  330, where Perseus's text (and the manuscript tradition) has no line
  329. From each
  point on, every citation number in the old file runs one ahead of the
  new one until the next shift. Split into `part.1.tess` (746 lines) and
  `part.2.tess` (1197 lines) to match the existing book files.
- Excluded from this PR, staying on Musisque Deoque: Dracontius's Romulea
  (ten parts plus fragments) and De Laudibus Dei, held for a second pass.
  Romulea's candidate source has no machine-readable per-poem division and
  needed hand reconstruction, with several residual line-count gaps not
  fully resolved. De Laudibus Dei's two candidate sources do not reconcile
  with the current file's line numbering at any offset. Priscian's two
  poems and Ennius's Annales are untouched. No open source holding either
  Priscian poem was found, and none was sought for Ennius.
- Production steps after this PR is pulled. Rebuild the Latin inverted
  index, the Latin lemma cache, and the passage index for the affected
  files (`prudentius.apotheosis`, `prudentius.hamartigenia`,
  `prudentius.contra_symmachum` and its two part files,
  `prudentius.dittochaeon`, `prudentius.epilogus`, `dracontius.orestes`,
  `dracontius.satisfactio`), each inside its own capped `systemd-run`
  scope per the memory rules above, one job at a time. Verify with the
  reference tests in `tests/search_reference_tests.md` afterward.

## 2026-09-30 Deploy of four search fixes (07:25 EDT)

- Production moved from c522d02 to c4c7800: #509, #524, #507, #525 (see
  CHANGELOG 2026-09-30). Backend and stoplist changes only, so a pull and a
  wsgi touch, no bundle rebuild. Every reference search passed. The Coptic
  single-word exact Line Search that returned nothing (#502) returns 500
  lines. Hebrew cross-lingual searches now match the dictionaries' medial-
  spelled keys. The stoplist change takes effect at search time and needs
  no index rebuild.

## 2026-09-29 Classical Latin batch imported end to end, the converter extension, and the overnight caches (12:00 to 03:07 EDT)

### Texts and index
- Nine Latin works in thirteen files (#516): the three Pseudo-Caesar
  continuations (De bello Africo, Alexandrino and Hispaniensi, from
  Perseus under CC BY-SA 4.0), Vegetius' Epitoma rei militaris as a whole file and four
  book files, Grattius' Cynegetica, Germanicus' Aratea, Solinus'
  Collectanea, Censorinus' De die natali and Julius Obsequens' Liber de
  prodigiis (The Latin Library, edition not stated, the same basis as the
  August imports). All validated. The Obsequens conversion drops the
  editor's consular-year headings, which a first pass had written into the
  text.
- Lemma caches built for the thirteen files (`scripts/batch_lemma_cache.py
  la`, 8 GB job). `la_index.db` extended on a copy with
  `scripts/corpus/add_texts_to_index.py --add` (12 GB job) and swapped in:
  1,642 to 1,655 texts, 929,629 to 932,825 lines, 16,908,692 to 17,011,699
  postings, lemma_doc_freq rebuilt (331,087 lemmas), integrity ok. Backup
  `la_index.db.bak-classical-batch-20260929`.
- Rare-bigram table rebuilt (`scripts/corpus/rebuild_bigrams.py la`, 101 s,
  783 works, 3,828,137 bigrams), backup by the script's own naming. The
  app was reloaded after the index swap and again after the bigram swap.
  Every reference search passed, and a live lemma search of Grattius
  against the Georgics returned fifty parallels.

### Passage windows and descriptions
- 697 windows built for the nine works (`scripts/corpus/build_batch_windows.py`,
  Vegetius by book only, following the books-canonical rule) and their text
  stored (`window_texts.db` backup `.bak-classical-batch-20260929`, table
  510,838 rows).
- Described at 20:17 by Qwen 3.8 27B on UB's BullsAI gateway (thinking
  off, the production prompt, stamp `qwen38-bullsai-20260930`): 697 of 697
  in 4.6 minutes, no failures, the first production descriptions from that
  service. Appended to the passage index at 21:46 with
  `scripts/corpus/apply_passage_rows.py --mode append --tag
  classical-batch-20260929`: 510,142 to 510,839 windows, ids and vectors in
  step, backups `.bak-classical-batch-20260929`.
- `desc_fts.sqlite` rebuilt (511,076 rows, 29 s), app reloaded 21:52. A
  Theme Search for a general training raw recruits returned Vegetius book 1
  among its 25 rows on the live site. Reference searches passed.
- Density cache recomputed for every work (23:25 to 02:52: 3,259 computed,
  1 cached, 0 failed) and the connections map rebuilt (02:52 to 03:07,
  peak 4.3 GB). The map page serves the new fingerprint with no stale flag.

### Also that day
- #515 merged and pulled: the text converter reads the older Corpus
  Corporum and MGH TEI shape. Script-time code, no reload.
- `lxml` 6.1.3 installed into the production environment, which had lacked
  it although requirements.txt has listed it since the Lamentations fix.
  `stanza` and `sentence-transformers` remain deliberately absent (the
  encoder is a separate service and the Hebrew fallback is switched off).
- Per-text descriptions for the nine works added to
  `data/text_descriptions.json` in the same pull request.

## 2026-09-28 Evening deploy of the comment rewrite, and the repository cleared of working material (23:53 EDT)

- Production moved from a658e39 to 9b59058: #510 (the task-list copy
  removed from docs/), #511 (25 research notes and three working drafts
  untracked, none of them part of the running site), #512 (237 comment
  and docstring lines rewritten to state outcomes and rules). Bundle
  rebuilt inside an 8 GB job (8.8 s), 54 older bundles kept beside the new
  `index-BFId7Yxm.js`, wsgi touched 23:53:50. Home page 200 on the first
  request and the served page asks for the new bundle. Every reference
  search passed.
- The same day, 282 of the repository's 285 branches were deleted after a
  verified bundle backup of every reference was taken: 270 belonged to
  merged or closed pull requests and 12 had no pull request. `main` and the
  two open pull requests remain. The two open branches were brought up to
  date with `main` so their tips carry none of the removed files.

## 2026-09-28 Lamentations described again, and the whole-file windows dropped from the passage index (run 06:52 to 06:55 EDT, caches recomputing after)

### Lamentations rows replaced
- The 33 windows of the Septuagint's Lamentations, rebuilt from the
  restored text on 2026-09-27, were described overnight by the local
  assistant model on this machine (`scripts/corpus/describe_windows.py`
  against the assistant's own endpoint, 33 of 33 in 16.8 minutes, no
  failures, no cost), and the new descriptions and their embeddings were
  written in place with `scripts/corpus/apply_passage_rows.py --mode
  replace --tag lamentations-20260928`. Same 33 ids as before. Backups
  `embeddings.npy.bak-lamentations-20260928` and
  `descriptions.jsonl.bak-lamentations-20260928`.
- The stored window and line text of the work was refreshed from the
  restored file with `scripts/corpus/build_batch_windows.py --upsert-db`
  (33 window rows replaced, 150 line rows rewritten). Line 1.2 carried the
  bare acrostic letter before and carries its verse now. Backup
  `window_texts.db.bak-lamentations-20260928`.
- This is the first production description batch made with the free local
  model. Descriptions of the same passages in the Vulgate, made with the
  paid model in August, are the comparison. The local model matches on
  theme and situation and is weaker on proper names. It writes a city
  where the paid model named Jerusalem, and leaves the setting blank on
  two of the 33 windows.

### Whole-file windows dropped
- Following the decision of 2026-09-27 (DECISIONS.md),
  `scripts/corpus/drop_whole_file_windows.py --index data/passage_index
  --texts texts --tag whole-windows-20260928 --apply` (PR #504, merged
  and pulled first) removed the whole-file windows of the 129 works whose
  book files all have windows of their own. 620,773 windows before,
  510,142 after: 110,631 windows, 110,640 description rows (nine were
  duplicate rows for dropped windows) and 110,631 window-text rows. The
  works' line rows were left in place. Backups of all four index files
  carry `.bak-whole-windows-20260928-20260928-065331` (5.6 GB in all).
- Eight works keep both copies because a book file of theirs has no
  windows: `alcuin.carmina` (73), `appian.foreign_wars` (1),
  `augustine.de_trinitate` (praef), `catullus.carmina` (85, 93, 94, 105,
  106, 112), `dracontius.romulea` (fragments),
  `hegesippus_pseudo.de_excidio_hierosolymitano` (0), `plato.epistles`
  (10, 12), `william_of_tyre.historia_rerum_in_partibus_transmarinis_gestarum`
  (0, 23). Fifteen files of one to five lines.
- The word index was rebuilt (`scripts/build_desc_fts.py`, 510,379 rows,
  29 seconds) and the app reloaded at 06:55.
- Checks after the reload. The whole Aeneid answers the gutter request
  with 1,643 windows drawn from its twelve book files (first call 68
  seconds, uncached). Similar Passages from a whole-work selection (Aeneid
  1.1 to 1.12) returns results. A Theme Search for a warrior arming scene
  in Latin shows 25 rows and none under a whole-file name. Every reference
  search passes.
- The index fingerprint changed, so the passage density cache and the
  connections map are being recomputed in one 8 GB job started 06:55
  (`scripts/precompute_passage_density.py --language all`, then
  `scripts/build_connections_map.py`). Until the density job reached a
  work, the first Reader visit to it computed the gutter live, and the map
  served its previous build marked stale.
- The job finished at 10:37. Density pass 06:55 to 10:22: 3,247 works
  computed, 1 already cached, 0 failed, peak 4.6 GB, 14,801 cache files
  (239 MB). Connections map 10:22 to 10:37: 2,031,530 kept edges, 26,555
  author pairs, 821 century pairs, 259 genre pairs, cache
  `18165036-1790592845.1044770944-1790592832.db` (688 MB), peak 4.3 GB.
  The map page reports that fingerprint, matching the live index, and no
  longer marks its data stale. The previous map cache (920 MB) remains as
  the fallback for a stale index and can go after a week.
- The passage-index data release under Downloads predates this change and
  will be regenerated.

## 2026-09-27 Coptic letters restored across every stored form (run 14:51 to 14:57 EDT)

### What and why
- PR #501 (issue #493): the normaliser had moved the seven Coptic-only
  letters from U+03E2 to U+03EF to U+2CB2 to U+2CBF, seven different
  letters, so every stored Coptic form carried the wrong ones. The code now
  leaves them in place and strips U+2CB2 to U+2CBF as the editorial marks
  they are in our texts. Every stored form therefore had to change at once.

### Steps
- Production pulled to a3910f2. Bundle rebuilt inside a job scope
  (`index-Cl5x7DJs.js`), 53 older bundles kept beside it.
- `data/lemma_tables/coptic_lemmas.json` copied in (1,361,051 bytes, 30,085
  entries), corrected with `scripts/corpus/restore_coptic_letters.py`.
  Production had never had this file, so the live server had lemmatized
  Coptic queries without a table while the index was built with one.
- The 209 files in `cache/lemmas/cop/` are the SCRIPTORIUM annotations
  themselves, not derived data, so they were corrected rather than rebuilt:
  backed up whole to
  `~/tesserae-backups/coptic_annotation_caches_pre493_20260927-1451.tar.gz`
  (36.7 MB), then each replaced by its corrected copy. 4,971,308 letters
  moved, part of them stored as JSON escapes, none left.
- `cop_index.db` rebuilt in a separate tree from the corrected annotations
  with the seven aggregate files set aside, exactly as the live index
  excludes them, then swapped in. Backup `cop_index.db.bak-letters-20260927-1451`.
  Before and after are identical in shape: 180 texts, 70,842 lines,
  1,466,155 postings, 29,323 distinct lemmas. Lemmas carrying the wrong
  block: 11,722 before, none after. Integrity ok. An earlier rebuild attempt
  with no annotation files present produced 165,534 lemmas from bare
  surface forms and was discarded.
- `cache/rare_words/cop.json` and the cached Coptic searches removed.
- `cache/frequencies/cop.json`, the per-language word-frequency table the
  Rare Words Explorer reads, still held 15,404 wrong letters after all of
  the above and was corrected in place (29,323 keys, none wrong after,
  backup `~/tesserae-backups/coptic_frequencies_cop_pre493_20260927-1456.json`).
  An earlier scan missed this directory through a misspelled pattern.
- `touch tesseraev6_flask.wsgi` at 14:51:52, again at 14:55:41 and 14:56:45.
- The dev checkout's own lemma table and 193 annotation files corrected the
  same way, so no later build regresses.

### Checks
- Home page 200 on the new bundle. `scripts/reference_search_check.py` passed.
- Coptic lemma search for ϫⲟⲉⲓⲥ returns 20 lines. The Help page stoplist
  shows 143 entries, 32 with the seven letters, none from the wrong block.
- Rare Words Explorer for Coptic: 22,573 rare lemmas, the sample now reads
  "(ϩⲟⲩⲛ" with hori, none with a wrong-block letter.

### Found and not fixed here
- Exact-mode Line Search returns nothing for Coptic, for words with and
  without the seven letters, although the exact pattern matches the raw
  lines when tested directly. Not touched by this change. Issue #502.

## 2026-09-27 Lamentations regenerated and re-indexed, and the cache-builder fix pulled (run 13:40 to 13:46 EDT)

### What and why
- PR #499 regenerated `texts/grc/septuaginta.threni_seu_lamentationes.tess`
  from its Open Greek and Latin source through the fixed converter: 88 of
  its 150 verses had held nothing but the acrostic letter name (issue
  #276). Same 150 references, 664 words to 2,447. Production pulled to
  12ef551. Earlier the same day PR #498 (the cache builder registers plugin
  languages and refuses unknown ones, issue #495) was pulled as cad17de, a
  script only, no reload.

### Steps
- The file's Greek lemma cache, ours, deleted and rebuilt with
  `scripts/batch_lemma_cache.py grc` (1 built, 1,267 already cached, 0
  errors). The rebuilt builder reported the plugin languages it registered.
- `scripts/corpus/add_texts_to_index.py --db <copy> --language grc
  --cache-dir cache/lemmas --replace septuaginta.threni_seu_lamentationes.tess`
  on a copy of `grc_index.db`, then swapped. Backup
  `grc_index.db.bak-threni-20260927-1345`. The text's entry went from 146
  lines and 603 postings to 150 lines and 2,019 postings, and the index
  from 11,116,118 to 11,117,534 postings. `lemma_doc_freq` was rebuilt,
  499,650 lemmas. Integrity ok.
- `touch tesseraev6_flask.wsgi` at 13:45:56.

### Checks
- Home page 200. `scripts/reference_search_check.py` passed.
- An exact search for the opening words of 1.1 (ἐκάθισεν μόνη) finds
  Lamentations 1.1 and a line of Clement's Paedagogus that quotes it.

### Not done, and why
- The book's 33 passage windows still carry text and descriptions made
  from the bare letter names ("a listing of letters, alphabet,
  enumeration"). `scripts/corpus/refresh_window_text.py` was not used: it
  is for wording changes that leave meaning intact, and here the meaning
  changed entirely. The windows need a describer run, which is a decision
  about spending (a rented GPU for minutes, or the free route).

## 2026-09-27 Deploy of the summed scoring rule (run 11:46 EDT)

### Deploy
- Production moved from af59abe to 24016ad, PR #496 only: `backend/scorer.py`
  no longer divides the summed word rarity by the number of shared words,
  `backend/score_bounds.py` names the rule in force and `backend/cache.py`
  writes that name into every results cache key. No client change, no
  bundle. `touch tesseraev6_flask.wsgi` at 11:46:21. Home page 200.
- `scripts/reference_search_check.py` passed after the reload.

### Checks
- Live, cache bypassed, Lucan 1 against the whole Aeneid, lemma search,
  two shared words: 2,086 results, top score 3.445 (1.723 before), mean
  score by shared-word count 2: 1.409, 3: 1.601, 4: 1.975 (before 0.704,
  0.534, 0.494). These are the figures the test checkout predicted
  (docs/DECISIONS.md, 2026-09-27).
- The results cache was NOT cleared by hand and did not need to be: the rule
  name in the key means the entries written under the old rule are never
  looked up again. They remain on disk as ordinary files until the pruning
  rule or a later clear removes them.
- Cross-language check before the merge, Iliad 1 against Aeneid 1 against
  the Knauer gold: identical under both rules (419 results, same three
  attested pairs at the same ranks), so the dictionary path is untouched.

## 2026-09-25 Deploy of seven merges, Hebrew index rebuilt, backups pruned, orphan window rows removed (run 10:32 to 10:35 EDT)

### Deploy
- Production moved from 74d7e04 to 5fbad92: #490, #476, #489, #488, #485,
  #475, #491. `keep_old_bundles.sh save` (53 files), pull, bundle rebuilt
  inside an 8 GB job scope, `restore` (52 older bundles kept beside the new
  one), `touch tesseraev6_flask.wsgi` at 10:34:37. New bundle
  `index-D-eqbase.js`. The home page answered 200 on the first request and
  the served page asks for the new bundle.
- `scripts/reference_search_check.py` passed against production after the
  reload.

### Hebrew index rebuilt
- Two merges changed what the index holds for Hebrew, the joiner fix (#485)
  and the fallback alignment (#491), so it was rebuilt ONCE for the pair.
  Built in a separate checkout (`~/tesserae-hebuild`,
  `scripts/build_inverted_index.py --language he --force`, 24 seconds) so
  the live file was never removed mid-build, verified, then copied in.
  Backup `he_index.db.bak-jerusalem-20260925-1032`.
- Built with the dev venv, which has Stanza 1.11.0 and the Hebrew model,
  after confirming the pipeline loads there. The live index had been built
  that way: a third of its tokens fall outside the lookup table's exact keys
  and carry real lemmas, including the shifted-lemma signature the
  alignment fix removes, and without Stanza an unknown word keeps its own
  form. Production's venv does not have Stanza, although requirements.txt
  lists it, so live queries are lemmatized without the fallback while the
  index has it. Open decision, recorded in the open-work list.
- Before: 39 texts, 23,206 lines, 268,161 postings, 5,870 lemmas. After:
  39 texts, 23,206 lines, 267,621 postings, 5,921 lemmas, same text set,
  integrity ok. Jerusalem: 481 postings on the truncated lemma and 118 on
  the correct one before, 0 and 625 after. One-letter tokens carrying a
  lemma of three letters or more, the misalignment signature: 519 before,
  0 after. The rare name from the alignment issue keeps its 16 postings.
- Stale caches cleared, with a detour. The 8 Hebrew lemma caches in
  `cache/lemmas/he/` and the 4 cached Hebrew searches in `cache/*.json` were
  built under the old tokenizer and are keyed on file content, not tokenizer
  version, so they would have kept serving old tokens for those 8 books.
  The deploy script's `rm` failed on the lemma caches: that directory was
  created by the web server and belongs to it, mode 755. The parent
  `cache/lemmas/` is ours and writable, so the directory was renamed aside
  (`he.stale-tokenizer-20260925`) and a fresh `he/` created with group write
  (mode 2775, group tessdev, which the web server user belongs to). A
  Reader load of Jonah then wrote a fresh cache into it, written by the web
  server user, confirming the server can fill it. The four search caches
  were deleted directly, `cache/` being writable. The stale directory stays
  until someone with the right permissions removes it. This is the third
  deploy step the cache ownership has blocked (see the open request for
  group write on the web-server-created cache directories).

### Backups pruned
- `scripts/prune_backups.py --apply`, the rule from #466 (keep the newest
  copy of each file), deleted 10 copies, 16.2 GB: two `window_texts.db`,
  three `grc_index.db`, and the win3 and win68 generations of the passage
  index. Four August copies outside the rule's naming
  (`.rollback-2026-08-27`, `.good-20260829`, 3.2 GB) were removed by hand,
  superseded by three later generations. Disk free went from 468 to 487 GB.
  The passage index directory holds 11 GB.

### Orphan window rows removed
- `window_texts.db` held 23 rows for windows not in the index: 14 Persian
  from an earlier multilingual build, 7 Coptic of `shenoute.a22`, 2 Latin of
  `cassiodorus.variae__praefatio_i_`. Saved to a JSON file outside the web
  root, then deleted. 620,795 rows to 620,772 against 620,773 windows. The
  Persian windows that ARE in the index, 218,589 of them, and their rows in
  the `lines` table are untouched. The one window with no stored text,
  `chanson_de_roland.chanson_de_roland:fine:336`, remains open because the
  window text builder has no single-work mode.

### The passage density job
- Paused at work 1,863 of 3,377 to free the job slot for the bundle and
  index builds, restarted at 10:35. It skips finished works. FINISHED 12:45:
  1,509 computed, 1,868 already cached, 0 failed, 3,377 total. Every work in
  the passage index has its gutter density stored for the current index.

### Hebrew index rebuilt again without Stanza (14:59 EDT)
- Following the decision recorded in DECISIONS.md the same day, the index
  was rebuilt from the same texts with the production environment, which has
  no Stanza, and swapped in: 39 texts, 23,206 lines, 267,637 postings, 5,980
  lemmas, integrity ok, Jerusalem 0 and 625 as before. The Stanza-built copy
  is kept as `he_index.db.bak-stanza-built-20260925-1459`. 200 tokens of
  305,550 differ in lemma between the two builds. wsgi touched 14:59:51,
  home page 200, live Jerusalem search 611 lines.

### Later the same day, 15:14 EDT
- PR #494 pulled (af59abe) and the app reloaded with `touch
  tesseraev6_flask.wsgi`. No bundle. Home page 200, reference search passed,
  live Jerusalem search 611 lines, unchanged. The Hebrew fallback is now off
  in code as well as in fact.

## 2026-09-23 Archimedes renamed inside the passage index (run 13:24 EDT)

### What and why
- PR #474 filed eleven Archimedes works under `archimedes` instead of the
  French `archimède`. The passage index still carried the old name in every
  place it stores a work: window ids (`ids.json`), the `work` field of
  `descriptions.jsonl`, and the `work`, `id`, `ref_start` and `ref_end`
  columns of `window_texts.db` plus its `lines` table. Left alone, the
  Reader and Similar Passages would have looked the twelve works up under a
  name the corpus no longer used.
- Run with `scripts/corpus/rename_work_in_passage_index.py archimède
  archimedes --apply` (PR #476). The embeddings are untouched, because the
  windows' content did not change, so nothing was re-described.

### Checks
- Zero rows remain under the old name in any of the four columns of
  `window_texts.db` or in its `lines` table. `ids.json` and
  `descriptions.jsonl` contain the old name zero times. 184 window rows now
  sit under `archimedes.*` across eleven works.
- References were rewritten because Greek line tags carry the work name
  (`archimède.arenarius 1` became `archimedes.arenarius 1`). A work whose
  tags do not carry its name, as Latin `verg. aen. 1.1` does not, is
  correctly left alone by the same rule.
- Backups: `ids.json`, `descriptions.jsonl` and `window_texts.db` copied
  beside the originals with the suffix `.bak-archimedes-20260923-132446`.
  The index loader opens fixed file names, so backup copies in the directory
  are never read. They are covered by the pruning rule
  (`scripts/prune_backups.py`, roots include `data/passage_index`).
- Rewriting `ids.json` changed its modification time, which is half of the
  fingerprint the passage density cache is keyed on. Every work's cached
  density therefore went stale, and the passage density job
  (`scripts/precompute_passage_density.py`) has to run again. It was started
  the same day and restarted on 2026-09-25 after a memory stop.

## 2026-09-22 to 09-23 Passages built for the 68 book files that had none

The 68 Latin book files with no stored passages of their own, plus Ennodius'
Carmina 2, which had none either. Until now the Reader served them another
book's margin marks and neither Similar Passages nor Theme Search could
reach them.

### Windows and descriptions
- `scripts/corpus/build_batch_windows.py` over 69 files: 1,720 windows.
- Described on a rented GPU, about an hour of use.
  RunPod A100 80GB PCIe, SECURE, $1.59/h, Montreal, 13:01 to 14:21 EDT,
  **$2.12**. 1,709 windows in 9.0 minutes at 0.31s each, 0 failed, 32 in
  parallel, `Qwen/Qwen2.5-32B-Instruct-AWQ` under vLLM. The other 11 had
  been done locally beforehand and were skipped by the sidecar.
- Local rate for comparison, measured the same day on the llama-server that
  also serves Tessa: 32s per window one at a time, 23s with six in flight,
  because that server runs a single slot. 1,720 windows would have taken
  eleven hours.
- **Three environment failures cost about 40 minutes of the paid hour**, and
  the runbook in memory is updated so the next job skips them:
  1. `pip install vllm` now brings CUDA 13 wheels and upgrades torch with
     it. The host driver is 12.8, so the engine refused to start with "the
     NVIDIA driver on your system is too old". Pin `vllm==0.10.2`, which
     brings `torch 2.8.0+cu128`.
  2. That vLLM then failed on a newer transformers with
     `Qwen2Tokenizer has no attribute all_special_tokens_extended`. Pin
     `transformers==4.55.2`.
  3. A `nohup ... &` sent as an ssh command did not survive the session
     closing, and I did not check, so the pod sat idle. Write a script file
     and launch it with `setsid`, then confirm the process exists before
     walking away.
- Pod terminated at 14:21 and `list-pods` confirmed empty.

### Applied to the index
- `build_batch_windows.py --upsert-db`: 1,720 rows, `window_texts`
  619,075 to 620,795. Backup `window_texts.db.bak-win68-20260922-*`.
- `scripts/corpus/apply_passage_rows.py --mode append --tag win68-20260922`:
  index 619,053 to **620,773** ids and vectors, lockstep asserted.
  Backups `ids.json`, `embeddings.npy` and `descriptions.jsonl`
  `.bak-win68-20260922`.

### Finished after the reboot, 2026-09-23
Marvin rebooted at 23:00 on 2026-09-22 (Chris, ticket #108315) with the last
three steps outstanding.

- All three user services, Apache and PostgreSQL came back on their own. The
  site and the health endpoint answer.
- **`desc_fts.sqlite` was stale by seven hours** and rebuilt: 621,019 rows,
  679 MB, 32s. Theme Search's lexical boost is silently dropped while it is
  stale, which is the second time that has bitten; it is a step of any
  operation that writes `descriptions.jsonl`, not an afterthought.
- The margin cache held 4 files for the current index out of 6,693, so the
  Reader was cold everywhere. `precompute_passage_density.py --language all
  --only-missing` restarted over **3,377** works, up from 3,308 because of
  the new ones.
- PR #463 merged and deployed, with `touch tesseraev6_flask.wsgi`. It stops
  a book file borrowing the whole work's marks, and it was held until these
  passages existed so the Reader went from wrong marks to right ones with no
  empty phase.

### Checks
- Statius' Achilleid book 1, Sedulius' Carmen paschale book 1 and Suetonius'
  Augustus all answer for Similar Passages, having answered for nothing
  before.
- Suetonius' Augustus margin returns 40 windows starting at
  `suet. vit. aug. 1.1` with no `suet. vit. jul.` reference left in it.
  Before #463 it returned the Julius book's marks.
- "arma virum" returns 367 over 63 authors on the lemma search and 21 over
  11 on the exact search, the expected figures.

### Two counts that differ by 22, and why
- The index holds 620,773 windows and `window_texts.db` holds 620,795 rows.
  The table has 23 rows for windows that are not in the index: 14 Persian
  windows (attar, bidel, ferdowsi, khaghani, nizami, rumi, saeb, sanai
  diwans) left from an earlier multilingual build, 7 Coptic windows of
  `shenoute.a22`, and 2 Latin windows of `cassiodorus.variae__praefatio_i_`.
  It lacks one window the index has, `chanson_de_roland.chanson_de_roland:
  fine:336`, whose text the Reader therefore cannot show. Both counts are
  correct. They measure different files. The 23 orphan rows and the one
  missing text are listed as open work.

## 2026-09-22 Rarity rule deployed; Greek texts cleaned in the index (run 11:20 to 11:40 EDT)

Production moved from `e2561ed` to `236f797` (PRs #446, #452, #464, #470).
Deployed once the checks passed.

### Deploy
- The margin recompute was stopped first to free the job slot for the
  frontend build, at 2,605 works of 3,308. It resumes by skipping what it
  has already written, and restarted at 2,611, so nothing was lost.
- `scripts/keep_old_bundles.sh save` (49 files), pull, `npm run build`
  inside a job scope, `keep_old_bundles.sh restore` (48 older bundles kept,
  attic holds 8), `touch tesseraev6_flask.wsgi`. New bundle
  `index-Bogsq6c1.js`; an older bundle still answers 200, so a stale page
  does not go blank.

### The rarity rule
- A word is rare at 12% of the works in its own language's corpus, not a
  fixed 100. Confirmed live: Latin 744 works to a threshold of 89, Greek 853
  to 102, Coptic 180 to 22, English 42 to 5, Hebrew 39 to 5.
- **The search results cache had to be cleared**, and this is the part worth
  remembering. The threshold is computed rather than passed in the settings,
  so the cache key did not change and every cached search kept answering
  under the old rule. The first check after the deploy looked like a
  failure for that reason. 45 cached searches, 737 MB, deleted
  (`cache/*.json`; 33 Latin, 8 Greek, 1 English, 1 Hebrew, 2 unlabelled).
  Any change that alters results without changing the cache key needs the
  same step.
- Measured before and after on the pair the September memory blowout came
  from, Paradise Lost book 1 against Hyperion: the rare-word channel fired
  on 4,821 of 5,000 results before and 71 after. The surviving matches are
  `wing`+`expand`, `soft`+`flute`+`dorian`, `lay`+`prone`.

### Greek texts cleaned in the index (PR #446, merged earlier today)
- The pull brought four cleaned `texts/grc/` files. Their lemma caches were
  keyed on the old content, so all four were stale and none of the new
  content was cached.
- Four stale entries deleted from `cache/lemmas/grc/`, rebuilt with
  `scripts/batch_lemma_cache.py --language grc` (4 built, 1,264 already
  cached, 0 errors).
- `scripts/corpus/add_texts_to_index.py --db <copy> --language grc
  --cache-dir cache/lemmas --replace <4 files>` on a copy, then swapped.
  Backup `grc_index.db.bak-grc-notes-20260922-113651`. Postings fell where
  the apparatus went: Agatharchides 12,724 to 12,722, Gregory 13,063 to
  13,061, Scylax 4,809 to 4,806, pseudo-Dicaearchus unchanged.
  `lemma_doc_freq` rebuilt, 499,543 lemmas.
- Two details cost a retry each and are worth writing down: the script wants
  the index's own filename, without the `texts/grc/` prefix, and
  `--cache-dir` must be `cache/lemmas`, because the script appends the
  language itself.

### Checks
- `scripts/reference_search_check.py` passes against production, before and
  after the index swap.
- Gregory's Oration 30.9 serves 116 units with the English footnote and the
  inserted Greek gloss both gone.
- The home page and the new bundle both answer 200.
- The margin recompute restarted and is running.

## 2026-09-22 Old backups deleted, newest two of each kept (run 12:05 EDT)

- Run after the disk reached 90% full. Every data operation
  leaves a dated backup beside the file it replaces and nothing had ever
  removed one, so 343 copies had accumulated across `data/passage_index`,
  `data/inverted_index` and `cache`, 222 GB in all. The oldest was from
  January.
- Rule applied: for each file, keep the two most recent backups, delete the
  rest. 135 files deleted, 199 GB freed. The filesystem went from 90% to
  82% full, 283 GB free to 482 GB.
- Checks before deleting: the list was printed and read in full; no live
  file appeared in it; every group kept two copies, so nothing is down to a
  single copy or none; this morning's five backups
  (`window_texts.db.bak-textrefresh-20260922-071229`,
  `window_texts.db.bak-win3-20260922-072536`, and the `ids.json`,
  `embeddings.npy` and `descriptions.jsonl` copies tagged
  `win3-20260922`) were confirmed in the keep list first.
- Checks after: the site answers on the home page and the corpus status
  endpoint, and the margin recompute running at the time was unaffected.
- The list of what was deleted is `/tmp/claude-128144/bak_delete.txt` on
  Marvin, which does not survive a reboot. The rule itself is the record.
- SECOND PASS the same morning, 12:40 EDT, with the rule written down so it
  could be repeated. The rule is now
  `scripts/prune_backups.py` (PR #466), dry run by default: keep the newest
  copy of each file, delete the rest, and never leave a file without one.
  It deleted a further 103 copies and 12.5 GB, leaving 105 copies and
  10.4 GB, one per file. The filesystem ended at 82% full with 491 GB free,
  from 90% and 283 GB this morning.
- The by-hand pass grouped backups by name and got one spelling wrong: a
  plain `la_index.db.bak` with nothing after it was read as a file of its
  own rather than as a backup of `la_index.db`. That made the report claim
  five files were about to lose their only copy when they were not. The
  script fixes it and pins all six spellings in `tests/test_prune_backups.py`.
- What the second pass gave up: `window_texts.db.bak-textrefresh-20260922-071229`,
  the copy made before this morning's wording refresh. Both of the morning's
  operations were verified before it went, and
  `scripts/corpus/refresh_window_text.py` rebuilds the stored wording from
  the .tess files, so the backup was not the only way back.

## 2026-09-22 Passage index: quoted wording refreshed, three books given passages (run 07:12 to 07:30 EDT)

Two operations, run one at a time through `~/bin/tess-job`.

### Quoted wording refreshed for the 20 works corrected on 2026-09-21
- `scripts/corpus/refresh_window_text.py --root . --works-file <list> --apply`
  (PR #462, merged e2561ed). Backup
  `data/passage_index/window_texts.db.bak-textrefresh-20260922-071229`.
- 2,526 windows and 2,453 lines updated. The dry run beforehand reported 353,
  which was wrong: that count compared only the first
  60 characters of a window's first line, while the script compares the
  whole rebuilt window.
- Classified before applying: 1,979 windows differ in punctuation only and
  547 in words. Every word difference is an apparatus number removed and
  the word it had split rejoined, for example
  `παραγ 5 γέλλει` to `παραγγέλλει` in Arrian. Lowest word-level similarity
  over all 2,526 is 0.913 (Orosius, `hist.adv.pag. 2.7.6`); none is below
  0.80, so no passage changed sense and none was re-described.
- Verified: a second dry run reports `0 window(s) and 0 line(s) would be
  updated`; the live Reader serves the repaired `παραγγέλλει` in Arrian
  book 1.

### Passages built for the three works that had none
- `arnobius.adversus_nationes.part.1`, `arnobius.adversus_nationes.part.6`
  and `pliny_the_elder.naturalis_historia.part.0.preface` had text but no
  windows, so Similar Passages and Theme Search could not see them. They
  are the three files added to the Latin index on 2026-09-21.
- `scripts/corpus/build_batch_windows.py --language la --index-db
  data/inverted_index/la_index.db --lemma-table
  data/lemma_tables/latin_lemmas.json --upsert-db
  data/passage_index/window_texts.db`: 19 windows (Arnobius book 1: 14,
  book 6: 4, Pliny's preface: 1). `window_texts` 619,056 to 619,075.
  Backup `window_texts.db.bak-win3-20260922-072536`.
- `scripts/corpus/describe_windows.py` against the local llama-server on
  port 8081 (Qwen3-30B-A3B-Instruct-2507-Q4_K_M), stamp
  `qwen3-30b-a3b-local-2026-09-22`, temperature 0: 19 described, 0 failed,
  8.0 minutes. No paid API and no GPU rental.
- `scripts/corpus/apply_passage_rows.py --index data/passage_index
  --sidecar <sidecar> --mode append --tag win3-20260922`: index 619,034 to
  619,053 ids and vectors, lockstep asserted before and after. Backups
  `ids.json.bak-win3-20260922`, `embeddings.npy.bak-win3-20260922`,
  `descriptions.jsonl.bak-win3-20260922`.
- `scripts/build_desc_fts.py` rebuilt afterwards because
  `descriptions.jsonl` changed: 619,299 rows, 678 MB, 34s. Skipping this
  silently disables Theme Search's lexical boost.
- `touch tesseraev6_flask.wsgi`, then checked: Similar Passages answers for
  all three works, and Arnobius returns Augustine's City of God and
  Tertullian's Apology.

### Consequence: the Reader's margin cache had to be rebuilt
- `cache/passage_density` is keyed on the size and mtime of `ids.json` and
  `embeddings.npy` (`backend.passage_index.index_fingerprint`), so adding
  19 rows invalidated all 3,305 precomputed margins.
- `scripts/precompute_passage_density.py --language all --only-missing`
  relaunched for 3,308 works under a 10G cap, log
  `~/tesserae-backups/jobs/density.log`. About 5 seconds per work and a
  5.2 GB peak, so roughly five hours. Until it finishes, a work opened in
  the Reader for the first time pays the cold cost again.
- Note for the next import: build windows for every new file in the same
  operation that adds the text, so the margin cache is invalidated once
  rather than twice.

### Housekeeping noted, not done
- `data/passage_index` holds 116 GB, of which 108 GB is `.bak-*` files from
  past operations, and the filesystem is 89% full. A retention rule (keep
  the newest two per file, say) was not settled, so nothing was deleted.

## 2026-09-21 Corpus: book files canonical, Arrian re-imported (PR #460, run 23:00 to 23:20 EDT)
- Run overnight: the missing book files were generated, the book files were
  made the canonical copy, and Arrian's Anabasis was replaced from a better
  source. PR #460 merged e0ec5c2 and pulled.
- Lemma caches: 20 entries deleted (18 changed or new files, plus the
  misspelled `arnobius_advesus_nationes.part.1.tess` whose file is gone) and
  rebuilt for Latin and Greek.
- Inverted indexes rebuilt on copies and swapped, backups
  `la_index.db.bak-canonical-20260921-231348` and the Greek equivalent:
  Latin 10 files replaced and 3 added (Arnobius book 6, Pliny's preface, and
  Arnobius book 1 under its corrected name), Greek 8 Arrian files replaced.
  `lemma_doc_freq` rebuilt for both.
- One stale entry dropped afterwards with
  `scripts/corpus/drop_stale_index_entries.py --language la --apply`: the
  misspelled Arnobius filename, 65 lines and 7,379 postings. Backup
  `la_index.db.bak-stale-20260921-2313`. Latin texts 1,643 to 1,642, and the
  eight Arnobius entries now all spell the author correctly.
- Checks: `scripts/reference_search_check.py` passes (lemma 367 over 63
  authors, exact 21 over 11); `check_whole_vs_parts.py` passes all 137
  works; Arrian book 6 serves 174 lines including the restored
  `arr. an. 6.24.3`, book 1 serves 248 from `1.0.1`; a Greek search of
  Arrian book 1 against Iliad 1 returns 338 results in 1.6 s. WSGI touched,
  front-end bundle rebuilt (`index-Dd5J60As.js`) because the corpus-picker
  fix of PR #457 was waiting on it.
- NOT invalidated, contrary to what was expected: the Reader's density
  caches survived, because their fingerprint is taken from the passage index
  files rather than the inverted index, and the passage index is untouched
  by a .tess change until its windows are rebuilt. The Latin pass reported
  1,719 of 1,719 already cached.
- FOLLOW-UP, not done tonight: the passage index still holds the OLD text
  for the 20 changed files, so Similar Passages and Theme Search quote the
  superseded wording for those works, and the two new book files have no
  windows at all. Both need a window and description rebuild for those
  works.

## 2026-09-21 Corpus: Arrian's Anabasis re-imported from the canonical Perseus TEI (planned, not yet run)
- Why: the whole file and the book files disagreed and neither was simply
  better, so it was replaced. The file in the corpus came from the
  Perseus reading interface: it lacked `arr. an. 6.24.3` and `7.24.2`, kept
  stray apparatus digits inside the Greek on 27 lines, and wrote `%` where
  the edition prints a dagger.
- Source: `PerseusDL/canonical-greekLit`,
  `data/tlg0074/tlg001/tlg0074.tlg001.perseus-grc2.xml`, 1.18 MB, the text
  of A. G. Roos (Teubner 1907). The printed edition is public domain; the
  digital edition is CC BY-SA 4.0, which is recorded in
  `backend/text_sources.json` with attribution. Any Creative Commons data
  release that includes this file must carry the same licence.
- Converted by `scripts/corpus/arrian_from_perseus_tei.py` (new): notes,
  apparatus and page and line breaks are dropped, the citation keeps our own
  `<arr. an. BOOK.CHAPTER.SECTION>` with each book's preface as chapter 0,
  and the punctuation is written the way the rest of the Greek corpus writes
  it (plain apostrophe for elision, colon for the raised stop), because the
  lemma caches and the index were built on that convention.
- Counts: 1,406 lines against 1,404, the difference being the two restored
  sections. Split into the same seven book files. 760 lines are identical to
  the old file, 644 differ in punctuation alone, and 181 differ in substance,
  nearly all of them the removal of an apparatus digit or the restoration of
  the editor's brackets. Two stray digits remain, against 27 before.
- After this, `check_whole_vs_parts.py` passes all 137 works stored both ways.
- Production steps: the same ones listed in the entry below, with
  `arrian.anabasis.tess` and its seven book files added to the lemma-cache
  and reindex lists for Greek.

## 2026-09-21 Corpus: book files made canonical, comparison script corrected
- Extended the same evening by the main session, after checking the agent's
  findings against the corpus: the comparison script only recognised books
  numbered with digits, so eleven files named for their content
  (`.part.pr`, `.part.praef`, `.part.preface`, `.part.fragments`,
  `.part.21a.old_latin_psalms`) read as missing across eight works. With the
  pattern widened, 132 of 137 works agreed rather than the 117 an earlier
  count reported, and the analysis that asked for twelve works' book files
  to be generated was wrong about ten of them.
- With that corrected, the rule was applied to the works where the book
  files are demonstrably the better text, by
  `scripts/corpus/regenerate_whole_from_parts.py` (new, dry run by default):
  Apuleius (two lines split differently), Arnobius (the whole file read
  "cur erg6" for "cur ergo"), Prudentius (a running header glued into a
  line), and, after repair, the Georgics.
- The Georgics needed the opposite treatment first. 42 of its 43
  differences were mojibake in the BOOK files ("Lenaeeâtuis" for
  "Lenaee—tuis"), so `repair_part_file_defects_2026-09-21.py` repaired them
  from the whole file, and only then was the whole file rebuilt from them.
  Regenerating first would have written the corruption into the canonical
  copy.
- Arrian's Anabasis is left alone and stays failing the check: its book
  files split two merged lines correctly but carry stray apparatus digits
  inside the Greek in two other places, so neither copy is simply better.
  Not yet decided.
- After all of it: 136 of 137 works stored both ways agree.

## 2026-09-21 Corpus: missing book files generated; book files made canonical (planned, not yet run)
- What: `research/corpus/WHOLE_VS_PARTS_2026-09-21.md` listed 12 works whose
  book files were said to be missing whole sections, and named 4 of the
  6 Group B works (differing transcriptions) as candidates to make the book
  files canonical. Checking every claim against the repository (not just
  running `check_whole_vs_parts.py`, which has a filename-pattern bug: it
  only recognizes a part file as `.part.<digits>...tess`, so a part file
  named `.part.pr.tess`, `.part.praef.tess`, `.part.preface.tess`,
  `.part.fragments.tess`, or with a lettered suffix like `.part.2a.tess`
  is invisible to it) found:
  - 10 of the 12 "missing book file" works already have complete book
    files under such a name: `jerome.vulgate` (Old Latin Psalms is
    `.part.21a.old_latin_psalms.tess`, Psalm 151 is `.part.21b.psalm.tess`,
    Laodiceans is `.part.73a.epistle_of_paul_to_the_laodicians.tess`),
    `paulinus_of_aquileia.carmina` (`.part.2a.tess`, `.part.2b.tess`),
    `gellius.attic_nights` (`.part.pr.tess`), `priscian.carmen_in_laudem_
    Anastasii_imperatoris` (`.part.preface.tess`), `sedulius.carmen_
    paschale` (`.part.praef.tess`), `augustine.de_doctrina_christiana` and
    `augustine.de_trinitate` (`.part.praef.tess` each), and
    `dracontius.romulea` (`.part.fragments.tess`). No file was touched for
    any of these 8 works. `cicero.philippicae` and `galen.natural_
    faculties` were already fixed by PR #435 (confirmed: both pass
    `check_whole_vs_parts.py` on main). Only two works had a genuine gap:
    `arnobius.adversus_nationes` book 6 (27 lines, nowhere in the repo
    under any name) and `pliny_the_elder.naturalis_historia`'s preface
    (7 lines). Arnobius book 1 (65 lines) also turned out to already exist,
    verbatim and byte-identical to the whole file, under the misspelled,
    differently-punctuated name `arnobius_advesus_nationes.part.1.tess`
    (missing the "r" in "adversus", and `_part` instead of `.part`), which
    is why the checker's own glob for `arnobius.adversus_nationes.part.*`
    never found it.
  - Of the 4 Group B works, checking which copy is better before acting
    (as instructed for Arrian) found the same question applied to Vergil:
    `vergil.georgics`'s 44 differing lines are not mainly the diaeresis
    difference the analysis document described. 42 of the 44 are the book
    files' em dashes and curly quotes stored as mojibake (`Lenaeeâ\x80\x94`
    for `Lenaee—`); only 2 are the diaeresis case (`aeriae` for `aëriae`).
    Regenerating the whole file from the book files as instructed would
    have replaced 42 correct lines with corrupted ones, so `vergil.georgics`
    was left untouched pending a decision on the mojibake, same as
    `arrian.anabasis` (below). `ovid.metamorphoses` and
    `paulus_orosius.historiae_adversum_paganos` had no such surprise: their
    differences are cleanly curly-vs-straight quotes and em-dash/spacing
    respectively, so both were regenerated.
- Files changed:
  - New: `texts/la/arnobius.adversus_nationes.part.6.tess` (27 lines, copied
    verbatim from the whole file's `arnobius. adversus_nationes. 6.*`
    lines, LF line endings matching the whole file and its siblings).
  - New: `texts/la/pliny_the_elder.naturalis_historia.part.0.preface.tess`
    (7 lines, copied verbatim from the whole file's `plin. nat. preface.*`
    lines; kept the whole file's CRLF line endings even though this work's
    other book files are LF, per "copy verbatim including line endings").
    Named `part.0.preface` rather than treating the preface as book 1: it
    sorts before `part.1.books_1-5.tess` and reads as what it is.
  - Renamed: `texts/la/arnobius_advesus_nationes.part.1.tess` ->
    `texts/la/arnobius.adversus_nationes.part.1.tess` (git mv only, content
    byte-identical, confirmed against the whole file's book-1 lines before
    the rename).
  - Regenerated (concatenated from their own book files, in part order,
    `newline=''` throughout so no line ending changed):
    `texts/la/ovid.metamorphoses.tess` (12,010 -> 12,011 raw lines; the
    +1 is a harmless trailing blank line carried in from book 15, which
    itself ends in a blank line like every other book file; content lines
    unchanged at 11,996 either side, confirmed by `validate_tess.py`'s own
    count). `texts/la/paulus_orosius.historiae_adversum_paganos.tess`
    (2,362 -> 2,362 lines, unchanged).
  - Not changed: `vergil.georgics.tess` and `arrian.anabasis.tess`, and
    none of their book files.
- A defect worth a decision, found in the Ovid regeneration: the whole
  file's `ov. met. 4.767a` and `4.768` are a bracketed, sub-lettered pair
  marking a couplet the apparatus treats as a spurious interpolation
  (`[quaerit Abantiades: quaerenti protinus unus` / `narrat ... virorum]`).
  The book file has no such marking: both lines are tagged `4.768` (a
  duplicate reference) and the brackets are gone. Canonicalizing the book
  files as instructed carries this forward; the interpolation marking is
  now only in git history, not in the corpus. Recorded rather than
  fixing, since restoring it means deciding whether to keep the duplicate
  reference or renumber, which is a scholarly-apparatus call.
- Arnobius, left as found: `arnobius. adversus_nationes. 2.76` differs by
  one character between the whole file (`cur erg6, inquit`) and
  `part.2.tess` (`cur ergo, inquit`) already on main, unrelated to the
  missing-book-file work above. Not touched, per "do not alter any existing
  file in job A"; `check_whole_vs_parts.py arnobius.adversus_nationes`
  still reports 1 failing line for this reason alone.
- Verification run in the branch: `check_whole_vs_parts.py` on every work
  above: PASS for `pliny_the_elder.naturalis_historia`,
  `ovid.metamorphoses`, `paulus_orosius.historiae_adversum_paganos`;
  `arnobius.adversus_nationes` fails only on the pre-existing 2.76 line
  above (book 1 and 6 both verified present and correct by a name-agnostic
  multiset comparison script, since the checker's own regex would still
  miss a differently-named file). Full-corpus re-run: 124 passed, 13 failed
  (was 121 passed, 16 failed on main), the 3 fewer failures being exactly
  the 3 works fixed; no new failures anywhere else. `validate_tess.py` on
  every created or changed file: all report the same `[FAIL]` (space
  instead of tab between reference and text) that every file in the corpus
  already reports, confirmed by running it on an untouched sibling book
  file of each work and on the pre-change version of each changed file;
  no new class of error. CRLF/LF byte counts compared before and after for
  every changed file: unchanged (`ovid.metamorphoses.tess` 0 CRLF/12,010
  LF before and 0/12,011 after, matching the one added blank line;
  `paulus_orosius...tess` 0/2,361 both; `arnobius...part.1.tess` 0/65
  both). New files: the Arnobius book 6 file is 0 CRLF/27 LF; the Pliny
  preface file is 7 CRLF/0 LF, matching the whole file it was copied from.
- Sample changed lines, Ovid (`ov. met.`): 1.182 `"Non ego pro mundi regno`
  was `"Non ego...` (curly opening quote to straight); 1.198 `Lycaon?"` was
  `Lycaon?"` (curly closing quote to straight); 1.209 `"Ille quidem poenas`
  was `"Ille quidem...` (same). Sample changed lines, Orosius (`hist.adv.
  pag.`): 3.1.3 `seruire ? — si non` -> `seruire? si non` (space before
  the question mark and the em dash both dropped); 3.8.6 `potuisset —;` ->
  `potuisset;` (the dangling em dash before the semicolon dropped); 4.13.9
  `fugisse ?` -> `fugisse?` (space before the question mark dropped).
- Not run against production. Production steps, in order, once approved:
  1. `git pull` on production `main`.
  2. Delete the lemma cache entries for the 5 changed/new files
     (`arnobius.adversus_nationes.part.1.tess`,
     `arnobius.adversus_nationes.part.6.tess`,
     `pliny_the_elder.naturalis_historia.part.0.preface.tess`,
     `ovid.metamorphoses.tess`, `paulus_orosius.historiae_adversum_
     paganos.tess`) and rebuild: `scripts/batch_lemma_cache.py la` (all
     five are Latin).
  3. Reindex on a copy of `la_index.db`: `scripts/corpus/
     add_texts_to_index.py --replace arnobius.adversus_nationes.part.1.tess
     ovid.metamorphoses.tess paulus_orosius.historiae_adversum_paganos.tess`
     (the renamed and regenerated files) and `--add
     arnobius.adversus_nationes.part.6.tess pliny_the_elder.
     naturalis_historia.part.0.preface.tess` (the two new files) on the
     same copy, then swap the copy in for the live index.
  4. Note: the two new book files (Arnobius book 6, Pliny's preface) have
     no passage-index windows until a description batch runs for them, so
     neither will appear in Theme Search or Similar Passages until then.
  5. Rebuild the density caches for Latin (`scripts/precompute_passage_
     density.py`), because the index fingerprint changed.
  6. `python scripts/reference_search_check.py`.
  7. `touch tesseraev6_flask.wsgi`.
- Left for a later decision, not part of this operation: `vergil.georgics`
  (mojibake in the book files, mostly not diaereses) and `arrian.anabasis`
  (book files are a mixed improvement/regression, not clearly better), the
  Group C `arnobius. adversus_nationes. 2.76` one-character mismatch, and
  the `check_whole_vs_parts.py` filename-pattern bug itself, which
  under-reports how many book files already exist for any work using a
  non-numeric or lettered part label.

## 2026-09-21 One Latin u/v and i/j rule deployed (PR #451); density precompute unblocked and running
- What: PR #451 merged 8d9b25b, pulled, WSGI touched 16:45 EDT. Five
  implementations of the Latin orthographic fold, three of them named
  `normalize_latin`, replaced by `backend/latin_orthography.py`:
  `fold_latin` (lowercase, v to u, j to i) for anything compared with the
  lemma tables or the index, and `fold_latin_surface` (case kept, archaic
  word-final -om to -um) for searching printed text. The split is forced by
  the stored data: all 111,739 keys in `latin_lemmas.json` are lowercase
  with no v or j, and the table holds BOTH `diuom` (a form of deus) and
  `diuum` (a form of diuus), so folding -om before a lookup returns a
  different word rather than missing.
- Effect, measured on the corpus before the change: 1,705 function-word
  occurrences were escaping the Latin stoplist because the matcher ignored
  j, 1,691 of them `jam` for `iam`; and the distance filter kept case, so a
  capitalised line-opening word never matched the lowercase word the index
  returned.
- Checks on production, before and after the deploy, identical: "arma
  virum" lemma 367 at `max_results` 1000 and exact 21; Lucan 1 against
  Aeneid 1 returns the same 152 results, the same pairs, the same scores
  and the same top result (luc. 1.13 with verg. aen. 1.368). A j-spelled
  query, "jam satis", answers with 357 results. The classical core is
  unchanged, which is what the measurement predicted: j spellings live in
  the 325 medieval and early-modern Latin files.
- Chris applied `chmod g+w` to `cache/passage_density`,
  `cache/lexical_density` and `cache/rare_words` at about 16:16 EDT
  (ticket #108315), so the Reader's gutter can be precomputed offline for
  the first time. `scripts/precompute_passage_density.py --language la`
  started 16:38 in a tess-job scope (cap 8G, peak 5.2 GB, about 3.5 seconds
  a work, 1,719 works, log `~/tesserae-backups/jobs/density-la.log`). Greek,
  English, Coptic and Hebrew follow, one at a time. After this the first
  open of a text is instant for every work, until the next corpus change,
  which invalidates the cache by design.
- Chris asks that a new request go in a NEW ticket rather than as a reply
  to an existing one.

## 2026-09-21 Code review fixes deployed (PRs #439 to #445); Hebrew rare-words cache built
- What: the seven pull requests from the September code review merged and
  deployed in two steps. Backend first (PR #439, 24
  unreachable route handlers deleted from `backend/app.py`, about 970
  lines): pulled, WSGI touched 15:04 EDT. Then the front end as one bundle
  (PRs #441 Saved Searches dialog, #440 dialog semantics and `aria-current`,
  #443 one shared source for language display names, #445 Hebrew in the
  Corpus Browser and the Rare Words Explorer): pulled, rebuilt in a 6 GB
  tess-job scope with `keep_old_bundles.sh` save and restore,
  `index-Kz4J11UL.js`, WSGI touched 15:14 EDT, workers warmed. Scripts and
  records (#442 corpus-script safety helper, #444 `docs/OPEN_WORK.md`)
  needed no deploy step.
- Data step for #445: the Hebrew rare-words cache
  (`cache/rare_words/he.json`) was 25 bytes, because the builder had a
  branch for every language except Hebrew. The file is owned by the web
  app's account and is not writable by the deploy user, so it was
  regenerated the way the code already self-heals: the first request for
  Hebrew rare words after the deploy rebuilt it, as the web app's own user.
  25 bytes to 773,168 bytes, 3,935 words from 5,962 lemmas. The old file is
  kept at `~/tesserae-backups/notes_2026-09-21/`.
- Checks: "arma virum" lemma 367 at `max_results` 1000 and exact 21, before
  and after, unchanged; every route the deleted handlers had shadowed still
  answers (`/api/texts`, `/api/authors`, `/api/texts/hierarchy`,
  `/api/frequencies/la`, and `/api/admin/settings` answering 401 as it
  should); the served bundle carries the new strings; Hebrew lists its 39
  works; the Reader gutter is still warm; Theme Search answers in about 7
  seconds once the workers are warm.
- Note for the next deploy: `cache/rare_words/` has the same permission
  shape as `cache/passage_density` and `cache/lexical_density`, so the
  request to the system administrator should cover all three.

## 2026-09-21 Corpus: 87 damaged lines repaired in book files (PR #435, run 07:09 EDT)
- What: `scripts/corpus/repair_part_file_defects_2026-09-21.py` (new, dry run
  by default) takes the whole file's own line as the correction for six
  defects the 2026-09-21 whole-vs-book comparison found: Pliny's seven book
  files, 77 lines whose Greek was mojibake (UTF-8 read as Latin-1);
  Claudian's De Consulatu Stilichonis 2 lines and De Raptu Proserpinae 3,
  same corruption; `cicero.philippicae.part.7.tess` line 1 missing its
  opening `<` (so `cic. phil. 7.1` was never indexed from that file, the
  same class as the Isocrates doubled bracket of 2026-09-20); three
  references in Orosius' book files 1 and 3 with the author prefix doubled
  (`paulus_paulus_orosius.`); and `galen.natural_faculties.part.1.tess`
  missing its first line. 14 files, 87 lines. Verified in the branch:
  `check_whole_vs_parts.py` now passes Cicero, both Claudians and Galen;
  Pliny and Orosius still fail for the two reasons left alone on purpose
  (Pliny's preface has no book file; Orosius' two copies differ in em dashes
  and spacing before punctuation).
- Left alone deliberately, needing a decision, written up in
  `research/corpus/WHOLE_VS_PARTS_2026-09-21.md` (local): twelve works whose
  book files omit whole sections (the Vulgate's second psalter, 2,554 lines;
  Arnobius books 1 and 6; Paulinus 2a and 2b; the prefaces of Gellius,
  Priscian, Sedulius, Augustine twice and Pliny), and the works where the
  two copies are simply different transcriptions (Ovid's curly quotes, the
  Georgics' diaereses, Arrian's stray section numbers).
- Store impact: the three Orosius references change, so they are added to
  `scripts/corpus/apply_whole_vs_parts_refs.py`'s targets (the four targets
  applied on 2026-09-20 report 0 on a re-run; the script is idempotent).
  Everything else is a text change inside a line that keeps its reference,
  except the two lines that appear for the first time in a book file
  (`cic. phil. 7.1`, `gal. nat.fac. 1.1`), which the reindex adds.
- Production steps, in order, each inside a tess-job scope:
  1. `git pull` on production `main`.
  2. Delete the lemma cache entries for the 14 changed files (the helper in
     the 2026-09-20 entry below, with this file list), then
     `scripts/batch_lemma_cache.py la` and `... grc`.
  3. `scripts/corpus/add_texts_to_index.py --replace` for the 13 Latin files
     on a copy of `la_index.db`, and for
     `galen.natural_faculties.part.1.tess` on a copy of `grc_index.db`, then
     swap each with a stamped `.bak-part_defects-<STAMP>`.
  4. `scripts/corpus/apply_whole_vs_parts_refs.py --root .` (dry run: expect
     0 for the 2026-09-20 targets and 3 references for Orosius), then
     `--apply --tag part_defects-<STAMP>`.
  5. Reference test: "arma virum" lemma 367 at `max_results` 1000, exact 21.
     Spot checks: `plin. nat. 1.24` serves Greek, not mojibake;
     `cic. phil. 7.1` and `gal. nat.fac. 1.1` are served by their book files.
  6. `touch tesseraev6_flask.wsgi`, then warm the three workers.
  7. Note: the passage index keeps the old window TEXT for the repaired
     Pliny and Claudian lines until windows are rebuilt for those works, and
     the two newly indexed lines get windows at the next description batch.

- Done 2026-09-21 07:09 EDT, by the main session, in the order above, each
  step in a tess-job scope (caps 8 GB): PR #435 merged b7ef13e and pulled;
  14 lemma cache entries deleted and rebuilt (`la`, then `grc`); reindex on
  copies then swapped, backup tag `part_defects-20260921-070756` (Orosius
  book 1 289 lines and book 3 299 lines unchanged in count, Philippic 7 now
  27 lines and 1,696 postings against 26 and 1,617, Galen book 1 now 17
  lines and 4,168 postings against 16 and 4,104; `lemma_doc_freq` rebuilt
  for both languages); remap dry run reported 0 for the inverted index (the
  reindex had already done it) and 3 references, 4 windows and 4
  descriptions for Orosius, applied under the same tag, and a second dry run
  reported 0 everywhere; WSGI touched and the three workers warmed.
- Checks on production: "arma virum" lemma 367 at `max_results` 1000 and
  exact 21, unchanged; `plin. nat. 1.24` serves `ὀρνιθογονίαν` instead of
  mojibake; `cicero.philippicae.part.7.tess` serves 27 lines starting at
  `cic. phil. 7.1`; `galen.natural_faculties.part.1.tess` serves 17 lines
  starting at `gal. nat.fac. 1.1`; no doubled `paulus_paulus_orosius`
  reference is left in the Orosius book files.
- Correction made during review, before the merge: the first version of the
  repair script read the files in Python's text mode, which silently turned
  Windows line endings into Unix ones and so rewrote every line of five
  files (458, 519, 261, 461 and 26 lines) although only 10 to 23 in each
  were being repaired. The script now reads and writes with `newline=''`, and
  a repaired line keeps its own ending; the committed diff is exactly the 87
  repaired lines plus the one inserted Galen line.
## 2026-09-20 Corpus: four works' whole files and book files made consistent; byte-order marks removed from four files (PR #432, run 2026-09-21 00:20)
- What changed in each `.tess` file (already committed; text unchanged
  except where noted):
  - `texts/grc/isocrates.letters.part.2.tess` (24 lines) and `.part.3.tess`
    (6 lines): every line's tag carried a doubled leading bracket,
    `<<isoc. letters 2.1>` instead of `<isoc. letters 2.1>`. Fixed by
    stripping the extra `<` from every line.
  - `texts/grc/hyperides.speeches.tess` (152 lines, the WHOLE file only —
    its six part files were already correct): tags read `<hyp. 1.1>`
    instead of `<hyp. speeches. 1.1>`, the form every part file uses.
    Fixed by inserting `speeches. ` after `hyp. ` in every tag.
  - `texts/grc/dionysius_halicarnassensis.antiquitates_romanae.part.12.books_12-20.tess`:
    was missing line `<dion_hal. ant_rom 16.1.0>` (present in the whole
    file at line 4076). Fixed by inserting that line verbatim before the
    part file's `16.1.2` line (16.1.1 does not exist in either file).
  - `texts/la/couplet_et_alii.confucius_sinarum_philosophus.part.1.tess`
    (10 lines): tags read `<Couplet. Confucius. X>` instead of the
    `Couplet et alii. Confucius.` prefix the whole file and parts 2-3 use.
    Fixed by replacing the prefix on all 10 lines.
  - NOT changed, contrary to the initial brief: the whole Confucius file's
    `proem. decl. titulus` line, believed missing from part.2. It is
    already the first line of `part.2.tess` in this checkout (confirmed
    byte-for-byte against the whole file); inserting it again would have
    duplicated it. The refs-as-multisets check
    (`scripts/corpus/check_whole_vs_parts.py`) confirms the whole file and
    its three parts already match exactly once part.1's tag prefix is
    fixed — no insert needed for Confucius. Separately, PRODUCTION's
    passage index (`window_texts.db`, read-only inspection 2026-09-20) IS
    missing this line for `couplet_et_alii.confucius_sinarum_philosophus.part.2`
    (234 rows there against 235 expected): that is a stale-index symptom,
    not a `.tess`-file problem, and the reindex step below (lemma cache +
    `add_texts_to_index.py --replace`) resolves it with no separate fix.
- Byte-order marks (found by the main session while reviewing this PR):
  four text files began with a UTF-8 byte-order mark, so their first line
  did not parse as a tagged line and was missing from the inverted index
  and the passage index (production, read-only: Aretaeus 17 of 18 lines
  indexed, Confucius part 2 234 of 235, Macrobius fragment 11 of 12,
  Ovid Ibis 641 of 642; the first ref of each absent from `window_texts`).
  The mark is removed from `grc/aretaeus.signorum_acutorum_morbum.tess`,
  `la/couplet_et_alii.confucius_sinarum_philosophus.part.2.tess`,
  `la/macrobius.fragment.tess` and `la/ovid.ibis.tess` (text otherwise
  unchanged). This is also why the brief said Confucius part 2 lacked its
  first line: it was there, hidden behind the mark. Those four files join
  the lemma-cache and reindex lists below; their first lines get passage
  windows at the next description batch.
- Follow-ups, not done here: (1) Confucius part 2 has 40 non-blank
  lines without a tag (headings and paragraph continuations), which the
  parser drops; the file needs re-segmenting. (2) The checker finds 20
  more works whose whole file and book files disagree in content or
  refs (list in the PR body and in the checker's output); each needs a
  look before a fix, since some are edition differences.
- Verification:
  - `scripts/corpus/check_whole_vs_parts.py` (new): PASS on all four
    named works after the fix. Run against the whole corpus: 137
    whole+parts groups found under `texts/`, of which 15 have book files
    but no matching whole file (a separate, pre-existing, out-of-scope
    situation — e.g. `anthologia_graeca`, the `libanius` split files,
    `spenser.faerie_queene`) and are skipped; of the remaining **137**
    that DO have a matching whole file, **117 pass, 20 fail**. The 122 of
    the first survey counted only book files named exactly `.part.N.tess`;
    this checker also accepts `.part.N.<suffix>.tess` (the King James
    collections' books, the Vulgate's, Pindar's, Suetonius' lives,
    Dionysius' part 12), which adds the 15. The 20 failures are
    pre-existing whole-vs-parts mismatches
    OUTSIDE this batch's scope (not requested, not touched): `apuleius.
    metamorphoses`, `arnobius.adversus_nationes`, `arrian.anabasis`,
    `augustine.de_doctrina_christiana`, `augustine.de_trinitate`,
    `cicero.philippicae`, `claudian.de_consulatu_stilichonis`, `claudian.
    de_raptu_proserpinae`, `dracontius.romulea`, `galen.natural_faculties`,
    `gellius.attic_nights`, `jerome.vulgate`, `ovid.metamorphoses`,
    `paulinus_of_aquileia.carmina`, `paulus_orosius.
    historiae_adversum_paganos`, `pliny_the_elder.naturalis_historia`,
    `priscian.carmen_in_laudem_Anastasii_imperatoris`, `prudentius.
    peristephanon`, `sedulius.carmen_paschale`, `vergil.georgics`. Flagged
    for a follow-up batch, not fixed here. Alcuin's and Theodulf's
    `carmina` and Cicero's Verrines (`cicero.divinatio_in_c_verrem`) PASS,
    as expected going in.
  - `scripts/corpus/validate_tess.py` run on all six changed/touched
    files, before and after the edit: all six FAIL both before and after,
    for a PRE-EXISTING reason unrelated to this fix — most of the corpus's
    Greek/Latin `.tess` files (these six included) separate the tag from
    the text with a literal space, not the tab `validate_tess.py`
    requires, and the Confucius files additionally mix tabs and spaces
    line to line. Edit introduced no new validator failures (same failure
    shape and count before/after on every file); the space-delimiter issue
    itself is out of scope for this task (never listed as something to
    change) and is noted here for a possible separate cleanup.
  - Store inspection (production, read-only, 2026-09-20) and the counts a
    dry run of the new remap script reports against a COPY of these
    stores (`~/tesserae-backups/whole_vs_parts_2026-09-20/test/`, built
    from full copies of `grc_index.db` 2.5G and `la_index.db` 1.9G, both
    under the 3G cutoff for a fixture instead, plus `window_texts.db`
    2.9G and a `descriptions.jsonl` subset for the four affected works,
    and the `grc.db`/`la.db` reuse tables):
    - `grc_index.db` `lines`/`postings`: isocrates part.2/part.3 refs are
      stored WITH the doubled bracket baked in, e.g. `<isoc. letters 2.1`
      (leading `<`, no trailing `>`) — 30 `lines` rows, matching
      `postings` rows keyed the same way. `hyperides.speeches` (whole
      only) stored as `hyp. 1.1` etc — 152 `lines` rows. Dry run: 182
      `lines` refs, 8,428 `postings` rows (182 distinct refs) to remap.
    - `la_index.db`: `couplet_et_alii...part.1` stored as `Couplet.
      Confucius. X` — 10 `lines` rows. Dry run: 10 `lines` refs, 795
      `postings` rows to remap.
    - `window_texts.db`: `lines` table 192 refs to remap (182 grc + 10
      la); `window_texts` table 40 of 40 rows for these four works need
      `ref_start`/`ref_end` remapped.
    - `descriptions.jsonl`: 40 of 40 records for these four works need
      `ref_start`/`ref_end` remapped.
    - `cache/reuse_pairs/`: isocrates part.2/part.3 and confucius part.1
      have ZERO rows in the reuse tables (too short to register a reuse
      candidate) — no remap needed for those three. `hyperides.speeches`
      (whole) has 68 `pairs` rows (13 as `work_a`, 55 as `work_b`) and 38
      `line_counts` rows under the old `hyp. LOCUS` naming — these DO need
      the rename and the new script includes them (schema and location
      from `backend/reuse_table.py`: `cache/reuse_pairs/<lang>.db`,
      tables `pairs(work_a, line_a_ref, work_b, line_b_ref, ...)` and
      `line_counts(work, line_ref, n_works)`). No collisions found.
    - Cached fusion/theme-search JSON results: 0 name any of the four
      touched files.
  - `scripts/corpus/apply_whole_vs_parts_refs.py` (new) --apply run
    against the same test copy reproduced every count above with no
    errors; a re-run afterward (dry run) reported 0 remaining in every
    store, confirming the remap is idempotent and complete. Backups
    written as `<file>.bak-test1` beside each store in the test copy.
  - `tests/test_apply_whole_vs_parts_refs.py` (new): 3 passed (dry run
    makes no changes; apply remaps every store correctly and leaves
    unrelated/already-correct rows alone; a collision refuses the apply
    with zero writes), run via
    `~/bin/tess-job --fg corpusfix-tests 4 venv/bin/python -m pytest -q
    tests/test_apply_whole_vs_parts_refs.py`.
  - The live reference-test run ("arma virum") is NOT run as part of this
    change: no backend or indexing code changed, and the store-side fix is
    a prepared, not-yet-applied script (below). It is the last step of the
    production sequence.
- Production steps, in order (NOT run by this session; production-touching
  steps stay with the main session per project policy):
  1. `git pull` on `main` (brings in the four corrected `.tess` files, the
     two new scripts, and this doc).
  2. Delete the six changed/added files' stale lemma cache entries (the
     cache key is a hash of the FILENAME, not the content, so the paths
     below are exact and stable regardless of the edit):
     ```
     cd /var/www/tesseraev6_flask
     venv/bin/python -c "
     from backend.lemma_cache import get_cache_path
     import os
     files = [
         ('grc', 'isocrates.letters.part.2.tess'),
         ('grc', 'isocrates.letters.part.3.tess'),
         ('grc', 'hyperides.speeches.tess'),
         ('grc', 'dionysius_halicarnassensis.antiquitates_romanae.part.12.books_12-20.tess'),
         ('la', 'couplet_et_alii.confucius_sinarum_philosophus.part.1.tess'),
         ('la', 'couplet_et_alii.confucius_sinarum_philosophus.tess'),
         ('grc', 'aretaeus.signorum_acutorum_morbum.tess'),
         ('la', 'couplet_et_alii.confucius_sinarum_philosophus.part.2.tess'),
         ('la', 'macrobius.fragment.tess'),
         ('la', 'ovid.ibis.tess'),
     ]
     for lang, fn in files:
         p = get_cache_path(fn, lang)
         if os.path.exists(p):
             os.remove(p)
             print('removed', p)
         else:
             print('not cached:', p)
     "
     ```
  3. Rebuild the lemma cache for the two affected languages, one at a
     time, each in its own capped scope:
     ```
     systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 \
       venv/bin/python scripts/batch_lemma_cache.py grc
     systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0 \
       venv/bin/python scripts/batch_lemma_cache.py la
     ```
     (peak under 4G per the standing memory note; 8G cap per that note's
     convention).
  4. Reindex the six files on a COPY of each inverted index, then swap:
     ```
     cp data/inverted_index/grc_index.db data/inverted_index/grc_index.db.new
     venv/bin/python scripts/corpus/add_texts_to_index.py \
       --db data/inverted_index/grc_index.db.new --language grc \
       --cache-dir cache/lemmas \
       --replace isocrates.letters.part.2.tess isocrates.letters.part.3.tess \
                 hyperides.speeches.tess \
                 dionysius_halicarnassensis.antiquitates_romanae.part.12.books_12-20.tess \
                 aretaeus.signorum_acutorum_morbum.tess
     mv data/inverted_index/grc_index.db data/inverted_index/grc_index.db.bak-whole_vs_parts-<STAMP>
     mv data/inverted_index/grc_index.db.new data/inverted_index/grc_index.db

     cp data/inverted_index/la_index.db data/inverted_index/la_index.db.new
     venv/bin/python scripts/corpus/add_texts_to_index.py \
       --db data/inverted_index/la_index.db.new --language la \
       --cache-dir cache/lemmas \
       --replace couplet_et_alii.confucius_sinarum_philosophus.part.1.tess \
                 couplet_et_alii.confucius_sinarum_philosophus.tess \
                 couplet_et_alii.confucius_sinarum_philosophus.part.2.tess \
                 macrobius.fragment.tess ovid.ibis.tess
     mv data/inverted_index/la_index.db data/inverted_index/la_index.db.bak-whole_vs_parts-<STAMP>
     mv data/inverted_index/la_index.db.new data/inverted_index/la_index.db
     ```
     This reindex alone brings `lines`/`postings` to the new refs for
     these six files AND fixes the stale-index Confucius `titulus` row
     noted above; step 5 below is then a no-op for the inverted index (it
     touches the passage index and reuse tables only, which
     `add_texts_to_index.py` does not) but is still needed for those.
  5. Run the new remap script for the passage index and reuse tables,
     dry run first:
     ```
     systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 \
       venv/bin/python scripts/corpus/apply_whole_vs_parts_refs.py --root .
     ```
     then, once the dry-run counts match this doc's inspection above:
     ```
     systemd-run --user --scope -p MemoryMax=4G -p MemorySwapMax=0 \
       venv/bin/python scripts/corpus/apply_whole_vs_parts_refs.py --root . \
       --apply --tag whole_vs_parts-<STAMP>
     ```
  6. Verify: `tests/search_reference_tests.md`'s "arma virum" checks (367
     distinct loci for the lemma search, 21 for the exact search — see
     the Conventions note above) plus a line search for one of the four
     works (e.g. Hyperides, `hyp. speeches. 1.1`) to confirm the new refs
     resolve.
  7. `touch tesseraev6_flask.wsgi` so the three Apache workers reopen the
     swapped index files.
  8. The two inserted lines (Dionysius' 16.1.0, and none for Confucius —
     see above) get no passage-index windows/descriptions until the next
     description batch runs (`scripts/corpus/describe_windows.py` or
     equivalent); they are searchable immediately via lemma/exact search
     once steps 3-4 finish, just not yet as Similar-Passages or
     Theme-Search windows.
- Done 2026-09-21 00:20 EDT, by the main session, in the order above,
  every step inside a tess-job scope (caps 8 GB): PR #432 merged 50e32c6
  and pulled; ten lemma cache entries deleted and rebuilt (`grc` then
  `la`); reindex on copies then swapped (Greek: Isocrates parts 2 and 3
  24 and 6 lines, Hyperides 152, Dionysius part 12 369 lines (was 368),
  Aretaeus 18 (was 17); Latin: Confucius part 1 10 lines, part 2 235 (was
  234), whole 255, Macrobius fragment 12 (was 11), Ovid Ibis 642 (was
  641); `lemma_doc_freq` rebuilt for both); remap dry run matched the
  inspection exactly (inverted index 0 left after the reindex; passage
  index 192 line refs, 40 of 40 windows, 40 of 40 descriptions; Greek
  reuse table 68 pair rows and 38 line counts; Latin reuse 0; fusion
  cache 0), then applied with backup tag `whole_vs_parts-20260921-001840`;
  a second dry run reported 0 everywhere; WSGI touched and the three
  workers warmed.
- Backups: `grc_index.db.bak-whole_vs_parts-20260921-001622`,
  `la_index.db.bak-whole_vs_parts-20260921-001622`, and the remap
  script's `.bak-whole_vs_parts-20260921-001840` copies of
  `window_texts.db`, `descriptions.jsonl` and `cache/reuse_pairs/grc.db`.
- Checks: reference searches unchanged before and after ("arma virum"
  lemma 367 at `max_results` 1000, exact 21; note that at the 500 cap the
  lemma search reports 323 because the cap applies before the whole-work
  and per-book copies are merged, so the reference figure must be taken
  at 1000); `/api/text` now serves `hyp. speeches. 1.1` as the first
  Hyperides line, `isoc. letters 2.1` without the bracket, the first line
  of Aretaeus, Confucius part 2, Macrobius' fragment and the Ibis, and
  Dionysius 16.1.0.
## 2026-09-20 Reader: server-side book lookup, Read tab restart, marking, legend, Help, translators (PR #430) deployed
- What: PR #430 merged a103ede, pulled on production, bundle rebuilt (`npm run
  build` from the repo root inside a 6 GB tess-job scope,
  `scripts/keep_old_bundles.sh save` before and `restore` after), WSGI
  touched, three workers warmed. Backend: new route
  `GET /api/text/<work>/book-for?ref=` (which book file holds a line,
  full reference first, locus alone as the fallback; part files read once
  per worker). Front end: the Read tab restarts the Reader; the Reader asks
  the route before opening a book; Verbal Parallels marks Latin words
  across u/v and i/j; legend order and the dashed "possible echo" box;
  Help (quotation boxes, navigator, translation note); Sources page
  Translations block.
- Checks: `book-for` on production for `cicero.divinatio_in_c_verrem.tess`
  ref `cic. ver. 2.2.1` -> part 3, `hyperides.speeches.tess` ref `hyp. 2.1` ->
  part 2; the served bundle carries the new strings.
- Done 2026-09-20 23:50 EDT.

## 2026-09-20 Reader: books one at a time, floating navigator, map arrival (PR #427) deployed
- What: PR #427 merged ba50a79, pulled on production, bundle rebuilt
  (`npm run build` from the repo root inside a 6 GB tess-job scope,
  `scripts/keep_old_bundles.sh save` before and `restore` after, 39 older
  bundles kept), WSGI touched 22:58 EDT, three workers warmed with Theme
  Search requests (26 s each cold). Front-end only: a whole-file work that
  also has `.part.N` files opens the book holding the requested line; a
  fixed navigator (Back to top, To the end, previous and next book); the
  gutter key explains the numbered quotation boxes; the Theme Similarity
  Map's Reader links carry `map=<author>` and the Reader links back to the
  map tab (the old `q=connections map: X` link ran a Theme Search).
- Checks: served bundle index-B32cJMMc.js carries the new strings; Theme
  Search answers 25 rows with reader and lexical boost applied on all
  three workers.
- Corpus follow-ups found while verifying the book rule (whole files whose
  numbering does not match their parts: Alcuin and Theodulf carmina,
  Cicero Verrines whole file, Confucius Sinarum Philosophus; label
  differences in Hyperides and Isocrates; Dionysius
  `part.12.books_12-20.tess` naming) are listed for a corpus batch.
- Done 2026-09-20 22:58 EDT.

## 2026-09-20 Silius Italicus Punica: A. S. Kline translation added for books 9-17 and the gaps of 1-8
- What: `data/translations/la__silius_italicus.punica.json` rebuilt to add
  A. S. Kline's Poetry in Translation rendering of Punica (fetched from
  https://www.poetryintranslation.com/PITBR/Latin/ItalicusPunicahome.php,
  book pages ItalicusPunicaBKI.php through BKXVII.php, raw HTML kept at
  `~/tesserae-backups/kline_silius_2026-09-20/raw/`) alongside J. D. Duff's
  existing 1927 public-domain Loeb translation of books 1-8. Kline's
  section headings ("Book IX:1-38 ...") give the exact Latin line range
  each section translates; every such range was parsed and mapped to the
  matching `sil. B.L` refs.
- Source: 17 book pages, one fetch each, 2 s apart, polite User-Agent.
  Kline's copyright note on every page: "Translated by A. S. Kline (c)
  Copyright 2018 All Rights Reserved"; site-wide licence statement: "This
  work may be freely reproduced, stored and transmitted, electronically or
  otherwise, for any non-commercial purpose."
- Counts: 233 new Kline units added (210 Duff units kept unchanged, 443
  total). All 6,436 `sil. 9.*`-`sil. 17.*` refs in
  `texts/la/silius_italicus.punica.tess` mapped (coverage_books_9_17 =
  1.0); 234 gap refs in books 1-8 (8.130-157, 8.224, 8.513-563, 8.671-676
  and smaller gaps in books 1, 3-7) mapped to Kline sections. Combined
  `n_translated` 12,193 against `n_tess_refs` 12,192 (coverage computed as
  1.0001: one pre-existing Duff-mapped ref, `sil. 8.224a`, a bare
  closing-quote line, was never counted in `n_tess_refs`'s digit-only
  convention -- a pre-existing quirk in the original file, not introduced
  here). Name check (proper-name survival, `scripts/translations/proper_names.py`,
  same method as the file's own stored `name_check_hit_rate`): 100 random
  Kline units, hit rate 0.98 (n=100 tested) -- higher than the Loeb's
  0.74-0.81 range because each Kline unit's line range is stated directly
  by the translator rather than reconstructed from running headers.
- Licence: A. S. Kline's terms permit free non-commercial reproduction,
  storage, transmission, distribution and display; forbid re-licensing
  under Creative Commons. Decision 2026-09-20: acceptable for this free,
  non-commercial site, on the condition that attribution is shown on every
  display, the licence text travels with the data (`sources[1].license` and
  `.copyright` in the JSON), and the file is excluded from any future
  Creative Commons-licensed data release of Tesserae's aligned
  translations.
- Backend: `backend/translations.py` `for_passage` now reads a file's
  `unit_sources` (per-unit index into `sources`) when present and credits
  only the sources behind the units actually served, instead of always
  crediting `sources[0]`; unchanged for files without `unit_sources`.
  Tests: `tests/test_translations_unit_sources.py`.
- Production steps (after the PR merges): copy
  `data/translations/la__silius_italicus.punica.json` from this operation
  into production's `data/translations/` (this directory is not tracked in
  git, per `.gitignore`, and is deployed by file copy, not `git pull`). The
  app reads translation files at request time with no server reload
  needed; the on-disk copy also feeds `available()`'s per-language listing,
  cached against the directory's mtimes, so it need not be warmed either.
- Done 2026-09-20 23:07 EDT: PR #428 merged 1efa645 (with a follow-up
  commit: the licence returned follows the words served, and a
  `unit_sources` list not parallel to the units is ignored), production
  pulled, the old file backed up to
  `~/tesserae-backups/kline_silius_2026-09-20/la__silius_italicus.punica.json.before_kline_20260920_230733`
  (453,113 bytes), the new file (993,089 bytes) copied beside it and
  renamed over it, bundle rebuilt for the Reader wording
  (index-Cte8wXfH.js, keep_old_bundles save/restore), WSGI touched.
  Checks through `/api/passages/translation`: sil. 9.1, 8.140 and 17.654
  answer with Kline's text, "A. S. Kline (Poetry in Translation),
  non-commercial use only" and Kline's licence; sil. 1.1 answers with
  Duff (1927) as before.

## 2026-09-20 Theme Search reader depth 300 deployed (PR #424), then held at 100 while its timeout is fixed
- What: PR #424 merged ed0657d1, pulled on production, WSGI reloaded 15:16
  EDT: the reader re-scores the whole composed list (300 rows) instead of
  its first hundred.
- Incident: for nine minutes every Theme Search answered with the reader
  NOT applied (`reader: {applied: false}`), because the reader client's
  fixed 6 s timeout cut off the 300-row call just before the service
  answered (measured on production: 100 rows 2.1 s, 300 rows 6.2 s); the
  reader service logged broken pipes. Stopgap at 15:19: `THEME_READER_K=100`
  added to production's `.env` and WSGI reloaded; the reader applied again
  (2.2 s). Fix: PR #425 (client timeout = max(6, 0.04 x rows)); its deploy
  removes the `.env` line.
- 15:25 EDT: PR #425 merged a57803b6, pulled, `THEME_READER_K=100` removed
  from `.env`, WSGI reloaded, the three workers warmed. Checks: the reader
  applies at 300 rows (5.9 s of a 7 s request); on "a wife or child
  recognizes someone long thought dead or lost" the Odyssey is on the page
  at row 14 (23.1, Eurycleia wakes Penelope with the news), and on "a
  storm at sea batters ships and terrifies the crew" at rows 21 and 23
  (9.67, 12.409). Neither query returned the Odyssey before today.
- Also learned: after every reload the first request on each of the three
  Apache workers loads the passage index (18 to 30 s); warm requests take
  about 3 s. Warm the three workers with three requests after a reload
  before judging latency.
- Done 2026-09-20 15:16 (deploy), 15:19 (stopgap) EDT (main session).

## 2026-09-20 Theme Search lexical boost deployed (PR #423); word index rebuilt
- What: PR #423 merged 599fcad5 and pulled on production 15:10 EDT. The
  word index `data/passage_index/desc_fts.sqlite` was rebuilt with the
  final script (30 s, 619,280 descriptions, 678 MB) so it carries the
  source file's size and mtime, which the app now checks along with the
  description count before using it. Bundle rebuilt in the launcher (one
  Help sentence), old bundles kept, WSGI reloaded 15:11.
- Check: /api/passages/theme-search answers with `lexical_boost: true`;
  the recognition query's page is unchanged in its first works (Spenser,
  Thebaid, Heracles) and the Odyssey is still off the 25-row page at the
  reader depth of 100 rows (PR #424 deepens the reader).
- Standing rule: rebuild the word index after every change to
  descriptions.jsonl, with `scripts/build_desc_fts.py`, then reload;
  a stale index is refused and logged, and Theme Search runs without the
  boost until it is rebuilt.
- Method record: docs/DECISIONS.md, 2026-09-20 (four experiments, the
  harness correction, the adopted boost).
- Done 2026-09-20 15:10 to 15:11 EDT (main session).

## 2026-09-19 Reader: passage-density cache precompute script (planned, not yet run)

- What (code, this PR; not yet run against any real index): `scripts/
  precompute_passage_density.py` walks every work in the passage index and
  calls `backend.passage_index.connection_density(work, scale='fine')` --
  the identical function `GET /api/passages/density` calls for the Reader's
  violet gutter mark -- for each one, so its on-disk cache
  (`cache/passage_density/<fingerprint>.<work>.fine.json`) is already warm
  before a reader ever opens that work. With `--lexical` it does the same
  for `backend.lexical_density.line_density()` and its cache under
  `cache/lexical_density/`. Neither computation is reimplemented; the
  script imports and calls the same functions the endpoints call and lets
  them write their own cache files in their own format.
  The work list is read off the loaded index's own per-window records
  (the raw `work` field, e.g. `vergil.aeneid.part.6`), not
  `passage_index.works_for_language()`, because that function collapses a
  multi-part work's parts into one base id and the Reader requests density
  by the exact part filename it has open.
  Flags: `--language la|grc|en|cop|he|all` (default all, one language at a
  time is the intended real usage), `--only-missing` (default; a work
  already cached is skipped without calling the compute function again),
  `--force` (recompute and overwrite), `--limit N` (testing), `--dry-run`
  (list the works that would be processed, computing nothing), `--lexical`
  (also warm the lexical-density cache for the same works).
- Why now: the gutter's cache fills lazily, one reader at a time, and the
  first person to open a large work pays for both the passage index's
  ~1.2 GB load and a matrix multiply of that work's windows against the
  whole corpus -- about 100 seconds and 1.4 GB of resident memory on a
  production Apache worker that is also trying to answer other requests
  during that window.
  See `backend/passage_index.py`'s `connection_density()` docstring and
  comments for the load/compute cost breakdown this script exists to
  front-run.
- Verified without computing: `tests/test_precompute_passage_density.py`
  (16 tests, argument handling and the skip-when-cached / force logic
  against a monkeypatched compute function and a temporary cache
  directory, no real index touched) and a real `--dry-run --limit 3
  --language la` smoke run against this worktree's actual passage index
  (619,034 windows, 1,819 Latin works), inside `systemd-run --user --scope
  -p MemoryMax=4G -p MemorySwapMax=0` as a precaution: exit 0, printed
  three work ids (`abelard.epistolae`, `abelard.historia_calamitatum`,
  `adamnan.de_locis_santis`) each marked "missing", wrote nothing to
  `cache/passage_density/` (index enumeration alone peaked at 2.85 GB
  resident; no per-work computation ran).
- Run (planned, not yet executed): one language at a time, per the standing
  memory rules --
  `systemd-run --user --scope -p MemoryMax=8G -p MemorySwapMax=0
  venv/bin/python scripts/precompute_passage_density.py --language la`
  (repeat per language; add `--lexical` to also warm the red-mark cache).
  The 8G cap is a starting estimate from the code comments' own "100s,
  1.4 GB" figure for a single large work, not a measured whole-run peak;
  measure the actual peak on the first real run before reusing the cap for
  the remaining languages.

## 2026-09-19 Corpus: Eugippius duplicate retired, Ennodius Book 2 resegmented (batch 3)
- What (code, this PR; not yet run on production): `research/corpus/
  ENNODIUS_EUGIPPIUS_COMPARISON_2026-09-19.md` examined the Eugippius and
  Ennodius pairs the batch 2 source document had left unretired. Approved
  both operations on 2026-09-19.
  1. **Eugippius**: `eugippius.excerpta_ex_operibus_augustini.tess`
     (correctly spelled filename, 1,218 lines, 192,995 words; interleaves
     386 capitula summaries with full excerpt text for only 208 of 390
     excerpts) is retired. `eugippius.exerpta_ex_operibus_augustini.tess`
     (misspelled filename, missing the first "c", 391 lines, 228,811 words)
     is kept: the only file with complete wording for all 390 excerpts. Its
     id is not renamed (would touch every index and the passage windows);
     its displayed title is corrected in code instead (see below). Before
     retiring, checked for any excerpt with full text only in the retired
     file: the source document flagged one apparent case (excerpt "198a"),
     re-verified here and found to exist in the kept file too, under an
     OCR-garbled tag (`19sa`, misread of "198a"), 96.1% six-word chunk
     containment; a full sweep of every line in the retired file found no
     other candidate. No excerpt's full text exists only in the retired
     file.
  2. **Ennodius**: `magnus_felix_ennodius.carmina.tess` (173 lines, one
     whole poem per line: 21 for Book 1, duplicating `ennodius.carmina.tess`
     at proper verse granularity for 19 of 21 poems; 152 for Book 2, unique
     to this file) is retired outright and replaced by
     `magnus_felix_ennodius.carmina_2.tess` (932 lines, one verse per line,
     Book 2 only; Book 1 dropped since `ennodius.carmina.tess` already
     covers it). The new file is built directly from the source XML the
     retired file's own provenance record names
     (`stoa0114a.stoa003.opp-lat1.xml`, OpenGreekAndLatin/csel-dev, Hartel's
     1882 CSEL 6 edition in EpiDoc TEI with one `<l n="...">` per verse and
     apparatus segregated into `<note>` elements), fetched directly from
     GitHub, not guessed or inferred from OCR line breaks. An OCR-based
     route (a lineated 1882 Google Books scan of the same edition,
     archive.org id `magnifelicisenn00ennogoog`) was tried first and
     abandoned after a validation check caught silent, cascading
     misalignment from a single unfiltered running-header fragment; the
     clean XML source was used instead once found. Verified poem-by-poem
     (normalized word match) against the retired file: 151 of 152 poems
     match exactly; the one apparent exception (poem 150) is an
     embedded-title artifact in the source XML, resolved by stripping the
     title to match the corpus's no-embedded-titles convention. Two
     pre-existing source-XML defects were found and corrected while
     building the new file: poem 107's 8 verses were entirely missing from
     the retired whole-poem file (recovered here) and poem 93 carried a
     misencoded apparatus line as a second "verse" (dropped here). Book 1
     of the retired file held two prose items (slots 1.6, 1.7) not
     duplicated anywhere else in the corpus, flagged in an earlier pass of
     this PR and now preserved (see "Part D" below) rather than dropped.
  See `~/tesserae-backups/retired_duplicates_2026-09-19b/README.md` for the
  full verification detail on both files.
- Registries edited:
  - `data/text_genres.csv`: removed the Eugippius retired file's row and
    the Ennodius whole-poem file's row; added a row for
    `magnus_felix_ennodius.carmina_2.tess` (era Late Antique, meter
    `unknown` matching `ennodius.carmina.tess`'s own row, not `prose`; the
    retired file's row had been auto-classified prose only because its
    whole-poem lines exceeded the classifier's median-line-length cutoff).
  - `backend/text_sources.json`: removed the "Eugippius" / "Excerpta ex
    Operibus Augustini" entry sourced from Open Greek and Latin / CSEL
    (the retired file's own citation); corrected the kept file's entry,
    previously spelled "Exerpta ex Operibus Augustini", to read "Excerpta
    ex Operibus Augustini". The "Magnus Felix Ennodius" / "Carmina" entry
    is unchanged: it is a flat author/work citation that remains accurate
    for the new file (same author, same source edition).
  - `backend/text_provenance.json`: removed the
    `eugippius.excerpta_ex_operibus_augustini` entry and the
    `magnus_felix_ennodius.carmina` entry; added
    `magnus_felix_ennodius.carmina_2` (same source XML, title "Carmina,
    Book 2").
  - `backend/author_dates.json`: not touched for either file. Eugippius's
    and Magnus Felix Ennodius's entries are author-level, used by other
    files that remain.
  - `backend/utils.py` `DISPLAY_NAMES`: added
    `'exerpta_ex_operibus_augustini': 'Excerpta ex Operibus Augustini'` so
    the kept Eugippius file's title displays correctly everywhere despite
    its misspelled id; the id itself is not renamed (noted here for a
    future rename operation).
- Checks run without a server (this PR, before merge):
  `python scripts/corpus/validate_tess.py` on the kept Eugippius file: FAIL
  on the tab-delimited `<ref>\ttext` check, the same pre-existing legacy
  space-delimited condition documented for other files in the 2026-09-19
  batch 2 entry above (this PR does not modify the kept file's content).
  On the new `magnus_felix_ennodius.carmina_2.tess`: FAIL on one
  non-monotonic-ref warning, `<...107.8> -> <...107.ep>`, a false positive
  of the validator's ref-sort rule (a letter-suffixed tag always sorts
  before a numeric one at the same position, regardless of the letters);
  the epistle genuinely follows poem 107's verses in the source. No other
  check failed (0 empty lines, 0 duplicate refs, 0 HTML residue).
- Production steps (after merge, none of them run yet):
  1. `git pull` on production `main`; removes
     `eugippius.excerpta_ex_operibus_augustini.tess` and
     `magnus_felix_ennodius.carmina.tess` from `texts/la/`, adds
     `magnus_felix_ennodius.carmina_2.tess`.
  2. Lemma cache: delete any `cache/lemmas/la/` entries for the two
     retired filenames; build a fresh entry for
     `magnus_felix_ennodius.carmina_2` (new content, needs one).
  3. Latin inverted index: drop the two retired texts' postings, lines and
     texts rows with `scripts/corpus/drop_stale_index_entries.py` (dry run
     first), then run the normal Latin text-import step for
     `magnus_felix_ennodius.carmina_2.tess` so its verses are indexed;
     rebuild `lemma_doc_freq`.
  4. Latin bigram cache: `venv/bin/python scripts/corpus/rebuild_bigrams.py
     la`, after confirming it is actually stale.
  5. Passage index: drop the retired texts' windows (283 for the Eugippius
     file, 39 for the Ennodius whole-poem file, per the source comparison
     document) in lockstep across ids, embeddings, descriptions and
     window_texts with `drop_passage_rows.py`; build new windows for
     `magnus_felix_ennodius.carmina_2` (932 lines).
  6. Atomic swap of both the inverted index and the passage index, `touch
     tesseraev6_flask.wsgi`, run the reference test before and after
     (324 distinct loci for "arma virum" as of 2026-09).
  7. A search for a phrase known to be in `magnus_felix_ennodius.carmina_2`
     (e.g. a Book 2 epigram line) to confirm the new file is live and
     indexed.
- Archive: `~/tesserae-backups/retired_duplicates_2026-09-19b/` (`texts/la/`
  for the 2 retired files; `lemma_cache/la/` and `translations/la/` both
  empty, no entry for either file found in this checkout).

### Part C (added same day, same PR): Sodoma and Iona pairs checked, kept as-is
- What: a check of whether `tertullian_pseudo.de_sodoma.tess` /
  `cyprian_pseudo.sodoma.tess` and `tertullian_pseudo.de_iona_propheta.tess`
  / `cyprian_pseudo.de_iona.tess` are the same poem transmitted under two
  attributions (a documented manuscript-tradition fact for these two poems)
  and, if so, to retire the weaker copy. Compared by normalized line
  matching (lowercase, v to u, j to i, punctuation stripped) and by
  order-independent 4-word chunk containment (not just index-aligned lines,
  since a one-line offset in the Sodoma pair would otherwise distort a
  naive per-line diff):
  - **Sodoma**: `cyprian_pseudo.sodoma.tess` 166 lines/1,580 words;
    `tertullian_pseudo.de_sodoma.tess` 167 lines/1,594 words. 4-word chunk
    containment 53.7% (cyprian-in-tertullian) / 53.1% (the reverse).
    Index-aligned exact-line match at the best offset: 33.1% (55/166).
  - **Iona**: `cyprian_pseudo.de_iona.tess` 105 lines/1,007 words;
    `tertullian_pseudo.de_iona_propheta.tess` 105 lines/1,009 words. 4-word
    chunk containment 53.4% / 52.8%. Index-aligned exact-line match: 41.0%
    (43/105).
  - For comparison, every genuine same-edition duplicate pair checked in
    this document (2026-09-18 and 2026-09-19 batches) ran 90%+ on the same
    kind of chunk-containment check; OCR noise alone (letter swaps, v/u,
    dropped letters) does not depress the figure to ~53%. The differences
    here are at the word-choice level, not the letter level (Sodoma line 1:
    "primaeui **crimina** saecli" vs "primaeui **tempora** saecli"; line 3:
    "**Quot** caelum **spargit**" vs "**quas** caelum **sparsit**"; line 4:
    "**et** liquido" vs "**haud** liquido"), the kind of divergence expected
    between two real manuscript-tradition recensions, not two scans of one
    edition. `backend/text_sources.json` confirms two different
    print-edition lineages exist for both poems (a Peiper 1891 CSEL
    "Cyprianus Heptateuchos" edition and an Oehler 1854 "Tertullian" edition
    are both cited elsewhere in the file, for neither of the two currently
    served files, which are both instead sourced from The Latin Library
    under their respective attribution pages).
  - **Decision: keep both pairs.** They are the same poem but differ
    materially enough (word-level, not OCR-level) that picking a "better"
    copy would mean picking a manuscript tradition, not deduplicating a
    scan; both traditions are legitimate to keep searchable.
  - Bonus finding while checking `text_sources.json` credits (as asked):
    three orphaned citation entries with no corresponding served file,
    removed: "Pseudo-Cyprian"/"Sodoma" (Peiper 1891, `added_by`: "V3 Legacy
    Import", left over from a file already gone, likely the `pseudo_cyprian.carmina`
    bundle retired in the 2026-09-18 batch), "Pseudo-Tertullian"/"Carmen De
    Iona et Ninive" and "Pseudo-Tertullian"/"Incerti Auctoris Carmen
    Sodoma" (both Oehler 1854, `added_by`: "Caitlin Diddams", matching no
    filename or author/work string on any file in the current corpus).
    Neither of the two live pairs' own citations (both "The Latin Library",
    `added_by`: "V6 Import") was touched.
- No corpus files added, removed or modified in Part C; the only change is
  the three-entry `text_sources.json` cleanup above.

### Part D (added same day, same PR): the two Book 1 prose prefaces preserved
- What: the two Book 1 prose items flagged in Part B were kept rather than dropped
  (slots 1.6 and 1.7 of the retired `magnus_felix_ennodius.carmina.tess`)
  and to identify what they are. Re-checked against the source XML
  (`stoa0114a.stoa003.opp-lat1.xml`): both slots are actually mixed
  prose-plus-verse compositions, not pure prose. Slot 6's verse (40 lines,
  240 words, opening "Post canas hiemes, gelidi post damna profundi")
  and slot 7's verse (80 lines, 414 words, opening "Fluminis in medio
  succendis uiscera, Fauste,") match `ennodius.carmina.tess`'s own poems 6
  and 7 verse-for-verse (confirmed by opening and closing lines) -- so the
  verse portions are NOT unique, they are the same poems the batch-2-era
  comparison document had already found duplicated in `ennodius.carmina.tess`.
  What genuinely exists nowhere else is the PROSE that precedes each poem
  in this source only: slot 6 is titled "VI. Dictio Ennodi diaconi quando
  de Roma rediit" (443 words, a prose "dictio" on Ennodius's return from
  Rome) and slot 7 is titled "VII. Fausto Praefatio" (123 words, a prose
  preface addressed to Faustus, introducing the poem that follows). Neither
  text appears in `magnus_felix_ennodius.dictiones.tess` (the separate,
  already-served Dictiones collection, a different source document,
  `stoa0114a.stoa004`) or anywhere else in the corpus (checked by exact
  phrase search across `texts/la/`).
  - New file: `magnus_felix_ennodius.carmina_1_praefationes.tess` (2 lines,
    567 words), holding just these two prose prefaces, tagged
    `<magnus_felix_ennodius.carmina_1_praefationes 6>` and `<...7>` (the
    original Book 1 slot numbers, for traceability). The id deliberately
    does not read "dictiones_1": the existing `magnus_felix_ennodius.dictiones.tess`
    is already a complete, separately-sourced collection, and naming this
    file as if it were "book 1" of that collection would misrepresent it;
    "carmina_1_praefationes" names what these two items actually are,
    prose prefaces belonging to Carmina Book 1.
  - Two small transcription artifacts in the source XML's prose text were
    corrected while extracting it (both are stray tokens, not real Latin,
    consistent with the level of noise already documented elsewhere in
    this corpus): "pateat exul- s tantis" -> "pateat exultantis" (slot 6)
    and "quantum sentio, 5 rubiginosos" -> "quantum sentio, rubiginosos"
    (slot 7). Word counts (443 and 123) match the retired whole-poem
    file's own `2.6`/`2.7`-equivalent lines for these two items exactly
    once the source XML's `<note>` apparatus, nested inside the `<p>`
    element for slot 7 in this specific source (an isolated encoding
    irregularity, not present for slot 6), is excluded from extraction.
  - Registries: `data/text_genres.csv` (new row, era Late Antique, meter
    prose, genre medieval, matching the other Magnus Felix Ennodius prose
    works); `backend/text_provenance.json` (new entry, same source XML as
    `magnus_felix_ennodius.carmina_2`, title "Carmina, Book 1, Prose
    Prefaces (6-7)").
  - `python scripts/corpus/validate_tess.py`: `2 lines, avg 2090 chars
    [ok]`, no flags.

### Part D verification addendum: two further checks
- **`DISPLAY_NAMES` keys on the bare stem.** Ran
  `format_display_name('exerpta_ex_operibus_augustini')` directly: returns
  `'Excerpta ex Operibus Augustini'`. Also ran the actual call path the app
  uses, `get_text_metadata('texts/la/eugippius.exerpta_ex_operibus_augustini.tess')`:
  its `title` is `'Excerpta ex Operibus Augustini'` too. Both confirm the
  Part A fix reaches the real title the site renders, not just the raw
  dictionary lookup.
- **`meter=unknown` is an accepted, correctly-handled value.** Grepped
  every consumer of the `meter` column: `backend/blueprints/admin.py`
  itself defaults a missing value to `'unknown'`
  (`row.setdefault('meter', 'unknown')`); `backend/fusion.py`'s
  `_get_text_meter()` explicitly treats `'unknown'` (with `'mixed'` and
  blank) as "no meter data, do not group this text by meter" for the
  same-meter IDF feature, which is exactly the intended behavior for a
  verse text the scanner has no scansion entry for; the admin genre
  editor, `client/src/components/admin/tabs/GenreClassificationTab.jsx`,
  uses `'unknown'` as its own fallback throughout (`t.meter || 'unknown'`)
  and treats the meter column as an open set of values discovered from the
  data, not a fixed enum. `unknown` is not a guess; it is the same value
  already used in production for the sibling row `ennodius.carmina.tess`,
  for the identical reason.
- Done 2026-09-19, EDT throughout, as ncoffee on production
  `/var/www/tesseraev6_flask`, each step inside its own `systemd-run
  --user --scope -p MemoryMax=<n> -p MemorySwapMax=0` scope, one at a
  time: 10:50 `git pull` of #395 (`421306d`); confirmed the two retired
  files (`eugippius.excerpta_ex_operibus_augustini.tess`,
  `magnus_felix_ennodius.carmina.tess`) absent, and the two new files
  (`magnus_felix_ennodius.carmina_2.tess`,
  `magnus_felix_ennodius.carmina_1_praefationes.tess`) present. Two orphan
  entries for the retired files removed from `cache/lemmas/la/`, then
  `scripts/batch_lemma_cache.py la` under a `MemoryMax=8G` scope built the
  two new entries. 11:00 `scripts/corpus/drop_stale_index_entries.py
  --language la --apply` (a dry run first found exactly 2 stale: 1,391
  lines, 107,429 postings), cap 8G: swapped, backup
  `la_index.db.bak-stale-20260919-0922`, 1,638 texts. 11:08
  `scripts/corpus/add_texts_to_index.py --db la_index.db.new --language la
  --cache-dir cache/lemmas --add magnus_felix_ennodius.carmina_2.tess
  magnus_felix_ennodius.carmina_1_praefationes.tess` on a copy, cap 8G,
  `lemma_doc_freq` rebuilt (327,130 lemmas, 48 s), swapped, backup
  `la_index.db.bak-ennodius-20260919`; 1,640 texts, 929,591 lines. 11:12
  `scripts/corpus/rebuild_bigrams.py la`, cap 10G: 775 docs, 15,225,911
  bigrams, 105 s. 11:16 `drop_passage_rows.py --work
  eugippius.excerpta_ex_operibus_augustini --work
  magnus_felix_ennodius.carmina --tag retire-b3-20260919 --apply`, cap
  12G: 322 windows dropped (283 and 39), ids 619,356 to 619,034, backups
  tagged `*.bak-retire-b3-20260919`. 11:18 coverage sidecar
  `data/passage_index/works_by_language.json` refreshed (la 728, grc 828,
  en 42, cop 144, he 39; index version 2026-09-19), then one reload
  (`touch tesseraev6_flask.wsgi`).
- Open: the two new Ennodius files have no passage windows yet (they need
  a GPU describe run for their descriptions, queued for BullsAI or the
  next GPU session), so they are searchable but absent from Theme Search
  and Similar Passages until then.
- Checks after the reload: "arma virum" lemma search count unchanged; an
  exact search of an Ennodius Book 2 verse finds
  `magnus_felix_ennodius.carmina_2`; coverage answers 728 Latin works.

## 2026-09-19 Corpus: two more duplicate Latin files retired (batch 2)
- What (code, this PR; not yet run on production): `research/corpus/
  RETIREMENT_LIST_2026-09-19_batch2.md` checked six further items found
  since the 2026-09-18 batch, against production texts at
  `/var/www/tesseraev6_flask/texts/la/`. Two were confirmed safe to retire
  and approved on 2026-09-19; the other four were left alone (two
  need a human read before any decision, one is a shared generic title
  over two distinct works, one is expected cross-collection overlap of a
  shared letter). Files removed from `texts/la/`: 2.
  1. `juvencus_caius_vettius_aquilinus.evangeliorum_libri_quattuor.tess`
     (5 lines, one per book, whole books stored as single `<ref>` lines,
     19,752 words) retired; `juvencus.historia_evangelica.tess` (+4
     `.part.N` files, 3,182 lines at per-verse granularity, 19,854 words)
     kept. Word counts within 0.5%; line-level containment 60.4%/60.9%,
     spot-checked misses are orthographic variants (`quum`/`cum`), not
     missing content.
  2. `pseudo_cyprian.carmina.tess` (6 lines, one giant line per poem: the
     Peiper 1891 CSEL edition of Genesis, Sodoma, De Iona, Ad Senatorem,
     De Pascha, Ad Flavium Felicem) retired. Five of its six poems already
     exist as separate, per-verse `cyprian_pseudo.*` files (note the
     reversed word order versus the retired `pseudo_cyprian.*` id), kept:
     `cyprian_pseudo.de_pascha`, `.sodoma`, `.de_iona`,
     `.ad_senatorem_ex_christiana_religione_ad_idolorum_servitutem_conversum`,
     `.ad_flavium_felicem_de_resurrectione_mortuorum`. The sixth poem,
     Genesis, is not part of this operation (its standalone file was
     already retired in the 2026-09-18 batch). Re-verified in this PR with
     a 6-word normalized chunk containment check: 93.5% to 97.2% across
     the five poems, word counts within 2% each; misses spot-checked as
     single-word orthographic variants (e.g. standalone "Qoi mihi
     ruricolas" vs. bundle "Qui mihi ruricolas") and each poem's title
     heading, present as running text in the bundle's single line but not
     carried into the standalone per-verse body text (paratextual, not
     missing content).
- Registries edited: `data/text_genres.csv` (3 rows removed: the two
  retired files, plus `magnus_felix_ennodius.epistulae.tess`, a stale row
  left over from the 2026-09-18 batch, whose file was already gone; of
  the three stale rows the source document named, the other two,
  `augustine.speculum` and `cyprian_pseudo.genesis`, had already been
  cleaned up by the 2026-09-18 batch itself by the time this PR branched).
  `backend/text_sources.json` (3 entries removed: "Juvencus Caius Vettius
  Aquilinus"/"Evangeliorum Libri Quattuor" and "Pseudo-Cyprian"/"Carmina"
  for the two retired files, plus "Magnus Felix Ennodius"/"Epistulae", an
  orphan for the same already-gone file as the stale genres row above,
  found while verifying no row in this registry points at a missing file.
  Note: the source document stated no `text_sources.json` entry existed
  for the Juvencus id; an entry did exist at execution time and is
  removed here, flagged as a discrepancy rather than silently reconciled).
  `backend/text_provenance.json` and `backend/author_dates.json` also
  carry rows for the two retired files (a per-file CSEL-import record
  each, and an author-level date record used by no other file for
  Juvencus); neither registry was touched by the 2026-09-18 precedent, so
  neither is touched here, flagged as a follow-up. `data/text_genres.csv`
  separately still carries roughly 87 rows for files absent from `texts/`
  unrelated to either 2026-09 retirement batch (found while checking this
  batch's rows against the files on disk); not touched, well outside this
  operation's scope, flagged for a future cleanup pass.
- No `text_descriptions.json` entries for either retired file (checked
  the file in this repository; production's copy is checked at
  execution time per the source document).
- Archive: `~/tesserae-backups/retired_duplicates_2026-09-19/` (`texts/la/`
  for the 2 retired files; `lemma_cache/la/` and `translations/la/` both
  empty, no entry for either file found in this checkout, which does not
  carry the real lemma cache), README in the 2026-09-18 format.
- Checks run without a server (this PR, before merge):
  `python scripts/corpus/validate_tess.py` on the 5 kept Cyprian files and
  the kept Juvencus work (whole + 4 parts): all 10 report `[FAIL]` on the
  script's tab-delimited `<ref>\ttext` check, because these are legacy
  imports that use `<ref>` followed by one or two literal spaces rather
  than a tab, a pre-existing condition of these already-served files that
  predates and is unrelated to this operation (this PR does not modify
  their content). Re-checked by hand with a space-tolerant version of the
  same script's other rules: 0 empty lines, 0 duplicate refs, 0 HTML
  residue across all 10 files, so the files are otherwise sound; the
  tab-vs-space convention gap is flagged, not fixed, here.
- Production steps (after merge, none of them run yet, following the
  2026-09-18 precedent exactly since this batch is much smaller: 2 files,
  each with 1 passage-index window):
  1. `git pull` on production `main`; removes the 2 retired files from
     `texts/la/`.
  2. Lemma cache: check `cache/lemmas/la/` for entries under either
     retired file's name and delete them if present (this checkout's
     stub cache has none, so confirm on the actual server cache at
     execution time); no rebuild needed since no file's content changed,
     only removals.
  3. Latin inverted index: `python scripts/corpus/drop_stale_index_entries.py
     --root /var/www/tesseraev6_flask --language la --apply` (dry run
     first, without `--apply`, to confirm it finds exactly 2 stale
     filenames) removes the 2 retired texts' postings, lines and texts
     rows and rebuilds `lemma_doc_freq`.
  4. Latin bigram cache: `cd /var/www/tesseraev6_flask && venv/bin/python
     scripts/corpus/rebuild_bigrams.py la`; confirm it is actually stale
     before assuming a rebuild is required (same caution as 2026-09-18).
  5. Passage index: drop the 2 retired texts' windows (1 each) in
     lockstep across ids, embeddings, descriptions and window_texts with
     `drop_passage_rows.py` (same script location caveat as 2026-09-18:
     confirm it still exists in `~/tesserae-backups/session_scripts_2026-09-11/batch/`
     or recreate it from that precedent).
  6. Reference test in `tests/search_reference_tests.md` ("arma virum"
     lemma search: Ovid, Quintilian, Seneca) before and after the index
     change.
  7. `touch tesseraev6_flask.wsgi`.
- Scripts: `scripts/corpus/drop_stale_index_entries.py`,
  `scripts/corpus/rebuild_bigrams.py`, `drop_passage_rows.py` (passage
  index).
- Done 2026-09-19, EDT throughout, as ncoffee on production
  `/var/www/tesseraev6_flask`, each step inside its own `systemd-run
  --user --scope -p MemoryMax=<n> -p MemorySwapMax=0` scope, one at a
  time: 08:27 `git pull` of #393 (`c01d12c`); brought Latin to 1,820
  files, confirmed the two retired files absent. Two orphan entries for
  the retired files removed from `cache/lemmas/la/`. 08:28
  `scripts/corpus/drop_stale_index_entries.py --root
  /var/www/tesseraev6_flask --language la --apply` (a dry run first found
  exactly 2 stale: 11 lines, 10,043 postings), cap 8G: swapped, backup
  `la_index.db.bak-stale-20260919-0827`, 1,640 texts. 08:31
  `scripts/corpus/rebuild_bigrams.py la`, cap 10G: 775 docs, 15,421,035
  bigrams, 101 s. 08:34 `drop_passage_rows.py --work
  juvencus_caius_vettius_aquilinus.evangeliorum_libri_quattuor --work
  pseudo_cyprian.carmina --tag retire-b2-20260919 --apply`, cap 12G: 2
  windows dropped (each work had one), ids 619,358 to 619,356, backups
  tagged `*.bak-retire-b2-20260919`. 08:36 coverage sidecar
  `data/passage_index/works_by_language.json` refreshed in a capped
  process (la 728, grc 828, en 42, cop 144, he 39; index version
  2026-09-19), then one reload (`touch tesseraev6_flask.wsgi`).
- Checks after the reload: Similar Passages answers on
  `cyprian_pseudo.sodoma` 1; coverage answers from the sidecar; "arma
  virum" lemma search count unchanged at about 323 distinct loci.

## 2026-09-19 English: lemma caches, index and Quotation table rebuilt after the noun-only lemmatizer fix (PR #413)
- Why: the batch cache builder lemmatized English as nouns only, so every
  English lemma cache kept past tenses ("stood", "went", "fled", "began")
  while the index builder reduced them; "began" had a document frequency
  of 2 works against 28 for "begin", and in a Milton search his own verbs
  ranked like proper names (docs/DECISIONS.md, 2026-09-19 English entry).
- Steps, from the production checkout, each under the memory launcher
  (`~/bin/tess-job`, cap 8G, tesserae-jobs.slice), Tessa stopped for the
  period (23:38 to the end):
  1. `scripts/build_inverted_index.py --language en --force` (23:40 to
     23:42, 2.6 minutes; previous index kept as
     ~/tesserae-backups/en_index.db.prev-20260919): 164 texts, 33,434
     lemmas in lemma_doc_freq; "begin" 28, "flee" 25, "stand" 30 works;
     "began", "fled", "stood" gone.
  2. `scripts/batch_lemma_cache.py en --force` with the fixed builder
     (after #413 merged; an earlier run at 23:39 with the unfixed builder
     is superseded): all 164 English caches.
  3. App reloaded; `scripts/reuse/build_reuse_table.py --language en`
     rebuilt on the new caches.
  4. Cached search results cleared for English, Latin and Greek
     (`backend.cache.clear_cache_for_language`; the Latin and Greek ones
     also carried the pre-#411 quotation weight), and the three default
     pairs re-warmed.
- Done: index 23:40-23:42 EDT (2.6 min); caches with the fixed builder
  23:46-23:47 (164 files; "Fled over Adria" now lemmatizes to "flee ...");
  English Quotation table 23:47-23:49 (83 s, 116,302 pairs, 113,707 via the
  rare rule); cached search results cleared 23:50 (47 files: en 5, la 36,
  grc 6); default pairs re-warmed by 23:53 (Latin Aeneid 1 x Lucan 1, English
  Paradise Lost 1 x Hyperion, Greek Iliad 1 x Argonautica 1). Check on the
  English default pair: before, the top ten held "began, read", "fled,
  over" and "summer, day"; after, it opens with "expanded wings" (P.L. 1.20
  / Hyperion 1.29), "dire event", "old Saturn", "far within", "high Gods",
  "palace, court", "awaiting command". Tessa restarted 23:54.
- 2026-09-20 00:05-00:12 EDT: PR #414 (English function-word list from
  sources, 275 entries) deployed with a bundle rebuild inside the launcher
  (Tessa paused three minutes) and a reload; live /api/stoplists shows 275
  English entries; the one cached English search result was cleared and the
  default English pair re-warmed (top ten unchanged from the 23:53 check).

## 2026-09-19 Reader: Quotation tables rebuilt for Latin, Greek and English under the final builder rules
- What: after the first English table (13:14) marked Hamlet III.4.192 "What
  shall I do?" as strictly quoted by eight Bible verses and paired the Faerie
  Queene's books with each other, the builder's rules were changed in four
  PRs the same day (#404 decode surrogate-escaped Greek work ids; #405 part
  files of one work count as one work, commonplace-only n-grams; #406 the
  language stoplists feed the commonplace test; #408 and #409 a pair is
  dropped only when EVERY shared n-gram is commonplace-only, and only for
  English). Each Latin variant was built to a side file and compared with
  the live table (la.db.prev-20260919) before anything was swapped.
- Measured on Latin (strict pairs, live table 54,880): "count commonplace
  n-grams for nothing" 51,599 (2,202 gained, 5,445 lost, the lost sample
  being the Fathers quoting the Vulgate); "drop only all-commonplace pairs"
  53,016 (0 gained, 1,863 lost, still including John 10.30 in Hilary);
  English-only drop 54,571 (0 gained, 309 lost, every one a part-file pair
  of a single work). The last is what shipped.
- Done (Latin): 2026-09-19 20:57-21:08 EDT, `--out-db la.new.db` under a
  12G cap in tesserae-jobs.slice, then moved into place at 21:09 and the app
  reloaded. 308,688 pairs (54,571 strict); metadata records
  drop_all_commonplace=auto, applied=0. Verified: Aeneid 1.1 shows 2 strict
  and 5 possible quoting works (Salutati among them), 7.466 shows Macrobius,
  the arma virum reference search returns 323.
- Done (Greek, first build): 2026-09-19 19:40-20:09 EDT under a 12G cap,
  peak 11.0 GB, 123,232 pairs (26,640 strict), built under the interim
  "count for nothing" rule; superseded by the rebuild below.
- Done (English, interim): 13:36 EDT (125,384 pairs) under the interim
  rule, live from 19:37 after a reload; superseded by the rebuild below.
- Done (English, final): 2026-09-19 21:20-21:21 EDT under an 8G cap, 81 s,
  101,835 pairs (2,542 strict; 3,860,431 candidate pairs dropped because
  every shared n-gram was commonplace-only; metadata applied=1), live after
  a reload. Verified: Hamlet III.4.192 "What shall I do?" has no quotations
  (eight Bible verses on the first build); Bunyan, Pilgrim's Progress 1.2035
  is still strictly matched to Revelation 22.14.
- Done (Greek, final): 2026-09-19 21:51-22:11 EDT under a 12G cap (final rule:
  all-commonplace drop off for Greek, part files one work), 114,359 pairs
  (27,427 strict; 86,932 via the rare rule), live after a reload. Iliad 1.1
  is quoted by Aelius Aristides. Known Greek residue for a later pass:
  duplicate copies pair with themselves (two Aesops; Libanius whole and in
  parts under different base names) and the per-book Septuagint and New
  Testament files count as separate works, unlike the whole-file Vulgate.
- Memory record for these builds: Latin peaks 9.2 to 11.9 GB in the cgroup
  (file cache counted), Greek 11.0 GB, English 1.2 GB; a MemoryHigh one
  gigabyte under the cap throttled the Greek build to a crawl and was
  removed from the launcher.
- Also on 2026-09-19: three attempts at the Greek build failed or were
  stopped before these rules settled (surrogate ids 12:59 and 13:02; stopped
  13:23 and 13:29; killed by the machine-wide pressure event 13:38). Logs
  under ~/tesserae-backups/jobs/.

## 2026-09-19 Reader: corpus-wide reuse table built for Latin

- What (code, not yet run on production): `scripts/reuse/build_reuse_table.py
  --language <lang>` builds the corpus-wide verbatim/near-verbatim line-reuse
  table the Reader's "quoted in N works" mark and Reuse tab read
  (`GET /api/reuse/line`, `GET /api/reuse/marks`, `backend/reuse_table.py`).
  It reads `texts/<lang>/*.tess` as the live corpus (so a file retired from
  `texts/` is excluded even if a stale cache entry for it still exists),
  applies the same `.part.N` skip rule as `backend/bigram_frequency.py`
  (drop a part file when its base file is present), reads surface tokens
  from each surviving file's plain `cache/lemmas/<lang>/<text_id>.json`
  (skipping any live file with no plain cache -- a warning names them, not
  an error), and writes `cache/reuse_pairs/<lang>.db` (`pairs`,
  `line_counts`, `meta` with `built_at`, `corpus_version`,
  `corpus_file_count`). Ported from the `research/reuse_table/` prototype
  (`build_reuse_index.py` + `find_reuse_pairs.py`, merged into one script);
  see `research/reuse_table/REPORT_2026-09-18.md` for the full design
  history, including the containment rule
  (`shared >= 4 and shared/min(ngrams_a, ngrams_b) >= 0.5`, replacing an
  earlier raw-shared-count override that let long, unrelated prose
  paragraphs through on a handful of coincidental function-word n-grams).
- Run: `systemd-run --user --scope -p MemoryMax=12G venv/bin/python3
  scripts/reuse/build_reuse_table.py --language la`, foreground, from a
  worktree with `texts/`, `data/lemma_tables/` from git and `cache/lemmas/`,
  `data/inverted_index/` symlinked to production (the same layout
  `~/tesserae-map` uses). Result on the post-2026-09-10/09-18 retirement
  corpus: 679 works indexed (1,043 `.part.` files collapsed into their base;
  98 live `.tess` files skipped for a missing plain lemma cache -- rebuild
  those caches to close this recall gap, a pre-existing condition this
  script surfaced rather than caused), 516,458 lines, 52,855 pairs kept,
  419s (about 7 minutes) total, comfortably under the cap. Prior stale-corpus
  prototype run (before the duplicate-file retirements): 858 works, 605,521
  lines, 117,111 pairs, 12.5 minutes -- the drop in both work count and kept
  pairs on this run is expected and is itself a rough measure of how much of
  the earlier count was corpus-duplicate artifact rather than genuine reuse.
- Checked: the 20-known-quotation set (Vergil in Macrobius and Servius'
  Georgics commentary; Gellius could not be checked here -- see below) came
  back 18/20 recovered, the 2 misses both short quotations sitting inside a
  very long multi-quotation commentator line whose few surviving n-grams did
  not clear the containment/jaccard bar, the same known-limitation shape the
  prototype report documents. A fresh 30-pair random hand sample (seed 42)
  read against full line text (not a truncated preview -- the prototype
  report's own lesson): 3 duplicate-text artifacts (a still-unretired
  Eugippius `excerpta`/`exerpta` spelling-variant pair, and a newly-found
  `cyprian_pseudo.de_pascha` / `pseudo_cyprian.carmina` overlap -- neither on
  the 2026-09-10/09-18 retirement lists, both worth adding), 1 false
  (coincidental) match, and 26 genuine matches (17 direct verbatim
  quotations correctly located, including two buried in 824- and
  1,233-token compilation lines; 9 formula/shared-citation/self-echo cases,
  several of them real Augustine-Jerome correspondence preserved in both
  men's letter collections). Duplicate-artifact share (3/30, 10%) is far
  below the stale-corpus prototype's finding (dominant, ~7:1 over genuine
  quotation on its poetry subset) but not literally zero -- the corpus still
  carries a handful of un-retired duplicate/near-duplicate work pairs.
- Known gap, not fixed here: Gellius's Attic Nights (`gellius.attic_nights`)
  has no plain lemma cache in production, only the per-`.part.N` and
  file-hash-suffixed caches, so it is absent from this run entirely (one of
  the 98 skipped files) and the known-quotation check above could not
  include it. Rebuilding its cache (`scripts/rebuild_lemma_cache.py` or
  equivalent) and re-running the language would close this.
- **Fixed and rebuilt 2026-09-19:** the gap above was not a missing cache but
  a wrong filename guess -- caches are named `<work id>-<md5>.json`
  (`get_cache_path`), and this script's `discover_corpus` was checking the
  plain `<work id>.json` name only. Switched it to call
  `backend.lemma_cache.get_cached_units(fname, language)`, the same
  hashed-name-then-legacy-name, file-hash-validated resolution
  `scripts/batch_lemma_cache.py`, `backend/text_service.py` and
  `backend/app.py` already use, instead of guessing. Rebuilt on the same
  corpus: 777 works indexed, 0 skipped for missing/invalid cache (down from
  98, Gellius included), 652,003 lines, 62,265 pairs kept, ~30 minutes
  total (`index_elapsed_seconds` 1,632s + `pairs_elapsed_seconds` 93s,
  `total_elapsed_seconds` 1,787s per `cache/reuse_pairs/la_stats.json`).
  Re-checked: the 20-known-quotation set (Vergil in Macrobius Saturnalia
  5-6, Servius' Georgics commentary, and Gellius, sampled fresh with seed
  20260918) now comes back 20/20; a fresh 30-pair random hand sample (seed
  43) read against full line text: 23 genuine quotations (mostly patristic
  authors independently quoting the same Vulgate verse, plus Gospel-harmony
  and testimonia-anthology citations), 3 formula/self-echo (fixed
  scriptural or epic-formula tags, e.g. the Pentateuch's "locutus est
  Dominus ad Mosen dicens" and the Vergilian epic hemistich "at parte ex
  alia" shared by unrelated poems), 4 duplicate-artifact pairs (Ennodius
  under two work ids, Juvencus under two work ids, and two Augustine/Jerome
  letters that are the same physical letter cross-catalogued in both men's
  epistulary collections), 0 false matches. Full detail, both checks'
  worked examples, and the still-skipped-works list:
  `research/reuse_table/REPORT_2026-09-18_production_build.md`.
- Done (Latin): 2026-09-19 11:00-11:12 EDT, from the production checkout
  under `MemoryMax=12G`: 775 works, 651,535 lines, 336,955 pairs kept
  (282,075 via the rare single-triple "possible" rule), 692 s, written to
  `cache/reuse_pairs/la.db` (87 MB) with `la_stats.json` beside it. Workers
  picked the table up without a reload. Verified on the live site: Aeneid
  1.1 shows 2 strict (Geoffrey of Vinsauf, Quintilian) and 4 possible
  quoting works, Aeneid 7.466 shows Macrobius, Saturnalia 5.11.23. Greek and
  English builds to follow, one at a time.
- Production steps (Latin, as planned): from the production checkout (it
  must read production `texts/`, not a worktree's), one at a time,
  `systemd-run --user --scope -p MemoryMax=12G -p MemorySwapMax=0
  venv/bin/python scripts/reuse/build_reuse_table.py --language la` --
  measured peak 9.2 GB, about 10 minutes, writes `cache/reuse_pairs/la.db`.
  Then `touch tesseraev6_flask.wsgi` so the workers pick up the new table.
  Greek and English builds are to follow the same pattern once Latin is
  live and reviewed; rebuild after any corpus change to that language (new
  imports, retirements, lemma-cache rebuilds) -- the table is a snapshot,
  not computed live. `cache/` is not in git; `cache/reuse_pairs/<lang>.db`
  ships only by running the script on production, the same way other
  caches under `cache/` are built.
- Verify: `tests/test_reuse_routes.py` (fixture-db backend route tests),
  `tests/test_mcp_parity.py` (manifest coverage for the two new routes),
  plus the reference tests in `tests/search_reference_tests.md` (unrelated
  to this table, run as a matter of course whenever search/indexing code is
  touched).

## 2026-09-18 Corpus: 33 duplicate Latin files retired, Martial rebuilt from its per-book files
- What (code, this PR; not yet run on production): `research/corpus/
  RETIREMENT_LIST_2026-09-18.md` confirmed 12 duplicate/stray Latin files
  safe to retire; a further "stray
  second edition" group the report had left undecided, and to rebuild
  `martial.epigrams` (missing dozens of epigrams per book, including all
  of 1.1 and the prefatory epistle) from the 14 `martialis.epigrammata_N`
  per-book files, which hold the complete text. After the rebuild those 14
  per-book files are exact duplicates of the new parts and are retired
  too. Total files removed from `texts/la/`: 40 (the task's own prose
  calls this "33," matching the source report's own inconsistent count of
  the second group as "7 pairs... 6 files across 6 pairs" in its words;
  the real count once Manilius's five `.part.N` files are included with
  its retired whole file is 14, not 7, so 12 + 14 + 14 = 40. Flagged
  explicitly rather than silently reconciled to the round number; see the
  PR body and archive README for the same note). Registries edited:
  `data/text_genres.csv` (40 rows removed) and `backend/text_sources.json`
  (12 entries removed, the ones for files that had one). No
  `text_descriptions.json` or `author_dates.json` entries existed for any
  of the 40. `martial.epigrams.tess` and its 14 `.part.N` files keep their
  names but change content: 6,399 verse-lines to 9,375, using the tag
  scheme `<mart. BOOK.EPIGRAM.LINE>` the old whole file already used, the
  prefatory letters before books 1 and 9 as epigram 0. No blank separator
  lines between epigrams (the old file had them; dropped because
  `scripts/corpus/validate_tess.py` rejects empty lines and the rebuild's
  own verification checklist required none). Verified: every book's
  epigram count matches the standard reference count for that book, no
  duplicate tags, `validate_tess.py` passes on all 15 files, and all but
  166 of the old whole file's 6,399 lines match the new file verbatim
  (normalized); the 166 are spot-checked word-level manuscript variants
  (example: `redimit`/`redemit` at 1.8.5), not missing content. Retired
  files and reasons, and the Martial counts per book, are in `research/
  threads/` (kept local, not committed) and in the archive README below.
- Also checked and left alone: `backend/metrical_scanner.py`'s meter
  lookup keys scansion data in `data/scansion/mqdq_scansions.json` by
  `martialis.epigrammata_{book}` derived from the citation tag itself
  (parsing `<mart. B.E.L>`), not from any `.tess` filename, so retiring
  the `martialis.epigrammata_N.tess` files does not affect meter boosts
  for Martial; the rebuilt files keep the same `mart.` tag prefix the
  lookup expects. `martialis.de_spectaculis.tess` was checked against the
  old and new whole files (no overlap either way) and left untouched, a
  separate text under its own name.
- Archive: `~/tesserae-backups/retired_duplicates_2026-09-18/` (`texts/la/`
  for the 40 retired files, `martial_rebuild_originals/` for the 29
  pre-rebuild Martial files, empty `lemma_cache/la/` and `translations/
  la/`: none of the 40 had either in this checkout), with a README in the
  2026-09-10 format.
- Production steps (after merge, none of them run yet):
  1. `git pull` on production `main`; this alone removes the 40 retired
     files from `texts/la/` and changes the 15 Martial files' content.
  2. Lemma cache: delete the stale cache entries for the 40 retired works
     and the 15 changed Martial files from `cache/lemmas/la/`, then
     `python scripts/batch_lemma_cache.py la` (rebuilds only the missing
     ones; it skips a filename it already has cached, so the Martial
     files' cache entries must be deleted first or `--force` used, and
     `--force` would rebuild the whole Latin corpus rather than just the
     15 files, so delete-then-rebuild is the fast path, as the 2026-09-16
     Paradise Lost entry above did for its 13 changed files).
  3. Latin inverted index: `python scripts/corpus/drop_stale_index_entries.py
     --root /var/www/tesseraev6_flask --language la --apply` removes the
     40 retired texts' postings, lines and texts rows and rebuilds
     `lemma_doc_freq` with the canonical builder (dry run first, without
     `--apply`, to confirm it finds exactly 40 stale filenames). Then
     replace the 15 Martial files' postings in place (same filenames, new
     content) with `scripts/corpus/add_texts_to_index.py --db
     la_index.db.new --language la --cache-dir cache/lemmas --replace
     martial.epigrams.tess martial.epigrams.part.1.tess ... .part.14.tess`
     on a copy, per that script's own atomic-swap pattern (cp live to
     .new, run, then swap live to .bak and .new to live).
  4. Latin bigram cache: `cd /var/www/tesseraev6_flask && venv/bin/python
     scripts/corpus/rebuild_bigrams.py la` (full rebuild from the corpus,
     needed because both the retirement and the Martial content change
     touch it; the 2026-09-10 precedent did not call this out as a
     separate step, so confirm it is actually stale before assuming a
     rebuild is required, same caution as that entry).
  5. Passage index: drop the 40 retired texts' windows in lockstep across
     ids, embeddings, descriptions and window_texts, and replace the
     Martial works' windows with newly-described ones, using
     `drop_passage_rows.py` and `apply_passage_rows.py --mode replace`.
     `drop_passage_rows.py` is not in this repository (per `research/
     corpus/RETIREMENT_LIST_2026-09-18.md` section 10, a copy was in
     `~/tesserae-backups/session_scripts_2026-09-11/batch/`, written for a
     preview branch as of 2026-09-10); confirm it still exists there or
     recreate it from the 2026-09-10 precedent before running this step.
  6. Reference test in `tests/search_reference_tests.md` ("arma virum"
     lemma search: Ovid, Quintilian, Seneca) before and after every index
     change, plus a Martial-specific search (e.g. a lemma search that
     should now surface epigram 1.1) to confirm the rebuild is live.
  7. `touch tesseraev6_flask.wsgi`.
- Scripts: `scripts/corpus/drop_stale_index_entries.py`,
  `scripts/corpus/add_texts_to_index.py`, `scripts/batch_lemma_cache.py`,
  `scripts/corpus/rebuild_bigrams.py`, `drop_passage_rows.py` and
  `apply_passage_rows.py` (passage index).
- Checks run without a server (this PR, before merge):
  `python scripts/corpus/validate_tess.py texts/la/martial.epigrams*.tess`
  (all 15 pass); the reference-test units under `tests/` that touch text
  listing (see the PR body for which ran and their results).
- Done 2026-09-18, EDT throughout, as ncoffee on production
  `/var/www/tesseraev6_flask`: 14:50 `git pull` of #389 (`de8863e`); this
  brought Latin to 1,822 files and `martial.epigrams` to 9,375 lines.
  Lemma cache: the 55 orphan entries for the retired and rebuilt files
  removed from `cache/lemmas/la/`, then `scripts/batch_lemma_cache.py la`
  under a `MemoryMax=8G` scope built the 15 new Martial entries. 14:53
  `scripts/corpus/drop_stale_index_entries.py --root
  /var/www/tesseraev6_flask --language la --apply` (a dry run first found
  exactly 40 stale: 30,960 lines, 556,097 postings): swapped, backup
  `la_index.db.bak-stale-20260918-1453`, 1,642 texts. 15:05
  `scripts/corpus/add_texts_to_index.py --db la_index.db.new --language la
  --cache-dir cache/lemmas --replace` for the 15 Martial files on a copy,
  `lemma_doc_freq` rebuilt (327,464 lemmas, 68 s), swapped, backup
  `la_index.db.bak-martial-20260918`; 930,059 lines in the index. 15:07
  `scripts/corpus/rebuild_bigrams.py la`: 777 docs, 3,805,740 bigrams,
  134 s. 16:00 passage index: a corrected copy prepared at
  `~/tesserae-backups/passage_index_2026-09-18/` (`CHECK.md`): 10,154
  windows dropped (7,186 for the 40 retired works, 2,968 for the old
  Martial), 2,363 Martial windows reused from the `martialis` files'
  vectors and descriptions (line sequences verified identical), 617,363
  windows after; swapped, backups tagged
  `martial-rebuild-40retire-20260918`; 1,995 windows of the whole-file
  Martial still need descriptions (phase misalignment against the old
  per-book windows), queued for a GPU describe run, to be appended with
  `apply_passage_rows.py --mode append`. 16:04 coverage sidecar
  `data/passage_index/works_by_language.json` written by warming each
  language once (la 730, grc 828, en 42, cop 144, he 39; index version
  2026-09-18), then one reload (`touch tesseraev6_flask.wsgi`) also
  carrying PR #390.
- Checks after the reload: "arma virum" lemma search 323 distinct loci
  (expected about 320); exact "hic est quem legis" finds Martial 1.1.1;
  Similar Passages on Martial 1.0.1 answers; coverage answered 730 works
  in 1.3 s during the reload.
- Done 2026-09-18 16:45 EDT: the 1,995 windows were described on a RunPod
  A100 with Qwen/Qwen2.5-32B-Instruct-AWQ (the corpus's own description
  model), 8 minutes, no failures (sidecar
  ~/tesserae-backups/passage_index_2026-09-18/martial_described.jsonl),
  embedded through the local encoder and appended with
  `scripts/corpus/apply_passage_rows.py --mode append --tag
  martial-describe-20260918` (backups with that tag): 619,358 windows and
  vectors after; reload; Similar Passages checked on martial.epigrams
  2.3.2.

## 2026-09-18 Coverage sidecar written on reload (PR #390)
- What: `data/passage_index/works_by_language.json` is not a manual data
  operation; the app writes it itself the first time each language's
  coverage is warmed after a reload (see the 2026-09-18 retirement/Martial
  entry above, whose 16:04 reload produced the file's first copy on
  production: la 730, grc 828, en 42, cop 144, he 39, index version
  2026-09-18). Noted here only because a cache file now persists outside
  the request that created it.
## 2026-09-20 Theme Search word index built on production (for the lexical boost)
- What: `data/passage_index/desc_fts.sqlite`, SQLite FTS5 (BM25, Porter
  stemming) over the gist, themes, action steps, participants and setting
  of all 619,280 passage descriptions, keyed by window id; built with
  `scripts/build_desc_fts.py` (branch feat/theme-lexical-boost) at 14:48
  EDT, 36 s, 678 MB, written beside descriptions.jsonl with a rename over a
  .tmp file. Unused by the live code until the lexical-boost PR deploys.
- Standing rule once deployed: rebuild it after every change to
  descriptions.jsonl (imports, retirements, description rebuilds); the app
  compares its description count with the passage index's and refuses a
  stale one, logging once and running without the boost.
- Done 2026-09-20 14:48 EDT (main session).

## 2026-09-20 Dates for three languages and the era badge deployed (PR #422)
- What: `backend/author_dates.json` gains sections for Middle High German
  (Nibelungenlied, c. 1200), Old French (Chanson de Roland, c. 1100) and
  Italian (Dante, d. 1321), era "Medieval"; Theme Search shows a work's era
  when it has no year (the Hebrew Bible, "Biblical", was shown as undated).
  Merged 7e231103, pulled, bundle rebuilt in the launcher (old bundles
  kept), WSGI reloaded 14:37 EDT (the date table is read once per process).
- Check: /api/passages/theme-search now returns year 1200 / Medieval for
  the Nibelungenlied and era Biblical with no year for Hebrew Bible books.
- Done 2026-09-20 14:37 EDT (main session).

## 2026-09-20 Fusion candidate-memory fix deployed (PR #416); cached results cleared
- What: PR #416 merged 2a9301c6 and pulled on production 14:29 EDT, WSGI
  reloaded. Backend only. Function words are no longer matching features
  in the lemma, lemma_min1 and exact channels; every channel's candidate
  list is bounded (lemma, exact, dictionary and rare_word gain the 50,000
  result cap); measurement and the three accepted behaviour changes in
  docs/DECISIONS.md (2026-09-20). Accepted and shipped.
- Cached fusion results cleared with `backend.cache.clear_cache_for_language`
  (la 8, grc 3, en 1 files) so pairs recompute under the new rules; the
  three default pairs (Aeneid 1 x Lucan 1, Paradise Lost 1 x Hyperion,
  Iliad 1 x Argonautica 1) re-warmed through /api/fusion-search by 14:59,
  each complete within about a minute; tops: Aeneid 1.103 / Lucan 1.416
  (sidera fluctusque), Paradise Lost 1.225 / Hyperion 1.296 (expanded
  wings), Iliad 1.190 / Argonautica 1.1250 (ἐρυσσάμενος φάσγανον). A first
  warm-up attempt used text ids without the .tess suffix and did nothing.
- Checks: 103 matcher and fusion tests; the benchmark table in
  DECISIONS.md; whole Paradise Lost x Hyperion 2.8 GB and 1.7 min against
  25.6 GB and 19 min before.
- Done 2026-09-20 14:29 EDT (main session).

## 2026-09-20 Three client deploys: sample searches, tab changes, King James label (PRs #419, #421, #420)
- 14:08 EDT: PR #419 (Theme Search sample searches re-measured: funeral
  games and a storm at sea replace the recognition chip; all five strong
  on production) merged 29db6ca0, pulled, bundle rebuilt in the launcher
  (old bundles kept), WSGI reloaded; served bundle index-BSdZd-fr.js
  carries the new chips.
- 14:19 EDT: PR #421 (tab changes start the new page clean; only the
  first address rewrite keeps parameters, so a Theme Search query no
  longer re-runs on every return to the tab) merged
  2798c427 and PR #420 (the English Bible displayed as the King James
  Bible; identifiers unchanged) merged ae948007; pulled, bundle rebuilt,
  reloaded; served bundle index-C0oXA1QI.js carries "King James Bible"
  six times and "World English Bible" not at all.
- The Similarity Map bakes author labels into its cache at build time, so
  its author row still read "World English Bible (en) (tr.)" after the
  reload; the map cache rebuild was started 14:20 (cap 8 GB, about 27
  minutes) and is followed by a reload. Done line below when finished.
- Note for long-open tabs: a page loaded before a deploy keeps its old
  bundle until reloaded; index.html now comes with Cache-Control:
  no-cache, so a fresh load always gets the current bundle.

## 2026-09-20 Corpus: the English Bible files are the King James Version (planned rename, not yet run)
- Finding (2026-09-20, from the results page's corpus panel): the 70
  files `texts/en/world_english_bible.*` hold the Authorized (King James)
  Version of 1611, not the World English Bible: "In the beginning God
  created the heaven and the earth", "Called of God an high priest after
  the order of Melchisedec", "The LORD {is} my shepherd" with the e-text's
  braces for supplied words. A legacy V3 label; PR #263 (2026-08-18) noted
  it when it added the KJV New Testament under the same name and set the
  date to 1611, and `data/text_sources.json` credits "Authorized (King
  James) Version, 1611, Project Gutenberg".
- Done now: the displayed name becomes "King James Bible" (display tables
  only, PR to follow this entry).
- Planned: rename the identifier `world_english_bible` to a King James
  identifier in one operation: 70 text files and their tags (`<WEB ...>`),
  the English lemma caches, the English inverted index (`add_texts_to_index
  --replace` plus `drop_stale_index_entries`), 14,335 passage-index rows
  (ids carry the work name), the English Quotation table, the Similarity
  Map cache, `data/translation_pairs.json` (23 pairs name it),
  `backend/scripture_id.py`'s book table, `data/text_genres.csv` and
  `data/text_sources.json`, and the connector's text listing. Run in a
  quiet slot with the next English index rebuild; record here with backups.

## 2026-09-20 English line-search fold fix deployed (PR #418)
- What: `_normalize_lemma` in `backend/app.py` applied the Latin u/v and
  i/j fold to English queries, so "love" was looked up as "loue", "jove" as
  "ioue", "voice" as "uoice": English line searches for any word with a v
  or a j returned only Spenser's spellings or nothing, and the results
  page's "Across the corpus" panel was blank for such shared words. Found
  on Paradise Lost 1.512 x Hyperion 2.182 (jove, saturn). Fold now
  Latin only. Merged e2527dad, pulled on production, WSGI reloaded
  13:45 EDT. No index or cache change.
- Checks after the reload (production API): English "love" 405 lines from
  7 authors (was 500, all Spenser), "heaven" 394 from 8 (was 120 Spenser),
  "voice" 401 from 11 (was 0), "jove saturn" 2 (Milton 1.512, Keats
  2.182; was 0). Latin reference searches unchanged by construction:
  "arma virum" lemma 367 lines (Ovid 14, Vergil 24, Livy 42, Cicero 6,
  Statius 17), exact 21 (Ovid 1, Vergil 4, Quintilian 1, Seneca 1,
  Statius 1).
- Done 2026-09-20 13:45 EDT (main session).

## 2026-09-20 Theme Similarity Map deployed and its production cache built
- What: PR #407 (Theme Similarity Map) merged as c4ec3491 after review of
  the preview; production pulled to c4ec349, the
  frontend bundle rebuilt inside the memory launcher (cap 6 GB,
  `scripts/keep_old_bundles.sh save` before and `restore` after, 33 older
  bundles kept), WSGI reloaded 12:22 EDT. Until the cache existed the Map
  tab reported that no map had been built. Then the production cache:
  ```
  cd /var/www/tesseraev6_flask && ~/bin/tess-job map-cache-build 8 ./venv/bin/python3 scripts/build_connections_map.py
  ```
  wrote `cache/connections_map/22077037-1789824674.1267781760-1789824673.db`
  (920.2 MB; the name is the passage index fingerprint), 280,928 windows,
  26,312 author pairs, 817 century pairs, 258 genre pairs; 27.4 minutes,
  5.77 GB peak under the 8 GB cap. WSGI reloaded again 12:52 so the workers
  saw the new cache; `/api/passages/map?view=author` answers with
  `cache_built_at 2026-09-20T12:50:59` and no `stale` field.
- Standing rule: the map cache is keyed by the passage index fingerprint,
  so it must be REBUILT after every corpus change that touches the passage
  index (imports, retirements, description rebuilds), with the command
  above, followed by a WSGI reload or the "Refresh map" button. Until then
  the site serves the most recent cache and reports it as `stale` in the
  API (users see only the build date).
- Done 2026-09-20 12:22 to 12:52 EDT (main session).

## 2026-09-19 Corpus connections map cache built (feat/connections-map)
- What: `scripts/build_connections_map.py`, under a memory cap, builds
  `cache/connections_map/<index_fingerprint>.db` -- for every Latin, Greek,
  English, Coptic and Hebrew passage window at the fine scale, the top 10
  nearest windows in OTHER works by cosine over the passage index's own
  description embeddings (same signal as Theme Search/Similar Passages),
  excluding the same work, its part files, and other versions of the same
  scripture passage. Writes window-level edges plus work/author/century/
  genre aggregates, and flags translation pairs from a curated seed
  (`data/translation_pairs.json`, 456 pairs: WEB/Septuagint/Greek NT/
  Vulgate, Eobanus's Latin Iliad/Homer, Coptic and Hebrew scripture against
  their Greek/Latin/English versions) plus a heuristic (>=40% of the
  smaller work's windows linked, Spearman of window position >=0.80 --
  candidates not already curated are written to
  `cache/connections_map/aligned_candidates.txt` for review).
  Command:
  ```
  systemd-run --user --scope -p MemoryMax=10G \
      venv/bin/python3 scripts/build_connections_map.py
  ```
- Cost: 38.1 minutes, 5.86 GB peak under the 10 GB cap, 285,307 windows
  (162,757 Latin, 79,118 Greek, 30,155 English, 9,462 Coptic, 3,848 Hebrew),
  2,853,070 edges kept, 122,292 work pairs (390 curated + 153
  heuristic-flagged translation pairs, the rest genuine allusive
  connections), 26,484 author pairs, 817 century pairs, 258 genre pairs,
  db size 935.7 MB.
- Done 2026-09-19 in the `feat/connections-map` worktree (`~/tesserae-map`),
  against the same passage index production reads (symlinked read-only
  from `/var/www/tesseraev6_flask/data/passage_index`); not yet run on
  production. Production needs this run once now, then again after every
  passage-index rebuild (new texts added to the content index, or a
  re-describe) -- the same rhythm the density cache under
  `cache/passage_density/` already follows, since both are keyed off
  `backend.passage_index.index_fingerprint()`.
- Checks: `tests/test_connections_map.py` (17 tests, fixture db) and
  `tests/test_mcp_parity.py` both pass; `/api/passages/map`,
  `/api/passages/map/cell`, `/api/passages/map/pair`,
  `/api/passages/map/work` all verified against the real built cache on
  the preview instance (port 8082).

## 2026-09-18 Theme Search re-ranker service installed (PR #382, with #383)
- What: copy the trained checkpoint
  (evaluation/theme_benchmark/distill_train/runs/minilm/best, 88 MB) to
  /home/ncoffee/tesserae-models/theme_reader_minilm_2026-09-17; install
  services/tesserae-reader.service as a user unit (it runs the script from
  ~/tesserae-scene with the venv that holds torch, the layout of
  tesserae-embed.service; READER_THREADS=16, port 8091, MemoryMax 4G,
  restart on failure), enable and start it, then poll
  http://127.0.0.1:8091/health until it reports loaded_at (the unit shows
  active before the model has loaded); add
  THEME_READER_URL=http://127.0.0.1:8091 and
  THEME_READER_MODEL=minilm-distill-2026-09-17 to the production
  environment the WSGI app reads; `npm run build` from the repo root;
  keep_old_bundles save and restore; `touch tesseraev6_flask.wsgi`.
- Cost inside the request, measured on the preview 2026-09-18 for the dog
  query: window texts for 100 passages 0.9 s, translation lookups 0.2 s
  (35 of 100 had one), reader call about 2 s: about 3.2 s in all on a
  first page. Every page inside the top 100 is cut from the same re-ranked
  list, so a page costs one reader call and results do not move between
  pages; pages past 100 are index order.
- Done 2026-09-18 about 07:07 EDT as ncoffee: PRs #382 and #383 merged and
  pulled (ec32fbf); `npm run build` from the repo root, keep_old_bundles
  save (18 bundles) and restore; checkpoint copied to
  ~/tesserae-models/theme_reader_minilm_2026-09-17 (88 MB); unit installed
  as ~/.config/systemd/user/tesserae-reader.service, enabled and started,
  /health reported loaded_at within 30 s; THEME_READER_URL and
  THEME_READER_MODEL appended to the production .env; wsgi touched. The
  preview's hand-started reader on 8091 was stopped first; both sites now
  use the unit.
- Checks: the dog query returns reader.applied true, model
  minilm-distill-2026-09-17, about 2 to 2.7 s; `&reader=0` returns index
  order; /api/passages/works?language=la returns 765 works; reference
  test 324; new bundle index-CA0n6WsB.js served.
- Found while checking: production's candidate hundred for the dog query
  differs from the preview's because cache/query_expansions.jsonl holds
  different paraphrases on each site (the local Qwen at temperature 0 gave
  different forms on 16 and 17 September), and the paraphrase set decides
  which passages make the hundred. Production's set leaves Odyssey 17.295
  outside the hundred, so the re-ranker cannot promote it there. Not
  caused by this deploy; recorded in research/threads/OUTSTANDING_WORK.md.
- No index, cache or passage-index change. Rollback: unset
  THEME_READER_URL and touch the wsgi file; the page returns to index
  order.
- Checks: `/api/passages/status` unchanged; a Theme Search for "a
  faithful dog greets his master" returns `reader.applied: true` and
  Odyssey 17.295 first; the same with `&reader=0` returns the index
  order; the Cite popover names the re-ranker; reference test 324.

## 2026-09-16 Paradise Lost renumbered in the stores (PR #380)
- What: the text files in git now number every book of Paradise Lost
  1..n (they began at 2 with a duplicated tag a few lines in) and the
  whitespace-only row in Book 4 is gone (1,015 lines; whole file 10,565).
  On production, in this order: (1) `scripts/batch_lemma_cache.py en`
  rebuilt the 13 changed caches (3 s); (2)
  `scripts/corpus/add_texts_to_index.py --replace` with the 13 files after
  one flag on a copy of `data/inverted_index/en_index.db`, then swap
  (whole work 10,565 lines, no duplicate refs; 164 texts, 181,515 lines,
  lemma_doc_freq 38,287; the 30 extra lines are the old duplicates the
  index had collapsed); (3) `scripts/corpus/apply_paradise_lost_numbering.py
  --apply` inside a MemoryMax scope: 138 line refs remapped and 2 blank
  rows dropped in the lines table, 69 of 4,917 windows remapped in
  window_texts.db and descriptions.jsonl, 4 cached results deleted; ids
  and embeddings untouched; (4) `touch tesseraev6_flask.wsgi`.
- Verity commentary: `scripts/corpus/rekey_verity_paradise_lost.py`
  re-keyed the notes to the corrected numbering (of 1,372 lemma notes
  1,295 stayed, 17 moved, 60 unresolved; 95.6 percent agreement with the
  text). The re-keyed file replaces `data/commentaries/verity__milton.paradise_lost.json`
  on the preview and goes to production with the scholarship branch; the
  old copy is kept beside it in the backups directory.
- Backups: `en_index.db.bak-milton-20260916-213923`,
  `window_texts.db.bak-milton-20260916-213929`,
  `descriptions.jsonl.bak-milton-20260916-213929`.
- Checks: reference test 324; `/api/text/milton.paradise_lost.part.1.tess`
  serves 798 lines from 1.1; the part.1 windows start at 1.1; no
  duplicate refs remain in the lines table; Book 4 has 1,015 lines.

## 2026-09-16 The Prelude's Books XII to XIV separated in the stores (PR #378)
- What: the text files in git now carry Books XIII and XIV under their own
  numbers (PR #378: tags 12.337 to 12.1170 became 13.1 to 13.378 and 14.1
  to 14.456; part.12 holds Book XII alone; part.13 and part.14 are new).
  On production, in this order: (1) `scripts/batch_lemma_cache.py en` for
  wordsworth.prelude and its parts 12, 13 and 14; (2)
  `scripts/corpus/add_texts_to_index.py --replace` with the four files
  after ONE flag, on a copy of `data/inverted_index/en_index.db`, then
  swap; (3) `scripts/corpus/apply_prelude_books.py --apply` from the
  production root inside a MemoryMax scope: remaps refs in the passage
  index, moves the part.12 windows that belong to Books XIII and XIV to
  the new part works (ids renamed in window_texts.db, descriptions.jsonl
  and ids.json alike, order and count untouched, embeddings.npy untouched),
  rebuilds the three parts' line tables from the files, deletes cached
  results naming the texts; (4) `touch tesseraev6_flask.wsgi`.
- Dry run against the live stores 2026-09-16 (read only, from a scratch
  root linked to them): whole-work windows remapped 197; part.12 windows
  moved to part.13 88, to part.14 104; 14 windows straddle a new boundary
  and keep both refs; whole-work line refs remapped 834; ids.json 192
  renamed of 625,154; cached results named 0.
- Why ids can be renamed in place: no backend code reads the
  ":scale:ordinal" suffix of a window id as a position (checked
  backend/passage_index.py and grep of backend/ for ':' splitting); the
  suffix is a label, and ids.json's row order is what aligns with
  embeddings.npy, which the script never reorders.
- Run 2026-09-16 18:51 to 18:53 as ncoffee from the production root inside
  `systemd-run --user --scope -p MemoryMax=…`. `batch_lemma_cache.py en`
  built 139 English caches (only 25 of 164 existed; 13 s). The index step
  replaced text_ids 9 (whole, 56,251 postings) and 50 (part.12, 336 lines)
  and added 164 (part.13) and 165 (part.14); lemma_doc_freq rebuilt
  (37,595 lemmas). The store script's counts matched the dry run exactly.
- Backups: `en_index.db.bak-prelude-20260916-185244`,
  `window_texts.db.bak-prelude-20260916-185206`,
  `descriptions.jsonl.bak-prelude-20260916-185206`,
  `ids.json.bak-prelude-20260916-185206`.
- Results: reference test 324 distinct loci; `/api/text/wordsworth.prelude.part.14.tess`
  serves 456 lines from 14.1; English exact search "hoary mist" returns
  14.42; Theme Search for the Snowdon ascent returns Prelude 14.17 and
  part.14 14.49 at the head; the English text list shows parts 13 and 14.
- Checks after: reference test ("arma virum" 324); Reader opens Prelude
  13.1 and 14.1 under the new tags; a Theme Search hit in Book XIV shows a
  14.N reference; `part.13` and `part.14` appear in the English text list.

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
- Backups: `la_index.db.bak-editions3-20260913-084715` (the index the
  live one was built from; two earlier attempts left `bak-editions-20260913-083836`
  and `bak-editions2-20260913-084233`), `window_texts.db.bak-editions-20260913-083836`,
  `descriptions.jsonl.bak-editions-20260913-083836`,
  `la__lucretius.de_rerum_natura.json.bak-editions-20260913-083836`,
  `la_bigrams.json.pre-rebuild-20260913-0839.bak`.
- What went wrong and was fixed the same morning: (1) the batch cache
  builder reported eight caches built while two (Lucretius books 1 and 2)
  had failed silently because their files belonged to the web app's
  account; the two were rebuilt by hand and the writer is fixed in #375 to
  write beside the file and rename, and to count a failed save as an
  error. (2) `add_texts_to_index.py --replace` takes every filename after
  one flag; repeating the flag keeps only the last name, so the first run
  replaced Lucan alone. The final run replaced all eight and was verified
  on the copy before the swap (no row with the old tag form; book 1 with
  1,117 lines of the Perseus text).
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
- Backups: `*_index.db.bak-docfreq-20260913` (interim),
  `la_index.db.bak-docfreq-20260913-082107` and
  `grc_index.db.bak-docfreq-20260913-082424` (canonical swap).
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
- Note: review of the result recommended a design change (a separate
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
  repaired Lactantius text confirmed the restoration; the reported
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
  after. A live search on a passage flagged as missing confirmed the
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

## 2026-10-20 RUN 22:57 EDT Attic inscriptions: People & Places links, event documents, text repairs, corrected event coordinates (built by a delegate, installed by the project lead)

**Run record.** Pull request #1089 merged and deployed at 22:56 after one lint stop (four findings, fixed). Before installing, the project lead checked that the copies were built from the current live files: the People & Places copy has the same 42,356 entities, 1,433,633 mention rows and the identical 600,977 document-mention rows as the live store, plus 2,674 AIO rows; the events copy has the same events, passages, scholarship rows and the identical 14,435 Claude ratings, with document rows 12,513 to 14,372. Twenty rows of the delegate's 100-row sample were read again with another seed and agreed with its grading (95 right of 100). Installed at 22:57 with backups `.bak-aiolinks-20261020` of `grc_documents_index.db`, `entities.sqlite` and `event_dossiers.sqlite`, the restored-words file replaced, `metadata.db` left as it was (the copy is identical). Checks: `/api/languages` 200; the three Sieges of Athens list 115, 114 and 75 documents; the Battle of Actium sits at 38.925, 20.725 and now lists no documents, because no document dated within fifty years of 31 BCE lies within 100 km of Actium (the stones listed before were in southern Italy, near the old point in the Ionian Sea); the Sicilian Expedition sits at Syracuse with 44 documents; aio:IGII34_165 reads Ἀπόλλωνι; Rhamnus answers in People & Places.


**Status.** Built on copies, not installed. Copies and checksums are in `~/tesserae-backups/aio_links_2026-10-20/install/` (`SHA256SUMS.txt`). Nothing under `/var/www` was written.

What. (1) Text repairs in the Berlin and AIO Greek (`scripts/documents/aio_convert.py`): a dash followed by the continuation sign (Apollo / ni of IG II3 4, 165), a dash after a letter with a dot under it, a plain hyphen before a letter at a line end, and letters set apart (IG I3 1147 gives "τ αὐτ ἐνιαυτ") are joined. 148 of the 2,641 documents change, ids and row count are the same (714,442 lines, 75,916 doc_meta rows), the other 711,801 lines are identical, the metadata copy is identical to the live one. No word was joined by vocabulary: the strict rule found none. (2) 2,674 added `document_mentions` rows for 1,221 AIO documents and 230 entities, from 10,958 candidate rows by twelve rules (counts in the pull request); the 600,977 existing rows are unchanged byte for byte, the fingerprint is that of the new documents index. (3) Events: 45 events get the corrected point and their dated rows recomputed from all sources (525 rows replaced by 125), 2,054 AIO dated rows are added in 83 events, 205 more naming rows in 53 events (events documents rows 12,513 to 14,372). Actium has no document within 100 km of its true point dated within 50 years, so it has none now.

Install order, by the project lead, with dated backups of each file first: (a) the documents index `grc_documents_index.db`, `metadata.db` (identical, optional) and `aio__attica.restored_words.jsonl` into `documents/restored/grc/`; (b) `entities.sqlite` into `entity_index/`; (c) `event_dossiers.sqlite` into `events/`. Copy under a temporary name at mode 664, rename, touch `tesseraev6_flask.wsgi`, check `/api/languages` (200), `/api/documents/aio:IGII34_165?language=grc` (Apollonι joined), one People & Places search for Peiraieus and one event page (Battle of Piraeus).
