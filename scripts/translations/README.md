# Aligned English translations

How the English in the Reader's Translation tab is built. Six pipelines feed
the same place, `data/translations/`, which `backend/translations.py` reads.

As of 2026-08-27 they produce **352,053 aligned references across 585 works**:
255,357 from Perseus, 35,941 from the Greek Bible, 2,299 five-line blocks
covering Seneca's ten tragedies, 10,991 lines of Statius, 12,223 of Aristophanes
and 35,242 verses of the Vulgate. The served directory holds 770 works in all,
the rest being the Coptic and Hebrew scripture pairings built separately.

---

## Why this is delicate

A missing translation is visible: the reader sees a blank and knows where they
are. **Wrong English beside right Latin is invisible.** A reader without Latin
has no way to detect it and every reason to trust it, and that reader is much of
the point of the feature.

So neither pipeline trusts a match it has not measured. Both check the pairing
two ways and refuse to write a file that cannot be defended:

- **proper names** — do the names in the source line appear in the English
  assigned to it?
- **length correlation** — do longer source lines get longer English? This needs
  no proper nouns, which matters because names run out in exactly the books that
  most need checking. Proverbs scores 0.03 on names and Wisdom 0.00, and both
  pairings are correct.

Neither test alone is enough. Names starve on short or nameless texts; length is
meaningless where one unit of translation covers many source lines. Each pipeline
uses whichever can speak, and writes into the output file which one vouched for
it (`verified_by`).

---

## Pipeline 1: Perseus

English translations that Perseus distributes as TEI beside the originals,
CC BY-SA 4.0 markup over public-domain translations.

    1. tei_extract.py            TEI -> extracted6.json
    2. verify_work_identity.py   which Perseus work IS ours -> verified.json
    3. match_works_by_title.py   fallback identity by author+title -> work_map.json
    4. align_perseus.py          the alignment search -> aligned .json per work
    5. compact_for_serving.py    reshape for the app  <-- NOT OPTIONAL

`tei_extract.py` builds on `tei_extract_base.py`; it exists because nineteen
Perseus translations are still in the older TEI P4 form, where every P5 lookup
missed silently and the files were reported as having no text. Tacitus in Church
and Brodribb and all fourteen works of Claudian were among them.

**Step 2 is the one to understand.** Identity is a question about the text, so it
is answered by comparing the text: `verify_work_identity.py` measures how far our
own Latin or Greek vocabulary overlaps each Perseus work's. Title matching (step
3) is kept only as a fallback, because it is deaf to a work Perseus words
differently and on that account had dropped Lucan, Thucydides, Phaedrus,
Ammianus, Apuleius' *Metamorphoses*, Tacitus' *Germania*, Sallust's *Jugurtha*,
Boethius, Claudian and Ovid's *Heroides*.

There is a `matches.json` in the working directory that looks like a shortcut for
step 2. **It is not.** It is a scored candidate list, and it pairs Boethius with
Suetonius, Claudianus Mamertus with Horace and Aethelwulf with Catullus.

**Step 5 is not optional and fails quietly if skipped.** `backend/translations.py`
reads `units` and `ref_to_unit`. An alignment installed in the raw form loads
without error and answers every request with "this work has a translation, but
not for the selected lines."

### What align_perseus.py decides

Its header carries the full reasoning. In short:

- **Granularity is traded against coverage.** Coverage alone always picks the
  coarsest unit, since a translation divided only by book covers every line in
  the book. What a reader feels is how many source lines they must search inside
  one unit, so the finest alignment reaching 85% of the best coverage wins.
  Lucretius went from 1,250 source lines per unit to 42, the *Metamorphoses* from
  809 to 90, Livy from 604 to 1.
- **The public-domain cutoff is 1931**, because 1930 publications entered the US
  public domain on 1 January 2026.
- **Abstention is not approval.** The name check refuses to speak on fewer than
  twenty sampled names, and reading that silence as a pass is how Ovid's
  *Medicamina* shipped labelled high confidence with English about pendants and
  lockets beside Latin about mixing powdered meal.

## Pipeline 2: the Greek Bible

    align_greek_bible.py

Septuagint from Brenton 1851, Greek New Testament from the World English Bible,
both public domain, both already used in production for Coptic. Sources are USFM
from ebible.org, kept at `$TESSERAE_BIBLE_SRC` (default
`~/perseus_trans/bible_src`) — **not in a temp directory**, which cost a rebuild
once. This one writes the served shape directly, so it needs no compaction step.

No alignment search is needed: our refs already end in chapter.verse. That makes
the whole job a book-name map, which is exactly what makes it dangerous, so the
map is measured:

- **Rival test.** Each book is scored against every other English book, not only
  its proposed one. A correct map beats the field — Judges 0.835 against a best
  rival of 0.092 — and a book that does not win clearly is not written.
- **Two kinds of numbering offset, both systematic.** Chapter offsets, because
  the Septuagint Psalms run one behind the Masoretic. Verse offsets, because
  Brenton numbers the superscription of the Epistle of Jeremiah as verse 1 and
  our Greek does not, putting all 72 of its verses off by one. Searching only
  chapters found the first and **silently mis-paired the second at full
  coverage**, which is the worst way to fail.

