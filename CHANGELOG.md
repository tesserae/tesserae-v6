# Tesserae V6 Changelog

Newest first. Every pull request adds a line here; production data
operations that are not code (index rebuilds, cache rebuilds, corpus
repairs) are listed under "Data operations" with the script that did them,
so the state of the live site can be reconstructed from this file and
docs/DATA_OPERATIONS.md.

## 2026-09-19

### Reader
- Navigation inside a text: a thin strip stays at the top of the text column
  with previous and next book, a Go to line box (a locus such as 6.851, or a
  bare line number within the open book) and Back to top, and the book links
  repeat at the end of the text. Until now the only way out of the bottom of a
  long book was a scroll back to the header.
- The side panel (Similar Passages, Verbal Parallels, Translation, Reuse) now
  stays on screen while the page scrolls. Its sticky rule had been cancelled
  by the outer card's overflow clipping since the Reader shipped, so deep in a
  text the panel sat above the fold and looked absent.

### Infrastructure
- The Python test workflow on main had failed since the Theme Search re-ranker
  merged: the security scan flagged the re-ranker client's URL open. The client
  now refuses a THEME_READER_URL without an http or https scheme and the scan
  line is marked as checked. No behaviour change for the configured service.

### Reader
- Similar Passages in the Reader showed the raw work id ("quintus_smyrnaeus.fall_of_troy")
  instead of a proper title. The passage index already sends author, title and
  display_name from `get_text_metadata` -- the same source Browse Corpus and
  Theme Search use -- but the Reader's card built its own rough label from the
  id instead of reading them. It now reads `display_name`, falling back to the
  old label only for a response that predates the field.
- Corpus-wide reuse table and "Reuse" tab: a small mark beside a line the
  corpus repeats verbatim elsewhere ("quoted in N works" on hover) opens a
  new Reuse tab beside Similar Passages, Verbal Parallels and Translation,
  listing the repeating lines grouped by work, newest-first by author date
  where known. Built from `scripts/reuse/build_reuse_table.py --language la`
  (ported from the `research/reuse_table/` prototype, containment-gated
  n-gram matching, see `research/reuse_table/REPORT_2026-09-18.md`), reading
  `texts/la/` as the live corpus so retired files are excluded automatically;
  writes `cache/reuse_pairs/la.db`. First run: 679 works, 516,458 lines,
  52,855 pairs kept in 419s under a 12G cap (98 live files skipped, Gellius
  among them, because the loader guessed the plain `<work>.json` cache
  filename instead of resolving the hashed name). Fixed to call
  `backend.lemma_cache.get_cached_units` and rebuilt: 777 works, 652,003
  lines, 62,265 pairs kept in ~30 minutes, 0 works skipped for missing
  cache; see docs/DATA_OPERATIONS.md and
  `research/reuse_table/REPORT_2026-09-18_production_build.md`. New endpoints
  `GET /api/reuse/line` and `GET /api/reuse/marks`
  (`backend/reuse_table.py`, `backend/blueprints/reuse.py`), registered
  site_only in `mcp_manifest.py`. Backend tests
  (`tests/test_reuse_routes.py`) and Vitest
  (`client/src/components/reader/ReuseTab.test.jsx`,
  `TextPane.reuse.test.jsx`). Help page: new Reuse paragraph under the
  Reader topic.

### Theme Search
- #388 The list of covered works is reachable, not just a checkbox in Browse
  Corpus: `/corpus?theme=1&language=la` opens Browse Corpus with the filter
  and language already set, with a heading, a Copy list button, and a
  Download list button for the works on screen. The Help page's Theme
  Search topic links to it, and the Theme Search page itself shows how much
  of the current language it reaches, with the same link (only when exactly
  one of the four Browse Corpus languages is selected). Verified against
  production: 765 of 782 Latin works covered, computed identically by both
  pages off one shared helper (`client/src/utils/passageCoverage.js`); a
  new App-level test confirms the `/corpus` deep link's query string
  survives the rewrite to the real route, `/browse`.
