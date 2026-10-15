#!/usr/bin/env python3
"""A recorded "nothing changed" check of the Tesserae API.

`record` sends every request in golden_requests.json to a server and stores the
normalised answers. `check` sends the same requests later (to a preview server
built from a branch, or to the live site after a deploy) and compares. A
structural change to the code must leave every answer the same.

    golden_api.py record --base https://tesserae.caset.buffalo.edu --out DIR
    golden_api.py check  --base http://127.0.0.1:5077 --against DIR
    golden_api.py check  --base ... --against DIR --only NAME
    golden_api.py check  --base ... --against DIR --update NAME   # re-record one
    golden_api.py check  --base ... --against DIR --preview       # skip requests marked skip_on_preview
    golden_api.py stability --base URL                            # run each request twice, list differences

Standard library only. See README_GOLDEN.md.
"""
import argparse
import difflib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_REQUESTS = os.path.join(HERE, "golden_requests.json")

# Keys that change from one run to the next without the answer changing.
GLOBAL_IGNORE = {
    "elapsed", "elapsed_time", "took", "time", "timing", "duration",
    "timestamp", "generated", "generated_at", "cache", "cached", "cache_hit",
    "request_id", "server_version", "build", "search_time", "last_updated", "last_updated_raw", "bundle",
}


def load_requests(path):
    with open(path, encoding="utf-8") as f:
        reqs = json.load(f)["requests"]
    names = [r["name"] for r in reqs]
    if len(names) != len(set(names)):
        sys.exit("duplicate request names in " + path)
    return reqs


def build_url(base, req):
    url = base.rstrip("/") + urllib.parse.quote(req["path"], safe="/%:@")
    params = req.get("params")
    if params:
        pairs = []
        for k, v in params.items():
            if isinstance(v, list):
                pairs.extend((k, str(x)) for x in v)
            else:
                pairs.append((k, str(v)))
        url += "?" + urllib.parse.urlencode(pairs)
    return url


def fetch(base, req, timeout=600):
    """Return (status, parsed body or text). Follows the async-poll pattern
    when a request declares `poll` (a path template and the id key)."""
    url = build_url(base, req)
    method = req.get("method", "GET")
    data = None
    headers = {"Accept": "application/json", "User-Agent": "tesserae-golden-check"}
    if "body" in req:
        data = json.dumps(req["body"]).encode("utf-8")
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            status, raw = resp.status, resp.read()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read()
    body = decode(raw)
    poll = req.get("poll")
    if poll and poll.get("same_url"):
        # A job-style GET: the same URL answers {"status": "running"} until
        # the result is ready.
        deadline = time.time() + poll.get("max_seconds", 900)
        while isinstance(body, dict) and body.get("status") in ("running", "queued", "pending", "started") \
                and time.time() < deadline:
            time.sleep(poll.get("every", 5))
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as resp:
                    status, raw = resp.status, resp.read()
            except urllib.error.HTTPError as e:
                status, raw = e.code, e.read()
            body = decode(raw)
    elif poll and isinstance(body, dict) and body.get(poll["id_key"]):
        pid = body[poll["id_key"]]
        deadline = time.time() + poll.get("max_seconds", 900)
        while time.time() < deadline:
            time.sleep(poll.get("every", 2))
            purl = base.rstrip("/") + poll["path"].replace("{id}", urllib.parse.quote(str(pid)))
            try:
                with urllib.request.urlopen(urllib.request.Request(purl, headers=headers), timeout=timeout) as resp:
                    status, raw = resp.status, resp.read()
            except urllib.error.HTTPError as e:
                status, raw = e.code, e.read()
            body = decode(raw)
            st = body.get("status") if isinstance(body, dict) else None
            if st in poll.get("done", ["complete", "completed", "done", "error", "failed"]):
                break
    return status, body


def decode(raw):
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {"_text": raw.decode("utf-8", "replace")}


# Fields compared to a fixed number of decimals. The Theme Search reader's scores
# vary in the seventh decimal from run to run since #911 (scores are kept per
# passage, so a later search batches only the passages not yet scored, and the
# batch changes the floating-point sums) and the length-sorted reader batches of 2026-10-14. The
# order of the results does not change; five decimals still catches any real
# change of score.
ROUND_FIELDS = {"reader_score": 5}


def scrub(obj, ignore):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ignore:
                continue
            if k in ROUND_FIELDS and isinstance(v, float):
                v = round(v, ROUND_FIELDS[k])
            out[k] = scrub(v, ignore)
        return out
    if isinstance(obj, list):  # order is part of the answer
        return [scrub(v, ignore) for v in obj]
    return obj


