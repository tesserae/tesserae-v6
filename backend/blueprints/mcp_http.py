"""
Tesserae remote MCP server (Streamable HTTP) — served at /api/mcp.

Lets a Claude custom connector (Settings -> Connectors -> "Add custom connector",
paste https://tesserae.caset.buffalo.edu/api/mcp) drive the Tesserae API from
ordinary chat Claude, with no guide-pasting.

Design: minimal, stateless, tools-only MCP over HTTP. Each client POST carries
JSON-RPC; we answer with a single application/json JSON-RPC response (no SSE is
needed because this server never initiates messages). The tool bodies are thin
wrappers over the public Tesserae API (reusing the same shapes as the stdio MCP
server), so this stays decoupled from the search internals.
"""
import os
import json
import time
import uuid
import logging
from urllib.parse import quote

import requests
from flask import Blueprint, request, jsonify, Response

logger = logging.getLogger(__name__)
mcp_http_bp = Blueprint('mcp_http', __name__)

API_BASE = os.environ.get('TESSERAE_API_BASE', 'https://tesserae.caset.buffalo.edu/api').rstrip('/')
# The web app that hosts the interactive charts, derived from the API base
# (strip a trailing /api). web_url fields below deep-link into it so an agent
# can hand the user a live, interactive timeline of the same result.
WEB_BASE = API_BASE[:-4] if API_BASE.endswith('/api') else API_BASE

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
    # Server-rendered image of the comparison's distribution chart (the same
    # picture the web page draws), for an agent to attach/embed with results.
    if not (source and target):
        return None
    return (f"{API_BASE}/comparison-chart?source={quote(str(source))}"
            f"&target={quote(str(target))}&language={quote(language or 'la')}")

def _history_url(source, target, language):
    # Server-rendered 'history strip': where each top shared phrase recurs across
    # the corpus over time, one row per parallel. One image for the whole set.
    if not (source and target):
        return None
    return (f"{API_BASE}/comparison-history-chart?source={quote(str(source))}"
            f"&target={quote(str(target))}&language={quote(language or 'la')}")
# Keep this minimal and spec-exact for the negotiated protocolVersion. Adding
# non-standard Implementation fields (title/websiteUrl/icons from a later draft)
# caused Claude's connector to reject the initialize response ("Tesserae returned
# an error when connecting"), 2026-08-14. The Tesserae icon comes from /favicon.ico.
SERVER_INFO = {"name": "tesserae", "version": "1.0.0"}
DEFAULT_PROTOCOL = "2025-06-18"
_TIMEOUT = 90
_FUSION_POLL_TIMEOUT = 330   # HTTP request timeout for a fresh fusion run
# Remote MCP clients (e.g. Claude's connector) cap each tool call at ~60s, so a
# fusion tool call must return well under that. We block-and-poll only for this
# budget, then hand back a "still running" status telling the assistant to call
# again — the job keeps computing server-side and its result is cached.
_FUSION_MCP_BUDGET = 45      # seconds to block before returning status=running
_COMPARE_BUDGET = 50         # hard per-call wall-clock ceiling for compare_texts (safe under ~60s client cap)
_COMPARE_FUSION_RESERVE = 4  # seconds kept back to kick off the (async, separately-polled) fusion section
_COMPARE_FUSION_PREVIEW = 25  # fusion parallels shown in the compare_texts first-look (fusion_search pages the rest)


