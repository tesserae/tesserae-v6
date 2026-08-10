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
SERVER_INFO = {"name": "tesserae", "version": "1.0.0"}
DEFAULT_PROTOCOL = "2025-06-18"
_TIMEOUT = 90
_FUSION_POLL_TIMEOUT = 330   # seconds to block-and-poll a fresh fusion run


# --------------------------------------------------------------------------
# API helpers
# --------------------------------------------------------------------------
def _get(path, params=None):
    r = requests.get(f"{API_BASE}{path}", params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


def _post(path, body):
    r = requests.post(f"{API_BASE}{path}", json=body, timeout=_TIMEOUT)
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


def _t_rare_pairs(a):
    d = _post('/rare-bigram-search', {'source': a.get('source'), 'target': a.get('target'),
                                      'language': a.get('language', 'la')})
    return {'shared_rare_count': d.get('shared_rare_count'),
            'results': [{'bigram': f"{r.get('display1', r.get('word1'))} {r.get('display2', r.get('word2'))}",
                         'rarity_percent': r.get('rarity_percent'),
                         'source_locations': (r.get('source_locations') or [])[:5],
                         'target_locations': (r.get('target_locations') or [])[:5]}
                        for r in (d.get('results') or [])[:40]]}


def _t_rare_words(a):
    d = _post('/hapax-search', {'source': a.get('source'), 'target': a.get('target'),
                                'language': a.get('language', 'la')})
    return {'shared_rare_count': d.get('shared_rare_count'),
            'results': [{'word': r.get('display_form') or r.get('lemma'),
                         'corpus_count': r.get('corpus_count'), 'proper_noun': r.get('is_proper_noun'),
                         'source_locations': (r.get('source_locations') or [])[:5],
                         'target_locations': (r.get('target_locations') or [])[:5]}
                        for r in (d.get('results') or [])[:40]]}


def _t_fusion_search(a):
    """Full fusion — blocks and polls the GET fusion endpoint until complete
    (MCP tools have no short timeout, so a few-minute wait is fine)."""
    params = {'source': a.get('source'), 'target': a.get('target'), 'language': a.get('language', 'la')}
    deadline = time.time() + _FUSION_POLL_TIMEOUT
    while True:
        d = _get('/fusion-search', params)
        status = d.get('status')
        if status == 'complete':
            return {'status': 'complete', 'count': d.get('count'), 'parallels': d.get('parallels')}
        if status == 'error':
            return {'status': 'error', 'error': d.get('error')}
        if time.time() > deadline:
            return {'status': 'running',
                    'note': 'Still computing after a few minutes; call fusion_search again shortly to get the cached result.'}
        time.sleep(15)


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
    {"name": "fusion_search",
     "description": "The flagship full fusion comparison of two texts — ranks the passages most likely to be genuine parallels across ten similarity channels. May take a few minutes on first run; cached afterward.",
     "inputSchema": {"type": "object", "properties": {"source": _STR, "target": _STR, "language": _STR},
                     "required": ["source", "target", "language"]},
     "fn": _t_fusion_search},
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
            "instructions": ("Tesserae finds intertextual parallels in classical literature. "
                             "Typical flow: list_texts -> rare_pairs/rare_words or fusion_search "
                             "-> line_search to test corpus-uniqueness -> interpret. Keep Tesserae's "
                             "results (transparent, reproducible) separate from your own interpretation."),
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
