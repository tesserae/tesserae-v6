import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts", "documents"))
import fix_image_urls  # noqa: E402
from image_url_rules import host_of, is_dead, load_dead_hosts, rewrite_image_url  # noqa: E402


def test_edh_photo_rule():
    assert rewrite_image_url("http://edh-www.adw.uni-heidelberg.de/fotos/F034014.JPG") == \
        "https://edh.ub.uni-heidelberg.de/edh/foto/F034014"


def test_edh_other_files_untouched():
    u = "http://edh-www.adw.uni-heidelberg.de/download/leugenstein_1_meshlab.pdf"
    assert rewrite_image_url(u) == u


def test_cil_rule_buckets():
    f = rewrite_image_url
    assert f("http://cil-old.bbaw.de/test06/bilder/datenbank/PH0006797.jpg") == \
        "https://cil.bbaw.de/ace/resources/PH/0005001-0010000/PH0006797.jpg"
    assert f("http://cil-old.bbaw.de/test06/bilder/datenbank/PH0000503.jpg") == \
        "https://cil.bbaw.de/ace/resources/PH/0000001-0005000/PH0000503.jpg"
    assert f("http://cil-old.bbaw.de/test06/bilder/datenbank/PEC0008986.jpg") == \
        "https://cil.bbaw.de/ace/resources/PEC/0005001-0010000/PEC0008986.jpg"


def test_cil_viewer_pages_have_no_rule():
    u = "http://cil-old.bbaw.de/dateien/cil_view.php?KO=KO0033048"
    assert rewrite_image_url(u) == u


def test_host_and_dead():
    dead = load_dead_hosts()
    assert host_of("ISic000001.jpg") == ""
    assert is_dead("ISic000001.jpg", dead)
    assert is_dead("https://access.bl.uk/item/viewer/ark:/81055/vdc_1", dead)
    assert not is_dead("https://lupa.at/16121", dead)


def _fixture(tmp_path):
    p = str(tmp_path / "m.db")
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE display (id TEXT, field TEXT, value TEXT)")
    rows = [
        ("a", "image_url", "http://edh-www.adw.uni-heidelberg.de/fotos/F000001.JPG"),
        ("b", "image_url", "http://cil-old.bbaw.de/test06/bilder/datenbank/PH0000010.jpg"),
        ("c", "image_url", "https://access.bl.uk/item/viewer/ark:/1"),
        ("d", "image_url", "ISic000001.jpg"),
        ("e", "image_url", "https://lupa.at/1"),
        ("f", "museum", "http://edh-www.adw.uni-heidelberg.de/fotos/F000002.JPG"),
    ]
    con.executemany("INSERT INTO display VALUES (?,?,?)", rows)
    con.commit()
    con.close()
    return p


def test_dry_run_counts_and_leaves_db(tmp_path, capsys):
    p = _fixture(tmp_path)
    assert fix_image_urls.main(["--dry-run", "--db", p]) == 0
    out = capsys.readouterr().out
    assert "edh-photo-moved: 1" in out and "cil-photo-moved: 1" in out
    assert "rows on dead hosts with no rule: 2" in out
    con = sqlite3.connect(p)
    assert con.execute("SELECT value FROM display WHERE id='a'").fetchone()[0].startswith("http://edh-www")


def test_apply_backs_up_and_rewrites_only_image_url(tmp_path):
    p = _fixture(tmp_path)
    fix_image_urls.main(["--apply", "--db", p])
    baks = [f for f in os.listdir(tmp_path) if ".bak-" in f]
    assert len(baks) == 1
    con = sqlite3.connect(p)
    v = dict(con.execute("SELECT id, value FROM display"))
    assert v["a"] == "https://edh.ub.uni-heidelberg.de/edh/foto/F000001"
    assert v["b"].startswith("https://cil.bbaw.de/ace/resources/PH/0000001-0005000/")
    assert v["f"].startswith("http://edh-www")  # other fields untouched
    assert v["e"] == "https://lupa.at/1"