- The covered-works link (#388, above) only showed with exactly one of the
  four Browse Corpus languages selected, so the default "All languages"
  view had no link at all. The line under the language row now always
  shows: the per-language sentence stays for one covered language, a
  summed sentence ("Theme Search covers N works in 4 languages") for the
  default or several languages picked together, and a fixed sentence for
  a language Browse Corpus doesn't index (Hebrew, Persian, Urdu). The link
  always goes to the Latin list, `/corpus?theme=1&language=la`. Review
  follow-up: the single-covered-language sentence was still gated on
  `coverage.total > 0`, so a covered language with a zero or not-yet-loaded
  count rendered none of the three sentences; it now shows a loading
  sentence while unresolved and the fixed four-language sentence if the
  count resolves to zero. The summed fetch also used to run on every
  mount regardless of the picker; it now runs only the first time the
  summed or fixed sentence is actually needed, and `language`'s initial
  value is read synchronously from a shared link's `languages=` param
  (rather than set later in an effect) so that check is accurate on the
  very first render.

### Corpus
- Retire the Eugippius duplicate and resegment Ennodius Book 2 (batch 3):
  `eugippius.excerpta_ex_operibus_augustini` (correctly spelled, but drops
  the real Augustine wording for 183 of 390 excerpts in favor of one-line
  summaries) is retired; `eugippius.exerpta_ex_operibus_augustini`
  (misspelled filename, kept, has complete text for all 390) gets its
  displayed title corrected in code so the misspelling never surfaces.
  `magnus_felix_ennodius.carmina` (152 Book 2 poems stored one whole poem
  per line) is retired and replaced by `magnus_felix_ennodius.carmina_2`,
  rebuilt at proper one-verse-per-line granularity directly from the
  edition's own EpiDoc XML source, which also recovers a poem missing from
  the old file and drops a miscoded apparatus line. See
  docs/DATA_OPERATIONS.md for the excerpt-containment check, the
  verse-by-verse verification, and the registries edited. Archived:
  `~/tesserae-backups/retired_duplicates_2026-09-19b/`.
  Also checked whether the Sodoma and Iona poems, each transmitted under
  both a Cyprian and a Tertullian attribution, are duplicate copies:
  `tertullian_pseudo.de_sodoma`/`cyprian_pseudo.sodoma` and
  `tertullian_pseudo.de_iona_propheta`/`cyprian_pseudo.de_iona` both run
  around 53% word-chunk containment (well below the 90%+ seen for genuine
  same-edition duplicates elsewhere in this document, and the differences
  are word-choice-level, not OCR-level), so both pairs are kept as distinct
  recensions rather than deduplicated. Removed three orphaned
  `backend/text_sources.json` citation entries found while checking
  credits for this comparison.
  Also preserved the two Book 1 prose items flagged when the whole-poem
  file was retired: they turn out to be prose prefaces ("Dictio Ennodi
  diaconi quando de Roma rediit" and "Fausto Praefatio") attached to poems
  6 and 7, whose verse is already covered by `ennodius.carmina.tess`; the
  prefaces themselves are not duplicated anywhere, so they are kept in a
  new file, `magnus_felix_ennodius.carmina_1_praefationes.tess` (2 lines).

- Retire two more duplicate Latin files (batch 2):
  `juvencus_caius_vettius_aquilinus.evangeliorum_libri_quattuor` (whole
  books stored one per line; `juvencus.historia_evangelica` already
  carries the same poem at per-verse granularity) and
  `pseudo_cyprian.carmina` (a six-poem bundle; five of its six poems
  already exist as separate, per-verse `cyprian_pseudo.*` files, kept).
  Also dropped a stale `data/text_genres.csv` row and a stale
  `backend/text_sources.json` entry left over from the 2026-09-18 batch,
  for a file already gone. See docs/DATA_OPERATIONS.md for the containment
  checks and the registries edited. Archived:
  `~/tesserae-backups/retired_duplicates_2026-09-19/`.

- Retire 40 duplicate Latin files, rebuild Martial from the per-book files:
  `martial.epigrams` and its 14 `.part.N` files, missing dozens of epigrams
  per book, are rebuilt from the 14 `martialis.epigrammata_N` files that
  held the complete text (6,399 verse-lines to 9,375); those 14 per-book
  files and 26 other duplicate or stray files are retired (40 total; see
  docs/DATA_OPERATIONS.md for why the file count and the "33" the source
  report used disagree, a count the merge commit's own title (`de8863e`,
  "(#389)") carried forward unchanged). Archived, not deleted outright:
  `~/tesserae-backups/retired_duplicates_2026-09-18/`.

- #390 Fixed the coverage list going blank mid-deploy. Right after a deploy
  reload, each Apache worker loads the 2GB passage index on its first
  request (about 90 seconds), and `/api/passages/works` used to answer
  slow or empty during that window, which Browse Corpus and Theme Search
  both read as "0 of 782 works are covered" -- indistinguishable from a
  real gap. The route now reads a small `works_by_language.json` sidecar
  next to the index first, falling back to loading the full index only
  when that file is missing or stamped with a different index version;
  the sidecar is written by the index merge script
  (`scripts/merge_index.py`) and, as a backstop, by whichever worker loads
  the index first. On the client, both pages retry a failed or empty
  coverage fetch once at +3s and once more at +10s, and show "Theme
  Search coverage is loading" instead of asserting "0 of N" while that is
  still unresolved.

## 2026-09-18

### Theme Search
- #382 The re-ranker: a small model trained once on 32,000 readings by a paid
  model reads the top hundred results against the query and re-orders
  them. Judged precision in the top ten on sixteen test themes rises from
  0.42 to 0.59 (the paid reader itself reaches 0.71); every scene query
  and every sealed Curtius topos improved. It runs as its own service
  (`services/reader_server.py`, port 8091, the pattern of the query
  encoder) so the web application never loads the model, adds about three
  seconds to a first-page search, and when it is down or slow the page
  comes back in index order with no error. `?reader=0` shows the old
  order. The reproducible citation names the re-ranker's version.
  Records: evaluation/theme_benchmark/distill_train/REPORT.md.

- Query expansion removed from Theme Search retrieval (`find_by_text`
  defaults to `expand=False`): measured no effect on 15 of 16 test queries
  and, on the one it touched, it pushed a right answer out of the top
  hundred before the reader ever saw it
  (evaluation/theme_benchmark/expansion_test/REPORT.md). Help page's
  reading-step figures corrected from 42/59 percent, measured on a
  different candidate set, to the live page's own 29/43 percent on the
  same sixteen test themes.
- #385 Help: names are precise and paraphrases broad in Theme Search, and
  what to type when a search finds little (from a user report).
- #383 Browse Corpus marks every work Theme Search covers with a "Theme
  Search" badge, shows how many of a language's works are covered, and can
  list only those; the Help page says what the index holds.

### Data operations
- The re-ranker service installed and switched on (detail in
  docs/DATA_OPERATIONS.md, 2026-09-18).

## 2026-09-16

### Corpus
- #380 Milton, Paradise Lost: every book now runs from line 1. The file
  had begun each book at 2 with a duplicated number a few lines in, so
  the opening lines were cited one too high and Verity's notes missed
  them; a blank row in Book 4 is gone. `scripts/corpus/apply_paradise_lost_numbering.py`
  brought the stores into line (data operation below) and
  `rekey_verity_paradise_lost.py` re-keyed the commentary.
- #378 Wordsworth, The Prelude (1850): Books XIII and XIV get their own
  numbers. The file had run them together under Book XII, so a line of the
  Snowdon ascent read "Prelude 12.900". Part files 13 and 14 added, part 12
  cut to Book XII; `scripts/corpus/apply_prelude_books.py` brought the
  passage index and the English index into line (data operation below).

### Data operations
- Paradise Lost refs remapped in the passage index (69 windows, 138 line
  refs, 2 blank rows dropped), English lemma caches and index updated for
  the thirteen files.
- The Prelude's refs remapped in the passage index (197 whole-work windows,
  192 part windows moved to the new parts, ids kept in embedding order),
  English lemma caches rebuilt (139 had been missing), English index
  updated for the four files with document frequency rebuilt.

