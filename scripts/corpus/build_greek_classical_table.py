"""Build a classical Greek lemma lookup table from the GLAUx treebank corpus.

Reads 936 XML treebank files, downloaded under ``_source/glaux-trees`` from
https://github.com/perseids-publications/glaux-trees (branch ``master``,
``public/xml/*.xml``). Each file is a ``<treebank>`` of ``<sentence>``
elements containing self-closing ``<word>`` elements, e.g.:

    <word id="640955" form="ἀρχόμενος" line="1" lemma="ἄρχω"
          postag="v-sppemn-" head="640963" relation="ADV"/>

GLAUx is Alek Keersmaekers' "large-scale automatically lemmatized and
parsed corpus of Ancient Greek" (26M+ tokens of literary Greek, 8th c. BC to
3rd/4th c. AD; lemmatization ~99% accurate per the GLAUx paper, largely
rule-based via Morpheus). This script treats the per-occurrence ``form`` /
``lemma`` pair on every ``<word>`` element as a training signal and keeps,
for each surface form, whichever lemma is attested most often.

Writes, under ``data/lemma_tables/``:

  - ``greek_classical_lemmas.json``   normalized surface form -> normalized
    lemma, for forms NOT present as a key in EITHER existing table
    (``greek_lemmas.json``, the UD-treebank table, or ``greek_koine_lemmas.json``,
    the Septuagint table). When a surface form has more than one attested
    lemma in GLAUx, the most frequent (by occurrence count) is kept; ties
    are broken by picking the alphabetically first lemma, for determinism.
  - ``greek_classical_conflicts.json``  forms that already exist in one of
    the two existing tables with a DIFFERENT lemma, for a human to
    adjudicate: ``{form: {"existing": <existing lemma>, "glaux": <GLAUx
    lemma>, "glaux_count": <occurrences of the GLAUx lemma for this
    form>}}``. "existing" is read from ``greek_lemmas.json`` when the form
    is a key there (it always wins at lookup time), else from
    ``greek_koine_lemmas.json``.
  - ``GREEK_CLASSICAL_LICENSE.txt``  attribution/licence text.

A GLAUx (form, lemma) pair is skipped entirely -- never counted, never
written -- when either side normalizes to the empty string. That already
excludes punctuation lemmas (",", ".", ";", "·", "—", ...), bare
numeral lemmas ("1", "10", ...), and GLAUx's own disambiguating sense
digits on otherwise-real lemmas (e.g. "ἅλοα1" -> normalizes to
"αλοα", identical to a plain "ἅλοα" lemma, since
normalization strips anything that isn't a Greek letter). A ``<word>``
element with no ``lemma`` attribute at all (seen on 158 of the 45,630 words
in one sample file, apparently not yet annotated) is likewise skipped.

Normalization matches the convention already used in
``data/lemma_tables/greek_lemmas.json`` and ``greek_koine_lemmas.json``:
NFD-decompose, drop combining marks (accents/breathings/iota subscript),
lowercase, final sigma ("ς") rewritten as medial sigma ("σ"), and
anything left that is not a Greek letter (or plain a-z, for the rare
Latin-alphabet lemma) is dropped.

Licence: the source repository (perseids-publications/glaux-trees) carries
two licence files. ``LICENSE`` (MIT) covers the repository's own code; the
treebank XML data itself is covered by ``TREEBANK_LICENSE``, whose full
text is Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA
4.0) -- note the repository's README summarizes this (inherited, unedited,
from the generic "treebank-template" this repo was built from) as "CC0
1.0", which does not match the actual ``TREEBANK_LICENSE`` file content;
this script's licence file quotes the file as found, CC BY-SA 4.0, and
treats that as authoritative. See ``GREEK_CLASSICAL_LICENSE.txt`` for the
full text and the discrepancy note.

Usage:
    python scripts/corpus/build_greek_classical_table.py
Run from the repository root (expects ``_source/glaux-trees/public/xml/``
beside it and ``data/lemma_tables/greek_lemmas.json`` /
``greek_koine_lemmas.json`` to already exist).
"""

