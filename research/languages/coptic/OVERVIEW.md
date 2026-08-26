# Coptic

**Live in production** for lexical, fusion and rare-word search, and present in
the content index via English translations.

## The corpus

**180 texts, 70,842 lines** as reported by `data/inverted_index/cop_index.db`.

An earlier figure of 186 texts and 170,748 lines circulated and is wrong: it
counts seven aggregate files that duplicate their own constituents. The wrong
figure reached the article draft.

Sources: Coptic SCRIPTORIUM (v6.0.0 **and** v6.2.0), plus the Sahidica New
Testament. Sahidic and Bohairic, including a Bohairic Old Testament. 20 Shenoute
works, 34 non-biblical works.

## Licensing, which is not uniform

| Portion | Terms |
|---|---|
| ~97 texts | CC BY-**SA** |
| 4 texts | CC BY-**NC-SA** |
| 28 texts (Sahidica NT) | **academic use only**, (c)2000-2006 J. Warren Wells |

The Sahidica NT is the Hebrews text used throughout the quotation evaluation, so
this is not a footnote. The site notice does carve out Sahidica; the article
draft states no licensing at all.

**Open:** production serves a per-text attribution table with **zero** Coptic
rows. Coptic SCRIPTORIUM is credited site-wide, so nothing is unattributed, but
per-text attribution is missing. The file that has those rows has 760 fewer
entries overall than the committed one, so it cannot simply be committed.

## The quotation channel

Coptic drove the eleventh fusion channel. Biblical prose quotes in **common
vocabulary**, which the IDF rarity penalty suppresses, so runs of three or more
consecutive identical surface tokens are detected separately and scored without
IDF: `run_length / 5`, uncapped.

It is the highest-weighted channel in the `biblical_coptic` profile at 35.052,
with sound 24.277 and semantic 11.216, and the classical-allusion channels
reduced (rare_word 0.55, lemma 0.32). That profile came from a 50-iteration
optimisation on Sahidic Hebrews x Sahidic Psalms.

### It was dead in production for eleven weeks

Found 2026-08-25 while fact-checking the article. Fed a real six-token verbatim
run, production's scorer returned **score 0.0 with empty matched_words**, so the
35.052 weight multiplied nothing.

**Cause:** commit `e99c778`, "Coptic ship (WIP 2/2): shared-file Coptic hunks,
other languages excluded", was assembled by hand from a branch carrying several
languages. It included `matcher.py` and `fusion.py` and **omitted
`backend/scorer.py`**. `_score_quotation_match` had never been in any commit on
`origin/main`. Detection shipped, the profile shipped, the weight shipped, the
scoring did not.

**Why tests missed it:** the tests added in `9d6ef7d` hand fusion a match with
the score already attached. They prove fusion weights a quotation score
correctly, which it always did, and cannot see that no score is ever produced.

### Effect of the fix

Hebrews x Sahidic Psalms, 124 TSK gold pairs, same weights both sides:

| | R@50 | R@100 | R@500 | R@1000 |
|---|---|---|---|---|
| before | 0.040 | 0.040 | 0.056 | 0.065 |
| after | **0.145** | **0.145** | **0.161** | **0.169** |

`tests/test_quotation_scoring.py` goes through the real scorer: four tests,
passing against the fix and failing against the old deployment.

## Coptic in the content index

13,199 windows. **The descriptions were written from the English translations,
not from the Coptic**, because no available model reads Coptic well enough.
Every record carries `derived_from_translation`, the released slice says so in
its licence file, and the Theme Search page says so to readers.

Evidence at one remove, and it should be cited that way. The article draft makes
no content-search claim, which is correct and must stay correct.

## Lexical handling

Real Coptic lemmatisation: a 30,085-entry table plus a sub-word morpheme cache.
A 144-word stoplist. Coptic Wordnet for the dictionary channel. Cross-lingual
search via a Coptic-Greek synonym set (11,641 pairs).

**Known display bug:** Coptic lemmas render mangled in live results, the six
Demotic letters each shifted.

## The article

Draft reviewed 2026-08-25 against the running system. Nine items in
`research/coptic_article/REVISION_INSTRUCTIONS.md` (local, not committed). Most
serious: the evaluated system was not the deployed system (now fixed);
precision-at-ten presented where a reader reads recall; an undisclosed 15-of-29
overlap between benchmark and tuning set; corpus size overstated 2.4x; and two
false claims about third-party work (multilingual-e5 was not trained on Coptic
and derives from XLM-RoBERTa *large*, not base; the TSK "votes" are
OpenBible.info user votes, not commentator judgements).

Reviewed by Krawiec: thirty hand-selected parallels, "nearly all" plausible,
with a caveat about corpus coverage.
