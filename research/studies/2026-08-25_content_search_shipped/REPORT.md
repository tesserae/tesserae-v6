# Content search, Tessa, and the Coptic quotation channel: 2026-08-25

What shipped, what was found wrong, and what is still open. Written for a future
article and for whoever picks this up next.

---

## 1. What went live

| Feature | State | Where |
|---|---|---|
| Passage index, 603,594 windows, 7 languages | live | `data/passage_index/` |
| Query encoder as its own service | live | `services/embed_server.py`, port 8090 |
| Reader with connection gutter and key | live | `/read` |
| Similar Passages | live | `/api/passages/similar` |
| Theme Search (page + API + MCP tool) | live | `/theme-search` |
| Tessa, the assistant | live | dock on every page |
| Coptic quotation channel | live | `backend/scorer.py` |

Languages in the index: Latin 208,931 windows, Persian 218,213, Greek 113,536,
plus English, Coptic, Hebrew and Urdu.

---

## 2. The Coptic quotation channel was dead in production for eleven weeks

The most consequential finding of the day, and it came out of fact-checking an
article rather than out of testing.

The channel detects runs of three or more consecutive identical surface tokens.
It exists because biblical prose quotes in common vocabulary that the IDF rarity
penalty suppresses, and it is the highest-weighted channel in the
`biblical_coptic` profile at 35.052.

**It contributed nothing.** Fed a real six-token verbatim run, production's
scorer returned score 0.0 with empty `matched_words`, so the weight multiplied
nothing.

### Cause

Commit `e99c778`, "Coptic ship (WIP 2/2): shared-file Coptic + multilingual-e5
hunks, other languages excluded", was assembled by hand out of a branch carrying
several languages. It included `matcher.py`, `fusion.py`, `text_processor.py` and
thirteen other files. It omitted `backend/scorer.py`.
`_score_quotation_match` has never been in any commit on `origin/main`.

So detection shipped, the profile shipped, the weight shipped, and the scoring
did not. Quotation matches fell through to the generic lemma path and were
scored under exactly the rarity penalty the channel exists to bypass.

### Why the tests did not catch it

Tests were added, in `9d6ef7d`, whose message says they cover "the quotation
channel scoring path". They do not. They build a match with the score already
attached and hand it to fusion:

    "quotation": [self._mk(6.0)]

That proves fusion weights a quotation score correctly, which it always did. It
cannot see that no quotation score is ever produced. **A test that supplies the
value under test cannot discover that the value is never computed.**

### Measured effect of the fix

Hebrews x Sahidic Psalms, 124 TSK gold pairs, `biblical_coptic` profile, same
weights on both sides, the only difference being whether `scorer.py` has the
quotation branch:

| | R@50 | R@100 | R@500 | R@1000 |
|---|---|---|---|---|
| production before | 0.040 | 0.040 | 0.056 | 0.065 |
| with the fix | **0.145** | **0.145** | **0.161** | **0.169** |

Recall more than triples at every cut-off. `tests/test_quotation_scoring.py` now
goes through the real scorer: four tests, which pass against the fix and fail
against the old deployment.

**For the article:** the ten-of-ten result in the tables is precision-at-ten on
one comparison, not recall. Both numbers should appear, and the before/after
above is a stronger argument than either alone. Full revision instructions in
`research/coptic_article/REVISION_INSTRUCTIONS.md`.

---

## 3. Confidence calibration went through three versions in one day

Worth recording in full, because each version was wrong in a way the previous
test set could not see.

### Version 1: combined lift and coherence, fitted on sentences

    combined = lift * 10 + (coherence - 0.85) * 10
    MODERATE = 1.40, STRONG = 1.7613

Fitted against 28 sentence-length queries, 93% accuracy. Six of the absent
queries were deliberate near misses at NC's suggestion: classical in register
with one thing in them that does not exist in antiquity. That mattered. "A
farmer lifts potatoes out of the ground and sorts them for seed" scored 1.76,
higher than eight of the twelve real subjects, because everything in it but the
potato is deeply present. Without those queries the strong boundary would have
been set at 1.28 by a tea ceremony.

Also caught here: the fitting script set `strong = max(absent)` while the
classifier compares with `>=`, so the worst absent subject scored exactly at the
boundary and was itself reported strong.

### Version 2: lift as a gate

"Airplanes and locomotives" reported STRONG. Its lift was 0.060, plainly too
low, but its coherence was **1.000**, so coherence carried the whole combined
score. Fix: lift below 0.070 returns low whatever the cluster looks like.

