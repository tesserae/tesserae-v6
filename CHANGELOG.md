# Tesserae V6 Changelog

Newest first. Every pull request adds a line here; production data
operations that are not code (index rebuilds, cache rebuilds, corpus
repairs) are listed under "Data operations" with the script that did them,
so the state of the live site can be reconstructed from this file and
docs/DATA_OPERATIONS.md. Method and scoring decisions, with the measurement
behind each, are in docs/DECISIONS.md.

## 2026-09-21

### Search
- How a multi-part work is collapsed to its own name is now decided in one
  place instead of fourteen. Three different rules were in use and one of
  them was wrong: it required the part number to end the name, so the 215
  files whose part carries a label, such as Pindar's Nemeans or the books
  of the Vulgate, were never recognised as belonging to their work. Their
  descriptions, translations and counts were looked up under a name nothing
  holds. Nothing errored, which is why it went unnoticed.

### Reader
- The Reader says why it is waiting. Opening a text for the first time takes
  a few minutes to work out where the rest of the corpus connects to it,
  because every passage in the text is compared with the whole corpus. A
  note now appears after a few seconds, names the text, and says the wait
  happens once. Nothing appears for a text whose answer is already stored,
  which is the usual case and returns instantly.
### Search
- Latin u and v, i and j are now decided in one place instead of five. The
  rules had drifted apart, so the same two words could count as the same in
  one part of a search and different in another. Two real effects, both
  measured on the corpus: a function word spelled with a j, such as the
  1,691 occurrences of "jam" for "iam", was not recognised as a function
  word and was matched on as though it carried meaning, 1,705 occurrences in
  all; and a word at the start of a line, which editions capitalise, did not
  match its own lemma when the distance between matched words was measured,
  so pairs were measured from the wrong place. Searching the printed text
  keeps its own rule, including the old spelling of "divom" for "divum",
  which must not be applied to a dictionary lookup: the dictionary has both,
  and they are different words.

### Site
- The "Saved Searches" button on the search page opens its dialog again. It
  had done nothing at all when clicked: the dialog was rendered without the
  one property that tells it to draw itself, so it returned nothing and no
  error appeared anywhere.

### Repository
- New text files are visible to git again. `texts/` was ignored wholesale,
  which never untracked the 3,484 files already committed but silently hid
  every new one: an imported text did not show up in `git status`, was
  skipped by `git add texts/`, and was never committed, while the index
  build and the deploy after it behaved as though it had shipped. The
  languages that ship are now listed one by one; Persian, Urdu and Arabic
  stay ignored on purpose, as do scratch folders inside a language
  directory, the runtime caches and the pre-computed embeddings (those are
  recomputable, and a run writes gigabytes).
- The developer and contributor guides no longer tell you to build the
  front end with `cd client && npm run build`, which cannot work: there is
  no `package.json` under `client/`, and the build runs from the repository
  root.
### Internal
- About 970 lines of `backend/app.py` deleted: 24 web-address handlers that
  Flask could never reach, because the blueprint files registered the same
  addresses earlier in the same file. They had drifted from the live
  versions (the dead admin routes checked a weaker password path), so
  anyone debugging one of those addresses could have read, changed and
  tested the wrong function without noticing. Every remaining address was
  checked to answer with exactly the same function as before, in both
  deployment modes.

### Site
- Tessa, the assistant, was mounted twice on every page: two copies asked the
  assistant service for its status on each page load, shared one stored
  conversation, and drew the floating button on top of itself. One copy now.
- The popup used for Save Parallel, adding or editing an intertext in the
  Repository, and the rare-word definition viewer now announces itself as a
  dialog, and pressing Escape closes it. Opening it moves the keyboard focus
  inside, tabbing no longer escapes into the page behind it, and closing it
  returns focus to whatever button opened it. None of this changes how the
  popup looks or works with a mouse.
- The highlighted tab in the top navigation and the language row is no longer
  shown by color alone: it now also reads slightly bolder, and screen readers
  are told which one is selected. No layout change.

### Theme Search
- The Similarity Map on a phone: the column of work names took a fixed 190
  pixels, leaving about 200 for the map itself. On a narrow screen the names
  now take a third of the width and truncate to fit, and the slanted labels
  along the top truncate sooner, which also lowers the header strip. Desktop
  is unchanged.
