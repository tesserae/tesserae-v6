"""Host rewrite rules for the outward links stored as `image_url` display rows.

The extractor imports `rewrite_image_url` so a rebuild does not bring back
addresses that stopped working. `fix_image_urls.py` applies the same table to an
existing metadata.db. Dead hosts (no verified replacement) are listed in
client/src/components/documents/imageHosts.json, which the page also reads.

Every rule below was checked on 2026-10-09 against at least five live
addresses (see the audit report). A rule is a (name, compiled pattern,
replacement) triple. The replacement is a string for `re.sub` or a function
taking the match and returning the new address.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlsplit

_HOSTS_JSON = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..",
    "client", "src", "components", "documents", "imageHosts.json")


def _cil_ace(m: "re.Match") -> str:
    """Old CIL photo files moved into the ACE resource tree, bucketed by
    number in directories of 5000 ids (1000 for the SCH series)."""
    prefix, digits = m.group(1), m.group(2)
    size = 1000 if prefix == "SCH" else 5000
    start = int(digits) // size * size + 1
    return ("https://cil.bbaw.de/ace/resources/%s/%07d-%07d/%s%s.jpg"
            % (prefix, start, start + size - 1, prefix, digits))


RULES = [
    ("edh-photo-moved",
     re.compile(r"^https?://edh-www\.adw\.uni-heidelberg\.de/fotos/(F\d+)\.jpg$", re.I),
     r"https://edh.ub.uni-heidelberg.de/edh/foto/\1"),
    ("cil-photo-moved",
     re.compile(r"^https?://cil-old\.bbaw\.de/test\d+/bilder/datenbank/([A-Z]+)(\d+)\.jpg$"),
     _cil_ace),
]


def host_of(url: str) -> str:
    """Lower-case host of an absolute http(s) address, '' for anything else
    (the I.Sicily rows hold bare file names such as ISic000001.jpg)."""
    if not re.match(r"^https?://", url or "", re.I):
        return ""
    return (urlsplit(url).hostname or "").lower()


def rule_for(url: str):
    for name, pat, repl in RULES:
        m = pat.match(url or "")
        if m:
            return name, (repl(m) if callable(repl) else m.expand(repl))
    return None


def rewrite_image_url(url: str) -> str:
    hit = rule_for(url)
    return hit[1] if hit else url


def load_dead_hosts(path: str = _HOSTS_JSON) -> set:
    with open(path, encoding="utf-8") as fh:
        return set(json.load(fh)["deadHosts"])


def is_dead(url: str, dead_hosts: set) -> bool:
    """Bare file names (no host) cannot be followed, so count them as dead."""
    h = host_of(url)
    return h == "" or h in dead_hosts
