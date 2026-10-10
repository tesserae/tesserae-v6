#!/usr/bin/env python3
"""Convert OCRE and CRRO coin-type records (nomisma.org SPARQL export) to the
documents collection's intermediate JSONL, one document per coin type.

PROTOTYPE (2026-10-09). Nothing here touches the live index or /var/www.

Input
-----
The type-level triples fetched from the public nomisma.org SPARQL endpoint:
one JSON object per line, ``{"t": type URI, "p": predicate, "o": {"v": value,
"l": language}}`` for type-level triples and the same plus ``"side":
"obverse" | "reverse"`` for triples that belong to a side (legend,
description, portrait). Licence of the data: ODbL 1.0.

Optional reference files (same folder fetched with the same endpoint) turn
nomisma ids into labels and mints into Pleiades ids:

  mints.jsonl   {"u": mint URI, "label": ..., "match": pleiades URL or absent}
  labels.jsonl  {"u": URI, "label": ...}   denominations, materials, mints
  people.jsonl  {"u": URI, "label": ...}   emperors, moneyers, offices

Output record
-------------
The EpiDoc converter's shape (see ``epidoc_convert.py``) so the unchanged
``write_document_tess.py`` and ``build_documents_index.py`` can index it, plus
coin-specific fields:

  id                 "ocre:<local id>" or "crro:<local id>"
  source             "ocre" | "crro"          (the .tess citation prefix)
  kind               "coin"
  bucket             "ocre" | "crro"
  languages          ["la"] (Latin script), ["grc"] (Greek only), or both
  lines              one line per non-empty legend, obverse then reverse;
                     ``restored_flags`` marks letters the catalogue puts in
                     square brackets (restored from other specimens)
  findspot           ancient_place = mint label, pleiades_id from nomisma
  portrait, region   obverse portrait (label) and the export's region, if any
  authority          emperor(s) (OCRE) or issuer/moneyer(s) (CRRO)
  denomination, material, mint{uri,label,pleiades_id}
  obverse_legend, reverse_legend            raw, as catalogued
  obverse_description, reverse_description  English, kept separate
  type_uri, source_url, principal_edition, licence_name, licence_url
  legend_note        set when a legend field was editorial commentary
                     ("APOLLI CO or APOLLI CON ... sometimes with A")
                     and so left out of ``lines``

Legend normalisation (the text that is indexed)
-----------------------------------------------
Nothing is expanded: IMP, AVG, P M TR P stay as catalogued. A die
line-break hyphen inside a word is joined (``THEODO-SIVS`` -> ``THEODOSIVS``)
and one between two whole words is read as a space (``GLORIA-ROMANORVM`` ->
``GLORIA ROMANORVM``), decided from the catalogue's own vocabulary. Word
separators (interpunct, bullet, ring, colon, asterisk, underscore, slash,
pipe) become spaces, square brackets are removed and their contents flagged
restored, parenthetical editorial notes ("(rev. N)") are removed, symbols
that are not letters (chi-rho, arrows, ellipsis, replacement characters) are
dropped, and whitespace is collapsed. Dots are kept.

Usage
-----
    python -I scripts/coins/convert_ocre.py \\
        --ocre ~/tesserae-backups/sources/archaeology/ocre/ocre_types.jsonl \\
        --crro ~/tesserae-backups/sources/archaeology/crro/crro_types.jsonl \\
        --refs ~/tesserae-backups/sources/archaeology/nomisma_refs \\
        --output /path/to/coins.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

NMO = "http://nomisma.org/ontology#"
DCT = "http://purl.org/dc/terms/"
SKOS = "http://www.w3.org/2004/02/skos/core#"

LICENCE_NAME = "Open Data Commons Open Database License 1.0 (ODbL)"
LICENCE_URL = "https://opendatacommons.org/licenses/odbl/1.0/"

DATASETS = {
    "ocre": {"name": "Online Coins of the Roman Empire (OCRE)",
             "url": "https://numismatics.org/ocre/"},
    "crro": {"name": "Coinage of the Roman Republic Online (CRRO)",
             "url": "https://numismatics.org/crro/"},
}

_SEPARATORS = "·•˙●:*_/|․‧"
_SEP_RE = re.compile("[" + re.escape(_SEPARATORS) + "]")
_PAREN_RE = re.compile(r"\(([^)]*)\)")
_WS_RE = re.compile(r"\s+")
# Letters of Latin or Greek script, plus the dot and the bracket markers
# the normaliser handles itself.
_KEEP_PUNCT = {".", "[", "]", " "}


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

def parse_year(value):
    """nomisma gives signed zero-padded years: "-0025", "0270", "+0014".
    Returns an int (negative = BCE) or None for anything else."""
    if value is None:
        return None
    s = str(value).strip()
    m = re.fullmatch(r"([+-]?)(\d{1,4})", s)
    if not m:
        return None
    y = int(m.group(2))
    return -y if m.group(1) == "-" else y


def date_range(start, end):
    """(not_before, not_after) with the two ends put in order. A missing end
    takes the other end's value (a single-year type)."""
    a, b = parse_year(start), parse_year(end)
    if a is None and b is None:
        return None, None
    if a is None:
        a = b
    if b is None:
        b = a
    return (a, b) if a <= b else (b, a)