### Corpus
- Eighty-seven damaged lines repaired in book files, found by comparing
  every work's whole file with its book files. Greek words inside Pliny's
  Natural History (77 lines) and three lines of Claudian were mojibake, the
  usual symptom of a file read in the wrong character encoding; Philippic 7
  was missing the opening bracket of its first line, so that line was not
  indexed from that file; three lines of Orosius carried the author's name
  twice in their reference; and Galen's first book was missing its first
  line. In every case the work's whole file already had the sound version,
  which is what the repair uses.
- A shared helper (`scripts/corpus/corpus_safety.py`) now gives any
  corpus-mutating script the three things the safety convention in
  `docs/DATA_OPERATIONS.md` asks for: a dry run by default, a dated backup
  that a rerun never overwrites, and a write-beside-and-rename swap that
  never leaves a half-written file. The audit of 2026-09-21 found that
  fewer than half the scripts under `scripts/corpus/` followed the
  convention, including `fix_hebrew_clitic_spacing.py`, which overwrote a
  `.tess` file in place with no backup at all. That script and
  `repair_lactantius_placidus.py` now use the helper; both were checked
  against the pre-change scripts on fixture data and produce byte-for-byte
  identical output when run with the new write flag.

### Language names
- Browse Corpus and the Rare Words Explorer showed the raw code "he" or "fa"
  in their headings instead of "Hebrew" or "Persian" whenever those
  languages reach those pages, and the admin Corpus Metadata table showed
  "English" for every Coptic or Hebrew work. A code review found the site
  had accumulated a dozen separate places that each spelled out their own
  list of language codes and names by hand, several missing the newer
  languages and one (an admin analytics export) calling Persian "Farsi"
  where the rest of the site says "Persian." All of them now read from the
  one shared list. Browse Corpus's era filter had also drifted from the
  site's own era list: English's "18th Century" option matched no work,
  since the site tags that period Neoclassical or Augustan, so it now reads
  from the same shared list too and offers the eras that are actually there.
### Corpus Browser and Rare Words Explorer
- Hebrew is now a tab on both pages, placed after English and before
  Coptic, matching the order already used in the Reader's language picker
  and Theme Search's language checkboxes. Both pages hardcoded their tabs
  to Latin, Greek, English and Coptic even though Hebrew has shipped
  elsewhere on the site since August, so it was unreachable from either
  page.
- The Rare Words Explorer can actually show Hebrew now. Its list is built
  by a step on the server that had a rule for Latin, Greek, English and
  Coptic and none for Hebrew, so it produced an empty list: the page would
  have shown a Hebrew tab with nothing in it. Hebrew words counted ten
  times or fewer in the corpus now qualify, leaving out single letters,
  transcription marks and the curated list of function words.
- Corpus Browser's era filter offers Biblical for Hebrew instead of
  falling back to the Latin era list, which is what happened before the
  filter had a Hebrew entry at all (the same gap already fixed for Coptic
  in a prior release). The live Hebrew corpus is 39 Hebrew Bible books, all
  one era, so Biblical plus Unknown is the whole list for now.
- Both pages now read language display names from the shared
  `languageNames.js` helper instead of a local, hand-rolled copy that did
  not know about Hebrew.
- The Rare Words Explorer's dictionary link sent every non-Latin,
  non-Greek, non-Coptic, non-English word to Logeion, a Greek and Latin
  lexicon; Hebrew words now link to Wiktionary instead, as English words
  already do.

## 2026-09-20

### Reader
- Works held in books open one book at a time: a whole-file work that also
  exists as book files (the Punica, the Aeneid, the Iliad and about 130
  others) opens on the book that holds the requested line, or on Book 1,
  so the books no longer run together and the previous/next links apply.
- A floating navigator at the bottom left of the window (to the top, to
  the end, previous and next book) that stays on screen wherever the
  reader is in the text.
- The gutter key now explains the numbered boxes: the count of other works
  that quote the line, click to see them.
- A passage opened from the Similarity Map says so and links back to the
  map; its link used to re-run "connections map: Vergil" as a Theme Search.
