# Adding a text: the full procedure

A text is not finished until it reaches every store the site reads. The last step
is the coverage check; an import is done when every required column says `ok`.

Run every heavy step through `~/bin/tess-job NAME CAP_GB CMD` (memory caps in
CLAUDE.md). Work on production data only after the pull request that adds the
text has merged. Record the operation in `docs/DATA_OPERATIONS.md` and add a line
to `CHANGELOG.md`.

| Step | Store the site reads | How |
|---|---|---|
| 1. Text file | `texts/<lang>/<author>.<work>[.part.N].tess` | converter for the source (scripts/corpus/*_to_tess.py); validate with `scripts/corpus/validate_tess.py`; licence checked first (data/restricted_texts.json for anything not openly licensed) |
| 2. Lemma cache | `cache/lemmas/<lang>/` | `scripts/batch_lemma_cache.py <lang>` |
| 3. Search index | `data/inverted_index/<lang>_index.db` (whole works) | copy the index, `scripts/corpus/add_texts_to_index.py --db COPY --language <lang> --cache-dir cache/lemmas/<lang> --add FILES`, swap the copy in |
| 4. Rare-phrase table | `cache/bigrams/<lang>_bigrams.json` | `scripts/corpus/rebuild_bigrams.py <lang>` (Greek needs more than 4 GB) |
| 5. Frequency table | `cache/frequencies/<lang>.json` | recomputed by the app on first use; force it with the admin route after a batch |
| 6. Semantic vectors | `backend/embeddings/<lang>/<base>.npy` (+ `.meta.json`), one row per line, whole works and part files | GPU job on BullsAI (encode_fill.py pattern, results via the upload route), part files sliced from the whole work by reference; SPhilBerta for la/grc, MiniLM for en, e5 for fa/ur/ar |
| 7. Passage windows | `data/passage_index/window_texts.db` and `lines` | `scripts/corpus/build_batch_windows.py`; for works with part files the windows belong to the parts |
| 8. Descriptions | `data/passage_index/descriptions.jsonl` | GLM 5.3 Flash on the campus gateway (describe script of the 3 October re-description) |
| 9. Passage vectors | `ids.json` + `embeddings.npy`, in lockstep | e5 over `"query: " + blob_for(desc)` on the GPU; append with backups; rebuild `desc_fts.sqlite` (`scripts/build_desc_fts.py`) |
| 10. Connection map | `cache/connections_map/*.db` | `scripts/build_connections_map.py` (8 GB) |
| 11. Browser metadata | `/api/texts` era, year, type | `backend/author_dates.json`, text-type audit (`scripts/audit_text_types.py`) |
| 12. Genre (Latin) | `data/text_genres.csv` | add the row |
| 13. Credits | `data/text_sources.json` (Sources page) | author, work, e-source and URL, print source, added by |
| 14. Description blurb | `data/text_descriptions.json` | add the entry (About this text) |
| 15. Translation (optional) | `data/translations/<lang>__<work>.json` | public-domain first (licence policy), aligned with a script in scripts/translations/ |
| 16. Reload and check | | touch the wsgi, `scripts/reference_search_check.py`, then the coverage check below |

## The coverage check

    python scripts/corpus/verify_text_coverage.py --root /var/www/tesseraev6_flask -l la author.work

prints one row per file with a column per store and exits non-zero while anything
required is missing. `--all` checks a whole language; `--json FILE` writes the rows.
