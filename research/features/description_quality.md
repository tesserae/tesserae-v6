# Description quality

The passage index is built on 603,594 machine-written English descriptions.
Everything content search claims rests on them, so what is wrong with them, and
how wrong, is a first-class subject.

---

## 1. Names: the check is any-match, and now shows its working

### The case that exposed it

Valerius Flaccus, *Argonautica* 1.1-30 was summarised as "a lyrical invocation to
Apollo for guidance on Aeneas' journey", participants "Apollo, Cumaean Sibyl,
Aeneas".

- **Apollo** is there: `Phoebe, mone` (1.5)
- **the Cumaean Sibyl** is there: `Cumaeae ... vatis` (1.5)
- **Aeneas is not.** Line 1.9 has `Phrygios ... Iulos`, and the model reached
  from Iulus back to Aeneas.

The gist was worse than the participant list: the invocation asks Apollo for help
singing the voyage of the **Argo**, so it attached Valerius Flaccus's proem to
the wrong epic.

The record passed as `names_in_text: True`, because the check asks whether **any**
named person appears, and Apollo does.

### Why any-match stays

Requiring all names flagged 22.3% of descriptions, and reading a sample showed
most were sound: Hebrews 11:20 names nine figures of whom seven are in the text,
and was flagged exactly like a description that invented both of its two. A
description that gets some names right is reading the passage; one that gets none
right may not be looking at it.

**What changed:** the verdict no longer discards its working. Every checkable
participant is recorded verified or unverified, and unverified ones are named in
the Reader and on Theme Search.

### Four fixes were needed before the flag could be trusted

| Fault | Effect |
|---|---|
| No epithets | Apollo reported unverified because the text says *Phoebe* |
| Names split per capitalised word | "Cumaean Sibyl" became two people, half missing |
| `fold()` strips spaces | the passage was one continuous string; word matching could never fire |
| English vs Latin name forms | Peter/*Petrus*, Luke/*Lucas*, Moses/*Moyses*, Solomon/*Salomon* |

Fixed with an epithet table (Pallas, Alcides, Aeacides, Anchisiades, Lyaeus), a
`k`->`c` fold beside the existing `j`->`i` and `v`->`u`, a similarity test, and a
table of biblical forms. Then group nouns — Gauls (451), Roman soldiers (432),
Achaeans (253) — which are bodies of people and cannot be looked up as names.

```
unverified rate: 12.9%  ->  9.8%  ->  6.9%
```

### Why tuning stopped at 6.9%

The remainder is real names in three situations, and each would cost more to
chase than it is worth:

- **genuine over-reach**: Cicero, absent from the preface of *Gallic War* 8
- **epithets no table can hold**: Claudian's `audierat mandata Pater` IS Jupiter
- **oblique reference**: a window about Achilles that only says "he"

Adding `pater` -> Jupiter would falsely verify Jupiter across thousands of
passages, which is a worse error than the one it fixes.

**Unverified never means invented**, and both surfaces say so.

### What this means for the published figure

The **0.1% name error rate we quote is a floor measured against an any-match
rule, not a ceiling**, and should be described that way anywhere it appears. An
attempt to measure the all-match rate gave 34.2%, but that figure is contaminated
by English/Latin form mismatch and must not be used. A defensible number needs
name-form normalisation between English and the source language.

### Earlier work: the 6.1% correction pass

The name check originally flagged 9,166 of 151,484 checkable descriptions, about
6%. The failure had one shape: where a passage names nobody, the model supplied
the most famous people who fit. Aeneid 8.397-408 is Vulcan speaking to Venus in
their chamber, and the description said "Hector speaks to Andromache about the
war and then they embrace before he falls asleep" — the scene read correctly, the
couple invented.

Fixed by re-describing with the passage's actual proper names supplied as a
constraint, and where a passage names nobody, requiring participants to stay
unnamed. **6.1% -> 0.1%.**

Extracting those names needed care of its own: Latin and Greek verse capitalises
the first word of every line, so a capitalisation test alone returned *Atque*,
*Posce* and *Edidit* as names. Resolving through the lemma table and rejecting
anything in more than 5% of the corpus fixed it, because a treebank lemmatiser
does not know proper names, and failure to resolve is weak evidence *for* one.

---

## 2. Plain language

14.5% of gists (87,743) opened with a frame carrying no information: "a narrative
of", "a description of", "a vivid depiction of". A result set clusters passages
about one subject, described by one model, so the same words landed several times
on one screen.

```
- A vivid depiction of a fierce battle during a city siege, detailing ...
+ A fierce battle during a city siege, detailing ...

gists opening "A vivid": 6,256 -> 11
```

Originals kept in `gist_raw`, so the edit is reversible, and it is a
deterministic rewrite rather than a re-description, which would need the GPU and
would spend money on wording rather than fact.

**Deliberately kept:** "The passage argues" and "The speaker laments" are equally
formulaic and are 45% of the corpus, but they record which voice is speaking and
what it is doing, which the schema exists to capture. An adjective like "vivid"
is the summariser's opinion of the passage, not a fact about it, and not a
judgement it is entitled to make on a scholar's behalf.

---

## 3. Dates

37.5% of the index showed as undated, 218,213 Persian windows among them. Since
Theme Search orders chronologically, an undated author is not merely unlabelled,
it is dropped to the end of every result list.

```
undated: 226,270 (37.5%)  ->  97 (0.02%)
```

The 97 remaining are literally "anonymous" and "unknown", left undated rather
than guessed.

28 authors added, mostly the Persian tradition (Rudaki through Ferdowsi,
Khayyam, Nizami, Attar, Rumi, Saadi, Hafez, Jami, to Iqbal and Parvin), plus
Ghalib and Iqbal in Urdu, the Greek New Testament and Aratus, Poe, and three
Arabic authors.

**Provenance matters and is recorded.** The Latin and Greek dates came from a
curated authority file; these 28 were supplied editorially from standard
reference knowledge. Every one carries `"added": "editorial-2026-08-25"` and can
be found and replaced in one query.

**The era labels need a specialist.** The vocabulary already in the file is Latin
and Greek (Augustan, Hellenistic); Persian literary history is not periodised
that way, so dynastic labels were used (Samanid, Ghaznavid, Seljuk, Timurid,
Safavid, Mughal, Modern). Ordinary practice, but a judgement rather than a
lookup. "Mughal / Colonial" for Ghalib is the least settled.

The New Testament and the Qur'an are collections, not authors, and are dated by
composition with the note saying so.

---

## 4. Open

- A defensible all-match name error rate, which needs English-to-source name
  normalisation.
- Persian and Urdu era labels reviewed by someone who works on them.
- Titles are title-cased from filenames; `backend/utils.py:title_case` handles
  small words and Roman numerals, but the underlying names are still derived
  rather than curated.