# --------------------------------------------------------------------------
# Legends
# --------------------------------------------------------------------------

def _is_letter(ch):
    return unicodedata.category(ch).startswith("L")


def _letters(piece):
    return "".join(ch for ch in piece if _is_letter(ch))


def _resolve_hyphens(s, vocab):
    """A hyphen marks a die line break: inside a word (THEODO-SIVS) or
    between two words (GLORIA-ROMANORVM). ``vocab`` is a Counter of the
    hyphen-free tokens of the same catalogue. A joined form that occurs in
    it wins; failing that, pieces that are each a common whole word are
    kept apart; otherwise the pieces are joined. With no vocabulary every
    hyphenated token is joined."""
    def fix(m):
        tok = m.group(0)
        pieces = [x for x in tok.split("-") if x]
        if len(pieces) < 2:
            return "".join(pieces)
        joined = "".join(pieces)
        if not vocab:
            return joined
        key = _letters(joined)
        if vocab.get(key, 0) >= 2:
            return joined
        keys = [_letters(x) for x in pieces]
        if all(len(k) >= 1 and vocab.get(k, 0) >= 20 for k in keys):
            return " ".join(pieces)
        return joined
    return re.sub(r"\S*-\S*", fix, s)


def build_vocab(legends):
    """Counter of whole-word tokens (letters only) from legends, ignoring
    every token that contains a hyphen."""
    from collections import Counter
    v = Counter()
    for leg in legends:
        for tok in leg.split():
            if "-" in tok:
                continue
            k = _letters(tok)
            if k:
                v[k] += 1
    return v


def normalise_legend(raw, vocab=None):
    """Return (text, restored_flags, note).

    ``text`` is the indexable legend (may be empty). ``restored_flags`` has
    one bool per character of ``text``. ``note`` is "commentary" when the
    field is editorial prose rather than an inscription, else None."""
    if raw is None:
        return "", [], None
    s = unicodedata.normalize("NFC", raw).replace("\xa0", " ")
    # "A or B or C" lists die variants (different line-break positions):
    # the first is indexed, the raw field keeps them all
    s = re.split(r"\s+or\s+", s, maxsplit=1)[0]
    # parenthetical editorial notes: "(rev. N)", "(inv. CBV)" -- any
    # parenthesis holding lower-case letters or a dot-abbreviated word
    def _paren(m):
        inner = m.group(1)
        return "" if re.search(r"[a-z]", inner) else inner
    s = _PAREN_RE.sub(_paren, s)
    s = s.replace("(", "").replace(")", "")
    # a word of lower-case letters outside brackets means the field is
    # catalogue prose, not a legend
    outside = re.sub(r"\[[^\]]*\]", "", s)
    lower_words = re.findall(r"\b[a-z]{2,}\b", outside)
    if len(lower_words) > 1:
        return "", [], "commentary"
    if lower_words:
        # one stray lower-case word ("round", "sic") is a note, not legend
        s = re.sub(r"\b[a-z]{2,}\b", " ", s)
    s = _resolve_hyphens(s, vocab)
    s = _SEP_RE.sub(" ", s)
    out_chars, flags = [], []
    inside = False
    for ch in s:
        if ch == "[":
            inside = True
            continue
        if ch == "]":
            inside = False
            continue
        if _is_letter(ch) or ch == "." or ch == " ":
            out_chars.append(ch)
            flags.append(inside and ch != " ")
        elif unicodedata.category(ch).startswith("M"):
            out_chars.append(ch)
            flags.append(inside)
        elif ch.isdigit():
            out_chars.append(ch)
            flags.append(inside)
        else:
            # symbols, arrows, ellipsis, replacement character: dropped
            # without splitting the word they sit in
            continue
    text = "".join(out_chars)
    # collapse whitespace while keeping the flags aligned
    new_chars, new_flags, prev_space = [], [], True
    for ch, fl in zip(text, flags):
        if ch == " ":
            if prev_space:
                continue
            prev_space = True
        else:
            prev_space = False
        new_chars.append(ch)
        new_flags.append(fl)
    while new_chars and new_chars[-1] == " ":
        new_chars.pop()
        new_flags.pop()
    return "".join(new_chars), new_flags, None