Four books are deliberately not written: the Odes and the Psalms of Solomon are
not in Brenton; the Old Greek Bel and the Dragon cannot be distinguished from
Theodotion's, which is what Brenton prints; and Lamentations is held back because
**our Greek text is defective** — 88 of its 150 reference lines hold nothing but
the acrostic letter name, a bare `Ἄλεφ.`, with the verse body missing. The
English is correct and can go in as soon as the source text is fixed.

## Pipeline 3: Seneca's tragedies

    align_seneca_tragedies.py

The largest canonical Latin gap with no English at all: 12,033 lines across ten
plays, none of them translated in Perseus, and the corner of the corpus that
Flavian and Elizabethan intertextual work runs straight through. Source is Frank
Justus Miller's translation, Project Gutenberg 57999 (Chicago, 1907), public
domain by publication and clear in the EU too since Miller died in 1938.

**The alignment is exact rather than approximate**, because the two sides were
built for each other without either knowing it. Our .tess files do not number
Seneca line by line; they number in FIVE-LINE BLOCKS, `<sen. oed. 200-4>`. Miller
prints the Latin line number in the margin every five lines. His marker 200 opens
exactly the English that renders our block 200-4.

That his markers are Latin line numbers and not a count of English verses is
checked, not assumed: for every one of the ten plays the highest marker is
exactly four less than our highest block start (1060 against 1064 in *Oedipus*,
1995 against 1999 in *Hercules Oetaeus*). A count of English verses would run
half again as long.

Coverage is 98-99.5% on every play, with proper-name agreement 0.48 to 0.74.
Length correlation is weak here and correctly ignored: every block is five lines,
so block lengths barely vary and the correlation has nothing to measure. That is
the mirror image of the wisdom books in pipeline 2, where names were the useless
test and length was the good one.

## Pipeline 4: Statius

    align_statius.py

*Thebaid*, *Silvae* and *Achilleid*: 14,783 lines, no English in Perseus and none
on Project Gutenberg, and the poet at the centre of the Flavian intertextual work
this project supports. Source is Mozley's Loeb of 1928 from the Internet Archive,
US public domain by date of publication.

**The alignment data is the running page header, not the marginal line numbers.**
This was planned as an OCR-and-margin-number job, which is slow and unreliable
because marginal digits stand alone in white space and are the first thing OCR
loses. It is also unnecessary: the Loeb prints "THEBAID, I. 18-41" at the head of
every page, in ordinary type, which is what OCR reads best. Every page of English
can be attached to a known range of Latin lines without reading one marginal
number. The *Silvae* headers give book, poem and line, matching our references
exactly.

**The repair rule is the part to understand, because the obvious version of it is
wrong.** Digits are what OCR misses, and a page header is mostly digits: "66-93"
comes back as "6-93". The first version of this trusted contiguity — each page
starts where the last ended — and that quietly stretched one page of English
across sixty lines belonging to a page whose header the scan had lost.

A page is now judged first on its own plausibility. A Loeb page holds twenty-odd
lines, so a header claiming a sane span is believed **as printed**, even where it
does not follow the previous page, because the usual reason for a jump is a lost
header and the lines in the gap should stay unpaired. Only an impossible span
means a digit was misread, and then contiguity supplies it — "6-93" after a page
ending at 65 becomes 66-93, twenty-eight lines, a real page, with two independent
reasons to believe it. Anything that cannot be made plausible is dropped.

That change cut *Thebaid* coverage from 97% to 80% and raised proper-name
agreement from 0.727 to **0.814**, which is the point: the pages it removed were
the wrong ones.

Coverage is 80% of the *Thebaid*, 89% of the *Achilleid* and 57% of the *Silvae*,
the shortfall being page headers the scan lost entirely. One page is dropped for
carrying Mozley's own prefatory note in place of the verse.

## Pipeline 5: Aristophanes

    align_aristophanes.py

Aeschylus, Sophocles and Euripides all arrived with the Perseus rebuild. Of the
eleven surviving comedies of Aristophanes, Perseus carries an English text of
two, so a reader browsing Attic comedy met a wall of blank tabs where tragedy
read through. Source is Rogers' Loeb of 1924, three volumes on the Internet
Archive, US public domain by date of publication, using the same running-header
trick as Statius.

**Two things here that the Statius script did not need**, both of them cases
where the first guess was wrong and measuring fixed it.

*The play name has to be matched by similarity.* This scan is dirtier than the
Statius one: "THE PEACE" comes through as "THE PEACH", "LYSISTRATA" as
"LCYSISTRATA", and "THESMOPHORIAZUSAE" in six spellings across its forty pages.
Matching the literal string would have dropped a third of the corpus silently. A
hand-written list of observed misspellings fails on the first one nobody saw, so
the title is matched against the eleven possible answers by similarity, at a
threshold that accepts PEACH and rejects every other capitalised word in the
scan.

