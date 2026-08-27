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

Embeddings: intfloat/multilingual-e5-large, prefix `query: `, 1024 dimensions,
float16. Prompt text capped at 1400 chars.

#### Which model described what

Three runs have written descriptions into this index. The table is the record;
see the caveat under it before trusting the data itself.

| | original bulk | gap fill | Persian/Urdu re-describe |
|---|---|---|---|
| date | (index built to 2026-08-25) | 2026-08-25 | 2026-08-26/27 |
| model | Qwen2.5-32B-Instruct | Qwen3-30B-A3B-Instruct | Qwen3-30B-A3B-Instruct-2507 |
| precision | BF16 | Q4_K_M (GGUF) | BF16 |
| server | vLLM, in-process `LLM()` | llama.cpp `llama-server` | vLLM 0.28.0 OpenAI server |
| hardware | rented GPU pod | local, CPU, 12 threads | rented A100 SXM 80GB (RunPod, $1.39/h) |
| temperature | 0.0 | 0.2 | 0.2 |
| max output tokens | 380 | 700 | 700 |
| input cap | 1400 chars | 1400 chars | 1400 chars |
| `max_model_len` | 4096 | 8192 (`-c`) | 4096 |
| `gpu_memory_utilization` | 0.92 | n/a | 0.92 |
| concurrency | vLLM internal batching | 4 | 128 threads, `--max-num-seqs 128` |
| script | `work/gpu_describe_v2.py`, `v3.py` | `work/describe_missing.py` | `work/redescribe.py` |
| scope | whole index, 603,594 windows | 35 windows the bulk run missed | 220,361 Persian + Urdu windows |
| `described_by` | *(not stamped)* | `qwen3-30b-a3b-local-2026-08-25` | `redescribe-2026-08` |

**The prompt is not the same across runs**, which matters as much as the model.
The bulk run's system prompt names the languages it expects, "Latin, Ancient
Greek, Hebrew, or English", and Persian and Urdu are absent from that list. It
also defines the key field permissively: "action_steps (list of short strings,
empty list if no action)". The re-describe prompt names the Perso-Arabic scripts
explicitly and requires "Several steps, not one". Both prompts are in their
scripts verbatim; `work/ab_prompt_vs_model.py` holds the bulk prompt as a copy
for comparison.

The bulk run also carried a constraint the re-describe does not: a
`names_present` list per window, extracted by lemma-resolved rarity filtering,
telling the model to name only people from that list. That was added to stop it
calling Aeneid 8.397-408 "Hector speaks to Andromache" when the speakers are
Vulcan and Venus. The re-describe achieves the same end with a prompt rule
rather than a per-window list.

