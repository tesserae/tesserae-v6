"""Guards for static/downloads/tesserae-openapi.yaml — the schema an OpenAI
Custom GPT imports as an Action.

OpenAI's GPT Action builder rejects a schema (and then refuses to run the
action) if any operation description exceeds 300 characters. It also requires
an operationId on every operation and a single server URL. These tests keep the
canonical schema importable so the "Tesserae" Custom GPT keeps working.
"""
import os

import pytest

yaml = pytest.importorskip("yaml")

SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "static", "downloads", "tesserae-openapi.yaml",
)

# OpenAI's Custom GPT Action importer limit; keep a small margin below it.
OPENAI_DESC_LIMIT = 300


@pytest.fixture(scope="module")
def schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _operations(schema):
    for path, ops in schema["paths"].items():
        for method, op in ops.items():
            if method.lower() in ("get", "post", "put", "patch", "delete"):
                yield path, method, op


def test_schema_parses_and_has_paths(schema):
    assert schema.get("openapi", "").startswith("3.")
    assert schema["paths"]


def test_single_server_url(schema):
    servers = schema.get("servers", [])
    assert len(servers) == 1, "Custom GPT Actions need exactly one server URL"
    assert servers[0]["url"].startswith("https://")


def test_every_operation_has_operationid(schema):
    missing = [f"{m.upper()} {p}" for p, m, op in _operations(schema)
               if not op.get("operationId")]
    assert not missing, f"operations missing operationId: {missing}"


def test_operation_descriptions_under_openai_limit(schema):
    """The concrete bug that broke the Custom GPT import (2026-08-11)."""
    offenders = {
        op["operationId"]: len(op.get("description", "") or "")
        for _p, _m, op in _operations(schema)
        if len(op.get("description", "") or "") > OPENAI_DESC_LIMIT
    }
    assert not offenders, (
        f"operation descriptions over OpenAI's {OPENAI_DESC_LIMIT}-char limit: "
        f"{offenders}"
    )


def test_operation_summaries_under_limit(schema):
    offenders = {
        op["operationId"]: len(op.get("summary", "") or "")
        for _p, _m, op in _operations(schema)
        if len(op.get("summary", "") or "") > OPENAI_DESC_LIMIT
    }
    assert not offenders, f"operation summaries over {OPENAI_DESC_LIMIT}: {offenders}"
