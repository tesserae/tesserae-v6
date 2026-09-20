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
  Ennodius pairs the batch 2 source document had left unretired. NC approved
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
- What: NC asked whether `tertullian_pseudo.de_sodoma.tess` /
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
- What: NC asked not to drop the two Book 1 prose items flagged in Part B
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

### Part D verification addendum: two checks NC asked to confirm
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
  and approved by NC on 2026-09-19; the other four were left alone (two
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
  safe to retire; NC additionally decided to retire a further "stray
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
## 2026-09-20 English line-search fold fix deployed (PR #418)
- What: `_normalize_lemma` in `backend/app.py` applied the Latin u/v and
  i/j fold to English queries, so "love" was looked up as "loue", "jove" as
  "ioue", "voice" as "uoice": English line searches for any word with a v
  or a j returned only Spenser's spellings or nothing, and the results
  page's "Across the corpus" panel was blank for such shared words. Found
  by NC on Paradise Lost 1.512 x Hyperion 2.182 (jove, saturn). Fold now
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
- What: PR #407 (Theme Similarity Map) merged as c4ec3491 after NC's
  review of the preview ("looks good"); production pulled to c4ec349, the
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
