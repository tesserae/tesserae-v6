# Decisions

Method and scoring decisions that change what the site returns, with the
measurement behind each and where to find the data. One entry per decision,
newest first. Working notes and evaluation folders are kept outside this
repository; this file is the record a later reader can find. Operational
history (index builds, cache rebuilds, corpus changes) is in
`DATA_OPERATIONS.md`; per-release changes are in `../CHANGELOG.md`.

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
layer penalizes those as function words. Adopted (NC, 2026-09-19 23:58, "Go ahead with that stop list"). The list, 274 words (220 plain words plus the 49 Snowball contractions and five apostrophe forms, since the tokenizer keeps contractions whole), is the Snowball English
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
