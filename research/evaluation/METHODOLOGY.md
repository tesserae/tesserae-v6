# Evaluation: what a number here means

How claims about Tesserae are measured, and the mistakes that shaped the
practice. Most of what is written here was learned by getting it wrong.

---

## The kinds of number we quote

| Kind | Question it answers | Where used |
|---|---|---|
| **Recall@k** | of the known parallels, how many are found in the top k | fusion benchmarks, Coptic |
| **Precision@k** | of the top k returned, how many are real | Coptic tables, spot checks |
| **MRR** | how high the first right answer sits, averaged | describe-then-retrieve |
| **Confidence accuracy** | does the band agree with a known answer | Theme Search probe sets |

**Precision@10 on one comparison and recall over a gold set are different
claims.** Reporting one where a reader will read the other is the single most
common way these numbers mislead, and it is what the Coptic article draft did.

---

## Gold sets

A gold set is a list of pairs a human believes are real parallels. Ours:

- **Latin fusion**: five benchmarks, 862 pairs, from published scholarship
  (Lucan-Vergil 213, Achilleid-Thebaid 52, and others).
- **Greek**: Hunter 1989 Apollonius-Homer, type 4+5, 121 pairs.
- **Cross-lingual**: Knauer Aeneid-Iliad, 412 target lines.
- **Coptic**: TSK cross-references filtered by vote, 124 pairs at the standard
  threshold, plus a 29-pair verse-strong subset.

**Disclose overlap between a gold set and any tuning.** The Coptic 29-pair
benchmark shares 15 pairs with the set used for weight optimisation, which was
not stated in the draft and would have been found by a reviewer.

**Know whose judgement a gold set encodes.** The TSK "votes" are user votes
published at OpenBible.info, not independent commentator judgements. A vote
threshold is a convenience filter, not a measure of scholarly consensus.

---

## Probe sets, for confidence calibration

A probe set is a list of queries whose answer is known: subjects the corpus
certainly holds and subjects it certainly does not. It exists to place a decision
boundary, not to measure recall.

`evaluation/probe_sets/tesserae_2026-08.json` (32 sentence queries) and
`short_query_stats.json` (28 queries of one to ten words).

### The absent half is the hard half, and there are three kinds

1. **Wrong civilisation or century.** A tea ceremony, a darkroom, a samurai.
   Easy, and a set made only of these gives a falsely confident threshold.
2. **Near misses** — NC's suggestion, and the ones that did the work. Classical
   in register with one impossible thing, where the impossible thing is the
   *action*: "a farmer lifts potatoes out of the ground and sorts them for seed".
   That scored higher than eight of the twelve real subjects, because everything
   in it except the potato is deeply present. Without them the strong boundary
   would have sat at 1.28 instead of 1.76.
3. **Wildly absent** — "airplanes and locomotives". Added late, after a query of
   this kind was reported STRONG. These produce *uniform noise*, which behaves
   completely differently from a near miss and which no near miss had exposed.

A set missing any of the three will pass a broken measure.

### What a good absent probe is not

"A spacecraft docks" is useless if it is the only kind you have: any threshold
separates it. But it is not useless as a category, as (3) shows. The rule is
coverage of all three kinds, not preference for one.

---

## The recurring failure, stated once

**Verification through a path the user does not take.** Nearly every wrong number
or dead feature found on 2026-08-25 had this shape:

- The Coptic quotation tests fed fusion a score the scorer never produced, so
  they passed for eleven weeks while the channel was dead.
- Tessa's conversation memory was tested through `answer()` and shipped through
  `answer_stream()`.
- A frontend change passed its build and produced a blank site: an undefined
  component is a runtime error, not a build error.
- Confidence thresholds were fitted on sentences and used on keywords, where
  they rated "airplanes" above "plague".
- The name check was measured with a rule that could not see the failure it was
  meant to catch.

**A test that supplies the value under test cannot discover that the value is
never computed.**

Practice: test through the door the user goes through. For a web feature, load
the page or hit the HTTP endpoint. For a model output, check the whole response
the reader sees. For a scoring change, run the benchmark on both sides of it.

---

## Reporting

- Quote the date a number was measured. Corpora grow; 92.6% Latin recall is a
  2026 figure over 1,429 texts.
- Quote the corpus version with a count where the count is the point.
- Say which set a number comes from, and whether it was tuned on.
- When two numbers disagree, publish both and explain the difference rather than
  choosing.
- **A threshold without the queries that produced it cannot be checked by
  anyone, including you.** Probe sets are committed beside the constants.

---

## Reproducibility for others

The confidence thresholds are the only calibrated constants in the system and do
**not** transfer between corpora. `evaluation/scripts/calibrate_confidence.py`
refits them from a probe set; `evaluation/scripts/validate_confidence.py` checks
a change against both sets. The context channel measures its own baseline per
text pair and needs no calibration at all, which is why it survived corpus
growth that broke the Theme Search bands.

---

## Running things safely

Benchmarks share a machine with the live site. `evaluation/scripts/run_bounded.sh`
runs a job under systemd with `MemoryMax`, `RuntimeMax` and `CPUQuota`, written
after a reference test grew to 48 GB on a 62 GB box that also serves production.
The lesson was not "watch it more carefully"; it was that a long job here must be
bounded by the system rather than by attention.