**Why the probe set missed it:** every absent query in it was a plausible near
miss that still returned varied results. None was alien enough to produce
uniform noise, which is the first thing a reader tries.

### Version 3: length-independent, the current one

"plague" reported LOW while its top hit was a plague in Silius 14.581.
"airplanes" reported STRONG. Raw similarity scales with query length, so a
keyword and a sentence were never on the same footing, and every probe the
thresholds were fitted on was a sentence.

Every magnitude statistic was tried — lift, z-score, robust z against the MAD,
ratio to median, head z-score — and all topped out at 82%, because "photograph"
and "television" score high on all of them. Coherence alone reaches 57%.

What works is two signals, the second only after the first:

1. **Degeneracy.** When nothing resembles the query the top results are uniformly
   distant from it and therefore identical to each other, and coherence goes to
   exactly 1.000. That is not agreement, it is the absence of structure to agree
   about. Nine of 57 test queries were degenerate and every one was absent.
2. **Head lift**, the mean of the top TEN above the median rather than the single
   best hit. A real subject brings a group; a stray brings one lucky vector.

```
DEGENERATE_COHERENCE = 0.995
HEAD_WEAK            = 0.0750
HEAD_STRONG          = 0.1006
```

| set | accuracy |
|---|---|
| short queries, 1 to 10 words (28) | 100% |
| original sentence set (32) | 84% |
| combined (57 after dedup) | **91%** |

**The trade, stated honestly:** the old measure was 93% on sentences and
unusable on keywords. The new one loses five deliberate near-misses (ether,
stirrups, a sextant, antibiotics, the potato query) which now read moderate, and
is right on every keyword. Probe sets and fitting scripts are committed:
`evaluation/probe_sets/`, `evaluation/scripts/short_query_confidence.py`,
`evaluation/scripts/validate_confidence.py`.

---

## 4. Description quality

### Names: the check is any-match, and now shows its working

Valerius Flaccus, *Argonautica* 1.1-30 was summarised with participants
"Apollo, Cumaean Sibyl, Aeneas". Apollo is there (`Phoebe`, 1.5) and the Cumaean
prophetess is there (`Cumaeae ... vatis`, 1.5). **Aeneas is not**: 1.9 has
`Phrygios ... Iulos` and the model reached from Iulus back to Aeneas. The gist
was worse than the participant list, attaching the proem to the wrong epic.

The record passed as `names_in_text: True`, because the check asks whether ANY
named person appears.

The any-rule stays, and the reason is recorded in the code: requiring all names
flagged Hebrews 11:20, which names nine figures and has seven, exactly like a
description that invented both of its two. What changed is that the verdict no
longer discards its working. Every participant is recorded verified or
unverified and the unverified ones are named in the Reader and on Theme Search.

Four fixes were needed to make the flag trustworthy, each found by testing:

- Apollo was reported unverified because the passage says *Phoebe*. Added the
  epithets verse actually uses: Pallas, Alcides, Aeacides, Anchisiades, Lyaeus.
- "Cumaean Sibyl" was split per capitalised word, so half of her went missing.
- `fold()` strips spaces, so the passage was one continuous string with no words
  in it and the word-level match could never fire.
- English and Latin name forms diverge: Peter/Petrus, Luke/Lucas, Moses/Moyses,
  Solomon/Salomon. Added a `k`->`c` fold beside the existing `j`->`i` and
  `v`->`u`, a similarity test, and a table of biblical forms.

Then group nouns: Gauls (451), Roman soldiers (432), Achaeans (253) are bodies
of people and cannot be looked up as names.

    unverified rate: 12.9% -> 9.8% -> 6.9%

