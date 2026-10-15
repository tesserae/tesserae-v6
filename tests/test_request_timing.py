"""Request-timing hook and its report script."""
import importlib.util
import io
import os
import re
from pathlib import Path

import pytest
from flask import Flask, jsonify

from backend import request_timing

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "request_timings.tsv"

LINE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}\t[A-Z]+\t/[^\t?]*\t\d{3}\t\d+\.\d\t-?\d+\t\d+\t(local|[0-9a-f]{10})$")


def make_app():
    app = Flask(__name__)

    @app.route("/api/ok")
    def ok():
        return jsonify(a=1)

    @app.route("/api/boom")
    def boom():
        raise RuntimeError("x")

    @app.route("/other")
    def other():
        return "hi"

    return app


def lines(d):
    out = []
    for f in Path(d).glob("*.tsv"):
        out += f.read_text().splitlines()
    return out


def test_writes_one_line_per_api_request_without_query(tmp_path, monkeypatch):
    monkeypatch.setenv(request_timing.ENV_VAR, str(tmp_path))
    app = make_app()
    assert request_timing.install(app) is True
    c = app.test_client()
    c.get("/api/ok?q=secret+words")
    c.post("/api/ok", data={"q": "secret"})  # 405, still recorded
    c.get("/other")
    got = lines(tmp_path)
    assert len(got) == 2
    assert all(LINE.match(x) for x in got)
    assert "secret" not in "".join(got)
    f = got[0].split("\t")
    assert f[1:4] == ["GET", "/api/ok", "200"] and int(f[6]) == os.getpid()
    assert got[1].split("\t")[3] == "405"


def test_off_when_unset_or_missing(tmp_path, monkeypatch):
    monkeypatch.delenv(request_timing.ENV_VAR, raising=False)
    app = make_app()
    assert request_timing.install(app) is False
    app.test_client().get("/api/ok")
    assert lines(tmp_path) == []
    monkeypatch.setenv(request_timing.ENV_VAR, str(tmp_path / "nope"))
    assert request_timing.install(make_app()) is False


def test_exception_path_writes_500(tmp_path, monkeypatch):
    monkeypatch.setenv(request_timing.ENV_VAR, str(tmp_path))
    app = make_app()
    app.config["TESTING"] = True  # exception propagates, teardown sees it
    request_timing.install(app)
    with pytest.raises(RuntimeError):
        app.test_client().get("/api/boom")
    got = lines(tmp_path)
    assert len(got) == 1
    assert got[0].split("\t")[3] == "500"


def test_unhandled_exception_not_double_counted(tmp_path, monkeypatch):
    monkeypatch.setenv(request_timing.ENV_VAR, str(tmp_path))
    app = make_app()
    request_timing.install(app)
    r = app.test_client().get("/api/boom")
    assert r.status_code == 500
    assert len(lines(tmp_path)) == 1


