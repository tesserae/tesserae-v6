# Content search

**Live since 2026-08-25.** Finds passages by what they are about rather than by
the words they use, across every indexed language at once.

Three surfaces share one index:

| Surface | What it does | Needs the encoder? |
|---|---|---|
| **Theme Search** (`/theme-search`) | describe a passage in your own words, get matches | yes |
| **Similar Passages** | passages resembling a selected one | no |
| **Reader gutter** | marks showing where content connects to each line | no |

Only Theme Search embeds a new query, so only Theme Search needs the model
running. The other two compare vectors computed when the index was built.

---

## 1. How it works

### Passage windows

Every text is cut into overlapping **passage windows**. Fine: 12 lines, a new
one every 6. Coarse: 30 lines, a new one every 15. Minimum 4 lines.

The overlap is the point. Without it a passage straddling a boundary is split
down the middle and neither half describes it.

*The unit was called a "scene" until 2026-08-25. NC renamed it: a Horace ode or
a stretch of argument is not a scene, and the description schema knows this, with
lyric, argument and prayer in its own vocabulary. Renamed throughout —
`backend/passage_index.py`, `backend/blueprints/passages.py`, `/api/passages/*`,
`data/passage_index/`.*

### Descriptions

A language model writes a structured English description of each window, in
eight fields: `mode` (closed vocabulary: narrative, speech, lyric, argument,
description, catalog, prayer, prophecy, dialogue), `setting`, `participants`,
`action_steps`, `props`, `themes`, `imagery_tone`, `gist`.

Those descriptions, not the original text, are what a query is compared against.
**This is the whole idea:** a Persian passage can answer an English description
of a Greek scene because two passages are compared by what they are about, with
nothing translated and no words matched.

Describer: Qwen2.5-32B-Instruct. Embeddings: intfloat/multilingual-e5-large,
prefix `query: `, 1024 dimensions, float16. Prompt text capped at 1400 chars.

Lineage: describe-then-retrieve, in the doc2query / HyDE tradition. Measured
cross-language MRR 0.82 against 0.15 for raw multilingual embeddings on the same
task.

### Size, as of 2026-08-25

603,594 windows, 1,849 works.

| Language | Windows |
|---|---|
| Persian | 218,213 |
| Latin | 208,931 |
| Greek | 113,536 |
| Coptic | 13,199 |
| Hebrew | 5,372 |
| Urdu | 2,148 |
| English | (remainder) |
| Arabic | 32 (demo, withheld from release) |

---

## 2. Confidence bands

A search always returns its closest matches, even when the corpus holds nothing
of the kind, so Theme Search reports whether to believe them. **This is the only
calibrated constant in the system**; the context channel measures its own
baseline per text pair and needs nothing.

### The current measure (2026-08-25)

Two signals, the second only meaningful after the first:

1. **Degeneracy.** When nothing resembles the query, the top results are
   uniformly distant from it and therefore identical to each other, and
   coherence goes to exactly 1.000. That is not agreement, it is the absence of
   structure to agree about.
2. **Head lift**, the mean of the top TEN above the corpus median, rather than
   the single top hit. A real subject brings a group; a stray brings one lucky
   vector.

```
DEGENERATE_COHERENCE = 0.995
HEAD_WEAK            = 0.0750
HEAD_STRONG          = 0.1006
```

Fitted against 57 queries from one word to ten: **100% on short queries, 84% on
the sentence set, 91% overall.**

### How it got here, because each version was wrong in a way the previous test could not see

**Version 1 — combined lift and coherence, sentences only.** `combined = lift*10
+ (coherence-0.85)*10`, MODERATE 1.40, STRONG 1.7613, 93% on 28 sentence probes.

Six absent probes were deliberate near misses, at NC's suggestion: classical in
register with one thing in them that cannot exist in antiquity. That mattered
enormously. *"A farmer lifts potatoes out of the ground and sorts them for seed"*
scored 1.76, **higher than eight of the twelve real subjects**, because
everything in it but the potato is deeply present. Without those probes the
strong boundary would have been set at 1.28 by a tea ceremony.

Also caught: the fitting script set `strong = max(absent)` while the classifier
compares with `>=`, so the worst absent subject sat exactly on the boundary and
was itself reported strong.