def legend_languages(texts):
    """["la"], ["grc"] or ["la", "grc"] from the scripts present."""
    latin = greek = False
    for t in texts:
        for ch in t:
            if not _is_letter(ch):
                continue
            name = unicodedata.name(ch, "")
            if name.startswith("GREEK"):
                greek = True
            elif name.startswith("LATIN"):
                latin = True
    if greek and not latin:
        return ["grc"]
    if greek and latin:
        return ["la", "grc"]
    return ["la"]


# --------------------------------------------------------------------------
# Triples -> records
# --------------------------------------------------------------------------

def slug(uri):
    return uri.rstrip("/").rsplit("/", 1)[-1]


def pretty(uri):
    return slug(uri).replace("_", " ").title()


def load_refs(refs_dir):
    """Return (labels, mint_pleiades). Missing files give empty maps."""
    labels, pleiades = {}, {}
    if not refs_dir:
        return labels, pleiades
    for name in ("labels.jsonl", "people.jsonl", "mints.jsonl"):
        p = os.path.join(refs_dir, name)
        if not os.path.exists(p):
            continue
        with open(p, encoding="utf-8") as f:
            for line in f:
                d = json.loads(line)
                labels.setdefault(d["u"], d["label"])
                m = d.get("match")
                if m and "pleiades.stoa.org/places/" in m:
                    pleiades.setdefault(d["u"], m.rstrip("/").rsplit("/", 1)[-1])
    return labels, pleiades


def group_triples(path):
    """Stream the triples file into {type URI: {"props": {p: [values]},
    "sides": {side: {p: [values]}}}}. The file is a few hundred MB for OCRE
    so records are held as compact tuples."""
    types = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            t = d.get("t")
            if not t:
                continue
            rec = types.get(t)
            if rec is None:
                rec = types[t] = {"props": defaultdict(list),
                                  "sides": {"obverse": defaultdict(list),
                                            "reverse": defaultdict(list)}}
            o = d.get("o") or {}
            val = (o.get("v"), o.get("l"))
            side = d.get("side")
            if side in ("obverse", "reverse"):
                rec["sides"][side][d["p"]].append(val)
            else:
                rec["props"][d["p"]].append(val)
    return types


def _uniq(seq):
    seen, out = set(), []
    for x in seq:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _label(uri, labels):
    return labels.get(uri) or pretty(uri)


