# Decisions

Method and scoring decisions that change what the site returns, with the
measurement behind each and where to find the data. One entry per decision,
newest first. Working notes and evaluation folders are kept outside this
repository; this file is the record a later reader can find. Operational
history (index builds, cache rebuilds, corpus changes) is in
`DATA_OPERATIONS.md`; per-release changes are in `../CHANGELOG.md`.

## 2026-10-01 Koine forms get a second lemma table, and the treebank table keeps the last word

**Question.** The Greek lemma table comes from Ancient Greek treebanks and
has little Koine in it. On the Septuagint the lemmatizer falls to the CLTK
backoff, which invents stems (υμνειτοσ for ὑμνεῖτε, λημψοσ for λήμψομαι),
or leaves the surface form. Measured on the production index, 71,572 of
589,484 Septuagint tokens (12.1%) carried a lemma that is no known lemma,
40,733 of them the surface form itself. Dictionary candidates drawn from
the Septuagint inherited the invented stems.

**Measurement.** Of the unresolved tokens, 5,837 were tokenizer artifacts
(the ano teleia and the spacing breathing kept on the word, fixed
separately). A table built from the Rahlfs Septuagint morphology (31,069
forms the treebank table lacks) resolves 53,164 of the remaining 66,035
(80.5%). What is left is inflected proper names for the most part. On the
Greek New Testament the treebank table already covers all but 0.35% of
tokens. 1,336 forms are in both tables with different lemmas: some are
Koine readings that are better (ἄγε as the imperative of ἄγω, not a lemma
of its own), and some are homograph ambiguities (ἀγών "contest" against
the participle of ἄγω) that a lookup table cannot settle either way.

**Decision.** The Koine table is loaded after the treebank table and fills
only the forms it lacks. The treebank table wins on every shared form, so
no lemma in a classical text changes, and the conflicts are kept in a file for
review and not applied. The source carries a Creative Commons
Attribution-NonCommercial-ShareAlike licence, the same family of terms as
the Hebrew morphology, and the attribution file names the repository and
the CCAT analysis it derives from.

**Left open.** The 1,336 conflicts, to be read by eye. The proper names
still unresolved, which would need a names table. The full Greek rebuild
that applies this table and the tokenizer fix to the index.

## 2026-10-01 Hebrew-Greek dictionary candidates pass through a model judge and a reader, never straight in (#519)

**Question.** The 1,787 Hebrew-Greek pairs proposed from verse alignment
(co-occurrence at least 10, lift at least 5) are mostly neighbours, not
translations: Pharaoh beside Egypt, flock beside shepherd, king beside
book. The first pass had taken 26 by hand. How to get the rest of the real
equivalents out without reading 1,787 rows.

