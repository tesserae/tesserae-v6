# Draft probe set for NC to edit — 2026-08-27

**Updated 2026-08-27:** NC ruled 45, 54, 58, 61, 77, 78, 79 and 80 to be
PRESENT, so they were replaced. Every replacement was run against the live index
and its top hit inspected before adoption. Full record in
`TESTING_RECORD_2026-08.md`.

Suggestions only. Change the wording, change the labels, delete what is wrong,
add what is missing. **A mislabelled query is worse than a missing one**, so
where you are not certain, cut it.

The queries marked ⚠ are ones I am least sure about and would most like you to
check.

---

## PRESENT — subjects the corpus does contain

Phrased as a reader would type them, not in the text's own words.

### Epic and myth (Latin and Greek)
1. a warrior puts on his armour before going out to fight
2. a hero descends to the underworld and speaks with the dead
3. a goddess disguises herself as a mortal to give advice
4. a ship is wrecked in a storm and the survivors reach shore
5. a funeral pyre is built and the body burned with offerings
6. a single combat between two champions in front of both armies
7. a prophecy is delivered that the hearer misunderstands
8. a river god or nymph appears to a sleeping man
9. a catalogue of forces listing their leaders and homelands
10. a mother laments over the body of her son
11. a banquet where a guest is asked to tell his story
12. a chariot race with a near-collision at the turning post

### History and oratory (Latin and Greek)
13. a general encourages his troops on the eve of battle
14. a city is besieged and its walls undermined
15. an ambassador delivers terms and is rejected
16. a conspiracy is uncovered and the plotters denounced
17. a plague strikes a city and the dead go unburied
18. a triumphal procession displaying captives and spoils
19. an army crosses a river under enemy fire
20. a defendant appeals to his past service to the state

### Tragedy
21. a messenger reports a death that happened offstage
22. a chorus warns against pride and reversal of fortune
23. a woman plans revenge against the husband who wronged her
24. a father discovers he has killed his own child

### Hebrew Bible
25. a covenant is made and sealed with a sacrifice
26. a prophet denounces a king to his face
27. a people wander in the wilderness and complain of hunger
28. a young man is sold into slavery by his brothers
29. a city's walls fall and it is put to the sword
30. a psalmist cries out to God from despair

### Coptic and early Christian
31. a monk is tempted in the desert by demons ⚠
32. a martyr refuses to sacrifice and is condemned
33. an abbot gives counsel to a younger brother ⚠

### Persian (now well described — worth testing)
34. a king holds court and receives petitioners
35. a lover complains that the beloved is indifferent
36. a warrior draws his bow and boasts of his strength

### Deliberately hard — narrow subjects
37. a snake or serpent attacks and kills a man ⚠
38. someone is turned into an animal or a tree
39. a shield or cup is described in detail as a work of art
40. a doctor treats a wound on the battlefield ⚠

---

## ABSENT — near misses, the half that does the work

The model to beat is *"a farmer lifts potatoes out of the ground and sorts them
for seed"*: farming, digging and seed are everywhere in the Georgics, and only
the potato is impossible. It scores 1.83, above eight of the twelve present
subjects. **That is what stops Theme Search calling near misses "strong".**

Aim for the same shape: right register, right activity, one impossible element.

### Post-classical technology in a classical scene
41. a scribe corrects a proof sheet fresh from the printing press
42. a surgeon gives the patient ether before cutting
43. a captain fixes his position with a sextant and a chronometer
44. a gunner swabs the barrel and rams home the powder
45. a farmer plants maize and banks the soil around the young stalks  *(tested: moderate, nearest is Vergil on tending seed)*
46. a rider fires a pistol from horseback at full gallop
47. a clerk copies a letter with carbon paper
48. a distiller heats the still and condenses the spirit

### The right act, the wrong culture
49. a tea ceremony conducted with careful attention to each gesture
50. a samurai prepares for ritual suicide before his lord
51. an Inuit hunter waits beside a seal's breathing hole
52. a Mesoamerican priest consults the calendar for an auspicious day
53. a Norse warrior boasts of his deeds in the mead hall
54. a scribe sets movable type and pulls a proof from the press  *(tested: low)*
55. a knight jousts in a tournament for a lady's favour
56. a shaman drums to enter a trance and travel to the spirit world

### Modern institutions in classical dress
57. a factory inspector reports on conditions in the mills
58. a barrister in wig and gown cross-examines a witness  *(tested: moderate, nearest is Demosthenes on a witness)*
59. a newspaper editor decides which story leads
60. a bank forecloses on a mortgage and seizes the property ⚠
61. a clerk stamps a traveller's passport at the border post  *(tested: low)*
62. a patient signs a consent form before an operation

### Modern science and medicine
63. antibiotics are prescribed for a bacterial infection
64. a naturalist classifies a specimen by genus and species ⚠
65. a chemist weighs a reagent and records the reaction
66. an astronomer photographs a comet through a telescope
67. a geologist reads the age of the rock from its strata

### Wholly outside the world
68. a spacecraft docks with an orbital station
69. a programmer traces a fault in a web server
70. a pilot lowers the landing gear on approach
71. a telegraph operator taps out a message in code
72. a radio broadcast interrupts with news of the war

### Subtle — the ones I would most like you to judge
73. a whaling crew harpoons a whale from an open boat ⚠
74. a coffee house where men argue politics over their cups
75. a duel fought with pistols at twenty paces
76. a violinist tunes before a concert in a hall ⚠
77. a machinist turns a steel shaft on a lathe to a thousandth of an inch  *(tested: moderate, nearest is Milton at a forge)*
78. a photographer develops a glass plate in a darkroom  *(tested: low)*
79. a chemist fixes nitrogen from the air to make fertiliser  *(tested: moderate, nearest is Vergil on soil fertility)*
80. a notary registers a company and issues shares to its founders  *(tested: low)*

---

## Notes on the ⚠ items

**RESOLVED.** NC ruled 45, 54, 58, 61, 77, 78, 79 and 80 to be possible when
they were supposed to be impossible. All eight are replaced above, and every
replacement was run against the live index and its top hit read before adoption,
to be sure only an ANALOGUE was matching and not the subject itself.

Something worth knowing came out of that testing, because it narrows what
"absent" can mean here. **The corpus is later than it looks.** English runs to
Browning, Carroll, Poe and the Romantics, and Latin includes Polignac (1741)
describing chemical and physical experiments. So modern science is not
automatically absent, and neither is nineteenth-century English life. Anything
after about 1850, or from outside Europe and the Mediterranean, is safer.

**Still open, and I would rather you ruled than I guessed:**

- **31, 33** Coptic monastic subjects. The corpus holds the Apophthegmata
  Patrum, so a monk tempted in the desert and an abbot counselling a younger
  brother are probably PRESENT, which is what I have labelled them. Confirm.
- **37, 40** may be too narrow to test anything reliably either way.
- **60** a bank foreclosing on a mortgage. Roman law has debt and seizure of
  property, so this may be closer to present than I assumed.
- **64** a naturalist classifying by genus and species. Linnaean taxonomy is
  modern, but Pliny and Aristotle classify animals at length, so this may be an
  unfair near-miss rather than a clean absence.
- **73, 76** whaling from an open boat, and a violinist tuning before a concert.
  Both feel absent to me; neither is tested.

Any of these can be settled the way the eight were, by running them and reading
what comes back. Say the word and I will test them rather than argue about them.

## What happens next

Send back whatever you keep, in any format. I will convert it to the JSON the
fitting script wants, run the fit, and report the new thresholds and accuracy
against today's 88% on 32 queries — noting that the two numbers are only
comparable if we also re-run the old set.
