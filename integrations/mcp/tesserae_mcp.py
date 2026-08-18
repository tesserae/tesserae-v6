"""
Tesserae MCP server
===================

Exposes the Tesserae intertext-search API (https://tesserae.caset.buffalo.edu)
as tools an MCP-capable AI client (Claude Desktop, Claude Code, etc.) can call.

Tesserae finds intertextual parallels — allusions, echoes, quotations, and
borrowings — across ~2,100 Latin, Greek, English, and Coptic literary works.
The API is open (no key). This server just wraps it.

Run:
    pip install fastmcp requests
    python tesserae_mcp.py            # stdio transport (for Claude Desktop/Code)

Config (Claude Desktop / Claude Code), in the mcpServers block:
    "tesserae": { "command": "python", "args": ["/full/path/to/tesserae_mcp.py"] }

Environment:
    TESSERAE_API_BASE  (default https://tesserae.caset.buffalo.edu/api)

Guidance for the model using these tools:
    - Typical workflow: list_texts -> (rare_pairs / rare_words to compare two
      texts, OR fusion_search for the full weighted comparison) -> line_search
      to test how unique a shared phrase is across the whole corpus -> interpret
      the strongest, rarest parallels, quoting both passages and their loci.
    - Keep Tesserae's results (matches, loci, rarity — transparent and
      reproducible) clearly separate from your own interpretation; attribute
      detections to Tesserae and present analysis as AI-assisted inference the
      scholar should verify.
    - Presentation: merge results into ONE list ranked by interest (not grouped
      by which tool found them); quote the COMPLETE line of BOTH passages with
      their loci and mark the shared words in bold on both sides; give each entry
      its corpus context in plain words via line_search(count_only=True) on its
      shared words (small counts get a who-else-uses-it line, larger ones are
      "commonplace", an unretrievable one is "unquantified", a capped one is "at
      least N"); never describe results you have not fetched; close with an offer
      to page deeper. Write for a reader, keeping technical terms for when the
      user asks how a figure was produced.
    - The matching is not only lexical: besides shared words, fusion matches on
      meaning (semantic), grammar (syntax), synonyms, and sound. A parallel found
      by meaning or grammar may share no words, so it has nothing to bold; present
      it on its own terms (quote both lines, say it is a meaning echo or a shared
      construction), name the kind of similarity, and never drop it for lacking
      shared words.
    - fusion_search can take several minutes on large texts; run it once.
    - When a response carries web_url, show it with the results in plain words
      ("open this comparison in Tesserae's own interface"), in the close and in
      any artifact footer, or the link stays invisible to the reader.
    - The response carries three ready-made chart image URLs, each the same figure
      the site draws, rendered server-side. When they display well in the medium,
      attach them with the results and PREFER them over drawing your own:
      chart_url (distribution: where the parallels fall in one text), history_url
      (history strip: where each top shared phrase recurs across the corpus over
      time -- shared-word recurrence only, so meaning/grammar-only parallels are
      not on it), and map_url (connection map: the two texts as vertical axes joined by
      curves weighted by strength, rare-word finds highlighted). These images are
      STATIC, the user cannot click them, so whenever you show a chart tell them
      the way to drill in is to open web_url, where they can click a bar to filter
      the parallels or click an author to see just their citations. Give that link
      every time you present a chart. Prefer the official charts by default; but
      if the user asks for a chart, a different cut, or a custom visualization,
      make it freely from the data and label it as your own rendering, not an
      official Tesserae figure. Offer, do not force.
    - Before a big comparison the first time, briefly offer the user a depth
      choice (a short menu, not a sprawl): the full comparison (ranked parallels
      plus a corpus-rarity check on every entry and the charts, most thorough, a
      few minutes), or a quick pass (top parallels only, no per-entry corpus
      checks, under a minute). Run the full version if they don't choose.
"""
import os
import json
from urllib.parse import quote

import requests

# FastMCP ships two ways: the standalone `fastmcp` package (recommended,
# `pip install fastmcp`) and, in older MCP SDKs, bundled at
# `mcp.server.fastmcp`. Support both so the server runs on either.
try:
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover
    from mcp.server.fastmcp import FastMCP

