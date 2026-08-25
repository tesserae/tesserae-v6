# Latin

**Live, and the core corpus.** ~1,826 works, 1,429 texts used for corpus IDF.

- All eleven fusion channels available. Every text lemmatised and indexed.
- Recall 92.6% across five benchmarks (798/862), range 89-96.
- 208,931 passage windows in the content index.
- Lemmatisation: UD treebank lookup (`data/lemma_tables/latin_lemmas.json`,
  111,738 mappings) with CLTK backoff, trailing sense digits stripped, optional
  LatinPipe syntax DB override at index-build time.

**Known issues**
- Exact search does not fold u/v or i/j, so `arma uirum` (7 hits) and
  `arma virum` (21 hits) return different sets and neither returns both. Fix
  exists on `fix/greek-exact-search`, not merged.
- Prefix assimilation splits some lemmas.
- See `features/fusion_search.md` for scoring, `evaluation/METHODOLOGY.md` for
  what the recall figures mean.
