#!/usr/bin/env python3
"""Convert Attic Inscriptions Online (AIO) records into the documents pipeline.

AIO (https://www.atticinscriptions.com/) gave permission on 2026-10-20 for
its translations and Greek texts to be included under its Creative Commons
license. Its REST API returns, for each inscription, the translation and (for
some) the Greek text as Base64-encoded EpiDoc XML. The EpiDoc carries no TEI
namespace, so each tag is moved into the TEI namespace here and the text is
then read with the same converter the other EpiDoc sources use
(`epidoc_convert.EpidocConverter`), so restorations and abbreviations display
the same way. Editorial notes in the Greek (<note>) are dropped, because they
hold dates and footnote numbers that are not part of the inscribed text.

The API carries no date, monument type or findspot, so the public HTML page of
each inscription that has a Greek text is read for them (`aio_fetch.py
--html-for-greek` stores those pages).

Document ids are `aio:<sourcevolume>_<id>` (for example `aio:IGII2_18`). The
slash form of AIO's own path (`IGII2/18`) cannot be used because the document
page requests `/api/documents/<id>` with the id percent-encoded, and a
percent-encoded slash does not reach the route.

The principal edition is the edition number as AIO's own page shows it in the
inscription heading (`<span id="ins_source">`), with italics and superscripts
flattened ("IG II2 18", "IG II3 1 1000", "SEG 12.147"), never the AIO number.

Usage:
    aio_convert.py RAW_DIR HTML_DIR OUT_JSONL [--report OUT_JSON]
"""
from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import re
import sys
import unicodedata
from urllib.parse import unquote

from lxml import etree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from epidoc_convert import (  # noqa: E402
    EpidocConverter, join_lines, qn,
)

SOURCE = "aio"
SOURCE_NAME = "Attic Inscriptions Online"
LICENCE_NAME = "CC BY-SA 3.0"
LICENCE_URL = "https://creativecommons.org/licenses/by-sa/3.0/"
PAGE_URL = "https://www.atticinscriptions.com/inscription/{vol}/{ident}"

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_WS = re.compile(r"\s+")


def doc_id(vol: str, ident: str) -> str:
    return f"{SOURCE}:{vol}_{ident}"


def decode_epidoc(b64: str, notes: list | None = None):
    """Base64 EpiDoc to an lxml root, in the TEI namespace. Falls back to the
    recovering parser for the few malformed records, and says so in `notes`."""
    raw = base64.b64decode(b64)
    try:
        root = etree.fromstring(raw)
    except etree.XMLSyntaxError as exc:
        if notes is not None:
            notes.append(f"recovered malformed XML: {str(exc)[:80]}")
        root = etree.fromstring(raw, etree.XMLParser(recover=True))
    for el in root.iter():
        if isinstance(el.tag, str):
            el.tag = qn(etree.QName(el).localname)
    return root


def _drop_keep_tail(el) -> None:
    parent = el.getparent()
    if parent is None:
        return
    tail = el.tail
    prev = el.getprevious()
    if tail:
        if prev is not None:
            prev.tail = (prev.tail or "") + tail
        else:
            parent.text = (parent.text or "") + tail
    parent.remove(el)


def _wrap_supplied_text(root) -> None:
    """EpidocConverter writes a <supplied>'s own text AFTER its children, which
    scrambles the order when the text comes first and a <lb/> follows inside.
    Move the leading text into a <hi> first child so the order is kept."""
    for sup in list(root.iter(qn("supplied"))):
        if sup.text and len(sup):
            hi = etree.Element(qn("hi"))
            hi.text = sup.text
            sup.text = None
            sup.insert(0, hi)


