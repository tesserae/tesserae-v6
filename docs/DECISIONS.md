# Decisions

Method and scoring decisions that change what the site returns, with the
measurement behind each and where to find the data. One entry per decision,
newest first. Working notes and evaluation folders are kept outside this
repository; this file is the record a later reader can find. Operational
history (index builds, cache rebuilds, corpus changes) is in
`DATA_OPERATIONS.md`; per-release changes are in `../CHANGELOG.md`.

## 2026-09-22 A parallel's score is no longer capped at 1.0

**Question.** `backend/scorer.py` ended with `min(score, 1.0)`, so every
result that computed above 1.0 was flattened to exactly 1.0 and results the
scoring had already separated became indistinguishable.

**Measurement.** Lucan book 1 against all twelve books of the Aeneid, lemma
search, `min_matches=2`, run against production. 1,923 results, 47 of them
among the 213 commentator-attested parallels in
`evaluation/benchmarks/lucan_vergil_lexical_benchmark.json`.

| | |
|---|---|
| Results at the ceiling | 317 of 1,923 (16%) |
| Attested parallels inside that block | 20 of 47 |
| Block size within one search | 19 to 35 results, arbitrary order |

Letting the scores through ranks 5 of those 20 first in their block and 13
in the top half. Counting ties at their average rank, attested parallels in
the top ten of a search rise from 5 to 13, and the mean rank of an attested
parallel improves from 54.7 to 52.6.

**Choice.** The ceiling is off by default, in one place
(`backend/score_bounds.py`), read by the scorer, the feature extractor and
the cache key. A caller may still pass `unbounded_scoring: False`.

**Scope.** Smaller than it sounds. `backend/fusion.py` already set
`unbounded_scoring: True` on every channel, and the interface defaults to
fusion, so the search most people run was never capped and already returns
scores up to about 1.43. Only a single-channel search was affected, which is
what a reader gets after changing the match type away from fusion. The
ceiling was an inconsistency between two code paths rather than a decision
anyone made.

**Consequence.** Results cached before this change were scored under the
ceiling. They are keyed on the setting, so they are not found again rather
than served.

**Also corrected.** The scorer's header claimed that more matching words
raise the score. The divisor carries the match count, so they do not. It now
describes the code and points at issue #465 for whether the code is right.

NC, on the measurement above.

## 2026-09-22 "Rare" is a share of the corpus, not a fixed number of works

**Question.** The rare-vocabulary channel admitted a word as rare when it
appeared in 100 works or fewer, a work being a text with its parts
collapsed. The number was the same for every language.

**Measurement.** Work counts from each language's own index, 2026-09-22.

| language | works | old cut-off | as a share | new cut-off |
|---|---|---|---|---|
| Latin | 744 | 100 | 13% | 89 |
| Greek | 853 | 100 | 12% | 102 |
| Coptic | 180 | 25 | 14% | 22 |
| English | 42 | 100 | 238% | 5 |
| Hebrew | 39 | 100 | 256% | 5 |

100 was chosen against Latin. In English it admitted everything: the
commonest English word appears in all 42 English works, so no word could
fail the test and the channel stopped discriminating. `backend/fusion.py`
already carried the consequence in a comment: 431,000 window matches for
*Paradise Lost* Book 1 against *Hyperion* and 12 GB of memory, which is why
the channel was capped in September. The cap treated the symptom.

**Choice.** 12% of the works in that language's corpus
(`hapax.RARE_WORD_SHARE`), at least 2, falling back to 100 when the corpus
size cannot be read. One share reproduces all three cut-offs that had been
set by hand, including Coptic's 25, which existed because sub-word
tokenisation inflates its document counts. That is what makes it the rule
underneath them rather than a fourth special case. A caller may still pass
`rare_word_max_occurrences` to override it for a single search.

**Not affected.** The sliding scale that scores every result, which is a
continuous inverse document frequency with no cut-off anywhere. The gate
belongs to one channel. The two also count different things: the scale
counts how many times a word occurs, the gate counts in how many works it
appears. Both are now described in `HOW_TESSERAE_SEARCHES.md` under "How
rarity is measured".

