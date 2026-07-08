#!/usr/bin/env python3
"""
Smoke tests for Flask application initialization and basic routes.
Ensures application starts up and registers blueprints without requiring
a populated PostgreSQL database.
"""

import os
import sys
import pytest
from flask import Flask

# Ensure project root is in python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(scope="module")
def app_instance():
    """Module-scoped fixture yielding Flask app configured with in-memory DB."""
    # Temporarily set environment variables to avoid database connection errors
    # and configure direct API server prefixes.
    old_db = os.environ.get("DATABASE_URL")
    old_direct = os.environ.get("TESSERAE_DIRECT_SERVER")
    old_secret = os.environ.get("SESSION_SECRET")
    
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["TESSERAE_DIRECT_SERVER"] = "1"
    os.environ["SESSION_SECRET"] = "test-secret-key"
    
    try:
        from backend.app import app
        yield app
    finally:
        # Restore environment variables
        if old_db is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_db
            
        if old_direct is None:
            os.environ.pop("TESSERAE_DIRECT_SERVER", None)
        else:
            os.environ["TESSERAE_DIRECT_SERVER"] = old_direct

        if old_secret is None:
            os.environ.pop("SESSION_SECRET", None)
        else:
            os.environ["SESSION_SECRET"] = old_secret


def test_app_initialization(app_instance):
    """Confirm Flask app initializes and is of correct instance type."""
    assert app_instance is not None
    assert isinstance(app_instance, Flask)
    assert app_instance.name == "backend.app"


def test_blueprint_registration(app_instance):
    """Verify core blueprints are registered with correct prefixes."""
    blueprints = app_instance.blueprints
    
    # Check that core search and corpus blueprints are present
    assert "search" in blueprints
    assert "corpus" in blueprints
    assert "hapax" in blueprints
    assert "fusion" in blueprints
    assert "admin" in blueprints
    assert "intertext" in blueprints


def test_health_check_endpoints(app_instance):
    """Verify that basic health check endpoints return successful status."""
    with app_instance.test_client() as client:
        # 1. Root health check
        resp1 = client.get("/health")
        assert resp1.status_code == 200
        data1 = resp1.get_json()
        assert data1 == {"status": "ok", "message": "Tesserae V6 is running"}
        
        # 2. Prefixed API health check
        resp2 = client.get("/api/health")
        assert resp2.status_code == 200
        data2 = resp2.get_json()
        assert data2 == {"status": "ok", "message": "Tesserae V6 is running"}


def test_version_endpoint(app_instance):
    """Verify version endpoint returns git version metadata structure."""
    with app_instance.test_client() as client:
        resp = client.get("/api/version")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "version" in data
        assert "last_updated" in data