**Measurement.** A triangulation through Latin (the Greek word's Latin
translations meeting the Hebrew word's) passed 32 and was wrong on about
a third of them, and in doing so exposed errors in the Hebrew-Latin bridge
(gold reaching argentum, six reaching quattuor), which is now its own
item. A model judge (Qwen 3.8 on the gateway, no reasoning, each pair with
the Hebrew word's BHSA glosses) answered yes to 216 of 1,787 at high
confidence. Of those, 88 had a Greek side that is no lemma at all (υιρι,
ελαλησ, γαη): the candidate generator's Greek lemmatizer leaves many
Septuagint forms unlemmatized. The 128 left were read one by one: 97 are
translation equivalents in some sense of the Hebrew word, 31 are not
(metonymies such as אכל with ἄρτος, neighbours such as בקר with πρόβατον
and אהל with μαρτύριον, and plain judge errors such as אתה with εἰ).

**Decision.** Candidates reach the dictionary only after the judge, the
artifact filter and a reading. The 74 pairs not already present are added
with a dated comment line naming the method. The 88 artifact rows are not
added even where the sense is right, because a dictionary of real lemmas is
what the file is, and the index tokens behind those forms are a
lemmatization problem to fix at its source.

**Left open.** The Greek lemmatizer's coverage of Septuagint forms, which
both pollutes candidates and leaves those tokens reachable only by their
surface form. The Hebrew-Latin bridge audit (HE.5 on the private list).

## 2026-10-01 Hebrew homographs are separate lemmas, read from the vowel points (#483)

**Question.** The Hebrew lemma table was keyed by consonants and kept the
first lemma BHSA listed for a spelling, so words that share their letters
collapsed into one lemma. Issue #483 named the cost. Stopping אל for
the preposition also stopped אל "God", and מלך "he reigned" was tagged as
the noun "king". Three ways were open. Leave ambiguous words off the stoplist
and accept the noise, keep one lemma per spelling but mark homographs in
the table without a way to choose between them, or read the vowel points,
which the text has and the lemmatizer discarded.

**Measurement.** On BHSA's 420,102 word occurrences, 3,430 consonantal
spellings cover more than one lexeme and 21,687 occurrences (5.2%) take the
wrong lemma under the majority reading. Keyed by pointed form, 1,408 keys
remain ambiguous and 4,804 occurrences (1.1%) take the wrong reading. A
pointed table built from BHSA finds 99.3% of the 328,822 words in texts/he
once the two editions' conventions are folded into the key: holam written
before or on the waw, dagesh present or absent, holam haser for waw and
qamats qatan as their plain marks.

On the held-out doublet 2 Samuel 22 = Psalm 18 (51 verse pairs, current
code on both sides, the old and the new Hebrew index) the default search
finds 10, 35, 40, 47, 48 and 49 of them in the top 10, 50, 100, 500, 1,000
and 5,000, against 10, 36, 43, 47, 47 and 49 before. Forty pairs moved,
twenty-four down and sixteen up, most by a few places. The one large mover
is 22.27 = 18.27 (13th to 71st): its shared words were ברר, עקש and עם, and
עם "with" is now the stopped preposition עם² while the old lemma, which also
meant "people", had passed as a content word. Two pairs gained correct
lemmas the old table could not give (22.30 = 18.30: "I run", אָרֻץ, had been
read as "land", and the prefix in בְכָה as "weep"). The doublet is a
near-verbatim parallel and does not measure what the change is for, which
is correct lemmas for one word in twenty, correct tags, a stoplist that
stops function readings only, and fewer pairs built on a shared spelling
with different meanings. The lemma-only configuration of the benchmark
cannot be read across this change. In its merged line-and-window mode
three gold pairs that the lemma matcher does produce (checked directly)
fall out of the result list, and in line mode they are present at ranks
76, 85 and 102.

**Decision.** Pointed lookup first, consonantal fallback. A lemma is the
consonantal spelling. When a spelling covers several lexemes the most
frequent keeps the bare spelling and the others carry a superscript numeral
in order of BHSA frequency (אל, אל², אל³, and עם "people", עם² "with"). The
numeral is part of the lemma everywhere lemmas are stored or compared, and
is stripped only where a lookup is keyed by consonants (the cross-language
dictionaries). The bare spelling goes to the most frequent reading rather
than to a fixed part of speech, because an unpointed query (a reader
typing אל) should find the reading it most often means, and the stoplist
names the rest by number. The stoplist stops function readings only.

**Rejected.** Marking homographs with BHSA's own symbols (אל=, אל/) was
rejected: the slash and bracket mark part of speech, not identity, and the
symbols would reach the display. A fixed part-of-speech order for the bare
form was rejected for the reason above. Rebuilding the dictionaries by
homograph was deferred: they are keyed by consonants from CATSS and the
aligned verses, and the stripped lookup loses nothing they had.

**Left open.** Unpointed queries take the majority reading, so a line search
for אל does not also find אל³. A query-time expansion to the whole homograph
group is the follow-up. Latin and Greek have the same collapse in a smaller
way (the lemma tables keep one lemma per form) and could use the same
mechanism with a different disambiguating signal.

## 2026-09-30 Theme Comparison, two works read against each other by content

**Question.** Theme Search reads the whole corpus against a description a
reader writes. Asked what two named books share in content, the site had
no answer, and the assistant said so. Can the same vectors compare two
works directly?

**Check.** Every passage window of one work scored against every window of
the other on the Similar Passages vectors, in blocks, each window of the
first work keeping its three best partners, pairs deduplicated on the
unordered pair. A whole work stored as book files gathers its books, and a
named book keeps to its own windows. On the live index, Aeneid 1 against
Lucan 1 puts Jupiter's prophecy (1.289) beside Lucan's prophecies (1.661,
1.31) and the storm beside the panicked exodus. The whole Aeneid against
the whole Bellum Civile puts storms with storms, a leader rallying troops
with the same, battle chaos with battle chaos, in a tenth of a second
once the index is loaded. Metamorphoses 1 against Hesiod's Theogony,
across languages, puts the cosmogonies together.

**Decision.** Shipped as Theme Comparison, with a "Compare two works" mode on
the Theme Search page, the route /api/passages/compare, the connector tool
theme_compare, and a path in the assistant that runs it for a question
about what two texts share in content and reads the best pairs from the
descriptions alone. Confidence reads the pair's own score matrix, the
median as baseline and the mean of the top ten above it as head lift,
with the Theme Search lift thresholds. This is a convention carried over,
not a fit, until a graded sheet of pairs exists. Pairs beyond forty
million cells are refused with advice to compare books.

## 2026-09-30 The assistant runs the comparison she is asked for (#533)

**Question.** Asked to compare two texts, the assistant said the corpus
held both and offered a control that opened the search. That was right
for a model that took twenty seconds to write a sentence and a search
that can take minutes. Is it still right with the model on the gateway?

**Check.** A cached pair's first page comes back from the fusion route at
once, and the results prompt reads twenty-five parallels in two to four
seconds with every guard reporting clean (the Statius against Aeneid
reading in the 2026-09-30 prompt entry). An uncached pair starts its run
on the first request and most finish within a minute or two.

**Decision.** For two texts in one language she fetches the first page,
waits up to a hundred seconds with a word to the reader while the run
starts, reads the page with the results prompt and its guards, and still
offers the control that opens the full list. Whole authors and
cross-language pairs hand over as before. The site's copy about her
says search, read, interpret, since that is now what she does.

## 2026-09-30 The assistant's accuracy is checked and recorded, not sampled (#532)

**Question.** The guards check citations, quotations and figures against
the material the assistant was given. Once she may add general knowledge
as background, a wrong century or a misattributed work carries none of
those and passes. What checks that?

**Check.** A second pass with the same model and the same material, asked
only for specific claims (a date, century or reign, an attribution, a
title, a work's contents) the material does not support, with a revision
that removes or softens the specific. Tried on a live answer about
Dracontius it removed "priest, active in the sixth century" and left "a
late antique Latin poet" and the judgement that he imitated Vergil, which
is the intended line: specifics are checked, judgements are hers. A first
version flagged the period word and the judgement too and gutted a fair
answer, so a filter now keeps a finding only when the sentence carries a
date-like token or the claim names a title, attribution or contents. The
pass takes about two and a half seconds after the answer.

**Decision.** Every answer runs through the check, and every exchange is
kept on the server with no identifier for a weekly sample reading. A
graded question set for the live site follows separately. The check is
a net, not a proof: a correct date it happens not to flag is a correct
date, and a wrong one it misses is what the weekly reading is for.

## 2026-09-30 The assistant is asked to judge, not only to report (#531)

**Question.** The assistant's prompts were written for a model with about
three billion parameters active, and confined it to naming searches and
putting computed facts into prose. With a 27-billion-parameter model
answering, can it be asked to weigh the parallels it is shown without
losing the one property that matters, that it never supplies a citation,
a quotation or a figure of its own?

**Check.** Old prompt against new on the same gateway model: three real
result sets (Lucan 1 against Aeneid 1, Thebaid 1 against Aeneid 1,
Metamorphoses 1 against De rerum natura 1), the default reading and three
questions each, plus eight guide questions. The guards stripped no
reference on either side and found every quotation in the passages
given. Number flags fell from twelve to seven, most of them the words
"twenty-five" for a 25 in the facts, which the guard now reads as one
number. Shown ten passages of up to 400 characters instead of five of
180, the new prompt found and explained the Thebaid 1.473 "meminisse
iuvet" against Aeneid 1.203 "meminisse iuvabit" echo, which the old one
never saw. Asked about a lesser-known author, the model invented a title
twice. Handing it the corpus's list of that author's works, with the
site's blurbs where they exist, stopped the invented titles. It did not
stop a wrong date offered from general knowledge.

**Decision.** The new prompts ship. Background about authors is marked as
background and draws on the site's own blurbs, which exist today only for
texts imported since late August. Writing blurbs for the rest of the
corpus is the follow-up, recorded separately when done.

## 2026-09-30 The assistant's model moves to the university's AI platform (#528)

**Question.** The assistant's model (Qwen3-30B-A3B under llama-server on
the web server's CPU) holds about 25 GB of memory, takes 15 to 20 seconds
to a finished paragraph, and forces every other heavy job on the machine
to run one at a time. The university's own AI platform serves larger open
models over an OpenAI-compatible gateway at no cost to the project. Is an
answer from there as good, and how fast?

**Check.** Ten of the assistant's typical questions (eight on using the
site, two reading a fixed set of search results) were put through her own
prompts to four gateway models. Qwen 3.8 27B with thinking off answered in
1.1 to 2.0 seconds and kept every rule. It named the right tool, declined
the request for scholarship with the right reason, said when the help
material it was given did not cover a question, and read the results
without invention. GPT-OSS 120B was fuller but explained a score from its
own knowledge, which the prompt forbids, and once returned nothing when
its reasoning consumed the token cap. GLM 5.3 Flash reasons before it
speaks and produced no visible text within the cap. Gemma 4 E4B misstated
what the help covered. A like-for-like run against the local model
follows the same day.

**Decision.** The client is made configurable for a keyed gateway with the
local server as the unchanged default. Production moves to Qwen 3.8 with
thinking off on the campus gateway, and the local model server is stopped,
returning its memory to the machine. Questions stay on campus. The Help
page says so.

## 2026-09-28 Hebrew stoplist: עם and שם come off, אל, את and על stay (#483 §2)

**Question.** Hebrew lemmas are consonantal, so one stoplist entry stops
every word with those consonants. Five entries collapse a function word
with a content word. Which should stay stopped until lemmas can tell them
apart?

**Measurement.** Every word in BHSA (ETCBC/bhsa via Text-Fabric), grouped
by the consonants of its lexeme, Hebrew and Aramaic together:

| Entry | Function readings | Content readings | Content share |
|---|---|---|---|
| עם | "with" 1,071 | "people" 1,881 | 64% |
| שם | "there" 834 | "name" 876, Shem 17 | 52% |
| אל | "to" 5,517, "not" 730, "these" 10, "where" 1 | "God" (El) 235, "power" 5, "nothingness" 1 | 3.7% |
| את | object marker 10,987, "with" 878, "you" 57 | "ploughshare" 5, "sign" 3 | 0.1% |
| על | "upon" 5,870 | "yoke" 40, "height" 9 | 0.8% |

**Decision.** Remove עם and שם: stopping them discarded more content
words than function words. Keep את and על, which are almost wholly
function words. Keep אל for now: its content reading is El (the usual word
for God, אלהים, is a separate lemma and is not stopped), and unstopping it
would admit some 6,250 occurrences of "to" and "not" to recover 235. The
list is now 52 entries.

**Revisit** when lemmas are looked up by pointed form (#483 §2–3, fix C),
which would separate אֵל from אֶל and עַם from עִם so each function reading
can be stopped alone.

**Effect.** The stoplist is applied at search time, so no index rebuild is
needed, but cached Hebrew results must be cleared: the cache key does not
include the stoplist. The classic lemma matcher's automatic mode also adds
a frequency cutoff (the Zipf elbow over the two texts), which can still
stop עם or שם in a long pair; that mechanism is unchanged.

## 2026-09-28 Hebrew stoplist: entries that can never match are removed (#483 §1)

**Observation.** The Hebrew stoplist (`backend/hebrew/stopwords.py`) is
compared against lemmas, but ten of its 64 distinct entries were prefixed
surface forms or forms the BHSA table never gives as a lemma, so they
stopped nothing: ויהי (becomes היה), והנה (הנה), לפני (פנה), אחרי (אחר),
כאשר (אשר), ההוא (הוא), ההיא (היא), האם (אם), אתם (את), אתן (נתן). Three
entries were also listed twice (את, אל, אין).

**Decision.** Remove the ten and the duplicates; the list is now 54
entries (52 after the entry above). Their lemmas were not added in their place. Six (הנה, אחר, אשר,
הוא, היא, את) are already on the list; the other four (היה "be", פנה
"face", אם "if"/"mother", נתן "give") are content words or homographs of
one, and the standing rule keeps content words off stoplists.

**Effect.** None on results: the removed entries never matched a lemma.
The homograph entries (אל, עם, את, על, שם) and the pointed-form lookup
that would separate them are §2–3 of #483 and still open.

**Left open.** The list as a whole is due for review: which Hebrew words
belong on it, including whether any of the four content-word lemmas above
should be, is not settled by this change. The interrogative entry אנה is
kept as it stands although BHSA gives its lemma as אן; אן is not added
until that review.

## 2026-09-27 Persian and Urdu stay in the all-languages Theme Search default

**Question.** Whether the Persian (218,589 windows) and Urdu passage
windows should be left out of Theme Search's default all-languages page,
since Persian alone is more than a third of the index and its two largest
works held most of a page before the per-work composition rule.

**Decision.** They stay in. The page is composed one window per work and
then by language round-robin (see the composition entries), so a large
language no longer crowds the page, and a scholar reading across
literatures should see what the corpus holds without opting in. Anyone
who wants one literature has the language filter.

## 2026-09-27 A work stored as a whole file and as book files keeps only the books' windows

**Observation.** 137 works are stored both ways, and the passage index held
each of them twice: 113,850 whole-file windows beside 112,185 book-file
windows, a third of the 620,773-window index. The same lines were described
and embedded twice under two names. A Similar Passages list could show one
passage twice, the result ranking carried a collapse step to hide that, and
the connections map and every count by work counted these works double.

**Decision.** The book files are the canonical copies (the decision of
2026-09-21, from which the whole files were regenerated), so their windows
stay and the whole file's are dropped. The Reader's whole-work view draws
its gutter marks from the books' windows through the existing whole-work
fallback in `connection_density`, and a selection in that view maps to a
book window the same way. The references are the same line references, so
the marks fall on the same lines.

**Exception.** Eight works have a book file with no windows of its own: a
two-line poem of Catullus, a preface, a set of fragments, fifteen files of
one to five lines in all. The whole file's windows are the only ones
covering those lines, so those eight keep both copies until the fifteen
files have windows. The tool refuses them unless told otherwise.

**Tool.** `scripts/corpus/drop_whole_file_windows.py`, dry run by default.
It backs up the four index files, drops ids, embedding rows, descriptions
and window-text rows in step with count checks, leaves the works' line rows
alone, and reports what it kept and why. Tests in
`tests/test_drop_whole_file_windows.py`. The dry run against the live
index names 129 works and 110,631 windows. The operation and the cache
rebuilds it forces (word index, passage density, connections map) are
recorded in DATA_OPERATIONS.md when run.

## 2026-09-27 Coptic: U+03E2 to U+03EF is the normal form of the seven Coptic-only letters

**Question.** Unicode has the Greek-derived Coptic letters at U+2C80 to
U+2CB1 and the seven Coptic-only letters (ϣ ϥ ϧ ϩ ϫ ϭ ϯ) at U+03E2 to
U+03EF. Which code points should stored Coptic forms use?

**Observation.** The normaliser moved the seven to U+2CB2 to U+2CBF in the
belief that these were the same letters in the Coptic block. Unicode names
them Dialect-P alef, Old Coptic ain, cryptogrammic eie, Dialect-P kapa,
Dialect-P ni, cryptogrammic ni and Old Coptic oou. Because query and text
were moved alike, no search was affected, but every stored form was wrong,
11,722 of 29,323 index lemmas among them, and anyone reading the
dictionaries outside Tesserae received the wrong letters. Twelve texts use
U+2CBB and two neighbours as editorial marks, which the tokenizer counted
as letters, so a mark glued to a word changed the word.

**Decision.** The seven letters stay at U+03E2 to U+03EF, their only code
points. U+2CB2 to U+2CBF are stripped by the normaliser as marks. There is
one normaliser, in `backend/coptic/processor.py`, and the interface and the
build scripts use it rather than copies. Traditional Coptic alphabetical
order, the seven letters last, is kept in the Rare Words Explorer by its
sort key, not by the stored form.

**Consequences.** Every stored Coptic form changes, so the dictionaries and
stoplist are corrected in the same change (`scripts/corpus/restore_coptic_letters.py`,
a one-to-one reversal) and the lemma caches, the Coptic index and the rare
words cache are rebuilt at deploy, recorded in DATA_OPERATIONS.md. Tests:
`tests/test_coptic_letters.py`.

## 2026-09-27 A third shared word raises the score: the sum, not the mean

**Question.** The lemma score sums the rarity (IDF) of the words two lines
share and divides by a corpus term. The code also divided by the number of
shared words, which made the sum a mean. Should it?

**Observation.** Under the mean an extra shared word raised the score only
when it was rarer than the words already counted. Aeneid 1 against Lucan 1
on 2026-09-22, 150 two-word results averaged 0.746 and the two three-word
results scored 0.538 and 0.468 (issue #465). This contradicts Coffee et al.
(2012), which the scorer cites, and the scorer's own docstring at the time.

**Measurement, 2026-09-27.** Lucan book 1 against the whole Aeneid on a test
checkout of main with the divisor switchable, data from production, results
cache bypassed.

Lemma search, at least two shared words, no ceiling: 2,088 results and 50
of the 213 attested parallels under either rule, order only differing.

| | mean | sum |
|---|---|---|
| attested in the top 10 | 6 | 6 |
| attested in the top 50 | 14 | 14 |
| attested in the top half | 40 | 43 |
| mean rank of an attested parallel | 541.5 | 473.1 |
| median rank | 396 | 344 |
| mean score, two shared words (2,058) | 0.704 | 1.409 |
| mean score, three shared words (29) | 0.534 | 1.601 |
| the one four-word result | 0.494 | 1.975 |

Fusion search, every channel, about 204,000 results, 75 s a run:

| | mean | sum |
|---|---|---|
| P@10 | 50% | 60% |
| P@50 | 26% | 28% |
| P@100 | 18% | 17% |
| R@500 | 20.2% | 20.2% |
| R@1000 | 25.8% | 25.8% |
| R@5000 | 41.8% | 41.3% |

**Decision.** The sum. The divisor is the corpus term alone
(`backend/scorer.py`). Both searches improve or hold, and the code again
does what its description and the published method say. Scores roughly
double for two-word matches. Nothing downstream depended on the old scale
in any way the fusion benchmark could see.

**Consequences.** Every lemma and fusion score changes. The results cache
is keyed on the search settings, which the rule is not, so at the rarity
deploy of 2026-09-22 cached searches kept answering under the old rule
until the files were deleted by hand. The rule's name
(`SCORING_RULE` in `backend/score_bounds.py`) is now part of every cache
key, so a changed rule orphans the old entries by itself and no clear can
be forgotten. `tests/test_scorer_rules.py` pins the rules the scorer
promises, including this one and the key. Data: `research/threads/465_measurement/` (kept outside the
repository).

## 2026-09-25 Hebrew: the Stanza fallback is off, and the index is built the way the server runs

**Question.** Words the BHSA lookup table does not have can be handed to
Stanza, an optional analyser, for a guessed dictionary form. Should the
fallback be on?

**Observation.** Stanza is listed in requirements.txt but was never
installed in the production environment, and because the fallback is
optional nothing reported it. The Hebrew index, built where Stanza was
installed, carried its guesses. Live queries did not. Measured on
2026-09-25 by building the index both ways from the same texts: 200 of
305,550 tokens (0.065 percent) take a different lemma with Stanza than
without. Every one is a word the table lacks, mostly rare names and
unusual forms. Installing Stanza on production would load a language model
in each of three web workers, the pattern the query encoder was moved out
of the web app to avoid.

**Decision.** Off unless `TESSERAE_HEBREW_STANZA=1` is set, on the server
and at build time alike (`backend/hebrew/processor.py`). The production
index was rebuilt without it the same day and swapped in, so the index and
the live server now agree on every word. A fraction of a percent of Hebrew
words keep their surface form instead of a guessed lemma.

**Effect.** Jerusalem, the case that started the Hebrew work, is unchanged:
625 postings on one lemma. Tests: `tests/test_hebrew_processor.py`, the
default-off case and the switch.

## 2026-09-25 Part-of-speech classes come from one table per tag scheme, and an untagged word abstains

**Question.** The part-of-speech boost compares the class of a shared word
in the source with its class in the target. Which class does each stored
tag belong to, and what does a word nobody tagged contribute?

**Observation.** Sampling 25 lemma-cache files per language on 2026-09-25
found three tag schemes in use. Hebrew stores Universal Dependencies tags
throughout. English stores Penn Treebank tags in 3 of 14 files and `UNK`
elsewhere, 85 percent of its tokens. Greek stores the nine-position Perseus
treebank code for 42 percent of its tokens and `Unk` for the rest. Latin
stores `UNK` for 82 percent of its tokens and the Perseus code in 4 of 25
files. The normaliser told these apart by prefix. `PROPN` begins with `PR`
and was classed as a pronoun (issue #487). Of the Perseus code only the `N`
and `V` positions were recognised, so seven other word classes became
OTHER, which matches itself. `UNK` also became OTHER, so two untagged words
counted as agreeing.

**Decision.** Each scheme is matched exactly against its own table in
`backend/feature_extractor.py`. Proper nouns and numerals class with nouns.
Auxiliaries and participles class with verbs. The article classes with
determiners. Particles, interjections, exclamations and punctuation are
OTHER. A tag from no scheme, a blank Perseus position, or `UNK` is UNKNOWN,
and a pair with an unknown on either side is left out of both the numerator
and the denominator, so an untagged word neither helps nor hurts. If every
shared word is untagged the boost is 0.

**Effect.** None on live results, because the boost is not in
`enabled_features` in production or in the defaults. Where it is switched
on, a Hebrew name now agrees with a noun rather than a pronoun, and a Greek
adjective no longer agrees with a preposition. The 20 cases in
`tests/test_pos_normalisation.py` are drawn from the stored tags.

**Open.** Whether the boost should be on at all, given how little of Latin
and English is tagged, is not decided here.

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

Adopted on the measurement above.

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

Adopted on the measurement above.

## 2026-09-20 Translations: public domain first, then open non-commercial with attribution (Silius books 9 to 17)

**Decision.**
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

**Decision.** The page is
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

**Decision.** Theme Search
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
   rarity threshold itself (100 works out of 42) is a separate decision,
   taken on 2026-09-22 and recorded above.

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

**Deferred.** A request-size guard in `/api/search` (refuse or
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

**Decision.** A stoplist holds function words (articles,
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
layer penalizes those as function words. Adopted 2026-09-19. The list, 275 words (220 plain words plus 50 Snowball contractions and five apostrophe forms, since the tokenizer keeps contractions whole), is the Snowball English
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
on 2026-09-19.

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
