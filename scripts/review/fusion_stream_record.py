#!/usr/bin/env python3
"""Record and check the server-sent events of POST /api/search-fusion.

The golden API check does not hold this route (its two fusion requests use the
GET route). A change to backend/blueprints/fusion.py::search_fusion_stream
must leave every event of the stream the same, so this script posts a fixed
list of requests to a running server, reads the stream to its end, and stores
the whole sequence of events.

    python3 scripts/review/fusion_stream_record.py record \
        --base http://127.0.0.1:5078 --out DIR --cache-dir WORKTREE/cache
    python3 scripts/review/fusion_stream_record.py check \
        --base http://127.0.0.1:5079 --against DIR --cache-dir WORKTREE/cache
    python3 scripts/review/fusion_stream_record.py time \
        --base http://127.0.0.1:5078 --runs 5

Both servers should be started with the same PYTHONHASHSEED (for example 0).

What is stored per request: the list of parsed events in order. Removed or
normalised so two runs can match: `elapsed`, `elapsed_time` (removed),
`result_id` (replaced by the word "present"), keep-alive comment lines (counted
and reported, not stored, and not compared because their number depends on
timing). Scores are compared as exact numbers.

Cache state: a request that finishes writes the result cache. Before each
request the script deletes every file in the cache directory (and in the paged
results directory) that was not there when the script started, so each request
meets the same cache as the one before the script, and a run leaves the
directories as it found them. A request marked `warm` is the exception: it is
sent straight after its cold twin so that the cache path is recorded too.
"""
import argparse
import json
import os
import statistics
import sys
import time
import urllib.request
import uuid

LA1 = ("catullus.carmina.part.1.tess", "propertius.elegies.part.1.tess")

REQUESTS = [
    ("01_la_plain", dict(language="la", source=LA1[0], target=LA1[1])),
    ("01b_la_plain_cached", dict(language="la", source=LA1[0], target=LA1[1]),
     "warm"),
    ("02_la_skip_cache", dict(language="la", source=LA1[0], target=LA1[1],
                              skip_cache=True)),
    ("03_la_formula_max", dict(language="la", source="vergil.aeneid.part.1.tess",
                               target="lucan.bellum_civile.part.1.tess",
                               formula_max=50)),
    ("04_la_formula_only", dict(language="la", source="vergil.aeneid.part.1.tess",
                                target="lucan.bellum_civile.part.1.tess",
                                formula_only=True)),
    ("05_grc_line", dict(language="grc", source="homer.iliad.part.1.tess",
                         target="apollonius_rhodius.argonautica.part.1.tess",
                         mode="line")),
    ("06_grc_window", dict(language="grc", source="homer.iliad.part.1.tess",
                           target="apollonius_rhodius.argonautica.part.1.tess",
                           mode="window")),
    ("07_la_disabled", dict(language="la", source=LA1[0], target=LA1[1],
                            disabled_channels=["sound", "edit_distance"])),
    ("08_la_weights", dict(language="la", source=LA1[0], target=LA1[1],
                           channel_weights={"lemma": 2.5, "exact": 0.5})),
    ("09_la_meter", dict(language="la", source=LA1[0], target=LA1[1],
                         use_meter=True)),
    ("10_cop", dict(language="cop", source="sahidica.1_john.tess",
                    target="sahidica.1_peter.tess")),
    ("11_fa", dict(language="fa", source="hafez.diwan.tess",
                   target="iqbal.asrar_e_khudi.tess")),
    ("12_la_paged", dict(language="la", source=LA1[0], target=LA1[1],
                         page_size=20)),
    ("13_error_no_target", dict(language="la", source=LA1[0])),
    ("14_error_source_only", dict(source=LA1[0])),
]

DROP = ("elapsed", "elapsed_time")