**Caveat: the original run recorded no model in the data.** 99.97% of rows carry
no `described_by` field at all, because the bulk describe script
(`gpu_describe_v2.py` / `v3.py`) took the model as a command-line argument and
never wrote it into the output. So the attribution above rests on prose notes
(`work/describe_missing.py`, which states "the corpus was described with
Qwen2.5-32B on a rented pod") and on this file, not on the index.

An unstamped row therefore means Qwen2.5-32B, by elimination rather than by
record. Every run since stamps itself, so this ambiguity does not grow.

#### Why these models

**Qwen2.5-32B-Instruct, for the bulk run.** Chosen by scaling up a measured
pilot, not by reputation. `motif_pilot_openmodel.py` asked whether a cheap OPEN
model's descriptions could match the hand-labeled gold set on
describe-then-retrieve: it described the 92 gold scenes with Qwen2.5-7B-Instruct
locally and free, ran the same TF-IDF retrieval, and compared against the
hand-labeled baseline (within-language R@5 0.96, cross-language MRR 0.85, R@5
0.95). It also timed generation specifically to project the cost of a full run
on a rented GPU. The constraints that decided it: open weights, so the corpus is
never sent to a third party and the run is reproducible; small enough to serve
on one rented GPU; good enough at 7B in the pilot that 32B was a safe step up
for the real thing.

**Qwen3-30B-A3B-Instruct, for the 35-window gap fill.** Chosen because it was
already running on the box. That job was 35 windows, too small to justify
renting anything, and Tessa's assistant model server was serving on port 8081
anyway. A different model from the bulk run, which is exactly why that run
stamps itself.

**Qwen3-30B-A3B-Instruct-2507, for the Persian/Urdu re-describe.** Continuity
with the gap fill, which had already been shown to produce 6-7 action steps on
the Persian and Urdu samples where the index held none. Its shape also suits a
long batch job: a mixture-of-experts model with 30B total parameters but only
~3B active per token, so it serves far faster than a dense 30B while fitting
one A100 in BF16. Served at full precision rather than the FP8 build because the
A100 is Ampere and has no native FP8: the quantized weights would have run
through dequantization kernels for no gain on passages this short.

Honestly stated: no benchmark was run against alternative model families for
this pass. The choice was continuity with a model already measured on this exact
task, not a bake-off. That is a real limitation of the record.

#### Which variable actually mattered: the prompt or the model?

Worth settling, because the re-describe was justified on a belief about the
model, and the prompts differ too. `work/ab_prompt_vs_model.py` runs the same 24
Persian windows through the current model under three conditions:

| condition | mean `action_steps` | zero-step | failed |
|---|---|---|---|
| A: bulk prompt, bulk sampling (temp 0.0, 380 tokens) | 6.33 | 0/24 | 0 |
| B: bulk prompt, new sampling (temp 0.2, 700 tokens) | 6.29 | 0/24 | 0 |
| C: new prompt, new sampling (what the live run does) | 9.79 | 0/24 | 0 |

Against the index's Persian rows: mean 1.46, and 56% with one step or none.

**The prompt was not the cause.** Condition A reproduces the bulk run's prompt
and sampling exactly and still returns 6.33 steps with not one empty result,
where the index holds close to zero for the same passages. The plausible theory
that the gap was a genre artifact -- Persian and Urdu here are Diwans, lyric
with little external action, and the old prompt permitted "empty list if no
action" -- does not survive this: the model assigns `mode: lyric` to 19 of 24
under that same prompt and still lists six actions.

The operative variable is the model. Qwen2.5-32B read Persian well enough for a
correct one-line gist, as the before/after samples show, but returned empty
`action_steps` on it. Qwen3-30B-A3B returns six on the identical prompt. The new
prompt then adds roughly three more steps on top (6.33 to 9.79), so both
contribute, with the model much the larger share.

Caveat on rigor: this compares the current model against *stored output* of
Qwen2.5-32B rather than re-serving Qwen2.5-32B alongside it. Prompt and sampling
are controlled; the vLLM version and the `names_present` constraint are not. A
fully controlled test would need the old model loaded on the same hardware.

#### Why the Persian and Urdu windows were re-described

The original describer produced shallow descriptions for these two languages.
Measured over the whole index:

| language | windows | mean `action_steps` | one step or none |
|---|---|---|---|
| Persian | 218,213 | 1.46 | 56% |
| Urdu | 2,148 | 0.78 | 76% |
| Coptic | 13,199 | 4.53 | 4% |
| Latin | 208,929 | 3.18 | 15% |

Not a window-size effect, which was the obvious explanation and the wrong one: a
386-character Persian window re-describes to six action steps. This hurt twice
over, because Persian windows also crowd the top of thematic queries (13 of the
top 20 for "warrior arming scene" were Persian Diwans), so bad descriptions
there both retrieved badly and displaced better-described works.

**It is shallowness, not illiteracy** -- but it is still the model's doing; see
the A/B above. An early reading of this was that the first describer could not
read the Perso-Arabic script at all. Comparing the two
descriptions of the same window shows otherwise: the old ones identify the
genre and subject correctly (a ghazal of love and separation, a panegyric to a
ruler) and are merely generic, with a one-line gist and no `action_steps` at
all. The model read the Persian; it did not work it through. That matters for
what to expect from the re-describe, which is depth on passages already roughly
placed, rather than the rescue of passages that were nonsense.

Example, `anvari.diwan:coarse:1080`:

- before, 0 action steps: "The speaker expresses the pain of separation and the
  beauty of their beloved, longing for reunion."
- after, 6 action steps: "The speaker laments the torment of love and
  separation, yearning for union with the beloved while enduring the pain of
  absence with quiet resolve." Steps name the sovereign, the beloved's hair
  "consuming souls", the turn to spiritual awakening.

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

### Why Vergil was missing: the page is 25 works and the corpus is seven languages

I first blamed description granularity, comparing two Aeneid windows against
Iliad 11.16, and that was WRONG. Measured across the whole index it is the other
way round:

| work | windows | mean action_steps | arming windows | mean steps |
|---|---|---|---|---|
| Vergil, *Aeneid* | 4,604 | **3.53** | 84 | **3.30** |
| Homer, *Iliad* | 7,291 | 3.19 | 245 | 3.07 |
| Statius, *Thebaid* | 4,527 | 3.43 | 66 | 3.17 |

The Aeneid is described in MORE detail than the Iliad, not less. Two windows are
not a corpus, and the aggregate says the opposite of the sample.

The actual cause is the cutoff. The page shows 25 works; the Aeneid is the 28th.
The 27 ahead of it are mostly genuine arming scenes in Persian, Greek, Neo-Latin
and English, so a Latinist was simply being outvoted by the breadth of the
corpus. Restricted to Latin the Aeneid is 8th; restricted to Greek, the Iliad is
1st. The fix is a language filter on the page, which the API already supported
and nothing exposed. No re-describing needed.

### Where descriptions ARE thin, and it is not Latin

The same measurement found the real granularity gap, in the languages added
last:

| language | windows | mean action_steps |
|---|---|---|
| Coptic | 13,199 | 4.53 |
| English | 42,163 | 3.39 |
| Hebrew | 5,372 | 3.32 |
| Latin | 208,929 | 3.18 |
| Greek | 113,531 | 3.06 |
| **Persian** | **218,213** | **1.46** |
| **Urdu** | **2,148** | **0.78** |

Persian windows are also half the size of Latin ones (506 characters against
954), which looked like an explanation: shorter passage, less to describe. It is
not. Re-describing a sample with the same prompt gives:

| sample | source size | current steps | re-described |
|---|---|---|---|
| Urdu, 12 windows | ~880 ch | 0.78 | **7.58** |
| Persian, 10 windows | 386 ch | 0.00 | **6.10** |

A 386-character window still yields six action steps, so these descriptions are
broken rather than brief: the original describer failed on the Perso-Arabic
script, not on short input. This is the one place in the index where spending
GPU time is clearly justified, and it is the opposite of a Latin problem.

It matters twice over, because Persian windows crowd the top of thematic
queries: 13 of the top 20 on "warrior arming scene" were Persian Diwans. Bad
descriptions there both retrieve badly and displace better-described works.
See `research/QUEUE.md` for the cost.