import glob
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_XML_DIR = ROOT / "_source" / "glaux-trees" / "public" / "xml"
TABLES = ROOT / "data" / "lemma_tables"

MAIN_TABLE_PATH = TABLES / "greek_lemmas.json"
KOINE_TABLE_PATH = TABLES / "greek_koine_lemmas.json"

OUT_TABLE = TABLES / "greek_classical_lemmas.json"
OUT_CONFLICTS = TABLES / "greek_classical_conflicts.json"
OUT_LICENSE = TABLES / "GREEK_CLASSICAL_LICENSE.txt"

LICENSE_TEXT = """\
Classical Greek lemma table: source licence and attribution
=============================================================

data/lemma_tables/greek_classical_lemmas.json and
data/lemma_tables/greek_classical_conflicts.json are built by
scripts/corpus/build_greek_classical_table.py from the per-word form/lemma
annotations in 936 treebank XML files published in the GitHub repository:

    perseids-publications/glaux-trees
    https://github.com/perseids-publications/glaux-trees

That repository publishes the GLAUx corpus:

    Alek Keersmaekers, "GLAUx: a large-scale automatically lemmatized and
    parsed corpus of Ancient Greek." KU Leuven / Perseids Project.
    https://github.com/alekkeersmaekers/glaux
    See also: Keersmaekers (2021), "The GLAUx corpus: methodological
    issues in designing a long-term, diverse, multi-layered corpus of
    Ancient Greek," ACL Anthology 2021.lchange-1.6.

The repository carries two separate licence files:

  - LICENSE (MIT): covers the repository's own publishing-template code,
    Copyright (c) 2018 The Perseids Project. Not relevant to the data
    extracted here.
  - TREEBANK_LICENSE: covers the treebank XML data itself. The file's full
    text, as published at
    https://github.com/perseids-publications/glaux-trees/blob/master/TREEBANK_LICENSE ,
    is the Creative Commons Attribution-ShareAlike 4.0 International
    Public License (CC BY-SA 4.0):
    https://creativecommons.org/licenses/by-sa/4.0/legalcode

    Note: the repository's own README.md describes the treebank licence
    as "CC0 1.0" (pointing to this same TREEBANK_LICENSE file), which
    appears to be stale boilerplate inherited from the generic
    "treebank-template" repository this one was built from and does not
    match the file's actual content. This licence file treats the
    TREEBANK_LICENSE file's text (CC BY-SA 4.0) as authoritative, since
    CC BY-SA requires attribution and share-alike redistribution while CC0
    would not, and the stricter reading governs.

Because CC BY-SA 4.0 requires attribution and share-alike redistribution,
any redistribution of greek_classical_lemmas.json or
greek_classical_conflicts.json (or of a lemma table built from them) must
credit Alek Keersmaekers and the GLAUx corpus / perseids-publications/glaux-trees
as above, and must be shared under CC BY-SA 4.0 or a compatible licence.
"""


def normalize(s):
    """Normalize a Greek string to the main table's convention: NFD-decompose,
    drop combining marks, lowercase, final sigma -> medial sigma, drop
    anything left that isn't a letter."""
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower()
    s = s.replace("ς", "σ")  # final sigma -> medial sigma
    s = re.sub(r"[^a-zα-ωϛ]", "", s)  # a-z, greek lower, stigma
    return s


def iter_words(xml_path):
    """Yield (form, lemma) raw attribute strings for every <word> in a GLAUx
    treebank XML file, streaming so memory stays flat across large files."""
    for _event, el in ET.iterparse(xml_path, events=("end",)):
        if el.tag == "word":
            yield el.get("form"), el.get("lemma")
            el.clear()