**Version 2 — lift as a gate.** "Airplanes and locomotives" reported STRONG. Lift
0.060, plainly too low, but coherence 1.000, so coherence carried the whole
score. Fixed by making low lift decisive.

*Why the probe set missed it:* every absent probe was a plausible near miss that
still returned varied results. None was alien enough to produce uniform noise —
which is the first thing a reader types when testing whether a search is honest.

**Version 3 — length independence, the current one.** "plague" reported LOW
while its top hit was a plague in Silius 14.581; "airplanes" reported STRONG.
Raw similarity scales with query length, so a keyword and a sentence were never
on the same footing, and every probe fitted on was a sentence.

Every magnitude statistic was tried — lift, z-score, robust z against the MAD,
ratio to median, head z-score — and all topped out at 82%, because "photograph"
and "television" score high on all of them. Coherence alone reaches 57%.

**The trade, stated plainly:** the old measure was 93% on sentences and unusable
on keywords. The new one loses five deliberate near-misses (ether, stirrups, a
sextant, antibiotics, potatoes) which now read moderate, and is right on every
keyword. A reader types keywords first.

Probe sets and fitting scripts: `evaluation/probe_sets/`,
`evaluation/scripts/short_query_confidence.py`,
`evaluation/scripts/validate_confidence.py`. See
[evaluation/METHODOLOGY.md](../evaluation/METHODOLOGY.md).

### Presentation follows the verdict

When the verdict is low the results are **not laid out**. The reader is told the
corpus does not appear to contain passages of this kind, and offered "Show the N
nearest passages anyway". They are not hidden — what came closest is sometimes
exactly what a scholar wants — but they are not presented as findings until
asked for. A list of twenty results reads as twenty findings whatever the banner
says.

---

## 3. Results presentation

- **Chronological, oldest first**, with the author's date in its own column at
  the left. A content search crosses centuries, so the reading order is itself
  information.
- **Grouped by work.** Several passages from one work sit under one heading with
  its date and language; each keeps its own locus, summary and themes. Not
  collapsed: the passages differ and their summaries are the point.
- **Dates** come from `backend/author_dates.json`. Undated fell from 37.5% of
  the index to 0.02% on 2026-08-25 (see
  [description_quality.md](description_quality.md)).
- **Clicking a passage** opens the Reader at that span with the translation
  panel open and the originating search shown above the text.

---

## 3a. The index answers sentences, because it is built from sentences

Measured 2026-08-25, and the largest single effect on result quality found so
far. A query shaped like a noun phrase lands somewhere quite different from one
shaped like a sentence:

| query | target | best rank | in top 50 |
|---|---|---|---|
| "warrior arming scene" | Iliad arming scenes | 1440 for il. 19.361 | **0** of 245 |
| "a warrior arms himself before battle, piece by piece" | same | 66 | 7 |
| "the shortness of life" | Seneca, *De Brevitate Vitae* | 31 | 1 |
| "life is short" | same | **1** | — |

Two things are going on and they compound:

- **Grammar.** Descriptions are sentences about what happens, so a sentence query
  sits near them and an abstract noun phrase does not.
- **Stance.** Seneca argues that life is NOT short. Embeddings handle negation
  poorly, so his descriptions sit far from "the shortness of life" while a poem
  lamenting brevity sits close. Notably "life is not short, we waste it" ranks
  him best of all.

This is a property of describe-then-retrieve, not a defect to patch away, and it
is worth stating in any write-up of the method: **the system finds passages that
DEPICT a subject more readily than passages that ARGUE about it.**

### What was done about it (shipped 2026-08-26)

Templates in code were measured first and rejected: they recover some of the gap
and not enough (rank 57 to 12 on the arming case, still nothing in the top 50),
because "a passage in which warrior arming scene" is not English, so the
embedding drifts toward sentence-space without landing in it.

What shipped is a model-written expansion. A query of six words or fewer is
rewritten by the local model into three sentences -- the scene, the scene said
differently, and the subject stated the OTHER way round so that a passage
arguing the negation still matches -- and the best score per window is kept.

| query | mode | best rank | in top 50 |
|---|---|---|---|
| warrior arming scene | plain | 57 | 0 |
| | model-expanded | **7** | **5** |
| the shortness of life | plain | 31 | 1 |
| | model-expanded | **8** | **4** |

