# Content search: open questions

Recorded 2026-08-25, after the passage index went live.

## 1. Content as a fusion channel (NC, 2026-08-25) — TO EXPLORE

Right now content similarity is a separate feature: Theme Search, Similar
Passages, the Reader gutter. It also exists as `context_channel`, a bounded
confirmation inside fusion at weight 0.15 with a top-3000 cap.

NC wants this explored further: content as a first-class fusion channel rather
than a confirmation-only signal.

What makes it hard, and worth thinking about before building:

- **Scale mismatch.** Fusion compares LINES. The passage index describes WINDOWS
  of 12 or 30 lines. A content match says "these two passages are about the same
  thing", which is a claim at a different granularity from "these two lines share
  a rare lemma". Giving it a channel weight means deciding what it means for one
  line to inherit its window's content score.
- **It has no rarity.** Every other channel earns its weight partly through IDF:
  a shared hapax is worth more than a shared `et`. Two passages both about a
  storm at sea is a real signal and an extremely common subject. Without an
  equivalent of rarity, a content channel would rank every storm against every
  other storm.
- **The calibration does not transfer.** The context channel measures a baseline
  per text pair precisely because absolute cosine thresholds failed across
  corpora. A fusion weight is a fixed number, so the same problem returns.
- **It changes what a "parallel" claims.** Every current channel is evidence of
  textual contact. Content similarity is not: two poets can describe a storm
  without either having read the other. Promoting it to a full channel changes
  what a high-scoring result asserts, which is a scholarly decision before it is
  an engineering one.

Prior work to read first: `research/studies/2026-08-24_context_channel_calibration/`.

## 2. The name check is any-match, not all-match — REAL, UNQUANTIFIED

Found 2026-08-25 from a case NC spotted on the live site.

Valerius Flaccus, *Argonautica* 1.1-30 is described as "a lyrical invocation to
Apollo for guidance on Aeneas' journey", with participants "Apollo, Cumaean
Sibyl, Aeneas". The passage contains Apollo (`Phoebe, mone`, 1.5) and the Cumaean
prophetess (`Cumaeae ... vatis`, 1.5). It does not contain Aeneas: line 1.9 has
`Phrygios ... Iulos`, and the model reached from Iulus back to Aeneas. The gist
is worse than the participant list, since the invocation asks Apollo for help
singing the voyage of the ARGO, not Aeneas's journey. It has attached Valerius
Flaccus's proem to the wrong epic.

The record is flagged `names_in_text: True`, because the check asks whether ANY
named person appears and Apollo does. So:

**The 0.1% error rate we publish is a floor measured against an any-match rule,
not a ceiling.** It should be described that way anywhere it is quoted.

An attempt to measure the all-match rate on Latin gave 34.2%, but that figure is
contaminated and must not be used: the descriptions are English and the texts
Latin, so `Charlemagne` fails to match `Carolus` and `Louis` fails to match
`Hludowicus`. A defensible number needs name-form normalisation between English
and the source language. That is a real job, not a patch.

## 3. Where things stand as of 2026-08-25

Live: the passage index (603,594 windows), the Reader with its gutter and key,
Similar Passages, Theme Search (page + API + MCP tool), the query encoder as its
own service on port 8090.

Confidence bands refitted to the full index, probe set recorded in
`evaluation/probe_sets/tesserae_2026-08.json`. Six of the absent probes are
near misses at NC's suggestion, and they raised the strong boundary from 1.28 to
1.76.
