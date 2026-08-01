# Coptic Language Support

Code module for Coptic (Sahidic and Bohairic dialects) in Tesserae V6.

## Files

- `processor.py` — text processor: tokenize, normalize, lemmatize. Handles Coptic Unicode (U+2C80–U+2CFF primary, U+03E2–U+03EF legacy), supralinear stroke stripping, and lemma table lookup.
- `stopwords.py` — `COPTIC_STOP_WORDS`. Used by `backend/fusion.py` `_STOPLISTS['cop']` for cross-lingual stoplist filtering and large-pair syntax candidate gating.
- `__init__.py` — registers the language handler.

## Data the Module Depends On

- `data/lemma_tables/coptic_lemmas.json` — surface form → lemma. Currently ~30,085 forms.
- `cache/lemmas/cop/*.json` — pre-computed per-text lemma cache (one JSON per `.tess`).
- `data/inverted_index/syntax_coptic.db` — UD parses (heads, deprels, upos) for the syntax channel. Schema matches `syntax_greek.db` / `syntax_latin.db`.

None of the above are tracked in git (data files); all are regenerable from upstream Coptic Scriptorium.

## Conversion Scripts

- `scripts/convert_coptic_scriptorium.py` — base CoNLL-U → .tess + lemma cache.
- `scripts/convert_coptic_scriptorium_full.py` — discovery + dispatch wrapper for upstream corpora (NT-split, OT-split, chapter, flat).
- `scripts/tt_to_conllu.py` — Coptic Scriptorium TT XML → CoNLL-U. Used **only** for the Sahidic NT, where upstream CoNLL-U files are 2-byte stubs (only Mark and 1 Cor are real). The TT files are the canonical source for that corpus.
- `scripts/build_coptic_syntax_db.py` — CoNLL-U → `syntax_coptic.db`. Coptic ships with pre-annotated UD parses, so no parser is run.

## Full History and Phase Notes

See [research/languages/coptic/implementation_report.md](../../research/languages/coptic/implementation_report.md) for:
- Phase 1 (2026-04-15): initial 23-text demo corpus, cross-lingual Coptic-Greek dictionary, channels.
- Phase 2 (2026-05-01): full Sahidic NT (TT-conversion workaround), Bohairic NT and OT, syntax channel.
- Refresh procedure when Coptic Scriptorium ships an update.
- Comparison with TRACER (Miyagawa 2022).

See also [research/languages/coptic/support_plan.md](../../research/languages/coptic/support_plan.md) for the original Phase 1 plan.

## Source Attribution

V6's Coptic module builds on the work of several external projects. All are credited here per their licenses and our practice of crediting upstream data and tool work.

### Texts and morphological annotations

- **Coptic Scriptorium** (https://copticscriptorium.org/) provides every Coptic text and CoNLL-U annotation in the corpus. CC-BY 4.0 / CC-BY-SA 4.0. Foundational reference: Caroline T. Schroeder and Amir Zeldes, *Raiders of the Lost Corpus* (*Digital Humanities Quarterly* 10.2, 2016).
- **Sahidica New Testament** (J. Warren Wells, 2000–2006) is incorporated under the Sahidica academic-use license, distributed through Coptic Scriptorium.

### Cross-lingual Coptic-Greek dictionary (`coptic_greek.csv`)

- **DDGLC — Database and Dictionary of Greek Loanwords in Coptic** (Freie Universität Berlin). CC-BY-SA 4.0. Provides the bulk of attested Coptic→Greek lexical correspondences.
- **BBAW Lexicon of Coptic Egyptian** (Berlin-Brandenburgische Akademie der Wissenschaften). CC-BY-SA 4.0.
- **Coptic Dictionary Online (CDO)** (Feder, Kupreyev, Manning, Schroeder, Zeldes 2018). CC-BY 4.0. Provides additional dictionary headwords with English glosses.

### Coptic-internal synonymy dictionary (`coptic_coptic_wordnet.csv`)

- **Coptic Wordnet** (Slaughter, Morgado da Costa, Miyagawa, Büchler, Zeldes, Lundhaug, Behlmer 2019, *The Making of Coptic Wordnet*, Global WordNet Conference 2019). CC-BY 4.0. Distributed at https://github.com/coptic-wordnet/data. V6 uses the synonymy layer (synsets, filtered to ≤30 lemmas per synset to suppress broad-concept noise) and excludes hypernymy and co-hyponymy. Integrated into V6's dictionary channel for same-language Coptic-Coptic detection (2026-05-14).

### Comparison and benchmarking literature

- **Miyagawa, So et al. (2025), "Automatic Detection of Coptic Text Reuse: Applying Coptic Wordnet to Intertextuality Studies in Selected Coptic Monastic Writings."** The 2025 paper that prompted V6's CWN integration. Their work establishes the case for semantic-aware Coptic text-reuse detection; V6's multi-channel fusion architecture provides ranked output where their TRACER+CWN approach provides an unranked candidate list. Comparative analysis: `research/languages/coptic/2026-05-14_miyagawa_comparison_results.md`.
- **Miyagawa, So (2022), *Shenoute, Besa and the Bible: Digital Text Reuse Analysis of Selected Monastic Writings from Egypt*** (SUB Göttingen). The dissertation that introduced TRACER-based Coptic text-reuse work to the field.
- **Treasury of Scripture Knowledge** (R. A. Torrey, 1880; public domain). Distributed via OpenBible.info as a CSV under CC-BY 4.0. Used as the gold set for the same-language Coptic NT → Coptic Psalms recall evaluation in `evaluation/coptic_recall/`. The Hebrew → LXX psalm-numbering conversion is applied to map TSK's references to the Sahidic Septuagint numbering.