- The Read tab, clicked while the Reader is open, takes the Reader back to
  its starting page; it used to do nothing.
- Which book holds a line is now looked up by the server in the book files
  instead of read off the line number, which was wrong for Alcuin and
  Theodulf (a book file may hold several poems), the Verrines (part 3 is
  actio 2 book 2) and Hyperides (whole file and parts tag lines
  differently); book files with a suffix after their number count too.
- In Verbal Parallels a Latin word spelt with v or j is marked even when
  the match was reported in the other text's u or i spelling ("catervas"
  for "cateruas").
- The key above the text keeps "darker = more connections" with the two
  gutter colours it describes, and names both forms of quotation box:
  solid for a quotation, dashed for a possible echo (one rare shared
  phrase).

### Help and About
- The Reader help describes the quotation boxes (solid and dashed), the
  Reuse tab, reading a work book by book and the floating navigator; its
  gutter key text matches the key on the page (colours, not the old W and
  C letters). The Translation tab note says translators are named under
  each passage and that a few open non-commercial translations are used
  with attribution.
- The Sources page has a Translations block: the translation policy in
  plain words and, on request, the list of every translated work with its
  translator, per language, drawn from the same files the Reader credits.


### Theme Search
- The reader client's timeout grows with the rows sent (6 s for 100,
  12 s for 300). A fixed 6 s cut the 300-row call off just as it
  answered, so for nine minutes after the depth change every Theme Search
  ran without the reader; the depth was set back to 100 through the
  environment while this was fixed.
- The reader re-scores the whole composed list (about 300 rows), not its
  first hundred, so a work whose rows sat past the hundred can reach the
  page: the Odyssey's recognitions on "a wife or child recognizes someone
  long thought dead or lost" were at rows 146 to 148 and land at row 15.
  Precision neutral on the 16-query benchmark (0.444 against 0.453 with
  the lexical boost at 100 rows); about 9 s a query instead of 4 s.
- A word index over the passage descriptions (SQLite FTS5, BM25;
  `scripts/build_desc_fts.py`) adds a small lexical boost to the embedding
  similarity, so a description that shares words with the query rises a
  little. Measured on the real code path on the 16-query benchmark:
  first-ten precision 0.434 to 0.453, the four held-out topoi 0.325 to
  0.375 (docs/DECISIONS.md, 2026-09-20). The index is rebuilt after every passage-index change; the
  app refuses a stale one and runs without the boost, saying so in its log.
- Dates for the Nibelungenlied (c. 1200), the Chanson de Roland (c. 1100)
  and Dante (d. 1321), which had none because their languages were absent
  from the date table; and a work with an era but no year (the Hebrew
  Bible, "Biblical") shows the era instead of "undated".

- Sample searches re-measured on production: the recognition query (rated
  moderate, and it misses the Odyssey) is replaced by "funeral games with
  athletic contests held in honor of the dead" (the benchmark's best theme,
  first-ten precision 1.00) and "a storm at sea batters ships and terrifies
  the crew"; all five chips rated strong on 2026-09-20.

### Search
- Fusion channels no longer treat function words as matching features, and
  their candidate lists are bounded. The lemma, lemma_min1 and exact
  channels ran the matcher with an empty stopword set, so every pair of
  lines or two-line windows sharing "the", "and", "qui" or "sum" became a
  candidate held in memory (5.3 million window pairs for Paradise Lost
  against Hyperion; a web worker at 25.6 GB for 19 minutes on 2026-09-19).
  The curated function-word list now applies in those channels (a user's
  own "-1" in the classic search still means no stoplist at all),
  the matcher keeps only the top candidates by quick IDF (four times the
  channel's cap, the set the old pre-filter kept), and lemma, exact,
  dictionary and rare_word get the 50,000 result cap the other channels
  have (the dictionary channel alone blew a 12 GB cap on Seneca's Letters
  against the Aeneid; rare_word did the same on the whole of Paradise
  Lost). Whole Paradise Lost against Hyperion: 25.6 GB and 19 minutes
  before, 2.8 GB and 1.7 minutes after. Measurement and rationale in
  docs/DECISIONS.md (2026-09-20).

- English line search: the Latin u/v and i/j spelling fold applied to
  every language but Greek, so English queries for any word with a v or a
  j were looked up in Spenser's spelling ("love" as "loue", "voice" as
  "uoice") and returned only Spenser or nothing. The fold now applies to
  Latin only. The results page's "Across the corpus" panel, blank for
  such shared words, works for English again.