## 2026-09-13

### Help
- Help gains "How well does it work?": one dated, measured figure per
  search and language (Latin, Greek, Coptic, Hebrew, English, Cross-Language,
  Theme Search), with "not measured" where that is the truth, and a
  standing invitation under each language for specialists' feedback and
  help; articles with full details are noted as in preparation.

### Corpus
- Lucan, Bellum Civile: six misreadings in the whole-work file corrected
  from its book files ("vitum" to "victum", "Tentates" to "Teutates" and
  four more); whole and books now agree line for line.
- Lucretius, De Rerum Natura: the six book files, which came from a
  different (Latin Library) edition with transposed lines, are regenerated
  from the Perseus whole-work file (Leonard), and the whole file's tags
  take the site's usual form "lucr. 1.1". One edition, one citation form.
  `scripts/corpus/apply_lucretius_lucan_editions.py` brings the passage
  index, the translation map and cached results into line.

### Fixes
- #375 Lemma cache saves write beside the file and rename over it, and a
  failed save is logged and counted as an error; files owned by another
  account had made saves fail silently.

### Data operations
- Document frequency restored to the canonical one-document-per-work rule
  in the Latin and Greek indexes (book files collapse to their base work;
  Latin 782 works, Greek 853). The stale-entry drop of the day before had
  recomputed it per file. Scripts touching the table now all call
  `build_lemma_doc_freq`. Found on the way: the book files of Lucretius and
  of Lucan come from a different edition than their whole-work files.

