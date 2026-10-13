# Superseded scripts

Scripts kept for the record only. Each one has been replaced by a newer script
that writes the same output, and each carries a header naming its replacement.
Do not run them against production data.

| Script here | Replacement | Why |
|---|---|---|
| `build_hebrew_greek_dict.py` | `scripts/build_hebrew_greek_parallel_dict.py` | Both write `backend/synonymy/v6_additions/hebrew_greek.csv`. This one pivots through English glosses; the replacement aligns verses against the Septuagint. |
| `precompute_hebrew_embeddings.py` | `scripts/recompute_hebrew_embeddings.py` | Both write `backend/embeddings/he/*.npy`. This one uses BEREL vectors, which are not in the query encoder's space; the replacement uses the shipped encoder. |
| `extract_bhsa_hebrew.py` | `scripts/corpus/build_hebrew_tables.py` | Writes the Hebrew lemma table and demo texts. The replacement builds consonantal and pointed tables with homographs told apart; `texts/he` now comes from Sefaria. |

The scripts compute the project root three folders up from their own location,
so they still run from here.
