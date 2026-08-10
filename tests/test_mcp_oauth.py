"""End-to-end test of the ceremonial OAuth flow for the MCP connector.

Register -> authorize (auto-approve, 302 with code) -> token (PKCE) -> gated
/api/mcp (401 without a token, 200 with it). No network needed.
"""
import os
import hashlib
import urllib.parse as up

os.environ.setdefault('SESSION_SECRET', 'test-oauth-secret')

import pytest
from flask import Flask

from backend.blueprints.mcp_oauth import mcp_oauth_bp, _b64u, verify_access_token
from backend.blueprints.mcp_http import mcp_http_bp


@pytest.fixture()
def client():
    app = Flask(__name__)
    app.register_blueprint(mcp_oauth_bp)
    app.register_blueprint(mcp_http_bp)
    return app.test_client()


def _auth_code(client, challenge):
    r = client.get('/oauth/authorize?response_type=code&client_id=x'
                   '&redirect_uri=https://claude.ai/cb'
                   f'&code_challenge={challenge}&code_challenge_method=S256&state=st1')
    assert r.status_code == 302
    q = up.parse_qs(up.urlparse(r.headers['Location']).query)
    assert q['state'][0] == 'st1'
    return q['code'][0]


def test_dynamic_registration(client):
    r = client.post('/oauth/register', json={'redirect_uris': ['https://claude.ai/cb']})
    assert r.status_code == 201
    assert r.get_json()['client_id'].startswith('tess-')


def test_full_pkce_flow_and_gate(client):
    verifier = 'verifier-1234567890-verifier-1234567890-verifier'
    challenge = _b64u(hashlib.sha256(verifier.encode()).digest())
    code = _auth_code(client, challenge)

    tok = client.post('/oauth/token', data={
        'grant_type': 'authorization_code', 'code': code,
        'redirect_uri': 'https://claude.ai/cb', 'code_verifier': verifier})
    assert tok.status_code == 200
    access = tok.get_json()['access_token']
    assert tok.get_json()['token_type'] == 'Bearer'
    assert verify_access_token(access)

    # /mcp is gated
    no_auth = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                                        'params': {'protocolVersion': '2025-06-18'}})
    assert no_auth.status_code == 401
    assert 'resource_metadata=' in no_auth.headers.get('WWW-Authenticate', '')

    ok = client.post('/mcp', json={'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
                                   'params': {'protocolVersion': '2025-06-18'}},
                     headers={'Authorization': 'Bearer ' + access})
    assert ok.status_code == 200
    assert ok.get_json()['result']['protocolVersion'] == '2025-06-18'


def test_bad_pkce_rejected(client):
    verifier = 'verifier-1234567890-verifier-1234567890-verifier'
    challenge = _b64u(hashlib.sha256(verifier.encode()).digest())
    code = _auth_code(client, challenge)
    bad = client.post('/oauth/token', data={
        'grant_type': 'authorization_code', 'code': code,
        'redirect_uri': 'https://claude.ai/cb', 'code_verifier': 'WRONG'})
    assert bad.status_code == 400


def test_discovery_metadata(client):
    asm = client.get('/oauth/.well-known/oauth-authorization-server').get_json()
    assert asm['token_endpoint'].endswith('/api/oauth/token')
    assert 'S256' in asm['code_challenge_methods_supported']
    prm = client.get('/mcp/.well-known/oauth-protected-resource').get_json()
    assert prm['authorization_servers'] == [asm['issuer']]
