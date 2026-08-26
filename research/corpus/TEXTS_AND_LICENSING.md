# The corpus: texts, provenance, licensing

What is in Tesserae, where it came from, and what governs its reuse.

## Scale

~2,100 works across Latin, Greek, English, Coptic and Hebrew for search, plus
Persian, Urdu and a small Arabic demo in the content index only.

Per-language detail lives in `languages/<lang>/OVERVIEW.md`.

## Provenance

| Source | Covers | Terms |
|---|---|---|
| Perseus Digital Library | much Latin and Greek | texts public domain; **TEI markup CC BY-SA 4.0** |
| First1KGreek | Septuagint and more Greek | open |
| SBLGNT | Greek New Testament | SBLGNT End User Licence, by permission |
| Coptic SCRIPTORIUM | Coptic, v6.0.0 and v6.2.0 | mixed, see below |
| Sahidica NT | 28 Coptic texts | **academic use only**, (c)2000-2006 J. Warren Wells |
| Sefaria / MAM | Hebrew Bible (Aleppo Codex) | CC BY-SA |
| ETCBC / BHSA | Hebrew morphology | **CC BY-NC 4.0** |
| Ganjoor | Persian poetry | freely available |
| Rekhta | Urdu digitisation | credit as digitisation source |

**Licensing is not uniform inside a language.** The Coptic corpus is roughly 97
ShareAlike texts, 4 NonCommercial-ShareAlike, and 28 academic-use-only. Assuming
one licence per language is how a wrong notice gets published.

## Why the released index is split per language

`scripts/build_passage_index_release.py` emits one slice per language, each with
its own `LICENCE.txt` and `MANIFEST.json`.

A single bundle would force BHSA's non-commercial term onto the **98.6%** of the
index that does not carry it. Split, a commercial user can take Latin, Greek and
English and have a working system; under one NC bundle they could take nothing.
The cost is a few extra clicks, and reassembly is concatenation with
`scripts/merge_index.py`, which checks its own invariants.

Arabic is deliberately withheld: 32 windows from a six-text demo is not a
language slice, and labelling it one invites exactly the misreading the word
"demo" is meant to prevent.

## Attribution on the site

Site-wide credits name every source. **Per-text attribution is served from
`backend/text_sources.json`, and production currently has zero Coptic rows in
it.** Nothing is unattributed, since Coptic SCRIPTORIUM is credited site-wide,
but per-text credit is missing. The file that carries those rows has 760 fewer
entries overall than the committed one, so it is a different file rather than a
newer one and cannot simply be committed. Open.

## Derived data

A description is a derivative of the text it describes, so the source licence
follows it into the passage index. This is why the released slices carry the
source terms rather than the terms of the model that generated them (Qwen2.5,
Apache-2.0).

## Expansion

Planning: `plans/CORPUS_EXPANSION_2026-08.md`, and
`plans/STAGE1A_MEDIEVAL_LATIN_EDITIONS.md` for the medieval Latin editions.

Adding texts to the content index: `motif_feature/ADDING_TEXTS_TO_THE_CONTENT_INDEX.md`.
The existing index is not recomputed; new texts are windowed, described on a GPU,
embedded and merged.

## Identifiers

Not started: linking texts to Perseus Catalog IDs and CTS/DTS URNs, plus CPL
numbers, for identity and locus standardisation. NC's idea, 2026-08-16.
