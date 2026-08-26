# Cross-language search

Finds parallels between texts in different languages, where no shared vocabulary
exists to match on.

**Four channels**, not the full eleven: semantic embeddings, dictionary,
phonetic, and the structural signal. Lexical channels cannot apply.

## How

- **Dictionary**: curated synonym sets, notably Greek-Latin, Coptic-Greek
  (11,641 pairs) and Hebrew-Greek.
- **Semantic**: SPhilBERTa cosine similarity across languages.
- **Phonetic**: Greek transliterated into Latin script, then edit distance, so a
  phonetic echo across scripts is detectable (mēnin vs Mene).
  `find_crosslingual_phonetic_matches()` in `backend/matcher.py`. **Used as a
  convergence booster only** — phonetic-only pairs are too noisy to stand alone.

## Recall

40.5%@50 per target line on Knauer's Aeneid-Iliad set (167/412).

## Enabled discoveries

The Hebrew-to-Greek dictionary makes Old-Testament-in-New-Testament reuse
findable, e.g. Habakkuk 2:4 in Galatians 3:11.

## Note

Content search is a different thing and should not be confused with this. Theme
Search crosses languages by comparing English descriptions of what happens, and
finds passages that share a subject without any contact between them. Cross-
language search looks for evidence of textual contact. See
[content_search.md](content_search.md) and
[motif_feature/OPEN_QUESTIONS.md](../motif_feature/OPEN_QUESTIONS.md).
