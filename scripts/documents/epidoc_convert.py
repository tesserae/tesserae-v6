#!/usr/bin/env python3
"""Convert EpiDoc TEI-XML documentary texts to a normalized JSON form.

Reads EpiDoc files from one of four open-licence sources (Epigraphic
Database Heidelberg, papyri.info DDbDP + HGV metadata, I.Sicily, Epigraphic
Database Roma) and writes one JSON object per document, one document per
line (JSONL). This is a read-only conversion step: it does not touch the
live search index, the backend, or any file under /var/www.

Each output record has the shape:

    {
      "id": "<source>:<local id>",
      "source": "edh" | "isicily" | "papyri" | "edr",
      "tm_id": int or null,
      "hgv_id": int or null,
      "edh_id": str or null,
      "edr_id": str or null,
      "edcs_id": str or null,
      "languages": ["la", "grc", ...],
      "bilingual": bool,
      "title": str or null,
      "object_type": str or null,
      "material": str or null,
      "date_not_before": int or null,   # negative = BCE
      "date_not_after": int or null,
      "findspot": {
        "ancient_place": str or null,
        "modern_place": str or null,
        "region": str or null,
        "pleiades_id": str or null
      },
      "lines": [
        {"n": "1", "diplomatic": str, "expanded": str, "text": str,
         "restored_flags": [bool, ...] }   # one flag per character of "text"
      ],
      "supplied_chars": int,
      "total_chars": int,
      "gap_count": int,
      "supplied_share": float   # supplied_chars / total_chars, or 0.0
    }

Usage:
    python scripts/documents/epidoc_convert.py --source edh \
        --input-dir /home/ncoffee/tesserae-docs/raw/edh/inscriptions \
        --output /home/ncoffee/tesserae-docs/converted/edh.jsonl

    python scripts/documents/epidoc_convert.py --source papyri \
        --input-dir /home/ncoffee/tesserae-docs/raw/papyri/DDbDP \
        --meta-dir /home/ncoffee/tesserae-docs/raw/papyri/HGV_meta_EpiDoc \
        --output /home/ncoffee/tesserae-docs/converted/papyri.jsonl

Sources: edh, isicily, papyri, edr. The "papyri" source needs --meta-dir
(the HGV metadata folder) because DDbDP editions do not carry date or
findspot data themselves; that lives in the matching HGV record, linked by
the TM/HGV id shared between the two files.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Iterable, Optional

from lxml import etree

TEI_NS = "http://www.tei-c.org/ns/1.0"
NS = {"t": TEI_NS, "xml": "http://www.w3.org/XML/1998/namespace"}


def qn(tag: str) -> str:
    return f"{{{TEI_NS}}}{tag}"


# ---------------------------------------------------------------------------
# Line-level text extraction
# ---------------------------------------------------------------------------

@dataclass
class LineBuffer:
    """Accumulates the three parallel renderings of one edition line.

    diplomatic: characters as physically inscribed/written (abbreviations
        left unexpanded, as <abbr> text; supplied text included in brackets
        is not applicable here, diplomatic keeps only what survives).
    expanded: abbreviations expanded (<expan>/<ex> resolved), supplied text
        included, editorial marks (brackets) still implicit in the
        restored_flags array rather than literal bracket characters.
    restored_flags: one bool per character appended to `expanded`/`text`,
        True where that character came from <supplied reason="lost">.
    """
    diplomatic: list = field(default_factory=list)
    expanded: list = field(default_factory=list)
    restored_flags: list = field(default_factory=list)

    def add_diplomatic(self, s: str) -> None:
        self.diplomatic.append(s)

    def add_expanded(self, s: str, restored: bool = False) -> None:
        self.expanded.append(s)
        self.restored_flags.extend([restored] * len(s))

    def diplomatic_text(self) -> str:
        return "".join(self.diplomatic)

    def expanded_text(self) -> str:
        return "".join(self.expanded)


GAP_PLACEHOLDER = "█"  # solid block, stands in for an editorial gap


class EpidocConverter:
    """Walks one TEI <div type="edition"> and produces a list of lines."""

    def __init__(self):
        self.lines: list[dict] = []
        self.gap_count = 0
        self.supplied_chars = 0
        self.total_chars = 0

    def convert_edition(self, edition_div) -> list[dict]:
        self.lines = []
        self.gap_count = 0
        self.supplied_chars = 0
        self.total_chars = 0
        current = {"n": None, "buf": LineBuffer()}

        def has_content(buf: LineBuffer) -> bool:
            return bool(buf.expanded_text().strip() or buf.diplomatic_text().strip())

        def flush():
            if current["n"] is not None or has_content(current["buf"]):
                self._finish_line(current["n"], current["buf"])
            current["buf"] = LineBuffer()

        def recurse(elem, restored: bool):
            tag = etree.QName(elem).localname if elem.tag is not etree.Comment else None
            # Text directly inside this element, before any children
            if elem.tag is etree.Comment:
                return
            if tag == "lb":
                # A line break. break="no" means the word continues from
                # the previous line (no word-space should be inserted); we
                # still start a new logical line entry either way, since
                # the spec's `lines` list is keyed by printed line number.
                if current["n"] is not None or has_content(current["buf"]):
                    flush()
                current["n"] = elem.get("n")
                _append_tail(elem, restored)
                return
            if tag == "gap":
                self.gap_count += 1
                unit = elem.get("unit", "")
                quantity = elem.get("quantity", "")
                placeholder = GAP_PLACEHOLDER
                current["buf"].add_diplomatic(f"[gap:{quantity}{unit}]" if quantity else "[gap]")
                current["buf"].add_expanded(placeholder, restored=True)
                _append_tail(elem, restored)
                return
            if tag == "supplied":
                reason = elem.get("reason", "")
                inner_restored = True
                for child in elem.iterchildren():
                    recurse(child, inner_restored)
                if elem.text:
                    current["buf"].add_diplomatic("")
                    current["buf"].add_expanded(elem.text, restored=True)
                _append_tail(elem, restored)
                return
            if tag in ("expan",):
                # <expan><abbr>D</abbr><ex>is</ex></expan>: diplomatic keeps
                # the abbreviation as written; expanded keeps abbr+ex, in
                # document order (some sources interleave more than one
                # <abbr>/<ex> pair, e.g. an <abbr> wrapping a christogram
                # glyph followed by <ex> then a trailing <abbr> letter).
                diplomatic_parts = []
                if elem.text and elem.text.strip():
                    diplomatic_parts.append(elem.text)
                    current["buf"].add_expanded(elem.text, restored=restored)
                for child in elem.iterchildren():
                    ctag = etree.QName(child).localname
                    child_text = "".join(child.itertext())
                    if ctag == "ex":
                        current["buf"].add_expanded(child_text, restored=True)
                    else:
                        # abbr, or any other child: part of what was
                        # actually written, not supplied by the editor.
                        diplomatic_parts.append(child_text)
                        current["buf"].add_expanded(child_text, restored=restored)
                current["buf"].add_diplomatic("".join(diplomatic_parts))
                _append_tail(elem, restored)
                return
            if tag == "choice":
                # <choice><sic>.../<corr>...</> or <orig>.../<reg>...</>:
                # keep the regularized / corrected reading.
                reg = None
                orig = None
                for child in elem.iterchildren():
                    ctag = etree.QName(child).localname
                    if ctag in ("reg", "corr"):
                        reg = "".join(child.itertext())
                    elif ctag in ("orig", "sic"):
                        orig = "".join(child.itertext())
                chosen = reg if reg is not None else orig if orig is not None else ""
                current["buf"].add_diplomatic(orig if orig is not None else chosen)
                current["buf"].add_expanded(chosen, restored=restored)
                _append_tail(elem, restored)
                return
            if tag == "num":
                val = elem.get("value")
                text = "".join(elem.itertext())
                current["buf"].add_diplomatic(text)
                current["buf"].add_expanded(text, restored=restored)
                _append_tail(elem, restored)
                return
            if tag == "unclear":
                text = "".join(elem.itertext())
                current["buf"].add_diplomatic(text)
                current["buf"].add_expanded(text, restored=restored)
                _append_tail(elem, restored)
                return
            if tag == "hi":
                if elem.text:
                    current["buf"].add_diplomatic(elem.text)
                    current["buf"].add_expanded(elem.text, restored=restored)
                for child in elem.iterchildren():
                    recurse(child, restored)
                _append_tail(elem, restored)
                return
            if tag in ("g",):
                # a glyph/symbol, e.g. an interpunct: keep its text form
                text = elem.text or ""
                current["buf"].add_diplomatic(text)
                current["buf"].add_expanded(text, restored=restored)
                _append_tail(elem, restored)
                return
            if tag in ("w", "ab", "persName", "name", "placeName", "add",
                       "del", "handShift", "orgName", "rs"):
                if elem.text:
                    current["buf"].add_diplomatic(elem.text)
                    current["buf"].add_expanded(elem.text, restored=restored)
                for child in elem.iterchildren():
                    recurse(child, restored)
                _append_tail(elem, restored)
                return
            if tag == "head":
                # Heading text is not part of the edition proper.
                return
            if tag in ("milestone", "pb", "cb"):
                _append_tail(elem, restored)
                return
            # Default: treat as transparent container, descend.
            if elem.text:
                current["buf"].add_diplomatic(elem.text)
                current["buf"].add_expanded(elem.text, restored=restored)
            for child in elem.iterchildren():
                recurse(child, restored)
            _append_tail(elem, restored)

        def _append_tail(elem, restored):
            if elem.tail:
                current["buf"].add_diplomatic(elem.tail)
                current["buf"].add_expanded(elem.tail, restored=restored)

        for child in edition_div.iterchildren():
            ctag = etree.QName(child).localname if child.tag is not etree.Comment else None
            if ctag == "head":
                continue
            recurse(child, False)
        flush()
        return self.lines

    def _finish_line(self, n, buf: LineBuffer) -> None:
        expanded_text = buf.expanded_text()
        # "text": expanded text with editorial marks removed. Our
        # add_expanded already stores plain characters (no literal bracket
        # markup), so expanded_text IS the plain text; restored_flags marks
        # which characters were supplied.
        plain = expanded_text
        flags = buf.restored_flags
        if len(flags) != len(plain):
            # Defensive: pad/truncate rather than crash on a mismatch.
            if len(flags) < len(plain):
                flags = flags + [False] * (len(plain) - len(flags))
            else:
                flags = flags[: len(plain)]
        # Strip leading/trailing whitespace from the text, and drop the
        # same number of entries from the front/back of restored_flags so
        # the two stay in lockstep (a plain str.strip() on the text alone
        # would leave restored_flags longer than the stripped text).
        stripped_text = plain.strip()
        if stripped_text:
            lead_cut = len(plain) - len(plain.lstrip())
            trail_cut = len(plain) - len(plain.rstrip())
            stripped_flags = flags[lead_cut: len(flags) - trail_cut or None]
        else:
            stripped_flags = []
        supplied = sum(1 for f in stripped_flags if f)
        self.supplied_chars += supplied
        self.total_chars += len(stripped_text)
        self.lines.append({
            "n": n,
            "diplomatic": buf.diplomatic_text().strip(),
            "expanded": expanded_text.strip(),
            "text": stripped_text,
            "restored_flags": stripped_flags,
        })


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _text(elem) -> str:
    return "".join(elem.itertext()).strip() if elem is not None else ""


def _first(elems):
    return elems[0] if elems else None


def _parse_year(value: Optional[str]) -> Optional[int]:
    """Parse an EpiDoc date-ish integer string ("0071", "-0071", "0289")
    into a signed int. origDate/when uses ISO-like "0289-09-17" sometimes;
    callers should pass only the year portion."""
    if value is None or value == "":
        return None
    value = value.strip()
    try:
        return int(value)
    except ValueError:
        return None


def extract_date(history_elem) -> tuple[Optional[int], Optional[int]]:
    if history_elem is None:
        return None, None
    orig_date = history_elem.find(f".//{qn('origDate')}")
    if orig_date is None:
        return None, None
    nb = orig_date.get("notBefore-custom") or orig_date.get("notBefore")
    na = orig_date.get("notAfter-custom") or orig_date.get("notAfter")
    when = orig_date.get("when")
    not_before = _parse_year(nb)
    not_after = _parse_year(na)
    if not_before is None and not_after is None and when:
        year_part = when.split("-")[0]
        y = _parse_year(year_part)
        not_before = y
        not_after = y
    return not_before, not_after


def extract_pleiades_id(history_elem) -> Optional[str]:
    if history_elem is None:
        return None
    for place in history_elem.iter(qn("placeName")):
        ref = place.get("ref") or ""
        for token in ref.split():
            if "pleiades.stoa.org/places/" in token:
                return token.rstrip("/").rsplit("/", 1)[-1]
    return None


def extract_findspot(history_elem) -> dict:
    out = {"ancient_place": None, "modern_place": None, "region": None,
           "pleiades_id": extract_pleiades_id(history_elem)}
    if history_elem is None:
        return out
    origin = history_elem.find(qn("origin"))
    if origin is not None:
        orig_place = origin.find(qn("origPlace"))
        if orig_place is not None:
            names = orig_place.findall(qn("placeName"))
            region_names = [n for n in names if n.get("type") in
                             ("provinceItalicRegion", "region")]
            ancient_names = [n for n in names if n.get("type") in
                              (None, "ancient")]
            if region_names:
                out["region"] = _text(region_names[0]) or None
            if ancient_names:
                out["ancient_place"] = _text(ancient_names[0]) or None
            elif names:
                out["ancient_place"] = _text(names[0]) or None
            elif orig_place.text and orig_place.text.strip():
                out["ancient_place"] = orig_place.text.strip()
    provenance = history_elem.find(qn("provenance"))
    if provenance is not None:
        names = provenance.findall(qn("placeName"))
        modern_names = [n for n in names if n.get("type") in
                         (None, "modern", "modern_region")]
        if modern_names:
            out["modern_place"] = _text(modern_names[0]) or None
        if out["region"] is None:
            region_names = [n for n in names if n.get("type") == "modern_region"]
            if region_names:
                out["region"] = _text(region_names[0]) or None
    return out


def extract_languages(tei_root, edition_divs) -> list[str]:
    langs = set()
    for div in edition_divs:
        lang = div.get(f"{{{NS['xml']}}}lang") or div.get("xml:lang")
        if lang:
            langs.add(lang)
    if not langs:
        for ms_contents in tei_root.iter(qn("textLang")):
            main = ms_contents.get("mainLang")
            if main:
                langs.add(main)
    return sorted(langs)


def extract_idnos(tei_root) -> dict:
    out = {"tm_id": None, "hgv_id": None, "edh_id": None, "edr_id": None,
           "edcs_id": None}
    for idno in tei_root.iter(qn("idno")):
        t = idno.get("type", "")
        val = _text(idno)
        if not val:
            continue
        if t == "TM":
            out["tm_id"] = _parse_year(val)
        elif t == "HGV":
            out["hgv_id"] = _parse_year(val)
        elif t == "EDH" and val:
            out["edh_id"] = val
        elif t == "EDR" and val:
            out["edr_id"] = val
        elif t == "EDCS" and val:
            out["edcs_id"] = val
        elif t == "localID" and out["edh_id"] is None and val.startswith("HD"):
            out["edh_id"] = val
        elif t == "localID" and out["edr_id"] is None and val.startswith("EDR"):
            out["edr_id"] = val
    return out


def extract_title(tei_root) -> Optional[str]:
    title = _first(tei_root.findall(f".//{qn('titleStmt')}/{qn('title')}"))
    return _text(title) or None


def extract_object_type(tei_root) -> Optional[str]:
    obj = _first(list(tei_root.iter(qn("objectType"))))
    return _text(obj) or None


def extract_material(tei_root) -> Optional[str]:
    mat = _first(list(tei_root.iter(qn("material"))))
    return _text(mat) or None


def edition_divs(tei_root):
    body = tei_root.find(f".//{qn('text')}/{qn('body')}")
    if body is None:
        return []
    return [d for d in body.findall(qn("div")) if d.get("type") == "edition"]


def merge_hgv(record: dict, hgv_root) -> None:
    """Fill date/findspot/title from an HGV metadata record (papyri.info
    DDbDP editions carry no date or place themselves)."""
    history = hgv_root.find(f".//{qn('history')}")
    nb, na = extract_date(history)
    if nb is not None or na is not None:
        record["date_not_before"] = nb
        record["date_not_after"] = na
    findspot = extract_findspot(history)
    if any(findspot.values()):
        record["findspot"] = findspot
    if record.get("title") is None:
        record["title"] = extract_title(hgv_root)
    mat = extract_material(hgv_root)
    if mat:
        record["material"] = mat


# ---------------------------------------------------------------------------
# Top-level conversion
# ---------------------------------------------------------------------------

def convert_file(path: str, source: str, hgv_root=None) -> Optional[dict]:
    try:
        tree = etree.parse(path)
    except etree.XMLSyntaxError as exc:
        print(f"SKIP (XML parse error) {path}: {exc}", file=sys.stderr)
        return None
    root = tree.getroot()

    idnos = extract_idnos(root)
    divs = edition_divs(root)
    languages = extract_languages(root, divs)

    all_lines: list[dict] = []
    gap_count = 0
    supplied_chars = 0
    total_chars = 0
    for div in divs:
        subtype = div.get("subtype")
        if subtype and "lemmatiz" in subtype:
            # A second, pre-lemmatized edition div (I.Sicily): skip, we
            # derive our own plain text instead of trusting a foreign
            # lemmatization scheme.
            continue
        conv = EpidocConverter()
        lines = conv.convert_edition(div)
        all_lines.extend(lines)
        gap_count += conv.gap_count
        supplied_chars += conv.supplied_chars
        total_chars += conv.total_chars

    filename = os.path.basename(path)
    local_id = os.path.splitext(filename)[0]
    record = {
        "id": f"{source}:{local_id}",
        "source": source,
        "tm_id": idnos["tm_id"],
        "hgv_id": idnos["hgv_id"],
        "edh_id": idnos["edh_id"],
        "edr_id": idnos["edr_id"],
        "edcs_id": idnos["edcs_id"],
        "languages": languages,
        "bilingual": len(languages) > 1,
        "title": extract_title(root),
        "object_type": extract_object_type(root),
        "material": extract_material(root),
        "date_not_before": None,
        "date_not_after": None,
        "findspot": {"ancient_place": None, "modern_place": None,
                      "region": None, "pleiades_id": None},
        "lines": all_lines,
        "supplied_chars": supplied_chars,
        "total_chars": total_chars,
        "gap_count": gap_count,
        "supplied_share": (supplied_chars / total_chars) if total_chars else 0.0,
    }

    history = root.find(f".//{qn('history')}")
    nb, na = extract_date(history)
    record["date_not_before"] = nb
    record["date_not_after"] = na
    record["findspot"] = extract_findspot(history)

    if hgv_root is not None:
        merge_hgv(record, hgv_root)

    return record


def iter_xml_files(input_dir: str) -> Iterable[str]:
    for dirpath, _dirnames, filenames in os.walk(input_dir):
        for name in sorted(filenames):
            if name.endswith(".xml"):
                yield os.path.join(dirpath, name)


def build_hgv_index(meta_dir: str) -> dict:
    """Map local id (filename stem) -> parsed HGV root, for the papyri
    source where DDbDP and HGV_meta_EpiDoc share the same filename stem."""
    index = {}
    for path in iter_xml_files(meta_dir):
        stem = os.path.splitext(os.path.basename(path))[0]
        index[stem] = path
    return index


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True,
                     choices=["edh", "isicily", "papyri", "edr"])
    ap.add_argument("--input-dir", required=True)
    ap.add_argument("--meta-dir", default=None,
                     help="HGV_meta_EpiDoc folder, required for --source papyri")
    ap.add_argument("--output", required=True)
    ap.add_argument("--limit", type=int, default=None,
                     help="stop after N documents (for sampling/testing)")
    args = ap.parse_args(argv)

    if args.source == "papyri" and not args.meta_dir:
        print("ERROR: --source papyri requires --meta-dir", file=sys.stderr)
        return 2

    hgv_index = {}
    if args.meta_dir:
        hgv_index = build_hgv_index(args.meta_dir)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)

    count = 0
    skipped = 0
    with open(args.output, "w", encoding="utf-8") as out:
        for path in iter_xml_files(args.input_dir):
            if args.limit is not None and count >= args.limit:
                break
            hgv_root = None
            if hgv_index:
                stem = os.path.splitext(os.path.basename(path))[0]
                hgv_path = hgv_index.get(stem)
                if hgv_path:
                    try:
                        hgv_root = etree.parse(hgv_path).getroot()
                    except etree.XMLSyntaxError:
                        hgv_root = None
            record = convert_file(path, args.source, hgv_root=hgv_root)
            if record is None:
                skipped += 1
                continue
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1

    print(f"{args.source}: wrote {count} documents to {args.output} "
          f"({skipped} skipped on parse error)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
