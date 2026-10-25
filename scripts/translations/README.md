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

## Pipeline 7: Quintus of Smyrna and Apollonius Rhodius

    align_theoi.py

The two big Greek epics outside Homer with no English at all: the
*Posthomerica* (8,800 lines) and the *Argonautica* (5,800). Way's Loeb of 1913
and Seaton's of 1912, both US public domain, from the Theoi Classical Texts
Library transcriptions -- clean HTML, no OCR, each paragraph opening with a
bracketed line number.

**What that number counts differs between the two authors**, and assuming
otherwise is the Seneca trap again. Seaton's markers are Greek line numbers
(book 4's last is 1773 against our 1781) and map directly. Way's are his OWN
English verse lines (book 1's last is 1103 against our 830 Greek), so they are
rescaled proportionally onto the Greek per book before use. The name check is
the judge of whether the rescale held: 0.44-0.46 for Quintus and 0.61 for
Apollonius, with length correlation 0.99 for both.

Both works exist twice in the corpus under different names (Quintus as
`fall_of_troy` and `posthomerica` with slightly different line counts,
Apollonius as `apollonius.argonautica` and `apollonius_rhodius.argonautica`,
byte-identical). One alignment is computed per author and written once per
work id. Coverage is 100% on all four.

## Pipeline 8: Ovid's Fasti, Tristia and Ex Ponto

    align_ovid.py

The rest of Ovid: the Perseus rebuild covered the *Metamorphoses*, *Amores*,
*Ars* and *Heroides*; these three (11,700 lines) had nothing. Two sources.

**Tristia and Ex Ponto: Wheeler's Loeb of 1924**, the Statius running-header
method with one addition. The OCR mauls the lower-case poem numerals in the
headers beyond reliable reading ("iii" arrives as m1, im and mr; "vii" and
"viii" both arrive as vu), so the walk trusts numbers and contiguity instead:
a single-range header continues the current poem, a cross header
("127--II. 24") finishes it and opens the next, both validated against our
own poem lengths, and the mangled numeral is consulted only to resync after a
failure. Coverage 77% and 90%, names 0.61 and 0.75.

**Fasti: Riley's Bohn prose of 1851**, because the only Loeb is Frazer 1931,
out of reach until 2027. The scan's headers alone are not enough (OCR loses
many), but Riley annotates so heavily that nearly every page carries footnotes
anchored "] -- Ver. 141.", and those verse numbers date the page directly. A
page whose footnotes run far past one page's span is a page whose successor
lost its header: its whole body, notes included, is kept as one honest coarse
unit rather than claiming verses whose prose was discarded. Coverage 87%,
names 0.69, length correlation 0.77.

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

## Pipeline 19: Demosthenes, the Republic, Isocrates and Plato by section (2026-10-25, Part G)

    g_common.py                    shared helpers (Perseus lookup, Stephanus page-break rule, license wording)
    g_renewal_checks.py            renewal searches per Loeb volume
    align_demosthenes_sections.py
    align_republic_shorey_stephanus.py
    align_isocrates_vanhook.py + merge_isocrates_norlin_vanhook.py
    align_plato_missing_english.py
    g_readings.py                  five passages per file for reading
    g_preview_check.py             preview through a Flask copy on port 8104

Built on staging copies in `~/tesserae-backups/tr_g_2026-10-25/` and not installed (docs/DATA_OPERATIONS.md has the
install order). Every file pairs our references with the Perseus TEI of the Loeb translation by the same
section numbers, so each reference takes the English of its own section, the finest unit the text has.

**Demosthenes** (`align_demosthenes_sections.py`). 60 files, one unit per section, 3,636 of 3,636 references, from
Vince (1930, 1935), Murray (1936, 1939) and N. W. and N. J. DeWitt (1949). They replace the 41 whole-speech files of
Kennedy that Part C held (one unit for a speech of 20 to 227 sections), the 16 whole-speech Vince files of 1930
now installed, and the Kennedy Exordia and Letters. On the Crown, On the Embassy and Against Leptines stay as
they are. Proper names 0.40 to 1.00, length correlation 0.845 to 0.959, and the rival-unit test 0.83 to 1.00 where
it can speak. The English sections follow the translator's own placement of the section numbers, so a clause of one
Greek section can sit at the head of the next unit.

**The Republic** (`align_republic_shorey_stephanus.py`). One file for the work, 1,354 of 1,355 references, one unit per
Stephanus section, two sources (Shorey vol. I 1930 for books 1 to 5, vol. II 1935 for books 6 to 10) each with its
own license and `unit_sources` for every unit. Proper names 0.82 on 342 (0.84 in books 1 to 5, 0.76 in books 6 to 10),
length correlation 0.70, rival test 0.98. Part F's page-spread method gave 438 of 645 references for books 6 to 10 at length
correlation 0.11 and is superseded.

**The page-break rule** (`stephanus_text` in `g_common.py`) is the part to understand. Perseus marks the Loeb's page
breaks in a Plato text with a bare number ('375') before or in place of the lettered sections. Matching only the
lettered keys exactly left 38 Republic references unpaired and dropped the tail of about one section in six, the
words that follow a page break inside a section. Read in document order, a bare number is the continuation of the
chunk before it when a section 'a' of that page exists in the record, and is the section 'a' itself when none does.
Coverage rose from 97.2 to 99.9 percent and names from 0.78 to 0.82. Plato files installed earlier from Perseus
may have the same loss.

**Isocrates** (`align_isocrates_vanhook.py`, `merge_isocrates_norlin_vanhook.py`). Speeches 9, 10, 11, 14 and 16 to 21
from Van Hook's vol. III (1945), 533 sections, names 0.84 on 312, length correlation 0.89, rival test 0.97. The
installed Norlin file keeps all 1,468 of its units and the merged file adds 533, so coverage goes from 73.4 to 100
percent. Each source carries its own license (the installed Norlin source had none, so the merge copies the file-level
license into it). The nine letters (Van Hook) are a separate standalone file, 114 of 114 references.

**Plato without English** (`align_plato_missing_english.py`). Alcibiades I (Lamb 1927, 162 of 162), Alcibiades II (Lamb,
67 of 67) and the Epistles (Bury 1929, 280 of 280), all published before 1931. The Lovers (Lamb 1927, 35 of 35) is
written only to `out/plato/review/`: it has 13 names to test (the check needs 20) and a length correlation of 0.52,
so neither check vouches for it, though the Stephanus numbers are exact and five passages read correctly. Jowett
was not needed because Perseus has a Loeb text of all four.

**Renewals.** The volumes of 1931 to 1963 (Vince 1935, Murray 1936 and 1939, DeWitt 1949, Van Hook 1945, Shorey 1935)
were searched in the NYPL cce-renewals data per translator and title (`g_renewal_checks.py`) and the title page of each
was read on an Internet Archive scan. Nothing was found, and each is treated as United States public domain under the
rule of 2026-10-24. The searches name Demosthenes, Isocrates and Plato by author, translator and series words.

## Pipeline 18: re-alignments of 2026-10-24

    align_anthologia_graeca.py + merge_anthologia_scans.py
    align_martial_ker.py
    align_pliny_bosanquet.py
    align_loeb_pages.py      (Petronius, Apocolocyntosis)
    align_josephus_vita.py

Six works whose installed English covered a fraction of a complete public-domain source.
Nothing here is a new translation. Each was re-aligned and measured against the same two
checks as the rest. The data files are built in a staging folder and installed by hand
(docs/DATA_OPERATIONS.md has the order).

**Greek Anthology, Paton's Loeb (books 7, 8, 14, 15, 16, and 10 to 13 with the same method).**
The earlier diagnosis (poor scans of volumes 4 and 5) was right but incomplete. Better
archive.org scans exist for every volume. `greekanthology02unse` and `greekanthology05unse`
cover 85 and 88 percent where the scans in use covered 51 and 61. Two layouts the script did not
read cost the rest. Book 8's epigrams 177 to 254 and Book 14's Metrodorus run (116 to 146) print
each epigram's number alone on a line under a range heading ("BOOK VIII. EPIGRAMS 177-181"), so the
aligner now accepts a bare number inside a declared range, and only for the next epigram or the one
after it, because a page number looks the same. The aligner runs once per scan, and
`merge_anthologia_scans.py` then takes each epigram from the highest-coverage scan that has it. A
filler from a lower scan is used only where it agrees with the best scan on the epigrams on both
sides of it (same opening text), because one scan numbered Book 14's riddles two off for a whole
stretch. The units are also cut where the next epigram's heading or the volume's index begins.
`repair_anthologia_small_caps.py` then repairs the first words that the Loeb's small capitals left garbled
("TuereE" for There, "Tue" for The, "ImaGInE"). The table of the 2026-09-10 install only saw the first word of a unit, and
about one unit in eight opens with a heading ("On the Same Tue ..."), so the table now applies to the first eight words (and the
words that are not English at all anywhere in a unit). A word with capitals in the middle is put back into ordinary case and its
OCR confusions (u for h, p for d) are undone where the result is a word the corpus itself uses. 537 words repaired across
the nine staged files, and the units with an odd-case word among their first twelve fell from 306 of 2,385 to 5. Garbles in
the letters of a proper name (Ampuilocuus for Amphilochus) keep their letters and only have their case repaired. Every change is in
the staged `small_caps_repair_log.tsv`.
Coverage 62, 58, 59, 63, 59 percent before and 97, 99, 95, 91, 99 after for books 7, 8, 14, 15 and 16,
names 0.78 to 0.91, length correlation 0.66 to 0.84, and the share of epigrams on which two scans
agree 90 to 95 percent.

**Martial (Bohn 1860, Ker's Loeb 1919 and 1920).** The installed file was built against a
6,399-line selection. The corpus text was replaced on 2026-09-18 by the complete 9,375 lines, so the file
covered 67 percent for a reason that had nothing to do with the translation. Bohn's epigram
anchors match the new numbers book by book, and aligned against the new text Bohn covers all but fifteen
epigrams (Bohn prints Graglia's Italian for them or nothing). Ker's Loeb is not complete either: it prints the Latin of
those epigrams and no English (4.48 is a plain case). Ker supplies 1.0, 1.58, 9.0, 11.45 and 11.58 (the two
prefatory poems are read out of the epistles), and ten epigrams (2.84, 4.48, 9.41, 10.55, 10.81, 10.90, 11.95, 12.95,
12.96, 12.97) have English in neither book and stay blank. `unit_sources` tells the Reader which translator wrote each unit.
Coverage 67 to 99 percent, names 0.83 on 800 pairs, length correlation 0.92 per epigram.

**Pliny the Younger, Letters (Melmoth revised by Bosanquet, the Bohn text, books 6 to 10).** Firth stays for
books 1 to 5. Books 6 to 9 are paired by the printed letter number (the OCR'd numerals read as a Latin
letter's number, in increasing order, with a length fit), plus pairs the order search adds between two numbered
neighbors. 125 of 130 letters pair. Where the Gutenberg selection (PG 2811, the same translation, typed) holds the
same letter, its clean text replaces the OCR. **Book 10 stays mostly without English.** Bosanquet reordered the Trajan letters against the numbering our
text uses (his "LETTER IV. [xx.]" is a different letter from our 10.4), so the printed number cannot vouch. Only 14 of 124 letters
carry a pairing that their own proper names support, and pairing the rest would put wrong English beside right Latin. A Melmoth-to-Mynors
concordance for Book 10 is the missing piece. Coverage 47 to 86 percent, length correlation 0.98.

**Petronius (Heseltine's Loeb, 1913) and the Apocolocyntosis (Rouse, same volume).** Our text holds only the verse
passages of each (29 in Petronius, chapters 2, 4, 7, 12 and 15 of the Apocolocyntosis). Heseltine prints Petronius's verse as running prose and neither
English page carries chapter numbers, so `align_loeb_pages.py` uses the layout of a Loeb. The Latin page and its English translation
face each other and the running heads differ (TITUS PETRONIUS ARBITER over the Latin, SATYRICON over the English). A passage is found on
its Latin page by its own words and takes the English page that follows. The unit is a whole page, about 15 source lines per
unit, and always holds the passage's translation. Eight Petronius passages are skipped because Heseltine leaves them in Latin
(23,3 and 132,8 are examples) or the page could not be read. Coverage Petronius 28 to 77 percent,
Apocolocyntosis 42 to 100 percent.

**Josephus, Life (Thackeray's Loeb, 1926).** Every English page of the Loeb carries a running head naming the small sections
that begin on it ("THE LIFE, 4-11"), the same 430 sections our references use. Each reference takes the page that begins its
section. Three scans are read because the OCR damages some heads, and a head is accepted only if it continues the chain of the heads
before it. Coverage 18 to 100 percent in 79 units of about 5 sections.

Environment variables this pipeline reads: `TESSERAE_TEXTS`, `TESSERAE_TRANS_OUT`, and for the Anthology
`PATON_VOL_FILES` (JSON, volume to scan file), `PATON_ONLY_VOLS` and `PATON_LOG_DIR`.
## Pipeline 17: the Coptic Septuagint books, Budge, and the Persian and Urdu attempts (2026-10-24)
    align_coptic_brenton.py     coptic_align_common.py
    align_budge_sections.py
    align_khayyam_whinfield.py  persian_poems.py  persian_semantic_common.py
Built on copies in `~/tesserae-backups/tr-d-staging/`, **not installed** (see
docs/DATA_OPERATIONS.md, entry PLANNED). Coptic has no capital letters and no printed
numbers beyond the verse, so the two checks of "Why this is delicate" are done differently here,
each against a displaced control (the same Coptic lines paired with English from seven places along).
*Names.* The capitalized names of the English unit are folded to a consonant skeleton and looked
for inside the consonant skeleton of the Coptic verse (Coptic writes Greek names in Greek spelling,
so Nabuchodonosor appears as ⲛⲁⲃⲟⲩⲭⲟⲇⲟⲛⲟⲥⲟⲣ). *Length.* The same correlation as pipeline 2.
**Coptic Old Testament against Brenton 1851** (`align_coptic_brenton.py`). The installed Bohairic
Daniel paired chapter n with the World English Bible's chapter n, which translates the Hebrew; the
Bohairic text divides Daniel 3 over three chapters and carries Susanna and Bel, so chapters 3 to 12
were paired with the wrong English (Coptic chapter 4 verse 1, the prayer of Azariah, sat beside
"Nebuchadnezzar the king, to all the peoples"; chapter 8 verse 1, Darius and the satraps, beside Belshazzar's
vision), and the file recorded its own checks as names 0.307 and length 0.266. Brenton translates the Septuagint, so it is the
right English. Verse numbers are not trusted: each chapter is paired by length with dynamic
programming (Gale and Church 1993; one-to-one, one-to-two, two-to-one and unmatched verses), and
the verse number is used as a prior only where both traditions number alike (Proverbs). Verses
that Brenton prints in parts (Proverbs 4:27a, 4:27b) are kept apart for the aligner; the shared loader
`align_greek_bible.load_usfm` keeps only the last part of such a verse and leaves the letter in the text.
Written: Bohairic Psalter (2,305 of 2,314 lines, names 0.315 against 0.095, length 0.609 against
0.016, two psalms left out whose own alignment costs too much), Sahidic Proverbs (794 of 890, length
0.562 against 0.056, chapters 24, 30 and 31 left out because the Septuagint prints them in a different
order), Epistle of Jeremiah (72 of 72), Bohairic Daniel (533 of 623, names 0.837 against 0.330, length
0.833 against 0.063: Daniel 1 to 12 as Theodotion, Susanna, Bel; chapters 15 and 19 hold the Old Greek
wording, which Brenton does not print), and the parts of two fragmentary books that can be tested: Sahidic
Habakkuk chapter 1 (13 of 30 lines) and Sahidic Daniel chapters 1, 6 and 9 (57 of 183). The rest of
those two, and the five-line Bel and two-line 1 Chronicles fragments, are too short or too
broken to pass either check and are not written. Where the Coptic fragment numbers its verses afresh
(Bel, 1 Chronicles 17) the number says nothing about the place, and length alone placed the fragment
wrongly when tested by eye.
**Budge, section level** (`align_budge_sections.py`, Mercurius, Theodosius on Michael, Bartholomew,
Repose of John). Our Coptic files number sentences or manuscript lines, with no folio marks, so the
English is cut into two-or-three-sentence segments and paired with runs of Coptic lines by dynamic
programming over length and over rare names. Half the rare names are withheld from the aligner and
used as the check. **No file is written**: the withheld names do no better than the control
(0.20 against 0.27 Mercurius, 0.29 against 0.33 Theodosius, 0.15 against 0.19 Bartholomew, 0.39 against
0.41 Repose of John), and a read of the pairs shows the English sitting one segment off in places. The
Coptic file called `mercurius` also holds two Budge texts in an order that is not his (XI then X), which
the script finds by trying the orders. The six texts the sweep left unsettled are not in Budge's
Coptic Martyrdoms (1914, ten texts) or Biblical Texts (1912, four books).
**Persian by meaning** (`align_khayyam_whinfield.py`, `persian_semantic_common.py`,
`persian_poems.py`). The Internet Archive scans of Whinfield's Khayyam and Clarke's Hafiz carry the
English only (the Persian is printed as images), so there is no first line to match. The quatrains
and the English are paired by meaning with the multilingual encoder that serves Theme Search, kept
only where each is the other's mutual best match, and judged on evidence the matcher never saw.
**Not written**: all 100 mutual best pairs are scattered (our file is not in Whinfield's order, rank
correlation 0.17) and every quatrain is the same length, so neither the order nor the length can
vouch for a pair, and the few names are too few. Several matches are visibly right ("From doubt to clear
assurance is a breath" against its Persian quatrain), which shows the method works and that without a
check that can speak the file would be right only for those the reader can already verify.
Clarke's Hafiz (Volume I only on the Archive) interleaves the translation with commentary and
"signifies" glosses couplet by couplet, so the translation cannot be separated by rule; Nizami and
Hafez are not attempted for that reason and the numbering of Wilson's Haft Paikar (every few lines
of prose) does not follow our couplets.
**Urdu: Hindustani Lyrics (1919)** is not attempted. It holds about 107 English poems in free
rhymed verse, each tied to a poet by name and none to a line of Urdu, and our Urdu files for the
eleven poets it draws on hold about 38,000 lines. Matching would need an encoder run over all of
them and has nothing to check against (no names, no numbers, no length that survives paraphrase).
---
## Pipelines 9 to 16: the exact-numbering batch of 2026-10-24
Fourteen works with no aligned English, from public-domain translations that share
our numbering, built by seven alignment scripts and one shared helper, `loeb_common.py`, ends every script the same way.
It runs the two checks of this document and writes the served file only if one of
them vouches. For works whose unit is one scanned page (Oppian, Colluthus,
Tryphiodorus, Pindar, Tibullus) it first strips footnote text that survived the page
cleaning (`strip_unit_notes`: a note number after a sentence end, a word fused to the
next, citations and edition sigla, words in no English vocabulary). Units that join
several pages or come from clean HTML or TEI are left alone, because a cut there takes
body text with it. It also holds the cleaning every scanned Loeb page needs (footnote
blocks cut off the page, folios and running heads, words the scan broke across
lines). Sources stay in a staging folder (`TESSERAE_BATCH_STAGE`), never in the
repository, and the files ship by copy (see "Installing a build").
**What the checks cannot catch, found by reading passages.** Both checks passed an
Epigrams alignment of Callimachus in which epigram 13 held the English of a different
epigram (names 0.227, length 0.451, floors 0.25 and 0.45, so the length check passed by
a hair). It was not written. A first Polyaenus version paired "Thibron" with a chapter
about Mnasippidas at names 0.91 and length 0.94. Reading five passages of every work
against the original is part of the procedure, and where numbers are read off a scan
the script now confirms each pairing by an independent signal before writing it.
| Script | Works | Source | Method | Coverage | Names | Length r |
|---|---|---|---|---|---|---|
| `align_oppian_mair.py` | Oppian, Halieutica and Cynegetica | Mair, Loeb 1928 | running head with Greek line range, as Statius | 99.5%, 98.4% | 0.54, 0.71 | 0.71, 0.62 |
| `align_oppian_mair.py` | Colluthus, Tryphiodorus | Mair, Loeb 1928 | no ranges in the heads, so the Greek lines of the facing page are counted and scaled to our line count | 100%, 100% | 0.69, 0.77 | 0.91, 0.67 |
| `align_theoi_exact.py` | Aratus, Callimachus Hymns, Lycophron, Bion Lament for Adonis, Theocritus Idylls | Mair and Mair, Loeb 1921, and Edmonds, Loeb 1912, as transcribed by Theoi | paragraph markers that are Greek line numbers | 100%, 100%, 100%, 100%, 92.3% | 0.36, 0.77, 0.79, 0.89, 0.75 | 0.99, 0.99, 1.00, -0.17, 0.63 |
| `align_pindar_sandys.py` | Pindar, Odes | Sandys, Loeb 1915 | running head with ode and line range | 89.5% | 0.65 | -0.05 |
| `align_tibullus_postgate.py` | Tibullus | Postgate, Loeb 1912 | the facing Latin page is found in our Latin text, the English page takes those lines | 92.4% | 0.64 | 0.36 |
| `align_lysias_lamb.py` | Lysias, Speeches | Lamb, Loeb 1930, via Perseus TEI (pipeline 1) | speech and section, one to one | 100% | 0.84 | 0.91 |
| `align_gregory_dialogues.py` | Gregory the Great, Dialogues, Books 1 to 3 | P. W. 1608, edited by Gardner 1911 | chapter heads in a blackletter scan, numbered by a monotone fit | 67.2% (Book 4 not written) | 0.74 | 0.995 |
| `align_polyaenus_shepherd.py` | Polyaenus, Stratagems | Shepherd 1793 | the order of the generals named in the chapter heads, matched to our chapters by the longest common subsequence | 45.1% | 0.87 | 0.88 |
Where a check is weak, the other speaks. Aratus has few names but a length correlation
of 0.99. Pindar and Bion have a length correlation near zero or below (Bion's eleven
units are few and alike in length) and are vouched by names and by reading.
**Not written, and why.**
- Seneca's tragedies from Miller's Loeb of 1917. The installed files of 1907 already
  cover 99.5 percent of our references (205 of 206 in Medea, 207 of 208 in Oedipus),
  one block of English per five-line block, which is the finest grain our
  references allow. The figure of 19 percent in the sweep came from dividing
  references by lines, and our references are blocks of five lines. The Loeb
  transcription on Theoi marks one paragraph per speech, 15 to 60 lines, so it would
  replace finer English with coarser.
- Callimachus Epigrams, the Aetia, the Hecale, the Iambi and the other fragments.
  The Epigrams numerals are read too badly to number them (see above), and the
  fragment files follow Pfeiffer's numbering, not Mair's.
- Theocritus Idylls 16, 19, 20 and 27 and Pythian 6 of Pindar. The printed
  numbering runs past our line count (Idyll 16: 114 against 109, Idyll 19: 33
  against 8, Idyll 27: 72 against 43, Pythian 6: 54 against 50). Theoi has no
  Idyll 20.
- Gregory, Book 4. Our Latin ends at chapter 60 and the English runs to 62
  chapters, so the two numberings disagree.
- Theocritus Epigrams, Bion's other poems, Moschus.

---

## Pipelines 9 and 10: Loeb volumes of 1931 to 1963 with no renewal (2026-10-24)

Eighteen files for eleven works (three of them laid over installed files), built from Loeb Classical Library volumes first
published 1931 to 1963 whose title page shows a United States publisher (Harvard
University Press, G. P. Putnam's Sons) beside the London one. A search of the NYPL
cce-renewals data found no renewal of any of them
(`renewal_search.py`, one search per volume, strings recorded in the pull request).
Under US law a work published in the United States in those years whose copyright was
not renewed in its 28th year is in the public domain, and a Loeb volume published at
once in London and Cambridge, Massachusetts or New York is a US work that the 1996
restoration did not reach. Every file's `sources` says so with the license
"public domain, US, copyright not renewed (renewal check 2026-10-24)".
Most scans are later printings of the first edition (the copyright page says which, and
the pull request lists the printing of each scan).

Both pipelines use `loeb_pages.py` (reading a page's English out of an OCR column that
also holds the facing source page, the apparatus and the footnotes, the contiguity
repair of misread header numbers, the two checks, the units) and refuse to write a file
whose checks fail. The name check abstains below twenty names and an abstention is
never counted as a pass.

**Pipeline 9: the running header names the source range** (the Statius method).
Where the English page's header gives the source range exactly, the range is the
address. `align_nonnus.py` (header "DIONYSIACA, XVII. 321-350"), `align_silius_duff2.py`
("PUNICA, IX. 17-44"), `align_josephus_antiquities.py` ("JEWISH ANTIQUITIES, V. 93-97",
Niese's continuous sections, which are our references), `align_dionysius_cary.py`
("BOOK V. 4, 2-5, 2", chapter and section), `align_sextus.py` (continuous section
numbers, with the Loeb's book numbering mapped to ours), `align_ptolemy_tetrabiblos.py`
(book and chapter, a unit being every page of the chapter) and `align_pausanias.py`
(region, chapter and section, Roman chapter numerals repaired against the sequence).
A section shared by two pages goes to the page where it begins.

**Pipeline 10: our own text is the address** (`loeb_locate.py`). Where the header gives no
range, or its numerals are unreadable, the scan is split into spreads (a source page
then its English page), each reference of ours is found on a source page by a probe of
its opening letters (normalized, accents and u/v, i/j folded, or the Greek letters
alone), the references are walked in order so a probe can only be found after the
previous one, and the walk begins only where three references in a row are found.
A reference takes the English page of its spread, or the pages from its own to the one
under the next reference's opening. `align_pliny_elder.py`, `align_minor_latin_poets.py`,
`align_prudentius_thomson.py`, `align_republic_shorey.py` and
`align_ennius_warmington.py` (refused, see below) use it.

`strip_book_summaries.py` cuts the volumes' own headings off the first unit of a book (Duff's
"ARGUMENT" of each book of the Punica, the English title of three Peristephanon poems).
`repair_book_openings.py` recovers the unheaded first page of each book where it applies
(Nonnus, Grattius, Calpurnius, Silius). `merge_unit_sources.py` lays a new alignment over
an installed file and keeps both translators (`unit_sources`). The whole sequence is
`run_unrenewed_batch.sh`.

What each file is, with the share of our references it pairs (`coverage`), the name
check, and what was left out.

- **Nonnus, Dionysiaca** (Rouse, vols 2 and 3, 1940 and 1942): books 16 to 48, 62 percent
  of the work, names 0.60 and 0.76 for the two volumes (0.53 on the whole file after the
  openings were recovered). Volume 1 (books 1 to 15) is not written.
  The only open scan has lost half its pages and many words on the rest (names 0.16),
  below the bar.
- **Pliny the Elder, Natural History** (Rackham, Jones, Eichholz, ten volumes, 1938 to
  1963): 93 percent, names 0.83, unit length correlation 0.68. Merged over Bostock.
  Each reference is one to a few Loeb pages (about 500 words), neighbouring chapters on
  a page share one. Book 1 (contents) has no English text to match.
- **Josephus, Jewish Antiquities books 5 to 17** (Thackeray, Marcus, Wikgren, 1934 to 1963):
  95 percent of those books, names 0.83. Merged over Whiston. Books 1 to 4 (1930) and 18
  to 20 (1965) are outside this batch, the Vita and the Jewish War as well.
- **Dionysius of Halicarnassus, Roman Antiquities** (Cary, 1937 to 1950): books 1 to 11,
  81 percent of the work, names 0.81. Books 12 to 20 are excerpts without page ranges and
  are not aligned. A separate file from the Spelman alignment.
- **Sextus Empiricus** (Bury): Outlines of Pyrrhonism 84 percent (names 0.81), Against the
  Logicians (adversus mathematicos 7 and 8) and Against the Professors (1 to 6) 45
  percent of the whole adversus mathematicos (names 0.78). Volume 3 (9 to 11) has no open
  scan.
- **Minor Latin Poets, vol. I** (Duff and Duff, 1934): Grattius 98 percent (names 0.75),
  Calpurnius Siculus 99.6 percent (names 0.62). Volume II (Rutilius, Tiberianus and
  the Phoenix) has no open scan, Nemesianus is installed already.
- **Silius Italicus, Punica books 9 to 17** (Duff, 1934): 94 percent, names 0.66. A
  separate file and a merged one (Duff vol. II over the installed Duff vol. I and
  Kline), the main session chooses.
- **Prudentius** (Thomson, 1949 and 1953): Apotheosis, Hamartigenia, Psychomachia, Contra
  Symmachum, Peristephanon and Dittochaeon, 96 to 100 percent, names 0.56 to 0.82. The
  Epilogus (34 lines) is refused, too few names to vouch for it.
- **Ptolemy, Tetrabiblos** (Robbins, 1940): 94 percent by chapter, names 0.51,
  unit length correlation 0.61.
- **Pausanias, books 6 to 8.21** (Jones and Ormerod, vol. III, 1933): 76 percent, names
  0.92. Volumes IV and V have no open scan. A separate file from Shilleto.
- **Plato, Republic books 6 to 10** (Shorey, vol. II, 1935): 68 percent, names 0.58 on
  66 names. Books 1 to 5 are volume I (1930), outside this batch.
- **Refused: Ennius, Annales** (Warmington, 1935). Warmington numbers fragments in his own
  order and prints his own readings, so only 71 of our 680 lines were found on a page.
  `align_ennius_warmington.py` writes nothing.

The scans of the Digital Library of India are noisier than the others (visible in the
English as `1s` for `is`, `maiket` for `market`). The share of running words outside a
vocabulary taken from installed translations is 7 to 13 percent for Prudentius, 12 to 14
for Dionysius, Josephus and Silius, 16 to 21 for Sextus, Pliny, Nonnus, Ptolemy and the
Republic, and 24 for Pausanias, against 13 to 19 for installed Perseus and Bohn files.

## Pipeline 9: chapter, section and speech level sources (2026-10-24, Part C)

Sixteen scripts and one shared module (`chapter_common.py`) build 85 served files, one per work, plus
four files held back for a reading. All of them write the served shape directly
(`units`, `ref_to_unit`, `sources`, `verified_by`), so `compact_for_serving.py` has nothing to do
for them (it was run over the output and reported 0 files compacted, and it is still needed for
the Hippocrates files that `align_perseus.py` wrote). Nothing here is installed: the files wait in a
staging folder with a `SHA256SUMS.txt`, and `measure_staging.py DIR` re-measures every one of them
against the corpus before an install.

**The checks.** Every file passes `chapter_common.finish()`, which refuses to write unless one of
two checks vouches for it: the proper-name check (0.30 or better on at least 20 names, 7 for a work
that is one unit) or the length correlation between the summed length of the source lines a unit
covers and the length of its English (0.80 or better). Where the pairing was made by cumulative
length (Cicero) the length correlation is circular and is not counted. A third test, new here, is the
rival-unit test: every unit's own English must score at least as well, against the proper names of
its source lines, as the English of any unit more than three places away. It exists because of the
Maximus of Tyre dissertations, where Taylor and our Greek number the forty-one dissertations in
different orders. Number to number pairing passed the name check (0.67) and failed the rival test
completely (0 of 41), and it would have put the wrong English beside every dissertation.

**Where the translators number differently from us.** `group_align` and `end_merge_map` align the
chapters of the two numberings by length, and a count that differs is repaired only where the
lengths say two chapters on one side are one on the other (at most three such places in a book).
Otherwise the book is refused. Differences of one at the end of a book were repaired that way
for Topics book 5, Sophistical Refutations, On the Heavens book 4, the Instructor book 2 and Gregory's
first oration. Refused: Parts of Animals book 4, Eutropius books 2 and 9 (the OCR lost the chain of
numerals), Hippocrates Aphorisms (the numbering drifts and two aphorisms stand in the other order).

| Script | Works | Source | Level | Coverage | Checks |
|---|---|---|---|---|---|
| `align_eusebius_mcgiffert.py` | Eusebius, Church History | McGiffert, NPNF 2.1 (1890), New Advent | chapter | 98% | names 0.89, length 0.995 |
| `align_pausanias_shilleto.py` | Pausanias | Shilleto, Bohn (1886), IA scans | chapter | 99.7% (355 of 357 chapters) | names 0.996, length 0.94 |
| `align_arrian_chinnock.py` | Arrian, Anabasis | Chinnock (1884), Gutenberg 46976 | chapter | 99.8% | names 0.98, length 0.98 |
| `align_maximus_taylor.py` | Maximus of Tyre | Taylor (1804), IA scans, through a concordance of the two orderings | dissertation | 100% | names 0.80, length 0.81, rival 0.98 |
| `align_isocrates_norlin.py` | Isocrates, speeches 1 to 8, 12, 13, 15 | Norlin, Loeb 1928 and 1929, Perseus TEI | section | 73% (the rest is Van Hook, 1945) | names 0.62, length 0.90 |
| `align_demosthenes_vince.py` | On the Crown, On the Embassy, Against Leptines | Vince, Loeb 1926 and 1930, Perseus TEI | section | 100% | names 0.89 to 0.94, length 0.88 to 0.93 |
| `align_demosthenes_kennedy.py` | 41 speeches, the Exordia, the Epistles | Kennedy, Bohn (1852 to 1863), IA scans | speech, exordium, letter | 100% for the speeches, 87% Exordia | printed title, length ratio, names |
| `align_perseus_direct.py` | Apollodorus (Library, Epitome), Epictetus (Discourses, Encheiridion), Hippocrates Ancient Medicine | Frazer 1921, Long 1890, Adams 1886, Perseus TEI | exact numbers | 100% | names 0.9 to 1.0, length 0.91 to 1.0 |
| `align_cicero_yonge_watson.py` | In Verrem, De Oratore, Brutus, De Fato | Yonge 1851 and 1853, Watson 1860, IA scans | chapter by cumulative length (Brutus exact) | 100% | names 0.74 to 0.99 |
| `align_florus_forster.py` | Florus | Forster, Loeb 1929, LacusCurtius | chapter | 100% | names 0.95, length 0.996, rival 1.0 |
| `align_aristotle_ne_rackham.py` | Nicomachean Ethics | Rackham, Loeb 1926, Perseus TEI | Bekker position | 100% | names 0.76, rival 0.88 |
| `align_aristotle_oxford.py` | Categories, Interpretation, Analytics, Topics, Sophistical Refutations, Physics, Heavens, Meteorology, Sense, Athenian Constitution | Oxford translation 1891 to 1930, Internet Classics Archive | chapter | 98 to 100% | length 0.94 to 0.999 |
| `align_newadvent_fathers.py` | Clement (Exhortation, Instructor, Rich Man), Basil Letters, Gregory of Nazianzus Orations 27 to 31 | ANF and NPNF, New Advent | chapter, letter, section | 71 to 100% | names 0.68 to 1.0, length 0.89 to 0.999 |
| `align_apuleius_eutropius.py` | Apuleius Apologia and Florida, Eutropius | Butler 1909 (Gutenberg), Watson 1853 (IA) | chapter | 100%, Eutropius 74% | names 0.94 to 0.99 |
| `align_celsus_greive.py` | Celsus, De Medicina | Greive 1756, Gutenberg 64207 | chapter | 73% | names 0.82, length 0.93 |
| `align_cassiodorus_hodgkin.py` (held back) | Cassiodorus, Variae | Hodgkin 1886, a CONDENSED translation | letter | 56% | names 0.80, rival 0.79 |

Held back for a reading in `review/`: Euripides, Rhesus (Murray 1913 through Perseus, exact line
numbers, five passages read and right, but rhyming verse gives a length correlation of 0.21 and the
names reach 0.26), two short Plutarch essays (one unit each, too few names to speak), and Cassiodorus,
whose OCR carries the marginal glosses into the text and whose English is Hodgkin's summary.

Not written, with the reason: Hippocrates Aphorisms (numbering drifts), Aristotle Parts of Animals
(book 4 differs by more than an end merge), Problemata (the OCR loses most problem numbers), Psalms of Solomon (the Ryle
and James volume interleaves the English with commentary and the Charles volume numbers verses
differently), Dionysius of Halicarnassus (Spelman 1758: long s and two-column notes run into the text),
Bacchylides (Jebb's English is interleaved with Greek and commentary, Poste translates ten odes), Achilles
Tatius (Smith 1855 has books only), Saxo (Elton cites Holder's pages), Valerius Maximus (Speed 1678 is
not digitized), Manilius and the Latin Dante by decision (a verse paraphrase, an unproven canto match).

To rebuild the four Hippocrates files and the held-back Perseus files: run `align_perseus.py` once
(`TESSERAE_TRANS_OUT=<dir>`), run `compact_for_serving.py <dir>`, then
`finalize_perseus_extras.py <out> <dir>/grc__hippocrates.de_articulis.json ...`, which re-measures each
file and sorts it into `<out>` or `<out>/review`.

## Paths

Defaults are the machine this was run on, kept so the record is honest, and
overridable so nobody edits a checked-in file to run it elsewhere:

| variable | default |
|---|---|
| `TESSERAE_PERSEUS_WORK` | `~/perseus_trans/work` |
| `TESSERAE_TEXTS` | `/var/www/tesseraev6_flask/texts` |
| `TESSERAE_TRANS_OUT` | `~/perseus_trans/translations_v3` |
| `TESSERAE_BATCH_STAGE` | `~/tesserae-backups/translations_exact_2026-10-24` (sources in `src/`, built files in `out/`) |
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
