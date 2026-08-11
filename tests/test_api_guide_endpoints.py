"""Tests for the AI-guide-driven API changes:

- the generic start-and-poll helper (backend.blueprints.async_poll),
- the fusion GET-poll result carrying both short and SSE field names,
- the removal of the leaked absolute 'filepath' from text metadata.

All self-contained — no network, no live server.
"""
import os
import sys
import json
import time

import pytest
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import backend.blueprints.async_poll as AP


# --------------------------------------------------------------------------- #
# async_poll helper
# --------------------------------------------------------------------------- #
@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(AP, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(AP, "ensure_cache_dir", lambda: None)
    return tmp_path


@pytest.fixture
def app_ctx():
    # poll() calls flask.jsonify, which needs an application context.
    app = Flask(__name__)
    with app.app_context():
        yield


def _body(resp):
    if isinstance(resp, tuple):
        resp = resp[0]
    return json.loads(resp.get_data(as_text=True))


def _wait_for(path, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.exists(path):
            return True
        time.sleep(0.02)
    return False


def test_make_job_key_deterministic_and_sized():
    a = AP.make_job_key("x", "a", 1, None)
    b = AP.make_job_key("x", "a", 1, None)
    c = AP.make_job_key("x", "a", 2, None)
    assert a == b
    assert a != c
    assert len(a) == 32


def test_search_input_error_status():
    e = AP.SearchInputError("bad", 404)
    assert str(e) == "bad"
    assert e.status == 404
    assert AP.SearchInputError("x").status == 400


def test_poll_lifecycle_running_then_complete(tmp_cache, app_ctx):
    key = AP.make_job_key("t", "k1")
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return {"results": [1, 2, 3], "count": 3}

    r1 = _body(AP.poll("t", key, compute))
    assert r1["status"] == "running"

    assert _wait_for(os.path.join(tmp_cache, f"asyncjob_t_{key}.json"))
    r2 = _body(AP.poll("t", key, compute))
    assert r2["status"] == "complete"
    assert r2["cached"] is True
    assert r2["results"] == [1, 2, 3]
    # compute ran exactly once despite two poll calls
    assert calls["n"] == 1


def test_poll_transform_slims_output(tmp_cache, app_ctx):
    key = AP.make_job_key("t", "k2")

    def compute():
        return {"results": list(range(100)), "count": 100}

    def transform(d):
        return {"count": d["count"], "results": d["results"][:5]}

    AP.poll("t", key, compute, transform=transform)
    assert _wait_for(os.path.join(tmp_cache, f"asyncjob_t_{key}.json"))
    r = _body(AP.poll("t", key, compute, transform=transform))
    assert r["status"] == "complete"
    assert r["count"] == 100
    assert r["results"] == [0, 1, 2, 3, 4]


def test_poll_surfaces_error_then_clears(tmp_cache, app_ctx):
    key = AP.make_job_key("t", "k3")

    def compute():
        raise AP.SearchInputError("boom")

    AP.poll("t", key, compute)
    assert _wait_for(os.path.join(tmp_cache, f"asyncjob_t_{key}.error"))

    resp = AP.poll("t", key, compute)
    body = _body(resp)
    assert body["status"] == "error"
    assert "boom" in body["error"]
    # error marker is consumed so the next call retries (returns running)
    assert not os.path.exists(os.path.join(tmp_cache, f"asyncjob_t_{key}.error"))
    assert _body(AP.poll("t", key, compute))["status"] == "running"


# --------------------------------------------------------------------------- #
# fusion GET-poll result shape (issue 4: field-name parity with SSE)
# --------------------------------------------------------------------------- #
def test_slim_fusion_result_carries_both_field_sets():
    from backend.blueprints.fusion import _slim_fusion_result

    r = _slim_fusion_result({
        "fused_score": 3.14159,
        "channels": ["lemma", "sound"],
        "matched_words": ["arma"],
        "matched_lemmas": ["arma"],
        "source": {"ref": "Verg. A. 1.1", "text": "arma virumque"},
        "target": {"ref": "Luc. 1.1", "text": "bella per"},
    })
    # short poll names AND streaming-endpoint names both present
    assert r["score"] == r["fused_score"]
    assert r["channel_count"] == 2
    assert r["channels"] == ["lemma", "sound"]
    assert r["matched"] == ["arma"]
    assert r["matched_words"] == ["arma"]
    assert r["matched_lemmas"] == ["arma"]
    assert r["source"]["ref"] == "Verg. A. 1.1"
    assert r["target"]["text"] == "bella per"


# --------------------------------------------------------------------------- #
# filepath leak removed from text metadata (issue 8)
# --------------------------------------------------------------------------- #
def test_get_text_metadata_does_not_leak_filepath(tmp_path):
    from backend.utils import get_text_metadata

    f = tmp_path / "vergil.aeneid.part.1.tess"
    f.write_text("<verg. aen. 1.1> arma virumque cano\n", encoding="utf-8")
    meta = get_text_metadata(str(f))
    assert "filepath" not in meta
    assert meta["id"] == "vergil.aeneid.part.1.tess"