*The Greek-page guard was set far too tight.* The reasoning was that an English
page contains no Greek. It does: volumes II and III bleed Greek from the facing
page and from Rogers' footnotes, so real English pages sit at 0.23 to 0.33 Greek
characters. A 0.25 threshold threw away 297 of them, every page of seven plays,
and left those plays at 13-24% coverage looking like a source problem. Nothing in
the scan exceeds 0.4, because the Greek pages carry Greek headers and never match
the pattern at all. The guard is kept at 0.6 for a volume where it would matter.

Coverage 83-96% across all eleven, proper-name agreement 0.39 to 0.78.

**Clouds is built but deliberately not installed.** It already has Hickie's 1853
translation at full coverage and 3.1 source lines per unit, against Rogers at
21.6. A coarser alignment should never displace a finer one that already works.

## Pipeline 6½: the SBLGNT remap

    remap_sblgnt.py

The SBL Greek New Testament shipped 2026-08-21 as `novum_testamentum.*` beside
the legacy `new_testament.*` files, and arrived with no English: pipeline 2's
27 WEB alignments are keyed to the legacy refs. Both schemes end in
chapter.verse, so this is a remap, not an alignment search — every SBLGNT ref
takes the unit the legacy file already holds for the same chapter and verse.

The whole risk is versification, and there are exactly four differences, each
verified against the Greek before being encoded (Matt 23:13, Rev 12:18,
3 John 1:15, Rom 16:24 — the script header has the details). With those
handled, coverage is 1.0000 on all 27 books, and the script refuses to write
any book below 0.95.

## Pipeline 6: the Vulgate

    align_vulgate.py

The largest single untranslated work in the corpus: 39,244 lines, none of which
had English beside it. It was left off the earlier priority list only because
demand was judged lower than for Seneca or Statius. By coverage per hour of work
it was far and away the best thing available.

**Douay-Rheims, and the choice is not incidental.** It is a translation *of the
Vulgate*. Every other public-domain English Bible translates the Hebrew and
Greek, and the difference is not academic: the Vulgate's Psalter follows the
Septuagint's numbering, so an English Bible made from the Hebrew is a psalm out
of step, and pairing verse *n* with verse *n* would be wrong for the whole book
while looking complete. Choosing the translation made from the same text removes
the problem at the source instead of correcting for it afterwards.

That it worked is visible in the numbers. **73 books, 35,242 verses, 100%
coverage on nearly every book with no offset applied anywhere**, and length
correlation between 0.88 and 0.98 — far above any other pipeline here, which is
what a translation of this very text should look like. Vulgate Psalm 22 ("The
Lord ruleth me: and I shall want nothing") is the Hebrew Bible's Psalm 23, and it
pairs at 22 without correction.

**Six books are deliberately unpaired**, being in the Vulgate and in no ordinary
English Bible: 3 and 4 Esdras, the Prayer of Manasseh, Psalm 151, the Old Latin
Psalter and the Epistle to the Laodiceans. They are reported as having no English
rather than forced onto the nearest-looking book, which is how the Prayer of
Manasseh would end up answering for Manasseh in Chronicles.

---

## Paths

Defaults are the machine this was run on, kept so the record is honest, and
overridable so nobody edits a checked-in file to run it elsewhere:

| variable | default |
|---|---|
| `TESSERAE_PERSEUS_WORK` | `~/perseus_trans/work` |
| `TESSERAE_TEXTS` | `/var/www/tesseraev6_flask/texts` |
| `TESSERAE_TRANS_OUT` | `~/perseus_trans/translations_v3` |
| `TESSERAE_BIBLE_SRC` | `~/perseus_trans/bible_src` |
| `TESSERAE_BIBLE_OUT` | `~/perseus_trans/translations_bible` |
| `TESSERAE_SENECA_SRC` | `~/perseus_trans/seneca_src/pg57999.txt` |
| `TESSERAE_SENECA_OUT` | `~/perseus_trans/translations_seneca` |
| `TESSERAE_STATIUS_SRC` | `~/perseus_trans/statius_src` |
| `TESSERAE_STATIUS_OUT` | `~/perseus_trans/translations_statius` |
| `TESSERAE_ARISTOPHANES_SRC` | `~/perseus_trans/aristophanes_src` |
| `TESSERAE_ARISTOPHANES_OUT` | `~/perseus_trans/translations_aristophanes` |
| `TESSERAE_DRA_SRC` | `~/perseus_trans/bible_src/dra` |
| `TESSERAE_VULGATE_OUT` | `~/perseus_trans/translations_vulgate` |

`ONLY_WORKS=la/lucan.bellum_civile,...` restricts `align_perseus.py` to named
works, which is how to test a change without a full rebuild.

## Installing a build

`data/` is gitignored, so aligned files are a data artifact with no path through
GitHub, the same as the indexes. Back up the target directory first, copy the new
files in, and **remove any file for a work the new build rejected** — otherwise a
translation that was withdrawn for being wrong stays on disk and keeps serving.

Then verify through the endpoint rather than by looking at the files:

    curl 'https://tesserae.caset.buffalo.edu/api/translation?work=la/lucan.bellum_civile&refs=luc.%201.41'

Note the path is `/api/translation`, not `/api/passages/translation`: the route is
declared without the `/passages/` prefix its neighbours in that blueprint carry.
