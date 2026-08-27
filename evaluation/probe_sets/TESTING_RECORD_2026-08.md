# Probe set: testing record, August 2026

`calibrate_confidence.py` ends by saying: *"Record the probe set alongside the
constants. A threshold without the queries that produced it cannot be checked by
anyone, including you."* This is that record, kept at NC's instruction.

It covers where the thresholds came from, every refit, and how each query in the
set was chosen and checked.

---

## 1. Why the set is being enlarged

The set stood at 32 queries (12 present, 20 absent). On 32 points one query is
worth 3%, so the reported accuracy carries a margin of roughly ±12 points: 88%
could as easily be 76% or 96%. The fitted boundary is placed between two
adjacent observations, which at this size is a high-variance estimate.

The `strong` threshold is pinned to the single highest-scoring ABSENT subject,
so with only 20 absent queries it rests on one noisy number. Today it sits at
1.83, held there by two outliers ("potatoes", "antibiotics"). More absent
queries should stabilise that estimate and probably lower it, which would mean
more genuinely good result sets correctly labelled strong.

Target: about 40 present and 40 absent.

---

## 2. Threshold history

| fitted | index | probe set | MODERATE | STRONG | accuracy |
|---|---|---|---|---|---|
| 2026-08-24 | 143,947 windows | 22 queries | 1.30 | 1.65 | 91% |
| 2026-08-25 | 603,594 windows | 28 queries | 1.40 | 1.7613 | 93% |
| 2026-08-27 | 603,594, Persian/Urdu re-described | 32 queries | **1.27** | **1.83** | **88%** |

**The 93% and the 88% are not comparable.** They were measured on different
sets: four absent queries were added between them, and absent queries are the
hard half. Measured like for like, the OLD index against TODAY's 32 queries
scores 91%, so the re-describe cost one query out of 32, inside the noise.

Why accuracy moved at all: the re-described Persian windows carry far more
content (1.46 action steps to 8.99), so an absent subject has more to
half-match against and the classes overlap more.

---

## 3. How queries are written

**Present** — a subject the corpus really contains, phrased as a reader would
type it, NOT in the text's own words. "a general addresses his troops before
battle", not "arma virumque cano". The second is a phrase search.

**Absent** — the half that does the work, and the half people get wrong. A
useless absent query is obviously impossible ("airplanes and locomotives",
scores 0.58, everything gets it right, teaches nothing). A useful one is
classical in every respect except one impossible element. The model is:

> *a farmer lifts potatoes out of the ground and sorts them for seed* — 1.83

Farming, digging and sorting seed are everywhere in the Georgics. Only the
potato is post-Columbian. It outscores eight of the twelve present subjects, and
it is the single query that stops Theme Search calling near misses "strong".

---

## 4. The trap, and what it cost

A first draft of 40 absent queries was written on the assumption that trades and
institutions sounding unmodern to a present-day ear would be absent. **Eight
were wrong**, and NC ruled them out:

| # | query | why it is actually PRESENT |
|---|---|---|
| 45 | a miller's watermill fitted with iron gearing | watermills are ancient |
| 54 | a monk illuminates a manuscript with gold leaf | late antique, in range |
| 58 | a jury is selected and challenged by the defence | Athenian juries; Demosthenes |
| 61 | a census taker records households street by street | the Roman census |
| 77 | a potter throws a pot on a wheel | ancient |
| 78 | a glassblower shapes a vessel at the furnace | Roman glass |
| 79 | a bee-keeper smokes the hive to take the honey | Georgics book 4 |
| 80 | a slave is manumitted before a magistrate | Roman law |

A mislabelled absent query does not merely waste a slot. It drags the `strong`
threshold upward, because that threshold is set above the highest absent score,
so a present subject mislabelled absent makes the tool more timid than it should
be. **This is the most damaging single mistake available when writing a probe
set.**

---

## 5. What bounds "absent" here, and it is later than you think

The corpus is not purely ancient. Checked 2026-08-27:

- **English** runs to Browning, Carroll, Poe, Shelley, Keats, Coleridge and
  Wordsworth: the nineteenth century.
- **Latin** includes Polignac (1741), whose Anti-Lucretius describes chemical
  and physical experiments.

So "modern science" is not automatically absent, and neither is nineteenth
century English life. Anything after roughly 1850, or from outside Europe and
the Mediterranean, is safer ground.

---

## 6. Replacements, chosen by measurement rather than assumption

Each candidate was run against the live index before adoption, and its top hit
inspected to confirm the subject itself is absent and only an ANALOGUE is being
matched. Run 2026-08-27 against the re-described index.

| replaces | new query | confidence | nearest thing in the corpus |
|---|---|---|---|
| 45 | a farmer plants maize and banks the soil around the young stalks | moderate | Vergil, planting and tending seed |
| 54 | a scribe sets movable type and pulls a proof from the press | low | Ferdowsi, a royal court announcement |
| 58 | a barrister in wig and gown cross-examines a witness | moderate | Demosthenes, arguing a witness's testimony |
| 61 | a clerk stamps a traveller's passport at the border post | low | Cicero, political matters |
| 77 | a machinist turns a steel shaft on a lathe to a thousandth of an inch | moderate | Milton, a worker at a forge |
| 78 | a photographer develops a glass plate in a darkroom | low | Keats, someone quietly entering a room |
| 79 | a chemist fixes nitrogen from the air to make fertiliser | moderate | Vergil, improving the fertility of ground |
| 80 | a notary registers a company and issues shares to its founders | low | Aristotle, jurors entering court |

Four score **moderate** and four **low**, which is the mix wanted: the moderate
ones are true near misses that discipline the threshold, the low ones are the
easy end of the range. Every one is genuinely absent, confirmed by reading the
top hit rather than trusting the score.

Tested and rejected as too easy or redundant, kept here so nobody re-derives
them: a signalman switching railway points (low), a cyclist changing gear
(moderate, but the top hit was Polignac on a mountain climb, so the near-miss is
accidental rather than designed), a dentist fitting an amalgam filling
(moderate, Celsus on extractions, a good candidate held in reserve), a nurse
taking a blood pressure reading (moderate, Galen on diagnosis, likewise).

---

## 7. Method, for whoever refits this next

1. Write candidates. Absent ones should share the register of something the
   corpus does contain.
2. **Run each candidate against the live index before adopting it.** Read the
   top hit. If the subject itself comes back, the query is present and must be
   relabelled or cut.
3. Prefer absent queries that score moderate. A set of easy absent queries
   produces a threshold that is too low and a tool that overclaims.
4. Refit with `calibrate_confidence.py`, update MODERATE_COMBINED and
   STRONG_COMBINED together in `backend/passage_index.py`.
5. **Re-run the previous set as well**, or the two accuracy figures are not
   comparable. That mistake was made on 2026-08-25 and corrected on 08-27.
6. The fit must be redone after any re-describe or re-embed, because every score
   is relative to the median of the whole index. The drift guard watches the
   window COUNT and will not notice.