def join_hyphenated_lines(lines: list) -> list:
    """A line of AIO's own Greek that ends in a plain hyphen written straight after a letter, with the next
    line starting with a letter, is a word broken at the line end where the EpiDoc has no
    <lb break="no"/> (AIO 2734 "προθυσαμε-" then "νους"). The hyphen is taken off and the next line is
    marked as continuing the word. A hyphen before a gap (the line text ends in the gap sign), after a
    space or before a line that starts with a gap stays as it is: there the word is cut off on the stone."""
    kept = [ln for ln in lines if ln.get("text")]
    for cur, nxt in zip(kept, kept[1:]):
        t = cur["text"]
        if (t.endswith("-") and len(t) > 1 and not t[-2].isspace() and _ends_in_greek_letter(t[:-1])
                and _GREEK.match(nxt["text"].lstrip("([")[:1] or " ")):
            cur["text"] = t[:-1]
            cur["restored_flags"] = list(cur.get("restored_flags") or [])[:len(t) - 1]
            for k in ("diplomatic", "expanded"):
                if cur.get(k, "").endswith("-"):
                    cur[k] = cur[k][:-1]
            nxt["joins_previous"] = True
    return lines


def greek_lines(greek_b64: str, notes: list | None = None):
    """(lines, languages, counters) from the Greek EpiDoc, using the shared
    converter."""
    root = decode_epidoc(greek_b64, notes)
    for el in list(root.iter(qn("note"))):
        _drop_keep_tail(el)
    _wrap_supplied_text(root)
    divs = [d for d in root.iter(qn("div")) if d.get("type") == "edition"]
    langs = sorted({d.get(XML_LANG) for d in divs if d.get(XML_LANG)})
    lines, gaps, supplied, total = [], 0, 0, 0
    for div in divs:
        conv = EpidocConverter()
        lines.extend(conv.convert_edition(div))
        gaps += conv.gap_count
        supplied += conv.supplied_chars
        total += conv.total_chars
    lines = join_hyphenated_lines(lines)
    return lines, langs, {"gap_count": gaps, "supplied_chars": supplied, "total_chars": total}


def _clean(s: str) -> str:
    return _WS.sub(" ", s).strip()


