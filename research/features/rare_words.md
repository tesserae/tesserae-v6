# Rare words and rare phrases

Fast, high-precision searches for distinctive shared vocabulary between two
texts, outside the fusion formula.

`backend/blueprints/hapax.py`.

| Search | Finds |
|---|---|
| **Rare words** | uncommon single lemmata shared by two texts |
| **Rare phrases / bigrams** | uncommon two-word combinations shared by two texts |

Both are fast and precise, which makes them a good first pass before a full
comparison.

## Important constraint

**Same language only.** Two languages share no vocabulary, so running these
across a pair returns index artefacts, not evidence of absence. Tessa once ran
rare-words between Deuteronomy and the Iliad, got noise back (`*lyrcea`,
`aaaicti`), and concluded from that failure that the corpus held no Hebrew at
all — having just been told it holds 39 Hebrew books. The tool description now
says so explicitly.

## Performance

~15x faster since 2026-08-15: a cached lemma loader plus a precomputed
`lemma_doc_freq` table took document frequency from 34s to 0.02s and live hapax
search from 38-57s to 3.7s. The table is built on both the production and dev
indexes.

## Rarity

Corpus document frequency from the inverted index, with `max(lemma_df,
headword_df)` normalisation via the lemma table so that inflected forms do not
appear artificially rare.

## Passage-sized line-search queries reduce to their rarest words (2026-08-29)

The Reader's Verbal Parallels tab sends a whole selection as one lemma
query. Six Aeneid lines lemmatize to 40 lemmas, whose posting lists union
to 269,850 candidate lines and 97 seconds of search (measured; NC watched
the spinner die). Above a 12-lemma cap, line_search now keeps the query's
rarest lemmas by `lemma_doc_freq` (0.7s, 862 candidates for the same
selection), which is also the Tesserae-shaped question: rare-word
convergence, not two-common-words-in-forty. The response carries
`query_reduced` naming the words; the Reader panel displays them; the Help
page documents it. Queries at or under 12 content lemmas are untouched
(arma virumque: 324, unchanged).

Same investigation, same table: the qere/ketiv rewrite of
build_inverted_index.py had DROPPED the #235 lemma_doc_freq finalize step,
so Hebrew and Coptic indexes had no table and Latin's was stale. The
builder is restored with a history note in its docstring; all five
languages' tables rebuilt on production 2026-08-29.