def normalise(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in DROP:
                continue
            out[k] = "present" if k == "result_id" else normalise(v)
        return out
    if isinstance(obj, list):
        return [normalise(x) for x in obj]
    return obj


def post(base, body):
    """POST and read the stream to the end. Returns (events, keepalives, t_first, t_total)."""
    body = dict(body)
    body["search_id"] = str(uuid.uuid4())
    req = urllib.request.Request(
        base.rstrip("/") + "/api/search-fusion",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    events, keep = [], 0
    t0 = time.time()
    t_first = None
    with urllib.request.urlopen(req, timeout=600) as resp:
        buf = ""
        while True:
            chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
            if not chunk:
                break
            buf += chunk.decode("utf-8")
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                if t_first is None:
                    t_first = time.time() - t0
                if block.startswith(":"):
                    keep += 1
                elif block.startswith("data: "):
                    events.append(json.loads(block[6:]))
                else:
                    events.append({"_unparsed": block})
        if buf.strip():
            events.append({"_trailing": buf})
    return events, keep, t_first, time.time() - t0


def snapshot(dirs):
    snap = {}
    for d in dirs:
        snap[d] = set(os.listdir(d)) if d and os.path.isdir(d) else set()
    return snap


def restore(snap):
    for d, names in snap.items():
        if not os.path.isdir(d):
            continue
        for n in os.listdir(d):
            if n not in names:
                try:
                    os.remove(os.path.join(d, n))
                except OSError:
                    pass


def run_all(base, dirs, only=None):
    snap = snapshot(dirs)
    results = {}
    try:
        for item in REQUESTS:
            name, body = item[0], item[1]
            warm = len(item) > 2
            if only and name not in only:
                continue
            if not warm:
                restore(snap)
            events, keep, t_first, t_total = post(base, body)
            results[name] = {"events": [normalise(e) for e in events],
                             "keepalives": keep}
            types = [e.get("type", "?") for e in events]
            print(f"  {name}: {len(events)} events, {keep} keep-alive, "
                  f"types={_summary(types)}", flush=True)
    finally:
        restore(snap)
    return results


def _summary(types):
    out, last, n = [], None, 0
    for t in types:
        if t == last:
            n += 1
        else:
            if last is not None:
                out.append(f"{last}x{n}" if n > 1 else last)
            last, n = t, 1
    if last is not None:
        out.append(f"{last}x{n}" if n > 1 else last)
    return ",".join(out)


def cmd_record(a):
    os.makedirs(a.out, exist_ok=True)
    dirs = [a.cache_dir, a.pages_dir]
    res = run_all(a.base, dirs)
    for name, r in res.items():
        with open(os.path.join(a.out, name + ".json"), "w") as f:
            json.dump(r["events"], f, sort_keys=True, ensure_ascii=False)
    with open(os.path.join(a.out, "manifest.json"), "w") as f:
        json.dump({"base": a.base, "recorded": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "requests": {k: len(v["events"]) for k, v in res.items()},
                   "keepalives": {k: v["keepalives"] for k, v in res.items()}},
                  f, indent=1)
    print(f"recorded {len(res)} requests to {a.out}")
    return 0


def first_diff(a, b, path=""):
    if type(a) is not type(b):
        return f"{path}: {a!r:.120} != {b!r:.120}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}/{k}: key only in {'recorded' if k in a else 'new'}"
            d = first_diff(a[k], b[k], f"{path}/{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: length {len(a)} != {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if a == b else f"{path}: {a!r:.120} != {b!r:.120}"


def cmd_check(a):
    dirs = [a.cache_dir, a.pages_dir]
    res = run_all(a.base, dirs, only=a.only)
    bad = 0
    for name, r in res.items():
        with open(os.path.join(a.against, name + ".json")) as f:
            rec = json.load(f)
        d = first_diff(rec, r["events"])
        if d:
            bad += 1
            print(f"DIFFERENT {name}: {d}")
        else:
            print(f"same      {name} ({len(rec)} events)")
    print(f"{len(res) - bad} same, {bad} different")
    return 1 if bad else 0


def cmd_time(a):
    """First-event and total time, uncached (skip_cache) and cached, medians."""
    dirs = [a.cache_dir, a.pages_dir]
    snap = snapshot(dirs)
    body = dict(language="la", source=LA1[0], target=LA1[1])
    try:
        for label, extra in (("uncached (skip_cache)", {"skip_cache": True}),
                             ("cached", {})):
            firsts, totals = [], []
            if not extra:
                post(a.base, body)  # make sure the cache holds the pair
            for _ in range(a.runs):
                _, _, tf, tt = post(a.base, {**body, **extra})
                firsts.append(tf)
                totals.append(tt)
            print(f"{label}: first event median {statistics.median(firsts):.4f}s "
                  f"total median {statistics.median(totals):.4f}s  "
                  f"(firsts {[round(x, 4) for x in firsts]} totals {[round(x, 3) for x in totals]})")
    finally:
        restore(snap)
    return 0


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("record", cmd_record), ("check", cmd_check), ("time", cmd_time)):
        s = sub.add_parser(name)
        s.add_argument("--base", required=True)
        s.add_argument("--cache-dir", default=None)
        s.add_argument("--pages-dir", default=None)
        if name == "record":
            s.add_argument("--out", required=True)
        if name == "check":
            s.add_argument("--against", required=True)
            s.add_argument("--only", action="append")
        if name == "time":
            s.add_argument("--runs", type=int, default=5)
        s.set_defaults(fn=fn)
    a = p.parse_args()
    if a.cache_dir and not a.pages_dir:
        a.pages_dir = os.path.join(os.path.dirname(a.cache_dir.rstrip("/")),
                                   "tmp", "search_results")
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