def _report():
    spec = importlib.util.spec_from_file_location(
        "request_timings_report", ROOT / "scripts" / "review" / "request_timings_report.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_route_collapsing():
    m = _report()
    assert m.route_of("/api/text/vergil.aeneid.tess") == "/api/text/<id>"
    assert m.route_of("/api/documents/12345") == "/api/documents/<id>"
    assert m.route_of("/api/passages/map/cell") == "/api/passages/map/cell"


def test_percentile():
    m = _report()
    v = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert m.percentile(v, 0.5) == 3.0
    assert m.percentile(v, 0.9) == pytest.approx(4.6)
    assert m.percentile([], 0.5) == 0.0


def test_report_on_fixture():
    m = _report()
    rows = m.read([str(FIXTURE)])
    assert len(rows) == 30
    buf = io.StringIO()
    m.report(rows, out=buf)
    text = buf.getvalue()
    assert "30 requests" in text
    assert "/api/text/<id>" in text
    # line-search has the most total time and sorts first
    first = [x for x in text.splitlines() if x.startswith("/api/")][0]
    assert first.startswith("/api/line-search")
    assert "/api/search" in text and "5xx=2" in text
    assert "Requests per hour" in text


def test_mounted_under_api_like_the_live_site(tmp_path, monkeypatch):
    """Apache mounts the application at /api (WSGIScriptAlias), so Flask sees
    script_root "/api" and path "/languages". The line must still be written,
    with the full path the visitor sent."""
    monkeypatch.setenv(request_timing.ENV_VAR, str(tmp_path))
    app = Flask(__name__)

    @app.route("/languages")
    def languages():
        return jsonify(a=1)

    assert request_timing.install(app) is True
    r = app.test_client().get("/languages", base_url="http://localhost/api")
    assert r.status_code == 200
    got = lines(tmp_path)
    assert len(got) == 1
    assert got[0].split("\t")[1:4] == ["GET", "/api/languages", "200"]


def test_streamed_response_is_not_read_by_the_hook(tmp_path, monkeypatch):
    """A streamed response (server-sent events) must reach the client as it is
    produced. The hook records -1 for its size and must not consume the
    generator to measure it."""
    from flask import Response
    monkeypatch.setenv(request_timing.ENV_VAR, str(tmp_path))
    app = Flask(__name__)
    ran = []

    @app.route("/api/stream")
    def stream():
        def gen():
            ran.append("one")
            yield "data: one\n\n"
            ran.append("two")
            yield "data: two\n\n"
        return Response(gen(), mimetype="text/event-stream")

    assert request_timing.install(app) is True
    r = app.test_client().get("/api/stream")
    # The test client pulls the first chunk to get the headers; the second is
    # still unproduced, so the hook did not read the stream through.
    assert ran == ["one"]
    got = lines(tmp_path)
    assert len(got) == 1 and got[0].split("\t")[5] == "-1"
    assert r.get_data(as_text=True) == "data: one\n\ndata: two\n\n"
    assert ran == ["one", "two"]


def test_visitor_code_is_keyed_daily_and_never_the_address(tmp_path, monkeypatch):
    monkeypatch.setenv(request_timing.ENV_VAR, str(tmp_path))
    monkeypatch.setenv("SESSION_SECRET", "k1")
    app = make_app()
    request_timing.install(app)
    request_timing._local.clear()
    c = app.test_client()
    c.get("/api/ok", environ_base={"REMOTE_ADDR": "203.0.113.7"}, headers={"User-Agent": "A"})
    c.get("/api/ok", environ_base={"REMOTE_ADDR": "203.0.113.7"}, headers={"User-Agent": "A"})
    c.get("/api/ok", environ_base={"REMOTE_ADDR": "198.51.100.9"}, headers={"User-Agent": "A"})
    got = [x.split("\t")[7] for x in lines(tmp_path)]
    assert got[0] == got[1] and got[0] != got[2]
    text = "".join(lines(tmp_path))
    assert "203.0.113" not in text and "198.51.100" not in text
    with app.test_request_context("/api/ok", environ_base={"REMOTE_ADDR": "203.0.113.7"},
                                  headers={"User-Agent": "A"}):
        assert request_timing._visitor("2026-10-15") == got[0]
        assert request_timing._visitor("2026-10-16") != got[0]


def test_requests_from_the_server_are_local(tmp_path, monkeypatch):
    monkeypatch.setenv(request_timing.ENV_VAR, str(tmp_path))
    monkeypatch.setenv("TESSERAE_TIMING_LOCAL_ADDRS", "192.0.2.5")
    app = make_app()
    request_timing.install(app)
    c = app.test_client()
    c.get("/api/ok", environ_base={"REMOTE_ADDR": "127.0.0.1"})
    c.get("/api/ok", environ_base={"REMOTE_ADDR": "192.0.2.5"})
    assert [x.split("\t")[7] for x in lines(tmp_path)] == ["local", "local"]
