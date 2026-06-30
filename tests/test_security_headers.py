import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Set environment variables for testing before importing app
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SESSION_SECRET"] = "test-secret"
os.environ["DEPLOYMENT_ENV"] = "test"

from backend.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_security_headers_are_present(client):
    # Make request to any endpoint (e.g. root SPA endpoint)
    response = client.get('/')
    assert response.headers.get('X-Content-Type-Options') == 'nosniff'
    assert response.headers.get('X-Frame-Options') == 'DENY'
    # Strict-Transport-Security should be present in non-dev DEPLOYMENT_ENV
    assert response.headers.get('Strict-Transport-Security') == 'max-age=31536000; includeSubDomains'

def test_cors_headers_restrict_origins(client):
    # Allowed origin: should echo back
    headers = {'Origin': 'http://localhost:5173'}
    response = client.get('/api/texts', headers=headers)
    assert response.headers.get('Access-Control-Allow-Origin') == 'http://localhost:5173'

    # Disallowed origin: should not echo back/should fail CORS
    headers = {'Origin': 'http://malicious.org'}
    response = client.get('/api/texts', headers=headers)
    assert response.headers.get('Access-Control-Allow-Origin') is None
