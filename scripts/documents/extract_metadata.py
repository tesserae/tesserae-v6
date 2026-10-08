#!/usr/bin/env python3
"""Stage 3a: per-document METADATA layer for the documentary corpus
(inscriptions and papyri), built on top of the stage 2 merged corpus.

This is an offline, read-only step. It does not touch the live search
index, the backend app, or any file under /var/www. It reads:

  - the stage 2 merged corpus (`dedupe_sources.py`'s `--output`, one JSON
    object per line: the 257,428-document deduplicated set across EDH,
    EDR, papyri.info/HGV, and I.Sicily), for ids, dates, place and
    language fields already resolved there;
  - the stage 1 raw EpiDoc/TEI source files directly (NOT the stage 1
    `converted/*.jsonl`, which drops the fields this stage needs:
    licence, bibliography, EAGLE vocabulary term URIs, museum/inventory,
    dimensions, layout and hand notes, apparatus, commentary,
    translation, and image links), to fill in the metadata tiers below;
  - `data/documents/eagle_labels.csv`, an English-label lookup for the
    EAGLE Network vocabulary terms (typeins/objtyp/material/writing)
    that EDH, EDR and I.Sicily tag their text-type/object-type/material/
    execution-technique fields with.

and writes one row per merged document to a SQLite database, in two
tables:

    documents(
        id TEXT PRIMARY KEY,       -- the stage 2 merged id, e.g.
                                    -- "edh:HD067781", "merged:6400"
        collection TEXT,            -- constant 'documents'
        source TEXT,                -- edh | edr | edh+edr | isicily | papyri
        tm_id INTEGER, hgv_id INTEGER, edh_id TEXT, edr_id TEXT,
        edcs_id TEXT,

        -- Tier 1, CREDIT (required by the source licences; present on
        -- every document that has a resolvable source):
        licence_name TEXT, licence_url TEXT,
        source_name TEXT, source_url TEXT,          -- this document's own
                                                      -- page at its source
        source_name_secondary TEXT, source_url_secondary TEXT,
                                                      -- only set for an
                                                      -- edh+edr merged
                                                      -- document: the
                                                      -- OTHER source's
                                                      -- own page+licence,
                                                      -- since both apply
        licence_name_secondary TEXT, licence_url_secondary TEXT,
        trismegistos_url TEXT,       -- https://www.trismegistos.org/text/<tm_id>,
                                      -- whenever tm_id is known, independent
                                      -- of `source`
        principal_edition TEXT,      -- e.g. "CIL VI 1234", "P.Oxy. 79 5202",
                                      -- as the source gives it

        -- Tier 2, FILTER fields, normalized to English where the source
        -- gives a controlled-vocabulary term with a URI:
        text_type_label TEXT, text_type_native TEXT, text_type_uri TEXT,
        object_type_label TEXT, object_type_native TEXT, object_type_uri TEXT,
        material_label TEXT, material_native TEXT, material_uri TEXT,
        date_not_before INTEGER, date_not_after INTEGER,
        ancient_place TEXT, modern_place TEXT, region TEXT,
        pleiades_id TEXT, place_tm_id INTEGER,
        languages TEXT,              -- comma-joined, as carried by stage 2
        bilingual INTEGER,           -- 0/1
        verse INTEGER                -- 0/1, NULL where the source gives no
                                      -- structural verse marker at all (see
                                      -- `detect_verse`: only I.Sicily's <l>
                                      -- verse-line element qualifies; EDH,
                                      -- EDR and papyri.info/DDbDP have none)
    )

    display(
        id TEXT,                     -- FK to documents.id (not enforced:
                                      -- sqlite3 default, no foreign keys)
        field TEXT,                  -- one of: museum, inventory,
                                      -- dimensions, letter_height,
                                      -- layout_note, execution_technique,
                                      -- preservation_state, apparatus,
                                      -- commentary, translation, image_url
        value TEXT
        -- (id, field) is NOT unique: a document can have more than one
        -- image_url, so this is a plain multi-row table, not a dict.
    )

Tier 4 (full bibliography beyond the principal edition, prosopography) is
NOT stored: `source_url`/`source_url_secondary` already point back to the
source's own page, which carries it.

Every field is optional. A missing field is never a reason to drop a
document or stop the run; `Stats` (below) counts every miss by field and
by source, printed as a summary at the end and used to write the
coverage report. A document whose raw source file cannot be found or
fails to parse still gets a `documents` row, built from the stage 2
merged-corpus fields alone (ids, dates, place, languages); its tier 1/2
English-label/tier 3 fields are left NULL and the miss is counted under
`raw_file_missing` / `raw_parse_error`.

Field provenance for an `edh+edr` merged document: every tier 1-3 field
below is read from EDH's own raw file first, falling back to EDR's only
where EDH's is missing. This mirrors `dedupe_sources.py`'s own
object_type/material merge rule (`edh_rec.get(...) or edr_rec.get(...)`,
EDH preferred) and extends it uniformly to the metadata fields this
script adds, rather than inventing a second, different preference rule.
The CREDIT fields are the one exception: since both sources' licences
genuinely apply to a merged document, EDH's go in the primary
licence_name/licence_url/source_name/source_url columns and EDR's go in
the *_secondary columns (both always CC-BY-family licences in this
corpus; see SOURCES.md), not just whichever source happened to win the
field-preference order above.

Usage:

    python scripts/documents/extract_metadata.py \\
        --merged ~/tesserae-docs/stage2/merged/merged_corpus.jsonl \\
        --docs-root ~/tesserae-docs \\
        --eagle-labels data/documents/eagle_labels.csv \\
        --output ~/tesserae-docs/stage3/metadata.db

`--docs-root` is the directory holding `raw/edh/inscriptions`,
`raw/edr/extracted`, `raw/isicily/inscriptions`, `raw/papyri/DDbDP`, and
`raw/papyri/HGV_meta_EpiDoc` (see SOURCES.md); if omitted it defaults to
`~/tesserae-docs` (expanded for whichever account runs the script, naming
no one). `--output` defaults to `~/tesserae-docs/stage3/metadata.db` the
same way. Every other path must be passed explicitly.

Run under `tess-job` with a 12G (or lower) cap; this script holds at most
one source's raw-file index and one document's parsed XML tree in memory
at a time, well under that.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
from collections import Counter
from typing import Optional

from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"
EAGLE_VOC_RE = re.compile(
    r"https?://(?:www\.)?eagle-network\.eu/voc/([a-z]+)/lod/?\s*/?\s*(\d+)", re.IGNORECASE
)
WHITESPACE_RE = re.compile(r"\s+")


def qn(tag: str) -> str:
    return f"{{{TEI_NS}}}{tag}"


def norm_ws(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = WHITESPACE_RE.sub(" ", s).strip()
    return s or None


def text_of(elem) -> Optional[str]:
    if elem is None:
        return None
    return norm_ws("".join(elem.itertext()))


# ---------------------------------------------------------------------------
# Source-level constants (tier 1 fallback credit, from SOURCES.md)
# ---------------------------------------------------------------------------

SOURCE_META = {
    "edh": {
        "name": "Epigraphic Database Heidelberg",
        "licence_name": "CC BY-SA 4.0",
        "licence_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "url_pattern": "https://edh.ub.uni-heidelberg.de/edh/inschrift/{id}",
    },
    "edr": {
        "name": "Epigraphic Database Roma",
        "licence_name": "CC BY 4.0",
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        # Confirmed live 2026-10-07 against the files' own <idno type="URI">
        # (consistently `id_nr=`, not the `IdAr=` query param guessed before
        # checking): http://www.edr-edr.it/edr_programmi/res_complex_comune.php?id_nr=EDR182490
        "url_pattern": "http://www.edr-edr.it/edr_programmi/res_complex_comune.php?id_nr={id}",
    },
    "isicily": {
        "name": "I.Sicily",
        "licence_name": "CC BY 4.0",
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        "url_pattern": "http://sicily.classics.ox.ac.uk/inscription/{id}",
    },
    "papyri": {
        "name": "papyri.info (DDbDP / HGV)",
        "licence_name": "CC BY 3.0",
        "licence_url": "https://creativecommons.org/licenses/by/3.0/",
        # hgv/<id>, not ddbdp/<ddb-hybrid-id>: hgv_id is always a plain
        # integer in this corpus, so this needs no id-string encoding;
        # the task spec allows either pattern.
        "url_pattern": "https://papyri.info/hgv/{id}",
    },
}

TRISMEGISTOS_URL_PATTERN = "https://www.trismegistos.org/text/{tm_id}"


# ---------------------------------------------------------------------------
# EAGLE vocabulary label lookup
# ---------------------------------------------------------------------------

class EagleLabels:
    """Loads data/documents/eagle_labels.csv (vocabulary,uri,native_label,
    english_label,label_source,doc_count) and resolves a (vocabulary, ref,
    native_text) triple from a raw EpiDoc file to an English label.

    Looks up by normalized URI first (fixing the handful of malformed refs
    the source XML itself contains: a stray internal space, a missing
    slash before the numeric id, a .htm/.html suffix, or more than one
    URI in the same ref= attribute, space-separated -- the first token is
    used); falls back to a (vocabulary, native_label) match for the rare
    case where the URI could not be normalized to anything resolvable at
    all (2 of 268 distinct terms found in this corpus, both reported in
    the coverage report)."""

    def __init__(self, path: str):
        self.by_uri: dict[tuple[str, str], dict] = {}
        self.by_label: dict[tuple[str, str], dict] = {}
        with open(path, "r", encoding="utf-8", newline="") as f:
            lines = [ln for ln in f if not ln.startswith("#")]
        reader = csv.DictReader(lines)
        for row in reader:
            key_uri = (row["vocabulary"], row["uri"])
            self.by_uri[key_uri] = row
            key_label = (row["vocabulary"], row["native_label"].strip().lower())
            self.by_label.setdefault(key_label, row)

    @staticmethod
    def normalize_uri(uri: str) -> Optional[str]:
        """Canonicalizes a ref= value from the raw XML to the same key
        `data/documents/eagle_labels.csv` was built with, so a term found
        via https:// (I.Sicily; EDH/EDR use http://) or with a .htm/.html
        suffix, a missing slash before the numeric id ("lod6"), a stray
        internal space ("typeins/l od/112"), two whitespace-separated
        URIs in one ref= (the first is used), or a doubled scheme prefix
        ("http://www.http://www...", seen once in this corpus) all
        resolve to the one row for that concept."""
        uri = uri.strip()
        if uri.count("http") > 1:
            parts = [p for p in uri.split() if "/voc/" in p]
            if not parts:
                return None
            uri = parts[0]
        else:
            uri = re.sub(r"\s+", "", uri)
        uri = re.sub(r"^https?://(www\.)?", "http://www.", uri)
        uri = re.sub(r"^(http://www\.)+", "http://www.", uri)
        uri = re.sub(r"(voc/[a-z]+/lod)(\d)", r"\1/\2", uri)
        uri = re.sub(r"\.html?$", "", uri)
        uri = uri.rstrip("/")
        if uri.endswith("/lod") or "/voc/" not in uri:
            return None
        return uri

    def lookup(self, vocabulary: str, ref: Optional[str], native: Optional[str]):
        """Returns (english_label, native_label, uri) or (None, native, ref)
        if nothing resolves. `native_label` in the return is always THIS
        document's own term text (the `native` argument), never the
        CSV's own `native_label` column: that column holds just one
        representative spelling per URI (picked by document-count when
        the lookup table was built, usually from whichever source tags
        that concept most often), since EDH, EDR and I.Sicily tag the
        same EAGLE concept in different languages/spellings (e.g. EDH's
        "Grabinschrift" and EDR's "sepulcralis" are the same typeins
        URI, lod/92); only the URI/label are shared, not the spelling."""
        if ref:
            norm = self.normalize_uri(ref)
            if norm:
                row = self.by_uri.get((vocabulary, norm))
                if row:
                    return row["english_label"] or None, native, norm
        if native:
            row = self.by_label.get((vocabulary, native.strip().lower()))
            if row:
                return row["english_label"] or None, native, row["uri"]
        return None, native, ref


def eagle_vocab_from_ref(ref: Optional[str]) -> Optional[str]:
    if not ref:
        return None
    m = EAGLE_VOC_RE.search(ref)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Raw-file indexing: local id (filename stem) -> path, one index per source
# ---------------------------------------------------------------------------

def index_dir(root_dir: str) -> dict:
    index = {}
    if not root_dir or not os.path.isdir(root_dir):
        return index
    for dirpath, _dirnames, filenames in os.walk(root_dir):
        for name in filenames:
            if name.endswith(".xml"):
                index[os.path.splitext(name)[0]] = os.path.join(dirpath, name)
    return index


def parse_xml(path: Optional[str], stats: "Stats", source: str):
    if not path:
        stats.miss(source, "raw_file_missing")
        return None
    if not os.path.exists(path):
        stats.miss(source, "raw_file_missing")
        return None
    try:
        return etree.parse(path).getroot()
    except etree.XMLSyntaxError:
        stats.miss(source, "raw_parse_error")
        return None


# ---------------------------------------------------------------------------
# Field extraction from one TEI root
# ---------------------------------------------------------------------------

def extract_licence(root) -> tuple[Optional[str], Optional[str]]:
    avail = root.find(f".//{qn('publicationStmt')}/{qn('availability')}")
    if avail is None:
        return None, None
    licence = avail.find(qn("licence"))
    if licence is not None:
        return text_of(licence), licence.get("target")
    ref = avail.find(f".//{qn('ref')}[@type='license']")
    if ref is not None:
        return text_of(ref), ref.get("target")
    return None, None


def extract_source_uri(root) -> Optional[str]:
    for idno in root.iter(qn("idno")):
        if idno.get("type") == "URI":
            val = text_of(idno)
            if val:
                return val
    return None


def extract_text_type(root, eagle: EagleLabels):
    term = root.find(f".//{qn('profileDesc')}/{qn('textClass')}/{qn('keywords')}/{qn('term')}")
    if term is None:
        return None, None, None
    native = text_of(term)
    ref = term.get("ref")
    if ref and "ontology.inscriptiones.org" in ref:
        # I.Sicily's own type-of-inscription ontology (not an EAGLE
        # vocabulary term): its term text is already the English label
        # (e.g. "funerary"), so it needs no lookup/translation.
        return native, native, ref
    vocab = eagle_vocab_from_ref(ref) or "typeins"
    label, native_out, uri_out = eagle.lookup(vocab, ref, native)
    return label, native_out, uri_out


def extract_vocab_field(root, tag: str, vocabulary: str, eagle: EagleLabels):
    elem = next(root.iter(qn(tag)), None)
    if elem is None:
        return None, None, None
    native = text_of(elem)
    ref = elem.get("ref")
    label, native_out, uri_out = eagle.lookup(vocabulary, ref, native)
    if label is None and ref and "eagle-network.eu" not in ref and native:
        # I.Sicily tags some objectType values against OTHER open
        # vocabularies instead of EAGLE's (kerameikos.org pottery-shape
        # ids, Getty AAT, DAI's archwort), confirmed by inspecting the
        # coverage report's unmapped-terms list: 21 distinct refs, 594
        # documents, all already-English pottery/architecture terms
        # ("kylix", "lekythos", "rock-cut tomb", ...). Not an EAGLE
        # lookup miss to report; the native text already IS the label.
        label = native
    return label, native_out, uri_out


def extract_principal_edition_plain(root) -> Optional[str]:
    """EDH / EDR: the first <bibl> under div[@type='bibliography']."""
    div = root.find(f".//{qn('div')}[@type='bibliography']")
    if div is None:
        return None
    bibl = div.find(f".//{qn('bibl')}")
    return text_of(bibl)


def extract_principal_edition_isicily(root) -> Optional[str]:
    for div in root.iter(qn("div")):
        if div.get("type") != "bibliography":
            continue
        for listbibl in div.findall(qn("listBibl")):
            if listbibl.get("type") != "edition":
                continue
            for bibl in listbibl.findall(qn("bibl")):
                if bibl.get("type") == "corpus":
                    n = bibl.get("n") or ""
                    cited = bibl.find(qn("citedRange"))
                    cited_text = text_of(cited)
                    parts = [p for p in (n, cited_text) if p]
                    if parts:
                        return " ".join(parts)
            # no "corpus" bibl: fall back to the first non-empty one
            for bibl in listbibl.findall(qn("bibl")):
                t = text_of(bibl)
                if t:
                    return t
    return None


def extract_principal_edition_hgv(hgv_root) -> Optional[str]:
    if hgv_root is None:
        return None
    for div in hgv_root.iter(qn("div")):
        if div.get("type") == "bibliography" and div.get("subtype") == "principalEdition":
            bibl = div.find(f".//{qn('bibl')}")
            if bibl is None:
                continue
            parts = []
            title = bibl.find(qn("title"))
            if title is not None:
                parts.append(text_of(title))
            for scope in bibl.findall(qn("biblScope")):
                parts.append(text_of(scope))
            parts = [p for p in parts if p]
            if parts:
                return " ".join(parts)
    return None


def extract_principal_edition_ddbdp(root) -> Optional[str]:
    bibl = root.find(f".//{qn('sourceDesc')}//{qn('bibl')}")
    return text_of(bibl)


def extract_museum(root) -> Optional[str]:
    repo = root.find(f".//{qn('msIdentifier')}/{qn('repository')}")
    return text_of(repo)


def extract_inventory(root) -> Optional[str]:
    for idno in root.iter(qn("idno")):
        if idno.get("type") == "inventory":
            val = text_of(idno)
            if val:
                return val
    return None


def extract_dimensions(root) -> Optional[str]:
    dims = root.find(f".//{qn('supportDesc')}//{qn('dimensions')}")
    if dims is None:
        return None
    unit = dims.get("unit", "")
    parts = []
    for tag in ("height", "width", "depth"):
        el = dims.find(qn(tag))
        v = text_of(el)
        if v:
            parts.append(f"{tag} {v}{unit}")
    return "; ".join(parts) if parts else None


def extract_letter_height(root) -> Optional[str]:
    hand_note = root.find(f".//{qn('handDesc')}/{qn('handNote')}")
    if hand_note is None:
        return None
    # I.Sicily: one or more <dimensions type="letterHeight"><height .../></dimensions>
    heights = []
    for dims in hand_note.findall(qn("dimensions")):
        if dims.get("type") == "letterHeight":
            h = dims.find(qn("height"))
            v = text_of(h)
            unit = h.get("unit", "") if h is not None else ""
            if v:
                heights.append(f"{v}{unit}")
    if heights:
        return "; ".join(heights)
    # EDH / EDR: handNote's own <height>/<width> (no "letterHeight" type attr)
    h = hand_note.find(qn("height"))
    v = text_of(h)
    if v:
        unit = h.get("unit", "")
        return f"{v}{unit}"
    return None


def extract_layout_note(root) -> Optional[str]:
    layout = root.find(f".//{qn('layoutDesc')}/{qn('layout')}")
    if layout is None:
        return None
    p = layout.find(qn("p"))
    return text_of(p)


def extract_execution_technique(root, eagle: EagleLabels):
    layout = root.find(f".//{qn('layoutDesc')}/{qn('layout')}")
    if layout is None:
        return None
    rs = None
    for cand in layout.findall(qn("rs")):
        if cand.get("type") == "execution":
            rs = cand
            break
    if rs is None:
        return None
    native = text_of(rs)
    label, _, _ = eagle.lookup("writing", rs.get("ref"), native)
    return label or native


def extract_preservation_state(root, eagle: EagleLabels) -> Optional[str]:
    for rs in root.iter(qn("rs")):
        if rs.get("type") == "statPreserv":
            native = text_of(rs)
            label, _, _ = eagle.lookup("statepreserv", rs.get("ref"), native)
            return label or native
    return None


def extract_div_text(root, div_type: str) -> Optional[str]:
    """Plain-text content of div[@type=div_type] (apparatus/commentary/
    translation on EDH/EDR/HGV, which use a <p>; I.Sicily's apparatus uses
    listApp/app/note instead, joined with '; '."""
    for div in root.iter(qn("div")):
        if div.get("type") != div_type:
            continue
        notes = div.findall(f".//{qn('note')}")
        if notes:
            parts = [text_of(n) for n in notes]
            parts = [p for p in parts if p]
            if parts:
                return "; ".join(parts)
        p = div.find(qn("p"))
        t = text_of(p)
        if t:
            return t
    return None


def extract_images(root) -> list[str]:
    urls = []
    for g in root.iter(qn("graphic")):
        url = g.get("url")
        if url and url not in urls:
            urls.append(url)
    return urls


def has_verse_marker(root) -> bool:
    """True if the PRIMARY edition div contains a TEI <l> (verse line)
    element. Checked across the full raw export before writing this
    (see research notes): only I.Sicily uses <l> inside its edition text
    at all (2 of 1,000 documents, one of them carrying an explicit
    @met="hexameter"/"pentameter"); EDH's apparent hits are a false
    positive (an editorial comment using literal "<l=V>" text, not a real
    element) and EDR/papyri.info DDbDP have none. This function is only
    ever called for I.Sicily records; EDH/EDR/papyri get a NULL verse
    flag, not False, since their formats carry no comparable marker to
    say "definitely not verse" either."""
    for div in root.iter(qn("div")):
        if div.get("type") == "edition" and div.get("subtype") in (None, "primary"):
            if div.find(f".//{qn('l')}") is not None:
                return True
    return False


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class Stats:
    def __init__(self):
        self.total = 0
        self.by_source = Counter()
        self.field_present = Counter()   # (source, field) -> count
        self.misses = Counter()          # (source, field) -> count
        self.unmapped_eagle_terms = Counter()  # (vocabulary, native) -> count

    def miss(self, source, field):
        self.misses[(source, field)] += 1

    def present(self, source, field, value):
        if value is not None and value != "" and value != []:
            self.field_present[(source, field)] += 1
        else:
            self.misses[(source, field)] += 1


# ---------------------------------------------------------------------------
# Per-document extraction
# ---------------------------------------------------------------------------

TIER3_FIELDS = (
    "museum", "inventory", "dimensions", "letter_height", "layout_note",
    "execution_technique", "preservation_state", "apparatus", "commentary",
    "translation",
)


def extract_principal_edition(root, source: str) -> Optional[str]:
    if source in ("edh", "edr"):
        return extract_principal_edition_plain(root)
    if source == "isicily":
        return extract_principal_edition_isicily(root)
    if source == "papyri":
        # Handled by the caller (process_record), which has both the
        # DDbDP and HGV roots available; a single root is not enough.
        return None
    return None


def extract_from_root(root, eagle: EagleLabels, source: str) -> dict:
    """All tier 1 (minus the per-source URL/licence, handled by the
    caller) + tier 2 + tier 3 fields extractable from one raw TEI root,
    independent of which of the four sources it came from (every
    extractor above degrades to None on a tag the source doesn't use).
    `source` is one of "edh", "edr", "isicily", "papyri" (never
    "edh+edr": that case calls this once per underlying source instead)."""
    text_type_label, text_type_native, text_type_uri = extract_text_type(root, eagle)
    object_type_label, object_type_native, object_type_uri = extract_vocab_field(
        root, "objectType", "objtyp", eagle)
    material_label, material_native, material_uri = extract_vocab_field(
        root, "material", "material", eagle)
    licence_name, licence_url = extract_licence(root)
    out = {
        "licence_name": licence_name,
        "licence_url": licence_url,
        "source_uri": extract_source_uri(root),
        "principal_edition": extract_principal_edition(root, source),
        "text_type_label": text_type_label,
        "text_type_native": text_type_native,
        "text_type_uri": text_type_uri,
        "object_type_label": object_type_label,
        "object_type_native": object_type_native,
        "object_type_uri": object_type_uri,
        "material_label": material_label,
        "material_native": material_native,
        "material_uri": material_uri,
        "museum": extract_museum(root),
        "inventory": extract_inventory(root),
        "dimensions": extract_dimensions(root),
        "letter_height": extract_letter_height(root),
        "layout_note": extract_layout_note(root),
        "execution_technique": extract_execution_technique(root, eagle),
        "preservation_state": extract_preservation_state(root, eagle),
        "apparatus": extract_div_text(root, "apparatus"),
        "commentary": extract_div_text(root, "commentary"),
        "translation": extract_div_text(root, "translation"),
        "images": extract_images(root),
    }
    return out


def merge_prefer(primary: Optional[dict], secondary: Optional[dict]) -> dict:
    """Field-by-field: primary's value if present, else secondary's. Images
    are unioned (order: primary's then secondary's, de-duplicated)."""
    if primary is None and secondary is None:
        return {}
    if primary is None:
        return dict(secondary)
    if secondary is None:
        return dict(primary)
    out = {}
    for key in primary.keys():
        pv, sv = primary.get(key), secondary.get(key)
        if key == "images":
            seen = []
            for v in (pv or []) + (sv or []):
                if v not in seen:
                    seen.append(v)
            out[key] = seen
        else:
            out[key] = pv if pv not in (None, "") else sv
    return out


def build_credit(source: str, rec: dict, edh_fields: Optional[dict],
                  edr_fields: Optional[dict], single_fields: Optional[dict],
                  single_local_id: Optional[str]) -> dict:
    """Resolves licence/source-url/principal-edition per the per-source
    rules (file's own licence/idno-URI first, SOURCES.md constants as
    fallback; the EDH canonical URL pattern always wins over EDH's own
    (older, since-moved) <idno type="URI"> domain, per the stage 3a spec)."""
    credit = {
        "licence_name": None, "licence_url": None,
        "source_name": None, "source_url": None,
        "licence_name_secondary": None, "licence_url_secondary": None,
        "source_name_secondary": None, "source_url_secondary": None,
        "principal_edition": None,
    }
    tm_id = rec.get("tm_id")
    credit["trismegistos_url"] = (
        TRISMEGISTOS_URL_PATTERN.format(tm_id=tm_id) if tm_id is not None else None
    )

    def one_source(src_key, fields, local_id):
        meta = SOURCE_META[src_key]
        licence_name = (fields or {}).get("licence_name") or meta["licence_name"]
        licence_url = (fields or {}).get("licence_url") or meta["licence_url"]
        if src_key == "edh":
            # Canonical pattern per the stage 3a spec, not EDH's own
            # (older) <idno type="URI"> domain.
            source_url = meta["url_pattern"].format(id=local_id) if local_id else None
        else:
            source_url = (fields or {}).get("source_uri") or (
                meta["url_pattern"].format(id=local_id) if local_id else None
            )
        return meta["name"], source_url, licence_name, licence_url

    if source == "edh+edr":
        name, url, lic_name, lic_url = one_source("edh", edh_fields, rec.get("edh_id"))
        credit["source_name"], credit["source_url"] = name, url
        credit["licence_name"], credit["licence_url"] = lic_name, lic_url
        name2, url2, lic_name2, lic_url2 = one_source("edr", edr_fields, rec.get("edr_id"))
        credit["source_name_secondary"], credit["source_url_secondary"] = name2, url2
        credit["licence_name_secondary"], credit["licence_url_secondary"] = lic_name2, lic_url2
        credit["principal_edition"] = (
            extract_pe(edh_fields) or extract_pe(edr_fields)
        )
    else:
        name, url, lic_name, lic_url = one_source(source, single_fields, single_local_id)
        credit["source_name"], credit["source_url"] = name, url
        credit["licence_name"], credit["licence_url"] = lic_name, lic_url
        credit["principal_edition"] = extract_pe(single_fields)
    return credit


def extract_pe(fields: Optional[dict]) -> Optional[str]:
    return (fields or {}).get("principal_edition")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

DOCUMENTS_COLUMNS = [
    "id", "collection", "source", "tm_id", "hgv_id", "edh_id", "edr_id", "edcs_id",
    "licence_name", "licence_url", "source_name", "source_url",
    "licence_name_secondary", "licence_url_secondary",
    "source_name_secondary", "source_url_secondary",
    "trismegistos_url", "principal_edition",
    "text_type_label", "text_type_native", "text_type_uri",
    "object_type_label", "object_type_native", "object_type_uri",
    "material_label", "material_native", "material_uri",
    "date_not_before", "date_not_after",
    "ancient_place", "modern_place", "region", "pleiades_id", "place_tm_id",
    "languages", "bilingual", "verse",
]


INTEGER_COLUMNS = {
    "tm_id", "hgv_id", "date_not_before", "date_not_after", "place_tm_id",
    "bilingual", "verse",
}


def create_schema(conn: sqlite3.Connection) -> None:
    def col_def(c):
        if c == "id":
            return '"id" TEXT PRIMARY KEY'
        return f'"{c}" INTEGER' if c in INTEGER_COLUMNS else f'"{c}" TEXT'

    cols = ", ".join(col_def(c) for c in DOCUMENTS_COLUMNS)
    conn.execute(f"DROP TABLE IF EXISTS documents")
    conn.execute(f"CREATE TABLE documents ({cols})")
    conn.execute("DROP TABLE IF EXISTS display")
    conn.execute("CREATE TABLE display (id TEXT, field TEXT, value TEXT)")
    conn.execute("CREATE INDEX idx_display_id ON display(id)")
    conn.execute("CREATE INDEX idx_documents_source ON documents(source)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def default_docs_root() -> str:
    return os.environ.get("TESSERAE_DOCS_ROOT", os.path.expanduser("~/tesserae-docs"))


def default_output(docs_root: str) -> str:
    return os.path.join(docs_root, "stage3", "metadata.db")


def local_id_from_merged_id(merged_id: str) -> Optional[str]:
    if ":" not in merged_id:
        return None
    return merged_id.split(":", 1)[1]


def process_record(rec: dict, indices: dict, eagle: EagleLabels, stats: Stats) -> dict:
    source = rec.get("source")
    stats.total += 1
    stats.by_source[source] += 1

    edh_fields = edr_fields = single_fields = None
    single_local_id = None
    verse = None

    if source == "edh+edr":
        edh_path = indices["edh"].get(rec.get("edh_id"))
        edr_local = ("a" + rec["edr_id"]) if rec.get("edr_id") else None
        edr_path = indices["edr"].get(edr_local) if edr_local else None
        edh_root = parse_xml(edh_path, stats, "edh+edr")
        edr_root = parse_xml(edr_path, stats, "edh+edr")
        if edh_root is not None:
            edh_fields = extract_from_root(edh_root, eagle, "edh")
        if edr_root is not None:
            edr_fields = extract_from_root(edr_root, eagle, "edr")
        merged_fields = merge_prefer(edh_fields, edr_fields)
    elif source == "edh":
        path = indices["edh"].get(rec.get("edh_id"))
        root = parse_xml(path, stats, "edh")
        single_fields = extract_from_root(root, eagle, "edh") if root is not None else None
        single_local_id = rec.get("edh_id")
        merged_fields = single_fields or {}
    elif source == "edr":
        local_id = local_id_from_merged_id(rec["id"])
        path = indices["edr"].get(local_id)
        root = parse_xml(path, stats, "edr")
        single_fields = extract_from_root(root, eagle, "edr") if root is not None else None
        single_local_id = rec.get("edr_id")
        merged_fields = single_fields or {}
    elif source == "isicily":
        local_id = local_id_from_merged_id(rec["id"])
        path = indices["isicily"].get(local_id)
        root = parse_xml(path, stats, "isicily")
        single_fields = extract_from_root(root, eagle, "isicily") if root is not None else None
        single_local_id = local_id
        merged_fields = single_fields or {}
        if root is not None:
            verse = has_verse_marker(root)
    elif source == "papyri":
        local_id = local_id_from_merged_id(rec["id"])
        ddbdp_path = indices["papyri_ddbdp"].get(local_id)
        hgv_path = indices["papyri_hgv"].get(local_id)
        ddbdp_root = parse_xml(ddbdp_path, stats, "papyri")
        hgv_root = parse_xml(hgv_path, stats, "papyri")
        ddbdp_fields = extract_from_root(ddbdp_root, eagle, "papyri") if ddbdp_root is not None else None
        hgv_fields = extract_from_root(hgv_root, eagle, "papyri") if hgv_root is not None else None
        # HGV's own metadata is preferred (it is the richer, curated
        # record for date/place/object/text-type/bibliography/images for
        # papyri; DDbDP editions carry only the licence and a plain
        # bibl reliably, per epidoc_convert.py's own `merge_hgv`).
        merged_fields = merge_prefer(hgv_fields, ddbdp_fields)
        pe = extract_principal_edition_hgv(hgv_root) if hgv_root is not None else None
        merged_fields["principal_edition"] = pe or (
            extract_principal_edition_ddbdp(ddbdp_root) if ddbdp_root is not None else None
        )
        single_fields = merged_fields
        single_local_id = rec.get("hgv_id")
    else:
        merged_fields = {}

    credit = build_credit(source, rec, edh_fields, edr_fields, single_fields, single_local_id)

    findspot = rec.get("findspot") or {}
    languages = rec.get("languages") or []

    row = {
        "id": rec["id"],
        "collection": "documents",
        "source": source,
        "tm_id": rec.get("tm_id"),
        "hgv_id": rec.get("hgv_id"),
        "edh_id": rec.get("edh_id"),
        "edr_id": rec.get("edr_id"),
        "edcs_id": rec.get("edcs_id"),
        "licence_name": credit["licence_name"],
        "licence_url": credit["licence_url"],
        "source_name": credit["source_name"],
        "source_url": credit["source_url"],
        "licence_name_secondary": credit["licence_name_secondary"],
        "licence_url_secondary": credit["licence_url_secondary"],
        "source_name_secondary": credit["source_name_secondary"],
        "source_url_secondary": credit["source_url_secondary"],
        "trismegistos_url": credit["trismegistos_url"],
        "principal_edition": credit["principal_edition"],
        "text_type_label": merged_fields.get("text_type_label"),
        "text_type_native": merged_fields.get("text_type_native"),
        "text_type_uri": merged_fields.get("text_type_uri"),
        "object_type_label": merged_fields.get("object_type_label"),
        "object_type_native": merged_fields.get("object_type_native"),
        "object_type_uri": merged_fields.get("object_type_uri"),
        "material_label": merged_fields.get("material_label"),
        "material_native": merged_fields.get("material_native"),
        "material_uri": merged_fields.get("material_uri"),
        "date_not_before": rec.get("date_not_before"),
        "date_not_after": rec.get("date_not_after"),
        "ancient_place": findspot.get("ancient_place"),
        "modern_place": findspot.get("modern_place"),
        "region": findspot.get("region"),
        "pleiades_id": findspot.get("pleiades_id") or rec.get("place_pleiades_id"),
        "place_tm_id": rec.get("place_tm_id"),
        "languages": ",".join(languages) if languages else None,
        "bilingual": 1 if rec.get("bilingual") else 0,
        "verse": (1 if verse else 0) if verse is not None else None,
    }

    for field in (
        "text_type_label", "object_type_label", "material_label",
        "principal_edition", "licence_name", "source_url",
        "ancient_place", "region", "pleiades_id",
    ):
        stats.present(source, field, row.get(field))

    for field, native, uri in (
        ("text_type", merged_fields.get("text_type_native"), merged_fields.get("text_type_uri")),
        ("object_type", merged_fields.get("object_type_native"), merged_fields.get("object_type_uri")),
        ("material", merged_fields.get("material_native"), merged_fields.get("material_uri")),
    ):
        label = merged_fields.get(f"{field}_label")
        if native and not label:
            stats.unmapped_eagle_terms[(field, native, uri)] += 1

    display_rows = []
    for field in TIER3_FIELDS:
        value = merged_fields.get(field)
        stats.present(source, field, value)
        if value:
            display_rows.append((rec["id"], field, value))
    for image_url in merged_fields.get("images") or []:
        display_rows.append((rec["id"], "image_url", image_url))
    stats.present(source, "image_url", merged_fields.get("images"))

    return {"row": row, "display_rows": display_rows}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--merged", required=True,
                     help="stage 2 merged_corpus.jsonl (dedupe_sources.py --output)")
    ap.add_argument("--docs-root", default=None,
                     help="directory holding raw/edh, raw/edr, raw/isicily, "
                          "raw/papyri (default: $TESSERAE_DOCS_ROOT or ~/tesserae-docs)")
    ap.add_argument("--eagle-labels", required=True,
                     help="data/documents/eagle_labels.csv")
    ap.add_argument("--output", default=None,
                     help="SQLite db path (default: <docs-root>/stage3/metadata.db)")
    ap.add_argument("--limit", type=int, default=None,
                     help="stop after N records (for sampling/testing)")
    ap.add_argument("--stats-json", default=None,
                     help="write the coverage/miss counters to this JSON path")
    args = ap.parse_args(argv)

    docs_root = args.docs_root or default_docs_root()
    output = args.output or default_output(docs_root)
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)

    eagle = EagleLabels(args.eagle_labels)

    indices = {
        "edh": index_dir(os.path.join(docs_root, "raw", "edh", "inscriptions")),
        "edr": index_dir(os.path.join(docs_root, "raw", "edr", "extracted")),
        "isicily": index_dir(os.path.join(docs_root, "raw", "isicily", "inscriptions")),
        "papyri_ddbdp": index_dir(os.path.join(docs_root, "raw", "papyri", "DDbDP")),
        "papyri_hgv": index_dir(os.path.join(docs_root, "raw", "papyri", "HGV_meta_EpiDoc")),
    }
    print(
        f"indexed raw files: edh={len(indices['edh'])} edr={len(indices['edr'])} "
        f"isicily={len(indices['isicily'])} papyri_ddbdp={len(indices['papyri_ddbdp'])} "
        f"papyri_hgv={len(indices['papyri_hgv'])}",
        file=sys.stderr,
    )

    stats = Stats()
    conn = sqlite3.connect(output)
    create_schema(conn)
    insert_doc_sql = (
        f"INSERT INTO documents ({', '.join(DOCUMENTS_COLUMNS)}) VALUES "
        f"({', '.join('?' for _ in DOCUMENTS_COLUMNS)})"
    )

    with open(args.merged, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if args.limit is not None and i >= args.limit:
                break
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            result = process_record(rec, indices, eagle, stats)
            row = result["row"]
            conn.execute(insert_doc_sql, [row[c] for c in DOCUMENTS_COLUMNS])
            if result["display_rows"]:
                conn.executemany(
                    "INSERT INTO display (id, field, value) VALUES (?, ?, ?)",
                    result["display_rows"],
                )
            if (i + 1) % 10000 == 0:
                conn.commit()
                print(f"{i + 1} documents processed", file=sys.stderr)

    conn.commit()
    conn.close()

    print(f"wrote {stats.total} documents to {output}", file=sys.stderr)
    print(f"by source: {dict(stats.by_source)}", file=sys.stderr)

    if args.stats_json:
        out_stats = {
            "total": stats.total,
            "by_source": dict(stats.by_source),
            "field_present": {f"{k[0]}|{k[1]}": v for k, v in stats.field_present.items()},
            "misses": {f"{k[0]}|{k[1]}": v for k, v in stats.misses.items()},
            "unmapped_eagle_terms": [
                {"vocabulary": k[0], "native_label": k[1], "uri": k[2], "count": v}
                for k, v in stats.unmapped_eagle_terms.items()
            ],
        }
        with open(args.stats_json, "w", encoding="utf-8") as f:
            json.dump(out_stats, f, indent=2, ensure_ascii=False)
        print(f"wrote coverage stats to {args.stats_json}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
