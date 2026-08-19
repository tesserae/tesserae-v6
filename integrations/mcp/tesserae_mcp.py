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
      shared words. The FORM depends on the count: under 6, list EVERY occurrence
      inline in compact canonical form (e.g. "Verg. Aen. 2.31; Stat. Theb. 12.531;
      Macr. Sat. 5.5.3 (quoting Vergil)"), marking any that quote an earlier line
      verbatim, because the scholar wants to gaze over the actual places; from 6 to
      ~40, characterize at the resolution the count allows (by work when few, by
      author when the author list is short, by period when it is long); above ~40,
      the count plus "too common to signify" stands; an unretrievable count is
      "unquantified", a capped one is "at least N". Never describe results you have
      not fetched; close with an offer to page deeper. Write for a reader, keeping
      technical terms for when the user asks how a figure was produced.
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
    - Charts: there are no pre-made images to attach. After presenting results,
      when the medium can display graphics, OFFER the user visual views and draw
      whichever they accept yourself, from the data in hand: (1) a connection map
      of the two texts, (2) a timeline of where a shared phrase recurs across the
      centuries, (3) a distribution of parallels across the books or poems of
      either text. Label every chart as your OWN rendering, never an official
      Tesserae figure, and give web_url with each chart and in the close as the
      way to explore interactively (the site's chart is clickable; yours is not).
      Offer, do not force. Conventions: CONNECTION MAP -- two vertical axes scaled
      to line counts (book boundaries marked on multi-book texts), each parallel a
      curve weighted by strength and colored by which search found it, weak links
      recessive gray, a small top tier labeled directly, hover gives both full
      lines (a source->target locus table is the fallback). TIMELINE -- horizontal
      years axis ("negative years are BCE"), one dot per occurrence labeled with
      its author/work/locus, one row per phrase; line_search hits carry era, year,
      author, work, and locus. Keep the encoding dimensions separate, one legend
      entry per dimension: COLOR answers WHERE (source text, target text, or
      elsewhere in the corpus) and nothing else; a HOLLOW marker answers HOW (the
      occurrence quotes an earlier line verbatim rather than reusing the phrase
      independently) and composes with any color; an undated occurrence goes in a
      labeled "undated" gutter at the axis edge with no special marker. DISTRIBUTION
      -- bars per book/poem with a value label on each, the
      leading unit emphasized, a title naming BOTH texts and a subtitle stating the
      population; use the by_book array the response carries and its population
      block (when capped is true say "at least N", the true size being
      total_candidates when given). Every chart footer carries corpus_version and
      web_url.
    - Before a big comparison the first time, briefly offer the user a depth
      choice (a short menu, not a sprawl): the full comparison (ranked parallels
      plus a corpus-rarity check on every entry, most thorough, a few minutes), or
      a quick pass (top parallels only, no per-entry corpus checks, under a
      minute). Run the full version if they don't choose.
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
            line_search matches only WITHIN a single line, so a verse phrase that
            straddles a line break (enjambment) is invisible; if an exact search
            of a verse phrase returns nothing, try a lemma search or regex on each
            half before concluding it is absent.
        count_only: return just the counts (fast, no passages) — quantify a
            commonplace cheaply. A SINGLE-word query then reports how many WORKS
            contain the word (single_word/unit:'works'), not co-occurring loci;
            an all-stopword query returns unquantified. WITHOUT count_only, a
            single-word query lists the lines that contain the word.

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
    total_candidates = None
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
            if isinstance(evt, dict) and evt.get("total_candidates") is not None:
                total_candidates = evt.get("total_candidates")
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
    # Per-book distribution over the whole ranking, so an agent can draw the
    # distribution chart without paging; total_candidates is the true (pre-cap)
    # size, `total` the capped ranked list.
    import re as _re
    from collections import Counter as _Counter
    _sc, _tc = _Counter(), _Counter()
    for _x in latest:
        for _side, _c in (("source", _sc), ("target", _tc)):
            _n = _re.findall(r"\d+", _ref(_x, _side))
            _c[int(_n[0]) if len(_n) >= 2 else 0] += 1
    _fmt = lambda c: [{"book": b, "count": n} for b, n in sorted(c.items())]
    # Older caches predate the stored count; when the ranking did not hit the cap
    # (default 5000) the ranked count is the true total, so fill it in.
    if total_candidates is None and total < 5000:
        total_candidates = total
    capped = (total_candidates is not None and total_candidates > total) or \
             (total_candidates is None and total >= 5000)
    return {"source": source, "target": target, "count": len(parallels),
            "total": total, "filtered_total": filtered_total,
            "total_candidates": total_candidates, "capped": capped,
            "by_book": {"source": _fmt(_sc), "target": _fmt(_tc),
                        "population": {"ranked_candidates": total,
                                       "total_candidates": total_candidates,
                                       "capped": capped}},
            "parallels": parallels,
            # Live, interactive (clickable) view of this comparison in the web app --
            # the one visual every user gets. Offer to draw charts yourself; do not
            # attach a pre-made image (there are none).
            "web_url": _compare_url(source, target, language)}


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