API_BASE = os.environ.get("TESSERAE_API_BASE", "https://tesserae.caset.buffalo.edu/api").rstrip("/")
# Web app that hosts the interactive charts (strip a trailing /api). web_url
# fields deep-link into it so the user can open a live, interactive timeline.
WEB_BASE = API_BASE[:-4] if API_BASE.endswith("/api") else API_BASE


def _line_search_url(query, language, search_type):
    if not query:
        return None
    return (f"{WEB_BASE}/?tab=line&q={quote(query)}"
            f"&lang={quote(language or 'la')}&type={quote(search_type or 'lemma')}")


def _compare_url(source, target, language):
    if not (source and target):
        return None
    return (f"{WEB_BASE}/?source={quote(str(source))}&target={quote(str(target))}"
            f"&lang={quote(language or 'la')}")


def _chart_url(source, target, language):
    # Server-rendered image of the comparison's distribution chart.
    if not (source and target):
        return None
    return (f"{API_BASE}/comparison-chart?source={quote(str(source))}"
            f"&target={quote(str(target))}&language={quote(language or 'la')}")


def _history_url(source, target, language):
    # Server-rendered 'history strip': where each top shared phrase recurs across
    # the corpus over time (one row per parallel), as one image.
    if not (source and target):
        return None
    return (f"{API_BASE}/comparison-history-chart?source={quote(str(source))}"
            f"&target={quote(str(target))}&language={quote(language or 'la')}")


def _map_url(source, target, language):
    # Server-rendered connection map (two texts as vertical axes, parallels as curves).
    if not (source and target):
        return None
    return (f"{API_BASE}/comparison-map-chart?source={quote(str(source))}"
            f"&target={quote(str(target))}&language={quote(language or 'la')}")

_TIMEOUT = 60
_FUSION_TIMEOUT = 600

mcp = FastMCP("tesserae")


