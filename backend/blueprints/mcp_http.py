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

import requests
from flask import Blueprint, request, jsonify, Response

logger = logging.getLogger(__name__)
mcp_http_bp = Blueprint('mcp_http', __name__)

API_BASE = os.environ.get('TESSERAE_API_BASE', 'https://tesserae.caset.buffalo.edu/api').rstrip('/')
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
    d = _post('/line-search', {'query': a.get('query', ''),
                               'language': a.get('language', 'la'),
                               'search_type': a.get('search_type', 'lemma')})
    return {'query': a.get('query'), 'total': d.get('total'),
            'results': [{'locus': r.get('locus'), 'author': r.get('author'),
                         'work': r.get('work'), 'text': r.get('text'),
                         'matched_words': r.get('matched_words')}
                        for r in (d.get('results') or [])[:40]]}


def _t_string_search(a):
    d = _post('/wildcard-search', {'query': a.get('query', ''), 'language': a.get('language', 'la')})
    return {'query': a.get('query'), 'total_matches': d.get('total_matches'),
            'results': [{'ref': r.get('ref') or r.get('reference'), 'author': r.get('author'),
                         'title': r.get('title'), 'text': r.get('text')}
                        for r in (d.get('results') or [])[:40]]}


def _t_rare_pairs(a, timeout=None):
    d = _post('/rare-bigram-search', {'source': a.get('source'), 'target': a.get('target'),
                                      'language': a.get('language', 'la')}, timeout=timeout)
    return {'shared_rare_count': d.get('shared_rare_count'),
            'results': [{'bigram': f"{r.get('display1', r.get('word1'))} {r.get('display2', r.get('word2'))}",
                         'rarity_percent': r.get('rarity_percent'),
                         'source_locations': (r.get('source_locations') or [])[:5],
                         'target_locations': (r.get('target_locations') or [])[:5]}
                        for r in (d.get('results') or [])[:40]]}


def _t_rare_words(a, timeout=None):
    d = _post('/hapax-search', {'source': a.get('source'), 'target': a.get('target'),
                                'language': a.get('language', 'la')}, timeout=timeout)
    return {'shared_rare_count': d.get('shared_rare_count'),
            'results': [{'word': r.get('display_form') or r.get('lemma'),
                         'corpus_count': r.get('corpus_count'), 'proper_noun': r.get('is_proper_noun'),
                         'source_locations': (r.get('source_locations') or [])[:5],
                         'target_locations': (r.get('target_locations') or [])[:5]}
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
        if lim > 0:
            p['limit'] = lim
    except (TypeError, ValueError):
        pass
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
    return _fusion_poll(_fusion_params(a), _FUSION_MCP_BUDGET)


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
    out = {
        'source': a.get('source'), 'target': a.get('target'), 'language': a.get('language', 'la'),
        'ranked_parallels': fusion,      # fusion: strongest overall parallels
        'rare_phrases': rare_phrases,    # distinctive shared two-word collocations
        'rare_words': rare_words,        # distinctive shared individual words
    }
    common = ('Present each ready section on its own (Ranked parallels / Rare shared phrases / '
              'Rare shared words), then a short synthesis. Fusion ranks the strongest overall '
              'parallels; the rare passes surface distinctive shared wording fusion may rank lower. '
              'If a rare section says too_large or skipped, offer to run rare_pairs / rare_words on '
              'its own. Genuine parallels also appear below fusion’s top results, so offer to page '
              'deeper (fusion_search with offset) when useful.')
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
     "description": "Find corpus lines sharing words with a phrase (corpus-wide). The uniqueness check: few results means distinctive wording. search_type: lemma (default) | exact | regex.",
     "inputSchema": {"type": "object",
                     "properties": {"query": _STR, "language": _STR, "search_type": _STR},
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
     "description": "Recommended for comparing two texts. Runs all three automated pairwise searches at once — fusion (ranked parallels across ten signals), rare shared phrases, and rare shared words — and returns them as labeled sections. The rare sections return immediately; the fusion section takes a few minutes on a first run, so it may come back status 'running' — call compare_texts again with the same arguments shortly to fill it in (cached afterward).",
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
                     "takes a few minutes (cached after); returns status 'running' until ready."),
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
                "synthesis. Recall is strongest near the top but genuine parallels also appear "
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
