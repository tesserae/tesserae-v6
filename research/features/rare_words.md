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