def convert_type(uri, rec, dataset, labels, mint_pleiades, vocab=None):
    """One type -> output record (dict)."""
    props, sides = rec["props"], rec["sides"]
    local = uri.split("/id/", 1)[-1]
    first = lambda p: next((v for v, _ in props.get(NMO + p, []) if v), None)  # noqa: E731
    allv = lambda p: _uniq([v for v, _ in props.get(NMO + p, [])])  # noqa: E731

    pref = next((v for v, l in props.get(SKOS + "prefLabel", []) if l in (None, "en")), None)

    nb, na = date_range(first("hasStartDate"), first("hasEndDate"))

    mint_uri = first("hasMint")
    mint = None
    if mint_uri:
        mint = {"uri": mint_uri, "label": _label(mint_uri, labels),
                "pleiades_id": mint_pleiades.get(mint_uri)}

    auth_uris = allv("hasAuthority") or allv("hasIssuer")
    # moneyers sit under hasIssuer for the Republic; OCRE types may have both
    issuers = allv("hasIssuer")
    authority = "; ".join(_label(u, labels) for u in auth_uris
                          if slug(u) != "anonymous") or (
        "anonymous" if "http://nomisma.org/id/anonymous" in auth_uris else None)
    issuer = "; ".join(_label(u, labels) for u in issuers
                       if slug(u) != "anonymous") or None

    denom_uri, mat_uri = first("hasDenomination"), first("hasMaterial")
    denomination = _label(denom_uri, labels) if denom_uri else None
    material = _label(mat_uri, labels) if mat_uri else None

    # who is shown on the obverse (an emperor, a deity), and the region the
    # export gives for some types
    portrait = "; ".join(_label(u, labels) for u in _uniq(
        [v for v, _ in sides["obverse"].get(NMO + "hasPortrait", [])])) or None
    region = "; ".join(_label(u, labels) for u in allv("hasRegion")
                       if slug(u) != "uncertain_value") or None

    legend_raw, descr, lines = {}, {}, []
    notes = []
    all_texts = []
    for side in ("obverse", "reverse"):
        sp = sides[side]
        legs = _uniq([v for v, _ in sp.get(NMO + "hasLegend", [])])
        legend_raw[side] = " | ".join(legs) if legs else None
        ds = _uniq([v for v, l in sp.get(DCT + "description", []) if l in (None, "en")])
        descr[side] = " or ".join(ds) if ds else None
        # index the first legend variant only; the raw field keeps them all
        if legs:
            text, flags, note = normalise_legend(legs[0], vocab)
            if note:
                notes.append(f"{side}: {note}")
            if text:
                lines.append({"n": side[0].upper(), "diplomatic": legs[0],
                              "expanded": text, "text": text,
                              "restored_flags": flags})
                all_texts.append(text)

    total = sum(len(l["text"]) for l in lines)
    supplied = sum(sum(l["restored_flags"]) for l in lines)

    rec_out = {
        "id": f"{dataset}:{local}",
        "source": dataset,
        "kind": "coin",
        "bucket": dataset,
        "tm_id": None, "hgv_id": None, "edh_id": None, "edr_id": None, "edcs_id": None,
        "languages": legend_languages(all_texts),
        "bilingual": False,
        "title": pref,
        "object_type": "coin",
        "material": material,
        "date_not_before": nb,
        "date_not_after": na,
        "findspot": {"ancient_place": mint["label"] if mint else None,
                     "modern_place": None, "region": None,
                     "pleiades_id": mint["pleiades_id"] if mint else None},
        "mint": mint,
        "authority": authority,
        "issuer": issuer,
        "portrait": portrait,
        "region": region,
        "denomination": denomination,
        "obverse_legend": legend_raw["obverse"],
        "reverse_legend": legend_raw["reverse"],
        "obverse_description": descr["obverse"],
        "reverse_description": descr["reverse"],
        "type_uri": uri,
        "source_url": uri,
        "principal_edition": pref,
        "source_name": DATASETS[dataset]["name"],
        "licence_name": LICENCE_NAME,
        "licence_url": LICENCE_URL,
        "legend_note": "; ".join(notes) or None,
        "lines": lines,
        "text": " / ".join(l["text"] for l in lines),
        "supplied_chars": supplied,
        "total_chars": total,
        "gap_count": 0,
        "supplied_share": (supplied / total) if total else 0.0,
    }
    return rec_out


def convert_file(path, dataset, labels, mint_pleiades):
    types = group_triples(path)
    vocab = build_vocab(v for rec in types.values()
                        for side in rec["sides"].values()
                        for v, _ in side.get(NMO + "hasLegend", []) if v)
    for uri in sorted(types):
        yield convert_type(uri, types[uri], dataset, labels, mint_pleiades, vocab)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ocre")
    ap.add_argument("--crro")
    ap.add_argument("--refs", help="folder with mints.jsonl, labels.jsonl, people.jsonl")
    ap.add_argument("--output", required=True)
    ap.add_argument("--stats-out")
    args = ap.parse_args(argv)
    if not (args.ocre or args.crro):
        ap.error("give --ocre and/or --crro")

    labels, mint_pleiades = load_refs(args.refs)
    stats = defaultdict(Counter)
    with open(args.output, "w", encoding="utf-8") as out:
        for dataset, path in (("ocre", args.ocre), ("crro", args.crro)):
            if not path:
                continue
            for r in convert_file(path, dataset, labels, mint_pleiades):
                s = stats[dataset]
                s["types"] += 1
                s["with_legend_text"] += bool(r["lines"])
                s["with_obverse_description"] += bool(r["obverse_description"])
                s["with_reverse_description"] += bool(r["reverse_description"])
                s["with_both_descriptions"] += bool(r["obverse_description"] and r["reverse_description"])
                s["with_any_description"] += bool(r["obverse_description"] or r["reverse_description"])
                s["with_mint"] += bool(r["mint"])
                s["with_pleiades_id"] += bool(r["findspot"]["pleiades_id"])
                s["with_date"] += r["date_not_before"] is not None
                s["with_authority"] += bool(r["authority"])
                s["legend_commentary"] += bool(r["legend_note"])
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
    report = {k: dict(v) for k, v in stats.items()}
    txt = json.dumps(report, indent=2)
    if args.stats_out:
        with open(args.stats_out, "w", encoding="utf-8") as f:
            f.write(txt)
    print(txt, file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
