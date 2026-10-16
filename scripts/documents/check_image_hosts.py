#!/usr/bin/env python3
"""Weekly check of the hosts behind the `image_url` links on document pages.

Lists every distinct host of an `image_url` in the documents metadata.db with
its row count, probes up to six sample links per host, and appends one check
per host to a status file (default data/documents/image_host_status.json):

  {"updated": iso, "hosts": {host: {"rows": n,
      "checks": [{"date": "YYYY-MM-DD", "ok": bool, "codes": [..]}],
      "down_since": "YYYY-MM-DD" | null}}}

A host is "ok" when at least half its sample links return 200. Only the last
twelve checks are kept. `down_since` is the date of the first failed check in
the current run of failures, null when the latest check passed. The page hides
a host's links while its two most recent checks both failed
(backend.documents.down_image_hosts).

  check_image_hosts.py [--db PATH] [--status PATH] [--only HOST]... [--dry-run]
  check_image_hosts.py --seed [--status PATH]    first state from the 9 and 16 October audits

Never writes anywhere but the status file.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import json
import os
import sqlite3
import sys
import tempfile
import urllib.request
from urllib.parse import urlsplit

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB = os.path.join(ROOT, "data", "documents", "metadata.db")
DEFAULT_STATUS = os.path.join(ROOT, "data", "documents", "image_host_status.json")

SAMPLES_PER_HOST = 6
TIMEOUT = 15
MAX_CHECKS = 12
MAX_HOSTS_AT_ONCE = 4
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36")

# Audit results the seed records (PR #743 on 9 October, recheck on 16 October).
SEED_DATES = ("2026-10-09", "2026-10-16")
SEED_DOWN = {
    "petriecat.museums.ucl.ac.uk": 500,
    "papyri-leipzig.dl.uni-leipzig.de": 500,
    "papyri-erlangen.dl.uni-leipzig.de": 500,
    "papyri-koeln.dl.uni-leipzig.de": 500,
    "papyri-wuerzburg.dl.uni-leipzig.de": 500,
    "www.ville-ge.ch": 503,
    "papyri.uni-koeln.de": 400,
}
SEED_RECOVERED = ("www.uni-koeln.de", "papyri.uni-leipzig.de")


def host_of(url):
    if not (url or "").lower().startswith(("http://", "https://")):
        return ""
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def collect_hosts(db_path):
    """{host: [row count, [sample urls]]} for every http(s) image_url."""
    con = sqlite3.connect(db_path)
    try:
        out = {}
        for (value,) in con.execute("SELECT value FROM display WHERE field='image_url'"):
            h = host_of(value)
            if not h:
                continue
            entry = out.setdefault(h, [0, []])
            entry[0] += 1
            if len(entry[1]) < SAMPLES_PER_HOST and value not in entry[1]:
                entry[1].append(value)
        return out
    finally:
        con.close()


def probe_url(url):
    """HTTP status of one GET (redirects followed), 0 on a network failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:  # nosec B310
            r.read(1024)
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:  # noqa: BLE001
        return 0


def probe_host(urls, prober=probe_url):
    """Probe a host's sample links one at a time -> (ok, codes)."""
    codes = [prober(u) for u in urls]
    return host_ok(codes), codes


def host_ok(codes):
    return bool(codes) and sum(1 for c in codes if c == 200) * 2 >= len(codes)


def load_status(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data.get("hosts"), dict):
            return data
    except (OSError, ValueError):
        pass
    return {"updated": None, "hosts": {}}


def recompute_down_since(checks):
    """Date of the first failed check in the trailing run of failures."""
    since = None
    for c in checks:
        if c["ok"]:
            since = None
        elif since is None:
            since = c["date"]
    return since


def add_check(status, host, rows, date, ok, codes, replace_same_date=True):
    """Append one check to a host. A second check on the same date replaces
    the first; the seed never replaces (see seed())."""
    entry = status["hosts"].setdefault(host, {"rows": rows, "checks": [], "down_since": None})
    entry["rows"] = rows
    checks = entry["checks"]
    if replace_same_date:
        checks[:] = [c for c in checks if c["date"] != date]
    checks.append({"date": date, "ok": bool(ok), "codes": list(codes)})
    checks.sort(key=lambda c: c["date"])
    del checks[:-MAX_CHECKS]
    entry["down_since"] = recompute_down_since(checks)


def seed(status, row_counts=None):
    """Two checks per host for the audit dates. Never overwrites a check that
    already exists for that date, real or seeded."""
    row_counts = row_counts or {}
    for host, code in SEED_DOWN.items():
        for date in SEED_DATES:
            have = {c["date"] for c in status["hosts"].get(host, {}).get("checks", [])}
            if date not in have:
                add_check(status, host, row_counts.get(host, 0), date, False, [code],
                          replace_same_date=False)
    for host in SEED_RECOVERED:
        for date in SEED_DATES:
            have = {c["date"] for c in status["hosts"].get(host, {}).get("checks", [])}
            if date not in have:
                add_check(status, host, row_counts.get(host, 0), date, True, [200],
                          replace_same_date=False)
    return status


def write_status(path, status):
    status["updated"] = datetime.datetime.now().isoformat(timespec="seconds")
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".image_host_status.")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=1, sort_keys=True)
    os.chmod(tmp, 0o664)
    os.replace(tmp, path)


def run_checks(hosts, status, date, prober=probe_url):
    """Probe each host (one request at a time per host, up to four hosts at
    once) and add a check. Returns {host: (ok, codes)}."""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_HOSTS_AT_ONCE) as ex:
        futs = {ex.submit(probe_host, urls, prober): h for h, (_n, urls) in hosts.items()}
        for fut in concurrent.futures.as_completed(futs):
            h = futs[fut]
            results[h] = fut.result()
    for h, (ok, codes) in results.items():
        add_check(status, h, hosts[h][0], date, ok, codes)
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--status", default=DEFAULT_STATUS)
    ap.add_argument("--only", action="append", default=[], metavar="HOST")
    ap.add_argument("--seed", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    status = load_status(a.status)
    hosts = {}
    if os.path.exists(a.db):
        hosts = collect_hosts(a.db)
    if a.seed:
        seed(status, {h: v[0] for h, v in hosts.items()})
        print(f"seeded {len(SEED_DOWN) + len(SEED_RECOVERED)} hosts")
    else:
        if not hosts:
            print(f"no image hosts found in {a.db}", file=sys.stderr)
            return 2
        if a.only:
            hosts = {h: v for h, v in hosts.items() if h in a.only}
            for h in a.only:
                if h not in hosts:
                    print(f"host not in the data: {h}", file=sys.stderr)
        today = datetime.date.today().isoformat()
        results = run_checks(hosts, status, today)
        for h in sorted(results, key=lambda x: -hosts[x][0]):
            ok, codes = results[h]
            print(f"{hosts[h][0]:7d}  {'ok  ' if ok else 'DOWN'}  {h}  {codes}")
    if a.dry_run:
        print("dry run: status file not written")
    else:
        write_status(a.status, status)
        print(f"wrote {a.status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
