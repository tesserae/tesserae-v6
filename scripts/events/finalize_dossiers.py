#!/usr/bin/env python3
"""Final pass over the dossier SQLite: the optional columns the Event page reads.

Usage: finalize_dossiers.py DOSSIERS.sqlite PLEIADES_POINTS.tsv
Adds (if missing) and fills passages.language (la or grc, from the passage index's works list),
documents.language, documents.lat and documents.lon (the document's Pleiades place, directly or
through the Trismegistos crosswalk, as in the gatherer), and sets events.type to the first of
the event's types (the full list moves to events.types_all). No gateway request is made.
"""
import json, os, sqlite3, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_event_dossier as b  # noqa: E402


def addcol(db, table, col, typ):
    if col not in {r[1] for r in db.execute(f"PRAGMA table_info({table})")}:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


def main(path, pleiades):
    db = sqlite3.connect(path, timeout=120)
    for t, c, ty in (("passages", "language", "TEXT"), ("documents", "language", "TEXT"), ("documents", "lat", "REAL"),
                     ("documents", "lon", "REAL"), ("events", "types_all", "TEXT")):
        addcol(db, t, c, ty)
    w = json.load(open(os.path.join(b.PROD, "data", "passage_index", "works_by_language.json")))["languages"]
    lang = {}
    for lg in ("la", "grc"):
        for x in w[lg]:
            lang[b.base_work(x if isinstance(x, str) else x["work"])] = lg
    works = [r[0] for r in db.execute("SELECT DISTINCT work FROM passages")]
    db.executemany("UPDATE passages SET language=? WHERE work=?", [(lang.get(b.base_work(x)), x) for x in works])
    # works whose name the works list spells differently (pseudo_*, supplements): ask the window itself
    wt = sqlite3.connect(f"file:{b.PROD}/data/passage_index/window_texts.db?mode=ro", uri=True)
    miss = db.execute("SELECT rowid, window_id FROM passages WHERE language IS NULL AND window_id IS NOT NULL").fetchall()
    fix = []
    for rid, wid in miss:
        r = wt.execute("SELECT language FROM window_texts WHERE id=?", (wid,)).fetchone()
        if r and r[0] in ("la", "grc"):
            fix.append((r[0], rid))
    db.executemany("UPDATE passages SET language=? WHERE rowid=?", fix)
    points, cw = b.load_points(pleiades), b.load_crosswalk()
    md = sqlite3.connect(f"file:{b.PROD}/data/documents/metadata.db?mode=ro", uri=True)
    ids = [r[0] for r in db.execute("SELECT DISTINCT doc_id FROM documents")]
    upd = []
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        for did, pid, tm, langs in md.execute(
                "SELECT id, pleiades_id, place_tm_id, languages FROM documents WHERE id IN (%s)" % ",".join("?" * len(chunk)), chunk):  # nosec B608
            pid = pid or cw.get(tm)
            pt = points.get(pid) if pid else None
            first = (langs or "").replace(";", ",").split(",")[0].strip()
            upd.append((first if first in ("la", "grc") else "la", pt[0] if pt else None, pt[1] if pt else None, did))
    db.executemany("UPDATE documents SET language=?, lat=?, lon=? WHERE doc_id=?", upd)
    db.execute("UPDATE events SET types_all = type WHERE types_all IS NULL")
    db.execute("UPDATE events SET type = substr(type, 1, instr(type || ',', ',') - 1) WHERE type LIKE '%,%'")
    db.commit()
    for t in ("events", "passages", "documents", "scholarship", "judgements", "requests"):
        print(t, db.execute(f"SELECT count(*) FROM {t}").fetchone()[0])
    print("passages without language", db.execute("SELECT count(*) FROM passages WHERE language IS NULL").fetchone()[0],
          "documents without coordinates", db.execute("SELECT count(*) FROM documents WHERE lat IS NULL").fetchone()[0])


if __name__ == "__main__":
    main(*sys.argv[1:3])
