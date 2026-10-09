#!/usr/bin/env python3
"""Merge dossier SQLite files from sharded runs into the first one.

Usage: merge_dossiers.py MAIN.sqlite PART.sqlite [PART2.sqlite ...]
Copies events, passages, documents, scholarship, judgements and requests of each PART into MAIN
(an event already in MAIN with status ok is left alone).
"""
import sqlite3, sys


def main(main_path, *parts):
    db = sqlite3.connect(main_path)
    for i, part in enumerate(parts):
        db.execute(f"ATTACH DATABASE ? AS p{i}", (part,))
        new = [r[0] for r in db.execute(f"SELECT id FROM p{i}.events WHERE status='ok' AND id NOT IN (SELECT id FROM main.events WHERE status='ok')")]
        db.executemany("DELETE FROM main.events WHERE id=?", [(x,) for x in new])
        for t, key in (("passages", "event_id"), ("documents", "event_id"), ("scholarship", "event_id")):
            db.executemany(f"DELETE FROM main.{t} WHERE {key}=?", [(x,) for x in new])
        db.execute("CREATE TEMP TABLE IF NOT EXISTS newids (id TEXT)")
        db.execute("DELETE FROM newids")
        db.executemany("INSERT INTO newids VALUES (?)", [(x,) for x in new])
        db.execute(f"INSERT INTO main.events SELECT * FROM p{i}.events WHERE id IN (SELECT id FROM newids)")
        for t in ("passages", "documents", "scholarship"):
            db.execute(f"INSERT INTO main.{t} SELECT * FROM p{i}.{t} WHERE event_id IN (SELECT id FROM newids)")
        db.execute(f"INSERT OR REPLACE INTO main.judgements SELECT * FROM p{i}.judgements")
        db.execute(f"INSERT INTO main.requests SELECT * FROM p{i}.requests")
        db.commit()
        db.execute(f"DETACH DATABASE p{i}")
        print(part, "merged events:", len(new))
    print("main events ok:", db.execute("SELECT count(*) FROM events WHERE status='ok'").fetchone()[0])


if __name__ == "__main__":
    main(*sys.argv[1:])
