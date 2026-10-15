#!/usr/bin/env python3
"""Record, check and time Line Search and wildcard search, in process.

    python scripts/review/line_search_profile.py record  --set line|wildcard --out DIR
    python scripts/review/line_search_profile.py check   --set line|wildcard --against DIR
    python scripts/review/line_search_profile.py profile --set line|wildcard --out FILE.jsonl [--passes 2]
    python scripts/review/line_search_profile.py summarize FILE.jsonl [FILE.jsonl ...] [--pass N]

--set line      the 258 requests of scripts/review/line_search_requests.json
--set wildcard  the queries of scripts/review/wildcard_requests.json

`record` and `check` build a small Flask app around the Line Search and
wildcard routes (no server, no database) and send every request through its
test client. The whole answer is stored, with the keys that change from one run
to the next removed (golden_api.GLOBAL_IGNORE plus `search_time`), and `check`
compares each stored answer with a fresh one and exits 1 on any difference.

`profile` sends every request `--passes` times in one process (pass 1 meets
empty per-process caches, pass 2 is warm), and writes one JSON line per request
with the time of each named step of line_search() (the wrappers only start and
stop a clock) and the shape of the request (language, search type, number of
words, result count). `summarize` prints median and p90 per step.

Run it under ~/bin/tess-job (it loads the frequency caches and the index).
"""
import argparse
import gzip
import json
import os
import statistics
import sys
import time
from pathlib import Path

os.environ.setdefault("TESSERAE_DIRECT_SERVER", "1")
os.environ.setdefault("TESSERAE_LANGUAGES", "la,grc,en,cop,he,fa,ur,it,gmh,fro")
os.environ.setdefault("TESSERAE_DOCUMENTS", "1")
os.environ.setdefault("TESSERAE_MAX_WORKERS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/line_search_profile.db")
os.environ.setdefault("SESSION_SECRET", "throwaway")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from golden_api import GLOBAL_IGNORE, scrub  # noqa: E402

IGNORE = set(GLOBAL_IGNORE) | {"search_time"}

SETS = {
    "line": HERE / "line_search_requests.json",
    "wildcard": HERE / "wildcard_requests.json",
}

STEPS = [
    "_documents_only", "_language_dirs", "_stoplist", "_query_lemmas", "_hebrew_fallbacks",
    "_drop_stopwords", "_reduce_passage_query", "_univerbation_variants", "_single_word_count",
    "_candidates", "_indexed_candidates", "_scanned_candidates", "_sort", "_dedup",
    "_rare_focus", "_payload", "_append_documents",
]

_acc = {}