def sort_unordered(obj, keys):
    """Sort the lists found under the named keys into a canonical order.

    Used only for requests whose server builds a list from a set or a hash
    (the order then differs between two server processes although the content
    is identical). The CONTENT is still compared in full, only the position of
    the items is not. A request declares the keys in `unordered`."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            v = sort_unordered(v, keys)
            if k in keys and isinstance(v, list):
                v = sorted(v, key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
            out[k] = v
        return out
    if isinstance(obj, list):
        return [sort_unordered(v, keys) for v in obj]
    return obj


def normalise(req, status, body):
    ignore = GLOBAL_IGNORE | set(req.get("ignore", []))
    body = scrub(body, ignore)
    if req.get("unordered"):
        body = sort_unordered(body, set(req["unordered"]))
    doc = {"status": status, "body": body}
    if req.get("loose"):
        doc["loose"] = loose_summary(req["loose"], status, body)
    return json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def dig(obj, path):
    for part in path.split("."):
        obj = obj.get(part) if isinstance(obj, dict) else None
    return obj


def loose_summary(spec, status, body):
    """The identity of the top results of a request whose full answer is not
    the same from one server process to the next (see README_GOLDEN.md)."""
    items = dig(body, spec["list"]) if isinstance(body, dict) else None
    ids = []
    for it in (items or [])[: spec.get("top", 30)]:
        ids.append("|".join(str(dig(it, p)) for p in spec["id"]))
    return {"status": status, "top": ids}


def fname(name):
    return os.path.join("{}.json".format(name))


def selected(reqs, only, preview):
    out = []
    for r in reqs:
        if only and r["name"] != only:
            continue
        if preview and r.get("skip_on_preview"):
            continue
        out.append(r)
    if only and not out:
        sys.exit("no request named " + only)
    return out


def commit_of(base):
    for p in ("/api/version", "/api/health"):
        try:
            with urllib.request.urlopen(base.rstrip("/") + p, timeout=30) as resp:
                return {p: json.loads(resp.read().decode("utf-8"))}
        except Exception:
            continue
    return None


def cmd_record(a):
    reqs = selected(load_requests(a.requests), a.only, False)
    os.makedirs(a.out, exist_ok=True)
    for r in reqs:
        t = time.time()
        status, body = fetch(a.base, r)
        with open(os.path.join(a.out, fname(r["name"])), "w", encoding="utf-8") as f:
            f.write(normalise(r, status, body))
        print("recorded {:<42} {} {:.1f}s".format(r["name"], status, time.time() - t), flush=True)
    if not a.only:
        with open(os.path.join(a.out, "manifest.json"), "w") as f:
            json.dump({"base": a.base, "server": commit_of(a.base),
                       "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "requests": [r["name"] for r in reqs]}, f, indent=1)
    return 0


def cmd_check(a):
    reqs = selected(load_requests(a.requests), a.only or a.update, a.preview)
    if a.update:
        a.out = a.against
        a.only = a.update
        return cmd_record(a)
    bad = 0
    for r in reqs:
        path = os.path.join(a.against, fname(r["name"]))
        if not os.path.exists(path):
            print("MISSING   {} (no recording)".format(r["name"]))
            bad += 1
            continue
        with open(path, encoding="utf-8") as f:
            old = f.read()
        status, body = fetch(a.base, r)
        new = normalise(r, status, body)
        if old == new:
            print("same      {}".format(r["name"]), flush=True)
            continue
        if r.get("loose") and not a.strict:
            lo, ln = json.loads(old)["loose"], json.loads(new)["loose"]
            a_ids, b_ids = set(lo["top"]), set(ln["top"])
            overlap = len(a_ids & b_ids) / max(len(a_ids | b_ids), 1)
            need = r["loose"].get("min_overlap", 0.8)
            if lo["status"] == ln["status"] and overlap >= need:
                print("same      {} (loose: {:.0%} of the top {} results shared; "
                      "the full answer differs between server processes)".format(r["name"], overlap, len(a_ids)), flush=True)
                continue
            print("DIFFERENT {} (loose: only {:.0%} of the top results shared, need {:.0%})".format(
                r["name"], overlap, need), flush=True)
            bad += 1
            continue
        bad += 1
        print("DIFFERENT {}".format(r["name"]), flush=True)
        diff = list(difflib.unified_diff(old.splitlines(), new.splitlines(),
                                         "recorded", "now", lineterm="", n=1))
        for line in diff[:a.diff_lines]:
            print("    " + line[:200])
        if len(diff) > a.diff_lines:
            print("    ... {} more diff lines".format(len(diff) - a.diff_lines))
    print("\n{} of {} requests DIFFERENT".format(bad, len(reqs)) if bad else "\nall {} requests same".format(len(reqs)))
    return 1 if bad else 0


def cmd_stability(a):
    """Send each request twice to one server and report any that differ."""
    reqs = selected(load_requests(a.requests), a.only, False)
    bad = 0
    for r in reqs:
        one = normalise(r, *fetch(a.base, r))
        two = normalise(r, *fetch(a.base, r))
        if one == two:
            print("stable    {}".format(r["name"]), flush=True)
        else:
            bad += 1
            print("UNSTABLE  {}".format(r["name"]), flush=True)
            diff = list(difflib.unified_diff(one.splitlines(), two.splitlines(), "first", "second", lineterm="", n=0))
            for line in diff[:12]:
                print("    " + line[:200])
    print("\n{} unstable of {}".format(bad, len(reqs)))
    return 1 if bad else 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("record", "check", "stability"):
        s = sub.add_parser(name)
        s.add_argument("--base", required=True)
        s.add_argument("--requests", default=DEFAULT_REQUESTS)
        s.add_argument("--only")
        if name == "record":
            s.add_argument("--out", required=True)
        if name == "check":
            s.add_argument("--against", required=True)
            s.add_argument("--update", metavar="NAME")
            s.add_argument("--preview", action="store_true", help="skip requests marked skip_on_preview")
            s.add_argument("--strict", action="store_true",
                           help="compare the full answer of loose requests too (for two servers started with the same PYTHONHASHSEED)")
            s.add_argument("--diff-lines", type=int, default=14)
    a = p.parse_args()
    sys.exit({"record": cmd_record, "check": cmd_check, "stability": cmd_stability}[a.cmd](a))


if __name__ == "__main__":
    main()
