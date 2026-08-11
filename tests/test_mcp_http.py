"""Tests for the remote MCP-over-HTTP protocol layer (backend.blueprints.mcp_http).

Exercises the JSON-RPC dispatch without any network — tool bodies are monkeypatched.
"""
import json

import backend.blueprints.mcp_http as M

ALL_TOOLS = {"get_languages", "list_texts", "line_search", "string_search",
             "rare_pairs", "rare_words", "fusion_search", "cross_language",
             "submit_feature_request"}


def test_initialize_echoes_protocol_and_serverinfo():
    r = M._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                   "params": {"protocolVersion": "2025-06-18"}})
    assert r["result"]["protocolVersion"] == "2025-06-18"
    assert r["result"]["serverInfo"]["name"] == "tesserae"
    assert "tools" in r["result"]["capabilities"]


def test_initialize_defaults_protocol_when_missing():
    r = M._handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert r["result"]["protocolVersion"] == M.DEFAULT_PROTOCOL


def test_tools_list_has_all_tools_with_schemas():
    r = M._handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = r["result"]["tools"]
    assert ALL_TOOLS <= {t["name"] for t in tools}
    for t in tools:
        assert t["inputSchema"]["type"] == "object"
        assert t["description"]


def test_ping_returns_empty_result():
    assert M._handle({"jsonrpc": "2.0", "id": 3, "method": "ping"})["result"] == {}


def test_notification_returns_none():
    assert M._handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_unknown_method_is_method_not_found():
    r = M._handle({"jsonrpc": "2.0", "id": 9, "method": "does/not/exist"})
    assert r["error"]["code"] == -32601


def test_tools_call_unknown_tool_errors():
    r = M._handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                   "params": {"name": "nope", "arguments": {}}})
    assert r["error"]["code"] == -32602


def test_tools_call_dispatches_and_wraps_result(monkeypatch):
    monkeypatch.setitem(M._TOOLS_BY_NAME, "get_languages",
                        {**M._TOOLS_BY_NAME["get_languages"], "fn": lambda a: {"ok": True}})
    r = M._handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                   "params": {"name": "get_languages", "arguments": {}}})
    assert r["result"]["isError"] is False
    assert json.loads(r["result"]["content"][0]["text"]) == {"ok": True}


def test_tools_call_error_is_wrapped_not_raised(monkeypatch):
    def boom(a):
        raise ValueError("kaboom")
    monkeypatch.setitem(M._TOOLS_BY_NAME, "get_languages",
                        {**M._TOOLS_BY_NAME["get_languages"], "fn": boom})
    r = M._handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                   "params": {"name": "get_languages", "arguments": {}}})
    assert r["result"]["isError"] is True
    assert "kaboom" in r["result"]["content"][0]["text"]