Tuning stopped there deliberately. The remainder is genuine over-reach (Cicero,
absent from the preface of *Gallic War* 8), epithets no table can hold
(Claudian's `audierat mandata Pater` IS Jupiter), and oblique reference. Adding
`pater` -> Jupiter would falsely verify Jupiter across thousands of passages.

**Unverified never means invented**, and both surfaces say so.

### Plain summaries

14.5% of gists (87,743) opened with a frame carrying no information: "a
narrative of", "a description of", "a vivid depiction of". A result set clusters
them, so the same words landed several times on one screen. The frame is
stripped, keeping the original in `gist_raw`.

    Gists opening "A vivid": 6,256 -> 11

"The passage argues" and "The speaker laments" are equally formulaic, are 45% of
the corpus, and are deliberately kept: they record which voice is speaking and
what it is doing. An adjective like "vivid" is the summariser's opinion, not a
fact about the passage.

### Dates

37.5% of the index showed as undated, 218,213 Persian windows among them. Since
Theme Search orders chronologically, an undated author is dropped out of the
sequence entirely.

    undated: 226,270 (37.5%) -> 97 (0.02%)

28 authors added, mostly the Persian tradition. **Provenance matters:** these
are editorial additions from standard reference knowledge, not from a curated
authority file like the Latin and Greek entries, and every one carries
`"added": "editorial-2026-08-25"`. The dynastic era labels (Samanid, Ghaznavid,
Seljuk, Timurid, Safavid, Mughal) deserve a specialist's eye.

---

## 5. Tessa

Went from a guide that could only name searches to an assistant that runs them.
The failures on the way are the useful part.

- **Recited tool lists instead of searching.** When no search produced facts, the
  question fell to the old guide path, which has no corpus access. Removed for
  corpus questions.
- **No conversation memory.** "Is it in Eobanus?" arrived with no idea what "it"
  was. History now travels from the page, with a session-cookie fallback.
- **Threaded history into `answer()` but not `answer_stream()`.** Every test
  called `answer()` directly, so the fix passed in testing and was dead in the
  browser.
- **Reasoned from a sample to the corpus**, three times: said the corpus held no
  Statius and no Aeneid, when it holds 23 and 14. Named works are now resolved
  in code against the real listing.
- **Fabricated primary text, twice.** First: twelve citations each quoting the
  Aeneid's opening line as Eobanus, because a 3,000-character cap discarded the
  real lines before the model saw them. Second: padding a list to a stated count
  of twelve by inventing loci and pasting Vergil's line under them.

The guards now: citations must come from a search that ran; numbers must appear
in the results or the question; quoted text must appear in the results; and
**quoted text must match the citation it is printed under** — the pairing check,
added because the first quote guard asked only whether text existed *somewhere*,
and Vergil's line does. Guard failures are appended to the answer where the
reader sees them, rather than written to a log.

---

## 6. Infrastructure

**The query encoder runs as its own service.** Apache runs three workers that
recycle every 1000 requests, so an in-process model would be loaded three times
over and reloaded at ~22s a time forever, and PyTorch would sit permanently
inside the web server. `services/embed_server.py`, MemoryMax 6G, holds 0.8 GB,
warm query 0.12s, first query ~7s. **The web application needs no
machine-learning dependency at all.**

Only Theme Search needs it. Similar Passages and the Reader gutter compare
vectors computed at index time.

**Stale pages fail silently and that is not fixed.** `index.html` is served with
no `Cache-Control`, only an ETag, so browsers cache it heuristically. Every
frontend deploy renames the bundle, and Apache's SPA fallback returns **200 OK
with `Content-Type: text/html`** for the missing file — the page pretending to
be JavaScript. The browser fails to parse it and nothing runs: no app, no error
handler, no message. It looks like the site is broken rather than out of date.

Mitigated without root by keeping old bundles on disk
(`scripts/keep_old_bundles.sh`) plus an update banner. **The real fix needs three
lines in the vhost and root access** — snippet in the comment at the top of the
`_cache_headers` hook in `backend/app.py`.

---

## 7. The pattern behind most of these bugs

Nearly every failure had one shape: **verification through a path the user does
not take.**

- the quotation channel: tests fed fusion a score the scorer never produced
- Tessa's history: tested through `answer()`, shipped through `answer_stream()`
- the blank homepage: the build passed, the page was never loaded
- confidence: fitted on sentences, used on keywords
- the name check: measured with a rule that could not see the failure

The fix in each case was to test through the door the user goes through, and
that is the practice worth carrying forward.

---

## 8. Open

- **Content as a fusion channel** (NC). See
  `research/motif_feature/OPEN_QUESTIONS.md` for the four problems: scale
  mismatch between lines and windows, no rarity equivalent, calibration that
  does not transfer, and that content similarity is not evidence of contact.
- **Cache-Control vhost change**, needs root.
- **Persian and Urdu era labels**, need a specialist.
- **Coptic per-text attribution**: production serves zero Coptic rows in the
  attribution table. The file with them has 760 fewer entries overall, so it
  cannot simply be committed.
- **Translation alignment**: original and translation sit in two columns, not
  interleaved line by line.
- **Title case** is applied site-wide from `backend/utils.py:title_case`.