def translation_text(tr_b64: str, notes: list | None = None) -> str:
    """AIO's English translation as plain running text. Footnote numbers and
    tribe tags are dropped, inline notes kept in parentheses, restored text in
    square brackets, gaps as ". . ."."""
    root = decode_epidoc(tr_b64, notes)
    out: list[str] = []

    def walk(el):
        tag = etree.QName(el).localname if isinstance(el.tag, str) else None
        if tag is None:
            return
        if tag == "note":
            kind = el.get("type")
            if kind == "inline":
                t = _clean("".join(el.itertext()))
                if t:
                    out.append(t if t.startswith("(") else f"({t})")
            return
        if tag == "gap":
            out.append(" \x00 ")
            return
        if tag in ("milestone", "space"):
            return
        if tag == "lb":
            out.append(" ")
            return
        if tag == "supplied":
            out.append("[")
            if el.text:
                out.append(el.text)
            for ch in el:
                walk(ch)
                if ch.tail:
                    out.append(ch.tail)
            out.append("]")
            return
        if el.text:
            out.append(el.text)
        for ch in el:
            walk(ch)
            if ch.tail:
                out.append(ch.tail)
        if tag == "seg":
            out.append(" ")  # AIO sets neighboring alternatives as adjacent segs

    for div in root.iter(qn("div")):
        if div.get("type") == "translation":
            walk(div)
            break
    else:
        walk(root)
    text = _clean("".join(out))
    text = re.sub(r"\s+([,.;:?!)\]])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    return _clean(text.replace("\x00", ". . ."))


def strip_tags(s: str) -> str:
    return _clean(re.sub(r"<[^>]+>", "", s))


def translators_of(rec: dict) -> str:
    names = [_clean(n) for n in rec.get("translators") or [] if _clean(n)]
    if len(names) > 2:
        return ", ".join(names[:-1]) + " and " + names[-1]
    return " and ".join(names)


# ---------------------------------------------------------------------------
# The public HTML page
# ---------------------------------------------------------------------------

def _html_text(fragment: str) -> str:
    import html as _html
    return _clean(_html.unescape(re.sub(r"<[^>]+>", " ", fragment)))


def parse_page(html_text: str) -> dict:
    """Edition number as displayed, date text, types and findspot."""
    out = {"edition": None, "references": [], "date_text": None, "monument_type": None,
           "inscription_types": [], "findspot": None, "pleiades_id": None,
           "original_location": None}
    m = re.search(r'<span id="ins_source">(.*?)</span>', html_text, re.S)
    if m:
        frag = re.sub(r"</?i>", "", m.group(1))
        frag = re.sub(r"<sup>(.*?)</sup>", r"\1", frag)
        out["edition"] = _html_text(frag) or None
    for rm in re.finditer(r'<div class="ins_alt_source"[^>]*>(.*?)</div>', html_text, re.S):
        am = re.search(r'<a [^>]*href="/browse/bysource/[^"]*">(.*?)</a>', rm.group(1), re.S)
        if am:
            frag = re.sub(r"</?i>", "", am.group(1))
            frag = re.sub(r"<sup>(.*?)</sup>", r"\1", frag)
            out["references"].append(_html_text(frag).replace(" (Translated text)", ""))
    m = re.search(r'<span id="ins_date">\s*Date:\s*(.*?)</span>', html_text, re.S)
    if m:
        out["date_text"] = _html_text(m.group(1)) or None
    m = re.search(r"Monument type:\s*(.*?)</div>", html_text, re.S)
    if m:
        out["monument_type"] = _html_text(m.group(1)) or None
    m = re.search(r"Inscription type:\s*(.*?)</div>", html_text, re.S)
    if m:
        out["inscription_types"] = [t.strip() for t in
                                    _html_text(m.group(1)).split(",") if t.strip()]
    m = re.search(r"Original location:\s*(.*?)</div>", html_text, re.S)
    if m:
        out["original_location"] = _html_text(m.group(1)) or None
    m = re.search(r"Findspot:\s*(.*?)(?:\(|<br|</div>)", html_text, re.S)
    if m:
        txt = _html_text(m.group(1))
        out["findspot"] = txt or None
        pm = re.search(r"pleiades\.stoa\.org/places/(\d+)", m.group(0))
        if pm:
            out["pleiades_id"] = pm.group(1)
    if out["pleiades_id"] is None:
        m = re.search(r"Findspot:.*?pleiades\.stoa\.org/places/(\d+)", html_text, re.S)
        if m:
            out["pleiades_id"] = m.group(1)
    return out


_ROMAN = {"i": 1, "v": 5, "x": 10}


def _roman(s: str) -> int | None:
    s = s.lower()
    if not s or any(c not in _ROMAN for c in s):
        return None
    total = 0
    for i, c in enumerate(s):
        v = _ROMAN[c]
        total += -v if i + 1 < len(s) and _ROMAN[s[i + 1]] > v else v
    return total


def _year_tokens(text: str) -> list[int]:
    """Years from tokens such as 394/3, 403/2, 145/6, 410, completing the
    short second part of a slash pair."""
    years = []
    for a, b in re.findall(r"(\d{1,4})(?:/(\d{1,4}))?", text):
        a_i = int(a)
        years.append(a_i)
        if b:
            if len(b) < len(a):
                b_i = int(a[:len(a) - len(b)] + b)
            else:
                b_i = int(b)
            years.append(b_i)
    return years


_QUAL = {"early": (0, 33), "in.": (0, 33), "mid": (33, 66), "med.": (33, 66),
         "late": (66, 99), "ex.": (66, 99), "first half": (0, 50),
         "second half": (50, 99), "": (0, 99)}


def _century_range(n: int, qual: str, sign: int):
    """(earliest, latest) signed years of the n-th century, narrowed by an
    early/mid/late/half qualifier."""
    lo, hi = _QUAL[qual]
    if sign < 0:   # century n BC runs from year 100n BC down to year 100(n-1)+1 BC
        return -(n * 100 - lo), -(n * 100 - hi)
    return (n - 1) * 100 + 1 + lo, (n - 1) * 100 + 1 + hi


def _parse_half(low: str, sign: int):
    """(earliest, latest) signed years for one era-less piece of a date."""
    qual_re = r"(early|mid|late|first half|second half|ex\.|in\.|med\.)"
    cents = []
    for q, n in re.findall(qual_re + r"?\s*(\d+)(?:st|nd|rd|th)(?!\s+half)(?:\s*cent\w*\.?)?(?=[\s\-\u2013/,;]|$)", low):
        cents.append((int(n), q))
    if not cents:
        for q, rn in re.findall(qual_re + r"?\s*\b([ivx]+)\b(?!\w)", low):
            n = _roman(rn)
            if n:
                cents.append((n, q))
    if cents:
        rng = [_century_range(n, q, sign) for n, q in cents]
        return min(r[0] for r in rng), max(r[1] for r in rng)
    yrs = _year_tokens(re.sub(r"\b[ivx]+\b", " ", low))
    if not yrs:
        return None, None
    if sign < 0:
        return -max(yrs), -min(yrs)
    return min(yrs), max(yrs)


def parse_date(text: str | None):
    """(not_before, not_after) in the signed-year convention (negative = BC)
    or (None, None) when the wording is not understood (several dated parts
    such as "A: ... B: ...", or no year at all). Handles year numbers, ranges,
    "after"/"before", "ca.", centuries in Roman or ordinal form with
    early/mid/late/half, and ranges that cross from BC to AD."""
    if not text:
        return None, None
    low = text.strip().lower()
    if re.search(r"\b[a-d]:\s|\b(i|ii|iii):\s|;", low):
        return None, None
    has_bc = bool(re.search(r"\bbc\b|\bb\.c\.", low))
    has_ad = bool(re.search(r"\bad\b|\ba\.d\.", low))
    if not (has_bc or has_ad):
        return None, None
    after = bool(re.search(r"\bafter\b", low))
    before = bool(re.search(r"\bbefore\b", low))
    if has_bc and has_ad:
        parts = re.split(r"\s*[\u2013\u2014-]\s*", low, maxsplit=1)
        if len(parts) != 2:
            return None, None
        p1, p2 = parts
        if not (re.search(r"\bbc\b", p1) and re.search(r"\bad\b", p2)):
            return None, None
        nb, _ = _parse_half(re.sub(r"\b(bc|ad)\b", " ", p1), -1)
        _, na = _parse_half(re.sub(r"\b(bc|ad)\b", " ", p2), 1)
        return nb, na
    sign = -1 if has_bc else 1
    body = re.sub(r"\b(bc|ad|b\.c\.|a\.d\.)\b", " ", low)
    lo, hi = _parse_half(body, sign)
    if lo is None:
        return None, None
    if after:
        return lo, None
    if before:
        return None, hi
    return lo, hi


# ---------------------------------------------------------------------------
# Record assembly
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Greek from the Berlin IG digital edition (CC BY 4.0), for AIO inscriptions
# that have a translation but no Greek of their own
# ---------------------------------------------------------------------------

BBAW_NAME = "Inscriptiones Graecae, Berlin-Brandenburg Academy of Sciences and Humanities"
BBAW_LICENCE_NAME = "CC BY 4.0"
BBAW_LICENCE_URL = "https://creativecommons.org/licenses/by/4.0/"
BBAW_LICENCE_TARGET = "https://creativecommons.org/licenses/by/4.0/legalcode"
BBAW_PAGE = "https://telota.bbaw.de/ig/digitale-edition/inschrift/"
GAP = "\u2588"   # the placeholder epidoc_convert uses for a gap
_GREEK = re.compile(r"[\u0370-\u03ff\u1f00-\u1fff]")
_LINE_MARK = object()


def bbaw_parse(xml_bytes: bytes, notes: list | None = None):
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        if notes is not None:
            notes.append(f"recovered malformed XML: {str(exc)[:70]}")
        root = etree.fromstring(xml_bytes, etree.XMLParser(recover=True))
    return root


def bbaw_licence_ok(root) -> bool:
    lic = root.find(".//" + qn("licence"))
    return lic is not None and lic.get("target") == BBAW_LICENCE_TARGET


def bbaw_page_url(root) -> str | None:
    for idno in root.iter(qn("idno")):
        if idno.get("type") == "URI" and idno.text:
            from urllib.parse import quote
            return quote(idno.text.strip(), safe=":/,")
    return None


def _letters(token: str) -> int:
    """How many letters (base characters, not accents or breathings) a token holds."""
    return sum(1 for c in unicodedata.normalize("NFD", token) if c.isalpha())


def join_letterspaced(txt: str) -> str | None:
    """The word or words of a stone whose letters were set apart (the Berlin edition's letterspacing
    element, one letter per gap: "τ   α   ὐ   τ" for "ταὐτ"). A run of white space wider than the usual
    gap between letters is the space between words. Returns None when the text is not spaced out letter
    by letter (a line set in wide type but written in ordinary words), so the caller keeps it as it is.
    A letter with its accents is one letter, and a private-use mark between letters (the editors' sign
    for a vacant space) is not a letter and adds its gap to the neighbours' gap."""
    t = re.sub("[\ue000-\uf8ff]", "", txt)
    parts = re.split(r"(\s+)", t.strip())
    toks = [p for p in parts[0::2] if p]
    if len(toks) < 3 or not _GREEK.search(t):
        return None
    letters = [_letters(tk) for tk in toks if _GREEK.search(tk)]
    if not letters or sum(1 for n in letters if n <= 1) < 0.6 * len(letters):
        return None
    gaps = [len(g) for g in parts[1::2]]
    base = min(gaps)
    out = [parts[0]]
    for g, tok in zip(parts[1::2], parts[2::2]):
        if len(g) > 1.6 * base and len(g) - base >= 2:
            out.append(" ")
        out.append(tok)
    return "".join(out)


def _bbaw_items(div):
    """Text pieces and line marks of an edition div, leaving out the editors'
    notes in small italics ("vacat", "lacuna"), the superscript gap sizes and
    "v" marks, and any italic Latin."""
    items = []

    def walk(el):
        if el.tag is etree.Comment:
            return
        name = etree.QName(el).localname
        if name == "lb":
            items.append(_LINE_MARK)
            return
        rend = el.get("rend") or ""
        if name == "hi":
            txt = "".join(el.itertext())
            if "sup" in rend or "smallit" in rend or ("italic" in rend and not _GREEK.search(txt)):
                return
            if "letterspacing" in rend:
                joined = join_letterspaced(txt)
                if joined is not None:
                    items.append(joined)
                    return
        if el.text:
            items.append(el.text)
        for ch in el:
            walk(ch)
            if ch.tail:
                items.append(ch.tail)

    for ch in div:
        walk(ch)
        if ch.tail:
            items.append(ch.tail)
    return items


def _clean_line(chars):
    """chars: list of (character, restored). Returns (text, flags)."""
    out = []   # (ch, restored)
    i = 0
    n = len(chars)
    while i < n:
        ch, fl = chars[i]
        o = ord(ch)
        if ch in ".\u2024\u2013\u2014":
            # a run of dots, dashes and the spaces between them is one gap
            j = i
            while j < n and (chars[j][0] in ".\u2024\u2013\u2014 \u00a0"):
                j += 1
            while chars[j - 1][0] in " \u00a0":
                j -= 1
            out.append((GAP, True))
            i = j
            continue
        if (ch == "\u0323" or 0xE000 <= o <= 0xF8FF or o >= 0xF0000
                or ch in "<>:\u205d\u00b7\u2012" or ch.isdigit()):
            i += 1
            continue
        out.append((ch, fl))
        i += 1
    text = "".join(c for c, _ in out)
    flags = [f for _, f in out]
    # drop whitespace-separated tokens with no Greek letter and no gap (stray Latin)
    res, rflags = [], []
    for m in re.finditer(r"\S+|\s+", text):
        piece = m.group(0)
        seg_flags = flags[m.start():m.end()]
        if not piece.isspace() and not _GREEK.search(piece) and GAP not in piece:
            continue
        res.append(piece)
        rflags.extend(seg_flags)
    t = "".join(res)
    # collapse whitespace, keeping flags in step
    fin, ff = [], []
    prev_space = True
    for c, f in zip(t, rflags):
        if c.isspace():
            if prev_space:
                continue
            c, prev_space = " ", True
        else:
            prev_space = False
        fin.append(c)
        ff.append(f)
    while fin and fin[-1] == " ":
        fin.pop()
        ff.pop()
    return "".join(fin), ff


def _ends_in_greek_letter(text: str) -> bool:
    """True when the last letter of the text, passing over combining marks (the dot under an uncertain
    letter, U+0323, stands after it), is Greek."""
    for ch in reversed(text):
        if unicodedata.combining(ch):
            continue
        return bool(_GREEK.match(ch))
    return False


def bbaw_lines(xml_bytes: bytes, notes: list | None = None):
    """Lines of the Berlin edition in the shape EpidocConverter writes. Square
    brackets mark restored letters, round brackets resolved abbreviations
    (both flagged restored), runs of dots and dashes become gaps, and a
    line-end hyphen joins the next line to this one."""
    root = bbaw_parse(xml_bytes, notes)
    divs = [d for d in root.iter(qn("div")) if d.get("type") == "edition"]
    raw_lines: list[list] = [[]]
    for d in divs:
        for it in _bbaw_items(d):
            if it is _LINE_MARK:
                raw_lines.append([])
            else:
                raw_lines[-1].append(it)
    lines = []
    in_br = in_par = False
    join_next = False
    for k, parts in enumerate(raw_lines):
        s = "".join(parts)
        # A sign after the dash ("λλω‒ >", the Berlin mark that the text goes on in the next line) does not
        # change what the dash is. Taken off before the dash is read (2026-10-20: Ἀπόλλω / νι).
        s = re.sub(r"[\s>]+$", "", s) if re.search(r"[\u2012\u2013-]\s*>\s*$", s) else s
        ends_hyphen = s.rstrip().endswith("\u2012")
        # The Berlin edition marks a word broken at the line end with an en dash
        # set right after the last letter (or after the bracket closing it),
        # "πρυτανεί]–" then "ας". A dash that follows a space or another dash is a gap.
        body = s.rstrip()
        if body.endswith("\u2013"):
            before = body[:-1].rstrip("])")
            if before and _ends_in_greek_letter(before) and body[-2:-1] != " ":
                ends_hyphen = True
                s = body[:-1]
        elif body.endswith("-") and not body.endswith(("--", "\u2013-")):
            # A plain hyphen at the line end after a letter, when the next line starts with a letter
            # (verse inscriptions: "θυγ-" then "ατρὸς"). Before a gap or a dash it is a gap sign.
            before = body[:-1].rstrip("])")
            nxt = "".join(raw_lines[k + 1]).lstrip(" \u00a0[(") if k + 1 < len(raw_lines) else ""
            if before and _ends_in_greek_letter(before) and body[-2:-1] != " " and nxt and _GREEK.match(nxt[0]):
                ends_hyphen = True
                s = body[:-1]
        chars = []
        for ch in s:
            if ch == "[":
                in_br = True
            elif ch == "]":
                in_br = False
            elif ch == "(":
                in_par = True
            elif ch == ")":
                in_par = False
            else:
                chars.append((ch, in_br or in_par))
        text, flags = _clean_line(chars)
        if not text:
            continue
        lines.append({"n": None, "diplomatic": text, "expanded": text, "text": text,
                      "restored_flags": flags, "joins_previous": join_next})
        join_next = ends_hyphen
    return lines


def build_record_bbaw(raw: dict, vol: str, ident: str, page: dict | None, files: list, notes: list):
    """A document whose Greek is the Berlin edition's and whose translation is
    AIO's. `files` is a list of (bytes) in the order of the IG numbers."""
    lines = []
    page_url = None
    for xb in files:
        lines.extend(bbaw_lines(xb, notes))
        if page_url is None:
            page_url = bbaw_page_url(bbaw_parse(xb))
    rec = build_record(dict(raw, greek_epidoc=None), vol, ident, page, notes, _allow_no_greek=True)
    rec["lines"] = lines
    rec["text"] = join_lines(lines)
    sup = sum(sum(1 for f in ln["restored_flags"] if f) for ln in lines)
    tot = sum(len(ln["text"]) for ln in lines)
    rec["supplied_chars"], rec["total_chars"] = sup, tot
    rec["gap_count"] = sum(ln["text"].count(GAP) for ln in lines)
    rec["supplied_share"] = sup / tot if tot else 0.0
    rec["languages"] = ["grc"]
    rec["aio"]["greek_source"] = "bbaw"
    rec["aio"]["bbaw_url"] = page_url
    return rec


def choose_edition(page: dict, tr_ref: dict | None):
    """The edition number to show, and how it was derived.

    The heading of AIO's page is used as it stands ("IG II2 18", "SEG 12.147").
    Where the heading is one of AIO's own numbers ("AIO 1049") or its
    UK-collections series ("AIUK 4.6 (BM, Funerary Monuments) no. 1"), the
    first listed reference to the Inscriptiones Graecae is used, else the first
    to the Supplementum Epigraphicum Graecum, else the first reference without
    a comma (a corpus or collection number such as "RO 4" or "Agora XVI 106A").
    With none of these the heading stays and the record is listed."""
    heading = (page or {}).get("edition")
    if not heading:
        if tr_ref:
            return f"{tr_ref['source']} {tr_ref['reference']}", "api-fallback"
        return None, "none"
    if not (heading.startswith("AIO ") or heading.startswith("AIUK")):
        return heading, "heading"
    others = [r for r in page.get("references", []) if r != heading]
    for r in others:
        if r.startswith("IG "):
            return r, "reference-IG"
    for r in others:
        if r.startswith("SEG "):
            return r, "reference-SEG"
    for r in others:
        if "," not in r and not r.startswith(("AIO ", "AIUK")):
            return r, "reference-other"
    return heading, "heading-own-number"


def build_record(raw: dict, vol: str, ident: str, page: dict | None, notes: list,
                 _allow_no_greek: bool = False):
    """One document in the shape epidoc_convert writes (+ AIO extras), or
    None when the inscription has no Greek text."""
    if not raw.get("greek_epidoc") and not _allow_no_greek:
        return None
    if raw.get("greek_epidoc"):
        lines, langs, counts = greek_lines(raw["greek_epidoc"], notes)
    else:
        lines, langs, counts = [], ["grc"], {"gap_count": 0, "supplied_chars": 0, "total_chars": 0}
    if not lines:
        notes.append("no lines")
    page = page or {}
    nb, na = parse_date(page.get("date_text"))
    place = None
    if page.get("findspot"):
        place = re.split(r"\s*[(,;]", page["findspot"])[0].strip() or None
    translators = translators_of(raw)
    tr_text = translation_text(raw["translation_epidoc"], notes) if raw.get("translation_epidoc") else ""
    tr_ref = next((r for r in raw.get("references", []) if r.get("is_translation_source")), None)
    edition, edition_how = choose_edition(page, tr_ref)
    rec = {
        "id": doc_id(vol, ident),
        "source": SOURCE,
        "tm_id": None, "hgv_id": None, "edh_id": None, "edr_id": None, "edcs_id": None,
        "languages": ["grc"] if not langs else langs,
        "bilingual": len(langs) > 1,
        "title": strip_tags(raw.get("translation_title") or "") or None,
        "object_type": page.get("monument_type"),
        "material": None,
        "date_not_before": nb,
        "date_not_after": na,
        "findspot": {"ancient_place": place, "modern_place": None, "region": "Attica",
                     "pleiades_id": page.get("pleiades_id")},
        "lines": lines,
        "text": join_lines(lines),
        "supplied_chars": counts["supplied_chars"],
        "total_chars": counts["total_chars"],
        "gap_count": counts["gap_count"],
        "supplied_share": (counts["supplied_chars"] / counts["total_chars"]) if counts["total_chars"] else 0.0,
        # AIO extras, read by aio_metadata.py
        "aio": {
            "aio_key": raw.get("aio_key"),
            "vol": vol, "ident": ident,
            "url": PAGE_URL.format(vol=vol, ident=ident),
            "edition": edition, "edition_how": edition_how,
            "date_text": page.get("date_text"),
            "monument_type": page.get("monument_type"),
            "inscription_types": page.get("inscription_types"),
            "findspot_text": page.get("findspot"),
            "original_location": page.get("original_location"),
            "translators": translators,
            "translation": tr_text,
            "heading": page.get("edition"),
            "references": page.get("references") or [f"{r['source']} {r['reference']}" for r in raw.get("references", [])],
        },
    }
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("raw_dir")
    ap.add_argument("html_dir")
    ap.add_argument("out")
    ap.add_argument("--report", default=None)
    ap.add_argument("--bbaw-dir", default=None,
                    help="folder with bbaw_index.json and bbaw_raw/ (aio_fetch_bbaw.py): "
                         "pair translations that lack Greek with the Berlin IG edition")
    a = ap.parse_args(argv)
    bbaw = None
    if a.bbaw_dir:
        bbaw = json.load(open(os.path.join(a.bbaw_dir, "bbaw_index.json"), encoding="utf-8"))
    bbaw_stats = {"inscriptions_listed": 0, "converted": 0, "ig_files_used": 0,
                  "licence_not_cc_by_4": [], "missing_files": [], "no_text": [], "recovered": []}

    n_all = n_greek = n_tr = n_written = 0
    problems = []
    langs_seen = {}
    unparsed_dates = []
    fallback_edition = []
    edition_how_counts = {}
    with open(a.out, "w", encoding="utf-8") as out:
        for fn in sorted(glob.glob(os.path.join(a.raw_dir, "*.json"))):
            stem = os.path.basename(fn)[:-5]
            vol_enc, ident_enc = stem.split("__", 1)
            vol, ident = unquote(vol_enc), unquote(ident_enc)
            raw = json.load(open(fn, encoding="utf-8"))
            n_all += 1
            n_tr += bool(raw.get("translation_epidoc"))
            if not raw.get("greek_epidoc"):
                if bbaw and stem in bbaw["per_inscription"]:
                    bbaw_stats["inscriptions_listed"] += 1
                    files = []
                    for num in bbaw["per_inscription"][stem]:
                        fp = os.path.join(a.bbaw_dir, "bbaw_raw", bbaw["files"][num])
                        if not os.path.exists(fp):
                            bbaw_stats["missing_files"].append(num)
                            continue
                        xb = open(fp, "rb").read()
                        if not bbaw_licence_ok(bbaw_parse(xb)):
                            bbaw_stats["licence_not_cc_by_4"].append(num)
                            continue
                        files.append(xb)
                    if not files:
                        continue
                    hp = os.path.join(a.html_dir, stem + ".html")
                    page = parse_page(open(hp, encoding="utf-8").read()) if os.path.exists(hp) else None
                    notes = []
                    rec = build_record_bbaw(raw, vol, ident, page, files, notes)
                    if any(n.startswith("recovered") for n in notes):
                        bbaw_stats["recovered"].append(rec["id"])
                    if not rec["lines"]:
                        bbaw_stats["no_text"].append(rec["id"])
                        continue
                    if page is None:
                        problems.append({"id": rec["id"], "notes": ["no html page"]})
                    bbaw_stats["converted"] += 1
                    bbaw_stats["ig_files_used"] += len(files)
                    how = rec["aio"]["edition_how"]
                    edition_how_counts[how] = edition_how_counts.get(how, 0) + 1
                    if how in ("heading-own-number", "api-fallback", "none"):
                        fallback_edition.append(f"{rec['id']} ({rec['aio']['edition']})")
                    if rec["aio"]["date_text"] and rec["date_not_before"] is None and rec["date_not_after"] is None:
                        unparsed_dates.append(rec["aio"]["date_text"])
                    out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                continue
            n_greek += 1
            hp = os.path.join(a.html_dir, stem + ".html")
            page = parse_page(open(hp, encoding="utf-8").read()) if os.path.exists(hp) else None
            notes: list = []
            rec = build_record(raw, vol, ident, page, notes)
            if notes:
                problems.append({"id": rec["id"], "notes": notes})
            if page is None:
                problems.append({"id": rec["id"], "notes": ["no html page"]})
            langs_seen[",".join(rec["languages"])] = langs_seen.get(",".join(rec["languages"]), 0) + 1
            if rec["aio"]["date_text"] and rec["date_not_before"] is None and rec["date_not_after"] is None:
                unparsed_dates.append(rec["aio"]["date_text"])
            how = rec["aio"]["edition_how"]
            edition_how_counts[how] = edition_how_counts.get(how, 0) + 1
            if how in ("heading-own-number", "api-fallback", "none"):
                fallback_edition.append(f"{rec['id']} ({rec['aio']['edition']})")
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_written += 1
    report = {"inscriptions": n_all, "with_greek": n_greek, "with_translation": n_tr,
              "records_written": n_written, "languages": langs_seen,
              "edition_how": edition_how_counts, "bbaw": bbaw_stats, "problems": problems, "unparsed_dates": unparsed_dates,
              "edition_not_from_page": fallback_edition}
    if a.report:
        json.dump(report, open(a.report, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in report.items()},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