def main():
    if not SRC_XML_DIR.is_dir():
        print(f"ERROR: GLAUx XML directory missing: {SRC_XML_DIR}", file=sys.stderr)
        sys.exit(1)
    for p in (MAIN_TABLE_PATH, KOINE_TABLE_PATH):
        if not p.exists():
            print(f"ERROR: required input missing: {p}", file=sys.stderr)
            sys.exit(1)

    print("Loading existing tables...")
    main_table = json.load(open(MAIN_TABLE_PATH, encoding="utf-8"))
    koine_table = json.load(open(KOINE_TABLE_PATH, encoding="utf-8"))
    print(f"  greek_lemmas.json: {len(main_table)} forms")
    print(f"  greek_koine_lemmas.json: {len(koine_table)} forms")

    xml_files = sorted(glob.glob(str(SRC_XML_DIR / "*.xml")))
    print(f"Found {len(xml_files)} GLAUx treebank XML files")

    counts = defaultdict(Counter)  # surface_norm -> Counter(lemma_norm -> count)

    n_files = 0
    n_words_total = 0
    n_words_no_lemma_attr = 0
    n_skipped_empty_norm = 0
    n_pairs_counted = 0

    for i, path in enumerate(xml_files, 1):
        n_files += 1
        try:
            for form, lemma in iter_words(path):
                n_words_total += 1
                if lemma is None:
                    n_words_no_lemma_attr += 1
                    continue
                surface_norm = normalize(form)
                lemma_norm = normalize(lemma)
                if not surface_norm or not lemma_norm:
                    n_skipped_empty_norm += 1
                    continue
                counts[surface_norm][lemma_norm] += 1
                n_pairs_counted += 1
        except ET.ParseError as e:
            print(f"ERROR: failed to parse {path}: {e}", file=sys.stderr)
            sys.exit(1)
        if i % 100 == 0 or i == len(xml_files):
            print(f"  ...{i}/{len(xml_files)} files parsed, "
                  f"{n_words_total} words seen, {len(counts)} unique surface forms so far")

    print(f"Parsed {n_files} files")
    print(f"  total <word> elements: {n_words_total}")
    print(f"  words with no lemma attribute at all: {n_words_no_lemma_attr}")
    print(f"  words skipped (form or lemma normalizes to empty -- punctuation/numbers/sense-digit-only): {n_skipped_empty_norm}")
    print(f"  (form, lemma) pairs counted: {n_pairs_counted}")
    print(f"  unique normalized surface forms: {len(counts)}")

    print("Selecting most frequent lemma per surface form...")
    new_table = {}
    conflicts = {}
    n_already_correct = 0

    for surface_norm, lemma_counter in counts.items():
        best_count = max(lemma_counter.values())
        best_lemmas = sorted(l for l, c in lemma_counter.items() if c == best_count)
        best_lemma = best_lemmas[0]

        if surface_norm in main_table:
            existing = main_table[surface_norm]
        elif surface_norm in koine_table:
            existing = koine_table[surface_norm]
        else:
            existing = None

        if existing is not None:
            if existing == best_lemma:
                n_already_correct += 1
            else:
                conflicts[surface_norm] = {
                    "existing": existing,
                    "glaux": best_lemma,
                    "glaux_count": best_count,
                }
            continue

        new_table[surface_norm] = best_lemma

    print(f"  already correct in an existing table (skipped): {n_already_correct}")
    print(f"  new classical table entries: {len(new_table)}")
    print(f"  conflicts (different lemma in an existing table): {len(conflicts)}")

    TABLES.mkdir(parents=True, exist_ok=True)

    print(f"Writing {OUT_TABLE} ...")
    with open(OUT_TABLE, "w", encoding="utf-8") as f:
        json.dump(new_table, f, ensure_ascii=False, indent=0, sort_keys=True)

    print(f"Writing {OUT_CONFLICTS} ...")
    with open(OUT_CONFLICTS, "w", encoding="utf-8") as f:
        json.dump(conflicts, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(f"Writing {OUT_LICENSE} ...")
    with open(OUT_LICENSE, "w", encoding="utf-8") as f:
        f.write(LICENSE_TEXT)

    print("Done.")
    print(f"SUMMARY files={n_files} words_total={n_words_total} "
          f"pairs_counted={n_pairs_counted} unique_surface_forms={len(counts)} "
          f"new_entries={len(new_table)} conflicts={len(conflicts)} "
          f"already_correct={n_already_correct}")


if __name__ == "__main__":
    main()
