# Aligned English translations

How the English in the Reader's Translation tab is built. Two pipelines feed the
same place, `data/translations/`, which `backend/translations.py` reads.

As of 2026-08-27 these two produce **291,298 aligned lines across 489 works**:
255,357 from Perseus and 35,941 from the Greek Bible. The served directory holds
673 works and 371,637 lines in all, the rest being the Coptic and Hebrew
scripture pairings built separately.

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
