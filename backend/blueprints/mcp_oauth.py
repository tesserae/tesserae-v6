"""
Ceremonial OAuth 2.1 for the Tesserae MCP connector (served under /api/oauth).

Claude's custom-connector flow requires OAuth. Tesserae's API is open (no
accounts, nothing to protect), so this is a *ceremonial* OAuth server: dynamic
client registration is auto-granted, authorization auto-approves (no login
screen), and access tokens are opaque HMAC-signed strings the /api/mcp endpoint
accepts. Because there is nothing sensitive behind it, the tokens don't need to
be bulletproof — the point is only to satisfy the client's OAuth handshake.

Stateless by design: authorization codes and access tokens are HMAC-signed with
SESSION_SECRET, so any of the (multiple) worker processes can issue and verify
them without shared storage. Everything lives under /api so it is routed to
Flask without an Apache change.
"""
import os
import json
import time
import hmac
import base64
import hashlib
import secrets
import logging

from flask import Blueprint, request, jsonify, redirect

logger = logging.getLogger(__name__)
mcp_oauth_bp = Blueprint('mcp_oauth', __name__)

PUBLIC_BASE = os.environ.get('TESSERAE_PUBLIC_BASE', 'https://tesserae.caset.buffalo.edu').rstrip('/')
ISSUER = f"{PUBLIC_BASE}/api/oauth"
MCP_RESOURCE = f"{PUBLIC_BASE}/api/mcp"
PRM_URL = f"{PUBLIC_BASE}/api/mcp/.well-known/oauth-protected-resource"
CODE_TTL = 600            # authorization code lifetime (10 min)
TOKEN_TTL = 90 * 24 * 3600  # access token lifetime (the resource is public anyway)


# --------------------------------------------------------------------------
# HMAC-signed, stateless tokens/codes
# --------------------------------------------------------------------------
def _key():
    return (os.environ.get('SESSION_SECRET') or 'tesserae-mcp-oauth-fallback-key').encode()


def _b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


def _b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + '=' * (-len(s) % 4))


def _sign(payload: dict) -> str:
    body = _b64u(json.dumps(payload, separators=(',', ':'), sort_keys=True).encode())
    sig = _b64u(hmac.new(_key(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def _unsign(token: str):
    """Return the payload dict if the signature is valid and not expired, else None."""
    try:
        body, sig = token.split('.', 1)
        expected = _b64u(hmac.new(_key(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64u_decode(body))
        if float(payload.get('exp', 0)) < time.time():
            return None
        return payload
    except Exception:
        return None


def verify_access_token(token: str) -> bool:
    """Public helper used by the /api/mcp endpoint."""
    p = _unsign(token or '')
    return bool(p and p.get('typ') == 'at')


# --------------------------------------------------------------------------
# Discovery metadata
# --------------------------------------------------------------------------
def _as_metadata():
    return {
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "registration_endpoint": f"{ISSUER}/register",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "code_challenge_methods_supported": ["S256", "plain"],
        "token_endpoint_auth_methods_supported": ["none"],
        "scopes_supported": ["mcp"],
    }


# Authorization-server metadata — served at several candidate paths so different
# clients' discovery rules all land on Flask (all under /api, no Apache change).
@mcp_oauth_bp.route('/oauth/.well-known/oauth-authorization-server', methods=['GET'])
@mcp_oauth_bp.route('/.well-known/oauth-authorization-server', methods=['GET'])
@mcp_oauth_bp.route('/oauth/.well-known/openid-configuration', methods=['GET'])
def authorization_server_metadata():
    return jsonify(_as_metadata())


# Protected-resource metadata (RFC 9728) — the 401 from /api/mcp points here.
@mcp_oauth_bp.route('/mcp/.well-known/oauth-protected-resource', methods=['GET'])
@mcp_oauth_bp.route('/.well-known/oauth-protected-resource', methods=['GET'])
def protected_resource_metadata():
    return jsonify({
        "resource": MCP_RESOURCE,
        "authorization_servers": [ISSUER],
        "scopes_supported": ["mcp"],
        "bearer_methods_supported": ["header"],
    })


# --------------------------------------------------------------------------
# Dynamic client registration (RFC 7591) — auto-grant
# --------------------------------------------------------------------------
@mcp_oauth_bp.route('/oauth/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    resp = {
        "client_id": "tess-" + secrets.token_hex(8),
        "client_id_issued_at": int(time.time()),
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "redirect_uris": data.get("redirect_uris", []),
    }
    for k in ("client_name", "scope", "client_uri"):
        if data.get(k):
            resp[k] = data[k]
    return jsonify(resp), 201


# --------------------------------------------------------------------------
# Authorization endpoint — auto-approve (no login; the resource is public)
# --------------------------------------------------------------------------
@mcp_oauth_bp.route('/oauth/authorize', methods=['GET'])
def authorize():
    redirect_uri = request.args.get('redirect_uri')
    state = request.args.get('state')
    code_challenge = request.args.get('code_challenge')
    code_challenge_method = request.args.get('code_challenge_method', 'plain')
    if not redirect_uri or not code_challenge:
        return jsonify({"error": "invalid_request",
                        "error_description": "redirect_uri and code_challenge are required"}), 400
    code = _sign({
        "typ": "code",
        "ru": redirect_uri,
        "cc": code_challenge,
        "ccm": code_challenge_method,
        "exp": int(time.time()) + CODE_TTL,
    })
    sep = '&' if '?' in redirect_uri else '?'
    location = f"{redirect_uri}{sep}code={code}"
    if state is not None:
        location += f"&state={state}"
    return redirect(location, code=302)


# --------------------------------------------------------------------------
# Token endpoint — authorization_code + PKCE
# --------------------------------------------------------------------------
@mcp_oauth_bp.route('/oauth/token', methods=['POST'])
def token():
    form = request.form if request.form else (request.get_json(silent=True) or {})
    if form.get('grant_type') != 'authorization_code':
        return jsonify({"error": "unsupported_grant_type"}), 400

    payload = _unsign(form.get('code') or '')
    if not payload or payload.get('typ') != 'code':
        return jsonify({"error": "invalid_grant", "error_description": "bad or expired code"}), 400
    if payload.get('ru') != form.get('redirect_uri'):
        return jsonify({"error": "invalid_grant", "error_description": "redirect_uri mismatch"}), 400

    # PKCE
    verifier = form.get('code_verifier') or ''
    if payload.get('ccm') == 'S256':
        calc = _b64u(hashlib.sha256(verifier.encode()).digest())
        if not hmac.compare_digest(calc, payload.get('cc', '')):
            return jsonify({"error": "invalid_grant", "error_description": "PKCE verification failed"}), 400
    else:  # plain
        if not hmac.compare_digest(verifier, payload.get('cc', '')):
            return jsonify({"error": "invalid_grant", "error_description": "PKCE verification failed"}), 400

    access = _sign({"typ": "at", "scope": "mcp", "exp": int(time.time()) + TOKEN_TTL})
    return jsonify({
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": TOKEN_TTL,
        "scope": "mcp",
    })