# --------------------------------------------------------------------------
# API helpers
# --------------------------------------------------------------------------
def _get(path, params=None):
    r = requests.get(f"{API_BASE}{path}", params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _post(path, body, timeout=None):
    # `timeout or _TIMEOUT` is always a real timeout; bandit B113 can't see the fallback.
    r = requests.post(f"{API_BASE}{path}", json=body, timeout=timeout or _TIMEOUT)  # nosec B113
    r.raise_for_status()
    return r.json()


# --------------------------------------------------------------------------
# Tool implementations (return plain JSON-able data)
# --------------------------------------------------------------------------
def _t_get_languages(a):
    return _get('/languages')


def _t_list_texts(a):
    texts = _get('/texts', {'language': a.get('language', 'la')})
    if isinstance(texts, dict):
        texts = texts.get('texts') or texts.get('results') or []
    needle = (a.get('contains') or '').strip().lower()
    limit = int(a.get('limit', 60) or 60)
    out = []
    for t in texts:
        blob = ' '.join(str(t.get(k, '')) for k in ('author', 'work', 'title', 'display_name', 'id')).lower()
        if needle and needle not in blob:
            continue
        out.append({'id': t.get('id'), 'author': t.get('author'),
                    'work': t.get('work'), 'title': t.get('title') or t.get('display_name')})
        if len(out) >= limit:
            break
    return out


def _t_line_search(a):
    count_only = bool(a.get('count_only'))
    d = _post('/line-search', {'query': a.get('query', ''),
                               'language': a.get('language', 'la'),
                               'search_type': a.get('search_type', 'lemma'),
                               'count_only': count_only})
    out = {'query': a.get('query'), 'total': d.get('total'),
           'distinct_loci': d.get('distinct_loci'), 'capped': d.get('capped'),
           'corpus_version': d.get('corpus_version')}
    # Single-word query: `total` is a corpus document frequency (number of works
    # containing the word), NOT co-occurring loci. Surface that so it isn't read
    # as a loci count; a null total means all-stopword (unquantified).
    if d.get('single_word'):
        out['single_word'] = True
        out['unit'] = d.get('unit', 'works')
        if d.get('unquantified'):
            out['unquantified'] = True
        out['note'] = d.get('note')
    # A common word in the query was too frequent to index alone but WAS used for
    # co-occurrence: name it so the pairing isn't mis-reported (the count is real).
    if d.get('filtered_common_words'):
        out['filtered_common_words'] = d.get('filtered_common_words')
    # When the corpus scan hit the cap, `total` is a floor — report "N+".
    if d.get('capped'):
        out['total_at_least'] = d.get('total_at_least', d.get('total'))
    if not count_only:
        out['results'] = [{'locus': r.get('locus'), 'author': r.get('author'),
                           'work': r.get('work'), 'text': r.get('text'),
                           'matched_words': r.get('matched_words'),
                           # era + year let you chart WHERE ACROSS TIME the phrase
                           # recurs (a period/author timeline), same as the web app.
                           'era': r.get('era'), 'year': r.get('year')}
                          for r in (d.get('results') or [])[:40]]
        # A live, interactive version of this search (timeline + filters) in the web app.
        out['web_url'] = _line_search_url(a.get('query'), a.get('language', 'la'),
                                          a.get('search_type', 'lemma'))
    return out


def _t_string_search(a):
    d = _post('/wildcard-search', {'query': a.get('query', ''), 'language': a.get('language', 'la')})
    return {'query': a.get('query'), 'total_matches': d.get('total_matches'),
            'results': [{'ref': r.get('ref') or r.get('reference'), 'author': r.get('author'),
                         'title': r.get('title'), 'text': r.get('text')}
                        for r in (d.get('results') or [])[:40]]}


def _locs(entries, k=3):
    """In-scope locations with ref AND the full line text, so the agent can always
    QUOTE the complete line per the presentation contract. Bounded to k entries to
    keep the payload small — the raw dicts also carry author/work/text_id/positions,
    which we drop as redundant (those inflated the response before)."""
    out = []
    for e in (entries or [])[:k]:
        if isinstance(e, dict):
            ref = e.get('ref')
            if not ref:
                continue
            item = {'ref': ref}
            if e.get('text'):
                item['text'] = e['text']
            out.append(item)
        elif e:
            out.append({'ref': e})
    return out


def _loc_ref(x):
    return x.get('ref') if isinstance(x, dict) else x


def _t_rare_pairs(a, timeout=None):
    d = _post('/rare-bigram-search', {'source': a.get('source'), 'target': a.get('target'),
                                      'language': a.get('language', 'la')}, timeout=timeout)
    return {'shared_rare_count': d.get('shared_rare_count'),
            'results': [{'bigram': f"{r.get('display1', r.get('word1'))} {r.get('display2', r.get('word2'))}",
                         'rarity_percent': r.get('rarity_percent'),
                         'source_locations': _locs(r.get('source_locations')),
                         'target_locations': _locs(r.get('target_locations'))}
                        for r in (d.get('results') or [])[:40]]}


def _t_rare_words(a, timeout=None):
    d = _post('/hapax-search', {'source': a.get('source'), 'target': a.get('target'),
                                'language': a.get('language', 'la')}, timeout=timeout)
    return {'shared_rare_count': d.get('shared_rare_count'),
            'results': [{'word': r.get('display_form') or r.get('lemma'),
                         'corpus_count': r.get('corpus_count'), 'proper_noun': r.get('is_proper_noun'),
                         'source_locations': _locs(r.get('source_locations')),
                         'target_locations': _locs(r.get('target_locations'))}
                        for r in (d.get('results') or [])[:40]]}


def _fusion_poll(params, budget):
    """Start (or resume) a server-side fusion run and block-poll the GET fusion
    endpoint for at most `budget` seconds, then return status=running so the
    (time-limited) MCP client can call again to pick up the cached result once it
    completes. Kicks off the job even when the budget is tiny (one GET starts it)."""
    poll_interval = 8
    deadline = time.time() + max(0, budget)
    running_note = ('Still computing server-side (first runs take a few minutes) and the '
                    'result will be cached. Call the same tool again with the same arguments '
                    'in ~30-60 seconds to retrieve it.')
    while True:
        d = _get('/fusion-search', params)
        status = d.get('status')
        if status == 'complete':
            out = {'status': 'complete', 'count': d.get('count'),
                   'showing': d.get('showing'), 'offset': d.get('offset', 0),
                   'parallels': d.get('parallels')}
            # Surface filter context when present (count is after filters; total is
            # the full result set before them).
            for k in ('total', 'limit', 'filters'):
                if d.get(k) is not None and d.get(k) != {}:
                    out[k] = d.get(k)
            return out
        if status == 'error':
            return {'status': 'error', 'error': d.get('error')}
        # Return before starting a sleep that would push us past the budget, so
        # the tool call never trips the client's ~60s per-call timeout.
        if time.time() + poll_interval >= deadline:
            return {'status': 'running', 'note': running_note}
        time.sleep(poll_interval)


def _fusion_params(a):
    p = {'source': a.get('source'), 'target': a.get('target'), 'language': a.get('language', 'la')}
    try:
        off = int(a.get('offset') or 0)
        if off > 0:
            p['offset'] = off
    except (TypeError, ValueError):
        pass
    try:
        lim = int(a.get('limit') or 0)
    except (TypeError, ValueError):
        lim = 0
    # Small default page (batch-of-~25 presentation contract) that also keeps the
    # common response under the MCP client's token window; page more via limit/offset.
    p['limit'] = lim if lim > 0 else 25
    # Server-side filters applied over the full result set before the display cap.
    for k in ('source_ref_prefix', 'target_ref_prefix'):
        v = (a.get(k) or '').strip()
        if v:
            p[k] = v
    try:
        if a.get('min_score') is not None and str(a.get('min_score')).strip() != '':
            p['min_score'] = float(a.get('min_score'))
    except (TypeError, ValueError):
        pass
    return p


def _t_fusion_search(a):
    """Ranked fusion parallels for two texts. Pass offset to page deeper into the
    ranking (0, 100, 200, ...) once the run is cached."""
    res = _fusion_poll(_fusion_params(a), _FUSION_MCP_BUDGET)
    if isinstance(res, dict):
        # Live, interactive view of this comparison (charts) in the web app.
        res.setdefault('web_url', _compare_url(a.get('source'), a.get('target'),
                                               a.get('language', 'la')))
        res.setdefault('chart_url', _chart_url(a.get('source'), a.get('target'),
                                               a.get('language', 'la')))
        res.setdefault('history_url', _history_url(a.get('source'), a.get('target'),
                                                   a.get('language', 'la')))
    return res


def _t_compare_texts(a):
    """Recommended two-text comparison: run all three automated pairwise searches
    and return them as labeled sections, all within one per-call time budget. The
    rare-word and rare-phrase passes run to completion (each bounded so it can't
    starve the others); fusion is async, so on a first run its section comes back
    status=running and the caller polls fusion_search to fill it in (cached after).
    A genuinely oversized pair degrades a section to a 'run it on its own' pointer."""
    start = time.time()

    def _left():
        return _COMPARE_BUDGET - (time.time() - start)

    def _section(fn, own_tool, cap):
        # Run the rare sections sequentially — the server is CPU-bound, so parallel
        # runs just make each slower. Give each a running-budget HTTP timeout (its
        # typical cost, but never so much that fusion can't be kicked off); a
        # genuinely oversized pair degrades to a pointer to run it on its own.
        budget = min(cap, _left() - _COMPARE_FUSION_RESERVE)
        if budget < 3:
            return {'status': 'skipped',
                    'note': f'Skipped to stay within the time budget; run {own_tool} on its own for this section.'}
        try:
            return fn(a, timeout=budget)
        except requests.exceptions.Timeout:
            return {'status': 'too_large',
                    'note': f'This pair is large; run {own_tool} on its own to get this section.'}
        except Exception as e:
            return {'error': str(e)}

    # rare_words first — shared rare individual words are the stronger intertext
    # signal, so give them budget priority; rare_pairs takes what remains.
    rare_words = _section(_t_rare_words, 'rare_words', 34)     # typically ~25s
    rare_phrases = _section(_t_rare_pairs, 'rare_pairs', 18)   # typically ~10s
    fusion = _fusion_poll(_fusion_params(a), max(0, _left()))
    # compare_texts is a "first look" that auto-runs three sections, so keep the
    # combined payload small: cap the fusion preview to a compact top slice (deep
    # dives go through fusion_search, which pages the full set). Without this a
    # single response can exceed the MCP client's token budget.
    if fusion.get('parallels'):
        full = fusion.get('count')
        fusion['parallels'] = [{'score': p.get('score'),
                                'source': p.get('source'), 'target': p.get('target'),
                                'matched': p.get('matched') or p.get('matched_lemmas')}
                               for p in fusion['parallels'][:_COMPARE_FUSION_PREVIEW]]
        fusion['showing'] = len(fusion['parallels'])
        fusion['note'] = (f"Top {len(fusion['parallels'])} of {full}; call fusion_search "
                          "(same source/target) for more, deeper pages, or ref/score filters.")
        # Cross-reference: flag fusion parallels whose passage pair was ALSO found
        # by a rare search (same source AND target loci), so the agent can merge by
        # convergence directly instead of inferring from refs. Convergence of
        # independent methods is real evidence and should raise an entry.
        def _norm(s):
            return ' '.join((s or '').split()).lower()
        rare_idx = []
        for sec, kind, key in ((rare_words, 'rare_word', 'word'), (rare_phrases, 'rare_phrase', 'bigram')):
            for it in (sec.get('results') or []) if isinstance(sec, dict) else []:
                srefs = {_norm(_loc_ref(x)) for x in (it.get('source_locations') or [])}
                trefs = {_norm(_loc_ref(x)) for x in (it.get('target_locations') or [])}
                if srefs and trefs:
                    rare_idx.append((srefs, trefs, f"{kind}:{it.get(key)}"))
        for p in fusion['parallels']:
            sref = _norm((p.get('source') or {}).get('ref'))
            tref = _norm((p.get('target') or {}).get('ref'))
            hits = [lbl for srefs, trefs, lbl in rare_idx if sref in srefs and tref in trefs]
            if hits:
                p['also_found_by'] = hits
    out = {
        'source': a.get('source'), 'target': a.get('target'), 'language': a.get('language', 'la'),
        'ranked_parallels': fusion,      # fusion: strongest overall parallels
        'rare_phrases': rare_phrases,    # distinctive shared two-word collocations
        'rare_words': rare_words,        # distinctive shared individual words
        # Live, interactive view of this comparison (with the distribution +
        # corpus-recurrence charts) in the web app.
        'web_url': _compare_url(a.get('source'), a.get('target'), a.get('language', 'la')),
        'chart_url': _chart_url(a.get('source'), a.get('target'), a.get('language', 'la')),
        'history_url': _history_url(a.get('source'), a.get('target'), a.get('language', 'la')),
    }
    common = (
        "PRESENTATION (default; an explicit user request for a by-search view, the full list, or a "
        "specific sort overrides this). Merge the three sections into ONE list ordered by how "
        "interesting each parallel is — your synthesis of fusion score, rarity, cross-method "
        "convergence, and interpretive promise. Do NOT organize the output by which search produced "
        "what; the sections here are data, interleave them. "
        "WRITE FOR A READER, NOT A PIPELINE. The visible presentation is plain English; the method "
        "vocabulary (deduplicated distinct loci, N+, capped scan, lemma, bigram, rarity percentile, "
        "fusion channels) is for your own reasoning, never for the reader. Translate every number into "
        "plain words with nothing lost: 'these words occur together in only 8 places in all of surviving "
        "Latin'; 'in at least 467 places — too common to mean much'; 'the two poems share the word in "
        "different forms'; 'one of the rarest word-pairings the two texts share'; 'confirmed by several "
        "independent kinds of similarity'. Keep the technical terms and raw numbers ready for when the "
        "user asks how a figure was produced, and once the user uses their own vocabulary, mirror it (a "
        "user who says 'lemma' may be answered with 'lemma'); default to plain. "
        "Per entry: quote the COMPLETE line (or two-line window) of BOTH passages with their loci — "
        "never a paraphrase, and this holds for tail entries too (a compressed entry shortens the "
        "discussion, not the quotation). In each quotation, mark the shared material in BOLD, using the "
        "matched word forms the results already carry for both sides; where the shared word wears "
        "different forms, bold each form ('tua **rura manebunt**' against '**manet** divini gloria "
        "**ruris**') — this makes the match visible without explaining it. Bold is the default marking; "
        "where the output has no markdown, use CAPITALS or [brackets]. Every section carries the line "
        "text: fusion parallels in source.text/target.text, and the rare sections in each in-scope "
        "location's text field. "
        "Say which search(es) found each parallel and how strong it is, in plain words (fusion = overall "
        "similarity plus how many independent kinds of match agree; rare phrase = a distinctive shared "
        "wording; rare word = a shared word and how rare it is corpus-wide); when more than one search "
        "found the same passage pair, say so and rank it HIGHER (a fusion parallel carries an "
        "also_found_by field when it coincides with a rare hit; otherwise match by ref) — agreement of "
        "independent methods is itself evidence. Keep the raw metrics available to show on request. "
        "Fold each parallel's corpus context INLINE with its entry, not in a separate methods section. "
        "EVERY presented entry carries its corpus-wide context inline, in two proportionate tiers. "
        "(a) Every entry states, in plain words, how common its shared material is across surviving Latin: "
        "line_search on the shared lemmas (use count_only:true — it returns just the deduped count "
        "cheaply), or the rare-word corpus_count where that is the entry's basis. (b) When that count is "
        "small enough to mean something (roughly under 40), also characterize the distribution in one "
        "line — who else, which era, verbatim quotation vs independent use — fetching the full "
        "line_search results (dedup applied) for that entry. Above ~40, give the number and say it is too "
        "common to signify, so the entry's interest rests on placement or theme — say which. If a count "
        "cannot be retrieved, the entry says the overlap is 'unquantified' rather than silently omitting "
        "it. If line_search reports capped:true the count is a floor: render it as 'at least N places', "
        "never 'N+'. When a rare-phrase/rare-word rarity metric and the line_search corpus check "
        "disagree, TRUST the line_search check — it is the direct corpus evidence. "
        "These corpus counts shift slightly as the corpus is cleaned, so when the user is recording a "
        "number for use elsewhere (a paper, a note), quote the corpus_version stamp the response carries "
        "alongside it ('8 places, corpus version 2026-08-16') so the figure names the state it came from. "
        "NEVER describe results you have not fetched. Do not claim the tail is 'all function words' or "
        "otherwise empty from a few visible entries or from memory of another run — genuine parallels "
        "keep appearing deep into the ranking, into the thousands. The ranking concentrates real "
        "parallels at the top; it never certifies the tail empty. "
        "Present ~25 entries, then ASK whether to continue, re-sort (by overall similarity, rarity, order "
        "in either poem, or number of agreeing methods), filter to a stretch of either text (a ref range "
        "via source_ref_prefix), or search other lines. Small sets (<10) need no batching. Before you "
        "close the list, sample a few deeper pages cheaply — a handful of entries near ranks 100, 300, "
        "and 1000 via fusion_search offset with a small limit — and describe what those bands actually "
        "look like in plain words (e.g. 'further down, the word-overlaps get thinner, but pairs worth a "
        "look keep turning up, and there are 3,900 candidates in this comparison — want me to keep going, "
        "or sweep a particular stretch of either poem?'). If you skip the sampling for time, close with "
        "what is certain — the number of remaining candidates and the offer to continue — without "
        "characterizing the unseen bands. The close is an open door, never a shut one. "
        "Label the ordering as YOURS — 'most interesting' is your judgement, never Tesserae's ranking; "
        "keep Tesserae's detections and your own interpretation distinct. "
        "If a rare section says too_large or skipped, offer to run rare_pairs / rare_words on its own. "
        "SURFACE THE LINK: when the response carries a web_url, include it with the results in plain "
        "words -- 'open this comparison in Tesserae's own interface' -- in the close and in any artifact "
        "footer; without it the link is invisible to the reader. "
        "OFFICIAL CHARTS: when the response carries a chart_url, attach or embed it -- it is the same "
        "distribution chart the site draws (where the parallels fall in one text), rendered server-side as "
        "an image, so every user sees the identical Tesserae chart. When it carries a history_url, attach "
        "that too: one 'history strip' image showing where each of the top shared phrases recurs across the "
        "corpus over time (one row per parallel, source and target marked), which answers 'where do these "
        "echoes sit in literary history' in a single picture instead of one chart per parallel. Prefer "
        "these official images over improvising charts from the raw numbers. The CONNECTION MAP below stays "
        "optional enrichment on top of them, for rich surfaces with an in-conversation hover layer. "
        "CONNECTION MAP: when the medium can display one (an HTML artifact, a notebook), OFFER or produce "
        "a connection map of the comparison -- one compare_texts response already carries everything it "
        "needs (both sides' line positions, strengths, which search found each, and the full line texts "
        "for a hover layer). Draw it the same way every time so every agent's map matches: the two texts "
        "are vertical axes scaled to their line counts (source right, target left, or by chronology); each "
        "parallel is a curve between its two lines; curve weight follows strength; color follows which "
        "search found it (ranked/fusion vs rare-word), with weaker top-band links a recessive gray; the "
        "few highlighted parallels get direct labels; hovering a curve shows both full lines with the "
        "plain-language corpus note; a table of the strongest sits beneath as the accessible fallback; the "
        "footer carries the corpus_version and the web_url. Offer, do not force -- a quick question does "
        "not need a graphic."
    )
    if fusion.get('status') == 'running':
        out['note'] = ('The ranked_parallels (fusion) section is still computing server-side. '
                       'Present the ready sections now, then call fusion_search with the same '
                       'source/target/language in ~30-60s to fill in the ranked_parallels section '
                       '(use fusion_search, not compare_texts, so the rare searches are not re-run). '
                       + common)
    else:
        out['note'] = common
    return out


def _t_cross_language(a):
    """Cross-language fusion — a source in one language vs a target in another
    (e.g. a Greek model behind a Latin poem). Synchronous POST /search; may take
    a few minutes on first run for a large pair."""
    body = {'source': a.get('source'), 'target': a.get('target'),
            'source_language': a.get('source_language', 'grc'),
            'target_language': a.get('target_language', 'la'),
            'match_type': 'crosslingual_fusion', 'min_matches': a.get('min_matches', 2)}
    r = requests.post(f"{API_BASE}/search", json=body, timeout=_FUSION_POLL_TIMEOUT)
    r.raise_for_status()
    d = r.json()
    results = (d.get('results') or [])[:30]
    return {'count': len(results),
            'parallels': [{'score': round(x.get('overall_score', 0), 2),
                           'source': {'ref': (x.get('source') or {}).get('ref'),
                                      'text': (x.get('source') or {}).get('text')},
                           'target': {'ref': (x.get('target') or {}).get('ref'),
                                      'text': (x.get('target') or {}).get('text')},
                           'matched': x.get('matched_words')}
                          for x in results]}


def _t_submit_feature_request(a):
    """File a feature/language/text/bug request. Requires explicit user sign-off
    first; feature/language/bug are auto-filed as a public GitHub issue (contact
    kept private)."""
    body = {'type': a.get('type') or a.get('request_type') or 'feature'}
    for k in ('title', 'problem', 'desired', 'example', 'context', 'contact'):
        if a.get(k):
            body[k] = a[k]
    return _post('/feature-request', body)


_STR = {"type": "string"}
TOOLS = [
    {"name": "get_languages",
     "description": "List Tesserae's languages (la Latin, grc Greek, en English, cop Coptic) and cross-language pairs.",
     "inputSchema": {"type": "object", "properties": {}},
     "fn": _t_get_languages},
    {"name": "list_texts",
     "description": "List texts (with their ids) for a language. Use a text's id as source/target for two-text searches. Filter with `contains` (author/work), since the full list is long.",
     "inputSchema": {"type": "object",
                     "properties": {"language": _STR, "contains": _STR, "limit": {"type": "integer"}},
                     "required": ["language"]},
     "fn": _t_list_texts},
    {"name": "line_search",
     "description": "Find corpus lines sharing words with a phrase (corpus-wide). The uniqueness check: few results (total) means distinctive wording. Counts collapse whole-work vs per-book/poem duplicates of the same line, AND same-passage duplicates that differ only by author/work spelling (e.g. cyprian vs cyprian_saint), so total is a true distinct-loci count. Set count_only:true to get just the counts (total, distinct_loci, capped) with no results payload — use this to quantify a commonplace cheaply; fetch full results only when the count is small enough to characterize. `capped` is true when the scan hit the result cap (default 500): then `total` is a floor (`total_at_least`) — treat it as 'at least N', not exact. SINGLE-WORD queries: a query that LITERALLY has one word can't co-occur with anything, so count_only returns `single_word:true` with `total` = the number of works that contain the word (a corpus document frequency, `unit:\"works\"`) — report as 'appears in N works', not co-occurring places; an all-stopword single word returns `unquantified:true` (total null). A MULTI-word query is always a co-occurrence count even if one word is too common to index alone: it returns the normal pair count plus `filtered_common_words` naming the common word(s) that were down-weighted — the count is real; say the pairing leans on the other word. Every response carries `corpus_version` (a date stamp of the corpus state); when the user is recording a count for use elsewhere, quote it with the number (e.g. '8 places, corpus version 2026-08-16'). search_type: 'lemma' (default) matches lines that share 2+ of the query's LEMMAS anywhere on the line — use this for words that co-occur but are NOT adjacent (e.g. 'Scythiam arces', 'lolium avenae'); 'exact' matches the query as an ADJACENT whole-word phrase (stopwords included literally, so 'ad Scythiam' matches only that contiguous phrase; a Latin enclitic on the final word is allowed, so 'arma virum' hits 'arma virumque') — for non-adjacent words use lemma; 'regex'. Each result carries `era` and `year` for its author, so you can chart WHERE ACROSS TIME the phrase recurs (a period or author timeline) — do that when a distribution over time would help the user see it. The response also carries `web_url`: a link that opens this same search in the Tesserae web app, which draws the timeline live and lets the user click a period or author to see just those citations. Offer that link when a visual or interactive view would help.",
     "inputSchema": {"type": "object",
                     "properties": {"query": _STR, "language": _STR, "search_type": _STR,
                                    "count_only": {"type": "boolean"}},
                     "required": ["query", "language"]},
     "fn": _t_line_search},
    {"name": "string_search",
     "description": "Wildcard / boolean / exact text search across the corpus (am*, AND/OR/NOT, \"phrases\").",
     "inputSchema": {"type": "object", "properties": {"query": _STR, "language": _STR},
                     "required": ["query", "language"]},
     "fn": _t_string_search},
    {"name": "rare_pairs",
     "description": "Rare two-word combinations shared by two texts (distinctive collocations), ranked by rarity. Fast two-text comparison.",
     "inputSchema": {"type": "object", "properties": {"source": _STR, "target": _STR, "language": _STR},
                     "required": ["source", "target", "language"]},
     "fn": _t_rare_pairs},
    {"name": "rare_words",
     "description": "Rare individual words shared by two texts, with corpus frequency (fewer texts = rarer = stronger signal).",
     "inputSchema": {"type": "object", "properties": {"source": _STR, "target": _STR, "language": _STR},
                     "required": ["source", "target", "language"]},
     "fn": _t_rare_words},
    {"name": "compare_texts",
     "description": "Recommended for comparing two texts. Runs all three automated pairwise searches at once — fusion (ranked parallels across ten signals), rare shared phrases, and rare shared words — and returns them as labeled sections. The rare sections return immediately; the fusion section takes a few minutes on a first run, so it may come back status 'running' — call compare_texts again with the same arguments shortly to fill it in (cached afterward). Direction is symmetric (same parallels and scores either way), but for allusion study put the earlier/model text as source and the later/alluding text as target so the labels read correctly. IMPORTANT: read the response 'note' — it specifies how to present the results (one merged, interest-ranked list, not by search type).",
     "inputSchema": {"type": "object", "properties": {"source": _STR, "target": _STR, "language": _STR},
                     "required": ["source", "target", "language"]},
     "fn": _t_compare_texts},
    {"name": "fusion_search",
     "description": ("Ranked fusion parallels for two texts across ten similarity signals — the passages "
                     "most likely to be genuine parallels, strongest first. Returns a page (default 100, "
                     "up to 500 via limit); pass offset (100, 200, ...) to page deeper, since real "
                     "parallels also appear below the top. To answer a question about ONE section/poem, "
                     "use source_ref_prefix / target_ref_prefix — these filter the FULL result set (not "
                     "just the page) by ref, so nothing is lost to the cap; a trailing dot pins a number "
                     "(e.g. source_ref_prefix=\"ecl. 1.\" matches book/poem 1 but not 10). min_score drops "
                     "weak matches. Response gives count (after filters) and total (before). First run "
                     "takes a few minutes (cached after); returns status 'running' until ready. Scores are "
                     "relative to the specific pair (frequency baselines are computed per comparison), so "
                     "the same parallel can score differently across pairings — compare ranks within one "
                     "run, not absolute scores across runs. Returns ~25 parallels by default (raise with "
                     "limit, up to 500). Direction is symmetric, but for allusion study put the "
                     "earlier/model text as source and the later/alluding text as target. Present results "
                     "as one interest-ranked list of ~25, labelled as your own ordering (never as "
                     "Tesserae's), each entry quoting its fused_score/channel_count; then ask to continue "
                     "or re-sort."),
     "inputSchema": {"type": "object",
                     "properties": {"source": _STR, "target": _STR, "language": _STR,
                                    "offset": {"type": "integer"}, "limit": {"type": "integer"},
                                    "source_ref_prefix": _STR, "target_ref_prefix": _STR,
                                    "min_score": {"type": "number"}},
                     "required": ["source", "target", "language"]},
     "fn": _t_fusion_search},
    {"name": "cross_language",
     "description": "Cross-language parallels between two texts in DIFFERENT languages (e.g. a Greek source behind a Latin poem). Give source/target ids (from list_texts) and their languages. Synchronous; may take a few minutes on a large pair.",
     "inputSchema": {"type": "object",
                     "properties": {"source": _STR, "target": _STR,
                                    "source_language": _STR, "target_language": _STR,
                                    "min_matches": {"type": "integer"}},
                     "required": ["source", "target", "source_language", "target_language"]},
     "fn": _t_cross_language},
    {"name": "submit_feature_request",
     "description": "File a feature / language / text / bug request. ONLY after the user explicitly confirms; warn them feature/language/bug requests become a public GitHub issue (contact kept private). type: feature|language|text|bug.",
     "inputSchema": {"type": "object",
                     "properties": {"type": _STR, "title": _STR, "problem": _STR, "desired": _STR,
                                    "example": _STR, "context": _STR, "contact": _STR},
                     "required": ["type"]},
     "fn": _t_submit_feature_request},
]
_TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}