## 2026-09-12

### Corpus
- #371 Repaired malformed line tags in 54 files (double space, doubled
  period: `<sal.  Cat..58.15>` is now `<sal. Cat. 58.15>`), 32,256 tags,
  text unchanged; `tests/test_tess_tags_clean.py` lints every corpus file.
- #372 `scripts/corpus/repair_ref_tags.py`: fixes from the production run
  (atomic writes, unique backup stamps, duplicate-heading handling).

### Data operations
- The same repair applied to every store that had copied the raw tags:
  lemma caches, Latin and Greek inverted indexes, passage index
  (descriptions and window texts), 41 translation maps, one cached result.
- Stale index entries dropped: 33 Greek (old Septuagint leftovers, retired
  duplicates, renamed Philo works) and 1 English.
  `scripts/corpus/drop_stale_index_entries.py`.
- Rare-bigram caches rebuilt from the corpus for Greek (610 to 900
  documents) and Latin (899 to 812; retired duplicates no longer counted).
  `scripts/corpus/rebuild_bigrams.py`.

### Decisions
- Poem-level book files (Catullus, Horace, Juvenal, Vergil and others; 178
  files) stay out of the inverted index: indexing them beside the whole
  works would inflate document frequencies (NC, 2026-09-12).

## 2026-09-11

### Ports from the preview branch (general improvements, no new language)
- #367 Fusion-route fixes (context confirmation once per search, compute at
  the storage cap, meter decided server-side); Tessa reads the top 25, 100
  or all loaded parallels and says so; Cite button with a reproducible
  reference, MLA and Chicago, and a corpus-version stamp on fusion and
  Theme Search responses; interface audit (contrast, one focus ring, phone
  tab-strip fade, link previews, page titles, Theme Search query in the
  address with Copy link, screen-reader labels); Theme Search offers any
  set of languages.
- #368 Reader on phones (bottom sheet, tap to select), long texts drawn in
  1,000-line stretches, selection fixes; #370 hotfix limits the Reader's
  index-lemma shortcut to Persian, Urdu and Arabic after it changed Latin
  results.
- #369 Scorer: a synonym pair scores in the dictionary channel again
  (benchmark 781 to 788 of 862).

### Connector
- #366 References are cleaned before the connector shows them, and
  passage lookups accept the cleaned form.

## 2026-09-10

