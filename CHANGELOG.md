# Tesserae V6 Changelog

Newest first. Every pull request adds a line here; production data
operations that are not code (index rebuilds, cache rebuilds, corpus
repairs) are listed under "Data operations" with the script that did them,
so the state of the live site can be reconstructed from this file and
docs/DATA_OPERATIONS.md.

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
