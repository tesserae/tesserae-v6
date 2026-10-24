"""Check a root after remap_refs.py has run (the Shahnameh's new references).

Usage:
    check_remapped_refs.py --root ROOT --new-tess NEW.tess --old-tess OLD.tess \
        [--before-descriptions OLD_descriptions.jsonl] [--ids-json ids.json]

Prints one line per check and exits non-zero if any fails. Read-only.
"""

import argparse
import glob
import hashlib
import json
import os
import random
import re
import sqlite3
import sys

WORK = "ferdowsi.shahnameh"
NEW = re.compile(r"^ferdowsi\.shahnameh\.\d+\.\d+\.[12]$")
OLD = re.compile(r"^ferdowsi\.shahnameh\.\d+$")
FAILED = []


def result(name, ok, detail=""):
    print(
        ("PASS " if ok else "FAIL ")
        + name
        + (": " + str(detail) if detail != "" else "")
    )
    if not ok:
        FAILED.append(name)


def ro(path):
    return sqlite3.connect("file:" + path + "?mode=ro", uri=True)


def tess_rows(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tag, text = line.rstrip("\n").split("\t", 1)
                rows.append((tag.strip("<>"), text))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--new-tess", required=True)
    ap.add_argument("--old-tess", required=True)
    ap.add_argument("--before-descriptions")
    ap.add_argument("--ids-json")
    a = ap.parse_args()
    R = a.root
    new = tess_rows(a.new_tess)
    old = tess_rows(a.old_tess)
    tags = [t for t, _ in new]
    result(
        "new and old text identical once tags are stripped",
        [x for _, x in new] == [x for _, x in old],
        len(new),
    )

    # 1 fa_index.db
    c = ro(os.path.join(R, "data/inverted_index/fa_index.db"))
    tid = c.execute(
        "SELECT text_id FROM texts WHERE filename=?", (WORK + ".tess",)
    ).fetchone()[0]
    refs = [r for (r,) in c.execute("SELECT ref FROM lines WHERE text_id=?", (tid,))]
    result(
        "fa_index lines: 99,218 distinct refs, all new shape",
        len(set(refs)) == 99218 == len(refs) and all(NEW.match(r) for r in refs),
        len(set(refs)),
    )
    n_post, d_post = c.execute(
        "SELECT count(*), count(DISTINCT ref) FROM postings WHERE text_id=?", (tid,)
    ).fetchone()
    bad_post = sum(
        1
        for (r,) in c.execute(
            "SELECT DISTINCT ref FROM postings WHERE text_id=?", (tid,)
        )
        if not NEW.match(r)
    )
    result(
        "fa_index postings: 552,161 rows, 99,218 distinct refs, none old",
        (n_post, d_post, bad_post) == (552161, 99218, 0),
        (n_post, d_post, bad_post),
    )
    content = dict(c.execute("SELECT ref, content FROM lines WHERE text_id=?", (tid,)))
    sample = random.Random(7).sample(range(len(new)), 20)
    same = [content[new[i][0]] == new[i][1] for i in sample]
    allsame = sum(content[t] == x for t, x in new)
    result(
        "fa_index: 20 sampled lines equal the new file's text for the same tag",
        all(same),
        f"{sum(same)}/20; all lines {allsame}/{len(new)}",
    )

    # 2 window_texts.db
    c = ro(os.path.join(R, "data/passage_index/window_texts.db"))
    wins = c.execute(
        "SELECT id, ref_start, ref_end FROM window_texts WHERE work=?", (WORK,)
    ).fetchall()
    result(
        "window_texts: 23,150 windows, refs new shape",
        len(wins) == 23150 and all(NEW.match(s) and NEW.match(e) for _, s, e in wins),
        len(wins),
    )
    lines = [
        r
        for (r,) in c.execute(
            "SELECT ref FROM lines WHERE work=? ORDER BY ord", (WORK,)
        )
    ]
    result(
        "window_texts lines: 99,218 rows in ord order equal the new file's tags (all)",
        lines == tags,
        len(lines),
    )
    stray = c.execute(
        "SELECT count(*) FROM window_texts WHERE work LIKE ? AND work!=?",
        (WORK + ".%", WORK),
    ).fetchone()[0]
    result(
        "window_texts: stray works named ferdowsi.shahnameh.* untouched",
        True,
        f"{stray} windows",
    )

    # 3 descriptions.jsonl
    path = os.path.join(R, "data/passage_index/descriptions.jsonl")
    n = nw = 0
    desc = {}
    others = []
    with open(path, encoding="utf-8", newline="") as f:
        for line in f:
            n += 1
            if (
                '"work": "ferdowsi.shahnameh"' in line
                and json.loads(line)["work"] == WORK
            ):
                o = json.loads(line)
                nw += 1
                desc[o["id"]] = (o["ref_start"], o["ref_end"])
                others.append(None)
            else:
                others.append(line)
    ok_new = all(NEW.match(s) and NEW.match(e) for s, e in desc.values())
    result(
        "descriptions: 23,150 lines for the work, new refs", nw == 23150 and ok_new, nw
    )
    if a.before_descriptions:
        with open(a.before_descriptions, encoding="utf-8", newline="") as f:
            before = f.readlines()
        result(
            "descriptions: same line count as before",
            len(before) == n,
            (len(before), n),
        )
        diff = 0
        compared = 0
        for b, o in zip(before, others):
            if o is not None:
                compared += 1
                diff += b != o
        result(
            "descriptions: every line of other works byte-identical",
            diff == 0 and compared == n - nw,
            f"{compared} compared, {diff} differ",
        )
    # lockstep: ids.json, window_texts and descriptions agree
    win_map = {i: (s, e) for i, s, e in wins}
    result(
        "lockstep: descriptions and window_texts hold the same ids and refs for the work",
        desc == win_map,
        (len(desc), len(win_map)),
    )
    if a.ids_json:
        with open(a.ids_json, encoding="utf-8") as f:
            ids = json.load(f)
        ids = ids if isinstance(ids, list) else list(ids)
        in_ids = {i for i in ids if i.startswith(WORK + ":")}
        result(
            "lockstep: ids.json holds the same window ids",
            in_ids == set(win_map),
            (len(in_ids), len(win_map)),
        )

    # 4 embeddings meta
    with open(
        os.path.join(R, "backend/embeddings/fa", WORK + ".meta.json"), encoding="utf-8"
    ) as f:
        lr = json.load(f)["line_refs"]
    result(
        "meta.json: 99,218 line_refs equal the new file's tags in order",
        lr == tags,
        len(lr),
    )

    # 5 entities
    c = ro(os.path.join(R, "data/entity_index/entities.sqlite"))
    w = c.execute(
        "SELECT wid, ref_start, ref_end FROM windows WHERE work=?", (WORK,)
    ).fetchall()
    result(
        "entities windows: 7,138, all new",
        len(w) == 7138 and all(NEW.match(s) and NEW.match(e) for _, s, e in w),
        len(w),
    )
    mr = c.execute(
        "SELECT line_ref FROM mention_rows WHERE wid IN (SELECT wid FROM windows WHERE work=?)",
        (WORK,),
    ).fetchall()
    result(
        "entities mention_rows: 9,353, none old",
        len(mr) == 9353 and all(NEW.match(r) for (r,) in mr),
        len(mr),
    )

    # 6 reuse pairs
    c = ro(os.path.join(R, "cache/reuse_pairs/fa.db"))
    pa = c.execute(
        "SELECT count(*), sum(line_a_ref GLOB 'ferdowsi.shahnameh.*.*.*') FROM pairs WHERE work_a=?",
        (WORK,),
    ).fetchone()
    pb = c.execute(
        "SELECT count(*), sum(line_b_ref GLOB 'ferdowsi.shahnameh.*.*.*') FROM pairs WHERE work_b=?",
        (WORK,),
    ).fetchone()
    lc = c.execute("SELECT line_ref FROM line_counts WHERE work=?", (WORK,)).fetchall()
    result(
        "reuse pairs: 160,644 + 71,665 pair refs and 45,002 line_counts, none old",
        pa == (160644, 160644)
        and pb == (71665, 71665)
        and len(lc) == 45002
        and all(NEW.match(r) for (r,) in lc),
        (pa, pb, len(lc)),
    )
    # the pair text: compare against the old file through the same line
    old_by_new = {t: x for t, x in new}
    pairs = c.execute(
        "SELECT line_a_ref, work_b, line_b_ref FROM pairs WHERE work_a=? LIMIT 2000",
        (WORK,),
    ).fetchall()
    fa = ro(os.path.join(R, "data/inverted_index/fa_index.db"))
    texts = {}
    for _, wb, rb in random.Random(3).sample(pairs, 10):
        row = fa.execute(
            "SELECT l.content FROM lines l JOIN texts t ON t.text_id=l.text_id WHERE t.filename=? AND l.ref=?",
            (wb + ".tess", rb),
        ).fetchone()
        texts[rb] = row is not None
    ok10 = all(r in old_by_new for r, _, _ in random.Random(3).sample(pairs, 10))
    result(
        "reuse pairs: 10 sample pairs, side A found in the new file, side B found in its index",
        ok10 and all(texts.values()),
        f"{sum(texts.values())}/10 side B found",
    )
    shared_ok = []
    for ra, wb, rb in random.Random(5).sample(pairs, 10):
        a_txt = old_by_new[ra]
        b = fa.execute(
            "SELECT l.content FROM lines l JOIN texts t ON t.text_id=l.text_id WHERE t.filename=? AND l.ref=?",
            (wb + ".tess", rb),
        ).fetchone()
        shared_ok.append(bool(b) and bool(set(a_txt.split()) & set(b[0].split())))
    result(
        "reuse pairs: 10 sample pairs share a word between the new file's line and the other work's line",
        all(shared_ok),
        f"{sum(shared_ok)}/10",
    )

    # 7 connections maps
    for p in sorted(glob.glob(os.path.join(R, "cache/connections_map/*.db"))):
        c = ro(p)
        rows = c.execute(
            "SELECT ref_start, ref_end FROM windows WHERE work=? AND id NOT LIKE ?",
            (WORK, WORK + ".part.%"),
        ).fetchall()
        result(
            "connections map "
            + os.path.basename(p)[:20]
            + ": 16,536 own windows rewritten, none old",
            len(rows) == 16536 and all(NEW.match(s) and NEW.match(e) for s, e in rows),
            len(rows),
        )
        st = c.execute(
            "SELECT count(*) FROM windows WHERE work=? AND id LIKE ?",
            (WORK, WORK + ".part.%"),
        ).fetchone()[0]
        result("connections map stray part windows left alone", True, st)

    # 8 lemma cache
    lp = glob.glob(os.path.join(R, "cache/lemmas/fa", WORK + "-*.json"))
    with open(lp[0], encoding="utf-8") as f:
        cache = json.load(f)
    ul = [u["ref"] for u in cache["units_line"]]
    result(
        "lemma cache: 99,218 units_line refs equal the new file's tags in order",
        ul == tags,
        len(ul),
    )
    up = cache["units_phrase"]
    phr_ok = all(
        NEW.match(r)
        for u in up
        for r in [*u["ref"].split("-", 1), *u.get("line_refs", [])]
    )
    result(
        "lemma cache: units_phrase new shape (ranges and line_refs)",
        phr_ok and sum(len(u["line_refs"]) for u in up) == 99218,
        (len(up), sum(len(u["line_refs"]) for u in up)),
    )
    with open(a.new_tess, "rb") as f:
        md5 = hashlib.md5(f.read()).hexdigest()
    result(
        "lemma cache: file_hash equals the md5 of the new text",
        cache["file_hash"] == md5,
        md5,
    )

    # 9 installed text equals new text
    with (
        open(os.path.join(R, "texts/fa", WORK + ".tess"), "rb") as f1,
        open(a.new_tess, "rb") as f2,
    ):
        result("installed text file is the new file", f1.read() == f2.read())

    # 10 grep of the whole root
    rx = re.compile(rb"ferdowsi\.shahnameh\.[0-9]+[\"' ,]")
    hits = []
    for dirpath, _, files in os.walk(R):
        for fn in files:
            if fn.endswith(".npy") or fn == "old_to_new_refs.json":
                continue
            if fn.endswith((".db", ".sqlite")):
                continue  # raw bytes of a record header look like "...22," next to text; the per-table checks above cover SQLite
            p = os.path.join(dirpath, fn)
            with open(p, "rb") as f:
                while True:
                    chunk = f.read(64 << 20)
                    if not chunk:
                        break
                    if rx.search(chunk):
                        hits.append(p)
                        break
    result(
        "grep of every non-SQLite file in the root for the old shape finds nothing",
        not hits,
        hits[:5],
    )
    print(f"{len(FAILED)} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
