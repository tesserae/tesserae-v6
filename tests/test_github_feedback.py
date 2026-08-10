"""Tests for backend.github_feedback — the gate that guards AI-protocol
feature requests from filing GitHub issues unless explicitly configured.

The critical safety property: with no token/repo configured, GitHub filing is
OFF and create_feedback_issue() is a no-op returning None (requests fall back to
the private DB + email path).
"""
import backend.github_feedback as gf


def _clear_env(monkeypatch):
    for k in ('GITHUB_FEEDBACK_TOKEN', 'GITHUB_FEEDBACK_REPO', 'FEEDBACK_GITHUB_ENABLED'):
        monkeypatch.delenv(k, raising=False)


def test_disabled_when_unconfigured(monkeypatch):
    _clear_env(monkeypatch)
    assert gf.github_feedback_enabled() is False


def test_disabled_with_token_but_no_repo(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv('GITHUB_FEEDBACK_TOKEN', 'x')
    assert gf.github_feedback_enabled() is False


def test_enabled_with_token_and_repo(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv('GITHUB_FEEDBACK_TOKEN', 'x')
    monkeypatch.setenv('GITHUB_FEEDBACK_REPO', 'org/repo')
    assert gf.github_feedback_enabled() is True


def test_kill_switch_off(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv('GITHUB_FEEDBACK_TOKEN', 'x')
    monkeypatch.setenv('GITHUB_FEEDBACK_REPO', 'org/repo')
    monkeypatch.setenv('FEEDBACK_GITHUB_ENABLED', 'false')
    assert gf.github_feedback_enabled() is False


def test_create_issue_noop_when_disabled(monkeypatch):
    """Must never call the network when disabled."""
    _clear_env(monkeypatch)

    def _boom(*a, **k):
        raise AssertionError("requests.post must not be called when disabled")

    monkeypatch.setattr(gf.requests, 'post', _boom)
    assert gf.create_feedback_issue('t', 'b', ['from-ai-protocol', 'feature']) is None
