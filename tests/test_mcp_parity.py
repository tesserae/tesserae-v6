"""Keeps the MCP connector (backend/blueprints/mcp_http.py) in step with the
site's own public API without a human having to notice the drift.

WHY THIS EXISTS

The connector wraps the site's API routes in AI-facing tools, by hand. Five
gaps between the two were found on 2026-09-10 only because someone sat down
and compared them line by line (see the parity report on branch
feat/connector-parity). Nothing forced that comparison, and nothing would
force the next one.

This test walks the live Flask url_map, keeps only the routes a research/AI
client could plausibly want (excluding admin, auth, internal poll/cancel/
stream variants, and the rest of the housekeeping surface -- see
_is_candidate_route below), and requires every one of them to appear in
backend/blueprints/mcp_manifest.MANIFEST, mapped to either the connector
tool(s) that cover it or a SITE_ONLY entry with a one-line reason. A route in
neither fails with a message telling the fixer what to do. The reverse check
(every tool names at least one route) catches a tool that has quietly stopped
matching anything real.

This is a fitness function, not a completeness audit of the manifest's prose:
it enforces that a DECISION was recorded, not that the decision was the right
one -- that judgment call is exactly what the failure message asks a human
(or the PR reviewer instructed by .github/workflows) to make.
"""
import re

import pytest

from backend.app import app
from backend.blueprints.mcp_manifest import MANIFEST
from backend.blueprints.mcp_http import TOOLS


# Path segments (after stripping <converter:> and a trailing .json/.csv/.html
# extension) that mark a route as NOT a candidate for connector coverage: admin
# surfaces, auth/session/user management, and assorted internal machinery this
# test's owner (the connector parity task, 2026-09-10) was told to exclude.
_EXCLUDE_SEGMENTS = {
    'admin', 'auth', 'oauth', 'login', 'logout', 'me', 'my', 'users', 'roles',
    'preferences', 'settings', 'audit-log', 'analytics', 'concurrency', 'jobs',
    'cache', 'embeddings', 'lemma-cache', 'bigram-cache', 'frequency-cache',
    'search-cache', 'dictionary-review', 'requests', 'feedback', 'features',
    'downloads', 'docs', 'mcp', '.well-known',
}
_INTERNAL_SUFFIX_RE = re.compile(r'-(poll|cancel|stream)$')
_EXT_RE = re.compile(r'\.(json|csv|html)$')
_CONVERTER_RE = re.compile(r'<[^>]*>')

# Non-API scaffolding that is never a candidate regardless of the segment rule.
_ALWAYS_EXCLUDE = {'/', '/<path:filename>', '/health', '/legacy'}


def _is_candidate_route(rule):
    """True for a route the connector might plausibly need to cover."""
    if rule in _ALWAYS_EXCLUDE:
        return False
    if not rule.startswith('/api/'):
        return False
    for seg in rule[len('/api/'):].split('/'):
        if not seg:
            continue
        base = _EXT_RE.sub('', _CONVERTER_RE.sub('', seg))
        if base in _EXCLUDE_SEGMENTS:
            return False
    if _INTERNAL_SUFFIX_RE.search(rule):
        return False
    return True


def _public_routes():
    return sorted({str(r) for r in app.url_map.iter_rules() if _is_candidate_route(str(r))})


def test_every_public_route_is_in_the_manifest():
    missing = [r for r in _public_routes() if r not in MANIFEST]
    assert not missing, (
        "These public API routes are covered by neither a connector tool nor a "
        "SITE_ONLY reason in backend/blueprints/mcp_manifest.MANIFEST:\n  "
        + "\n  ".join(missing)
        + "\n\nAdd a line to MANIFEST for each: either {'tools': [...]} naming the "
          "connector tool(s) (in backend/blueprints/mcp_http.py TOOLS) that already "
          "cover it or should be extended to, or {'site_only': True, 'reason': "
          "'...'} saying in one line why the connector doesn't need it (a chart or "
          "network view is visual, an export/cite route produces a file, a saved-"
          "parallel route needs a login, a density route feeds the Reader margin)."
    )


def test_every_manifest_entry_is_well_formed():
    tool_names = {t['name'] for t in TOOLS}
    problems = []
    for route, entry in MANIFEST.items():
        if entry.get('site_only'):
            if not (entry.get('reason') or '').strip():
                problems.append(f"{route}: site_only with no (or empty) reason")
            if entry.get('tools'):
                problems.append(f"{route}: has both site_only and tools")
            continue
        tools = entry.get('tools') or []
        if not tools:
            problems.append(f"{route}: neither site_only nor any tools listed")
        for t in tools:
            if t not in tool_names:
                problems.append(f"{route}: names unknown tool {t!r}")
    assert not problems, "Malformed MANIFEST entries:\n  " + "\n  ".join(problems)


def test_manifest_keys_are_real_routes():
    """Catches a typo'd or stale route string in the manifest itself (checked
    against the FULL url_map, not just the walked candidate set, since a
    couple of entries -- e.g. the cross-lingual poll route -- are listed on
    purpose despite being filtered out of the walk; see the comment on that
    entry in mcp_manifest.py)."""
    all_routes = {str(r) for r in app.url_map.iter_rules()}
    stale = [r for r in MANIFEST if r not in all_routes]
    assert not stale, (
        "backend/blueprints/mcp_manifest.MANIFEST names routes that no longer "
        "exist in app.url_map (typo, or the route was removed/renamed):\n  "
        + "\n  ".join(stale)
    )


def test_every_tool_names_at_least_one_manifest_route():
    """The reverse check: a tool that no longer matches anything real in the
    manifest is a tool the last route change forgot about."""
    referenced = set()
    for entry in MANIFEST.values():
        referenced.update(entry.get('tools') or [])
    tool_names = {t['name'] for t in TOOLS}
    orphaned = tool_names - referenced
    assert not orphaned, (
        "These connector tools are not named by any route in "
        "backend/blueprints/mcp_manifest.MANIFEST:\n  " + "\n  ".join(sorted(orphaned))
        + "\n\nEither the tool's backing route was removed/renamed (update the "
          "manifest) or it never had one recorded (add it)."
    )


@pytest.mark.parametrize('name', [t['name'] for t in TOOLS])
def test_tool_has_a_description_and_object_schema(name):
    """Sanity check on TOOLS itself, so a malformed new tool entry fails here
    rather than surfacing as a confusing MCP client error."""
    tool = next(t for t in TOOLS if t['name'] == name)
    assert tool.get('description', '').strip()
    assert tool['inputSchema']['type'] == 'object'
    assert callable(tool.get('fn'))