### Corpus
- #360 Curtius batch: Greek Anthology (16 books), Tiberianus, Pentadius,
  Prudentius Cathemerinon, Matthew of Vendome, Geoffrey of Vinsauf,
  Eberhard the German, Peter Riga, complete Carmina Burana, Aelian re-cut
  by sentence; Greek lemma-cache normalisation fixed.
- #362 45 duplicate texts retired (weaker copy of each pair).
- #363 Paton's Greek Anthology translation aligned (76.5%); #365 Pope's
  Prudentius aligned (99.4%); #364 Aeschines Against Ctesiphon trimmed to
  the speech.

### Assistant and connector
- #355 to #359 Tessa prose and guards (plain verdict words, no arithmetic,
  no speculation about access, cleaner citations, caveat wording).
- #361 Connector parity with the site, with a parity test.

---

# Earlier (January to February 2026, as first written)

## Published (January 26, 2026)

Initial public release of Tesserae V6 at https://tesserae-v-6.replit.app

### Features
- Phrase search with V3-style scoring (IDF + distance penalties)
- Corpus-wide line search across 800,000+ indexed lines
- Rare word pairs search with bigram frequency analysis
- Rare words explorer with dictionary definitions
- Cross-lingual search (Greek-Latin) using SPhilBERTa embeddings
- Intertext repository for saving and sharing discovered parallels
- User authentication via Replit OpenID Connect with ORCID linking
- Metrical scansion display from MQDQ/Pede Certo data
- Text viewer with highlighted matches
- CSV export for search results
- Saved searches (localStorage)
- Shareable search URLs

### Corpus
- 1,444+ Latin texts
- 650+ Greek texts
- 14+ English texts

---

## Pending

Changes made after the January 26, 2026 release, awaiting next deployment:

### Fusion Search (February 21–22, 2026)
- **9-channel fusion search** available as "Fusion — All Channels (best recall)" in match type dropdown
- Combines lemma, lemma_min1, exact, edit_distance, sound, semantic, dictionary, syntax, and rare_word channels
- Weighted score fusion with convergence bonus (Config D weights)
- Two-pass line/window architecture: line pass (all 9 channels) + window pass (4 channels: lemma, lemma_min1, rare_word, dictionary) for enjambed allusions
- Syntax channel restored using syntax_latin.db (542K pre-parsed lines, lemma-inverted-index pruning)
- SSE streaming with per-channel progress updates
- Channel badges on results showing which channels found each pair
- Fused score display and sorting
- Per-channel result capping (top 50K per channel before fusion)
- Internal parallelization of edit_distance and sound channels (8 worker processes)

### Fixes
- Rare Words Explorer: Fixed asterisk display issue in lemma column
- Rare Words Explorer: Added author and work columns (previously empty)
- Rare Words Explorer: Added clickable links to text viewer for each location
- Corpus-wide line search: Fixed highlighting to show all matched word forms (not just exact lemma matches)
- Rare Words Explorer (Greek): Added diacritics lookup for Greek lemmas using corpus text forms
- Repository: Fixed word highlighting using platform-standard u/v normalization (consistent with matcher.py)
- Rare Words Explorer: Fixed "First Work" column to show properly capitalized work title (client-side formatting)

### Enhancements
- Repository: Added submitter attribution showing name AND ORCID when both available
- About page: Added automatic "Last Updated" date (reads from git)
- Created CHANGELOG.md for version tracking
- Enhanced article methods draft with feature examples and benchmark testing sections
- Repository: Simplified status system (flagged/normal instead of pending/confirmed)
- Repository: Added hierarchical "By Work" browse view (Language→Author→Work)
- Repository: Added flag toggle button for logged-in users
- Repository: Added 500-character limit on contributor notes
- Rare Words Explorer: Mobile-responsive layout with compact headers

### Documentation
- docs/ARTICLE_METHODS_DRAFT.md: Comprehensive methods article featuring Vergil-Lucan parallel case study

---

## Version History

| Version | Date | Notes |
|---------|------|-------|
| 6.0 | January 26, 2026 | Initial public release |
