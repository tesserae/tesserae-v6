"""Build a NEW syntax database from the live one plus a gap plan and parses.

Never touches the live file: it copies it to --out first.

  python scripts/syntax/gap_build.py --lang la --live-db DB --texts DIR --plan plan_la.json \
      --todo todo_la.jsonl --parsed out_la_0.jsonl out_la_1.jsonl ... --out NEW.db

Order of work: read every row that is to be copied (before any ref changes),
rekey rows stored under a ref that is not their file's tag, insert the copied
rows and the parsed rows under their tags, give each file that gets rows its
`texts` entry, set `syntax_source`, run PRAGMA integrity_check.
"""

import argparse
import datetime
import json
import os
import shutil
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from syntax_gap_lib import (  # noqa: E402
    read_tess,
)

COLS = ("tokens", "lemmas", "upos", "heads", "deprels", "feats")
SOURCE = {
    "la": ("latinpipe", "latin-evalatin24-240520"),
    "grc": (
        "stanza 1.11.0",
        "grc default package perseus (tokenize perseus; pos, lemma, depparse perseus_nocharlm)",
    ),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True)
    ap.add_argument("--live-db", required=True)
    ap.add_argument("--texts", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--todo", required=True)
    ap.add_argument("--parsed", nargs="*", default=[])
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--no-fill",
        action="store_true",
        help="parse and copy only for files with no rows (leave partly parsed files as they are)",
    )
    a = ap.parse_args()
    if os.path.abspath(a.out) == os.path.abspath(a.live_db):
        sys.exit("refusing to write over the live database")
    plan = json.load(open(a.plan))
    parsed_before = set(plan["parsed_before"])

    todo = {}
    for line in open(a.todo, encoding="utf-8"):
        o = json.loads(line)
        todo[o["text"]] = o["id"]
    parsed = {}
    for p in a.parsed:
        for line in open(p, encoding="utf-8"):
            o = json.loads(line)
            parsed[o["id"]] = tuple(json.dumps(o[c], ensure_ascii=False) for c in COLS)

    shutil.copyfile(a.live_db, a.out + ".partial")
    conn = sqlite3.connect(a.out + ".partial")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA journal_mode=MEMORY")
    ids = dict(conn.execute("SELECT filename, text_id FROM texts"))

    # 1. rows to copy, read before any ref changes
    copy_rows = {}
    for f, m in plan["copy"].items():
        if a.no_fill and f in parsed_before:
            continue
        got = {}
        for tag, (sfn, sref) in m.items():
            r = conn.execute(
                "SELECT tokens, lemmas, upos, heads, deprels, feats FROM syntax WHERE text_id=? AND ref=?",
                (ids[sfn], sref),
            ).fetchone()
            if r:
                got[tag] = r
        copy_rows[f] = got

    stats = {
        "rekeyed": 0,
        "copied": 0,
        "parsed_rows": 0,
        "parse_missing": 0,
        "ignored": 0,
        "new_files": 0,
        "files_touched": 0,
    }
    # 2. rekey
    for f, m in plan["rekey"].items():
        for tag, oldref in m.items():
            cur = conn.execute(
                "UPDATE syntax SET ref=? WHERE text_id=? AND ref=?",
                (tag, ids[f], oldref),
            )
            stats["rekeyed"] += cur.rowcount

    def text_id_for(f):
        if f not in ids:
            cur = conn.execute("INSERT INTO texts (filename) VALUES (?)", (f,))
            ids[f] = cur.lastrowid
            stats["new_files"] += 1
        return ids[f]

    def insert(f, tag, row):
        cur = conn.execute(
            "INSERT OR IGNORE INTO syntax (text_id, ref, tokens, lemmas, upos, heads, deprels, feats) VALUES (?,?,?,?,?,?,?,?)",
            (text_id_for(f), tag) + tuple(row),
        )
        if cur.rowcount == 0:
            stats["ignored"] += 1
            return False
        return True

    touched = set()
    # 3. copies
    for f, got in copy_rows.items():
        for tag, row in got.items():
            if insert(f, tag, row):
                stats["copied"] += 1
                touched.add(f)
    # 4. parses
    for f, tags in plan["parse"].items():
        if a.no_fill and f in parsed_before:
            continue
        want = set(tags)
        text_of = {}
        for tag, x in read_tess(os.path.join(a.texts, f)):
            if tag in want and tag not in text_of:
                text_of[tag] = x
        for tag in tags:
            pid = todo.get(text_of.get(tag))
            row = parsed.get(pid)
            if row is None:
                stats["parse_missing"] += 1
                continue
            if insert(f, tag, row):
                stats["parsed_rows"] += 1
                touched.add(f)
    stats["files_touched"] = len(touched)

    parser, model = SOURCE[a.lang]
    n_texts = conn.execute("SELECT COUNT(DISTINCT text_id) FROM syntax").fetchone()[0]
    n_lines = conn.execute("SELECT COUNT(*) FROM syntax").fetchone()[0]
    conn.execute("DELETE FROM syntax_source")
    conn.execute(
        "INSERT INTO syntax_source (parser, model, build_date, total_texts, total_lines) VALUES (?,?,?,?,?)",
        (
            parser,
            model,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            n_texts,
            n_lines,
        ),
    )
    conn.commit()
    ic = conn.execute("PRAGMA integrity_check").fetchall()
    stats.update(
        total_texts=n_texts,
        total_lines=n_lines,
        integrity=ic[0][0] if len(ic) == 1 else str(ic[:3]),
    )
    conn.close()
    os.replace(a.out + ".partial", a.out)
    print(json.dumps(stats))


main()
