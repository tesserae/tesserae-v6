# Tesserae V6 research documentation

One document per subject. Each is a **living record**: everything known about
that capability, feature or language belongs in its document, updated as work
happens, rather than scattered across dated session notes.

Dated files still exist under `studies/`, `sessions/` and `motif_feature/`. They
are the raw material. The documents below are where the standing account lives,
and where to look first.

---

## Capabilities and features

| Subject | Document | State |
|---|---|---|
| Content search (passage index, Theme Search, Similar Passages) | [features/content_search.md](features/content_search.md) | live |
| Tessa, the assistant | [features/assistant_tessa.md](features/assistant_tessa.md) | live |
| The Reader | [features/reader.md](features/reader.md) | live |
| Fusion search (eleven channels) | [features/fusion_search.md](features/fusion_search.md) | live |
| Cross-language search | [features/cross_lingual.md](features/cross_lingual.md) | live |
| Rare words and rare phrases | [features/rare_words.md](features/rare_words.md) | live |
| MCP connector (use your own AI) | [features/mcp_connector.md](features/mcp_connector.md) | live |

## Languages

| Language | Document | State |
|---|---|---|
| Latin | [languages/latin/OVERVIEW.md](languages/latin/OVERVIEW.md) | live, the core corpus |
| Greek | [languages/greek/OVERVIEW.md](languages/greek/OVERVIEW.md) | live |
| Coptic | [languages/coptic/OVERVIEW.md](languages/coptic/OVERVIEW.md) | live |
| Hebrew | [languages/hebrew/OVERVIEW.md](languages/hebrew/OVERVIEW.md) | live |
| English | [languages/english/OVERVIEW.md](languages/english/OVERVIEW.md) | live |
| Persian | [languages/persian/OVERVIEW.md](languages/persian/OVERVIEW.md) | content index only |
| Urdu | [languages/urdu/OVERVIEW.md](languages/urdu/OVERVIEW.md) | content index only |
| Arabic | [languages/arabic/OVERVIEW.md](languages/arabic/OVERVIEW.md) | demo, not a corpus |

## Method and practice

| Subject | Document |
|---|---|
| Evaluation: gold sets, probe sets, what a number means | [evaluation/METHODOLOGY.md](evaluation/METHODOLOGY.md) |
| Deployment, services, and the hazards found the hard way | [infrastructure/DEPLOYMENT.md](infrastructure/DEPLOYMENT.md) |
| The corpus: editions, provenance, licensing | [corpus/TEXTS_AND_LICENSING.md](corpus/TEXTS_AND_LICENSING.md) |
| Description quality: names, phrasing, dates | [features/description_quality.md](features/description_quality.md) |

## Writing

| Subject | Document |
|---|---|
| Coptic article, review and revision instructions | `coptic_article/` (local, not committed) |
| DHQ article | [writing/](writing/) |
| Open questions parked for later | [motif_feature/OPEN_QUESTIONS.md](motif_feature/OPEN_QUESTIONS.md) |

---

## How to use these

**Adding to a subject:** edit its document. Put the finding where someone
looking for that subject will find it, not in a new dated file. If the work also
produced raw output worth keeping, put that under `studies/<date>_<name>/` and
link to it from the subject document.

**When a subject document contradicts a dated note,** the subject document wins;
it is the one being maintained.

**What belongs in a subject document:** what the thing is, how it works, what is
live, the numbers with the date they were measured, what has gone wrong and why,
and what is still open. Failures are worth as much space as successes: most of
what is known about these systems was learned from them.
