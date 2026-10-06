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
    - Typical workflow: list_texts -> compare_texts (all three pairwise methods
      at once, recommended) OR rare_pairs / rare_words / fusion_search
      individually -> line_search to test how unique a shared phrase is across
      the whole corpus -> interpret the strongest, rarest parallels, quoting
      both passages and their loci. For content/thematic work use theme_search
      (find passages on a subject), theme_compare (two whole works compared by
      content), similar_passages (content neighbours of a known passage), and
      theme_pair_lift (content context of word-level matches). Use get_passage
      to fetch actual lines before quoting anything from theme_search or
      similar_passages — those return machine-written gists. Use describe_text
      for an unfamiliar work before discussing it.
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
import csv
import os
import json
import re
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

# Genre/meter classification from data/text_genres.csv at repo root. Optional —
# falls back gracefully when running without the full repository.
_TEXT_GENRES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data", "text_genres.csv")
_genres_cache = {"mtime": None, "data": {}}


def _genre_row(filename):
    """Genre/meter row for one text file, or None when the CSV is absent."""
    try:
        mtime = os.path.getmtime(_TEXT_GENRES_PATH)
    except OSError:
        return None
    if _genres_cache["mtime"] != mtime:
        data = {}
        try:
            with open(_TEXT_GENRES_PATH, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    data[row["filename"]] = row
        except (OSError, KeyError, csv.Error):
            data = {}
        _genres_cache["mtime"] = mtime
        _genres_cache["data"] = data
    return _genres_cache["data"].get(filename)


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
def compare_texts(source: str, target: str, language: str = "la") -> dict:
    """Recommended for comparing two texts. Runs all three automated pairwise
    searches — fusion (ranked parallels across ten signals), rare shared phrases,
    and rare shared words — and returns them as labeled sections.

    The rare sections return in seconds; fusion streams and can take several
    minutes on a first run (cached afterwards). Put the earlier/model text as
    source and the later/alluding text as target for allusion study.

    Present the three sections as ONE merged list ordered by interest — fusion
    score, rarity, and cross-method convergence. A parallel in `also_found_by`
    was confirmed by multiple independent methods; rank those first.

    Args:
        source: source text id from list_texts.
        target: target text id from list_texts.
        language: la | grc | en | cop.
    """
    rw = rare_words(source, target, language)
    rp = rare_pairs(source, target, language)
    fusion = fusion_search(source, target, language, top=100)

    def _norm_ref(s):
        return " ".join((s or "").split()).lower()

    rare_idx = []
    for sec, kind, key in ((rw, "rare_word", "word"), (rp, "rare_phrase", "bigram")):
        for it in (sec.get("results") or []):
            srefs = {_norm_ref(x.get("ref") if isinstance(x, dict) else str(x))
                     for x in (it.get("source_locations") or [])}
            trefs = {_norm_ref(x.get("ref") if isinstance(x, dict) else str(x))
                     for x in (it.get("target_locations") or [])}
            if srefs and trefs:
                rare_idx.append((srefs, trefs, f"{kind}:{it.get(key)}"))

    for p in (fusion.get("parallels") or []):
        sref = _norm_ref((p.get("source") or {}).get("ref"))
        tref = _norm_ref((p.get("target") or {}).get("ref"))
        hits = [lbl for srefs, trefs, lbl in rare_idx if sref in srefs and tref in trefs]
        if hits:
            p["also_found_by"] = hits

    return {
        "source": source, "target": target, "language": language,
        "ranked_parallels": fusion,
        "rare_phrases": rp,
        "rare_words": rw,
        "note": (
            "Merge the three sections into ONE list ordered by how interesting each "
            "parallel is — fusion score, rarity, and cross-method convergence. A "
            "parallel in also_found_by was found by multiple independent methods and "
            "is the strongest evidence — rank those first. Quote BOTH lines with loci, "
            "mark shared words in bold, and give each entry its corpus context via "
            "line_search(count_only=True). Present ~25 then offer to continue."
        ),
    }


@mcp.tool()
def theme_search(query: str, limit: int = 25, languages: str = "",
                 offset: int = 0) -> dict:
    """Find passages ABOUT a described subject, across Latin, Greek, Hebrew and
    English at once — even when they share no vocabulary. Describe the scene or
    topic in plain English ("a city surrenders and hands over hostages",
    "grain shortage and famine relief").

    Complements word-based searches: use this when the connection is one of
    subject or scene type rather than wording. Check `confidence`: 'low' means
    the corpus does not appear to hold this subject. Pass `offset` to page
    deeper into the same ranking.

    Args:
        query: a sentence describing the scene or subject.
        limit: passages to return (default 25).
        languages: optional comma-separated filter (la, grc, he, cop, en).
        offset: page past the normal cutoff (same ranking, not a fresh run).
    """
    params = {"q": query, "limit": limit}
    if languages:
        params["languages"] = languages
    if offset:
        params["offset"] = offset
    d = _get("/passages/theme-search", params)
    out = {
        "query": d.get("query"),
        "confidence": d.get("confidence"),
        "strong_matches": d.get("strong_matches"),
        "results": [{
            "work": r.get("work"), "language": r.get("language"),
            "author": r.get("author"), "title": r.get("title"),
            "display_name": r.get("display_name"),
            "date": r.get("date_note") or r.get("year"),
            "ref_start": r.get("ref_start"), "ref_end": r.get("ref_end"),
            "score": r.get("score"), "strong": r.get("strong"),
            "gist": r.get("gist"),
        } for r in (d.get("results") or [])],
    }
    if d.get("error"):
        out["error"] = d["error"]
    out["note"] = (
        "Content matches: passages whose subject or scene type resembles the query, "
        "found through descriptions rather than shared words. A cross-language hit "
        "shares no vocabulary with the query — explain the kind of resemblance. "
        "The gist is a machine-written summary; fetch the lines with get_passage "
        "before quoting."
    )
    return out


@mcp.tool()
def get_passage(work: str, ref_start: str = "", ref_end: str = "",
                context: int = 0, translation: bool = False) -> dict:
    """The ACTUAL LINES at a reference, each with its own locus. Use this before
    quoting anything from theme_search or similar_passages — those return a
    machine-written gist, never the passage itself.

    Takes the fields those tools emit, e.g. work="vergil.aeneid.part.6" with
    ref_start="verg. aen. 6.258" and ref_end="verg. aen. 6.270".

    Args:
        work: work id from list_texts (e.g. "vergil.aeneid.part.6").
        ref_start: first line reference (e.g. "verg. aen. 6.258").
        ref_end: last line reference (e.g. "verg. aen. 6.270").
        context: widen the window by this many lines each side.
        translation: if True, also fetch the aligned public-domain English
            translation the Reader shows for these lines (when available).
    """
    params = {"work": work}
    if ref_start:
        params["ref_start"] = ref_start
    if ref_end:
        params["ref_end"] = ref_end
    if context:
        params["context"] = str(context)
    d = _get("/passages/lines", params)
    if d.get("error"):
        return d
    out = {
        "work": d.get("work"), "author": d.get("author"),
        "title": d.get("title"), "display_name": d.get("display_name"),
        "language": d.get("language"),
        "lines": d.get("lines") or [],
        "returned": d.get("returned"), "total": d.get("total"),
        "capped": d.get("capped"), "corpus_version": d.get("corpus_version"),
        "web_url": d.get("web_url"),
        "note": (
            "These are the source lines, not a summary. Quote them with the locus "
            "shown against each line. If capped is true this is a bounded window — "
            "say so rather than implying the passage ends here."
        ),
    }
    if translation:
        refs = [str(ln.get("ref")) for ln in (d.get("lines") or [])
                if isinstance(ln, dict) and ln.get("ref")]
        if refs:
            try:
                tr = _get("/passages/translation", {"work": work, "refs": "|".join(refs)})
                out["translation"] = tr
            except Exception:
                out["translation"] = {"available": False,
                                      "reason": "Translation lookup failed."}
        else:
            out["translation"] = {"available": False,
                                  "reason": "No lines to align a translation to."}
    return out


@mcp.tool()
def similar_passages(work: str, ref_start: str = "", ref_end: str = "",
                     limit: int = 25, languages: str = "") -> dict:
    """Passages elsewhere in the corpus whose CONTENT resembles a given passage.
    Finds cross-language matches that share subject and situation rather than
    words — how a Latin scene finds its Greek or Hebrew counterparts.

    Args:
        work: work id from list_texts.
        ref_start: start of the passage (e.g. "verg. aen. 6.258").
        ref_end: end of the passage (optional).
        limit: results to return (default 25).
        languages: optional comma-separated language filter (la, grc, he, cop, en).
    """
    params = {"work": work}
    if ref_start:
        params["ref_start"] = ref_start
    if ref_end:
        params["ref_end"] = ref_end
    if limit != 25:
        params["limit"] = str(limit)
    if languages:
        params["languages"] = languages
    d = _get("/passages/similar", params)
    src = d.get("source") or {}
    out = {
        "source": {
            "work": src.get("work"),
            "ref_start": src.get("ref_start"), "ref_end": src.get("ref_end"),
            "gist": src.get("gist"),
        },
        "confidence": d.get("confidence"),
        "results": [{
            "work": r.get("work"), "language": r.get("language"),
            "author": r.get("author"), "title": r.get("title"),
            "display_name": r.get("display_name"),
            "date": r.get("date_note") or r.get("year"),
            "ref_start": r.get("ref_start"), "ref_end": r.get("ref_end"),
            "score": r.get("score"), "strong": r.get("strong"),
            "gist": r.get("gist"),
        } for r in (d.get("results") or [])],
    }
    if d.get("error"):
        out["error"] = d["error"]
    out["note"] = (
        "Content matches: passages that resemble the source in subject and situation "
        "rather than wording. The gist is machine-written — fetch the lines with "
        "get_passage before quoting either side."
    )
    return out


@mcp.tool()
def theme_compare(work_a: str, work_b: str, scale: str = "", limit: int = 25) -> dict:
    """Two whole works, or two books, read against each other by CONTENT: every
    indexed window of work_a scored against every window of work_b, returning
    the closest-matching passage pairs. Works across languages — no shared
    vocabulary needed. A first comparison of two long poems takes ~12 seconds.

    Check `confidence`: at level 'low' the two works resemble each other little
    beyond general similarity — present the pairs as the closest they come rather
    than as findings. `strong` on a pair marks one that stands well above that
    general resemblance.

    Args:
        work_a: work id of the first text (from list_texts).
        work_b: work id of the second text.
        scale: optional granularity override ("window" or "book").
        limit: pairs to return (default 25).
    """
    params = {"work_a": work_a, "work_b": work_b}
    if scale:
        params["scale"] = scale
    if limit != 25:
        params["limit"] = str(limit)
    r = requests.get(f"{API_BASE}/passages/compare", params=params, timeout=_TIMEOUT)
    try:
        d = r.json()
    except ValueError:
        r.raise_for_status()
        raise

    def _work_meta(key):
        w = d.get(key) or {}
        return {"work": w.get("work"), "author": w.get("author"),
                "title": w.get("title"), "display_name": w.get("display_name")}

    def _side(w):
        if not w:
            return w
        return {"work": w.get("work"),
                "ref_start": w.get("ref_start"), "ref_end": w.get("ref_end"),
                "gist": w.get("gist")}

    out = {
        "work_a": _work_meta("work_a"), "work_b": _work_meta("work_b"),
        "scale": d.get("scale"), "n_a": d.get("n_a"), "n_b": d.get("n_b"),
        "confidence": d.get("confidence"),
        "pairs": [{"score": p.get("score"), "lift": p.get("lift"),
                   "strong": p.get("strong"),
                   "a": _side(p.get("a")), "b": _side(p.get("b"))}
                  for p in (d.get("pairs") or [])],
    }
    if d.get("error"):
        out["error"] = d["error"]
    out["note"] = (
        "Pairs match in CONTENT (scene, theme, situation), not wording, so a "
        "cross-language pair shares no vocabulary. strong marks a pair that "
        "stands well above the two works' general resemblance. The gist is "
        "machine-written — use get_passage to fetch the actual lines before quoting."
    )
    return out


@mcp.tool()
def theme_pair_lift(pairs: list) -> dict:
    """For word-level result pairs from fusion_search or compare_texts, the
    CONTENT-similarity reading of each pair: whether the matched lines also sit
    in a thematically close stretch of the two works, or are isolated shared
    wording in otherwise unrelated passages.

    Takes up to 100 {work_a, ref_a, work_b, ref_b} dicts — the work and ref
    fields a fusion_search or compare_texts result carries — and returns the
    content-similarity score of each pair and its lift above the two works'
    general resemblance.

    Args:
        pairs: list of {work_a, ref_a, work_b, ref_b} dicts (up to 100).
    """
    if not isinstance(pairs, list) or not pairs:
        return {"error": "pairs must be a non-empty list of {work_a, ref_a, work_b, ref_b}"}
    d = _post("/passages/pair-lift", {"pairs": pairs[:100]})
    out = {"results": d.get("results") or []}
    if d.get("error"):
        out["error"] = d["error"]
    out["note"] = (
        "'strong' means this pair of lines resembles each other in content well "
        "above the two works' general resemblance; 'low' means little beyond that. "
        "A null level means no indexed passage window covers one of the two lines — "
        "say so rather than treating it as a weak reading."
    )
    return out


@mcp.tool()
def describe_text(id: str, language: str = "la") -> dict:
    """What a text IS and where it came from: the orientation description shown on
    the site, the print/electronic source citation, the author's dates and era,
    and the genre/meter classification. Give a text id from list_texts.

    Use this before discussing an unfamiliar text, or when a user asks 'what is
    this' or wants to cite an edition. Fields the corpus does not have yet come
    back null rather than omitted, so 'no orientation written' is distinguishable
    from a lookup failure.

    Args:
        id: text id from list_texts (e.g. "vergil.aeneid.tess" or "vergil.aeneid").
        language: language of the text (la | grc | en | cop | he).
    """
    filename = id if id.endswith(".tess") else f"{id}.tess"
    texts = _get("/texts", {"language": language})
    if isinstance(texts, dict):
        texts = texts.get("texts") or texts.get("results") or []
    meta = next((t for t in (texts or []) if t.get("id") == filename), None)
    if meta is None:
        return {"error": f"{filename!r} not found in language {language!r} (see list_texts)"}

    base = re.sub(r"\.part\.\d+$", "", filename[: -len(".tess")])
    description = None
    try:
        desc = _get("/text-descriptions", {"language": language, "work": base})
        description = desc.get("description") if isinstance(desc, dict) else None
    except Exception:
        pass

    source = None
    author = meta.get("author") or ""
    work = meta.get("work") or meta.get("title") or ""
    if author and work:
        try:
            credits = _get("/text-credits", {"query": author, "limit": 500, "offset": 0})
            entries = (credits or {}).get("entries") or []
            na, nw = author.strip().lower(), work.strip().lower()
            source = next(
                (e for e in entries
                 if (e.get("author") or "").strip().lower() == na
                 and (e.get("work") or "").strip().lower() == nw),
                None)
        except Exception:
            pass

    author_dates = None
    author_key = meta.get("author_key") or ""
    if author_key:
        try:
            dates = _get("/author-dates")
            lang_dates = (dates or {}).get(language, {}) if isinstance(dates, dict) else {}
            author_dates = (lang_dates.get(author_key)
                            or lang_dates.get(author_key.lower()))
        except Exception:
            pass

    genre = None
    row = _genre_row(filename)
    if row:
        genre = {
            "era": row.get("era") or None,
            "meter": row.get("meter") or None,
            "genre": row.get("genre") or None,
            "confidence": row.get("confidence") or None,
        }

    return {
        "id": filename, "author": meta.get("author"), "work": meta.get("work"),
        "title": meta.get("title"), "language": language,
        "year": meta.get("year"), "era": meta.get("era"),
        "description": description,
        "source": source,
        "author_dates": author_dates,
        "genre": genre,
    }


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