### Site
- Changing tabs no longer carries the previous page's query string along,
  so a Theme Search query no longer re-runs itself every time the Theme
  Search tab is reopened. Links opened at a page's own address keep their
  parameters as before.

### Corpus
- The English Bible is displayed as the King James Bible: the files named
  world_english_bible hold the Authorized Version of 1611 (a legacy label;
  the sources registry already credits it correctly). File identifiers
  unchanged; the rename of the files is a later corpus operation.
- Four works whose whole file and book files disagreed (found while
  verifying today's book-by-book Reader rule) are now consistent: Isocrates'
  Letters (parts 2 and 3 had every line tagged with a doubled bracket),
  Hyperides' Speeches (the whole file was missing the "speeches." segment
  its own part files use), Dionysius of Halicarnassus' Antiquitates
  Romanae (one line, 16.1.0, was missing from the part 12-20 file), and the
  Couplet et alii Confucius Sinarum Philosophus (part 1's lines carried a
  shortened "Couplet." tag instead of "Couplet et alii."). Text unchanged
  in every case except Dionysius, where the missing line was inserted. A
  new check script, `scripts/corpus/check_whole_vs_parts.py`, confirms the
  fix and, run against the whole corpus, found 137 works pairing a whole
  file with book files, of which 117 already agree and, beyond this
  batch's four, 20 more disagree pre-existing and out of this batch's
  scope (listed in the PR for a follow-up). The store-side ref rename these four needed
  (`scripts/corpus/apply_whole_vs_parts_refs.py`) is prepared but not yet
  run on production; see docs/DATA_OPERATIONS.md.
- Four files began with a byte-order mark that hid their first line from
  the indexes (Aretaeus, Confucius Sinarum Philosophus part 2, Macrobius'
  fragment, Ovid's Ibis); the mark is removed.

### Reader
- Kline's translation added for Punica 9-17 and the gaps of 1-8,
  non-commercial licence, attribution shown per passage.

## 2026-09-19

### Search
- English function-word list rebuilt from sources (275 words): the Snowball
  stopword list plus the same words in their Early Modern inflections after
  Barber, Early Modern English (1997). Seven content verbs the old list held
  (get, go, know, make, say, see, take) are gone, 27 Snowball function words
  it lacked are in, two duplicates removed. Rule recorded in
  docs/DECISIONS.md: stoplists are function words only; common content
  words are down-weighted, never removed. Help page and docs carry the
  sources; the list itself is visible on the Help page and at /api/stoplists.
- The batch lemma-cache builder's English path lemmatized every word as a
  noun, so past tenses ("stood", "went", "fled", "began") stayed as they
  were in the English caches while the index builder reduced them; in a
  Milton search Milton's own verbs then looked as rare as proper names and
  ranked high. The fast path now applies the main processor's noun-or-verb
  rule. English caches, index and Quotation table rebuilt (DATA_OPERATIONS).
- The quotation channel now carries weight 10 in the Latin and Greek fusion
  profile (it was 0). Measured on 32 prose quotations of Vergil (Gellius,
  Macrobius, Quintilian, Servius): first-ten recall 8 to 19, recall at 100
  14 to 28, for one Lucan pair lost at rank 100 on the poetry benchmarks and
  none in the top ten (evaluation/quotation_weight_test/REPORT.md). English
  keeps 0 until measured.
- The search page falls back to its default text pair whenever the
  remembered selection is not valid for the language; a stale remembered
  pair used to leave the English page with no texts chosen.

### Reader
- Quotation table builder: the "all shared n-grams commonplace" drop is now
  per language (`--drop-all-commonplace auto|on|off`, auto = English only).
  Measured on Latin it removed 1,863 strict pairs and gained none, among them
  genuine short scripture quotations made entirely of common words (John
  10.30 "ego et pater unum sumus" in Hilary); the English function-word junk
  it was written for does not occur in Latin or Greek at that scale.
- Quotation table builder: the commonplace rule is now "drop a pair only when
  every shared n-gram is commonplace-only". The earlier "count commonplace
  n-grams for nothing" removed Hamlet's function-word matches but, rebuilt on
  Latin, also lost 5,445 strict pairs, mostly the Fathers quoting the Vulgate
  in wording made of common words (Augustine, Conf. 7.13 and John 1.3). All
  shared n-grams count again for the totals and the shared count; the pair is
  refused only if none of them carries a content word.
- Quotation table builder: a word also counts as commonplace when it is in
  the language's stoplist (the cross-lingual function-word lists in
  backend/synonym_dict.py, accent-stripped and u/v folded). The data-driven
  threshold alone missed "shall" and "do" on the English corpus, so "what
  shall I do" still linked Hamlet to Bunyan after the previous fix.