def _get(path, params=None):
    r = requests.get(f"{API_BASE}{path}", params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _post(path, body):
    r = requests.post(f"{API_BASE}{path}", json=body, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


@mcp.tool()
def get_languages() -> dict:
    """List the languages Tesserae supports (la=Latin, grc=Greek, en=English,
    cop=Coptic) and the available cross-language pairs."""
    return _get("/languages")


@mcp.tool()
def list_texts(language: str, contains: str = "", limit: int = 60) -> list:
    """List texts (with their ids) for a language. Use a text's `id` as the
    source/target for two-text searches.

    Args:
        language: la | grc | en | cop
        contains: optional case-insensitive filter on author/work/title
                  (e.g. "vergil", "aeneid") — recommended, the full list is long.
        limit: max texts to return (default 60).
    """
    texts = _get("/texts", {"language": language})
    if isinstance(texts, dict):
        texts = texts.get("texts") or texts.get("results") or []
    needle = contains.strip().lower()
    out = []
    for t in texts:
        blob = " ".join(str(t.get(k, "")) for k in ("author", "work", "title", "display_name", "id")).lower()
        if needle and needle not in blob:
            continue
        out.append({
            "id": t.get("id"),
            "author": t.get("author"),
            "work": t.get("work"),
            "title": t.get("title") or t.get("display_name"),
        })
        if len(out) >= limit:
            break
    return out


@mcp.tool()
def line_search(query: str, language: str = "la", search_type: str = "lemma",
                count_only: bool = False) -> dict:
    """Find lines ANYWHERE in the corpus that share words with a phrase. The
    corpus-wide UNIQUENESS check: run a candidate parallel's shared words here —
    few results means the wording is distinctive (a stronger allusion claim).

    Report distinct_loci (not total). If the result is capped, say "at least N".
    When the user records a count for use elsewhere, quote corpus_version with it.

    Args:
        query: a phrase or line (e.g. "arma virumque").
        language: la | grc | en | cop.
        search_type: lemma (dictionary form, default) | exact | regex.
        count_only: return just the counts (fast, no passages) — quantify a
            commonplace cheaply. A SINGLE-word query then reports how many WORKS
            contain the word (single_word/unit:'works'), not co-occurring loci;
            an all-stopword query returns unquantified.

    Each result carries era and year for its author, so you can chart where
    across time the phrase recurs (a period/author timeline). The response also
    carries web_url: a link that opens this search in the Tesserae web app,
    which draws the timeline live and lets the user click a period or author to
    see just those citations. Offer it when a visual would help.
    """
    d = _post("/line-search", {"query": query, "language": language,
                               "search_type": search_type, "count_only": count_only})
    out = {"query": query, "total": d.get("total"),
           "distinct_loci": d.get("distinct_loci"),
           "capped": d.get("capped"), "corpus_version": d.get("corpus_version")}
    for k in ("total_at_least", "filtered_common_words", "single_word", "unit",
              "corpus_document_frequency", "unquantified"):
        if d.get(k) is not None:
            out[k] = d.get(k)
    if not count_only:
        out["results"] = [{
            "locus": r.get("locus"),
            "author": r.get("author"),
            "work": r.get("work"),
            "text": r.get("text"),
            "matched_words": r.get("matched_words"),
            "era": r.get("era"),
            "year": r.get("year"),
        } for r in (d.get("results") or [])[:40]]
        out["web_url"] = _line_search_url(query, language, search_type)
    return out


@mcp.tool()
def string_search(query: str, language: str = "la") -> dict:
    """Wildcard / boolean / exact text search across the corpus. Supports
    wildcards (am*), boolean operators (AND / OR / NOT), and "quoted phrases"."""
    d = _post("/wildcard-search", {"query": query, "language": language})
    results = [{
        "ref": r.get("ref") or r.get("reference"),
        "author": r.get("author"),
        "title": r.get("title"),
        "text": r.get("text"),
    } for r in (d.get("results") or [])[:40]]
    return {"query": query, "total_matches": d.get("total_matches"),
            "truncated": d.get("truncated"), "results": results}


@mcp.tool()
def rare_pairs(source: str, target: str, language: str = "la") -> dict:
    """Rare two-word combinations shared by two texts (distinctive collocations),
    ranked by rarity. A JSON-fast way to compare two texts. Use text ids from
    list_texts as source/target."""
    d = _post("/rare-bigram-search", {"source": source, "target": target, "language": language})
    results = [{
        "bigram": f"{r.get('display1', r.get('word1'))} {r.get('display2', r.get('word2'))}",
        "rarity_percent": r.get("rarity_percent"),
        "source_locations": (r.get("source_locations") or [])[:5],
        "target_locations": (r.get("target_locations") or [])[:5],
    } for r in (d.get("results") or [])[:40]]
    return {"shared_rare_count": d.get("shared_rare_count"), "results": results}


@mcp.tool()
def rare_words(source: str, target: str, language: str = "la") -> dict:
    """Rare individual words shared by two texts, with how common each is
    corpus-wide (fewer texts = rarer = stronger signal). Use ids from list_texts."""
    d = _post("/hapax-search", {"source": source, "target": target, "language": language})
    results = [{
        "word": r.get("display_form") or r.get("lemma"),
        "corpus_count": r.get("corpus_count"),
        "proper_noun": r.get("is_proper_noun"),
        "source_locations": (r.get("source_locations") or [])[:5],
        "target_locations": (r.get("target_locations") or [])[:5],
    } for r in (d.get("results") or [])[:40]]
    return {"shared_rare_count": d.get("shared_rare_count"), "results": results}


@mcp.tool()
def fusion_search(source: str, target: str, language: str = "la", top: int = 20,
                  source_ref_prefix: str = "", target_ref_prefix: str = "",
                  min_score: float = 0.0, offset: int = 0) -> dict:
    """Full weighted FUSION comparison of two texts — the flagship search. Ranks
    the passages most likely to be genuine parallels, fusing ten similarity
    channels (shared words, sound, meaning, syntax, rare vocabulary, ...).

    NOTE: this streams and can take SEVERAL MINUTES on large texts; results are
    cached afterwards, so run it once. Use text ids from list_texts.

    Args:
        source, target: text ids from list_texts.
        language: la | grc | en | cop.
        top: max parallels to return.
        source_ref_prefix: keep only parallels whose SOURCE ref starts with this
            (e.g. "1." for book 1) — for a question about one book or poem.
        target_ref_prefix: same, for the TARGET ref.
        min_score: drop parallels below this fused score.
        offset: page into the ranked set (0, 20, ...) — genuine parallels also
            appear below the top, so offer to page deeper.

    Returns the parallels (source/target loci + text, fused score, channels), plus
    `total` (before filters) and `filtered_total` (after ref/score filters).
    """
    url = f"{API_BASE}/search-fusion"
    body = {"source": source, "target": target, "language": language}
    latest = []
    with requests.post(url, json=body, stream=True, timeout=_FUSION_TIMEOUT) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            try:
                evt = json.loads(line[6:])
            except Exception:
                continue
            if isinstance(evt, dict) and isinstance(evt.get("results"), list):
                latest = evt["results"]
    latest = sorted(latest, key=lambda x: x.get("fused_score", 0), reverse=True)
    total = len(latest)

    def _ref(x, side):
        return str((x.get(side) or {}).get("ref") or "")
    if source_ref_prefix:
        latest = [x for x in latest if _ref(x, "source").startswith(source_ref_prefix)]
    if target_ref_prefix:
        latest = [x for x in latest if _ref(x, "target").startswith(target_ref_prefix)]
    if min_score:
        latest = [x for x in latest if x.get("fused_score", 0) >= min_score]
    filtered_total = len(latest)
    latest = latest[offset:offset + top]
    parallels = [{
        "score": round(x.get("fused_score", 0), 2),
        "channels": x.get("channels"),
        "source": {"ref": x.get("source", {}).get("ref"), "text": x.get("source", {}).get("text")},
        "target": {"ref": x.get("target", {}).get("ref"), "text": x.get("target", {}).get("text")},
        "matched": x.get("matched_lemmas") or x.get("matched_words"),
    } for x in latest]
    return {"source": source, "target": target, "count": len(parallels),
            "total": total, "filtered_total": filtered_total, "parallels": parallels,
            # Live, interactive view of this comparison (with its charts) in the web app.
            "web_url": _compare_url(source, target, language),
            # Server-rendered distribution chart image (attach/embed with results).
            "chart_url": _chart_url(source, target, language),
            # Server-rendered 'history strip' image (where the top phrases recur over time).
            "history_url": _history_url(source, target, language),
            # Server-rendered connection-map image (the two texts joined by weighted curves).
            "map_url": _map_url(source, target, language)}


@mcp.tool()
def cross_language(source: str, target: str, source_language: str,
                   target_language: str, top: int = 20) -> dict:
    """Cross-language intertext parallels between two texts in DIFFERENT languages
    (e.g. the Greek model behind a Latin poem). Use text ids from list_texts and
    give each text's language. Synchronous; may take a few minutes on a large pair.

    Args:
        source: source text id.
        target: target text id.
        source_language: source language (la | grc | en | cop).
        target_language: target language (la | grc | en | cop).
        top: max parallels to return.
    """
    r = requests.post(f"{API_BASE}/search", json={
        "source": source, "target": target,
        "source_language": source_language, "target_language": target_language,
        "match_type": "crosslingual_fusion", "min_matches": 2,
    }, timeout=_FUSION_TIMEOUT)
    r.raise_for_status()
    d = r.json()
    parallels = [{
        "score": round(x.get("overall_score", 0), 2),
        "source": {"ref": (x.get("source") or {}).get("ref"), "text": (x.get("source") or {}).get("text")},
        "target": {"ref": (x.get("target") or {}).get("ref"), "text": (x.get("target") or {}).get("text")},
        "matched": x.get("matched_words"),
    } for x in (d.get("results") or [])[:top]]
    return {"source": source, "target": target, "count": len(parallels), "parallels": parallels}


@mcp.tool()
def submit_feature_request(request_type: str, title: str = "", problem: str = "",
                           desired: str = "", example: str = "", context: str = "",
                           contact: str = "") -> dict:
    """File a feature / language / text / bug request for Tesserae.

    ONLY call this AFTER the user has explicitly confirmed the exact request —
    never file silently. WARN the user first that feature/language/bug requests
    are auto-filed as a PUBLIC GitHub issue for the dev team; any contact email
    they give is kept private and never placed in the public issue.

    Args:
        request_type: feature | language | text | bug | other
        title, problem, desired, example: the request (include at least a title
            or a problem description).
        context: the actual queries/results that prompted the request — attach
            them so the request is actionable.
        contact: optional email — kept private.
    """
    body = {"type": request_type, "title": title, "problem": problem,
            "desired": desired, "example": example, "context": context, "contact": contact}
    return _post("/feature-request", {k: v for k, v in body.items() if v})


if __name__ == "__main__":
    mcp.run()
