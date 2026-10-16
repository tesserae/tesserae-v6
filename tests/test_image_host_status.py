"""Image host status: backend.documents.down_image_hosts and
scripts/documents/check_image_hosts.py. No network (a fake prober)."""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import backend.documents as docs
from scripts.documents import check_image_hosts as chk


def _status(path, hosts):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"hosts": hosts}, f)


def _c(date, ok):
    return {"date": date, "ok": ok, "codes": [200 if ok else 500]}


def test_two_failures_make_a_host_down(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    _status(p, {"a.org": {"checks": [_c("2026-10-09", False), _c("2026-10-16", False)],
                          "down_since": "2026-10-09"}})
    monkeypatch.setenv("TESSERAE_IMAGE_HOST_STATUS", str(p))
    assert docs.down_image_hosts() == {"a.org": "2026-10-09"}


def test_latest_pass_or_single_failure_is_not_down(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    _status(p, {
        "pass.org": {"checks": [_c("2026-10-09", False), _c("2026-10-16", True)]},
        "once.org": {"checks": [_c("2026-10-16", False)]},
        "old.org": {"checks": [_c("2026-10-02", False), _c("2026-10-09", True),
                               _c("2026-10-16", False)]},
    })
    monkeypatch.setenv("TESSERAE_IMAGE_HOST_STATUS", str(p))
    assert docs.down_image_hosts() == {}


def test_missing_file_is_empty_and_changed_file_is_reread(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    monkeypatch.setenv("TESSERAE_IMAGE_HOST_STATUS", str(p))
    assert docs.down_image_hosts() == {}
    _status(p, {"a.org": {"checks": [_c("2026-10-09", False), _c("2026-10-16", False)]}})
    os.utime(p, (1, 1))
    assert "a.org" in docs.down_image_hosts()
    _status(p, {"a.org": {"checks": [_c("2026-10-09", False), _c("2026-10-16", True)]}})
    os.utime(p, (2, 2))
    assert docs.down_image_hosts() == {}


def test_image_hosts_down_for_filters_to_the_documents_own_hosts(tmp_path, monkeypatch):
    p = tmp_path / "s.json"
    two = [_c("2026-10-09", False), _c("2026-10-16", False)]
    _status(p, {"a.org": {"checks": two, "down_since": "2026-10-09"},
                "b.org": {"checks": two, "down_since": "2026-10-09"}})
    monkeypatch.setenv("TESSERAE_IMAGE_HOST_STATUS", str(p))
    assert docs.image_hosts_down_for(["https://A.org/x.jpg", "bare.jpg"]) == [
        {"host": "a.org", "down_since": "2026-10-09"}]
    assert docs.image_hosts_down_for(None) == []


def test_ok_rule_is_at_least_half_200():
    assert chk.host_ok([200, 200, 500])
    assert chk.host_ok([200, 500])
    assert not chk.host_ok([200, 500, 500])
    assert not chk.host_ok([])


def test_probe_host_uses_the_prober_once_per_sample():
    seen = []

    def fake(u):
        seen.append(u)
        return 200 if u.endswith("1") else 404
    ok, codes = chk.probe_host(["http://h/1", "http://h/2"], fake)
    assert ok and codes == [200, 404] and seen == ["http://h/1", "http://h/2"]


def test_twelve_check_cap_and_down_since():
    st = {"hosts": {}}
    for i in range(1, 16):
        chk.add_check(st, "h", 5, f"2026-09-{i:02d}", i <= 3, [500])
    e = st["hosts"]["h"]
    assert len(e["checks"]) == 12
    assert e["down_since"] == "2026-09-04"
    chk.add_check(st, "h", 5, "2026-09-20", True, [200])
    assert st["hosts"]["h"]["down_since"] is None


def test_seed_marks_seven_down_two_recovered_and_never_overwrites():
    st = {"hosts": {}}
    chk.add_check(st, "papyri.uni-koeln.de", 204, "2026-10-16", True, [200])
    chk.seed(st, {"papyri.uni-koeln.de": 204})
    e = st["hosts"]["papyri.uni-koeln.de"]
    assert [c["date"] for c in e["checks"]] == ["2026-10-09", "2026-10-16"]
    assert e["checks"][1]["ok"] is True      # the real check was kept
    chk.seed(st, {})
    assert st["hosts"]["petriecat.museums.ucl.ac.uk"]["down_since"] == "2026-10-09"
    assert st["hosts"]["www.uni-koeln.de"]["down_since"] is None
    assert len(st["hosts"]) == 9


def test_run_checks_over_a_fixture_db(tmp_path):
    db = tmp_path / "m.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE display (id TEXT, field TEXT, value TEXT)")
    for i in range(8):
        con.execute("INSERT INTO display VALUES (?,?,?)", (f"d{i}", "image_url", f"https://x.org/{i}"))
    con.execute("INSERT INTO display VALUES ('d9','image_url','bare.jpg')")
    con.commit()
    con.close()
    hosts = chk.collect_hosts(str(db))
    assert list(hosts) == ["x.org"] and hosts["x.org"][0] == 8 and len(hosts["x.org"][1]) == 6
    st = {"hosts": {}}
    res = chk.run_checks(hosts, st, "2026-10-16", prober=lambda u: 500)
    assert res["x.org"][0] is False and st["hosts"]["x.org"]["down_since"] == "2026-10-16"