- Quotation table builder: two rules tightened after the first English build
  marked Hamlet's "What shall I do?" as strictly quoted by eight Bible verses
  and paired the Faerie Queene's books with each other. An n-gram made only of
  commonplace words now counts toward no rule and no line total (before, the
  commonplace set only guarded the rare single-n-gram rule), and part files of
  one work count as the same work. The English table was taken off production
  until it is rebuilt under these rules; Latin and Greek are rebuilt too.
- Quotation table builder (`scripts/reuse/build_reuse_table.py`): a Greek
  lemma cache whose text_id holds a Greek file name as escaped bytes (eight
  such caches, written under an ASCII locale) crashed the Greek build with
  "surrogates not allowed"; the builder now decodes those ids back to UTF-8
  (the same round trip backend/lemma_cache.py already does) and reports how
  many it repaired.
- The connection gutter's density computation now scores a work's windows
  256 at a time instead of all at once. The old single block cost 2.5 MB per
  window (5 GB for the whole Punica, 11.6 GB for the Vulgate), which is what
  pushed a preview server past its memory caps and what a production worker
  paid on the first open of any large uncached work. Same answer, under
  0.7 GB. Also: the works-route unit test no longer writes the real coverage
  sidecar (it did, through a worktree symlink, on 2026-09-19).
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
- Theme Similarity Map: a "Similarity Map" tab beside Theme Search showing how
  strongly authors, works, centuries or genres connect to one another,
  built from the same passage-index description embeddings Theme Search
  and Similar Passages already use (`backend/connections_map.py`,
  `scripts/build_connections_map.py`). Canvas heatmap, click a cell for
  the work pairs behind it, click a work pair for the strongest passage
  pairs, click a passage pair to open the Reader. Translation pairs (the
  same text in two languages) are flagged two ways -- a curated list
  (`data/translation_pairs.json`, 730 pairs) and a
  heuristic (window-order correlation) -- and hidden by default. New
  routes `/api/passages/map`, `/api/passages/map/cell`,
  `/api/passages/map/pair`, `/api/passages/map/work`, all site-only in
  `backend/blueprints/mcp_manifest.py` (read-only picture of an existing
  signal, not a new tool a connector caller needs). Help page: a
  paragraph under Theme Search.
- Similarity Map details settled with NC on the preview (2026-09-19 to 20):
  authors in chronological order, log colour scale with a "relative to
  size" mode, hover highlights the row and column and boxes both names,
  frozen column headers, drill-down work by work, then book by book, then
  passages, with the browser's Back button unwinding each step; a "Map
  built <date>" footer with a "Refresh map" button instead of any notice
  that the stored map is older than the corpus (the API still reports it
  as `stale` for operators; `?refresh=1` clears the process caches). Help
  page section "The Similarity Map".

### Data operations
- Corpus connections map cache built for the first time
  (`cache/connections_map/<index_fingerprint>.db`, detail in
  docs/DATA_OPERATIONS.md, 2026-09-19).

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
- Planned: `scripts/precompute_passage_density.py` warms the Reader gutter's
  passage-density cache (`cache/passage_density/`) and, with `--lexical`, the
  lexical-density cache (`cache/lexical_density/`) for every work in the
  passage index, so a first Reader open of a large work no longer pays the
  ~100s/1.4 GB the live `/api/passages/density` computation costs on an
  Apache worker. Not yet run against the production index (detail in
  docs/DATA_OPERATIONS.md).
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
