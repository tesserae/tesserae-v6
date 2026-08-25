# Fusion search

The core capability: compare two texts and rank the parallels between them, by
running many independent detection methods and combining what they find.

**Eleven channels**, not ten. Documentation said ten in seven places until
2026-08-25; the eleventh, `quotation`, was added for Coptic and never written up.

| Channel | Detects |
|---|---|
| `lemma` | 2+ shared dictionary forms |
| `lemma_min1` | a single shared lemma (high recall, noisy, catch-all) |
| `exact` | 2+ identical surface tokens |
| `sound` | character-trigram similarity |
| `edit_distance` | Levenshtein fuzzy matching |
| `semantic` | SPhilBERTa cosine similarity |
| `dictionary` | synonym pairs from the V3 synonymy sets |
| `syntax` | dependency pattern match at shared lemma positions |
| `syntax_structural` | identical dependency head pattern, no shared lemmas |
| `rare_word` | shared low-frequency lemmata |
| `quotation` | runs of 3+ consecutive identical surface tokens |

Weight profiles select per corpus type: `latin_epic` (the historical default),
`english`, `biblical_coptic`, `biblical_coptic_thematic`. `quotation` carries
weight **0.0** by default and 35.052 under `biblical_coptic`, because verbatim
quotation in common vocabulary is a biblical-prose phenomenon that the rarity
penalty otherwise suppresses.

## Scoring

Three-layer rarity, using geometric-mean corpus IDF over 1,429 Latin texts: a
squared base multiplier, min-word-IDF-weighted convergence, and a
convergence-scaled rarity boost. Function words come from a curated stoplist
(66 Latin, 88 Greek, 60 English) rather than an IDF threshold, which gives
precise identification and let the min-IDF gate be removed entirely.

Three penalty tiers: single-word matches, all-function-word matches, and mixed
function+content matches. Convergence is zeroed for all three.

Details and history: `scoring_history.md`, `scoring_crosslingual_reference.md`.

## Recall

92.6% across five Latin benchmarks (798/862). Lucan-Vergil 90.1%,
Achilleid-Thebaid 96.2%. Greek 78.5%@200 on Hunter's Apollonius-Homer.
Cross-lingual 40.5%@50 per target line on Knauer.

**The Latin figure is 92.6%**, range 89-96 across benchmarks. A quoted "91 to 94
percent" matches no record.

## The quotation channel outage

Dead in production for eleven weeks; see
[languages/coptic/OVERVIEW.md](../languages/coptic/OVERVIEW.md). Restoring it
more than tripled Coptic recall. The lesson is in
[evaluation/METHODOLOGY.md](../evaluation/METHODOLOGY.md).

## Open

- Content similarity as a channel: see
  [motif_feature/OPEN_QUESTIONS.md](../motif_feature/OPEN_QUESTIONS.md).
- The context channel exists as a bounded confirmation (weight 0.15, top-3000
  cap) and measures its own baseline per text pair, which is why it survived
  corpus growth that broke the Theme Search bands.