def _wrap(mod, name):
    fn = getattr(mod, name)

    def timed(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            _acc[name] = _acc.get(name, 0.0) + time.perf_counter() - t0
    setattr(mod, name, timed)


def make_client(install_timers=False):
    from flask import Flask
    from flask_login import LoginManager
    from backend.blueprints import line_search as ls
    from backend.blueprints import search as sr
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "throwaway"
    login_manager = LoginManager(app)
    login_manager.user_loader(lambda user_id: None)
    # No database in this tool: the search log is a no-op.
    ls.log_search = lambda *a, **k: None
    sr.log_search = lambda *a, **k: None
    if install_timers:
        for s in STEPS:
            if hasattr(ls, s):
                _wrap(ls, s)
        import backend.wildcard_search as ws
        _wrap(ws, "search_file")
    app.register_blueprint(ls.line_search_bp)
    app.register_blueprint(sr.search_bp, url_prefix="/api")
    return app.test_client()


def load_set(which):
    reqs = json.load(open(SETS[which], encoding="utf-8"))["requests"]
    names = [r["name"] for r in reqs]
    assert len(names) == len(set(names)), "duplicate request names"
    return reqs


def send(client, req):
    method = req.get("method", "GET")
    kw = {}
    if req.get("params"):
        kw["query_string"] = {k: str(v) for k, v in req["params"].items()}
    if "body" in req:
        kw["json"] = req["body"]
    t0 = time.perf_counter()
    r = client.open(req["path"], method=method, **kw)
    dt = time.perf_counter() - t0
    try:
        body = r.get_json()
    except Exception:
        body = {"_text": r.get_data(as_text=True)[:2000]}
    return r.status_code, body, dt


def canon(req, status, body):
    return json.dumps({"status": status, "body": scrub(body, IGNORE | set(req.get("ignore", [])))},
                      sort_keys=True, ensure_ascii=False, indent=None)


def path_for(d, name):
    return Path(d) / (name + ".json.gz")


def cmd_record(a):
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    client = make_client()
    reqs = load_set(a.set)
    for i, req in enumerate(reqs):
        if a.only and req["name"] != a.only:
            continue
        status, body, dt = send(client, req)
        with gzip.open(path_for(out, req["name"]), "wt", encoding="utf-8") as f:
            f.write(canon(req, status, body))
        print(f"{i + 1:3d}/{len(reqs)} {req['name']} {status} {dt:.2f}s", flush=True)
    json.dump({"set": a.set, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
               "requests": [r["name"] for r in reqs]}, open(out / "manifest.json", "w"), indent=1)


def tie_groups(doc):
    """The results of a wildcard answer cut into runs of rows with one sort key.

    Wildcard search sorts by (year, author, reference). Two files can carry the
    same reference under one author (a work held whole and in book files), and
    those rows come back in whichever order the file scans finished, which
    differs from one run to the next on the same code. Returns None for an
    answer that has no such list.
    """
    body = doc.get("body")
    res = body.get("results") if isinstance(body, dict) else None
    if not isinstance(res, list) or not all(isinstance(r, dict) and "reference" in r for r in res):
        return None
    groups = []
    for r in res:
        key = (r.get("year") or 9999, r.get("author", ""), r.get("reference", ""))
        if groups and groups[-1][0] == key:
            groups[-1][1].append(json.dumps(r, sort_keys=True, ensure_ascii=False))
        else:
            groups.append((key, [json.dumps(r, sort_keys=True, ensure_ascii=False)]))
    return groups


def compare(now, was):
    """'same', 'tie order' (only the order inside runs of equal sort key differs),
    'tie cutoff' (as that, and the last run, cut by max_results, holds other
    members of the tie) or 'DIFFERENT'."""
    if now == was:
        return "same"
    dn, dw = json.loads(now), json.loads(was)
    gn, gw = tie_groups(dn), tie_groups(dw)
    if gn is None or gw is None or len(gn) != len(gw):
        return "DIFFERENT"
    if [(k, sorted(v)) for k, v in gn] == [(k, sorted(v)) for k, v in gw]:
        rest = dict(dn, body=dict(dn["body"], results=None))
        rest_w = dict(dw, body=dict(dw["body"], results=None))
        return "tie order" if rest == rest_w else "DIFFERENT"
    # only the last run may differ in which members it holds
    if ([(k, sorted(v)) for k, v in gn[:-1]] == [(k, sorted(v)) for k, v in gw[:-1]]
            and gn[-1][0] == gw[-1][0] and len(gn[-1][1]) == len(gw[-1][1])
            and dn["body"].get("truncated") and dw["body"].get("truncated")):
        rest = dict(dn, body=dict(dn["body"], results=None))
        rest_w = dict(dw, body=dict(dw["body"], results=None))
        return "tie cutoff" if rest == rest_w else "DIFFERENT"
    return "DIFFERENT"


def cmd_check(a):
    client = make_client()
    reqs = load_set(a.set)
    bad = 0
    kinds = {}
    for i, req in enumerate(reqs):
        if a.only and req["name"] != a.only:
            continue
        status, body, dt = send(client, req)
        now = canon(req, status, body)
        with gzip.open(path_for(a.against, req["name"]), "rt", encoding="utf-8") as f:
            was = f.read()
        kind = compare(now, was) if a.set == "wildcard" else ("same" if now == was else "DIFFERENT")
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind != "DIFFERENT":
            print(f"{kind:10s} {req['name']} ({dt:.2f}s)", flush=True)
        else:
            bad += 1
            j = next((k for k in range(min(len(now), len(was))) if now[k] != was[k]), min(len(now), len(was)))
            print(f"DIFFERENT  {req['name']}\n   was ...{was[max(0, j - 80):j + 120]}\n   now ...{now[max(0, j - 80):j + 120]}",
                  flush=True)
    print(f"{bad} different of {len(reqs)}  {kinds}")
    sys.exit(1 if bad else 0)


def shape(req, body):
    b = req.get("body") or req.get("params") or {}
    q = b.get("query") or b.get("line_text") or ""
    res = body.get("results") if isinstance(body, dict) else None
    return {
        "language": b.get("language"), "search_type": b.get("search_type"),
        "n_words": len(str(q).split()), "max_results": b.get("max_results"),
        "collection": b.get("collection"), "count_only": b.get("count_only"),
        "n_results": len(res) if isinstance(res, list) else None,
        "n_total": body.get("total", body.get("total_matches")) if isinstance(body, dict) else None,
        "query": str(q)[:60],
    }


def cmd_profile(a):
    client = make_client(install_timers=True)
    reqs = load_set(a.set)
    if a.first or a.count:
        reqs = reqs[a.first:a.first + a.count] if a.count else reqs[a.first:]
    out = open(a.out, "a")
    for p in range(1, a.passes + 1):
        for i, req in enumerate(reqs):
            _acc.clear()
            status, body, dt = send(client, req)
            row = {"name": req["name"], "pass": p, "status": status, "total": dt, **shape(req, body)}
            row["steps"] = dict(_acc)
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(f"p{p} {i + 1:3d}/{len(reqs)} {req['name']} {dt:.2f}s", flush=True)


def pct(vals, q):
    vals = sorted(vals)
    if not vals:
        return 0.0
    k = (len(vals) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def cmd_summarize(a):
    rows = []
    for f in a.files:
        rows += [json.loads(line) for line in open(f)]
    if a.pass_no:
        rows = [r for r in rows if r["pass"] == a.pass_no]
    if a.min_total:
        rows = [r for r in rows if r["total"] >= a.min_total]
    print(f"{len(rows)} requests")
    tot = [r["total"] for r in rows]
    print(f"total median {statistics.median(tot):.3f}s  p90 {pct(tot, .9):.3f}s  max {max(tot):.2f}s  sum {sum(tot):.1f}s")
    names = sorted({s for r in rows for s in r["steps"]})
    print(f"{'step':26s} {'median':>8s} {'p90':>8s} {'sum':>8s} {'share':>7s}")
    for s in names:
        v = [r["steps"].get(s, 0.0) for r in rows]
        print(f"{s:26s} {statistics.median(v):8.3f} {pct(v, .9):8.3f} {sum(v):8.1f} {100 * sum(v) / sum(tot):6.1f}%")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("record", "check", "profile"):
        s = sub.add_parser(c)
        s.add_argument("--set", choices=list(SETS), required=True)
        s.add_argument("--only")
        if c == "record":
            s.add_argument("--out", required=True)
        if c == "check":
            s.add_argument("--against", required=True)
        if c == "profile":
            s.add_argument("--out", required=True)
            s.add_argument("--passes", type=int, default=2)
            s.add_argument("--first", type=int, default=0)
            s.add_argument("--count", type=int, default=0)
    s = sub.add_parser("summarize")
    s.add_argument("files", nargs="+")
    s.add_argument("--pass", dest="pass_no", type=int, default=0)
    s.add_argument("--min-total", type=float, default=0.0)
    a = ap.parse_args()
    {"record": cmd_record, "check": cmd_check, "profile": cmd_profile, "summarize": cmd_summarize}[a.cmd](a)


if __name__ == "__main__":
    main()
