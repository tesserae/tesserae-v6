"""Checks on a syntax database built by gap_build.py (read-only).

gap_check.py coverage --lang la --db DB --texts DIR --plan PLAN [--label before|after]
gap_check.py refs     --lang la --db NEW --texts DIR --plan PLAN [--n 10]
gap_check.py fusion   --lang la --db NEW --live-db LIVE --texts DIR --plan PLAN
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
from syntax_gap_lib import (  # noqa: E402
    PART_RE,
    open_ro,
    read_tess,
)


def live_files(texts):
    return sorted(f for f in os.listdir(texts) if f.endswith(".tess"))


def cmd_coverage(a):
    plan = json.load(open(a.plan))
    conn = open_ro(a.db)
    have = {
        fn: n
        for fn, n in conn.execute(
            "SELECT t.filename, COUNT(s.ref) FROM texts t JOIN syntax s USING (text_id) GROUP BY t.filename"
        )
    }
    files = live_files(a.texts)
    whole = [f for f in files if not PART_RE.match(f)]
    parsed = [f for f in files if have.get(f)]
    wparsed = [f for f in whole if have.get(f)]
    excl = set(plan["excluded"])
    missing = [f for f in files if not have.get(f)]
    unexplained = [f for f in missing if f not in excl and f not in set(plan["empty"])]
    # line-level: tags that resolve
    n_tags = n_read = 0
    for f in files:
        tags = {t for t, _ in read_tess(os.path.join(a.texts, f))}
        n_tags += len(tags)
        if have.get(f):
            refs = {
                r
                for (r,) in conn.execute(
                    "SELECT ref FROM syntax s JOIN texts t USING (text_id) WHERE t.filename=?",
                    (f,),
                )
            }
            n_read += len(tags & refs)
    print(
        json.dumps(
            {
                "label": a.label,
                "lang": a.lang,
                "live_files": len(files),
                "with_a_parse": len(parsed),
                "whole_works": len(whole),
                "whole_works_with_a_parse": len(wparsed),
                "files_without_rows_and_excluded": len(
                    [f for f in missing if f in excl]
                ),
                "files_without_rows_and_empty": len(
                    [f for f in missing if f in set(plan["empty"])]
                ),
                "files_without_rows_unexplained": len(unexplained),
                "unexplained_examples": unexplained[:10],
                "distinct_tags": n_tags,
                "tags_with_a_readable_row": n_read,
                "readable_line_share": round(n_read / max(1, n_tags), 4),
            }
        )
    )


def cmd_refs(a):
    plan = json.load(open(a.plan))
    conn = open_ro(a.db)
    live = set(live_files(a.texts))
    new = [f for f in plan["parse"] if f not in plan["parsed_before"]] + [
        f for f in plan["copy"] if f not in plan["parsed_before"]
    ]
    new = sorted({f for f in new if f in live})
    step = max(1, len(new) // a.n)
    pick = new[::step][: a.n]
    bad = 0
    for f in pick:
        tl = read_tess(os.path.join(a.texts, f))
        tags = list(dict.fromkeys(t for t, _ in tl))
        refs = {
            r
            for (r,) in conn.execute(
                "SELECT ref FROM syntax s JOIN texts t USING (text_id) WHERE t.filename=?",
                (f,),
            )
        }
        miss = [t for t in tags if t not in refs]
        # a tag with no row is acceptable only when the line failed to parse (reported), never because the ref differs
        stray = refs - set(tags)
        print(
            f"{f}: {len(tags)} tags, {len(tags) - len(miss)} resolve, {len(miss)} without a row, {len(stray)} rows under a ref that is not a tag"
        )
        bad += len(stray)
    print("rows under a non-tag ref in the ten files:", bad)


def cmd_fusion(a):
    plan = json.load(open(a.plan))
    from backend import fusion

    open_ro(a.db)
    live = open_ro(a.live_db)
    live_names = {fn for (fn,) in live.execute("SELECT filename FROM texts")}
    cand = []
    for f in sorted(set(plan["parse"]) | set(plan["copy"])):
        if f in plan["parsed_before"] or f in live_names or ".part." in f:
            continue
        n = len(read_tess(os.path.join(a.texts, f)))
        if 800 <= n <= 2500:
            cand.append((f, n))
    if len(cand) < 2:
        sys.exit("no pair of mid-size newly covered files")
    # try pairs until one shows the syntax channel contributing on the new database
    for i in range(len(cand)):
        for j in range(i + 1, min(len(cand), i + 6)):
            sf, tf = cand[i][0], cand[j][0]

            def units(f):
                return [
                    {
                        "ref": t,
                        "text": x,
                        "tokens": x.split(),
                        "lemmas": x.lower().split(),
                    }
                    for t, x in read_tess(os.path.join(a.texts, f))
                ]

            su, tu = units(sf), units(tf)
            out = {}
            for label, path in (("new", a.db), ("live", a.live_db)):
                if a.lang == "grc":
                    fusion._SYNTAX_GREEK_DB_PATH = path
                else:
                    fusion._SYNTAX_DB_PATH = path
                fusion._SYNTAX_PARSE_CACHE.clear()
                r = fusion.find_syntax_matches(
                    su,
                    tu,
                    sf,
                    tf,
                    min_score=0.1,
                    max_results=50000,
                    source_language=a.lang,
                    target_language=a.lang,
                )
                out[label] = (
                    {k: len(v) for k, v in r.items()}
                    if isinstance(r, dict)
                    else {"raw": len(r)}
                )
            print(
                json.dumps(
                    {
                        "source": sf,
                        "target": tf,
                        "new_db": out["new"],
                        "live_db": out["live"],
                    }
                )
            )
            if sum(out["new"].values()) > 0:
                return
    print("no pair showed syntax results on the new database")


ap = argparse.ArgumentParser()
sp = ap.add_subparsers(dest="cmd", required=True)
for name in ("coverage", "refs", "fusion"):
    p = sp.add_parser(name)
    p.add_argument("--lang", required=True)
    p.add_argument("--db", required=True)
    p.add_argument("--texts", required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--label", default="")
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--live-db", default="")
a = ap.parse_args()
{"coverage": cmd_coverage, "refs": cmd_refs, "fusion": cmd_fusion}[a.cmd](a)
