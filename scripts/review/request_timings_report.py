#!/usr/bin/env python3
"""Report on request-timing files written by backend/request_timing.py.

Usage: request_timings_report.py [--visitors-only] FILE [FILE...]

Columns of a file: time, method, path, status, ms, bytes, worker, and from
2026-10-15 visitor (tab-separated). The visitor column holds a daily code
for each visitor, or "local" for requests from the server itself (the site's
own checks and tools). --visitors-only leaves the local requests out.
Standard library only.
"""
import re
import sys
from collections import defaultdict


def route_of(path):
    """Collapse every segment that contains a digit or a dot to <id>."""
    parts = path.split("/")
    return "/".join("<id>" if re.search(r"[0-9.]", p) else p for p in parts)


def percentile(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def read(files):
    rows = []
    for name in files:
        # A request path can carry raw bytes (a probe sent 0x89 on 2026-10-13);
        # the report must not stop on one such row.
        with open(name, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                f = line.rstrip("\n").split("\t")
                if len(f) < 7:
                    continue
                try:
                    rows.append({"time": f[0], "method": f[1], "route": route_of(f[2]),
                                 "status": int(f[3]), "ms": float(f[4]),
                                 "visitor": f[7] if len(f) > 7 else ""})
                except ValueError:
                    continue
    return rows


def report(rows, out=sys.stdout):
    total_ms = sum(r["ms"] for r in rows) or 1.0
    by = defaultdict(list)
    for r in rows:
        by[r["route"]].append(r)
    p = lambda *a: print(*a, file=out)  # noqa: E731
    p("%d requests, %.1f seconds of wall time" % (len(rows), total_ms / 1000))
    p("\nBy route (sorted by total seconds)")
    p("%-44s %7s %9s %9s %9s %9s %6s" % ("route", "count", "median", "p90", "max", "total_s", "share"))
    for route, rs in sorted(by.items(), key=lambda kv: -sum(r["ms"] for r in kv[1])):
        ms = sorted(r["ms"] for r in rs)
        tot = sum(ms)
        p("%-44s %7d %9.1f %9.1f %9.1f %9.1f %5.1f%%" % (
            route[:44], len(ms), percentile(ms, 0.5), percentile(ms, 0.9), ms[-1],
            tot / 1000, 100 * tot / total_ms))
    p("\nTwenty slowest requests")
    for r in sorted(rows, key=lambda r: -r["ms"])[:20]:
        p("%s  %-40s %9.1f ms  %d" % (r["time"], r["route"][:40], r["ms"], r["status"]))
    p("\nStatus counts for routes with any non-2xx")
    for route, rs in sorted(by.items()):
        c = {"2xx": 0, "4xx": 0, "5xx": 0, "other": 0}
        for r in rs:
            s = r["status"]
            c["2xx" if 200 <= s < 300 else "4xx" if 400 <= s < 500
              else "5xx" if 500 <= s < 600 else "other"] += 1
        if c["2xx"] != len(rs):
            p("%-44s 2xx=%d 4xx=%d 5xx=%d other=%d" % (route[:44], c["2xx"], c["4xx"], c["5xx"], c["other"]))
    coded = [r for r in rows if r["visitor"]]
    if coded:
        local = sum(1 for r in coded if r["visitor"] == "local")
        codes = {(r["time"][:10], r["visitor"]) for r in coded if r["visitor"] not in ("local", "-")}
        p("\nVisitors (rows with a visitor column)")
        p("requests from the server itself: %d; from visitors: %d; visitor codes (per day): %d" % (
            local, len(coded) - local, len(codes)))
    p("\nRequests per hour")
    hours = defaultdict(list)
    for r in rows:
        hours[r["time"][:13]].append(r["ms"])
    for h in sorted(hours):
        ms = sorted(hours[h])
        p("%s:00  %6d  median %8.1f ms" % (h.replace("T", " "), len(ms), percentile(ms, 0.5)))


def main(argv):
    only = "--visitors-only" in argv
    argv = [a for a in argv if a != "--visitors-only"]
    if not argv:
        print(__doc__)
        return 2
    rows = read(argv)
    if only:
        rows = [r for r in rows if r["visitor"] != "local"]
    report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