**Open, noticed while checking this.** `frequency_source` decides what the
sliding scale counts against. The main search sends `corpus`; the default in
the scoring code is `texts`, meaning only the two texts being compared.
Anything calling the scorer without the setting therefore judges rarity
locally rather than against the corpus. Not investigated yet.

NC, on the measurement above ("We can proceed with your fix making it a
percentage for rare word").

## 2026-09-20 Translations: public domain first, then open non-commercial with attribution (Silius books 9 to 17)

**Decision (NC: "If it's legal and appropriate, we should use Kline").**
The Reader's aligned translations come, in this order of preference, from
(1) public-domain texts, (2) translations whose author grants free
non-commercial reproduction, storage, transmission and display, credited
by name on the Reader and in the sources registry, and never included in
the site's own CC-licensed data releases. Silius Italicus, Punica books
9 to 17, is the first case of (2): A. S. Kline's translation
(poetryintranslation.com), whose licence note permits exactly those uses
for non-commercial purposes and asks for attribution. Books 1 to 8 keep
J. D. Duff's Loeb translation (1927, public domain); Duff's second volume
(1934) enters the US public domain on 2030-01-01 and can replace Kline
then if the site prefers a uniform translator.

**Why.** The site is a free scholarly service with no commercial use, so
Kline's terms fit. The alternatives were measured first. Thomas Ross's
1661 verse translation, the only complete public-domain English Punica,
exists as a CC0 EEBO-TCP transcription (A60230: 19,149 verse lines, about
400 small illegible gaps) and could be aligned by book and by proper
names, but it is a 17th-century paraphrase without line numbers, which a
reader of the Latin cannot follow line for line. Kline's section headings
("Book IX:1-38") carry exact Latin line ranges, so his units align to the
Latin at section level with no guessing.

**Rules that follow.**
- Each aligned translation records its source per unit (`unit_sources`)
  so a work with two translators credits the right one on every passage.
- The data releases under Downloads exclude non-PD translations; the
  Reader displays them with the translator's name and a link to the
  source page.
- A future public-domain replacement (Duff vol. II in 2030) is a swap of
  the same units, recorded in `DATA_OPERATIONS.md`.

## 2026-09-20 Theme Search: the reader re-scores all 300 composed rows

**Decision (NC: "Give the reader all 300 composed rows").** The page is
composed as about 100 works with three windows each, in order of each
work's best score with languages interleaved; the reader then re-scores
rows and the page shows the first 25. It used to re-score the first 100
rows. It now re-scores the whole composed list (READER_HEADS = 100 works,
DEFAULT_K = 300 rows; THEME_READER_K still overrides).

**Why.** With the lexical boost in place, measured on the real code path
over the 16-query benchmark: first-ten precision 0.444 at 300 rows against
0.453 at 100 (neutral within noise for sixteen queries; 0.350 against
0.375 on the four held-out topoi). What changes is reach: a work whose
rows sit past the first hundred can now be lifted by the reader. The
Odyssey's recognitions on "a wife or child recognizes someone long thought
dead or lost" sat at rows 146 to 148 of the composed list, unseen; with
all rows re-scored the Odyssey lands at row 15 of the page. Cost: about
9 s a query against 4 s (the reader service accepts up to 400 passages).

## 2026-09-20 Theme Search: a lexical channel over the descriptions, adopted

**Decision (NC: "adopt the light boost in production").** Theme Search
scores each passage window by the cosine between the query's embedding and
the window's description embedding, plus LEXICAL_BETA (0.02) times a BM25
word-match score over the description text (gist, themes, action steps,
participants, setting), normalised to [0, 1] over the top 3,000 word
matches and zero elsewhere. The confidence band is still computed from the
embedding alone. The composition (one window per work, languages
interleaved, three windows per work) and the reader over the first hundred
rows are unchanged.

**Why.** Four tests on 2026-09-20 with the calibrated Opus judge on the
16-query benchmark (harnesses in evaluation/theme_benchmark/composition_test/,
private):

| change | all 16 | 12 development | 4 held out |
|---|---|---|---|
| shipped page | 0.434 | 0.471 | 0.325 |
| reader over a deeper per-work pool | 0.419 | 0.425 | 0.400 |
| work score by mass of close windows | 0.391 | 0.425 | 0.287 |
| mass relative to work size (blend) | 0.434 | 0.462 | 0.350 |
| lexical channel, rank fusion (harness) | 0.475 | 0.483 | 0.450 |
| lexical channel, light boost (harness) | 0.506 | 0.533 | 0.425 |
| **light boost on the real code path (adopted)** | **0.453** | **0.479** | **0.375** |
| the same with the reader over all 300 composed rows | 0.444 | 0.475 | 0.350 |

**A correction found while re-measuring.** The first four rows come from
an offline harness whose page composition lacked the site's collapse of
overlapping windows, so a passage indexed twice (whole-file and book-file
copies, 130 works) could occupy two of the ten slots and be counted twice.
The real code path collapses them, and its figures are the honest ones:
a gain of 0.019 over the sixteen queries and 0.050 on the four held-out
topoi, positive on both, smaller than the harness suggested. The earlier
negative results (deeper pool, mass, density) were measured with the same
inflation and would only look worse without it.

The case that started it: "a wife or child recognizes someone long
thought dead or lost" returned no Odyssey, although the index describes
Odyssey 23.199 as "a woman recognizes Odysseus through a unique sign". The
encoder ranks the Odyssey 63rd by work for that wording; with the boost it
is 50th on the real path, and its rows sit at 146 to 148 of the 300
composed rows, past the 100 the reader re-scores. With the reader over all
300 rows the Odyssey lands at row 15 of the page. Whether to deepen the
reader (about 9 s a query instead of 4 s; precision neutral) is a separate
decision. Judgements: 236 new Opus verdicts across the tests (about 380k
input tokens).

**Operations.** `scripts/build_desc_fts.py` writes
`data/passage_index/desc_fts.sqlite` (about three minutes) and must be run
after every change to descriptions.jsonl; the app compares the index's
description count with the passage index's and refuses a stale one.

## 2026-09-20 Fusion channels: function words are not matching features, and candidate lists are bounded

**Problem.** One fusion search of Paradise Lost (10,565 lines) against
Hyperion held a web worker at 25.6 GB for over 19 minutes on 2026-09-19,
and the quotation-weight sweep was killed twice at the window stage on
whole-file prose sources. Cause, found 2026-09-20: the lemma, lemma_min1
and exact channels ran the matcher with `stoplist_size: -1`, which meant an
EMPTY stopword set, so "the", "and", "his", "with" (English) and "qui",
"sum", "hic", "non" (Latin) were matching features. Every pair of two-line
windows sharing one of them became a candidate held in memory, and the
list grew with source units times target units. The `lemma` and `exact`
channels also had no result cap, so every candidate was scored in full.

Candidate pairs at the window stage, counted from the lemma caches
(`count_pairs.py`, session scripts 2026-09-20):

| pair | one shared word, as it was | one shared word, function words excluded | two shared words, as it was | two, excluded |
|---|---|---|---|---|
| Paradise Lost x Hyperion | 5,287,486 | 330,358 | 1,380,119 | 7,186 |
| Aeneid x Lucan 1 | 1,142,943 | 584,430 | 115,664 | 28,236 |
| Aeneid x Achilleid | 1,763,321 | 823,283 | 156,892 | 32,655 |
| Aeneid x Metamorphoses | 22,308,739 | 9,145,844 | 2,535,778 | 393,788 |
| Iliad x Odyssey | 61,407,496 | 24,240,161 | 11,133,128 | 1,908,090 |

**Decision (five changes, one PR).**
1. The three channels pass `exclude_function_words` with their
   `stoplist_size: -1`, so the language's curated function-word list
   applies in the matcher, as it already did for Coptic. A user's own -1 in
   the classic search keeps its documented meaning (no stoplist at all). Common content words stay matchable and are
   down-weighted by rarity in scoring (the 2026-09-19 rule, now true of the
   channels as well as the scoring layer).
2. The matcher keeps a bounded candidate list (`candidate_cap`, four times
   the channel's result cap) ranked by the same quick IDF score the channel
   runner's pre-filter used, so memory is proportional to the cap, not to
   the text sizes. The kept set is the one the pre-filter kept.
3. `lemma` and `exact` get the 50,000 result cap every other channel has.
   On the two poetry benchmark pairs it does not bind (28k to 33k two-word
   window pairs); it binds on prose sources against the Aeneid (a 287-line
   Quintilian book produced 783,588 uncapped window results) and on very
   long pairs such as Aeneid x Metamorphoses (394k), where the pairs
   dropped are the lowest by quick IDF beyond the top 200,000.
4. The `dictionary` channel is bounded the same way (cap 50,000,
   candidates 200,000). With `include_lemma_matches` it re-finds every
   pair sharing two content lemmas plus the synonym pairs and had no cap:
   up to 360,126 window results per prose source against the Aeneid, and
   the first after-fix benchmark run was killed at its 12 GB cap in this
   channel's window step for Seneca's Letters, after the lemma channels
   had passed the same step in under a minute at 3 GB.

5. The `rare_word` channel is bounded the same way (cap 50,000). It had no
   cap, and in English "rare" means df <= 100 of only 42 works, so every
   shared lemma counts as rare there: Paradise Lost Book 1 against Hyperion
   produced 431,131 window matches, and the whole poem was killed at a
   12 GB cap in this channel after the other four were bounded. The English
   rarity threshold itself (100 works out of 42) is a separate decision for
   NC.

**Not a fusion defect.** salutati.de_laboribus_herculis.tess has 97 units
of median 1,232 words (one .tess line per chapter), so every channel
works on chapter-sized units and the pair against the Aeneid runs for
hours. That is a text-segmentation defect of the file; it is skipped in
the measurement and listed as a corpus follow-up.

**Measurement (2026-09-20, `evaluation/fusion_memory_test/`).** The
quotation-weight harness run twice at the production weight on identical
texts and caches, once with the code at main ("before") and once with this
branch ("after"): 32 verbatim prose quotations of Vergil in Gellius,
Macrobius, Quintilian and Servius; the Lucan 1 and Achilleid benchmarks
against the Aeneid; Odyssey 6 against Argonautica 3.

| gold set | pairs | before: found in top 10 / 50 / 100 | after: 10 / 50 / 100 | channel seconds before -> after |
|---|---|---|---|---|
| prose quotations of Vergil | 32 | 19 / 26 / 28 | 17 / 26 / 28 | 3,260 -> 2,300 |
| Lucan 1 + Achilleid against the Aeneid | 266 | 6 / 14 / 20 | 6 / 14 / 20 | 240 -> 205 |
| Odyssey 6 against Argonautica 3 | 16 | 1 / 1 / 1 | 1 / 2 / 2 | 40 -> 33 |

Peak memory of the whole run: 11.3 GB before, 4.7 GB after (the before
run sat just under its 12 GB cap on the benchmark pairs alone). Poetry
recall is identical pair for pair. In the prose set two quotations moved
from the top ten to the top fifty (Macrobius 4 against the Eclogues,
Servius against the Eclogues), Macrobius 5 against the Aeneid lost one at
50 and one at 100, Macrobius 3 gained one at 50 and Macrobius 6 one at
100; the whole-list counts at 50 and 100 are unchanged. Six more gold
quotations, in Seneca's Letters and De beneficiis as whole files, could
not be run before (the window step blew a 12 GB cap) and now score 4 of 6
in the top ten and 6 of 6 in the top fifty, the Letters against the
Aeneid in 20 minutes at a 4.4 GB peak. English (production's texts and caches, no gold set, the pair that held
a web worker at 25.6 GB for 19 minutes on 2026-09-19):

| pair | before: channel seconds, process peak | after: seconds, peak |
|---|---|---|
| Paradise Lost Book 1 (798 lines) x Hyperion (885) | 126.5 s, 4.38 GB | 33.5 s, 2.19 GB |
| whole Paradise Lost (10,565 lines) x Hyperion | killed at 12 GB before the fix (25.6 GB observed in production) | 102.5 s, 2.83 GB |

Channel counts for Book 1: lemma line pairs 13,101 before (function words)
against 54 after; rare_word window matches 431,131 against 50,000. The
whole poem's top ten after the fix leads with "intestine broil" (Paradise
Lost 2.1001, Hyperion 2.192).

**Why a few prose ranks moved (traced on Macrobius 4 against the
Eclogues with full fused lists).** The gold quotations' own scores are
identical before and after. What changed is competitors: fifteen pairs in
the top 200 rose (1.20 to 1.43, 0.68 to 1.16), all of them adjacent-line
window matches of genuine Vergil quotations. The scoring layer has a
"mixed" penalty: when any matched word is a function word, the pair is
scored like a single-word match with its convergence bonus removed, even
if it shares two or more content words as well. Now that function words
are never among the matched words of the lemma, exact and dictionary
channels, that penalty stops firing for such pairs, and multi-content-word
matches that also shared "et", "qui" or "non" score as content-only
matches. That is the scorer's own stated intent ("function words add zero
allusion signal") applied consistently. It moves genuine quotation
neighbours up beside the gold lines, so per-pair gold ranks slip a few
places among tied pairs, while whole-list recall at 50 and 100 is
unchanged and poetry recall is unchanged pair for pair.

**Deferred for NC.** A request-size guard in `/api/search` (refuse or
queue pairs whose estimated candidate count is too large, with a plain
message) and a memory cap on the web workers (root). Both are visible
behaviour changes.

## 2026-09-20 Theme Search: sample searches are measured winners; a deeper per-work re-ranking pool was tested and not adopted

**Sample searches (PR #419).** The five suggestions on the Theme Search page
for the Latin, Greek and English site are queries that rated "strong" on
production on 2026-09-20 and whose first works are the expected ones: a
guest welcomed with food, wine and a bath; a mother lamenting her dead son;
a warrior arming piece by piece; funeral games (the theme the 16-query
benchmark scores best, first-ten precision 1.00); a storm at sea. The
former chip "a wife or child recognizes someone long thought dead or lost"
rated moderate and did not return the Odyssey's recognitions.

**Why the Odyssey misses that query.** The passage index describes the
scenes accurately (23.199 "a woman recognizes Odysseus through a unique
sign", 19.466 "recognized by his nurse", 16.181 "reveals his identity to
Telemachus"), but the description encoder ranks the Odyssey 63rd among
works for that wording across all languages (25th within Greek), and the
head of the page is one window per work chosen by cosine. Theme Search has
no word-matching bonus: the score is the cosine between the query's
embedding and each description's embedding. The distilled cross-encoder
that reorders the top hundred then places the Odyssey's cosine-best window
(23.232, the reunion and the delayed dawn) low. Wordings that name the
scene's own features find it at once ("a man is recognized by an old scar":
Odyssey at ranks 2, 4 and 5).

**Deeper per-work pool for the re-ranker: tested, not adopted.** On the 16
benchmark queries, judged with the calibrated Opus judge (80 new pairs):
shipped page 0.434 first-ten precision; reader sees all 300 composed rows
0.447; 40 works with 8 windows each 0.419; the same grouped by work 0.388.
Within noise or worse, and none reaches a work the encoder ranks 63rd.
Harness: evaluation/theme_benchmark/composition_test/run_deep_per_work.py.
Ideas still open: a work-level score that pools a work's several close
windows instead of taking its single best, and a lexical channel over the
descriptions fused with the cosine ranking.

## 2026-09-19 Standing rule: stoplists are function words only

**Decision (Neil Coffee).** A stoplist holds function words (articles,
pronouns, prepositions, conjunctions, auxiliaries, particles) and nothing
else. A common content word such as "summer", "day", "old" or "began" is
down-weighted by its corpus frequency in scoring, never removed from
matching or from the shared-word count. Applies to every language and to
every place a stoplist is used: the search channels, the fusion scoring
layer's function-word penalty, and the Quotation table builder's
commonplace test.

**Consequence found the same day.** The curated English list in
`backend/matcher.py` (`DEFAULT_ENGLISH_STOP_WORDS_LIST`, 202 entries)
mixes function words with common verbs ("know", "take", "make", "go",
"see", "come", "think", "look", "want", "give", "use", "find", "tell",
"ask", "work", "seem", "feel", "try", "leave", "call"). The fusion scoring
layer penalizes those as function words. Adopted (NC, 2026-09-19 23:58, "Go ahead with that stop list"). The list, 275 words (220 plain words plus 50 Snowball contractions and five apostrophe forms, since the tokenizer keeps contractions whole), is the Snowball English
stopword list (Porter's Snowball project, `snowball.tartarus.org/algorithms/
english/stop.txt`, 174 entries, 124 once contractions are set aside), a
published function-word list widely reused (NLTK, Lucene, R), PLUS the
early modern inflections of the same function words that the current list
already carries (thou, thee, thy, thine, ye; art, wast, wert; hath, hast,
hadst; doth, dost, didst; shalt, wilt, canst, mayst, mightst, shouldst,
wouldst, couldst; 'tis, 'twas, 'twere, 'twill, 'twould; ere, oft, unto,
whilst, hither, thither, whence, thence, wherefore, whereon, wherein,
whereof, hereby, herein, therein, thereof; nay, yea, prithee, forsooth,
verily, methinks, lo, behold, alas, ah, oh, o), which follow the pronoun
and auxiliary paradigms of Early Modern English as set out in Charles
Barber, Early Modern English (Edinburgh, 1997) and the Cambridge History of
the English Language, vol. III. Net change against the current 202-word
list: add the 27 Snowball words it lacks (above, again, against, below,
between, cannot, did, does, doing, down, during, further, herself, himself,
itself, myself, off, once, only, ought, ourselves, over, themselves,
through, under, yourself, yourselves); remove the 7 content verbs (get, go,
know, make, say, see, take). No published list combines both parts; the
Voyant/Taporware list, the only common one with early modern forms, has
571 entries including content words (make, take, see, find, thing) and only
three archaic forms (thou, thee, thy). The Latin (102) and Greek (167)
lists to be audited by the same rule.

## 2026-09-19 Quotation channel weight 10 for Latin and Greek (PR #411)

**Decision.** `CHANNEL_WEIGHTS['quotation']` goes from 0 to 10, so the
Latin and Greek fusion profile (`latin_epic`) scores runs of three or more
identical words. The English profile pins it at 0 until measured. Approved
by Neil Coffee on 2026-09-19.

**Measurement.** A gold set of 42 verbatim prose quotations of Vergil was
built from the corpus's own texts (Gellius, Macrobius, Quintilian, Seneca,
Servius, Salutati; six or more identical words), and the fused ranking was
recomputed at weights 0, 2, 5, 10 and 35 with every other weight unchanged,
against that set and against the two poetry benchmarks the Latin weights
were tuned on (Lucan 1 and the Achilleid against the Aeneid, 266 gold
pairs). Three whole-file prose sources (Salutati, Seneca's Letters and De
beneficiis, 10 gold pairs) could not be run; 32 gold pairs were scored.

| weight | prose quotations found in top 10 / 50 / 100 (of 32) | poetry top 10 / 100 (of 266) |
|---|---|---|
| 0 (before) | 8 / 14 / 14 | 8 / 22 |
| 2 | 11 / 15 / 20 | 8 / 22 |
| 5 | 13 / 21 / 23 | 8 / 22 |
| 10 (chosen) | 19 / 26 / 28 | 8 / 21 |
| 35 (Coptic value) | 24 / 30 / 32 | 5 / 22 |

Greek (Odyssey 6 against Argonautica 3, 16 gold pairs): unchanged at every
weight; the channel finds no identical three-word runs in Homeric echoes.

**Why 10.** It more than doubles first-ten recall of prose quotations for
one Lucan pair lost at rank 100 and none in the top ten. 35 finds every
quotation but pushes three poetry pairs out of the top ten, so it suits a
quotation-first profile, not the default.

**Caveat.** Fusion results are cached per text pair; a Latin or Greek pair
already cached keeps its old ranking until recomputed.

## 2026-09-19 Quotation table builder rules (PRs #404 to #409)

The corpus-wide Quotation table behind the Reader's quotation markers
(`scripts/reuse/build_reuse_table.py`) was rebuilt for Latin, Greek and
English under rules settled by measurement on Latin against the live table
(54,880 strict pairs):

1. Part files of one work count as one work, so a poem's repeated formulas
   across its own books are not "quotation by another work".
2. An n-gram made only of commonplace words (corpus-frequency threshold, or
   the language's function-word list) still counts toward the pair's shared
   total; a pair is dropped only when EVERY shared n-gram is such, and only
   for English (`--drop-all-commonplace auto`). Two stricter variants were
   measured and rejected: counting such n-grams for nothing cost 5,445
   strict Latin pairs, mostly the Fathers quoting the Vulgate; dropping
   all-commonplace pairs in Latin too cost 1,863, including short scripture
   quotations made entirely of common words (John 10.30 in Hilary). The
   English case that started this ("What shall I do?" in Hamlet, matched to
   eight Bible verses) is a function-word run with no content word.
3. Work ids stored as escaped bytes in older Greek lemma caches are decoded
   back to their Greek file names.

Final Latin table: 54,571 strict pairs, the only losses the 309 part-file
pairs of one work. Details and Done lines: `DATA_OPERATIONS.md`,
2026-09-19.

## 2026-09-19 Reader connection gutter: chunked density (PR #403)

The gutter's density computation scored all of a work's passage windows
against the corpus in one block, 2.5 MB per window (5 GB for the Punica,
11.6 GB for the Vulgate). It now scores 256 windows at a time with
byte-identical output (checked on the whole Aeneid). A batch script
precomputes the cache for every work.

## 2026-09-19 English search: why common words rank high (open)

**Observation.** On the default English pair (Paradise Lost 1 against
Hyperion) the fusion search ranks "began, read", "fled, over" and "summer,
day" beside genuine borrowings like "dire event" and "Saturn old".

**Diagnosis.** Two causes, neither a missing stoplist (the scoring layer
already penalizes function words from the curated English list):

1. Rarity is measured per work, and English has 42 works once part files
   are collapsed, so the scale from "common" to "rare" is compressed.
2. English lemmatization is inconsistent across the lemma cache: "began"
   is a lemma of its own in 2 works and "begin" in 28; "fled" 2 against
   "flee" 24; "stood" 2 against "stand" 30; "went" 2 against "go" 34. The
   unlemmatized forms sit almost entirely in Paradise Lost (whole file and
   its twelve part files) and Wordsworth's Prelude, whose lemma caches were
   built with a different lemmatizer setup from the rest of the English
   corpus. In a Milton search, Milton's own past tenses therefore look as
   rare as proper names, and the rarity boost rewards them.

**Check.** The current English lemmatizer, run on Milton's own lines,
returns "begin, flee, stand, sit" for "began, fled, stood, sat", so the
old caches predate it rather than reflect it.

**Action (same night).** Rebuild the whole English lemma cache with the
current lemmatizer, rebuild the English index and its rarity table, rebuild
the English Quotation table, clear the cached search results for English,
Latin and Greek (the Latin and Greek ones also carry the old quotation
weight), and re-warm the default pairs. Recorded in DATA_OPERATIONS.md.
Rarity by lines rather than works stays deferred until an English gold set
exists to measure it against.