Zero of eight absent probes became findable, so nothing was traded for it. The
negation form is what finds Seneca, which is the direct answer to the stance
problem above.

### Two further things that had to be fixed with it

**One work was owning the page.** Scores here are compressed to a degree that
makes raw rank a poor guide: on "warrior arming scene" the top window scored
0.8701 and rank 4546 scored 0.8174. What fills a page is therefore repetition,
not relevance. Ferdowsi's and Nizami's Diwans are each ONE work holding tens of
thousands of windows described in near-identical words, and between them they
held 13 of the top 20. The page is now built in two passes: works are chosen
first, one window each, and only then does each chosen work show up to three
passages. Aeneid position 89 -> 19, and the Iliad keeps its several arming
scenes, which a flat per-work cap would have thrown away.

**The same query gave different answers.** Expansion ran at temperature 0.3.
Setting it to 0 was not enough -- identical calls still returned different
sentences -- so expansions are written to a shared file and reused. That also
makes the three Apache workers agree with each other. A scholar who cites a
result has to be able to find it again.

### The limit that remains: descriptions differ in granularity

Vergil still does not return for "warrior arming scene", and this one is not
ranking. The windows exist and are described correctly, just summarily:

    Iliad 11.16   action_steps: puts on greaves; puts on cuirass; puts on sword;
                                takes shield; puts on helmet
    Aen. 12.87    action_steps: Aeneas arms himself; Aeneas takes a spear
    Aen. 11.486   action_steps: arming; charging into battle

A piece-by-piece query matches Homer's enumeration and not Vergil's summary. No
ranking change fixes this, and tuning around it would be fitting the retrieval
to one query. The real fix is re-describing with a prompt that forces consistent
detail, which costs GPU time. See `research/QUEUE.md`.

## 4. Limits a reader is told about

- The summaries are machine-written: a finding aid, not evidence.
- Where a summary names someone the passage does not appear to name, the result
  says so. A flag to check, not proof of error.
- **Coptic descriptions were written from English translations**, not from
  Coptic, because no available model reads Coptic well enough. Evidence at one
  remove. Every record carries `derived_from_translation`.
- **Persian and Urdu intertextuality often works through form** — a poem
  answering another in the same metre, rhyme and radif, sometimes with almost no
  shared vocabulary. These descriptions capture content, not form, so that whole
  mode of response is invisible here.
- The first search after a quiet period takes about ten seconds while the
  encoder loads. After that, well under a second.

---

## 5. Performance

- Similar Passages: 0.28s
- Reader gutter: 5.4s first visit, instant thereafter (cached)
- Theme Search: ~0.7s warm, ~12s cold

Scoring is one pass over the whole embedding matrix. numpy's matrix-vector
product is **single-threaded**, which was the real bottleneck; splitting across
threads is a measured 4.1x and needs no extra memory. An earlier diagnosis
blamed float32 conversion and both proposed fixes were slower.

---

## 6. Adding texts

See `motif_feature/ADDING_TEXTS_TO_THE_CONTENT_INDEX.md`. In short: new texts
need windowing, describing (GPU), embedding, and merging with
`scripts/merge_index.py`, which checks that ids and embedding rows stay in
lockstep and refuses to write if they do not. The existing index is not
recomputed.

**The invariant that matters:** ids, embedding rows and description records must
agree in count and order. A slice whose ids and rows disagree does not fail
loudly, it returns the wrong passage for every query.

---

## 7. Release

`scripts/build_passage_index_release.py` splits the index per language so each
slice carries its own licence. One bundle would force BHSA's non-commercial term
onto the 98.6% of the index that does not carry it. See
[corpus/TEXTS_AND_LICENSING.md](../corpus/TEXTS_AND_LICENSING.md).

---

## 8. Open

- **Content as a fusion channel** (NC). Four problems make it hard: scale
  mismatch between lines and windows, no rarity equivalent, calibration that
  does not transfer, and that content similarity is not evidence of textual
  contact. See [motif_feature/OPEN_QUESTIONS.md](../motif_feature/OPEN_QUESTIONS.md).
- Translation and original sit in two columns, not interleaved line by line.
- The 84% on the sentence probe set is worth improving without losing keyword
  accuracy.
