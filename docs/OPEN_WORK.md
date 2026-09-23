# Open work

What is known to be wrong or unfinished in this project, kept current so it
survives any one machine or any one person's memory. Operational history is
in `DATA_OPERATIONS.md`, decisions that change what the site returns are in
`DECISIONS.md`, and released changes are in `../CHANGELOG.md`. This file is
the forward-looking companion to those three.

Last rewritten 2026-09-21, corpus section revised 2026-09-22.

## Corpus

- **33 Coptic works have no stored passages.** The Latin gap was closed on
  2026-09-22: all 68 Latin book files, and Ennodius' Carmina 2, were given
  their own passages. Coptic is what remains, and nine of the 42 files
  without passages are aggregates whose individual books are indexed
  (`sahidic.bible`, `bohairic.ot` and the like) and want none of their own.
- **60 more files are shorter than four lines**, which is below the window
  geometry's floor, so they cannot be described at all. Catullus 85, 93 and
  94 are among them. Nothing to fix unless the floor changes.
- **The passage index holds 130 works twice**, once as a whole file and
  once as book files, so one passage can appear twice in a result list
  under two names.
- **Two files need re-segmenting.** `salutati.de_laboribus_herculis` has
  one line per chapter, median 1,232 words, which makes any comparison
  against it enormously expensive. `couplet_et_alii.confucius_sinarum_philosophus.part.2`
  has 40 non-blank lines with no reference tag, which the parser drops.
- **Ranking: a third shared word lowers the score** (issue #465). The
  scorer divides by the number of matched words, so the score is a mean
  rather than a sum, against the published 2012 method its own header
  cites. On Aeneid 1 against Lucan 1, the two three-word results score
  0.538 and 0.468 while 25 two-word results tie at the 1.0 ceiling. PR #459
  is held until this is decided, so its tests do not freeze the behaviour.
- **Rarity in English is not meaningful yet.** A word counts as rare at a
  document frequency of 100 or fewer, and the English corpus has 42 works,
  so every shared word qualifies.
- **The English Bible files are named `world_english_bible` but hold the
  King James text.** The display name is corrected; renaming 70 files,
  their index entries and their windows is a separate operation.
- Smaller items: the Libanius declamations are split under a second base
  name rather than `.part.N`; the Greek Anthology needs a better scan for
  books 7, 8 and 14 to 16; the Faral texts have unsplit verse runs; Persian
  and Urdu lack era labels and Coptic lacks per-text attribution.

## Code health

A three-part review in September 2026 read the backend, the front end, and
the scripts and configuration around them. Its verdict was that the project
is not tangled, and that what it has is accumulation damage: a few files
grown too large, and the same small facts written out in several places so
one copy goes stale. These are the items not yet fixed, most valuable
first.

- **`backend/app.py` is documented as an application factory but is one
  long module-level side effect**, with `create_app()` returning the global
  it has already built.
- **The Latin u/v and i/j spelling rule exists three times**, in
  `matcher.py`, `wildcard_search.py` and `distance_filter.py`, and the
  three do not agree, so two search paths can judge the same pair of words
  differently. It needs one shared helper, with recall measured before and
  after.
- **The rule that collapses a multi-part text to its base work is written
  out at least nine times**, including once in raw SQL.
- **The admin blueprint has no tests**, though it includes deleting users
  and resetting passwords. Several core scoring and parsing modules have
  none either.
- **Some functions are far too long**: `line_search` in `app.py` runs to
  638 lines, and five others pass 300.
- **The front end has three god components.** `App.jsx` owns routing, all
  search state and a modal in 1,227 lines. `SearchResults.jsx` is 1,273
  lines with three separate ways of highlighting matched words and two
  charting libraries in one file.
- **`useCorpus.js` has no guard against out-of-order responses**, so
  switching language tabs quickly can leave the picker showing a different
  language's texts than the tab selected.
- **There is no linter**, although a dozen lint-suppression comments
  already sit in the code suppressing warnings that nothing produces.
- **The project's own named regression test is a manual checklist.** The
  "arma virum" search must return Ovid, Quintilian and Seneca; nothing
  automatic checks it. `tests/test_endpoints.py` is excluded from
  continuous integration with no comment saying why.
- **One script recomputes a backend function by hand**:
  `scripts/corpus/add_texts_to_index.py` reimplements the lemma-cache
  filename hash instead of importing it, and the copy is missing a step.
  Two other script pairs write the same output by different methods, with
  the obsolete one unmarked.
- **`scripts/corpus/renumber_paradise_lost.py` writes by default** and its
  flag opts out of writing, the opposite of every other corpus script, and
  it keeps no backup.

## Infrastructure

- **The Reader's gutter is slow the first time a text is opened**, between
  80 seconds and four minutes, because the server compares every passage of
  that work against the whole index. The result is cached and instant
  afterwards. The cache is keyed by a fingerprint of the whole index, by
  design, because adding one text changes the figure for every work, so
  every corpus import invalidates all of it. A batch script precomputes the
  whole corpus offline; it needs group write on two cache directories,
  which is a server-administrator change.
- **After any corpus change**, the word index behind Theme Search
  (`data/passage_index/desc_fts.sqlite`) must be rebuilt in the same
  session. It is staleness-checked against the descriptions file, and a
  stale index silently disables the lexical boost.
- **`index.html` is served with no `Cache-Control`**, and the server's
  single-page fallback returns a page rather than an error for a missing
  bundle, so a stale page can fail silently. Mitigated on every deploy by
  keeping the previous bundles; the real fix needs a virtual-host change.
- **Usage is not logged.** Theme Search, the Reader, Similar Passages and
  the connector have no event record, so there are no real usage numbers.

## How this list is kept

The code-health section comes from a review that can be run again: three
agents read the code from a read-only copy and write one report each. The
review's own instructions and output format are kept with the reports. When
an item here is fixed, it moves to `../CHANGELOG.md` with the release that
fixed it, and anything touching live data gets an entry in
`DATA_OPERATIONS.md` with its backups and checks.