# --------------------------------------------------------------------------
# JSON-RPC / MCP protocol
# --------------------------------------------------------------------------
def _result(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def _error(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def _handle(msg):
    """Return a JSON-RPC response dict, or None for notifications."""
    if not isinstance(msg, dict):
        return _error(None, -32600, "Invalid Request")
    method = msg.get('method')
    mid = msg.get('id')
    params = msg.get('params') or {}

    if method == 'initialize':
        return _result(mid, {
            "protocolVersion": params.get('protocolVersion') or DEFAULT_PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": (
                "Tesserae finds intertextual parallels (allusions, echoes, borrowings) in Latin, "
                "Greek, English, and Coptic literature. It does the searching; you orchestrate and "
                "interpret. Read the results and discuss them freely, including your own literary "
                "judgement — no need to constantly disclaim it. The one rule: don't present a "
                "parallel Tesserae didn't return as if it had; anything you add beyond the results "
                "is simply your own reading, offered normally.\n"
                "On the first Tesserae request in a conversation, briefly orient the user: it can "
                "compare two texts (a comprehensive ranked search plus fast rare-phrase and "
                "rare-word passes), search the whole corpus, and match across languages. For "
                "'compare these two texts', default to compare_texts, which runs all three pairwise "
                "searches and returns labeled sections — present each section, then a short "
                "synthesis. Before running a big comparison the first time, briefly offer the user a "
                "depth choice (a short menu, not a sprawl): the full comparison (ranked parallels plus "
                "a corpus-rarity check on every entry and the distribution and history charts, most "
                "thorough, takes a few minutes), or a quick pass (top parallels only, no per-entry "
                "corpus checks, back in under a minute). Run the full version if they don't want to "
                "choose. Recall is strongest near the top but genuine parallels also appear "
                "further down, so offer to page deeper (fusion_search with offset) when useful. "
                "Typical flow: list_texts -> compare_texts -> line_search to test how distinctive a "
                "phrase is across the corpus."),
        })
    if method in ('notifications/initialized', 'initialized', 'notifications/cancelled'):
        return None  # notification: no response
    if method == 'ping':
        return _result(mid, {})
    if method == 'tools/list':
        return _result(mid, {"tools": [{"name": t["name"], "description": t["description"],
                                        "inputSchema": t["inputSchema"]} for t in TOOLS]})
    if method == 'tools/call':
        name = params.get('name')
        args = params.get('arguments') or {}
        tool = _TOOLS_BY_NAME.get(name)
        if not tool:
            return _error(mid, -32602, f"Unknown tool: {name}")
        try:
            data = tool["fn"](args)
            text = json.dumps(data, ensure_ascii=False)[:120000]
            return _result(mid, {"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as e:
            logger.warning("MCP tool %s failed: %s", name, e)
            return _result(mid, {"content": [{"type": "text", "text": f"Error running {name}: {e}"}],
                                 "isError": True})
    if mid is not None:
        return _error(mid, -32601, f"Method not found: {method}")
    return None


@mcp_http_bp.route('/mcp', methods=['POST', 'GET', 'OPTIONS'])
def mcp_endpoint():
    if request.method == 'OPTIONS':
        return Response(status=204)
    if request.method == 'GET':
        # This server never initiates messages, so it offers no SSE stream.
        return Response('Method Not Allowed', status=405)

    # OAuth: the connector must present a bearer token (issued via /api/oauth).
    # Missing/invalid -> 401 with WWW-Authenticate, which triggers the client's
    # OAuth discovery + registration flow. (The resource behind this is the open
    # Tesserae API, so the token is ceremonial — see backend/blueprints/mcp_oauth.)
    from backend.blueprints.mcp_oauth import verify_access_token, PRM_URL
    auth = request.headers.get('Authorization', '')
    if not (auth.startswith('Bearer ') and verify_access_token(auth[7:])):
        resp = jsonify({"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32001, "message": "Unauthorized"}})
        resp.status_code = 401
        resp.headers['WWW-Authenticate'] = f'Bearer resource_metadata="{PRM_URL}"'
        return resp

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify(_error(None, -32700, "Parse error")), 400

    extra_headers = {}
    if isinstance(payload, dict) and payload.get('method') == 'initialize':
        extra_headers['Mcp-Session-Id'] = uuid.uuid4().hex

    if isinstance(payload, list):
        responses = [r for r in (_handle(m) for m in payload) if r is not None]
        body = responses if responses else None
    else:
        body = _handle(payload)

    if body is None:
        return Response(status=202, headers=extra_headers)  # notification(s) only
    resp = jsonify(body)
    for k, v in extra_headers.items():
        resp.headers[k] = v
    return resp
